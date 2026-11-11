import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ParamSpec, TypeVar

import click

P = ParamSpec('P')
R = TypeVar('R')


@dataclass(frozen=True)
class Timer:
  started_at: float = field(default_factory=time.monotonic)

  def duration(self) -> float:
    return time.monotonic() - self.started_at


def status(
  label: str,
  duration: float,
  success: bool = True,
  informational: bool = False,
) -> None:
  if success and informational:
    colour = 'blue'
    text = 'INFO'
  else:
    colour = 'green' if success else 'red'
    text = 'PASS' if success else 'FAIL'
  click.echo(
    f'[{click.style(text, fg=colour, bold=True)}] '
    f'{label} ({duration:.2f}s)'
  )


class AliasedCommand(click.Command):
  aliases: list[str]


def _command_aliases(command: click.Command) -> list[str]:
  value: object = getattr(command, 'aliases', None)
  if not isinstance(value, list):
    return []
  aliases = []
  for alias in value:
    if not isinstance(alias, str):
      return []
    aliases.append(alias)
  return aliases


class AliasedGroup(click.Group):
  aliases: list[str]
  command_class: type[AliasedCommand] = AliasedCommand

  def get_command(
    self, ctx: click.Context, cmd_name: str
  ) -> click.Command | None:
    rv = click.Group.get_command(self, ctx, cmd_name)
    if rv is not None:
      return rv
    for cmd in self.commands.values():
      if cmd_name in _command_aliases(cmd):
        return cmd
    return None


def run_cmd(
  cmd: str,
  label: str | None = None,
  informational_success: bool = False,
) -> None:
  if label is None:
    label = cmd

  click.echo(f'Running: {cmd}')
  t = Timer()
  ret = os.system(cmd)
  d = t.duration()

  if ret != 0:
    status(label, d, success=False)
    # os.system returns exit status (shifted by 8 bits on Unix)
    if ret == -1:
      exit_code = 1
    elif hasattr(os, 'waitstatus_to_exitcode'):
      exit_code = os.waitstatus_to_exitcode(ret)
      if exit_code < 0:
        exit_code = 128 - exit_code
    else:
      exit_code = ret >> 8
    sys.exit(exit_code)

  status(label, d, success=True, informational=informational_success)


def command_with_aliases(
  group: AliasedGroup,
  aliases: list[str] | None = None,
  **kwargs: object,
) -> Callable[[Callable[P, R]], AliasedCommand]:
  if aliases is None:
    aliases = []

  def decorator(function: Callable[P, R]) -> AliasedCommand:
    command = group.command(**kwargs)(function)
    if not isinstance(command, AliasedCommand):
      raise TypeError('AliasedGroup created a non-aliased command')
    command.aliases = aliases
    return command

  return decorator


def group_with_aliases(
  group: AliasedGroup,
  aliases: list[str] | None = None,
  cls: type[AliasedGroup] | None = None,
  **kwargs: object,
) -> Callable[[Callable[P, R]], AliasedGroup]:
  if aliases is None:
    aliases = []
  if cls is None:
    cls = AliasedGroup

  def decorator(function: Callable[P, R]) -> AliasedGroup:
    command = group.group(cls=cls, **kwargs)(function)
    if not isinstance(command, AliasedGroup):
      raise TypeError('AliasedGroup created a non-aliased group')
    command.aliases = aliases
    return command

  return decorator


def parse_args(
  args: list[str], max_pos: int = 1
) -> tuple[list[str], list[str]]:
  pos = []
  idx = 0
  # Parse positionals
  while idx < len(args) and len(pos) < max_pos:
    arg = args[idx]
    if arg == '--':
      break
    if arg.startswith('-'):
      break
    pos.append(arg)
    idx += 1

  extras = args[idx:]
  return pos, extras


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
  extras: list[str] | None = None,
  nocapture: bool = False,
) -> list[str]:
  cmd = ['cargo', 'test']
  if package:
    cmd.extend(['-p', package])
  if test_name:
    cmd.append(test_name)
  if extras:
    cmd.extend(extras)

  if nocapture:
    if '--' in cmd:
      cmd.append('--nocapture')
    else:
      cmd.extend(['--', '--nocapture'])

  return cmd
