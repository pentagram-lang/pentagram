from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import click

from zero.agent.common import (
  ExecFn,
  check_ambient_file,
  exec_agent,
  is_under,
  json_object,
  raise_preflight,
  read_json_file,
  scan_ambient_files,
  string_list,
)

CLAUDE_MCP_SET_ENV = 'PENTAGRAM_CLAUDE_MCP_SET'
CLAUDE_MCP_SERVERS = (
  'claude.ai Gmail',
  'claude.ai Google Calendar',
  'claude.ai Google Drive',
)
CLAUDE_MANAGED_SETTINGS_PATHS = (
  Path('/etc/claude-code/managed-settings.json'),
  Path('/Library/Application Support/ClaudeCode/managed-settings.json'),
)

McpProbeFn = Callable[[Path], tuple[str, ...]]


def parse_mcp_list_output(output: str) -> tuple[str, ...]:
  servers: list[str] = []
  for line in output.splitlines():
    if ':' not in line or ' - ' not in line:
      continue
    name = line.split(':', 1)[0].strip()
    if name:
      servers.append(name)
  return tuple(servers)


def _probe_claude_mcp(project_root: Path) -> tuple[str, ...]:
  proc = subprocess.run(
    ['claude', 'mcp', 'list'],
    cwd=project_root,
    capture_output=True,
    text=True,
    check=False,
  )
  if proc.returncode != 0:
    detail = proc.stderr.strip() or proc.stdout.strip()
    raise RuntimeError(
      f'claude mcp list exited with {proc.returncode}: {detail}'
    )
  return parse_mcp_list_output(proc.stdout)


def _check_settings_files(
  home: Path,
  resolved_root: Path,
  managed_paths: Sequence[Path],
) -> list[str]:
  findings: list[str] = []
  candidates = [
    ('Claude user settings', home / '.claude' / 'settings.json'),
    (
      'Claude project settings',
      resolved_root / '.claude' / 'settings.json',
    ),
    (
      'Claude local settings',
      resolved_root / '.claude' / 'settings.local.json',
    ),
    *(('Claude managed settings', path) for path in managed_paths),
  ]

  seen: set[Path] = set()
  saw_auto_memory_disabled = False

  for label, path in candidates:
    resolved = path.resolve()
    if resolved in seen:
      continue
    seen.add(resolved)
    data, err = read_json_file(path, label)
    if err is not None:
      findings.append(err)
      continue
    if data is None:
      continue

    if 'autoMemoryEnabled' in data:
      auto_mem = data['autoMemoryEnabled']
      if auto_mem is False:
        saw_auto_memory_disabled = True
      else:
        findings.append(
          f'Claude autoMemoryEnabled must be false in {path}; '
          'disable via /memory'
        )

    if 'enabledPlugins' in data:
      plugins = json_object(data['enabledPlugins'])
      if plugins is None:
        findings.append(
          f'Expected JSON object for enabledPlugins in {path}'
        )
      else:
        for name, enabled in sorted(plugins.items()):
          if enabled is not False:
            findings.append(
              f'Claude plugin {name!r} is enabled in {path}; '
              'disable via /plugin'
            )

  if not saw_auto_memory_disabled:
    findings.append(
      'Claude autoMemoryEnabled must be set to false in at least one '
      'loaded settings file; disable via /memory'
    )
  return findings


def _check_ambient_claude_files(home: Path) -> list[str]:
  findings: list[str] = []
  claude_dir = home / '.claude'

  for mem_path in (home / 'CLAUDE.md', claude_dir / 'CLAUDE.md'):
    found, err = check_ambient_file(mem_path, label='Claude memory file')
    if err is not None:
      findings.append(err)
    elif found is not None:
      findings.append(
        'Claude ambient memory file blocks launch '
        f'(no persistent disable setting): {found}'
      )

  rule_files, rule_errors = scan_ambient_files(
    claude_dir / 'rules', label='Claude rules', suffix='.md'
  )
  findings.extend(rule_errors)
  for rule_file in rule_files:
    findings.append(
      'Claude ambient rule file blocks launch '
      f'(no persistent disable setting): {rule_file}'
    )

  skill_files, skill_errors = scan_ambient_files(
    claude_dir / 'skills', label='Claude skills', match_name='SKILL.md'
  )
  findings.extend(skill_errors)
  plugins_dir = claude_dir / 'plugins'
  for skill_file in skill_files:
    if is_under(skill_file, plugins_dir):
      continue
    findings.append(
      'Claude standalone skill blocks launch '
      f'(no persistent disable setting): {skill_file}'
    )

  return findings


def _check_top_level_mcp(
  claude_json: dict[str, object], claude_json_path: Path
) -> list[str]:
  findings: list[str] = []

  if 'enabledMcpServers' in claude_json:
    enabled_top = string_list(claude_json['enabledMcpServers'])
    if enabled_top is None:
      findings.append(
        f'Expected string list for enabledMcpServers in {claude_json_path}'
      )
    else:
      for name in sorted(enabled_top):
        findings.append(
          f'Claude top-level MCP server {name!r} is enabled in '
          f'{claude_json_path}; disable via /mcp'
        )

  disabled_top: list[str] | None = []
  if 'disabledMcpServers' in claude_json:
    disabled_top = string_list(claude_json['disabledMcpServers'])
    if disabled_top is None:
      findings.append(
        'Expected string list for disabledMcpServers in '
        f'{claude_json_path}'
      )

  if 'mcpServers' in claude_json:
    mcp_top = json_object(claude_json['mcpServers'])
    if mcp_top is None:
      findings.append(
        f'Expected JSON object for mcpServers in {claude_json_path}'
      )
    elif disabled_top is not None:
      disabled_set = set(disabled_top)
      for name in sorted(mcp_top):
        if name not in disabled_set:
          findings.append(
            f'Claude top-level MCP server {name!r} must be listed in '
            f'disabledMcpServers in {claude_json_path}; disable via /mcp'
          )

  return findings


def _check_project_mcp(
  claude_json: dict[str, object],
  claude_json_path: Path,
  resolved_root: Path,
  repo_mcp_servers: dict[str, object] | None,
) -> list[str]:
  findings: list[str] = []
  root_key = str(resolved_root)

  projects = (
    json_object(claude_json['projects'])
    if 'projects' in claude_json
    else None
  )
  if 'projects' in claude_json and projects is None:
    findings.append(
      f'Expected JSON object for projects in {claude_json_path}'
    )
    return findings

  project_raw = None if projects is None else projects.get(root_key)
  if project_raw is None:
    findings.append(
      f'Claude project entry projects[{root_key!r}] missing in '
      f'{claude_json_path}; disable Claude.ai MCP servers via /mcp'
    )
    return findings

  project_obj = json_object(project_raw)
  if project_obj is None:
    findings.append(
      f'Expected JSON object for projects[{root_key!r}] in '
      f'{claude_json_path}'
    )
    return findings

  if 'enabledMcpServers' in project_obj:
    enabled_proj = string_list(project_obj['enabledMcpServers'])
    if enabled_proj is None:
      findings.append(
        f'Expected string list for projects[{root_key!r}].'
        f'enabledMcpServers in {claude_json_path}'
      )
    else:
      for name in sorted(enabled_proj):
        findings.append(
          f'Claude project MCP server {name!r} is enabled in '
          f'{claude_json_path}; disable via /mcp'
        )

  disabled_proj: list[str] | None = []
  if 'disabledMcpServers' in project_obj:
    disabled_proj = string_list(project_obj['disabledMcpServers'])
    if disabled_proj is None:
      findings.append(
        f'Expected string list for projects[{root_key!r}].'
        f'disabledMcpServers in {claude_json_path}'
      )

  required_disabled = set(CLAUDE_MCP_SERVERS)
  if 'mcpServers' in project_obj:
    proj_mcp = json_object(project_obj['mcpServers'])
    if proj_mcp is None:
      findings.append(
        f'Expected JSON object for projects[{root_key!r}].mcpServers '
        f'in {claude_json_path}'
      )
    else:
      required_disabled.update(proj_mcp.keys())

  if disabled_proj is not None:
    disabled_proj_set = set(disabled_proj)
    for name in sorted(required_disabled):
      if name not in disabled_proj_set:
        findings.append(
          f'Claude project MCP server {name!r} must be listed in '
          f'projects[{root_key!r}].disabledMcpServers in '
          f'{claude_json_path}; disable via /mcp'
        )

  if repo_mcp_servers:
    disabled_mcpjson = string_list(
      project_obj.get('disabledMcpjsonServers', [])
    )
    if disabled_mcpjson is None:
      findings.append(
        f'Expected string list for projects[{root_key!r}].'
        f'disabledMcpjsonServers in {claude_json_path}'
      )
    enabled_mcpjson = string_list(
      project_obj.get('enabledMcpjsonServers', [])
    )
    if enabled_mcpjson is None:
      findings.append(
        f'Expected string list for projects[{root_key!r}].'
        f'enabledMcpjsonServers in {claude_json_path}'
      )
    if disabled_mcpjson is not None and enabled_mcpjson is not None:
      disabled_set = set(disabled_mcpjson)
      enabled_set = set(enabled_mcpjson)
      for name in sorted(repo_mcp_servers):
        if name not in disabled_set:
          findings.append(
            f'Claude .mcp.json server {name!r} must be listed in '
            f'projects[{root_key!r}].disabledMcpjsonServers in '
            f'{claude_json_path}; disable via /mcp'
          )
        if name in enabled_set:
          findings.append(
            f'Claude .mcp.json server {name!r} must not appear in '
            f'projects[{root_key!r}].enabledMcpjsonServers in '
            f'{claude_json_path}; disable via /mcp'
          )

  return findings


def preflight_claude(
  project_root: Path,
  *,
  home: Path | None = None,
  environ: Mapping[str, str] | None = None,
  managed_paths: Sequence[Path] = CLAUDE_MANAGED_SETTINGS_PATHS,
  mcp_probe: McpProbeFn = _probe_claude_mcp,
) -> tuple[str, ...]:
  resolved_home = Path.home() if home is None else home
  resolved_env = os.environ if environ is None else environ
  resolved_root = project_root.resolve()

  findings = _check_settings_files(
    resolved_home, resolved_root, managed_paths
  )
  findings.extend(_check_ambient_claude_files(resolved_home))

  repo_mcp_data, repo_mcp_err = read_json_file(
    resolved_root / '.mcp.json', 'Claude project MCP config'
  )
  if repo_mcp_err is not None:
    findings.append(repo_mcp_err)
  repo_mcp_servers: dict[str, object] | None = None
  if repo_mcp_data is not None and 'mcpServers' in repo_mcp_data:
    repo_mcp_servers = json_object(repo_mcp_data['mcpServers'])
    if repo_mcp_servers is None:
      findings.append(
        f'Expected JSON object for mcpServers in '
        f'{resolved_root / ".mcp.json"}'
      )

  claude_json_path = resolved_home / '.claude.json'
  claude_json, claude_json_err = read_json_file(
    claude_json_path, 'Claude state file'
  )
  if claude_json_err is not None:
    findings.append(claude_json_err)
  elif claude_json is None:
    findings.append(
      f'Claude state file {claude_json_path} is missing; '
      'disable MCP servers via /mcp'
    )
  else:
    findings.extend(_check_top_level_mcp(claude_json, claude_json_path))
    findings.extend(
      _check_project_mcp(
        claude_json, claude_json_path, resolved_root, repo_mcp_servers
      )
    )

  if CLAUDE_MCP_SET_ENV in resolved_env:
    try:
      live_servers = mcp_probe(resolved_root)
    except (OSError, RuntimeError, click.ClickException) as err:
      findings.append(f'Claude live MCP probe failed: {err}')
    else:
      expected = set(CLAUDE_MCP_SERVERS)
      actual = set(live_servers)
      if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        findings.append(
          f'Claude live MCP server set mismatch: '
          f'missing={missing}, unexpected={extra}'
        )

  return tuple(findings)


def build_claude_command(model: str, system_file: Path) -> list[str]:
  return [
    'claude',
    '--model',
    model,
    '--system-prompt-file',
    str(system_file),
    '--dangerously-skip-permissions',
  ]


def launch(
  project_root: Path,
  model: str,
  system_file: Path,
  arguments: Sequence[str],
  *,
  home: Path | None = None,
  environ: Mapping[str, str] | None = None,
  managed_paths: Sequence[Path] = CLAUDE_MANAGED_SETTINGS_PATHS,
  mcp_probe: McpProbeFn = _probe_claude_mcp,
  exec_fn: ExecFn = exec_agent,
) -> None:
  resolved_root = project_root.resolve()
  resolved_system = system_file.resolve()
  findings = preflight_claude(
    resolved_root,
    home=home,
    environ=environ,
    managed_paths=managed_paths,
    mcp_probe=mcp_probe,
  )
  raise_preflight('Claude', findings)
  command = build_claude_command(model, resolved_system)
  exec_fn(resolved_root, command, arguments)
