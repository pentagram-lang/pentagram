# Tests

## Judge the named environment

**Task**

Use `env/quality/review-protocol.md` to review a named environment and cite the relevant sections. The handoff names a preview document, the command that implements it, the target-selection interface, and the state that the command can change. Its intent is a local preview with no remote change for humans and agents. The document says “local only”, but the command's default configuration synchronizes the preview to a remote target. The reviewer has no evidence that a participant has followed the instruction or that execution has changed the remote state. The handoff also names one `jj` change ID and states the participants, situations, causal model, evidence, and use. Report the problems and evidence the report should contain. If one of the required handoff inputs were absent or unclear, explain how the protocol handles that limitation. Do not propose repairs or decide what the project should do.

**Assert**

- The answer reads every named environmental surface as it currently exists and uses the supplied intent, design, local requirements, and environment criteria together.
- The answer reports a limitation rather than silently assuming the meaning of a missing or unclear required handoff input.
- The answer distinguishes state created or preserved by documentation or code in the `total-environment` from external participant, situation, and encounter-noise conditions.
- The answer treats the contradiction between the document and default execution as a present environmental problem even without an observed participant encounter.
- The answer keeps any claim about a participant sending data or an observed remote result separate from the contradiction and does not present it as observed without evidence.
- The answer inspects the complete diff for the single supplied change ID and explains that the diff does not replace or expand the named surface.
- The answer uses `--ignore-working-copy` with the diff so the read-only inspection does not snapshot current edits.
- The answer keeps linked or dependent surfaces out of scope unless named and records any relevant evidence limitation.
- The answer reports the environmental boundary, affected effect and causal path, governing intent or requirement, evidence, participant or system consequence, and uncertainty without proposing a repair.
- The answer keeps the review report as evidence and says that the reviewer does not issue the environment-quality judgement.
- The answer cites `env/quality/review-protocol.md` and `env/quality/criteria.md` as the governing guidance.

## Review current evidence again

**Task**

Use `env/quality/review-protocol.md` to conduct a re-review. The continuation prompt links to `env/quality/review.md#review-a-repair`, restates the complete original environmental surface, and identifies the command and preview document as updated. Read the current named environment from the beginning. The old report found a document/execution contradiction and also claimed an unsupported human consequence. Explain how the reviewer records the current evidence. Do not decide whether the repair succeeded or propose a repair.

**Assert**

- The answer checks every earlier finding against the current named environmental surface.
- The answer reuses the original identifier if the same contradiction remains and records in Coverage what the current environment and evidence establish if it no longer remains.
- The answer uses a new identifier for a distinct current problem.
- The answer does not infer resolution from the changed surfaces, the old report, or a repair suggestion.
- The answer keeps unsupported participant or execution consequences distinct from observed conditions and records uncertainty.
- The answer cites `env/quality/review-protocol.md` and the continuation prompt in `env/quality/review.md`.
