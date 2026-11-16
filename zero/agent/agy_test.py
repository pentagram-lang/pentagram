import json
import os
import re
import signal
import stat
import subprocess
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
import pytest

from zero.agent import agy, common
from zero.agent.common import JsonObject

HOME = Path('/home/operator')
CONFIG = HOME / '.gemini' / 'config'
PROJECT_ROOT = Path('/work/pentagram')
SYSTEM_FILE = PROJECT_ROOT / 'sys.md'
RUNTIME_DIR = Path('/runtime/pentagram-agy-0')
MODEL = 'gemini-3.8-flash-high'
SYSTEM_CONTENT = '# Pentagram agent system\n'

EXPECTED_ADAPTER = (
  '---\n'
  'name: pentagram\n'
  'description: Pentagram engineering agent governed by the '
  'repository-root system contract.\n'
  'tools:\n'
  '  - ask_question\n'
  '  - define_subagent\n'
  '  - edit_file\n'
  '  - generate_image\n'
  '  - invoke_subagent\n'
  '  - manage_subagents\n'
  '  - manage_task\n'
  '  - read_file\n'
  '  - run_command\n'
  '  - run_workflow\n'
  '  - schedule\n'
  '  - search_web\n'
  '  - send_message\n'
  '  - swarm_manage\n'
  '  - swarm_post_message\n'
  '  - swarm_read_board\n'
  '  - swarm_wait\n'
  '  - write_file\n'
  'commandExecutionPolicy: eager\n'
  '---\n\n'
  '# Pentagram agent system\n'
)


@dataclass(frozen=True, slots=True)
class _FakeNode:
  mode: int
  ino: int
  dev: int = 1
  content: str | Exception | None = None
  target: Path | None = None
  children: tuple[tuple[str, Path], ...] = ()
  scandir_error: OSError | None = None

  def to_stat_result(self) -> os.stat_result:
    return os.stat_result(
      (self.mode, self.ino, self.dev, 1, 0, 0, 0, 0, 0, 0)
    )


class _FakeDirEntry:
  def __init__(
    self, name: str, path: Path, nodes: Mapping[Path, _FakeNode]
  ) -> None:
    self.name = name
    self.path = str(path)
    self._path = path
    self._nodes = nodes

  def is_symlink(self) -> bool:
    return stat.S_ISLNK(self._nodes[self._path].mode)

  def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
    node = self._nodes[self._path]
    if not follow_symlinks or node.target is None:
      return node.to_stat_result()
    target = self._nodes.get(node.target)
    if target is None:
      raise FileNotFoundError(
        2, 'No such file or directory', str(self._path)
      )
    return target.to_stat_result()


@contextmanager
def _scandir_context(
  items: list[_FakeDirEntry],
) -> Iterator[Iterator[_FakeDirEntry]]:
  yield iter(items)


def _install_virtual_fs(
  mp: pytest.MonkeyPatch,
  *,
  files: Mapping[Path, str | Exception],
  symlinks: Mapping[Path, Path] | None = None,
  extra_dirs: Mapping[Path, OSError | None] | None = None,
  others: Sequence[Path] = (),
  read_counts: dict[Path, int] | None = None,
) -> None:
  nodes: dict[Path, _FakeNode] = {}
  dir_children: dict[Path, dict[str, Path]] = {}
  next_ino = 100

  def alloc_ino() -> int:
    nonlocal next_ino
    next_ino += 1
    return next_ino

  def ensure_dir(
    directory: Path, scandir_error: OSError | None = None
  ) -> None:
    if directory not in nodes:
      nodes[directory] = _FakeNode(
        stat.S_IFDIR | 0o755,
        ino=alloc_ino(),
        scandir_error=scandir_error,
      )
      dir_children.setdefault(directory, {})
    for parent in directory.parents:
      if parent == directory:
        continue
      if parent not in nodes:
        nodes[parent] = _FakeNode(stat.S_IFDIR | 0o755, ino=alloc_ino())
        dir_children.setdefault(parent, {})
    for child in (directory, *directory.parents):
      parent = child.parent
      if child != parent:
        dir_children.setdefault(parent, {})[child.name] = child

  ensure_dir(HOME)
  ensure_dir(PROJECT_ROOT)
  for directory, scandir_err in (extra_dirs or {}).items():
    ensure_dir(directory, scandir_error=scandir_err)

  for path in others:
    ensure_dir(path.parent)
    nodes[path] = _FakeNode(stat.S_IFIFO | 0o644, ino=alloc_ino())
    dir_children.setdefault(path.parent, {})[path.name] = path

  for path, content in files.items():
    ensure_dir(path.parent)
    nodes[path] = _FakeNode(
      stat.S_IFREG | 0o644, ino=alloc_ino(), content=content
    )
    dir_children.setdefault(path.parent, {})[path.name] = path

  for path, target in (symlinks or {}).items():
    ensure_dir(path.parent)
    nodes[path] = _FakeNode(
      stat.S_IFLNK | 0o777, ino=alloc_ino(), target=target
    )
    dir_children.setdefault(path.parent, {})[path.name] = path

  for directory, children in dir_children.items():
    existing = nodes[directory]
    nodes[directory] = _FakeNode(
      existing.mode,
      ino=existing.ino,
      scandir_error=existing.scandir_error,
      children=tuple(sorted(children.items())),
    )

  link_map = symlinks or {}

  def resolve_path(path: Path) -> Path:
    parts = path.parts
    resolved = Path(parts[0])
    for part in parts[1:]:
      resolved = resolved / part
      if resolved in link_map:
        resolved = link_map[resolved]
    return resolved

  def fake_lstat(self: Path) -> os.stat_result:
    node = nodes.get(self)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(self))
    return node.to_stat_result()

  def fake_stat(
    self: Path, *, follow_symlinks: bool = True
  ) -> os.stat_result:
    key = resolve_path(self) if follow_symlinks else self
    node = nodes.get(key)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(self))
    return node.to_stat_result()

  def fake_resolve(self: Path, strict: bool = False) -> Path:
    del strict
    return resolve_path(self)

  def fake_read_text(self: Path, encoding: str = 'utf-8') -> str:
    del encoding
    target = resolve_path(self)
    if read_counts is not None:
      read_counts[target] = read_counts.get(target, 0) + 1
    node = nodes.get(target)
    if node is None or node.content is None:
      raise FileNotFoundError(self)
    if isinstance(node.content, Exception):
      raise node.content
    return node.content

  def fake_scandir(
    path: Path | str,
  ) -> AbstractContextManager[Iterator[_FakeDirEntry]]:
    key = resolve_path(Path(path))
    node = nodes.get(key)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(path))
    if node.scandir_error is not None:
      raise node.scandir_error
    return _scandir_context(
      [_FakeDirEntry(name, child, nodes) for name, child in node.children]
    )

  mp.setattr(agy.os, 'environ', {'HOME': str(HOME), 'PATH': '/usr/bin'})
  mp.setattr(Path, 'home', classmethod(lambda cls: HOME))
  mp.setattr(Path, 'lstat', fake_lstat)
  mp.setattr(Path, 'stat', fake_stat)
  mp.setattr(Path, 'resolve', fake_resolve)
  mp.setattr(Path, 'read_text', fake_read_text)
  mp.setattr(common.os, 'scandir', fake_scandir)


def _safe_agy_state(
  *,
  rule_files: tuple[Path, ...] = (),
  skill_files: tuple[Path, ...] = (),
  plugin_state: JsonObject | None = None,
  plugin_manifests: tuple[agy.AgyPluginManifest, ...] = (),
  mcp_config: JsonObject | None = None,
  read_findings: tuple[str, ...] = (),
) -> agy.AgyState:
  return agy.AgyState(
    config_root=CONFIG,
    rule_files=rule_files,
    skill_files=skill_files,
    plugin_state=plugin_state,
    plugin_manifests=plugin_manifests,
    mcp_config=mcp_config,
    read_findings=read_findings,
  )


def test_render_and_command_builders() -> None:
  assert agy.render_agent_adapter(SYSTEM_CONTENT) == EXPECTED_ADAPTER
  assert agy.build_launch_command(
    RUNTIME_DIR, MODEL, ('--resume', 'session-1')
  ) == [
    'agy',
    '--new-project',
    '--add-dir',
    str(RUNTIME_DIR),
    '--agent',
    'pentagram',
    '--model',
    MODEL,
    '--dangerously-skip-permissions',
    '--resume',
    'session-1',
  ]
  assert agy.build_toolset_probe_command(RUNTIME_DIR, MODEL) == [
    'agy',
    '--new-project',
    '--add-dir',
    str(RUNTIME_DIR),
    '--agent',
    'pentagram',
    '--model',
    MODEL,
    '--output-format',
    'stream-json',
    '--print',
    'Reply OK and do not call any tools.',
  ]


def test_expand_agy_path_and_path_matching() -> None:
  env = {'ROOT': '/opt/agy', 'SUB': 'shared'}
  assert agy.expand_agy_path('~', HOME, env) == HOME
  assert agy.expand_agy_path('~/skills', HOME, env) == HOME / 'skills'
  assert agy.expand_agy_path('$ROOT/${SUB}/$MISSING', HOME, env) == Path(
    '/opt/agy/shared/$MISSING'
  )

  include_groups = ((re.compile('team'), re.compile('shared')),)
  excludes = (re.compile('private'),)
  assert agy.agy_path_matches(
    Path('/shared/shared-search'), include_groups, excludes
  )
  assert not agy.agy_path_matches(
    Path('/shared/team-private'), include_groups, excludes
  )
  assert not agy.agy_path_matches(
    Path('/shared/solo-search'), include_groups, excludes
  )


def test_parse_registration_config_parses_filters_and_reports_errors() -> (
  None
):
  config_path = CONFIG / 'skills.json'
  parsed = agy.parse_registration_config(
    {
      'entries': [
        {
          'path': 'shared',
          'include_only': ['search'],
          'exclude': ['draft'],
        },
        'not-a-dict',
        {'include_only': ['ok']},
      ],
      'inherits': [
        {'path': 'base.json', 'include_only': 'bad', 'exclude': ['[']},
      ],
    },
    config_path=config_path,
    kind='skills',
    inherited_include_groups=((re.compile('team'),),),
    inherited_excludes=(re.compile('legacy'),),
  )

  assert parsed == agy.ParsedRegistrationConfig(
    entries=(
      agy.AgyFilterEntry(
        'shared',
        ((re.compile('team'),), (re.compile('search'),)),
        (re.compile('legacy'), re.compile('draft')),
      ),
    ),
    inherits=(
      agy.AgyFilterEntry(
        'base.json',
        ((re.compile('team'),),),
        (re.compile('legacy'),),
      ),
    ),
    findings=(
      f'Invalid AGY skills config entry 1 in {config_path}',
      f'Invalid AGY skills config entry 2 in {config_path}',
      f'Invalid include_only in AGY skills inheritance entry 0 in '
      f'{config_path}',
      f"Invalid exclude pattern '[' in AGY skills inheritance entry 0 in "
      f'{config_path}: unterminated character set at position 0',
    ),
  )

  bad_lists = agy.parse_registration_config(
    {'entries': 'bad', 'inherits': 123},
    config_path=config_path,
    kind='skills',
  )
  assert bad_lists == agy.ParsedRegistrationConfig(
    entries=(),
    inherits=(),
    findings=(
      f'Invalid entries in AGY skills config {config_path}',
      f'Invalid inherits in AGY skills config {config_path}',
    ),
  )


def test_agy_preflight_findings_evaluates_pure_state() -> None:
  assert agy.agy_preflight_findings(_safe_agy_state()) == ()

  skill = CONFIG / 'skills' / 'search' / 'SKILL.md'
  rule = HOME / 'AGENTS.md'
  manifest_disabled = CONFIG / 'plugins' / 'safe' / 'plugin.json'
  manifest_enabled = CONFIG / 'plugins' / 'unsafe' / 'plugin.json'
  manifest_bad = CONFIG / 'plugins' / 'bad' / 'plugin.json'
  state = _safe_agy_state(
    skill_files=(skill,),
    rule_files=(rule,),
    plugin_state={
      'plugins': {
        'safe': {'enabled': False},
        'unsafe': {'enabled': True},
        'bad_override': 'invalid',
      }
    },
    plugin_manifests=(
      agy.AgyPluginManifest(manifest_disabled, {'disabled': False}),
      agy.AgyPluginManifest(manifest_enabled, {'disabled': True}),
      agy.AgyPluginManifest(
        CONFIG / 'plugins' / 'bad_override' / 'plugin.json', {}
      ),
      agy.AgyPluginManifest(manifest_bad, {'disabled': 'nope'}),
      agy.AgyPluginManifest(
        CONFIG / 'plugins' / 'err' / 'plugin.json', None
      ),
    ),
    mcp_config={
      'mcpServers': {
        'search': {'command': 'search-server'},
        'docs': {'command': 'docs-server'},
      }
    },
    read_findings=('Cannot scan AGY skills /bad: denied',),
  )

  assert agy.agy_preflight_findings(state) == (
    'Cannot scan AGY skills /bad: denied',
    f'AGY skill {skill} is present; remove it or deregister its path '
    'because AGY has no persistent all-skills disable setting',
    f'AGY rule file {rule} is present; remove or rename it because AGY '
    'has no persistent setting to disable AGENTS.md/rules files',
    f"AGY plugin 'unsafe' is enabled; set plugins['unsafe'].enabled = "
    f'false in {CONFIG / "config.json"}',
    f"Invalid AGY plugin override for 'bad_override' in "
    f'{CONFIG / "config.json"}',
    f'Invalid disabled setting in AGY plugin manifest {manifest_bad}',
    f"AGY MCP server 'docs' is configured in "
    f'{CONFIG / "mcp_config.json"}; '
    'remove it because AGY has no persistent all-MCP disable setting',
    f"AGY MCP server 'search' is configured in "
    f'{CONFIG / "mcp_config.json"}; '
    'remove it because AGY has no persistent all-MCP disable setting',
  )

  bad_plugin_and_mcp_tables = _safe_agy_state(
    plugin_state={'plugins': 'bad'},
    mcp_config={'mcpServers': 'bad'},
  )
  assert agy.agy_preflight_findings(bad_plugin_and_mcp_tables) == (
    f'Invalid plugins setting in {CONFIG / "config.json"}',
    f'Invalid mcpServers setting in {CONFIG / "mcp_config.json"}',
  )


def test_collect_agy_state_collects_filters_symlinks_cycles_and_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  external_skills = Path('/external/skills')
  linked_skills = CONFIG / 'skills' / 'linked'
  external_skill = external_skills / 'shared' / 'SKILL.md'
  read_counts: dict[Path, int] = {}

  files: dict[Path, str | Exception] = {
    CONFIG / 'mcp_config.json': '  \n',
    HOME
    / '.gemini'
    / 'antigravity-cli'
    / 'builtin'
    / 'skills'
    / 'native_swarm'
    / 'SKILL.md': 'builtin\n',
    PROJECT_ROOT
    / '.gemini'
    / 'config'
    / 'skills'
    / 'local'
    / 'SKILL.md': 'local\n',
    PROJECT_ROOT / '.agents' / 'rules' / 'local.md': 'local\n',
    CONFIG / 'rules.json': json.dumps(
      {
        'entries': [
          {
            'path': 'shared-rules',
            'include_only': ['policy'],
            'exclude': ['draft'],
          }
        ]
      }
    ),
    CONFIG / 'shared-rules' / 'active-policy.md': 'rule\n',
    CONFIG / 'shared-rules' / 'draft-policy.md': 'excluded\n',
    CONFIG / 'plugins.json': json.dumps(
      {'inherits': [{'path': str(CONFIG / 'inherited-plugins.json')}]}
    ),
    CONFIG / 'inherited-plugins.json': json.dumps(
      {'entries': [{'path': '/shared/plugins'}]}
    ),
    Path('/shared/plugins/unsafe/plugin.json'): json.dumps({}),
    CONFIG / 'config.json': json.dumps(
      {'plugins': {'unsafe': {'enabled': False}}}
    ),
    external_skill: 'skill\n',
  }

  with monkeypatch.context() as mp:
    _install_virtual_fs(
      mp,
      files=files,
      symlinks={linked_skills: external_skills},
      read_counts=read_counts,
    )
    state = agy._collect_agy_state(PROJECT_ROOT)

  assert read_counts[CONFIG / 'mcp_config.json'] == 1
  assert state == agy.AgyState(
    config_root=CONFIG,
    rule_files=(CONFIG / 'shared-rules' / 'active-policy.md',),
    skill_files=(external_skill,),
    plugin_state={'plugins': {'unsafe': {'enabled': False}}},
    plugin_manifests=(
      agy.AgyPluginManifest(
        Path('/shared/plugins/unsafe/plugin.json'), {}
      ),
    ),
    mcp_config=None,
    read_findings=(),
  )


def test_collect_agy_state_reports_cycles_missing_and_unreadable_paths(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  blocked_rules = CONFIG / 'rules' / 'blocked'
  fifo_skills = Path('/shared/fifo-skills')
  mcp_path = CONFIG / 'mcp_config.json'
  read_counts: dict[Path, int] = {}

  with monkeypatch.context() as mp:
    _install_virtual_fs(
      mp,
      files={
        CONFIG / 'skills.json': json.dumps(
          {
            'entries': [{'path': str(fifo_skills)}],
            'inherits': [
              {'path': str(CONFIG / 'cycle.json')},
              {'path': str(CONFIG / 'missing.json')},
            ],
          }
        ),
        CONFIG / 'cycle.json': json.dumps(
          {'inherits': [{'path': str(CONFIG / 'skills.json')}]}
        ),
        mcp_path: UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'bad byte'),
      },
      extra_dirs={blocked_rules: PermissionError(13, 'denied')},
      others=(fifo_skills,),
      read_counts=read_counts,
    )
    state = agy._collect_agy_state(PROJECT_ROOT)

  assert read_counts[mcp_path] == 1
  assert state == agy.AgyState(
    config_root=CONFIG,
    rule_files=(),
    skill_files=(),
    plugin_state=None,
    plugin_manifests=(),
    mcp_config=None,
    read_findings=(
      f'Cyclic AGY skills config inheritance at {CONFIG / "skills.json"}',
      f'AGY skills config path does not exist: {CONFIG / "missing.json"}',
      f'AGY skills path is not a file or directory: {fifo_skills}',
      f'Cannot scan AGY rules {blocked_rules}: [Errno 13] denied',
      f'Cannot read AGY MCP configuration {mcp_path}: '
      "'utf-8' codec can't decode byte 0xff in position 0: bad byte",
    ),
  )

  with monkeypatch.context() as mp:
    _install_virtual_fs(mp, files={}, extra_dirs={mcp_path: None})
    dir_state = agy._collect_agy_state(PROJECT_ROOT)
  assert dir_state == agy.AgyState(
    config_root=CONFIG,
    rule_files=(),
    skill_files=(),
    plugin_state=None,
    plugin_manifests=(),
    mcp_config=None,
    read_findings=(
      f'AGY MCP configuration path is not a file: {mcp_path}',
    ),
  )


@pytest.mark.parametrize(
  ('returncode', 'stdout', 'stderr', 'expected_error'),
  (
    (
      0,
      '\n'.join(
        (
          json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
          json.dumps({'event': 'result', 'result': {'status': 'SUCCESS'}}),
        )
      ),
      '',
      None,
    ),
    (
      3,
      '\n'.join(
        (
          json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
          json.dumps(
            {
              'event': 'result',
              'result': {
                'status': 'ERROR',
                'error': (
                  'failed to construct executor: unknown component: '
                  'tool "bogus" not found in registry'
                ),
              },
            }
          ),
        )
      ),
      'error: failed to construct executor\n',
      (
        'AGY tool preflight failed: failed to construct executor: '
        'unknown component: tool "bogus" not found in registry'
      ),
    ),
    (
      2,
      '',
      'auth expired\n',
      'AGY tool preflight failed: auth expired',
    ),
    (
      0,
      '\n'.join(
        (
          json.dumps({'event': 'init', 'init': {'agent': 'default'}}),
          json.dumps({'event': 'result', 'result': {'status': 'SUCCESS'}}),
        )
      ),
      '',
      'AGY tool preflight did not initialize the pentagram custom agent',
    ),
    (
      0,
      json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
      '',
      'AGY tool preflight returned no stream-json result event',
    ),
    (
      0,
      '\n'.join(
        (
          json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
          json.dumps(
            {'event': 'result', 'result': {'status': 'CANCELLED'}}
          ),
        )
      ),
      '',
      "AGY tool preflight failed: unexpected result status 'CANCELLED'",
    ),
  ),
  ids=(
    'success',
    'executor-component-error',
    'stderr-failure',
    'wrong-agent',
    'missing-result-event',
    'non-success-result',
  ),
)
def test_toolset_probe_error_validates_stream_json_output(
  returncode: int,
  stdout: str,
  stderr: str,
  expected_error: str | None,
) -> None:
  assert (
    agy.toolset_probe_error(returncode, stdout, stderr) == expected_error
  )


def test_launch_handles_probe_signal_exits_and_os_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[dict[str, object]] = []
  cleaned: list[str] = []

  class FakeTmpDir:
    def __init__(self, prefix: str = '') -> None:
      del prefix
      self.name = str(RUNTIME_DIR)

    def cleanup(self) -> None:
      cleaned.append(self.name)

  written_adapters: dict[Path, str] = {}

  def install_runtime(
    mp: pytest.MonkeyPatch,
    replies: Sequence[subprocess.CompletedProcess[str] | Exception],
  ) -> None:
    queue = deque(replies)
    written_adapters.clear()
    calls.clear()
    cleaned.clear()
    mp.setattr(agy, '_collect_agy_state', lambda _r: _safe_agy_state())
    mp.setattr(agy.tempfile, 'TemporaryDirectory', FakeTmpDir)
    mp.setattr(Path, 'mkdir', lambda self, parents=False: None)
    mp.setattr(
      Path,
      'read_text',
      lambda self, encoding='utf-8': SYSTEM_CONTENT
      if self == SYSTEM_FILE
      else '',
    )
    mp.setattr(
      Path,
      'write_text',
      lambda self, content, encoding='utf-8': (
        written_adapters.__setitem__(self, content) or len(content)
      ),
    )

    def fake_run(
      cmd: Sequence[str],
      cwd: Path,
      env: Mapping[str, str],
      capture_output: bool = False,
      text: bool = False,
      encoding: str | None = None,
      errors: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
      adapter_path = (
        RUNTIME_DIR / '.agents' / 'agents' / 'pentagram' / 'agent.md'
      )
      calls.append(
        {
          'cmd': list(cmd),
          'cwd': cwd,
          'capture_output': capture_output,
          'text': text,
          'encoding': encoding,
          'errors': errors,
          'adapter': written_adapters.get(adapter_path),
        }
      )
      reply = queue.popleft()
      if isinstance(reply, Exception):
        raise reply
      return reply

    mp.setattr(agy.subprocess, 'run', fake_run)

  probe_ok = '\n'.join(
    (
      json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
      json.dumps({'event': 'result', 'result': {'status': 'SUCCESS'}}),
    )
  )
  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {agy.AGY_TOOLSET_ENV: '1'})
    install_runtime(
      mp,
      [
        subprocess.CompletedProcess([], 0, stdout=probe_ok, stderr=''),
        subprocess.CompletedProcess([], -signal.SIGTERM),
      ],
    )
    with pytest.raises(click.exceptions.Exit) as exit_info:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, ('--print', 'hi'), MODEL)
    assert exit_info.value.exit_code == 128 + signal.SIGTERM
    assert cleaned == [str(RUNTIME_DIR)]
    assert calls == [
      {
        'cmd': agy.build_toolset_probe_command(RUNTIME_DIR, MODEL),
        'cwd': PROJECT_ROOT,
        'capture_output': True,
        'text': True,
        'encoding': 'utf-8',
        'errors': 'replace',
        'adapter': EXPECTED_ADAPTER,
      },
      {
        'cmd': agy.build_launch_command(
          RUNTIME_DIR, MODEL, ('--print', 'hi')
        ),
        'cwd': PROJECT_ROOT,
        'capture_output': False,
        'text': False,
        'encoding': None,
        'errors': None,
        'adapter': EXPECTED_ADAPTER,
      },
    ]

  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {})
    install_runtime(mp, [FileNotFoundError(2, 'agy missing')])
    with pytest.raises(click.ClickException) as run_err:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, (), MODEL)
    assert str(run_err.value) == (
      'Failed to launch agent agy: [Errno 2] agy missing'
    )
    assert cleaned == [str(RUNTIME_DIR)]

  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {})
    mp.setattr(agy, '_collect_agy_state', lambda _r: _safe_agy_state())
    mp.setattr(
      Path,
      'read_text',
      lambda self, encoding='utf-8': (_ for _ in ()).throw(
        PermissionError(13, 'denied')
      ),
    )
    with pytest.raises(click.ClickException) as sys_err:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, (), MODEL)
    assert str(sys_err.value) == (
      f'Cannot read system prompt {SYSTEM_FILE}: [Errno 13] denied'
    )

  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {})
    mp.setattr(agy, '_collect_agy_state', lambda _r: _safe_agy_state())
    mp.setattr(
      Path, 'read_text', lambda self, encoding='utf-8': SYSTEM_CONTENT
    )
    mp.setattr(
      agy.tempfile,
      'TemporaryDirectory',
      lambda prefix='': (_ for _ in ()).throw(OSError('disk full')),
    )
    with pytest.raises(click.ClickException) as tmp_err:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, (), MODEL)
    assert str(tmp_err.value) == (
      'Failed to prepare AGY runtime adapter: disk full'
    )

  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {})
    mp.setattr(
      agy,
      '_collect_agy_state',
      lambda _r: _safe_agy_state(rule_files=(HOME / 'AGENTS.md',)),
    )
    mp.setattr(
      Path,
      'read_text',
      lambda self, encoding='utf-8': (_ for _ in ()).throw(
        AssertionError(f'unexpected read_text on {self}')
      ),
    )
    mp.setattr(
      agy.tempfile,
      'TemporaryDirectory',
      lambda prefix='': (_ for _ in ()).throw(
        AssertionError('unexpected TemporaryDirectory')
      ),
    )
    mp.setattr(
      agy.subprocess,
      'run',
      lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError('unexpected subprocess.run')
      ),
    )
    with pytest.raises(click.ClickException) as preflight_err:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, (), MODEL)
    assert str(preflight_err.value) == (
      'AGY filesystem preflight failed:\n'
      f'  - AGY rule file {HOME / "AGENTS.md"} is present; remove or '
      'rename it because AGY has no persistent setting to disable '
      'AGENTS.md/rules files'
    )

  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {agy.AGY_TOOLSET_ENV: '1'})
    install_runtime(mp, [FileNotFoundError(2, 'probe missing')])
    with pytest.raises(click.ClickException) as probe_os_err:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, (), MODEL)
    assert str(probe_os_err.value) == (
      'AGY tool preflight failed: [Errno 2] probe missing'
    )
    assert cleaned == [str(RUNTIME_DIR)]
    assert len(calls) == 1

  with monkeypatch.context() as mp:
    mp.setattr(agy.os, 'environ', {agy.AGY_TOOLSET_ENV: '1'})
    install_runtime(
      mp,
      [subprocess.CompletedProcess([], 2, stdout='', stderr='bad tool\n')],
    )
    with pytest.raises(click.ClickException) as probe_fail_err:
      agy.launch(PROJECT_ROOT, SYSTEM_FILE, (), MODEL)
    assert (
      str(probe_fail_err.value) == 'AGY tool preflight failed: bad tool'
    )
    assert cleaned == [str(RUNTIME_DIR)]
    assert len(calls) == 1
