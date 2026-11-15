import importlib.util
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TypedDict

import click
import pytest
from click.testing import CliRunner
from pytest import MonkeyPatch

from zero import cli, lib

_CLI_NODEID = (
  'cli_test.py::test_standalone_check_cmd_subcommands_propagate_exit_codes'
)
_PROJ_NODEID = (
  'test_lifecycle.py::'
  'test_stage_dependencies_gate_activation_and_reject_cycles'
)
_RUNNER = CliRunner()


class PythonTestOptions(TypedDict, total=False):
  keyword_expression: str
  marker_expression: str
  nodeids: tuple[str, ...]
  parallel: bool


@dataclass(frozen=True)
class RunCmdCall:
  command: list[str]
  label: str | None = None
  cwd: Path | None = None


@dataclass(frozen=True)
class StatusCall:
  label: str
  duration: float
  success: bool = True


def _stub_timer(monkeypatch: MonkeyPatch, duration: float = 0.5) -> None:
  monkeypatch.setattr(
    cli.lib, 'Timer', lambda: SimpleNamespace(duration=lambda: duration)
  )


def _stub_virtual_fs(
  monkeypatch: MonkeyPatch,
  *,
  files: frozenset[Path],
  dirs: frozenset[Path] = frozenset(),
  symlinks: dict[Path, Path] | None = None,
) -> None:
  resolved_map = symlinks or {}

  def fake_resolve(self: Path, strict: bool = False) -> Path:
    target = resolved_map.get(self, self)
    if strict and (
      files.isdisjoint((target,)) and dirs.isdisjoint((target,))
    ):
      raise FileNotFoundError(target)
    return target

  monkeypatch.setattr(cli.Path, 'resolve', fake_resolve)
  monkeypatch.setattr(
    cli.Path, 'is_file', lambda self: not files.isdisjoint((self,))
  )


def _record_run_cmd(monkeypatch: MonkeyPatch) -> list[RunCmdCall]:
  calls: list[RunCmdCall] = []

  def fake_run_cmd(
    command: list[str] | tuple[str, ...],
    label: str | None = None,
    *,
    cwd: Path | None = None,
  ) -> None:
    calls.append(RunCmdCall(list(command), label, cwd))

  monkeypatch.setattr(cli.lib, 'run_cmd', fake_run_cmd)
  return calls


def _record_check_cmd(
  monkeypatch: MonkeyPatch,
  failures: dict[str, int] | None = None,
  default_exit: int = 0,
) -> list[RunCmdCall]:
  calls: list[RunCmdCall] = []

  def fake_check_cmd(
    command: list[str] | tuple[str, ...],
    label: str | None = None,
    *,
    cwd: Path | None = None,
  ) -> int:
    calls.append(RunCmdCall(list(command), label, cwd))
    return (failures or {}).get(label or '', default_exit)

  monkeypatch.setattr(cli.lib, 'check_cmd', fake_check_cmd)
  return calls


def _record_statuses(monkeypatch: MonkeyPatch) -> list[StatusCall]:
  statuses: list[StatusCall] = []
  monkeypatch.setattr(
    cli.lib,
    'status',
    lambda label, duration, success=True: statuses.append(
      StatusCall(label, duration, success)
    ),
  )
  return statuses


def _stub_nodeid_fs(monkeypatch: MonkeyPatch) -> Path:
  fake_root = Path('/repo')
  _stub_virtual_fs(
    monkeypatch,
    files=frozenset(
      {
        Path('/repo/zero/cli_test.py'),
        Path('/repo/proj/test_lifecycle.py'),
        Path('/outside/escape.py'),
      }
    ),
    dirs=frozenset(
      {
        Path('/repo'),
        Path('/repo/zero'),
        Path('/repo/proj'),
        Path('/repo/zero/dir.py'),
      }
    ),
    symlinks={Path('/repo/zero/escape.py'): Path('/outside/escape.py')},
  )
  return fake_root


def test_importing_cli_and_entrypoint_does_not_chdir(
  monkeypatch: MonkeyPatch,
) -> None:
  chdir_calls: list[object] = []
  cli_spec = importlib.util.find_spec('zero.cli')
  main_spec = importlib.util.find_spec('zero.__main__')
  assert cli_spec is not None and cli_spec.loader is not None
  assert main_spec is not None and main_spec.loader is not None

  with monkeypatch.context() as patch:
    patch.setattr(cli.os, 'chdir', lambda path: chdir_calls.append(path))
    fresh_cli = importlib.util.module_from_spec(cli_spec)
    cli_spec.loader.exec_module(fresh_cli)
    patch.setitem(sys.modules, 'zero.cli', fresh_cli)
    patch.setattr(sys.modules['zero'], 'cli', fresh_cli)
    fresh_main = importlib.util.module_from_spec(main_spec)
    main_spec.loader.exec_module(fresh_main)

  assert fresh_main.cli is fresh_cli
  assert chdir_calls == []


def test_resolve_repo_root_finds_ancestor_and_fails_outside_checkout(
  monkeypatch: MonkeyPatch,
) -> None:
  _stub_virtual_fs(
    monkeypatch,
    files=frozenset({Path('/worktree/checkout/zero/__main__.py')}),
    symlinks={
      Path('/symlink/agent'): Path('/worktree/checkout/zero/agent')
    },
  )

  assert cli.resolve_repo_root(
    Path('/worktree/checkout/zero/agent')
  ) == Path('/worktree/checkout')
  assert cli.resolve_repo_root(Path('/symlink/agent')) == Path(
    '/worktree/checkout'
  )

  monkeypatch.setattr(
    cli.Path,
    'cwd',
    lambda: Path('/worktree/checkout/zero/agent'),
  )
  assert cli.resolve_repo_root() == Path('/worktree/checkout')

  with pytest.raises(click.ClickException) as outside_error:
    cli.resolve_repo_root(Path('/outside/worktree'))
  assert outside_error.value.message == (
    'zero/__main__.py not found in parent directories.'
  )

  def missing_cwd() -> Path:
    raise FileNotFoundError(2, 'No such file or directory')

  monkeypatch.setattr(cli.Path, 'cwd', missing_cwd)
  with pytest.raises(click.ClickException) as unlinked_error:
    cli.resolve_repo_root()
  assert unlinked_error.value.message == (
    'zero/__main__.py not found in parent directories.'
  )


@pytest.mark.parametrize(
  ('argv', 'cli_error', 'expected_exit'),
  [
    (['check', '--skip-commit'], None, 0),
    (None, SystemExit(3), 3),
  ],
  ids=('normal-return', 'restores-on-exit'),
)
def test_main_passes_repo_root_and_restores_cwd(
  monkeypatch: MonkeyPatch,
  argv: list[str] | None,
  cli_error: SystemExit | None,
  expected_exit: int,
) -> None:
  events: list[tuple[object, ...]] = []
  previous_cwd = Path('/caller/dir')
  expected_root = Path('/worktree/checkout')
  monkeypatch.setattr(cli, 'resolve_repo_root', lambda: expected_root)
  monkeypatch.setattr(cli.Path, 'cwd', lambda: previous_cwd)
  monkeypatch.setattr(
    cli.os, 'chdir', lambda path: events.append(('chdir', path))
  )

  def fake_cli(
    *, args: list[str] | None, prog_name: str, obj: Path
  ) -> None:
    events.append(('cli', args, prog_name, obj))
    if cli_error is not None:
      raise cli_error

  monkeypatch.setattr(cli, 'cli', fake_cli)

  if cli_error is None:
    cli.main(argv)
  else:
    with pytest.raises(SystemExit) as error:
      cli.main(argv)
    assert error.value.code == expected_exit

  assert events == [
    ('chdir', expected_root),
    ('cli', argv, '0', expected_root),
    ('chdir', previous_cwd),
  ]


def test_main_tolerates_unlinked_cwd_and_missing_repo_root(
  monkeypatch: MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
  events: list[tuple[object, ...]] = []
  expected_root = Path('/worktree/checkout')

  def missing_cwd() -> Path:
    raise FileNotFoundError(2, 'No such file or directory')

  monkeypatch.setattr(cli, 'resolve_repo_root', lambda: expected_root)
  monkeypatch.setattr(cli.Path, 'cwd', missing_cwd)
  monkeypatch.setattr(
    cli.os, 'chdir', lambda path: events.append(('chdir', path))
  )
  monkeypatch.setattr(
    cli,
    'cli',
    lambda *, args, prog_name, obj: events.append(
      ('cli', args, prog_name, obj)
    ),
  )

  cli.main(['check'])
  assert events == [
    ('chdir', expected_root),
    ('cli', ['check'], '0', expected_root),
  ]

  def fail_resolve() -> Path:
    raise click.ClickException(
      'zero/__main__.py not found in parent directories.'
    )

  monkeypatch.setattr(cli, 'resolve_repo_root', fail_resolve)
  with pytest.raises(SystemExit) as error:
    cli.main(['check'])

  assert error.value.code == 1
  assert capsys.readouterr().err == (
    'Error: zero/__main__.py not found in parent directories.\n'
  )


@pytest.mark.parametrize(
  ('argv', 'expected_output'),
  [
    (
      ['-w', 'check'],
      'Usage: cli [OPTIONS] COMMAND [ARGS]...\n'
      "Try 'cli --help' for help.\n\n"
      'Error: --watch cannot be combined with a subcommand.\n',
    ),
    (
      ['--watch', 'fix'],
      'Usage: cli [OPTIONS] COMMAND [ARGS]...\n'
      "Try 'cli --help' for help.\n\n"
      'Error: --watch cannot be combined with a subcommand.\n',
    ),
    (
      ['--watch', 'fmt'],
      'Usage: cli [OPTIONS] COMMAND [ARGS]...\n'
      "Try 'cli --help' for help.\n\n"
      "Error: No such command 'fmt'.\n",
    ),
    (
      ['check', '--skip-commit', 'lint'],
      'Usage: cli check [OPTIONS] COMMAND [ARGS]...\n'
      "Try 'cli check --help' for help.\n\n"
      'Error: --skip-commit cannot be combined with a subcommand.\n',
    ),
    (
      ['c', '-s', 'fmt'],
      'Usage: cli c [OPTIONS] COMMAND [ARGS]...\n'
      "Try 'cli c --help' for help.\n\n"
      'Error: --skip-commit cannot be combined with a subcommand.\n',
    ),
  ],
  ids=(
    'watch-short',
    'watch-long',
    'watch-unknown',
    'skip-commit-long',
    'skip-commit-short',
  ),
)
def test_conflicting_group_options_fail_with_usage_error(
  argv: list[str], expected_output: str
) -> None:
  result = _RUNNER.invoke(cli.cli, argv)

  assert (result.exit_code, result.output) == (2, expected_output)


@pytest.mark.parametrize(
  'argv',
  (['-w'], ['--watch'], ['watch'], ['w']),
  ids=('short-flag', 'long-flag', 'command', 'alias'),
)
def test_watch_invocations_call_run_watch(
  monkeypatch: MonkeyPatch, argv: list[str]
) -> None:
  calls: list[Path] = []
  monkeypatch.setattr(
    cli.watch, 'run_watch', lambda root: calls.append(root)
  )

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls) == (
    0,
    '',
    [Path('/repo')],
  )


@pytest.mark.parametrize(
  ('command', 'expected_summary'),
  [
    ('fix', 'Run Cargo, Ruff, dprint, and nixfmt formatters.'),
    ('check', 'Run Cargo, Ruff, dprint, and nixfmt format checks.'),
  ],
  ids=('fix', 'check'),
)
def test_formatter_help_names_each_repository_formatter(
  command: str, expected_summary: str
) -> None:
  result = _RUNNER.invoke(cli.cli, [command, 'fmt', '--help'])

  assert (result.exit_code, result.output) == (
    0,
    f'Usage: cli {command} fmt [OPTIONS]\n\n'
    f'  {expected_summary}\n\n'
    'Options:\n'
    '  --help  Show this message and exit.\n',
  )


@pytest.mark.parametrize(
  ('argv', 'nix_paths', 'expected_calls', 'expected_statuses'),
  [
    (
      ['fix', 'fmt'],
      ['/repo/flake.nix', '/repo/nix/zero.nix'],
      [
        RunCmdCall(['cargo', 'fmt'], 'rust-fmt', Path('/repo')),
        RunCmdCall(['ruff', 'format'], 'py-fmt', Path('/repo')),
        RunCmdCall(['dprint', 'fmt'], 'dprint', Path('/repo')),
        RunCmdCall(
          ['nixfmt', '--', 'flake.nix', 'nix/zero.nix'],
          'nix-fmt',
          Path('/repo'),
        ),
      ],
      [StatusCall('fix-fmt', 0.5)],
    ),
    (
      ['f', 'f'],
      [],
      [
        RunCmdCall(['cargo', 'fmt'], 'rust-fmt', Path('/repo')),
        RunCmdCall(['ruff', 'format'], 'py-fmt', Path('/repo')),
        RunCmdCall(['dprint', 'fmt'], 'dprint', Path('/repo')),
      ],
      [StatusCall('fix-fmt', 0.5)],
    ),
    (
      ['fix'],
      ['/repo/flake.nix'],
      [
        RunCmdCall(['cargo', 'fmt'], 'rust-fmt', Path('/repo')),
        RunCmdCall(['ruff', 'format'], 'py-fmt', Path('/repo')),
        RunCmdCall(['dprint', 'fmt'], 'dprint', Path('/repo')),
        RunCmdCall(
          ['nixfmt', '--', 'flake.nix'], 'nix-fmt', Path('/repo')
        ),
        RunCmdCall(['ruff', 'check', '--fix'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'fixit',
            '--allow-dirty',
            '--allow-staged',
            '--all-targets',
            '--all-features',
          ],
          'rust-fixit',
          Path('/repo'),
        ),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
      [
        StatusCall('fix-fmt', 0.5),
        StatusCall('fix-lint', 0.5),
        StatusCall('fix', 0.5),
      ],
    ),
  ],
  ids=('fix-fmt', 'fix-fmt-no-nix', 'fix-all'),
)
def test_fix_commands_dispatch_direct_argv_and_expanded_nix_files(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  nix_paths: list[str],
  expected_calls: list[RunCmdCall],
  expected_statuses: list[StatusCall],
) -> None:
  calls = _record_run_cmd(monkeypatch)
  statuses = _record_statuses(monkeypatch)
  monkeypatch.setattr(cli.lib, 'nix_files', lambda _root: nix_paths)
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls, statuses) == (
    0,
    '',
    expected_calls,
    expected_statuses,
  )


@pytest.mark.parametrize(
  ('argv', 'expected_calls'),
  [
    (
      ['fix', 'lint'],
      [
        RunCmdCall(['ruff', 'check', '--fix'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'fixit',
            '--allow-dirty',
            '--allow-staged',
            '--all-targets',
            '--all-features',
          ],
          'rust-fixit',
          Path('/repo'),
        ),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
    ),
    (
      ['fix', 'lint', 'boot_lex'],
      [
        RunCmdCall(['ruff', 'check', '--fix'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'fixit',
            '--allow-dirty',
            '--allow-staged',
            '-p',
            'boot_lex',
            '--all-targets',
            '--all-features',
          ],
          'rust-fixit',
          Path('/repo'),
        ),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '-p',
            'boot_lex',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
    ),
    (
      ['f', 'l', 'boot_lex'],
      [
        RunCmdCall(['ruff', 'check', '--fix'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'fixit',
            '--allow-dirty',
            '--allow-staged',
            '-p',
            'boot_lex',
            '--all-targets',
            '--all-features',
          ],
          'rust-fixit',
          Path('/repo'),
        ),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '-p',
            'boot_lex',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
    ),
  ],
  ids=('workspace', 'package', 'aliases'),
)
def test_fix_lint_cli_dispatches_python_and_rust_tools(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  expected_calls: list[RunCmdCall],
) -> None:
  calls = _record_run_cmd(monkeypatch)
  statuses = _record_statuses(monkeypatch)
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls, statuses) == (
    0,
    '',
    expected_calls,
    [StatusCall('fix-lint', 0.5)],
  )


def test_fix_lint_rejects_unknown_options() -> None:
  result = _RUNNER.invoke(cli.cli, ['fix', 'lint', '--bogus'])

  assert (result.exit_code, result.output) == (
    2,
    'Usage: cli fix lint [OPTIONS] [PACKAGE]\n'
    "Try 'cli fix lint --help' for help.\n\n"
    'Error: No such option: --bogus\n',
  )


@pytest.mark.parametrize(
  ('argv', 'nix_paths', 'failures', 'expected_exit', 'expected_calls'),
  [
    (
      ['check', 'fmt'],
      ['/repo/flake.nix', '/repo/nix/zero.nix'],
      {},
      0,
      [
        RunCmdCall(
          ['cargo', 'fmt', '--', '--check'], 'rust-fmt', Path('/repo')
        ),
        RunCmdCall(['ruff', 'format', '--check'], 'py-fmt', Path('/repo')),
        RunCmdCall(['dprint', 'check'], 'dprint', Path('/repo')),
        RunCmdCall(
          ['nixfmt', '--check', '--', 'flake.nix', 'nix/zero.nix'],
          'nix-fmt',
          Path('/repo'),
        ),
      ],
    ),
    (
      ['c', 'f'],
      [],
      {},
      0,
      [
        RunCmdCall(
          ['cargo', 'fmt', '--', '--check'], 'rust-fmt', Path('/repo')
        ),
        RunCmdCall(['ruff', 'format', '--check'], 'py-fmt', Path('/repo')),
        RunCmdCall(['dprint', 'check'], 'dprint', Path('/repo')),
      ],
    ),
    (
      ['check', 'fmt'],
      ['/repo/flake.nix'],
      {'rust-fmt': 3, 'dprint': 2},
      3,
      [
        RunCmdCall(
          ['cargo', 'fmt', '--', '--check'], 'rust-fmt', Path('/repo')
        ),
        RunCmdCall(['ruff', 'format', '--check'], 'py-fmt', Path('/repo')),
        RunCmdCall(['dprint', 'check'], 'dprint', Path('/repo')),
        RunCmdCall(
          ['nixfmt', '--check', '--', 'flake.nix'],
          'nix-fmt',
          Path('/repo'),
        ),
      ],
    ),
  ],
  ids=('all-pass', 'aliases-no-nix', 'non-short-circuiting-failure'),
)
def test_check_fmt_runs_all_formatters_without_short_circuiting(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  nix_paths: list[str],
  failures: dict[str, int],
  expected_exit: int,
  expected_calls: list[RunCmdCall],
) -> None:
  calls = _record_check_cmd(monkeypatch, failures)
  statuses = _record_statuses(monkeypatch)
  monkeypatch.setattr(cli.lib, 'nix_files', lambda _root: nix_paths)
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls, statuses) == (
    expected_exit,
    '',
    expected_calls,
    [StatusCall('check-fmt', 0.5, expected_exit == 0)],
  )


def test_fmt_commands_report_nix_discovery_errors_without_crashing(
  monkeypatch: MonkeyPatch,
) -> None:
  def fail_nix_files(_root: Path) -> list[str]:
    raise RuntimeError('Cannot scan Nix files with git: fatal')

  monkeypatch.setattr(cli.lib, 'nix_files', fail_nix_files)
  _stub_timer(monkeypatch)

  check_calls = _record_check_cmd(monkeypatch)
  check_statuses = _record_statuses(monkeypatch)
  check_result = _RUNNER.invoke(
    cli.cli, ['check', 'fmt'], obj=Path('/repo')
  )

  assert (
    check_result.exit_code,
    check_result.output,
    check_calls,
    check_statuses,
  ) == (
    1,
    'Error: Cannot scan Nix files with git: fatal\n',
    [
      RunCmdCall(
        ['cargo', 'fmt', '--', '--check'], 'rust-fmt', Path('/repo')
      ),
      RunCmdCall(['ruff', 'format', '--check'], 'py-fmt', Path('/repo')),
      RunCmdCall(['dprint', 'check'], 'dprint', Path('/repo')),
    ],
    [
      StatusCall('nix-fmt', 0.5, False),
      StatusCall('check-fmt', 0.5, False),
    ],
  )

  fix_calls = _record_run_cmd(monkeypatch)
  fix_statuses = _record_statuses(monkeypatch)
  fix_result = _RUNNER.invoke(cli.cli, ['fix', 'fmt'], obj=Path('/repo'))

  assert (
    fix_result.exit_code,
    fix_result.output,
    fix_calls,
    fix_statuses,
  ) == (
    1,
    'Error: Cannot scan Nix files with git: fatal\n',
    [
      RunCmdCall(['cargo', 'fmt'], 'rust-fmt', Path('/repo')),
      RunCmdCall(['ruff', 'format'], 'py-fmt', Path('/repo')),
      RunCmdCall(['dprint', 'fmt'], 'dprint', Path('/repo')),
    ],
    [StatusCall('nix-fmt', 0.5, False)],
  )


def test_check_fmt_preserves_surrogate_paths_through_check_cmd(
  monkeypatch: MonkeyPatch,
) -> None:
  bad_rel = os.fsdecode(b'bad-\xff.nix')
  calls: list[tuple[tuple[str, ...], Path | None, bool]] = []

  def fake_run(
    argv: list[str] | tuple[str, ...], *, cwd: Path | None, check: bool
  ) -> SimpleNamespace:
    calls.append((tuple(argv), cwd, check))
    return SimpleNamespace(returncode=0)

  monkeypatch.setattr(
    cli.lib, 'nix_files', lambda root: [str(Path(root) / bad_rel)]
  )
  monkeypatch.setattr(cli.lib.subprocess, 'run', fake_run)
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(
    cli.cli, ['check', 'fmt'], obj=Path('/repo'), color=False
  )

  assert (result.exit_code, result.exception, calls, result.output) == (
    0,
    None,
    [
      (('cargo', 'fmt', '--', '--check'), Path('/repo'), False),
      (('ruff', 'format', '--check'), Path('/repo'), False),
      (('dprint', 'check'), Path('/repo'), False),
      (('nixfmt', '--check', '--', bad_rel), Path('/repo'), False),
    ],
    'Running: cargo fmt -- --check\n'
    '[PASS] rust-fmt (0.50s)\n'
    'Running: ruff format --check\n'
    '[PASS] py-fmt (0.50s)\n'
    'Running: dprint check\n'
    '[PASS] dprint (0.50s)\n'
    "Running: nixfmt --check -- 'bad-\\udcff.nix'\n"
    '[PASS] nix-fmt (0.50s)\n'
    '[PASS] check-fmt (0.50s)\n',
  )


@pytest.mark.parametrize(
  ('argv', 'failures', 'expected_exit', 'expected_calls'),
  [
    (
      ['check', 'lint'],
      {},
      0,
      [
        RunCmdCall(['ruff', 'check'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
    ),
    (
      ['c', 'l', 'boot_lex'],
      {},
      0,
      [
        RunCmdCall(['ruff', 'check'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '-p',
            'boot_lex',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
    ),
    (
      ['check', 'lint'],
      {'py-lint': 4},
      4,
      [
        RunCmdCall(['ruff', 'check'], 'py-lint', Path('/repo')),
        RunCmdCall(
          [
            'cargo',
            'clippy',
            '--all-targets',
            '--all-features',
            '--',
            '-D',
            'warnings',
          ],
          'clippy',
          Path('/repo'),
        ),
      ],
    ),
  ],
  ids=('workspace', 'aliases-package', 'non-short-circuiting-failure'),
)
def test_check_lint_runs_all_linters_without_short_circuiting(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  failures: dict[str, int],
  expected_exit: int,
  expected_calls: list[RunCmdCall],
) -> None:
  calls = _record_check_cmd(monkeypatch, failures)
  statuses = _record_statuses(monkeypatch)
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls, statuses) == (
    expected_exit,
    '',
    expected_calls,
    [StatusCall('check-lint', 0.5, expected_exit == 0)],
  )


def test_check_lint_rejects_unknown_options() -> None:
  result = _RUNNER.invoke(cli.cli, ['check', 'lint', '--bogus'])

  assert (result.exit_code, result.output) == (
    2,
    'Usage: cli check lint [OPTIONS] [PACKAGE]\n'
    "Try 'cli check lint --help' for help.\n\n"
    'Error: No such option: --bogus\n',
  )


@pytest.mark.parametrize(
  ('argv', 'expected'),
  [
    (
      ['check', '--skip-commit'],
      [
        ('format', Path('/repo')),
        ('lint', Path('/repo')),
        ('type', Path('/repo')),
        ('policy', Path('/repo')),
        ('docs', Path('/repo')),
        ('ztest', Path('/repo')),
        ('ptest', Path('/repo')),
        ('btest', Path('/repo')),
        ('language-test', Path('/repo')),
      ],
    ),
    (
      ['c', '-s'],
      [
        ('format', Path('/repo')),
        ('lint', Path('/repo')),
        ('type', Path('/repo')),
        ('policy', Path('/repo')),
        ('docs', Path('/repo')),
        ('ztest', Path('/repo')),
        ('ptest', Path('/repo')),
        ('btest', Path('/repo')),
        ('language-test', Path('/repo')),
      ],
    ),
    (
      ['check'],
      [
        ('format', Path('/repo')),
        ('lint', Path('/repo')),
        ('type', Path('/repo')),
        ('policy', Path('/repo')),
        ('docs', Path('/repo')),
        ('ztest', Path('/repo')),
        ('ptest', Path('/repo')),
        ('btest', Path('/repo')),
        ('language-test', Path('/repo')),
        ('commit', Path('/repo')),
        ('history', Path('/repo')),
      ],
    ),
  ],
  ids=('skip-commit', 'short-aliases', 'full-check'),
)
def test_check_runs_each_step_once_and_skips_only_commit_validation(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  expected: list[tuple[str, Path]],
) -> None:
  calls: list[tuple[str, Path]] = []
  steps = (
    ('do_check_fmt', 'format'),
    ('do_check_lint', 'lint'),
    ('do_check_type', 'type'),
    ('do_check_repo_policy', 'policy'),
    ('do_check_doc_lint', 'docs'),
    ('do_ztest', 'ztest'),
    ('do_ptest', 'ptest'),
    ('do_btest', 'btest'),
    ('do_test', 'language-test'),
    ('do_check_commit_message', 'commit'),
    ('do_check_history', 'history'),
  )
  for name, label in steps:

    def make_step(step_label: str = label) -> Callable[..., int]:
      def step(*args: Path, repo_root: Path = lib.REPO_ROOT) -> int:
        calls.append((step_label, args[0] if args else repo_root))
        return 0

      return step

    monkeypatch.setattr(cli, name, make_step())
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls) == (
    0,
    '[PASS] check (0.50s)\n',
    expected,
  )


def test_check_runs_all_steps_without_short_circuiting_on_failure(
  monkeypatch: MonkeyPatch,
) -> None:
  calls: list[str] = []

  def make_step(
    label: str, code: int = 0, message: str | None = None
  ) -> Callable[..., int]:
    def step(*_args: object, **_kwargs: object) -> int:
      calls.append(label)
      if message is not None:
        click.echo(f'Error: {message}', err=True)
      return code

    return step

  steps = (
    ('do_check_fmt', 'format', 3, None),
    ('do_check_lint', 'lint', 0, None),
    ('do_check_type', 'type', 0, None),
    ('do_check_repo_policy', 'policy', 1, 'policy error'),
    ('do_check_doc_lint', 'docs', 0, None),
    ('do_ztest', 'ztest', 0, None),
    ('do_ptest', 'ptest', 0, None),
    ('do_btest', 'btest', 0, None),
    ('do_test', 'language-test', 0, None),
    ('do_check_commit_message', 'commit', 1, 'commit error'),
    ('do_check_history', 'history', 0, None),
  )
  for name, label, code, message in steps:
    monkeypatch.setattr(cli, name, make_step(label, code, message))
  _stub_timer(monkeypatch)

  result = _RUNNER.invoke(cli.cli, ['check'], obj=Path('/repo'))

  assert (result.exit_code, calls, result.output) == (
    3,
    [
      'format',
      'lint',
      'type',
      'policy',
      'docs',
      'ztest',
      'ptest',
      'btest',
      'language-test',
      'commit',
      'history',
    ],
    'Error: policy error\nError: commit error\n[FAIL] check (0.50s)\n',
  )


@pytest.mark.parametrize(
  ('argv', 'module', 'fn_name', 'label', 'failure'),
  [
    (
      ['check', 'policy'],
      cli.repo_policy,
      'check_repository_policy',
      'repo-policy',
      cli.repo_policy.RepositoryPolicyError('banned file'),
    ),
    (
      ['c', 'p'],
      cli.repo_policy,
      'check_repository_policy',
      'repo-policy',
      cli.repo_policy.RepositoryPolicyError('banned file'),
    ),
    (
      ['check', 'doc'],
      cli.doc_lint,
      'check_documentation',
      'doc-lint',
      cli.doc_lint.DocumentationLintError([]),
    ),
    (
      ['c', 'd'],
      cli.doc_lint,
      'check_documentation',
      'doc-lint',
      cli.doc_lint.DocumentationLintError([]),
    ),
    (
      ['check', 'commit'],
      cli.commit_message,
      'check_commit_message',
      'commit-message',
      cli.commit_message.CommitMessageLintError([]),
    ),
    (
      ['c', 'm'],
      cli.commit_message,
      'check_commit_message',
      'commit-message',
      cli.commit_message.CommitMessageLintError([]),
    ),
  ],
  ids=(
    'policy',
    'policy-alias',
    'doc',
    'doc-alias',
    'commit',
    'commit-alias',
  ),
)
def test_standalone_validators_report_timed_status_on_pass_and_fail(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  module: ModuleType,
  fn_name: str,
  label: str,
  failure: Exception,
) -> None:
  calls: list[str] = []
  _stub_timer(monkeypatch, duration=0.75)

  monkeypatch.setattr(module, fn_name, lambda root: calls.append(root))
  pass_result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo/root'))
  assert (pass_result.exit_code, pass_result.output) == (
    0,
    f'[PASS] {label} (0.75s)\n',
  )

  def fail_check(root: str) -> None:
    calls.append(root)
    raise failure

  monkeypatch.setattr(module, fn_name, fail_check)
  fail_result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo/root'))
  assert (fail_result.exit_code, fail_result.output) == (
    1,
    f'Error: {failure}\n[FAIL] {label} (0.75s)\n',
  )
  assert calls == ['/repo/root', '/repo/root']


@pytest.mark.parametrize(
  ('argv', 'expected_call'),
  [
    (
      ['check', 'type'],
      RunCmdCall(
        ['ty', 'check', '--python', sys.prefix], 'type', Path('/repo')
      ),
    ),
    (
      ['check', 'history'],
      RunCmdCall(['cog', 'check'], 'history', Path('/repo')),
    ),
    (['c', 'h'], RunCmdCall(['cog', 'check'], 'history', Path('/repo'))),
    (
      ['check', 'test'],
      RunCmdCall(
        ['cargo', 'run', '-p', 'boot_shell', '--', 'test', 'core'],
        'test',
        Path('/repo'),
      ),
    ),
    (
      ['c', 't'],
      RunCmdCall(
        ['cargo', 'run', '-p', 'boot_shell', '--', 'test', 'core'],
        'test',
        Path('/repo'),
      ),
    ),
    (
      ['check', 'btest'],
      RunCmdCall(['cargo', 'test'], 'btest', Path('/repo')),
    ),
    (
      ['c', 'bt'],
      RunCmdCall(['cargo', 'test'], 'btest', Path('/repo')),
    ),
    (
      ['check', 'ztest'],
      RunCmdCall(
        [
          sys.executable,
          '-m',
          'pytest',
          '-o',
          'testpaths=zero',
          '-n',
          'auto',
        ],
        'command-plane-test',
        Path('/repo'),
      ),
    ),
    (
      ['check', 'ptest'],
      RunCmdCall(
        [
          sys.executable,
          '-m',
          'pytest',
          '-o',
          'testpaths=proj',
          '-n',
          'auto',
        ],
        'project-test',
        Path('/repo'),
      ),
    ),
  ],
  ids=(
    'type',
    'history',
    'history-alias',
    'test',
    'test-alias',
    'btest',
    'btest-alias',
    'ztest',
    'ptest',
  ),
)
@pytest.mark.parametrize('exit_code', [0, 5], ids=('pass', 'fail'))
def test_standalone_check_cmd_subcommands_propagate_exit_codes(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  expected_call: RunCmdCall,
  exit_code: int,
) -> None:
  calls = _record_check_cmd(monkeypatch, default_exit=exit_code)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls) == (
    exit_code,
    '',
    [expected_call],
  )


@pytest.mark.parametrize(
  'argv', (['check', 'changelog'], ['c', 'ch']), ids=('full', 'alias')
)
def test_changelog_command_runs_git_cliff(
  monkeypatch: MonkeyPatch, argv: list[str]
) -> None:
  calls = _record_run_cmd(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls) == (
    0,
    '',
    [RunCmdCall(['git', 'cliff'], 'changelog', Path('/repo'))],
  )


@pytest.mark.parametrize(
  ('argv', 'expected_command'),
  [
    (['check', 'btest'], ['cargo', 'test']),
    (
      ['c', 'bt', '-n', '--exact', 'boot_lex', 'lexer::rejects'],
      [
        'cargo',
        'test',
        '-p',
        'boot_lex',
        'lexer::rejects',
        '--',
        '--exact',
        '--nocapture',
      ],
    ),
  ],
  ids=('default', 'options-and-positionals'),
)
def test_btest_forwards_typed_options_and_positionals(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  expected_command: list[str],
) -> None:
  calls = _record_check_cmd(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=Path('/repo'))

  assert (result.exit_code, result.output, calls) == (
    0,
    '',
    [RunCmdCall(expected_command, 'btest', Path('/repo'))],
  )


def test_btest_rejects_unknown_options() -> None:
  result = _RUNNER.invoke(cli.cli, ['check', 'btest', '--bogus'])

  assert (result.exit_code, result.output) == (
    2,
    'Usage: cli check btest [OPTIONS] [PACKAGE] [TEST_NAME]\n'
    "Try 'cli check btest --help' for help.\n\n"
    'Error: No such option: --bogus\n',
  )


@pytest.mark.parametrize(
  ('filters', 'expected'),
  [
    (
      {},
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=zero',
        '-n',
        'auto',
      ],
    ),
    (
      {'keyword_expression': 'storage and not slow'},
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=zero',
        '-k',
        'storage and not slow',
      ],
    ),
    (
      {'nodeids': (_CLI_NODEID,)},
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=zero',
        f'zero/{_CLI_NODEID}',
      ],
    ),
    (
      {
        'marker_expression': 'integration',
        'nodeids': (_CLI_NODEID,),
        'parallel': False,
      },
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=zero',
        '-m',
        'integration',
        f'zero/{_CLI_NODEID}',
      ],
    ),
  ],
  ids=(
    'unfiltered-parallel',
    'targeted-keyword',
    'nodeid',
    'marker-in-process',
  ),
)
def test_ztest_composes_filters_and_parallelism(
  monkeypatch: MonkeyPatch,
  filters: PythonTestOptions,
  expected: list[str],
) -> None:
  fake_root = _stub_nodeid_fs(monkeypatch)
  calls = _record_check_cmd(monkeypatch)

  assert cli.do_ztest(**filters, repo_root=fake_root) == 0
  assert calls == [RunCmdCall(expected, 'command-plane-test', fake_root)]


@pytest.mark.parametrize(
  ('argv', 'expected_command'),
  [
    (
      ['check', 'ztest', '--parallel', '-k', 'telemetry'],
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=zero',
        '-n',
        'auto',
        '-k',
        'telemetry',
      ],
    ),
    (
      ['check', 'ptest'],
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=proj',
        '-n',
        'auto',
      ],
    ),
    (
      [
        'check',
        'ptest',
        '-k',
        'lifecycle',
        '--nodeid',
        _PROJ_NODEID,
        '--no-parallel',
      ],
      [
        sys.executable,
        '-m',
        'pytest',
        '-o',
        'testpaths=proj',
        '-k',
        'lifecycle',
        f'proj/{_PROJ_NODEID}',
      ],
    ),
  ],
  ids=('ztest-parallel-filter', 'ptest-default', 'ptest-targeted'),
)
def test_python_test_cli_dispatches_pytest_argv(
  monkeypatch: MonkeyPatch,
  argv: list[str],
  expected_command: list[str],
) -> None:
  fake_root = _stub_nodeid_fs(monkeypatch)
  calls = _record_check_cmd(monkeypatch)

  result = _RUNNER.invoke(cli.cli, argv, obj=fake_root)

  expected_label = (
    'command-plane-test' if argv[1] == 'ztest' else 'project-test'
  )
  assert (result.exit_code, result.output, calls) == (
    0,
    '',
    [RunCmdCall(expected_command, expected_label, fake_root)],
  )


@pytest.mark.parametrize(
  ('nodeid', 'expected'),
  [
    ('cli_test.py::test_a', 'zero/cli_test.py::test_a'),
    (
      'cli_test.py::Suite::test_a[case-1]',
      'zero/cli_test.py::Suite::test_a[case-1]',
    ),
    ('cli_test.py::test_a[]', 'zero/cli_test.py::test_a[]'),
  ],
  ids=('function', 'class-and-param', 'empty-param-id'),
)
def test_validate_test_nodeid_accepts_valid_selectors(
  monkeypatch: MonkeyPatch, nodeid: str, expected: str
) -> None:
  fake_root = _stub_nodeid_fs(monkeypatch)

  assert cli.validate_test_nodeid('zero', nodeid, repo_root=fake_root) == (
    expected
  )


@pytest.mark.parametrize(
  ('nodeid', 'expected_message'),
  [
    (
      'cli_test.py',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py::',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py::   ',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py:::',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py::Suite::',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py::test_a[unclosed',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py::test_a[]extra',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'cli_test.py::test_a]',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      '../proj/test_project.py::test_case',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      '/abs/cli_test.py::test_case',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'sub\\cli_test.py::test_case',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'README.md::test_case',
      'expected a zero/-relative Python test selector FILE::TEST',
    ),
    (
      'missing.py::test_case',
      'test file must resolve inside zero/ and exist',
    ),
    (
      'escape.py::test_case',
      'test file must resolve inside zero/ and exist',
    ),
    (
      'dir.py::test_case',
      'test file must exist inside zero/',
    ),
  ],
  ids=(
    'missing-separator',
    'missing-test',
    'whitespace-test',
    'extra-colon',
    'trailing-empty-segment',
    'unclosed-param',
    'trailing-param-suffix',
    'stray-closing-bracket',
    'parent-escape',
    'absolute-path',
    'backslash-path',
    'wrong-extension',
    'missing-file',
    'symlink-escape',
    'directory-py',
  ),
)
def test_python_test_command_rejects_invalid_node_ids(
  monkeypatch: MonkeyPatch, nodeid: str, expected_message: str
) -> None:
  fake_root = _stub_nodeid_fs(monkeypatch)
  calls = _record_check_cmd(monkeypatch)

  with pytest.raises(click.BadParameter) as error:
    cli.do_ztest(nodeids=(nodeid,), repo_root=fake_root)

  assert error.value.message == expected_message
  assert calls == []


@pytest.mark.parametrize(
  ('argv', 'expected'),
  [
    (
      ['run', '--help', 'core/hello.penta'],
      ('--help', 'core/hello.penta'),
    ),
    (['r', 'repl'], ('repl',)),
  ],
  ids=('run-with-flags', 'alias'),
)
def test_run_command_forwards_unprocessed_args(
  monkeypatch: MonkeyPatch, argv: list[str], expected: tuple[str, ...]
) -> None:
  calls: list[tuple[str, ...]] = []
  monkeypatch.setattr(
    cli.boot, 'run_shell', lambda args: calls.append(args)
  )

  result = _RUNNER.invoke(cli.cli, argv)

  assert (result.exit_code, result.output, calls) == (0, '', [expected])


@pytest.mark.parametrize(
  ('alias', 'configured_name'),
  [
    ('luna', 'codex-luna-yolo'),
    ('sol', 'codex-sol-yolo'),
    ('astra', 'codex-astra-yolo'),
    ('sonnet', 'claude-sonnet-yolo'),
    ('fable', 'claude-fable-yolo'),
    ('flash', 'agy-flash-yolo'),
    ('argon', 'agy-argon-yolo'),
    ('carbon', 'agy-carbon-yolo'),
  ],
)
def test_agent_aliases_forward_configured_agent_and_arguments(
  monkeypatch: MonkeyPatch, alias: str, configured_name: str
) -> None:
  calls: list[tuple[str, tuple[str, ...]]] = []
  monkeypatch.setattr(
    cli.agent_runner,
    'launch',
    lambda name, arguments: calls.append((name, arguments)),
  )

  result = _RUNNER.invoke(cli.cli, ['a', alias, '--resume', 'session'])

  assert (result.exit_code, result.output, calls) == (
    0,
    '',
    [(configured_name, ('--resume', 'session'))],
  )


def test_agy_command_help_uses_system_prompt_wording() -> None:
  agent_group = cli.cli.commands['agent']
  assert isinstance(agent_group, click.Group)
  assert {
    name: agent_group.commands[name].help
    for name in ('agy-flash-yolo', 'agy-argon-yolo', 'agy-carbon-yolo')
  } == {
    'agy-flash-yolo': (
      'Launch Antigravity Flash with the Pentagram system prompt.'
    ),
    'agy-argon-yolo': (
      'Launch Antigravity Argon with the Pentagram system prompt.'
    ),
    'agy-carbon-yolo': (
      'Launch Antigravity Carbon with the Pentagram system prompt.'
    ),
  }


def test_project_command_is_registered_on_the_root_cli() -> None:
  root_context = click.Context(cli.cli)
  proj_group = cli.cli.commands['proj']
  assert proj_group is cli.project_runner.project_group
  assert cli.cli.get_command(root_context, 'p') is (
    cli.project_runner.project_group
  )

  result = _RUNNER.invoke(cli.cli, ['proj', '--help'])
  expected = _RUNNER.invoke(
    cli.project_runner.project_group, ['--help'], prog_name='cli proj'
  )

  assert (result.exit_code, result.output) == (0, expected.output)
