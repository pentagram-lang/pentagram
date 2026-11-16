import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import click

from . import agy, claude, codex


@dataclass(frozen=True, slots=True)
class AgentConfig:
  executable: str
  model: str


AGENT_CONFIGURATIONS: Mapping[str, AgentConfig] = {
  'codex-luna-yolo': AgentConfig('codex', 'gpt-6-luna'),
  'codex-sol-yolo': AgentConfig('codex', 'gpt-6-sol'),
  'codex-astra-yolo': AgentConfig('codex', 'gpt-6-astra'),
  'claude-sonnet-yolo': AgentConfig('claude', 'sonnet'),
  'claude-fable-yolo': AgentConfig('claude', 'fable'),
  'agy-flash-yolo': AgentConfig('agy', 'gemini-3.8-flash-high'),
  'agy-argon-yolo': AgentConfig('agy', 'gemini-4-argon-medium'),
  'agy-carbon-yolo': AgentConfig('agy', 'gemini-4-carbon-medium'),
}

_PROVIDERS = {
  'codex': codex.launch,
  'claude': claude.launch,
  'agy': agy.launch,
}


def _require_agent_config(agent_name: str) -> AgentConfig:
  config = AGENT_CONFIGURATIONS.get(agent_name)
  if config is None:
    raise click.ClickException(f'Unknown agent: {agent_name}')
  return config


def _validate_agent_launch(
  config: AgentConfig,
  system_file: Path,
  *,
  system_file_exists: bool,
  executable_available: bool,
) -> None:
  if not system_file_exists:
    raise click.ClickException(f'Missing system prompt: {system_file}')
  if not executable_available:
    raise click.ClickException(
      f'Agent executable not found on PATH: {config.executable}'
    )


def launch(agent_name: str, arguments: Sequence[str]) -> None:
  """Validate preflight invariants and launch the selected agent."""
  config = _require_agent_config(agent_name)
  project_root = Path(__file__).resolve().parents[2]
  system_file = project_root / 'sys.md'
  try:
    has_system_file = system_file.is_file()
  except OSError as error:
    raise click.ClickException(
      f'Cannot read system prompt {system_file}: {error}'
    ) from error

  _validate_agent_launch(
    config,
    system_file,
    system_file_exists=has_system_file,
    executable_available=shutil.which(config.executable) is not None,
  )
  _PROVIDERS[config.executable](
    project_root, system_file, arguments, config.model
  )
