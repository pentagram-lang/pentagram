from __future__ import annotations

import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import click

Runner = Callable[[Sequence[str], Path | None], int]


@dataclass(frozen=True, slots=True)
class Diagnostic:
  path: str
  message: str
  line: int | None = None

  def format(self) -> str:
    if self.line is not None:
      return f'{self.path}:{self.line}: {self.message}'
    return f'{self.path}: {self.message}'


def find_repo_root(start: Path | None = None) -> Path:
  base = (Path.cwd() if start is None else start).resolve()
  for candidate in (base, *base.parents):
    if (candidate / 'zero' / '__main__.py').is_file():
      return candidate
  raise click.ClickException(
    'zero/__main__.py not found in parent directories.'
  )


def run_cmd(cmd: Sequence[str], cwd: Path | None = None) -> int:
  print(f'Running: {shlex.join(cmd)}', flush=True)
  try:
    return subprocess.run(cmd, cwd=cwd, check=False).returncode
  except OSError as err:
    print(f'Error: {err}', file=sys.stderr, flush=True)
    return 127


def timed_step(label: str, action: Callable[[], bool]) -> bool:
  start = time.perf_counter()
  ok = action()
  elapsed = time.perf_counter() - start
  status = 'PASS' if ok else 'FAIL'
  print(f'[{status}] {label} ({elapsed:.2f}s)', flush=True)
  return ok


def run_timed_cmd(
  label: str,
  cmd: Sequence[str],
  *,
  cwd: Path | None = None,
  runner: Runner = run_cmd,
) -> bool:
  return timed_step(label, lambda: runner(cmd, cwd) == 0)


def git_ls_files(repo: Path) -> list[str]:
  try:
    proc = subprocess.run(
      [
        'git',
        '-C',
        str(repo),
        'ls-files',
        '-z',
        '--cached',
        '--others',
        '--exclude-standard',
      ],
      capture_output=True,
      check=True,
    )
  except (OSError, subprocess.CalledProcessError) as err:
    raise click.ClickException(f'git ls-files failed: {err}') from err
  return sorted(
    {
      entry.decode('utf-8')
      for entry in proc.stdout.split(b'\x00')
      if entry
    }
  )


def nix_files(
  repo: Path, inventory: Sequence[str] | None = None
) -> list[str]:
  paths = git_ls_files(repo) if inventory is None else inventory
  return [
    rel
    for rel in paths
    if rel.endswith('.nix')
    and not (p := repo / rel).is_symlink()
    and p.is_file()
  ]


def cargo_package_args(package: str | None) -> list[str]:
  return ['-p', package] if package else []


class AliasedGroup(click.Group):
  def __init__(
    self,
    name: str | None = None,
    commands: (
      MutableMapping[str, click.Command] | Sequence[click.Command] | None
    ) = None,
    aliases: Mapping[str, str] | None = None,
    *,
    invoke_without_command: bool = False,
    no_args_is_help: bool | None = None,
    subcommand_metavar: str | None = None,
    chain: bool = False,
    result_callback: Callable[..., object] | None = None,
    **attrs: object,
  ) -> None:
    super().__init__(
      name=name,
      commands=commands,
      invoke_without_command=invoke_without_command,
      no_args_is_help=no_args_is_help,
      subcommand_metavar=subcommand_metavar,
      chain=chain,
      result_callback=result_callback,
      **attrs,
    )
    self._aliases = dict(aliases) if aliases else {}

  def get_command(
    self, ctx: click.Context, cmd_name: str
  ) -> click.Command | None:
    target = self._aliases.get(cmd_name, cmd_name)
    return super().get_command(ctx, target)
