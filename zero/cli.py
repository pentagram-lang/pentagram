from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath

import click

from proj.cli import project_group
from zero.agent import launch as launch_agent
from zero.agent.dispatch import AGENT_CONFIGURATIONS
from zero.boot import run_boot
from zero.commit_message import check_commit_message, read_head_message
from zero.doc_lint import check_docs
from zero.lib import (
  AliasedGroup,
  Diagnostic,
  Runner,
  cargo_package_args,
  find_repo_root,
  nix_files,
  run_cmd,
  run_timed_cmd,
  timed_step,
)
from zero.repo_policy import check_repo_policy
from zero.watch import run_watch


def _repo(ctx: click.Context) -> Path:
  if isinstance(ctx.obj, Path):
    return ctx.obj
  return find_repo_root()


def _exit_on_fail(ok: bool) -> None:
  if not ok:
    sys.exit(1)


def _run_diag_check(
  label: str, check_fn: Callable[[], list[Diagnostic]]
) -> bool:
  def _step() -> bool:
    try:
      diags = check_fn()
    except click.ClickException as err:
      click.echo(f'Error: {err.format_message()}', err=True)
      return False
    for diag in diags:
      click.echo(diag.format(), err=True)
    return not diags

  return timed_step(label, _step)


def _fmt_steps(repo: Path, *, check: bool) -> list[tuple[str, list[str]]]:
  steps: list[tuple[str, list[str]]] = [
    ('rust-fmt', ['cargo', 'fmt', *(['--', '--check'] if check else [])]),
    ('py-fmt', ['ruff', 'format', *(['--check'] if check else [])]),
    ('dprint', ['dprint', 'check' if check else 'fmt']),
  ]
  nix_paths = nix_files(repo)
  if nix_paths:
    nix_cmd = ['nixfmt', *(['--check'] if check else []), '--', *nix_paths]
    steps.append(('nix-fmt', nix_cmd))
  return steps


def do_fix_fmt(repo: Path, runner: Runner = run_cmd) -> bool:
  def _step() -> bool:
    try:
      steps = _fmt_steps(repo, check=False)
    except click.ClickException as err:
      click.echo(f'Error: {err.format_message()}', err=True)
      return False
    return all(
      run_timed_cmd(label, cmd, cwd=repo, runner=runner)
      for label, cmd in steps
    )

  return timed_step('fix-fmt', _step)


def do_fix_lint(
  repo: Path, package: str | None = None, runner: Runner = run_cmd
) -> bool:
  pkg_fixit = ['-p', package] if package else ['--workspace']
  steps: list[tuple[str, list[str]]] = [
    ('py-lint', ['ruff', 'check', '--fix']),
    (
      'fixit',
      [
        'cargo',
        'fixit',
        '--clippy',
        '--broken-code',
        '--allow-dirty',
        '--allow-staged',
        '--all-targets',
        '--all-features',
        *pkg_fixit,
      ],
    ),
    (
      'clippy',
      [
        'cargo',
        'clippy',
        *cargo_package_args(package),
        '--all-targets',
        '--all-features',
        '--',
        '-D',
        'warnings',
      ],
    ),
  ]
  return timed_step(
    'fix-lint',
    lambda: all(
      run_timed_cmd(label, cmd, cwd=repo, runner=runner)
      for label, cmd in steps
    ),
  )


def do_fix_all(repo: Path, runner: Runner = run_cmd) -> bool:
  return timed_step(
    'fix',
    lambda: do_fix_fmt(repo, runner) and do_fix_lint(repo, None, runner),
  )


def do_check_fmt(repo: Path, runner: Runner = run_cmd) -> bool:
  def _step() -> bool:
    try:
      steps = _fmt_steps(repo, check=True)
    except click.ClickException as err:
      click.echo(f'Error: {err.format_message()}', err=True)
      return False
    return all(
      [
        run_timed_cmd(label, cmd, cwd=repo, runner=runner)
        for label, cmd in steps
      ]
    )

  return timed_step('check-fmt', _step)


def do_check_lint(
  repo: Path, package: str | None = None, runner: Runner = run_cmd
) -> bool:
  steps: list[tuple[str, list[str]]] = [
    ('py-lint', ['ruff', 'check']),
    (
      'clippy',
      [
        'cargo',
        'clippy',
        *cargo_package_args(package),
        '--all-targets',
        '--all-features',
        '--',
        '-D',
        'warnings',
      ],
    ),
  ]
  return timed_step(
    'check-lint',
    lambda: all(
      [
        run_timed_cmd(label, cmd, cwd=repo, runner=runner)
        for label, cmd in steps
      ]
    ),
  )


def do_check_type(repo: Path, runner: Runner = run_cmd) -> bool:
  return run_timed_cmd(
    'type',
    ['ty', 'check', '--python', sys.prefix],
    cwd=repo,
    runner=runner,
  )


def do_check_policy(repo: Path) -> bool:
  return _run_diag_check('repo-policy', lambda: check_repo_policy(repo))


def do_check_doc(repo: Path) -> bool:
  return _run_diag_check('doc-lint', lambda: check_docs(repo))


def do_check_commit(repo: Path) -> bool:
  return _run_diag_check(
    'commit-msg', lambda: check_commit_message(read_head_message(repo))
  )


_SUITE_DIRS = {'ztest': 'zero', 'ptest': 'proj'}


def validate_nodeid(suite_dir: str, raw: str) -> str:
  rel_file, sep, selector = raw.partition('::')
  if not sep or not rel_file or not selector:
    raise click.ClickException(f'Invalid node ID: {raw!r}')
  rel_path = PurePosixPath(rel_file)
  if (
    rel_path.is_absolute()
    or '..' in rel_path.parts
    or not rel_file.endswith('_test.py')
  ):
    raise click.ClickException(f'Invalid node ID: {raw!r}')
  return f'{suite_dir}/{rel_path.as_posix()}::{selector}'


def do_check_pytest(
  suite: str,
  repo: Path,
  *,
  keyword: str | None = None,
  marker: str | None = None,
  nodeids: Sequence[str] = (),
  parallel: bool | None = None,
  runner: Runner = run_cmd,
) -> bool:
  suite_dir = _SUITE_DIRS[suite]
  rewritten = [validate_nodeid(suite_dir, nid) for nid in nodeids]
  filtered = bool(keyword or marker or rewritten)
  use_parallel = (not filtered) if parallel is None else parallel
  cmd = [
    'pytest',
    *(['-n', 'auto'] if use_parallel else []),
    *(['-k', keyword] if keyword else []),
    *(['-m', marker] if marker else []),
    *(rewritten or [suite_dir]),
  ]
  return run_timed_cmd(suite, cmd, cwd=repo, runner=runner)


def do_check_btest(
  repo: Path,
  package: str | None = None,
  test_name: str | None = None,
  *,
  nocapture: bool = False,
  exact: bool = False,
  runner: Runner = run_cmd,
) -> bool:
  extra = [
    *(['--nocapture'] if nocapture else []),
    *(['--exact'] if exact else []),
  ]
  cmd = [
    'cargo',
    'test',
    *cargo_package_args(package),
    *([test_name] if test_name else []),
    *(['--', *extra] if extra else []),
  ]
  return run_timed_cmd('btest', cmd, cwd=repo, runner=runner)


def do_check_test(repo: Path, runner: Runner = run_cmd) -> bool:
  return run_timed_cmd(
    'test',
    ['cargo', 'run', '-p', 'boot_shell', '--', 'test', 'core'],
    cwd=repo,
    runner=runner,
  )


def do_check_history(repo: Path, runner: Runner = run_cmd) -> bool:
  return run_timed_cmd(
    'history', ['cog', 'check'], cwd=repo, runner=runner
  )


def do_check_changelog(repo: Path, runner: Runner = run_cmd) -> bool:
  return run_timed_cmd(
    'changelog', ['git', 'cliff'], cwd=repo, runner=runner
  )


def do_check_all(
  repo: Path, *, skip_commit: bool = False, runner: Runner = run_cmd
) -> bool:
  def _step() -> bool:
    results = [
      do_check_fmt(repo, runner),
      do_check_lint(repo, runner=runner),
      do_check_type(repo, runner),
      do_check_policy(repo),
      do_check_doc(repo),
      do_check_pytest('ztest', repo, runner=runner),
      do_check_pytest('ptest', repo, runner=runner),
      do_check_btest(repo, runner=runner),
      do_check_test(repo, runner),
    ]
    if not skip_commit:
      results.append(do_check_commit(repo))
      results.append(do_check_history(repo, runner))
    return all(results)

  return timed_step('check', _step)


@click.group(
  cls=AliasedGroup,
  name='0',
  aliases={
    'f': 'fix',
    'c': 'check',
    'r': 'run',
    'p': 'proj',
    'a': 'agent',
    'w': 'watch',
  },
  invoke_without_command=True,
)
@click.option('-w', '--watch', is_flag=True)
@click.pass_context
def cli(ctx: click.Context, watch: bool) -> None:
  if not isinstance(ctx.obj, Path):
    ctx.obj = find_repo_root()
  if watch and ctx.invoked_subcommand is not None:
    raise click.ClickException(
      '--watch cannot be combined with a subcommand.'
    )
  if watch:
    _exit_on_fail(run_watch(_repo(ctx)) == 0)
    return
  if ctx.invoked_subcommand is None:
    click.echo(ctx.get_help())


@cli.command('watch')
@click.pass_context
def watch_cmd(ctx: click.Context) -> None:
  _exit_on_fail(run_watch(_repo(ctx)) == 0)


@cli.command('help')
@click.pass_context
def help_cmd(ctx: click.Context) -> None:
  assert ctx.parent is not None
  click.echo(ctx.parent.get_help())


cli.add_command(project_group, name='proj')

_AGENT_ALIASES = {
  'flash': 'agy-flash-yolo',
  'argon': 'agy-argon-yolo',
  'carbon': 'agy-carbon-yolo',
  'luna': 'codex-luna-yolo',
  'sol': 'codex-sol-yolo',
  'astra': 'codex-astra-yolo',
  'sonnet': 'claude-sonnet-yolo',
  'fable': 'claude-fable-yolo',
}


@cli.group('agent', cls=AliasedGroup, aliases=_AGENT_ALIASES)
def agent_group() -> None:
  pass


class _PassthroughCommand(click.Command):
  def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
    ctx.args = list(args)
    return []


def _make_agent_command(target_name: str) -> click.Command:
  @click.command(
    target_name,
    cls=_PassthroughCommand,
  )
  @click.pass_context
  def _agent_cmd(ctx: click.Context) -> None:
    launch_agent(target_name, tuple(ctx.args), repo=_repo(ctx))

  return _agent_cmd


for _target in AGENT_CONFIGURATIONS:
  agent_group.add_command(_make_agent_command(_target))


@cli.command('run', cls=_PassthroughCommand)
@click.pass_context
def run_cmd_entry(ctx: click.Context) -> None:
  run_boot(tuple(ctx.args))


@cli.group(
  'fix',
  cls=AliasedGroup,
  aliases={'f': 'fmt', 'l': 'lint'},
  invoke_without_command=True,
)
@click.pass_context
def fix_group(ctx: click.Context) -> None:
  if ctx.invoked_subcommand is None:
    _exit_on_fail(do_fix_all(_repo(ctx)))


@fix_group.command('fmt')
@click.pass_context
def fix_fmt_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_fix_fmt(_repo(ctx)))


@fix_group.command('lint')
@click.argument('package', required=False)
@click.pass_context
def fix_lint_cmd(ctx: click.Context, package: str | None) -> None:
  _exit_on_fail(do_fix_lint(_repo(ctx), package))


@cli.group(
  'check',
  cls=AliasedGroup,
  aliases={
    'f': 'fmt',
    'l': 'lint',
    'p': 'policy',
    'd': 'doc',
    'bt': 'btest',
    't': 'test',
    'm': 'commit',
    'h': 'history',
    'ch': 'changelog',
  },
  invoke_without_command=True,
)
@click.option('-s', '--skip-commit', is_flag=True)
@click.pass_context
def check_group(ctx: click.Context, skip_commit: bool) -> None:
  if skip_commit and ctx.invoked_subcommand is not None:
    raise click.ClickException(
      '--skip-commit cannot be combined with a subcommand.'
    )
  if ctx.invoked_subcommand is None:
    _exit_on_fail(do_check_all(_repo(ctx), skip_commit=skip_commit))


@check_group.command('fmt')
@click.pass_context
def check_fmt_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_fmt(_repo(ctx)))


@check_group.command('lint')
@click.argument('package', required=False)
@click.pass_context
def check_lint_cmd(ctx: click.Context, package: str | None) -> None:
  _exit_on_fail(do_check_lint(_repo(ctx), package))


@check_group.command('type')
@click.pass_context
def check_type_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_type(_repo(ctx)))


@check_group.command('policy')
@click.pass_context
def check_policy_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_policy(_repo(ctx)))


@check_group.command('doc')
@click.pass_context
def check_doc_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_doc(_repo(ctx)))


def _pytest_command(suite: str) -> click.Command:
  @click.command(suite)
  @click.option('-k', 'keyword', default=None)
  @click.option('-m', 'marker', default=None)
  @click.option('--nodeid', 'nodeids', multiple=True)
  @click.option('--parallel/--no-parallel', default=None)
  @click.pass_context
  def _cmd(
    ctx: click.Context,
    keyword: str | None,
    marker: str | None,
    nodeids: tuple[str, ...],
    parallel: bool | None,
  ) -> None:
    _exit_on_fail(
      do_check_pytest(
        suite,
        _repo(ctx),
        keyword=keyword,
        marker=marker,
        nodeids=nodeids,
        parallel=parallel,
      )
    )

  return _cmd


check_group.add_command(_pytest_command('ztest'), name='ztest')
check_group.add_command(_pytest_command('ptest'), name='ptest')


@check_group.command('btest')
@click.argument('package', required=False)
@click.argument('test_name', required=False)
@click.option('-n', '--nocapture', is_flag=True)
@click.option('--exact', is_flag=True)
@click.pass_context
def check_btest_cmd(
  ctx: click.Context,
  package: str | None,
  test_name: str | None,
  nocapture: bool,
  exact: bool,
) -> None:
  _exit_on_fail(
    do_check_btest(
      _repo(ctx),
      package,
      test_name,
      nocapture=nocapture,
      exact=exact,
    )
  )


@check_group.command('test')
@click.pass_context
def check_test_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_test(_repo(ctx)))


@check_group.command('commit')
@click.pass_context
def check_commit_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_commit(_repo(ctx)))


@check_group.command('history')
@click.pass_context
def check_history_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_history(_repo(ctx)))


@check_group.command('changelog')
@click.pass_context
def check_changelog_cmd(ctx: click.Context) -> None:
  _exit_on_fail(do_check_changelog(_repo(ctx)))


def main(argv: Sequence[str] | None = None) -> None:
  try:
    repo = find_repo_root()
    prev = Path.cwd()
    os.chdir(repo)
  except click.ClickException as err:
    err.show()
    sys.exit(err.exit_code)
  except OSError as err:
    click.ClickException(str(err)).show()
    sys.exit(1)
  try:
    cli.main(
      args=list(argv) if argv is not None else None,
      prog_name='0',
      obj=repo,
    )
  finally:
    os.chdir(prev)
