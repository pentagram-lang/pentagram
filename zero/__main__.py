#!/usr/bin/env python3
import os

import click

from proj import project as project_runner
from zero import agent as agent_runner
from zero import boot, commit_message, doc_lint, lib, repo_policy, watch

# Always run from the project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.group(cls=lib.AliasedGroup, invoke_without_command=True)
@click.option('-w', '--watch', is_flag=True, help='Run in watch mode.')
@click.pass_context
def cli(ctx, watch):
  """Pentagram task runner."""
  if ctx.invoked_subcommand is None and watch:
    ctx.invoke(watch_cmd)
  pass


def do_fix_fmt():
  t = lib.Timer()
  lib.run_cmd('cargo fmt', 'rust-fmt')
  lib.run_cmd('ruff format', 'py-fmt')
  lib.run_cmd('dprint fmt', 'dprint')
  lib.run_cmd('nixfmt *.nix nix/*.nix', 'nix-fmt')
  lib.status('fix-fmt', t.duration())


def do_check_fmt():
  t = lib.Timer()
  lib.run_cmd('cargo fmt -- --check', 'rust-fmt')
  lib.run_cmd('ruff format --check', 'py-fmt')
  lib.run_cmd('dprint check', 'dprint')
  lib.run_cmd('nixfmt --check *.nix nix/*.nix', 'nix-fmt')
  lib.status('check-fmt', t.duration())


def do_fix_lint(args=None):
  if args is None:
    args = []

  t = lib.Timer()
  pos, extras = lib.parse_args(args, max_pos=1)

  # Python Lint (Fix)
  lib.run_cmd('ruff check --fix', 'py-lint')

  # Rust Fixit
  pkg = pos[0] if pos else None
  fix_cmd = lib.get_cargo_fix_cmd(package=pkg)
  lib.run_cmd(' '.join(fix_cmd), 'rust-fixit')

  # Rust Clippy
  clippy_cmd = lib.get_cargo_clippy_cmd(package=pkg)
  lib.run_cmd(' '.join(clippy_cmd), 'clippy')
  lib.status('fix-lint', t.duration())


def do_check_lint(args=None):
  if args is None:
    args = []

  t = lib.Timer()
  pos, extras = lib.parse_args(args, max_pos=1)
  pkg = pos[0] if pos else None

  # Python Lint (Check)
  lib.run_cmd('ruff check', 'py-lint')

  # Rust Clippy
  clippy_cmd = lib.get_cargo_clippy_cmd(package=pkg)
  lib.run_cmd(' '.join(clippy_cmd), 'clippy')
  lib.status('check-lint', t.duration())


def do_btest(args=None):
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

  lib.run_cmd(' '.join(test_cmd), 'btest')


def do_test():
  lib.run_cmd('cargo run -p boot_shell -- test core', 'test')


def do_ptest():
  lib.run_cmd(
    'python -m unittest discover -s proj -p "*_test.py"',
    'project-test',
  )


def do_ztest():
  lib.run_cmd(
    'python -m unittest discover -s zero -p "*_test.py"',
    'command-plane-test',
  )


def do_check_history():
  lib.run_cmd('cog check', 'history')


def do_check_repo_policy():
  t = lib.Timer()
  try:
    repo_policy.check_repository_policy(os.getcwd())
  except repo_policy.RepositoryPolicyError as error:
    raise click.ClickException(str(error)) from error
  lib.status('repo-policy', t.duration())


def do_check_doc_lint():
  t = lib.Timer()
  try:
    doc_lint.check_documentation(os.getcwd())
  except (doc_lint.DocumentationLintError, RuntimeError) as error:
    raise click.ClickException(str(error)) from error
  lib.status('doc-lint', t.duration())


def do_check_commit_message():
  t = lib.Timer()
  try:
    commit_message.check_commit_message(os.getcwd())
  except (
    commit_message.CommitMessageLintError,
    RuntimeError,
  ) as error:
    raise click.ClickException(str(error)) from error
  lib.status('commit-message', t.duration())


def do_generate_changelog():
  lib.run_cmd('git cliff', 'changelog')


# Fix Group
@lib.group_with_aliases(cli, aliases=['f'], invoke_without_command=True)
@click.pass_context
def fix(ctx):
  """Format and lint the codebase."""
  if ctx.invoked_subcommand is None:
    t = lib.Timer()
    do_fix_fmt()
    do_fix_lint()
    lib.status('fix', t.duration())


@lib.command_with_aliases(fix, name='fmt', aliases=['f'])
def fmt_fix():
  """Run cargo fmt and ruff format."""
  do_fix_fmt()


@lib.command_with_aliases(
  fix,
  name='lint',
  aliases=['l'],
  context_settings=dict(ignore_unknown_options=True),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def lint_fix(args):
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
def check(ctx, skip_commit):
  """Format, lint, test, and validate history."""
  if ctx.invoked_subcommand is None:
    t = lib.Timer()
    do_check_fmt()
    do_check_lint()
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
def fmt_check():
  """Run cargo fmt --check and ruff format --check."""
  do_check_fmt()


@lib.command_with_aliases(check, name='doc', aliases=['d'])
def doc_check():
  """Run documentation lint."""
  do_check_doc_lint()


@lib.command_with_aliases(check, name='commit', aliases=['m'])
def commit_check():
  """Run commit-message line-length validation."""
  do_check_commit_message()


@lib.command_with_aliases(
  check,
  name='lint',
  aliases=['l'],
  context_settings=dict(ignore_unknown_options=True),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def lint_check(args):
  """Run ruff check and cargo clippy."""
  do_check_lint(args)


@lib.command_with_aliases(
  check, aliases=['bt'], context_settings=dict(ignore_unknown_options=True)
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def btest(args):
  """Run cargo test (bootstrap tests)."""
  do_btest(args)


@lib.command_with_aliases(check, aliases=['t'])
def test():
  """Run core language tests."""
  do_test()


@lib.command_with_aliases(check, name='ptest')
def project_test():
  """Run project control-plane tests."""
  do_ptest()


@lib.command_with_aliases(check, name='ztest')
def command_plane_test():
  """Run command-plane tests."""
  do_ztest()


@lib.command_with_aliases(check, aliases=['h'])
def history():
  """Run cog check."""
  do_check_history()


@lib.command_with_aliases(check, aliases=['ch'])
def changelog():
  """Run git cliff."""
  do_generate_changelog()


# Run Command
@lib.command_with_aliases(
  cli,
  aliases=['r'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def run(args):
  """Run the boot_shell (boot/shell)."""
  boot.run_shell(args)


@lib.group_with_aliases(cli, aliases=['a'])
def agent():
  """Launch a Pentagram-configured coding agent."""


@lib.command_with_aliases(
  agent,
  name='codex-luna-yolo',
  aliases=['luna', 'cluna'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def codex_luna_agent(args):
  """Launch Codex Luna with the Pentagram system prompt."""
  agent_runner.launch('codex-luna-yolo', args)


@lib.command_with_aliases(
  agent,
  name='codex-sol-yolo',
  aliases=['sol', 'csol'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def codex_sol_agent(args):
  """Launch Codex Sol with the Pentagram system prompt."""
  agent_runner.launch('codex-sol-yolo', args)


@lib.command_with_aliases(
  agent,
  name='claude-sonnet-yolo',
  aliases=['sonnet', 'csonnet'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def claude_sonnet_agent(args):
  """Launch Claude Sonnet with the Pentagram system prompt."""
  agent_runner.launch('claude-sonnet-yolo', args)


@lib.command_with_aliases(
  agent,
  name='claude-fable-yolo',
  aliases=['fable', 'cfable'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def claude_fable_agent(args):
  """Launch Claude Fable with the Pentagram system prompt."""
  agent_runner.launch('claude-fable-yolo', args)


@lib.command_with_aliases(
  agent,
  name='agy-flash-yolo',
  aliases=['flash', 'aflash'],
  context_settings=dict(ignore_unknown_options=True, help_option_names=[]),
)
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
def agy_agent(args):
  """Launch Antigravity with the Pentagram workspace rules."""
  agent_runner.launch('agy-flash-yolo', args)


@lib.command_with_aliases(cli, aliases=['w'])
def watch_cmd():
  """Watch for changes and run tests."""
  watch.run_watch()


cli.add_command(project_runner.project_group, name='proj')


if __name__ == '__main__':
  cli()
