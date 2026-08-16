# Project Workflow

## Purpose

Meaningful Pentagram work belongs to a project. A project is the durable unit of work that carries an outcome across tasks, sessions, failures, and changes of plan.

The project is not inert ceremony around the work. It is a control system that keeps work oriented toward a real result and supplies the information and authority needed to realize that result.

All project text is documentation. Charters, goals, stages, tasks, decisions, logs, evidence, summaries, and handoffs must follow the standards in [`doc/`](../doc/README.md). Provisional storage changes durability, not the obligation to write text that is true, well structured, and usable.

## The project as a control system

A project compares the desired state with the observed state and selects the next action that most usefully closes the gap.

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

This loop makes the desired behaviour easier without making the path brittle. The method can adapt when evidence changes; the outcome remains the anchor.

## Project, goal, stage, task, and session

- A **project** owns a terminal outcome and remains meaningful across sessions.
- A **goal** is an optional durable statement of a project's current desired result and boundary. A project has at most one active goal. Goal activation makes the same canonical goal active in both the project and the agent harness; only then does pursuit begin. The project control plane continues to own execution.
- A **stage** owns an intermediate outcome that advances or de-risks the project.
- A **task** is a bounded action that advances a stage or produces information needed for the next decision.
- A **session** is a temporary execution window. It may complete tasks, but it does not own the project’s meaning or completion.

The distinction prevents activity from becoming a substitute for progress. A task such as “write `proj/README.md`” is not itself an outcome. The associated outcome is that the project workflow is defined clearly enough to guide and evaluate real work.

### Goals

A substantial session has an active project. The project may also have one active goal, just as it has a current stage, task, summary, and next action. A goal is useful when a desired result and exact boundary need to persist across sessions; it provides that durable focus while the project control plane plans and sequences stages, tasks, and next actions.

Goal text is a literal delegation of operator intent, not a summary of the subject or a proposed plan. It must preserve the requested result, scope, authority, and exclusions without strengthening, weakening, or filling gaps in the request. If the intended delegation cannot be stated clearly from current authority and project state, resolve the uncertainty before activating a goal.

A goal can name source documents, reports, diffs, research, or other reference material without granting that material authority. State whether a reference governs, supplies a project input, records evidence, or provides context. When discussion has accepted, rejected, or changed proposals from a reference, the goal captures the resulting operator decision or delegates to the project records that do; it never turns the reference itself into a requirements document without explicit authority.

The goal delegates detailed control to named, truthful project state. It can rely on the current stage, task, decisions, and other project records for evolving detail instead of freezing a partial interpretation into a second control plane. The goal must still state enough of the bounded result, scope, and completion evidence to remain inspectable without reconstructing private conversation.

A good goal therefore:

- names a bounded result that can be inspected and declared complete;
- identifies the project state that owns detailed requirements and execution;
- states exact scope through the relevant stage, task, artifact, behaviour, or evidence boundaries;
- preserves the authority and role of every consequential reference;
- names important exclusions so a plausible adjacent result is not mistaken for success;
- leaves decomposition, sequencing, alternative approaches, and ordinary recovery to the project control plane; and
- says what may genuinely block the line of progress.

The project is designed to unblock itself. Ordinary uncertainty, a failed approach, incomplete decomposition, a task-level blocker, or the need to replan is not an acceptable goal blocker. A goal blocker is exceptional only when progress requires a decision that changes the charter or scope, crosses a higher-priority or safety boundary, requires unavailable destructive, external, privileged, or irreversible authority, or depends on information or capability outside the project’s control. The blocker record preserves what was tried, what is affected, and the exact decision or capability required.

Goal text is canonical project data. It must be non-empty, is preserved exactly as submitted, and is limited to 4,000 characters. The command plane measures the submitted text and rejects an over-limit value with its measured length; it never truncates or silently normalizes the text. The limit exists because agent harnesses may reject prompts longer than 4,000 characters.

Goal activation is a two-plane transition. It is complete only when the project contains the active canonical goal and the agent harness is actively pursuing that exact goal. `0 proj goal set` establishes the project plane; it does not activate the harness or complete activation. A request to **activate** a goal includes both planes unless the operator explicitly narrows the request.

Activate a goal in this order:

1. Set and inspect the canonical project goal. Confirm that the current stage, task, summary, next action, decisions, and relationships are truthful for the delegation.
2. Read the exact goal text with `0 proj goal text NAME`.
3. Activate that exact text in the harness.
4. Read both active goals and verify that they match before beginning pursuit.

Do not start goal work between these steps. Do not activate an approximate goal with the intention of repairing it during execution: an active harness goal may not support replacement, and work under different project and harness objectives has no coherent authority.

If the harness cannot activate a goal, ask the operator to run `0 proj goal copy NAME` and activate the copied text. Wait for that handoff to complete before beginning pursuit.

A missing goal on either plane is an activation mismatch. Different goal text is also a mismatch. Stop work until one canonical goal is active on both planes. When the records disagree, supersede the incorrect project goal without claiming achievement, end the incorrect harness goal through its supported lifecycle or operator control, and activate the corrected canonical text. Never continue by silently choosing one objective or blending both.

The project control plane owns the goal’s planning, sequencing, stage and task relationships, lifecycle, blocker/unblocking behaviour, evidence, and status. Goal completion is not project completion. A goal can be achieved while the project continues through later goals or stages; project completion still requires the project charter’s terminal outcome and evidence.

Every meaningful task must either advance the project toward its outcome or produce information that changes the next project decision.

## Project charter

Before execution, a project establishes a charter containing:

- the problem or opportunity being addressed;
- the terminal outcome in observable terms;
- the scope and explicit non-goals;
- constraints, invariants, and authority boundaries;
- the evidence required to establish completion;
- the initial stages and their dependencies;
- known uncertainty, risks, and external dependencies.

The charter gives work a stable purpose without prescribing every implementation detail. The project owns its method and may change it when evidence shows that the current path is ineffective.

## Project authority

Unless an exceptional boundary applies, the project has full authority to make the decisions and resolve the blockers necessary to realize its charter. This includes choosing designs, decomposition, sequencing, tradeoffs, verification methods, and responses to failed work.

Ordinary uncertainty is not an escalation condition. The project should first inspect further, choose an alternative, revise its plan, or record a tradeoff.

Exceptional boundaries are decisions that:

- materially change the terminal outcome or charter;
- cross a higher-priority instruction or safety boundary;
- require destructive, external, privileged, or irreversible authority that the project does not possess; or
- depend on information or capability outside the project’s control.

The project may freely revise its method. A change to its outcome or authority requires an explicit re-charter rather than silent drift. Project authority ends when the project closes.

## Staged outcomes

Projects are commonly staged with intermediate outcomes. Stages are outcome contracts, not activity checklists. Each stage defines:

- a meaningful state it must produce;
- how that state advances or de-risks the terminal outcome;
- conditions for starting the stage;
- evidence that establishes the stage outcome;
- dependencies on other stages; and
- its current state: pending, active, verifying, achieved, superseded, or blocked.

Stages are usually a dependency graph rather than a rigid linear sequence. They may be split, reordered, added, removed, or revisited when project evidence warrants it. A completed stage must leave behind a usable artifact, capability, decision, or reduction in uncertainty—not merely a record of activity.

For example, a project to improve Pentagram work might have these outcomes:

1. The workflow semantics are defined and agreed.
2. A durable project control surface exists and is navigable.
3. Operator and agent workflows use that control surface.
4. A real project demonstrates that the workflow works.
5. Findings are reconciled into the durable system.

The final outcome remains the project’s completion criterion; intermediate outcomes provide useful control points and visible progress toward it.

## Operating lifecycle

The project lifecycle is a sequence of control decisions:

1. **Charter:** establish the problem, outcome, boundaries, authority, and completion evidence.
2. **Orient:** inspect the current system, relevant documentation, existing state, and constraints.
3. **Frame:** state the semantic change or intended result, invariants, boundaries, and unchanged behaviour.
4. **Plan:** choose stages, dependencies, next actions, and likely evidence.
5. **Execute:** perform the smallest coherent task within the current stage.
6. **Check:** inspect implementation or other results using evidence appropriate to the risk.
7. **Reconcile:** update documentation, decisions, stage state, and the next action to match what actually exists.
8. **Close:** verify the terminal outcome, preserve the handoff state, and record unresolved uncertainty or follow-up work.

The lifecycle is iterative. A failed check can return the project to framing or planning; new information can change the stage graph; a blocker can require a decision rather than more execution.

## Persistent project state

Project state preserves only information that changes future decisions. It should make the following visible:

- the current outcome and stage;
- the active goal and its exact canonical text;
- the current state and next bounded action;
- achieved outcomes and their evidence;
- decisions and their rationale;
- blockers, attempted resolutions, and escalation needs;
- changed assumptions, risks, and dependencies; and
- completion status and unresolved uncertainty.

Project state is not a diary of every action. It is a compact, truthful state estimate that lets a fresh operator or agent session continue the control loop without relying on private conversation history.

## Blockers and completion

A blocker is project state, not project completion. When blocked, the project records the concrete condition, what has been tried, what decision or authority is missing, and what can proceed independently. The project resumes when the condition changes or the project chooses a valid alternative.

A project is complete only when:

- the terminal outcome is achieved;
- the required evidence has been inspected and is sufficient;
- affected documentation and durable state describe reality accurately; and
- remaining uncertainty, risks, and follow-up work are explicitly recorded.

Passing a test, producing a diff, or completing a task is evidence about the project. None of those facts alone proves that the project reached its outcome.

## Invariants

An effective project workflow preserves these invariants:

- meaningful work has a project-level purpose;
- the terminal outcome remains visible during execution;
- every task advances an outcome or changes the next decision;
- plans may adapt, but outcome changes are explicit;
- stage transitions depend on evidence rather than activity;
- blockers and uncertainty remain visible and actionable;
- project state is updated at meaningful boundaries; and
- completion is declared only against the defined outcome and evidence.

The project workflow defines these semantics. Commands, file conventions, and automation are operational mechanisms that must support them rather than become a substitute for them.

## Operational project plane

Each project is stored in its own provisional SQLite database at:

```text
.tmp/<project-name>.sqlite3
```

Project databases are intentionally not Git-tracked. They contain working state that is useful across sessions but remains provisional until the project reconciles its durable conclusions into the repository’s documentation, code, tests, or other permanent artifacts.

Multiple projects may be active at once. A project name is unique among the active database files. When a new project is created with an existing name, the existing database is moved to `.tmp/archive/` with its filesystem ctime appended to the base name before the replacement is created. Creating a project never overwrites an existing project database.

Project names are single path components without the `.sqlite3` suffix. The name is used as the active database filename and is therefore validated before filesystem operations.

The project database is the authoritative working state for that project. `0 proj` provides common reads and writes, while agents and other tools may use direct SQLite queries for reports or operations that do not warrant a dedicated command.

## Project database tables

The schema has one project record and these related records:

- `project` stores the charter, terminal outcome, boundaries, acceptance criteria, lifecycle status, and timestamps.
- `project_state` stores the compact current control state: active goal, current stage, current task, situation summary, next action, and state revision.
- `goal` stores canonical goal text, lifecycle status, timestamps, and an optional status reason. The project-state pointer identifies the one current active or blocked goal.
- `goal_stage` records every stage a goal advances, so a goal can cross stage boundaries without changing the project objective.
- `stage` stores intermediate outcome contracts and their lifecycle state.
- `stage_dependency` stores the stage dependency graph.
- `task` stores bounded work, lifecycle timestamps, priority, purpose, and its optional goal relationship.
- `task_tag` stores a free-form string tag list for each task.
- `task_log` stores the append-only running log for task activity and transitions.
- `decision` stores decisions, rationale, alternatives, consequences, and its optional goal relationship.
- `blocker` stores concrete blocking conditions, attempted resolutions, required decisions or capabilities, and its optional goal relationship.
- `evidence` stores observations and sources supporting goal, stage, or project outcomes.

Current state is kept separately from history so status and handoff reads stay small and direct. Logs and evidence preserve useful detail without requiring every read to load the project’s full history.

## `0 proj` command surface

The command surface supports common project-plane operations. Every command selects a project explicitly by name because multiple projects may be active.

```text
0 proj create NAME
0 proj list
0 proj status NAME
0 proj show NAME
0 proj handoff NAME
0 proj update NAME
0 proj archive NAME

0 proj goal list NAME
0 proj goal set NAME --text TEXT --stage STAGE [--stage STAGE...]
0 proj goal show NAME [GOAL]
0 proj goal text NAME [GOAL]
0 proj goal copy NAME [GOAL]
0 proj goal achieve NAME [GOAL]
0 proj goal block NAME [GOAL]
0 proj goal reopen NAME [GOAL]
0 proj goal supersede NAME [GOAL]

0 proj stage list NAME
0 proj stage add NAME
0 proj stage update NAME STAGE
0 proj stage start NAME STAGE
0 proj stage achieve NAME STAGE
0 proj stage depend NAME STAGE DEPENDENCY

0 proj task list NAME
0 proj task ready NAME
0 proj task add NAME
0 proj task show NAME TASK
0 proj task logs NAME TASK
0 proj task start NAME TASK
0 proj task log NAME TASK MESSAGE
0 proj task update NAME TASK
0 proj task complete NAME TASK
0 proj task block NAME TASK
0 proj task reopen NAME TASK
0 proj task tag NAME TASK TAG...
0 proj task untag NAME TASK TAG...

0 proj decision add NAME
0 proj decision list NAME
0 proj blocker add NAME
0 proj blocker list NAME
0 proj blocker resolve NAME BLOCKER
0 proj evidence add NAME
0 proj evidence list NAME
```

`goal set` creates one active project goal and requires at least one stage reference. It establishes only the project plane; goal activation remains incomplete until the exact text is active and verified in the harness. It rejects a second active or blocked project goal rather than silently replacing the current line of progress. `goal show` returns the goal and its linked stages, tasks, blockers, and evidence. `goal text` returns only the exact stored text for harness activation. The optional `GOAL` reference is a numeric goal id; when omitted, reads and lifecycle commands select the current project goal. `goal achieve` requires goal-linked evidence, `goal block` requires a concrete exceptional blocker record, `goal reopen` requires all of that goal’s blockers to be resolved or withdrawn, and `goal supersede` ends the line without claiming that its result was achieved.

`goal copy` emits an OSC 52 sequence containing the exact UTF-8 goal text. It does not print a reformatted substitute and does not mutate the database. The operator fallback for project `sys`, for example, is exactly:

```text
0 proj goal copy sys
```

The command plane reports an over-limit goal as an error containing both the 4,000-character limit and the measured length, for example: `Goal text is limited to 4,000 characters; received 4,001.`

The command plane is implemented in `zero/`; this project subsystem is implemented in `proj/project.py` with its shadow test in `proj/project_test.py`. `0` is the working command name and `zero` is the installed long-form alias. The former `pt` command is not retained.

`status` and `handoff` produce compact, high-signal views. They include the project identity, outcome, active goal, current state, current stage and task, next action, open blockers, and recent decision or evidence pointers without duplicating retrievable history. Detailed reads expose stored records, and list commands provide bounded reads where appropriate. Machine-readable output is available for agent use.

Commands validate the selected project even when an update carries no field changes; a missing project is an error rather than a silent no-op.

Starting a task records its start time. Completing, blocking, reopening, or otherwise changing task status records the state transition and appends to its running log. Task-log reads are bounded by default and can be limited or filtered by a Unix timestamp. Tags remain free-form metadata; they do not replace authoritative status, stage, blocker, or decision records.

A task with an open blocker cannot be started or moved to active status. A handoff current task must represent live work in active, verifying, or blocked status; completed, cancelled, and merely planned tasks remain discoverable through task reads but cannot be presented as the current execution point.

When a current task is completed or becomes planned after all blockers resolve, the project clears that handoff pointer rather than retaining stale work as current.

A stage cannot start until its dependencies are achieved, and dependency cycles are rejected. Achieving a stage requires its declared exit evidence and at least one recorded evidence entry. Completing a project requires acceptance criteria, recorded evidence, no open blockers, no unfinished tasks, and all stages achieved or superseded.

An active goal must link to one or more stages. A task, decision, blocker, or evidence entry may link to a goal; when a task or evidence entry also names a stage, that stage must be one of the goal’s linked stages. Only one goal is active for a project. Resolving the last blocker for a blocked goal returns it to active status, so ordinary unblocking does not require a second control plane or an undocumented agent convention.

Project updates validate the resulting values atomically, so an update may provide acceptance criteria and complete the project in the same operation.
