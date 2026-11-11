import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, NewType, TypedDict, cast

from .errors import ProjectError
from .storage import (
  PROJECT_SUFFIX,
  archive_database,
  create_database,
  current_time,
  database_path,
  is_substantive,
  open_project,
  project_directory,
  validate_project_name,
)

MAX_GOAL_TEXT_LENGTH = 4000

type GoalStatus = Literal[
  'active', 'pending', 'blocked', 'achieved', 'cancelled'
]
type TaskStatus = Literal[
  'pending', 'active', 'completed', 'blocked', 'cancelled'
]
type BlockerStatus = Literal['open', 'resolved', 'withdrawn']
type StageStatus = Literal[
  'active', 'pending', 'blocked', 'achieved', 'superseded'
]
type ProjectStatus = Literal['complete', 'active', 'blocked']

GOAL_STATUSES: tuple[GoalStatus, ...] = (
  'active',
  'pending',
  'blocked',
  'achieved',
  'cancelled',
)

TASK_STATUSES: tuple[TaskStatus, ...] = (
  'pending',
  'active',
  'completed',
  'blocked',
  'cancelled',
)

BLOCKER_STATUSES: tuple[BlockerStatus, ...] = (
  'open',
  'resolved',
  'withdrawn',
)

HANDOFF_LIMIT = 5

Unset = NewType('Unset', object)
UNSET: Unset = Unset(object())

type ProjectRoot = str | Path
type StageReference = int | str
type RecordReference = int | str
type GoalReference = int | str


class TaskRecord(TypedDict, total=False):
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
  updated_at: int
  started_at: int | None
  completed_at: int | None
  stage_name: str | None
  tags: str
  title_status: Literal['substantive', 'legacy-blank']
  context_status: str
  claim_status: str | None


class ProjectRecord(TypedDict, total=False):
  id: int
  name: str
  objective: str
  scope: str
  non_goals: str
  constraints_text: str
  acceptance: str
  created_at: int
  updated_at: int
  status: ProjectStatus
  completed_at: int | None
  charter_context_status: Literal['current', 'legacy-incomplete']
  path: str


class ProjectState(TypedDict, total=False):
  id: int
  summary: str
  next_action: str
  updated_at: int
  revision: int


class GoalRecord(TypedDict, total=False):
  id: int
  text: str
  status: GoalStatus
  status_reason: str
  ever_activated: int
  created_at: int
  started_at: int
  achieved_at: int | None
  updated_at: int
  is_active: bool
  stage_names: str


class StageRecord(TypedDict, total=False):
  id: int
  name: str
  outcome: str
  purpose: str
  entry_conditions: str
  exit_evidence: str
  position: int
  status: StageStatus
  started_at: int | None
  achieved_at: int | None
  achievement_evidence_id: int | None
  achievement_generation: int
  dependencies: str


class HandoffPage(TypedDict):
  shown: int
  total: int
  truncated: bool


class HandoffPageCount(TypedDict, total=False):
  total: int


class HandoffFocus(TypedDict):
  kind: Literal['task', 'goal'] | None
  id: int | None


class ActiveGoal(TypedDict):
  goal: GoalRecord


class HandoffRetrievalInput(TypedDict, total=False):
  project: ProjectRecord
  goal: ActiveGoal | None
  task: TaskRecord | None
  stage: StageRecord | None
  focus: HandoffFocus
  pages: dict[str, HandoffPageCount]


class ProjectView(TypedDict):
  path: str
  project: ProjectRecord
  state: ProjectState
  goal: 'GoalDetails | None'
  charter_history: list[dict[str, object]]


class GoalDetails(TypedDict):
  goal: GoalRecord
  stages: list[dict[str, object]]
  tasks: list[TaskRecord]
  blockers: list[dict[str, object]]
  evidence: list[dict[str, object]]
  decisions: list[dict[str, object]]


class TaskDetails(TypedDict):
  task: TaskRecord
  logs: list[dict[str, object]]


class HandoffData(HandoffRetrievalInput):
  path: str
  project: ProjectRecord
  state: ProjectState
  goal: ActiveGoal | None
  stage: StageRecord | None
  task: TaskRecord | None
  blocked_tasks: list[TaskRecord]
  blocked_goals: list[dict[str, object]]
  blockers: list[dict[str, object]]
  decisions: list[dict[str, object]]
  evidence: list[dict[str, object]]
  logs: list[dict[str, object]]
  focus: HandoffFocus
  pages: dict[str, HandoffPage]


def create_project(
  root: ProjectRoot,
  name: str,
  objective: str,
  scope: str = '',
  non_goals: str = '',
  constraints: str = '',
  acceptance: str = '',
) -> Path:
  validate_project_name(name)
  _require_record_text(objective, 'Project objective')
  return create_database(
    root, name, objective, scope, non_goals, constraints, acceptance
  )


def archive_project(root: ProjectRoot, name: str) -> Path:
  return archive_database(root, name)


def _row_dict(
  row: sqlite3.Row | Mapping[str, object] | None,
) -> dict[str, object] | None:
  return dict(row) if row is not None else None


def _required_record(
  row: sqlite3.Row | None, label: str
) -> dict[str, object]:
  if row is None:
    raise ProjectError(f'{label} record does not exist')
  return dict(row)


def _task_read_dict(
  row: sqlite3.Row | Mapping[str, object] | None,
) -> TaskRecord | None:
  task = _row_dict(row)
  if task is not None and row is not None:
    title = task.get('title')
    if not isinstance(title, str):
      raise ProjectError('Task record has no text title')
    task['title_status'] = (
      'substantive' if is_substantive(title) else 'legacy-blank'
    )
  return cast(TaskRecord, task) if task is not None else None


def _inserted_id(cursor: sqlite3.Cursor, record_name: str) -> int:
  identifier = cursor.lastrowid
  if identifier is None:
    raise ProjectError(
      f'{record_name} insertion did not return an identifier'
    )
  return identifier


def _touch(connection: sqlite3.Connection) -> None:
  timestamp = current_time()
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
  connection: sqlite3.Connection, reference: StageReference | None
) -> int | None:
  if reference is None:
    return None
  if str(reference).isdigit():
    row = connection.execute(
      'SELECT id FROM stage WHERE id = ?', (int(reference),)
    ).fetchone()
  else:
    row = connection.execute(
      'SELECT id FROM stage WHERE name = ?', (reference,)
    ).fetchone()
  if row is None:
    raise ProjectError(f'Stage does not exist: {reference}')
  return row['id']


def _resolve_task(
  connection: sqlite3.Connection, reference: RecordReference
) -> int:
  if str(reference).isdigit():
    row = connection.execute(
      'SELECT id FROM task WHERE id = ?', (int(reference),)
    ).fetchone()
  else:
    raise ProjectError(f'Task references must be numeric: {reference}')
  if row is None:
    raise ProjectError(f'Task does not exist: {reference}')
  return row['id']


def validate_goal_text(text: str) -> str:
  length = len(text)
  if not is_substantive(text):
    raise ProjectError(
      'Goal text must contain at least one non-whitespace character'
    )
  if length > MAX_GOAL_TEXT_LENGTH:
    raise ProjectError(
      f'Goal text is limited to {MAX_GOAL_TEXT_LENGTH:,} characters; '
      f'received {length:,}.'
    )
  return text


def _require_record_text(value: str, label: str) -> None:
  if not is_substantive(value):
    raise ProjectError(f'{label} must contain non-whitespace text')


def _resolve_goal(
  connection: sqlite3.Connection,
  reference: GoalReference | None = None,
) -> int:
  if reference is None or str(reference) == 'active':
    row = connection.execute(
      "SELECT id FROM goal WHERE status = 'active'"
    ).fetchone()
    if row is None:
      raise ProjectError('Project has no active goal')
    return row['id']
  if not str(reference).isdigit():
    raise ProjectError(f'Goal references must be numeric: {reference}')
  row = connection.execute(
    'SELECT id FROM goal WHERE id = ?', (int(reference),)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Goal does not exist: {reference}')
  return row['id']


def _resolve_evidence(
  connection: sqlite3.Connection, reference: RecordReference
) -> int:
  if not str(reference).isdigit():
    raise ProjectError(f'Evidence references must be numeric: {reference}')
  row = connection.execute(
    'SELECT id FROM evidence WHERE id = ?', (int(reference),)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Evidence does not exist: {reference}')
  return row['id']


def _ensure_goal_stage(
  connection: sqlite3.Connection,
  goal_id: int | None,
  stage_id: int | None,
  relationship: str,
) -> None:
  if goal_id is None or stage_id is None:
    return
  if (
    connection.execute(
      'SELECT 1 FROM goal_stage WHERE goal_id = ? AND stage_id = ?',
      (goal_id, stage_id),
    ).fetchone()
    is None
  ):
    raise ProjectError(
      f'{relationship} stage is not linked to goal {goal_id}'
    )


def _project_charter_missing(connection: sqlite3.Connection) -> list[str]:
  project = connection.execute('SELECT * FROM project').fetchone()
  labels = {
    'objective': 'objective',
    'scope': 'scope',
    'non_goals': 'non-goals',
    'constraints_text': 'constraints',
    'acceptance': 'acceptance evidence',
  }
  return [
    label
    for field, label in labels.items()
    if not is_substantive(project[field])
  ]


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
  if stage is None or not all(
    is_substantive(stage[field]) for field in ('name', 'outcome')
  ):
    raise ProjectError('Starting work requires a complete stage contract')


def _resolve_record_relationships(
  connection: sqlite3.Connection,
  relationship: str,
  stage: StageReference | None = None,
  task: RecordReference | None = None,
  goal: GoalReference | None = None,
) -> tuple[int | None, int | None, int | None]:
  stage_id = _resolve_stage(connection, stage)
  task_id = _resolve_task(connection, task) if task is not None else None
  goal_id = _resolve_goal(connection, goal) if goal is not None else None
  if task_id is not None:
    task_record = connection.execute(
      'SELECT goal_id, stage_id FROM task WHERE id = ?', (task_id,)
    ).fetchone()
    if stage_id is None:
      stage_id = task_record['stage_id']
    elif stage_id != task_record['stage_id']:
      raise ProjectError(f'{relationship} stage does not match task stage')
    if goal_id is None:
      goal_id = task_record['goal_id']
    elif goal_id != task_record['goal_id']:
      raise ProjectError(f'{relationship} goal does not match task goal')
  _ensure_goal_stage(connection, goal_id, stage_id, relationship)
  return stage_id, task_id, goal_id


def _active_goal(
  connection: sqlite3.Connection,
) -> sqlite3.Row | None:
  return connection.execute(
    "SELECT id, status FROM goal WHERE status = 'active'"
  ).fetchone()


def _active_task(
  connection: sqlite3.Connection,
) -> sqlite3.Row | None:
  return connection.execute(
    "SELECT * FROM task WHERE status = 'active'"
  ).fetchone()


def _stage_status(
  connection: sqlite3.Connection, stage_id: int
) -> StageStatus:
  counts = {
    row['status']: row['count']
    for row in connection.execute(
      'SELECT status, count(*) AS count FROM task '
      'WHERE stage_id = ? GROUP BY status',
      (stage_id,),
    )
  }
  if counts.get('active'):
    return 'active'
  if counts.get('pending'):
    return 'pending'
  if counts.get('blocked'):
    return 'blocked'
  if (
    counts.get('completed')
    and connection.execute(
      'SELECT 1 FROM stage_achievement '
      'WHERE stage_id = ? AND invalidated_at IS NULL',
      (stage_id,),
    ).fetchone()
  ):
    return 'achieved'
  if counts and counts.get('cancelled') == sum(counts.values()):
    return 'superseded'
  return 'pending'


def _stage_record(
  connection: sqlite3.Connection, stage_id: int
) -> StageRecord:
  row = connection.execute(
    'SELECT * FROM stage WHERE id = ?', (stage_id,)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Stage does not exist: {stage_id}')
  stage = dict(row)
  achievement = connection.execute(
    'SELECT evidence_id, achieved_at FROM stage_achievement '
    'WHERE stage_id = ? AND invalidated_at IS NULL',
    (stage_id,),
  ).fetchone()
  started = connection.execute(
    'SELECT MIN(started_at) AS started_at FROM task '
    'WHERE stage_id = ? AND started_at IS NOT NULL',
    (stage_id,),
  ).fetchone()['started_at']
  return cast(
    StageRecord,
    {
      **stage,
      'status': _stage_status(connection, stage_id),
      'started_at': started,
      'achieved_at': achievement['achieved_at'] if achievement else None,
      'achievement_evidence_id': (
        achievement['evidence_id'] if achievement else None
      ),
    },
  )


def _project_status(connection: sqlite3.Connection) -> ProjectStatus:
  statuses = [
    _stage_status(connection, row['id'])
    for row in connection.execute('SELECT id FROM stage')
  ]
  if 'achieved' in statuses and all(
    status in ('achieved', 'superseded') for status in statuses
  ):
    return 'complete'
  if any(status in ('active', 'pending') for status in statuses):
    return 'active'
  if any(status == 'blocked' for status in statuses):
    return 'blocked'
  return 'active'


def _project_completed_at(
  connection: sqlite3.Connection,
) -> int | None:
  if _project_status(connection) != 'complete':
    return None
  return connection.execute(
    'SELECT MAX(achieved_at) AS completed_at FROM stage_achievement '
    'WHERE invalidated_at IS NULL'
  ).fetchone()['completed_at']


def _ensure_task_goal_is_active(
  connection: sqlite3.Connection, goal_id: int | None
) -> None:
  active_goal = _active_goal(connection)
  active_goal_id = active_goal['id'] if active_goal is not None else None
  if goal_id is None:
    return
  if active_goal_id == goal_id:
    return
  if active_goal_id is None:
    raise ProjectError(f'Task goal {goal_id} is not the active goal')
  raise ProjectError(
    f'Task goal {goal_id} does not match active goal {active_goal_id}'
  )


def _ensure_task_dependencies_are_achieved(
  connection: sqlite3.Connection, stage_id: int | None
) -> None:
  if stage_id is None:
    return
  dependency = connection.execute(
    """
    SELECT dependency_stage.name
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
    (stage_id,),
  ).fetchone()
  if dependency is not None:
    raise ProjectError(
      f'Stage dependency is not achieved: {dependency["name"]}'
    )


def _task_documentation_missing(
  task: Mapping[str, object],
) -> list[str]:
  fields = (
    'title',
    'purpose',
    'scope',
    'exclusions',
    'result',
    'completion_evidence',
  )
  missing: list[str] = []
  for field in fields:
    value = task[field]
    if not isinstance(value, str) or not is_substantive(value):
      missing.append(field.replace('_', ' '))
  return missing


def _ensure_task_documented(task: Mapping[str, object]) -> None:
  missing = _task_documentation_missing(task)
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
    task = _active_task(connection)
  else:
    task = connection.execute(
      "SELECT id FROM task WHERE status = 'active' AND goal_id = ?",
      (goal_id,),
    ).fetchone()
  if task is not None:
    raise ProjectError(
      f'{transition} requires active task {task["id"]} to end first'
    )


def _return_task_to_pending(
  connection: sqlite3.Connection,
  task: sqlite3.Row,
  timestamp: int,
  reason: str,
) -> None:
  connection.execute(
    "UPDATE task SET status = 'pending', updated_at = ? WHERE id = ?",
    (timestamp, task['id']),
  )
  connection.execute(
    'INSERT INTO task_log '
    '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
    (task['id'], timestamp, 'handoff', reason),
  )


def _handoff_active_goal(
  connection: sqlite3.Connection,
  target_goal_id: int,
  timestamp: int,
) -> None:
  active_goal = _active_goal(connection)
  if active_goal is None or active_goal['id'] == target_goal_id:
    return
  active_task = _active_task(connection)
  if (
    active_task is not None and active_task['goal_id'] == active_goal['id']
  ):
    _return_task_to_pending(
      connection,
      active_task,
      timestamp,
      f'Task returned to pending while activating goal {target_goal_id}',
    )
  connection.execute(
    "UPDATE goal SET status = 'pending', status_reason = ?, "
    'updated_at = ? WHERE id = ?',
    (
      f'Deferred while activating goal {target_goal_id}',
      timestamp,
      active_goal['id'],
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
  if goal['status'] not in allowed_statuses:
    statuses = ' or '.join(allowed_statuses)
    raise ProjectError(
      f'Only {statuses} goals can be activated; goal {goal_id} is '
      f'{goal["status"]}'
    )
  if connection.execute(
    'SELECT 1 FROM blocker '
    "WHERE goal_id = ? AND task_id IS NULL AND status = 'open' LIMIT 1",
    (goal_id,),
  ).fetchone():
    raise ProjectError('A goal cannot activate while it has open blockers')
  _handoff_active_goal(connection, goal_id, timestamp)
  if goal['ever_activated']:
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
  _touch(connection)


def create_goal(
  root: ProjectRoot,
  name: str,
  text: str,
  stages: Sequence[StageReference] | str,
) -> int:
  validate_goal_text(text)
  stage_references = (
    (stages,) if isinstance(stages, str) else tuple(stages)
  )
  if not stage_references or any(
    reference is None for reference in stage_references
  ):
    raise ProjectError('A goal must link to at least one stage')
  connection = open_project(root, name)
  try:
    with connection:
      stage_ids: list[int] = []
      for reference in stage_references:
        stage_id = _resolve_stage(connection, reference)
        if stage_id is None:
          raise ProjectError('A goal must link to at least one stage')
        stage_ids.append(stage_id)
      if len(stage_ids) != len(set(stage_ids)):
        raise ProjectError(
          'A goal cannot link the same stage more than once'
        )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO goal
          (text, status, started_at, created_at, updated_at)
        VALUES (?, 'cancelled', 0, ?, ?)
        """,
        (text, timestamp, timestamp),
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
  finally:
    connection.close()


def _blocked_goal_reason(
  connection: sqlite3.Connection, goal_id: int
) -> str:
  blocker = connection.execute(
    'SELECT description FROM blocker WHERE goal_id = ? '
    "AND task_id IS NULL AND status = 'open' "
    'ORDER BY opened_at DESC, id DESC LIMIT 1',
    (goal_id,),
  ).fetchone()
  return blocker['description'] if blocker is not None else ''


def _goal_read_dict(
  connection: sqlite3.Connection, row: sqlite3.Row
) -> GoalRecord:
  goal = dict(row)
  if goal['status'] == 'blocked':
    goal['status_reason'] = _blocked_goal_reason(connection, goal['id'])
  return cast(GoalRecord, goal)


def _read_goal_record(
  connection: sqlite3.Connection, goal_id: int
) -> GoalDetails:
  goal_row = connection.execute(
    'SELECT * FROM goal WHERE id = ?', (goal_id,)
  ).fetchone()
  if goal_row is None:
    raise ProjectError(f'Goal does not exist: {goal_id}')
  goal = _goal_read_dict(
    connection,
    goal_row,
  )
  stages = []
  for row in connection.execute(
    """
    SELECT s.id
    FROM goal_stage gs
    JOIN stage s ON s.id = gs.stage_id
    WHERE gs.goal_id = ?
    ORDER BY s.position, s.id
    """,
    (goal_id,),
  ):
    stage = _stage_record(connection, row['id'])
    stages.append(
      {key: stage[key] for key in ('id', 'name', 'status', 'outcome')}
    )
  tasks = []
  for row in connection.execute(
    """
      SELECT t.*, s.name AS stage_name
      FROM task t
      LEFT JOIN stage s ON s.id = t.stage_id
      WHERE t.goal_id = ?
      ORDER BY t.priority DESC, t.id
      """,
    (goal_id,),
  ).fetchall():
    task = _task_read_dict(row)
    if task is not None:
      tasks.append(task)
  blockers = [
    dict(row)
    for row in connection.execute(
      "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
      'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
      'FROM blocker WHERE goal_id = ? '
      'ORDER BY opened_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  evidence = [
    dict(row)
    for row in connection.execute(
      'SELECT * FROM evidence WHERE goal_id = '
      '? ORDER BY captured_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  decisions = [
    dict(row)
    for row in connection.execute(
      'SELECT * FROM decision WHERE goal_id = '
      '? ORDER BY decided_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  return cast(
    GoalDetails,
    {
      'goal': goal,
      'stages': stages,
      'tasks': tasks,
      'blockers': blockers,
      'evidence': evidence,
      'decisions': decisions,
    },
  )


def read_goals(
  root: ProjectRoot,
  name: str,
  status: GoalStatus | None = None,
) -> list[GoalRecord]:
  if status is not None and status not in GOAL_STATUSES:
    raise ProjectError(f'Invalid goal status: {status}')
  connection = open_project(root, name)
  try:
    condition = 'WHERE g.status = ?' if status else ''
    parameters = (status,) if status else ()
    rows = connection.execute(
      f"""
      SELECT g.*,
        CASE WHEN g.status = 'active' THEN 1 ELSE 0 END AS is_active,
        COALESCE((
          SELECT group_concat(s.name, ', ')
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
    return [_goal_read_dict(connection, row) for row in rows]
  finally:
    connection.close()


def read_goal(
  root: ProjectRoot,
  name: str,
  reference: GoalReference | None = None,
) -> GoalDetails:
  connection = open_project(root, name)
  try:
    return _read_goal_record(
      connection, _resolve_goal(connection, reference)
    )
  finally:
    connection.close()


def goal_text(
  root: ProjectRoot,
  name: str,
  reference: GoalReference | None = None,
) -> str:
  connection = open_project(root, name)
  try:
    goal_id = _resolve_goal(connection, reference)
    return connection.execute(
      'SELECT text FROM goal WHERE id = ?', (goal_id,)
    ).fetchone()['text']
  finally:
    connection.close()


def achieve_goal(
  root: ProjectRoot,
  name: str,
  reference: GoalReference | None = None,
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] != 'active':
        raise ProjectError(
          f'Only active goals can be achieved; goal {goal_id} is '
          f'{goal["status"]}'
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
      timestamp = current_time()
      connection.execute(
        """
        UPDATE goal
        SET status = 'achieved', achieved_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, goal_id),
      )
      _touch(connection)
  finally:
    connection.close()


def cancel_goal(
  root: ProjectRoot,
  name: str,
  reference: GoalReference | None = None,
  reason: str = '',
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] not in ('active', 'pending', 'blocked'):
        raise ProjectError(
          f'Only active, pending, or blocked goals can be cancelled; goal '
          f'{goal_id} is {goal["status"]}'
        )
      _ensure_no_active_task(connection, 'Cancelling a goal', goal_id)
      timestamp = current_time()
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
      _touch(connection)
  finally:
    connection.close()


def reopen_goal(
  root: ProjectRoot,
  name: str,
  reference: GoalReference | None = None,
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] != 'blocked':
        raise ProjectError(
          f'Only blocked goals can be reopened; goal {goal_id} is '
          f'{goal["status"]}'
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
      timestamp = current_time()
      _activate_goal(connection, goal_id, timestamp, ('blocked',))
  finally:
    connection.close()


def activate_goal(
  root: ProjectRoot, name: str, reference: GoalReference
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      timestamp = current_time()
      _activate_goal(connection, goal_id, timestamp, ('pending',))
  finally:
    connection.close()


def block_goal(
  root: ProjectRoot,
  name: str,
  reference: GoalReference | None,
  description: str,
  impact: str = '',
  attempts: str = '',
  required: str = '',
) -> int:
  _require_record_text(description, 'Blocker description')
  _require_record_text(required, 'Blocker requirement')
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] != 'active':
        raise ProjectError(
          f'Only active goals can be blocked; goal {goal_id} is '
          f'{goal["status"]}'
        )
      _ensure_no_active_task(connection, 'Blocking a goal', goal_id)
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, description, impact, attempts, required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (goal_id, description, impact, attempts, required, timestamp),
      )
      connection.execute(
        """
        UPDATE goal
        SET status = 'blocked', status_reason = ?, updated_at = ?
        WHERE id = ?
        """,
        (description, timestamp, goal_id),
      )
      _touch(connection)
      blocker_id = cursor.lastrowid
      if blocker_id is None:
        raise ProjectError(
          'Blocker insertion did not return an identifier'
        )
      return blocker_id
  finally:
    connection.close()


def _project_record(connection: sqlite3.Connection) -> ProjectRecord:
  row = connection.execute('SELECT * FROM project').fetchone()
  if row is None:
    raise ProjectError('Project database has no project record')
  project = dict(row)
  return cast(
    ProjectRecord,
    {
      **project,
      'status': _project_status(connection),
      'completed_at': _project_completed_at(connection),
    },
  )


def read_project(root: ProjectRoot, name: str) -> ProjectView:
  connection = open_project(root, name)
  try:
    project = _project_record(connection)
    state = cast(
      ProjectState,
      _required_record(
        connection.execute('SELECT * FROM project_state').fetchone(),
        'Project state',
      ),
    )
    active_goal = _active_goal(connection)
    goal = (
      _read_goal_record(connection, active_goal['id'])
      if active_goal is not None
      else None
    )
    charter_history = [
      record
      for row in connection.execute(
        'SELECT * FROM project_charter_history '
        'ORDER BY replaced_at DESC, id DESC'
      )
      if (record := _row_dict(row)) is not None
    ]
    return cast(
      ProjectView,
      {
        'path': str(database_path(root, name)),
        'project': project,
        'state': state,
        'goal': goal,
        'charter_history': charter_history,
      },
    )
  finally:
    connection.close()


def list_projects(root: ProjectRoot) -> list[ProjectRecord]:
  directory = project_directory(root)
  if not directory.is_dir():
    return []
  projects = []
  for path in sorted(directory.glob(f'*{PROJECT_SUFFIX}')):
    connection = open_project(root, path.stem)
    try:
      item = _project_record(connection)
      item = {
        key: item[key]
        for key in ('name', 'status', 'objective', 'updated_at')
      }
      item['path'] = str(path)
      projects.append(cast(ProjectRecord, item))
    finally:
      connection.close()
  return projects


def _prepare_project_values(
  values: Mapping[str, object],
) -> dict[str, object]:
  allowed = {
    'objective',
    'scope',
    'non_goals',
    'constraints_text',
    'acceptance',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  unknown = set(values) - allowed
  if unknown:
    raise ProjectError(f'Unknown project fields: {sorted(unknown)}')
  return values


def _apply_project_update(
  connection: sqlite3.Connection, values: Mapping[str, object]
) -> bool:
  if not values:
    return False
  assignments = ', '.join(f'{field} = ?' for field in values)
  try:
    connection.execute(
      f'UPDATE project SET {assignments} WHERE id = 1',
      list(values.values()),
    )
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not update project: {error}') from error
  return True


def update_project(root: ProjectRoot, name: str, **values: object) -> None:
  values = _prepare_project_values(values)
  connection = open_project(root, name)
  try:
    with connection:
      if _apply_project_update(connection, values):
        _touch(connection)
  finally:
    connection.close()


def update_state(
  root: ProjectRoot,
  name: str,
  summary: str | Unset = UNSET,
  next_action: str | Unset = UNSET,
) -> None:
  values = {'summary': summary, 'next_action': next_action}
  connection = open_project(root, name)
  try:
    with connection:
      if _apply_state_update(connection, values):
        _touch(connection)
  finally:
    connection.close()


def _apply_state_update(
  connection: sqlite3.Connection, values: Mapping[str, object]
) -> bool:
  selected = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if not selected:
    return False
  unknown = set(selected) - {'summary', 'next_action'}
  if unknown:
    raise ProjectError(f'Unknown project-state fields: {sorted(unknown)}')
  assignments = ', '.join(f'{field} = ?' for field in selected)
  connection.execute(
    f'UPDATE project_state SET {assignments} WHERE id = 1',
    list(selected.values()),
  )
  return True


def update_project_and_state(
  root: ProjectRoot,
  name: str,
  project_values: Mapping[str, object],
  state_values: Mapping[str, object],
) -> None:
  project_values = _prepare_project_values(project_values)
  connection = open_project(root, name)
  try:
    with connection:
      project_changed = _apply_project_update(connection, project_values)
      state_changed = _apply_state_update(connection, state_values)
      if project_changed or state_changed:
        _touch(connection)
  finally:
    connection.close()


def add_stage(
  root: ProjectRoot,
  name: str,
  stage_name: str,
  outcome: str,
  purpose: str = '',
  entry_conditions: str = '',
  exit_evidence: str = '',
) -> int:
  _require_record_text(stage_name, 'Stage name')
  _require_record_text(outcome, 'Stage outcome')
  connection = open_project(root, name)
  try:
    with connection:
      position = connection.execute(
        'SELECT COALESCE(MAX(position), -1) + 1 FROM stage'
      ).fetchone()[0]
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO stage
          (name, outcome, purpose, entry_conditions, exit_evidence,
           position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          stage_name,
          outcome,
          purpose,
          entry_conditions,
          exit_evidence,
          position,
          timestamp,
          timestamp,
        ),
      )
      _touch(connection)
      return _inserted_id(cursor, 'Stage')
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not add stage: {error}') from error
  finally:
    connection.close()


def read_stages(root: ProjectRoot, name: str) -> list[dict[str, object]]:
  connection = open_project(root, name)
  try:
    stages = []
    for row in connection.execute(
      'SELECT id FROM stage ORDER BY position, id'
    ):
      stage = _stage_record(connection, row['id'])
      dependencies = connection.execute(
        """
        SELECT group_concat(d.name, ', ') AS names
        FROM stage_dependency sd
        JOIN stage d ON d.id = sd.dependency_id
        WHERE sd.stage_id = ?
        """,
        (row['id'],),
      ).fetchone()['names']
      stage['dependencies'] = dependencies or ''
      stages.append(stage)
    return stages
  finally:
    connection.close()


def update_stage(
  root: ProjectRoot,
  project_name: str,
  reference: StageReference,
  **values: object,
) -> None:
  allowed = {
    'name',
    'outcome',
    'purpose',
    'entry_conditions',
    'exit_evidence',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if set(values) - allowed:
    raise ProjectError('Unknown stage field')
  if 'name' in values:
    stage_name = values['name']
    if not isinstance(stage_name, str):
      raise ProjectError('Stage name must be text')
    _require_record_text(stage_name, 'Stage name')
  if 'outcome' in values:
    outcome = values['outcome']
    if not isinstance(outcome, str):
      raise ProjectError('Stage outcome must be text')
    _require_record_text(outcome, 'Stage outcome')
  connection = open_project(root, project_name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, reference)
      if not values:
        return
      assignments = ', '.join(f'{field} = ?' for field in values)
      parameters = [*values.values(), current_time(), stage_id]
      connection.execute(
        f'UPDATE stage SET {assignments}, updated_at = ? WHERE id = ?',
        parameters,
      )
      _touch(connection)
  finally:
    connection.close()


def achieve_stage(
  root: ProjectRoot,
  name: str,
  reference: StageReference,
  evidence: RecordReference,
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, reference)
      if stage_id is None:
        raise ProjectError('A stage reference is required')
      evidence_id = _resolve_evidence(connection, evidence)
      status = _stage_status(connection, stage_id)
      if status == 'achieved':
        raise ProjectError(f'Stage {stage_id} is already achieved')
      generation = connection.execute(
        'SELECT achievement_generation FROM stage WHERE id = ?',
        (stage_id,),
      ).fetchone()['achievement_generation']
      timestamp = current_time()
      try:
        connection.execute(
          """
          INSERT INTO stage_achievement
            (stage_id, evidence_id, achieved_at, stage_generation)
          VALUES (?, ?, ?, ?)
          """,
          (stage_id, evidence_id, timestamp, generation),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not achieve stage: {error}') from error
      connection.execute(
        'UPDATE stage SET updated_at = ? WHERE id = ?',
        (timestamp, stage_id),
      )
      _touch(connection)
  finally:
    connection.close()


def add_stage_dependency(
  root: ProjectRoot,
  name: str,
  reference: StageReference,
  dependency: StageReference,
) -> None:
  connection = open_project(root, name)
  try:
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
      _touch(connection)
  finally:
    connection.close()


def remove_stage_dependency(
  root: ProjectRoot,
  name: str,
  reference: StageReference,
  dependency: StageReference,
) -> None:
  connection = open_project(root, name)
  try:
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
      _touch(connection)
  finally:
    connection.close()


def add_task(
  root: ProjectRoot,
  name: str,
  title: str,
  purpose: str = '',
  stage: StageReference | None = None,
  priority: int = 0,
  tags: Sequence[str] = (),
  goal: GoalReference | None = None,
  scope: str = '',
  exclusions: str = '',
  result: str = '',
  completion_evidence: str = '',
) -> int:
  _require_record_text(title, 'Task title')
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, stage)
      goal_id = (
        _resolve_goal(connection, goal) if goal is not None else None
      )
      _ensure_goal_stage(connection, goal_id, stage_id, 'Task')
      timestamp = current_time()
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
          title,
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
      for tag in tags:
        _insert_tag(connection, task_id, tag)
      _touch(connection)
      return task_id
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not add task: {error}') from error
  finally:
    connection.close()


def _insert_tag(
  connection: sqlite3.Connection, task_id: int, tag: str
) -> None:
  tag = tag.strip()
  if not tag:
    raise ProjectError('Task tags cannot be empty')
  connection.execute(
    'INSERT OR IGNORE INTO task_tag (task_id, tag) VALUES (?, ?)',
    (task_id, tag),
  )


def _task_is_ready(
  connection: sqlite3.Connection, task: TaskRecord
) -> bool:
  if (
    task['status'] != 'pending'
    or task['stage_id'] is None
    or _task_documentation_missing(task)
  ):
    return False
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open'",
    (task['id'],),
  ).fetchone():
    return False
  try:
    _ensure_project_chartered(connection)
    _ensure_stage_contract(connection, task['stage_id'])
    _ensure_task_goal_is_active(connection, task['goal_id'])
    _ensure_goal_stage(
      connection, task['goal_id'], task['stage_id'], 'Task'
    )
    _ensure_task_dependencies_are_achieved(connection, task['stage_id'])
  except ProjectError:
    return False
  return True


def read_tasks(
  root: ProjectRoot,
  name: str,
  status: TaskStatus | None = None,
  stage: StageReference | None = None,
  tag: str | None = None,
  ready: bool = False,
) -> list[TaskRecord]:
  if status is not None and status not in TASK_STATUSES:
    raise ProjectError(f'Invalid task status: {status}')
  connection = open_project(root, name)
  try:
    clauses = []
    parameters = []
    if status:
      clauses.append('t.status = ?')
      parameters.append(status)
    if stage is not None:
      clauses.append('t.stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if tag:
      clauses.append(
        'EXISTS (SELECT 1 FROM task_tag '
        'tt_filter WHERE tt_filter.task_id = t.id '
        'AND tt_filter.tag = ?)'
      )
      parameters.append(tag)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    tasks = [
      task
      for row in connection.execute(
        f"""
        SELECT t.*, s.name AS stage_name,
          COALESCE(
            (SELECT group_concat(tag, ', ') FROM task_tag
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
      if (task := _task_read_dict(row)) is not None
    ]
    if ready:
      tasks = [task for task in tasks if _task_is_ready(connection, task)]
    return tasks
  finally:
    connection.close()


def read_task_logs(
  connection: sqlite3.Connection,
  task_id: int,
  limit: int = 20,
  since: int | None = None,
) -> list[dict[str, object]]:
  if limit <= 0:
    raise ProjectError('Task-log limits must be positive')
  parameters = [task_id]
  condition = ''
  if since is not None:
    condition = ' AND occurred_at >= ?'
    parameters.append(since)
  parameters.append(limit)
  rows = connection.execute(
    'SELECT * FROM task_log WHERE task_id = ?'
    f'{condition} ORDER BY occurred_at DESC, id DESC LIMIT ?',
    parameters,
  ).fetchall()
  return [
    record
    for row in reversed(rows)
    if (record := _row_dict(row)) is not None
  ]


def read_task(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  limit: int = 20,
  since: int | None = None,
) -> TaskDetails:
  connection = open_project(root, name)
  try:
    task_id = _resolve_task(connection, reference)
    task_record = _task_read_dict(
      connection.execute(
        """
        SELECT t.*, s.name AS stage_name,
          COALESCE(
            (SELECT group_concat(tag, ', ') FROM task_tag
             WHERE task_id = t.id),
            ''
          ) AS tags
        FROM task t
        LEFT JOIN stage s ON s.id = t.stage_id
        WHERE t.id = ?
        """,
        (task_id,),
      ).fetchone()
    )
    if task_record is None:
      raise ProjectError(f'Task does not exist: {reference}')
    logs = read_task_logs(connection, task_id, limit, since)
    return cast(TaskDetails, {'task': task_record, 'logs': logs})
  finally:
    connection.close()


def update_task(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  **values: object,
) -> None:
  allowed = {
    'title',
    'purpose',
    'scope',
    'exclusions',
    'result',
    'completion_evidence',
    'priority',
    'stage_id',
    'goal_id',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if set(values) - allowed:
    raise ProjectError('Unknown task field')
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      if 'stage_id' in values:
        stage_reference = values['stage_id']
        if stage_reference is not None and not isinstance(
          stage_reference, (int, str)
        ):
          raise ProjectError('Task stage reference must be text or an ID')
        values['stage_id'] = _resolve_stage(connection, stage_reference)
      if 'goal_id' in values and values['goal_id'] is not None:
        goal_reference = values['goal_id']
        if not isinstance(goal_reference, (int, str)):
          raise ProjectError('Task goal reference must be text or an ID')
        values['goal_id'] = _resolve_goal(connection, goal_reference)
      if not values:
        return
      task = connection.execute(
        'SELECT * FROM task WHERE id = ?', (task_id,)
      ).fetchone()
      target_stage = values.get('stage_id', task['stage_id'])
      target_goal = values.get('goal_id', task['goal_id'])
      if target_stage is not None and not isinstance(target_stage, int):
        raise ProjectError('Task stage ID must be numeric')
      if target_goal is not None and not isinstance(target_goal, int):
        raise ProjectError('Task goal ID must be numeric')
      _ensure_goal_stage(connection, target_goal, target_stage, 'Task')
      if task['status'] == 'active':
        _ensure_task_goal_is_active(connection, target_goal)
        _ensure_task_dependencies_are_achieved(connection, target_stage)
      assignments = ', '.join(f'{field} = ?' for field in values)
      parameters = [*values.values(), current_time(), task_id]
      try:
        connection.execute(
          f'UPDATE task SET {assignments}, updated_at = ? WHERE id = ?',
          parameters,
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not update task: {error}') from error
      _touch(connection)
  finally:
    connection.close()


def append_task_log(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  message: str,
  kind: str = 'note',
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      timestamp = current_time()
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, kind, message),
      )
      connection.execute(
        'UPDATE task SET updated_at = ? WHERE id = ?',
        (timestamp, task_id),
      )
      _touch(connection)
  finally:
    connection.close()


def _ensure_task_can_start(
  connection: sqlite3.Connection, task_id: int
) -> sqlite3.Row:
  task = connection.execute(
    'SELECT * FROM task WHERE id = ?', (task_id,)
  ).fetchone()
  if task['status'] != 'pending':
    raise ProjectError(
      f'Only pending tasks can start; task {task_id} is {task["status"]}'
    )
  _ensure_project_chartered(connection)
  _ensure_task_documented(task)
  if task['stage_id'] is None:
    raise ProjectError('Starting a task requires a stage relationship')
  _ensure_stage_contract(connection, task['stage_id'])
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open' LIMIT 1",
    (task_id,),
  ).fetchone():
    raise ProjectError('Cannot start a task with open blockers')
  _ensure_goal_stage(connection, task['goal_id'], task['stage_id'], 'Task')
  _ensure_task_goal_is_active(connection, task['goal_id'])
  _ensure_task_dependencies_are_achieved(connection, task['stage_id'])
  return task


def start_task(
  root: ProjectRoot, name: str, reference: RecordReference
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      _ensure_task_can_start(connection, task_id)
      timestamp = current_time()
      active_task = _active_task(connection)
      if active_task is not None:
        _return_task_to_pending(
          connection,
          active_task,
          timestamp,
          f'Task returned to pending while activating task {task_id}',
        )
      try:
        connection.execute(
          """
          UPDATE task
          SET status = 'active', started_at = COALESCE(started_at, ?),
            completed_at = NULL, updated_at = ?
          WHERE id = ?
          """,
          (timestamp, timestamp, task_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not start task: {error}') from error
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'started', 'Task started'),
      )
      _touch(connection)
  finally:
    connection.close()


def complete_task(
  root: ProjectRoot, name: str, reference: RecordReference
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
      if task['status'] != 'active':
        raise ProjectError(
          f'Only the active task can complete; task {task_id} is '
          f'{task["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE task
        SET status = 'completed', completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'completed', 'Task completed'),
      )
      _touch(connection)
  finally:
    connection.close()


def reopen_task(
  root: ProjectRoot, name: str, reference: RecordReference
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
      if task['status'] not in ('completed', 'cancelled'):
        raise ProjectError(
          f'Only completed or cancelled tasks can reopen; task '
          f'{task_id} is {task["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE task
        SET status = 'pending', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'reopened', 'Task reopened'),
      )
      _touch(connection)
  finally:
    connection.close()


def cancel_task(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  reason: str = '',
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?', (task_id,)
      ).fetchone()
      if task['status'] not in ('pending', 'active', 'blocked'):
        raise ProjectError(
          f'Only pending, active, or blocked tasks can be cancelled; '
          f'task {task_id} is {task["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE blocker
        SET status = 'withdrawn', resolved_at = ?, resolution = ?
        WHERE task_id = ? AND status = 'open'
        """,
        (timestamp, reason or 'Task cancelled', task_id),
      )
      connection.execute(
        """
        UPDATE task
        SET status = 'cancelled', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'cancelled', reason or 'Task cancelled'),
      )
      _touch(connection)
  finally:
    connection.close()


def block_task(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  description: str,
  impact: str = '',
  attempts: str = '',
  required: str = '',
) -> int:
  _require_record_text(description, 'Blocker description')
  _require_record_text(required, 'Blocker requirement')
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
      if task['status'] not in ('pending', 'active'):
        raise ProjectError(
          f'Only pending or active tasks can be blocked; task {task_id} '
          f'is {task["status"]}'
        )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, stage_id, task_id, description, impact, attempts,
           required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          task['goal_id'],
          task['stage_id'],
          task_id,
          description,
          impact,
          attempts,
          required,
          timestamp,
        ),
      )
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
        (task_id, timestamp, 'blocked', description),
      )
      _touch(connection)
      return _inserted_id(cursor, 'Blocker')
  finally:
    connection.close()


def add_task_tags(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  tags: Sequence[str],
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      for tag in tags:
        _insert_tag(connection, task_id, tag)
      _touch(connection)
  finally:
    connection.close()


def remove_task_tags(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  tags: Sequence[str],
) -> None:
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      for tag in tags:
        connection.execute(
          'DELETE FROM task_tag WHERE task_id = ? AND tag = ?',
          (task_id, tag.strip()),
        )
      _touch(connection)
  finally:
    connection.close()


def add_decision(
  root: ProjectRoot,
  name: str,
  summary: str,
  rationale: str = '',
  alternatives: str = '',
  consequences: str = '',
  stage: StageReference | None = None,
  task: RecordReference | None = None,
  goal: GoalReference | None = None,
) -> int:
  connection = open_project(root, name)
  try:
    with connection:
      stage_id, task_id, goal_id = _resolve_record_relationships(
        connection, 'Decision', stage, task, goal
      )
      timestamp = current_time()
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
          summary,
          rationale,
          alternatives,
          consequences,
          timestamp,
        ),
      )
      _touch(connection)
      return _inserted_id(cursor, 'Decision')
  finally:
    connection.close()


def read_decisions(
  root: ProjectRoot,
  name: str,
  limit: int = 20,
  stage: StageReference | None = None,
  task: RecordReference | None = None,
  goal: GoalReference | None = None,
  no_task: bool = False,
) -> list[dict[str, object]]:
  if limit <= 0:
    raise ProjectError('Decision limits must be positive')
  connection = open_project(root, name)
  try:
    clauses = []
    parameters = []
    if no_task and task is not None:
      raise ProjectError('Decision task and no-task filters conflict')
    if no_task:
      clauses.append('task_id IS NULL')
    if stage is not None:
      clauses.append('stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if task is not None:
      clauses.append('task_id = ?')
      parameters.append(_resolve_task(connection, task))
    if goal is not None:
      clauses.append('goal_id = ?')
      parameters.append(_resolve_goal(connection, goal))
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    parameters.append(limit)
    rows = connection.execute(
      f'SELECT * FROM decision {where} '
      'ORDER BY decided_at DESC, id DESC LIMIT ?',
      parameters,
    ).fetchall()
    return [dict(row) for row in rows]
  finally:
    connection.close()


def add_blocker(
  root: ProjectRoot,
  name: str,
  description: str,
  impact: str = '',
  attempts: str = '',
  required: str = '',
  stage: StageReference | None = None,
  task: RecordReference | None = None,
  goal: GoalReference | None = None,
) -> int:
  _require_record_text(description, 'Blocker description')
  _require_record_text(required, 'Blocker requirement')
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, stage)
      task_id = (
        _resolve_task(connection, task) if task is not None else None
      )
      goal_id = (
        _resolve_goal(connection, goal) if goal is not None else None
      )
      task_record = None
      if task_id is not None:
        task_record = connection.execute(
          'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
          (task_id,),
        ).fetchone()
        if task_record['status'] in ('completed', 'cancelled'):
          raise ProjectError(
            f'Cannot block task {task_id} in status '
            f'{task_record["status"]}'
          )
        if goal_id is None:
          goal_id = task_record['goal_id']
        elif task_record['goal_id'] != goal_id:
          raise ProjectError('Blocker goal does not match task goal')
        if stage_id is None:
          stage_id = task_record['stage_id']
        elif task_record['stage_id'] != stage_id:
          raise ProjectError('Blocker stage does not match task stage')
      elif goal_id is None:
        raise ProjectError('A blocker must target a task or goal')
      _ensure_goal_stage(connection, goal_id, stage_id, 'Blocker')
      goal_status = None
      if goal_id is not None and task_id is None:
        goal_status = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()['status']
        if goal_status not in ('active', 'blocked'):
          raise ProjectError(
            f'Only active or blocked goals can receive blockers; goal '
            f'{goal_id} is {goal_status}'
          )
        _ensure_no_active_task(connection, 'Blocking a goal', goal_id)
      timestamp = current_time()
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
          description,
          impact,
          attempts,
          required,
          timestamp,
        ),
      )
      if task_record is not None and task_record['status'] != 'blocked':
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
          (task_id, timestamp, 'blocked', description),
        )
      if task_id is None:
        connection.execute(
          """
          UPDATE goal
          SET status = 'blocked', status_reason = ?, updated_at = ?
          WHERE id = ?
          """,
          (description, timestamp, goal_id),
        )
      _touch(connection)
      return _inserted_id(cursor, 'Blocker')
  finally:
    connection.close()


def read_blockers(
  root: ProjectRoot,
  name: str,
  status: BlockerStatus | Literal['all'] = 'open',
) -> list[dict[str, object]]:
  connection = open_project(root, name)
  try:
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
    return [dict(row) for row in rows]
  finally:
    connection.close()


def resolve_blocker(
  root: ProjectRoot,
  name: str,
  reference: RecordReference,
  resolution: str,
) -> None:
  _require_record_text(resolution, 'Blocker resolution')
  connection = open_project(root, name)
  try:
    with connection:
      if not str(reference).isdigit():
        raise ProjectError(
          f'Blocker references must be numeric: {reference}'
        )
      blocker = connection.execute(
        """
        SELECT goal_id, task_id
        FROM blocker
        WHERE id = ? AND status = 'open'
        """,
        (int(reference),),
      ).fetchone()
      if blocker is None:
        raise ProjectError(f'Open blocker does not exist: {reference}')
      task_was_blocked = False
      if blocker['task_id'] is not None:
        task = connection.execute(
          'SELECT status FROM task WHERE id = ?', (blocker['task_id'],)
        ).fetchone()
        task_was_blocked = task['status'] == 'blocked'
      remaining_goal = None
      goal_to_reactivate = None
      if blocker['task_id'] is None and blocker['goal_id'] is not None:
        remaining_goal = connection.execute(
          """
          SELECT description FROM blocker
          WHERE goal_id = ? AND task_id IS NULL
            AND status = 'open' AND id <> ?
          ORDER BY opened_at DESC, id DESC LIMIT 1
          """,
          (blocker['goal_id'], int(reference)),
        ).fetchone()
        goal = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker['goal_id'],)
        ).fetchone()
        if remaining_goal is None and goal['status'] == 'blocked':
          goal_to_reactivate = blocker['goal_id']
      timestamp = current_time()
      if goal_to_reactivate is not None:
        _handoff_active_goal(connection, goal_to_reactivate, timestamp)
      connection.execute(
        """
        UPDATE blocker
        SET status = 'resolved', resolved_at = ?, resolution = ?
        WHERE id = ?
        """,
        (timestamp, resolution, int(reference)),
      )
      if blocker['task_id'] is not None:
        connection.execute(
          'UPDATE task SET updated_at = ? WHERE id = ?',
          (timestamp, blocker['task_id']),
        )
        connection.execute(
          'INSERT INTO task_log '
          '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
          (blocker['task_id'], timestamp, 'blocker-resolved', resolution),
        )
        remaining = connection.execute(
          """
          SELECT 1 FROM blocker
          WHERE task_id = ? AND status = 'open'
          LIMIT 1
          """,
          (blocker['task_id'],),
        ).fetchone()
        if remaining is None and task_was_blocked:
          connection.execute(
            'INSERT INTO task_log '
            '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
            (
              blocker['task_id'],
              timestamp,
              'unblocked',
              'All task blockers resolved',
            ),
          )
      if blocker['task_id'] is None and blocker['goal_id'] is not None:
        goal = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker['goal_id'],)
        ).fetchone()
        if goal['status'] == 'blocked':
          if remaining_goal is None:
            raise ProjectError(
              f'Could not reactivate goal {blocker["goal_id"]}'
            )
          connection.execute(
            """
            UPDATE goal
            SET status_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
              remaining_goal['description'],
              timestamp,
              blocker['goal_id'],
            ),
          )
      _touch(connection)
  finally:
    connection.close()


def add_evidence(
  root: ProjectRoot,
  name: str,
  claim: str,
  source: str = '',
  result: str = '',
  stage: StageReference | None = None,
  task: RecordReference | None = None,
  goal: GoalReference | None = None,
) -> int:
  _require_record_text(claim, 'Evidence claim')
  connection = open_project(root, name)
  try:
    with connection:
      stage_id, task_id, goal_id = _resolve_record_relationships(
        connection, 'Evidence', stage, task, goal
      )
      if goal_id is not None:
        goal_status = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()['status']
        if goal_status == 'achieved':
          raise ProjectError('Achieved goal evidence is fixed')
      stage_generation = (
        connection.execute(
          'SELECT achievement_generation FROM stage WHERE id = ?',
          (stage_id,),
        ).fetchone()['achievement_generation']
        if stage_id is not None
        else None
      )
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
          claim,
          source,
          result,
          current_time(),
          stage_generation,
        ),
      )
      _touch(connection)
      return _inserted_id(cursor, 'Evidence')
  finally:
    connection.close()


def read_evidence(
  root: ProjectRoot,
  name: str,
  limit: int = 20,
  stage: StageReference | None = None,
  task: RecordReference | None = None,
  goal: GoalReference | None = None,
  no_task: bool = False,
) -> list[dict[str, object]]:
  if limit <= 0:
    raise ProjectError('Evidence limits must be positive')
  connection = open_project(root, name)
  try:
    clauses = []
    parameters = []
    if no_task and task is not None:
      raise ProjectError('Evidence task and no-task filters conflict')
    if no_task:
      clauses.append('task_id IS NULL')
    if stage is not None:
      clauses.append('stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if task is not None:
      clauses.append('task_id = ?')
      parameters.append(_resolve_task(connection, task))
    if goal is not None:
      clauses.append('goal_id = ?')
      parameters.append(_resolve_goal(connection, goal))
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    parameters.append(limit)
    rows = connection.execute(
      f'SELECT * FROM evidence {where} '
      'ORDER BY captured_at DESC, id DESC LIMIT ?',
      parameters,
    ).fetchall()
    return [dict(row) for row in rows]
  finally:
    connection.close()


def _validate_active_state(
  connection: sqlite3.Connection,
  goal: sqlite3.Row | None,
  task: sqlite3.Row | None,
) -> None:
  if task is None:
    return
  _ensure_task_documented(dict(task))
  if task['stage_id'] is None:
    raise ProjectError('Active task has no stage relationship')
  goal_id = goal['id'] if goal is not None else None
  if task['goal_id'] is not None and task['goal_id'] != goal_id:
    raise ProjectError('Active task goal does not match the active goal')
  _ensure_goal_stage(
    connection, task['goal_id'], task['stage_id'], 'Active task'
  )
  _ensure_task_dependencies_are_achieved(connection, task['stage_id'])
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open'",
    (task['id'],),
  ).fetchone():
    raise ProjectError('Active task has an open blocker')


def _handoff_page(
  connection: sqlite3.Connection,
  query: str,
  count_query: str,
  parameters: Sequence[object] = (),
) -> tuple[list[dict[str, object]], dict[str, int | bool]]:
  count_row = connection.execute(count_query, parameters).fetchone()
  if count_row is None:
    raise ProjectError('Handoff page count returned no row')
  total = count_row[0]
  if not isinstance(total, int):
    raise ProjectError('Handoff page count was not an integer')
  rows = [
    record
    for row in connection.execute(
      f'{query} LIMIT ?', (*parameters, HANDOFF_LIMIT)
    ).fetchall()
    if (record := _row_dict(row)) is not None
  ]
  return rows, {
    'shown': len(rows),
    'total': total,
    'truncated': total > len(rows),
  }


def read_handoff(root: ProjectRoot, name: str) -> HandoffData:
  connection = open_project(root, name)
  try:
    project = _project_record(connection)
    state = cast(
      ProjectState,
      _required_record(
        connection.execute('SELECT * FROM project_state').fetchone(),
        'Project state',
      ),
    )
    active_goal = _active_goal(connection)
    active_task = _active_task(connection)
    _validate_active_state(connection, active_goal, active_task)
    goal = None
    if active_goal is not None:
      goal = {
        'goal': _row_dict(
          connection.execute(
            'SELECT * FROM goal WHERE id = ?', (active_goal['id'],)
          ).fetchone()
        )
      }
    task = _task_read_dict(active_task)
    task_stage_id = task.get('stage_id') if task is not None else None
    stage = (
      _stage_record(connection, task_stage_id)
      if isinstance(task_stage_id, int)
      else None
    )
    blocked_tasks, blocked_task_page = _handoff_page(
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
    blocked_tasks = [
      task_record
      for item in blocked_tasks
      if (task_record := _task_read_dict(item)) is not None
    ]
    blocked_goals, blocked_goal_page = _handoff_page(
      connection,
      """
      SELECT id, text, status, status_reason, updated_at
      FROM goal
      WHERE status = 'blocked'
      ORDER BY updated_at DESC, id DESC
      """,
      "SELECT count(*) FROM goal WHERE status = 'blocked'",
    )
    for blocked_goal in blocked_goals:
      goal_id = blocked_goal.get('id')
      if not isinstance(goal_id, int):
        raise ProjectError('Blocked goal record has no numeric ID')
      blocked_goal['status_reason'] = _blocked_goal_reason(
        connection, goal_id
      )
    blockers, blocker_page = _handoff_page(
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
    focus_task_id = (
      task['id']
      if task is not None
      else blocked_tasks[0]['id']
      if blocked_tasks
      else None
    )
    focus_goal_id = (
      active_goal['id']
      if active_goal is not None
      else blocked_goals[0]['id']
      if blocked_goals
      else None
    )
    if focus_task_id is not None:
      focus_clause = 'task_id = ?'
      focus_parameters = (focus_task_id,)
      focus_kind = 'task'
      focus_id = focus_task_id
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
    decisions, decision_page = _handoff_page(
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
    evidence, evidence_page = _handoff_page(
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
    logs = []
    log_page = {'shown': 0, 'total': 0, 'truncated': False}
    if focus_task_id is not None:
      logs, log_page = _handoff_page(
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
    data = {
      'path': str(Path('.tmp') / f'{name}{PROJECT_SUFFIX}'),
      'project': project,
      'state': state,
      'goal': goal,
      'stage': stage,
      'task': task,
      'blocked_tasks': blocked_tasks,
      'blocked_goals': blocked_goals,
      'blockers': blockers,
      'decisions': decisions,
      'evidence': evidence,
      'logs': logs,
      'focus': {'kind': focus_kind, 'id': focus_id},
      'pages': {
        'blocked_tasks': blocked_task_page,
        'blocked_goals': blocked_goal_page,
        'blockers': blocker_page,
        'decisions': decision_page,
        'evidence': evidence_page,
        'task_log': log_page,
      },
    }
    return cast(HandoffData, data)
  finally:
    connection.close()
