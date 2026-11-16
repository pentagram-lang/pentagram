import os
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner
from pytest import CaptureFixture, MonkeyPatch

from zero import lib


def test_parse_git_ls_files_and_git_ls_files(
  monkeypatch: MonkeyPatch,
) -> None:
  assert lib.parse_git_ls_files(b'') == ()
  assert lib.parse_git_ls_files(
    b'README.md\0\0nix/\xffbad.nix\0README.md\0sub/file.py\0'
  ) == (
    Path('README.md'),
    Path(os.fsdecode(b'nix/\xffbad.nix')),
    Path('sub/file.py'),
  )

  calls: list[list[str]] = []

  def fake_run(argv: list[str], **_kwargs: object) -> SimpleNamespace:
    calls.append(argv)
    return SimpleNamespace(
      returncode=0,
      stdout=b'README.md\0README.md\0zero/cli.py\0',
      stderr=b'',
    )

  monkeypatch.setattr(lib.subprocess, 'run', fake_run)
  assert lib.git_ls_files(Path('/repo')) == (
    Path('README.md'),
    Path('zero/cli.py'),
  )
  assert calls == [
    [
      'git',
      '-C',
      '/repo',
      'ls-files',
      '--cached',
      '--others',
      '--exclude-standard',
      '-z',
    ]
  ]


def test_repo_root_points_to_checkout_root() -> None:
  assert lib.REPO_ROOT == Path(__file__).resolve().parent.parent


def test_timer_uses_monotonic_elapsed_time(
  monkeypatch: MonkeyPatch,
) -> None:
  timer = lib.Timer(started_at=10.0)
  with monkeypatch.context() as patch:
    patch.setattr(lib.time, 'monotonic', lambda: 12.25)
    duration = timer.duration()

  assert duration == 2.25


@pytest.mark.parametrize(
  ('label', 'duration', 'success', 'use_colour', 'expected'),
  [
    ('check-fmt', 0.25, True, False, '[PASS] check-fmt (0.25s)\n'),
    ('check-lint', 1.5, False, False, '[FAIL] check-lint (1.50s)\n'),
    (
      'check-fmt',
      0.25,
      True,
      True,
      '[\x1b[32m\x1b[1mPASS\x1b[0m] check-fmt (0.25s)\n',
    ),
    (
      'check-lint',
      1.5,
      False,
      True,
      '[\x1b[31m\x1b[1mFAIL\x1b[0m] check-lint (1.50s)\n',
    ),
  ],
  ids=('pass-plain', 'fail-plain', 'pass-ansi', 'fail-ansi'),
)
def test_status_formats_pass_and_fail_lines(
  capsys: CaptureFixture[str],
  label: str,
  duration: float,
  success: bool,
  use_colour: bool,
  expected: str,
) -> None:
  if use_colour:
    with click.Context(click.Command('cmd'), color=True):
      lib.status(label, duration, success=success)
  else:
    lib.status(label, duration, success=success)

  assert capsys.readouterr().out == expected


@pytest.mark.parametrize(
  ('root', 'expected'),
  [
    (
      '.',
      [
        'flake.nix',
        'nix/overlays/dev.nix',
        'nix/zero.nix',
        os.fsdecode(b'nix/\xffbad.nix'),
      ],
    ),
    (
      Path('repo'),
      [
        'repo/flake.nix',
        'repo/nix/overlays/dev.nix',
        'repo/nix/zero.nix',
        f'repo/{os.fsdecode(b"nix/\xffbad.nix")}',
      ],
    ),
  ],
  ids=('default-root', 'explicit-path'),
)
def test_nix_files_uses_git_inventory_and_skips_symlinks(
  monkeypatch: MonkeyPatch,
  root: str | os.PathLike[str],
  expected: list[str],
) -> None:
  git_calls: list[tuple[tuple[str, ...], dict[str, object]]] = []
  monkeypatch.setattr(
    lib.Path, 'is_symlink', lambda self: self.name == 'result.nix'
  )
  monkeypatch.setattr(
    lib.Path, 'is_file', lambda self: self.name != 'dir.nix'
  )

  def fake_run(
    argv: list[str],
    **kwargs: object,
  ) -> SimpleNamespace:
    git_calls.append((tuple(argv), kwargs))
    return SimpleNamespace(
      returncode=0,
      stdout=(
        b'nix/zero.nix\0'
        b'flake.nix\0'
        b'flake.nix\0'
        b'result.nix\0'
        b'dir.nix\0'
        b'nix/\xffbad.nix\0'
        b'nix/overlays/dev.nix\0'
      ),
    )

  monkeypatch.setattr(lib.subprocess, 'run', fake_run)

  assert lib.nix_files(root) == expected
  assert git_calls == [
    (
      (
        'git',
        '-C',
        os.fspath(root),
        'ls-files',
        '--cached',
        '--others',
        '--exclude-standard',
        '-z',
        '--',
        '*.nix',
      ),
      {'capture_output': True, 'check': False},
    )
  ]


def test_nix_files_raises_when_git_invocation_fails(
  monkeypatch: MonkeyPatch,
) -> None:
  def missing_git(_argv: list[str], **_kwargs: object) -> SimpleNamespace:
    raise FileNotFoundError(2, 'No such file or directory', 'git')

  monkeypatch.setattr(lib.subprocess, 'run', missing_git)

  with pytest.raises(
    RuntimeError, match=r'Cannot scan Nix files with git: .*git'
  ):
    lib.nix_files('.')


@pytest.mark.parametrize(
  ('stderr', 'expected_detail'),
  [
    (b'fatal: not a git repository\n', 'fatal: not a git repository'),
    (b'', 'unknown git error'),
  ],
  ids=('stderr-detail', 'empty-stderr'),
)
def test_nix_files_raises_on_git_error_exit(
  monkeypatch: MonkeyPatch,
  stderr: bytes,
  expected_detail: str,
) -> None:
  monkeypatch.setattr(
    lib.subprocess,
    'run',
    lambda _argv, **_kwargs: SimpleNamespace(
      returncode=128, stdout=b'', stderr=stderr
    ),
  )

  with pytest.raises(
    RuntimeError,
    match=f'^Cannot scan Nix files with git: {expected_detail}$',
  ):
    lib.nix_files(Path('repo'))


@pytest.mark.parametrize(
  'failing_method',
  ['is_symlink', 'is_file'],
  ids=('symlink-permission-error', 'stat-permission-error'),
)
def test_nix_files_raises_on_candidate_os_error(
  monkeypatch: MonkeyPatch, failing_method: str
) -> None:
  bad_name = os.fsdecode(b'nix/\xffbad.nix')
  monkeypatch.setattr(
    lib.subprocess,
    'run',
    lambda _argv, **_kwargs: SimpleNamespace(
      returncode=0, stdout=b'nix/\xffbad.nix\0', stderr=b''
    ),
  )
  monkeypatch.setattr(lib.Path, 'is_symlink', lambda _self: False)
  monkeypatch.setattr(lib.Path, 'is_file', lambda _self: True)

  def fail_stat(_self: Path) -> bool:
    raise PermissionError(13, 'Permission denied', bad_name)

  monkeypatch.setattr(lib.Path, failing_method, fail_stat)

  with pytest.raises(
    RuntimeError,
    match=(
      r'^Cannot scan Nix files: \[Errno 13\] Permission denied: '
      r"'nix/\\udcffbad\.nix'$"
    ),
  ):
    lib.nix_files('.')


def test_check_cmd_rejects_empty_commands() -> None:
  with pytest.raises(ValueError, match='cmd must be non-empty'):
    lib.check_cmd([])
  with pytest.raises(ValueError, match='cmd must be non-empty'):
    lib.check_cmd(())


@pytest.mark.parametrize(
  ('command', 'label', 'cwd', 'expected_display', 'expected_label'),
  [
    (['pytest', '-q'], 'python-test', None, 'pytest -q', 'python-test'),
    (
      ('echo', 'hello world'),
      None,
      Path('/repo/root'),
      "echo 'hello world'",
      "echo 'hello world'",
    ),
  ],
  ids=('explicit-label', 'default-label-and-cwd'),
)
def test_check_cmd_and_run_cmd_report_success_and_forward_cwd(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
  command: list[str] | tuple[str, ...],
  label: str | None,
  cwd: Path | None,
  expected_display: str,
  expected_label: str,
) -> None:
  calls: list[tuple[tuple[str, ...], Path | None, bool]] = []
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []

  def fake_run(
    argv: list[str] | tuple[str, ...], *, cwd: Path | None, check: bool
  ) -> SimpleNamespace:
    calls.append((tuple(argv), cwd, check))
    return SimpleNamespace(returncode=0)

  monkeypatch.setattr(lib.subprocess, 'run', fake_run)
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.25)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  assert lib.check_cmd(command, label, cwd=cwd) == 0
  lib.run_cmd(command, label, cwd=cwd)

  captured = capsys.readouterr()
  assert (captured.out, captured.err) == (
    f'Running: {expected_display}\nRunning: {expected_display}\n',
    '',
  )
  assert calls == [
    (tuple(command), cwd, False),
    (tuple(command), cwd, False),
  ]
  assert reports == [
    ((expected_label, 0.25), {'success': True}),
    ((expected_label, 0.25), {'success': True}),
  ]


@pytest.mark.parametrize(
  ('returncode', 'expected_exit'),
  [
    (9, 9),
    (-15, 143),
  ],
  ids=('non-zero-exit', 'signal-termination'),
)
def test_check_cmd_and_run_cmd_map_non_zero_and_signal_exit_codes(
  monkeypatch: MonkeyPatch,
  capsys: CaptureFixture[str],
  returncode: int,
  expected_exit: int,
) -> None:
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []
  monkeypatch.setattr(
    lib.subprocess,
    'run',
    lambda _argv, *, cwd, check: SimpleNamespace(returncode=returncode),
  )
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.5)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  assert (
    lib.check_cmd(['pytest'], 'python-test', cwd=Path('/repo'))
    == expected_exit
  )
  with pytest.raises(SystemExit) as error:
    lib.run_cmd(['pytest'], 'python-test', cwd=Path('/repo'))

  assert error.value.code == expected_exit
  captured = capsys.readouterr()
  assert (captured.out, captured.err) == (
    'Running: pytest\nRunning: pytest\n',
    '',
  )
  assert reports == [
    (('python-test', 0.5), {'success': False}),
    (('python-test', 0.5), {'success': False}),
  ]


def test_check_cmd_and_run_cmd_handle_os_error_with_exit_one(
  monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
  reports: list[tuple[tuple[object, ...], dict[str, object]]] = []

  def missing_binary(
    _argv: list[str], *, cwd: Path | None, check: bool
  ) -> object:
    raise FileNotFoundError(2, 'No such file or directory', 'missing-tool')

  monkeypatch.setattr(lib.subprocess, 'run', missing_binary)
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.1)
  )
  monkeypatch.setattr(
    lib,
    'status',
    lambda *arguments, **options: reports.append((arguments, options)),
  )

  assert lib.check_cmd(['missing-tool'], 'missing') == 1
  with pytest.raises(SystemExit) as error:
    lib.run_cmd(['missing-tool'], 'missing')

  assert error.value.code == 1
  captured = capsys.readouterr()
  expected_err = (
    "Error: [Errno 2] No such file or directory: 'missing-tool'\n"
  )
  assert (captured.out, captured.err) == (
    'Running: missing-tool\nRunning: missing-tool\n',
    f'{expected_err}{expected_err}',
  )
  assert reports == [
    (('missing', 0.1), {'success': False}),
    (('missing', 0.1), {'success': False}),
  ]


@pytest.mark.parametrize(
  ('label', 'raise_error', 'expected_exit', 'expected_output'),
  [
    (
      None,
      False,
      0,
      "Running: nixfmt -- 'nix/\\udcffbad.nix'\n"
      "[PASS] nixfmt -- 'nix/\\udcffbad.nix' (0.25s)\n",
    ),
    (
      'nix-fmt',
      False,
      0,
      "Running: nixfmt -- 'nix/\\udcffbad.nix'\n[PASS] nix-fmt (0.25s)\n",
    ),
    (
      None,
      True,
      1,
      "Running: nixfmt -- 'nix/\\udcffbad.nix'\n"
      "Error: [Errno 2] No such file or directory: 'nix/\\udcffbad.nix'\n"
      "[FAIL] nixfmt -- 'nix/\\udcffbad.nix' (0.25s)\n",
    ),
  ],
  ids=('default-label', 'explicit-label', 'os-error'),
)
def test_check_cmd_sanitizes_surrogates_in_output_and_preserves_raw_cmd(
  monkeypatch: MonkeyPatch,
  label: str | None,
  raise_error: bool,
  expected_exit: int,
  expected_output: str,
) -> None:
  bad_path = os.fsdecode(b'nix/\xffbad.nix')
  exit_codes: list[int] = []
  seen_cmds: list[tuple[tuple[str, ...], Path | None, bool]] = []

  def fake_run(
    argv: list[str] | tuple[str, ...], *, cwd: Path | None, check: bool
  ) -> SimpleNamespace:
    seen_cmds.append((tuple(argv), cwd, check))
    if raise_error:
      raise FileNotFoundError(2, 'No such file or directory', bad_path)
    return SimpleNamespace(returncode=0)

  monkeypatch.setattr(lib.subprocess, 'run', fake_run)
  monkeypatch.setattr(
    lib, 'Timer', lambda: SimpleNamespace(duration=lambda: 0.25)
  )

  @click.command()
  def harness() -> None:
    exit_codes.append(lib.check_cmd(['nixfmt', '--', bad_path], label))

  result = CliRunner().invoke(harness, color=False)

  assert (
    exit_codes,
    result.exit_code,
    result.exception,
    result.output,
    seen_cmds,
  ) == (
    [expected_exit],
    0,
    None,
    expected_output,
    [(('nixfmt', '--', bad_path), None, False)],
  )


def test_aliased_group_and_decorators_resolve_aliases() -> None:
  invoked: list[str] = []
  policy_aliases = ['p']
  group_aliases = ['c']

  @click.group(cls=lib.AliasedGroup)
  def root() -> None:
    return None

  @root.command()
  def plain() -> None:
    click.echo('plain')

  @lib.group_with_aliases(root, aliases=group_aliases)
  def check() -> None:
    return None

  @lib.group_with_aliases(root)
  def extra() -> None:
    return None

  @lib.command_with_aliases(check, name='policy', aliases=policy_aliases)
  def policy_cmd() -> None:
    invoked.append('policy')
    click.echo('ok')

  group_aliases.append('mutated-group')
  policy_aliases.append('mutated-cmd')

  context = click.Context(root)
  assert isinstance(plain, lib.AliasedCommand)
  assert plain.aliases == ()
  assert extra.aliases == ()
  assert check.aliases == ('c',)
  assert policy_cmd.aliases == ('p',)
  assert root.get_command(context, 'plain') is plain
  assert root.get_command(context, 'check') is check
  assert root.get_command(context, 'c') is check
  assert root.get_command(context, 'mutated-group') is None
  assert root.get_command(context, 'unknown') is None
  assert check.get_command(context, 'p') is policy_cmd
  assert check.get_command(context, 'mutated-cmd') is None

  result = CliRunner().invoke(root, ['c', 'p'])
  assert (result.exit_code, result.output, invoked) == (
    0,
    'ok\n',
    ['policy'],
  )


@pytest.mark.parametrize(
  ('package', 'expected'),
  [
    (
      None,
      [
        'cargo',
        'clippy',
        '--all-targets',
        '--all-features',
        '--',
        '-D',
        'warnings',
      ],
    ),
    (
      'boot_lex',
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
    ),
  ],
  ids=('workspace', 'package'),
)
def test_cargo_clippy_command_builder_preserves_arguments(
  package: str | None, expected: list[str]
) -> None:
  assert lib.get_cargo_clippy_cmd(package) == expected


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
      'boot_lex',
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
    ),
  ],
  ids=('workspace', 'package'),
)
def test_cargo_fix_command_builder_preserves_arguments(
  package: str | None, expected: list[str]
) -> None:
  assert lib.get_cargo_fix_cmd(package) == expected


@pytest.mark.parametrize(
  ('package', 'test_name', 'nocapture', 'exact', 'expected'),
  [
    (None, None, False, False, ['cargo', 'test']),
    (
      'boot_lex',
      'lexer::rejects_invalid_text',
      False,
      False,
      ['cargo', 'test', '-p', 'boot_lex', 'lexer::rejects_invalid_text'],
    ),
    (
      None,
      'test_a',
      True,
      False,
      ['cargo', 'test', 'test_a', '--', '--nocapture'],
    ),
    (
      None,
      'test_a',
      False,
      True,
      ['cargo', 'test', 'test_a', '--', '--exact'],
    ),
    (
      'boot_lex',
      'lexer::rejects_invalid_text',
      True,
      True,
      [
        'cargo',
        'test',
        '-p',
        'boot_lex',
        'lexer::rejects_invalid_text',
        '--',
        '--exact',
        '--nocapture',
      ],
    ),
  ],
  ids=('default', 'package-and-test', 'nocapture', 'exact', 'all-options'),
)
def test_cargo_test_command_builder_preserves_arguments(
  package: str | None,
  test_name: str | None,
  nocapture: bool,
  exact: bool,
  expected: list[str],
) -> None:
  assert (
    lib.get_cargo_test_cmd(
      package=package,
      test_name=test_name,
      nocapture=nocapture,
      exact=exact,
    )
    == expected
  )


@pytest.mark.parametrize(
  ('value', 'expected'),
  [
    ({'a': 1, 'b': 'two'}, {'a': 1, 'b': 'two'}),
    ({}, {}),
    ({1: 'non-string-key'}, None),
    (['not', 'a', 'mapping'], None),
    ('string', None),
    (None, None),
  ],
  ids=(
    'object',
    'empty',
    'non-string-key',
    'list',
    'string',
    'none',
  ),
)
def test_json_object_narrows_string_keyed_mappings(
  value: object, expected: dict[str, object] | None
) -> None:
  assert lib.json_object(value) == expected


@pytest.mark.parametrize(
  ('value', 'expected'),
  [
    (['a', 'b'], ['a', 'b']),
    ([], []),
    (['a', 1], None),
    (('a', 'b'), None),
    ('ab', None),
    (None, None),
  ],
  ids=('strings', 'empty', 'mixed-item', 'tuple', 'string', 'none'),
)
def test_string_list_narrows_lists_of_strings(
  value: object, expected: list[str] | None
) -> None:
  assert lib.string_list(value) == expected
