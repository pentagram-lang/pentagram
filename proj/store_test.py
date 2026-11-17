import ctypes
import errno
import hashlib
import os
import sqlite3
import stat
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import ClassVar

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
  raw_bytes: bytes | None = None


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
  _next_temp_id: int = 1

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
    if tmp in self._files:
      raise NotADirectoryError(
        errno.ENOTDIR,
        os.strerror(errno.ENOTDIR),
        os.fspath(self.root / tmp),
      )
    if tmp not in self._dirs:
      return ()
    return tuple(
      sorted(
        path.name.removesuffix(core.PROJECT_SUFFIX)
        for path in self._files
        if path.parent == tmp and path.name.endswith(core.PROJECT_SUFFIX)
      )
    )

  def next_temp_suffix(self) -> str:
    suffix = f'temp-{self._next_temp_id}'
    self._next_temp_id += 1
    return suffix

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
    self, rel_path: PurePosixPath, *, mode: store.StoreOpenMode
  ) -> sqlite3.Connection:
    if mode != 'rwc' and self.is_file_fault is not None:
      self.is_file_fault(rel_path)
    slot = self._files.get(rel_path)
    if slot is None:
      if mode != 'rwc':
        raise FileNotFoundError(
          errno.ENOENT,
          os.strerror(errno.ENOENT),
          os.fspath(self.root / rel_path),
        )
      uri = f'file:/{self.uri_prefix}-{id(self)}-{self._next_id}?vfs=memdb'
      self._next_id += 1
      anchor = sqlite3.connect(uri, uri=True, timeout=5)
      slot = _MemdbSlot(
        uri=uri,
        anchor=anchor,
        ctime_ns=self.default_ctime_ns,
      )
      self._files[rel_path] = slot
    if slot.raw_bytes is not None:
      connection = sqlite3.connect(':memory:')
      connection.deserialize(slot.raw_bytes)
      if mode == 'ro':
        connection.execute('PRAGMA query_only = ON')
    else:
      connect_uri = (
        f'{slot.uri}&mode=ro&immutable=1' if mode == 'ro' else slot.uri
      )
      connection = sqlite3.connect(connect_uri, uri=True, timeout=5)
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
    conn = self.open_raw(rel_path, mode='rwc')
    if not snapshot:
      conn.close()
      return
    src = sqlite3.connect(':memory:')
    try:
      src.deserialize(snapshot)
      try:
        src.backup(conn)
      except sqlite3.DatabaseError:
        self._files[rel_path].raw_bytes = snapshot
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
    raw = backend.open_raw(PurePosixPath('.tmp/demo.sqlite3'), mode='ro')
    try:
      return raw.serialize()
    finally:
      raw.close()


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
      PurePosixPath('.tmp/archive/demo-42000-1.sqlite3'), mode='ro'
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
    backend.seed(db_rel, v7_snapshot)
    raw = backend.open_raw(db_rel, mode='rw')
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
      PurePosixPath('.tmp/broken.sqlite3'), mode='rwc'
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
      'Project schema is incomplete; missing tables: '
      'blocker, decision, evidence, goal, goal_stage, '
      'legacy_lifecycle, project, project_charter_history, '
      'project_state, stage, stage_achievement, stage_dependency, '
      'task, task_log, task_tag: /memdb-root/.tmp/broken.sqlite3'
    )

  with _memdb_store() as (backend, project_store):
    db_rel = PurePosixPath('.tmp/demo.sqlite3')
    backend.seed(db_rel, v7_snapshot)
    raw = backend.open_raw(db_rel, mode='rw')
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

    check_persisted = backend.open_raw(db_rel, mode='ro')
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
    temp_path = Path('/memdb-root/.tmp/.demo-temp-4.tmp')
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
    temp_path = Path('/memdb-root/.tmp/.demo-temp-1.tmp')
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


def test_host_backend_uri_listing_modes_and_special_names(
  monkeypatch: MonkeyPatch,
) -> None:
  root = Path('/host root')
  backend = store.HostStoreBackend(root)
  ticks = iter((123_456, 789_012))
  tokens = iter(('deadbeef', 'cafebabe'))
  with monkeypatch.context() as mp:
    mp.setattr(store.time, 'time_ns', lambda: next(ticks))
    mp.setattr(store.os, 'getpid', lambda: 4242)
    mp.setattr(store.secrets, 'token_hex', lambda n: next(tokens))
    temp_suffixes = (
      backend.next_temp_suffix(),
      backend.next_temp_suffix(),
    )

  special_host_path = Path('/host root/.tmp/a?b#c % " ✓.sqlite3')
  double_slash_host_path = Path('//host-ns/.tmp/double-slash.sqlite3')
  assert (
    store._sqlite_file_uri(special_host_path, 'ro'),
    store._sqlite_file_uri(Path('/host/demo.sqlite3'), 'rw'),
    store._sqlite_file_uri(Path('/host/demo.sqlite3'), 'rwc'),
    store._sqlite_file_uri(double_slash_host_path, 'ro'),
    store._sqlite_file_uri(double_slash_host_path, 'rw'),
    store._sqlite_file_uri(double_slash_host_path, 'rwc'),
    temp_suffixes,
  ) == (
    'file:/host%20root/.tmp/a%3Fb%23c%20%25%20%22%20%E2%9C%93.sqlite3'
    '?mode=ro&immutable=1',
    'file:/host/demo.sqlite3?mode=rw',
    'file:/host/demo.sqlite3?mode=rwc',
    'file://localhost//host-ns/.tmp/double-slash.sqlite3'
    '?mode=ro&immutable=1',
    'file://localhost//host-ns/.tmp/double-slash.sqlite3?mode=rw',
    'file://localhost//host-ns/.tmp/double-slash.sqlite3?mode=rwc',
    ('123456-4242-deadbeef', '789012-4242-cafebabe'),
  )

  uri_observations: list[tuple[list[tuple[str]], str]] = []
  for host_path in (special_host_path, double_slash_host_path):
    rwc_conn: sqlite3.Connection | None = None
    rw_conn: sqlite3.Connection | None = None
    ro_conn: sqlite3.Connection | None = None
    try:
      rwc_conn = sqlite3.connect(
        f'{store._sqlite_file_uri(host_path, "rwc")}&vfs=memdb', uri=True
      )
      rw_conn = sqlite3.connect(
        f'{store._sqlite_file_uri(host_path, "rw")}&vfs=memdb', uri=True
      )
      rwc_conn.execute('CREATE TABLE item (label TEXT)')
      rwc_conn.execute("INSERT INTO item VALUES ('created')")
      rwc_conn.commit()
      rw_conn.execute("INSERT INTO item VALUES ('updated')")
      rw_conn.commit()
      ro_conn = sqlite3.connect(
        f'{store._sqlite_file_uri(host_path, "ro")}&vfs=memdb', uri=True
      )
      rows = ro_conn.execute(
        'SELECT label FROM item ORDER BY rowid'
      ).fetchall()
      with pytest.raises(sqlite3.OperationalError) as ro_err:
        ro_conn.execute('CREATE TABLE forbidden (x INT)')
      uri_observations.append((rows, str(ro_err.value)))
    finally:
      if ro_conn is not None:
        ro_conn.close()
      if rw_conn is not None:
        rw_conn.close()
      if rwc_conn is not None:
        rwc_conn.close()

  assert uri_observations == [
    ([('created',), ('updated',)], 'attempt to write a readonly database'),
    ([('created',), ('updated',)], 'attempt to write a readonly database'),
  ]

  tmp_dir = root / '.tmp'
  existing_files = {
    tmp_dir / '.sqlite3',
    tmp_dir / 'alpha.sqlite3',
    tmp_dir / 'notes.sqlite3.sqlite3',
    tmp_dir / 'onebyte.sqlite3',
  }
  existing_dirs = {tmp_dir, tmp_dir / 'dir-entry.sqlite3'}
  existing_symlinks = {
    tmp_dir / 'link.sqlite3',
    Path('/broken-link-host/.tmp'),
  }
  entry_follow_symlinks: list[bool] = []
  exists_follow_symlinks: list[tuple[Path, bool]] = []
  stat_follow_symlinks: list[tuple[Path, bool]] = []
  is_file_follow_symlinks: list[tuple[Path, bool]] = []

  @dataclass(frozen=True, slots=True)
  class _FakeEntry:
    name: str
    _is_file: bool

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
      entry_follow_symlinks.append(follow_symlinks)
      return self._is_file

  class _FakeScandir:
    def __init__(self, entries: list[_FakeEntry]) -> None:
      self._entries = entries

    def __enter__(self) -> Iterator[_FakeEntry]:
      return iter(self._entries)

    def __exit__(self, *_args: object) -> None:
      return None

  def _make_stat(mode_bits: int, size: int) -> os.stat_result:
    return os.stat_result((mode_bits, 0, 0, 1, 0, 0, size, 0, 0, 0))

  def fake_stat(
    self: Path, *, follow_symlinks: bool = True
  ) -> os.stat_result:
    stat_follow_symlinks.append((self, follow_symlinks))
    if self in existing_files:
      size = 1 if self == tmp_dir / 'onebyte.sqlite3' else 4096
      return _make_stat(stat.S_IFREG | 0o644, size)
    if not follow_symlinks and self in existing_symlinks:
      return _make_stat(stat.S_IFLNK | 0o777, 8)
    if self in existing_dirs:
      return _make_stat(stat.S_IFDIR | 0o755, 0)
    raise FileNotFoundError(
      errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(self)
    )

  def fake_exists(self: Path, *, follow_symlinks: bool = True) -> bool:
    exists_follow_symlinks.append((self, follow_symlinks))
    return (
      self in existing_files
      or self in existing_dirs
      or (not follow_symlinks and self in existing_symlinks)
    )

  def fake_is_file(self: Path, *, follow_symlinks: bool = True) -> bool:
    is_file_follow_symlinks.append((self, follow_symlinks))
    return self in existing_files

  def fake_scandir(target: str | os.PathLike[str]) -> _FakeScandir:
    target_path = Path(os.fspath(target))
    if target_path in (
      Path('/missing-host/.tmp'),
      Path('/broken-link-host/.tmp'),
    ):
      raise FileNotFoundError(
        errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(target_path)
      )
    if target_path == Path('/denied-host/.tmp'):
      raise PermissionError(
        errno.EACCES, os.strerror(errno.EACCES), str(target_path)
      )
    assert target_path == tmp_dir
    return _FakeScandir(
      [
        _FakeEntry('notes.sqlite3.sqlite3', True),
        _FakeEntry('dir-entry.sqlite3', False),
        _FakeEntry('link.sqlite3', False),
        _FakeEntry('alpha.sqlite3', True),
        _FakeEntry('.sqlite3', True),
      ]
    )

  vanished_uri = store._sqlite_file_uri(tmp_dir / 'vanished.sqlite3', 'ro')
  cantopen_file_uri = store._sqlite_file_uri(
    tmp_dir / 'cantopen-file.sqlite3', 'ro'
  )
  onebyte_uri = store._sqlite_file_uri(tmp_dir / 'onebyte.sqlite3', 'ro')
  connect_calls: list[tuple[str, float, bool]] = []
  opened_connections: list[sqlite3.Connection] = []
  onebyte_connections: list[sqlite3.Connection] = []
  real_connect = sqlite3.connect

  def fake_connect(
    target: str, *, timeout: float = 5, uri: bool = False
  ) -> sqlite3.Connection:
    connect_calls.append((target, timeout, uri))
    if target in (vanished_uri, cantopen_file_uri):
      err = sqlite3.OperationalError('unable to open database file')
      err.sqlite_errorcode = sqlite3.SQLITE_CANTOPEN | (1 << 8)
      raise err
    conn = real_connect(':memory:')
    if target == onebyte_uri:
      onebyte_connections.append(conn)
    else:
      opened_connections.append(conn)
    return conn

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'stat', fake_stat)
    mp.setattr(Path, 'exists', fake_exists)
    mp.setattr(Path, 'is_file', fake_is_file)
    mp.setattr(store.os, 'scandir', fake_scandir)
    mp.setattr(store.sqlite3, 'connect', fake_connect)

    try:
      stems = backend.list_sqlite_stems()
      missing_dir_stems = store.HostStoreBackend(
        Path('/missing-host')
      ).list_sqlite_stems()
      with pytest.raises(FileNotFoundError) as broken_link_scandir:
        store.HostStoreBackend(
          Path('/broken-link-host')
        ).list_sqlite_stems()
      with pytest.raises(PermissionError) as denied_scandir:
        store.HostStoreBackend(Path('/denied-host')).list_sqlite_stems()

      with pytest.raises(FileNotFoundError) as ro_missing:
        backend.open_raw(PurePosixPath('.tmp/missing.sqlite3'), mode='ro')
      with pytest.raises(FileNotFoundError) as rw_missing:
        backend.open_raw(PurePosixPath('.tmp/missing.sqlite3'), mode='rw')
      with pytest.raises(FileNotFoundError) as link_open_err:
        backend.open_raw(PurePosixPath('.tmp/link.sqlite3'), mode='ro')
      with pytest.raises(FileNotFoundError) as dir_open_err:
        backend.open_raw(
          PurePosixPath('.tmp/dir-entry.sqlite3'), mode='ro'
        )
      with pytest.raises(sqlite3.DatabaseError) as onebyte_err:
        backend.open_raw(PurePosixPath('.tmp/onebyte.sqlite3'), mode='ro')

      existing_files.add(tmp_dir / 'vanished.sqlite3')
      existing_files.add(tmp_dir / 'cantopen-file.sqlite3')

      def vanish_on_second_check(
        self: Path, *, follow_symlinks: bool = True
      ) -> bool:
        is_file_follow_symlinks.append((self, follow_symlinks))
        if self == tmp_dir / 'vanished.sqlite3':
          existing_files.discard(self)
          return False
        return self in existing_files

      mp.setattr(Path, 'is_file', vanish_on_second_check)
      with pytest.raises(FileNotFoundError) as cantopen_vanished:
        backend.open_raw(PurePosixPath('.tmp/vanished.sqlite3'), mode='ro')
      mp.setattr(Path, 'is_file', fake_is_file)

      with pytest.raises(sqlite3.OperationalError) as cantopen_reraised:
        backend.open_raw(
          PurePosixPath('.tmp/cantopen-file.sqlite3'), mode='ro'
        )

      backend.open_raw(PurePosixPath('.tmp/alpha.sqlite3'), mode='ro')
      backend.open_raw(PurePosixPath('.tmp/alpha.sqlite3'), mode='rw')
      backend.open_raw(PurePosixPath('.tmp/created.sqlite3'), mode='rwc')
    finally:
      for conn in opened_connections:
        conn.close()

  with pytest.raises(sqlite3.ProgrammingError) as onebyte_closed_err:
    onebyte_connections[0].execute('SELECT 1')

  assert (
    stems,
    missing_dir_stems,
    (broken_link_scandir.value.errno, str(broken_link_scandir.value)),
    (denied_scandir.value.errno, str(denied_scandir.value)),
    (ro_missing.value.errno, str(ro_missing.value)),
    (rw_missing.value.errno, str(rw_missing.value)),
    (link_open_err.value.errno, str(link_open_err.value)),
    (dir_open_err.value.errno, str(dir_open_err.value)),
    str(onebyte_err.value),
    onebyte_err.value.sqlite_errorcode,
    str(onebyte_closed_err.value),
    (cantopen_vanished.value.errno, str(cantopen_vanished.value)),
    str(cantopen_reraised.value),
    entry_follow_symlinks,
    exists_follow_symlinks,
    stat_follow_symlinks,
    is_file_follow_symlinks,
    connect_calls,
  ) == (
    ('', 'alpha', 'notes.sqlite3'),
    (),
    (
      errno.ENOENT,
      "[Errno 2] No such file or directory: '/broken-link-host/.tmp'",
    ),
    (errno.EACCES, "[Errno 13] Permission denied: '/denied-host/.tmp'"),
    (
      errno.ENOENT,
      '[Errno 2] No such file or directory: '
      "'/host root/.tmp/missing.sqlite3'",
    ),
    (
      errno.ENOENT,
      '[Errno 2] No such file or directory: '
      "'/host root/.tmp/missing.sqlite3'",
    ),
    (
      errno.ENOENT,
      '[Errno 2] No such file or directory: '
      "'/host root/.tmp/link.sqlite3'",
    ),
    (
      errno.ENOENT,
      '[Errno 2] No such file or directory: '
      "'/host root/.tmp/dir-entry.sqlite3'",
    ),
    'file is not a database',
    sqlite3.SQLITE_NOTADB,
    'Cannot operate on a closed database.',
    (
      errno.ENOENT,
      '[Errno 2] No such file or directory: '
      "'/host root/.tmp/vanished.sqlite3'",
    ),
    'unable to open database file',
    [False, False, False, False, False],
    [
      (Path('/missing-host/.tmp'), False),
      (Path('/broken-link-host/.tmp'), False),
    ],
    [
      (tmp_dir / 'missing.sqlite3', False),
      (tmp_dir / 'missing.sqlite3', False),
      (tmp_dir / 'link.sqlite3', False),
      (tmp_dir / 'dir-entry.sqlite3', False),
      (tmp_dir / 'onebyte.sqlite3', False),
      (tmp_dir / 'onebyte.sqlite3', False),
      (tmp_dir / 'vanished.sqlite3', False),
      (tmp_dir / 'cantopen-file.sqlite3', False),
      (tmp_dir / 'alpha.sqlite3', False),
      (tmp_dir / 'alpha.sqlite3', False),
    ],
    [
      (tmp_dir / 'vanished.sqlite3', False),
      (tmp_dir / 'cantopen-file.sqlite3', False),
    ],
    [
      (onebyte_uri, 5, True),
      (vanished_uri, 5, True),
      (cantopen_file_uri, 5, True),
      (
        'file:/host%20root/.tmp/alpha.sqlite3?mode=ro&immutable=1',
        5,
        True,
      ),
      ('file:/host%20root/.tmp/alpha.sqlite3?mode=rw', 5, True),
      ('file:/host%20root/.tmp/created.sqlite3?mode=rwc', 5, True),
    ],
  )

  with _memdb_store(default_ctime_ns=99_000) as (_backend, project_store):
    special = core.ProjectName.parse('a?b#c % " ✓')
    leading = core.ProjectName.parse('-leading')
    project_store.create_project(special, _CHARTER)
    project_store.create_project(leading, _CHARTER)
    replacement = core.CharterInput.parse(objective='Replaced special')
    project_store.create_project(special, replacement)

    special_path = project_store.database_path(special)
    leading_path = project_store.database_path(leading)
    with project_store.open_project(special) as conn:
      loaded = service.read_project(conn, special_path)
    with project_store.open_project(leading) as conn:
      loaded_leading = service.read_project_summary(conn, leading_path)
    summaries = project_store.list_projects()
    expected_leading_summary = service.ProjectSummary(
      name='-leading',
      status='active',
      objective='Store module delivery',
      updated_at=_NOW,
      path=leading_path,
    )
    expected_special_summary = service.ProjectSummary(
      name='a?b#c % " ✓',
      status='active',
      objective='Replaced special',
      updated_at=_NOW,
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
          created_at=_NOW,
          updated_at=_NOW,
          charter_context_status='current',
          status='active',
          completed_at=None,
        ),
        state=service.ProjectState(
          id=1,
          summary='',
          next_action='',
          updated_at=_NOW,
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
  monkeypatch: MonkeyPatch, v7_snapshot: bytes
) -> None:
  with _memdb_store() as (backend, project_store):
    db_rel = PurePosixPath('.tmp/demo.sqlite3')
    backend.seed(db_rel, v7_snapshot)
    slot = backend._files[db_rel]
    real_open_raw = MemdbBackend.open_raw

    def open_closing_error(
      _self: MemdbBackend,
      _rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      assert mode in ('ro', 'rw')
      uri = f'{slot.uri}&mode=ro' if mode == 'ro' else slot.uri
      return sqlite3.connect(
        uri, uri=True, timeout=5, factory=_CloseErrorConnection
      )

    def rw_open_closing_error(
      self: MemdbBackend,
      rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      if mode == 'rw':
        return sqlite3.connect(
          slot.uri, uri=True, timeout=5, factory=_CloseErrorConnection
        )
      return real_open_raw(self, rel_path, mode=mode)

    with monkeypatch.context() as mp:
      mp.setattr(MemdbBackend, 'open_raw', open_closing_error)
      with pytest.raises(core.ProjectError) as open_close_err:
        with project_store.open_project(_NAME):
          pass
      with pytest.raises(core.ProjectError) as list_probe_close_err:
        project_store.list_projects()
      with pytest.raises(core.ProjectError) as create_close_err:
        project_store.create_project(_NAME, _CHARTER)
      with pytest.raises(core.ProjectError) as archive_close_err:
        project_store.archive_project(_NAME)
      mp.setattr(MemdbBackend, 'open_raw', rw_open_closing_error)
      with pytest.raises(core.ProjectError) as list_rw_close_err:
        project_store.list_projects()

    def vanish_on_rw_open(
      self: MemdbBackend,
      rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      if rel_path == db_rel and mode == 'rw':
        raise FileNotFoundError(
          errno.ENOENT,
          os.strerror(errno.ENOENT),
          os.fspath(self.root / rel_path),
        )
      return real_open_raw(self, rel_path, mode=mode)

    with monkeypatch.context() as mp:
      mp.setattr(MemdbBackend, 'open_raw', vanish_on_rw_open)
      with pytest.raises(core.ProjectError) as open_vanished_err:
        with project_store.open_project(_NAME):
          pass
      listed_after_vanish = project_store.list_projects()

    def broken_configure(_connection: sqlite3.Connection) -> None:
      raise core.ProjectError('pragma configuration failed')

    with monkeypatch.context() as mp:
      mp.setattr(store, 'configure_connection', broken_configure)
      with pytest.raises(core.ProjectError) as open_cfg_err:
        with project_store.open_project(_NAME):
          pass
      with pytest.raises(core.ProjectError) as create_cfg_err:
        project_store.create_project(
          core.ProjectName.parse('fresh'), _CHARTER
        )

    yielded_conn: sqlite3.Connection | None = None
    with pytest.raises(FileNotFoundError) as body_fnf_err:
      with project_store.open_project(_NAME) as yielded_conn:
        raise FileNotFoundError(
          errno.ENOENT, os.strerror(errno.ENOENT), '/caller/missing.txt'
        )
    assert yielded_conn is not None
    with pytest.raises(sqlite3.ProgrammingError) as body_closed_err:
      yielded_conn.execute('SELECT 1')

    assert (
      str(open_close_err.value),
      str(list_probe_close_err.value),
      str(list_rw_close_err.value),
      str(create_close_err.value),
      str(archive_close_err.value),
      str(open_vanished_err.value),
      listed_after_vanish,
      str(open_cfg_err.value),
      str(create_cfg_err.value),
      backend.exists(PurePosixPath('.tmp/.fresh-temp-1.tmp')),
      (body_fnf_err.value.errno, str(body_fnf_err.value)),
      str(body_closed_err.value),
    ) == (
      'Project database could not be closed: '
      '/memdb-root/.tmp/demo.sqlite3: close failed',
      'Project database could not be validated: '
      '/memdb-root/.tmp/demo.sqlite3: close failed',
      'Project database could not be closed: '
      '/memdb-root/.tmp/demo.sqlite3: close failed',
      'Could not create project database at '
      '/memdb-root/.tmp/demo.sqlite3: close failed',
      'Could not archive project database at '
      '/memdb-root/.tmp/demo.sqlite3: close failed',
      'Project does not exist: demo',
      (),
      'pragma configuration failed: /memdb-root/.tmp/demo.sqlite3',
      'pragma configuration failed: /memdb-root/.tmp/.fresh-temp-1.tmp',
      False,
      (
        errno.ENOENT,
        "[Errno 2] No such file or directory: '/caller/missing.txt'",
      ),
      'Cannot operate on a closed database.',
    )

  non_utf8_root = Path(os.fsdecode(b'/root-\xff'))
  with pytest.raises(core.ProjectError) as direct_root_err:
    store.ProjectStore(MemdbBackend(root=non_utf8_root))

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda self: Path('/resolved/root'))
    resolved_store = store.ProjectStore.from_root('rel-root')
    assert resolved_store == store.ProjectStore(
      store.HostStoreBackend(Path('/resolved/root'))
    )

    mp.setattr(Path, 'resolve', lambda self: non_utf8_root)
    with pytest.raises(core.ProjectError) as from_root_utf8_err:
      store.ProjectStore.from_root(non_utf8_root)

    def broken_resolve(self: Path) -> Path:
      raise OSError('permission denied')

    mp.setattr(Path, 'resolve', broken_resolve)
    with pytest.raises(core.ProjectError) as resolve_err:
      store.ProjectStore.from_root('/unresolvable-root')
  assert (
    str(direct_root_err.value),
    str(from_root_utf8_err.value),
    str(resolve_err.value),
  ) == (
    'Project root path is not valid UTF-8: /root-\\xff',
    'Project root path is not valid UTF-8: /root-\\xff',
    'Could not resolve project root /unresolvable-root: permission denied',
  )


def _seed_raw_non_project(
  backend: MemdbBackend, rel_path: PurePosixPath, script: str
) -> None:
  conn = backend.open_raw(rel_path, mode='rwc')
  try:
    conn.executescript(script)
    conn.commit()
  finally:
    conn.close()


def _read_user_version(
  backend: MemdbBackend, rel_path: PurePosixPath
) -> int:
  conn = backend.open_raw(rel_path, mode='ro')
  try:
    return int(conn.execute('PRAGMA user_version').fetchone()[0])
  finally:
    conn.close()


def test_list_projects_skips_non_project_databases_without_mutation(
  monkeypatch: MonkeyPatch,
) -> None:
  with _memdb_store() as (backend, project_store):
    no_dir_listing = project_store.list_projects()
    backend.mkdir(PurePosixPath('.tmp'))
    empty_dir_listing = project_store.list_projects()
    assert (no_dir_listing, empty_dir_listing) == ((), ())

    project_store.create_project(core.ProjectName.parse('alpha'), _CHARTER)
    project_store.create_project(core.ProjectName.parse('beta'), _CHARTER)
    beta_rel = PurePosixPath('.tmp/beta.sqlite3')
    beta_raw = backend.open_raw(beta_rel, mode='rw')
    try:
      _downgrade_v7_to_v6(beta_raw)
      beta_raw.commit()
    finally:
      beta_raw.close()

    telemetry_rel = PurePosixPath('.tmp/task99-telemetry.sqlite3')
    _seed_raw_non_project(
      backend,
      telemetry_rel,
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
      """,
    )
    scratch_rel = PurePosixPath('.tmp/scratch.sqlite3')
    _seed_raw_non_project(
      backend,
      scratch_rel,
      'CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT);',
    )
    zero_byte_rel = PurePosixPath('.tmp/zero-byte.sqlite3')
    backend.seed(zero_byte_rel, b'')
    dot_only_rel = PurePosixPath('.tmp/.sqlite3')
    _seed_raw_non_project(
      backend, dot_only_rel, 'CREATE TABLE x (id INT);'
    )
    double_suffix_rel = PurePosixPath('.tmp/notes.sqlite3.sqlite3')
    _seed_raw_non_project(
      backend, double_suffix_rel, 'CREATE TABLE y (id INT);'
    )
    long_stem_rel = PurePosixPath(f'.tmp/{"x" * 205}.sqlite3')
    _seed_raw_non_project(
      backend, long_stem_rel, 'CREATE TABLE z (id INT);'
    )

    real_stems = backend.list_sqlite_stems()
    with monkeypatch.context() as mp:
      mp.setattr(
        MemdbBackend,
        'list_sqlite_stems',
        lambda _self: (*real_stems, 'vanished-transient'),
      )
      listed = project_store.list_projects()

    telemetry_version_after = _read_user_version(backend, telemetry_rel)
    scratch_version_after = _read_user_version(backend, scratch_rel)
    zero_byte_version_after = _read_user_version(backend, zero_byte_rel)
    beta_version_after = _read_user_version(backend, beta_rel)

    assert (
      listed,
      telemetry_version_after,
      scratch_version_after,
      zero_byte_version_after,
      beta_version_after,
    ) == (
      (
        service.ProjectSummary(
          name='alpha',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path='/memdb-root/.tmp/alpha.sqlite3',
        ),
        service.ProjectSummary(
          name='beta',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path='/memdb-root/.tmp/beta.sqlite3',
        ),
      ),
      1,
      0,
      0,
      schema.SCHEMA_VERSION,
    )

    with pytest.raises(core.ProjectError) as direct_err:
      with project_store.open_project(
        core.ProjectName.parse('task99-telemetry')
      ):
        pass
    assert str(direct_err.value) == (
      'Unsupported project schema version 1; expected 7: '
      '/memdb-root/.tmp/task99-telemetry.sqlite3'
    )

    with pytest.raises(core.ProjectError) as overwrite_non_project_err:
      project_store.create_project(
        core.ProjectName.parse('scratch'), _CHARTER
      )
    with pytest.raises(core.ProjectError) as archive_non_project_err:
      project_store.archive_project(core.ProjectName.parse('scratch'))

    backend.mkdir(PurePosixPath('.tmp/not-a-file.sqlite3'))
    with pytest.raises(core.ProjectError) as overwrite_dir_err:
      project_store.create_project(
        core.ProjectName.parse('not-a-file'), _CHARTER
      )

    assert (
      str(overwrite_non_project_err.value),
      str(archive_non_project_err.value),
      str(overwrite_dir_err.value),
      backend.exists(scratch_rel),
      backend.exists(PurePosixPath('.tmp/archive')),
    ) == (
      'Cannot overwrite non-project SQLite database: '
      '/memdb-root/.tmp/scratch.sqlite3',
      'Cannot archive non-project SQLite database: '
      '/memdb-root/.tmp/scratch.sqlite3',
      'Cannot overwrite non-file path at '
      '/memdb-root/.tmp/not-a-file.sqlite3',
      True,
      False,
    )


def test_create_and_archive_recover_corrupt_targets_single_probe_and_races(
  monkeypatch: MonkeyPatch, v7_snapshot: bytes
) -> None:
  corrupt_bytes = bytearray(v7_snapshot)
  corrupt_bytes[100:200] = b'\xff' * 100

  with _memdb_store(default_ctime_ns=55_000) as (backend, project_store):
    corrupt_name = core.ProjectName.parse('corrupt-create')
    corrupt_rel = PurePosixPath('.tmp/corrupt-create.sqlite3')
    backend.seed(corrupt_rel, bytes(corrupt_bytes))
    project_store.create_project(corrupt_name, _CHARTER)

    non_sqlite_name = core.ProjectName.parse('raw-archive')
    non_sqlite_rel = PurePosixPath('.tmp/raw-archive.sqlite3')
    backend.seed(non_sqlite_rel, b'not a sqlite database')
    archived_raw_path = project_store.archive_project(non_sqlite_name)

    ro_probes: list[PurePosixPath] = []
    real_open_raw = MemdbBackend.open_raw

    def counting_open_raw(
      self: MemdbBackend,
      rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      if mode == 'ro':
        ro_probes.append(rel_path)
      return real_open_raw(self, rel_path, mode=mode)

    with monkeypatch.context() as mp:
      mp.setattr(MemdbBackend, 'open_raw', counting_open_raw)
      project_store.create_project(corrupt_name, _CHARTER)

    def vanish_after_is_file(
      self: MemdbBackend,
      rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      if rel_path == non_sqlite_rel and mode == 'ro':
        raise FileNotFoundError(
          errno.ENOENT,
          os.strerror(errno.ENOENT),
          os.fspath(self.root / rel_path),
        )
      return real_open_raw(self, rel_path, mode=mode)

    project_store.create_project(non_sqlite_name, _CHARTER)
    with monkeypatch.context() as mp:
      mp.setattr(MemdbBackend, 'open_raw', vanish_after_is_file)
      with pytest.raises(core.ProjectError) as archive_vanished:
        project_store.archive_project(non_sqlite_name)

    def vanish_target_during_create(
      self: MemdbBackend,
      rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      if rel_path == non_sqlite_rel and mode == 'ro':
        self.unlink(rel_path)
        raise FileNotFoundError(
          errno.ENOENT,
          os.strerror(errno.ENOENT),
          os.fspath(self.root / rel_path),
        )
      return real_open_raw(self, rel_path, mode=mode)

    with monkeypatch.context() as mp:
      mp.setattr(MemdbBackend, 'open_raw', vanish_target_during_create)
      project_store.create_project(non_sqlite_name, _CHARTER)

    race_dir_name = core.ProjectName.parse('race-dir')
    race_dir_rel = PurePosixPath('.tmp/race-dir.sqlite3')

    def mkdir_during_temp_open(
      self: MemdbBackend,
      rel_path: PurePosixPath,
      *,
      mode: store.StoreOpenMode,
    ) -> sqlite3.Connection:
      if rel_path.name.startswith('.race-dir-'):
        self.mkdir(race_dir_rel)
      return real_open_raw(self, rel_path, mode=mode)

    with monkeypatch.context() as mp:
      mp.setattr(MemdbBackend, 'open_raw', mkdir_during_temp_open)
      with pytest.raises(core.ProjectError) as race_dir_err:
        project_store.create_project(race_dir_name, _CHARTER)

    assert (
      backend.exists(
        PurePosixPath('.tmp/archive/corrupt-create-55000.sqlite3')
      ),
      archived_raw_path,
      ro_probes,
      str(archive_vanished.value),
      str(race_dir_err.value),
      backend.exists(PurePosixPath('.tmp/.race-dir-temp-6.tmp')),
      project_store.list_projects(),
    ) == (
      True,
      Path('/memdb-root/.tmp/archive/raw-archive-55000.sqlite3'),
      [corrupt_rel],
      'Project does not exist: raw-archive',
      'Could not install project database at '
      '/memdb-root/.tmp/race-dir.sqlite3: '
      'Existing target is not a file: /memdb-root/.tmp/race-dir.sqlite3',
      False,
      (
        service.ProjectSummary(
          name='corrupt-create',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path='/memdb-root/.tmp/corrupt-create.sqlite3',
        ),
        service.ProjectSummary(
          name='raw-archive',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path='/memdb-root/.tmp/raw-archive.sqlite3',
        ),
      ),
    )


def test_error_path_injectivity_and_raw_summary_paths() -> None:
  assert (
    store._format_error_path('a\\tb'),
    store._format_error_path('a\tb'),
    store._format_error_path('a\n\r\t\x1bb'),
    store._format_error_path(os.fsdecode(b'/root/\xff/demo.sqlite3')),
    store._format_error_path('/root/\\xff/demo.sqlite3'),
  ) == (
    'a\\\\tb',
    'a\\tb',
    'a\\n\\r\\t\\u001bb',
    '/root/\\xff/demo.sqlite3',
    '/root/\\\\xff/demo.sqlite3',
  )

  tab_backend = MemdbBackend(
    root=Path('/memdb\troot'), uri_prefix='tabmemdb'
  )
  tab_store = store.ProjectStore(tab_backend)
  try:
    tab_store.create_project(_NAME, _CHARTER)
    listed = tab_store.list_projects()
    tab_backend.seed(PurePosixPath('.tmp/broken.sqlite3'), b'not sqlite')
    with pytest.raises(core.ProjectError) as err:
      tab_store.list_projects()
    assert (listed, str(err.value)) == (
      (
        service.ProjectSummary(
          name='demo',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path='/memdb\troot/.tmp/demo.sqlite3',
        ),
      ),
      'Project database could not be validated: '
      '/memdb\\troot/.tmp/broken.sqlite3: file is not a database',
    )
  finally:
    tab_backend.close()


def test_host_store_backend_posix_scandir_and_wal_immutability(
  tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
  with monkeypatch.context() as mp:
    mp.setattr(schema, 'connection_time', lambda _conn: _NOW)
    mp.setattr(
      store.HostStoreBackend, 'ctime_ns', lambda _self, _rel: 77_000
    )
    mp.setattr(
      store.HostStoreBackend,
      'next_temp_suffix',
      lambda _self: 'temp-host',
    )

    root_path = tmp_path
    double_slash_root = Path(f'//{str(root_path).lstrip("/")}')
    project_store = store.ProjectStore.from_root(root_path)
    double_slash_store = store.ProjectStore.from_root(double_slash_root)

    special = core.ProjectName.parse('a?b#c % " ✓')
    project_store.create_project(special, _CHARTER)
    created_list = double_slash_store.list_projects()
    archived = project_store.archive_project(special)
    assert (created_list, archived) == (
      (
        service.ProjectSummary(
          name='a?b#c % " ✓',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path=f'{root_path}/.tmp/a?b#c % " ✓.sqlite3',
        ),
      ),
      root_path / '.tmp' / 'archive' / 'a?b#c % " ✓-77000.sqlite3',
    )

    tmp_dir = root_path / '.tmp'
    wal_active = tmp_dir / 'wal-active.sqlite3'
    wal_ro = tmp_dir / 'ro-wal.sqlite3'
    wal_writer: sqlite3.Connection | None = None
    ro_writer: sqlite3.Connection | None = None
    try:
      wal_writer = sqlite3.connect(wal_active)
      wal_writer.execute('PRAGMA journal_mode = WAL')
      wal_writer.execute('CREATE TABLE metrics (k TEXT, v INT)')
      wal_writer.commit()
      wal_writer.execute("INSERT INTO metrics VALUES ('open', 1)")
      wal_writer.commit()
      wal_wal = tmp_dir / 'wal-active.sqlite3-wal'
      wal_db_digest = hashlib.sha256(wal_active.read_bytes()).hexdigest()
      wal_sidecar_digest = hashlib.sha256(wal_wal.read_bytes()).hexdigest()

      ro_writer = sqlite3.connect(wal_ro)
      ro_writer.execute('PRAGMA journal_mode = WAL')
      ro_writer.execute('CREATE TABLE notes (body TEXT)')
      ro_writer.execute("INSERT INTO notes VALUES ('locked')")
      ro_writer.commit()
      ro_writer.close()
      ro_writer = None
      ro_digest = hashlib.sha256(wal_ro.read_bytes()).hexdigest()
      os.chmod(wal_ro, 0o444)

      listed_none = project_store.list_projects()
      with pytest.raises(core.ProjectError) as overwrite_wal:
        project_store.create_project(
          core.ProjectName.parse('ro-wal'), _CHARTER
        )
      with pytest.raises(core.ProjectError) as archive_wal:
        project_store.archive_project(core.ProjectName.parse('wal-active'))

      assert (
        listed_none,
        hashlib.sha256(wal_active.read_bytes()).hexdigest(),
        hashlib.sha256(wal_wal.read_bytes()).hexdigest(),
        hashlib.sha256(wal_ro.read_bytes()).hexdigest(),
        (tmp_dir / 'ro-wal.sqlite3-shm').exists(),
        (tmp_dir / 'ro-wal.sqlite3-wal').exists(),
        str(overwrite_wal.value),
        str(archive_wal.value),
      ) == (
        (),
        wal_db_digest,
        wal_sidecar_digest,
        ro_digest,
        False,
        False,
        f'Cannot overwrite non-project SQLite database: {wal_ro}',
        f'Cannot archive non-project SQLite database: {wal_active}',
      )
    finally:
      if wal_ro.exists():
        os.chmod(wal_ro, 0o644)
      if ro_writer is not None:
        ro_writer.close()
      if wal_writer is not None:
        wal_writer.rollback()
        wal_writer.close()

    wal_active.unlink()
    wal_wal.unlink(missing_ok=True)
    wal_ro.unlink()

    onebyte_path = tmp_dir / 'onebyte.sqlite3'
    onebyte_path.write_bytes(b'x')
    with pytest.raises(core.ProjectError) as onebyte_list_err:
      project_store.list_projects()
    with pytest.raises(core.ProjectError) as onebyte_open_err:
      with project_store.open_project(core.ProjectName.parse('onebyte')):
        pass
    archived_onebyte = project_store.archive_project(
      core.ProjectName.parse('onebyte')
    )
    onebyte_path.write_bytes(b'y')
    project_store.create_project(
      core.ProjectName.parse('onebyte'), _CHARTER
    )
    recovered_onebyte_archive = (
      tmp_dir / 'archive' / 'onebyte-77000-1.sqlite3'
    )
    project_store.archive_project(core.ProjectName.parse('onebyte'))

    project_store.create_project(special, _CHARTER)
    live_symlink = tmp_dir / 'live-link.sqlite3'
    live_symlink.symlink_to(tmp_dir / f'{special.value}.sqlite3')
    broken_symlink = tmp_dir / 'broken-link.sqlite3'
    broken_symlink.symlink_to(tmp_dir / 'does-not-exist.sqlite3')

    listed_with_links = project_store.list_projects()
    with pytest.raises(core.ProjectError) as create_broken_link_err:
      project_store.create_project(
        core.ProjectName.parse('broken-link'), _CHARTER
      )
    with pytest.raises(core.ProjectError) as open_broken_link_err:
      with project_store.open_project(
        core.ProjectName.parse('broken-link')
      ):
        pass
    with pytest.raises(core.ProjectError) as archive_broken_link_err:
      project_store.archive_project(core.ProjectName.parse('broken-link'))

    file_root = tmp_path / 'file-tmp-root'
    file_root.mkdir()
    file_tmp = file_root / '.tmp'
    file_tmp.write_bytes(b'not a dir')
    with pytest.raises(core.ProjectError) as file_tmp_err:
      store.ProjectStore.from_root(file_root).list_projects()

    link_root = tmp_path / 'broken-link-tmp-root'
    link_root.mkdir()
    link_tmp = link_root / '.tmp'
    link_tmp.symlink_to(link_root / 'missing-target')
    with pytest.raises(core.ProjectError) as link_tmp_err:
      store.ProjectStore.from_root(link_root).list_projects()

    enotdir_error = (
      f'[Errno {errno.ENOTDIR}] '
      f'{os.strerror(errno.ENOTDIR)}: {str(file_tmp)!r}'
    )
    enoent_error = (
      f'[Errno {errno.ENOENT}] '
      f'{os.strerror(errno.ENOENT)}: {str(link_tmp)!r}'
    )
    assert (
      str(onebyte_list_err.value),
      str(onebyte_open_err.value),
      archived_onebyte,
      recovered_onebyte_archive.read_bytes(),
      listed_with_links,
      str(create_broken_link_err.value),
      str(open_broken_link_err.value),
      str(archive_broken_link_err.value),
      str(file_tmp_err.value),
      str(link_tmp_err.value),
    ) == (
      f'Project database could not be validated: {onebyte_path}: '
      'file is not a database',
      f'Project database could not be validated: {onebyte_path}: '
      'file is not a database',
      tmp_dir / 'archive' / 'onebyte-77000.sqlite3',
      b'y',
      (
        service.ProjectSummary(
          name='a?b#c % " ✓',
          status='active',
          objective='Store module delivery',
          updated_at=_NOW,
          path=f'{tmp_dir}/a?b#c % " ✓.sqlite3',
        ),
      ),
      f'Cannot overwrite non-file path at {broken_symlink}',
      'Project does not exist: broken-link',
      'Project does not exist: broken-link',
      f'Could not list projects under {file_tmp}: {enotdir_error}',
      f'Could not list projects under {link_tmp}: {enoent_error}',
    )


class _CapHeader(ctypes.Structure):
  _fields_: ClassVar[tuple[tuple[str, type[ctypes._SimpleCData]], ...]] = (
    ('version', ctypes.c_uint32),
    ('pid', ctypes.c_int),
  )


class _CapData(ctypes.Structure):
  _fields_: ClassVar[tuple[tuple[str, type[ctypes._SimpleCData]], ...]] = (
    ('effective', ctypes.c_uint32),
    ('permitted', ctypes.c_uint32),
    ('inheritable', ctypes.c_uint32),
  )


@contextmanager
def _without_dac_override() -> Iterator[None]:
  if sys.platform != 'linux':
    yield
    return
  libc = ctypes.CDLL(None, use_errno=True)
  header = _CapHeader(0x20080522, 0)
  saved = (_CapData * 2)()
  if libc.capget(ctypes.byref(header), saved) != 0:
    err = ctypes.get_errno()
    raise OSError(err, os.strerror(err))
  dac_mask = (1 << 1) | (1 << 2)
  if (saved[0].effective & dac_mask) == 0:
    yield
    return
  dropped = (_CapData * 2)()
  for index in (0, 1):
    dropped[index].effective = saved[index].effective
    dropped[index].permitted = saved[index].permitted
    dropped[index].inheritable = saved[index].inheritable
  dropped[0].effective &= ~dac_mask
  if libc.capset(ctypes.byref(header), dropped) != 0:
    err = ctypes.get_errno()
    raise OSError(err, os.strerror(err))
  try:
    yield
  finally:
    if libc.capset(ctypes.byref(header), saved) != 0:
      err = ctypes.get_errno()
      raise OSError(err, os.strerror(err))


def test_host_store_backend_posix_permission_errors(
  tmp_path: Path, v7_snapshot: bytes
) -> None:
  project_store = store.ProjectStore.from_root(tmp_path)
  tmp_dir = tmp_path / '.tmp'
  tmp_dir.mkdir(parents=True)
  locked = tmp_dir / 'locked.sqlite3'
  locked.write_bytes(v7_snapshot)
  locked_onebyte = tmp_dir / 'locked-onebyte.sqlite3'

  with _without_dac_override():
    os.chmod(locked, 0o000)
    try:
      with pytest.raises(core.ProjectError) as list_locked_err:
        project_store.list_projects()
      with pytest.raises(core.ProjectError) as open_locked_err:
        with project_store.open_project(core.ProjectName.parse('locked')):
          pass
      with pytest.raises(core.ProjectError) as create_locked_err:
        project_store.create_project(
          core.ProjectName.parse('locked'), _CHARTER
        )
      with pytest.raises(core.ProjectError) as archive_locked_err:
        project_store.archive_project(core.ProjectName.parse('locked'))
      locked_exists = locked.exists()
      archive_missing_after_locked = not (tmp_dir / 'archive').exists()
    finally:
      os.chmod(locked, 0o644)
      locked.unlink()

    locked_onebyte.write_bytes(b'x')
    os.chmod(locked_onebyte, 0o000)
    try:
      with pytest.raises(core.ProjectError) as list_onebyte_err:
        project_store.list_projects()
      with pytest.raises(core.ProjectError) as open_onebyte_err:
        with project_store.open_project(
          core.ProjectName.parse('locked-onebyte')
        ):
          pass
      with pytest.raises(core.ProjectError) as create_onebyte_err:
        project_store.create_project(
          core.ProjectName.parse('locked-onebyte'), _CHARTER
        )
      with pytest.raises(core.ProjectError) as archive_onebyte_err:
        project_store.archive_project(
          core.ProjectName.parse('locked-onebyte')
        )
      locked_onebyte_exists = locked_onebyte.exists()
      archive_missing_after_onebyte = not (tmp_dir / 'archive').exists()
    finally:
      os.chmod(locked_onebyte, 0o644)
      locked_onebyte.unlink()

    os.chmod(tmp_dir, 0o000)
    eacces_error = (
      f'[Errno {errno.EACCES}] '
      f'{os.strerror(errno.EACCES)}: {str(tmp_dir)!r}'
    )
    try:
      with pytest.raises(core.ProjectError) as scandir_err:
        project_store.list_projects()
    finally:
      os.chmod(tmp_dir, 0o755)

  assert (
    locked_exists,
    archive_missing_after_locked,
    str(list_locked_err.value),
    str(open_locked_err.value),
    str(create_locked_err.value),
    str(archive_locked_err.value),
    locked_onebyte_exists,
    archive_missing_after_onebyte,
    str(list_onebyte_err.value),
    str(open_onebyte_err.value),
    str(create_onebyte_err.value),
    str(archive_onebyte_err.value),
    str(scandir_err.value),
  ) == (
    True,
    True,
    f'Project database could not be validated: {locked}: '
    'unable to open database file',
    f'Project database could not be validated: {locked}: '
    'unable to open database file',
    f'Could not create project database at {locked}: '
    'unable to open database file',
    f'Could not archive project database at {locked}: '
    'unable to open database file',
    True,
    True,
    f'Project database could not be validated: {locked_onebyte}: '
    'unable to open database file',
    f'Project database could not be validated: {locked_onebyte}: '
    'unable to open database file',
    f'Could not create project database at {locked_onebyte}: '
    'unable to open database file',
    f'Could not archive project database at {locked_onebyte}: '
    'unable to open database file',
    f'Could not list projects under {tmp_dir}: {eacces_error}',
  )


def _capture_broken_project_list_error(
  stem: str,
  mutate: Callable[[sqlite3.Connection], None],
) -> str:
  with _memdb_store() as (backend, project_store):
    project_store.create_project(core.ProjectName.parse(stem), _CHARTER)
    raw = backend.open_raw(
      PurePosixPath(f'.tmp/{stem}.sqlite3'), mode='rw'
    )
    try:
      schema.configure_connection(raw)
      mutate(raw)
      raw.commit()
    finally:
      raw.close()
    with pytest.raises(core.ProjectError) as err:
      project_store.list_projects()
    return str(err.value)


def _forge_active_task(conn: sqlite3.Connection) -> None:
  trigger_sql = conn.execute(
    'SELECT sql FROM sqlite_master '
    "WHERE type = 'trigger' AND name = 'task_start_time_valid'"
  ).fetchone()[0]
  conn.executescript(
    f'DROP TRIGGER task_start_time_valid; '
    f'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
    f"VALUES (1, 's1', 'o1', {_NOW}, {_NOW}); "
    'INSERT INTO task '
    '(id, stage_id, title, purpose, scope, exclusions, '
    'result, completion_evidence, created_at, updated_at) '
    f"VALUES (1, 1, 't', 'p', 's', 'e', 'r', 'c', {_NOW}, {_NOW}); "
    "UPDATE task SET status = 'active', started_at = 9999999999 "
    'WHERE id = 1; '
    f'{trigger_sql};'
  )


def test_list_projects_rejects_broken_project_and_corrupt_databases(
  v7_snapshot: bytes,
) -> None:
  bad_version_err = _capture_broken_project_list_error(
    'bad-version',
    lambda conn: conn.execute('PRAGMA user_version = 99'),
  )
  with _memdb_store() as (backend, project_store):
    backend.seed(PurePosixPath('.tmp/mismatch.sqlite3'), v7_snapshot)
    with pytest.raises(core.ProjectError) as mismatch_exc:
      project_store.list_projects()
    mismatch_err = str(mismatch_exc.value)
  missing_table_err = _capture_broken_project_list_error(
    'missing-table',
    lambda conn: conn.execute('DROP TABLE project'),
  )
  missing_trigger_err = _capture_broken_project_list_error(
    'missing-trigger',
    lambda conn: conn.execute('DROP TRIGGER project_charter_update'),
  )
  forged_lifecycle_err = _capture_broken_project_list_error(
    'forged-lifecycle', _forge_active_task
  )

  corrupt_bytes = bytearray(v7_snapshot)
  corrupt_bytes[100:200] = b'\xff' * 100
  with _memdb_store() as (backend, project_store):
    backend.seed(
      PurePosixPath('.tmp/corrupt.sqlite3'), bytes(corrupt_bytes)
    )
    with pytest.raises(core.ProjectError) as corrupt_exc:
      project_store.list_projects()
    corrupt_err = str(corrupt_exc.value)

  with _memdb_store() as (backend, project_store):
    backend.seed(
      PurePosixPath('.tmp/not-sqlite.sqlite3'), b'not a sqlite database'
    )
    with pytest.raises(core.ProjectError) as non_sqlite_exc:
      project_store.list_projects()
    non_sqlite_err = str(non_sqlite_exc.value)

  with _memdb_store() as (backend, project_store):
    bad_stem_rel = PurePosixPath('.tmp/bad\x07.sqlite3')
    backend.seed(bad_stem_rel, v7_snapshot)
    bad_stem_raw = backend.open_raw(bad_stem_rel, mode='rw')
    try:
      _downgrade_v7_to_v6(bad_stem_raw)
    finally:
      bad_stem_raw.close()
    with pytest.raises(core.ProjectError) as bad_stem_exc:
      project_store.list_projects()
    bad_stem_err = str(bad_stem_exc.value)
    bad_stem_version_after = _read_user_version(backend, bad_stem_rel)

  with _memdb_store() as (backend, project_store):
    control_rel = PurePosixPath('.tmp/bad\nInjected\x1b]52;\x07.sqlite3')
    backend.seed(control_rel, v7_snapshot)
    with pytest.raises(core.ProjectError) as control_exc:
      project_store.list_projects()
    control_err = str(control_exc.value)

  assert (
    bad_version_err,
    mismatch_err,
    missing_table_err,
    missing_trigger_err,
    forged_lifecycle_err,
    corrupt_err,
    non_sqlite_err,
    bad_stem_err,
    bad_stem_version_after,
    control_err,
  ) == (
    'Unsupported project schema version 99; expected 7: '
    '/memdb-root/.tmp/bad-version.sqlite3',
    "Project name 'demo' does not match database address 'mismatch': "
    '/memdb-root/.tmp/mismatch.sqlite3',
    'Project schema is incomplete; missing tables: project: '
    '/memdb-root/.tmp/missing-table.sqlite3',
    'Project schema is incomplete; missing triggers: '
    'project_charter_update: /memdb-root/.tmp/missing-trigger.sqlite3',
    'Project has an invalid active task: 1: '
    '/memdb-root/.tmp/forged-lifecycle.sqlite3',
    'Project database could not be validated: '
    '/memdb-root/.tmp/corrupt.sqlite3: database disk image is malformed',
    'Project database could not be validated: '
    '/memdb-root/.tmp/not-sqlite.sqlite3: file is not a database',
    'Project names must be printable, non-empty single path components '
    'of at most 200 characters without the .sqlite3 suffix: '
    '/memdb-root/.tmp/bad\\u0007.sqlite3',
    6,
    'Project names must be printable, non-empty single path components '
    'of at most 200 characters without the .sqlite3 suffix: '
    '/memdb-root/.tmp/bad\\nInjected\\u001b]52;\\u0007.sqlite3',
  )
