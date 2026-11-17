import base64
import errno
import json
import os
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

import click
import pytest
from click.testing import CliRunner
from pytest import MonkeyPatch

from proj import cli, core, render, service, store
from proj.schema_test import downgrade_v7_to_v6
from proj.store_test import MemdbBackend

_NOW = 1_700_000_000
_TIME_TEXT = '2023-11-14T22:13:20+00:00'
_NAME = core.ProjectName.parse('demo')
_CHARTER = core.CharterInput.parse(
  objective='Deliver CLI parity',
  scope='Commands and formatting',
  non_goals='Zero dependency',
  constraints='Deterministic memdb',
  acceptance='All tests pass',
)


@pytest.fixture(autouse=True)
def _isolate_click_environment(monkeypatch: MonkeyPatch) -> None:
  monkeypatch.setenv('COLUMNS', '80')
  for key in list(os.environ):
    if key.startswith('_') and key.endswith('_COMPLETE'):
      monkeypatch.delenv(key, raising=False)


@contextmanager
def _memdb_cli() -> Iterator[tuple[MemdbBackend, store.ProjectStore]]:
  backend = MemdbBackend(uri_prefix='cli-memdb')
  try:
    yield backend, store.ProjectStore(backend)
  finally:
    backend.close()


@pytest.fixture(scope='module')
def v7_snapshot() -> bytes:
  with _memdb_cli() as (backend, project_store):
    project_store.create_project(_NAME, _CHARTER)
    raw = backend.open_raw(PurePosixPath('.tmp/demo.sqlite3'), mode='ro')
    try:
      return raw.serialize()
    finally:
      raw.close()


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


def test_parameter_types_and_handoff_command_builders() -> None:
  assert (
    cli.STAGE_REFERENCE.convert('release', None, None),
    cli.STAGE_REFERENCE.convert('10', None, None),
    cli.STAGE_REFERENCE.convert('²', None, None),
    cli.STAGE_REFERENCE.convert('\u0661', None, None),
    cli.STAGE_REFERENCE.convert(None, None, None),
    cli.GOAL_REFERENCE.convert('active', None, None),
    cli.GOAL_REFERENCE.convert('8', None, None),
    cli.GOAL_REFERENCE.convert(None, None, None),
  ) == (
    core.StageName('release'),
    core.PositiveInt(10),
    core.StageName('²'),
    core.StageName('\u0661'),
    None,
    'active',
    core.PositiveInt(8),
    None,
  )

  bad_params: list[str] = []
  for param, value in (
    (cli.STAGE_REFERENCE, '0'),
    (cli.STAGE_REFERENCE, -1),
    (cli.STAGE_REFERENCE, ''),
    (cli.STAGE_REFERENCE, True),
    (cli.GOAL_REFERENCE, '0'),
    (cli.GOAL_REFERENCE, 'other'),
    (cli.GOAL_REFERENCE, '\u0661'),
    (cli.GOAL_REFERENCE, True),
  ):
    with pytest.raises(click.BadParameter) as err:
      param.convert(value, None, None)
    bad_params.append(err.value.message)
  assert bad_params == [
    'Expected a stage name or positive stage ID.',
    'Expected a stage name or positive stage ID.',
    'Expected a stage name or positive stage ID.',
    'Expected a stage name or positive stage ID.',
    'Expected a positive goal ID or the active keyword.',
    'Expected a positive goal ID or the active keyword.',
    'Expected a positive goal ID or the active keyword.',
    'Expected a positive goal ID or the active keyword.',
  ]

  assert (
    cli._shell_quote(''),
    cli._shell_quote('a_@%+=:,./-1'),
    cli._shell_quote('my repo'),
    cli._shell_quote("a'b"),
    cli._project_command(('task', 'show'), 'my repo', (7,), ('--json',)),
  ) == (
    "''",
    'a_@%+=:,./-1',
    'my\\ repo',
    "a\\'b",
    '0 proj task show --json -- my\\ repo 7',
  )
  with pytest.raises(core.ProjectError) as bad_quote:
    cli._shell_quote('bad\ntoken')
  assert str(bad_quote.value) == (
    'Recovery command token contains non-printable characters'
  )
  with pytest.raises(core.ProjectError) as long_cmd:
    cli._project_command(('show',), 'x' * 1000)
  assert str(long_cmd.value) == (
    'Generated project recovery command exceeds the handoff text limit'
  )

  project_rec = service.ProjectRecord(
    id=1,
    name='sample',
    objective='Build',
    scope='CLI',
    non_goals='None',
    constraints_text='Pure',
    acceptance='Pass',
    created_at=_NOW,
    updated_at=_NOW,
    charter_context_status='current',
    status='active',
    completed_at=None,
  )
  state_rec = service.ProjectState(
    id=1, summary='S', next_action='N', updated_at=_NOW, revision=1
  )
  goal_rec = service.GoalRecord(
    id=4,
    text='G',
    status='active',
    status_reason='',
    ever_activated=1,
    created_at=_NOW,
    started_at=_NOW,
    achieved_at=None,
    updated_at=_NOW,
  )
  stage_rec = service.StageRecord(
    id=2,
    name='Build',
    outcome='Done',
    purpose='',
    entry_conditions='',
    exit_evidence='',
    position=0,
    achievement_generation=0,
    achievement_generation_started_at=_NOW,
    created_at=_NOW,
    updated_at=_NOW,
    status='active',
    started_at=_NOW,
    achieved_at=None,
    achievement_evidence_id=None,
  )
  task_rec = service.HandoffTaskRecord(
    id=7,
    goal_id=4,
    stage_id=2,
    title='T',
    purpose='P',
    scope='S',
    exclusions='E',
    result='R',
    completion_evidence='CE',
    status='active',
    priority=0,
    created_at=_NOW,
    started_at=_NOW,
    completed_at=None,
    updated_at=_NOW,
    title_status='substantive',
  )
  handoff_data = service.HandoffData(
    path='.tmp/sample.sqlite3',
    project=project_rec,
    state=state_rec,
    goal=service.ActiveGoalRef(goal=goal_rec),
    stage=stage_rec,
    task=task_rec,
    blocked_tasks=(
      service.BlockedTaskSummary(
        id=9,
        title='BT',
        status='blocked',
        goal_id=4,
        stage_id=2,
        stage_name='Build',
        updated_at=_NOW,
        title_status='substantive',
      ),
    ),
    blocked_goals=(
      service.BlockedGoalSummary(
        id=5,
        text='BG',
        status='blocked',
        status_reason='Wait',
        updated_at=_NOW,
      ),
    ),
    blockers=(),
    decisions=(),
    evidence=(),
    logs=(),
    focus=service.HandoffFocus(kind='task', id=7),
    pages=service.HandoffPages(
      blocked_tasks=service.HandoffPage(shown=1, total=1, truncated=False),
      blocked_goals=service.HandoffPage(shown=1, total=1, truncated=False),
      blockers=service.HandoffPage(shown=0, total=0, truncated=False),
      decisions=service.HandoffPage(shown=0, total=3, truncated=True),
      evidence=service.HandoffPage(shown=0, total=2, truncated=True),
      task_log=service.HandoffPage(shown=0, total=8, truncated=True),
    ),
  )
  retrieval = cli._handoff_retrieval_commands(handoff_data)
  assert retrieval == render.HandoffRetrieval(
    project='0 proj show --json -- sample',
    goal='0 proj goal show --json -- sample 4',
    stage='0 proj stage list --json -- sample',
    task='0 proj task show --json -- sample 7',
    blocked_tasks='0 proj task list --status blocked --json -- sample',
    blocked_goals='0 proj goal list --status blocked --json -- sample',
    blockers='0 proj blocker list --json -- sample',
    ready_tasks='0 proj task ready -- sample',
    decisions='0 proj decision list --task 7 --limit 3 --json -- sample',
    evidence='0 proj evidence list --task 7 --limit 2 --json -- sample',
    task_log='0 proj task list-logs --limit 8 --json -- sample 7',
  )

  view = render.HandoffView(data=handoff_data, retrieval=retrieval)
  assert (
    cli._handoff_full_value_command(view, 'sample', ('path',)),
    cli._handoff_full_value_command(
      view, 'sample', ('goal', 'goal', 'text')
    ),
    cli._handoff_full_value_command(view, 'sample', ('stage', 'name')),
    cli._handoff_full_value_command(view, 'sample', ('task', 'title')),
    cli._handoff_full_value_command(
      view, 'sample', ('blocked_tasks', 0, 'title')
    ),
    cli._handoff_full_value_command(
      view, 'sample', ('blocked_goals', 0, 'text')
    ),
    cli._handoff_full_value_command(
      view, 'sample', ('logs', 0, 'message')
    ),
  ) == (
    '0 proj handoff --json -- sample',
    '0 proj goal show --json -- sample 4',
    '0 proj stage list --json -- sample',
    '0 proj task show --json -- sample 7',
    '0 proj task show --json -- sample 9',
    '0 proj goal show --json -- sample 5',
    '0 proj task list-logs --limit 8 --json -- sample 7',
  )

  with pytest.raises(ValueError) as bad_path:
    cli._handoff_full_value_command(view, 'sample', ('unknown',))
  assert str(bad_path.value) == 'No handoff retrieval path for unknown'


def test_canonical_command_inventory_and_help_contracts() -> None:
  runner = CliRunner()
  expected_groups = (
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
  with _memdb_cli() as (_backend, project_store):
    group_helps = tuple(
      (
        subject,
        runner.invoke(
          cli.project_group, (*subject, '--help'), obj=project_store
        ),
      )
      for subject, _ in expected_groups
    )
    observed_groups = tuple(
      (subject, result.exit_code, _help_commands(result.output))
      for subject, result in group_helps
    )
    assert observed_groups == tuple(
      (subject, 0, cmds) for subject, cmds in expected_groups
    )

    goal_show_help = runner.invoke(
      cli.project_group, ('goal', 'show', '--help'), obj=project_store
    )
    goal_act_help = runner.invoke(
      cli.project_group, ('goal', 'activate', '--help'), obj=project_store
    )
    logs_help = runner.invoke(
      cli.project_group, ('task', 'list-logs', '--help'), obj=project_store
    )
    decision_list_help = runner.invoke(
      cli.project_group, ('decision', 'list', '--help'), obj=project_store
    )
    blocker_list_help = runner.invoke(
      cli.project_group, ('blocker', 'list', '--help'), obj=project_store
    )
    task_create_help = runner.invoke(
      cli.project_group, ('task', 'create', '--help'), obj=project_store
    )
    handoff_help = runner.invoke(
      cli.project_group, ('handoff', '--help'), obj=project_store
    )
  assert (
    (goal_show_help.exit_code, goal_show_help.output),
    (goal_act_help.exit_code, goal_act_help.output),
    (logs_help.exit_code, logs_help.output),
    (decision_list_help.exit_code, decision_list_help.output),
    (blocker_list_help.exit_code, blocker_list_help.output),
    (task_create_help.exit_code, task_create_help.output),
    (handoff_help.exit_code, handoff_help.output),
  ) == (
    (
      0,
      'Usage: project goal show [OPTIONS] NAME [GOAL]\n\n'
      'Options:\n'
      '  --json  Output JSON instead of the human-readable view.\n'
      '  --help  Show this message and exit.\n',
    ),
    (
      0,
      'Usage: project goal activate [OPTIONS] NAME GOAL\n\n'
      '  Activate a pending goal, handing off active goal-linked work.\n\n'
      'Options:\n'
      '  --help  Show this message and exit.\n',
    ),
    (
      0,
      'Usage: project task list-logs [OPTIONS] NAME TASK\n\n'
      "  List a task's log entries.\n\n"
      'Options:\n'
      '  --limit LIMIT           Maximum number of task logs to return.  '
      '[default: 20;\n'
      '                          x>=1]\n'
      '  --since UNIX_TIMESTAMP\n'
      '  --json                  Output JSON instead of the '
      'human-readable view.\n'
      '  --help                  Show this message and exit.\n',
    ),
    (
      0,
      'Usage: project decision list [OPTIONS] NAME\n\n'
      'Options:\n'
      '  --limit LIMIT  Maximum number of decisions to return.  '
      '[default: 20; x>=1]\n'
      '  --stage STAGE\n'
      '  --task TASK    [x>=1]\n'
      '  --goal GOAL\n'
      '  --no-task\n'
      '  --json         Output JSON instead of the human-readable view.\n'
      '  --help         Show this message and exit.\n',
    ),
    (
      0,
      'Usage: project blocker list [OPTIONS] NAME\n\n'
      'Options:\n'
      '  --status [open|resolved|withdrawn|all]\n'
      '                                  Filter by blocker status.  '
      '[default: open]\n'
      '  --json                          Output JSON instead of the '
      'human-readable\n'
      '                                  view.\n'
      '  --help                          Show this message and exit.\n',
    ),
    (
      0,
      'Usage: project task create [OPTIONS] NAME\n\n'
      '  Create a pending project task.\n\n'
      'Options:\n'
      '  --title TEXT                [required]\n'
      '  --purpose TEXT\n'
      '  --scope TEXT\n'
      '  --exclusions TEXT\n'
      '  --result TEXT\n'
      '  --completion-evidence TEXT\n'
      '  --stage STAGE\n'
      '  --priority PRIORITY\n'
      '  --tag TEXT\n'
      '  --goal GOAL\n'
      '  --help                      Show this message and exit.\n',
    ),
    (
      0,
      'Usage: project handoff [OPTIONS] NAME\n\n'
      '  Produce a compact handoff for a new session.\n\n'
      'Options:\n'
      '  --json  Output JSON instead of the human-readable view.\n'
      '  --help  Show this message and exit.\n',
    ),
  )

  with _memdb_cli() as (_backend, project_store):
    bad_cli = runner.invoke(
      cli.project_group,
      ('stage', 'update', 'demo', '0'),
      obj=project_store,
    )
  assert (bad_cli.exit_code, bad_cli.output) == (
    2,
    'Usage: project stage update [OPTIONS] NAME STAGE\n'
    "Try 'project stage update --help' for help.\n\n"
    "Error: Invalid value for 'STAGE': Expected a stage name or positive "
    'stage ID.\n',
  )


def test_pre_open_validation_does_not_migrate_v6_until_valid_op(
  v7_snapshot: bytes,
) -> None:
  runner = CliRunner()
  with _memdb_cli() as (backend, project_store):
    db_rel = PurePosixPath('.tmp/demo.sqlite3')
    backend.seed(db_rel, v7_snapshot)
    raw = backend.open_raw(db_rel, mode='rw')
    try:
      downgrade_v7_to_v6(raw)
    finally:
      raw.close()

    r_goal = runner.invoke(
      cli.project_group,
      ('goal', 'create', 'demo', '--text', '   ', '--stage', 's1'),
      obj=project_store,
    )
    r_dup_goal = runner.invoke(
      cli.project_group,
      (
        'goal',
        'create',
        'demo',
        '--text',
        'Valid goal',
        '--stage',
        's1',
        '--stage',
        's1',
      ),
      obj=project_store,
    )
    r_filter = runner.invoke(
      cli.project_group,
      ('decision', 'list', 'demo', '--task', '1', '--no-task'),
      obj=project_store,
    )
    r_update = runner.invoke(
      cli.project_group,
      ('task', 'update', 'demo', '1', '--goal', '1', '--no-goal'),
      obj=project_store,
    )
    r_bad_title = runner.invoke(
      cli.project_group,
      ('task', 'update', 'demo', '1', '--title', '   '),
      obj=project_store,
    )
    r_bad_create_tag = runner.invoke(
      cli.project_group,
      ('task', 'create', 'demo', '--title', 'Valid task', '--tag', '   '),
      obj=project_store,
    )
    r_bad_add_tag = runner.invoke(
      cli.project_group,
      ('task', 'add-tag', 'demo', '1', '   '),
      obj=project_store,
    )
    r_bad_remove_tag = runner.invoke(
      cli.project_group,
      ('task', 'remove-tag', 'demo', '1', '   '),
      obj=project_store,
    )
    r_bad_decision = runner.invoke(
      cli.project_group,
      ('decision', 'create', 'demo', '--summary', '   '),
      obj=project_store,
    )
    r_blocker_target = runner.invoke(
      cli.project_group,
      (
        'blocker',
        'create',
        'demo',
        '--description',
        'Need help',
        '--required',
        'Input',
      ),
      obj=project_store,
    )

    check_unmigrated = backend.open_raw(db_rel, mode='ro')
    try:
      version_before = check_unmigrated.execute(
        'PRAGMA user_version'
      ).fetchone()[0]
    finally:
      check_unmigrated.close()

    assert (
      (r_goal.exit_code, r_goal.output),
      (r_dup_goal.exit_code, r_dup_goal.output),
      (r_filter.exit_code, r_filter.output),
      (r_update.exit_code, r_update.output),
      (r_bad_title.exit_code, r_bad_title.output),
      (r_bad_create_tag.exit_code, r_bad_create_tag.output),
      (r_bad_add_tag.exit_code, r_bad_add_tag.output),
      (r_bad_remove_tag.exit_code, r_bad_remove_tag.output),
      (r_bad_decision.exit_code, r_bad_decision.output),
      (r_blocker_target.exit_code, r_blocker_target.output),
      version_before,
    ) == (
      (
        1,
        'Error: Goal text must contain at least one non-whitespace '
        'character\n',
      ),
      (1, 'Error: A goal cannot link the same stage more than once\n'),
      (1, 'Error: Decision task and no-task filters conflict\n'),
      (
        2,
        'Usage: project task update [OPTIONS] NAME TASK\n'
        "Try 'project task update --help' for help.\n\n"
        'Error: --goal and --no-goal cannot be combined\n',
      ),
      (1, 'Error: Task title must contain non-whitespace text\n'),
      (1, 'Error: Task tags cannot be empty\n'),
      (1, 'Error: Task tags cannot be empty\n'),
      (1, 'Error: Task tags cannot be empty\n'),
      (1, 'Error: Decision summary must contain non-whitespace text\n'),
      (1, 'Error: A blocker must target a task or goal\n'),
      6,
    )

    r_ok = runner.invoke(
      cli.project_group,
      ('stage', 'list', 'demo'),
      obj=project_store,
    )
    check_migrated = backend.open_raw(db_rel, mode='ro')
    try:
      version_after = check_migrated.execute(
        'PRAGMA user_version'
      ).fetchone()[0]
    finally:
      check_migrated.close()
    assert (r_ok.exit_code, r_ok.output, version_after) == (
      0,
      'ID  Status  Name  Outcome\n--  ------  ----  -------\n',
      7,
    )


def test_end_to_end_cli_lifecycle_and_handoff_round_trip() -> None:
  runner = CliRunner()
  with _memdb_cli() as (_backend, project_store):
    empty_list = runner.invoke(
      cli.project_group, ('list',), obj=project_store
    )
    assert (empty_list.exit_code, empty_list.output) == (
      0,
      'Name  Status  Updated  Objective\n'
      '----  ------  -------  ---------\n',
    )

    long_objective = 'o' * 1_100
    r_create = runner.invoke(
      cli.project_group,
      (
        'create',
        'demo',
        '--objective',
        long_objective,
        '--scope',
        'CLI scope',
        '--non-goals',
        'No network',
        '--constraints',
        'Memdb',
        '--acceptance',
        'All commands work',
      ),
      obj=project_store,
    )
    r_list_json = runner.invoke(
      cli.project_group, ('list', '--json'), obj=project_store
    )
    r_update = runner.invoke(
      cli.project_group,
      (
        'update',
        'demo',
        '--summary',
        'Ready',
        '--next-action',
        'Run stages',
      ),
      obj=project_store,
    )
    r_show_json = runner.invoke(
      cli.project_group, ('show', 'demo', '--json'), obj=project_store
    )
    assert (
      (r_create.exit_code, r_create.output),
      (r_list_json.exit_code, json.loads(r_list_json.output)),
      (r_update.exit_code, r_update.output),
      (r_show_json.exit_code, json.loads(r_show_json.output)),
    ) == (
      (0, '/memdb-root/.tmp/demo.sqlite3\n'),
      (
        0,
        [
          {
            'name': 'demo',
            'status': 'active',
            'objective': long_objective,
            'updated_at': _NOW,
            'path': '/memdb-root/.tmp/demo.sqlite3',
          }
        ],
      ),
      (0, ''),
      (
        0,
        {
          'charter_history': [],
          'goal': None,
          'path': '/memdb-root/.tmp/demo.sqlite3',
          'project': {
            'acceptance': 'All commands work',
            'charter_context_status': 'current',
            'completed_at': None,
            'constraints_text': 'Memdb',
            'created_at': _NOW,
            'id': 1,
            'name': 'demo',
            'non_goals': 'No network',
            'objective': long_objective,
            'scope': 'CLI scope',
            'status': 'active',
            'updated_at': _NOW,
          },
          'state': {
            'id': 1,
            'next_action': 'Run stages',
            'revision': 1,
            'summary': 'Ready',
            'updated_at': _NOW,
          },
        },
      ),
    )

    r_s1 = runner.invoke(
      cli.project_group,
      (
        'stage',
        'create',
        'demo',
        's1',
        '--outcome',
        'Stage 1 done',
        '--exit-evidence',
        'Proof 1',
      ),
      obj=project_store,
    )
    r_s2 = runner.invoke(
      cli.project_group,
      (
        'stage',
        'create',
        'demo',
        's2',
        '--outcome',
        'Stage 2 done',
        '--exit-evidence',
        'Proof 2',
      ),
      obj=project_store,
    )
    r_s_upd = runner.invoke(
      cli.project_group,
      ('stage', 'update', 'demo', 's2', '--purpose', 'Final stage'),
      obj=project_store,
    )
    r_s_dep = runner.invoke(
      cli.project_group,
      ('stage', 'add-dependency', 'demo', 's2', 's1'),
      obj=project_store,
    )
    assert (
      (r_s1.exit_code, r_s1.output),
      (r_s2.exit_code, r_s2.output),
      (r_s_upd.exit_code, r_s_upd.output),
      (r_s_dep.exit_code, r_s_dep.output),
    ) == ((0, '1\n'), (0, '2\n'), (0, ''), (0, ''))

    ansi_goal = '\x1b[31mShip\x1b[0m \x1b[1mCLI\x1b[0m'
    r_g1 = runner.invoke(
      cli.project_group,
      ('goal', 'create', 'demo', '--text', ansi_goal, '--stage', 's1'),
      obj=project_store,
    )
    r_g2 = runner.invoke(
      cli.project_group,
      ('goal', 'create', 'demo', '--text', 'Temp goal', '--stage', 's2'),
      obj=project_store,
    )
    r_g_act = runner.invoke(
      cli.project_group,
      ('goal', 'activate', 'demo', '1'),
      obj=project_store,
    )
    r_g_text = runner.invoke(
      cli.project_group, ('goal', 'text', 'demo'), obj=project_store
    )
    r_g_copy = runner.invoke(
      cli.project_group, ('goal', 'copy', 'demo', '1'), obj=project_store
    )
    expected_b64 = base64.b64encode(ansi_goal.encode('utf-8')).decode(
      'ascii'
    )
    assert (
      (r_g1.exit_code, r_g1.output),
      (r_g2.exit_code, r_g2.output),
      (r_g_act.exit_code, r_g_act.output),
      (r_g_text.exit_code, r_g_text.output),
      (r_g_copy.exit_code, r_g_copy.output),
    ) == (
      (0, '1\n'),
      (0, '2\n'),
      (0, ''),
      (0, ansi_goal),
      (0, f'\x1b]52;c;{expected_b64}\x07'),
    )

    r_t1 = runner.invoke(
      cli.project_group,
      (
        'task',
        'create',
        'demo',
        '--title',
        'Do work',
        '--purpose',
        'Build',
        '--scope',
        'Core',
        '--exclusions',
        'None',
        '--result',
        'Built',
        '--completion-evidence',
        'Green',
        '--stage',
        's1',
        '--goal',
        'active',
        '--priority',
        '2',
        '--tag',
        'cli',
      ),
      obj=project_store,
    )
    r_t_ready = runner.invoke(
      cli.project_group, ('task', 'ready', 'demo'), obj=project_store
    )
    r_t_act = runner.invoke(
      cli.project_group,
      ('task', 'activate', 'demo', '1'),
      obj=project_store,
    )
    r_t_log = runner.invoke(
      cli.project_group,
      ('task', 'add-log', 'demo', '1', 'Progress', '--kind', 'note'),
      obj=project_store,
    )
    r_t_tag_add = runner.invoke(
      cli.project_group,
      ('task', 'add-tag', 'demo', '1', 'parity'),
      obj=project_store,
    )
    r_t_tag_rm = runner.invoke(
      cli.project_group,
      ('task', 'remove-tag', 'demo', '1', 'cli'),
      obj=project_store,
    )
    r_t_upd = runner.invoke(
      cli.project_group,
      ('task', 'update', 'demo', '1', '--priority', '5'),
      obj=project_store,
    )
    r_t_blk = runner.invoke(
      cli.project_group,
      (
        'task',
        'block',
        'demo',
        '1',
        '--description',
        'Need input',
        '--required',
        'Answer',
      ),
      obj=project_store,
    )
    r_blk_list = runner.invoke(
      cli.project_group,
      ('blocker', 'list', 'demo', '--status', 'all'),
      obj=project_store,
    )
    r_blk_res = runner.invoke(
      cli.project_group,
      ('blocker', 'resolve', 'demo', '1', '--resolution', 'Answered'),
      obj=project_store,
    )
    r_t_cancel = runner.invoke(
      cli.project_group,
      ('task', 'cancel', 'demo', '1', '--reason', 'Retry'),
      obj=project_store,
    )
    r_t_reopen = runner.invoke(
      cli.project_group, ('task', 'reopen', 'demo', '1'), obj=project_store
    )
    r_t_react = runner.invoke(
      cli.project_group,
      ('task', 'activate', 'demo', '1'),
      obj=project_store,
    )
    r_t_show = runner.invoke(
      cli.project_group, ('task', 'show', 'demo', '1'), obj=project_store
    )
    r_t_logs = runner.invoke(
      cli.project_group,
      ('task', 'list-logs', 'demo', '1', '--json'),
      obj=project_store,
    )
    r_dec = runner.invoke(
      cli.project_group,
      (
        'decision',
        'create',
        'demo',
        '--summary',
        'Keep pure',
        '--task',
        '1',
      ),
      obj=project_store,
    )
    r_ev = runner.invoke(
      cli.project_group,
      ('evidence', 'create', 'demo', '--claim', 'Verified', '--task', '1'),
      obj=project_store,
    )
    r_handoff = runner.invoke(
      cli.project_group, ('handoff', 'demo'), obj=project_store
    )
    r_handoff_json = runner.invoke(
      cli.project_group, ('handoff', 'demo', '--json'), obj=project_store
    )

    assert (
      (r_t1.exit_code, r_t1.output),
      (r_t_ready.exit_code, r_t_ready.output),
      (r_t_act.exit_code, r_t_act.output),
      (r_t_log.exit_code, r_t_log.output),
      (r_t_tag_add.exit_code, r_t_tag_add.output),
      (r_t_tag_rm.exit_code, r_t_tag_rm.output),
      (r_t_upd.exit_code, r_t_upd.output),
      (r_t_blk.exit_code, r_t_blk.output),
      (r_blk_list.exit_code, r_blk_list.output),
      (r_blk_res.exit_code, r_blk_res.output),
      (r_t_cancel.exit_code, r_t_cancel.output),
      (r_t_reopen.exit_code, r_t_reopen.output),
      (r_t_react.exit_code, r_t_react.output),
      (r_t_show.exit_code, r_t_show.output),
      (r_t_logs.exit_code, json.loads(r_t_logs.output)),
      (r_dec.exit_code, r_dec.output),
      (r_ev.exit_code, r_ev.output),
      (r_handoff.exit_code, r_handoff.output),
      (r_handoff_json.exit_code, json.loads(r_handoff_json.output)),
    ) == (
      (0, '1\n'),
      (
        0,
        'ID  Stage  Title\n--  -----  -------\n1   s1     Do work\n',
      ),
      (0, ''),
      (0, ''),
      (0, ''),
      (0, ''),
      (0, ''),
      (0, '1\n'),
      (
        0,
        'Status filter: all\n'
        'ID  Status  Target  Stage  Goal  Description  Impact  Attempts  '
        'Required\n'
        '--  ------  ------  -----  ----  -----------  ------  --------  '
        '--------\n'
        '1   open    task 1  1      1     Need input   -       -         '
        'Answer\n',
      ),
      (0, ''),
      (0, ''),
      (0, ''),
      (0, ''),
      (
        0,
        'Task:\n'
        '  ID: 1\n'
        '  Goal ID: 1\n'
        '  Stage ID: 1\n'
        '  Title: Do work\n'
        '  Purpose: Build\n'
        '  Scope: Core\n'
        '  Exclusions: None\n'
        '  Result: Built\n'
        '  Completion Evidence: Green\n'
        '  Status: active\n'
        '  Priority: 5\n'
        f'  Created At: {_TIME_TEXT}\n'
        f'  Started At: {_TIME_TEXT}\n'
        '  Completed At: -\n'
        f'  Updated At: {_TIME_TEXT}\n'
        '  Stage Name: s1\n'
        '  Tags: parity\n'
        '  Title Status: substantive\n'
        'Logs (8):\n'
        '  Log 1:\n'
        '    ID: 1\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: started\n'
        '    Message: Task started\n'
        '  Log 2:\n'
        '    ID: 2\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: note\n'
        '    Message: Progress\n'
        '  Log 3:\n'
        '    ID: 3\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: blocked\n'
        '    Message: Need input\n'
        '  Log 4:\n'
        '    ID: 4\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: blocker-resolved\n'
        '    Message: Answered\n'
        '  Log 5:\n'
        '    ID: 5\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: unblocked\n'
        '    Message: All task blockers resolved\n'
        '  Log 6:\n'
        '    ID: 6\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: cancelled\n'
        '    Message: Retry\n'
        '  Log 7:\n'
        '    ID: 7\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: reopened\n'
        '    Message: Task reopened\n'
        '  Log 8:\n'
        '    ID: 8\n'
        '    Task ID: 1\n'
        f'    Occurred At: {_TIME_TEXT}\n'
        '    Kind: started\n'
        '    Message: Task started\n',
      ),
      (
        0,
        [
          {
            'id': 1,
            'kind': 'started',
            'message': 'Task started',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 2,
            'kind': 'note',
            'message': 'Progress',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 3,
            'kind': 'blocked',
            'message': 'Need input',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 4,
            'kind': 'blocker-resolved',
            'message': 'Answered',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 5,
            'kind': 'unblocked',
            'message': 'All task blockers resolved',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 6,
            'kind': 'cancelled',
            'message': 'Retry',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 7,
            'kind': 'reopened',
            'message': 'Task reopened',
            'occurred_at': _NOW,
            'task_id': 1,
          },
          {
            'id': 8,
            'kind': 'started',
            'message': 'Task started',
            'occurred_at': _NOW,
            'task_id': 1,
          },
        ],
      ),
      (0, '1\n'),
      (0, '1\n'),
      (
        0,
        'Project: demo\n'
        'Status: active\n'
        f'Objective: {"o" * 999}…\n'
        'Project database: .tmp/demo.sqlite3\n'
        'Active goal: 1 (active)\n'
        'Goal text: \\u001b[31mShip\\u001b[0m \\u001b[1mCLI\\u001b[0m\n'
        'Active stage: s1\n'
        'Active task: 1 Do work\n'
        'Summary: Ready\n'
        'Next action: Run stages\n'
        'Relevant task decisions (1 of 1):\n'
        '- 1: Keep pure\n'
        'Relevant task evidence (1 of 1):\n'
        '- 1: Verified\n'
        'Recent task log (5 of 8; more: 0 proj task list-logs --limit 8 '
        '--json -- demo 1):\n'
        '- blocker-resolved: Answered\n'
        '- unblocked: All task blockers resolved\n'
        '- cancelled: Retry\n'
        '- reopened: Task reopened\n'
        '- started: Task started\n'
        'Text projection: 1 fields truncated at 1000 rendered '
        'characters.\n'
        '- Full values: 0 proj handoff --json -- demo\n',
      ),
      (
        0,
        {
          'blocked_goals': [],
          'blocked_tasks': [],
          'blockers': [],
          'decisions': [
            {
              'context_status': 'complete',
              'decided_at': _NOW,
              'goal_id': 1,
              'id': 1,
              'stage_id': 1,
              'summary': 'Keep pure',
              'task_id': 1,
            }
          ],
          'evidence': [
            {
              'captured_at': _NOW,
              'claim': 'Verified',
              'claim_status': 'substantive',
              'context_status': 'complete',
              'goal_id': 1,
              'id': 1,
              'result': '',
              'source': '',
              'stage_generation': 0,
              'stage_id': 1,
              'task_id': 1,
            }
          ],
          'focus': {'id': 1, 'kind': 'task'},
          'goal': {
            'goal': {
              'achieved_at': None,
              'created_at': _NOW,
              'ever_activated': 1,
              'id': 1,
              'started_at': _NOW,
              'status': 'active',
              'status_reason': '',
              'text': ansi_goal,
              'updated_at': _NOW,
            }
          },
          'logs': [
            {
              'kind': 'started',
              'message': 'Task started',
              'occurred_at': _NOW,
            },
            {
              'kind': 'reopened',
              'message': 'Task reopened',
              'occurred_at': _NOW,
            },
            {'kind': 'cancelled', 'message': 'Retry', 'occurred_at': _NOW},
            {
              'kind': 'unblocked',
              'message': 'All task blockers resolved',
              'occurred_at': _NOW,
            },
            {
              'kind': 'blocker-resolved',
              'message': 'Answered',
              'occurred_at': _NOW,
            },
          ],
          'pages': {
            'blocked_goals': {'shown': 0, 'total': 0, 'truncated': False},
            'blocked_tasks': {'shown': 0, 'total': 0, 'truncated': False},
            'blockers': {'shown': 0, 'total': 0, 'truncated': False},
            'decisions': {'shown': 1, 'total': 1, 'truncated': False},
            'evidence': {'shown': 1, 'total': 1, 'truncated': False},
            'task_log': {'shown': 5, 'total': 8, 'truncated': True},
          },
          'path': '.tmp/demo.sqlite3',
          'project': {
            'acceptance': 'All commands work',
            'charter_context_status': 'current',
            'completed_at': None,
            'constraints_text': 'Memdb',
            'created_at': _NOW,
            'id': 1,
            'name': 'demo',
            'non_goals': 'No network',
            'objective': long_objective,
            'scope': 'CLI scope',
            'status': 'active',
            'updated_at': _NOW,
          },
          'retrieval': {
            'blocked_goals': (
              '0 proj goal list --status blocked --json -- demo'
            ),
            'blocked_tasks': (
              '0 proj task list --status blocked --json -- demo'
            ),
            'blockers': '0 proj blocker list --json -- demo',
            'decisions': (
              '0 proj decision list --task 1 --limit 1 --json -- demo'
            ),
            'evidence': (
              '0 proj evidence list --task 1 --limit 1 --json -- demo'
            ),
            'goal': '0 proj goal show --json -- demo 1',
            'project': '0 proj show --json -- demo',
            'ready_tasks': '0 proj task ready -- demo',
            'stage': '0 proj stage list --json -- demo',
            'task': '0 proj task show --json -- demo 1',
            'task_log': (
              '0 proj task list-logs --limit 8 --json -- demo 1'
            ),
          },
          'stage': {
            'achieved_at': None,
            'achievement_evidence_id': None,
            'achievement_generation': 0,
            'achievement_generation_started_at': _NOW,
            'created_at': _NOW,
            'entry_conditions': '',
            'exit_evidence': 'Proof 1',
            'id': 1,
            'name': 's1',
            'outcome': 'Stage 1 done',
            'position': 0,
            'purpose': '',
            'started_at': _NOW,
            'status': 'active',
            'updated_at': _NOW,
          },
          'state': {
            'id': 1,
            'next_action': 'Run stages',
            'revision': 21,
            'summary': 'Ready',
            'updated_at': _NOW,
          },
          'task': {
            'completed_at': None,
            'completion_evidence': 'Green',
            'created_at': _NOW,
            'exclusions': 'None',
            'goal_id': 1,
            'id': 1,
            'priority': 5,
            'purpose': 'Build',
            'result': 'Built',
            'scope': 'Core',
            'stage_id': 1,
            'started_at': _NOW,
            'status': 'active',
            'title': 'Do work',
            'title_status': 'substantive',
            'updated_at': _NOW,
          },
          'text_projection': {
            'character_limit': 1000,
            'full_value_commands': ['0 proj handoff --json -- demo'],
            'truncated_fields': [
              {
                'characters': 1100,
                'path': 'project.objective',
                'retrieval': '0 proj handoff --json -- demo',
              }
            ],
          },
        },
      ),
    )

    recovery_line = next(
      line.removeprefix('- Full values: ')
      for line in r_handoff.output.splitlines()
      if line.startswith('- Full values: ')
    )
    assert recovery_line == '0 proj handoff --json -- demo'
    recovery_run = runner.invoke(
      cli.project_group,
      shlex.split(recovery_line)[2:],
      obj=project_store,
    )
    assert (
      recovery_run.exit_code,
      json.loads(recovery_run.output),
    ) == (0, json.loads(r_handoff_json.output))

    r_t_comp = runner.invoke(
      cli.project_group,
      ('task', 'complete', 'demo', '1'),
      obj=project_store,
    )
    r_s_ach = runner.invoke(
      cli.project_group,
      ('stage', 'achieve', 'demo', 's1', '--evidence', '1'),
      obj=project_store,
    )
    r_s_rem = runner.invoke(
      cli.project_group,
      ('stage', 'remove-dependency', 'demo', 's2', 's1'),
      obj=project_store,
    )
    r_g_blk = runner.invoke(
      cli.project_group,
      (
        'goal',
        'block',
        'demo',
        '--description',
        'Hold',
        '--required',
        'Sign-off',
      ),
      obj=project_store,
    )
    r_g_reopen_err = runner.invoke(
      cli.project_group, ('goal', 'reopen', 'demo', '1'), obj=project_store
    )
    r_blk_goal = runner.invoke(
      cli.project_group,
      (
        'blocker',
        'create',
        'demo',
        '--description',
        'Second hold',
        '--required',
        'Clear',
        '--goal',
        '1',
      ),
      obj=project_store,
    )
    r_g_blk2_res = runner.invoke(
      cli.project_group,
      ('blocker', 'resolve', 'demo', '2', '--resolution', 'Ok 2'),
      obj=project_store,
    )
    r_g_blk3_res = runner.invoke(
      cli.project_group,
      ('blocker', 'resolve', 'demo', '3', '--resolution', 'Ok 3'),
      obj=project_store,
    )
    r_ev_goal = runner.invoke(
      cli.project_group,
      (
        'evidence',
        'create',
        'demo',
        '--claim',
        'Goal proven',
        '--goal',
        '1',
      ),
      obj=project_store,
    )
    r_g_ach = runner.invoke(
      cli.project_group, ('goal', 'achieve', 'demo'), obj=project_store
    )
    r_g2_cancel = runner.invoke(
      cli.project_group,
      ('goal', 'cancel', 'demo', '2', '--reason', 'Done'),
      obj=project_store,
    )
    r_dec_l = runner.invoke(
      cli.project_group, ('decision', 'list', 'demo'), obj=project_store
    )
    r_ev_l = runner.invoke(
      cli.project_group, ('evidence', 'list', 'demo'), obj=project_store
    )
    r_g_list = runner.invoke(
      cli.project_group, ('goal', 'list', 'demo'), obj=project_store
    )
    r_g_show = runner.invoke(
      cli.project_group, ('goal', 'show', 'demo', '1'), obj=project_store
    )
    r_t_list = runner.invoke(
      cli.project_group, ('task', 'list', 'demo'), obj=project_store
    )
    r_arch = runner.invoke(
      cli.project_group, ('archive', 'demo'), obj=project_store
    )

    assert (
      (r_t_comp.exit_code, r_t_comp.output),
      (r_s_ach.exit_code, r_s_ach.output),
      (r_s_rem.exit_code, r_s_rem.output),
      (r_g_blk.exit_code, r_g_blk.output),
      (r_g_reopen_err.exit_code, r_g_reopen_err.output),
      (r_blk_goal.exit_code, r_blk_goal.output),
      (r_g_blk2_res.exit_code, r_g_blk2_res.output),
      (r_g_blk3_res.exit_code, r_g_blk3_res.output),
      (r_ev_goal.exit_code, r_ev_goal.output),
      (r_g_ach.exit_code, r_g_ach.output),
      (r_g2_cancel.exit_code, r_g2_cancel.output),
      (r_dec_l.exit_code, r_dec_l.output),
      (r_ev_l.exit_code, r_ev_l.output),
      (r_g_list.exit_code, r_g_list.output),
      (r_g_show.exit_code, r_g_show.output),
      (r_t_list.exit_code, r_t_list.output),
      (r_arch.exit_code, r_arch.output),
    ) == (
      (0, ''),
      (0, ''),
      (0, ''),
      (0, '2\n'),
      (1, 'Error: A goal cannot reopen while it has open blockers\n'),
      (0, '3\n'),
      (0, ''),
      (0, ''),
      (0, '2\n'),
      (0, ''),
      (0, ''),
      (
        0,
        'ID  Decided                    Summary\n'
        '--  -------------------------  ---------\n'
        f'1   {_TIME_TEXT}  Keep pure\n',
      ),
      (
        0,
        'ID  Captured                   Claim\n'
        '--  -------------------------  -----------\n'
        f'2   {_TIME_TEXT}  Goal proven\n'
        f'1   {_TIME_TEXT}  Verified\n',
      ),
      (
        0,
        'ID  Status     Stages  Text\n'
        '--  ---------  ------  '
        '---------------------------------------------\n'
        '2   cancelled  s2      Temp goal\n'
        '1   achieved   s1      '
        '\\u001b[31mShip\\u001b[0m \\u001b[1mCLI\\u001b[0m\n',
      ),
      (
        0,
        'Goal:\n'
        '  ID: 1\n'
        '  Text: \\u001b[31mShip\\u001b[0m \\u001b[1mCLI\\u001b[0m\n'
        '  Status: achieved\n'
        '  Status Reason: -\n'
        '  Ever Activated: 1\n'
        f'  Created At: {_TIME_TEXT}\n'
        f'  Started At: {_TIME_TEXT}\n'
        f'  Achieved At: {_TIME_TEXT}\n'
        f'  Updated At: {_TIME_TEXT}\n'
        '  Stages (1):\n'
        '    Stage 1:\n'
        '      ID: 1\n'
        '      Name: s1\n'
        '      Status: achieved\n'
        '      Outcome: Stage 1 done\n'
        '  Tasks (1):\n'
        '    Task 1:\n'
        '      ID: 1\n'
        '      Goal ID: 1\n'
        '      Stage ID: 1\n'
        '      Title: Do work\n'
        '      Purpose: Build\n'
        '      Scope: Core\n'
        '      Exclusions: None\n'
        '      Result: Built\n'
        '      Completion Evidence: Green\n'
        '      Status: completed\n'
        '      Priority: 5\n'
        f'      Created At: {_TIME_TEXT}\n'
        f'      Started At: {_TIME_TEXT}\n'
        f'      Completed At: {_TIME_TEXT}\n'
        f'      Updated At: {_TIME_TEXT}\n'
        '      Stage Name: s1\n'
        '      Title Status: substantive\n'
        '  Blockers (3):\n'
        '    Blocker 1:\n'
        '      ID: 3\n'
        '      Goal ID: 1\n'
        '      Stage ID: -\n'
        '      Task ID: -\n'
        '      Description: Second hold\n'
        '      Impact: -\n'
        '      Attempts: -\n'
        '      Required: Clear\n'
        '      Status: resolved\n'
        f'      Opened At: {_TIME_TEXT}\n'
        f'      Resolved At: {_TIME_TEXT}\n'
        '      Resolution: Ok 3\n'
        '      Target Kind: goal\n'
        '      Target ID: 1\n'
        '    Blocker 2:\n'
        '      ID: 2\n'
        '      Goal ID: 1\n'
        '      Stage ID: -\n'
        '      Task ID: -\n'
        '      Description: Hold\n'
        '      Impact: -\n'
        '      Attempts: -\n'
        '      Required: Sign-off\n'
        '      Status: resolved\n'
        f'      Opened At: {_TIME_TEXT}\n'
        f'      Resolved At: {_TIME_TEXT}\n'
        '      Resolution: Ok 2\n'
        '      Target Kind: goal\n'
        '      Target ID: 1\n'
        '    Blocker 3:\n'
        '      ID: 1\n'
        '      Goal ID: 1\n'
        '      Stage ID: 1\n'
        '      Task ID: 1\n'
        '      Description: Need input\n'
        '      Impact: -\n'
        '      Attempts: -\n'
        '      Required: Answer\n'
        '      Status: resolved\n'
        f'      Opened At: {_TIME_TEXT}\n'
        f'      Resolved At: {_TIME_TEXT}\n'
        '      Resolution: Answered\n'
        '      Target Kind: task\n'
        '      Target ID: 1\n'
        '  Evidence (2):\n'
        '    Evidence 1:\n'
        '      ID: 2\n'
        '      Goal ID: 1\n'
        '      Stage ID: -\n'
        '      Task ID: -\n'
        '      Claim: Goal proven\n'
        '      Source: -\n'
        '      Result: -\n'
        f'      Captured At: {_TIME_TEXT}\n'
        '      Context Status: complete\n'
        '      Claim Status: substantive\n'
        '      Stage Generation: -\n'
        '    Evidence 2:\n'
        '      ID: 1\n'
        '      Goal ID: 1\n'
        '      Stage ID: 1\n'
        '      Task ID: 1\n'
        '      Claim: Verified\n'
        '      Source: -\n'
        '      Result: -\n'
        f'      Captured At: {_TIME_TEXT}\n'
        '      Context Status: complete\n'
        '      Claim Status: substantive\n'
        '      Stage Generation: 0\n'
        '  Decisions (1):\n'
        '    Decision 1:\n'
        '      ID: 1\n'
        '      Goal ID: 1\n'
        '      Stage ID: 1\n'
        '      Task ID: 1\n'
        '      Summary: Keep pure\n'
        '      Rationale: -\n'
        '      Alternatives: -\n'
        '      Consequences: -\n'
        f'      Decided At: {_TIME_TEXT}\n'
        '      Context Status: complete\n',
      ),
      (
        0,
        'ID  Status     Stage  Goal  Title    Tags\n'
        '--  ---------  -----  ----  -------  ------\n'
        '1   completed  s1     1     Do work  parity\n',
      ),
      (0, '/memdb-root/.tmp/archive/demo-1000.sqlite3\n'),
    )


def test_path_context_forwarding_and_from_root_error_adaptation(
  monkeypatch: MonkeyPatch,
) -> None:
  runner = CliRunner()
  virtual_root = Path('/virtual-clean-root')

  def missing_scandir(target: str | os.PathLike[str]) -> object:
    raise FileNotFoundError(
      errno.ENOENT, os.strerror(errno.ENOENT), os.fspath(target)
    )

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda self: virtual_root)
    mp.setattr(store.os, 'scandir', missing_scandir)
    mp.setattr(
      Path, 'exists', lambda _self, *, follow_symlinks=True: False
    )
    ok = runner.invoke(cli.project_group, ('list',), obj=virtual_root)
  assert (ok.exit_code, ok.output) == (
    0,
    'Name  Status  Updated  Objective\n----  ------  -------  ---------\n',
  )

  def broken_resolve(self: Path) -> Path:
    raise OSError('unresolvable')

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', broken_resolve)
    help_without_root = runner.invoke(
      cli.project_group, ('goal', 'show', '--help')
    )
    failed = runner.invoke(
      cli.project_group, ('--root', str(virtual_root), 'list')
    )
  with pytest.raises(RuntimeError) as bad_ctx_err:
    runner.invoke(
      cli.project_group,
      ('list',),
      obj='bad-context',
      catch_exceptions=False,
    )

  bad_root_arg = os.fsdecode(b'/virtual-clean-root/bad-\xff')
  side_effects: list[Path] = []

  def record_mkdir(
    self: Path, _mode: int = 0o777, _parents: bool = False, **_kw: object
  ) -> None:
    side_effects.append(self)

  def record_rename(self: Path, target: str | os.PathLike[str]) -> Path:
    side_effects.append(self)
    return Path(target)

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'resolve', lambda self: self)
    mp.setattr(Path, 'mkdir', record_mkdir)
    mp.setattr(Path, 'rename', record_rename)
    bad_create = runner.invoke(
      cli.project_group,
      ('--root', bad_root_arg, 'create', 'demo', '--objective', 'O'),
    )
    bad_list = runner.invoke(
      cli.project_group, ('--root', bad_root_arg, 'list', '--json')
    )
    bad_show = runner.invoke(
      cli.project_group, ('--root', bad_root_arg, 'show', 'demo')
    )
    bad_archive = runner.invoke(
      cli.project_group, ('--root', bad_root_arg, 'archive', 'demo')
    )
  expected_utf8_err = (
    'Error: Project root path is not valid UTF-8: '
    '/virtual-clean-root/bad-\\xff\n'
  )

  assert (
    help_without_root.exit_code,
    help_without_root.output,
    failed.exit_code,
    failed.output,
    str(bad_ctx_err.value),
    (bad_create.exit_code, bad_create.output),
    (bad_list.exit_code, bad_list.output),
    (bad_show.exit_code, bad_show.output),
    (bad_archive.exit_code, bad_archive.output),
    bad_create.output.encode('utf-8'),
    side_effects,
  ) == (
    0,
    'Usage: project goal show [OPTIONS] NAME [GOAL]\n\n'
    'Options:\n'
    '  --json  Output JSON instead of the human-readable view.\n'
    '  --help  Show this message and exit.\n',
    1,
    f'Error: Could not resolve project root {virtual_root}: '
    'unresolvable\n',
    'Unsupported project store context: str',
    (1, expected_utf8_err),
    (1, expected_utf8_err),
    (1, expected_utf8_err),
    (1, expected_utf8_err),
    expected_utf8_err.encode('utf-8'),
    [],
  )


def test_single_quote_heavy_project_name_handoff_round_trip() -> None:
  runner = CliRunner()
  quotes_name = "'" * 200
  quoted_token = "\\'" * 200
  with _memdb_cli() as (_backend, project_store):
    r_create = runner.invoke(
      cli.project_group,
      ('create', quotes_name, '--objective', 'Quote parity'),
      obj=project_store,
    )
    r_handoff = runner.invoke(
      cli.project_group,
      ('handoff', '--', quotes_name),
      obj=project_store,
    )
    r_handoff_json = runner.invoke(
      cli.project_group,
      ('handoff', '--json', '--', quotes_name),
      obj=project_store,
    )
    handoff_payload = json.loads(r_handoff_json.output)
    assert (
      (r_create.exit_code, r_create.output),
      (r_handoff.exit_code, r_handoff.output),
      (
        r_handoff_json.exit_code,
        handoff_payload,
        {
          key: shlex.split(val)
          for key, val in handoff_payload['retrieval'].items()
          if val is not None
        },
      ),
    ) == (
      (0, f'/memdb-root/.tmp/{quotes_name}.sqlite3\n'),
      (
        0,
        f'Project: {quotes_name}\n'
        'Status: active\n'
        'Objective: Quote parity\n'
        f'Project database: .tmp/{quotes_name}.sqlite3\n'
        'Active goal: -\n'
        'Goal text: -\n'
        'Active stage: -\n'
        'Active task: -\n'
        'Summary: -\n'
        'Next action: -\n',
      ),
      (
        0,
        {
          'blocked_goals': [],
          'blocked_tasks': [],
          'blockers': [],
          'decisions': [],
          'evidence': [],
          'focus': {'id': None, 'kind': None},
          'goal': None,
          'logs': [],
          'pages': {
            'blocked_goals': {'shown': 0, 'total': 0, 'truncated': False},
            'blocked_tasks': {'shown': 0, 'total': 0, 'truncated': False},
            'blockers': {'shown': 0, 'total': 0, 'truncated': False},
            'decisions': {'shown': 0, 'total': 0, 'truncated': False},
            'evidence': {'shown': 0, 'total': 0, 'truncated': False},
            'task_log': {'shown': 0, 'total': 0, 'truncated': False},
          },
          'path': f'.tmp/{quotes_name}.sqlite3',
          'project': {
            'acceptance': '',
            'charter_context_status': 'current',
            'completed_at': None,
            'constraints_text': '',
            'created_at': _NOW,
            'id': 1,
            'name': quotes_name,
            'non_goals': '',
            'objective': 'Quote parity',
            'scope': '',
            'status': 'active',
            'updated_at': _NOW,
          },
          'retrieval': {
            'blocked_goals': (
              f'0 proj goal list --status blocked --json -- {quoted_token}'
            ),
            'blocked_tasks': (
              f'0 proj task list --status blocked --json -- {quoted_token}'
            ),
            'blockers': f'0 proj blocker list --json -- {quoted_token}',
            'decisions': f'0 proj decision list --json -- {quoted_token}',
            'evidence': f'0 proj evidence list --json -- {quoted_token}',
            'goal': None,
            'project': f'0 proj show --json -- {quoted_token}',
            'ready_tasks': f'0 proj task ready -- {quoted_token}',
            'stage': None,
            'task': None,
            'task_log': None,
          },
          'stage': None,
          'state': {
            'id': 1,
            'next_action': '',
            'revision': 0,
            'summary': '',
            'updated_at': _NOW,
          },
          'task': None,
          'text_projection': {
            'character_limit': 1000,
            'full_value_commands': [],
            'truncated_fields': [],
          },
        },
        {
          'blocked_goals': [
            '0',
            'proj',
            'goal',
            'list',
            '--status',
            'blocked',
            '--json',
            '--',
            quotes_name,
          ],
          'blocked_tasks': [
            '0',
            'proj',
            'task',
            'list',
            '--status',
            'blocked',
            '--json',
            '--',
            quotes_name,
          ],
          'blockers': [
            '0',
            'proj',
            'blocker',
            'list',
            '--json',
            '--',
            quotes_name,
          ],
          'decisions': [
            '0',
            'proj',
            'decision',
            'list',
            '--json',
            '--',
            quotes_name,
          ],
          'evidence': [
            '0',
            'proj',
            'evidence',
            'list',
            '--json',
            '--',
            quotes_name,
          ],
          'project': ['0', 'proj', 'show', '--json', '--', quotes_name],
          'ready_tasks': ['0', 'proj', 'task', 'ready', '--', quotes_name],
        },
      ),
    )


def test_list_skips_non_project_databases_and_rejects_broken_projects(
  v7_snapshot: bytes,
) -> None:
  runner = CliRunner()
  with _memdb_cli() as (backend, project_store):
    project_store.create_project(core.ProjectName.parse('alpha'), _CHARTER)
    project_store.create_project(core.ProjectName.parse('beta'), _CHARTER)
    beta_raw = backend.open_raw(
      PurePosixPath('.tmp/beta.sqlite3'), mode='rw'
    )
    try:
      downgrade_v7_to_v6(beta_raw)
      beta_raw.commit()
    finally:
      beta_raw.close()

    telemetry_raw = backend.open_raw(
      PurePosixPath('.tmp/task99-abc.sqlite3'), mode='rwc'
    )
    try:
      telemetry_raw.executescript(
        """
        PRAGMA user_version = 1;
        CREATE TABLE run (id INTEGER PRIMARY KEY);
        CREATE TABLE run_event (id INTEGER PRIMARY KEY);
        CREATE TABLE test_started (id INTEGER PRIMARY KEY);
        CREATE TABLE test_result (id INTEGER PRIMARY KEY);
        CREATE TABLE resource_sample (id INTEGER PRIMARY KEY);
        """
      )
      telemetry_raw.commit()
    finally:
      telemetry_raw.close()

    scratch_raw = backend.open_raw(
      PurePosixPath('.tmp/notes.sqlite3'), mode='rwc'
    )
    try:
      scratch_raw.execute(
        'CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)'
      )
      scratch_raw.commit()
    finally:
      scratch_raw.close()

    backend.seed(PurePosixPath('.tmp/zero-byte.sqlite3'), b'')
    dot_raw = backend.open_raw(PurePosixPath('.tmp/.sqlite3'), mode='rwc')
    try:
      dot_raw.execute('CREATE TABLE x (id INT)')
      dot_raw.commit()
    finally:
      dot_raw.close()
    double_raw = backend.open_raw(
      PurePosixPath('.tmp/notes.sqlite3.sqlite3'), mode='rwc'
    )
    try:
      double_raw.execute('CREATE TABLE y (id INT)')
      double_raw.commit()
    finally:
      double_raw.close()

    r_list = runner.invoke(cli.project_group, ('list',), obj=project_store)
    r_list_json = runner.invoke(
      cli.project_group, ('list', '--json'), obj=project_store
    )
    r_show_telemetry = runner.invoke(
      cli.project_group, ('show', 'task99-abc'), obj=project_store
    )
    r_create_scratch = runner.invoke(
      cli.project_group,
      ('create', 'notes', '--objective', 'Should fail'),
      obj=project_store,
    )
    r_archive_scratch = runner.invoke(
      cli.project_group,
      ('archive', 'notes'),
      obj=project_store,
    )

    assert (
      (r_list.exit_code, r_list.output),
      (r_list_json.exit_code, json.loads(r_list_json.output)),
      (r_show_telemetry.exit_code, r_show_telemetry.output),
      (r_create_scratch.exit_code, r_create_scratch.output),
      (r_archive_scratch.exit_code, r_archive_scratch.output),
    ) == (
      (
        0,
        'Name   Status  Updated                    Objective\n'
        '-----  ------  -------------------------  ------------------\n'
        f'alpha  active  {_TIME_TEXT}  Deliver CLI parity\n'
        f'beta   active  {_TIME_TEXT}  Deliver CLI parity\n',
      ),
      (
        0,
        [
          {
            'name': 'alpha',
            'objective': 'Deliver CLI parity',
            'path': '/memdb-root/.tmp/alpha.sqlite3',
            'status': 'active',
            'updated_at': _NOW,
          },
          {
            'name': 'beta',
            'objective': 'Deliver CLI parity',
            'path': '/memdb-root/.tmp/beta.sqlite3',
            'status': 'active',
            'updated_at': _NOW,
          },
        ],
      ),
      (
        1,
        'Error: Unsupported project schema version 1; expected 7: '
        '/memdb-root/.tmp/task99-abc.sqlite3\n',
      ),
      (
        1,
        'Error: Cannot overwrite non-project SQLite database: '
        '/memdb-root/.tmp/notes.sqlite3\n',
      ),
      (
        1,
        'Error: Cannot archive non-project SQLite database: '
        '/memdb-root/.tmp/notes.sqlite3\n',
      ),
    )

  corrupt_bytes = bytearray(v7_snapshot)
  corrupt_bytes[100:200] = b'\xff' * 100
  with _memdb_cli() as (backend, project_store):
    backend.seed(
      PurePosixPath('.tmp/corrupt.sqlite3'), bytes(corrupt_bytes)
    )
    r_corrupt_text = runner.invoke(
      cli.project_group, ('list',), obj=project_store
    )
    r_corrupt_json = runner.invoke(
      cli.project_group, ('list', '--json'), obj=project_store
    )

  with _memdb_cli() as (backend, project_store):
    backend.seed(
      PurePosixPath('.tmp/not-sqlite.sqlite3'), b'not a sqlite database'
    )
    r_non_sqlite_text = runner.invoke(
      cli.project_group, ('list',), obj=project_store
    )
    r_non_sqlite_json = runner.invoke(
      cli.project_group, ('list', '--json'), obj=project_store
    )

  with _memdb_cli() as (backend, project_store):
    project_store.create_project(
      core.ProjectName.parse('bad-version'), _CHARTER
    )
    bad_raw = backend.open_raw(
      PurePosixPath('.tmp/bad-version.sqlite3'), mode='rw'
    )
    try:
      bad_raw.execute('PRAGMA user_version = 99')
      bad_raw.commit()
    finally:
      bad_raw.close()
    r_version_text = runner.invoke(
      cli.project_group, ('list',), obj=project_store
    )
    r_version_json = runner.invoke(
      cli.project_group, ('list', '--json'), obj=project_store
    )

  with _memdb_cli() as (backend, project_store):
    backend.seed(PurePosixPath('.tmp/demo.sqlite3'), bytes(corrupt_bytes))
    r_archive_corrupt = runner.invoke(
      cli.project_group, ('archive', 'demo'), obj=project_store
    )
    backend.seed(
      PurePosixPath('.tmp/demo.sqlite3'), b'not a sqlite database'
    )
    r_create_corrupt = runner.invoke(
      cli.project_group,
      ('create', 'demo', '--objective', 'Recovered from corrupt'),
      obj=project_store,
    )

  with _memdb_cli() as (backend, project_store):
    backend.seed(
      PurePosixPath('.tmp/bad\nInjected\x1b]52;\x07.sqlite3'), v7_snapshot
    )
    r_control_stem = runner.invoke(
      cli.project_group, ('list',), obj=project_store
    )

  assert (
    (r_corrupt_text.exit_code, r_corrupt_text.output),
    (r_corrupt_json.exit_code, r_corrupt_json.output),
    (r_non_sqlite_text.exit_code, r_non_sqlite_text.output),
    (r_non_sqlite_json.exit_code, r_non_sqlite_json.output),
    (r_version_text.exit_code, r_version_text.output),
    (r_version_json.exit_code, r_version_json.output),
    (r_archive_corrupt.exit_code, r_archive_corrupt.output),
    (r_create_corrupt.exit_code, r_create_corrupt.output),
    (r_control_stem.exit_code, r_control_stem.output),
  ) == (
    (
      1,
      'Error: Project database could not be validated: '
      '/memdb-root/.tmp/corrupt.sqlite3: '
      'database disk image is malformed\n',
    ),
    (
      1,
      'Error: Project database could not be validated: '
      '/memdb-root/.tmp/corrupt.sqlite3: '
      'database disk image is malformed\n',
    ),
    (
      1,
      'Error: Project database could not be validated: '
      '/memdb-root/.tmp/not-sqlite.sqlite3: '
      'file is not a database\n',
    ),
    (
      1,
      'Error: Project database could not be validated: '
      '/memdb-root/.tmp/not-sqlite.sqlite3: '
      'file is not a database\n',
    ),
    (
      1,
      'Error: Unsupported project schema version 99; expected 7: '
      '/memdb-root/.tmp/bad-version.sqlite3\n',
    ),
    (
      1,
      'Error: Unsupported project schema version 99; expected 7: '
      '/memdb-root/.tmp/bad-version.sqlite3\n',
    ),
    (0, '/memdb-root/.tmp/archive/demo-1000.sqlite3\n'),
    (0, '/memdb-root/.tmp/demo.sqlite3\n'),
    (
      1,
      'Error: Project names must be printable, non-empty single path '
      'components of at most 200 characters without the .sqlite3 suffix: '
      '/memdb-root/.tmp/bad\\nInjected\\u001b]52;\\u0007.sqlite3\n',
    ),
  )
