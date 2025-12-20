#!/usr/bin/env python3
import os
import sys

import click

# Add the task directory to path to import boot and lib
sys.path.append(os.path.join(os.path.dirname(__file__), 'task'))
import lib
import watch

import boot

# Always run from the project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))


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
  lib.run_cmd('nixfmt **/*.nix', 'nix-fmt')
  lib.status('fix-fmt', t.duration())


def do_check_fmt():
  t = lib.Timer()
  lib.run_cmd('cargo fmt -- --check', 'rust-fmt')
  lib.run_cmd('ruff format --check', 'py-fmt')
  lib.run_cmd('dprint check', 'dprint')
  lib.run_cmd('nixfmt --check **/*.nix', 'nix-fmt')
  lib.status('check-fmt', t.duration())


def do_fix_lint(args=None):
  if args is None:
    args = []

  t = lib.Timer()
  pos, extras = lib.parse_args(args, max_pos=1)

  # Python Lint (Fix)
  lib.run_cmd('ruff check --fix', 'py-lint')

  # Rust Fixit
  fix_base = ['cargo', 'fixit', '--allow-dirty', '--allow-staged']
  fix_cmd = lib.build_cargo_cmd(fix_base, pos, extras)
  lib.run_cmd(' '.join(fix_cmd), 'rust-fixit')

  # Rust Clippy
  clippy_base = ['cargo', 'clippy']
  clippy_cmd = lib.build_cargo_cmd(clippy_base, pos, extras)
  lib.ensure_clippy_fails_on_warnings(clippy_cmd)
  lib.run_cmd(' '.join(clippy_cmd), 'clippy')
  lib.status('fix-lint', t.duration())


def do_check_lint(args=None):
  if args is None:
    args = []

  t = lib.Timer()
  pos, extras = lib.parse_args(args, max_pos=1)

  # Python Lint (Check)
  lib.run_cmd('ruff check', 'py-lint')

  # Rust Clippy
  clippy_base = ['cargo', 'clippy']
  clippy_cmd = lib.build_cargo_cmd(clippy_base, pos, extras)
  lib.ensure_clippy_fails_on_warnings(clippy_cmd)
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

  test_base = ['cargo', 'test']
  test_cmd = lib.build_cargo_cmd(test_base, pos, extras)

  if nocapture:
    # Ensure --nocapture is passed to the test binary (after --)
    if '--' in test_cmd:
      test_cmd.append('--nocapture')
    else:
      test_cmd.extend(['--', '--nocapture'])

  lib.run_cmd(' '.join(test_cmd), 'btest')


def do_test():
  lib.run_cmd('cargo run -p boot_shell -- test core', 'test')


def do_check_history():
  lib.run_cmd('cog check', 'history')


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


@lib.command_with_aliases(fix, aliases=['f'])
def fmt_fix():
  """Run cargo fmt and ruff format."""
  do_fix_fmt()


@lib.command_with_aliases(
  fix, aliases=['l'], context_settings=dict(ignore_unknown_options=True)
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
  help='Skip commit history validation.',
)
@click.pass_context
def check(ctx, skip_commit):
  """Format, lint, test, and validate history."""
  if ctx.invoked_subcommand is None:
    t = lib.Timer()
    do_check_fmt()
    do_check_lint()
    do_btest()
    do_test()
    if not skip_commit:
      do_check_history()
    lib.status('check', t.duration())


@lib.command_with_aliases(check, aliases=['f'])
def fmt_check():
  """Run cargo fmt --check and ruff format --check."""
  do_check_fmt()


@lib.command_with_aliases(
  check, aliases=['l'], context_settings=dict(ignore_unknown_options=True)
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


@lib.command_with_aliases(cli, aliases=['w'])
def watch_cmd():
  """Watch for changes and run tests."""
  watch.run_watch()


if __name__ == '__main__':
  cli()
