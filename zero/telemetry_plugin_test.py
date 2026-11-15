"""Tests for the pytest CI test telemetry plugin."""

import itertools
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pluggy
import pytest

from zero import telemetry, telemetry_plugin
from zero.telemetry import (
  RunIdentity,
  TestCase,
  initialize_schema,
  record_incomplete_test_results,
  record_test_start,
)
from zero.telemetry_plugin import (
  outcome_for_reports,
  pytest_configure,
  pytest_handlecrashitem,
  pytest_runtest_makereport,
  pytest_runtest_protocol,
  pytest_unconfigure,
  suite_for_nodeid,
)

IDENTITY = RunIdentity('build-9', 'job-4', 'deadbeef')


@contextmanager
def _virtual_dbs(
  monkeypatch: pytest.MonkeyPatch,
  dbs: dict[Path, str],
) -> Iterator[dict[Path, sqlite3.Connection]]:
  real_connect = sqlite3.connect
  keepers: dict[Path, sqlite3.Connection] = {}
  uris = {path: f'file:/{name}?vfs=memdb' for path, name in dbs.items()}
  for path, uri in uris.items():
    keeper = real_connect(uri, uri=True)
    initialize_schema(keeper, IDENTITY, 1_000, '3.13.9')
    keepers[path] = keeper

  def fake_connect(
    target: object, timeout: float = 5.0
  ) -> sqlite3.Connection:
    path = Path(str(target))
    uri = uris[path]
    return real_connect(uri, timeout=timeout, uri=True)

  with monkeypatch.context() as mp:
    mp.setattr(telemetry.sqlite3, 'connect', fake_connect)
    try:
      yield keepers
    finally:
      for keeper in keepers.values():
        keeper.close()


def _make_config(
  testpaths: tuple[str, ...] = (),
  root_name: str = 'pentagram',
) -> pytest.Config:
  return cast(
    pytest.Config,
    SimpleNamespace(
      rootpath=Path(f'/virtual/{root_name}'),
      stash=pytest.Stash(),
      getini=lambda name: list(testpaths) if name == 'testpaths' else [],
    ),
  )


def _make_item(config: pytest.Config, nodeid: str) -> pytest.Item:
  item = SimpleNamespace(
    config=config, nodeid=nodeid, stash=pytest.Stash()
  )
  return cast(pytest.Item, item)


def _make_report(
  nodeid: str,
  outcome: Literal['passed', 'failed', 'skipped'],
  when: Literal['setup', 'call', 'teardown'] = 'call',
  wasxfail: str | None = None,
  node: object = None,
) -> pytest.TestReport:
  report = pytest.TestReport(
    nodeid=nodeid,
    location=('suite/sample_test.py', 1, 'test_case'),
    keywords={},
    outcome=outcome,
    longrepr=None,
    when=when,
  )
  if wasxfail is not None:
    report.wasxfail = wasxfail
  if node is not None:
    report.__dict__['node'] = node
  return report


def _drive_protocol(
  item: pytest.Item,
  reports: list[object],
  exc: BaseException | None = None,
) -> None:
  protocol = pytest_runtest_protocol(item, None)
  next(protocol)
  for report in reports:
    makereport = pytest_runtest_makereport(item, None)
    next(makereport)
    with pytest.raises(StopIteration):
      makereport.send(pluggy.Result(report, None))
  with pytest.raises(StopIteration):
    protocol.send(pluggy.Result(None, exc))
  assert len(item.stash) == 0


def _set_plugin_env(
  monkeypatch: pytest.MonkeyPatch,
  database: str | None,
  *,
  build_id: str | None = IDENTITY.build_id,
  job_id: str | None = IDENTITY.job_id,
  revision: str | None = IDENTITY.source_revision,
  worker_id: str | None = None,
) -> None:
  monkeypatch.delenv('PYTEST_PLUGINS', raising=False)
  values = {
    'PENTAGRAM_TEST_TELEMETRY_DB': database,
    'PENTAGRAM_TEST_TELEMETRY_BUILD_ID': build_id,
    'PENTAGRAM_TEST_TELEMETRY_JOB_ID': job_id,
    'PENTAGRAM_TEST_TELEMETRY_REVISION': revision,
    'PYTEST_XDIST_WORKER': worker_id,
  }
  for key, value in values.items():
    if value is None:
      monkeypatch.delenv(key, raising=False)
    else:
      monkeypatch.setenv(key, value)


@pytest.mark.parametrize(
  ('nodeid', 'default_suite', 'expected'),
  [
    ('zero/a_test.py::test_one', 'pentagram', 'zero'),
    ('proj/sub/b_test.py::test_two', 'pentagram', 'proj'),
    ('./top_test.py::test_root', 'pentagram', 'pentagram'),
    ('top_test.py::test_bare', 'pentagram', 'pentagram'),
    ('/abs/top_test.py::test_abs', 'pentagram', 'pentagram'),
  ],
)
def test_suite_for_nodeid_attributes_multi_suite_and_root_paths(
  nodeid: str, default_suite: str, expected: str
) -> None:
  assert suite_for_nodeid(nodeid, default_suite) == expected


@pytest.mark.parametrize(
  ('reports', 'expected'),
  [
    ([], None),
    ([_make_report('t::a', 'passed', 'setup')], None),
    (
      [
        _make_report('t::a', 'passed', 'setup'),
        _make_report('t::a', 'passed', 'call'),
      ],
      None,
    ),
    (
      [
        _make_report('t::a', 'passed', 'setup'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      None,
    ),
    (
      [
        _make_report('t::a', 'passed', 'setup'),
        _make_report('t::a', 'failed', 'call'),
      ],
      None,
    ),
    (
      [
        _make_report('t::a', 'passed', 'setup'),
        _make_report('t::a', 'failed', 'call'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'failed',
    ),
    (
      [
        _make_report('t::a', 'failed', 'setup'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'failed',
    ),
    (
      [
        _make_report('t::a', 'skipped', 'setup'),
        _make_report('t::a', 'failed', 'teardown'),
      ],
      'failed',
    ),
    (
      [
        _make_report('t::a', 'passed', 'call', wasxfail='expected bug'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'xpassed',
    ),
    (
      [
        _make_report('t::a', 'passed', 'call', wasxfail=''),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'xpassed',
    ),
    (
      [
        _make_report('t::a', 'skipped', 'call', wasxfail='expected bug'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'xfailed',
    ),
    (
      [
        _make_report('t::a', 'skipped', 'call', wasxfail=''),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'xfailed',
    ),
    (
      [
        _make_report('t::a', 'skipped', 'setup'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'skipped',
    ),
    (
      [
        _make_report('t::a', 'passed', 'setup'),
        _make_report('t::a', 'passed', 'call'),
        _make_report('t::a', 'passed', 'teardown'),
      ],
      'passed',
    ),
  ],
)
def test_outcome_for_reports_classifies_all_pytest_outcomes(
  reports: list[pytest.TestReport], expected: str | None
) -> None:
  assert outcome_for_reports(reports) == expected


def test_pytest_configure_requires_env_and_handles_errors(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  def unexpected_connect(_database: Path) -> sqlite3.Connection:
    raise AssertionError('unexpected connect')

  with monkeypatch.context() as mp:
    mp.setattr(telemetry_plugin, 'connect_database', unexpected_connect)
    config = _make_config(('zero',))
    _set_plugin_env(mp, None)
    pytest_configure(config)
    item = _make_item(config, 'zero/t.py::test_unconfigured')
    _drive_protocol(item, [])
    assert capsys.readouterr() == ('', '')

  with monkeypatch.context() as mp:
    mp.setattr(telemetry_plugin, 'connect_database', unexpected_connect)
    config = _make_config(('zero',))
    _set_plugin_env(mp, '/virtual/plugin.sqlite3', revision='')
    pytest_configure(config)
    _drive_protocol(_make_item(config, 'zero/t.py::test_unconfigured'), [])
    assert capsys.readouterr() == ('', '')

  with monkeypatch.context() as mp:
    _set_plugin_env(mp, ':memory:')
    pytest_configure(_make_config(('zero',)))
    assert capsys.readouterr().err == (
      'CI test telemetry unavailable in pytest: '
      'invalid telemetry database path: :memory:\n'
    )

  with monkeypatch.context() as mp:
    mp.setattr(
      telemetry_plugin,
      'connect_database',
      lambda _database: (_ for _ in ()).throw(
        sqlite3.OperationalError('cannot open db')
      ),
    )
    _set_plugin_env(mp, '/virtual/plugin.sqlite3')
    pytest_configure(_make_config(('zero',)))
    assert capsys.readouterr().err == (
      'CI test telemetry unavailable in pytest: cannot open db\n'
    )

  with monkeypatch.context() as mp:
    close_calls: list[bool] = []

    def close_and_fail() -> None:
      close_calls.append(True)
      raise sqlite3.ProgrammingError('close fail')

    mp.setattr(
      telemetry_plugin,
      'connect_database',
      lambda _db: cast(
        sqlite3.Connection, SimpleNamespace(close=close_and_fail)
      ),
    )
    bad_ini_config = _make_config(('zero',))
    mp.setattr(
      bad_ini_config,
      'getini',
      lambda _name: (_ for _ in ()).throw(ValueError('bad ini')),
    )
    _set_plugin_env(mp, '/virtual/plugin.sqlite3')
    pytest_configure(bad_ini_config)
    assert close_calls == [True]
    assert capsys.readouterr().err == (
      'CI test telemetry unavailable in pytest: bad ini\n'
    )


def test_pytest_configure_and_protocol_record_outcomes_and_suites(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  wall_ticks = itertools.count(2_000, 100)
  mono_ticks = itertools.count(10_000, 50)
  monkeypatch.setattr(
    telemetry_plugin.time, 'time_ns', lambda: next(wall_ticks)
  )
  monkeypatch.setattr(
    telemetry_plugin.time, 'monotonic_ns', lambda: next(mono_ticks)
  )

  db_path = Path('/virtual/plugin_outcomes.sqlite3')
  with _virtual_dbs(monkeypatch, {db_path: 'plugin_outcomes'}) as keepers:
    keeper = keepers[db_path]
    config = _make_config(('.', 'proj'))
    _set_plugin_env(monkeypatch, str(db_path), worker_id='gw1')
    pytest_configure(config)

    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_pass'),
      [
        _make_report('zero/a_test.py::test_pass', 'passed', 'setup'),
        'non-report-result',
        _make_report('zero/a_test.py::test_pass', 'passed', 'call'),
        _make_report('zero/a_test.py::test_pass', 'passed', 'teardown'),
      ],
    )
    _drive_protocol(
      _make_item(config, 'top_test.py::test_xpass'),
      [
        _make_report(
          'top_test.py::test_xpass', 'passed', 'call', wasxfail=''
        ),
        _make_report('top_test.py::test_xpass', 'passed', 'teardown'),
      ],
    )
    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_xfail'),
      [
        _make_report(
          'zero/a_test.py::test_xfail', 'skipped', 'call', wasxfail=''
        ),
        _make_report('zero/a_test.py::test_xfail', 'passed', 'teardown'),
      ],
    )
    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_skip'),
      [
        _make_report('zero/a_test.py::test_skip', 'skipped', 'setup'),
        _make_report('zero/a_test.py::test_skip', 'passed', 'teardown'),
      ],
    )
    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_fail'),
      [
        _make_report('zero/a_test.py::test_fail', 'failed', 'call'),
        _make_report('zero/a_test.py::test_fail', 'passed', 'teardown'),
      ],
    )

    unconfigured = _make_config(('zero',))
    untracked_item = _make_item(unconfigured, 'zero/a_test.py::test_noop')
    _drive_protocol(untracked_item, [])
    makereport_untracked = pytest_runtest_makereport(untracked_item, None)
    next(makereport_untracked)
    with pytest.raises(StopIteration):
      makereport_untracked.send(
        pluggy.Result(
          _make_report('zero/a_test.py::test_noop', 'passed'), None
        )
      )

    pytest_unconfigure(config)
    pytest_unconfigure(config)

    starts = keeper.execute(
      'SELECT event_id, run_id, source_revision, suite, nodeid, '
      'worker_id, started_at_ns FROM test_started ORDER BY event_id'
    ).fetchall()
    results = keeper.execute(
      'SELECT event_id, start_event_id, run_id, source_revision, suite, '
      'nodeid, worker_id, outcome, started_at_ns, ended_at_ns, '
      'duration_ns, recovered_at_ns FROM test_result ORDER BY event_id'
    ).fetchall()
    rid = 'build-9:job-4'
    rev = 'deadbeef'
    assert starts == [
      (1, rid, rev, 'zero', 'zero/a_test.py::test_pass', 'gw1', 2000),
      (2, rid, rev, 'proj', 'top_test.py::test_xpass', 'gw1', 2200),
      (3, rid, rev, 'zero', 'zero/a_test.py::test_xfail', 'gw1', 2400),
      (4, rid, rev, 'zero', 'zero/a_test.py::test_skip', 'gw1', 2600),
      (5, rid, rev, 'zero', 'zero/a_test.py::test_fail', 'gw1', 2800),
    ]
    assert results == [
      (
        1,
        1,
        rid,
        rev,
        'zero',
        'zero/a_test.py::test_pass',
        'gw1',
        'passed',
        2000,
        2100,
        50,
        None,
      ),
      (
        2,
        2,
        rid,
        rev,
        'proj',
        'top_test.py::test_xpass',
        'gw1',
        'xpassed',
        2200,
        2300,
        50,
        None,
      ),
      (
        3,
        3,
        rid,
        rev,
        'zero',
        'zero/a_test.py::test_xfail',
        'gw1',
        'xfailed',
        2400,
        2500,
        50,
        None,
      ),
      (
        4,
        4,
        rid,
        rev,
        'zero',
        'zero/a_test.py::test_skip',
        'gw1',
        'skipped',
        2600,
        2700,
        50,
        None,
      ),
      (
        5,
        5,
        rid,
        rev,
        'zero',
        'zero/a_test.py::test_fail',
        'gw1',
        'failed',
        2800,
        2900,
        50,
        None,
      ),
    ]


def test_protocol_abort_leaves_test_started_for_incomplete_recovery(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  wall_ticks = itertools.count(3_000, 100)
  mono_ticks = itertools.count(20_000, 50)
  monkeypatch.setattr(
    telemetry_plugin.time, 'time_ns', lambda: next(wall_ticks)
  )
  monkeypatch.setattr(
    telemetry_plugin.time, 'monotonic_ns', lambda: next(mono_ticks)
  )

  db_path = Path('/virtual/plugin_abort.sqlite3')
  with _virtual_dbs(monkeypatch, {db_path: 'plugin_abort'}) as keepers:
    keeper = keepers[db_path]
    config = _make_config(('zero',))
    _set_plugin_env(monkeypatch, str(db_path), worker_id='gw0')
    pytest_configure(config)

    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_abort_setup'),
      [],
      exc=KeyboardInterrupt(),
    )
    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_abort_call'),
      [_make_report('zero/a_test.py::test_abort_call', 'passed', 'setup')],
      exc=pytest.exit.Exception('stop'),
    )
    _drive_protocol(
      _make_item(config, 'zero/a_test.py::test_abort_teardown'),
      [
        _make_report(
          'zero/a_test.py::test_abort_teardown', 'passed', 'setup'
        ),
        _make_report(
          'zero/a_test.py::test_abort_teardown', 'passed', 'call'
        ),
      ],
      exc=KeyboardInterrupt(),
    )

    assert keeper.execute('SELECT * FROM test_result').fetchall() == []
    pytest_unconfigure(config)

    record_incomplete_test_results(keeper, IDENTITY, 9_000)
    assert keeper.execute(
      'SELECT event_id, start_event_id, nodeid, outcome, ended_at_ns, '
      'duration_ns, recovered_at_ns FROM test_result ORDER BY event_id'
    ).fetchall() == [
      (
        1,
        1,
        'zero/a_test.py::test_abort_setup',
        'incomplete',
        None,
        None,
        9_000,
      ),
      (
        2,
        2,
        'zero/a_test.py::test_abort_call',
        'incomplete',
        None,
        None,
        9_000,
      ),
      (
        3,
        3,
        'zero/a_test.py::test_abort_teardown',
        'incomplete',
        None,
        None,
        9_000,
      ),
    ]


def test_warn_once_and_protocol_database_errors(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  monkeypatch.setattr(telemetry_plugin.time, 'time_ns', lambda: 1_234)
  monkeypatch.setattr(telemetry_plugin.time, 'monotonic_ns', lambda: 5_000)
  db_start_err = Path('/virtual/plugin_start_err.sqlite3')
  db_result_err = Path('/virtual/plugin_result_err.sqlite3')
  with _virtual_dbs(
    monkeypatch,
    {
      db_start_err: 'plugin_start_err',
      db_result_err: 'plugin_result_err',
    },
  ) as keepers:
    with monkeypatch.context() as mp:
      config_a = _make_config((), root_name='pentagram')
      _set_plugin_env(mp, str(db_start_err))
      pytest_configure(config_a)
      keepers[db_start_err].execute('DROP TABLE test_started')
      keepers[db_start_err].commit()
      _drive_protocol(
        _make_item(config_a, 'root_t.py::test_start_err'), []
      )
      _drive_protocol(
        _make_item(config_a, 'root_t.py::test_suppressed'), []
      )
      assert capsys.readouterr().err == (
        'CI test telemetry could not record a test: '
        'no such table: test_started\n'
      )
      pytest_unconfigure(config_a)

    with monkeypatch.context() as mp:
      config_b = _make_config((), root_name='pentagram')
      _set_plugin_env(mp, str(db_result_err))
      pytest_configure(config_b)
      keepers[db_result_err].execute('DROP TABLE test_result')
      keepers[db_result_err].commit()
      _drive_protocol(
        _make_item(config_b, 'root_t.py::test_result_err'),
        [
          _make_report('root_t.py::test_result_err', 'passed', 'call'),
          _make_report('root_t.py::test_result_err', 'passed', 'teardown'),
        ],
      )
      assert capsys.readouterr().err == (
        'CI test telemetry could not record a test: '
        'no such table: test_result\n'
      )
      assert keepers[db_result_err].execute(
        'SELECT * FROM test_started ORDER BY event_id'
      ).fetchall() == [
        (
          1,
          'build-9:job-4',
          'deadbeef',
          'pentagram',
          'root_t.py::test_result_err',
          'master',
          1_234,
        )
      ]
      pytest_unconfigure(config_b)


def test_pytest_handlecrashitem_routes_and_guards(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  monkeypatch.setattr(telemetry_plugin.time, 'time_ns', lambda: 9_500)

  db_path = Path('/virtual/plugin_crash.sqlite3')
  with _virtual_dbs(monkeypatch, {db_path: 'plugin_crash'}) as keepers:
    keeper = keepers[db_path]
    master_config = _make_config(('zero',))
    with monkeypatch.context() as mp:
      _set_plugin_env(mp, str(db_path))
      pytest_configure(master_config)
    record_test_start(
      keeper,
      IDENTITY,
      TestCase('zero', 'zero/c_test.py::test_a', 'gw0'),
      8_000,
    )
    record_test_start(
      keeper,
      IDENTITY,
      TestCase('proj', 'proj/c_test.py::test_b', 'gw1'),
      8_500,
    )
    record_test_start(
      keeper,
      IDENTITY,
      TestCase('zero', 'zero/c_test.py::test_db_err', 'gw2'),
      9_000,
    )

    node = SimpleNamespace(config=master_config, workerinfo={'id': 'gw0'})
    pytest_handlecrashitem(
      'zero/c_test.py::test_a',
      _make_report('zero/c_test.py::test_a', 'failed', node=node),
      SimpleNamespace(),
    )

    node_without_config = SimpleNamespace(workerinfo={'id': 'gw1'})
    pytest_handlecrashitem(
      'proj/c_test.py::test_b',
      _make_report(
        'proj/c_test.py::test_b', 'failed', node=node_without_config
      ),
      SimpleNamespace(config=master_config),
    )

    pytest_handlecrashitem(
      'zero/c_test.py::test_ignored_no_config',
      _make_report('zero/c_test.py::test_ignored_no_config', 'failed'),
      SimpleNamespace(config='not-a-config'),
    )
    pytest_handlecrashitem(
      'zero/c_test.py::test_ignored_no_state',
      _make_report('zero/c_test.py::test_ignored_no_state', 'failed'),
      SimpleNamespace(config=_make_config(('zero',))),
    )
    pytest_handlecrashitem(
      'zero/c_test.py::test_ignored_bad_worker',
      _make_report(
        'zero/c_test.py::test_ignored_bad_worker',
        'failed',
        node=SimpleNamespace(config=master_config, workerinfo={'id': 12}),
      ),
      SimpleNamespace(),
    )

    worker_config = _make_config(('zero',))
    with monkeypatch.context() as mp:
      _set_plugin_env(mp, str(db_path), worker_id='gw0')
      pytest_configure(worker_config)
    pytest_handlecrashitem(
      'zero/c_test.py::test_ignored_non_master',
      _make_report(
        'zero/c_test.py::test_ignored_non_master',
        'failed',
        node=SimpleNamespace(
          config=worker_config, workerinfo={'id': 'gw0'}
        ),
      ),
      SimpleNamespace(),
    )

    results = keeper.execute(
      'SELECT event_id, start_event_id, run_id, source_revision, suite, '
      'nodeid, worker_id, outcome, started_at_ns, ended_at_ns, '
      'duration_ns, recovered_at_ns FROM test_result ORDER BY event_id'
    ).fetchall()
    assert results == [
      (
        1,
        1,
        'build-9:job-4',
        'deadbeef',
        'zero',
        'zero/c_test.py::test_a',
        'gw0',
        'failed',
        8_000,
        None,
        None,
        9_500,
      ),
      (
        2,
        2,
        'build-9:job-4',
        'deadbeef',
        'proj',
        'proj/c_test.py::test_b',
        'gw1',
        'failed',
        8_500,
        None,
        None,
        9_500,
      ),
    ]

    keeper.execute('DROP TABLE test_result')
    keeper.commit()
    pytest_handlecrashitem(
      'zero/c_test.py::test_db_err',
      _make_report(
        'zero/c_test.py::test_db_err',
        'failed',
        node=SimpleNamespace(
          config=master_config, workerinfo={'id': 'gw2'}
        ),
      ),
      SimpleNamespace(),
    )
    assert capsys.readouterr().err == (
      'CI test telemetry could not record a test: '
      'no such table: test_result\n'
    )

    pytest_unconfigure(master_config)
    pytest_unconfigure(worker_config)


def test_two_simultaneous_pytest_configs_stay_isolated(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(telemetry_plugin.time, 'time_ns', lambda: 4_000)
  monkeypatch.setattr(telemetry_plugin.time, 'monotonic_ns', lambda: 5_000)

  db_alpha = Path('/virtual/plugin_alpha.sqlite3')
  db_beta = Path('/virtual/plugin_beta.sqlite3')
  with _virtual_dbs(
    monkeypatch,
    {db_alpha: 'plugin_dual_alpha', db_beta: 'plugin_dual_beta'},
  ) as keepers:
    config_alpha = _make_config(('alpha',), root_name='alpha_root')
    with monkeypatch.context() as mp:
      _set_plugin_env(mp, str(db_alpha))
      pytest_configure(config_alpha)

    config_beta = _make_config((), root_name='beta_root')
    with monkeypatch.context() as mp:
      _set_plugin_env(mp, str(db_beta), worker_id='gw2')
      pytest_configure(config_beta)

    _drive_protocol(
      _make_item(config_alpha, 'alpha/one_test.py::test_one'),
      [
        _make_report('alpha/one_test.py::test_one', 'passed', 'call'),
        _make_report('alpha/one_test.py::test_one', 'passed', 'teardown'),
      ],
    )
    _drive_protocol(
      _make_item(config_beta, 'beta/two_test.py::test_two'),
      [
        _make_report('beta/two_test.py::test_two', 'failed', 'call'),
        _make_report('beta/two_test.py::test_two', 'passed', 'teardown'),
      ],
    )

    pytest_unconfigure(config_alpha)
    _drive_protocol(
      _make_item(
        config_alpha, 'alpha/one_test.py::test_after_unconfigure'
      ),
      [],
    )

    _drive_protocol(
      _make_item(config_beta, 'top_test.py::test_three'),
      [
        _make_report('top_test.py::test_three', 'passed', 'call'),
        _make_report('top_test.py::test_three', 'passed', 'teardown'),
      ],
    )
    pytest_unconfigure(config_beta)

    alpha_started = (
      keepers[db_alpha]
      .execute('SELECT * FROM test_started ORDER BY event_id')
      .fetchall()
    )
    alpha_results = (
      keepers[db_alpha]
      .execute('SELECT * FROM test_result ORDER BY event_id')
      .fetchall()
    )
    beta_started = (
      keepers[db_beta]
      .execute('SELECT * FROM test_started ORDER BY event_id')
      .fetchall()
    )
    beta_results = (
      keepers[db_beta]
      .execute('SELECT * FROM test_result ORDER BY event_id')
      .fetchall()
    )
    assert alpha_started == [
      (
        1,
        'build-9:job-4',
        'deadbeef',
        'alpha',
        'alpha/one_test.py::test_one',
        'master',
        4_000,
      )
    ]
    assert alpha_results == [
      (
        1,
        1,
        'build-9:job-4',
        'deadbeef',
        'alpha',
        'alpha/one_test.py::test_one',
        'master',
        'passed',
        4_000,
        4_000,
        0,
        None,
      )
    ]
    assert beta_started == [
      (
        1,
        'build-9:job-4',
        'deadbeef',
        'beta',
        'beta/two_test.py::test_two',
        'gw2',
        4_000,
      ),
      (
        2,
        'build-9:job-4',
        'deadbeef',
        'beta_root',
        'top_test.py::test_three',
        'gw2',
        4_000,
      ),
    ]
    assert beta_results == [
      (
        1,
        1,
        'build-9:job-4',
        'deadbeef',
        'beta',
        'beta/two_test.py::test_two',
        'gw2',
        'failed',
        4_000,
        4_000,
        0,
        None,
      ),
      (
        2,
        2,
        'build-9:job-4',
        'deadbeef',
        'beta_root',
        'top_test.py::test_three',
        'gw2',
        'passed',
        4_000,
        4_000,
        0,
        None,
      ),
    ]


def test_plugin_handles_rollback_and_close_sqlite_errors(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  def make_broken_conn() -> tuple[
    sqlite3.Connection, list[str], list[str]
  ]:
    rollback_calls: list[str] = []
    close_calls: list[str] = []

    def broken_rollback() -> None:
      rollback_calls.append('rollback')
      raise sqlite3.ProgrammingError('broken rollback')

    def broken_close() -> None:
      close_calls.append('close')
      raise sqlite3.ProgrammingError('broken close')

    conn = cast(
      sqlite3.Connection,
      SimpleNamespace(rollback=broken_rollback, close=broken_close),
    )
    return conn, rollback_calls, close_calls

  with monkeypatch.context() as mp:
    broken_conn, rollback_calls, close_calls = make_broken_conn()
    mp.setattr(
      telemetry_plugin, 'connect_database', lambda _db: broken_conn
    )
    config_start = _make_config(('zero',))
    _set_plugin_env(mp, '/virtual/broken_start.sqlite3')
    pytest_configure(config_start)
    mp.setattr(
      telemetry_plugin,
      'record_test_start',
      lambda *_a: (_ for _ in ()).throw(
        sqlite3.OperationalError('start fail')
      ),
    )
    _drive_protocol(_make_item(config_start, 'zero/t.py::test_start'), [])
    assert rollback_calls == ['rollback']
    assert capsys.readouterr().err == (
      'CI test telemetry could not record a test: start fail\n'
    )
    pytest_unconfigure(config_start)
    assert close_calls == ['close']
    assert capsys.readouterr().err == ''

  with monkeypatch.context() as mp:
    broken_conn, rollback_calls, close_calls = make_broken_conn()
    mp.setattr(
      telemetry_plugin, 'connect_database', lambda _db: broken_conn
    )
    config_result = _make_config(('zero',))
    _set_plugin_env(mp, '/virtual/broken_result.sqlite3')
    pytest_configure(config_result)
    mp.setattr(telemetry_plugin, 'record_test_start', lambda *_a: 1)
    mp.setattr(
      telemetry_plugin,
      'record_test_result',
      lambda *_a: (_ for _ in ()).throw(
        sqlite3.OperationalError('result fail')
      ),
    )
    _drive_protocol(
      _make_item(config_result, 'zero/t.py::test_result'),
      [
        _make_report('zero/t.py::test_result', 'passed', 'call'),
        _make_report('zero/t.py::test_result', 'passed', 'teardown'),
      ],
    )
    assert rollback_calls == ['rollback']
    assert capsys.readouterr().err == (
      'CI test telemetry could not record a test: result fail\n'
    )
    pytest_unconfigure(config_result)
    assert close_calls == ['close']

  with monkeypatch.context() as mp:
    broken_conn, rollback_calls, close_calls = make_broken_conn()
    mp.setattr(
      telemetry_plugin, 'connect_database', lambda _db: broken_conn
    )
    config_crash = _make_config(('zero',))
    _set_plugin_env(mp, '/virtual/broken_crash.sqlite3')
    pytest_configure(config_crash)
    mp.setattr(
      telemetry_plugin,
      'record_test_failure_for_worker',
      lambda *_a: (_ for _ in ()).throw(
        sqlite3.OperationalError('crash fail')
      ),
    )
    pytest_handlecrashitem(
      'zero/t.py::test_crash',
      cast(
        pytest.TestReport,
        SimpleNamespace(
          node=SimpleNamespace(
            config=config_crash, workerinfo={'id': 'gw0'}
          )
        ),
      ),
      SimpleNamespace(),
    )
    assert rollback_calls == ['rollback']
    assert capsys.readouterr().err == (
      'CI test telemetry could not record a test: crash fail\n'
    )
    pytest_unconfigure(config_crash)
    assert close_calls == ['close']

  with monkeypatch.context() as mp:
    broken_conn, _rollback_calls, close_calls = make_broken_conn()
    mp.setattr(
      telemetry_plugin, 'connect_database', lambda _db: broken_conn
    )
    config_unwarned = _make_config(('zero',))
    _set_plugin_env(mp, '/virtual/broken_unwarned.sqlite3')
    pytest_configure(config_unwarned)
    pytest_unconfigure(config_unwarned)
    assert close_calls == ['close']
    assert capsys.readouterr().err == (
      'CI test telemetry could not record a test: broken close\n'
    )
