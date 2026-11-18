from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import click

from zero.agent.common import (
  check_ambient_file,
  expand_env_path,
  json_object,
  parse_json_object,
  raise_preflight,
  read_json_file,
  read_regular_text,
  scan_ambient_files,
  string_list,
)

AGY_TOOLSET_ENV = 'PENTAGRAM_AGY_TOOLSET'
AGY_ADAPTER_RELPATH = Path('.agents/agents/pentagram/agent.md')
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

RunFn = Callable[
  [Sequence[str], Path, bool], subprocess.CompletedProcess[str]
]


def _run_subprocess(
  command: Sequence[str], cwd: Path, capture: bool
) -> subprocess.CompletedProcess[str]:
  try:
    return subprocess.run(
      command,
      cwd=cwd,
      capture_output=capture,
      text=True,
      check=False,
    )
  except OSError as error:
    raise click.ClickException(
      f'Failed to launch agent {command[0]}: {error}'
    ) from error


def render_agent_adapter(
  system_content: str, tools: Sequence[str] = AGY_AGENT_TOOLS
) -> str:
  lines = [
    '---',
    'name: pentagram',
    'description: Pentagram engineering agent governed by the '
    'repository-root system contract.',
    'tools:',
    *(f'  - {tool}' for tool in tools),
    'commandExecutionPolicy: eager',
    '---',
    '',
    system_content,
  ]
  return '\n'.join(lines)


def _resolve_agy_path(
  raw_path: str,
  config_path: Path,
  project_root: Path,
  home: Path,
  environ: Mapping[str, str],
) -> Path:
  expanded = expand_env_path(raw_path, home, environ)
  if expanded.is_absolute():
    return expanded
  repo_candidate = project_root / expanded
  try:
    exists_in_repo = repo_candidate.exists()
  except OSError:
    return repo_candidate
  return (
    repo_candidate if exists_in_repo else config_path.parent / expanded
  )


def _compile_patterns(
  raw: object, *, field: str, cfg_path: Path
) -> tuple[tuple[re.Pattern[str], ...], str | None]:
  if raw is None:
    return (), None
  if isinstance(raw, str):
    items: list[str] | None = [raw]
  else:
    items = string_list(raw)
  if items is None:
    return (), f'Expected string list for {field} in {cfg_path}'
  compiled: list[re.Pattern[str]] = []
  for pattern in items:
    try:
      compiled.append(re.compile(pattern))
    except re.error as err:
      return (), (
        f'Invalid regex {pattern!r} for {field} in {cfg_path}: {err}'
      )
  return tuple(compiled), None


def _matches_filters(
  candidate: Path,
  *,
  target_from_parent: bool,
  include_groups: Sequence[Sequence[re.Pattern[str]]],
  exclude: Sequence[re.Pattern[str]],
) -> bool:
  target = candidate.parent if target_from_parent else candidate
  names = (target.name, target.stem)
  for group in include_groups:
    if group and not any(
      pat.search(name) for pat in group for name in names
    ):
      return False
  if exclude and any(
    pat.search(name) for pat in exclude for name in names
  ):
    return False
  return True


def _parse_entry_spec(
  raw_entry: object, cfg_path: Path
) -> tuple[
  str | None,
  tuple[re.Pattern[str], ...],
  tuple[re.Pattern[str], ...],
  str | None,
]:
  if isinstance(raw_entry, str):
    if not raw_entry:
      return None, (), (), f'Empty entry path in {cfg_path}'
    return raw_entry, (), (), None
  entry = json_object(raw_entry)
  if entry is None:
    return None, (), (), f'Expected entry object or string in {cfg_path}'
  raw_path = entry.get('path')
  if not isinstance(raw_path, str) or not raw_path:
    return None, (), (), f'Entry missing valid path in {cfg_path}'
  include_only, inc_err = _compile_patterns(
    entry.get('include_only'), field='include_only', cfg_path=cfg_path
  )
  if inc_err is not None:
    return None, (), (), inc_err
  exclude, exc_err = _compile_patterns(
    entry.get('exclude'), field='exclude', cfg_path=cfg_path
  )
  if exc_err is not None:
    return None, (), (), exc_err
  return raw_path, include_only, exclude, None


def _collect_registry_files(
  config_path: Path,
  project_root: Path,
  home: Path,
  environ: Mapping[str, str],
  *,
  label: str,
  match_name: str | None = None,
  suffix: str | None = None,
  target_from_parent: bool,
) -> tuple[list[Path], list[str]]:
  found: list[Path] = []
  errors: list[str] = []
  pending: list[
    tuple[
      Path,
      bool,
      tuple[tuple[re.Pattern[str], ...], ...],
      tuple[re.Pattern[str], ...],
      frozenset[Path],
    ]
  ] = [(config_path, False, (), (), frozenset())]

  while pending:
    cfg_path, is_inherited, parent_includes, parent_excludes, ancestors = (
      pending.pop()
    )
    resolved_cfg = cfg_path.resolve()
    if resolved_cfg in ancestors:
      continue
    next_ancestors = ancestors | {resolved_cfg}

    data, err = read_json_file(cfg_path, f'{label} registry')
    if err is not None:
      errors.append(err)
      continue
    if data is None:
      if is_inherited:
        errors.append(
          f'{label} inherited config does not exist: {cfg_path}'
        )
      continue

    if 'inherits' in data:
      raw_inherits = data['inherits']
      if not isinstance(raw_inherits, list):
        errors.append(f'Expected list for inherits in {cfg_path}')
      else:
        for raw_item in reversed(raw_inherits):
          raw_parent, inc_pats, exc_pats, item_err = _parse_entry_spec(
            raw_item, cfg_path
          )
          if item_err is not None or raw_parent is None:
            if item_err is not None:
              errors.append(item_err)
            continue
          parent_path = _resolve_agy_path(
            raw_parent, cfg_path, project_root, home, environ
          )
          next_includes = (
            (*parent_includes, inc_pats) if inc_pats else parent_includes
          )
          next_excludes = (*parent_excludes, *exc_pats)
          pending.append(
            (
              parent_path,
              True,
              next_includes,
              next_excludes,
              next_ancestors,
            )
          )

    if 'entries' in data:
      entries = data['entries']
      if not isinstance(entries, list):
        errors.append(f'Expected list for entries in {cfg_path}')
      else:
        for raw_entry in entries:
          raw_path, include_only, exclude, entry_err = _parse_entry_spec(
            raw_entry, cfg_path
          )
          if entry_err is not None or raw_path is None:
            if entry_err is not None:
              errors.append(entry_err)
            continue
          entry_target = _resolve_agy_path(
            raw_path, cfg_path, project_root, home, environ
          )
          files, scan_errors = scan_ambient_files(
            entry_target,
            label=label,
            match_name=match_name,
            suffix=suffix,
            allow_single_file=True,
          )
          errors.extend(scan_errors)
          eff_includes = (
            (*parent_includes, include_only)
            if include_only
            else parent_includes
          )
          eff_excludes = (*parent_excludes, *exclude)
          for candidate in files:
            if _matches_filters(
              candidate,
              target_from_parent=target_from_parent,
              include_groups=eff_includes,
              exclude=eff_excludes,
            ):
              found.append(candidate)

  return found, errors


def _dedupe_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
  by_resolved: dict[Path, Path] = {}
  for path in paths:
    by_resolved.setdefault(path.resolve(), path)
  return tuple(sorted(by_resolved.values()))


def _check_mcp_config(mcp_config_path: Path) -> list[str]:
  raw, err = read_regular_text(mcp_config_path, 'AGY MCP config')
  if err is not None:
    return [err]
  if raw is None or not raw.strip():
    return []
  data, parse_err = parse_json_object(
    raw, mcp_config_path, 'AGY MCP config'
  )
  if parse_err is not None:
    return [parse_err]
  if data is None or 'mcpServers' not in data:
    return []
  servers = json_object(data['mcpServers'])
  if servers is None:
    return [f'Expected JSON object for mcpServers in {mcp_config_path}']
  return [
    f'AGY standalone MCP server {name!r} in {mcp_config_path} '
    'blocks launch (no persistent disable setting)'
    for name in sorted(servers)
  ]


def _check_plugins(
  plugin_paths: Sequence[Path], config_path: Path
) -> list[str]:
  findings: list[str] = []
  config_data, config_err = read_json_file(config_path, 'AGY config')
  overrides: dict[str, object] | None = {}
  if config_err is not None:
    findings.append(config_err)
    overrides = None
  elif config_data is not None and 'plugins' in config_data:
    overrides = json_object(config_data['plugins'])
    if overrides is None:
      findings.append(f'Expected JSON object for plugins in {config_path}')

  for plugin_json_path in plugin_paths:
    plugin_data, plugin_err = read_json_file(
      plugin_json_path, 'AGY plugin manifest'
    )
    if plugin_err is not None:
      findings.append(plugin_err)
      continue
    if plugin_data is None or overrides is None:
      continue

    plugin_name = plugin_json_path.parent.name
    if plugin_name in overrides:
      override = json_object(overrides[plugin_name])
      if override is None:
        findings.append(
          f'Expected JSON object for plugins[{plugin_name!r}] '
          f'in {config_path}'
        )
        continue
      override_enabled = override.get('enabled')
      if not isinstance(override_enabled, bool):
        findings.append(
          f'AGY plugin {plugin_name!r} override in {config_path} '
          'must set boolean enabled'
        )
        continue
      if override_enabled is False:
        continue
      findings.append(
        f'AGY plugin {plugin_name!r} ({plugin_json_path}) is enabled; '
        f'disable it in {config_path}'
      )
      continue

    if plugin_data.get('disabled') is not True:
      findings.append(
        f'AGY plugin {plugin_name!r} ({plugin_json_path}) must be '
        f'disabled in {config_path} or via disabled: true in '
        f'{plugin_json_path}'
      )

  return findings


def preflight_agy(
  project_root: Path,
  *,
  home: Path | None = None,
  environ: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
  resolved_home = Path.home() if home is None else home
  resolved_env = os.environ if environ is None else environ
  resolved_root = project_root.resolve()
  gemini_dir = resolved_home / '.gemini'
  config_dir = gemini_dir / 'config'
  findings: list[str] = []

  skill_files, skill_errs = scan_ambient_files(
    config_dir / 'skills', label='AGY skills', match_name='SKILL.md'
  )
  reg_skills, reg_skill_errs = _collect_registry_files(
    config_dir / 'skills.json',
    resolved_root,
    resolved_home,
    resolved_env,
    label='AGY skills',
    match_name='SKILL.md',
    target_from_parent=True,
  )
  findings.extend(skill_errs)
  findings.extend(reg_skill_errs)
  for skill_file in _dedupe_paths([*skill_files, *reg_skills]):
    findings.append(
      'AGY standalone skill blocks launch '
      f'(no persistent disable setting): {skill_file}'
    )

  rule_candidates: list[Path] = []
  for root_rule in (
    resolved_home / 'AGENTS.md',
    resolved_home / 'GEMINI.md',
    gemini_dir / 'AGENTS.md',
    gemini_dir / 'GEMINI.md',
  ):
    found_rule, rule_err = check_ambient_file(
      root_rule, label='AGY rule file'
    )
    if rule_err is not None:
      findings.append(rule_err)
    elif found_rule is not None:
      rule_candidates.append(found_rule)

  for rules_dir in (
    gemini_dir / 'rules',
    resolved_home / '.agents' / 'rules',
    config_dir / 'rules',
  ):
    dir_rules, dir_rule_errs = scan_ambient_files(
      rules_dir, label='AGY rules', suffix='.md'
    )
    findings.extend(dir_rule_errs)
    rule_candidates.extend(dir_rules)

  reg_rules, reg_rule_errs = _collect_registry_files(
    config_dir / 'rules.json',
    resolved_root,
    resolved_home,
    resolved_env,
    label='AGY rules',
    suffix='.md',
    target_from_parent=False,
  )
  findings.extend(reg_rule_errs)
  rule_candidates.extend(reg_rules)
  for rule_file in _dedupe_paths(rule_candidates):
    findings.append(
      'AGY standalone rule file blocks launch '
      f'(no persistent disable setting): {rule_file}'
    )

  findings.extend(_check_mcp_config(config_dir / 'mcp_config.json'))

  plugin_files, plugin_errs = scan_ambient_files(
    config_dir / 'plugins', label='AGY plugins', match_name='plugin.json'
  )
  reg_plugins, reg_plugin_errs = _collect_registry_files(
    config_dir / 'plugins.json',
    resolved_root,
    resolved_home,
    resolved_env,
    label='AGY plugins',
    match_name='plugin.json',
    target_from_parent=True,
  )
  findings.extend(plugin_errs)
  findings.extend(reg_plugin_errs)
  findings.extend(
    _check_plugins(
      _dedupe_paths([*plugin_files, *reg_plugins]),
      config_dir / 'config.json',
    )
  )

  return tuple(findings)


def toolset_probe_error(
  proc: subprocess.CompletedProcess[str],
) -> str | None:
  if proc.returncode != 0:
    detail = proc.stderr.strip() or proc.stdout.strip()
    return f'AGY toolset probe exited with {proc.returncode}: {detail}'

  saw_init = False
  saw_success = False
  for line in proc.stdout.splitlines():
    stripped = line.strip()
    if not stripped:
      continue
    try:
      parsed = json.loads(stripped)
    except json.JSONDecodeError:
      continue
    envelope = json_object(parsed)
    if envelope is None:
      continue
    event_type = envelope.get('event')
    if event_type == 'init':
      init_obj = json_object(envelope.get('init'))
      agent_name = None if init_obj is None else init_obj.get('agent')
      if agent_name != 'pentagram':
        return (
          f'AGY toolset probe initialized unexpected agent: {agent_name!r}'
        )
      saw_init = True
    elif event_type == 'result':
      result_obj = json_object(envelope.get('result'))
      if result_obj is None:
        return 'AGY toolset probe emitted invalid result event'
      status = result_obj.get('status')
      if status != 'SUCCESS':
        err_detail = result_obj.get('error')
        suffix = f' ({err_detail})' if err_detail else ''
        return (
          f'AGY toolset probe returned non-SUCCESS status: '
          f'{status!r}{suffix}'
        )
      saw_success = True

  if not saw_init:
    return 'AGY toolset probe did not emit an init event for pentagram'
  if not saw_success:
    return 'AGY toolset probe did not emit a SUCCESS result event'
  return None


def launch(
  project_root: Path,
  model: str,
  system_file: Path,
  arguments: Sequence[str],
  *,
  home: Path | None = None,
  environ: Mapping[str, str] | None = None,
  run_fn: RunFn = _run_subprocess,
  runtime_parent: Path | None = None,
) -> None:
  resolved_home = Path.home() if home is None else home
  resolved_env = os.environ if environ is None else environ
  resolved_root = project_root.resolve()
  resolved_system = system_file.resolve()

  findings = preflight_agy(
    resolved_root, home=resolved_home, environ=resolved_env
  )
  raise_preflight('AGY', findings)

  system_content, sys_err = read_regular_text(
    resolved_system, 'AGY system prompt'
  )
  if sys_err is not None:
    raise click.ClickException(sys_err)
  if system_content is None:
    raise click.ClickException(
      f'Missing system prompt file: {resolved_system}'
    )

  adapter_text = render_agent_adapter(system_content)
  with tempfile.TemporaryDirectory(
    prefix='pentagram-agy-', dir=runtime_parent
  ) as tmp:
    runtime_dir = Path(tmp)
    adapter_path = runtime_dir / AGY_ADAPTER_RELPATH
    adapter_path.parent.mkdir(parents=True, exist_ok=True)
    adapter_path.write_text(adapter_text, encoding='utf-8')

    if AGY_TOOLSET_ENV in resolved_env:
      probe_cmd = [
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
        'Reply OK and do not call any tools.',
      ]
      probe_proc = run_fn(probe_cmd, resolved_root, True)
      probe_err = toolset_probe_error(probe_proc)
      if probe_err is not None:
        raise click.ClickException(probe_err)

    command = [
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
    proc = run_fn(command, resolved_root, False)
  exit_code = (
    128 - proc.returncode if proc.returncode < 0 else proc.returncode
  )
  raise click.exceptions.Exit(exit_code)
