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

The task must also have a structured stage relationship and an applicable goal relationship, which is empty when the project is operating without a goal. Each prose field must contain substantive text. The database rejects activation when any field or the stage relationship is missing. After activation, it keeps every required field non-empty and prevents the task from losing its stage relationship. Changing an active task's boundary must precede work under the changed boundary.

Task completeness does not replace the project charter. Activation also requires substantive project objective, scope, non-goals, constraints, and acceptance evidence, together with a substantive name and outcome for the task's stage. Use an explicit value such as `None` when a required charter category has no items; an empty field means that the charter is unfinished. A project can be created and documented incrementally, but no task is ready or active until this gate passes. Once work has started, the charter cannot return to an unfinished state.

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

The objective, scope, non-goals, constraints, and acceptance-evidence fields are the stored activation gate for this charter. Each must contain substantive text. Initial stages and dependencies remain structured records rather than duplicated prose.

The charter gives work a stable purpose without prescribing every implementation detail. The project owns its method and may change it when evidence shows that the present path is ineffective.

An update to any charter field after execution has begun is an explicit re-charter. It requires the active task to end and every active, pending, or blocked goal to be cancelled. When the goal is also active in the agent harness, end that pursuit before cancelling the project goal. After replacing the charter, establish any replacement goal on both planes and verify their exact match before resuming meaningful work.

Re-chartering preserves the replaced charter in project history and invalidates every current stage achievement in the same transaction. The project then derives as unfinished until current-generation evidence establishes the stage outcomes under the replacement charter. This conservative field boundary avoids treating a fixed goal or evidence for an earlier terminal outcome, scope, authority, or acceptance contract as authority or proof for the replacement. Initial charter construction, before any task starts, does not create replacement history or invalidate achievement. An active or blocked pre-execution goal does not change that boundary: its charter fields can still be completed incrementally.

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

Goal text is canonical project data. It must contain non-whitespace text, is preserved exactly as submitted, and is limited to 4,000 characters.

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

Goal statuses are `active`, `pending`, `blocked`, `achieved`, and `cancelled`. At most one goal is active. `pending` means a previously activated goal was deferred without being blocked, cancelled, or achieved; its status reason identifies the goal that displaced it, and reactivation clears that reason. Goal creation constructs its row and stage set in one transaction and activates that never-before-activated row. The intermediate construction state cannot persist beyond that transaction. Its structured stage set then becomes fixed; later scope changes require a replacement goal. Cancellation is terminal. A pending goal can be activated explicitly; a blocked goal can reactivate through `goal reopen` or final-blocker recovery.

Activating a goal while another is active first returns any active task linked to the old goal to `pending`, records a handoff task log, and returns the old goal to `pending`. A goal-less active task remains active because it is compatible with either goal. `goal create`, `goal activate`, `goal reopen`, and final-blocker recovery use the same handoff. Their project-database changes are atomic: if activation fails, the old goal and task remain active. The command changes only project state; when the goal is also active in the agent harness, follow the two-plane activation procedure above.

An active goal may become achieved only with substantive goal-linked evidence, no active task, and no open goal blocker. Every fixed evidence entry must exist by the achievement time, and an achievement time cannot be in the future or precede the goal's start. The evidence set and achieved lifecycle timing cannot then be changed. Blocking or cancelling a goal also requires its active task to end.

## Derived lifecycle

Task status is the single stored execution status. Active stages, project status, and handoff selection are derived from task and achievement records; there are no active or current entity ID pointers.

### Tasks

Task statuses are:

- `pending`: available for further documentation or activation;
- `active`: the project's one execution boundary;
- `blocked`: unable to proceed while one or more task blockers remain open;
- `completed`: its required result has been established; and
- `cancelled`: intentionally ended without claiming completion.

Only a pending, fully documented task can be activated. It must have no open blocker, it must belong to a stage, and its stage dependencies must be achieved. A task linked to a goal requires that goal to be active. A goal-less task may run whether or not the project has an active goal.

Completing a task records the contributor's claim that its required result has been established against its `completion_evidence` criterion. That evidence can be an external observation or a project evidence record; the project plane does not evaluate it or require a linked evidence row. Record project evidence when later work must inspect the basis. Stage achievement has the separate named-evidence gate described under [stage achievement](#stages).

Activating another eligible task while one is active returns the old task to `pending` and activates the requested task in one transaction. The handoff appends a task-log entry and preserves the old task's first activation time and history, so it can be resumed later. An unsuccessful activation leaves the current task unchanged. `task ready` can list eligible pending tasks even while another task is active. Completing a task requires it to be active. Resolving the final task blocker returns the task to pending. Reopening a completed or cancelled task also returns it to pending. Cancelling a blocked task withdraws its remaining blockers rather than leaving a terminal task blocked.

Task activation and completion times preserve their causal order. A start time must be positive and no later than the current time. A completion time must be no earlier than the start and no later than the current time. A stage achievement cannot predate the completed task work on which it depends.

### Stages

Stage status is calculated in this precedence order:

1. `active` when any task in the stage is active;
2. `pending` when no task is active and any task is pending;
3. `blocked` when no task is active or pending and any task is blocked;
4. `achieved` when at least one task is completed, every other task is completed or cancelled, and a valid stage-achievement record exists;
5. `superseded` when the stage has tasks and every task is cancelled; and
6. `pending` when the stage is empty or completed work still lacks valid achievement evidence.

This order makes mixed states deterministic. Because only one task can be active, at most one stage can be active.

A stage-achievement record names one substantive evidence entry that belongs to the stage and existed when the claim was established. Creating it requires a complete project charter; a substantive stage name, outcome, and exit-evidence requirement; at least one completed task; and no pending, active, or blocked task in the stage. An achievement time cannot be in the future or precede its evidence.

A stage's outcome and exit-evidence requirement form its achievement contract. A task addition, movement, or status change that makes an achieved stage ineligible invalidates its achievement record in the same transaction. Changing either achievement-contract field does the same. Invalidation preserves the historical record and evidence but removes them from current status derivation.

Each stage has an achievement generation and records when that generation began. Evidence linked to a stage captures its current generation and cannot claim capture before that generation began. An achievement must use evidence from the current generation. Invalidation begins the next generation in the same transaction that preserves and invalidates the current achievement record. The generation distinguishes evidence captured after invalidation even when both display timestamps share one-second resolution.

To become achieved again, the stage must satisfy its tasks and use an evidence entry from the new generation that it has not used for an earlier achievement. Evidence captured before invalidation therefore cannot establish the changed contract, even when both records have the same timestamp.

An achievement cannot be invalidated while an active task belongs to a stage that depends on it. The dependent task must end before the upstream task or achievement contract changes. Moving a completed task into an achieved stage also re-evaluates chronology: a completion later than the current achievement invalidates it, while an equal timestamp remains valid. This keeps every dependency satisfied throughout the active task instead of committing a task whose activation conditions no longer hold.

A stage dependency is satisfied only by a valid achievement record. Dependency cycles are rejected, and a task cannot activate while one of its stage's dependencies is unachieved. A dependency also cannot be removed while a task in the dependent stage is active; changing that graph first requires the task to end.

### Projects

Project status is calculated from all stage statuses:

- `complete` when at least one stage is achieved and every other stage is achieved or superseded;
- `active` when any stage is active or pending;
- `blocked` when unfinished stages exist and all of them are blocked; and
- `active` when the project has no stages.

An all-superseded project remains active because cancellation alone does not establish its outcome. It must be re-chartered, given a stage that can establish the outcome, or archived without a completion claim. The stage graph must cover the terminal outcome. A project reaches `complete` through at least one evidence-backed stage outcome, not through a separately stored project-status transition.

## Blockers and evidence

A blocker is project state, not completion. Its description and exact decision or capability required must contain non-whitespace text. It also records the condition's impact and attempted resolutions.

Every blocker has one lifecycle target. A blocker with a task relationship targets that task; its stage and goal relationships are context and must agree with the task when present. A task cannot be reassigned while an open blocker's recorded context would disagree with the new relationship. A blocker without a task relationship must target a goal, and any stage context must belong to that goal. Stage-only and targetless blockers are rejected. Creating an open blocker moves only its target to blocked state. Resolving the target's last blocker returns a task to pending. It returns a blocked goal to active using the same handoff as other goal activations: any other active goal and its linked task become pending, while a goal-less active task remains active. Open blockers cannot be deleted; cancellation withdraws those that no longer govern work.

New evidence records substantive observations and their sources and results; its claim must contain non-whitespace text. Stage achievement identifies one supporting evidence entry. Goal achievement fixes the complete set of evidence linked to the goal at that transition. Tests, reviews, diagnostics, and diffs are evidence; none alone proves an outcome outside the contract it actually covers.

A decision or evidence record linked to a task captures the task's complete stage and goal context when the record is created. When a decision or evidence record is created through `0 proj`, the project service infers omitted stage and goal context from the linked task; service validation and SQLite triggers reject missing or conflicting context. The relationship snapshot is immutable. Later task reassignment does not rewrite the historical record.

An already-current database can contain explicit compatibility records whose original task context or substantive text was not established. These records remain readable without being treated as ordinary evidence or authority. The [operational project plane](#operational-project-plane) defines their current behaviour.

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

The state is not a diary. Task logs and evidence preserve useful detail, while the handoff remains a compact state estimate that lets a fresh operator or agent continue without private conversation history.

## Operational project plane

Each project is stored in a provisional SQLite database:

```text
.tmp/<project-name>.sqlite3
```

Project databases persist across sessions but remain outside published history. A project name is one path component without the `.sqlite3` suffix. Creating a project with an existing name archives the old database under `.tmp/archive/` before installing the new one.

The name must contain only printable characters and at most 200 characters. Spaces, quotes, leading hyphens, and shell metacharacters remain valid path-component text; generated recovery commands shell-escape the name and place it after an option terminator. Control characters are rejected so a project identity cannot create additional handoff lines. An existing database at such an address is left unchanged and rejected before open; controlled recovery must choose a supported address and update the filename and stored name together before ordinary commands resume.

The database is authoritative working state. `0 proj` is the supported write interface; tools may query SQLite directly. A raw SQLite write is not an alternative command API and does not reproduce command-owned logs, timestamps, state revisions, or feedback. Database checks, foreign keys, partial unique indexes, and lifecycle triggers still reject incoherent core relationships when a write attempts to bypass the command interface.

The project plane defines substantive text once: Python's Unicode `str.strip()` must leave at least one character. It registers that predicate with SQLite so command validation, canonical storage, and current-state validation make the same distinction.

The singleton project and project-state rows and all task, stage, and goal records cannot be deleted. The stored project name is immutable and must equal the database filename stem that addresses every command.

The project plane creates schema version 7. On open, it validates and migrates a version 6 database to version 7 in one transaction, preserving its project records, identifiers, relationships, and history while adding the `pending` goal state and activation transitions. An incompatible version 6 database is rejected before migration; a failed migration rolls back. Other schema versions are rejected without modification. Before returning a current-schema connection, the project plane checks database integrity, foreign-key relationships, singleton rows, project identity, every required table and index definition, the exact lifecycle-trigger set and definitions, and the current lifecycle relationships and authority claims. A same-named object with a different contract, an additional trigger, an additional index on a canonical table, or a central row contradiction is incompatible rather than sufficient. Additional tables and indexes confined to those tables do not change the lifecycle contract and are not rejected merely for existing.

Current lifecycle validation covers active cardinality and authorization; post-execution charter completeness; task boundaries and chronology; goal activation, blocking, cancellation, and evidence-backed achievement; open blocker and target agreement; decision and evidence context; stage contracts, generations, and dependency cycles; current stage-achievement relationships and chronology; and the generation order of invalidated achievements. A current-schema goal-construction row cannot survive an open as durable history. Recognized incomplete legacy construction state remains editable. A blocked goal whose final blocker was repaired without its release trigger remains available to `goal reopen`. This validation detects invalid rows left by an external writer that disabled enforcement and later restored the canonical schema. It does not reconstruct historical changes whose resulting rows satisfy the current contract.

Task logs and replaced project charters are append-only, while `legacy_lifecycle` compatibility history is immutable (rejecting inserts, updates, and deletes). Canonical goal text, activation history, fixed goal scope, blocker relationships, recorded decision and evidence context, evidence capture generation and time, task start and completion chronology, achieved-goal lifecycle timing, established stage achievements, and achievement evidence are immutable at their documented boundaries. Lifecycle operations create a replacement record or apply the defined terminal or invalidation transition instead of rewriting that history.

Some current databases contain compatibility history established before this implementation became current. `legacy_lifecycle` preserves removed status, timing, and selection values as immutable database history. It is intentionally absent from routine current-work projections and remains available to explicit read-only SQLite queries when its historical provenance matters.

A decision or evidence entry can mark its record-time task context as `legacy-unresolved`; an evidence entry can mark a blank claim as `legacy-blank`; and a task read can mark a blank title as `legacy-blank`. Text and JSON reads expose these record-level markers. Ordinary operations cannot create them or use them as current evidence. An incomplete compatibility charter remains outside current authority until every charter field is complete. None of this compatibility state authorizes active work or a current achievement.

## Database tables

The schema has one `project` row and these related records:

- `project` stores the charter, its context status, and timestamps; status is derived.
- `project_charter_history` preserves every charter replaced after execution began.
- `project_state` stores only the compact summary, next action, revision, and timestamps.
- `goal` stores exact goal text, lifecycle status, activation history, timestamps, and status reason.
- `goal_stage` records the stages advanced by each goal.
- `stage` stores intermediate outcome contracts, the current achievement generation, and when that generation began; status and other lifecycle timestamps are derived.
- `stage_achievement` preserves current and invalidated evidence-backed achievement claims and the generation each claim established.
- `legacy_lifecycle` preserves immutable status, timing, and selection compatibility history already present in a current database.
- `stage_dependency` stores the acyclic stage graph.
- `task` stores its structured boundary, relationships, priority, lifecycle status, and timestamps.
- `task_tag` and `task_log` store task metadata and append-only history.
- `decision`, `blocker`, and `evidence` store project reasoning and feedback. Decision and evidence rows expose record-time context status; evidence also exposes claim status and its stage generation.

## `0 proj` command surface

Project-specific commands name their project. `list` reports unarchived projects.

The forms below show the command groups and principal arguments. Use `0 proj COMMAND --help` or the relevant nested command's `--help` to see the options exposed for normal use.

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

### Read output

Read commands use a human-readable view by default. The collection commands `list`, `goal list`, `stage list`, `task list`, `task ready`, `task list-logs`, `decision list`, `blocker list`, and `evidence list` render deterministic tables with a header and separator even when there are no rows. `show`, `goal show`, and `task show` render records as labelled fields; related records appear in named sections with their counts. `handoff` renders a compact labelled summary. Each read command that supports JSON documents `--json` in its help; that option emits the full command result as JSON, including fields omitted from a concise human-readable table and handoff retrieval and truncation metadata.

Human-readable tables align each column by terminal display width to its longest header or displayed value. Stored text is escaped with JSON string escaping, without surrounding quotes, so embedded line breaks and control characters stay within one cell or field; printable non-ASCII text remains readable. Null and empty values display as `-`; a stored literal `-` is quoted as `"-"` so it remains distinguishable. A legacy-incomplete charter, unresolved record context, blank evidence, and blank task titles are visibly marked in text and JSON reads. `goal text` and `goal copy` are deliberate exceptions: `goal text` writes exact goal text (including ANSI escape sequences), and `goal copy` writes an OSC 52 clipboard escape sequence (`\x1b]52;c;<base64>\x07`) to standard output for OSC 52-capable terminals rather than accessing a host OS clipboard directly, both without table, field, or JSON formatting.

Task-log, decision, and evidence reads return at most 20 rows by default; `--limit` sets a different positive maximum. When a human-readable result reaches its limit, it says that more records may exist and how to request a larger result. JSON retains the same command data shape and limit; increase `--limit` when more rows are needed. `blocker list` defaults to open blockers and identifies its status filter in the text output. Pass `--status all` to read every blocker status.

`handoff` derives the active goal and task from their unique active statuses and derives the active stage from the task, reporting no blocked or terminal entity as active. Its bounded recovery projection identifies blocked tasks and goals, every displayed blocker's target and required resolution, and the task or goal whose decisions, evidence, and log entries are relevant; a blocked goal's displayed reason comes from its newest current open blocker rather than a copied historical description. The text handoff limits projected stored values and generated retrieval commands to 1,000 rendered characters without introducing false lines or fields, and generated recovery commands shell-escape arguments (including the project address) while placing every option before `--` so the name remains one positional argument. The handoff omits empty related-collection sections and caps each non-empty related collection at five displayed rows, reporting shown and total counts and providing a complete-data JSON retrieval command when rows are omitted; this bound applies to the handoff projection rather than to other collection reads. If a field value is shortened, the projection lists its full-value command, while handoff JSON preserves the full authoritative value alongside each shortened field's path, original character count, and exact retrieval command; the active-goal projection contains only the goal record rather than its related history.

### Argument types

Click parses `0 proj` arguments and options before command execution (rejecting malformed IDs, integers, union references, and finite choices), `cli.py` rejects `--goal` with `--no-goal` and targetless `blocker create` invocations, and `cli.py` runs `core.py` and `service.py` boundary parsers before `store.py` opens or migrates any database. The command help names each positional argument and option exposed for normal use; these domain rules apply wherever that name appears:

| CLI input                                                                                                                                                                                                                                                                                                                                              | Parsed domain value                                                                                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `NAME`                                                                                                                                                                                                                                                                                                                                                 | Printable single-component project name (`ProjectName`, at most 200 characters, without `/`, `\`, NUL, `.`, `..`, or `.sqlite3`), parsed before database open.                                                                                              |
| `STAGE_NAME` and substantive `TEXT` options (`create --objective`, `stage create --outcome`, `stage update --stage-name` and `--outcome`, `task create --title`, `task update --title`, `--description` and `--required` on `blocker`, `goal`, and `task`, `blocker resolve --resolution`, `decision create --summary`, and `evidence create --claim`) | Non-whitespace text (`SubstantiveText`, preserving surrounding whitespace and non-printable characters), parsed before database open when supplied; `goal create --text` (`GoalText`) additionally enforces the 4,000-character limit before database open. |
| `TAGS...` and `task create --tag`                                                                                                                                                                                                                                                                                                                      | Trimmed non-empty tag (`TaskTag`), parsed before database open (`task list --tag` and `task ready --tag` accept `str` filter text, trimming whitespace and returning no rows when blank).                                                                   |
| `MESSAGE`, `--kind`, `update` charter and state `TEXT` options, and optional prose `TEXT` options                                                                                                                                                                                                                                                      | Unchanged text (`str`); `--kind` accepts arbitrary text rather than a finite choice, and `update` charter fields are validated against charter rules during transaction execution.                                                                          |
| `TASK`, `BLOCKER`, `EVIDENCE`, `--task`                                                                                                                                                                                                                                                                                                                | Positive integer ID (`PositiveInt`).                                                                                                                                                                                                                        |
| `LIMIT`                                                                                                                                                                                                                                                                                                                                                | Positive integer (`PositiveInt`, minimum `1`).                                                                                                                                                                                                              |
| `PRIORITY`, `UNIX_TIMESTAMP`                                                                                                                                                                                                                                                                                                                           | Integer (`int`), including negative values (`bool` rejected at the service boundary).                                                                                                                                                                       |
| `--status` choice lists                                                                                                                                                                                                                                                                                                                                | Exact choice listed in that command's help (for example, `open`, `resolved`, `withdrawn`, or `all` on `blocker list`).                                                                                                                                      |
| Boolean flags (such as `--json`, `--no-goal`, and `--no-task`)                                                                                                                                                                                                                                                                                         | Boolean flag.                                                                                                                                                                                                                                               |

`STAGE`, `DEPENDENCY`, and `--stage` parse tokens composed exclusively of ASCII digits into positive stage IDs (`PositiveInt`) and any other non-empty text (including mixed names such as `stage-1` and non-ASCII numerals) into `StageName` values. Stage names composed exclusively of ASCII digits are therefore not addressable by name; `STAGE_NAME` when creating a stage accepts any `SubstantiveText`.

`GOAL` and `--goal` accept the exact keyword `active` or an ASCII-digit positive integer ID (`PositiveInt`). Omitting an optional positional `GOAL` selects the active goal. Omitting an optional `--goal` does not select it: the relationship stays unspecified, or unchanged for `task update`. Domain-level validation beyond argument syntax remains enforced at the boundary and by `service.py` before or during transaction execution.

### Command semantics

The command vocabulary uses `create` for project and entity records, `list` for collections, `show` for detailed project, goal, and task reads, and `update` for editable project, stage, and task data. `activate` selects a pending goal or eligible task. `block`, `cancel`, and `reopen` are shared goal and task lifecycle verbs. The command list above is the inventory for each project noun.

`0 proj create` requires a substantive objective and accepts the other charter fields shown by its help; those fields can be completed through `update` before execution. `goal create` also activates the new goal. Other `create` commands create their documented initial record state. Goals have no `update` command because their text and stage scope are fixed after creation, and `0 proj` exposes no update or delete commands for decisions or evidence (while schema triggers keep recorded decision and evidence relationship snapshots and achievement-linked evidence immutable as documented in the [operational project plane](#operational-project-plane)).

`task create` and `task update` accept `--purpose`, `--scope`, `--exclusions`, `--result`, and `--completion-evidence`. A task may be created before those fields are complete, but `task activate` enforces all of them. `task update --no-goal` removes a task's optional goal relationship; it cannot be combined with `--goal`. `task ready` reports pending tasks whose project charter, stage contract, task documentation, blockers, goal relationship, and stage dependencies permit activation, even when another task is active; activating one hands the current task back to pending.

`stage add-dependency` adds a prerequisite edge, and `stage remove-dependency` removes one when the dependent stage has no active task; removal rejects a missing edge or an active dependent task without changing the graph. `task add-tag` and `task remove-tag` add or remove free-form metadata. `task add-log` appends history, while `task list-logs` reads it; task logs are append-only.

`task complete` records a task result claim. `goal achieve` and `stage achieve` record evidence-backed outcomes, so these verbs are not interchangeable. `goal reopen` reactivates a repaired blocked goal, while `task reopen` returns a completed or cancelled task to pending. `goal block` accepts an active goal only when it has no active linked task; `task block` accepts a pending or active task. Each command creates an open blocker and transitions its target to blocked. `blocker create` is the explicit-target form; it can record an additional blocker on a target that is already blocked. `blocker resolve` records its resolution and may reactivate a goal after its final blocker is resolved.

The other specialized verbs also identify distinct results: `task ready` filters eligible tasks, and `goal text` and `goal copy` preserve exact goal text. `handoff` is the bounded current-state and recovery projection; `show` reads the project charter and compact state; `archive` moves an unarchived database. Project status is derived data, not a separate command. `goal create` and goal activation change only project state; when an agent harness also pursues a goal, follow the [two-plane activation procedure](#goal-activation). Goal-focused decision and evidence commands use `--no-task` to recover the same goal-level set rather than including task-linked history; `--no-task` cannot be combined with `--task`.

Activating, completing, blocking, reopening, or cancelling a task records its transition in the task log. Task-log reads are bounded and may be filtered by a Unix timestamp. Tags remain free-form metadata and do not replace authoritative status, stage, goal, blocker, or evidence records.

## Implementation boundaries

The `proj/` package separates domain values, database contracts, lifecycle operations, provisional storage, output formatting, and CLI dispatch along a strict acyclic dependency graph. At the base of that graph, `core.py` depends only on the Python standard library and owns domain constants, literal status types, `ProjectError`, the `UNSET` sentinel, dataclass serialization (`dataclass_to_dict`), and boundary value types (`SubstantiveText`, `ProjectName`, `GoalText`, `PositiveInt`, `StageName`, `TaskTag`, `CharterInput`, `parse_stage_reference`, and `parse_goal_reference`). Above it, `schema.py` depends only on `core.py` and owns SQLite connection setup, schema version 7 creation, atomic version 6-to-7 migration, canonical trigger contracts, and persisted-state validation.

Transactional domain operations live in `service.py`, which depends only on `core.py` and `schema.py` with no store or filesystem dependency; it owns immutable projection records, filter and patch parsers (`GoalStages`, `RecordListFilter`, `TaskPatch`, and companion patch/focus records), pure status derivations, and connection-level project read and write operations. Persistence lives in `store.py`, which depends on `core.py`, `schema.py`, and `service.py` to own the storage backend protocol, OS filesystem backend, `.tmp/` project addressing, atomic project creation and archiving, listing, and validated connection opening.

Presentation and CLI wiring sit above the core engine without circular imports or database leakage. `render.py` depends only on `core.py` and `service.py`, with no SQLite or Click dependency, and formats deterministic tables, labelled detail views, `--limit` truncation notices, and bounded handoff projections; command-line shell quoting belongs to `cli.py` rather than `render.py`. At the top of `proj/`, `cli.py` depends on `core.py`, `service.py`, `store.py`, and `render.py`, with no Python import dependency on the [command plane](../zero/README.md). `cli.py` resolves `ProjectStore` from `--root`, Click's context (`ProjectStore` or repository `Path`), or the repository root, parses arguments and runs pre-open boundary validation before opening or migrating any database, dispatches `0 proj` commands to `store.py` and `service.py` while converting `ProjectError` into `click.ClickException`, serializes `--json` responses, builds shell-escaped `0 proj` recovery commands, and wires `render.py`, exact `goal text` output, and OSC 52 clipboard output (`goal copy`).

## Invariants

The project workflow preserves these invariants:

- all meaningful work occurs within one properly documented active task;
- a project may operate without a goal, but never with competing active goals;
- active identity is derived rather than selected by a second pointer;
- stage and project statuses are deterministic aggregates;
- task activation requires both its local boundary and the complete project and stage contracts;
- project re-chartering preserves the replaced contract, requires active work to end and active, pending, or blocked goals to be cancelled, and retires every current stage achievement;
- stage achievement depends on substantive, timely, generation-current named evidence and is invalidated when a task or achievement-contract change removes its validity;
- open blocker context cannot drift from its target, and newly recorded decision and evidence context is complete and immutable;
- the terminal outcome remains visible while methods adapt;
- blockers and uncertainty remain actionable; and
- completion is claimed only against the outcomes and evidence that actually establish it.

Commands and storage are operational mechanisms for these semantics, not a second definition of them.
