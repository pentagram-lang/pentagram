#!/usr/bin/env python3
import os
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path

import click

from proj import cli as project_runner
from zero import agent as agent_runner
from zero import boot, commit_message, doc_lint, lib, repo_policy, watch

# Always run from the project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.group(cls=lib.AliasedGroup, invoke_without_command=True)
@click.option('-w', '--watch', is_flag=True, help='Run in watch mode.')
@click.pass_context
def cli(ctx: click.Context, watch: bool) -> None:
  """Pentagram task runner."""
  if ctx.invoked_subcommand is None and watch:
    ctx.invoke(watch_cmd)
  pass


def do_fix_fmt() -> None:
  t = lib.Timer()
  lib.run_cmd('cargo fmt', 'rust-fmt')
  lib.run_cmd('ruff format', 'py-fmt')
  lib.run_cmd('dprint fmt', 'dprint')
  lib.run_cmd('nixfmt *.nix nix/*.nix', 'nix-fmt')
  lib.status('fix-fmt', t.duration())


def do_check_fmt() -> None:
  t = lib.Timer()
  lib.run_cmd('cargo fmt -- --check', 'rust-fmt')
  lib.run_cmd('ruff format --check', 'py-fmt')
  lib.run_cmd('dprint check', 'dprint')
  lib.run_cmd('nixfmt --check *.nix nix/*.nix', 'nix-fmt')
  lib.status('check-fmt', t.duration())


def do_fix_lint(args: Sequence[str] | None = None) -> None:
  args = list(args) if args is not None else []

  t = lib.Timer()
  pos, _extras = lib.parse_args(args, max_pos=1)

  # Python Lint (Fix)
  lib.run_cmd('ruff check --fix', 'py-lint')

  # Rust Fixit
  pkg = pos[0] if pos else None
  fix_cmd = lib.get_cargo_fix_cmd(package=pkg)
  lib.run_cmd(shlex.join(fix_cmd), 'rust-fixit')

  # Rust Clippy
  clippy_cmd = lib.get_cargo_clippy_cmd(package=pkg)
  lib.run_cmd(shlex.join(clippy_cmd), 'clippy')
  lib.status('fix-lint', t.duration())


def do_check_lint(args: Sequence[str] | None = None) -> None:
  args = list(args) if args is not None else []

  t = lib.Timer()
  pos, _extras = lib.parse_args(args, max_pos=1)
  pkg = pos[0] if pos else None

  # Python Lint (Check)
  lib.run_cmd('ruff check', 'py-lint')

  # Rust Clippy
  clippy_cmd = lib.get_cargo_clippy_cmd(package=pkg)
  lib.run_cmd(shlex.join(clippy_cmd), 'clippy')
  lib.status('check-lint', t.duration())


def do_btest(args: Sequence[str] | None = None) -> None:
  if args is None:
    args = []

  # Scan for --nocapture or -n and remove them
  nocapture = False
  new_args = []
  for arg in args:
    if arg == '-n' or arg == '--nocapture':
      nocapture = True
    else:
      new_args.append(arg)

  pos, extras = lib.parse_args(new_args, max_pos=2)
  pkg = pos[0] if len(pos) > 0 else None
  test_name = pos[1] if len(pos) > 1 else None

  test_cmd = lib.get_cargo_test_cmd(
    package=pkg, test_name=test_name, extras=extras, nocapture=nocapture
  )

  lib.run_cmd(shlex.join(test_cmd), 'btest')


def do_test() -> None:
  lib.run_cmd('cargo run -p boot_shell -- test core', 'test')


def validate_test_nodeid(test_root: str, nodeid: str) -> str:
  test_file, separator, test_name = nodeid.partition('::')
  relative_path = Path(test_file)
  if (
    not separator
    or not test_name
    or '\\' in test_file
    or relative_path.is_absolute()
    or '..' in relative_path.parts
    or relative_path.suffix != '.py'
  ):
    raise click.BadParameter(
      'expected a root-relative Python test selector FILE::TEST'
    )

  root = Path(test_root).resolve()
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
) -> None:
  cmd = ['python', '-m', 'pytest', '-o', f'testpaths={test_root}']
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
  cmd.extend(validate_test_nodeid(test_root, nodeid) for nodeid in nodeids)
  lib.run_cmd(shlex.join(cmd), label)


def do_ptest(
  keyword_expression: str | None = None,
  marker_expression: str | None = None,
  nodeids: tuple[str, ...] = (),
  parallel: bool | None = None,
) -> None:
  do_python_tests(
    'proj',
    'project-test',
    keyword_expression,
    marker_expression,
    nodeids,
    parallel,
  )


def do_ztest(
  keyword_expression: str | None = None,
  marker_expression: str | None = None,
  nodeids: tuple[str, ...] = (),
  parallel: bool | None = None,
) -> None:
  do_python_tests(
    'zero',
    'command-plane-test',
    keyword_expression,
    marker_expression,
    nodeids,
    parallel,
  )


def do_check_history() -> None:
  lib.run_cmd('cog check', 'history')


def do_check_repo_policy() -> None:
  t = lib.Timer()
  try:
    repo_policy.check_repository_policy(os.getcwd())
  except repo_policy.RepositoryPolicyError as error:
    raise click.ClickException(str(error)) from error
  lib.status('repo-policy', t.duration())


def do_check_doc_lint() -> None:
  t = lib.Timer()
  try:
    doc_lint.check_documentation(os.getcwd())
  except (doc_lint.DocumentationLintError, RuntimeError) as error:
    raise click.ClickException(str(error)) from error
  lib.status('doc-lint', t.duration())


def do_check_type() -> None:
  lib.run_cmd(
    shlex.join(['ty', 'check', '--python', sys.prefix]),
    'type',
  )


def do_check_commit_message() -> None:
  t = lib.Timer()
  try:
    commit_message.check_commit_message(os.getcwd())
  except (
    commit_message.CommitMessageLintError,
    RuntimeError,
  ) as error:
    raise click.ClickException(str(error)) from error
  lib.status('commit-message', t.duration())


def do_generate_changelog() -> None:
  lib.run_cmd('git cliff', 'changelog')


# Fix Group
@lib.group_with_aliases(cli, aliases=['f'], invoke_without_command=True)
@click.pass_context
def fix(ctx: click.Context) -> None:
  """Format and lint the codebase."""
  if ctx.invoked_subcommand is None:
    t = lib.Timer()
    do_fix_fmt()
    do_fix_lint()
    lib.status('fix', t.duration())


@lib.command_with_aliases(fix, name='fmt', aliases=['f'])
def fmt_fix() -> None:
  """Run Cargo, Ruff, dprint, and nixfmt formatters."""
  do_fix_fmt()


@lib.command_with_aliases(
  fix,
  name='lint',
  aliases=['l'],
  context_settings=dict(ignore_unknown_options=True),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def lint_fix(args: tuple[str, ...]) -> None:
  """Run ruff fix, cargo fixit, and clippy."""
  do_fix_lint(args)


# Check Group
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
  if ctx.invoked_subcommand is None:
    t = lib.Timer()
    do_check_fmt()
    do_check_lint()
    do_check_type()
    do_check_repo_policy()
    do_check_doc_lint()
    do_ztest()
    do_ptest()
    do_btest()
    do_test()
    if not skip_commit:
      do_check_commit_message()
      do_check_history()
    lib.status('check', t.duration())


@lib.command_with_aliases(check, name='fmt', aliases=['f'])
def fmt_check() -> None:
  """Run Cargo, Ruff, dprint, and nixfmt format checks."""
  do_check_fmt()


@lib.command_with_aliases(check, name='doc', aliases=['d'])
def doc_check() -> None:
  """Run documentation lint."""
  do_check_doc_lint()


@lib.command_with_aliases(check, name='type')
def type_check() -> None:
  """Enforce ty checking across first-party Python code and tests."""
  do_check_type()


@lib.command_with_aliases(check, name='commit', aliases=['m'])
def commit_check() -> None:
  """Run commit-message line-length validation."""
  do_check_commit_message()


@lib.command_with_aliases(
  check,
  name='lint',
  aliases=['l'],
  context_settings=dict(ignore_unknown_options=True),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def lint_check(args: tuple[str, ...]) -> None:
  """Run ruff check and cargo clippy."""
  do_check_lint(args)


@lib.command_with_aliases(
  check, aliases=['bt'], context_settings=dict(ignore_unknown_options=True)
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def btest(args: tuple[str, ...]) -> None:
  """Run cargo test (bootstrap tests)."""
  do_btest(args)


@lib.command_with_aliases(check, aliases=['t'])
def test() -> None:
  """Run core language tests."""
  do_test()


@lib.command_with_aliases(
  check,
  name='ptest',
)
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
def project_test(
  keyword_expression: str | None,
  marker_expression: str | None,
  parallel: bool | None,
  nodeids: tuple[str, ...],
) -> None:
  """Run project tests with optional filters and parallel execution."""
  do_ptest(keyword_expression, marker_expression, nodeids, parallel)


@lib.command_with_aliases(
  check,
  name='ztest',
)
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
def command_plane_test(
  keyword_expression: str | None,
  marker_expression: str | None,
  parallel: bool | None,
  nodeids: tuple[str, ...],
) -> None:
  """Run command-plane tests with pytest filters."""
  do_ztest(keyword_expression, marker_expression, nodeids, parallel)


@lib.command_with_aliases(check, aliases=['h'])
def history() -> None:
  """Run cog check."""
  do_check_history()


@lib.command_with_aliases(check, aliases=['ch'])
def changelog() -> None:
  """Run git cliff."""
  do_generate_changelog()


# Run Command
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
  """Launch Antigravity Flash with the Pentagram workspace rules."""
  agent_runner.launch('agy-flash-yolo', args)


@lib.command_with_aliases(
  agent,
  name='agy-argon-yolo',
  aliases=['argon'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def agy_argon_agent(args: tuple[str, ...]) -> None:
  """Launch Antigravity Argon with the Pentagram workspace rules."""
  agent_runner.launch('agy-argon-yolo', args)


@lib.command_with_aliases(
  agent,
  name='agy-carbon-yolo',
  aliases=['carbon'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def agy_carbon_agent(args: tuple[str, ...]) -> None:
  """Launch Antigravity Carbon with the Pentagram workspace rules."""
  agent_runner.launch('agy-carbon-yolo', args)


@lib.command_with_aliases(cli, aliases=['w'])
def watch_cmd() -> None:
  """Watch for changes and run tests."""
  watch.run_watch()


cli.add_command(project_runner.project_group, name='proj')


if __name__ == '__main__':
  cli()
