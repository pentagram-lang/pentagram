import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import IO, TypedDict

import pywatchman

from zero import lib

# ANSI Colours
GREY = '\033[90m'
RED = '\033[1;91m'
GREEN = '\033[1;92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
RESET = '\033[0m'


class BuildState(TypedDict):
  rebuilt_shell: bool


type TestBinary = tuple[str, str]


def _string_keyed_object(value: object) -> dict[str, object] | None:
  if not isinstance(value, dict):
    return None
  result: dict[str, object] = {}
  for key, item in value.items():
    if not isinstance(key, str):
      return None
    result[key] = item
  return result


def _string_list(value: object) -> list[str] | None:
  if not isinstance(value, list):
    return None
  result: list[str] = []
  for item in value:
    if not isinstance(item, str):
      return None
    result.append(item)
  return result


def colour_line(line: str, colour: str) -> str:
  return f'{colour}{line}{RESET}'


def status(label: str, duration: float, success: bool = True) -> None:
  colour = GREEN if success else RED
  text = 'PASS' if success else 'FAIL'
  print(f'[{colour}{text}{RESET}] {label} ({duration:.2f}s)')


class Timer:
  def __init__(self) -> None:
    self.start = time.time()

  def duration(self) -> float:
    return time.time() - self.start


class StreamPrefixer(threading.Thread):
  def __init__(
    self,
    stream: IO[str] | None,
    prefix: str,
    colour: str,
    output_stream: IO[str] | None = None,
  ) -> None:
    super().__init__()
    self.stream = stream
    self.prefix = prefix
    self.colour = colour
    self.output_stream = (
      sys.stdout if output_stream is None else output_stream
    )
    self.daemon = True

  def run(self) -> None:
    try:
      if self.stream is None:
        return
      for line in iter(self.stream.readline, ''):
        line_str = line.rstrip()
        if line_str:
          formatted = f'{self.colour}[{self.prefix}] {line_str}{RESET}\n'
          self.output_stream.write(formatted)
          self.output_stream.flush()
    except ValueError:
      pass  # Stream closed


def _python_test_commands(
  files: Iterable[str],
) -> list[tuple[list[str], str]]:
  roots = {
    path.parts[0]
    for path in (PurePosixPath(file) for file in files)
    if path.parts and path.suffix == '.py'
  }
  return [
    (['0', 'check', command], command)
    for root, command in (('zero', 'ztest'), ('proj', 'ptest'))
    if root in roots
  ]


def _nixfmt_check_command(root: str | os.PathLike[str]) -> list[str]:
  root_path = Path(root)
  nix_files = sorted(
    str(path)
    for pattern in ('*.nix', 'nix/*.nix')
    for path in root_path.glob(pattern)
    if path.is_file()
  )
  return ['nixfmt', '--check', *nix_files]


class WatchSession:
  def __init__(self, root: str | os.PathLike[str]) -> None:
    self.root = os.path.abspath(root)
    self.client = pywatchman.client(timeout=1.0)
    self.child_process: subprocess.Popen[str] | None = None
    self.stdout_thread: StreamPrefixer | None = None
    self.stderr_thread: StreamPrefixer | None = None
    self.should_stop = False
    self.lock = threading.Lock()
    self.first_rust_run = True

  def start(self) -> None:
    try:
      self.client.capabilityCheck(optional=[])
      # Watch the project root
      self.client.query('watch-project', self.root)
    except pywatchman.CommandError as ex:
      print(f'Watchman error: {ex}')
      return

    self._subscribe()
    self._loop()

  def _subscribe(self) -> None:
    # Trigger on any Rust file change or Cargo.toml/lock
    sub = {
      'expression': [
        'anyof',
        ['suffix', 'rs'],
        ['suffix', 'py'],
        ['suffix', 'md'],
        ['suffix', 'json'],
        ['suffix', 'nix'],
        ['suffix', 'toml'],
        ['name', 'Cargo.toml'],
        ['name', 'Cargo.lock'],
      ],
      'fields': ['name'],
      'defer_vcs': False,
    }
    self.client.query('subscribe', self.root, 'rust-trigger', sub)

  def _loop(self) -> None:
    while not self.should_stop:
      try:
        # Receive events
        event = _string_keyed_object(self.client.receive())
        if event is None or event.get('subscription') != 'rust-trigger':
          continue
        files = _string_list(event.get('files', []))
        if files is None:
          continue
        if files:
          print(f'{GREY}Change detected in {len(files)} files...{RESET}')
          self._rebuild_and_restart(files)

      except pywatchman.SocketTimeout:
        pass
      except KeyboardInterrupt:
        self.stop()
        break

  def _rebuild_and_restart(
    self, files: Iterable[str] | None = None
  ) -> None:
    t_total = Timer()
    # Determine context
    is_rust = True
    is_python = True
    is_dprint = True
    is_nix = True
    if files:
      is_rust = any(f.endswith('.rs') or 'Cargo' in f for f in files)
      is_python = any(f.endswith('.py') for f in files)
      is_dprint = any(
        f.endswith('.json') or f.endswith('.md') or f.endswith('.toml')
        for f in files
      )
      is_nix = any(f.endswith('.nix') for f in files)

    all_success = True

    # Use a ThreadPoolExecutor for max parallelism
    with concurrent.futures.ThreadPoolExecutor() as executor:
      futures = {}

      # 1. Independent Checks (Format/Lint)
      if is_rust:
        futures[
          executor.submit(
            self._run_cmd,
            ['cargo', 'fmt', '--', '--check'],
            'rust-fmt',
            CYAN,
          )
        ] = 'rust-fmt'

      if is_python:
        futures[
          executor.submit(
            self._run_cmd, ['ruff', 'format', '--check'], 'py-fmt', CYAN
          )
        ] = 'py-fmt'
        futures[
          executor.submit(
            self._run_cmd, ['ruff', 'check'], 'py-lint', YELLOW
          )
        ] = 'py-lint'
        for command, label in _python_test_commands(files or ()):
          futures[
            executor.submit(self._run_cmd, command, label, MAGENTA)
          ] = label

      if is_dprint:
        futures[
          executor.submit(
            self._run_cmd, ['dprint', 'check'], 'dprint', CYAN
          )
        ] = 'dprint'

      if is_nix:
        futures[
          executor.submit(
            self._run_cmd,
            _nixfmt_check_command(self.root),
            'nix-fmt',
            CYAN,
          )
        ] = 'nix-fmt'

      # 2. Rust Build Pipeline (The heavy lifter)
      if is_rust:
        # We submit the build pipeline as a single task that may fan out
        # later
        futures[executor.submit(self._rust_build_pipeline, executor)] = (
          'rust-build'
        )

      # Wait for all submitted tasks
      # We don't necessarily stop on one failure, we let them all complete
      # to show all errors
      for future in concurrent.futures.as_completed(futures):
        name = futures[future]
        try:
          success = future.result()
          if not success:
            all_success = False
        except Exception as e:
          all_success = False
          print(f'{RED}[{name}] exception: {e}{RESET}')

    status('watch-iteration', t_total.duration(), all_success)

  def _rust_build_pipeline(
    self, executor: concurrent.futures.ThreadPoolExecutor
  ) -> bool:
    t = Timer()
    # A. Build & Discover
    print(f'{BLUE}Running build...{RESET}')
    test_binaries: list[TestBinary] = []
    build_state: BuildState = {'rebuilt_shell': False}

    cmd = [
      'cargo',
      'build',
      '--tests',
      '--message-format=json-diagnostic-rendered-ansi',
    ]

    proc = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      bufsize=1,
      text=True,
    )

    # We must consume stdout/stderr
    # We can use our StreamPrefixer/Process logic, but we need to do it
    # here blocking
    stdout_thread = threading.Thread(
      target=self._process_build_output,
      args=(proc.stdout, test_binaries, build_state, self.first_rust_run),
    )
    stderr_thread = StreamPrefixer(proc.stderr, 'build', BLUE)

    stdout_thread.start()
    stderr_thread.start()

    ret = proc.wait()
    stdout_thread.join()
    stderr_thread.join()

    if ret != 0:
      status('rust-build', t.duration(), False)
      return False

    status('rust-build', t.duration(), True)

    # After first successful build, we are no longer in "first run"
    self.first_rust_run = False

    # B. Post-Build Parallelism
    # Now that build is done, we can run Clippy (takes lock) and Tests
    # (no lock) in parallel

    sub_futures = []

    # B1. Clippy
    sub_futures.append(
      executor.submit(
        self._run_cmd,
        lib.get_cargo_clippy_cmd(),
        'clippy',
        YELLOW,
      )
    )

    # B2. Unit Tests (Parallel Execution of Binaries)
    if not test_binaries:
      print(f'{BLUE}[btest] No new test binaries to run.{RESET}')

    for test_bin, name in test_binaries:
      sub_futures.append(
        executor.submit(self._run_cmd, [test_bin], f'btest:{name}', BLUE)
      )

    # B3. Restart Child (The App)
    # We only restart if the shell was rebuilt, or if it's not running yet.
    if build_state['rebuilt_shell'] or self.child_process is None:
      sub_futures.append(executor.submit(self._restart_child_process))

    # Wait for sub-futures to report status
    all_passed = True
    for f in concurrent.futures.as_completed(sub_futures):
      if not f.result():
        all_passed = False

    return all_passed

  def _restart_child_process(self) -> bool:
    t = Timer()
    with self.lock:
      if self.child_process:
        print(f'{GREY}Stopping active process...{RESET}')
        self.child_process.terminate()
        try:
          self.child_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
          self.child_process.kill()
        self.child_process = None

      bin_path = os.path.join(self.root, 'target', 'debug', 'boot_shell')
      if not os.path.isfile(bin_path):
        print(
          f'{RED}Could not find boot_shell binary at {bin_path}{RESET}'
        )
        status('restart-shell', t.duration(), False)
        return False

      self._start_child()
    status('restart-shell', t.duration(), True)
    return True

  def _process_build_output(
    self,
    stream: IO[str] | None,
    binaries: list[TestBinary],
    state: BuildState,
    is_first_run: bool,
  ) -> None:
    try:
      if stream is None:
        return
      for line in iter(stream.readline, ''):
        if not line:
          break
        try:
          data = _string_keyed_object(json.loads(line))
          if data is None:
            continue
          reason = data.get('reason')

          if reason == 'compiler-message':
            message = _string_keyed_object(data.get('message'))
            rendered = (
              message.get('rendered') if message is not None else None
            )
            if isinstance(rendered, str) and rendered:
              sys.stdout.write(rendered)

          elif reason == 'compiler-artifact':
            target = _string_keyed_object(data.get('target'))
            target_name = (
              target.get('name') if target is not None else None
            )
            profile = _string_keyed_object(data.get('profile'))
            test_profile = (
              profile.get('test') if profile is not None else False
            )
            fresh = data.get('fresh', False)
            executable = data.get('executable')

            if isinstance(executable, str) and isinstance(
              target_name, str
            ):
              if test_profile is True:
                if is_first_run or fresh is False:
                  binaries.append((executable, target_name))
              elif target_name == 'boot_shell' and fresh is False:
                state['rebuilt_shell'] = True

        except json.JSONDecodeError:
          pass
    except ValueError:
      pass

  def _run_cmd(self, cmd: Sequence[str], label: str, colour: str) -> bool:
    print(f'{colour}Running {label}...{RESET}')
    t = Timer()
    proc = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      bufsize=1,
      text=True,
    )

    stdout_thread = StreamPrefixer(proc.stdout, label, colour)
    stderr_thread = StreamPrefixer(proc.stderr, label, colour)
    stdout_thread.start()
    stderr_thread.start()

    ret = proc.wait()
    stdout_thread.join()
    stderr_thread.join()

    duration = t.duration()
    success = ret == 0
    status(label, duration, success)
    return success

  def _start_child(self) -> None:
    # Run the boot_shell binary directly
    # We assume it was built by the build step
    bin_path = os.path.join(self.root, 'target', 'debug', 'boot_shell')
    cmd = [
      bin_path,
      'test',
      '--watch',
      'core',
    ]

    self.child_process = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      bufsize=1,
      text=True,
    )

    self.stdout_thread = StreamPrefixer(
      self.child_process.stdout, 'test', MAGENTA
    )
    self.stderr_thread = StreamPrefixer(
      self.child_process.stderr, 'test', MAGENTA
    )
    self.stdout_thread.start()
    self.stderr_thread.start()

  def stop(self) -> None:
    self.should_stop = True
    if self.child_process:
      self.child_process.terminate()


def run_watch() -> None:
  session = WatchSession(os.getcwd())
  try:
    session.start()
  except KeyboardInterrupt:
    session.stop()
