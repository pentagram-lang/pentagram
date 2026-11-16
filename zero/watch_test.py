"""Tests for zero.watch."""

import concurrent.futures
import json
import os
import socket
import threading
from collections.abc import Callable, Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

import pytest
import pywatchman
from pytest import CaptureFixture, MonkeyPatch
from pywatchman import bser

from zero import lib, watch

ROOT = Path('/virtual/repo')


class _TrackedStringIO(StringIO):
  def __init__(self, initial_value: str = '') -> None:
    super().__init__(initial_value)
    self.closed_event = threading.Event()

  def close(self) -> None:
    super().close()
    self.closed_event.set()


@dataclass(eq=False)
class _FakeProcess:
  stdout: StringIO = field(default_factory=StringIO)
  stderr: StringIO = field(default_factory=StringIO)
  exit_code: int = 0
  poll_result: int | None = 0
  wait_outcomes: list[int | BaseException] = field(default_factory=list)
  wait_until_stopped: bool = False
  on_wait_enter: Callable[[], None] | None = None
  terminate_error: OSError | None = None
  actions: list[str] = field(default_factory=list)
  stop_event: threading.Event = field(default_factory=threading.Event)

  def poll(self) -> int | None:
    return self.poll_result

  def wait(self, timeout: float | None = None) -> int:
    self.actions.append(
      f'wait:{timeout}' if timeout is not None else 'wait'
    )
    if self.on_wait_enter is not None:
      self.on_wait_enter()
    if self.wait_outcomes:
      outcome = self.wait_outcomes.pop(0)
      if isinstance(outcome, BaseException):
        raise outcome
      return outcome
    if self.wait_until_stopped and timeout is None:
      self.stop_event.wait(timeout=2.0)
    return self.exit_code

  def terminate(self) -> None:
    self.actions.append('terminate')
    self.poll_result = -15
    self.stop_event.set()
    if self.terminate_error is not None:
      raise self.terminate_error

  def kill(self) -> None:
    self.actions.append('kill')
    self.poll_result = -9
    self.stop_event.set()


class _FakeWatchmanClient:
  def __init__(
    self,
    *,
    watch_project_reply: object = None,
    clock_reply: object = None,
    query_error: BaseException | None = None,
    buffered_pdus: list[dict[str, object]] | None = None,
    receive_steps: list[object] | None = None,
  ) -> None:
    self.watch_project_reply = (
      {'watch': '/virtual', 'relative_path': 'repo'}
      if watch_project_reply is None
      else watch_project_reply
    )
    self.clock_reply = (
      {'clock': 'c:42:1'} if clock_reply is None else clock_reply
    )
    self.query_error = query_error
    self.receive_steps = list(receive_steps or [])
    self.queries: list[tuple[object, ...]] = []
    self.timeouts: list[float] = []
    self.closed = False
    self.subs: dict[str, list[dict[str, object]]] = {}
    self.logs: list[object] = []
    self.sub_by_root: dict[str, dict[str, list[dict[str, object]]]] = {}
    if buffered_pdus:
      root = os.path.normpath(os.path.normcase('/virtual'))
      self.sub_by_root[root] = {
        watch._SUBSCRIPTION_NAME: list(buffered_pdus)
      }

  def capabilityCheck(self, optional: list[str] | None = None) -> None:
    self.queries.append(('capabilityCheck', tuple(optional or ())))

  def query(self, *args: object) -> object:
    self.queries.append(args)
    if self.query_error is not None:
      raise self.query_error
    if args[0] == 'watch-project':
      return self.watch_project_reply
    if args[0] == 'clock':
      return self.clock_reply
    if args[0] == 'subscribe':
      return {'subscribe': watch._SUBSCRIPTION_NAME}
    return {}

  def receive(self) -> object:
    step = self.receive_steps.pop(0)
    if isinstance(step, BaseException):
      raise step
    pdus = step if isinstance(step, list) else [step]
    for item in pdus:
      if isinstance(item, dict) and 'log' in item:
        self.logs.append(item['log'])
      if isinstance(item, dict) and 'subscription' in item:
        sub_name = str(item['subscription'])
        root = os.path.normpath(
          os.path.normcase(str(item.get('root', '/virtual')))
        )
        self.sub_by_root.setdefault(root, {}).setdefault(
          sub_name, []
        ).append(item)
    return pdus[-1] if pdus else {}

  def getLog(self, remove: bool = True) -> list[object]:
    res = self.logs
    if remove:
      self.logs = []
    return res

  def setTimeout(self, value: float) -> None:
    self.timeouts.append(value)

  def getSubscription(
    self,
    name: str,
    remove: bool = True,
    root: str | None = None,
  ) -> list[dict[str, object]] | None:
    norm_root = os.path.normpath(
      os.path.normcase('/virtual' if root is None else root)
    )
    subs = self.sub_by_root.get(norm_root, {})
    pdus = subs.get(name)
    if pdus is None:
      return None
    if remove:
      del subs[name]
    return pdus

  def close(self) -> None:
    self.closed = True


@contextmanager
def _runtime(
  client: _FakeWatchmanClient | None = None,
) -> Iterator[watch._WatchRuntime]:
  state = watch._WatchRuntime(
    root=ROOT,
    client=_FakeWatchmanClient() if client is None else client,
    watch_root='/virtual',
    relative_root='repo',
    wake_pair=watch._create_wakeup_pair(),
  )
  try:
    yield state
  finally:
    watch._shutdown_watch(state)


def _socketpair_watchman_client(
  sock: socket.socket,
) -> pywatchman.client:
  sock.settimeout(60.0)
  transport = pywatchman.SocketTransport()
  transport.sock = sock
  transport.timeout = 60.0
  client = pywatchman.client(timeout=60.0)
  client.subs = {}
  client.sub_by_root = {}
  client.logs = []
  client.tport = transport
  client.sendConn = pywatchman.BserCodec(
    transport, 'utf-8', 'surrogateescape'
  )
  client.recvConn = pywatchman.BserCodec(
    transport, 'utf-8', 'surrogateescape'
  )
  client.pid = os.getpid()
  return client


def _install_constant_clock(
  mp: MonkeyPatch, duration: float = 0.25
) -> None:
  class _FakeTimer:
    def duration(self) -> float:
      return duration

  mp.setattr(watch.lib, 'Timer', _FakeTimer)


def test_partition_watch_files_and_subscription_spec() -> None:
  raw = [
    'target/debug/boot_shell.rs',
    'target-analyzer/foo.rs',
    '.pytest_cache/README.md',
    '.ruff_cache/cache.json',
    'pkg/__pycache__/mod.py',
    '.git/index',
    '.jj/working_copy/foo.toml',
    '.tmp/scratch.md',
    '.nix-cache/store.nix',
    'result',
    'result/bin/tool.py',
    'FOO.MD',
    'zero/watch.py',
    'zero/watch.py',
    'core/tests/demo.penta',
    'docs/Cargo_notes.md',
  ]
  assert watch._filter_parent_files(raw) == (
    'zero/watch.py',
    'docs/Cargo_notes.md',
  )
  assert watch._filter_penta_files(raw) == ('core/tests/demo.penta',)
  assert watch._filter_parent_files(['core/tests/demo.penta']) == ()
  assert watch._filter_penta_files(['FOO.MD']) == ()
  assert watch._filter_parent_files(['FOO.MD']) == ()

  assert watch._build_watch_subscription(
    since='c:1:2', relative_root='sub/pkg'
  ) == {
    'expression': [
      'allof',
      [
        'not',
        [
          'anyof',
          ['dirname', '.git'],
          ['dirname', '.jj'],
          ['dirname', '.tmp'],
          ['dirname', '.nix-cache'],
          ['dirname', '.pytest_cache'],
          ['dirname', '.ruff_cache'],
          ['dirname', '__pycache__'],
          ['dirname', 'target'],
          ['dirname', 'target-analyzer'],
          ['dirname', 'result'],
          ['name', 'result'],
        ],
      ],
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
    ],
    'fields': ['name'],
    'defer_vcs': False,
    'since': 'c:1:2',
    'relative_root': 'sub/pkg',
  }
  assert watch._build_penta_recovery_subscription(
    since='c:1:2', relative_root='sub/pkg'
  ) == {
    'expression': [
      'allof',
      [
        'not',
        [
          'anyof',
          ['dirname', '.git'],
          ['dirname', '.jj'],
          ['dirname', '.tmp'],
          ['dirname', '.nix-cache'],
          ['dirname', '.pytest_cache'],
          ['dirname', '.ruff_cache'],
          ['dirname', '__pycache__'],
          ['dirname', 'target'],
          ['dirname', 'target-analyzer'],
          ['dirname', 'result'],
          ['name', 'result'],
        ],
      ],
      ['suffix', 'penta'],
    ],
    'fields': ['name'],
    'defer_vcs': False,
    'since': 'c:1:2',
    'relative_root': 'sub/pkg',
  }


@pytest.mark.parametrize(
  ('files', 'expected'),
  (
    (
      ['zero/cli.py'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('ruff', 'format', '--check'), 'py-fmt', 'cyan'
          ),
          watch._CheckSpec(('ruff', 'check'), 'py-lint', 'yellow'),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'type'), 'type', 'yellow'
          ),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'ztest'), 'ztest', 'magenta'
          ),
        )
      ),
    ),
    (
      ['proj/cli.py'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('ruff', 'format', '--check'), 'py-fmt', 'cyan'
          ),
          watch._CheckSpec(('ruff', 'check'), 'py-lint', 'yellow'),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'type'), 'type', 'yellow'
          ),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'ptest'), 'ptest', 'magenta'
          ),
        )
      ),
    ),
    (
      ['zero/cli.py', 'proj/cli.py', 'other/helper.py'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('ruff', 'format', '--check'), 'py-fmt', 'cyan'
          ),
          watch._CheckSpec(('ruff', 'check'), 'py-lint', 'yellow'),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'type'), 'type', 'yellow'
          ),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'ztest'), 'ztest', 'magenta'
          ),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'ptest'), 'ptest', 'magenta'
          ),
        )
      ),
    ),
    (
      ['other/helper.py'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('ruff', 'format', '--check'), 'py-fmt', 'cyan'
          ),
          watch._CheckSpec(('ruff', 'check'), 'py-lint', 'yellow'),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'type'), 'type', 'yellow'
          ),
        )
      ),
    ),
    (
      ['docs/guide.md', 'dprint.json', 'pyproject.toml'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(('dprint', 'check'), 'dprint', 'cyan'),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'doc'), 'doc-lint', 'yellow'
          ),
        )
      ),
    ),
    (
      ['docs/Cargo_notes.md'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(('dprint', 'check'), 'dprint', 'cyan'),
          watch._CheckSpec(
            ('/py', '-m', 'zero', 'check', 'doc'), 'doc-lint', 'yellow'
          ),
        )
      ),
    ),
    (
      ['flake.nix'],
      watch._WatchPlan(
        checks=(), run_nix_fmt=True, run_rust_pipeline=False
      ),
    ),
    (
      ['Cargo.toml'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('cargo', 'fmt', '--', '--check'), 'rust-fmt', 'cyan'
          ),
          watch._CheckSpec(('dprint', 'check'), 'dprint', 'cyan'),
        ),
        run_rust_pipeline=True,
      ),
    ),
    (
      ['Cargo.lock'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('cargo', 'fmt', '--', '--check'), 'rust-fmt', 'cyan'
          ),
        ),
        run_rust_pipeline=True,
      ),
    ),
    (
      ['core/src/lib.rs'],
      watch._WatchPlan(
        checks=(
          watch._CheckSpec(
            ('cargo', 'fmt', '--', '--check'), 'rust-fmt', 'cyan'
          ),
        ),
        run_rust_pipeline=True,
      ),
    ),
    (
      [
        'target/debug/foo.rs',
        '.pytest_cache/README.md',
        'core/tests/demo.penta',
        'FOO.MD',
      ],
      watch._WatchPlan(
        checks=(), run_nix_fmt=False, run_rust_pipeline=False
      ),
    ),
  ),
  ids=(
    'py-zero',
    'py-proj',
    'py-both-and-other',
    'py-outside',
    'md-json-toml-dedup-dprint',
    'cargo-named-markdown-no-rust',
    'nix',
    'cargo-toml',
    'cargo-lock',
    'rust-source',
    'ignored-and-penta',
  ),
)
def test_plan_watch_iteration_maps_changed_files(
  monkeypatch: MonkeyPatch, files: list[str], expected: watch._WatchPlan
) -> None:
  monkeypatch.setattr(watch.sys, 'executable', '/py')
  assert watch._plan_watch_iteration(files) == expected


def test_parse_cargo_json_line_returns_effect_union() -> None:
  msg_line = json.dumps(
    {
      'reason': 'compiler-message',
      'message': {'rendered': 'warning: unused\n'},
    }
  )
  fresh_test_line = json.dumps(
    {
      'reason': 'compiler-artifact',
      'target': {'name': 'core_unit'},
      'profile': {'test': True},
      'fresh': True,
      'executable': '/repo/target/debug/deps/core_unit-123',
    }
  )
  stale_test_line = json.dumps(
    {
      'reason': 'compiler-artifact',
      'target': {'name': 'core_int'},
      'profile': {'test': True},
      'fresh': False,
      'executable': '/repo/target/debug/deps/core_int-456',
    }
  )
  fresh_shell_line = json.dumps(
    {
      'reason': 'compiler-artifact',
      'target': {'name': 'boot_shell'},
      'profile': {'test': False},
      'fresh': True,
      'executable': '/repo/target/debug/boot_shell',
    }
  )
  rebuilt_shell_line = json.dumps(
    {
      'reason': 'compiler-artifact',
      'target': {'name': 'boot_shell'},
      'profile': {'test': False},
      'fresh': False,
      'executable': '/repo/target/debug/boot_shell',
    }
  )

  assert (
    watch._parse_cargo_json_line('not json', is_first_run=True),
    watch._parse_cargo_json_line(msg_line, is_first_run=True),
    watch._parse_cargo_json_line(fresh_test_line, is_first_run=True),
    watch._parse_cargo_json_line(fresh_test_line, is_first_run=False),
    watch._parse_cargo_json_line(stale_test_line, is_first_run=False),
    watch._parse_cargo_json_line(fresh_shell_line, is_first_run=False),
    watch._parse_cargo_json_line(rebuilt_shell_line, is_first_run=False),
  ) == (
    None,
    watch._CargoCompilerMessage('warning: unused\n'),
    watch._CargoTestArtifact(
      watch._TestBinary(
        '/repo/target/debug/deps/core_unit-123', 'core_unit'
      )
    ),
    None,
    watch._CargoTestArtifact(
      watch._TestBinary('/repo/target/debug/deps/core_int-456', 'core_int')
    ),
    None,
    watch._CargoShellRebuilt(),
  )


def test_run_watch_iteration_forwards_cwd_and_closes_pipes(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  popen_calls: list[dict[str, object]] = []
  spawned: list[_FakeProcess] = []

  def fake_popen(cmd: Sequence[str], **kwargs: object) -> _FakeProcess:
    proc = _FakeProcess(
      _TrackedStringIO(), _TrackedStringIO(), exit_code=0
    )
    spawned.append(proc)
    popen_calls.append(
      {
        'cmd': tuple(cmd),
        'cwd': kwargs.get('cwd'),
        'encoding': kwargs.get('encoding'),
        'errors': kwargs.get('errors'),
      }
    )
    return proc

  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(watch.sys, 'executable', '/py')
    mp.setattr(
      watch.lib,
      'nix_files',
      lambda root: ([str(ROOT / 'flake.nix')] if root == ROOT else []),
    )
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    ok = watch._run_watch_iteration(
      state,
      ['zero/cli.py', 'proj/cli.py', 'flake.nix', 'docs/guide.md'],
    )
    assert ok
    assert state.active_processes == set()
  assert all(p.stdout.closed and p.stderr.closed for p in spawned)
  assert {c['cmd'] for c in popen_calls} == {
    ('ruff', 'format', '--check'),
    ('ruff', 'check'),
    ('/py', '-m', 'zero', 'check', 'type'),
    ('/py', '-m', 'zero', 'check', 'ztest'),
    ('/py', '-m', 'zero', 'check', 'ptest'),
    ('dprint', 'check'),
    ('/py', '-m', 'zero', 'check', 'doc'),
    ('nixfmt', '--check', '--', str(ROOT / 'flake.nix')),
  }
  assert {(c['cwd'], c['encoding'], c['errors']) for c in popen_calls} == {
    (ROOT, 'utf-8', 'replace')
  }
  captured = capsys.readouterr()
  assert captured.err == ''
  assert sorted(captured.out.splitlines()) == sorted(
    [
      'Running py-fmt...',
      '[PASS] py-fmt (0.25s)',
      'Running py-lint...',
      '[PASS] py-lint (0.25s)',
      'Running type...',
      '[PASS] type (0.25s)',
      'Running ztest...',
      '[PASS] ztest (0.25s)',
      'Running ptest...',
      '[PASS] ptest (0.25s)',
      'Running dprint...',
      '[PASS] dprint (0.25s)',
      'Running doc-lint...',
      '[PASS] doc-lint (0.25s)',
      'Running nix-fmt...',
      '[PASS] nix-fmt (0.25s)',
      '[PASS] watch-iteration (0.25s)',
    ]
  )


def test_run_watch_iteration_skips_empty_nix_files(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(watch.lib, 'nix_files', lambda _r: [])
    mp.setattr(
      watch.subprocess,
      'Popen',
      lambda *_a, **_kw: (_ for _ in ()).throw(
        AssertionError('unexpected')
      ),
    )
    assert watch._run_watch_iteration(state, ['flake.nix'])

  assert capsys.readouterr() == ('[PASS] watch-iteration (0.25s)\n', '')


def test_run_watch_iteration_reports_nix_discovery_error(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(
      watch.lib,
      'nix_files',
      lambda _r: (_ for _ in ()).throw(
        RuntimeError('Cannot scan Nix files with git: fatal')
      ),
    )
    assert not watch._run_watch_iteration(state, ['flake.nix'])

  assert capsys.readouterr() == (
    '[nix-fmt] Cannot scan Nix files with git: fatal\n'
    '[FAIL] nix-fmt (0.25s)\n'
    '[FAIL] watch-iteration (0.25s)\n',
    '',
  )


def test_run_watch_iteration_reports_popen_error(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(watch.sys, 'executable', '/py')
    mp.setattr(
      watch.subprocess,
      'Popen',
      lambda *_a, **_kw: (_ for _ in ()).throw(
        FileNotFoundError(2, 'python missing')
      ),
    )
    assert not watch._run_watch_iteration(state, ['other/mod.py'])

  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running py-fmt...',
        '[py-fmt] [Errno 2] python missing',
        '[FAIL] py-fmt (0.25s)',
        'Running py-lint...',
        '[py-lint] [Errno 2] python missing',
        '[FAIL] py-lint (0.25s)',
        'Running type...',
        '[type] [Errno 2] python missing',
        '[FAIL] type (0.25s)',
        '[FAIL] watch-iteration (0.25s)',
      ]
    ),
  )


def test_rust_build_pipeline_builds_bins_and_tests_without_deadlock(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  build_stdout = (
    '\n'.join(
      (
        json.dumps(
          {
            'reason': 'compiler-message',
            'message': {'rendered': 'warning: demo\n'},
          }
        ),
        json.dumps(
          {
            'reason': 'compiler-artifact',
            'target': {'name': 'core_test'},
            'profile': {'test': True},
            'fresh': True,
            'executable': '/virtual/repo/target/debug/deps/core_test-1',
          }
        ),
        json.dumps(
          {
            'reason': 'compiler-artifact',
            'target': {'name': 'boot_shell'},
            'profile': {'test': False},
            'fresh': False,
            'executable': str(shell_bin),
          }
        ),
      )
    )
    + '\n'
  )

  popen_calls: list[tuple[tuple[str, ...], object]] = []
  transient_procs: list[_FakeProcess] = []
  child_proc = _FakeProcess(
    StringIO('watching core\n'),
    StringIO(),
    exit_code=0,
    poll_result=None,
    wait_until_stopped=True,
  )
  clippy_cmd = tuple(lib.get_cargo_clippy_cmd())
  original_executor = concurrent.futures.ThreadPoolExecutor
  executor_max_workers: list[int | None] = []

  def single_outer_executor(
    max_workers: int | None = None,
  ) -> concurrent.futures.ThreadPoolExecutor:
    chosen = 1 if not executor_max_workers else max_workers
    executor_max_workers.append(chosen)
    return original_executor(max_workers=chosen)

  def fake_popen(cmd: Sequence[str], **kwargs: object) -> _FakeProcess:
    cmd_tuple = tuple(cmd)
    popen_calls.append((cmd_tuple, kwargs.get('cwd')))
    if cmd_tuple[:4] == ('cargo', 'build', '--bins', '--tests'):
      proc = _FakeProcess(StringIO(build_stdout), StringIO(), exit_code=0)
      transient_procs.append(proc)
      return proc
    if cmd_tuple[0] == str(shell_bin):
      return child_proc
    proc = _FakeProcess(StringIO(), StringIO(), exit_code=0)
    transient_procs.append(proc)
    return proc

  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(
      watch.concurrent.futures,
      'ThreadPoolExecutor',
      single_outer_executor,
    )
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    ok = watch._run_watch_iteration(state, ['core/src/lib.rs'])
    watch._shutdown_watch(state)
    assert ok
    assert executor_max_workers == [1, None]
    assert not state.first_rust_run
    assert state.active_processes == set()
  assert all(p.stdout.closed and p.stderr.closed for p in transient_procs)
  assert child_proc.stdout.closed and child_proc.stderr.closed
  assert {cmd for cmd, _ in popen_calls} == {
    ('cargo', 'fmt', '--', '--check'),
    (
      'cargo',
      'build',
      '--bins',
      '--tests',
      '--message-format=json-diagnostic-rendered-ansi',
    ),
    clippy_cmd,
    ('/virtual/repo/target/debug/deps/core_test-1',),
    (str(shell_bin), 'test', '--watch', 'core'),
  }
  assert {cwd for _, cwd in popen_calls} == {ROOT}
  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running rust-fmt...',
        '[PASS] rust-fmt (0.25s)',
        'Running rust-build...',
        'warning: demo',
        '[PASS] rust-build (0.25s)',
        'Running clippy...',
        '[PASS] clippy (0.25s)',
        'Running btest:core_test...',
        '[PASS] btest:core_test (0.25s)',
        '[test] watching core',
        '[PASS] restart-shell (0.25s)',
        '[PASS] watch-iteration (0.25s)',
      ]
    ),
  )


def test_rust_build_pipeline_reports_missing_boot_shell_binary(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'

  def fake_popen(cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    del cmd
    return _FakeProcess(StringIO(), StringIO(), exit_code=0)

  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    mp.setattr(Path, 'is_file', lambda _self: False)
    ok = watch._run_watch_iteration(state, ['core/src/lib.rs'])
    assert not ok
  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running rust-fmt...',
        '[PASS] rust-fmt (0.25s)',
        'Running rust-build...',
        '[PASS] rust-build (0.25s)',
        '[btest] No new test binaries to run.',
        'Running clippy...',
        '[PASS] clippy (0.25s)',
        f'Could not find boot_shell binary at {shell_bin}',
        '[FAIL] restart-shell (0.25s)',
        '[FAIL] watch-iteration (0.25s)',
      ]
    ),
  )


def test_run_watch_exits_on_root_resolve_oserror(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  with monkeypatch.context() as mp:
    mp.setattr(
      Path,
      'resolve',
      lambda _s, strict=False: (_ for _ in ()).throw(
        PermissionError(13, 'denied')
      ),
    )
    mp.setattr(
      watch.pywatchman,
      'client',
      lambda **_kw: (_ for _ in ()).throw(
        AssertionError('unexpected client')
      ),
    )
    with pytest.raises(SystemExit) as root_exit:
      watch.run_watch(ROOT)

  assert root_exit.value.code == 1
  assert capsys.readouterr() == ('', 'Watch error: [Errno 13] denied\n')


def test_run_watch_exits_on_watchman_client_error(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  ctor_timeouts: list[float] = []
  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)

    def fail_client(*, timeout: float = 0.0) -> object:
      ctor_timeouts.append(timeout)
      raise pywatchman.WatchmanError('socket unavailable')

    mp.setattr(watch.pywatchman, 'client', fail_client)
    with pytest.raises(SystemExit) as ctor_exit:
      watch.run_watch(ROOT)

  assert ctor_timeouts == [60.0]
  assert ctor_exit.value.code == 1
  assert capsys.readouterr() == (
    '',
    'Watchman error: socket unavailable\n',
  )


def test_run_watch_exits_on_invalid_watch_project_reply(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  bad_project_client = _FakeWatchmanClient(watch_project_reply={})
  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(
      watch.pywatchman, 'client', lambda **_kw: bad_project_client
    )
    with pytest.raises(SystemExit) as proj_exit:
      watch.run_watch(ROOT)

  assert proj_exit.value.code == 1
  assert bad_project_client.closed
  assert capsys.readouterr() == (
    '',
    "Watchman error: Watchman 'watch-project' response did not contain a "
    "valid 'watch'\n",
  )


def test_run_watch_exits_on_invalid_clock_reply(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  bad_clock_client = _FakeWatchmanClient(clock_reply={'clock': ''})
  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(watch.pywatchman, 'client', lambda **_kw: bad_clock_client)
    with pytest.raises(SystemExit) as clock_exit:
      watch.run_watch(ROOT)

  assert clock_exit.value.code == 1
  assert bad_clock_client.closed
  assert capsys.readouterr() == (
    '',
    "Watchman error: Watchman 'clock' response did not contain a valid "
    "'clock'\n",
  )


def test_run_watch_startup_failure_recovers_on_subsequent_rust_save(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  shell_available = False
  recovery_cmds: list[tuple[str, ...]] = []
  client = _FakeWatchmanClient(
    receive_steps=[
      pywatchman.SocketTimeout('idle'),
      {
        'subscription': watch._SUBSCRIPTION_NAME,
        'root': '/virtual',
        'files': ['core/src/lib.rs'],
      },
      pywatchman.SocketTimeout('drained'),
      KeyboardInterrupt(),
    ]
  )
  recovery_artifacts = (
    '\n'.join(
      (
        json.dumps(
          {
            'reason': 'compiler-artifact',
            'target': {'name': 'core_unit'},
            'profile': {'test': True},
            'fresh': True,
            'executable': '/virtual/repo/target/debug/deps/core_unit-1',
          }
        ),
        json.dumps(
          {
            'reason': 'compiler-artifact',
            'target': {'name': 'boot_shell'},
            'profile': {'test': False},
            'fresh': False,
            'executable': str(shell_bin),
          }
        ),
      )
    )
    + '\n'
  )

  def fake_popen(cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    nonlocal shell_available
    cmd_tuple = tuple(cmd)
    recovery_cmds.append(cmd_tuple)
    if cmd_tuple[:3] == ('cargo', 'build', '-p'):
      return _FakeProcess(StringIO(), StringIO(), exit_code=1)
    if cmd_tuple[:4] == ('cargo', 'build', '--bins', '--tests'):
      shell_available = True
      return _FakeProcess(
        StringIO(recovery_artifacts), StringIO(), exit_code=0
      )
    if cmd_tuple[0] == str(shell_bin):
      return _FakeProcess(
        StringIO(),
        StringIO(),
        exit_code=0,
        poll_result=None,
        wait_until_stopped=True,
      )
    return _FakeProcess(StringIO(), StringIO(), exit_code=0)

  ctor_timeouts: list[float] = []

  def make_client(*, timeout: float = 0.0) -> _FakeWatchmanClient:
    ctor_timeouts.append(timeout)
    return client

  with monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(
      Path, 'is_file', lambda self: shell_available and self == shell_bin
    )
    mp.setattr(watch.pywatchman, 'client', make_client)
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    watch.run_watch(ROOT)

  assert ctor_timeouts == [60.0]
  assert client.timeouts == [1.0]
  assert client.closed
  assert client.queries == [
    ('capabilityCheck', ()),
    ('watch-project', str(ROOT)),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._SUBSCRIPTION_NAME,
      watch._build_watch_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
  ]
  assert {cmd for cmd in recovery_cmds} == {
    (
      'cargo',
      'build',
      '-p',
      'boot_shell',
      '--message-format=json-diagnostic-rendered-ansi',
    ),
    ('cargo', 'fmt', '--', '--check'),
    (
      'cargo',
      'build',
      '--bins',
      '--tests',
      '--message-format=json-diagnostic-rendered-ansi',
    ),
    tuple(lib.get_cargo_clippy_cmd()),
    ('/virtual/repo/target/debug/deps/core_unit-1',),
    (str(shell_bin), 'test', '--watch', 'core'),
  }
  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running boot-shell-build...',
        '[FAIL] boot-shell-build (0.25s)',
        'Change detected in 1 files...',
        'Running rust-fmt...',
        '[PASS] rust-fmt (0.25s)',
        'Running rust-build...',
        '[PASS] rust-build (0.25s)',
        'Running clippy...',
        '[PASS] clippy (0.25s)',
        'Running btest:core_unit...',
        '[PASS] btest:core_unit (0.25s)',
        '[PASS] restart-shell (0.25s)',
        '[PASS] watch-iteration (0.25s)',
      ]
    ),
  )


def test_run_watch_coalesces_buffered_pdus_and_exits_on_canceled(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  client = _FakeWatchmanClient(
    buffered_pdus=[
      {'subscription': watch._SUBSCRIPTION_NAME, 'files': ['zero/a.py']},
      {'subscription': watch._SUBSCRIPTION_NAME, 'files': ['zero/b.py']},
    ],
    receive_steps=[
      pywatchman.SocketTimeout('drained'),
      {
        'subscription': watch._SUBSCRIPTION_NAME,
        'root': '/virtual',
        'canceled': True,
      },
      pywatchman.SocketTimeout('drained'),
    ],
  )
  iteration_batches: list[tuple[str, ...]] = []

  with monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
    mp.setattr(
      watch,
      '_run_cargo_build',
      lambda *_a, **_kw: watch._CargoBuildSummary((), False),
    )
    mp.setattr(watch, '_restart_boot_shell', lambda _s: True)
    mp.setattr(
      watch,
      '_run_watch_iteration',
      lambda _s, files: iteration_batches.append(tuple(files)) or True,
    )
    with pytest.raises(SystemExit) as cancel_exit:
      watch.run_watch(ROOT)

  assert cancel_exit.value.code == 1
  assert client.closed
  assert (
    client.getSubscription(
      watch._SUBSCRIPTION_NAME, remove=True, root='/virtual'
    )
    is None
  )
  assert iteration_batches == [('zero/a.py', 'zero/b.py')]
  assert capsys.readouterr() == (
    'Change detected in 2 files...\n',
    f"Watchman error: subscription '{watch._SUBSCRIPTION_NAME}' was "
    'cancelled\n',
  )


def test_run_watch_exits_on_wakeup_socketpair_oserror(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(
      watch.socket,
      'socketpair',
      lambda: (_ for _ in ()).throw(OSError(24, 'too many open files')),
    )
    with pytest.raises(SystemExit) as sock_exit:
      watch.run_watch(ROOT)

  assert sock_exit.value.code == 1
  assert capsys.readouterr() == (
    '',
    'Watch error: [Errno 24] too many open files\n',
  )

  closed_flags: list[bool] = []

  class _FailSetBlockingSocket:
    def __init__(self, *, fail_on_setblocking: bool) -> None:
      self.fail_on_setblocking = fail_on_setblocking
      self.closed = False

    def setblocking(self, _flag: bool) -> None:
      if self.fail_on_setblocking:
        raise OSError(22, 'invalid argument')

    def close(self) -> None:
      self.closed = True
      closed_flags.append(self.closed)

  s_r = _FailSetBlockingSocket(fail_on_setblocking=True)
  s_w = _FailSetBlockingSocket(fail_on_setblocking=False)
  with monkeypatch.context() as mp:
    mp.setattr(watch.socket, 'socketpair', lambda: (s_r, s_w))
    with pytest.raises(OSError, match='invalid argument'):
      watch._create_wakeup_pair()

  assert closed_flags == [True, True]


def test_run_watch_coalesces_socketpair_bser_backlog_into_one_iteration(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  client_sock, peer_sock = socket.socketpair(
    socket.AF_UNIX, socket.SOCK_STREAM
  )
  client = _socketpair_watchman_client(client_sock)
  iteration_batches: list[tuple[str, ...]] = []

  def record_and_stop(
    _state: watch._WatchRuntime, files: Iterable[str]
  ) -> bool:
    iteration_batches.append(tuple(files))
    raise KeyboardInterrupt()

  try:
    with monkeypatch.context() as mp:
      mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
      mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
      mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
      mp.setattr(
        watch, '_subscribe_watch', lambda _c, _r: ('/virtual', None)
      )
      mp.setattr(
        watch,
        '_run_cargo_build',
        lambda *_a, **_kw: watch._CargoBuildSummary((), False),
      )
      mp.setattr(watch, '_restart_boot_shell', lambda _s: True)
      mp.setattr(watch, '_run_watch_iteration', record_and_stop)
      peer_sock.sendall(
        bser.dumps({'log': 'watchman started\n'})
        + bser.dumps(
          {
            'subscription': watch._SUBSCRIPTION_NAME,
            'root': '/virtual',
            'files': ['zero/a.py'],
          }
        )
        + bser.dumps(
          {
            'subscription': watch._SUBSCRIPTION_NAME,
            'root': '/virtual',
            'files': ['zero/b.py'],
          }
        )
      )
      watch.run_watch(ROOT)
  finally:
    peer_sock.close()

  assert client.logs == []
  assert iteration_batches == [('zero/a.py', 'zero/b.py')]
  assert capsys.readouterr() == ('Change detected in 2 files...\n', '')


def test_run_watch_exits_on_malformed_bser_frame_over_socketpair(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  client_sock, peer_sock = socket.socketpair(
    socket.AF_UNIX, socket.SOCK_STREAM
  )
  client = _socketpair_watchman_client(client_sock)
  try:
    with monkeypatch.context() as mp:
      mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
      mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
      mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
      mp.setattr(
        watch, '_subscribe_watch', lambda _c, _r: ('/virtual', None)
      )
      mp.setattr(
        watch,
        '_run_cargo_build',
        lambda *_a, **_kw: watch._CargoBuildSummary((), False),
      )
      mp.setattr(watch, '_restart_boot_shell', lambda _s: True)
      peer_sock.sendall(b'\x00\x01\xff' * 6)
      with pytest.raises(SystemExit) as bser_exit:
        watch.run_watch(ROOT)
  finally:
    peer_sock.close()

  assert bser_exit.value.code == 1
  assert capsys.readouterr() == (
    '',
    'Watchman error: invalid bser int encoding 0xffffffff\n',
  )


def test_reaper_wakes_idle_select_and_arms_recovery_before_exit_log(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  client_sock, peer_sock = socket.socketpair(
    socket.AF_UNIX, socket.SOCK_STREAM
  )
  client = _socketpair_watchman_client(client_sock)
  queries: list[tuple[object, ...]] = []
  children: list[_FakeProcess] = []
  real_select = watch.select.select
  select_calls = 0
  clock_calls = 0
  wake_selected: list[bool] = []
  order_log: list[str] = []
  original_emit = watch._emit_line

  def track_emit(
    rt: watch._WatchRuntime,
    text: str,
    *,
    colour: str | None = None,
    bold: bool = False,
    err: bool = False,
    nl: bool = True,
  ) -> None:
    if 'boot_shell watcher exited' in text:
      order_log.append(
        f'emit:{threading.current_thread() is rt.main_thread}'
      )
    original_emit(rt, text, colour=colour, bold=bold, err=err, nl=nl)

  def fake_popen(cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    assert tuple(cmd) == (str(shell_bin), 'test', '--watch', 'core')
    child = _FakeProcess(
      _TrackedStringIO(),
      _TrackedStringIO(),
      exit_code=1 if not children else 0,
      poll_result=None,
      wait_until_stopped=True,
    )
    children.append(child)
    return child

  def fake_query(*args: object) -> object:
    nonlocal clock_calls
    queries.append(args)
    if args[0] == 'clock':
      clock_calls += 1
      return {'clock': f'c:{clock_calls * 10}:1'}
    if (
      args[0] == 'subscribe'
      and args[2] == watch._PENTA_RECOVERY_SUBSCRIPTION
    ):
      order_log.append('subscribe-recovery')
      peer_sock.sendall(
        bser.dumps(
          {
            'subscription': watch._PENTA_RECOVERY_SUBSCRIPTION,
            'root': '/virtual',
            'files': ['core/a.penta'],
          }
        )
      )
    elif args[0] == 'unsubscribe':
      order_log.append('unsubscribe-recovery')
    return {}

  def fake_select(
    rlist: Sequence[object],
    wlist: Sequence[object],
    xlist: Sequence[object],
    timeout: float | None = None,
  ) -> tuple[list[object], list[object], list[object]]:
    nonlocal select_calls
    if len(rlist) == 2 and timeout == 1.0:
      select_calls += 1
      if select_calls == 1:
        children[0].poll_result = 1
        children[0].stop_event.set()
        readable, writable, errored = real_select(rlist, wlist, xlist, 5.0)
        wake_selected.append(readable == [rlist[1]])
        return readable, writable, errored
      if select_calls == 2:
        return real_select(rlist, wlist, xlist, 5.0)
      if select_calls == 3:
        raise KeyboardInterrupt()
    return real_select(rlist, wlist, xlist, timeout)

  try:
    with monkeypatch.context() as mp:
      _install_constant_clock(mp)
      mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
      mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
      mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
      mp.setattr(
        watch, '_subscribe_watch', lambda _c, _r: ('/virtual', 'repo')
      )
      mp.setattr(watch, '_emit_line', track_emit)
      mp.setattr(client, 'query', fake_query)
      mp.setattr(watch.select, 'select', fake_select)
      mp.setattr(
        watch,
        '_run_cargo_build',
        lambda *_a, **_kw: watch._CargoBuildSummary((), False),
      )
      mp.setattr(watch.subprocess, 'Popen', fake_popen)
      watch.run_watch(ROOT)
  finally:
    peer_sock.close()
    client_sock.close()

  assert len(children) == 2
  assert wake_selected == [True]
  assert order_log == [
    'subscribe-recovery',
    'emit:True',
    'unsubscribe-recovery',
  ]
  assert queries == [
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      watch._build_penta_recovery_subscription(
        since='c:10:1', relative_root='repo'
      ),
    ),
    ('unsubscribe', '/virtual', watch._PENTA_RECOVERY_SUBSCRIPTION),
  ]
  assert capsys.readouterr() == (
    '[PASS] restart-shell (0.25s)\n'
    '[test] boot_shell watcher exited (code 1)\n'
    '[PASS] restart-shell (0.25s)\n',
    '',
  )


def test_penta_crash_and_fix_during_parent_iteration_restarts_on_next_turn(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  children: list[_FakeProcess] = []
  recovery_armed = threading.Event()
  exit_logged = threading.Event()
  orig_emit_line = watch._emit_line

  def track_emit_line(
    runtime: watch._WatchRuntime,
    text: str,
    *,
    colour: str | None = None,
    bold: bool = False,
    err: bool = False,
    nl: bool = True,
  ) -> None:
    orig_emit_line(runtime, text, colour=colour, bold=bold, err=err, nl=nl)
    if text == '[test] boot_shell watcher exited (code 1)':
      assert recovery_armed.is_set()
      exit_logged.set()

  def fake_popen(cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    cmd_tuple = tuple(cmd)
    if cmd_tuple[0] == str(shell_bin):
      child = _FakeProcess(
        _TrackedStringIO(),
        _TrackedStringIO(),
        exit_code=1 if not children else 0,
        poll_result=None,
        wait_until_stopped=True,
      )
      children.append(child)
      return child
    if cmd_tuple == ('dprint', 'check'):

      def wait_crash_and_fix() -> None:
        children[0].poll_result = 1
        children[0].stop_event.set()
        assert recovery_armed.wait(timeout=2.0)
        assert exit_logged.wait(timeout=2.0)
        client.receive_steps.extend(
          [
            {
              'subscription': watch._PENTA_RECOVERY_SUBSCRIPTION,
              'root': '/virtual',
              'files': ['core/a.penta'],
            },
            KeyboardInterrupt(),
          ]
        )

      return _FakeProcess(
        _TrackedStringIO(),
        _TrackedStringIO(),
        exit_code=0,
        on_wait_enter=wait_crash_and_fix,
      )
    return _FakeProcess(
      _TrackedStringIO(), _TrackedStringIO(), exit_code=0
    )

  class _RecoveryHookClient(_FakeWatchmanClient):
    def query(self, *args: object) -> object:
      res = super().query(*args)
      if (
        args[0] == 'subscribe'
        and args[2] == watch._PENTA_RECOVERY_SUBSCRIPTION
      ):
        recovery_armed.set()
      return res

  client = _RecoveryHookClient(
    receive_steps=[
      {
        'subscription': watch._SUBSCRIPTION_NAME,
        'root': '/virtual',
        'files': ['a.json'],
      },
    ]
  )

  with monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(watch, '_emit_line', track_emit_line)
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
    mp.setattr(
      watch,
      '_run_cargo_build',
      lambda *_a, **_kw: watch._CargoBuildSummary((), False),
    )
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    watch.run_watch(ROOT)

  assert len(children) == 2
  assert client.closed
  assert client.queries == [
    ('capabilityCheck', ()),
    ('watch-project', os.fspath(ROOT)),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._SUBSCRIPTION_NAME,
      watch._build_watch_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      watch._build_penta_recovery_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
    ('unsubscribe', '/virtual', watch._PENTA_RECOVERY_SUBSCRIPTION),
  ]
  assert capsys.readouterr() == (
    '[PASS] restart-shell (0.25s)\n'
    'Change detected in 1 files...\n'
    'Running dprint...\n'
    '[test] boot_shell watcher exited (code 1)\n'
    '[PASS] dprint (0.25s)\n'
    '[PASS] watch-iteration (0.25s)\n'
    '[PASS] restart-shell (0.25s)\n',
    '',
  )


def test_combined_rust_and_penta_batch_restarts_boot_shell_only_once(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  children: list[_FakeProcess] = []
  rebuild_stdout = (
    json.dumps(
      {
        'reason': 'compiler-artifact',
        'target': {'name': 'boot_shell'},
        'profile': {'test': False},
        'fresh': False,
        'executable': str(shell_bin),
      }
    )
    + '\n'
  )

  def fake_popen(cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    cmd_tuple = tuple(cmd)
    if cmd_tuple[0] == str(shell_bin):
      is_second = len(children) == 1
      child = _FakeProcess(
        _TrackedStringIO(),
        _TrackedStringIO(),
        exit_code=2 if is_second else 1,
        poll_result=2 if is_second else None,
        wait_until_stopped=not is_second,
      )
      children.append(child)
      return child
    if cmd_tuple[:4] == ('cargo', 'build', '--bins', '--tests'):
      return _FakeProcess(
        _TrackedStringIO(rebuild_stdout), _TrackedStringIO(), exit_code=0
      )
    return _FakeProcess(
      _TrackedStringIO(), _TrackedStringIO(), exit_code=0
    )

  class _ArmThenCrashClient(_FakeWatchmanClient):
    def receive(self) -> object:
      if len(self.receive_steps) == 3:
        children[0].poll_result = 1
        children[0].stop_event.set()
      return super().receive()

  client = _ArmThenCrashClient(
    receive_steps=[
      pywatchman.SocketTimeout('idle'),
      [
        {
          'subscription': watch._SUBSCRIPTION_NAME,
          'root': '/virtual',
          'files': ['core/src/lib.rs'],
        },
        {
          'subscription': watch._PENTA_RECOVERY_SUBSCRIPTION,
          'root': '/virtual',
          'files': ['core/broken.penta'],
        },
      ],
      KeyboardInterrupt(),
    ]
  )

  with monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    watch.run_watch(ROOT)

  assert len(children) == 2
  assert client.closed
  recovery_sub = watch._build_penta_recovery_subscription(
    since='c:42:1', relative_root='repo'
  )
  assert client.queries == [
    ('capabilityCheck', ()),
    ('watch-project', os.fspath(ROOT)),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._SUBSCRIPTION_NAME,
      watch._build_watch_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      recovery_sub,
    ),
    ('unsubscribe', '/virtual', watch._PENTA_RECOVERY_SUBSCRIPTION),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      recovery_sub,
    ),
  ]
  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running boot-shell-build...',
        '[PASS] boot-shell-build (0.25s)',
        '[PASS] restart-shell (0.25s)',
        '[test] boot_shell watcher exited (code 1)',
        'Change detected in 1 files...',
        'Running rust-fmt...',
        '[PASS] rust-fmt (0.25s)',
        'Running rust-build...',
        '[PASS] rust-build (0.25s)',
        '[btest] No new test binaries to run.',
        'Running clippy...',
        '[PASS] clippy (0.25s)',
        '[PASS] restart-shell (0.25s)',
        '[test] boot_shell watcher exited (code 2)',
        '[PASS] watch-iteration (0.25s)',
      ]
    ),
  )


def test_failed_rust_pipeline_restart_recovers_on_next_penta_save(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  shell_present = False
  children: list[_FakeProcess] = []

  def fake_popen(cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    cmd_tuple = tuple(cmd)
    if cmd_tuple[:3] == ('cargo', 'build', '-p'):
      return _FakeProcess(
        _TrackedStringIO(), _TrackedStringIO(), exit_code=1
      )
    if cmd_tuple[0] == str(shell_bin):
      child = _FakeProcess(
        _TrackedStringIO(),
        _TrackedStringIO(),
        exit_code=0,
        poll_result=None,
        wait_until_stopped=True,
      )
      children.append(child)
      return child
    return _FakeProcess(
      _TrackedStringIO(), _TrackedStringIO(), exit_code=0
    )

  class _DelayedShellBinaryClient(_FakeWatchmanClient):
    def receive(self) -> object:
      nonlocal shell_present
      if len(self.receive_steps) == 2:
        shell_present = True
      return super().receive()

  client = _DelayedShellBinaryClient(
    receive_steps=[
      {
        'subscription': watch._SUBSCRIPTION_NAME,
        'root': '/virtual',
        'files': ['core/src/lib.rs'],
      },
      {
        'subscription': watch._PENTA_RECOVERY_SUBSCRIPTION,
        'root': '/virtual',
        'files': ['core/a.penta'],
      },
      KeyboardInterrupt(),
    ]
  )

  with monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(
      Path, 'is_file', lambda self: shell_present and self == shell_bin
    )
    mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    watch.run_watch(ROOT)

  assert len(children) == 1
  assert client.closed
  assert client.queries == [
    ('capabilityCheck', ()),
    ('watch-project', os.fspath(ROOT)),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._SUBSCRIPTION_NAME,
      watch._build_watch_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      watch._build_penta_recovery_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
    ('unsubscribe', '/virtual', watch._PENTA_RECOVERY_SUBSCRIPTION),
  ]
  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running boot-shell-build...',
        '[FAIL] boot-shell-build (0.25s)',
        'Change detected in 1 files...',
        'Running rust-fmt...',
        '[PASS] rust-fmt (0.25s)',
        'Running rust-build...',
        '[PASS] rust-build (0.25s)',
        '[btest] No new test binaries to run.',
        'Running clippy...',
        '[PASS] clippy (0.25s)',
        f'Could not find boot_shell binary at {shell_bin}',
        '[FAIL] restart-shell (0.25s)',
        '[FAIL] watch-iteration (0.25s)',
        '[PASS] restart-shell (0.25s)',
      ]
    ),
  )


def test_reaper_emits_exit_log_strictly_before_concurrent_restart(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  exited_child = _FakeProcess(
    _TrackedStringIO(),
    _TrackedStringIO(),
    exit_code=1,
    poll_result=None,
    wait_until_stopped=True,
  )
  restarted_child = _FakeProcess(
    _TrackedStringIO(),
    _TrackedStringIO(),
    exit_code=0,
    poll_result=None,
    wait_until_stopped=True,
  )
  children = [exited_child, restarted_child]
  saw_exit_emit_before_spawn = False
  original_emit = watch._emit_line

  def check_exit_emit(
    rt: watch._WatchRuntime,
    text: str,
    *,
    colour: str | None = None,
    bold: bool = False,
    err: bool = False,
    nl: bool = True,
  ) -> None:
    nonlocal saw_exit_emit_before_spawn
    if 'boot_shell watcher exited' in text:
      saw_exit_emit_before_spawn = (
        rt.child_process is None and len(children) == 1
      )
    original_emit(rt, text, colour=colour, bold=bold, err=err, nl=nl)

  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch, '_emit_line', check_exit_emit)
    mp.setattr(
      watch.subprocess, 'Popen', lambda *_a, **_kw: children.pop(0)
    )
    assert watch._restart_boot_shell(state)
    exited_child.poll_result = 1
    exited_child.stop_event.set()
    assert watch._restart_boot_shell(state)
    assert state.recovery_state is watch._RecoveryState.DISARMED
    assert exited_child.stdout.closed and exited_child.stderr.closed

  assert saw_exit_emit_before_spawn
  assert capsys.readouterr() == (
    '[PASS] restart-shell (0.25s)\n'
    '[test] boot_shell watcher exited (code 1)\n'
    '[PASS] restart-shell (0.25s)\n',
    '',
  )


def test_ctrl_c_in_watchman_wait_closes_client_cleanly(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  client = _FakeWatchmanClient(receive_steps=[KeyboardInterrupt()])
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  with monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'resolve', lambda _s, strict=False: ROOT)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch.pywatchman, 'client', lambda **_kw: client)
    mp.setattr(watch, '_run_cargo_build', lambda *_a, **_kw: None)
    watch.run_watch(ROOT)

  assert client.closed
  assert capsys.readouterr() == ('', '')


def test_abort_active_processes_unblocks_waiting_disarm_event(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  disarm_result: list[bool] = []
  disarm_waiting = threading.Event()
  orig_nudge = watch._nudge_wakeup_locked

  def signal_on_disarm(runtime: watch._WatchRuntime) -> None:
    orig_nudge(runtime)
    if runtime.disarm_recovery_event is not None:
      disarm_waiting.set()

  with _runtime() as state:
    state.recovery_state = watch._RecoveryState.SUBSCRIBED

    def wait_disarm() -> None:
      with monkeypatch.context() as mp:
        mp.setattr(watch, '_nudge_wakeup_locked', signal_on_disarm)
        mp.setattr(Path, 'is_file', lambda _self: True)
        disarm_result.append(watch._restart_boot_shell(state))

    worker = threading.Thread(target=wait_disarm, daemon=True)
    worker.start()
    assert disarm_waiting.wait(timeout=2.0)
    watch._abort_active_processes(state)
    worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert disarm_result == [False]
    assert state.should_stop
  assert capsys.readouterr() == ('', '')


def test_restart_missing_binary_while_subscribed_avoids_pending_arm(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  client = _FakeWatchmanClient()
  with _runtime(client) as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'is_file', lambda _self: False)
    state.recovery_state = watch._RecoveryState.SUBSCRIBED
    assert not watch._restart_boot_shell(state)
    assert state.recovery_state is watch._RecoveryState.SUBSCRIBED
    assert not watch._has_pending_wake_state(state)
    assert client.queries == []

  assert capsys.readouterr() == (
    f'Could not find boot_shell binary at {shell_bin}\n'
    '[FAIL] restart-shell (0.25s)\n',
    '',
  )


def test_service_recovery_subscribes_before_logging_exit_on_race(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  client = _FakeWatchmanClient()

  class _FlipAfterFirstPollProcess(_FakeProcess):
    def __init__(self) -> None:
      super().__init__(
        _TrackedStringIO(),
        _TrackedStringIO(),
        exit_code=1,
        poll_result=None,
        wait_until_stopped=True,
      )
      self.poll_calls = 0

    def poll(self) -> int | None:
      self.poll_calls += 1
      res = super().poll()
      if self.poll_calls == 1:
        self.poll_result = 1
        self.stop_event.set()
      return res

  child = _FlipAfterFirstPollProcess()
  original_emit = watch._emit_line
  events: list[str] = []

  def record_emit(
    rt: watch._WatchRuntime,
    text: str,
    *,
    colour: str | None = None,
    bold: bool = False,
    err: bool = False,
    nl: bool = True,
  ) -> None:
    if 'exited' in text:
      events.append(f'emit:{rt.recovery_state.value}:{text}')
    original_emit(rt, text, colour=colour, bold=bold, err=err, nl=nl)

  with _runtime(client) as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch, '_emit_line', record_emit)
    mp.setattr(watch.subprocess, 'Popen', lambda *_a, **_kw: child)
    assert watch._restart_boot_shell(state)
    watch._service_watch_recovery_on_main(state)
    assert state.recovery_state is watch._RecoveryState.SUBSCRIBED

  assert child.poll_calls == 2
  assert events == [
    'emit:subscribed:[test] boot_shell watcher exited (code 1)'
  ]
  assert client.queries == [
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      watch._build_penta_recovery_subscription(
        since='c:42:1', relative_root='repo'
      ),
    ),
  ]
  assert capsys.readouterr() == (
    '[PASS] restart-shell (0.25s)\n'
    '[test] boot_shell watcher exited (code 1)\n',
    '',
  )


def test_concurrent_restart_during_subscribe_unsubscribes_before_spawn(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  shell_bin = ROOT / 'target' / 'debug' / 'boot_shell'
  exited_child = _FakeProcess(
    _TrackedStringIO(),
    _TrackedStringIO(),
    exit_code=1,
    poll_result=None,
    wait_until_stopped=True,
  )
  restarted_child = _FakeProcess(
    _TrackedStringIO(),
    _TrackedStringIO(),
    exit_code=0,
    poll_result=None,
    wait_until_stopped=True,
  )
  children = [exited_child, restarted_child]
  subscribe_entered = threading.Event()
  worker_waiting_disarm = threading.Event()
  spawn_snapshot: list[
    tuple[watch._RecoveryState, int | None, list[tuple[object, ...]]]
  ] = []
  state_holder: list[watch._WatchRuntime] = []

  class _PauseInSubscribeClient(_FakeWatchmanClient):
    def query(self, *args: object) -> object:
      if (
        args[0] == 'subscribe'
        and args[2] == watch._PENTA_RECOVERY_SUBSCRIPTION
      ):
        assert (
          state_holder[0].recovery_state
          is watch._RecoveryState.SUBSCRIBING
        )
        subscribe_entered.set()
        assert worker_waiting_disarm.wait(timeout=2.0)
      return super().query(*args)

  client = _PauseInSubscribeClient()
  orig_nudge = watch._nudge_wakeup_locked

  def signal_worker_disarm(runtime: watch._WatchRuntime) -> None:
    orig_nudge(runtime)
    if runtime.disarm_recovery_event is not None:
      worker_waiting_disarm.set()

  def fake_popen(_cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    proc = children.pop(0)
    if proc is restarted_child:
      rt = state_holder[0]
      spawn_snapshot.append(
        (rt.recovery_state, rt.pending_exit_code, list(client.queries))
      )
    return proc

  worker_result: list[bool] = []
  with _runtime(client) as state, monkeypatch.context() as mp:
    state_holder.append(state)
    _install_constant_clock(mp)
    mp.setattr(Path, 'is_file', lambda self: self == shell_bin)
    mp.setattr(watch, '_nudge_wakeup_locked', signal_worker_disarm)
    mp.setattr(watch.subprocess, 'Popen', fake_popen)

    assert watch._restart_boot_shell(state)
    exited_child.poll_result = 1
    exited_child.stop_event.set()
    assert not watch._ensure_reaped_if_exited(state)
    assert state.recovery_state is watch._RecoveryState.PENDING_ARM

    def run_concurrent_restart() -> None:
      assert subscribe_entered.wait(timeout=2.0)
      worker_result.append(watch._restart_boot_shell(state))

    worker = threading.Thread(target=run_concurrent_restart, daemon=True)
    worker.start()
    watch._service_watch_recovery_on_main(state)
    worker.join(timeout=2.0)
    assert not worker.is_alive()
    assert worker_result == [True]
    assert state.recovery_state is watch._RecoveryState.DISARMED

  recovery_sub = watch._build_penta_recovery_subscription(
    since='c:42:1', relative_root='repo'
  )
  expected_queries = [
    ('clock', '/virtual'),
    (
      'subscribe',
      '/virtual',
      watch._PENTA_RECOVERY_SUBSCRIPTION,
      recovery_sub,
    ),
    ('unsubscribe', '/virtual', watch._PENTA_RECOVERY_SUBSCRIPTION),
  ]
  assert spawn_snapshot == [
    (watch._RecoveryState.DISARMED, None, expected_queries)
  ]
  assert client.queries == expected_queries
  assert capsys.readouterr() == (
    '[PASS] restart-shell (0.25s)\n'
    '[test] boot_shell watcher exited (code 1)\n'
    '[PASS] restart-shell (0.25s)\n',
    '',
  )


def test_keyboard_interrupt_mid_iteration_aborts_blocked_sibling_processes(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  spawned: list[_FakeProcess] = []
  sibling_procs: list[_FakeProcess] = []
  tracked_stderrs: list[_TrackedStringIO] = []
  wait_lock = threading.Lock()
  waiting_count = 0
  three_waiting = threading.Event()
  interrupt_proc_holder: list[_FakeProcess] = []

  def on_sibling_wait() -> None:
    nonlocal waiting_count
    with wait_lock:
      waiting_count += 1
      if waiting_count == 3:
        three_waiting.set()

  def on_interrupt_wait() -> None:
    three_waiting.wait(timeout=2.0)

  def fake_popen(_cmd: Sequence[str], **_kwargs: object) -> _FakeProcess:
    with wait_lock:
      index = len(spawned)
      err_stream = _TrackedStringIO()
      tracked_stderrs.append(err_stream)
      if index < 3:
        proc = _FakeProcess(
          _TrackedStringIO(),
          err_stream,
          poll_result=None,
          wait_until_stopped=True,
          on_wait_enter=on_sibling_wait,
        )
        sibling_procs.append(proc)
      else:
        proc = _FakeProcess(
          _TrackedStringIO(),
          err_stream,
          poll_result=None,
          wait_outcomes=[KeyboardInterrupt(), -15],
          on_wait_enter=on_interrupt_wait,
        )
        interrupt_proc_holder.append(proc)
      spawned.append(proc)
      return proc

  with _runtime() as state, monkeypatch.context() as mp:
    _install_constant_clock(mp)
    mp.setattr(
      watch.lib,
      'nix_files',
      lambda root: ([str(ROOT / 'flake.nix')] if root == ROOT else []),
    )
    mp.setattr(watch.subprocess, 'Popen', fake_popen)
    with pytest.raises(KeyboardInterrupt):
      watch._run_watch_iteration(state, ['flake.nix', 'other/mod.py'])

    for err_stream in tracked_stderrs:
      err_stream.closed_event.wait(timeout=2.0)

    assert len(spawned) == 4
    assert len(sibling_procs) == 3
    assert state.should_stop
    assert state.active_processes == set()
  assert all(p.stdout.closed and p.stderr.closed for p in spawned)
  assert all(
    p.actions == ['wait', 'terminate', 'wait:2'] for p in sibling_procs
  )
  assert interrupt_proc_holder[0].actions == [
    'wait',
    'terminate',
    'wait:2',
  ]
  captured = capsys.readouterr()
  assert (captured.err, sorted(captured.out.splitlines())) == (
    '',
    sorted(
      [
        'Running nix-fmt...',
        'Running py-fmt...',
        'Running py-lint...',
        'Running type...',
      ]
    ),
  )


def test_shutdown_watch_terminates_kills_and_blocks_restart(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
) -> None:
  child = _FakeProcess(
    _TrackedStringIO(),
    _TrackedStringIO(),
    wait_outcomes=[watch.subprocess.TimeoutExpired(['boot_shell'], 2), -9],
    poll_result=None,
  )
  client = _FakeWatchmanClient()

  with _runtime(client) as state, monkeypatch.context() as mp:
    state.child_process = child
    mp.setattr(Path, 'is_file', lambda _self: True)
    watch._shutdown_watch(state)
    assert not watch._restart_boot_shell(state)
    assert state.should_stop
    assert state.child_process is None

  assert client.closed
  assert child.actions == ['terminate', 'wait:2', 'kill', 'wait']
  assert child.stdout.closed and child.stderr.closed
  assert capsys.readouterr() == ('', '')


def test_shutdown_watch_handles_already_exited_child(
  capsys: CaptureFixture[str],
) -> None:
  exited_child = _FakeProcess(
    _TrackedStringIO(),
    _TrackedStringIO(),
    terminate_error=ProcessLookupError(3, 'already exited'),
    poll_result=1,
  )

  with _runtime() as exited_state:
    exited_state.child_process = exited_child
    watch._shutdown_watch(exited_state)
    assert exited_state.child_process is None

  assert exited_child.actions == ['terminate', 'wait:2']
  assert exited_child.stdout.closed and exited_child.stderr.closed
  assert capsys.readouterr() == ('', '')
