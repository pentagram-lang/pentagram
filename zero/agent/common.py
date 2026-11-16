import json
import os
import stat
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path

import click

from zero.lib import json_object

type JsonObject = Mapping[str, object]


def is_under(path: Path, root: Path) -> bool:
  """Return whether path is equal to root or nested inside root."""
  return path == root or root in path.parents


def parse_json_object(
  raw: str, path: Path, label: str
) -> tuple[dict[str, object] | None, str | None]:
  """Parse raw JSON text as an object, returning (object, error)."""
  try:
    value = json.loads(raw)
  except json.JSONDecodeError as error:
    return None, f'Cannot read {label} {path}: {error}'
  obj = json_object(value)
  if obj is None:
    return None, f'{label} must contain a JSON object: {path}'
  return obj, None


def read_regular_text(
  path: Path, label: str
) -> tuple[str | None, str | None]:
  """Read UTF-8 text from an existing regular file, fail-closed."""
  try:
    path.lstat()
  except (FileNotFoundError, NotADirectoryError):
    return None, None
  except OSError as error:
    return None, f'Cannot read {label} {path}: {error}'

  try:
    st = path.stat()
  except OSError as error:
    return None, f'Cannot read {label} {path}: {error}'
  if not stat.S_ISREG(st.st_mode):
    return None, f'{label} path is not a file: {path}'

  try:
    return path.read_text(encoding='utf-8'), None
  except (OSError, UnicodeDecodeError) as error:
    return None, f'Cannot read {label} {path}: {error}'


def read_json_file(
  path: Path, label: str
) -> tuple[dict[str, object] | None, str | None]:
  """Read and parse a JSON object file if present."""
  raw, error = read_regular_text(path, label)
  if raw is None:
    return None, error
  return parse_json_object(raw, path, label)


def check_ambient_file(
  path: Path, *, label: str
) -> tuple[Path | None, str | None]:
  """Resolve path when regular file, recording scan errors."""
  try:
    lst = path.lstat()
  except (FileNotFoundError, NotADirectoryError):
    return None, None
  except OSError as error:
    return None, f'Cannot scan {label} {path}: {error}'

  is_link = stat.S_ISLNK(lst.st_mode)
  try:
    st = path.stat()
  except (FileNotFoundError, NotADirectoryError) as error:
    if is_link:
      return None, None
    return None, f'Cannot scan {label} {path}: {error}'
  except OSError as error:
    return None, f'Cannot scan {label} {path}: {error}'

  if not stat.S_ISREG(st.st_mode):
    return None, None
  try:
    return path.resolve(strict=True), None
  except OSError as error:
    return None, f'Cannot scan {label} {path}: {error}'


def _matches_ambient_file(
  name: str, match_name: str | None, suffix: str | None
) -> bool:
  if match_name is not None and name != match_name:
    return False
  return suffix is None or Path(name).suffix == suffix


def scan_ambient_files(
  root: Path,
  *,
  label: str,
  match_name: str | None = None,
  suffix: str | None = None,
  allow_single_file: bool = False,
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
  """Scan root recursively for matching regular files via os.scandir."""
  try:
    lst = root.lstat()
  except (FileNotFoundError, NotADirectoryError):
    return (), ()
  except OSError as error:
    return (), (f'Cannot scan {label} {root}: {error}',)

  is_link = stat.S_ISLNK(lst.st_mode)
  try:
    st = root.stat()
  except (FileNotFoundError, NotADirectoryError) as error:
    if is_link:
      return (), ()
    return (), (f'Cannot scan {label} {root}: {error}',)
  except OSError as error:
    return (), (f'Cannot scan {label} {root}: {error}',)

  if stat.S_ISREG(st.st_mode):
    if allow_single_file and _matches_ambient_file(
      root.name, match_name, suffix
    ):
      try:
        return (root.resolve(strict=True),), ()
      except OSError as error:
        return (), (f'Cannot scan {label} {root}: {error}',)
    return (), ()

  if not stat.S_ISDIR(st.st_mode):
    return (), ()

  seen_files: set[Path] = set()
  findings: list[str] = []
  visited_dirs: set[tuple[int, int]] = {(st.st_dev, st.st_ino)}
  pending: deque[Path] = deque([root])

  while pending:
    current_dir = pending.popleft()
    try:
      with os.scandir(current_dir) as entries:
        entry_list = sorted(entries, key=lambda item: item.name)
    except OSError as error:
      findings.append(f'Cannot scan {label} {current_dir}: {error}')
      continue

    for entry in entry_list:
      entry_path = Path(entry.path)
      try:
        entry_is_link = entry.is_symlink()
      except OSError as error:
        findings.append(f'Cannot scan {label} {entry_path}: {error}')
        continue

      try:
        entry_stat = entry.stat(follow_symlinks=True)
      except (FileNotFoundError, NotADirectoryError) as error:
        if entry_is_link:
          continue
        findings.append(f'Cannot scan {label} {entry_path}: {error}')
        continue
      except OSError as error:
        findings.append(f'Cannot scan {label} {entry_path}: {error}')
        continue

      if stat.S_ISDIR(entry_stat.st_mode):
        dir_key = (entry_stat.st_dev, entry_stat.st_ino)
        if dir_key not in visited_dirs:
          visited_dirs.add(dir_key)
          pending.append(entry_path)
        continue

      if not stat.S_ISREG(entry_stat.st_mode):
        continue
      if not _matches_ambient_file(entry.name, match_name, suffix):
        continue
      try:
        resolved = entry_path.resolve(strict=True)
      except OSError as error:
        findings.append(f'Cannot scan {label} {entry_path}: {error}')
        continue
      seen_files.add(resolved)

  return tuple(sorted(seen_files)), tuple(findings)


def exec_agent(
  project_root: Path, command: Sequence[str], arguments: Sequence[str]
) -> None:
  """Replace the current process with the configured agent command."""
  try:
    os.chdir(project_root)
    os.execvpe(command[0], [*command, *arguments], os.environ)
  except OSError as error:
    raise click.ClickException(
      f'Failed to launch agent {command[0]}: {error}'
    ) from error
