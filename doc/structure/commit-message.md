# Commit message

Within [structure](README.md), a commit message is the durable technical narrative of one complete contribution. In Jujutsu, it is the final description of the squashed change that becomes the published Git commit. The subject names the resulting change, and the body explains the intent, architecture, findings, and impact needed to understand it.

The format makes repository history ergonomic to scan, deterministic for readers and tools to interpret, and efficient to use as a source of established design context.

This document defines the final message format. The [development-change workflow](../../source-control.md#maintain-distinct-changes) defines mutable changes and temporary `wip:` descriptions. The [publication workflow](../../source-control.md#publish-a-branch) defines final squashing, bookmarks, validation order, and publication. The [Pentagram agent system](../../sys.md) adds agent-specific authority.

## Subject line

The first line is a Conventional Commit subject. Use one of these forms:

```text
<type>: <summary>
<type>(<scope>): <summary>
<type>!: <summary>
<type>(<scope>)!: <summary>
```

The type identifies the contribution's principal effect:

- `feat` adds a developer-visible capability;
- `fix` corrects incorrect behaviour;
- `doc` changes documentation without changing implementation behaviour;
- `perf` improves performance without an intended semantic change;
- `refactor` changes implementation structure without an intended behaviour change;
- `style` changes formatting or other non-semantic presentation;
- `test` changes tests or test infrastructure;
- `chore` performs repository maintenance that does not fit another type;
- `ci` changes continuous-integration or build automation; and
- `revert` reverses a previous change.

Do not introduce additional types. Choose the type from the contribution as a whole, not from the last edit or the largest file category.

The optional scope names a stable subsystem or surface when the name makes the contribution easier to identify. Omit the scope when the change crosses boundaries or the added label would merely repeat the summary.

The optional `!` marks an incompatible change. Place `!` immediately after the type or closing scope. The narrative body explains the affected contract, consequence, and required migration or recovery.

The summary is a concise imperative phrase that states the contribution. Name the resulting capability, correction, or system change rather than the editing activity. Do not end the summary with a period, repeat the type as prose, or describe the contribution as a file list.

The complete subject line must not exceed 72 characters. The limit includes the type, optional scope, optional `!`, punctuation, spaces, and summary. Rewrite the summary or remove an unnecessary scope instead of abbreviating a concept until it becomes unclear.

## Narrative body

Separate the subject from the narrative body with one blank line. The body is a technical narrative of the complete commit, written for a contributor who has the repository but not the authoring session.

Wrap body prose at 72 characters per line, including prose in list items. Only a line made entirely of one exact literal may exceed the limit. The checker recognizes a URL without spaces, a shell command whose first two characters are a dollar sign and a space, a token-shaped path or identifier without spaces, or a quoted literal enclosed in backticks or quotation marks. A line of prose containing a literal remains subject to the limit.

Lead with why the change was necessary and the outcome it produces. Then explain the design relationships needed to understand the result. Include whichever of these concerns carry decision-relevant information:

- **Intent:** the problem, constraint, or opportunity and the resulting outcome;
- **Architecture:** important boundaries, data flow, models, and design decisions;
- **Findings:** non-obvious behaviour, consequences, or discoveries established while completing the work; and
- **Impact:** compatibility, resource behaviour, risks, migration, recovery, and implications for later work.

These concerns are a content model, not required headings. Arrange the body in the order needed to understand the contribution. Use paragraphs, lists, or short headings when they reveal the relationships clearly.

State governing decisions and causal relationships, not a chronology of the authoring session. Do not substitute a file inventory, test transcript, or generic claim that documentation and tests were updated. Mention specific files, commands, or evidence only when they help explain the architecture, establish a consequential fact, or make validation boundaries clear.

The body must agree with the complete commit. Distinguish current behaviour from aspiration, established findings from inference, and resolved work from remaining risk or uncertainty. A commit message preserves the reasoned result; it does not replace review of the diff or governing documentation.

## Repository portability

A commit message must remain accurate and useful in any repository checkout. Use repository-relative paths and stable system names. Describe behaviour and decisions without depending on one machine, home directory, editor, chat, or temporary project artifact.

Do not identify the current operator, refer to personal files, or record provisional state from `.tmp/`. Do not use phrases such as “in this session,” “the current conversation,” or “the agent found” when the durable fact can be stated directly.

Name external systems when they materially affect the contribution, but keep the local consequence understandable without access to transient external state. Record unresolved uncertainty only when the uncertainty remains part of the committed result.

## Prepare the message

The format and preparation process are normative. The [publication workflow](../../source-control.md#publish-a-branch) owns squashing, message application, and final validation. The [Pentagram agent system](../../sys.md) governs agent authority and isolation.

Every final message requires a factual audit by at least one fresh independent subagent. After the contribution is merged, its commit and message are immutable repository history; correcting either requires later history rather than changing that record in place. The audit therefore establishes the message from the facts of the finalized change rather than from the authoring conversation. The coordinating contributor remains responsible for verifying the evidence and writing an accurate message.

Scale the audit without omitting it. One subagent can inspect the complete diff for a small, coherent contribution. Use separate logical clusters and additional subagents when the contribution's consequence, complexity, size, unfamiliarity, conflicting evidence, or unresolved uncertainty makes independent investigation materially useful. The assignments must collectively account for every changed line. Proportionality governs the breadth and depth of investigation, the number of subagents, the detail of their reports, and the need for further independent passes; it does not remove the first independent audit.

### Establish the audit boundary

1. Squash the branch contribution into one change on top of its parent as the publication workflow requires.
2. Identify the exact `PARENT` and finalized `CHANGE`. Inspect the complete Git diff and statistics from `jj diff --git --stat --from PARENT --to CHANGE`, and account for every changed file.
3. Give one subagent the complete diff or divide it into coherent logical clusters. Write each assigned diff under `.tmp/` with `jj diff --git --from PARENT --to CHANGE -- FILESETS`, omitting `FILESETS` only for the complete diff. Record the exact revisions in the assignment. Inspect each file before assignment and keep it unchanged while the audit is active. The assignments must collectively cover the complete change.

### Run the independent audit

Start each subagent without inherited authoring conversation or project conclusions. Tell the subagent not to read active project state or run `0 proj`. Give it the diff path, resulting repository context, exact responsibility, and required report without supplying a desired conclusion or draft message.

The assigned diff bounds responsibility, not investigation. The subagent follows governing documentation, implementation, tests, callers, consumers, and tools far enough to establish:

- the changed lines and resulting behaviour;
- the intent, rationale, authority, and evidence for each material change;
- affected boundaries, relationships, compatibility, and resource behaviour;
- consequential findings or problems; and
- unresolved uncertainty and the evidence needed to resolve it.

The report records its diff coverage and identifies anything it could not establish. A report with no finding is evidence of investigation, not proof that the contribution is correct.

### Write from established facts

1. Verify the reports against their cited sources and diff regions. Resolve discrepancies, repair problems, and keep unsupported or conflicting claims out of the message. If the audited parent-to-change diff changes, return to [establish the audit boundary](#establish-the-audit-boundary), reconcile complete coverage, and repeat the independent work for every affected region. Resume synthesis only after current reports collectively cover every line of the current diff and their material claims have been verified.
2. Identify the contribution's principal effect. Draft the [subject line](#subject-line) from that outcome and build the [narrative body](#narrative-body) from the decision-relevant intent, architecture, findings, and impact established by the audit.
3. Audit every message claim against the finalized diff and its evidence. Read it as a contributor without the authoring context, remove transient or repeated material, and check grammar, wrapping, completeness, portability, and agreement with the final change. If this work changes the contribution, repeat the recovery loop in step 1 before continuing.
4. Validate the message under [quality](../quality/README.md), then apply it to the exact final change through the revision-targeted publication action.

Affected re-review can continue with the same subagent when its investigative context remains useful. Use another fresh subagent when the changed boundary or evidence calls for another independent judgement. Proportionality limits the repeated work to the affected regions and relationships; the coverage condition still applies to the complete current diff.
