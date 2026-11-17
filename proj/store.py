import contextlib
import errno
import os
import secrets
import sqlite3
import stat
import time
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, Protocol

from .core import PROJECT_SUFFIX, CharterInput, ProjectError, ProjectName
from .schema import (
  CorruptDatabase,
  DatabaseClassification,
  classify_database,
  configure_connection,
  initialize_project,
  is_corrupt_sqlite_error,
  validate_project,
)
from .service import ProjectSummary, read_project_summary

type StoreOpenMode = Literal['ro', 'rw', 'rwc']

__all__ = [
  'HostStoreBackend',
  'ProjectStore',
  'StoreBackend',
  'StoreOpenMode',
]

_TMP_DIR: Final[PurePosixPath] = PurePosixPath('.tmp')
_ARCHIVE_DIR: Final[PurePosixPath] = PurePosixPath('.tmp/archive')


class StoreBackend(Protocol):
  @property
  def root(self) -> Path: ...

  def is_file(self, rel_path: PurePosixPath) -> bool: ...

  def exists(self, rel_path: PurePosixPath) -> bool: ...

  def ctime_ns(self, rel_path: PurePosixPath) -> int: ...

  def list_sqlite_stems(self) -> tuple[str, ...]: ...

  def next_temp_suffix(self) -> str: ...

  def mkdir(self, rel_path: PurePosixPath) -> None: ...

  def rename(self, src: PurePosixPath, dst: PurePosixPath) -> None: ...

  def unlink(self, rel_path: PurePosixPath) -> None: ...

  def open_raw(
    self, rel_path: PurePosixPath, *, mode: StoreOpenMode
  ) -> sqlite3.Connection: ...


_CONTROL_ESCAPES: Final[dict[str, str]] = {
  '\n': '\\n',
  '\r': '\\r',
  '\t': '\\t',
}


def _sqlite_file_uri(path: Path, mode: StoreOpenMode) -> str:
  encoded = urllib.parse.quote(os.fsencode(path), safe=b'/')
  prefix = 'file://localhost' if encoded.startswith('//') else 'file:'
  if mode == 'ro':
    return f'{prefix}{encoded}?mode=ro&immutable=1'
  return f'{prefix}{encoded}?mode={mode}'


def _format_error_path(path: Path | str) -> str:
  text = os.fsdecode(path)
  parts: list[str] = []
  for ch in text:
    code = ord(ch)
    if ch == '\\':
      parts.append('\\\\')
    elif 0xDC80 <= code <= 0xDCFF:
      parts.append(f'\\x{code & 0xFF:02x}')
    elif ch.isprintable():
      parts.append(ch)
    else:
      parts.append(_CONTROL_ESCAPES.get(ch) or f'\\u{code:04x}')
  return ''.join(parts)


@dataclass(frozen=True, slots=True)
class HostStoreBackend:
  root: Path

  def _host_path(self, rel_path: PurePosixPath) -> Path:
    return self.root / rel_path

  def is_file(self, rel_path: PurePosixPath) -> bool:
    return self._host_path(rel_path).is_file(follow_symlinks=False)

  def exists(self, rel_path: PurePosixPath) -> bool:
    return self._host_path(rel_path).exists(follow_symlinks=False)

  def ctime_ns(self, rel_path: PurePosixPath) -> int:
    return (
      self._host_path(rel_path).stat(follow_symlinks=False).st_ctime_ns
    )

  def list_sqlite_stems(self) -> tuple[str, ...]:
    directory = self._host_path(_TMP_DIR)
    try:
      with os.scandir(os.fspath(directory)) as entries:
        return tuple(
          sorted(
            entry.name.removesuffix(PROJECT_SUFFIX)
            for entry in entries
            if entry.name.endswith(PROJECT_SUFFIX)
            and entry.is_file(follow_symlinks=False)
          )
        )
    except FileNotFoundError:
      if not directory.exists(follow_symlinks=False):
        return ()
      raise

  def next_temp_suffix(self) -> str:
    return f'{time.time_ns()}-{os.getpid()}-{secrets.token_hex(4)}'

  def mkdir(self, rel_path: PurePosixPath) -> None:
    self._host_path(rel_path).mkdir(parents=True, exist_ok=True)

  def rename(self, src: PurePosixPath, dst: PurePosixPath) -> None:
    self._host_path(src).rename(self._host_path(dst))

  def unlink(self, rel_path: PurePosixPath) -> None:
    self._host_path(rel_path).unlink(missing_ok=True)

  def open_raw(
    self, rel_path: PurePosixPath, *, mode: StoreOpenMode
  ) -> sqlite3.Connection:
    path = self._host_path(rel_path)
    st: os.stat_result | None = None
    if mode != 'rwc':
      st = path.stat(follow_symlinks=False)
      if not stat.S_ISREG(st.st_mode):
        raise FileNotFoundError(
          errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(path)
        )
    try:
      connection = sqlite3.connect(
        _sqlite_file_uri(path, mode), timeout=5, uri=True
      )
    except sqlite3.OperationalError as error:
      code = getattr(error, 'sqlite_errorcode', None)
      if (
        mode != 'rwc'
        and isinstance(code, int)
        and (code & 0xFF) == sqlite3.SQLITE_CANTOPEN
        and not path.is_file(follow_symlinks=False)
      ):
        raise FileNotFoundError(
          errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(path)
        ) from error
      raise
    if st is not None and st.st_size == 1:
      with contextlib.suppress(OSError):
        st = path.stat(follow_symlinks=False)
      if stat.S_ISREG(st.st_mode) and st.st_size == 1:
        _close_quietly(connection)
        err = sqlite3.DatabaseError('file is not a database')
        err.sqlite_errorcode = sqlite3.SQLITE_NOTADB
        raise err
    return connection


def _db_rel_path(name: ProjectName) -> PurePosixPath:
  return _TMP_DIR / f'{name.value}{PROJECT_SUFFIX}'


def _close_quietly(connection: sqlite3.Connection) -> None:
  with contextlib.suppress(sqlite3.Error):
    connection.close()


@dataclass(frozen=True, slots=True)
class ProjectStore:
  backend: StoreBackend

  def __post_init__(self) -> None:
    try:
      os.fsdecode(self.backend.root).encode('utf-8')
    except UnicodeEncodeError as error:
      raise ProjectError(
        'Project root path is not valid UTF-8: '
        f'{_format_error_path(self.backend.root)}'
      ) from error

  @classmethod
  def from_root(cls, root: str | Path) -> 'ProjectStore':
    try:
      resolved = Path(root).resolve()
    except OSError as error:
      raise ProjectError(
        'Could not resolve project root '
        f'{_format_error_path(root)}: {error}'
      ) from error
    return cls(HostStoreBackend(resolved))

  def database_path(self, name: ProjectName) -> str:
    return str(
      self.backend.root / '.tmp' / f'{name.value}{PROJECT_SUFFIX}'
    )

  @staticmethod
  def handoff_database_path(name: ProjectName) -> str:
    return str(Path('.tmp') / f'{name.value}{PROJECT_SUFFIX}')

  def _unlink_ignoring_os_error(self, rel_path: PurePosixPath) -> None:
    with contextlib.suppress(OSError):
      self.backend.unlink(rel_path)

  def _archive_existing(
    self, name: ProjectName, rel_path: PurePosixPath
  ) -> tuple[PurePosixPath, Path]:
    self.backend.mkdir(_ARCHIVE_DIR)
    ctime = self.backend.ctime_ns(rel_path)
    archive_rel = _ARCHIVE_DIR / f'{name.value}-{ctime}{PROJECT_SUFFIX}'
    suffix = 1
    while self.backend.exists(archive_rel):
      archive_rel = (
        _ARCHIVE_DIR / f'{name.value}-{ctime}-{suffix}{PROJECT_SUFFIX}'
      )
      suffix += 1
    self.backend.rename(rel_path, archive_rel)
    return archive_rel, self.backend.root / archive_rel

  def _probe_database(
    self,
    rel_path: PurePosixPath,
    *,
    error_prefix: str,
  ) -> Literal['missing'] | DatabaseClassification:
    try:
      connection = self.backend.open_raw(rel_path, mode='ro')
    except FileNotFoundError:
      return 'missing'
    except sqlite3.Error as error:
      if is_corrupt_sqlite_error(error):
        return CorruptDatabase(str(error))
      raise ProjectError(f'{error_prefix}: {error}') from error
    except OSError as error:
      raise ProjectError(f'{error_prefix}: {error}') from error
    try:
      kind = classify_database(connection)
    except sqlite3.Error as error:
      _close_quietly(connection)
      raise ProjectError(f'{error_prefix}: {error}') from error
    except BaseException:
      _close_quietly(connection)
      raise
    try:
      connection.close()
    except sqlite3.Error as error:
      raise ProjectError(f'{error_prefix}: {error}') from error
    return kind

  def _ensure_overwritable_target(
    self, rel_path: PurePosixPath, err_path: str
  ) -> None:
    try:
      if not self.backend.exists(rel_path):
        return
      if not self.backend.is_file(rel_path):
        raise ProjectError(f'Cannot overwrite non-file path at {err_path}')
    except OSError as error:
      raise ProjectError(
        f'Could not create project database at {err_path}: {error}'
      ) from error
    kind = self._probe_database(
      rel_path,
      error_prefix=f'Could not create project database at {err_path}',
    )
    if kind == 'non-project':
      raise ProjectError(
        f'Cannot overwrite non-project SQLite database: {err_path}'
      )

  def _ensure_archivable_target(
    self, name: ProjectName, rel_path: PurePosixPath, err_path: str
  ) -> None:
    try:
      if not self.backend.is_file(rel_path):
        raise ProjectError(f'Project does not exist: {name.value}')
    except OSError as error:
      raise ProjectError(
        f'Could not archive project database at {err_path}: {error}'
      ) from error
    kind = self._probe_database(
      rel_path,
      error_prefix=f'Could not archive project database at {err_path}',
    )
    if kind == 'missing':
      raise ProjectError(f'Project does not exist: {name.value}')
    if kind == 'non-project':
      raise ProjectError(
        f'Cannot archive non-project SQLite database: {err_path}'
      )

  def create_project(
    self, name: ProjectName, charter: CharterInput
  ) -> Path:
    rel_path = _db_rel_path(name)
    path = Path(self.database_path(name))
    err_path = _format_error_path(path)
    err_dir = _format_error_path(self.backend.root / _TMP_DIR)
    self._ensure_overwritable_target(rel_path, err_path)
    temp_rel = (
      _TMP_DIR / f'.{name.value}-{self.backend.next_temp_suffix()}.tmp'
    )
    temp_path = self.backend.root / temp_rel
    err_temp = _format_error_path(temp_path)
    try:
      self.backend.mkdir(_TMP_DIR)
    except OSError as error:
      raise ProjectError(
        f'Could not create project directory at {err_dir}: {error}'
      ) from error
    try:
      connection = self.backend.open_raw(temp_rel, mode='rwc')
    except (OSError, sqlite3.Error) as error:
      self._unlink_ignoring_os_error(temp_rel)
      raise ProjectError(
        f'Could not open temporary project database at {err_temp}: {error}'
      ) from error
    try:
      configure_connection(connection)
      initialize_project(connection, name, charter)
    except ProjectError as error:
      _close_quietly(connection)
      self._unlink_ignoring_os_error(temp_rel)
      raise ProjectError(f'{error}: {err_temp}') from error
    except BaseException:
      _close_quietly(connection)
      self._unlink_ignoring_os_error(temp_rel)
      raise
    try:
      connection.close()
    except sqlite3.Error as error:
      _close_quietly(connection)
      self._unlink_ignoring_os_error(temp_rel)
      raise ProjectError(
        f'Could not finalize temporary project database at {err_temp}: '
        f'{error}'
      ) from error
    except BaseException:
      _close_quietly(connection)
      self._unlink_ignoring_os_error(temp_rel)
      raise
    archived: tuple[PurePosixPath, Path] | None = None
    try:
      if self.backend.exists(rel_path):
        if not self.backend.is_file(rel_path):
          raise IsADirectoryError(
            f'Existing target is not a file: {err_path}'
          )
        archived = self._archive_existing(name, rel_path)
      self.backend.rename(temp_rel, rel_path)
    except OSError as error:
      if archived is not None:
        archived_rel, archived_path = archived
        err_archived = _format_error_path(archived_path)
        try:
          self.backend.rename(archived_rel, rel_path)
        except OSError as restore_error:
          raise ProjectError(
            f'Could not install project database at {err_path}: {error}; '
            f'the previous database could not be restored from '
            f'{err_archived}: {restore_error}; the new database remains '
            f'at {err_temp}'
          ) from restore_error
      try:
        self.backend.unlink(temp_rel)
      except OSError as cleanup_error:
        raise ProjectError(
          f'Could not install project database at {err_path}: {error}; '
          f'the temporary database remains at {err_temp}: {cleanup_error}'
        ) from cleanup_error
      raise ProjectError(
        f'Could not install project database at {err_path}: {error}'
      ) from error
    return path

  def archive_project(self, name: ProjectName) -> Path:
    rel_path = _db_rel_path(name)
    err_path = _format_error_path(self.database_path(name))
    self._ensure_archivable_target(name, rel_path, err_path)
    try:
      _, archive_path = self._archive_existing(name, rel_path)
    except FileNotFoundError as error:
      raise ProjectError(
        f'Project does not exist: {name.value}'
      ) from error
    except OSError as error:
      raise ProjectError(
        f'Could not archive project database at {err_path}: {error}'
      ) from error
    return archive_path

  @staticmethod
  def _close_checked(
    connection: sqlite3.Connection, display_path: str
  ) -> None:
    try:
      connection.close()
    except sqlite3.Error as error:
      raise ProjectError(
        f'Project database could not be closed: {display_path}: {error}'
      ) from error

  def _connect_validated(
    self, rel_path: PurePosixPath, name: ProjectName, err_path: str
  ) -> sqlite3.Connection:
    try:
      connection = self.backend.open_raw(rel_path, mode='rw')
    except FileNotFoundError:
      raise
    except (OSError, sqlite3.Error) as error:
      raise ProjectError(
        f'Project database could not be validated: {err_path}: {error}'
      ) from error
    try:
      try:
        configure_connection(connection)
      except ProjectError as error:
        raise ProjectError(f'{error}: {err_path}') from error
      validate_project(
        connection,
        expected_name=name,
        display_path=err_path,
      )
    except BaseException:
      _close_quietly(connection)
      raise
    return connection

  @contextmanager
  def open_project(
    self, name: ProjectName
  ) -> Iterator[sqlite3.Connection]:
    rel_path = _db_rel_path(name)
    err_path = _format_error_path(self.database_path(name))
    try:
      connection = self._connect_validated(rel_path, name, err_path)
    except FileNotFoundError as error:
      raise ProjectError(
        f'Project does not exist: {name.value}'
      ) from error
    try:
      yield connection
    except BaseException:
      _close_quietly(connection)
      raise
    self._close_checked(connection, err_path)

  def list_projects(self) -> tuple[ProjectSummary, ...]:
    err_dir = _format_error_path(self.backend.root / _TMP_DIR)
    try:
      stems = self.backend.list_sqlite_stems()
    except OSError as error:
      raise ProjectError(
        f'Could not list projects under {err_dir}: {error}'
      ) from error
    summaries: list[ProjectSummary] = []
    for stem in stems:
      rel_path = _TMP_DIR / f'{stem}{PROJECT_SUFFIX}'
      raw_path = str(self.backend.root / rel_path)
      err_path = _format_error_path(raw_path)
      err_prefix = f'Project database could not be validated: {err_path}'
      kind = self._probe_database(rel_path, error_prefix=err_prefix)
      if kind in ('missing', 'non-project'):
        continue
      if isinstance(kind, CorruptDatabase):
        raise ProjectError(
          f'Project database could not be validated: {err_path}: '
          f'{kind.reason}'
        )
      try:
        project_name = ProjectName.parse(stem)
      except ProjectError as error:
        raise ProjectError(
          f'{str(error).rstrip(".")}: {err_path}'
        ) from error
      try:
        connection = self._connect_validated(
          rel_path, project_name, err_path
        )
      except FileNotFoundError:
        continue
      try:
        try:
          summaries.append(read_project_summary(connection, raw_path))
        except ProjectError as error:
          raise ProjectError(f'{error}: {err_path}') from error
      except BaseException:
        _close_quietly(connection)
        raise
      self._close_checked(connection, err_path)
    return tuple(summaries)
