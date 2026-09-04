import base64
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from zero import lib

SCHEMA_VERSION = 6
MAX_GOAL_TEXT_LENGTH = 4000
PROJECT_SUFFIX = '.sqlite3'
PROJECT_NAME_PATTERN = re.compile(r'^[^/\\\x00]+$')
GOAL_STATUSES = ('active', 'blocked', 'achieved', 'cancelled')
TASK_STATUSES = (
  'pending',
  'active',
  'completed',
  'blocked',
  'cancelled',
)
BLOCKER_STATUSES = ('open', 'resolved', 'withdrawn')
HANDOFF_LIMIT = 5
HANDOFF_TEXT_LIMIT = 1000
MAX_PROJECT_NAME_LENGTH = 200
UNSET = object()
_SCHEMA_DEFINITIONS = None
PROJECT_CHARTER_STABLE_ERROR = (
  'active task or active/blocked goal requires a stable project charter; '
  'end the task and cancel the goal before re-chartering'
)
TASK_START_TIME_ERROR = (
  'task start time must be positive and not in the future'
)
TASK_COMPLETION_TIME_ERROR = (
  'task completion time must follow activation and not be in the future'
)

SCHEMA_SQL = """
CREATE TABLE project (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT NOT NULL,
  objective TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  non_goals TEXT NOT NULL DEFAULT '',
  constraints_text TEXT NOT NULL DEFAULT '',
  acceptance TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  charter_context_status TEXT NOT NULL DEFAULT 'current'
    CHECK (charter_context_status IN ('current', 'legacy-incomplete'))
);

CREATE TABLE project_charter_history (
  id INTEGER PRIMARY KEY,
  objective TEXT NOT NULL,
  scope TEXT NOT NULL,
  non_goals TEXT NOT NULL,
  constraints_text TEXT NOT NULL,
  acceptance TEXT NOT NULL,
  replaced_at INTEGER NOT NULL
);

CREATE TABLE goal (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL
    CHECK (
      length(text) > 0
      AND substantive(text)
      AND length(text) <= 4000
    ),
  status TEXT NOT NULL DEFAULT 'cancelled'
    CHECK (status IN ('active', 'blocked', 'achieved', 'cancelled')),
  status_reason TEXT NOT NULL DEFAULT '',
  ever_activated INTEGER NOT NULL DEFAULT 0
    CHECK (ever_activated IN (0, 1)),
  created_at INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  achieved_at INTEGER,
  updated_at INTEGER NOT NULL,
  CHECK (
    (status = 'achieved' AND achieved_at IS NOT NULL)
    OR (status <> 'achieved' AND achieved_at IS NULL)
  )
);

CREATE TABLE stage (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  outcome TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  entry_conditions TEXT NOT NULL DEFAULT '',
  exit_evidence TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0,
  achievement_generation INTEGER NOT NULL DEFAULT 0
    CHECK (achievement_generation >= 0),
  achievement_generation_started_at INTEGER NOT NULL
    DEFAULT (unixepoch()),
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE goal_stage (
  goal_id INTEGER NOT NULL REFERENCES goal(id) ON DELETE CASCADE,
  stage_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  PRIMARY KEY (goal_id, stage_id)
);

CREATE TABLE task (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  purpose TEXT NOT NULL DEFAULT '',
  scope TEXT NOT NULL DEFAULT '',
  exclusions TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT '',
  completion_evidence TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (
      status IN (
        'pending', 'active', 'completed', 'blocked', 'cancelled'
      )
    ),
  priority INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  completed_at INTEGER,
  updated_at INTEGER NOT NULL,
  CHECK (
    started_at IS NULL
    OR (
      substantive(purpose)
      AND substantive(scope)
      AND substantive(exclusions)
      AND substantive(result)
      AND substantive(completion_evidence)
    )
  ),
  CHECK (status <> 'active' OR started_at IS NOT NULL),
  CHECK (status <> 'active' OR stage_id IS NOT NULL),
  CHECK (status <> 'completed' OR started_at IS NOT NULL),
  CHECK (
    (status = 'completed' AND completed_at IS NOT NULL)
    OR (status <> 'completed' AND completed_at IS NULL)
  )
);

CREATE TABLE project_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  summary TEXT NOT NULL DEFAULT '',
  next_action TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL,
  revision INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE stage_dependency (
  stage_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  dependency_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  PRIMARY KEY (stage_id, dependency_id),
  CHECK (stage_id <> dependency_id)
);

CREATE TABLE task_tag (
  task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  tag TEXT NOT NULL CHECK (substantive(tag)),
  PRIMARY KEY (task_id, tag)
);

CREATE TABLE task_log (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
  occurred_at INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'note',
  message TEXT NOT NULL
);

CREATE TABLE decision (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  summary TEXT NOT NULL,
  rationale TEXT NOT NULL DEFAULT '',
  alternatives TEXT NOT NULL DEFAULT '',
  consequences TEXT NOT NULL DEFAULT '',
  decided_at INTEGER NOT NULL,
  context_status TEXT NOT NULL DEFAULT 'complete'
    CHECK (context_status IN ('complete', 'legacy-unresolved'))
);

CREATE TABLE blocker (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  description TEXT NOT NULL,
  impact TEXT NOT NULL DEFAULT '',
  attempts TEXT NOT NULL DEFAULT '',
  required TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'resolved', 'withdrawn')),
  opened_at INTEGER NOT NULL,
  resolved_at INTEGER,
  resolution TEXT NOT NULL DEFAULT '',
  CHECK (
    (status = 'open' AND resolved_at IS NULL AND resolution = '')
    OR (
      status <> 'open'
      AND resolved_at IS NOT NULL
      AND substantive(resolution)
    )
  )
);

CREATE TABLE evidence (
  id INTEGER PRIMARY KEY,
  goal_id INTEGER REFERENCES goal(id) ON DELETE SET NULL,
  stage_id INTEGER REFERENCES stage(id) ON DELETE SET NULL,
  task_id INTEGER REFERENCES task(id) ON DELETE SET NULL,
  claim TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  result TEXT NOT NULL DEFAULT '',
  captured_at INTEGER NOT NULL,
  context_status TEXT NOT NULL DEFAULT 'complete'
    CHECK (context_status IN ('complete', 'legacy-unresolved')),
  claim_status TEXT NOT NULL DEFAULT 'substantive'
    CHECK (claim_status IN ('substantive', 'legacy-blank')),
  stage_generation INTEGER CHECK (stage_generation >= 0),
  CHECK (
    (stage_id IS NULL AND stage_generation IS NULL)
    OR (stage_id IS NOT NULL AND stage_generation IS NOT NULL)
  )
);

CREATE TABLE stage_achievement (
  id INTEGER PRIMARY KEY,
  stage_id INTEGER NOT NULL REFERENCES stage(id) ON DELETE CASCADE,
  evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
  achieved_at INTEGER NOT NULL,
  invalidated_at INTEGER,
  stage_generation INTEGER NOT NULL DEFAULT 0
    CHECK (stage_generation >= 0)
);

CREATE TABLE legacy_lifecycle (
  id INTEGER PRIMARY KEY,
  source_schema_version INTEGER NOT NULL CHECK (
    source_schema_version IN (1, 2, 3, 4, 5)
  ),
  entity_kind TEXT NOT NULL CHECK (
    entity_kind IN ('project', 'goal', 'stage', 'task')
  ),
  entity_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  started_at INTEGER,
  achieved_at INTEGER,
  completed_at INTEGER,
  was_selected INTEGER NOT NULL CHECK (was_selected IN (0, 1)),
  migrated_at INTEGER NOT NULL,
  UNIQUE (source_schema_version, entity_kind, entity_id)
);

CREATE INDEX task_stage_index ON task(stage_id);
CREATE INDEX task_goal_index ON task(goal_id);
CREATE INDEX task_status_index ON task(status);
CREATE INDEX task_tag_index ON task_tag(tag);
CREATE INDEX task_log_task_time_index
  ON task_log(task_id, occurred_at DESC);
CREATE INDEX blocker_status_index ON blocker(status);
CREATE INDEX blocker_goal_index ON blocker(goal_id);
CREATE INDEX evidence_goal_index ON evidence(goal_id);
CREATE INDEX evidence_stage_index ON evidence(stage_id);
CREATE INDEX goal_status_index ON goal(status);
CREATE INDEX goal_stage_stage_index ON goal_stage(stage_id);
CREATE UNIQUE INDEX one_active_goal_index
  ON goal(status) WHERE status = 'active';
CREATE UNIQUE INDEX one_active_task_index
  ON task(status) WHERE status = 'active';
CREATE UNIQUE INDEX one_valid_stage_achievement_index
  ON stage_achievement(stage_id) WHERE invalidated_at IS NULL;
"""


LIFECYCLE_TRIGGER_SQL = f"""
CREATE TRIGGER project_charter_update
BEFORE UPDATE OF objective, scope, non_goals, constraints_text, acceptance
ON project
WHEN NEW.charter_context_status <> 'legacy-incomplete'
AND (
  NOT substantive(NEW.objective)
  OR NOT substantive(NEW.scope)
  OR NOT substantive(NEW.non_goals)
  OR NOT substantive(NEW.constraints_text)
  OR NOT substantive(NEW.acceptance)
) AND (
  EXISTS (SELECT 1 FROM task WHERE started_at IS NOT NULL)
  OR EXISTS (
    SELECT 1 FROM stage_achievement WHERE invalidated_at IS NULL
  )
)
BEGIN
  SELECT RAISE(ABORT, 'started work requires a complete project charter');
END;

CREATE TRIGGER project_charter_active_task
BEFORE UPDATE OF objective, scope, non_goals, constraints_text, acceptance
ON project
WHEN OLD.charter_context_status = 'current'
AND (
  NEW.objective IS NOT OLD.objective
  OR NEW.scope IS NOT OLD.scope
  OR NEW.non_goals IS NOT OLD.non_goals
  OR NEW.constraints_text IS NOT OLD.constraints_text
  OR NEW.acceptance IS NOT OLD.acceptance
) AND (
  EXISTS (SELECT 1 FROM task WHERE status = 'active')
  OR EXISTS (SELECT 1 FROM goal WHERE status IN ('active', 'blocked'))
)
AND EXISTS (
  SELECT 1 FROM task WHERE started_at IS NOT NULL
)
BEGIN
  SELECT RAISE(
    ABORT, {PROJECT_CHARTER_STABLE_ERROR!r}
  );
END;

CREATE TRIGGER preserve_project_charter
BEFORE UPDATE OF objective, scope, non_goals, constraints_text, acceptance
ON project
WHEN OLD.charter_context_status = 'current'
AND (
  NEW.objective IS NOT OLD.objective
  OR NEW.scope IS NOT OLD.scope
  OR NEW.non_goals IS NOT OLD.non_goals
  OR NEW.constraints_text IS NOT OLD.constraints_text
  OR NEW.acceptance IS NOT OLD.acceptance
) AND EXISTS (SELECT 1 FROM task WHERE started_at IS NOT NULL)
BEGIN
  INSERT INTO project_charter_history
    (objective, scope, non_goals, constraints_text, acceptance,
     replaced_at)
  VALUES (
    OLD.objective,
    OLD.scope,
    OLD.non_goals,
    OLD.constraints_text,
    OLD.acceptance,
    CAST(strftime('%s', 'now') AS INTEGER)
  );
END;

CREATE TRIGGER invalidate_stage_achievement_project_contract
AFTER UPDATE OF objective, scope, non_goals, constraints_text, acceptance
ON project
WHEN OLD.charter_context_status = 'current'
AND (
  NEW.objective IS NOT OLD.objective
  OR NEW.scope IS NOT OLD.scope
  OR NEW.non_goals IS NOT OLD.non_goals
  OR NEW.constraints_text IS NOT OLD.constraints_text
  OR NEW.acceptance IS NOT OLD.acceptance
) AND EXISTS (
  SELECT 1 FROM stage_achievement WHERE invalidated_at IS NULL
)
BEGIN
  UPDATE stage
  SET achievement_generation = achievement_generation + 1,
    achievement_generation_started_at = MAX(
      (
        SELECT achieved_at FROM stage_achievement
        WHERE stage_id = stage.id AND invalidated_at IS NULL
      ),
      CAST(strftime('%s', 'now') AS INTEGER)
    )
  WHERE EXISTS (
    SELECT 1 FROM stage_achievement
    WHERE stage_id = stage.id AND invalidated_at IS NULL
  );
END;

CREATE TRIGGER project_charter_context_update
BEFORE UPDATE OF charter_context_status ON project
WHEN (
  OLD.charter_context_status = 'current'
  AND NEW.charter_context_status <> 'current'
) OR (
  OLD.charter_context_status = 'legacy-incomplete'
  AND NEW.charter_context_status = 'current'
  AND (
    NOT substantive(NEW.objective)
    OR NOT substantive(NEW.scope)
    OR NOT substantive(NEW.non_goals)
    OR NOT substantive(NEW.constraints_text)
    OR NOT substantive(NEW.acceptance)
  )
)
BEGIN
  SELECT RAISE(ABORT, 'invalid project charter context transition');
END;

CREATE TRIGGER complete_legacy_project_charter
AFTER UPDATE OF objective, scope, non_goals, constraints_text, acceptance
ON project
WHEN NEW.charter_context_status = 'legacy-incomplete'
  AND substantive(NEW.objective)
  AND substantive(NEW.scope)
  AND substantive(NEW.non_goals)
  AND substantive(NEW.constraints_text)
  AND substantive(NEW.acceptance)
BEGIN
  UPDATE project SET charter_context_status = 'current'
  WHERE id = NEW.id;
END;

CREATE TRIGGER stage_text_insert
BEFORE INSERT ON stage
WHEN NOT substantive(NEW.name) OR NOT substantive(NEW.outcome)
BEGIN
  SELECT RAISE(ABORT, 'stage name and outcome must contain text');
END;

CREATE TRIGGER stage_text_update
BEFORE UPDATE OF name, outcome ON stage
WHEN NOT substantive(NEW.name) OR NOT substantive(NEW.outcome)
BEGIN
  SELECT RAISE(ABORT, 'stage name and outcome must contain text');
END;

CREATE TRIGGER stage_generation_insert
BEFORE INSERT ON stage
WHEN NEW.achievement_generation <> 0
  OR NEW.achievement_generation_started_at <>
    CAST(strftime('%s', 'now') AS INTEGER)
BEGIN
  SELECT RAISE(ABORT, 'new stage must begin its first generation now');
END;

CREATE TRIGGER task_title_insert
BEFORE INSERT ON task
WHEN NOT substantive(NEW.title)
BEGIN
  SELECT RAISE(ABORT, 'task title must contain text');
END;

CREATE TRIGGER task_title_update
BEFORE UPDATE OF title ON task
WHEN NOT substantive(NEW.title)
BEGIN
  SELECT RAISE(ABORT, 'task title must contain text');
END;

CREATE TRIGGER task_initial_status
BEFORE INSERT ON task
WHEN NEW.status <> 'pending' OR NEW.started_at IS NOT NULL
BEGIN
  SELECT RAISE(ABORT, 'new task is not unstarted and pending');
END;

CREATE TRIGGER task_status_transition
BEFORE UPDATE OF status ON task
WHEN NEW.status <> OLD.status AND NOT (
  (OLD.status = 'pending'
    AND NEW.status IN ('active', 'blocked', 'cancelled'))
  OR (OLD.status = 'active'
    AND NEW.status IN ('completed', 'blocked', 'cancelled'))
  OR (OLD.status = 'blocked' AND NEW.status IN ('pending', 'cancelled'))
  OR (OLD.status = 'completed' AND NEW.status = 'pending')
  OR (OLD.status = 'cancelled' AND NEW.status = 'pending')
)
BEGIN
  SELECT RAISE(ABORT, 'invalid task status transition');
END;

CREATE TRIGGER blocked_task_insert
BEFORE INSERT ON task
WHEN NEW.status = 'blocked' AND NOT EXISTS (
  SELECT 1 FROM blocker WHERE task_id = NEW.id AND status = 'open'
)
BEGIN
  SELECT RAISE(ABORT, 'blocked task has no open blocker');
END;

CREATE TRIGGER blocked_task_update
BEFORE UPDATE OF status ON task
WHEN NEW.status = 'blocked' AND NOT EXISTS (
  SELECT 1 FROM blocker WHERE task_id = NEW.id AND status = 'open'
)
BEGIN
  SELECT RAISE(ABORT, 'blocked task has no open blocker');
END;

CREATE TRIGGER cancelled_task_update
BEFORE UPDATE OF status ON task
WHEN NEW.status = 'cancelled' AND EXISTS (
  SELECT 1 FROM blocker WHERE task_id = NEW.id AND status = 'open'
)
BEGIN
  SELECT RAISE(ABORT, 'cancelled task has an open blocker');
END;

CREATE TRIGGER pending_task_update
BEFORE UPDATE OF status ON task
WHEN NEW.status = 'pending' AND EXISTS (
  SELECT 1 FROM blocker WHERE task_id = NEW.id AND status = 'open'
)
BEGIN
  SELECT RAISE(ABORT, 'pending task has an open blocker');
END;

CREATE TRIGGER completed_task_update
BEFORE UPDATE OF status, started_at ON task
WHEN NEW.status = 'completed' AND NEW.started_at IS NULL
BEGIN
  SELECT RAISE(ABORT, 'completed task has no start time');
END;

CREATE TRIGGER task_start_time_valid
BEFORE UPDATE OF started_at ON task
WHEN NEW.started_at IS NOT NULL AND (
  NEW.started_at <= 0
  OR NEW.started_at > CAST(strftime('%s', 'now') AS INTEGER)
)
BEGIN
  SELECT RAISE(ABORT, {TASK_START_TIME_ERROR!r});
END;

CREATE TRIGGER started_task_stage_update
BEFORE UPDATE OF stage_id ON task
WHEN OLD.started_at IS NOT NULL
  AND OLD.stage_id IS NOT NULL
  AND NEW.stage_id IS NULL
BEGIN
  SELECT RAISE(ABORT, 'started task cannot lose its stage relationship');
END;

CREATE TRIGGER started_task_time_immutable
BEFORE UPDATE OF started_at ON task
WHEN OLD.started_at IS NOT NULL
  AND NEW.started_at IS NOT OLD.started_at
BEGIN
  SELECT RAISE(ABORT, 'task start time is immutable');
END;

CREATE TRIGGER task_start_transition
BEFORE UPDATE OF started_at ON task
WHEN OLD.started_at IS NULL
  AND NEW.started_at IS NOT NULL
  AND NEW.status <> 'active'
BEGIN
  SELECT RAISE(ABORT, 'task start time requires activation');
END;

CREATE TRIGGER completed_task_time_immutable
BEFORE UPDATE OF completed_at ON task
WHEN OLD.status = 'completed'
  AND NEW.status = 'completed'
  AND NEW.completed_at IS NOT OLD.completed_at
BEGIN
  SELECT RAISE(ABORT, 'completed task time is immutable');
END;

CREATE TRIGGER task_completion_time_valid
BEFORE UPDATE OF status, completed_at ON task
WHEN NEW.status = 'completed' AND (
  NEW.completed_at IS NULL
  OR NEW.completed_at < NEW.started_at
  OR NEW.completed_at > CAST(strftime('%s', 'now') AS INTEGER)
)
BEGIN
  SELECT RAISE(
    ABORT, {TASK_COMPLETION_TIME_ERROR!r}
  );
END;

CREATE TRIGGER task_goal_stage_insert
BEFORE INSERT ON task
WHEN NEW.goal_id IS NOT NULL AND NEW.stage_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM goal_stage
    WHERE goal_id = NEW.goal_id AND stage_id = NEW.stage_id
  )
BEGIN
  SELECT RAISE(ABORT, 'task stage is not linked to task goal');
END;

CREATE TRIGGER task_goal_stage_update
BEFORE UPDATE OF goal_id, stage_id ON task
WHEN NEW.goal_id IS NOT NULL AND NEW.stage_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM goal_stage
    WHERE goal_id = NEW.goal_id AND stage_id = NEW.stage_id
  )
BEGIN
  SELECT RAISE(ABORT, 'task stage is not linked to task goal');
END;

CREATE TRIGGER open_task_blocker_context
BEFORE UPDATE OF goal_id, stage_id ON task
WHEN EXISTS (
  SELECT 1 FROM blocker
  WHERE task_id = OLD.id AND status = 'open'
    AND (
      (stage_id IS NOT NULL AND stage_id IS NOT NEW.stage_id)
      OR (goal_id IS NOT NULL AND goal_id IS NOT NEW.goal_id)
    )
)
BEGIN
  SELECT RAISE(ABORT, 'task update conflicts with open blocker context');
END;

CREATE TRIGGER active_task_insert
BEFORE INSERT ON task
WHEN NEW.status = 'active'
BEGIN
  SELECT CASE WHEN NOT substantive(NEW.title) THEN RAISE(
    ABORT, 'active task has no substantive title'
  ) END;
  SELECT CASE WHEN NEW.stage_id IS NULL THEN RAISE(
    ABORT, 'active task has no stage'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM project
    WHERE NOT substantive(objective)
      OR NOT substantive(scope)
      OR NOT substantive(non_goals)
      OR NOT substantive(constraints_text)
      OR NOT substantive(acceptance)
  ) THEN RAISE(
    ABORT, 'active task requires a complete project charter'
  ) END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM stage
    WHERE id = NEW.stage_id
      AND substantive(name)
      AND substantive(outcome)
  ) THEN RAISE(
    ABORT, 'active task requires a complete stage contract'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM blocker
    WHERE task_id = NEW.id AND status = 'open'
  ) THEN RAISE(ABORT, 'active task has an open blocker') END;
  SELECT CASE WHEN (
    (NEW.goal_id IS NULL AND EXISTS (
      SELECT 1 FROM goal WHERE status = 'active'
    ))
    OR (NEW.goal_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM goal
      WHERE id = NEW.goal_id AND status = 'active'
    ))
  ) THEN RAISE(ABORT, 'active task does not match the active goal') END;
  SELECT CASE WHEN NEW.stage_id IS NOT NULL AND EXISTS (
    SELECT 1
    FROM stage_dependency
    LEFT JOIN stage_achievement
      ON stage_achievement.stage_id = stage_dependency.dependency_id
      AND stage_achievement.invalidated_at IS NULL
    WHERE stage_dependency.stage_id = NEW.stage_id
      AND stage_achievement.id IS NULL
  ) THEN RAISE(
    ABORT, 'active task has an unachieved stage dependency'
  ) END;
END;

CREATE TRIGGER active_task_update
BEFORE UPDATE OF status, goal_id, stage_id ON task
WHEN NEW.status = 'active'
BEGIN
  SELECT CASE WHEN NOT substantive(NEW.title) THEN RAISE(
    ABORT, 'active task has no substantive title'
  ) END;
  SELECT CASE WHEN NEW.stage_id IS NULL THEN RAISE(
    ABORT, 'active task has no stage'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM project
    WHERE NOT substantive(objective)
      OR NOT substantive(scope)
      OR NOT substantive(non_goals)
      OR NOT substantive(constraints_text)
      OR NOT substantive(acceptance)
  ) THEN RAISE(
    ABORT, 'active task requires a complete project charter'
  ) END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM stage
    WHERE id = NEW.stage_id
      AND substantive(name)
      AND substantive(outcome)
  ) THEN RAISE(
    ABORT, 'active task requires a complete stage contract'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM blocker
    WHERE task_id = NEW.id AND status = 'open'
  ) THEN RAISE(ABORT, 'active task has an open blocker') END;
  SELECT CASE WHEN (
    (NEW.goal_id IS NULL AND EXISTS (
      SELECT 1 FROM goal WHERE status = 'active'
    ))
    OR (NEW.goal_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM goal
      WHERE id = NEW.goal_id AND status = 'active'
    ))
  ) THEN RAISE(ABORT, 'active task does not match the active goal') END;
  SELECT CASE WHEN NEW.stage_id IS NOT NULL AND EXISTS (
    SELECT 1
    FROM stage_dependency
    LEFT JOIN stage_achievement
      ON stage_achievement.stage_id = stage_dependency.dependency_id
      AND stage_achievement.invalidated_at IS NULL
    WHERE stage_dependency.stage_id = NEW.stage_id
      AND stage_achievement.id IS NULL
  ) THEN RAISE(
    ABORT, 'active task has an unachieved stage dependency'
  ) END;
END;

CREATE TRIGGER active_goal_update
BEFORE UPDATE OF status, started_at, ever_activated ON goal
WHEN NEW.status = 'active'
BEGIN
  SELECT CASE WHEN NEW.started_at <= 0 THEN RAISE(
    ABORT, 'active goal has no start time'
  ) END;
  SELECT CASE WHEN NEW.started_at > CAST(strftime('%s', 'now') AS INTEGER)
    THEN RAISE(ABORT, 'active goal starts in the future') END;
  SELECT CASE WHEN NEW.ever_activated <> 1 THEN RAISE(
    ABORT, 'active goal has no activation history'
  ) END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM goal_stage WHERE goal_id = NEW.id
  ) THEN RAISE(ABORT, 'active goal has no stage') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM blocker
    WHERE goal_id = NEW.id AND task_id IS NULL AND status = 'open'
  ) THEN RAISE(ABORT, 'active goal has an open blocker') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM task
    WHERE status = 'active' AND goal_id IS NOT NEW.id
  ) THEN RAISE(ABORT, 'active goal does not match the active task') END;
END;

CREATE TRIGGER goal_text_immutable
BEFORE UPDATE OF text ON goal
WHEN NEW.text IS NOT OLD.text
BEGIN
  SELECT RAISE(ABORT, 'goal text is immutable');
END;

CREATE TRIGGER goal_initial_status
BEFORE INSERT ON goal
WHEN NEW.status <> 'cancelled'
  OR NEW.started_at <> 0
  OR NEW.ever_activated <> 0
BEGIN
  SELECT RAISE(ABORT, 'new goal is not in construction state');
END;

CREATE TRIGGER goal_status_transition
BEFORE UPDATE OF status, ever_activated ON goal
WHEN (
  NEW.status <> OLD.status
  OR NEW.ever_activated IS NOT OLD.ever_activated
) AND NOT (
  (OLD.status = 'cancelled'
    AND OLD.ever_activated = 0
    AND NEW.status = 'active'
    AND NEW.ever_activated = 1)
  OR (OLD.status = 'active'
    AND OLD.ever_activated = 1
    AND NEW.status IN ('blocked', 'achieved', 'cancelled')
    AND NEW.ever_activated = 1)
  OR (OLD.status = 'blocked'
    AND OLD.ever_activated = 1
    AND NEW.status IN ('active', 'cancelled')
    AND NEW.ever_activated = 1)
)
BEGIN
  SELECT RAISE(ABORT, 'invalid goal status transition');
END;

CREATE TRIGGER blocked_goal_update
BEFORE UPDATE OF status ON goal
WHEN NEW.status = 'blocked' AND NOT EXISTS (
  SELECT 1 FROM blocker
  WHERE goal_id = NEW.id AND task_id IS NULL AND status = 'open'
)
BEGIN
  SELECT RAISE(ABORT, 'blocked goal has no open blocker');
END;

CREATE TRIGGER cancelled_goal_update
BEFORE UPDATE OF status ON goal
WHEN NEW.status = 'cancelled' AND EXISTS (
  SELECT 1 FROM blocker
  WHERE goal_id = NEW.id AND task_id IS NULL AND status = 'open'
)
BEGIN
  SELECT RAISE(ABORT, 'cancelled goal has an open blocker');
END;

CREATE TRIGGER achieved_goal_update
BEFORE UPDATE OF status, achieved_at ON goal
WHEN NEW.status = 'achieved' AND (
  EXISTS (
    SELECT 1 FROM blocker
    WHERE goal_id = NEW.id AND task_id IS NULL AND status = 'open'
  )
  OR NOT EXISTS (
    SELECT 1 FROM evidence
    WHERE goal_id = NEW.id
      AND claim_status = 'substantive'
      AND substantive(claim)
  )
  OR EXISTS (
    SELECT 1 FROM evidence
    WHERE goal_id = NEW.id
      AND (
        claim_status <> 'substantive'
        OR
        NOT substantive(claim)
        OR captured_at > NEW.achieved_at
      )
  )
  OR NEW.achieved_at > CAST(strftime('%s', 'now') AS INTEGER)
  OR NEW.achieved_at < NEW.started_at
)
BEGIN
  SELECT RAISE(ABORT, 'goal achievement lacks required evidence');
END;

CREATE TRIGGER achieved_goal_lifecycle_immutable
BEFORE UPDATE OF started_at, achieved_at ON goal
WHEN OLD.status = 'achieved' AND (
  NEW.started_at IS NOT OLD.started_at
  OR NEW.achieved_at IS NOT OLD.achieved_at
)
BEGIN
  SELECT RAISE(ABORT, 'achieved goal lifecycle is immutable');
END;

CREATE TRIGGER started_goal_time_immutable
BEFORE UPDATE OF started_at ON goal
WHEN OLD.started_at > 0 AND NEW.started_at IS NOT OLD.started_at
BEGIN
  SELECT RAISE(ABORT, 'goal start time is immutable');
END;

CREATE TRIGGER goal_start_transition
BEFORE UPDATE OF started_at ON goal
WHEN OLD.started_at = 0
  AND NEW.started_at IS NOT OLD.started_at
  AND NEW.status <> 'active'
BEGIN
  SELECT RAISE(ABORT, 'goal start time requires activation');
END;

CREATE TRIGGER active_goal_exit
BEFORE UPDATE OF status ON goal
WHEN OLD.status = 'active' AND NEW.status <> 'active'
  AND EXISTS (
    SELECT 1 FROM task
    WHERE status = 'active' AND goal_id = OLD.id
  )
BEGIN
  SELECT RAISE(ABORT, 'active goal has an active task');
END;

CREATE TRIGGER goal_stage_insert
BEFORE INSERT ON goal_stage
WHEN NOT EXISTS (
  SELECT 1 FROM goal
  WHERE id = NEW.goal_id
    AND status = 'cancelled'
    AND started_at = 0
    AND ever_activated = 0
)
BEGIN
  SELECT RAISE(ABORT, 'goal-stage scope is already fixed');
END;

CREATE TRIGGER goal_stage_delete
BEFORE DELETE ON goal_stage
WHEN NOT EXISTS (
  SELECT 1 FROM goal
  WHERE id = OLD.goal_id
    AND status = 'cancelled'
    AND started_at = 0
    AND ever_activated = 0
)
BEGIN
  SELECT RAISE(ABORT, 'goal-stage scope is already fixed');
END;

CREATE TRIGGER goal_stage_update
BEFORE UPDATE ON goal_stage
BEGIN
  SELECT RAISE(ABORT, 'goal-stage relationships cannot be updated');
END;

CREATE TRIGGER stage_dependency_cycle
BEFORE INSERT ON stage_dependency
WHEN EXISTS (
  WITH RECURSIVE dependencies(id) AS (
    SELECT NEW.dependency_id
    UNION
    SELECT stage_dependency.dependency_id
    FROM stage_dependency
    JOIN dependencies ON dependencies.id = stage_dependency.stage_id
  )
  SELECT 1 FROM dependencies WHERE id = NEW.stage_id
)
BEGIN
  SELECT RAISE(ABORT, 'stage dependency would create a cycle');
END;

CREATE TRIGGER stage_dependency_active_task
BEFORE INSERT ON stage_dependency
WHEN EXISTS (
  SELECT 1 FROM task
  WHERE stage_id = NEW.stage_id AND status = 'active'
) AND NOT EXISTS (
  SELECT 1 FROM stage_achievement
  WHERE stage_id = NEW.dependency_id AND invalidated_at IS NULL
)
BEGIN
  SELECT RAISE(ABORT, 'active task would have an unachieved dependency');
END;

CREATE TRIGGER stage_dependency_update
BEFORE UPDATE ON stage_dependency
BEGIN
  SELECT RAISE(ABORT, 'stage dependencies cannot be updated');
END;

CREATE TRIGGER stage_dependency_active_task_delete
BEFORE DELETE ON stage_dependency
WHEN EXISTS (
  SELECT 1 FROM task
  WHERE stage_id = OLD.stage_id AND status = 'active'
)
BEGIN
  SELECT RAISE(ABORT, 'active task requires its stage dependencies');
END;

CREATE TRIGGER stage_generation_update
BEFORE UPDATE OF achievement_generation,
  achievement_generation_started_at ON stage
WHEN NOT (
  NEW.achievement_generation = OLD.achievement_generation + 1
  AND NEW.achievement_generation_started_at = MAX(
    (
      SELECT achieved_at FROM stage_achievement
      WHERE stage_id = OLD.id AND invalidated_at IS NULL
    ),
    CAST(strftime('%s', 'now') AS INTEGER)
  )
  AND EXISTS (
    SELECT 1 FROM stage_achievement
    WHERE stage_id = OLD.id AND invalidated_at IS NULL
  )
)
BEGIN
  SELECT RAISE(ABORT, 'stage achievement generation is controlled');
END;

CREATE TRIGGER apply_stage_generation
AFTER UPDATE OF achievement_generation ON stage
WHEN NEW.achievement_generation = OLD.achievement_generation + 1
BEGIN
  UPDATE stage_achievement
  SET invalidated_at = NEW.achievement_generation_started_at
  WHERE stage_id = NEW.id AND invalidated_at IS NULL;
END;

CREATE TRIGGER invalidate_stage_achievement_contract
AFTER UPDATE OF outcome, exit_evidence ON stage
WHEN (
  NEW.outcome IS NOT OLD.outcome
  OR NEW.exit_evidence IS NOT OLD.exit_evidence
) AND EXISTS (
  SELECT 1 FROM stage_achievement
  WHERE stage_id = NEW.id AND invalidated_at IS NULL
)
BEGIN
  UPDATE stage
  SET achievement_generation = achievement_generation + 1,
    achievement_generation_started_at = MAX(
      (
        SELECT achieved_at FROM stage_achievement
        WHERE stage_id = NEW.id AND invalidated_at IS NULL
      ),
      CAST(strftime('%s', 'now') AS INTEGER)
    )
  WHERE id = NEW.id;
END;

CREATE TRIGGER stage_achievement_insert
BEFORE INSERT ON stage_achievement
BEGIN
  SELECT CASE WHEN NEW.invalidated_at IS NOT NULL THEN RAISE(
    ABORT, 'new stage achievement is already invalidated'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM project
    WHERE NOT substantive(objective)
      OR NOT substantive(scope)
      OR NOT substantive(non_goals)
      OR NOT substantive(constraints_text)
      OR NOT substantive(acceptance)
  ) THEN RAISE(
    ABORT, 'stage achievement requires a complete project charter'
  ) END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM stage
    WHERE id = NEW.stage_id
      AND substantive(name)
      AND substantive(outcome)
  ) THEN RAISE(ABORT, 'stage has an incomplete achievement contract') END;
  SELECT CASE WHEN NOT substantive((
    SELECT exit_evidence FROM stage WHERE id = NEW.stage_id
  )) THEN RAISE(ABORT, 'stage has no exit-evidence requirement') END;
  SELECT CASE WHEN NEW.stage_generation IS NOT (
    SELECT achievement_generation FROM stage WHERE id = NEW.stage_id
  ) THEN RAISE(ABORT, 'achievement has the wrong stage generation') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM evidence
    WHERE id = NEW.evidence_id
      AND stage_id = NEW.stage_id
  ) THEN RAISE(ABORT, 'achievement evidence does not belong to stage') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM evidence
    WHERE id = NEW.evidence_id
      AND claim_status = 'substantive'
      AND substantive(claim)
  ) THEN RAISE(ABORT, 'achievement evidence has no substantive claim') END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM stage_achievement
    WHERE stage_id = NEW.stage_id AND evidence_id = NEW.evidence_id
  ) THEN RAISE(
    ABORT, 'achievement evidence was already used for this stage'
  ) END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM evidence
    WHERE id = NEW.evidence_id
      AND stage_generation = NEW.stage_generation
  ) THEN RAISE(
    ABORT, 'achievement evidence predates the current stage generation'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM evidence
    WHERE id = NEW.evidence_id AND captured_at > NEW.achieved_at
  ) THEN RAISE(
    ABORT, 'achievement predates its evidence'
  ) END;
  SELECT CASE WHEN EXISTS (
    SELECT 1 FROM task
    WHERE stage_id = NEW.stage_id
      AND status = 'completed'
      AND completed_at > NEW.achieved_at
  ) THEN RAISE(
    ABORT, 'stage achievement predates completed task work'
  ) END;
  SELECT CASE WHEN NEW.achieved_at > CAST(strftime('%s', 'now') AS INTEGER)
    THEN RAISE(ABORT, 'stage achievement is in the future') END;
  SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM task
    WHERE stage_id = NEW.stage_id
      AND status = 'completed'
      AND substantive(title)
  ) OR EXISTS (
    SELECT 1 FROM task
    WHERE stage_id = NEW.stage_id
      AND status IN ('pending', 'active', 'blocked')
  ) THEN RAISE(ABORT, 'stage tasks do not establish achievement') END;
END;

CREATE TRIGGER stage_achievement_update
BEFORE UPDATE ON stage_achievement
WHEN NOT (
  OLD.invalidated_at IS NULL
  AND NEW.invalidated_at IS NOT NULL
  AND NEW.invalidated_at = MAX(
    OLD.achieved_at,
    CAST(strftime('%s', 'now') AS INTEGER)
  )
  AND NEW.invalidated_at >= OLD.achieved_at
  AND NEW.id IS OLD.id
  AND NEW.stage_id IS OLD.stage_id
  AND NEW.evidence_id IS OLD.evidence_id
  AND NEW.achieved_at IS OLD.achieved_at
  AND NEW.stage_generation IS OLD.stage_generation
  AND (
    SELECT achievement_generation FROM stage WHERE id = OLD.stage_id
  ) = OLD.stage_generation + 1
)
BEGIN
  SELECT RAISE(ABORT, 'stage achievement is immutable');
END;

CREATE TRIGGER stage_achievement_active_dependency
BEFORE UPDATE OF invalidated_at ON stage_achievement
WHEN OLD.invalidated_at IS NULL
  AND NEW.invalidated_at IS NOT NULL
  AND EXISTS (
    SELECT 1
    FROM stage_dependency
    JOIN task ON task.stage_id = stage_dependency.stage_id
    WHERE stage_dependency.dependency_id = OLD.stage_id
      AND task.status = 'active'
  )
BEGIN
  SELECT RAISE(
    ABORT, 'an active task depends on the stage achievement'
  );
END;

CREATE TRIGGER stage_achievement_delete
BEFORE DELETE ON stage_achievement
BEGIN
  SELECT RAISE(ABORT, 'stage achievement cannot be deleted');
END;

CREATE TRIGGER achievement_evidence_update
BEFORE UPDATE ON evidence
WHEN EXISTS (
  SELECT 1 FROM stage_achievement
  WHERE evidence_id = OLD.id
  UNION ALL
  SELECT 1 FROM goal
  WHERE id = OLD.goal_id AND status = 'achieved'
)
BEGIN
  SELECT RAISE(ABORT, 'achievement evidence is immutable');
END;

CREATE TRIGGER achievement_evidence_delete
BEFORE DELETE ON evidence
WHEN EXISTS (
  SELECT 1 FROM stage_achievement
  WHERE evidence_id = OLD.id
  UNION ALL
  SELECT 1 FROM goal
  WHERE id = OLD.goal_id AND status = 'achieved'
)
BEGIN
  SELECT RAISE(ABORT, 'achievement evidence cannot be deleted');
END;

CREATE TRIGGER achieved_goal_evidence_insert
BEFORE INSERT ON evidence
WHEN NEW.goal_id IS NOT NULL AND EXISTS (
  SELECT 1 FROM goal
  WHERE id = NEW.goal_id AND status = 'achieved'
)
BEGIN
  SELECT RAISE(ABORT, 'achieved goal evidence is fixed');
END;

CREATE TRIGGER achieved_goal_evidence_attach
BEFORE UPDATE OF goal_id ON evidence
WHEN NEW.goal_id IS NOT OLD.goal_id
  AND NEW.goal_id IS NOT NULL
  AND EXISTS (
  SELECT 1 FROM goal
  WHERE id = NEW.goal_id AND status = 'achieved'
)
BEGIN
  SELECT RAISE(ABORT, 'achieved goal evidence is fixed');
END;

CREATE TRIGGER invalidate_stage_achievement_task_insert
AFTER INSERT ON task
WHEN NEW.stage_id IS NOT NULL
BEGIN
  UPDATE stage
  SET achievement_generation = achievement_generation + 1,
    achievement_generation_started_at = MAX(
      (
        SELECT achieved_at FROM stage_achievement
        WHERE stage_id = NEW.stage_id AND invalidated_at IS NULL
      ),
      CAST(strftime('%s', 'now') AS INTEGER)
    )
  WHERE id = NEW.stage_id
    AND EXISTS (
      SELECT 1 FROM stage_achievement
      WHERE stage_id = NEW.stage_id AND invalidated_at IS NULL
    )
    AND (
      NOT EXISTS (
        SELECT 1 FROM task
        WHERE stage_id = NEW.stage_id AND status = 'completed'
      )
      OR EXISTS (
        SELECT 1 FROM task
        WHERE stage_id = NEW.stage_id
          AND status IN ('pending', 'active', 'blocked')
      )
    );
END;

CREATE TRIGGER invalidate_stage_achievement_task_update
AFTER UPDATE OF status, stage_id ON task
BEGIN
  UPDATE stage
  SET achievement_generation = achievement_generation + 1,
    achievement_generation_started_at = MAX(
      (
        SELECT achieved_at FROM stage_achievement
        WHERE stage_id = stage.id AND invalidated_at IS NULL
      ),
      CAST(strftime('%s', 'now') AS INTEGER)
    )
  WHERE id IN (OLD.stage_id, NEW.stage_id)
    AND EXISTS (
      SELECT 1 FROM stage_achievement
      WHERE stage_id = stage.id AND invalidated_at IS NULL
    )
    AND (
      NOT EXISTS (
        SELECT 1 FROM task
        WHERE stage_id = stage.id
          AND status = 'completed'
      )
      OR EXISTS (
        SELECT 1 FROM task
        WHERE stage_id = stage.id
          AND status IN ('pending', 'active', 'blocked')
      )
      OR EXISTS (
        SELECT 1 FROM task
        WHERE stage_id = stage.id
          AND status = 'completed'
          AND completed_at > (
            SELECT achieved_at FROM stage_achievement
            WHERE stage_id = stage.id AND invalidated_at IS NULL
          )
      )
    );
END;

CREATE TRIGGER invalidate_stage_achievement_task_delete
AFTER DELETE ON task
WHEN OLD.stage_id IS NOT NULL
BEGIN
  UPDATE stage
  SET achievement_generation = achievement_generation + 1,
    achievement_generation_started_at = MAX(
      (
        SELECT achieved_at FROM stage_achievement
        WHERE stage_id = OLD.stage_id AND invalidated_at IS NULL
      ),
      CAST(strftime('%s', 'now') AS INTEGER)
    )
  WHERE id = OLD.stage_id
    AND EXISTS (
      SELECT 1 FROM stage_achievement
      WHERE stage_id = OLD.stage_id AND invalidated_at IS NULL
    )
    AND NOT EXISTS (
      SELECT 1 FROM task
      WHERE stage_id = OLD.stage_id AND status = 'completed'
    );
END;

CREATE TRIGGER apply_open_blocker
AFTER INSERT ON blocker
WHEN NEW.status = 'open'
BEGIN
  UPDATE task
  SET status = 'blocked', completed_at = NULL,
    updated_at = NEW.opened_at
  WHERE id = NEW.task_id AND status IN ('pending', 'active');
  UPDATE goal
  SET status = 'blocked', status_reason = NEW.description,
    updated_at = NEW.opened_at
  WHERE NEW.task_id IS NULL AND id = NEW.goal_id AND status = 'active';
END;

CREATE TRIGGER blocker_relationship_insert
BEFORE INSERT ON blocker
WHEN (
  NEW.task_id IS NULL AND NEW.goal_id IS NULL
) OR (
  NEW.task_id IS NOT NULL AND (
    (NEW.stage_id IS NOT NULL AND NEW.stage_id IS NOT (
      SELECT stage_id FROM task WHERE id = NEW.task_id
    ))
    OR (NEW.goal_id IS NOT NULL AND NEW.goal_id IS NOT (
      SELECT goal_id FROM task WHERE id = NEW.task_id
    ))
  )
) OR (
  NEW.task_id IS NULL
  AND NEW.goal_id IS NOT NULL
  AND NEW.stage_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM goal_stage
    WHERE goal_id = NEW.goal_id AND stage_id = NEW.stage_id
  )
)
BEGIN
  SELECT RAISE(ABORT, 'blocker relationships are incoherent');
END;

CREATE TRIGGER decision_relationship_insert
BEFORE INSERT ON decision
WHEN NEW.context_status <> 'complete' OR (
  NEW.task_id IS NOT NULL AND (
    NEW.stage_id IS NOT (
      SELECT stage_id FROM task WHERE id = NEW.task_id
    )
    OR NEW.goal_id IS NOT (
      SELECT goal_id FROM task WHERE id = NEW.task_id
    )
  )
) OR (
  NEW.goal_id IS NOT NULL
  AND NEW.stage_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM goal_stage
    WHERE goal_id = NEW.goal_id AND stage_id = NEW.stage_id
  )
)
BEGIN
  SELECT RAISE(ABORT, 'decision relationships are incoherent');
END;

CREATE TRIGGER decision_relationship_update
BEFORE UPDATE OF goal_id, stage_id, task_id, context_status ON decision
WHEN NEW.goal_id IS NOT OLD.goal_id
  OR NEW.stage_id IS NOT OLD.stage_id
  OR NEW.task_id IS NOT OLD.task_id
  OR NEW.context_status IS NOT OLD.context_status
BEGIN
  SELECT RAISE(ABORT, 'decision relationships are immutable');
END;

CREATE TRIGGER evidence_relationship_insert
BEFORE INSERT ON evidence
WHEN NEW.context_status <> 'complete' OR (
  NEW.task_id IS NOT NULL AND (
    NEW.stage_id IS NOT (
      SELECT stage_id FROM task WHERE id = NEW.task_id
    )
    OR NEW.goal_id IS NOT (
      SELECT goal_id FROM task WHERE id = NEW.task_id
    )
  )
) OR (
  NEW.goal_id IS NOT NULL
  AND NEW.stage_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM goal_stage
    WHERE goal_id = NEW.goal_id AND stage_id = NEW.stage_id
  )
)
BEGIN
  SELECT RAISE(ABORT, 'evidence relationships are incoherent');
END;

CREATE TRIGGER evidence_relationship_update
BEFORE UPDATE OF goal_id, stage_id, task_id, context_status,
  claim_status, stage_generation ON evidence
WHEN NEW.goal_id IS NOT OLD.goal_id
  OR NEW.stage_id IS NOT OLD.stage_id
  OR NEW.task_id IS NOT OLD.task_id
  OR NEW.context_status IS NOT OLD.context_status
  OR NEW.claim_status IS NOT OLD.claim_status
  OR NEW.stage_generation IS NOT OLD.stage_generation
BEGIN
  SELECT RAISE(ABORT, 'evidence relationships are immutable');
END;

CREATE TRIGGER evidence_claim_insert
BEFORE INSERT ON evidence
WHEN NEW.claim_status <> 'substantive'
  OR NOT substantive(NEW.claim)
BEGIN
  SELECT RAISE(ABORT, 'evidence claim must contain text');
END;

CREATE TRIGGER evidence_capture_time_insert
BEFORE INSERT ON evidence
WHEN NEW.captured_at > CAST(strftime('%s', 'now') AS INTEGER)
BEGIN
  SELECT RAISE(ABORT, 'evidence capture time is in the future');
END;

CREATE TRIGGER evidence_claim_update
BEFORE UPDATE OF claim ON evidence
WHEN (
  OLD.claim_status = 'substantive' AND NOT substantive(NEW.claim)
) OR (
  OLD.claim_status = 'legacy-blank' AND NEW.claim IS NOT OLD.claim
)
BEGIN
  SELECT RAISE(
    ABORT, 'evidence claim is invalid or compatibility history'
  );
END;

CREATE TRIGGER evidence_capture_time_immutable
BEFORE UPDATE OF captured_at ON evidence
WHEN NEW.captured_at IS NOT OLD.captured_at
BEGIN
  SELECT RAISE(ABORT, 'evidence capture time is immutable');
END;

CREATE TRIGGER evidence_stage_generation_insert
BEFORE INSERT ON evidence
WHEN (
  NEW.stage_id IS NULL AND NEW.stage_generation IS NOT NULL
) OR (
  NEW.stage_id IS NOT NULL AND NEW.stage_generation IS NOT (
    SELECT achievement_generation FROM stage WHERE id = NEW.stage_id
  )
)
BEGIN
  SELECT RAISE(ABORT, 'evidence has the wrong stage generation');
END;

CREATE TRIGGER evidence_stage_generation_time_insert
BEFORE INSERT ON evidence
WHEN NEW.stage_id IS NOT NULL AND NEW.captured_at < (
  SELECT achievement_generation_started_at
  FROM stage WHERE id = NEW.stage_id
)
BEGIN
  SELECT RAISE(ABORT, 'evidence predates the current stage generation');
END;

CREATE TRIGGER open_blocker_target
BEFORE INSERT ON blocker
WHEN NEW.status = 'open' AND (
  (NEW.task_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM task
    WHERE id = NEW.task_id AND status IN ('completed', 'cancelled')
  ))
  OR (NEW.task_id IS NULL AND EXISTS (
    SELECT 1 FROM goal
    WHERE id = NEW.goal_id AND status IN ('achieved', 'cancelled')
  ))
)
BEGIN
  SELECT RAISE(ABORT, 'open blocker targets a terminal entity');
END;

CREATE TRIGGER blocker_initial_status
BEFORE INSERT ON blocker
WHEN NEW.status <> 'open'
BEGIN
  SELECT RAISE(ABORT, 'new blocker is not open');
END;

CREATE TRIGGER blocker_text_insert
BEFORE INSERT ON blocker
WHEN NOT substantive(NEW.description)
  OR NOT substantive(NEW.required)
BEGIN
  SELECT RAISE(ABORT, 'blocker description and requirement need text');
END;

CREATE TRIGGER blocker_text_update
BEFORE UPDATE OF description, required ON blocker
WHEN NEW.status = 'open' AND (
  NOT substantive(NEW.description)
  OR NOT substantive(NEW.required)
)
BEGIN
  SELECT RAISE(ABORT, 'blocker description and requirement need text');
END;

CREATE TRIGGER blocker_relationship_update
BEFORE UPDATE OF goal_id, stage_id, task_id ON blocker
WHEN NEW.goal_id IS NOT OLD.goal_id
  OR NEW.stage_id IS NOT OLD.stage_id
  OR NEW.task_id IS NOT OLD.task_id
BEGIN
  SELECT RAISE(ABORT, 'blocker relationships are immutable');
END;

CREATE TRIGGER blocker_status_transition
BEFORE UPDATE OF status, resolved_at, resolution ON blocker
WHEN NOT (
  OLD.status = 'open'
  AND NEW.status IN ('resolved', 'withdrawn')
  AND NEW.resolved_at IS NOT NULL
  AND substantive(NEW.resolution)
)
BEGIN
  SELECT RAISE(ABORT, 'invalid blocker status transition');
END;

CREATE TRIGGER release_resolved_blocker
AFTER UPDATE OF status ON blocker
WHEN OLD.status = 'open' AND NEW.status = 'resolved'
BEGIN
  UPDATE task
  SET status = 'pending',
    updated_at = COALESCE(NEW.resolved_at, updated_at)
  WHERE id = NEW.task_id AND status = 'blocked'
    AND NOT EXISTS (
      SELECT 1 FROM blocker
      WHERE task_id = NEW.task_id AND status = 'open'
    );
  UPDATE goal
  SET status = 'active', status_reason = '',
    updated_at = COALESCE(NEW.resolved_at, updated_at)
  WHERE NEW.task_id IS NULL AND id = NEW.goal_id AND status = 'blocked'
    AND NOT EXISTS (
      SELECT 1 FROM blocker
      WHERE goal_id = NEW.goal_id AND task_id IS NULL AND status = 'open'
    );
END;

CREATE TRIGGER release_withdrawn_blocker
AFTER UPDATE OF status ON blocker
WHEN OLD.status = 'open' AND NEW.status = 'withdrawn'
BEGIN
  UPDATE task
  SET status = 'cancelled', completed_at = NULL,
    updated_at = COALESCE(NEW.resolved_at, updated_at)
  WHERE id = NEW.task_id AND status = 'blocked'
    AND NOT EXISTS (
      SELECT 1 FROM blocker
      WHERE task_id = NEW.task_id AND status = 'open'
    );
  UPDATE goal
  SET status = 'cancelled', achieved_at = NULL,
    updated_at = COALESCE(NEW.resolved_at, updated_at)
  WHERE NEW.task_id IS NULL AND id = NEW.goal_id AND status = 'blocked'
    AND NOT EXISTS (
      SELECT 1 FROM blocker
      WHERE goal_id = NEW.goal_id AND task_id IS NULL AND status = 'open'
    );
END;

CREATE TRIGGER task_delete
BEFORE DELETE ON task
BEGIN
  SELECT RAISE(ABORT, 'task history cannot be deleted');
END;

CREATE TRIGGER goal_delete
BEFORE DELETE ON goal
BEGIN
  SELECT RAISE(ABORT, 'goal history cannot be deleted');
END;

CREATE TRIGGER stage_delete
BEFORE DELETE ON stage
BEGIN
  SELECT RAISE(ABORT, 'stage history cannot be deleted');
END;

CREATE TRIGGER project_delete
BEFORE DELETE ON project
BEGIN
  SELECT RAISE(ABORT, 'project charter cannot be deleted');
END;

CREATE TRIGGER project_name_update
BEFORE UPDATE OF name ON project
WHEN NEW.name IS NOT OLD.name
BEGIN
  SELECT RAISE(ABORT, 'project name is immutable');
END;

CREATE TRIGGER project_state_delete
BEFORE DELETE ON project_state
BEGIN
  SELECT RAISE(ABORT, 'project state cannot be deleted');
END;

CREATE TRIGGER project_charter_history_update
BEFORE UPDATE ON project_charter_history
BEGIN
  SELECT RAISE(ABORT, 'project charter history is immutable');
END;

CREATE TRIGGER project_charter_history_delete
BEFORE DELETE ON project_charter_history
BEGIN
  SELECT RAISE(ABORT, 'project charter history cannot be deleted');
END;

CREATE TRIGGER task_log_update
BEFORE UPDATE ON task_log
BEGIN
  SELECT RAISE(ABORT, 'task log is append-only');
END;

CREATE TRIGGER task_log_delete
BEFORE DELETE ON task_log
BEGIN
  SELECT RAISE(ABORT, 'task log is append-only');
END;

CREATE TRIGGER legacy_lifecycle_update
BEFORE UPDATE ON legacy_lifecycle
BEGIN
  SELECT RAISE(ABORT, 'legacy lifecycle history is immutable');
END;

CREATE TRIGGER legacy_lifecycle_insert
BEFORE INSERT ON legacy_lifecycle
BEGIN
  SELECT RAISE(ABORT, 'legacy lifecycle history does not accept inserts');
END;

CREATE TRIGGER legacy_lifecycle_delete
BEFORE DELETE ON legacy_lifecycle
BEGIN
  SELECT RAISE(ABORT, 'legacy lifecycle history cannot be deleted');
END;

CREATE TRIGGER retain_open_blocker
BEFORE DELETE ON blocker
WHEN OLD.status = 'open'
BEGIN
  SELECT RAISE(ABORT, 'open blocker must be resolved or withdrawn');
END;
"""


class ProjectError(Exception):
  pass


def repository_root():
  return Path(__file__).resolve().parent.parent


def current_time():
  return int(time.time())


def format_time(value):
  if value is None:
    return '-'
  return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _substantive(value):
  return bool(value and value.strip())


def _format_text(value, default='-'):
  if value is None or value == '':
    return default
  return json.dumps(str(value), ensure_ascii=False)[1:-1]


def _shell_quote(value):
  value = str(value)
  if not value:
    return "''"
  return ''.join(
    character
    if character.isascii()
    and (character.isalnum() or character in '_@%+=:,./-')
    else f'\\{character}'
    for character in value
  )


def _truncate_text(value, limit):
  rendered = ''
  prefix = ''
  for character in value:
    encoded = _format_text(character, '')
    if len(rendered) + len(encoded) + 1 > limit:
      break
    rendered += encoded
    prefix += character
  return prefix + '…'


def validate_project_name(name):
  if (
    not name
    or name in ('.', '..')
    or name.endswith(PROJECT_SUFFIX)
    or PROJECT_NAME_PATTERN.fullmatch(name) is None
    or not name.isprintable()
    or len(name) > MAX_PROJECT_NAME_LENGTH
  ):
    raise ProjectError(
      'Project names must be printable, non-empty single path components '
      f'of at most {MAX_PROJECT_NAME_LENGTH} characters without the '
      '.sqlite3 suffix.'
    )
  return name


def project_directory(root):
  return Path(root) / '.tmp'


def database_path(root, name):
  validate_project_name(name)
  return project_directory(root) / f'{name}{PROJECT_SUFFIX}'


def connect(path):
  connection = sqlite3.connect(path, timeout=5)
  connection.row_factory = sqlite3.Row
  connection.create_function(
    'substantive', 1, _substantive, deterministic=True
  )
  connection.execute('PRAGMA foreign_keys = ON')
  connection.execute('PRAGMA busy_timeout = 5000')
  return connection


def open_project(root, name):
  path = database_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project does not exist: {name}')
  connection = connect(path)
  try:
    _validate_project(connection, path)
    return connection
  except ProjectError:
    connection.close()
    raise


def _validate_project(connection, path):
  version = connection.execute('PRAGMA user_version').fetchone()[0]
  if version != SCHEMA_VERSION:
    raise ProjectError(
      f'Unsupported project schema version {version}; expected '
      f'{SCHEMA_VERSION}: {path}'
    )
  _validate_project_singletons(connection, path.stem)
  _validate_project_schema(connection)
  _validate_project_integrity(connection)
  _validate_current_lifecycle(connection)


def _validate_project_schema(connection):
  expected = _canonical_schema_definitions()
  canonical_tables = {name for (kind, name) in expected if kind == 'table'}
  for kind in ('table', 'index', 'trigger'):
    required = {
      name: definition
      for (object_kind, name), definition in expected.items()
      if object_kind == kind
    }
    rows = connection.execute(
      'SELECT name, tbl_name, sql FROM sqlite_master '
      'WHERE type = ? AND sql IS NOT NULL',
      (kind,),
    ).fetchall()
    present = {
      row['name']: _normalize_schema_definition(row['sql']) for row in rows
    }
    missing = sorted(set(required) - set(present))
    if missing:
      plural = 'indexes' if kind == 'index' else f'{kind}s'
      raise ProjectError(
        f'Project schema is incomplete; missing {plural}: '
        f'{", ".join(missing)}'
      )
    incompatible = sorted(
      name
      for name, definition in required.items()
      if present[name] != definition
    )
    if incompatible:
      plural = 'indexes' if kind == 'index' else f'{kind}s'
      raise ProjectError(
        f'Project schema has incompatible {plural}: '
        f'{", ".join(incompatible)}'
      )
    if kind == 'index':
      unexpected = sorted(
        row['name']
        for row in rows
        if row['name'] not in required
        and row['tbl_name'] in canonical_tables
      )
      if unexpected:
        raise ProjectError(
          'Project schema has unexpected indexes on canonical tables: '
          f'{", ".join(unexpected)}'
        )
    if kind == 'trigger':
      unexpected = sorted(set(present) - set(required))
      if unexpected:
        raise ProjectError(
          'Project schema has unexpected triggers: '
          f'{", ".join(unexpected)}'
        )


def _validate_project_integrity(connection):
  integrity = [
    row[0] for row in connection.execute('PRAGMA integrity_check')
  ]
  if integrity != ['ok']:
    raise ProjectError(
      f'Project database integrity check failed: {integrity[0]}'
    )
  violation = connection.execute('PRAGMA foreign_key_check').fetchone()
  if violation is not None:
    raise ProjectError(
      'Project has a foreign-key violation: '
      f'{violation[0]} row {violation[1]} references {violation[2]}'
    )


def _validate_project_singletons(connection, expected_name):
  try:
    project_rows = connection.execute(
      'SELECT name FROM project'
    ).fetchall()
    state_count = connection.execute(
      'SELECT count(*) FROM project_state'
    ).fetchone()[0]
  except sqlite3.Error as error:
    raise ProjectError(f'Project schema is incomplete: {error}') from error
  if len(project_rows) != 1:
    raise ProjectError(
      f'Project database must contain one project row; found '
      f'{len(project_rows)}'
    )
  if state_count != 1:
    raise ProjectError(
      f'Project database must contain one project-state row; found '
      f'{state_count}'
    )
  stored_name = project_rows[0]['name']
  if stored_name != expected_name:
    raise ProjectError(
      f'Project name {stored_name!r} does not match database address '
      f'{expected_name!r}'
    )


def _execute_sql(connection, script):
  statement = ''
  for line in script.splitlines(keepends=True):
    statement += line
    if sqlite3.complete_statement(statement):
      connection.execute(statement)
      statement = ''
  if statement.strip():
    raise ProjectError('Incomplete project schema SQL')


def _normalize_schema_definition(definition):
  return ' '.join(definition.strip().rstrip(';').split())


def _canonical_schema_definitions():
  global _SCHEMA_DEFINITIONS
  if _SCHEMA_DEFINITIONS is None:
    expected = sqlite3.connect(':memory:')
    expected.row_factory = sqlite3.Row
    expected.create_function(
      'substantive', 1, _substantive, deterministic=True
    )
    try:
      _execute_sql(expected, SCHEMA_SQL)
      _execute_sql(expected, LIFECYCLE_TRIGGER_SQL)
      _SCHEMA_DEFINITIONS = {
        (row['type'], row['name']): _normalize_schema_definition(
          row['sql']
        )
        for row in expected.execute(
          'SELECT type, name, sql FROM sqlite_master '
          "WHERE type IN ('table', 'index', 'trigger') "
          "AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"
        )
      }
    finally:
      expected.close()
  return _SCHEMA_DEFINITIONS


def _project_charter_complete(project):
  return all(
    _substantive(project[field])
    for field in (
      'objective',
      'scope',
      'non_goals',
      'constraints_text',
      'acceptance',
    )
  )


def _stage_contract_complete(stage):
  return _substantive(stage['name']) and _substantive(stage['outcome'])


def _validate_current_lifecycle(connection):
  for entity, table in (('goals', 'goal'), ('tasks', 'task')):
    active_count = connection.execute(
      f"SELECT count(*) FROM {table} WHERE status = 'active'"
    ).fetchone()[0]
    if active_count > 1:
      raise ProjectError(
        f'Project has multiple active {entity}: {active_count}'
      )
  incomplete_charter = connection.execute(
    """
    SELECT id
    FROM project
    WHERE (
      charter_context_status = 'current'
      AND (
        NOT substantive(objective)
        OR NOT substantive(scope)
        OR NOT substantive(non_goals)
        OR NOT substantive(constraints_text)
        OR NOT substantive(acceptance)
      )
      AND (
        EXISTS (SELECT 1 FROM task WHERE started_at IS NOT NULL)
        OR EXISTS (
          SELECT 1 FROM stage_achievement
          WHERE invalidated_at IS NULL
        )
      )
    ) OR (
      charter_context_status = 'legacy-incomplete'
      AND (
        (
          substantive(objective)
          AND substantive(scope)
          AND substantive(non_goals)
          AND substantive(constraints_text)
          AND substantive(acceptance)
        )
        OR NOT EXISTS (
          SELECT 1 FROM legacy_lifecycle
          WHERE entity_kind = 'project' AND entity_id = project.id
        )
        OR NOT EXISTS (
          SELECT 1 FROM task WHERE started_at IS NOT NULL
        )
        OR EXISTS (
          SELECT 1 FROM stage_achievement
          WHERE invalidated_at IS NULL
        )
      )
    )
    LIMIT 1
    """
  ).fetchone()
  if incomplete_charter is not None:
    raise ProjectError('Project has an incomplete post-execution charter')
  invalid_stage = connection.execute(
    """
    SELECT id
    FROM stage
    WHERE (
      (NOT substantive(name) OR NOT substantive(outcome))
      AND NOT EXISTS (
        SELECT 1 FROM legacy_lifecycle
        WHERE entity_kind = 'stage'
          AND entity_id = stage.id
          AND source_schema_version IN (1, 2)
      )
    ) OR achievement_generation_started_at < 0
      OR achievement_generation_started_at > unixepoch()
    LIMIT 1
    """
  ).fetchone()
  if invalid_stage is not None:
    raise ProjectError(
      f'Project has an invalid stage contract: {invalid_stage["id"]}'
    )
  invalid_task_boundary = connection.execute(
    """
    SELECT task.id
    FROM task
    LEFT JOIN stage ON stage.id = task.stage_id
    WHERE (
      NOT substantive(task.title)
      AND (
        task.status NOT IN ('pending', 'blocked')
        OR task.started_at IS NOT NULL
        OR task.completed_at IS NOT NULL
        OR NOT EXISTS (
          SELECT 1 FROM legacy_lifecycle
          WHERE entity_kind = 'task'
            AND entity_id = task.id
            AND source_schema_version IN (1, 2)
        )
      )
    ) OR (
      task.started_at IS NOT NULL
      AND (
        NOT substantive(task.title)
        OR NOT substantive(task.purpose)
        OR NOT substantive(task.scope)
        OR NOT substantive(task.exclusions)
        OR NOT substantive(task.result)
        OR NOT substantive(task.completion_evidence)
        OR (
          stage.id IS NULL
          AND NOT EXISTS (
            SELECT 1 FROM legacy_lifecycle
            WHERE entity_kind = 'task' AND entity_id = task.id
          )
        )
      )
    ) OR (
      task.goal_id IS NOT NULL
      AND task.stage_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM goal_stage
        WHERE goal_id = task.goal_id AND stage_id = task.stage_id
      )
    )
    LIMIT 1
    """
  ).fetchone()
  if invalid_task_boundary is not None:
    raise ProjectError(
      'Project has an invalid task boundary: '
      f'{invalid_task_boundary["id"]}'
    )
  invalid_blocker = connection.execute(
    """
    SELECT blocker.id
    FROM blocker
    LEFT JOIN task ON task.id = blocker.task_id
    LEFT JOIN goal ON goal.id = blocker.goal_id
    WHERE (blocker.task_id IS NULL AND blocker.goal_id IS NULL)
      OR (
        blocker.status = 'open'
        AND (
          NOT substantive(blocker.description)
          OR NOT substantive(blocker.required)
          OR (blocker.task_id IS NOT NULL AND task.status <> 'blocked')
          OR (
            blocker.task_id IS NULL
            AND blocker.goal_id IS NOT NULL
            AND goal.status <> 'blocked'
          )
          OR (
            blocker.task_id IS NOT NULL
            AND (
              (blocker.stage_id IS NOT NULL
                AND blocker.stage_id IS NOT task.stage_id)
              OR (blocker.goal_id IS NOT NULL
                AND blocker.goal_id IS NOT task.goal_id)
            )
          )
        )
      )
      OR (
        blocker.task_id IS NULL
        AND blocker.goal_id IS NOT NULL
        AND blocker.stage_id IS NOT NULL
        AND NOT EXISTS (
          SELECT 1 FROM goal_stage
          WHERE goal_id = blocker.goal_id
            AND stage_id = blocker.stage_id
        )
      )
    LIMIT 1
    """
  ).fetchone()
  if invalid_blocker is not None:
    raise ProjectError(
      f'Project has an incoherent blocker: {invalid_blocker["id"]}'
    )
  blocked_task_without_blocker = connection.execute(
    """
    SELECT task.id
    FROM task
    WHERE task.status = 'blocked'
      AND NOT EXISTS (
        SELECT 1 FROM blocker
        WHERE blocker.task_id = task.id AND blocker.status = 'open'
      )
    LIMIT 1
    """
  ).fetchone()
  if blocked_task_without_blocker is not None:
    raise ProjectError(
      'Project has a blocked task without an open blocker: '
      f'{blocked_task_without_blocker["id"]}'
    )
  incoherent_record = connection.execute(
    """
    SELECT kind, id
    FROM (
      SELECT 'decision' AS kind, id, goal_id, stage_id, task_id,
        context_status
      FROM decision
      UNION ALL
      SELECT 'evidence' AS kind, id, goal_id, stage_id, task_id,
        context_status
      FROM evidence
    ) AS record
    WHERE (
      record.context_status = 'complete'
      AND record.task_id IS NOT NULL
      AND record.stage_id IS NULL
    ) OR (
      record.context_status = 'legacy-unresolved'
      AND record.task_id IS NULL
    ) OR (
      record.context_status = 'complete'
      AND record.goal_id IS NOT NULL
      AND record.stage_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM goal_stage
        WHERE goal_id = record.goal_id AND stage_id = record.stage_id
      )
    )
    LIMIT 1
    """
  ).fetchone()
  if incoherent_record is not None:
    raise ProjectError(
      'Project has incoherent record context: '
      f'{incoherent_record["kind"]} {incoherent_record["id"]}'
    )
  invalid_evidence = connection.execute(
    """
    SELECT evidence.id
    FROM evidence
    LEFT JOIN stage ON stage.id = evidence.stage_id
    WHERE (
      evidence.claim_status = 'substantive'
      AND NOT substantive(evidence.claim)
    ) OR (
      evidence.claim_status = 'legacy-blank'
      AND substantive(evidence.claim)
    ) OR evidence.captured_at > unixepoch()
      OR (
        evidence.stage_id IS NOT NULL
        AND evidence.stage_generation > stage.achievement_generation
      )
      OR (
        evidence.stage_id IS NOT NULL
        AND evidence.stage_generation = stage.achievement_generation
        AND evidence.captured_at < stage.achievement_generation_started_at
      )
    LIMIT 1
    """
  ).fetchone()
  if invalid_evidence is not None:
    raise ProjectError(
      f'Project has incoherent evidence state: {invalid_evidence["id"]}'
    )
  dependency_cycle = connection.execute(
    """
    WITH RECURSIVE reach(start_id, dependency_id) AS (
      SELECT stage_id, dependency_id FROM stage_dependency
      UNION
      SELECT reach.start_id, stage_dependency.dependency_id
      FROM reach
      JOIN stage_dependency
        ON stage_dependency.stage_id = reach.dependency_id
    )
    SELECT start_id FROM reach
    WHERE start_id = dependency_id
    LIMIT 1
    """
  ).fetchone()
  if dependency_cycle is not None:
    raise ProjectError(
      'Project has a stage-dependency cycle at stage '
      f'{dependency_cycle["start_id"]}'
    )
  invalid_active_task = connection.execute(
    """
    SELECT task.id
    FROM task
    LEFT JOIN stage ON stage.id = task.stage_id
    WHERE task.status = 'active'
      AND (
        NOT substantive(task.title)
        OR NOT substantive(task.purpose)
        OR NOT substantive(task.scope)
        OR NOT substantive(task.exclusions)
        OR NOT substantive(task.result)
        OR NOT substantive(task.completion_evidence)
        OR task.started_at IS NULL
        OR task.started_at <= 0
        OR task.started_at > CAST(strftime('%s', 'now') AS INTEGER)
        OR stage.id IS NULL
        OR NOT substantive(stage.name)
        OR NOT substantive(stage.outcome)
        OR EXISTS (
          SELECT 1 FROM project
          WHERE NOT substantive(objective)
            OR NOT substantive(scope)
            OR NOT substantive(non_goals)
            OR NOT substantive(constraints_text)
            OR NOT substantive(acceptance)
        )
        OR EXISTS (
          SELECT 1 FROM blocker
          WHERE task_id = task.id AND status = 'open'
        )
        OR (
          task.goal_id IS NULL
          AND EXISTS (SELECT 1 FROM goal WHERE status = 'active')
        )
        OR (
          task.goal_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM goal
            WHERE id = task.goal_id AND status = 'active'
          )
        )
        OR (
          task.goal_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM goal_stage
            WHERE goal_id = task.goal_id AND stage_id = task.stage_id
          )
        )
        OR EXISTS (
          SELECT 1
          FROM stage_dependency
          LEFT JOIN stage_achievement
            ON stage_achievement.stage_id =
              stage_dependency.dependency_id
            AND stage_achievement.invalidated_at IS NULL
          WHERE stage_dependency.stage_id = task.stage_id
            AND stage_achievement.id IS NULL
        )
      )
    LIMIT 1
    """
  ).fetchone()
  if invalid_active_task is not None:
    raise ProjectError(
      f'Project has an invalid active task: {invalid_active_task["id"]}'
    )
  invalid_active_goal = connection.execute(
    """
    SELECT goal.id
    FROM goal
    WHERE goal.status = 'active'
      AND (
        goal.ever_activated <> 1
        OR goal.started_at <= 0
        OR goal.started_at > CAST(strftime('%s', 'now') AS INTEGER)
        OR NOT EXISTS (
          SELECT 1 FROM goal_stage WHERE goal_id = goal.id
        )
        OR EXISTS (
          SELECT 1 FROM blocker
          WHERE goal_id = goal.id AND task_id IS NULL AND status = 'open'
        )
        OR EXISTS (
          SELECT 1 FROM task
          WHERE status = 'active' AND goal_id IS NOT goal.id
        )
      )
    LIMIT 1
    """
  ).fetchone()
  if invalid_active_goal is not None:
    raise ProjectError(
      f'Project has an invalid active goal: {invalid_active_goal["id"]}'
    )
  invalid_goal = connection.execute(
    """
    SELECT goal.id
    FROM goal
    WHERE goal.ever_activated = 0
    OR (
      goal.ever_activated = 1
      AND (
        goal.started_at <= 0
        OR goal.started_at > unixepoch()
        OR NOT EXISTS (
          SELECT 1 FROM goal_stage WHERE goal_id = goal.id
        )
      )
    ) OR (
      goal.status <> 'blocked'
      AND EXISTS (
        SELECT 1 FROM blocker
        WHERE blocker.goal_id = goal.id
          AND blocker.task_id IS NULL
          AND blocker.status = 'open'
      )
    ) OR (
      goal.status = 'achieved'
      AND (
        goal.ever_activated <> 1
        OR goal.achieved_at < goal.started_at
        OR goal.achieved_at > unixepoch()
        OR NOT EXISTS (
          SELECT 1 FROM evidence
          WHERE evidence.goal_id = goal.id
            AND evidence.claim_status = 'substantive'
            AND substantive(evidence.claim)
        )
        OR EXISTS (
          SELECT 1 FROM evidence
          WHERE evidence.goal_id = goal.id
            AND (
              evidence.claim_status <> 'substantive'
              OR NOT substantive(evidence.claim)
              OR evidence.captured_at > goal.achieved_at
            )
        )
      )
    )
    LIMIT 1
    """
  ).fetchone()
  if invalid_goal is not None:
    raise ProjectError(
      f'Project has an invalid goal lifecycle: {invalid_goal["id"]}'
    )
  invalid_task_chronology = connection.execute(
    """
    SELECT id
    FROM task
    WHERE (started_at IS NOT NULL AND (
      started_at <= 0
      OR started_at > CAST(strftime('%s', 'now') AS INTEGER)
    )) OR (completed_at IS NOT NULL AND (
      started_at IS NULL
      OR completed_at < started_at
      OR completed_at > CAST(strftime('%s', 'now') AS INTEGER)
    ))
    LIMIT 1
    """
  ).fetchone()
  if invalid_task_chronology is not None:
    raise ProjectError(
      'Project has invalid task chronology: '
      f'{invalid_task_chronology["id"]}'
    )
  invalid_achievement = connection.execute(
    """
    SELECT stage_achievement.id
    FROM stage_achievement
    JOIN stage ON stage.id = stage_achievement.stage_id
    LEFT JOIN evidence
      ON evidence.id = stage_achievement.evidence_id
      AND evidence.stage_id = stage_achievement.stage_id
    WHERE stage_achievement.invalidated_at IS NULL
      AND (
        EXISTS (
          SELECT 1 FROM project
          WHERE NOT substantive(objective)
            OR NOT substantive(scope)
            OR NOT substantive(non_goals)
            OR NOT substantive(constraints_text)
            OR NOT substantive(acceptance)
        )
        OR NOT substantive(stage.name)
        OR NOT substantive(stage.outcome)
        OR NOT substantive(stage.exit_evidence)
        OR evidence.id IS NULL
        OR evidence.claim_status <> 'substantive'
        OR NOT substantive(evidence.claim)
        OR evidence.captured_at > stage_achievement.achieved_at
        OR evidence.captured_at < stage.achievement_generation_started_at
        OR stage_achievement.achieved_at > unixepoch()
        OR evidence.stage_generation <> stage.achievement_generation
        OR stage_achievement.stage_generation <>
          stage.achievement_generation
        OR EXISTS (
          SELECT 1 FROM stage_achievement AS prior_achievement
          WHERE prior_achievement.stage_id = stage_achievement.stage_id
            AND prior_achievement.evidence_id =
              stage_achievement.evidence_id
            AND prior_achievement.id <> stage_achievement.id
        )
        OR EXISTS (
          SELECT 1 FROM task
          WHERE task.stage_id = stage.id
            AND task.status = 'completed'
            AND task.completed_at > stage_achievement.achieved_at
        )
        OR NOT EXISTS (
          SELECT 1 FROM task
          WHERE task.stage_id = stage.id
            AND task.status = 'completed'
            AND substantive(task.title)
        )
        OR EXISTS (
          SELECT 1 FROM task
          WHERE task.stage_id = stage.id
            AND task.status IN ('pending', 'active', 'blocked')
        )
      )
    LIMIT 1
    """
  ).fetchone()
  if invalid_achievement is not None:
    raise ProjectError(
      'Project has an invalid current stage achievement: '
      f'{invalid_achievement["id"]}'
    )
  invalid_achievement_history = connection.execute(
    """
    SELECT stage_achievement.id
    FROM stage_achievement
    JOIN stage ON stage.id = stage_achievement.stage_id
    WHERE stage_achievement.invalidated_at IS NOT NULL
      AND (
        stage_achievement.invalidated_at < stage_achievement.achieved_at
        OR stage_achievement.stage_generation >=
          stage.achievement_generation
      )
    LIMIT 1
    """
  ).fetchone()
  if invalid_achievement_history is not None:
    raise ProjectError(
      'Project has invalid stage-achievement history: '
      f'{invalid_achievement_history["id"]}'
    )


def _archive_path(path):
  archive_directory = path.parent / 'archive'
  archive_directory.mkdir(parents=True, exist_ok=True)
  ctime = path.stat().st_ctime_ns
  destination = archive_directory / f'{path.stem}-{ctime}{path.suffix}'
  suffix = 1
  while destination.exists():
    destination = (
      archive_directory / f'{path.stem}-{ctime}-{suffix}{path.suffix}'
    )
    suffix += 1
  return destination


def archive_project(root, name):
  path = database_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project does not exist: {name}')
  destination = _archive_path(path)
  path.rename(destination)
  return destination


def _initialize_project(
  connection, name, objective, scope, non_goals, constraints, acceptance
):
  connection.executescript(SCHEMA_SQL)
  connection.executescript(LIFECYCLE_TRIGGER_SQL)
  connection.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
  timestamp = current_time()
  connection.execute(
    """
    INSERT INTO project
      (id, name, objective, scope, non_goals, constraints_text, acceptance,
       created_at, updated_at)
    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
      name,
      objective,
      scope,
      non_goals,
      constraints,
      acceptance,
      timestamp,
      timestamp,
    ),
  )
  connection.execute(
    """
    INSERT INTO project_state (id, updated_at)
    VALUES (1, ?)
    """,
    (timestamp,),
  )
  connection.commit()


def create_project(
  root,
  name,
  objective,
  scope='',
  non_goals='',
  constraints='',
  acceptance='',
):
  validate_project_name(name)
  _require_record_text(objective, 'Project objective')
  project_directory(root).mkdir(parents=True, exist_ok=True)
  path = database_path(root, name)
  temporary_path = (
    project_directory(root) / f'.{name}-{time.time_ns()}.tmp'
  )
  connection = connect(temporary_path)
  try:
    _initialize_project(
      connection,
      name,
      objective,
      scope,
      non_goals,
      constraints,
      acceptance,
    )
  except Exception:
    connection.close()
    temporary_path.unlink(missing_ok=True)
    raise
  connection.close()
  if path.exists():
    archive_project(root, name)
  temporary_path.rename(path)
  return path


def _row_dict(row):
  return dict(row) if row is not None else None


def _task_read_dict(row):
  task = _row_dict(row)
  if task is not None:
    task['title_status'] = (
      'substantive' if _substantive(task['title']) else 'legacy-blank'
    )
  return task


def _touch(connection):
  timestamp = current_time()
  connection.execute(
    'UPDATE project SET updated_at = ? WHERE id = 1', (timestamp,)
  )
  connection.execute(
    """
    UPDATE project_state
    SET updated_at = ?, revision = revision + 1
    WHERE id = 1
    """,
    (timestamp,),
  )


def _resolve_stage(connection, reference):
  if reference is None:
    return None
  if str(reference).isdigit():
    row = connection.execute(
      'SELECT id FROM stage WHERE id = ?', (int(reference),)
    ).fetchone()
  else:
    row = connection.execute(
      'SELECT id FROM stage WHERE name = ?', (reference,)
    ).fetchone()
  if row is None:
    raise ProjectError(f'Stage does not exist: {reference}')
  return row['id']


def _resolve_task(connection, reference):
  if str(reference).isdigit():
    row = connection.execute(
      'SELECT id FROM task WHERE id = ?', (int(reference),)
    ).fetchone()
  else:
    raise ProjectError(f'Task references must be numeric: {reference}')
  if row is None:
    raise ProjectError(f'Task does not exist: {reference}')
  return row['id']


def validate_goal_text(text):
  length = len(text)
  if not _substantive(text):
    raise ProjectError(
      'Goal text must contain at least one non-whitespace character'
    )
  if length > MAX_GOAL_TEXT_LENGTH:
    raise ProjectError(
      f'Goal text is limited to {MAX_GOAL_TEXT_LENGTH:,} characters; '
      f'received {length:,}.'
    )
  return text


def _require_record_text(value, label):
  if not _substantive(value):
    raise ProjectError(f'{label} must contain non-whitespace text')


def _resolve_goal(connection, reference=None):
  if reference is None or str(reference) == 'active':
    row = connection.execute(
      "SELECT id FROM goal WHERE status = 'active'"
    ).fetchone()
    if row is None:
      raise ProjectError('Project has no active goal')
    return row['id']
  if not str(reference).isdigit():
    raise ProjectError(f'Goal references must be numeric: {reference}')
  row = connection.execute(
    'SELECT id FROM goal WHERE id = ?', (int(reference),)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Goal does not exist: {reference}')
  return row['id']


def _resolve_evidence(connection, reference):
  if not str(reference).isdigit():
    raise ProjectError(f'Evidence references must be numeric: {reference}')
  row = connection.execute(
    'SELECT id FROM evidence WHERE id = ?', (int(reference),)
  ).fetchone()
  if row is None:
    raise ProjectError(f'Evidence does not exist: {reference}')
  return row['id']


def _ensure_goal_stage(connection, goal_id, stage_id, relationship):
  if goal_id is None or stage_id is None:
    return
  if (
    connection.execute(
      'SELECT 1 FROM goal_stage WHERE goal_id = ? AND stage_id = ?',
      (goal_id, stage_id),
    ).fetchone()
    is None
  ):
    raise ProjectError(
      f'{relationship} stage is not linked to goal {goal_id}'
    )


def _project_charter_missing(connection):
  project = connection.execute('SELECT * FROM project').fetchone()
  labels = {
    'objective': 'objective',
    'scope': 'scope',
    'non_goals': 'non-goals',
    'constraints_text': 'constraints',
    'acceptance': 'acceptance evidence',
  }
  return [
    label
    for field, label in labels.items()
    if not _substantive(project[field])
  ]


def _ensure_project_chartered(connection):
  missing = _project_charter_missing(connection)
  if missing:
    raise ProjectError(
      'Starting work requires a complete project charter; missing: '
      + ', '.join(missing)
    )


def _ensure_stage_contract(connection, stage_id):
  stage = connection.execute(
    'SELECT name, outcome FROM stage WHERE id = ?', (stage_id,)
  ).fetchone()
  if stage is None or not all(
    _substantive(stage[field]) for field in ('name', 'outcome')
  ):
    raise ProjectError('Starting work requires a complete stage contract')


def _resolve_record_relationships(
  connection, relationship, stage=None, task=None, goal=None
):
  stage_id = _resolve_stage(connection, stage)
  task_id = _resolve_task(connection, task) if task is not None else None
  goal_id = _resolve_goal(connection, goal) if goal is not None else None
  if task_id is not None:
    task_record = connection.execute(
      'SELECT goal_id, stage_id FROM task WHERE id = ?', (task_id,)
    ).fetchone()
    if stage_id is None:
      stage_id = task_record['stage_id']
    elif stage_id != task_record['stage_id']:
      raise ProjectError(f'{relationship} stage does not match task stage')
    if goal_id is None:
      goal_id = task_record['goal_id']
    elif goal_id != task_record['goal_id']:
      raise ProjectError(f'{relationship} goal does not match task goal')
  _ensure_goal_stage(connection, goal_id, stage_id, relationship)
  return stage_id, task_id, goal_id


def _active_goal(connection):
  return connection.execute(
    "SELECT id, status FROM goal WHERE status = 'active'"
  ).fetchone()


def _active_task(connection):
  return connection.execute(
    "SELECT * FROM task WHERE status = 'active'"
  ).fetchone()


def _stage_status(connection, stage_id):
  counts = {
    row['status']: row['count']
    for row in connection.execute(
      'SELECT status, count(*) AS count FROM task '
      'WHERE stage_id = ? GROUP BY status',
      (stage_id,),
    )
  }
  if counts.get('active'):
    return 'active'
  if counts.get('pending'):
    return 'pending'
  if counts.get('blocked'):
    return 'blocked'
  if (
    counts.get('completed')
    and connection.execute(
      'SELECT 1 FROM stage_achievement '
      'WHERE stage_id = ? AND invalidated_at IS NULL',
      (stage_id,),
    ).fetchone()
  ):
    return 'achieved'
  if counts and counts.get('cancelled') == sum(counts.values()):
    return 'superseded'
  return 'pending'


def _stage_record(connection, stage_id):
  stage = _row_dict(
    connection.execute(
      'SELECT * FROM stage WHERE id = ?', (stage_id,)
    ).fetchone()
  )
  achievement = connection.execute(
    'SELECT evidence_id, achieved_at FROM stage_achievement '
    'WHERE stage_id = ? AND invalidated_at IS NULL',
    (stage_id,),
  ).fetchone()
  started = connection.execute(
    'SELECT MIN(started_at) AS started_at FROM task '
    'WHERE stage_id = ? AND started_at IS NOT NULL',
    (stage_id,),
  ).fetchone()['started_at']
  return {
    **stage,
    'status': _stage_status(connection, stage_id),
    'started_at': started,
    'achieved_at': achievement['achieved_at'] if achievement else None,
    'achievement_evidence_id': (
      achievement['evidence_id'] if achievement else None
    ),
  }


def _project_status(connection):
  statuses = [
    _stage_status(connection, row['id'])
    for row in connection.execute('SELECT id FROM stage')
  ]
  if 'achieved' in statuses and all(
    status in ('achieved', 'superseded') for status in statuses
  ):
    return 'complete'
  if any(status in ('active', 'pending') for status in statuses):
    return 'active'
  if any(status == 'blocked' for status in statuses):
    return 'blocked'
  return 'active'


def _project_completed_at(connection):
  if _project_status(connection) != 'complete':
    return None
  return connection.execute(
    'SELECT MAX(achieved_at) AS completed_at FROM stage_achievement '
    'WHERE invalidated_at IS NULL'
  ).fetchone()['completed_at']


def _ensure_task_goal_is_active(connection, goal_id):
  active_goal = _active_goal(connection)
  active_goal_id = active_goal['id'] if active_goal is not None else None
  if active_goal_id == goal_id:
    return
  if active_goal_id is None and goal_id is not None:
    raise ProjectError(f'Task goal {goal_id} is not the active goal')
  if active_goal_id is not None and goal_id is None:
    raise ProjectError(
      f'An active task must link to goal {active_goal_id}'
    )
  raise ProjectError(
    f'Task goal {goal_id} does not match active goal {active_goal_id}'
  )


def _ensure_task_dependencies_are_achieved(connection, stage_id):
  if stage_id is None:
    return
  dependency = connection.execute(
    """
    SELECT dependency_stage.name
    FROM stage_dependency
    JOIN stage dependency_stage
      ON dependency_stage.id = stage_dependency.dependency_id
    LEFT JOIN stage_achievement
      ON stage_achievement.stage_id = dependency_stage.id
      AND stage_achievement.invalidated_at IS NULL
    WHERE stage_dependency.stage_id = ?
      AND stage_achievement.id IS NULL
    LIMIT 1
    """,
    (stage_id,),
  ).fetchone()
  if dependency is not None:
    raise ProjectError(
      f'Stage dependency is not achieved: {dependency["name"]}'
    )


def _task_documentation_missing(task):
  return [
    field.replace('_', ' ')
    for field in (
      'title',
      'purpose',
      'scope',
      'exclusions',
      'result',
      'completion_evidence',
    )
    if not _substantive(task[field])
  ]


def _ensure_task_documented(task):
  missing = _task_documentation_missing(task)
  if missing:
    raise ProjectError(
      'Starting a task requires documented ' + ', '.join(missing)
    )


def _ensure_no_active_task(connection, transition, goal_id=UNSET):
  if goal_id is UNSET:
    task = _active_task(connection)
  else:
    task = connection.execute(
      "SELECT id FROM task WHERE status = 'active' AND goal_id = ?",
      (goal_id,),
    ).fetchone()
  if task is not None:
    raise ProjectError(
      f'{transition} requires active task {task["id"]} to end first'
    )


def create_goal(root, name, text, stages):
  validate_goal_text(text)
  stage_references = (
    (stages,) if isinstance(stages, str) else tuple(stages)
  )
  if not stage_references or any(
    reference is None for reference in stage_references
  ):
    raise ProjectError('A goal must link to at least one stage')
  connection = open_project(root, name)
  try:
    with connection:
      active = _active_goal(connection)
      if active is not None:
        raise ProjectError(
          'Project already has an active goal; achieve, cancel, or block '
          'it before setting another goal'
        )
      _ensure_no_active_task(connection, 'Activating a goal')
      stage_ids = [
        _resolve_stage(connection, reference)
        for reference in stage_references
      ]
      if len(stage_ids) != len(set(stage_ids)):
        raise ProjectError(
          'A goal cannot link the same stage more than once'
        )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO goal
          (text, status, started_at, created_at, updated_at)
        VALUES (?, 'cancelled', 0, ?, ?)
        """,
        (text, timestamp, timestamp),
      )
      goal_id = cursor.lastrowid
      connection.executemany(
        'INSERT INTO goal_stage (goal_id, stage_id) VALUES (?, ?)',
        ((goal_id, stage_id) for stage_id in stage_ids),
      )
      connection.execute(
        "UPDATE goal SET status = 'active', started_at = ?, "
        'ever_activated = 1 WHERE id = ?',
        (timestamp, goal_id),
      )
      _touch(connection)
      return goal_id
  finally:
    connection.close()


def _blocked_goal_reason(connection, goal_id):
  blocker = connection.execute(
    'SELECT description FROM blocker WHERE goal_id = ? '
    "AND task_id IS NULL AND status = 'open' "
    'ORDER BY opened_at DESC, id DESC LIMIT 1',
    (goal_id,),
  ).fetchone()
  return blocker['description'] if blocker is not None else ''


def _goal_read_dict(connection, row):
  goal = _row_dict(row)
  if goal is not None and goal['status'] == 'blocked':
    goal['status_reason'] = _blocked_goal_reason(connection, goal['id'])
  return goal


def _read_goal_record(connection, goal_id):
  goal = _goal_read_dict(
    connection,
    connection.execute(
      'SELECT * FROM goal WHERE id = ?', (goal_id,)
    ).fetchone(),
  )
  stages = []
  for row in connection.execute(
    """
    SELECT s.id
    FROM goal_stage gs
    JOIN stage s ON s.id = gs.stage_id
    WHERE gs.goal_id = ?
    ORDER BY s.position, s.id
    """,
    (goal_id,),
  ):
    stage = _stage_record(connection, row['id'])
    stages.append(
      {key: stage[key] for key in ('id', 'name', 'status', 'outcome')}
    )
  tasks = [
    _task_read_dict(row)
    for row in connection.execute(
      """
      SELECT t.*, s.name AS stage_name
      FROM task t
      LEFT JOIN stage s ON s.id = t.stage_id
      WHERE t.goal_id = ?
      ORDER BY t.priority DESC, t.id
      """,
      (goal_id,),
    ).fetchall()
  ]
  blockers = [
    _row_dict(row)
    for row in connection.execute(
      "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
      'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
      'FROM blocker WHERE goal_id = ? '
      'ORDER BY opened_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  evidence = [
    _row_dict(row)
    for row in connection.execute(
      'SELECT * FROM evidence WHERE goal_id = '
      '? ORDER BY captured_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  decisions = [
    _row_dict(row)
    for row in connection.execute(
      'SELECT * FROM decision WHERE goal_id = '
      '? ORDER BY decided_at DESC, id DESC',
      (goal_id,),
    ).fetchall()
  ]
  return {
    'goal': goal,
    'stages': stages,
    'tasks': tasks,
    'blockers': blockers,
    'evidence': evidence,
    'decisions': decisions,
  }


def read_goals(root, name, status=None):
  if status is not None and status not in GOAL_STATUSES:
    raise ProjectError(f'Invalid goal status: {status}')
  connection = open_project(root, name)
  try:
    condition = 'WHERE g.status = ?' if status else ''
    parameters = (status,) if status else ()
    rows = connection.execute(
      f"""
      SELECT g.*,
        CASE WHEN g.status = 'active' THEN 1 ELSE 0 END AS is_active,
        COALESCE((
          SELECT group_concat(s.name, ', ')
          FROM goal_stage gs
          JOIN stage s ON s.id = gs.stage_id
          WHERE gs.goal_id = g.id
        ), '') AS stage_names
      FROM goal g
      {condition}
      ORDER BY g.id DESC
      """,
      parameters,
    ).fetchall()
    return [_goal_read_dict(connection, row) for row in rows]
  finally:
    connection.close()


def read_goal(root, name, reference=None):
  connection = open_project(root, name)
  try:
    return _read_goal_record(
      connection, _resolve_goal(connection, reference)
    )
  finally:
    connection.close()


def goal_text(root, name, reference=None):
  connection = open_project(root, name)
  try:
    goal_id = _resolve_goal(connection, reference)
    return connection.execute(
      'SELECT text FROM goal WHERE id = ?', (goal_id,)
    ).fetchone()['text']
  finally:
    connection.close()


def copy_goal(root, name, reference=None):
  text = goal_text(root, name, reference)
  payload = base64.b64encode(text.encode('utf-8')).decode('ascii')
  return f'\x1b]52;c;{payload}\x07'


def achieve_goal(root, name, reference=None):
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] != 'active':
        raise ProjectError(
          f'Only active goals can be achieved; goal {goal_id} is '
          f'{goal["status"]}'
        )
      if connection.execute(
        'SELECT 1 FROM blocker '
        'WHERE goal_id = ? AND task_id IS NULL '
        "AND status = 'open' LIMIT 1",
        (goal_id,),
      ).fetchone():
        raise ProjectError(
          'Achieving a goal requires all goal blockers to be resolved'
        )
      if (
        connection.execute(
          'SELECT 1 FROM evidence '
          "WHERE goal_id = ? AND claim_status = 'substantive' "
          'AND substantive(claim) LIMIT 1',
          (goal_id,),
        ).fetchone()
        is None
      ):
        raise ProjectError(
          'Achieving a goal requires at least one goal-linked '
          'evidence entry'
        )
      _ensure_no_active_task(connection, 'Achieving a goal', goal_id)
      timestamp = current_time()
      connection.execute(
        """
        UPDATE goal
        SET status = 'achieved', achieved_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, goal_id),
      )
      _touch(connection)
  finally:
    connection.close()


def cancel_goal(root, name, reference=None, reason=''):
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] not in ('active', 'blocked'):
        raise ProjectError(
          f'Only active or blocked goals can be cancelled; goal '
          f'{goal_id} is {goal["status"]}'
        )
      _ensure_no_active_task(connection, 'Cancelling a goal', goal_id)
      timestamp = current_time()
      connection.execute(
        """
        UPDATE blocker
        SET status = 'withdrawn', resolved_at = ?, resolution = ?
        WHERE goal_id = ? AND task_id IS NULL AND status = 'open'
        """,
        (timestamp, reason or 'Goal cancelled', goal_id),
      )
      connection.execute(
        """
        UPDATE goal
        SET status = 'cancelled', status_reason = ?, achieved_at = NULL,
          updated_at = ?
        WHERE id = ?
        """,
        (reason, timestamp, goal_id),
      )
      _touch(connection)
  finally:
    connection.close()


def reopen_goal(root, name, reference=None):
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] != 'blocked':
        raise ProjectError(
          f'Only blocked goals can be reopened; goal {goal_id} is '
          f'{goal["status"]}'
        )
      if connection.execute(
        'SELECT 1 FROM blocker '
        'WHERE goal_id = ? AND task_id IS NULL '
        "AND status = 'open' LIMIT 1",
        (goal_id,),
      ).fetchone():
        raise ProjectError(
          'A goal cannot reopen while it has open blockers'
        )
      if _active_goal(connection) is not None:
        raise ProjectError('Project already has another active goal')
      _ensure_no_active_task(connection, 'Reopening a goal')
      timestamp = current_time()
      connection.execute(
        """
        UPDATE goal
        SET status = 'active', status_reason = '', updated_at = ?
        WHERE id = ?
        """,
        (timestamp, goal_id),
      )
      _touch(connection)
  finally:
    connection.close()


def block_goal(
  root, name, reference, description, impact='', attempts='', required=''
):
  _require_record_text(description, 'Blocker description')
  _require_record_text(required, 'Blocker requirement')
  connection = open_project(root, name)
  try:
    with connection:
      goal_id = _resolve_goal(connection, reference)
      goal = connection.execute(
        'SELECT status FROM goal WHERE id = ?', (goal_id,)
      ).fetchone()
      if goal['status'] != 'active':
        raise ProjectError(
          f'Only active goals can be blocked; goal {goal_id} is '
          f'{goal["status"]}'
        )
      _ensure_no_active_task(connection, 'Blocking a goal', goal_id)
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, description, impact, attempts, required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (goal_id, description, impact, attempts, required, timestamp),
      )
      connection.execute(
        """
        UPDATE goal
        SET status = 'blocked', status_reason = ?, updated_at = ?
        WHERE id = ?
        """,
        (description, timestamp, goal_id),
      )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def _project_record(connection):
  project = _row_dict(
    connection.execute('SELECT * FROM project').fetchone()
  )
  return {
    **project,
    'status': _project_status(connection),
    'completed_at': _project_completed_at(connection),
  }


def read_project(root, name):
  connection = open_project(root, name)
  try:
    project = _project_record(connection)
    state = _row_dict(
      connection.execute('SELECT * FROM project_state').fetchone()
    )
    active_goal = _active_goal(connection)
    goal = (
      _read_goal_record(connection, active_goal['id'])
      if active_goal is not None
      else None
    )
    charter_history = [
      _row_dict(row)
      for row in connection.execute(
        'SELECT * FROM project_charter_history '
        'ORDER BY replaced_at DESC, id DESC'
      )
    ]
    return {
      'path': str(database_path(root, name)),
      'project': project,
      'state': state,
      'goal': goal,
      'charter_history': charter_history,
    }
  finally:
    connection.close()


def list_projects(root):
  directory = project_directory(root)
  if not directory.is_dir():
    return []
  projects = []
  for path in sorted(directory.glob(f'*{PROJECT_SUFFIX}')):
    connection = open_project(root, path.stem)
    try:
      item = _project_record(connection)
      item = {
        key: item[key]
        for key in ('name', 'status', 'objective', 'updated_at')
      }
      item['path'] = str(path)
      projects.append(item)
    finally:
      connection.close()
  return projects


def _prepare_project_values(values):
  allowed = {
    'objective',
    'scope',
    'non_goals',
    'constraints_text',
    'acceptance',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  unknown = set(values) - allowed
  if unknown:
    raise ProjectError(f'Unknown project fields: {sorted(unknown)}')
  return values


def _apply_project_update(connection, values):
  if not values:
    return False
  assignments = ', '.join(f'{field} = ?' for field in values)
  try:
    connection.execute(
      f'UPDATE project SET {assignments} WHERE id = 1',
      list(values.values()),
    )
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not update project: {error}') from error
  return True


def update_project(root, name, **values):
  values = _prepare_project_values(values)
  connection = open_project(root, name)
  try:
    with connection:
      if _apply_project_update(connection, values):
        _touch(connection)
  finally:
    connection.close()


def update_state(root, name, summary=UNSET, next_action=UNSET):
  values = {'summary': summary, 'next_action': next_action}
  connection = open_project(root, name)
  try:
    with connection:
      if _apply_state_update(connection, values):
        _touch(connection)
  finally:
    connection.close()


def _apply_state_update(connection, values):
  selected = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if not selected:
    return False
  unknown = set(selected) - {'summary', 'next_action'}
  if unknown:
    raise ProjectError(f'Unknown project-state fields: {sorted(unknown)}')
  assignments = ', '.join(f'{field} = ?' for field in selected)
  connection.execute(
    f'UPDATE project_state SET {assignments} WHERE id = 1',
    list(selected.values()),
  )
  return True


def update_project_and_state(root, name, project_values, state_values):
  project_values = _prepare_project_values(project_values)
  connection = open_project(root, name)
  try:
    with connection:
      project_changed = _apply_project_update(connection, project_values)
      state_changed = _apply_state_update(connection, state_values)
      if project_changed or state_changed:
        _touch(connection)
  finally:
    connection.close()


def add_stage(
  root,
  name,
  stage_name,
  outcome,
  purpose='',
  entry_conditions='',
  exit_evidence='',
):
  _require_record_text(stage_name, 'Stage name')
  _require_record_text(outcome, 'Stage outcome')
  connection = open_project(root, name)
  try:
    with connection:
      position = connection.execute(
        'SELECT COALESCE(MAX(position), -1) + 1 FROM stage'
      ).fetchone()[0]
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO stage
          (name, outcome, purpose, entry_conditions, exit_evidence,
           position, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          stage_name,
          outcome,
          purpose,
          entry_conditions,
          exit_evidence,
          position,
          timestamp,
          timestamp,
        ),
      )
      _touch(connection)
      return cursor.lastrowid
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not add stage: {error}') from error
  finally:
    connection.close()


def read_stages(root, name):
  connection = open_project(root, name)
  try:
    stages = []
    for row in connection.execute(
      'SELECT id FROM stage ORDER BY position, id'
    ):
      stage = _stage_record(connection, row['id'])
      dependencies = connection.execute(
        """
        SELECT group_concat(d.name, ', ') AS names
        FROM stage_dependency sd
        JOIN stage d ON d.id = sd.dependency_id
        WHERE sd.stage_id = ?
        """,
        (row['id'],),
      ).fetchone()['names']
      stage['dependencies'] = dependencies or ''
      stages.append(stage)
    return stages
  finally:
    connection.close()


def update_stage(root, project_name, reference, **values):
  allowed = {
    'name',
    'outcome',
    'purpose',
    'entry_conditions',
    'exit_evidence',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if set(values) - allowed:
    raise ProjectError('Unknown stage field')
  if 'name' in values:
    _require_record_text(values['name'], 'Stage name')
  if 'outcome' in values:
    _require_record_text(values['outcome'], 'Stage outcome')
  connection = open_project(root, project_name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, reference)
      if not values:
        return
      assignments = ', '.join(f'{field} = ?' for field in values)
      parameters = [*values.values(), current_time(), stage_id]
      connection.execute(
        f'UPDATE stage SET {assignments}, updated_at = ? WHERE id = ?',
        parameters,
      )
      _touch(connection)
  finally:
    connection.close()


def achieve_stage(root, name, reference, evidence):
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, reference)
      evidence_id = _resolve_evidence(connection, evidence)
      status = _stage_status(connection, stage_id)
      if status == 'achieved':
        raise ProjectError(f'Stage {stage_id} is already achieved')
      generation = connection.execute(
        'SELECT achievement_generation FROM stage WHERE id = ?',
        (stage_id,),
      ).fetchone()['achievement_generation']
      timestamp = current_time()
      try:
        connection.execute(
          """
          INSERT INTO stage_achievement
            (stage_id, evidence_id, achieved_at, stage_generation)
          VALUES (?, ?, ?, ?)
          """,
          (stage_id, evidence_id, timestamp, generation),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not achieve stage: {error}') from error
      connection.execute(
        'UPDATE stage SET updated_at = ? WHERE id = ?',
        (timestamp, stage_id),
      )
      _touch(connection)
  finally:
    connection.close()


def add_stage_dependency(root, name, reference, dependency):
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, reference)
      dependency_id = _resolve_stage(connection, dependency)
      cycle = connection.execute(
        """
        WITH RECURSIVE dependencies(id) AS (
          SELECT dependency_id
          FROM stage_dependency
          WHERE stage_id = ?
          UNION
          SELECT stage_dependency.dependency_id
          FROM stage_dependency
          JOIN dependencies ON dependencies.id = stage_dependency.stage_id
        )
        SELECT 1 FROM dependencies WHERE id = ? LIMIT 1
        """,
        (dependency_id, stage_id),
      ).fetchone()
      if cycle is not None:
        raise ProjectError('Stage dependency would create a cycle')
      try:
        connection.execute(
          'INSERT INTO stage_dependency '
          '(stage_id, dependency_id) VALUES (?, ?)',
          (stage_id, dependency_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(
          f'Could not add stage dependency: {error}'
        ) from error
      _touch(connection)
  finally:
    connection.close()


def remove_stage_dependency(root, name, reference, dependency):
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, reference)
      dependency_id = _resolve_stage(connection, dependency)
      exists = connection.execute(
        'SELECT 1 FROM stage_dependency '
        'WHERE stage_id = ? AND dependency_id = ?',
        (stage_id, dependency_id),
      ).fetchone()
      if exists is None:
        raise ProjectError(
          f'Stage {stage_id} does not depend on stage {dependency_id}'
        )
      try:
        connection.execute(
          'DELETE FROM stage_dependency '
          'WHERE stage_id = ? AND dependency_id = ?',
          (stage_id, dependency_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(
          f'Could not remove stage dependency: {error}'
        ) from error
      _touch(connection)
  finally:
    connection.close()


def add_task(
  root,
  name,
  title,
  purpose='',
  stage=None,
  priority=0,
  tags=(),
  goal=None,
  scope='',
  exclusions='',
  result='',
  completion_evidence='',
):
  _require_record_text(title, 'Task title')
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, stage)
      goal_id = (
        _resolve_goal(connection, goal) if goal is not None else None
      )
      _ensure_goal_stage(connection, goal_id, stage_id, 'Task')
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO task
          (goal_id, stage_id, title, purpose, scope, exclusions, result,
           completion_evidence, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          title,
          purpose,
          scope,
          exclusions,
          result,
          completion_evidence,
          priority,
          timestamp,
          timestamp,
        ),
      )
      task_id = cursor.lastrowid
      for tag in tags:
        _insert_tag(connection, task_id, tag)
      _touch(connection)
      return task_id
  except sqlite3.IntegrityError as error:
    raise ProjectError(f'Could not add task: {error}') from error
  finally:
    connection.close()


def _insert_tag(connection, task_id, tag):
  tag = tag.strip()
  if not tag:
    raise ProjectError('Task tags cannot be empty')
  connection.execute(
    'INSERT OR IGNORE INTO task_tag (task_id, tag) VALUES (?, ?)',
    (task_id, tag),
  )


def _task_is_ready(connection, task):
  if (
    task['status'] != 'pending'
    or task['stage_id'] is None
    or _task_documentation_missing(task)
  ):
    return False
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open'",
    (task['id'],),
  ).fetchone():
    return False
  try:
    _ensure_project_chartered(connection)
    _ensure_stage_contract(connection, task['stage_id'])
    _ensure_task_goal_is_active(connection, task['goal_id'])
    _ensure_goal_stage(
      connection, task['goal_id'], task['stage_id'], 'Task'
    )
    _ensure_task_dependencies_are_achieved(connection, task['stage_id'])
  except ProjectError:
    return False
  return True


def read_tasks(root, name, status=None, stage=None, tag=None, ready=False):
  if status is not None and status not in TASK_STATUSES:
    raise ProjectError(f'Invalid task status: {status}')
  connection = open_project(root, name)
  try:
    if ready and _active_task(connection) is not None:
      return []
    clauses = []
    parameters = []
    if status:
      clauses.append('t.status = ?')
      parameters.append(status)
    if stage is not None:
      clauses.append('t.stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if tag:
      clauses.append(
        'EXISTS (SELECT 1 FROM task_tag '
        'tt_filter WHERE tt_filter.task_id = t.id '
        'AND tt_filter.tag = ?)'
      )
      parameters.append(tag)
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    tasks = [
      _task_read_dict(row)
      for row in connection.execute(
        f"""
        SELECT t.*, s.name AS stage_name,
          COALESCE(
            (SELECT group_concat(tag, ', ') FROM task_tag
             WHERE task_id = t.id),
            ''
          ) AS tags
        FROM task t
        LEFT JOIN stage s ON s.id = t.stage_id
        {where}
        ORDER BY t.priority DESC, t.id
        """,
        parameters,
      ).fetchall()
    ]
    if ready:
      tasks = [task for task in tasks if _task_is_ready(connection, task)]
    return tasks
  finally:
    connection.close()


def read_task_logs(connection, task_id, limit=20, since=None):
  if limit <= 0:
    raise ProjectError('Task-log limits must be positive')
  parameters = [task_id]
  condition = ''
  if since is not None:
    condition = ' AND occurred_at >= ?'
    parameters.append(since)
  parameters.append(limit)
  rows = connection.execute(
    'SELECT * FROM task_log WHERE task_id = ?'
    f'{condition} ORDER BY occurred_at DESC, id DESC LIMIT ?',
    parameters,
  ).fetchall()
  return [_row_dict(row) for row in reversed(rows)]


def read_task(root, name, reference, limit=20, since=None):
  connection = open_project(root, name)
  try:
    task_id = _resolve_task(connection, reference)
    task = _task_read_dict(
      connection.execute(
        """
        SELECT t.*, s.name AS stage_name,
          COALESCE(
            (SELECT group_concat(tag, ', ') FROM task_tag
             WHERE task_id = t.id),
            ''
          ) AS tags
        FROM task t
        LEFT JOIN stage s ON s.id = t.stage_id
        WHERE t.id = ?
        """,
        (task_id,),
      ).fetchone()
    )
    logs = read_task_logs(connection, task_id, limit, since)
    return {'task': task, 'logs': logs}
  finally:
    connection.close()


def update_task(root, name, reference, **values):
  allowed = {
    'title',
    'purpose',
    'scope',
    'exclusions',
    'result',
    'completion_evidence',
    'priority',
    'stage_id',
    'goal_id',
  }
  values = {
    key: value for key, value in values.items() if value is not UNSET
  }
  if set(values) - allowed:
    raise ProjectError('Unknown task field')
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      if 'stage_id' in values:
        values['stage_id'] = _resolve_stage(connection, values['stage_id'])
      if 'goal_id' in values and values['goal_id'] is not None:
        values['goal_id'] = _resolve_goal(connection, values['goal_id'])
      if not values:
        return
      task = connection.execute(
        'SELECT * FROM task WHERE id = ?', (task_id,)
      ).fetchone()
      target_stage = values.get('stage_id', task['stage_id'])
      target_goal = values.get('goal_id', task['goal_id'])
      _ensure_goal_stage(connection, target_goal, target_stage, 'Task')
      if task['status'] == 'active':
        _ensure_task_goal_is_active(connection, target_goal)
        _ensure_task_dependencies_are_achieved(connection, target_stage)
      assignments = ', '.join(f'{field} = ?' for field in values)
      parameters = [*values.values(), current_time(), task_id]
      try:
        connection.execute(
          f'UPDATE task SET {assignments}, updated_at = ? WHERE id = ?',
          parameters,
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not update task: {error}') from error
      _touch(connection)
  finally:
    connection.close()


def append_task_log(root, name, reference, message, kind='note'):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      timestamp = current_time()
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, kind, message),
      )
      connection.execute(
        'UPDATE task SET updated_at = ? WHERE id = ?',
        (timestamp, task_id),
      )
      _touch(connection)
  finally:
    connection.close()


def _ensure_task_can_start(connection, task_id):
  task = connection.execute(
    'SELECT * FROM task WHERE id = ?', (task_id,)
  ).fetchone()
  if task['status'] != 'pending':
    raise ProjectError(
      f'Only pending tasks can start; task {task_id} is {task["status"]}'
    )
  active = _active_task(connection)
  if active is not None:
    raise ProjectError(f'Task {active["id"]} is already active')
  _ensure_project_chartered(connection)
  _ensure_task_documented(task)
  if task['stage_id'] is None:
    raise ProjectError('Starting a task requires a stage relationship')
  _ensure_stage_contract(connection, task['stage_id'])
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open' LIMIT 1",
    (task_id,),
  ).fetchone():
    raise ProjectError('Cannot start a task with open blockers')
  _ensure_goal_stage(connection, task['goal_id'], task['stage_id'], 'Task')
  _ensure_task_goal_is_active(connection, task['goal_id'])
  _ensure_task_dependencies_are_achieved(connection, task['stage_id'])
  return task


def start_task(root, name, reference):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      _ensure_task_can_start(connection, task_id)
      timestamp = current_time()
      try:
        connection.execute(
          """
          UPDATE task
          SET status = 'active', started_at = COALESCE(started_at, ?),
            completed_at = NULL, updated_at = ?
          WHERE id = ?
          """,
          (timestamp, timestamp, task_id),
        )
      except sqlite3.IntegrityError as error:
        raise ProjectError(f'Could not start task: {error}') from error
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'started', 'Task started'),
      )
      _touch(connection)
  finally:
    connection.close()


def complete_task(root, name, reference):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
      if task['status'] != 'active':
        raise ProjectError(
          f'Only the active task can complete; task {task_id} is '
          f'{task["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE task
        SET status = 'completed', completed_at = ?, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'completed', 'Task completed'),
      )
      _touch(connection)
  finally:
    connection.close()


def reopen_task(root, name, reference):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
      if task['status'] not in ('completed', 'cancelled'):
        raise ProjectError(
          f'Only completed or cancelled tasks can reopen; task '
          f'{task_id} is {task["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE task
        SET status = 'pending', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'reopened', 'Task reopened'),
      )
      _touch(connection)
  finally:
    connection.close()


def cancel_task(root, name, reference, reason=''):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status FROM task WHERE id = ?', (task_id,)
      ).fetchone()
      if task['status'] not in ('pending', 'active', 'blocked'):
        raise ProjectError(
          f'Only pending, active, or blocked tasks can be cancelled; '
          f'task {task_id} is {task["status"]}'
        )
      timestamp = current_time()
      connection.execute(
        """
        UPDATE blocker
        SET status = 'withdrawn', resolved_at = ?, resolution = ?
        WHERE task_id = ? AND status = 'open'
        """,
        (timestamp, reason or 'Task cancelled', task_id),
      )
      connection.execute(
        """
        UPDATE task
        SET status = 'cancelled', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'cancelled', reason or 'Task cancelled'),
      )
      _touch(connection)
  finally:
    connection.close()


def block_task(
  root, name, reference, description, impact='', attempts='', required=''
):
  _require_record_text(description, 'Blocker description')
  _require_record_text(required, 'Blocker requirement')
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      task = connection.execute(
        'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
        (task_id,),
      ).fetchone()
      if task['status'] not in ('pending', 'active'):
        raise ProjectError(
          f'Only pending or active tasks can be blocked; task {task_id} '
          f'is {task["status"]}'
        )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, stage_id, task_id, description, impact, attempts,
           required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          task['goal_id'],
          task['stage_id'],
          task_id,
          description,
          impact,
          attempts,
          required,
          timestamp,
        ),
      )
      connection.execute(
        """
        UPDATE task
        SET status = 'blocked', completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (timestamp, task_id),
      )
      connection.execute(
        'INSERT INTO task_log '
        '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
        (task_id, timestamp, 'blocked', description),
      )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def add_task_tags(root, name, reference, tags):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      for tag in tags:
        _insert_tag(connection, task_id, tag)
      _touch(connection)
  finally:
    connection.close()


def remove_task_tags(root, name, reference, tags):
  connection = open_project(root, name)
  try:
    with connection:
      task_id = _resolve_task(connection, reference)
      for tag in tags:
        connection.execute(
          'DELETE FROM task_tag WHERE task_id = ? AND tag = ?',
          (task_id, tag.strip()),
        )
      _touch(connection)
  finally:
    connection.close()


def add_decision(
  root,
  name,
  summary,
  rationale='',
  alternatives='',
  consequences='',
  stage=None,
  task=None,
  goal=None,
):
  connection = open_project(root, name)
  try:
    with connection:
      stage_id, task_id, goal_id = _resolve_record_relationships(
        connection, 'Decision', stage, task, goal
      )
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO decision
          (goal_id, stage_id, task_id, summary, rationale, alternatives,
           consequences, decided_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          summary,
          rationale,
          alternatives,
          consequences,
          timestamp,
        ),
      )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def read_decisions(
  root, name, limit=20, stage=None, task=None, goal=None, no_task=False
):
  if limit <= 0:
    raise ProjectError('Decision limits must be positive')
  connection = open_project(root, name)
  try:
    clauses = []
    parameters = []
    if no_task and task is not None:
      raise ProjectError('Decision task and no-task filters conflict')
    if no_task:
      clauses.append('task_id IS NULL')
    if stage is not None:
      clauses.append('stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if task is not None:
      clauses.append('task_id = ?')
      parameters.append(_resolve_task(connection, task))
    if goal is not None:
      clauses.append('goal_id = ?')
      parameters.append(_resolve_goal(connection, goal))
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    parameters.append(limit)
    rows = connection.execute(
      f'SELECT * FROM decision {where} '
      'ORDER BY decided_at DESC, id DESC LIMIT ?',
      parameters,
    ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def add_blocker(
  root,
  name,
  description,
  impact='',
  attempts='',
  required='',
  stage=None,
  task=None,
  goal=None,
):
  _require_record_text(description, 'Blocker description')
  _require_record_text(required, 'Blocker requirement')
  connection = open_project(root, name)
  try:
    with connection:
      stage_id = _resolve_stage(connection, stage)
      task_id = (
        _resolve_task(connection, task) if task is not None else None
      )
      goal_id = (
        _resolve_goal(connection, goal) if goal is not None else None
      )
      task_record = None
      if task_id is not None:
        task_record = connection.execute(
          'SELECT status, goal_id, stage_id FROM task WHERE id = ?',
          (task_id,),
        ).fetchone()
        if task_record['status'] in ('completed', 'cancelled'):
          raise ProjectError(
            f'Cannot block task {task_id} in status '
            f'{task_record["status"]}'
          )
        if goal_id is None:
          goal_id = task_record['goal_id']
        elif task_record['goal_id'] != goal_id:
          raise ProjectError('Blocker goal does not match task goal')
        if stage_id is None:
          stage_id = task_record['stage_id']
        elif task_record['stage_id'] != stage_id:
          raise ProjectError('Blocker stage does not match task stage')
      elif goal_id is None:
        raise ProjectError('A blocker must target a task or goal')
      _ensure_goal_stage(connection, goal_id, stage_id, 'Blocker')
      goal_status = None
      if goal_id is not None and task_id is None:
        goal_status = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()['status']
        if goal_status not in ('active', 'blocked'):
          raise ProjectError(
            f'Only active or blocked goals can receive blockers; goal '
            f'{goal_id} is {goal_status}'
          )
        _ensure_no_active_task(connection, 'Blocking a goal', goal_id)
      timestamp = current_time()
      cursor = connection.execute(
        """
        INSERT INTO blocker
          (goal_id, stage_id, task_id, description, impact, attempts,
           required, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          description,
          impact,
          attempts,
          required,
          timestamp,
        ),
      )
      if task_record is not None and task_record['status'] != 'blocked':
        connection.execute(
          """
          UPDATE task
          SET status = 'blocked', completed_at = NULL, updated_at = ?
          WHERE id = ?
          """,
          (timestamp, task_id),
        )
        connection.execute(
          'INSERT INTO task_log '
          '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
          (task_id, timestamp, 'blocked', description),
        )
      if task_id is None:
        connection.execute(
          """
          UPDATE goal
          SET status = 'blocked', status_reason = ?, updated_at = ?
          WHERE id = ?
          """,
          (description, timestamp, goal_id),
        )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def read_blockers(root, name, status='open'):
  connection = open_project(root, name)
  try:
    if status == 'all':
      rows = connection.execute(
        "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
        'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
        'FROM blocker ORDER BY opened_at DESC, id DESC'
      ).fetchall()
    else:
      rows = connection.execute(
        "SELECT *, CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' "
        'END AS target_kind, COALESCE(task_id, goal_id) AS target_id '
        'FROM blocker WHERE status = ? '
        'ORDER BY opened_at DESC, id DESC',
        (status,),
      ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def resolve_blocker(root, name, reference, resolution):
  connection = open_project(root, name)
  try:
    with connection:
      if not str(reference).isdigit():
        raise ProjectError(
          f'Blocker references must be numeric: {reference}'
        )
      blocker = connection.execute(
        """
        SELECT goal_id, task_id
        FROM blocker
        WHERE id = ? AND status = 'open'
        """,
        (int(reference),),
      ).fetchone()
      if blocker is None:
        raise ProjectError(f'Open blocker does not exist: {reference}')
      remaining_goal = None
      if blocker['task_id'] is None and blocker['goal_id'] is not None:
        remaining_goal = connection.execute(
          """
          SELECT description FROM blocker
          WHERE goal_id = ? AND task_id IS NULL
            AND status = 'open' AND id <> ?
          ORDER BY opened_at DESC, id DESC LIMIT 1
          """,
          (blocker['goal_id'], int(reference)),
        ).fetchone()
        goal = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker['goal_id'],)
        ).fetchone()
        if remaining_goal is None and goal['status'] == 'blocked':
          active_goal = _active_goal(connection)
          if active_goal is not None:
            raise ProjectError(
              f'Cannot reactivate goal {blocker["goal_id"]}; goal '
              f'{active_goal["id"]} is active'
            )
          _ensure_no_active_task(connection, 'Reactivating a goal')
      timestamp = current_time()
      connection.execute(
        """
        UPDATE blocker
        SET status = 'resolved', resolved_at = ?, resolution = ?
        WHERE id = ?
        """,
        (timestamp, resolution, int(reference)),
      )
      if blocker['task_id'] is not None:
        connection.execute(
          'UPDATE task SET updated_at = ? WHERE id = ?',
          (timestamp, blocker['task_id']),
        )
        connection.execute(
          'INSERT INTO task_log '
          '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
          (blocker['task_id'], timestamp, 'blocker-resolved', resolution),
        )
        remaining = connection.execute(
          """
          SELECT 1 FROM blocker
          WHERE task_id = ? AND status = 'open'
          LIMIT 1
          """,
          (blocker['task_id'],),
        ).fetchone()
        task = connection.execute(
          'SELECT status FROM task WHERE id = ?', (blocker['task_id'],)
        ).fetchone()
        if remaining is None and task['status'] == 'blocked':
          connection.execute(
            """
            UPDATE task
            SET status = 'pending', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, blocker['task_id']),
          )
          connection.execute(
            'INSERT INTO task_log '
            '(task_id, occurred_at, kind, message) VALUES (?, ?, ?, ?)',
            (
              blocker['task_id'],
              timestamp,
              'unblocked',
              'All task blockers resolved',
            ),
          )
      if blocker['task_id'] is None and blocker['goal_id'] is not None:
        goal = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (blocker['goal_id'],)
        ).fetchone()
        if goal['status'] == 'blocked' and remaining_goal is None:
          connection.execute(
            """
            UPDATE goal
            SET status = 'active', status_reason = '', updated_at = ?
            WHERE id = ?
            """,
            (timestamp, blocker['goal_id']),
          )
        elif goal['status'] == 'blocked':
          connection.execute(
            """
            UPDATE goal
            SET status_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (
              remaining_goal['description'],
              timestamp,
              blocker['goal_id'],
            ),
          )
      _touch(connection)
  finally:
    connection.close()


def add_evidence(
  root, name, claim, source='', result='', stage=None, task=None, goal=None
):
  _require_record_text(claim, 'Evidence claim')
  connection = open_project(root, name)
  try:
    with connection:
      stage_id, task_id, goal_id = _resolve_record_relationships(
        connection, 'Evidence', stage, task, goal
      )
      if goal_id is not None:
        goal_status = connection.execute(
          'SELECT status FROM goal WHERE id = ?', (goal_id,)
        ).fetchone()['status']
        if goal_status == 'achieved':
          raise ProjectError('Achieved goal evidence is fixed')
      stage_generation = (
        connection.execute(
          'SELECT achievement_generation FROM stage WHERE id = ?',
          (stage_id,),
        ).fetchone()['achievement_generation']
        if stage_id is not None
        else None
      )
      cursor = connection.execute(
        """
        INSERT INTO evidence
          (goal_id, stage_id, task_id, claim, source, result, captured_at,
           stage_generation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          goal_id,
          stage_id,
          task_id,
          claim,
          source,
          result,
          current_time(),
          stage_generation,
        ),
      )
      _touch(connection)
      return cursor.lastrowid
  finally:
    connection.close()


def read_evidence(
  root, name, limit=20, stage=None, task=None, goal=None, no_task=False
):
  if limit <= 0:
    raise ProjectError('Evidence limits must be positive')
  connection = open_project(root, name)
  try:
    clauses = []
    parameters = []
    if no_task and task is not None:
      raise ProjectError('Evidence task and no-task filters conflict')
    if no_task:
      clauses.append('task_id IS NULL')
    if stage is not None:
      clauses.append('stage_id = ?')
      parameters.append(_resolve_stage(connection, stage))
    if task is not None:
      clauses.append('task_id = ?')
      parameters.append(_resolve_task(connection, task))
    if goal is not None:
      clauses.append('goal_id = ?')
      parameters.append(_resolve_goal(connection, goal))
    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    parameters.append(limit)
    rows = connection.execute(
      f'SELECT * FROM evidence {where} '
      'ORDER BY captured_at DESC, id DESC LIMIT ?',
      parameters,
    ).fetchall()
    return [_row_dict(row) for row in rows]
  finally:
    connection.close()


def _validate_active_state(connection, goal, task):
  if task is None:
    return
  _ensure_task_documented(task)
  if task['stage_id'] is None:
    raise ProjectError('Active task has no stage relationship')
  goal_id = goal['id'] if goal is not None else None
  if task['goal_id'] != goal_id:
    raise ProjectError('Active task goal does not match the active goal')
  _ensure_goal_stage(
    connection, task['goal_id'], task['stage_id'], 'Active task'
  )
  _ensure_task_dependencies_are_achieved(connection, task['stage_id'])
  if connection.execute(
    "SELECT 1 FROM blocker WHERE task_id = ? AND status = 'open'",
    (task['id'],),
  ).fetchone():
    raise ProjectError('Active task has an open blocker')


def _handoff_page(connection, query, count_query, parameters=()):
  total = connection.execute(count_query, parameters).fetchone()[0]
  rows = [
    _row_dict(row)
    for row in connection.execute(
      f'{query} LIMIT ?', (*parameters, HANDOFF_LIMIT)
    ).fetchall()
  ]
  return rows, {
    'shown': len(rows),
    'total': total,
    'truncated': total > len(rows),
  }


def _project_command(command, name, arguments=(), options=()):
  parts = ('0', 'proj', *command, *options, '--', name, *arguments)
  rendered = ' '.join(_shell_quote(part) for part in parts)
  if len(rendered) > HANDOFF_TEXT_LIMIT:
    raise ProjectError(
      'Generated project recovery command exceeds the handoff text limit'
    )
  return rendered


def _handoff_full_value_command(data, name, path):
  root = path[0]
  if root == 'path':
    return _project_command(('status',), name, options=('--json',))
  if root in ('project', 'state'):
    return _project_command(('show',), name, options=('--json',))
  if root == 'goal':
    return _project_command(
      ('goal', 'show'),
      name,
      (data['goal']['goal']['id'],),
      ('--json',),
    )
  if root == 'stage':
    return _project_command(('stage', 'list'), name, options=('--json',))
  if root == 'task':
    return _project_command(
      ('task', 'show'), name, (data['task']['id'],), ('--json',)
    )
  if root == 'blocked_tasks':
    task = data[root][path[1]]
    return _project_command(
      ('task', 'show'), name, (task['id'],), ('--json',)
    )
  if root == 'blocked_goals':
    goal = data[root][path[1]]
    return _project_command(
      ('goal', 'show'), name, (goal['id'],), ('--json',)
    )
  if root in ('blockers', 'decisions', 'evidence', 'logs'):
    key = 'task_log' if root == 'logs' else root
    return data['retrieval'][key]
  raise ProjectError(f'No handoff retrieval path for {root}')


def read_handoff(root, name):
  connection = open_project(root, name)
  try:
    project = _project_record(connection)
    state = _row_dict(
      connection.execute('SELECT * FROM project_state').fetchone()
    )
    active_goal = _active_goal(connection)
    active_task = _active_task(connection)
    _validate_active_state(connection, active_goal, active_task)
    goal = None
    if active_goal is not None:
      goal = {
        'goal': _row_dict(
          connection.execute(
            'SELECT * FROM goal WHERE id = ?', (active_goal['id'],)
          ).fetchone()
        )
      }
    task = _task_read_dict(active_task)
    stage = (
      _stage_record(connection, task['stage_id'])
      if task is not None and task['stage_id'] is not None
      else None
    )
    blocked_tasks, blocked_task_page = _handoff_page(
      connection,
      """
      SELECT task.id, task.title, task.status, task.goal_id, task.stage_id,
        stage.name AS stage_name, task.updated_at
      FROM task
      LEFT JOIN stage ON stage.id = task.stage_id
      WHERE task.status = 'blocked'
      ORDER BY task.updated_at DESC, task.id DESC
      """,
      "SELECT count(*) FROM task WHERE status = 'blocked'",
    )
    blocked_tasks = [_task_read_dict(item) for item in blocked_tasks]
    blocked_goals, blocked_goal_page = _handoff_page(
      connection,
      """
      SELECT id, text, status, status_reason, updated_at
      FROM goal
      WHERE status = 'blocked'
      ORDER BY updated_at DESC, id DESC
      """,
      "SELECT count(*) FROM goal WHERE status = 'blocked'",
    )
    for blocked_goal in blocked_goals:
      blocked_goal['status_reason'] = _blocked_goal_reason(
        connection, blocked_goal['id']
      )
    blockers, blocker_page = _handoff_page(
      connection,
      """
      SELECT id, goal_id, stage_id, task_id, description, required,
        opened_at,
        CASE WHEN task_id IS NOT NULL THEN 'task' ELSE 'goal' END
          AS target_kind,
        COALESCE(task_id, goal_id) AS target_id
      FROM blocker
      WHERE status = 'open'
      ORDER BY opened_at DESC, id DESC
      """,
      "SELECT count(*) FROM blocker WHERE status = 'open'",
    )
    focus_task_id = (
      task['id']
      if task is not None
      else blocked_tasks[0]['id']
      if blocked_tasks
      else None
    )
    focus_goal_id = (
      active_goal['id']
      if active_goal is not None
      else blocked_goals[0]['id']
      if blocked_goals
      else None
    )
    if focus_task_id is not None:
      focus_clause = 'task_id = ?'
      focus_parameters = (focus_task_id,)
      focus_kind = 'task'
      focus_id = focus_task_id
    elif focus_goal_id is not None:
      focus_clause = 'goal_id = ? AND task_id IS NULL'
      focus_parameters = (focus_goal_id,)
      focus_kind = 'goal'
      focus_id = focus_goal_id
    else:
      focus_clause = '0'
      focus_parameters = ()
      focus_kind = None
      focus_id = None
    decisions, decision_page = _handoff_page(
      connection,
      f"""
      SELECT id, goal_id, stage_id, task_id, summary, decided_at,
        context_status
      FROM decision
      WHERE {focus_clause}
      ORDER BY decided_at DESC, id DESC
      """,
      f'SELECT count(*) FROM decision WHERE {focus_clause}',
      focus_parameters,
    )
    evidence, evidence_page = _handoff_page(
      connection,
      f"""
      SELECT id, goal_id, stage_id, task_id, claim, source, result,
        captured_at, context_status, claim_status, stage_generation
      FROM evidence
      WHERE {focus_clause}
      ORDER BY captured_at DESC, id DESC
      """,
      f'SELECT count(*) FROM evidence WHERE {focus_clause}',
      focus_parameters,
    )
    logs = []
    log_page = {'shown': 0, 'total': 0, 'truncated': False}
    if focus_task_id is not None:
      logs, log_page = _handoff_page(
        connection,
        """
        SELECT occurred_at, kind, message
        FROM task_log
        WHERE task_id = ?
        ORDER BY occurred_at DESC, id DESC
        """,
        'SELECT count(*) FROM task_log WHERE task_id = ?',
        (focus_task_id,),
      )
    retrieval = {
      'project': _project_command(('show',), name, options=('--json',)),
      'goal': (
        _project_command(
          ('goal', 'show'), name, (active_goal['id'],), ('--json',)
        )
        if active_goal is not None
        else None
      ),
      'stage': (
        _project_command(('stage', 'list'), name, options=('--json',))
        if stage is not None
        else None
      ),
      'task': (
        _project_command(
          ('task', 'show'), name, (task['id'],), ('--json',)
        )
        if task is not None
        else None
      ),
      'blocked_tasks': _project_command(
        ('task', 'list'),
        name,
        options=('--status', 'blocked', '--json'),
      ),
      'blocked_goals': _project_command(
        ('goal', 'list'),
        name,
        options=('--status', 'blocked', '--json'),
      ),
      'blockers': _project_command(
        ('blocker', 'list'), name, options=('--json',)
      ),
      'ready_tasks': _project_command(('task', 'ready'), name),
      'decisions': (
        _project_command(
          ('decision', 'list'),
          name,
          options=(
            f'--{focus_kind}',
            focus_id,
            *(('--no-task',) if focus_kind == 'goal' else ()),
            '--limit',
            max(decision_page['total'], 1),
            '--json',
          ),
        )
        if focus_kind is not None
        else _project_command(
          ('decision', 'list'), name, options=('--json',)
        )
      ),
      'evidence': (
        _project_command(
          ('evidence', 'list'),
          name,
          options=(
            f'--{focus_kind}',
            focus_id,
            *(('--no-task',) if focus_kind == 'goal' else ()),
            '--limit',
            max(evidence_page['total'], 1),
            '--json',
          ),
        )
        if focus_kind is not None
        else _project_command(
          ('evidence', 'list'), name, options=('--json',)
        )
      ),
      'task_log': (
        _project_command(
          ('task', 'logs'),
          name,
          (focus_task_id,),
          ('--limit', max(log_page['total'], 1), '--json'),
        )
        if focus_task_id is not None
        else None
      ),
    }
    data = {
      'path': str(Path('.tmp') / f'{name}{PROJECT_SUFFIX}'),
      'project': project,
      'state': state,
      'goal': goal,
      'stage': stage,
      'task': task,
      'blocked_tasks': blocked_tasks,
      'blocked_goals': blocked_goals,
      'blockers': blockers,
      'decisions': decisions,
      'evidence': evidence,
      'logs': logs,
      'focus': {'kind': focus_kind, 'id': focus_id},
      'pages': {
        'blocked_tasks': blocked_task_page,
        'blocked_goals': blocked_goal_page,
        'blockers': blocker_page,
        'decisions': decision_page,
        'evidence': evidence_page,
        'task_log': log_page,
      },
      'retrieval': retrieval,
    }
    data['text_projection'] = _render_handoff(data)[1]
    return data
  finally:
    connection.close()


def _handoff_page_suffix(data, key):
  page = data['pages'][key]
  parts = [f'{page["shown"]} of {page["total"]}']
  if page['truncated']:
    parts.append(f'more: {data["retrieval"][key]}')
  return f' ({"; ".join(parts)})'


def _record_compatibility_markers(item):
  markers = []
  if item['context_status'] != 'complete':
    markers.append('legacy unresolved context')
  if item.get('claim_status') not in (None, 'substantive'):
    markers.append('legacy blank claim')
  return ''.join(f' [{marker}]' for marker in markers)


def _task_compatibility_markers(item):
  if item.get('title_status') == 'legacy-blank':
    return ' [legacy blank title]'
  return ''


def _render_handoff(data):
  project = data['project']
  state = data['state']
  stage = data['stage']
  task = data['task']
  goal = data['goal']
  name = project['name']
  truncations = []
  commands = set()

  def text(value, path, default='-'):
    if value is None or value == '':
      return default
    value = str(value)
    if len(_format_text(value, '')) <= HANDOFF_TEXT_LIMIT:
      return _format_text(value)
    command = _handoff_full_value_command(data, name, path)
    commands.add(command)
    truncations.append(
      {
        'path': '.'.join(str(part) for part in path),
        'characters': len(value),
        'retrieval': command,
      }
    )
    return _format_text(_truncate_text(value, HANDOFF_TEXT_LIMIT))

  lines = [
    f'Project: {text(project["name"], ("project", "name"))}',
    f'Status: {project["status"]}',
    f'Objective: {text(project["objective"], ("project", "objective"))}',
    *(
      ['Charter context: legacy incomplete']
      if project['charter_context_status'] == 'legacy-incomplete'
      else []
    ),
    f'Project database: {text(data["path"], ("path",))}',
    f'Active goal: {goal["goal"]["id"]} ({goal["goal"]["status"]})'
    if goal
    else 'Active goal: -',
    f'Goal text: {text(goal["goal"]["text"], ("goal", "goal", "text"))}'
    if goal
    else 'Goal text: -',
    f'Active stage: {text(stage["name"], ("stage", "name"))}'
    if stage
    else 'Active stage: -',
    f'Active task: {task["id"]}'
    f'{_task_compatibility_markers(task)} '
    f'{text(task["title"], ("task", "title"))}'
    if task
    else 'Active task: -',
    f'Summary: {text(state["summary"], ("state", "summary"))}',
    f'Next action: {text(state["next_action"], ("state", "next_action"))}',
  ]
  if data['blockers']:
    lines.append(f'Open blockers{_handoff_page_suffix(data, "blockers")}:')
    for index, item in enumerate(data['blockers']):
      lines.append(
        f'- {item["id"]} [{item["target_kind"]} '
        f'{item["target_id"]}]: '
        f'{text(item["description"], ("blockers", index, "description"))}'
        '; '
        f'required: '
        f'{text(item["required"], ("blockers", index, "required"))}'
      )
  for key, label in (
    ('blocked_tasks', 'Blocked tasks'),
    ('blocked_goals', 'Blocked goals'),
  ):
    if not data[key]:
      continue
    lines.append(f'{label}{_handoff_page_suffix(data, key)}:')
    if key == 'blocked_tasks':
      for index, item in enumerate(data[key]):
        lines.append(
          f'- {item["id"]}{_task_compatibility_markers(item)} '
          f'{text(item["title"], (key, index, "title"))} '
          f'(stage: '
          f'{text(item["stage_name"], (key, index, "stage_name"))}; '
          f'goal: {item["goal_id"] or "-"})'
        )
    else:
      for index, item in enumerate(data[key]):
        lines.append(
          f'- {item["id"]}: {text(item["text"], (key, index, "text"))}; '
          f'reason: '
          f'{text(item["status_reason"], (key, index, "status_reason"))}'
        )
  if data['decisions']:
    lines.append(
      f'Relevant {data["focus"]["kind"]} decisions'
      + _handoff_page_suffix(data, 'decisions')
      + ':'
    )
    for index, item in enumerate(data['decisions']):
      lines.append(
        f'- {item["id"]}'
        f'{_record_compatibility_markers(item)}'
        f': {text(item["summary"], ("decisions", index, "summary"))}'
      )
  if data['evidence']:
    lines.append(
      f'Relevant {data["focus"]["kind"]} evidence'
      + _handoff_page_suffix(data, 'evidence')
      + ':'
    )
    for index, item in enumerate(data['evidence']):
      lines.append(
        f'- {item["id"]}'
        f'{_record_compatibility_markers(item)}'
        f': {text(item["claim"], ("evidence", index, "claim"))}'
      )
  if data['logs']:
    lines.append(
      'Recent task log' + _handoff_page_suffix(data, 'task_log') + ':'
    )
    for reverse_index, item in enumerate(reversed(data['logs'])):
      index = len(data['logs']) - reverse_index - 1
      lines.append(
        f'- {text(item["kind"], ("logs", index, "kind"))}: '
        f'{text(item["message"], ("logs", index, "message"))}'
      )
  projection = {
    'character_limit': HANDOFF_TEXT_LIMIT,
    'truncated_fields': truncations,
    'full_value_commands': sorted(commands),
  }
  if projection['truncated_fields']:
    lines.append(
      f'Text projection: {len(projection["truncated_fields"])} fields '
      f'truncated at {projection["character_limit"]} rendered characters.'
    )
    lines.extend(
      f'- Full values: {command}'
      for command in projection['full_value_commands']
    )
  return '\n'.join(lines), projection


def format_handoff(data):
  return _render_handoff(data)[0]


def format_project_details(data):
  project = data['project']
  state = data['state']
  goal = data['goal']
  return '\n'.join(
    [
      f'Project: {_format_text(project["name"])}',
      f'Status: {project["status"]}',
      f'Objective: {_format_text(project["objective"])}',
      f'Scope: {_format_text(project["scope"])}',
      f'Non-goals: {_format_text(project["non_goals"])}',
      f'Constraints: {_format_text(project["constraints_text"])}',
      f'Acceptance: {_format_text(project["acceptance"])}',
      f'Active goal: {goal["goal"]["id"]} ({goal["goal"]["status"]})'
      if goal
      else 'Active goal: -',
      f'Goal text: {_format_text(goal["goal"]["text"])}'
      if goal
      else 'Goal text: -',
      f'Created: {format_time(project["created_at"])}',
      f'Updated: {format_time(project["updated_at"])}',
      f'Summary: {_format_text(state["summary"])}',
      f'Next action: {_format_text(state["next_action"])}',
      f'State revision: {state["revision"]}',
    ]
  )


def _project_root(ctx):
  return ctx.obj['project_root']


def _json_or_echo(value, as_json):
  if as_json:
    click.echo(json.dumps(value, indent=2, sort_keys=True))
  else:
    click.echo(value)


def _invoke(function, *args, **kwargs):
  try:
    return function(*args, **kwargs)
  except (ProjectError, sqlite3.Error) as error:
    raise click.ClickException(str(error)) from error


@click.group(cls=lib.AliasedGroup)
@click.option(
  '--root', type=click.Path(file_okay=False, path_type=Path), hidden=True
)
@click.pass_context
def project_group(ctx, root):
  """Manage provisional SQLite project control planes."""
  ctx.ensure_object(dict)
  ctx.obj['project_root'] = root.resolve() if root else repository_root()


project_group.aliases = ['p']


@project_group.command('create')
@click.argument('name')
@click.option('--objective', required=True)
@click.option('--scope', default='')
@click.option('--non-goals', default='')
@click.option('--constraints', default='')
@click.option('--acceptance', default='')
@click.pass_context
def create_command(
  ctx, name, objective, scope, non_goals, constraints, acceptance
):
  """Create a project, archiving an existing same-name project."""
  path = _invoke(
    create_project,
    _project_root(ctx),
    name,
    objective,
    scope,
    non_goals,
    constraints,
    acceptance,
  )
  click.echo(path)


@project_group.command('list')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def list_command(ctx, as_json):
  """List unarchived project databases."""
  projects = _invoke(list_projects, _project_root(ctx))
  if as_json:
    _json_or_echo(projects, True)
    return
  for project in projects:
    click.echo(
      f'{_format_text(project["name"])}\t{project["status"]}\t'
      f'{format_time(project["updated_at"])}\t'
      f'{_format_text(project["objective"])}'
    )


@project_group.command('status')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def status_command(ctx, name, as_json):
  """Read compact project state."""
  data = _invoke(read_handoff, _project_root(ctx), name)
  _json_or_echo(data, as_json) if as_json else click.echo(
    format_handoff(data)
  )


@project_group.command('handoff')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def handoff_command(ctx, name, as_json):
  """Produce a compact handoff for a new session."""
  data = _invoke(read_handoff, _project_root(ctx), name)
  _json_or_echo(data, as_json) if as_json else click.echo(
    format_handoff(data)
  )


@project_group.command('show')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def show_command(ctx, name, as_json):
  """Read the project charter and compact state."""
  data = _invoke(read_project, _project_root(ctx), name)
  _json_or_echo(data, as_json) if as_json else click.echo(
    format_project_details(data)
  )


@project_group.command('update')
@click.argument('name')
@click.option('--objective')
@click.option('--scope')
@click.option('--non-goals')
@click.option('--constraints')
@click.option('--acceptance')
@click.option('--summary')
@click.option('--next-action')
@click.pass_context
def update_command(
  ctx,
  name,
  objective,
  scope,
  non_goals,
  constraints,
  acceptance,
  summary,
  next_action,
):
  """Update charter or compact project state."""
  root = _project_root(ctx)
  _invoke(
    update_project_and_state,
    root,
    name,
    {
      'objective': objective if objective is not None else UNSET,
      'scope': scope if scope is not None else UNSET,
      'non_goals': non_goals if non_goals is not None else UNSET,
      'constraints_text': constraints
      if constraints is not None
      else UNSET,
      'acceptance': acceptance if acceptance is not None else UNSET,
    },
    {
      'summary': summary if summary is not None else UNSET,
      'next_action': next_action if next_action is not None else UNSET,
    },
  )


@project_group.command('archive')
@click.argument('name')
@click.pass_context
def archive_command(ctx, name):
  """Move an unarchived project database into the archive."""
  click.echo(_invoke(archive_project, _project_root(ctx), name))


@project_group.group(cls=lib.AliasedGroup)
def goal():
  """Manage the project's durable goal."""


@goal.command('list')
@click.argument('name')
@click.option('--status', type=click.Choice(GOAL_STATUSES))
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_list_command(ctx, name, status, as_json):
  goals = _invoke(read_goals, _project_root(ctx), name, status)
  if as_json:
    _json_or_echo(goals, True)
  else:
    for item in goals:
      marker = '*' if item['is_active'] else '-'
      click.echo(
        f'{marker}\t{item["id"]}\t{item["status"]}\t'
        f'{_format_text(item["stage_names"])}\t'
        f'{_format_text(item["text"])}'
      )


@goal.command('set')
@click.argument('name')
@click.option('--text', required=True)
@click.option('--stage', 'stages', multiple=True, required=True)
@click.pass_context
def goal_set_command(ctx, name, text, stages):
  click.echo(_invoke(create_goal, _project_root(ctx), name, text, stages))


@goal.command('show')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def goal_show_command(ctx, name, goal_reference, as_json):
  data = _invoke(read_goal, _project_root(ctx), name, goal_reference)
  _json_or_echo(data, as_json) if as_json else click.echo(
    json.dumps(data, indent=2, sort_keys=True)
  )


@goal.command('text')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_text_command(ctx, name, goal_reference):
  click.echo(
    _invoke(goal_text, _project_root(ctx), name, goal_reference), nl=False
  )


@goal.command('copy')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_copy_command(ctx, name, goal_reference):
  click.echo(
    _invoke(copy_goal, _project_root(ctx), name, goal_reference), nl=False
  )


@goal.command('achieve')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.pass_context
def goal_achieve_command(ctx, name, goal_reference):
  _invoke(achieve_goal, _project_root(ctx), name, goal_reference)


@goal.command('block')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', required=True)
@click.pass_context
def goal_block_command(
  ctx, name, goal_reference, description, impact, attempts, required
):
  click.echo(
    _invoke(
      block_goal,
      _project_root(ctx),
      name,
      goal_reference,
      description,
      impact,
      attempts,
      required,
    )
  )


@goal.command('reopen')
@click.argument('name')
@click.argument('goal_reference')
@click.pass_context
def goal_reopen_command(ctx, name, goal_reference):
  _invoke(reopen_goal, _project_root(ctx), name, goal_reference)


@goal.command('cancel')
@click.argument('name')
@click.argument('goal_reference', required=False)
@click.option('--reason', default='')
@click.pass_context
def goal_cancel_command(ctx, name, goal_reference, reason):
  _invoke(
    cancel_goal,
    _project_root(ctx),
    name,
    goal_reference,
    reason,
  )


@project_group.group(cls=lib.AliasedGroup)
def stage():
  """Manage project stages."""


@stage.command('list')
@click.argument('name')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def stage_list_command(ctx, name, as_json):
  stages = _invoke(read_stages, _project_root(ctx), name)
  if as_json:
    _json_or_echo(stages, True)
  else:
    for item in stages:
      click.echo(
        f'{item["id"]}\t{item["status"]}\t'
        f'{_format_text(item["name"])}\t'
        f'{_format_text(item["outcome"])}'
      )


@stage.command('add')
@click.argument('name')
@click.argument('stage_name')
@click.option('--outcome', required=True)
@click.option('--purpose', default='')
@click.option('--entry-conditions', default='')
@click.option('--exit-evidence', default='')
@click.pass_context
def stage_add_command(
  ctx, name, stage_name, outcome, purpose, entry_conditions, exit_evidence
):
  click.echo(
    _invoke(
      add_stage,
      _project_root(ctx),
      name,
      stage_name,
      outcome,
      purpose,
      entry_conditions,
      exit_evidence,
    )
  )


@stage.command('update')
@click.argument('name')
@click.argument('stage_reference')
@click.option('--stage-name')
@click.option('--outcome')
@click.option('--purpose')
@click.option('--entry-conditions')
@click.option('--exit-evidence')
@click.pass_context
def stage_update_command(
  ctx,
  name,
  stage_reference,
  stage_name,
  outcome,
  purpose,
  entry_conditions,
  exit_evidence,
):
  _invoke(
    update_stage,
    _project_root(ctx),
    name,
    stage_reference,
    name=stage_name if stage_name is not None else UNSET,
    outcome=outcome if outcome is not None else UNSET,
    purpose=purpose if purpose is not None else UNSET,
    entry_conditions=entry_conditions
    if entry_conditions is not None
    else UNSET,
    exit_evidence=exit_evidence if exit_evidence is not None else UNSET,
  )


@stage.command('achieve')
@click.argument('name')
@click.argument('stage_reference')
@click.option('--evidence', required=True)
@click.pass_context
def stage_achieve_command(ctx, name, stage_reference, evidence):
  _invoke(
    achieve_stage,
    _project_root(ctx),
    name,
    stage_reference,
    evidence,
  )


@stage.command('depend')
@click.argument('name')
@click.argument('stage_reference')
@click.argument('dependency')
@click.pass_context
def stage_depend_command(ctx, name, stage_reference, dependency):
  _invoke(
    add_stage_dependency,
    _project_root(ctx),
    name,
    stage_reference,
    dependency,
  )


@stage.command('undepend')
@click.argument('name')
@click.argument('stage_reference')
@click.argument('dependency')
@click.pass_context
def stage_undepend_command(ctx, name, stage_reference, dependency):
  """Remove one stage dependency when dependent work is inactive."""
  _invoke(
    remove_stage_dependency,
    _project_root(ctx),
    name,
    stage_reference,
    dependency,
  )


@project_group.group(cls=lib.AliasedGroup)
def task():
  """Manage project tasks."""


@task.command('list')
@click.argument('name')
@click.option('--status', type=click.Choice(TASK_STATUSES))
@click.option('--stage')
@click.option('--tag')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_list_command(ctx, name, status, stage, tag, as_json):
  tasks = _invoke(read_tasks, _project_root(ctx), name, status, stage, tag)
  if as_json:
    _json_or_echo(tasks, True)
  else:
    for item in tasks:
      click.echo(
        f'{item["id"]}{_task_compatibility_markers(item)}'
        f'\t{item["status"]}\t{_format_text(item["stage_name"])}'
        f'\tgoal {item["goal_id"] or "-"}'
        f'\t{_format_text(item["title"])}'
        f'\t{_format_text(item["tags"])}'
      )


@task.command('ready')
@click.argument('name')
@click.option('--tag')
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_ready_command(ctx, name, tag, as_json):
  tasks = _invoke(
    read_tasks, _project_root(ctx), name, tag=tag, ready=True
  )
  if as_json:
    _json_or_echo(tasks, True)
  else:
    for item in tasks:
      click.echo(
        f'{item["id"]}{_task_compatibility_markers(item)}'
        f'\t{_format_text(item["stage_name"])}'
        f'\t{_format_text(item["title"])}'
      )


@task.command('add')
@click.argument('name')
@click.option('--title', required=True)
@click.option('--purpose', default='')
@click.option('--scope', default='')
@click.option('--exclusions', default='')
@click.option('--result', default='')
@click.option('--completion-evidence', default='')
@click.option('--stage')
@click.option('--priority', default=0, type=int)
@click.option('--tag', multiple=True)
@click.option('--goal')
@click.pass_context
def task_add_command(
  ctx,
  name,
  title,
  purpose,
  scope,
  exclusions,
  result,
  completion_evidence,
  stage,
  priority,
  tag,
  goal,
):
  click.echo(
    _invoke(
      add_task,
      _project_root(ctx),
      name,
      title,
      purpose,
      stage,
      priority,
      tag,
      goal,
      scope,
      exclusions,
      result,
      completion_evidence,
    )
  )


@task.command('show')
@click.argument('name')
@click.argument('task_reference')
@click.option('--limit', default=20, type=int)
@click.option('--since', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_show_command(ctx, name, task_reference, limit, since, as_json):
  data = _invoke(
    read_task,
    _project_root(ctx),
    name,
    task_reference,
    limit,
    since,
  )
  _json_or_echo(data, as_json) if as_json else click.echo(
    json.dumps(data, indent=2, sort_keys=True)
  )


@task.command('logs')
@click.argument('name')
@click.argument('task_reference')
@click.option('--limit', default=20, type=int)
@click.option('--since', type=int)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def task_logs_command(ctx, name, task_reference, limit, since, as_json):
  data = _invoke(
    read_task,
    _project_root(ctx),
    name,
    task_reference,
    limit,
    since,
  )
  logs = data['logs']
  if as_json:
    _json_or_echo(logs, True)
  else:
    for entry in logs:
      click.echo(
        f'{format_time(entry["occurred_at"])}\t'
        f'{_format_text(entry["kind"])}\t'
        f'{_format_text(entry["message"])}'
      )


@task.command('update')
@click.argument('name')
@click.argument('task_reference')
@click.option('--title')
@click.option('--purpose')
@click.option('--scope')
@click.option('--exclusions')
@click.option('--result')
@click.option('--completion-evidence')
@click.option('--priority', type=int)
@click.option('--stage')
@click.option('--goal')
@click.option('--no-goal', is_flag=True)
@click.pass_context
def task_update_command(
  ctx,
  name,
  task_reference,
  title,
  purpose,
  scope,
  exclusions,
  result,
  completion_evidence,
  priority,
  stage,
  goal,
  no_goal,
):
  if goal is not None and no_goal:
    raise click.UsageError('--goal and --no-goal cannot be combined')
  _invoke(
    update_task,
    _project_root(ctx),
    name,
    task_reference,
    title=title if title is not None else UNSET,
    purpose=purpose if purpose is not None else UNSET,
    scope=scope if scope is not None else UNSET,
    exclusions=exclusions if exclusions is not None else UNSET,
    result=result if result is not None else UNSET,
    completion_evidence=completion_evidence
    if completion_evidence is not None
    else UNSET,
    priority=priority if priority is not None else UNSET,
    stage_id=stage if stage is not None else UNSET,
    goal_id=None if no_goal else goal if goal is not None else UNSET,
  )


@task.command('start')
@click.argument('name')
@click.argument('task_reference')
@click.pass_context
def task_start_command(ctx, name, task_reference):
  _invoke(start_task, _project_root(ctx), name, task_reference)


@task.command('complete')
@click.argument('name')
@click.argument('task_reference')
@click.pass_context
def task_complete_command(ctx, name, task_reference):
  _invoke(complete_task, _project_root(ctx), name, task_reference)


@task.command('reopen')
@click.argument('name')
@click.argument('task_reference')
@click.pass_context
def task_reopen_command(ctx, name, task_reference):
  _invoke(reopen_task, _project_root(ctx), name, task_reference)


@task.command('cancel')
@click.argument('name')
@click.argument('task_reference')
@click.option('--reason', default='')
@click.pass_context
def task_cancel_command(ctx, name, task_reference, reason):
  _invoke(cancel_task, _project_root(ctx), name, task_reference, reason)


@task.command('log')
@click.argument('name')
@click.argument('task_reference')
@click.argument('message')
@click.option('--kind', default='note')
@click.pass_context
def task_log_command(ctx, name, task_reference, message, kind):
  _invoke(
    append_task_log,
    _project_root(ctx),
    name,
    task_reference,
    message,
    kind,
  )


@task.command('block')
@click.argument('name')
@click.argument('task_reference')
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', required=True)
@click.pass_context
def task_block_command(
  ctx, name, task_reference, description, impact, attempts, required
):
  click.echo(
    _invoke(
      block_task,
      _project_root(ctx),
      name,
      task_reference,
      description,
      impact,
      attempts,
      required,
    )
  )


@task.command('tag')
@click.argument('name')
@click.argument('task_reference')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_tag_command(ctx, name, task_reference, tags):
  _invoke(add_task_tags, _project_root(ctx), name, task_reference, tags)


@task.command('untag')
@click.argument('name')
@click.argument('task_reference')
@click.argument('tags', nargs=-1, required=True)
@click.pass_context
def task_untag_command(ctx, name, task_reference, tags):
  _invoke(remove_task_tags, _project_root(ctx), name, task_reference, tags)


@project_group.group(cls=lib.AliasedGroup)
def decision():
  """Manage project decisions."""


@decision.command('add')
@click.argument('name')
@click.option('--summary', required=True)
@click.option('--rationale', default='')
@click.option('--alternatives', default='')
@click.option('--consequences', default='')
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.pass_context
def decision_add_command(
  ctx,
  name,
  summary,
  rationale,
  alternatives,
  consequences,
  stage,
  task,
  goal,
):
  click.echo(
    _invoke(
      add_decision,
      _project_root(ctx),
      name,
      summary,
      rationale,
      alternatives,
      consequences,
      stage,
      task,
      goal,
    )
  )


@decision.command('list')
@click.argument('name')
@click.option('--limit', default=20, type=int)
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.option('--no-task', is_flag=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def decision_list_command(
  ctx, name, limit, stage, task, goal, no_task, as_json
):
  decisions = _invoke(
    read_decisions,
    _project_root(ctx),
    name,
    limit,
    stage,
    task,
    goal,
    no_task,
  )
  if as_json:
    _json_or_echo(decisions, True)
  else:
    for item in decisions:
      click.echo(
        f'{item["id"]}{_record_compatibility_markers(item)}'
        f'\t{format_time(item["decided_at"])}\t'
        f'{_format_text(item["summary"])}'
      )


@project_group.group(cls=lib.AliasedGroup)
def blocker():
  """Manage project blockers."""


@blocker.command('add')
@click.argument('name')
@click.option('--description', required=True)
@click.option('--impact', default='')
@click.option('--attempts', default='')
@click.option('--required', required=True)
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.pass_context
def blocker_add_command(
  ctx, name, description, impact, attempts, required, stage, task, goal
):
  click.echo(
    _invoke(
      add_blocker,
      _project_root(ctx),
      name,
      description,
      impact,
      attempts,
      required,
      stage,
      task,
      goal,
    )
  )


@blocker.command('list')
@click.argument('name')
@click.option(
  '--status', type=click.Choice((*BLOCKER_STATUSES, 'all')), default='open'
)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def blocker_list_command(ctx, name, status, as_json):
  blockers = _invoke(read_blockers, _project_root(ctx), name, status)
  if as_json:
    _json_or_echo(blockers, True)
  else:
    for item in blockers:
      click.echo(
        f'{item["id"]}\t{item["status"]}\t{item["target_kind"]} '
        f'{item["target_id"]}\tstage {item["stage_id"] or "-"}'
        f'\tgoal {item["goal_id"] or "-"}'
        f'\t{_format_text(item["description"])}'
        f'\timpact: {_format_text(item["impact"])}'
        f'\tattempts: {_format_text(item["attempts"])}'
        f'\trequired: {_format_text(item["required"])}'
      )


@blocker.command('resolve')
@click.argument('name')
@click.argument('blocker_reference')
@click.option('--resolution', required=True)
@click.pass_context
def blocker_resolve_command(ctx, name, blocker_reference, resolution):
  _invoke(
    resolve_blocker,
    _project_root(ctx),
    name,
    blocker_reference,
    resolution,
  )


@project_group.group(cls=lib.AliasedGroup)
def evidence():
  """Manage project evidence."""


@evidence.command('add')
@click.argument('name')
@click.option('--claim', required=True)
@click.option('--source', default='')
@click.option('--result', default='')
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.pass_context
def evidence_add_command(
  ctx, name, claim, source, result, stage, task, goal
):
  click.echo(
    _invoke(
      add_evidence,
      _project_root(ctx),
      name,
      claim,
      source,
      result,
      stage,
      task,
      goal,
    )
  )


@evidence.command('list')
@click.argument('name')
@click.option('--limit', default=20, type=int)
@click.option('--stage')
@click.option('--task')
@click.option('--goal')
@click.option('--no-task', is_flag=True)
@click.option('--json', 'as_json', is_flag=True)
@click.pass_context
def evidence_list_command(
  ctx, name, limit, stage, task, goal, no_task, as_json
):
  entries = _invoke(
    read_evidence,
    _project_root(ctx),
    name,
    limit,
    stage,
    task,
    goal,
    no_task,
  )
  if as_json:
    _json_or_echo(entries, True)
  else:
    for item in entries:
      click.echo(
        f'{item["id"]}{_record_compatibility_markers(item)}'
        f'\t{format_time(item["captured_at"])}'
        f'\t{_format_text(item["claim"])}'
      )
