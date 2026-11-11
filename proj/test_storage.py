import sqlite3
from pathlib import Path

import pytest

from proj import project, storage
from proj.errors import ProjectError
from proj.test_support import ProjectWorld, rewrite_project_database


def _downgrade_goal_schema_to_v6(path: Path) -> None:
  connection = storage.connect(path)
  try:
    goal_triggers = [
      row['sql']
      for row in connection.execute(
        'SELECT sql FROM sqlite_master '
        "WHERE type = 'trigger' AND tbl_name = 'goal'"
      )
    ]
    connection.execute('PRAGMA foreign_keys = OFF')
    connection.execute('BEGIN IMMEDIATE')
    for trigger_name in storage.V6_TRIGGER_NAMES:
      connection.execute(f'DROP TRIGGER "{trigger_name}"')
    connection.execute(
      """
      CREATE TEMP TABLE goal_migration_copy AS
      SELECT id, text, status, status_reason, ever_activated, created_at,
        started_at, achieved_at, updated_at
      FROM goal
      """
    )
    connection.execute('DROP TABLE goal')
    connection.execute(storage.GOAL_TABLE_SQL_V6)
    connection.execute(
      """
      INSERT INTO goal (
        id, text, status, status_reason, ever_activated, created_at,
        started_at, achieved_at, updated_at
      ) SELECT
        id, text, status, status_reason, ever_activated, created_at,
        started_at, achieved_at, updated_at
      FROM goal_migration_copy
      """
    )
    connection.execute('DROP TABLE goal_migration_copy')
    for trigger_sql in goal_triggers:
      if not any(
        f'CREATE TRIGGER {name}\n' in trigger_sql
        for name in storage.V6_TRIGGER_NAMES
      ):
        connection.execute(trigger_sql)
    connection.execute('CREATE INDEX goal_status_index ON goal(status)')
    connection.execute(
      """
      CREATE UNIQUE INDEX one_active_goal_index
      ON goal(status) WHERE status = 'active'
      """
    )
    for trigger_sql in storage.V6_TRIGGER_SQL:
      connection.execute(trigger_sql)
    connection.execute('PRAGMA user_version = 6')
    connection.commit()
    assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
  finally:
    if connection.in_transaction:
      connection.rollback()
    connection.close()


def _project_rows(
  path: str | Path,
) -> dict[str, tuple[tuple[object, ...], ...]]:
  connection = sqlite3.connect(path)
  try:
    rows: dict[str, tuple[tuple[object, ...], ...]] = {}
    for table_row in connection.execute(
      'SELECT name FROM sqlite_master '
      "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
      table = table_row[0]
      columns = [
        row[1]
        for row in connection.execute(f'PRAGMA table_info("{table}")')
      ]
      selected = ', '.join(f'"{column}"' for column in columns)
      rows[table] = tuple(
        tuple(row)
        for row in connection.execute(
          f'SELECT {selected} FROM "{table}" ORDER BY rowid'
        )
      )
    return rows
  finally:
    connection.close()


@pytest.mark.parametrize(
  'name',
  [
    'sample',
    '-leading-hyphen',
    'spaces and quotes "',
    'printable-✓',
  ],
  ids=('ordinary', 'leading-hyphen', 'shell-text', 'unicode'),
)
def test_project_name_accepts_printable_single_path_components(
  name: str,
) -> None:
  assert storage.validate_project_name(name) == name


@pytest.mark.parametrize(
  'name',
  [
    '',
    '.',
    '..',
    'nested/path',
    r'nested\path',
    'name.sqlite3',
    'line\nfeed',
  ],
  ids=(
    'empty',
    'dot',
    'dot-dot',
    'forward-slash',
    'backslash',
    'database-suffix',
    'control-character',
  ),
)
def test_project_name_rejects_unsupported_addresses(name: str) -> None:
  with pytest.raises(ProjectError) as error:
    storage.validate_project_name(name)

  assert str(error.value) == (
    'Project names must be printable, non-empty single path components '
    'of at most 200 characters without the .sqlite3 suffix.'
  )


def test_project_connection_enforces_foreign_keys_and_substantive_text(
  project_root: Path, chartered_project: str
) -> None:
  path = storage.database_path(project_root, chartered_project)
  connection = storage.connect(path)
  try:
    assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    blank = connection.execute(
      'SELECT substantive(?)', ('  ',)
    ).fetchone()[0]
    substantive = connection.execute(
      'SELECT substantive(?)', (' x ',)
    ).fetchone()[0]
    assert blank == 0
    assert substantive == 1
    with pytest.raises(sqlite3.IntegrityError) as error:
      connection.execute(
        'INSERT INTO task_tag (task_id, tag) VALUES (?, ?)',
        (10, 'missing-task'),
      )
  finally:
    connection.close()

  assert str(error.value) == 'FOREIGN KEY constraint failed'


@pytest.mark.parametrize(
  'text',
  (' \t\n', '\u2003', '\u00a0'),
  ids=('ascii-whitespace', 'em-space', 'no-break-space'),
)
def test_sqlite_and_python_share_the_unicode_substantive_text_rule(
  project_root: Path,
  chartered_project: str,
  text: str,
) -> None:
  assert storage.is_substantive(text) is False

  connection = storage.connect(
    storage.database_path(project_root, chartered_project)
  )
  try:
    assert (
      connection.execute('SELECT substantive(?)', (text,)).fetchone()[0]
      == 0
    )
  finally:
    connection.close()


@pytest.mark.parametrize(
  ('statement', 'expected'),
  [
    (
      'UPDATE task SET started_at = NULL WHERE id = ?',
      'task start time is immutable',
    ),
    (
      'UPDATE task SET completed_at = 0 WHERE id = ?',
      'task completion time must follow activation and not be in the '
      'future',
    ),
    (
      'UPDATE task SET stage_id = NULL WHERE id = ?',
      'started task cannot lose its stage relationship',
    ),
  ],
  ids=('start-time', 'completion-time', 'stage-relationship'),
)
def test_started_task_times_and_stage_relationship_are_immutable(
  project_world: ProjectWorld, statement: str, expected: str
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  connection = storage.connect(storage.database_path(root, name))
  try:
    with pytest.raises(sqlite3.IntegrityError) as error:
      connection.execute(statement, (task_id,))
    assert str(error.value) == expected
    connection.rollback()
  finally:
    connection.close()


def test_task_start_rejects_a_future_time(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  connection = storage.connect(storage.database_path(root, name))
  try:
    with pytest.raises(sqlite3.IntegrityError) as future_start:
      connection.execute(
        "UPDATE task SET status = 'active', started_at = ? WHERE id = ?",
        (1_700_000_001, task_id),
      )
    assert str(future_start.value) == (
      'task start time must be positive and not in the future'
    )
    connection.rollback()
    assert tuple(
      connection.execute(
        'SELECT status, started_at, completed_at FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
    ) == ('pending', None, None)
  finally:
    connection.close()


@pytest.mark.parametrize(
  'completion_time',
  (1_699_999_999, 1_700_000_001),
  ids=('before-start', 'after-now'),
)
def test_task_completion_rejects_invalid_times(
  project_world: ProjectWorld, completion_time: int
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  connection = storage.connect(storage.database_path(root, name))
  try:
    with pytest.raises(sqlite3.IntegrityError) as error:
      connection.execute(
        "UPDATE task SET status = 'completed', completed_at = ? "
        'WHERE id = ?',
        (completion_time, task_id),
      )
    assert str(error.value) == (
      'task completion time must follow activation and not be in the '
      'future'
    )
    connection.rollback()
    assert tuple(
      connection.execute(
        'SELECT status, started_at, completed_at FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
    ) == ('active', 1_700_000_000, None)
  finally:
    connection.close()


def test_task_logs_are_append_only(project_world: ProjectWorld) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.append_task_log(root, name, task_id, 'Preserve this history')
  connection = storage.connect(storage.database_path(root, name))
  try:
    with pytest.raises(sqlite3.IntegrityError) as update_error:
      connection.execute(
        'UPDATE task_log SET message = ? WHERE id = 1',
        ('Rewrite the history',),
      )
    assert str(update_error.value) == 'task log is append-only'
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError) as delete_error:
      connection.execute('DELETE FROM task_log WHERE id = 1')
    assert str(delete_error.value) == 'task log is append-only'
    connection.rollback()
  finally:
    connection.close()

  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'title': 'Exercise the lifecycle',
      'purpose': 'Guard state transitions',
      'scope': 'Task and stage status',
      'exclusions': 'CLI presentation',
      'result': 'Transitions produce the documented state',
      'completion_evidence': 'Exact returned lifecycle records',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [
      {
        'id': 1,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'note',
        'message': 'Preserve this history',
      }
    ],
  }


def test_open_rejects_unsupported_schema_without_rewriting_database(
  project_root: Path, chartered_project: str
) -> None:
  path = storage.database_path(project_root, chartered_project)
  connection = sqlite3.connect(path)
  connection.execute('PRAGMA user_version = 5')
  connection.commit()
  connection.close()
  before = path.read_bytes()

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_root, chartered_project)

  assert str(error.value) == (
    f'Unsupported project schema version 5; expected 7: {path}'
  )
  assert path.read_bytes() == before


def test_open_migrates_schema_6_without_changing_project_records(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  goal_id = project.create_goal(
    root,
    name,
    'Preserve the active goal during migration',
    [project_world.stage_id],
  )
  task_id = project.add_task(
    root,
    name,
    'Preserve the active task during migration',
    purpose='Verify the v6 migration',
    stage=project_world.stage_id,
    goal=goal_id,
    scope='The active project database',
    exclusions='Unrelated project records',
    result='All existing records retain their values and relationships',
    completion_evidence='Exact rows before and after migration',
  )
  project.start_task(root, name, task_id)
  project.append_task_log(
    root, name, task_id, 'Preserve this task history'
  )
  project.add_decision(root, name, 'Preserve task context', task=task_id)
  project.add_evidence(
    root, name, 'Preserve the recorded task evidence', task=task_id
  )
  path = storage.database_path(root, name)
  _downgrade_goal_schema_to_v6(path)
  before = _project_rows(path)

  connection = storage.open_project(root, name)
  try:
    assert connection.execute('PRAGMA user_version').fetchone()[0] == 7
    assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    assert tuple(
      connection.execute(
        'SELECT id, status, ever_activated FROM goal WHERE id = ?',
        (goal_id,),
      ).fetchone()
    ) == (goal_id, 'active', 1)
    assert tuple(
      connection.execute(
        'SELECT id, status, goal_id, stage_id FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
    ) == (task_id, 'active', goal_id, project_world.stage_id)
    assert [
      tuple(row)
      for row in connection.execute(
        'SELECT goal_id, stage_id FROM goal_stage WHERE goal_id = ?',
        (goal_id,),
      )
    ] == [(goal_id, project_world.stage_id)]
  finally:
    connection.close()

  assert _project_rows(path) == before


def test_incompatible_schema_6_is_rejected_without_rewriting_database(
  project_world: ProjectWorld,
) -> None:
  path = storage.database_path(project_world.root, project_world.name)
  _downgrade_goal_schema_to_v6(path)
  connection = sqlite3.connect(path)
  connection.execute(
    """
    CREATE TRIGGER unexpected_project_trigger
    BEFORE INSERT ON stage
    BEGIN
      SELECT RAISE(ABORT, 'unexpected trigger');
    END
    """
  )
  connection.commit()
  connection.close()
  before = path.read_bytes()

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_world.root, project_world.name)

  assert str(error.value) == (
    'Project schema has unexpected triggers: unexpected_project_trigger'
  )
  assert path.read_bytes() == before


def test_schema_6_migration_rolls_back_a_mid_migration_failure(
  project_world: ProjectWorld,
) -> None:
  path = storage.database_path(project_world.root, project_world.name)
  _downgrade_goal_schema_to_v6(path)
  before = path.read_bytes()
  rows_before = _project_rows(path)
  connection = storage.connect(path)
  connection.execute('CREATE TEMP TABLE goal_migration_copy (id INTEGER)')

  with pytest.raises(sqlite3.OperationalError) as error:
    storage._migrate_schema_6_to_7(connection)

  assert str(error.value) == ('table goal_migration_copy already exists')
  assert connection.execute('PRAGMA user_version').fetchone()[0] == 6
  assert connection.execute('PRAGMA foreign_keys').fetchone()[0] == 1
  connection.close()
  assert path.read_bytes() == before
  assert _project_rows(path) == rows_before


def test_open_rejects_an_active_task_with_a_forged_incomplete_charter(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  path = storage.database_path(root, name)
  trigger_names = ('project_charter_update', 'project_charter_active_task')
  rewrite_project_database(
    path,
    trigger_names,
    'UPDATE project SET scope = ? WHERE id = 1',
    ('',),
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(root, name)

  assert str(error.value) == (
    'Project has an incomplete post-execution charter'
  )


def test_open_rejects_a_blocked_task_without_an_open_blocker(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  path = storage.database_path(root, name)
  rewrite_project_database(
    path,
    ('blocked_task_update',),
    "UPDATE task SET status = 'blocked' WHERE id = ?",
    (task_id,),
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(root, name)

  assert str(error.value) == (
    f'Project has a blocked task without an open blocker: {task_id}'
  )


def test_open_rejects_a_forged_unicode_whitespace_charter(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  project.start_task(root, name, project_world.task_id)
  rewrite_project_database(
    storage.database_path(root, name),
    ('project_charter_update', 'project_charter_active_task'),
    'UPDATE project SET scope = ? WHERE id = 1',
    ('\u2003',),
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(root, name)

  assert str(error.value) == (
    'Project has an incomplete post-execution charter'
  )


def test_open_rejects_a_forged_record_with_missing_task_context(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  decision_id = project.add_decision(
    root,
    name,
    'Record the task context before it changes',
    task=project_world.task_id,
  )
  rewrite_project_database(
    storage.database_path(root, name),
    ('decision_relationship_update',),
    'UPDATE decision SET stage_id = NULL WHERE id = ?',
    (decision_id,),
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(root, name)

  assert str(error.value) == (
    f'Project has incoherent record context: decision {decision_id}'
  )


def test_open_rejects_a_forged_blocker_with_mismatched_task_context(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  other_stage = project.add_stage(
    root,
    name,
    'Other stage',
    'Keep blocker context attached to the task',
    exit_evidence='The task context remains coherent',
  )
  blocker_id = project.block_task(
    root,
    name,
    project_world.task_id,
    'The task input is missing',
    required='Provide the task input',
  )
  rewrite_project_database(
    storage.database_path(root, name),
    ('blocker_relationship_update',),
    'UPDATE blocker SET stage_id = ? WHERE id = ?',
    (other_stage, blocker_id),
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(root, name)

  assert str(error.value) == (
    f'Project has an incoherent blocker: {blocker_id}'
  )


def test_open_rejects_a_database_with_a_forged_table_constraint(
  project_world: ProjectWorld,
) -> None:
  path = storage.database_path(project_world.root, project_world.name)
  rewrite_project_database(
    path,
    ('task_status_transition',),
    "UPDATE task SET status = 'unknown' WHERE id = ?",
    (project_world.task_id,),
    ignore_check_constraints=True,
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_world.root, project_world.name)

  assert str(error.value) == (
    'Project database integrity check failed: CHECK constraint failed '
    'in task'
  )


def test_open_rejects_a_foreign_key_violation(
  project_root: Path, chartered_project: str
) -> None:
  path = storage.database_path(project_root, chartered_project)
  connection = storage.connect(path)
  connection.execute('PRAGMA foreign_keys = OFF')
  connection.execute(
    'INSERT INTO task_tag (task_id, tag) VALUES (?, ?)',
    (999, 'orphan'),
  )
  connection.commit()
  connection.close()

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_root, chartered_project)

  assert str(error.value) == (
    'Project has a foreign-key violation: task_tag row 1 references task'
  )


def test_open_rejects_a_forged_legacy_charter_context(
  project_root: Path, chartered_project: str
) -> None:
  rewrite_project_database(
    storage.database_path(project_root, chartered_project),
    ('project_charter_context_update',),
    "UPDATE project SET charter_context_status = 'legacy-incomplete' "
    'WHERE id = 1',
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_root, chartered_project)

  assert str(error.value) == (
    'Project has an incomplete post-execution charter'
  )


def test_open_rejects_a_persisted_goal_construction_state(
  project_root: Path, chartered_project: str
) -> None:
  rewrite_project_database(
    storage.database_path(project_root, chartered_project),
    ('goal_initial_status',),
    'INSERT INTO goal (text, created_at, started_at, updated_at) '
    'VALUES (?, ?, ?, ?)',
    (
      'A construction state must not persist',
      1_700_000_000,
      0,
      1_700_000_000,
    ),
  )

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_root, chartered_project)

  assert str(error.value) == 'Project has an invalid goal lifecycle: 1'


@pytest.mark.parametrize(
  ('statement', 'expected'),
  [
    (
      'DROP TRIGGER task_delete',
      'Project schema is incomplete; missing triggers: task_delete',
    ),
    (
      'CREATE INDEX extra_task_title ON task(title)',
      'Project schema has unexpected indexes on canonical tables: '
      'extra_task_title',
    ),
    (
      'CREATE TRIGGER unexpected_stage_insert BEFORE INSERT ON stage '
      "BEGIN SELECT RAISE(ABORT, 'unexpected'); END",
      'Project schema has unexpected triggers: unexpected_stage_insert',
    ),
  ],
  ids=(
    'missing-lifecycle-trigger',
    'extra-canonical-index',
    'unexpected-trigger',
  ),
)
def test_open_rejects_noncanonical_schema_objects(
  project_root: Path,
  chartered_project: str,
  statement: str,
  expected: str,
) -> None:
  path = storage.database_path(project_root, chartered_project)
  connection = sqlite3.connect(path)
  connection.execute(statement)
  connection.commit()
  connection.close()

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_root, chartered_project)

  assert str(error.value) == expected


def test_open_rejects_a_same_named_incompatible_index(
  project_root: Path, chartered_project: str
) -> None:
  path = storage.database_path(project_root, chartered_project)
  connection = sqlite3.connect(path)
  connection.execute('DROP INDEX task_stage_index')
  connection.execute('CREATE INDEX task_stage_index ON task(status)')
  connection.commit()
  connection.close()

  with pytest.raises(ProjectError) as error:
    storage.open_project(project_root, chartered_project)

  assert str(error.value) == (
    'Project schema has incompatible indexes: task_stage_index'
  )


def test_open_allows_an_additional_table_and_its_private_index(
  project_root: Path, chartered_project: str
) -> None:
  path = storage.database_path(project_root, chartered_project)
  connection = sqlite3.connect(path)
  connection.execute('CREATE TABLE local_cache (value TEXT NOT NULL)')
  connection.execute(
    'CREATE INDEX local_cache_value ON local_cache(value)'
  )
  connection.commit()
  connection.close()

  opened = storage.open_project(project_root, chartered_project)
  try:
    name = opened.execute('SELECT name FROM project').fetchone()['name']
    assert name == chartered_project
  finally:
    opened.close()


def test_recreating_project_archives_the_previous_database(
  project_root: Path, chartered_project: str
) -> None:
  project.update_state(
    project_root, chartered_project, summary='Old state'
  )

  project.create_project(
    project_root,
    chartered_project,
    'Replacement objective',
    scope='Replacement scope',
    non_goals='No unrelated work',
    constraints='Preserve history',
    acceptance='Replacement evidence',
  )

  archive_directory = project_root / '.tmp' / 'archive'
  archived = list(archive_directory.glob('sample-*.sqlite3'))
  assert len(archived) == 1
  assert project.read_project(project_root, chartered_project) == {
    'path': str(storage.database_path(project_root, chartered_project)),
    'project': {
      'id': 1,
      'name': 'sample',
      'objective': 'Replacement objective',
      'scope': 'Replacement scope',
      'non_goals': 'No unrelated work',
      'constraints_text': 'Preserve history',
      'acceptance': 'Replacement evidence',
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'charter_context_status': 'current',
      'status': 'active',
      'completed_at': None,
    },
    'state': {
      'id': 1,
      'summary': '',
      'next_action': '',
      'updated_at': 1_700_000_000,
      'revision': 0,
    },
    'goal': None,
    'charter_history': [],
  }
  assert project.list_projects(project_root) == [
    {
      'name': 'sample',
      'status': 'active',
      'objective': 'Replacement objective',
      'updated_at': 1_700_000_000,
      'path': str(storage.database_path(project_root, chartered_project)),
    }
  ]
  archived_connection = storage.connect(archived[0])
  try:
    assert dict(
      archived_connection.execute('SELECT * FROM project').fetchone()
    ) == {
      'id': 1,
      'name': 'sample',
      'objective': 'Deliver a reliable project workflow',
      'scope': 'Project state and commands',
      'non_goals': 'Language runtime behaviour',
      'constraints_text': 'Preserve append-only history',
      'acceptance': 'Lifecycle tests and review',
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'charter_context_status': 'current',
    }
    assert dict(
      archived_connection.execute('SELECT * FROM project_state').fetchone()
    ) == {
      'id': 1,
      'summary': 'Old state',
      'next_action': '',
      'updated_at': 1_700_000_000,
      'revision': 1,
    }
  finally:
    archived_connection.close()
