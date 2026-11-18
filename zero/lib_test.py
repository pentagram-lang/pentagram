from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from zero.lib import (
  AliasedGroup,
  Diagnostic,
  cargo_package_args,
  find_repo_root,
  git_ls_files,
  nix_files,
  run_cmd,
  run_timed_cmd,
  timed_step,
)


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='zero-lib-test-', dir='/dev/shm'))
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def test_diagnostic_format() -> None:
  assert Diagnostic('a.py', 'bad').format() == 'a.py: bad'
  assert Diagnostic('a.py', 'bad', 12).format() == 'a.py:12: bad'


def test_find_repo_root(shm_dir: Path) -> None:
  repo = shm_dir / 'repo'
  nested = repo / 'a' / 'b'
  nested.mkdir(parents=True)
  (repo / 'zero').mkdir()

  with pytest.raises(
    click.ClickException,
    match=r'zero/__main__\.py not found in parent directories\.',
  ):
    find_repo_root(nested)

  (repo / 'zero' / '__main__.py').mkdir()
  with pytest.raises(click.ClickException):
    find_repo_root(nested)

  (repo / 'zero' / '__main__.py').rmdir()
  (repo / 'zero' / '__main__.py').write_text('', encoding='utf-8')
  assert find_repo_root(nested) == repo.resolve()


def test_timed_step_and_runners(
  capsys: pytest.CaptureFixture[str], shm_dir: Path
) -> None:
  assert timed_step('ok', lambda: True) is True
  assert timed_step('bad', lambda: False) is False

  seen: list[tuple[tuple[str, ...], Path | None]] = []

  def fake_runner(cmd: Sequence[str], cwd: Path | None) -> int:
    seen.append((tuple(cmd), cwd))
    return 0 if list(cmd) == ['echo', 'hi'] else 2

  assert run_timed_cmd(
    'echo', ['echo', 'hi'], cwd=shm_dir, runner=fake_runner
  )
  assert (
    run_timed_cmd('fail', ['false'], cwd=None, runner=fake_runner) is False
  )
  assert seen == [(('echo', 'hi'), shm_dir), (('false',), None)]

  rc = run_cmd([sys.executable, '-c', 'raise SystemExit(3)'], cwd=shm_dir)
  assert rc == 3

  out_lines = capsys.readouterr().out.splitlines()
  assert len(out_lines) == 5
  assert out_lines[0].startswith('[PASS] ok (')
  assert out_lines[1].startswith('[FAIL] bad (')
  assert out_lines[2].startswith('[PASS] echo (')
  assert out_lines[3].startswith('[FAIL] fail (')
  assert out_lines[4].startswith('Running: ')


def test_git_ls_files_and_nix_files(shm_dir: Path) -> None:
  subprocess.run(['git', 'init', '-q', str(shm_dir)], check=True)
  (shm_dir / '.gitignore').write_text('ignored.nix\n', encoding='utf-8')
  (shm_dir / 'a.nix').write_text('{}\n', encoding='utf-8')
  (shm_dir / 'deleted.nix').write_text('{}\n', encoding='utf-8')
  (shm_dir / 'ignored.nix').write_text('{}\n', encoding='utf-8')
  (shm_dir / 'sub').mkdir()
  (shm_dir / 'sub' / 'b.nix').write_text('{}\n', encoding='utf-8')
  (shm_dir / 'link.nix').symlink_to('a.nix')
  (shm_dir / 'readme.md').write_text('# Hi\n', encoding='utf-8')

  subprocess.run(
    ['git', '-C', str(shm_dir), 'add', 'a.nix', 'deleted.nix'],
    check=True,
  )
  (shm_dir / 'deleted.nix').unlink()

  inv = git_ls_files(shm_dir)
  assert inv == [
    '.gitignore',
    'a.nix',
    'deleted.nix',
    'link.nix',
    'readme.md',
    'sub/b.nix',
  ]
  assert nix_files(shm_dir, inv) == ['a.nix', 'sub/b.nix']
  assert nix_files(shm_dir) == ['a.nix', 'sub/b.nix']


def test_run_cmd_oserror_and_git_ls_files_error(
  capsys: pytest.CaptureFixture[str], shm_dir: Path
) -> None:
  rc = run_cmd(['nonexistent-zero-binary-xyz'], cwd=shm_dir)
  assert rc == 127
  captured = capsys.readouterr()
  assert captured.err.startswith('Error: ')

  non_git = shm_dir / 'plain'
  non_git.mkdir()
  with pytest.raises(click.ClickException, match='git ls-files failed'):
    git_ls_files(non_git)


def test_cargo_package_args_and_aliased_group() -> None:
  assert cargo_package_args(None) == []
  assert cargo_package_args('') == []
  assert cargo_package_args('boot_shell') == ['-p', 'boot_shell']

  @click.group(cls=AliasedGroup, aliases={'c': 'check'})
  def cli() -> None:
    pass

  @cli.command('check')
  def check_cmd() -> None:
    click.echo('ran-check')

  runner = CliRunner()
  assert runner.invoke(cli, ['check']).output == 'ran-check\n'
  assert runner.invoke(cli, ['c']).output == 'ran-check\n'
  res = runner.invoke(cli, ['ch'])
  assert res.exit_code == 2
