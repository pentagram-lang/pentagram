import json
import shlex
from pathlib import Path

import pytest
from click.testing import CliRunner

from proj import cli
from proj.cli import project_group

COMMANDS = (
  (
    (),
    (
      'archive',
      'blocker',
      'create',
      'decision',
      'evidence',
      'goal',
      'handoff',
      'list',
      'show',
      'stage',
      'task',
      'update',
    ),
  ),
  (
    ('goal',),
    (
      'achieve',
      'activate',
      'block',
      'cancel',
      'copy',
      'create',
      'list',
      'reopen',
      'show',
      'text',
    ),
  ),
  (
    ('stage',),
    (
      'achieve',
      'add-dependency',
      'create',
      'list',
      'remove-dependency',
      'update',
    ),
  ),
  (
    ('task',),
    (
      'activate',
      'add-log',
      'add-tag',
      'block',
      'cancel',
      'complete',
      'create',
      'list',
      'list-logs',
      'ready',
      'remove-tag',
      'reopen',
      'show',
      'update',
    ),
  ),
  (('decision',), ('create', 'list')),
  (('blocker',), ('create', 'list', 'resolve')),
  (('evidence',), ('create', 'list')),
)


def _help_commands(output: str) -> tuple[str, ...]:
  commands: list[str] = []
  reading_commands = False
  for line in output.splitlines():
    if line == 'Commands:':
      reading_commands = True
      continue
    if reading_commands and not line:
      break
    if (
      reading_commands
      and line.startswith('  ')
      and not line.startswith('   ')
    ):
      commands.append(line.strip().split()[0])
  return tuple(commands)


@pytest.mark.parametrize(('subject', 'expected'), COMMANDS)
def test_command_help_matches_the_canonical_inventory(
  subject: tuple[str, ...], expected: tuple[str, ...]
) -> None:
  result = CliRunner().invoke(project_group, (*subject, '--help'))

  assert result.exit_code == 0
  assert _help_commands(result.output) == expected


@pytest.mark.parametrize(
  ('arguments', 'description'),
  [
    (
      ('goal', 'create', '--help'),
      'Create and activate a goal, handing off active goal-linked work.',
    ),
    (
      ('goal', 'activate', '--help'),
      'Activate a pending goal, handing off active goal-linked work.',
    ),
    (
      ('goal', 'reopen', '--help'),
      'Reopen a repaired goal, handing off active goal-linked work.',
    ),
    (
      ('stage', 'create', '--help'),
      'Create a stage with an outcome contract.',
    ),
    (
      ('task', 'create', '--help'),
      'Create a pending project task.',
    ),
    (
      ('decision', 'create', '--help'),
      'Create a project decision record.',
    ),
    (
      ('blocker', 'create', '--help'),
      'Create a blocker for a task or goal.',
    ),
    (
      ('evidence', 'create', '--help'),
      'Create a project evidence record.',
    ),
    (
      ('task', 'ready', '--help'),
      'List eligible pending tasks even when one task is active.',
    ),
    (
      ('task', 'activate', '--help'),
      'Activate an eligible task, returning any current task to pending.',
    ),
    (
      ('stage', 'add-dependency', '--help'),
      'Add a prerequisite edge to a stage.',
    ),
    (
      ('stage', 'remove-dependency', '--help'),
      'Remove one stage dependency when dependent work is inactive.',
    ),
    (
      ('task', 'add-log', '--help'),
      'Append an entry to a task log.',
    ),
    (
      ('task', 'list-logs', '--help'),
      "List a task's log entries.",
    ),
    (
      ('task', 'add-tag', '--help'),
      'Add metadata tags to a task.',
    ),
    (
      ('task', 'remove-tag', '--help'),
      'Remove metadata tags from a task.',
    ),
    (
      ('blocker', 'resolve', '--help'),
      'Resolve a blocker, handing off work on final goal recovery.',
    ),
  ],
  ids=(
    'goal-create',
    'goal-activate',
    'goal-reopen',
    'stage-create',
    'task-create',
    'decision-create',
    'blocker-create',
    'evidence-create',
    'task-ready',
    'task-activate',
    'stage-add-dependency',
    'stage-remove-dependency',
    'task-add-log',
    'task-list-logs',
    'task-add-tag',
    'task-remove-tag',
    'blocker-resolve',
  ),
)
def test_command_help_describes_its_operation(
  arguments: tuple[str, ...], description: str
) -> None:
  result = CliRunner().invoke(project_group, arguments)

  assert result.exit_code == 0
  assert description in result.output


def test_generated_task_log_command_uses_list_logs(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  expected_logs: list[dict[str, int | str]] = [
    {'occurred_at': 1, 'kind': 'note', 'message': 'Last task note'}
  ]
  observed_calls: list[tuple[str, int, int, int | None]] = []

  def read_task(
    root: Path,
    name: str,
    task: int,
    limit: int,
    since: int | None,
  ) -> dict[str, object]:
    observed_calls.append((name, task, limit, since))
    return {'logs': expected_logs}

  monkeypatch.setattr(cli, 'read_task', read_task)
  data: cli.HandoffRetrievalInput = {
    'project': {'name': 'sample'},
    'goal': None,
    'task': {'id': 7},
    'stage': None,
    'focus': {'kind': 'task', 'id': 7},
    'pages': {
      'decisions': {'total': 0},
      'evidence': {'total': 0},
      'task_log': {'total': 8},
    },
  }
  retrieval_command = cli._handoff_retrieval_commands(data)['task_log']
  assert retrieval_command is not None
  arguments = shlex.split(retrieval_command)
  result = CliRunner().invoke(project_group, arguments[2:])

  assert result.exit_code == 0
  assert json.loads(result.output) == expected_logs
  assert observed_calls == [('sample', 7, 8, None)]


def test_generated_path_command_uses_handoff_json(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  expected_handoff = {'path': '.tmp/sample.sqlite3'}

  def read_handoff(root: Path, name: str) -> dict[str, object]:
    assert name == 'sample'
    return {}

  monkeypatch.setattr(cli, 'read_handoff', read_handoff)
  monkeypatch.setattr(cli, '_handoff_json', lambda data: expected_handoff)
  retrieval_command = cli._handoff_full_value_command(
    None, 'sample', ('path',)
  )
  arguments = shlex.split(retrieval_command)
  result = CliRunner().invoke(project_group, arguments[2:])

  assert retrieval_command == '0 proj handoff --json -- sample'
  assert result.exit_code == 0
  assert json.loads(result.output) == expected_handoff
