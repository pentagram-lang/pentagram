from __future__ import annotations

import shutil
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import click

from zero.agent import agy, claude, codex

ProviderLauncher = Callable[[Path, str, Path, Sequence[str]], None]


@dataclass(frozen=True, slots=True)
class AgentConfig:
  executable: str
  model: str


AGENT_CONFIGURATIONS: dict[str, AgentConfig] = {
  'codex-luna-yolo': AgentConfig('codex', 'gpt-6-luna'),
  'codex-sol-yolo': AgentConfig('codex', 'gpt-6-sol'),
  'codex-astra-yolo': AgentConfig('codex', 'gpt-6-astra'),
  'claude-sonnet-yolo': AgentConfig('claude', 'sonnet'),
  'claude-fable-yolo': AgentConfig('claude', 'fable'),
  'agy-flash-yolo': AgentConfig('agy', 'gemini-3.8-flash-high'),
  'agy-argon-yolo': AgentConfig('agy', 'gemini-4-argon-medium'),
  'agy-carbon-yolo': AgentConfig('agy', 'gemini-4-carbon-medium'),
}

_DEFAULT_PROVIDERS: dict[str, ProviderLauncher] = {
  'codex': codex.launch,
  'claude': claude.launch,
  'agy': agy.launch,
}


def launch(
  agent_name: str,
  arguments: Sequence[str],
  *,
  repo: Path | None = None,
  which_fn: Callable[[str], str | None] = shutil.which,
  providers: Mapping[str, ProviderLauncher] | None = None,
) -> None:
  config = AGENT_CONFIGURATIONS.get(agent_name)
  if config is None:
    raise click.ClickException(f'Unknown agent target: {agent_name}')

  project_root = (
    Path(__file__).resolve().parents[2] if repo is None else repo.resolve()
  )
  system_file = (project_root / 'sys.md').resolve()
  try:
    st = system_file.stat()
  except OSError as err:
    raise click.ClickException(
      f'Missing system prompt file ({system_file}): {err}'
    ) from err
  if not stat.S_ISREG(st.st_mode):
    raise click.ClickException(
      f'System prompt path is not a regular file: {system_file}'
    )

  if which_fn(config.executable) is None:
    raise click.ClickException(
      f'Agent executable not found on PATH: {config.executable}'
    )

  provider_map = _DEFAULT_PROVIDERS if providers is None else providers
  launcher = provider_map.get(config.executable)
  if launcher is None:
    raise click.ClickException(
      f'Unsupported agent provider: {config.executable}'
    )

  launcher(project_root, config.model, system_file, arguments)
