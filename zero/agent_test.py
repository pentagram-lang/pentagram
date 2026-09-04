import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import click

from zero.agent import (
  AGY_AGENT_TOOLS,
  CLAUDE_MCP_SERVERS,
  _check_agy_ambient_state,
  _check_claude_ambient_state,
  _check_codex_ambient_state,
  launch,
  launch_agy,
)


class CodexPreflightTest(unittest.TestCase):
  def _safe_codex_home(self, root):
    codex_home = root / 'home' / '.codex'
    codex_home.mkdir(parents=True)
    (codex_home / 'config.toml').write_text(
      '[features]\n'
      'memories = false\n\n'
      'plugins = false\n\n'
      '[memories]\n'
      'use_memories = true\n'
      'generate_memories = true\n'
    )
    return codex_home

  def test_preflight_requires_each_discovered_skill_to_be_disabled(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      skill_file = codex_home / 'skills' / 'system' / 'SKILL.md'
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname = "system"\n---\n')

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          r'Codex skill .* is not disabled.*run /skills and disable',
        ):
          _check_codex_ambient_state(root)

  def test_preflight_ignores_plugin_skills(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      plugin_skill = (
        codex_home
        / '.tmp'
        / 'plugins'
        / 'plugins'
        / 'templates'
        / 'skills'
        / 'calendar'
        / 'SKILL.md'
      )
      plugin_skill.parent.mkdir(parents=True)
      plugin_skill.write_text('---\nname = "calendar"\n---\n')

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_ignores_non_home_skill_and_memory_files(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_codex_home(root)
      skill_file = root / '.agents' / 'skills' / 'sample' / 'SKILL.md'
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname = "sample"\n---\n')
      memory_file = root / '.codex' / 'memories' / 'project.md'
      memory_file.parent.mkdir(parents=True)
      memory_file.write_text('# project rule\n')

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_rejects_home_memory_files(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      memory_file = codex_home / 'memories' / 'session.md'
      memory_file.parent.mkdir(parents=True)
      memory_file.write_text('# memory\n')

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'Codex memory file .*remove or rename',
        ):
          _check_codex_ambient_state(root)

  def test_preflight_ignores_codex_execpolicy_rules(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      rule_file = codex_home / 'rules' / 'default.rules'
      rule_file.parent.mkdir(parents=True)
      rule_file.write_text('')

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_accepts_features_disabled_by_omission(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      (codex_home / 'config.toml').write_text('')

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_accepts_disabled_mcp(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      (codex_home / 'config.toml').write_text(
        '[features]\n'
        'memories = false\n\n'
        'plugins = false\n\n'
        '[memories]\n'
        'use_memories = true\n'
        'generate_memories = true\n\n'
        '[mcp_servers.example]\n'
        'command = "example"\n'
        'enabled = false\n'
      )

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_accepts_disabled_standalone_skill(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      skill_file = codex_home / 'skills' / 'system' / 'SKILL.md'
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname = "system"\n---\n')
      (codex_home / 'config.toml').write_text(
        '[features]\n'
        'memories = false\n'
        'plugins = false\n\n'
        '[[skills.config]]\n'
        f'path = {json.dumps(str(skill_file))}\n'
        'enabled = false\n'
      )

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_rejects_enabled_mcp(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      (codex_home / 'config.toml').write_text(
        '[features]\n'
        'memories = false\n\n'
        'plugins = false\n\n'
        '[memories]\n'
        'use_memories = true\n'
        'generate_memories = true\n\n'
        '[mcp_servers.example]\n'
        'command = "example"\n'
      )

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'MCP server .* is not disabled.*mcp_servers.*enabled = false',
        ):
          _check_codex_ambient_state(root)

  def test_preflight_ignores_plugin_mcp_when_plugins_are_disabled(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      (codex_home / 'config.toml').write_text(
        '[features]\n'
        'memories = false\n'
        'plugins = false\n\n'
        '[memories]\n'
        'use_memories = true\n'
        'generate_memories = true\n\n'
        '[plugins."sample@test".mcp_servers."calendar.server"]\n'
        'enabled = true\n'
      )

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        _check_codex_ambient_state(root)

  def test_preflight_rejects_enabled_plugins(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      codex_home = self._safe_codex_home(root)
      (codex_home / 'config.toml').write_text(
        '[features]\n'
        'memories = false\n'
        'plugins = true\n\n'
        '[memories]\n'
        'use_memories = true\n'
        'generate_memories = true\n'
      )

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home')},
        clear=False,
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'features.plugins is not disabled.*'
          'codex features disable plugins',
        ):
          _check_codex_ambient_state(root)

  def test_codex_launch_runs_preflight_before_exec(self):
    with patch('zero.agent._check_codex_ambient_state') as preflight:
      with patch('zero.agent.shutil.which', return_value='/usr/bin/codex'):
        with patch('zero.agent.os.execvpe') as execvpe:
          launch('codex-luna-yolo', ('--ephemeral',))

    preflight.assert_called_once()
    execvpe.assert_called_once()


class ClaudePreflightTest(unittest.TestCase):
  def _safe_claude_state(self, root):
    home = root / 'home'
    claude_home = home / '.claude'
    claude_home.mkdir(parents=True)
    (claude_home / 'settings.json').write_text(
      json.dumps(
        {
          'autoMemoryEnabled': False,
          'enabledPlugins': {'sample@marketplace': False},
        }
      )
    )
    (home / '.claude.json').write_text(
      json.dumps(
        {
          'projects': {
            str(root.resolve()): {
              'mcpServers': {},
              'disabledMcpServers': list(CLAUDE_MCP_SERVERS),
              'disabledMcpjsonServers': [],
            }
          }
        }
      )
    )
    return home

  def test_preflight_accepts_persistent_disabled_state(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      (root / '.mcp.json').write_text(
        json.dumps({'mcpServers': {'example': {'command': 'example'}}})
      )
      claude_json = json.loads(
        (root / 'home' / '.claude.json').read_text()
      )
      claude_json['projects'][str(root.resolve())][
        'disabledMcpjsonServers'
      ] = ['example']
      (root / 'home' / '.claude.json').write_text(json.dumps(claude_json))

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_claude_ambient_state(root)

  def test_preflight_requires_persistent_auto_memory_setting(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      (root / 'home' / '.claude' / 'settings.json').write_text(
        json.dumps({'enabledPlugins': {}})
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'auto-memory is not persistently disabled.*run /memory',
        ):
          _check_claude_ambient_state(root)

  def test_preflight_requires_each_claude_mcp_to_be_disabled(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      claude_json_path = root / 'home' / '.claude.json'
      claude_json = json.loads(claude_json_path.read_text())
      project = claude_json['projects'][str(root.resolve())]
      project['disabledMcpServers'].remove('claude.ai Google Drive')
      claude_json_path.write_text(json.dumps(claude_json))

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'MCP server .*Google Drive.*is not disabled.*run /mcp',
        ):
          _check_claude_ambient_state(root)

  def test_preflight_can_verify_hardcoded_claude_mcp_set(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      output = '\n'.join(
        f'{name}: https://example.test/mcp - ✔ Connected'
        for name in CLAUDE_MCP_SERVERS
      )

      result = type(
        'Result',
        (),
        {'returncode': 0, 'stderr': '', 'stdout': output},
      )()

      with patch('zero.agent.subprocess.run', return_value=result):
        with patch.dict(
          os.environ,
          {'HOME': str(root / 'home'), 'PENTAGRAM_CLAUDE_MCP_SET': '1'},
          clear=False,
        ):
          _check_claude_ambient_state(root)

  def test_preflight_rejects_stale_hardcoded_claude_mcp_set(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)

      result = type(
        'Result',
        (),
        {
          'returncode': 0,
          'stderr': '',
          'stdout': (
            'claude.ai Gmail: https://example.test/mcp - ✔ Connected\n'
          ),
        },
      )()

      with patch('zero.agent.subprocess.run', return_value=result):
        with patch.dict(
          os.environ,
          {'HOME': str(root / 'home'), 'PENTAGRAM_CLAUDE_MCP_SET': '1'},
          clear=False,
        ):
          with self.assertRaisesRegex(
            click.ClickException, 'Claude MCP inventory mismatch'
          ):
            _check_claude_ambient_state(root)

  def test_preflight_rejects_enabled_plugin(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      (root / 'home' / '.claude' / 'settings.json').write_text(
        json.dumps(
          {'autoMemoryEnabled': False, 'enabledPlugins': {'sample': True}}
        )
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException, 'plugin .* is not disabled.*run /plugin'
        ):
          _check_claude_ambient_state(root)

  def test_preflight_rejects_enabled_mcp(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      claude_json = json.loads(
        (root / 'home' / '.claude.json').read_text()
      )
      project = claude_json['projects'][str(root.resolve())]
      project['mcpServers'] = {'example': {'command': 'example'}}
      (root / 'home' / '.claude.json').write_text(json.dumps(claude_json))

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException, 'MCP server .* is not disabled.*run /mcp'
        ):
          _check_claude_ambient_state(root)

  def test_preflight_rejects_standalone_skill(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      skill_file = (
        root / 'home' / '.claude' / 'skills' / 'sample' / 'SKILL.md'
      )
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname: sample\n---\n')

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'Claude skill .*no persistent setting to disable '
          'standalone skills',
        ):
          _check_claude_ambient_state(root)

  def test_preflight_rejects_home_memory_files(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      memory_file = root / 'home' / '.claude' / 'rules' / 'memory.md'
      memory_file.parent.mkdir(parents=True)
      memory_file.write_text('remember this\n')

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'Claude memory file .*remove or rename',
        ):
          _check_claude_ambient_state(root)

  def test_preflight_ignores_plugin_skill_files(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      skill_file = (
        root
        / 'home'
        / '.claude'
        / 'plugins'
        / 'sample'
        / 'skills'
        / 'sample'
        / 'SKILL.md'
      )
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname: sample\n---\n')

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_claude_ambient_state(root)

  def test_preflight_ignores_non_home_skill_and_memory_files(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_claude_state(root)
      skill_file = root / '.claude' / 'skills' / 'sample' / 'SKILL.md'
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname: sample\n---\n')
      (root / 'CLAUDE.md').write_text('project memory\n')
      rule_file = root / '.claude' / 'rules' / 'project.md'
      rule_file.parent.mkdir(parents=True)
      rule_file.write_text('project rule\n')

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_claude_ambient_state(root)

  def test_claude_launch_runs_preflight_before_exec(self):
    with patch('zero.agent._check_claude_ambient_state') as preflight:
      with patch(
        'zero.agent.shutil.which', return_value='/usr/bin/claude'
      ):
        with patch('zero.agent.os.execvpe') as execvpe:
          launch('claude-sonnet-yolo', ('--print', 'check'))

    preflight.assert_called_once()
    execvpe.assert_called_once()


class AgyPreflightTest(unittest.TestCase):
  def _safe_agy_home(self, root):
    config_root = root / 'home' / '.gemini' / 'config'
    config_root.mkdir(parents=True)
    (config_root / 'config.json').write_text('{}')
    (config_root / 'mcp_config.json').write_text('')
    return config_root

  def test_preflight_rejects_standard_home_skill(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      skill_file = config_root / 'skills' / 'sample' / 'SKILL.md'
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname: sample\n---\n')

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'AGY skill .*no persistent all-skills disable setting',
        ):
          _check_agy_ambient_state(root)

  def test_preflight_rejects_registered_inherited_skill(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      shared_root = root / 'shared-skills' / 'sample'
      shared_root.mkdir(parents=True)
      (shared_root / 'SKILL.md').write_text('---\nname: sample\n---\n')
      shared_config = root / 'shared-skills.json'
      shared_config.write_text(
        json.dumps({'entries': [{'path': str(shared_root.parent)}]})
      )
      (config_root / 'skills.json').write_text(
        json.dumps({'inherits': [{'path': str(shared_config)}]})
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          'AGY skill .*shared-skills.*sample.*no persistent',
        ):
          _check_agy_ambient_state(root)

  def test_preflight_ignores_excluded_registered_skill(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      skills_root = root / 'registered-skills'
      skill_file = skills_root / 'ignored' / 'SKILL.md'
      skill_file.parent.mkdir(parents=True)
      skill_file.write_text('---\nname: ignored\n---\n')
      (config_root / 'skills.json').write_text(
        json.dumps(
          {
            'entries': [
              {'path': str(skills_root), 'exclude': ['^ignored$']}
            ]
          }
        )
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_agy_ambient_state(root)

  def test_preflight_accepts_disabled_plugin_manifest(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      plugin_manifest = config_root / 'plugins' / 'sample' / 'plugin.json'
      plugin_manifest.parent.mkdir(parents=True)
      plugin_manifest.write_text(json.dumps({'disabled': True}))

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_agy_ambient_state(root)

  def test_preflight_rejects_enabled_plugin_override(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      plugin_manifest = config_root / 'plugins' / 'sample' / 'plugin.json'
      plugin_manifest.parent.mkdir(parents=True)
      plugin_manifest.write_text('{}')
      (config_root / 'config.json').write_text(
        json.dumps({'plugins': {'sample': {'enabled': True}}})
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          "AGY plugin 'sample' is enabled",
        ):
          _check_agy_ambient_state(root)

  def test_preflight_accepts_disabled_plugin_override(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      plugin_manifest = config_root / 'plugins' / 'sample' / 'plugin.json'
      plugin_manifest.parent.mkdir(parents=True)
      plugin_manifest.write_text('{}')
      (config_root / 'config.json').write_text(
        json.dumps({'plugins': {'sample': {'enabled': False}}})
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_agy_ambient_state(root)

  def test_preflight_rejects_registered_inherited_plugin(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      plugin_root = root / 'shared-plugins' / 'sample'
      plugin_root.mkdir(parents=True)
      (plugin_root / 'plugin.json').write_text('{}')
      shared_config = root / 'shared-plugins.json'
      shared_config.write_text(
        json.dumps({'entries': [{'path': str(plugin_root.parent)}]})
      )
      (config_root / 'plugins.json').write_text(
        json.dumps({'inherits': [{'path': str(shared_config)}]})
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          "AGY plugin 'sample' is enabled",
        ):
          _check_agy_ambient_state(root)

  def test_preflight_rejects_global_mcp_servers(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      config_root = self._safe_agy_home(root)
      (config_root / 'mcp_config.json').write_text(
        json.dumps({'mcpServers': {'sample': {'command': 'sample'}}})
      )

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException,
          "AGY MCP server 'sample' is configured",
        ):
          _check_agy_ambient_state(root)

  def test_preflight_ignores_builtin_and_project_customizations(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_agy_home(root)
      builtin = (
        root
        / 'home'
        / '.gemini'
        / 'antigravity-cli'
        / 'builtin'
        / 'skills'
        / 'sample'
        / 'SKILL.md'
      )
      builtin.parent.mkdir(parents=True)
      builtin.write_text('---\nname: sample\n---\n')
      project_skill = root / '.agents' / 'skills' / 'sample' / 'SKILL.md'
      project_skill.parent.mkdir(parents=True)
      project_skill.write_text('---\nname: sample\n---\n')
      (root / 'AGENTS.md').write_text('ambient instruction\n')

      with patch.dict(
        os.environ, {'HOME': str(root / 'home')}, clear=False
      ):
        _check_agy_ambient_state(root)

  def test_preflight_does_not_start_agy(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      root = Path(temporary_directory)
      self._safe_agy_home(root)

      with patch.dict(
        os.environ,
        {'HOME': str(root / 'home'), 'PENTAGRAM_AGY_TOOLSET': '1'},
        clear=False,
      ):
        with patch(
          'zero.agent.subprocess.run',
          side_effect=AssertionError(
            'AGY must not run during ambient check'
          ),
        ):
          _check_agy_ambient_state(root)


class AgyLauncherTest(unittest.TestCase):
  def test_launch_agy_declares_write_capable_tool_surface(self):
    system_file = Path('sys.md')
    captured = {}
    calls = []

    def run(command, **kwargs):
      calls.append(command)

      class Result:
        returncode = 0
        stderr = ''

      if '--output-format' in command:
        Result.stdout = json.dumps(
          {'event': 'init', 'init': {'tools': list(AGY_AGENT_TOOLS)}}
        )
        return Result()

      captured['command'] = command
      captured['cwd'] = kwargs['cwd']
      captured['agent_content'] = (
        Path(command[3]) / '.agents' / 'agents' / 'pentagram' / 'agent.md'
      ).read_text()

      return Result()

    with patch('zero.agent.subprocess.run', side_effect=run):
      with patch.dict('os.environ', {'TMPDIR': '/tmp'}, clear=True):
        with self.assertRaises(click.exceptions.Exit):
          launch_agy(Path('.'), system_file, ('--print', 'check'))

    self.assertEqual(captured['command'][0:2], ['agy', '--new-project'])
    self.assertEqual(captured['command'][4:6], ['--agent', 'pentagram'])
    self.assertIn('--dangerously-skip-permissions', captured['command'])
    self.assertEqual(captured['command'][-2:], ['--print', 'check'])
    self.assertEqual(
      captured['agent_content'].split('---\n\n', 1)[0],
      '---\n'
      'name: pentagram\n'
      'description: Pentagram engineering agent governed by the '
      'repository-root system contract.\n'
      'tools:\n'
      + ''.join(f'  - {tool}\n' for tool in AGY_AGENT_TOOLS)
      + 'commandExecutionPolicy: eager\n',
    )
    self.assertEqual(
      captured['agent_content'].split('---\n\n', 1)[1],
      system_file.read_text(),
    )
    self.assertEqual(len(calls), 1)

  def test_launch_agy_preflights_when_toolset_env_is_set(self):
    captured = {}
    calls = []

    def run(command, **kwargs):
      calls.append(command)

      class Result:
        returncode = 0
        stderr = ''
        stdout = json.dumps(
          {'event': 'init', 'init': {'tools': list(AGY_AGENT_TOOLS)}}
        )

      if '--output-format' not in command:
        captured['agent_content'] = (
          Path(command[3])
          / '.agents'
          / 'agents'
          / 'pentagram'
          / 'agent.md'
        ).read_text()
      return Result()

    with patch('zero.agent.subprocess.run', side_effect=run):
      with patch.dict(
        'os.environ',
        {'PENTAGRAM_AGY_TOOLSET': 'future_tool,another_future_tool'},
        clear=False,
      ):
        with self.assertRaises(click.exceptions.Exit):
          launch_agy(Path('.'), Path('sys.md'), ())

    self.assertEqual(len(calls), 2)
    self.assertIn('--output-format', calls[0])
    self.assertIn('--print', calls[0])
    self.assertIn(
      ''.join(f'  - {tool}\n' for tool in AGY_AGENT_TOOLS),
      captured['agent_content'],
    )

  def test_launch_agy_rejects_tool_surface_mismatch(self):
    def run(command, **kwargs):
      class Result:
        returncode = 0
        stderr = ''
        stdout = json.dumps(
          {'event': 'init', 'init': {'tools': list(AGY_AGENT_TOOLS[:-1])}}
        )

      return Result()

    with patch('zero.agent.subprocess.run', side_effect=run):
      with patch.dict(
        'os.environ', {'PENTAGRAM_AGY_TOOLSET': '1'}, clear=False
      ):
        with self.assertRaisesRegex(
          click.ClickException, 'tool surface mismatch'
        ):
          launch_agy(Path('.'), Path('sys.md'), ())


if __name__ == '__main__':
  unittest.main()
