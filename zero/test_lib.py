from types import SimpleNamespace

import click
import pytest
from pytest import CaptureFixture, MonkeyPatch

from zero import lib


@pytest.mark.parametrize(
  ('arguments', 'max_pos', 'expected'),
  [
    (['project', 'test', 'filter'], 2, (['project', 'test'], ['filter'])),
    (['project', '--', 'test'], 2, (['project'], ['--', 'test'])),
    (['--verbose', 'test'], 2, ([], ['--verbose', 'test'])),
  ],
  ids=('position-limit', 'separator', 'option'),
)
def test_parse_args_preserves_positionals_and_unparsed_arguments(
  arguments: list[str],
  max_pos: int,
  expected: tuple[list[str], list[str]],
) -> None:
  assert lib.parse_args(arguments, max_pos) == expected


def test_cargo_clippy_command_builder_preserves_arguments() -> None:
  assert lib.get_cargo_clippy_cmd('core') == [
    'cargo',
    'clippy',
    '-p',
    'core',
    '--all-targets',
    '--all-features',
    '--',
    '-D',
    'warnings',
  ]


@pytest.mark.parametrize(
  ('package', 'expected'),
  [
    (
      None,
      [
        'cargo',
        'fixit',
        '--allow-dirty',
        '--allow-staged',
        '--all-targets',
        '--all-features',
      ],
    ),
    (
      'core',
      [
        'cargo',
        'fixit',
        '--allow-dirty',
        '--allow-staged',
        '-p',
        'core',
        '--all-targets',
        '--all-features',
      ],
    ),
  ],
  ids=('workspace', 'package'),
)
def test_cargo_fix_command_builder_preserves_arguments(
  package: str | None, expected: list[str]
) -> None:
  assert lib.get_cargo_fix_cmd(package) == expected


def test_cargo_test_command_builder_preserves_arguments() -> None:
  assert lib.get_cargo_test_cmd(
    package='core',
    test_name='lexer::rejects_invalid_text',
    extras=['--exact'],
    nocapture=True,
  ) == [
    'cargo',
    'test',
    '-p',
    'core',
    'lexer::rejects_invalid_text',
    '--exact',
    '--',
    '--nocapture',
  ]


def test_timer_uses_monotonic_elapsed_time(
  monkeypatch: MonkeyPatch,
) -> None:
  timer = lib.Timer(started_at=10.0)
  with monkeypatch.context() as patch:
    patch.setattr(lib.time, 'monotonic', lambda: 12.25)
    duration = timer.duration()

  assert duration == 2.25


def test_run_command_reports_success_with_its_duration(
  monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []
  monkeypatch.setattr(lib.os, 'system', lambda _command: 0)
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.25)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  lib.run_cmd('pytest', 'python-test')

  assert capsys.readouterr().out == 'Running: pytest\n'
  assert reports == [
    (('python-test', 0.25), {'success': True, 'informational': False})
  ]


def test_run_command_propagates_child_failure(
  monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []
  monkeypatch.setattr(lib.os, 'system', lambda _command: 9 << 8)
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.5)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  with pytest.raises(SystemExit) as error:
    lib.run_cmd('pytest', 'python-test')

  assert error.value.code == 9
  assert capsys.readouterr().out == 'Running: pytest\n'
  assert reports == [(('python-test', 0.5), {'success': False})]


def test_run_command_reports_system_failure_as_exit_code_one(
  monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []
  monkeypatch.setattr(lib.os, 'system', lambda _command: -1)
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.5)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  with pytest.raises(SystemExit) as error:
    lib.run_cmd('pytest', 'python-test')

  assert error.value.code == 1
  assert capsys.readouterr().out == 'Running: pytest\n'
  assert reports == [(('python-test', 0.5), {'success': False})]


def test_run_command_maps_signal_termination_to_shell_exit_status(
  monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []
  monkeypatch.setattr(lib.os, 'system', lambda _command: 15)
  monkeypatch.setattr(
    lib.os, 'waitstatus_to_exitcode', lambda _status: -15
  )
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.5)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  with pytest.raises(SystemExit) as error:
    lib.run_cmd('pytest', 'python-test')

  assert error.value.code == 143
  assert capsys.readouterr().out == 'Running: pytest\n'
  assert reports == [(('python-test', 0.5), {'success': False})]


def test_aliased_group_resolves_a_command_alias() -> None:
  @click.command('canonical')
  def canonical_command() -> None:
    return None

  vars(canonical_command)['aliases'] = ['shortcut']
  group = lib.AliasedGroup(commands={'canonical': canonical_command})
  context = click.Context(group)

  assert group.get_command(context, 'shortcut') is canonical_command
