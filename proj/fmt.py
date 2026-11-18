from __future__ import annotations

import json
from collections.abc import Sequence

from wcwidth import wcswidth

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
)

HANDOFF_TEXT_LIMIT = 1000


def escape_cell(value: object) -> str:
  if value is None or value == '':
    return '-'
  if value == '-':
    return '"-"'
  if isinstance(value, (bool, int)):
    return str(value)
  if isinstance(value, (list, tuple)):
    return ', '.join(escape_cell(v) for v in value) if value else '-'
  text = value if isinstance(value, str) else str(value)
  return json.dumps(text, ensure_ascii=False)[1:-1]


def shorten_cell(value: object, limit: int = HANDOFF_TEXT_LIMIT) -> str:
  if isinstance(value, str) and len(value) > limit:
    return f'{escape_cell(value[:limit])}…'
  return escape_cell(value)


def _width(text: str) -> int:
  w = wcswidth(text)
  return w if w >= 0 else len(text)


def render_table(
  headers: Sequence[str], rows: Sequence[Sequence[object]]
) -> str:
  grid = [[escape_cell(c) for c in row] for row in rows]
  widths = [
    max([_width(h), *(_width(r[i]) for r in grid)])
    for i, h in enumerate(headers)
  ]
  last = len(headers) - 1

  def fmt_row(cells: Sequence[str]) -> str:
    parts = [
      c if i == last else f'{c}{" " * (widths[i] - _width(c))}'
      for i, c in enumerate(cells)
    ]
    return '  '.join(parts)

  sep = '  '.join('-' * w for w in widths)
  lines = [fmt_row(headers), sep, *(fmt_row(r) for r in grid)]
  return '\n'.join(lines)


def render_kv(pairs: Sequence[tuple[str, object]]) -> str:
  return '\n'.join(f'{k}: {escape_cell(v)}' for k, v in pairs)


def limit_notice(shown: int, has_more: bool, flag: str = '--limit') -> str:
  if not has_more:
    return ''
  return f'Showing {shown} rows; more exist. Pass {flag} for more.'


def _with_notice(body: str, shown: int, has_more: bool) -> str:
  note = limit_notice(shown, has_more)
  return f'{body}\n{note}' if note else body


def format_project_list(items: Sequence[ProjectSummary]) -> str:
  return render_table(
    ('Name', 'Status', 'Objective', 'Summary', 'Next action'),
    [
      (p.name, p.status, p.objective, p.summary, p.next_action)
      for p in items
    ],
  )


def format_project_show(p: ProjectView) -> str:
  return render_kv(
    (
      ('Name', p.name),
      ('Status', p.status),
      ('Charter complete', p.charter_complete),
      ('Objective', p.objective),
      ('Scope', p.scope),
      ('Non-goals', p.non_goals),
      ('Constraints', p.constraints_text),
      ('Acceptance', p.acceptance),
      ('Summary', p.summary),
      ('Next action', p.next_action),
      ('Created', p.created_at),
      ('Updated', p.updated_at),
    )
  )


def format_stage_list(stages: Sequence[StageView]) -> str:
  return render_table(
    ('ID', 'Name', 'Status', 'Deps', 'Outcome', 'Exit evidence'),
    [
      (s.id, s.name, s.status, s.dependencies, s.outcome, s.exit_evidence)
      for s in stages
    ],
  )


def format_goal_list(goals: Sequence[GoalView]) -> str:
  return render_table(
    ('ID', 'Status', 'Stages', 'Reason', 'Text'),
    [(g.id, g.status, g.stages, g.status_reason, g.text) for g in goals],
  )


def format_task_list(tasks: Sequence[TaskView]) -> str:
  return render_table(
    ('ID', 'Status', 'Priority', 'Stage', 'Goal', 'Tags', 'Title'),
    [
      (t.id, t.status, t.priority, t.stage_id, t.goal_id, t.tags, t.title)
      for t in tasks
    ],
  )


def format_task_logs(logs: Sequence[TaskLog], has_more: bool) -> str:
  table = render_table(
    ('ID', 'Occurred', 'Kind', 'Message'),
    [(x.id, x.occurred_at, x.kind, x.message) for x in logs],
  )
  return _with_notice(table, len(logs), has_more)


def format_decision_list(
  decisions: Sequence[DecisionRecord], has_more: bool
) -> str:
  table = render_table(
    ('ID', 'Decided', 'Goal', 'Stage', 'Task', 'Summary'),
    [
      (d.id, d.decided_at, d.goal_id, d.stage_id, d.task_id, d.summary)
      for d in decisions
    ],
  )
  return _with_notice(table, len(decisions), has_more)


def _blocker_table(blockers: Sequence[BlockerRecord]) -> str:
  return render_table(
    (
      'ID',
      'Status',
      'Goal',
      'Stage',
      'Task',
      'Description',
      'Required',
      'Resolution',
    ),
    [
      (
        b.id,
        b.status,
        b.goal_id,
        b.stage_id,
        b.task_id,
        b.description,
        b.required,
        b.resolution,
      )
      for b in blockers
    ],
  )


def format_blocker_list(
  blockers: Sequence[BlockerRecord], status_filter: str
) -> str:
  return f'Blockers (status={status_filter}):\n{_blocker_table(blockers)}'


def format_evidence_list(
  evidence: Sequence[EvidenceRecord], has_more: bool
) -> str:
  table = render_table(
    (
      'ID',
      'Captured',
      'Goal',
      'Stage',
      'Task',
      'Claim',
      'Source',
      'Result',
    ),
    [
      (
        e.id,
        e.captured_at,
        e.goal_id,
        e.stage_id,
        e.task_id,
        e.claim,
        e.source,
        e.result,
      )
      for e in evidence
    ],
  )
  return _with_notice(table, len(evidence), has_more)


def format_goal_show(d: GoalDetails) -> str:
  g = d.goal
  sections = [
    render_kv(
      (
        ('ID', g.id),
        ('Status', g.status),
        ('Reason', g.status_reason),
        ('Stages', g.stages),
        ('Text', g.text),
        ('Started', g.started_at),
        ('Achieved', g.achieved_at),
      )
    ),
    f'Tasks ({len(d.tasks)}):\n{format_task_list(d.tasks)}',
    f'Blockers ({len(d.blockers)}):\n{_blocker_table(d.blockers)}',
    f'Decisions ({len(d.decisions)}):\n'
    f'{format_decision_list(d.decisions, False)}',
    f'Evidence ({len(d.evidence)}):\n'
    f'{format_evidence_list(d.evidence, False)}',
  ]
  return '\n\n'.join(sections)


def format_task_show(d: TaskDetails) -> str:
  t = d.task
  sections = [
    render_kv(
      (
        ('ID', t.id),
        ('Status', t.status),
        ('Priority', t.priority),
        ('Stage', t.stage_id),
        ('Goal', t.goal_id),
        ('Tags', t.tags),
        ('Title', t.title),
        ('Purpose', t.purpose),
        ('Scope', t.scope),
        ('Exclusions', t.exclusions),
        ('Result', t.result),
        ('Completion evidence', t.completion_evidence),
        ('Started', t.started_at),
        ('Completed', t.completed_at),
      )
    ),
    f'Logs ({len(d.logs)}):\n{format_task_logs(d.logs, False)}',
    f'Blockers ({len(d.blockers)}):\n{_blocker_table(d.blockers)}',
    f'Decisions ({len(d.decisions)}):\n'
    f'{format_decision_list(d.decisions, False)}',
    f'Evidence ({len(d.evidence)}):\n'
    f'{format_evidence_list(d.evidence, False)}',
  ]
  return '\n\n'.join(sections)


def render_handoff(data: HandoffData) -> str:
  p = data.project
  focus = (
    f'{data.focus_kind} {data.focus_id}'
    if data.focus_kind is not None and data.focus_id is not None
    else 'none'
  )
  parts = [
    render_kv(
      (
        ('Project', p.name),
        ('Status', p.status),
        ('Charter complete', p.charter_complete),
        ('Objective', shorten_cell(p.objective)),
        ('Summary', shorten_cell(p.summary)),
        ('Next action', shorten_cell(p.next_action)),
        ('Focus', focus),
      )
    )
  ]
  if data.active_goal is not None:
    g = data.active_goal
    parts.append(
      'Active goal:\n'
      + render_kv(
        (
          ('ID', g.id),
          ('Stages', g.stages),
          ('Text', shorten_cell(g.text)),
        )
      )
    )
  if data.active_task is not None:
    t = data.active_task
    st_label = (
      f'{data.active_stage.id} ({shorten_cell(data.active_stage.name)})'
      if data.active_stage is not None
      else t.stage_id
    )
    parts.append(
      'Active task:\n'
      + render_kv(
        (
          ('ID', t.id),
          ('Stage', st_label),
          ('Goal', t.goal_id),
          ('Title', shorten_cell(t.title)),
          ('Result', shorten_cell(t.result)),
          ('Completion evidence', shorten_cell(t.completion_evidence)),
        )
      )
    )
  if data.open_blockers:
    tbl = render_table(
      ('ID', 'Goal', 'Task', 'Description', 'Required'),
      [
        (
          b.id,
          b.goal_id,
          b.task_id,
          shorten_cell(b.description),
          shorten_cell(b.required),
        )
        for b in data.open_blockers
      ],
    )
    parts.append(f'Open blockers ({len(data.open_blockers)}):\n{tbl}')
  if data.blocked_tasks:
    tbl = render_table(
      ('ID', 'Stage', 'Goal', 'Title'),
      [
        (t.id, t.stage_id, t.goal_id, shorten_cell(t.title))
        for t in data.blocked_tasks
      ],
    )
    parts.append(f'Blocked tasks ({len(data.blocked_tasks)}):\n{tbl}')
  if data.blocked_goals:
    tbl = render_table(
      ('ID', 'Reason', 'Text'),
      [
        (g.id, shorten_cell(g.status_reason), shorten_cell(g.text))
        for g in data.blocked_goals
      ],
    )
    parts.append(f'Blocked goals ({len(data.blocked_goals)}):\n{tbl}')
  if data.decisions:
    tbl = render_table(
      ('ID', 'Decided', 'Summary'),
      [
        (d.id, d.decided_at, shorten_cell(d.summary))
        for d in data.decisions
      ],
    )
    n, total = len(data.decisions), data.decisions_total
    parts.append(f'Decisions ({n} of {total}):\n{tbl}')
  if data.evidence:
    tbl = render_table(
      ('ID', 'Captured', 'Claim', 'Result'),
      [
        (
          e.id,
          e.captured_at,
          shorten_cell(e.claim),
          shorten_cell(e.result),
        )
        for e in data.evidence
      ],
    )
    parts.append(
      f'Evidence ({len(data.evidence)} of {data.evidence_total}):\n{tbl}'
    )
  if data.task_logs:
    tbl = render_table(
      ('ID', 'Occurred', 'Kind', 'Message'),
      [
        (x.id, x.occurred_at, x.kind, shorten_cell(x.message))
        for x in reversed(data.task_logs)
      ],
    )
    n, total = len(data.task_logs), data.task_logs_total
    parts.append(f'Task logs ({n} of {total}):\n{tbl}')
  return '\n\n'.join(parts)
