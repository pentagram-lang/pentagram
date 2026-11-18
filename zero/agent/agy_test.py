from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import click
import pytest

from zero.agent.agy import (
  AGY_ADAPTER_RELPATH,
  AGY_AGENT_TOOLS,
  AGY_TOOLSET_ENV,
  launch,
  preflight_agy,
  render_agent_adapter,
  toolset_probe_error,
)


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  root = Path(tempfile.mkdtemp(prefix='zero-agent-agy-', dir='/dev/shm'))
  try:
    yield root
  finally:
    shutil.rmtree(root, ignore_errors=True)


def test_render_agent_adapter() -> None:
  rendered = render_agent_adapter('# System Contract\n')
  expected_tools = '\n'.join(f'  - {tool}' for tool in AGY_AGENT_TOOLS)
  assert rendered == (
    '---\n'
    'name: pentagram\n'
    'description: Pentagram engineering agent governed by the '
    'repository-root system contract.\n'
    'tools:\n'
    f'{expected_tools}\n'
    'commandExecutionPolicy: eager\n'
    '---\n'
    '\n'
    '# System Contract\n'
  )


def test_agy_clean_launch_toolset_probe_and_exit_code(
  shm_dir: Path,
) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  config_dir = home / '.gemini' / 'config'
  (config_dir / 'plugins' / 'plug_cfg_off').mkdir(parents=True)
  (config_dir / 'plugins' / 'plug_manifest_off').mkdir(parents=True)
  (config_dir / 'extra_plugins' / 'plug_filtered_out').mkdir(parents=True)
  repo.mkdir(parents=True)

  (config_dir / 'plugins' / 'plug_cfg_off' / 'plugin.json').write_text(
    '{"name": "plug_cfg_off"}', encoding='utf-8'
  )
  (
    config_dir / 'plugins' / 'plug_manifest_off' / 'plugin.json'
  ).write_text(
    '{"name": "plug_manifest_off", "disabled": true}', encoding='utf-8'
  )
  (
    config_dir / 'extra_plugins' / 'plug_filtered_out' / 'plugin.json'
  ).write_text('{"name": "plug_filtered_out"}', encoding='utf-8')
  (config_dir / 'plugins.json').write_text(
    '{"entries": [{"path": "$EXTRA", "exclude": ["filtered"]}]}',
    encoding='utf-8',
  )
  (config_dir / 'config.json').write_text(
    '{"plugins": {"plug_cfg_off": {"enabled": false}}}',
    encoding='utf-8',
  )
  (config_dir / 'mcp_config.json').write_text('   \n', encoding='utf-8')

  sys_file = repo / 'sys.md'
  sys_file.write_text('# Sys\n', encoding='utf-8')
  env = {
    'EXTRA': str(config_dir / 'extra_plugins'),
    AGY_TOOLSET_ENV: '1',
  }

  seen: list[tuple[list[str], Path, bool, str]] = []
  observed_runtime_dir: Path | None = None

  def fake_run(
    cmd: Sequence[str], cwd: Path, capture: bool
  ) -> subprocess.CompletedProcess[str]:
    nonlocal observed_runtime_dir
    runtime_dir = Path(cmd[cmd.index('--add-dir') + 1])
    observed_runtime_dir = runtime_dir
    adapter_text = (runtime_dir / AGY_ADAPTER_RELPATH).read_text(
      encoding='utf-8'
    )
    seen.append((list(cmd), cwd, capture, adapter_text))
    if capture:
      return subprocess.CompletedProcess(
        list(cmd),
        0,
        stdout=(
          'Starting agy...\n'
          '{"event": "init", "init": {"agent": "pentagram"}}\n'
          '{"event": "result", "result": {"status": "SUCCESS"}}\n'
        ),
        stderr='',
      )
    return subprocess.CompletedProcess(
      list(cmd), -15, stdout='', stderr=''
    )

  with pytest.raises(click.exceptions.Exit) as exc_info:
    launch(
      repo,
      'gemini-3.8-flash-high',
      sys_file,
      ['--help', '--extra'],
      home=home,
      environ=env,
      run_fn=fake_run,
      runtime_parent=shm_dir,
    )

  assert exc_info.value.exit_code == 143
  assert observed_runtime_dir is not None
  assert not observed_runtime_dir.exists()
  expected_adapter = render_agent_adapter('# Sys\n')
  assert seen == [
    (
      [
        'agy',
        '--new-project',
        '--add-dir',
        str(observed_runtime_dir),
        '--agent',
        'pentagram',
        '--model',
        'gemini-3.8-flash-high',
        '--output-format',
        'stream-json',
        '--print',
        'Reply OK and do not call any tools.',
      ],
      repo,
      True,
      expected_adapter,
    ),
    (
      [
        'agy',
        '--new-project',
        '--add-dir',
        str(observed_runtime_dir),
        '--agent',
        'pentagram',
        '--model',
        'gemini-3.8-flash-high',
        '--dangerously-skip-permissions',
        '--help',
        '--extra',
      ],
      repo,
      False,
      expected_adapter,
    ),
  ]


def test_agy_preflight_rejects_skills_rules_mcp_and_plugins(
  shm_dir: Path,
) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  gemini_dir = home / '.gemini'
  config_dir = gemini_dir / 'config'
  (config_dir / 'skills' / 's_dir').mkdir(parents=True)
  (config_dir / 'reg_skills' / 's_keep').mkdir(parents=True)
  (config_dir / 'reg_skills' / 's_keep_skip').mkdir(parents=True)
  (config_dir / 'reg_skills' / 'other_keep').mkdir(parents=True)
  (gemini_dir / 'rules').mkdir(parents=True)
  (home / '.agents' / 'rules').mkdir(parents=True)
  (config_dir / 'rules').mkdir(parents=True)
  (config_dir / 'plugins' / 'p_enabled').mkdir(parents=True)
  (config_dir / 'plugins' / 'p_missing_key').mkdir(parents=True)
  (config_dir / 'plugins' / 'p_no_flag').mkdir(parents=True)
  (repo / 'repo_rules').mkdir(parents=True)

  shared_skill_dir = shm_dir / 'shared_skill'
  shared_skill_dir.mkdir()
  (shared_skill_dir / 'SKILL.md').write_text('# shared', encoding='utf-8')
  (config_dir / 'reg_skills' / 's_alias_skip').symlink_to(shared_skill_dir)
  (config_dir / 'reg_skills' / 's_alias_keep').symlink_to(shared_skill_dir)
  s_alias_keep = config_dir / 'reg_skills' / 's_alias_keep' / 'SKILL.md'

  s_dir = config_dir / 'skills' / 's_dir' / 'SKILL.md'
  s_keep = config_dir / 'reg_skills' / 's_keep' / 'SKILL.md'
  s_skip = config_dir / 'reg_skills' / 's_keep_skip' / 'SKILL.md'
  s_other = config_dir / 'reg_skills' / 'other_keep' / 'SKILL.md'
  s_dir.write_text('# s_dir', encoding='utf-8')
  s_keep.write_text('# s_keep', encoding='utf-8')
  s_skip.write_text('# s_skip', encoding='utf-8')
  s_other.write_text('# s_other', encoding='utf-8')

  (config_dir / 'skills.json').write_text(
    '{"inherits": [{"path": "skills_parent.json", '
    '"include_only": ["^s_"], "exclude": ["skip"]}]}',
    encoding='utf-8',
  )
  (config_dir / 'skills_parent.json').write_text(
    '{"inherits": ["skills.json"], '
    '"entries": [{"path": "reg_skills", "include_only": ["keep"]}]}',
    encoding='utf-8',
  )

  home_agents = home / 'AGENTS.md'
  home_gemini = home / 'GEMINI.md'
  gem_agents = gemini_dir / 'AGENTS.md'
  gem_gemini = gemini_dir / 'GEMINI.md'
  r_gem = gemini_dir / 'rules' / 'a.md'
  r_agents = home / '.agents' / 'rules' / 'b.md'
  r_cfg = config_dir / 'rules' / 'c.md'
  r_repo = repo / 'repo_rules' / 'd.md'
  for p in (
    home_agents,
    home_gemini,
    gem_agents,
    gem_gemini,
    r_gem,
    r_agents,
    r_cfg,
    r_repo,
  ):
    p.write_text('# rule', encoding='utf-8')

  (config_dir / 'rules.json').write_text(
    '{"entries": [{"path": "repo_rules", "include_only": ["^d$"]}]}',
    encoding='utf-8',
  )

  mcp_cfg = config_dir / 'mcp_config.json'
  mcp_cfg.write_text('{"mcpServers": {"srv": {"command": "x"}}}', 'utf-8')

  p_enabled = config_dir / 'plugins' / 'p_enabled' / 'plugin.json'
  p_missing_key = config_dir / 'plugins' / 'p_missing_key' / 'plugin.json'
  p_no_flag = config_dir / 'plugins' / 'p_no_flag' / 'plugin.json'
  p_enabled.write_text('{"disabled": true}', encoding='utf-8')
  p_missing_key.write_text('{"disabled": true}', encoding='utf-8')
  p_no_flag.write_text('{}', encoding='utf-8')
  cfg_json = config_dir / 'config.json'
  cfg_json.write_text(
    '{"plugins": {"p_enabled": {"enabled": true}, "p_missing_key": {}}}',
    encoding='utf-8',
  )

  findings = preflight_agy(repo, home=home, environ={})
  expected_rules = sorted(
    [
      home_agents,
      home_gemini,
      gem_agents,
      gem_gemini,
      r_gem,
      r_agents,
      r_cfg,
      r_repo,
    ]
  )
  assert findings == (
    f'AGY standalone skill blocks launch (no persistent disable setting): '
    f'{s_alias_keep}',
    f'AGY standalone skill blocks launch (no persistent disable setting): '
    f'{s_keep}',
    f'AGY standalone skill blocks launch (no persistent disable setting): '
    f'{s_dir}',
    *(
      'AGY standalone rule file blocks launch '
      f'(no persistent disable setting): {p}'
      for p in expected_rules
    ),
    f"AGY standalone MCP server 'srv' in {mcp_cfg} blocks launch "
    '(no persistent disable setting)',
    f"AGY plugin 'p_enabled' ({p_enabled}) is enabled; "
    f'disable it in {cfg_json}',
    f"AGY plugin 'p_missing_key' override in {cfg_json} "
    'must set boolean enabled',
    f"AGY plugin 'p_no_flag' ({p_no_flag}) must be disabled in {cfg_json} "
    f'or via disabled: true in {p_no_flag}',
  )


def test_agy_missing_inherited_config_fails_closed(shm_dir: Path) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  config_dir = home / '.gemini' / 'config'
  config_dir.mkdir(parents=True)
  repo.mkdir()
  missing_parent = config_dir / 'missing_rules.json'
  (config_dir / 'rules.json').write_text(
    '{"inherits": [{"path": "missing_rules.json"}]}', encoding='utf-8'
  )

  assert preflight_agy(repo, home=home, environ={}) == (
    f'AGY rules inherited config does not exist: {missing_parent}',
  )


def test_toolset_probe_errors(shm_dir: Path) -> None:
  bad_rc = subprocess.CompletedProcess(
    ['agy'], 1, stdout='', stderr='nope'
  )
  assert toolset_probe_error(bad_rc) == (
    'AGY toolset probe exited with 1: nope'
  )

  non_json = subprocess.CompletedProcess(
    ['agy'], 0, stdout='log line only\n', stderr=''
  )
  assert toolset_probe_error(non_json) == (
    'AGY toolset probe did not emit an init event for pentagram'
  )

  wrong_agent = subprocess.CompletedProcess(
    ['agy'],
    0,
    stdout='{"event": "init", "init": {"agent": "other"}}\n',
    stderr='',
  )
  assert toolset_probe_error(wrong_agent) == (
    "AGY toolset probe initialized unexpected agent: 'other'"
  )

  bad_status = subprocess.CompletedProcess(
    ['agy'],
    0,
    stdout=(
      '{"event": "init", "init": {"agent": "pentagram"}}\n'
      '{"event": "result", "result": {"status": "ERROR", '
      '"error": "unknown tool"}}\n'
    ),
    stderr='',
  )
  assert toolset_probe_error(bad_status) == (
    "AGY toolset probe returned non-SUCCESS status: 'ERROR' (unknown tool)"
  )

  missing_result = subprocess.CompletedProcess(
    ['agy'],
    0,
    stdout='{"event": "init", "init": {"agent": "pentagram"}}\n',
    stderr='',
  )
  assert toolset_probe_error(missing_result) == (
    'AGY toolset probe did not emit a SUCCESS result event'
  )

  repo = shm_dir / 'repo'
  home = shm_dir / 'home'
  repo.mkdir()
  home.mkdir()
  sys_file = repo / 'sys.md'
  sys_file.write_text('# Sys', encoding='utf-8')

  def fail_probe(
    cmd: Sequence[str], cwd: Path, capture: bool
  ) -> subprocess.CompletedProcess[str]:
    return bad_status

  with pytest.raises(click.ClickException, match='non-SUCCESS status'):
    launch(
      repo,
      'gemini-3.8-flash-high',
      sys_file,
      (),
      home=home,
      environ={AGY_TOOLSET_ENV: '1'},
      run_fn=fail_probe,
      runtime_parent=shm_dir,
    )
