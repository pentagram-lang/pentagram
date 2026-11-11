import os
from pathlib import Path

import pytest


def isolate_git_environment(
  monkeypatch: pytest.MonkeyPatch, root: Path
) -> None:
  for name in tuple(os.environ):
    if name.startswith('GIT_'):
      monkeypatch.delenv(name, raising=False)

  global_config = root.parent / f'{root.name}.gitconfig'
  global_config.write_text('', encoding='utf-8')
  monkeypatch.setenv('HOME', str(root.parent / f'{root.name}.home'))
  monkeypatch.setenv(
    'XDG_CONFIG_HOME', str(root.parent / f'{root.name}.xdg')
  )
  monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')
  monkeypatch.setenv('GIT_CONFIG_GLOBAL', str(global_config))
