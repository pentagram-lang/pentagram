import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import click

from zero.lib import json_object, string_list

from .common import (
  JsonObject,
  check_ambient_file,
  exec_agent,
  is_under,
  read_json_file,
  scan_ambient_files,
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


@dataclass(frozen=True, slots=True)
class ClaudeState:
  home: Path
  project_root: Path
  settings: tuple[tuple[Path, JsonObject], ...]
  claude_json_path: Path
  claude_json: JsonObject | None
  mcp_json_path: Path
  mcp_json: JsonObject | None
  memory_files: tuple[Path, ...]
  skill_files: tuple[Path, ...]
  live_mcp_servers: tuple[str, ...] | None
  read_findings: tuple[str, ...] = ()


def _claude_settings_paths(home: Path, project_root: Path) -> list[Path]:
  paths = [
    home / '.claude' / 'settings.json',
    project_root / '.claude' / 'settings.json',
    project_root / '.claude' / 'settings.local.json',
    *CLAUDE_MANAGED_SETTINGS_PATHS,
  ]
  unique_paths: list[Path] = []
  seen: set[Path] = set()
  for path in paths:
    resolved = path.expanduser().resolve()
    if resolved not in seen:
      seen.add(resolved)
      unique_paths.append(resolved)
  return unique_paths


def _claude_memory_files(
  home: Path, findings: list[str]
) -> tuple[Path, ...]:
  files: set[Path] = set()
  for path in (home / 'CLAUDE.md', home / '.claude' / 'CLAUDE.md'):
    resolved, error = check_ambient_file(path, label='Claude rules')
    if error is not None:
      findings.append(error)
    elif resolved is not None:
      files.add(resolved)
  scanned, scan_findings = scan_ambient_files(
    home / '.claude' / 'rules', label='Claude rules', suffix='.md'
  )
  findings.extend(scan_findings)
  files.update(scanned)
  return tuple(sorted(files))


def _claude_skill_files(
  home: Path, findings: list[str]
) -> tuple[Path, ...]:
  plugin_dir = home / '.claude' / 'plugins'
  try:
    plugin_root = plugin_dir.resolve()
  except OSError:
    plugin_root = plugin_dir

  scanned, scan_findings = scan_ambient_files(
    home / '.claude' / 'skills',
    label='Claude skills',
    match_name='SKILL.md',
    allow_single_file=True,
  )
  findings.extend(scan_findings)
  return tuple(
    resolved for resolved in scanned if not is_under(resolved, plugin_root)
  )


def parse_mcp_list_output(stdout: str) -> tuple[str, ...]:
  """Extract configured MCP server names from `claude mcp list` stdout."""
  servers: set[str] = set()
  for line in stdout.splitlines():
    line = line.strip()
    if ':' not in line or ' - ' not in line:
      continue
    name = line.split(':', 1)[0].strip()
    if name:
      servers.add(name)
  return tuple(sorted(servers))


def _probe_claude_mcp_servers(project_root: Path) -> tuple[str, ...]:
  try:
    result = subprocess.run(
      ['claude', 'mcp', 'list'],
      cwd=project_root,
      env=os.environ,
      capture_output=True,
      text=True,
      encoding='utf-8',
      errors='replace',
    )
  except OSError as error:
    raise click.ClickException(
      f'Claude MCP inventory preflight failed: {error}'
    ) from error
  if result.returncode != 0:
    detail = result.stderr.strip() or 'no diagnostic output'
    raise click.ClickException(
      f'Claude MCP inventory preflight failed: {detail}'
    )
  return parse_mcp_list_output(result.stdout)


def claude_mcp_set_error(
  live_mcp_servers: Sequence[str] | None,
) -> str | None:
  """Return mismatch message if live_mcp_servers differs from expected."""
  if live_mcp_servers is None:
    return None
  expected = set(CLAUDE_MCP_SERVERS)
  actual = set(live_mcp_servers)
  if actual == expected:
    return None
  missing = ', '.join(sorted(expected - actual)) or 'none'
  extra = ', '.join(sorted(actual - expected)) or 'none'
  return (
    f'Claude MCP inventory mismatch for {CLAUDE_MCP_SET_ENV}; '
    f'missing from claude mcp list: {missing}; '
    f'not in the hardcoded set: {extra}'
  )


def _collect_claude_state(project_root: Path) -> ClaudeState:
  home = Path.home().resolve()
  resolved_root = project_root.resolve()
  findings: list[str] = []
  settings: list[tuple[Path, JsonObject]] = []
  for path in _claude_settings_paths(home, resolved_root):
    config, error = read_json_file(path, 'Claude settings')
    if error is not None:
      findings.append(error)
    elif config is not None:
      settings.append((path, config))

  claude_json_path = home / '.claude.json'
  claude_json, claude_json_error = read_json_file(
    claude_json_path, 'Claude MCP configuration'
  )
  if claude_json_error is not None:
    findings.append(claude_json_error)

  mcp_json_path = resolved_root / '.mcp.json'
  mcp_json, mcp_json_error = read_json_file(
    mcp_json_path, 'Claude project MCP configuration'
  )
  if mcp_json_error is not None:
    findings.append(mcp_json_error)

  live_mcp_servers = (
    _probe_claude_mcp_servers(resolved_root)
    if CLAUDE_MCP_SET_ENV in os.environ
    else None
  )
  memory_files = _claude_memory_files(home, findings)
  skill_files = _claude_skill_files(home, findings)
  return ClaudeState(
    home=home,
    project_root=resolved_root,
    settings=tuple(settings),
    claude_json_path=claude_json_path,
    claude_json=claude_json,
    mcp_json_path=mcp_json_path,
    mcp_json=mcp_json,
    memory_files=memory_files,
    skill_files=skill_files,
    live_mcp_servers=live_mcp_servers,
    read_findings=tuple(findings),
  )


def _claude_plugin_findings(
  settings: Sequence[tuple[Path, JsonObject]],
) -> list[str]:
  findings: list[str] = []
  for settings_path, config in settings:
    plugins = json_object(config.get('enabledPlugins', {}))
    if plugins is None:
      findings.append(
        'Invalid enabledPlugins setting in Claude settings '
        f'{settings_path}'
      )
      continue
    for name, enabled in sorted(plugins.items()):
      if enabled is not False:
        findings.append(
          f'Claude plugin {name!r} is not disabled in {settings_path}; '
          f'run /plugin and disable {name}'
        )
  return findings


def _claude_memory_findings(
  home: Path,
  settings: Sequence[tuple[Path, JsonObject]],
  memory_files: Sequence[Path],
) -> list[str]:
  findings: list[str] = []
  values: list[tuple[bool, Path]] = []
  for settings_path, config in settings:
    if 'autoMemoryEnabled' not in config:
      continue
    value = config['autoMemoryEnabled']
    if not isinstance(value, bool):
      findings.append(
        f'Invalid autoMemoryEnabled setting in Claude settings '
        f'{settings_path}'
      )
    else:
      values.append((value, settings_path))

  enabled_path = next(
    (path for value, path in values if value is not False),
    None,
  )
  if enabled_path is not None or not values:
    target = enabled_path or (home / '.claude' / 'settings.json')
    findings.append(
      'Claude auto-memory is not persistently disabled; '
      f'run /memory and disable auto-memory in {target}'
    )

  for memory_file in memory_files:
    findings.append(
      f'Claude memory file {memory_file} is present; remove or rename it '
      'because Claude has no persistent setting to disable CLAUDE.md/rules'
      ' memory files'
    )
  return findings


def _claude_mcp_names(
  config: JsonObject,
  key: str,
  label: str | Path,
  findings: list[str],
) -> set[str]:
  names = string_list(config.get(key, []))
  if names is None:
    findings.append(f'Invalid {key} setting in {label}')
    return set()
  return set(names)


def _claude_mcp_findings(
  state: ClaudeState, known_servers: Sequence[str]
) -> list[str]:
  findings: list[str] = []
  project_disabled: set[str] = set()
  project_disabled_json: set[str] = set()
  project_enabled_json: set[str] = set()
  claude_json_path = state.claude_json_path
  claude_json = state.claude_json
  if claude_json is not None:
    disabled = _claude_mcp_names(
      claude_json, 'disabledMcpServers', claude_json_path, findings
    )
    enabled = _claude_mcp_names(
      claude_json, 'enabledMcpServers', claude_json_path, findings
    )
    for name in sorted(enabled):
      findings.append(
        f'Claude MCP server {name!r} is explicitly enabled in '
        f'{claude_json_path}; run /mcp and disable {name}'
      )
    servers = json_object(claude_json.get('mcpServers', {}))
    if servers is None:
      findings.append(f'Invalid mcpServers setting in {claude_json_path}')
    else:
      for name in sorted(servers):
        if name not in disabled:
          findings.append(
            f'Claude MCP server {name!r} is not disabled in '
            f'{claude_json_path}; run /mcp and disable {name}'
          )

    projects = json_object(claude_json.get('projects', {}))
    if projects is None:
      findings.append(f'Invalid projects setting in {claude_json_path}')
    else:
      project_config = json_object(
        projects.get(str(state.project_root), {})
      )
      if project_config is None:
        findings.append(
          f'Invalid Claude project configuration in {claude_json_path}'
        )
      else:
        project_disabled = _claude_mcp_names(
          project_config, 'disabledMcpServers', claude_json_path, findings
        )
        project_enabled = _claude_mcp_names(
          project_config, 'enabledMcpServers', claude_json_path, findings
        )
        for name in sorted(project_enabled):
          findings.append(
            f'Claude MCP server {name!r} is explicitly enabled in '
            f'{claude_json_path}; run /mcp and disable {name}'
          )
        project_servers = json_object(project_config.get('mcpServers', {}))
        if project_servers is None:
          findings.append(
            f'Invalid project mcpServers setting in {claude_json_path}'
          )
        else:
          for name in sorted(project_servers):
            if name not in project_disabled:
              findings.append(
                f'Claude MCP server {name!r} is not disabled in '
                f'{claude_json_path}; run /mcp and disable {name}'
              )

        project_disabled_json = _claude_mcp_names(
          project_config,
          'disabledMcpjsonServers',
          claude_json_path,
          findings,
        )
        project_enabled_json = _claude_mcp_names(
          project_config,
          'enabledMcpjsonServers',
          claude_json_path,
          findings,
        )

  mcp_json_path = state.mcp_json_path
  mcp_json = state.mcp_json
  if mcp_json is not None:
    servers = json_object(mcp_json.get('mcpServers', {}))
    if servers is None:
      findings.append(f'Invalid mcpServers setting in {mcp_json_path}')
    else:
      for name in sorted(project_enabled_json):
        if name in servers:
          findings.append(
            f'Claude MCP server {name!r} is explicitly enabled in '
            f'{claude_json_path}; run /mcp and disable {name}'
          )
      for name in sorted(servers):
        if name not in project_disabled_json:
          findings.append(
            f'Claude MCP server {name!r} is not disabled in '
            f'{mcp_json_path}; run /mcp and disable {name}'
          )

  for name in sorted(set(known_servers)):
    if name not in project_disabled:
      findings.append(
        f'Claude MCP server {name!r} is not disabled in '
        f'{claude_json_path}; run /mcp and disable {name}'
      )
  return findings


def claude_preflight_findings(state: ClaudeState) -> tuple[str, ...]:
  """Evaluate all pure Claude preflight invariants against ClaudeState."""
  findings = list(state.read_findings)
  findings.extend(
    _claude_memory_findings(state.home, state.settings, state.memory_files)
  )
  findings.extend(_claude_plugin_findings(state.settings))
  findings.extend(_claude_mcp_findings(state, sorted(CLAUDE_MCP_SERVERS)))
  for skill_file in state.skill_files:
    findings.append(
      f'Claude skill {skill_file} is present; remove or rename it because '
      'Claude has no persistent setting to disable standalone skills'
    )
  return tuple(findings)


def build_launch_command(system_file: Path, model: str) -> list[str]:
  """Build the Claude CLI command line."""
  return [
    'claude',
    '--model',
    model,
    '--system-prompt-file',
    str(system_file),
    '--dangerously-skip-permissions',
  ]


def _check_claude_ambient_state(project_root: Path) -> None:
  state = _collect_claude_state(project_root)
  mcp_error = claude_mcp_set_error(state.live_mcp_servers)
  if mcp_error is not None:
    raise click.ClickException(mcp_error)
  findings = claude_preflight_findings(state)
  if findings:
    detail = '\n'.join(f'  - {finding}' for finding in findings)
    raise click.ClickException(
      f'Claude filesystem preflight failed:\n{detail}'
    )


def launch(
  project_root: Path,
  system_file: Path,
  arguments: Sequence[str],
  model: str,
) -> None:
  """Run Claude preflight checks and replace the process with claude."""
  _check_claude_ambient_state(project_root)
  exec_agent(
    project_root, build_launch_command(system_file, model), arguments
  )
