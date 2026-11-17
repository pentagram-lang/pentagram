import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import pytest
from pytest import MonkeyPatch

from proj import core, schema, service, store
from proj.schema_test import downgrade_v7_to_v6

_NOW = 1_700_000_000
_NAME = core.ProjectName.parse('demo')
_CHARTER = core.CharterInput.parse(
  objective='Store module delivery',
  scope='Backend and store lifecycle',
  non_goals='CLI shell',
  constraints='No unguarded errors',
  acceptance='All store checks pass',
)


@dataclass(slots=True)
class _MemdbSlot:
  uri: str
  anchor: sqlite3.Connection
  ctime_ns: int


@dataclass(slots=True)
class MemdbBackend:
  """In-memory SQLite VFS backend implementing StoreBackend for tests."""

  root: Path = Path('/memdb-root')
  now: list[int] = field(default_factory=lambda: [_NOW])
  default_ctime_ns: int = 1_000
  uri_prefix: str = 'memdb'
  rename_fault: Callable[[PurePosixPath, PurePosixPath], None] | None = (
    None
  )
  unlink_fault: Callable[[PurePosixPath], None] | None = None
  is_file_fault: Callable[[PurePosixPath], None] | None = None
  _dirs: set[PurePosixPath] = field(default_factory=set)
  _files: dict[PurePosixPath, _MemdbSlot] = field(default_factory=dict)
  _next_id: int = 1

  def is_dir(self, rel_path: PurePosixPath) -> bool:
    return rel_path in self._dirs

  def is_file(self, rel_path: PurePosixPath) -> bool:
    if self.is_file_fault is not None:
      self.is_file_fault(rel_path)
    return rel_path in self._files

  def exists(self, rel_path: PurePosixPath) -> bool:
    return rel_path in self._files or rel_path in self._dirs

  def ctime_ns(self, rel_path: PurePosixPath) -> int:
    return self._files[rel_path].ctime_ns

  def list_sqlite_stems(self) -> tuple[str, ...]:
    tmp = PurePosixPath('.tmp')
    return tuple(
      sorted(
        path.name.removesuffix(core.PROJECT_SUFFIX)
        for path in self._files
        if path.parent == tmp and path.name.endswith(core.PROJECT_SUFFIX)
      )
    )

  def mkdir(self, rel_path: PurePosixPath) -> None:
    current = rel_path
    while str(current) not in ('.', ''):
      self._dirs.add(current)
      current = current.parent

  def rename(self, src: PurePosixPath, dst: PurePosixPath) -> None:
    if self.rename_fault is not None:
      self.rename_fault(src, dst)
    slot = self._files.pop(src)
    replaced = self._files.pop(dst, None)
    if replaced is not None:
      replaced.anchor.close()
    self._files[dst] = slot

  def unlink(self, rel_path: PurePosixPath) -> None:
    if self.unlink_fault is not None:
      self.unlink_fault(rel_path)
    slot = self._files.pop(rel_path, None)
    if slot is not None:
      slot.anchor.close()

  def open_raw(
    self, rel_path: PurePosixPath, *, create: bool
  ) -> sqlite3.Connection:
    slot = self._files.get(rel_path)
    if slot is None:
      if not create:
        raise FileNotFoundError(self.root / rel_path)
      uri = f'file:/{self.uri_prefix}-{id(self)}-{self._next_id}?vfs=memdb'
      self._next_id += 1
      anchor = sqlite3.connect(uri, uri=True, timeout=5)
      slot = _MemdbSlot(
        uri=uri,
        anchor=anchor,
        ctime_ns=self.default_ctime_ns,
      )
      self._files[rel_path] = slot
    connection = sqlite3.connect(slot.uri, uri=True, timeout=5)
    connection.create_function(
      'unixepoch', 0, lambda: self.now[0], deterministic=False
    )
    connection.create_function(
      'strftime',
      2,
      lambda fmt, val: str(self.now[0])
      if (fmt, val) == ('%s', 'now')
      else '',
      deterministic=False,
    )
    return connection

  def seed(self, rel_path: PurePosixPath, snapshot: bytes) -> None:
    self.mkdir(rel_path.parent)
    conn = self.open_raw(rel_path, create=True)
    src = sqlite3.connect(':memory:')
    try:
      src.deserialize(snapshot)
      src.backup(conn)
    finally:
      src.close()
      conn.close()

  def close(self) -> None:
    for slot in self._files.values():
      slot.anchor.close()
    self._files.clear()


@pytest.fixture(scope='module')
def v7_snapshot() -> bytes:
  with _memdb_store() as (backend, project_store):
    project_store.create_project(_NAME, _CHARTER)
    raw = backend.open_raw(
      PurePosixPath('.tmp/demo.sqlite3'), create=False
    )
    try:
      return raw.serialize()
    finally:
      raw.close()


def _seed_memdb(
  backend: MemdbBackend, rel_path: PurePosixPath, snapshot: bytes
) -> None:
  backend.seed(rel_path, snapshot)


@contextmanager
def _memdb_store(
  *, default_ctime_ns: int = 1_000
) -> Iterator[tuple[MemdbBackend, store.ProjectStore]]:
  backend = MemdbBackend(default_ctime_ns=default_ctime_ns)
  try:
    yield backend, store.ProjectStore(backend)
  finally:
    backend.close()


def test_create_list_open_recreate_and_archive_disambiguation() -> None:
  with _memdb_store(default_ctime_ns=42_000) as (backend, project_store):
    assert project_store.list_projects() == ()
    assert (
      project_store.database_path(_NAME) == '/memdb-root/.tmp/demo.sqlite3'
    )
    assert (
      project_store.handoff_database_path(_NAME) == '.tmp/demo.sqlite3'
    )

    created = project_store.create_project(_NAME, _CHARTER)
    assert created == Path('/memdb-root/.tmp/demo.sqlite3')

    with project_store.open_project(_NAME) as conn:
      service.update_project_and_state(
        conn,
        service.ProjectPatch(),
        service.ProjectStatePatch(summary='First generation'),
      )

    archived_one = project_store.archive_project(_NAME)
    assert archived_one == Path(
      '/memdb-root/.tmp/archive/demo-42000.sqlite3'
    )
    assert project_store.list_projects() == ()
    with pytest.raises(core.ProjectError) as missing_err:
      with project_store.open_project(_NAME):
        pass
    assert str(missing_err.value) == 'Project does not exist: demo'

    backend.now[0] = _NOW + 5
    second_charter = core.CharterInput.parse(
      objective='Second generation',
      scope='Replacement',
      non_goals='Legacy',
      constraints='Strict',
      acceptance='Green',
    )
    project_store.create_project(_NAME, second_charter)
    replacement = core.CharterInput.parse(
      objective='Third generation',
      scope='Final',
      non_goals='Extra',
      constraints='Fast',
      acceptance='Done',
    )
    backend.now[0] = _NOW + 10
    project_store.create_project(_NAME, replacement)

    assert project_store.list_projects() == (
      service.ProjectSummary(
        name='demo',
        status='active',
        objective='Third generation',
        updated_at=_NOW + 10,
        path='/memdb-root/.tmp/demo.sqlite3',
      ),
    )
    archived_prev = backend.open_raw(
      PurePosixPath('.tmp/archive/demo-42000-1.sqlite3'), create=False
    )
    try:
      schema.configure_connection(archived_prev)
      assert service.read_project_summary(
        archived_prev, 'archived://demo'
      ) == service.ProjectSummary(
        name='demo',
        status='active',
        objective='Second generation',
        updated_at=_NOW + 5,
        path='archived://demo',
      )
    finally:
      archived_prev.close()

    assert project_store.archive_project(_NAME) == Path(
      '/memdb-root/.tmp/archive/demo-42000-2.sqlite3'
    )


def _downgrade_v7_to_v6(raw: sqlite3.Connection) -> None:
  downgrade_v7_to_v6(raw)
  raw.execute(
    'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
    "VALUES (1, 'Stage v6', 'Done', ?, ?)",
    (_NOW, _NOW),
  )
  raw.execute(
    'INSERT INTO goal (id, text, created_at, started_at, updated_at) '
    "VALUES (1, 'Goal v6', ?, 0, ?)",
    (_NOW, _NOW),
  )
  raw.execute('INSERT INTO goal_stage (goal_id, stage_id) VALUES (1, 1)')
  raw.execute(
    "UPDATE goal SET status = 'active', ever_activated = 1, "
    'started_at = ? WHERE id = 1',
    (_NOW,),
  )
  raw.execute(
    'INSERT INTO task '
    '(id, goal_id, stage_id, title, purpose, scope, exclusions, result, '
    'completion_evidence, created_at, updated_at) '
    "VALUES (1, 1, 1, 'Task v6', 'p', 's', 'e', 'r', 'ce', ?, ?)",
    (_NOW, _NOW),
  )
  raw.commit()


def test_open_rejects_version_mismatch_and_persists_v6_migration(
  v7_snapshot: bytes,
) -> None:
  with _memdb_store() as (backend, project_store):
    db_rel = PurePosixPath('.tmp/demo.sqlite3')
    _seed_memdb(backend, db_rel, v7_snapshot)
    raw = backend.open_raw(db_rel, create=False)
    try:
      raw.execute('PRAGMA user_version = 99')
    finally:
      raw.close()

    with pytest.raises(core.ProjectError) as version_err:
      with project_store.open_project(_NAME):
        pass
    assert str(version_err.value) == (
      'Unsupported project schema version 99; expected 7: '
      '/memdb-root/.tmp/demo.sqlite3'
    )

    corrupt_name = core.ProjectName.parse('broken')
    backend.mkdir(PurePosixPath('.tmp'))
    corrupt_conn = backend.open_raw(
      PurePosixPath('.tmp/broken.sqlite3'), create=True
    )
    try:
      corrupt_conn.execute('CREATE TABLE bogus (id INTEGER PRIMARY KEY)')
      corrupt_conn.execute('PRAGMA user_version = 7')
      corrupt_conn.commit()
    finally:
      corrupt_conn.close()
    with pytest.raises(core.ProjectError) as broken_err:
      with project_store.open_project(corrupt_name):
        pass
    assert str(broken_err.value) == (
      'Project schema is incomplete: no such table: project'
    )

  with _memdb_store() as (backend, project_store):
    db_rel = PurePosixPath('.tmp/demo.sqlite3')
    _seed_memdb(backend, db_rel, v7_snapshot)
    raw = backend.open_raw(db_rel, create=False)
    try:
      _downgrade_v7_to_v6(raw)
    finally:
      raw.close()

    expected_tables = (
      ((1, 'Goal v6', 'active', '', 1, _NOW, _NOW, None, _NOW),),
      ((1, 'Stage v6', 'Done', '', '', '', 0, 0, _NOW, _NOW, _NOW),),
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

    with project_store.open_project(_NAME) as migrated:
      assert (
        migrated.execute('PRAGMA user_version').fetchone()[0],
        tuple(
          tuple(row)
          for row in migrated.execute('SELECT * FROM goal ORDER BY id')
        ),
        tuple(
          tuple(row)
          for row in migrated.execute('SELECT * FROM stage ORDER BY id')
        ),
        tuple(
          tuple(row)
          for row in migrated.execute(
            'SELECT * FROM goal_stage ORDER BY goal_id, stage_id'
          )
        ),
        tuple(
          tuple(row)
          for row in migrated.execute('SELECT * FROM task ORDER BY id')
        ),
      ) == (7, *expected_tables)

    check_persisted = backend.open_raw(db_rel, create=False)
    try:
      assert (
        check_persisted.execute('PRAGMA user_version').fetchone()[0] == 7
      )
    finally:
      check_persisted.close()


def test_create_project_install_restore_and_cleanup_error_recovery() -> (
  None
):
  with _memdb_store(default_ctime_ns=77) as (backend, project_store):

    def fail_initial_install(
      src: PurePosixPath, dst: PurePosixPath
    ) -> None:
      raise OSError('disk full')

    backend.rename_fault = fail_initial_install
    with pytest.raises(core.ProjectError) as install_err:
      project_store.create_project(_NAME, _CHARTER)
    db_path = '/memdb-root/.tmp/demo.sqlite3'
    assert str(install_err.value) == (
      f'Could not install project database at {db_path}: disk full'
    )
    assert project_store.list_projects() == ()

    backend.rename_fault = None
    project_store.create_project(_NAME, _CHARTER)

    def fail_second_rename(src: PurePosixPath, dst: PurePosixPath) -> None:
      if dst == PurePosixPath('.tmp/demo.sqlite3') and src.name.endswith(
        '.tmp'
      ):
        raise OSError('install blocked')

    backend.rename_fault = fail_second_rename
    new_charter = core.CharterInput.parse(objective='New objective')
    with pytest.raises(core.ProjectError) as recovered_err:
      project_store.create_project(_NAME, new_charter)
    assert str(recovered_err.value) == (
      f'Could not install project database at {db_path}: install blocked'
    )
    backend.rename_fault = None
    assert project_store.list_projects() == (
      service.ProjectSummary(
        name='demo',
        status='active',
        objective='Store module delivery',
        updated_at=_NOW,
        path=db_path,
      ),
    )

    def fail_install_and_restore(
      src: PurePosixPath, dst: PurePosixPath
    ) -> None:
      if dst == PurePosixPath('.tmp/demo.sqlite3'):
        if src.name.endswith('.tmp'):
          raise OSError('install crash')
        raise OSError('restore crash')

    backend.rename_fault = fail_install_and_restore
    with pytest.raises(core.ProjectError) as restore_err:
      project_store.create_project(_NAME, new_charter)
    archived_path = Path('/memdb-root/.tmp/archive/demo-77.sqlite3')
    remaining_temps = [
      p
      for p in backend._files
      if p.parent == PurePosixPath('.tmp') and p.name.endswith('.tmp')
    ]
    assert len(remaining_temps) == 1
    temp_path = Path('/memdb-root') / remaining_temps[0]
    assert str(restore_err.value) == (
      f'Could not install project database at {db_path}: '
      'install crash; the previous database could not be restored from '
      f'{archived_path}: restore crash; the new database remains at '
      f'{temp_path}'
    )

  with _memdb_store() as (backend, project_store):

    def fail_rename(src: PurePosixPath, dst: PurePosixPath) -> None:
      raise OSError('rename failed')

    def fail_unlink(rel_path: PurePosixPath) -> None:
      raise OSError('unlink failed')

    backend.rename_fault = fail_rename
    backend.unlink_fault = fail_unlink
    with pytest.raises(core.ProjectError) as cleanup_err:
      project_store.create_project(_NAME, _CHARTER)
    remaining_temps = [
      p
      for p in backend._files
      if p.parent == PurePosixPath('.tmp') and p.name.endswith('.tmp')
    ]
    assert len(remaining_temps) == 1
    temp_path = Path('/memdb-root') / remaining_temps[0]
    assert str(cleanup_err.value) == (
      f'Could not install project database at {db_path}: '
      f'rename failed; the temporary database remains at {temp_path}: '
      'unlink failed'
    )

  with _memdb_store() as (backend, project_store):

    def deny_stat(rel_path: PurePosixPath) -> None:
      raise PermissionError(f'stat denied: {rel_path}')

    backend.is_file_fault = deny_stat
    with pytest.raises(core.ProjectError) as open_stat_err:
      with project_store.open_project(_NAME):
        pass
    with pytest.raises(core.ProjectError) as archive_stat_err:
      project_store.archive_project(_NAME)
    assert (str(open_stat_err.value), str(archive_stat_err.value)) == (
      'Project database could not be validated: '
      '/memdb-root/.tmp/demo.sqlite3: stat denied: .tmp/demo.sqlite3',
      'Could not archive project database at '
      '/memdb-root/.tmp/demo.sqlite3: stat denied: .tmp/demo.sqlite3',
    )


def test_host_store_special_names_and_archive(tmp_path: Path) -> None:
  project_store = store.ProjectStore.from_root(tmp_path)
  special = core.ProjectName.parse('a?b#c % " ✓')
  leading = core.ProjectName.parse('-leading')

  project_store.create_project(special, _CHARTER)
  project_store.create_project(leading, _CHARTER)
  replacement = core.CharterInput.parse(objective='Replaced special')
  project_store.create_project(special, replacement)

  archived = list((tmp_path / '.tmp' / 'archive').glob('*.sqlite3'))
  assert len(archived) == 1
  special_path = project_store.database_path(special)
  leading_path = project_store.database_path(leading)
  with project_store.open_project(special) as conn:
    loaded = service.read_project(conn, special_path)
  with project_store.open_project(leading) as conn:
    loaded_leading = service.read_project_summary(conn, leading_path)
  special_ts = loaded.project.updated_at
  leading_ts = loaded_leading.updated_at
  summaries = project_store.list_projects()
  expected_leading_summary = service.ProjectSummary(
    name='-leading',
    status='active',
    objective='Store module delivery',
    updated_at=leading_ts,
    path=leading_path,
  )
  expected_special_summary = service.ProjectSummary(
    name='a?b#c % " ✓',
    status='active',
    objective='Replaced special',
    updated_at=special_ts,
    path=special_path,
  )
  assert (loaded, loaded_leading, summaries) == (
    service.ProjectView(
      path=special_path,
      project=service.ProjectRecord(
        id=1,
        name='a?b#c % " ✓',
        objective='Replaced special',
        scope='',
        non_goals='',
        constraints_text='',
        acceptance='',
        created_at=special_ts,
        updated_at=special_ts,
        charter_context_status='current',
        status='active',
        completed_at=None,
      ),
      state=service.ProjectState(
        id=1,
        summary='',
        next_action='',
        updated_at=special_ts,
        revision=0,
      ),
      goal=None,
      charter_history=(),
    ),
    expected_leading_summary,
    (expected_leading_summary, expected_special_summary),
  )


class _CloseErrorConnection(sqlite3.Connection):
  def close(self) -> None:
    try:
      super().close()
    finally:
      raise sqlite3.OperationalError('close failed')


def test_from_root_and_open_close_error_adaptation(
  tmp_path: Path, monkeypatch: MonkeyPatch, v7_snapshot: bytes
) -> None:
  with _memdb_store() as (backend, project_store):
    db_rel = PurePosixPath('.tmp/demo.sqlite3')
    _seed_memdb(backend, db_rel, v7_snapshot)
    slot = backend._files[db_rel]

    def open_closing_error(
      _self: MemdbBackend, _rel_path: PurePosixPath, *, create: bool
    ) -> sqlite3.Connection:
      assert not create
      return sqlite3.connect(
        slot.uri, uri=True, timeout=5, factory=_CloseErrorConnection
      )

    monkeypatch.setattr(MemdbBackend, 'open_raw', open_closing_error)
    with pytest.raises(core.ProjectError) as close_err:
      with project_store.open_project(_NAME):
        pass
    assert str(close_err.value) == (
      'Project database could not be closed: '
      '/memdb-root/.tmp/demo.sqlite3: close failed'
    )

  def broken_resolve(self: Path) -> Path:
    raise OSError('permission denied')

  monkeypatch.setattr(Path, 'resolve', broken_resolve)
  with pytest.raises(core.ProjectError) as resolve_err:
    store.ProjectStore.from_root(tmp_path)
  assert str(resolve_err.value) == (
    f'Could not resolve project root {tmp_path}: permission denied'
  )
