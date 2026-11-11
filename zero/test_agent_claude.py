import json
from pathlib import Path

import click
import pytest

from zero.agent import claude
from zero.agent.common import JsonObject


def _write_json(path: Path, value: JsonObject) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(value), encoding='utf-8')


def _safe_claude_state(
  home: Path,
  project_root: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> Path:
  monkeypatch.delenv(claude.CLAUDE_MCP_SET_ENV, raising=False)
  disabled_servers = list(claude.CLAUDE_MCP_SERVERS)
  settings = home / '.claude' / 'settings.json'
  _write_json(
    settings,
    {'autoMemoryEnabled': False, 'enabledPlugins': {}},
  )
  _write_json(
    home / '.claude.json',
    {
      'disabledMcpServers': disabled_servers,
      'enabledMcpServers': [],
      'mcpServers': {},
      'projects': {
        str(project_root.resolve()): {
          'disabledMcpServers': disabled_servers,
          'enabledMcpServers': [],
          'mcpServers': {},
          'disabledMcpjsonServers': [],
          'enabledMcpjsonServers': [],
        }
      },
    },
  )
  _write_json(project_root / '.mcp.json', {'mcpServers': {}})
  return settings


def test_claude_launch_uses_persistent_disables_and_forwards_arguments(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  project_root = tmp_path / 'project'
  project_root.mkdir()
  settings = _safe_claude_state(home, project_root, monkeypatch)
  monkeypatch.setenv('HOME', str(home))
  monkeypatch.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())
  system_file = project_root / 'sys.md'
  system_file.write_text('system contract\n', encoding='utf-8')
  calls = []
  monkeypatch.setattr(
    claude,
    '_exec_agent',
    lambda root, command, arguments: calls.append(
      (root, command, arguments)
    ),
  )

  claude.launch(
    project_root, system_file, ['--resume', 'session'], 'sonnet'
  )

  assert calls == [
    (
      project_root,
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
  assert settings.is_file()


def test_claude_requires_a_persistent_auto_memory_disable(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  project_root = tmp_path / 'project'
  project_root.mkdir()
  _safe_claude_state(home, project_root, monkeypatch)
  settings = home / '.claude' / 'settings.json'
  _write_json(settings, {'enabledPlugins': {}})
  monkeypatch.setenv('HOME', str(home))
  monkeypatch.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())

  with pytest.raises(click.ClickException) as error:
    claude._check_claude_ambient_state(project_root)

  assert str(error.value) == (
    'Claude filesystem preflight failed:\n'
    '  - Claude auto-memory is not persistently disabled; '
    f'run /memory and disable auto-memory in {settings}'
  )


def test_claude_rejects_standalone_skills_memory_and_enabled_plugins(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  project_root = tmp_path / 'project'
  project_root.mkdir()
  settings = _safe_claude_state(home, project_root, monkeypatch)
  _write_json(
    settings,
    {'autoMemoryEnabled': False, 'enabledPlugins': {'unsafe': True}},
  )
  skill = home / '.claude' / 'skills' / 'search' / 'SKILL.md'
  skill.parent.mkdir(parents=True)
  skill.write_text('skill\n', encoding='utf-8')
  memory = home / '.claude' / 'rules' / 'runtime.md'
  memory.parent.mkdir(parents=True)
  memory.write_text('memory\n', encoding='utf-8')
  monkeypatch.setenv('HOME', str(home))
  monkeypatch.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())

  with pytest.raises(click.ClickException) as error:
    claude._check_claude_ambient_state(project_root)

  assert str(error.value) == (
    'Claude filesystem preflight failed:\n'
    f'  - Claude memory file {memory} is present; remove or rename it '
    'because Claude has no persistent setting to disable CLAUDE.md/rules '
    'memory files\n'
    f"  - Claude plugin 'unsafe' is not disabled in {settings}; "
    'run /plugin and disable unsafe\n'
    f'  - Claude skill {skill} is present; remove or rename it because '
    'Claude has no persistent setting to disable standalone skills'
  )


def test_claude_rejects_an_enabled_mcp_server(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  project_root = tmp_path / 'project'
  project_root.mkdir()
  _safe_claude_state(home, project_root, monkeypatch)
  claude_json = home / '.claude.json'
  value = json.loads(claude_json.read_text(encoding='utf-8'))
  value['mcpServers'] = {'unsafe': {'command': 'unsafe-server'}}
  _write_json(claude_json, value)
  monkeypatch.setenv('HOME', str(home))
  monkeypatch.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())

  with pytest.raises(click.ClickException) as error:
    claude._check_claude_ambient_state(project_root)

  assert str(error.value) == (
    'Claude filesystem preflight failed:\n'
    f"  - Claude MCP server 'unsafe' is not disabled in {claude_json}; "
    'run /mcp and disable unsafe'
  )


def test_claude_rejects_a_project_mcpjson_server(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  project_root = tmp_path / 'project'
  project_root.mkdir()
  _safe_claude_state(home, project_root, monkeypatch)
  mcp_json = project_root / '.mcp.json'
  _write_json(mcp_json, {'mcpServers': {'unsafe': {'command': 'server'}}})
  monkeypatch.setenv('HOME', str(home))
  monkeypatch.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())

  with pytest.raises(click.ClickException) as error:
    claude._check_claude_ambient_state(project_root)

  assert str(error.value) == (
    'Claude filesystem preflight failed:\n'
    f"  - Claude MCP server 'unsafe' is not disabled in {mcp_json}; "
    'run /mcp and disable unsafe'
  )


def test_claude_ignores_plugin_and_project_skills(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  project_root = tmp_path / 'project'
  project_root.mkdir()
  _safe_claude_state(home, project_root, monkeypatch)
  monkeypatch.setenv('HOME', str(home))
  monkeypatch.setattr(claude, 'CLAUDE_MANAGED_SETTINGS_PATHS', ())
  plugin_skill = home / '.claude' / 'plugins' / 'sample' / 'SKILL.md'
  plugin_skill.parent.mkdir(parents=True)
  plugin_skill.write_text('plugin skill\n', encoding='utf-8')
  linked_skill = home / '.claude' / 'skills' / 'plugin' / 'SKILL.md'
  linked_skill.parent.mkdir(parents=True)
  linked_skill.symlink_to(plugin_skill)
  project_skill = (
    project_root / '.claude' / 'skills' / 'local' / 'SKILL.md'
  )
  project_skill.parent.mkdir(parents=True)
  project_skill.write_text('project skill\n', encoding='utf-8')
  project_memory = project_root / 'CLAUDE.md'
  project_memory.write_text('project-specific memory\n', encoding='utf-8')
  project_rule = project_root / '.claude' / 'rules' / 'local.md'
  project_rule.parent.mkdir(parents=True)
  project_rule.write_text('project-specific rule\n', encoding='utf-8')
  plugin_mcp = home / '.claude' / 'plugins' / 'sample' / '.mcp.json'
  plugin_mcp.parent.mkdir(parents=True, exist_ok=True)
  plugin_mcp.write_text(
    '{"mcpServers": {"plugin-server": {"command": "server"}}}',
    encoding='utf-8',
  )

  assert claude._check_claude_ambient_state(project_root) is None


def test_claude_optional_live_mcp_inventory_must_match(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  project_root = tmp_path / 'project'
  project_root.mkdir()
  expected = tuple(sorted(claude.CLAUDE_MCP_SERVERS))
  monkeypatch.setenv(claude.CLAUDE_MCP_SET_ENV, '1')
  monkeypatch.setattr(
    claude, '_probe_claude_mcp_servers', lambda _root: expected
  )

  assert claude._check_claude_mcp_set(project_root) == expected

  monkeypatch.setattr(
    claude,
    '_probe_claude_mcp_servers',
    lambda _root: ('unexpected server',),
  )
  with pytest.raises(click.ClickException) as error:
    claude._check_claude_mcp_set(project_root)

  assert str(error.value) == (
    f'Claude MCP inventory mismatch for {claude.CLAUDE_MCP_SET_ENV}; '
    f'missing from claude mcp list: {", ".join(expected)}; '
    'not in the hardcoded set: unexpected server'
  )


def test_claude_launch_stops_before_exec_when_preflight_fails(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  project_root = tmp_path / 'project'
  system_file = project_root / 'sys.md'
  calls = []

  def reject(root: Path) -> None:
    calls.append(('preflight', root))
    raise click.ClickException('ambient state is unsafe')

  monkeypatch.setattr(claude, '_check_claude_ambient_state', reject)
  monkeypatch.setattr(
    claude,
    '_exec_agent',
    lambda root, command, arguments: calls.append(('exec', root)),
  )

  with pytest.raises(click.ClickException) as error:
    claude.launch(project_root, system_file, ['--resume'], 'sonnet')

  assert str(error.value) == 'ambient state is unsafe'
  assert calls == [('preflight', project_root)]
