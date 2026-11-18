from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from proj.db import ProjectError, connect_memory, init_project
from proj.ops import (
  BlockerRecord,
  DecisionRecord,
  EvidenceRecord,
  GoalDetails,
  GoalView,
  HandoffData,
  ProjectSummary,
  ProjectView,
  StageView,
  TaskDetails,
  TaskLog,
  TaskView,
  achieve_goal,
  achieve_stage,
  activate_goal,
  activate_task,
  add_stage_dependency,
  add_task_tags,
  append_task_log,
  block_goal,
  block_task,
  cancel_goal,
  cancel_task,
  complete_task,
  create_blocker,
  create_decision,
  create_evidence,
  create_goal,
  create_stage,
  create_task,
  dataclass_to_dict,
  derive_project_status,
  derive_stage_status,
  get_goal_text,
  list_blockers,
  list_decisions,
  list_evidence,
  list_goals,
  list_ready_tasks,
  list_stages,
  list_task_logs,
  list_tasks,
  parse_goal_ref,
  parse_stage_ref,
  read_handoff,
  read_project,
  read_project_summary,
  remove_stage_dependency,
  remove_task_tags,
  reopen_goal,
  reopen_task,
  resolve_blocker,
  show_goal,
  show_task,
  update_project,
  update_stage,
  update_task,
)


@pytest.fixture
def mem() -> Iterator[sqlite3.Connection]:
  conn = connect_memory()
  try:
    init_project(
      conn,
      name='demo',
      objective='Build proj',
      scope='Core ops',
      non_goals='UI',
      constraints_text='Strict',
      acceptance='Tests pass',
      now=100,
    )
    yield conn
  finally:
    conn.close()


def _make_ready_task(
  conn: sqlite3.Connection,
  *,
  stage: str | int = 's1',
  goal: int | None = None,
  title: str = 'Task 1',
  now: int = 110,
) -> TaskView:
  return create_task(
    conn,
    title=title,
    stage=stage,
    goal=goal,
    purpose='Purpose',
    scope='Scope',
    exclusions='None',
    result='Done',
    completion_evidence='Verified',
    now=now,
  )


def test_pure_derivations_and_refs() -> None:
  assert derive_stage_status((), False) == 'pending'
  assert derive_stage_status(('active', 'blocked'), True) == 'active'
  assert derive_stage_status(('pending', 'blocked'), True) == 'pending'
  assert derive_stage_status(('blocked', 'completed'), True) == 'blocked'
  assert (
    derive_stage_status(('completed', 'cancelled'), True) == 'achieved'
  )
  assert (
    derive_stage_status(('completed', 'cancelled'), False) == 'pending'
  )
  assert (
    derive_stage_status(('cancelled', 'cancelled'), False) == 'superseded'
  )

  assert derive_project_status(()) == 'active'
  assert derive_project_status(('superseded',)) == 'active'
  assert derive_project_status(('achieved', 'superseded')) == 'complete'
  assert derive_project_status(('achieved', 'pending')) == 'active'
  assert derive_project_status(('achieved', 'blocked')) == 'blocked'

  assert parse_stage_ref(3) == 3
  assert parse_stage_ref('42') == 42
  assert parse_stage_ref('stage-1') == 'stage-1'
  for bad_stage in (0, -1, True, '', '0'):
    with pytest.raises(ProjectError):
      parse_stage_ref(bad_stage)

  assert parse_goal_ref('active') == 'active'
  assert parse_goal_ref('7') == 7
  assert parse_goal_ref(7) == 7
  for bad_goal in (0, -1, True, '', '0', 'other'):
    with pytest.raises(ProjectError):
      parse_goal_ref(bad_goal)


def test_project_reads_and_recharter() -> None:
  conn = connect_memory()
  try:
    init_project(conn, name='p', objective='Obj', now=10)
    assert read_project_summary(conn) == ProjectSummary(
      'p', 'active', 'Obj', '', '', 10, 10
    )
    assert read_project(conn).charter_complete is False

    pv = update_project(
      conn,
      scope='S',
      non_goals='N',
      constraints_text='C',
      acceptance='A',
      summary='Ready',
      next_action='Act',
      now=20,
    )
    assert pv == ProjectView(
      'p',
      'active',
      'Obj',
      'S',
      'N',
      'C',
      'A',
      'Ready',
      'Act',
      True,
      10,
      20,
    )
    assert dataclass_to_dict(pv)['charter_complete'] is True

    s = create_stage(
      conn, name='s1', outcome='Out', exit_evidence='Ev', now=25
    )
    t = _make_ready_task(conn, stage=s.id, now=30)
    activate_task(conn, t.id, now=35)

    with pytest.raises(ProjectError):
      update_project(conn, scope='  ', now=40)
    with pytest.raises(ProjectError):
      update_project(conn, scope='New', now=40)

    up = update_project(conn, summary='Still active', now=40)
    assert up.summary == 'Still active'

    complete_task(conn, t.id, now=45)
    ev = create_evidence(conn, claim='Proof', stage=s.id, now=45)
    achieve_stage(conn, s.id, ev.id, now=50)
    assert read_project(conn).status == 'complete'

    g = create_goal(conn, text='Goal', stages=[s.id], now=55)
    with pytest.raises(ProjectError):
      update_project(conn, scope='Rechartered', now=60)
    cancel_goal(conn, g.id, now=61)

    pv2 = update_project(conn, scope='Rechartered', now=65)
    assert pv2.scope == 'Rechartered'
    assert pv2.status == 'active'
    assert list_stages(conn)[0].achievement_evidence_id is None
  finally:
    conn.close()


def test_stages_dependencies_and_invalidation(
  mem: sqlite3.Connection,
) -> None:
  with pytest.raises(ProjectError):
    create_stage(mem, name='123', outcome='Bad name', now=104)

  s1 = create_stage(
    mem, name='s1', outcome='Out 1', exit_evidence='Ex 1', now=105
  )
  with pytest.raises(ProjectError):
    update_stage(mem, s1.id, name='99', now=105)
  s2 = create_stage(
    mem,
    name='s2',
    outcome='Out 2',
    exit_evidence='Ex 2',
    dependencies=['s1'],
    now=106,
  )
  assert s2.dependencies == (s1.id,)

  with pytest.raises(ProjectError):
    add_stage_dependency(mem, s1.id, s1.id)
  with pytest.raises(ProjectError):
    add_stage_dependency(mem, s2.id, s1.id)
  with pytest.raises(ProjectError):
    add_stage_dependency(mem, s1.id, s2.id)

  t1 = _make_ready_task(mem, stage='s1', title='T1', now=110)
  t2 = _make_ready_task(mem, stage='s2', title='T2', now=110)
  assert [t.id for t in list_ready_tasks(mem)] == [t1.id]

  with pytest.raises(ProjectError):
    activate_task(mem, t2.id, now=112)

  activate_task(mem, t1.id, now=112)
  complete_task(mem, t1.id, now=115)
  ev = create_evidence(mem, claim='Stage 1 done', stage=s1.id, now=116)
  with pytest.raises(ProjectError):
    achieve_stage(mem, s1.id, ev.id, now=114)
  s1_ach = achieve_stage(mem, s1.id, ev.id, now=118)
  assert s1_ach == StageView(
    s1.id,
    's1',
    'Out 1',
    '',
    '',
    'Ex 1',
    1,
    'achieved',
    (),
    ev.id,
    118,
    105,
    118,
  )

  activate_task(mem, t2.id, now=120)
  with pytest.raises(ProjectError):
    remove_stage_dependency(mem, s2.id, s1.id)
  with pytest.raises(ProjectError):
    update_stage(mem, s1.id, outcome='Changed', now=121)
  with pytest.raises(ProjectError):
    reopen_task(mem, t1.id, now=121)

  complete_task(mem, t2.id, now=125)
  remove_stage_dependency(mem, s2.id, s1.id)
  add_stage_dependency(mem, s2.id, s1.id)

  t_later = _make_ready_task(mem, stage=s2.id, title='Later', now=126)
  activate_task(mem, t_later.id, now=127)
  complete_task(mem, t_later.id, now=130)
  ev2 = create_evidence(mem, claim='Stage 2 done', stage=s2.id, now=130)
  achieve_stage(mem, s2.id, ev2.id, now=131)

  t_active_move = _make_ready_task(
    mem, stage=s2.id, title='Back move', now=131
  )
  activate_task(mem, t_active_move.id, now=132)
  assert list_stages(mem)[1].achievement_evidence_id is None
  t_back_to_s1 = update_task(mem, t_active_move.id, stage=s1.id, now=134)
  assert t_back_to_s1.stage_id == s1.id
  assert list_stages(mem)[0].achievement_evidence_id is None
  complete_task(mem, t_active_move.id, now=135)
  ev1_b = create_evidence(
    mem, claim='Stage 1 re-done', stage=s1.id, now=135
  )
  achieve_stage(mem, s1.id, ev1_b.id, now=136)
  ev2_b = create_evidence(
    mem, claim='Stage 2 re-done', stage=s2.id, now=136
  )
  achieve_stage(mem, s2.id, ev2_b.id, now=137)

  t_moved = update_task(mem, t_later.id, stage=s1.id, now=138)
  assert t_moved.stage_id == s1.id
  assert list_stages(mem)[0].achievement_evidence_id == ev1_b.id

  update_stage(mem, s1.id, outcome='Out 1 v2', now=138)
  stages_after = list_stages(mem)
  assert stages_after[0].achievement_evidence_id is None
  assert stages_after[1].achievement_evidence_id is None

  with pytest.raises(ProjectError):
    achieve_stage(mem, s2.id, ev2_b.id, now=139)

  s3 = create_stage(
    mem, name='s3', outcome='Out 3', exit_evidence='Ex 3', now=140
  )
  t3 = _make_ready_task(mem, stage=s3.id, title='T3', now=141)
  activate_task(mem, t3.id, now=142)
  complete_task(mem, t3.id, now=143)
  ev3 = create_evidence(mem, claim='Stage 3 done', stage=s3.id, now=143)
  achieve_stage(mem, s3.id, ev3.id, now=144)
  s3_dep = add_stage_dependency(mem, s3.id, s1.id, now=145)
  assert s3_dep.achievement_evidence_id is None


def test_goals_and_handoffs(mem: sqlite3.Connection) -> None:
  s1 = create_stage(
    mem, name='s1', outcome='Out 1', exit_evidence='Ex 1', now=105
  )
  with pytest.raises(ProjectError):
    update_stage(mem, s1.id, name='99', now=105)
  with pytest.raises(ProjectError):
    create_goal(mem, text='No stages', stages=(), now=106)
  with pytest.raises(ProjectError):
    create_goal(mem, text='a\x00b', stages=[s1.id], now=106)

  g1 = create_goal(mem, text='First goal', stages=[s1.id], now=110)
  t_g1 = _make_ready_task(
    mem, stage=s1.id, goal=g1.id, title='G1T', now=111
  )
  t_free = _make_ready_task(mem, stage=s1.id, title='FreeT', now=111)
  activate_task(mem, t_g1.id, now=112)

  g2 = create_goal(mem, text='Second goal', stages=[s1.id], now=120)
  assert g2.status == 'active'
  assert get_goal_text(mem) == 'Second goal'
  goals = {g.id: g for g in list_goals(mem)}
  assert goals[g1.id].status == 'pending'
  assert goals[g1.id].status_reason == f'Deferred for goal {g2.id}'
  assert show_task(mem, t_g1.id).task.status == 'pending'

  activate_task(mem, t_free.id, now=125)
  activate_goal(mem, g1.id, now=130)
  assert show_task(mem, t_free.id).task.status == 'active'
  assert get_goal_text(mem) == 'First goal'

  with pytest.raises(ProjectError):
    achieve_goal(mem, g1.id, now=131)
  complete_task(mem, t_free.id, now=132)
  with pytest.raises(ProjectError):
    achieve_goal(mem, g1.id, now=133)

  create_evidence(mem, claim='Goal proof', goal=g1.id, now=135)
  g1_ach = achieve_goal(mem, g1.id, now=140)
  assert g1_ach == GoalView(
    g1.id, 'First goal', 'achieved', '', (s1.id,), 110, 110, 140, 140
  )

  activate_goal(mem, g2.id, now=145)
  g2_blk = block_goal(
    mem, g2.id, description='Need decision', required='Pick X', now=150
  )
  assert g2_blk.status == 'blocked'
  with pytest.raises(ProjectError):
    reopen_goal(mem, g2.id, now=151)

  blk = list_blockers(mem)[0]
  resolve_blocker(mem, blk.id, resolution='Picked X', now=155)
  assert get_goal_text(mem) == 'Second goal'
  assert show_goal(mem, g2.id) == GoalDetails(
    GoalView(
      g2.id, 'Second goal', 'active', '', (s1.id,), 120, 120, None, 155
    ),
    (),
    (
      BlockerRecord(
        blk.id,
        g2.id,
        None,
        None,
        'Need decision',
        '',
        '',
        'Pick X',
        'resolved',
        150,
        155,
        'Picked X',
      ),
    ),
    (),
    (),
  )
  g2_can = cancel_goal(mem, g2.id, reason='Superseded', now=160)
  assert g2_can.status == 'cancelled'


def test_tasks_tags_logs_and_blockers(mem: sqlite3.Connection) -> None:
  s1 = create_stage(mem, name='s1', outcome='Out', now=105)
  g1 = create_goal(mem, text='Goal', stages=[s1.id], now=106)
  t1 = _make_ready_task(mem, stage=s1.id, goal=g1.id, title='T1', now=110)
  t2 = create_task(
    mem,
    title='T2',
    stage=s1.id,
    purpose='P',
    scope='S',
    exclusions='E',
    result='R',
    completion_evidence='CE',
    priority=5,
    tags=('core', 'mvp'),
    now=110,
  )
  assert [t.id for t in list_tasks(mem, tag='  ')] == []
  assert [t.id for t in list_tasks(mem, tag='core')] == [t2.id]
  t2 = remove_task_tags(mem, t2.id, ['mvp'])
  t2 = add_task_tags(mem, t2.id, ['fast'])
  assert t2.tags == ('core', 'fast')

  activate_task(mem, t1.id, now=115)
  activate_task(mem, t2.id, now=120)
  assert show_task(mem, t1.id).task.started_at == 115
  logs1, more1 = list_task_logs(mem, t1.id, limit=1)
  assert more1 is True
  assert len(logs1) == 1
  assert logs1[0].kind == 'handoff'

  append_task_log(mem, t2.id, 'Checked edge', kind='note', now=122)
  logs_since, more_since = list_task_logs(mem, t2.id, since=121)
  assert more_since is False
  assert logs_since == [TaskLog(4, t2.id, 122, 'note', 'Checked edge')]

  t1_blk = block_task(
    mem, t1.id, description='Blocked', required='Fix dep', now=125
  )
  assert t1_blk.status == 'blocked'
  with pytest.raises(ProjectError):
    update_task(mem, t1.id, clear_goal=True, now=126)

  blk = list_blockers(mem, status='open')[0]
  resolve_blocker(mem, blk.id, resolution='Dep fixed', now=130)
  assert show_task(mem, t1.id).task.status == 'pending'

  t1_can = cancel_task(mem, t1.id, now=135)
  assert t1_can.status == 'cancelled'
  t1_re = reopen_task(mem, t1.id, now=140)
  assert t1_re.status == 'pending'


def test_decisions_evidence_and_handoff(mem: sqlite3.Connection) -> None:
  s1 = create_stage(mem, name='s1', outcome='Out', now=105)
  create_stage(mem, name='s2', outcome='Out 2', now=105)
  g1 = create_goal(mem, text='Goal 1', stages=[s1.id], now=106)
  t1 = _make_ready_task(mem, stage=s1.id, goal=g1.id, title='T1', now=110)

  with pytest.raises(ProjectError):
    create_blocker(
      mem, description='Bad', required='Fix', stage=s1.id, now=111
    )
  with pytest.raises(ProjectError):
    create_decision(
      mem, summary='Conflict', task_id=t1.id, stage='s2', now=111
    )

  d_goal = create_decision(
    mem, summary='Goal dec', goal=g1.id, stage=s1.id, now=112
  )
  e_goal = create_evidence(
    mem, claim='Goal ev', goal=g1.id, stage=s1.id, now=113
  )
  assert d_goal == DecisionRecord(
    1, g1.id, s1.id, None, 'Goal dec', '', '', '', 112
  )
  assert e_goal == EvidenceRecord(
    1, g1.id, s1.id, None, 'Goal ev', '', '', 113
  )

  h_goal = read_handoff(mem)
  assert (h_goal.focus_kind, h_goal.focus_id) == ('goal', g1.id)
  assert h_goal.decisions == (d_goal,)
  assert h_goal.evidence == (e_goal,)
  assert h_goal.task_logs == ()

  activate_task(mem, t1.id, now=115)
  for i in range(6):
    create_decision(mem, summary=f'D{i}', task_id=t1.id, now=120 + i)
    create_evidence(mem, claim=f'E{i}', task_id=t1.id, now=120 + i)
    append_task_log(mem, t1.id, f'L{i}', now=120 + i)

  decs, more_d = list_decisions(mem, task_id=t1.id, limit=4)
  assert more_d is True and len(decs) == 4
  evs, more_e = list_evidence(mem, goal=g1.id, no_task=True)
  assert more_e is False and evs == [e_goal]

  h_task = read_handoff(mem)
  assert (h_task.focus_kind, h_task.focus_id) == ('task', t1.id)
  assert len(h_task.decisions) == 5 and h_task.decisions_total == 6
  assert len(h_task.evidence) == 5 and h_task.evidence_total == 6
  assert len(h_task.task_logs) == 5 and h_task.task_logs_total == 7

  block_task(mem, t1.id, description='Stuck', required='Help', now=130)
  h_blk = read_handoff(mem)
  assert (h_blk.focus_kind, h_blk.focus_id) == ('task', t1.id)
  assert len(h_blk.blocked_tasks) == 1
  assert isinstance(h_blk, HandoffData)

  d_task_details = show_task(mem, t1.id)
  assert isinstance(d_task_details, TaskDetails)
  assert len(d_task_details.decisions) == 6
