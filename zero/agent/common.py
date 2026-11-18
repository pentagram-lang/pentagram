from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import click

ExecFn = Callable[[Path, Sequence[str], Sequence[str]], None]

_ENV_VAR_RE = re.compile(
  r'\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))'
)


def json_object(value: object) -> dict[str, object] | None:
  if not isinstance(value, Mapping):
    return None
  out: dict[str, object] = {}
  for key, item in value.items():
    if not isinstance(key, str):
      return None
    out[key] = item
  return out


def string_list(value: object) -> list[str] | None:
  if not isinstance(value, list):
    return None
  out: list[str] = []
  for item in value:
    if not isinstance(item, str):
      return None
    out.append(item)
  return out


def is_under(path: Path, root: Path) -> bool:
  try:
    return path.resolve().is_relative_to(root.resolve())
  except (OSError, RuntimeError):
    return False


def expand_env_path(
  raw_path: str, home: Path, environ: Mapping[str, str]
) -> Path:
  def _replace(match: re.Match[str]) -> str:
    name = match.group(1) or match.group(2)
    return environ[name] if name in environ else match.group(0)

  if raw_path == '~':
    return home
  if raw_path.startswith('~/'):
    rest = _ENV_VAR_RE.sub(_replace, raw_path[2:])
    return Path(f'{home}/{rest}')
  return Path(_ENV_VAR_RE.sub(_replace, raw_path))


def read_regular_text(
  path: Path, label: str
) -> tuple[str | None, str | None]:
  try:
    path.lstat()
  except FileNotFoundError:
    return None, None
  except OSError as err:
    return None, f'Could not stat {label} ({path}): {err}'

  try:
    st = path.stat()
  except OSError as err:
    return None, f'Could not stat {label} ({path}): {err}'

  if not stat.S_ISREG(st.st_mode):
    return None, f'{label} ({path}) is not a regular file'

  try:
    return path.read_text(encoding='utf-8'), None
  except OSError as err:
    return None, f'Could not read {label} ({path}): {err}'
  except UnicodeDecodeError as err:
    return None, f'Invalid UTF-8 in {label} ({path}): {err}'


def parse_json_object(
  raw: str, path: Path, label: str
) -> tuple[dict[str, object] | None, str | None]:
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError as err:
    return None, f'Invalid JSON in {label} ({path}): {err}'
  obj = json_object(parsed)
  if obj is None:
    return None, f'Expected JSON object in {label} ({path})'
  return obj, None


def read_json_file(
  path: Path, label: str
) -> tuple[dict[str, object] | None, str | None]:
  raw, err = read_regular_text(path, label)
  if err is not None:
    return None, err
  if raw is None:
    return None, None
  return parse_json_object(raw, path, label)


def check_ambient_file(
  path: Path, *, label: str
) -> tuple[Path | None, str | None]:
  try:
    path.lstat()
  except FileNotFoundError:
    return None, None
  except OSError as err:
    return None, f'Could not stat {label} ({path}): {err}'

  try:
    st = path.stat()
  except FileNotFoundError:
    return None, None
  except OSError as err:
    return None, f'Could not stat {label} ({path}): {err}'

  if not stat.S_ISREG(st.st_mode):
    return None, f'{label} ({path}) is not a regular file'
  return path, None


def _matches_ambient(
  path: Path, *, match_name: str | None, suffix: str | None
) -> bool:
  if match_name is not None and path.name != match_name:
    return False
  if suffix is not None and not path.name.endswith(suffix):
    return False
  return True


def scan_ambient_files(
  root: Path,
  *,
  label: str,
  match_name: str | None = None,
  suffix: str | None = None,
  allow_single_file: bool = False,
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
  try:
    root.lstat()
  except FileNotFoundError:
    return (), ()
  except OSError as err:
    return (), (f'Could not stat {label} ({root}): {err}',)

  try:
    root_stat = root.stat()
  except FileNotFoundError:
    return (), ()
  except OSError as err:
    return (), (f'Could not stat {label} ({root}): {err}',)

  if stat.S_ISREG(root_stat.st_mode):
    if not allow_single_file:
      return (), (f'{label} ({root}) is not a directory',)
    if _matches_ambient(root, match_name=match_name, suffix=suffix):
      return (root,), ()
    return (), ()

  if not stat.S_ISDIR(root_stat.st_mode):
    return (), (f'{label} ({root}) is not a directory',)

  root_key = (root_stat.st_dev, root_stat.st_ino)
  pending: list[tuple[Path, frozenset[tuple[int, int]]]] = [
    (root, frozenset({root_key}))
  ]
  found: list[Path] = []
  errors: list[str] = []

  while pending:
    current, ancestors = pending.pop()
    try:
      with os.scandir(current) as entries_iter:
        entries = sorted(entries_iter, key=lambda entry: entry.name)
    except OSError as err:
      errors.append(f'Could not scan {label} ({current}): {err}')
      continue

    for entry in entries:
      entry_path = Path(entry.path)
      try:
        st = entry.stat(follow_symlinks=True)
      except FileNotFoundError:
        continue
      except OSError as err:
        errors.append(f'Could not stat {label} ({entry_path}): {err}')
        continue

      if stat.S_ISDIR(st.st_mode):
        key = (st.st_dev, st.st_ino)
        if key not in ancestors:
          pending.append((entry_path, ancestors | {key}))
      elif stat.S_ISREG(st.st_mode):
        if _matches_ambient(
          entry_path, match_name=match_name, suffix=suffix
        ):
          found.append(entry_path)
      else:
        errors.append(f'{label} ({entry_path}) is not a regular file')

  return tuple(sorted(found)), tuple(errors)


def raise_preflight(provider: str, findings: Sequence[str]) -> None:
  if not findings:
    return
  details = '\n'.join(f'  - {finding}' for finding in findings)
  raise click.ClickException(
    f'{provider} filesystem preflight failed:\n{details}'
  )


def exec_agent(
  project_root: Path,
  command: Sequence[str],
  arguments: Sequence[str],
) -> None:
  try:
    os.chdir(project_root)
    os.execvpe(command[0], [*command, *arguments], os.environ)
  except OSError as error:
    raise click.ClickException(
      f'Failed to launch agent {command[0]}: {error}'
    ) from error
