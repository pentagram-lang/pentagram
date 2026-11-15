"""Record pytest outcomes for CI test telemetry."""

import os
import sqlite3
import sys
import time
from collections.abc import Generator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pytest

from zero.telemetry import (
  CompletedTestOutcome,
  CompletedTestResult,
  RunIdentity,
  TestCase,
  connect_database,
  parse_database_path,
  record_test_failure_for_worker,
  record_test_result,
  record_test_start,
)


class _HookResult(Protocol):
  excinfo: object

  def get_result(self) -> object: ...


@dataclass(slots=True)
class _PluginState:
  connection: sqlite3.Connection
  identity: RunIdentity
  suite: str
  worker_id: str
  warned: bool = False


_STATE: pytest.StashKey[_PluginState] = pytest.StashKey()
_REPORTS: pytest.StashKey[list[pytest.TestReport]] = pytest.StashKey()


def suite_for_nodeid(nodeid: str, default_suite: str) -> str:
  file_path = nodeid.split('::', 1)[0]
  if '/' not in file_path:
    return default_suite
  leading = file_path.split('/', 1)[0]
  if not leading or leading == '.':
    return default_suite
  return leading


def pytest_configure(config: pytest.Config) -> None:
  database = os.environ.get('PENTAGRAM_TEST_TELEMETRY_DB')
  if database is None:
    return
  build_id = os.environ.get('PENTAGRAM_TEST_TELEMETRY_BUILD_ID')
  job_id = os.environ.get('PENTAGRAM_TEST_TELEMETRY_JOB_ID')
  revision = os.environ.get('PENTAGRAM_TEST_TELEMETRY_REVISION')
  if not build_id or not job_id or not revision:
    return

  connection: sqlite3.Connection | None = None
  try:
    connection = connect_database(parse_database_path(database))
    configured_suite = next(
      (
        Path(path).name
        for path in config.getini('testpaths')
        if Path(path).name
      ),
      None,
    )
    suite = (
      configured_suite
      if configured_suite is not None
      else config.rootpath.name
    )
    config.stash[_STATE] = _PluginState(
      connection=connection,
      identity=RunIdentity(build_id, job_id, revision),
      suite=suite,
      worker_id=os.environ.get('PYTEST_XDIST_WORKER', 'master'),
    )
    connection = None
  except (OSError, sqlite3.Error, ValueError) as error:
    if connection is not None:
      try:
        connection.close()
      except sqlite3.Error:
        pass
    print(
      f'CI test telemetry unavailable in pytest: {error}', file=sys.stderr
    )


def outcome_for_reports(
  reports: Sequence[pytest.TestReport],
) -> CompletedTestOutcome | None:
  if not any(report.when == 'teardown' for report in reports):
    return None
  if any(report.failed for report in reports):
    return 'failed'
  if any(
    report.outcome == 'passed'
    and getattr(report, 'wasxfail', None) is not None
    for report in reports
  ) and any(report.when == 'call' for report in reports):
    return 'xpassed'
  if any(
    report.outcome == 'skipped'
    and getattr(report, 'wasxfail', None) is not None
    for report in reports
  ):
    return 'xfailed'
  if any(report.skipped for report in reports):
    return 'skipped'
  if any(
    report.when == 'call' and report.outcome == 'passed'
    for report in reports
  ):
    return 'passed'
  return None


def _rollback_quietly(connection: sqlite3.Connection) -> None:
  try:
    connection.rollback()
  except sqlite3.Error:
    pass


def _warn_once(state: _PluginState, error: Exception) -> None:
  if state.warned:
    return
  print(
    f'CI test telemetry could not record a test: {error}', file=sys.stderr
  )
  state.warned = True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
  item: pytest.Item, call: object
) -> Generator[None, object]:
  del call
  result = yield
  reports = item.stash.get(_REPORTS, None)
  if reports is None:
    return
  report = cast(_HookResult, result).get_result()
  if isinstance(report, pytest.TestReport):
    reports.append(report)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(
  item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, object]:
  del nextitem
  state = item.config.stash.get(_STATE, None)
  if state is None:
    yield
    return

  test = TestCase(
    suite=suite_for_nodeid(item.nodeid, state.suite),
    nodeid=item.nodeid,
    worker_id=state.worker_id,
  )
  item.stash[_REPORTS] = []
  started_at_ns = time.time_ns()
  started_monotonic_ns = time.monotonic_ns()
  start_event_id: int | None = None
  try:
    start_event_id = record_test_start(
      state.connection, state.identity, test, started_at_ns
    )
  except (sqlite3.Error, OSError) as error:
    _rollback_quietly(state.connection)
    _warn_once(state, error)
  aborted = False
  try:
    hook_result = yield
    aborted = getattr(hook_result, 'excinfo', None) is not None
  finally:
    reports = item.stash.get(_REPORTS, [])
    if _REPORTS in item.stash:
      del item.stash[_REPORTS]
    ended_at_ns = time.time_ns()
    duration_ns = time.monotonic_ns() - started_monotonic_ns
    outcome = (
      outcome_for_reports(reports)
      if start_event_id is not None and not aborted
      else None
    )
    if start_event_id is not None and outcome is not None:
      try:
        record_test_result(
          state.connection,
          state.identity,
          CompletedTestResult(
            start_event_id=start_event_id,
            test=test,
            outcome=outcome,
            started_at_ns=started_at_ns,
            ended_at_ns=ended_at_ns,
            duration_ns=duration_ns,
          ),
        )
      except (sqlite3.Error, OSError) as error:
        _rollback_quietly(state.connection)
        _warn_once(state, error)


def _config_stash(owner: object) -> pytest.Stash | None:
  config = getattr(owner, 'config', None)
  stash = getattr(config, 'stash', None)
  return stash if isinstance(stash, pytest.Stash) else None


@pytest.hookimpl(optionalhook=True)
def pytest_handlecrashitem(
  crashitem: str,
  report: pytest.TestReport,
  sched: object,
) -> None:
  node = getattr(report, 'node', None)
  stash = _config_stash(node)
  if stash is None:
    stash = _config_stash(sched)
  if stash is None:
    return
  state = stash.get(_STATE, None)
  if state is None or state.worker_id != 'master':
    return
  workerinfo = getattr(node, 'workerinfo', None)
  worker_id = (
    workerinfo.get('id') if isinstance(workerinfo, dict) else None
  )
  if not isinstance(worker_id, str):
    return
  test = TestCase(
    suite=suite_for_nodeid(crashitem, state.suite),
    nodeid=crashitem,
    worker_id=worker_id,
  )
  try:
    record_test_failure_for_worker(
      state.connection, state.identity, test, time.time_ns()
    )
  except (sqlite3.Error, OSError) as error:
    _rollback_quietly(state.connection)
    _warn_once(state, error)


def pytest_unconfigure(config: pytest.Config) -> None:
  state = config.stash.get(_STATE, None)
  if state is not None:
    del config.stash[_STATE]
    try:
      state.connection.close()
    except sqlite3.Error as error:
      _warn_once(state, error)
