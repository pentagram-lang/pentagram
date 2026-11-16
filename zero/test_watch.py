from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from pytest import CaptureFixture, MonkeyPatch

from zero import cli as command_plane
from zero import lib as command_plane_lib
from zero import watch


@dataclass
class ProcessDouble:
  stdout: StringIO
  stderr: StringIO
  exit_code: int

  def wait(self) -> int:
    return self.exit_code


@pytest.mark.parametrize(
  ('files', 'expected'),
  (
    ([], []),
    (['zero/cli.py'], [(['0', 'check', 'ztest'], 'ztest')]),
    (['proj/cli.py'], [(['0', 'check', 'ptest'], 'ptest')]),
    (
      ['zero/watch.py', 'proj/cli.py', 'zero/README.md'],
      [
        (['0', 'check', 'ztest'], 'ztest'),
        (['0', 'check', 'ptest'], 'ptest'),
      ],
    ),
    (['other/module.py'], []),
  ),
  ids=('no-python', 'command-plane', 'project', 'both', 'other-root'),
)
def test_python_changes_select_the_affected_test_runners(
  files: list[str], expected: list[tuple[list[str], str]]
) -> None:
  assert watch._python_test_commands(files) == expected


@pytest.mark.parametrize(
  ('files', 'runner_name'),
  (
    (['zero/cli.py'], '_do_ztest'),
    (['proj/cli.py'], '_do_ptest'),
  ),
  ids=('command-plane', 'project'),
)
def test_watch_commands_resolve_to_the_registered_runners(
  monkeypatch: MonkeyPatch, files: list[str], runner_name: str
) -> None:
  calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
  command, _ = watch._python_test_commands(files)[0]

  def fake_runner(*arguments: object, **kwargs: object) -> int:
    calls.append((arguments, kwargs))
    return 0

  monkeypatch.setattr(command_plane, runner_name, fake_runner)

  result = CliRunner().invoke(command_plane.cli, command[1:])

  assert (result.exit_code, result.output, result.exception) == (
    0,
    '',
    None,
  )
  assert calls == [
    ((command_plane_lib.REPO_ROOT, None, None, (), None), {})
  ]


def test_watch_runs_changed_python_suites_and_propagates_failure(
  monkeypatch: MonkeyPatch,
  tmp_path: Path,
  capsys: CaptureFixture[str],
) -> None:
  monkeypatch.setattr(watch.pywatchman, 'client', lambda **_kwargs: None)
  session = watch.WatchSession(tmp_path)
  commands: Queue[tuple[str, ...]] = Queue()

  def fake_process(
    command: Sequence[str], **_kwargs: object
  ) -> ProcessDouble:
    command_tuple = tuple(command)
    commands.put(command_tuple)
    failed = command_tuple == ('0', 'check', 'ptest')
    return ProcessDouble(
      stdout=StringIO('project tests failed\n' if failed else ''),
      stderr=StringIO('assertion detail\n' if failed else ''),
      exit_code=1 if failed else 0,
    )

  monkeypatch.setattr(watch.subprocess, 'Popen', fake_process)
  session._rebuild_and_restart(
    ['zero/test_main.py', 'proj/test_cli_output.py']
  )
  actual_commands = sorted(commands.get_nowait() for _ in range(4))
  output = capsys.readouterr().out

  assert actual_commands == sorted(
    (
      ('0', 'check', 'ztest'),
      ('0', 'check', 'ptest'),
      ('ruff', 'check'),
      ('ruff', 'format', '--check'),
    )
  )
  assert commands.empty()
  assert '[ptest] project tests failed' in output
  assert '[ptest] assertion detail' in output
  assert f'{watch.RED}FAIL{watch.RESET}] ptest (' in output
  assert f'{watch.RED}FAIL{watch.RESET}] watch-iteration (' in output


@pytest.mark.parametrize(
  ('exit_code', 'status'),
  ((0, 'PASS'), (1, 'FAIL')),
  ids=('formatted', 'format-error'),
)
def test_watch_expands_nix_paths_and_reports_nixfmt_result(
  monkeypatch: MonkeyPatch,
  tmp_path: Path,
  capsys: CaptureFixture[str],
  exit_code: int,
  status: str,
) -> None:
  root_nix = tmp_path / 'flake.nix'
  nested_nix = tmp_path / 'nix' / 'python.nix'
  nix_roots: list[object] = []

  def fake_nix_files(root: object) -> list[str]:
    nix_roots.append(root)
    return [str(root_nix), str(nested_nix)]

  monkeypatch.setattr(watch.lib, 'nix_files', fake_nix_files)
  monkeypatch.setattr(watch.pywatchman, 'client', lambda **_kwargs: None)
  session = watch.WatchSession(tmp_path)
  commands: Queue[tuple[str, ...]] = Queue()

  def fake_process(
    command: Sequence[str], **_kwargs: object
  ) -> ProcessDouble:
    commands.put(tuple(command))
    return ProcessDouble(StringIO(), StringIO(), exit_code)

  monkeypatch.setattr(watch.subprocess, 'Popen', fake_process)
  session._rebuild_and_restart(['flake.nix'])
  output = capsys.readouterr().out

  assert nix_roots == [str(tmp_path)]
  assert commands.get_nowait() == (
    'nixfmt',
    '--check',
    '--',
    str(root_nix),
    str(nested_nix),
  )
  assert commands.empty()
  expected_colour = watch.GREEN if exit_code == 0 else watch.RED
  assert f'{expected_colour}{status}{watch.RESET}] nix-fmt (' in output
  assert (
    f'{expected_colour}{status}{watch.RESET}] watch-iteration (' in output
  )


def test_watch_skips_nixfmt_when_no_nix_files_exist(
  monkeypatch: MonkeyPatch,
  tmp_path: Path,
  capsys: CaptureFixture[str],
) -> None:
  monkeypatch.setattr(watch.lib, 'nix_files', lambda _root: [])
  assert watch._nixfmt_check_command(tmp_path) == []
  monkeypatch.setattr(watch.pywatchman, 'client', lambda **_kwargs: None)
  monkeypatch.setattr(
    watch, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.25)
  )
  session = watch.WatchSession(tmp_path)
  commands: Queue[tuple[str, ...]] = Queue()

  def fake_process(
    command: Sequence[str], **_kwargs: object
  ) -> ProcessDouble:
    commands.put(tuple(command))
    return ProcessDouble(StringIO(), StringIO(), 0)

  monkeypatch.setattr(watch.subprocess, 'Popen', fake_process)
  session._rebuild_and_restart(['flake.nix'])
  output = capsys.readouterr().out

  assert commands.empty()
  assert output == (
    f'[{watch.GREEN}PASS{watch.RESET}] watch-iteration (0.25s)\n'
  )


def test_watch_reports_nix_discovery_error_without_crashing(
  monkeypatch: MonkeyPatch,
  tmp_path: Path,
  capsys: CaptureFixture[str],
) -> None:
  def fail_nix_files(_root: object) -> list[str]:
    raise RuntimeError('Cannot scan Nix files with git: fatal')

  monkeypatch.setattr(watch.lib, 'nix_files', fail_nix_files)
  monkeypatch.setattr(watch.pywatchman, 'client', lambda **_kwargs: None)
  monkeypatch.setattr(
    watch, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.25)
  )
  session = watch.WatchSession(tmp_path)

  session._rebuild_and_restart(['flake.nix'])
  output = capsys.readouterr().out

  assert output == (
    f'{watch.RED}[nix-fmt] Cannot scan Nix files with git: fatal'
    f'{watch.RESET}\n'
    f'[{watch.RED}FAIL{watch.RESET}] nix-fmt (0.25s)\n'
    f'[{watch.RED}FAIL{watch.RESET}] watch-iteration (0.25s)\n'
  )


def test_watch_reports_a_missing_shell_binary_as_a_rust_failure(
  monkeypatch: MonkeyPatch,
  tmp_path: Path,
  capsys: CaptureFixture[str],
) -> None:
  monkeypatch.setattr(watch.pywatchman, 'client', lambda **_kwargs: None)

  def successful_check(
    _self: watch.WatchSession,
    _command: Sequence[str],
    _label: str,
    _colour: str,
  ) -> bool:
    return True

  def successful_build(
    command: Sequence[str], **_kwargs: object
  ) -> ProcessDouble:
    assert tuple(command[:3]) == ('cargo', 'build', '--tests')
    return ProcessDouble(StringIO(), StringIO(), 0)

  monkeypatch.setattr(watch.WatchSession, '_run_cmd', successful_check)
  monkeypatch.setattr(watch.subprocess, 'Popen', successful_build)
  session = watch.WatchSession(tmp_path)

  session._rebuild_and_restart(['src/main.rs'])
  output = capsys.readouterr().out

  assert 'Could not find boot_shell binary' in output
  assert f'{watch.RED}FAIL{watch.RESET}] restart-shell (' in output
  assert f'{watch.RED}FAIL{watch.RESET}] watch-iteration (' in output
