import concurrent.futures
import json
import os
import select
import socket
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import IO, Final, Protocol

import click
import pywatchman

from zero import lib

__all__ = ['run_watch']

_SUBSCRIPTION_NAME: Final[str] = 'pentagram-watch'
_PENTA_RECOVERY_SUBSCRIPTION: Final[str] = 'pentagram-penta-recovery'

_IGNORED_WATCH_DIRS: Final[tuple[str, ...]] = (
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
)
_IGNORED_PARTS: Final[frozenset[str]] = frozenset(_IGNORED_WATCH_DIRS)
_PARENT_SUFFIXES: Final[frozenset[str]] = frozenset(
  {'.rs', '.py', '.md', '.json', '.nix', '.toml'}
)


class _WatchmanClient(Protocol):
  """Minimal Watchman client protocol needed for watch mode."""

  def capabilityCheck(
    self, optional: list[str] | None = None
  ) -> object: ...

  def query(self, *args: object) -> object: ...

  def receive(self) -> object: ...

  def getSubscription(
    self,
    name: str,
    remove: bool = True,
    root: str | None = None,
  ) -> list[dict[str, object]] | None: ...

  def getLog(self, remove: bool = True) -> list[object]: ...

  def setTimeout(self, value: float) -> object: ...

  def close(self) -> object: ...


class _ChildProcess(Protocol):
  """Minimal subprocess protocol tracked by _WatchRuntime."""

  @property
  def stdout(self) -> IO[str] | None: ...

  @property
  def stderr(self) -> IO[str] | None: ...

  def poll(self) -> int | None: ...

  def wait(self, timeout: float | None = None) -> int: ...

  def terminate(self) -> object: ...

  def kill(self) -> object: ...


@dataclass(frozen=True, slots=True)
class _TestBinary:
  executable: str
  target_name: str


@dataclass(frozen=True, slots=True)
class _CheckSpec:
  command: tuple[str, ...]
  label: str
  colour: str


@dataclass(frozen=True, slots=True)
class _WatchPlan:
  checks: tuple[_CheckSpec, ...]
  run_nix_fmt: bool = False
  run_rust_pipeline: bool = False


@dataclass(frozen=True, slots=True)
class _CargoCompilerMessage:
  rendered: str


@dataclass(frozen=True, slots=True)
class _CargoTestArtifact:
  binary: _TestBinary


@dataclass(frozen=True, slots=True)
class _CargoShellRebuilt:
  pass


type _CargoMessageEffect = (
  _CargoCompilerMessage | _CargoTestArtifact | _CargoShellRebuilt | None
)


@dataclass(frozen=True, slots=True)
class _CargoBuildSummary:
  test_binaries: tuple[_TestBinary, ...]
  rebuilt_shell: bool


@dataclass(frozen=True, slots=True)
class _SpawnOutcome:
  proc: _ChildProcess | None
  cancelled: bool = False


class _RecoveryState(Enum):
  DISARMED = 'disarmed'
  PENDING_ARM = 'pending_arm'
  SUBSCRIBING = 'subscribing'
  SUBSCRIBED = 'subscribed'


@dataclass(slots=True)
class _WatchRuntime:
  root: Path
  client: _WatchmanClient
  watch_root: str
  relative_root: str | None
  wake_pair: tuple[socket.socket, socket.socket]
  main_thread: threading.Thread = field(
    default_factory=threading.current_thread
  )
  lock: threading.Lock = field(default_factory=threading.Lock)
  output_lock: threading.Lock = field(default_factory=threading.Lock)
  recovery_state: _RecoveryState = _RecoveryState.DISARMED
  pending_exit_code: int | None = None
  disarm_recovery_event: threading.Event | None = None
  child_process: _ChildProcess | None = None
  stdout_thread: threading.Thread | None = None
  stderr_thread: threading.Thread | None = None
  reaper_thread: threading.Thread | None = None
  active_processes: set[_ChildProcess] = field(default_factory=set)
  wake_closed: bool = False
  shell_generation: int = 0
  should_stop: bool = False
  first_rust_run: bool = True


def _emit_startup_error(text: str) -> None:
  click.echo(lib.sanitize_text(text), err=True)


def _emit_line(
  state: _WatchRuntime,
  text: str,
  *,
  colour: str | None = None,
  bold: bool = False,
  err: bool = False,
  nl: bool = True,
) -> None:
  sanitized = lib.sanitize_text(text)
  styled = (
    click.style(sanitized, fg=colour, bold=bold)
    if colour is not None
    else sanitized
  )
  with state.output_lock:
    click.echo(styled, err=err, nl=nl)


def _emit_status(
  state: _WatchRuntime, label: str, duration: float, success: bool = True
) -> None:
  with state.output_lock:
    lib.status(label, duration, success)


def _close_process_streams(proc: _ChildProcess) -> None:
  for stream in (proc.stdout, proc.stderr):
    if stream is not None:
      with suppress(OSError, ValueError):
        stream.close()


def _terminate_process(proc: _ChildProcess) -> None:
  with suppress(OSError):
    proc.terminate()
  try:
    proc.wait(timeout=2)
  except subprocess.TimeoutExpired:
    with suppress(OSError):
      proc.kill()
    with suppress(OSError):
      proc.wait()
  except OSError:
    pass


def _create_wakeup_pair() -> tuple[socket.socket, socket.socket]:
  wake_r, wake_w = socket.socketpair()
  try:
    wake_r.setblocking(False)
    wake_w.setblocking(False)
  except OSError:
    with suppress(OSError):
      wake_r.close()
    with suppress(OSError):
      wake_w.close()
    raise
  return wake_r, wake_w


def _nudge_wakeup_locked(state: _WatchRuntime) -> None:
  if not state.wake_closed:
    with suppress(OSError, ValueError):
      state.wake_pair[1].send(b'\x00')


def _arm_recovery_locked(state: _WatchRuntime) -> None:
  if (
    not state.should_stop
    and state.recovery_state is _RecoveryState.DISARMED
  ):
    state.recovery_state = _RecoveryState.PENDING_ARM
    _nudge_wakeup_locked(state)


def _drain_wakeup(wake_r: socket.socket) -> None:
  while True:
    try:
      if not wake_r.recv(4096):
        break
    except BlockingIOError:
      break
    except OSError:
      break


def _close_wakeup_pair(state: _WatchRuntime) -> None:
  with state.lock:
    if state.wake_closed:
      return
    state.wake_closed = True
  for sock in state.wake_pair:
    with suppress(OSError):
      sock.close()


def _join_if_started(thread: threading.Thread | None) -> None:
  if thread is not None and thread.ident is not None:
    thread.join()


def _nudge_wakeup(state: _WatchRuntime) -> None:
  with state.lock:
    _nudge_wakeup_locked(state)


def _abort_active_processes(state: _WatchRuntime) -> None:
  with state.lock:
    state.should_stop = True
    if state.disarm_recovery_event is not None:
      state.disarm_recovery_event.set()
    active = list(state.active_processes)
    _nudge_wakeup_locked(state)
  for proc in active:
    _terminate_process(proc)


def _forward_prefixed_stream(
  state: _WatchRuntime,
  stream: IO[str] | None,
  prefix: str,
  colour: str,
) -> None:
  if stream is None:
    return
  try:
    for line in iter(stream.readline, ''):
      line_str = line.rstrip()
      if line_str:
        _emit_line(state, f'[{prefix}] {line_str}', colour=colour)
  except ValueError:
    pass


def _ensure_reaped_if_exited(state: _WatchRuntime) -> bool:
  with state.lock:
    proc = state.child_process
    reaper = state.reaper_thread
  if proc is None:
    return False
  if proc.poll() is None:
    return True
  if reaper is not None and threading.current_thread() is not reaper:
    _join_if_started(reaper)
  with state.lock:
    return state.child_process is not None


def _filter_watch_files(
  files: Iterable[str], predicate: Callable[[PurePosixPath], bool]
) -> tuple[str, ...]:
  matched: list[str] = []
  for file in dict.fromkeys(files):
    path = PurePosixPath(file)
    if any(part in _IGNORED_PARTS for part in path.parts):
      continue
    if predicate(path):
      matched.append(file)
  return tuple(matched)


def _filter_parent_files(files: Iterable[str]) -> tuple[str, ...]:
  return _filter_watch_files(
    files,
    lambda path: (
      path.suffix in _PARENT_SUFFIXES or path.name == 'Cargo.lock'
    ),
  )


def _build_subscription_spec(
  match_expression: list[object],
  *,
  since: str,
  relative_root: str | None = None,
) -> dict[str, object]:
  sub: dict[str, object] = {
    'expression': [
      'allof',
      [
        'not',
        [
          'anyof',
          *(['dirname', directory] for directory in _IGNORED_WATCH_DIRS),
          ['name', 'result'],
        ],
      ],
      match_expression,
    ],
    'fields': ['name'],
    'defer_vcs': False,
    'since': since,
  }
  if relative_root:
    sub['relative_root'] = relative_root
  return sub


def _build_watch_subscription(
  *,
  since: str,
  relative_root: str | None = None,
) -> dict[str, object]:
  return _build_subscription_spec(
    [
      'anyof',
      ['suffix', 'rs'],
      ['suffix', 'py'],
      ['suffix', 'md'],
      ['suffix', 'json'],
      ['suffix', 'nix'],
      ['suffix', 'toml'],
      ['name', 'Cargo.lock'],
    ],
    since=since,
    relative_root=relative_root,
  )


def _filter_penta_files(files: Iterable[str]) -> tuple[str, ...]:
  return _filter_watch_files(files, lambda path: path.suffix == '.penta')


def _build_penta_recovery_subscription(
  *,
  since: str,
  relative_root: str | None = None,
) -> dict[str, object]:
  return _build_subscription_spec(
    ['suffix', 'penta'], since=since, relative_root=relative_root
  )


def _plan_watch_iteration(files: Iterable[str]) -> _WatchPlan:
  exe = sys.executable
  has_rust = False
  has_py = False
  has_md = False
  has_dprint = False
  has_nix = False
  py_roots: set[str] = set()

  for file in _filter_parent_files(files):
    path = PurePosixPath(file)
    suffix = path.suffix
    name = path.name
    if suffix == '.py':
      has_py = True
      if path.parts and path.parts[0] in {'zero', 'proj'}:
        py_roots.add(path.parts[0])
    if suffix == '.md':
      has_md = True
      has_dprint = True
    if suffix in {'.json', '.toml'}:
      has_dprint = True
    if suffix == '.nix':
      has_nix = True
    if suffix == '.rs' or name in {'Cargo.toml', 'Cargo.lock'}:
      has_rust = True

  checks: list[_CheckSpec] = []
  if has_rust:
    checks.append(
      _CheckSpec(('cargo', 'fmt', '--', '--check'), 'rust-fmt', 'cyan')
    )
  if has_py:
    checks.append(
      _CheckSpec(('ruff', 'format', '--check'), 'py-fmt', 'cyan')
    )
    checks.append(_CheckSpec(('ruff', 'check'), 'py-lint', 'yellow'))
    checks.append(
      _CheckSpec((exe, '-m', 'zero', 'check', 'type'), 'type', 'yellow')
    )
    for root, command in (('zero', 'ztest'), ('proj', 'ptest')):
      if root in py_roots:
        checks.append(
          _CheckSpec(
            (exe, '-m', 'zero', 'check', command), command, 'magenta'
          )
        )
  if has_dprint:
    checks.append(_CheckSpec(('dprint', 'check'), 'dprint', 'cyan'))
  if has_md:
    checks.append(
      _CheckSpec((exe, '-m', 'zero', 'check', 'doc'), 'doc-lint', 'yellow')
    )
  return _WatchPlan(
    checks=tuple(checks),
    run_nix_fmt=has_nix,
    run_rust_pipeline=has_rust,
  )


def _parse_cargo_json_line(
  line: str, *, is_first_run: bool
) -> _CargoMessageEffect:
  if not line:
    return None
  try:
    data = lib.json_object(json.loads(line))
  except json.JSONDecodeError:
    return None
  if data is None:
    return None

  reason = data.get('reason')
  if reason == 'compiler-message':
    message = lib.json_object(data.get('message'))
    rendered = message.get('rendered') if message is not None else None
    if isinstance(rendered, str) and rendered:
      return _CargoCompilerMessage(rendered)
    return None

  if reason == 'compiler-artifact':
    target = lib.json_object(data.get('target'))
    target_name = target.get('name') if target is not None else None
    profile = lib.json_object(data.get('profile'))
    test_profile = profile.get('test') if profile is not None else False
    fresh = data.get('fresh', False)
    executable = data.get('executable')
    if isinstance(executable, str) and isinstance(target_name, str):
      if test_profile is True:
        if is_first_run or fresh is False:
          return _CargoTestArtifact(_TestBinary(executable, target_name))
      elif target_name == 'boot_shell' and fresh is False:
        return _CargoShellRebuilt()

  return None


def _spawn_tracked_process(
  state: _WatchRuntime, cmd: Sequence[str], label: str, *, colour: str
) -> _SpawnOutcome:
  with state.lock:
    if state.should_stop:
      return _SpawnOutcome(None, cancelled=True)
    _emit_line(state, f'Running {label}...', colour=colour)
    try:
      proc: _ChildProcess = subprocess.Popen(
        cmd,
        cwd=state.root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        text=True,
        encoding='utf-8',
        errors='replace',
      )
    except OSError as error:
      _emit_line(state, f'[{label}] {error}', colour='red', bold=True)
      return _SpawnOutcome(None)
    state.active_processes.add(proc)
    return _SpawnOutcome(proc)


def _run_cmd(
  state: _WatchRuntime, cmd: Sequence[str], label: str, colour: str
) -> bool:
  t = lib.Timer()
  spawned = _spawn_tracked_process(state, cmd, label, colour=colour)
  if spawned.cancelled:
    return False
  proc = spawned.proc
  if proc is None:
    _emit_status(state, label, t.duration(), False)
    return False

  stdout_thread: threading.Thread | None = None
  stderr_thread: threading.Thread | None = None
  try:
    stdout_thread = threading.Thread(
      target=_forward_prefixed_stream,
      args=(state, proc.stdout, label, colour),
      daemon=True,
    )
    stderr_thread = threading.Thread(
      target=_forward_prefixed_stream,
      args=(state, proc.stderr, label, colour),
      daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    ret = proc.wait()
  finally:
    if proc.poll() is None:
      _terminate_process(proc)
    _join_if_started(stdout_thread)
    _join_if_started(stderr_thread)
    _close_process_streams(proc)
    with state.lock:
      state.active_processes.discard(proc)

  with state.lock:
    if state.should_stop:
      return False
  success = ret == 0
  _emit_status(state, label, t.duration(), success)
  return success


def _run_nix_check(state: _WatchRuntime) -> bool:
  with state.lock:
    if state.should_stop:
      return False
  t = lib.Timer()
  try:
    nix_paths = lib.nix_files(state.root)
  except RuntimeError as error:
    _emit_line(state, f'[nix-fmt] {error}', colour='red', bold=True)
    _emit_status(state, 'nix-fmt', t.duration(), False)
    return False
  if not nix_paths:
    return True
  return _run_cmd(
    state, ['nixfmt', '--check', '--', *nix_paths], 'nix-fmt', 'cyan'
  )


def _run_cargo_build(
  state: _WatchRuntime,
  cmd: Sequence[str],
  label: str,
  *,
  is_first_run: bool,
) -> _CargoBuildSummary | None:
  t = lib.Timer()
  spawned = _spawn_tracked_process(state, cmd, label, colour='blue')
  if spawned.cancelled:
    return None
  proc = spawned.proc
  if proc is None:
    _emit_status(state, label, t.duration(), False)
    return None

  test_binaries: list[_TestBinary] = []
  rebuilt_shell = False

  def consume_stdout() -> None:
    nonlocal rebuilt_shell
    if proc.stdout is None:
      return
    try:
      for line in iter(proc.stdout.readline, ''):
        effect = _parse_cargo_json_line(line, is_first_run=is_first_run)
        if isinstance(effect, _CargoCompilerMessage):
          _emit_line(state, effect.rendered, nl=False)
        elif isinstance(effect, _CargoTestArtifact):
          test_binaries.append(effect.binary)
        elif isinstance(effect, _CargoShellRebuilt):
          rebuilt_shell = True
    except ValueError:
      pass

  stdout_thread: threading.Thread | None = None
  stderr_thread: threading.Thread | None = None
  try:
    stdout_thread = threading.Thread(target=consume_stdout, daemon=True)
    stderr_thread = threading.Thread(
      target=_forward_prefixed_stream,
      args=(state, proc.stderr, label, 'blue'),
      daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    ret = proc.wait()
  finally:
    if proc.poll() is None:
      _terminate_process(proc)
    _join_if_started(stdout_thread)
    _join_if_started(stderr_thread)
    _close_process_streams(proc)
    with state.lock:
      state.active_processes.discard(proc)

  with state.lock:
    if state.should_stop:
      return None
  success = ret == 0
  _emit_status(state, label, t.duration(), success)
  if not success:
    return None
  return _CargoBuildSummary(tuple(test_binaries), rebuilt_shell)


def _stop_and_join_child(
  old_proc: _ChildProcess | None,
  old_stdout: threading.Thread | None,
  old_stderr: threading.Thread | None,
  old_reaper: threading.Thread | None,
) -> None:
  if old_proc is not None:
    _terminate_process(old_proc)
  _join_if_started(old_stdout)
  _join_if_started(old_stderr)
  if threading.current_thread() is not old_reaper:
    _join_if_started(old_reaper)
  if old_proc is not None:
    _close_process_streams(old_proc)


def _detach_child(
  state: _WatchRuntime, *, stop: bool = False
) -> tuple[
  _ChildProcess | None,
  threading.Thread | None,
  threading.Thread | None,
  threading.Thread | None,
]:
  with state.lock:
    if stop:
      state.should_stop = True
    detached = (
      state.child_process,
      state.stdout_thread,
      state.stderr_thread,
      state.reaper_thread,
    )
    state.child_process = None
    state.stdout_thread = None
    state.stderr_thread = None
    state.reaper_thread = None
    return detached


def _flush_pending_exit_log_locked(state: _WatchRuntime) -> None:
  rc = state.pending_exit_code
  if rc is None:
    return
  state.pending_exit_code = None
  _emit_line(
    state,
    f'[test] boot_shell watcher exited (code {rc})',
    colour='yellow',
  )


def _flush_pending_exit_log(state: _WatchRuntime) -> None:
  with state.lock:
    _flush_pending_exit_log_locked(state)


def _unsubscribe_penta_recovery(
  client: _WatchmanClient, watch_root: str
) -> None:
  client.query('unsubscribe', watch_root, _PENTA_RECOVERY_SUBSCRIPTION)
  client.getSubscription(
    _PENTA_RECOVERY_SUBSCRIPTION, remove=True, root=watch_root
  )


def _service_watch_recovery_on_main(state: _WatchRuntime) -> None:
  with state.lock:
    disarm_event = state.disarm_recovery_event
    need_unsub = (
      disarm_event is not None
      and state.recovery_state is _RecoveryState.SUBSCRIBED
    )
    if disarm_event is not None:
      state.recovery_state = _RecoveryState.DISARMED
  if disarm_event is not None:
    try:
      if need_unsub:
        _unsubscribe_penta_recovery(state.client, state.watch_root)
      _flush_pending_exit_log(state)
    finally:
      with state.lock:
        state.disarm_recovery_event = None
      disarm_event.set()

  _ensure_reaped_if_exited(state)
  with state.lock:
    need_live_unsub = (
      state.child_process is not None
      and state.recovery_state is _RecoveryState.SUBSCRIBED
    )
    if need_live_unsub:
      state.recovery_state = _RecoveryState.DISARMED
  if need_live_unsub:
    _unsubscribe_penta_recovery(state.client, state.watch_root)

  _ensure_reaped_if_exited(state)
  with state.lock:
    if state.child_process is not None:
      _flush_pending_exit_log_locked(state)
      return
    if state.should_stop:
      return
    if state.recovery_state is not _RecoveryState.PENDING_ARM:
      _flush_pending_exit_log_locked(state)
      return
    state.recovery_state = _RecoveryState.SUBSCRIBING

  subscribed = False
  try:
    clock = _query_watchman_clock(state.client, state.watch_root)
    sub = _build_penta_recovery_subscription(
      since=clock, relative_root=state.relative_root
    )
    state.client.query(
      'subscribe', state.watch_root, _PENTA_RECOVERY_SUBSCRIPTION, sub
    )
    subscribed = True
  finally:
    if not subscribed:
      with state.lock:
        if state.recovery_state is _RecoveryState.SUBSCRIBING:
          state.recovery_state = _RecoveryState.DISARMED
        cancel_ev = state.disarm_recovery_event
        if cancel_ev is not None:
          state.disarm_recovery_event = None
          cancel_ev.set()

  with state.lock:
    disarm_after_sub = state.disarm_recovery_event
    interrupted = (
      disarm_after_sub is not None
      or state.child_process is not None
      or state.should_stop
    )
    if interrupted:
      state.recovery_state = _RecoveryState.DISARMED
    else:
      state.recovery_state = _RecoveryState.SUBSCRIBED

  if interrupted:
    try:
      _unsubscribe_penta_recovery(state.client, state.watch_root)
      _flush_pending_exit_log(state)
    finally:
      if disarm_after_sub is not None:
        with state.lock:
          state.disarm_recovery_event = None
        disarm_after_sub.set()
    return

  _flush_pending_exit_log(state)


def _restart_boot_shell(state: _WatchRuntime) -> bool:
  t = lib.Timer()
  _ensure_reaped_if_exited(state)
  old_proc, old_stdout, old_stderr, old_reaper = _detach_child(state)
  if old_proc is not None:
    _emit_line(state, 'Stopping active process...', colour='bright_black')
  _stop_and_join_child(old_proc, old_stdout, old_stderr, old_reaper)

  with state.lock:
    if state.should_stop:
      return False
    bin_path = state.root / 'target' / 'debug' / 'boot_shell'

  try:
    is_binary = bin_path.is_file()
  except OSError as error:
    _flush_pending_exit_log(state)
    _emit_line(state, f'[restart-shell] {error}', colour='red', bold=True)
    _emit_status(state, 'restart-shell', t.duration(), False)
    with state.lock:
      _arm_recovery_locked(state)
    return False

  if not is_binary:
    _flush_pending_exit_log(state)
    _emit_line(
      state,
      f'Could not find boot_shell binary at {bin_path}',
      colour='red',
      bold=True,
    )
    _emit_status(state, 'restart-shell', t.duration(), False)
    with state.lock:
      _arm_recovery_locked(state)
    return False

  if threading.current_thread() is state.main_thread:
    with state.lock:
      need_unsub = state.recovery_state is _RecoveryState.SUBSCRIBED
      state.recovery_state = _RecoveryState.DISARMED
    if need_unsub:
      _unsubscribe_penta_recovery(state.client, state.watch_root)
    _flush_pending_exit_log(state)
  else:
    disarm_ev: threading.Event | None = None
    with state.lock:
      if state.should_stop:
        return False
      if (
        state.recovery_state is not _RecoveryState.DISARMED
        or state.pending_exit_code is not None
      ):
        disarm_ev = threading.Event()
        state.disarm_recovery_event = disarm_ev
        _nudge_wakeup_locked(state)
    if disarm_ev is not None:
      disarm_ev.wait()
      with state.lock:
        if state.should_stop:
          return False
    _flush_pending_exit_log(state)

  with state.lock:
    if state.should_stop:
      return False
    state.shell_generation += 1
    cmd = [os.fspath(bin_path), 'test', '--watch', 'core']
    try:
      proc: _ChildProcess = subprocess.Popen(
        cmd,
        cwd=state.root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        text=True,
        encoding='utf-8',
        errors='replace',
      )
    except OSError as error:
      _emit_line(
        state, f'[restart-shell] {error}', colour='red', bold=True
      )
      _emit_status(state, 'restart-shell', t.duration(), False)
      _arm_recovery_locked(state)
      return False

    state.child_process = proc
    stdout_thread = threading.Thread(
      target=_forward_prefixed_stream,
      args=(state, proc.stdout, 'test', 'magenta'),
      daemon=True,
    )
    stderr_thread = threading.Thread(
      target=_forward_prefixed_stream,
      args=(state, proc.stderr, 'test', 'magenta'),
      daemon=True,
    )

    def reap_child() -> None:
      stdout_thread.join()
      stderr_thread.join()
      try:
        rc = proc.wait()
      except OSError:
        rc = -1
      with state.lock:
        if state.child_process is proc:
          _close_process_streams(proc)
          if not state.should_stop:
            state.pending_exit_code = rc
            _arm_recovery_locked(state)
          state.child_process = None
          state.stdout_thread = None
          state.stderr_thread = None
          state.reaper_thread = None
          _nudge_wakeup_locked(state)

    reaper_thread = threading.Thread(target=reap_child, daemon=True)
    state.stdout_thread = stdout_thread
    state.stderr_thread = stderr_thread
    state.reaper_thread = reaper_thread
    stdout_thread.start()
    stderr_thread.start()
    reaper_thread.start()

  _emit_status(state, 'restart-shell', t.duration(), True)
  return True


def _rust_build_pipeline(state: _WatchRuntime) -> bool:
  summary = _run_cargo_build(
    state,
    [
      'cargo',
      'build',
      '--bins',
      '--tests',
      '--message-format=json-diagnostic-rendered-ansi',
    ],
    'rust-build',
    is_first_run=state.first_rust_run,
  )
  if summary is None:
    return False

  with state.lock:
    if state.should_stop:
      return False

  state.first_rust_run = False
  if not summary.test_binaries:
    _emit_line(
      state, '[btest] No new test binaries to run.', colour='blue'
    )

  need_restart = summary.rebuilt_shell or not _ensure_reaped_if_exited(
    state
  )

  with concurrent.futures.ThreadPoolExecutor() as post_executor:
    try:
      sub_futures: list[concurrent.futures.Future[bool]] = [
        post_executor.submit(
          _run_cmd, state, lib.get_cargo_clippy_cmd(), 'clippy', 'yellow'
        )
      ]
      for binary in summary.test_binaries:
        sub_futures.append(
          post_executor.submit(
            _run_cmd,
            state,
            [binary.executable],
            f'btest:{binary.target_name}',
            'blue',
          )
        )
      if need_restart:
        sub_futures.append(
          post_executor.submit(_restart_boot_shell, state)
        )

      all_passed = True
      for future in concurrent.futures.as_completed(sub_futures):
        if not future.result():
          all_passed = False
    except BaseException:
      _abort_active_processes(state)
      post_executor.shutdown(wait=False, cancel_futures=True)
      raise

  return all_passed


def _consume_completed_futures(
  state: _WatchRuntime,
  pending: set[concurrent.futures.Future[bool]],
  futures: dict[concurrent.futures.Future[bool], str],
) -> bool:
  all_success = True
  for future in [f for f in pending if f.done()]:
    pending.remove(future)
    name = futures[future]
    try:
      if not future.result():
        all_success = False
    except Exception as error:
      all_success = False
      _emit_line(
        state, f'[{name}] exception: {error}', colour='red', bold=True
      )
  return all_success


def _run_watch_iteration(
  state: _WatchRuntime, files: Iterable[str]
) -> bool:
  t_total = lib.Timer()
  plan = _plan_watch_iteration(files)
  all_success = True

  with concurrent.futures.ThreadPoolExecutor() as executor:
    try:
      futures: dict[concurrent.futures.Future[bool], str] = {}
      for spec in plan.checks:
        futures[
          executor.submit(
            _run_cmd, state, spec.command, spec.label, spec.colour
          )
        ] = spec.label
      if plan.run_nix_fmt:
        futures[executor.submit(_run_nix_check, state)] = 'nix-fmt'
      if plan.run_rust_pipeline:
        futures[executor.submit(_rust_build_pipeline, state)] = (
          'rust-build'
        )

      for future in futures:
        future.add_done_callback(lambda _f: _nudge_wakeup(state))
      pending = set(futures)
      while pending:
        _service_watch_recovery_on_main(state)
        if not _consume_completed_futures(state, pending, futures):
          all_success = False
        if not pending:
          break
        select.select([state.wake_pair[0]], [], [], 0.2)
        _drain_wakeup(state.wake_pair[0])
      _service_watch_recovery_on_main(state)
    except BaseException:
      _abort_active_processes(state)
      executor.shutdown(wait=False, cancel_futures=True)
      raise

  _emit_status(state, 'watch-iteration', t_total.duration(), all_success)
  return all_success


def _shutdown_watch(state: _WatchRuntime) -> None:
  _abort_active_processes(state)
  old_proc, old_stdout, old_stderr, old_reaper = _detach_child(
    state, stop=True
  )
  _stop_and_join_child(old_proc, old_stdout, old_stderr, old_reaper)
  with suppress(pywatchman.WatchmanError, OSError):
    state.client.close()
  _close_wakeup_pair(state)


def _query_watchman_clock(client: _WatchmanClient, watch_root: str) -> str:
  clock_obj = lib.json_object(client.query('clock', watch_root))
  clock = clock_obj.get('clock') if clock_obj is not None else None
  if not isinstance(clock, str) or not clock:
    raise pywatchman.WatchmanError(
      "Watchman 'clock' response did not contain a valid 'clock'"
    )
  return clock


def _subscribe_watch(
  client: _WatchmanClient, root: Path
) -> tuple[str, str | None]:
  client.capabilityCheck(optional=[])
  project = lib.json_object(client.query('watch-project', os.fspath(root)))
  watch_root = project.get('watch') if project is not None else None
  if not isinstance(watch_root, str) or not watch_root:
    raise pywatchman.WatchmanError(
      "Watchman 'watch-project' response did not contain a valid 'watch'"
    )
  rel_obj = project.get('relative_path') if project is not None else None
  relative_root = rel_obj if isinstance(rel_obj, str) and rel_obj else None

  clock = _query_watchman_clock(client, watch_root)
  sub = _build_watch_subscription(since=clock, relative_root=relative_root)
  client.query('subscribe', watch_root, _SUBSCRIPTION_NAME, sub)
  return watch_root, relative_root


def _client_socket(client: _WatchmanClient) -> socket.socket | None:
  tport = getattr(client, 'tport', None)
  sock = getattr(tport, 'sock', None)
  return sock if isinstance(sock, socket.socket) else None


def _has_readable_socket_data(sock: socket.socket | None) -> bool:
  return sock is not None and bool(select.select([sock], [], [], 0.0)[0])


def _has_pending_wake_state(state: _WatchRuntime) -> bool:
  with state.lock:
    return (
      state.should_stop
      or state.recovery_state is _RecoveryState.PENDING_ARM
      or state.pending_exit_code is not None
      or state.disarm_recovery_event is not None
    )


def _pop_client_events(
  client: _WatchmanClient, watch_root: str, *, include_recovery: bool
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
  client.getLog(remove=True)
  pdus = client.getSubscription(
    _SUBSCRIPTION_NAME, remove=True, root=watch_root
  )
  recovery = (
    client.getSubscription(
      _PENTA_RECOVERY_SUBSCRIPTION, remove=True, root=watch_root
    )
    if include_recovery
    else None
  )
  return (list(pdus) if pdus else [], list(recovery) if recovery else [])


def _drain_subscription_events(
  state: _WatchRuntime,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
  client = state.client
  watch_root = state.watch_root
  with state.lock:
    include_recovery = state.recovery_state is _RecoveryState.SUBSCRIBED
  collected_parent, collected_recovery = _pop_client_events(
    client, watch_root, include_recovery=include_recovery
  )
  sock = _client_socket(client)

  if not collected_parent and not collected_recovery:
    if _has_pending_wake_state(state):
      return [], []
    if sock is not None:
      wake_r = state.wake_pair[0]
      readable, _, _ = select.select([sock, wake_r], [], [], 1.0)
      if wake_r in readable:
        _drain_wakeup(wake_r)
      if sock not in readable:
        return [], []
      client.receive()
    else:
      try:
        client.receive()
      except pywatchman.SocketTimeout:
        return [], []
    more_parent, more_recovery = _pop_client_events(
      client, watch_root, include_recovery=include_recovery
    )
    collected_parent.extend(more_parent)
    collected_recovery.extend(more_recovery)

  sock = _client_socket(client)
  while _has_readable_socket_data(sock):
    client.receive()
    more_parent, more_recovery = _pop_client_events(
      client, watch_root, include_recovery=include_recovery
    )
    collected_parent.extend(more_parent)
    collected_recovery.extend(more_recovery)
    sock = _client_socket(client)
  return collected_parent, collected_recovery


def _extract_pdu_files(
  state: _WatchRuntime,
  pdus: Sequence[dict[str, object]],
  subscription_name: str,
) -> list[str]:
  files: list[str] = []
  for pdu in pdus:
    if pdu.get('canceled') is True:
      _emit_line(
        state,
        f"Watchman error: subscription '{subscription_name}' was "
        'cancelled',
        err=True,
      )
      raise SystemExit(1)
    pdu_files = lib.string_list(pdu.get('files', []))
    if pdu_files is not None:
      files.extend(pdu_files)
  return files


def run_watch(root: str | os.PathLike[str] | None = None) -> None:
  """Subscribe to repository changes and run incremental check loops."""
  state: _WatchRuntime | None = None
  raw_client: _WatchmanClient | None = None
  wake_pair: tuple[socket.socket, socket.socket] | None = None
  try:
    try:
      raw_root = os.getcwd() if root is None else root
      resolved_root = Path(raw_root).resolve()
      wake_pair = _create_wakeup_pair()
    except OSError as error:
      _emit_startup_error(f'Watch error: {error}')
      raise SystemExit(1) from error

    try:
      client = pywatchman.client(timeout=60.0)
      if 'subs' not in vars(client):
        client.subs = {}
      if 'sub_by_root' not in vars(client):
        client.sub_by_root = {}
      if 'logs' not in vars(client):
        client.logs = []
      raw_client = client
      watch_root, relative_root = _subscribe_watch(client, resolved_root)
      if _client_socket(client) is None:
        client.setTimeout(1.0)
    except (pywatchman.WatchmanError, OSError, ValueError) as error:
      _emit_startup_error(f'Watchman error: {error}')
      raise SystemExit(1) from error

    state = _WatchRuntime(
      root=resolved_root,
      client=raw_client,
      watch_root=watch_root,
      relative_root=relative_root,
      wake_pair=wake_pair,
    )

    summary = _run_cargo_build(
      state,
      [
        'cargo',
        'build',
        '-p',
        'boot_shell',
        '--message-format=json-diagnostic-rendered-ansi',
      ],
      'boot-shell-build',
      is_first_run=False,
    )
    if summary is not None:
      _restart_boot_shell(state)

    while not state.should_stop:
      try:
        _service_watch_recovery_on_main(state)
        parent_pdus, recovery_pdus = _drain_subscription_events(state)
        _service_watch_recovery_on_main(state)
      except (pywatchman.WatchmanError, OSError, ValueError) as error:
        _emit_line(state, f'Watchman error: {error}', err=True)
        raise SystemExit(1) from error

      parent_raw = _extract_pdu_files(
        state, parent_pdus, _SUBSCRIPTION_NAME
      )
      recovery_raw = _extract_pdu_files(
        state, recovery_pdus, _PENTA_RECOVERY_SUBSCRIPTION
      )
      parent_files = _filter_parent_files(parent_raw)
      has_recovery_penta = bool(_filter_penta_files(recovery_raw))

      with state.lock:
        gen_before = state.shell_generation

      if parent_files:
        _emit_line(
          state,
          f'Change detected in {len(parent_files)} files...',
          colour='bright_black',
        )
        try:
          _run_watch_iteration(state, parent_files)
        except (pywatchman.WatchmanError, OSError, ValueError) as error:
          _emit_line(state, f'Watchman error: {error}', err=True)
          raise SystemExit(1) from error

      try:
        _service_watch_recovery_on_main(state)
      except (pywatchman.WatchmanError, OSError, ValueError) as error:
        _emit_line(state, f'Watchman error: {error}', err=True)
        raise SystemExit(1) from error

      if (
        has_recovery_penta
        and not _ensure_reaped_if_exited(state)
        and state.shell_generation == gen_before
      ):
        try:
          _restart_boot_shell(state)
        except (pywatchman.WatchmanError, OSError, ValueError) as error:
          _emit_line(state, f'Watchman error: {error}', err=True)
          raise SystemExit(1) from error
  except KeyboardInterrupt:
    pass
  finally:
    if state is not None:
      _shutdown_watch(state)
    else:
      if raw_client is not None:
        with suppress(pywatchman.WatchmanError, OSError):
          raw_client.close()
      if wake_pair is not None:
        for sock in wake_pair:
          with suppress(OSError):
            sock.close()
