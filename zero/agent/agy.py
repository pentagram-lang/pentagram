import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click

from zero.lib import json_object, string_list

from .common import (
  JsonObject,
  check_ambient_file,
  parse_json_object,
  read_json_file,
  read_regular_text,
  scan_ambient_files,
)

AGY_TOOLSET_ENV = 'PENTAGRAM_AGY_TOOLSET'

AGY_AGENT_TOOLS = (
  'ask_question',
  'define_subagent',
  'edit_file',
  'generate_image',
  'invoke_subagent',
  'manage_subagents',
  'manage_task',
  'read_file',
  'run_command',
  'run_workflow',
  'schedule',
  'search_web',
  'send_message',
  'swarm_manage',
  'swarm_post_message',
  'swarm_read_board',
  'swarm_wait',
  'write_file',
)

type IncludeGroup = tuple[re.Pattern[str], ...]
type IncludeGroups = tuple[IncludeGroup, ...]
type ExcludePatterns = tuple[re.Pattern[str], ...]
type RegisteredRoot = tuple[Path, IncludeGroups, ExcludePatterns]

_ENV_VAR_PATTERN = re.compile(r'\$(?:(\w+)|\{([^}]+)\})')
_TOOLSET_PROBE_PROMPT = 'Reply OK and do not call any tools.'


@dataclass(frozen=True, slots=True)
class AgyPluginManifest:
  path: Path
  config: JsonObject | None


@dataclass(frozen=True, slots=True)
class AgyFilterEntry:
  raw_path: str
  include_groups: IncludeGroups
  excludes: ExcludePatterns


@dataclass(frozen=True, slots=True)
class ParsedRegistrationConfig:
  entries: tuple[AgyFilterEntry, ...]
  inherits: tuple[AgyFilterEntry, ...]
  findings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgyState:
  config_root: Path
  rule_files: tuple[Path, ...]
  skill_files: tuple[Path, ...]
  plugin_state: JsonObject | None
  plugin_manifests: tuple[AgyPluginManifest, ...]
  mcp_config: JsonObject | None
  read_findings: tuple[str, ...] = ()


def render_agent_adapter(
  system_content: str, tools: Sequence[str] = AGY_AGENT_TOOLS
) -> str:
  """Render the pentagram custom-agent markdown adapter for AGY."""
  return (
    '---\n'
    'name: pentagram\n'
    'description: Pentagram engineering agent governed by the '
    'repository-root system contract.\n'
    'tools:\n'
    + ''.join(f'  - {tool}\n' for tool in tools)
    + 'commandExecutionPolicy: eager\n'
    '---\n\n'
    f'{system_content}'
  )


def build_toolset_probe_command(
  runtime_dir: Path, model: str
) -> list[str]:
  """Build the AGY non-interactive stream-json toolset probe command."""
  return [
    'agy',
    '--new-project',
    '--add-dir',
    str(runtime_dir),
    '--agent',
    'pentagram',
    '--model',
    model,
    '--output-format',
    'stream-json',
    '--print',
    _TOOLSET_PROBE_PROMPT,
  ]


def build_launch_command(
  runtime_dir: Path, model: str, arguments: Sequence[str]
) -> list[str]:
  """Build the AGY interactive launch command."""
  return [
    'agy',
    '--new-project',
    '--add-dir',
    str(runtime_dir),
    '--agent',
    'pentagram',
    '--model',
    model,
    '--dangerously-skip-permissions',
    *arguments,
  ]


def expand_agy_path(
  raw_path: str, home: Path, environ: Mapping[str, str]
) -> Path:
  """Expand $VAR / ${VAR} environment variables and ~ against home."""

  def replace_var(match: re.Match[str]) -> str:
    name = match.group(1) or match.group(2)
    if name is None or name not in environ:
      return match.group(0)
    return environ[name]

  expanded = _ENV_VAR_PATTERN.sub(replace_var, raw_path)
  if expanded == '~':
    return home
  if expanded.startswith('~/'):
    return home / expanded[2:]
  return Path(expanded)


def _agy_filter_spec(
  entry: JsonObject,
  inherited_include_groups: IncludeGroups,
  inherited_excludes: ExcludePatterns,
  config_path: Path,
  kind: str,
  entry_label: str,
  index: int,
  findings: list[str],
) -> tuple[IncludeGroups, ExcludePatterns]:
  include_groups = list(inherited_include_groups)
  excludes = list(inherited_excludes)
  for field in ('include_only', 'exclude'):
    value = entry.get(field)
    if value is None:
      continue
    patterns = string_list(value)
    if patterns is None:
      findings.append(
        f'Invalid {field} in AGY {kind} {entry_label} {index} in '
        f'{config_path}'
      )
      continue
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
      try:
        compiled.append(re.compile(pattern))
      except re.error as error:
        findings.append(
          f'Invalid {field} pattern {pattern!r} in AGY {kind} '
          f'{entry_label} {index} in {config_path}: {error}'
        )
    if field == 'include_only':
      include_groups.append(tuple(compiled))
    else:
      excludes.extend(compiled)
  return tuple(include_groups), tuple(excludes)


def _parse_filter_entries(
  config: JsonObject,
  *,
  field: str,
  entry_label: str,
  config_path: Path,
  kind: str,
  inherited_include_groups: IncludeGroups,
  inherited_excludes: ExcludePatterns,
  findings: list[str],
) -> tuple[AgyFilterEntry, ...]:
  raw_items = config.get(field, [])
  if not isinstance(raw_items, list):
    findings.append(f'Invalid {field} in AGY {kind} config {config_path}')
    return ()

  parsed: list[AgyFilterEntry] = []
  for index, raw_entry in enumerate(raw_items):
    entry = json_object(raw_entry)
    if entry is None:
      findings.append(
        f'Invalid AGY {kind} {entry_label} {index} in {config_path}'
      )
      continue
    entry_path = entry.get('path')
    if not isinstance(entry_path, str):
      findings.append(
        f'Invalid AGY {kind} {entry_label} {index} in {config_path}'
      )
      continue
    include_groups, excludes = _agy_filter_spec(
      entry,
      inherited_include_groups,
      inherited_excludes,
      config_path,
      kind,
      entry_label,
      index,
      findings,
    )
    parsed.append(AgyFilterEntry(entry_path, include_groups, excludes))
  return tuple(parsed)


def parse_registration_config(
  config: JsonObject,
  *,
  config_path: Path,
  kind: str,
  inherited_include_groups: IncludeGroups = (),
  inherited_excludes: ExcludePatterns = (),
) -> ParsedRegistrationConfig:
  """Parse an AGY rules/skills/plugins registration JSON object."""
  findings: list[str] = []
  entries = _parse_filter_entries(
    config,
    field='entries',
    entry_label='config entry',
    config_path=config_path,
    kind=kind,
    inherited_include_groups=inherited_include_groups,
    inherited_excludes=inherited_excludes,
    findings=findings,
  )
  inherits = _parse_filter_entries(
    config,
    field='inherits',
    entry_label='inheritance entry',
    config_path=config_path,
    kind=kind,
    inherited_include_groups=inherited_include_groups,
    inherited_excludes=inherited_excludes,
    findings=findings,
  )
  return ParsedRegistrationConfig(entries, inherits, tuple(findings))


def agy_path_matches(
  path: Path,
  include_groups: IncludeGroups,
  excludes: ExcludePatterns,
) -> bool:
  """Return whether path passes include_only and exclude filters."""
  names = (path.name, path.stem)
  return all(
    any(any(pattern.search(name) for name in names) for pattern in group)
    for group in include_groups
  ) and not any(
    any(pattern.search(name) for name in names) for pattern in excludes
  )


def _agy_resolve_path(
  raw_path: str,
  config_path: Path,
  project_root: Path,
  home: Path,
  environ: Mapping[str, str],
  *,
  kind: str,
  findings: list[str],
) -> Path | None:
  path = expand_agy_path(raw_path, home, environ)
  if not path.is_absolute():
    candidates = (project_root / path, config_path.parent / path)
    chosen = candidates[0]
    for candidate in candidates:
      try:
        candidate.lstat()
      except (FileNotFoundError, NotADirectoryError):
        continue
      except OSError:
        chosen = candidate
        break
      chosen = candidate
      break
    path = chosen
  try:
    return path.resolve()
  except OSError as error:
    findings.append(f'Cannot scan AGY {kind} {path}: {error}')
    return None


def _agy_registered_roots(
  config_root: Path,
  kind: str,
  project_root: Path,
  home: Path,
  environ: Mapping[str, str],
  findings: list[str],
) -> list[RegisteredRoot]:
  root_config = config_root / f'{kind}.json'
  try:
    root_config.lstat()
  except (FileNotFoundError, NotADirectoryError):
    return []
  except OSError:
    pass

  roots: list[RegisteredRoot] = []

  def visit(
    path: Path,
    include_groups: IncludeGroups,
    excludes: ExcludePatterns,
    chain: set[Path],
    *,
    require_exists: bool,
  ) -> None:
    try:
      resolved = path.resolve()
    except OSError as error:
      findings.append(f'Cannot scan AGY {kind} {path}: {error}')
      return
    if resolved in chain:
      findings.append(
        f'Cyclic AGY {kind} config inheritance at {resolved}'
      )
      return
    if require_exists:
      try:
        resolved.lstat()
      except (FileNotFoundError, NotADirectoryError):
        findings.append(
          f'AGY {kind} config path does not exist: {resolved}'
        )
        return
      except OSError as error:
        findings.append(
          f'Cannot read AGY {kind} configuration {resolved}: {error}'
        )
        return

    config, read_error = read_json_file(
      resolved, f'AGY {kind} configuration'
    )
    if read_error is not None:
      findings.append(read_error)
      return
    if config is None:
      return

    parsed = parse_registration_config(
      config,
      config_path=resolved,
      kind=kind,
      inherited_include_groups=include_groups,
      inherited_excludes=excludes,
    )
    findings.extend(parsed.findings)
    next_chain = chain | {resolved}

    for entry in parsed.entries:
      target = _agy_resolve_path(
        entry.raw_path,
        resolved,
        project_root,
        home,
        environ,
        kind=kind,
        findings=findings,
      )
      if target is not None:
        roots.append((target, entry.include_groups, entry.excludes))

    for inherit in parsed.inherits:
      target = _agy_resolve_path(
        inherit.raw_path,
        resolved,
        project_root,
        home,
        environ,
        kind=kind,
        findings=findings,
      )
      if target is not None:
        visit(
          target,
          inherit.include_groups,
          inherit.excludes,
          next_chain,
          require_exists=True,
        )

  visit(root_config, (), (), set(), require_exists=False)
  return roots


def _agy_customization_files(
  root: Path,
  filename: str,
  include_groups: IncludeGroups,
  excludes: ExcludePatterns,
  label: str,
  findings: list[str],
) -> list[Path]:
  try:
    resolved_root = root.resolve()
  except OSError as error:
    findings.append(f'Cannot scan AGY {label} {root}: {error}')
    return []

  try:
    resolved_root.lstat()
    st = resolved_root.stat()
  except (FileNotFoundError, NotADirectoryError):
    findings.append(f'AGY {label} path does not exist: {resolved_root}')
    return []
  except OSError as error:
    findings.append(f'Cannot scan AGY {label} {resolved_root}: {error}')
    return []

  if stat.S_ISREG(st.st_mode):
    matches = resolved_root.name == filename or (
      filename == '*.md' and resolved_root.suffix == '.md'
    )
    candidates: tuple[Path, ...] = (resolved_root,) if matches else ()
  elif stat.S_ISDIR(st.st_mode):
    match_name = None if filename == '*.md' else filename
    suffix = '.md' if filename == '*.md' else None
    candidates, scan_findings = scan_ambient_files(
      resolved_root,
      label=f'AGY {label}',
      match_name=match_name,
      suffix=suffix,
    )
    findings.extend(scan_findings)
  else:
    findings.append(
      f'AGY {label} path is not a file or directory: {resolved_root}'
    )
    return []

  files: list[Path] = []
  for candidate in candidates:
    match_target = candidate if filename == '*.md' else candidate.parent
    if agy_path_matches(match_target, include_groups, excludes):
      files.append(candidate)
  return files


def _agy_skill_files(
  home: Path,
  config_root: Path,
  project_root: Path,
  environ: Mapping[str, str],
  findings: list[str],
) -> tuple[Path, ...]:
  files: set[Path] = set()
  standard_scanned, standard_findings = scan_ambient_files(
    config_root / 'skills', label='AGY skills', match_name='SKILL.md'
  )
  findings.extend(standard_findings)
  files.update(standard_scanned)

  for root, include_groups, excludes in _agy_registered_roots(
    config_root, 'skills', project_root, home, environ, findings
  ):
    files.update(
      _agy_customization_files(
        root,
        'SKILL.md',
        include_groups,
        excludes,
        'skills',
        findings,
      )
    )
  return tuple(sorted(files))


def _agy_rule_files(
  home: Path,
  config_root: Path,
  project_root: Path,
  environ: Mapping[str, str],
  findings: list[str],
) -> tuple[Path, ...]:
  files: set[Path] = set()
  for candidate in (
    home / 'AGENTS.md',
    home / 'GEMINI.md',
    home / '.gemini' / 'AGENTS.md',
    home / '.gemini' / 'GEMINI.md',
  ):
    resolved, error = check_ambient_file(candidate, label='AGY rules')
    if error is not None:
      findings.append(error)
    elif resolved is not None:
      files.add(resolved)

  for directory in (
    home / '.gemini' / 'rules',
    home / '.agents' / 'rules',
    config_root / 'rules',
  ):
    scanned, scan_findings = scan_ambient_files(
      directory, label='AGY rules', suffix='.md'
    )
    findings.extend(scan_findings)
    files.update(scanned)

  for root, include_groups, excludes in _agy_registered_roots(
    config_root, 'rules', project_root, home, environ, findings
  ):
    files.update(
      _agy_customization_files(
        root, '*.md', include_groups, excludes, 'rules', findings
      )
    )
  return tuple(sorted(files))


def _agy_plugin_manifest_paths(
  home: Path,
  config_root: Path,
  project_root: Path,
  environ: Mapping[str, str],
  findings: list[str],
) -> tuple[Path, ...]:
  manifests: set[Path] = set()
  standard_scanned, standard_findings = scan_ambient_files(
    config_root / 'plugins', label='AGY plugins', match_name='plugin.json'
  )
  findings.extend(standard_findings)
  manifests.update(standard_scanned)

  for root, include_groups, excludes in _agy_registered_roots(
    config_root, 'plugins', project_root, home, environ, findings
  ):
    manifests.update(
      _agy_customization_files(
        root,
        'plugin.json',
        include_groups,
        excludes,
        'plugins',
        findings,
      )
    )
  return tuple(sorted(manifests))


def _collect_agy_state(project_root: Path) -> AgyState:
  home = Path.home().resolve()
  config_root = (home / '.gemini' / 'config').resolve()
  resolved_root = project_root.resolve()
  environ = os.environ
  findings: list[str] = []

  skill_files = _agy_skill_files(
    home, config_root, resolved_root, environ, findings
  )
  rule_files = _agy_rule_files(
    home, config_root, resolved_root, environ, findings
  )
  manifest_paths = _agy_plugin_manifest_paths(
    home, config_root, resolved_root, environ, findings
  )

  plugin_state, state_error = read_json_file(
    config_root / 'config.json', 'AGY plugin state'
  )
  if state_error is not None:
    findings.append(state_error)

  plugin_manifests: list[AgyPluginManifest] = []
  for manifest_path in manifest_paths:
    manifest, manifest_error = read_json_file(
      manifest_path, 'AGY plugin manifest'
    )
    if manifest_error is not None:
      findings.append(manifest_error)
    plugin_manifests.append(AgyPluginManifest(manifest_path, manifest))

  mcp_path = config_root / 'mcp_config.json'
  mcp_raw, mcp_read_error = read_regular_text(
    mcp_path, 'AGY MCP configuration'
  )
  mcp_config: JsonObject | None = None
  if mcp_read_error is not None:
    findings.append(mcp_read_error)
  elif mcp_raw is not None and mcp_raw.strip():
    mcp_config, mcp_parse_error = parse_json_object(
      mcp_raw, mcp_path, 'AGY MCP configuration'
    )
    if mcp_parse_error is not None:
      findings.append(mcp_parse_error)

  return AgyState(
    config_root=config_root,
    rule_files=rule_files,
    skill_files=skill_files,
    plugin_state=plugin_state,
    plugin_manifests=tuple(plugin_manifests),
    mcp_config=mcp_config,
    read_findings=tuple(findings),
  )


def _agy_plugin_findings(state: AgyState) -> list[str]:
  findings: list[str] = []
  state_path = state.config_root / 'config.json'
  overrides: JsonObject = {}
  if state.plugin_state is not None:
    plugins = json_object(state.plugin_state.get('plugins', {}))
    if plugins is None:
      findings.append(f'Invalid plugins setting in {state_path}')
    else:
      overrides = plugins

  for entry in state.plugin_manifests:
    if entry.config is None:
      continue
    plugin_name = entry.path.parent.name
    manifest_disabled = entry.config.get('disabled', False)
    if not isinstance(manifest_disabled, bool):
      findings.append(
        f'Invalid disabled setting in AGY plugin manifest {entry.path}'
      )
      continue

    raw_override = overrides.get(plugin_name)
    if raw_override is not None:
      override = json_object(raw_override)
      if override is None or not isinstance(override.get('enabled'), bool):
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
  return findings


def _agy_mcp_findings(state: AgyState) -> list[str]:
  if state.mcp_config is None:
    return []
  config_path = state.config_root / 'mcp_config.json'
  servers = json_object(state.mcp_config.get('mcpServers', {}))
  if servers is None:
    return [f'Invalid mcpServers setting in {config_path}']
  return [
    f'AGY MCP server {name!r} is configured in {config_path}; '
    'remove it because AGY has no persistent all-MCP disable setting'
    for name in sorted(servers)
  ]


def agy_preflight_findings(state: AgyState) -> tuple[str, ...]:
  """Evaluate all pure AGY preflight invariants against AgyState."""
  findings = list(state.read_findings)
  for skill_file in state.skill_files:
    findings.append(
      f'AGY skill {skill_file} is present; remove it or deregister its '
      'path because AGY has no persistent all-skills disable setting'
    )
  for rule_file in state.rule_files:
    findings.append(
      f'AGY rule file {rule_file} is present; remove or rename it '
      'because AGY has no persistent setting to disable '
      'AGENTS.md/rules files'
    )
  findings.extend(_agy_plugin_findings(state))
  findings.extend(_agy_mcp_findings(state))
  return tuple(findings)


def toolset_probe_error(
  returncode: int, stdout: str, stderr: str
) -> str | None:
  """Validate AGY stream-json probe output and return an error message."""
  initialized_agent: str | None = None
  result_status: str | None = None
  result_error: str | None = None

  for line in stdout.splitlines():
    try:
      event = json.loads(line)
    except json.JSONDecodeError:
      continue
    if not isinstance(event, Mapping):
      continue
    kind = event.get('event')
    if kind == 'init':
      initialization = event.get('init')
      if isinstance(initialization, Mapping):
        agent = initialization.get('agent')
        if isinstance(agent, str):
          initialized_agent = agent
    elif kind == 'result':
      payload = event.get('result')
      if isinstance(payload, Mapping):
        status = payload.get('status')
        if isinstance(status, str):
          result_status = status
        error = payload.get('error')
        if isinstance(error, str) and error:
          result_error = error

  if returncode != 0:
    detail = result_error or stderr.strip() or 'no diagnostic output'
    return f'AGY tool preflight failed: {detail}'
  if initialized_agent != 'pentagram':
    return (
      'AGY tool preflight did not initialize the pentagram custom agent'
    )
  if result_status is None:
    return 'AGY tool preflight returned no stream-json result event'
  if result_status != 'SUCCESS':
    detail = result_error or f'unexpected result status {result_status!r}'
    return f'AGY tool preflight failed: {detail}'
  return None


@contextmanager
def _runtime_adapter(agent_content: str) -> Iterator[Path]:
  try:
    tmpdir = tempfile.TemporaryDirectory(prefix='pentagram-agy-')
  except OSError as error:
    raise click.ClickException(
      f'Failed to prepare AGY runtime adapter: {error}'
    ) from error
  try:
    runtime_dir = Path(tmpdir.name)
    agent_file = (
      runtime_dir / '.agents' / 'agents' / 'pentagram' / 'agent.md'
    )
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text(agent_content, encoding='utf-8')
  except OSError as error:
    tmpdir.cleanup()
    raise click.ClickException(
      f'Failed to prepare AGY runtime adapter: {error}'
    ) from error
  try:
    yield runtime_dir
  finally:
    tmpdir.cleanup()


def _check_agy_toolset(
  project_root: Path, runtime_dir: Path, model: str
) -> None:
  probe_command = build_toolset_probe_command(runtime_dir, model)
  try:
    result = subprocess.run(
      probe_command,
      cwd=project_root,
      env=os.environ,
      capture_output=True,
      text=True,
      encoding='utf-8',
      errors='replace',
    )
  except OSError as error:
    raise click.ClickException(
      f'AGY tool preflight failed: {error}'
    ) from error
  error = toolset_probe_error(
    result.returncode, result.stdout, result.stderr
  )
  if error is not None:
    raise click.ClickException(error)


def launch(
  project_root: Path,
  system_file: Path,
  arguments: Sequence[str],
  model: str,
) -> None:
  """Run AGY preflight checks, prepare runtime adapter, and invoke agy."""
  findings = agy_preflight_findings(_collect_agy_state(project_root))
  if findings:
    detail = '\n'.join(f'  - {finding}' for finding in findings)
    raise click.ClickException(
      f'AGY filesystem preflight failed:\n{detail}'
    )

  try:
    system_content = system_file.read_text(encoding='utf-8')
  except (OSError, UnicodeDecodeError) as error:
    raise click.ClickException(
      f'Cannot read system prompt {system_file}: {error}'
    ) from error

  agent_content = render_agent_adapter(system_content, AGY_AGENT_TOOLS)
  with _runtime_adapter(agent_content) as runtime_dir:
    if AGY_TOOLSET_ENV in os.environ:
      _check_agy_toolset(project_root, runtime_dir, model)
    command = build_launch_command(runtime_dir, model, arguments)
    try:
      result = subprocess.run(
        command,
        cwd=project_root,
        env=os.environ,
        capture_output=False,
      )
    except OSError as error:
      raise click.ClickException(
        f'Failed to launch agent agy: {error}'
      ) from error

  exit_code = (
    128 - result.returncode if result.returncode < 0 else result.returncode
  )
  raise click.exceptions.Exit(exit_code)
