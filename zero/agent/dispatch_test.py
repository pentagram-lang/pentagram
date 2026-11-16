from collections.abc import Sequence
from pathlib import Path

import click
import pytest

from zero.agent import dispatch


@pytest.mark.parametrize(
  ('agent_name', 'expected_executable', 'expected_model'),
  [
    ('codex-luna-yolo', 'codex', 'gpt-6-luna'),
    ('codex-sol-yolo', 'codex', 'gpt-6-sol'),
    ('codex-astra-yolo', 'codex', 'gpt-6-astra'),
    ('claude-sonnet-yolo', 'claude', 'sonnet'),
    ('claude-fable-yolo', 'claude', 'fable'),
    ('agy-flash-yolo', 'agy', 'gemini-3.8-flash-high'),
    ('agy-argon-yolo', 'agy', 'gemini-4-argon-medium'),
    ('agy-carbon-yolo', 'agy', 'gemini-4-carbon-medium'),
  ],
)
def test_dispatch_launch_resolves_every_configured_agent(
  monkeypatch: pytest.MonkeyPatch,
  agent_name: str,
  expected_executable: str,
  expected_model: str,
) -> None:
  calls: list[tuple[Path, Path, Sequence[str], str]] = []
  assert dispatch.__file__ is not None
  root = Path(dispatch.__file__).resolve().parents[2]
  system_file = root / 'sys.md'

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'is_file', lambda self: self == system_file)
    mp.setattr(
      dispatch.shutil,
      'which',
      lambda executable: f'/bin/{executable}',
    )
    mp.setitem(
      dispatch._PROVIDERS,
      expected_executable,
      lambda project_root, sys_path, arguments, model: calls.append(
        (project_root, sys_path, arguments, model)
      ),
    )
    dispatch.launch(agent_name, ['--resume', 'session'])

  assert calls == [
    (root, system_file, ['--resume', 'session'], expected_model)
  ]


def test_dispatch_launch_rejects_missing_and_unreadable_targets(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  assert dispatch.__file__ is not None
  system_file = Path(dispatch.__file__).resolve().parents[2] / 'sys.md'

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'is_file', lambda _self: False)
    mp.setattr(
      dispatch.shutil, 'which', lambda executable: f'/bin/{executable}'
    )
    with pytest.raises(click.ClickException) as missing_sys:
      dispatch.launch('codex-astra-yolo', [])
    assert (
      str(missing_sys.value) == f'Missing system prompt: {system_file}'
    )

  def raise_eperm(self: Path) -> bool:
    assert self == system_file
    raise PermissionError(13, 'denied')

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'is_file', raise_eperm)
    with pytest.raises(click.ClickException) as error:
      dispatch.launch('codex-astra-yolo', [])
    assert str(error.value) == (
      f'Cannot read system prompt {system_file}: [Errno 13] denied'
    )

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'is_file', lambda self: self == system_file)
    mp.setattr(dispatch.shutil, 'which', lambda _executable: None)
    with pytest.raises(click.ClickException) as missing_bin:
      dispatch.launch('codex-astra-yolo', [])
    assert str(missing_bin.value) == (
      'Agent executable not found on PATH: codex'
    )

  with monkeypatch.context() as mp:
    mp.setattr(
      Path,
      'is_file',
      lambda self: (_ for _ in ()).throw(
        AssertionError(f'unexpected is_file on {self}')
      ),
    )
    mp.setattr(
      dispatch.shutil,
      'which',
      lambda executable: (_ for _ in ()).throw(
        AssertionError(f'unexpected which({executable})')
      ),
    )
    with pytest.raises(click.ClickException) as unknown:
      dispatch.launch('no-such-agent', [])
    assert str(unknown.value) == 'Unknown agent: no-such-agent'
