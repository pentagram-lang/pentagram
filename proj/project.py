import base64
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from zero import lib

SCHEMA_VERSION = 2
MAX_GOAL_TEXT_LENGTH = 4000
PROJECT_SUFFIX = '.sqlite3'
PROJECT_NAME_PATTERN = re.compile(r'^[^/\\\x00]+$')
PROJECT_STATUSES = ('active', 'blocked', 'verifying', 'complete')
GOAL_STATUSES = ('active', 'blocked', 'achieved', 'superseded')
STAGE_STATUSES = (
  'pending',
  'active',
  'verifying',
  'achieved',
  'superseded',
  'blocked',
)
TASK_STATUSES = (
  'planned',
  'active',
  'verifying',
  'completed',
  'blocked',
  'cancelled',
)
BLOCKER_STATUSES = ('open', 'resolved', 'withdrawn')
UNSET = object()

SCHEMA_SQL = """
CREATE TABLE project (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT NOT NULL,
  objective TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  non_goals TEXT NOT NULL DEFAULT '',
  constraints_text TEXT NOT NULL DEFAULT '',
  acceptance TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'blocked', 'verifying', 'complete')),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  completed_at INTEGER
);

CREATE TABLE goal (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL
    CHECK (
      length(text) > 0
      AND length(trim(text)) > 0
      AND length(text) <= 4000
    ),
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'blocked', 'achieved', 'superseded')),
  status_reason TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  achieved_at INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE stage (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  outcome TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  entry_conditions TEXT NOT NULL DEFAULT '',
  exit_evidence TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (
      status IN (
        'pending', 'active', 'verifying',
        'achieved', 'superseded', 'blocked'
      )
    ),
  position INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  achieved_at INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE goal_stage (
  goal_id INTEGER NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
  stage_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  PRIMARY KEY (goal_id, stage_id)
);

CREATE TABLE task (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'planned'
    CHECK (
      status IN (
        'planned', 'active', 'verifying',
        'completed', 'blocked', 'cancelled'
      )
    ),
  priority INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  completed_at INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE project_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  summary TEXT NOT NULL DEFAULT '',
  next_action TEXT NOT NULL DEFAULT '',
  active_goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  current_stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  current_task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  updated_at INTEGER NOT NULL,
  revision INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE stage_dependency (
  stage_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  dependency_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  PRIMARY KEY (stage_id, dependency_id),
  CHECK (stage_id <> dependency_id)
);

CREATE TABLE task_tag (
  task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  tag TEXT NOT NULL CHECK (length(trim(tag)) > 0),
  PRIMARY KEY (task_id, tag)
);

CREATE TABLE task_log (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  occurred_at INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'note',
  message TEXT NOT NULL
);

CREATE TABLE decision (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  summary TEXT NOT NULL,
  rationale TEXT NOT NULL DEFAULT '',
  alternatives TEXT NOT NULL DEFAULT '',
  consequences TEXT NOT NULL DEFAULT '',
  decided_at INTEGER NOT NULL
);

CREATE TABLE blocker (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  description TEXT NOT NULL,
  impact TEXT NOT NULL DEFAULT '',
  attempts TEXT NOT NULL DEFAULT '',
  required TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'resolved', 'withdrawn')),
  opened_at INTEGER NOT NULL,
  resolved_at INTEGER,
  resolution TEXT NOT NULL DEFAULT ''
);

CREATE TABLE evidence (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  claim TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT '',
  captured_at INTEGER NOT NULL
);

CREATE INDEX task_stage_index ON task(stage_id);
CREATE INDEX task_goal_index ON task(goal_id);
CREATE INDEX task_status_index ON task(status);
CREATE INDEX task_tag_index ON task_tag(tag);
CREATE INDEX task_log_task_time_index
  ON task_log(task_id, occurred_at DESC);
CREATE INDEX blocker_status_index ON blocker(status);
CREATE INDEX blocker_goal_index ON blocker(goal_id);
CREATE INDEX evidence_goal_index ON evidence(goal_id);
CREATE INDEX evidence_stage_index ON evidence(stage_id);
CREATE INDEX goal_status_index ON goal(status);
CREATE INDEX goal_stage_stage_index ON goal_stage(stage_id);
"""

MIGRATION_1_TO_2_SQL = """
CREATE TABLE goal (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL
    CHECK (
      length(text) > 0
      AND length(trim(text)) > 0
      AND length(text) <= 4000
    ),
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'blocked', 'achieved', 'superseded')),
  status_reason TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  achieved_at INTEGER,
  updated_at INTEGER NOT NULL
);

ALTER TABLE project_state
  ADD COLUMN active_goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL;
ALTER TABLE task
  ADD COLUMN goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL;
ALTER TABLE decision
  ADD COLUMN goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL;
ALTER TABLE blocker
  ADD COLUMN goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL;
ALTER TABLE evidence
  ADD COLUMN goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL;

CREATE TABLE goal_stage (
  goal_id INTEGER NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
  stage_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  PRIMARY KEY (goal_id, stage_id)
);

CREATE INDEX task_goal_index ON task(goal_id);
CREATE INDEX blocker_goal_index ON blocker(goal_id);
CREATE INDEX evidence_goal_index ON evidence(goal_id);
CREATE INDEX goal_status_index ON goal(status);
CREATE INDEX goal_stage_stage_index ON goal_stage(stage_id);
"""


class ProjectError(Exception):
  pass


def repository_root():
  return Path(__file__).resolve().parent.parent


def current_time():
  return int(time.time())


def format_time(value):
  if value is None:
    return '-'
  return datetime.fromtimestamp(value, timezone.utc).isoformat()


def validate_project_name(name):
  if (
    not name
    or name in ('.', '..')
    or name.endswith(PROJECT_SUFFIX)
    or PROJECT_NAME_PATTERN.fullmatch(name) is None
  ):
    raise ProjectError(
      'Project names must be non-empty single path components without the '
      '.sqlite3 suffix.'
    )
  return name


def project_directory(root):
  return Path(root) / '.tmp'


def database_path(root, name):
  validate_project_name(name)
  return project_directory(root) / f'{name}{PROJECT_SUFFIX}'


def connect(path):
  connection = sqlite3.connect(path, timeout=5)
  connection.row_factory = sqlite3.Row
  connection.execute('PRAGMA foreign_keys = ON')
  connection.execute('PRAGMA busy_timeout = 5000')
  return connection


def open_project(root, name):
  path = database_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project does not exist: {name}')
  connection = connect(path)
  try:
    _migrate_project(connection, path)
    return connection
  except ProjectError:
    connection.close()
    raise


def _migrate_project(connection, path):
  version = connection.execute('PRAGMA user_version').fetchone()[0]
  if version == SCHEMA_VERSION:
    return
  if version > SCHEMA_VERSION or version != 1:
    raise ProjectError(f'Unsupported project schema: {path}')
  try:
    connection.executescript(MIGRATION_1_TO_2_SQL)
    connection.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    connection.commit()
  except sqlite3.Error as error:
    raise ProjectError(
      f'Could not migrate project schema: {path}: {error}'
    ) from error


def _archive_path(path):
  archive_directory = path.parent / 'archive'
  archive_directory.mkdir(parents=True, exist_ok=True)
  ctime = path.stat().st_ctime_ns
  destination = archive_directory / f'{path.stem}-{ctime}{path.suffix}'
  suffix = 1
  while destination.exists():
    destination = (
      archive_directory / f'{path.stem}-{ctime}-{suffix}{path.suffix}'
    )
    suffix += 1
  return destination


def archive_project(root, name):
  path = database_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project does not exist: {name}')
  destination = _archive_path(path)
  path.rename(destination)
  return destination


def _initialize_project(
  connection, name, objective, scope, non_goals, constraints, acceptance
):
  connection.executescript(SCHEMA_SQL)
  connection.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
  timestamp = current_time()
  connection.execute(
    """
    INSERT INTO project
      (id, name, objective, scope, non_goals, constraints_text, acceptance,
       created_at, updated_at)
    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
      name,
      objective,
      scope,
      non_goals,
      constraints,
      acceptance,
      timestamp,
      timestamp,
    ),
  )
  connection.execute(
    """
    INSERT INTO project_state (id, updated_at)
    VALUES (1, ?)
    """,
    (timestamp,),
  )
  connection.commit()


def create_project(
  root,
  name,
  objective,
  scope='',
  non_goals='',
  constraints='',
  acceptance='',
):
  validate_project_name(name)
  project_directory(root).mkdir(parents=True, exist_ok=True)
  path = database_path(root, name)
  temporary_path = (
    project_directory(root) / f'.{name}-{time.time_ns()}.tmp'
  )
  connection = connect(temporary_path)
  try:
    _initialize_project(
      connection,
      name,
      objective,
      scope,
      non_goals,
      constraints,
      acceptance,
    )
  except Exception:
    connection.close()
    temporary_path.unlink(missing_ok=True)
    raise
  connection.close()
  if path.exists():
    archive_project(root, name)
  temporary_path.rename(path)
  return path


def _row_dict(row):
  return dict(row) if row is not None else None


def _touch(connection):
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


def _resolve_stage(connection, reference):
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


def _resolve_task(connection, reference):
  if str(reference).isdigit():
    row = connection.execute(
      'SELECT id FROM task WHERE id = ?', (int(reference),)
    ).fetchone()
  else:
    raise ProjectError(f'Task references must be numeric: {reference}')
  if row is None:
    raise ProjectError(f'Task does not exist: {reference}')
  return row['id']


def validate_goal_text(text):
  length = len(text)
  if not text.strip():
    raise ProjectError(
      'Goal text must contain at least one non-whitespace character'
    )
  if length > MAX_GOAL_TEXT_LENGTH:
    raise ProjectError(
      f'Goal text is limited to {MAX_GOAL_TEXT_LENGTH:,} characters; '
      f'received {length:,}.'
    )
  return text


def _resolve_goal(connection, reference=None):
  if reference is None or str(reference) == 'active':
    row = connection.execute(
      """
      SELECT g.id
      FROM project_state ps
      JOIN goal g ON g.id = ps.active_goal_id
      WHERE ps.id = 1
      """
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


def _ensure_goal_stage(connection, goal_id, stage_id, relationship):
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


def create_goal(root, name, text, stages):
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
      active = connection.execute(
        'SELECT active_goal_id FROM project_state WHERE id = 1'
      ).fetchone()
      if active['active_goal_id'] is not None:
        raise ProjectError(
          'Project already has an active goal; achieve, supersede, or '
          'reopen it before setting another goal'
        )
      stage_ids = [
        _resolve_stage(connection, reference)
        for reference in stage_references
      ]
      if len(stage_ids) != len(set(stage_ids)):
        raise ProjectError(
          'A goal cannot link the same stage more than once'
        )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO goal (text, started_at, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (text, timestamp, timestamp, timestamp),
      )
      goal_id = cursor.lastrowid
      connection.executemany(
        'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
        ((goal_id, stage_id) for stage_id in stage_ids),
      )
      connection.execute(
        'UPDATE project_state SET active_goal_id = ? WHERE id = 1',
        (goal_id,),
      )
      _touch(connection)
      return goal_id
  finally:
    connection.close()


def _read_goal_record(connection, goal_id):
  goal = _row_dict(
    connection.execute(
      'SELECT * FROM goal WHERE id = ?', (goal_id,)
    ).fetchone()
  )
  stages = [
    _row_dict(row)
    for row in connection.execute(
      """
      SELECT s.id, s.name, s.status, s.outcome
      FROM goal_stage gs
      JOIN stage s ON s.id = gs.stage_id
      WHERE gs.goal_id = ?
      ORDER BY s.position, s.id
      """,
      (goal_id,),
    ).fetchall()
  ]
  tasks = [
    _row_dict(row)
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
  ]
  blockers = [
    _row_dict(row)
    for row in connection.execute(
      'SELECT * FROM blocker WHERE goal_id = '
      '? ORDER BY opened_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  evidence = [
    _row_dict(row)
    for row in connection.execute(
      'SELECT * FROM evidence WHERE goal_id = '
      '? ORDER BY captured_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  decisions = [
    _row_dict(row)
    for row in connection.execute(
      'SELECT * FROM decision WHERE goal_id = '
      '? ORDER BY decided_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  return {
    'goal': goal,
    'stages': stages,
    'tasks': tasks,
    'blockers': blockers,
    'evidence': evidence,
    'decisions': decisions,
  }


def read_goals(root, name, status=None):
  if status is not None and status not in GOAL_STATUSES:
    raise ProjectError(f'Invalid goal status: {status}')
  connection = open_project(root, name)
  try:
    condition = 'WHERE g.status = ?' if status else ''
    parameters = (status,) if status else ()
    rows = connection.execute(
      f"""
      SELECT g.*,
        CASE WHEN ps.active_goal_id = g.id THEN 1 ELSE 0 END AS is_active,
        COALESCE((
          SELECT group_concat(s.name, ', ')
          FROM goal_stage gs
          JOIN stage s ON s.id = gs.stage_id
          WHERE gs.goal_id = g.id
        ), '') AS stage_names
      FROM goal g
      CROSS JOIN project_state ps
      {condition}
      ORDER BY g.id DESC
      """,
      parameters,
    ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def read_goal(root, name, reference=None):
  connection = open_project(root, name)
  try:
    return _read_goal_record(
      connection, _resolve_goal(connection, reference)
    )
  finally:
    connection.close()


def goal_text(root, name, reference=None):
  connection = open_project(root, name)
  try:
    goal_id = _resolve_goal(connection, reference)
    return connection.execute(
      'SELECT text FROM goal WHERE id = ?', (goal_id,)
    ).fetchone()['text']
  finally:
    connection.close()


def copy_goal(root, name, reference=None):
  text = goal_text(root, name, reference)
  payload = base64.b64encode(text.encode('utf-8')).decode('ascii')
  return f'\x1b]52;c;{payload}\x07'


def achieve_goal(root, name, reference=None):
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
        "WHERE goal_id = ? AND status = 'open' LIMIT 1",
        (goal_id,),
      ).fetchone():
        raise ProjectError(
          'Achieving a goal requires all goal blockers to be resolved'
        )
      if (
        connection.execute(
          'SELECT 1 FROM evidence WHERE goal_id = ? LIMIT 1', (goal_id,)
        ).fetchone()
        is None
      ):
        raise ProjectError(
          'Achieving a goal requires at least one goal-linked '
          'evidence entry'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE goal
        SET status = 'achieved', achieved_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, goal_id),
      )
      connection.execute(
        'UPDATE project_state SET active_goal_id = NULL '
        'WHERE active_goal_id = ?',
        (goal_id,),
      )
      _touch(connection)
  finally:
    connection.close()


def supersede_goal(root, name, reference=None, reason=''):
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] not in ('active', 'blocked'):
        raise ProjectError(
          f'Only active or blocked goals can be superseded; '
          f'goal {goal_id} '
          f'is {goal["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE goal
        SET status = 'superseded', status_reason = ?, updated_at = ?
        WHERE id = ?
        """,
        (reason, timestamp, goal_id),
      )
      connection.execute(
        'UPDATE project_state SET active_goal_id = NULL '
        'WHERE active_goal_id = ?',
        (goal_id,),
      )
      _touch(connection)
  finally:
    connection.close()


def reopen_goal(root, name, reference=None):
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
        "WHERE goal_id = ? AND status = 'open' LIMIT 1",
        (goal_id,),
      ).fetchone():
        raise ProjectError(
          'A goal cannot reopen while it has open blockers'
        )
      active = connection.execute(
        'SELECT active_goal_id FROM project_state WHERE id = 1'
      ).fetchone()['active_goal_id']
      if active is not None and active != goal_id:
        raise ProjectError('Project already has another active goal')
      timestamp = current_time()
      connection.execute(
        """
        UPDATE goal
        SET status = 'active', status_reason = '', updated_at = ?
        WHERE id = ?
        """,
        (timestamp, goal_id),
      )
      connection.execute(
        'UPDATE project_state SET active_goal_id = ? WHERE id = 1',
        (goal_id,),
      )
      _touch(connection)
  finally:
    connection.close()


def block_goal(
  root, name, reference, description, impact='', attempts='', required=''
):
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
      return cursor.lastrowid
  finally:
    connection.close()


def read_project(root, name):
  connection = open_project(root, name)
  try:
    project = _row_dict(
      connection.execute('SELECT * FROM project').fetchone()
    )
    state = _row_dict(
      connection.execute('SELECT * FROM project_state').fetchone()
    )
    goal = (
      _read_goal_record(connection, state['active_goal_id'])
      if state['active_goal_id'] is not None
      else None
    )
    return {
      'path': str(database_path(root, name)),
      'project': project,
      'state': state,
      'goal': goal,
    }
  finally:
    connection.close()


def list_projects(root):
  directory = project_directory(root)
  if not directory.is_dir():
    return []
  projects = []
  for path in sorted(directory.glob(f'*{PROJECT_SUFFIX}')):
    connection = connect(path)
    try:
      row = connection.execute(
        'SELECT name, status, objective, updated_at FROM project'
      ).fetchone()
      if row is None:
        raise ProjectError(f'Project database has no project row: {path}')
      item = _row_dict(row)
      item['path'] = str(path)
      projects.append(item)
    finally:
      connection.close()
  return projects


def _ensure_project_complete(connection, acceptance=UNSET):
  project = connection.execute(
    'SELECT acceptance FROM project WHERE id = 1'
  ).fetchone()
  acceptance_value = (
    project['acceptance'] if acceptance is UNSET else acceptance
  )
  if not acceptance_value:
    raise ProjectError('Completing a project requires acceptance criteria')
  if connection.execute(
    "SELECT 1 FROM blocker WHERE status = 'open' LIMIT 1"
  ).fetchone():
    raise ProjectError(
      'Completing a project requires all blockers to be resolved'
    )
  if connection.execute(
    "SELECT 1 FROM goal WHERE status IN ('active', 'blocked') LIMIT 1"
  ).fetchone():
    raise ProjectError(
      'Completing a project requires all goals to be achieved or '
      'superseded'
    )
  if connection.execute(
    """
    SELECT 1 FROM task
    WHERE status IN ('planned', 'active', 'verifying', 'blocked')
    LIMIT 1
    """
  ).fetchone():
    raise ProjectError(
      'Completing a project requires unfinished tasks to be resolved'
    )
  if connection.execute(
    """
    SELECT 1 FROM stage
    WHERE status NOT IN ('achieved', 'superseded')
    LIMIT 1
    """
  ).fetchone():
    raise ProjectError(
      'Completing a project requires all stages to be achieved'
    )
  if (
    connection.execute('SELECT 1 FROM evidence LIMIT 1').fetchone() is None
  ):
    raise ProjectError('Completing a project requires recorded evidence')


def _prepare_project_values(values):
  allowed = {
    'objective',
    'scope',
    'non_goals',
    'constraints_text',
    'acceptance',
    'status',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  unknown = set(values) - allowed
  if unknown:
    raise ProjectError(f'Unknown project fields: {sorted(unknown)}')
  if 'status' in values and values['status'] not in PROJECT_STATUSES:
    raise ProjectError(f'Invalid project status: {values["status"]}')
  return values


def _apply_project_update(connection, values):
  if not values:
    return False
  if values.get('status') == 'complete':
    _ensure_project_complete(connection, values.get('acceptance', UNSET))
  assignments = ', '.join(f'{field} = ?' for field in values)
  parameters = list(values.values())
  if values.get('status') == 'complete':
    assignments += ', completed_at = ?'
    parameters.append(current_time())
  elif values.get('status') is not None:
    assignments += ', completed_at = NULL'
  connection.execute(
    f'UPDATE project SET {assignments} WHERE id = 1', parameters
  )
  return True


def update_project(root, name, **values):
  values = _prepare_project_values(values)
  connection = open_project(root, name)
  try:
    with connection:
      if _apply_project_update(connection, values):
        _touch(connection)
  finally:
    connection.close()


def update_state(
  root,
  name,
  summary=UNSET,
  next_action=UNSET,
  current_stage=UNSET,
  current_task=UNSET,
):
  values = {
    'summary': summary,
    'next_action': next_action,
    'current_stage': current_stage,
    'current_task': current_task,
  }
  connection = open_project(root, name)
  try:
    with connection:
      if _apply_state_update(connection, values):
        _touch(connection)
  finally:
    connection.close()


def _apply_state_update(connection, values):
  parameters = []
  assignments = []
  if values['summary'] is not UNSET:
    assignments.append('summary = ?')
    parameters.append(values['summary'])
  if values['next_action'] is not UNSET:
    assignments.append('next_action = ?')
    parameters.append(values['next_action'])
  if values['current_stage'] is not UNSET:
    assignments.append('current_stage_id = ?')
    parameters.append(_resolve_stage(connection, values['current_stage']))
  if values['current_task'] is not UNSET:
    task_id = _resolve_task(connection, values['current_task'])
    task = connection.execute(
      'SELECT status FROM task WHERE id = ?', (task_id,)
    ).fetchone()
    if task['status'] not in ('active', 'verifying', 'blocked'):
      raise ProjectError(
        'A handoff current task must be active, verifying, or blocked'
      )
    assignments.append('current_task_id = ?')
    parameters.append(task_id)
  if not assignments:
    return False
  connection.execute(
    f'UPDATE project_state SET {", ".join(assignments)} WHERE id = 1',
    parameters,
  )
  return True


def update_project_and_state(root, name, project_values, state_values):
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
  root,
  name,
  stage_name,
  outcome,
  purpose='',
  entry_conditions='',
  exit_evidence='',
):
  connection = open_project(root, name)
  try:
    with connection:
      position = connection.execute(
        'SELECT COALESCE(MAX(position), -1) + 1 FROM stage'
      ).fetchone()[0]
      cursor = connection.execute(
        """
        INSERT INTO stage
          (name, outcome, purpose, entry_conditions, exit_evidence,
           position,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          stage_name,
          outcome,
          purpose,
          entry_conditions,
          exit_evidence,
          position,
          current_time(),
          current_time(),
        ),
      )
      _touch(connection)
      return cursor.lastrowid
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not add stage: {error}') from error
  finally:
    connection.close()


def read_stages(root, name):
  connection = open_project(root, name)
  try:
    rows = connection.execute(
      """
      SELECT s.*,
        COALESCE((
          SELECT group_concat(d.name, ', ')
          FROM stage_dependency sd
          JOIN stage d ON d.id = sd.dependency_id
          WHERE sd.stage_id = s.id
        ), '') AS dependencies
      FROM stage s
      ORDER BY s.position, s.id
      """
    ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def update_stage(root, project_name, reference, **values):
  allowed = {
    'name',
    'outcome',
    'purpose',
    'entry_conditions',
    'exit_evidence',
    'status',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if set(values) - allowed:
    raise ProjectError('Unknown stage field')
  if 'status' in values and values['status'] not in STAGE_STATUSES:
    raise ProjectError(f'Invalid stage status: {values["status"]}')
  connection = open_project(root, project_name)
  try:
    stage_id = _resolve_stage(connection, reference)
    if not values:
      return
    stage = connection.execute(
      'SELECT status, exit_evidence FROM stage WHERE id = ?',
      (stage_id,),
    ).fetchone()
    if values.get('status') == 'active':
      dependency = connection.execute(
        """
        SELECT dependency_stage.name
        FROM stage_dependency
        JOIN stage dependency_stage
          ON dependency_stage.id = stage_dependency.dependency_id
        WHERE stage_dependency.stage_id = ?
          AND dependency_stage.status <> 'achieved'
        LIMIT 1
        """,
        (stage_id,),
      ).fetchone()
      if dependency is not None:
        raise ProjectError(
          f'Stage dependency is not achieved: {dependency["name"]}'
        )
    if values.get('status') == 'achieved':
      exit_evidence = values.get('exit_evidence', stage['exit_evidence'])
      evidence = connection.execute(
        'SELECT 1 FROM evidence WHERE stage_id = ? LIMIT 1',
        (stage_id,),
      ).fetchone()
      if not exit_evidence or evidence is None:
        raise ProjectError(
          'Achieving a stage requires exit evidence and a recorded '
          'evidence entry'
        )
    with connection:
      assignments = ', '.join(f'{field} = ?' for field in values)
      parameters = list(values.values())
      if values.get('status') == 'active':
        assignments += ', started_at = COALESCE(started_at, ?)'
        parameters.append(current_time())
      if values.get('status') == 'achieved':
        assignments += ', achieved_at = ?'
        parameters.append(current_time())
      assignments += ', updated_at = ?'
      parameters.append(current_time())
      parameters.append(stage_id)
      connection.execute(
        f'UPDATE stage SET {assignments} WHERE id = ?', parameters
      )
      if values.get('status') == 'active':
        connection.execute(
          'UPDATE project_state SET current_stage_id = ? WHERE id = 1',
          (stage_id,),
        )
      _touch(connection)
  finally:
    connection.close()


def add_stage_dependency(root, name, reference, dependency):
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


def add_task(
  root,
  name,
  title,
  purpose='',
  stage=None,
  priority=0,
  tags=(),
  goal=None,
):
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
          (
            goal_id, stage_id, title, purpose, priority, created_at,
            updated_at
          )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          title,
          purpose,
          priority,
          timestamp,
          timestamp,
        ),
      )
      task_id = cursor.lastrowid
      for tag in tags:
        _insert_tag(connection, task_id, tag)
      _touch(connection)
      return task_id
  finally:
    connection.close()


def _insert_tag(connection, task_id, tag):
  tag = tag.strip()
  if not tag:
    raise ProjectError('Task tags cannot be empty')
  connection.execute(
    'INSERT OR IGNORE INTO task_tag (task_id, tag) VALUES (?, ?)',
    (task_id, tag),
  )


def read_tasks(root, name, status=None, stage=None, tag=None, ready=False):
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
    if ready:
      clauses.append("t.status = 'planned'")
      clauses.append(
        """
        (
          t.stage_id IS NULL
          OR (
            EXISTS (
              SELECT 1 FROM stage ready_stage
              WHERE ready_stage.id = t.stage_id
                AND ready_stage.status = 'active'
            )
            AND NOT EXISTS (
              SELECT 1
              FROM stage_dependency ready_dependency
              JOIN stage dependency_stage
                ON dependency_stage.id = ready_dependency.dependency_id
              WHERE ready_dependency.stage_id = t.stage_id
                AND dependency_stage.status <> 'achieved'
            )
          )
        )
        """
      )
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    rows = connection.execute(
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
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def read_task_logs(connection, task_id, limit=20, since=None):
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
  return [_row_dict(row) for row in reversed(rows)]


def read_task(root, name, reference, limit=20, since=None):
  connection = open_project(root, name)
  try:
    task_id = _resolve_task(connection, reference)
    task = _row_dict(
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
    logs = read_task_logs(connection, task_id, limit, since)
    return {'task': task, 'logs': logs}
  finally:
    connection.close()


def update_task(root, name, reference, **values):
  allowed = {
    'title',
    'purpose',
    'status',
    'priority',
    'stage_id',
    'goal_id',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if set(values) - allowed:
    raise ProjectError('Unknown task field')
  if 'status' in values and values['status'] not in TASK_STATUSES:
    raise ProjectError(f'Invalid task status: {values["status"]}')
  connection = open_project(root, name)
  try:
    task_id = _resolve_task(connection, reference)
    if 'stage_id' in values:
      values['stage_id'] = _resolve_stage(connection, values['stage_id'])
    if 'goal_id' in values and values['goal_id'] is not None:
      values['goal_id'] = _resolve_goal(connection, values['goal_id'])
    if not values:
      return
    task = connection.execute(
      'SELECT stage_id, goal_id FROM task WHERE id = ?', (task_id,)
    ).fetchone()
    target_stage = values.get('stage_id', task['stage_id'])
    target_goal = values.get('goal_id', task['goal_id'])
    _ensure_goal_stage(connection, target_goal, target_stage, 'Task')
    with connection:
      assignments = ', '.join(f'{field} = ?' for field in values)
      parameters = list(values.values())
      status = values.get('status')
      timestamp = current_time()
      if status == 'active':
        _ensure_task_can_start(connection, task_id)
        assignments += (
          ', started_at = COALESCE(started_at, ?), completed_at = NULL'
        )
        parameters.append(timestamp)
      elif status == 'completed':
        assignments += ', completed_at = ?'
        parameters.append(timestamp)
      elif status is not None:
        assignments += ', completed_at = NULL'
      assignments += ', updated_at = ?'
      parameters.extend((timestamp, task_id))
      connection.execute(
        f'UPDATE task SET {assignments} WHERE id = ?', parameters
      )
      if status == 'active':
        connection.execute(
          'UPDATE project_state SET current_task_id = ? WHERE id = 1',
          (task_id,),
        )
      elif status in ('planned', 'completed', 'cancelled'):
        _clear_current_task(connection, task_id)
      if status is not None:
        connection.execute(
          'INSERT INTO task_log '
          '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
          (task_id, timestamp, 'status', f'Task status set to {status}'),
        )
      _touch(connection)
  finally:
    connection.close()


def append_task_log(root, name, reference, message, kind='note'):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, current_time(), kind, message),
      )
      connection.execute(
        'UPDATE task SET updated_at = ? WHERE id = ?',
        (current_time(), task_id),
      )
      _touch(connection)
  finally:
    connection.close()


def start_task(root, name, reference):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      _ensure_task_can_start(connection, task_id)
      timestamp = current_time()
      connection.execute(
        """
        UPDATE task
        SET status = 'active', started_at = COALESCE(started_at, ?),
          updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'started', 'Task started'),
      )
      connection.execute(
        'UPDATE project_state SET current_task_id = ? WHERE id = 1',
        (task_id,),
      )
      _touch(connection)
  finally:
    connection.close()


def _ensure_task_can_start(connection, task_id):
  task = connection.execute(
    'SELECT status FROM task WHERE id = ?', (task_id,)
  ).fetchone()
  if task['status'] in ('completed', 'cancelled', 'blocked'):
    raise ProjectError(f'Cannot start task in status {task["status"]}')
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open' LIMIT 1",
    (task_id,),
  ).fetchone():
    raise ProjectError('Cannot start a task with open blockers')


def _clear_current_task(connection, task_id):
  connection.execute(
    'UPDATE project_state SET current_task_id = NULL '
    'WHERE current_task_id = ?',
    (task_id,),
  )


def complete_task(root, name, reference):
  return _set_task_status(
    root, name, reference, 'completed', 'completed', 'Task completed'
  )


def reopen_task(root, name, reference):
  return _set_task_status(
    root, name, reference, 'planned', 'reopened', 'Task reopened'
  )


def _set_task_status(root, name, reference, status, kind, message):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      timestamp = current_time()
      if status == 'completed':
        connection.execute(
          'UPDATE task SET status = ?, completed_at = ?, '
          'updated_at = ? WHERE id = ?',
          (status, timestamp, timestamp, task_id),
        )
      else:
        connection.execute(
          'UPDATE task SET status = ?, completed_at = NULL, '
          'updated_at = ? WHERE id = ?',
          (status, timestamp, task_id),
        )
      if status in ('planned', 'completed', 'cancelled'):
        _clear_current_task(connection, task_id)
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, kind, message),
      )
      _touch(connection)
  finally:
    connection.close()


def block_task(
  root, name, reference, description, impact='', attempts='', required=''
):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (
            goal_id, task_id, description, impact, attempts, required,
            opened_at
          )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
          None,
          task_id,
          description,
          impact,
          attempts,
          required,
          timestamp,
        ),
      )
      blocker_id = cursor.lastrowid
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
      return blocker_id
  finally:
    connection.close()


def add_task_tags(root, name, reference, tags):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      for tag in tags:
        _insert_tag(connection, task_id, tag)
      _touch(connection)
  finally:
    connection.close()


def remove_task_tags(root, name, reference, tags):
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
  root,
  name,
  summary,
  rationale='',
  alternatives='',
  consequences='',
  stage=None,
  task=None,
  goal=None,
):
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
      _ensure_goal_stage(connection, goal_id, stage_id, 'Decision')
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
      return cursor.lastrowid
  finally:
    connection.close()


def read_decisions(root, name, limit=20):
  if limit <= 0:
    raise ProjectError('Decision limits must be positive')
  connection = open_project(root, name)
  try:
    rows = connection.execute(
      'SELECT * FROM decision ORDER BY decided_at DESC, id DESC LIMIT ?',
      (limit,),
    ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def add_blocker(
  root,
  name,
  description,
  impact='',
  attempts='',
  required='',
  stage=None,
  task=None,
  goal=None,
):
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
      if task_id is not None:
        task = connection.execute(
          'SELECT goal_id, stage_id FROM task WHERE id = ?', (task_id,)
        ).fetchone()
        if (
          goal_id is not None
          and task['goal_id'] is not None
          and task['goal_id'] != goal_id
        ):
          raise ProjectError('Blocker goal does not match task goal')
        if stage_id is None:
          stage_id = task['stage_id']
      _ensure_goal_stage(connection, goal_id, stage_id, 'Blocker')
      if goal_id is not None:
        goal_status = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()['status']
        if goal_status not in ('active', 'blocked'):
          raise ProjectError(
            f'Only active or blocked goals can receive blockers; goal '
            f'{goal_id} is {goal_status}'
          )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (
            goal_id, stage_id, task_id, description, impact, attempts,
            required, opened_at
          )
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
      if task_id is not None:
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
      if goal_id is not None:
        connection.execute(
          """
          UPDATE goal
          SET status = 'blocked', status_reason = ?, updated_at = ?
          WHERE id = ?
          """,
          (description, timestamp, goal_id),
        )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def read_blockers(root, name, status='open'):
  connection = open_project(root, name)
  try:
    if status == 'all':
      rows = connection.execute(
        'SELECT * FROM blocker ORDER BY opened_at DESC, id DESC'
      ).fetchall()
    else:
      rows = connection.execute(
        'SELECT * FROM blocker WHERE status = ? '
        'ORDER BY opened_at DESC, id DESC',
        (status,),
      ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def resolve_blocker(root, name, reference, resolution):
  connection = open_project(root, name)
  try:
    with connection:
      if not str(reference).isdigit():
        raise ProjectError(
          f'Blocker references must be numeric: {reference}'
        )
      timestamp = current_time()
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
      cursor = connection.execute(
        """
        UPDATE blocker
        SET status = 'resolved', resolved_at = ?, resolution = ?
        WHERE id = ? AND status = 'open'
        """,
        (timestamp, resolution, int(reference)),
      )
      if cursor.rowcount == 0:
        raise ProjectError(f'Open blocker does not exist: {reference}')
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
        task = connection.execute(
          'SELECT status FROM task WHERE id = ?', (blocker['task_id'],)
        ).fetchone()
        if remaining is None and task['status'] == 'blocked':
          connection.execute(
            """
            UPDATE task
            SET status = 'planned', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, blocker['task_id']),
          )
          _clear_current_task(connection, blocker['task_id'])
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
      if blocker['goal_id'] is not None:
        remaining_goal = connection.execute(
          """
          SELECT 1 FROM blocker
          WHERE goal_id = ? AND status = 'open'
          LIMIT 1
          """,
          (blocker['goal_id'],),
        ).fetchone()
        goal = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker['goal_id'],)
        ).fetchone()
        active_goal = connection.execute(
          'SELECT active_goal_id FROM project_state WHERE id = 1'
        ).fetchone()['active_goal_id']
        if (
          remaining_goal is None
          and goal['status'] == 'blocked'
          and (active_goal is None or active_goal == blocker['goal_id'])
        ):
          connection.execute(
            """
            UPDATE goal
            SET status = 'active', status_reason = '', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, blocker['goal_id']),
          )
          connection.execute(
            'UPDATE project_state SET active_goal_id = ? WHERE id = 1',
            (blocker['goal_id'],),
          )
      _touch(connection)
  finally:
    connection.close()


def add_evidence(
  root, name, claim, source='', result='', stage=None, task=None, goal=None
):
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
      if task_id is not None:
        task_goal = connection.execute(
          'SELECT goal_id, stage_id FROM task WHERE id = ?', (task_id,)
        ).fetchone()
        if goal_id is None:
          goal_id = task_goal['goal_id']
        elif (
          task_goal['goal_id'] is not None
          and task_goal['goal_id'] != goal_id
        ):
          raise ProjectError('Evidence goal does not match task goal')
        if stage_id is None:
          stage_id = task_goal['stage_id']
      _ensure_goal_stage(connection, goal_id, stage_id, 'Evidence')
      cursor = connection.execute(
        """
        INSERT INTO evidence
          (goal_id, stage_id, task_id, claim, source, result, captured_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          claim,
          source,
          result,
          current_time(),
        ),
      )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def read_evidence(root, name, limit=20):
  if limit <= 0:
    raise ProjectError('Evidence limits must be positive')
  connection = open_project(root, name)
  try:
    rows = connection.execute(
      'SELECT * FROM evidence ORDER BY captured_at DESC, id DESC LIMIT ?',
      (limit,),
    ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def read_handoff(root, name):
  connection = open_project(root, name)
  try:
    project = _row_dict(
      connection.execute('SELECT * FROM project').fetchone()
    )
    state = _row_dict(
      connection.execute('SELECT * FROM project_state').fetchone()
    )
    goal = (
      _read_goal_record(connection, state['active_goal_id'])
      if state['active_goal_id'] is not None
      else None
    )
    stage = None
    if state['current_stage_id'] is not None:
      stage = _row_dict(
        connection.execute(
          'SELECT * FROM stage WHERE id = ?', (state['current_stage_id'],)
        ).fetchone()
      )
    task = None
    if state['current_task_id'] is not None:
      task = _row_dict(
        connection.execute(
          'SELECT * FROM task WHERE id = ?', (state['current_task_id'],)
        ).fetchone()
      )
    blockers = [
      _row_dict(row)
      for row in connection.execute(
        'SELECT id, description, required FROM blocker '
        "WHERE status = 'open' "
        'ORDER BY opened_at DESC, id DESC LIMIT 5'
      ).fetchall()
    ]
    decisions = [
      _row_dict(row)
      for row in connection.execute(
        'SELECT id, summary, decided_at FROM decision '
        'ORDER BY decided_at DESC, id DESC LIMIT 5'
      ).fetchall()
    ]
    evidence = [
      _row_dict(row)
      for row in connection.execute(
        'SELECT id, claim, source, result, captured_at FROM evidence '
        'ORDER BY captured_at DESC, id DESC LIMIT 5'
      ).fetchall()
    ]
    logs = []
    if task is not None:
      logs = [
        _row_dict(row)
        for row in connection.execute(
          'SELECT occurred_at, kind, message FROM task_log '
          'WHERE task_id = ? ORDER BY occurred_at DESC, id DESC LIMIT 5',
          (task['id'],),
        ).fetchall()
      ]
    return {
      'path': str(database_path(root, name)),
      'project': project,
      'state': state,
      'goal': goal,
      'stage': stage,
      'task': task,
      'blockers': blockers,
      'decisions': decisions,
      'evidence': evidence,
      'logs': logs,
    }
  finally:
    connection.close()


def format_handoff(data):
  project = data['project']
  state = data['state']
  stage = data['stage']
  task = data['task']
  goal = data['goal']
  lines = [
    f'Project: {project["name"]}',
    f'Status: {project["status"]}',
    f'Objective: {project["objective"]}',
    f'Project database: {data["path"]}',
    f'Active goal: {goal["goal"]["id"]} ({goal["goal"]["status"]})'
    if goal
    else 'Active goal: -',
    f'Goal text: {goal["goal"]["text"]}' if goal else 'Goal text: -',
    f'Current stage: {stage["name"] if stage else "-"}',
    f'Current task: {task["id"]} {task["title"]}'
    if task
    else 'Current task: -',
    f'Summary: {state["summary"] or "-"}',
    f'Next action: {state["next_action"] or "-"}',
  ]
  if data['blockers']:
    lines.append('Open blockers:')
    lines.extend(
      f'- {item["id"]}: {item["description"]}' for item in data['blockers']
    )
  if data['decisions']:
    lines.append('Recent decisions:')
    lines.extend(
      f'- {item["id"]}: {item["summary"]}' for item in data['decisions']
    )
  if data['evidence']:
    lines.append('Recent evidence:')
    lines.extend(
      f'- {item["id"]}: {item["claim"]}' for item in data['evidence']
    )
  if data['logs']:
    lines.append('Recent current-task log:')
    lines.extend(
      f'- {item["kind"]}: {item["message"]}'
      for item in reversed(data['logs'])
    )
  return '\n'.join(lines)


def format_project_details(data):
  project = data['project']
  state = data['state']
  goal = data['goal']
  return '\n'.join(
    [
      f'Project: {project["name"]}',
      f'Status: {project["status"]}',
      f'Objective: {project["objective"]}',
      f'Scope: {project["scope"] or "-"}',
      f'Non-goals: {project["non_goals"] or "-"}',
      f'Constraints: {project["constraints_text"] or "-"}',
      f'Acceptance: {project["acceptance"] or "-"}',
      f'Active goal: {goal["goal"]["id"]} ({goal["goal"]["status"]})'
      if goal
      else 'Active goal: -',
      f'Goal text: {goal["goal"]["text"]}' if goal else 'Goal text: -',
      f'Created: {format_time(project["created_at"])}',
      f'Updated: {format_time(project["updated_at"])}',
      f'Summary: {state["summary"] or "-"}',
      f'Next action: {state["next_action"] or "-"}',
      f'Current stage id: {state["current_stage_id"] or "-"}',
      f'Current task id: {state["current_task_id"] or "-"}',
      f'State revision: {state["revision"]}',
    ]
  )


def _project_root(ctx):
  return ctx.obj['project_root']


def _json_or_echo(value, as_json):
  if as_json:
    click.echo(json.dumps(value, indent=2, sort_keys=True))
  else:
    click.echo(value)


def _invoke(function, *args, **kwargs):
  try:
    return function(*args, **kwargs)
  except (ProjectError, sqlite3.Error) as error:
    raise click.ClickException(str(error)) from error


@click.group(cls=lib.AliasedGroup)
@click.option(
  '--root', type=click.Path(file_okay=False, path_type=Path), hidden=True
)
@click.pass_context
def project_group(ctx, root):
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
  ctx, name, objective, scope, non_goals, constraints, acceptance
):
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
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def list_command(ctx, as_json):
  """List active project databases."""
  projects = _invoke(list_projects, _project_root(ctx))
  if as_json:
    _json_or_echo(projects, True)
    return
  for project in projects:
    click.echo(
      f'{project["name"]}\t{project["status"]}\t{format_time(project["updated_at"])}\t{project["objective"]}'
    )


@project_group.command('status')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def status_command(ctx, name, as_json):
  """Read compact current project state."""
  data = _invoke(read_handoff, _project_root(ctx), name)
  _json_or_echo(data, as_json) if as_json else click.echo(
    format_handoff(data)
  )


@project_group.command('handoff')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def handoff_command(ctx, name, as_json):
  """Produce a compact handoff for a new session."""
  data = _invoke(read_handoff, _project_root(ctx), name)
  _json_or_echo(data, as_json) if as_json else click.echo(
    format_handoff(data)
  )


@project_group.command('show')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def show_command(ctx, name, as_json):
  """Read the project charter and current state."""
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
@click.option('--status', type=click.Choice(PROJECT_STATUSES))
@click.option('--summary')
@click.option('--next-action')
@click.option('--current-stage')
@click.option('--current-task')
@click.pass_context
def update_command(
  ctx,
  name,
  objective,
  scope,
  non_goals,
  constraints,
  acceptance,
  status,
  summary,
  next_action,
  current_stage,
  current_task,
):
  """Update charter or current project state."""
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
      'status': status if status is not None else UNSET,
    },
    {
      'summary': summary if summary is not None else UNSET,
      'next_action': next_action if next_action is not None else UNSET,
      'current_stage': current_stage
      if current_stage is not None
      else UNSET,
      'current_task': current_task if current_task is not None else UNSET,
    },
  )


@project_group.command('archive')
@click.argument('name')
@click.pass_context
def archive_command(ctx, name):
  """Move an active project database into the archive."""
  click.echo(_invoke(archive_project, _project_root(ctx), name))


@project_group.group(cls=lib.AliasedGroup)
def goal():
  """Manage the project's durable current line of progress."""


@goal.command('list')
@click.argument('name')
@click.option('--status', type=click.Choice(GOAL_STATUSES))
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_list_command(ctx, name, status, as_json):
  goals = _invoke(read_goals, _project_root(ctx), name, status)
  if as_json:
    _json_or_echo(goals, True)
  else:
    for item in goals:
      marker = '*' if item['is_active'] else '-'
      click.echo(
        f'{marker}\t{item["id"]}\t{item["status"]}\t'
        f'{item["stage_names"]}\t{item["text"]}'
      )


@goal.command('set')
@click.argument('name')
@click.option('--text', required=True)
@click.option('--stage', 'stages', multiple=True, required=True)
@click.pass_context
def goal_set_command(ctx, name, text, stages):
  click.echo(_invoke(create_goal, _project_root(ctx), name, text, stages))


@goal.command('show')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_show_command(ctx, name, goal_reference, as_json):
  data = _invoke(read_goal, _project_root(ctx), name, goal_reference)
  _json_or_echo(data, as_json) if as_json else click.echo(
    json.dumps(data, indent=2, sort_keys=True)
  )


@goal.command('text')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_text_command(ctx, name, goal_reference):
  click.echo(
    _invoke(goal_text, _project_root(ctx), name, goal_reference), nl=False
  )


@goal.command('copy')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_copy_command(ctx, name, goal_reference):
  click.echo(
    _invoke(copy_goal, _project_root(ctx), name, goal_reference), nl=False
  )


@goal.command('achieve')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_achieve_command(ctx, name, goal_reference):
  _invoke(achieve_goal, _project_root(ctx), name, goal_reference)


@goal.command('block')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', default='')
@click.pass_context
def goal_block_command(
  ctx, name, goal_reference, description, impact, attempts, required
):
  click.echo(
    _invoke(
      block_goal,
      _project_root(ctx),
      name,
      goal_reference,
      description,
      impact,
      attempts,
      required,
    )
  )


@goal.command('reopen')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_reopen_command(ctx, name, goal_reference):
  _invoke(reopen_goal, _project_root(ctx), name, goal_reference)


@goal.command('supersede')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.option('--reason', default='')
@click.pass_context
def goal_supersede_command(ctx, name, goal_reference, reason):
  _invoke(
    supersede_goal,
    _project_root(ctx),
    name,
    goal_reference,
    reason,
  )


@project_group.group(cls=lib.AliasedGroup)
def stage():
  """Manage project stages."""


@stage.command('list')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_list_command(ctx, name, as_json):
  stages = _invoke(read_stages, _project_root(ctx), name)
  if as_json:
    _json_or_echo(stages, True)
  else:
    for item in stages:
      click.echo(
        f'{item["id"]}\t{item["status"]}\t{item["name"]}\t{item["outcome"]}'
      )


@stage.command('add')
@click.argument('name')
@click.argument('stage_name')
@click.option('--outcome', required=True)
@click.option('--purpose', default='')
@click.option('--entry-conditions', default='')
@click.option('--exit-evidence', default='')
@click.pass_context
def stage_add_command(
  ctx, name, stage_name, outcome, purpose, entry_conditions, exit_evidence
):
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
@click.argument('stage_reference')
@click.option('--stage-name')
@click.option('--outcome')
@click.option('--purpose')
@click.option('--entry-conditions')
@click.option('--exit-evidence')
@click.option('--status', type=click.Choice(STAGE_STATUSES))
@click.pass_context
def stage_update_command(
  ctx,
  name,
  stage_reference,
  stage_name,
  outcome,
  purpose,
  entry_conditions,
  exit_evidence,
  status,
):
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
    status=status if status is not None else UNSET,
  )


@stage.command('start')
@click.argument('name')
@click.argument('stage_reference')
@click.pass_context
def stage_start_command(ctx, name, stage_reference):
  _invoke(
    update_stage,
    _project_root(ctx),
    name,
    stage_reference,
    status='active',
  )


@stage.command('achieve')
@click.argument('name')
@click.argument('stage_reference')
@click.pass_context
def stage_achieve_command(ctx, name, stage_reference):
  _invoke(
    update_stage,
    _project_root(ctx),
    name,
    stage_reference,
    status='achieved',
  )


@stage.command('depend')
@click.argument('name')
@click.argument('stage_reference')
@click.argument('dependency')
@click.pass_context
def stage_depend_command(ctx, name, stage_reference, dependency):
  _invoke(
    add_stage_dependency,
    _project_root(ctx),
    name,
    stage_reference,
    dependency,
  )


@project_group.group(cls=lib.AliasedGroup)
def task():
  """Manage project tasks."""


@task.command('list')
@click.argument('name')
@click.option('--status', type=click.Choice(TASK_STATUSES))
@click.option('--stage')
@click.option('--tag')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_list_command(ctx, name, status, stage, tag, as_json):
  tasks = _invoke(read_tasks, _project_root(ctx), name, status, stage, tag)
  if as_json:
    _json_or_echo(tasks, True)
  else:
    for item in tasks:
      click.echo(
        f'{item["id"]}\t{item["status"]}\t{item["stage_name"] or "-"}'
        f'\t{item["title"]}\t{item["tags"]}'
      )


@task.command('ready')
@click.argument('name')
@click.option('--tag')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_ready_command(ctx, name, tag, as_json):
  tasks = _invoke(
    read_tasks, _project_root(ctx), name, tag=tag, ready=True
  )
  if as_json:
    _json_or_echo(tasks, True)
  else:
    for item in tasks:
      click.echo(
        f'{item["id"]}\t{item["stage_name"] or "-"}\t{item["title"]}'
      )


@task.command('add')
@click.argument('name')
@click.option('--title', required=True)
@click.option('--purpose', default='')
@click.option('--stage')
@click.option('--priority', default=0, type=int)
@click.option('--tag', multiple=True)
@click.option('--goal')
@click.pass_context
def task_add_command(
  ctx, name, title, purpose, stage, priority, tag, goal
):
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
    )
  )


@task.command('show')
@click.argument('name')
@click.argument('task_reference')
@click.option('--limit', default=20, type=int)
@click.option('--since', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_show_command(ctx, name, task_reference, limit, since, as_json):
  data = _invoke(
    read_task,
    _project_root(ctx),
    name,
    task_reference,
    limit,
    since,
  )
  _json_or_echo(data, as_json) if as_json else click.echo(
    json.dumps(data, indent=2, sort_keys=True)
  )


@task.command('logs')
@click.argument('name')
@click.argument('task_reference')
@click.option('--limit', default=20, type=int)
@click.option('--since', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_logs_command(ctx, name, task_reference, limit, since, as_json):
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
  else:
    for entry in logs:
      click.echo(
        f'{format_time(entry["occurred_at"])}\t'
        f'{entry["kind"]}\t{entry["message"]}'
      )


@task.command('update')
@click.argument('name')
@click.argument('task_reference')
@click.option('--title')
@click.option('--purpose')
@click.option('--status', type=click.Choice(TASK_STATUSES))
@click.option('--priority', type=int)
@click.option('--stage')
@click.option('--goal')
@click.pass_context
def task_update_command(
  ctx,
  name,
  task_reference,
  title,
  purpose,
  status,
  priority,
  stage,
  goal,
):
  _invoke(
    update_task,
    _project_root(ctx),
    name,
    task_reference,
    title=title if title is not None else UNSET,
    purpose=purpose if purpose is not None else UNSET,
    status=status if status is not None else UNSET,
    priority=priority if priority is not None else UNSET,
    stage_id=stage if stage is not None else UNSET,
    goal_id=goal if goal is not None else UNSET,
  )


@task.command('start')
@click.argument('name')
@click.argument('task_reference')
@click.pass_context
def task_start_command(ctx, name, task_reference):
  _invoke(start_task, _project_root(ctx), name, task_reference)


@task.command('complete')
@click.argument('name')
@click.argument('task_reference')
@click.pass_context
def task_complete_command(ctx, name, task_reference):
  _invoke(complete_task, _project_root(ctx), name, task_reference)


@task.command('reopen')
@click.argument('name')
@click.argument('task_reference')
@click.pass_context
def task_reopen_command(ctx, name, task_reference):
  _invoke(reopen_task, _project_root(ctx), name, task_reference)


@task.command('log')
@click.argument('name')
@click.argument('task_reference')
@click.argument('message')
@click.option('--kind', default='note')
@click.pass_context
def task_log_command(ctx, name, task_reference, message, kind):
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
@click.argument('task_reference')
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', default='')
@click.pass_context
def task_block_command(
  ctx, name, task_reference, description, impact, attempts, required
):
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


@task.command('tag')
@click.argument('name')
@click.argument('task_reference')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_tag_command(ctx, name, task_reference, tags):
  _invoke(add_task_tags, _project_root(ctx), name, task_reference, tags)


@task.command('untag')
@click.argument('name')
@click.argument('task_reference')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_untag_command(ctx, name, task_reference, tags):
  _invoke(remove_task_tags, _project_root(ctx), name, task_reference, tags)


@project_group.group(cls=lib.AliasedGroup)
def decision():
  """Manage project decisions."""


@decision.command('add')
@click.argument('name')
@click.option('--summary', required=True)
@click.option('--rationale', default='')
@click.option('--alternatives', default='')
@click.option('--consequences', default='')
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.pass_context
def decision_add_command(
  ctx,
  name,
  summary,
  rationale,
  alternatives,
  consequences,
  stage,
  task,
  goal,
):
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
@click.option('--limit', default=20, type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def decision_list_command(ctx, name, limit, as_json):
  decisions = _invoke(read_decisions, _project_root(ctx), name, limit)
  if as_json:
    _json_or_echo(decisions, True)
  else:
    for item in decisions:
      click.echo(
        f'{item["id"]}\t{format_time(item["decided_at"])}\t{item["summary"]}'
      )


@project_group.group(cls=lib.AliasedGroup)
def blocker():
  """Manage project blockers."""


@blocker.command('add')
@click.argument('name')
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', default='')
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.pass_context
def blocker_add_command(
  ctx, name, description, impact, attempts, required, stage, task, goal
):
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
  '--status', type=click.Choice((*BLOCKER_STATUSES, 'all')), default='open'
)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def blocker_list_command(ctx, name, status, as_json):
  blockers = _invoke(read_blockers, _project_root(ctx), name, status)
  if as_json:
    _json_or_echo(blockers, True)
  else:
    for item in blockers:
      click.echo(f'{item["id"]}\t{item["status"]}\t{item["description"]}')


@blocker.command('resolve')
@click.argument('name')
@click.argument('blocker_reference')
@click.option('--resolution', required=True)
@click.pass_context
def blocker_resolve_command(ctx, name, blocker_reference, resolution):
  _invoke(
    resolve_blocker,
    _project_root(ctx),
    name,
    blocker_reference,
    resolution,
  )


@project_group.group(cls=lib.AliasedGroup)
def evidence():
  """Manage project evidence."""


@evidence.command('add')
@click.argument('name')
@click.option('--claim', required=True)
@click.option('--source', default='')
@click.option('--result', default='')
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.pass_context
def evidence_add_command(
  ctx, name, claim, source, result, stage, task, goal
):
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
@click.option('--limit', default=20, type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def evidence_list_command(ctx, name, limit, as_json):
  entries = _invoke(read_evidence, _project_root(ctx), name, limit)
  if as_json:
    _json_or_echo(entries, True)
  else:
    for item in entries:
      click.echo(
        f'{item["id"]}\t{format_time(item["captured_at"])}\t{item["claim"]}'
      )
