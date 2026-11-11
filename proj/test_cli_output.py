import base64
import json
import shlex
from collections.abc import Sequence
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from proj import cli
from proj.cli import project_group
from proj.project import create_project

TIME = 1_700_000_000
TIME_TEXT = '2023-11-14T22:13:20+00:00'

TABLE_READS = (
  (
    ('list',),
    'list_projects',
    [
      {
        'name': 'acme',
        'status': 'active',
        'updated_at': TIME,
        'objective': 'brief',
      }
    ],
    [
      {
        'name': 'acme',
        'status': 'active',
        'updated_at': TIME,
        'objective': 'brief',
      }
    ],
    'Name  Status  Updated                    Objective\n'
    '----  ------  -------------------------  ---------\n'
    'acme  active  2023-11-14T22:13:20+00:00  brief',
  ),
  (
    ('goal', 'list', 'sample'),
    'read_goals',
    [
      {
        'id': 7,
        'status': 'pending',
        'stage_names': 'Build',
        'text': 'write tests',
      }
    ],
    [
      {
        'id': 7,
        'status': 'pending',
        'stage_names': 'Build',
        'text': 'write tests',
      }
    ],
    'ID  Status   Stages  Text\n'
    '--  -------  ------  -----------\n'
    '7   pending  Build   write tests',
  ),
  (
    ('stage', 'list', 'sample'),
    'read_stages',
    [
      {
        'id': 3,
        'status': 'active',
        'name': 'Build',
        'outcome': 'Code',
      }
    ],
    [
      {
        'id': 3,
        'status': 'active',
        'name': 'Build',
        'outcome': 'Code',
      }
    ],
    'ID  Status  Name   Outcome\n'
    '--  ------  -----  -------\n'
    '3   active  Build  Code',
  ),
  (
    ('task', 'list', 'sample'),
    'read_tasks',
    [
      {
        'id': 12,
        'status': 'active',
        'stage_name': 'Build',
        'goal_id': None,
        'title': 'Review',
        'tags': 'test',
      }
    ],
    [
      {
        'id': 12,
        'status': 'active',
        'stage_name': 'Build',
        'goal_id': None,
        'title': 'Review',
        'tags': 'test',
      }
    ],
    'ID  Status  Stage  Goal  Title   Tags\n'
    '--  ------  -----  ----  ------  ----\n'
    '12  active  Build  -     Review  test',
  ),
  (
    ('task', 'ready', 'sample'),
    'read_tasks',
    [
      {
        'id': 12,
        'stage_name': 'Build',
        'title': 'Review',
      }
    ],
    [
      {
        'id': 12,
        'stage_name': 'Build',
        'title': 'Review',
      }
    ],
    'ID  Stage  Title\n--  -----  ------\n12  Build  Review',
  ),
  (
    ('task', 'list-logs', 'sample', '9'),
    'read_task',
    {
      'logs': [{'occurred_at': TIME, 'kind': 'note', 'message': 'started'}]
    },
    [{'occurred_at': TIME, 'kind': 'note', 'message': 'started'}],
    'Time                       Kind  Message\n'
    '-------------------------  ----  -------\n'
    '2023-11-14T22:13:20+00:00  note  started',
  ),
  (
    ('decision', 'list', 'sample'),
    'read_decisions',
    [
      {
        'id': 1,
        'decided_at': TIME,
        'summary': 'accepted',
        'context_status': 'complete',
      }
    ],
    [
      {
        'id': 1,
        'decided_at': TIME,
        'summary': 'accepted',
        'context_status': 'complete',
      }
    ],
    'ID  Decided                    Summary\n'
    '--  -------------------------  --------\n'
    '1   2023-11-14T22:13:20+00:00  accepted',
  ),
  (
    ('blocker', 'list', 'sample'),
    'read_blockers',
    [
      {
        'id': 2,
        'status': 'open',
        'target_kind': 'task',
        'target_id': 9,
        'stage_id': 3,
        'goal_id': None,
        'description': 'wait',
        'impact': '',
        'attempts': '',
        'required': 'review',
      }
    ],
    [
      {
        'id': 2,
        'status': 'open',
        'target_kind': 'task',
        'target_id': 9,
        'stage_id': 3,
        'goal_id': None,
        'description': 'wait',
        'impact': '',
        'attempts': '',
        'required': 'review',
      }
    ],
    'Status filter: open\n'
    'ID  Status  Target  Stage  Goal  Description  Impact  Attempts  '
    'Required\n'
    '--  ------  ------  -----  ----  -----------  ------  --------  '
    '--------\n'
    '2   open    task 9  3      -     wait         -       -         '
    'review',
  ),
  (
    ('evidence', 'list', 'sample'),
    'read_evidence',
    [
      {
        'id': 4,
        'captured_at': TIME,
        'claim': 'tests pass',
        'context_status': 'complete',
        'claim_status': 'substantive',
      }
    ],
    [
      {
        'id': 4,
        'captured_at': TIME,
        'claim': 'tests pass',
        'context_status': 'complete',
        'claim_status': 'substantive',
      }
    ],
    'ID  Captured                   Claim\n'
    '--  -------------------------  ----------\n'
    '4   2023-11-14T22:13:20+00:00  tests pass',
  ),
)

EMPTY_TABLE_HEADERS = (
  (
    ('list',),
    'list_projects',
    'Name  Status  Updated  Objective\n----  ------  -------  ---------',
  ),
  (
    ('goal', 'list', 'sample'),
    'read_goals',
    'ID  Status  Stages  Text\n--  ------  ------  ----',
  ),
  (
    ('stage', 'list', 'sample'),
    'read_stages',
    'ID  Status  Name  Outcome\n--  ------  ----  -------',
  ),
  (
    ('task', 'list', 'sample'),
    'read_tasks',
    'ID  Status  Stage  Goal  Title  Tags\n'
    '--  ------  -----  ----  -----  ----',
  ),
  (
    ('task', 'ready', 'sample'),
    'read_tasks',
    'ID  Stage  Title\n--  -----  -----',
  ),
  (
    ('task', 'list-logs', 'sample', '9'),
    'read_task',
    'Time  Kind  Message\n----  ----  -------',
  ),
  (
    ('decision', 'list', 'sample'),
    'read_decisions',
    'ID  Decided  Summary\n--  -------  -------',
  ),
  (
    ('blocker', 'list', 'sample'),
    'read_blockers',
    'Status filter: open\n'
    'ID  Status  Target  Stage  Goal  Description  Impact  Attempts  '
    'Required\n'
    '--  ------  ------  -----  ----  -----------  ------  --------  '
    '--------',
  ),
  (
    ('evidence', 'list', 'sample'),
    'read_evidence',
    'ID  Captured  Claim\n--  --------  -----',
  ),
)

JSON_READ_COMMANDS = (
  ('list',),
  ('handoff',),
  ('show',),
  ('goal', 'list'),
  ('goal', 'show'),
  ('stage', 'list'),
  ('task', 'list'),
  ('task', 'ready'),
  ('task', 'show'),
  ('task', 'list-logs'),
  ('decision', 'list'),
  ('blocker', 'list'),
  ('evidence', 'list'),
)

LIMITED_TABLE_READS = (TABLE_READS[5], TABLE_READS[6], TABLE_READS[8])


def _invoke_read(
  monkeypatch: pytest.MonkeyPatch,
  command: Sequence[str],
  service: str,
  result: object,
) -> Result:
  monkeypatch.setattr(cli, service, lambda *args, **kwargs: result)
  return CliRunner().invoke(project_group, command)


@pytest.mark.parametrize(
  ('command', 'service', 'expected'), EMPTY_TABLE_HEADERS
)
def test_empty_collection_reads_keep_their_headers(
  monkeypatch: pytest.MonkeyPatch,
  command: tuple[str, ...],
  service: str,
  expected: str,
) -> None:
  result = _invoke_read(
    monkeypatch,
    command,
    service,
    {'logs': []} if command[1:2] == ('list-logs',) else [],
  )

  assert result.exit_code == 0, result.output
  assert result.output == expected + '\n'


def test_blocker_list_reports_an_explicit_status_filter(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  result = _invoke_read(
    monkeypatch,
    ('blocker', 'list', 'sample', '--status', 'all'),
    'read_blockers',
    [],
  )

  assert result.exit_code == 0, result.output
  assert result.output == (
    'Status filter: all\n'
    'ID  Status  Target  Stage  Goal  Description  Impact  Attempts  '
    'Required\n'
    '--  ------  ------  -----  ----  -----------  ------  --------  '
    '--------\n'
  )


def test_task_show_discloses_when_the_log_limit_is_reached(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  data = {
    'task': {'id': 12, 'title': 'Review'},
    'logs': [{'occurred_at': TIME, 'kind': 'note', 'message': 'Started'}],
  }
  result = _invoke_read(
    monkeypatch,
    ('task', 'show', 'sample', '12', '--limit', '1'),
    'read_task',
    data,
  )

  assert result.exit_code == 0, result.output
  assert result.output == (
    'Task:\n'
    '  ID: 12\n'
    '  Title: Review\n'
    'Logs (1):\n'
    '  Log 1:\n'
    f'    Occurred At: {TIME_TEXT}\n'
    '    Kind: note\n'
    '    Message: Started\n'
    'Logs: Limit reached (1 rows); more records may exist. '
    'Increase --limit to retrieve more.\n'
  )


@pytest.mark.parametrize(
  ('command', 'service', 'service_result', 'json_value', 'expected_table'),
  TABLE_READS,
)
def test_collection_reads_render_populated_human_tables(
  monkeypatch: pytest.MonkeyPatch,
  command: tuple[str, ...],
  service: str,
  service_result: list[dict[str, object]],
  json_value: list[dict[str, object]],
  expected_table: str,
) -> None:
  result = _invoke_read(monkeypatch, command, service, service_result)

  assert result.exit_code == 0, result.output
  assert result.output == expected_table + '\n'


@pytest.mark.parametrize(
  ('command', 'service', 'service_result', 'json_value', 'expected_table'),
  TABLE_READS,
)
def test_collection_reads_emit_exact_json_only_when_requested(
  monkeypatch: pytest.MonkeyPatch,
  command: tuple[str, ...],
  service: str,
  service_result: list[dict[str, object]],
  json_value: list[dict[str, object]],
  expected_table: str,
) -> None:
  result = _invoke_read(
    monkeypatch, (*command, '--json'), service, service_result
  )

  assert result.exit_code == 0, result.output
  assert json.loads(result.output) == json_value


@pytest.mark.parametrize(
  ('command', 'service', 'service_result', 'json_value', 'expected_table'),
  LIMITED_TABLE_READS,
)
def test_limited_collection_reads_disclose_when_the_limit_is_reached(
  monkeypatch: pytest.MonkeyPatch,
  command: tuple[str, ...],
  service: str,
  service_result: list[dict[str, object]],
  json_value: list[dict[str, object]],
  expected_table: str,
) -> None:
  result = _invoke_read(
    monkeypatch, (*command, '--limit', '1'), service, service_result
  )

  assert result.exit_code == 0, result.output
  assert result.output == (
    expected_table + '\nLimit reached (1 rows); more records may exist. '
    'Increase --limit to retrieve more.\n'
  )


def test_table_snapshot_has_headers_and_aligned_columns() -> None:
  assert (
    cli._format_table(('ID', 'Title'), ((2, 'x'), (10, 'longer')))
    == 'ID  Title\n--  ------\n2   x\n10  longer'
  )


def test_table_snapshot_aligns_wide_and_combining_cells() -> None:
  assert (
    cli._format_table(
      ('Name', 'Value'), (('界', 'x'), ('e\u0301', 'longer'))
    )
    == 'Name  Value\n----  ------\n界    x\ne\u0301     longer'
  )


def test_table_cells_escape_unicode_line_separators() -> None:
  rendered = cli._format_table(
    ('Name', 'Value'), (('sample', '\u2028\u2029'),)
  )

  assert '\\u2028\\u2029' in rendered
  assert '\u2028' not in rendered
  assert '\u2029' not in rendered
  assert len(rendered.splitlines()) == 3


def test_table_snapshot_distinguishes_literal_dash_from_empty_values() -> (
  None
):
  assert (
    cli._format_table(('Value',), (('-',), (None,), ('',)))
    == 'Value\n-----\n"-"\n-\n-'
  )


def test_table_snapshot_escapes_long_and_multiline_cells() -> None:
  assert cli._format_table(
    ('ID', 'Text'), ((1, 'line one\nline two'), (2, 'long value'))
  ) == (
    'ID  Text\n'
    '--  ------------------\n'
    '1   line one\\nline two\n'
    '2   long value'
  )


@pytest.mark.parametrize('command', JSON_READ_COMMANDS)
def test_json_option_help_identifies_machine_readable_output(
  command: tuple[str, ...],
) -> None:
  result = CliRunner().invoke(project_group, (*command, '--help'))

  assert result.exit_code == 0, result.output
  assert '--json' in result.output
  assert 'Output JSON instead of the human-readable view.' in ' '.join(
    result.output.split()
  )


@pytest.mark.parametrize(
  'command',
  (
    ('task', 'show'),
    ('task', 'list-logs'),
    ('decision', 'list'),
    ('evidence', 'list'),
  ),
)
def test_bounded_read_help_shows_its_default(
  command: tuple[str, ...],
) -> None:
  result = CliRunner().invoke(project_group, (*command, '--help'))

  assert result.exit_code == 0, result.output
  assert '[default: 20; x>=1]' in ' '.join(result.output.split())


def test_blocker_list_help_shows_its_open_status_default() -> None:
  result = CliRunner().invoke(project_group, ('blocker', 'list', '--help'))

  assert result.exit_code == 0, result.output
  assert '[default: open]' in ' '.join(result.output.split())


def test_goal_text_and_copy_preserve_exact_text(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  text = '\x1b[31mGoal\x1b[0m\n"quoted" \\ Δ'
  monkeypatch.setattr(cli, 'goal_text', lambda *args: text)
  text_result = CliRunner().invoke(
    project_group, ('goal', 'text', 'sample', 'active')
  )
  copy_result = CliRunner().invoke(
    project_group, ('goal', 'copy', 'sample', 'active')
  )
  expected_copy = (
    '\x1b]52;c;'
    + base64.b64encode(text.encode('utf-8')).decode('ascii')
    + '\x07'
  )

  assert text_result.exit_code == 0
  assert text_result.output == text
  assert copy_result.exit_code == 0
  assert copy_result.output == expected_copy


def _handoff_data(objective: str) -> dict[str, object]:
  return {
    'path': '.tmp/sample.sqlite3',
    'project': {
      'name': 'sample',
      'status': 'active',
      'objective': objective,
      'charter_context_status': 'current',
    },
    'state': {'summary': '', 'next_action': ''},
    'goal': None,
    'stage': None,
    'task': None,
    'blocked_tasks': [],
    'blocked_goals': [],
    'blockers': [],
    'decisions': [],
    'evidence': [],
    'logs': [],
    'focus': {'kind': None, 'id': None},
    'pages': {
      'decisions': {'total': 0},
      'evidence': {'total': 0},
      'task_log': {'total': 0},
    },
  }


def test_handoff_escapes_control_text_and_preserves_short_values(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  objective = 'First line\n"quoted" \\ end\t'
  handoff = _handoff_data(objective)
  monkeypatch.setattr(cli, 'read_handoff', lambda *args: handoff)
  result = CliRunner().invoke(project_group, ('handoff', 'sample'))

  assert result.exit_code == 0, result.output
  assert (
    'Objective: First line\\n\\"quoted\\" \\\\ end\\t' in result.output
  )
  assert '\n"quoted"' not in result.output


def test_handoff_escapes_unicode_line_separators(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  handoff = _handoff_data('before\u2028middle\u2029after')
  monkeypatch.setattr(cli, 'read_handoff', lambda *args: handoff)
  result = CliRunner().invoke(project_group, ('handoff', 'sample'))

  assert result.exit_code == 0, result.output
  assert 'Objective: before\\u2028middle\\u2029after' in result.output
  assert '\u2028' not in result.output
  assert '\u2029' not in result.output


def test_handoff_bounds_text_projection_and_keeps_exact_json(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  objective = 'a' * 1_200
  handoff = _handoff_data(objective)
  monkeypatch.setattr(cli, 'read_handoff', lambda *args: handoff)
  text_result = CliRunner().invoke(project_group, ('handoff', 'sample'))
  json_result = CliRunner().invoke(
    project_group, ('handoff', 'sample', '--json')
  )
  result_value = json.loads(json_result.output)
  expected_command = '0 proj handoff --json -- sample'
  rendered_objective = next(
    line.removeprefix('Objective: ')
    for line in text_result.output.splitlines()
    if line.startswith('Objective: ')
  )

  assert text_result.exit_code == 0, text_result.output
  assert json_result.exit_code == 0, json_result.output
  assert len(rendered_objective) == cli.HANDOFF_TEXT_LIMIT
  assert rendered_objective == 'a' * 999 + '…'
  assert f'- Full values: {expected_command}' in text_result.output
  assert result_value['project']['objective'] == objective
  assert result_value['text_projection'] == {
    'character_limit': cli.HANDOFF_TEXT_LIMIT,
    'truncated_fields': [
      {
        'path': 'project.objective',
        'characters': 1_200,
        'retrieval': expected_command,
      }
    ],
    'full_value_commands': [expected_command],
  }


def test_handoff_retrieval_command_reads_the_complete_stored_value(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  objective = 'a' * 1_200
  create_project(tmp_path, 'sample', objective)
  monkeypatch.setattr(cli, 'repository_root', lambda: tmp_path)
  handoff = CliRunner().invoke(project_group, ('handoff', 'sample'))
  command = next(
    line.removeprefix('- Full values: ')
    for line in handoff.output.splitlines()
    if line.startswith('- Full values: ')
  )
  retrieval = CliRunner().invoke(project_group, shlex.split(command)[2:])

  assert handoff.exit_code == 0, handoff.output
  assert retrieval.exit_code == 0, retrieval.output
  assert json.loads(retrieval.output)['project']['objective'] == objective


def test_handoff_keeps_exactly_fitting_escaped_values() -> None:
  rendered, truncated = cli._bounded_escaped_text(
    'x' * cli.HANDOFF_TEXT_LIMIT, cli.HANDOFF_TEXT_LIMIT
  )

  assert rendered == 'x' * cli.HANDOFF_TEXT_LIMIT
  assert truncated is False


def test_handoff_quotes_a_literal_dash() -> None:
  assert cli._bounded_escaped_text('-', cli.HANDOFF_TEXT_LIMIT) == (
    '"-"',
    False,
  )


def test_handoff_truncates_escaped_text_without_exceeding_the_limit() -> (
  None
):
  rendered, truncated = cli._bounded_escaped_text(
    '\n' * 600, cli.HANDOFF_TEXT_LIMIT
  )

  assert rendered == '\\n' * 499 + '…'
  assert len(rendered) <= cli.HANDOFF_TEXT_LIMIT
  assert truncated is True


@pytest.mark.parametrize(
  ('command', 'service', 'value', 'expected'),
  (
    (
      ('show', 'sample'),
      'read_project',
      {
        'path': '.tmp/sample.sqlite3',
        'project': {
          'name': 'sample',
          'objective': 'Build it',
          'scope': 'CLI',
          'non_goals': 'No storage changes',
          'constraints_text': 'Keep exact data',
          'acceptance_evidence': 'Tests pass',
          'created_at': TIME,
          'updated_at': TIME,
          'archived_at': None,
          'status': 'active',
          'completed_at': None,
        },
        'state': {'summary': 'Current', 'next_action': 'Test output'},
        'goal': None,
        'charter_history': [],
      },
      (
        'Project:\n'
        '  Name: sample\n'
        '  Objective: Build it\n'
        '  Scope: CLI\n'
        '  Non-goals: No storage changes\n'
        '  Constraints: Keep exact data\n'
        '  Acceptance Evidence: Tests pass\n'
        f'  Created At: {TIME_TEXT}\n'
        f'  Updated At: {TIME_TEXT}\n'
        '  Archived At: -\n'
        '  Status: active\n'
        '  Completed At: -\n'
        'Database path: .tmp/sample.sqlite3\n'
        'Project state:\n'
        '  Summary: Current\n'
        '  Next Action: Test output\n'
        'Active goal: -\n'
        'Previous charters (0):'
      ),
    ),
    (
      ('goal', 'show', 'sample', '7'),
      'read_goal',
      {
        'goal': {
          'id': 7,
          'status': 'active',
          'text': 'Ship output',
          'status_reason': None,
          'started_at': TIME,
        },
        'stages': [{'id': 3, 'name': 'Build', 'outcome': 'Clear output'}],
        'tasks': [],
        'blockers': [],
        'evidence': [],
        'decisions': [],
      },
      (
        'Goal:\n'
        '  ID: 7\n'
        '  Status: active\n'
        '  Text: Ship output\n'
        '  Status Reason: -\n'
        f'  Started At: {TIME_TEXT}\n'
        '  Stages (1):\n'
        '    Stage 1:\n'
        '      ID: 3\n'
        '      Name: Build\n'
        '      Outcome: Clear output\n'
        '  Tasks (0):\n'
        '  Blockers (0):\n'
        '  Evidence (0):\n'
        '  Decisions (0):'
      ),
    ),
    (
      ('task', 'show', 'sample', '12'),
      'read_task',
      {
        'task': {
          'id': 12,
          'title': 'Review output',
          'status': 'active',
          'stage_name': 'Build',
          'goal_id': None,
        },
        'logs': [
          {'occurred_at': TIME, 'kind': 'note', 'message': 'Started'},
        ],
      },
      (
        'Task:\n'
        '  ID: 12\n'
        '  Title: Review output\n'
        '  Status: active\n'
        '  Stage Name: Build\n'
        '  Goal ID: -\n'
        'Logs (1):\n'
        '  Log 1:\n'
        f'    Occurred At: {TIME_TEXT}\n'
        '    Kind: note\n'
        '    Message: Started'
      ),
    ),
  ),
)
def test_detailed_reads_render_labelled_fields_by_default(
  monkeypatch: pytest.MonkeyPatch,
  command: tuple[str, ...],
  service: str,
  value: dict[str, object],
  expected: str,
) -> None:
  result = _invoke_read(monkeypatch, command, service, value)

  assert result.exit_code == 0, result.output
  assert result.output == expected + '\n'


@pytest.mark.parametrize(
  ('command', 'service', 'value'),
  (
    (
      ('show', 'sample'),
      'read_project',
      {
        'path': '.tmp/sample.sqlite3',
        'project': {'name': 'sample', 'objective': 'Keep "exact"'},
        'state': {'summary': 'A\nB'},
        'goal': None,
        'charter_history': [],
      },
    ),
    (
      ('goal', 'show', 'sample', '7'),
      'read_goal',
      {
        'goal': {'id': 7, 'text': 'Goal "exact"'},
        'stages': [],
        'tasks': [],
        'blockers': [],
        'evidence': [],
        'decisions': [],
      },
    ),
    (
      ('task', 'show', 'sample', '12'),
      'read_task',
      {'task': {'id': 12, 'title': 'Task\\exact'}, 'logs': []},
    ),
  ),
)
def test_detailed_reads_preserve_the_exact_json_payload(
  monkeypatch: pytest.MonkeyPatch,
  command: tuple[str, ...],
  service: str,
  value: dict[str, object],
) -> None:
  result = _invoke_read(monkeypatch, (*command, '--json'), service, value)

  assert result.exit_code == 0, result.output
  assert json.loads(result.output) == value
