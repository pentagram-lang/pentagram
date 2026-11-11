import shlex
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TypedDict

import click
import pytest
from click.testing import CliRunner

from zero import __main__ as command_plane

_FORMATTER_NODEID = (
  'test_main.py::test_formatter_help_names_each_repository_formatter'
)


class PythonTestOptions(TypedDict, total=False):
  keyword_expression: str
  marker_expression: str
  nodeids: tuple[str, ...]
  parallel: bool


def test_agent_alias_forwards_the_configured_agent_and_arguments(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane.agent_runner,
    'launch',
    lambda name, arguments: calls.append((name, arguments)),
  )

  result = CliRunner().invoke(
    command_plane.cli, ['agent', 'astra', '--resume', 'session']
  )

  assert result.exit_code == 0
  assert calls == [('codex-astra-yolo', ('--resume', 'session'))]


def test_agent_help_names_the_astra_alias() -> None:
  result = CliRunner().invoke(command_plane.cli, ['agent', '--help'])

  assert result.exit_code == 0
  assert 'astra' in result.output


def test_project_command_is_registered_on_the_root_cli() -> None:
  result = CliRunner().invoke(command_plane.cli, ['proj', '--help'])

  assert result.exit_code == 0
  assert 'Usage: cli proj [OPTIONS] COMMAND [ARGS]...' in result.output
  assert 'create' in result.output


@pytest.mark.parametrize('command', ('fix', 'check'), ids=('fix', 'check'))
def test_formatter_help_names_each_repository_formatter(
  command: str,
) -> None:
  result = CliRunner().invoke(
    command_plane.cli, [command, 'fmt', '--help']
  )

  assert result.exit_code == 0
  assert 'Cargo, Ruff, dprint, and nixfmt' in result.output


def test_fix_lint_cli_dispatches_python_and_package_scoped_rust_tools(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane.lib,
    'run_cmd',
    lambda command, label: calls.append((command, label)),
  )
  monkeypatch.setattr(
    command_plane.lib,
    'Timer',
    lambda: SimpleNamespace(duration=lambda: 0.5),
  )
  monkeypatch.setattr(command_plane.lib, 'status', lambda *_args: None)

  result = CliRunner().invoke(command_plane.cli, ['fix', 'lint', 'core'])

  assert result.exit_code == 0
  assert calls == [
    ('ruff check --fix', 'py-lint'),
    (
      'cargo fixit --allow-dirty --allow-staged -p core '
      '--all-targets --all-features',
      'rust-fixit',
    ),
    (
      'cargo clippy -p core --all-targets --all-features -- -D warnings',
      'clippy',
    ),
  ]


@pytest.mark.parametrize(
  ('skip_commit', 'expected'),
  [
    (
      True,
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
      ],
    ),
    (
      False,
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
    ),
  ],
  ids=('skip-commit', 'full-check'),
)
def test_check_runs_each_step_once_and_skips_only_commit_validation(
  monkeypatch: pytest.MonkeyPatch,
  skip_commit: bool,
  expected: list[str],
) -> None:
  calls = []
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
    monkeypatch.setattr(
      command_plane,
      name,
      lambda label=label: calls.append(label),
    )
  monkeypatch.setattr(
    command_plane.lib,
    'Timer',
    lambda: SimpleNamespace(duration=lambda: 0.5),
  )
  monkeypatch.setattr(command_plane.lib, 'status', lambda *_args: None)
  arguments = ['check', '--skip-commit'] if skip_commit else ['check']

  result = CliRunner().invoke(command_plane.cli, arguments)

  assert result.exit_code == 0
  assert calls == expected


@pytest.mark.parametrize(
  ('function', 'module', 'name', 'label'),
  [
    (
      command_plane.do_check_doc_lint,
      command_plane.doc_lint,
      'check_documentation',
      'doc-lint',
    ),
    (
      command_plane.do_check_commit_message,
      command_plane.commit_message,
      'check_commit_message',
      'commit-message',
    ),
  ],
  ids=('documentation', 'commit-message'),
)
def test_standalone_validators_report_their_own_timed_step(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  function: Callable[[], None],
  module: ModuleType,
  name: str,
  label: str,
) -> None:
  calls = []
  monkeypatch.chdir(tmp_path)
  monkeypatch.setattr(
    module, name, lambda root: calls.append(('check', root))
  )
  monkeypatch.setattr(
    command_plane.lib,
    'Timer',
    lambda: SimpleNamespace(duration=lambda: 0.75),
  )
  statuses = []
  monkeypatch.setattr(
    command_plane.lib,
    'status',
    lambda *args, **kwargs: statuses.append((args, kwargs)),
  )

  function()

  assert calls == [('check', str(tmp_path))]
  assert statuses == [((label, 0.75), {})]


def test_standalone_type_check_is_fail_closed(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[tuple[str, str]] = []
  monkeypatch.setattr(
    command_plane.lib,
    'run_cmd',
    lambda command, label: calls.append((command, label)),
  )

  command_plane.do_check_type()

  assert calls == [
    (
      shlex.join(['ty', 'check', '--python', command_plane.sys.prefix]),
      'type',
    )
  ]
  assert '--exit-zero' not in calls[0][0]


@pytest.mark.parametrize(
  ('filters', 'expected'),
  [
    (
      {},
      'python -m pytest -o testpaths=zero -n auto',
    ),
    (
      {'keyword_expression': 'storage and not slow'},
      "python -m pytest -o testpaths=zero -k 'storage and not slow'",
    ),
    (
      {'nodeids': (_FORMATTER_NODEID,)},
      f'python -m pytest -o testpaths=zero zero/{_FORMATTER_NODEID}',
    ),
    (
      {
        'marker_expression': 'integration',
        'nodeids': (_FORMATTER_NODEID,),
        'parallel': False,
      },
      'python -m pytest -o testpaths=zero -m integration '
      f'zero/{_FORMATTER_NODEID}',
    ),
  ],
  ids=(
    'unfiltered-parallel',
    'targeted-keyword',
    'nodeid',
    'marker-in-process',
  ),
)
def test_python_test_command_composes_filters_and_parallelism(
  monkeypatch: pytest.MonkeyPatch,
  filters: PythonTestOptions,
  expected: str,
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane.lib,
    'run_cmd',
    lambda *args: calls.append(args),
  )

  command_plane.do_ztest(**filters)

  assert calls == [(expected, 'command-plane-test')]


def test_project_test_command_composes_targeted_filters(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane.lib,
    'run_cmd',
    lambda *args: calls.append(args),
  )

  command_plane.do_ptest(
    keyword_expression='stage_dependencies',
    nodeids=(
      'test_lifecycle.py::'
      'test_stage_dependencies_gate_activation_and_reject_cycles',
    ),
    parallel=False,
  )

  assert calls == [
    (
      'python -m pytest -o testpaths=proj -k stage_dependencies '
      'proj/test_lifecycle.py::'
      'test_stage_dependencies_gate_activation_and_reject_cycles',
      'project-test',
    )
  ]


def test_project_test_command_runs_the_project_suite(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane.lib,
    'run_cmd',
    lambda *args: calls.append(args),
  )

  command_plane.do_ptest()

  assert calls == [
    ('python -m pytest -o testpaths=proj -n auto', 'project-test')
  ]


def test_project_test_cli_forwards_targeted_filters(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane,
    'do_ptest',
    lambda *args: calls.append(args),
  )

  result = CliRunner().invoke(
    command_plane.cli,
    [
      'check',
      'ptest',
      '-k',
      'lifecycle',
      '--nodeid',
      'test_lifecycle.py::test_stage_dependencies_gate_activation_and_reject_cycles',
      '--no-parallel',
    ],
  )

  assert result.exit_code == 0
  assert calls == [
    (
      'lifecycle',
      None,
      (
        'test_lifecycle.py::'
        'test_stage_dependencies_gate_activation_and_reject_cycles',
      ),
      False,
    )
  ]


@pytest.mark.parametrize(
  'nodeid',
  [
    '../proj/test_project.py::test_case',
    'README.md::test_case',
    'missing.py::test_case',
    'test_main.py::',
  ],
  ids=('outside-suite', 'wrong-extension', 'missing-file', 'missing-test'),
)
def test_python_test_command_rejects_invalid_node_ids(
  monkeypatch: pytest.MonkeyPatch, nodeid: str
) -> None:
  calls = []
  monkeypatch.setattr(
    command_plane.lib,
    'run_cmd',
    lambda *args: calls.append(args),
  )

  with pytest.raises(click.BadParameter):
    command_plane.do_ztest(nodeids=(nodeid,))

  assert calls == []
