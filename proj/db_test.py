from __future__ import annotations

import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from proj.db import (
  SCHEMA_VERSION,
  ProjectError,
  archive_project_db,
  connect_memory,
  create_project_db,
  init_project,
  is_substantive,
  iter_project_dbs,
  open_project,
  parse_project_name,
  require_substantive,
)


@pytest.fixture
def shm_root() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='proj-db-test-', dir='/dev/shm'))
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def test_text_and_name_validation() -> None:
  assert is_substantive('  x  ') is True
  assert is_substantive(' \t\n ') is False
  assert require_substantive(' ok ', 'f') == ' ok '
  with pytest.raises(ProjectError):
    require_substantive('   ', 'field')

  assert parse_project_name('alpha-1') == 'alpha-1'
  assert parse_project_name('my project') == 'my project'
  assert parse_project_name('x' * 200) == 'x' * 200

  bad = [
    '',
    'x' * 201,
    'bad\nname',
    'a/b',
    'a\\b',
    'a\x00b',
    '.',
    '..',
    'demo.sqlite3',
  ]
  for name in bad:
    with pytest.raises(ProjectError):
      parse_project_name(name)


def test_memory_db_schema_and_init() -> None:
  conn = connect_memory()
  try:
    assert (
      conn.execute('PRAGMA user_version').fetchone()[0] == SCHEMA_VERSION
    )
    assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    init_project(conn, name='demo', objective='Build core', now=100)
    row = conn.execute('SELECT * FROM project WHERE id = 1').fetchone()
    assert dict(row) == {
      'id': 1,
      'name': 'demo',
      'objective': 'Build core',
      'scope': '',
      'non_goals': '',
      'constraints_text': '',
      'acceptance': '',
      'summary': '',
      'next_action': '',
      'created_at': 100,
      'updated_at': 100,
    }
    with pytest.raises(ProjectError):
      init_project(conn, name='bad', objective='   ', now=100)
  finally:
    conn.close()


def test_filesystem_lifecycle_and_guards(shm_root: Path) -> None:
  db_path = create_project_db(
    shm_root, name='alpha', objective='Ship alpha', scope='Core', now=100
  )
  assert db_path == shm_root / '.tmp' / 'alpha.sqlite3'
  assert db_path.is_file()

  with open_project(shm_root, 'alpha', readonly=True) as conn:
    row = conn.execute('SELECT name, objective FROM project').fetchone()
    assert (row['name'], row['objective']) == ('alpha', 'Ship alpha')
    with pytest.raises(sqlite3.OperationalError):
      conn.execute("UPDATE project SET summary = 'x'")

  db_path2 = create_project_db(
    shm_root, name='alpha', objective='Ship alpha v2', now=200
  )
  assert db_path2 == db_path
  archived = shm_root / '.tmp' / 'archive' / 'alpha-200.sqlite3'
  assert archived.is_file()
  with open_project(shm_root, 'alpha') as conn:
    assert (
      conn.execute('SELECT objective FROM project').fetchone()[0]
      == 'Ship alpha v2'
    )

  dest1 = archive_project_db(shm_root, 'alpha', now=200)
  assert dest1 == shm_root / '.tmp' / 'archive' / 'alpha-200-1.sqlite3'
  assert not db_path.exists()
  with pytest.raises(ProjectError):
    open_project(shm_root, 'alpha').__enter__()
  with pytest.raises(ProjectError):
    archive_project_db(shm_root, 'alpha', now=200)


def test_non_project_and_corrupt_dbs(shm_root: Path) -> None:
  assert iter_project_dbs(shm_root) == []
  tmp = shm_root / '.tmp'
  tmp.mkdir(parents=True)

  scratch = tmp / 'scratch.sqlite3'
  sconn = sqlite3.connect(scratch)
  sconn.execute('CREATE TABLE kv (k TEXT, v TEXT)')
  sconn.commit()
  sconn.close()

  create_project_db(shm_root, name='beta', objective='Beta obj', now=10)
  assert iter_project_dbs(shm_root) == [
    ('beta', tmp / 'beta.sqlite3'),
  ]

  with pytest.raises(ProjectError):
    create_project_db(
      shm_root, name='scratch', objective='Overwrite', now=20
    )
  with pytest.raises(ProjectError):
    archive_project_db(shm_root, 'scratch', now=20)
  with pytest.raises(ProjectError):
    open_project(shm_root, 'scratch').__enter__()

  bad_ver = tmp / 'old.sqlite3'
  vconn = sqlite3.connect(bad_ver)
  vconn.execute('CREATE TABLE project (id INTEGER PRIMARY KEY, name TEXT)')
  vconn.execute("INSERT INTO project VALUES (1, 'old')")
  vconn.execute('PRAGMA user_version = 99')
  vconn.commit()
  vconn.close()
  with pytest.raises(ProjectError):
    open_project(shm_root, 'old').__enter__()

  bad_col = tmp / 'badcol.sqlite3'
  bconn = sqlite3.connect(bad_col)
  bconn.execute('CREATE TABLE project (id INTEGER PRIMARY KEY)')
  bconn.execute('PRAGMA user_version = 1')
  bconn.commit()
  bconn.close()
  with pytest.raises(ProjectError):
    open_project(shm_root, 'badcol').__enter__()

  corrupt = tmp / 'corrupt.sqlite3'
  corrupt.write_bytes(b'not sqlite')
  with pytest.raises(ProjectError, match=r'corrupt\.sqlite3'):
    iter_project_dbs(shm_root)
  with pytest.raises(ProjectError):
    create_project_db(shm_root, name='corrupt', objective='Fail', now=30)
