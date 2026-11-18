from __future__ import annotations

import select
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

import click
import pywatchman

from zero.lib import Runner, nix_files, run_cmd, run_timed_cmd, timed_step

IGNORED_DIRS = frozenset(
  {
    '.git',
    '.jj',
    '.tmp',
    '.nix-cache',
    '.pytest_cache',
    '.ruff_cache',
    '__pycache__',
    'target',
    'target-analyzer',
    'result',
  }
)

_SUBSCRIPTION_NAME = 'pentagram-watch'
_BOOT_SHELL_BUILD_CMD = ('cargo', 'build', '-p', 'boot_shell')

WatchEvent = tuple[str, ...] | None


class WatchmanError(Exception):
  pass


@dataclass(frozen=True, slots=True)
class WatchPlan:
  steps: tuple[tuple[str, tuple[str, ...]], ...]
  rust_changed: bool
  penta_changed: bool


class WatchSession(Protocol):
  def next_batch(self, timeout: float = 0.25) -> WatchEvent: ...

  def close(self) -> None: ...


class ShellWatcher(Protocol):
  def poll(self) -> int | None: ...

  def stop(self) -> None: ...


def _normalize_rel_path(raw: str) -> PurePosixPath | None:
  stripped = raw.strip()
  if not stripped:
    return None
  posix = PurePosixPath(stripped.replace('\\', '/'))
  norm = posix.as_posix()
  if norm in ('', '.'):
    return None
  if any(part in IGNORED_DIRS for part in posix.parts):
    return None
  return PurePosixPath(norm)


def _normalize_paths(
  changed_paths: Sequence[str],
) -> tuple[PurePosixPath, ...]:
  paths: list[PurePosixPath] = []
  for raw in changed_paths:
    path = _normalize_rel_path(raw)
    if path is not None:
      paths.append(path)
  return tuple(paths)


def plan_watch_iteration(
  changed_paths: Sequence[str],
  *,
  nix_paths: Sequence[str],
  python_exe: str = sys.executable,
) -> WatchPlan:
  has_py = False
  has_zero_py = False
  has_proj_py = False
  has_md = False
  has_dprint = False
  has_nix = False
  rust_changed = False
  penta_changed = False

  for path in _normalize_paths(changed_paths):
    rel = path.as_posix()
    suffix = path.suffix
    if suffix == '.py':
      has_py = True
      if rel.startswith('zero/'):
        has_zero_py = True
      elif rel.startswith('proj/'):
        has_proj_py = True
    elif suffix == '.md':
      has_md = True
      has_dprint = True
    elif suffix in ('.json', '.toml'):
      has_dprint = True
    elif suffix == '.nix':
      has_nix = True
    elif suffix == '.rs':
      rust_changed = True
    elif suffix == '.penta':
      penta_changed = True

    if path.name in ('Cargo.toml', 'Cargo.lock'):
      rust_changed = True

  steps: list[tuple[str, tuple[str, ...]]] = []
  if has_py:
    steps.extend(
      [
        ('py-fmt', ('ruff', 'format', '--check')),
        ('py-lint', ('ruff', 'check')),
        ('type', (python_exe, '-m', 'zero', 'check', 'type')),
      ]
    )
    if has_zero_py:
      steps.append(('ztest', (python_exe, '-m', 'zero', 'check', 'ztest')))
    if has_proj_py:
      steps.append(('ptest', (python_exe, '-m', 'zero', 'check', 'ptest')))
  if has_dprint:
    steps.append(('dprint', ('dprint', 'check')))
  if has_md:
    steps.append(('doc-lint', (python_exe, '-m', 'zero', 'check', 'doc')))
  if has_nix and nix_paths:
    steps.append(('nix-fmt', ('nixfmt', '--check', '--', *nix_paths)))
  if rust_changed:
    steps.extend(
      [
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
      ]
    )
  return WatchPlan(
    steps=tuple(steps),
    rust_changed=rust_changed,
    penta_changed=penta_changed,
  )


class PywatchmanSession:
  def __init__(self, repo: Path) -> None:
    self._client: pywatchman.client | None = None
    try:
      self._client = pywatchman.client(timeout=5.0)
      watch_res = self._client.query('watch-project', str(repo.resolve()))
      watch_root = watch_res.get('watch')
      if not isinstance(watch_root, str) or not watch_root:
        raise WatchmanError('watch-project returned invalid watch root.')
      clock_res = self._client.query('clock', watch_root)
      clock = clock_res.get('clock')
      if not isinstance(clock, str) or not clock:
        raise WatchmanError('clock returned invalid clock value.')
      sub_opts: dict[str, object] = {
        'fields': ['name'],
        'since': clock,
        'expression': [
          'not',
          [
            'anyof',
            *(['dirname', d] for d in sorted(IGNORED_DIRS)),
            *(['name', d] for d in sorted(IGNORED_DIRS)),
          ],
        ],
      }
      relative_path = watch_res.get('relative_path')
      if isinstance(relative_path, str) and relative_path:
        sub_opts['relative_root'] = relative_path
      self._client.query(
        'subscribe', watch_root, _SUBSCRIPTION_NAME, sub_opts
      )
    except WatchmanError:
      self.close()
      raise
    except (pywatchman.WatchmanError, OSError) as err:
      self.close()
      raise WatchmanError(str(err)) from err

  def _socket(self) -> socket.socket:
    if self._client is None:
      raise WatchmanError('Watchman session is closed.')
    sock = getattr(self._client.tport, 'sock', None)
    if not isinstance(sock, socket.socket):
      raise WatchmanError('Watchman transport socket unavailable.')
    return sock

  def _drain_readable(self, sock: socket.socket) -> None:
    assert self._client is not None
    while select.select([sock], [], [], 0.0)[0]:
      self._client.receive()

  def next_batch(self, timeout: float = 0.25) -> WatchEvent:
    if self._client is None:
      raise WatchmanError('Watchman session is closed.')
    sock = self._socket()
    try:
      payloads = self._client.getSubscription(_SUBSCRIPTION_NAME)
      if payloads:
        self._drain_readable(sock)
        extra = self._client.getSubscription(_SUBSCRIPTION_NAME)
        if extra:
          payloads = [*payloads, *extra]
      else:
        deadline = time.monotonic() + timeout
        while not payloads:
          remaining = deadline - time.monotonic()
          if remaining <= 0:
            return None
          readable, _, _ = select.select([sock], [], [], remaining)
          if not readable:
            return None
          self._client.receive()
          self._drain_readable(sock)
          payloads = self._client.getSubscription(_SUBSCRIPTION_NAME)
    except (pywatchman.WatchmanError, OSError, ValueError) as err:
      raise WatchmanError(str(err)) from err

    seen: dict[str, None] = {}
    for payload in payloads:
      if not isinstance(payload, dict):
        raise WatchmanError(
          'Watchman subscription payload was not a dict.'
        )
      if payload.get('canceled'):
        raise WatchmanError('Watchman subscription canceled.')
      files = payload.get('files')
      if isinstance(files, list):
        for item in files:
          if isinstance(item, str):
            seen[item] = None
          elif isinstance(item, dict) and isinstance(
            item.get('name'), str
          ):
            seen[item['name']] = None
    return tuple(seen)

  def close(self) -> None:
    if self._client is not None:
      self._client.close()
      self._client = None


class SubprocessShellWatcher:
  def __init__(self, repo: Path) -> None:
    self._proc = subprocess.Popen(
      [
        str(repo / 'target' / 'debug' / 'boot_shell'),
        'test',
        '--watch',
        'core',
      ],
      cwd=repo,
    )

  def poll(self) -> int | None:
    return self._proc.poll()

  def stop(self) -> None:
    if self._proc.poll() is not None:
      return
    self._proc.terminate()
    try:
      self._proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
      self._proc.kill()
      self._proc.wait()


def _reap_shell(shell: ShellWatcher | None) -> ShellWatcher | None:
  if shell is not None and (rc := shell.poll()) is not None:
    print(f'[test] boot_shell watcher exited (code {rc})', flush=True)
    return None
  return shell


def _spawn_shell(
  repo: Path, shell_spawner: Callable[[Path], ShellWatcher]
) -> ShellWatcher | None:
  try:
    return shell_spawner(repo)
  except OSError as err:
    print(f'Watch error: {err}', file=sys.stderr, flush=True)
    return None


def _run_iteration(
  repo: Path,
  plan: WatchPlan,
  shell: ShellWatcher | None,
  shell_built: bool,
  *,
  nix_error: bool,
  runner: Runner,
  shell_spawner: Callable[[Path], ShellWatcher],
) -> tuple[ShellWatcher | None, bool]:
  new_shell = shell
  new_built = shell_built
  restart_only = (
    plan.penta_changed
    and shell is None
    and shell_built
    and not plan.rust_changed
  )

  def _step() -> bool:
    nonlocal new_shell, new_built
    ok = True
    if nix_error:
      timed_step('nix-fmt', lambda: False)
      ok = False
    for label, cmd in plan.steps:
      if not run_timed_cmd(label, cmd, cwd=repo, runner=runner):
        ok = False
    if plan.rust_changed:
      new_built = run_timed_cmd(
        'boot-shell-build', _BOOT_SHELL_BUILD_CMD, cwd=repo, runner=runner
      )
      if not new_built:
        return False
      if new_shell is not None:
        new_shell.stop()
      new_shell = _spawn_shell(repo, shell_spawner)
      if new_shell is None:
        ok = False
    elif restart_only:
      new_shell = _spawn_shell(repo, shell_spawner)
      if new_shell is None:
        ok = False
    return ok

  timed_step('watch-iteration', _step)
  return new_shell, new_built


def run_watch(
  repo: Path,
  *,
  session_factory: Callable[[Path], WatchSession] = PywatchmanSession,
  runner: Runner = run_cmd,
  shell_spawner: Callable[[Path], ShellWatcher] = SubprocessShellWatcher,
) -> int:
  try:
    session = session_factory(repo)
  except WatchmanError as err:
    print(f'Watchman error: {err}', file=sys.stderr, flush=True)
    return 1

  shell: ShellWatcher | None = None
  try:
    shell_built = run_timed_cmd(
      'boot-shell-build', _BOOT_SHELL_BUILD_CMD, cwd=repo, runner=runner
    )
    if shell_built:
      shell = _spawn_shell(repo, shell_spawner)

    while True:
      shell = _reap_shell(shell)
      batch = session.next_batch()
      if batch is None:
        continue
      shell = _reap_shell(shell)
      normalized = _normalize_paths(batch)
      if not normalized:
        continue
      nix_paths: Sequence[str] = ()
      nix_error = False
      if any(path.suffix == '.nix' for path in normalized):
        try:
          nix_paths = nix_files(repo)
        except click.ClickException as err:
          print(
            f'Error: {err.format_message()}', file=sys.stderr, flush=True
          )
          nix_error = True
      plan = plan_watch_iteration(
        tuple(path.as_posix() for path in normalized),
        nix_paths=nix_paths,
      )
      restart_only = (
        plan.penta_changed
        and shell is None
        and shell_built
        and not plan.rust_changed
      )
      if (
        not plan.steps
        and not plan.rust_changed
        and not restart_only
        and not nix_error
      ):
        continue
      shell, shell_built = _run_iteration(
        repo,
        plan,
        shell,
        shell_built,
        nix_error=nix_error,
        runner=runner,
        shell_spawner=shell_spawner,
      )
  except KeyboardInterrupt:
    return 0
  except WatchmanError as err:
    print(f'Watchman error: {err}', file=sys.stderr, flush=True)
    return 1
  finally:
    try:
      if shell is not None:
        shell.stop()
    finally:
      session.close()
