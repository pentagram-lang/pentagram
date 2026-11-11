import shutil
from collections.abc import Sequence
from pathlib import Path

import click

from . import agy, claude, codex

AGENT_CONFIGURATIONS = {
  'codex-luna-yolo': ('codex', 'gpt-6-luna'),
  'codex-sol-yolo': ('codex', 'gpt-6-sol'),
  'codex-astra-yolo': ('codex', 'gpt-6-astra'),
  'claude-sonnet-yolo': ('claude', 'sonnet'),
  'claude-fable-yolo': ('claude', 'fable'),
  'agy-flash-yolo': ('agy', 'gemini-3.8-flash-high'),
  'agy-argon-yolo': ('agy', 'gemini-4-argon-medium'),
  'agy-carbon-yolo': ('agy', 'gemini-4-carbon-medium'),
}

_PROVIDERS = {
  'codex': codex.launch,
  'claude': claude.launch,
  'agy': agy.launch,
}


def launch(agent_name: str, arguments: Sequence[str]) -> None:
  project_root = Path(__file__).resolve().parents[2]
  system_file = project_root / 'sys.md'

  if not system_file.is_file():
    raise click.ClickException(f'Missing system prompt: {system_file}')

  executable, model = AGENT_CONFIGURATIONS[agent_name]
  if shutil.which(executable) is None:
    raise click.ClickException(
      f'Agent executable not found on PATH: {executable}'
    )

  _PROVIDERS[executable](project_root, system_file, arguments, model)
