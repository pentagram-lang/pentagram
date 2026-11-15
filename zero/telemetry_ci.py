"""Run one command while recording its tests and process resources."""

import argparse
import importlib
import os
import queue
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from zero.telemetry import (
  CheckFinished,
  CheckStarted,
  ProcessCounters,
  ProcessCounterState,
  ProcessObservation,
  RunIdentity,
  connect_database,
  finalize_database,
  initialize_database,
  observe_process_session,
  parse_database_path,
  record_incomplete_test_results,
  record_resource_sample,
  record_run_event,
  resource_sample_between,
  validate_database_path,
)

SAMPLE_INTERVAL_SECONDS = 0.5
SIGNAL_GRACE_SECONDS = 5.0


class _SignalInterrupt(BaseException):
  pass


@dataclass(frozen=True, slots=True)
class _ReceivedSignal:
  signum: int
  at_monotonic: float


@dataclass(slots=True)
class _SupervisionState:
  received: _ReceivedSignal | None = None
  process_id: int | None = None
  child_reaped: bool = False
  waiting_for_exit: bool = False


def _close_quietly(connection: sqlite3.Connection | None) -> None:
  if connection is None:
    return
  try:
    connection.close()
  except sqlite3.Error:
    pass


def _run_supervised_command(
  command: Sequence[str],
  *,
  environment: Mapping[str, str] | None = None,
  on_started: Callable[[int], Callable[[], None]] | None = None,
  on_finished: Callable[[int], None] | None = None,
) -> int:
  state = _SupervisionState()

  def forward_signal(signum: int, _frame: object) -> None:
    is_first_pre_reap = not state.child_reaped and state.received is None
    if is_first_pre_reap:
      state.received = _ReceivedSignal(signum, time.monotonic())
    if state.process_id is not None:
      signal_check_process_group(state.process_id, signum)
    if is_first_pre_reap and state.waiting_for_exit:
      state.waiting_for_exit = False
      raise _SignalInterrupt

  previous_handlers = (
    {
      signum: signal.signal(signum, forward_signal)
      for signum in (signal.SIGINT, signal.SIGTERM)
      if signal.getsignal(signum) not in (None, signal.SIG_IGN)
    }
    if threading.current_thread() is threading.main_thread()
    else {}
  )
  stop_background: Callable[[], None] | None = None
  try:
    try:
      try:
        process = subprocess.Popen(
          command, env=environment, start_new_session=True
        )
      except OSError as error:
        print(f'Unable to run check command: {error}', file=sys.stderr)
        return_code = 127
      else:
        state.process_id = process.pid
        if state.received is not None:
          signal_check_process_group(
            state.process_id, state.received.signum
          )
        if on_started is not None:
          stop_background = on_started(state.process_id)
        try:
          try:
            state.waiting_for_exit = True
            if state.received is None:
              os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOWAIT)
          except ChildProcessError:
            pass
          finally:
            state.waiting_for_exit = False
        except _SignalInterrupt:
          pass
        if state.received is None:
          return_code = process.wait()
        else:
          grace_remaining = max(
            0.0,
            SIGNAL_GRACE_SECONDS
            - (time.monotonic() - state.received.at_monotonic),
          )
          try:
            return_code = process.wait(timeout=grace_remaining)
          except subprocess.TimeoutExpired:
            signal_check_process_group(process.pid, signal.SIGKILL)
            return_code = process.wait()
        state.process_id = None
        state.child_reaped = True
        if state.received is not None:
          return_code = 128 + state.received.signum
        elif return_code < 0:
          return_code = 128 - return_code
    finally:
      if stop_background is not None:
        stop_background()

    if on_finished is not None:
      on_finished(return_code)
    return return_code
  finally:
    for signum, handler in previous_handlers.items():
      if handler is not None:
        signal.signal(signum, handler)


def run_uninstrumented(command: Sequence[str]) -> int:
  return _run_supervised_command(command)


def signal_check_process_group(process_id: int, signum: int) -> None:
  try:
    os.killpg(process_id, signum)
  except ProcessLookupError:
    return
  except OSError as error:
    print(
      f'Unable to signal check process group: {error}', file=sys.stderr
    )


def write_completion_marker(database: Path) -> None:
  validate_database_path(database)
  with database.with_name(f'{database.name}.complete').open('xb'):
    pass


@dataclass(frozen=True, slots=True)
class TelemetryOptions:
  database: Path
  build_id: str
  job_id: str
  revision: str
  command: tuple[str, ...]


def read_arguments(
  arguments: Sequence[str] | None = None,
) -> TelemetryOptions:
  parser = argparse.ArgumentParser(
    prog='python -m zero.telemetry_ci',
    usage=(
      'python -m zero.telemetry_ci [-h] --database DATABASE '
      '--build-id BUILD_ID --job-id JOB_ID --revision REVISION -- ...'
    ),
  )
  parser.add_argument('--database', required=True)
  parser.add_argument('--build-id', required=True)
  parser.add_argument('--job-id', required=True)
  parser.add_argument('--revision', required=True)

  raw_args = list(sys.argv[1:] if arguments is None else arguments)
  if '--' in raw_args:
    separator = raw_args.index('--')
    option_args = raw_args[:separator]
    command = raw_args[separator + 1 :]
    parsed = parser.parse_args(option_args)
  else:
    parsed = parser.parse_args(raw_args)
    command = []

  raw_database: str = parsed.database
  build_id: str = parsed.build_id
  job_id: str = parsed.job_id
  revision: str = parsed.revision
  try:
    database = parse_database_path(raw_database)
  except ValueError:
    parser.error('--database must be a valid filesystem path')
  if not build_id:
    parser.error('--build-id must not be empty')
  if not job_id:
    parser.error('--job-id must not be empty')
  if not revision:
    parser.error('--revision must not be empty')
  if not command:
    parser.error('a command must follow --')
  return TelemetryOptions(
    database=database,
    build_id=build_id,
    job_id=job_id,
    revision=revision,
    command=tuple(command),
  )


def append_pytest_plugin(environment: dict[str, str]) -> None:
  existing = environment.get('PYTEST_PLUGINS', '')
  plugins = [plugin for plugin in existing.split(',') if plugin]
  if 'zero.telemetry_plugin' not in plugins:
    plugins.append('zero.telemetry_plugin')
  environment['PYTEST_PLUGINS'] = ','.join(plugins)


def sample_resources(
  database: Path,
  identity: RunIdentity,
  session_id: int,
  stop: threading.Event,
  errors: queue.SimpleQueue[str],
) -> None:
  connection: sqlite3.Connection | None = None
  try:
    connection = connect_database(database)
    page_size = int(os.sysconf('SC_PAGE_SIZE'))
    clock_ticks = int(os.sysconf('SC_CLK_TCK'))
    proc = Path('/proc')
    state = ProcessCounterState(active={}, retired=ProcessCounters())
    previous: ProcessObservation | None = None
    while not stop.wait(SAMPLE_INTERVAL_SECONDS):
      state, current = observe_process_session(
        proc,
        session_id,
        page_size,
        state,
        time.time_ns(),
        time.monotonic_ns(),
      )
      sample = (
        resource_sample_between(previous, current, clock_ticks)
        if previous is not None
        else None
      )
      if sample is not None:
        record_resource_sample(connection, identity, sample)
      previous = current

    _state, current = observe_process_session(
      proc,
      session_id,
      page_size,
      state,
      time.time_ns(),
      time.monotonic_ns(),
    )
    sample = (
      resource_sample_between(previous, current, clock_ticks)
      if previous is not None
      else None
    )
    if sample is not None:
      record_resource_sample(connection, identity, sample)
    to_close = connection
    connection = None
    to_close.close()
  except (OSError, sqlite3.Error, ValueError) as error:
    errors.put(str(error))
  finally:
    _close_quietly(connection)


def _instrumented_environment(
  database: Path, identity: RunIdentity
) -> dict[str, str]:
  environment = os.environ.copy()
  environment['PENTAGRAM_TEST_TELEMETRY_DB'] = str(database)
  environment['PENTAGRAM_TEST_TELEMETRY_BUILD_ID'] = identity.build_id
  environment['PENTAGRAM_TEST_TELEMETRY_JOB_ID'] = identity.job_id
  environment['PENTAGRAM_TEST_TELEMETRY_REVISION'] = (
    identity.source_revision
  )
  environment.pop('PYTEST_XDIST_WORKER', None)
  append_pytest_plugin(environment)
  return environment


def _finalize_instrumented_run(
  database: Path,
  identity: RunIdentity,
  occurred_at_ns: int,
  return_code: int,
) -> None:
  connection: sqlite3.Connection | None = None
  try:
    connection = connect_database(database)
    try:
      record_incomplete_test_results(connection, identity, occurred_at_ns)
    except sqlite3.Error as error:
      try:
        connection.rollback()
      except sqlite3.Error:
        pass
      print(
        f'CI incomplete-test recovery unavailable: {error}',
        file=sys.stderr,
      )
    record_run_event(
      connection,
      identity,
      CheckFinished(occurred_at_ns, return_code),
    )
    to_close = connection
    connection = None
    to_close.close()
    finalize_database(database)
    write_completion_marker(database)
  except (OSError, sqlite3.Error, ValueError) as error:
    print(f'CI telemetry finalization failed: {error}', file=sys.stderr)
  finally:
    _close_quietly(connection)


def run_instrumented(
  database: Path,
  identity: RunIdentity,
  command: Sequence[str],
) -> int:
  started_at_ns = time.time_ns()
  resolved_database: Path | None = None
  database_initialized = False
  setup_connection: sqlite3.Connection | None = None
  try:
    validate_database_path(database)
    resolved_database = validate_database_path(database.resolve())
    importlib.import_module('zero.telemetry_plugin')
    initialize_database(
      resolved_database, identity, started_at_ns, sys.version.split()[0]
    )
    database_initialized = True
    setup_connection = connect_database(resolved_database)
    record_run_event(
      setup_connection, identity, CheckStarted(started_at_ns)
    )
    to_close = setup_connection
    setup_connection = None
    to_close.close()
    environment = _instrumented_environment(resolved_database, identity)
  except (
    ImportError,
    OSError,
    sqlite3.Error,
    ValueError,
  ) as error:
    _close_quietly(setup_connection)
    if database_initialized and resolved_database is not None:
      for path in (
        resolved_database,
        resolved_database.with_name(f'{resolved_database.name}-wal'),
        resolved_database.with_name(f'{resolved_database.name}-shm'),
      ):
        try:
          path.unlink(missing_ok=True)
        except OSError:
          pass
    print(f'CI test telemetry unavailable: {error}', file=sys.stderr)
    return run_uninstrumented(command)

  errors: queue.SimpleQueue[str] = queue.SimpleQueue()

  def start_sampler(session_id: int) -> Callable[[], None]:
    stop = threading.Event()
    sampler: threading.Thread | None = threading.Thread(
      target=sample_resources,
      args=(resolved_database, identity, session_id, stop, errors),
      daemon=True,
    )
    try:
      sampler.start()
    except (OSError, RuntimeError) as error:
      print(f'CI resource sampling unavailable: {error}', file=sys.stderr)
      sampler = None

    def stop_sampler() -> None:
      stop.set()
      if sampler is not None:
        sampler.join()

    return stop_sampler

  def finish_run(return_code: int) -> None:
    while not errors.empty():
      print(
        f'CI resource sampling unavailable: {errors.get()}',
        file=sys.stderr,
      )
    _finalize_instrumented_run(
      resolved_database,
      identity,
      time.time_ns(),
      return_code,
    )

  return _run_supervised_command(
    command,
    environment=environment,
    on_started=start_sampler,
    on_finished=finish_run,
  )


def main(arguments: Sequence[str] | None = None) -> int:
  options = read_arguments(arguments)
  identity = RunIdentity(
    build_id=options.build_id,
    job_id=options.job_id,
    source_revision=options.revision,
  )
  return run_instrumented(options.database, identity, options.command)


if __name__ == '__main__':
  sys.exit(main())
