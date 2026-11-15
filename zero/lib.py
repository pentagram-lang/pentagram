import os
import shlex
import subprocess
import time
from collections.abc import Callable
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


def nix_files(root: str | os.PathLike[str] = '.') -> list[str]:
  try:
    completed = subprocess.run(
      [
        'git',
        '-C',
        os.fspath(root),
        'ls-files',
        '--cached',
        '--others',
        '--exclude-standard',
        '-z',
        '--',
        '*.nix',
      ],
      capture_output=True,
      check=False,
    )
  except OSError as error:
    raise RuntimeError(
      sanitize_text(f'Cannot scan Nix files with git: {error}')
    ) from error

  if completed.returncode != 0:
    detail = (
      completed.stderr.decode(errors='replace').strip()
      or 'unknown git error'
    )
    raise RuntimeError(f'Cannot scan Nix files with git: {detail}')

  matches: set[str] = set()
  for raw_path in completed.stdout.split(b'\0'):
    if not raw_path:
      continue
    rel_path = os.fsdecode(raw_path)
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


class AliasedCommand(click.Command):
  aliases: tuple[str, ...] | list[str] = ()


class AliasedGroup(click.Group):
  aliases: tuple[str, ...] | list[str] = ()
  command_class: type[AliasedCommand] = AliasedCommand

  def get_command(
    self, ctx: click.Context, cmd_name: str
  ) -> click.Command | None:
    rv = click.Group.get_command(self, ctx, cmd_name)
    if rv is not None:
      return rv
    for cmd in self.commands.values():
      if isinstance(cmd, (AliasedCommand, AliasedGroup)) and (
        cmd_name in cmd.aliases
      ):
        return cmd
    return None


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
  aliases: list[str] | tuple[str, ...] = (),
  **kwargs: object,
) -> Callable[[Callable[P, R]], AliasedCommand]:
  alias_tuple = tuple(aliases)

  def decorator(function: Callable[P, R]) -> AliasedCommand:
    command = group.command(**kwargs)(function)
    if not isinstance(command, AliasedCommand):
      raise TypeError('AliasedGroup created a non-aliased command')
    command.aliases = alias_tuple
    return command

  return decorator


def group_with_aliases(
  group: AliasedGroup,
  aliases: list[str] | tuple[str, ...] = (),
  cls: type[AliasedGroup] | None = None,
  **kwargs: object,
) -> Callable[[Callable[P, R]], AliasedGroup]:
  alias_tuple = tuple(aliases)
  if cls is None:
    cls = AliasedGroup

  def decorator(function: Callable[P, R]) -> AliasedGroup:
    command = group.group(cls=cls, **kwargs)(function)
    if not isinstance(command, AliasedGroup):
      raise TypeError('AliasedGroup created a non-aliased group')
    command.aliases = alias_tuple
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
