import os
import subprocess
from collections.abc import Sequence
from pathlib import Path

import click

from .common import (
  JsonObject,
  _exec_agent,
  _is_under,
  _json_object,
  _read_json_file,
  _string_list,
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


def _claude_settings_paths(project_root: Path) -> list[Path]:
  paths = [
    Path.home() / '.claude' / 'settings.json',
    project_root / '.claude' / 'settings.json',
    project_root / '.claude' / 'settings.local.json',
    *CLAUDE_MANAGED_SETTINGS_PATHS,
  ]
  unique_paths = []
  seen = set()
  for path in paths:
    resolved = path.expanduser().resolve()
    if resolved not in seen:
      seen.add(resolved)
      unique_paths.append(resolved)
  return unique_paths


def _read_claude_settings(
  project_root: Path,
) -> tuple[list[tuple[Path, JsonObject]], list[str]]:
  settings: list[tuple[Path, JsonObject]] = []
  findings: list[str] = []
  for path in _claude_settings_paths(project_root):
    config = _read_json_file(path, 'Claude settings', findings)
    if config is not None:
      settings.append((path, config))
  return settings, findings


def _claude_memory_files() -> list[Path]:
  files: list[Path] = []
  seen: set[Path] = set()
  home = Path.home().resolve()
  for path in (home / 'CLAUDE.md', home / '.claude' / 'CLAUDE.md'):
    resolved = path.resolve()
    if resolved.is_file() and resolved not in seen:
      seen.add(resolved)
      files.append(resolved)
  root = home / '.claude' / 'rules'
  if root.is_dir():
    for path in root.rglob('*.md'):
      resolved = path.resolve()
      if resolved not in seen:
        seen.add(resolved)
        files.append(resolved)
  return sorted(files)


def _claude_plugin_roots() -> tuple[Path, ...]:
  return ((Path.home() / '.claude' / 'plugins').expanduser().resolve(),)


def _claude_skill_files() -> list[Path]:
  roots = [Path.home() / '.claude' / 'skills']
  plugin_roots = _claude_plugin_roots()
  skill_files = []
  seen_roots: set[Path] = set()
  seen_files: set[Path] = set()
  for root in roots:
    root = root.expanduser().resolve()
    if root in seen_roots or not root.exists():
      continue
    seen_roots.add(root)
    if root.is_file() and root.name == 'SKILL.md':
      candidates = [root]
    elif root.is_dir():
      try:
        candidates = root.rglob('SKILL.md')
      except OSError:
        candidates = ()
    else:
      candidates = ()
    for candidate in candidates:
      try:
        resolved = candidate.resolve()
      except OSError:
        continue
      if any(
        _is_under(resolved, plugin_root) for plugin_root in plugin_roots
      ):
        continue
      if resolved not in seen_files:
        seen_files.add(resolved)
        skill_files.append(resolved)
  return sorted(skill_files)


def _claude_plugin_findings(
  settings: Sequence[tuple[Path, JsonObject]],
) -> list[str]:
  findings: list[str] = []
  for settings_path, config in settings:
    plugins = config.get('enabledPlugins', {})
    if not isinstance(plugins, dict):
      findings.append(
        f'Invalid enabledPlugins setting in Claude settings '
        f'{settings_path}'
      )
      continue
    for name, enabled in plugins.items():
      if enabled is not False:
        findings.append(
          f'Claude plugin {name!r} is not disabled in {settings_path}; '
          f'run /plugin and disable {name}'
        )
  return findings


def _claude_memory_findings(
  settings: Sequence[tuple[Path, JsonObject]],
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
    target = enabled_path or (Path.home() / '.claude' / 'settings.json')
    findings.append(
      'Claude auto-memory is not persistently disabled; '
      f'run /memory and disable auto-memory in {target}'
    )

  for memory_file in _claude_memory_files():
    findings.append(
      f'Claude memory file {memory_file} is present; remove or rename it '
      'because Claude has no persistent setting to disable '
      'CLAUDE.md/rules '
      'memory files'
    )
  return findings


def _claude_mcp_disabled_names(
  config: JsonObject,
  key: str,
  label: str | Path,
  findings: list[str],
) -> set[str]:
  names = _string_list(config.get(key, []))
  if names is None:
    findings.append(f'Invalid {key} setting in {label}')
    return set()
  return set(names)


def _claude_mcp_findings(
  project_root: Path, known_servers: Sequence[str]
) -> list[str]:
  findings: list[str] = []
  known_server_names = set(known_servers)
  project_disabled: set[str] = set()
  project_disabled_json: set[str] = set()
  project_enabled_json: set[str] = set()
  claude_json_path = Path.home() / '.claude.json'
  claude_json = _read_json_file(
    claude_json_path, 'Claude MCP configuration', findings
  )
  if claude_json is not None:
    disabled = _claude_mcp_disabled_names(
      claude_json,
      'disabledMcpServers',
      claude_json_path,
      findings,
    )
    enabled = _claude_mcp_disabled_names(
      claude_json,
      'enabledMcpServers',
      claude_json_path,
      findings,
    )
    servers = _json_object(claude_json.get('mcpServers', {}))
    if servers is None:
      findings.append(f'Invalid mcpServers setting in {claude_json_path}')
    else:
      for name in enabled:
        findings.append(
          f'Claude MCP server {name!r} is explicitly enabled in '
          f'{claude_json_path}; run /mcp and disable {name}'
        )
      for name in servers:
        if name not in disabled:
          findings.append(
            f'Claude MCP server {name!r} is not disabled in '
            f'{claude_json_path}; run /mcp and disable {name}'
          )

    projects = _json_object(claude_json.get('projects', {}))
    if projects is None:
      findings.append(f'Invalid projects setting in {claude_json_path}')
    else:
      project_config = projects.get(str(project_root.resolve()), {})
      project_config = _json_object(project_config)
      if project_config is None:
        findings.append(
          f'Invalid Claude project configuration in {claude_json_path}'
        )
      else:
        project_disabled = _claude_mcp_disabled_names(
          project_config,
          'disabledMcpServers',
          claude_json_path,
          findings,
        )
        project_enabled = _claude_mcp_disabled_names(
          project_config,
          'enabledMcpServers',
          claude_json_path,
          findings,
        )
        project_servers = _json_object(
          project_config.get('mcpServers', {})
        )
        if project_servers is None:
          findings.append(
            f'Invalid project mcpServers setting in {claude_json_path}'
          )
        else:
          for name in project_enabled:
            findings.append(
              f'Claude MCP server {name!r} is explicitly enabled in '
              f'{claude_json_path}; run /mcp and disable {name}'
            )
          for name in project_servers:
            if name not in project_disabled:
              findings.append(
                f'Claude MCP server {name!r} is not disabled in '
                f'{claude_json_path}; run /mcp and disable {name}'
              )

        project_disabled_json = _claude_mcp_disabled_names(
          project_config,
          'disabledMcpjsonServers',
          claude_json_path,
          findings,
        )
        project_enabled_json = _claude_mcp_disabled_names(
          project_config,
          'enabledMcpjsonServers',
          claude_json_path,
          findings,
        )

  mcp_json_path = project_root / '.mcp.json'
  mcp_json = _read_json_file(
    mcp_json_path, 'Claude project MCP configuration', findings
  )
  if mcp_json is not None:
    servers = _json_object(mcp_json.get('mcpServers', {}))
    if servers is None:
      findings.append(f'Invalid mcpServers setting in {mcp_json_path}')
    else:
      for name in project_enabled_json:
        if name in servers:
          findings.append(
            f'Claude MCP server {name!r} is explicitly enabled in '
            f'{claude_json_path}; run /mcp and disable {name}'
          )
      for name in servers:
        if name not in project_disabled_json:
          findings.append(
            f'Claude MCP server {name!r} is not disabled in '
            f'{mcp_json_path}; run /mcp and disable {name}'
          )
  for name in sorted(known_server_names):
    if name not in project_disabled:
      findings.append(
        f'Claude MCP server {name!r} is not disabled in '
        f'{claude_json_path}; run /mcp and disable {name}'
      )
  return findings


def _claude_mcp_set_preflight_enabled() -> bool:
  return CLAUDE_MCP_SET_ENV in os.environ


def _probe_claude_mcp_servers(project_root: Path) -> tuple[str, ...]:
  result = subprocess.run(
    ['claude', 'mcp', 'list'],
    cwd=project_root,
    env=os.environ,
    capture_output=True,
    text=True,
  )
  if result.returncode != 0:
    detail = result.stderr.strip() or 'no diagnostic output'
    raise click.ClickException(
      f'Claude MCP inventory preflight failed: {detail}'
    )

  servers: set[str] = set()
  for line in result.stdout.splitlines():
    line = line.strip()
    if ':' not in line or ' - ' not in line:
      continue
    name = line.split(':', 1)[0].strip()
    if name:
      servers.add(name)
  return tuple(sorted(servers))


def _check_claude_mcp_set(project_root: Path) -> tuple[str, ...]:
  expected: set[str] = set(CLAUDE_MCP_SERVERS)
  if not _claude_mcp_set_preflight_enabled():
    return tuple(sorted(expected))

  actual: set[str] = set(_probe_claude_mcp_servers(project_root))
  missing = ', '.join(sorted(expected - actual)) or 'none'
  extra = ', '.join(sorted(actual - expected)) or 'none'
  if actual != expected:
    raise click.ClickException(
      f'Claude MCP inventory mismatch for {CLAUDE_MCP_SET_ENV}; '
      f'missing from claude mcp list: {missing}; '
      f'not in the hardcoded set: {extra}'
    )
  return tuple(sorted(expected))


def _check_claude_ambient_state(project_root: Path) -> None:
  settings, findings = _read_claude_settings(project_root)
  findings.extend(_claude_memory_findings(settings))
  findings.extend(_claude_plugin_findings(settings))
  known_servers = _check_claude_mcp_set(project_root)
  findings.extend(_claude_mcp_findings(project_root, known_servers))

  for skill_file in _claude_skill_files():
    findings.append(
      f'Claude skill {skill_file} is present; remove or rename it because '
      'Claude has no persistent setting to disable standalone skills'
    )

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
  _check_claude_ambient_state(project_root)
  command = [
    'claude',
    '--model',
    model,
    '--system-prompt-file',
    str(system_file),
    '--dangerously-skip-permissions',
  ]
  _exec_agent(project_root, command, arguments)
