import os
import queue
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path

import pytest

from zero import ci_telemetry
from zero.ci_telemetry import append_pytest_plugin, read_arguments
from zero.telemetry import (
  ProcessCounters,
  ProcessCounterState,
  ProcessObservation,
  ResourceSample,
  RunIdentity,
  connect_database,
  initialize_database,
  observe_process_session,
  parse_process_io,
  parse_process_stat,
  record_incomplete_test_results,
  record_resource_sample,
  record_run_event,
  record_test_result,
  record_test_start,
  resource_sample_between,
)


def process_stat_line(
  pid: int,
  session_id: int,
  start_time_ticks: int,
  user_ticks: int,
  system_ticks: int,
  rss_pages: int,
) -> str:
  fields = ['S'] + ['0'] * 21
  fields[3] = str(session_id)
  fields[11] = str(user_ticks)
  fields[12] = str(system_ticks)
  fields[19] = str(start_time_ticks)
  fields[21] = str(rss_pages)
  return f'{pid} (pytest worker (gw0)) {" ".join(fields)}'


def write_process(
  proc_root: Path,
  pid: int,
  session_id: int,
  start_time_ticks: int,
  user_ticks: int,
  system_ticks: int,
  rss_pages: int,
  read_bytes: int,
  write_bytes: int,
) -> None:
  process = proc_root / str(pid)
  process.mkdir(parents=True, exist_ok=True)
  (process / 'stat').write_text(
    process_stat_line(
      pid,
      session_id,
      start_time_ticks,
      user_ticks,
      system_ticks,
      rss_pages,
    ),
    encoding='utf-8',
  )
  (process / 'io').write_text(
    f'read_bytes: {read_bytes}\nwrite_bytes: {write_bytes}\n',
    encoding='utf-8',
  )


def wrapper_command(database: Path, command: Sequence[str]) -> list[str]:
  return [
    sys.executable,
    '-m',
    'zero.ci_telemetry',
    '--database',
    str(database),
    '--build-id',
    'fixture-build',
    '--job-id',
    'fixture-job',
    '--revision',
    'fixture-revision',
    '--',
    *command,
  ]


def test_run_database_records_identity_tests_samples_and_rejects_rewrites(
  tmp_path: Path,
) -> None:
  database = tmp_path / 'test-results.sqlite3'
  identity = RunIdentity('build-1', 'job-2', 'revision-3')
  initialize_database(database, identity, 10, '3.13.9')
  connection = connect_database(database)

  record_run_event(connection, identity, 'check-started', 10)
  start_event_id = record_test_start(
    connection, identity, 'zero', 'test_main.py::test_check', 'gw0', 20
  )
  record_test_result(
    connection,
    identity,
    start_event_id,
    'zero',
    'test_main.py::test_check',
    'gw0',
    'passed',
    20,
    30,
    9,
  )
  record_resource_sample(
    connection,
    identity,
    ResourceSample(40, 10, 1.5, 4096, 100.0, 200.0),
  )
  record_resource_sample(
    connection,
    identity,
    ResourceSample(50, 10, 0.0, 0, None, None),
  )
  record_run_event(connection, identity, 'check-finished', 50, 0)

  actual = connection.execute(
    """
    SELECT run_id, source_revision, suite, nodeid, worker_id, outcome,
           started_at_ns, ended_at_ns, duration_ns
    FROM test_result
    """
  ).fetchall()
  assert actual == [
    (
      'build-1:job-2',
      'revision-3',
      'zero',
      'test_main.py::test_check',
      'gw0',
      'passed',
      20,
      30,
      9,
    )
  ]
  assert connection.execute(
    'SELECT cpu_cores, memory_rss_bytes, read_bytes_per_second, '
    'write_bytes_per_second FROM resource_sample ORDER BY sampled_at_ns'
  ).fetchall() == [
    (1.5, 4096, 100.0, 200.0),
    (0.0, 0, None, None),
  ]
  assert connection.execute(
    'SELECT source_revision, nodeid FROM test_result '
    'WHERE source_revision = ? AND nodeid = ?',
    ('revision-3', 'test_main.py::test_check'),
  ).fetchall() == [('revision-3', 'test_main.py::test_check')]
  with pytest.raises(sqlite3.IntegrityError, match='append-only'):
    connection.execute("UPDATE test_result SET outcome = 'failed'")
  connection.rollback()
  with pytest.raises(sqlite3.IntegrityError, match='append-only'):
    connection.execute('UPDATE test_started SET nodeid = "changed"')
  connection.rollback()
  with pytest.raises(sqlite3.IntegrityError, match='identity'):
    connection.execute(
      """
      INSERT INTO resource_sample
        (run_id, source_revision, sampled_at_ns, interval_ns, cpu_cores,
         memory_rss_bytes, read_bytes_per_second, write_bytes_per_second)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      """,
      ('build-1:job-2', 'other-revision', 60, 10, 0.0, 0, 0.0, 0.0),
    )
  connection.rollback()
  connection.close()


def test_incomplete_test_start_does_not_invent_an_outcome_or_end_time(
  tmp_path: Path,
) -> None:
  database = tmp_path / 'test-results.sqlite3'
  identity = RunIdentity('build', 'job', 'revision')
  initialize_database(database, identity, 10, '3.13.9')
  connection = connect_database(database)
  record_test_start(
    connection,
    identity,
    'zero',
    'test_crash.py::test_worker_crash',
    'gw0',
    20,
  )

  record_incomplete_test_results(connection, identity, 30)

  assert connection.execute(
    'SELECT suite, nodeid, worker_id, outcome, started_at_ns, '
    'ended_at_ns, duration_ns, recovered_at_ns FROM test_result'
  ).fetchall() == [
    (
      'zero',
      'test_crash.py::test_worker_crash',
      'gw0',
      'incomplete',
      20,
      None,
      None,
      30,
    )
  ]
  assert connection.execute(
    'SELECT count(*) FROM test_result'
  ).fetchone() == (1,)
  bad_start_event_id = record_test_start(
    connection,
    identity,
    'zero',
    'test_crash.py::test_invalid_incomplete_timing',
    'gw1',
    40,
  )
  with pytest.raises(
    sqlite3.IntegrityError, match='CHECK constraint failed'
  ):
    record_test_result(
      connection,
      identity,
      bad_start_event_id,
      'zero',
      'test_crash.py::test_invalid_incomplete_timing',
      'gw1',
      'incomplete',
      40,
      50,
      10,
    )
  connection.rollback()
  assert connection.execute(
    'SELECT count(*) FROM test_result WHERE start_event_id = ?',
    (bad_start_event_id,),
  ).fetchone() == (0,)
  connection.close()


def test_process_stat_parses_command_and_counters() -> None:
  line = process_stat_line(99, 7, 12, 30, 4, 5)

  process = parse_process_stat(99, line, 4096)

  assert process is not None
  assert process.session_id == 7
  assert process.start_time_ticks == 12
  assert process.counters == ProcessCounters(cpu_ticks=34)
  assert process.memory_rss_bytes == 5 * 4096


def test_process_io_requires_both_valid_counters() -> None:
  assert parse_process_io(
    'read_bytes: 1\nwrite_bytes: 2\n'
  ) == ProcessCounters(
    read_bytes=1,
    write_bytes=2,
  )
  assert parse_process_io('read_bytes: 1\n') is None
  assert parse_process_io('read_bytes: invalid\nwrite_bytes: 2\n') is None


def test_resource_samples_track_run_processes_and_correlate_with_test_time(
  tmp_path: Path,
) -> None:
  write_process(tmp_path, 123, 42, 1, 10, 5, 4, 100, 200)
  write_process(tmp_path, 124, 7, 1, 100, 50, 40, 1000, 2000)
  state, first = observe_process_session(
    tmp_path,
    42,
    4096,
    ProcessCounterState({}, ProcessCounters()),
    1_000,
    1,
  )

  write_process(tmp_path, 123, 42, 1, 30, 10, 5, 600, 1000)
  write_process(tmp_path, 125, 42, 1, 4, 1, 2, 50, 100)
  state, second = observe_process_session(
    tmp_path, 42, 4096, state, 2_000, 2_000_000_001
  )
  first_interval = resource_sample_between(first, second, 100)

  assert first_interval == ResourceSample(
    2_000,
    2_000_000_000,
    0.15,
    7 * 4096,
    275.0,
    450.0,
  )

  (tmp_path / '123').rename(tmp_path / 'exited-process')
  write_process(tmp_path, 125, 42, 1, 20, 0, 2, 150, 300)
  _, third = observe_process_session(
    tmp_path, 42, 4096, state, 3_000, 4_000_000_001
  )
  second_interval = resource_sample_between(second, third, 100)

  assert second_interval == ResourceSample(
    3_000,
    2_000_000_000,
    0.075,
    2 * 4096,
    50.0,
    100.0,
  )


def test_missing_process_io_produces_null_rates_for_the_rest_of_the_run(
  tmp_path: Path,
) -> None:
  write_process(tmp_path, 123, 42, 1, 10, 5, 4, 100, 200)
  (tmp_path / '123' / 'io').unlink()
  state, first = observe_process_session(
    tmp_path,
    42,
    4096,
    ProcessCounterState({}, ProcessCounters()),
    1_000,
    1,
  )

  write_process(tmp_path, 123, 42, 1, 30, 10, 5, 600, 1000)
  state, second = observe_process_session(
    tmp_path, 42, 4096, state, 2_000, 2_000_000_001
  )
  first_interval = resource_sample_between(first, second, 100)

  assert first_interval == ResourceSample(
    2_000,
    2_000_000_000,
    0.125,
    5 * 4096,
    None,
    None,
  )
  assert not state.io_counters_available

  _, third = observe_process_session(
    tmp_path, 42, 4096, state, 3_000, 4_000_000_001
  )
  second_interval = resource_sample_between(second, third, 100)
  assert second_interval == ResourceSample(
    3_000,
    2_000_000_000,
    0.0,
    5 * 4096,
    None,
    None,
  )


def test_invalid_process_io_encoding_does_not_stop_resource_sampling(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  database = tmp_path / 'telemetry.sqlite3'
  identity = RunIdentity('build', 'job', 'revision')
  initialize_database(database, identity, 10, '3.13.9')
  write_process(tmp_path, 123, 42, 1, 10, 5, 4, 100, 200)
  (tmp_path / '123' / 'io').write_bytes(b'\xff\n')
  stop = threading.Event()
  observation_count = 0
  observe = ci_telemetry.observe_process_session

  def observe_and_stop_after_first(
    proc_root: Path,
    session_id: int,
    page_size: int,
    state: ProcessCounterState,
    wall_time_ns: int,
    monotonic_ns: int,
  ) -> tuple[ProcessCounterState, ProcessObservation]:
    nonlocal observation_count
    result = observe(
      proc_root,
      session_id,
      page_size,
      state,
      wall_time_ns,
      monotonic_ns,
    )
    observation_count += 1
    if observation_count == 1:
      stop.set()
    return result

  monkeypatch.setattr(
    ci_telemetry, 'observe_process_session', observe_and_stop_after_first
  )
  monkeypatch.setattr(ci_telemetry, 'SAMPLE_INTERVAL_SECONDS', 0.001)
  monkeypatch.setattr(
    ci_telemetry.time, 'time_ns', iter((100, 200)).__next__
  )
  monkeypatch.setattr(
    ci_telemetry.time,
    'monotonic_ns',
    iter((1, 1_000_000_001)).__next__,
  )
  errors: queue.SimpleQueue[str] = queue.SimpleQueue()

  ci_telemetry.sample_resources(
    database, identity, 42, stop, errors, tmp_path
  )

  connection = sqlite3.connect(database)
  assert connection.execute(
    'SELECT cpu_cores, memory_rss_bytes, read_bytes_per_second, '
    'write_bytes_per_second FROM resource_sample'
  ).fetchall() == [(0.0, 4 * 4096, None, None)]
  connection.close()
  assert observation_count == 2
  assert errors.empty()


def test_runner_options_keep_a_command_after_the_separator() -> None:
  options = read_arguments(
    [
      '--database',
      '.tmp/results.sqlite3',
      '--build-id',
      'build',
      '--job-id',
      'job',
      '--revision',
      'revision',
      '--',
      '0',
      'check',
    ]
  )

  assert options.command == ('0', 'check')


def test_plugin_environment_addition_is_idempotent() -> None:
  environment = {'PYTEST_PLUGINS': 'existing.plugin'}

  append_pytest_plugin(environment)
  append_pytest_plugin(environment)

  assert environment == {
    'PYTEST_PLUGINS': 'existing.plugin,zero.pytest_telemetry'
  }


def test_telemetry_setup_failure_preserves_the_check_exit_code(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  calls: list[tuple[str, ...]] = []

  def fail_initialization(
    _database: Path,
    _identity: RunIdentity,
    _started_at_ns: int,
    _python_version: str,
  ) -> None:
    raise sqlite3.OperationalError('fixture storage failure')

  def run_original(command: Sequence[str]) -> int:
    calls.append(tuple(command))
    return 17

  monkeypatch.setattr(
    ci_telemetry, 'initialize_database', fail_initialization
  )
  monkeypatch.setattr(ci_telemetry, 'run_uninstrumented', run_original)
  identity = RunIdentity('build', 'job', 'revision')

  result = ci_telemetry.run_instrumented(
    tmp_path / 'telemetry.sqlite3', identity, ['0', 'check']
  )

  assert result == 17
  assert calls == [('0', 'check')]


def test_worker_crash_is_recorded_as_a_failed_test(
  tmp_path: Path,
) -> None:
  database = tmp_path / 'worker-crash.sqlite3'
  test_file = tmp_path / 'test_worker_crash.py'
  test_file.write_text(
    'import os\n\ndef test_worker_crash():\n  os._exit(23)\n',
    encoding='utf-8',
  )

  result = subprocess.run(
    wrapper_command(
      database,
      [
        sys.executable,
        '-m',
        'pytest',
        '-n',
        '1',
        '--max-worker-restart=0',
        '-q',
        str(test_file),
      ],
    ),
    check=False,
    capture_output=True,
    text=True,
    timeout=15,
  )

  assert result.returncode != 0
  connection = sqlite3.connect(database)
  rows = connection.execute(
    'SELECT nodeid, outcome, ended_at_ns, duration_ns, recovered_at_ns '
    'FROM test_result'
  ).fetchall()
  assert len(rows) == 1
  assert rows[0][0].endswith('test_worker_crash.py::test_worker_crash')
  assert rows[0][1] == 'failed'
  assert rows[0][2:4] == (None, None)
  assert rows[0][4] is not None
  connection.close()


def test_sigterm_stops_the_check_process_group(
  tmp_path: Path,
) -> None:
  database = tmp_path / 'signal.sqlite3'
  started = tmp_path / 'child-started'
  survived = tmp_path / 'child-survived'
  child_code = (
    'import sys, time; from pathlib import Path; time.sleep(1); '
    'Path(sys.argv[1]).touch()'
  )
  check_code = (
    'import subprocess, sys, time; from pathlib import Path; '
    'subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2]]); '
    'Path(sys.argv[3]).touch(); time.sleep(30)'
  )
  wrapper = subprocess.Popen(
    wrapper_command(
      database,
      [
        sys.executable,
        '-c',
        check_code,
        child_code,
        str(survived),
        str(started),
      ],
    )
  )
  try:
    deadline = time.monotonic() + 5
    while not started.exists() and wrapper.poll() is None:
      if time.monotonic() >= deadline:
        raise AssertionError('check child did not start')
      time.sleep(0.01)
    assert started.is_file()
    wrapper.send_signal(signal.SIGTERM)
    assert wrapper.wait(timeout=10) == 128 + signal.SIGTERM
    time.sleep(1.1)
    assert not survived.exists()
  finally:
    if wrapper.poll() is None:
      wrapper.send_signal(signal.SIGTERM)
      try:
        wrapper.wait(timeout=5)
      except subprocess.TimeoutExpired:
        wrapper.kill()
        wrapper.wait()

  connection = sqlite3.connect(database)
  assert connection.execute(
    'SELECT event, exit_code FROM run_event ORDER BY event_id'
  ).fetchall() == [('check-started', None), ('check-finished', 143)]
  connection.close()


def test_sigterm_escalates_for_an_unresponsive_check_group(
  monkeypatch: pytest.MonkeyPatch,
  tmp_path: Path,
) -> None:
  monkeypatch.setattr(ci_telemetry, 'SIGNAL_GRACE_SECONDS', 0.1)
  database = tmp_path / 'unresponsive.sqlite3'
  started = tmp_path / 'child-started'
  survived = tmp_path / 'child-survived'
  child_code = (
    'import sys, time; from pathlib import Path; time.sleep(0.4); '
    'Path(sys.argv[1]).touch()'
  )
  check_code = (
    'import signal, subprocess, sys, time; from pathlib import Path; '
    'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
    'subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2]]); '
    'Path(sys.argv[3]).touch(); time.sleep(30)'
  )

  def interrupt_after_child_start() -> None:
    deadline = time.monotonic() + 5
    while not started.exists() and time.monotonic() < deadline:
      time.sleep(0.01)
    if started.exists():
      os.kill(os.getpid(), signal.SIGTERM)

  sender = threading.Thread(
    target=interrupt_after_child_start, daemon=True
  )
  sender.start()
  result = ci_telemetry.run_instrumented(
    database,
    RunIdentity('build', 'job', 'revision'),
    [
      sys.executable,
      '-c',
      check_code,
      child_code,
      str(survived),
      str(started),
    ],
  )
  sender.join(timeout=5)

  assert result == 128 + signal.SIGTERM
  assert not sender.is_alive()
  time.sleep(0.5)
  assert not survived.exists()
