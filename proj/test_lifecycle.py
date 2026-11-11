import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Never

import pytest

from proj import project
from proj.errors import ProjectError
from proj.test_support import ProjectWorld


@pytest.mark.parametrize(
  'field',
  (
    'status',
    'active_goal_id',
    'current_goal_id',
    'active_stage_id',
    'active_task_id',
    'current_task_id',
  ),
  ids=(
    'status',
    'active-goal-pointer',
    'current-goal-pointer',
    'active-stage-pointer',
    'active-task-pointer',
    'current-task-pointer',
  ),
)
def test_project_updates_reject_derived_lifecycle_fields(
  project_world: ProjectWorld, field: str
) -> None:
  with pytest.raises(ProjectError) as error:
    project.update_project(
      project_world.root,
      project_world.name,
      **{field: 'attempted override'},
    )

  assert str(error.value) == f"Unknown project fields: ['{field}']"


def test_project_status_follows_task_and_evidence_backed_stage(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  task_id = project_world.task_id

  expected_project = {
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
  }
  expected_stage = {
    'id': stage_id,
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
    'started_at': None,
    'achieved_at': None,
    'achievement_evidence_id': None,
    'dependencies': '',
  }

  assert project.read_project(root, name)[
    'project'
  ] == expected_project | {
    'status': 'active',
    'completed_at': None,
  }
  assert project.read_stages(root, name) == [
    expected_stage | {'status': 'pending'}
  ]

  project.start_task(root, name, task_id)
  assert project.read_stages(root, name) == [
    expected_stage | {'status': 'active', 'started_at': 1_700_000_000}
  ]
  project.complete_task(root, name, task_id)
  assert project.read_stages(root, name) == [
    expected_stage | {'status': 'pending', 'started_at': 1_700_000_000}
  ]

  evidence_id = project.add_evidence(
    root,
    name,
    'The required validation report is complete',
    source='pytest and review',
    result='All lifecycle cases pass',
    stage=stage_id,
  )
  project.achieve_stage(root, name, stage_id, evidence_id)

  assert project.read_stages(root, name)[0] == {
    'id': stage_id,
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
    'status': 'achieved',
    'started_at': 1_700_000_000,
    'achieved_at': 1_700_000_000,
    'achievement_evidence_id': evidence_id,
    'dependencies': '',
  }
  assert project.read_project(root, name)[
    'project'
  ] == expected_project | {
    'status': 'complete',
    'completed_at': 1_700_000_000,
  }


def test_cancelling_the_only_task_does_not_complete_its_project(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  project.cancel_task(
    root, name, project_world.task_id, 'The task is no longer needed'
  )

  assert project.read_stages(root, name) == [
    {
      'id': stage_id,
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
      'status': 'superseded',
      'started_at': None,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    }
  ]
  assert project.read_project(root, name)['project'] == {
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
  }


def test_stage_achievement_requires_completed_work_and_stage_evidence(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  task_id = project_world.task_id
  evidence_id = project.add_evidence(
    root,
    name,
    'The stage evidence belongs to this stage',
    source='pytest',
    result='No task remains pending',
    stage=stage_id,
  )

  with pytest.raises(ProjectError) as error:
    project.achieve_stage(root, name, stage_id, evidence_id)

  assert str(error.value) == (
    'Could not achieve stage: stage tasks do not establish achievement'
  )
  assert project.read_stages(root, name) == [
    {
      'id': stage_id,
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
      'status': 'pending',
      'started_at': None,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    }
  ]

  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  project.achieve_stage(root, name, stage_id, evidence_id)

  assert project.read_stages(root, name) == [
    {
      'id': stage_id,
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
      'status': 'achieved',
      'started_at': 1_700_000_000,
      'achieved_at': 1_700_000_000,
      'achievement_evidence_id': evidence_id,
      'dependencies': '',
    }
  ]


def test_stage_without_exit_evidence_cannot_be_achieved(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project.add_stage(
    root,
    name,
    'Unspecified exit',
    'Establish a testable completion contract',
  )
  task_id = project.add_task(
    root,
    name,
    'Complete the stage',
    purpose='Exercise exit evidence validation',
    stage=stage_id,
    scope='Stage achievement',
    exclusions='Other stage outcomes',
    result='The achievement contract is enforced',
    completion_evidence='The stage is complete',
  )
  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  evidence_id = project.add_evidence(
    root, name, 'The stage task is complete', stage=stage_id
  )

  with pytest.raises(ProjectError) as error:
    project.achieve_stage(root, name, stage_id, evidence_id)

  assert str(error.value) == (
    'Could not achieve stage: stage has no exit-evidence requirement'
  )
  assert project.read_stages(root, name) == [
    {
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
      'status': 'pending',
      'started_at': None,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    },
    {
      'id': stage_id,
      'name': 'Unspecified exit',
      'outcome': 'Establish a testable completion contract',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': '',
      'position': 1,
      'achievement_generation': 0,
      'achievement_generation_started_at': 1_700_000_000,
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'status': 'pending',
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    },
  ]


def test_stage_contract_change_requires_fresh_generation_evidence(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  original_evidence = project.add_evidence(
    root,
    name,
    'The original stage contract was verified',
    stage=stage_id,
  )
  unused_old_evidence = project.add_evidence(
    root,
    name,
    'A second observation from the original generation',
    stage=stage_id,
  )
  project.achieve_stage(root, name, stage_id, original_evidence)

  project.update_stage(
    root,
    name,
    stage_id,
    exit_evidence='A report for the revised contract',
  )

  assert project.read_stages(root, name) == [
    {
      'id': stage_id,
      'name': 'Workflow',
      'outcome': 'Represent the lifecycle coherently',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': 'A report for the revised contract',
      'position': 0,
      'achievement_generation': 1,
      'achievement_generation_started_at': 1_700_000_000,
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'status': 'pending',
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    }
  ]
  with pytest.raises(ProjectError) as error:
    project.achieve_stage(root, name, stage_id, unused_old_evidence)
  assert str(error.value) == (
    'Could not achieve stage: achievement evidence predates the current '
    'stage generation'
  )

  fresh_evidence = project.add_evidence(
    root,
    name,
    'The revised stage contract was verified',
    stage=stage_id,
  )
  project.achieve_stage(root, name, stage_id, fresh_evidence)

  assert project.read_stages(root, name)[0] == {
    'id': stage_id,
    'name': 'Workflow',
    'outcome': 'Represent the lifecycle coherently',
    'purpose': '',
    'entry_conditions': '',
    'exit_evidence': 'A report for the revised contract',
    'position': 0,
    'achievement_generation': 1,
    'achievement_generation_started_at': 1_700_000_000,
    'created_at': 1_700_000_000,
    'updated_at': 1_700_000_000,
    'status': 'achieved',
    'started_at': 1_700_000_000,
    'achieved_at': 1_700_000_000,
    'achievement_evidence_id': fresh_evidence,
    'dependencies': '',
  }

  project.add_task(
    root,
    name,
    'Extend the revised stage',
    purpose='Test task insertion after achievement',
    stage=stage_id,
    scope='The revised stage contract',
    exclusions='Earlier stage evidence',
    result='New work invalidates the previous achievement',
    completion_evidence='A fresh stage report',
  )

  assert project.read_stages(root, name)[0] == {
    'id': stage_id,
    'name': 'Workflow',
    'outcome': 'Represent the lifecycle coherently',
    'purpose': '',
    'entry_conditions': '',
    'exit_evidence': 'A report for the revised contract',
    'position': 0,
    'achievement_generation': 2,
    'achievement_generation_started_at': 1_700_000_000,
    'created_at': 1_700_000_000,
    'updated_at': 1_700_000_000,
    'status': 'pending',
    'started_at': 1_700_000_000,
    'achieved_at': None,
    'achievement_evidence_id': None,
    'dependencies': '',
  }


def test_moving_completed_task_invalidates_its_achieved_stage(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  first_stage = project_world.stage_id
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  evidence_id = project.add_evidence(
    root, name, 'The original stage result is verified', stage=first_stage
  )
  project.achieve_stage(root, name, first_stage, evidence_id)
  second_stage = project.add_stage(
    root,
    name,
    'Follow-up',
    'Continue the verified workflow',
    exit_evidence='A follow-up result is verified',
  )

  project.update_task(root, name, task_id, stage_id=second_stage)

  assert project.read_stages(root, name) == [
    {
      'id': first_stage,
      'name': 'Workflow',
      'outcome': 'Represent the lifecycle coherently',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': 'A complete validation report',
      'position': 0,
      'achievement_generation': 1,
      'achievement_generation_started_at': 1_700_000_000,
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'status': 'pending',
      'started_at': None,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    },
    {
      'id': second_stage,
      'name': 'Follow-up',
      'outcome': 'Continue the verified workflow',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': 'A follow-up result is verified',
      'position': 1,
      'achievement_generation': 0,
      'achievement_generation_started_at': 1_700_000_000,
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'status': 'pending',
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    },
  ]


@pytest.mark.parametrize(
  ('seconds_after_achievement', 'status', 'generation'),
  ((0, 'achieved', 0), (1, 'pending', 1)),
  ids=('equal-completion-time', 'later-completion-time'),
)
def test_moving_completed_task_into_achieved_stage_uses_completion_time(
  project_world: ProjectWorld,
  project_clock: Callable[[int], None],
  seconds_after_achievement: int,
  status: Literal['achieved', 'pending'],
  generation: Literal[0, 1],
) -> None:
  root = project_world.root
  name = project_world.name
  achieved_stage = project_world.stage_id
  original_task = project_world.task_id
  project.start_task(root, name, original_task)
  project.complete_task(root, name, original_task)
  evidence_id = project.add_evidence(
    root, name, 'The stage result is verified', stage=achieved_stage
  )
  project.achieve_stage(root, name, achieved_stage, evidence_id)

  completion_time = 1_700_000_000 + seconds_after_achievement
  project_clock(completion_time)
  source_stage = project.add_stage(
    root,
    name,
    'Later work',
    'Complete work that can move to the achieved stage',
    exit_evidence='The later work is complete',
  )
  moved_task = project.add_task(
    root,
    name,
    'Complete later work',
    purpose='Check the destination stage chronology',
    stage=source_stage,
    scope='The destination stage chronology',
    exclusions='Other stage contracts',
    result='The destination stage retains only valid achievement',
    completion_evidence='The later task completion time',
  )
  project.start_task(root, name, moved_task)
  project.complete_task(root, name, moved_task)

  project.update_task(root, name, moved_task, stage_id=achieved_stage)

  assert project.read_task(root, name, moved_task) == {
    'task': {
      'id': moved_task,
      'goal_id': None,
      'stage_id': achieved_stage,
      'title': 'Complete later work',
      'purpose': 'Check the destination stage chronology',
      'scope': 'The destination stage chronology',
      'exclusions': 'Other stage contracts',
      'result': 'The destination stage retains only valid achievement',
      'completion_evidence': 'The later task completion time',
      'status': 'completed',
      'priority': 0,
      'created_at': completion_time,
      'started_at': completion_time,
      'completed_at': completion_time,
      'updated_at': completion_time,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [
      {
        'id': 3,
        'task_id': moved_task,
        'occurred_at': completion_time,
        'kind': 'started',
        'message': 'Task started',
      },
      {
        'id': 4,
        'task_id': moved_task,
        'occurred_at': completion_time,
        'kind': 'completed',
        'message': 'Task completed',
      },
    ],
  }
  assert project.read_stages(root, name)[0] == {
    'id': achieved_stage,
    'name': 'Workflow',
    'outcome': 'Represent the lifecycle coherently',
    'purpose': '',
    'entry_conditions': '',
    'exit_evidence': 'A complete validation report',
    'position': 0,
    'achievement_generation': generation,
    'achievement_generation_started_at': completion_time,
    'created_at': 1_700_000_000,
    'updated_at': 1_700_000_000,
    'status': status,
    'started_at': 1_700_000_000,
    'achieved_at': (1_700_000_000 if status == 'achieved' else None),
    'achievement_evidence_id': (
      evidence_id if status == 'achieved' else None
    ),
    'dependencies': '',
  }


def test_rechartering_preserves_the_old_contract_and_retires_completion(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  stage_id = project_world.stage_id
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  evidence_id = project.add_evidence(
    root, name, 'The original charter was satisfied', stage=stage_id
  )
  project.achieve_stage(root, name, stage_id, evidence_id)

  project.update_project(
    root,
    name,
    objective='Deliver a revised project workflow',
    scope='Revised project state and commands',
  )

  assert project.read_project(root, name) == {
    'path': str(root / '.tmp' / 'sample.sqlite3'),
    'project': {
      'id': 1,
      'name': 'sample',
      'objective': 'Deliver a revised project workflow',
      'scope': 'Revised project state and commands',
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
      'summary': '',
      'next_action': '',
      'updated_at': 1_700_000_000,
      'revision': 5,
    },
    'goal': None,
    'charter_history': [
      {
        'id': 1,
        'objective': 'Deliver a reliable project workflow',
        'scope': 'Project state and commands',
        'non_goals': 'Language runtime behaviour',
        'constraints_text': 'Preserve append-only history',
        'acceptance': 'Lifecycle tests and review',
        'replaced_at': 1_700_000_000,
      }
    ],
  }
  assert project.read_stages(root, name) == [
    {
      'id': stage_id,
      'name': 'Workflow',
      'outcome': 'Represent the lifecycle coherently',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': 'A complete validation report',
      'position': 0,
      'achievement_generation': 1,
      'achievement_generation_started_at': 1_700_000_000,
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'status': 'pending',
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': '',
    }
  ]


@pytest.mark.parametrize(
  ('status', 'status_reason', 'has_blocker', 'revision'),
  [
    ('active', '', False, 3),
    ('blocked', 'The charter decision is unresolved', True, 4),
  ],
  ids=('active-goal', 'blocked-goal'),
)
def test_rechartering_requires_active_or_blocked_goals_to_end(
  project_world: ProjectWorld,
  status: str,
  status_reason: str,
  has_blocker: bool,
  revision: int,
) -> None:
  root = project_world.root
  name = project_world.name
  goal_id = project.create_goal(
    root, name, 'Complete the chartered work', [project_world.stage_id]
  )
  project.start_task(root, name, project_world.task_id)
  project.complete_task(root, name, project_world.task_id)
  if has_blocker:
    blocker_id = project.block_goal(
      root,
      name,
      goal_id,
      status_reason,
      required='Resolve the charter decision',
    )
    expected_blockers = [
      {
        'id': blocker_id,
        'goal_id': goal_id,
        'stage_id': None,
        'task_id': None,
        'description': status_reason,
        'impact': '',
        'attempts': '',
        'required': 'Resolve the charter decision',
        'status': 'open',
        'opened_at': 1_700_000_000,
        'resolved_at': None,
        'resolution': '',
        'target_kind': 'goal',
        'target_id': goal_id,
      }
    ]
  else:
    expected_blockers = []

  with pytest.raises(ProjectError) as error:
    project.update_project(
      root, name, objective='Replace the established charter'
    )

  assert str(error.value) == (
    'Could not update project: active task or active/pending/blocked goal '
    'requires a stable project charter; end the task and cancel active, '
    'pending, or blocked goals before re-chartering'
  )
  project_record = project.read_project(root, name)
  assert project_record['project'] == {
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
  }
  assert project_record['state'] == {
    'id': 1,
    'summary': '',
    'next_action': '',
    'updated_at': 1_700_000_000,
    'revision': revision,
  }
  assert project_record['charter_history'] == []
  assert project.read_goals(root, name) == [
    {
      'id': goal_id,
      'text': 'Complete the chartered work',
      'status': status,
      'status_reason': status_reason,
      'ever_activated': 1,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'updated_at': 1_700_000_000,
      'stage_names': 'Workflow',
      'is_active': status == 'active',
    }
  ]
  assert project.read_tasks(root, name) == [
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
      'status': 'completed',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    }
  ]
  assert (
    project.read_blockers(root, name, status='all') == expected_blockers
  )


def test_rechartering_requires_pending_goals_to_end(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  project.start_task(root, name, project_world.task_id)
  project.complete_task(root, name, project_world.task_id)
  first_goal = project.create_goal(
    root,
    name,
    'Keep the deferred goal within its charter',
    [project_world.stage_id],
  )
  active_goal = project.create_goal(
    root,
    name,
    'Keep the active goal within its charter',
    [project_world.stage_id],
  )

  with pytest.raises(ProjectError) as error:
    project.update_project(
      root, name, objective='Replace the established charter'
    )

  assert str(error.value) == (
    'Could not update project: active task or active/pending/blocked goal '
    'requires a stable project charter; end the task and cancel active, '
    'pending, or blocked goals before re-chartering'
  )
  assert project.read_goals(root, name) == [
    {
      'id': active_goal,
      'text': 'Keep the active goal within its charter',
      'status': 'active',
      'status_reason': '',
      'ever_activated': 1,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'updated_at': 1_700_000_000,
      'stage_names': 'Workflow',
      'is_active': True,
    },
    {
      'id': first_goal,
      'text': 'Keep the deferred goal within its charter',
      'status': 'pending',
      'status_reason': f'Deferred while activating goal {active_goal}',
      'ever_activated': 1,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'updated_at': 1_700_000_000,
      'stage_names': 'Workflow',
      'is_active': False,
    },
  ]


@pytest.mark.parametrize(
  ('field', 'label'),
  [
    ('purpose', 'purpose'),
    ('scope', 'scope'),
    ('exclusions', 'exclusions'),
    ('result', 'result'),
    ('completion_evidence', 'completion evidence'),
  ],
  ids=('purpose', 'scope', 'exclusions', 'result', 'completion-evidence'),
)
def test_pending_task_cannot_start_without_each_required_field(
  project_world: ProjectWorld, field: str, label: str
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project.add_task(
    root,
    name,
    f'Missing {label}',
    purpose='Purpose',
    stage=project_world.stage_id,
    scope='Scope',
    exclusions='Exclusions',
    result='Result',
    completion_evidence='Evidence',
  )
  project.update_task(root, name, task_id, **{field: ''})

  with pytest.raises(ProjectError) as error:
    project.start_task(root, name, task_id)

  assert str(error.value) == (
    f'Starting a task requires documented {label}'
  )
  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'title': f'Missing {label}',
      'purpose': '' if field == 'purpose' else 'Purpose',
      'scope': '' if field == 'scope' else 'Scope',
      'exclusions': '' if field == 'exclusions' else 'Exclusions',
      'result': '' if field == 'result' else 'Result',
      'completion_evidence': (
        '' if field == 'completion_evidence' else 'Evidence'
      ),
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [],
  }


def test_pending_task_requires_a_stage_relationship(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project.add_task(
    root,
    name,
    'Task without a stage',
    purpose='Check the relationship gate',
    scope='Task activation',
    exclusions='Stage selection',
    result='A task without a stage cannot activate',
    completion_evidence='The activation error is exact',
  )

  with pytest.raises(ProjectError) as error:
    project.start_task(root, name, task_id)

  assert str(error.value) == (
    'Starting a task requires a stage relationship'
  )
  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': None,
      'stage_id': None,
      'title': 'Task without a stage',
      'purpose': 'Check the relationship gate',
      'scope': 'Task activation',
      'exclusions': 'Stage selection',
      'result': 'A task without a stage cannot activate',
      'completion_evidence': 'The activation error is exact',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': None,
      'tags': '',
      'title_status': 'substantive',
    },
    'logs': [],
  }


def test_starting_a_task_hands_off_and_preserves_the_previous_task(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  first_task_id = project_world.task_id
  second_task_id = project.add_task(
    root,
    name,
    'Continue the workflow',
    purpose='Exercise task handoff',
    stage=project_world.stage_id,
    scope='Task activation and resumption',
    exclusions='Goal activation',
    result='Both tasks remain resumable',
    completion_evidence='Exact lifecycle records',
  )

  project.start_task(root, name, first_task_id)
  assert project.read_tasks(root, name, ready=True) == [
    {
      'id': second_task_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'title': 'Continue the workflow',
      'purpose': 'Exercise task handoff',
      'scope': 'Task activation and resumption',
      'exclusions': 'Goal activation',
      'result': 'Both tasks remain resumable',
      'completion_evidence': 'Exact lifecycle records',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    }
  ]

  project.start_task(root, name, second_task_id)

  assert project.read_task(root, name, first_task_id) == {
    'task': {
      'id': first_task_id,
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
        'task_id': first_task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'started',
        'message': 'Task started',
      },
      {
        'id': 2,
        'task_id': first_task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'handoff',
        'message': (
          'Task returned to pending while activating task '
          f'{second_task_id}'
        ),
      },
    ],
  }
  assert project.read_tasks(root, name, ready=True) == [
    {
      'id': first_task_id,
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
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Workflow',
      'tags': '',
      'title_status': 'substantive',
    }
  ]


def test_rejected_task_activation_does_not_handoff_current_task(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  first_task_id = project_world.task_id
  second_task_id = project.add_task(
    root,
    name,
    'Incomplete task',
    purpose='Exercise rejected activation',
    stage=project_world.stage_id,
    scope='An incomplete task remains pending',
    exclusions='Other lifecycle transitions',
    result='Activation rejects missing completion evidence',
  )
  project.start_task(root, name, first_task_id)
  tasks_before = project.read_tasks(root, name)
  active_task_before = project.read_task(root, name, first_task_id)

  with pytest.raises(ProjectError) as error:
    project.start_task(root, name, second_task_id)

  assert str(error.value) == (
    'Starting a task requires documented completion evidence'
  )
  assert project.read_tasks(root, name) == tasks_before
  assert project.read_task(root, name, first_task_id) == active_task_before


def test_failed_task_handoff_rolls_back_both_activations(
  project_world: ProjectWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
  root = project_world.root
  name = project_world.name
  first_task_id = project_world.task_id
  second_task_id = project.add_task(
    root,
    name,
    'Replacement task',
    purpose='Exercise transaction rollback',
    stage=project_world.stage_id,
    scope='Atomic task handoff',
    exclusions='Goal activation',
    result='A failed transaction preserves the active task',
    completion_evidence='The exact pre-transition records',
  )
  project.start_task(root, name, first_task_id)
  tasks_before = project.read_tasks(root, name)
  logs_before = project.read_task(root, name, first_task_id)

  def fail_revision_update(_connection: sqlite3.Connection) -> Never:
    raise ProjectError('Injected revision failure')

  monkeypatch.setattr(project, '_touch', fail_revision_update)
  with pytest.raises(ProjectError) as error:
    project.start_task(root, name, second_task_id)

  assert str(error.value) == 'Injected revision failure'
  assert project.read_tasks(root, name) == tasks_before
  assert project.read_task(root, name, first_task_id) == logs_before


def test_pre_execution_charter_can_be_completed_before_task_activation(
  project_root: Path, chartered_project: str
) -> None:
  name = chartered_project
  project.update_project(
    project_root,
    name,
    scope='',
    non_goals='',
    constraints_text='',
    acceptance='',
  )
  stage_id = project.add_stage(
    project_root,
    name,
    'Delivery',
    'Deliver a verified result',
    exit_evidence='A completed validation record',
  )
  goal_id = project.create_goal(
    project_root, name, 'Deliver the verified project result', [stage_id]
  )
  task_id = project.add_task(
    project_root,
    name,
    'Perform the project work',
    purpose='Fulfil the project goal',
    stage=stage_id,
    goal=goal_id,
    scope='The requested result',
    exclusions='Unrelated repository work',
    result='The requested result is delivered',
    completion_evidence='A validation record',
  )

  with pytest.raises(ProjectError) as error:
    project.start_task(project_root, name, task_id)

  assert str(error.value) == (
    'Starting work requires a complete project charter; missing: scope, '
    'non-goals, constraints, acceptance evidence'
  )
  assert project.read_tasks(project_root, name, ready=True) == []

  project.update_project(
    project_root,
    name,
    scope='Project control and implementation',
    non_goals='Unrelated language features',
    constraints_text='Preserve the charter and task boundaries',
    acceptance='A passing validation record',
  )

  assert project.read_tasks(project_root, name, ready=True) == [
    {
      'id': task_id,
      'goal_id': goal_id,
      'stage_id': stage_id,
      'title': 'Perform the project work',
      'purpose': 'Fulfil the project goal',
      'scope': 'The requested result',
      'exclusions': 'Unrelated repository work',
      'result': 'The requested result is delivered',
      'completion_evidence': 'A validation record',
      'status': 'pending',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Delivery',
      'tags': '',
      'title_status': 'substantive',
    }
  ]

  project.start_task(project_root, name, task_id)

  assert project.read_task(project_root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': goal_id,
      'stage_id': stage_id,
      'title': 'Perform the project work',
      'purpose': 'Fulfil the project goal',
      'scope': 'The requested result',
      'exclusions': 'Unrelated repository work',
      'result': 'The requested result is delivered',
      'completion_evidence': 'A validation record',
      'status': 'active',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': 1_700_000_000,
      'completed_at': None,
      'updated_at': 1_700_000_000,
      'stage_name': 'Delivery',
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
      }
    ],
  }


def test_stage_dependencies_gate_activation_and_reject_cycles(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  first_stage = project_world.stage_id
  second_stage = project.add_stage(
    root,
    name,
    'Follow-up',
    'Depend on validated workflow',
    exit_evidence='A completed follow-up report',
  )
  task_id = project.add_task(
    root,
    name,
    'Run follow-up',
    purpose='Verify dependency readiness',
    stage=second_stage,
    scope='Follow-up stage',
    exclusions='Initial stage',
    result='Dependency is honoured',
    completion_evidence='A successful follow-up result',
  )
  project.add_stage_dependency(root, name, second_stage, first_stage)
  tasks_before = project.read_tasks(root, name)
  stages_before = project.read_stages(root, name)

  with pytest.raises(ProjectError) as error:
    project.start_task(root, name, task_id)

  assert str(error.value) == 'Stage dependency is not achieved: Workflow'
  assert project.read_tasks(root, name) == tasks_before
  assert project.read_stages(root, name) == stages_before
  with pytest.raises(ProjectError) as cycle:
    project.add_stage_dependency(root, name, first_stage, second_stage)
  assert str(cycle.value) == 'Stage dependency would create a cycle'
  assert project.read_stages(root, name) == stages_before


def test_active_dependent_task_prevents_removing_its_achieved_dependency(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  prerequisite = project_world.stage_id
  dependent = project.add_stage(
    root,
    name,
    'Dependent',
    'Use the validated prerequisite',
    exit_evidence='A completed dependent result',
  )
  dependent_task = project.add_task(
    root,
    name,
    'Use the prerequisite',
    purpose='Verify active dependency stability',
    stage=dependent,
    scope='The dependent stage',
    exclusions='The prerequisite implementation',
    result='The active task retains its prerequisite',
    completion_evidence='A completed dependent result',
  )
  project.add_stage_dependency(root, name, dependent, prerequisite)
  project.start_task(root, name, project_world.task_id)
  project.complete_task(root, name, project_world.task_id)
  evidence_id = project.add_evidence(
    root,
    name,
    'The prerequisite is complete',
    stage=prerequisite,
  )
  project.achieve_stage(root, name, prerequisite, evidence_id)
  project.start_task(root, name, dependent_task)

  with pytest.raises(ProjectError) as error:
    project.remove_stage_dependency(root, name, dependent, prerequisite)

  assert str(error.value) == (
    'Could not remove stage dependency: '
    'active task requires its stage dependencies'
  )
  assert project.read_stages(root, name) == [
    {
      'id': prerequisite,
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
      'status': 'achieved',
      'started_at': 1_700_000_000,
      'achieved_at': 1_700_000_000,
      'achievement_evidence_id': evidence_id,
      'dependencies': '',
    },
    {
      'id': dependent,
      'name': 'Dependent',
      'outcome': 'Use the validated prerequisite',
      'purpose': '',
      'entry_conditions': '',
      'exit_evidence': 'A completed dependent result',
      'position': 1,
      'achievement_generation': 0,
      'achievement_generation_started_at': 1_700_000_000,
      'created_at': 1_700_000_000,
      'updated_at': 1_700_000_000,
      'status': 'active',
      'started_at': 1_700_000_000,
      'achieved_at': None,
      'achievement_evidence_id': None,
      'dependencies': 'Workflow',
    },
  ]


def test_active_dependent_task_prevents_upstream_achievement_invalidation(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  prerequisite = project_world.stage_id
  dependent = project.add_stage(
    root,
    name,
    'Dependent',
    'Use the validated prerequisite',
    exit_evidence='A completed dependent result',
  )
  alternate = project.add_stage(
    root,
    name,
    'Alternate',
    'Receive a moved prerequisite task',
    exit_evidence='The alternate task is complete',
  )
  dependent_task = project.add_task(
    root,
    name,
    'Use the prerequisite',
    purpose='Verify active dependency stability',
    stage=dependent,
    scope='The dependent stage',
    exclusions='The prerequisite implementation',
    result='The active task retains its prerequisite',
    completion_evidence='A completed dependent result',
  )
  project.add_stage_dependency(root, name, dependent, prerequisite)
  project.start_task(root, name, project_world.task_id)
  project.complete_task(root, name, project_world.task_id)
  evidence_id = project.add_evidence(
    root, name, 'The prerequisite is complete', stage=prerequisite
  )
  project.achieve_stage(root, name, prerequisite, evidence_id)
  project.start_task(root, name, dependent_task)
  tasks_before = project.read_tasks(root, name)
  stages_before = project.read_stages(root, name)

  with pytest.raises(ProjectError) as error:
    project.update_task(
      root, name, project_world.task_id, stage_id=alternate
    )

  assert str(error.value) == (
    'Could not update task: an active task depends on the stage '
    'achievement'
  )
  assert project.read_tasks(root, name) == tasks_before
  assert project.read_stages(root, name) == stages_before


def test_final_task_blocker_resolution_returns_task_to_pending(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  first = project.block_task(
    root,
    name,
    task_id,
    'Access is unavailable',
    required='Restore local access',
  )
  second = project.add_blocker(
    root,
    name,
    'Fixture data is missing',
    required='Provide deterministic fixture data',
    task=task_id,
  )

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
    'priority': 0,
    'created_at': 1_700_000_000,
    'started_at': None,
    'completed_at': None,
    'updated_at': 1_700_000_000,
    'stage_name': 'Workflow',
    'tags': '',
    'title_status': 'substantive',
  }

  assert project.read_tasks(root, name) == [
    expected_task | {'status': 'blocked'}
  ]
  project.resolve_blocker(root, name, first, 'Use the local fixture')
  assert project.read_tasks(root, name) == [
    expected_task | {'status': 'blocked'}
  ]
  project.resolve_blocker(root, name, second, 'Fixture data added')

  assert project.read_tasks(root, name) == [
    expected_task | {'status': 'pending'}
  ]
  assert project.read_blockers(root, name, status='all') == [
    {
      'id': second,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'description': 'Fixture data is missing',
      'impact': '',
      'attempts': '',
      'required': 'Provide deterministic fixture data',
      'opened_at': 1_700_000_000,
      'status': 'resolved',
      'resolved_at': 1_700_000_000,
      'resolution': 'Fixture data added',
      'target_kind': 'task',
      'target_id': task_id,
    },
    {
      'id': first,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'description': 'Access is unavailable',
      'impact': '',
      'attempts': '',
      'required': 'Restore local access',
      'opened_at': 1_700_000_000,
      'status': 'resolved',
      'resolved_at': 1_700_000_000,
      'resolution': 'Use the local fixture',
      'target_kind': 'task',
      'target_id': task_id,
    },
  ]
  assert project.read_task(root, name, task_id)['logs'] == [
    {
      'id': 1,
      'task_id': task_id,
      'occurred_at': 1_700_000_000,
      'kind': 'blocked',
      'message': 'Access is unavailable',
    },
    {
      'id': 2,
      'task_id': task_id,
      'occurred_at': 1_700_000_000,
      'kind': 'blocker-resolved',
      'message': 'Use the local fixture',
    },
    {
      'id': 3,
      'task_id': task_id,
      'occurred_at': 1_700_000_000,
      'kind': 'blocker-resolved',
      'message': 'Fixture data added',
    },
    {
      'id': 4,
      'task_id': task_id,
      'occurred_at': 1_700_000_000,
      'kind': 'unblocked',
      'message': 'All task blockers resolved',
    },
  ]


def test_cancelling_blocked_task_withdraws_its_blockers(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  blocker_id = project.block_task(
    root,
    name,
    task_id,
    'Required service is unavailable',
    required='Restore the service',
  )

  project.cancel_task(root, name, task_id, 'No longer needed')

  assert project.read_task(root, name, task_id) == {
    'task': {
      'id': task_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'title': 'Exercise the lifecycle',
      'purpose': 'Guard state transitions',
      'scope': 'Task and stage status',
      'exclusions': 'CLI presentation',
      'result': 'Transitions produce the documented state',
      'completion_evidence': 'Exact returned lifecycle records',
      'status': 'cancelled',
      'priority': 0,
      'created_at': 1_700_000_000,
      'started_at': None,
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
        'kind': 'blocked',
        'message': 'Required service is unavailable',
      },
      {
        'id': 2,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'cancelled',
        'message': 'No longer needed',
      },
    ],
  }
  assert project.read_blockers(root, name, status='all') == [
    {
      'id': blocker_id,
      'goal_id': None,
      'stage_id': project_world.stage_id,
      'task_id': task_id,
      'description': 'Required service is unavailable',
      'impact': '',
      'attempts': '',
      'required': 'Restore the service',
      'opened_at': 1_700_000_000,
      'status': 'withdrawn',
      'resolved_at': 1_700_000_000,
      'resolution': 'No longer needed',
      'target_kind': 'task',
      'target_id': task_id,
    }
  ]


def test_reopening_completed_task_preserves_start_time_and_task_history(
  project_world: ProjectWorld,
) -> None:
  root = project_world.root
  name = project_world.name
  task_id = project_world.task_id
  project.start_task(root, name, task_id)
  project.complete_task(root, name, task_id)
  project.reopen_task(root, name, task_id)

  assert project.read_task(root, name, task_id) == {
    'task': {
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
        'kind': 'completed',
        'message': 'Task completed',
      },
      {
        'id': 3,
        'task_id': task_id,
        'occurred_at': 1_700_000_000,
        'kind': 'reopened',
        'message': 'Task reopened',
      },
    ],
  }
