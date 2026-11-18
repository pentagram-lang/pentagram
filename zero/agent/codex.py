from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path

from zero.agent.common import (
  ExecFn,
  exec_agent,
  expand_env_path,
  is_under,
  json_object,
  raise_preflight,
  read_regular_text,
  scan_ambient_files,
)

_FEATURE_REMEDIATIONS = (
  ('memories', 'codex features disable memories'),
  ('plugins', 'codex features disable plugins'),
)


def _read_toml_config(
  path: Path, label: str
) -> tuple[dict[str, object] | None, str | None]:
  raw, err = read_regular_text(path, label)
  if err is not None:
    return None, err
  if raw is None:
    return None, None
  try:
    parsed = tomllib.loads(raw)
  except tomllib.TOMLDecodeError as exc:
    return None, f'Invalid TOML in {label} ({path}): {exc}'
  obj = json_object(parsed)
  if obj is None:
    return None, f'Expected TOML table in {label} ({path})'
  return obj, None


def _load_codex_configs(
  codex_dir: Path, project_root: Path
) -> tuple[list[tuple[Path, dict[str, object]]], list[str]]:
  loaded: list[tuple[Path, dict[str, object]]] = []
  findings: list[str] = []
  seen: set[Path] = set()

  def _load_one(path: Path, label: str) -> dict[str, object] | None:
    resolved = path.resolve()
    if resolved in seen:
      return None
    seen.add(resolved)
    data, err = _read_toml_config(path, label)
    if err is not None:
      findings.append(err)
      return None
    if data is not None:
      loaded.append((path, data))
    return data

  home_cfg = _load_one(codex_dir / 'config.toml', 'Codex home config')
  if home_cfg is not None:
    profile = home_cfg.get('profile')
    if isinstance(profile, str) and profile:
      _load_one(
        codex_dir / f'{profile}.config.toml',
        f'Codex profile config {profile!r}',
      )
  _load_one(project_root / '.codex' / 'config.toml', 'Codex repo config')
  return loaded, findings


def _check_config_tables(
  configs: Sequence[tuple[Path, dict[str, object]]],
  home: Path,
  environ: Mapping[str, str],
) -> tuple[list[str], dict[Path, list[bool]]]:
  findings: list[str] = []
  skill_states: dict[Path, list[bool]] = {}

  for cfg_path, data in configs:
    if 'profile' in data:
      profile = data['profile']
      if not (isinstance(profile, str) and profile == ''):
        findings.append(
          f'Codex config {cfg_path} sets profile={profile!r}; '
          'clear or remove `profile`'
        )

    if 'features' in data:
      features = json_object(data['features'])
      if features is None:
        findings.append(
          f'Codex config {cfg_path} has non-table [features]'
        )
      else:
        for key, cmd in _FEATURE_REMEDIATIONS:
          if key in features and features[key] is not False:
            findings.append(
              f'Codex feature {key!r} must be false or omitted in '
              f'{cfg_path}; run `{cmd}`'
            )

    if 'mcp_servers' in data:
      servers = json_object(data['mcp_servers'])
      if servers is None:
        findings.append(
          f'Codex config {cfg_path} has non-table [mcp_servers]'
        )
      else:
        for name, raw_entry in sorted(servers.items()):
          entry = json_object(raw_entry)
          if entry is None or entry.get('enabled') is not False:
            findings.append(
              f'Codex MCP server {name!r} in {cfg_path} must set '
              'enabled = false'
            )

    if 'skills' in data:
      skills_obj = json_object(data['skills'])
      if skills_obj is None:
        findings.append(f'Codex config {cfg_path} has non-table [skills]')
      elif 'config' in skills_obj:
        entries = skills_obj['config']
        if not isinstance(entries, list):
          findings.append(
            f'Codex config {cfg_path} has non-list skills.config'
          )
        else:
          for raw_entry in entries:
            entry = json_object(raw_entry)
            if entry is None:
              findings.append(
                f'Codex config {cfg_path} has non-table '
                'skills.config entry'
              )
              continue
            raw_path = entry.get('path')
            if not isinstance(raw_path, str) or not raw_path:
              findings.append(
                f'Codex config {cfg_path} has skills.config entry '
                'without valid path'
              )
              continue
            expanded = expand_env_path(raw_path, home, environ)
            target = (
              expanded
              if expanded.is_absolute()
              else cfg_path.parent / expanded
            )
            if target.name != 'SKILL.md':
              target = target / 'SKILL.md'
            skill_states.setdefault(target.resolve(), []).append(
              entry.get('enabled') is False
            )

  return findings, skill_states


def preflight_codex(
  project_root: Path,
  *,
  home: Path | None = None,
  environ: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
  resolved_home = Path.home() if home is None else home
  resolved_env = os.environ if environ is None else environ
  codex_dir = resolved_home / '.codex'

  configs, findings = _load_codex_configs(codex_dir, project_root)
  table_findings, skill_states = _check_config_tables(
    configs, resolved_home, resolved_env
  )
  findings.extend(table_findings)

  mem_files, mem_errors = scan_ambient_files(
    codex_dir / 'memories',
    label='Codex memories',
    allow_single_file=True,
  )
  findings.extend(mem_errors)
  for mem_file in mem_files:
    findings.append(
      'Codex ambient memory file blocks launch '
      f'(no persistent disable setting): {mem_file}'
    )

  skill_files, skill_errors = scan_ambient_files(
    codex_dir / 'skills',
    label='Codex skills',
    match_name='SKILL.md',
  )
  findings.extend(skill_errors)
  excluded = (codex_dir / 'plugins', codex_dir / '.tmp' / 'plugins')
  for skill_file in skill_files:
    if any(is_under(skill_file, root) for root in excluded):
      continue
    states = skill_states.get(skill_file.resolve(), [])
    if not states or not all(states):
      findings.append(
        f'Codex skill {skill_file} must be disabled with '
        'enabled = false via /skills'
      )

  return tuple(findings)


def build_codex_command(
  model: str, system_file: Path, project_root: Path
) -> list[str]:
  return [
    'codex',
    '--model',
    model,
    '--config',
    f'model_instructions_file={json.dumps(str(system_file))}',
    '--dangerously-bypass-approvals-and-sandbox',
    '--cd',
    str(project_root),
  ]


def launch(
  project_root: Path,
  model: str,
  system_file: Path,
  arguments: Sequence[str],
  *,
  home: Path | None = None,
  environ: Mapping[str, str] | None = None,
  exec_fn: ExecFn = exec_agent,
) -> None:
  resolved_root = project_root.resolve()
  resolved_system = system_file.resolve()
  findings = preflight_codex(resolved_root, home=home, environ=environ)
  raise_preflight('Codex', findings)
  command = build_codex_command(model, resolved_system, resolved_root)
  exec_fn(resolved_root, command, arguments)
