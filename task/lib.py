import os
import sys

import click


class AliasedGroup(click.Group):
  def get_command(self, ctx, cmd_name):
    rv = click.Group.get_command(self, ctx, cmd_name)
    if rv is not None:
      return rv
    for name, cmd in self.commands.items():
      if hasattr(cmd, 'aliases') and cmd_name in cmd.aliases:
        return cmd
    return None


def run_cmd(cmd):
  click.echo(f'Running: {cmd}')
  ret = os.system(cmd)
  if ret != 0:
    # os.system returns exit status (shifted by 8 bits on Unix)
    exit_code = (
      os.waitstatus_to_exitcode(ret)
      if hasattr(os, 'waitstatus_to_exitcode')
      else (ret >> 8)
    )
    sys.exit(exit_code)


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


def build_cargo_cmd(base_cmd, pos_args, extras):
  cmd = list(base_cmd)
  if len(pos_args) > 0:
    cmd.extend(['-p', pos_args[0]])
  if len(pos_args) > 1:
    cmd.append(pos_args[1])
  cmd.extend(extras)
  return cmd


def ensure_clippy_fails_on_warnings(cmd):
  if '--' in cmd:
    cmd.extend(['-D', 'warnings'])
  else:
    cmd.extend(['--', '-D', 'warnings'])
  return cmd
