"""Run one command while recording its tests and process resources."""

import argparse
import os
import queue
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from zero.telemetry import (
  ProcessCounters,
  ProcessCounterState,
  ProcessObservation,
  RunIdentity,
  connect_database,
  finalize_database,
  initialize_database,
  observe_process_session,
  record_incomplete_test_results,
  record_resource_sample,
  record_run_event,
  resource_sample_between,
)

SAMPLE_INTERVAL_SECONDS = 0.5
PROCESS_WAIT_POLL_SECONDS = 0.1
SIGNAL_GRACE_SECONDS = 5.0


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
  parser = argparse.ArgumentParser()
  parser.add_argument('--database', type=Path, required=True)
  parser.add_argument('--build-id', required=True)
  parser.add_argument('--job-id', required=True)
  parser.add_argument('--revision', required=True)
  parser.add_argument('command', nargs=argparse.REMAINDER)
  parsed = parser.parse_args(arguments)
  database: object = parsed.database
  build_id: object = parsed.build_id
  job_id: object = parsed.job_id
  revision: object = parsed.revision
  command: object = parsed.command
  if not isinstance(database, Path):
    parser.error('--database must be a path')
  if not isinstance(build_id, str) or not build_id:
    parser.error('--build-id must not be empty')
  if not isinstance(job_id, str) or not job_id:
    parser.error('--job-id must not be empty')
  if not isinstance(revision, str) or not revision:
    parser.error('--revision must not be empty')
  if not isinstance(command, list) or not all(
    isinstance(argument, str) for argument in command
  ):
    parser.error('command arguments must be text')
  if command and command[0] == '--':
    command = command[1:]
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
  if 'zero.pytest_telemetry' not in plugins:
    plugins.append('zero.pytest_telemetry')
  environment['PYTEST_PLUGINS'] = ','.join(plugins)


def sample_resources(
  database: Path,
  identity: RunIdentity,
  session_id: int,
  stop: threading.Event,
  errors: queue.SimpleQueue[str],
  proc_root: Path = Path('/proc'),
) -> None:
  connection: sqlite3.Connection | None = None
  try:
    connection = connect_database(database)
    page_size = int(os.sysconf('SC_PAGE_SIZE'))
    clock_ticks = int(os.sysconf('SC_CLK_TCK'))
    state = ProcessCounterState(active={}, retired=ProcessCounters())
    previous: ProcessObservation | None = None
    while not stop.wait(SAMPLE_INTERVAL_SECONDS):
      state, current = observe_process_session(
        proc_root,
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
      proc_root,
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
  except (OSError, sqlite3.Error, ValueError) as error:
    errors.put(str(error))
  finally:
    if connection is not None:
      connection.close()


def run_uninstrumented(command: Sequence[str]) -> int:
  try:
    result = subprocess.run(command, check=False)
  except OSError as error:
    print(f'Unable to run check command: {error}', file=sys.stderr)
    return 127
  return (
    128 - result.returncode if result.returncode < 0 else result.returncode
  )


def signal_check_process_group(process_id: int, signum: int) -> None:
  try:
    os.killpg(process_id, signum)
  except ProcessLookupError:
    return
  except OSError as error:
    print(
      f'Unable to signal check process group: {error}', file=sys.stderr
    )


def run_instrumented(
  database: Path, identity: RunIdentity, command: Sequence[str]
) -> int:
  started_at_ns = time.time_ns()
  try:
    import zero.pytest_telemetry  # noqa: F401

    initialize_database(
      database, identity, started_at_ns, sys.version.split()[0]
    )
  except (ImportError, OSError, sqlite3.Error) as error:
    print(f'CI test telemetry unavailable: {error}', file=sys.stderr)
    return run_uninstrumented(command)

  try:
    connection = connect_database(database)
    try:
      record_run_event(
        connection, identity, 'check-started', started_at_ns
      )
    finally:
      connection.close()
  except sqlite3.Error as error:
    print(f'CI test telemetry unavailable: {error}', file=sys.stderr)
    return run_uninstrumented(command)

  environment = os.environ.copy()
  environment['PENTAGRAM_TEST_TELEMETRY_DB'] = str(database.resolve())
  environment['PENTAGRAM_TEST_TELEMETRY_BUILD_ID'] = identity.build_id
  environment['PENTAGRAM_TEST_TELEMETRY_JOB_ID'] = identity.job_id
  environment['PENTAGRAM_TEST_TELEMETRY_REVISION'] = (
    identity.source_revision
  )
  environment.pop('PYTEST_XDIST_WORKER', None)
  append_pytest_plugin(environment)

  received_signal: int | None = None
  received_at_monotonic: float | None = None
  process_id: int | None = None

  def forward_signal(signum: int, _frame: object) -> None:
    nonlocal received_signal, received_at_monotonic
    if received_signal is None:
      received_signal = signum
      received_at_monotonic = time.monotonic()
    if process_id is not None:
      signal_check_process_group(process_id, signum)

  previous_handlers = {
    signal.SIGINT: signal.signal(signal.SIGINT, forward_signal),
    signal.SIGTERM: signal.signal(signal.SIGTERM, forward_signal),
  }
  stop: threading.Event | None = None
  sampler: threading.Thread | None = None
  errors: queue.SimpleQueue[str] = queue.SimpleQueue()
  try:
    try:
      process = subprocess.Popen(
        command, env=environment, start_new_session=True
      )
    except OSError as error:
      print(f'Unable to run check command: {error}', file=sys.stderr)
      return_code = 127
    else:
      process_id = process.pid
      if received_signal is not None:
        signal_check_process_group(process_id, received_signal)
      stop = threading.Event()
      sampler = threading.Thread(
        target=sample_resources,
        args=(database, identity, process_id, stop, errors),
        daemon=True,
      )
      try:
        sampler.start()
      except (OSError, RuntimeError) as error:
        print(
          f'CI resource sampling unavailable: {error}', file=sys.stderr
        )
        sampler = None
      while True:
        try:
          return_code = process.wait(timeout=PROCESS_WAIT_POLL_SECONDS)
        except subprocess.TimeoutExpired:
          if (
            received_at_monotonic is None
            or time.monotonic() - received_at_monotonic
            < SIGNAL_GRACE_SECONDS
          ):
            continue
          signal_check_process_group(process_id, signal.SIGKILL)
          return_code = process.wait()
          break
        except KeyboardInterrupt:
          if received_signal is None:
            received_signal = signal.SIGINT
            received_at_monotonic = time.monotonic()
          signal_check_process_group(process_id, signal.SIGINT)
        else:
          break
      if received_signal is not None:
        signal_check_process_group(process_id, signal.SIGKILL)
        return_code = 128 + received_signal
      elif return_code < 0:
        return_code = 128 - return_code
  finally:
    if stop is not None:
      stop.set()
    if sampler is not None:
      sampler.join()
    for signum, handler in previous_handlers.items():
      signal.signal(signum, handler)

  while not errors.empty():
    print(
      f'CI resource sampling unavailable: {errors.get()}',
      file=sys.stderr,
    )

  occurred_at_ns = time.time_ns()
  try:
    connection = connect_database(database)
    try:
      try:
        record_incomplete_test_results(
          connection, identity, occurred_at_ns
        )
      except sqlite3.Error as error:
        connection.rollback()
        print(
          f'CI incomplete-test recovery unavailable: {error}',
          file=sys.stderr,
        )
      record_run_event(
        connection,
        identity,
        'check-finished',
        occurred_at_ns,
        exit_code=return_code,
      )
    finally:
      connection.close()
    finalize_database(database)
    with database.with_name(f'{database.name}.complete').open('xb'):
      pass
  except (OSError, sqlite3.Error) as error:
    print(f'CI telemetry finalization failed: {error}', file=sys.stderr)
  return return_code


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
