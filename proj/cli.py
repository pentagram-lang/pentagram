from __future__ import annotations

import base64
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, cast

import click

from proj.db import (
  ProjectError,
  archive_project_db,
  create_project_db,
  iter_project_dbs,
  open_project,
)
from proj.fmt import (
  format_blocker_list,
  format_decision_list,
  format_evidence_list,
  format_goal_list,
  format_goal_show,
  format_project_list,
  format_project_show,
  format_stage_list,
  format_task_list,
  format_task_logs,
  format_task_show,
  render_handoff,
)
from proj.ops import (
  BlockerStatus,
  GoalRef,
  ProjectSummary,
  TaskStatus,
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


def _root(ctx: click.Context) -> Path:
  if isinstance(ctx.obj, Path):
    return ctx.obj
  return Path(__file__).resolve().parent.parent


@contextmanager
def _guard() -> Iterator[None]:
  try:
    yield
  except ProjectError as err:
    raise click.ClickException(str(err)) from err


def _opt_goal(raw: str | None) -> GoalRef | None:
  return parse_goal_ref(raw) if raw is not None else None


def _emit(payload: object, text: str, as_json: bool) -> None:
  if as_json:
    click.echo(json.dumps(payload, ensure_ascii=False))
  else:
    click.echo(text)


@click.group(name='proj')
@click.option(
  '--root',
  type=click.Path(path_type=Path, file_okay=False),
  default=None,
  help='Repository root directory.',
)
@click.pass_context
def project_group(ctx: click.Context, root: Path | None) -> None:
  """Manage Pentagram project workflow databases."""
  if root is not None:
    ctx.obj = root
  elif not isinstance(ctx.obj, Path):
    ctx.obj = Path(__file__).resolve().parent.parent


@project_group.command('create')
@click.argument('name')
@click.option('--objective', required=True)
@click.option('--scope', default='')
@click.option('--non-goals', default='')
@click.option('--constraints', default='')
@click.option('--acceptance', default='')
@click.option('--summary', default='')
@click.option('--next-action', default='')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def project_create(
  ctx: click.Context,
  name: str,
  objective: str,
  scope: str,
  non_goals: str,
  constraints: str,
  acceptance: str,
  summary: str,
  next_action: str,
  as_json: bool,
) -> None:
  with _guard():
    path = create_project_db(
      _root(ctx),
      name=name,
      objective=objective,
      scope=scope,
      non_goals=non_goals,
      constraints_text=constraints,
      acceptance=acceptance,
      summary=summary,
      next_action=next_action,
    )
    with open_project(_root(ctx), name, readonly=True) as conn:
      pv = read_project(conn)
  _emit(dataclass_to_dict(pv), f'Created {name}: {path}', as_json)


@project_group.command('list')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def project_list(ctx: click.Context, as_json: bool) -> None:
  items: list[ProjectSummary] = []
  with _guard():
    root = _root(ctx)
    for name, _ in iter_project_dbs(root):
      with open_project(root, name, readonly=True) as conn:
        items.append(read_project_summary(conn))
  _emit(
    [dataclass_to_dict(i) for i in items],
    format_project_list(items),
    as_json,
  )


@project_group.command('show')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def project_show(ctx: click.Context, name: str, as_json: bool) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    pv = read_project(conn)
  _emit(dataclass_to_dict(pv), format_project_show(pv), as_json)


@project_group.command('handoff')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def project_handoff(ctx: click.Context, name: str, as_json: bool) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    data = read_handoff(conn)
  _emit(dataclass_to_dict(data), render_handoff(data), as_json)


@project_group.command('update')
@click.argument('name')
@click.option('--objective', default=None)
@click.option('--scope', default=None)
@click.option('--non-goals', default=None)
@click.option('--constraints', default=None)
@click.option('--acceptance', default=None)
@click.option('--summary', default=None)
@click.option('--next-action', default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def project_update(
  ctx: click.Context,
  name: str,
  objective: str | None,
  scope: str | None,
  non_goals: str | None,
  constraints: str | None,
  acceptance: str | None,
  summary: str | None,
  next_action: str | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    pv = update_project(
      conn,
      objective=objective,
      scope=scope,
      non_goals=non_goals,
      constraints_text=constraints,
      acceptance=acceptance,
      summary=summary,
      next_action=next_action,
    )
  _emit(dataclass_to_dict(pv), format_project_show(pv), as_json)


@project_group.command('archive')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def project_archive(ctx: click.Context, name: str, as_json: bool) -> None:
  with _guard():
    dest = archive_project_db(_root(ctx), name)
  _emit(
    {'name': name, 'archive_path': str(dest)},
    f'Archived {name}: {dest}',
    as_json,
  )


@project_group.group('goal')
def goal_group() -> None:
  """Manage project goals."""


@goal_group.command('list')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_list(ctx: click.Context, name: str, as_json: bool) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    goals = list_goals(conn)
  _emit(
    [dataclass_to_dict(g) for g in goals], format_goal_list(goals), as_json
  )


@goal_group.command('create')
@click.argument('name')
@click.option('--text', required=True)
@click.option('--stage', 'stages', multiple=True, required=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_create(
  ctx: click.Context,
  name: str,
  text: str,
  stages: tuple[str, ...],
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    g = create_goal(conn, text=text, stages=stages)
  _emit(dataclass_to_dict(g), f'Goal {g.id}: {g.status}', as_json)


@goal_group.command('activate')
@click.argument('name')
@click.argument('goal')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_activate(
  ctx: click.Context, name: str, goal: str, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    g = activate_goal(conn, goal)
  _emit(dataclass_to_dict(g), f'Goal {g.id}: {g.status}', as_json)


@goal_group.command('show')
@click.argument('name')
@click.argument('goal', default='active')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_show(
  ctx: click.Context, name: str, goal: str, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    d = show_goal(conn, goal)
  _emit(dataclass_to_dict(d), format_goal_show(d), as_json)


@goal_group.command('text')
@click.argument('name')
@click.argument('goal', default='active')
@click.pass_context
def goal_text(ctx: click.Context, name: str, goal: str) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    text = get_goal_text(conn, goal)
  click.echo(text)


@goal_group.command('copy')
@click.argument('name')
@click.argument('goal', default='active')
@click.pass_context
def goal_copy(ctx: click.Context, name: str, goal: str) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    text = get_goal_text(conn, goal)
  b64 = base64.b64encode(text.encode('utf-8')).decode('ascii')
  sys.stdout.write(f'\x1b]52;c;{b64}\x07')
  sys.stdout.flush()


@goal_group.command('achieve')
@click.argument('name')
@click.argument('goal', default='active')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_achieve(
  ctx: click.Context, name: str, goal: str, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    g = achieve_goal(conn, goal)
  _emit(dataclass_to_dict(g), f'Goal {g.id}: {g.status}', as_json)


@goal_group.command('block')
@click.argument('name')
@click.argument('goal', default='active')
@click.option('--description', required=True)
@click.option('--required', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_block(
  ctx: click.Context,
  name: str,
  goal: str,
  description: str,
  required: str,
  impact: str,
  attempts: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    g = block_goal(
      conn,
      goal,
      description=description,
      required=required,
      impact=impact,
      attempts=attempts,
    )
  _emit(dataclass_to_dict(g), f'Goal {g.id}: {g.status}', as_json)


@goal_group.command('reopen')
@click.argument('name')
@click.argument('goal')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_reopen(
  ctx: click.Context, name: str, goal: str, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    g = reopen_goal(conn, goal)
  _emit(dataclass_to_dict(g), f'Goal {g.id}: {g.status}', as_json)


@goal_group.command('cancel')
@click.argument('name')
@click.argument('goal', default='active')
@click.option('--reason', default='')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_cancel(
  ctx: click.Context, name: str, goal: str, reason: str, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    g = cancel_goal(conn, goal, reason=reason)
  _emit(dataclass_to_dict(g), f'Goal {g.id}: {g.status}', as_json)


@project_group.group('stage')
def stage_group() -> None:
  """Manage project stages."""


@stage_group.command('list')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_list(ctx: click.Context, name: str, as_json: bool) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    stages = list_stages(conn)
  _emit(
    [dataclass_to_dict(s) for s in stages],
    format_stage_list(stages),
    as_json,
  )


@stage_group.command('create')
@click.argument('name')
@click.argument('stage_name')
@click.option('--outcome', required=True)
@click.option('--purpose', default='')
@click.option('--entry-conditions', default='')
@click.option('--exit-evidence', default='')
@click.option('--position', type=int, default=None)
@click.option('--depends-on', multiple=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_create(
  ctx: click.Context,
  name: str,
  stage_name: str,
  outcome: str,
  purpose: str,
  entry_conditions: str,
  exit_evidence: str,
  position: int | None,
  depends_on: tuple[str, ...],
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    s = create_stage(
      conn,
      name=stage_name,
      outcome=outcome,
      purpose=purpose,
      entry_conditions=entry_conditions,
      exit_evidence=exit_evidence,
      position=position,
      dependencies=depends_on,
    )
  _emit(
    dataclass_to_dict(s), f'Stage {s.id} ({s.name}): {s.status}', as_json
  )


@stage_group.command('update')
@click.argument('name')
@click.argument('stage')
@click.option('--stage-name', default=None)
@click.option('--outcome', default=None)
@click.option('--purpose', default=None)
@click.option('--entry-conditions', default=None)
@click.option('--exit-evidence', default=None)
@click.option('--position', type=int, default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_update(
  ctx: click.Context,
  name: str,
  stage: str,
  stage_name: str | None,
  outcome: str | None,
  purpose: str | None,
  entry_conditions: str | None,
  exit_evidence: str | None,
  position: int | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    s = update_stage(
      conn,
      stage,
      name=stage_name,
      outcome=outcome,
      purpose=purpose,
      entry_conditions=entry_conditions,
      exit_evidence=exit_evidence,
      position=position,
    )
  _emit(
    dataclass_to_dict(s), f'Stage {s.id} ({s.name}): {s.status}', as_json
  )


@stage_group.command('achieve')
@click.argument('name')
@click.argument('stage')
@click.option('--evidence', type=int, required=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_achieve(
  ctx: click.Context, name: str, stage: str, evidence: int, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    s = achieve_stage(conn, stage, evidence)
  _emit(
    dataclass_to_dict(s), f'Stage {s.id} ({s.name}): {s.status}', as_json
  )


@stage_group.command('add-dependency')
@click.argument('name')
@click.argument('stage')
@click.argument('dependency')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_add_dependency(
  ctx: click.Context,
  name: str,
  stage: str,
  dependency: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    s = add_stage_dependency(conn, stage, dependency)
  _emit(
    dataclass_to_dict(s), f'Stage {s.id} ({s.name}): {s.status}', as_json
  )


@stage_group.command('remove-dependency')
@click.argument('name')
@click.argument('stage')
@click.argument('dependency')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_remove_dependency(
  ctx: click.Context,
  name: str,
  stage: str,
  dependency: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    s = remove_stage_dependency(conn, stage, dependency)
  _emit(
    dataclass_to_dict(s), f'Stage {s.id} ({s.name}): {s.status}', as_json
  )


@project_group.group('task')
def task_group() -> None:
  """Manage project tasks."""


@task_group.command('list')
@click.argument('name')
@click.option('--stage', default=None)
@click.option(
  '--status',
  type=click.Choice(
    ['pending', 'active', 'blocked', 'completed', 'cancelled']
  ),
  default=None,
)
@click.option('--goal', default=None)
@click.option('--tag', default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_list(
  ctx: click.Context,
  name: str,
  stage: str | None,
  status: str | None,
  goal: str | None,
  tag: str | None,
  as_json: bool,
) -> None:
  typed_status = cast(TaskStatus | None, status)
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    tasks = list_tasks(
      conn,
      stage=stage,
      status=typed_status,
      goal=_opt_goal(goal),
      tag=tag,
    )
  _emit(
    [dataclass_to_dict(t) for t in tasks], format_task_list(tasks), as_json
  )


@task_group.command('ready')
@click.argument('name')
@click.option('--stage', default=None)
@click.option('--goal', default=None)
@click.option('--tag', default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_ready(
  ctx: click.Context,
  name: str,
  stage: str | None,
  goal: str | None,
  tag: str | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    tasks = list_ready_tasks(
      conn, stage=stage, goal=_opt_goal(goal), tag=tag
    )
  _emit(
    [dataclass_to_dict(t) for t in tasks], format_task_list(tasks), as_json
  )


@task_group.command('create')
@click.argument('name')
@click.option('--title', required=True)
@click.option('--stage', default=None)
@click.option('--goal', default=None)
@click.option('--purpose', default='')
@click.option('--scope', default='')
@click.option('--exclusions', default='')
@click.option('--result', default='')
@click.option('--completion-evidence', default='')
@click.option('--priority', type=int, default=0)
@click.option('--tag', 'tags', multiple=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_create(
  ctx: click.Context,
  name: str,
  title: str,
  stage: str | None,
  goal: str | None,
  purpose: str,
  scope: str,
  exclusions: str,
  result: str,
  completion_evidence: str,
  priority: int,
  tags: tuple[str, ...],
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = create_task(
      conn,
      title=title,
      stage=stage,
      goal=_opt_goal(goal),
      purpose=purpose,
      scope=scope,
      exclusions=exclusions,
      result=result,
      completion_evidence=completion_evidence,
      priority=priority,
      tags=tags,
    )
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('show')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_show(
  ctx: click.Context, name: str, task_id: int, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    d = show_task(conn, task_id)
  _emit(dataclass_to_dict(d), format_task_show(d), as_json)


@task_group.command('list-logs')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--limit', type=int, default=20)
@click.option('--since', type=int, default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_list_logs(
  ctx: click.Context,
  name: str,
  task_id: int,
  limit: int,
  since: int | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    rows, more = list_task_logs(conn, task_id, limit=limit, since=since)
  _emit(
    {'items': [dataclass_to_dict(r) for r in rows], 'has_more': more},
    format_task_logs(rows, more),
    as_json,
  )


@task_group.command('activate')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_activate(
  ctx: click.Context, name: str, task_id: int, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = activate_task(conn, task_id)
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('add-log')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.argument('message')
@click.option('--kind', default='note')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_add_log(
  ctx: click.Context,
  name: str,
  task_id: int,
  message: str,
  kind: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    entry = append_task_log(conn, task_id, message, kind=kind)
  _emit(dataclass_to_dict(entry), f'Log {entry.id}', as_json)


@task_group.command('update')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--title', default=None)
@click.option('--stage', default=None)
@click.option('--goal', default=None)
@click.option('--no-goal', is_flag=True)
@click.option('--purpose', default=None)
@click.option('--scope', default=None)
@click.option('--exclusions', default=None)
@click.option('--result', default=None)
@click.option('--completion-evidence', default=None)
@click.option('--priority', type=int, default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_update(
  ctx: click.Context,
  name: str,
  task_id: int,
  title: str | None,
  stage: str | None,
  goal: str | None,
  no_goal: bool,
  purpose: str | None,
  scope: str | None,
  exclusions: str | None,
  result: str | None,
  completion_evidence: str | None,
  priority: int | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = update_task(
      conn,
      task_id,
      title=title,
      stage=stage,
      goal=_opt_goal(goal),
      clear_goal=no_goal,
      purpose=purpose,
      scope=scope,
      exclusions=exclusions,
      result=result,
      completion_evidence=completion_evidence,
      priority=priority,
    )
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('complete')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_complete(
  ctx: click.Context, name: str, task_id: int, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = complete_task(conn, task_id)
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('block')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--description', required=True)
@click.option('--required', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_block(
  ctx: click.Context,
  name: str,
  task_id: int,
  description: str,
  required: str,
  impact: str,
  attempts: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = block_task(
      conn,
      task_id,
      description=description,
      required=required,
      impact=impact,
      attempts=attempts,
    )
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('reopen')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_reopen(
  ctx: click.Context, name: str, task_id: int, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = reopen_task(conn, task_id)
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('cancel')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_cancel(
  ctx: click.Context, name: str, task_id: int, as_json: bool
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = cancel_task(conn, task_id)
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.status}', as_json)


@task_group.command('add-tag')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.argument('tags', nargs=-1, required=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_add_tag(
  ctx: click.Context,
  name: str,
  task_id: int,
  tags: tuple[str, ...],
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = add_task_tags(conn, task_id, tags)
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.tags}', as_json)


@task_group.command('remove-tag')
@click.argument('name')
@click.argument('task_id', metavar='TASK', type=int)
@click.argument('tags', nargs=-1, required=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_remove_tag(
  ctx: click.Context,
  name: str,
  task_id: int,
  tags: tuple[str, ...],
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    t = remove_task_tags(conn, task_id, tags)
  _emit(dataclass_to_dict(t), f'Task {t.id}: {t.tags}', as_json)


@project_group.group('decision')
def decision_group() -> None:
  """Record and inspect project decisions."""


@decision_group.command('create')
@click.argument('name')
@click.option('--summary', required=True)
@click.option('--rationale', default='')
@click.option('--alternatives', default='')
@click.option('--consequences', default='')
@click.option('--task', 'task_id', type=int, default=None)
@click.option('--stage', default=None)
@click.option('--goal', default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def decision_create(
  ctx: click.Context,
  name: str,
  summary: str,
  rationale: str,
  alternatives: str,
  consequences: str,
  task_id: int | None,
  stage: str | None,
  goal: str | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    d = create_decision(
      conn,
      summary=summary,
      rationale=rationale,
      alternatives=alternatives,
      consequences=consequences,
      task_id=task_id,
      stage=stage,
      goal=_opt_goal(goal),
    )
  _emit(dataclass_to_dict(d), f'Decision {d.id}', as_json)


@decision_group.command('list')
@click.argument('name')
@click.option('--limit', type=int, default=20)
@click.option('--stage', default=None)
@click.option('--task', 'task_id', type=int, default=None)
@click.option('--goal', default=None)
@click.option('--no-task', is_flag=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def decision_list(
  ctx: click.Context,
  name: str,
  limit: int,
  stage: str | None,
  task_id: int | None,
  goal: str | None,
  no_task: bool,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    rows, more = list_decisions(
      conn,
      limit=limit,
      stage=stage,
      task_id=task_id,
      goal=_opt_goal(goal),
      no_task=no_task,
    )
  _emit(
    {'items': [dataclass_to_dict(r) for r in rows], 'has_more': more},
    format_decision_list(rows, more),
    as_json,
  )


@project_group.group('blocker')
def blocker_group() -> None:
  """Record and resolve project blockers."""


@blocker_group.command('create')
@click.argument('name')
@click.option('--description', required=True)
@click.option('--required', required=True)
@click.option('--task', 'task_id', type=int, default=None)
@click.option('--goal', default=None)
@click.option('--stage', default=None)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def blocker_create(
  ctx: click.Context,
  name: str,
  description: str,
  required: str,
  task_id: int | None,
  goal: str | None,
  stage: str | None,
  impact: str,
  attempts: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    b = create_blocker(
      conn,
      description=description,
      required=required,
      task_id=task_id,
      goal=_opt_goal(goal),
      stage=stage,
      impact=impact,
      attempts=attempts,
    )
  _emit(dataclass_to_dict(b), f'Blocker {b.id}: {b.status}', as_json)


@blocker_group.command('list')
@click.argument('name')
@click.option(
  '--status',
  type=click.Choice(['open', 'resolved', 'withdrawn', 'all']),
  default='open',
)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def blocker_list(
  ctx: click.Context, name: str, status: str, as_json: bool
) -> None:
  typed_status = cast(Literal[BlockerStatus, 'all'], status)
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    rows = list_blockers(conn, status=typed_status)
  _emit(
    [dataclass_to_dict(r) for r in rows],
    format_blocker_list(rows, status),
    as_json,
  )


@blocker_group.command('resolve')
@click.argument('name')
@click.argument('blocker_id', metavar='BLOCKER', type=int)
@click.option('--resolution', required=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def blocker_resolve(
  ctx: click.Context,
  name: str,
  blocker_id: int,
  resolution: str,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    b = resolve_blocker(conn, blocker_id, resolution=resolution)
  _emit(dataclass_to_dict(b), f'Blocker {b.id}: {b.status}', as_json)


@project_group.group('evidence')
def evidence_group() -> None:
  """Record and inspect project evidence."""


@evidence_group.command('create')
@click.argument('name')
@click.option('--claim', required=True)
@click.option('--source', default='')
@click.option('--result', default='')
@click.option('--task', 'task_id', type=int, default=None)
@click.option('--stage', default=None)
@click.option('--goal', default=None)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def evidence_create(
  ctx: click.Context,
  name: str,
  claim: str,
  source: str,
  result: str,
  task_id: int | None,
  stage: str | None,
  goal: str | None,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name) as conn:
    e = create_evidence(
      conn,
      claim=claim,
      source=source,
      result=result,
      task_id=task_id,
      stage=stage,
      goal=_opt_goal(goal),
    )
  _emit(dataclass_to_dict(e), f'Evidence {e.id}', as_json)


@evidence_group.command('list')
@click.argument('name')
@click.option('--limit', type=int, default=20)
@click.option('--stage', default=None)
@click.option('--task', 'task_id', type=int, default=None)
@click.option('--goal', default=None)
@click.option('--no-task', is_flag=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def evidence_list(
  ctx: click.Context,
  name: str,
  limit: int,
  stage: str | None,
  task_id: int | None,
  goal: str | None,
  no_task: bool,
  as_json: bool,
) -> None:
  with _guard(), open_project(_root(ctx), name, readonly=True) as conn:
    rows, more = list_evidence(
      conn,
      limit=limit,
      stage=stage,
      task_id=task_id,
      goal=_opt_goal(goal),
      no_task=no_task,
    )
  _emit(
    {'items': [dataclass_to_dict(r) for r in rows], 'has_more': more},
    format_evidence_list(rows, more),
    as_json,
  )
