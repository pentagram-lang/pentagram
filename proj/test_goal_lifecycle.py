import sqlite3
from pathlib import Path
from typing import Literal, Never, TypedDict

import pytest

from proj import project, storage
from proj.errors import ProjectError
from proj.test_support import ProjectWorld, rewrite_project_database

type GoalStatus = Literal[
  'active', 'pending', 'blocked', 'achieved', 'cancelled'
]


class GoalRecord(TypedDict):
  id: int
  text: str
  status: GoalStatus
  status_reason: str
  ever_activated: int
  created_at: int
  started_at: int
  achieved_at: int | None
  updated_at: int
  stage_names: str
  is_active: bool


def _goal_record(
  goal_id: int,
  text: str,
  stage_names: str,
  status: GoalStatus = 'active',
  status_reason: str = '',
  achieved_at: int | None = None,
) -> GoalRecord:
  return {
    'id': goal_id,
    'text': text,
    'status': status,
    'status_reason': status_reason,
    'ever_activated': 1,
    'created_at': 1_700_000_000,
    'started_at': 1_700_000_000,
    'achieved_at': achieved_at,
    'updated_at': 1_700_000_000,
    'stage_names': stage_names,
    'is_active': status == 'active',
  }


@pytest.mark.parametrize(
  ('text', 'message'),
  [
    ('', 'Goal text must contain at least one non-whitespace character'),
    (
      '  \t  ',
      'Goal text must contain at least one non-whitespace character',
    ),
    (
      'x' * 4001,
      'Goal text is limited to 4,000 characters; received 4,001.',
    ),
  ],
  ids=('empty', 'whitespace', 'too-long'),
)
def test_goal_text_rejects_empty_and_oversized_values(
  project_world: ProjectWorld, text: str, message: str
) -> None:
  with pytest.raises(ProjectError) as error:
    project.create_goal(
      project_world.root,
      project_world.name,
      text,
      [project_world.stage_id],
    )

  assert str(error.value) == message
  assert project.read_goals(project_world.root, project_world.name) == []


def test_goal_scope_is_fixed_and_goal_linked_tasks_need_active_goal(
  chartered_project: str, project_root: Path
) -> None:
  name = chartered_project
  stage_id = project.add_stage(
    project_root,
    name,
    'Build',
    'Deliver a verified result',
    exit_evidence='A verified result',
  )
  goal_id = project.create_goal(
    project_root, name, 'Deliver the agreed result exactly', [stage_id]
  )
  task_id = project.add_task(
    project_root,
    name,
    'Complete the goal',
    purpose='Fulfil the active goal',
    stage=stage_id,
    goal=goal_id,
    scope='The goal result',
    exclusions='Unrelated changes',
    result='The agreed result is delivered',
    completion_evidence='Validation record',
  )

  assert project.goal_text(project_root, name, goal_id) == (
    'Deliver the agreed result exactly'
  )
  assert project.read_goals(project_root, name) == [
    {
      'id': goal_id,
      'text': 'Deliver the agreed result exactly',
      'status': 'active',
      'status_reason': '',
      'ever_activated': 1,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'updated_at': 1_700_000_000,
      'stage_names': 'Build',
      'is_active': True,
    }
  ]
  project.start_task(project_root, name, task_id)
  project.complete_task(project_root, name, task_id)
  evidence_id = project.add_evidence(
    project_root,
    name,
    'Goal result is verified',
    result='Validation passed',
    goal=goal_id,
  )
  project.achieve_goal(project_root, name, goal_id)

  assert project.read_goals(project_root, name) == [
    _goal_record(
      goal_id,
      'Deliver the agreed result exactly',
      'Build',
      status='achieved',
      achieved_at=1_700_000_000,
    )
  ]
  assert project.read_evidence(project_root, name, goal=goal_id) == [
    {
      'id': evidence_id,
      'goal_id': goal_id,
      'stage_id': None,
      'task_id': None,
      'claim': 'Goal result is verified',
      'source': '',
      'result': 'Validation passed',
      'captured_at': 1_700_000_000,
      'context_status': 'complete',
      'claim_status': 'substantive',
      'stage_generation': None,
    }
  ]
  with pytest.raises(ProjectError) as error:
    project.reopen_goal(project_root, name, goal_id)
  assert str(error.value) == (
    f'Only blocked goals can be reopened; goal {goal_id} is achieved'
  )


def test_activated_goal_stage_scope_is_immutable(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  goal_id = project.create_goal(
    root, name, 'Keep the activated goal scope fixed', [stage_id]
  )
  other_stage = project.add_stage(
    root,
    name,
    'Additional stage',
    'Keep the original goal relationship unchanged',
    exit_evidence='The activated goal scope stays fixed',
  )
  connection = storage.connect(storage.database_path(root, name))
  try:
    with pytest.raises(sqlite3.IntegrityError) as insert_error:
      connection.execute(
        'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
        (goal_id, other_stage),
      )
    assert str(insert_error.value) == 'goal-stage scope is already fixed'
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError) as update_error:
      connection.execute(
        'UPDATE goal_stage SET stage_id = ? WHERE goal_id = ?',
        (other_stage, goal_id),
      )
    assert str(update_error.value) == (
      'goal-stage relationships cannot be updated'
    )
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError) as delete_error:
      connection.execute(
        'DELETE FROM goal_stage WHERE goal_id = ?', (goal_id,)
      )
    assert str(delete_error.value) == 'goal-stage scope is already fixed'
    connection.rollback()
  finally:
    connection.close()

  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Keep the activated goal scope fixed',
      'Workflow',
    )
  ]


def test_goal_activation_hands_off_previous_goal_and_keeps_goal_less_task(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  project.start_task(root, name, project_world.task_id)

  goal_id = project.create_goal(
    root,
    name,
    'A concurrent goal-less task remains valid',
    [project_world.stage_id],
  )

  replacement = project.create_goal(
    root,
    name,
    'Replace the active goal without ending goal-less work',
    [project_world.stage_id],
  )

  assert project.read_goals(root, name) == [
    _goal_record(
      replacement,
      'Replace the active goal without ending goal-less work',
      'Workflow',
    ),
    _goal_record(
      goal_id,
      'A concurrent goal-less task remains valid',
      'Workflow',
      status='pending',
      status_reason=f'Deferred while activating goal {replacement}',
    ),
  ]
  assert project.read_tasks(root, name, status='active') == [
    {
      'id': project_world.task_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'title': 'Exercise the lifecycle',
      'purpose': 'Guard state transitions',
      'scope': 'Task and stage status',
      'exclusions': 'CLI presentation',
      'result': 'Transitions produce the documented state',
      'completion_evidence': 'Exact returned lifecycle records',
      'status': 'active',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    }
  ]


def test_goal_activation_returns_goal_linked_task_to_pending(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  first_goal = project.create_goal(
    root,
    name,
    'Defer the current goal and its task',
    [project_world.stage_id],
  )
  task_id = project.add_task(
    root,
    name,
    'Work for the current goal',
    purpose='Verify goal activation handoff',
    stage=project_world.stage_id,
    goal=first_goal,
    scope='Task and goal activation',
    exclusions='Goal-less tasks',
    result='The task remains resumable',
    completion_evidence='Task status and log history',
  )
  project.start_task(root, name, task_id)
  second_goal = project.create_goal(
    root, name, 'Activate the replacement goal', [project_world.stage_id]
  )

  assert project.read_goals(root, name) == [
    _goal_record(
      second_goal,
      'Activate the replacement goal',
      'Workflow',
    ),
    _goal_record(
      first_goal,
      'Defer the current goal and its task',
      'Workflow',
      status='pending',
      status_reason=f'Deferred while activating goal {second_goal}',
    ),
  ]
  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': first_goal,
      'stage_id': project_world.stage_id,
      'title': 'Work for the current goal',
      'purpose': 'Verify goal activation handoff',
      'scope': 'Task and goal activation',
      'exclusions': 'Goal-less tasks',
      'result': 'The task remains resumable',
      'completion_evidence': 'Task status and log history',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [
      {
        'id': 1,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'started',
        'message': 'Task started',
      },
      {
        'id': 2,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'handoff',
        'message': (
          f'Task returned to pending while activating goal {second_goal}'
        ),
      },
    ],
  }


def test_activating_a_pending_goal_hands_off_active_goal_work(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  first_goal = project.create_goal(
    root, name, 'Resume the pending goal', [project_world.stage_id]
  )
  second_goal = project.create_goal(
    root,
    name,
    'Defer the currently active goal',
    [project_world.stage_id],
  )
  task_id = project.add_task(
    root,
    name,
    'Work for the active goal',
    purpose='Verify explicit goal activation',
    stage=project_world.stage_id,
    goal=second_goal,
    scope='Goal handoff',
    exclusions='Task goal reassignment',
    result='The active goal work is resumable',
    completion_evidence='The handoff records',
  )
  project.start_task(root, name, task_id)

  project.activate_goal(root, name, first_goal)

  assert project.read_goals(root, name) == [
    _goal_record(
      second_goal,
      'Defer the currently active goal',
      'Workflow',
      status='pending',
      status_reason=f'Deferred while activating goal {first_goal}',
    ),
    _goal_record(
      first_goal,
      'Resume the pending goal',
      'Workflow',
    ),
  ]
  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': second_goal,
      'stage_id': project_world.stage_id,
      'title': 'Work for the active goal',
      'purpose': 'Verify explicit goal activation',
      'scope': 'Goal handoff',
      'exclusions': 'Task goal reassignment',
      'result': 'The active goal work is resumable',
      'completion_evidence': 'The handoff records',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [
      {
        'id': 1,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'started',
        'message': 'Task started',
      },
      {
        'id': 2,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'handoff',
        'message': (
          f'Task returned to pending while activating goal {first_goal}'
        ),
      },
    ],
  }


def test_failed_goal_handoff_rolls_back_both_activations(
  project_world: ProjectWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
  root = project_world.root
  name = project_world.name
  pending_goal = project.create_goal(
    root,
    name,
    'Keep the pending goal unchanged',
    [project_world.stage_id],
  )
  active_goal = project.create_goal(
    root,
    name,
    'Keep the active goal unchanged',
    [project_world.stage_id],
  )
  task_id = project.add_task(
    root,
    name,
    'Keep the active task unchanged',
    purpose='Exercise goal transaction rollback',
    stage=project_world.stage_id,
    goal=active_goal,
    scope='Atomic goal handoff',
    exclusions='Task activation',
    result='A failed transaction preserves active work',
    completion_evidence='The exact pre-transition records',
  )
  project.start_task(root, name, task_id)
  goals_before = project.read_goals(root, name)
  task_before = project.read_task(root, name, task_id)

  def fail_revision_update(_connection: sqlite3.Connection) -> Never:
    raise ProjectError('Injected revision failure')

  monkeypatch.setattr(project, '_touch', fail_revision_update)
  with pytest.raises(ProjectError) as error:
    project.activate_goal(root, name, pending_goal)

  assert str(error.value) == 'Injected revision failure'
  assert project.read_goals(root, name) == goals_before
  assert project.read_task(root, name, task_id) == task_before


def test_reopening_a_repaired_goal_hands_off_current_goal_work(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  blocked_goal = project.create_goal(
    root,
    name,
    'Resume the repaired blocked goal',
    [project_world.stage_id],
  )
  blocker_id = project.block_goal(
    root,
    name,
    blocked_goal,
    'The goal needs a decision',
    required='Resolve the goal decision',
  )
  rewrite_project_database(
    storage.database_path(root, name),
    ('release_resolved_blocker',),
    "UPDATE blocker SET status = 'resolved', resolved_at = ?, "
    'resolution = ? WHERE id = ?',
    (1_700_000_000, 'Decision received', blocker_id),
  )
  active_goal = project.create_goal(
    root,
    name,
    'Defer this goal when reopening the other',
    [project_world.stage_id],
  )
  task_id = project.add_task(
    root,
    name,
    'Work for the active goal',
    purpose='Verify blocked-goal reopening',
    stage=project_world.stage_id,
    goal=active_goal,
    scope='Goal reopening and handoff',
    exclusions='Blocker resolution',
    result='The current goal work remains resumable',
    completion_evidence='The resulting lifecycle records',
  )
  project.start_task(root, name, task_id)

  project.reopen_goal(root, name, blocked_goal)

  assert project.read_goals(root, name) == [
    _goal_record(
      active_goal,
      'Defer this goal when reopening the other',
      'Workflow',
      status='pending',
      status_reason=f'Deferred while activating goal {blocked_goal}',
    ),
    _goal_record(
      blocked_goal,
      'Resume the repaired blocked goal',
      'Workflow',
    ),
  ]
  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': active_goal,
      'stage_id': project_world.stage_id,
      'title': 'Work for the active goal',
      'purpose': 'Verify blocked-goal reopening',
      'scope': 'Goal reopening and handoff',
      'exclusions': 'Blocker resolution',
      'result': 'The current goal work remains resumable',
      'completion_evidence': 'The resulting lifecycle records',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [
      {
        'id': 1,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'started',
        'message': 'Task started',
      },
      {
        'id': 2,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'handoff',
        'message': (
          f'Task returned to pending while activating goal {blocked_goal}'
        ),
      },
    ],
  }


def test_goal_achievement_requires_evidence_and_no_active_task(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  goal_id = project.create_goal(
    root, name, 'Establish the verified outcome', [project_world.stage_id]
  )

  with pytest.raises(ProjectError) as missing_evidence:
    project.achieve_goal(root, name, goal_id)
  assert str(missing_evidence.value) == (
    'Achieving a goal requires at least one goal-linked evidence entry'
  )

  project.start_task(root, name, project_world.task_id)
  project.add_evidence(
    root,
    name,
    'The goal has supporting evidence',
    goal=goal_id,
  )
  with pytest.raises(ProjectError) as active_task:
    project.achieve_goal(root, name, goal_id)
  assert str(active_task.value) == (
    f'Achieving a goal requires active task {project_world.task_id} '
    'to end first'
  )
  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Establish the verified outcome',
      'Workflow',
    )
  ]
  assert project.read_tasks(root, name, status='active') == [
    {
      'id': project_world.task_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'title': 'Exercise the lifecycle',
      'purpose': 'Guard state transitions',
      'scope': 'Task and stage status',
      'exclusions': 'CLI presentation',
      'result': 'Transitions produce the documented state',
      'completion_evidence': 'Exact returned lifecycle records',
      'status': 'active',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    }
  ]


def test_goal_achievement_freezes_evidence_and_lifecycle_timing(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  goal_id = project.create_goal(
    root,
    name,
    'Freeze the achieved evidence set',
    [project_world.stage_id],
  )
  evidence_id = project.add_evidence(
    root,
    name,
    'The goal outcome is established',
    source='acceptance run',
    result='All required behaviour passed',
    goal=goal_id,
  )
  project.achieve_goal(root, name, goal_id)

  with pytest.raises(ProjectError) as add_error:
    project.add_evidence(
      root, name, 'A later goal observation', goal=goal_id
    )
  assert str(add_error.value) == 'Achieved goal evidence is fixed'

  connection = storage.connect(storage.database_path(root, name))
  try:
    with pytest.raises(sqlite3.IntegrityError) as update_error:
      connection.execute(
        'UPDATE evidence SET claim = ? WHERE id = ?',
        ('Replace the accepted claim', evidence_id),
      )
    assert str(update_error.value) == 'achievement evidence is immutable'
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError) as delete_error:
      connection.execute(
        'DELETE FROM evidence WHERE id = ?', (evidence_id,)
      )
    assert (
      str(delete_error.value) == 'achievement evidence cannot be deleted'
    )
    connection.rollback()

    with pytest.raises(sqlite3.IntegrityError) as timing_error:
      connection.execute(
        'UPDATE goal SET achieved_at = ? WHERE id = ?',
        (1_700_000_001, goal_id),
      )
    assert (
      str(timing_error.value) == 'achieved goal lifecycle is immutable'
    )
    connection.rollback()
  finally:
    connection.close()

  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Freeze the achieved evidence set',
      'Workflow',
      status='achieved',
      achieved_at=1_700_000_000,
    )
  ]
  assert project.read_evidence(root, name, goal=goal_id) == [
    {
      'id': evidence_id,
      'goal_id': goal_id,
      'stage_id': None,
      'task_id': None,
      'claim': 'The goal outcome is established',
      'source': 'acceptance run',
      'result': 'All required behaviour passed',
      'captured_at': 1_700_000_000,
      'context_status': 'complete',
      'claim_status': 'substantive',
      'stage_generation': None,
    }
  ]


def test_task_blocker_does_not_block_its_contextual_goal(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  goal_id = project.create_goal(
    root, name, 'Keep task and goal blockers distinct', [stage_id]
  )
  task_id = project.add_task(
    root,
    name,
    'Work under the goal',
    purpose='Exercise task blocker context',
    stage=stage_id,
    goal=goal_id,
    scope='Goal-linked task work',
    exclusions='Goal lifecycle changes',
    result='Only the task becomes blocked',
    completion_evidence='Task blocker record',
  )
  blocker_id = project.block_task(
    root,
    name,
    task_id,
    'The task input is unavailable',
    required='Provide the task input',
  )

  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Keep task and goal blockers distinct',
      'Workflow',
    )
  ]
  assert project.read_blockers(root, name) == [
    {
      'id': blocker_id,
      'goal_id': goal_id,
      'stage_id': stage_id,
      'task_id': task_id,
      'description': 'The task input is unavailable',
      'impact': '',
      'attempts': '',
      'required': 'Provide the task input',
      'opened_at': 1_700_000_000,
      'status': 'open',
      'resolved_at': None,
      'resolution': '',
      'target_kind': 'task',
      'target_id': task_id,
    }
  ]


def test_goal_blockers_track_latest_reason_and_reactivate_after_resolution(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  goal_id = project.create_goal(
    root, name, 'Resolve external dependencies', [project_world.stage_id]
  )
  first = project.block_goal(
    root,
    name,
    goal_id,
    'Credentials are missing',
    required='Obtain the correct credentials',
  )
  second = project.add_blocker(
    root,
    name,
    'Access approval is pending',
    required='Receive approval',
    stage=project_world.stage_id,
    goal=goal_id,
  )

  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Resolve external dependencies',
      'Workflow',
      status='blocked',
      status_reason='Access approval is pending',
    )
  ]
  project.resolve_blocker(root, name, second, 'Approval received')
  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Resolve external dependencies',
      'Workflow',
      status='blocked',
      status_reason='Credentials are missing',
    )
  ]
  project.resolve_blocker(root, name, first, 'Credentials received')

  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Resolve external dependencies',
      'Workflow',
    )
  ]
  assert project.read_blockers(root, name, status='all') == [
    {
      'id': second,
      'goal_id': goal_id,
      'stage_id': project_world.stage_id,
      'task_id': None,
      'description': 'Access approval is pending',
      'impact': '',
      'attempts': '',
      'required': 'Receive approval',
      'status': 'resolved',
      'opened_at': 1_700_000_000,
      'resolved_at': 1_700_000_000,
      'resolution': 'Approval received',
      'target_kind': 'goal',
      'target_id': goal_id,
    },
    {
      'id': first,
      'goal_id': goal_id,
      'stage_id': None,
      'task_id': None,
      'description': 'Credentials are missing',
      'impact': '',
      'attempts': '',
      'required': 'Obtain the correct credentials',
      'status': 'resolved',
      'opened_at': 1_700_000_000,
      'resolved_at': 1_700_000_000,
      'resolution': 'Credentials received',
      'target_kind': 'goal',
      'target_id': goal_id,
    },
  ]


def test_goal_blocker_resolution_hands_off_the_other_active_goal(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  blocked_goal = project.create_goal(
    root, name, 'Restore the first goal', [stage_id]
  )
  blocker_id = project.block_goal(
    root,
    name,
    blocked_goal,
    'The first goal needs a decision',
    required='Make the first goal decision',
  )
  active_goal = project.create_goal(
    root, name, 'Continue the second goal', [stage_id]
  )
  task_id = project.add_task(
    root,
    name,
    'Work for the second goal',
    purpose='Verify blocker recovery handoff',
    stage=stage_id,
    goal=active_goal,
    scope='Goal blocker recovery',
    exclusions='Goal cancellation',
    result='The interrupted goal work is resumable',
    completion_evidence='The status and log records',
  )
  project.start_task(root, name, task_id)

  project.resolve_blocker(root, name, blocker_id, 'Decision received')

  assert project.read_goals(root, name) == [
    _goal_record(
      active_goal,
      'Continue the second goal',
      'Workflow',
      status='pending',
      status_reason=f'Deferred while activating goal {blocked_goal}',
    ),
    _goal_record(
      blocked_goal,
      'Restore the first goal',
      'Workflow',
    ),
  ]
  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': active_goal,
      'stage_id': stage_id,
      'title': 'Work for the second goal',
      'purpose': 'Verify blocker recovery handoff',
      'scope': 'Goal blocker recovery',
      'exclusions': 'Goal cancellation',
      'result': 'The interrupted goal work is resumable',
      'completion_evidence': 'The status and log records',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [
      {
        'id': 1,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'started',
        'message': 'Task started',
      },
      {
        'id': 2,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'handoff',
        'message': (
          f'Task returned to pending while activating goal {blocked_goal}'
        ),
      },
    ],
  }
  assert project.read_blockers(root, name, status='all') == [
    {
      'id': blocker_id,
      'goal_id': blocked_goal,
      'stage_id': None,
      'task_id': None,
      'description': 'The first goal needs a decision',
      'impact': '',
      'attempts': '',
      'required': 'Make the first goal decision',
      'status': 'resolved',
      'opened_at': 1_700_000_000,
      'resolved_at': 1_700_000_000,
      'resolution': 'Decision received',
      'target_kind': 'goal',
      'target_id': blocked_goal,
    }
  ]


def test_cancelling_a_blocked_goal_withdraws_blockers_and_is_terminal(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  goal_id = project.create_goal(
    root, name, 'A goal can be cancelled without achievement', [stage_id]
  )
  blocker_id = project.block_goal(
    root,
    name,
    goal_id,
    'The required decision is unavailable',
    required='Obtain the decision',
  )

  project.cancel_goal(
    root, name, goal_id, 'The goal is no longer required'
  )

  assert project.read_goals(root, name) == [
    {
      'id': goal_id,
      'text': 'A goal can be cancelled without achievement',
      'status': 'cancelled',
      'status_reason': 'The goal is no longer required',
      'ever_activated': 1,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'updated_at': 1_700_000_000,
      'stage_names': 'Workflow',
      'is_active': False,
    }
  ]
  assert project.read_blockers(root, name, status='all') == [
    {
      'id': blocker_id,
      'goal_id': goal_id,
      'stage_id': None,
      'task_id': None,
      'description': 'The required decision is unavailable',
      'impact': '',
      'attempts': '',
      'required': 'Obtain the decision',
      'opened_at': 1_700_000_000,
      'status': 'withdrawn',
      'resolved_at': 1_700_000_000,
      'resolution': 'The goal is no longer required',
      'target_kind': 'goal',
      'target_id': goal_id,
    }
  ]
  with pytest.raises(ProjectError) as error:
    project.reopen_goal(root, name, goal_id)
  assert str(error.value) == (
    f'Only blocked goals can be reopened; goal {goal_id} is cancelled'
  )


def test_blocked_goal_can_be_cancelled_while_another_goal_is_active(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  blocked_goal = project.create_goal(
    root, name, 'Cancel the blocked delegation', [stage_id]
  )
  blocker_id = project.block_goal(
    root,
    name,
    blocked_goal,
    'The blocked delegation is no longer useful',
    required='Decide whether to continue the delegation',
  )
  active_goal = project.create_goal(
    root, name, 'Continue the current delegation', [stage_id]
  )

  project.cancel_goal(
    root, name, blocked_goal, 'The blocked delegation is superseded'
  )

  assert project.read_goals(root, name) == [
    _goal_record(
      active_goal,
      'Continue the current delegation',
      'Workflow',
    ),
    _goal_record(
      blocked_goal,
      'Cancel the blocked delegation',
      'Workflow',
      status='cancelled',
      status_reason='The blocked delegation is superseded',
    ),
  ]
  assert project.read_blockers(root, name, status='all') == [
    {
      'id': blocker_id,
      'goal_id': blocked_goal,
      'stage_id': None,
      'task_id': None,
      'description': 'The blocked delegation is no longer useful',
      'impact': '',
      'attempts': '',
      'required': 'Decide whether to continue the delegation',
      'status': 'withdrawn',
      'opened_at': 1_700_000_000,
      'resolved_at': 1_700_000_000,
      'resolution': 'The blocked delegation is superseded',
      'target_kind': 'goal',
      'target_id': blocked_goal,
    }
  ]


def test_goal_cannot_be_blocked_while_its_task_is_active(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  goal_id = project.create_goal(
    root, name, 'Finish the active goal', [project_world.stage_id]
  )
  task_id = project.add_task(
    root,
    name,
    'Work inside the goal',
    purpose='Complete goal work',
    stage=project_world.stage_id,
    goal=goal_id,
    scope='Goal result',
    exclusions='Unrelated work',
    result='Goal result is complete',
    completion_evidence='Validation',
  )
  project.start_task(root, name, task_id)
  tasks_before = project.read_tasks(root, name)

  with pytest.raises(ProjectError) as error:
    project.block_goal(
      root,
      name,
      goal_id,
      'External decision is missing',
      required='Receive decision',
    )

  assert str(error.value) == (
    f'Blocking a goal requires active task {task_id} to end first'
  )
  assert project.read_goals(root, name) == [
    _goal_record(
      goal_id,
      'Finish the active goal',
      'Workflow',
    )
  ]
  assert project.read_tasks(root, name) == tasks_before
  assert project.read_blockers(root, name, status='all') == []
