# Tests

## Prepare an environmental review

**Task**

Use `env/quality/review/README.md` to prepare an independent review of a preview environment. The environment includes a preview document, the command that implements it, its target-selection interface, and the state it can change. Humans and agents need to understand which target will be used, what the command will do, and whether a remote result can occur. The intended effect is a local preview with no remote change. The design hypothesis says that the document, interface, command, and feedback should make that boundary clear and enforce it. An existing default can make participants infer that remote synchronization is permitted; treat that as a material frame distortion the environment must correct. Existing documentation, implementation, and environment-test evidence covers only its own recorded conditions. Explain what the author decides before review and what the single handoff prompt contains. Cite the governing repository documentation.

**Assert**

- The answer says that the author uses each effect's credible divergence and seriousness to choose evidentiary strength and each affected surface's causal reach to choose breadth, then weighs that evidence against its full preparation, maintenance, and execution cost and chooses the smallest set that can make the complete evidence adequate.
- The answer treats the complete `total-environment`, including the documentation, command, interface, and relevant state, as one environmental surface bounded by the effects and their material causes, not only by changed files.
- The handoff is one chat prompt that names the environmental surface and tells the reviewer to report every present problem that makes it unclear or incorrect without proposing repairs.
- The handoff tells the reviewer not to read active project state or run `0 proj`.
- The handoff states the desirable and important undesirable effects, participants, situations, encounter noise, design hypothesis, any material frame distortions it must correct, relevant state, dependencies, credible divergences, seriousness, causal reach, existing evidence, evidence gaps, and intended participant use.
- The answer distinguishes state created or preserved by documentation or code in the `total-environment` from external participant, situation, and encounter-noise conditions, without duplicating environment state in `situation`.
- The answer says that the reviewer is a separate subagent with no inherited authoring conversation or project conclusions and receives the handoff rather than a private explanation.
- The answer says that one `jj` change ID may be supplied when the review focuses on a specific change and that it does not replace the current surface or expand its boundary.
- The answer cites `env/quality/review/README.md`, `env/quality/criteria.md`, and `env/quality/test.md` as the governing guidance.

## Evaluate an environmental report

**Task**

Use `env/quality/review/README.md` to evaluate this fictional report without editing files or executing a command. The named environment contains a preview label that says “local only” and a command whose default configuration also synchronizes the preview to a remote target. The reviewer reports that the label and default execution contradict the intended no-remote-change effect and suggests changing the intent to permit synchronization. The reviewer also claims that a human already sent confidential data because of the command, but cites only the conflicting label and configuration; no participant or execution evidence exists. Finally, the reviewer reports a broken link in an unnamed archive document. The active task permits evaluation only and authorizes no edits or external actions. Explain how the author evaluates the report, what remains a prediction or evidence gap, and what may happen next. Cite the governing repository documentation.

**Assert**

- The answer accepts the documented conflict with the no-remote-change intent as a present environmental problem.
- The answer ignores the suggestion to change the intent and derives any repair or preceding work from project context, intent, design, applicable standards, and the complete environment.
- The answer distinguishes the unsupported claim about a human sending data from the observed documentation and configuration conflict, and records the claimed consequence as unsupported or uncertain rather than as an observed effect.
- The answer treats the unnamed archive link as out of scope and uses project context to decide whether separate work is warranted without expanding the current review.
- The answer keeps the review report, finding dispositions, and environment-quality judgement distinct.
- The answer says that a report with no findings does not by itself establish that the environment passes.
- The answer makes no edits or external actions while evaluating the report under the stated evaluation-only task.
- The answer cites `env/quality/review/README.md` and `env/quality/criteria.md` as the governing guidance.

## Review a repaired environment

**Task**

Use `env/quality/review/README.md` to explain the next review after the author repairs the command and preview document. The author will reuse the same subagent. The original environmental surface remains under review, and the author has updated only the command and preview document. Explain what the continuation prompt says and how the author evaluates the new report. Do not propose a repair.

**Assert**

- The answer says that the author reuses the same subagent by default, at the author's discretion.
- The continuation prompt restates the full original environmental surface and identifies the updated command and preview document.
- The answer says that the author does not change the named review set or pass the repair argument or project decision to the reused reviewer.
- The answer says that if the author does not reuse the same subagent, the author starts a new review with the original handoff.
- The answer says that the author evaluates the new report against the current environment, intent, applicable standards, and project context rather than treating the repair or a no-finding report as proof of resolution.
- The answer cites `env/quality/review/README.md` as the governing guidance.

## Relate to other review processes

**Task**

Use `env/quality/review/README.md` to answer this task and cite the relevant section. An author prepares an environment change that includes a preview guide and an implementing command. Explain how environment review relates to other review processes and whether additional reviews are warranted.

**Assert**

- The answer explains that environment review is independent of documentation review and code review, and that no review type replaces or substitutes for another.
- The answer explains that environment review does not replace local documentation criteria for text as written or local code criteria for machine execution.
- The answer explains that a passing environment review does not establish that local documentation or code is clearly correct under its own standards.
- The answer explains that documentation in the environment may warrant an independent documentation review to judge whether that documentation accurately describes its subject and gives meaning a durable, navigable form as written.
- The answer explains that code in the environment may warrant an independent code review to judge whether that code faithfully executes its intended behaviour across its complete execution surface.
- The answer cites `env/quality/review/README.md` as the basis for the multi-process guidance.
