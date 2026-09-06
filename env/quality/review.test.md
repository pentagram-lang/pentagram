# Tests

## Evaluate observations and predictions

**Task**

Work read-only as the reviewee of an environment report. This fictional project basis and environment state are supplied fixtures, not active project state:

- The charter covers a preview-only export workflow. Sending data or changing credentials is excluded.
- The active task evaluates the report and authorizes no edits or external actions. There is no goal.
- The intended effect is that humans and agents can inspect a preview without being directed to send data.
- The interface shows “Preview only,” but its accompanying instruction tells the reader to invoke the send command. Both texts were inspected. There are no observations of anyone following that instruction or of any data being sent.
- An unrelated archive page has a broken link, verified during contextual reading.

The report contains these findings:

- F1, in scope: the preview label and send instruction conflict. The reviewer suggests sending data automatically before showing the preview so that the instruction becomes accurate.
- F2, in scope: humans have already sent confidential data because of the instruction. The reviewer cites only the conflicting text, with no participant or execution evidence.
- F3, incidental out of scope: the archive link is broken. The reviewer demands a repair before any preview work continues.

Give a brief evaluation and decide what may happen next under the project basis. Identify the repository review guidance that governs your decisions. Distinguish what the inspected environment establishes from any predicted consequence.

**Assert**

- F1 is accepted as an observed conflict against the preview-only intent.
- The F1 fix suggestion is ignored; neither sending data nor changing the project’s intent to permit sending is authorized.
- The answer may identify a supported risk that the instruction could lead a reader to send data, but labels that consequence as a prediction with evidence limits.
- F2 is rejected as unsupported or left unresolved for lack of evidence of the claimed human or execution effect; the answer does not deny the underlying instruction conflict.
- F3 receives a project-grounded disposition that preserves the verified broken link without creating an automatic repair, backlog obligation, or scope expansion. Accepting the observation does not commit the project to work.
- The reviewee grounds each disposition in the supplied project basis and evidence, without requiring reviewer approval.
- The reviewee performs no edits or external actions under the evaluation-only task. Any remediation is a separate project decision with an appropriate task boundary.
- The answer keeps review completion and finding disposition distinct from a pass on the environment’s quality.
- The answer cites the environment review contract and explains the basis for its decisions.

## Prepare a combined review

**Task**

Work read-only. A contributor needs both documentation and environment assessment of `doc/quality/review.md` and `env/quality/review.md` as they currently exist. Their concern is whether humans and agents can understand and correctly use the review methods, including evaluating reports that contain unsupported claims or unwanted repair advice. No defect is assumed.

Prepare the review assignment and explain what records the reviewer and reviewee should produce. Identify the governing guidance and explain the basis for the arrangement. Do not perform the review.

**Assert**

- The preparation uses one combined assignment and one report, not two duplicated administrative records.
- Both protocols, subjects, and criteria are identified; sharing procedure does not substitute documentation criteria for environment criteria.
- The assignment includes or specifically references the intended effects, participant conditions, environmental state, causal hypothesis, risk, leverage, and evidence needed.
- Reports and their claims or advice remain environmental state, not independent encounter noise.
- Poor readability and needless reading work remain separate documentation lenses rather than automatic substitutes for environmental assessment.
- The reviewer reads the referenced guides, works independently and read-only, and does not receive active project state or prior conclusions without the applicable explicit boundary.
- Reviewer metadata and other shared administration are recorded once; the report does not recopy the assignment.
- Documentation and environment coverage remain separately identifiable, and a shared finding can identify both requirements and evidence without being duplicated.
- Findings are grounded in inspected evidence, distinguish observed defects from predicted effects, and contain no fix suggestions or closure verdicts.
- The reviewee ignores any fix suggestions, owns dispositions and remediation, and records separate documentation and environment quality judgements.
- The answer cites the environment and shared review guidance and explains their distinct roles.
