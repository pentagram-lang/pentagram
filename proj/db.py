from __future__ import annotations

import sqlite3
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

SCHEMA_VERSION = 1

SCHEMA_SQL = f"""
PRAGMA foreign_keys = ON;
PRAGMA user_version = {SCHEMA_VERSION};
CREATE TABLE project (
  id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT NOT NULL,
  objective TEXT NOT NULL, scope TEXT NOT NULL DEFAULT '',
  non_goals TEXT NOT NULL DEFAULT '',
  constraints_text TEXT NOT NULL DEFAULT '',
  acceptance TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
  next_action TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
) STRICT;
CREATE TABLE stage (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, outcome TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  entry_conditions TEXT NOT NULL DEFAULT '',
  exit_evidence TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL,
  achievement_evidence_id INTEGER REFERENCES evidence(id),
  achieved_at INTEGER, created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
) STRICT;
CREATE TABLE stage_dependency (
  stage_id INTEGER NOT NULL REFERENCES stage(id),
  dependency_id INTEGER NOT NULL REFERENCES stage(id),
  PRIMARY KEY (stage_id, dependency_id), CHECK (stage_id != dependency_id)
) STRICT;
CREATE TABLE goal (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL CHECK (
    length(text) <= 4000 AND instr(text, char(0)) = 0
  ),
  status TEXT NOT NULL CHECK (
    status IN ('active', 'pending', 'blocked', 'achieved', 'cancelled')
  ),
  status_reason TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL,
  started_at INTEGER NOT NULL, achieved_at INTEGER,
  updated_at INTEGER NOT NULL
) STRICT;
CREATE UNIQUE INDEX idx_goal_active
  ON goal(status) WHERE status = 'active';
CREATE TABLE goal_stage (
  goal_id INTEGER NOT NULL REFERENCES goal(id),
  stage_id INTEGER NOT NULL REFERENCES stage(id),
  PRIMARY KEY (goal_id, stage_id)
) STRICT;
CREATE TABLE task (
  id INTEGER PRIMARY KEY, goal_id INTEGER REFERENCES goal(id),
  stage_id INTEGER REFERENCES stage(id), title TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT '',
  exclusions TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
  completion_evidence TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (
    status IN ('pending', 'active', 'blocked', 'completed', 'cancelled')
  ),
  priority INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL,
  started_at INTEGER, completed_at INTEGER, updated_at INTEGER NOT NULL
) STRICT;
CREATE UNIQUE INDEX idx_task_active
  ON task(status) WHERE status = 'active';
CREATE TABLE task_tag (
  task_id INTEGER NOT NULL REFERENCES task(id), tag TEXT NOT NULL,
  PRIMARY KEY (task_id, tag)
) STRICT;
CREATE TABLE task_log (
  id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES task(id),
  occurred_at INTEGER NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL
) STRICT;
CREATE TABLE blocker (
  id INTEGER PRIMARY KEY, goal_id INTEGER REFERENCES goal(id),
  stage_id INTEGER REFERENCES stage(id),
  task_id INTEGER REFERENCES task(id),
  description TEXT NOT NULL, impact TEXT NOT NULL DEFAULT '',
  attempts TEXT NOT NULL DEFAULT '', required TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'resolved', 'withdrawn')),
  opened_at INTEGER NOT NULL, resolved_at INTEGER,
  resolution TEXT NOT NULL DEFAULT '',
  CHECK (task_id IS NOT NULL OR goal_id IS NOT NULL)
) STRICT;
CREATE TABLE decision (
  id INTEGER PRIMARY KEY, goal_id INTEGER REFERENCES goal(id),
  stage_id INTEGER REFERENCES stage(id),
  task_id INTEGER REFERENCES task(id),
  summary TEXT NOT NULL, rationale TEXT NOT NULL DEFAULT '',
  alternatives TEXT NOT NULL DEFAULT '',
  consequences TEXT NOT NULL DEFAULT '', decided_at INTEGER NOT NULL
) STRICT;
CREATE TABLE evidence (
  id INTEGER PRIMARY KEY, goal_id INTEGER REFERENCES goal(id),
  stage_id INTEGER REFERENCES stage(id),
  task_id INTEGER REFERENCES task(id),
  claim TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT '', captured_at INTEGER NOT NULL
) STRICT;
"""


class ProjectError(Exception):
  """Domain, validation, or storage error in the project workflow."""


def is_substantive(text: str) -> bool:
  return bool(text.strip())


def require_substantive(text: str, label: str) -> str:
  if not is_substantive(text):
    raise ProjectError(f'{label} must contain non-whitespace text')
  return text


def parse_project_name(raw: str) -> str:
  if not raw:
    raise ProjectError('Project name must not be empty')
  if len(raw) > 200:
    raise ProjectError('Project name must be at most 200 characters')
  if not raw.isprintable():
    raise ProjectError('Project name must contain only printable text')
  if '/' in raw or '\\' in raw or '\x00' in raw:
    raise ProjectError('Project name must not contain path separators')
  if raw in ('.', '..') or raw.endswith('.sqlite3'):
    raise ProjectError(f'Invalid project name: {raw!r}')
  return raw


def _configure(conn: sqlite3.Connection) -> sqlite3.Connection:
  conn.row_factory = sqlite3.Row
  conn.execute('PRAGMA foreign_keys = ON')
  return conn


def init_schema(conn: sqlite3.Connection) -> None:
  conn.executescript(SCHEMA_SQL)


def connect_memory() -> sqlite3.Connection:
  conn = _configure(sqlite3.connect(':memory:'))
  init_schema(conn)
  return conn


def init_project(
  conn: sqlite3.Connection,
  *,
  name: str,
  objective: str,
  scope: str = '',
  non_goals: str = '',
  constraints_text: str = '',
  acceptance: str = '',
  summary: str = '',
  next_action: str = '',
  now: int | None = None,
) -> None:
  parse_project_name(name)
  require_substantive(objective, 'objective')
  ts = int(time.time()) if now is None else now
  with conn:
    conn.execute(
      'INSERT INTO project (id, name, objective, scope, non_goals, '
      'constraints_text, acceptance, summary, next_action, created_at, '
      'updated_at) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
      (
        name,
        objective,
        scope,
        non_goals,
        constraints_text,
        acceptance,
        summary,
        next_action,
        ts,
        ts,
      ),
    )


def _connect_file(
  path: Path, *, readonly: bool = False
) -> sqlite3.Connection:
  if readonly:
    return sqlite3.connect(f'file:{quote(str(path))}?mode=ro', uri=True)
  return sqlite3.connect(path)


def _has_project_table(path: Path) -> bool:
  try:
    conn = _connect_file(path, readonly=True)
  except sqlite3.Error as exc:
    raise ProjectError(f'Cannot open SQLite file {path}: {exc}') from exc
  try:
    return (
      conn.execute(
        'SELECT 1 FROM sqlite_master '
        "WHERE type = 'table' AND name = 'project'"
      ).fetchone()
      is not None
    )
  except sqlite3.Error as exc:
    raise ProjectError(f'Cannot read SQLite file {path}: {exc}') from exc
  finally:
    conn.close()


def _project_path(root: Path, name: str) -> Path:
  return root / '.tmp' / f'{parse_project_name(name)}.sqlite3'


@contextmanager
def open_project(
  root: Path, name: str, *, readonly: bool = False
) -> Iterator[sqlite3.Connection]:
  path = _project_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project database does not exist: {path}')
  conn: sqlite3.Connection | None = None
  try:
    conn = _configure(_connect_file(path, readonly=readonly))
    has_proj = conn.execute(
      'SELECT 1 FROM sqlite_master '
      "WHERE type = 'table' AND name = 'project'"
    ).fetchone()
    if has_proj is None:
      raise ProjectError(f'Not a project database: {path}')
    ver = conn.execute('PRAGMA user_version').fetchone()[0]
    if ver != SCHEMA_VERSION:
      raise ProjectError(f'Unsupported schema version {ver} in {path}')
    row = conn.execute('SELECT name FROM project WHERE id = 1').fetchone()
    if row is None or row['name'] != name:
      raise ProjectError(f'Project name mismatch in {path}')
  except sqlite3.Error as exc:
    if conn is not None:
      conn.close()
    raise ProjectError(f'Invalid project database {path}: {exc}') from exc
  except BaseException:
    if conn is not None:
      conn.close()
    raise
  try:
    yield conn
  finally:
    conn.close()


def archive_project_db(
  root: Path, name: str, *, now: int | None = None
) -> Path:
  path = _project_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project database does not exist: {path}')
  if not _has_project_table(path):
    raise ProjectError(
      f'Refusing to archive non-project SQLite database: {path}'
    )
  ts = int(time.time()) if now is None else now
  arch = root / '.tmp' / 'archive'
  arch.mkdir(parents=True, exist_ok=True)
  dest = arch / f'{name}-{ts}.sqlite3'
  n = 1
  while dest.exists():
    dest = arch / f'{name}-{ts}-{n}.sqlite3'
    n += 1
  path.replace(dest)
  return dest


def create_project_db(
  root: Path,
  *,
  name: str,
  objective: str,
  scope: str = '',
  non_goals: str = '',
  constraints_text: str = '',
  acceptance: str = '',
  summary: str = '',
  next_action: str = '',
  now: int | None = None,
) -> Path:
  path = _project_path(root, name)
  require_substantive(objective, 'objective')
  if path.exists():
    if not path.is_file():
      raise ProjectError(f'Project path is not a regular file: {path}')
    if not _has_project_table(path):
      raise ProjectError(
        f'Refusing to overwrite non-project SQLite database: {path}'
      )
    archive_project_db(root, name, now=now)
  path.parent.mkdir(parents=True, exist_ok=True)
  with tempfile.NamedTemporaryFile(
    dir=path.parent, prefix=f'.{name}.', suffix='.tmp', delete=False
  ) as tmp:
    tmp_path = Path(tmp.name)
  try:
    conn = _configure(_connect_file(tmp_path))
    try:
      init_schema(conn)
      init_project(
        conn,
        name=name,
        objective=objective,
        scope=scope,
        non_goals=non_goals,
        constraints_text=constraints_text,
        acceptance=acceptance,
        summary=summary,
        next_action=next_action,
        now=now,
      )
    finally:
      conn.close()
    tmp_path.replace(path)
  except BaseException:
    tmp_path.unlink(missing_ok=True)
    raise
  return path


def iter_project_dbs(root: Path) -> list[tuple[str, Path]]:
  tmp_dir = root / '.tmp'
  if not tmp_dir.is_dir():
    return []
  return [
    (parse_project_name(p.stem), p)
    for p in sorted(tmp_dir.iterdir(), key=lambda p: p.name)
    if p.is_file()
    and p.name.endswith('.sqlite3')
    and _has_project_table(p)
  ]
