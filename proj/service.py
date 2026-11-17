import codecs
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

from .core import (
  BLOCKER_STATUSES,
  GOAL_STATUSES,
  HANDOFF_LIMIT,
  HANDOFF_TEXT_LIMIT,
  TASK_STATUSES,
  UNICODE_WHITESPACE,
  UNSET,
  BlockerFilterStatus,
  BlockerStatus,
  CharterContextStatus,
  ClaimStatus,
  FocusKind,
  GoalReference,
  GoalStatus,
  GoalText,
  PositiveInt,
  ProjectError,
  ProjectStatus,
  RecordContextStatus,
  StageName,
  StageReference,
  StageStatus,
  SubstantiveText,
  TaskStatus,
  TaskTag,
  TitleStatus,
  Unset,
  dataclass_to_dict,
  is_substantive,
  parse_goal_reference,
  parse_stage_reference,
)
from .schema import connection_time, ensure_utf8_encoding

__all__ = [
  'ActiveGoalRef',
  'BlockedGoalSummary',
  'BlockedTaskSummary',
  'BlockerRecord',
  'BoundedText',
  'CharterHistoryRecord',
  'DecisionRecord',
  'EvidenceRecord',
  'GoalDetails',
  'GoalListItem',
  'GoalRecord',
  'GoalStageSummary',
  'GoalStages',
  'GoalTaskRecord',
  'HandoffBlockerSummary',
  'HandoffData',
  'HandoffDecisionSummary',
  'HandoffFocus',
  'HandoffLogEntry',
  'HandoffPage',
  'HandoffPages',
  'HandoffTaskRecord',
  'ProjectPatch',
  'ProjectRecord',
  'ProjectState',
  'ProjectStatePatch',
  'ProjectSummary',
  'ProjectView',
  'RecordListFilter',
  'StageListItem',
  'StagePatch',
  'StageRecord',
  'TaskDetails',
  'TaskLogRecord',
  'TaskPatch',
  'TaskRecord',
  'TextBlockedGoalSummary',
  'TextBlockedTaskSummary',
  'TextHandoffBlockerSummary',
  'TextHandoffData',
  'TextHandoffDecisionSummary',
  'TextHandoffEvidenceSummary',
  'TextHandoffGoal',
  'TextHandoffLogEntry',
  'TextHandoffProject',
  'TextHandoffStage',
  'TextHandoffState',
  'TextHandoffTask',
  'achieve_goal',
  'achieve_stage',
  'activate_goal',
  'add_blocker',
  'add_decision',
  'add_evidence',
  'add_stage',
  'add_stage_dependency',
  'add_task',
  'add_task_tags',
  'append_task_log',
  'block_goal',
  'block_task',
  'cancel_goal',
  'cancel_task',
  'complete_task',
  'create_goal',
  'derive_project_status',
  'derive_stage_status',
  'goal_text',
  'read_blockers',
  'read_decisions',
  'read_evidence',
  'read_goal',
  'read_goals',
  'read_handoff',
  'read_project',
  'read_project_summary',
  'read_stages',
  'read_task',
  'read_task_logs',
  'read_tasks',
  'read_text_handoff',
  'remove_stage_dependency',
  'remove_task_tags',
  'reopen_goal',
  'reopen_task',
  'resolve_blocker',
  'start_task',
  'title_status_for',
  'update_project_and_state',
  'update_stage',
  'update_task',
]

_GOAL_STATUS_MAP: Final[dict[str, GoalStatus]] = {
  'active': 'active',
  'pending': 'pending',
  'blocked': 'blocked',
  'achieved': 'achieved',
  'cancelled': 'cancelled',
}
_TASK_STATUS_MAP: Final[dict[str, TaskStatus]] = {
  'pending': 'pending',
  'active': 'active',
  'completed': 'completed',
  'blocked': 'blocked',
  'cancelled': 'cancelled',
}
_BLOCKER_STATUS_MAP: Final[dict[str, BlockerStatus]] = {
  'open': 'open',
  'resolved': 'resolved',
  'withdrawn': 'withdrawn',
}
_CHARTER_CONTEXT_MAP: Final[dict[str, CharterContextStatus]] = {
  'current': 'current',
  'legacy-incomplete': 'legacy-incomplete',
}
_RECORD_CONTEXT_MAP: Final[dict[str, RecordContextStatus]] = {
  'complete': 'complete',
  'legacy-unresolved': 'legacy-unresolved',
}
_CLAIM_STATUS_MAP: Final[dict[str, ClaimStatus]] = {
  'substantive': 'substantive',
  'legacy-blank': 'legacy-blank',
}
_FOCUS_KIND_MAP: Final[dict[str, FocusKind]] = {
  'task': 'task',
  'goal': 'goal',
}
_DEFAULT_LOG_LIMIT: Final[PositiveInt] = PositiveInt(20)


@dataclass(frozen=True, slots=True)
class ProjectSummary:
  name: str
  status: ProjectStatus
  objective: str
  updated_at: int
  path: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ProjectRecord:
  id: int
  name: str
  objective: str
  scope: str
  non_goals: str
  constraints_text: str
  acceptance: str
  created_at: int
  updated_at: int
  charter_context_status: CharterContextStatus
  status: ProjectStatus
  completed_at: int | None

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ProjectState:
  id: int
  summary: str
  next_action: str
  updated_at: int
  revision: int

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class CharterHistoryRecord:
  id: int
  objective: str
  scope: str
  non_goals: str
  constraints_text: str
  acceptance: str
  replaced_at: int

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class GoalStageSummary:
  id: int
  name: str
  status: StageStatus
  outcome: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class GoalRecord:
  id: int
  text: str
  status: GoalStatus
  status_reason: str
  ever_activated: int
  created_at: int
  started_at: int
  achieved_at: int | None
  updated_at: int

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class GoalListItem:
  id: int
  text: str
  status: GoalStatus
  status_reason: str
  ever_activated: int
  created_at: int
  started_at: int
  achieved_at: int | None
  updated_at: int
  is_active: int
  stage_names: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class StageRecord:
  id: int
  name: str
  outcome: str
  purpose: str
  entry_conditions: str
  exit_evidence: str
  position: int
  achievement_generation: int
  achievement_generation_started_at: int
  created_at: int
  updated_at: int
  status: StageStatus
  started_at: int | None
  achieved_at: int | None
  achievement_evidence_id: int | None

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class StageListItem:
  id: int
  name: str
  outcome: str
  purpose: str
  entry_conditions: str
  exit_evidence: str
  position: int
  achievement_generation: int
  achievement_generation_started_at: int
  created_at: int
  updated_at: int
  status: StageStatus
  started_at: int | None
  achieved_at: int | None
  achievement_evidence_id: int | None
  dependencies: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffTaskRecord:
  id: int
  goal_id: int | None
  stage_id: int | None
  title: str
  purpose: str
  scope: str
  exclusions: str
  result: str
  completion_evidence: str
  status: TaskStatus
  priority: int
  created_at: int
  started_at: int | None
  completed_at: int | None
  updated_at: int
  title_status: TitleStatus

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class GoalTaskRecord:
  id: int
  goal_id: int | None
  stage_id: int | None
  title: str
  purpose: str
  scope: str
  exclusions: str
  result: str
  completion_evidence: str
  status: TaskStatus
  priority: int
  created_at: int
  started_at: int | None
  completed_at: int | None
  updated_at: int
  stage_name: str | None
  title_status: TitleStatus

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class TaskRecord:
  id: int
  goal_id: int | None
  stage_id: int | None
  title: str
  purpose: str
  scope: str
  exclusions: str
  result: str
  completion_evidence: str
  status: TaskStatus
  priority: int
  created_at: int
  started_at: int | None
  completed_at: int | None
  updated_at: int
  stage_name: str | None
  tags: str
  title_status: TitleStatus

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class TaskLogRecord:
  id: int
  task_id: int
  occurred_at: int
  kind: str
  message: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class DecisionRecord:
  id: int
  goal_id: int | None
  stage_id: int | None
  task_id: int | None
  summary: str
  rationale: str
  alternatives: str
  consequences: str
  decided_at: int
  context_status: RecordContextStatus

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class BlockerRecord:
  id: int
  goal_id: int | None
  stage_id: int | None
  task_id: int | None
  description: str
  impact: str
  attempts: str
  required: str
  status: BlockerStatus
  opened_at: int
  resolved_at: int | None
  resolution: str
  target_kind: FocusKind
  target_id: int

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
  id: int
  goal_id: int | None
  stage_id: int | None
  task_id: int | None
  claim: str
  source: str
  result: str
  captured_at: int
  context_status: RecordContextStatus
  claim_status: ClaimStatus
  stage_generation: int | None

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class GoalDetails:
  goal: GoalRecord
  stages: tuple[GoalStageSummary, ...]
  tasks: tuple[GoalTaskRecord, ...]
  blockers: tuple[BlockerRecord, ...]
  evidence: tuple[EvidenceRecord, ...]
  decisions: tuple[DecisionRecord, ...]

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ProjectView:
  path: str
  project: ProjectRecord
  state: ProjectState
  goal: GoalDetails | None
  charter_history: tuple[CharterHistoryRecord, ...]

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class TaskDetails:
  task: TaskRecord
  logs: tuple[TaskLogRecord, ...]

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ActiveGoalRef:
  goal: GoalRecord

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class BlockedTaskSummary:
  id: int
  title: str
  status: TaskStatus
  goal_id: int | None
  stage_id: int | None
  stage_name: str | None
  updated_at: int
  title_status: TitleStatus

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class BlockedGoalSummary:
  id: int
  text: str
  status: GoalStatus
  status_reason: str
  updated_at: int

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffBlockerSummary:
  id: int
  goal_id: int | None
  stage_id: int | None
  task_id: int | None
  description: str
  required: str
  opened_at: int
  target_kind: FocusKind
  target_id: int

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffDecisionSummary:
  id: int
  goal_id: int | None
  stage_id: int | None
  task_id: int | None
  summary: str
  decided_at: int
  context_status: RecordContextStatus

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffLogEntry:
  occurred_at: int
  kind: str
  message: str

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffPage:
  shown: int
  total: int
  truncated: bool

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffPages:
  blocked_tasks: HandoffPage
  blocked_goals: HandoffPage
  blockers: HandoffPage
  decisions: HandoffPage
  evidence: HandoffPage
  task_log: HandoffPage

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffFocus:
  kind: FocusKind | None
  id: int | None

  def __post_init__(self) -> None:
    if (self.kind is None) != (self.id is None):
      raise ProjectError(
        'Handoff focus kind and ID must both be set or both be null'
      )
    if self.id is not None and (isinstance(self.id, bool) or self.id <= 0):
      raise ProjectError('Handoff focus ID must be positive')

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class HandoffData:
  path: str
  project: ProjectRecord
  state: ProjectState
  goal: ActiveGoalRef | None
  stage: StageRecord | None
  task: HandoffTaskRecord | None
  blocked_tasks: tuple[BlockedTaskSummary, ...]
  blocked_goals: tuple[BlockedGoalSummary, ...]
  blockers: tuple[HandoffBlockerSummary, ...]
  decisions: tuple[HandoffDecisionSummary, ...]
  evidence: tuple[EvidenceRecord, ...]
  logs: tuple[HandoffLogEntry, ...]
  focus: HandoffFocus
  pages: HandoffPages

  def to_dict(self) -> dict[str, object]:
    return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class BoundedText:
  prefix: str
  characters: int

  def __post_init__(self) -> None:
    if not isinstance(self.prefix, str):
      raise ProjectError('BoundedText prefix must be str')
    if (
      isinstance(self.characters, bool)
      or not isinstance(self.characters, int)
      or self.characters < 0
    ):
      raise ProjectError(
        'BoundedText characters must be a non-negative int'
      )
    expected_len = min(self.characters, HANDOFF_TEXT_LIMIT + 1)
    if len(self.prefix) != expected_len:
      raise ProjectError(
        f'BoundedText prefix length must be {expected_len}; '
        f'received {len(self.prefix)}'
      )


@dataclass(frozen=True, slots=True)
class TextHandoffProject:
  name: BoundedText
  status: ProjectStatus
  objective: BoundedText
  charter_context_status: CharterContextStatus


@dataclass(frozen=True, slots=True)
class TextHandoffState:
  summary: BoundedText
  next_action: BoundedText


@dataclass(frozen=True, slots=True)
class TextHandoffGoal:
  id: int
  status: GoalStatus
  text: BoundedText


@dataclass(frozen=True, slots=True)
class TextHandoffStage:
  id: int
  name: BoundedText


@dataclass(frozen=True, slots=True)
class TextHandoffTask:
  id: int
  goal_id: int | None
  stage_id: int | None
  title: BoundedText
  title_status: TitleStatus


@dataclass(frozen=True, slots=True)
class TextBlockedTaskSummary:
  id: int
  title: BoundedText
  goal_id: int | None
  stage_id: int | None
  stage_name: BoundedText | None
  title_status: TitleStatus


@dataclass(frozen=True, slots=True)
class TextBlockedGoalSummary:
  id: int
  text: BoundedText
  status_reason: BoundedText


@dataclass(frozen=True, slots=True)
class TextHandoffBlockerSummary:
  id: int
  description: BoundedText
  required: BoundedText
  target_kind: FocusKind
  target_id: int


@dataclass(frozen=True, slots=True)
class TextHandoffDecisionSummary:
  id: int
  summary: BoundedText
  context_status: RecordContextStatus


@dataclass(frozen=True, slots=True)
class TextHandoffEvidenceSummary:
  id: int
  claim: BoundedText
  context_status: RecordContextStatus
  claim_status: ClaimStatus


@dataclass(frozen=True, slots=True)
class TextHandoffLogEntry:
  kind: BoundedText
  message: BoundedText


@dataclass(frozen=True, slots=True)
class TextHandoffData:
  path: str
  project: TextHandoffProject
  state: TextHandoffState
  goal: TextHandoffGoal | None
  stage: TextHandoffStage | None
  task: TextHandoffTask | None
  blocked_tasks: tuple[TextBlockedTaskSummary, ...]
  blocked_goals: tuple[TextBlockedGoalSummary, ...]
  blockers: tuple[TextHandoffBlockerSummary, ...]
  decisions: tuple[TextHandoffDecisionSummary, ...]
  evidence: tuple[TextHandoffEvidenceSummary, ...]
  logs: tuple[TextHandoffLogEntry, ...]
  focus: HandoffFocus
  pages: HandoffPages


def _coerce_stage_ref(raw: StageReference | int | str) -> StageReference:
  if isinstance(raw, (PositiveInt, StageName)):
    return raw
  return parse_stage_reference(raw)


def _coerce_goal_ref(raw: GoalReference | int | str) -> GoalReference:
  if raw == 'active':
    return 'active'
  if isinstance(raw, PositiveInt):
    return raw
  return parse_goal_reference(raw)


@dataclass(frozen=True, slots=True)
class GoalStages:
  references: tuple[StageReference, ...]

  def __post_init__(self) -> None:
    if not self.references:
      raise ProjectError('A goal must link to at least one stage')
    if len(self.references) != len(set(self.references)):
      raise ProjectError(
        'A goal cannot link the same stage more than once'
      )

  @classmethod
  def parse(
    cls, stages: Sequence[StageReference | int | str] | str
  ) -> 'GoalStages':
    raw_items: Sequence[StageReference | int | str] = (
      (stages,) if isinstance(stages, str) else stages
    )
    if not raw_items or any(ref is None for ref in raw_items):
      raise ProjectError('A goal must link to at least one stage')
    return cls(tuple(_coerce_stage_ref(item) for item in raw_items))


@dataclass(frozen=True, slots=True)
class RecordListFilter:
  limit: PositiveInt
  stage: StageReference | None = None
  task: PositiveInt | None = None
  goal: GoalReference | None = None
  no_task: bool = False

  def __post_init__(self) -> None:
    if not isinstance(self.limit, PositiveInt):
      raise ProjectError('Record limits must be positive')
    if not isinstance(self.no_task, bool):
      raise ProjectError('Record no-task filter must be a boolean')
    if self.no_task and self.task is not None:
      raise ProjectError('Record task and no-task filters conflict')

  @classmethod
  def parse(
    cls,
    entity_label: str,
    *,
    limit: int = 20,
    stage: StageReference | int | str | None = None,
    task: int | None = None,
    goal: GoalReference | int | str | None = None,
    no_task: bool = False,
  ) -> 'RecordListFilter':
    parsed_limit = PositiveInt.parse(limit, f'{entity_label} limits')
    if no_task and task is not None:
      raise ProjectError(
        f'{entity_label} task and no-task filters conflict'
      )
    parsed_task = (
      PositiveInt.parse(task, 'Task ID') if task is not None else None
    )
    parsed_stage = _coerce_stage_ref(stage) if stage is not None else None
    parsed_goal = _coerce_goal_ref(goal) if goal is not None else None
    return cls(
      limit=parsed_limit,
      stage=parsed_stage,
      task=parsed_task,
      goal=parsed_goal,
      no_task=no_task,
    )


@dataclass(frozen=True, slots=True)
class ProjectPatch:
  objective: str | Unset = UNSET
  scope: str | Unset = UNSET
  non_goals: str | Unset = UNSET
  constraints_text: str | Unset = UNSET
  acceptance: str | Unset = UNSET


@dataclass(frozen=True, slots=True)
class ProjectStatePatch:
  summary: str | Unset = UNSET
  next_action: str | Unset = UNSET


@dataclass(frozen=True, slots=True)
class StagePatch:
  name: SubstantiveText | Unset = UNSET
  outcome: SubstantiveText | Unset = UNSET
  purpose: str | Unset = UNSET
  entry_conditions: str | Unset = UNSET
  exit_evidence: str | Unset = UNSET

  @classmethod
  def parse(
    cls,
    *,
    name: str | Unset = UNSET,
    outcome: str | Unset = UNSET,
    purpose: str | Unset = UNSET,
    entry_conditions: str | Unset = UNSET,
    exit_evidence: str | Unset = UNSET,
  ) -> 'StagePatch':
    parsed_name: SubstantiveText | Unset = (
      SubstantiveText.parse(name, 'Stage name')
      if isinstance(name, str)
      else name
    )
    parsed_outcome: SubstantiveText | Unset = (
      SubstantiveText.parse(outcome, 'Stage outcome')
      if isinstance(outcome, str)
      else outcome
    )
    return cls(
      name=parsed_name,
      outcome=parsed_outcome,
      purpose=purpose,
      entry_conditions=entry_conditions,
      exit_evidence=exit_evidence,
    )


@dataclass(frozen=True, slots=True)
class TaskPatch:
  title: SubstantiveText | Unset = UNSET
  purpose: str | Unset = UNSET
  scope: str | Unset = UNSET
  exclusions: str | Unset = UNSET
  result: str | Unset = UNSET
  completion_evidence: str | Unset = UNSET
  priority: int | Unset = UNSET
  stage_id: StageReference | None | Unset = UNSET
  goal_id: GoalReference | None | Unset = UNSET

  def __post_init__(self) -> None:
    if isinstance(self.priority, bool) or (
      self.priority is not UNSET and not isinstance(self.priority, int)
    ):
      raise ProjectError('Task priority must be an integer')

  @classmethod
  def parse(
    cls,
    *,
    title: str | SubstantiveText | Unset = UNSET,
    purpose: str | Unset = UNSET,
    scope: str | Unset = UNSET,
    exclusions: str | Unset = UNSET,
    result: str | Unset = UNSET,
    completion_evidence: str | Unset = UNSET,
    priority: int | Unset = UNSET,
    stage_id: StageReference | int | str | None | Unset = UNSET,
    goal_id: GoalReference | int | str | None | Unset = UNSET,
  ) -> 'TaskPatch':
    parsed_title: SubstantiveText | Unset = (
      SubstantiveText.parse(title, 'Task title')
      if isinstance(title, str)
      else title
    )
    if isinstance(priority, bool):
      raise ProjectError('Task priority must be an integer')
    parsed_stage: StageReference | None | Unset
    if stage_id is None:
      parsed_stage = None
    elif isinstance(stage_id, (PositiveInt, StageName, int, str)):
      parsed_stage = _coerce_stage_ref(stage_id)
    else:
      parsed_stage = UNSET
    parsed_goal: GoalReference | None | Unset
    if goal_id is None:
      parsed_goal = None
    elif isinstance(goal_id, (PositiveInt, int, str)):
      parsed_goal = _coerce_goal_ref(goal_id)
    else:
      parsed_goal = UNSET
    return cls(
      title=parsed_title,
      purpose=purpose,
      scope=scope,
      exclusions=exclusions,
      result=result,
      completion_evidence=completion_evidence,
      priority=priority,
      stage_id=parsed_stage,
      goal_id=parsed_goal,
    )


def derive_stage_status(
  counts: Mapping[str, int], *, has_valid_achievement: bool
) -> StageStatus:
  if counts.get('active'):
    return 'active'
  if counts.get('pending'):
    return 'pending'
  if counts.get('blocked'):
    return 'blocked'
  if counts.get('completed') and has_valid_achievement:
    return 'achieved'
  total = sum(counts.values())
  if total > 0 and counts.get('cancelled', 0) == total:
    return 'superseded'
  return 'pending'


def derive_project_status(
  stage_statuses: Sequence[StageStatus],
) -> ProjectStatus:
  if 'achieved' in stage_statuses and all(
    status in ('achieved', 'superseded') for status in stage_statuses
  ):
    return 'complete'
  if any(status in ('active', 'pending') for status in stage_statuses):
    return 'active'
  if any(status == 'blocked' for status in stage_statuses):
    return 'blocked'
  return 'active'


def title_status_for(title: str) -> TitleStatus:
  return 'substantive' if is_substantive(title) else 'legacy-blank'


@contextmanager
def _sqlite_boundary() -> Iterator[None]:
  try:
    yield
  except sqlite3.Error as error:
    raise ProjectError(f'Project database error: {error}') from error


def _req_int(row: sqlite3.Row, col: str) -> int:
  val = row[col]
  if isinstance(val, bool) or not isinstance(val, int):
    raise ProjectError(f'Column {col!r} must be an integer')
  return val


def _opt_int(row: sqlite3.Row, col: str) -> int | None:
  val = row[col]
  if val is None:
    return None
  if isinstance(val, bool) or not isinstance(val, int):
    raise ProjectError(f'Column {col!r} must be an integer or null')
  return val


def _req_str(row: sqlite3.Row, col: str) -> str:
  val = row[col]
  if not isinstance(val, str):
    raise ProjectError(f'Column {col!r} must be text')
  return val


def _opt_str(row: sqlite3.Row, col: str) -> str | None:
  val = row[col]
  if val is None:
    return None
  if not isinstance(val, str):
    raise ProjectError(f'Column {col!r} must be text or null')
  return val


def _req_goal_status(row: sqlite3.Row) -> GoalStatus:
  raw = _req_str(row, 'status')
  val = _GOAL_STATUS_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid goal status: {raw}')
  return val


def _req_task_status(row: sqlite3.Row) -> TaskStatus:
  raw = _req_str(row, 'status')
  val = _TASK_STATUS_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid task status: {raw}')
  return val


def _req_blocker_status(row: sqlite3.Row) -> BlockerStatus:
  raw = _req_str(row, 'status')
  val = _BLOCKER_STATUS_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid blocker status: {raw}')
  return val


def _req_charter_context(row: sqlite3.Row) -> CharterContextStatus:
  raw = _req_str(row, 'charter_context_status')
  val = _CHARTER_CONTEXT_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid charter context status: {raw}')
  return val


def _req_record_context(row: sqlite3.Row) -> RecordContextStatus:
  raw = _req_str(row, 'context_status')
  val = _RECORD_CONTEXT_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid record context status: {raw}')
  return val


def _req_claim_status(row: sqlite3.Row) -> ClaimStatus:
  raw = _req_str(row, 'claim_status')
  val = _CLAIM_STATUS_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid evidence claim status: {raw}')
  return val


def _req_focus_kind(row: sqlite3.Row, col: str) -> FocusKind:
  raw = _req_str(row, col)
  val = _FOCUS_KIND_MAP.get(raw)
  if val is None:
    raise ProjectError(f'Invalid focus kind: {raw}')
  return val


def _inserted_id(cursor: sqlite3.Cursor, record_name: str) -> int:
  identifier = cursor.lastrowid
  if identifier is None:
    raise ProjectError(
      f'{record_name} insertion did not return an identifier'
    )
  return identifier


def _touch(connection: sqlite3.Connection, timestamp: int) -> None:
  connection.execute(
    'UPDATE project SET updated_at = ? WHERE id = 1', (timestamp,)
  )
  connection.execute(
    """
    UPDATE project_state
    SET updated_at = ?, revision = revision + 1
    WHERE id = 1
    """,
    (timestamp,),
  )


def _resolve_stage(
  connection: sqlite3.Connection, reference: StageReference
) -> int:
  if isinstance(reference, PositiveInt):
    row = connection.execute(
      'SELECT id FROM stage WHERE id = ?', (reference.value,)
    ).fetchone()
  else:
    row = connection.execute(
      'SELECT id FROM stage WHERE name = ?', (reference.value,)
    ).fetchone()
  if row is None:
    raise ProjectError(f'Stage does not exist: {reference.value}')
  return _req_int(row, 'id')


def _resolve_optional_stage(
  connection: sqlite3.Connection, reference: StageReference | None
) -> int | None:
  if reference is None:
    return None
  return _resolve_stage(connection, reference)


def _resolve_task_id(connection: sqlite3.Connection, task_id: int) -> int:
  row = connection.execute(
    'SELECT id FROM task WHERE id = ?', (task_id,)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Task does not exist: {task_id}')
  return _req_int(row, 'id')


def _resolve_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
) -> int:
  if reference is None or reference == 'active':
    row = connection.execute(
      "SELECT id FROM goal WHERE status = 'active'"
    ).fetchone()
    if row is None:
      raise ProjectError('Project has no active goal')
    return _req_int(row, 'id')
  row = connection.execute(
    'SELECT id FROM goal WHERE id = ?', (reference.value,)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Goal does not exist: {reference.value}')
  return _req_int(row, 'id')


def _resolve_evidence_id(
  connection: sqlite3.Connection, evidence_id: int
) -> int:
  row = connection.execute(
    'SELECT id FROM evidence WHERE id = ?', (evidence_id,)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Evidence does not exist: {evidence_id}')
  return _req_int(row, 'id')


def _has_goal_stage_link(
  connection: sqlite3.Connection,
  goal_id: int | None,
  stage_id: int | None,
) -> bool:
  if goal_id is None or stage_id is None:
    return True
  return (
    connection.execute(
      'SELECT 1 FROM goal_stage WHERE goal_id = ? AND stage_id = ?',
      (goal_id, stage_id),
    ).fetchone()
    is not None
  )


def _ensure_goal_stage(
  connection: sqlite3.Connection,
  goal_id: int | None,
  stage_id: int | None,
  relationship: str,
) -> None:
  if not _has_goal_stage_link(connection, goal_id, stage_id):
    raise ProjectError(
      f'{relationship} stage is not linked to goal {goal_id}'
    )


def _project_charter_missing(connection: sqlite3.Connection) -> list[str]:
  project = connection.execute('SELECT * FROM project').fetchone()
  if project is None:
    raise ProjectError('Project database has no project record')
  labels = (
    ('objective', 'objective'),
    ('scope', 'scope'),
    ('non_goals', 'non-goals'),
    ('constraints_text', 'constraints'),
    ('acceptance', 'acceptance evidence'),
  )
  return [
    label
    for field_name, label in labels
    if not is_substantive(_req_str(project, field_name))
  ]


def _is_project_chartered(connection: sqlite3.Connection) -> bool:
  return not _project_charter_missing(connection)


def _ensure_project_chartered(connection: sqlite3.Connection) -> None:
  missing = _project_charter_missing(connection)
  if missing:
    raise ProjectError(
      'Starting work requires a complete project charter; missing: '
      + ', '.join(missing)
    )


def _ensure_stage_contract(
  connection: sqlite3.Connection, stage_id: int
) -> None:
  stage = connection.execute(
    'SELECT name, outcome FROM stage WHERE id = ?', (stage_id,)
  ).fetchone()
  if (
    stage is None
    or not is_substantive(_req_str(stage, 'name'))
    or not is_substantive(_req_str(stage, 'outcome'))
  ):
    raise ProjectError('Starting work requires a complete stage contract')


def _resolve_record_relationships(
  connection: sqlite3.Connection,
  relationship: str,
  stage: StageReference | None = None,
  task: PositiveInt | None = None,
  goal: GoalReference | None = None,
) -> tuple[int | None, int | None, int | None]:
  stage_id = _resolve_optional_stage(connection, stage)
  task_id = _resolve_task_id(connection, task.value) if task else None
  goal_id = _resolve_goal(connection, goal) if goal is not None else None
  if task_id is not None:
    task_row = connection.execute(
      'SELECT goal_id, stage_id FROM task WHERE id = ?', (task_id,)
    ).fetchone()
    if task_row is None:
      raise ProjectError(f'Task does not exist: {task_id}')
    task_stage_id = _opt_int(task_row, 'stage_id')
    task_goal_id = _opt_int(task_row, 'goal_id')
    if stage_id is None:
      stage_id = task_stage_id
    elif stage_id != task_stage_id:
      raise ProjectError(f'{relationship} stage does not match task stage')
    if goal_id is None:
      goal_id = task_goal_id
    elif goal_id != task_goal_id:
      raise ProjectError(f'{relationship} goal does not match task goal')
  _ensure_goal_stage(connection, goal_id, stage_id, relationship)
  return stage_id, task_id, goal_id


def _active_goal_id(connection: sqlite3.Connection) -> int | None:
  row = connection.execute(
    "SELECT id FROM goal WHERE status = 'active'"
  ).fetchone()
  return _req_int(row, 'id') if row is not None else None


def _active_task_row(connection: sqlite3.Connection) -> sqlite3.Row | None:
  return connection.execute(
    "SELECT * FROM task WHERE status = 'active'"
  ).fetchone()


_STAGE_COUNTS_SQL: Final[str] = """
  sa.evidence_id AS achievement_evidence_id,
  sa.achieved_at AS achieved_at,
  MIN(t.started_at) AS started_at,
  COALESCE(
    SUM(CASE WHEN t.status = 'active' THEN 1 ELSE 0 END), 0
  ) AS active_count,
  COALESCE(
    SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END), 0
  ) AS pending_count,
  COALESCE(
    SUM(CASE WHEN t.status = 'blocked' THEN 1 ELSE 0 END), 0
  ) AS blocked_count,
  COALESCE(
    SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END), 0
  ) AS completed_count,
  COALESCE(
    SUM(CASE WHEN t.status = 'cancelled' THEN 1 ELSE 0 END), 0
  ) AS cancelled_count
"""


def _stage_status_from_summary(row: sqlite3.Row) -> StageStatus:
  counts = {
    status: _req_int(row, f'{status}_count')
    for status in (
      'active',
      'pending',
      'blocked',
      'completed',
      'cancelled',
    )
  }
  return derive_stage_status(
    counts,
    has_valid_achievement=_opt_int(row, 'achieved_at') is not None,
  )


def _decode_stage_from_summary(row: sqlite3.Row) -> StageRecord:
  return StageRecord(
    id=_req_int(row, 'id'),
    name=_req_str(row, 'name'),
    outcome=_req_str(row, 'outcome'),
    purpose=_req_str(row, 'purpose'),
    entry_conditions=_req_str(row, 'entry_conditions'),
    exit_evidence=_req_str(row, 'exit_evidence'),
    position=_req_int(row, 'position'),
    achievement_generation=_req_int(row, 'achievement_generation'),
    achievement_generation_started_at=_req_int(
      row, 'achievement_generation_started_at'
    ),
    created_at=_req_int(row, 'created_at'),
    updated_at=_req_int(row, 'updated_at'),
    status=_stage_status_from_summary(row),
    started_at=_opt_int(row, 'started_at'),
    achieved_at=_opt_int(row, 'achieved_at'),
    achievement_evidence_id=_opt_int(row, 'achievement_evidence_id'),
  )


def _stage_status(
  connection: sqlite3.Connection, stage_id: int
) -> StageStatus:
  counts = {
    _req_str(row, 'status'): _req_int(row, 'count')
    for row in connection.execute(
      'SELECT status, count(*) AS count FROM task '
      'WHERE stage_id = ? GROUP BY status',
      (stage_id,),
    )
  }
  has_valid_achievement = (
    connection.execute(
      'SELECT 1 FROM stage_achievement '
      'WHERE stage_id = ? AND invalidated_at IS NULL',
      (stage_id,),
    ).fetchone()
    is not None
  )
  return derive_stage_status(
    counts, has_valid_achievement=has_valid_achievement
  )


def _stage_record(
  connection: sqlite3.Connection, stage_id: int
) -> StageRecord:
  row = connection.execute(
    f"""
    SELECT s.*, {_STAGE_COUNTS_SQL}
    FROM stage s
    LEFT JOIN stage_achievement sa
      ON sa.stage_id = s.id AND sa.invalidated_at IS NULL
    LEFT JOIN task t ON t.stage_id = s.id
    WHERE s.id = ?
    GROUP BY s.id
    """,
    (stage_id,),
  ).fetchone()
  if row is None:
    raise ProjectError(f'Stage does not exist: {stage_id}')
  return _decode_stage_from_summary(row)


def _project_status(connection: sqlite3.Connection) -> ProjectStatus:
  rows = connection.execute(
    """
    SELECT s.id,
      MAX(sa.achieved_at) AS achieved_at,
      COALESCE(
        SUM(CASE WHEN t.status = 'active' THEN 1 ELSE 0 END), 0
      ) AS active_count,
      COALESCE(
        SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END), 0
      ) AS pending_count,
      COALESCE(
        SUM(CASE WHEN t.status = 'blocked' THEN 1 ELSE 0 END), 0
      ) AS blocked_count,
      COALESCE(
        SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END), 0
      ) AS completed_count,
      COALESCE(
        SUM(CASE WHEN t.status = 'cancelled' THEN 1 ELSE 0 END), 0
      ) AS cancelled_count
    FROM stage s
    LEFT JOIN stage_achievement sa
      ON sa.stage_id = s.id AND sa.invalidated_at IS NULL
    LEFT JOIN task t ON t.stage_id = s.id
    GROUP BY s.id
    """
  ).fetchall()
  return derive_project_status(
    tuple(_stage_status_from_summary(row) for row in rows)
  )


def _project_completed_at(
  connection: sqlite3.Connection, status: ProjectStatus
) -> int | None:
  if status != 'complete':
    return None
  row = connection.execute(
    'SELECT MAX(achieved_at) AS completed_at FROM stage_achievement '
    'WHERE invalidated_at IS NULL'
  ).fetchone()
  return _opt_int(row, 'completed_at') if row is not None else None


def _ensure_task_goal_is_active(
  connection: sqlite3.Connection, goal_id: int | None
) -> None:
  if goal_id is None:
    return
  active_goal_id = _active_goal_id(connection)
  if active_goal_id == goal_id:
    return
  if active_goal_id is None:
    raise ProjectError(f'Task goal {goal_id} is not the active goal')
  raise ProjectError(
    f'Task goal {goal_id} does not match active goal {active_goal_id}'
  )


def _unachieved_dependency_name(
  connection: sqlite3.Connection, stage_id: int | None
) -> str | None:
  if stage_id is None:
    return None
  ensure_utf8_encoding(connection)
  dependency = connection.execute(
    """
    SELECT
      typeof(dependency_stage.name) AS name_type,
      CAST(
        substr(CAST(dependency_stage.name AS BLOB), 1, ?) AS BLOB
      ) AS name_prefix,
      octet_length(dependency_stage.name) AS name_bytes
    FROM stage_dependency
    JOIN stage dependency_stage
      ON dependency_stage.id = stage_dependency.dependency_id
    LEFT JOIN stage_achievement
      ON stage_achievement.stage_id = dependency_stage.id
      AND stage_achievement.invalidated_at IS NULL
    WHERE stage_dependency.stage_id = ?
      AND stage_achievement.id IS NULL
    LIMIT 1
    """,
    (_HANDOFF_BYTE_LIMIT, stage_id),
  ).fetchone()
  if dependency is None:
    return None
  if dependency['name_type'] != 'text':
    raise ProjectError("Column 'name' must be text")
  prefix_blob = dependency['name_prefix']
  total_bytes = _req_int(dependency, 'name_bytes')
  if total_bytes == 0 and prefix_blob is None:
    return ''
  if not isinstance(prefix_blob, (bytes, bytearray, memoryview)):
    raise ProjectError("Column 'name' prefix must be bytes")
  decoder = codecs.getincrementaldecoder('utf-8')('strict')
  try:
    decoded = decoder.decode(
      bytes(prefix_blob), final=(total_bytes <= _HANDOFF_BYTE_LIMIT)
    )
  except UnicodeDecodeError as error:
    raise ProjectError(f'Database error: {error}') from error
  if (
    len(decoded) > HANDOFF_TEXT_LIMIT or total_bytes > _HANDOFF_BYTE_LIMIT
  ):
    return f'{decoded[:HANDOFF_TEXT_LIMIT]}…'
  return decoded


def _ensure_task_dependencies_are_achieved(
  connection: sqlite3.Connection, stage_id: int | None
) -> None:
  missing_name = _unachieved_dependency_name(connection, stage_id)
  if missing_name is not None:
    raise ProjectError(f'Stage dependency is not achieved: {missing_name}')


def _task_documentation_missing(row: sqlite3.Row) -> list[str]:
  fields_to_check = (
    'title',
    'purpose',
    'scope',
    'exclusions',
    'result',
    'completion_evidence',
  )
  return [
    field_name.replace('_', ' ')
    for field_name in fields_to_check
    if not is_substantive(_req_str(row, field_name))
  ]


def _ensure_task_documented(row: sqlite3.Row) -> None:
  missing = _task_documentation_missing(row)
  if missing:
    raise ProjectError(
      'Starting a task requires documented ' + ', '.join(missing)
    )


def _ensure_no_active_task(
  connection: sqlite3.Connection,
  transition: str,
  goal_id: int | None | Unset = UNSET,
) -> None:
  if goal_id is UNSET:
    task = _active_task_row(connection)
  else:
    task = connection.execute(
      "SELECT id FROM task WHERE status = 'active' AND goal_id = ?",
      (goal_id,),
    ).fetchone()
  if task is not None:
    raise ProjectError(
      f'{transition} requires active task {_req_int(task, "id")} to '
      'end first'
    )


def _return_task_to_pending(
  connection: sqlite3.Connection,
  task_id: int,
  timestamp: int,
  reason: str,
) -> None:
  connection.execute(
    "UPDATE task SET status = 'pending', updated_at = ? WHERE id = ?",
    (timestamp, task_id),
  )
  connection.execute(
    'INSERT INTO task_log '
    '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
    (task_id, timestamp, 'handoff', reason),
  )


def _handoff_active_goal(
  connection: sqlite3.Connection,
  target_goal_id: int,
  timestamp: int,
) -> None:
  active_goal_id = _active_goal_id(connection)
  if active_goal_id is None or active_goal_id == target_goal_id:
    return
  active_task = _active_task_row(connection)
  if (
    active_task is not None
    and _opt_int(active_task, 'goal_id') == active_goal_id
  ):
    _return_task_to_pending(
      connection,
      _req_int(active_task, 'id'),
      timestamp,
      f'Task returned to pending while activating goal {target_goal_id}',
    )
  connection.execute(
    "UPDATE goal SET status = 'pending', status_reason = ?, "
    'updated_at = ? WHERE id = ?',
    (
      f'Deferred while activating goal {target_goal_id}',
      timestamp,
      active_goal_id,
    ),
  )


def _activate_goal(
  connection: sqlite3.Connection,
  goal_id: int,
  timestamp: int,
  allowed_statuses: Sequence[GoalStatus],
) -> None:
  goal = connection.execute(
    'SELECT status, ever_activated FROM goal WHERE id = ?', (goal_id,)
  ).fetchone()
  if goal is None:
    raise ProjectError(f'Goal does not exist: {goal_id}')
  status = _req_goal_status(goal)
  if status not in allowed_statuses:
    statuses = ' or '.join(allowed_statuses)
    raise ProjectError(
      f'Only {statuses} goals can be activated; goal {goal_id} is {status}'
    )
  if connection.execute(
    'SELECT 1 FROM blocker '
    "WHERE goal_id = ? AND task_id IS NULL AND status = 'open' LIMIT 1",
    (goal_id,),
  ).fetchone():
    raise ProjectError('A goal cannot activate while it has open blockers')
  _handoff_active_goal(connection, goal_id, timestamp)
  if _req_int(goal, 'ever_activated'):
    connection.execute(
      "UPDATE goal SET status = 'active', status_reason = '', "
      'updated_at = ? WHERE id = ?',
      (timestamp, goal_id),
    )
  else:
    connection.execute(
      "UPDATE goal SET status = 'active', status_reason = '', "
      'started_at = ?, ever_activated = 1, updated_at = ? WHERE id = ?',
      (timestamp, timestamp, goal_id),
    )
  _touch(connection, timestamp)


def _blocked_goal_reason(
  connection: sqlite3.Connection, goal_id: int
) -> str:
  blocker = connection.execute(
    'SELECT description FROM blocker WHERE goal_id = ? '
    "AND task_id IS NULL AND status = 'open' "
    'ORDER BY opened_at DESC, id DESC LIMIT 1',
    (goal_id,),
  ).fetchone()
  return _req_str(blocker, 'description') if blocker is not None else ''


def _decode_goal_record(
  connection: sqlite3.Connection, row: sqlite3.Row
) -> GoalRecord:
  goal_id = _req_int(row, 'id')
  status = _req_goal_status(row)
  reason = (
    _blocked_goal_reason(connection, goal_id)
    if status == 'blocked'
    else _req_str(row, 'status_reason')
  )
  return GoalRecord(
    id=goal_id,
    text=_req_str(row, 'text'),
    status=status,
    status_reason=reason,
    ever_activated=_req_int(row, 'ever_activated'),
    created_at=_req_int(row, 'created_at'),
    started_at=_req_int(row, 'started_at'),
    achieved_at=_opt_int(row, 'achieved_at'),
    updated_at=_req_int(row, 'updated_at'),
  )


def _decode_goal_list_item(
  connection: sqlite3.Connection, row: sqlite3.Row
) -> GoalListItem:
  goal = _decode_goal_record(connection, row)
  return GoalListItem(
    id=goal.id,
    text=goal.text,
    status=goal.status,
    status_reason=goal.status_reason,
    ever_activated=goal.ever_activated,
    created_at=goal.created_at,
    started_at=goal.started_at,
    achieved_at=goal.achieved_at,
    updated_at=goal.updated_at,
    is_active=_req_int(row, 'is_active'),
    stage_names=_req_str(row, 'stage_names'),
  )


def _decode_handoff_task(row: sqlite3.Row) -> HandoffTaskRecord:
  title = _req_str(row, 'title')
  return HandoffTaskRecord(
    id=_req_int(row, 'id'),
    goal_id=_opt_int(row, 'goal_id'),
    stage_id=_opt_int(row, 'stage_id'),
    title=title,
    purpose=_req_str(row, 'purpose'),
    scope=_req_str(row, 'scope'),
    exclusions=_req_str(row, 'exclusions'),
    result=_req_str(row, 'result'),
    completion_evidence=_req_str(row, 'completion_evidence'),
    status=_req_task_status(row),
    priority=_req_int(row, 'priority'),
    created_at=_req_int(row, 'created_at'),
    started_at=_opt_int(row, 'started_at'),
    completed_at=_opt_int(row, 'completed_at'),
    updated_at=_req_int(row, 'updated_at'),
    title_status=title_status_for(title),
  )


def _decode_goal_task(row: sqlite3.Row) -> GoalTaskRecord:
  base = _decode_handoff_task(row)
  return GoalTaskRecord(
    id=base.id,
    goal_id=base.goal_id,
    stage_id=base.stage_id,
    title=base.title,
    purpose=base.purpose,
    scope=base.scope,
    exclusions=base.exclusions,
    result=base.result,
    completion_evidence=base.completion_evidence,
    status=base.status,
    priority=base.priority,
    created_at=base.created_at,
    started_at=base.started_at,
    completed_at=base.completed_at,
    updated_at=base.updated_at,
    stage_name=_opt_str(row, 'stage_name'),
    title_status=base.title_status,
  )


def _decode_task(row: sqlite3.Row) -> TaskRecord:
  base = _decode_handoff_task(row)
  return TaskRecord(
    id=base.id,
    goal_id=base.goal_id,
    stage_id=base.stage_id,
    title=base.title,
    purpose=base.purpose,
    scope=base.scope,
    exclusions=base.exclusions,
    result=base.result,
    completion_evidence=base.completion_evidence,
    status=base.status,
    priority=base.priority,
    created_at=base.created_at,
    started_at=base.started_at,
    completed_at=base.completed_at,
    updated_at=base.updated_at,
    stage_name=_opt_str(row, 'stage_name'),
    tags=_req_str(row, 'tags'),
    title_status=base.title_status,
  )


def _decode_blocker(row: sqlite3.Row) -> BlockerRecord:
  return BlockerRecord(
    id=_req_int(row, 'id'),
    goal_id=_opt_int(row, 'goal_id'),
    stage_id=_opt_int(row, 'stage_id'),
    task_id=_opt_int(row, 'task_id'),
    description=_req_str(row, 'description'),
    impact=_req_str(row, 'impact'),
    attempts=_req_str(row, 'attempts'),
    required=_req_str(row, 'required'),
    status=_req_blocker_status(row),
    opened_at=_req_int(row, 'opened_at'),
    resolved_at=_opt_int(row, 'resolved_at'),
    resolution=_req_str(row, 'resolution'),
    target_kind=_req_focus_kind(row, 'target_kind'),
    target_id=_req_int(row, 'target_id'),
  )


def _decode_evidence(row: sqlite3.Row) -> EvidenceRecord:
  return EvidenceRecord(
    id=_req_int(row, 'id'),
    goal_id=_opt_int(row, 'goal_id'),
    stage_id=_opt_int(row, 'stage_id'),
    task_id=_opt_int(row, 'task_id'),
    claim=_req_str(row, 'claim'),
    source=_req_str(row, 'source'),
    result=_req_str(row, 'result'),
    captured_at=_req_int(row, 'captured_at'),
    context_status=_req_record_context(row),
    claim_status=_req_claim_status(row),
    stage_generation=_opt_int(row, 'stage_generation'),
  )


def _decode_decision(row: sqlite3.Row) -> DecisionRecord:
  return DecisionRecord(
    id=_req_int(row, 'id'),
    goal_id=_opt_int(row, 'goal_id'),
    stage_id=_opt_int(row, 'stage_id'),
    task_id=_opt_int(row, 'task_id'),
    summary=_req_str(row, 'summary'),
    rationale=_req_str(row, 'rationale'),
    alternatives=_req_str(row, 'alternatives'),
    consequences=_req_str(row, 'consequences'),
    decided_at=_req_int(row, 'decided_at'),
    context_status=_req_record_context(row),
  )


def _decode_project_record(
  connection: sqlite3.Connection,
) -> ProjectRecord:
  row = connection.execute('SELECT * FROM project').fetchone()
  if row is None:
    raise ProjectError('Project database has no project record')
  status = _project_status(connection)
  return ProjectRecord(
    id=_req_int(row, 'id'),
    name=_req_str(row, 'name'),
    objective=_req_str(row, 'objective'),
    scope=_req_str(row, 'scope'),
    non_goals=_req_str(row, 'non_goals'),
    constraints_text=_req_str(row, 'constraints_text'),
    acceptance=_req_str(row, 'acceptance'),
    created_at=_req_int(row, 'created_at'),
    updated_at=_req_int(row, 'updated_at'),
    charter_context_status=_req_charter_context(row),
    status=status,
    completed_at=_project_completed_at(connection, status),
  )


def _decode_project_state(connection: sqlite3.Connection) -> ProjectState:
  row = connection.execute('SELECT * FROM project_state').fetchone()
  if row is None:
    raise ProjectError('Project state record does not exist')
  return ProjectState(
    id=_req_int(row, 'id'),
    summary=_req_str(row, 'summary'),
    next_action=_req_str(row, 'next_action'),
    updated_at=_req_int(row, 'updated_at'),
    revision=_req_int(row, 'revision'),
  )


def _read_goal_details(
  connection: sqlite3.Connection, goal_id: int
) -> GoalDetails:
  goal_row = connection.execute(
    'SELECT * FROM goal WHERE id = ?', (goal_id,)
  ).fetchone()
  if goal_row is None:
    raise ProjectError(f'Goal does not exist: {goal_id}')
  goal = _decode_goal_record(connection, goal_row)
  stages = tuple(
    GoalStageSummary(
      id=stage.id,
      name=stage.name,
      status=stage.status,
      outcome=stage.outcome,
    )
    for row in connection.execute(
      f"""
      SELECT s.*, {_STAGE_COUNTS_SQL}
      FROM goal_stage gs
      JOIN stage s ON s.id = gs.stage_id
      LEFT JOIN stage_achievement sa
        ON sa.stage_id = s.id AND sa.invalidated_at IS NULL
      LEFT JOIN task t ON t.stage_id = s.id
      WHERE gs.goal_id = ?
      GROUP BY s.id
      ORDER BY s.position, s.id
      """,
      (goal_id,),
    )
    for stage in (_decode_stage_from_summary(row),)
  )
  tasks = tuple(
    _decode_goal_task(row)
    for row in connection.execute(
      """
      SELECT t.*, s.name AS stage_name
      FROM task t
      LEFT JOIN stage s ON s.id = t.stage_id
      WHERE t.goal_id = ?
      ORDER BY t.priority DESC, t.id
      """,
      (goal_id,),
    ).fetchall()
  )
  blockers = tuple(
    _decode_blocker(row)
    for row in connection.execute(
      "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
      'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
      'FROM blocker WHERE goal_id = ? '
      'ORDER BY opened_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  )
  evidence = tuple(
    _decode_evidence(row)
    for row in connection.execute(
      'SELECT * FROM evidence WHERE goal_id = ? '
      'ORDER BY captured_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  )
  decisions = tuple(
    _decode_decision(row)
    for row in connection.execute(
      'SELECT * FROM decision WHERE goal_id = ? '
      'ORDER BY decided_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  )
  return GoalDetails(
    goal=goal,
    stages=stages,
    tasks=tasks,
    blockers=blockers,
    evidence=evidence,
    decisions=decisions,
  )


def read_project(connection: sqlite3.Connection, path: str) -> ProjectView:
  with _sqlite_boundary():
    project = _decode_project_record(connection)
    state = _decode_project_state(connection)
    active_goal_id = _active_goal_id(connection)
    goal = (
      _read_goal_details(connection, active_goal_id)
      if active_goal_id is not None
      else None
    )
    charter_history = tuple(
      CharterHistoryRecord(
        id=_req_int(row, 'id'),
        objective=_req_str(row, 'objective'),
        scope=_req_str(row, 'scope'),
        non_goals=_req_str(row, 'non_goals'),
        constraints_text=_req_str(row, 'constraints_text'),
        acceptance=_req_str(row, 'acceptance'),
        replaced_at=_req_int(row, 'replaced_at'),
      )
      for row in connection.execute(
        'SELECT * FROM project_charter_history '
        'ORDER BY replaced_at DESC, id DESC'
      )
    )
    return ProjectView(
      path=path,
      project=project,
      state=state,
      goal=goal,
      charter_history=charter_history,
    )


def read_project_summary(
  connection: sqlite3.Connection, path: str
) -> ProjectSummary:
  with _sqlite_boundary():
    project = _decode_project_record(connection)
    return ProjectSummary(
      name=project.name,
      status=project.status,
      objective=project.objective,
      updated_at=project.updated_at,
      path=path,
    )


def _apply_project_patch(
  connection: sqlite3.Connection, patch: ProjectPatch
) -> bool:
  selected: dict[str, str] = {}
  for field_name in (
    'objective',
    'scope',
    'non_goals',
    'constraints_text',
    'acceptance',
  ):
    value = getattr(patch, field_name)
    if isinstance(value, str):
      selected[field_name] = value
  if not selected:
    return False
  assignments = ', '.join(f'{field_name} = ?' for field_name in selected)
  try:
    connection.execute(
      f'UPDATE project SET {assignments} WHERE id = 1',
      list(selected.values()),
    )
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not update project: {error}') from error
  return True


def _apply_state_patch(
  connection: sqlite3.Connection, patch: ProjectStatePatch
) -> bool:
  selected: dict[str, str] = {}
  for field_name in ('summary', 'next_action'):
    value = getattr(patch, field_name)
    if isinstance(value, str):
      selected[field_name] = value
  if not selected:
    return False
  assignments = ', '.join(f'{field_name} = ?' for field_name in selected)
  connection.execute(
    f'UPDATE project_state SET {assignments} WHERE id = 1',
    list(selected.values()),
  )
  return True


def update_project_and_state(
  connection: sqlite3.Connection,
  project_patch: ProjectPatch,
  state_patch: ProjectStatePatch,
) -> None:
  with _sqlite_boundary():
    with connection:
      project_changed = _apply_project_patch(connection, project_patch)
      state_changed = _apply_state_patch(connection, state_patch)
      if project_changed or state_changed:
        _touch(connection, connection_time(connection))


def create_goal(
  connection: sqlite3.Connection, text: GoalText, stages: GoalStages
) -> int:
  with _sqlite_boundary():
    with connection:
      stage_ids = [
        _resolve_stage(connection, reference)
        for reference in stages.references
      ]
      if len(stage_ids) != len(set(stage_ids)):
        raise ProjectError(
          'A goal cannot link the same stage more than once'
        )
      timestamp = connection_time(connection)
      cursor = connection.execute(
        """
        INSERT INTO goal
          (text, status, started_at, created_at, updated_at)
        VALUES (?, 'cancelled', 0, ?, ?)
        """,
        (text.value, timestamp, timestamp),
      )
      goal_id = cursor.lastrowid
      if goal_id is None:
        raise ProjectError('Goal insertion did not return an identifier')
      connection.executemany(
        'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
        ((goal_id, stage_id) for stage_id in stage_ids),
      )
      _activate_goal(connection, goal_id, timestamp, ('cancelled',))
      return goal_id


def activate_goal(
  connection: sqlite3.Connection, reference: GoalReference
) -> None:
  with _sqlite_boundary():
    with connection:
      goal_id = _resolve_goal(connection, reference)
      timestamp = connection_time(connection)
      _activate_goal(connection, goal_id, timestamp, ('pending',))


def reopen_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
) -> None:
  with _sqlite_boundary():
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal is None:
        raise ProjectError(f'Goal does not exist: {goal_id}')
      status = _req_goal_status(goal)
      if status != 'blocked':
        raise ProjectError(
          f'Only blocked goals can be reopened; goal {goal_id} is {status}'
        )
      if connection.execute(
        'SELECT 1 FROM blocker '
        'WHERE goal_id = ? AND task_id IS NULL '
        "AND status = 'open' LIMIT 1",
        (goal_id,),
      ).fetchone():
        raise ProjectError(
          'A goal cannot reopen while it has open blockers'
        )
      timestamp = connection_time(connection)
      _activate_goal(connection, goal_id, timestamp, ('blocked',))


def read_goals(
  connection: sqlite3.Connection, status: GoalStatus | None = None
) -> tuple[GoalListItem, ...]:
  if status is not None and status not in GOAL_STATUSES:
    raise ProjectError(f'Invalid goal status: {status}')
  with _sqlite_boundary():
    condition = 'WHERE g.status = ?' if status else ''
    parameters = (status,) if status else ()
    rows = connection.execute(
      f"""
      SELECT g.*,
        CASE WHEN g.status = 'active' THEN 1 ELSE 0 END AS is_active,
        COALESCE((
          SELECT GROUP_CONCAT(s.name, ', ' ORDER BY s.position, s.id)
          FROM goal_stage gs
          JOIN stage s ON s.id = gs.stage_id
          WHERE gs.goal_id = g.id
        ), '') AS stage_names
      FROM goal g
      {condition}
      ORDER BY g.id DESC
      """,
      parameters,
    ).fetchall()
    return tuple(_decode_goal_list_item(connection, row) for row in rows)


def read_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
) -> GoalDetails:
  with _sqlite_boundary():
    return _read_goal_details(
      connection, _resolve_goal(connection, reference)
    )


def goal_text(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
) -> str:
  with _sqlite_boundary():
    goal_id = _resolve_goal(connection, reference)
    row = connection.execute(
      'SELECT text FROM goal WHERE id = ?', (goal_id,)
    ).fetchone()
    if row is None:
      raise ProjectError(f'Goal does not exist: {goal_id}')
    return _req_str(row, 'text')


def achieve_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
) -> None:
  with _sqlite_boundary():
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal is None:
        raise ProjectError(f'Goal does not exist: {goal_id}')
      status = _req_goal_status(goal)
      if status != 'active':
        raise ProjectError(
          f'Only active goals can be achieved; goal {goal_id} is {status}'
        )
      if connection.execute(
        'SELECT 1 FROM blocker '
        'WHERE goal_id = ? AND task_id IS NULL '
        "AND status = 'open' LIMIT 1",
        (goal_id,),
      ).fetchone():
        raise ProjectError(
          'Achieving a goal requires all goal blockers to be resolved'
        )
      if (
        connection.execute(
          'SELECT 1 FROM evidence '
          "WHERE goal_id = ? AND claim_status = 'substantive' "
          'AND substantive(claim) LIMIT 1',
          (goal_id,),
        ).fetchone()
        is None
      ):
        raise ProjectError(
          'Achieving a goal requires at least one goal-linked '
          'evidence entry'
        )
      _ensure_no_active_task(connection, 'Achieving a goal')
      timestamp = connection_time(connection)
      connection.execute(
        """
        UPDATE goal
        SET status = 'achieved', achieved_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, goal_id),
      )
      _touch(connection, timestamp)


def cancel_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
  reason: str = '',
) -> None:
  with _sqlite_boundary():
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal is None:
        raise ProjectError(f'Goal does not exist: {goal_id}')
      status = _req_goal_status(goal)
      if status not in ('active', 'pending', 'blocked'):
        raise ProjectError(
          'Only active, pending, or blocked goals can be cancelled; '
          f'goal {goal_id} is {status}'
        )
      _ensure_no_active_task(connection, 'Cancelling a goal', goal_id)
      timestamp = connection_time(connection)
      connection.execute(
        """
        UPDATE blocker
        SET status = 'withdrawn', resolved_at = ?, resolution = ?
        WHERE goal_id = ? AND task_id IS NULL AND status = 'open'
        """,
        (timestamp, reason or 'Goal cancelled', goal_id),
      )
      connection.execute(
        """
        UPDATE goal
        SET status = 'cancelled', status_reason = ?, achieved_at = NULL,
          updated_at = ?
        WHERE id = ?
        """,
        (reason, timestamp, goal_id),
      )
      _touch(connection, timestamp)


def block_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None,
  description: SubstantiveText,
  *,
  required: SubstantiveText,
  impact: str = '',
  attempts: str = '',
) -> int:
  with _sqlite_boundary():
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal is None:
        raise ProjectError(f'Goal does not exist: {goal_id}')
      status = _req_goal_status(goal)
      if status != 'active':
        raise ProjectError(
          f'Only active goals can be blocked; goal {goal_id} is {status}'
        )
      _ensure_no_active_task(connection, 'Blocking a goal', goal_id)
      timestamp = connection_time(connection)
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, description, impact, attempts, required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          description.value,
          impact,
          attempts,
          required.value,
          timestamp,
        ),
      )
      connection.execute(
        """
        UPDATE goal
        SET status = 'blocked', status_reason = ?, updated_at = ?
        WHERE id = ?
        """,
        (description.value, timestamp, goal_id),
      )
      _touch(connection, timestamp)
      return _inserted_id(cursor, 'Blocker')


def add_stage(
  connection: sqlite3.Connection,
  name: SubstantiveText,
  outcome: SubstantiveText,
  *,
  purpose: str = '',
  entry_conditions: str = '',
  exit_evidence: str = '',
) -> int:
  with _sqlite_boundary():
    try:
      with connection:
        pos_row = connection.execute(
          'SELECT COALESCE(MAX(position), -1) + 1 FROM stage'
        ).fetchone()
        position = pos_row[0] if pos_row is not None else 0
        timestamp = connection_time(connection)
        cursor = connection.execute(
          """
          INSERT INTO stage
            (name, outcome, purpose, entry_conditions, exit_evidence,
             position, created_at, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            name.value,
            outcome.value,
            purpose,
            entry_conditions,
            exit_evidence,
            position,
            timestamp,
            timestamp,
          ),
        )
        _touch(connection, timestamp)
        return _inserted_id(cursor, 'Stage')
    except sqlite3.IntegrityError as error:
      raise ProjectError(f'Could not add stage: {error}') from error


def read_stages(
  connection: sqlite3.Connection,
) -> tuple[StageListItem, ...]:
  with _sqlite_boundary():
    rows = connection.execute(
      f"""
      SELECT s.*, {_STAGE_COUNTS_SQL},
        COALESCE((
          SELECT GROUP_CONCAT(d.name, ', ' ORDER BY d.position, d.id)
          FROM stage_dependency sd
          JOIN stage d ON d.id = sd.dependency_id
          WHERE sd.stage_id = s.id
        ), '') AS dependencies
      FROM stage s
      LEFT JOIN stage_achievement sa
        ON sa.stage_id = s.id AND sa.invalidated_at IS NULL
      LEFT JOIN task t ON t.stage_id = s.id
      GROUP BY s.id
      ORDER BY s.position, s.id
      """
    ).fetchall()
    return tuple(
      StageListItem(
        id=stage.id,
        name=stage.name,
        outcome=stage.outcome,
        purpose=stage.purpose,
        entry_conditions=stage.entry_conditions,
        exit_evidence=stage.exit_evidence,
        position=stage.position,
        achievement_generation=stage.achievement_generation,
        achievement_generation_started_at=(
          stage.achievement_generation_started_at
        ),
        created_at=stage.created_at,
        updated_at=stage.updated_at,
        status=stage.status,
        started_at=stage.started_at,
        achieved_at=stage.achieved_at,
        achievement_evidence_id=stage.achievement_evidence_id,
        dependencies=_req_str(row, 'dependencies'),
      )
      for row in rows
      for stage in (_decode_stage_from_summary(row),)
    )


def update_stage(
  connection: sqlite3.Connection,
  reference: StageReference,
  patch: StagePatch,
) -> None:
  selected: dict[str, str] = {}
  if isinstance(patch.name, SubstantiveText):
    selected['name'] = patch.name.value
  if isinstance(patch.outcome, SubstantiveText):
    selected['outcome'] = patch.outcome.value
  for field_name in ('purpose', 'entry_conditions', 'exit_evidence'):
    value = getattr(patch, field_name)
    if isinstance(value, str):
      selected[field_name] = value

  with _sqlite_boundary():
    with connection:
      stage_id = _resolve_stage(connection, reference)
      if not selected:
        return
      timestamp = connection_time(connection)
      assignments = ', '.join(
        f'{field_name} = ?' for field_name in selected
      )
      parameters = [*selected.values(), timestamp, stage_id]
      try:
        connection.execute(
          f'UPDATE stage SET {assignments}, updated_at = ? WHERE id = ?',
          parameters,
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not update stage: {error}') from error
      _touch(connection, timestamp)


def achieve_stage(
  connection: sqlite3.Connection,
  reference: StageReference,
  evidence_id: PositiveInt,
) -> None:
  with _sqlite_boundary():
    with connection:
      stage_id = _resolve_stage(connection, reference)
      resolved_evidence_id = _resolve_evidence_id(
        connection, evidence_id.value
      )
      status = _stage_status(connection, stage_id)
      if status == 'achieved':
        raise ProjectError(f'Stage {stage_id} is already achieved')
      gen_row = connection.execute(
        'SELECT achievement_generation FROM stage WHERE id = ?',
        (stage_id,),
      ).fetchone()
      if gen_row is None:
        raise ProjectError(f'Stage does not exist: {stage_id}')
      generation = _req_int(gen_row, 'achievement_generation')
      timestamp = connection_time(connection)
      try:
        connection.execute(
          """
          INSERT INTO stage_achievement
            (stage_id, evidence_id, achieved_at, stage_generation)
          VALUES (?, ?, ?, ?)
          """,
          (stage_id, resolved_evidence_id, timestamp, generation),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not achieve stage: {error}') from error
      connection.execute(
        'UPDATE stage SET updated_at = ? WHERE id = ?',
        (timestamp, stage_id),
      )
      _touch(connection, timestamp)


def add_stage_dependency(
  connection: sqlite3.Connection,
  reference: StageReference,
  dependency: StageReference,
) -> None:
  with _sqlite_boundary():
    with connection:
      stage_id = _resolve_stage(connection, reference)
      dependency_id = _resolve_stage(connection, dependency)
      cycle = connection.execute(
        """
        WITH RECURSIVE dependencies(id) AS (
          SELECT dependency_id
          FROM stage_dependency
          WHERE stage_id = ?
          UNION
          SELECT stage_dependency.dependency_id
          FROM stage_dependency
          JOIN dependencies ON dependencies.id = stage_dependency.stage_id
        )
        SELECT 1 FROM dependencies WHERE id = ? LIMIT 1
        """,
        (dependency_id, stage_id),
      ).fetchone()
      if cycle is not None:
        raise ProjectError('Stage dependency would create a cycle')
      try:
        connection.execute(
          'INSERT INTO stage_dependency '
          '(stage_id, dependency_id) VALUES (?, ?)',
          (stage_id, dependency_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(
          f'Could not add stage dependency: {error}'
        ) from error
      _touch(connection, connection_time(connection))


def remove_stage_dependency(
  connection: sqlite3.Connection,
  reference: StageReference,
  dependency: StageReference,
) -> None:
  with _sqlite_boundary():
    with connection:
      stage_id = _resolve_stage(connection, reference)
      dependency_id = _resolve_stage(connection, dependency)
      exists = connection.execute(
        'SELECT 1 FROM stage_dependency '
        'WHERE stage_id = ? AND dependency_id = ?',
        (stage_id, dependency_id),
      ).fetchone()
      if exists is None:
        raise ProjectError(
          f'Stage {stage_id} does not depend on stage {dependency_id}'
        )
      try:
        connection.execute(
          'DELETE FROM stage_dependency '
          'WHERE stage_id = ? AND dependency_id = ?',
          (stage_id, dependency_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(
          f'Could not remove stage dependency: {error}'
        ) from error
      _touch(connection, connection_time(connection))


def _insert_tag(
  connection: sqlite3.Connection, task_id: int, tag: TaskTag
) -> None:
  connection.execute(
    'INSERT OR IGNORE INTO task_tag (task_id, tag) VALUES (?, ?)',
    (task_id, tag.value),
  )


def _validated_tags(tags: Sequence[TaskTag]) -> tuple[TaskTag, ...]:
  if isinstance(tags, str) or any(
    not isinstance(tag, TaskTag) for tag in tags
  ):
    raise ProjectError('Task tags must be TaskTag values')
  return tuple(tags)


def add_task(
  connection: sqlite3.Connection,
  title: SubstantiveText,
  *,
  purpose: str = '',
  stage: StageReference | None = None,
  priority: int = 0,
  tags: Sequence[TaskTag] = (),
  goal: GoalReference | None = None,
  scope: str = '',
  exclusions: str = '',
  result: str = '',
  completion_evidence: str = '',
) -> int:
  if isinstance(priority, bool):
    raise ProjectError('Task priority must be an integer')
  validated_tags = _validated_tags(tags)
  with _sqlite_boundary():
    try:
      with connection:
        stage_id = _resolve_optional_stage(connection, stage)
        goal_id = (
          _resolve_goal(connection, goal) if goal is not None else None
        )
        _ensure_goal_stage(connection, goal_id, stage_id, 'Task')
        timestamp = connection_time(connection)
        cursor = connection.execute(
          """
          INSERT INTO task
            (goal_id, stage_id, title, purpose, scope, exclusions, result,
             completion_evidence, priority, created_at, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
            goal_id,
            stage_id,
            title.value,
            purpose,
            scope,
            exclusions,
            result,
            completion_evidence,
            priority,
            timestamp,
            timestamp,
          ),
        )
        task_id = _inserted_id(cursor, 'Task')
        for tag in validated_tags:
          _insert_tag(connection, task_id, tag)
        _touch(connection, timestamp)
        return task_id
    except sqlite3.IntegrityError as error:
      raise ProjectError(f'Could not add task: {error}') from error


def _ready_tasks(
  connection: sqlite3.Connection, tasks: tuple[TaskRecord, ...]
) -> tuple[TaskRecord, ...]:
  pending_documented = tuple(
    task
    for task in tasks
    if task.status == 'pending'
    and task.stage_id is not None
    and is_substantive(task.title)
    and is_substantive(task.purpose)
    and is_substantive(task.scope)
    and is_substantive(task.exclusions)
    and is_substantive(task.result)
    and is_substantive(task.completion_evidence)
  )
  if not pending_documented or not _is_project_chartered(connection):
    return ()
  active_goal_id = _active_goal_id(connection)
  open_blocked_ids = {
    _req_int(row, 'task_id')
    for row in connection.execute(
      'SELECT DISTINCT task_id FROM blocker '
      "WHERE task_id IS NOT NULL AND status = 'open'"
    )
  }
  complete_stage_ids = {
    _req_int(row, 'id')
    for row in connection.execute(
      'SELECT id FROM stage '
      'WHERE substantive(name) AND substantive(outcome)'
    )
  }
  goal_stage_pairs = {
    (_req_int(row, 'goal_id'), _req_int(row, 'stage_id'))
    for row in connection.execute(
      'SELECT goal_id, stage_id FROM goal_stage'
    )
  }
  unachieved_dep_stages = {
    _req_int(row, 'stage_id')
    for row in connection.execute(
      """
      SELECT DISTINCT sd.stage_id
      FROM stage_dependency sd
      LEFT JOIN stage_achievement sa
        ON sa.stage_id = sd.dependency_id AND sa.invalidated_at IS NULL
      WHERE sa.id IS NULL
      """
    )
  }
  return tuple(
    task
    for task in pending_documented
    if task.id not in open_blocked_ids
    and task.stage_id in complete_stage_ids
    and task.stage_id not in unachieved_dep_stages
    and (
      task.goal_id is None
      or (
        task.goal_id == active_goal_id
        and (task.goal_id, task.stage_id) in goal_stage_pairs
      )
    )
  )


def read_tasks(
  connection: sqlite3.Connection,
  *,
  status: TaskStatus | None = None,
  stage: StageReference | None = None,
  tag: str | None = None,
  ready: bool = False,
) -> tuple[TaskRecord, ...]:
  if status is not None and status not in TASK_STATUSES:
    raise ProjectError(f'Invalid task status: {status}')
  with _sqlite_boundary():
    clauses: list[str] = []
    parameters: list[object] = []
    if status:
      clauses.append('t.status = ?')
      parameters.append(status)
    if stage is not None:
      clauses.append('t.stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if tag is not None:
      stripped_tag = tag.strip()
      if not stripped_tag:
        return ()
      clauses.append(
        'EXISTS (SELECT 1 FROM task_tag '
        'tt_filter WHERE tt_filter.task_id = t.id '
        'AND tt_filter.tag = ?)'
      )
      parameters.append(stripped_tag)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    tasks = tuple(
      _decode_task(row)
      for row in connection.execute(
        f"""
        SELECT t.*, s.name AS stage_name,
          COALESCE(
            (SELECT GROUP_CONCAT(tag, ', ' ORDER BY tag) FROM task_tag
             WHERE task_id = t.id),
            ''
          ) AS tags
        FROM task t
        LEFT JOIN stage s ON s.id = t.stage_id
        {where}
        ORDER BY t.priority DESC, t.id
        """,
        parameters,
      ).fetchall()
    )
    if ready:
      return _ready_tasks(connection, tasks)
    return tasks


def _query_task_logs(
  connection: sqlite3.Connection,
  task_id: int,
  *,
  limit: PositiveInt,
  since: int | None,
) -> tuple[TaskLogRecord, ...]:
  parameters: list[object] = [task_id]
  condition = ''
  if since is not None:
    condition = ' AND occurred_at >= ?'
    parameters.append(since)
  parameters.append(limit.value)
  rows = connection.execute(
    'SELECT * FROM task_log WHERE task_id = ?'
    f'{condition} ORDER BY occurred_at DESC, id DESC LIMIT ?',
    parameters,
  ).fetchall()
  return tuple(
    TaskLogRecord(
      id=_req_int(row, 'id'),
      task_id=_req_int(row, 'task_id'),
      occurred_at=_req_int(row, 'occurred_at'),
      kind=_req_str(row, 'kind'),
      message=_req_str(row, 'message'),
    )
    for row in reversed(rows)
  )


def read_task_logs(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  *,
  limit: PositiveInt = _DEFAULT_LOG_LIMIT,
  since: int | None = None,
) -> tuple[TaskLogRecord, ...]:
  if isinstance(since, bool):
    raise ProjectError('Log timestamp filter must be an integer')
  with _sqlite_boundary():
    resolved_task_id = _resolve_task_id(connection, task_id.value)
    return _query_task_logs(
      connection, resolved_task_id, limit=limit, since=since
    )


def read_task(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  *,
  limit: PositiveInt = _DEFAULT_LOG_LIMIT,
  since: int | None = None,
) -> TaskDetails:
  if isinstance(since, bool):
    raise ProjectError('Log timestamp filter must be an integer')
  with _sqlite_boundary():
    row = connection.execute(
      """
      SELECT t.*, s.name AS stage_name,
        COALESCE(
          (SELECT GROUP_CONCAT(tag, ', ' ORDER BY tag) FROM task_tag
           WHERE task_id = t.id),
          ''
        ) AS tags
      FROM task t
      LEFT JOIN stage s ON s.id = t.stage_id
      WHERE t.id = ?
      """,
      (task_id.value,),
    ).fetchone()
    if row is None:
      raise ProjectError(f'Task does not exist: {task_id.value}')
    task = _decode_task(row)
    logs = _query_task_logs(connection, task.id, limit=limit, since=since)
    return TaskDetails(task=task, logs=logs)


def update_task(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  patch: TaskPatch,
) -> None:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      selected: dict[str, object] = {}
      if isinstance(patch.title, SubstantiveText):
        selected['title'] = patch.title.value
      for field_name in (
        'purpose',
        'scope',
        'exclusions',
        'result',
        'completion_evidence',
      ):
        value = getattr(patch, field_name)
        if isinstance(value, str):
          selected[field_name] = value
      if patch.priority is not UNSET and isinstance(patch.priority, int):
        selected['priority'] = patch.priority
      if patch.stage_id is None or isinstance(
        patch.stage_id, (PositiveInt, StageName)
      ):
        selected['stage_id'] = _resolve_optional_stage(
          connection, patch.stage_id
        )
      if patch.goal_id is None:
        selected['goal_id'] = None
      elif patch.goal_id == 'active':
        selected['goal_id'] = _resolve_goal(connection, 'active')
      elif isinstance(patch.goal_id, PositiveInt):
        selected['goal_id'] = _resolve_goal(connection, patch.goal_id)
      if not selected:
        return
      task_row = connection.execute(
        'SELECT * FROM task WHERE id = ?', (resolved_task_id,)
      ).fetchone()
      if task_row is None:
        raise ProjectError(f'Task does not exist: {resolved_task_id}')
      raw_stage = selected.get('stage_id', _opt_int(task_row, 'stage_id'))
      raw_goal = selected.get('goal_id', _opt_int(task_row, 'goal_id'))
      target_stage = raw_stage if isinstance(raw_stage, int) else None
      target_goal = raw_goal if isinstance(raw_goal, int) else None
      _ensure_goal_stage(connection, target_goal, target_stage, 'Task')
      if _req_task_status(task_row) == 'active':
        _ensure_task_goal_is_active(connection, target_goal)
        _ensure_task_dependencies_are_achieved(connection, target_stage)
      timestamp = connection_time(connection)
      assignments = ', '.join(
        f'{field_name} = ?' for field_name in selected
      )
      parameters = [*selected.values(), timestamp, resolved_task_id]
      try:
        connection.execute(
          f'UPDATE task SET {assignments}, updated_at = ? WHERE id = ?',
          parameters,
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not update task: {error}') from error
      _touch(connection, timestamp)


def append_task_log(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  message: str,
  *,
  kind: str = 'note',
) -> None:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      timestamp = connection_time(connection)
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (resolved_task_id, timestamp, kind, message),
      )
      connection.execute(
        'UPDATE task SET updated_at = ? WHERE id = ?',
        (timestamp, resolved_task_id),
      )
      _touch(connection, timestamp)


def _ensure_task_can_start(
  connection: sqlite3.Connection, task_id: int
) -> sqlite3.Row:
  task = connection.execute(
    'SELECT * FROM task WHERE id = ?', (task_id,)
  ).fetchone()
  if task is None:
    raise ProjectError(f'Task does not exist: {task_id}')
  status = _req_task_status(task)
  if status != 'pending':
    raise ProjectError(
      f'Only pending tasks can start; task {task_id} is {status}'
    )
  _ensure_project_chartered(connection)
  _ensure_task_documented(task)
  stage_id = _opt_int(task, 'stage_id')
  if stage_id is None:
    raise ProjectError('Starting a task requires a stage relationship')
  _ensure_stage_contract(connection, stage_id)
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open' LIMIT 1",
    (task_id,),
  ).fetchone():
    raise ProjectError('Cannot start a task with open blockers')
  goal_id = _opt_int(task, 'goal_id')
  _ensure_goal_stage(connection, goal_id, stage_id, 'Task')
  _ensure_task_goal_is_active(connection, goal_id)
  _ensure_task_dependencies_are_achieved(connection, stage_id)
  return task


def start_task(
  connection: sqlite3.Connection, task_id: PositiveInt
) -> None:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      _ensure_task_can_start(connection, resolved_task_id)
      timestamp = connection_time(connection)
      active_task = _active_task_row(connection)
      if active_task is not None:
        _return_task_to_pending(
          connection,
          _req_int(active_task, 'id'),
          timestamp,
          'Task returned to pending while activating task '
          f'{resolved_task_id}',
        )
      try:
        connection.execute(
          """
          UPDATE task
          SET status = 'active', started_at = COALESCE(started_at, ?),
            completed_at = NULL, updated_at = ?
          WHERE id = ?
          """,
          (timestamp, timestamp, resolved_task_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not start task: {error}') from error
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (resolved_task_id, timestamp, 'started', 'Task started'),
      )
      _touch(connection, timestamp)


def complete_task(
  connection: sqlite3.Connection, task_id: PositiveInt
) -> None:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?', (resolved_task_id,)
      ).fetchone()
      if task is None:
        raise ProjectError(f'Task does not exist: {resolved_task_id}')
      status = _req_task_status(task)
      if status != 'active':
        raise ProjectError(
          f'Only the active task can complete; task {resolved_task_id} is '
          f'{status}'
        )
      timestamp = connection_time(connection)
      connection.execute(
        """
        UPDATE task
        SET status = 'completed', completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, resolved_task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (resolved_task_id, timestamp, 'completed', 'Task completed'),
      )
      _touch(connection, timestamp)


def reopen_task(
  connection: sqlite3.Connection, task_id: PositiveInt
) -> None:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?', (resolved_task_id,)
      ).fetchone()
      if task is None:
        raise ProjectError(f'Task does not exist: {resolved_task_id}')
      status = _req_task_status(task)
      if status not in ('completed', 'cancelled'):
        raise ProjectError(
          f'Only completed or cancelled tasks can reopen; task '
          f'{resolved_task_id} is {status}'
        )
      timestamp = connection_time(connection)
      connection.execute(
        """
        UPDATE task
        SET status = 'pending', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, resolved_task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (resolved_task_id, timestamp, 'reopened', 'Task reopened'),
      )
      _touch(connection, timestamp)


def cancel_task(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  *,
  reason: str = '',
) -> None:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?', (resolved_task_id,)
      ).fetchone()
      if task is None:
        raise ProjectError(f'Task does not exist: {resolved_task_id}')
      status = _req_task_status(task)
      if status not in ('pending', 'active', 'blocked'):
        raise ProjectError(
          'Only pending, active, or blocked tasks can be cancelled; '
          f'task {resolved_task_id} is {status}'
        )
      timestamp = connection_time(connection)
      connection.execute(
        """
        UPDATE blocker
        SET status = 'withdrawn', resolved_at = ?, resolution = ?
        WHERE task_id = ? AND status = 'open'
        """,
        (timestamp, reason or 'Task cancelled', resolved_task_id),
      )
      connection.execute(
        """
        UPDATE task
        SET status = 'cancelled', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, resolved_task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (
          resolved_task_id,
          timestamp,
          'cancelled',
          reason or 'Task cancelled',
        ),
      )
      _touch(connection, timestamp)


def block_task(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  description: SubstantiveText,
  *,
  required: SubstantiveText,
  impact: str = '',
  attempts: str = '',
) -> int:
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      task = connection.execute(
        'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
        (resolved_task_id,),
      ).fetchone()
      if task is None:
        raise ProjectError(f'Task does not exist: {resolved_task_id}')
      status = _req_task_status(task)
      if status not in ('pending', 'active'):
        raise ProjectError(
          f'Only pending or active tasks can be blocked; task '
          f'{resolved_task_id} is {status}'
        )
      timestamp = connection_time(connection)
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, stage_id, task_id, description, impact, attempts,
           required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          _opt_int(task, 'goal_id'),
          _opt_int(task, 'stage_id'),
          resolved_task_id,
          description.value,
          impact,
          attempts,
          required.value,
          timestamp,
        ),
      )
      connection.execute(
        """
        UPDATE task
        SET status = 'blocked', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, resolved_task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (resolved_task_id, timestamp, 'blocked', description.value),
      )
      _touch(connection, timestamp)
      return _inserted_id(cursor, 'Blocker')


def add_task_tags(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  tags: Sequence[TaskTag],
) -> None:
  validated_tags = _validated_tags(tags)
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      for tag in validated_tags:
        _insert_tag(connection, resolved_task_id, tag)
      _touch(connection, connection_time(connection))


def remove_task_tags(
  connection: sqlite3.Connection,
  task_id: PositiveInt,
  tags: Sequence[TaskTag],
) -> None:
  validated_tags = _validated_tags(tags)
  with _sqlite_boundary():
    with connection:
      resolved_task_id = _resolve_task_id(connection, task_id.value)
      for tag in validated_tags:
        connection.execute(
          'DELETE FROM task_tag WHERE task_id = ? AND tag = ?',
          (resolved_task_id, tag.value),
        )
      _touch(connection, connection_time(connection))


def add_decision(
  connection: sqlite3.Connection,
  summary: SubstantiveText,
  *,
  rationale: str = '',
  alternatives: str = '',
  consequences: str = '',
  stage: StageReference | None = None,
  task: PositiveInt | None = None,
  goal: GoalReference | None = None,
) -> int:
  if not isinstance(summary, SubstantiveText):
    raise ProjectError('Decision summary must contain non-whitespace text')
  with _sqlite_boundary():
    with connection:
      stage_id, task_id, goal_id = _resolve_record_relationships(
        connection, 'Decision', stage, task, goal
      )
      timestamp = connection_time(connection)
      cursor = connection.execute(
        """
        INSERT INTO decision
          (goal_id, stage_id, task_id, summary, rationale, alternatives,
           consequences, decided_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          summary.value,
          rationale,
          alternatives,
          consequences,
          timestamp,
        ),
      )
      _touch(connection, timestamp)
      return _inserted_id(cursor, 'Decision')


def _build_record_filter_sql(
  connection: sqlite3.Connection, filters: RecordListFilter
) -> tuple[str, list[object]]:
  clauses: list[str] = []
  parameters: list[object] = []
  if filters.no_task:
    clauses.append('task_id IS NULL')
  if filters.stage is not None:
    clauses.append('stage_id = ?')
    parameters.append(_resolve_stage(connection, filters.stage))
  if filters.task is not None:
    clauses.append('task_id = ?')
    parameters.append(_resolve_task_id(connection, filters.task.value))
  if filters.goal is not None:
    clauses.append('goal_id = ?')
    parameters.append(_resolve_goal(connection, filters.goal))
  where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
  parameters.append(filters.limit.value)
  return where, parameters


def read_decisions(
  connection: sqlite3.Connection, filters: RecordListFilter
) -> tuple[DecisionRecord, ...]:
  with _sqlite_boundary():
    where, parameters = _build_record_filter_sql(connection, filters)
    rows = connection.execute(
      f'SELECT * FROM decision {where} '
      'ORDER BY decided_at DESC, id DESC LIMIT ?',
      parameters,
    ).fetchall()
    return tuple(_decode_decision(row) for row in rows)


def add_blocker(
  connection: sqlite3.Connection,
  description: SubstantiveText,
  *,
  required: SubstantiveText,
  impact: str = '',
  attempts: str = '',
  stage: StageReference | None = None,
  task: PositiveInt | None = None,
  goal: GoalReference | None = None,
) -> int:
  with _sqlite_boundary():
    with connection:
      stage_id = _resolve_optional_stage(connection, stage)
      task_id = _resolve_task_id(connection, task.value) if task else None
      goal_id = (
        _resolve_goal(connection, goal) if goal is not None else None
      )
      task_status: TaskStatus | None = None
      if task_id is not None:
        task_row = connection.execute(
          'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
          (task_id,),
        ).fetchone()
        if task_row is None:
          raise ProjectError(f'Task does not exist: {task_id}')
        task_status = _req_task_status(task_row)
        if task_status in ('completed', 'cancelled'):
          raise ProjectError(
            f'Cannot block task {task_id} in status {task_status}'
          )
        task_goal_id = _opt_int(task_row, 'goal_id')
        task_stage_id = _opt_int(task_row, 'stage_id')
        if goal_id is None:
          goal_id = task_goal_id
        elif task_goal_id != goal_id:
          raise ProjectError('Blocker goal does not match task goal')
        if stage_id is None:
          stage_id = task_stage_id
        elif task_stage_id != stage_id:
          raise ProjectError('Blocker stage does not match task stage')
      elif goal_id is None:
        raise ProjectError('A blocker must target a task or goal')
      _ensure_goal_stage(connection, goal_id, stage_id, 'Blocker')
      if goal_id is not None and task_id is None:
        goal_row = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()
        if goal_row is None:
          raise ProjectError(f'Goal does not exist: {goal_id}')
        goal_status = _req_goal_status(goal_row)
        if goal_status not in ('active', 'blocked'):
          raise ProjectError(
            'Only active or blocked goals can receive blockers; '
            f'goal {goal_id} is {goal_status}'
          )
        _ensure_no_active_task(connection, 'Blocking a goal', goal_id)
      timestamp = connection_time(connection)
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, stage_id, task_id, description, impact, attempts,
           required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          description.value,
          impact,
          attempts,
          required.value,
          timestamp,
        ),
      )
      if task_status is not None and task_status != 'blocked':
        connection.execute(
          """
          UPDATE task
          SET status = 'blocked', completed_at = NULL, updated_at = ?
          WHERE id = ?
          """,
          (timestamp, task_id),
        )
        connection.execute(
          'INSERT INTO task_log '
          '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
          (task_id, timestamp, 'blocked', description.value),
        )
      if task_id is None:
        connection.execute(
          """
          UPDATE goal
          SET status = 'blocked', status_reason = ?, updated_at = ?
          WHERE id = ?
          """,
          (description.value, timestamp, goal_id),
        )
      _touch(connection, timestamp)
      return _inserted_id(cursor, 'Blocker')


def read_blockers(
  connection: sqlite3.Connection, status: BlockerFilterStatus = 'open'
) -> tuple[BlockerRecord, ...]:
  if status != 'all' and status not in BLOCKER_STATUSES:
    raise ProjectError(f'Invalid blocker status: {status}')
  with _sqlite_boundary():
    if status == 'all':
      rows = connection.execute(
        "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
        'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
        'FROM blocker ORDER BY opened_at DESC, id DESC'
      ).fetchall()
    else:
      rows = connection.execute(
        "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
        'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
        'FROM blocker WHERE status = ? '
        'ORDER BY opened_at DESC, id DESC',
        (status,),
      ).fetchall()
    return tuple(_decode_blocker(row) for row in rows)


def resolve_blocker(
  connection: sqlite3.Connection,
  blocker_id: PositiveInt,
  resolution: SubstantiveText,
) -> None:
  with _sqlite_boundary():
    with connection:
      blocker = connection.execute(
        """
        SELECT goal_id, task_id
        FROM blocker
        WHERE id = ? AND status = 'open'
        """,
        (blocker_id.value,),
      ).fetchone()
      if blocker is None:
        raise ProjectError(
          f'Open blocker does not exist: {blocker_id.value}'
        )
      blocker_task_id = _opt_int(blocker, 'task_id')
      blocker_goal_id = _opt_int(blocker, 'goal_id')
      task_was_blocked = False
      if blocker_task_id is not None:
        task_row = connection.execute(
          'SELECT status FROM task WHERE id = ?', (blocker_task_id,)
        ).fetchone()
        task_was_blocked = (
          task_row is not None and _req_task_status(task_row) == 'blocked'
        )
      remaining_goal: sqlite3.Row | None = None
      goal_to_reactivate: int | None = None
      if blocker_task_id is None and blocker_goal_id is not None:
        remaining_goal = connection.execute(
          """
          SELECT description FROM blocker
          WHERE goal_id = ? AND task_id IS NULL
            AND status = 'open' AND id <> ?
          ORDER BY opened_at DESC, id DESC LIMIT 1
          """,
          (blocker_goal_id, blocker_id.value),
        ).fetchone()
        goal_row = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker_goal_id,)
        ).fetchone()
        if (
          remaining_goal is None
          and goal_row is not None
          and _req_goal_status(goal_row) == 'blocked'
        ):
          goal_to_reactivate = blocker_goal_id
      timestamp = connection_time(connection)
      if goal_to_reactivate is not None:
        _handoff_active_goal(connection, goal_to_reactivate, timestamp)
      connection.execute(
        """
        UPDATE blocker
        SET status = 'resolved', resolved_at = ?, resolution = ?
        WHERE id = ?
        """,
        (timestamp, resolution.value, blocker_id.value),
      )
      if blocker_task_id is not None:
        connection.execute(
          'UPDATE task SET updated_at = ? WHERE id = ?',
          (timestamp, blocker_task_id),
        )
        connection.execute(
          'INSERT INTO task_log '
          '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
          (
            blocker_task_id,
            timestamp,
            'blocker-resolved',
            resolution.value,
          ),
        )
        remaining = connection.execute(
          """
          SELECT 1 FROM blocker
          WHERE task_id = ? AND status = 'open'
          LIMIT 1
          """,
          (blocker_task_id,),
        ).fetchone()
        if remaining is None and task_was_blocked:
          connection.execute(
            'INSERT INTO task_log '
            '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
            (
              blocker_task_id,
              timestamp,
              'unblocked',
              'All task blockers resolved',
            ),
          )
      if blocker_task_id is None and blocker_goal_id is not None:
        goal_row = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker_goal_id,)
        ).fetchone()
        if (
          goal_row is not None and _req_goal_status(goal_row) == 'blocked'
        ):
          if remaining_goal is None:
            raise ProjectError(
              f'Could not reactivate goal {blocker_goal_id}'
            )
          connection.execute(
            """
            UPDATE goal
            SET status_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
              _req_str(remaining_goal, 'description'),
              timestamp,
              blocker_goal_id,
            ),
          )
      _touch(connection, timestamp)


def add_evidence(
  connection: sqlite3.Connection,
  claim: SubstantiveText,
  *,
  source: str = '',
  result: str = '',
  stage: StageReference | None = None,
  task: PositiveInt | None = None,
  goal: GoalReference | None = None,
) -> int:
  with _sqlite_boundary():
    with connection:
      stage_id, task_id, goal_id = _resolve_record_relationships(
        connection, 'Evidence', stage, task, goal
      )
      if goal_id is not None:
        goal_row = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()
        if (
          goal_row is not None and _req_goal_status(goal_row) == 'achieved'
        ):
          raise ProjectError('Achieved goal evidence is fixed')
      stage_generation: int | None = None
      if stage_id is not None:
        stage_row = connection.execute(
          'SELECT achievement_generation FROM stage WHERE id = ?',
          (stage_id,),
        ).fetchone()
        if stage_row is None:
          raise ProjectError(f'Stage does not exist: {stage_id}')
        stage_generation = _req_int(stage_row, 'achievement_generation')
      timestamp = connection_time(connection)
      cursor = connection.execute(
        """
        INSERT INTO evidence
          (goal_id, stage_id, task_id, claim, source, result, captured_at,
           stage_generation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          claim.value,
          source,
          result,
          timestamp,
          stage_generation,
        ),
      )
      _touch(connection, timestamp)
      return _inserted_id(cursor, 'Evidence')


def read_evidence(
  connection: sqlite3.Connection, filters: RecordListFilter
) -> tuple[EvidenceRecord, ...]:
  with _sqlite_boundary():
    where, parameters = _build_record_filter_sql(connection, filters)
    rows = connection.execute(
      f'SELECT * FROM evidence {where} '
      'ORDER BY captured_at DESC, id DESC LIMIT ?',
      parameters,
    ).fetchall()
    return tuple(_decode_evidence(row) for row in rows)


def _validate_active_state(
  connection: sqlite3.Connection,
  goal_id: int | None,
  task_row: sqlite3.Row | None,
) -> None:
  if task_row is None:
    return
  _ensure_task_documented(task_row)
  stage_id = _opt_int(task_row, 'stage_id')
  if stage_id is None:
    raise ProjectError('Active task has no stage relationship')
  task_goal_id = _opt_int(task_row, 'goal_id')
  if task_goal_id is not None and task_goal_id != goal_id:
    raise ProjectError('Active task goal does not match the active goal')
  _ensure_goal_stage(connection, task_goal_id, stage_id, 'Active task')
  _ensure_task_dependencies_are_achieved(connection, stage_id)
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open'",
    (_req_int(task_row, 'id'),),
  ).fetchone():
    raise ProjectError('Active task has an open blocker')


def _handoff_page(
  connection: sqlite3.Connection,
  query: str,
  count_query: str,
  parameters: Sequence[object] = (),
  query_prefix: Sequence[object] = (),
) -> tuple[list[sqlite3.Row], HandoffPage]:
  count_row = connection.execute(count_query, parameters).fetchone()
  if count_row is None:
    raise ProjectError('Handoff page count returned no row')
  total = count_row[0]
  if isinstance(total, bool) or not isinstance(total, int):
    raise ProjectError('Handoff page count was not an integer')
  rows = connection.execute(
    f'{query} LIMIT ?', (*query_prefix, *parameters, HANDOFF_LIMIT)
  ).fetchall()
  return rows, HandoffPage(
    shown=len(rows),
    total=total,
    truncated=total > len(rows),
  )


@contextmanager
def _read_snapshot(connection: sqlite3.Connection) -> Iterator[None]:
  if connection.in_transaction:
    yield
    return
  connection.execute('BEGIN')
  try:
    yield
  finally:
    if connection.in_transaction:
      connection.rollback()


def read_handoff(connection: sqlite3.Connection, path: str) -> HandoffData:
  with _sqlite_boundary(), _read_snapshot(connection):
    project = _decode_project_record(connection)
    state = _decode_project_state(connection)
    active_goal_id = _active_goal_id(connection)
    active_task_row = _active_task_row(connection)
    _validate_active_state(connection, active_goal_id, active_task_row)
    goal: ActiveGoalRef | None = None
    if active_goal_id is not None:
      goal_row = connection.execute(
        'SELECT * FROM goal WHERE id = ?', (active_goal_id,)
      ).fetchone()
      if goal_row is not None:
        goal = ActiveGoalRef(
          goal=_decode_goal_record(connection, goal_row)
        )
    task = (
      _decode_handoff_task(active_task_row)
      if active_task_row is not None
      else None
    )
    stage = (
      _stage_record(connection, task.stage_id)
      if task is not None and task.stage_id is not None
      else None
    )
    blocked_task_rows, blocked_task_page = _handoff_page(
      connection,
      """
      SELECT task.id, task.title, task.status, task.goal_id, task.stage_id,
        stage.name AS stage_name, task.updated_at
      FROM task
      LEFT JOIN stage ON stage.id = task.stage_id
      WHERE task.status = 'blocked'
      ORDER BY task.updated_at DESC, task.id DESC
      """,
      "SELECT count(*) FROM task WHERE status = 'blocked'",
    )
    blocked_tasks = tuple(
      BlockedTaskSummary(
        id=_req_int(row, 'id'),
        title=(title := _req_str(row, 'title')),
        status=_req_task_status(row),
        goal_id=_opt_int(row, 'goal_id'),
        stage_id=_opt_int(row, 'stage_id'),
        stage_name=_opt_str(row, 'stage_name'),
        updated_at=_req_int(row, 'updated_at'),
        title_status=title_status_for(title),
      )
      for row in blocked_task_rows
    )
    blocked_goal_rows, blocked_goal_page = _handoff_page(
      connection,
      """
      SELECT id, text, status, status_reason, updated_at
      FROM goal
      WHERE status = 'blocked'
      ORDER BY updated_at DESC, id DESC
      """,
      "SELECT count(*) FROM goal WHERE status = 'blocked'",
    )
    blocked_goals = tuple(
      BlockedGoalSummary(
        id=(goal_id := _req_int(row, 'id')),
        text=_req_str(row, 'text'),
        status=_req_goal_status(row),
        status_reason=_blocked_goal_reason(connection, goal_id),
        updated_at=_req_int(row, 'updated_at'),
      )
      for row in blocked_goal_rows
    )
    blocker_rows, blocker_page = _handoff_page(
      connection,
      """
      SELECT id, goal_id, stage_id, task_id, description, required,
        opened_at,
        CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' END
          AS target_kind,
        COALESCE(task_id, goal_id) AS target_id
      FROM blocker
      WHERE status = 'open'
      ORDER BY opened_at DESC, id DESC
      """,
      "SELECT count(*) FROM blocker WHERE status = 'open'",
    )
    blockers = tuple(
      HandoffBlockerSummary(
        id=_req_int(row, 'id'),
        goal_id=_opt_int(row, 'goal_id'),
        stage_id=_opt_int(row, 'stage_id'),
        task_id=_opt_int(row, 'task_id'),
        description=_req_str(row, 'description'),
        required=_req_str(row, 'required'),
        opened_at=_req_int(row, 'opened_at'),
        target_kind=_req_focus_kind(row, 'target_kind'),
        target_id=_req_int(row, 'target_id'),
      )
      for row in blocker_rows
    )
    focus_task_id = (
      task.id
      if task is not None
      else blocked_tasks[0].id
      if blocked_tasks
      else None
    )
    focus_goal_id = (
      active_goal_id
      if active_goal_id is not None
      else blocked_goals[0].id
      if blocked_goals
      else None
    )
    if focus_task_id is not None:
      focus_clause = 'task_id = ?'
      focus_parameters: tuple[object, ...] = (focus_task_id,)
      focus_kind: FocusKind | None = 'task'
      focus_id: int | None = focus_task_id
    elif focus_goal_id is not None:
      focus_clause = 'goal_id = ? AND task_id IS NULL'
      focus_parameters = (focus_goal_id,)
      focus_kind = 'goal'
      focus_id = focus_goal_id
    else:
      focus_clause = '0'
      focus_parameters = ()
      focus_kind = None
      focus_id = None
    decision_rows, decision_page = _handoff_page(
      connection,
      f"""
      SELECT id, goal_id, stage_id, task_id, summary, decided_at,
        context_status
      FROM decision
      WHERE {focus_clause}
      ORDER BY decided_at DESC, id DESC
      """,
      f'SELECT count(*) FROM decision WHERE {focus_clause}',
      focus_parameters,
    )
    decisions = tuple(
      HandoffDecisionSummary(
        id=_req_int(row, 'id'),
        goal_id=_opt_int(row, 'goal_id'),
        stage_id=_opt_int(row, 'stage_id'),
        task_id=_opt_int(row, 'task_id'),
        summary=_req_str(row, 'summary'),
        decided_at=_req_int(row, 'decided_at'),
        context_status=_req_record_context(row),
      )
      for row in decision_rows
    )
    evidence_rows, evidence_page = _handoff_page(
      connection,
      f"""
      SELECT id, goal_id, stage_id, task_id, claim, source, result,
        captured_at, context_status, claim_status, stage_generation
      FROM evidence
      WHERE {focus_clause}
      ORDER BY captured_at DESC, id DESC
      """,
      f'SELECT count(*) FROM evidence WHERE {focus_clause}',
      focus_parameters,
    )
    evidence = tuple(_decode_evidence(row) for row in evidence_rows)
    logs: tuple[HandoffLogEntry, ...] = ()
    log_page = HandoffPage(shown=0, total=0, truncated=False)
    if focus_task_id is not None:
      log_rows, log_page = _handoff_page(
        connection,
        """
        SELECT occurred_at, kind, message
        FROM task_log
        WHERE task_id = ?
        ORDER BY occurred_at DESC, id DESC
        """,
        'SELECT count(*) FROM task_log WHERE task_id = ?',
        (focus_task_id,),
      )
      logs = tuple(
        HandoffLogEntry(
          occurred_at=_req_int(row, 'occurred_at'),
          kind=_req_str(row, 'kind'),
          message=_req_str(row, 'message'),
        )
        for row in log_rows
      )
    return HandoffData(
      path=path,
      project=project,
      state=state,
      goal=goal,
      stage=stage,
      task=task,
      blocked_tasks=blocked_tasks,
      blocked_goals=blocked_goals,
      blockers=blockers,
      decisions=decisions,
      evidence=evidence,
      logs=logs,
      focus=HandoffFocus(kind=focus_kind, id=focus_id),
      pages=HandoffPages(
        blocked_tasks=blocked_task_page,
        blocked_goals=blocked_goal_page,
        blockers=blocker_page,
        decisions=decision_page,
        evidence=evidence_page,
        task_log=log_page,
      ),
    )


_BLOB_CHUNK_BYTES: Final[int] = 65536
_HANDOFF_BYTE_LIMIT: Final[int] = 4 * (HANDOFF_TEXT_LIMIT + 1)


def _bounded_col_sql(expr: str, alias: str) -> str:
  return (
    f'typeof({expr}) AS {alias}_type, '
    f'CAST(substr(CAST({expr} AS BLOB), 1, ?) AS BLOB) '
    f'AS {alias}_prefix, '
    f'octet_length({expr}) AS {alias}_bytes'
  )


def _stream_utf8_char_count(
  connection: sqlite3.Connection,
  table_name: str,
  column_name: str,
  row_id: int,
) -> int:
  decoder = codecs.getincrementaldecoder('utf-8')('strict')
  total = 0
  try:
    with connection.blobopen(
      table_name, column_name, row_id, readonly=True
    ) as blob:
      while chunk := blob.read(_BLOB_CHUNK_BYTES):
        total += len(decoder.decode(chunk, final=False))
      total += len(decoder.decode(b'', final=True))
  except UnicodeDecodeError as error:
    raise ProjectError(f'Database error: {error}') from error
  return total


def _decode_bounded_text(
  connection: sqlite3.Connection,
  row: sqlite3.Row,
  alias: str,
  *,
  table_name: str,
  column_name: str,
  row_id: int,
  error_col: str | None = None,
) -> BoundedText:
  col_label = alias if error_col is None else error_col
  col_type = row[f'{alias}_type']
  if col_type != 'text':
    raise ProjectError(f'Column {col_label!r} must be text')
  prefix_blob = row[f'{alias}_prefix']
  total_bytes = _req_int(row, f'{alias}_bytes')
  if total_bytes == 0 and prefix_blob is None:
    return BoundedText('', 0)
  if not isinstance(prefix_blob, (bytes, bytearray, memoryview)):
    raise ProjectError(f'Column {col_label!r} prefix must be bytes')
  decoder = codecs.getincrementaldecoder('utf-8')('strict')
  try:
    prefix = decoder.decode(
      bytes(prefix_blob), final=(total_bytes <= _HANDOFF_BYTE_LIMIT)
    )
  except UnicodeDecodeError as error:
    raise ProjectError(f'Database error: {error}') from error
  if total_bytes <= _HANDOFF_BYTE_LIMIT:
    characters = len(prefix)
  else:
    characters = _stream_utf8_char_count(
      connection, table_name, column_name, row_id
    )
  return BoundedText(prefix[: HANDOFF_TEXT_LIMIT + 1], characters)


def _opt_bounded_text(
  connection: sqlite3.Connection,
  row: sqlite3.Row,
  alias: str,
  *,
  table_name: str,
  column_name: str,
  row_id: int | None,
  error_col: str | None = None,
) -> BoundedText | None:
  col_label = alias if error_col is None else error_col
  col_type = row[f'{alias}_type']
  if col_type == 'null':
    return None
  if col_type != 'text':
    raise ProjectError(f'Column {col_label!r} must be text or null')
  if row_id is None:
    raise ProjectError(f'Column {col_label!r} is missing row identity')
  return _decode_bounded_text(
    connection,
    row,
    alias,
    table_name=table_name,
    column_name=column_name,
    row_id=row_id,
    error_col=col_label,
  )


def _decode_text_project(
  connection: sqlite3.Connection,
) -> TextHandoffProject:
  row = connection.execute(
    f"""
    SELECT id,
      {_bounded_col_sql('name', 'name')},
      {_bounded_col_sql('objective', 'objective')},
      charter_context_status
    FROM project
    """,
    (_HANDOFF_BYTE_LIMIT, _HANDOFF_BYTE_LIMIT),
  ).fetchone()
  if row is None:
    raise ProjectError('Project database has no project record')
  row_id = _req_int(row, 'id')
  status = _project_status(connection)
  return TextHandoffProject(
    name=_decode_bounded_text(
      connection,
      row,
      'name',
      table_name='project',
      column_name='name',
      row_id=row_id,
    ),
    status=status,
    objective=_decode_bounded_text(
      connection,
      row,
      'objective',
      table_name='project',
      column_name='objective',
      row_id=row_id,
    ),
    charter_context_status=_req_charter_context(row),
  )


def _decode_text_state(
  connection: sqlite3.Connection,
) -> TextHandoffState:
  row = connection.execute(
    f"""
    SELECT id,
      {_bounded_col_sql('summary', 'summary')},
      {_bounded_col_sql('next_action', 'next_action')}
    FROM project_state
    """,
    (_HANDOFF_BYTE_LIMIT, _HANDOFF_BYTE_LIMIT),
  ).fetchone()
  if row is None:
    raise ProjectError('Project state record does not exist')
  row_id = _req_int(row, 'id')
  return TextHandoffState(
    summary=_decode_bounded_text(
      connection,
      row,
      'summary',
      table_name='project_state',
      column_name='summary',
      row_id=row_id,
    ),
    next_action=_decode_bounded_text(
      connection,
      row,
      'next_action',
      table_name='project_state',
      column_name='next_action',
      row_id=row_id,
    ),
  )


def _active_text_task_row(
  connection: sqlite3.Connection,
) -> sqlite3.Row | None:
  return connection.execute(
    f"""
    SELECT id, goal_id, stage_id,
      {_bounded_col_sql('title', 'title')},
      (typeof(title) = 'text' AND octet_length(ltrim(title, ?)) > 0)
        AS title_substantive,
      typeof(purpose) AS purpose_type,
      (typeof(purpose) = 'text' AND octet_length(ltrim(purpose, ?)) > 0)
        AS purpose_substantive,
      typeof(scope) AS scope_type,
      (typeof(scope) = 'text' AND octet_length(ltrim(scope, ?)) > 0)
        AS scope_substantive,
      typeof(exclusions) AS exclusions_type,
      (
        typeof(exclusions) = 'text'
        AND octet_length(ltrim(exclusions, ?)) > 0
      ) AS exclusions_substantive,
      typeof(result) AS result_type,
      (typeof(result) = 'text' AND octet_length(ltrim(result, ?)) > 0)
        AS result_substantive,
      typeof(completion_evidence) AS completion_evidence_type,
      (
        typeof(completion_evidence) = 'text'
        AND octet_length(ltrim(completion_evidence, ?)) > 0
      ) AS completion_evidence_substantive
    FROM task
    WHERE status = 'active'
    """,
    (
      _HANDOFF_BYTE_LIMIT,
      UNICODE_WHITESPACE,
      UNICODE_WHITESPACE,
      UNICODE_WHITESPACE,
      UNICODE_WHITESPACE,
      UNICODE_WHITESPACE,
      UNICODE_WHITESPACE,
    ),
  ).fetchone()


def _validate_active_text_task(
  connection: sqlite3.Connection,
  goal_id: int | None,
  task_row: sqlite3.Row | None,
) -> None:
  if task_row is None:
    return
  missing: list[str] = []
  for field_name in (
    'title',
    'purpose',
    'scope',
    'exclusions',
    'result',
    'completion_evidence',
  ):
    if task_row[f'{field_name}_type'] != 'text':
      raise ProjectError(f'Column {field_name!r} must be text')
    if not task_row[f'{field_name}_substantive']:
      missing.append(field_name.replace('_', ' '))
  if missing:
    raise ProjectError(
      'Starting a task requires documented ' + ', '.join(missing)
    )
  stage_id = _opt_int(task_row, 'stage_id')
  if stage_id is None:
    raise ProjectError('Active task has no stage relationship')
  task_goal_id = _opt_int(task_row, 'goal_id')
  if task_goal_id is not None and task_goal_id != goal_id:
    raise ProjectError('Active task goal does not match the active goal')
  _ensure_goal_stage(connection, task_goal_id, stage_id, 'Active task')
  _ensure_task_dependencies_are_achieved(connection, stage_id)
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open'",
    (_req_int(task_row, 'id'),),
  ).fetchone():
    raise ProjectError('Active task has an open blocker')


def _text_blocked_goal_reason(
  connection: sqlite3.Connection, goal_id: int
) -> BoundedText:
  blocker = connection.execute(
    f"""
    SELECT id, {_bounded_col_sql('description', 'description')}
    FROM blocker
    WHERE goal_id = ? AND task_id IS NULL AND status = 'open'
    ORDER BY opened_at DESC, id DESC
    LIMIT 1
    """,
    (_HANDOFF_BYTE_LIMIT, goal_id),
  ).fetchone()
  if blocker is None:
    return BoundedText('', 0)
  return _decode_bounded_text(
    connection,
    blocker,
    'description',
    table_name='blocker',
    column_name='description',
    row_id=_req_int(blocker, 'id'),
  )


def read_text_handoff(
  connection: sqlite3.Connection, path: str
) -> TextHandoffData:
  with _sqlite_boundary():
    ensure_utf8_encoding(connection)
    with _read_snapshot(connection):
      project = _decode_text_project(connection)
      state = _decode_text_state(connection)
      active_goal_id = _active_goal_id(connection)
      active_task_row = _active_text_task_row(connection)
      _validate_active_text_task(
        connection, active_goal_id, active_task_row
      )

      goal: TextHandoffGoal | None = None
      if active_goal_id is not None:
        goal_row = connection.execute(
          f'SELECT id, status, {_bounded_col_sql("text", "text")} '
          'FROM goal WHERE id = ?',
          (_HANDOFF_BYTE_LIMIT, active_goal_id),
        ).fetchone()
        if goal_row is not None:
          goal_id = _req_int(goal_row, 'id')
          goal = TextHandoffGoal(
            id=goal_id,
            status=_req_goal_status(goal_row),
            text=_decode_bounded_text(
              connection,
              goal_row,
              'text',
              table_name='goal',
              column_name='text',
              row_id=goal_id,
            ),
          )

      task: TextHandoffTask | None = None
      if active_task_row is not None:
        active_task_id = _req_int(active_task_row, 'id')
        task = TextHandoffTask(
          id=active_task_id,
          goal_id=_opt_int(active_task_row, 'goal_id'),
          stage_id=_opt_int(active_task_row, 'stage_id'),
          title=_decode_bounded_text(
            connection,
            active_task_row,
            'title',
            table_name='task',
            column_name='title',
            row_id=active_task_id,
          ),
          title_status='substantive',
        )

      stage: TextHandoffStage | None = None
      if task is not None and task.stage_id is not None:
        stage_row = connection.execute(
          f'SELECT id, {_bounded_col_sql("name", "name")} '
          'FROM stage WHERE id = ?',
          (_HANDOFF_BYTE_LIMIT, task.stage_id),
        ).fetchone()
        if stage_row is None:
          raise ProjectError(f'Stage does not exist: {task.stage_id}')
        stage_id = _req_int(stage_row, 'id')
        stage = TextHandoffStage(
          id=stage_id,
          name=_decode_bounded_text(
            connection,
            stage_row,
            'name',
            table_name='stage',
            column_name='name',
            row_id=stage_id,
          ),
        )

      blocked_task_rows, blocked_task_page = _handoff_page(
        connection,
        f"""
        SELECT task.id,
          {_bounded_col_sql('task.title', 'title')},
          (
            typeof(task.title) = 'text'
            AND octet_length(ltrim(task.title, ?)) > 0
          ) AS title_substantive,
          task.status, task.goal_id, task.stage_id,
          {_bounded_col_sql('stage.name', 'stage_name')}
        FROM task
        LEFT JOIN stage ON stage.id = task.stage_id
        WHERE task.status = 'blocked'
        ORDER BY task.updated_at DESC, task.id DESC
        """,
        "SELECT count(*) FROM task WHERE status = 'blocked'",
        query_prefix=(
          _HANDOFF_BYTE_LIMIT,
          UNICODE_WHITESPACE,
          _HANDOFF_BYTE_LIMIT,
        ),
      )
      blocked_tasks_list: list[TextBlockedTaskSummary] = []
      for row in blocked_task_rows:
        _req_task_status(row)
        task_id = _req_int(row, 'id')
        row_stage_id = _opt_int(row, 'stage_id')
        blocked_title_status: TitleStatus = (
          'substantive' if row['title_substantive'] else 'legacy-blank'
        )
        blocked_tasks_list.append(
          TextBlockedTaskSummary(
            id=task_id,
            title=_decode_bounded_text(
              connection,
              row,
              'title',
              table_name='task',
              column_name='title',
              row_id=task_id,
            ),
            goal_id=_opt_int(row, 'goal_id'),
            stage_id=row_stage_id,
            stage_name=_opt_bounded_text(
              connection,
              row,
              'stage_name',
              table_name='stage',
              column_name='name',
              row_id=row_stage_id,
              error_col='stage_name',
            ),
            title_status=blocked_title_status,
          )
        )
      blocked_tasks = tuple(blocked_tasks_list)

      blocked_goal_rows, blocked_goal_page = _handoff_page(
        connection,
        f"""
        SELECT id, status, {_bounded_col_sql('text', 'text')}
        FROM goal
        WHERE status = 'blocked'
        ORDER BY updated_at DESC, id DESC
        """,
        "SELECT count(*) FROM goal WHERE status = 'blocked'",
        query_prefix=(_HANDOFF_BYTE_LIMIT,),
      )
      blocked_goals_list: list[TextBlockedGoalSummary] = []
      for row in blocked_goal_rows:
        _req_goal_status(row)
        blocked_goal_id = _req_int(row, 'id')
        blocked_goals_list.append(
          TextBlockedGoalSummary(
            id=blocked_goal_id,
            text=_decode_bounded_text(
              connection,
              row,
              'text',
              table_name='goal',
              column_name='text',
              row_id=blocked_goal_id,
            ),
            status_reason=_text_blocked_goal_reason(
              connection, blocked_goal_id
            ),
          )
        )
      blocked_goals = tuple(blocked_goals_list)

      blocker_rows, blocker_page = _handoff_page(
        connection,
        f"""
        SELECT id,
          {_bounded_col_sql('description', 'description')},
          {_bounded_col_sql('required', 'required')},
          CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' END
            AS target_kind,
          COALESCE(task_id, goal_id) AS target_id
        FROM blocker
        WHERE status = 'open'
        ORDER BY opened_at DESC, id DESC
        """,
        "SELECT count(*) FROM blocker WHERE status = 'open'",
        query_prefix=(_HANDOFF_BYTE_LIMIT, _HANDOFF_BYTE_LIMIT),
      )
      blockers = tuple(
        TextHandoffBlockerSummary(
          id=(blocker_id := _req_int(row, 'id')),
          description=_decode_bounded_text(
            connection,
            row,
            'description',
            table_name='blocker',
            column_name='description',
            row_id=blocker_id,
          ),
          required=_decode_bounded_text(
            connection,
            row,
            'required',
            table_name='blocker',
            column_name='required',
            row_id=blocker_id,
          ),
          target_kind=_req_focus_kind(row, 'target_kind'),
          target_id=_req_int(row, 'target_id'),
        )
        for row in blocker_rows
      )

      focus_task_id = (
        task.id
        if task is not None
        else blocked_tasks[0].id
        if blocked_tasks
        else None
      )
      focus_goal_id = (
        active_goal_id
        if active_goal_id is not None
        else blocked_goals[0].id
        if blocked_goals
        else None
      )
      if focus_task_id is not None:
        focus_clause = 'task_id = ?'
        focus_parameters: tuple[object, ...] = (focus_task_id,)
        focus_kind: FocusKind | None = 'task'
        focus_id: int | None = focus_task_id
      elif focus_goal_id is not None:
        focus_clause = 'goal_id = ? AND task_id IS NULL'
        focus_parameters = (focus_goal_id,)
        focus_kind = 'goal'
        focus_id = focus_goal_id
      else:
        focus_clause = '0'
        focus_parameters = ()
        focus_kind = None
        focus_id = None

      decision_rows, decision_page = _handoff_page(
        connection,
        f"""
        SELECT id,
          {_bounded_col_sql('summary', 'summary')},
          context_status
        FROM decision
        WHERE {focus_clause}
        ORDER BY decided_at DESC, id DESC
        """,
        f'SELECT count(*) FROM decision WHERE {focus_clause}',
        focus_parameters,
        (_HANDOFF_BYTE_LIMIT,),
      )
      decisions = tuple(
        TextHandoffDecisionSummary(
          id=(decision_id := _req_int(row, 'id')),
          summary=_decode_bounded_text(
            connection,
            row,
            'summary',
            table_name='decision',
            column_name='summary',
            row_id=decision_id,
          ),
          context_status=_req_record_context(row),
        )
        for row in decision_rows
      )

      evidence_rows, evidence_page = _handoff_page(
        connection,
        f"""
        SELECT id,
          {_bounded_col_sql('claim', 'claim')},
          context_status, claim_status
        FROM evidence
        WHERE {focus_clause}
        ORDER BY captured_at DESC, id DESC
        """,
        f'SELECT count(*) FROM evidence WHERE {focus_clause}',
        focus_parameters,
        (_HANDOFF_BYTE_LIMIT,),
      )
      evidence = tuple(
        TextHandoffEvidenceSummary(
          id=(evidence_id := _req_int(row, 'id')),
          claim=_decode_bounded_text(
            connection,
            row,
            'claim',
            table_name='evidence',
            column_name='claim',
            row_id=evidence_id,
          ),
          context_status=_req_record_context(row),
          claim_status=_req_claim_status(row),
        )
        for row in evidence_rows
      )

      logs: tuple[TextHandoffLogEntry, ...] = ()
      log_page = HandoffPage(shown=0, total=0, truncated=False)
      if focus_task_id is not None:
        log_rows, log_page = _handoff_page(
          connection,
          f"""
          SELECT id,
            {_bounded_col_sql('kind', 'kind')},
            {_bounded_col_sql('message', 'message')}
          FROM task_log
          WHERE task_id = ?
          ORDER BY occurred_at DESC, id DESC
          """,
          'SELECT count(*) FROM task_log WHERE task_id = ?',
          (focus_task_id,),
          (_HANDOFF_BYTE_LIMIT, _HANDOFF_BYTE_LIMIT),
        )
        logs = tuple(
          TextHandoffLogEntry(
            kind=_decode_bounded_text(
              connection,
              row,
              'kind',
              table_name='task_log',
              column_name='kind',
              row_id=(log_id := _req_int(row, 'id')),
            ),
            message=_decode_bounded_text(
              connection,
              row,
              'message',
              table_name='task_log',
              column_name='message',
              row_id=log_id,
            ),
          )
          for row in log_rows
        )

      return TextHandoffData(
        path=path,
        project=project,
        state=state,
        goal=goal,
        stage=stage,
        task=task,
        blocked_tasks=blocked_tasks,
        blocked_goals=blocked_goals,
        blockers=blockers,
        decisions=decisions,
        evidence=evidence,
        logs=logs,
        focus=HandoffFocus(kind=focus_kind, id=focus_id),
        pages=HandoffPages(
          blocked_tasks=blocked_task_page,
          blocked_goals=blocked_goal_page,
          blockers=blocker_page,
          decisions=decision_page,
          evidence=evidence_page,
          task_log=log_page,
        ),
      )
