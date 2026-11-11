import json
from pathlib import Path

import click
import pytest

from zero.agent import codex


def _set_codex_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
  monkeypatch.setenv('HOME', str(home))
  return home / '.codex'


def test_codex_launch_uses_disabled_state_and_forwards_arguments(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  codex_home = _set_codex_home(monkeypatch, home)
  skill = codex_home / 'skills' / 'guide' / 'SKILL.md'
  skill.parent.mkdir(parents=True)
  skill.write_text('skill\n', encoding='utf-8')
  config = codex_home / 'config.toml'
  config.parent.mkdir(parents=True, exist_ok=True)
  config.write_text(
    '[features]\nmemories = false\nplugins = false\n\n'
    '[mcp_servers.docs]\nenabled = false\n\n'
    '[[skills.config]]\npath = "~/.codex/skills/guide/SKILL.md"\n'
    'enabled = false\n',
    encoding='utf-8',
  )
  root = tmp_path / 'project'
  root.mkdir()
  system_file = root / 'sys.md'
  system_file.write_text('system contract\n', encoding='utf-8')
  calls = []
  monkeypatch.setattr(
    codex,
    '_exec_agent',
    lambda project_root, command, arguments: calls.append(
      (project_root, command, arguments)
    ),
  )

  codex.launch(root, system_file, ['--resume', 'session'], 'gpt-6-astra')

  assert calls == [
    (
      root,
      [
        'codex',
        '--model',
        'gpt-6-astra',
        '--config',
        f'model_instructions_file={json.dumps(str(system_file))}',
        '--dangerously-bypass-approvals-and-sandbox',
        '--cd',
        str(root),
      ],
      ['--resume', 'session'],
    )
  ]


def test_codex_allows_omitted_feature_disable_settings(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  codex_home = _set_codex_home(monkeypatch, tmp_path / 'home')
  config = codex_home / 'config.toml'
  config.parent.mkdir(parents=True)
  config.write_text('', encoding='utf-8')

  assert codex._check_codex_ambient_state(tmp_path / 'project') is None


def test_codex_rejects_enabled_features_mcp_and_profile(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  codex_home = _set_codex_home(monkeypatch, tmp_path / 'home')
  config = codex_home / 'config.toml'
  config.parent.mkdir(parents=True)
  config.write_text(
    'profile = "work"\n\n'
    '[features]\nmemories = true\nplugins = true\n\n'
    '[mcp_servers.docs]\nenabled = true\n',
    encoding='utf-8',
  )

  with pytest.raises(click.ClickException) as error:
    codex._check_codex_ambient_state(tmp_path / 'project')

  assert str(error.value) == (
    'Codex filesystem preflight failed:\n'
    f'  - Codex profile selection is not allowed in {config}: work\n'
    f'  - Codex setting features.memories is not disabled; '
    f'run codex features disable memories; this persists the disabled '
    f'state in {config}\n'
    f'  - Codex setting features.plugins is not disabled; '
    f'run codex features disable plugins; this persists the disabled '
    f'state in {config}\n'
    f"  - Codex MCP server 'docs' is not disabled in {config}; "
    f'set [mcp_servers."docs"] enabled = false in {config}'
  )


def test_codex_rejects_a_home_memory_file(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  codex_home = _set_codex_home(monkeypatch, home)
  config = codex_home / 'config.toml'
  config.parent.mkdir(parents=True)
  config.write_text(
    '[features]\nmemories = false\nplugins = false\n',
    encoding='utf-8',
  )
  memory = codex_home / 'memories' / 'note.md'
  memory.parent.mkdir()
  memory.write_text('ambient context\n', encoding='utf-8')

  with pytest.raises(click.ClickException) as error:
    codex._check_codex_ambient_state(tmp_path / 'project')

  assert str(error.value) == (
    'Codex filesystem preflight failed:\n'
    f'  - Codex memory file {memory} is present; remove or rename it '
    'because Codex has no persistent setting to disable memory files'
  )


def test_codex_ignores_plugin_project_and_execution_policy_files(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  home = tmp_path / 'home'
  codex_home = _set_codex_home(monkeypatch, home)
  config = codex_home / 'config.toml'
  config.parent.mkdir(parents=True)
  config.write_text(
    '[features]\nmemories = false\nplugins = false\n', encoding='utf-8'
  )
  plugin_skill = codex_home / 'plugins' / 'example' / 'SKILL.md'
  plugin_skill.parent.mkdir(parents=True)
  plugin_skill.write_text('plugin skill\n', encoding='utf-8')
  plugin_mcp = codex_home / 'plugins' / 'example' / 'mcp_config.json'
  plugin_mcp.write_text(
    '{"mcp_servers": {"plugin-server": {"command": "server"}}}',
    encoding='utf-8',
  )
  linked_skill = codex_home / 'skills' / 'example' / 'SKILL.md'
  linked_skill.parent.mkdir(parents=True)
  linked_skill.symlink_to(plugin_skill)
  project_root = tmp_path / 'project'
  project_skill = project_root / '.codex' / 'skills' / 'local' / 'SKILL.md'
  project_skill.parent.mkdir(parents=True)
  project_skill.write_text('project skill\n', encoding='utf-8')
  project_memory = project_root / '.codex' / 'memories' / 'local.md'
  project_memory.parent.mkdir(parents=True)
  project_memory.write_text('project-specific memory\n', encoding='utf-8')
  execution_policy = codex_home / 'rules' / 'execution-policy.md'
  execution_policy.parent.mkdir()
  execution_policy.write_text('policy\n', encoding='utf-8')

  assert codex._check_codex_ambient_state(project_root) is None


def test_codex_requires_each_standalone_skill_to_be_disabled(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  codex_home = _set_codex_home(monkeypatch, tmp_path / 'home')
  config = codex_home / 'config.toml'
  config.parent.mkdir(parents=True)
  config.write_text(
    '[features]\nmemories = false\nplugins = false\n',
    encoding='utf-8',
  )
  skill = codex_home / 'skills' / 'search' / 'SKILL.md'
  skill.parent.mkdir(parents=True)
  skill.write_text('search skill\n', encoding='utf-8')

  with pytest.raises(click.ClickException) as error:
    codex._check_codex_ambient_state(tmp_path / 'project')

  assert str(error.value) == (
    'Codex filesystem preflight failed:\n'
    f'  - Codex skill {skill} is not disabled; run /skills and disable '
    f'{skill}'
  )


def test_codex_launch_stops_before_exec_when_preflight_fails(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  project_root = tmp_path / 'project'
  system_file = project_root / 'sys.md'
  calls = []

  def reject(root: Path) -> None:
    calls.append(('preflight', root))
    raise click.ClickException('ambient state is unsafe')

  monkeypatch.setattr(codex, '_check_codex_ambient_state', reject)
  monkeypatch.setattr(
    codex,
    '_exec_agent',
    lambda root, command, arguments: calls.append(('exec', root)),
  )

  with pytest.raises(click.ClickException) as error:
    codex.launch(project_root, system_file, ['--resume'], 'gpt-6-astra')

  assert str(error.value) == 'ambient state is unsafe'
  assert calls == [('preflight', project_root)]
