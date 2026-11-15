"""Append-only records for CI test observations."""

import os
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

type CompletedTestOutcome = Literal[
  'passed', 'failed', 'skipped', 'xfailed', 'xpassed'
]
type TestOutcome = CompletedTestOutcome | Literal['incomplete']

_EXITED_PROCESS_STATES: Final[frozenset[str]] = frozenset({'Z', 'X', 'x'})


@dataclass(frozen=True, slots=True)
class RunIdentity:
  build_id: str
  job_id: str
  source_revision: str


@dataclass(frozen=True, slots=True)
class CheckStarted:
  occurred_at_ns: int


@dataclass(frozen=True, slots=True)
class CheckFinished:
  occurred_at_ns: int
  exit_code: int


type RunEvent = CheckStarted | CheckFinished


@dataclass(frozen=True, slots=True)
class TestCase:
  __test__ = False
  suite: str
  nodeid: str
  worker_id: str


@dataclass(frozen=True, slots=True)
class CompletedTestResult:
  start_event_id: int
  test: TestCase
  outcome: CompletedTestOutcome
  started_at_ns: int
  ended_at_ns: int
  duration_ns: int


def run_id(identity: RunIdentity) -> str:
  return f'{identity.build_id}:{identity.job_id}'


@dataclass(frozen=True, slots=True)
class ResourceSample:
  sampled_at_ns: int
  interval_ns: int
  cpu_cores: float
  memory_rss_bytes: int
  read_bytes_per_second: float | None
  write_bytes_per_second: float | None


@dataclass(frozen=True, slots=True)
class ProcessCounters:
  cpu_ticks: int = 0
  read_bytes: int = 0
  write_bytes: int = 0


@dataclass(frozen=True, slots=True)
class ProcessInfo:
  state: str
  session_id: int
  start_time_ticks: int
  counters: ProcessCounters
  memory_rss_bytes: int


@dataclass(frozen=True, slots=True)
class ProcFs:
  list_entries: Callable[[], Iterable[str]]
  read_text: Callable[[int, Literal['stat', 'io']], str]


def proc_fs(proc_root: Path) -> ProcFs:
  def read_text(pid: int, name: Literal['stat', 'io']) -> str:
    errors = 'replace' if name == 'stat' else 'strict'
    return (
      (proc_root / str(pid) / name)
      .read_bytes()
      .decode('utf-8', errors=errors)
    )

  return ProcFs(
    list_entries=lambda: (entry.name for entry in proc_root.iterdir()),
    read_text=read_text,
  )


@dataclass(frozen=True, slots=True)
class ProcessObservation:
  wall_time_ns: int
  monotonic_ns: int
  counters: ProcessCounters
  memory_rss_bytes: int
  io_counters_available: bool


@dataclass(frozen=True, slots=True)
class ProcessCounterState:
  active: dict[tuple[int, int], ProcessCounters]
  retired: ProcessCounters
  io_counters_available: bool = True


SCHEMA_SQL = """
CREATE TABLE run (
  run_id TEXT PRIMARY KEY,
  build_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  source_revision TEXT NOT NULL,
  python_version TEXT NOT NULL,
  started_at_ns INTEGER NOT NULL
);

CREATE TABLE run_event (
  event_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(run_id),
  source_revision TEXT NOT NULL,
  event TEXT NOT NULL CHECK (event IN ('check-started', 'check-finished')),
  occurred_at_ns INTEGER NOT NULL,
  exit_code INTEGER,
  CHECK (
    (event = 'check-started' AND exit_code IS NULL)
    OR (event = 'check-finished' AND exit_code IS NOT NULL)
  )
);

CREATE TABLE test_started (
  event_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(run_id),
  source_revision TEXT NOT NULL,
  suite TEXT NOT NULL,
  nodeid TEXT NOT NULL,
  worker_id TEXT NOT NULL,
  started_at_ns INTEGER NOT NULL
);

CREATE TABLE test_result (
  event_id INTEGER PRIMARY KEY,
  start_event_id INTEGER NOT NULL UNIQUE REFERENCES test_started(event_id),
  run_id TEXT NOT NULL REFERENCES run(run_id),
  source_revision TEXT NOT NULL,
  suite TEXT NOT NULL,
  nodeid TEXT NOT NULL,
  worker_id TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (
    outcome IN (
      'passed', 'failed', 'skipped', 'xfailed', 'xpassed', 'incomplete'
    )
  ),
  started_at_ns INTEGER NOT NULL,
  ended_at_ns INTEGER,
  duration_ns INTEGER CHECK (duration_ns IS NULL OR duration_ns >= 0),
  recovered_at_ns INTEGER,
  CHECK (
    (
      outcome != 'incomplete'
      AND ended_at_ns IS NOT NULL
      AND ended_at_ns >= started_at_ns
      AND duration_ns IS NOT NULL
      AND recovered_at_ns IS NULL
    )
    OR (
      outcome IN ('failed', 'incomplete')
      AND ended_at_ns IS NULL
      AND duration_ns IS NULL
      AND recovered_at_ns IS NOT NULL
      AND recovered_at_ns >= started_at_ns
    )
  )
);

CREATE TABLE resource_sample (
  event_id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES run(run_id),
  source_revision TEXT NOT NULL,
  sampled_at_ns INTEGER NOT NULL,
  interval_ns INTEGER NOT NULL CHECK (interval_ns > 0),
  cpu_cores REAL NOT NULL CHECK (cpu_cores >= 0),
  memory_rss_bytes INTEGER NOT NULL CHECK (memory_rss_bytes >= 0),
  read_bytes_per_second REAL CHECK (
    read_bytes_per_second IS NULL OR read_bytes_per_second >= 0
  ),
  write_bytes_per_second REAL CHECK (
    write_bytes_per_second IS NULL OR write_bytes_per_second >= 0
  )
);

CREATE INDEX test_result_revision_nodeid_index
  ON test_result(source_revision, nodeid, run_id);
CREATE INDEX test_started_run_index ON test_started(run_id, worker_id);
CREATE INDEX resource_sample_run_time_index
  ON resource_sample(run_id, sampled_at_ns);

CREATE TRIGGER run_event_identity_matches_run
BEFORE INSERT ON run_event
WHEN NOT EXISTS (
  SELECT 1 FROM run
  WHERE run_id = NEW.run_id
    AND source_revision = NEW.source_revision
)
BEGIN
  SELECT RAISE(ABORT, 'telemetry event identity does not match its run');
END;
CREATE TRIGGER test_result_identity_matches_run
BEFORE INSERT ON test_result
WHEN NOT EXISTS (
  SELECT 1 FROM run
  WHERE run_id = NEW.run_id
    AND source_revision = NEW.source_revision
)
BEGIN
  SELECT RAISE(ABORT, 'test identity does not match its run');
END;
CREATE TRIGGER test_started_identity_matches_run
BEFORE INSERT ON test_started
WHEN NOT EXISTS (
  SELECT 1 FROM run
  WHERE run_id = NEW.run_id
    AND source_revision = NEW.source_revision
)
BEGIN
  SELECT RAISE(ABORT, 'test start identity does not match its run');
END;
CREATE TRIGGER test_result_identity_matches_start
BEFORE INSERT ON test_result
WHEN NOT EXISTS (
  SELECT 1 FROM test_started
  WHERE event_id = NEW.start_event_id
    AND run_id = NEW.run_id
    AND source_revision = NEW.source_revision
    AND suite = NEW.suite
    AND nodeid = NEW.nodeid
    AND worker_id = NEW.worker_id
    AND started_at_ns = NEW.started_at_ns
)
BEGIN
  SELECT RAISE(ABORT, 'test result does not match its start event');
END;
CREATE TRIGGER resource_sample_identity_matches_run
BEFORE INSERT ON resource_sample
WHEN NOT EXISTS (
  SELECT 1 FROM run
  WHERE run_id = NEW.run_id
    AND source_revision = NEW.source_revision
)
BEGIN
  SELECT RAISE(ABORT, 'resource sample identity does not match its run');
END;

CREATE TRIGGER run_is_append_only_update
BEFORE UPDATE ON run
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER run_is_append_only_delete
BEFORE DELETE ON run
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER run_event_is_append_only_update
BEFORE UPDATE ON run_event
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER run_event_is_append_only_delete
BEFORE DELETE ON run_event
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER test_result_is_append_only_update
BEFORE UPDATE ON test_result
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER test_result_is_append_only_delete
BEFORE DELETE ON test_result
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER test_started_is_append_only_update
BEFORE UPDATE ON test_started
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER test_started_is_append_only_delete
BEFORE DELETE ON test_started
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER resource_sample_is_append_only_update
BEFORE UPDATE ON resource_sample
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
CREATE TRIGGER resource_sample_is_append_only_delete
BEFORE DELETE ON resource_sample
BEGIN
  SELECT RAISE(ABORT, 'telemetry history is append-only');
END;
"""


def validate_database_path(database: Path) -> Path:
  raw = os.fspath(database)
  name = database.name
  if (
    '\x00' in raw
    or not name
    or name in {'.', '..', ':memory:'}
    or raw.startswith('file:')
    or name.startswith('file:')
  ):
    raise ValueError(f'invalid telemetry database path: {database}')
  return database


def parse_database_path(raw: str) -> Path:
  if (
    not raw
    or '\x00' in raw
    or raw in {'.', '..'}
    or raw.endswith(('/', '/.', '/..'))
    or raw.startswith('file:')
  ):
    raise ValueError(f'invalid telemetry database path: {raw}')
  return validate_database_path(Path(raw))


def connect_database(database: Path) -> sqlite3.Connection:
  validate_database_path(database)
  connection = sqlite3.connect(database, timeout=30)
  try:
    connection.execute('PRAGMA foreign_keys = ON')
    connection.execute('PRAGMA busy_timeout = 30000')
  except Exception:
    try:
      connection.close()
    except sqlite3.Error:
      pass
    raise
  return connection


def initialize_schema(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  started_at_ns: int,
  python_version: str,
) -> None:
  connection.execute('PRAGMA foreign_keys = ON')
  connection.execute('PRAGMA user_version = 1')
  connection.executescript(SCHEMA_SQL)
  connection.execute(
    """
    INSERT INTO run
      (run_id, build_id, job_id, source_revision, python_version,
       started_at_ns)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
      run_id(identity),
      identity.build_id,
      identity.job_id,
      identity.source_revision,
      python_version,
      started_at_ns,
    ),
  )
  connection.commit()


def validate_database(connection: sqlite3.Connection) -> None:
  user_version = connection.execute('PRAGMA user_version').fetchone()
  if user_version != (1,):
    raise sqlite3.DatabaseError(
      f'telemetry schema version mismatch: {user_version}'
    )
  tables = {
    row[0]
    for row in connection.execute(
      "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
  }
  expected_tables = {
    'run',
    'run_event',
    'test_started',
    'test_result',
    'resource_sample',
  }
  if tables != expected_tables:
    raise sqlite3.DatabaseError(
      f'telemetry schema tables mismatch: {sorted(tables)}'
    )
  run_count = connection.execute('SELECT count(*) FROM run').fetchone()
  if run_count != (1,):
    raise sqlite3.DatabaseError(
      f'telemetry run row count mismatch: {run_count}'
    )
  integrity = connection.execute('PRAGMA integrity_check').fetchone()
  if integrity != ('ok',):
    raise sqlite3.DatabaseError(
      f'telemetry integrity check failed: {integrity}'
    )
  foreign_key_errors = connection.execute(
    'PRAGMA foreign_key_check'
  ).fetchall()
  if foreign_key_errors:
    raise sqlite3.DatabaseError(
      f'telemetry foreign-key check failed: {foreign_key_errors}'
    )


def initialize_database(
  database: Path,
  identity: RunIdentity,
  started_at_ns: int,
  python_version: str,
) -> None:
  validate_database_path(database)
  database.parent.mkdir(parents=True, exist_ok=True)
  if database.exists():
    raise FileExistsError(f'telemetry database already exists: {database}')

  with database.open('xb'):
    pass
  connection: sqlite3.Connection | None = None
  initialized = False
  try:
    connection = connect_database(database)
    connection.execute('PRAGMA journal_mode = WAL')
    initialize_schema(connection, identity, started_at_ns, python_version)
    to_close = connection
    connection = None
    to_close.close()
    initialized = True
  finally:
    if connection is not None:
      try:
        connection.close()
      except sqlite3.Error:
        pass
    if not initialized:
      for path in (
        database,
        database.with_name(f'{database.name}-wal'),
        database.with_name(f'{database.name}-shm'),
      ):
        try:
          path.unlink()
        except OSError:
          pass


def record_run_event(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  event: RunEvent,
) -> None:
  match event:
    case CheckStarted(occurred_at_ns):
      event_name = 'check-started'
      exit_code = None
    case CheckFinished(occurred_at_ns, exit_code):
      event_name = 'check-finished'
  connection.execute(
    """
    INSERT INTO run_event (run_id, source_revision, event, occurred_at_ns,
                           exit_code)
    VALUES (?, ?, ?, ?, ?)
    """,
    (
      run_id(identity),
      identity.source_revision,
      event_name,
      occurred_at_ns,
      exit_code,
    ),
  )
  connection.commit()


def _insert_test_result(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  start_event_id: int,
  test: TestCase,
  outcome: TestOutcome,
  started_at_ns: int,
  ended_at_ns: int | None,
  duration_ns: int | None,
  recovered_at_ns: int | None = None,
) -> None:
  connection.execute(
    """
    INSERT INTO test_result
      (start_event_id, run_id, source_revision, suite, nodeid, worker_id,
       outcome, started_at_ns, ended_at_ns, duration_ns, recovered_at_ns)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
      start_event_id,
      run_id(identity),
      identity.source_revision,
      test.suite,
      test.nodeid,
      test.worker_id,
      outcome,
      started_at_ns,
      ended_at_ns,
      duration_ns,
      recovered_at_ns,
    ),
  )


def record_test_result(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  result: CompletedTestResult,
) -> None:
  ended_at_ns = max(result.started_at_ns, result.ended_at_ns)
  duration_ns = max(0, result.duration_ns)
  _insert_test_result(
    connection,
    identity,
    result.start_event_id,
    result.test,
    result.outcome,
    result.started_at_ns,
    ended_at_ns,
    duration_ns,
  )
  connection.commit()


def record_test_start(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  test: TestCase,
  started_at_ns: int,
) -> int:
  cursor = connection.execute(
    """
    INSERT INTO test_started
      (run_id, source_revision, suite, nodeid, worker_id, started_at_ns)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
    (
      run_id(identity),
      identity.source_revision,
      test.suite,
      test.nodeid,
      test.worker_id,
      started_at_ns,
    ),
  )
  connection.commit()
  if cursor.lastrowid is None:
    raise sqlite3.DatabaseError('test start event has no row ID')
  return cursor.lastrowid


def record_incomplete_test_results(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  recovered_at_ns: int,
) -> None:
  starts = connection.execute(
    """
    SELECT start.event_id, start.suite, start.nodeid, start.worker_id,
           start.started_at_ns
    FROM test_started AS start
    WHERE start.run_id = ?
      AND start.source_revision = ?
      AND NOT EXISTS (
        SELECT 1 FROM test_result AS result
        WHERE result.start_event_id = start.event_id
      )
    ORDER BY start.event_id
    """,
    (run_id(identity), identity.source_revision),
  ).fetchall()
  for start_event_id, suite, nodeid, worker_id, started_at_ns in starts:
    _insert_test_result(
      connection,
      identity,
      start_event_id,
      TestCase(suite, nodeid, worker_id),
      'incomplete',
      started_at_ns,
      None,
      None,
      max(recovered_at_ns, started_at_ns),
    )
  if starts:
    connection.commit()


def record_test_failure_for_worker(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  test: TestCase,
  recovered_at_ns: int,
) -> bool:
  start = connection.execute(
    """
    SELECT event_id, started_at_ns
    FROM test_started
    WHERE run_id = ?
      AND source_revision = ?
      AND suite = ?
      AND nodeid = ?
      AND worker_id = ?
      AND NOT EXISTS (
        SELECT 1 FROM test_result
        WHERE start_event_id = test_started.event_id
      )
    ORDER BY event_id DESC
    LIMIT 1
    """,
    (
      run_id(identity),
      identity.source_revision,
      test.suite,
      test.nodeid,
      test.worker_id,
    ),
  ).fetchone()
  if start is None:
    return False
  start_event_id, started_at_ns = start
  _insert_test_result(
    connection,
    identity,
    start_event_id,
    test,
    'failed',
    started_at_ns,
    None,
    None,
    max(recovered_at_ns, started_at_ns),
  )
  connection.commit()
  return True


def record_resource_sample(
  connection: sqlite3.Connection,
  identity: RunIdentity,
  sample: ResourceSample,
) -> None:
  connection.execute(
    """
    INSERT INTO resource_sample
      (run_id, source_revision, sampled_at_ns, interval_ns, cpu_cores,
       memory_rss_bytes, read_bytes_per_second, write_bytes_per_second)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
      run_id(identity),
      identity.source_revision,
      sample.sampled_at_ns,
      sample.interval_ns,
      sample.cpu_cores,
      sample.memory_rss_bytes,
      sample.read_bytes_per_second,
      sample.write_bytes_per_second,
    ),
  )
  connection.commit()


def finalize_database(database: Path) -> None:
  validate_database_path(database)
  if not database.is_file():
    raise FileNotFoundError(
      f'telemetry database does not exist: {database}'
    )
  connection = connect_database(database)
  try:
    validate_database(connection)
    checkpoint = connection.execute(
      'PRAGMA wal_checkpoint(TRUNCATE)'
    ).fetchone()
    if checkpoint is None or checkpoint[0] != 0:
      raise sqlite3.DatabaseError(
        f'telemetry WAL checkpoint blocked: {checkpoint}'
      )
    journal_mode = connection.execute(
      'PRAGMA journal_mode = DELETE'
    ).fetchone()
    if journal_mode != ('delete',):
      raise sqlite3.DatabaseError(
        f'telemetry journal mode switch failed: {journal_mode}'
      )
  except Exception:
    try:
      connection.close()
    except sqlite3.Error:
      pass
    raise
  connection.close()


def parse_process_stat(
  pid: int, contents: str, page_size: int
) -> ProcessInfo | None:
  if pid < 0:
    return None
  prefix = f'{pid} ('
  if not contents.startswith(prefix):
    return None
  command_end = contents.rfind(')')
  if command_end < len(prefix):
    return None
  if contents[command_end + 1 : command_end + 2] != ' ':
    return None

  fields = contents[command_end + 2 :].split()
  if len(fields) < 22 or len(fields[0]) != 1:
    return None

  try:
    session_id = int(fields[3])
    user_ticks = int(fields[11])
    system_ticks = int(fields[12])
    start_time_ticks = int(fields[19])
    rss_pages = int(fields[21])
  except ValueError:
    return None

  return ProcessInfo(
    state=fields[0],
    session_id=session_id,
    start_time_ticks=start_time_ticks,
    counters=ProcessCounters(cpu_ticks=user_ticks + system_ticks),
    memory_rss_bytes=max(0, rss_pages) * page_size,
  )


def parse_process_io(contents: str) -> ProcessCounters | None:
  values: dict[str, int] = {}
  for line in contents.splitlines():
    key, separator, value = line.partition(':')
    if not separator or not key or key != key.strip() or key in values:
      return None
    try:
      values[key] = int(value.strip())
    except ValueError:
      return None
  read_bytes = values.get('read_bytes')
  write_bytes = values.get('write_bytes')
  if (
    read_bytes is None
    or write_bytes is None
    or read_bytes < 0
    or write_bytes < 0
  ):
    return None
  return ProcessCounters(read_bytes=read_bytes, write_bytes=write_bytes)


def read_session_processes(
  proc: Path | ProcFs, session_id: int, page_size: int
) -> tuple[dict[tuple[int, int], tuple[ProcessCounters, int]], bool]:
  reader = proc_fs(proc) if isinstance(proc, Path) else proc
  processes: dict[tuple[int, int], tuple[ProcessCounters, int]] = {}
  io_counters_available = True
  for entry_name in reader.list_entries():
    if not (entry_name.isascii() and entry_name.isdigit()):
      continue
    pid = int(entry_name)
    try:
      process = parse_process_stat(
        pid, reader.read_text(pid, 'stat'), page_size
      )
    except (FileNotFoundError, ProcessLookupError):
      continue
    if (
      process is None
      or process.session_id != session_id
      or process.state in _EXITED_PROCESS_STATES
    ):
      continue
    try:
      io = parse_process_io(reader.read_text(pid, 'io'))
    except (OSError, UnicodeError):
      io = None
    if io is None:
      try:
        rechecked = parse_process_stat(
          pid, reader.read_text(pid, 'stat'), page_size
        )
      except (FileNotFoundError, ProcessLookupError):
        continue
      if (
        rechecked is None
        or rechecked.state in _EXITED_PROCESS_STATES
        or (rechecked.session_id, rechecked.start_time_ticks)
        != (process.session_id, process.start_time_ticks)
      ):
        continue
      io_counters_available = False
      io = ProcessCounters()
    processes[(pid, process.start_time_ticks)] = (
      ProcessCounters(
        cpu_ticks=process.counters.cpu_ticks,
        read_bytes=io.read_bytes,
        write_bytes=io.write_bytes,
      ),
      process.memory_rss_bytes,
    )
  return processes, io_counters_available


def add_counters(
  left: ProcessCounters, right: ProcessCounters
) -> ProcessCounters:
  return ProcessCounters(
    cpu_ticks=left.cpu_ticks + right.cpu_ticks,
    read_bytes=left.read_bytes + right.read_bytes,
    write_bytes=left.write_bytes + right.write_bytes,
  )


def max_counters(
  left: ProcessCounters, right: ProcessCounters
) -> ProcessCounters:
  return ProcessCounters(
    cpu_ticks=max(left.cpu_ticks, right.cpu_ticks),
    read_bytes=max(left.read_bytes, right.read_bytes),
    write_bytes=max(left.write_bytes, right.write_bytes),
  )


def observe_process_session(
  proc: Path | ProcFs,
  session_id: int,
  page_size: int,
  state: ProcessCounterState,
  wall_time_ns: int,
  monotonic_ns: int,
) -> tuple[ProcessCounterState, ProcessObservation]:
  current, current_io_available = read_session_processes(
    proc, session_id, page_size
  )
  retired = state.retired
  for key in state.active.keys() - current.keys():
    retired = add_counters(retired, state.active[key])

  active: dict[tuple[int, int], ProcessCounters] = {}
  total = retired
  memory_rss_bytes = 0
  for key, (counters, rss_bytes) in current.items():
    high_water = max_counters(
      state.active.get(key, ProcessCounters()), counters
    )
    active[key] = high_water
    total = add_counters(total, high_water)
    memory_rss_bytes += rss_bytes

  io_counters_available = (
    state.io_counters_available and current_io_available
  )
  next_state = ProcessCounterState(
    active=active,
    retired=retired,
    io_counters_available=io_counters_available,
  )
  observation = ProcessObservation(
    wall_time_ns=wall_time_ns,
    monotonic_ns=monotonic_ns,
    counters=total,
    memory_rss_bytes=memory_rss_bytes,
    io_counters_available=io_counters_available,
  )
  return next_state, observation


def resource_sample_between(
  previous: ProcessObservation,
  current: ProcessObservation,
  clock_ticks_per_second: int,
) -> ResourceSample | None:
  interval_ns = current.monotonic_ns - previous.monotonic_ns
  if interval_ns <= 0:
    return None
  seconds = interval_ns / 1_000_000_000
  io_counters_available = (
    previous.io_counters_available and current.io_counters_available
  )
  return ResourceSample(
    sampled_at_ns=current.wall_time_ns,
    interval_ns=interval_ns,
    cpu_cores=max(
      0.0,
      (current.counters.cpu_ticks - previous.counters.cpu_ticks)
      / clock_ticks_per_second
      / seconds,
    ),
    memory_rss_bytes=current.memory_rss_bytes,
    read_bytes_per_second=(
      max(
        0.0,
        (current.counters.read_bytes - previous.counters.read_bytes)
        / seconds,
      )
      if io_counters_available
      else None
    ),
    write_bytes_per_second=(
      max(
        0.0,
        (current.counters.write_bytes - previous.counters.write_bytes)
        / seconds,
      )
      if io_counters_available
      else None
    ),
  )
