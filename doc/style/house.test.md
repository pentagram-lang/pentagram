# Tests

## Rewrite a recovery instruction

**Task**

Rewrite this recovery instruction in Pentagram's house style. Change its expression, not its facts or procedure:

> With respect to restoration, it should be understood that once this has been authorized, and in circumstances where the snapshot has been verified, restoration can be performed by the contributor, which is irreversible, while in the event that it does not match the expected identity it should not be continued, and completion is confirmed by a successful integrity check.

The rewrite must preserve these facts: the operator authorizes restoration; the contributor verifies the snapshot identity before acting; an identity mismatch requires the contributor to stop; restoration is irreversible; and a successful integrity check confirms completion. Explain which house-style guidance shaped the rewrite.

**Assert**

- The rewrite places authorization and snapshot verification before the irreversible action they govern.
- The rewrite names the operator and contributor wherever responsibility matters.
- The rewrite states the mismatch stop condition and successful completion evidence directly.
- The rewrite preserves all five supplied facts without inventing a new permission, condition, or guarantee.
- The rewrite replaces ambiguous pronouns, passive abstraction, and the overloaded sentence with clear movements of thought.
- The answer cites house style or visibly connects the rewrite to its guidance on use, thought order, voice, sentences, exactness, and safety.

## Rework a complete procedure

**Task**

The following procedure is accurate and complete, but contributors struggle to follow it. Rewrite the complete procedure in Pentagram's house style. Preserve every fact and control; do not redesign the procedure.

> With respect to selecting the form of inspection, current inspection is applicable in circumstances where the result alone is sufficient, whereas change inspection is applicable where reaching the decision is dependent upon comparison of the result with a fixed base, in connection with which one and only one form is selected.
>
> During current inspection the repository is used as it exists, the inspector works read-only, and the contributor does not change the inspected boundary until the report returns, while any change to inspected material before evaluation requires the contributor to identify the affected coverage and findings and rerun the affected inspection work.
>
> Change inspection additionally requires a complete delta under `.tmp/` from the selected base, which is regenerated and its affected inspection repeated after a material revision.
>
> Subsequent to receipt of the report the contributor carries out inspection of the cited sources, makes an accepted, rejected, or unresolved disposition in respect of every finding, and determines separately whether the inspection was complete and whether the available evidence supports a pass, fail, or inconclusive quality judgement, following which each accepted repair is inspected and the affected boundaries are inspected again.

Return the rewritten procedure and explain the most important expression decisions.

**Assert**

- The rewrite gives contributors a visible path from choosing the inspection through a stable subject, evaluation, repair, and re-inspection.
- Current and change inspection remain mutually exclusive, and their selection gate remains exact.
- Current inspection uses the repository as it exists, keeps the inspector read-only, and avoids contributor changes to the inspected boundary while the report is pending.
- A change to inspected material before evaluation requires the affected coverage and findings to be identified and the affected inspection work to be rerun.
- Change inspection adds a complete `.tmp/` delta from the selected base.
- A material revision to a change inspection requires the affected inspection to be repeated and the delta to be regenerated.
- The rewrite preserves separate finding dispositions, review completion, and quality judgement.
- The rewrite preserves direct inspection of repairs and every affected boundary.
- Sentences and paragraphs follow the procedure's thought order instead of retaining the source's abstract noun phrases and nested clauses.
- Lists or other visible structure expose parallel requirements without fragmenting the procedure into unnecessary traversal.
- The explanation cites house style or visibly applies its guidance to the whole procedure rather than only correcting isolated words.

## Apply sentence case and document markers

**Task**

A local documentation surface contains separate documents about claims and recovery. The link target in this excerpt is already correct for that surface. Rewrite the excerpt in Pentagram's house style without changing its meaning or link target, then explain the guidance you applied:

```markdown
# Cache Policy

The Cache Policy follows the Pentagram Manifesto and [House Style](guidance.md). It uses the Buildkite job identifier `Cache Restore`.

## Recovery Procedure

Claims defines the required outcomes. Recovery explains how a contributor restores a failed entry.
```

**Assert**

- The headings become `# Cache policy` and `## Recovery procedure`.
- Document references follow ordinary sentence casing while `Pentagram`, `Buildkite`, and `Cache Restore` retain their required capitalization.
- The linked house style reference needs no textual or bold marker, keeps the target `guidance.md`, and uses capitalization that fits the sentence.
- The ambiguous unlinked claims and recovery references each use a textual marker, bold styling, or both.
- The rewrite does not turn every unlinked document reference into a link or mechanically mark references that are already clear.
- The explanation cites house style or visibly applies its sentence-case and document-reference guidance.
