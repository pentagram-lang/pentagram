from pathlib import Path

import pytest
from click.testing import CliRunner

from proj import cli
from proj.cli import project_group


@pytest.mark.parametrize(
  ('reference', 'expected'),
  [('release', 'release'), ('10', 10)],
  ids=('stage-name', 'stage-id'),
)
def test_stage_reference_preserves_names_and_converts_ids(
  monkeypatch: pytest.MonkeyPatch,
  reference: str,
  expected: str | int,
) -> None:
  calls: list[tuple[str, cli.StageReference]] = []

  def update_stage(
    root: Path,
    project_name: str,
    stage: cli.StageReference,
    **fields: object,
  ) -> None:
    calls.append((project_name, stage))

  monkeypatch.setattr(cli, 'update_stage', update_stage)
  result = CliRunner().invoke(
    project_group, ('stage', 'update', 'sample', reference)
  )

  assert result.exit_code == 0, result.output
  assert calls == [('sample', expected)]


@pytest.mark.parametrize(
  ('reference', 'expected'),
  [('active', 'active'), ('8', 8), (None, None)],
  ids=('active-keyword', 'goal-id', 'omitted-active-goal'),
)
def test_goal_reference_parses_its_supported_forms(
  monkeypatch: pytest.MonkeyPatch,
  reference: str | None,
  expected: str | int | None,
) -> None:
  calls: list[tuple[str, cli.GoalReference | None]] = []

  def read_goal(
    root: Path, name: str, goal: cli.GoalReference | None
  ) -> dict[str, object]:
    calls.append((name, goal))
    return {'goal': {'id': 8}}

  monkeypatch.setattr(cli, 'read_goal', read_goal)
  arguments = ('goal', 'show', 'sample')
  if reference is not None:
    arguments = (*arguments, reference)
  result = CliRunner().invoke(project_group, (*arguments, '--json'))

  assert result.exit_code == 0, result.output
  assert calls == [('sample', expected)]


def test_numeric_ids_and_quantities_reach_the_service_as_integers(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[tuple[str, int, int, int | None]] = []

  def read_task(
    root: Path,
    name: str,
    task: int,
    limit: int,
    since: int | None,
  ) -> dict[str, object]:
    calls.append((name, task, limit, since))
    return {'logs': []}

  monkeypatch.setattr(cli, 'read_task', read_task)
  result = CliRunner().invoke(
    project_group,
    (
      'task',
      'list-logs',
      'sample',
      '7',
      '--limit',
      '3',
      '--since',
      '-2',
      '--json',
    ),
  )

  assert result.exit_code == 0, result.output
  assert calls == [('sample', 7, 3, -2)]


@pytest.mark.parametrize(
  ('stage_token', 'stage', 'goal_token', 'goal', 'priority'),
  [
    ('release', 'release', 'active', 'active', -3),
    ('10', 10, '8', 8, 5),
  ],
  ids=('names-and-keyword', 'numeric-ids'),
)
def test_relationship_options_and_priority_use_domain_values(
  monkeypatch: pytest.MonkeyPatch,
  stage_token: str,
  stage: str | int,
  goal_token: str,
  goal: str | int,
  priority: int,
) -> None:
  calls: list[
    tuple[
      str,
      str,
      str,
      cli.StageReference | None,
      int,
      tuple[str, ...],
      cli.GoalReference | None,
    ]
  ] = []

  def add_task(
    root: Path,
    name: str,
    title: str,
    purpose: str,
    stage: cli.StageReference | None,
    priority: int,
    tags: tuple[str, ...],
    goal: cli.GoalReference | None,
    scope: str,
    exclusions: str,
    required_result: str,
    completion_evidence: str,
  ) -> int:
    calls.append((name, title, purpose, stage, priority, tags, goal))
    return 21

  monkeypatch.setattr(cli, 'add_task', add_task)
  result = CliRunner().invoke(
    project_group,
    (
      'task',
      'create',
      'sample',
      '--title',
      'New task',
      '--stage',
      stage_token,
      '--goal',
      goal_token,
      '--tag',
      'release candidate',
      '--priority',
      str(priority),
    ),
  )

  assert result.exit_code == 0, result.output
  assert calls == [
    (
      'sample',
      'New task',
      '',
      stage,
      priority,
      ('release candidate',),
      goal,
    )
  ]


def test_task_relationship_option_uses_an_integer_id(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[
    tuple[
      str,
      str,
      str,
      str,
      cli.StageReference | None,
      int | None,
      cli.GoalReference | None,
    ]
  ] = []

  def add_evidence(
    root: Path,
    name: str,
    claim: str,
    source: str,
    result: str,
    stage: cli.StageReference | None,
    task: int | None,
    goal: cli.GoalReference | None,
  ) -> int:
    calls.append((name, claim, source, result, stage, task, goal))
    return 22

  monkeypatch.setattr(cli, 'add_evidence', add_evidence)
  result = CliRunner().invoke(
    project_group,
    ('evidence', 'create', 'sample', '--claim', 'claim', '--task', '9'),
  )

  assert result.exit_code == 0, result.output
  assert calls == [('sample', 'claim', '', '', None, 9, None)]


def test_name_and_free_form_log_text_are_unchanged(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  message = '  leading\ntrailing  '
  kind = 'release-note'
  calls: list[tuple[str, int, str, str]] = []

  def append_task_log(
    root: Path,
    name: str,
    task: int,
    actual_message: str,
    actual_kind: str,
  ) -> None:
    calls.append((name, task, actual_message, actual_kind))

  monkeypatch.setattr(cli, 'append_task_log', append_task_log)
  result = CliRunner().invoke(
    project_group,
    ('task', 'add-log', 'sample', '9', message, '--kind', kind),
  )

  assert result.exit_code == 0, result.output
  assert calls == [('sample', 9, message, kind)]


@pytest.mark.parametrize(
  ('arguments', 'parameter', 'service'),
  [
    (
      ('task', 'activate', 'sample', 'not-an-id'),
      'TASK',
      'start_task',
    ),
    (('task', 'activate', 'sample', '0'), 'TASK', 'start_task'),
    (('stage', 'update', 'sample', '0'), 'STAGE', 'update_stage'),
    (
      ('stage', 'achieve', 'sample', 'release', '--evidence', '0'),
      '--evidence',
      'achieve_stage',
    ),
    (
      ('task', 'list-logs', 'sample', '1', '--limit', '0'),
      '--limit',
      'read_task',
    ),
    (
      ('goal', 'activate', 'sample', 'not-a-goal'),
      'GOAL',
      'activate_goal',
    ),
    (('goal', 'show', 'sample', '0'), '[GOAL]', 'read_goal'),
    (
      ('task', 'list', 'sample', '--status', 'unknown'),
      '--status',
      'read_tasks',
    ),
  ],
  ids=(
    'task-id-text',
    'task-id-zero',
    'stage-id-zero',
    'evidence-id-zero',
    'non-positive-limit',
    'invalid-goal-reference',
    'goal-id-zero',
    'invalid-status-choice',
  ),
)
def test_invalid_arguments_fail_before_service_operation(
  monkeypatch: pytest.MonkeyPatch,
  arguments: tuple[str, ...],
  parameter: str,
  service: str,
) -> None:
  calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

  def reject_call(*args: object, **kwargs: object) -> None:
    calls.append((args, kwargs))

  monkeypatch.setattr(cli, service, reject_call)
  result = CliRunner().invoke(project_group, arguments)

  assert result.exit_code == 2
  assert f"Invalid value for '{parameter}'" in result.output
  assert calls == []


def test_help_exposes_numeric_argument_names() -> None:
  result = CliRunner().invoke(
    project_group, ('task', 'list-logs', '--help')
  )

  assert result.exit_code == 0
  assert 'TASK' in result.output
  assert '--limit LIMIT' in result.output
  assert '--since UNIX_TIMESTAMP' in result.output


def test_help_distinguishes_optional_and_required_goal_references() -> (
  None
):
  optional = CliRunner().invoke(project_group, ('goal', 'show', '--help'))
  required = CliRunner().invoke(
    project_group, ('goal', 'activate', '--help')
  )

  assert optional.exit_code == 0
  assert 'NAME [GOAL]' in optional.output
  assert required.exit_code == 0
  assert 'NAME GOAL' in required.output
