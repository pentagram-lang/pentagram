"""Record pytest outcomes for CI test telemetry."""

import os
import sqlite3
import sys
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import pytest

from zero.telemetry import (
  RunIdentity,
  TestOutcome,
  connect_database,
  record_test_failure_for_worker,
  record_test_result,
  record_test_start,
)


class HookResult(Protocol):
  def get_result(self) -> object: ...


@dataclass
class PluginState:
  connection: sqlite3.Connection
  identity: RunIdentity
  suite: str
  worker_id: str
  warned: bool = False


_STATE: pytest.StashKey[PluginState] = pytest.StashKey()
_REPORTS: pytest.StashKey[list[pytest.TestReport]] = pytest.StashKey()
_MASTER_STATE: PluginState | None = None


def pytest_configure(config: pytest.Config) -> None:
  global _MASTER_STATE
  database = os.environ.get('PENTAGRAM_TEST_TELEMETRY_DB')
  if database is None:
    return
  build_id = os.environ.get('PENTAGRAM_TEST_TELEMETRY_BUILD_ID')
  job_id = os.environ.get('PENTAGRAM_TEST_TELEMETRY_JOB_ID')
  revision = os.environ.get('PENTAGRAM_TEST_TELEMETRY_REVISION')
  if not build_id or not job_id or not revision:
    return

  try:
    connection = connect_database(Path(database))
    test_paths = config.getini('testpaths')
    suite = (
      Path(test_paths[0]).name if test_paths else config.rootpath.name
    )
    state = PluginState(
      connection=connection,
      identity=RunIdentity(build_id, job_id, revision),
      suite=suite,
      worker_id=os.environ.get('PYTEST_XDIST_WORKER', 'master'),
    )
    config.stash[_STATE] = state
    if 'PYTEST_XDIST_WORKER' not in os.environ:
      _MASTER_STATE = state
  except (OSError, sqlite3.Error) as error:
    print(
      f'CI test telemetry unavailable in pytest: {error}', file=sys.stderr
    )


def outcome_for_reports(reports: list[pytest.TestReport]) -> TestOutcome:
  if not reports:
    return 'failed'
  if any(report.failed for report in reports):
    return 'failed'
  if any(
    report.outcome == 'passed' and getattr(report, 'wasxfail', None)
    for report in reports
  ):
    return 'xpassed'
  if any(
    report.outcome == 'skipped' and getattr(report, 'wasxfail', None)
    for report in reports
  ):
    return 'xfailed'
  if any(report.skipped for report in reports):
    return 'skipped'
  return 'passed'


def warn_once(state: PluginState, error: Exception) -> None:
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
  result = yield
  reports = item.stash.get(_REPORTS, None)
  if reports is None:
    return
  report = cast(HookResult, result).get_result()
  if isinstance(report, pytest.TestReport):
    reports.append(report)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(
  item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, object]:
  state = item.config.stash.get(_STATE, None)
  if state is None:
    yield
    return

  item.stash[_REPORTS] = []
  started_at_ns = time.time_ns()
  started_monotonic_ns = time.monotonic_ns()
  start_event_id: int | None = None
  try:
    start_event_id = record_test_start(
      state.connection,
      state.identity,
      state.suite,
      item.nodeid,
      state.worker_id,
      started_at_ns,
    )
  except (sqlite3.Error, OSError) as error:
    state.connection.rollback()
    warn_once(state, error)
  try:
    yield
  finally:
    ended_at_ns = max(started_at_ns, time.time_ns())
    duration_ns = max(0, time.monotonic_ns() - started_monotonic_ns)
    if start_event_id is not None:
      try:
        record_test_result(
          state.connection,
          state.identity,
          start_event_id,
          state.suite,
          item.nodeid,
          state.worker_id,
          outcome_for_reports(item.stash.get(_REPORTS, [])),
          started_at_ns,
          ended_at_ns,
          duration_ns,
        )
      except (sqlite3.Error, OSError) as error:
        state.connection.rollback()
        warn_once(state, error)


@pytest.hookimpl(optionalhook=True)
def pytest_handlecrashitem(
  crashitem: str,
  report: pytest.TestReport,
  sched: object,
) -> None:
  del sched
  state = _MASTER_STATE
  if state is None:
    return
  worker = getattr(report, 'node', None)
  workerinfo = getattr(worker, 'workerinfo', None)
  worker_id = (
    workerinfo.get('id') if isinstance(workerinfo, dict) else None
  )
  if not isinstance(worker_id, str):
    return
  try:
    record_test_failure_for_worker(
      state.connection,
      state.identity,
      state.suite,
      crashitem,
      worker_id,
      time.time_ns(),
    )
  except (sqlite3.Error, OSError) as error:
    state.connection.rollback()
    warn_once(state, error)


def pytest_unconfigure(config: pytest.Config) -> None:
  global _MASTER_STATE
  state = config.stash.get(_STATE, None)
  if state is not None:
    state.connection.close()
    if state is _MASTER_STATE:
      _MASTER_STATE = None
