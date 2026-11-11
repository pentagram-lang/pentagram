import base64
import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, ParamSpec, TypedDict, TypeVar, cast

import click
from wcwidth import wcswidth

from zero import lib

from .errors import ProjectError
from .project import (
  BLOCKER_STATUSES,
  GOAL_STATUSES,
  TASK_STATUSES,
  UNSET,
  BlockerStatus,
  GoalDetails,
  GoalStatus,
  HandoffData,
  HandoffRetrievalInput,
  ProjectRoot,
  ProjectView,
  TaskDetails,
  TaskStatus,
  achieve_goal,
  achieve_stage,
  activate_goal,
  add_blocker,
  add_decision,
  add_evidence,
  add_stage,
  add_stage_dependency,
  add_task,
  add_task_tags,
  append_task_log,
  archive_project,
  block_goal,
  block_task,
  cancel_goal,
  cancel_task,
  complete_task,
  create_goal,
  create_project,
  goal_text,
  list_projects,
  read_blockers,
  read_decisions,
  read_evidence,
  read_goal,
  read_goals,
  read_handoff,
  read_project,
  read_stages,
  read_task,
  read_tasks,
  remove_stage_dependency,
  remove_task_tags,
  reopen_goal,
  reopen_task,
  resolve_blocker,
  start_task,
  update_project_and_state,
  update_stage,
  update_task,
)

HANDOFF_TEXT_LIMIT = 1000
_TEXT_ESCAPES = {
  **{codepoint: f'\\u{codepoint:04x}' for codepoint in range(0x7F, 0xA0)},
  0x2028: '\\u2028',
  0x2029: '\\u2029',
}

type StageReference = int | str
type GoalReference = int | Literal['active']

type HandoffPageKey = Literal[
  'blocked_tasks',
  'blocked_goals',
  'blockers',
  'decisions',
  'evidence',
  'task_log',
]

P = ParamSpec('P')
R = TypeVar('R')


class TruncatedField(TypedDict):
  path: str
  characters: int
  retrieval: str


class HandoffProjection(TypedDict):
  character_limit: int
  truncated_fields: list[TruncatedField]
  full_value_commands: list[str]


class HandoffRetrieval(TypedDict):
  project: str
  goal: str | None
  stage: str | None
  task: str | None
  blocked_tasks: str
  blocked_goals: str
  blockers: str
  ready_tasks: str
  decisions: str
  evidence: str
  task_log: str | None


class HandoffView(HandoffData):
  retrieval: HandoffRetrieval


class HandoffJson(HandoffView):
  text_projection: HandoffProjection


def _positive_id(value: object) -> int:
  if isinstance(value, int) and not isinstance(value, bool):
    result = value
  elif isinstance(value, str) and value.isdigit():
    result = int(value)
  else:
    raise ValueError('Expected a positive integer ID')
  if result < 1:
    raise ValueError('Expected a positive integer ID')
  return result


class StageReferenceType(click.ParamType):
  name = 'STAGE'

  def convert(
    self,
    value: object,
    param: click.Parameter | None,
    ctx: click.Context | None,
  ) -> StageReference | None:
    if value is None:
      return None
    if isinstance(value, str) and not value.isdigit():
      return value
    try:
      return _positive_id(value)
    except ValueError:
      self.fail('Expected a stage name or positive stage ID.', param, ctx)


class GoalReferenceType(click.ParamType):
  name = 'GOAL'

  def convert(
    self,
    value: object,
    param: click.Parameter | None,
    ctx: click.Context | None,
  ) -> GoalReference | None:
    if value is None:
      return None
    if isinstance(value, str) and value == 'active':
      return 'active'
    try:
      return _positive_id(value)
    except ValueError:
      self.fail(
        'Expected a positive goal ID or the active keyword.', param, ctx
      )


STAGE_REFERENCE = StageReferenceType()
GOAL_REFERENCE = GoalReferenceType()
POSITIVE_INTEGER = click.IntRange(min=1)


def repository_root() -> Path:
  return Path(__file__).resolve().parent.parent


def _handoff_retrieval_commands(
  data: HandoffRetrievalInput,
) -> HandoffRetrieval:
  name = data['project']['name']
  goal = data['goal']['goal'] if data['goal'] is not None else None
  task = data['task']
  stage = data['stage']
  focus_kind = data['focus']['kind']
  focus_id = data['focus']['id']
  if focus_kind is not None and focus_id is None:
    raise ProjectError('Handoff focus is missing its record ID')
  decision_count = data['pages']['decisions']['total']
  evidence_count = data['pages']['evidence']['total']
  log_count = data['pages']['task_log']['total']
  return cast(
    HandoffRetrieval,
    {
      'project': _project_command(('show',), name, options=('--json',)),
      'goal': (
        _project_command(
          ('goal', 'show'), name, (goal['id'],), ('--json',)
        )
        if goal is not None
        else None
      ),
      'stage': (
        _project_command(('stage', 'list'), name, options=('--json',))
        if stage is not None
        else None
      ),
      'task': (
        _project_command(
          ('task', 'show'), name, (task['id'],), ('--json',)
        )
        if task is not None
        else None
      ),
      'blocked_tasks': _project_command(
        ('task', 'list'),
        name,
        options=('--status', 'blocked', '--json'),
      ),
      'blocked_goals': _project_command(
        ('goal', 'list'),
        name,
        options=('--status', 'blocked', '--json'),
      ),
      'blockers': _project_command(
        ('blocker', 'list'), name, options=('--json',)
      ),
      'ready_tasks': _project_command(('task', 'ready'), name),
      'decisions': (
        _project_command(
          ('decision', 'list'),
          name,
          options=_handoff_filter_options(
            focus_kind, focus_id, decision_count
          ),
        )
        if focus_kind is not None
        else _project_command(
          ('decision', 'list'), name, options=('--json',)
        )
      ),
      'evidence': (
        _project_command(
          ('evidence', 'list'),
          name,
          options=_handoff_filter_options(
            focus_kind, focus_id, evidence_count
          ),
        )
        if focus_kind is not None
        else _project_command(
          ('evidence', 'list'), name, options=('--json',)
        )
      ),
      'task_log': (
        _project_command(
          ('task', 'list-logs'),
          name,
          (focus_id,),
          ('--limit', max(log_count, 1), '--json'),
        )
        if focus_kind == 'task' and focus_id is not None
        else None
      ),
    },
  )


def _handoff_filter_options(
  focus_kind: Literal['task', 'goal'] | None,
  focus_id: int | None,
  count: int,
) -> list[str | int]:
  if focus_kind is None:
    raise ProjectError('A filtered handoff command needs a focus kind')
  if focus_id is None:
    raise ProjectError('A filtered handoff command needs a record ID')
  options: list[str | int] = [f'--{focus_kind}', focus_id]
  if focus_kind == 'goal':
    options.append('--no-task')
  options.extend(('--limit', max(count, 1), '--json'))
  return options


def _handoff_view(data: HandoffData) -> HandoffView:
  return cast(
    HandoffView, {**data, 'retrieval': _handoff_retrieval_commands(data)}
  )


def _handoff_json(data: HandoffData) -> HandoffJson:
  view = _handoff_view(data)
  _, projection = _render_handoff(view)
  return cast(HandoffJson, {**view, 'text_projection': projection})


def format_time(value: int | None) -> str:
  if value is None:
    return '-'
  return datetime.fromtimestamp(value, UTC).isoformat()


def _format_text(value: object, default: str = '-') -> str:
  if value is None or value == '':
    return default
  rendered = _escape_text(value)
  return f'"{rendered}"' if rendered == default else rendered


def _escape_text(value: object) -> str:
  return json.dumps(str(value), ensure_ascii=False)[1:-1].translate(
    _TEXT_ESCAPES
  )


def _display_width(value: str) -> int:
  width = wcswidth(value)
  return width if width >= 0 else len(value)


def _format_table(
  headers: Sequence[str], rows: Sequence[Sequence[object]]
) -> str:
  cells = [tuple(_format_text(value) for value in row) for row in rows]
  widths = [_display_width(header) for header in headers]
  for row in cells:
    for index, value in enumerate(row):
      widths[index] = max(widths[index], _display_width(value))

  def render_row(row: Sequence[str]) -> str:
    return '  '.join(
      value + ' ' * (widths[index] - _display_width(value))
      if index < len(row) - 1
      else value
      for index, value in enumerate(row)
    )

  lines = [render_row(headers), '  '.join('-' * width for width in widths)]
  lines.extend(render_row(row) for row in cells)
  return '\n'.join(lines)


def _format_limit_notice(shown: int, limit: int) -> str | None:
  if shown < limit:
    return None
  return (
    f'Limit reached ({limit} rows); more records may exist. '
    'Increase --limit to retrieve more.'
  )


def _format_limited_table(
  headers: Sequence[str], rows: Sequence[Sequence[object]], limit: int
) -> str:
  table = _format_table(headers, rows)
  notice = _format_limit_notice(len(rows), limit)
  return f'{table}\n{notice}' if notice else table


def _field_label(name: str) -> str:
  if name == 'non_goals':
    return 'Non-goals'
  if name == 'constraints_text':
    return 'Constraints'
  return ' '.join(
    part.upper() if part == 'id' else part.capitalize()
    for part in name.split('_')
  )


def _field_value(name: str, value: object) -> str:
  if name.endswith('_at'):
    if value is not None and not isinstance(value, int):
      raise ProjectError(f'Timestamp field {name} is not an integer')
    return format_time(value)
  if isinstance(value, bool):
    return 'yes' if value else 'no'
  return _format_text(value)


def _format_fields(
  fields: Mapping[str, object], indent: int = 0
) -> list[str]:
  prefix = '  ' * indent
  return [
    f'{prefix}{_field_label(name)}: {_field_value(name, value)}'
    for name, value in fields.items()
  ]


def _format_record_list(
  label: str,
  records: Sequence[Mapping[str, object]],
  indent: int = 0,
) -> list[str]:
  prefix = '  ' * indent
  item_label = label[:-1] if label.endswith('s') else label
  lines = [f'{prefix}{label} ({len(records)}):']
  for index, record in enumerate(records, 1):
    lines.append(f'{prefix}  {item_label} {index}:')
    lines.extend(_format_fields(record, indent + 2))
  return lines


def _format_goal_details(
  data: GoalDetails, label: str = 'Goal', indent: int = 0
) -> list[str]:
  prefix = '  ' * indent
  lines = [f'{prefix}{label}:']
  lines.extend(_format_fields(data['goal'], indent + 1))
  for key, section in (
    ('stages', 'Stages'),
    ('tasks', 'Tasks'),
    ('blockers', 'Blockers'),
    ('evidence', 'Evidence'),
    ('decisions', 'Decisions'),
  ):
    lines.extend(_format_record_list(section, data[key], indent + 1))
  return lines


def _shell_quote(value: object) -> str:
  value = str(value)
  if not value:
    return "''"
  return ''.join(
    character
    if character.isascii()
    and (character.isalnum() or character in '_@%+=:,./-')
    else f'\\{character}'
    for character in value
  )


def _bounded_escaped_text(value: str, limit: int) -> tuple[str, bool]:
  if value == '-':
    return '"-"', False
  rendered = []
  rendered_length = 0
  for character in value:
    encoded = _escape_text(character)
    if rendered_length + len(encoded) > limit:
      while rendered_length + 1 > limit:
        rendered_length -= len(rendered.pop())
      return ''.join(rendered) + '…', True
    rendered.append(encoded)
    rendered_length += len(encoded)
  return ''.join(rendered), False


def _project_command(
  command: Sequence[str],
  name: str,
  arguments: Sequence[str | int] = (),
  options: Sequence[str | int] = (),
) -> str:
  parts = ('0', 'proj', *command, *options, '--', name, *arguments)
  rendered = ' '.join(_shell_quote(part) for part in parts)
  if len(rendered) > HANDOFF_TEXT_LIMIT:
    raise ProjectError(
      'Generated project recovery command exceeds the handoff text limit'
    )
  return rendered


def _handoff_retrieval(
  data: HandoffView, key: HandoffPageKey
) -> str | None:
  match key:
    case 'blocked_tasks':
      return data['retrieval']['blocked_tasks']
    case 'blocked_goals':
      return data['retrieval']['blocked_goals']
    case 'blockers':
      return data['retrieval']['blockers']
    case 'decisions':
      return data['retrieval']['decisions']
    case 'evidence':
      return data['retrieval']['evidence']
    case 'task_log':
      return data['retrieval']['task_log']


def _handoff_full_value_command(
  data: HandoffView | None, name: str, path: Sequence[str | int]
) -> str:
  if not path or not isinstance(path[0], str):
    raise ProjectError(
      'Handoff retrieval path must start with a field name'
    )
  root = path[0]
  if root in ('path', 'project', 'state'):
    return _project_command(('handoff',), name, options=('--json',))
  if data is None:
    raise ProjectError(f'No handoff retrieval data for {root}')
  if root == 'goal':
    goal = data['goal']
    if goal is None:
      raise ProjectError('There is no active goal to retrieve')
    return _project_command(
      ('goal', 'show'),
      name,
      (goal['goal']['id'],),
      ('--json',),
    )
  if root == 'stage':
    return _project_command(('stage', 'list'), name, options=('--json',))
  if root == 'task':
    task = data['task']
    if task is None:
      raise ProjectError('There is no active task to retrieve')
    return _project_command(
      ('task', 'show'), name, (task['id'],), ('--json',)
    )
  if root in ('blocked_tasks', 'blocked_goals'):
    if len(path) < 2 or not isinstance(path[1], int):
      raise ProjectError(f'Handoff {root} retrieval needs a numeric index')
    index = path[1]
    if root == 'blocked_tasks':
      task = data['blocked_tasks'][index]
      return _project_command(
        ('task', 'show'), name, (task['id'],), ('--json',)
      )
    goal = data['blocked_goals'][index]
    return _project_command(
      ('goal', 'show'), name, (goal['id'],), ('--json',)
    )
  if root in ('blockers', 'decisions', 'evidence', 'logs'):
    key: HandoffPageKey = (
      'task_log' if root == 'logs' else cast(HandoffPageKey, root)
    )
    command = _handoff_retrieval(data, key)
    if command is None:
      raise ProjectError(f'No handoff retrieval command for {root}')
    return command
  raise ProjectError(f'No handoff retrieval path for {root}')


def _handoff_page_suffix(data: HandoffView, key: HandoffPageKey) -> str:
  page = data['pages'][key]
  parts = [f'{page["shown"]} of {page["total"]}']
  if page['truncated']:
    command = _handoff_retrieval(data, key)
    if command is None:
      raise ProjectError(f'No handoff retrieval command for {key}')
    parts.append(f'more: {command}')
  return f' ({"; ".join(parts)})'


def _record_compatibility_markers(item: Mapping[str, object]) -> str:
  markers = []
  if item['context_status'] != 'complete':
    markers.append('legacy unresolved context')
  if item.get('claim_status') not in (None, 'substantive'):
    markers.append('legacy blank claim')
  return ''.join(f' [{marker}]' for marker in markers)


def _task_compatibility_markers(item: Mapping[str, object]) -> str:
  if item.get('title_status') == 'legacy-blank':
    return ' [legacy blank title]'
  return ''


def _render_handoff(data: HandoffView) -> tuple[str, HandoffProjection]:
  project = data['project']
  state = data['state']
  stage = data['stage']
  task = data['task']
  goal = data['goal']
  name = project['name']
  truncations: list[TruncatedField] = []
  commands: set[str] = set()

  def text(
    value: object, path: Sequence[str | int], default: str = '-'
  ) -> str:
    if value is None or value == '':
      return default
    value = str(value)
    rendered, truncated = _bounded_escaped_text(value, HANDOFF_TEXT_LIMIT)
    if not truncated:
      return rendered
    command = _handoff_full_value_command(data, name, path)
    commands.add(command)
    truncations.append(
      {
        'path': '.'.join(str(part) for part in path),
        'characters': len(value),
        'retrieval': command,
      }
    )
    return rendered

  lines = [
    f'Project: {text(project["name"], ("project", "name"))}',
    f'Status: {project["status"]}',
    f'Objective: {text(project["objective"], ("project", "objective"))}',
    *(
      ['Charter context: legacy incomplete']
      if project['charter_context_status'] == 'legacy-incomplete'
      else []
    ),
    f'Project database: {text(data["path"], ("path",))}',
    f'Active goal: {goal["goal"]["id"]} ({goal["goal"]["status"]})'
    if goal
    else 'Active goal: -',
    f'Goal text: {text(goal["goal"]["text"], ("goal", "goal", "text"))}'
    if goal
    else 'Goal text: -',
    f'Active stage: {text(stage["name"], ("stage", "name"))}'
    if stage
    else 'Active stage: -',
    f'Active task: {task["id"]}'
    f'{_task_compatibility_markers(task)} '
    f'{text(task["title"], ("task", "title"))}'
    if task
    else 'Active task: -',
    f'Summary: {text(state["summary"], ("state", "summary"))}',
    f'Next action: {text(state["next_action"], ("state", "next_action"))}',
  ]
  if data['blockers']:
    lines.append(f'Open blockers{_handoff_page_suffix(data, "blockers")}:')
    for index, item in enumerate(data['blockers']):
      lines.append(
        f'- {item["id"]} [{item["target_kind"]} '
        f'{item["target_id"]}]: '
        f'{text(item["description"], ("blockers", index, "description"))}'
        '; '
        f'required: '
        f'{text(item["required"], ("blockers", index, "required"))}'
      )
  for key, label in (
    ('blocked_tasks', 'Blocked tasks'),
    ('blocked_goals', 'Blocked goals'),
  ):
    if not data[key]:
      continue
    lines.append(f'{label}{_handoff_page_suffix(data, key)}:')
    if key == 'blocked_tasks':
      for index, item in enumerate(data[key]):
        lines.append(
          f'- {item["id"]}{_task_compatibility_markers(item)} '
          f'{text(item["title"], (key, index, "title"))} '
          f'(stage: '
          f'{text(item["stage_name"], (key, index, "stage_name"))}; '
          f'goal: {item["goal_id"] or "-"})'
        )
    else:
      for index, item in enumerate(data[key]):
        lines.append(
          f'- {item["id"]}: {text(item["text"], (key, index, "text"))}; '
          f'reason: '
          f'{text(item["status_reason"], (key, index, "status_reason"))}'
        )
  if data['decisions']:
    lines.append(
      f'Relevant {data["focus"]["kind"]} decisions'
      + _handoff_page_suffix(data, 'decisions')
      + ':'
    )
    for index, item in enumerate(data['decisions']):
      lines.append(
        f'- {item["id"]}'
        f'{_record_compatibility_markers(item)}'
        f': {text(item["summary"], ("decisions", index, "summary"))}'
      )
  if data['evidence']:
    lines.append(
      f'Relevant {data["focus"]["kind"]} evidence'
      + _handoff_page_suffix(data, 'evidence')
      + ':'
    )
    for index, item in enumerate(data['evidence']):
      lines.append(
        f'- {item["id"]}'
        f'{_record_compatibility_markers(item)}'
        f': {text(item["claim"], ("evidence", index, "claim"))}'
      )
  if data['logs']:
    lines.append(
      'Recent task log' + _handoff_page_suffix(data, 'task_log') + ':'
    )
    for reverse_index, item in enumerate(reversed(data['logs'])):
      index = len(data['logs']) - reverse_index - 1
      lines.append(
        f'- {text(item["kind"], ("logs", index, "kind"))}: '
        f'{text(item["message"], ("logs", index, "message"))}'
      )
  projection: HandoffProjection = {
    'character_limit': HANDOFF_TEXT_LIMIT,
    'truncated_fields': truncations,
    'full_value_commands': sorted(commands),
  }
  if projection['truncated_fields']:
    lines.append(
      f'Text projection: {len(projection["truncated_fields"])} fields '
      f'truncated at {projection["character_limit"]} rendered characters.'
    )
    lines.extend(
      f'- Full values: {command}'
      for command in projection['full_value_commands']
    )
  return '\n'.join(lines), projection


def format_handoff(data: HandoffData) -> str:
  return _render_handoff(_handoff_view(data))[0]


def format_project_details(data: ProjectView) -> str:
  lines = ['Project:', *_format_fields(data['project'], 1)]
  lines.append(f'Database path: {_format_text(data["path"])}')
  lines.extend(['Project state:', *_format_fields(data['state'], 1)])
  if data['goal'] is None:
    lines.append('Active goal: -')
  else:
    lines.extend(_format_goal_details(data['goal'], 'Active goal'))
  lines.extend(
    _format_record_list('Previous charters', data['charter_history'])
  )
  return '\n'.join(lines)


def _format_task_details(data: TaskDetails, limit: int) -> str:
  lines = [
    'Task:',
    *_format_fields(data['task'], 1),
    *_format_record_list('Logs', data['logs']),
  ]
  notice = _format_limit_notice(len(data['logs']), limit)
  if notice:
    lines.append(f'Logs: {notice}')
  return '\n'.join(lines)


def _project_root(ctx: click.Context) -> ProjectRoot:
  return cast(ProjectRoot, ctx.obj['project_root'])


def _json_or_echo(value: object, as_json: bool) -> None:
  if as_json:
    click.echo(json.dumps(value, indent=2, sort_keys=True))
  else:
    click.echo(value)


def _invoke(
  function: Callable[P, R], *args: P.args, **kwargs: P.kwargs
) -> R:
  try:
    return function(*args, **kwargs)
  except (OSError, ProjectError, sqlite3.Error) as error:
    raise click.ClickException(str(error)) from error


@click.group(cls=lib.AliasedGroup)
@click.option(
  '--root', type=click.Path(file_okay=False, path_type=Path), hidden=True
)
@click.pass_context
def project_group(ctx: click.Context, root: Path | None) -> None:
  """Manage provisional SQLite project control planes."""
  ctx.ensure_object(dict)
  ctx.obj['project_root'] = root.resolve() if root else repository_root()


project_group.aliases = ['p']


@project_group.command('create')
@click.argument('name')
@click.option('--objective', required=True)
@click.option('--scope', default='')
@click.option('--non-goals', default='')
@click.option('--constraints', default='')
@click.option('--acceptance', default='')
@click.pass_context
def create_command(
  ctx: click.Context,
  name: str,
  objective: str,
  scope: str,
  non_goals: str,
  constraints: str,
  acceptance: str,
) -> None:
  """Create a project, archiving an existing same-name project."""
  path = _invoke(
    create_project,
    _project_root(ctx),
    name,
    objective,
    scope,
    non_goals,
    constraints,
    acceptance,
  )
  click.echo(path)


@project_group.command('list')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def list_command(ctx: click.Context, as_json: bool) -> None:
  """List unarchived project databases."""
  projects = _invoke(list_projects, _project_root(ctx))
  if as_json:
    _json_or_echo(projects, True)
    return
  click.echo(
    _format_table(
      ('Name', 'Status', 'Updated', 'Objective'),
      [
        (
          project['name'],
          project['status'],
          format_time(project['updated_at']),
          project['objective'],
        )
        for project in projects
      ],
    )
  )


@project_group.command('handoff')
@click.argument('name')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def handoff_command(ctx: click.Context, name: str, as_json: bool) -> None:
  """Produce a compact handoff for a new session."""
  data = _invoke(read_handoff, _project_root(ctx), name)
  if as_json:
    _json_or_echo(_handoff_json(data), True)
  else:
    click.echo(format_handoff(data))


@project_group.command('show')
@click.argument('name')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def show_command(ctx: click.Context, name: str, as_json: bool) -> None:
  """Read the project charter and compact state."""
  data = _invoke(read_project, _project_root(ctx), name)
  _json_or_echo(data, as_json) if as_json else click.echo(
    format_project_details(data)
  )


@project_group.command('update')
@click.argument('name')
@click.option('--objective')
@click.option('--scope')
@click.option('--non-goals')
@click.option('--constraints')
@click.option('--acceptance')
@click.option('--summary')
@click.option('--next-action')
@click.pass_context
def update_command(
  ctx: click.Context,
  name: str,
  objective: str | None,
  scope: str | None,
  non_goals: str | None,
  constraints: str | None,
  acceptance: str | None,
  summary: str | None,
  next_action: str | None,
) -> None:
  """Update charter or compact project state."""
  root = _project_root(ctx)
  _invoke(
    update_project_and_state,
    root,
    name,
    {
      'objective': objective if objective is not None else UNSET,
      'scope': scope if scope is not None else UNSET,
      'non_goals': non_goals if non_goals is not None else UNSET,
      'constraints_text': constraints
      if constraints is not None
      else UNSET,
      'acceptance': acceptance if acceptance is not None else UNSET,
    },
    {
      'summary': summary if summary is not None else UNSET,
      'next_action': next_action if next_action is not None else UNSET,
    },
  )


@project_group.command('archive')
@click.argument('name')
@click.pass_context
def archive_command(ctx: click.Context, name: str) -> None:
  """Move an unarchived project database into the archive."""
  click.echo(_invoke(archive_project, _project_root(ctx), name))


@project_group.group(cls=lib.AliasedGroup)
def goal() -> None:
  """Manage the project's durable goal."""


@goal.command('list')
@click.argument('name')
@click.option('--status', type=click.Choice(GOAL_STATUSES))
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def goal_list_command(
  ctx: click.Context, name: str, status: GoalStatus | None, as_json: bool
) -> None:
  goals = _invoke(read_goals, _project_root(ctx), name, status)
  if as_json:
    _json_or_echo(goals, True)
    return
  click.echo(
    _format_table(
      ('ID', 'Status', 'Stages', 'Text'),
      [
        (item['id'], item['status'], item['stage_names'], item['text'])
        for item in goals
      ],
    )
  )


@goal.command('create')
@click.argument('name')
@click.option('--text', required=True)
@click.option(
  '--stage',
  'stages',
  multiple=True,
  required=True,
  type=STAGE_REFERENCE,
  metavar='STAGE',
)
@click.pass_context
def goal_create_command(
  ctx: click.Context,
  name: str,
  text: str,
  stages: tuple[StageReference, ...],
) -> None:
  """Create and activate a goal, handing off active goal-linked work."""
  click.echo(_invoke(create_goal, _project_root(ctx), name, text, stages))


@goal.command('activate')
@click.argument('name')
@click.argument('goal_reference', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def goal_activate_command(
  ctx: click.Context, name: str, goal_reference: GoalReference
) -> None:
  """Activate a pending goal, handing off active goal-linked work."""
  _invoke(activate_goal, _project_root(ctx), name, goal_reference)


@goal.command('show')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def goal_show_command(
  ctx: click.Context, name: str, goal: GoalReference | None, as_json: bool
) -> None:
  data = _invoke(read_goal, _project_root(ctx), name, goal)
  _json_or_echo(data, True) if as_json else click.echo(
    '\n'.join(_format_goal_details(data))
  )


@goal.command('text')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.pass_context
def goal_text_command(
  ctx: click.Context, name: str, goal: GoalReference | None
) -> None:
  click.echo(
    _invoke(goal_text, _project_root(ctx), name, goal),
    nl=False,
    color=True,
  )


@goal.command('copy')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.pass_context
def goal_copy_command(
  ctx: click.Context, name: str, goal: GoalReference | None
) -> None:
  text = _invoke(goal_text, _project_root(ctx), name, goal)
  payload = base64.b64encode(text.encode('utf-8')).decode('ascii')
  click.echo(f'\x1b]52;c;{payload}\x07', nl=False)


@goal.command('achieve')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.pass_context
def goal_achieve_command(
  ctx: click.Context, name: str, goal: GoalReference | None
) -> None:
  _invoke(achieve_goal, _project_root(ctx), name, goal)


@goal.command('block')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', required=True)
@click.pass_context
def goal_block_command(
  ctx: click.Context,
  name: str,
  goal: GoalReference | None,
  description: str,
  impact: str,
  attempts: str,
  required: str,
) -> None:
  click.echo(
    _invoke(
      block_goal,
      _project_root(ctx),
      name,
      goal,
      description,
      impact,
      attempts,
      required,
    )
  )


@goal.command('reopen')
@click.argument('name')
@click.argument('goal_reference', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def goal_reopen_command(
  ctx: click.Context, name: str, goal_reference: GoalReference
) -> None:
  """Reopen a repaired goal, handing off active goal-linked work."""
  _invoke(reopen_goal, _project_root(ctx), name, goal_reference)


@goal.command('cancel')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.option('--reason', default='')
@click.pass_context
def goal_cancel_command(
  ctx: click.Context, name: str, goal: GoalReference | None, reason: str
) -> None:
  _invoke(
    cancel_goal,
    _project_root(ctx),
    name,
    goal,
    reason,
  )


@project_group.group(cls=lib.AliasedGroup)
def stage() -> None:
  """Manage project stages."""


@stage.command('list')
@click.argument('name')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def stage_list_command(
  ctx: click.Context, name: str, as_json: bool
) -> None:
  stages = _invoke(read_stages, _project_root(ctx), name)
  if as_json:
    _json_or_echo(stages, True)
    return
  click.echo(
    _format_table(
      ('ID', 'Status', 'Name', 'Outcome'),
      [
        (item['id'], item['status'], item['name'], item['outcome'])
        for item in stages
      ],
    )
  )


@stage.command('create')
@click.argument('name')
@click.argument('stage_name', metavar='STAGE_NAME')
@click.option('--outcome', required=True)
@click.option('--purpose', default='')
@click.option('--entry-conditions', default='')
@click.option('--exit-evidence', default='')
@click.pass_context
def stage_create_command(
  ctx: click.Context,
  name: str,
  stage_name: str,
  outcome: str,
  purpose: str,
  entry_conditions: str,
  exit_evidence: str,
) -> None:
  """Create a stage with an outcome contract."""
  click.echo(
    _invoke(
      add_stage,
      _project_root(ctx),
      name,
      stage_name,
      outcome,
      purpose,
      entry_conditions,
      exit_evidence,
    )
  )


@stage.command('update')
@click.argument('name')
@click.argument('stage_reference', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--stage-name')
@click.option('--outcome')
@click.option('--purpose')
@click.option('--entry-conditions')
@click.option('--exit-evidence')
@click.pass_context
def stage_update_command(
  ctx: click.Context,
  name: str,
  stage_reference: StageReference,
  stage_name: str | None,
  outcome: str | None,
  purpose: str | None,
  entry_conditions: str | None,
  exit_evidence: str | None,
) -> None:
  _invoke(
    update_stage,
    _project_root(ctx),
    name,
    stage_reference,
    name=stage_name if stage_name is not None else UNSET,
    outcome=outcome if outcome is not None else UNSET,
    purpose=purpose if purpose is not None else UNSET,
    entry_conditions=entry_conditions
    if entry_conditions is not None
    else UNSET,
    exit_evidence=exit_evidence if exit_evidence is not None else UNSET,
  )


@stage.command('achieve')
@click.argument('name')
@click.argument('stage_reference', type=STAGE_REFERENCE, metavar='STAGE')
@click.option(
  '--evidence',
  required=True,
  type=POSITIVE_INTEGER,
  metavar='EVIDENCE',
)
@click.pass_context
def stage_achieve_command(
  ctx: click.Context,
  name: str,
  stage_reference: StageReference,
  evidence: int,
) -> None:
  _invoke(
    achieve_stage,
    _project_root(ctx),
    name,
    stage_reference,
    evidence,
  )


@stage.command('add-dependency')
@click.argument('name')
@click.argument('stage_reference', type=STAGE_REFERENCE, metavar='STAGE')
@click.argument('dependency', type=STAGE_REFERENCE, metavar='DEPENDENCY')
@click.pass_context
def stage_add_dependency_command(
  ctx: click.Context,
  name: str,
  stage_reference: StageReference,
  dependency: StageReference,
) -> None:
  """Add a prerequisite edge to a stage."""
  _invoke(
    add_stage_dependency,
    _project_root(ctx),
    name,
    stage_reference,
    dependency,
  )


@stage.command('remove-dependency')
@click.argument('name')
@click.argument('stage_reference', type=STAGE_REFERENCE, metavar='STAGE')
@click.argument('dependency', type=STAGE_REFERENCE, metavar='DEPENDENCY')
@click.pass_context
def stage_remove_dependency_command(
  ctx: click.Context,
  name: str,
  stage_reference: StageReference,
  dependency: StageReference,
) -> None:
  """Remove one stage dependency when dependent work is inactive."""
  _invoke(
    remove_stage_dependency,
    _project_root(ctx),
    name,
    stage_reference,
    dependency,
  )


@project_group.group(cls=lib.AliasedGroup)
def task() -> None:
  """Manage project tasks."""


@task.command('list')
@click.argument('name')
@click.option('--status', type=click.Choice(TASK_STATUSES))
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--tag')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def task_list_command(
  ctx: click.Context,
  name: str,
  status: TaskStatus | None,
  stage: StageReference | None,
  tag: str | None,
  as_json: bool,
) -> None:
  tasks = _invoke(read_tasks, _project_root(ctx), name, status, stage, tag)
  if as_json:
    _json_or_echo(tasks, True)
    return
  click.echo(
    _format_table(
      ('ID', 'Status', 'Stage', 'Goal', 'Title', 'Tags'),
      [
        (
          f'{item["id"]}{_task_compatibility_markers(item)}',
          item['status'],
          item['stage_name'],
          item['goal_id'],
          item['title'],
          item['tags'],
        )
        for item in tasks
      ],
    )
  )


@task.command('ready')
@click.argument('name')
@click.option('--tag')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def task_ready_command(
  ctx: click.Context, name: str, tag: str | None, as_json: bool
) -> None:
  """List eligible pending tasks even when one task is active."""
  tasks = _invoke(
    read_tasks, _project_root(ctx), name, tag=tag, ready=True
  )
  if as_json:
    _json_or_echo(tasks, True)
    return
  click.echo(
    _format_table(
      ('ID', 'Stage', 'Title'),
      [
        (
          f'{item["id"]}{_task_compatibility_markers(item)}',
          item['stage_name'],
          item['title'],
        )
        for item in tasks
      ],
    )
  )


@task.command('create')
@click.argument('name')
@click.option('--title', required=True)
@click.option('--purpose', default='')
@click.option('--scope', default='')
@click.option('--exclusions', default='')
@click.option('--result', default='')
@click.option('--completion-evidence', default='')
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--priority', default=0, type=int, metavar='PRIORITY')
@click.option('--tag', multiple=True)
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def task_create_command(
  ctx: click.Context,
  name: str,
  title: str,
  purpose: str,
  scope: str,
  exclusions: str,
  result: str,
  completion_evidence: str,
  stage: StageReference | None,
  priority: int,
  tag: tuple[str, ...],
  goal: GoalReference | None,
) -> None:
  """Create a pending project task."""
  click.echo(
    _invoke(
      add_task,
      _project_root(ctx),
      name,
      title,
      purpose,
      stage,
      priority,
      tag,
      goal,
      scope,
      exclusions,
      result,
      completion_evidence,
    )
  )


@task.command('show')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.option(
  '--limit',
  default=20,
  type=POSITIVE_INTEGER,
  metavar='LIMIT',
  show_default=True,
  help='Maximum number of task logs to return.',
)
@click.option('--since', type=int, metavar='UNIX_TIMESTAMP')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def task_show_command(
  ctx: click.Context,
  name: str,
  task_reference: int,
  limit: int,
  since: int | None,
  as_json: bool,
) -> None:
  data = _invoke(
    read_task,
    _project_root(ctx),
    name,
    task_reference,
    limit,
    since,
  )
  _json_or_echo(data, True) if as_json else click.echo(
    _format_task_details(data, limit)
  )


@task.command('list-logs')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.option(
  '--limit',
  default=20,
  type=POSITIVE_INTEGER,
  metavar='LIMIT',
  show_default=True,
  help='Maximum number of task logs to return.',
)
@click.option('--since', type=int, metavar='UNIX_TIMESTAMP')
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def task_list_logs_command(
  ctx: click.Context,
  name: str,
  task_reference: int,
  limit: int,
  since: int | None,
  as_json: bool,
) -> None:
  """List a task's log entries."""
  data = _invoke(
    read_task,
    _project_root(ctx),
    name,
    task_reference,
    limit,
    since,
  )
  logs = data['logs']
  if as_json:
    _json_or_echo(logs, True)
    return
  click.echo(
    _format_limited_table(
      ('Time', 'Kind', 'Message'),
      [
        (
          format_time(entry['occurred_at']),
          entry['kind'],
          entry['message'],
        )
        for entry in logs
      ],
      limit,
    )
  )


@task.command('update')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--title')
@click.option('--purpose')
@click.option('--scope')
@click.option('--exclusions')
@click.option('--result')
@click.option('--completion-evidence')
@click.option('--priority', type=int, metavar='PRIORITY')
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.option('--no-goal', is_flag=True)
@click.pass_context
def task_update_command(
  ctx: click.Context,
  name: str,
  task_reference: int,
  title: str | None,
  purpose: str | None,
  scope: str | None,
  exclusions: str | None,
  result: str | None,
  completion_evidence: str | None,
  priority: int | None,
  stage: StageReference | None,
  goal: GoalReference | None,
  no_goal: bool,
) -> None:
  if goal is not None and no_goal:
    raise click.UsageError('--goal and --no-goal cannot be combined')
  _invoke(
    update_task,
    _project_root(ctx),
    name,
    task_reference,
    title=title if title is not None else UNSET,
    purpose=purpose if purpose is not None else UNSET,
    scope=scope if scope is not None else UNSET,
    exclusions=exclusions if exclusions is not None else UNSET,
    result=result if result is not None else UNSET,
    completion_evidence=completion_evidence
    if completion_evidence is not None
    else UNSET,
    priority=priority if priority is not None else UNSET,
    stage_id=stage if stage is not None else UNSET,
    goal_id=None if no_goal else goal if goal is not None else UNSET,
  )


@task.command('activate')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.pass_context
def task_activate_command(
  ctx: click.Context, name: str, task_reference: int
) -> None:
  """Activate an eligible task, returning any current task to pending."""
  _invoke(start_task, _project_root(ctx), name, task_reference)


@task.command('complete')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.pass_context
def task_complete_command(
  ctx: click.Context, name: str, task_reference: int
) -> None:
  _invoke(complete_task, _project_root(ctx), name, task_reference)


@task.command('reopen')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.pass_context
def task_reopen_command(
  ctx: click.Context, name: str, task_reference: int
) -> None:
  _invoke(reopen_task, _project_root(ctx), name, task_reference)


@task.command('cancel')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--reason', default='')
@click.pass_context
def task_cancel_command(
  ctx: click.Context, name: str, task_reference: int, reason: str
) -> None:
  _invoke(cancel_task, _project_root(ctx), name, task_reference, reason)


@task.command('add-log')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.argument('message')
@click.option('--kind', default='note')
@click.pass_context
def task_add_log_command(
  ctx: click.Context,
  name: str,
  task_reference: int,
  message: str,
  kind: str,
) -> None:
  """Append an entry to a task log."""
  _invoke(
    append_task_log,
    _project_root(ctx),
    name,
    task_reference,
    message,
    kind,
  )


@task.command('block')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', required=True)
@click.pass_context
def task_block_command(
  ctx: click.Context,
  name: str,
  task_reference: int,
  description: str,
  impact: str,
  attempts: str,
  required: str,
) -> None:
  click.echo(
    _invoke(
      block_task,
      _project_root(ctx),
      name,
      task_reference,
      description,
      impact,
      attempts,
      required,
    )
  )


@task.command('add-tag')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_add_tag_command(
  ctx: click.Context, name: str, task_reference: int, tags: tuple[str, ...]
) -> None:
  """Add metadata tags to a task."""
  _invoke(add_task_tags, _project_root(ctx), name, task_reference, tags)


@task.command('remove-tag')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_remove_tag_command(
  ctx: click.Context, name: str, task_reference: int, tags: tuple[str, ...]
) -> None:
  """Remove metadata tags from a task."""
  _invoke(remove_task_tags, _project_root(ctx), name, task_reference, tags)


@project_group.group(cls=lib.AliasedGroup)
def decision() -> None:
  """Manage project decisions."""


@decision.command('create')
@click.argument('name')
@click.option('--summary', required=True)
@click.option('--rationale', default='')
@click.option('--alternatives', default='')
@click.option('--consequences', default='')
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--task', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def decision_create_command(
  ctx: click.Context,
  name: str,
  summary: str,
  rationale: str,
  alternatives: str,
  consequences: str,
  stage: StageReference | None,
  task: int | None,
  goal: GoalReference | None,
) -> None:
  """Create a project decision record."""
  click.echo(
    _invoke(
      add_decision,
      _project_root(ctx),
      name,
      summary,
      rationale,
      alternatives,
      consequences,
      stage,
      task,
      goal,
    )
  )


@decision.command('list')
@click.argument('name')
@click.option(
  '--limit',
  default=20,
  type=POSITIVE_INTEGER,
  metavar='LIMIT',
  show_default=True,
  help='Maximum number of decisions to return.',
)
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--task', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.option('--no-task', is_flag=True)
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def decision_list_command(
  ctx: click.Context,
  name: str,
  limit: int,
  stage: StageReference | None,
  task: int | None,
  goal: GoalReference | None,
  no_task: bool,
  as_json: bool,
) -> None:
  decisions = _invoke(
    read_decisions,
    _project_root(ctx),
    name,
    limit,
    stage,
    task,
    goal,
    no_task,
  )
  if as_json:
    _json_or_echo(decisions, True)
    return
  click.echo(
    _format_limited_table(
      ('ID', 'Decided', 'Summary'),
      [
        (
          f'{item["id"]}{_record_compatibility_markers(item)}',
          format_time(item['decided_at']),
          item['summary'],
        )
        for item in decisions
      ],
      limit,
    )
  )


@project_group.group(cls=lib.AliasedGroup)
def blocker() -> None:
  """Manage project blockers."""


@blocker.command('create')
@click.argument('name')
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', required=True)
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--task', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def blocker_create_command(
  ctx: click.Context,
  name: str,
  description: str,
  impact: str,
  attempts: str,
  required: str,
  stage: StageReference | None,
  task: int | None,
  goal: GoalReference | None,
) -> None:
  """Create a blocker for a task or goal."""
  click.echo(
    _invoke(
      add_blocker,
      _project_root(ctx),
      name,
      description,
      impact,
      attempts,
      required,
      stage,
      task,
      goal,
    )
  )


@blocker.command('list')
@click.argument('name')
@click.option(
  '--status',
  type=click.Choice((*BLOCKER_STATUSES, 'all')),
  default='open',
  show_default=True,
  help='Filter by blocker status.',
)
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def blocker_list_command(
  ctx: click.Context,
  name: str,
  status: BlockerStatus | Literal['all'],
  as_json: bool,
) -> None:
  blockers = _invoke(read_blockers, _project_root(ctx), name, status)
  if as_json:
    _json_or_echo(blockers, True)
    return
  click.echo(
    f'Status filter: {status}\n'
    + _format_table(
      (
        'ID',
        'Status',
        'Target',
        'Stage',
        'Goal',
        'Description',
        'Impact',
        'Attempts',
        'Required',
      ),
      [
        (
          item['id'],
          item['status'],
          f'{item["target_kind"]} {item["target_id"]}',
          item['stage_id'],
          item['goal_id'],
          item['description'],
          item['impact'],
          item['attempts'],
          item['required'],
        )
        for item in blockers
      ],
    )
  )


@blocker.command('resolve')
@click.argument('name')
@click.argument(
  'blocker_reference', type=POSITIVE_INTEGER, metavar='BLOCKER'
)
@click.option('--resolution', required=True)
@click.pass_context
def blocker_resolve_command(
  ctx: click.Context, name: str, blocker_reference: int, resolution: str
) -> None:
  """Resolve a blocker, handing off work on final goal recovery."""
  _invoke(
    resolve_blocker,
    _project_root(ctx),
    name,
    blocker_reference,
    resolution,
  )


@project_group.group(cls=lib.AliasedGroup)
def evidence() -> None:
  """Manage project evidence."""


@evidence.command('create')
@click.argument('name')
@click.option('--claim', required=True)
@click.option('--source', default='')
@click.option('--result', default='')
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--task', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def evidence_create_command(
  ctx: click.Context,
  name: str,
  claim: str,
  source: str,
  result: str,
  stage: StageReference | None,
  task: int | None,
  goal: GoalReference | None,
) -> None:
  """Create a project evidence record."""
  click.echo(
    _invoke(
      add_evidence,
      _project_root(ctx),
      name,
      claim,
      source,
      result,
      stage,
      task,
      goal,
    )
  )


@evidence.command('list')
@click.argument('name')
@click.option(
  '--limit',
  default=20,
  type=POSITIVE_INTEGER,
  metavar='LIMIT',
  show_default=True,
  help='Maximum number of evidence records to return.',
)
@click.option('--stage', type=STAGE_REFERENCE, metavar='STAGE')
@click.option('--task', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--goal', type=GOAL_REFERENCE, metavar='GOAL')
@click.option('--no-task', is_flag=True)
@click.option(
  '--json',
  'as_json',
  is_flag=True,
  help='Output JSON instead of the human-readable view.',
)
@click.pass_context
def evidence_list_command(
  ctx: click.Context,
  name: str,
  limit: int,
  stage: StageReference | None,
  task: int | None,
  goal: GoalReference | None,
  no_task: bool,
  as_json: bool,
) -> None:
  entries = _invoke(
    read_evidence,
    _project_root(ctx),
    name,
    limit,
    stage,
    task,
    goal,
    no_task,
  )
  if as_json:
    _json_or_echo(entries, True)
    return
  click.echo(
    _format_limited_table(
      ('ID', 'Captured', 'Claim'),
      [
        (
          f'{item["id"]}{_record_compatibility_markers(item)}',
          format_time(item['captured_at']),
          item['claim'],
        )
        for item in entries
      ],
      limit,
    )
  )
