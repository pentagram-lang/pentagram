from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Never

import click
import pytest
from click.testing import CliRunner

from zero.cli import (
  cli,
  do_check_all,
  do_check_btest,
  do_check_fmt,
  do_check_lint,
  do_check_pytest,
  do_fix_all,
  do_fix_fmt,
  do_fix_lint,
  main,
  validate_nodeid,
)


@pytest.fixture
def shm_repo() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='zero-cli-test-', dir='/dev/shm'))
  subprocess.run(['git', 'init', '-q', str(d)], check=True)
  subprocess.run(
    ['git', '-C', str(d), 'config', 'user.name', 'Test'], check=True
  )
  subprocess.run(
    ['git', '-C', str(d), 'config', 'user.email', 'test@example.com'],
    check=True,
  )
  (d / 'zero').mkdir()
  (d / 'zero' / '__main__.py').write_text('', encoding='utf-8')
  (d / 'README.md').write_text('# Root\n', encoding='utf-8')
  (d / 'a.nix').write_text('{}\n', encoding='utf-8')
  subprocess.run(
    ['git', '-C', str(d), 'add', 'README.md', 'a.nix', 'zero/__main__.py'],
    check=True,
  )
  subprocess.run(
    ['git', '-C', str(d), 'commit', '-q', '-m', 'feat: init'], check=True
  )
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def test_help_and_skip_commit_errors(shm_repo: Path) -> None:
  runner = CliRunner()
  bare = runner.invoke(cli, [], obj=shm_repo)
  help_sub = runner.invoke(cli, ['help'], obj=shm_repo)
  help_flag = runner.invoke(cli, ['--help'], obj=shm_repo)
  assert bare.exit_code == 0
  assert help_sub.exit_code == 0
  assert help_flag.exit_code == 0
  assert bare.output == help_sub.output
  assert bare.output == help_flag.output

  extra = runner.invoke(cli, ['help', 'extra'], obj=shm_repo)
  assert extra.exit_code == 2

  for args in (['check', '--skip-commit', 'fmt'], ['c', '-s', 'f']):
    res = runner.invoke(cli, args, obj=shm_repo)
    assert res.exit_code != 0
    assert (
      '--skip-commit cannot be combined with a subcommand.' in res.output
    )


def test_fix_aborts_on_first_failure(shm_repo: Path) -> None:
  calls: list[list[str]] = []

  def fail_ruff(cmd: Sequence[str], cwd: Path | None) -> int:
    assert cwd == shm_repo
    calls.append(list(cmd))
    return 1 if cmd[:2] == ['ruff', 'format'] else 0

  assert do_fix_fmt(shm_repo, runner=fail_ruff) is False
  assert calls == [['cargo', 'fmt'], ['ruff', 'format']]

  calls.clear()

  def fail_py_lint(cmd: Sequence[str], cwd: Path | None) -> int:
    assert cwd == shm_repo
    calls.append(list(cmd))
    return 1 if cmd[:2] == ['ruff', 'check'] else 0

  assert do_fix_lint(shm_repo, 'boot_shell', runner=fail_py_lint) is False
  assert calls == [['ruff', 'check', '--fix']]

  calls.clear()
  assert do_fix_all(shm_repo, runner=fail_ruff) is False
  assert calls == [['cargo', 'fmt'], ['ruff', 'format']]

  calls.clear()
  assert do_fix_all(
    shm_repo, runner=lambda cmd, _cwd: calls.append(list(cmd)) or 0
  )
  assert calls == [
    ['cargo', 'fmt'],
    ['ruff', 'format'],
    ['dprint', 'fmt'],
    ['nixfmt', '--', 'a.nix'],
    ['ruff', 'check', '--fix'],
    [
      'cargo',
      'fixit',
      '--clippy',
      '--broken-code',
      '--allow-dirty',
      '--allow-staged',
      '--all-targets',
      '--all-features',
      '--workspace',
    ],
    [
      'cargo',
      'clippy',
      '--all-targets',
      '--all-features',
      '--',
      '-D',
      'warnings',
    ],
  ]


def test_check_non_short_circuit_and_skip_commit(shm_repo: Path) -> None:
  calls: list[list[str]] = []

  def fail_first(cmd: Sequence[str], _cwd: Path | None) -> int:
    calls.append(list(cmd))
    return 1 if cmd[0] in ('cargo', 'ruff') else 0

  assert do_check_fmt(shm_repo, runner=fail_first) is False
  assert calls == [
    ['cargo', 'fmt', '--', '--check'],
    ['ruff', 'format', '--check'],
    ['dprint', 'check'],
    ['nixfmt', '--check', '--', 'a.nix'],
  ]

  calls.clear()
  assert do_check_lint(shm_repo, 'boot_shell', runner=fail_first) is False
  assert calls == [
    ['ruff', 'check'],
    [
      'cargo',
      'clippy',
      '-p',
      'boot_shell',
      '--all-targets',
      '--all-features',
      '--',
      '-D',
      'warnings',
    ],
  ]

  calls.clear()
  assert (
    do_check_all(shm_repo, skip_commit=False, runner=fail_first) is False
  )
  expected_all = [
    ['cargo', 'fmt', '--', '--check'],
    ['ruff', 'format', '--check'],
    ['dprint', 'check'],
    ['nixfmt', '--check', '--', 'a.nix'],
    ['ruff', 'check'],
    [
      'cargo',
      'clippy',
      '--all-targets',
      '--all-features',
      '--',
      '-D',
      'warnings',
    ],
    ['ty', 'check', '--python', sys.prefix],
    ['pytest', '-n', 'auto', 'zero'],
    ['pytest', '-n', 'auto', 'proj'],
    ['cargo', 'test'],
    ['cargo', 'run', '-p', 'boot_shell', '--', 'test', 'core'],
    ['cog', 'check'],
  ]
  assert calls == expected_all

  subprocess.run(
    [
      'git',
      '-C',
      str(shm_repo),
      'commit',
      '--allow-empty',
      '-q',
      '-m',
      'wip: bad',
    ],
    check=True,
  )
  calls.clear()
  ok = do_check_all(
    shm_repo,
    skip_commit=True,
    runner=lambda cmd, _cwd: calls.append(list(cmd)) or 0,
  )
  assert ok is True
  assert calls == expected_all[:-1]
  assert (
    do_check_all(
      shm_repo,
      skip_commit=False,
      runner=lambda cmd, _cwd: calls.append(list(cmd)) or 0,
    )
    is False
  )


def test_pytest_nodeid_validation_and_btest_argv(shm_repo: Path) -> None:
  assert validate_nodeid('zero', 'lib_test.py::test_x') == (
    'zero/lib_test.py::test_x'
  )
  bad_nodeids = (
    'lib_test.py',
    '::test_x',
    'lib_test.py::',
    '/abs_test.py::test_x',
    '../up_test.py::test_x',
    'lib.py::test_x',
  )
  for raw in bad_nodeids:
    with pytest.raises(click.ClickException):
      validate_nodeid('zero', raw)

  calls: list[list[str]] = []

  def rec(cmd: Sequence[str], _cwd: Path | None) -> int:
    calls.append(list(cmd))
    return 0

  assert do_check_pytest('ztest', shm_repo, runner=rec) is True
  assert (
    do_check_pytest('ztest', shm_repo, parallel=False, runner=rec) is True
  )
  assert (
    do_check_pytest(
      'ptest', shm_repo, keyword='db', marker='fast', runner=rec
    )
    is True
  )
  assert (
    do_check_pytest(
      'ztest',
      shm_repo,
      nodeids=('lib_test.py::test_a',),
      parallel=True,
      runner=rec,
    )
    is True
  )
  assert do_check_btest(shm_repo, runner=rec) is True
  assert (
    do_check_btest(
      shm_repo,
      'boot_shell',
      'test_x',
      nocapture=True,
      exact=True,
      runner=rec,
    )
    is True
  )
  assert calls == [
    ['pytest', '-n', 'auto', 'zero'],
    ['pytest', 'zero'],
    ['pytest', '-k', 'db', '-m', 'fast', 'proj'],
    ['pytest', '-n', 'auto', 'zero/lib_test.py::test_a'],
    ['cargo', 'test'],
    [
      'cargo',
      'test',
      '-p',
      'boot_shell',
      'test_x',
      '--',
      '--nocapture',
      '--exact',
    ],
  ]


def test_run_passthrough_proj_mount_and_main_chdir(
  shm_repo: Path,
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  seen_run: list[tuple[str, ...]] = []

  def fake_run_boot(args: Sequence[str]) -> Never:
    seen_run.append(tuple(args))
    raise SystemExit(0)

  monkeypatch.setattr('zero.cli.run_boot', fake_run_boot)
  runner = CliRunner()
  res = runner.invoke(
    cli, ['r', '--help', '--watch', 'core'], obj=shm_repo
  )
  assert res.exit_code == 0
  assert seen_run == [('--help', '--watch', 'core')]

  proj_res = runner.invoke(cli, ['p', 'list'], obj=shm_repo)
  assert proj_res.exit_code == 0
  assert proj_res.output == (
    'Name  Status  Objective  Summary  Next action\n'
    '----  ------  ---------  -------  -----------\n'
  )

  nested = shm_repo / 'nested'
  nested.mkdir()
  prev = Path.cwd()
  os.chdir(nested)
  try:
    with pytest.raises(SystemExit) as ok_exit:
      main(['help'])
    assert ok_exit.value.code == 0
    assert Path.cwd() == nested.resolve()

    with pytest.raises(SystemExit) as err_exit:
      main(['help', 'extra'])
    assert err_exit.value.code == 2
    assert Path.cwd() == nested.resolve()
  finally:
    os.chdir(prev)

  outside = Path(tempfile.mkdtemp(prefix='zero-no-repo-', dir='/dev/shm'))
  os.chdir(outside)
  try:
    capsys.readouterr()
    with pytest.raises(SystemExit) as missing_exit:
      main(['help'])
    assert missing_exit.value.code == 1
    assert capsys.readouterr().err == (
      'Error: zero/__main__.py not found in parent directories.\n'
    )
  finally:
    os.chdir(prev)
    shutil.rmtree(outside, ignore_errors=True)


def test_check_all_handles_unborn_head_without_aborting() -> None:
  unborn = Path(tempfile.mkdtemp(prefix='zero-unborn-', dir='/dev/shm'))
  subprocess.run(['git', 'init', '-q', str(unborn)], check=True)
  (unborn / 'README.md').write_text('# Root\n', encoding='utf-8')
  calls: list[list[str]] = []
  try:
    ok = do_check_all(
      unborn,
      skip_commit=False,
      runner=lambda cmd, _cwd: calls.append(list(cmd)) or 0,
    )
    assert ok is False
    assert calls[-1] == ['cog', 'check']
  finally:
    shutil.rmtree(unborn, ignore_errors=True)
