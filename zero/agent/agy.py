import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import click

from .common import JsonObject, _string_list

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

type PathKind = Literal['missing', 'file', 'dir', 'other']
type IncludeGroup = tuple[re.Pattern[str], ...]
type IncludeGroups = tuple[IncludeGroup, ...]
type ExcludePatterns = tuple[re.Pattern[str], ...]
type RegisteredRoot = tuple[Path, IncludeGroups, ExcludePatterns]

_ENV_VAR_PATTERN = re.compile(r'\$(?:(\w+)|\{([^}]+)\})')
_TOOLSET_PROBE_PROMPT = 'Reply OK and do not call any tools.'


@dataclass(frozen=True)
class _Host:
  home: Path
  environ: Mapping[str, str]
  resolve: Callable[[Path], Path]
  path_kind: Callable[[Path], PathKind]
  read_text: Callable[[Path], str]
  rglob: Callable[[Path, str], tuple[Path, ...]]
  runtime_adapter: Callable[[str], AbstractContextManager[Path]]
  run_command: Callable[
    [Sequence[str], Path, Mapping[str, str], bool],
    subprocess.CompletedProcess[str],
  ]


def launch(
  project_root: Path,
  system_file: Path,
  arguments: Sequence[str],
  model: str,
) -> None:
  host = _os_host()
  _check_agy_ambient_state(host, project_root)
  system_content = host.read_text(system_file)
  agent_content = _render_agent_adapter(system_content, AGY_AGENT_TOOLS)

  with host.runtime_adapter(agent_content) as runtime_dir:
    if AGY_TOOLSET_ENV in host.environ:
      _check_agy_toolset(host, project_root, runtime_dir, model)
    command = _build_launch_command(runtime_dir, model, arguments)
    result = host.run_command(command, project_root, host.environ, False)

  raise click.exceptions.Exit(result.returncode)


def _render_agent_adapter(
  system_content: str, tools: Sequence[str]
) -> str:
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


def _build_toolset_probe_command(
  runtime_dir: Path, model: str
) -> list[str]:
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


def _build_launch_command(
  runtime_dir: Path, model: str, arguments: Sequence[str]
) -> list[str]:
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


def _agy_config_root(host: _Host) -> Path:
  return host.resolve(host.home / '.gemini' / 'config')


def _expand_agy_path(raw_path: str, host: _Host) -> Path:
  def replace_var(match: re.Match[str]) -> str:
    name = match.group(1) or match.group(2)
    if name is None or name not in host.environ:
      return match.group(0)
    return host.environ[name]

  expanded = _ENV_VAR_PATTERN.sub(replace_var, raw_path)
  if expanded == '~':
    return host.home
  if expanded.startswith('~/'):
    return host.home / expanded[2:]
  return Path(expanded)


def _agy_resolve_path(
  host: _Host, raw_path: str, config_path: Path, project_root: Path
) -> Path:
  path = _expand_agy_path(raw_path, host)
  if path.is_absolute():
    return host.resolve(path)
  candidates = (
    project_root / path,
    config_path.parent / path,
  )
  for candidate in candidates:
    if host.path_kind(candidate) != 'missing':
      return host.resolve(candidate)
  return host.resolve(candidates[0])


def _read_agy_json(
  host: _Host, path: Path, label: str, findings: list[str]
) -> JsonObject | None:
  kind = host.path_kind(path)
  if kind == 'missing':
    return None
  if kind != 'file':
    findings.append(f'{label} path is not a file: {path}')
    return None
  try:
    value = json.loads(host.read_text(path))
  except (OSError, json.JSONDecodeError) as error:
    findings.append(f'Cannot read {label} {path}: {error}')
    return None
  if not isinstance(value, dict):
    findings.append(f'{label} must contain a JSON object: {path}')
    return None
  return value


def _agy_filter_spec(
  entry: JsonObject,
  inherited_include_groups: IncludeGroups,
  inherited_excludes: ExcludePatterns,
  config_path: Path,
  kind: str,
  index: int,
  findings: list[str],
) -> tuple[IncludeGroups, ExcludePatterns]:
  include_groups = list(inherited_include_groups)
  excludes = list(inherited_excludes)
  for field in ('include_only', 'exclude'):
    value = entry.get(field)
    if value is None:
      continue
    patterns = _string_list(value)
    if patterns is None:
      findings.append(
        f'Invalid {field} in AGY {kind} config entry {index} in '
        f'{config_path}'
      )
      continue
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
      try:
        compiled.append(re.compile(pattern))
      except re.error as error:
        findings.append(
          f'Invalid {field} pattern {pattern!r} in AGY {kind} config '
          f'entry {index} in {config_path}: {error}'
        )
    if field == 'include_only':
      include_groups.append(tuple(compiled))
    else:
      excludes.extend(compiled)
  return tuple(include_groups), tuple(excludes)


def _agy_registered_roots(
  host: _Host, kind: str, project_root: Path, findings: list[str]
) -> list[RegisteredRoot]:
  config_path = _agy_config_root(host) / f'{kind}.json'
  if host.path_kind(config_path) == 'missing':
    return []

  roots: list[RegisteredRoot] = []

  def visit(
    path: Path,
    include_groups: IncludeGroups,
    excludes: ExcludePatterns,
    chain: set[Path],
  ) -> None:
    path = host.resolve(path)
    if path in chain:
      findings.append(f'Cyclic AGY {kind} config inheritance at {path}')
      return
    if host.path_kind(path) == 'missing':
      findings.append(f'AGY {kind} config path does not exist: {path}')
      return
    config = _read_agy_json(
      host, path, f'AGY {kind} configuration', findings
    )
    if config is None:
      return
    next_chain = chain | {path}

    entries = config.get('entries', [])
    if not isinstance(entries, list):
      findings.append(f'Invalid entries in AGY {kind} config {path}')
    else:
      for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
          findings.append(
            f'Invalid AGY {kind} config entry {index} in {path}'
          )
          continue
        entry_path = entry.get('path')
        if not isinstance(entry_path, str):
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
            _agy_resolve_path(host, entry_path, path, project_root),
            entry_include_groups,
            entry_excludes,
          )
        )

    inherits = config.get('inherits', [])
    if not isinstance(inherits, list):
      findings.append(f'Invalid inherits in AGY {kind} config {path}')
    else:
      for index, entry in enumerate(inherits):
        if not isinstance(entry, Mapping):
          findings.append(
            f'Invalid AGY {kind} inheritance entry {index} in {path}'
          )
          continue
        entry_path = entry.get('path')
        if not isinstance(entry_path, str):
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
          _agy_resolve_path(host, entry_path, path, project_root),
          inherit_include_groups,
          inherit_excludes,
          next_chain,
        )

  visit(config_path, (), (), set())
  return roots


def _agy_path_matches(
  path: Path,
  include_groups: IncludeGroups,
  excludes: ExcludePatterns,
) -> bool:
  names = (path.name, path.stem)
  return all(
    any(any(pattern.search(name) for name in names) for pattern in group)
    for group in include_groups
  ) and not any(
    any(pattern.search(name) for pattern in excludes) for name in names
  )


def _agy_customization_files(
  host: _Host,
  root: Path,
  filename: str,
  include_groups: IncludeGroups,
  excludes: ExcludePatterns,
  label: str,
  findings: list[str],
) -> list[Path]:
  root = host.resolve(root)
  kind = host.path_kind(root)
  if kind == 'missing':
    findings.append(f'AGY {label} path does not exist: {root}')
    return []
  if kind == 'file':
    matches = root.name == filename or (
      filename == '*.md' and root.suffix == '.md'
    )
    candidates: Sequence[Path] = (root,) if matches else ()
  elif kind == 'dir':
    try:
      candidates = host.rglob(root, filename)
    except OSError as error:
      findings.append(f'Cannot scan AGY {label} path {root}: {error}')
      return []
  else:
    findings.append(f'AGY {label} path is not a file or directory: {root}')
    return []

  files: list[Path] = []
  for candidate in candidates:
    try:
      resolved = host.resolve(candidate)
    except OSError:
      continue
    if host.path_kind(resolved) != 'file':
      continue
    match_target = resolved if filename == '*.md' else resolved.parent
    if _agy_path_matches(match_target, include_groups, excludes):
      files.append(resolved)
  return files


def _agy_rule_files(
  host: _Host, project_root: Path, findings: list[str]
) -> list[Path]:
  home = host.resolve(host.home)
  standard_candidates = (
    home / 'AGENTS.md',
    home / 'GEMINI.md',
    home / '.gemini' / 'AGENTS.md',
    home / '.gemini' / 'GEMINI.md',
  )
  files: list[Path] = []
  seen: set[Path] = set()
  for candidate in standard_candidates:
    try:
      resolved = host.resolve(candidate)
    except OSError:
      continue
    if host.path_kind(resolved) == 'file' and resolved not in seen:
      seen.add(resolved)
      files.append(resolved)

  for directory in (
    home / '.gemini' / 'rules',
    home / '.agents' / 'rules',
  ):
    resolved_dir = host.resolve(directory)
    if host.path_kind(resolved_dir) != 'dir':
      continue
    try:
      candidates = host.rglob(resolved_dir, '*.md')
    except OSError:
      candidates = ()
    for candidate in candidates:
      try:
        resolved = host.resolve(candidate)
      except OSError:
        continue
      if host.path_kind(resolved) == 'file' and resolved not in seen:
        seen.add(resolved)
        files.append(resolved)

  roots: list[RegisteredRoot] = []
  standard_rules_root = _agy_config_root(host) / 'rules'
  if host.path_kind(standard_rules_root) != 'missing':
    roots.append((standard_rules_root, (), ()))
  roots.extend(
    _agy_registered_roots(host, 'rules', project_root, findings)
  )
  for root, include_groups, excludes in roots:
    for rule_file in _agy_customization_files(
      host,
      root,
      '*.md',
      include_groups,
      excludes,
      'rules',
      findings,
    ):
      if rule_file not in seen:
        seen.add(rule_file)
        files.append(rule_file)

  return sorted(files)


def _agy_skill_files(
  host: _Host, project_root: Path, findings: list[str]
) -> list[Path]:
  roots: list[RegisteredRoot] = []
  standard_root = _agy_config_root(host) / 'skills'
  if host.path_kind(standard_root) != 'missing':
    roots.append((standard_root, (), ()))
  roots.extend(
    _agy_registered_roots(host, 'skills', project_root, findings)
  )
  files: list[Path] = []
  seen: set[Path] = set()
  for root, include_groups, excludes in roots:
    for skill_file in _agy_customization_files(
      host,
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


def _agy_plugin_manifests(
  host: _Host, project_root: Path, findings: list[str]
) -> list[Path]:
  roots: list[RegisteredRoot] = []
  standard_root = _agy_config_root(host) / 'plugins'
  if host.path_kind(standard_root) != 'missing':
    roots.append((standard_root, (), ()))
  roots.extend(
    _agy_registered_roots(host, 'plugins', project_root, findings)
  )
  manifests: list[Path] = []
  seen: set[Path] = set()
  for root, include_groups, excludes in roots:
    for manifest in _agy_customization_files(
      host,
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


def _agy_plugin_findings(
  host: _Host, project_root: Path, findings: list[str]
) -> None:
  manifests = _agy_plugin_manifests(host, project_root, findings)
  state_path = _agy_config_root(host) / 'config.json'
  state = _read_agy_json(host, state_path, 'AGY plugin state', findings)
  overrides: JsonObject = {}
  if state is not None:
    plugins = state.get('plugins', {})
    if not isinstance(plugins, dict):
      findings.append(f'Invalid plugins setting in {state_path}')
    else:
      overrides = plugins

  for manifest_path in manifests:
    manifest = _read_agy_json(
      host,
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
      if not isinstance(override, Mapping) or not isinstance(
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


def _agy_mcp_findings(host: _Host, findings: list[str]) -> None:
  config_path = _agy_config_root(host) / 'mcp_config.json'
  kind = host.path_kind(config_path)
  if kind == 'missing':
    return
  if kind != 'file':
    findings.append(
      f'AGY MCP configuration path is not a file: {config_path}'
    )
    return
  try:
    if not host.read_text(config_path).strip():
      return
  except OSError as error:
    findings.append(
      f'Cannot read AGY MCP configuration {config_path}: {error}'
    )
    return
  config = _read_agy_json(
    host,
    config_path,
    'AGY MCP configuration',
    findings,
  )
  if config is None:
    return
  servers = config.get('mcpServers', {})
  if not isinstance(servers, Mapping):
    findings.append(f'Invalid mcpServers setting in {config_path}')
    return
  for name in sorted(servers):
    findings.append(
      f'AGY MCP server {name!r} is configured in {config_path}; '
      'remove it because AGY has no persistent all-MCP disable setting'
    )


def _check_agy_ambient_state(host: _Host, project_root: Path) -> None:
  findings: list[str] = []
  for skill_file in _agy_skill_files(host, project_root, findings):
    findings.append(
      f'AGY skill {skill_file} is present; remove it or deregister its '
      'path because AGY has no persistent all-skills disable setting'
    )
  for rule_file in _agy_rule_files(host, project_root, findings):
    findings.append(
      f'AGY rule file {rule_file} is present; remove or rename it '
      'because AGY has no persistent setting to disable '
      'AGENTS.md/rules files'
    )
  _agy_plugin_findings(host, project_root, findings)
  _agy_mcp_findings(host, findings)
  if findings:
    detail = '\n'.join(f'  - {finding}' for finding in findings)
    raise click.ClickException(
      f'AGY filesystem preflight failed:\n{detail}'
    )


def _validate_toolset_probe_output(
  returncode: int, stdout: str, stderr: str
) -> None:
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
    raise click.ClickException(f'AGY tool preflight failed: {detail}')
  if initialized_agent != 'pentagram':
    raise click.ClickException(
      'AGY tool preflight did not initialize the pentagram custom agent'
    )
  if result_status is None:
    raise click.ClickException(
      'AGY tool preflight returned no stream-json result event'
    )
  if result_status != 'SUCCESS':
    detail = result_error or f'unexpected result status {result_status!r}'
    raise click.ClickException(f'AGY tool preflight failed: {detail}')


def _check_agy_toolset(
  host: _Host, project_root: Path, runtime_dir: Path, model: str
) -> None:
  probe_command = _build_toolset_probe_command(runtime_dir, model)
  try:
    result = host.run_command(
      probe_command, project_root, host.environ, True
    )
  except OSError as error:
    raise click.ClickException(
      f'AGY tool preflight failed: {error}'
    ) from error
  _validate_toolset_probe_output(
    result.returncode, result.stdout, result.stderr
  )


def _os_path_kind(path: Path) -> PathKind:
  if not path.exists():
    return 'missing'
  if path.is_file():
    return 'file'
  if path.is_dir():
    return 'dir'
  return 'other'


def _os_read_text(path: Path) -> str:
  return path.read_text(encoding='utf-8')


def _os_rglob(root: Path, pattern: str) -> tuple[Path, ...]:
  return tuple(root.rglob(pattern))


@contextmanager
def _os_runtime_adapter(agent_content: str) -> Iterator[Path]:
  with tempfile.TemporaryDirectory(prefix='pentagram-agy-') as raw_dir:
    runtime_dir = Path(raw_dir)
    agent_file = (
      runtime_dir / '.agents' / 'agents' / 'pentagram' / 'agent.md'
    )
    agent_file.parent.mkdir(parents=True)
    agent_file.write_text(agent_content, encoding='utf-8')
    yield runtime_dir


def _os_run_command(
  command: Sequence[str],
  cwd: Path,
  env: Mapping[str, str],
  capture_output: bool,
) -> subprocess.CompletedProcess[str]:
  return subprocess.run(
    command,
    cwd=cwd,
    env=env,
    capture_output=capture_output,
    text=True,
  )


def _os_host() -> _Host:
  return _Host(
    home=Path.home().resolve(),
    environ=os.environ,
    resolve=Path.resolve,
    path_kind=_os_path_kind,
    read_text=_os_read_text,
    rglob=_os_rglob,
    runtime_adapter=_os_runtime_adapter,
    run_command=_os_run_command,
  )
