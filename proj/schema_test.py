"""In-memory SQLite integration tests for proj.schema."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from pytest import MonkeyPatch

from proj import core, schema

_NOW = 1_700_000_000
_NAME = core.ProjectName.parse('demo')
_CHARTER = core.CharterInput.parse(
  objective='Deliver core',
  scope='Schema layer',
  non_goals='UI shell',
  constraints='No disk writes',
  acceptance='All checks pass',
)

_GOAL_TABLE_SQL_V6 = """CREATE TABLE goal (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL
    CHECK (
      length(text) > 0
      AND substantive(text)
      AND length(text) <= 4000
    ),
  status TEXT NOT NULL DEFAULT 'cancelled'
    CHECK (status IN ('active', 'blocked', 'achieved', 'cancelled')),
  status_reason TEXT NOT NULL DEFAULT '',
  ever_activated INTEGER NOT NULL DEFAULT 0
    CHECK (ever_activated IN (0, 1)),
  created_at INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  achieved_at INTEGER,
  updated_at INTEGER NOT NULL,
  CHECK (
    (status = 'achieved' AND achieved_at IS NOT NULL)
    OR (status <> 'achieved' AND achieved_at IS NULL)
  )
)"""

_V6_TRIGGER_NAMES = (
  'project_charter_active_task',
  'task_status_transition',
  'goal_status_transition',
  'open_blocker_target',
)

_PROJECT_CHARTER_STABLE_ERROR_V6 = (
  'active task or active/blocked goal requires a stable project charter; '
  'end the task and cancel the goal before re-chartering'
)

_V6_TRIGGER_SQL = (
  f"""CREATE TRIGGER project_charter_active_task
BEFORE UPDATE OF objective, scope, non_goals, constraints_text, acceptance
ON project
WHEN OLD.charter_context_status = 'current'
AND (
  NEW.objective IS NOT OLD.objective
  OR NEW.scope IS NOT OLD.scope
  OR NEW.non_goals IS NOT OLD.non_goals
  OR NEW.constraints_text IS NOT OLD.constraints_text
  OR NEW.acceptance IS NOT OLD.acceptance
) AND (
  EXISTS (SELECT 1 FROM task WHERE status = 'active')
  OR EXISTS (SELECT 1 FROM goal WHERE status IN ('active', 'blocked'))
)
AND EXISTS (
  SELECT 1 FROM task WHERE started_at IS NOT NULL
)
BEGIN
  SELECT RAISE(
    ABORT, {_PROJECT_CHARTER_STABLE_ERROR_V6!r}
  );
END""",
  """CREATE TRIGGER task_status_transition
BEFORE UPDATE OF status ON task
WHEN NEW.status <> OLD.status AND NOT (
  (OLD.status = 'pending'
    AND NEW.status IN ('active', 'blocked', 'cancelled'))
  OR (OLD.status = 'active'
    AND NEW.status IN ('completed', 'blocked', 'cancelled'))
  OR (OLD.status = 'blocked' AND NEW.status IN ('pending', 'cancelled'))
  OR (OLD.status = 'completed' AND NEW.status = 'pending')
  OR (OLD.status = 'cancelled' AND NEW.status = 'pending')
)
BEGIN
  SELECT RAISE(ABORT, 'invalid task status transition');
END""",
  """CREATE TRIGGER goal_status_transition
BEFORE UPDATE OF status, ever_activated ON goal
WHEN (
  NEW.status <> OLD.status
  OR NEW.ever_activated IS NOT OLD.ever_activated
) AND NOT (
  (OLD.status = 'cancelled'
    AND OLD.ever_activated = 0
    AND NEW.status = 'active'
    AND NEW.ever_activated = 1)
  OR (OLD.status = 'active'
    AND OLD.ever_activated = 1
    AND NEW.status IN ('blocked', 'achieved', 'cancelled')
    AND NEW.ever_activated = 1)
  OR (OLD.status = 'blocked'
    AND OLD.ever_activated = 1
    AND NEW.status IN ('active', 'cancelled')
    AND NEW.ever_activated = 1)
)
BEGIN
  SELECT RAISE(ABORT, 'invalid goal status transition');
END""",
  """CREATE TRIGGER open_blocker_target
BEFORE INSERT ON blocker
WHEN NEW.status = 'open' AND (
  (NEW.task_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM task
    WHERE id = NEW.task_id AND status IN ('completed', 'cancelled')
  ))
  OR (NEW.task_id IS NULL AND EXISTS (
    SELECT 1 FROM goal
    WHERE id = NEW.goal_id AND status IN ('achieved', 'cancelled')
  ))
)
BEGIN
  SELECT RAISE(ABORT, 'open blocker targets a terminal entity');
END""",
)


@contextmanager
def _memory_db() -> Iterator[sqlite3.Connection]:
  connection = sqlite3.connect(':memory:')
  try:
    schema.configure_connection(connection)
    connection.create_function(
      'unixepoch', 0, lambda: _NOW, deterministic=False
    )
    connection.create_function(
      'strftime',
      2,
      lambda fmt, value: str(_NOW)
      if (fmt, value) == ('%s', 'now')
      else '',
      deterministic=False,
    )
    yield connection
  finally:
    connection.close()


def _init_db(connection: sqlite3.Connection) -> None:
  schema.initialize_project(connection, _NAME, _CHARTER)


def _setup_stage_and_task(
  connection: sqlite3.Connection,
) -> tuple[int, int]:
  stage_cursor = connection.execute(
    'INSERT INTO stage '
    '(name, outcome, exit_evidence, created_at, updated_at) '
    "VALUES ('s1', 'Stage outcome', 'Evidence', ?, ?)",
    (_NOW, _NOW),
  )
  stage_id = stage_cursor.lastrowid
  assert stage_id is not None
  task_cursor = connection.execute(
    'INSERT INTO task '
    '(stage_id, title, purpose, scope, exclusions, result, '
    'completion_evidence, created_at, updated_at) '
    "VALUES (?, 't1', 'p', 's', 'e', 'r', 'ce', ?, ?)",
    (stage_id, _NOW, _NOW),
  )
  task_id = task_cursor.lastrowid
  assert task_id is not None
  connection.commit()
  return stage_id, task_id


@pytest.fixture(scope='module')
def v7_snapshot() -> bytes:
  with _memory_db() as base:
    _init_db(base)
    return base.serialize()


def downgrade_v7_to_v6(raw: sqlite3.Connection) -> None:
  """Downgrade a configured or raw v7 SQLite connection to canonical v6."""
  schema.configure_connection(raw)
  goal_triggers = {
    row['name']: row['sql']
    for row in raw.execute(
      'SELECT name, sql FROM sqlite_master '
      "WHERE type = 'trigger' AND tbl_name = 'goal'"
    )
  }
  for name in _V6_TRIGGER_NAMES:
    if name not in goal_triggers:
      raw.execute(f'DROP TRIGGER "{name}"')
  raw.execute('PRAGMA foreign_keys = OFF')
  raw.executescript(
    f"""
    DROP TABLE goal;
    {_GOAL_TABLE_SQL_V6};
    CREATE INDEX goal_status_index ON goal(status);
    CREATE UNIQUE INDEX one_active_goal_index
      ON goal(status) WHERE status = 'active';
    PRAGMA user_version = 6;
    """
  )
  for name, sql in goal_triggers.items():
    if name not in _V6_TRIGGER_NAMES:
      raw.execute(sql)
  for trigger_sql in _V6_TRIGGER_SQL:
    raw.execute(trigger_sql)
  raw.execute('PRAGMA foreign_keys = ON')
  raw.commit()


def _build_v6_snapshot(v7_snapshot: bytes) -> bytes:
  with _memory_db() as source:
    source.deserialize(v7_snapshot)
    downgrade_v7_to_v6(source)
    stage_id = source.execute(
      'INSERT INTO stage (name, outcome, created_at, updated_at) '
      "VALUES ('s1', 'o1', ?, ?)",
      (_NOW, _NOW),
    ).lastrowid
    goal_id = source.execute(
      'INSERT INTO goal (text, created_at, started_at, updated_at) '
      "VALUES ('Goal v6', ?, 0, ?)",
      (_NOW, _NOW),
    ).lastrowid
    source.execute(
      'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
      (goal_id, stage_id),
    )
    source.execute(
      "UPDATE goal SET status = 'active', ever_activated = 1, "
      'started_at = ? WHERE id = ?',
      (_NOW, goal_id),
    )
    source.execute(
      'INSERT INTO task '
      '(stage_id, goal_id, title, purpose, scope, exclusions, result, '
      'completion_evidence, created_at, updated_at) '
      "VALUES (?, ?, 'Task v6', 'p', 's', 'e', 'r', 'ce', ?, ?)",
      (stage_id, goal_id, _NOW, _NOW),
    )
    source.commit()
    return source.serialize()


def test_configure_connection_and_connection_time_contracts() -> None:
  with _memory_db() as connection:
    fk = connection.execute('PRAGMA foreign_keys').fetchone()
    busy = connection.execute('PRAGMA busy_timeout').fetchone()
    substantive_values = connection.execute(
      "SELECT substantive('\u00a0\u2003'), substantive(' x '), "
      "substantive(X'c2a0'), substantive(X'41'), substantive(123)"
    ).fetchone()
    now = schema.connection_time(connection)
    assert (
      connection.row_factory,
      tuple(fk) if fk is not None else None,
      tuple(busy) if busy is not None else None,
      tuple(substantive_values)
      if substantive_values is not None
      else None,
      now,
    ) == (sqlite3.Row, (1,), (5000,), (0, 1, 0, 0, 0), _NOW)

  with pytest.raises(core.ProjectError) as cfg_err:
    schema.configure_connection(connection)
  assert str(cfg_err.value) == (
    'Project database connection could not be configured: '
    'Cannot operate on a closed database.'
  )

  with pytest.raises(core.ProjectError) as time_err:
    schema.connection_time(connection)
  assert str(time_err.value) == (
    'Project database clock query failed: '
    'Cannot operate on a closed database.'
  )


def test_initialize_and_validate_project_round_trip() -> None:
  with _memory_db() as connection:
    _init_db(connection)
    schema.validate_project(
      connection, expected_name=_NAME, display_path='memory://demo'
    )
    version = connection.execute('PRAGMA user_version').fetchone()
    project = connection.execute('SELECT * FROM project').fetchone()
    state = connection.execute('SELECT * FROM project_state').fetchone()
    assert (
      tuple(version) if version is not None else None,
      dict(project) if project is not None else None,
      dict(state) if state is not None else None,
    ) == (
      (schema.SCHEMA_VERSION,),
      {
        'id': 1,
        'name': 'demo',
        'objective': 'Deliver core',
        'scope': 'Schema layer',
        'non_goals': 'UI shell',
        'constraints_text': 'No disk writes',
        'acceptance': 'All checks pass',
        'created_at': _NOW,
        'updated_at': _NOW,
        'charter_context_status': 'current',
      },
      {
        'id': 1,
        'summary': '',
        'next_action': '',
        'updated_at': _NOW,
        'revision': 0,
      },
    )

    with pytest.raises(core.ProjectError) as reinit_err:
      schema.initialize_project(connection, _NAME, _CHARTER)
    assert str(reinit_err.value) == (
      'Project database could not be initialized: '
      'table project already exists'
    )


def test_lifecycle_triggers_and_foreign_keys_enforce_contracts() -> None:
  with _memory_db() as connection:
    _init_db(connection)
    stage_id, task_id = _setup_stage_and_task(connection)
    stage2_id = connection.execute(
      'INSERT INTO stage (name, outcome, exit_evidence, created_at, '
      "updated_at) VALUES ('s2', 'o2', 'e2', ?, ?)",
      (_NOW, _NOW),
    ).lastrowid
    assert stage2_id is not None

    goal_id = connection.execute(
      'INSERT INTO goal (text, created_at, started_at, updated_at) '
      "VALUES ('Goal A', ?, 0, ?)",
      (_NOW, _NOW),
    ).lastrowid
    assert goal_id is not None
    connection.execute(
      'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
      (goal_id, stage_id),
    )
    connection.execute(
      "UPDATE goal SET status = 'active', ever_activated = 1, "
      'started_at = ? WHERE id = ?',
      (_NOW, goal_id),
    )

    with pytest.raises(sqlite3.IntegrityError) as fk_err:
      connection.execute(
        'INSERT INTO task_log (task_id, occurred_at, message) '
        "VALUES (999, ?, 'orphan')",
        (_NOW,),
      )
    assert str(fk_err.value) == 'FOREIGN KEY constraint failed'

    trigger_cases: list[tuple[str, tuple[object, ...], str]] = [
      (
        'INSERT INTO stage (name, outcome, created_at, updated_at) '
        "VALUES (' ', 'out', ?, ?)",
        (_NOW, _NOW),
        'stage name and outcome must contain text',
      ),
      (
        'INSERT INTO stage '
        '(name, outcome, achievement_generation_started_at, '
        "created_at, updated_at) VALUES ('bad_gen', 'out', ?, ?, ?)",
        (_NOW - 1, _NOW, _NOW),
        'new stage must begin its first generation now',
      ),
      (
        'INSERT INTO task '
        '(stage_id, title, status, created_at, updated_at) '
        "VALUES (?, 'bad', 'active', ?, ?)",
        (stage_id, _NOW, _NOW),
        'new task is not unstarted and pending',
      ),
      (
        "UPDATE task SET status = 'completed', completed_at = ? "
        'WHERE id = ?',
        (_NOW, task_id),
        'completed task has no start time',
      ),
      (
        "UPDATE goal SET text = 'Changed' WHERE id = ?",
        (goal_id,),
        'goal text is immutable',
      ),
      (
        'INSERT INTO goal '
        '(text, status, created_at, started_at, updated_at) '
        "VALUES ('Bad goal', 'active', ?, 0, ?)",
        (_NOW, _NOW),
        'new goal is not in construction state',
      ),
      (
        'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
        (goal_id, stage2_id),
        'goal-stage scope is already fixed',
      ),
      (
        'INSERT INTO blocker (task_id, description, required, opened_at) '
        "VALUES (?, '  ', 'fix', ?)",
        (task_id, _NOW),
        'blocker description and requirement need text',
      ),
      (
        'INSERT INTO blocker (task_id, goal_id, description, required, '
        "opened_at) VALUES (?, ?, 'mismatch', 'fix', ?)",
        (task_id, goal_id, _NOW),
        'blocker relationships are incoherent',
      ),
      (
        'INSERT INTO decision (task_id, stage_id, summary, decided_at, '
        "context_status) VALUES (?, ?, 'd', ?, 'legacy-unresolved')",
        (task_id, stage_id, _NOW),
        'decision relationships are incoherent',
      ),
      (
        'INSERT INTO evidence (stage_id, claim, captured_at, '
        "stage_generation) VALUES (?, 'ev', ?, 0)",
        (stage_id, _NOW + 1),
        'evidence capture time is in the future',
      ),
      (
        'INSERT INTO evidence (stage_id, claim, captured_at, '
        "stage_generation) VALUES (?, 'ev', ?, 1)",
        (stage_id, _NOW),
        'evidence has the wrong stage generation',
      ),
    ]
    observed_errors: list[str] = []
    for sql, params, _expected in trigger_cases:
      with pytest.raises(sqlite3.IntegrityError) as exc_info:
        connection.execute(sql, params)
      observed_errors.append(str(exc_info.value))
    assert observed_errors == [
      expected for _, _, expected in trigger_cases
    ]

    connection.execute(
      'INSERT INTO blocker (task_id, description, required, opened_at) '
      "VALUES (?, 'Blocked on env', 'Fix env', ?)",
      (task_id, _NOW),
    )
    blocker_id = connection.execute(
      'SELECT last_insert_rowid()'
    ).fetchone()[0]
    blocked_status = connection.execute(
      'SELECT status FROM task WHERE id = ?', (task_id,)
    ).fetchone()['status']
    connection.execute(
      "UPDATE blocker SET status = 'resolved', resolved_at = ?, "
      "resolution = 'Env fixed' WHERE id = ?",
      (_NOW, blocker_id),
    )
    released_status = connection.execute(
      'SELECT status FROM task WHERE id = ?', (task_id,)
    ).fetchone()['status']
    connection.execute(
      'INSERT INTO evidence (goal_id, claim, captured_at) '
      "VALUES (?, 'Goal verified', ?)",
      (goal_id, _NOW),
    )
    connection.execute(
      "UPDATE goal SET status = 'achieved', achieved_at = ? WHERE id = ?",
      (_NOW, goal_id),
    )
    achieved_status = connection.execute(
      'SELECT status FROM goal WHERE id = ?', (goal_id,)
    ).fetchone()['status']
    assert (blocked_status, released_status, achieved_status) == (
      'blocked',
      'pending',
      'achieved',
    )


def test_validate_project_accepts_private_objects_and_rejects_drift(
  v7_snapshot: bytes,
) -> None:
  raw = v7_snapshot

  with _memory_db() as drift_db:
    drift_db.deserialize(raw)

    def assert_valid_savepoint(statements: tuple[str, ...]) -> None:
      drift_db.execute('SAVEPOINT drift_case')
      try:
        for statement in statements:
          drift_db.execute(statement)
        schema.validate_project(
          drift_db,
          expected_name=_NAME,
          display_path='memory://demo',
        )
      finally:
        drift_db.execute('ROLLBACK TO drift_case')
        drift_db.execute('RELEASE drift_case')

    def capture_error_savepoint(
      statements: tuple[str, ...],
      expected_name: core.ProjectName = _NAME,
    ) -> str:
      drift_db.execute('SAVEPOINT drift_case')
      try:
        for statement in statements:
          drift_db.execute(statement)
        with pytest.raises(core.ProjectError) as exc_info:
          schema.validate_project(
            drift_db,
            expected_name=expected_name,
            display_path='memory://demo',
          )
        return str(exc_info.value)
      finally:
        drift_db.execute('ROLLBACK TO drift_case')
        drift_db.execute('RELEASE drift_case')

    assert_valid_savepoint(
      (
        'CREATE TABLE custom_notes (id INTEGER PRIMARY KEY, note TEXT)',
        'CREATE INDEX custom_notes_idx ON custom_notes(note)',
      )
    )

    with _memory_db() as missing_table_db:
      with pytest.raises(core.ProjectError) as missing_tbl_err:
        schema.validate_project(
          missing_table_db,
          expected_name=_NAME,
          display_path='memory://demo',
        )
    with _memory_db() as fk_db:
      fk_db.deserialize(raw)
      fk_db.executescript(
        'PRAGMA foreign_keys = OFF; '
        'INSERT INTO task_log (task_id, occurred_at, message) '
        f"VALUES (999, {_NOW}, 'orphan'); "
        'PRAGMA foreign_keys = ON;'
      )
      with pytest.raises(core.ProjectError) as fk_err:
        schema.validate_project(
          fk_db, expected_name=_NAME, display_path='memory://demo'
        )

    def capture_singleton_error_savepoint(
      trigger_name: str,
      statements: tuple[str, ...],
    ) -> str:
      drift_db.execute('SAVEPOINT drift_case')
      try:
        trigger_row = drift_db.execute(
          'SELECT sql FROM sqlite_master '
          "WHERE type = 'trigger' AND name = ?",
          (trigger_name,),
        ).fetchone()
        assert trigger_row is not None
        drift_db.execute(f'DROP TRIGGER "{trigger_name}"')
        for statement in statements:
          drift_db.execute(statement)
        drift_db.execute(trigger_row['sql'])
        with pytest.raises(core.ProjectError) as exc_info:
          schema.validate_project(
            drift_db,
            expected_name=_NAME,
            display_path='memory://demo',
          )
        return str(exc_info.value)
      finally:
        drift_db.execute('ROLLBACK TO drift_case')
        drift_db.execute('RELEASE drift_case')

    observed_drift = (
      str(missing_tbl_err.value),
      capture_error_savepoint(('PRAGMA user_version = 5',)),
      capture_singleton_error_savepoint(
        'project_name_update',
        ("UPDATE project SET name = X'64656d6f'",),
      ),
      capture_error_savepoint((), core.ProjectName.parse('other')),
      capture_singleton_error_savepoint(
        'project_delete', ('DELETE FROM project',)
      ),
      capture_singleton_error_savepoint(
        'project_state_delete', ('DELETE FROM project_state',)
      ),
      capture_error_savepoint(('DROP INDEX task_stage_index',)),
      capture_error_savepoint(
        (
          'DROP INDEX task_stage_index',
          'CREATE INDEX task_stage_index ON task(stage_id, status)',
        )
      ),
      capture_error_savepoint(
        ('CREATE INDEX extra_task_idx ON task(priority)',)
      ),
      capture_error_savepoint(
        (
          'CREATE TRIGGER extra_trig AFTER INSERT ON task '
          'BEGIN SELECT 1; END',
        )
      ),
      str(fk_err.value),
    )

  assert observed_drift == (
    'Unsupported project schema version 0; expected 7: memory://demo',
    'Unsupported project schema version 5; expected 7: memory://demo',
    'Project database metadata columns must be text: memory://demo',
    "Project name 'demo' does not match database address 'other': memory://demo",
    'Project database must contain one project row; found 0: memory://demo',
    'Project database must contain one project-state row; found 0: '
    'memory://demo',
    'Project schema is incomplete; missing indexes: task_stage_index: '
    'memory://demo',
    'Project schema has incompatible indexes: task_stage_index: memory://demo',
    'Project schema has unexpected indexes on canonical tables: '
    'extra_task_idx: memory://demo',
    'Project schema has unexpected triggers: extra_trig: memory://demo',
    'Project has a foreign-key violation: task_log row 1 references task: '
    'memory://demo',
  )


def test_validate_project_missing_tables_and_corrupt_page_adaptation(
  v7_snapshot: bytes,
) -> None:
  with _memory_db() as db:
    db.execute('PRAGMA user_version = 7')
    with pytest.raises(core.ProjectError) as exc_info:
      schema.validate_project(
        db, expected_name=_NAME, display_path='memory://demo'
      )
    with pytest.raises(core.ProjectError) as overlap_exc_info:
      schema.validate_project(
        db, expected_name=_NAME, display_path='project'
      )

  corrupt_page_db = sqlite3.connect(':memory:')
  try:
    corrupt_page_db.deserialize(v7_snapshot)
    root_page = corrupt_page_db.execute(
      'SELECT rootpage FROM sqlite_master '
      "WHERE type = 'table' AND name = 'project'"
    ).fetchone()[0]
    page_offset = (root_page - 1) * 4096
    corrupt_page_bytes = bytearray(v7_snapshot)
    corrupt_page_bytes[page_offset : page_offset + 256] = b'\xff' * 256
    corrupt_page_db.deserialize(bytes(corrupt_page_bytes))
    schema.configure_connection(corrupt_page_db)
    classified = schema.classify_database(corrupt_page_db)
    with pytest.raises(core.ProjectError) as corrupt_page_err:
      schema.validate_project(
        corrupt_page_db,
        expected_name=_NAME,
        display_path='memory://corrupt-page',
      )
  finally:
    corrupt_page_db.close()

  expected_missing = (
    'Project schema is incomplete; missing tables: '
    'blocker, decision, evidence, goal, goal_stage, legacy_lifecycle, '
    'project, project_charter_history, project_state, stage, '
    'stage_achievement, stage_dependency, task, task_log, task_tag'
  )
  assert (
    str(exc_info.value),
    str(overlap_exc_info.value),
    classified,
    str(corrupt_page_err.value),
  ) == (
    f'{expected_missing}: memory://demo',
    f'{expected_missing}: project',
    'project',
    'Project database could not be validated: '
    'memory://corrupt-page: database disk image is malformed',
  )


def test_v6_migration_upgrades_to_v7_and_rolls_back_atomically(
  v7_snapshot: bytes,
  monkeypatch: MonkeyPatch,
) -> None:
  v6_bytes = _build_v6_snapshot(v7_snapshot)
  expected_tables = (
    ((1, 'Goal v6', 'active', '', 1, _NOW, _NOW, None, _NOW),),
    ((1, 's1', 'o1', '', '', '', 0, 0, _NOW, _NOW, _NOW),),
    ((1, 1),),
    (
      (
        1,
        1,
        1,
        'Task v6',
        'p',
        's',
        'e',
        'r',
        'ce',
        'pending',
        0,
        _NOW,
        None,
        None,
        _NOW,
      ),
    ),
  )

  def read_tables(
    conn: sqlite3.Connection,
  ) -> tuple[
    tuple[tuple[object, ...], ...],
    tuple[tuple[object, ...], ...],
    tuple[tuple[object, ...], ...],
    tuple[tuple[object, ...], ...],
  ]:
    return (
      tuple(
        tuple(row)
        for row in conn.execute('SELECT * FROM goal ORDER BY id')
      ),
      tuple(
        tuple(row)
        for row in conn.execute('SELECT * FROM stage ORDER BY id')
      ),
      tuple(
        tuple(row)
        for row in conn.execute(
          'SELECT * FROM goal_stage ORDER BY goal_id, stage_id'
        )
      ),
      tuple(
        tuple(row)
        for row in conn.execute('SELECT * FROM task ORDER BY id')
      ),
    )

  with _memory_db() as db:
    db.deserialize(v6_bytes)
    assert read_tables(db) == expected_tables

    with pytest.raises(core.ProjectError) as in_tx_err:
      db.execute('BEGIN')
      schema._migrate_schema_6_to_7(db)
    assert str(in_tx_err.value) == (
      'Cannot migrate schema version 6 database inside an active '
      'transaction'
    )
    db.rollback()

    original_validate_lifecycle = schema._validate_current_lifecycle
    calls = 0

    def fail_on_post_migration_check(conn: sqlite3.Connection) -> None:
      nonlocal calls
      calls += 1
      if calls == 2:
        raise core.ProjectError(
          'Simulated mid-migration lifecycle failure'
        )
      original_validate_lifecycle(conn)

    with monkeypatch.context() as mp:
      mp.setattr(
        schema, '_validate_current_lifecycle', fail_on_post_migration_check
      )
      with pytest.raises(core.ProjectError) as exc_info:
        schema.validate_project(
          db, expected_name=_NAME, display_path='memory://demo'
        )
    assert str(exc_info.value) == (
      'Simulated mid-migration lifecycle failure: memory://demo'
    )
    version_after = db.execute('PRAGMA user_version').fetchone()
    fk_after = db.execute('PRAGMA foreign_keys').fetchone()
    assert (
      db.in_transaction,
      tuple(version_after) if version_after is not None else None,
      tuple(fk_after) if fk_after is not None else None,
      read_tables(db),
    ) == (False, (6,), (1,), expected_tables)

    schema.validate_project(
      db, expected_name=_NAME, display_path='memory://demo'
    )
    assert read_tables(db) == expected_tables

    db.execute("UPDATE goal SET status = 'pending' WHERE id = 1")
    schema.validate_project(
      db, expected_name=_NAME, display_path='memory://demo'
    )
    version = db.execute('PRAGMA user_version').fetchone()
    status = db.execute('SELECT status FROM goal WHERE id = 1').fetchone()
    assert (
      tuple(version) if version is not None else None,
      status['status'] if status is not None else None,
    ) == ((schema.SCHEMA_VERSION,), 'pending')


def test_initialize_project_rolls_back_on_project_error(
  monkeypatch: MonkeyPatch,
) -> None:
  def fail_clock(_conn: sqlite3.Connection) -> int:
    raise core.ProjectError('Simulated clock failure')

  with _memory_db() as db:
    monkeypatch.setattr(schema, 'connection_time', fail_clock)
    with pytest.raises(core.ProjectError) as init_err:
      schema.initialize_project(db, _NAME, _CHARTER)
    assert str(init_err.value) == (
      'Project database could not be initialized: Simulated clock failure'
    )
    tables = tuple(
      row[0]
      for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
      )
    )
    version = db.execute('PRAGMA user_version').fetchone()
    assert (db.in_transaction, tables, version[0]) == (False, (), 0)


def test_validate_project_rejects_forged_lifecycle_states(
  v7_snapshot: bytes,
) -> None:
  raw = v7_snapshot

  with _memory_db() as db:
    db.deserialize(raw)

    def run_with_bypassed(
      triggers_to_bypass: tuple[str, ...], statements: tuple[str, ...]
    ) -> str:
      db.execute('SAVEPOINT forged_case')
      try:
        saved_sql: list[str] = []
        for name in triggers_to_bypass:
          row = db.execute(
            'SELECT sql FROM sqlite_master '
            "WHERE type = 'trigger' AND name = ?",
            (name,),
          ).fetchone()
          assert row is not None
          saved_sql.append(row['sql'])
          db.execute(f'DROP TRIGGER "{name}"')
        for statement in statements:
          db.execute(statement)
        for sql in saved_sql:
          db.execute(sql)
        with pytest.raises(core.ProjectError) as exc_info:
          schema.validate_project(
            db, expected_name=_NAME, display_path='memory://demo'
          )
        return str(exc_info.value)
      finally:
        db.execute('ROLLBACK TO forged_case')
        db.execute('RELEASE forged_case')

    observed_forged = (
      run_with_bypassed(
        ('stage_dependency_cycle',),
        (
          'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
          f"VALUES (1, 's1', 'o1', {_NOW}, {_NOW}), "
          f"(2, 's2', 'o2', {_NOW}, {_NOW})",
          'INSERT INTO stage_dependency VALUES (1, 2), (2, 1)',
        ),
      ),
      run_with_bypassed(
        ('project_charter_update', 'project_charter_active_task'),
        (
          'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
          f"VALUES (1, 's1', 'o1', {_NOW}, {_NOW})",
          'INSERT INTO task '
          '(id, stage_id, title, purpose, scope, exclusions, '
          'result, completion_evidence, created_at, updated_at) '
          f"VALUES (1, 1, 't', 'p', 's', 'e', 'r', 'c', {_NOW}, {_NOW})",
          f"UPDATE task SET status = 'active', started_at = {_NOW} "
          'WHERE id = 1',
          "UPDATE project SET scope = '' WHERE id = 1",
        ),
      ),
      run_with_bypassed(
        ('stage_generation_insert',),
        (
          'INSERT INTO stage (id, name, outcome, '
          'achievement_generation_started_at, created_at, updated_at) '
          f"VALUES (1, 's1', 'o1', {_NOW + 5}, {_NOW}, {_NOW})",
        ),
      ),
      run_with_bypassed(
        ('blocked_task_update',),
        (
          'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
          f"VALUES (1, 's1', 'o1', {_NOW}, {_NOW})",
          'INSERT INTO task (id, stage_id, title, created_at, updated_at) '
          f"VALUES (1, 1, 't1', {_NOW}, {_NOW})",
          "UPDATE task SET status = 'blocked' WHERE id = 1",
        ),
      ),
      run_with_bypassed(
        ('decision_relationship_insert',),
        (
          'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
          f"VALUES (1, 's1', 'o1', {_NOW}, {_NOW})",
          'INSERT INTO task (id, stage_id, title, created_at, updated_at) '
          f"VALUES (1, 1, 't1', {_NOW}, {_NOW})",
          'INSERT INTO decision (id, task_id, stage_id, summary, '
          'decided_at, context_status) '
          f"VALUES (1, 1, NULL, 'd', {_NOW}, 'complete')",
        ),
      ),
      run_with_bypassed(
        ('evidence_capture_time_insert',),
        (
          'INSERT INTO evidence (id, claim, captured_at) '
          f"VALUES (1, 'future', {_NOW + 10})",
        ),
      ),
      run_with_bypassed(
        ('goal_initial_status',),
        (
          'INSERT INTO goal '
          '(id, text, ever_activated, created_at, started_at, updated_at) '
          f"VALUES (1, 'never', 0, {_NOW}, 0, {_NOW})",
        ),
      ),
      run_with_bypassed(
        ('task_completion_time_valid',),
        (
          'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
          f"VALUES (1, 's1', 'o1', {_NOW}, {_NOW})",
          'INSERT INTO task '
          '(id, stage_id, title, purpose, scope, exclusions, '
          'result, completion_evidence, created_at, updated_at) '
          f"VALUES (1, 1, 't', 'p', 's', 'e', 'r', 'c', {_NOW}, {_NOW})",
          f"UPDATE task SET status = 'active', started_at = {_NOW} "
          'WHERE id = 1',
          "UPDATE task SET status = 'completed', "
          f'completed_at = {_NOW + 5} WHERE id = 1',
        ),
      ),
    )

  assert observed_forged == (
    'Project has a stage-dependency cycle at stage 1: memory://demo',
    'Project has an incomplete post-execution charter: memory://demo',
    'Project has an invalid stage contract: 1: memory://demo',
    'Project has a blocked task without an open blocker: 1: memory://demo',
    'Project has incoherent record context: decision 1: memory://demo',
    'Project has incoherent evidence state: 1: memory://demo',
    'Project has an invalid goal lifecycle: 1: memory://demo',
    'Project has invalid task chronology: 1: memory://demo',
  )


def _classify_raw_database(script: str) -> schema.DatabaseClassification:
  conn = sqlite3.connect(':memory:')
  try:
    if script:
      conn.executescript(script)
    return schema.classify_database(conn)
  finally:
    conn.close()


def test_classify_database_classifies_schemas_and_corruption(
  v7_snapshot: bytes,
) -> None:
  v7_triggers = {
    name
    for kind, name in schema._canonical_schema_definitions(7)
    if kind == 'trigger'
  }
  v6_triggers = {
    name
    for kind, name in schema._canonical_schema_definitions(6)
    if kind == 'trigger'
  }
  assert schema._PROJECT_TRIGGER_NAMES == v7_triggers
  assert v7_triggers == v6_triggers

  v7_raw = sqlite3.connect(':memory:')
  v6_raw = sqlite3.connect(':memory:')
  damaged_raw = sqlite3.connect(':memory:')
  try:
    v7_raw.deserialize(v7_snapshot)
    v6_raw.deserialize(v7_snapshot)
    downgrade_v7_to_v6(v6_raw)
    damaged_raw.deserialize(v7_snapshot)
    damaged_raw.execute('DROP TABLE project')
    v7_kind = schema.classify_database(v7_raw)
    v6_kind = schema.classify_database(v6_raw)
    damaged_kind = schema.classify_database(damaged_raw)
  finally:
    v7_raw.close()
    v6_raw.close()
    damaged_raw.close()

  raw_observations = (
    _classify_raw_database(''),
    _classify_raw_database(
      """
      PRAGMA user_version = 1;
      CREATE TABLE run (id INTEGER PRIMARY KEY);
      CREATE TABLE run_event (id INTEGER PRIMARY KEY);
      CREATE TABLE test_started (id INTEGER PRIMARY KEY);
      CREATE TABLE test_result (id INTEGER PRIMARY KEY);
      CREATE TABLE resource_sample (id INTEGER PRIMARY KEY);
      CREATE TRIGGER append_only_run
      BEFORE UPDATE ON run
      BEGIN
        SELECT RAISE(ABORT, 'append only');
      END;
      """
    ),
    _classify_raw_database(
      """
      CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);
      CREATE TRIGGER notes_guard BEFORE DELETE ON notes
      BEGIN
        SELECT RAISE(ABORT, 'immutable');
      END;
      """
    ),
    _classify_raw_database(
      'CREATE TABLE project (id INTEGER PRIMARY KEY);'
    ),
    _classify_raw_database(
      'CREATE TABLE project_state (id INTEGER PRIMARY KEY);'
    ),
    _classify_raw_database(
      'CREATE TABLE project_charter_history (id INTEGER PRIMARY KEY);'
    ),
    _classify_raw_database(
      'CREATE TABLE legacy_lifecycle (id INTEGER PRIMARY KEY);'
    ),
    _classify_raw_database(
      """
      CREATE TABLE stage (id INTEGER PRIMARY KEY);
      CREATE TRIGGER stage_delete
      BEFORE DELETE ON stage
      BEGIN
        SELECT RAISE(ABORT, 'stage cannot be deleted');
      END;
      """
    ),
    v7_kind,
    v6_kind,
    damaged_kind,
  )
  assert raw_observations == (
    'non-project',
    'non-project',
    'non-project',
    'project',
    'project',
    'project',
    'project',
    'project',
    'project',
    'project',
    'project',
  )

  corrupt_bytes = bytearray(v7_snapshot)
  corrupt_bytes[100:200] = b'\xff' * 100
  corrupt_db = sqlite3.connect(':memory:')
  non_sqlite_db = sqlite3.connect(':memory:')
  try:
    corrupt_db.deserialize(bytes(corrupt_bytes))
    non_sqlite_db.deserialize(b'not a sqlite database')
    corrupt_result = schema.classify_database(corrupt_db)
    non_sqlite_result = schema.classify_database(non_sqlite_db)
    assert (corrupt_result, non_sqlite_result) == (
      schema.CorruptDatabase('database disk image is malformed'),
      schema.CorruptDatabase('file is not a database'),
    )
  finally:
    non_sqlite_db.close()
    corrupt_db.close()

  class _ExtendedCorruptConnection(sqlite3.Connection):
    def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor:
      del sql, parameters
      err = sqlite3.OperationalError('corrupt index')
      err.sqlite_errorcode = sqlite3.SQLITE_CORRUPT | (1 << 8)
      raise err

  ext_corrupt_db = sqlite3.connect(
    ':memory:', factory=_ExtendedCorruptConnection
  )
  try:
    ext_corrupt_result = schema.classify_database(ext_corrupt_db)
    assert ext_corrupt_result == schema.CorruptDatabase('corrupt index')
  finally:
    ext_corrupt_db.close()

  class _IoErrConnection(sqlite3.Connection):
    def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor:
      del sql, parameters
      err = sqlite3.OperationalError('disk I/O error')
      err.sqlite_errorcode = sqlite3.SQLITE_IOERR
      raise err

  io_db = sqlite3.connect(':memory:', factory=_IoErrConnection)
  try:
    with pytest.raises(sqlite3.OperationalError) as io_err:
      schema.classify_database(io_db)
    assert (
      str(io_err.value),
      schema.is_corrupt_sqlite_error(io_err.value),
    ) == ('disk I/O error', False)
  finally:
    io_db.close()
