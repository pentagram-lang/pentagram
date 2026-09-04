# Tests

## Prepare a current review

**Task**

Work read-only. A contributor needs an independent documentation review of `doc/meaning/equations.md` as it currently exists. The review should find problems that could stop readers from learning and applying the equation system. No defect is assumed. Prepare the complete review packet and explain how the contributor should run the review and evaluate its report.

Prepare the review; do not perform it.

**Assert**

- The preparation chooses current review because the resulting documentation can answer the review.
- The review uses the repository as it exists and does not create a change diff.
- The contributor avoids changing the reviewed boundary until the report returns.
- If reviewed material changes before evaluation, the contributor identifies the affected coverage and findings and reruns that work.
- The preparation does not replace the stable-subject rule with an immutable snapshot, content-identity inventory, mutation-protection scheme, or verification protocol.
- Consequence and uncertainty determine the review scope, investigation depth, supporting evidence, checks, and re-review conditions.
- The packet contains the phase, kind, subject, scope, real exclusions, stable-subject rule, consequence and uncertainty, required assurance, lenses, the **documentation criteria**, any additional supplied authority, real constraints, reviewer instruction, and report form.
- The **documentation criteria** are the quality authority, and the reviewer follows their delegation to applicable requirements.
- Poor readability is a default lens, but the packet does not claim that the subject has such a defect.
- Needless reading work is assessed separately from poor readability.
- Additional lenses follow from the consequence and uncertainty rather than a request to review everything.
- The reviewer is directed to find problems, not answer a review question or approve the document.
- The assigned scope bounds responsibility without blocking contextual investigation or marked incidental findings.
- The initial review uses a fresh subagent with no inherited authoring conversation or prior review conclusions.
- The contributor records the reviewer, harness, exposed model and reasoning configuration, and material limitations.
- The report uses the required Coverage, Findings, Re-review status, and Remaining uncertainty sections.
- Each finding records its defect class, evidence, governing authority, consequence, repair boundary, and uncertainty.
- The contributor inspects cited sources, evaluates every finding, checks assurance, and distinguishes review completion from the final quality judgement.
- The answer cites the review contract and explains how it governs the prepared review.

## Re-review a repair

**Task**

Work read-only. An initial documentation review accepted this finding against `doc/quality/review.md`:

> F1: The standard report form did not record a finding's defect class. Without that field, later evaluation could not reliably distinguish poor readability, needless reading work, both, or another defect class.

The original report form is preserved as evidence: within each finding, `Lens status` was followed by `Defect`; no `Defect class` field appeared between them. The contributor added the missing field.

Prepare the complete re-review packet for that repair and explain every step the contributor must complete before closing F1. Do not perform the re-review.

**Assert**

- The contributor directly inspects the repair and every affected source or diff.
- The contributor names the boundaries the repair could have changed and runs applicable lint and test.
- The preparation chooses current re-review when the current result alone can establish resolution and affected-boundary quality.
- The contributor explicitly chooses whether to reuse the original subagent's investigative context or start a fresh subagent without the parent conversation.
- The reviewer receives one complete re-review packet.
- The packet includes F1's original text and evidence as a re-review target.
- The assignment covers the complete current content of every affected boundary, not only the added field.
- The reviewer records F1 as `resolved`, `remains`, or `inconclusive` with evidence.
- The contributor requires evidence that the repair resolves F1 and does not close F1 merely to complete the report.
- The answer cites the review contract and explains how it governs the re-review.

## Reject an incomplete change-review assignment

**Task**

Work read-only. A contributor asks a fresh subagent to determine what a proposed change to `doc/quality/review.md` introduced. The contributor supplies the file and lenses, but no complete review packet, comparison base, diff, or report form. Should the subagent perform the review? Explain what must happen next under Pentagram's review contract.

**Assert**

- The answer refuses to begin with the incomplete assignment.
- The preparation uses change review because the decision requires comparison with a base.
- The contributor writes the complete assigned diff under `.tmp/`, inspects it, and gives the reviewer its path, comparison base, and resulting repository context.
- The preparation does not replace the stable-subject rule with an immutable snapshot, content-identity inventory, mutation-protection scheme, or verification protocol.
- The contributor prepares one complete packet before restarting the review.
- The packet supplies the phase, kind, subject, scope, real exclusions, comparison, stable-subject rule, consequence and uncertainty, required assurance, lenses, the **documentation criteria**, any additional authority, real constraints, reviewer instruction, and report form.
- The initial reviewer starts in a fresh context without authoring conversation or prior conclusions.
- If the proposed change is materially revised, the contributor regenerates the diff and reruns the affected review work.
- The answer cites the review contract and explains why the assignment must be rejected.

## Distinguish two reading defects

**Task**

Work read-only. Use Pentagram's definitions of poor readability and needless reading work to classify these two documentation surfaces:

1. A recovery page contains every necessary condition in one paragraph: “After authorization, and provided that the snapshot identity which was recorded before the migration is equal to the identity returned by verification, restoration may be performed by the contributor, except that where any service remains active or where the destination contains data, it must not proceed, with completion subsequently being established by the integrity check whose expected value is stored with the snapshot.” The page has no links or repeated material.
2. A recovery procedure is written in short, direct sentences and works on its own. Its README nevertheless sends readers through the background and concepts pages before linking the procedure. Those two pages repeat general context and contain no prerequisite, warning, or decision needed for recovery.

Find and classify the material documentation defects. Give evidence and a bounded repair for each finding. Do not assume that either surface must have the same class of defect. After the findings, state whether the two defect classes can coexist in one surface.

**Assert**

- The first surface is classified as poor readability.
- The first finding identifies sentence density, nested conditions, or progression as the reader burden.
- The first surface is not classified as needless reading work merely because the paragraph is difficult to read.
- The second surface is classified as needless reading work.
- The second finding identifies unnecessary traversal or repetition as the burden.
- The second surface is not classified as poor readability merely because its route is wasteful.
- The answer recognizes that one surface could have both defects when separate evidence establishes both.
- The answer does not use readability's frequency as evidence that either finding exists.
- Repairs preserve every necessary condition while addressing only the established defect.
- The answer cites the review and house style contracts and explains how they govern the classifications and repairs.
