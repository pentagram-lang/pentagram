import base64
import json
import shlex
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import ParamSpec, TypeVar

import click

from .core import (
  BLOCKER_STATUSES,
  GOAL_STATUSES,
  HANDOFF_TEXT_LIMIT,
  TASK_STATUSES,
  UNSET,
  BlockerFilterStatus,
  CharterInput,
  FocusKind,
  GoalReference,
  GoalStatus,
  GoalText,
  PositiveInt,
  ProjectError,
  ProjectName,
  StageReference,
  SubstantiveText,
  TaskStatus,
  TaskTag,
  parse_goal_reference,
  parse_stage_reference,
)
from .render import (
  HandoffJson,
  HandoffRetrieval,
  HandoffView,
  TextHandoffView,
  build_handoff_json,
  format_blocker_list,
  format_decision_list,
  format_evidence_list,
  format_goal_details,
  format_goal_list,
  format_handoff,
  format_project_details,
  format_project_list,
  format_ready_task_list,
  format_stage_list,
  format_task_details,
  format_task_list,
  format_task_log_list,
)
from .service import (
  ActiveGoalRef,
  BlockerRecord,
  BoundedText,
  DecisionRecord,
  EvidenceRecord,
  GoalDetails,
  GoalListItem,
  GoalRecord,
  GoalStages,
  HandoffData,
  ProjectPatch,
  ProjectStatePatch,
  ProjectView,
  RecordListFilter,
  StageListItem,
  StagePatch,
  TaskDetails,
  TaskLogRecord,
  TaskPatch,
  TaskRecord,
  TextHandoffData,
  TextHandoffGoal,
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
  block_goal,
  block_task,
  cancel_goal,
  cancel_task,
  complete_task,
  create_goal,
  goal_text,
  read_blockers,
  read_decisions,
  read_evidence,
  read_goal,
  read_goals,
  read_handoff,
  read_project,
  read_stages,
  read_task,
  read_task_logs,
  read_tasks,
  read_text_handoff,
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
from .store import ProjectStore

__all__ = ['project_group']

P = ParamSpec('P')
R = TypeVar('R')


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
    if isinstance(value, str) or (
      isinstance(value, int) and not isinstance(value, bool)
    ):
      try:
        return parse_stage_reference(value)
      except ProjectError:
        pass
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
    if isinstance(value, str) or (
      isinstance(value, int) and not isinstance(value, bool)
    ):
      try:
        return parse_goal_reference(value)
      except ProjectError:
        pass
    self.fail(
      'Expected a positive goal ID or the active keyword.', param, ctx
    )


STAGE_REFERENCE = StageReferenceType()
GOAL_REFERENCE = GoalReferenceType()
POSITIVE_INTEGER = click.IntRange(min=1)


def _repository_root() -> Path:
  return Path(__file__).resolve().parent.parent


def _project_store(ctx: click.Context) -> ProjectStore:
  if isinstance(ctx.obj, ProjectStore):
    return ctx.obj
  if isinstance(ctx.obj, Path):
    ctx.obj = _invoke(ProjectStore.from_root, ctx.obj)
    return ctx.obj
  if ctx.obj is None:
    ctx.obj = _invoke(ProjectStore.from_root, _repository_root())
    return ctx.obj
  raise RuntimeError(
    f'Unsupported project store context: {type(ctx.obj).__name__}'
  )


def _invoke(
  function: Callable[P, R], *args: P.args, **kwargs: P.kwargs
) -> R:
  try:
    return function(*args, **kwargs)
  except ProjectError as error:
    raise click.ClickException(str(error)) from error


def _json_echo(value: object) -> None:
  click.echo(json.dumps(value, indent=2, sort_keys=True))


def _run_read(
  as_json: bool,
  load: Callable[[], R],
  to_json: Callable[[R], object],
  to_text: Callable[[R], str],
) -> None:
  if as_json:
    _json_echo(_invoke(lambda: to_json(load())))
  else:
    click.echo(_invoke(lambda: to_text(load())))


def _shell_quote(value: str | int) -> str:
  text = str(value)
  if any(not character.isprintable() for character in text):
    raise ProjectError(
      'Recovery command token contains non-printable characters'
    )
  if not text:
    return "''"
  single_quoted = shlex.quote(text)
  backslash_escaped = ''.join(
    ch
    if ch.isascii() and (ch.isalnum() or ch in '_@%+=:,./-')
    else f'\\{ch}'
    for ch in text
  )
  return (
    single_quoted
    if len(single_quoted) <= len(backslash_escaped)
    else backslash_escaped
  )


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


def _handoff_filter_options(
  focus_kind: FocusKind,
  focus_id: int,
  count: int,
) -> tuple[str | int, ...]:
  options: list[str | int] = [f'--{focus_kind}', focus_id]
  if focus_kind == 'goal':
    options.append('--no-task')
  options.extend(('--limit', max(count, 1), '--json'))
  return tuple(options)


def _handoff_project_name(name: str | BoundedText) -> str:
  if isinstance(name, BoundedText):
    if name.characters > HANDOFF_TEXT_LIMIT:
      raise ProjectError(
        'Generated project recovery command exceeds the handoff text limit'
      )
    return name.prefix
  return name


def _handoff_active_goal(
  data: HandoffData | TextHandoffData,
) -> GoalRecord | TextHandoffGoal | None:
  if data.goal is None:
    return None
  return (
    data.goal.goal if isinstance(data.goal, ActiveGoalRef) else data.goal
  )


def _handoff_retrieval_commands(
  data: HandoffData | TextHandoffData,
) -> HandoffRetrieval:
  name = _handoff_project_name(data.project.name)
  goal_ref = _handoff_active_goal(data)
  focus_kind = data.focus.kind
  focus_id = data.focus.id
  decision_count = data.pages.decisions.total
  evidence_count = data.pages.evidence.total
  log_count = data.pages.task_log.total
  return HandoffRetrieval(
    project=_project_command(('show',), name, options=('--json',)),
    goal=(
      _project_command(('goal', 'show'), name, (goal_ref.id,), ('--json',))
      if goal_ref is not None
      else None
    ),
    stage=(
      _project_command(('stage', 'list'), name, options=('--json',))
      if data.stage is not None
      else None
    ),
    task=(
      _project_command(
        ('task', 'show'), name, (data.task.id,), ('--json',)
      )
      if data.task is not None
      else None
    ),
    blocked_tasks=_project_command(
      ('task', 'list'),
      name,
      options=('--status', 'blocked', '--json'),
    ),
    blocked_goals=_project_command(
      ('goal', 'list'),
      name,
      options=('--status', 'blocked', '--json'),
    ),
    blockers=_project_command(
      ('blocker', 'list'), name, options=('--json',)
    ),
    ready_tasks=_project_command(('task', 'ready'), name),
    decisions=(
      _project_command(
        ('decision', 'list'),
        name,
        options=_handoff_filter_options(
          focus_kind, focus_id, decision_count
        ),
      )
      if focus_kind is not None and focus_id is not None
      else _project_command(
        ('decision', 'list'), name, options=('--json',)
      )
    ),
    evidence=(
      _project_command(
        ('evidence', 'list'),
        name,
        options=_handoff_filter_options(
          focus_kind, focus_id, evidence_count
        ),
      )
      if focus_kind is not None and focus_id is not None
      else _project_command(
        ('evidence', 'list'), name, options=('--json',)
      )
    ),
    task_log=(
      _project_command(
        ('task', 'list-logs'),
        name,
        (focus_id,),
        ('--limit', max(log_count, 1), '--json'),
      )
      if focus_kind == 'task' and focus_id is not None
      else None
    ),
  )


def _handoff_full_value_command(
  view: HandoffView | TextHandoffView,
  name: str | BoundedText,
  path: Sequence[str | int],
) -> str:
  project_name = _handoff_project_name(name)
  if not path or not isinstance(path[0], str):
    raise ValueError('Handoff retrieval path must start with a field name')
  root = path[0]
  if root in ('path', 'project', 'state'):
    return _project_command(
      ('handoff',), project_name, options=('--json',)
    )
  data = view.data
  if root == 'goal':
    goal_ref = _handoff_active_goal(data)
    if goal_ref is None:
      raise ValueError('There is no active goal to retrieve')
    return _project_command(
      ('goal', 'show'),
      project_name,
      (goal_ref.id,),
      ('--json',),
    )
  if root == 'stage':
    return _project_command(
      ('stage', 'list'), project_name, options=('--json',)
    )
  if root == 'task':
    if data.task is None:
      raise ValueError('There is no active task to retrieve')
    return _project_command(
      ('task', 'show'), project_name, (data.task.id,), ('--json',)
    )
  if root in ('blocked_tasks', 'blocked_goals'):
    if len(path) < 2 or not isinstance(path[1], int):
      raise ValueError(f'Handoff {root} retrieval needs a numeric index')
    index = path[1]
    if root == 'blocked_tasks':
      return _project_command(
        ('task', 'show'),
        project_name,
        (data.blocked_tasks[index].id,),
        ('--json',),
      )
    return _project_command(
      ('goal', 'show'),
      project_name,
      (data.blocked_goals[index].id,),
      ('--json',),
    )
  retrieval_map: dict[str, str | None] = {
    'blockers': view.retrieval.blockers,
    'decisions': view.retrieval.decisions,
    'evidence': view.retrieval.evidence,
    'logs': view.retrieval.task_log,
  }
  if root in retrieval_map:
    command = retrieval_map[root]
    if command is None:
      raise ValueError(f'No handoff retrieval command for {root}')
    return command
  raise ValueError(f'No handoff retrieval path for {root}')


def _handoff_view(data: HandoffData) -> HandoffView:
  return HandoffView(
    data=data, retrieval=_handoff_retrieval_commands(data)
  )


def _text_handoff_view(data: TextHandoffData) -> TextHandoffView:
  return TextHandoffView(
    data=data, retrieval=_handoff_retrieval_commands(data)
  )


def _handoff_json(view: HandoffView) -> HandoffJson:
  name = view.data.project.name
  return build_handoff_json(
    view, lambda path: _handoff_full_value_command(view, name, path)
  )


@click.group()
@click.option(
  '--root', type=click.Path(file_okay=False, path_type=Path), hidden=True
)
@click.pass_context
def project_group(ctx: click.Context, root: Path | None) -> None:
  """Manage provisional SQLite project control planes."""
  if root is not None:
    ctx.obj = root


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
  store = _project_store(ctx)

  def _run() -> Path:
    project_name = ProjectName.parse(name)
    charter = CharterInput.parse(
      objective, scope, non_goals, constraints, acceptance
    )
    return store.create_project(project_name, charter)

  click.echo(_invoke(_run))


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
  _run_read(
    as_json,
    _project_store(ctx).list_projects,
    lambda projects: [item.to_dict() for item in projects],
    format_project_list,
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
  store = _project_store(ctx)

  def _run() -> str:
    project_name = ProjectName.parse(name)
    handoff_path = store.handoff_database_path(project_name)
    with store.open_project(project_name) as connection:
      if as_json:
        json_data = read_handoff(connection, handoff_path)
        json_view = _handoff_view(json_data)
        return json.dumps(
          _handoff_json(json_view).to_dict(), indent=2, sort_keys=True
        )
      text_data = read_text_handoff(connection, handoff_path)
    text_view = _text_handoff_view(text_data)
    return format_handoff(
      text_view,
      lambda path: _handoff_full_value_command(
        text_view, text_data.project.name, path
      ),
    )

  click.echo(_invoke(_run))


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
  store = _project_store(ctx)

  def _load() -> ProjectView:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_project(connection, store.database_path(project_name))

  _run_read(
    as_json,
    _load,
    lambda view: view.to_dict(),
    format_project_details,
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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    project_patch = ProjectPatch(
      objective=objective if objective is not None else UNSET,
      scope=scope if scope is not None else UNSET,
      non_goals=non_goals if non_goals is not None else UNSET,
      constraints_text=constraints if constraints is not None else UNSET,
      acceptance=acceptance if acceptance is not None else UNSET,
    )
    state_patch = ProjectStatePatch(
      summary=summary if summary is not None else UNSET,
      next_action=next_action if next_action is not None else UNSET,
    )
    with store.open_project(project_name) as connection:
      update_project_and_state(connection, project_patch, state_patch)

  _invoke(_run)


@project_group.command('archive')
@click.argument('name')
@click.pass_context
def archive_command(ctx: click.Context, name: str) -> None:
  """Move an unarchived project database into the archive."""
  store = _project_store(ctx)

  def _run() -> Path:
    return store.archive_project(ProjectName.parse(name))

  click.echo(_invoke(_run))


@project_group.group()
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
  store = _project_store(ctx)

  def _load() -> tuple[GoalListItem, ...]:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_goals(connection, status)

  _run_read(
    as_json,
    _load,
    lambda goals: [item.to_dict() for item in goals],
    format_goal_list,
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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_text = GoalText.parse(text)
    parsed_stages = GoalStages.parse(stages)
    with store.open_project(project_name) as connection:
      return create_goal(connection, parsed_text, parsed_stages)

  click.echo(_invoke(_run))


@goal.command('activate')
@click.argument('name')
@click.argument('goal_reference', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def goal_activate_command(
  ctx: click.Context, name: str, goal_reference: GoalReference
) -> None:
  """Activate a pending goal, handing off active goal-linked work."""
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      activate_goal(connection, goal_reference)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _load() -> GoalDetails:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_goal(connection, goal)

  _run_read(
    as_json,
    _load,
    lambda details: details.to_dict(),
    format_goal_details,
  )


@goal.command('text')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.pass_context
def goal_text_command(
  ctx: click.Context, name: str, goal: GoalReference | None
) -> None:
  store = _project_store(ctx)

  def _run() -> str:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return goal_text(connection, goal)

  click.echo(_invoke(_run), nl=False, color=True)


@goal.command('copy')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.pass_context
def goal_copy_command(
  ctx: click.Context, name: str, goal: GoalReference | None
) -> None:
  store = _project_store(ctx)

  def _run() -> str:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return goal_text(connection, goal)

  text_value = _invoke(_run)
  payload = base64.b64encode(text_value.encode('utf-8')).decode('ascii')
  click.echo(f'\x1b]52;c;{payload}\x07', nl=False)


@goal.command('achieve')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.pass_context
def goal_achieve_command(
  ctx: click.Context, name: str, goal: GoalReference | None
) -> None:
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      achieve_goal(connection, goal)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_description = SubstantiveText.parse(
      description, 'Blocker description'
    )
    parsed_required = SubstantiveText.parse(
      required, 'Blocker requirement'
    )
    with store.open_project(project_name) as connection:
      return block_goal(
        connection,
        goal,
        parsed_description,
        required=parsed_required,
        impact=impact,
        attempts=attempts,
      )

  click.echo(_invoke(_run))


@goal.command('reopen')
@click.argument('name')
@click.argument('goal_reference', type=GOAL_REFERENCE, metavar='GOAL')
@click.pass_context
def goal_reopen_command(
  ctx: click.Context, name: str, goal_reference: GoalReference
) -> None:
  """Reopen a repaired goal, handing off active goal-linked work."""
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      reopen_goal(connection, goal_reference)

  _invoke(_run)


@goal.command('cancel')
@click.argument('name')
@click.argument('goal', required=False, type=GOAL_REFERENCE)
@click.option('--reason', default='')
@click.pass_context
def goal_cancel_command(
  ctx: click.Context, name: str, goal: GoalReference | None, reason: str
) -> None:
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      cancel_goal(connection, goal, reason=reason)

  _invoke(_run)


@project_group.group()
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
  store = _project_store(ctx)

  def _load() -> tuple[StageListItem, ...]:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_stages(connection)

  _run_read(
    as_json,
    _load,
    lambda stages: [item.to_dict() for item in stages],
    format_stage_list,
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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_name = SubstantiveText.parse(stage_name, 'Stage name')
    parsed_outcome = SubstantiveText.parse(outcome, 'Stage outcome')
    with store.open_project(project_name) as connection:
      return add_stage(
        connection,
        parsed_name,
        parsed_outcome,
        purpose=purpose,
        entry_conditions=entry_conditions,
        exit_evidence=exit_evidence,
      )

  click.echo(_invoke(_run))


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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    patch = StagePatch.parse(
      name=stage_name if stage_name is not None else UNSET,
      outcome=outcome if outcome is not None else UNSET,
      purpose=purpose if purpose is not None else UNSET,
      entry_conditions=entry_conditions
      if entry_conditions is not None
      else UNSET,
      exit_evidence=exit_evidence if exit_evidence is not None else UNSET,
    )
    with store.open_project(project_name) as connection:
      update_stage(connection, stage_reference, patch)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_evidence = PositiveInt.parse(evidence, 'Evidence ID')
    with store.open_project(project_name) as connection:
      achieve_stage(connection, stage_reference, parsed_evidence)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      add_stage_dependency(connection, stage_reference, dependency)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      remove_stage_dependency(connection, stage_reference, dependency)

  _invoke(_run)


@project_group.group()
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
  store = _project_store(ctx)

  def _load() -> tuple[TaskRecord, ...]:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_tasks(connection, status=status, stage=stage, tag=tag)

  _run_read(
    as_json,
    _load,
    lambda tasks: [item.to_dict() for item in tasks],
    format_task_list,
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
  store = _project_store(ctx)

  def _load() -> tuple[TaskRecord, ...]:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_tasks(connection, tag=tag, ready=True)

  _run_read(
    as_json,
    _load,
    lambda tasks: [item.to_dict() for item in tasks],
    format_ready_task_list,
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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_title = SubstantiveText.parse(title, 'Task title')
    parsed_tags = tuple(TaskTag.parse(item) for item in tag)
    with store.open_project(project_name) as connection:
      return add_task(
        connection,
        parsed_title,
        purpose=purpose,
        stage=stage,
        priority=priority,
        tags=parsed_tags,
        goal=goal,
        scope=scope,
        exclusions=exclusions,
        result=result,
        completion_evidence=completion_evidence,
      )

  click.echo(_invoke(_run))


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
  store = _project_store(ctx)

  def _load() -> tuple[TaskDetails, int]:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    parsed_limit = PositiveInt.parse(limit, 'Task log limits')
    with store.open_project(project_name) as connection:
      return (
        read_task(
          connection, parsed_task, limit=parsed_limit, since=since
        ),
        parsed_limit.value,
      )

  _run_read(
    as_json,
    _load,
    lambda pair: pair[0].to_dict(),
    lambda pair: format_task_details(pair[0], pair[1]),
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
  store = _project_store(ctx)

  def _load() -> tuple[tuple[TaskLogRecord, ...], int]:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    parsed_limit = PositiveInt.parse(limit, 'Task log limits')
    with store.open_project(project_name) as connection:
      return (
        read_task_logs(
          connection, parsed_task, limit=parsed_limit, since=since
        ),
        parsed_limit.value,
      )

  _run_read(
    as_json,
    _load,
    lambda pair: [entry.to_dict() for entry in pair[0]],
    lambda pair: format_task_log_list(pair[0], pair[1]),
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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    patch = TaskPatch.parse(
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
    with store.open_project(project_name) as connection:
      update_task(connection, parsed_task, patch)

  _invoke(_run)


@task.command('activate')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.pass_context
def task_activate_command(
  ctx: click.Context, name: str, task_reference: int
) -> None:
  """Activate an eligible task, returning any current task to pending."""
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    with store.open_project(project_name) as connection:
      start_task(connection, parsed_task)

  _invoke(_run)


@task.command('complete')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.pass_context
def task_complete_command(
  ctx: click.Context, name: str, task_reference: int
) -> None:
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    with store.open_project(project_name) as connection:
      complete_task(connection, parsed_task)

  _invoke(_run)


@task.command('reopen')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.pass_context
def task_reopen_command(
  ctx: click.Context, name: str, task_reference: int
) -> None:
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    with store.open_project(project_name) as connection:
      reopen_task(connection, parsed_task)

  _invoke(_run)


@task.command('cancel')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.option('--reason', default='')
@click.pass_context
def task_cancel_command(
  ctx: click.Context, name: str, task_reference: int, reason: str
) -> None:
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    with store.open_project(project_name) as connection:
      cancel_task(connection, parsed_task, reason=reason)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    with store.open_project(project_name) as connection:
      append_task_log(connection, parsed_task, message, kind=kind)

  _invoke(_run)


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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    parsed_description = SubstantiveText.parse(
      description, 'Blocker description'
    )
    parsed_required = SubstantiveText.parse(
      required, 'Blocker requirement'
    )
    with store.open_project(project_name) as connection:
      return block_task(
        connection,
        parsed_task,
        parsed_description,
        required=parsed_required,
        impact=impact,
        attempts=attempts,
      )

  click.echo(_invoke(_run))


@task.command('add-tag')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_add_tag_command(
  ctx: click.Context, name: str, task_reference: int, tags: tuple[str, ...]
) -> None:
  """Add metadata tags to a task."""
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    parsed_tags = tuple(TaskTag.parse(item) for item in tags)
    with store.open_project(project_name) as connection:
      add_task_tags(connection, parsed_task, parsed_tags)

  _invoke(_run)


@task.command('remove-tag')
@click.argument('name')
@click.argument('task_reference', type=POSITIVE_INTEGER, metavar='TASK')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_remove_tag_command(
  ctx: click.Context, name: str, task_reference: int, tags: tuple[str, ...]
) -> None:
  """Remove metadata tags from a task."""
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_task = PositiveInt.parse(task_reference, 'Task ID')
    parsed_tags = tuple(TaskTag.parse(item) for item in tags)
    with store.open_project(project_name) as connection:
      remove_task_tags(connection, parsed_task, parsed_tags)

  _invoke(_run)


@project_group.group()
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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_summary = SubstantiveText.parse(summary, 'Decision summary')
    parsed_task = (
      PositiveInt.parse(task, 'Task ID') if task is not None else None
    )
    with store.open_project(project_name) as connection:
      return add_decision(
        connection,
        parsed_summary,
        rationale=rationale,
        alternatives=alternatives,
        consequences=consequences,
        stage=stage,
        task=parsed_task,
        goal=goal,
      )

  click.echo(_invoke(_run))


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
  store = _project_store(ctx)

  def _load() -> tuple[tuple[DecisionRecord, ...], int]:
    project_name = ProjectName.parse(name)
    filters = RecordListFilter.parse(
      'Decision',
      limit=limit,
      stage=stage,
      task=task,
      goal=goal,
      no_task=no_task,
    )
    with store.open_project(project_name) as connection:
      return read_decisions(connection, filters), filters.limit.value

  _run_read(
    as_json,
    _load,
    lambda pair: [item.to_dict() for item in pair[0]],
    lambda pair: format_decision_list(pair[0], pair[1]),
  )


@project_group.group()
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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_description = SubstantiveText.parse(
      description, 'Blocker description'
    )
    parsed_required = SubstantiveText.parse(
      required, 'Blocker requirement'
    )
    parsed_task = (
      PositiveInt.parse(task, 'Task ID') if task is not None else None
    )
    if parsed_task is None and goal is None:
      raise ProjectError('A blocker must target a task or goal')
    with store.open_project(project_name) as connection:
      return add_blocker(
        connection,
        parsed_description,
        required=parsed_required,
        impact=impact,
        attempts=attempts,
        stage=stage,
        task=parsed_task,
        goal=goal,
      )

  click.echo(_invoke(_run))


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
  status: BlockerFilterStatus,
  as_json: bool,
) -> None:
  store = _project_store(ctx)

  def _load() -> tuple[BlockerRecord, ...]:
    project_name = ProjectName.parse(name)
    with store.open_project(project_name) as connection:
      return read_blockers(connection, status)

  _run_read(
    as_json,
    _load,
    lambda blockers: [item.to_dict() for item in blockers],
    lambda blockers: format_blocker_list(blockers, status),
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
  store = _project_store(ctx)

  def _run() -> None:
    project_name = ProjectName.parse(name)
    parsed_blocker = PositiveInt.parse(blocker_reference, 'Blocker ID')
    parsed_resolution = SubstantiveText.parse(
      resolution, 'Blocker resolution'
    )
    with store.open_project(project_name) as connection:
      resolve_blocker(connection, parsed_blocker, parsed_resolution)

  _invoke(_run)


@project_group.group()
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
  store = _project_store(ctx)

  def _run() -> int:
    project_name = ProjectName.parse(name)
    parsed_claim = SubstantiveText.parse(claim, 'Evidence claim')
    parsed_task = (
      PositiveInt.parse(task, 'Task ID') if task is not None else None
    )
    with store.open_project(project_name) as connection:
      return add_evidence(
        connection,
        parsed_claim,
        source=source,
        result=result,
        stage=stage,
        task=parsed_task,
        goal=goal,
      )

  click.echo(_invoke(_run))


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
  store = _project_store(ctx)

  def _load() -> tuple[tuple[EvidenceRecord, ...], int]:
    project_name = ProjectName.parse(name)
    filters = RecordListFilter.parse(
      'Evidence',
      limit=limit,
      stage=stage,
      task=task,
      goal=goal,
      no_task=no_task,
    )
    with store.open_project(project_name) as connection:
      return read_evidence(connection, filters), filters.limit.value

  _run_read(
    as_json,
    _load,
    lambda pair: [item.to_dict() for item in pair[0]],
    lambda pair: format_evidence_list(pair[0], pair[1]),
  )
