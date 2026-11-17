import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal

from wcwidth import wcswidth

from .core import (
  HANDOFF_TEXT_LIMIT,
  BlockerFilterStatus,
  ClaimStatus,
  ProjectError,
  RecordContextStatus,
  TitleStatus,
  dataclass_to_dict,
)
from .service import (
  ActiveGoalRef,
  BlockerRecord,
  BoundedText,
  CharterHistoryRecord,
  DecisionRecord,
  EvidenceRecord,
  GoalDetails,
  GoalListItem,
  GoalRecord,
  GoalStageSummary,
  GoalTaskRecord,
  HandoffData,
  HandoffPage,
  ProjectRecord,
  ProjectState,
  ProjectSummary,
  ProjectView,
  StageListItem,
  TaskDetails,
  TaskLogRecord,
  TaskRecord,
  TextHandoffData,
  TextHandoffGoal,
)

__all__ = [
  'HandoffJson',
  'HandoffProjection',
  'HandoffRetrieval',
  'HandoffView',
  'TextHandoffView',
  'TruncatedField',
  'build_handoff_json',
  'format_blocker_list',
  'format_decision_list',
  'format_evidence_list',
  'format_goal_details',
  'format_goal_list',
  'format_handoff',
  'format_project_details',
  'format_project_list',
  'format_ready_task_list',
  'format_stage_list',
  'format_task_details',
  'format_task_list',
  'format_task_log_list',
]

_TEXT_ESCAPES: Final[dict[int, str]] = {
  **{codepoint: f'\\u{codepoint:04x}' for codepoint in range(0x7F, 0xA0)},
  0x2028: '\\u2028',
  0x2029: '\\u2029',
}

type _HandoffPageKey = Literal[
  'blocked_tasks',
  'blocked_goals',
  'blockers',
  'decisions',
  'evidence',
  'task_log',
]


@dataclass(frozen=True, slots=True)
class TruncatedField:
  path: str
  characters: int
  retrieval: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffProjection:
  character_limit: int
  truncated_fields: tuple[TruncatedField, ...]
  full_value_commands: tuple[str, ...]

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffRetrieval:
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

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffView:
  data: HandoffData
  retrieval: HandoffRetrieval

  def to_dict(self) -> dict[str, object]:
    return {**self.data.to_dict(), 'retrieval': self.retrieval.to_dict()}


@dataclass(frozen=True, slots=True)
class TextHandoffView:
  data: TextHandoffData
  retrieval: HandoffRetrieval


@dataclass(frozen=True, slots=True)
class HandoffJson:
  view: HandoffView
  text_projection: HandoffProjection

  def to_dict(self) -> dict[str, object]:
    return {
      **self.view.to_dict(),
      'text_projection': self.text_projection.to_dict(),
    }


def _format_time(value: int | None) -> str:
  if value is None:
    return '-'
  return datetime.fromtimestamp(value, UTC).isoformat()


def _escape_text(value: object) -> str:
  return json.dumps(str(value), ensure_ascii=False)[1:-1].translate(
    _TEXT_ESCAPES
  )


def _format_text(value: object, default: str = '-') -> str:
  if value is None or value == '':
    return default
  rendered = _escape_text(value)
  return f'"{rendered}"' if rendered == default else rendered


def _display_width(value: str) -> int:
  width = wcswidth(value)
  return width if width >= 0 else len(value)


def _bounded_escaped_prefix(
  prefix: str, total_chars: int, limit: int
) -> tuple[str, bool]:
  if limit < 1:
    raise ValueError('limit must be at least 1')
  if total_chars == 1 and prefix == '-':
    return ('"-"', False) if limit >= 3 else ('…', True)
  rendered: list[str] = []
  rendered_length = 0
  for character in prefix:
    encoded = _escape_text(character)
    if rendered_length + len(encoded) > limit:
      while rendered and rendered_length + 1 > limit:
        rendered_length -= len(rendered.pop())
      return ''.join(rendered) + '…', True
    rendered.append(encoded)
    rendered_length += len(encoded)
  return ''.join(rendered), False


def _format_table(
  headers: Sequence[str], rows: Sequence[Sequence[object]]
) -> str:
  if isinstance(headers, str) or any(
    len(row) != len(headers) for row in rows
  ):
    raise ValueError('Table row width must match headers')
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


def _format_pairs(
  pairs: Sequence[tuple[str, str]], indent: int = 0
) -> list[str]:
  prefix = '  ' * indent
  return [f'{prefix}{label}: {value}' for label, value in pairs]


def _format_typed_record_list(
  label: str,
  records: Sequence[Sequence[tuple[str, str]]],
  indent: int = 0,
) -> list[str]:
  prefix = '  ' * indent
  item_label = label[:-1] if label.endswith('s') else label
  lines = [f'{prefix}{label} ({len(records)}):']
  for index, pairs in enumerate(records, 1):
    lines.append(f'{prefix}  {item_label} {index}:')
    lines.extend(_format_pairs(pairs, indent + 2))
  return lines


def _project_pairs(project: ProjectRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(project.id)),
    ('Name', _format_text(project.name)),
    ('Objective', _format_text(project.objective)),
    ('Scope', _format_text(project.scope)),
    ('Non-goals', _format_text(project.non_goals)),
    ('Constraints', _format_text(project.constraints_text)),
    ('Acceptance', _format_text(project.acceptance)),
    ('Created At', _format_time(project.created_at)),
    ('Updated At', _format_time(project.updated_at)),
    (
      'Charter Context Status',
      _format_text(project.charter_context_status),
    ),
    ('Status', _format_text(project.status)),
    ('Completed At', _format_time(project.completed_at)),
  )


def _state_pairs(state: ProjectState) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(state.id)),
    ('Summary', _format_text(state.summary)),
    ('Next Action', _format_text(state.next_action)),
    ('Updated At', _format_time(state.updated_at)),
    ('Revision', _format_text(state.revision)),
  )


def _charter_history_pairs(
  item: CharterHistoryRecord,
) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(item.id)),
    ('Objective', _format_text(item.objective)),
    ('Scope', _format_text(item.scope)),
    ('Non-goals', _format_text(item.non_goals)),
    ('Constraints', _format_text(item.constraints_text)),
    ('Acceptance', _format_text(item.acceptance)),
    ('Replaced At', _format_time(item.replaced_at)),
  )


def _goal_pairs(goal: GoalRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(goal.id)),
    ('Text', _format_text(goal.text)),
    ('Status', _format_text(goal.status)),
    ('Status Reason', _format_text(goal.status_reason)),
    ('Ever Activated', _format_text(goal.ever_activated)),
    ('Created At', _format_time(goal.created_at)),
    ('Started At', _format_time(goal.started_at)),
    ('Achieved At', _format_time(goal.achieved_at)),
    ('Updated At', _format_time(goal.updated_at)),
  )


def _goal_stage_pairs(
  stage: GoalStageSummary,
) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(stage.id)),
    ('Name', _format_text(stage.name)),
    ('Status', _format_text(stage.status)),
    ('Outcome', _format_text(stage.outcome)),
  )


def _goal_task_pairs(task: GoalTaskRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(task.id)),
    ('Goal ID', _format_text(task.goal_id)),
    ('Stage ID', _format_text(task.stage_id)),
    ('Title', _format_text(task.title)),
    ('Purpose', _format_text(task.purpose)),
    ('Scope', _format_text(task.scope)),
    ('Exclusions', _format_text(task.exclusions)),
    ('Result', _format_text(task.result)),
    ('Completion Evidence', _format_text(task.completion_evidence)),
    ('Status', _format_text(task.status)),
    ('Priority', _format_text(task.priority)),
    ('Created At', _format_time(task.created_at)),
    ('Started At', _format_time(task.started_at)),
    ('Completed At', _format_time(task.completed_at)),
    ('Updated At', _format_time(task.updated_at)),
    ('Stage Name', _format_text(task.stage_name)),
    ('Title Status', _format_text(task.title_status)),
  )


def _blocker_pairs(item: BlockerRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(item.id)),
    ('Goal ID', _format_text(item.goal_id)),
    ('Stage ID', _format_text(item.stage_id)),
    ('Task ID', _format_text(item.task_id)),
    ('Description', _format_text(item.description)),
    ('Impact', _format_text(item.impact)),
    ('Attempts', _format_text(item.attempts)),
    ('Required', _format_text(item.required)),
    ('Status', _format_text(item.status)),
    ('Opened At', _format_time(item.opened_at)),
    ('Resolved At', _format_time(item.resolved_at)),
    ('Resolution', _format_text(item.resolution)),
    ('Target Kind', _format_text(item.target_kind)),
    ('Target ID', _format_text(item.target_id)),
  )


def _evidence_pairs(item: EvidenceRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(item.id)),
    ('Goal ID', _format_text(item.goal_id)),
    ('Stage ID', _format_text(item.stage_id)),
    ('Task ID', _format_text(item.task_id)),
    ('Claim', _format_text(item.claim)),
    ('Source', _format_text(item.source)),
    ('Result', _format_text(item.result)),
    ('Captured At', _format_time(item.captured_at)),
    ('Context Status', _format_text(item.context_status)),
    ('Claim Status', _format_text(item.claim_status)),
    ('Stage Generation', _format_text(item.stage_generation)),
  )


def _decision_pairs(item: DecisionRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(item.id)),
    ('Goal ID', _format_text(item.goal_id)),
    ('Stage ID', _format_text(item.stage_id)),
    ('Task ID', _format_text(item.task_id)),
    ('Summary', _format_text(item.summary)),
    ('Rationale', _format_text(item.rationale)),
    ('Alternatives', _format_text(item.alternatives)),
    ('Consequences', _format_text(item.consequences)),
    ('Decided At', _format_time(item.decided_at)),
    ('Context Status', _format_text(item.context_status)),
  )


def _task_pairs(task: TaskRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(task.id)),
    ('Goal ID', _format_text(task.goal_id)),
    ('Stage ID', _format_text(task.stage_id)),
    ('Title', _format_text(task.title)),
    ('Purpose', _format_text(task.purpose)),
    ('Scope', _format_text(task.scope)),
    ('Exclusions', _format_text(task.exclusions)),
    ('Result', _format_text(task.result)),
    ('Completion Evidence', _format_text(task.completion_evidence)),
    ('Status', _format_text(task.status)),
    ('Priority', _format_text(task.priority)),
    ('Created At', _format_time(task.created_at)),
    ('Started At', _format_time(task.started_at)),
    ('Completed At', _format_time(task.completed_at)),
    ('Updated At', _format_time(task.updated_at)),
    ('Stage Name', _format_text(task.stage_name)),
    ('Tags', _format_text(task.tags)),
    ('Title Status', _format_text(task.title_status)),
  )


def _task_log_pairs(entry: TaskLogRecord) -> tuple[tuple[str, str], ...]:
  return (
    ('ID', _format_text(entry.id)),
    ('Task ID', _format_text(entry.task_id)),
    ('Occurred At', _format_time(entry.occurred_at)),
    ('Kind', _format_text(entry.kind)),
    ('Message', _format_text(entry.message)),
  )


def _goal_detail_lines(
  data: GoalDetails, label: str = 'Goal', indent: int = 0
) -> list[str]:
  prefix = '  ' * indent
  return [
    f'{prefix}{label}:',
    *_format_pairs(_goal_pairs(data.goal), indent + 1),
    *_format_typed_record_list(
      'Stages',
      [_goal_stage_pairs(item) for item in data.stages],
      indent + 1,
    ),
    *_format_typed_record_list(
      'Tasks', [_goal_task_pairs(item) for item in data.tasks], indent + 1
    ),
    *_format_typed_record_list(
      'Blockers',
      [_blocker_pairs(item) for item in data.blockers],
      indent + 1,
    ),
    *_format_typed_record_list(
      'Evidence',
      [_evidence_pairs(item) for item in data.evidence],
      indent + 1,
    ),
    *_format_typed_record_list(
      'Decisions',
      [_decision_pairs(item) for item in data.decisions],
      indent + 1,
    ),
  ]


def format_goal_details(
  data: GoalDetails, label: str = 'Goal', indent: int = 0
) -> str:
  return '\n'.join(_goal_detail_lines(data, label, indent))


def format_project_details(data: ProjectView) -> str:
  lines = [
    'Project:',
    *_format_pairs(_project_pairs(data.project), 1),
    f'Database path: {_format_text(data.path)}',
    'Project state:',
    *_format_pairs(_state_pairs(data.state), 1),
  ]
  if data.goal is None:
    lines.append('Active goal: -')
  else:
    lines.extend(_goal_detail_lines(data.goal, 'Active goal'))
  lines.extend(
    _format_typed_record_list(
      'Previous charters',
      [_charter_history_pairs(item) for item in data.charter_history],
    )
  )
  return '\n'.join(lines)


def format_task_details(data: TaskDetails, limit: int) -> str:
  lines = [
    'Task:',
    *_format_pairs(_task_pairs(data.task), 1),
    *_format_typed_record_list(
      'Logs', [_task_log_pairs(entry) for entry in data.logs]
    ),
  ]
  notice = _format_limit_notice(len(data.logs), limit)
  if notice:
    lines.append(f'Logs: {notice}')
  return '\n'.join(lines)


def _record_compatibility_markers(
  context_status: RecordContextStatus,
  claim_status: ClaimStatus | None = None,
) -> str:
  markers: list[str] = []
  if context_status != 'complete':
    markers.append('legacy unresolved context')
  if claim_status is not None and claim_status != 'substantive':
    markers.append('legacy blank claim')
  return ''.join(f' [{marker}]' for marker in markers)


def _task_compatibility_markers(title_status: TitleStatus) -> str:
  if title_status == 'legacy-blank':
    return ' [legacy blank title]'
  return ''


def format_project_list(projects: Sequence[ProjectSummary]) -> str:
  return _format_table(
    ('Name', 'Status', 'Updated', 'Objective'),
    [
      (
        project.name,
        project.status,
        _format_time(project.updated_at),
        project.objective,
      )
      for project in projects
    ],
  )


def format_goal_list(goals: Sequence[GoalListItem]) -> str:
  return _format_table(
    ('ID', 'Status', 'Stages', 'Text'),
    [
      (item.id, item.status, item.stage_names, item.text) for item in goals
    ],
  )


def format_stage_list(stages: Sequence[StageListItem]) -> str:
  return _format_table(
    ('ID', 'Status', 'Name', 'Outcome'),
    [(item.id, item.status, item.name, item.outcome) for item in stages],
  )


def format_task_list(tasks: Sequence[TaskRecord]) -> str:
  return _format_table(
    ('ID', 'Status', 'Stage', 'Goal', 'Title', 'Tags'),
    [
      (
        f'{item.id}{_task_compatibility_markers(item.title_status)}',
        item.status,
        item.stage_name,
        item.goal_id,
        item.title,
        item.tags,
      )
      for item in tasks
    ],
  )


def format_ready_task_list(tasks: Sequence[TaskRecord]) -> str:
  return _format_table(
    ('ID', 'Stage', 'Title'),
    [
      (
        f'{item.id}{_task_compatibility_markers(item.title_status)}',
        item.stage_name,
        item.title,
      )
      for item in tasks
    ],
  )


def format_task_log_list(logs: Sequence[TaskLogRecord], limit: int) -> str:
  return _format_limited_table(
    ('Time', 'Kind', 'Message'),
    [
      (_format_time(entry.occurred_at), entry.kind, entry.message)
      for entry in logs
    ],
    limit,
  )


def format_decision_list(
  decisions: Sequence[DecisionRecord], limit: int
) -> str:
  return _format_limited_table(
    ('ID', 'Decided', 'Summary'),
    [
      (
        f'{item.id}{_record_compatibility_markers(item.context_status)}',
        _format_time(item.decided_at),
        item.summary,
      )
      for item in decisions
    ],
    limit,
  )


def format_blocker_list(
  blockers: Sequence[BlockerRecord], status: BlockerFilterStatus
) -> str:
  return f'Status filter: {status}\n' + _format_table(
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
        item.id,
        item.status,
        f'{item.target_kind} {item.target_id}',
        item.stage_id,
        item.goal_id,
        item.description,
        item.impact,
        item.attempts,
        item.required,
      )
      for item in blockers
    ],
  )


def format_evidence_list(
  entries: Sequence[EvidenceRecord], limit: int
) -> str:
  return _format_limited_table(
    ('ID', 'Captured', 'Claim'),
    [
      (
        f'{item.id}'
        f'{
          _record_compatibility_markers(
            item.context_status, item.claim_status
          )
        }',
        _format_time(item.captured_at),
        item.claim,
      )
      for item in entries
    ],
    limit,
  )


def _handoff_page_and_command(
  view: HandoffView | TextHandoffView, key: _HandoffPageKey
) -> tuple[HandoffPage, str | None]:
  match key:
    case 'blocked_tasks':
      return view.data.pages.blocked_tasks, view.retrieval.blocked_tasks
    case 'blocked_goals':
      return view.data.pages.blocked_goals, view.retrieval.blocked_goals
    case 'blockers':
      return view.data.pages.blockers, view.retrieval.blockers
    case 'decisions':
      return view.data.pages.decisions, view.retrieval.decisions
    case 'evidence':
      return view.data.pages.evidence, view.retrieval.evidence
    case 'task_log':
      return view.data.pages.task_log, view.retrieval.task_log


def _handoff_page_suffix(
  view: HandoffView | TextHandoffView, key: _HandoffPageKey
) -> str:
  page, command = _handoff_page_and_command(view, key)
  parts = [f'{page.shown} of {page.total}']
  if page.truncated:
    if command is None:
      raise ProjectError(f'No handoff retrieval command for {key}')
    parts.append(f'more: {command}')
  return f' ({"; ".join(parts)})'


def _render_handoff(
  view: HandoffView | TextHandoffView,
  full_value_command: Callable[[tuple[str | int, ...]], str],
) -> tuple[str, HandoffProjection]:
  data = view.data
  project = data.project
  state = data.state
  stage = data.stage
  task = data.task
  raw_goal = data.goal
  goal_record: GoalRecord | TextHandoffGoal | None = (
    raw_goal.goal if isinstance(raw_goal, ActiveGoalRef) else raw_goal
  )
  truncations: list[TruncatedField] = []
  commands: set[str] = set()

  def text(
    value: object, path: tuple[str | int, ...], default: str = '-'
  ) -> str:
    if value is None:
      return default
    if isinstance(value, BoundedText):
      prefix = value.prefix
      total_chars = value.characters
    else:
      prefix = str(value)
      total_chars = len(prefix)
    if total_chars == 0:
      return default
    rendered, truncated = _bounded_escaped_prefix(
      prefix, total_chars, HANDOFF_TEXT_LIMIT
    )
    if not truncated:
      return rendered
    command = full_value_command(path)
    commands.add(command)
    truncations.append(
      TruncatedField(
        path='.'.join(str(part) for part in path),
        characters=total_chars,
        retrieval=command,
      )
    )
    return rendered

  lines = [
    f'Project: {text(project.name, ("project", "name"))}',
    f'Status: {project.status}',
    f'Objective: {text(project.objective, ("project", "objective"))}',
    *(
      ['Charter context: legacy incomplete']
      if project.charter_context_status == 'legacy-incomplete'
      else []
    ),
    f'Project database: {text(data.path, ("path",))}',
    f'Active goal: {goal_record.id} ({goal_record.status})'
    if goal_record is not None
    else 'Active goal: -',
    f'Goal text: {text(goal_record.text, ("goal", "goal", "text"))}'
    if goal_record is not None
    else 'Goal text: -',
    f'Active stage: {text(stage.name, ("stage", "name"))}'
    if stage is not None
    else 'Active stage: -',
    f'Active task: {task.id}'
    f'{_task_compatibility_markers(task.title_status)} '
    f'{text(task.title, ("task", "title"))}'
    if task is not None
    else 'Active task: -',
    f'Summary: {text(state.summary, ("state", "summary"))}',
    f'Next action: {text(state.next_action, ("state", "next_action"))}',
  ]
  if data.blockers:
    lines.append(f'Open blockers{_handoff_page_suffix(view, "blockers")}:')
    for index, item in enumerate(data.blockers):
      lines.append(
        f'- {item.id} [{item.target_kind} {item.target_id}]: '
        f'{text(item.description, ("blockers", index, "description"))}; '
        f'required: '
        f'{text(item.required, ("blockers", index, "required"))}'
      )
  if data.blocked_tasks:
    lines.append(
      f'Blocked tasks{_handoff_page_suffix(view, "blocked_tasks")}:'
    )
    for index, item in enumerate(data.blocked_tasks):
      title_text = text(item.title, ('blocked_tasks', index, 'title'))
      stage_text = text(
        item.stage_name, ('blocked_tasks', index, 'stage_name')
      )
      lines.append(
        f'- {item.id}{_task_compatibility_markers(item.title_status)} '
        f'{title_text} (stage: {stage_text}; goal: {item.goal_id or "-"})'
      )
  if data.blocked_goals:
    lines.append(
      f'Blocked goals{_handoff_page_suffix(view, "blocked_goals")}:'
    )
    for index, item in enumerate(data.blocked_goals):
      goal_desc = text(item.text, ('blocked_goals', index, 'text'))
      reason_text = text(
        item.status_reason, ('blocked_goals', index, 'status_reason')
      )
      lines.append(f'- {item.id}: {goal_desc}; reason: {reason_text}')
  if data.decisions:
    lines.append(
      f'Relevant {data.focus.kind} decisions'
      + _handoff_page_suffix(view, 'decisions')
      + ':'
    )
    for index, item in enumerate(data.decisions):
      lines.append(
        f'- {item.id}'
        f'{_record_compatibility_markers(item.context_status)}'
        f': {text(item.summary, ("decisions", index, "summary"))}'
      )
  if data.evidence:
    lines.append(
      f'Relevant {data.focus.kind} evidence'
      + _handoff_page_suffix(view, 'evidence')
      + ':'
    )
    for index, item in enumerate(data.evidence):
      markers = _record_compatibility_markers(
        item.context_status, item.claim_status
      )
      lines.append(
        f'- {item.id}{markers}: '
        f'{text(item.claim, ("evidence", index, "claim"))}'
      )
  if data.logs:
    lines.append(
      'Recent task log' + _handoff_page_suffix(view, 'task_log') + ':'
    )
    for reverse_index, item in enumerate(reversed(data.logs)):
      index = len(data.logs) - reverse_index - 1
      lines.append(
        f'- {text(item.kind, ("logs", index, "kind"))}: '
        f'{text(item.message, ("logs", index, "message"))}'
      )
  projection = HandoffProjection(
    character_limit=HANDOFF_TEXT_LIMIT,
    truncated_fields=tuple(truncations),
    full_value_commands=tuple(sorted(commands)),
  )
  if projection.truncated_fields:
    lines.append(
      f'Text projection: {len(projection.truncated_fields)} fields '
      f'truncated at {projection.character_limit} rendered characters.'
    )
    lines.extend(
      f'- Full values: {command}'
      for command in projection.full_value_commands
    )
  return '\n'.join(lines), projection


def format_handoff(
  view: HandoffView | TextHandoffView,
  full_value_command: Callable[[tuple[str | int, ...]], str],
) -> str:
  return _render_handoff(view, full_value_command)[0]


def build_handoff_json(
  view: HandoffView,
  full_value_command: Callable[[tuple[str | int, ...]], str],
) -> HandoffJson:
  _, projection = _render_handoff(view, full_value_command)
  return HandoffJson(view=view, text_projection=projection)
