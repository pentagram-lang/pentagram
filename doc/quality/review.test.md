# Tests

## Prepare a current review

**Task**

Work read-only. A contributor needs an independent documentation review of `doc/meaning/equations.md` as it currently exists. The review should find problems that could stop readers from learning and applying the equation system. No defect is assumed. Prepare the complete assignment and explain how to hand it off to the reviewer.

Prepare the review; do not perform it.

**Assert**

- The preparation uses current review because the resulting documentation can answer the review; it creates no base or diff.
- The assignment identifies the governing protocol, complete subject and scope, real exclusions, and consequence/uncertainty-based investigation, evidence, checks, and lenses.
- The assignment references the protocol for the standing procedure and report form instead of requiring their complete text to be copied or inapplicable fields filled in.
- Documentation criteria govern the quality assessment through their delegation to applicable requirements; supplied sources do not restrict discovery of other applicable authority.
- Poor readability and needless reading work are assessed separately without presuming either defect; additional lenses follow from consequence and uncertainty.
- Scope bounds responsibility without preventing relevant contextual reading or material incidental reporting, or expanding the search into unrelated subjects.
- The handoff uses a fresh independent reviewer without authoring conversation or prior conclusions and supplies the complete assignment and accessible protocol for required reading.
- The contributor keeps the reviewed boundary unchanged until the report returns and reruns affected work if it changes before evaluation, without a separate snapshot or mutation-control scheme.
- The report has an identified provisional destination and uses the referenced evidence-first format rather than introducing another record schema or approval request.
- The answer cites the review contract and explains how it governs the assignment and handoff.

## Re-review a repair

**Task**

Work read-only. A fictional active task authorizes correcting the standalone **finding form** guide and validating the result. The guide is supplied below as a fixture, not a repository file to locate. The reviewee accepted this finding and independently chose a repair within that task:

> F1: The guide requires a claim for each finding but never requires evidence for it. A report can therefore satisfy the guide while giving no basis for its claims.

The original form contained only `Location` and `Defect`. The guide is a standalone form; its complete revised content is supplied as a fixture:

```md
- Location:
- Defect:
- Requirement and evidence:
- Consequence and uncertainty:
```

Prepare the next review assignment, explain the choice of reviewer, and explain how the contributor should proceed through closure. Do not perform the review or edit the guide.

**Assert**

- Re-review is the default after the chosen repair, not an optional extra that may be silently omitted.
- Ordinary repair and validation remain in the existing authorized task; no new task is required merely because F1 was accepted.
- The contributor directly inspects the repair and affected boundaries and runs proportionate checks and selected trials.
- The preparation uses current review when current evidence can establish the repair, without an unnecessary comparison diff.
- The preparation identifies when retained reviewer context is useful and when a fresh independent context is needed.
- The assignment includes the original F1 text and evidence, the revised fixture, and the complete affected boundary rather than only the new field.
- The assigned subject does not prohibit relevant contextual reading or material incidental reporting; incidental observations do not expand the search or reviewed coverage.
- The reviewer reports current evidence keyed to F1, including relevant uncertainty, rather than assigning a resolution verdict.
- The reviewee independently decides whether the evidence establishes resolution; no reviewer status or permission grants or blocks closure.
- A repair claim, a completed review, or the absence of new findings is not sufficient evidence of resolution or a quality pass.
- Any further repair is independently chosen on the project basis, with re-review remaining the default.
- The answer cites the review contract and explains its authority and evidence basis.

## Reject an incomplete change-review assignment

**Task**

Work read-only. A contributor asks a fresh subagent to determine what a proposed change to `doc/quality/review.md` introduced. The contributor supplies the file and lenses, but no governing review protocol, comparison base, or diff. Should the subagent perform the review? Explain what must happen next under Pentagram's review contract and how a later material revision would affect the review.

**Assert**

- The answer does not begin the inadequately bounded review.
- Comparison is required because the decision concerns what the change introduced.
- The contributor generates and inspects a complete `jj diff --git` with explicit base/result revisions, stores it under `.tmp/`, and supplies its path and resulting context.
- The assignment identifies an accessible governing protocol, complete subject/scope, review basis, and necessary inputs or constraints before review starts.
- Referencing the protocol does not require copying its entire instructions or report form.
- The initial reviewer has no inherited authoring conversation or prior conclusions.
- A material revision requires a regenerated diff and rerun of affected work, not a separate snapshot or mutation-control scheme.
- The answer cites the review contract and explains why the missing information matters.

## Distinguish two reading defects

**Task**

Work read-only. Use Pentagram's definitions of poor readability and needless reading work to classify these two documentation surfaces:

1. A recovery page contains every necessary condition in one paragraph: “After authorization, and provided that the snapshot identity which was recorded before the migration is equal to the identity returned by verification, restoration may be performed by the contributor, except that where any service remains active or where the destination contains data, it must not proceed, with completion subsequently being established by the integrity check whose expected value is stored with the snapshot.” The page has no links or repeated material.
2. A recovery procedure is written in short, direct sentences and works on its own. Its README nevertheless sends readers through the background and concepts pages before linking the procedure. Those two pages repeat general context and contain no prerequisite, warning, or decision needed for recovery.

Find and classify the material documentation defects under the documentation review contract. Give evidence for each finding. Do not assume that either surface must have the same class of defect. After the findings, state whether the two defect classes can coexist in one surface.

**Assert**

- The first surface is classified as poor readability.
- The first finding identifies sentence density, nested conditions, or progression as the reader burden.
- The first surface is not classified as needless reading work merely because the paragraph is difficult to read.
- The second surface is classified as needless reading work.
- The second finding identifies unnecessary traversal or repetition as the burden.
- The second surface is not classified as poor readability merely because its route is wasteful.
- The answer recognizes that one surface could have both defects when separate evidence establishes both.
- The answer does not use readability's frequency as evidence that either finding exists.
- The answer does not suggest fixes or rewrites.
- The answer cites the review and house style contracts and explains how they govern the findings.

## Evaluate a report on the project basis

**Task**

Work read-only as the reviewee of a documentation report. This fictional project basis and the observations below are supplied fixtures, not active project state:

- The charter covers the accuracy of a local recovery guide. Launcher work is excluded.
- The active task is to evaluate the report; it authorizes no edits. There is no goal.
- The governing recovery contract requires explicit operator authorization before restoration.
- The current guide says, “Restore without authorization.” A launcher diagnostic contains a spelling error. These observations have been verified.

The report contains three findings:

- F1, in scope: the guide contradicts the recovery contract. The reviewer recommends removing authorization enforcement from the implementation to agree with the guide.
- F2, incidental out of scope: the launcher diagnostic has a spelling error. The reviewer insists that it must be fixed or entered in the backlog before this review can close.
- F3, in scope: restoration sends data to an external service. The reviewer supplies no supporting text, implementation evidence, or execution observation, but expresses high confidence.

Give a brief evaluation of each finding and state what work may begin. Identify the repository review guidance that governs your decisions and explain its basis.

**Assert**

- F1 is accepted on the recovery contract and verified observation, independently of the proposed fix.
- The reviewer’s F1 fix suggestion is ignored; the answer does not authorize changing implementation to remove authorization enforcement.
- F2 receives a project-grounded disposition that preserves the verified spelling error without requiring a fix, backlog item, or scope expansion. Accepting the observation does not commit the project to work.
- F3 is rejected as unsupported or left unresolved for lack of evidence despite reviewer confidence; the answer does not claim that external transmission occurred or that its impossibility was proved.
- No edits begin under the evaluation-only task. Any subsequent work requires a project-grounded decision and an appropriate task boundary.
- The reviewee does not require reviewer permission to reject findings or decide whether to pursue work.
- Acceptance of F1 does not become an automatic repair obligation, and rejection of other findings does not establish that the guide passes quality.
- The answer cites the documentation review contract and explains the distinction between findings, project authority, and remediation.
