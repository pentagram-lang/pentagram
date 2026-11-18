from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Never

import click

ExecVp = Callable[[str, Sequence[str]], Never]


def _default_execvp(file: str, args: Sequence[str]) -> Never:
  os.execvp(file, list(args))


def run_boot(
  args: Sequence[str], *, execvp: ExecVp = _default_execvp
) -> Never:
  try:
    execvp('cargo', ['cargo', 'run', '-p', 'boot_shell', '--', *args])
  except OSError as err:
    raise click.ClickException(
      f'Failed to launch boot_shell: {err}'
    ) from err
