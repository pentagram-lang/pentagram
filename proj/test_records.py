from collections.abc import Mapping, Sequence
from typing import Literal

import pytest

from proj import project
from proj.errors import ProjectError
from proj.test_support import ProjectWorld


def _expected_inactive_task_handoff(
  world: ProjectWorld,
  *,
  project_status: Literal['active', 'blocked'],
  revision: int,
  goal: Mapping[str, object] | None,
  blocked_tasks: Sequence[Mapping[str, object]],
  blocked_goals: Sequence[Mapping[str, object]],
  blockers: Sequence[Mapping[str, object]],
  decisions: Sequence[Mapping[str, object]],
  evidence: Sequence[Mapping[str, object]],
  logs: Sequence[Mapping[str, object]],
  focus: Mapping[str, object],
  pages: Mapping[str, object],
) -> dict[str, object]:
  return {
    'path': f'.tmp/{world.name}.sqlite3',
    'project': {
      'id': 1,
      'name': world.name,
      'objective': 'Deliver a reliable project workflow',
      'scope': 'Project state and commands',
      'non_goals': 'Language runtime behaviour',
      'constraints_text': 'Preserve append-only history',
      'acceptance': 'Lifecycle tests and review',
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'charter_context_status': 'current',
      'status': project_status,
      'completed_at': None,
    },
    'state': {
      'id': 1,
      'summary': '',
      'next_action': '',
      'updated_at': 1_700_000_000,
      'revision': revision,
    },
    'goal': goal,
    'stage': None,
    'task': None,
    'blocked_tasks': blocked_tasks,
    'blocked_goals': blocked_goals,
    'blockers': blockers,
    'decisions': decisions,
    'evidence': evidence,
    'logs': logs,
    'focus': focus,
    'pages': pages,
  }


def test_decision_and_evidence_capture_task_context_and_apply_filters(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  decision_id = project.add_decision(
    root,
    name,
    'Keep the storage boundary local',
    rationale='It owns SQLite state',
    alternatives='Move the connection into the CLI',
    task=task_id,
  )
  evidence_id = project.add_evidence(
    root,
    name,
    'The task fixture opens through the project API',
    source='pytest',
    result='The expected record was returned',
    task=task_id,
  )

  decisions = project.read_decisions(root, name, task=task_id)
  evidence = project.read_evidence(root, name, task=task_id)
  assert decisions == [
    {
      'id': decision_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'summary': 'Keep the storage boundary local',
      'rationale': 'It owns SQLite state',
      'alternatives': 'Move the connection into the CLI',
      'consequences': '',
      'decided_at': 1_700_000_000,
      'context_status': 'complete',
    }
  ]
  assert evidence == [
    {
      'id': evidence_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'claim': 'The task fixture opens through the project API',
      'source': 'pytest',
      'result': 'The expected record was returned',
      'captured_at': 1_700_000_000,
      'context_status': 'complete',
      'claim_status': 'substantive',
      'stage_generation': 0,
    }
  ]
  assert project.read_decisions(root, name, no_task=True) == []
  assert project.read_evidence(root, name, no_task=True) == []
  with pytest.raises(ProjectError) as decision_error:
    project.read_decisions(root, name, task=task_id, no_task=True)
  with pytest.raises(ProjectError) as evidence_error:
    project.read_evidence(root, name, task=task_id, no_task=True)
  assert str(decision_error.value) == (
    'Decision task and no-task filters conflict'
  )
  assert str(evidence_error.value) == (
    'Evidence task and no-task filters conflict'
  )


def test_task_record_context_is_preserved_after_task_reassignment(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  first_stage_id = project_world.stage_id
  second_stage_id = project.add_stage(
    root,
    name,
    'Follow-up',
    'Complete follow-up work',
    exit_evidence='A follow-up validation result',
  )
  decision_id = project.add_decision(
    root, name, 'Record the original context', task=task_id
  )
  evidence_id = project.add_evidence(
    root, name, 'Record the original evidence context', task=task_id
  )

  project.update_task(root, name, task_id, stage_id=second_stage_id)

  decision = project.read_decisions(root, name)[0]
  evidence = project.read_evidence(root, name)[0]
  assert decision == {
    'id': decision_id,
    'goal_id': None,
    'stage_id': first_stage_id,
    'task_id': task_id,
    'summary': 'Record the original context',
    'rationale': '',
    'alternatives': '',
    'consequences': '',
    'decided_at': 1_700_000_000,
    'context_status': 'complete',
  }
  assert evidence == {
    'id': evidence_id,
    'goal_id': None,
    'stage_id': first_stage_id,
    'task_id': task_id,
    'claim': 'Record the original evidence context',
    'source': '',
    'result': '',
    'captured_at': 1_700_000_000,
    'context_status': 'complete',
    'claim_status': 'substantive',
    'stage_generation': 0,
  }
  assert project.read_tasks(root, name) == [
    {
      'id': task_id,
      'goal_id': None,
      'stage_id': second_stage_id,
      'title': 'Exercise the lifecycle',
      'purpose': 'Guard state transitions',
      'scope': 'Task and stage status',
      'exclusions': 'CLI presentation',
      'result': 'Transitions produce the documented state',
      'completion_evidence': 'Exact returned lifecycle records',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Follow-up',
      'tags': '',
      'title_status': 'substantive',
    }
  ]


def test_task_tags_and_log_reads_use_exact_filters_and_bounds(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.add_task_tags(root, name, task_id, ('fast', 'storage', 'fast'))
  project.append_task_log(root, name, task_id, 'first note')
  project.append_task_log(root, name, task_id, 'second note')
  project.append_task_log(root, name, task_id, 'third note')
  expected_task = {
    'id': task_id,
    'goal_id': None,
    'stage_id': project_world.stage_id,
    'title': 'Exercise the lifecycle',
    'purpose': 'Guard state transitions',
    'scope': 'Task and stage status',
    'exclusions': 'CLI presentation',
    'result': 'Transitions produce the documented state',
    'completion_evidence': 'Exact returned lifecycle records',
    'status': 'pending',
    'priority': 0,
    'created_at': 1_700_000_000,
    'started_at': None,
    'completed_at': None,
    'updated_at': 1_700_000_000,
    'stage_name': 'Workflow',
    'tags': 'fast, storage',
    'title_status': 'substantive',
  }
  expected_logs = [
    {
      'id': 2,
      'task_id': task_id,
      'occurred_at': 1_700_000_000,
      'kind': 'note',
      'message': 'second note',
    },
    {
      'id': 3,
      'task_id': task_id,
      'occurred_at': 1_700_000_000,
      'kind': 'note',
      'message': 'third note',
    },
  ]

  assert project.read_tasks(root, name, tag='storage') == [expected_task]
  assert project.read_tasks(root, name, tag='missing') == []
  assert project.read_task(root, name, task_id, limit=2) == {
    'task': expected_task,
    'logs': expected_logs,
  }
  assert project.read_task(root, name, task_id, since=1_700_000_001) == {
    'task': expected_task,
    'logs': [],
  }

  project.remove_task_tags(root, name, task_id, ('storage',))
  assert project.read_tasks(root, name, tag='storage') == []


@pytest.mark.parametrize(
  ('reader', 'message'),
  [
    ('task', 'Task-log limits must be positive'),
    ('decision', 'Decision limits must be positive'),
    ('evidence', 'Evidence limits must be positive'),
  ],
  ids=('task-logs', 'decisions', 'evidence'),
)
def test_bounded_record_reads_reject_nonpositive_limits(
  project_world: ProjectWorld,
  reader: Literal['task', 'decision', 'evidence'],
  message: str,
) -> None:
  with pytest.raises(ProjectError) as error:
    if reader == 'task':
      project.read_task(
        project_world.root,
        project_world.name,
        project_world.task_id,
        limit=0,
      )
    elif reader == 'decision':
      project.read_decisions(
        project_world.root, project_world.name, limit=0
      )
    else:
      project.read_evidence(
        project_world.root, project_world.name, limit=0
      )

  assert str(error.value) == message


def test_handoff_focuses_active_task_and_bounds_related_collections(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  project.update_state(
    root, name, summary='Task is running', next_action='Finish tests'
  )
  for index in range(6):
    project.add_decision(root, name, f'Decision {index}', task=task_id)
    project.add_evidence(root, name, f'Evidence {index}', task=task_id)

  handoff = project.read_handoff(root, name)

  expected_task = {
    'id': task_id,
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
    'title_status': 'substantive',
  }
  expected_stage = {
    'id': project_world.stage_id,
    'name': 'Workflow',
    'outcome': 'Represent the lifecycle coherently',
    'purpose': '',
    'entry_conditions': '',
    'exit_evidence': 'A complete validation report',
    'position': 0,
    'achievement_generation': 0,
    'achievement_generation_started_at': 1_700_000_000,
    'created_at': 1_700_000_000,
    'updated_at': 1_700_000_000,
    'status': 'active',
    'started_at': 1_700_000_000,
    'achieved_at': None,
    'achievement_evidence_id': None,
  }
  expected_decisions = [
    {
      'id': index,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'summary': f'Decision {index - 1}',
      'decided_at': 1_700_000_000,
      'context_status': 'complete',
    }
    for index in range(6, 1, -1)
  ]
  expected_evidence = [
    {
      'id': index,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'claim': f'Evidence {index - 1}',
      'source': '',
      'result': '',
      'captured_at': 1_700_000_000,
      'context_status': 'complete',
      'claim_status': 'substantive',
      'stage_generation': 0,
    }
    for index in range(6, 1, -1)
  ]

  assert handoff == {
    'path': '.tmp/sample.sqlite3',
    'project': {
      'id': 1,
      'name': 'sample',
      'objective': 'Deliver a reliable project workflow',
      'scope': 'Project state and commands',
      'non_goals': 'Language runtime behaviour',
      'constraints_text': 'Preserve append-only history',
      'acceptance': 'Lifecycle tests and review',
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'charter_context_status': 'current',
      'status': 'active',
      'completed_at': None,
    },
    'state': {
      'id': 1,
      'summary': 'Task is running',
      'next_action': 'Finish tests',
      'updated_at': 1_700_000_000,
      'revision': 14,
    },
    'goal': None,
    'stage': expected_stage,
    'task': expected_task,
    'blocked_tasks': [],
    'blocked_goals': [],
    'blockers': [],
    'decisions': expected_decisions,
    'evidence': expected_evidence,
    'logs': [
      {
        'occurred_at': 1_700_000_000,
        'kind': 'started',
        'message': 'Task started',
      }
    ],
    'focus': {'kind': 'task', 'id': task_id},
    'pages': {
      'blocked_tasks': {'shown': 0, 'total': 0, 'truncated': False},
      'blocked_goals': {'shown': 0, 'total': 0, 'truncated': False},
      'blockers': {'shown': 0, 'total': 0, 'truncated': False},
      'decisions': {'shown': 5, 'total': 6, 'truncated': True},
      'evidence': {'shown': 5, 'total': 6, 'truncated': True},
      'task_log': {'shown': 1, 'total': 1, 'truncated': False},
    },
  }


def test_handoff_recovers_a_blocked_task_with_its_full_context(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  stage_id = project_world.stage_id
  blocker_id = project.block_task(
    root,
    name,
    task_id,
    'A required local service is unavailable',
    impact='The task cannot make progress',
    attempts='Restarted the isolated service',
    required='Restore the local service',
  )
  decision_id = project.add_decision(
    root,
    name,
    'Wait for the local service',
    task=task_id,
  )
  evidence_id = project.add_evidence(
    root,
    name,
    'The service endpoint does not respond',
    source='local probe',
    result='Connection refused',
    task=task_id,
  )

  handoff = project.read_handoff(root, name)

  assert handoff == _expected_inactive_task_handoff(
    project_world,
    project_status='blocked',
    revision=3,
    goal=None,
    blocked_tasks=[
      {
        'id': task_id,
        'title': 'Exercise the lifecycle',
        'status': 'blocked',
        'goal_id': None,
        'stage_id': stage_id,
        'stage_name': 'Workflow',
        'updated_at': 1_700_000_000,
        'title_status': 'substantive',
      }
    ],
    blocked_goals=[],
    blockers=[
      {
        'id': blocker_id,
        'goal_id': None,
        'stage_id': stage_id,
        'task_id': task_id,
        'description': 'A required local service is unavailable',
        'required': 'Restore the local service',
        'opened_at': 1_700_000_000,
        'target_kind': 'task',
        'target_id': task_id,
      }
    ],
    decisions=[
      {
        'id': decision_id,
        'goal_id': None,
        'stage_id': stage_id,
        'task_id': task_id,
        'summary': 'Wait for the local service',
        'decided_at': 1_700_000_000,
        'context_status': 'complete',
      }
    ],
    evidence=[
      {
        'id': evidence_id,
        'goal_id': None,
        'stage_id': stage_id,
        'task_id': task_id,
        'claim': 'The service endpoint does not respond',
        'source': 'local probe',
        'result': 'Connection refused',
        'captured_at': 1_700_000_000,
        'context_status': 'complete',
        'claim_status': 'substantive',
        'stage_generation': 0,
      }
    ],
    logs=[
      {
        'occurred_at': 1_700_000_000,
        'kind': 'blocked',
        'message': 'A required local service is unavailable',
      }
    ],
    focus={'kind': 'task', 'id': task_id},
    pages={
      'blocked_tasks': {'shown': 1, 'total': 1, 'truncated': False},
      'blocked_goals': {'shown': 0, 'total': 0, 'truncated': False},
      'blockers': {'shown': 1, 'total': 1, 'truncated': False},
      'decisions': {'shown': 1, 'total': 1, 'truncated': False},
      'evidence': {'shown': 1, 'total': 1, 'truncated': False},
      'task_log': {'shown': 1, 'total': 1, 'truncated': False},
    },
  )


def test_handoff_uses_goal_level_records_without_task_context(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  goal_id = project.create_goal(
    root, name, 'Resolve the full workflow outcome', [stage_id]
  )
  goal_decision = project.add_decision(
    root,
    name,
    'Keep the goal-level plan',
    stage=stage_id,
    goal=goal_id,
  )
  goal_evidence = project.add_evidence(
    root,
    name,
    'The goal-level result is still required',
    stage=stage_id,
    goal=goal_id,
  )
  task_id = project.add_task(
    root,
    name,
    'Continue the stage work',
    purpose='Keep task history separate from goal history',
    stage=stage_id,
    goal=goal_id,
    scope='Stage work',
    exclusions='Goal lifecycle',
    result='Records retain their owner',
    completion_evidence='Filtered handoff records',
  )
  project.add_decision(
    root, name, 'Record task-specific planning', task=task_id
  )
  project.add_evidence(
    root, name, 'The pending task has its own evidence', task=task_id
  )
  project.add_decision(root, name, 'Keep unrelated planning separate')
  project.add_evidence(root, name, 'Unrelated evidence remains separate')

  handoff = project.read_handoff(root, name)

  assert handoff == _expected_inactive_task_handoff(
    project_world,
    project_status='active',
    revision=8,
    goal={
      'goal': {
        'id': goal_id,
        'text': 'Resolve the full workflow outcome',
        'status': 'active',
        'status_reason': '',
        'ever_activated': 1,
        'created_at': 1_700_000_000,
        'started_at': 1_700_000_000,
        'achieved_at': None,
        'updated_at': 1_700_000_000,
      }
    },
    blocked_tasks=[],
    blocked_goals=[],
    blockers=[],
    decisions=[
      {
        'id': goal_decision,
        'goal_id': goal_id,
        'stage_id': stage_id,
        'task_id': None,
        'summary': 'Keep the goal-level plan',
        'decided_at': 1_700_000_000,
        'context_status': 'complete',
      }
    ],
    evidence=[
      {
        'id': goal_evidence,
        'goal_id': goal_id,
        'stage_id': stage_id,
        'task_id': None,
        'claim': 'The goal-level result is still required',
        'source': '',
        'result': '',
        'captured_at': 1_700_000_000,
        'context_status': 'complete',
        'claim_status': 'substantive',
        'stage_generation': 0,
      }
    ],
    logs=[],
    focus={'kind': 'goal', 'id': goal_id},
    pages={
      'blocked_tasks': {'shown': 0, 'total': 0, 'truncated': False},
      'blocked_goals': {'shown': 0, 'total': 0, 'truncated': False},
      'blockers': {'shown': 0, 'total': 0, 'truncated': False},
      'decisions': {'shown': 1, 'total': 1, 'truncated': False},
      'evidence': {'shown': 1, 'total': 1, 'truncated': False},
      'task_log': {'shown': 0, 'total': 0, 'truncated': False},
    },
  )
