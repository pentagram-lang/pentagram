import re
import sqlite3
import time
from pathlib import Path

from .errors import ProjectError


def is_substantive(value: str) -> bool:
  return bool(value and value.strip())


SCHEMA_VERSION = 7

PROJECT_SUFFIX = '.sqlite3'

PROJECT_NAME_PATTERN = re.compile(r'^[^/\\\x00]+$')

MAX_PROJECT_NAME_LENGTH = 200

type SchemaDefinitionKey = tuple[str, str]
type SchemaDefinitions = dict[int, dict[SchemaDefinitionKey, str]]

_SCHEMA_DEFINITIONS: SchemaDefinitions = {}

GOAL_TABLE_SQL = """CREATE TABLE goal (
  id INTEGER PRIMARY KEY,
  text TEXT NOT NULL
    CHECK (
      length(text) > 0
      AND substantive(text)
      AND length(text) <= 4000
    ),
  status TEXT NOT NULL DEFAULT 'cancelled'
    CHECK (
      status IN ('active', 'pending', 'blocked', 'achieved', 'cancelled')
    ),
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
)"""

GOAL_TABLE_SQL_V6 = """CREATE TABLE goal (
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
)"""

PROJECT_CHARTER_STABLE_ERROR = (
  'active task or active/pending/blocked goal requires a stable project '
  'charter; end the task and cancel active, pending, or blocked goals '
  'before re-chartering'
)

TASK_START_TIME_ERROR = (
  'task start time must be positive and not in the future'
)

TASK_COMPLETION_TIME_ERROR = (
  'task completion time must follow activation and not be in the future'
)

SCHEMA_SQL = f"""
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

{GOAL_TABLE_SQL};

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
  OR EXISTS (
    SELECT 1 FROM goal WHERE status IN ('active', 'pending', 'blocked')
  )
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
    AND NEW.status IN ('pending', 'completed', 'blocked', 'cancelled'))
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
    NEW.goal_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM goal
      WHERE id = NEW.goal_id AND status = 'active'
    )
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
    NEW.goal_id IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM goal
      WHERE id = NEW.goal_id AND status = 'active'
    )
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
    WHERE status = 'active'
      AND goal_id IS NOT NULL AND goal_id IS NOT NEW.id
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
    AND NEW.status IN ('pending', 'blocked', 'achieved', 'cancelled')
    AND NEW.ever_activated = 1)
  OR (OLD.status = 'pending'
    AND OLD.ever_activated = 1
    AND NEW.status IN ('active', 'cancelled')
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
    WHERE id = NEW.goal_id
      AND status IN ('pending', 'achieved', 'cancelled')
  ))
)
BEGIN
  SELECT RAISE(ABORT, 'open blocker targets an inactive entity');
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

PROJECT_CHARTER_STABLE_ERROR_V6 = (
  'active task or active/blocked goal requires a stable project charter; '
  'end the task and cancel the goal before re-chartering'
)

GOAL_STATUS_TRANSITION_SQL_V6 = """CREATE TRIGGER goal_status_transition
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
END"""

V6_TRIGGER_SQL = (
  f"""CREATE TRIGGER project_charter_active_task
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
    ABORT, {PROJECT_CHARTER_STABLE_ERROR_V6!r}
  );
END""",
  """CREATE TRIGGER task_status_transition
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
END""",
  GOAL_STATUS_TRANSITION_SQL_V6,
  """CREATE TRIGGER open_blocker_target
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
END""",
)

V6_TRIGGER_NAMES = (
  'project_charter_active_task',
  'task_status_transition',
  'goal_status_transition',
  'open_blocker_target',
)


def current_time() -> int:
  return int(time.time())


def validate_project_name(name: str) -> str:
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


def project_directory(root: str | Path) -> Path:
  return Path(root) / '.tmp'


def database_path(root: str | Path, name: str) -> Path:
  validate_project_name(name)
  return project_directory(root) / f'{name}{PROJECT_SUFFIX}'


def connect(path: str | Path) -> sqlite3.Connection:
  connection = sqlite3.connect(path, timeout=5)
  connection.row_factory = sqlite3.Row
  connection.create_function(
    'substantive', 1, is_substantive, deterministic=True
  )
  connection.execute('PRAGMA foreign_keys = ON')
  connection.execute('PRAGMA busy_timeout = 5000')
  return connection


def open_project(root: str | Path, name: str) -> sqlite3.Connection:
  path = database_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project does not exist: {name}')
  connection = connect(path)
  try:
    _validate_project(connection, path)
    return connection
  except sqlite3.Error as error:
    connection.close()
    raise ProjectError(
      f'Project database could not be validated: {path}: {error}'
    ) from error
  except ProjectError:
    connection.close()
    raise


def _validate_project(connection: sqlite3.Connection, path: Path) -> None:
  version = connection.execute('PRAGMA user_version').fetchone()[0]
  if version == 6:
    _validate_project_singletons(connection, path.stem)
    _validate_project_schema(connection, _canonical_schema_definitions(6))
    _validate_project_integrity(connection)
    _validate_current_lifecycle(connection)
    _migrate_schema_6_to_7(connection)
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


def _migrate_schema_6_to_7(connection: sqlite3.Connection) -> None:
  trigger_names = sorted(
    name
    for kind, name in _canonical_schema_definitions(6)
    if kind == 'trigger'
  )
  drop_triggers = '\n'.join(
    f'DROP TRIGGER "{name}";' for name in trigger_names
  )
  migration = f"""
  BEGIN IMMEDIATE;
  {drop_triggers}
  CREATE TEMP TABLE goal_migration_copy AS
    SELECT id, text, status, status_reason, ever_activated, created_at,
      started_at, achieved_at, updated_at
    FROM goal;
  DROP TABLE goal;
  {GOAL_TABLE_SQL};
  INSERT INTO goal (
    id, text, status, status_reason, ever_activated, created_at,
    started_at, achieved_at, updated_at
  ) SELECT
    id, text, status, status_reason, ever_activated, created_at,
    started_at, achieved_at, updated_at
  FROM goal_migration_copy;
  DROP TABLE goal_migration_copy;
  CREATE INDEX goal_status_index ON goal(status);
  CREATE UNIQUE INDEX one_active_goal_index
    ON goal(status) WHERE status = 'active';
  {LIFECYCLE_TRIGGER_SQL}
  PRAGMA user_version = {SCHEMA_VERSION};
  """
  connection.execute('PRAGMA foreign_keys = OFF')
  try:
    connection.executescript(migration)
    _validate_project_schema(connection)
    _validate_project_integrity(connection)
    _validate_current_lifecycle(connection)
    connection.commit()
  finally:
    if connection.in_transaction:
      connection.rollback()
    connection.execute('PRAGMA foreign_keys = ON')


def _validate_project_schema(
  connection: sqlite3.Connection,
  expected: dict[SchemaDefinitionKey, str] | None = None,
) -> None:
  expected = (
    _canonical_schema_definitions() if expected is None else expected
  )
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


def _validate_project_integrity(connection: sqlite3.Connection) -> None:
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


def _validate_project_singletons(
  connection: sqlite3.Connection, expected_name: str
) -> None:
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


def _execute_sql(connection: sqlite3.Connection, script: str) -> None:
  statement = ''
  for line in script.splitlines(keepends=True):
    statement += line
    if sqlite3.complete_statement(statement):
      connection.execute(statement)
      statement = ''
  if statement.strip():
    raise ProjectError('Incomplete project schema SQL')


def _normalize_schema_definition(definition: str) -> str:
  return ' '.join(definition.strip().rstrip(';').split())


def _canonical_schema_definitions(
  version: int = SCHEMA_VERSION,
) -> dict[SchemaDefinitionKey, str]:
  if version not in (6, SCHEMA_VERSION):
    raise ValueError(f'Unsupported schema definition version: {version}')
  if version not in _SCHEMA_DEFINITIONS:
    expected = sqlite3.connect(':memory:')
    expected.row_factory = sqlite3.Row
    expected.create_function(
      'substantive', 1, is_substantive, deterministic=True
    )
    try:
      schema_sql = SCHEMA_SQL
      if version == 6:
        schema_sql = schema_sql.replace(
          f'{GOAL_TABLE_SQL};', f'{GOAL_TABLE_SQL_V6};'
        )
      _execute_sql(expected, schema_sql)
      _execute_sql(expected, LIFECYCLE_TRIGGER_SQL)
      if version == 6:
        for trigger_name, trigger_sql in zip(
          V6_TRIGGER_NAMES, V6_TRIGGER_SQL, strict=True
        ):
          expected.execute(f'DROP TRIGGER "{trigger_name}"')
          expected.execute(trigger_sql)
      _SCHEMA_DEFINITIONS[version] = {
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
  return _SCHEMA_DEFINITIONS[version]


def _project_charter_complete(project: sqlite3.Row) -> bool:
  return all(
    is_substantive(project[field])
    for field in (
      'objective',
      'scope',
      'non_goals',
      'constraints_text',
      'acceptance',
    )
  )


def _stage_contract_complete(stage: sqlite3.Row) -> bool:
  return is_substantive(stage['name']) and is_substantive(stage['outcome'])


def _validate_current_lifecycle(connection: sqlite3.Connection) -> None:
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
          WHERE status = 'active'
            AND goal_id IS NOT NULL AND goal_id IS NOT goal.id
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


def _archive_path(path: Path) -> Path:
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


def archive_database(root: str | Path, name: str) -> Path:
  path = database_path(root, name)
  if not path.is_file():
    raise ProjectError(f'Project does not exist: {name}')
  destination = _archive_path(path)
  path.rename(destination)
  return destination


def _initialize_project(
  connection: sqlite3.Connection,
  name: str,
  objective: str,
  scope: str,
  non_goals: str,
  constraints: str,
  acceptance: str,
) -> None:
  connection.executescript(
    f'BEGIN;\n{SCHEMA_SQL}\n{LIFECYCLE_TRIGGER_SQL}'
  )
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


def create_database(
  root: str | Path,
  name: str,
  objective: str,
  scope: str = '',
  non_goals: str = '',
  constraints: str = '',
  acceptance: str = '',
) -> Path:
  validate_project_name(name)
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
  archived_path = None
  try:
    if path.exists():
      archived_path = archive_database(root, name)
    temporary_path.rename(path)
  except OSError as error:
    if archived_path is not None:
      try:
        archived_path.rename(path)
      except OSError as restore_error:
        raise ProjectError(
          f'Could not install project database at {path}: {error}; '
          f'the previous database could not be restored from '
          f'{archived_path}: {restore_error}; the new database remains at '
          f'{temporary_path}'
        ) from restore_error
    try:
      temporary_path.unlink(missing_ok=True)
    except OSError as cleanup_error:
      raise ProjectError(
        f'Could not install project database at {path}: {error}; '
        f'the temporary database remains at {temporary_path}: '
        f'{cleanup_error}'
      ) from cleanup_error
    raise
  return path
