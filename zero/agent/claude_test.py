from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import click
import pytest

from zero.agent.claude import (
  CLAUDE_MCP_SERVERS,
  CLAUDE_MCP_SET_ENV,
  build_claude_command,
  launch,
  parse_mcp_list_output,
  preflight_claude,
)


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  root = Path(
    tempfile.mkdtemp(prefix='zero-agent-claude-', dir='/dev/shm')
  )
  try:
    yield root
  finally:
    shutil.rmtree(root, ignore_errors=True)


def _write_clean_claude_env(home: Path, repo: Path) -> None:
  (home / '.claude' / 'plugins' / 'p1').mkdir(parents=True)
  (home / '.claude' / 'skills' / 'from_plugin').mkdir(parents=True)
  repo.mkdir(parents=True, exist_ok=True)
  resolved_repo = repo.resolve()

  plugin_skill = home / '.claude' / 'plugins' / 'p1' / 'SKILL.md'
  plugin_skill.write_text('# plugin skill', encoding='utf-8')
  (home / '.claude' / 'skills' / 'from_plugin' / 'SKILL.md').symlink_to(
    plugin_skill
  )

  (home / '.claude' / 'settings.json').write_text(
    json.dumps(
      {
        'autoMemoryEnabled': False,
        'enabledPlugins': {'plugin-a@org': False},
      }
    ),
    encoding='utf-8',
  )
  (repo / '.mcp.json').write_text(
    json.dumps({'mcpServers': {'repo_srv': {'command': 'srv'}}}),
    encoding='utf-8',
  )
  (home / '.claude.json').write_text(
    json.dumps(
      {
        'enabledMcpServers': [],
        'mcpServers': {'global_srv': {'command': 'g'}},
        'disabledMcpServers': ['global_srv'],
        'projects': {
          str(resolved_repo): {
            'enabledMcpServers': [],
            'mcpServers': {'proj_srv': {'command': 'p'}},
            'disabledMcpServers': ['proj_srv', *CLAUDE_MCP_SERVERS],
            'disabledMcpjsonServers': ['repo_srv'],
            'enabledMcpjsonServers': [],
          }
        },
      }
    ),
    encoding='utf-8',
  )


def test_parse_mcp_list_output() -> None:
  raw = (
    'Checking MCP server health...\n'
    '\n'
    'claude.ai Gmail: https://gmail.mcp.claude.com/mcp - ! Needs auth\n'
    'claude.ai Google Calendar: https://gcal.mcp.claude.com/mcp - ok\n'
    'claude.ai Google Drive: https://gdrive.mcp.claude.com/mcp - ok\n'
  )
  assert parse_mcp_list_output(raw) == CLAUDE_MCP_SERVERS


def test_claude_clean_launch_and_live_probe(shm_dir: Path) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  _write_clean_claude_env(home, repo)
  sys_file = repo / 'sys.md'
  sys_file.write_text('system', encoding='utf-8')

  probe_calls: list[Path] = []

  def fake_probe(root: Path) -> tuple[str, ...]:
    probe_calls.append(root)
    return CLAUDE_MCP_SERVERS

  recorded: list[tuple[Path, list[str], list[str]]] = []

  def fake_exec(
    root: Path, cmd: Sequence[str], args: Sequence[str]
  ) -> None:
    recorded.append((root, list(cmd), list(args)))

  launch(
    repo,
    'sonnet',
    sys_file,
    ['--continue'],
    home=home,
    environ={},
    managed_paths=(),
    mcp_probe=fake_probe,
    exec_fn=fake_exec,
  )
  assert probe_calls == []

  launch(
    repo,
    'sonnet',
    sys_file,
    ['--continue'],
    home=home,
    environ={CLAUDE_MCP_SET_ENV: '1'},
    managed_paths=(),
    mcp_probe=fake_probe,
    exec_fn=fake_exec,
  )
  assert probe_calls == [repo.resolve()]

  expected_cmd = build_claude_command('sonnet', sys_file)
  assert expected_cmd == [
    'claude',
    '--model',
    'sonnet',
    '--system-prompt-file',
    str(sys_file),
    '--dangerously-skip-permissions',
  ]
  assert recorded == [
    (repo, expected_cmd, ['--continue']),
    (repo, expected_cmd, ['--continue']),
  ]


def test_claude_preflight_failures(shm_dir: Path) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  managed = shm_dir / 'managed-settings.json'
  (home / '.claude' / 'rules').mkdir(parents=True)
  (home / '.claude' / 'skills' / 'custom').mkdir(parents=True)
  (repo / '.claude').mkdir(parents=True)

  user_settings = home / '.claude' / 'settings.json'
  local_settings = repo / '.claude' / 'settings.local.json'
  root_mem = home / 'CLAUDE.md'
  claude_mem = home / '.claude' / 'CLAUDE.md'
  rule_file = home / '.claude' / 'rules' / 'extra.md'
  skill_file = home / '.claude' / 'skills' / 'custom' / 'SKILL.md'
  claude_json = home / '.claude.json'

  user_settings.write_text(
    json.dumps({'enabledPlugins': {'plug@x': True}}),
    encoding='utf-8',
  )
  local_settings.write_text(
    json.dumps({'autoMemoryEnabled': True}),
    encoding='utf-8',
  )
  managed.write_text(
    json.dumps({'enabledPlugins': {'corp@y': False}}),
    encoding='utf-8',
  )
  root_mem.write_text('# root', encoding='utf-8')
  claude_mem.write_text('# claude', encoding='utf-8')
  rule_file.write_text('# rule', encoding='utf-8')
  skill_file.write_text('# skill', encoding='utf-8')
  (repo / '.mcp.json').write_text(
    json.dumps({'mcpServers': {'repo_srv': {'command': 'r'}}}),
    encoding='utf-8',
  )
  resolved_repo = repo.resolve()
  claude_json.write_text(
    json.dumps(
      {
        'enabledMcpServers': ['top_enabled'],
        'mcpServers': {'top_unlisted': {'command': 't'}},
        'disabledMcpServers': [],
        'projects': {
          str(resolved_repo): {
            'enabledMcpServers': ['proj_enabled'],
            'mcpServers': {'proj_srv': {'command': 'p'}},
            'disabledMcpServers': ['claude.ai Gmail'],
            'disabledMcpjsonServers': [],
            'enabledMcpjsonServers': ['repo_srv'],
          }
        },
      }
    ),
    encoding='utf-8',
  )

  def mismatched_probe(root: Path) -> tuple[str, ...]:
    return ('claude.ai Gmail', 'extra.server')

  findings = preflight_claude(
    repo,
    home=home,
    environ={CLAUDE_MCP_SET_ENV: '1'},
    managed_paths=(managed,),
    mcp_probe=mismatched_probe,
  )
  assert findings == (
    f"Claude plugin 'plug@x' is enabled in {user_settings}; "
    'disable via /plugin',
    f'Claude autoMemoryEnabled must be false in {local_settings}; '
    'disable via /memory',
    'Claude autoMemoryEnabled must be set to false in at least one '
    'loaded settings file; disable via /memory',
    'Claude ambient memory file blocks launch '
    f'(no persistent disable setting): {root_mem}',
    'Claude ambient memory file blocks launch '
    f'(no persistent disable setting): {claude_mem}',
    'Claude ambient rule file blocks launch '
    f'(no persistent disable setting): {rule_file}',
    'Claude standalone skill blocks launch '
    f'(no persistent disable setting): {skill_file}',
    f"Claude top-level MCP server 'top_enabled' is enabled in "
    f'{claude_json}; disable via /mcp',
    f"Claude top-level MCP server 'top_unlisted' must be listed in "
    f'disabledMcpServers in {claude_json}; disable via /mcp',
    f"Claude project MCP server 'proj_enabled' is enabled in "
    f'{claude_json}; disable via /mcp',
    f"Claude project MCP server 'claude.ai Google Calendar' must be "
    f"listed in projects['{resolved_repo}'].disabledMcpServers in "
    f'{claude_json}; disable via /mcp',
    f"Claude project MCP server 'claude.ai Google Drive' must be listed "
    f"in projects['{resolved_repo}'].disabledMcpServers in {claude_json}; "
    'disable via /mcp',
    f"Claude project MCP server 'proj_srv' must be listed in "
    f"projects['{resolved_repo}'].disabledMcpServers in {claude_json}; "
    'disable via /mcp',
    f"Claude .mcp.json server 'repo_srv' must be listed in "
    f"projects['{resolved_repo}'].disabledMcpjsonServers in "
    f'{claude_json}; disable via /mcp',
    f"Claude .mcp.json server 'repo_srv' must not appear in "
    f"projects['{resolved_repo}'].enabledMcpjsonServers in {claude_json}; "
    'disable via /mcp',
    'Claude live MCP server set mismatch: '
    "missing=['claude.ai Google Calendar', 'claude.ai Google Drive'], "
    "unexpected=['extra.server']",
  )

  called = False

  def fake_exec(
    root: Path, cmd: Sequence[str], args: Sequence[str]
  ) -> None:
    nonlocal called
    called = True

  with pytest.raises(click.ClickException) as exc_info:
    launch(
      repo,
      'fable',
      repo / 'sys.md',
      (),
      home=home,
      environ={},
      managed_paths=(managed,),
      exec_fn=fake_exec,
    )
  assert called is False
  assert exc_info.value.format_message().startswith(
    'Claude filesystem preflight failed:\n'
  )


def test_claude_missing_state_and_probe_error(shm_dir: Path) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  (home / '.claude').mkdir(parents=True)
  repo.mkdir(parents=True)
  (home / '.claude' / 'settings.json').write_text(
    json.dumps({'autoMemoryEnabled': False}), encoding='utf-8'
  )
  (repo / '.mcp.json').write_text('{"mcpServers": []}', encoding='utf-8')

  def failing_probe(root: Path) -> tuple[str, ...]:
    raise RuntimeError('claude mcp list exited with 1: boom')

  findings = preflight_claude(
    repo,
    home=home,
    environ={CLAUDE_MCP_SET_ENV: '1'},
    managed_paths=(),
    mcp_probe=failing_probe,
  )
  assert findings == (
    'Expected JSON object for mcpServers in '
    f'{repo.resolve() / ".mcp.json"}',
    f'Claude state file {home / ".claude.json"} is missing; '
    'disable MCP servers via /mcp',
    'Claude live MCP probe failed: claude mcp list exited with 1: boom',
  )
