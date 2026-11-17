"""Integration and unit tests for proj.service."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

import pytest

from proj import core, schema, service

_START_NOW = 1_700_000_000
_NAME = core.ProjectName.parse('demo')


@contextmanager
def _memory_db(
  snapshot: bytes | None = None, *, now: int = _START_NOW
) -> Iterator[tuple[sqlite3.Connection, list[int]]]:
  clock = [now]
  connection = sqlite3.connect(':memory:')
  try:
    schema.configure_connection(connection)
    connection.create_function(
      'unixepoch', 0, lambda: clock[0], deterministic=False
    )
    connection.create_function(
      'strftime',
      2,
      lambda fmt, val: str(clock[0])
      if (fmt, val) == ('%s', 'now')
      else '',
      deterministic=False,
    )
    if snapshot is not None:
      connection.deserialize(snapshot)
    yield connection, clock
  finally:
    connection.close()


@pytest.fixture(scope='module')
def base_snapshot() -> bytes:
  charter = core.CharterInput.parse(
    objective='Ship service layer',
    scope='In-memory SQLite service',
    non_goals='Filesystem CLI',
    constraints='No disk writes',
    acceptance='Suite passes',
  )
  with _memory_db() as (connection, _clock):
    schema.initialize_project(connection, _NAME, charter)
    return connection.serialize()


def _add_documented_task(
  connection: sqlite3.Connection,
  title: str,
  stage_ref: core.StageReference,
  *,
  goal: core.GoalReference | None = None,
  priority: int = 0,
  tags: tuple[str, ...] = (),
) -> int:
  return service.add_task(
    connection,
    core.SubstantiveText.parse(title, 'Task title'),
    purpose='Implement feature',
    stage=stage_ref,
    goal=goal,
    priority=priority,
    tags=tuple(core.TaskTag.parse(tag) for tag in tags),
    scope='Service module',
    exclusions='UI',
    result='Working contract',
    completion_evidence='Tests green',
  )


def test_pure_derivations_and_input_parsers() -> None:
  assert (
    service.derive_stage_status({'active': 1}, has_valid_achievement=True),
    service.derive_stage_status(
      {'pending': 1, 'blocked': 1}, has_valid_achievement=False
    ),
    service.derive_stage_status(
      {'blocked': 1}, has_valid_achievement=False
    ),
    service.derive_stage_status(
      {'completed': 2}, has_valid_achievement=True
    ),
    service.derive_stage_status(
      {'completed': 2}, has_valid_achievement=False
    ),
    service.derive_stage_status(
      {'cancelled': 2}, has_valid_achievement=False
    ),
    service.derive_stage_status({}, has_valid_achievement=False),
    service.derive_stage_status({}, has_valid_achievement=True),
    service.derive_stage_status(
      {
        'active': 0,
        'pending': 0,
        'blocked': 0,
        'completed': 0,
        'cancelled': 0,
      },
      has_valid_achievement=False,
    ),
    service.derive_stage_status(
      {
        'active': 0,
        'pending': 0,
        'blocked': 0,
        'completed': 0,
        'cancelled': 0,
      },
      has_valid_achievement=True,
    ),
    service.derive_project_status(('achieved', 'superseded')),
    service.derive_project_status(('achieved', 'pending')),
    service.derive_project_status(('blocked',)),
    service.derive_project_status(('superseded',)),
    service.title_status_for('Valid title'),
    service.title_status_for('   '),
  ) == (
    'active',
    'pending',
    'blocked',
    'achieved',
    'pending',
    'superseded',
    'pending',
    'pending',
    'pending',
    'pending',
    'complete',
    'active',
    'blocked',
    'active',
    'substantive',
    'legacy-blank',
  )

  stages_from_str = service.GoalStages.parse('build')
  stages_from_seq = service.GoalStages.parse(['build', 2])
  flt = service.RecordListFilter.parse(
    'Decision', limit=10, stage='build', task=3, goal='active'
  )
  patch = service.StagePatch.parse(
    name='Build', outcome='Shipped', purpose='p'
  )
  assert (stages_from_str, stages_from_seq, flt, patch) == (
    service.GoalStages((core.StageName('build'),)),
    service.GoalStages((core.StageName('build'), core.PositiveInt(2))),
    service.RecordListFilter(
      limit=core.PositiveInt(10),
      stage=core.StageName('build'),
      task=core.PositiveInt(3),
      goal='active',
      no_task=False,
    ),
    service.StagePatch(
      name=core.SubstantiveText('Build'),
      outcome=core.SubstantiveText('Shipped'),
      purpose='p',
    ),
  )

  errors: list[str] = []
  with pytest.raises(core.ProjectError) as empty_stages:
    service.GoalStages.parse([])
  errors.append(str(empty_stages.value))
  with pytest.raises(core.ProjectError) as dup_parsed_stages:
    service.GoalStages.parse(['build', 'build'])
  errors.append(str(dup_parsed_stages.value))
  with pytest.raises(core.ProjectError) as dup_direct_stages:
    service.GoalStages((core.PositiveInt(1), core.PositiveInt(1)))
  errors.append(str(dup_direct_stages.value))
  with pytest.raises(core.ProjectError) as focus_mismatch:
    service.HandoffFocus(kind='task', id=None)
  errors.append(str(focus_mismatch.value))
  with pytest.raises(core.ProjectError) as focus_missing_kind:
    service.HandoffFocus(kind=None, id=1)
  errors.append(str(focus_missing_kind.value))
  with pytest.raises(core.ProjectError) as focus_non_positive:
    service.HandoffFocus(kind='task', id=0)
  errors.append(str(focus_non_positive.value))
  with pytest.raises(core.ProjectError) as focus_bool:
    service.HandoffFocus(kind='task', id=True)
  errors.append(str(focus_bool.value))
  with pytest.raises(core.ProjectError) as task_patch_bool:
    service.TaskPatch(priority=True)
  errors.append(str(task_patch_bool.value))
  with pytest.raises(core.ProjectError) as bad_limit:
    service.RecordListFilter.parse('Evidence', limit=0)
  errors.append(str(bad_limit.value))
  with pytest.raises(core.ProjectError) as direct_conflict:
    service.RecordListFilter(
      limit=core.PositiveInt(10), task=core.PositiveInt(1), no_task=True
    )
  errors.append(str(direct_conflict.value))
  with pytest.raises(core.ProjectError) as conflict:
    service.RecordListFilter.parse('Decision', task=1, no_task=True)
  errors.append(str(conflict.value))
  with pytest.raises(core.ProjectError) as bad_stage_name:
    service.StagePatch.parse(name='   ')
  errors.append(str(bad_stage_name.value))

  assert errors == [
    'A goal must link to at least one stage',
    'A goal cannot link the same stage more than once',
    'A goal cannot link the same stage more than once',
    'Handoff focus kind and ID must both be set or both be null',
    'Handoff focus kind and ID must both be set or both be null',
    'Handoff focus ID must be positive',
    'Handoff focus ID must be positive',
    'Task priority must be an integer',
    'Evidence limits must be positive',
    'Record task and no-task filters conflict',
    'Decision task and no-task filters conflict',
    'Stage name must contain non-whitespace text',
  ]


def test_charter_recharter_and_stage_achievement_invalidation(
  base_snapshot: bytes,
) -> None:
  with _memory_db(base_snapshot) as (conn, clock):
    clock[0] = _START_NOW + 1
    service.update_project_and_state(
      conn,
      service.ProjectPatch(scope='Updated pre-work scope'),
      service.ProjectStatePatch(
        summary='Initial', next_action='Add stage'
      ),
    )
    stage_id = service.add_stage(
      conn,
      core.SubstantiveText('Build'),
      core.SubstantiveText('Build passes'),
      exit_evidence='Green suite',
    )
    task_id = _add_documented_task(
      conn, 'Implement', core.PositiveInt(stage_id)
    )
    clock[0] = _START_NOW + 2
    service.start_task(conn, core.PositiveInt(task_id))

    with pytest.raises(core.ProjectError) as stable_err:
      service.update_project_and_state(
        conn,
        service.ProjectPatch(objective='Changed mid-task'),
        service.ProjectStatePatch(),
      )
    assert str(stable_err.value) == (
      'Could not update project: active task or active/pending/blocked '
      'goal requires a stable project charter; end the task and cancel '
      'active, pending, or blocked goals before re-chartering'
    )

    clock[0] = _START_NOW + 3
    service.complete_task(conn, core.PositiveInt(task_id))
    ev1 = service.add_evidence(
      conn,
      core.SubstantiveText('Build suite green'),
      stage=core.PositiveInt(stage_id),
    )
    ev_unused = service.add_evidence(
      conn,
      core.SubstantiveText('Unused gen-0 proof'),
      stage=core.PositiveInt(stage_id),
    )
    service.achieve_stage(
      conn, core.PositiveInt(stage_id), core.PositiveInt(ev1)
    )

    completed_summary = service.read_project_summary(conn, 'memory://demo')
    assert completed_summary == service.ProjectSummary(
      name='demo',
      status='complete',
      objective='Ship service layer',
      updated_at=_START_NOW + 3,
      path='memory://demo',
    )

    clock[0] = _START_NOW + 4
    service.update_project_and_state(
      conn,
      service.ProjectPatch(objective='Ship service v2'),
      service.ProjectStatePatch(next_action='Re-verify'),
    )

    view = service.read_project(conn, 'memory://demo')
    stages = service.read_stages(conn)
    assert view == service.ProjectView(
      path='memory://demo',
      project=service.ProjectRecord(
        id=1,
        name='demo',
        objective='Ship service v2',
        scope='Updated pre-work scope',
        non_goals='Filesystem CLI',
        constraints_text='No disk writes',
        acceptance='Suite passes',
        created_at=_START_NOW,
        updated_at=_START_NOW + 4,
        charter_context_status='current',
        status='active',
        completed_at=None,
      ),
      state=service.ProjectState(
        id=1,
        summary='Initial',
        next_action='Re-verify',
        updated_at=_START_NOW + 4,
        revision=9,
      ),
      goal=None,
      charter_history=(
        service.CharterHistoryRecord(
          id=1,
          objective='Ship service layer',
          scope='Updated pre-work scope',
          non_goals='Filesystem CLI',
          constraints_text='No disk writes',
          acceptance='Suite passes',
          replaced_at=_START_NOW + 4,
        ),
      ),
    )
    assert stages == (
      service.StageListItem(
        id=stage_id,
        name='Build',
        outcome='Build passes',
        purpose='',
        entry_conditions='',
        exit_evidence='Green suite',
        position=0,
        achievement_generation=1,
        achievement_generation_started_at=_START_NOW + 4,
        created_at=_START_NOW + 1,
        updated_at=_START_NOW + 3,
        status='pending',
        started_at=_START_NOW + 2,
        achieved_at=None,
        achievement_evidence_id=None,
        dependencies='',
      ),
    )

    with pytest.raises(core.ProjectError) as reused_ev_err:
      service.achieve_stage(
        conn, core.PositiveInt(stage_id), core.PositiveInt(ev1)
      )
    with pytest.raises(core.ProjectError) as stale_ev_err:
      service.achieve_stage(
        conn, core.PositiveInt(stage_id), core.PositiveInt(ev_unused)
      )
    assert (str(reused_ev_err.value), str(stale_ev_err.value)) == (
      'Could not achieve stage: '
      'achievement evidence was already used for this stage',
      'Could not achieve stage: '
      'achievement evidence predates the current stage generation',
    )

    encoded = json.loads(json.dumps(view.to_dict()))
    assert encoded == {
      'path': 'memory://demo',
      'project': {
        'id': 1,
        'name': 'demo',
        'objective': 'Ship service v2',
        'scope': 'Updated pre-work scope',
        'non_goals': 'Filesystem CLI',
        'constraints_text': 'No disk writes',
        'acceptance': 'Suite passes',
        'created_at': _START_NOW,
        'updated_at': _START_NOW + 4,
        'charter_context_status': 'current',
        'status': 'active',
        'completed_at': None,
      },
      'state': {
        'id': 1,
        'summary': 'Initial',
        'next_action': 'Re-verify',
        'updated_at': _START_NOW + 4,
        'revision': 9,
      },
      'goal': None,
      'charter_history': [
        {
          'id': 1,
          'objective': 'Ship service layer',
          'scope': 'Updated pre-work scope',
          'non_goals': 'Filesystem CLI',
          'constraints_text': 'No disk writes',
          'acceptance': 'Suite passes',
          'replaced_at': _START_NOW + 4,
        }
      ],
    }


def test_stage_dependencies_and_active_dependent_guards(
  base_snapshot: bytes,
) -> None:
  with _memory_db(base_snapshot) as (conn, clock):
    s1 = service.add_stage(
      conn,
      core.SubstantiveText('Stage1'),
      core.SubstantiveText('First done'),
      exit_evidence='Evidence 1',
    )
    s2 = service.add_stage(
      conn,
      core.SubstantiveText('Stage2'),
      core.SubstantiveText('Second done'),
      exit_evidence='Evidence 2',
    )
    service.add_stage_dependency(
      conn, core.StageName('Stage2'), core.StageName('Stage1')
    )

    with pytest.raises(core.ProjectError) as cycle_err:
      service.add_stage_dependency(
        conn, core.PositiveInt(s1), core.PositiveInt(s2)
      )
    assert str(cycle_err.value) == 'Stage dependency would create a cycle'

    t1 = _add_documented_task(conn, 'Task 1', core.PositiveInt(s1))
    t2 = _add_documented_task(conn, 'Task 2', core.PositiveInt(s2))
    assert service.read_tasks(conn, ready=True) == (
      service.TaskRecord(
        id=t1,
        goal_id=None,
        stage_id=s1,
        title='Task 1',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='pending',
        priority=0,
        created_at=_START_NOW,
        started_at=None,
        completed_at=None,
        updated_at=_START_NOW,
        stage_name='Stage1',
        tags='',
        title_status='substantive',
      ),
    )
    with pytest.raises(core.ProjectError) as blocked_dep:
      service.start_task(conn, core.PositiveInt(t2))
    assert str(blocked_dep.value) == (
      'Stage dependency is not achieved: Stage1'
    )

    clock[0] = _START_NOW + 1
    service.start_task(conn, core.PositiveInt(t1))
    service.complete_task(conn, core.PositiveInt(t1))
    ev1 = service.add_evidence(
      conn,
      core.SubstantiveText('Stage 1 verified'),
      stage=core.PositiveInt(s1),
    )
    service.achieve_stage(
      conn, core.PositiveInt(s1), core.PositiveInt(ev1)
    )

    service.start_task(conn, core.PositiveInt(t2))
    with pytest.raises(core.ProjectError) as remove_dep_err:
      service.remove_stage_dependency(
        conn, core.PositiveInt(s2), core.PositiveInt(s1)
      )
    assert str(remove_dep_err.value) == (
      'Could not remove stage dependency: '
      'active task requires its stage dependencies'
    )

    with pytest.raises(core.ProjectError) as invalidate_err:
      service.update_stage(
        conn,
        core.PositiveInt(s1),
        service.StagePatch(exit_evidence='Changed'),
      )
    assert str(invalidate_err.value) == (
      'Could not update stage: '
      'an active task depends on the stage achievement'
    )

    service.complete_task(conn, core.PositiveInt(t2))
    service.remove_stage_dependency(
      conn, core.PositiveInt(s2), core.PositiveInt(s1)
    )
    assert service.read_stages(conn) == (
      service.StageListItem(
        id=s1,
        name='Stage1',
        outcome='First done',
        purpose='',
        entry_conditions='',
        exit_evidence='Evidence 1',
        position=0,
        achievement_generation=0,
        achievement_generation_started_at=_START_NOW,
        created_at=_START_NOW,
        updated_at=_START_NOW + 1,
        status='achieved',
        started_at=_START_NOW + 1,
        achieved_at=_START_NOW + 1,
        achievement_evidence_id=ev1,
        dependencies='',
      ),
      service.StageListItem(
        id=s2,
        name='Stage2',
        outcome='Second done',
        purpose='',
        entry_conditions='',
        exit_evidence='Evidence 2',
        position=1,
        achievement_generation=0,
        achievement_generation_started_at=_START_NOW,
        created_at=_START_NOW,
        updated_at=_START_NOW,
        status='pending',
        started_at=_START_NOW + 1,
        achieved_at=None,
        achievement_evidence_id=None,
        dependencies='',
      ),
    )


def test_task_lifecycle_handoff_tags_logs_and_error_adaptation(
  base_snapshot: bytes,
) -> None:
  with _memory_db(base_snapshot) as (conn, clock):
    s1 = service.add_stage(
      conn, core.SubstantiveText('S1'), core.SubstantiveText('O1')
    )
    t1 = _add_documented_task(
      conn, 'First', core.PositiveInt(s1), priority=1, tags=('cli', 'core')
    )
    t2 = _add_documented_task(
      conn, 'Second', core.PositiveInt(s1), priority=2
    )

    clock[0] = _START_NOW + 1
    service.start_task(conn, core.PositiveInt(t1))
    clock[0] = _START_NOW + 2
    service.start_task(conn, core.PositiveInt(t2))
    service.append_task_log(
      conn, core.PositiveInt(t1), 'Note at t2', kind='note'
    )

    t1_details = service.read_task(
      conn,
      core.PositiveInt(t1),
      limit=core.PositiveInt(5),
      since=_START_NOW + 2,
    )
    assert t1_details == service.TaskDetails(
      task=service.TaskRecord(
        id=t1,
        goal_id=None,
        stage_id=s1,
        title='First',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='pending',
        priority=1,
        created_at=_START_NOW,
        started_at=_START_NOW + 1,
        completed_at=None,
        updated_at=_START_NOW + 2,
        stage_name='S1',
        tags='cli, core',
        title_status='substantive',
      ),
      logs=(
        service.TaskLogRecord(
          id=2,
          task_id=t1,
          occurred_at=_START_NOW + 2,
          kind='handoff',
          message=f'Task returned to pending while activating task {t2}',
        ),
        service.TaskLogRecord(
          id=4,
          task_id=t1,
          occurred_at=_START_NOW + 2,
          kind='note',
          message='Note at t2',
        ),
      ),
    )

    service.remove_task_tags(
      conn, core.PositiveInt(t1), (core.TaskTag.parse('cli'),)
    )
    service.add_task_tags(
      conn, core.PositiveInt(t1), (core.TaskTag.parse('sqlite'),)
    )
    with pytest.raises(core.ProjectError) as since_logs_err:
      service.read_task_logs(conn, core.PositiveInt(t1), since=True)
    with pytest.raises(core.ProjectError) as since_task_err:
      service.read_task(conn, core.PositiveInt(t1), since=False)
    assert (str(since_logs_err.value), str(since_task_err.value)) == (
      'Log timestamp filter must be an integer',
      'Log timestamp filter must be an integer',
    )
    tagged = service.read_tasks(conn, tag='sqlite')
    assert (
      tagged,
      service.read_tasks(conn, tag=''),
      service.read_tasks(conn, tag='   '),
      service.read_tasks(conn, tag=' sqlite '),
    ) == (
      (
        service.TaskRecord(
          id=t1,
          goal_id=None,
          stage_id=s1,
          title='First',
          purpose='Implement feature',
          scope='Service module',
          exclusions='UI',
          result='Working contract',
          completion_evidence='Tests green',
          status='pending',
          priority=1,
          created_at=_START_NOW,
          started_at=_START_NOW + 1,
          completed_at=None,
          updated_at=_START_NOW + 2,
          stage_name='S1',
          tags='core, sqlite',
          title_status='substantive',
        ),
      ),
      (),
      (),
      tagged,
    )

    blocker_id = service.block_task(
      conn,
      core.PositiveInt(t2),
      core.SubstantiveText('Missing fixture'),
      required=core.SubstantiveText('Create fixture'),
    )
    assert service.read_tasks(conn, status='blocked') == (
      service.TaskRecord(
        id=t2,
        goal_id=None,
        stage_id=s1,
        title='Second',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='blocked',
        priority=2,
        created_at=_START_NOW,
        started_at=_START_NOW + 2,
        completed_at=None,
        updated_at=_START_NOW + 2,
        stage_name='S1',
        tags='',
        title_status='substantive',
      ),
    )
    service.cancel_task(conn, core.PositiveInt(t2), reason='Superseded')
    assert service.read_blockers(conn, status='withdrawn') == (
      service.BlockerRecord(
        id=blocker_id,
        goal_id=None,
        stage_id=s1,
        task_id=t2,
        description='Missing fixture',
        impact='',
        attempts='',
        required='Create fixture',
        status='withdrawn',
        opened_at=_START_NOW + 2,
        resolved_at=_START_NOW + 2,
        resolution='Superseded',
        target_kind='task',
        target_id=t2,
      ),
    )

    service.reopen_task(conn, core.PositiveInt(t2))
    assert service.read_task(
      conn, core.PositiveInt(t2)
    ) == service.TaskDetails(
      task=service.TaskRecord(
        id=t2,
        goal_id=None,
        stage_id=s1,
        title='Second',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='pending',
        priority=2,
        created_at=_START_NOW,
        started_at=_START_NOW + 2,
        completed_at=None,
        updated_at=_START_NOW + 2,
        stage_name='S1',
        tags='',
        title_status='substantive',
      ),
      logs=(
        service.TaskLogRecord(
          id=3,
          task_id=t2,
          occurred_at=_START_NOW + 2,
          kind='started',
          message='Task started',
        ),
        service.TaskLogRecord(
          id=5,
          task_id=t2,
          occurred_at=_START_NOW + 2,
          kind='blocked',
          message='Missing fixture',
        ),
        service.TaskLogRecord(
          id=6,
          task_id=t2,
          occurred_at=_START_NOW + 2,
          kind='cancelled',
          message='Superseded',
        ),
        service.TaskLogRecord(
          id=7,
          task_id=t2,
          occurred_at=_START_NOW + 2,
          kind='reopened',
          message='Task reopened',
        ),
      ),
    )

    with pytest.raises(core.ProjectError) as reopen_pending_err:
      service.reopen_task(conn, core.PositiveInt(t2))
    assert str(reopen_pending_err.value) == (
      f'Only completed or cancelled tasks can reopen; task {t2} is pending'
    )

    with pytest.raises(core.ProjectError) as bad_prio_err:
      service.add_task(
        conn, core.SubstantiveText('Bad prio'), priority=True
      )
    assert str(bad_prio_err.value) == 'Task priority must be an integer'

    with pytest.raises(core.ProjectError) as bad_update_err:
      service.update_task(
        conn, core.PositiveInt(t2), service.TaskPatch.parse(title='   ')
      )
    assert str(bad_update_err.value) == (
      'Task title must contain non-whitespace text'
    )

    service.cancel_task(conn, core.PositiveInt(t2), reason='Cancel again')
    blocker_trig = conn.execute(
      'SELECT sql FROM sqlite_master '
      "WHERE type = 'trigger' AND name = 'open_blocker_target'"
    ).fetchone()['sql']
    conn.execute('DROP TRIGGER open_blocker_target')
    conn.execute(
      'INSERT INTO blocker '
      '(task_id, description, required, opened_at) '
      "VALUES (?, 'dangling', 'fix', ?)",
      (t2, _START_NOW + 3),
    )
    conn.execute(blocker_trig)
    with pytest.raises(core.ProjectError) as trigger_reopen_err:
      service.reopen_task(conn, core.PositiveInt(t2))
    assert str(trigger_reopen_err.value) == (
      'Project database error: pending task has an open blocker'
    )

  with pytest.raises(core.ProjectError) as closed_err:
    service.read_stages(conn)
  assert str(closed_err.value) == (
    'Project database error: Cannot operate on a closed database.'
  )


def test_goal_lifecycle_displacement_blockers_and_repair(
  base_snapshot: bytes,
) -> None:
  with _memory_db(base_snapshot) as (conn, clock):
    s1 = service.add_stage(
      conn, core.SubstantiveText('Work'), core.SubstantiveText('Done')
    )
    clock[0] = _START_NOW + 1
    g1 = service.create_goal(
      conn, core.GoalText('First goal'), service.GoalStages.parse([s1])
    )
    t1 = _add_documented_task(
      conn, 'G1 task', core.PositiveInt(s1), goal=core.PositiveInt(g1)
    )
    service.start_task(conn, core.PositiveInt(t1))

    clock[0] = _START_NOW + 2
    g2 = service.create_goal(
      conn, core.GoalText('Second goal'), service.GoalStages.parse('Work')
    )
    goals = service.read_goals(conn)
    assert goals == (
      service.GoalListItem(
        id=g2,
        text='Second goal',
        status='active',
        status_reason='',
        ever_activated=1,
        created_at=_START_NOW + 2,
        started_at=_START_NOW + 2,
        achieved_at=None,
        updated_at=_START_NOW + 2,
        is_active=1,
        stage_names='Work',
      ),
      service.GoalListItem(
        id=g1,
        text='First goal',
        status='pending',
        status_reason='Deferred while activating goal 2',
        ever_activated=1,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        achieved_at=None,
        updated_at=_START_NOW + 2,
        is_active=0,
        stage_names='Work',
      ),
    )
    assert service.goal_text(conn) == 'Second goal'

    service.activate_goal(conn, core.PositiveInt(g1))
    assert service.goal_text(conn, 'active') == 'First goal'
    assert service.read_task(
      conn, core.PositiveInt(t1)
    ) == service.TaskDetails(
      task=service.TaskRecord(
        id=t1,
        goal_id=g1,
        stage_id=s1,
        title='G1 task',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='pending',
        priority=0,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        completed_at=None,
        updated_at=_START_NOW + 2,
        stage_name='Work',
        tags='',
        title_status='substantive',
      ),
      logs=(
        service.TaskLogRecord(
          id=1,
          task_id=t1,
          occurred_at=_START_NOW + 1,
          kind='started',
          message='Task started',
        ),
        service.TaskLogRecord(
          id=2,
          task_id=t1,
          occurred_at=_START_NOW + 2,
          kind='handoff',
          message=f'Task returned to pending while activating goal {g2}',
        ),
      ),
    )

    clock[0] = _START_NOW + 3
    service.start_task(conn, core.PositiveInt(t1))
    service.complete_task(conn, core.PositiveInt(t1))
    b1 = service.block_goal(
      conn,
      core.PositiveInt(g1),
      core.SubstantiveText('Need approval'),
      required=core.SubstantiveText('Sign-off'),
    )
    b2 = service.add_blocker(
      conn,
      core.SubstantiveText('Need hardware'),
      required=core.SubstantiveText('Allocate box'),
      goal=core.PositiveInt(g1),
    )
    g1_stage_summary = (
      service.GoalStageSummary(
        id=s1, name='Work', status='pending', outcome='Done'
      ),
    )
    g1_task_summary = (
      service.GoalTaskRecord(
        id=t1,
        goal_id=g1,
        stage_id=s1,
        title='G1 task',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='completed',
        priority=0,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        completed_at=_START_NOW + 3,
        updated_at=_START_NOW + 3,
        stage_name='Work',
        title_status='substantive',
      ),
    )
    b1_record = service.BlockerRecord(
      id=b1,
      goal_id=g1,
      stage_id=None,
      task_id=None,
      description='Need approval',
      impact='',
      attempts='',
      required='Sign-off',
      status='open',
      opened_at=_START_NOW + 3,
      resolved_at=None,
      resolution='',
      target_kind='goal',
      target_id=g1,
    )
    assert service.read_goal(
      conn, core.PositiveInt(g1)
    ) == service.GoalDetails(
      goal=service.GoalRecord(
        id=g1,
        text='First goal',
        status='blocked',
        status_reason='Need hardware',
        ever_activated=1,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        achieved_at=None,
        updated_at=_START_NOW + 3,
      ),
      stages=g1_stage_summary,
      tasks=g1_task_summary,
      blockers=(
        service.BlockerRecord(
          id=b2,
          goal_id=g1,
          stage_id=None,
          task_id=None,
          description='Need hardware',
          impact='',
          attempts='',
          required='Allocate box',
          status='open',
          opened_at=_START_NOW + 3,
          resolved_at=None,
          resolution='',
          target_kind='goal',
          target_id=g1,
        ),
        b1_record,
      ),
      evidence=(),
      decisions=(),
    )

    service.resolve_blocker(
      conn, core.PositiveInt(b2), core.SubstantiveText('Box ready')
    )
    assert service.read_goal(
      conn, core.PositiveInt(g1)
    ) == service.GoalDetails(
      goal=service.GoalRecord(
        id=g1,
        text='First goal',
        status='blocked',
        status_reason='Need approval',
        ever_activated=1,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        achieved_at=None,
        updated_at=_START_NOW + 3,
      ),
      stages=g1_stage_summary,
      tasks=g1_task_summary,
      blockers=(
        service.BlockerRecord(
          id=b2,
          goal_id=g1,
          stage_id=None,
          task_id=None,
          description='Need hardware',
          impact='',
          attempts='',
          required='Allocate box',
          status='resolved',
          opened_at=_START_NOW + 3,
          resolved_at=_START_NOW + 3,
          resolution='Box ready',
          target_kind='goal',
          target_id=g1,
        ),
        b1_record,
      ),
      evidence=(),
      decisions=(),
    )

    service.activate_goal(conn, core.PositiveInt(g2))
    service.resolve_blocker(
      conn, core.PositiveInt(b1), core.SubstantiveText('Approved')
    )
    expected_recovered_goals = (
      service.GoalListItem(
        id=g2,
        text='Second goal',
        status='pending',
        status_reason='Deferred while activating goal 1',
        ever_activated=1,
        created_at=_START_NOW + 2,
        started_at=_START_NOW + 2,
        achieved_at=None,
        updated_at=_START_NOW + 3,
        is_active=0,
        stage_names='Work',
      ),
      service.GoalListItem(
        id=g1,
        text='First goal',
        status='active',
        status_reason='',
        ever_activated=1,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        achieved_at=None,
        updated_at=_START_NOW + 3,
        is_active=1,
        stage_names='Work',
      ),
    )
    assert service.read_goals(conn) == expected_recovered_goals

    b3 = service.block_goal(
      conn,
      core.PositiveInt(g1),
      core.SubstantiveText('Temp hold'),
      required=core.SubstantiveText('Clear hold'),
    )
    service.activate_goal(conn, core.PositiveInt(g2))
    trig_sql = conn.execute(
      'SELECT sql FROM sqlite_master '
      "WHERE type = 'trigger' AND name = 'release_resolved_blocker'"
    ).fetchone()['sql']
    conn.execute('DROP TRIGGER release_resolved_blocker')
    conn.execute(
      "UPDATE blocker SET status = 'resolved', resolved_at = ?, "
      "resolution = 'Triggerless clear' WHERE id = ?",
      (_START_NOW + 4, b3),
    )
    conn.execute(trig_sql)
    service.reopen_goal(conn, core.PositiveInt(g1))
    assert service.read_goals(conn) == expected_recovered_goals

    service.add_evidence(
      conn,
      core.SubstantiveText('Goal 1 proven'),
      goal=core.PositiveInt(g1),
    )
    service.achieve_goal(conn, core.PositiveInt(g1))
    service.cancel_goal(conn, core.PositiveInt(g2), reason='Obsolete')
    assert service.read_goals(conn) == (
      service.GoalListItem(
        id=g2,
        text='Second goal',
        status='cancelled',
        status_reason='Obsolete',
        ever_activated=1,
        created_at=_START_NOW + 2,
        started_at=_START_NOW + 2,
        achieved_at=None,
        updated_at=_START_NOW + 3,
        is_active=0,
        stage_names='Work',
      ),
      service.GoalListItem(
        id=g1,
        text='First goal',
        status='achieved',
        status_reason='',
        ever_activated=1,
        created_at=_START_NOW + 1,
        started_at=_START_NOW + 1,
        achieved_at=_START_NOW + 3,
        updated_at=_START_NOW + 3,
        is_active=0,
        stage_names='Work',
      ),
    )


def test_records_legacy_markers_and_handoff_focus_and_bounding(
  base_snapshot: bytes,
) -> None:
  with _memory_db(base_snapshot) as (conn, clock):
    s1 = service.add_stage(
      conn, core.SubstantiveText('Main'), core.SubstantiveText('Ship')
    )
    g1 = service.create_goal(
      conn, core.GoalText('Main goal'), service.GoalStages.parse([s1])
    )
    t1 = _add_documented_task(
      conn, 'Primary task', core.PositiveInt(s1), goal=core.PositiveInt(g1)
    )

    clock[0] = _START_NOW + 1
    service.start_task(conn, core.PositiveInt(t1))
    d1 = service.add_decision(
      conn,
      core.SubstantiveText('Use immutable views'),
      task=core.PositiveInt(t1),
    )
    d2 = service.add_decision(
      conn,
      core.SubstantiveText('Keep project goal'),
      goal=core.PositiveInt(g1),
    )
    e1 = service.add_evidence(
      conn,
      core.SubstantiveText('Task proof'),
      task=core.PositiveInt(t1),
    )
    for i in range(6):
      clock[0] = _START_NOW + 2 + i
      service.append_task_log(conn, core.PositiveInt(t1), f'Log {i}')

    legacy_trig = conn.execute(
      'SELECT sql FROM sqlite_master '
      "WHERE type = 'trigger' AND name = 'decision_relationship_insert'"
    ).fetchone()['sql']
    conn.execute('DROP TRIGGER decision_relationship_insert')
    conn.execute(
      'INSERT INTO decision '
      '(task_id, summary, decided_at, context_status) '
      "VALUES (?, 'Legacy task decision', ?, 'legacy-unresolved')",
      (t1, _START_NOW + 9),
    )
    conn.execute(legacy_trig)

    task_decisions = service.read_decisions(
      conn, service.RecordListFilter.parse('Decision', task=t1)
    )
    goal_only_decisions = service.read_decisions(
      conn, service.RecordListFilter.parse('Decision', no_task=True)
    )
    task_evidence = service.read_evidence(
      conn, service.RecordListFilter.parse('Evidence', task=t1)
    )
    d1_record = service.DecisionRecord(
      id=d1,
      goal_id=g1,
      stage_id=s1,
      task_id=t1,
      summary='Use immutable views',
      rationale='',
      alternatives='',
      consequences='',
      decided_at=_START_NOW + 1,
      context_status='complete',
    )
    d2_record = service.DecisionRecord(
      id=d2,
      goal_id=g1,
      stage_id=None,
      task_id=None,
      summary='Keep project goal',
      rationale='',
      alternatives='',
      consequences='',
      decided_at=_START_NOW + 1,
      context_status='complete',
    )
    e1_record = service.EvidenceRecord(
      id=e1,
      goal_id=g1,
      stage_id=s1,
      task_id=t1,
      claim='Task proof',
      source='',
      result='',
      captured_at=_START_NOW + 1,
      context_status='complete',
      claim_status='substantive',
      stage_generation=0,
    )
    assert task_decisions == (
      service.DecisionRecord(
        id=3,
        goal_id=None,
        stage_id=None,
        task_id=t1,
        summary='Legacy task decision',
        rationale='',
        alternatives='',
        consequences='',
        decided_at=_START_NOW + 9,
        context_status='legacy-unresolved',
      ),
      d1_record,
    )
    assert goal_only_decisions == (d2_record,)
    assert task_evidence == (e1_record,)

    handoff = service.read_handoff(conn, 'memory://demo')
    expected_project = service.ProjectRecord(
      id=1,
      name='demo',
      objective='Ship service layer',
      scope='In-memory SQLite service',
      non_goals='Filesystem CLI',
      constraints_text='No disk writes',
      acceptance='Suite passes',
      created_at=_START_NOW,
      updated_at=_START_NOW + 7,
      charter_context_status='current',
      status='active',
      completed_at=None,
    )
    expected_state = service.ProjectState(
      id=1,
      summary='',
      next_action='',
      updated_at=_START_NOW + 7,
      revision=13,
    )
    expected_goal = service.ActiveGoalRef(
      goal=service.GoalRecord(
        id=g1,
        text='Main goal',
        status='active',
        status_reason='',
        ever_activated=1,
        created_at=_START_NOW,
        started_at=_START_NOW,
        achieved_at=None,
        updated_at=_START_NOW,
      )
    )
    expected_stage = service.StageRecord(
      id=s1,
      name='Main',
      outcome='Ship',
      purpose='',
      entry_conditions='',
      exit_evidence='',
      position=0,
      achievement_generation=0,
      achievement_generation_started_at=_START_NOW,
      created_at=_START_NOW,
      updated_at=_START_NOW,
      status='active',
      started_at=_START_NOW + 1,
      achieved_at=None,
      achievement_evidence_id=None,
    )
    expected_logs = tuple(
      service.HandoffLogEntry(
        occurred_at=_START_NOW + 7 - i,
        kind='note',
        message=f'Log {5 - i}',
      )
      for i in range(5)
    )
    assert handoff == service.HandoffData(
      path='memory://demo',
      project=expected_project,
      state=expected_state,
      goal=expected_goal,
      stage=expected_stage,
      task=service.HandoffTaskRecord(
        id=t1,
        goal_id=g1,
        stage_id=s1,
        title='Primary task',
        purpose='Implement feature',
        scope='Service module',
        exclusions='UI',
        result='Working contract',
        completion_evidence='Tests green',
        status='active',
        priority=0,
        created_at=_START_NOW,
        started_at=_START_NOW + 1,
        completed_at=None,
        updated_at=_START_NOW + 7,
        title_status='substantive',
      ),
      blocked_tasks=(),
      blocked_goals=(),
      blockers=(),
      decisions=(
        service.HandoffDecisionSummary(
          id=3,
          goal_id=None,
          stage_id=None,
          task_id=t1,
          summary='Legacy task decision',
          decided_at=_START_NOW + 9,
          context_status='legacy-unresolved',
        ),
        service.HandoffDecisionSummary(
          id=d1,
          goal_id=g1,
          stage_id=s1,
          task_id=t1,
          summary='Use immutable views',
          decided_at=_START_NOW + 1,
          context_status='complete',
        ),
      ),
      evidence=(e1_record,),
      logs=expected_logs,
      focus=service.HandoffFocus(kind='task', id=t1),
      pages=service.HandoffPages(
        blocked_tasks=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blocked_goals=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blockers=service.HandoffPage(shown=0, total=0, truncated=False),
        decisions=service.HandoffPage(shown=2, total=2, truncated=False),
        evidence=service.HandoffPage(shown=1, total=1, truncated=False),
        task_log=service.HandoffPage(shown=5, total=7, truncated=True),
      ),
    )

    service.block_task(
      conn,
      core.PositiveInt(t1),
      core.SubstantiveText('Wait'),
      required=core.SubstantiveText('Unblock'),
    )
    blocked_handoff = service.read_handoff(conn, 'memory://demo')
    assert blocked_handoff == service.HandoffData(
      path='memory://demo',
      project=service.ProjectRecord(
        id=1,
        name='demo',
        objective='Ship service layer',
        scope='In-memory SQLite service',
        non_goals='Filesystem CLI',
        constraints_text='No disk writes',
        acceptance='Suite passes',
        created_at=_START_NOW,
        updated_at=_START_NOW + 7,
        charter_context_status='current',
        status='blocked',
        completed_at=None,
      ),
      state=service.ProjectState(
        id=1,
        summary='',
        next_action='',
        updated_at=_START_NOW + 7,
        revision=14,
      ),
      goal=expected_goal,
      stage=None,
      task=None,
      blocked_tasks=(
        service.BlockedTaskSummary(
          id=t1,
          title='Primary task',
          status='blocked',
          goal_id=g1,
          stage_id=s1,
          stage_name='Main',
          updated_at=_START_NOW + 7,
          title_status='substantive',
        ),
      ),
      blocked_goals=(),
      blockers=(
        service.HandoffBlockerSummary(
          id=1,
          goal_id=g1,
          stage_id=s1,
          task_id=t1,
          description='Wait',
          required='Unblock',
          opened_at=_START_NOW + 7,
          target_kind='task',
          target_id=t1,
        ),
      ),
      decisions=(
        service.HandoffDecisionSummary(
          id=3,
          goal_id=None,
          stage_id=None,
          task_id=t1,
          summary='Legacy task decision',
          decided_at=_START_NOW + 9,
          context_status='legacy-unresolved',
        ),
        service.HandoffDecisionSummary(
          id=d1,
          goal_id=g1,
          stage_id=s1,
          task_id=t1,
          summary='Use immutable views',
          decided_at=_START_NOW + 1,
          context_status='complete',
        ),
      ),
      evidence=(e1_record,),
      logs=(
        service.HandoffLogEntry(
          occurred_at=_START_NOW + 7,
          kind='blocked',
          message='Wait',
        ),
        *expected_logs[:4],
      ),
      focus=service.HandoffFocus(kind='task', id=t1),
      pages=service.HandoffPages(
        blocked_tasks=service.HandoffPage(
          shown=1, total=1, truncated=False
        ),
        blocked_goals=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blockers=service.HandoffPage(shown=1, total=1, truncated=False),
        decisions=service.HandoffPage(shown=2, total=2, truncated=False),
        evidence=service.HandoffPage(shown=1, total=1, truncated=False),
        task_log=service.HandoffPage(shown=5, total=8, truncated=True),
      ),
    )

    service.cancel_task(conn, core.PositiveInt(t1), reason='Stop')
    goal_handoff = service.read_handoff(conn, 'memory://demo')
    assert goal_handoff == service.HandoffData(
      path='memory://demo',
      project=expected_project,
      state=service.ProjectState(
        id=1,
        summary='',
        next_action='',
        updated_at=_START_NOW + 7,
        revision=15,
      ),
      goal=expected_goal,
      stage=None,
      task=None,
      blocked_tasks=(),
      blocked_goals=(),
      blockers=(),
      decisions=(
        service.HandoffDecisionSummary(
          id=d2,
          goal_id=g1,
          stage_id=None,
          task_id=None,
          summary='Keep project goal',
          decided_at=_START_NOW + 1,
          context_status='complete',
        ),
      ),
      evidence=(),
      logs=(),
      focus=service.HandoffFocus(kind='goal', id=g1),
      pages=service.HandoffPages(
        blocked_tasks=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blocked_goals=service.HandoffPage(
          shown=0, total=0, truncated=False
        ),
        blockers=service.HandoffPage(shown=0, total=0, truncated=False),
        decisions=service.HandoffPage(shown=1, total=1, truncated=False),
        evidence=service.HandoffPage(shown=0, total=0, truncated=False),
        task_log=service.HandoffPage(shown=0, total=0, truncated=False),
      ),
    )


def test_empty_stage_stays_pending_until_completed_and_achieved(
  base_snapshot: bytes,
) -> None:
  with _memory_db(base_snapshot) as (conn, _clock):
    s1 = service.add_stage(
      conn,
      core.SubstantiveText('s1'),
      core.SubstantiveText('First done'),
      exit_evidence='Proof 1',
    )
    s2 = service.add_stage(
      conn,
      core.SubstantiveText('s2'),
      core.SubstantiveText('Second done'),
      exit_evidence='Proof 2',
    )
    g1 = service.create_goal(
      conn,
      core.GoalText('Ship stages'),
      service.GoalStages.parse([s1, s2]),
    )
    t1 = _add_documented_task(conn, 'Task 1', core.PositiveInt(s1))
    b1 = service.block_task(
      conn,
      core.PositiveInt(t1),
      core.SubstantiveText('Blocked work'),
      required=core.SubstantiveText('Resolve'),
    )
    blocked_stages = service.read_stages(conn)
    blocked_summary = service.read_project_summary(conn, 'memory://demo')
    blocked_goal = service.read_goal(conn, core.PositiveInt(g1))

    service.resolve_blocker(
      conn, core.PositiveInt(b1), core.SubstantiveText('Resolved')
    )
    service.start_task(conn, core.PositiveInt(t1))
    service.complete_task(conn, core.PositiveInt(t1))
    ev1 = service.add_evidence(
      conn,
      core.SubstantiveText('Stage 1 proof'),
      stage=core.PositiveInt(s1),
    )
    service.achieve_stage(
      conn, core.PositiveInt(s1), core.PositiveInt(ev1)
    )

    achieved_s1_stages = service.read_stages(conn)
    achieved_s1_summary = service.read_project_summary(
      conn, 'memory://demo'
    )
    achieved_s1_goal = service.read_goal(conn, core.PositiveInt(g1))

    s2_stage_item = service.StageListItem(
      id=s2,
      name='s2',
      outcome='Second done',
      purpose='',
      entry_conditions='',
      exit_evidence='Proof 2',
      position=1,
      achievement_generation=0,
      achievement_generation_started_at=_START_NOW,
      created_at=_START_NOW,
      updated_at=_START_NOW,
      status='pending',
      started_at=None,
      achieved_at=None,
      achievement_evidence_id=None,
      dependencies='',
    )
    s2_goal_stage = service.GoalStageSummary(
      id=s2,
      name='s2',
      outcome='Second done',
      status='pending',
    )
    expected_goal_record = service.GoalRecord(
      id=g1,
      text='Ship stages',
      status='active',
      status_reason='',
      ever_activated=1,
      created_at=_START_NOW,
      started_at=_START_NOW,
      achieved_at=None,
      updated_at=_START_NOW,
    )
    expected_project_summary = service.ProjectSummary(
      name='demo',
      status='active',
      objective='Ship service layer',
      updated_at=_START_NOW,
      path='memory://demo',
    )

    assert (
      blocked_stages,
      blocked_summary,
      blocked_goal,
      achieved_s1_stages,
      achieved_s1_summary,
      achieved_s1_goal,
    ) == (
      (
        service.StageListItem(
          id=s1,
          name='s1',
          outcome='First done',
          purpose='',
          entry_conditions='',
          exit_evidence='Proof 1',
          position=0,
          achievement_generation=0,
          achievement_generation_started_at=_START_NOW,
          created_at=_START_NOW,
          updated_at=_START_NOW,
          status='blocked',
          started_at=None,
          achieved_at=None,
          achievement_evidence_id=None,
          dependencies='',
        ),
        s2_stage_item,
      ),
      expected_project_summary,
      service.GoalDetails(
        goal=expected_goal_record,
        stages=(
          service.GoalStageSummary(
            id=s1,
            name='s1',
            outcome='First done',
            status='blocked',
          ),
          s2_goal_stage,
        ),
        tasks=(),
        blockers=(),
        evidence=(),
        decisions=(),
      ),
      (
        service.StageListItem(
          id=s1,
          name='s1',
          outcome='First done',
          purpose='',
          entry_conditions='',
          exit_evidence='Proof 1',
          position=0,
          achievement_generation=0,
          achievement_generation_started_at=_START_NOW,
          created_at=_START_NOW,
          updated_at=_START_NOW,
          status='achieved',
          started_at=_START_NOW,
          achieved_at=_START_NOW,
          achievement_evidence_id=ev1,
          dependencies='',
        ),
        s2_stage_item,
      ),
      expected_project_summary,
      service.GoalDetails(
        goal=expected_goal_record,
        stages=(
          service.GoalStageSummary(
            id=s1,
            name='s1',
            outcome='First done',
            status='achieved',
          ),
          s2_goal_stage,
        ),
        tasks=(),
        blockers=(),
        evidence=(),
        decisions=(),
      ),
    )


def _bounded(value: str) -> service.BoundedText:
  return service.BoundedText(
    value[: core.HANDOFF_TEXT_LIMIT + 1], len(value)
  )


def test_bounded_text_and_read_text_handoff_sql_edge_cases(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  bad_bounded: list[str] = []
  for fn in (
    lambda: service.BoundedText(cast(str, 123), 5),
    lambda: service.BoundedText('abc', True),
    lambda: service.BoundedText('abc', -1),
    lambda: service.BoundedText('abc', 2),
    lambda: service.BoundedText('abc', 5000),
  ):
    with pytest.raises(core.ProjectError) as bad_err:
      fn()
    bad_bounded.append(str(bad_err.value))
  assert bad_bounded == [
    'BoundedText prefix must be str',
    'BoundedText characters must be a non-negative int',
    'BoundedText characters must be a non-negative int',
    'BoundedText prefix length must be 2; received 3',
    'BoundedText prefix length must be 1001; received 3',
  ]

  with _memory_db() as (conn, _clock):
    charter = core.CharterInput.parse(
      objective='Initial objective',
      scope='Initial scope',
      non_goals='None',
      constraints='Strict',
      acceptance='Green',
    )
    schema.initialize_project(conn, _NAME, charter)
    emoji_boundary_values: list[service.BoundedText] = []
    for pad in (0, 1, 2, 3):
      candidate = ('a' * pad) + ('😀' * 1005)
      conn.execute(
        'UPDATE project SET objective = ? WHERE id = 1', (candidate,)
      )
      pad_handoff = service.read_text_handoff(conn, 'memory://demo')
      emoji_boundary_values.append(pad_handoff.project.objective)

    oversized_objective = 'a' * 70_000 + '\x00' + '😀' * 100
    conn.execute(
      'UPDATE project SET objective = ? WHERE id = 1',
      (oversized_objective,),
    )
    conn.execute(
      'UPDATE project_state SET summary = ?, next_action = ? WHERE id = 1',
      ('-\x00' + 's' * 1500, '-'),
    )

    stage_active = service.add_stage(
      conn,
      core.SubstantiveText('stage-active'),
      core.SubstantiveText('Outcome A'),
    )
    stage_blocked = service.add_stage(
      conn,
      core.SubstantiveText('B' + 'é' * 500 + '\x00' + '😀' * 600),
      core.SubstantiveText('Outcome B'),
    )
    blocked_goal_id = service.create_goal(
      conn,
      core.GoalText('Blocked goal text'),
      service.GoalStages.parse([stage_blocked]),
    )
    service.block_goal(
      conn,
      core.PositiveInt(blocked_goal_id),
      core.SubstantiveText('GBlock ' + '\x00' + 'w' * 5000),
      required=core.SubstantiveText('GReq'),
    )
    goal_id = service.create_goal(
      conn,
      core.GoalText('G' + '😀' * 1005),
      service.GoalStages.parse([stage_active]),
    )
    active_task_id = service.add_task(
      conn,
      core.SubstantiveText('T' + 'x' * 4500),
      stage=core.PositiveInt(stage_active),
      goal=core.PositiveInt(goal_id),
      purpose='P',
      scope='S',
      exclusions='E',
      result='R',
      completion_evidence='C',
    )
    service.start_task(conn, core.PositiveInt(active_task_id))
    blocked_task_id = service.add_task(
      conn,
      core.SubstantiveText('\x00'),
      stage=core.PositiveInt(stage_blocked),
      purpose='P2',
      scope='S2',
      exclusions='E2',
      result='R2',
      completion_evidence='C2',
    )
    service.block_task(
      conn,
      core.PositiveInt(blocked_task_id),
      core.SubstantiveText('Blocked desc ' + '\x00' + 'z' * 5000),
      required=core.SubstantiveText('Unblock req ' + '😀' * 1005),
    )
    blocked_no_stage_id = service.add_task(
      conn, core.SubstantiveText('No stage task')
    )
    service.block_task(
      conn,
      core.PositiveInt(blocked_no_stage_id),
      core.SubstantiveText('B2'),
      required=core.SubstantiveText('R2'),
    )
    service.add_decision(
      conn,
      core.SubstantiveText('Decision summary ' + 'a' * 1200),
      task=core.PositiveInt(active_task_id),
    )
    service.add_evidence(
      conn,
      core.SubstantiveText('Evidence claim ' + '\x00' + 'b' * 70_000),
      task=core.PositiveInt(active_task_id),
    )
    service.append_task_log(
      conn,
      core.PositiveInt(active_task_id),
      'Log message ' + '\x00' + '😀' * 1200,
      kind='note',
    )

    full = service.read_handoff(conn, 'memory://demo')
    bounded = service.read_text_handoff(conn, 'memory://demo')

    conn.execute(
      'UPDATE task SET purpose = ? WHERE id = ?',
      ('\x00', active_task_id),
    )
    nul_purpose_ok = service.read_text_handoff(conn, 'memory://demo').task
    conn.create_function('substantive', 1, lambda _value: True)
    conn.execute(
      'UPDATE task SET purpose = ? WHERE id = ?',
      ('\u2003\u3000\n', active_task_id),
    )
    schema.configure_connection(conn)
    with pytest.raises(core.ProjectError) as ws_full_err:
      service.read_handoff(conn, 'memory://demo')
    with pytest.raises(core.ProjectError) as ws_text_err:
      service.read_text_handoff(conn, 'memory://demo')

    conn.execute(
      "UPDATE project_state SET summary = CAST(X'ff' AS TEXT) WHERE id = 1"
    )
    with pytest.raises(core.ProjectError) as small_bad_utf8:
      service.read_text_handoff(conn, 'memory://demo')
    conn.execute(
      'UPDATE project_state SET summary = '
      "CAST(CAST(printf('%.*c', 70000, 'a') AS BLOB) || X'ff' AS TEXT) "
      'WHERE id = 1'
    )
    with pytest.raises(core.ProjectError) as large_bad_utf8:
      service.read_text_handoff(conn, 'memory://demo')

    dependent_stage = service.add_stage(
      conn,
      core.SubstantiveText('dependent-stage'),
      core.SubstantiveText('Dependent outcome'),
    )
    long_dep_stage = service.add_stage(
      conn,
      core.SubstantiveText('d' * 100_000),
      core.SubstantiveText('Long dep outcome'),
    )
    conn.execute(
      'INSERT INTO stage_dependency (stage_id, dependency_id) '
      'VALUES (?, ?)',
      (dependent_stage, long_dep_stage),
    )
    dep_task = service.add_task(
      conn,
      core.SubstantiveText('Blocked by long dep'),
      stage=core.PositiveInt(dependent_stage),
      purpose='P',
      scope='S',
      exclusions='E',
      result='R',
      completion_evidence='C',
    )
    with pytest.raises(core.ProjectError) as dep_err:
      service.start_task(conn, core.PositiveInt(dep_task))

  memdb_uri = 'file:/service_snapshot_isolation?vfs=memdb'
  writer = sqlite3.connect(memdb_uri, uri=True, timeout=0.01)
  reader = sqlite3.connect(memdb_uri, uri=True, timeout=0.01)
  try:
    schema.configure_connection(writer)
    writer.execute('PRAGMA busy_timeout = 10')
    schema.configure_connection(reader)
    schema.initialize_project(
      writer,
      _NAME,
      core.CharterInput.parse(
        objective='x' * 5000,
        scope='Scope',
        non_goals='None',
        constraints='Strict',
        acceptance='Green',
      ),
    )
    writer.commit()

    real_stream = service._stream_utf8_char_count
    busy_errors: list[str] = []

    def _contend_mid_read(
      conn_arg: sqlite3.Connection,
      table_name: str,
      column_name: str,
      row_id: int,
    ) -> int:
      if table_name == 'project' and column_name == 'objective':
        with pytest.raises(sqlite3.OperationalError) as busy_err:
          writer.execute(
            "UPDATE project SET objective = 'mutated' WHERE id = 1"
          )
          writer.commit()
        busy_errors.append(str(busy_err.value))
      return real_stream(conn_arg, table_name, column_name, row_id)

    monkeypatch.setattr(
      service, '_stream_utf8_char_count', _contend_mid_read
    )
    snapshot_handoff = service.read_text_handoff(reader, 'memory://snap')
    writer.execute("UPDATE project SET objective = 'mutated' WHERE id = 1")
    writer.commit()
    after_handoff = service.read_text_handoff(reader, 'memory://snap')
  finally:
    reader.close()
    writer.close()

  raw_utf16 = sqlite3.connect(':memory:')
  try:
    raw_utf16.execute("PRAGMA encoding = 'UTF-16le'")
    raw_utf16.row_factory = sqlite3.Row
    raw_utf16.create_function('substantive', 1, core.is_substantive)
    for sql in schema._canonical_schema_definitions().values():
      raw_utf16.execute(sql)
    raw_utf16.execute(f'PRAGMA user_version = {schema.SCHEMA_VERSION}')
    raw_utf16.execute(
      'INSERT INTO project (id, name, objective, scope, non_goals, '
      'constraints_text, acceptance, created_at, updated_at) '
      "VALUES (1, 'demo', 'O', 'S', 'N', 'C', 'A', 1, 1)"
    )
    raw_utf16.execute(
      'INSERT INTO project_state (id, summary, next_action, updated_at) '
      "VALUES (1, '', '', 1)"
    )
    raw_utf16.execute(
      'INSERT INTO stage (id, name, outcome, created_at, updated_at) '
      "VALUES (1, 'dep', 'Dep', 1, 1), (2, 'target', 'Target', 1, 1)"
    )
    raw_utf16.execute(
      'INSERT INTO stage_dependency (stage_id, dependency_id) '
      'VALUES (2, 1)'
    )
    raw_utf16.execute(
      'INSERT INTO task (id, stage_id, title, purpose, scope, exclusions, '
      'result, completion_evidence, created_at, updated_at) '
      "VALUES (1, 2, 'T', 'P', 'S', 'E', 'R', 'C', 1, 1)"
    )
    with pytest.raises(core.ProjectError) as handoff_utf16_err:
      service.read_text_handoff(raw_utf16, 'memory://raw-utf16')
    with pytest.raises(core.ProjectError) as start_utf16_err:
      service.start_task(raw_utf16, core.PositiveInt(1))
  finally:
    raw_utf16.close()

  assert (
    emoji_boundary_values,
    bounded,
    nul_purpose_ok,
    str(ws_full_err.value),
    str(ws_text_err.value),
    str(small_bad_utf8.value),
    str(large_bad_utf8.value),
    str(dep_err.value),
    busy_errors,
    snapshot_handoff.project.objective.characters,
    after_handoff.project.objective,
    str(handoff_utf16_err.value),
    str(start_utf16_err.value),
  ) == (
    [
      _bounded(('a' * 0) + ('😀' * 1005)),
      _bounded(('a' * 1) + ('😀' * 1005)),
      _bounded(('a' * 2) + ('😀' * 1005)),
      _bounded(('a' * 3) + ('😀' * 1005)),
    ],
    service.TextHandoffData(
      path='memory://demo',
      project=service.TextHandoffProject(
        name=_bounded(full.project.name),
        status=full.project.status,
        objective=_bounded(full.project.objective),
        charter_context_status=full.project.charter_context_status,
      ),
      state=service.TextHandoffState(
        summary=_bounded(full.state.summary),
        next_action=_bounded(full.state.next_action),
      ),
      goal=service.TextHandoffGoal(
        id=goal_id,
        status='active',
        text=_bounded('G' + '😀' * 1005),
      ),
      stage=service.TextHandoffStage(
        id=stage_active,
        name=_bounded('stage-active'),
      ),
      task=service.TextHandoffTask(
        id=active_task_id,
        goal_id=goal_id,
        stage_id=stage_active,
        title=_bounded('T' + 'x' * 4500),
        title_status='substantive',
      ),
      blocked_tasks=tuple(
        service.TextBlockedTaskSummary(
          id=item.id,
          title=_bounded(item.title),
          goal_id=item.goal_id,
          stage_id=item.stage_id,
          stage_name=(
            _bounded(item.stage_name)
            if item.stage_name is not None
            else None
          ),
          title_status=item.title_status,
        )
        for item in full.blocked_tasks
      ),
      blocked_goals=tuple(
        service.TextBlockedGoalSummary(
          id=item.id,
          text=_bounded(item.text),
          status_reason=_bounded(item.status_reason),
        )
        for item in full.blocked_goals
      ),
      blockers=tuple(
        service.TextHandoffBlockerSummary(
          id=item.id,
          description=_bounded(item.description),
          required=_bounded(item.required),
          target_kind=item.target_kind,
          target_id=item.target_id,
        )
        for item in full.blockers
      ),
      decisions=tuple(
        service.TextHandoffDecisionSummary(
          id=item.id,
          summary=_bounded(item.summary),
          context_status=item.context_status,
        )
        for item in full.decisions
      ),
      evidence=tuple(
        service.TextHandoffEvidenceSummary(
          id=item.id,
          claim=_bounded(item.claim),
          context_status=item.context_status,
          claim_status=item.claim_status,
        )
        for item in full.evidence
      ),
      logs=tuple(
        service.TextHandoffLogEntry(
          kind=_bounded(item.kind),
          message=_bounded(item.message),
        )
        for item in full.logs
      ),
      focus=full.focus,
      pages=full.pages,
    ),
    service.TextHandoffTask(
      id=active_task_id,
      goal_id=goal_id,
      stage_id=stage_active,
      title=_bounded('T' + 'x' * 4500),
      title_status='substantive',
    ),
    'Starting a task requires documented purpose',
    'Starting a task requires documented purpose',
    "Database error: 'utf-8' codec can't decode byte 0xff in position 0: "
    'invalid start byte',
    "Database error: 'utf-8' codec can't decode byte 0xff in "
    'position 4464: invalid start byte',
    f'Stage dependency is not achieved: {"d" * core.HANDOFF_TEXT_LIMIT}…',
    ['database is locked'],
    5000,
    _bounded('mutated'),
    "Unsupported project database encoding 'UTF-16le'; expected 'UTF-8'",
    "Unsupported project database encoding 'UTF-16le'; expected 'UTF-8'",
  )
