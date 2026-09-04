# Tests

## Identify intent before design

**Task**

You are about to design documentation and code for a new repository command. Explain who is responsible for identifying the relevant intent and how governing authority bounds that responsibility. Define an environmental effect and state what must be identified before choosing changes, including how humans and agents affect those requirements. Explain how to bound the `total-environment` and where environment state and external encounter conditions belong. State what `env/` does and does not supply as intent. Cite the governing repository documentation.

**Assert**

- The answer says the author identifies desirable and important undesirable environmental effects for the subject before design or quality evaluation.
- The answer says the author identifies and applies intent within governing authority and cannot replace operator instructions, project decisions, or the subject's existing contract.
- The answer calls the author's judgement `intent`, not `environment intent`, `environmental intent`, or `local intent`.
- The answer says an effect can be an outcome, an invariant, or a transition and distinguishes a system result that execution permits from one it produces.
- The answer includes at least one desirable effect for humans and one for agents because the complete environment must benefit both participant classes.
- The answer distinguishes intended effects from interventions and does not treat `env/` as a source of predetermined intents.
- The answer follows causal reach to bound the `total-environment` and keeps state created or preserved by documentation and code in that environment.
- The answer uses `participant`, `situation`, and `encounter-noise` to state the applicable encounter conditions, keeps material external conditions outside the `total-environment`, and does not duplicate environment state through `situation`.
- The answer cites `env/intent.md` and the applicable definitions in `env/theory.md`.

## Scale environment-quality evidence

**Task**

A proposed change affects shared repository guidance used across many subjects. Explain how environment quality decides the strength and breadth of evidence to gather, where its investigation stops, and how it decides whether environment tests or review are worth performing. Cite the governing repository documentation.

**Assert**

- The answer assigns environmental risk to each effect in scope and explains that it governs evidentiary strength.
- The answer assesses risk from the credible material ways the effect can diverge from intent and how seriously those divergences matter.
- The answer assigns environmental leverage to each affected environmental surface across all effects and explains that it governs evidentiary breadth.
- The answer follows plausible causal paths from an affected surface and stops expanding the boundary when no further material effect can change through them.
- The answer weighs the evidence an environment test or review can add against its resource cost without describing the test run itself as risky.
- The answer cites the governing definitions and methods in `env/quality/`.

## Choose the test system

**Task**

A change contains documentation and an executable command implemented in `command.rs`. A `.test.md` companion must accompany `command.rs` rather than a Markdown subject. You need evidence that readers understand and act from the documentation, that actual command execution produces its required outcome, and that an agent encounter with the complete environment produces an intended action and applicable system outcome. Explain which Pentagram test system covers each need, what each can assert, and where the durable test contracts belong. Cite the governing repository documentation.

**Assert**

- The answer says documentation tests assert reader understanding or action attributable to documentation and never assert a result of actual system execution.
- The answer says implementation tests assert only results of actual execution and do not assert participant understanding or action.
- The answer places implementation tests in the same-directory shadow test file required by `code/README.md`, not in a `.test.md` companion.
- The answer says environment tests assert understanding or action from an encounter with the complete environment and may also assert an applicable system result.
- The answer distinguishes participant action from a system result by the proposition asserted, even when one execution trace supplies evidence for both.
- The answer explains that documentation and environment tests share the `.test.md` companion schema, can accompany any file type, and are distinguished by their task, assertions, and causal boundary rather than by the subject's file type. It maps a companion for `command.rs` to `command.rs.test.md`.
- The answer cites `doc/quality/test.md`, `code/README.md`, and `env/quality/test.md`.

## Design one environment for a destructive command

**Task**

A repository is adding `0 purge-cache TARGET` for humans and agents. The governing contract permits deletion only inside an explicitly selected repository-owned cache directory and requires the participant to know the resolved target and recovery consequence before deletion. The current proposal lets an omitted target mean the working directory, follows symbolic links, deletes before displaying the resolved path, and reports `done` after complete or partial deletion. Agents are encouraged to invoke it whenever a build fails. Before anyone edits or executes the proposal, produce a concise environment-engineering record that gives design a valid target and proposes one compatible environment for both participant classes. Cite the governing repository documentation.

**Assert**

- The record identifies subject-specific desirable environmental effects and important undesirable environmental effects before proposing interventions and keeps that intent within the supplied contract.
- The effects cover humans and agents, state whether the consequential system results are permitted or produced, and use applicable outcome, invariant, or transition forms.
- The record bounds the `total-environment` by material causal reach across documentation, command behaviour, defaults, feedback, state, and agent guidance rather than by an artifact inventory.
- The record classifies every material version, configuration value, and persistent fact created or preserved by documentation or code as environment state.
- The record assigns prior human experience and model tendencies to `participant`, task, location, and access conditions to `situation`, and only omission, substitution, or distortion in environmental information to `encounter-noise`. It keeps documentation or code causes in the `total-environment`.
- The proposed design applies both human and agent principles to one compatible environment, produces a desirable effect for both classes, and does not use a benefit to one to compensate for an important undesirable effect on the other.
- The record states causal hypotheses from specific environmental causes through human experience or agent context and actual execution to the intended effects.
- The design corrects the material frame distortions created by the unsafe default, early deletion, ambiguous success response, and unconditional agent guidance; it supports detection and recovery without relying on perfect participant attention.
- The proposed action surface refuses a missing target without deletion and makes the exact resolved target and recovery consequence available before commitment.
- Its feedback distinguishes complete and partial execution truthfully, and its agent guidance cannot make a generic build failure standing authority to purge.
- The proposed design prevents resolution or traversal from permitting deletion outside the explicitly selected repository-owned cache, including through a symbolic link.
- The result remains a concise application of principles rather than an inventory of prompting techniques, interface features, or possible files.
- The record cites `env/intent.md`, `env/theory.md`, both methods under `env/design/`, and the governing environment engineering index.

## Evaluate an unsafe preview environment

**Task**

An implemented `0 publish-preview TARGET` command is governed by a contract that a preview never changes a remote system. Its documentation describes a local preview and requires an explicit target. The CLI displays that target and writes the local preview, but its default configuration also synchronizes the result to the remote target. A documentation check passes, an implementation test covers only the local preview output, a documentation trial shows one agent understands the prose, and an environment trial shows one agent chooses an explicit target without executing the command. No evidence observes the remote effect. Evaluate the implemented environment: bound the effects and causal surface; assess each effect's risk from its credible divergence and seriousness; assess surface leverage; classify the existing evidence; decide whether environment testing and independent review add evidence that justifies their authoring, maintenance, context, compute, and system costs; choose the smallest next evidence adequate across all supported preview configurations; identify the repair boundary; and make the current environment-quality judgement. Do not edit files, execute the fictional command, or contact a remote system. Cite the governing repository documentation.

**Assert**

- The evaluation identifies the desirable preview effects and the important undesirable remote-change effect for humans and agents under applicable encounter conditions.
- The evaluation includes documentation, command implementation, default configuration, interface feedback, agent exposure, and remote state in the causally bounded `total-environment` without absorbing unrelated subjects.
- The evaluation assigns risk to each effect and uses credible divergence and its seriousness to choose evidentiary strength.
- The evaluation assigns leverage to affected surfaces, traces their plausible causal paths across every material effect they can change, and stops at a material boundary.
- The evaluation treats the documentation check, implementation test, documentation trial, and environment trial as evidence only for the properties, assertions, causal boundaries, and conditions they observed.
- The evaluation distinguishes the participant action of choosing or invoking a command from the system results that execution permits or produces.
- The evaluation prioritizes making every `publish-preview` execution path unable to invoke, enqueue, retry, or otherwise produce remote synchronization under any supported configuration and requires safe actual-execution evidence across that domain; it does not propose another prose-only trial as proof of the result.
- The evaluation chooses the smallest next evidence set that can make the complete post-repair evidence adequate. It does not choose an environment test or review whose expected contribution cannot justify its full resource cost, stops when further work cannot materially change the judgement, and does not assign risk to the runs.
- The current judgement is `fail` because the supplied implementation establishes a violation of the no-remote-change contract; it does not substitute passing bounded evidence or missing observation for a pass or inconclusive judgement.
- The result leaves the fictional and unobserved conditions explicit and cites the governing environment quality criteria, test, and review documents.
