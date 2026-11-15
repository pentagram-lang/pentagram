import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import click

from proj import cli as project_runner
from zero import agent as agent_runner
from zero import boot, commit_message, doc_lint, lib, repo_policy, watch


def _context_repo_root(ctx: click.Context) -> Path:
  return ctx.obj if isinstance(ctx.obj, Path) else lib.REPO_ROOT


def resolve_repo_root(start: Path | None = None) -> Path:
  try:
    current = (Path.cwd() if start is None else start).resolve()
  except OSError as error:
    raise click.ClickException(
      'zero/__main__.py not found in parent directories.'
    ) from error

  for candidate in (current, *current.parents):
    if (candidate / 'zero' / '__main__.py').is_file():
      return candidate
  raise click.ClickException(
    'zero/__main__.py not found in parent directories.'
  )


@click.group(cls=lib.AliasedGroup, invoke_without_command=True)
@click.option('-w', '--watch', is_flag=True, help='Run in watch mode.')
@click.pass_context
def cli(ctx: click.Context, watch: bool) -> None:
  """Pentagram task runner."""
  if watch and ctx.invoked_subcommand is not None:
    raise click.UsageError('--watch cannot be combined with a subcommand.')
  if watch and ctx.invoked_subcommand is None:
    ctx.invoke(watch_cmd)


def main(argv: Sequence[str] | None = None) -> None:
  try:
    repo_root = resolve_repo_root()
  except click.ClickException as error:
    error.show()
    raise SystemExit(error.exit_code) from error

  previous_cwd: Path | None
  try:
    previous_cwd = Path.cwd()
  except OSError:
    previous_cwd = None

  try:
    os.chdir(repo_root)
    cli(
      args=list(argv) if argv is not None else None,
      prog_name='0',
      obj=repo_root,
    )
  finally:
    if previous_cwd is not None:
      try:
        os.chdir(previous_cwd)
      except OSError:
        pass


def _relative_nix_files(repo_root: Path) -> list[str]:
  return [
    Path(path).relative_to(repo_root).as_posix()
    for path in lib.nix_files(repo_root)
  ]


def _exit_if_failed(code: int) -> None:
  if code != 0:
    raise SystemExit(code)


def _run_check_group(
  label: str, steps: Sequence[Callable[[], int]]
) -> int:
  t = lib.Timer()
  exit_code = 0
  for step in steps:
    step_code = step()
    if step_code != 0 and exit_code == 0:
      exit_code = step_code

  lib.status(label, t.duration(), success=(exit_code == 0))
  return exit_code


def _run_validator(
  label: str,
  validator: Callable[[str], object],
  caught: tuple[type[Exception], ...],
  *,
  repo_root: Path = lib.REPO_ROOT,
) -> int:
  t = lib.Timer()
  try:
    validator(str(repo_root))
  except caught as error:
    click.echo(f'Error: {lib.sanitize_text(str(error))}', err=True)
    lib.status(label, t.duration(), success=False)
    return 1
  lib.status(label, t.duration())
  return 0


def _nixfmt_paths_or_fail(repo_root: Path) -> list[str] | None:
  t = lib.Timer()
  try:
    return _relative_nix_files(repo_root)
  except RuntimeError as error:
    click.echo(f'Error: {lib.sanitize_text(str(error))}', err=True)
    lib.status('nix-fmt', t.duration(), success=False)
    return None


def _check_nix_fmt(repo_root: Path) -> int:
  nix_paths = _nixfmt_paths_or_fail(repo_root)
  if nix_paths is None:
    return 1
  if not nix_paths:
    return 0
  return lib.check_cmd(
    ['nixfmt', '--check', '--', *nix_paths], 'nix-fmt', cwd=repo_root
  )


def do_fix_fmt(repo_root: Path = lib.REPO_ROOT) -> None:
  t = lib.Timer()
  lib.run_cmd(['cargo', 'fmt'], 'rust-fmt', cwd=repo_root)
  lib.run_cmd(['ruff', 'format'], 'py-fmt', cwd=repo_root)
  lib.run_cmd(['dprint', 'fmt'], 'dprint', cwd=repo_root)
  nix_paths = _nixfmt_paths_or_fail(repo_root)
  if nix_paths is None:
    raise SystemExit(1)
  if nix_paths:
    lib.run_cmd(['nixfmt', '--', *nix_paths], 'nix-fmt', cwd=repo_root)
  lib.status('fix-fmt', t.duration())


def do_check_fmt(repo_root: Path = lib.REPO_ROOT) -> int:
  return _run_check_group(
    'check-fmt',
    [
      lambda: lib.check_cmd(
        ['cargo', 'fmt', '--', '--check'], 'rust-fmt', cwd=repo_root
      ),
      lambda: lib.check_cmd(
        ['ruff', 'format', '--check'], 'py-fmt', cwd=repo_root
      ),
      lambda: lib.check_cmd(['dprint', 'check'], 'dprint', cwd=repo_root),
      lambda: _check_nix_fmt(repo_root),
    ],
  )


def do_fix_lint(
  package: str | None = None, *, repo_root: Path = lib.REPO_ROOT
) -> None:
  t = lib.Timer()
  lib.run_cmd(['ruff', 'check', '--fix'], 'py-lint', cwd=repo_root)
  lib.run_cmd(
    lib.get_cargo_fix_cmd(package=package), 'rust-fixit', cwd=repo_root
  )
  lib.run_cmd(
    lib.get_cargo_clippy_cmd(package=package), 'clippy', cwd=repo_root
  )
  lib.status('fix-lint', t.duration())


def do_check_lint(
  package: str | None = None, *, repo_root: Path = lib.REPO_ROOT
) -> int:
  return _run_check_group(
    'check-lint',
    [
      lambda: lib.check_cmd(['ruff', 'check'], 'py-lint', cwd=repo_root),
      lambda: lib.check_cmd(
        lib.get_cargo_clippy_cmd(package=package), 'clippy', cwd=repo_root
      ),
    ],
  )


def do_btest(
  package: str | None = None,
  test_name: str | None = None,
  *,
  nocapture: bool = False,
  exact: bool = False,
  repo_root: Path = lib.REPO_ROOT,
) -> int:
  test_cmd = lib.get_cargo_test_cmd(
    package=package,
    test_name=test_name,
    nocapture=nocapture,
    exact=exact,
  )
  return lib.check_cmd(test_cmd, 'btest', cwd=repo_root)


def do_test(repo_root: Path = lib.REPO_ROOT) -> int:
  return lib.check_cmd(
    ['cargo', 'run', '-p', 'boot_shell', '--', 'test', 'core'],
    'test',
    cwd=repo_root,
  )


def validate_test_nodeid(
  test_root: str, nodeid: str, *, repo_root: Path = lib.REPO_ROOT
) -> str:
  test_file, separator, test_name = nodeid.partition('::')
  relative_path = Path(test_file)
  qual_part, bracket, param_part = test_name.partition('[')
  if (
    not separator
    or not test_name
    or '\\' in test_file
    or relative_path.is_absolute()
    or '..' in relative_path.parts
    or relative_path.suffix != '.py'
    or not qual_part
    or any(
      not part or part != part.strip() or ':' in part or ']' in part
      for part in qual_part.split('::')
    )
    or (bool(bracket) and not param_part.endswith(']'))
  ):
    raise click.BadParameter(
      f'expected a {test_root}/-relative Python test selector FILE::TEST'
    )

  root = (repo_root / test_root).resolve()
  try:
    resolved_path = (root / relative_path).resolve(strict=True)
    resolved_path.relative_to(root)
  except (OSError, RuntimeError, ValueError) as error:
    raise click.BadParameter(
      f'test file must resolve inside {test_root}/ and exist'
    ) from error

  if not resolved_path.is_file():
    raise click.BadParameter(f'test file must exist inside {test_root}/')

  suite_path = resolved_path.relative_to(root).as_posix()
  return f'{test_root}/{suite_path}::{test_name}'


def do_python_tests(
  test_root: str,
  label: str,
  keyword_expression: str | None = None,
  marker_expression: str | None = None,
  nodeids: tuple[str, ...] = (),
  parallel: bool | None = None,
  *,
  repo_root: Path = lib.REPO_ROOT,
) -> int:
  cmd = [sys.executable, '-m', 'pytest', '-o', f'testpaths={test_root}']
  if parallel is None:
    parallel = not (
      keyword_expression is not None
      or marker_expression is not None
      or nodeids
    )
  if parallel:
    cmd.extend(['-n', 'auto'])
  if keyword_expression is not None:
    cmd.extend(['-k', keyword_expression])
  if marker_expression is not None:
    cmd.extend(['-m', marker_expression])
  cmd.extend(
    validate_test_nodeid(test_root, nodeid, repo_root=repo_root)
    for nodeid in nodeids
  )
  return lib.check_cmd(cmd, label, cwd=repo_root)


def do_ptest(
  keyword_expression: str | None = None,
  marker_expression: str | None = None,
  nodeids: tuple[str, ...] = (),
  parallel: bool | None = None,
  *,
  repo_root: Path = lib.REPO_ROOT,
) -> int:
  return do_python_tests(
    'proj',
    'project-test',
    keyword_expression,
    marker_expression,
    nodeids,
    parallel,
    repo_root=repo_root,
  )


def do_ztest(
  keyword_expression: str | None = None,
  marker_expression: str | None = None,
  nodeids: tuple[str, ...] = (),
  parallel: bool | None = None,
  *,
  repo_root: Path = lib.REPO_ROOT,
) -> int:
  return do_python_tests(
    'zero',
    'command-plane-test',
    keyword_expression,
    marker_expression,
    nodeids,
    parallel,
    repo_root=repo_root,
  )


def do_check_history(repo_root: Path = lib.REPO_ROOT) -> int:
  return lib.check_cmd(['cog', 'check'], 'history', cwd=repo_root)


def do_check_repo_policy(repo_root: Path = lib.REPO_ROOT) -> int:
  return _run_validator(
    'repo-policy',
    repo_policy.check_repository_policy,
    (repo_policy.RepositoryPolicyError,),
    repo_root=repo_root,
  )


def do_check_doc_lint(repo_root: Path = lib.REPO_ROOT) -> int:
  return _run_validator(
    'doc-lint',
    doc_lint.check_documentation,
    (doc_lint.DocumentationLintError, RuntimeError),
    repo_root=repo_root,
  )


def do_check_type(repo_root: Path = lib.REPO_ROOT) -> int:
  return lib.check_cmd(
    ['ty', 'check', '--python', sys.prefix], 'type', cwd=repo_root
  )


def do_check_commit_message(repo_root: Path = lib.REPO_ROOT) -> int:
  return _run_validator(
    'commit-message',
    commit_message.check_commit_message,
    (commit_message.CommitMessageLintError, RuntimeError),
    repo_root=repo_root,
  )


def do_generate_changelog(repo_root: Path = lib.REPO_ROOT) -> None:
  lib.run_cmd(['git', 'cliff'], 'changelog', cwd=repo_root)


@lib.group_with_aliases(cli, aliases=['f'], invoke_without_command=True)
@click.pass_context
def fix(ctx: click.Context) -> None:
  """Format and lint the codebase."""
  if ctx.invoked_subcommand is None:
    repo_root = _context_repo_root(ctx)
    t = lib.Timer()
    do_fix_fmt(repo_root)
    do_fix_lint(repo_root=repo_root)
    lib.status('fix', t.duration())


@lib.command_with_aliases(fix, name='fmt', aliases=['f'])
@click.pass_context
def fmt_fix(ctx: click.Context) -> None:
  """Run Cargo, Ruff, dprint, and nixfmt formatters."""
  do_fix_fmt(_context_repo_root(ctx))


@lib.command_with_aliases(fix, name='lint', aliases=['l'])
@click.argument('package', required=False, type=str)
@click.pass_context
def lint_fix(ctx: click.Context, package: str | None) -> None:
  """Run ruff check --fix across Python and cargo fixit/clippy
  (optionally for Cargo PACKAGE)."""
  do_fix_lint(package, repo_root=_context_repo_root(ctx))


@lib.group_with_aliases(cli, aliases=['c'], invoke_without_command=True)
@click.option(
  '-s',
  '--skip-commit',
  is_flag=True,
  help='Skip commit-message and history validation.',
)
@click.pass_context
def check(ctx: click.Context, skip_commit: bool) -> None:
  """Format, lint, test, and validate history."""
  if skip_commit and ctx.invoked_subcommand is not None:
    raise click.UsageError(
      '--skip-commit cannot be combined with a subcommand.'
    )
  if ctx.invoked_subcommand is None:
    repo_root = _context_repo_root(ctx)
    steps: list[Callable[[], int]] = [
      lambda: do_check_fmt(repo_root),
      lambda: do_check_lint(repo_root=repo_root),
      lambda: do_check_type(repo_root),
      lambda: do_check_repo_policy(repo_root),
      lambda: do_check_doc_lint(repo_root),
      lambda: do_ztest(repo_root=repo_root),
      lambda: do_ptest(repo_root=repo_root),
      lambda: do_btest(repo_root=repo_root),
      lambda: do_test(repo_root),
    ]
    if not skip_commit:
      steps.extend(
        [
          lambda: do_check_commit_message(repo_root),
          lambda: do_check_history(repo_root),
        ]
      )
    _exit_if_failed(_run_check_group('check', steps))


@lib.command_with_aliases(check, name='fmt', aliases=['f'])
@click.pass_context
def fmt_check(ctx: click.Context) -> None:
  """Run Cargo, Ruff, dprint, and nixfmt format checks."""
  _exit_if_failed(do_check_fmt(_context_repo_root(ctx)))


@lib.command_with_aliases(check, name='policy', aliases=['p'])
@click.pass_context
def policy_check(ctx: click.Context) -> None:
  """Run repository policy check."""
  _exit_if_failed(do_check_repo_policy(_context_repo_root(ctx)))


@lib.command_with_aliases(check, name='doc', aliases=['d'])
@click.pass_context
def doc_check(ctx: click.Context) -> None:
  """Run documentation lint."""
  _exit_if_failed(do_check_doc_lint(_context_repo_root(ctx)))


@lib.command_with_aliases(check, name='type')
@click.pass_context
def type_check(ctx: click.Context) -> None:
  """Enforce ty checking across first-party Python code and tests."""
  _exit_if_failed(do_check_type(_context_repo_root(ctx)))


@lib.command_with_aliases(check, name='commit', aliases=['m'])
@click.pass_context
def commit_check(ctx: click.Context) -> None:
  """Run commit-message line-length validation."""
  _exit_if_failed(do_check_commit_message(_context_repo_root(ctx)))


@lib.command_with_aliases(check, name='lint', aliases=['l'])
@click.argument('package', required=False, type=str)
@click.pass_context
def lint_check(ctx: click.Context, package: str | None) -> None:
  """Run ruff check across Python and cargo clippy
  (optionally for Cargo PACKAGE)."""
  _exit_if_failed(
    do_check_lint(package, repo_root=_context_repo_root(ctx))
  )


@lib.command_with_aliases(check, aliases=['bt'])
@click.option(
  '-n',
  '--nocapture',
  is_flag=True,
  help='Pass --nocapture to the Rust test binary.',
)
@click.option(
  '--exact',
  is_flag=True,
  help='Match test_name exactly.',
)
@click.argument('package', required=False, type=str)
@click.argument('test_name', required=False, type=str)
@click.pass_context
def btest(
  ctx: click.Context,
  nocapture: bool,
  exact: bool,
  package: str | None,
  test_name: str | None,
) -> None:
  """Run cargo test (bootstrap tests)."""
  _exit_if_failed(
    do_btest(
      package,
      test_name,
      nocapture=nocapture,
      exact=exact,
      repo_root=_context_repo_root(ctx),
    )
  )


@lib.command_with_aliases(check, aliases=['t'])
@click.pass_context
def test(ctx: click.Context) -> None:
  """Run core language tests."""
  _exit_if_failed(do_test(_context_repo_root(ctx)))


@lib.command_with_aliases(check, name='ptest')
@click.option(
  '-k',
  'keyword_expression',
  help='Only run tests matching this keyword expression.',
)
@click.option(
  '-m',
  'marker_expression',
  help='Only run tests matching this marker expression.',
)
@click.option(
  '--parallel/--no-parallel',
  default=None,
  help=(
    'Filtered runs use the main process; --parallel enables xdist. '
    'Unfiltered runs use xdist unless --no-parallel is set.'
  ),
)
@click.option(
  '--nodeid',
  'nodeids',
  multiple=True,
  metavar='FILE::TEST',
  help=(
    'Run a test selected by a path relative to proj/. '
    'Repeat to select more tests.'
  ),
)
@click.pass_context
def project_test(
  ctx: click.Context,
  keyword_expression: str | None,
  marker_expression: str | None,
  parallel: bool | None,
  nodeids: tuple[str, ...],
) -> None:
  """Run project tests with optional filters and parallel execution."""
  _exit_if_failed(
    do_ptest(
      keyword_expression,
      marker_expression,
      nodeids,
      parallel,
      repo_root=_context_repo_root(ctx),
    )
  )


@lib.command_with_aliases(check, name='ztest')
@click.option(
  '-k',
  'keyword_expression',
  help='Only run tests matching this keyword expression.',
)
@click.option(
  '-m',
  'marker_expression',
  help='Only run tests matching this marker expression.',
)
@click.option(
  '--parallel/--no-parallel',
  default=None,
  help=(
    'Filtered runs use the main process; --parallel enables xdist. '
    'Unfiltered runs use xdist unless --no-parallel is set.'
  ),
)
@click.option(
  '--nodeid',
  'nodeids',
  multiple=True,
  metavar='FILE::TEST',
  help=(
    'Run a test selected by a path relative to zero/. '
    'Repeat to select more tests.'
  ),
)
@click.pass_context
def command_plane_test(
  ctx: click.Context,
  keyword_expression: str | None,
  marker_expression: str | None,
  parallel: bool | None,
  nodeids: tuple[str, ...],
) -> None:
  """Run command-plane tests with pytest filters."""
  _exit_if_failed(
    do_ztest(
      keyword_expression,
      marker_expression,
      nodeids,
      parallel,
      repo_root=_context_repo_root(ctx),
    )
  )


@lib.command_with_aliases(check, aliases=['h'])
@click.pass_context
def history(ctx: click.Context) -> None:
  """Run cog check."""
  _exit_if_failed(do_check_history(_context_repo_root(ctx)))


@lib.command_with_aliases(check, aliases=['ch'])
@click.pass_context
def changelog(ctx: click.Context) -> None:
  """Run git cliff."""
  do_generate_changelog(_context_repo_root(ctx))


@lib.command_with_aliases(
  cli,
  aliases=['r'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def run(args: tuple[str, ...]) -> None:
  """Run the boot_shell (boot/shell)."""
  boot.run_shell(args)


@lib.group_with_aliases(cli, aliases=['a'])
def agent() -> None:
  """Launch a Pentagram-configured coding agent."""


@lib.command_with_aliases(
  agent,
  name='codex-luna-yolo',
  aliases=['luna'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def codex_luna_agent(args: tuple[str, ...]) -> None:
  """Launch Codex Luna with the Pentagram system prompt."""
  agent_runner.launch('codex-luna-yolo', args)


@lib.command_with_aliases(
  agent,
  name='codex-sol-yolo',
  aliases=['sol'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def codex_sol_agent(args: tuple[str, ...]) -> None:
  """Launch Codex Sol with the Pentagram system prompt."""
  agent_runner.launch('codex-sol-yolo', args)


@lib.command_with_aliases(
  agent,
  name='codex-astra-yolo',
  aliases=['astra'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def codex_astra_agent(args: tuple[str, ...]) -> None:
  """Launch Codex Astra with the Pentagram system prompt."""
  agent_runner.launch('codex-astra-yolo', args)


@lib.command_with_aliases(
  agent,
  name='claude-sonnet-yolo',
  aliases=['sonnet'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def claude_sonnet_agent(args: tuple[str, ...]) -> None:
  """Launch Claude Sonnet with the Pentagram system prompt."""
  agent_runner.launch('claude-sonnet-yolo', args)


@lib.command_with_aliases(
  agent,
  name='claude-fable-yolo',
  aliases=['fable'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def claude_fable_agent(args: tuple[str, ...]) -> None:
  """Launch Claude Fable with the Pentagram system prompt."""
  agent_runner.launch('claude-fable-yolo', args)


@lib.command_with_aliases(
  agent,
  name='agy-flash-yolo',
  aliases=['flash'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def agy_flash_agent(args: tuple[str, ...]) -> None:
  """Launch Antigravity Flash with the Pentagram system prompt."""
  agent_runner.launch('agy-flash-yolo', args)


@lib.command_with_aliases(
  agent,
  name='agy-argon-yolo',
  aliases=['argon'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def agy_argon_agent(args: tuple[str, ...]) -> None:
  """Launch Antigravity Argon with the Pentagram system prompt."""
  agent_runner.launch('agy-argon-yolo', args)


@lib.command_with_aliases(
  agent,
  name='agy-carbon-yolo',
  aliases=['carbon'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def agy_carbon_agent(args: tuple[str, ...]) -> None:
  """Launch Antigravity Carbon with the Pentagram system prompt."""
  agent_runner.launch('agy-carbon-yolo', args)


@lib.command_with_aliases(cli, aliases=['w'])
@click.pass_context
def watch_cmd(ctx: click.Context) -> None:
  """Watch for changes and run tests."""
  watch.run_watch(_context_repo_root(ctx))


cli.add_command(project_runner.project_group, name='proj')


if __name__ == '__main__':
  main()
