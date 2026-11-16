import json
import os
import posixpath
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import click

from zero.lib import json_object

from .common import (
  exec_agent,
  is_under,
  read_regular_text,
  scan_ambient_files,
)

type CodexConfig = dict[str, object]
type CodexConfigEntry = tuple[Path, CodexConfig]

_ENV_VAR_PATTERN = re.compile(r'\$(?:(\w+)|\{([^}]+)\})')


@dataclass(frozen=True, slots=True)
class CodexState:
  home: Path
  codex_home: Path
  configs: tuple[CodexConfigEntry, ...]
  memory_files: tuple[Path, ...]
  skill_files: tuple[Path, ...]
  environ: Mapping[str, str]
  skill_path_resolutions: tuple[tuple[Path, Path], ...] = ()
  read_findings: tuple[str, ...] = ()


def parse_toml_config(
  raw: str, path: Path
) -> tuple[CodexConfig | None, str | None]:
  """Parse TOML text as a table, returning (config, error)."""
  try:
    loaded = tomllib.loads(raw)
  except tomllib.TOMLDecodeError as error:
    return None, f'Cannot read Codex config {path}: {error}'
  config = json_object(loaded)
  if config is None:
    return None, f'Invalid Codex config table: {path}'
  return config, None


def _read_toml_file(path: Path) -> tuple[CodexConfig | None, str | None]:
  raw, error = read_regular_text(path, 'Codex config')
  if raw is None:
    return None, error
  return parse_toml_config(raw, path)


def _expand_skill_raw_path(
  raw_path: str, home: Path, environ: Mapping[str, str]
) -> Path:
  expanded = _ENV_VAR_PATTERN.sub(
    lambda match: environ.get(
      match.group(1) or match.group(2), match.group(0)
    ),
    raw_path,
  )
  if expanded == '~':
    return home
  if expanded.startswith('~/'):
    return home / expanded[2:]
  return Path(expanded)


def _skill_config_path(
  raw_path: str, config_path: Path, home: Path, environ: Mapping[str, str]
) -> Path:
  path = _expand_skill_raw_path(raw_path, home, environ)
  if not path.is_absolute():
    path = config_path.parent / path
  if path.name != 'SKILL.md':
    path = path / 'SKILL.md'
  return Path(posixpath.normpath(str(path)))


def _codex_skill_overrides(
  configs: Sequence[CodexConfigEntry],
  home: Path,
  environ: Mapping[str, str],
) -> tuple[list[tuple[Path, bool]], list[str]]:
  overrides: list[tuple[Path, bool]] = []
  findings: list[str] = []
  for config_path, config in configs:
    skills = json_object(config.get('skills', {}))
    if skills is None:
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
    for index, raw_entry in enumerate(entries):
      entry = json_object(raw_entry)
      if entry is None:
        findings.append(
          f'Invalid skills.config entry {index} in Codex config '
          f'{config_path}'
        )
        continue
      raw_path = entry.get('path')
      if not isinstance(raw_path, str):
        findings.append(
          f'Invalid skills.config entry {index} in Codex config '
          f'{config_path}'
        )
        continue
      skill_path = _skill_config_path(raw_path, config_path, home, environ)
      enabled = entry.get('enabled')
      if not isinstance(enabled, bool):
        findings.append(
          f'Invalid skills.config entry {index} in Codex config '
          f'{config_path}'
        )
        overrides.append((skill_path, False))
        continue
      overrides.append((skill_path, enabled is False))
  return overrides, findings


def _codex_skill_files(
  codex_home: Path, findings: list[str]
) -> tuple[Path, ...]:
  plugin_roots: list[Path] = []
  for candidate in (
    codex_home / 'plugins',
    codex_home / '.tmp' / 'plugins',
  ):
    try:
      plugin_roots.append(candidate.resolve())
    except OSError:
      plugin_roots.append(candidate)

  scanned, scan_findings = scan_ambient_files(
    codex_home / 'skills',
    label='Codex skills',
    match_name='SKILL.md',
    allow_single_file=True,
  )
  findings.extend(scan_findings)
  return tuple(
    resolved
    for resolved in scanned
    if not any(is_under(resolved, root) for root in plugin_roots)
  )


def _codex_memory_files(
  codex_home: Path, findings: list[str]
) -> tuple[Path, ...]:
  scanned, scan_findings = scan_ambient_files(
    codex_home / 'memories', label='Codex memories'
  )
  findings.extend(scan_findings)
  return scanned


def _collect_codex_state(project_root: Path) -> CodexState:
  home = Path.home().resolve()
  codex_home = (home / '.codex').resolve()
  resolved_root = project_root.resolve()
  environ = MappingProxyType(dict(os.environ))
  findings: list[str] = []
  configs: list[CodexConfigEntry] = []
  seen_paths: set[Path] = set()

  user_candidate = codex_home / 'config.toml'
  user_config: CodexConfig | None = None
  try:
    user_config_path = user_candidate.resolve()
  except OSError as error:
    findings.append(f'Cannot read Codex config {user_candidate}: {error}')
  else:
    seen_paths.add(user_config_path)
    user_config, err = _read_toml_file(user_config_path)
    if err is not None:
      findings.append(err)
    elif user_config is not None:
      configs.append((user_config_path, user_config))

  extra_candidates = [resolved_root / '.codex' / 'config.toml']
  profile = user_config.get('profile') if user_config is not None else None
  if isinstance(profile, str) and profile:
    extra_candidates.append(codex_home / f'{profile}.config.toml')

  for candidate in extra_candidates:
    try:
      resolved = candidate.resolve()
    except OSError as error:
      findings.append(f'Cannot read Codex config {candidate}: {error}')
      continue
    if resolved in seen_paths:
      continue
    seen_paths.add(resolved)
    config, err = _read_toml_file(resolved)
    if err is not None:
      findings.append(err)
    elif config is not None:
      configs.append((resolved, config))

  memory_files = _codex_memory_files(codex_home, findings)
  skill_files = _codex_skill_files(codex_home, findings)

  overrides, _ = _codex_skill_overrides(configs, home, environ)
  resolutions: dict[Path, Path] = {}
  for skill_path, _ in overrides:
    if skill_path in resolutions:
      continue
    try:
      resolved_skill = skill_path.resolve()
    except OSError:
      continue
    if resolved_skill != skill_path:
      resolutions[skill_path] = resolved_skill

  return CodexState(
    home=home,
    codex_home=codex_home,
    configs=tuple(configs),
    memory_files=memory_files,
    skill_files=skill_files,
    environ=environ,
    skill_path_resolutions=tuple(sorted(resolutions.items())),
    read_findings=tuple(findings),
  )


def _codex_feature_remediation(setting: str, config_path: Path) -> str:
  _, name = setting.split('.', 1)
  return (
    f'run codex features disable {name}; this persists the disabled '
    f'state in {config_path}'
  )


def _codex_mcp_remediation(name: str, config_path: Path) -> str:
  return (
    f'set [mcp_servers.{json.dumps(name)}] enabled = false '
    f'in {config_path}'
  )


def _codex_mcp_findings(configs: Sequence[CodexConfigEntry]) -> list[str]:
  findings: list[str] = []
  for config_path, config in configs:
    servers = json_object(config.get('mcp_servers', {}))
    if servers is None:
      findings.append(
        f'Invalid mcp_servers table in Codex config {config_path}'
      )
      continue
    for name, value in sorted(servers.items()):
      server = json_object(value)
      if server is None or server.get('enabled') is not False:
        findings.append(
          f'Codex MCP server {name!r} is not disabled in {config_path}; '
          f'{_codex_mcp_remediation(name, config_path)}'
        )
  return findings


def _codex_feature_findings(
  configs: Sequence[CodexConfigEntry],
) -> list[str]:
  findings: list[str] = []
  settings: dict[str, list[tuple[object, Path]]] = {
    'features.memories': [],
    'features.plugins': [],
  }
  for config_path, config in configs:
    features = json_object(config.get('features', {}))
    if features is None:
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


def codex_preflight_findings(state: CodexState) -> tuple[str, ...]:
  """Evaluate all pure Codex preflight invariants against CodexState."""
  findings = list(state.read_findings)
  findings.extend(_codex_feature_findings(state.configs))
  findings.extend(_codex_mcp_findings(state.configs))

  for memory_file in state.memory_files:
    findings.append(
      f'Codex memory file {memory_file} is present; remove or rename it '
      'because Codex has no persistent setting to disable memory files'
    )

  overrides, override_findings = _codex_skill_overrides(
    state.configs, state.home, state.environ
  )
  findings.extend(override_findings)
  resolutions = dict(state.skill_path_resolutions)
  skill_states: dict[Path, bool] = {}
  for path, disabled in overrides:
    canonical = resolutions.get(path, path)
    if not disabled:
      skill_states[canonical] = False
    elif canonical not in skill_states:
      skill_states[canonical] = True
  disabled_paths = {
    path for path, disabled in skill_states.items() if disabled
  }

  for skill_file in state.skill_files:
    if skill_file not in disabled_paths:
      findings.append(
        f'Codex skill {skill_file} is not disabled; '
        f'run /skills and disable {skill_file}'
      )
  return tuple(findings)


def build_launch_command(
  project_root: Path, system_file: Path, model: str
) -> list[str]:
  """Build the Codex CLI command line."""
  config = f'model_instructions_file={json.dumps(str(system_file))}'
  return [
    'codex',
    '--model',
    model,
    '--config',
    config,
    '--dangerously-bypass-approvals-and-sandbox',
    '--cd',
    str(project_root),
  ]


def _check_codex_ambient_state(project_root: Path) -> None:
  findings = codex_preflight_findings(_collect_codex_state(project_root))
  if findings:
    detail = '\n'.join(f'  - {finding}' for finding in findings)
    raise click.ClickException(
      f'Codex filesystem preflight failed:\n{detail}'
    )


def launch(
  project_root: Path,
  system_file: Path,
  arguments: Sequence[str],
  model: str,
) -> None:
  """Run Codex preflight checks and replace the process with codex."""
  _check_codex_ambient_state(project_root)
  exec_agent(
    project_root,
    build_launch_command(project_root, system_file, model),
    arguments,
  )
