# Review

[Quality](README.md) uses review to find documentation defects that require judgement. An independent reviewer investigates and reports problems. The contributor evaluating the report is the **reviewee**; they retain authority over finding dispositions and any ensuing work.

Review can expose false meaning, broken models, missing boundaries, and prose that is accurate but difficult to read. A report supplies evidence, not fixes, approval, or authority over the documented system. The process is:

1. Assign a bounded review.
2. The reviewer reports supported findings without suggesting fixes.
3. The reviewee evaluates the findings on the project basis and ignores any fix suggestions.
4. The project decides whether and how to pursue work.

This separation must be easy for humans and agents to understand and follow. Accepting a finding does not authorize a repair.

## Choose current or change review

Use current review to find problems in the system as it exists. The origin of a problem is irrelevant.

Use change review when the decision requires comparison with a specific base. The reviewer examines the complete assigned diff in the context of the resulting system.

Choose one kind. If the result alone can answer the review, use current review. If the reviewer must compare the base and result, use change review.

## Scale and bound the review

First record the material consequences of a missed defect and the uncertainty surrounding the subject. Use them to choose the subject boundary, investigation depth, supporting evidence, checks, and re-review conditions. This basis scales the work; it does not produce a numerical score.

Name the exact document, surface, change, or claim the reviewer is responsible for. State real exclusions, but do not suggest likely defects or a desired conclusion. Discovering the applicable authority, evidence, and problems is part of the review.

## Keep the subject stable

Review the repository as it exists. The reviewer works read-only, and the reviewee avoids changing the reviewed boundary until the report returns.

A current reviewer reads the complete subject and follows relevant repository context normally. If reviewed material changes before the reviewee evaluates the report, identify which coverage and findings the change affects and rerun that review work against the current repository. Prepare a new packet when the assignment itself changes.

For a change review, write the complete assigned diff under `.tmp/` with `jj diff --git` and explicit base and result revisions. Inspect the diff before giving its path and the resulting repository context to the reviewer. Regenerate the diff and rerun affected review work after a material revision.

## Prepare one review packet

The packet below is the complete assignment. Fill every placeholder and include the report form. Review scope defines the reviewer's responsibility; the project basis governs any ensuing work.

The [documentation criteria](criteria.md) delegate to applicable meaning, structure, style, and local requirements. The reviewer follows that delegation and independently establishes the subject's intent, other governing authority, and evidence from durable repository sources. Do not preselect those requirements or use a supplied authority list to restrict investigation.

Prepare the complete packet before starting the review. If the assignment changes, update the packet and rerun the affected review work. Do not substitute inherited conversation context for the packet.

## Apply the default lenses

Poor readability is Pentagram's most common documentation defect, so every review must actively look for it. That frequency justifies the default lens; it does not establish a defect in the subject.

Poor readability makes wording, density, progression, or relationships difficult to understand. Look for buried points, overloaded sentences, paragraphs with several movements, unclear referents, and details introduced before the model that makes them intelligible. A finding must identify the actual burden rather than call prose unclear by preference.

Needless reading work is a separate ergonomic defect. It adds repetition, detours, misplaced detail, or unnecessary traversal even when each passage is clear. Every review assesses it separately from poor readability. A subject can have either defect, both defects, or neither.

## Choose additional lenses

Use consequence and uncertainty to choose any other areas in which the reviewer should actively seek defects. Useful lenses include:

- correctness, claim status, scope, and authority;
- models, equations, and semantic completeness;
- ownership, navigation, and links;
- reader decisions, actions, failures, and recovery;
- agreement with implementation, tests, diagnostics, and tools;
- resource behaviour and the Pentagram aims; and
- maintenance, compatibility, drift, and unresolved uncertainty.

Combine lenses when one investigation serves them together. Separate lenses that require different evidence or expertise. Do not ask a reviewer to review everything.

The assigned scope bounds review responsibility, not contextual investigation. If investigation happens to reveal a material problem outside the scope or lenses, report it as incidental without expanding the search. Mark scope status and lens status separately. An incidental finding does not expand review coverage.

Subject coverage and quality coverage are also separate. Subject coverage records which assigned content the reviewer examined. Quality coverage records which applicable requirements and lenses the reviewer assessed. Complete subject coverage does not imply complete quality coverage. Record every applicable area left unassessed.

## Prompt the reviewer

Include this instruction in the packet and replace every placeholder. A re-review also includes the original text and evidence for every target finding.

```text
Find documentation problems in the assigned scope.

Review phase: <initial or re-review>
Review kind: <current or change>
Subject: <document, surface, change, or claim>
Scope: <exact responsibility and exclusions>
Comparison: <base and diff path for change review, or not applicable>
Subject stability: <repository as it exists, read-only reviewer, reviewee
avoids changes to the reviewed boundary until the report, and response to
reviewed material changing before evaluation>
Consequence and uncertainty: <material effects of a missed defect and unknowns>
Required assurance: <scope, investigation, evidence, checks, and re-review>
Default lenses: poor readability and needless reading work, assessed separately
Additional lenses: <other assigned areas, or none>
Quality authority: doc/quality/criteria.md
Additional authority: <other governing sources supplied as inputs, or none>
Re-review targets: <finding identifiers, original findings, and evidence, or not
applicable>
Constraints: <real safety, authority, or access constraints, or none>

Work read-only. Do not read active project state or run `0 proj`.

Inspect the complete subject in repository context. Start from the nearest
README. Apply doc/quality/criteria.md and follow its delegation to applicable
meaning, structure, style, and local requirements. Follow relevant authority,
definitions, implementation, tests, diagnostics, tools, callers, and consumers
as far as needed.

Find every material problem you can establish within the assigned scope and
lenses. Do not actively seek problems outside them. Mark incidental findings
without expanding the search. Do not answer an assigned question, infer a desired
conclusion, or treat preference as a defect.

Report only findings grounded in evidence you inspected. Do not suggest fixes,
rewrites, or repair plans. State the observed defect separately from inferred
consequences; give the basis and limits of each inference. Missing evidence is
a limit to report, not permission to invent a defect or assign remedial work.

Return the supplied report form. Give evidence for every finding. Record subject
coverage, quality coverage, and material gaps in evidence or certainty.
```

## Run the initial review independently

Start the initial review in a fresh subagent context with the complete packet. Do not pass the authoring conversation or prior review conclusions. Harness mechanisms can differ; the required properties are a complete assignment and independent judgement.

Record the reviewer, harness, exposed model and reasoning configuration, and material limitations. Re-review follows [review: repair and re-review](#repair-and-re-review) and can retain the original reviewer's investigative context.

## Require a structured report

The reviewer uses this form:

```md
# Review report

## Coverage

- Review phase and kind:
- Subject and scope:
- Comparison base and diff:
- Default and additional lenses:
- Consequence and uncertainty:
- Required assurance:
- Assurance provided:
- Quality authority:
- Additional authority supplied:
- Authority established during review:
- Files and surfaces inspected:
- Subject coverage:
- Quality coverage:
- Checks run:
- Context, evidence, and checks not assessed:

## Findings

### F1: Concise defect name

- Location:
- Scope status: in scope | incidental out of scope
- Lens status: within lens | incidental outside lens
- Defect class: poor readability | needless reading work | both | other class
- Defect:
- Requirement or authority:
- Evidence:
- Consequence:
- Uncertainty:

## Re-review status

- Target finding: resolved | remains | inconclusive — evidence

## Remaining uncertainty

- Uncertainty and evidence needed to resolve it
```

Quote only enough text to locate a problem. Use one numbered subsection per finding. Mark every boundary an incidental finding crossed; do not count that area as reviewed coverage.

Supplied authority names governing sources the reviewee provided as inputs. Authority established during review names the governing sources the reviewer discovered and applied. Files and surfaces inspected records contextual investigation; it does not replace either authority field.

When no defect is established, write `No findings established.` under Findings. That result is not approval. An initial review uses `Not applicable.` for Re-review status. A re-review records each target as `resolved`, `remains`, or `inconclusive`. Use `Not applicable.` for Remaining uncertainty when none remains.

Keep the packet and report under `.tmp/` until evaluation and re-review are complete.

## Evaluate the report

The reviewee reads the report and inspects the cited sources. If the reviewed boundary changed before evaluation, identify the affected coverage and findings and rerun that work against the current repository. Check that the investigation supplied the required assurance. A review with insufficient assurance is incomplete even when every finding can be evaluated.

Evaluate findings using the [project basis](../../proj/README.md#project-authority): the charter, active task, applicable goal, decisions, governing requirements, and evidence. The reviewee may reject any finding, including an in-scope or incidental out-of-scope finding, without reviewer approval. Record each as accepted, rejected, or unresolved, with the basis for that decision. An out-of-scope observation does not automatically become work or a backlog item.

Ignore every fix suggestion in the report, even when it accompanies a supported finding. Evaluate the finding separately and choose any remediation independently from the project basis. Reviewer confidence, a proposed solution, and a re-review verdict supply no project authority.

Acceptance acknowledges a finding; it does not authorize a fix, expand the active task, or require immediate work. The project decides whether work is warranted and establishes the appropriate task boundary before pursuing it. Rejection does not erase observed facts or establish a quality pass. Keep finding disposition, review completion, and the quality judgement distinct.

Preserve this reviewee-owned evaluation with the report:

```md
# Review evaluation

- Report:
- Assurance: sufficient | insufficient — evidence
- Review status: complete | incomplete — reason
- Quality judgement: pass | fail | inconclusive — evidence
- Finding dispositions and project basis:
- Remaining uncertainty and project-chosen work:
```

A review is complete only when the required assurance was provided, every finding has a disposition, and remaining uncertainty is recorded. Apply the [documentation criteria](criteria.md) to all available evidence for the quality judgement. A report with no findings does not by itself establish a pass.

## Repair and re-review

When the project chooses and authorizes repair work:

1. Determine the repair independently from the project basis. Address the actual source of the defect, whether documentation, implementation, tests, tools, or the governed design.
2. Directly inspect the repair and every affected source or diff. Name the boundaries the repair could have changed. Run applicable [lint](lint.md) and [test](test.md).
3. Choose current re-review when the revised system alone can establish whether the findings are resolved and the affected boundaries remain sound. Choose change re-review when that decision requires comparison with the original state, and generate a fresh complete diff.
4. Choose the reviewer. Continue with the original subagent when established investigative context helps test the repair. Start a fresh subagent when the boundary changed or another independent judgement matters. Do not pass the parent conversation or unrelated review conclusions.
5. Give the reviewer a complete re-review packet containing the original text and evidence for every target finding. Re-review the complete current content of every affected boundary.
6. Evaluate the re-review report using the same [report evaluation](#evaluate-the-report). A `remains` or `inconclusive` verdict does not block evidence-based closure; a `resolved` verdict does not establish it. Track each finding to a repair, explicit decision, preserved uncertainty, or authorized exclusion. Do not close findings merely to make the report complete.

## Respect the wider environment

Every document participates in the repository environment. Use [environment review](../../env/quality/review.md) when the behaviour under review comes from the wider instruction hierarchy, repository composition, tool affordances, or interaction among systems. [Environment engineering](../../env/README.md) governs that wider boundary. Documentation review remains responsible for the document's meaning, path, expression, and evidence.
