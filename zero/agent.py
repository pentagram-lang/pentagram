import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import click
import tomllib

AGENT_CONFIGURATIONS = {
  'codex-luna-yolo': ('codex', 'gpt-5.6-luna'),
  'codex-sol-yolo': ('codex', 'gpt-5.6-sol'),
  'claude-sonnet-yolo': ('claude', 'sonnet'),
  'claude-fable-yolo': ('claude', 'fable'),
  'agy-flash-yolo': ('agy', None),
}

AGY_TOOLSET_ENV = 'PENTAGRAM_AGY_TOOLSET'
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

AGY_AGENT_TOOLS = (
  'ask_question',
  'define_subagent',
  'find_by_name',
  'generate_image',
  'grep_search',
  'invoke_subagent',
  'list_dir',
  'manage_subagents',
  'manage_task',
  'read_url_content',
  'replace_file_content',
  'run_command',
  'schedule',
  'search_web',
  'send_message',
  'view_file',
  'write_to_file',
)


def _codex_home():
  return Path.home() / '.codex'


def _codex_config_paths(project_root):
  paths = [_codex_home() / 'config.toml']
  project_config = project_root / '.codex' / 'config.toml'
  paths.append(project_config)

  user_config = paths[0]
  if user_config.is_file():
    try:
      config = tomllib.loads(user_config.read_text())
    except (OSError, tomllib.TOMLDecodeError):
      config = {}
    profile = config.get('profile')
    if profile:
      paths.append(_codex_home() / f'{profile}.config.toml')

  unique_paths = []
  seen = set()
  for path in paths:
    resolved = path.expanduser().resolve()
    if resolved not in seen:
      seen.add(resolved)
      unique_paths.append(resolved)
  return unique_paths


def _read_codex_configs(project_root):
  configs = []
  findings = []
  for path in _codex_config_paths(project_root):
    if not path.exists():
      continue
    if not path.is_file():
      findings.append(f'Codex config path is not a file: {path}')
      continue
    try:
      configs.append((path, tomllib.loads(path.read_text())))
    except (OSError, tomllib.TOMLDecodeError) as error:
      findings.append(f'Cannot read Codex config {path}: {error}')
  return configs, findings


def _codex_plugin_roots():
  codex_home = _codex_home()
  return (
    (codex_home / 'plugins').expanduser().resolve(),
    (codex_home / '.tmp' / 'plugins').expanduser().resolve(),
  )


def _is_under(path, root):
  return path == root or root in path.parents


def _codex_skill_files():
  roots = [_codex_home() / 'skills']
  plugin_roots = _codex_plugin_roots()
  skill_files = []
  seen_roots = set()
  seen_files = set()
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


def _codex_memory_files():
  files = []
  for root in (_codex_home() / 'memories',):
    root = root.expanduser().resolve()
    if not root.is_dir():
      continue
    try:
      candidates = root.rglob('*')
    except OSError:
      candidates = ()
    for candidate in candidates:
      try:
        resolved = candidate.resolve()
      except OSError:
        continue
      if resolved.is_file():
        files.append(resolved)
  return sorted(set(files))


def _skill_config_path(raw_path, config_path):
  path = Path(os.path.expandvars(raw_path)).expanduser()
  if not path.is_absolute():
    path = config_path.parent / path
  if path.name != 'SKILL.md':
    path /= 'SKILL.md'
  return path.resolve()


def _codex_skill_overrides(configs, findings):
  overrides = []
  for config_path, config in configs:
    skills = config.get('skills', {})
    if not isinstance(skills, dict):
      findings.append(
        f'Invalid skills table in Codex config {config_path}'
      )
      continue
    entries = skills.get('config', [])
    if not isinstance(entries, list):
      findings.append(
        f'Invalid skills.config value in Codex config {config_path}'
      )
      continue
    for index, entry in enumerate(entries):
      if not isinstance(entry, dict) or not isinstance(
        entry.get('path'), str
      ):
        findings.append(
          f'Invalid skills.config entry {index} in Codex config '
          f'{config_path}'
        )
        continue
      overrides.append(
        (
          _skill_config_path(entry['path'], config_path),
          entry.get('enabled') is False,
          config_path,
        )
      )
  return overrides


def _codex_feature_remediation(setting, config_path=None):
  _, name = setting.split('.', 1)
  config_path = config_path or (_codex_home() / 'config.toml')
  return (
    f'run codex features disable {name}; this persists the disabled '
    f'state in {config_path}'
  )


def _codex_mcp_remediation(name, config_path):
  return (
    f'set [mcp_servers.{json.dumps(name)}] enabled = false '
    f'in {config_path}'
  )


def _codex_skill_remediation(skill_file):
  return f'run /skills and disable {skill_file}'


def _codex_mcp_findings(configs):
  findings = []
  for config_path, config in configs:
    servers = config.get('mcp_servers', {})
    if not isinstance(servers, dict):
      findings.append(
        f'Invalid mcp_servers table in Codex config {config_path}'
      )
    else:
      for name, server in servers.items():
        if (
          not isinstance(server, dict)
          or server.get('enabled') is not False
        ):
          findings.append(
            f'Codex MCP server {name!r} is not disabled in {config_path}; '
            f'{_codex_mcp_remediation(name, config_path)}'
          )
  return findings


def _codex_feature_findings(configs):
  findings = []
  settings = {
    'features.memories': [],
    'features.plugins': [],
  }
  for config_path, config in configs:
    features = config.get('features', {})
    if not isinstance(features, dict):
      findings.append(
        f'Invalid features table in Codex config {config_path}'
      )
    else:
      for key in ('memories', 'plugins'):
        if key in features:
          settings[f'features.{key}'].append((features[key], config_path))

    profile = config.get('profile')
    if profile:
      findings.append(
        f'Codex profile selection is not allowed in {config_path}: '
        f'{profile}'
      )

  for key, values in settings.items():
    enabled_path = next(
      (path for value, path in values if value is not False),
      None,
    )
    if enabled_path is not None:
      findings.append(
        f'Codex setting {key} is not disabled; '
        f'{_codex_feature_remediation(key, enabled_path)}'
      )
  return findings


def _check_codex_ambient_state(project_root):
  configs, findings = _read_codex_configs(project_root)
  findings.extend(_codex_feature_findings(configs))
  findings.extend(_codex_mcp_findings(configs))

  for memory_file in _codex_memory_files():
    findings.append(
      f'Codex memory file {memory_file} is present; remove or rename it '
      'because Codex has no persistent setting to disable memory files'
    )

  overrides = _codex_skill_overrides(configs, findings)
  disabled_paths = {path for path, disabled, _ in overrides if disabled}
  undisabled_skills = []
  for skill_file in _codex_skill_files():
    if skill_file not in disabled_paths:
      undisabled_skills.append(skill_file)

  for skill_file in undisabled_skills:
    findings.append(
      f'Codex skill {skill_file} is not disabled; '
      f'{_codex_skill_remediation(skill_file)}'
    )

  if findings:
    detail = '\n'.join(f'  - {finding}' for finding in findings)
    raise click.ClickException(
      f'Codex filesystem preflight failed:\n{detail}'
    )


def _claude_settings_paths(project_root):
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


def _read_json_file(path, label, findings):
  if not path.exists():
    return None
  if not path.is_file():
    findings.append(f'{label} path is not a file: {path}')
    return None
  try:
    value = json.loads(path.read_text())
  except (OSError, json.JSONDecodeError) as error:
    findings.append(f'Cannot read {label} {path}: {error}')
    return None
  if not isinstance(value, dict):
    findings.append(f'{label} must contain a JSON object: {path}')
    return None
  return value


def _read_claude_settings(project_root):
  settings = []
  findings = []
  for path in _claude_settings_paths(project_root):
    config = _read_json_file(path, 'Claude settings', findings)
    if config is not None:
      settings.append((path, config))
  return settings, findings


def _claude_memory_files():
  files = []
  seen = set()
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


def _claude_plugin_roots():
  return ((Path.home() / '.claude' / 'plugins').expanduser().resolve(),)


def _claude_skill_files():
  roots = [Path.home() / '.claude' / 'skills']
  plugin_roots = _claude_plugin_roots()
  skill_files = []
  seen_roots = set()
  seen_files = set()
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


def _claude_plugin_findings(settings):
  findings = []
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


def _claude_memory_findings(settings):
  findings = []
  values = []
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


def _claude_mcp_disabled_names(config, key, label, findings):
  names = config.get(key, [])
  if not isinstance(names, list) or not all(
    isinstance(name, str) for name in names
  ):
    findings.append(f'Invalid {key} setting in {label}')
    return set()
  return set(names)


def _claude_mcp_findings(project_root, known_servers):
  findings = []
  known_servers = set(known_servers)
  project_disabled = set()
  project_disabled_json = set()
  project_enabled_json = set()
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
    servers = claude_json.get('mcpServers', {})
    if not isinstance(servers, dict):
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

    projects = claude_json.get('projects', {})
    if not isinstance(projects, dict):
      findings.append(f'Invalid projects setting in {claude_json_path}')
    else:
      project_config = projects.get(str(project_root.resolve()), {})
      if not isinstance(project_config, dict):
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
        project_servers = project_config.get('mcpServers', {})
        if not isinstance(project_servers, dict):
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
    servers = mcp_json.get('mcpServers', {})
    if not isinstance(servers, dict):
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
  for name in sorted(known_servers):
    if name not in project_disabled:
      findings.append(
        f'Claude MCP server {name!r} is not disabled in '
        f'{claude_json_path}; run /mcp and disable {name}'
      )
  return findings


def _claude_mcp_set_preflight_enabled():
  return CLAUDE_MCP_SET_ENV in os.environ


def _probe_claude_mcp_servers(project_root):
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

  servers = set()
  for line in result.stdout.splitlines():
    line = line.strip()
    if ':' not in line or ' - ' not in line:
      continue
    name = line.split(':', 1)[0].strip()
    if name:
      servers.add(name)
  return tuple(sorted(servers))


def _check_claude_mcp_set(project_root):
  expected = set(CLAUDE_MCP_SERVERS)
  if not _claude_mcp_set_preflight_enabled():
    return tuple(sorted(expected))

  actual = set(_probe_claude_mcp_servers(project_root))
  missing = ', '.join(sorted(expected - actual)) or 'none'
  extra = ', '.join(sorted(actual - expected)) or 'none'
  if actual != expected:
    raise click.ClickException(
      f'Claude MCP inventory mismatch for {CLAUDE_MCP_SET_ENV}; '
      f'missing from claude mcp list: {missing}; '
      f'not in the hardcoded set: {extra}'
    )
  return tuple(sorted(expected))


def _check_claude_ambient_state(project_root):
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


def _agy_config_root():
  return (Path.home() / '.gemini' / 'config').resolve()


def _agy_resolve_path(raw_path, config_path, project_root):
  path = Path(os.path.expandvars(raw_path)).expanduser()
  if path.is_absolute():
    return path.resolve()
  candidates = (
    project_root / path,
    config_path.parent / path,
  )
  for candidate in candidates:
    if candidate.exists():
      return candidate.resolve()
  return candidates[0].resolve()


def _agy_filter_spec(
  entry,
  inherited_include_groups,
  inherited_excludes,
  config_path,
  kind,
  index,
  findings,
):
  include_groups = list(inherited_include_groups)
  excludes = list(inherited_excludes)
  for field, target in (
    ('include_only', include_groups),
    ('exclude', excludes),
  ):
    value = entry.get(field)
    if value is None:
      continue
    if not isinstance(value, list) or not all(
      isinstance(pattern, str) for pattern in value
    ):
      findings.append(
        f'Invalid {field} in AGY {kind} config entry {index} in '
        f'{config_path}'
      )
      continue
    compiled = []
    for pattern in value:
      try:
        compiled.append(re.compile(pattern))
      except re.error as error:
        findings.append(
          f'Invalid {field} pattern {pattern!r} in AGY {kind} config '
          f'entry {index} in {config_path}: {error}'
        )
    if field == 'include_only':
      target.append(tuple(compiled))
    elif field == 'exclude':
      target.extend(compiled)
  return tuple(include_groups), tuple(excludes)


def _agy_registered_roots(kind, project_root, findings):
  config_path = _agy_config_root() / f'{kind}.json'
  if not config_path.exists():
    return []

  roots = []

  def visit(path, include_groups, excludes, chain):
    path = path.resolve()
    if path in chain:
      findings.append(f'Cyclic AGY {kind} config inheritance at {path}')
      return
    if not path.exists():
      findings.append(f'AGY {kind} config path does not exist: {path}')
      return
    config = _read_json_file(path, f'AGY {kind} configuration', findings)
    if config is None:
      return
    next_chain = chain | {path}

    entries = config.get('entries', [])
    if not isinstance(entries, list):
      findings.append(f'Invalid entries in AGY {kind} config {path}')
    else:
      for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(
          entry.get('path'), str
        ):
          findings.append(
            f'Invalid AGY {kind} config entry {index} in {path}'
          )
          continue
        entry_include_groups, entry_excludes = _agy_filter_spec(
          entry,
          include_groups,
          excludes,
          path,
          kind,
          index,
          findings,
        )
        roots.append(
          (
            _agy_resolve_path(entry['path'], path, project_root),
            entry_include_groups,
            entry_excludes,
          )
        )

    inherits = config.get('inherits', [])
    if not isinstance(inherits, list):
      findings.append(f'Invalid inherits in AGY {kind} config {path}')
    else:
      for index, entry in enumerate(inherits):
        if not isinstance(entry, dict) or not isinstance(
          entry.get('path'), str
        ):
          findings.append(
            f'Invalid AGY {kind} inheritance entry {index} in {path}'
          )
          continue
        inherit_include_groups, inherit_excludes = _agy_filter_spec(
          entry,
          include_groups,
          excludes,
          path,
          kind,
          index,
          findings,
        )
        visit(
          _agy_resolve_path(entry['path'], path, project_root),
          inherit_include_groups,
          inherit_excludes,
          next_chain,
        )

  visit(config_path, (), (), set())
  return roots


def _agy_path_matches(path, include_groups, excludes):
  name = path.name
  return all(
    any(pattern.search(name) for pattern in group)
    for group in include_groups
  ) and not any(pattern.search(name) for pattern in excludes)


def _agy_customization_files(
  root,
  filename,
  include_groups,
  excludes,
  label,
  findings,
):
  root = root.resolve()
  if not root.exists():
    findings.append(f'AGY {label} path does not exist: {root}')
    return []
  if root.is_file():
    candidates = [root] if root.name == filename else []
  elif root.is_dir():
    try:
      candidates = list(root.rglob(filename))
    except OSError as error:
      findings.append(f'Cannot scan AGY {label} path {root}: {error}')
      return []
  else:
    findings.append(f'AGY {label} path is not a file or directory: {root}')
    return []

  files = []
  for candidate in candidates:
    try:
      resolved = candidate.resolve()
    except OSError:
      continue
    if resolved.is_file() and _agy_path_matches(
      resolved.parent, include_groups, excludes
    ):
      files.append(resolved)
  return files


def _agy_skill_files(project_root, findings):
  roots = []
  standard_root = _agy_config_root() / 'skills'
  if standard_root.exists():
    roots.append((standard_root, (), ()))
  roots.extend(_agy_registered_roots('skills', project_root, findings))
  files = []
  seen = set()
  for root, include_groups, excludes in roots:
    for skill_file in _agy_customization_files(
      root,
      'SKILL.md',
      include_groups,
      excludes,
      'skills',
      findings,
    ):
      if skill_file not in seen:
        seen.add(skill_file)
        files.append(skill_file)
  return sorted(files)


def _agy_plugin_manifests(project_root, findings):
  roots = []
  standard_root = _agy_config_root() / 'plugins'
  if standard_root.exists():
    roots.append((standard_root, (), ()))
  roots.extend(_agy_registered_roots('plugins', project_root, findings))
  manifests = []
  seen = set()
  for root, include_groups, excludes in roots:
    for manifest in _agy_customization_files(
      root,
      'plugin.json',
      include_groups,
      excludes,
      'plugins',
      findings,
    ):
      if manifest not in seen:
        seen.add(manifest)
        manifests.append(manifest)
  return sorted(manifests)


def _agy_plugin_findings(project_root, findings):
  manifests = _agy_plugin_manifests(project_root, findings)
  state_path = _agy_config_root() / 'config.json'
  state = _read_json_file(state_path, 'AGY plugin state', findings)
  overrides = {}
  if state is not None:
    plugins = state.get('plugins', {})
    if not isinstance(plugins, dict):
      findings.append(f'Invalid plugins setting in {state_path}')
    else:
      overrides = plugins

  for manifest_path in manifests:
    manifest = _read_json_file(
      manifest_path,
      'AGY plugin manifest',
      findings,
    )
    if manifest is None:
      continue
    plugin_name = manifest_path.parent.name
    manifest_disabled = manifest.get('disabled', False)
    if not isinstance(manifest_disabled, bool):
      findings.append(
        f'Invalid disabled setting in AGY plugin manifest {manifest_path}'
      )
      continue

    override = overrides.get(plugin_name)
    if override is not None:
      if not isinstance(override, dict) or not isinstance(
        override.get('enabled'), bool
      ):
        findings.append(
          f'Invalid AGY plugin override for {plugin_name!r} in '
          f'{state_path}'
        )
        continue
      disabled = override['enabled'] is False
    else:
      disabled = manifest_disabled

    if not disabled:
      findings.append(
        f'AGY plugin {plugin_name!r} is enabled; set '
        f'plugins[{plugin_name!r}].enabled = false in {state_path}'
      )


def _agy_mcp_findings(findings):
  config_path = _agy_config_root() / 'mcp_config.json'
  if not config_path.exists():
    return
  if not config_path.is_file():
    findings.append(
      f'AGY MCP configuration path is not a file: {config_path}'
    )
    return
  try:
    if not config_path.read_text().strip():
      return
  except OSError as error:
    findings.append(
      f'Cannot read AGY MCP configuration {config_path}: {error}'
    )
    return
  config = _read_json_file(
    config_path,
    'AGY MCP configuration',
    findings,
  )
  if config is None:
    return
  servers = config.get('mcpServers', {})
  if not isinstance(servers, dict):
    findings.append(f'Invalid mcpServers setting in {config_path}')
    return
  for name in sorted(servers):
    findings.append(
      f'AGY MCP server {name!r} is configured in {config_path}; '
      'remove it because AGY has no persistent all-MCP disable setting'
    )


def _check_agy_ambient_state(project_root):
  findings = []
  for skill_file in _agy_skill_files(project_root, findings):
    findings.append(
      f'AGY skill {skill_file} is present; remove it or deregister its '
      'path because AGY has no persistent all-skills disable setting'
    )
  _agy_plugin_findings(project_root, findings)
  _agy_mcp_findings(findings)
  if findings:
    detail = '\n'.join(f'  - {finding}' for finding in findings)
    raise click.ClickException(
      f'AGY filesystem preflight failed:\n{detail}'
    )


def _agy_toolset_preflight_enabled():
  return AGY_TOOLSET_ENV in os.environ


def _probe_agy_tools(project_root):
  probe_command = [
    'agy',
    '--new-project',
    '--output-format',
    'stream-json',
    '--print',
    'Report the initialized tool surface and do not call any tools.',
  ]
  result = subprocess.run(
    probe_command,
    cwd=project_root,
    env=os.environ,
    capture_output=True,
    text=True,
  )
  if result.returncode != 0:
    detail = result.stderr.strip() or 'no diagnostic output'
    raise click.ClickException(f'AGY tool preflight failed: {detail}')

  for line in result.stdout.splitlines():
    try:
      event = json.loads(line)
    except json.JSONDecodeError:
      continue
    if event.get('event') == 'init':
      tools = event.get('init', {}).get('tools')
      if isinstance(tools, list) and all(
        isinstance(tool, str) for tool in tools
      ):
        return tuple(sorted(set(tools)))

  raise click.ClickException(
    'AGY tool preflight returned no stream-json init tool inventory'
  )


def _check_agy_tools(project_root):
  if not _agy_toolset_preflight_enabled():
    return AGY_AGENT_TOOLS

  actual = _probe_agy_tools(project_root)
  missing = ', '.join(sorted(set(AGY_AGENT_TOOLS) - set(actual)))
  if missing:
    raise click.ClickException(
      f'AGY tool surface mismatch for {AGY_TOOLSET_ENV}; '
      f'missing: {missing}'
    )
  return AGY_AGENT_TOOLS


def launch_agy(project_root, system_file, arguments):
  _check_agy_ambient_state(project_root)
  system_content = system_file.read_text()
  agent_tools = _check_agy_tools(project_root)
  agent_content = (
    '---\n'
    'name: pentagram\n'
    'description: Pentagram engineering agent governed by the '
    'repository-root '
    'system contract.\n'
    'tools:\n'
    + ''.join(f'  - {tool}\n' for tool in agent_tools)
    + 'commandExecutionPolicy: eager\n'
    '---\n\n'
    f'{system_content}'
  )

  with tempfile.TemporaryDirectory(prefix='pentagram-agy-') as runtime_dir:
    agent_file = (
      Path(runtime_dir) / '.agents' / 'agents' / 'pentagram' / 'agent.md'
    )
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text(agent_content)
    agy_command = [
      'agy',
      '--new-project',
      '--add-dir',
      runtime_dir,
      '--agent',
      'pentagram',
      '--dangerously-skip-permissions',
      *arguments,
    ]
    result = subprocess.run(agy_command, cwd=project_root, env=os.environ)

  raise click.exceptions.Exit(result.returncode)


def launch(agent_name, arguments):
  project_root = Path(__file__).resolve().parent.parent
  system_file = project_root / 'sys.md'

  if not system_file.is_file():
    raise click.ClickException(f'Missing system prompt: {system_file}')

  executable, model = AGENT_CONFIGURATIONS[agent_name]
  if shutil.which(executable) is None:
    raise click.ClickException(
      f'Agent executable not found on PATH: {executable}'
    )

  command = [executable]
  if executable == 'codex':
    _check_codex_ambient_state(project_root)
    config = f'model_instructions_file={json.dumps(str(system_file))}'
    command.extend(
      [
        '--model',
        model,
        '--config',
        config,
        '--dangerously-bypass-approvals-and-sandbox',
        '--cd',
        str(project_root),
      ]
    )
  elif executable == 'claude':
    _check_claude_ambient_state(project_root)
    command.extend(
      [
        '--model',
        model,
        '--system-prompt-file',
        str(system_file),
        '--dangerously-skip-permissions',
      ]
    )
  else:
    launch_agy(project_root, system_file, arguments)

  os.chdir(project_root)
  os.execvpe(command[0], command + list(arguments), os.environ)
