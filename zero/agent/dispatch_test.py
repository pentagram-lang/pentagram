from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import click
import pytest

from zero.agent import launch
from zero.agent.dispatch import (
  AGENT_CONFIGURATIONS,
  AgentConfig,
  ProviderLauncher,
)


@pytest.fixture
def shm_repo() -> Iterator[Path]:
  root = Path(
    tempfile.mkdtemp(prefix='zero-agent-dispatch-', dir='/dev/shm')
  )
  try:
    yield root
  finally:
    shutil.rmtree(root, ignore_errors=True)


def test_agent_configurations_match_spec() -> None:
  assert AGENT_CONFIGURATIONS == {
    'codex-luna-yolo': AgentConfig('codex', 'gpt-6-luna'),
    'codex-sol-yolo': AgentConfig('codex', 'gpt-6-sol'),
    'codex-astra-yolo': AgentConfig('codex', 'gpt-6-astra'),
    'claude-sonnet-yolo': AgentConfig('claude', 'sonnet'),
    'claude-fable-yolo': AgentConfig('claude', 'fable'),
    'agy-flash-yolo': AgentConfig('agy', 'gemini-3.8-flash-high'),
    'agy-argon-yolo': AgentConfig('agy', 'gemini-4-argon-medium'),
    'agy-carbon-yolo': AgentConfig('agy', 'gemini-4-carbon-medium'),
  }


def test_dispatch_validates_target_sys_md_and_path(shm_repo: Path) -> None:
  with pytest.raises(
    click.ClickException, match='Unknown agent target: bad'
  ):
    launch('bad', (), repo=shm_repo)

  with pytest.raises(
    click.ClickException, match='Missing system prompt file'
  ):
    launch(
      'codex-luna-yolo',
      (),
      repo=shm_repo,
      which_fn=lambda exe: f'/usr/bin/{exe}',
    )

  sys_file = shm_repo / 'sys.md'
  sys_file.mkdir()
  with pytest.raises(
    click.ClickException, match='System prompt path is not a regular file'
  ):
    launch(
      'codex-luna-yolo',
      (),
      repo=shm_repo,
      which_fn=lambda exe: f'/usr/bin/{exe}',
    )
  sys_file.rmdir()

  sys_file.write_text('# sys', encoding='utf-8')
  with pytest.raises(
    click.ClickException,
    match='Agent executable not found on PATH: claude',
  ):
    launch(
      'claude-sonnet-yolo',
      (),
      repo=shm_repo,
      which_fn=lambda _exe: None,
    )


def test_dispatch_routes_to_provider_launcher(shm_repo: Path) -> None:
  sys_file = shm_repo / 'sys.md'
  sys_file.write_text('# sys', encoding='utf-8')

  calls: list[tuple[str, Path, str, Path, tuple[str, ...]]] = []

  def _make_stub(provider: str) -> ProviderLauncher:
    def _stub(
      root: Path, model: str, sys_path: Path, args: Sequence[str]
    ) -> None:
      calls.append((provider, root, model, sys_path, tuple(args)))

    return _stub

  providers: dict[str, ProviderLauncher] = {
    'codex': _make_stub('codex'),
    'claude': _make_stub('claude'),
    'agy': _make_stub('agy'),
  }

  launch(
    'codex-astra-yolo',
    ('--help',),
    repo=shm_repo,
    which_fn=lambda exe: f'/bin/{exe}',
    providers=providers,
  )
  launch(
    'claude-fable-yolo',
    ('--continue',),
    repo=shm_repo,
    which_fn=lambda exe: f'/bin/{exe}',
    providers=providers,
  )
  launch(
    'agy-carbon-yolo',
    ('--print', 'hi'),
    repo=shm_repo,
    which_fn=lambda exe: f'/bin/{exe}',
    providers=providers,
  )

  prev_cwd = Path.cwd()
  os.chdir(shm_repo.parent)
  try:
    launch(
      'codex-luna-yolo',
      ('--flag',),
      repo=Path(shm_repo.name),
      which_fn=lambda exe: f'/bin/{exe}',
      providers=providers,
    )
  finally:
    os.chdir(prev_cwd)

  resolved_repo = shm_repo.resolve()
  resolved_sys = sys_file.resolve()
  assert calls == [
    ('codex', resolved_repo, 'gpt-6-astra', resolved_sys, ('--help',)),
    ('claude', resolved_repo, 'fable', resolved_sys, ('--continue',)),
    (
      'agy',
      resolved_repo,
      'gemini-4-carbon-medium',
      resolved_sys,
      ('--print', 'hi'),
    ),
    ('codex', resolved_repo, 'gpt-6-luna', resolved_sys, ('--flag',)),
  ]
