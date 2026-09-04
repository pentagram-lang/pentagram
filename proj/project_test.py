import base64
import json
import shlex
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from click.testing import CliRunner

from proj.project import (
  ProjectError,
  achieve_goal,
  achieve_stage,
  add_blocker,
  add_decision,
  add_evidence,
  add_stage,
  add_stage_dependency,
  add_task,
  add_task_tags,
  append_task_log,
  archive_project,
  block_goal,
  block_task,
  cancel_goal,
  cancel_task,
  complete_task,
  copy_goal,
  create_goal,
  create_project,
  format_handoff,
  goal_text,
  list_projects,
  open_project,
  project_group,
  read_blockers,
  read_decisions,
  read_evidence,
  read_goal,
  read_goals,
  read_handoff,
  read_project,
  read_stages,
  read_task,
  read_tasks,
  remove_stage_dependency,
  remove_task_tags,
  reopen_goal,
  reopen_task,
  resolve_blocker,
  start_task,
  update_project,
  update_stage,
  update_state,
  update_task,
)
from proj.project import (
  connect as connect_project_database,
)

TASK_DOCUMENTATION = {
  'purpose': 'Advance the stage outcome.',
  'scope': 'Only the named work.',
  'exclusions': 'No adjacent work.',
  'result': 'The named result exists.',
  'completion_evidence': 'The focused checks pass.',
}


def direct_database_connection(path):
  connection = connect_project_database(path)
  connection.execute('PRAGMA foreign_keys = OFF')
  return connection


class ProjectTestCase(unittest.TestCase):
  def setUp(self):
    self.directory = tempfile.TemporaryDirectory()
    self.root = Path(self.directory.name)

  def tearDown(self):
    self.directory.cleanup()

  def create_project(self, name='demo', objective='Reach the outcome'):
    return create_project(
      self.root,
      name,
      objective,
      scope='Complete the named project work.',
      non_goals='No work outside the named project.',
      constraints='Keep the recorded authority boundaries.',
      acceptance='The project outcome and checks are established.',
    )

  def add_documented_task(self, title='Do the work', **values):
    if 'stage' not in values:
      stages = read_stages(self.root, 'demo')
      values['stage'] = (
        stages[0]['id']
        if stages
        else add_stage(self.root, 'demo', 'work', 'Complete the work')
      )
    return add_task(
      self.root,
      'demo',
      title,
      **{**TASK_DOCUMENTATION, **values},
    )

  def complete_stage(self, stage, goal=None, title='Complete stage'):
    task = self.add_documented_task(
      title,
      stage=stage,
      goal=goal,
    )
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    evidence = add_evidence(
      self.root,
      'demo',
      'The stage result is established.',
      source='focused check',
      result='pass',
      stage=stage,
      task=task,
      goal=goal,
    )
    achieve_stage(self.root, 'demo', stage, evidence)
    return task, evidence


class ProjectLifecycleTest(ProjectTestCase):
  def test_create_archives_same_name_without_overwriting(self):
    first = self.create_project(objective='First outcome')
    second = create_project(self.root, 'demo', 'Second outcome')

    archives = list(
      (self.root / '.tmp' / 'archive').glob('demo-*.sqlite3')
    )
    self.assertEqual(len(archives), 1)
    self.assertEqual(first, second)
    self.assertEqual(
      read_project(self.root, 'demo')['project']['objective'],
      'Second outcome',
    )
    connection = direct_database_connection(archives[0])
    try:
      self.assertEqual(
        connection.execute('SELECT objective FROM project').fetchone()[0],
        'First outcome',
      )
    finally:
      connection.close()

  def test_project_and_stage_statuses_are_derived_from_tasks(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'build', 'Build the result')
    task = self.add_documented_task(stage=stage)

    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'pending'
    )
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'active'
    )

    start_task(self.root, 'demo', task)
    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['stage']['status'], 'active')
    self.assertEqual(handoff['task']['id'], task)

    blocker = block_task(
      self.root, 'demo', task, 'Waiting', required='Dependency available'
    )
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'blocked'
    )
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'blocked'
    )

    resolve_blocker(self.root, 'demo', blocker, 'Available')
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'pending'
    )

    cancel_task(self.root, 'demo', task)
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'superseded'
    )
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'active'
    )

  def test_stage_achievement_requires_terminal_tasks_and_named_evidence(
    self,
  ):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='Focused checks pass.',
    )
    task = self.add_documented_task(stage=stage)
    evidence = add_evidence(
      self.root, 'demo', 'A premature observation', stage=stage
    )

    with self.assertRaisesRegex(
      ProjectError, 'stage tasks do not establish achievement'
    ):
      achieve_stage(self.root, 'demo', stage, evidence)

    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    unrelated = add_evidence(self.root, 'demo', 'Other evidence')
    with self.assertRaisesRegex(
      ProjectError, 'achievement evidence does not belong to stage'
    ):
      achieve_stage(self.root, 'demo', stage, unrelated)

    achieve_stage(self.root, 'demo', stage, evidence)
    stage_record = read_stages(self.root, 'demo')[0]
    self.assertEqual(stage_record['status'], 'achieved')
    self.assertEqual(stage_record['achievement_evidence_id'], evidence)
    self.assertIsNotNone(stage_record['achieved_at'])
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'complete'
    )

  def test_stage_without_exit_evidence_cannot_be_achieved(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'build', 'Build the result')
    task = self.add_documented_task(stage=stage)
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    evidence = add_evidence(self.root, 'demo', 'Result', stage=stage)

    with self.assertRaisesRegex(ProjectError, 'exit-evidence requirement'):
      achieve_stage(self.root, 'demo', stage, evidence)

  def test_task_change_atomically_invalidates_stage_achievement(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='Checks pass.',
    )
    task, evidence = self.complete_stage(stage)

    reopen_task(self.root, 'demo', task)

    stage_record = read_stages(self.root, 'demo')[0]
    self.assertEqual(stage_record['status'], 'pending')
    self.assertIsNone(stage_record['achievement_evidence_id'])
    connection = open_project(self.root, 'demo')
    try:
      achievement = connection.execute(
        'SELECT evidence_id, invalidated_at FROM stage_achievement'
      ).fetchone()
      self.assertEqual(achievement['evidence_id'], evidence)
      self.assertIsNotNone(achievement['invalidated_at'])
    finally:
      connection.close()

  def test_task_and_requirement_changes_invalidate_achievement(
    self,
  ):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='Checks pass.',
    )
    self.complete_stage(stage)

    self.add_documented_task('Follow-up', stage=stage)
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'pending'
    )
    pending = read_tasks(self.root, 'demo', status='pending')[0]
    cancel_task(self.root, 'demo', pending['id'])
    evidence = add_evidence(
      self.root, 'demo', 'Re-established', stage=stage
    )
    achieve_stage(self.root, 'demo', stage, evidence)
    update_stage(
      self.root, 'demo', stage, exit_evidence='A stronger check passes.'
    )
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'pending'
    )
    evidence = add_evidence(
      self.root, 'demo', 'Stronger check passed', stage=stage
    )
    achieve_stage(self.root, 'demo', stage, evidence)
    update_stage(self.root, 'demo', stage, outcome='Build another result')
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'pending'
    )

  def test_task_movement_revalidates_achievement_chronology(self):
    self.create_project()
    destination = add_stage(
      self.root,
      'demo',
      'destination',
      'Complete the destination',
      exit_evidence='Checks pass.',
    )
    source = add_stage(self.root, 'demo', 'source', 'Complete the source')
    self.complete_stage(destination)
    moved = self.add_documented_task('Moved work', stage=source)
    connection = open_project(self.root, 'demo')
    try:
      achieved_at = connection.execute(
        'SELECT achieved_at FROM stage_achievement '
        'WHERE stage_id = ? AND invalidated_at IS NULL',
        (destination,),
      ).fetchone()[0]
      connection.execute(
        "UPDATE task SET status = 'active', started_at = ? WHERE id = ?",
        (achieved_at, moved),
      )
      connection.execute(
        "UPDATE task SET status = 'completed', completed_at = ? "
        'WHERE id = ?',
        (achieved_at, moved),
      )
      connection.execute(
        'UPDATE task SET stage_id = ? WHERE id = ?',
        (destination, moved),
      )
      connection.commit()
      self.assertEqual(
        connection.execute(
          'SELECT count(*) FROM stage_achievement '
          'WHERE stage_id = ? AND invalidated_at IS NULL',
          (destination,),
        ).fetchone()[0],
        1,
      )
    finally:
      connection.close()

    update_task(self.root, 'demo', moved, stage_id=source)
    reopen_task(self.root, 'demo', moved)
    start_task(self.root, 'demo', moved)
    while int(time.time()) <= achieved_at:
      time.sleep(0.05)
    complete_task(self.root, 'demo', moved)
    update_task(self.root, 'demo', moved, stage_id=destination)

    stages = {
      stage['id']: stage for stage in read_stages(self.root, 'demo')
    }
    self.assertEqual(stages[destination]['status'], 'pending')
    self.assertIsNone(stages[destination]['achievement_evidence_id'])
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'active'
    )

  def test_task_movement_cannot_invalidate_an_active_prerequisite(self):
    self.create_project()
    prerequisite = add_stage(
      self.root,
      'demo',
      'prerequisite',
      'Complete the prerequisite',
      exit_evidence='Checks pass.',
    )
    source = add_stage(self.root, 'demo', 'source', 'Complete the source')
    dependent = add_stage(
      self.root, 'demo', 'dependent', 'Complete dependent work'
    )
    self.complete_stage(prerequisite)
    add_stage_dependency(self.root, 'demo', dependent, prerequisite)
    active = self.add_documented_task('Dependent work', stage=dependent)
    start_task(self.root, 'demo', active)
    connection = open_project(self.root, 'demo')
    try:
      achieved_at = connection.execute(
        'SELECT achieved_at FROM stage_achievement '
        'WHERE stage_id = ? AND invalidated_at IS NULL',
        (prerequisite,),
      ).fetchone()[0]
    finally:
      connection.close()
    moved = self.add_documented_task('Later work', stage=source)
    cancel_task(self.root, 'demo', active)
    start_task(self.root, 'demo', moved)
    while int(time.time()) <= achieved_at:
      time.sleep(0.05)
    complete_task(self.root, 'demo', moved)
    reopen_task(self.root, 'demo', active)
    start_task(self.root, 'demo', active)

    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'active task depends'
      ):
        connection.execute(
          'UPDATE task SET stage_id = ? WHERE id = ?',
          (prerequisite, moved),
        )
      connection.rollback()
      self.assertEqual(
        connection.execute(
          'SELECT count(*) FROM stage_achievement '
          'WHERE stage_id = ? AND invalidated_at IS NULL',
          (prerequisite,),
        ).fetchone()[0],
        1,
      )
    finally:
      connection.close()

  def test_reachievement_requires_fresh_unused_evidence(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='Checks pass.',
    )
    task, first_evidence = self.complete_stage(stage)
    stale_evidence = add_evidence(
      self.root, 'demo', 'Another old observation', stage=stage
    )

    reopen_task(self.root, 'demo', task)
    connection = open_project(self.root, 'demo')
    try:
      self.assertEqual(
        connection.execute(
          'SELECT stage_generation FROM evidence WHERE id = ?',
          (stale_evidence,),
        ).fetchone()[0],
        0,
      )
      self.assertEqual(
        connection.execute(
          'SELECT achievement_generation FROM stage WHERE id = ?',
          (stage,),
        ).fetchone()[0],
        1,
      )
    finally:
      connection.close()
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)

    with self.assertRaisesRegex(ProjectError, 'already used'):
      achieve_stage(self.root, 'demo', stage, first_evidence)
    with self.assertRaisesRegex(ProjectError, 'current stage generation'):
      achieve_stage(self.root, 'demo', stage, stale_evidence)
    fresh_evidence = add_evidence(
      self.root, 'demo', 'The changed result passes', stage=stage
    )
    achieve_stage(self.root, 'demo', stage, fresh_evidence)
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'achieved'
    )

  def test_dependencies_gate_ready_and_active_tasks(self):
    self.create_project()
    first = add_stage(
      self.root,
      'demo',
      'frame',
      'Frame the work',
      exit_evidence='Frame evidence',
    )
    second = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='Build evidence',
    )
    add_stage_dependency(self.root, 'demo', second, first)
    first_task = self.add_documented_task('Frame', stage=first)
    second_task = self.add_documented_task('Build', stage=second)

    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [first_task],
    )
    with self.assertRaisesRegex(
      ProjectError, 'dependency is not achieved'
    ):
      start_task(self.root, 'demo', second_task)

    start_task(self.root, 'demo', first_task)
    complete_task(self.root, 'demo', first_task)
    evidence = add_evidence(self.root, 'demo', 'Frame done', stage=first)
    achieve_stage(self.root, 'demo', first, evidence)
    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [second_task],
    )
    start_task(self.root, 'demo', second_task)
    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'requires its stage dependencies'
      ):
        connection.execute(
          'DELETE FROM stage_dependency '
          'WHERE stage_id = ? AND dependency_id = ?',
          (second, first),
        )
    finally:
      connection.close()
    with self.assertRaisesRegex(
      sqlite3.IntegrityError, 'active task depends'
    ):
      reopen_task(self.root, 'demo', first_task)
    with self.assertRaisesRegex(
      sqlite3.IntegrityError, 'active task depends'
    ):
      update_stage(self.root, 'demo', first, outcome='A changed frame')
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'achieved'
    )
    self.assertEqual(
      read_task(self.root, 'demo', second_task)['task']['status'],
      'active',
    )

  def test_dependency_cycles_are_rejected(self):
    self.create_project()
    first = add_stage(self.root, 'demo', 'first', 'First')
    second = add_stage(self.root, 'demo', 'second', 'Second')
    add_stage_dependency(self.root, 'demo', second, first)

    with self.assertRaisesRegex(ProjectError, 'cycle'):
      add_stage_dependency(self.root, 'demo', first, second)

  def test_dependency_removal_requires_inactive_dependent_work(self):
    self.create_project()
    prerequisite = add_stage(
      self.root,
      'demo',
      'prerequisite',
      'Establish the prerequisite',
      exit_evidence='Focused checks pass.',
    )
    dependent = add_stage(
      self.root, 'demo', 'dependent', 'Complete the dependent work'
    )
    add_stage_dependency(self.root, 'demo', dependent, prerequisite)
    task = self.add_documented_task(stage=dependent)
    self.assertEqual(read_tasks(self.root, 'demo', ready=True), [])

    remove_stage_dependency(self.root, 'demo', dependent, prerequisite)
    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [task],
    )
    with self.assertRaisesRegex(ProjectError, 'does not depend on stage'):
      remove_stage_dependency(self.root, 'demo', dependent, prerequisite)

    add_stage_dependency(self.root, 'demo', dependent, prerequisite)
    self.complete_stage(prerequisite)
    start_task(self.root, 'demo', task)
    with self.assertRaisesRegex(
      ProjectError, 'active task requires its stage dependencies'
    ):
      remove_stage_dependency(self.root, 'demo', dependent, prerequisite)
    cancel_task(self.root, 'demo', task)
    remove_stage_dependency(self.root, 'demo', dependent, prerequisite)

  def test_only_one_task_can_be_active(self):
    self.create_project()
    first = self.add_documented_task('First')
    second = self.add_documented_task('Second')
    start_task(self.root, 'demo', first)

    self.assertEqual(read_tasks(self.root, 'demo', ready=True), [])
    with self.assertRaisesRegex(ProjectError, 'already active'):
      start_task(self.root, 'demo', second)

  def test_projects_can_run_without_goals(self):
    self.create_project()
    task = self.add_documented_task()
    start_task(self.root, 'demo', task)

    handoff = read_handoff(self.root, 'demo')
    self.assertIsNone(handoff['goal'])
    self.assertEqual(handoff['task']['id'], task)

  def test_task_activation_requires_complete_documentation(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = add_task(self.root, 'demo', 'Undocumented', stage=stage)

    with self.assertRaisesRegex(
      ProjectError,
      'documented purpose, scope, exclusions, result, completion evidence',
    ):
      start_task(self.root, 'demo', task)

    update_task(self.root, 'demo', task, **TASK_DOCUMENTATION)
    start_task(self.root, 'demo', task)
    self.assertEqual(
      read_task(self.root, 'demo', task)['task']['status'], 'active'
    )

  def test_task_activation_requires_a_structured_stage_relationship(self):
    self.create_project()
    task = add_task(
      self.root,
      'demo',
      'Unassigned work',
      **TASK_DOCUMENTATION,
    )

    self.assertEqual(read_tasks(self.root, 'demo', ready=True), [])
    with self.assertRaisesRegex(ProjectError, 'stage relationship'):
      start_task(self.root, 'demo', task)

  def test_task_lifecycle_preserves_timing_logs_and_tags(self):
    self.create_project()
    task = self.add_documented_task(tags=('schema',))
    add_task_tags(self.root, 'demo', task, ('migration',))
    start_task(self.root, 'demo', task)
    append_task_log(self.root, 'demo', task, 'Implementation progressed')
    complete_task(self.root, 'demo', task)
    completed = read_task(self.root, 'demo', task)

    self.assertIsNotNone(completed['task']['started_at'])
    self.assertIsNotNone(completed['task']['completed_at'])
    self.assertEqual(completed['task']['status'], 'completed')
    self.assertEqual(completed['task']['tags'], 'migration, schema')
    self.assertEqual(
      [entry['kind'] for entry in completed['logs']],
      ['started', 'note', 'completed'],
    )

    reopen_task(self.root, 'demo', task)
    remove_task_tags(self.root, 'demo', task, ('schema',))
    reopened = read_task(self.root, 'demo', task)
    self.assertEqual(reopened['task']['status'], 'pending')
    self.assertIsNone(reopened['task']['completed_at'])
    self.assertEqual(reopened['task']['tags'], 'migration')

  def test_task_log_reads_are_bounded(self):
    self.create_project()
    task = self.add_documented_task()
    for index in range(4):
      append_task_log(self.root, 'demo', task, f'Entry {index}')

    self.assertEqual(
      len(read_task(self.root, 'demo', task, limit=2)['logs']), 2
    )
    with self.assertRaisesRegex(ProjectError, 'limits must be positive'):
      read_task(self.root, 'demo', task, limit=0)

  def test_blocked_task_reopens_only_after_its_last_blocker(self):
    self.create_project()
    task = self.add_documented_task()
    first = block_task(
      self.root, 'demo', task, 'First blocker', required='Resolve first'
    )
    second = add_blocker(
      self.root,
      'demo',
      'Second blocker',
      required='Resolve second',
      task=task,
    )

    resolve_blocker(self.root, 'demo', first, 'First resolved')
    self.assertEqual(
      read_task(self.root, 'demo', task)['task']['status'], 'blocked'
    )
    resolve_blocker(self.root, 'demo', second, 'Second resolved')
    self.assertEqual(
      read_task(self.root, 'demo', task)['task']['status'], 'pending'
    )

  def test_cancelling_blocked_task_withdraws_its_blockers(self):
    self.create_project()
    task = self.add_documented_task()
    blocker = block_task(
      self.root,
      'demo',
      task,
      'No longer relevant',
      required='Remove the work',
    )

    cancel_task(self.root, 'demo', task, 'Work removed')

    self.assertEqual(
      read_task(self.root, 'demo', task)['task']['status'], 'cancelled'
    )
    record = next(
      item
      for item in read_blockers(self.root, 'demo', 'all')
      if item['id'] == blocker
    )
    self.assertEqual(record['status'], 'withdrawn')
    self.assertEqual(record['resolution'], 'Work removed')


class GoalLifecycleTest(ProjectTestCase):
  def add_stage(self, name='stage'):
    return add_stage(
      self.root,
      'demo',
      name,
      'Produce the stage outcome',
      exit_evidence='The result is established.',
    )

  def test_goal_links_stages_and_controls_task_activation(self):
    self.create_project()
    first = self.add_stage('first')
    second = self.add_stage('second')
    goal = create_goal(
      self.root, 'demo', 'Reach both outcomes', [first, second]
    )
    linked = self.add_documented_task(stage=first, goal=goal)
    unlinked = self.add_documented_task('Unlinked', stage=first)

    start_task(self.root, 'demo', linked)
    complete_task(self.root, 'demo', linked)
    with self.assertRaisesRegex(ProjectError, 'must link to goal'):
      start_task(self.root, 'demo', unlinked)

    record = read_goal(self.root, 'demo', goal)
    self.assertEqual(
      [stage['id'] for stage in record['stages']], [first, second]
    )
    self.assertEqual(record['tasks'][0]['id'], linked)

  def test_only_one_goal_can_be_active(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'First goal', [stage])

    with self.assertRaisesRegex(
      ProjectError, 'already has an active goal'
    ):
      create_goal(self.root, 'demo', 'Second goal', [stage])

    cancel_goal(self.root, 'demo', goal, 'Replaced')
    second = create_goal(self.root, 'demo', 'Second goal', [stage])
    self.assertEqual(
      read_goal(self.root, 'demo', second)['goal']['status'], 'active'
    )

  def test_goal_cannot_activate_while_a_goal_less_task_is_active(self):
    self.create_project()
    stage = self.add_stage()
    task = self.add_documented_task(stage=stage)
    start_task(self.root, 'demo', task)

    with self.assertRaisesRegex(ProjectError, 'active task .* end first'):
      create_goal(self.root, 'demo', 'Goal', [stage])

  def test_goal_achievement_requires_evidence_and_no_active_task(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    start_task(self.root, 'demo', task)

    with self.assertRaisesRegex(ProjectError, 'evidence entry'):
      achieve_goal(self.root, 'demo', goal)

    evidence = add_evidence(
      self.root, 'demo', 'Goal result', stage=stage, task=task, goal=goal
    )
    with self.assertRaisesRegex(ProjectError, 'active task .* end first'):
      achieve_goal(self.root, 'demo', goal)

    complete_task(self.root, 'demo', task)
    achieve_goal(self.root, 'demo', goal)
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'achieved'
    )
    self.assertIsNone(read_handoff(self.root, 'demo')['goal'])
    self.assertEqual(read_goals(self.root, 'demo')[0]['is_active'], 0)
    self.assertEqual(evidence, 1)

    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'achievement evidence is immutable'
      ):
        connection.execute(
          "UPDATE evidence SET claim = 'Changed' WHERE id = ?",
          (evidence,),
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'achievement evidence cannot be deleted'
      ):
        connection.execute(
          'DELETE FROM evidence WHERE id = ?', (evidence,)
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'achieved goal evidence is fixed'
      ):
        connection.execute(
          'INSERT INTO evidence '
          '(goal_id, claim, captured_at) VALUES (?, ?, ?)',
          (goal, 'Later', 10),
        )
    finally:
      connection.close()
    with self.assertRaisesRegex(ProjectError, 'evidence is fixed'):
      add_evidence(self.root, 'demo', 'Later', goal=goal)

  def test_goal_achievement_preserves_scope_and_chronology(self):
    self.create_project()
    first = self.add_stage('first')
    second = self.add_stage('second')
    goal = create_goal(self.root, 'demo', 'Goal', [first])
    evidence = add_evidence(self.root, 'demo', 'Goal result', goal=goal)
    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'lacks required evidence'
      ):
        connection.execute(
          "UPDATE goal SET status = 'achieved', achieved_at = 0 "
          'WHERE id = ?',
          (goal,),
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'scope is already fixed'
      ):
        connection.execute(
          'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
          (goal, second),
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'scope is already fixed'
      ):
        connection.execute(
          'DELETE FROM goal_stage WHERE goal_id = ? AND stage_id = ?',
          (goal, first),
        )
    finally:
      connection.close()

    achieve_goal(self.root, 'demo', goal)
    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'lifecycle is immutable'
      ):
        connection.execute(
          'UPDATE goal SET achieved_at = 0 WHERE id = ?', (goal,)
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'scope is already fixed'
      ):
        connection.execute(
          'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
          (goal, second),
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'scope is already fixed'
      ):
        connection.execute(
          'DELETE FROM goal_stage WHERE goal_id = ? AND stage_id = ?',
          (goal, first),
        )
    finally:
      connection.close()
    self.assertEqual(evidence, 1)

  def test_terminal_cancelled_goal_cannot_be_reactivated(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    goal = create_goal(self.root, 'demo', 'Original goal', [stage])
    cancel_goal(self.root, 'demo', goal, 'Replaced')

    connection = open_project(self.root, 'demo')
    try:
      row = connection.execute(
        'SELECT status, ever_activated, status_reason '
        'FROM goal WHERE id = ?',
        (goal,),
      ).fetchone()
      self.assertEqual(tuple(row), ('cancelled', 1, 'Replaced'))
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'invalid goal status transition'
      ):
        connection.execute(
          "UPDATE goal SET status = 'active' WHERE id = ?", (goal,)
        )
    finally:
      connection.close()

  def test_task_blockers_do_not_block_their_contextual_goal(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    start_task(self.root, 'demo', task)

    blocker = add_blocker(
      self.root,
      'demo',
      'Task dependency',
      required='Supply the dependency',
      stage=stage,
      task=task,
      goal=goal,
    )

    self.assertEqual(
      read_task(self.root, 'demo', task)['task']['status'], 'blocked'
    )
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'active'
    )
    resolve_blocker(self.root, 'demo', blocker, 'Available')
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'active'
    )

  def test_goal_blocking_requires_active_task_to_end(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    start_task(self.root, 'demo', task)

    with self.assertRaisesRegex(ProjectError, 'active task .* end first'):
      block_goal(
        self.root,
        'demo',
        goal,
        'External decision',
        required='Supply the decision',
      )

    block_task(
      self.root, 'demo', task, 'Task paused', required='End the task'
    )
    blocker = block_goal(
      self.root,
      'demo',
      goal,
      'External decision',
      required='Supply the decision',
    )
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'blocked'
    )
    self.assertIsNone(read_handoff(self.root, 'demo')['goal'])
    resolve_blocker(self.root, 'demo', blocker, 'Decision arrived')
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'active'
    )

  def test_cancelling_blocked_goal_withdraws_blockers(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    blocker = block_goal(
      self.root,
      'demo',
      goal,
      'No longer relevant',
      required='Remove the goal',
    )

    cancel_goal(self.root, 'demo', goal, 'Goal removed')

    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'cancelled'
    )
    self.assertEqual(
      read_blockers(self.root, 'demo', 'all')[0]['id'], blocker
    )
    self.assertEqual(
      read_blockers(self.root, 'demo', 'all')[0]['status'], 'withdrawn'
    )

  def test_blocked_goal_can_be_cancelled_while_another_goal_is_active(
    self,
  ):
    self.create_project()
    first = self.add_stage('first')
    second = self.add_stage('second')
    blocked = create_goal(self.root, 'demo', 'Blocked goal', [first])
    block_goal(
      self.root, 'demo', blocked, 'Wait', required='Resolve the wait'
    )
    active = create_goal(self.root, 'demo', 'Active goal', [second])

    cancel_goal(self.root, 'demo', blocked, 'No longer needed')

    self.assertEqual(
      read_goal(self.root, 'demo', blocked)['goal']['status'],
      'cancelled',
    )
    self.assertEqual(
      read_goal(self.root, 'demo', active)['goal']['status'], 'active'
    )

  def test_final_goal_blocker_waits_for_reactivation_conditions(self):
    self.create_project()
    first = self.add_stage('first')
    second = self.add_stage('second')
    blocked = create_goal(self.root, 'demo', 'Blocked goal', [first])
    blocker = block_goal(
      self.root,
      'demo',
      blocked,
      'Wait',
      required='Supply the result',
    )
    active = create_goal(self.root, 'demo', 'Active goal', [second])

    with self.assertRaisesRegex(ProjectError, 'goal .* is active'):
      resolve_blocker(self.root, 'demo', blocker, 'Available')
    self.assertEqual(
      read_goal(self.root, 'demo', blocked)['goal']['status'], 'blocked'
    )
    cancel_goal(self.root, 'demo', active, 'Focus returned')
    resolve_blocker(self.root, 'demo', blocker, 'Available')
    self.assertEqual(
      read_goal(self.root, 'demo', blocked)['goal']['status'], 'active'
    )

  def test_goal_scope_remains_fixed_while_blocked_or_cancelled(self):
    self.create_project()
    first = self.add_stage('first')
    second = self.add_stage('second')
    goal = create_goal(self.root, 'demo', 'Goal', [first])
    block_goal(
      self.root,
      'demo',
      goal,
      'Wait',
      required='Supply the result',
    )
    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'scope is already fixed'
      ):
        connection.execute(
          'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
          (goal, second),
        )
    finally:
      connection.close()

    cancel_goal(self.root, 'demo', goal, 'No longer needed')
    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'scope is already fixed'
      ):
        connection.execute(
          'DELETE FROM goal_stage WHERE goal_id = ?', (goal,)
        )
    finally:
      connection.close()

  def test_reopen_requires_a_blocked_goal_without_open_blockers(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    blocker = block_goal(
      self.root, 'demo', goal, 'Wait', required='Resolve the wait'
    )

    with self.assertRaisesRegex(ProjectError, 'open blockers'):
      reopen_goal(self.root, 'demo', goal)

    connection = open_project(self.root, 'demo')
    try:
      with connection:
        trigger_sql = connection.execute(
          "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
          "AND name = 'release_resolved_blocker'"
        ).fetchone()[0]
        connection.execute('DROP TRIGGER release_resolved_blocker')
        connection.execute(
          "UPDATE blocker SET status = 'resolved', resolved_at = 1, "
          "resolution = 'Available' "
          'WHERE id = ?',
          (blocker,),
        )
        connection.execute(trigger_sql)
    finally:
      connection.close()
    reopen_goal(self.root, 'demo', goal)
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'active'
    )

  def test_blocked_goal_reason_tracks_the_current_open_blocker(self):
    self.create_project()
    stage = self.add_stage()
    goal = create_goal(self.root, 'demo', 'Complete the project', [stage])
    first = block_goal(
      self.root,
      'demo',
      goal,
      'First condition',
      required='Resolve the first condition',
    )
    second = add_blocker(
      self.root,
      'demo',
      'Second condition',
      required='Resolve the second condition',
      goal=goal,
    )

    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status_reason'],
      'Second condition',
    )
    self.assertEqual(
      read_handoff(self.root, 'demo')['blocked_goals'][0]['status_reason'],
      'Second condition',
    )

    resolve_blocker(self.root, 'demo', second, 'Second condition resolved')
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status_reason'],
      'First condition',
    )
    resolve_blocker(self.root, 'demo', first, 'First condition resolved')
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status_reason'], ''
    )

  def test_goal_text_and_copy_preserve_canonical_content(self):
    self.create_project()
    stage = self.add_stage()
    content = '  Exact goal\nwith Unicode: λ  '
    goal = create_goal(self.root, 'demo', content, [stage])

    self.assertEqual(goal_text(self.root, 'demo', goal), content)
    sequence = copy_goal(self.root, 'demo', goal)
    encoded = sequence.removeprefix('\x1b]52;c;').removesuffix('\x07')
    self.assertEqual(base64.b64decode(encoded).decode(), content)

  def test_goal_text_validation_and_stage_relationships(self):
    self.create_project()
    stage = self.add_stage()
    other = self.add_stage('other')
    with self.assertRaisesRegex(ProjectError, 'non-whitespace'):
      create_goal(self.root, 'demo', '   ', [stage])
    with self.assertRaisesRegex(ProjectError, '4,000.*4,001'):
      create_goal(self.root, 'demo', 'x' * 4001, [stage])
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    with self.assertRaisesRegex(ProjectError, 'not linked'):
      self.add_documented_task(stage=other, goal=goal)


class ProjectRecordTest(ProjectTestCase):
  def test_decisions_evidence_blockers_and_handoff_are_queryable(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'build', 'Build')
    task = self.add_documented_task(stage=stage)
    decision = add_decision(
      self.root,
      'demo',
      'Use the normalized lifecycle',
      rationale='One authority',
      stage=stage,
      task=task,
    )
    evidence = add_evidence(
      self.root,
      'demo',
      'The schema can be queried directly',
      source='SQLite',
      result='pass',
      stage=stage,
      task=task,
    )
    blocker = add_blocker(
      self.root,
      'demo',
      'Dependency unavailable',
      required='Supply the dependency',
      stage=stage,
      task=task,
    )
    update_state(
      self.root,
      'demo',
      summary='The lifecycle is normalized.',
      next_action='Resolve the dependency.',
    )

    self.assertEqual(read_decisions(self.root, 'demo')[0]['id'], decision)
    self.assertEqual(read_evidence(self.root, 'demo')[0]['id'], evidence)
    self.assertEqual(read_blockers(self.root, 'demo')[0]['id'], blocker)
    handoff = read_handoff(self.root, 'demo')
    rendered = format_handoff(handoff)
    self.assertIsNone(handoff['task'])
    self.assertIn('Active stage: -', rendered)
    self.assertIn('Active task: -', rendered)
    self.assertNotIn('Current stage', rendered)
    self.assertNotIn('Current task', rendered)
    self.assertIn('The lifecycle is normalized.', rendered)
    self.assertEqual(handoff['blocked_tasks'][0]['id'], task)
    self.assertEqual(handoff['blockers'][0]['target_kind'], 'task')
    self.assertEqual(handoff['blockers'][0]['target_id'], task)

  def test_handoff_bounds_and_explains_recovery_context(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'build', 'Build')
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    start_task(self.root, 'demo', task)
    for index in range(7):
      add_decision(
        self.root, 'demo', f'Decision {index}', task=task, stage=stage
      )
      add_evidence(
        self.root, 'demo', f'Evidence {index}', task=task, stage=stage
      )
      append_task_log(self.root, 'demo', task, f'Log {index}')

    active = read_handoff(self.root, 'demo')
    self.assertEqual(set(active['goal']), {'goal'})
    self.assertEqual(active['focus'], {'kind': 'task', 'id': task})
    self.assertEqual(len(active['decisions']), 5)
    self.assertEqual(active['pages']['decisions']['total'], 7)
    self.assertTrue(active['pages']['decisions']['truncated'])
    self.assertIn(
      f'--task {task} --limit 7', active['retrieval']['decisions']
    )
    self.assertEqual(len(active['evidence']), 5)
    self.assertEqual(active['pages']['evidence']['total'], 7)
    self.assertEqual(len(active['logs']), 5)
    self.assertEqual(active['pages']['task_log']['total'], 8)

    block_task(
      self.root,
      'demo',
      task,
      'First blocker',
      required='Supply the dependency',
    )
    for index in range(6):
      add_blocker(
        self.root,
        'demo',
        f'Blocker {index}',
        required=f'Resolve {index}',
        task=task,
      )
    blocked = read_handoff(self.root, 'demo')
    rendered = format_handoff(blocked)
    self.assertIsNone(blocked['task'])
    self.assertEqual(blocked['blocked_tasks'][0]['id'], task)
    self.assertEqual(len(blocked['blockers']), 5)
    self.assertEqual(blocked['pages']['blockers']['total'], 7)
    self.assertTrue(blocked['pages']['blockers']['truncated'])
    self.assertTrue(
      all(item['task_id'] == task for item in blocked['blockers'])
    )
    self.assertIn(f'task {task}', rendered)
    self.assertIn('required:', rendered)
    self.assertIn('0 proj blocker list --json -- demo', rendered)
    self.assertEqual(
      blocked['retrieval']['blocked_tasks'],
      '0 proj task list --status blocked --json -- demo',
    )

  def test_goal_handoff_retrieval_matches_goal_level_projection(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    goal = create_goal(self.root, 'demo', 'Complete the goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    goal_decisions = [
      add_decision(self.root, 'demo', f'Goal decision {index}', goal=goal)
      for index in range(2)
    ]
    goal_evidence = [
      add_evidence(self.root, 'demo', f'Goal evidence {index}', goal=goal)
      for index in range(2)
    ]
    for index in range(3):
      add_decision(self.root, 'demo', f'Task decision {index}', task=task)
      add_evidence(self.root, 'demo', f'Task evidence {index}', task=task)

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['focus'], {'kind': 'goal', 'id': goal})
    self.assertEqual(
      [item['id'] for item in handoff['decisions']],
      list(reversed(goal_decisions)),
    )
    self.assertEqual(
      [item['id'] for item in handoff['evidence']],
      list(reversed(goal_evidence)),
    )
    self.assertIn(
      f'--goal {goal} --no-task --limit 2 --json',
      handoff['retrieval']['decisions'],
    )
    self.assertEqual(
      [
        item['id']
        for item in read_decisions(
          self.root, 'demo', 2, goal=goal, no_task=True
        )
      ],
      list(reversed(goal_decisions)),
    )
    self.assertEqual(
      [
        item['id']
        for item in read_evidence(
          self.root, 'demo', 2, goal=goal, no_task=True
        )
      ],
      list(reversed(goal_evidence)),
    )
    runner = CliRunner()
    decision_output = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'decision',
        'list',
        'demo',
        '--goal',
        str(goal),
        '--no-task',
        '--limit',
        '2',
        '--json',
      ],
    )
    self.assertEqual(decision_output.exit_code, 0, decision_output.output)
    self.assertEqual(
      [item['id'] for item in json.loads(decision_output.output)],
      list(reversed(goal_decisions)),
    )
    evidence_output = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'evidence',
        'list',
        'demo',
        '--goal',
        str(goal),
        '--no-task',
        '--limit',
        '2',
        '--json',
      ],
    )
    self.assertEqual(evidence_output.exit_code, 0, evidence_output.output)
    self.assertEqual(
      [item['id'] for item in json.loads(evidence_output.output)],
      list(reversed(goal_evidence)),
    )
    with self.assertRaisesRegex(ProjectError, 'filters conflict'):
      read_decisions(self.root, 'demo', task=task, goal=goal, no_task=True)

  def test_handoff_bounds_text_and_preserves_full_value_reads(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'build', 'Build')
    large = ('x\n\t' * 70_000) + 'x'
    task = add_task(
      self.root,
      'demo',
      large,
      purpose=large,
      scope=large,
      exclusions=large,
      result=large,
      completion_evidence=large,
      stage=stage,
    )
    start_task(self.root, 'demo', task)

    handoff = read_handoff(self.root, 'demo')
    rendered = format_handoff(handoff)

    projection = handoff['text_projection']
    self.assertEqual(projection['character_limit'], 1000)
    self.assertEqual(
      [item['path'] for item in projection['truncated_fields']],
      ['task.title'],
    )
    self.assertEqual(handoff['task']['title'], large)
    self.assertEqual(handoff['task']['purpose'], large)
    self.assertEqual(
      json.loads(json.dumps(handoff))['task']['title'], large
    )
    self.assertLess(len(rendered), 5_000)
    self.assertNotIn(large, rendered)
    command = f'0 proj task show --json -- demo {task}'
    self.assertIn(command, projection['full_value_commands'])
    self.assertIn(command, rendered)

    runner = CliRunner()
    for action in ('status', 'handoff'):
      with self.subTest(action=action):
        output = runner.invoke(
          project_group,
          ['--root', str(self.root), action, 'demo', '--json'],
        )
        self.assertEqual(output.exit_code, 0, output.output)
        self.assertEqual(json.loads(output.output)['task']['title'], large)

  def test_handoff_does_not_report_hidden_fields_as_truncated(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'build', 'Build')
    task = add_task(
      self.root,
      'demo',
      'Visible title',
      purpose='x' * 2000,
      scope='Visible scope',
      exclusions='Visible exclusions',
      result='Visible result',
      completion_evidence='Visible evidence',
      stage=stage,
    )
    start_task(self.root, 'demo', task)

    handoff = read_handoff(self.root, 'demo')
    rendered = format_handoff(handoff)

    self.assertEqual(handoff['task']['purpose'], 'x' * 2000)
    self.assertEqual(handoff['text_projection']['truncated_fields'], [])
    self.assertEqual(handoff['text_projection']['full_value_commands'], [])
    self.assertNotIn('Text projection:', rendered)
    self.assertNotIn('Full values:', rendered)

  def test_text_outputs_escape_structure_and_json_preserves_values(self):
    objective = 'Objective\nStatus: spoofed'
    stage_name = 'build\nActive stage: spoofed'
    stage_outcome = 'Outcome\tInjected'
    goal_text_value = 'Goal\nActive task: 999 Spoofed'
    task_title = 'Task\tInjected'
    summary = 'Summary\nNext action: spoofed'
    next_action = 'Next\tAction'
    decision_summary = 'Decision\n999\tInjected'
    evidence_claim = 'Evidence\n999\tInjected'
    log_message = 'Log\n999\tInjected'
    blocker_description = 'Blocker\n999\tInjected'
    blocker_required = 'Required\tAction'

    self.create_project(objective=objective)
    stage = add_stage(self.root, 'demo', stage_name, stage_outcome)
    goal = create_goal(self.root, 'demo', goal_text_value, [stage])
    task = self.add_documented_task(task_title, stage=stage, goal=goal)
    start_task(self.root, 'demo', task)
    update_state(
      self.root,
      'demo',
      summary=summary,
      next_action=next_action,
    )
    add_decision(self.root, 'demo', decision_summary, task=task)
    add_evidence(self.root, 'demo', evidence_claim, task=task)
    append_task_log(self.root, 'demo', task, log_message)
    add_blocker(
      self.root,
      'demo',
      blocker_description,
      required=blocker_required,
      task=task,
    )

    runner = CliRunner()

    def invoke(*arguments):
      result = runner.invoke(
        project_group, ['--root', str(self.root), *arguments]
      )
      self.assertEqual(result.exit_code, 0, result.output)
      return result.output

    text_outputs = (
      invoke('status', 'demo'),
      invoke('show', 'demo'),
      invoke('goal', 'list', 'demo'),
      invoke('stage', 'list', 'demo'),
      invoke('task', 'list', 'demo'),
      invoke('task', 'logs', 'demo', str(task)),
      invoke('decision', 'list', 'demo'),
      invoke('blocker', 'list', 'demo'),
      invoke('evidence', 'list', 'demo'),
    )
    rendered = '\n'.join(text_outputs)
    values = (
      objective,
      stage_name,
      stage_outcome,
      goal_text_value,
      task_title,
      summary,
      next_action,
      decision_summary,
      evidence_claim,
      log_message,
      blocker_description,
      blocker_required,
    )
    for value in values:
      with self.subTest(value=value):
        self.assertNotIn(value, rendered)
        escaped = json.dumps(value, ensure_ascii=False)[1:-1]
        self.assertIn(escaped, rendered)

    handoff = json.loads(invoke('status', 'demo', '--json'))
    self.assertEqual(handoff['project']['objective'], objective)
    self.assertEqual(handoff['state']['summary'], summary)
    self.assertEqual(handoff['state']['next_action'], next_action)
    self.assertEqual(handoff['goal']['goal']['text'], goal_text_value)
    self.assertEqual(handoff['blocked_tasks'][0]['title'], task_title)
    self.assertEqual(handoff['blocked_tasks'][0]['stage_name'], stage_name)
    self.assertEqual(
      handoff['blockers'][0]['description'], blocker_description
    )
    self.assertEqual(handoff['decisions'][0]['summary'], decision_summary)
    self.assertEqual(handoff['evidence'][0]['claim'], evidence_claim)
    self.assertEqual(handoff['logs'][-2]['message'], log_message)

  def test_project_names_produce_exact_safe_recovery_commands(self):
    runner = CliRunner()
    for name in (
      'demo space',
      "demo'quote",
      '-leading',
      'demo;$(echo-nope)',
    ):
      with self.subTest(name=name):
        self.create_project(name)
        handoff = read_handoff(self.root, name)
        command = handoff['retrieval']['project']
        arguments = shlex.split(command)
        self.assertEqual(arguments[:2], ['0', 'proj'])
        self.assertEqual(arguments[-1], name)
        self.assertEqual(arguments[-2], '--')
        result = runner.invoke(
          project_group,
          ['--root', str(self.root), *arguments[2:]],
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(
          json.loads(result.output)['project']['name'], name
        )
        rendered = format_handoff(handoff)
        self.assertEqual(rendered.splitlines()[0], f'Project: {name}')

  def test_project_names_reject_control_characters(self):
    for name in ('demo\nActive task: 999 Spoofed', 'demo\tstate'):
      with (
        self.subTest(name=name),
        self.assertRaisesRegex(ProjectError, 'printable'),
      ):
        self.create_project(name)

  def test_project_names_reject_addresses_over_recovery_limit(self):
    name = 'x' * 201
    with self.assertRaisesRegex(ProjectError, 'at most 200 characters'):
      self.create_project(name)
    self.assertFalse((self.root / '.tmp' / f'{name}.sqlite3').exists())

  def test_handoff_path_is_relative_and_cannot_create_false_lines(self):
    rooted = self.root / 'root\nActive task: 999 Spoofed\tcolumn'
    create_project(
      rooted,
      'demo',
      'Reach the outcome',
      scope='Complete the named project work.',
      non_goals='No work outside the named project.',
      constraints='Keep the recorded authority boundaries.',
      acceptance='The project outcome and checks are established.',
    )

    handoff = read_handoff(rooted, 'demo')
    rendered = format_handoff(handoff)

    self.assertEqual(handoff['path'], '.tmp/demo.sqlite3')
    self.assertIn('Project database: .tmp/demo.sqlite3', rendered)
    self.assertNotIn(str(rooted), rendered)
    self.assertEqual(
      len(
        [
          line
          for line in rendered.splitlines()
          if line.startswith('Active task:')
        ]
      ),
      1,
    )

  def test_long_quoted_project_address_keeps_recovery_bounded(self):
    name = "'" * 200
    self.create_project(name)
    update_state(self.root, name, summary='x' * 2000)

    handoff = read_handoff(self.root, name)
    rendered = format_handoff(handoff)
    commands = {
      command
      for command in handoff['retrieval'].values()
      if command is not None
    }
    commands.update(handoff['text_projection']['full_value_commands'])

    self.assertTrue(commands)
    self.assertTrue(all(len(command) <= 1000 for command in commands))
    self.assertTrue(
      all(
        '\n' not in command and '\t' not in command for command in commands
      )
    )
    self.assertTrue(
      all(shlex.split(command)[-1] == name for command in commands)
    )
    self.assertTrue(
      all(
        len(line) <= 1000
        for line in rendered.splitlines()
        if line.startswith('- Full values: ')
      )
    )

    command = handoff['retrieval']['project']
    arguments = shlex.split(command)
    result = CliRunner().invoke(
      project_group,
      ['--root', str(self.root), *arguments[2:]],
    )
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertEqual(json.loads(result.output)['project']['name'], name)

  def test_existing_control_character_address_is_left_unchanged(self):
    self.create_project('legacy')
    unsafe_name = 'legacy\nspoof'
    original_path = self.root / '.tmp' / 'legacy.sqlite3'
    connection = direct_database_connection(original_path)
    try:
      connection.execute('DROP TRIGGER project_name_update')
      connection.execute(
        'UPDATE project SET name = ? WHERE id = 1', (unsafe_name,)
      )
      connection.commit()
    finally:
      connection.close()
    unsafe_path = self.root / '.tmp' / f'{unsafe_name}.sqlite3'
    original_path.rename(unsafe_path)
    before = unsafe_path.read_bytes()

    with self.assertRaisesRegex(ProjectError, 'printable'):
      read_project(self.root, unsafe_name)

    self.assertEqual(unsafe_path.read_bytes(), before)

  def test_all_handoff_recovery_commands_quote_project_name(self):
    name = "demo space'-$()"
    self.create_project(name)
    stage = add_stage(self.root, name, 'work', 'Complete the work')
    goal = create_goal(self.root, name, 'Complete the project', [stage])
    task = add_task(
      self.root,
      name,
      'Do the work',
      stage=stage,
      goal=goal,
      **TASK_DOCUMENTATION,
    )
    start_task(self.root, name, task)
    add_decision(self.root, name, 'Use the bounded method', task=task)
    add_evidence(self.root, name, 'The method is bounded', task=task)
    handoff = read_handoff(self.root, name)
    runner = CliRunner()
    for key, command in handoff['retrieval'].items():
      if command is None:
        continue
      with self.subTest(key=key):
        arguments = shlex.split(command)
        self.assertIn('--', arguments)
        self.assertEqual(arguments[arguments.index('--') + 1], name)
        result = runner.invoke(
          project_group,
          ['--root', str(self.root), *arguments[2:]],
        )
        self.assertEqual(result.exit_code, 0, result.output)

  def test_bounded_reads_reject_nonpositive_limits(self):
    self.create_project()
    with self.assertRaisesRegex(ProjectError, 'Decision limits'):
      read_decisions(self.root, 'demo', 0)
    with self.assertRaisesRegex(ProjectError, 'Evidence limits'):
      read_evidence(self.root, 'demo', 0)

  def test_project_updates_do_not_accept_status_or_entity_pointers(self):
    self.create_project()
    update_project(self.root, 'demo', acceptance='All stages achieved.')
    self.assertEqual(
      read_project(self.root, 'demo')['project']['acceptance'],
      'All stages achieved.',
    )
    with self.assertRaisesRegex(ProjectError, 'Unknown project fields'):
      update_project(self.root, 'demo', status='complete')
    with self.assertRaises(TypeError):
      update_state(self.root, 'demo', current_task=1)

  def test_archive_removes_project_from_unarchived_list(self):
    self.create_project()
    self.assertEqual(
      [item['name'] for item in list_projects(self.root)], ['demo']
    )
    destination = archive_project(self.root, 'demo')
    self.assertTrue(destination.is_file())
    self.assertEqual(list_projects(self.root), [])


class ProjectConstraintTest(ProjectTestCase):
  def connection(self):
    return open_project(self.root, 'demo')

  def test_task_activation_requires_complete_project_charter(self):
    create_project(self.root, 'demo', 'Reach the outcome')
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)

    self.assertEqual(read_tasks(self.root, 'demo', ready=True), [])
    with self.assertRaisesRegex(ProjectError, 'complete project charter'):
      start_task(self.root, 'demo', task)

    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'complete project charter'
      ):
        connection.execute(
          "UPDATE task SET status = 'active', started_at = 1 WHERE id = ?",
          (task,),
        )
    finally:
      connection.close()

    update_project(
      self.root,
      'demo',
      scope='Complete the named work.',
      non_goals='No adjacent work.',
      constraints_text='Respect the project authority.',
      acceptance='The outcome evidence is recorded.',
    )
    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [task],
    )
    start_task(self.root, 'demo', task)
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'stable project charter'
      ):
        connection.execute("UPDATE project SET scope = '   ' WHERE id = 1")
    finally:
      connection.close()

  def test_pre_execution_goal_allows_incremental_charter_construction(
    self,
  ):
    create_project(self.root, 'demo', 'Reach the outcome')
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    goal = create_goal(self.root, 'demo', 'Complete the project', [stage])

    connection = self.connection()
    try:
      connection.execute(
        "UPDATE project SET scope = 'Complete the named work.'"
      )
      connection.commit()
    finally:
      connection.close()
    blocker = block_goal(
      self.root,
      'demo',
      goal,
      'The charter needs a decision',
      required='Complete the charter decision',
    )
    update_project(
      self.root,
      'demo',
      non_goals='No adjacent work.',
      constraints_text='Respect the project authority.',
      acceptance='The outcome evidence is recorded.',
    )

    project = read_project(self.root, 'demo')
    self.assertEqual(project['charter_history'], [])
    self.assertEqual(
      project['project']['scope'], 'Complete the named work.'
    )
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'blocked'
    )
    resolve_blocker(self.root, 'demo', blocker, 'The charter is complete')
    self.assertEqual(
      read_goal(self.root, 'demo', goal)['goal']['status'], 'active'
    )

  def test_rechartering_retires_completion_and_preserves_contract(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'work',
      'Complete the original outcome',
      exit_evidence='The original checks pass.',
    )
    task, first_evidence = self.complete_stage(stage)
    original = read_project(self.root, 'demo')['project']
    self.assertEqual(original['status'], 'complete')

    update_project(
      self.root,
      'demo',
      objective='Reach the replacement outcome',
      acceptance='The replacement checks are established.',
    )
    project = read_project(self.root, 'demo')
    self.assertEqual(project['project']['status'], 'active')
    self.assertEqual(len(project['charter_history']), 1)
    self.assertEqual(
      project['charter_history'][0]['objective'], original['objective']
    )
    self.assertEqual(
      project['charter_history'][0]['acceptance'], original['acceptance']
    )
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'pending'
    )

    connection = self.connection()
    try:
      achievement = connection.execute(
        'SELECT invalidated_at FROM stage_achievement '
        'WHERE evidence_id = ?',
        (first_evidence,),
      ).fetchone()
      self.assertIsNotNone(achievement['invalidated_at'])
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'charter history is immutable'
      ):
        connection.execute(
          "UPDATE project_charter_history SET objective = 'Changed'"
        )
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'charter history cannot be deleted'
      ):
        connection.execute('DELETE FROM project_charter_history')
    finally:
      connection.close()

    replacement_evidence = add_evidence(
      self.root,
      'demo',
      'The stage remains established under the replacement charter.',
      stage=stage,
      task=task,
    )
    achieve_stage(self.root, 'demo', stage, replacement_evidence)
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'complete'
    )

    reopen_task(self.root, 'demo', task)
    start_task(self.root, 'demo', task)
    with self.assertRaisesRegex(ProjectError, 'stable project charter'):
      update_project(self.root, 'demo', scope='A changed project scope.')

  def test_rechartering_requires_active_or_blocked_goal_cancellation(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    goal = create_goal(
      self.root, 'demo', 'Deliver the original result', [stage]
    )
    task = self.add_documented_task(stage=stage, goal=goal)
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)

    with self.assertRaisesRegex(ProjectError, 'cancel the goal'):
      update_project(self.root, 'demo', objective='Replacement result')
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'cancel the goal'
      ):
        connection.execute(
          "UPDATE project SET objective = 'Replacement result'"
        )
    finally:
      connection.close()

    cancel_goal(self.root, 'demo', goal, 'The charter is changing')
    update_project(self.root, 'demo', objective='Replacement result')
    replacement = create_goal(
      self.root, 'demo', 'Deliver the replacement result', [stage]
    )
    block_goal(
      self.root,
      'demo',
      replacement,
      'A decision is missing',
      required='Make the decision',
    )
    with self.assertRaisesRegex(ProjectError, 'cancel the goal'):
      update_project(self.root, 'demo', scope='Replacement scope')
    cancel_goal(self.root, 'demo', replacement, 'Re-charter again')
    update_project(self.root, 'demo', scope='Replacement scope')

  def test_project_and_stage_outcomes_require_substantive_text(self):
    with self.assertRaisesRegex(ProjectError, 'Project objective'):
      create_project(self.root, 'blank', '   ')
    self.create_project()
    with self.assertRaisesRegex(ProjectError, 'Stage name'):
      add_stage(self.root, 'demo', '   ', 'Outcome')
    with self.assertRaisesRegex(ProjectError, 'Stage outcome'):
      add_stage(self.root, 'demo', 'work', '   ')

    stage = add_stage(self.root, 'demo', 'work', 'Outcome')
    with self.assertRaisesRegex(ProjectError, 'Stage outcome'):
      update_stage(self.root, 'demo', stage, outcome='   ')
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'stage name and outcome'
      ):
        connection.execute(
          'INSERT INTO stage '
          '(name, outcome, created_at, updated_at) '
          "VALUES ('other', '   ', 1, 1)"
        )
    finally:
      connection.close()

  def test_new_task_titles_require_substantive_text(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    with self.assertRaisesRegex(
      ProjectError, '[Tt]ask title must contain'
    ):
      add_task(self.root, 'demo', '   ', stage=stage)

    task = self.add_documented_task(stage=stage)
    with self.assertRaisesRegex(
      ProjectError, 'task title must contain text'
    ):
      update_task(self.root, 'demo', task, title='   ')

    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'task title must contain text'
      ):
        connection.execute(
          'INSERT INTO task (title, created_at, updated_at) '
          "VALUES ('   ', 1, 1)"
        )
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'task title must contain text'
      ):
        connection.execute(
          "UPDATE task SET title = '   ' WHERE id = ?", (task,)
        )
    finally:
      connection.close()

  def test_unicode_whitespace_uses_one_substantive_text_contract(self):
    whitespace = ('\t', '\n', '\u00a0', ' \t\n\u00a0 ')
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)

    for index, value in enumerate(whitespace):
      with self.subTest(surface='project objective', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Project objective'):
          create_project(self.root, f'blank-{index}', value)
      with self.subTest(surface='stage name', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Stage name'):
          add_stage(self.root, 'demo', value, 'Outcome')
      with self.subTest(surface='stage outcome', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Stage outcome'):
          add_stage(self.root, 'demo', f'blank-stage-{index}', value)
      with self.subTest(surface='goal text', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'non-whitespace'):
          create_goal(self.root, 'demo', value, [stage])
      with self.subTest(surface='task title', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Task title'):
          add_task(self.root, 'demo', value, stage=stage)
      with self.subTest(surface='blocker description', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Blocker description'):
          add_blocker(
            self.root,
            'demo',
            value,
            required='Resolve the condition',
            task=task,
          )
      with self.subTest(surface='blocker requirement', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Blocker requirement'):
          add_blocker(
            self.root,
            'demo',
            'Condition exists',
            required=value,
            task=task,
          )
      with self.subTest(surface='evidence claim', value=repr(value)):
        with self.assertRaisesRegex(ProjectError, 'Evidence claim'):
          add_evidence(self.root, 'demo', value, task=task)

    connection = self.connection()
    try:
      for value in whitespace:
        with (
          self.subTest(
            surface='canonical SQL predicate', value=repr(value)
          ),
          self.assertRaisesRegex(
            sqlite3.IntegrityError, 'task title must contain text'
          ),
        ):
          connection.execute(
            'INSERT INTO task (title, created_at, updated_at) '
            'VALUES (?, 1, 1)',
            (value,),
          )
        connection.rollback()
    finally:
      connection.close()

    for index, field in enumerate(
      ('scope', 'non_goals', 'constraints_text', 'acceptance')
    ):
      name = f'charter-whitespace-{index}'
      self.create_project(name)
      stage_id = add_stage(self.root, name, 'work', 'Complete the work')
      task_id = add_task(
        self.root,
        name,
        'Do the work',
        stage=stage_id,
        **TASK_DOCUMENTATION,
      )
      update_project(
        self.root, name, **{field: whitespace[index % len(whitespace)]}
      )
      with (
        self.subTest(surface=f'project {field}'),
        self.assertRaisesRegex(ProjectError, 'complete project charter'),
      ):
        start_task(self.root, name, task_id)

    for index, field in enumerate(
      ('purpose', 'scope', 'exclusions', 'result', 'completion_evidence')
    ):
      name = f'task-whitespace-{index}'
      self.create_project(name)
      stage_id = add_stage(self.root, name, 'work', 'Complete the work')
      documentation = dict(TASK_DOCUMENTATION)
      documentation[field] = whitespace[index % len(whitespace)]
      task_id = add_task(
        self.root,
        name,
        'Do the work',
        stage=stage_id,
        **documentation,
      )
      with (
        self.subTest(surface=f'task {field}'),
        self.assertRaisesRegex(ProjectError, 'Starting a task requires'),
      ):
        start_task(self.root, name, task_id)

    name = 'stage-exit-whitespace'
    self.create_project(name)
    stage_id = add_stage(
      self.root,
      name,
      'work',
      'Complete the work',
      exit_evidence='\u00a0',
    )
    task_id = add_task(
      self.root,
      name,
      'Do the work',
      stage=stage_id,
      **TASK_DOCUMENTATION,
    )
    start_task(self.root, name, task_id)
    complete_task(self.root, name, task_id)
    evidence_id = add_evidence(
      self.root, name, 'The result is established.', stage=stage_id
    )
    with self.assertRaisesRegex(ProjectError, 'exit-evidence requirement'):
      achieve_stage(self.root, name, stage_id, evidence_id)

  def test_current_open_rejects_forged_unicode_whitespace_state(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)
    start_task(self.root, 'demo', task)
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      connection.execute('PRAGMA ignore_check_constraints = ON')
      connection.execute(
        'UPDATE task SET completion_evidence = ? WHERE id = ?',
        ('\u00a0', task),
      )
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'integrity check failed'):
      open_project(self.root, 'demo')

  def test_legacy_lifecycle_rejects_new_history(self):
    self.create_project()
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError,
        'legacy lifecycle history does not accept inserts',
      ):
        connection.execute(
          'INSERT INTO legacy_lifecycle '
          '(source_schema_version, entity_kind, entity_id, status, '
          'was_selected, migrated_at) '
          "VALUES (5, 'task', 1, 'pending', 0, 1)"
        )
    finally:
      connection.close()

  def test_future_achievement_times_are_rejected(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'work',
      'Complete the work',
      exit_evidence='Checks pass.',
    )
    task = self.add_documented_task(stage=stage)
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    evidence = add_evidence(self.root, 'demo', 'Checks pass.', stage=stage)
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'stage achievement is in the future'
      ):
        connection.execute(
          'INSERT INTO stage_achievement '
          '(stage_id, evidence_id, achieved_at, stage_generation) '
          'VALUES (?, ?, 9999999999, 0)',
          (stage, evidence),
        )
    finally:
      connection.close()

    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    add_evidence(self.root, 'demo', 'Goal result.', goal=goal)
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'goal achievement lacks required evidence'
      ):
        connection.execute(
          "UPDATE goal SET status = 'achieved', achieved_at = 9999999999 "
          'WHERE id = ?',
          (goal,),
        )
    finally:
      connection.close()

  def test_schema_omits_stored_project_stage_and_pointer_state(self):
    self.create_project()
    connection = self.connection()
    try:
      project = {
        row['name']
        for row in connection.execute('PRAGMA table_info(project)')
      }
      stage = {
        row['name']
        for row in connection.execute('PRAGMA table_info(stage)')
      }
      state = {
        row['name']
        for row in connection.execute('PRAGMA table_info(project_state)')
      }
    finally:
      connection.close()
    self.assertNotIn('status', project)
    self.assertNotIn('status', stage)
    self.assertEqual(
      state, {'id', 'summary', 'next_action', 'updated_at', 'revision'}
    )

  def test_schema_preserves_project_singletons_and_open_validates_them(
    self,
  ):
    self.create_project()
    connection = self.connection()
    try:
      for table, message in (
        ('project', 'project charter'),
        ('project_state', 'project state'),
      ):
        with self.assertRaisesRegex(sqlite3.IntegrityError, message):
          connection.execute(f'DELETE FROM {table}')
        connection.rollback()
      connection.execute('DROP TRIGGER project_state_delete')
      connection.execute('DELETE FROM project_state')
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'one project-state row'):
      open_project(self.root, 'demo')

  def test_project_name_is_immutable_and_must_match_its_address(self):
    self.create_project()
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'name is immutable'
      ):
        connection.execute("UPDATE project SET name = 'renamed'")
      connection.rollback()
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'project_name_update'"
      ).fetchone()[0]
      connection.execute('DROP TRIGGER project_name_update')
      connection.execute("UPDATE project SET name = 'renamed'")
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'database address'):
      read_project(self.root, 'demo')

  def test_schema_rejects_removed_statuses(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    task = self.add_documented_task(stage=stage)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE task SET status = 'verifying' WHERE id = ?", (task,)
        )
      connection.rollback()
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'INSERT INTO goal '
          '(text, status, created_at, started_at, updated_at) '
          "VALUES ('Old', 'superseded', 1, 1, 1)"
        )
    finally:
      connection.close()

  def test_schema_rejects_two_active_tasks(self):
    self.create_project()
    first = self.add_documented_task('First')
    second = self.add_documented_task('Second')
    start_task(self.root, 'demo', first)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE task SET status = 'active', started_at = 1 WHERE id = ?",
          (second,),
        )
    finally:
      connection.close()

  def test_schema_rejects_blocked_entities_without_blockers(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE task SET status = 'blocked' WHERE id = ?", (task,)
        )
      connection.rollback()
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE goal SET status = 'blocked' WHERE id = ?", (goal,)
        )
    finally:
      connection.close()

  def test_schema_rejects_active_task_with_wrong_goal(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE task SET status = 'active', started_at = 1 WHERE id = ?",
          (task,),
        )
    finally:
      connection.close()

  def test_schema_rejects_task_goal_stage_mismatch(self):
    self.create_project()
    linked = add_stage(self.root, 'demo', 'linked', 'Linked')
    other = add_stage(self.root, 'demo', 'other', 'Other')
    goal = create_goal(self.root, 'demo', 'Goal', [linked])
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          """
          INSERT INTO task
            (goal_id, stage_id, title, created_at, updated_at)
          VALUES (?, ?, 'Invalid', 1, 1)
          """,
          (goal, other),
        )
    finally:
      connection.close()

  def test_schema_rejects_invalid_direct_task_transition(self):
    self.create_project()
    task = self.add_documented_task()
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE task SET status = 'completed', started_at = 1, "
          'completed_at = 1 WHERE id = ?',
          (task,),
        )
    finally:
      connection.close()

  def test_schema_preserves_blocker_lifecycle(self):
    self.create_project()
    task = self.add_documented_task()
    blocker = block_task(
      self.root, 'demo', task, 'Wait', required='Resolve the wait'
    )
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE task SET status = 'pending' WHERE id = ?", (task,)
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE blocker SET task_id = NULL WHERE id = ?', (blocker,)
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE blocker SET status = 'resolved' WHERE id = ?",
          (blocker,),
        )
    finally:
      connection.close()

    resolve_blocker(self.root, 'demo', blocker, 'Available')
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE blocker SET status = 'open', resolved_at = NULL, "
          "resolution = '' WHERE id = ?",
          (blocker,),
        )
    finally:
      connection.close()

  def test_blockers_require_descriptions_and_recovery_requirements(self):
    self.create_project()
    task = self.add_documented_task()
    with self.assertRaisesRegex(ProjectError, 'Blocker requirement'):
      block_task(self.root, 'demo', task, 'Wait')
    with self.assertRaisesRegex(ProjectError, 'Blocker description'):
      block_task(
        self.root, 'demo', task, ' ', required='Supply the result'
      )
    task_record = read_task(self.root, 'demo', task)['task']
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'description and requirement need text'
      ):
        connection.execute(
          'INSERT INTO blocker '
          '(stage_id, task_id, description, required, opened_at) '
          "VALUES (?, ?, 'Wait', '', 1)",
          (task_record['stage_id'], task),
        )
    finally:
      connection.close()

  def test_open_blocker_context_prevents_task_reassignment(self):
    self.create_project()
    first = add_stage(self.root, 'demo', 'first', 'First')
    second = add_stage(self.root, 'demo', 'second', 'Second')
    goal = create_goal(self.root, 'demo', 'Goal', [first, second])
    task = self.add_documented_task(stage=first, goal=goal)
    add_blocker(
      self.root,
      'demo',
      'Wait',
      required='Supply the result',
      task=task,
    )

    with self.assertRaisesRegex(ProjectError, 'open blocker context'):
      update_task(self.root, 'demo', task, stage_id=second)
    with self.assertRaisesRegex(ProjectError, 'open blocker context'):
      update_task(self.root, 'demo', task, goal_id=None)
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'open blocker context'
      ):
        connection.execute(
          'UPDATE task SET stage_id = ? WHERE id = ?', (second, task)
        )
    finally:
      connection.close()

  def test_schema_rejects_incoherent_or_targetless_blockers(self):
    self.create_project()
    first = add_stage(self.root, 'demo', 'first', 'First')
    second = add_stage(self.root, 'demo', 'second', 'Second')
    goal = create_goal(self.root, 'demo', 'Goal', [first, second])
    task = self.add_documented_task(stage=first, goal=goal)
    connection = self.connection()
    try:
      for values in (
        (goal, second, task),
        (None, second, None),
        (None, None, None),
      ):
        with self.assertRaisesRegex(
          sqlite3.IntegrityError, 'blocker relationships are incoherent'
        ):
          connection.execute(
            'INSERT INTO blocker '
            '(goal_id, stage_id, task_id, description, required, '
            'opened_at) '
            "VALUES (?, ?, ?, 'Invalid', 'Resolve it', 1)",
            values,
          )
        connection.rollback()
    finally:
      connection.close()

  def test_schema_rejects_incoherent_decision_and_evidence_context(self):
    self.create_project()
    first = add_stage(self.root, 'demo', 'first', 'First')
    second = add_stage(self.root, 'demo', 'second', 'Second')
    goal = create_goal(self.root, 'demo', 'Goal', [first, second])
    task = self.add_documented_task(stage=first, goal=goal)
    connection = self.connection()
    try:
      generation_start = connection.execute(
        'SELECT achievement_generation_started_at FROM stage WHERE id = ?',
        (second,),
      ).fetchone()[0]
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'decision relationships are incoherent'
      ):
        connection.execute(
          'INSERT INTO decision '
          '(goal_id, stage_id, task_id, summary, decided_at) '
          "VALUES (?, ?, ?, 'Invalid', 1)",
          (goal, second, task),
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'evidence relationships are incoherent'
      ):
        connection.execute(
          'INSERT INTO evidence '
          '(goal_id, stage_id, task_id, claim, captured_at, '
          'stage_generation) '
          "VALUES (?, ?, ?, 'Invalid', ?, 0)",
          (goal, second, task, generation_start),
        )
    finally:
      connection.close()

  def test_schema_requires_complete_immutable_record_context(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    connection = self.connection()
    try:
      for table, text_column in (
        ('decision', 'summary'),
        ('evidence', 'claim'),
      ):
        with self.assertRaisesRegex(
          sqlite3.IntegrityError, 'relationships are incoherent'
        ):
          connection.execute(
            f'INSERT INTO {table} '
            f'(task_id, {text_column}, '
            f'{"decided_at" if table == "decision" else "captured_at"}) '
            "VALUES (?, 'Record', 1)",
            (task,),
          )
        connection.rollback()
      decision = add_decision(self.root, 'demo', 'Decision', task=task)
      evidence = add_evidence(self.root, 'demo', 'Evidence', task=task)
      for table, record in (
        ('decision', decision),
        ('evidence', evidence),
      ):
        with self.assertRaisesRegex(
          sqlite3.IntegrityError, 'relationships are immutable'
        ):
          connection.execute(
            f'UPDATE {table} SET goal_id = NULL WHERE id = ?',
            (record,),
          )
        connection.rollback()
    finally:
      connection.close()

    cancel_goal(self.root, 'demo', goal, 'Use goal-less work')
    goal_less = self.add_documented_task('Goal-less', stage=stage)
    connection = self.connection()
    try:
      generation_start = connection.execute(
        'SELECT achievement_generation_started_at FROM stage WHERE id = ?',
        (stage,),
      ).fetchone()[0]
      connection.execute(
        'INSERT INTO decision '
        '(stage_id, task_id, summary, decided_at) '
        "VALUES (?, ?, 'Goal-less decision', 1)",
        (stage, goal_less),
      )
      connection.execute(
        'INSERT INTO evidence '
        '(stage_id, task_id, claim, captured_at, stage_generation) '
        "VALUES (?, ?, 'Goal-less evidence', ?, 0)",
        (stage, goal_less, generation_start),
      )
      connection.commit()
    finally:
      connection.close()

  def test_schema_requires_substantive_evidence_and_chronology(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'stage',
      'Stage',
      exit_evidence='Checks pass.',
    )
    task = self.add_documented_task(stage=stage)
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    with self.assertRaisesRegex(ProjectError, 'non-whitespace'):
      add_evidence(self.root, 'demo', '  ', stage=stage)
    connection = self.connection()
    try:
      generation_start = connection.execute(
        'SELECT achievement_generation_started_at FROM stage WHERE id = ?',
        (stage,),
      ).fetchone()[0]
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'evidence claim must contain text'
      ):
        connection.execute(
          'INSERT INTO evidence '
          '(stage_id, claim, captured_at, stage_generation) '
          "VALUES (?, '', ?, 0)",
          (stage, generation_start),
        )
      connection.rollback()
      evidence = connection.execute(
        'INSERT INTO evidence '
        '(stage_id, claim, captured_at, stage_generation) '
        "VALUES (?, 'Observed', ?, 0)",
        (stage, generation_start),
      ).lastrowid
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'predates its evidence'
      ):
        connection.execute(
          'INSERT INTO stage_achievement '
          '(stage_id, evidence_id, achieved_at) VALUES (?, ?, ?)',
          (stage, evidence, generation_start - 1),
        )
    finally:
      connection.close()

  def test_task_reassignment_preserves_historical_context(
    self,
  ):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    first_goal = create_goal(self.root, 'demo', 'First goal', [stage])
    task = self.add_documented_task(stage=stage, goal=first_goal)
    decision = add_decision(
      self.root, 'demo', 'Choose the approach', task=task
    )
    evidence = add_evidence(
      self.root, 'demo', 'Observe the result', task=task
    )

    cancel_goal(self.root, 'demo', first_goal, 'Focus changed')
    second_goal = create_goal(self.root, 'demo', 'Second goal', [stage])
    update_task(self.root, 'demo', task, goal_id=second_goal)

    decision_record = next(
      item
      for item in read_decisions(self.root, 'demo')
      if item['id'] == decision
    )
    evidence_record = next(
      item
      for item in read_evidence(self.root, 'demo')
      if item['id'] == evidence
    )
    self.assertEqual(decision_record['goal_id'], first_goal)
    self.assertEqual(decision_record['stage_id'], stage)
    self.assertEqual(evidence_record['goal_id'], first_goal)
    self.assertEqual(evidence_record['stage_id'], stage)
    self.assertEqual(
      read_task(self.root, 'demo', task)['task']['goal_id'], second_goal
    )
    connection = self.connection()
    try:
      for table, record in (
        ('decision', decision),
        ('evidence', evidence),
      ):
        with self.assertRaisesRegex(
          sqlite3.IntegrityError, 'relationships are immutable'
        ):
          connection.execute(
            f'UPDATE {table} SET goal_id = ? WHERE id = ?',
            (second_goal, record),
          )
        connection.rollback()
    finally:
      connection.close()

  def test_schema_preserves_lifecycle_records_and_append_only_logs(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)
    start_task(self.root, 'demo', task)
    connection = self.connection()
    try:
      for statement, parameters, message in (
        ('DELETE FROM task WHERE id = ?', (task,), 'task history'),
        ('DELETE FROM goal WHERE id = ?', (goal,), 'goal history'),
        ('DELETE FROM stage WHERE id = ?', (stage,), 'stage history'),
        (
          'UPDATE task_log SET message = ? WHERE task_id = ?',
          ('Changed', task),
          'append-only',
        ),
        ('DELETE FROM task_log WHERE task_id = ?', (task,), 'append-only'),
      ):
        with self.assertRaisesRegex(sqlite3.IntegrityError, message):
          connection.execute(statement, parameters)
        connection.rollback()
    finally:
      connection.close()

  def test_schema_preserves_a_started_task_contract(self):
    self.create_project()
    task = self.add_documented_task()
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE task SET started_at = NULL WHERE id = ?', (task,)
        )
      connection.rollback()
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE task SET completed_at = 0 WHERE id = ?', (task,)
        )
      connection.rollback()
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE task SET stage_id = NULL WHERE id = ?', (task,)
        )
    finally:
      connection.close()

  def test_schema_preserves_task_lifecycle_chronology(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)
    connection = self.connection()
    try:
      timestamp = connection.execute('SELECT unixepoch()').fetchone()[0]
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'not in the future'
      ):
        connection.execute(
          "UPDATE task SET status = 'active', started_at = ? WHERE id = ?",
          (timestamp + 100, task),
        )
      connection.rollback()
      connection.execute(
        "UPDATE task SET status = 'active', started_at = ? WHERE id = ?",
        (timestamp, task),
      )
      connection.commit()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'must follow activation'
      ):
        connection.execute(
          "UPDATE task SET status = 'completed', completed_at = ? "
          'WHERE id = ?',
          (timestamp - 1, task),
        )
      connection.rollback()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'not be in the future'
      ):
        connection.execute(
          "UPDATE task SET status = 'completed', completed_at = ? "
          'WHERE id = ?',
          (timestamp + 100, task),
        )
    finally:
      connection.close()

    pending = add_task(
      self.root,
      'demo',
      'Pending',
      **TASK_DOCUMENTATION,
    )
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'start time requires activation'
      ):
        connection.execute(
          'UPDATE task SET started_at = 1 WHERE id = ?', (pending,)
        )
    finally:
      connection.close()

  def test_schema_preserves_goal_and_graph_relationships(self):
    self.create_project()
    first = add_stage(self.root, 'demo', 'first', 'First')
    second = add_stage(self.root, 'demo', 'second', 'Second')
    third = add_stage(self.root, 'demo', 'third', 'Third')
    goal = create_goal(self.root, 'demo', 'Exact goal', [first])
    add_stage_dependency(self.root, 'demo', second, first)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE goal SET text = 'Changed' WHERE id = ?", (goal,)
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE goal_stage SET stage_id = ? WHERE goal_id = ?',
          (second, goal),
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE stage_dependency SET dependency_id = ? '
          'WHERE stage_id = ?',
          (third, second),
        )
      connection.rollback()
      construction = connection.execute(
        'INSERT INTO goal '
        '(text, status, created_at, started_at, updated_at) '
        "VALUES ('Construction', 'cancelled', 1, 0, 1)"
      ).lastrowid
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'start time requires activation'
      ):
        connection.execute(
          'UPDATE goal SET started_at = 1 WHERE id = ?', (construction,)
        )
    finally:
      connection.close()

  def test_schema_preserves_stage_achievement_history(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'stage',
      'Stage',
      exit_evidence='Checks pass.',
    )
    task, evidence = self.complete_stage(stage)
    connection = self.connection()
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'stage achievement is immutable'
      ):
        connection.execute(
          'UPDATE stage_achievement SET invalidated_at = 1'
        )
      connection.rollback()
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE evidence SET claim = 'Changed' WHERE id = ?",
          (evidence,),
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute('DELETE FROM stage_achievement')
    finally:
      connection.close()

  def test_stage_generation_records_and_enforces_its_start(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'stage',
      'Stage',
      exit_evidence='Checks pass.',
    )
    task, _ = self.complete_stage(stage)
    reopen_task(self.root, 'demo', task)
    start_task(self.root, 'demo', task)
    complete_task(self.root, 'demo', task)
    connection = self.connection()
    try:
      generation, generation_start = connection.execute(
        'SELECT achievement_generation, '
        'achievement_generation_started_at FROM stage WHERE id = ?',
        (stage,),
      ).fetchone()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'predates the current stage generation'
      ):
        connection.execute(
          'INSERT INTO evidence '
          '(stage_id, claim, captured_at, stage_generation) '
          "VALUES (?, 'Stale', ?, ?)",
          (stage, generation_start - 1, generation),
        )
      connection.rollback()
      evidence = connection.execute(
        'INSERT INTO evidence '
        '(stage_id, claim, captured_at, stage_generation) '
        "VALUES (?, 'Current', ?, ?)",
        (stage, generation_start, generation),
      ).lastrowid
      connection.commit()
      with self.assertRaisesRegex(
        sqlite3.IntegrityError, 'generation is controlled'
      ):
        connection.execute(
          'UPDATE stage SET achievement_generation_started_at = 0 '
          'WHERE id = ?',
          (stage,),
        )
    finally:
      connection.close()

    achieve_stage(self.root, 'demo', stage, evidence)
    self.assertEqual(
      read_stages(self.root, 'demo')[0]['status'], 'achieved'
    )

    reopen_task(self.root, 'demo', task)
    connection = self.connection()
    try:
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'UPDATE stage_achievement SET invalidated_at = NULL'
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          "UPDATE evidence SET claim = 'Changed' WHERE id = ?",
          (evidence,),
        )
      with self.assertRaises(sqlite3.IntegrityError):
        connection.execute(
          'INSERT INTO stage_achievement '
          '(stage_id, evidence_id, achieved_at, invalidated_at) '
          'VALUES (?, ?, 1, 1)',
          (stage, evidence),
        )
    finally:
      connection.close()


class ProjectCommandTest(ProjectTestCase):
  def invoke(self, *arguments):
    return CliRunner().invoke(
      project_group,
      ['--root', str(self.root), *arguments],
    )

  def test_cli_rejects_incomplete_execution_contracts(self):
    blank = self.invoke('create', 'blank', '--objective', '   ')
    self.assertEqual(blank.exit_code, 1)
    self.assertIn('Project objective', blank.output)

    created = self.invoke(
      'create', 'draft', '--objective', 'Draft objective'
    )
    self.assertEqual(created.exit_code, 0, created.output)
    stage = self.invoke(
      'stage', 'add', 'draft', 'work', '--outcome', 'Outcome'
    )
    self.assertEqual(stage.exit_code, 0, stage.output)
    task = self.invoke(
      'task',
      'add',
      'draft',
      '--title',
      'Work',
      '--purpose',
      TASK_DOCUMENTATION['purpose'],
      '--scope',
      TASK_DOCUMENTATION['scope'],
      '--exclusions',
      TASK_DOCUMENTATION['exclusions'],
      '--result',
      TASK_DOCUMENTATION['result'],
      '--completion-evidence',
      TASK_DOCUMENTATION['completion_evidence'],
      '--stage',
      'work',
    )
    self.assertEqual(task.exit_code, 0, task.output)
    started = self.invoke('task', 'start', 'draft', task.output.strip())
    self.assertEqual(started.exit_code, 1)
    self.assertIn('complete project charter', started.output)

    blank_stage = self.invoke(
      'stage', 'add', 'draft', 'other', '--outcome', '   '
    )
    self.assertEqual(blank_stage.exit_code, 1)
    self.assertIn('Stage outcome', blank_stage.output)

  def test_cli_runs_the_normalized_lifecycle(self):
    created = self.invoke(
      'create',
      'cli-demo',
      '--objective',
      'Exercise the CLI',
      '--scope',
      'Exercise this command path.',
      '--non-goals',
      'No work outside the fixture.',
      '--constraints',
      'Use the isolated project.',
      '--acceptance',
      'The complete lifecycle succeeds.',
    )
    self.assertEqual(created.exit_code, 0, created.output)
    stage = self.invoke(
      'stage',
      'add',
      'cli-demo',
      'build',
      '--outcome',
      'Build it',
      '--exit-evidence',
      'Checks pass',
    )
    self.assertEqual(stage.exit_code, 0, stage.output)
    task = self.invoke(
      'task',
      'add',
      'cli-demo',
      '--title',
      'Implement',
      '--purpose',
      TASK_DOCUMENTATION['purpose'],
      '--scope',
      TASK_DOCUMENTATION['scope'],
      '--exclusions',
      TASK_DOCUMENTATION['exclusions'],
      '--result',
      TASK_DOCUMENTATION['result'],
      '--completion-evidence',
      TASK_DOCUMENTATION['completion_evidence'],
      '--stage',
      'build',
    )
    self.assertEqual(task.exit_code, 0, task.output)
    task_id = task.output.strip()
    self.assertEqual(
      self.invoke('task', 'start', 'cli-demo', task_id).exit_code, 0
    )
    self.assertEqual(
      self.invoke('task', 'complete', 'cli-demo', task_id).exit_code, 0
    )
    evidence = self.invoke(
      'evidence',
      'add',
      'cli-demo',
      '--claim',
      'Checks pass',
      '--stage',
      'build',
      '--task',
      task_id,
    )
    self.assertEqual(evidence.exit_code, 0, evidence.output)
    achieved = self.invoke(
      'stage',
      'achieve',
      'cli-demo',
      'build',
      '--evidence',
      evidence.output.strip(),
    )
    self.assertEqual(achieved.exit_code, 0, achieved.output)
    status = self.invoke('status', 'cli-demo')
    self.assertEqual(status.exit_code, 0, status.output)
    self.assertIn('Status: complete', status.output)
    self.assertIn('Active stage: -', status.output)
    self.assertIn('Active task: -', status.output)

  def test_cli_exposes_pending_and_cancel_lifecycle(self):
    self.assertEqual(
      self.invoke(
        'create', 'cli-demo', '--objective', 'Exercise the CLI'
      ).exit_code,
      0,
    )
    task = self.invoke('task', 'add', 'cli-demo', '--title', 'Draft')
    task_id = task.output.strip()
    pending = self.invoke(
      'task', 'list', 'cli-demo', '--status', 'pending'
    )
    self.assertEqual(pending.exit_code, 0, pending.output)
    self.assertIn(f'{task_id}\tpending', pending.output)
    cancelled = self.invoke(
      'task', 'cancel', 'cli-demo', task_id, '--reason', 'Not needed'
    )
    self.assertEqual(cancelled.exit_code, 0, cancelled.output)

  def test_cli_requires_evidence_and_blocker_recovery_text(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)

    missing = self.invoke(
      'task', 'block', 'demo', str(task), '--description', 'Wait'
    )
    self.assertNotEqual(missing.exit_code, 0)
    self.assertIn("Missing option '--required'", missing.output)
    blank = self.invoke('evidence', 'add', 'demo', '--claim', '  ')
    self.assertNotEqual(blank.exit_code, 0)
    self.assertIn('non-whitespace', blank.output)

    block_task(
      self.root,
      'demo',
      task,
      'Dependency unavailable',
      impact='Cannot finish',
      attempts='Checked the service',
      required='Restore the service',
    )
    tasks = self.invoke('task', 'list', 'demo', '--status', 'blocked')
    self.assertEqual(tasks.exit_code, 0, tasks.output)
    self.assertIn(f'goal {goal}', tasks.output)
    blockers = self.invoke('blocker', 'list', 'demo')
    self.assertEqual(blockers.exit_code, 0, blockers.output)
    self.assertIn(f'stage {stage}', blockers.output)
    self.assertIn(f'goal {goal}', blockers.output)
    self.assertIn('impact: Cannot finish', blockers.output)
    self.assertIn('attempts: Checked the service', blockers.output)
    self.assertIn('required: Restore the service', blockers.output)

  def test_cli_can_remove_an_optional_goal_relationship(self):
    self.create_project('demo')
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    goal = create_goal(self.root, 'demo', 'Goal', [stage])
    task = self.add_documented_task(stage=stage, goal=goal)

    updated = self.invoke('task', 'update', 'demo', str(task), '--no-goal')
    self.assertEqual(updated.exit_code, 0, updated.output)
    self.assertIsNone(
      read_task(self.root, 'demo', task)['task']['goal_id']
    )
    conflicting = self.invoke(
      'task',
      'update',
      'demo',
      str(task),
      '--goal',
      str(goal),
      '--no-goal',
    )
    self.assertNotEqual(conflicting.exit_code, 0)
    self.assertIn('cannot be combined', conflicting.output)

  def test_cli_can_remove_a_stage_dependency(self):
    self.create_project()
    prerequisite = add_stage(
      self.root, 'demo', 'prerequisite', 'Establish the prerequisite'
    )
    dependent = add_stage(
      self.root, 'demo', 'dependent', 'Complete dependent work'
    )
    add_stage_dependency(self.root, 'demo', dependent, prerequisite)

    removed = self.invoke(
      'stage',
      'undepend',
      'demo',
      str(dependent),
      str(prerequisite),
    )
    self.assertEqual(removed.exit_code, 0, removed.output)
    stages = read_stages(self.root, 'demo')
    self.assertEqual(stages[1]['dependencies'], '')

    missing = self.invoke(
      'stage',
      'undepend',
      'demo',
      str(dependent),
      str(prerequisite),
    )
    self.assertNotEqual(missing.exit_code, 0)
    self.assertIn('does not depend', missing.output)

  def test_cli_removes_manual_and_legacy_lifecycle_commands(self):
    self.assertNotEqual(
      self.invoke('stage', 'start', 'missing', 'stage').exit_code, 0
    )
    self.assertNotEqual(
      self.invoke('goal', 'supersede', 'missing', '1').exit_code, 0
    )
    self.assertNotEqual(
      self.invoke('update', 'missing', '--status', 'complete').exit_code, 0
    )
    self.assertNotEqual(
      self.invoke(
        'task', 'update', 'missing', '1', '--status', 'active'
      ).exit_code,
      0,
    )

  def test_cli_goal_text_and_copy_are_exact(self):
    self.create_project('demo')
    stage = add_stage(self.root, 'demo', 'stage', 'Stage')
    goal = create_goal(self.root, 'demo', 'Exact\ntext', [stage])

    text = self.invoke('goal', 'text', 'demo', str(goal))
    self.assertEqual(text.exit_code, 0, text.output)
    self.assertEqual(text.output, 'Exact\ntext')
    copied = self.invoke('goal', 'copy', 'demo', str(goal))
    self.assertEqual(copied.exit_code, 0, copied.output)
    self.assertEqual(copied.output, copy_goal(self.root, 'demo', goal))

  def test_cli_json_reads_are_machine_usable(self):
    self.create_project()
    result = self.invoke('show', 'demo', '--json')
    self.assertEqual(result.exit_code, 0, result.output)
    self.assertEqual(json.loads(result.output)['project']['name'], 'demo')

  def test_cli_filters_decision_and_evidence_reads_by_task(self):
    self.create_project()
    first = self.add_documented_task('First')
    second = self.add_documented_task('Second')
    add_decision(self.root, 'demo', 'First decision', task=first)
    add_decision(self.root, 'demo', 'Second decision', task=second)
    add_evidence(self.root, 'demo', 'First evidence', task=first)
    add_evidence(self.root, 'demo', 'Second evidence', task=second)

    decisions = self.invoke(
      'decision', 'list', 'demo', '--task', str(first)
    )
    self.assertEqual(decisions.exit_code, 0, decisions.output)
    self.assertIn('First decision', decisions.output)
    self.assertNotIn('Second decision', decisions.output)
    evidence = self.invoke(
      'evidence', 'list', 'demo', '--task', str(first)
    )
    self.assertEqual(evidence.exit_code, 0, evidence.output)
    self.assertIn('First evidence', evidence.output)
    self.assertNotIn('Second evidence', evidence.output)


class ProjectSchemaTest(ProjectTestCase):
  def test_current_schema_rejects_same_named_object_substitutions(self):
    substitutions = (
      (
        'table',
        'task_tag',
        'DROP TABLE task_tag; '
        'CREATE TABLE task_tag (task_id INTEGER, tag TEXT)',
      ),
      (
        'index',
        'one_active_task_index',
        'DROP INDEX one_active_task_index; '
        'CREATE UNIQUE INDEX one_active_task_index ON task(id)',
      ),
      (
        'trigger',
        'project_name_update',
        'DROP TRIGGER project_name_update; '
        'CREATE TRIGGER project_name_update BEFORE UPDATE ON project '
        'BEGIN SELECT 1; END',
      ),
    )
    for number, (kind, name, script) in enumerate(substitutions):
      project_name = f'substitution-{number}'
      self.create_project(project_name)
      path = self.root / '.tmp' / f'{project_name}.sqlite3'
      connection = direct_database_connection(path)
      try:
        connection.executescript(script)
        connection.commit()
      finally:
        connection.close()
      plural = 'indexes' if kind == 'index' else f'{kind}s'
      with (
        self.subTest(kind=kind),
        self.assertRaisesRegex(
          ProjectError, f'incompatible {plural}: {name}'
        ),
      ):
        open_project(self.root, project_name)

  def test_current_schema_rejects_invalid_rows_after_contract_restoration(
    self,
  ):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    create_goal(self.root, 'demo', 'Complete the project', [stage])
    task = self.add_documented_task(stage=stage)
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'active_task_update'"
      ).fetchone()[0]
      timestamp = connection.execute('SELECT unixepoch()').fetchone()[0]
      connection.execute('DROP TRIGGER active_task_update')
      connection.execute(
        "UPDATE task SET status = 'active', started_at = ? WHERE id = ?",
        (timestamp, task),
      )
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'invalid active task'):
      read_handoff(self.root, 'demo')

  def test_current_schema_rejects_foreign_key_violations(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      self.assertEqual(
        connection.execute('PRAGMA foreign_keys').fetchone()[0], 0
      )
      connection.execute(
        'UPDATE task SET stage_id = 999 WHERE id = ?', (task,)
      )
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'foreign-key violation'):
      open_project(self.root, 'demo')

  def test_current_schema_rejects_table_constraint_corruption(self):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'task_status_transition'"
      ).fetchone()[0]
      connection.execute('DROP TRIGGER task_status_transition')
      connection.execute('PRAGMA ignore_check_constraints = ON')
      connection.execute(
        "UPDATE task SET status = 'unknown' WHERE id = ?", (task,)
      )
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'integrity check failed'):
      open_project(self.root, 'demo')

  def test_current_schema_rejects_invalid_terminal_authority(self):
    self.create_project()
    stage = add_stage(
      self.root,
      'demo',
      'work',
      'Complete the work',
      exit_evidence='Focused checks pass.',
    )
    goal = create_goal(self.root, 'demo', 'Complete the project', [stage])
    goal_evidence = add_evidence(
      self.root, 'demo', 'The goal is achieved.', goal=goal
    )
    achieve_goal(self.root, 'demo', goal)
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'achievement_evidence_delete'"
      ).fetchone()[0]
      connection.execute('DROP TRIGGER achievement_evidence_delete')
      connection.execute(
        'DELETE FROM evidence WHERE id = ?', (goal_evidence,)
      )
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'invalid goal lifecycle'):
      open_project(self.root, 'demo')

    second_name = 'stage-authority'
    self.create_project(second_name)
    stage = add_stage(
      self.root,
      second_name,
      'work',
      'Complete the work',
      exit_evidence='Focused checks pass.',
    )
    task = add_task(
      self.root,
      second_name,
      'Complete stage',
      stage=stage,
      **TASK_DOCUMENTATION,
    )
    start_task(self.root, second_name, task)
    complete_task(self.root, second_name, task)
    evidence = add_evidence(
      self.root,
      second_name,
      'The stage result is established.',
      stage=stage,
      task=task,
    )
    achieve_stage(self.root, second_name, stage, evidence)
    path = self.root / '.tmp' / f'{second_name}.sqlite3'
    connection = direct_database_connection(path)
    try:
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'stage_achievement_update'"
      ).fetchone()[0]
      connection.execute('DROP TRIGGER stage_achievement_update')
      connection.execute(
        'UPDATE stage_achievement SET achieved_at = 9999999999 '
        'WHERE stage_id = ? AND invalidated_at IS NULL',
        (stage,),
      )
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(
      ProjectError, 'invalid current stage achievement'
    ):
      open_project(self.root, second_name)

  def test_current_schema_rejects_incoherent_blocker_and_record_state(
    self,
  ):
    self.create_project()
    stage = add_stage(self.root, 'demo', 'work', 'Complete the work')
    task = self.add_documented_task(stage=stage)
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'apply_open_blocker'"
      ).fetchone()[0]
      connection.execute('DROP TRIGGER apply_open_blocker')
      connection.execute(
        'INSERT INTO blocker '
        '(task_id, stage_id, description, required, opened_at) '
        "VALUES (?, ?, 'Dependency unavailable', "
        "'Supply the dependency', unixepoch())",
        (task, stage),
      )
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'incoherent blocker'):
      open_project(self.root, 'demo')

    second_name = 'record-context'
    self.create_project(second_name)
    stage = add_stage(self.root, second_name, 'work', 'Complete the work')
    decision = add_decision(
      self.root, second_name, 'Keep the contract explicit', stage=stage
    )
    path = self.root / '.tmp' / f'{second_name}.sqlite3'
    connection = direct_database_connection(path)
    try:
      trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
        "AND name = 'decision_relationship_update'"
      ).fetchone()[0]
      connection.execute('DROP TRIGGER decision_relationship_update')
      connection.execute(
        "UPDATE decision SET context_status = 'legacy-unresolved', "
        'task_id = NULL WHERE id = ?',
        (decision,),
      )
      connection.execute(trigger_sql)
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'incoherent record context'):
      open_project(self.root, second_name)

  def test_current_schema_rejects_unexpected_lifecycle_triggers(self):
    for number, table in enumerate(
      ('task', 'goal', 'stage_achievement', 'blocker')
    ):
      name = f'unexpected-trigger-{number}'
      self.create_project(name)
      trigger = f'unexpected_{table}_guard'
      path = self.root / '.tmp' / f'{name}.sqlite3'
      connection = direct_database_connection(path)
      try:
        connection.execute(
          f'CREATE TRIGGER {trigger} BEFORE UPDATE ON {table} '
          'BEGIN SELECT 1; END'
        )
        connection.commit()
      finally:
        connection.close()
      with (
        self.subTest(table=table),
        self.assertRaisesRegex(
          ProjectError, f'unexpected triggers: {trigger}'
        ),
      ):
        open_project(self.root, name)

  def test_current_schema_rejects_persisted_goal_construction(self):
    self.create_project()
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      connection.execute(
        'INSERT INTO goal (text, status, started_at, created_at, '
        "updated_at) VALUES ('Unfinished', 'cancelled', 0, 1, 1)"
      )
      connection.commit()
    finally:
      connection.close()

    with self.assertRaisesRegex(ProjectError, 'invalid goal lifecycle'):
      open_project(self.root, 'demo')

  def test_current_schema_rejects_incomplete_post_execution_charter(self):
    for task_result in ('completed', 'cancelled'):
      for number, field in enumerate(
        (
          'objective',
          'scope',
          'non_goals',
          'constraints_text',
          'acceptance',
        )
      ):
        name = f'charter-{task_result}-{number}'
        with self.subTest(task_result=task_result, field=field):
          self.create_project(name)
          stage = add_stage(self.root, name, 'work', 'Complete the work')
          task = add_task(
            self.root,
            name,
            'Complete the work',
            stage=stage,
            **TASK_DOCUMENTATION,
          )
          start_task(self.root, name, task)
          if task_result == 'completed':
            complete_task(self.root, name, task)
          else:
            cancel_task(self.root, name, task)
          path = self.root / '.tmp' / f'{name}.sqlite3'
          connection = direct_database_connection(path)
          try:
            trigger_sql = connection.execute(
              "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
              "AND name = 'project_charter_update'"
            ).fetchone()[0]
            connection.execute('DROP TRIGGER project_charter_update')
            connection.execute(f'UPDATE project SET {field} = ?', ('',))
            connection.execute(trigger_sql)
            connection.commit()
          finally:
            connection.close()
          with self.assertRaisesRegex(
            ProjectError, 'incomplete post-execution charter'
          ):
            open_project(self.root, name)

  def test_current_schema_rejects_forged_legacy_charter_context(self):
    self.create_project()
    connection = open_project(self.root, 'demo')
    try:
      with self.assertRaisesRegex(
        sqlite3.IntegrityError,
        'invalid project charter context transition',
      ):
        connection.execute(
          "UPDATE project SET charter_context_status = 'legacy-incomplete'"
        )
    finally:
      connection.close()

  def test_current_schema_rejects_indexes_on_canonical_tables(self):
    for kind in ('INDEX', 'UNIQUE INDEX'):
      name = f'canonical-index-{kind.lower().replace(" ", "-")}'
      self.create_project(name)
      path = self.root / '.tmp' / f'{name}.sqlite3'
      connection = direct_database_connection(path)
      try:
        connection.execute(
          f'CREATE {kind} unexpected_task_status ON task(status)'
        )
        connection.commit()
      finally:
        connection.close()
      with (
        self.subTest(kind=kind),
        self.assertRaisesRegex(
          ProjectError, 'unexpected indexes on canonical tables'
        ),
      ):
        open_project(self.root, name)

  def test_current_schema_accepts_indexes_confined_to_additional_tables(
    self,
  ):
    self.create_project()
    path = self.root / '.tmp' / 'demo.sqlite3'
    connection = direct_database_connection(path)
    try:
      connection.execute(
        'CREATE TABLE local_cache (id INTEGER PRIMARY KEY, value TEXT)'
      )
      connection.execute(
        'CREATE UNIQUE INDEX local_cache_value ON local_cache(value)'
      )
      connection.commit()
    finally:
      connection.close()

    connection = open_project(self.root, 'demo')
    connection.close()

  def test_current_schema_only_rejects_other_versions_without_mutation(
    self,
  ):
    for version in (0, 5, 7):
      name = f'unsupported-version-{version}'
      self.create_project(name)
      path = self.root / '.tmp' / f'{name}.sqlite3'
      connection = direct_database_connection(path)
      try:
        connection.execute(f'PRAGMA user_version = {version}')
        connection.commit()
      finally:
        connection.close()
      before = path.read_bytes()

      with (
        self.subTest(version=version),
        self.assertRaisesRegex(
          ProjectError,
          f'Unsupported project schema version {version}; expected 6',
        ),
      ):
        open_project(self.root, name)

      self.assertEqual(path.read_bytes(), before)
