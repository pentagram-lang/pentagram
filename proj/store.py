import contextlib
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Protocol

from .core import PROJECT_SUFFIX, CharterInput, ProjectError, ProjectName
from .schema import (
  configure_connection,
  initialize_project,
  validate_project,
)
from .service import ProjectSummary, read_project_summary

__all__ = [
  'HostStoreBackend',
  'ProjectStore',
  'StoreBackend',
]

_TMP_DIR: Final[PurePosixPath] = PurePosixPath('.tmp')
_ARCHIVE_DIR: Final[PurePosixPath] = PurePosixPath('.tmp/archive')


class StoreBackend(Protocol):
  @property
  def root(self) -> Path: ...

  def is_dir(self, rel_path: PurePosixPath) -> bool: ...

  def is_file(self, rel_path: PurePosixPath) -> bool: ...

  def exists(self, rel_path: PurePosixPath) -> bool: ...

  def ctime_ns(self, rel_path: PurePosixPath) -> int: ...

  def list_sqlite_stems(self) -> tuple[str, ...]: ...

  def mkdir(self, rel_path: PurePosixPath) -> None: ...

  def rename(self, src: PurePosixPath, dst: PurePosixPath) -> None: ...

  def unlink(self, rel_path: PurePosixPath) -> None: ...

  def open_raw(
    self, rel_path: PurePosixPath, *, create: bool
  ) -> sqlite3.Connection: ...


@dataclass(frozen=True, slots=True)
class HostStoreBackend:
  root: Path

  def _host_path(self, rel_path: PurePosixPath) -> Path:
    return self.root / rel_path

  def is_dir(self, rel_path: PurePosixPath) -> bool:
    return self._host_path(rel_path).is_dir()

  def is_file(self, rel_path: PurePosixPath) -> bool:
    return self._host_path(rel_path).is_file()

  def exists(self, rel_path: PurePosixPath) -> bool:
    return self._host_path(rel_path).exists()

  def ctime_ns(self, rel_path: PurePosixPath) -> int:
    return self._host_path(rel_path).stat().st_ctime_ns

  def list_sqlite_stems(self) -> tuple[str, ...]:
    directory = self._host_path(_TMP_DIR)
    if not directory.is_dir():
      return ()
    return tuple(
      sorted(
        path.stem
        for path in directory.glob(f'*{PROJECT_SUFFIX}')
        if path.is_file()
      )
    )

  def mkdir(self, rel_path: PurePosixPath) -> None:
    self._host_path(rel_path).mkdir(parents=True, exist_ok=True)

  def rename(self, src: PurePosixPath, dst: PurePosixPath) -> None:
    self._host_path(src).rename(self._host_path(dst))

  def unlink(self, rel_path: PurePosixPath) -> None:
    self._host_path(rel_path).unlink(missing_ok=True)

  def open_raw(
    self, rel_path: PurePosixPath, *, create: bool
  ) -> sqlite3.Connection:
    path = self._host_path(rel_path)
    if not create and not path.is_file():
      raise FileNotFoundError(path)
    return sqlite3.connect(path, timeout=5, uri=False)


def _db_rel_path(name: ProjectName) -> PurePosixPath:
  return _TMP_DIR / f'{name.value}{PROJECT_SUFFIX}'


def _close_quietly(connection: sqlite3.Connection) -> None:
  with contextlib.suppress(sqlite3.Error):
    connection.close()


@dataclass(frozen=True, slots=True)
class ProjectStore:
  backend: StoreBackend

  @classmethod
  def from_root(cls, root: str | Path) -> 'ProjectStore':
    try:
      resolved = Path(root).resolve()
    except OSError as error:
      raise ProjectError(
        f'Could not resolve project root {root}: {error}'
      ) from error
    return cls(HostStoreBackend(resolved))

  def database_path(self, name: ProjectName) -> str:
    return str(
      self.backend.root / '.tmp' / f'{name.value}{PROJECT_SUFFIX}'
    )

  def handoff_database_path(self, name: ProjectName) -> str:
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

  def create_project(
    self, name: ProjectName, charter: CharterInput
  ) -> Path:
    rel_path = _db_rel_path(name)
    path = Path(self.database_path(name))
    temp_rel = _TMP_DIR / f'.{name.value}-{time.time_ns()}.tmp'
    temp_path = self.backend.root / temp_rel
    try:
      self.backend.mkdir(_TMP_DIR)
    except OSError as error:
      raise ProjectError(
        f'Could not create project directory at '
        f'{self.backend.root / _TMP_DIR}: {error}'
      ) from error
    try:
      connection = self.backend.open_raw(temp_rel, create=True)
    except (OSError, sqlite3.Error) as error:
      self._unlink_ignoring_os_error(temp_rel)
      raise ProjectError(
        f'Could not open temporary project database at {temp_path}: '
        f'{error}'
      ) from error
    try:
      configure_connection(connection)
      initialize_project(connection, name, charter)
    except Exception as error:
      _close_quietly(connection)
      self._unlink_ignoring_os_error(temp_rel)
      if isinstance(error, sqlite3.Error):
        raise ProjectError(
          f'Could not initialize project database at {temp_path}: {error}'
        ) from error
      raise
    try:
      connection.close()
    except sqlite3.Error as error:
      _close_quietly(connection)
      self._unlink_ignoring_os_error(temp_rel)
      raise ProjectError(
        f'Could not finalize temporary project database at {temp_path}: '
        f'{error}'
      ) from error
    archived: tuple[PurePosixPath, Path] | None = None
    try:
      if self.backend.exists(rel_path):
        if not self.backend.is_file(rel_path):
          raise OSError(f'Existing target is not a file: {path}')
        archived = self._archive_existing(name, rel_path)
      self.backend.rename(temp_rel, rel_path)
    except OSError as error:
      if archived is not None:
        archived_rel, archived_path = archived
        try:
          self.backend.rename(archived_rel, rel_path)
        except OSError as restore_error:
          raise ProjectError(
            f'Could not install project database at {path}: {error}; '
            f'the previous database could not be restored from '
            f'{archived_path}: {restore_error}; the new database remains '
            f'at {temp_path}'
          ) from restore_error
      try:
        self.backend.unlink(temp_rel)
      except OSError as cleanup_error:
        raise ProjectError(
          f'Could not install project database at {path}: {error}; '
          f'the temporary database remains at {temp_path}: '
          f'{cleanup_error}'
        ) from cleanup_error
      raise ProjectError(
        f'Could not install project database at {path}: {error}'
      ) from error
    return path

  def archive_project(self, name: ProjectName) -> Path:
    rel_path = _db_rel_path(name)
    try:
      if not self.backend.is_file(rel_path):
        raise ProjectError(f'Project does not exist: {name.value}')
      _, archive_path = self._archive_existing(name, rel_path)
    except OSError as error:
      raise ProjectError(
        f'Could not archive project database at '
        f'{self.database_path(name)}: {error}'
      ) from error
    return archive_path

  @contextmanager
  def open_project(
    self, name: ProjectName
  ) -> Iterator[sqlite3.Connection]:
    rel_path = _db_rel_path(name)
    display_path = self.database_path(name)
    try:
      if not self.backend.is_file(rel_path):
        raise ProjectError(f'Project does not exist: {name.value}')
      connection = self.backend.open_raw(rel_path, create=False)
    except (OSError, sqlite3.Error) as error:
      raise ProjectError(
        f'Project database could not be validated: {display_path}: {error}'
      ) from error
    try:
      configure_connection(connection)
      validate_project(
        connection,
        expected_name=name,
        display_path=display_path,
      )
    except sqlite3.Error as error:
      _close_quietly(connection)
      raise ProjectError(
        f'Project database could not be validated: {display_path}: {error}'
      ) from error
    except Exception:
      _close_quietly(connection)
      raise
    normal_exit = False
    try:
      yield connection
      normal_exit = True
    finally:
      if normal_exit:
        try:
          connection.close()
        except sqlite3.Error as error:
          raise ProjectError(
            f'Project database could not be closed: {display_path}: '
            f'{error}'
          ) from error
      else:
        _close_quietly(connection)

  def list_projects(self) -> tuple[ProjectSummary, ...]:
    try:
      if not self.backend.is_dir(_TMP_DIR):
        return ()
      stems = self.backend.list_sqlite_stems()
    except OSError as error:
      raise ProjectError(
        f'Could not list projects under {self.backend.root / _TMP_DIR}: '
        f'{error}'
      ) from error
    summaries: list[ProjectSummary] = []
    for stem in stems:
      project_name = ProjectName.parse(stem)
      with self.open_project(project_name) as connection:
        summaries.append(
          read_project_summary(
            connection, self.database_path(project_name)
          )
        )
    return tuple(summaries)
