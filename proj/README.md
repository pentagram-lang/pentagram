# Project workflow

The project workflow provides Pentagram's control plane for durable outcomes, charters, stages, tasks, goals, decisions, blockers, and evidence across sessions and interruptions. By binding meaningful work to an explicit charter and a single active task, it lets contributors and agents advance, inspect, hand off, and verify work without relying on private conversation history. Its domain semantics govern provisional SQLite databases stored at `.tmp/<project-name>.sqlite3`, exposed through the `0 proj` CLI (mounted by the [command plane](../zero/README.md) as `0 proj` and `0 p`) and implemented in Python across `proj/`.

## Purpose

Meaningful Pentagram work belongs to a project. A project is the durable unit that carries an outcome across tasks, sessions, failures, and changes of plan.

The project is a control system, not ceremony around the work. It keeps work oriented towards an observable result and supplies the state and authority needed to reach that result.

A project's **charter** is its stable, project-wide contract. It states the problem or opportunity, terminal outcome, boundaries and authority, and evidence needed to establish completion. Its stored fields are the objective, scope, non-goals, constraints, and acceptance evidence. The charter governs goals, stages, and tasks without prescribing the project's method.

All project text is documentation. The charter, goals, stages, tasks, decisions, logs, evidence, summaries, and handoffs follow the [documentation standards](../doc/README.md). Provisional storage changes durability, not the obligation to keep project text true, clear, and usable.

## Control model

A project compares its desired state with observed state and chooses the next bounded action that most usefully closes the gap.

| Control concept | Project meaning                                                 |
| --------------- | --------------------------------------------------------------- |
| Desired state   | The terminal outcome and its acceptance criteria                |
| Observed state  | Completed work, evidence, decisions, risks, and blockers        |
| Control input   | The next bounded task or project decision                       |
| Feedback        | Tests, review, diagnostics, experiments, and observed behaviour |
| Disturbance     | Ambiguity, failure, dependency change, or new information       |
| Controller      | The project workflow that chooses or revises the next action    |

The project loop is:

```text
observe -> choose the next bounded action -> act -> inspect the result
  -> update project state -> re-align with the outcome
```

The method can adapt when evidence changes; the outcome remains the anchor.

## Project entities

- A **project** owns a terminal outcome and remains meaningful across sessions.
- A **goal** is an optional durable delegation of the project's present desired result and boundary. A project has at most one active goal.
- A **stage** owns an intermediate outcome that advances or de-risks the project.
- A **task** owns a bounded result and the work needed to establish it. It must belong to a stage before activation, and a project has at most one active task.
- A **session** is a temporary execution window. It may advance tasks but does not own project meaning or completion.

Entity relationships are structured project state. A task need not repeat its stage or goal relationship in prose, although mentioning a relationship can make the task easier to understand. Goals are optional: a project and its tasks can run without one.

## Task-bound work

All meaningful project work must be tracked by and performed within the scope of a properly documented active task. Meaningful work includes substantive investigation, design, implementation, testing, review, and reconciliation. A task is not merely a pointer to work recorded elsewhere; it establishes the boundary within which that work is authorized and evaluated.

Keep questions, exploration, decisions, and ordinary problem-solving within the current task when they advance its result and remain within its authorized scope. A new question, discovered defect, change of activity, or session boundary does not by itself require a new task. Answering a question or finishing a step does not complete the task unless its required result has been established.

Create a separate task when distinct scope, authority, or useful decomposition requires a separate execution boundary. If newly needed work falls outside the current task's scope, revise its boundary or create a separate task before proceeding. Neither choice expands the project's authority.

Before a task can become active, its record must identify:

- the bounded work, through its title;
- its purpose;
- its scope;
- its exclusions;
- the result required for completion; and
- the evidence needed to establish that result.

The task must also have a structured stage relationship and an optional goal relationship, which is omitted when the task is not bound to a goal. Each prose field must contain substantive text. Operations reject activation when any field or the stage relationship is missing. After activation, updates keep every required field substantive and prevent the active task from losing its stage relationship. Changing an active task's boundary must precede work under the changed boundary.

Task completeness does not replace the project charter. Activation also requires substantive project objective, scope, non-goals, constraints, and acceptance evidence, together with a substantive name and outcome for the task's stage. Use an explicit value such as `None` when a required charter category has no items; an empty field means that the charter is unfinished. A project can be created and documented incrementally, but no task is ready or active until this gate passes. Once execution has started, the charter cannot return to an unfinished state.

A narrow control-plane exception permits only the project-control work needed to establish or recover a properly documented active task. Depending on the existing state, this can include creating and chartering the project, defining stages and dependencies, establishing an applicable goal, creating and documenting the task, recording blockers, and updating the handoff. This exception does not authorize substantive investigation, design, implementation, testing, or review outside an active task.

Every task must advance the project outcome or produce information that changes the next project decision. Activity is not a substitute for progress.

## Project charter

Before execution, a project establishes a charter containing:

- the problem or opportunity;
- the terminal outcome in observable terms;
- scope and explicit non-goals;
- constraints, invariants, and authority boundaries;
- evidence required for completion;
- initial stages and their dependencies; and
- known uncertainty, risks, and external dependencies.

The five stored charter fields (`objective` / `--objective`, `scope` / `--scope`, `non_goals` / `--non-goals`, `constraints_text` / `--constraints`, and `acceptance` / `--acceptance`) are the activation gate for this charter. Each must contain substantive text. Initial stages and dependencies remain structured records rather than duplicated prose.

The charter gives work a stable purpose without prescribing every implementation detail. The project owns its method and may change it when evidence shows that the present path is ineffective.

Execution begins once any task has a `started_at` timestamp or status `active` or `completed`. Modifying any charter field after execution has begun is an explicit re-charter. It keeps all charter fields substantive, requires no active task and no active, pending, or blocked goal, and clears `achievement_evidence_id` and `achieved_at` on all `stage` rows in the same transaction. When a goal is also active in the agent harness, end that pursuit before cancelling the project goal. After replacing the charter, establish any replacement goal on both planes and verify their exact match before resuming meaningful work. Updating `summary` or `next_action` alone never triggers re-chartering, and pre-execution charter construction does not trigger these gates.

## Project authority

Unless an exceptional boundary applies, the project has authority to make the decisions and resolve the blockers needed to realize its charter. This includes choosing designs, decomposition, sequencing, trade-offs, verification methods, and responses to failed work.

Following a chosen method includes establishing the roles and isolated work contexts that the method requires. This is ordinary project work, not a separate authority boundary. Every participant and action remains constrained by the active task and applicable authority.

Ordinary uncertainty is not an escalation condition. The project first inspects further, chooses an alternative, revises its plan, or records a trade-off.

Exceptional boundaries are decisions that:

- materially change the terminal outcome or charter;
- cross a higher-priority instruction or safety boundary;
- require destructive, external, privileged, or irreversible authority the project does not possess; or
- depend on information or capability outside the project's control.

A method change is ordinary project work. An outcome or authority change requires an explicit re-charter rather than silent drift. Project authority ends when the project closes.

## Goals

A goal is useful when an exact desired result and boundary must persist across sessions. Goal text is a literal delegation of operator intent, not a subject summary or proposed plan. It preserves the requested result, scope, authority, and exclusions without strengthening, weakening, or filling gaps in the request.

A goal may name source documents, reports, diffs, research, or other references without granting them authority. It states whether a reference governs, supplies an input, records evidence, or provides context. When discussion has changed a proposal from a reference, the goal captures the resulting decision or delegates to project state that does; it does not silently turn the reference into requirements.

A good goal:

- names a bounded, inspectable result;
- identifies the project state that owns detailed requirements and execution;
- states consequential scope and exclusions;
- preserves the authority and role of consequential references;
- leaves decomposition, sequencing, alternatives, and ordinary recovery to the project control plane; and
- identifies conditions that may genuinely block progress.

Goal text is canonical project data. It must contain non-whitespace text, excludes NUL characters, is preserved exactly as submitted, and is limited to 4,000 characters.

### Goal activation

Goal activation is a two-plane transition. It is complete only when the project contains the active canonical goal and the agent harness is pursuing that exact text. `0 proj goal create` establishes the project plane; it does not activate the harness.

Activate a goal in this order:

1. Create or activate and inspect the canonical project goal. Confirm that the applicable tasks, stages, summary, next action, decisions, and relationships are truthful.
2. Read the exact text with `0 proj goal text NAME`.
3. Activate that exact text in the harness.
4. Read both goals and verify an exact match before beginning pursuit.

Do not begin goal work between these steps. If the harness cannot activate a goal, ask the operator to run `0 proj goal copy NAME` (or `0 proj goal copy NAME GOAL`), which writes an OSC 52 clipboard escape sequence (`\x1b]52;c;<base64>\x07`) to standard output for OSC 52-capable terminals rather than accessing a host OS clipboard directly, and activate the copied text.

A missing or different goal on either plane is an activation mismatch. Stop goal work and recover both planes instead of choosing one or blending them. End any active task governed by the incorrect project goal, cancel that goal without claiming achievement, end the incorrect harness goal through the harness's supported lifecycle or operator control, establish the corrected project goal, activate its exact text in the harness, and verify the match again. If either plane cannot complete its transition, keep work stopped and record the exact unavailable transition as the blocker.

The project control plane owns planning, task sequencing, evidence, blockers, and lifecycle. Goal completion is not project completion. A goal can be achieved while later project work remains.

Goal statuses are `active`, `pending`, `blocked`, `achieved`, and `cancelled`. At most one goal is active (`idx_goal_active`). `pending` means a previously activated goal was deferred without being blocked, cancelled, or achieved; its status reason identifies the goal that displaced it (`Deferred for goal <id>`), and reactivation clears that reason. Goal creation constructs its row and `goal_stage` rows and activates it in one transaction; its stage set is fixed after creation. Cancellation is terminal. A `pending` goal can be activated explicitly; a `blocked` goal can reactivate through `goal reopen` or final-blocker resolution.

Activating a goal while another is active first returns any active task linked to the old goal to `pending`, records a `'handoff'` task log, and returns the old goal to `pending`. A goal-less active task remains active because it is compatible with either goal. `goal create`, `goal activate`, `goal reopen`, and final-blocker recovery share this atomic handoff. The command changes only project state; when the goal is also active in the agent harness, follow the two-plane activation procedure above.

An active goal may become achieved only with substantive goal-linked evidence, no active task, and no open goal blocker. Every goal-linked evidence entry must exist by the achievement time (`captured_at <= achieved_at`), and `achieved_at` cannot precede the goal's `started_at`. Blocking or cancelling a goal requires no active linked task.

## Derived lifecycle

Task status is the primary stored execution status; goals and blockers also store their own statuses. Stage status and project status are derived from task and stage-achievement columns (`achievement_evidence_id`, `achieved_at`), active stage is derived from the active task, and `handoff` derives its active and blocked entities and focus from current task, goal, and open-blocker records without separate active or current entity pointers.

### Tasks

Task statuses are:

- `pending`: available for further documentation or activation;
- `active`: the project's one execution boundary (`idx_task_active`);
- `blocked`: unable to proceed while one or more task blockers remain open;
- `completed`: its required result has been established; and
- `cancelled`: intentionally ended without claiming completion.

Only a `pending`, fully documented task can be activated. It must have no open blocker, it must belong to a stage with substantive `name` and `outcome`, and all transitive dependencies of its stage must be achieved. A task linked to a goal requires that goal to be active. A goal-less task may run whether or not the project has an active goal.

Completing a task records the contributor's claim that its required result has been established against its `completion_evidence` criterion. That evidence can be an external observation or a project evidence record; the project plane does not evaluate it or require a linked evidence row. Record project evidence when later work must inspect the basis. Stage achievement has the separate named-evidence gate described under [stages](#stages).

Activating another eligible task while one is active returns the old task to `pending` and activates the requested task in one transaction. The handoff appends a `'handoff'` task-log entry and preserves the old task's first `started_at` timestamp, so it can be resumed later. An unsuccessful activation leaves the current task unchanged. `task ready` lists eligible pending tasks even while another task is active. Completing a task requires it to be `active` and `completed_at >= started_at`. Resolving the final task blocker returns a blocked task to `pending` with an `'unblocked'` log. Reopening a `completed` or `cancelled` task returns it to `pending`, clears `completed_at`, and invalidates its stage achievement when needed. Cancelling a `pending`, `active`, or `blocked` task withdraws its remaining open blockers and appends a `'cancelled'` log.

### Stages

Stage status is calculated in this precedence order:

1. `active` when any task in the stage is `active`;
2. `pending` when no task is `active` and any task is `pending`;
3. `blocked` when no task is `active` or `pending` and any task is `blocked`;
4. `achieved` when at least one task is `completed`, every other task is `completed` or `cancelled`, and `achievement_evidence_id` is set;
5. `superseded` when the stage has tasks and every task is `cancelled`; and
6. `pending` when the stage is empty or completed work lacks achievement evidence.

Because only one task can be active, at most one stage can be active.

Achieving a stage records `achievement_evidence_id` and `achieved_at` on the `stage` row. It requires a complete 5-field project charter; a substantive stage `name`, `outcome`, and `exit_evidence`; all transitive stage dependencies `achieved`; at least one `completed` task; zero `pending`, `active`, or `blocked` tasks in the stage; every `completed` task's `completed_at <= achieved_at`; and a stage-linked `evidence` row (`stage_id == stage.id`) with a substantive `claim` and `captured_at <= achieved_at`.

A stage's `outcome` and `exit_evidence` form its achievement contract. Changing either field, adding an unachieved dependency, creating or reopening a task in an achieved stage, moving a `pending`, `active`, or `blocked` task into an achieved stage, moving a `completed` task with `completed_at > achieved_at` (or missing `completed_at`) into an achieved stage, or moving the last `completed` task out of an achieved stage clears `achievement_evidence_id` and `achieved_at` on that stage and every stage transitively depending on it in the same transaction. Moving a `cancelled` task or a `completed` task with `completed_at <= achieved_at` into an achieved stage preserves its achievement. Invalidation is rejected while any stage transitively depending on the stage has an `active` task (excluding the moving task itself during `update_task`).

A stage dependency is satisfied only when the dependency stage is `achieved`. Dependency cycles are rejected, a task cannot activate while any transitive dependency of its stage is unachieved, adding an unachieved dependency to a stage with an active task is rejected, and removing a dependency while the dependent stage has an active task is rejected.

### Projects

Project status is calculated from all stage statuses in this precedence order:

1. `complete` when at least one stage is `achieved` and every stage is `achieved` or `superseded`;
2. `active` when any stage is `active` or `pending`;
3. `blocked` when no stage is `active` or `pending` and any stage is `blocked`; and
4. `active` otherwise (when the project has no stages or every stage is `superseded`).

An all-superseded project remains active because cancellation alone does not establish its outcome. It must be re-chartered, given a stage that can establish the outcome, or archived without a completion claim.

## Blockers and evidence

A blocker is project state, not completion. Its description and exact decision or capability required must contain non-whitespace text. It also records the condition's impact and attempted resolutions.

Every blocker has one lifecycle target. A blocker with a task relationship targets that task (`pending`, `active`, or `blocked`); its stage and goal relationships are context and must agree with the task when supplied, and a task cannot be reassigned while an open blocker's recorded context would disagree. A blocker without a task relationship must target an `active` or `blocked` goal (with no active linked task when `active`), and any stage context must belong to that goal via `goal_stage`. Stage-only and targetless blockers are rejected. Creating an open blocker transitions its target to `blocked`. Resolving the target's last open blocker returns a blocked task to `pending` (recording an `'unblocked'` log) or reactivates a blocked goal using the standard goal handoff. Cancelling a task or goal withdraws its open blockers.

Evidence records substantive observations alongside optional sources and results. Stage achievement identifies one stage-linked evidence entry. Goal achievement requires at least one goal-linked evidence entry.

When a decision or evidence record is created with `task_id`, `ops.py` snapshots the task's `goal_id` and `stage_id` onto the record and rejects conflicting explicit `--stage` or `--goal` values.

## Operating lifecycle

The project lifecycle is iterative:

1. **Charter:** establish the problem, outcome, boundaries, authority, and completion evidence.
2. **Orient:** inspect the current system, relevant documentation, state, and constraints within an active task.
3. **Frame:** state the semantic change, invariants, boundaries, and unchanged behaviour.
4. **Plan:** choose stages, dependencies, task boundaries, and evidence.
5. **Execute:** advance the active task within its authorized scope.
6. **Check:** inspect the result using evidence proportionate to its risk.
7. **Reconcile:** update documentation, decisions, evidence, summary, and next action to match reality.
8. **Close:** establish stage and project outcomes and record remaining uncertainty or follow-up work.

A failed check can return the project to framing or planning. New information can change the stage graph, and a blocker can require a decision rather than more execution.

## Persistent project state

Project state preserves information that changes future decisions:

- the terminal outcome and derived project status;
- the active goal and task, when present;
- the stage derived from the active task;
- the situation summary and next bounded action;
- achieved outcomes and their evidence;
- decisions and rationale;
- blockers, attempted resolutions, and escalation needs; and
- changed assumptions, risks, dependencies, and unresolved uncertainty.

The state is not a diary. Task logs and evidence preserve useful detail, while `handoff` remains a compact state estimate that lets a fresh operator or agent continue without private conversation history.

## Operational project plane

Each project is stored in a provisional SQLite database:

```text
.tmp/<project-name>.sqlite3
```

Project databases persist across sessions but remain outside published history. A project name is one printable path component of at most 200 characters, forbidding `/`, `\`, NUL, exact `.` or `..`, and a trailing `.sqlite3` suffix. Creating a project with an existing name moves the old project database to `.tmp/archive/<name>-<ts>.sqlite3` before atomically installing the new one via a temporary file.

The `.tmp/` directory also holds non-project provisional artifacts. `list`, `create`, and `archive` probe `.tmp/*.sqlite3` regular files read-only (`?mode=ro`) for a `project` table in `sqlite_master`: `list` skips readable SQLite files without a `project` table and fails naming the path on unreadable or non-SQLite files, while `create` and `archive` refuse to overwrite or archive readable non-project SQLite files and fail on non-SQLite files.

Substantive text is defined once by `is_substantive(text)`: `bool(text.strip())`.

The database uses SQLite schema version `1` (`PRAGMA user_version = 1`), `PRAGMA foreign_keys = ON`, `STRICT` tables, and partial unique indexes `idx_goal_active` and `idx_task_active`, with zero migrations, zero triggers, and zero open-time DDL or integrity scans. Opening a named project verifies that `.tmp/<name>.sqlite3` exists, contains a `project` table, has `user_version == 1`, and has `project.name == name`.

## Database tables

The schema has 11 `STRICT` tables:

- `project` (`id = 1`) stores `name`, charter fields (`objective`, `scope`, `non_goals`, `constraints_text`, `acceptance`), `summary`, `next_action`, `created_at`, and `updated_at`.
- `stage` stores intermediate outcome contracts (`name`, `outcome`, `purpose`, `entry_conditions`, `exit_evidence`, `position`), current achievement pointers (`achievement_evidence_id`, `achieved_at`), `created_at`, and `updated_at`.
- `stage_dependency` stores the acyclic stage graph (`stage_id`, `dependency_id`).
- `goal` stores exact goal `text` (`<= 4000` chars, no NUL), `status`, `status_reason`, and timestamps.
- `goal_stage` records the stages associated with each goal.
- `task` stores bounded work fields (`title`, `purpose`, `scope`, `exclusions`, `result`, `completion_evidence`), `goal_id`, `stage_id`, `status`, `priority`, and timestamps.
- `task_tag` and `task_log` store task tags and task history.
- `blocker`, `decision`, and `evidence` store blockers, decisions, and observations with optional `goal_id`, `stage_id`, and `task_id` links.

## `0 proj` command surface

Project-specific commands name their project. The `proj` group also accepts `--root PATH` (defaulting to Click `ctx.obj` when a `Path`, otherwise the repository root).

```text
0 proj create NAME --objective TEXT
0 proj list
0 proj show NAME
0 proj handoff NAME
0 proj update NAME
0 proj archive NAME

0 proj goal list NAME
0 proj goal create NAME --text TEXT --stage STAGE [--stage STAGE...]
0 proj goal activate NAME GOAL
0 proj goal show NAME [GOAL]
0 proj goal text NAME [GOAL]
0 proj goal copy NAME [GOAL]
0 proj goal achieve NAME [GOAL]
0 proj goal block NAME [GOAL] --description TEXT --required TEXT
0 proj goal reopen NAME GOAL
0 proj goal cancel NAME [GOAL]

0 proj stage list NAME
0 proj stage create NAME STAGE_NAME --outcome TEXT
0 proj stage update NAME STAGE
0 proj stage achieve NAME STAGE --evidence EVIDENCE
0 proj stage add-dependency NAME STAGE DEPENDENCY
0 proj stage remove-dependency NAME STAGE DEPENDENCY

0 proj task list NAME
0 proj task ready NAME
0 proj task create NAME --title TEXT
0 proj task show NAME TASK
0 proj task list-logs NAME TASK [--limit LIMIT] [--since UNIX_TIMESTAMP]
0 proj task activate NAME TASK
0 proj task add-log NAME TASK MESSAGE [--kind TEXT]
0 proj task update NAME TASK
0 proj task complete NAME TASK
0 proj task block NAME TASK --description TEXT --required TEXT
0 proj task reopen NAME TASK
0 proj task cancel NAME TASK
0 proj task add-tag NAME TASK TAGS...
0 proj task remove-tag NAME TASK TAGS...

0 proj decision create NAME --summary TEXT
0 proj decision list NAME [--limit LIMIT] [--stage STAGE] [--task TASK] [--goal GOAL] [--no-task]
0 proj blocker create NAME --description TEXT --required TEXT --task TASK
0 proj blocker create NAME --description TEXT --required TEXT --goal GOAL
0 proj blocker list NAME [--status open|resolved|withdrawn|all]
0 proj blocker resolve NAME BLOCKER --resolution TEXT
0 proj evidence create NAME --claim TEXT
0 proj evidence list NAME [--limit LIMIT] [--stage STAGE] [--task TASK] [--goal GOAL] [--no-task]
```

### Read output and `--json`

Read commands and write commands accept `--json` (except `goal text` and `goal copy`). In text mode, collection commands (`list`, `goal list`, `stage list`, `task list`, `task ready`, `task list-logs`, `decision list`, `blocker list`, `evidence list`) render tables aligned by terminal display width (`wcwidth.wcswidth`) without trailing padding on the final column, always emitting a header row and `-` separator row. `escape_cell` renders `None` and `''` as `-`, `'-'` as `"-"`, sequences as comma-joined values, and strings with JSON escaping without outer quotes. `show` renders labelled `key: value` fields, while `goal show` and `task show` render labelled `key: value` fields alongside related tables.

`goal text` writes exact goal text via `click.echo`; `goal copy` writes `\x1b]52;c;<base64>\x07` directly to `sys.stdout` without a trailing newline.

`task list-logs`, `decision list`, and `evidence list` default to `--limit 20` (`LIMIT >= 1`). When more rows exist, text mode prints a `--limit` notice and `--json` emits `{"items": [...], "has_more": true}`. `blocker list` defaults to `open` and prints `Blockers (status=<filter>):`.

`handoff` derives the active goal, active task, and active stage; lists open blockers, blocked tasks, and blocked goals; selects focus in precedence order (`active` task -> newest `blocked` task `(updated_at DESC, id DESC)` -> `active` goal with `task_id IS NULL` -> newest `blocked` goal with `task_id IS NULL` -> none); caps focus-scoped decisions, evidence, and task logs at `5` (`HANDOFF_LIMIT`) with `(shown of total)` counts; omits empty related sections; reverses `task_logs` to chronological order in text mode; and shortens prose strings exceeding `1,000` characters (`HANDOFF_TEXT_LIMIT`) with `…`.

### Argument parsing

`parse_stage_ref` parses non-empty all-ASCII-digit tokens into positive integer stage IDs (rejecting `0`) and any other non-empty text into stage names; `create_stage` and `update_stage` reject stage names consisting solely of ASCII digits. `parse_goal_ref` accepts `active` or positive integer IDs. `task update --no-goal` clears a task's goal and rejects combination with `--goal`; `decision list` and `evidence list` reject combining `--no-task` with `--task`; `task list --tag` and `task ready --tag` return no rows when given blank filter text.

## Implementation boundaries

`proj/` is organized into four modules with an acyclic dependency graph:

- `proj/db.py` depends only on the Python standard library and owns `SCHEMA_VERSION`, `ProjectError`, text/name validation (`is_substantive`, `require_substantive`, `parse_project_name`), schema creation (`init_schema`, `connect_memory`, `init_project`), and `.tmp/` filesystem helpers (`open_project`, `create_project_db`, `archive_project_db`, `iter_project_dbs`).
- `proj/ops.py` depends on `proj.db` and the standard library and owns immutable `@dataclass(frozen=True, slots=True)` view/record types, `dataclass_to_dict`, pure status derivations (`derive_stage_status`, `derive_project_status`), reference parsers (`parse_stage_ref`, `parse_goal_ref`), and atomic connection-level operations (`read_handoff` and all project, stage, goal, task, blocker, decision, and evidence operations).
- `proj/fmt.py` depends on `proj.ops`, `wcwidth`, and the standard library (no SQLite or Click imports) and owns `HANDOFF_TEXT_LIMIT`, `escape_cell`, `shorten_cell`, `render_table`, `render_kv`, `limit_notice`, collection/detail formatters, and `render_handoff`.
- `proj/cli.py` depends on `click`, `proj.db`, `proj.ops`, `proj.fmt`, and the standard library (zero imports from `zero/`) and exports `project_group`, converting `ProjectError` into `click.ClickException`.

## Invariants

The project workflow preserves these invariants:

- all meaningful work occurs within one properly documented active task;
- a project may operate without a goal, but never with competing active goals;
- active identity is derived rather than selected by a second pointer;
- stage and project statuses are deterministic aggregates;
- task activation requires both its local boundary and the complete project and stage contracts;
- project re-chartering requires active work to end and open goals to be cancelled, and retires every current stage achievement;
- stage achievement depends on substantive, timely named evidence and is invalidated when a task or achievement-contract change removes its validity;
- open blocker context cannot drift from its target, and newly recorded decision and evidence context matches its linked task;
- the terminal outcome remains visible while methods adapt;
- blockers and uncertainty remain actionable; and
- completion is claimed only against the outcomes and evidence that actually establish it.

Commands and storage are operational mechanisms for these semantics, not a second definition of them.
