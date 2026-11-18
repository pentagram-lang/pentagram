from __future__ import annotations

import sqlite3
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Literal

from proj.db import ProjectError, is_substantive, require_substantive

HANDOFF_LIMIT = 5

TaskStatus = Literal[
  'pending', 'active', 'blocked', 'completed', 'cancelled'
]
StageStatus = Literal[
  'pending', 'active', 'blocked', 'achieved', 'superseded'
]
ProjectStatus = Literal['active', 'blocked', 'complete']
GoalStatus = Literal[
  'active', 'pending', 'blocked', 'achieved', 'cancelled'
]
BlockerStatus = Literal['open', 'resolved', 'withdrawn']
StageRef = int | str
GoalRef = int | Literal['active']
type JsonValue = (
  None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)

CHARTER_FIELDS = (
  'objective',
  'scope',
  'non_goals',
  'constraints_text',
  'acceptance',
)
TASK_PROSE_FIELDS = (
  'title',
  'purpose',
  'scope',
  'exclusions',
  'result',
  'completion_evidence',
)


@dataclass(frozen=True, slots=True)
class ProjectSummary:
  name: str
  status: ProjectStatus
  objective: str
  summary: str
  next_action: str
  created_at: int
  updated_at: int


@dataclass(frozen=True, slots=True)
class ProjectView:
  name: str
  status: ProjectStatus
  objective: str
  scope: str
  non_goals: str
  constraints_text: str
  acceptance: str
  summary: str
  next_action: str
  charter_complete: bool
  created_at: int
  updated_at: int


@dataclass(frozen=True, slots=True)
class StageView:
  id: int
  name: str
  outcome: str
  purpose: str
  entry_conditions: str
  exit_evidence: str
  position: int
  status: StageStatus
  dependencies: tuple[int, ...]
  achievement_evidence_id: int | None
  achieved_at: int | None
  created_at: int
  updated_at: int


@dataclass(frozen=True, slots=True)
class GoalView:
  id: int
  text: str
  status: GoalStatus
  status_reason: str
  stages: tuple[int, ...]
  created_at: int
  started_at: int
  achieved_at: int | None
  updated_at: int


@dataclass(frozen=True, slots=True)
class TaskView:
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
  tags: tuple[str, ...]
  created_at: int
  started_at: int | None
  completed_at: int | None
  updated_at: int


@dataclass(frozen=True, slots=True)
class TaskLog:
  id: int
  task_id: int
  occurred_at: int
  kind: str
  message: str


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


@dataclass(frozen=True, slots=True)
class GoalDetails:
  goal: GoalView
  tasks: tuple[TaskView, ...]
  blockers: tuple[BlockerRecord, ...]
  decisions: tuple[DecisionRecord, ...]
  evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class TaskDetails:
  task: TaskView
  logs: tuple[TaskLog, ...]
  blockers: tuple[BlockerRecord, ...]
  decisions: tuple[DecisionRecord, ...]
  evidence: tuple[EvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class HandoffData:
  project: ProjectView
  active_goal: GoalView | None
  active_task: TaskView | None
  active_stage: StageView | None
  open_blockers: tuple[BlockerRecord, ...]
  blocked_tasks: tuple[TaskView, ...]
  blocked_goals: tuple[GoalView, ...]
  focus_kind: Literal['task', 'goal'] | None
  focus_id: int | None
  decisions: tuple[DecisionRecord, ...]
  decisions_total: int
  evidence: tuple[EvidenceRecord, ...]
  evidence_total: int
  task_logs: tuple[TaskLog, ...]
  task_logs_total: int


def _to_json(val: object) -> JsonValue:
  if is_dataclass(val) and not isinstance(val, type):
    return {f.name: _to_json(getattr(val, f.name)) for f in fields(val)}
  if isinstance(val, (list, tuple)):
    return [_to_json(x) for x in val]
  if isinstance(val, dict):
    return {str(k): _to_json(v) for k, v in val.items()}
  if isinstance(val, (bool, int, float, str)) or val is None:
    return val
  raise TypeError(f'Unsupported JSON value: {type(val).__name__}')


def dataclass_to_dict(obj: object) -> dict[str, JsonValue]:
  if not (is_dataclass(obj) and not isinstance(obj, type)):
    raise TypeError('Expected a dataclass instance')
  return {f.name: _to_json(getattr(obj, f.name)) for f in fields(obj)}


def derive_stage_status(
  task_statuses: Sequence[TaskStatus], achieved: bool
) -> StageStatus:
  if 'active' in task_statuses:
    return 'active'
  if 'pending' in task_statuses:
    return 'pending'
  if 'blocked' in task_statuses:
    return 'blocked'
  if (
    achieved
    and 'completed' in task_statuses
    and all(s in ('completed', 'cancelled') for s in task_statuses)
  ):
    return 'achieved'
  if task_statuses and all(s == 'cancelled' for s in task_statuses):
    return 'superseded'
  return 'pending'


def derive_project_status(
  stage_statuses: Sequence[StageStatus],
) -> ProjectStatus:
  if 'achieved' in stage_statuses and all(
    s in ('achieved', 'superseded') for s in stage_statuses
  ):
    return 'complete'
  if any(s in ('active', 'pending') for s in stage_statuses):
    return 'active'
  if 'blocked' in stage_statuses:
    return 'blocked'
  return 'active'


def parse_stage_ref(raw: StageRef) -> int | str:
  if isinstance(raw, bool):
    raise ProjectError('Stage reference must not be a boolean')
  if isinstance(raw, int):
    if raw <= 0:
      raise ProjectError('Stage ID must be positive')
    return raw
  if not raw:
    raise ProjectError('Stage reference must not be empty')
  if raw.isascii() and raw.isdigit():
    val = int(raw)
    if val <= 0:
      raise ProjectError('Stage ID must be positive')
    return val
  return raw


def parse_goal_ref(raw: GoalRef | str) -> int | Literal['active']:
  if isinstance(raw, bool):
    raise ProjectError('Goal reference must not be a boolean')
  if isinstance(raw, int):
    if raw <= 0:
      raise ProjectError('Goal ID must be positive')
    return raw
  if raw == 'active':
    return 'active'
  if raw.isascii() and raw.isdigit():
    val = int(raw)
    if val <= 0:
      raise ProjectError('Goal ID must be positive')
    return val
  raise ProjectError(f'Invalid goal reference: {raw!r}')


def _now(now: int | None) -> int:
  return int(time.time()) if now is None else now


def _exists(
  conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()
) -> bool:
  return conn.execute(sql, params).fetchone() is not None


def _require_row(
  conn: sqlite3.Connection,
  sql: str,
  params: tuple[object, ...],
  msg: str,
) -> sqlite3.Row:
  row = conn.execute(sql, params).fetchone()
  if row is None:
    raise ProjectError(msg)
  return row


def _update_cols(
  conn: sqlite3.Connection,
  table: str,
  row_id: int,
  updates: Mapping[str, object],
  ts: int,
) -> None:
  cols = ', '.join(f'{k} = ?' for k in updates)
  conn.execute(
    f'UPDATE {table} SET {cols}, updated_at = ? WHERE id = ?',
    (*updates.values(), ts, row_id),
  )


def _charter_complete(row: sqlite3.Row) -> bool:
  return all(is_substantive(row[col]) for col in CHARTER_FIELDS)


def _execution_begun(conn: sqlite3.Connection) -> bool:
  return _exists(
    conn,
    'SELECT 1 FROM task WHERE started_at IS NOT NULL '
    "OR status IN ('active', 'completed') LIMIT 1",
  )


def _transitive_reach(
  adj: Mapping[int, Sequence[int]], start: int
) -> set[int]:
  seen: set[int] = set()
  stack = list(adj.get(start, ()))
  while stack:
    node = stack.pop()
    if node not in seen:
      seen.add(node)
      stack.extend(adj.get(node, ()))
  return seen


def _stage_maps(
  conn: sqlite3.Connection,
) -> tuple[dict[int, tuple[int, ...]], dict[int, list[int]]]:
  deps: dict[int, list[int]] = {}
  rev: dict[int, list[int]] = {}
  for r in conn.execute(
    'SELECT stage_id, dependency_id FROM stage_dependency '
    'ORDER BY dependency_id ASC'
  ):
    sid, did = int(r['stage_id']), int(r['dependency_id'])
    deps.setdefault(sid, []).append(did)
    rev.setdefault(did, []).append(sid)
  return {k: tuple(v) for k, v in deps.items()}, rev


def _stage_view(
  r: sqlite3.Row, deps: tuple[int, ...], statuses: Sequence[TaskStatus]
) -> StageView:
  return StageView(
    r['id'],
    r['name'],
    r['outcome'],
    r['purpose'],
    r['entry_conditions'],
    r['exit_evidence'],
    r['position'],
    derive_stage_status(
      statuses, r['achievement_evidence_id'] is not None
    ),
    deps,
    r['achievement_evidence_id'],
    r['achieved_at'],
    r['created_at'],
    r['updated_at'],
  )


def _goal_view(r: sqlite3.Row, stages: tuple[int, ...]) -> GoalView:
  return GoalView(
    r['id'],
    r['text'],
    r['status'],
    r['status_reason'],
    stages,
    r['created_at'],
    r['started_at'],
    r['achieved_at'],
    r['updated_at'],
  )


def _task_view(r: sqlite3.Row, tags: tuple[str, ...]) -> TaskView:
  return TaskView(
    r['id'],
    r['goal_id'],
    r['stage_id'],
    r['title'],
    r['purpose'],
    r['scope'],
    r['exclusions'],
    r['result'],
    r['completion_evidence'],
    r['status'],
    r['priority'],
    tags,
    r['created_at'],
    r['started_at'],
    r['completed_at'],
    r['updated_at'],
  )


def _row_as[T](cls: type[T], r: sqlite3.Row) -> T:
  return cls(*r)


def _resolve_stage(conn: sqlite3.Connection, ref: StageRef) -> sqlite3.Row:
  parsed = parse_stage_ref(ref)
  col = 'id' if isinstance(parsed, int) else 'name'
  return _require_row(
    conn,
    f'SELECT * FROM stage WHERE {col} = ?',
    (parsed,),
    f'No stage: {ref!r}',
  )


def _resolve_goal(
  conn: sqlite3.Connection, ref: GoalRef | str = 'active'
) -> sqlite3.Row:
  parsed = parse_goal_ref(ref)
  if parsed == 'active':
    return _require_row(
      conn,
      "SELECT * FROM goal WHERE status = 'active'",
      (),
      'No active goal',
    )
  return _require_row(
    conn,
    'SELECT * FROM goal WHERE id = ?',
    (parsed,),
    f'No goal: {parsed}',
  )


def _resolve_task(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
  if isinstance(task_id, bool) or task_id <= 0:
    raise ProjectError('Task ID must be a positive integer')
  return _require_row(
    conn,
    'SELECT * FROM task WHERE id = ?',
    (task_id,),
    f'No task: {task_id}',
  )


def _append_log(
  conn: sqlite3.Connection, task_id: int, kind: str, message: str, ts: int
) -> TaskLog:
  cur = conn.execute(
    'INSERT INTO task_log (task_id, occurred_at, kind, message) '
    'VALUES (?, ?, ?, ?)',
    (task_id, ts, kind, message),
  )
  return _row_as(
    TaskLog,
    _require_row(
      conn, 'SELECT * FROM task_log WHERE id = ?', (cur.lastrowid,), 'Log'
    ),
  )


def _invalidate_stage_achievement(
  conn: sqlite3.Connection,
  stage_id: int,
  ts: int,
  *,
  exclude_task_id: int | None = None,
) -> None:
  row = _require_row(
    conn, 'SELECT * FROM stage WHERE id = ?', (stage_id,), 'Stage missing'
  )
  if row['achievement_evidence_id'] is None:
    return
  _, rev = _stage_maps(conn)
  deps = _transitive_reach(rev, stage_id)
  if deps:
    marks = ','.join('?' for _ in deps)
    excl = 'AND id != ? ' if exclude_task_id is not None else ''
    params: tuple[object, ...] = (
      (*deps, exclude_task_id)
      if exclude_task_id is not None
      else tuple(deps)
    )
    if _exists(
      conn,
      f"SELECT 1 FROM task WHERE status = 'active' "
      f'AND stage_id IN ({marks}) {excl}LIMIT 1',
      params,
    ):
      raise ProjectError(
        'Cannot invalidate achieved stage with active dependent task'
      )
  target_ids = (stage_id, *deps)
  tmarks = ','.join('?' for _ in target_ids)
  conn.execute(
    'UPDATE stage SET achievement_evidence_id = NULL, '
    f'achieved_at = NULL, updated_at = ? WHERE id IN ({tmarks}) '
    'AND achievement_evidence_id IS NOT NULL',
    (ts, *target_ids),
  )


def _handoff_active_goal(
  conn: sqlite3.Connection, reason: str, ts: int
) -> None:
  old = conn.execute(
    "SELECT id FROM goal WHERE status = 'active'"
  ).fetchone()
  if old is None:
    return
  old_id = int(old['id'])
  for trow in conn.execute(
    "SELECT id FROM task WHERE goal_id = ? AND status = 'active'",
    (old_id,),
  ).fetchall():
    tid = int(trow['id'])
    conn.execute(
      "UPDATE task SET status = 'pending', updated_at = ? WHERE id = ?",
      (ts, tid),
    )
    _append_log(conn, tid, 'handoff', reason, ts)
  conn.execute(
    "UPDATE goal SET status = 'pending', status_reason = ?, "
    'updated_at = ? WHERE id = ?',
    (reason, ts, old_id),
  )


def _set_goal_active(conn: sqlite3.Connection, gid: int, ts: int) -> None:
  _handoff_active_goal(conn, f'Deferred for goal {gid}', ts)
  conn.execute(
    "UPDATE goal SET status = 'active', status_reason = '', "
    'updated_at = ? WHERE id = ?',
    (ts, gid),
  )


def read_project_summary(conn: sqlite3.Connection) -> ProjectSummary:
  r = _require_row(
    conn, 'SELECT * FROM project WHERE id = 1', (), 'No project'
  )
  statuses: list[StageStatus] = [s.status for s in list_stages(conn)]
  status = derive_project_status(statuses)
  return ProjectSummary(
    r['name'],
    status,
    r['objective'],
    r['summary'],
    r['next_action'],
    r['created_at'],
    r['updated_at'],
  )


def read_project(conn: sqlite3.Connection) -> ProjectView:
  r = _require_row(
    conn, 'SELECT * FROM project WHERE id = 1', (), 'No project'
  )
  statuses: list[StageStatus] = [s.status for s in list_stages(conn)]
  status = derive_project_status(statuses)
  return ProjectView(
    r['name'],
    status,
    r['objective'],
    r['scope'],
    r['non_goals'],
    r['constraints_text'],
    r['acceptance'],
    r['summary'],
    r['next_action'],
    _charter_complete(r),
    r['created_at'],
    r['updated_at'],
  )


def update_project(
  conn: sqlite3.Connection,
  *,
  objective: str | None = None,
  scope: str | None = None,
  non_goals: str | None = None,
  constraints_text: str | None = None,
  acceptance: str | None = None,
  summary: str | None = None,
  next_action: str | None = None,
  now: int | None = None,
) -> ProjectView:
  ts = _now(now)
  if objective is not None:
    require_substantive(objective, 'objective')
  updates = {
    k: v
    for k, v in (
      ('objective', objective),
      ('scope', scope),
      ('non_goals', non_goals),
      ('constraints_text', constraints_text),
      ('acceptance', acceptance),
      ('summary', summary),
      ('next_action', next_action),
    )
    if v is not None
  }
  if not updates:
    return read_project(conn)
  with conn:
    row = _require_row(
      conn, 'SELECT * FROM project WHERE id = 1', (), 'No project'
    )
    begun = _execution_begun(conn)
    changed = False
    for col in CHARTER_FIELDS:
      if col in updates:
        if begun:
          require_substantive(updates[col], col)
        if updates[col] != row[col]:
          changed = True
    if begun and changed:
      if _exists(
        conn, "SELECT 1 FROM task WHERE status = 'active' LIMIT 1"
      ):
        raise ProjectError('Cannot re-charter while a task is active')
      if _exists(
        conn,
        'SELECT 1 FROM goal '
        "WHERE status IN ('active', 'pending', 'blocked') LIMIT 1",
      ):
        raise ProjectError('Cannot re-charter with open goals')
      conn.execute(
        'UPDATE stage SET achievement_evidence_id = NULL, '
        'achieved_at = NULL'
      )
    _update_cols(conn, 'project', 1, updates, ts)
  return read_project(conn)


def list_stages(conn: sqlite3.Connection) -> list[StageView]:
  deps, _ = _stage_maps(conn)
  tasks_by_stage: dict[int, list[TaskStatus]] = {}
  for trow in conn.execute(
    'SELECT stage_id, status FROM task WHERE stage_id IS NOT NULL'
  ):
    tasks_by_stage.setdefault(int(trow['stage_id']), []).append(
      trow['status']
    )
  rows = conn.execute(
    'SELECT * FROM stage ORDER BY position ASC, id ASC'
  ).fetchall()
  return [
    _stage_view(
      r, deps.get(int(r['id']), ()), tasks_by_stage.get(int(r['id']), ())
    )
    for r in rows
  ]


def _get_stage_view(conn: sqlite3.Connection, stage_id: int) -> StageView:
  for s in list_stages(conn):
    if s.id == stage_id:
      return s
  raise ProjectError(f'Stage not found: {stage_id}')


def _validate_stage_name(name: str) -> None:
  require_substantive(name, 'stage name')
  if name.isascii() and name.isdigit():
    raise ProjectError(
      'Stage name must not consist solely of ASCII digits'
    )


def create_stage(
  conn: sqlite3.Connection,
  *,
  name: str,
  outcome: str,
  purpose: str = '',
  entry_conditions: str = '',
  exit_evidence: str = '',
  position: int | None = None,
  dependencies: Sequence[StageRef] = (),
  now: int | None = None,
) -> StageView:
  _validate_stage_name(name)
  require_substantive(outcome, 'stage outcome')
  ts = _now(now)
  with conn:
    dep_ids = list(
      dict.fromkeys(
        int(_resolve_stage(conn, r)['id']) for r in dependencies
      )
    )
    pos = (
      int(
        conn.execute(
          'SELECT COALESCE(MAX(position), 0) + 1 FROM stage'
        ).fetchone()[0]
      )
      if position is None
      else position
    )
    try:
      cur = conn.execute(
        'INSERT INTO stage (name, outcome, purpose, entry_conditions, '
        'exit_evidence, position, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (
          name,
          outcome,
          purpose,
          entry_conditions,
          exit_evidence,
          pos,
          ts,
          ts,
        ),
      )
    except sqlite3.IntegrityError as exc:
      raise ProjectError(f'Stage already exists: {name!r}') from exc
    sid = int(cur.lastrowid or 0)
    for did in dep_ids:
      conn.execute(
        'INSERT INTO stage_dependency (stage_id, dependency_id) '
        'VALUES (?, ?)',
        (sid, did),
      )
  return _get_stage_view(conn, sid)


def update_stage(
  conn: sqlite3.Connection,
  stage_ref: StageRef,
  *,
  name: str | None = None,
  outcome: str | None = None,
  purpose: str | None = None,
  entry_conditions: str | None = None,
  exit_evidence: str | None = None,
  position: int | None = None,
  now: int | None = None,
) -> StageView:
  ts = _now(now)
  if name is not None:
    _validate_stage_name(name)
  if outcome is not None:
    require_substantive(outcome, 'stage outcome')
  updates: dict[str, object] = {
    k: v
    for k, v in (
      ('name', name),
      ('outcome', outcome),
      ('purpose', purpose),
      ('entry_conditions', entry_conditions),
      ('exit_evidence', exit_evidence),
      ('position', position),
    )
    if v is not None
  }
  with conn:
    row = _resolve_stage(conn, stage_ref)
    sid = int(row['id'])
    if not updates:
      return _get_stage_view(conn, sid)
    if any(
      k in updates and updates[k] != row[k]
      for k in ('outcome', 'exit_evidence')
    ):
      _invalidate_stage_achievement(conn, sid, ts)
    try:
      _update_cols(conn, 'stage', sid, updates, ts)
    except sqlite3.IntegrityError as exc:
      raise ProjectError(f'Stage name conflict: {name!r}') from exc
  return _get_stage_view(conn, sid)


def add_stage_dependency(
  conn: sqlite3.Connection,
  stage_ref: StageRef,
  dep_ref: StageRef,
  *,
  now: int | None = None,
) -> StageView:
  ts = _now(now)
  with conn:
    sid = int(_resolve_stage(conn, stage_ref)['id'])
    did = int(_resolve_stage(conn, dep_ref)['id'])
    if sid == did:
      raise ProjectError('Stage cannot depend on itself')
    deps, _ = _stage_maps(conn)
    if did in deps.get(sid, ()):
      raise ProjectError('Stage dependency already exists')
    if sid in _transitive_reach(deps, did):
      raise ProjectError('Stage dependency would create a cycle')
    if _get_stage_view(conn, did).status != 'achieved':
      if _exists(
        conn,
        'SELECT 1 FROM task '
        "WHERE stage_id = ? AND status = 'active' LIMIT 1",
        (sid,),
      ):
        raise ProjectError(
          'Cannot add unachieved dependency to a stage with an active task'
        )
      _invalidate_stage_achievement(conn, sid, ts)
    conn.execute(
      'INSERT INTO stage_dependency (stage_id, dependency_id) '
      'VALUES (?, ?)',
      (sid, did),
    )
  return _get_stage_view(conn, sid)


def remove_stage_dependency(
  conn: sqlite3.Connection, stage_ref: StageRef, dep_ref: StageRef
) -> StageView:
  with conn:
    sid = int(_resolve_stage(conn, stage_ref)['id'])
    did = int(_resolve_stage(conn, dep_ref)['id'])
    if _exists(
      conn,
      'SELECT 1 FROM task '
      "WHERE stage_id = ? AND status = 'active' LIMIT 1",
      (sid,),
    ):
      raise ProjectError('Cannot remove dependency while stage is active')
    cur = conn.execute(
      'DELETE FROM stage_dependency '
      'WHERE stage_id = ? AND dependency_id = ?',
      (sid, did),
    )
    if cur.rowcount == 0:
      raise ProjectError('Stage dependency does not exist')
  return _get_stage_view(conn, sid)


def achieve_stage(
  conn: sqlite3.Connection,
  stage_ref: StageRef,
  evidence_id: int,
  *,
  now: int | None = None,
) -> StageView:
  ts = _now(now)
  with conn:
    proj = _require_row(
      conn, 'SELECT * FROM project WHERE id = 1', (), 'Project missing'
    )
    if not _charter_complete(proj):
      raise ProjectError('Charter must be complete to achieve stage')
    stage = _resolve_stage(conn, stage_ref)
    sid = int(stage['id'])
    if stage['achievement_evidence_id'] is not None:
      raise ProjectError('Stage is already achieved')
    if not all(
      is_substantive(stage[c])
      for c in ('name', 'outcome', 'exit_evidence')
    ):
      raise ProjectError(
        'Stage name, outcome, and exit_evidence must be substantive'
      )
    stages = {s.id: s for s in list_stages(conn)}
    for dep_id in _transitive_reach(
      {s.id: s.dependencies for s in stages.values()}, sid
    ):
      if stages[dep_id].status != 'achieved':
        raise ProjectError(f'Stage dependency {dep_id} is not achieved')
    tasks = conn.execute(
      'SELECT status, completed_at FROM task WHERE stage_id = ?', (sid,)
    ).fetchall()
    if any(t['status'] in ('pending', 'active', 'blocked') for t in tasks):
      raise ProjectError('Stage still has open tasks')
    completed = [t for t in tasks if t['status'] == 'completed']
    if not completed:
      raise ProjectError('Stage requires at least one completed task')
    if any(
      t['completed_at'] is not None and int(t['completed_at']) > ts
      for t in completed
    ):
      raise ProjectError('Achievement cannot precede completed task work')
    ev = _require_row(
      conn,
      'SELECT * FROM evidence WHERE id = ?',
      (evidence_id,),
      f'Evidence not found: {evidence_id}',
    )
    if ev['stage_id'] != sid:
      raise ProjectError('Evidence does not belong to this stage')
    if not is_substantive(ev['claim']):
      raise ProjectError('Achievement evidence claim must be substantive')
    if int(ev['captured_at']) > ts:
      raise ProjectError(
        'Achievement time cannot precede evidence capture'
      )
    conn.execute(
      'UPDATE stage SET achievement_evidence_id = ?, achieved_at = ?, '
      'updated_at = ? WHERE id = ?',
      (evidence_id, ts, ts, sid),
    )
  return _get_stage_view(conn, sid)


def _goal_stages_map(
  conn: sqlite3.Connection,
) -> dict[int, tuple[int, ...]]:
  res: dict[int, list[int]] = {}
  for r in conn.execute(
    'SELECT goal_id, stage_id FROM goal_stage ORDER BY stage_id ASC'
  ):
    res.setdefault(int(r['goal_id']), []).append(int(r['stage_id']))
  return {k: tuple(v) for k, v in res.items()}


def list_goals(conn: sqlite3.Connection) -> list[GoalView]:
  stages = _goal_stages_map(conn)
  return [
    _goal_view(r, stages.get(int(r['id']), ()))
    for r in conn.execute('SELECT * FROM goal ORDER BY id ASC')
  ]


def _get_goal_view(conn: sqlite3.Connection, goal_id: int) -> GoalView:
  row = _require_row(
    conn, 'SELECT * FROM goal WHERE id = ?', (goal_id,), 'Goal missing'
  )
  srows = conn.execute(
    'SELECT stage_id FROM goal_stage WHERE goal_id = ? '
    'ORDER BY stage_id ASC',
    (goal_id,),
  ).fetchall()
  return _goal_view(row, tuple(int(r['stage_id']) for r in srows))


def get_goal_text(
  conn: sqlite3.Connection, goal_ref: GoalRef | str = 'active'
) -> str:
  return str(_resolve_goal(conn, goal_ref)['text'])


def _scope_records(
  conn: sqlite3.Connection, col: str, val: int
) -> tuple[
  tuple[BlockerRecord, ...],
  tuple[DecisionRecord, ...],
  tuple[EvidenceRecord, ...],
]:
  blockers = tuple(
    _row_as(BlockerRecord, r)
    for r in conn.execute(
      f'SELECT * FROM blocker WHERE {col} = ? '
      'ORDER BY opened_at DESC, id DESC',
      (val,),
    )
  )
  decisions = tuple(
    _row_as(DecisionRecord, r)
    for r in conn.execute(
      f'SELECT * FROM decision WHERE {col} = ? '
      'ORDER BY decided_at DESC, id DESC',
      (val,),
    )
  )
  evidence = tuple(
    _row_as(EvidenceRecord, r)
    for r in conn.execute(
      f'SELECT * FROM evidence WHERE {col} = ? '
      'ORDER BY captured_at DESC, id DESC',
      (val,),
    )
  )
  return blockers, decisions, evidence


def show_goal(
  conn: sqlite3.Connection, goal_ref: GoalRef | str = 'active'
) -> GoalDetails:
  gid = int(_resolve_goal(conn, goal_ref)['id'])
  blockers, decisions, evidence = _scope_records(conn, 'goal_id', gid)
  return GoalDetails(
    _get_goal_view(conn, gid),
    tuple(list_tasks(conn, goal=gid)),
    blockers,
    decisions,
    evidence,
  )


def create_goal(
  conn: sqlite3.Connection,
  *,
  text: str,
  stages: Sequence[StageRef],
  now: int | None = None,
) -> GoalView:
  require_substantive(text, 'goal text')
  if len(text) > 4000 or '\x00' in text:
    raise ProjectError('Goal text exceeds 4000 chars or contains NUL')
  if not stages:
    raise ProjectError('Goal must reference at least one stage')
  ts = _now(now)
  with conn:
    stage_ids = list(
      dict.fromkeys(int(_resolve_stage(conn, r)['id']) for r in stages)
    )
    cur = conn.execute(
      'INSERT INTO goal (text, status, status_reason, created_at, '
      "started_at, updated_at) VALUES (?, 'pending', '', ?, ?, ?)",
      (text, ts, ts, ts),
    )
    gid = int(cur.lastrowid or 0)
    _set_goal_active(conn, gid, ts)
    for sid in stage_ids:
      conn.execute(
        'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
        (gid, sid),
      )
  return _get_goal_view(conn, gid)


def activate_goal(
  conn: sqlite3.Connection,
  goal_ref: GoalRef | str,
  *,
  now: int | None = None,
) -> GoalView:
  ts = _now(now)
  with conn:
    row = _resolve_goal(conn, goal_ref)
    if row['status'] != 'pending':
      raise ProjectError('Only pending goals can be activated')
    gid = int(row['id'])
    _set_goal_active(conn, gid, ts)
  return _get_goal_view(conn, gid)


def achieve_goal(
  conn: sqlite3.Connection,
  goal_ref: GoalRef | str = 'active',
  *,
  now: int | None = None,
) -> GoalView:
  ts = _now(now)
  with conn:
    row = _resolve_goal(conn, goal_ref)
    gid = int(row['id'])
    if row['status'] != 'active':
      raise ProjectError('Only an active goal can be achieved')
    if ts < int(row['started_at']):
      raise ProjectError('Goal achievement time cannot precede start time')
    if _exists(conn, "SELECT 1 FROM task WHERE status = 'active' LIMIT 1"):
      raise ProjectError('Cannot achieve goal while a task is active')
    if _exists(
      conn,
      'SELECT 1 FROM blocker '
      "WHERE goal_id = ? AND task_id IS NULL AND status = 'open' LIMIT 1",
      (gid,),
    ):
      raise ProjectError('Cannot achieve goal with open goal blockers')
    evs = conn.execute(
      'SELECT claim, captured_at FROM evidence WHERE goal_id = ?', (gid,)
    ).fetchall()
    if not evs:
      raise ProjectError('Goal achievement requires goal-linked evidence')
    if any(not is_substantive(e['claim']) for e in evs):
      raise ProjectError('Goal-linked evidence claims must be substantive')
    if any(int(e['captured_at']) > ts for e in evs):
      raise ProjectError('Goal achievement time cannot precede evidence')
    conn.execute(
      "UPDATE goal SET status = 'achieved', status_reason = '', "
      'achieved_at = ?, updated_at = ? WHERE id = ?',
      (ts, ts, gid),
    )
  return _get_goal_view(conn, gid)


def block_goal(
  conn: sqlite3.Connection,
  goal_ref: GoalRef | str = 'active',
  *,
  description: str,
  required: str,
  impact: str = '',
  attempts: str = '',
  now: int | None = None,
) -> GoalView:
  gid = int(_resolve_goal(conn, goal_ref)['id'])
  create_blocker(
    conn,
    description=description,
    required=required,
    goal=gid,
    impact=impact,
    attempts=attempts,
    now=now,
  )
  return _get_goal_view(conn, gid)


def reopen_goal(
  conn: sqlite3.Connection,
  goal_ref: GoalRef | str,
  *,
  now: int | None = None,
) -> GoalView:
  ts = _now(now)
  with conn:
    row = _resolve_goal(conn, goal_ref)
    if row['status'] != 'blocked':
      raise ProjectError('Only a blocked goal can be reopened')
    gid = int(row['id'])
    if _exists(
      conn,
      'SELECT 1 FROM blocker '
      "WHERE goal_id = ? AND task_id IS NULL AND status = 'open' LIMIT 1",
      (gid,),
    ):
      raise ProjectError('Cannot reopen goal with open goal blockers')
    _set_goal_active(conn, gid, ts)
  return _get_goal_view(conn, gid)


def cancel_goal(
  conn: sqlite3.Connection,
  goal_ref: GoalRef | str = 'active',
  *,
  reason: str = '',
  now: int | None = None,
) -> GoalView:
  ts = _now(now)
  with conn:
    row = _resolve_goal(conn, goal_ref)
    if row['status'] in ('achieved', 'cancelled'):
      raise ProjectError('Terminal goal cannot be cancelled')
    gid = int(row['id'])
    if _exists(
      conn,
      "SELECT 1 FROM task WHERE goal_id = ? AND status = 'active' LIMIT 1",
      (gid,),
    ):
      raise ProjectError(
        'Cannot cancel goal while a linked task is active'
      )
    conn.execute(
      "UPDATE blocker SET status = 'withdrawn', resolved_at = ?, "
      "resolution = 'Goal cancelled' "
      "WHERE goal_id = ? AND task_id IS NULL AND status = 'open'",
      (ts, gid),
    )
    conn.execute(
      "UPDATE goal SET status = 'cancelled', status_reason = ?, "
      'updated_at = ? WHERE id = ?',
      (reason, ts, gid),
    )
  return _get_goal_view(conn, gid)


def _task_tags_map(conn: sqlite3.Connection) -> dict[int, tuple[str, ...]]:
  res: dict[int, list[str]] = {}
  for r in conn.execute(
    'SELECT task_id, tag FROM task_tag ORDER BY tag ASC'
  ):
    res.setdefault(int(r['task_id']), []).append(str(r['tag']))
  return {k: tuple(v) for k, v in res.items()}


def _get_task_view(conn: sqlite3.Connection, task_id: int) -> TaskView:
  row = _resolve_task(conn, task_id)
  tags = tuple(
    str(r['tag'])
    for r in conn.execute(
      'SELECT tag FROM task_tag WHERE task_id = ? ORDER BY tag ASC',
      (task_id,),
    )
  )
  return _task_view(row, tags)


def list_tasks(
  conn: sqlite3.Connection,
  *,
  stage: StageRef | None = None,
  status: TaskStatus | None = None,
  goal: GoalRef | None = None,
  tag: str | None = None,
) -> list[TaskView]:
  clauses: list[str] = []
  params: list[object] = []
  if stage is not None:
    clauses.append('t.stage_id = ?')
    params.append(int(_resolve_stage(conn, stage)['id']))
  if status is not None:
    clauses.append('t.status = ?')
    params.append(status)
  if goal is not None:
    clauses.append('t.goal_id = ?')
    params.append(int(_resolve_goal(conn, goal)['id']))
  join = ''
  if tag is not None:
    stripped = tag.strip()
    if not stripped:
      return []
    join = 'JOIN task_tag tt ON tt.task_id = t.id'
    clauses.append('tt.tag = ?')
    params.append(stripped)
  where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
  rows = conn.execute(
    f'SELECT t.* FROM task t {join} {where} '
    'ORDER BY t.priority DESC, t.id ASC',
    tuple(params),
  ).fetchall()
  tags_map = _task_tags_map(conn)
  return [_task_view(r, tags_map.get(int(r['id']), ())) for r in rows]


def _task_ready_reason(
  conn: sqlite3.Connection, row: sqlite3.Row
) -> str | None:
  if row['status'] != 'pending':
    return 'Only pending tasks can be activated'
  proj = _require_row(
    conn, 'SELECT * FROM project WHERE id = 1', (), 'Project missing'
  )
  if not _charter_complete(proj):
    return 'Project charter must be complete'
  if row['stage_id'] is None:
    return 'Task must belong to a stage'
  sid = int(row['stage_id'])
  stages = {s.id: s for s in list_stages(conn)}
  stage = stages.get(sid)
  if stage is None or not (
    is_substantive(stage.name) and is_substantive(stage.outcome)
  ):
    return 'Task stage must have substantive name and outcome'
  deps_map = {s.id: s.dependencies for s in stages.values()}
  for dep_id in _transitive_reach(deps_map, sid):
    if stages[dep_id].status != 'achieved':
      return f'Stage dependency {dep_id} is not achieved'
  for col in TASK_PROSE_FIELDS:
    if not is_substantive(row[col]):
      return f'Task {col} must be substantive'
  if _exists(
    conn,
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open' LIMIT 1",
    (int(row['id']),),
  ):
    return 'Task has open blockers'
  if row['goal_id'] is not None:
    g = conn.execute(
      'SELECT status FROM goal WHERE id = ?', (int(row['goal_id']),)
    ).fetchone()
    if g is None or g['status'] != 'active':
      return 'Task linked goal must be active'
  return None


def list_ready_tasks(
  conn: sqlite3.Connection,
  *,
  stage: StageRef | None = None,
  goal: GoalRef | None = None,
  tag: str | None = None,
) -> list[TaskView]:
  candidates = list_tasks(
    conn, stage=stage, status='pending', goal=goal, tag=tag
  )
  if not candidates:
    return []
  proj = _require_row(
    conn, 'SELECT * FROM project WHERE id = 1', (), 'Project missing'
  )
  if not _charter_complete(proj):
    return []
  stages = {s.id: s for s in list_stages(conn)}
  deps_map = {s.id: s.dependencies for s in stages.values()}
  stage_ok = {
    sid: is_substantive(st.name)
    and is_substantive(st.outcome)
    and all(
      stages[d].status == 'achieved'
      for d in _transitive_reach(deps_map, sid)
    )
    for sid, st in stages.items()
  }
  blocked_ids = {
    int(r[0])
    for r in conn.execute(
      'SELECT DISTINCT task_id FROM blocker '
      "WHERE task_id IS NOT NULL AND status = 'open'"
    )
  }
  ag_row = conn.execute(
    "SELECT id FROM goal WHERE status = 'active'"
  ).fetchone()
  active_gid = int(ag_row['id']) if ag_row is not None else None
  return [
    t
    for t in candidates
    if t.stage_id is not None
    and stage_ok.get(t.stage_id, False)
    and t.id not in blocked_ids
    and (t.goal_id is None or t.goal_id == active_gid)
    and all(
      is_substantive(v)
      for v in (
        t.title,
        t.purpose,
        t.scope,
        t.exclusions,
        t.result,
        t.completion_evidence,
      )
    )
  ]


def show_task(conn: sqlite3.Connection, task_id: int) -> TaskDetails:
  task = _get_task_view(conn, task_id)
  logs = tuple(
    _row_as(TaskLog, r)
    for r in conn.execute(
      'SELECT * FROM task_log WHERE task_id = ? '
      'ORDER BY occurred_at DESC, id DESC',
      (task_id,),
    )
  )
  blockers, decisions, evidence = _scope_records(conn, 'task_id', task_id)
  return TaskDetails(task, logs, blockers, decisions, evidence)


def _clean_tags(tags: Sequence[str]) -> list[str]:
  return list(
    dict.fromkeys(require_substantive(raw, 'tag').strip() for raw in tags)
  )


def create_task(
  conn: sqlite3.Connection,
  *,
  title: str,
  stage: StageRef | None = None,
  goal: GoalRef | None = None,
  purpose: str = '',
  scope: str = '',
  exclusions: str = '',
  result: str = '',
  completion_evidence: str = '',
  priority: int = 0,
  tags: Sequence[str] = (),
  now: int | None = None,
) -> TaskView:
  require_substantive(title, 'task title')
  cleaned = _clean_tags(tags)
  ts = _now(now)
  with conn:
    sid = (
      int(_resolve_stage(conn, stage)['id']) if stage is not None else None
    )
    gid = (
      int(_resolve_goal(conn, goal)['id']) if goal is not None else None
    )
    if sid is not None:
      _invalidate_stage_achievement(conn, sid, ts)
    cur = conn.execute(
      'INSERT INTO task (goal_id, stage_id, title, purpose, scope, '
      'exclusions, result, completion_evidence, status, priority, '
      "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', "
      '?, ?, ?)',
      (
        gid,
        sid,
        title,
        purpose,
        scope,
        exclusions,
        result,
        completion_evidence,
        priority,
        ts,
        ts,
      ),
    )
    tid = int(cur.lastrowid or 0)
    for tag in cleaned:
      conn.execute(
        'INSERT INTO task_tag (task_id, tag) VALUES (?, ?)', (tid, tag)
      )
  return _get_task_view(conn, tid)


def update_task(
  conn: sqlite3.Connection,
  task_id: int,
  *,
  title: str | None = None,
  stage: StageRef | None = None,
  goal: GoalRef | None = None,
  clear_goal: bool = False,
  purpose: str | None = None,
  scope: str | None = None,
  exclusions: str | None = None,
  result: str | None = None,
  completion_evidence: str | None = None,
  priority: int | None = None,
  now: int | None = None,
) -> TaskView:
  if goal is not None and clear_goal:
    raise ProjectError('Cannot combine goal and clear_goal')
  if title is not None:
    require_substantive(title, 'task title')
  ts = _now(now)
  with conn:
    row = _resolve_task(conn, task_id)
    old_sid = int(row['stage_id']) if row['stage_id'] is not None else None
    old_gid = int(row['goal_id']) if row['goal_id'] is not None else None
    new_sid = (
      int(_resolve_stage(conn, stage)['id'])
      if stage is not None
      else old_sid
    )
    new_gid = (
      None
      if clear_goal
      else (
        int(_resolve_goal(conn, goal)['id'])
        if goal is not None
        else old_gid
      )
    )
    updates: dict[str, object] = {}
    if stage is not None:
      updates['stage_id'] = new_sid
    if goal is not None or clear_goal:
      updates['goal_id'] = new_gid
    for col, val in (
      ('title', title),
      ('purpose', purpose),
      ('scope', scope),
      ('exclusions', exclusions),
      ('result', result),
      ('completion_evidence', completion_evidence),
      ('priority', priority),
    ):
      if val is not None:
        updates[col] = val
    if not updates:
      return _get_task_view(conn, task_id)
    for b in conn.execute(
      'SELECT stage_id, goal_id FROM blocker '
      "WHERE task_id = ? AND status = 'open'",
      (task_id,),
    ):
      if b['stage_id'] is not None and new_sid != b['stage_id']:
        raise ProjectError('Open blocker requires existing stage')
      if b['goal_id'] is not None and new_gid != b['goal_id']:
        raise ProjectError('Open blocker requires existing goal')
    if row['status'] == 'active':
      for col in TASK_PROSE_FIELDS:
        val = updates.get(col, row[col])
        if not isinstance(val, str) or not is_substantive(val):
          raise ProjectError(f'Active task {col} must remain substantive')
      if new_sid is None:
        raise ProjectError('Active task must belong to a stage')
      stages = {s.id: s for s in list_stages(conn)}
      st = stages[new_sid]
      if not (is_substantive(st.name) and is_substantive(st.outcome)):
        raise ProjectError(
          'Active task stage must have substantive name and outcome'
        )
      for dep_id in _transitive_reach(
        {s.id: s.dependencies for s in stages.values()}, new_sid
      ):
        if stages[dep_id].status != 'achieved':
          raise ProjectError(f'Stage dependency {dep_id} is not achieved')
      if new_gid is not None:
        g = _require_row(
          conn, 'SELECT status FROM goal WHERE id = ?', (new_gid,), 'Goal'
        )
        if g['status'] != 'active':
          raise ProjectError('Active task goal must be active')
    if new_sid != old_sid:
      if new_sid is not None:
        ach = _require_row(
          conn,
          'SELECT achieved_at FROM stage WHERE id = ?',
          (new_sid,),
          '',
        )['achieved_at']
        comp = row['completed_at']
        if row['status'] in ('pending', 'active', 'blocked') or (
          row['status'] == 'completed'
          and ach is not None
          and (comp is None or int(comp) > int(ach))
        ):
          _invalidate_stage_achievement(
            conn, new_sid, ts, exclude_task_id=task_id
          )
      if old_sid is not None and not _exists(
        conn,
        'SELECT 1 FROM task WHERE stage_id = ? AND id != ? '
        "AND status = 'completed' LIMIT 1",
        (old_sid, task_id),
      ):
        _invalidate_stage_achievement(
          conn, old_sid, ts, exclude_task_id=task_id
        )
    _update_cols(conn, 'task', task_id, updates, ts)
  return _get_task_view(conn, task_id)


def activate_task(
  conn: sqlite3.Connection, task_id: int, *, now: int | None = None
) -> TaskView:
  ts = _now(now)
  with conn:
    row = _resolve_task(conn, task_id)
    err = _task_ready_reason(conn, row)
    if err is not None:
      raise ProjectError(err)
    old = conn.execute(
      "SELECT id FROM task WHERE status = 'active' AND id != ?", (task_id,)
    ).fetchone()
    if old is not None:
      old_id = int(old['id'])
      conn.execute(
        "UPDATE task SET status = 'pending', updated_at = ? WHERE id = ?",
        (ts, old_id),
      )
      _append_log(
        conn, old_id, 'handoff', f'Deferred for task {task_id}', ts
      )
    conn.execute(
      "UPDATE task SET status = 'active', "
      'started_at = COALESCE(started_at, ?), updated_at = ? WHERE id = ?',
      (ts, ts, task_id),
    )
    _append_log(conn, task_id, 'started', 'Task activated', ts)
  return _get_task_view(conn, task_id)


def complete_task(
  conn: sqlite3.Connection, task_id: int, *, now: int | None = None
) -> TaskView:
  ts = _now(now)
  with conn:
    row = _resolve_task(conn, task_id)
    if row['status'] != 'active':
      raise ProjectError('Only an active task can be completed')
    if row['started_at'] is not None and ts < int(row['started_at']):
      raise ProjectError('Completion time cannot precede task start time')
    conn.execute(
      "UPDATE task SET status = 'completed', completed_at = ?, "
      'updated_at = ? WHERE id = ?',
      (ts, ts, task_id),
    )
    _append_log(conn, task_id, 'completed', 'Task completed', ts)
  return _get_task_view(conn, task_id)


def block_task(
  conn: sqlite3.Connection,
  task_id: int,
  *,
  description: str,
  required: str,
  impact: str = '',
  attempts: str = '',
  now: int | None = None,
) -> TaskView:
  create_blocker(
    conn,
    description=description,
    required=required,
    task_id=task_id,
    impact=impact,
    attempts=attempts,
    now=now,
  )
  return _get_task_view(conn, task_id)


def reopen_task(
  conn: sqlite3.Connection, task_id: int, *, now: int | None = None
) -> TaskView:
  ts = _now(now)
  with conn:
    row = _resolve_task(conn, task_id)
    if row['status'] not in ('completed', 'cancelled'):
      raise ProjectError(
        'Only completed or cancelled tasks can be reopened'
      )
    if row['stage_id'] is not None:
      _invalidate_stage_achievement(conn, int(row['stage_id']), ts)
    conn.execute(
      "UPDATE task SET status = 'pending', completed_at = NULL, "
      'updated_at = ? WHERE id = ?',
      (ts, task_id),
    )
    _append_log(conn, task_id, 'reopened', 'Task reopened', ts)
  return _get_task_view(conn, task_id)


def cancel_task(
  conn: sqlite3.Connection, task_id: int, *, now: int | None = None
) -> TaskView:
  ts = _now(now)
  with conn:
    row = _resolve_task(conn, task_id)
    if row['status'] not in ('pending', 'active', 'blocked'):
      raise ProjectError('Terminal task cannot be cancelled')
    conn.execute(
      "UPDATE blocker SET status = 'withdrawn', resolved_at = ?, "
      "resolution = 'Task cancelled' "
      "WHERE task_id = ? AND status = 'open'",
      (ts, task_id),
    )
    conn.execute(
      "UPDATE task SET status = 'cancelled', updated_at = ? WHERE id = ?",
      (ts, task_id),
    )
    _append_log(conn, task_id, 'cancelled', 'Task cancelled', ts)
  return _get_task_view(conn, task_id)


def add_task_tags(
  conn: sqlite3.Connection, task_id: int, tags: Sequence[str]
) -> TaskView:
  cleaned = _clean_tags(tags)
  with conn:
    _resolve_task(conn, task_id)
    for tag in cleaned:
      conn.execute(
        'INSERT OR IGNORE INTO task_tag (task_id, tag) VALUES (?, ?)',
        (task_id, tag),
      )
  return _get_task_view(conn, task_id)


def remove_task_tags(
  conn: sqlite3.Connection, task_id: int, tags: Sequence[str]
) -> TaskView:
  cleaned = [t.strip() for t in tags if t.strip()]
  with conn:
    _resolve_task(conn, task_id)
    for tag in cleaned:
      conn.execute(
        'DELETE FROM task_tag WHERE task_id = ? AND tag = ?',
        (task_id, tag),
      )
  return _get_task_view(conn, task_id)


def append_task_log(
  conn: sqlite3.Connection,
  task_id: int,
  message: str,
  *,
  kind: str = 'note',
  now: int | None = None,
) -> TaskLog:
  require_substantive(message, 'log message')
  ts = _now(now)
  with conn:
    _resolve_task(conn, task_id)
    return _append_log(conn, task_id, kind, message, ts)


def list_task_logs(
  conn: sqlite3.Connection,
  task_id: int,
  *,
  limit: int = 20,
  since: int | None = None,
) -> tuple[list[TaskLog], bool]:
  if limit < 1:
    raise ProjectError('Limit must be positive')
  _resolve_task(conn, task_id)
  sql = (
    'SELECT * FROM task_log WHERE task_id = ? '
    + ('AND occurred_at >= ? ' if since is not None else '')
    + 'ORDER BY occurred_at DESC, id DESC LIMIT ?'
  )
  params = (
    (task_id, since, limit + 1)
    if since is not None
    else (task_id, limit + 1)
  )
  rows = conn.execute(sql, params).fetchall()
  return [_row_as(TaskLog, r) for r in rows[:limit]], len(rows) > limit


def create_blocker(
  conn: sqlite3.Connection,
  *,
  description: str,
  required: str,
  task_id: int | None = None,
  goal: GoalRef | None = None,
  stage: StageRef | None = None,
  impact: str = '',
  attempts: str = '',
  now: int | None = None,
) -> BlockerRecord:
  require_substantive(description, 'blocker description')
  require_substantive(required, 'blocker required resolution')
  if task_id is None and goal is None:
    raise ProjectError('Blocker must target a task or goal')
  ts = _now(now)
  with conn:
    if task_id is not None:
      trow = _resolve_task(conn, task_id)
      if trow['status'] not in ('pending', 'active', 'blocked'):
        raise ProjectError('Cannot block a completed or cancelled task')
      sid = (
        int(_resolve_stage(conn, stage)['id'])
        if stage is not None
        else trow['stage_id']
      )
      if stage is not None and sid != trow['stage_id']:
        raise ProjectError('Blocker stage disagrees with task stage')
      gid = (
        int(_resolve_goal(conn, goal)['id'])
        if goal is not None
        else trow['goal_id']
      )
      if goal is not None and gid != trow['goal_id']:
        raise ProjectError('Blocker goal disagrees with task goal')
      conn.execute(
        "UPDATE task SET status = 'blocked', updated_at = ? WHERE id = ?",
        (ts, task_id),
      )
      _append_log(conn, task_id, 'blocked', description, ts)
    else:
      assert goal is not None
      grow = _resolve_goal(conn, goal)
      if grow['status'] not in ('active', 'blocked'):
        raise ProjectError('Only an active or blocked goal can be blocked')
      gid = int(grow['id'])
      if grow['status'] == 'active' and _exists(
        conn,
        'SELECT 1 FROM task WHERE goal_id = ? '
        "AND status = 'active' LIMIT 1",
        (gid,),
      ):
        raise ProjectError(
          'Cannot block goal while a linked task is active'
        )
      sid = (
        int(_resolve_stage(conn, stage)['id'])
        if stage is not None
        else None
      )
      if sid is not None and not _exists(
        conn,
        'SELECT 1 FROM goal_stage WHERE goal_id = ? AND stage_id = ?',
        (gid, sid),
      ):
        raise ProjectError('Blocker stage does not belong to target goal')
      conn.execute(
        "UPDATE goal SET status = 'blocked', status_reason = ?, "
        'updated_at = ? WHERE id = ?',
        (description, ts, gid),
      )
    cur = conn.execute(
      'INSERT INTO blocker (goal_id, stage_id, task_id, description, '
      'impact, attempts, required, status, opened_at) '
      "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
      (gid, sid, task_id, description, impact, attempts, required, ts),
    )
    row = _require_row(
      conn,
      'SELECT * FROM blocker WHERE id = ?',
      (cur.lastrowid,),
      'Blocker',
    )
  return _row_as(BlockerRecord, row)


def list_blockers(
  conn: sqlite3.Connection,
  *,
  status: Literal['open', 'resolved', 'withdrawn', 'all'] = 'open',
) -> list[BlockerRecord]:
  if status not in ('open', 'resolved', 'withdrawn', 'all'):
    raise ProjectError(f'Invalid blocker status filter: {status!r}')
  sql = (
    'SELECT * FROM blocker '
    + ('' if status == 'all' else 'WHERE status = ? ')
    + 'ORDER BY opened_at DESC, id DESC'
  )
  rows = conn.execute(sql, () if status == 'all' else (status,)).fetchall()
  return [_row_as(BlockerRecord, r) for r in rows]


def resolve_blocker(
  conn: sqlite3.Connection,
  blocker_id: int,
  *,
  resolution: str,
  now: int | None = None,
) -> BlockerRecord:
  require_substantive(resolution, 'blocker resolution')
  ts = _now(now)
  with conn:
    brow = _require_row(
      conn,
      'SELECT * FROM blocker WHERE id = ?',
      (blocker_id,),
      f'Blocker not found: {blocker_id}',
    )
    if brow['status'] != 'open':
      raise ProjectError('Only an open blocker can be resolved')
    conn.execute(
      "UPDATE blocker SET status = 'resolved', resolved_at = ?, "
      'resolution = ? WHERE id = ?',
      (ts, resolution, blocker_id),
    )
    if brow['task_id'] is not None:
      tid = int(brow['task_id'])
      if (
        not _exists(
          conn,
          'SELECT 1 FROM blocker '
          "WHERE task_id = ? AND status = 'open' LIMIT 1",
          (tid,),
        )
        and _resolve_task(conn, tid)['status'] == 'blocked'
      ):
        conn.execute(
          "UPDATE task SET status = 'pending', updated_at = ? "
          'WHERE id = ?',
          (ts, tid),
        )
        _append_log(conn, tid, 'unblocked', resolution, ts)
    elif brow['goal_id'] is not None:
      gid = int(brow['goal_id'])
      if (
        not _exists(
          conn,
          'SELECT 1 FROM blocker WHERE goal_id = ? '
          "AND task_id IS NULL AND status = 'open' LIMIT 1",
          (gid,),
        )
        and _resolve_goal(conn, gid)['status'] == 'blocked'
      ):
        _set_goal_active(conn, gid, ts)
    updated = _require_row(
      conn, 'SELECT * FROM blocker WHERE id = ?', (blocker_id,), 'Blocker'
    )
  return _row_as(BlockerRecord, updated)


def _resolve_record_context(
  conn: sqlite3.Connection,
  task_id: int | None,
  stage: StageRef | None,
  goal: GoalRef | None,
) -> tuple[int | None, int | None, int | None]:
  if task_id is not None:
    trow = _resolve_task(conn, task_id)
    if (
      stage is not None
      and int(_resolve_stage(conn, stage)['id']) != trow['stage_id']
    ):
      raise ProjectError('Stage disagrees with task stage')
    if (
      goal is not None
      and int(_resolve_goal(conn, goal)['id']) != trow['goal_id']
    ):
      raise ProjectError('Goal disagrees with task goal')
    return trow['goal_id'], trow['stage_id'], task_id
  gid = int(_resolve_goal(conn, goal)['id']) if goal is not None else None
  sid = (
    int(_resolve_stage(conn, stage)['id']) if stage is not None else None
  )
  return gid, sid, None


def create_decision(
  conn: sqlite3.Connection,
  *,
  summary: str,
  rationale: str = '',
  alternatives: str = '',
  consequences: str = '',
  task_id: int | None = None,
  stage: StageRef | None = None,
  goal: GoalRef | None = None,
  now: int | None = None,
) -> DecisionRecord:
  require_substantive(summary, 'decision summary')
  ts = _now(now)
  with conn:
    gid, sid, tid = _resolve_record_context(conn, task_id, stage, goal)
    cur = conn.execute(
      'INSERT INTO decision (goal_id, stage_id, task_id, summary, '
      'rationale, alternatives, consequences, decided_at) '
      'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      (gid, sid, tid, summary, rationale, alternatives, consequences, ts),
    )
    row = _require_row(
      conn, 'SELECT * FROM decision WHERE id = ?', (cur.lastrowid,), 'Dec'
    )
  return _row_as(DecisionRecord, row)


def create_evidence(
  conn: sqlite3.Connection,
  *,
  claim: str,
  source: str = '',
  result: str = '',
  task_id: int | None = None,
  stage: StageRef | None = None,
  goal: GoalRef | None = None,
  now: int | None = None,
) -> EvidenceRecord:
  require_substantive(claim, 'evidence claim')
  ts = _now(now)
  with conn:
    gid, sid, tid = _resolve_record_context(conn, task_id, stage, goal)
    cur = conn.execute(
      'INSERT INTO evidence (goal_id, stage_id, task_id, claim, source, '
      'result, captured_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
      (gid, sid, tid, claim, source, result, ts),
    )
    row = _require_row(
      conn, 'SELECT * FROM evidence WHERE id = ?', (cur.lastrowid,), 'Ev'
    )
  return _row_as(EvidenceRecord, row)


def _query_scoped(
  conn: sqlite3.Connection,
  table: str,
  order_col: str,
  *,
  limit: int,
  stage: StageRef | None,
  task_id: int | None,
  goal: GoalRef | None,
  no_task: bool,
) -> tuple[list[sqlite3.Row], bool]:
  if limit < 1:
    raise ProjectError('Limit must be positive')
  if no_task and task_id is not None:
    raise ProjectError('Cannot combine task_id and no_task')
  clauses: list[str] = []
  params: list[object] = []
  if stage is not None:
    clauses.append('stage_id = ?')
    params.append(int(_resolve_stage(conn, stage)['id']))
  if task_id is not None:
    _resolve_task(conn, task_id)
    clauses.append('task_id = ?')
    params.append(task_id)
  if goal is not None:
    clauses.append('goal_id = ?')
    params.append(int(_resolve_goal(conn, goal)['id']))
  if no_task:
    clauses.append('task_id IS NULL')
  where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
  rows = conn.execute(
    f'SELECT * FROM {table} {where} ORDER BY {order_col} DESC, id DESC '
    'LIMIT ?',
    (*params, limit + 1),
  ).fetchall()
  return rows[:limit], len(rows) > limit


def list_decisions(
  conn: sqlite3.Connection,
  *,
  limit: int = 20,
  stage: StageRef | None = None,
  task_id: int | None = None,
  goal: GoalRef | None = None,
  no_task: bool = False,
) -> tuple[list[DecisionRecord], bool]:
  rows, more = _query_scoped(
    conn,
    'decision',
    'decided_at',
    limit=limit,
    stage=stage,
    task_id=task_id,
    goal=goal,
    no_task=no_task,
  )
  return [_row_as(DecisionRecord, r) for r in rows], more


def list_evidence(
  conn: sqlite3.Connection,
  *,
  limit: int = 20,
  stage: StageRef | None = None,
  task_id: int | None = None,
  goal: GoalRef | None = None,
  no_task: bool = False,
) -> tuple[list[EvidenceRecord], bool]:
  rows, more = _query_scoped(
    conn,
    'evidence',
    'captured_at',
    limit=limit,
    stage=stage,
    task_id=task_id,
    goal=goal,
    no_task=no_task,
  )
  return [_row_as(EvidenceRecord, r) for r in rows], more


def _handoff_slice(
  conn: sqlite3.Connection,
  table: str,
  where: str,
  params: tuple[object, ...],
  order_col: str,
) -> tuple[list[sqlite3.Row], int]:
  rows = conn.execute(
    f'SELECT * FROM {table} WHERE {where} '
    f'ORDER BY {order_col} DESC, id DESC LIMIT ?',
    (*params, HANDOFF_LIMIT),
  ).fetchall()
  total = int(
    conn.execute(
      f'SELECT COUNT(*) FROM {table} WHERE {where}', params
    ).fetchone()[0]
  )
  return rows, total


def read_handoff(conn: sqlite3.Connection) -> HandoffData:
  project = read_project(conn)
  gstages = _goal_stages_map(conn)
  ttags = _task_tags_map(conn)
  ag_row = conn.execute(
    "SELECT * FROM goal WHERE status = 'active'"
  ).fetchone()
  active_goal = (
    _goal_view(ag_row, gstages.get(int(ag_row['id']), ()))
    if ag_row is not None
    else None
  )
  at_row = conn.execute(
    "SELECT * FROM task WHERE status = 'active'"
  ).fetchone()
  active_task = (
    _task_view(at_row, ttags.get(int(at_row['id']), ()))
    if at_row is not None
    else None
  )
  active_stage = (
    _get_stage_view(conn, active_task.stage_id)
    if active_task is not None and active_task.stage_id is not None
    else None
  )
  open_blockers = tuple(list_blockers(conn, status='open'))
  blocked_tasks = tuple(
    _task_view(r, ttags.get(int(r['id']), ()))
    for r in conn.execute(
      "SELECT * FROM task WHERE status = 'blocked' "
      'ORDER BY updated_at DESC, id DESC'
    )
  )
  blocked_goals = tuple(
    _goal_view(r, gstages.get(int(r['id']), ()))
    for r in conn.execute(
      "SELECT * FROM goal WHERE status = 'blocked' "
      'ORDER BY updated_at DESC, id DESC'
    )
  )
  focus_kind: Literal['task', 'goal'] | None = None
  focus_id: int | None = None
  if active_task is not None:
    focus_kind, focus_id = 'task', active_task.id
  elif blocked_tasks:
    focus_kind, focus_id = 'task', blocked_tasks[0].id
  elif active_goal is not None:
    focus_kind, focus_id = 'goal', active_goal.id
  elif blocked_goals:
    focus_kind, focus_id = 'goal', blocked_goals[0].id
  decisions: tuple[DecisionRecord, ...] = ()
  decisions_total = 0
  evidence: tuple[EvidenceRecord, ...] = ()
  evidence_total = 0
  task_logs: tuple[TaskLog, ...] = ()
  task_logs_total = 0
  if focus_kind == 'task' and focus_id is not None:
    where, params = 'task_id = ?', (focus_id,)
    lrows, task_logs_total = _handoff_slice(
      conn, 'task_log', where, params, 'occurred_at'
    )
    task_logs = tuple(_row_as(TaskLog, r) for r in lrows)
  elif focus_kind == 'goal' and focus_id is not None:
    where, params = 'goal_id = ? AND task_id IS NULL', (focus_id,)
  else:
    where, params = None, ()
  if where is not None:
    drows, decisions_total = _handoff_slice(
      conn, 'decision', where, params, 'decided_at'
    )
    erows, evidence_total = _handoff_slice(
      conn, 'evidence', where, params, 'captured_at'
    )
    decisions = tuple(_row_as(DecisionRecord, r) for r in drows)
    evidence = tuple(_row_as(EvidenceRecord, r) for r in erows)
  return HandoffData(
    project,
    active_goal,
    active_task,
    active_stage,
    open_blockers,
    blocked_tasks,
    blocked_goals,
    focus_kind,
    focus_id,
    decisions,
    decisions_total,
    evidence,
    evidence_total,
    task_logs,
    task_logs_total,
  )
