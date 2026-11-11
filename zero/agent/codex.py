import json
import os
import tomllib
from collections.abc import Sequence
from pathlib import Path

import click

from .common import _exec_agent, _is_under

type CodexConfig = dict[str, object]
type CodexConfigEntry = tuple[Path, CodexConfig]


def _string_keyed_object(value: object) -> CodexConfig | None:
  if not isinstance(value, dict):
    return None
  result: CodexConfig = {}
  for key, item in value.items():
    if not isinstance(key, str):
      return None
    result[key] = item
  return result


def _codex_home() -> Path:
  return Path.home() / '.codex'


def _codex_config_paths(project_root: Path) -> list[Path]:
  paths = [_codex_home() / 'config.toml']
  project_config = project_root / '.codex' / 'config.toml'
  paths.append(project_config)

  user_config = paths[0]
  if user_config.is_file():
    try:
      config = _string_keyed_object(tomllib.loads(user_config.read_text()))
    except (OSError, tomllib.TOMLDecodeError):
      config = None
    profile = config.get('profile') if config is not None else None
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


def _read_codex_configs(
  project_root: Path,
) -> tuple[list[CodexConfigEntry], list[str]]:
  configs: list[CodexConfigEntry] = []
  findings: list[str] = []
  for path in _codex_config_paths(project_root):
    if not path.exists():
      continue
    if not path.is_file():
      findings.append(f'Codex config path is not a file: {path}')
      continue
    try:
      config = _string_keyed_object(tomllib.loads(path.read_text()))
      if config is None:
        findings.append(f'Invalid Codex config table: {path}')
      else:
        configs.append((path, config))
    except (OSError, tomllib.TOMLDecodeError) as error:
      findings.append(f'Cannot read Codex config {path}: {error}')
  return configs, findings


def _codex_plugin_roots() -> tuple[Path, Path]:
  codex_home = _codex_home()
  return (
    (codex_home / 'plugins').expanduser().resolve(),
    (codex_home / '.tmp' / 'plugins').expanduser().resolve(),
  )


def _codex_skill_files() -> list[Path]:
  roots = [_codex_home() / 'skills']
  plugin_roots = _codex_plugin_roots()
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


def _codex_memory_files() -> list[Path]:
  files: list[Path] = []
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


def _skill_config_path(raw_path: str, config_path: Path) -> Path:
  path = Path(os.path.expandvars(raw_path)).expanduser()
  if not path.is_absolute():
    path = config_path.parent / path
  if path.name != 'SKILL.md':
    path /= 'SKILL.md'
  return path.resolve()


def _codex_skill_overrides(
  configs: Sequence[CodexConfigEntry], findings: list[str]
) -> list[tuple[Path, bool, Path]]:
  overrides: list[tuple[Path, bool, Path]] = []
  for config_path, config in configs:
    skills = _string_keyed_object(config.get('skills', {}))
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
    for index, entry in enumerate(entries):
      entry = _string_keyed_object(entry)
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
      overrides.append(
        (
          _skill_config_path(raw_path, config_path),
          entry.get('enabled') is False,
          config_path,
        )
      )
  return overrides


def _codex_feature_remediation(
  setting: str, config_path: Path | None = None
) -> str:
  _, name = setting.split('.', 1)
  config_path = config_path or (_codex_home() / 'config.toml')
  return (
    f'run codex features disable {name}; this persists the disabled '
    f'state in {config_path}'
  )


def _codex_mcp_remediation(name: str, config_path: Path) -> str:
  return (
    f'set [mcp_servers.{json.dumps(name)}] enabled = false '
    f'in {config_path}'
  )


def _codex_skill_remediation(skill_file: Path) -> str:
  return f'run /skills and disable {skill_file}'


def _codex_mcp_findings(
  configs: Sequence[CodexConfigEntry],
) -> list[str]:
  findings: list[str] = []
  for config_path, config in configs:
    servers = _string_keyed_object(config.get('mcp_servers', {}))
    if servers is None:
      findings.append(
        f'Invalid mcp_servers table in Codex config {config_path}'
      )
    else:
      for name, value in servers.items():
        server = _string_keyed_object(value)
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
    features = _string_keyed_object(config.get('features', {}))
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


def _check_codex_ambient_state(project_root: Path) -> None:
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


def launch(
  project_root: Path,
  system_file: Path,
  arguments: Sequence[str],
  model: str,
) -> None:
  _check_codex_ambient_state(project_root)
  config = f'model_instructions_file={json.dumps(str(system_file))}'
  command = [
    'codex',
    '--model',
    model,
    '--config',
    config,
    '--dangerously-bypass-approvals-and-sandbox',
    '--cd',
    str(project_root),
  ]
  _exec_agent(project_root, command, arguments)
