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
    invoke('stage', 'achieve', 'lifecycle', 'build')
    invoke('task', 'complete', 'lifecycle', '1')
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
