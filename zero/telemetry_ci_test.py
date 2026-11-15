"""Tests for the CI test-telemetry wrapper."""

import io
import itertools
import os
import queue
import signal
import sqlite3
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from zero import telemetry, telemetry_ci
from zero.telemetry import (
  RunIdentity,
  TestCase,
  connect_database,
  record_test_start,
)
from zero.telemetry_ci import (
  TelemetryOptions,
  append_pytest_plugin,
  main,
  read_arguments,
  run_instrumented,
  run_uninstrumented,
  sample_resources,
  signal_check_process_group,
  write_completion_marker,
)

IDENTITY = RunIdentity('build-12', 'job-34', 'cafebabe')


def _stat_bytes(
  process_id: int,
  *,
  state: str = 'R',
  session_id: int = 42,
  user_ticks: int = 0,
  system_ticks: int = 0,
  start_time_ticks: int = 1,
  rss_pages: int = 0,
) -> bytes:
  fields = ['0'] * 50
  fields[0] = state
  fields[3] = str(session_id)
  fields[11] = str(user_ticks)
  fields[12] = str(system_ticks)
  fields[19] = str(start_time_ticks)
  fields[21] = str(rss_pages)
  return (f'{process_id} (worker) ' + ' '.join(fields) + '\n').encode()


def _drain_queue(q: queue.SimpleQueue[str]) -> list[str]:
  items: list[str] = []
  while not q.empty():
    items.append(q.get())
  return items


@dataclass
class VirtualFsState:
  db_path: Path
  resolved_path: Path
  marker_path: Path
  exists: bool = False
  marker_created: bool = False
  fail_resolve: OSError | None = None
  fail_marker: OSError | None = None
  unlinked: list[Path] = field(default_factory=list)
  proc_entries: tuple[Path, ...] = ()
  proc_bytes: dict[Path, list[bytes | Exception]] = field(
    default_factory=dict
  )


_REAL_SQLITE_CONNECT = sqlite3.connect


@contextmanager
def _virtual_ci_env(
  monkeypatch: pytest.MonkeyPatch,
  name: str,
  db_path: Path = Path('out/run.sqlite3'),
) -> Iterator[tuple[sqlite3.Connection, VirtualFsState]]:
  resolved_path = Path(f'/virtual/{db_path.name}')
  marker_path = resolved_path.with_name(f'{resolved_path.name}.complete')
  state = VirtualFsState(
    db_path=db_path, resolved_path=resolved_path, marker_path=marker_path
  )
  uri = f'file:/{name}?vfs=memdb'
  keeper = _REAL_SQLITE_CONNECT(uri, uri=True)

  def fake_resolve(self: Path) -> Path:
    if state.fail_resolve is not None and self == db_path:
      raise state.fail_resolve
    if self == db_path:
      return resolved_path
    return self

  def fake_mkdir(
    self: Path,
    mode: int = 0o777,
    parents: bool = False,
    exist_ok: bool = False,
  ) -> None:
    del self, mode, parents, exist_ok

  def fake_exists(self: Path) -> bool:
    return (self == resolved_path or self == db_path) and state.exists

  def fake_is_file(self: Path) -> bool:
    return (self == resolved_path or self == db_path) and state.exists

  def fake_open(self: Path, mode: str = 'r') -> io.BytesIO:
    assert mode == 'xb'
    if self == marker_path:
      if state.fail_marker is not None:
        raise state.fail_marker
      if state.marker_created:
        raise FileExistsError(self)
      state.marker_created = True
      return io.BytesIO()
    assert self == resolved_path or self == db_path
    if state.exists:
      raise FileExistsError(self)
    state.exists = True
    return io.BytesIO()

  def fake_unlink(self: Path, missing_ok: bool = False) -> None:
    state.unlinked.append(self)
    if self == resolved_path or self == db_path:
      state.exists = False
      return
    if not missing_ok:
      raise FileNotFoundError(self)

  def fake_connect(
    target: object, timeout: float = 5.0
  ) -> sqlite3.Connection:
    assert target == resolved_path or target == db_path
    return _REAL_SQLITE_CONNECT(uri, timeout=timeout, uri=True)

  def fake_iterdir(self: Path) -> Iterator[Path]:
    assert self == Path('/proc')
    return iter(state.proc_entries)

  def fake_read_bytes(self: Path) -> bytes:
    value = state.proc_bytes[self].pop(0)
    if isinstance(value, Exception):
      raise value
    return value

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', fake_resolve)
    mp.setattr(Path, 'mkdir', fake_mkdir)
    mp.setattr(Path, 'exists', fake_exists)
    mp.setattr(Path, 'is_file', fake_is_file)
    mp.setattr(Path, 'open', fake_open)
    mp.setattr(Path, 'unlink', fake_unlink)
    mp.setattr(Path, 'iterdir', fake_iterdir)
    mp.setattr(Path, 'read_bytes', fake_read_bytes)
    mp.setattr(telemetry.sqlite3, 'connect', fake_connect)
    try:
      yield keeper, state
    finally:
      keeper.close()


def _make_stop_event(
  responses: Sequence[bool], timeouts: list[float | None]
) -> threading.Event:
  iterator = iter(responses)
  event = SimpleNamespace(
    wait=lambda timeout=None: (
      timeouts.append(timeout),
      next(iterator),
    )[1],
    set=lambda: None,
  )
  return cast(threading.Event, event)


def _setup_sample_clock(
  monkeypatch: pytest.MonkeyPatch,
  wall_ns: Iterator[int],
  mono_ns: Iterator[int],
) -> None:
  monkeypatch.setattr(
    telemetry_ci.os,
    'sysconf',
    lambda name: 4096 if name == 'SC_PAGE_SIZE' else 100,
  )
  monkeypatch.setattr(telemetry_ci.time, 'time_ns', lambda: next(wall_ns))
  monkeypatch.setattr(
    telemetry_ci.time, 'monotonic_ns', lambda: next(mono_ns)
  )


@pytest.mark.parametrize(
  ('arguments', 'expected'),
  [
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=-rev1',
        '--',
        '0',
        'check',
      ],
      TelemetryOptions(
        database=Path('out/run.sqlite3'),
        build_id='b1',
        job_id='j1',
        revision='-rev1',
        command=('0', 'check'),
      ),
    ),
    (
      [
        '--database',
        'out/run.sqlite3',
        '--build-id',
        'b2',
        '--job-id',
        'j2',
        '--revision',
        'rev2',
        '--',
        'pytest',
        '-q',
      ],
      TelemetryOptions(
        database=Path('out/run.sqlite3'),
        build_id='b2',
        job_id='j2',
        revision='rev2',
        command=('pytest', '-q'),
      ),
    ),
  ],
)
def test_read_arguments_parses_valid_options(
  arguments: list[str], expected: TelemetryOptions
) -> None:
  assert read_arguments(arguments) == expected


@pytest.mark.parametrize(
  ('bad_arguments', 'expected_error'),
  [
    (
      [
        '--database=',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=.',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=:memory:',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=file:/x?vfs=memdb',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=/',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=..',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=.//',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=./:memory:',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=./file:x',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=dir/',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=dir/.',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=out/run.sqlite3\x00',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--database must be a valid filesystem path',
    ),
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=',
        '--job-id=j1',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--build-id must not be empty',
    ),
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=b1',
        '--job-id=',
        '--revision=rev1',
        '--',
        '0',
      ],
      '--job-id must not be empty',
    ),
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=',
        '--',
        '0',
      ],
      '--revision must not be empty',
    ),
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        '--',
      ],
      'a command must follow --',
    ),
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
      ],
      'a command must follow --',
    ),
    (
      [
        '--database=out/run.sqlite3',
        '--build-id=b1',
        '--job-id=j1',
        '--revision=rev1',
        'stray',
        '--',
        '0',
        'check',
      ],
      'unrecognized arguments: stray',
    ),
  ],
)
def test_read_arguments_rejects_invalid_values(
  bad_arguments: list[str],
  expected_error: str,
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  monkeypatch.setenv('COLUMNS', '80')
  with pytest.raises(SystemExit) as exc_info:
    read_arguments(bad_arguments)
  assert exc_info.value.code == 2
  assert capsys.readouterr().err == (
    'usage: python -m zero.telemetry_ci [-h] --database DATABASE '
    '--build-id BUILD_ID --job-id JOB_ID --revision REVISION -- ...\n'
    f'python -m zero.telemetry_ci: error: {expected_error}\n'
  )


def test_read_arguments_help_shows_strict_separator_usage(
  capsys: pytest.CaptureFixture[str],
) -> None:
  with pytest.raises(SystemExit) as exc_info:
    read_arguments(['-h'])
  assert exc_info.value.code == 0
  stdout = capsys.readouterr().out
  assert stdout.splitlines()[0] == (
    'usage: python -m zero.telemetry_ci [-h] --database DATABASE '
    '--build-id BUILD_ID --job-id JOB_ID --revision REVISION -- ...'
  )


@pytest.mark.parametrize(
  ('initial', 'expected'),
  [
    ('', 'zero.telemetry_plugin'),
    ('xdist,other', 'xdist,other,zero.telemetry_plugin'),
    ('xdist,zero.telemetry_plugin', 'xdist,zero.telemetry_plugin'),
    ('xdist,,zero.telemetry_plugin,', 'xdist,zero.telemetry_plugin'),
  ],
)
def test_append_pytest_plugin_updates_environment_without_duplicates(
  initial: str, expected: str
) -> None:
  environment = {'PYTEST_PLUGINS': initial} if initial else {}
  append_pytest_plugin(environment)
  assert environment == {'PYTEST_PLUGINS': expected}


def test_sample_resources_records_normal_and_short_runs(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  db_path = Path('/virtual/ci_sample.sqlite3')
  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sample_normal', db_path) as (
      keeper,
      vstate,
    ),
  ):
    telemetry.initialize_database(db_path, IDENTITY, 1_000, '3.13.9')
    vstate.proc_entries = (Path('/proc/10'),)
    vstate.proc_bytes = {
      Path('/proc/10/stat'): [
        _stat_bytes(10, user_ticks=10, system_ticks=5, rss_pages=10),
        _stat_bytes(10, user_ticks=30, system_ticks=15, rss_pages=20),
        _stat_bytes(10, user_ticks=40, system_ticks=25, rss_pages=15),
      ],
      Path('/proc/10/io'): [
        b'read_bytes: 100\nwrite_bytes: 200\n',
        b'read_bytes: 600\nwrite_bytes: 1200\n',
        b'read_bytes: 1100\nwrite_bytes: 1200\n',
      ],
    }
    _setup_sample_clock(
      mp,
      itertools.count(1_000_000_000, 500_000_000),
      itertools.count(2_000_000_000, 500_000_000),
    )
    timeouts: list[float | None] = []
    errors: queue.SimpleQueue[str] = queue.SimpleQueue()
    sample_resources(
      db_path,
      IDENTITY,
      42,
      _make_stop_event([False, False, True], timeouts),
      errors,
    )
    assert timeouts == [0.5, 0.5, 0.5]
    assert _drain_queue(errors) == []
    rows = keeper.execute(
      'SELECT event_id, run_id, source_revision, sampled_at_ns, '
      'interval_ns, cpu_cores, memory_rss_bytes, read_bytes_per_second, '
      'write_bytes_per_second FROM resource_sample ORDER BY event_id'
    ).fetchall()
    rid = 'build-12:job-34'
    rev = 'cafebabe'
    assert rows == [
      (
        1,
        rid,
        rev,
        1_500_000_000,
        500_000_000,
        0.6,
        20 * 4096,
        1000.0,
        2000.0,
      ),
      (
        2,
        rid,
        rev,
        2_000_000_000,
        500_000_000,
        0.4,
        15 * 4096,
        1000.0,
        0.0,
      ),
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sample_short', db_path) as (
      keeper,
      vstate,
    ),
  ):
    telemetry.initialize_database(db_path, IDENTITY, 1_000, '3.13.9')
    vstate.proc_entries = (Path('/proc/10'),)
    vstate.proc_bytes = {
      Path('/proc/10/stat'): [
        _stat_bytes(10, user_ticks=10, system_ticks=5, rss_pages=10)
      ],
      Path('/proc/10/io'): [b'read_bytes: 100\nwrite_bytes: 200\n'],
    }
    _setup_sample_clock(mp, iter([1_000]), iter([2_000]))
    errors = queue.SimpleQueue()
    sample_resources(
      db_path, IDENTITY, 42, _make_stop_event([True], []), errors
    )
    assert _drain_queue(errors) == []
    assert keeper.execute('SELECT * FROM resource_sample').fetchall() == []


def test_sample_resources_handles_mid_exit_bad_io_and_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  db_path = Path('/virtual/ci_sample_edge.sqlite3')
  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sample_mid_exit', db_path) as (
      keeper,
      vstate,
    ),
  ):
    telemetry.initialize_database(db_path, IDENTITY, 1_000, '3.13.9')
    vstate.proc_entries = (Path('/proc/10'), Path('/proc/11'))
    vstate.proc_bytes = {
      Path('/proc/10/stat'): [
        _stat_bytes(10, user_ticks=10, rss_pages=4),
        _stat_bytes(10, user_ticks=30, rss_pages=8),
        _stat_bytes(10, user_ticks=50, rss_pages=8),
      ],
      Path('/proc/10/io'): [
        b'read_bytes: 100\nwrite_bytes: 50\n',
        b'read_bytes: 600\nwrite_bytes: 550\n',
        b'read_bytes: 1100\nwrite_bytes: 1050\n',
      ],
      Path('/proc/11/stat'): [
        _stat_bytes(11, user_ticks=5, rss_pages=2),
        FileNotFoundError(11),
        FileNotFoundError(11),
        FileNotFoundError(11),
      ],
      Path('/proc/11/io'): [FileNotFoundError(11)],
    }
    _setup_sample_clock(
      mp,
      itertools.count(1_000_000_000, 500_000_000),
      itertools.count(2_000_000_000, 500_000_000),
    )
    errors: queue.SimpleQueue[str] = queue.SimpleQueue()
    sample_resources(
      db_path,
      IDENTITY,
      42,
      _make_stop_event([False, False, True], []),
      errors,
    )
    assert _drain_queue(errors) == []
    rows = keeper.execute(
      'SELECT * FROM resource_sample ORDER BY event_id'
    ).fetchall()
    rid = 'build-12:job-34'
    rev = 'cafebabe'
    assert rows == [
      (
        1,
        rid,
        rev,
        1_500_000_000,
        500_000_000,
        0.4,
        8 * 4096,
        1000.0,
        1000.0,
      ),
      (
        2,
        rid,
        rev,
        2_000_000_000,
        500_000_000,
        0.4,
        8 * 4096,
        1000.0,
        1000.0,
      ),
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sample_bad_io', db_path) as (
      keeper,
      vstate,
    ),
  ):
    telemetry.initialize_database(db_path, IDENTITY, 1_000, '3.13.9')
    vstate.proc_entries = (Path('/proc/10'),)
    vstate.proc_bytes = {
      Path('/proc/10/stat'): [
        _stat_bytes(10, user_ticks=10, rss_pages=4),
        _stat_bytes(10, user_ticks=20, rss_pages=6),
        _stat_bytes(10, user_ticks=20, rss_pages=6),
      ],
      Path('/proc/10/io'): [
        b'read_bytes: 100\nwrite_bytes: 50\n',
        b'read_bytes: \xff\n',
      ],
    }
    _setup_sample_clock(
      mp,
      itertools.count(1_000_000_000, 500_000_000),
      itertools.count(2_000_000_000, 500_000_000),
    )
    errors = queue.SimpleQueue()
    sample_resources(
      db_path, IDENTITY, 42, _make_stop_event([False, True], []), errors
    )
    assert _drain_queue(errors) == []
    rows = keeper.execute(
      'SELECT * FROM resource_sample ORDER BY event_id'
    ).fetchall()
    assert rows == [
      (
        1,
        'build-12:job-34',
        'cafebabe',
        1_500_000_000,
        500_000_000,
        0.2,
        6 * 4096,
        None,
        None,
      )
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sample_db_error', db_path),
  ):
    _setup_sample_clock(mp, iter([1, 2]), itertools.count(1, 100))
    errors = queue.SimpleQueue()
    sample_resources(
      db_path, IDENTITY, 42, _make_stop_event([False, True], []), errors
    )
    assert _drain_queue(errors) == ['no such table: resource_sample']

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sample_close_error', db_path),
  ):
    telemetry.initialize_database(db_path, IDENTITY, 1_000, '3.13.9')
    _setup_sample_clock(mp, iter([1_000]), iter([2_000]))
    real_connect_db = telemetry_ci.connect_database

    def connect_with_broken_close(database: Path) -> sqlite3.Connection:
      conn = real_connect_db(database)
      return cast(
        sqlite3.Connection,
        SimpleNamespace(
          execute=conn.execute,
          commit=conn.commit,
          close=lambda: (_ for _ in ()).throw(
            sqlite3.OperationalError('close failed')
          ),
        ),
      )

    mp.setattr(telemetry_ci, 'connect_database', connect_with_broken_close)
    errors = queue.SimpleQueue()
    sample_resources(
      db_path, IDENTITY, 42, _make_stop_event([True], []), errors
    )
    assert _drain_queue(errors) == ['close failed']


def test_run_uninstrumented_and_signal_and_completion_marker(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  with monkeypatch.context() as mp:
    _install_single_thread_runtime(
      mp, wall_ns=itertools.repeat(0), mono_s=itertools.repeat(0.0)
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda _cmd, env=None, start_new_session=False: SimpleNamespace(
        pid=501, wait=lambda timeout=None: 3
      ),
    )
    assert run_uninstrumented(['0', 'check']) == 3

  with monkeypatch.context() as mp:
    _install_single_thread_runtime(
      mp, wall_ns=itertools.repeat(0), mono_s=itertools.repeat(0.0)
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda _cmd, env=None, start_new_session=False: SimpleNamespace(
        pid=502, wait=lambda timeout=None: -15
      ),
    )
    assert run_uninstrumented(['0', 'check']) == 143

  with monkeypatch.context() as mp:
    _install_single_thread_runtime(
      mp, wall_ns=itertools.repeat(0), mono_s=itertools.repeat(0.0)
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_args, **_kwargs: (_ for _ in ()).throw(
        FileNotFoundError('missing command')
      ),
    )
    assert run_uninstrumented(['0', 'check']) == 127
    assert capsys.readouterr().err == (
      'Unable to run check command: missing command\n'
    )

  with monkeypatch.context() as mp:
    handlers: dict[int, Callable[[int, object], None]] = {}
    signals_sent = _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(0),
      mono_s=iter([10.0, 10.5]),
      installed_handlers=handlers,
      waitid_fn=lambda _t, _p, _o: handlers[signal.SIGINT](
        signal.SIGINT, None
      ),
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda _cmd, env=None, start_new_session=False: SimpleNamespace(
        pid=504, wait=lambda timeout=None: -signal.SIGINT
      ),
    )
    assert run_uninstrumented(['0', 'check']) == 130
    assert signals_sent == [(504, signal.SIGINT)]
    assert handlers == {}

  with monkeypatch.context() as mp:
    sent: list[tuple[int, int]] = []
    mp.setattr(
      telemetry_ci.os, 'killpg', lambda pid, sig: sent.append((pid, sig))
    )
    signal_check_process_group(123, signal.SIGTERM)
    assert sent == [(123, signal.SIGTERM)]

  with monkeypatch.context() as mp:
    mp.setattr(
      telemetry_ci.os,
      'killpg',
      lambda _p, _s: (_ for _ in ()).throw(ProcessLookupError('gone')),
    )
    signal_check_process_group(123, signal.SIGTERM)
    assert capsys.readouterr().err == ''

  with monkeypatch.context() as mp:
    mp.setattr(
      telemetry_ci.os,
      'killpg',
      lambda _p, _s: (_ for _ in ()).throw(PermissionError('denied')),
    )
    signal_check_process_group(123, signal.SIGTERM)
    assert capsys.readouterr().err == (
      'Unable to signal check process group: denied\n'
    )

  with monkeypatch.context() as mp:
    opened: list[tuple[Path, str]] = []
    mp.setattr(
      Path,
      'open',
      lambda self, mode='r': (opened.append((self, mode)), io.BytesIO())[
        1
      ],
    )
    write_completion_marker(Path('artifacts/run.sqlite3'))
    assert opened == [(Path('artifacts/run.sqlite3.complete'), 'xb')]
  with pytest.raises(ValueError) as bad_marker_exc:
    write_completion_marker(Path(''))
  assert str(bad_marker_exc.value) == 'invalid telemetry database path: .'


def test_run_instrumented_falls_back_on_setup_or_resolve_failure(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_resolve_fail') as (_k, vstate),
  ):
    uninstrumented: list[tuple[str, ...]] = []
    mp.setattr(
      telemetry_ci,
      'run_uninstrumented',
      lambda cmd: (uninstrumented.append(tuple(cmd)), 7)[1],
    )
    mp.setattr(telemetry_ci.time, 'time_ns', lambda: 100)
    vstate.fail_resolve = OSError('bad path')
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 7
    )
    assert uninstrumented == [('0', 'check')]
    assert capsys.readouterr().err == (
      'CI test telemetry unavailable: bad path\n'
    )

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_started_fail') as (_k, vstate),
  ):
    uninstrumented = []
    mp.setattr(
      telemetry_ci,
      'run_uninstrumented',
      lambda cmd: (uninstrumented.append(tuple(cmd)), 7)[1],
    )
    mp.setattr(telemetry_ci.time, 'time_ns', lambda: 100)
    mp.setattr(
      telemetry_ci,
      'record_run_event',
      lambda *_a: (_ for _ in ()).throw(
        sqlite3.OperationalError('check-started failed')
      ),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 7
    )
    assert uninstrumented == [('0', 'check')]
    assert vstate.exists is False
    assert vstate.unlinked == [
      vstate.resolved_path,
      Path('/virtual/run.sqlite3-wal'),
      Path('/virtual/run.sqlite3-shm'),
    ]
    assert capsys.readouterr().err == (
      'CI test telemetry unavailable: check-started failed\n'
    )

  with monkeypatch.context() as mp, _virtual_ci_env(mp, 'ci_import_fail'):
    uninstrumented = []
    mp.setattr(
      telemetry_ci,
      'run_uninstrumented',
      lambda cmd: (uninstrumented.append(tuple(cmd)), 7)[1],
    )
    mp.setattr(telemetry_ci.time, 'time_ns', lambda: 100)
    mp.setattr(
      telemetry_ci.importlib,
      'import_module',
      lambda _name: (_ for _ in ()).throw(ImportError('plugin missing')),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 7
    )
    assert uninstrumented == [('0', 'check')]
    assert capsys.readouterr().err == (
      'CI test telemetry unavailable: plugin missing\n'
    )


def _install_single_thread_runtime(
  monkeypatch: pytest.MonkeyPatch,
  *,
  wall_ns: Iterator[int],
  mono_s: Iterator[float],
  event_log: list[str] | None = None,
  installed_handlers: dict[int, Callable[[int, object], None]]
  | None = None,
  is_main_thread: bool = True,
  sampler_start_error: Exception | None = None,
  sampler_runtime_error: str | None = None,
  waitid_fn: Callable[[int, int, int], object] | None = None,
  getsignal_overrides: dict[int, object] | None = None,
  thread_records: list[tuple[object, tuple[object, ...], bool, list[bool]]]
  | None = None,
) -> list[tuple[int, int]]:
  signals_sent: list[tuple[int, int]] = []
  monkeypatch.setattr(telemetry_ci.time, 'time_ns', lambda: next(wall_ns))
  monkeypatch.setattr(telemetry_ci.time, 'monotonic', lambda: next(mono_s))
  monkeypatch.setattr(
    telemetry_ci.os,
    'killpg',
    lambda pid, sig: signals_sent.append((pid, sig)),
  )

  def fake_waitid(idtype: int, pid: int, options: int) -> None:
    assert idtype == os.P_PID
    assert options == (os.WEXITED | os.WNOWAIT)
    if waitid_fn is not None:
      waitid_fn(idtype, pid, options)

  monkeypatch.setattr(telemetry_ci.os, 'waitid', fake_waitid)

  sentinel_main = SimpleNamespace(name='main')
  sentinel_other = SimpleNamespace(name='worker')
  monkeypatch.setattr(
    telemetry_ci.threading, 'main_thread', lambda: sentinel_main
  )
  monkeypatch.setattr(
    telemetry_ci.threading,
    'current_thread',
    lambda: sentinel_main if is_main_thread else sentinel_other,
  )

  previous = {
    signal.SIGINT: SimpleNamespace(name='prev_int'),
    signal.SIGTERM: SimpleNamespace(name='prev_term'),
  }

  missing_signal = object()

  def fake_getsignal(signum: int) -> object:
    if getsignal_overrides is not None:
      override = getsignal_overrides.get(signum, missing_signal)
      if override is not missing_signal:
        return override
    return previous[signum]

  def fake_signal(signum: int, handler: object) -> object:
    if handler is None:
      raise TypeError('handler must not be None')
    if handler == previous[signum]:
      if event_log is not None:
        event_log.append(f'restore-{signum}')
      if installed_handlers is not None:
        installed_handlers.pop(signum, None)
      return handler
    if event_log is not None:
      event_log.append(f'install-{signum}')
    if installed_handlers is not None and callable(handler):
      installed_handlers[signum] = cast(
        Callable[[int, object], None], handler
      )
    return previous[signum]

  monkeypatch.setattr(telemetry_ci.signal, 'getsignal', fake_getsignal)
  monkeypatch.setattr(telemetry_ci.signal, 'signal', fake_signal)

  def fake_thread(
    target: Callable[..., None],
    args: tuple[object, ...],
    daemon: bool = False,
  ) -> object:
    stop_event = cast(threading.Event, args[3])
    errors_queue = cast(queue.SimpleQueue[str], args[4])
    stop_states: list[bool] = []
    if thread_records is not None:
      thread_records.append((target, args, daemon, stop_states))

    def start() -> None:
      stop_states.append(stop_event.is_set())
      if sampler_start_error is not None:
        raise sampler_start_error
      if sampler_runtime_error is not None:
        errors_queue.put(sampler_runtime_error)
      if event_log is not None:
        event_log.append('sampler-start')

    def join() -> None:
      stop_states.append(stop_event.is_set())
      if event_log is not None:
        event_log.append('sampler-join')

    return SimpleNamespace(start=start, join=join)

  monkeypatch.setattr(telemetry_ci.threading, 'Thread', fake_thread)
  return signals_sent


def test_run_instrumented_records_env_recovery_and_signal_order(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.delenv('PYTEST_PLUGINS', raising=False)
  monkeypatch.setenv('PYTEST_XDIST_WORKER', 'gw9')

  event_log: list[str] = []
  thread_records: list[
    tuple[object, tuple[object, ...], bool, list[bool]]
  ] = []
  with _virtual_ci_env(monkeypatch, 'ci_instrumented_ok') as (
    keeper,
    vstate,
  ):
    handlers: dict[int, Callable[[int, object], None]] = {}
    signals_sent = _install_single_thread_runtime(
      monkeypatch,
      wall_ns=itertools.count(5_000, 1_000),
      mono_s=itertools.repeat(1.0),
      event_log=event_log,
      installed_handlers=handlers,
      thread_records=thread_records,
    )
    real_marker = telemetry_ci.write_completion_marker

    def traced_marker(database: Path) -> None:
      event_log.append('write-marker')
      handlers[signal.SIGINT](signal.SIGINT, None)
      real_marker(database)

    monkeypatch.setattr(
      telemetry_ci, 'write_completion_marker', traced_marker
    )

    spawn_calls: list[tuple[tuple[str, ...], dict[str, str], bool]] = []

    def fake_popen(
      command: Sequence[str],
      *,
      env: dict[str, str],
      start_new_session: bool,
    ) -> object:
      spawn_calls.append((tuple(command), dict(env), start_new_session))
      conn = connect_database(vstate.resolved_path)
      try:
        record_test_start(
          conn,
          IDENTITY,
          TestCase('zero', 'zero/t.py::test_x', 'gw0'),
          5_500,
        )
      finally:
        conn.close()
      return SimpleNamespace(pid=777, wait=lambda timeout=None: 0)

    monkeypatch.setattr(telemetry_ci.subprocess, 'Popen', fake_popen)

    code = run_instrumented(
      Path('out/run.sqlite3'), IDENTITY, ['0', 'check']
    )
    assert code == 0
    assert signals_sent == []
    assert handlers == {}
    assert vstate.marker_created is True
    assert len(thread_records) == 1
    target, thread_args, daemon, stop_states = thread_records[0]
    assert target is sample_resources
    assert len(thread_args) == 5
    assert thread_args[:3] == (vstate.resolved_path, IDENTITY, 777)
    assert isinstance(thread_args[3], threading.Event)
    assert isinstance(thread_args[4], queue.SimpleQueue)
    assert daemon is True
    assert stop_states == [False, True]
    assert event_log == [
      f'install-{signal.SIGINT}',
      f'install-{signal.SIGTERM}',
      'sampler-start',
      'sampler-join',
      'write-marker',
      f'restore-{signal.SIGINT}',
      f'restore-{signal.SIGTERM}',
    ]
    assert len(spawn_calls) == 1
    cmd, env, new_session = spawn_calls[0]
    assert (cmd, new_session) == (('0', 'check'), True)
    assert (
      env['PENTAGRAM_TEST_TELEMETRY_DB'],
      env['PENTAGRAM_TEST_TELEMETRY_BUILD_ID'],
      env['PENTAGRAM_TEST_TELEMETRY_JOB_ID'],
      env['PENTAGRAM_TEST_TELEMETRY_REVISION'],
      env.get('PYTEST_XDIST_WORKER'),
      env['PYTEST_PLUGINS'],
    ) == (
      str(vstate.resolved_path),
      IDENTITY.build_id,
      IDENTITY.job_id,
      IDENTITY.source_revision,
      None,
      'zero.telemetry_plugin',
    )

    rid = 'build-12:job-34'
    rev = 'cafebabe'
    assert keeper.execute(
      'SELECT run_id, build_id, job_id, source_revision, python_version, '
      'started_at_ns FROM run'
    ).fetchall() == [
      (rid, 'build-12', 'job-34', rev, sys.version.split()[0], 5_000)
    ]
    assert keeper.execute(
      'SELECT event_id, run_id, source_revision, event, occurred_at_ns, '
      'exit_code FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 5_000, None),
      (2, rid, rev, 'check-finished', 6_000, 0),
    ]
    assert keeper.execute(
      'SELECT * FROM test_started ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'zero', 'zero/t.py::test_x', 'gw0', 5_500)
    ]
    assert keeper.execute(
      'SELECT * FROM test_result ORDER BY event_id'
    ).fetchall() == [
      (
        1,
        1,
        rid,
        rev,
        'zero',
        'zero/t.py::test_x',
        'gw0',
        'incomplete',
        5_500,
        None,
        None,
        6_000,
      )
    ]
    assert (
      keeper.execute(
        'SELECT * FROM resource_sample ORDER BY event_id'
      ).fetchall()
      == []
    )


def test_run_instrumented_handles_spawn_signals_non_main_and_errors(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  rid = 'build-12:job-34'
  rev = 'cafebabe'
  py_ver = sys.version.split()[0]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_spawn_fail') as (keeper, vstate),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    _install_single_thread_runtime(
      mp, wall_ns=itertools.repeat(1_000), mono_s=itertools.repeat(1.0)
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: (_ for _ in ()).throw(
        FileNotFoundError('missing bin')
      ),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 127
    )
    assert vstate.marker_created is True
    assert capsys.readouterr().err == (
      'Unable to run check command: missing bin\n'
    )
    assert keeper.execute('SELECT * FROM run').fetchall() == [
      (rid, 'build-12', 'job-34', rev, py_ver, 1_000)
    ]
    assert keeper.execute(
      'SELECT * FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 1_000, None),
      (2, rid, rev, 'check-finished', 1_000, 127),
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sigterm_clean') as (keeper, _vs),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    handlers: dict[int, Callable[[int, object], None]] = {}
    signals_sent = _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(2_000),
      mono_s=iter([10.0, 10.5]),
      installed_handlers=handlers,
      waitid_fn=lambda _t, _p, _o: handlers[signal.SIGTERM](
        signal.SIGTERM, None
      ),
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(
        pid=888, wait=lambda timeout=None: -signal.SIGTERM
      ),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 143
    )
    assert signals_sent == [(888, signal.SIGTERM)]
    assert handlers == {}
    assert keeper.execute('SELECT * FROM run').fetchall() == [
      (rid, 'build-12', 'job-34', rev, py_ver, 2_000)
    ]
    assert keeper.execute(
      'SELECT * FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 2_000, None),
      (2, rid, rev, 'check-finished', 2_000, 143),
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sigterm_grace') as (keeper, _vs),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    handlers = {}
    signals_sent = _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(2_000),
      mono_s=iter([10.0, 12.0]),
      installed_handlers=handlers,
      waitid_fn=lambda _t, _p, _o: handlers[signal.SIGTERM](
        signal.SIGTERM, None
      ),
    )
    wait_calls = itertools.count()

    def wait_grace_timeout(timeout: float | None = None) -> int:
      if next(wait_calls) == 0:
        assert timeout == 3.0
        raise subprocess.TimeoutExpired(['0', 'check'], 3.0)
      assert timeout is None
      return -signal.SIGKILL

    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(pid=889, wait=wait_grace_timeout),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 143
    )
    assert signals_sent == [
      (889, signal.SIGTERM),
      (889, signal.SIGKILL),
    ]
    assert keeper.execute('SELECT * FROM run').fetchall() == [
      (rid, 'build-12', 'job-34', rev, py_ver, 2_000)
    ]
    assert keeper.execute(
      'SELECT * FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 2_000, None),
      (2, rid, rev, 'check-finished', 2_000, 143),
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_pre_pid_sigint') as (keeper, _vs),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    handlers = {}
    signals_sent = _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(3_000),
      mono_s=iter([20.0, 20.5]),
      installed_handlers=handlers,
      waitid_fn=lambda *_a: (_ for _ in ()).throw(
        AssertionError('waitid should not run after pre-pid signal')
      ),
    )

    def popen_with_early_sigint(*_a: object, **_kw: object) -> object:
      handlers[signal.SIGINT](signal.SIGINT, None)
      assert signals_sent == []
      return SimpleNamespace(pid=778, wait=lambda timeout=None: 0)

    mp.setattr(telemetry_ci.subprocess, 'Popen', popen_with_early_sigint)
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 130
    )
    assert signals_sent == [(778, signal.SIGINT)]
    assert keeper.execute(
      'SELECT * FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 3_000, None),
      (2, rid, rev, 'check-finished', 3_000, 130),
    ]

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sigterm_none_and_sampler_error') as (
      _keeper,
      vstate,
    ),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    event_log: list[str] = []
    _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(3_500),
      mono_s=itertools.repeat(3.0),
      event_log=event_log,
      getsignal_overrides={signal.SIGTERM: None},
      sampler_runtime_error='sampler thread failed',
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(
        pid=779, wait=lambda timeout=None: 0
      ),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 0
    )
    assert event_log == [
      f'install-{signal.SIGINT}',
      'sampler-start',
      'sampler-join',
      f'restore-{signal.SIGINT}',
    ]
    assert vstate.marker_created is True
    assert capsys.readouterr().err == (
      'CI resource sampling unavailable: sampler thread failed\n'
    )

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_sigterm_ignored') as (_keeper, vstate),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    event_log = []
    _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(3_600),
      mono_s=itertools.repeat(3.0),
      event_log=event_log,
      getsignal_overrides={signal.SIGTERM: signal.SIG_IGN},
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(
        pid=781, wait=lambda timeout=None: 0
      ),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 0
    )
    assert event_log == [
      f'install-{signal.SIGINT}',
      'sampler-start',
      'sampler-join',
      f'restore-{signal.SIGINT}',
    ]
    assert vstate.marker_created is True

  with (
    monkeypatch.context() as mp,
    _virtual_ci_env(mp, 'ci_non_main_and_errors') as (keeper, vstate),
  ):
    mp.delenv('PYTEST_PLUGINS', raising=False)
    event_log = []
    _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(4_000),
      mono_s=itertools.repeat(4.0),
      event_log=event_log,
      is_main_thread=False,
      sampler_start_error=RuntimeError('no threads'),
    )
    vstate.fail_marker = OSError('disk full')
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(
        pid=321, wait=lambda timeout=None: -9
      ),
    )
    assert (
      run_instrumented(Path('out/run.sqlite3'), IDENTITY, ['0', 'check'])
      == 137
    )
    assert event_log == []
    assert capsys.readouterr().err == (
      'CI resource sampling unavailable: no threads\n'
      'CI telemetry finalization failed: disk full\n'
    )
    assert keeper.execute('SELECT * FROM run').fetchall() == [
      (rid, 'build-12', 'job-34', rev, py_ver, 4_000)
    ]
    assert keeper.execute(
      'SELECT * FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 4_000, None),
      (2, rid, rev, 'check-finished', 4_000, 137),
    ]


def test_finalize_instrumented_run_handles_recovery_and_rollback_errors(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  rid = 'build-12:job-34'
  rev = 'cafebabe'
  with _virtual_ci_env(
    monkeypatch, 'ci_finalize_recover_and_rollback_err'
  ) as (
    keeper,
    vstate,
  ):
    _install_single_thread_runtime(
      monkeypatch,
      wall_ns=iter([3_800, 3_900]),
      mono_s=itertools.repeat(1.0),
    )
    real_connect_finalize = telemetry_ci.connect_database

    def connect_with_broken_rollback(database: Path) -> sqlite3.Connection:
      conn = real_connect_finalize(database)
      return cast(
        sqlite3.Connection,
        SimpleNamespace(
          execute=conn.execute,
          commit=conn.commit,
          close=conn.close,
          rollback=lambda: (_ for _ in ()).throw(
            sqlite3.ProgrammingError('rollback broken')
          ),
        ),
      )

    monkeypatch.setattr(
      telemetry_ci, 'connect_database', connect_with_broken_rollback
    )
    monkeypatch.setattr(
      telemetry_ci,
      'record_incomplete_test_results',
      lambda *_a: (_ for _ in ()).throw(
        sqlite3.OperationalError('recover failed')
      ),
    )
    monkeypatch.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(
        pid=780, wait=lambda timeout=None: 0
      ),
    )
    code = run_instrumented(
      Path('out/run.sqlite3'), IDENTITY, ['0', 'check']
    )
    assert code == 0
    assert capsys.readouterr().err == (
      'CI incomplete-test recovery unavailable: recover failed\n'
    )
    assert vstate.marker_created is True
    assert keeper.execute(
      'SELECT * FROM run_event ORDER BY event_id'
    ).fetchall() == [
      (1, rid, rev, 'check-started', 3_800, None),
      (2, rid, rev, 'check-finished', 3_900, 0),
    ]


@pytest.mark.parametrize('waitid_error', [False, True])
def test_run_uninstrumented_handles_sigterm_at_every_executed_line(
  waitid_error: bool,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  module_file = telemetry_ci.__file__
  assert module_file is not None

  def dry_waitid(_idtype: int, _pid: int, _options: int) -> None:
    if waitid_error:
      raise ChildProcessError('already exited')

  executed: dict[int, bool] = {}
  handlers: dict[int, Callable[[int, object], None]] = {}
  with monkeypatch.context() as mp:
    _install_single_thread_runtime(
      mp,
      wall_ns=itertools.repeat(5_000),
      mono_s=itertools.repeat(10.0),
      installed_handlers=handlers,
      waitid_fn=dry_waitid,
    )
    mp.setattr(
      telemetry_ci.subprocess,
      'Popen',
      lambda *_a, **_kw: SimpleNamespace(
        pid=905, wait=lambda timeout=None: 0
      ),
    )
    previous_trace = sys.gettrace()

    def record_trace(frame: object, event: str, _arg: object) -> object:
      code = getattr(frame, 'f_code', None)
      if (
        event == 'line'
        and getattr(code, 'co_filename', None) == module_file
        and handlers.get(signal.SIGTERM) is not None
      ):
        lineno = getattr(frame, 'f_lineno', None)
        if isinstance(lineno, int):
          executed.setdefault(lineno, True)
      return record_trace

    sys.settrace(record_trace)
    try:
      assert run_uninstrumented(['0', 'check']) == 0
    finally:
      sys.settrace(previous_trace)

    def run_with_signal_at(target_lineno: int) -> int:
      handlers.clear()
      fired = False
      saved_trace = sys.gettrace()

      def sweep_trace(frame: object, event: str, _arg: object) -> object:
        nonlocal fired
        code = getattr(frame, 'f_code', None)
        if (
          not fired
          and event == 'line'
          and getattr(code, 'co_filename', None) == module_file
          and getattr(frame, 'f_lineno', None) == target_lineno
        ):
          handler = handlers.get(signal.SIGTERM)
          if handler is not None:
            fired = True
            handler(signal.SIGTERM, None)
        return sweep_trace

      sys.settrace(sweep_trace)
      try:
        return run_uninstrumented(['0', 'check'])
      finally:
        sys.settrace(saved_trace)

    outcomes = [run_with_signal_at(lineno) for lineno in executed]
  assert (
    outcomes[0],
    outcomes[-1],
    outcomes == sorted(outcomes, reverse=True),
    set(outcomes),
  ) == (143, 0, True, {0, 143})


def test_main_forwards_parsed_options(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  captured: list[tuple[Path, RunIdentity, tuple[str, ...]]] = []

  def fake_run(
    database: Path, identity: RunIdentity, command: Sequence[str]
  ) -> int:
    captured.append((database, identity, tuple(command)))
    return 0

  monkeypatch.setattr(telemetry_ci, 'run_instrumented', fake_run)
  code = main(
    [
      '--database',
      'out/run.sqlite3',
      '--build-id',
      'b7',
      '--job-id',
      'j8',
      '--revision',
      'rev9',
      '--',
      '0',
      'check',
    ]
  )
  assert code == 0
  assert captured == [
    (
      Path('out/run.sqlite3'),
      RunIdentity('b7', 'j8', 'rev9'),
      ('0', 'check'),
    )
  ]
