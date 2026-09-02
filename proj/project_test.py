import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

from proj.project import (
  ProjectError,
  achieve_goal,
  add_decision,
  add_evidence,
  add_stage,
  add_stage_dependency,
  add_task,
  append_task_log,
  archive_project,
  block_goal,
  block_task,
  complete_task,
  copy_goal,
  create_goal,
  create_project,
  format_handoff,
  goal_text,
  list_projects,
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
  reopen_goal,
  resolve_blocker,
  start_task,
  supersede_goal,
  update_project,
  update_stage,
  update_state,
  update_task,
)


class ProjectControlPlaneTest(unittest.TestCase):
  def setUp(self):
    self.directory = tempfile.TemporaryDirectory()
    self.root = Path(self.directory.name)

  def tearDown(self):
    self.directory.cleanup()

  def create_project(self, name='demo', objective='Reach the outcome'):
    return create_project(self.root, name, objective)

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
    with sqlite3.connect(archives[0]) as connection:
      self.assertEqual(
        connection.execute('SELECT objective FROM project').fetchone()[0],
        'First outcome',
      )

  def test_stage_dependency_controls_ready_tasks(self):
    self.create_project()
    first_stage = add_stage(
      self.root,
      'demo',
      'frame',
      'Frame the work',
      exit_evidence='Frame evidence',
    )
    second_stage = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='Build evidence',
    )
    add_stage_dependency(self.root, 'demo', second_stage, first_stage)
    first_task = add_task(
      self.root, 'demo', 'Frame task', stage=first_stage
    )
    second_task = add_task(
      self.root, 'demo', 'Build task', stage=second_stage
    )

    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [],
    )

    update_stage(self.root, 'demo', first_stage, status='active')
    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [first_task],
    )
    add_evidence(
      self.root,
      'demo',
      'The frame stage was validated',
      stage=first_stage,
    )
    update_stage(self.root, 'demo', first_stage, status='achieved')
    update_stage(self.root, 'demo', second_stage, status='active')
    self.assertEqual(
      [item['id'] for item in read_tasks(self.root, 'demo', ready=True)],
      [second_task],
    )
    self.assertEqual(len(read_stages(self.root, 'demo')), 2)

  def test_task_lifecycle_records_start_time_log_and_tags(self):
    self.create_project()
    task_id = add_task(
      self.root, 'demo', 'Implement plane', tags=('docs', 'control')
    )

    start_task(self.root, 'demo', task_id)
    append_task_log(
      self.root, 'demo', task_id, 'Inspected the current runner'
    )
    task = read_task(self.root, 'demo', task_id)
    self.assertEqual(task['task']['status'], 'active')
    self.assertIsNotNone(task['task']['started_at'])
    self.assertEqual(task['task']['tags'], 'control, docs')
    self.assertEqual(
      [entry['kind'] for entry in task['logs']],
      ['started', 'note'],
    )

    complete_task(self.root, 'demo', task_id)
    self.assertEqual(
      read_task(self.root, 'demo', task_id)['task']['status'], 'completed'
    )

  def test_task_update_status_records_timing_and_log(self):
    self.create_project()
    task_id = add_task(self.root, 'demo', 'Status update')

    update_task(self.root, 'demo', task_id, status='active')
    active = read_task(self.root, 'demo', task_id)
    self.assertIsNotNone(active['task']['started_at'])
    self.assertEqual(active['logs'][-1]['kind'], 'status')
    update_task(self.root, 'demo', task_id, status='completed')
    completed = read_task(self.root, 'demo', task_id)
    self.assertIsNotNone(completed['task']['completed_at'])
    self.assertEqual(completed['logs'][-1]['kind'], 'status')

  def test_task_start_requires_an_active_stage_and_makes_it_current(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First stage')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second stage')
    task_id = add_task(
      self.root, 'demo', 'Second-stage task', stage=second_stage
    )

    with self.assertRaisesRegex(ProjectError, 'stage .* is pending'):
      start_task(self.root, 'demo', task_id)
    with self.assertRaisesRegex(ProjectError, 'stage .* is pending'):
      update_task(self.root, 'demo', task_id, status='active')

    update_stage(self.root, 'demo', second_stage, status='active')
    update_stage(self.root, 'demo', first_stage, status='active')
    start_task(self.root, 'demo', task_id)

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['task']['id'], task_id)
    self.assertEqual(handoff['stage']['id'], second_stage)

  def test_stage_activation_requires_the_active_goal_relationship(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First stage')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second stage')
    update_stage(self.root, 'demo', first_stage, status='active')
    goal_id = create_goal(
      self.root, 'demo', 'Complete the first stage', (first_stage,)
    )

    with self.assertRaisesRegex(ProjectError, 'not linked to goal'):
      update_stage(self.root, 'demo', second_stage, status='active')

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['stage']['id'], first_stage)
    self.assertEqual(handoff['goal']['goal']['id'], goal_id)

  def test_stage_activation_preserves_the_current_task_stage(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First stage')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second stage')
    update_stage(self.root, 'demo', second_stage, status='active')
    update_stage(self.root, 'demo', first_stage, status='active')
    goal_id = create_goal(
      self.root,
      'demo',
      'Complete both stages',
      (first_stage, second_stage),
    )
    task_id = add_task(
      self.root,
      'demo',
      'First-stage task',
      stage=first_stage,
      goal=goal_id,
    )
    start_task(self.root, 'demo', task_id)

    with self.assertRaisesRegex(ProjectError, 'current task stage'):
      update_stage(self.root, 'demo', second_stage, status='active')

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['stage']['id'], first_stage)
    self.assertEqual(handoff['task']['id'], task_id)

  def test_stage_status_preserves_the_current_task_lifecycle(self):
    self.create_project()
    stage_id = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='The result is established',
    )
    update_stage(self.root, 'demo', stage_id, status='active')
    task_id = add_task(self.root, 'demo', 'Build task', stage=stage_id)
    start_task(self.root, 'demo', task_id)
    add_evidence(
      self.root,
      'demo',
      'The stage result is established',
      stage=stage_id,
      task=task_id,
    )

    invalid_statuses = {
      'pending': 'current task requires a live stage',
      'verifying': 'active current task requires an active stage',
      'blocked': 'active current task requires an active stage',
      'achieved': 'current task requires a live stage',
      'superseded': 'current task requires a live stage',
    }
    for status, error in invalid_statuses.items():
      with self.subTest(status=status):
        with self.assertRaisesRegex(ProjectError, error):
          update_stage(self.root, 'demo', stage_id, status=status)

    update_task(self.root, 'demo', task_id, status='verifying')
    update_stage(self.root, 'demo', stage_id, status='verifying')
    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['task']['status'], 'verifying')
    self.assertEqual(handoff['stage']['status'], 'verifying')

  def test_current_task_reassignment_requires_a_live_active_stage(self):
    self.create_project()
    active_stage = add_stage(self.root, 'demo', 'active', 'Active stage')
    pending_stage = add_stage(
      self.root, 'demo', 'pending', 'Pending stage'
    )
    terminal_stage = add_stage(
      self.root, 'demo', 'terminal', 'Terminal stage'
    )
    update_stage(self.root, 'demo', terminal_stage, status='active')
    update_stage(self.root, 'demo', terminal_stage, status='superseded')
    update_stage(self.root, 'demo', active_stage, status='active')
    task_id = add_task(
      self.root, 'demo', 'Active task', stage=active_stage
    )
    start_task(self.root, 'demo', task_id)

    for stage_id in (pending_stage, terminal_stage):
      with self.subTest(stage_id=stage_id):
        with self.assertRaisesRegex(
          ProjectError, 'current task requires a live stage'
        ):
          update_task(self.root, 'demo', task_id, stage_id=stage_id)

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['task']['stage_id'], active_stage)
    self.assertEqual(handoff['stage']['id'], active_stage)

  def test_task_start_requires_the_active_goal(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    update_stage(self.root, 'demo', stage_id, status='active')
    first_goal = create_goal(
      self.root, 'demo', 'Build the first result', (stage_id,)
    )
    old_task = add_task(
      self.root,
      'demo',
      'Old goal task',
      stage=stage_id,
      goal=first_goal,
    )
    supersede_goal(self.root, 'demo', first_goal)
    second_goal = create_goal(
      self.root, 'demo', 'Build the second result', (stage_id,)
    )
    current_task = add_task(
      self.root,
      'demo',
      'Current goal task',
      stage=stage_id,
      goal=second_goal,
    )
    goal_less_task = add_task(
      self.root, 'demo', 'Goal-less task', stage=stage_id
    )

    with self.assertRaisesRegex(
      ProjectError, 'does not match active goal'
    ):
      start_task(self.root, 'demo', old_task)
    with self.assertRaisesRegex(ProjectError, 'must link to active goal'):
      start_task(self.root, 'demo', goal_less_task)
    start_task(self.root, 'demo', current_task)

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['goal']['goal']['id'], second_goal)
    self.assertEqual(handoff['task']['id'], current_task)

  def test_task_activation_uses_updated_goal_and_stage_relationships(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    update_stage(self.root, 'demo', stage_id, status='active')
    goal_id = create_goal(
      self.root, 'demo', 'Build the result', (stage_id,)
    )
    task_id = add_task(self.root, 'demo', 'Unassigned task')

    update_task(
      self.root,
      'demo',
      task_id,
      stage_id=stage_id,
      goal_id=goal_id,
      status='active',
    )

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['state']['active_goal_id'], goal_id)
    self.assertEqual(handoff['state']['current_stage_id'], stage_id)
    self.assertEqual(handoff['state']['current_task_id'], task_id)

  def test_blocking_completed_task_clears_completion_time(self):
    self.create_project()
    task_id = add_task(self.root, 'demo', 'Regress completion state')
    complete_task(self.root, 'demo', task_id)

    block_task(
      self.root, 'demo', task_id, 'The completed result needs revision'
    )

    task = read_task(self.root, 'demo', task_id)['task']
    self.assertEqual(task['status'], 'blocked')
    self.assertIsNone(task['completed_at'])

  def test_task_log_reads_are_bounded(self):
    self.create_project()
    task_id = add_task(self.root, 'demo', 'Bounded log')
    append_task_log(self.root, 'demo', task_id, 'one')
    append_task_log(self.root, 'demo', task_id, 'two')
    append_task_log(self.root, 'demo', task_id, 'three')

    logs = read_task(self.root, 'demo', task_id, limit=2)['logs']
    self.assertEqual(
      [entry['message'] for entry in logs], ['two', 'three']
    )
    with self.assertRaises(ProjectError):
      read_task(self.root, 'demo', task_id, limit=0)
    with self.assertRaises(ProjectError):
      read_task(self.root, 'demo', task_id, limit=-1)

  def test_stage_dependencies_reject_cycles_and_unmet_start(self):
    self.create_project()
    first_stage = add_stage(
      self.root, 'demo', 'first', 'First', exit_evidence='First evidence'
    )
    second_stage = add_stage(
      self.root,
      'demo',
      'second',
      'Second',
      exit_evidence='Second evidence',
    )
    add_stage_dependency(self.root, 'demo', second_stage, first_stage)
    with self.assertRaises(ProjectError):
      update_stage(self.root, 'demo', second_stage, status='active')
    with self.assertRaises(ProjectError):
      add_stage_dependency(self.root, 'demo', first_stage, second_stage)

  def test_project_completion_requires_acceptance_and_evidence(self):
    create_project(
      self.root,
      'demo',
      'Complete the project',
      acceptance='Acceptance evidence is recorded',
    )
    with self.assertRaises(ProjectError):
      update_project(self.root, 'demo', status='complete')
    add_evidence(self.root, 'demo', 'The outcome was verified')
    update_project(self.root, 'demo', status='complete')
    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'complete'
    )

  def test_project_completion_uses_updated_acceptance(self):
    self.create_project()
    add_evidence(self.root, 'demo', 'The outcome was verified')

    update_project(
      self.root,
      'demo',
      acceptance='Acceptance is recorded',
      status='complete',
    )

    self.assertEqual(
      read_project(self.root, 'demo')['project']['status'], 'complete'
    )

  def test_blocked_tasks_cannot_start(self):
    self.create_project()
    task_id = add_task(self.root, 'demo', 'Blocked work')
    block_task(self.root, 'demo', task_id, 'A required input is missing')

    with self.assertRaises(ProjectError):
      start_task(self.root, 'demo', task_id)
    with self.assertRaises(ProjectError):
      update_task(self.root, 'demo', task_id, status='active')

  def test_handoff_current_task_requires_live_work(self):
    self.create_project()
    task_id = add_task(self.root, 'demo', 'Live handoff task')

    with self.assertRaises(ProjectError):
      update_state(self.root, 'demo', current_task=task_id)
    start_task(self.root, 'demo', task_id)
    update_state(self.root, 'demo', current_task=task_id)
    complete_task(self.root, 'demo', task_id)
    self.assertIsNone(
      read_handoff(self.root, 'demo')['state']['current_task_id']
    )
    with self.assertRaises(ProjectError):
      update_state(self.root, 'demo', current_task=task_id)

  def test_state_update_requires_the_current_task_stage(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First stage')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second stage')
    update_stage(self.root, 'demo', first_stage, status='active')
    update_stage(self.root, 'demo', second_stage, status='active')
    task_id = add_task(
      self.root, 'demo', 'Second-stage task', stage=second_stage
    )
    start_task(self.root, 'demo', task_id)

    with self.assertRaisesRegex(ProjectError, 'must match'):
      update_state(
        self.root,
        'demo',
        current_stage=first_stage,
        current_task=task_id,
      )
    with self.assertRaisesRegex(ProjectError, 'must match'):
      update_state(self.root, 'demo', current_stage=first_stage)

  def test_handoff_rejects_inconsistent_stale_relationships(self):
    path = self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First stage')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second stage')
    update_stage(self.root, 'demo', first_stage, status='active')
    update_stage(self.root, 'demo', second_stage, status='active')
    goal_id = create_goal(
      self.root,
      'demo',
      'Complete the second stage',
      (first_stage, second_stage),
    )
    task_id = add_task(
      self.root,
      'demo',
      'Second-stage task',
      stage=second_stage,
      goal=goal_id,
    )
    start_task(self.root, 'demo', task_id)

    with sqlite3.connect(path) as connection:
      connection.execute(
        'UPDATE project_state SET current_stage_id = ? WHERE id = 1',
        (first_stage,),
      )

    with self.assertRaisesRegex(ProjectError, 'stage does not match'):
      read_handoff(self.root, 'demo')

  def test_handoff_rejects_a_stale_terminal_current_stage(self):
    path = self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    update_stage(self.root, 'demo', stage_id, status='active')
    task_id = add_task(self.root, 'demo', 'Build task', stage=stage_id)
    start_task(self.root, 'demo', task_id)

    with sqlite3.connect(path) as connection:
      connection.execute(
        "UPDATE stage SET status = 'achieved' WHERE id = ?",
        (stage_id,),
      )

    with self.assertRaisesRegex(ProjectError, 'requires a live stage'):
      read_handoff(self.root, 'demo')

  def test_handoff_accepts_a_terminal_current_stage_without_a_task(self):
    self.create_project()
    stage_id = add_stage(
      self.root,
      'demo',
      'build',
      'Build the result',
      exit_evidence='The result is established',
    )
    update_stage(self.root, 'demo', stage_id, status='active')
    add_evidence(
      self.root, 'demo', 'The result is established', stage=stage_id
    )
    update_stage(self.root, 'demo', stage_id, status='achieved')

    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['stage']['status'], 'achieved')
    self.assertIsNone(handoff['task'])

  def test_handoff_rejects_a_stale_terminal_current_goal(self):
    path = self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    goal_id = create_goal(
      self.root, 'demo', 'Build the result', (stage_id,)
    )

    with sqlite3.connect(path) as connection:
      connection.execute(
        "UPDATE goal SET status = 'achieved' WHERE id = ?", (goal_id,)
      )

    with self.assertRaisesRegex(ProjectError, 'current goal is achieved'):
      read_handoff(self.root, 'demo')

  def test_decision_and_evidence_reads_reject_unbounded_limits(self):
    self.create_project()
    add_decision(self.root, 'demo', 'Record a decision')
    add_evidence(self.root, 'demo', 'Record evidence')

    with self.assertRaises(ProjectError):
      read_decisions(self.root, 'demo', limit=-1)
    with self.assertRaises(ProjectError):
      read_evidence(self.root, 'demo', limit=-1)

  def test_blocker_decision_evidence_and_handoff_are_queryable(self):
    self.create_project()
    stage_id = add_stage(
      self.root, 'demo', 'validate', 'Validate behaviour'
    )
    update_stage(self.root, 'demo', stage_id, status='active')
    task_id = add_task(self.root, 'demo', 'Run validation', stage=stage_id)
    blocker_id = block_task(
      self.root,
      'demo',
      task_id,
      'A required check is not available',
      required='Run the check when the tool is installed',
    )
    add_decision(
      self.root, 'demo', 'Use the project database as handoff state'
    )
    add_evidence(
      self.root,
      'demo',
      'The schema can be queried directly',
      source='project test',
    )
    update_state(
      self.root,
      'demo',
      summary='The control plane is under test',
      next_action='Resolve the validation blocker',
      current_stage=stage_id,
      current_task=task_id,
    )

    handoff = format_handoff(read_handoff(self.root, 'demo'))
    self.assertIn('The control plane is under test', handoff)
    self.assertIn('Resolve the validation blocker', handoff)
    self.assertIn('A required check is not available', handoff)
    self.assertIn('Use the project database as handoff state', handoff)
    self.assertIn('The schema can be queried directly', handoff)
    self.assertEqual(read_blockers(self.root, 'demo')[0]['id'], blocker_id)
    self.assertEqual(
      read_evidence(self.root, 'demo')[0]['claim'],
      'The schema can be queried directly',
    )

    resolve_blocker(
      self.root, 'demo', blocker_id, 'The check is now available'
    )
    self.assertEqual(read_blockers(self.root, 'demo'), [])
    task = read_task(self.root, 'demo', task_id)
    self.assertEqual(task['task']['status'], 'planned')
    self.assertEqual(task['logs'][-1]['kind'], 'unblocked')
    self.assertIsNone(
      read_handoff(self.root, 'demo')['state']['current_task_id']
    )

  def test_cli_update_rolls_back_project_fields_when_state_fails(self):
    self.create_project()
    task_id = add_task(self.root, 'demo', 'Planned handoff task')
    runner = CliRunner()

    result = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'update',
        'demo',
        '--acceptance',
        'Do not persist this failed update',
        '--current-task',
        str(task_id),
      ],
    )

    self.assertNotEqual(result.exit_code, 0)
    self.assertEqual(
      read_project(self.root, 'demo')['project']['acceptance'], ''
    )

    missing = runner.invoke(
      project_group,
      ['--root', str(self.root), 'update', 'missing'],
    )
    self.assertNotEqual(missing.exit_code, 0)

  def test_cli_creates_and_reads_a_project(self):
    runner = CliRunner()
    result = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'create',
        'cli-demo',
        '--objective',
        'Exercise the CLI',
        '--scope',
        'CLI-only behaviour',
      ],
    )
    self.assertEqual(result.exit_code, 0, result.output)
    status = runner.invoke(
      project_group,
      ['--root', str(self.root), 'status', 'cli-demo'],
    )
    self.assertEqual(status.exit_code, 0, status.output)
    self.assertIn('Exercise the CLI', status.output)
    show = runner.invoke(
      project_group,
      ['--root', str(self.root), 'show', 'cli-demo'],
    )
    self.assertEqual(show.exit_code, 0, show.output)
    self.assertIn('Scope: CLI-only behaviour', show.output)
    self.assertEqual(len(list_projects(self.root)), 1)

  def test_cli_runs_a_project_lifecycle(self):
    runner = CliRunner()

    def invoke(*arguments):
      result = runner.invoke(
        project_group,
        ['--root', str(self.root), *arguments],
      )
      self.assertEqual(result.exit_code, 0, result.output)
      return result

    invoke(
      'create',
      'lifecycle',
      '--objective',
      'Exercise every common write',
    )
    invoke(
      'stage',
      'add',
      'lifecycle',
      'build',
      '--outcome',
      'Build the result',
      '--exit-evidence',
      'The result is tested',
    )
    invoke('stage', 'start', 'lifecycle', 'build')
    invoke(
      'task',
      'add',
      'lifecycle',
      '--title',
      'Build task',
      '--stage',
      'build',
      '--tag',
      'cli',
    )
    invoke('task', 'update', 'lifecycle', '1', '--status', 'active')
    invoke('task', 'log', 'lifecycle', '1', 'A progress note')
    invoke('task', 'tag', 'lifecycle', '1', 'handoff')
    limited_logs = invoke(
      'task',
      'logs',
      'lifecycle',
      '1',
      '--limit',
      '1',
      '--since',
      '0',
      '--json',
    )
    self.assertEqual(len(json.loads(limited_logs.output)), 1)
    invoke(
      'blocker',
      'add',
      'lifecycle',
      '--description',
      'A temporary blocker',
      '--task',
      '1',
    )
    invoke(
      'blocker',
      'resolve',
      'lifecycle',
      '1',
      '--resolution',
      'Resolved in the lifecycle test',
    )
    invoke('task', 'start', 'lifecycle', '1')
    invoke(
      'evidence',
      'add',
      'lifecycle',
      '--claim',
      'The task was tested',
      '--source',
      'CLI lifecycle test',
      '--stage',
      'build',
      '--task',
      '1',
    )
    invoke('task', 'complete', 'lifecycle', '1')
    invoke('stage', 'achieve', 'lifecycle', 'build')
    invoke(
      'update',
      'lifecycle',
      '--acceptance',
      'The lifecycle evidence is present',
      '--status',
      'complete',
    )
    invoke(
      'decision',
      'add',
      'lifecycle',
      '--summary',
      'Keep the CLI explicit',
    )
    self.assertIn('Build task', invoke('task', 'list', 'lifecycle').output)
    self.assertIn(
      'A progress note', invoke('task', 'logs', 'lifecycle', '1').output
    )
    self.assertIn(
      'Keep the CLI explicit',
      invoke('decision', 'list', 'lifecycle').output,
    )
    self.assertIn(
      'The task was tested', invoke('evidence', 'list', 'lifecycle').output
    )
    self.assertIn(
      'Exercise every common write', invoke('handoff', 'lifecycle').output
    )
    archive = invoke('archive', 'lifecycle').output.strip()
    self.assertTrue(Path(archive).is_file())

  def test_explicit_archive_removes_project_from_active_list(self):
    self.create_project()
    archive_path = archive_project(self.root, 'demo')

    self.assertTrue(archive_path.is_file())
    self.assertEqual(list_projects(self.root), [])

  def test_goal_links_multiple_stages_and_related_records(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'frame', 'Frame the result')
    second_stage = add_stage(
      self.root, 'demo', 'verify', 'Verify the result'
    )
    text = (
      'Use the project control plane to verify the result across stages.'
    )

    goal_id = create_goal(
      self.root, 'demo', text, (first_stage, second_stage)
    )
    task_id = add_task(
      self.root,
      'demo',
      'Verify task',
      stage=second_stage,
      goal=goal_id,
    )
    evidence_id = add_evidence(
      self.root,
      'demo',
      'The goal result is observable',
      stage=second_stage,
      task=task_id,
      goal=goal_id,
    )

    record = read_goal(self.root, 'demo', goal_id)
    self.assertEqual(record['goal']['text'], text)
    self.assertEqual(
      [stage['id'] for stage in record['stages']],
      [first_stage, second_stage],
    )
    self.assertEqual(record['tasks'][0]['id'], task_id)
    self.assertEqual(record['evidence'][0]['id'], evidence_id)
    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['state']['active_goal_id'], goal_id)
    self.assertEqual(handoff['goal']['goal']['text'], text)
    self.assertEqual(goal_text(self.root, 'demo'), text)
    self.assertEqual(read_goals(self.root, 'demo')[0]['is_active'], 1)

  def test_goal_creation_rejects_invalid_text_stage_scope_and_concurrency(
    self,
  ):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')

    with self.assertRaisesRegex(ProjectError, 'non-whitespace'):
      create_goal(self.root, 'demo', '   ', (stage_id,))
    with self.assertRaisesRegex(ProjectError, 'received 4,001'):
      create_goal(self.root, 'demo', 'x' * 4001, (stage_id,))
    with self.assertRaisesRegex(ProjectError, 'at least one stage'):
      create_goal(self.root, 'demo', 'A valid goal', ())
    create_project(self.root, 'limit', 'Check the text boundary')
    limit_stage = add_stage(
      self.root, 'limit', 'boundary', 'Check the boundary'
    )
    exact_goal = create_goal(
      self.root, 'limit', 'x' * 4000, (limit_stage,)
    )
    self.assertEqual(len(goal_text(self.root, 'limit', exact_goal)), 4000)

    create_goal(self.root, 'demo', 'The first goal', (stage_id,))
    with self.assertRaisesRegex(
      ProjectError, 'already has an active goal'
    ):
      create_goal(self.root, 'demo', 'The second goal', (stage_id,))

  def test_goal_relationship_rejects_unlinked_stage(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First result')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second result')
    goal_id = create_goal(
      self.root, 'demo', 'Advance the first result', (first_stage,)
    )

    with self.assertRaisesRegex(ProjectError, 'not linked to goal'):
      add_task(
        self.root,
        'demo',
        'Wrong stage task',
        stage=second_stage,
        goal=goal_id,
      )
    with self.assertRaisesRegex(ProjectError, 'not linked to goal'):
      add_evidence(
        self.root,
        'demo',
        'Wrong stage evidence',
        stage=second_stage,
        goal=goal_id,
      )

  def test_goal_activation_and_completion_preserve_current_state(self):
    self.create_project()
    first_stage = add_stage(self.root, 'demo', 'first', 'First result')
    second_stage = add_stage(self.root, 'demo', 'second', 'Second result')
    update_stage(self.root, 'demo', first_stage, status='active')

    with self.assertRaisesRegex(ProjectError, 'not linked to goal'):
      create_goal(
        self.root,
        'demo',
        'Advance the second result',
        (second_stage,),
      )

    goal_id = create_goal(
      self.root, 'demo', 'Advance the first result', (first_stage,)
    )
    task_id = add_task(
      self.root,
      'demo',
      'Current goal task',
      stage=first_stage,
      goal=goal_id,
    )
    start_task(self.root, 'demo', task_id)
    add_evidence(
      self.root,
      'demo',
      'The goal result is established',
      stage=first_stage,
      task=task_id,
      goal=goal_id,
    )

    with self.assertRaisesRegex(ProjectError, 'current task to end'):
      achieve_goal(self.root, 'demo', goal_id)
    with self.assertRaisesRegex(ProjectError, 'current task to end'):
      supersede_goal(self.root, 'demo', goal_id)

    complete_task(self.root, 'demo', task_id)
    achieve_goal(self.root, 'demo', goal_id)
    self.assertIsNone(read_handoff(self.root, 'demo')['goal'])

  def test_new_goal_rejects_an_unrelated_current_task(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    update_stage(self.root, 'demo', stage_id, status='active')
    task_id = add_task(self.root, 'demo', 'Existing task', stage=stage_id)
    start_task(self.root, 'demo', task_id)

    with self.assertRaisesRegex(ProjectError, 'does not belong'):
      create_goal(self.root, 'demo', 'Build the result', (stage_id,))

    self.assertIsNone(read_handoff(self.root, 'demo')['goal'])
    self.assertEqual(
      read_handoff(self.root, 'demo')['task']['id'], task_id
    )

  def test_goal_completion_requires_evidence_and_clears_active_pointer(
    self,
  ):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'verify', 'Verify the result')
    goal_id = create_goal(
      self.root, 'demo', 'Verify the result', (stage_id,)
    )

    with self.assertRaisesRegex(ProjectError, 'goal-linked evidence'):
      achieve_goal(self.root, 'demo')
    add_evidence(
      self.root,
      'demo',
      'The result is verified',
      stage=stage_id,
      goal=goal_id,
    )
    achieve_goal(self.root, 'demo')

    self.assertEqual(
      read_goal(self.root, 'demo', goal_id)['goal']['status'], 'achieved'
    )
    self.assertIsNone(read_handoff(self.root, 'demo')['goal'])

  def test_goal_blocker_reactivates_goal_after_resolution(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    goal_id = create_goal(
      self.root, 'demo', 'Build the result', (stage_id,)
    )
    blocker_id = block_goal(
      self.root,
      'demo',
      goal_id,
      'Required external authority is unavailable',
      required='An authorized external decision',
    )

    self.assertEqual(
      read_goal(self.root, 'demo', goal_id)['goal']['status'], 'blocked'
    )
    resolve_blocker(
      self.root, 'demo', blocker_id, 'The authorized decision is recorded'
    )
    self.assertEqual(
      read_goal(self.root, 'demo', goal_id)['goal']['status'], 'active'
    )
    self.assertEqual(
      read_handoff(self.root, 'demo')['state']['active_goal_id'], goal_id
    )

  def test_blocked_goal_retains_current_work_for_recovery(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    update_stage(self.root, 'demo', stage_id, status='active')
    goal_id = create_goal(
      self.root, 'demo', 'Build the result', (stage_id,)
    )
    retained_task = add_task(
      self.root,
      'demo',
      'Retained live task',
      stage=stage_id,
      goal=goal_id,
    )
    start_task(self.root, 'demo', retained_task)
    block_goal(self.root, 'demo', goal_id, 'Exceptional boundary')

    update_state(self.root, 'demo', current_task=retained_task)
    handoff = read_handoff(self.root, 'demo')
    self.assertEqual(handoff['goal']['goal']['status'], 'blocked')
    self.assertEqual(handoff['task']['id'], retained_task)
    self.assertEqual(handoff['task']['status'], 'active')
    self.assertIn(
      f'Active goal: {goal_id} (blocked)', format_handoff(handoff)
    )

  def test_blocked_goal_rejects_new_current_work(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    update_stage(self.root, 'demo', stage_id, status='active')
    goal_id = create_goal(
      self.root, 'demo', 'Build the result', (stage_id,)
    )
    candidate_task = add_task(
      self.root,
      'demo',
      'Candidate task',
      stage=stage_id,
      goal=goal_id,
    )
    retained_task = add_task(
      self.root,
      'demo',
      'Retained task',
      stage=stage_id,
      goal=goal_id,
    )
    start_task(self.root, 'demo', candidate_task)
    start_task(self.root, 'demo', retained_task)
    block_goal(self.root, 'demo', goal_id, 'Exceptional boundary')

    with self.assertRaisesRegex(ProjectError, 'become current only'):
      update_state(self.root, 'demo', current_task=candidate_task)

    block_task(
      self.root, 'demo', candidate_task, 'The candidate is also blocked'
    )
    with self.assertRaisesRegex(ProjectError, 'become current only'):
      update_state(self.root, 'demo', current_task=candidate_task)

    self.assertEqual(
      read_handoff(self.root, 'demo')['task']['id'], retained_task
    )

  def test_goal_supersession_is_distinct_from_achievement(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    goal_id = create_goal(
      self.root, 'demo', 'Build the first result', (stage_id,)
    )

    supersede_goal(
      self.root, 'demo', goal_id, 'A clearer result replaced it'
    )

    self.assertEqual(
      read_goal(self.root, 'demo', goal_id)['goal']['status'], 'superseded'
    )
    self.assertIsNone(read_handoff(self.root, 'demo')['goal'])

  def test_cli_goal_text_and_copy_preserve_canonical_content(self):
    runner = CliRunner()
    create = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'create',
        'cli-goal',
        '--objective',
        'Exercise goal activation',
      ],
    )
    self.assertEqual(create.exit_code, 0, create.output)
    stage = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'stage',
        'add',
        'cli-goal',
        'verify',
        '--outcome',
        'Verify goal activation',
      ],
    )
    self.assertEqual(stage.exit_code, 0, stage.output)
    text = 'Use the exact goal text, including unicode: café.'
    set_goal = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'goal',
        'set',
        'cli-goal',
        '--text',
        text,
        '--stage',
        'verify',
      ],
    )
    self.assertEqual(set_goal.exit_code, 0, set_goal.output)
    raw = runner.invoke(
      project_group,
      ['--root', str(self.root), 'goal', 'text', 'cli-goal'],
    )
    self.assertEqual(raw.exit_code, 0, raw.output)
    self.assertEqual(raw.output, text)
    copied = runner.invoke(
      project_group,
      ['--root', str(self.root), 'goal', 'copy', 'cli-goal'],
    )
    self.assertEqual(copied.exit_code, 0, copied.output)
    self.assertEqual(copied.output, copy_goal(self.root, 'cli-goal'))
    overlong = runner.invoke(
      project_group,
      [
        '--root',
        str(self.root),
        'goal',
        'set',
        'cli-goal',
        '--text',
        'x' * 4001,
        '--stage',
        'verify',
      ],
    )
    self.assertNotEqual(overlong.exit_code, 0)
    self.assertIn('received 4,001', overlong.output)

  def test_goal_reopen_requires_resolved_blockers(self):
    self.create_project()
    stage_id = add_stage(self.root, 'demo', 'build', 'Build the result')
    goal_id = create_goal(
      self.root, 'demo', 'Build the result', (stage_id,)
    )
    blocker_id = block_goal(
      self.root, 'demo', goal_id, 'Exceptional boundary'
    )

    with self.assertRaisesRegex(ProjectError, 'open blockers'):
      reopen_goal(self.root, 'demo', goal_id)
    resolve_blocker(self.root, 'demo', blocker_id, 'Boundary resolved')
    self.assertEqual(
      read_goal(self.root, 'demo', goal_id)['goal']['status'], 'active'
    )


if __name__ == '__main__':
  unittest.main()
