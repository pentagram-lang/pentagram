import json
import os
import stat
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import click
import pytest

from zero.agent import codex, common

HOME = Path('/virtual/home')
CODEX_HOME = HOME / '.codex'
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


def _safe_codex_state(
  *,
  home: Path = HOME,
  codex_home: Path = CODEX_HOME,
  configs: tuple[codex.CodexConfigEntry, ...] | None = None,
  memory_files: tuple[Path, ...] = (),
  skill_files: tuple[Path, ...] = (),
  environ: Mapping[str, str] | None = None,
  skill_path_resolutions: tuple[tuple[Path, Path], ...] = (),
  read_findings: tuple[str, ...] = (),
) -> codex.CodexState:
  default_configs: tuple[codex.CodexConfigEntry, ...] = (
    (
      codex_home / 'config.toml',
      {'features': {'memories': False, 'plugins': False}},
    ),
  )
  return codex.CodexState(
    home=home,
    codex_home=codex_home,
    configs=default_configs if configs is None else configs,
    memory_files=memory_files,
    skill_files=skill_files,
    environ={} if environ is None else environ,
    skill_path_resolutions=skill_path_resolutions,
    read_findings=read_findings,
  )


def _install_virtual_fs(
  mp: pytest.MonkeyPatch,
  *,
  files: Mapping[Path, str | Exception],
  symlinks: Mapping[Path, Path] | None = None,
  extra_dirs: Mapping[Path, OSError | None] | None = None,
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
      parent_resolved = resolve_path(self.parent) / self.name
      node = nodes.get(parent_resolved)
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

  mp.setattr(codex.os, 'environ', {'HOME': str(HOME)})
  mp.setattr(Path, 'home', classmethod(lambda cls: HOME))
  mp.setattr(Path, 'lstat', fake_lstat)
  mp.setattr(Path, 'stat', fake_stat)
  mp.setattr(Path, 'resolve', fake_resolve)
  mp.setattr(Path, 'read_text', fake_read_text)
  mp.setattr(common.os, 'scandir', fake_scandir)


def test_parse_toml_config_returns_config_or_error() -> None:
  path = CODEX_HOME / 'config.toml'

  ok_cfg, ok_err = codex.parse_toml_config(
    '[features]\nmemories = false\n', path
  )
  bad_cfg, bad_err = codex.parse_toml_config('not = [valid toml', path)

  assert (ok_cfg, ok_err) == ({'features': {'memories': False}}, None)
  assert (bad_cfg, bad_err) == (
    None,
    f'Cannot read Codex config {path}: '
    'Invalid value (at line 1, column 8)',
  )


def test_codex_allows_omitted_feature_disable_settings() -> None:
  state = _safe_codex_state(configs=((CODEX_HOME / 'config.toml', {}),))
  assert codex.codex_preflight_findings(state) == ()


def test_codex_rejects_enabled_features_mcp_and_invalid_schemas() -> None:
  config_path = CODEX_HOME / 'config.toml'
  state = _safe_codex_state(
    configs=(
      (
        config_path,
        {
          'profile': 'work',
          'features': {'memories': True, 'plugins': True},
          'mcp_servers': {'docs': {'enabled': True}, 'bad': 'not-a-table'},
        },
      ),
    )
  )

  assert codex.codex_preflight_findings(state) == (
    f'Codex profile selection is not allowed in {config_path}: work',
    'Codex setting features.memories is not disabled; '
    'run codex features disable memories; this persists the disabled '
    f'state in {config_path}',
    'Codex setting features.plugins is not disabled; '
    'run codex features disable plugins; this persists the disabled '
    f'state in {config_path}',
    f"Codex MCP server 'bad' is not disabled in {config_path}; "
    f'set [mcp_servers."bad"] enabled = false in {config_path}',
    f"Codex MCP server 'docs' is not disabled in {config_path}; "
    f'set [mcp_servers."docs"] enabled = false in {config_path}',
  )

  bad_tables = _safe_codex_state(
    configs=(
      (
        config_path,
        {
          'features': 'bad',
          'mcp_servers': 'bad',
          'skills': 'bad',
        },
      ),
      (
        PROJECT / '.codex' / 'config.toml',
        {
          'skills': {'config': 'bad'},
        },
      ),
    )
  )
  assert codex.codex_preflight_findings(bad_tables) == (
    f'Invalid features table in Codex config {config_path}',
    f'Invalid mcp_servers table in Codex config {config_path}',
    f'Invalid skills table in Codex config {config_path}',
    f'Invalid skills.config value in Codex config '
    f'{PROJECT / ".codex" / "config.toml"}',
  )


def test_codex_rejects_home_memory_file_and_undisabled_skill() -> None:
  memory = CODEX_HOME / 'memories' / 'note.md'
  skill = CODEX_HOME / 'skills' / 'search' / 'SKILL.md'
  state = _safe_codex_state(memory_files=(memory,), skill_files=(skill,))

  assert codex.codex_preflight_findings(state) == (
    f'Codex memory file {memory} is present; remove or rename it '
    'because Codex has no persistent setting to disable memory files',
    f'Codex skill {skill} is not disabled; '
    f'run /skills and disable {skill}',
  )


def test_codex_skill_overrides_handle_expansion_and_reenabled() -> None:
  config_path = CODEX_HOME / 'config.toml'
  project_config = PROJECT / '.codex' / 'config.toml'
  dotfiles_skill = Path('/dotfiles/codex/skills/guide/SKILL.md')
  env_skill = Path('/virtual/shared/custom/SKILL.md')
  rel_skill = CODEX_HOME / 'skills' / 'local' / 'SKILL.md'
  reenabled_skill = CODEX_HOME / 'skills' / 'reenabled' / 'SKILL.md'
  reversed_skill = CODEX_HOME / 'skills' / 'reversed' / 'SKILL.md'
  non_bool_skill = CODEX_HOME / 'skills' / 'non_bool' / 'SKILL.md'

  state = _safe_codex_state(
    configs=(
      (
        config_path,
        {
          'features': {'memories': False, 'plugins': False},
          'skills': {
            'config': [
              'not-a-dict',
              {'enabled': False},
              {'path': '~/.codex/skills/guide/SKILL.md', 'enabled': False},
              {'path': '$SKILL_ROOT/custom', 'enabled': False},
              {'path': 'skills/local', 'enabled': False},
              {'path': 'skills/reenabled', 'enabled': False},
              {'path': 'skills/reversed', 'enabled': True},
              {'path': 'skills/non_bool', 'enabled': 'false'},
            ]
          },
        },
      ),
      (
        project_config,
        {
          'skills': {
            'config': [
              {'path': str(reenabled_skill), 'enabled': True},
              {'path': str(reversed_skill), 'enabled': False},
            ]
          }
        },
      ),
    ),
    skill_files=(
      dotfiles_skill,
      env_skill,
      rel_skill,
      reenabled_skill,
      reversed_skill,
      non_bool_skill,
    ),
    environ={'SKILL_ROOT': '/virtual/shared'},
    skill_path_resolutions=(
      (HOME / '.codex' / 'skills' / 'guide' / 'SKILL.md', dotfiles_skill),
    ),
  )

  assert codex.codex_preflight_findings(state) == (
    f'Invalid skills.config entry 0 in Codex config {config_path}',
    f'Invalid skills.config entry 1 in Codex config {config_path}',
    f'Invalid skills.config entry 7 in Codex config {config_path}',
    f'Codex skill {reenabled_skill} is not disabled; '
    f'run /skills and disable {reenabled_skill}',
    f'Codex skill {reversed_skill} is not disabled; '
    f'run /skills and disable {reversed_skill}',
    f'Codex skill {non_bool_skill} is not disabled; '
    f'run /skills and disable {non_bool_skill}',
  )


def test_collect_codex_state_handles_symlinks_profiles_and_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  real_codex_home = Path('/dotfiles/codex')
  user_config = real_codex_home / 'config.toml'
  profile_config = real_codex_home / 'work.config.toml'
  project_config = PROJECT / '.codex' / 'config.toml'
  plugin_skill = real_codex_home / 'plugins' / 'example' / 'SKILL.md'
  tmp_plugin_skill = (
    real_codex_home / '.tmp' / 'plugins' / 'x' / 'SKILL.md'
  )
  real_skill = Path('/external/shared-skill/SKILL.md')
  linked_skill = real_codex_home / 'skills' / 'shared' / 'SKILL.md'
  broken_skill = real_codex_home / 'skills' / 'broken' / 'SKILL.md'
  dir_named_skill = real_codex_home / 'skills' / 'dir_skill' / 'SKILL.md'
  blocked_memories = real_codex_home / 'memories' / 'blocked'
  read_counts: dict[Path, int] = {}

  with monkeypatch.context() as mp:
    _install_virtual_fs(
      mp,
      files={
        user_config: (
          'profile = "work"\n'
          '[features]\nmemories = false\nplugins = false\n'
          '[[skills.config]]\n'
          'path = "~/.codex/skills/shared/SKILL.md"\n'
          'enabled = false\n'
        ),
        profile_config: '[mcp_servers.docs]\nenabled = false\n',
        project_config: UnicodeDecodeError(
          'utf-8', b'\xff', 0, 1, 'bad byte'
        ),
        plugin_skill: 'plugin skill\n',
        tmp_plugin_skill: 'tmp plugin skill\n',
        real_skill: 'shared skill\n',
      },
      symlinks={
        CODEX_HOME: real_codex_home,
        linked_skill: real_skill,
        broken_skill: Path('/virtual/missing/SKILL.md'),
      },
      extra_dirs={
        dir_named_skill: None,
        blocked_memories: PermissionError(13, 'denied'),
      },
      read_counts=read_counts,
    )
    state = codex._collect_codex_state(PROJECT)

  assert read_counts[user_config] == 1
  expected_skill_entry = HOME / '.codex' / 'skills' / 'shared' / 'SKILL.md'
  expected_state = codex.CodexState(
    home=HOME,
    codex_home=real_codex_home,
    configs=(
      (
        user_config,
        {
          'profile': 'work',
          'features': {'memories': False, 'plugins': False},
          'skills': {
            'config': [
              {
                'path': '~/.codex/skills/shared/SKILL.md',
                'enabled': False,
              }
            ]
          },
        },
      ),
      (profile_config, {'mcp_servers': {'docs': {'enabled': False}}}),
    ),
    memory_files=(),
    skill_files=(real_skill,),
    environ=MappingProxyType({'HOME': str(HOME)}),
    skill_path_resolutions=((expected_skill_entry, real_skill),),
    read_findings=(
      f'Cannot read Codex config {project_config}: '
      "'utf-8' codec can't decode byte 0xff in position 0: bad byte",
      f'Cannot scan Codex memories {blocked_memories}: [Errno 13] denied',
    ),
  )
  assert state == expected_state
  assert codex.codex_preflight_findings(state) == (
    f'Cannot read Codex config {project_config}: '
    "'utf-8' codec can't decode byte 0xff in position 0: bad byte",
    f'Cannot scan Codex memories {blocked_memories}: [Errno 13] denied',
    f'Codex profile selection is not allowed in {user_config}: work',
  )


def test_codex_launch_forwards_arguments_and_aborts_before_exec(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  system_file = PROJECT / 'sys.md'

  with monkeypatch.context() as mp:
    calls: list[tuple[Path, Sequence[str], Sequence[str]]] = []
    mp.setattr(
      codex, '_collect_codex_state', lambda _r: _safe_codex_state()
    )
    mp.setattr(
      codex,
      'exec_agent',
      lambda root, command, arguments: calls.append(
        (root, command, arguments)
      ),
    )
    codex.launch(
      PROJECT, system_file, ['--resume', 'session'], 'gpt-6-astra'
    )
    assert calls == [
      (
        PROJECT,
        [
          'codex',
          '--model',
          'gpt-6-astra',
          '--config',
          f'model_instructions_file={json.dumps(str(system_file))}',
          '--dangerously-bypass-approvals-and-sandbox',
          '--cd',
          str(PROJECT),
        ],
        ['--resume', 'session'],
      )
    ]

  with monkeypatch.context() as mp:
    calls = []
    mp.setattr(
      codex,
      '_collect_codex_state',
      lambda _r: _safe_codex_state(
        configs=((CODEX_HOME / 'config.toml', {'profile': 'work'}),)
      ),
    )
    mp.setattr(
      codex,
      'exec_agent',
      lambda root, command, arguments: calls.append(
        (root, command, arguments)
      ),
    )
    with pytest.raises(click.ClickException) as error:
      codex.launch(PROJECT, system_file, ['--resume'], 'gpt-6-astra')
    assert str(error.value) == (
      'Codex filesystem preflight failed:\n'
      f'  - Codex profile selection is not allowed in '
      f'{CODEX_HOME / "config.toml"}: work'
    )
    assert calls == []
