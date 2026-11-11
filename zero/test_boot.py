import subprocess
import sys
from collections.abc import Sequence

import pytest

from zero import boot


def test_run_shell_replaces_the_process_with_the_boot_package(
  monkeypatch: pytest.MonkeyPatch,
  capsys: pytest.CaptureFixture[str],
) -> None:
  calls: list[tuple[str, Sequence[str]]] = []
  monkeypatch.setattr(
    boot.os,
    'execvp',
    lambda executable, arguments: calls.append((executable, arguments)),
  )

  boot.run_shell(['test', 'core', '--verbose'])

  assert calls == [
    (
      'cargo',
      [
        'cargo',
        'run',
        '-p',
        'boot_shell',
        '--',
        'test',
        'core',
        '--verbose',
      ],
    )
  ]
  assert capsys.readouterr().out == (
    'Exec: cargo run -p boot_shell -- test core --verbose\n'
  )


def test_run_shell_flushes_announcement_before_process_replacement() -> (
  None
):
  child_program = r'import os; os.write(1, b"child\n")'
  script = f"""
import os
import sys
from zero import boot

def replace_with_child(_executable, _arguments):
  os.execv(
    sys.executable,
    [sys.executable, '-c', {child_program!r}],
  )

boot.os.execvp = replace_with_child
boot.run_shell(['--version'])
"""
  result = subprocess.run(
    [sys.executable, '-c', script],
    check=True,
    capture_output=True,
    text=True,
  )

  assert result.stdout == (
    'Exec: cargo run -p boot_shell -- --version\nchild\n'
  )
  assert result.stderr == ''
