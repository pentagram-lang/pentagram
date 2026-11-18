from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from zero.watch import (
  WatchEvent,
  WatchmanError,
  WatchPlan,
  plan_watch_iteration,
  run_watch,
)


class _FakeSession:
  def __init__(self, events: Sequence[WatchEvent | BaseException]) -> None:
    self._events: Iterator[WatchEvent | BaseException] = iter(events)
    self.closed = False

  def next_batch(self, timeout: float = 0.25) -> WatchEvent:
    del timeout
    try:
      event = next(self._events)
    except StopIteration as err:
      raise KeyboardInterrupt from err
    if isinstance(event, BaseException):
      raise event
    return event

  def close(self) -> None:
    self.closed = True


class _FakeShell:
  def __init__(self, polls: Sequence[int | None] = ()) -> None:
    self._polls: Iterator[int | None] = iter(polls)
    self.stopped = False

  def poll(self) -> int | None:
    return next(self._polls, None)

  def stop(self) -> None:
    self.stopped = True


@pytest.fixture
def shm_git_repo() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='zero-watch-test-', dir='/dev/shm'))
  subprocess.run(['git', 'init', '-q', str(d)], check=True)
  (d / 'flake.nix').write_text('{}\n', encoding='utf-8')
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def test_plan_watch_iteration_ignored_and_empty() -> None:
  plan = plan_watch_iteration(
    [
      '',
      '.',
      './',
      '.git/HEAD',
      '.jj/working_copy/tree_state',
      '.tmp/notes.md',
      '.nix-cache/a.nix',
      '.pytest_cache/x.py',
      '.ruff_cache/x.py',
      '__pycache__/x.py',
      'target/debug/boot_shell.rs',
      'target-analyzer/x.rs',
      'result/bin/x.py',
      'README.txt',
    ],
    nix_paths=['flake.nix'],
    python_exe='py3',
  )
  assert plan == WatchPlan(
    steps=(), rust_changed=False, penta_changed=False
  )


def test_plan_watch_iteration_python_scopes() -> None:
  plain = plan_watch_iteration(
    ['scripts/helper.py'], nix_paths=[], python_exe='py3'
  )
  assert plain == WatchPlan(
    steps=(
      ('py-fmt', ('ruff', 'format', '--check')),
      ('py-lint', ('ruff', 'check')),
      ('type', ('py3', '-m', 'zero', 'check', 'type')),
    ),
    rust_changed=False,
    penta_changed=False,
  )

  zero_only = plan_watch_iteration(
    ['./zero/watch.py'], nix_paths=[], python_exe='py3'
  )
  assert zero_only == WatchPlan(
    steps=(
      ('py-fmt', ('ruff', 'format', '--check')),
      ('py-lint', ('ruff', 'check')),
      ('type', ('py3', '-m', 'zero', 'check', 'type')),
      ('ztest', ('py3', '-m', 'zero', 'check', 'ztest')),
    ),
    rust_changed=False,
    penta_changed=False,
  )

  both = plan_watch_iteration(
    ['proj/ops.py', 'zero/cli.py'], nix_paths=[], python_exe='py3'
  )
  assert both == WatchPlan(
    steps=(
      ('py-fmt', ('ruff', 'format', '--check')),
      ('py-lint', ('ruff', 'check')),
      ('type', ('py3', '-m', 'zero', 'check', 'type')),
      ('ztest', ('py3', '-m', 'zero', 'check', 'ztest')),
      ('ptest', ('py3', '-m', 'zero', 'check', 'ptest')),
    ),
    rust_changed=False,
    penta_changed=False,
  )


def test_plan_watch_iteration_docs_nix_rust_and_penta() -> None:
  docs = plan_watch_iteration(
    ['a.json', 'pyproject.toml', 'README.md'],
    nix_paths=[],
    python_exe='py3',
  )
  assert docs == WatchPlan(
    steps=(
      ('dprint', ('dprint', 'check')),
      ('doc-lint', ('py3', '-m', 'zero', 'check', 'doc')),
    ),
    rust_changed=False,
    penta_changed=False,
  )

  nix_present = plan_watch_iteration(
    ['flake.nix'],
    nix_paths=['flake.nix', 'nix/zero.nix'],
    python_exe='py3',
  )
  assert nix_present == WatchPlan(
    steps=(
      (
        'nix-fmt',
        ('nixfmt', '--check', '--', 'flake.nix', 'nix/zero.nix'),
      ),
    ),
    rust_changed=False,
    penta_changed=False,
  )

  nix_empty = plan_watch_iteration(
    ['deleted.nix'], nix_paths=[], python_exe='py3'
  )
  assert nix_empty == WatchPlan(
    steps=(), rust_changed=False, penta_changed=False
  )

  cargo_toml = plan_watch_iteration(
    ['boot/Cargo.toml'], nix_paths=[], python_exe='py3'
  )
  assert cargo_toml == WatchPlan(
    steps=(
      ('dprint', ('dprint', 'check')),
      ('rust-fmt', ('cargo', 'fmt', '--', '--check')),
      (
        'clippy',
        (
          'cargo',
          'clippy',
          '--all-targets',
          '--all-features',
          '--',
          '-D',
          'warnings',
        ),
      ),
      ('btest', ('cargo', 'test')),
    ),
    rust_changed=True,
    penta_changed=False,
  )

  cargo_lock = plan_watch_iteration(
    ['Cargo.lock', 'boot/src/main.rs', 'core/prelude.penta'],
    nix_paths=[],
    python_exe='py3',
  )
  assert cargo_lock == WatchPlan(
    steps=(
      ('rust-fmt', ('cargo', 'fmt', '--', '--check')),
      (
        'clippy',
        (
          'cargo',
          'clippy',
          '--all-targets',
          '--all-features',
          '--',
          '-D',
          'warnings',
        ),
      ),
      ('btest', ('cargo', 'test')),
    ),
    rust_changed=True,
    penta_changed=True,
  )


def test_run_watch_initial_build_failure_and_rust_recovery(
  tmp_path: Path,
) -> None:
  session = _FakeSession(
    [
      None,
      ('.git/index',),
      ('core/unbuilt.penta',),
      ('boot/src/lib.rs',),
    ]
  )
  shells: list[_FakeShell] = []
  cmds: list[list[str]] = []
  build_calls = 0

  def fake_runner(cmd: Sequence[str], cwd: Path | None) -> int:
    nonlocal build_calls
    assert cwd == tmp_path
    cmds.append(list(cmd))
    if list(cmd) == ['cargo', 'build', '-p', 'boot_shell']:
      build_calls += 1
      return 1 if build_calls == 1 else 0
    return 1 if list(cmd) == ['cargo', 'fmt', '--', '--check'] else 0

  def spawn(_repo: Path) -> _FakeShell:
    s = _FakeShell()
    shells.append(s)
    return s

  rc = run_watch(
    tmp_path,
    session_factory=lambda _repo: session,
    runner=fake_runner,
    shell_spawner=spawn,
  )
  assert rc == 0
  assert session.closed is True
  assert len(shells) == 1
  assert shells[0].stopped is True
  assert cmds == [
    ['cargo', 'build', '-p', 'boot_shell'],
    ['cargo', 'fmt', '--', '--check'],
    [
      'cargo',
      'clippy',
      '--all-targets',
      '--all-features',
      '--',
      '-D',
      'warnings',
    ],
    ['cargo', 'test'],
    ['cargo', 'build', '-p', 'boot_shell'],
  ]


def test_run_watch_penta_ignored_while_alive_and_restarts_without_build(
  tmp_path: Path,
  capsys: pytest.CaptureFixture[str],
) -> None:
  session = _FakeSession(
    [
      ('core/ok.penta',),
      ('core/recover.penta',),
    ]
  )
  shells = [
    _FakeShell([None, None, 2]),
    _FakeShell(),
  ]
  spawn_idx = 0
  cmds: list[list[str]] = []

  def spawn(_repo: Path) -> _FakeShell:
    nonlocal spawn_idx
    s = shells[spawn_idx]
    spawn_idx += 1
    return s

  def fake_runner(cmd: Sequence[str], cwd: Path | None) -> int:
    assert cwd == tmp_path
    cmds.append(list(cmd))
    return 0

  rc = run_watch(
    tmp_path,
    session_factory=lambda _repo: session,
    runner=fake_runner,
    shell_spawner=spawn,
  )
  assert rc == 0
  assert spawn_idx == 2
  assert shells[0].stopped is False
  assert shells[1].stopped is True
  assert session.closed is True
  assert cmds == [['cargo', 'build', '-p', 'boot_shell']]
  out = capsys.readouterr().out
  assert '[test] boot_shell watcher exited (code 2)' in out


def test_run_watch_nix_paths_and_error_containment(
  shm_git_repo: Path,
  tmp_path: Path,
  capsys: pytest.CaptureFixture[str],
) -> None:
  cmds: list[list[str]] = []

  def rec(cmd: Sequence[str], _cwd: Path | None) -> int:
    cmds.append(list(cmd))
    return 0

  session_ok = _FakeSession(
    [
      ('.tmp/ignored.nix',),
      ('flake.nix ',),
    ]
  )
  rc_ok = run_watch(
    shm_git_repo,
    session_factory=lambda _repo: session_ok,
    runner=rec,
    shell_spawner=lambda _repo: _FakeShell(),
  )
  assert rc_ok == 0
  assert cmds == [
    ['cargo', 'build', '-p', 'boot_shell'],
    ['nixfmt', '--check', '--', 'flake.nix'],
  ]

  capsys.readouterr()

  def fail_spawn(_repo: Path) -> _FakeShell:
    raise OSError('missing boot_shell')

  session_err = _FakeSession([('bad.nix',)])
  rc_err = run_watch(
    tmp_path,
    session_factory=lambda _repo: session_err,
    runner=lambda _cmd, _cwd: 0,
    shell_spawner=fail_spawn,
  )
  assert rc_err == 0
  captured = capsys.readouterr()
  assert 'Watch error: missing boot_shell' in captured.err
  assert 'Error: git ls-files failed:' in captured.err
  assert '[FAIL] nix-fmt' in captured.out
  assert '[FAIL] watch-iteration' in captured.out


def test_run_watch_watchman_errors(
  tmp_path: Path,
  capsys: pytest.CaptureFixture[str],
) -> None:
  def fail_connect(_repo: Path) -> _FakeSession:
    raise WatchmanError('daemon unavailable')

  rc_init = run_watch(tmp_path, session_factory=fail_connect)
  assert rc_init == 1
  assert capsys.readouterr().err == 'Watchman error: daemon unavailable\n'

  shell = _FakeShell()
  session = _FakeSession([WatchmanError('subscription canceled')])
  rc_loop = run_watch(
    tmp_path,
    session_factory=lambda _repo: session,
    runner=lambda _cmd, _cwd: 0,
    shell_spawner=lambda _repo: shell,
  )
  assert rc_loop == 1
  assert shell.stopped is True
  assert session.closed is True
  assert (
    capsys.readouterr().err == 'Watchman error: subscription canceled\n'
  )
