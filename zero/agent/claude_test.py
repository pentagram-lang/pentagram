import json
import os
import stat
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import click
import pytest

from zero.agent import claude, common
from zero.agent.common import JsonObject

HOME = Path('/virtual/home')
PROJECT = Path('/virtual/project')


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
    self,
    name: str,
    path: Path,
    nodes: Mapping[Path, _FakeNode],
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


def _safe_claude_state(
  *,
  settings: tuple[tuple[Path, JsonObject], ...] | None = None,
  claude_json: JsonObject | None = None,
  mcp_json: JsonObject | None = None,
  memory_files: tuple[Path, ...] = (),
  skill_files: tuple[Path, ...] = (),
  live_mcp_servers: tuple[str, ...] | None = None,
  read_findings: tuple[str, ...] = (),
) -> claude.ClaudeState:
  disabled = list(claude.CLAUDE_MCP_SERVERS)
  default_settings = (
    (
      HOME / '.claude' / 'settings.json',
      {'autoMemoryEnabled': False, 'enabledPlugins': {}},
    ),
  )
  default_claude_json: JsonObject = {
    'disabledMcpServers': disabled,
    'enabledMcpServers': [],
    'mcpServers': {},
    'projects': {
      str(PROJECT): {
        'disabledMcpServers': disabled,
        'enabledMcpServers': [],
        'mcpServers': {},
        'disabledMcpjsonServers': [],
        'enabledMcpjsonServers': [],
      }
    },
  }
  return claude.ClaudeState(
    home=HOME,
    project_root=PROJECT,
    settings=default_settings if settings is None else settings,
    claude_json_path=HOME / '.claude.json',
    claude_json=(
      default_claude_json if claude_json is None else claude_json
    ),
    mcp_json_path=PROJECT / '.mcp.json',
    mcp_json={'mcpServers': {}} if mcp_json is None else mcp_json,
    memory_files=memory_files,
    skill_files=skill_files,
    live_mcp_servers=live_mcp_servers,
    read_findings=read_findings,
  )


def _build_virtual_tree(
  files: Mapping[Path, str | Exception],
  *,
  symlinks: Mapping[Path, Path] | None = None,
  extra_dirs: Mapping[Path, OSError | None] | None = None,
) -> dict[Path, _FakeNode]:
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

  for directory, scandir_err in (extra_dirs or {}).items():
    ensure_dir(directory, scandir_error=scandir_err)

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
  return nodes


def _install_virtual_fs(
  mp: pytest.MonkeyPatch,
  *,
  files: Mapping[Path, str | Exception],
  symlinks: Mapping[Path, Path] | None = None,
  extra_dirs: Mapping[Path, OSError | None] | None = None,
) -> None:
  nodes = _build_virtual_tree(
    files, symlinks=symlinks, extra_dirs=extra_dirs
  )

  def fake_lstat(self: Path) -> os.stat_result:
    node = nodes.get(self)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(self))
    return node.to_stat_result()

  def fake_stat(
    self: Path, *, follow_symlinks: bool = True
  ) -> os.stat_result:
    node = nodes.get(self)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(self))
    if follow_symlinks and node.target is not None:
      target = nodes.get(node.target)
      if target is None:
        raise FileNotFoundError(2, 'No such file or directory', str(self))
      return target.to_stat_result()
    return node.to_stat_result()

  def fake_resolve(self: Path, strict: bool = False) -> Path:
    del strict
    node = nodes.get(self)
    if node is not None and node.target is not None:
      return node.target
    return self

  def fake_read_text(self: Path, encoding: str = 'utf-8') -> str:
    del encoding
    node = nodes.get(self)
    if node is not None and node.target is not None:
      node = nodes.get(node.target)
    if node is None or node.content is None:
      raise FileNotFoundError(self)
    if isinstance(node.content, Exception):
      raise node.content
    return node.content

  def fake_scandir(
    path: Path | str,
  ) -> AbstractContextManager[Iterator[_FakeDirEntry]]:
    key = Path(path)
    node = nodes.get(key)
    if node is not None and node.target is not None:
      node = nodes.get(node.target)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(path))
    if node.scandir_error is not None:
      raise node.scandir_error
    return _scandir_context(
      [_FakeDirEntry(name, child, nodes) for name, child in node.children]
    )

  mp.setenv('HOME', str(HOME))
  mp.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())
  mp.setattr(Path, 'lstat', fake_lstat)
  mp.setattr(Path, 'stat', fake_stat)
  mp.setattr(Path, 'resolve', fake_resolve)
  mp.setattr(Path, 'read_text', fake_read_text)
  mp.setattr(common.os, 'scandir', fake_scandir)


def test_parse_mcp_list_output_and_build_launch_command() -> None:
  stdout = (
    'Checking MCP servers...\n'
    'claude.ai Gmail: https://mail.example - Connected\n'
    'claude.ai Google Drive: https://drive.example - Needs auth\n'
    'ignored line without separator\n'
    'claude.ai Gmail: duplicate - Connected\n'
    '  : empty - Ignored\n'
  )
  assert (
    claude.parse_mcp_list_output(stdout),
    claude.build_launch_command(PROJECT / 'sys.md', 'sonnet'),
  ) == (
    ('claude.ai Gmail', 'claude.ai Google Drive'),
    [
      'claude',
      '--model',
      'sonnet',
      '--system-prompt-file',
      str(PROJECT / 'sys.md'),
      '--dangerously-skip-permissions',
    ],
  )


def test_claude_preflight_accepts_safe_state() -> None:
  assert claude.claude_preflight_findings(_safe_claude_state()) == ()


def test_claude_preflight_validates_auto_memory_and_plugins() -> None:
  user_settings = HOME / '.claude' / 'settings.json'
  project_settings = PROJECT / '.claude' / 'settings.json'

  omitted = _safe_claude_state(
    settings=((user_settings, {'enabledPlugins': {}}),)
  )
  assert claude.claude_preflight_findings(omitted) == (
    'Claude auto-memory is not persistently disabled; '
    f'run /memory and disable auto-memory in {user_settings}',
  )

  true_and_non_bool = _safe_claude_state(
    settings=(
      (
        user_settings,
        {'autoMemoryEnabled': 'false', 'enabledPlugins': []},
      ),
      (
        project_settings,
        {
          'autoMemoryEnabled': True,
          'enabledPlugins': {'b': True, 'a': True},
        },
      ),
    )
  )
  assert claude.claude_preflight_findings(true_and_non_bool) == (
    f'Invalid autoMemoryEnabled setting in Claude settings '
    f'{user_settings}',
    'Claude auto-memory is not persistently disabled; '
    f'run /memory and disable auto-memory in {project_settings}',
    f'Invalid enabledPlugins setting in Claude settings {user_settings}',
    f"Claude plugin 'a' is not disabled in {project_settings}; "
    'run /plugin and disable a',
    f"Claude plugin 'b' is not disabled in {project_settings}; "
    'run /plugin and disable b',
  )


def test_claude_preflight_rejects_skills_memory_and_plugins() -> None:
  settings_path = HOME / '.claude' / 'settings.json'
  memory_path = HOME / '.claude' / 'rules' / 'runtime.md'
  skill_path = HOME / '.claude' / 'skills' / 'search' / 'SKILL.md'
  state = _safe_claude_state(
    settings=(
      (
        settings_path,
        {'autoMemoryEnabled': False, 'enabledPlugins': {'unsafe': True}},
      ),
    ),
    memory_files=(memory_path,),
    skill_files=(skill_path,),
  )

  assert claude.claude_preflight_findings(state) == (
    f'Claude memory file {memory_path} is present; remove or rename it '
    'because Claude has no persistent setting to disable CLAUDE.md/rules '
    'memory files',
    f"Claude plugin 'unsafe' is not disabled in {settings_path}; "
    'run /plugin and disable unsafe',
    f'Claude skill {skill_path} is present; remove or rename it because '
    'Claude has no persistent setting to disable standalone skills',
  )


def test_claude_preflight_checks_mcp_ordering_and_malformed_schemas() -> (
  None
):
  claude_json_path = HOME / '.claude.json'
  mcp_json_path = PROJECT / '.mcp.json'
  disabled = list(claude.CLAUDE_MCP_SERVERS)

  state = _safe_claude_state(
    claude_json={
      'disabledMcpServers': disabled,
      'enabledMcpServers': ['z-global', 'a-global'],
      'mcpServers': 'invalid',
      'projects': {
        str(PROJECT): {
          'disabledMcpServers': disabled,
          'enabledMcpServers': ['z-proj', 'a-proj'],
          'mcpServers': 'invalid',
          'disabledMcpjsonServers': [],
          'enabledMcpjsonServers': ['z-json', 'a-json'],
        }
      },
    },
    mcp_json={
      'mcpServers': {
        'z-json': {'command': 'server'},
        'a-json': {'command': 'server'},
      }
    },
  )

  assert claude.claude_preflight_findings(state) == (
    "Claude MCP server 'a-global' is explicitly enabled in "
    f'{claude_json_path}; run /mcp and disable a-global',
    "Claude MCP server 'z-global' is explicitly enabled in "
    f'{claude_json_path}; run /mcp and disable z-global',
    f'Invalid mcpServers setting in {claude_json_path}',
    "Claude MCP server 'a-proj' is explicitly enabled in "
    f'{claude_json_path}; run /mcp and disable a-proj',
    "Claude MCP server 'z-proj' is explicitly enabled in "
    f'{claude_json_path}; run /mcp and disable z-proj',
    f'Invalid project mcpServers setting in {claude_json_path}',
    "Claude MCP server 'a-json' is explicitly enabled in "
    f'{claude_json_path}; run /mcp and disable a-json',
    "Claude MCP server 'z-json' is explicitly enabled in "
    f'{claude_json_path}; run /mcp and disable z-json',
    "Claude MCP server 'a-json' is not disabled in "
    f'{mcp_json_path}; run /mcp and disable a-json',
    "Claude MCP server 'z-json' is not disabled in "
    f'{mcp_json_path}; run /mcp and disable z-json',
  )

  bad_types = _safe_claude_state(
    claude_json={
      'disabledMcpServers': 'bad',
      'enabledMcpServers': 123,
      'projects': 'bad',
    },
    mcp_json={'mcpServers': 'bad'},
  )
  assert claude.claude_preflight_findings(bad_types) == (
    f'Invalid disabledMcpServers setting in {claude_json_path}',
    f'Invalid enabledMcpServers setting in {claude_json_path}',
    f'Invalid projects setting in {claude_json_path}',
    f'Invalid mcpServers setting in {mcp_json_path}',
    "Claude MCP server 'claude.ai Gmail' is not disabled in "
    f'{claude_json_path}; run /mcp and disable claude.ai Gmail',
    "Claude MCP server 'claude.ai Google Calendar' is not disabled in "
    f'{claude_json_path}; run /mcp and disable claude.ai Google Calendar',
    "Claude MCP server 'claude.ai Google Drive' is not disabled in "
    f'{claude_json_path}; run /mcp and disable claude.ai Google Drive',
  )

  bad_project_entry = _safe_claude_state(
    claude_json={'projects': {str(PROJECT): 'bad'}},
  )
  assert claude.claude_preflight_findings(bad_project_entry) == (
    f'Invalid Claude project configuration in {claude_json_path}',
    "Claude MCP server 'claude.ai Gmail' is not disabled in "
    f'{claude_json_path}; run /mcp and disable claude.ai Gmail',
    "Claude MCP server 'claude.ai Google Calendar' is not disabled in "
    f'{claude_json_path}; run /mcp and disable claude.ai Google Calendar',
    "Claude MCP server 'claude.ai Google Drive' is not disabled in "
    f'{claude_json_path}; run /mcp and disable claude.ai Google Drive',
  )


def test_claude_mcp_set_error_is_pure_and_deterministic() -> None:
  expected = tuple(sorted(claude.CLAUDE_MCP_SERVERS))
  assert claude.claude_mcp_set_error(None) is None
  assert claude.claude_mcp_set_error(expected) is None
  assert (
    claude.claude_preflight_findings(
      _safe_claude_state(live_mcp_servers=('unexpected server',))
    )
    == ()
  )

  assert claude.claude_mcp_set_error(('unexpected server',)) == (
    f'Claude MCP inventory mismatch for {claude.CLAUDE_MCP_SET_ENV}; '
    f'missing from claude mcp list: {", ".join(expected)}; '
    'not in the hardcoded set: unexpected server'
  )


def test_collect_claude_state_scans_symlinks_and_records_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  managed = Path('/etc/claude-code/managed-settings.json')
  plugin_skill = HOME / '.claude' / 'plugins' / 'sample' / 'SKILL.md'
  linked_skill = HOME / '.claude' / 'skills' / 'plugin' / 'SKILL.md'
  external_skill_dir = Path('/external/shared-skills')
  external_skill = external_skill_dir / 'tool' / 'SKILL.md'
  symlinked_skill_dir = HOME / '.claude' / 'skills' / 'shared'
  broken_skill = HOME / '.claude' / 'skills' / 'broken' / 'SKILL.md'
  dir_named_skill = HOME / '.claude' / 'skills' / 'dir_skill' / 'SKILL.md'
  external_rule_dir = Path('/external/shared-rules')
  external_rule = external_rule_dir / 'rule.md'
  symlinked_rule_dir = HOME / '.claude' / 'rules' / 'shared'
  blocked_rules_dir = HOME / '.claude' / 'rules' / 'blocked'
  project_skill = PROJECT / '.claude' / 'skills' / 'local' / 'SKILL.md'
  project_memory = PROJECT / 'CLAUDE.md'
  project_rule = PROJECT / '.claude' / 'rules' / 'local.md'
  disabled = list(claude.CLAUDE_MCP_SERVERS)

  user_settings_payload = {
    'autoMemoryEnabled': False,
    'enabledPlugins': {},
  }
  managed_payload = {'enabledPlugins': {'managed-plugin': False}}
  claude_json_payload: JsonObject = {
    'disabledMcpServers': ['claude.ai Gmail'],
    'enabledMcpServers': [],
    'mcpServers': {},
    'projects': {
      str(PROJECT): {
        'disabledMcpServers': disabled,
        'enabledMcpServers': [],
        'mcpServers': {},
        'disabledMcpjsonServers': [],
        'enabledMcpjsonServers': [],
      }
    },
  }

  files: dict[Path, str | Exception] = {
    HOME / '.claude' / 'settings.json': json.dumps(user_settings_payload),
    managed: json.dumps(managed_payload),
    HOME / '.claude.json': json.dumps(claude_json_payload),
    PROJECT / '.mcp.json': json.dumps({'mcpServers': {}}),
    plugin_skill: 'plugin skill\n',
    external_skill: 'external skill\n',
    external_rule: 'external rule\n',
    project_skill: 'project skill\n',
    project_memory: 'project memory\n',
    project_rule: 'project rule\n',
  }

  with monkeypatch.context() as mp:
    _install_virtual_fs(
      mp,
      files=files,
      symlinks={
        linked_skill: plugin_skill,
        symlinked_skill_dir: external_skill_dir,
        symlinked_rule_dir: external_rule_dir,
        broken_skill: Path('/virtual/missing/SKILL.md'),
      },
      extra_dirs={
        dir_named_skill: None,
        blocked_rules_dir: PermissionError(13, 'denied'),
      },
    )
    mp.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', (managed,))
    mp.delenv(claude.CLAUDE_MCP_SET_ENV, raising=False)
    state = claude._collect_claude_state(PROJECT)

  assert state == claude.ClaudeState(
    home=HOME,
    project_root=PROJECT,
    settings=(
      (HOME / '.claude' / 'settings.json', user_settings_payload),
      (managed, managed_payload),
    ),
    claude_json_path=HOME / '.claude.json',
    claude_json=claude_json_payload,
    mcp_json_path=PROJECT / '.mcp.json',
    mcp_json={'mcpServers': {}},
    memory_files=(external_rule,),
    skill_files=(external_skill,),
    live_mcp_servers=None,
    read_findings=(
      f'Cannot scan Claude rules {blocked_rules_dir}: [Errno 13] denied',
    ),
  )


def test_claude_live_mcp_probe_errors_wrap_in_click_exception(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  with monkeypatch.context() as mp:
    mp.setattr(
      claude.subprocess,
      'run',
      lambda *_a, **_kw: SimpleNamespace(
        returncode=1, stdout='', stderr='auth missing\n'
      ),
    )
    with pytest.raises(click.ClickException) as nonzero_err:
      claude._probe_claude_mcp_servers(PROJECT)
    assert str(nonzero_err.value) == (
      'Claude MCP inventory preflight failed: auth missing'
    )

  with monkeypatch.context() as mp:
    mp.setattr(
      claude.subprocess,
      'run',
      lambda *_a, **_kw: (_ for _ in ()).throw(
        FileNotFoundError(2, 'claude missing')
      ),
    )
    with pytest.raises(click.ClickException) as oserr:
      claude._probe_claude_mcp_servers(PROJECT)
    assert str(oserr.value) == (
      'Claude MCP inventory preflight failed: [Errno 2] claude missing'
    )

  with monkeypatch.context() as mp:
    stdout = '\n'.join(
      f'{server}: https://mcp.example - Connected'
      for server in claude.CLAUDE_MCP_SERVERS
    )
    mp.setattr(
      claude.subprocess,
      'run',
      lambda *_a, **_kw: SimpleNamespace(
        returncode=0, stdout=stdout, stderr=''
      ),
    )
    assert claude._probe_claude_mcp_servers(PROJECT) == tuple(
      sorted(claude.CLAUDE_MCP_SERVERS)
    )


def test_claude_launch_forwards_arguments_and_aborts_before_exec(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  system_file = PROJECT / 'sys.md'

  with monkeypatch.context() as mp:
    calls: list[tuple[Path, Sequence[str], Sequence[str]]] = []
    mp.setattr(
      claude, '_collect_claude_state', lambda _r: _safe_claude_state()
    )
    mp.setattr(
      claude,
      'exec_agent',
      lambda root, command, arguments: calls.append(
        (root, command, arguments)
      ),
    )
    claude.launch(PROJECT, system_file, ['--resume', 'session'], 'sonnet')
    assert calls == [
      (
        PROJECT,
        [
          'claude',
          '--model',
          'sonnet',
          '--system-prompt-file',
          str(system_file),
          '--dangerously-skip-permissions',
        ],
        ['--resume', 'session'],
      )
    ]

  with monkeypatch.context() as mp:
    calls = []
    mp.setattr(
      claude,
      '_collect_claude_state',
      lambda _r: _safe_claude_state(settings=()),
    )
    mp.setattr(
      claude,
      'exec_agent',
      lambda root, command, arguments: calls.append(
        (root, command, arguments)
      ),
    )
    with pytest.raises(click.ClickException) as error:
      claude.launch(PROJECT, system_file, ['--resume'], 'sonnet')
    assert str(error.value) == (
      'Claude filesystem preflight failed:\n'
      '  - Claude auto-memory is not persistently disabled; '
      f'run /memory and disable auto-memory in '
      f'{HOME / ".claude" / "settings.json"}'
    )
    assert calls == []

  with monkeypatch.context() as mp:
    calls = []
    mp.setattr(
      claude,
      '_collect_claude_state',
      lambda _r: _safe_claude_state(live_mcp_servers=('unexpected',)),
    )
    mp.setattr(
      claude,
      'exec_agent',
      lambda root, command, arguments: calls.append(
        (root, command, arguments)
      ),
    )
    with pytest.raises(click.ClickException) as mcp_error:
      claude.launch(PROJECT, system_file, [], 'sonnet')
    expected = ', '.join(sorted(claude.CLAUDE_MCP_SERVERS))
    assert str(mcp_error.value) == (
      f'Claude MCP inventory mismatch for {claude.CLAUDE_MCP_SET_ENV}; '
      f'missing from claude mcp list: {expected}; '
      'not in the hardcoded set: unexpected'
    )
    assert calls == []
