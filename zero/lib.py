import os
import shlex
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, ParamSpec, TypeVar

import click

P = ParamSpec('P')
R = TypeVar('R')

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Timer:
  started_at: float = field(default_factory=time.monotonic)

  def duration(self) -> float:
    return time.monotonic() - self.started_at


def sanitize_text(text: str) -> str:
  return text.encode('utf-8', 'backslashreplace').decode('utf-8')


def status(label: str, duration: float, success: bool = True) -> None:
  colour = 'green' if success else 'red'
  text = 'PASS' if success else 'FAIL'
  click.echo(
    f'[{click.style(text, fg=colour, bold=True)}] '
    f'{sanitize_text(label)} ({duration:.2f}s)'
  )


def parse_git_ls_files(stdout: bytes) -> tuple[Path, ...]:
  """Parse NUL-delimited `git ls-files -z` output into unique paths."""
  return tuple(
    dict.fromkeys(
      Path(os.fsdecode(raw_path))
      for raw_path in stdout.split(b'\0')
      if raw_path
    )
  )


def git_ls_files(
  root: str | os.PathLike[str],
  *pathspecs: str,
  error_prefix: str = 'Cannot scan repository with git',
) -> tuple[Path, ...]:
  """List tracked and non-ignored Git paths under root."""
  command = [
    'git',
    '-C',
    os.fspath(root),
    'ls-files',
    '--cached',
    '--others',
    '--exclude-standard',
    '-z',
  ]
  if pathspecs:
    command.extend(('--', *pathspecs))
  try:
    completed = subprocess.run(command, capture_output=True, check=False)
  except OSError as error:
    raise RuntimeError(
      sanitize_text(f'{error_prefix}: {error}')
    ) from error

  if completed.returncode != 0:
    detail = (
      completed.stderr.decode(errors='replace').strip()
      or 'unknown git error'
    )
    raise RuntimeError(sanitize_text(f'{error_prefix}: {detail}'))

  return parse_git_ls_files(completed.stdout)


def nix_files(root: str | os.PathLike[str] = '.') -> list[str]:
  """List regular non-symlink Nix files tracked or visible to Git."""
  matches: set[str] = set()
  for rel_path in git_ls_files(
    root, '*.nix', error_prefix='Cannot scan Nix files with git'
  ):
    candidate = Path(root, rel_path)
    try:
      is_candidate = not candidate.is_symlink() and candidate.is_file()
    except OSError as error:
      raise RuntimeError(
        sanitize_text(f'Cannot scan Nix files: {error}')
      ) from error
    if is_candidate:
      matches.add(str(candidate))
  return sorted(matches)


def _validate_aliases(aliases: Sequence[str]) -> tuple[str, ...]:
  if isinstance(aliases, str):
    raise TypeError('aliases must not be a string')
  seen: set[str] = set()
  validated: list[str] = []
  for alias in aliases:
    if not alias:
      raise ValueError('Command alias must be non-empty')
    if alias in seen:
      raise ValueError(f'Duplicate command alias: {alias!r}')
    seen.add(alias)
    validated.append(alias)
  return tuple(validated)


class AliasedGroup(click.Group):
  _aliases: dict[str, str]

  def _alias_map(self) -> dict[str, str]:
    aliases = vars(self).get('_aliases')
    if aliases is None:
      aliases = {}
      self._aliases = aliases
    return aliases

  def add_command(
    self,
    cmd: click.Command,
    name: str | None = None,
    *,
    aliases: Sequence[str] = (),
  ) -> None:
    cmd_name = name or cmd.name
    if not cmd_name:
      raise ValueError('Command must have a name')
    alias_map = self._alias_map()
    alias_tuple = _validate_aliases(aliases)
    for alias in alias_tuple:
      if alias == cmd_name:
        raise ValueError(
          f'Alias {alias!r} cannot match command name {cmd_name!r}'
        )
      if alias in self.commands:
        raise ValueError(
          f'Alias {alias!r} collides with command {alias!r}'
        )
      owner = alias_map.get(alias)
      if owner is not None and owner != cmd_name:
        raise ValueError(
          f'Alias {alias!r} is already registered to {owner!r}'
        )
    owner = alias_map.get(cmd_name)
    if owner is not None:
      raise ValueError(
        f'Command {cmd_name!r} collides with alias for {owner!r}'
      )

    for existing_alias, existing_owner in list(alias_map.items()):
      if existing_owner == cmd_name:
        del alias_map[existing_alias]
    super().add_command(cmd, name=cmd_name)
    for alias in alias_tuple:
      alias_map[alias] = cmd_name

  def get_command(
    self, ctx: click.Context, cmd_name: str
  ) -> click.Command | None:
    rv = click.Group.get_command(self, ctx, cmd_name)
    if rv is not None:
      return rv
    canonical = self._alias_map().get(cmd_name)
    if canonical is None:
      return None
    return click.Group.get_command(self, ctx, canonical)


def check_cmd(
  cmd: list[str] | tuple[str, ...],
  label: str | None = None,
  *,
  cwd: Path | None = None,
) -> int:
  if not cmd:
    raise ValueError('cmd must be non-empty')

  display = sanitize_text(shlex.join(cmd))
  resolved_label = display if label is None else label

  click.echo(f'Running: {display}')
  t = Timer()
  try:
    completed = subprocess.run(cmd, cwd=cwd, check=False)
  except OSError as error:
    click.echo(f'Error: {sanitize_text(str(error))}', err=True)
    status(resolved_label, t.duration(), success=False)
    return 1

  duration = t.duration()
  exit_code = (
    128 - completed.returncode
    if completed.returncode < 0
    else completed.returncode
  )
  status(resolved_label, duration, success=(exit_code == 0))
  return exit_code


def run_cmd(
  cmd: list[str] | tuple[str, ...],
  label: str | None = None,
  *,
  cwd: Path | None = None,
) -> None:
  exit_code = check_cmd(cmd, label, cwd=cwd)
  if exit_code != 0:
    raise SystemExit(exit_code)


def command_with_aliases(
  group: AliasedGroup,
  aliases: Sequence[str] = (),
  *,
  name: str | None = None,
  context_settings: Mapping[str, object] | None = None,
) -> Callable[[Callable[P, R]], click.Command]:
  alias_tuple = _validate_aliases(aliases)
  settings = None if context_settings is None else dict(context_settings)

  def decorator(function: Callable[P, R]) -> click.Command:
    command = click.command(name=name, context_settings=settings)(function)
    group.add_command(command, aliases=alias_tuple)
    return command

  return decorator


def group_with_aliases(
  group: AliasedGroup,
  aliases: Sequence[str] = (),
  cls: type[AliasedGroup] | None = None,
  *,
  name: str | None = None,
  invoke_without_command: bool = False,
  subcommand_metavar: str | None = None,
  context_settings: Mapping[str, object] | None = None,
) -> Callable[[Callable[P, R]], AliasedGroup]:
  alias_tuple = _validate_aliases(aliases)
  group_cls = AliasedGroup if cls is None else cls
  settings = None if context_settings is None else dict(context_settings)

  def decorator(function: Callable[P, R]) -> AliasedGroup:
    command = click.group(
      name=name,
      cls=group_cls,
      invoke_without_command=invoke_without_command,
      subcommand_metavar=subcommand_metavar,
      context_settings=settings,
    )(function)
    if not isinstance(command, AliasedGroup):
      raise TypeError('group_with_aliases created a non-aliased group')
    group.add_command(command, aliases=alias_tuple)
    return command

  return decorator


def get_cargo_clippy_cmd(package: str | None = None) -> list[str]:
  cmd = ['cargo', 'clippy']
  if package:
    cmd.extend(['-p', package])
  cmd.extend(['--all-targets', '--all-features', '--', '-D', 'warnings'])
  return cmd


def get_cargo_fix_cmd(package: str | None = None) -> list[str]:
  cmd = ['cargo', 'fixit', '--allow-dirty', '--allow-staged']
  if package:
    cmd.extend(['-p', package])
  cmd.extend(['--all-targets', '--all-features'])
  return cmd


def get_cargo_test_cmd(
  package: str | None = None,
  test_name: str | None = None,
  *,
  nocapture: bool = False,
  exact: bool = False,
) -> list[str]:
  cmd = ['cargo', 'test']
  if package:
    cmd.extend(['-p', package])
  if test_name:
    cmd.append(test_name)
  if exact or nocapture:
    cmd.append('--')
    if exact:
      cmd.append('--exact')
    if nocapture:
      cmd.append('--nocapture')
  return cmd


def json_object(value: object) -> dict[str, object] | None:
  if not isinstance(value, Mapping):
    return None
  result: dict[str, object] = {}
  for key, item in value.items():
    if not isinstance(key, str):
      return None
    result[key] = item
  return result


def string_list(value: object) -> list[str] | None:
  if not isinstance(value, list):
    return None
  result: list[str] = []
  for item in value:
    if not isinstance(item, str):
      return None
    result.append(item)
  return result
