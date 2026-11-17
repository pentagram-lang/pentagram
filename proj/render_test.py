import json

import pytest

from proj import core, render, service

_TIME = 1_700_000_000
_TIME_TEXT = '2023-11-14T22:13:20+00:00'


def _project_record(
  *,
  name: str = 'sample',
  objective: str = 'Build output',
  charter_context_status: core.CharterContextStatus = 'current',
  status: core.ProjectStatus = 'active',
) -> service.ProjectRecord:
  return service.ProjectRecord(
    id=1,
    name=name,
    objective=objective,
    scope='Render layer',
    non_goals='Storage IO',
    constraints_text='Pure formatting',
    acceptance='Suite passes',
    created_at=_TIME,
    updated_at=_TIME,
    charter_context_status=charter_context_status,
    status=status,
    completed_at=None,
  )


def _sample_retrieval(
  *,
  goal: str | None = 'show-goal 7',
  stage: str | None = 'list-stages',
  task: str | None = 'show-task 12',
  blockers: str = 'list-blockers',
  task_log: str | None = 'list-logs 12',
) -> render.HandoffRetrieval:
  return render.HandoffRetrieval(
    project='show-project',
    goal=goal,
    stage=stage,
    task=task,
    blocked_tasks='list-blocked-tasks',
    blocked_goals='list-blocked-goals',
    blockers=blockers,
    ready_tasks='list-ready',
    decisions='list-decisions',
    evidence='list-evidence',
    task_log=task_log,
  )


def _command_for_path(path: tuple[str | int, ...]) -> str:
  return f'retrieve:{".".join(str(part) for part in path)}'


def test_public_exports_and_formatted_primitives() -> None:
  assert set(render.__all__) == {
    'HandoffJson',
    'HandoffProjection',
    'HandoffRetrieval',
    'HandoffView',
    'TextHandoffView',
    'TruncatedField',
    'build_handoff_json',
    'format_blocker_list',
    'format_decision_list',
    'format_evidence_list',
    'format_goal_details',
    'format_goal_list',
    'format_handoff',
    'format_project_details',
    'format_project_list',
    'format_ready_task_list',
    'format_stage_list',
    'format_task_details',
    'format_task_list',
    'format_task_log_list',
  }

  table_text = render.format_project_list(
    (
      service.ProjectSummary(
        name='中',
        status='active',
        objective='e\u0301',
        updated_at=_TIME,
        path='.tmp/a.sqlite3',
      ),
      service.ProjectSummary(
        name='e\u0301',
        status='active',
        objective='-',
        updated_at=_TIME,
        path='.tmp/b.sqlite3',
      ),
      service.ProjectSummary(
        name='\x07',
        status='active',
        objective='-\n',
        updated_at=_TIME,
        path='.tmp/c.sqlite3',
      ),
      service.ProjectSummary(
        name='x',
        status='active',
        objective='a\nb\u2028c\u2029"\x7f\x9f\\',
        updated_at=_TIME,
        path='.tmp/d.sqlite3',
      ),
    )
  )
  assert table_text == (
    'Name    Status  Updated                    '
    'Objective\n'
    '------  ------  -------------------------  '
    '---------------------------------\n'
    f'中      active  {_TIME_TEXT}  e\u0301\n'
    f'e\u0301       active  {_TIME_TEXT}  "-"\n'
    f'\\u0007  active  {_TIME_TEXT}  -\\n\n'
    f'x       active  {_TIME_TEXT}  '
    'a\\nb\\u2028c\\u2029\\"\\u007f\\u009f\\\\'
  )


def test_collection_formatters() -> None:
  assert (
    render.format_project_list(()),
    render.format_project_list(
      (
        service.ProjectSummary(
          name='acme',
          status='active',
          objective='brief',
          updated_at=_TIME,
          path='.tmp/acme.sqlite3',
        ),
      )
    ),
    render.format_goal_list(
      (
        service.GoalListItem(
          id=7,
          text='write tests',
          status='pending',
          status_reason='',
          ever_activated=1,
          created_at=_TIME,
          started_at=_TIME,
          achieved_at=None,
          updated_at=_TIME,
          is_active=0,
          stage_names='Build',
        ),
      )
    ),
    render.format_stage_list(
      (
        service.StageListItem(
          id=3,
          name='Build',
          outcome='Code',
          purpose='',
          entry_conditions='',
          exit_evidence='',
          position=0,
          achievement_generation=0,
          achievement_generation_started_at=_TIME,
          created_at=_TIME,
          updated_at=_TIME,
          status='active',
          started_at=_TIME,
          achieved_at=None,
          achievement_evidence_id=None,
          dependencies='',
        ),
      )
    ),
  ) == (
    'Name  Status  Updated  Objective\n----  ------  -------  ---------',
    'Name  Status  Updated                    Objective\n'
    '----  ------  -------------------------  ---------\n'
    f'acme  active  {_TIME_TEXT}  brief',
    'ID  Status   Stages  Text\n'
    '--  -------  ------  -----------\n'
    '7   pending  Build   write tests',
    'ID  Status  Name   Outcome\n'
    '--  ------  -----  -------\n'
    '3   active  Build  Code',
  )

  task_item = service.TaskRecord(
    id=12,
    goal_id=None,
    stage_id=3,
    title='',
    purpose='',
    scope='',
    exclusions='',
    result='',
    completion_evidence='',
    status='active',
    priority=0,
    created_at=_TIME,
    started_at=_TIME,
    completed_at=None,
    updated_at=_TIME,
    stage_name='Build',
    tags='test',
    title_status='legacy-blank',
  )
  log_item = service.TaskLogRecord(
    id=1, task_id=12, occurred_at=_TIME, kind='note', message='started'
  )
  decision_item = service.DecisionRecord(
    id=1,
    goal_id=None,
    stage_id=None,
    task_id=None,
    summary='accepted',
    rationale='',
    alternatives='',
    consequences='',
    decided_at=_TIME,
    context_status='legacy-unresolved',
  )
  blocker_item = service.BlockerRecord(
    id=2,
    goal_id=None,
    stage_id=3,
    task_id=9,
    description='wait',
    impact='',
    attempts='',
    required='review',
    status='open',
    opened_at=_TIME,
    resolved_at=None,
    resolution='',
    target_kind='task',
    target_id=9,
  )
  evidence_item = service.EvidenceRecord(
    id=4,
    goal_id=None,
    stage_id=None,
    task_id=None,
    claim='',
    source='',
    result='',
    captured_at=_TIME,
    context_status='legacy-unresolved',
    claim_status='legacy-blank',
    stage_generation=None,
  )

  assert (
    render.format_task_list((task_item,)),
    render.format_ready_task_list((task_item,)),
    render.format_task_log_list((log_item,), limit=1),
    render.format_decision_list((decision_item,), limit=2),
    render.format_blocker_list((blocker_item,), 'open'),
    render.format_evidence_list((evidence_item,), limit=1),
  ) == (
    'ID                       Status  Stage  Goal  Title  Tags\n'
    '-----------------------  ------  -----  ----  -----  ----\n'
    '12 [legacy blank title]  active  Build  -     -      test',
    'ID                       Stage  Title\n'
    '-----------------------  -----  -----\n'
    '12 [legacy blank title]  Build  -',
    'Time                       Kind  Message\n'
    '-------------------------  ----  -------\n'
    f'{_TIME_TEXT}  note  started\n'
    'Limit reached (1 rows); more records may exist. '
    'Increase --limit to retrieve more.',
    'ID                             Decided                    Summary\n'
    '-----------------------------  -------------------------  --------\n'
    f'1 [legacy unresolved context]  {_TIME_TEXT}  accepted',
    'Status filter: open\n'
    'ID  Status  Target  Stage  Goal  Description  Impact  Attempts  '
    'Required\n'
    '--  ------  ------  -----  ----  -----------  ------  --------  '
    '--------\n'
    '2   open    task 9  3      -     wait         -       -         '
    'review',
    'ID                                                  '
    'Captured                   Claim\n'
    '--------------------------------------------------  '
    '-------------------------  -----\n'
    '4 [legacy unresolved context] [legacy blank claim]  '
    f'{_TIME_TEXT}  -\n'
    'Limit reached (1 rows); more records may exist. '
    'Increase --limit to retrieve more.',
  )


def test_detail_formatters_fields_and_timestamp_validation() -> None:
  goal_details = service.GoalDetails(
    goal=service.GoalRecord(
      id=7,
      text='Ship output',
      status='active',
      status_reason='',
      ever_activated=1,
      created_at=_TIME,
      started_at=_TIME,
      achieved_at=None,
      updated_at=_TIME,
    ),
    stages=(
      service.GoalStageSummary(
        id=3, name='Build', status='active', outcome='Clear output'
      ),
    ),
    tasks=(),
    blockers=(),
    evidence=(),
    decisions=(),
  )
  project_view = service.ProjectView(
    path='.tmp/sample.sqlite3',
    project=_project_record(),
    state=service.ProjectState(
      id=1,
      summary='Current',
      next_action='Test output',
      updated_at=_TIME,
      revision=2,
    ),
    goal=None,
    charter_history=(
      service.CharterHistoryRecord(
        id=1,
        objective='Initial objective',
        scope='Initial scope',
        non_goals='Old non-goals',
        constraints_text='Old constraints',
        acceptance='Old acceptance',
        replaced_at=_TIME,
      ),
    ),
  )
  task_details = service.TaskDetails(
    task=service.TaskRecord(
      id=12,
      goal_id=None,
      stage_id=3,
      title='Review output',
      purpose='Verify',
      scope='Render',
      exclusions='CLI',
      result='Exact text',
      completion_evidence='Tests pass',
      status='active',
      priority=1,
      created_at=_TIME,
      started_at=_TIME,
      completed_at=None,
      updated_at=_TIME,
      stage_name='Build',
      tags='render',
      title_status='substantive',
    ),
    logs=(
      service.TaskLogRecord(
        id=1, task_id=12, occurred_at=_TIME, kind='note', message='Started'
      ),
    ),
  )

  assert (
    render.format_goal_details(goal_details),
    render.format_project_details(project_view),
    render.format_task_details(task_details, limit=1),
  ) == (
    'Goal:\n'
    '  ID: 7\n'
    '  Text: Ship output\n'
    '  Status: active\n'
    '  Status Reason: -\n'
    '  Ever Activated: 1\n'
    f'  Created At: {_TIME_TEXT}\n'
    f'  Started At: {_TIME_TEXT}\n'
    '  Achieved At: -\n'
    f'  Updated At: {_TIME_TEXT}\n'
    '  Stages (1):\n'
    '    Stage 1:\n'
    '      ID: 3\n'
    '      Name: Build\n'
    '      Status: active\n'
    '      Outcome: Clear output\n'
    '  Tasks (0):\n'
    '  Blockers (0):\n'
    '  Evidence (0):\n'
    '  Decisions (0):',
    'Project:\n'
    '  ID: 1\n'
    '  Name: sample\n'
    '  Objective: Build output\n'
    '  Scope: Render layer\n'
    '  Non-goals: Storage IO\n'
    '  Constraints: Pure formatting\n'
    '  Acceptance: Suite passes\n'
    f'  Created At: {_TIME_TEXT}\n'
    f'  Updated At: {_TIME_TEXT}\n'
    '  Charter Context Status: current\n'
    '  Status: active\n'
    '  Completed At: -\n'
    'Database path: .tmp/sample.sqlite3\n'
    'Project state:\n'
    '  ID: 1\n'
    '  Summary: Current\n'
    '  Next Action: Test output\n'
    f'  Updated At: {_TIME_TEXT}\n'
    '  Revision: 2\n'
    'Active goal: -\n'
    'Previous charters (1):\n'
    '  Previous charter 1:\n'
    '    ID: 1\n'
    '    Objective: Initial objective\n'
    '    Scope: Initial scope\n'
    '    Non-goals: Old non-goals\n'
    '    Constraints: Old constraints\n'
    '    Acceptance: Old acceptance\n'
    f'    Replaced At: {_TIME_TEXT}',
    'Task:\n'
    '  ID: 12\n'
    '  Goal ID: -\n'
    '  Stage ID: 3\n'
    '  Title: Review output\n'
    '  Purpose: Verify\n'
    '  Scope: Render\n'
    '  Exclusions: CLI\n'
    '  Result: Exact text\n'
    '  Completion Evidence: Tests pass\n'
    '  Status: active\n'
    '  Priority: 1\n'
    f'  Created At: {_TIME_TEXT}\n'
    f'  Started At: {_TIME_TEXT}\n'
    '  Completed At: -\n'
    f'  Updated At: {_TIME_TEXT}\n'
    '  Stage Name: Build\n'
    '  Tags: render\n'
    '  Title Status: substantive\n'
    'Logs (1):\n'
    '  Log 1:\n'
    '    ID: 1\n'
    '    Task ID: 12\n'
    f'    Occurred At: {_TIME_TEXT}\n'
    '    Kind: note\n'
    '    Message: Started\n'
    'Logs: Limit reached (1 rows); more records may exist. '
    'Increase --limit to retrieve more.',
  )


def test_handoff_rendering_projection_and_json_dict() -> None:
  long_objective = 'a' * 1_200
  long_summary = '\n' * 600
  view = render.HandoffView(
    data=service.HandoffData(
      path='.tmp/sample.sqlite3',
      project=_project_record(
        objective=long_objective,
        charter_context_status='legacy-incomplete',
      ),
      state=service.ProjectState(
        id=1,
        summary=long_summary,
        next_action='-',
        updated_at=_TIME,
        revision=3,
      ),
      goal=service.ActiveGoalRef(
        goal=service.GoalRecord(
          id=7,
          text='Goal text',
          status='active',
          status_reason='',
          ever_activated=1,
          created_at=_TIME,
          started_at=_TIME,
          achieved_at=None,
          updated_at=_TIME,
        )
      ),
      stage=service.StageRecord(
        id=3,
        name='Stage\u2028One',
        outcome='Done',
        purpose='',
        entry_conditions='',
        exit_evidence='',
        position=0,
        achievement_generation=0,
        achievement_generation_started_at=_TIME,
        created_at=_TIME,
        updated_at=_TIME,
        status='active',
        started_at=_TIME,
        achieved_at=None,
        achievement_evidence_id=None,
      ),
      task=service.HandoffTaskRecord(
        id=12,
        goal_id=7,
        stage_id=3,
        title='',
        purpose='',
        scope='',
        exclusions='',
        result='',
        completion_evidence='',
        status='active',
        priority=0,
        created_at=_TIME,
        started_at=_TIME,
        completed_at=None,
        updated_at=_TIME,
        title_status='legacy-blank',
      ),
      blocked_tasks=(
        service.BlockedTaskSummary(
          id=15,
          title='',
          status='blocked',
          goal_id=7,
          stage_id=3,
          stage_name='Build',
          updated_at=_TIME,
          title_status='legacy-blank',
        ),
      ),
      blocked_goals=(
        service.BlockedGoalSummary(
          id=8,
          text='Blocked goal',
          status='blocked',
          status_reason='Need review',
          updated_at=_TIME,
        ),
      ),
      blockers=(
        service.HandoffBlockerSummary(
          id=2,
          goal_id=7,
          stage_id=3,
          task_id=12,
          description='Wait',
          required='Sign-off',
          opened_at=_TIME,
          target_kind='task',
          target_id=12,
        ),
      ),
      decisions=(
        service.HandoffDecisionSummary(
          id=5,
          goal_id=None,
          stage_id=None,
          task_id=12,
          summary='Keep pure',
          decided_at=_TIME,
          context_status='legacy-unresolved',
        ),
      ),
      evidence=(
        service.EvidenceRecord(
          id=6,
          goal_id=None,
          stage_id=None,
          task_id=12,
          claim='',
          source='',
          result='',
          captured_at=_TIME,
          context_status='legacy-unresolved',
          claim_status='legacy-blank',
          stage_generation=None,
        ),
      ),
      logs=(
        service.HandoffLogEntry(
          occurred_at=_TIME, kind='note', message='old'
        ),
        service.HandoffLogEntry(
          occurred_at=_TIME + 1, kind='note', message='new'
        ),
      ),
      focus=service.HandoffFocus(kind='task', id=12),
      pages=service.HandoffPages(
        blocked_tasks=service.HandoffPage(
          shown=1, total=1, truncated=False
        ),
        blocked_goals=service.HandoffPage(
          shown=1, total=1, truncated=False
        ),
        blockers=service.HandoffPage(shown=1, total=2, truncated=True),
        decisions=service.HandoffPage(shown=1, total=1, truncated=False),
        evidence=service.HandoffPage(shown=1, total=1, truncated=False),
        task_log=service.HandoffPage(shown=2, total=5, truncated=True),
      ),
    ),
    retrieval=_sample_retrieval(),
  )

  exact_limit_view = render.HandoffView(
    data=service.HandoffData(
      path='.tmp/exact.sqlite3',
      project=_project_record(objective='x' * core.HANDOFF_TEXT_LIMIT),
      state=service.ProjectState(
        id=1, summary='-', next_action='', updated_at=_TIME, revision=1
      ),
      goal=None,
      stage=None,
      task=None,
      blocked_tasks=(),
      blocked_goals=(),
      blockers=(),
      decisions=(),
      evidence=(),
      logs=(),
      focus=service.HandoffFocus(kind=None, id=None),
      pages=service.HandoffPages(
        blocked_tasks=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blocked_goals=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blockers=service.HandoffPage(shown=0, total=0, truncated=False),
        decisions=service.HandoffPage(shown=0, total=0, truncated=False),
        evidence=service.HandoffPage(shown=0, total=0, truncated=False),
        task_log=service.HandoffPage(shown=0, total=0, truncated=False),
      ),
    ),
    retrieval=_sample_retrieval(
      goal=None, stage=None, task=None, task_log=None
    ),
  )
  exact_handoff_json = render.build_handoff_json(
    exact_limit_view, _command_for_path
  )

  handoff_json = render.build_handoff_json(view, _command_for_path)
  expected_text = (
    'Project: sample\n'
    'Status: active\n'
    f'Objective: {"a" * 999}…\n'
    'Charter context: legacy incomplete\n'
    'Project database: .tmp/sample.sqlite3\n'
    'Active goal: 7 (active)\n'
    'Goal text: Goal text\n'
    'Active stage: Stage\\u2028One\n'
    'Active task: 12 [legacy blank title] -\n'
    f'Summary: {"\\n" * 499}…\n'
    'Next action: "-"\n'
    'Open blockers (1 of 2; more: list-blockers):\n'
    '- 2 [task 12]: Wait; required: Sign-off\n'
    'Blocked tasks (1 of 1):\n'
    '- 15 [legacy blank title] - (stage: Build; goal: 7)\n'
    'Blocked goals (1 of 1):\n'
    '- 8: Blocked goal; reason: Need review\n'
    'Relevant task decisions (1 of 1):\n'
    '- 5 [legacy unresolved context]: Keep pure\n'
    'Relevant task evidence (1 of 1):\n'
    '- 6 [legacy unresolved context] [legacy blank claim]: -\n'
    'Recent task log (2 of 5; more: list-logs 12):\n'
    '- note: new\n'
    '- note: old\n'
    'Text projection: 2 fields truncated at 1000 rendered characters.\n'
    '- Full values: retrieve:project.objective\n'
    '- Full values: retrieve:state.summary'
  )
  expected_projection = render.HandoffProjection(
    character_limit=1000,
    truncated_fields=(
      render.TruncatedField(
        path='project.objective',
        characters=1200,
        retrieval='retrieve:project.objective',
      ),
      render.TruncatedField(
        path='state.summary',
        characters=600,
        retrieval='retrieve:state.summary',
      ),
    ),
    full_value_commands=(
      'retrieve:project.objective',
      'retrieve:state.summary',
    ),
  )

  assert (
    render.format_handoff(exact_limit_view, _command_for_path),
    exact_handoff_json.text_projection,
    render.format_handoff(view, _command_for_path),
    handoff_json,
  ) == (
    'Project: sample\n'
    'Status: active\n'
    f'Objective: {"x" * core.HANDOFF_TEXT_LIMIT}\n'
    'Project database: .tmp/exact.sqlite3\n'
    'Active goal: -\n'
    'Goal text: -\n'
    'Active stage: -\n'
    'Active task: -\n'
    'Summary: "-"\n'
    'Next action: -',
    render.HandoffProjection(
      character_limit=1000,
      truncated_fields=(),
      full_value_commands=(),
    ),
    expected_text,
    render.HandoffJson(view=view, text_projection=expected_projection),
  )

  decoded = json.loads(json.dumps(handoff_json.to_dict()))
  assert decoded == {
    'path': '.tmp/sample.sqlite3',
    'project': {
      'id': 1,
      'name': 'sample',
      'objective': long_objective,
      'scope': 'Render layer',
      'non_goals': 'Storage IO',
      'constraints_text': 'Pure formatting',
      'acceptance': 'Suite passes',
      'created_at': _TIME,
      'updated_at': _TIME,
      'charter_context_status': 'legacy-incomplete',
      'status': 'active',
      'completed_at': None,
    },
    'state': {
      'id': 1,
      'summary': long_summary,
      'next_action': '-',
      'updated_at': _TIME,
      'revision': 3,
    },
    'goal': {
      'goal': {
        'id': 7,
        'text': 'Goal text',
        'status': 'active',
        'status_reason': '',
        'ever_activated': 1,
        'created_at': _TIME,
        'started_at': _TIME,
        'achieved_at': None,
        'updated_at': _TIME,
      }
    },
    'stage': {
      'id': 3,
      'name': 'Stage\u2028One',
      'outcome': 'Done',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': '',
      'position': 0,
      'achievement_generation': 0,
      'achievement_generation_started_at': _TIME,
      'created_at': _TIME,
      'updated_at': _TIME,
      'status': 'active',
      'started_at': _TIME,
      'achieved_at': None,
      'achievement_evidence_id': None,
    },
    'task': {
      'id': 12,
      'goal_id': 7,
      'stage_id': 3,
      'title': '',
      'purpose': '',
      'scope': '',
      'exclusions': '',
      'result': '',
      'completion_evidence': '',
      'status': 'active',
      'priority': 0,
      'created_at': _TIME,
      'started_at': _TIME,
      'completed_at': None,
      'updated_at': _TIME,
      'title_status': 'legacy-blank',
    },
    'blocked_tasks': [
      {
        'id': 15,
        'title': '',
        'status': 'blocked',
        'goal_id': 7,
        'stage_id': 3,
        'stage_name': 'Build',
        'updated_at': _TIME,
        'title_status': 'legacy-blank',
      }
    ],
    'blocked_goals': [
      {
        'id': 8,
        'text': 'Blocked goal',
        'status': 'blocked',
        'status_reason': 'Need review',
        'updated_at': _TIME,
      }
    ],
    'blockers': [
      {
        'id': 2,
        'goal_id': 7,
        'stage_id': 3,
        'task_id': 12,
        'description': 'Wait',
        'required': 'Sign-off',
        'opened_at': _TIME,
        'target_kind': 'task',
        'target_id': 12,
      }
    ],
    'decisions': [
      {
        'id': 5,
        'goal_id': None,
        'stage_id': None,
        'task_id': 12,
        'summary': 'Keep pure',
        'decided_at': _TIME,
        'context_status': 'legacy-unresolved',
      }
    ],
    'evidence': [
      {
        'id': 6,
        'goal_id': None,
        'stage_id': None,
        'task_id': 12,
        'claim': '',
        'source': '',
        'result': '',
        'captured_at': _TIME,
        'context_status': 'legacy-unresolved',
        'claim_status': 'legacy-blank',
        'stage_generation': None,
      }
    ],
    'logs': [
      {'occurred_at': _TIME, 'kind': 'note', 'message': 'old'},
      {'occurred_at': _TIME + 1, 'kind': 'note', 'message': 'new'},
    ],
    'focus': {'kind': 'task', 'id': 12},
    'pages': {
      'blocked_tasks': {'shown': 1, 'total': 1, 'truncated': False},
      'blocked_goals': {'shown': 1, 'total': 1, 'truncated': False},
      'blockers': {'shown': 1, 'total': 2, 'truncated': True},
      'decisions': {'shown': 1, 'total': 1, 'truncated': False},
      'evidence': {'shown': 1, 'total': 1, 'truncated': False},
      'task_log': {'shown': 2, 'total': 5, 'truncated': True},
    },
    'retrieval': {
      'project': 'show-project',
      'goal': 'show-goal 7',
      'stage': 'list-stages',
      'task': 'show-task 12',
      'blocked_tasks': 'list-blocked-tasks',
      'blocked_goals': 'list-blocked-goals',
      'blockers': 'list-blockers',
      'ready_tasks': 'list-ready',
      'decisions': 'list-decisions',
      'evidence': 'list-evidence',
      'task_log': 'list-logs 12',
    },
    'text_projection': {
      'character_limit': 1000,
      'truncated_fields': [
        {
          'path': 'project.objective',
          'characters': 1200,
          'retrieval': 'retrieve:project.objective',
        },
        {
          'path': 'state.summary',
          'characters': 600,
          'retrieval': 'retrieve:state.summary',
        },
      ],
      'full_value_commands': [
        'retrieve:project.objective',
        'retrieve:state.summary',
      ],
    },
  }

  missing_cmd_view = render.HandoffView(
    data=view.data,
    retrieval=_sample_retrieval(task_log=None),
  )
  with pytest.raises(core.ProjectError) as missing_cmd_err:
    render.format_handoff(missing_cmd_view, _command_for_path)
  assert str(missing_cmd_err.value) == (
    'No handoff retrieval command for task_log'
  )


def test_text_handoff_view_differential_parity_and_short_prefixes() -> (
  None
):
  retrieval = _sample_retrieval()
  long_dash = '-' + ('x' * 1500)
  newline_501 = '\n' * 501
  tricky_utf8 = 'a\x1b\x9f\u2028\u2029' + ('😀' * 600)
  exact_1000 = 'k' * 1000
  over_1001 = 'm' * 1001

  full_data = service.HandoffData(
    path='memory://demo',
    project=_project_record(name='demo', objective=long_dash),
    state=service.ProjectState(
      id=1,
      summary='-',
      next_action=newline_501,
      updated_at=_TIME,
      revision=2,
    ),
    goal=service.ActiveGoalRef(
      goal=service.GoalRecord(
        id=4,
        text=tricky_utf8,
        status='active',
        status_reason='',
        ever_activated=1,
        created_at=_TIME,
        started_at=_TIME,
        achieved_at=None,
        updated_at=_TIME,
      )
    ),
    stage=service.StageRecord(
      id=7,
      name=exact_1000,
      outcome='Done',
      purpose='',
      entry_conditions='',
      exit_evidence='',
      position=0,
      achievement_generation=0,
      achievement_generation_started_at=_TIME,
      created_at=_TIME,
      updated_at=_TIME,
      status='active',
      started_at=_TIME,
      achieved_at=None,
      achievement_evidence_id=None,
    ),
    task=service.HandoffTaskRecord(
      id=12,
      goal_id=4,
      stage_id=7,
      title=over_1001,
      purpose='P',
      scope='S',
      exclusions='E',
      result='R',
      completion_evidence='C',
      status='active',
      priority=0,
      created_at=_TIME,
      started_at=_TIME,
      completed_at=None,
      updated_at=_TIME,
      title_status='legacy-blank',
    ),
    blocked_tasks=(
      service.BlockedTaskSummary(
        id=20,
        title='-',
        status='blocked',
        goal_id=4,
        stage_id=7,
        stage_name=None,
        updated_at=_TIME,
        title_status='substantive',
      ),
      service.BlockedTaskSummary(
        id=21,
        title=long_dash,
        status='blocked',
        goal_id=None,
        stage_id=8,
        stage_name=tricky_utf8,
        updated_at=_TIME,
        title_status='substantive',
      ),
    ),
    blocked_goals=(
      service.BlockedGoalSummary(
        id=9,
        text=exact_1000,
        status='blocked',
        status_reason=over_1001,
        updated_at=_TIME,
      ),
    ),
    blockers=(
      service.HandoffBlockerSummary(
        id=3,
        goal_id=4,
        stage_id=7,
        task_id=12,
        description=long_dash,
        required='-',
        opened_at=_TIME,
        target_kind='task',
        target_id=12,
      ),
    ),
    decisions=(
      service.HandoffDecisionSummary(
        id=5,
        goal_id=4,
        stage_id=7,
        task_id=12,
        summary=newline_501,
        decided_at=_TIME,
        context_status='legacy-unresolved',
      ),
    ),
    evidence=(
      service.EvidenceRecord(
        id=6,
        goal_id=4,
        stage_id=7,
        task_id=12,
        claim=tricky_utf8,
        source='S',
        result='R',
        captured_at=_TIME,
        context_status='complete',
        claim_status='legacy-blank',
        stage_generation=0,
      ),
    ),
    logs=(
      service.HandoffLogEntry(
        occurred_at=_TIME,
        kind='-',
        message=over_1001,
      ),
    ),
    focus=service.HandoffFocus(kind='task', id=12),
    pages=service.HandoffPages(
      blocked_tasks=service.HandoffPage(shown=2, total=2, truncated=False),
      blocked_goals=service.HandoffPage(shown=1, total=1, truncated=False),
      blockers=service.HandoffPage(shown=1, total=1, truncated=False),
      decisions=service.HandoffPage(shown=1, total=1, truncated=False),
      evidence=service.HandoffPage(shown=1, total=1, truncated=False),
      task_log=service.HandoffPage(shown=1, total=1, truncated=False),
    ),
  )

  def _bounded(value: str) -> service.BoundedText:
    return service.BoundedText(
      value[: core.HANDOFF_TEXT_LIMIT + 1], len(value)
    )

  text_data = service.TextHandoffData(
    path='memory://demo',
    project=service.TextHandoffProject(
      name=_bounded('demo'),
      status='active',
      objective=_bounded(long_dash),
      charter_context_status='current',
    ),
    state=service.TextHandoffState(
      summary=_bounded('-'),
      next_action=_bounded(newline_501),
    ),
    goal=service.TextHandoffGoal(
      id=4,
      status='active',
      text=_bounded(tricky_utf8),
    ),
    stage=service.TextHandoffStage(id=7, name=_bounded(exact_1000)),
    task=service.TextHandoffTask(
      id=12,
      goal_id=4,
      stage_id=7,
      title=_bounded(over_1001),
      title_status='legacy-blank',
    ),
    blocked_tasks=(
      service.TextBlockedTaskSummary(
        id=20,
        title=_bounded('-'),
        goal_id=4,
        stage_id=7,
        stage_name=None,
        title_status='substantive',
      ),
      service.TextBlockedTaskSummary(
        id=21,
        title=_bounded(long_dash),
        goal_id=None,
        stage_id=8,
        stage_name=_bounded(tricky_utf8),
        title_status='substantive',
      ),
    ),
    blocked_goals=(
      service.TextBlockedGoalSummary(
        id=9,
        text=_bounded(exact_1000),
        status_reason=_bounded(over_1001),
      ),
    ),
    blockers=(
      service.TextHandoffBlockerSummary(
        id=3,
        description=_bounded(long_dash),
        required=_bounded('-'),
        target_kind='task',
        target_id=12,
      ),
    ),
    decisions=(
      service.TextHandoffDecisionSummary(
        id=5,
        summary=_bounded(newline_501),
        context_status='legacy-unresolved',
      ),
    ),
    evidence=(
      service.TextHandoffEvidenceSummary(
        id=6,
        claim=_bounded(tricky_utf8),
        context_status='complete',
        claim_status='legacy-blank',
      ),
    ),
    logs=(
      service.TextHandoffLogEntry(
        kind=_bounded('-'),
        message=_bounded(over_1001),
      ),
    ),
    focus=full_data.focus,
    pages=full_data.pages,
  )
  full_rendered = render._render_handoff(
    render.HandoffView(data=full_data, retrieval=retrieval),
    _command_for_path,
  )
  text_rendered = render._render_handoff(
    render.TextHandoffView(data=text_data, retrieval=retrieval),
    _command_for_path,
  )

  assert (
    text_rendered,
    render.format_handoff(
      render.TextHandoffView(data=text_data, retrieval=retrieval),
      _command_for_path,
    ),
  ) == (full_rendered, full_rendered[0])
