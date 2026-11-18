from __future__ import annotations

from proj.fmt import (
  HANDOFF_TEXT_LIMIT,
  escape_cell,
  format_blocker_list,
  format_goal_show,
  format_project_show,
  format_task_show,
  limit_notice,
  render_handoff,
  render_kv,
  render_table,
  shorten_cell,
)
from proj.ops import (
  BlockerRecord,
  DecisionRecord,
  EvidenceRecord,
  GoalDetails,
  GoalView,
  HandoffData,
  ProjectView,
  StageView,
  TaskDetails,
  TaskLog,
  TaskView,
)


def test_escape_shorten_and_kv() -> None:
  assert escape_cell(None) == '-'
  assert escape_cell('') == '-'
  assert escape_cell('-') == '"-"'
  assert escape_cell(True) == 'True'
  assert escape_cell(42) == '42'
  assert escape_cell(()) == '-'
  assert escape_cell(('a', 'b')) == 'a, b'
  assert escape_cell('line1\nline2') == r'line1\nline2'
  assert escape_cell('café') == 'café'

  exact = 'a' * HANDOFF_TEXT_LIMIT
  assert shorten_cell(exact) == exact
  assert shorten_cell(exact + 'b') == exact + '…'
  with_nl = ('a' * (HANDOFF_TEXT_LIMIT - 1)) + '\nb'
  assert shorten_cell(with_nl) == f'{("a" * (HANDOFF_TEXT_LIMIT - 1))}\\n…'

  assert render_kv((('A', ''), ('B', '-'))) == 'A: -\nB: "-"'
  assert limit_notice(5, False) == ''
  assert (
    limit_notice(5, True)
    == 'Showing 5 rows; more exist. Pass --limit for more.'
  )


def test_render_table_empty_and_wide_chars() -> None:
  assert render_table(('ID', 'Name'), ()) == 'ID  Name\n--  ----'

  out = render_table(('Name', 'Note'), (('界a', 'x   '), ('hi', 'y')))
  assert out == 'Name  Note\n----  ----\n界a   x   \nhi    y'


def test_format_show_blocker_and_handoff() -> None:
  b = BlockerRecord(
    1, None, 1, 2, 'Stuck', '', '', 'Need key', 'open', 50, None, ''
  )
  assert format_blocker_list([b], 'open') == (
    'Blockers (status=open):\n'
    'ID  Status  Goal  Stage  Task  Description  Required  Resolution\n'
    '--  ------  ----  -----  ----  -----------  --------  ----------\n'
    '1   open    -     1      2     Stuck        Need key  -'
  )

  long_obj = 'x' * (HANDOFF_TEXT_LIMIT + 5)
  pv = ProjectView(
    'demo',
    'active',
    long_obj,
    'S',
    'N',
    'C',
    'A',
    'Sum',
    'Next',
    True,
    10,
    20,
  )
  assert format_project_show(
    ProjectView(
      'demo',
      'active',
      'Obj',
      'S',
      'N',
      'C',
      'A',
      'Sum',
      'Next',
      True,
      10,
      20,
    )
  ) == (
    'Name: demo\nStatus: active\nCharter complete: True\nObjective: Obj\n'
    'Scope: S\nNon-goals: N\nConstraints: C\nAcceptance: A\nSummary: Sum\n'
    'Next action: Next\nCreated: 10\nUpdated: 20'
  )

  stage = StageView(
    1, 's1', 'Out', '', '', 'Ex', 1, 'active', (), None, None, 10, 10
  )
  goal = GoalView(1, 'Goal', 'active', '', (1,), 10, 10, None, 10)
  task = TaskView(
    2,
    1,
    1,
    'T2',
    'P',
    'S',
    'E',
    'Res',
    'CE',
    'active',
    0,
    (),
    11,
    12,
    None,
    12,
  )
  logs = (
    TaskLog(2, 2, 30, 'note', 'second'),
    TaskLog(1, 2, 20, 'started', 'first'),
  )
  decs = (DecisionRecord(1, 1, 1, 2, 'Use SQLite', '', '', '', 25),)
  evs = (EvidenceRecord(1, 1, 1, 2, 'Passed', '', 'ok', 26),)

  goal_out = format_goal_show(GoalDetails(goal, (task,), (b,), decs, evs))
  assert 'Blockers (1):\nID  Status' in goal_out
  assert 'Blockers (status=' not in goal_out

  task_out = format_task_show(TaskDetails(task, logs, (b,), decs, evs))
  assert 'Completion evidence: CE' in task_out
  assert 'Blockers (1):\nID  Status' in task_out
  assert 'Blockers (status=' not in task_out

  data = HandoffData(
    pv, goal, task, stage, (), (), (), 'task', 2, decs, 3, evs, 1, logs, 2
  )
  assert render_handoff(data) == (
    f'Project: demo\n'
    f'Status: active\n'
    f'Charter complete: True\n'
    f'Objective: {"x" * HANDOFF_TEXT_LIMIT}…\n'
    f'Summary: Sum\n'
    f'Next action: Next\n'
    f'Focus: task 2\n'
    f'\n'
    f'Active goal:\n'
    f'ID: 1\n'
    f'Stages: 1\n'
    f'Text: Goal\n'
    f'\n'
    f'Active task:\n'
    f'ID: 2\n'
    f'Stage: 1 (s1)\n'
    f'Goal: 1\n'
    f'Title: T2\n'
    f'Result: Res\n'
    f'Completion evidence: CE\n'
    f'\n'
    f'Decisions (1 of 3):\n'
    f'ID  Decided  Summary\n'
    f'--  -------  ----------\n'
    f'1   25       Use SQLite\n'
    f'\n'
    f'Evidence (1 of 1):\n'
    f'ID  Captured  Claim   Result\n'
    f'--  --------  ------  ------\n'
    f'1   26        Passed  ok\n'
    f'\n'
    f'Task logs (2 of 2):\n'
    f'ID  Occurred  Kind     Message\n'
    f'--  --------  -------  -------\n'
    f'1   20        started  first\n'
    f'2   30        note     second'
  )
