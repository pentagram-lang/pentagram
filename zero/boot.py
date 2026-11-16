import os
import shlex
from collections.abc import Sequence

import click

from zero.lib import sanitize_text


def build_shell_command(args: Sequence[str]) -> list[str]:
  """Build the cargo command line that launches the boot shell."""
  return ['cargo', 'run', '-p', 'boot_shell', '--', *args]


def format_exec_announcement(cmd: Sequence[str]) -> str:
  """Format the pre-exec command announcement."""
  return f'Exec: {sanitize_text(shlex.join(cmd))}'


def run_shell(args: Sequence[str]) -> None:
  """Run the boot_shell via cargo run, replacing the current process."""
  cmd = build_shell_command(args)
  try:
    print(format_exec_announcement(cmd), flush=True)
    os.execvp('cargo', cmd)
  except OSError as error:
    raise click.ClickException(
      sanitize_text(f'Failed to launch boot_shell: {error}')
    ) from error
