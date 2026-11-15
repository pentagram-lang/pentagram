import errno
import io
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest

from zero import telemetry
from zero.telemetry import (
  CheckFinished,
  CheckStarted,
  CompletedTestResult,
  ProcessCounters,
  ProcessCounterState,
  ProcessInfo,
  ProcessObservation,
  ProcFs,
  ResourceSample,
  RunIdentity,
  TestCase,
  add_counters,
  connect_database,
  finalize_database,
  initialize_database,
  initialize_schema,
  max_counters,
  observe_process_session,
  parse_database_path,
  parse_process_io,
  parse_process_stat,
  proc_fs,
  read_session_processes,
  record_incomplete_test_results,
  record_resource_sample,
  record_run_event,
  record_test_failure_for_worker,
  record_test_result,
  record_test_start,
  resource_sample_between,
  run_id,
  validate_database,
  validate_database_path,
)


def stat_line(
  pid: int,
  *,
  command: str = 'pytest worker (gw0)',
  state: str = 'S',
  session_id: int = 42,
  user_ticks: int = 0,
  system_ticks: int = 0,
  start_time_ticks: int = 1,
  rss_pages: int = 0,
) -> str:
  fields = [state] + ['0'] * 21
  fields[3] = str(session_id)
  fields[11] = str(user_ticks)
  fields[12] = str(system_ticks)
  fields[19] = str(start_time_ticks)
  fields[21] = str(rss_pages)
  return f'{pid} ({command}) {" ".join(fields)}'


def scripted_procfs(
  entries: dict[int, list[str | Exception]],
  ios: dict[int, list[str | Exception]],
  extra_names: tuple[str, ...] = (),
) -> ProcFs:
  stat_indices: dict[int, int] = {}
  io_indices: dict[int, int] = {}

  def next_item(
    source: dict[int, list[str | Exception]],
    indices: dict[int, int],
    pid: int,
  ) -> str:
    sequence = source.get(pid)
    if not sequence:
      raise FileNotFoundError(pid)
    index = indices.get(pid, 0)
    indices[pid] = index + 1
    item = sequence[index] if index < len(sequence) else sequence[-1]
    if isinstance(item, Exception):
      raise item
    return item

  def read_text(pid: int, name: Literal['stat', 'io']) -> str:
    if name == 'stat':
      return next_item(entries, stat_indices, pid)
    return next_item(ios, io_indices, pid)

  return ProcFs(
    list_entries=lambda: (
      *extra_names,
      *(str(pid) for pid in entries),
    ),
    read_text=read_text,
  )


def _memory_connection() -> sqlite3.Connection:
  connection = sqlite3.connect(':memory:')
  connection.execute('PRAGMA foreign_keys = ON')
  return connection


def initialized_memory_db() -> tuple[sqlite3.Connection, RunIdentity]:
  identity = RunIdentity('build-1', 'job-2', 'rev-3')
  connection = _memory_connection()
  initialize_schema(connection, identity, 10, '3.13.9')
  return connection, identity


def test_run_id_combines_build_and_job_ids() -> None:
  identity = RunIdentity('build-42', 'job-9', 'abc123')
  assert run_id(identity) == 'build-42:job-9'


@pytest.mark.parametrize(
  ('pid', 'line', 'page_size', 'expected'),
  [
    (
      99,
      stat_line(
        99,
        command='pytest (worker 1)',
        state='R',
        session_id=7,
        user_ticks=30,
        system_ticks=4,
        start_time_ticks=12,
        rss_pages=5,
      ),
      4096,
      ProcessInfo(
        state='R',
        session_id=7,
        start_time_ticks=12,
        counters=ProcessCounters(cpu_ticks=34),
        memory_rss_bytes=20480,
      ),
    ),
    (
      100,
      stat_line(
        100,
        state='Z',
        session_id=7,
        user_ticks=1,
        system_ticks=2,
        start_time_ticks=88,
        rss_pages=-3,
      ),
      4096,
      ProcessInfo(
        state='Z',
        session_id=7,
        start_time_ticks=88,
        counters=ProcessCounters(cpu_ticks=3),
        memory_rss_bytes=0,
      ),
    ),
  ],
  ids=('running-with-parens', 'zombie-clamps-negative-rss'),
)
def test_parse_process_stat_parses_valid_lines_and_clamps_negative_rss(
  pid: int, line: str, page_size: int, expected: ProcessInfo
) -> None:
  assert parse_process_stat(pid, line, page_size) == expected


@pytest.mark.parametrize(
  ('pid', 'line'),
  [
    (-1, '-1 (cmd) S ' + ' '.join(['0'] * 21)),
    (99, stat_line(100)),
    (99, '99 missing-parens S 1 2'),
    (99, '99 (cmd)S ' + ' '.join(['0'] * 21)),
    (99, 'abc (cmd) S ' + ' '.join(['0'] * 21)),
    (99, '99 (cmd) SS ' + ' '.join(['0'] * 21)),
    (99, '99 (cmd) S ' + ' '.join(['0'] * 20)),
    (99, '99 (cmd) S 0 0 bad ' + ' '.join(['0'] * 18)),
  ],
  ids=(
    'negative-pid',
    'pid-mismatch',
    'missing-closing-paren',
    'missing-space-after-paren',
    'non-int-pid',
    'multi-char-state',
    'too-few-fields',
    'non-int-counter',
  ),
)
def test_parse_process_stat_rejects_malformed_lines(
  pid: int, line: str
) -> None:
  assert parse_process_stat(pid, line, 4096) is None


@pytest.mark.parametrize(
  ('contents', 'expected'),
  [
    (
      'rchar: 999\nread_bytes: 12\nsyscr: 5\nwrite_bytes: 34\n',
      ProcessCounters(read_bytes=12, write_bytes=34),
    ),
    ('read_bytes: 12\n', None),
    ('read_bytes: -1\nwrite_bytes: 2\n', None),
    ('read_bytes: 1\nwrite_bytes: -2\n', None),
    ('read_bytes: invalid\nwrite_bytes: 2\n', None),
    ('garbage\nread_bytes: 12\nwrite_bytes: 34\n', None),
    ('rchar: bad\nread_bytes: 12\nwrite_bytes: 34\n', None),
    ('read_bytes : 12\nwrite_bytes: 34\n', None),
    (': 12\nread_bytes: 12\nwrite_bytes: 34\n', None),
    ('read_bytes: 12\nread_bytes: 12\nwrite_bytes: 34\n', None),
  ],
  ids=(
    'valid',
    'missing-write',
    'negative-read',
    'negative-write',
    'non-int-line',
    'malformed-non-target',
    'non-int-non-target',
    'whitespace-key',
    'empty-key',
    'duplicate-key',
  ),
)
def test_process_io_requires_both_valid_counters(
  contents: str, expected: ProcessCounters | None
) -> None:
  assert parse_process_io(contents) == expected


def test_counter_aggregation_helpers() -> None:
  left = ProcessCounters(cpu_ticks=10, read_bytes=300, write_bytes=50)
  right = ProcessCounters(cpu_ticks=15, read_bytes=100, write_bytes=90)

  assert add_counters(left, right) == ProcessCounters(
    cpu_ticks=25, read_bytes=400, write_bytes=140
  )
  assert max_counters(left, right) == ProcessCounters(
    cpu_ticks=15, read_bytes=300, write_bytes=90
  )


@pytest.mark.parametrize(
  ('previous', 'current', 'expected'),
  [
    (
      ProcessObservation(
        1_000, 1, ProcessCounters(10, 100, 200), 4096, True
      ),
      ProcessObservation(
        2_000, 2_000_000_001, ProcessCounters(40, 650, 1100), 8192, True
      ),
      ResourceSample(2_000, 2_000_000_000, 0.15, 8192, 275.0, 450.0),
    ),
    (
      ProcessObservation(
        1_000, 1, ProcessCounters(10, 100, 200), 4096, False
      ),
      ProcessObservation(
        2_000, 2_000_000_001, ProcessCounters(35, 650, 1100), 8192, True
      ),
      ResourceSample(2_000, 2_000_000_000, 0.125, 8192, None, None),
    ),
    (
      ProcessObservation(
        1_000, 1, ProcessCounters(50, 500, 500), 4096, True
      ),
      ProcessObservation(
        2_000, 2_000_000_001, ProcessCounters(20, 100, 100), 2048, True
      ),
      ResourceSample(2_000, 2_000_000_000, 0.0, 2048, 0.0, 0.0),
    ),
    (
      ProcessObservation(
        1_000, 500, ProcessCounters(10, 100, 200), 4096, True
      ),
      ProcessObservation(
        2_000, 500, ProcessCounters(20, 200, 300), 4096, True
      ),
      None,
    ),
    (
      ProcessObservation(
        1_000, 500, ProcessCounters(10, 100, 200), 4096, True
      ),
      ProcessObservation(
        2_000, 400, ProcessCounters(20, 200, 300), 4096, True
      ),
      None,
    ),
  ],
  ids=(
    'with-io',
    'io-unavailable',
    'regression-clamped',
    'zero-interval',
    'negative-interval',
  ),
)
def test_resource_sample_between(
  previous: ProcessObservation,
  current: ProcessObservation,
  expected: ResourceSample | None,
) -> None:
  assert resource_sample_between(previous, current, 100) == expected


def test_observe_process_session_tracks_retires_and_clamps_counters() -> (
  None
):
  first_proc = scripted_procfs(
    {
      123: [
        stat_line(
          123,
          session_id=42,
          user_ticks=10,
          system_ticks=5,
          start_time_ticks=1,
          rss_pages=4,
        )
      ],
      124: [
        stat_line(
          124,
          session_id=7,
          user_ticks=100,
          system_ticks=50,
          start_time_ticks=1,
          rss_pages=40,
        )
      ],
    },
    {
      123: ['read_bytes: 100\nwrite_bytes: 200\n'],
      124: ['read_bytes: 1000\nwrite_bytes: 2000\n'],
    },
    extra_names=('self', 'meminfo', '١٢', '²'),
  )
  state, first = observe_process_session(
    first_proc,
    42,
    4096,
    ProcessCounterState({}, ProcessCounters()),
    1_000,
    1,
  )

  assert (state, first) == (
    ProcessCounterState(
      active={(123, 1): ProcessCounters(15, 100, 200)},
      retired=ProcessCounters(),
      io_counters_available=True,
    ),
    ProcessObservation(
      1_000, 1, ProcessCounters(15, 100, 200), 4 * 4096, True
    ),
  )

  second_proc = scripted_procfs(
    {
      123: [
        stat_line(
          123,
          session_id=42,
          user_ticks=12,
          system_ticks=2,
          start_time_ticks=1,
          rss_pages=5,
        )
      ],
      125: [
        stat_line(
          125,
          session_id=42,
          user_ticks=4,
          system_ticks=1,
          start_time_ticks=2,
          rss_pages=2,
        )
      ],
    },
    {
      123: ['read_bytes: 600\nwrite_bytes: 100\n'],
      125: ['read_bytes: 50\nwrite_bytes: 100\n'],
    },
  )
  state, second = observe_process_session(
    second_proc, 42, 4096, state, 2_000, 2_000_000_001
  )

  assert (state, second) == (
    ProcessCounterState(
      active={
        (123, 1): ProcessCounters(15, 600, 200),
        (125, 2): ProcessCounters(5, 50, 100),
      },
      retired=ProcessCounters(),
      io_counters_available=True,
    ),
    ProcessObservation(
      2_000, 2_000_000_001, ProcessCounters(20, 650, 300), 7 * 4096, True
    ),
  )

  third_proc = scripted_procfs(
    {
      125: [
        stat_line(
          125,
          session_id=42,
          user_ticks=20,
          system_ticks=0,
          start_time_ticks=2,
          rss_pages=2,
        )
      ]
    },
    {125: ['read_bytes: 150\nwrite_bytes: 300\n']},
  )
  state, third = observe_process_session(
    third_proc, 42, 4096, state, 3_000, 4_000_000_001
  )

  assert (state, third) == (
    ProcessCounterState(
      active={(125, 2): ProcessCounters(20, 150, 300)},
      retired=ProcessCounters(15, 600, 200),
      io_counters_available=True,
    ),
    ProcessObservation(
      3_000, 4_000_000_001, ProcessCounters(35, 750, 500), 2 * 4096, True
    ),
  )


@pytest.mark.parametrize(
  ('stat_sequence', 'io_sequence'),
  [
    (
      [stat_line(123, state='Z', user_ticks=10)],
      [FileNotFoundError('no io for zombie')],
    ),
    (
      [stat_line(123, state='X', user_ticks=10)],
      [FileNotFoundError('no io for dead')],
    ),
    (
      [stat_line(123, state='x', user_ticks=10)],
      [FileNotFoundError('no io for exiting')],
    ),
    (
      [stat_line(123, state='R', user_ticks=10), FileNotFoundError(123)],
      [FileNotFoundError(123)],
    ),
    (
      [
        stat_line(123, state='R', user_ticks=10),
        stat_line(123, state='Z', user_ticks=10),
      ],
      [FileNotFoundError(123)],
    ),
    (
      [
        stat_line(123, state='R', session_id=42, start_time_ticks=1),
        stat_line(123, state='R', session_id=42, start_time_ticks=99),
      ],
      [FileNotFoundError(123)],
    ),
    (
      [
        stat_line(123, state='R', session_id=42, start_time_ticks=1),
        stat_line(123, state='R', session_id=77, start_time_ticks=1),
      ],
      [FileNotFoundError(123)],
    ),
  ],
  ids=(
    'initial-zombie-Z',
    'initial-dead-X',
    'initial-dead-x',
    'mid-sample-disappeared',
    'mid-sample-became-zombie',
    'mid-sample-pid-recycled-start',
    'mid-sample-pid-recycled-session',
  ),
)
def test_read_session_processes_ignores_exited_and_recycled_processes(
  stat_sequence: list[str | Exception],
  io_sequence: list[str | Exception],
) -> None:
  proc = scripted_procfs({123: stat_sequence}, {123: io_sequence})
  prior = ProcessCounterState(
    active={(123, 1): ProcessCounters(10, 50, 60)},
    retired=ProcessCounters(),
    io_counters_available=True,
  )

  processes, io_available = read_session_processes(proc, 42, 4096)
  assert (processes, io_available) == ({}, True)

  next_state, observation = observe_process_session(
    scripted_procfs({123: list(stat_sequence)}, {123: list(io_sequence)}),
    42,
    4096,
    prior,
    2_000,
    2,
  )
  assert (next_state, observation) == (
    ProcessCounterState(
      active={},
      retired=ProcessCounters(10, 50, 60),
      io_counters_available=True,
    ),
    ProcessObservation(2_000, 2, ProcessCounters(10, 50, 60), 0, True),
  )


@pytest.mark.parametrize(
  ('stat_sequence', 'io_sequence', 'expected_error'),
  [
    (
      [PermissionError(13, 'Permission denied')],
      [],
      PermissionError,
    ),
    (
      [OSError(errno.EMFILE, 'Too many open files')],
      [],
      OSError,
    ),
    (
      [
        stat_line(123, state='R', session_id=42, start_time_ticks=1),
        OSError(errno.EMFILE, 'Too many open files'),
      ],
      [FileNotFoundError(123)],
      OSError,
    ),
    (
      [RuntimeError('unexpected stat failure')],
      [],
      RuntimeError,
    ),
  ],
  ids=(
    'initial-permission-denied',
    'initial-emfile',
    'mid-sample-emfile',
    'initial-runtime-error',
  ),
)
def test_read_session_processes_propagates_operational_stat_errors(
  stat_sequence: list[str | Exception],
  io_sequence: list[str | Exception],
  expected_error: type[Exception],
) -> None:
  proc = scripted_procfs({123: stat_sequence}, {123: io_sequence})
  prior = ProcessCounterState(
    active={(123, 1): ProcessCounters(10, 50, 60)},
    retired=ProcessCounters(),
    io_counters_available=True,
  )

  with pytest.raises(expected_error):
    read_session_processes(proc, 42, 4096)

  with pytest.raises(expected_error):
    observe_process_session(
      scripted_procfs(
        {123: list(stat_sequence)}, {123: list(io_sequence)}
      ),
      42,
      4096,
      prior,
      2_000,
      2,
    )
  assert prior == ProcessCounterState(
    active={(123, 1): ProcessCounters(10, 50, 60)},
    retired=ProcessCounters(),
    io_counters_available=True,
  )


@pytest.mark.parametrize(
  'io_failure',
  [
    FileNotFoundError(2, 'No such file or directory'),
    PermissionError(13, 'Permission denied'),
    UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte'),
    'read_bytes: 1\n',
  ],
  ids=('missing-io', 'permission-denied', 'invalid-utf8', 'malformed-io'),
)
def test_observe_process_session_latches_io_unavailable_for_live_process(
  io_failure: str | Exception,
) -> None:
  first_proc = scripted_procfs(
    {
      123: [
        stat_line(
          123,
          state='R',
          session_id=42,
          user_ticks=10,
          system_ticks=5,
          start_time_ticks=1,
          rss_pages=4,
        ),
        stat_line(
          123,
          state='S',
          session_id=42,
          user_ticks=10,
          system_ticks=5,
          start_time_ticks=1,
          rss_pages=4,
        ),
      ]
    },
    {123: [io_failure]},
  )
  state, first = observe_process_session(
    first_proc,
    42,
    4096,
    ProcessCounterState({}, ProcessCounters()),
    1_000,
    1,
  )

  assert (state, first) == (
    ProcessCounterState(
      active={(123, 1): ProcessCounters(15, 0, 0)},
      retired=ProcessCounters(),
      io_counters_available=False,
    ),
    ProcessObservation(
      1_000, 1, ProcessCounters(15, 0, 0), 4 * 4096, False
    ),
  )

  second_proc = scripted_procfs(
    {
      123: [
        stat_line(
          123,
          state='R',
          session_id=42,
          user_ticks=30,
          system_ticks=10,
          start_time_ticks=1,
          rss_pages=5,
        )
      ]
    },
    {123: ['read_bytes: 600\nwrite_bytes: 1000\n']},
  )
  state, second = observe_process_session(
    second_proc, 42, 4096, state, 2_000, 2_000_000_001
  )

  assert (state, second) == (
    ProcessCounterState(
      active={(123, 1): ProcessCounters(40, 600, 1000)},
      retired=ProcessCounters(),
      io_counters_available=False,
    ),
    ProcessObservation(
      2_000,
      2_000_000_001,
      ProcessCounters(40, 600, 1000),
      5 * 4096,
      False,
    ),
  )
  assert resource_sample_between(first, second, 100) == ResourceSample(
    2_000, 2_000_000_000, 0.125, 5 * 4096, None, None
  )


def test_proc_fs_decodes_stat_lossily_and_io_strictly(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  proc_root = Path('/virtual/proc')
  stat_bytes = (
    b'123 (w\xffrker) R '
    + b'0 ' * 2
    + b'42 '
    + b'0 ' * 7
    + b'10 5 '
    + b'0 ' * 6
    + b'1 0 4\n'
  )
  files: dict[Path, list[bytes]] = {
    proc_root / '123' / 'stat': [stat_bytes, stat_bytes, stat_bytes],
    proc_root / '123' / 'io': [
      b'read_bytes: 100\nwrite_bytes: 200\n',
      b'read_bytes: \xff\nwrite_bytes: 200\n',
    ],
  }

  def fake_iterdir(self: Path) -> Iterator[Path]:
    assert self == proc_root
    return iter((proc_root / '123', proc_root / 'self'))

  def fake_read_bytes(self: Path) -> bytes:
    return files[self].pop(0)

  monkeypatch.setattr(Path, 'iterdir', fake_iterdir)
  monkeypatch.setattr(Path, 'read_bytes', fake_read_bytes)

  reader = proc_fs(proc_root)
  assert tuple(reader.list_entries()) == ('123', 'self')
  first_procs, first_io = read_session_processes(proc_root, 42, 4096)
  assert (first_procs, first_io) == (
    {(123, 1): (ProcessCounters(15, 100, 200), 4 * 4096)},
    True,
  )
  second_procs, second_io = read_session_processes(proc_root, 42, 4096)
  assert (second_procs, second_io) == (
    {(123, 1): (ProcessCounters(15, 0, 0), 4 * 4096)},
    False,
  )


_REAL_SQLITE_CONNECT = sqlite3.connect


@dataclass
class _VirtualDbState:
  exists: bool = False
  unlinked: list[Path] = field(default_factory=list)
  mkdirs: list[Path] = field(default_factory=list)
  blocked_checkpoint: bool = False
  journal_mode_override: str | None = None
  close_error: sqlite3.Error | None = None
  pragmas: list[str] = field(default_factory=list)


@contextmanager
def _virtual_sqlite_env(
  monkeypatch: pytest.MonkeyPatch, name: str, db_path: Path
) -> Iterator[tuple[sqlite3.Connection, _VirtualDbState]]:
  uri = f'file:/{name}?vfs=memdb'
  keeper = _REAL_SQLITE_CONNECT(uri, uri=True)
  state = _VirtualDbState()

  def fake_mkdir(
    self: Path,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
  ) -> None:
    del mode, parents, exist_ok
    state.mkdirs.append(self)

  def fake_exists(self: Path) -> bool:
    return self == db_path and state.exists

  def fake_is_file(self: Path) -> bool:
    return self == db_path and state.exists

  def fake_open(self: Path, mode: str = 'r') -> io.BytesIO:
    assert self == db_path
    assert mode == 'xb'
    if state.exists:
      raise FileExistsError(self)
    state.exists = True
    return io.BytesIO()

  def fake_unlink(self: Path) -> None:
    state.unlinked.append(self)
    if self != db_path:
      raise FileNotFoundError(self)
    state.exists = False

  def fake_connect(
    target: object, timeout: float = 5.0
  ) -> sqlite3.Connection:
    assert target == db_path
    conn = _REAL_SQLITE_CONNECT(uri, timeout=timeout, uri=True)

    def fake_execute(
      sql: str, params: tuple[object, ...] = ()
    ) -> sqlite3.Cursor:
      if sql.startswith(('PRAGMA journal_mode', 'PRAGMA wal_checkpoint')):
        state.pragmas.append(sql)
      if (
        state.blocked_checkpoint
        and sql == 'PRAGMA wal_checkpoint(TRUNCATE)'
      ):
        return conn.execute('SELECT 1, 1, 1')
      if (
        state.journal_mode_override is not None
        and sql == 'PRAGMA journal_mode = DELETE'
      ):
        return conn.execute('SELECT ?', (state.journal_mode_override,))
      return conn.execute(sql, params)

    def fake_close() -> None:
      conn.close()
      if state.close_error is not None:
        raise state.close_error

    return cast(
      sqlite3.Connection,
      SimpleNamespace(
        execute=fake_execute,
        executescript=conn.executescript,
        commit=conn.commit,
        rollback=conn.rollback,
        close=fake_close,
      ),
    )

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'mkdir', fake_mkdir)
    mp.setattr(Path, 'exists', fake_exists)
    mp.setattr(Path, 'is_file', fake_is_file)
    mp.setattr(Path, 'open', fake_open)
    mp.setattr(Path, 'unlink', fake_unlink)
    mp.setattr(telemetry.sqlite3, 'connect', fake_connect)
    try:
      yield keeper, state
    finally:
      keeper.close()


@pytest.mark.parametrize(
  ('raw', 'expected_name'),
  [
    ('', ''),
    ('.', '.'),
    ('.//', './/'),
    ('/', '/'),
    ('..', '..'),
    ('dir/.', 'dir/.'),
    ('dir/..', 'dir/..'),
    (':memory:', ':memory:'),
    ('./:memory:', ':memory:'),
    ('file:mem', 'file:mem'),
    ('./file:mem', 'file:mem'),
    ('dir/', 'dir/'),
    ('out/run.sqlite3\x00', 'out/run.sqlite3\x00'),
  ],
)
def test_parse_database_path_rejects_invalid_targets(
  raw: str, expected_name: str
) -> None:
  with pytest.raises(ValueError) as parse_exc:
    parse_database_path(raw)
  assert (
    str(parse_exc.value)
    == f'invalid telemetry database path: {expected_name}'
  )


@pytest.mark.parametrize(
  'bad_path',
  [
    Path(''),
    Path('/'),
    Path('..'),
    Path('.'),
    Path('dir/..'),
    Path(':memory:'),
    Path('file:x'),
    Path('file:/bad?vfs=memdb'),
    Path('a\x00b'),
  ],
  ids=str,
)
def test_validate_database_path_rejects_invalid_paths(
  bad_path: Path,
) -> None:
  identity = RunIdentity('build-1', 'job-2', 'rev-3')
  expected = f'invalid telemetry database path: {bad_path}'
  with pytest.raises(ValueError) as validate_exc:
    validate_database_path(bad_path)
  assert str(validate_exc.value) == expected
  with pytest.raises(ValueError) as connect_exc:
    connect_database(bad_path)
  assert str(connect_exc.value) == expected
  with pytest.raises(ValueError) as init_exc:
    initialize_database(bad_path, identity, 10, '3.13.9')
  assert str(init_exc.value) == expected
  with pytest.raises(ValueError) as finalize_exc:
    finalize_database(bad_path)
  assert str(finalize_exc.value) == expected


def test_parse_and_validate_database_path_accepts_relative_path() -> None:
  assert parse_database_path('out/run.sqlite3') == Path('out/run.sqlite3')
  assert validate_database_path(Path('out/run.sqlite3')) == Path(
    'out/run.sqlite3'
  )


def test_path_database_lifecycle_and_recording(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  db_path = Path('/virtual/dir/run.sqlite3')
  identity = RunIdentity('build-1', 'job-2', 'rev-3')

  with _virtual_sqlite_env(
    monkeypatch, 'telemetry_test_lifecycle', db_path
  ) as (keeper, vstate):
    with pytest.raises(FileNotFoundError) as missing_exc:
      finalize_database(db_path)
    assert str(missing_exc.value) == (
      f'telemetry database does not exist: {db_path}'
    )

    initialize_database(db_path, identity, 10, '3.13.9')
    assert (vstate.mkdirs, vstate.exists, vstate.pragmas) == (
      [Path('/virtual/dir')],
      True,
      ['PRAGMA journal_mode = WAL'],
    )
    with pytest.raises(FileExistsError) as exists_exc:
      initialize_database(db_path, identity, 10, '3.13.9')
    assert str(exists_exc.value) == (
      f'telemetry database already exists: {db_path}'
    )

    connection = connect_database(db_path)
    try:
      assert connection.execute('PRAGMA user_version').fetchone() == (1,)
      assert connection.execute('PRAGMA foreign_keys').fetchone() == (1,)
      record_run_event(connection, identity, CheckStarted(10))
      test_a = TestCase('zero', 'telemetry_test.py::test_a', 'gw0')
      start_id = record_test_start(connection, identity, test_a, 20)
      record_test_result(
        connection,
        identity,
        CompletedTestResult(start_id, test_a, 'passed', 20, 30, 9),
      )
      record_resource_sample(
        connection,
        identity,
        ResourceSample(40, 10, 1.5, 4096, 100.0, 200.0),
      )
      record_run_event(connection, identity, CheckFinished(50, 0))

      assert connection.execute('SELECT * FROM run').fetchall() == [
        ('build-1:job-2', 'build-1', 'job-2', 'rev-3', '3.13.9', 10)
      ]
      assert connection.execute(
        'SELECT * FROM run_event ORDER BY event_id'
      ).fetchall() == [
        (1, 'build-1:job-2', 'rev-3', 'check-started', 10, None),
        (2, 'build-1:job-2', 'rev-3', 'check-finished', 50, 0),
      ]
      assert connection.execute(
        'SELECT * FROM test_started ORDER BY event_id'
      ).fetchall() == [
        (
          start_id,
          'build-1:job-2',
          'rev-3',
          'zero',
          'telemetry_test.py::test_a',
          'gw0',
          20,
        )
      ]
      assert connection.execute(
        'SELECT * FROM test_result ORDER BY event_id'
      ).fetchall() == [
        (
          1,
          start_id,
          'build-1:job-2',
          'rev-3',
          'zero',
          'telemetry_test.py::test_a',
          'gw0',
          'passed',
          20,
          30,
          9,
          None,
        )
      ]
      assert connection.execute(
        'SELECT * FROM resource_sample ORDER BY event_id'
      ).fetchall() == [
        (1, 'build-1:job-2', 'rev-3', 40, 10, 1.5, 4096, 100.0, 200.0)
      ]
      validate_database(connection)
    finally:
      connection.close()

    vstate.blocked_checkpoint = True
    with pytest.raises(sqlite3.DatabaseError) as blocked_exc:
      finalize_database(db_path)
    assert str(blocked_exc.value) == (
      'telemetry WAL checkpoint blocked: (1, 1, 1)'
    )

    vstate.blocked_checkpoint = False
    vstate.journal_mode_override = 'wal'
    with pytest.raises(sqlite3.DatabaseError) as journal_exc:
      finalize_database(db_path)
    assert (
      str(journal_exc.value)
      == "telemetry journal mode switch failed: ('wal',)"
    )

    vstate.journal_mode_override = None
    finalize_database(db_path)
    assert vstate.pragmas == [
      'PRAGMA journal_mode = WAL',
      'PRAGMA wal_checkpoint(TRUNCATE)',
      'PRAGMA wal_checkpoint(TRUNCATE)',
      'PRAGMA journal_mode = DELETE',
      'PRAGMA wal_checkpoint(TRUNCATE)',
      'PRAGMA journal_mode = DELETE',
    ]
    assert keeper.execute('SELECT count(*) FROM run').fetchone() == (1,)

  with _virtual_sqlite_env(
    monkeypatch, 'telemetry_test_cleanup', db_path
  ) as (_keeper, vstate):
    with monkeypatch.context() as mp:
      mp.setattr(
        telemetry,
        'initialize_schema',
        lambda *_a: (_ for _ in ()).throw(
          sqlite3.OperationalError('boom')
        ),
      )
      with pytest.raises(sqlite3.OperationalError, match=r'^boom$'):
        initialize_database(db_path, identity, 10, '3.13.9')
    assert (vstate.exists, vstate.unlinked) == (
      False,
      [
        db_path,
        Path('/virtual/dir/run.sqlite3-wal'),
        Path('/virtual/dir/run.sqlite3-shm'),
      ],
    )

  with _virtual_sqlite_env(
    monkeypatch, 'telemetry_test_close_cleanup', db_path
  ) as (_keeper, vstate):
    vstate.close_error = sqlite3.OperationalError('close boom')
    with pytest.raises(sqlite3.OperationalError, match=r'^close boom$'):
      initialize_database(db_path, identity, 10, '3.13.9')
    assert (vstate.exists, vstate.unlinked) == (
      False,
      [
        db_path,
        Path('/virtual/dir/run.sqlite3-wal'),
        Path('/virtual/dir/run.sqlite3-shm'),
      ],
    )


def test_record_test_result_clamps_non_monotonic_timestamps() -> None:
  connection, identity = initialized_memory_db()
  try:
    test_case = TestCase('zero', 'a.py::test_clock', 'gw0')
    start_id = record_test_start(connection, identity, test_case, 50)
    record_test_result(
      connection,
      identity,
      CompletedTestResult(start_id, test_case, 'passed', 50, 30, -5),
    )
    assert connection.execute(
      'SELECT * FROM test_result ORDER BY event_id'
    ).fetchall() == [
      (
        1,
        start_id,
        'build-1:job-2',
        'rev-3',
        'zero',
        'a.py::test_clock',
        'gw0',
        'passed',
        50,
        50,
        0,
        None,
      )
    ]
  finally:
    connection.close()


def test_record_incomplete_and_worker_failure_results() -> None:
  connection, identity = initialized_memory_db()
  try:
    done_case = TestCase('zero', 'a.py::test_done', 'gw0')
    done_start = record_test_start(connection, identity, done_case, 10)
    record_test_result(
      connection,
      identity,
      CompletedTestResult(done_start, done_case, 'passed', 10, 20, 10),
    )
    crash_case = TestCase('zero', 'a.py::test_crash', 'gw1')
    crash_start = record_test_start(connection, identity, crash_case, 50)
    assert (
      record_test_failure_for_worker(connection, identity, crash_case, 40)
      is True
    )
    assert (
      record_test_failure_for_worker(connection, identity, crash_case, 60)
      is False
    )
    assert (
      record_test_failure_for_worker(
        connection,
        identity,
        TestCase('zero', 'a.py::test_never_started', 'gw2'),
        60,
      )
      is False
    )
    unfinished_start = record_test_start(
      connection,
      identity,
      TestCase('proj', 'b.py::test_hang', 'gw3'),
      100,
    )
    record_incomplete_test_results(connection, identity, 90)

    assert connection.execute(
      'SELECT * FROM test_started ORDER BY event_id'
    ).fetchall() == [
      (
        done_start,
        'build-1:job-2',
        'rev-3',
        'zero',
        'a.py::test_done',
        'gw0',
        10,
      ),
      (
        crash_start,
        'build-1:job-2',
        'rev-3',
        'zero',
        'a.py::test_crash',
        'gw1',
        50,
      ),
      (
        unfinished_start,
        'build-1:job-2',
        'rev-3',
        'proj',
        'b.py::test_hang',
        'gw3',
        100,
      ),
    ]

    expected_results = [
      (
        1,
        done_start,
        'build-1:job-2',
        'rev-3',
        'zero',
        'a.py::test_done',
        'gw0',
        'passed',
        10,
        20,
        10,
        None,
      ),
      (
        2,
        crash_start,
        'build-1:job-2',
        'rev-3',
        'zero',
        'a.py::test_crash',
        'gw1',
        'failed',
        50,
        None,
        None,
        50,
      ),
      (
        3,
        unfinished_start,
        'build-1:job-2',
        'rev-3',
        'proj',
        'b.py::test_hang',
        'gw3',
        'incomplete',
        100,
        None,
        None,
        100,
      ),
    ]
    assert (
      connection.execute(
        'SELECT * FROM test_result ORDER BY event_id'
      ).fetchall()
      == expected_results
    )

    record_test_start(
      connection, identity, TestCase('zero', 'a.py::test_tx1', 'gw0'), 200
    )
    record_test_start(
      connection, identity, TestCase('zero', 'a.py::test_boom', 'gw1'), 210
    )
    connection.execute(
      """
      CREATE TRIGGER fail_on_boom
      BEFORE INSERT ON test_result
      WHEN NEW.nodeid = 'a.py::test_boom'
      BEGIN
        SELECT RAISE(ABORT, 'simulated recovery abort');
      END;
      """
    )
    with pytest.raises(sqlite3.IntegrityError) as abort_exc:
      record_incomplete_test_results(connection, identity, 250)
    assert str(abort_exc.value) == 'simulated recovery abort'
    connection.rollback()
    assert (
      connection.execute(
        'SELECT * FROM test_result ORDER BY event_id'
      ).fetchall()
      == expected_results
    )
  finally:
    connection.close()


@pytest.mark.parametrize(
  'table',
  ['run', 'run_event', 'test_started', 'test_result', 'resource_sample'],
)
def test_schema_enforces_append_only_triggers(table: str) -> None:
  connection, identity = initialized_memory_db()
  try:
    record_run_event(connection, identity, CheckStarted(10))
    test_case = TestCase('zero', 'a.py::test_a', 'gw0')
    start_id = record_test_start(connection, identity, test_case, 20)
    record_test_result(
      connection,
      identity,
      CompletedTestResult(start_id, test_case, 'passed', 20, 30, 10),
    )
    record_resource_sample(
      connection, identity, ResourceSample(40, 10, 0.5, 1024, 1.0, 2.0)
    )

    with pytest.raises(
      sqlite3.IntegrityError, match=r'^telemetry history is append-only$'
    ):
      connection.execute(f"UPDATE {table} SET run_id = 'other'")
    connection.rollback()

    with pytest.raises(
      sqlite3.IntegrityError, match=r'^telemetry history is append-only$'
    ):
      connection.execute(f'DELETE FROM {table}')
    connection.rollback()
  finally:
    connection.close()


_INSERT_TEST_RESULT_SQL = (
  'INSERT INTO test_result '
  '(start_event_id, run_id, source_revision, suite, nodeid, '
  'worker_id, outcome, started_at_ns, ended_at_ns, duration_ns, '
  'recovered_at_ns) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
)


@pytest.mark.parametrize(
  ('action', 'expected_error'),
  [
    (
      lambda conn, _id, _s: conn.execute(
        'INSERT INTO run_event '
        '(run_id, source_revision, event, occurred_at_ns, exit_code) '
        "VALUES ('build-1:job-2', 'wrong-rev', 'check-started', 10, NULL)"
      ),
      'telemetry event identity does not match its run',
    ),
    (
      lambda conn, _id, _s: conn.execute(
        'INSERT INTO test_started '
        '(run_id, source_revision, suite, nodeid, worker_id, '
        'started_at_ns) '
        "VALUES ('build-1:job-2', 'wrong-rev', 'zero', 't.py::t', "
        "'gw0', 10)"
      ),
      'test start identity does not match its run',
    ),
    (
      lambda conn, _id, start_id: (
        conn.execute('DROP TRIGGER test_result_identity_matches_start'),
        conn.execute(
          _INSERT_TEST_RESULT_SQL,
          (
            start_id,
            'build-1:job-2',
            'wrong-rev',
            'zero',
            'a.py::test_a',
            'gw0',
            'passed',
            20,
            30,
            10,
            None,
          ),
        ),
      ),
      'test identity does not match its run',
    ),
    (
      lambda conn, _id, start_id: conn.execute(
        _INSERT_TEST_RESULT_SQL,
        (
          start_id,
          'build-1:job-2',
          'rev-3',
          'zero',
          'a.py::other',
          'gw0',
          'passed',
          20,
          30,
          10,
          None,
        ),
      ),
      'test result does not match its start event',
    ),
    (
      lambda conn, _id, _s: conn.execute(
        'INSERT INTO resource_sample '
        '(run_id, source_revision, sampled_at_ns, interval_ns, cpu_cores, '
        'memory_rss_bytes, read_bytes_per_second, write_bytes_per_second) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        ('build-1:job-2', 'wrong-rev', 40, 10, 0.0, 0, None, None),
      ),
      'resource sample identity does not match its run',
    ),
    (
      lambda conn, _id, _s: conn.execute(
        'INSERT INTO run_event '
        '(run_id, source_revision, event, occurred_at_ns, exit_code) '
        "VALUES ('build-1:job-2', 'rev-3', 'check-started', 10, 0)"
      ),
      "CHECK constraint failed: (event = 'check-started' "
      'AND exit_code IS NULL)\n'
      "    OR (event = 'check-finished' AND exit_code IS NOT NULL)",
    ),
    (
      lambda conn, _id, start_id: conn.execute(
        _INSERT_TEST_RESULT_SQL,
        (
          start_id,
          'build-1:job-2',
          'rev-3',
          'zero',
          'a.py::test_a',
          'gw0',
          'incomplete',
          20,
          30,
          10,
          None,
        ),
      ),
      'CHECK constraint failed: (\n'
      "      outcome != 'incomplete'\n"
      '      AND ended_at_ns IS NOT NULL\n'
      '      AND ended_at_ns >= started_at_ns\n'
      '      AND duration_ns IS NOT NULL\n'
      '      AND recovered_at_ns IS NULL\n'
      '    )\n'
      '    OR (\n'
      "      outcome IN ('failed', 'incomplete')\n"
      '      AND ended_at_ns IS NULL\n'
      '      AND duration_ns IS NULL\n'
      '      AND recovered_at_ns IS NOT NULL\n'
      '      AND recovered_at_ns >= started_at_ns\n'
      '    )',
    ),
    (
      lambda conn, identity, _s: record_resource_sample(
        conn, identity, ResourceSample(40, 0, 0.0, 0, None, None)
      ),
      'CHECK constraint failed: interval_ns > 0',
    ),
  ],
  ids=(
    'run-event-identity',
    'test-started-identity',
    'test-result-run-identity',
    'test-result-start-identity',
    'resource-sample-identity',
    'run-event-check',
    'test-result-check',
    'resource-sample-check',
  ),
)
def test_schema_enforces_identity_and_check_constraints(
  action: Callable[[sqlite3.Connection, RunIdentity, int], object],
  expected_error: str,
) -> None:
  connection, identity = initialized_memory_db()
  try:
    start_id = record_test_start(
      connection, identity, TestCase('zero', 'a.py::test_a', 'gw0'), 20
    )
    with pytest.raises(sqlite3.IntegrityError) as exc_info:
      action(connection, identity, start_id)
    assert str(exc_info.value) == expected_error
    connection.rollback()
  finally:
    connection.close()


def test_validate_database_rejects_fk_and_integrity_failures() -> None:
  fk_connection, _identity = initialized_memory_db()
  try:
    fk_connection.execute(
      'DROP TRIGGER resource_sample_identity_matches_run'
    )
    fk_connection.execute('PRAGMA foreign_keys = OFF')
    fk_connection.execute(
      'INSERT INTO resource_sample '
      '(run_id, source_revision, sampled_at_ns, interval_ns, cpu_cores, '
      'memory_rss_bytes, read_bytes_per_second, write_bytes_per_second) '
      'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
      ('missing:run', 'rev', 40, 10, 0.0, 0, None, None),
    )
    fk_connection.execute('PRAGMA foreign_keys = ON')

    with pytest.raises(sqlite3.DatabaseError) as fk_exc:
      validate_database(fk_connection)
    assert str(fk_exc.value) == (
      'telemetry foreign-key check failed: '
      "[('resource_sample', 1, 'run', 0)]"
    )
  finally:
    fk_connection.close()

  integrity_connection, identity = initialized_memory_db()
  try:
    integrity_connection.execute('PRAGMA ignore_check_constraints = ON')
    record_resource_sample(
      integrity_connection,
      identity,
      ResourceSample(40, 0, 0.0, 0, None, None),
    )
    integrity_connection.execute('PRAGMA ignore_check_constraints = OFF')

    with pytest.raises(sqlite3.DatabaseError) as integrity_exc:
      validate_database(integrity_connection)
    assert str(integrity_exc.value) == (
      'telemetry integrity check failed: '
      "('CHECK constraint failed in resource_sample',)"
    )
  finally:
    integrity_connection.close()

  version_conn, _id = initialized_memory_db()
  try:
    version_conn.execute('PRAGMA user_version = 2')
    with pytest.raises(sqlite3.DatabaseError) as version_exc:
      validate_database(version_conn)
    assert (
      str(version_exc.value) == 'telemetry schema version mismatch: (2,)'
    )
  finally:
    version_conn.close()

  tables_conn = _memory_connection()
  try:
    tables_conn.execute('PRAGMA user_version = 1')
    tables_conn.execute('CREATE TABLE extra_table (id INTEGER)')
    with pytest.raises(sqlite3.DatabaseError) as tables_exc:
      validate_database(tables_conn)
    assert str(tables_exc.value) == (
      "telemetry schema tables mismatch: ['extra_table']"
    )
  finally:
    tables_conn.close()

  empty_run_conn = _memory_connection()
  try:
    empty_run_conn.execute('PRAGMA user_version = 1')
    empty_run_conn.executescript(telemetry.SCHEMA_SQL)
    with pytest.raises(
      sqlite3.DatabaseError,
      match=r'^telemetry run row count mismatch: \(0,\)$',
    ):
      validate_database(empty_run_conn)
  finally:
    empty_run_conn.close()
