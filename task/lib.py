import os
import sys
import time

import click


class Timer:
  def __init__(self):
    self.start = time.time()

  def duration(self):
    return time.time() - self.start


def status(label, duration, success=True):
  color = 'green' if success else 'red'
  text = 'PASS' if success else 'FAIL'
  click.echo(
    f'[{click.style(text, fg=color, bold=True)}] {label} ({duration:.2f}s)'
  )


class AliasedGroup(click.Group):
  def get_command(self, ctx, cmd_name):
    rv = click.Group.get_command(self, ctx, cmd_name)
    if rv is not None:
      return rv
    for name, cmd in self.commands.items():
      if hasattr(cmd, 'aliases') and cmd_name in cmd.aliases:
        return cmd
    return None


def run_cmd(cmd, label=None):
  if label is None:
    label = cmd

  click.echo(f'Running: {cmd}')
  t = Timer()
  ret = os.system(cmd)
  d = t.duration()

  if ret != 0:
    status(label, d, success=False)
    # os.system returns exit status (shifted by 8 bits on Unix)
    exit_code = (
      os.waitstatus_to_exitcode(ret)
      if hasattr(os, 'waitstatus_to_exitcode')
      else (ret >> 8)
    )
    sys.exit(exit_code)

  status(label, d, success=True)


def command_with_aliases(group, aliases=None, **kwargs):
  if aliases is None:
    aliases = []

  def decorator(f):
    cmd = group.command(**kwargs)(f)
    cmd.aliases = aliases
    return cmd

  return decorator


def group_with_aliases(group, aliases=None, cls=None, **kwargs):
  if aliases is None:
    aliases = []
  if cls is None:
    cls = AliasedGroup

  def decorator(f):
    cmd = group.group(cls=cls, **kwargs)(f)
    cmd.aliases = aliases
    return cmd

  return decorator


def parse_args(args, max_pos=1):
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


def get_cargo_clippy_cmd(package=None):
  cmd = ['cargo', 'clippy']
  if package:
    cmd.extend(['-p', package])
  cmd.extend(['--all-targets', '--all-features', '--', '-D', 'warnings'])
  return cmd


def get_cargo_fix_cmd(package=None):
  cmd = ['cargo', 'fixit', '--allow-dirty', '--allow-staged']
  if package:
    cmd.extend(['-p', package])
  cmd.extend(['--all-targets', '--all-features'])
  return cmd


def get_cargo_test_cmd(
  package=None, test_name=None, extras=None, nocapture=False
):
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
