# Commit message

Within [structure](README.md), a commit message is the durable technical narrative of one complete contribution. The subject names the resulting change, and the body explains the intent, architecture, findings, and impact needed to understand it.

The format makes repository history ergonomic to scan, deterministic for readers and tools to interpret, and efficient to use as a source of established design context.

This document defines the final message format. [Pentagram agent system: source control](../../sys.md#source-control) defines the branch workflow, the temporary `WIP` message, validation requirements, and the authorization boundary for commit operations.

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

Do not identify the current operator, refer to personal files, or record uncommitted state from `.tmp/`. Do not use phrases such as “in this session,” “the current conversation,” or “the agent found” when the durable fact can be stated directly.

Name external systems when they materially affect the contribution, but keep the local consequence understandable without access to transient external state. Record unresolved uncertainty only when the uncertainty remains part of the committed result.

## Suggested agentic process

The format above is normative. The following preparation process is suggested; the source-control workflow and authorization rules remain authoritative in [Pentagram agent system: source control](../../sys.md#source-control).

Because a commit message is the durable technical narrative of the complete contribution, preparing one requires an accurate account of the whole diff. The process separates fact-finding from narrative synthesis to reduce omissions, unsupported claims, and distorted emphasis. Independent subagents examine distinct logical parts of the diff. The coordinating contributor verifies their reports, resolves discrepancies, and writes and audits the subject and body from the established facts.

### Audit the contribution

1. Identify the exact parent and inspect the complete branch diff and statistics. Account for every changed file.
2. Group the changed files into logical clusters rather than by file type or editing order. Each cluster is one subagent's distinct review scope.
3. Write each cluster's diff to a separate file under `.tmp/` with ordinary shell redirection: `git diff ... -- ... > .tmp/...`. Together, the files must cover the complete branch diff. Put only the diff in each file.
4. Keep each diff file unchanged while its review is active. Regenerate the affected file after a material revision and before re-review.

### Review with independent subagents

Start every review subagent without inherited conversation context. Tell the subagent not to read active project state or run `0 proj`. Harnesses provide different isolation mechanisms; the required result is a new task context with no parent conversation or project conclusions. State task-specific context explicitly in the subagent task rather than relying on the parent conversation.

1. Give each subagent the repository-relative path to its distinct `.tmp/` diff file and ask for an exhaustive, factual account of that logical cluster. Do not include a desired conclusion or draft commit message.
2. Treat the diff as the boundary of review ownership, not the boundary of investigation. Inspect the changed repository files in context, and follow relevant local documentation, definitions, callers, consumers, tests, and tools far enough to understand the change and its consequences.
3. Require the subagents collectively to examine every changed line against the relevant governing documentation, implementation, tests, and other evidence. They establish what changed, why it changed, and what behaviour now results.
4. Keep the reviews independent until their reports are complete. Parallel execution can reduce delay, but independence matters more than concurrency.

Each subagent report must make these parts explicit:

- **Coverage:** identify the diff file and every changed file reviewed, confirm whether every changed line was examined, and name anything the subagent could not assess.
- **Change account:** explain each logical change, including important additions, removals, and resulting behaviour. Describe the mechanism when the mechanism is needed to understand the result.
- **Rationale and authority:** identify the intent, constraint, governing documentation, or other evidence that justifies each material change. Distinguish explicit evidence from inference and facts that could not be established.
- **System relationships:** explain affected boundaries, interfaces, data flow, and dependencies, including relationships that another diff cluster must account for.
- **Evidence:** identify the implementation, documentation, tests, checks, or other evidence that supports each material claim. Name missing, contradictory, or inconclusive evidence.
- **Consequences:** record non-obvious findings, compatibility and resource effects, benefits, deficiencies, risks, and follow-on implications.
- **Review findings:** for each problem, give its repository-relative location, supporting evidence, consequence, severity, and suggested resolution when known. State explicitly when no problem was found.
- **Uncertainty:** record unresolved questions and the additional evidence needed to answer them. State explicitly when none remains.

The coordinating contributor verifies and synthesizes the reports. Resolve discrepancies and disagreements explicitly, revise the contribution where needed, and repeat affected reviews after material changes. No changed behaviour should remain unexplained. A report with no findings is evidence of review, not proof that the cluster is correct.

Re-review may continue with the same subagent or start a new isolated subagent. Harnesses provide different continuation mechanisms. Regenerate the diff file for that logical cluster and give the reviewer its path rather than asking the reviewer to reconstruct changes from conversation. A continuing subagent may retain its own review context, but it must not receive the parent conversation, active project state, or other reviewers' reports before completing its independent re-review, and it must not run `0 proj`.

### Write from established facts

1. Read every subagent report and directly inspect the complete diff and relevant repository sources wherever needed to verify claims, understand relationships between clusters, and resolve uncertainty. Reports guide synthesis; they do not replace direct inspection.
2. Identify the contribution's principal effect and overall outcome.
3. Draft the [subject line](#subject-line) from that outcome rather than from the last edit or largest file category.
4. Build the [narrative body](#narrative-body) from the decision-relevant intent, architecture, findings, and impact established by the audit.
5. Remove repetition, transient context, raw file inventories, and claims the evidence does not support.

### Audit the message

1. Compare every factual claim with the diff, governing documentation, and relevant evidence.
2. Reinspect the complete diff and confirm that the narrative accounts for every decision-relevant concern.
3. Read the message from the perspective of a contributor who has the repository but not the authoring session.
4. Check the subject grammar and length, body wrapping, narrative completeness, repository portability, and agreement with the final diff.
5. Validate the complete message under [quality](../quality/README.md).
