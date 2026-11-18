from __future__ import annotations

from collections.abc import Sequence
from typing import Never

import pytest

from zero.boot import run_boot


class _ExecCalled(BaseException):
  def __init__(self, file: str, argv: list[str]) -> None:
    self.file = file
    self.argv = argv


def _fake_execvp(file: str, argv: Sequence[str]) -> Never:
  raise _ExecCalled(file, list(argv))


def test_run_boot_forwards_args() -> None:
  with pytest.raises(_ExecCalled) as exc_info:
    run_boot(['--watch', 'core'], execvp=_fake_execvp)
  assert (exc_info.value.file, exc_info.value.argv) == (
    'cargo',
    ['cargo', 'run', '-p', 'boot_shell', '--', '--watch', 'core'],
  )

  with pytest.raises(_ExecCalled) as empty_exc:
    run_boot([], execvp=_fake_execvp)
  assert (empty_exc.value.file, empty_exc.value.argv) == (
    'cargo',
    ['cargo', 'run', '-p', 'boot_shell', '--'],
  )
