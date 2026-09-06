# Review

[Quality](README.md) uses independent review to find defects that checks and reader trials may miss. The reviewer investigates and reports evidence. The **reviewee** is the contributor who evaluates that report and decides what to do on the project basis.

The normal loop is **assign → review → evaluate → repair → re-review**. Repairs are project decisions, not automatic consequences of findings. Re-review is the default after repairs, and ordinary repairs stay in the current authorized task.

This document owns the shared review procedure and record formats. Its documentation requirements apply to documentation review; [environment review](../../env/quality/review.md) uses the same procedure with its own subject, criteria, and evidence. A report supplies neither fixes nor approval.

## Assign the review

Name the complete subject and the exact responsibility, including real exclusions. Use the consequences of missed defects and the remaining uncertainty to choose the investigation, evidence, checks, and lenses needed. Do not ask for an unbounded review or suggest likely findings or a desired conclusion.

Scope bounds what the reviewer actively investigates. It must not prevent relevant contextual reading or the reporting of material incidental observations.

Review the current system by default. Add a comparison only when the decision depends on what a change introduced, removed, or preserved. For that change review, generate the complete assigned diff under `.tmp/` with `jj diff --git` and explicit base and result revisions. Inspect it and give the reviewer its path and the resulting repository context.

A complete assignment contains the following information. Reference the governing review guide instead of copying its standing instructions and report form. The reviewer must read that guide; neither prior familiarity nor inherited conversation replaces it.

```text
Protocol: <governing review guide path or paths>
Subject and scope: <complete subject, responsibility, and real exclusions>
Review basis: <consequence and uncertainty; investigation, evidence, checks,
and lenses needed>
```

Add inputs, authority, access constraints, and an output location when the encounter needs them. Add the base and diff path only for change review. For re-review, include the original text and evidence of each target finding, keyed by its identifier. References must identify accessible, specific sources; they must not stand in for missing assignment decisions.

Keep the assignment and report under `.tmp/`. Prepare the assignment before starting; recover missing material information rather than beginning an inadequately bounded review.

### Documentation scope and lenses

Use [documentation criteria](criteria.md) as the quality authority. Follow its delegation to applicable meaning, structure, style, and local requirements. Supplied authority is an input, not a restriction on discovering other applicable requirements.

Every documentation review assesses these lenses separately:

- **Poor readability:** wording, density, progression, or relationships make the text difficult to understand. Identify the actual burden, such as nested conditions or an unexplained dependency.
- **Needless reading work:** repetition, detours, misplaced detail, or unnecessary traversal create work even when the passages themselves are clear.

Poor readability is Pentagram's most common documentation defect; that motivates the default lens, not a finding in any particular subject. A document can have either defect, both, or neither. Classify documentation findings accordingly, using another class when neither applies.

Choose additional lenses from the subject's consequence and uncertainty: for example, semantic correctness, authority, model completeness, navigation, reader actions and recovery, implementation agreement, or resource behaviour. Do not turn the examples into a mandatory checklist.

## Run the review

Start the initial review in a fresh subagent context without authoring conversation or prior conclusions. Give the reviewer the complete assignment and access to its referenced protocol and subject. Record the reviewer, harness, exposed model and reasoning configuration, and material limitations once with the report; do not guess unavailable conditions.

The reviewer works read-only. The reviewee keeps the reviewed boundary unchanged until the report returns. If material changes before evaluation, identify affected coverage and findings and rerun that work against the current subject. Update the assignment when its boundary changes; regenerate a change diff after a material revision. No snapshot or additional mutation-control protocol is required.

The reviewer must:

1. Read the assigned protocol and start subject investigation from the nearest README. Inspect the complete subject and follow relevant authority, definitions, implementation, tests, diagnostics, tools, callers, and consumers as far as needed.
2. Find supported problems within the assigned scope and lenses. Report material incidental observations without expanding the search.
3. Report only defects grounded in inspected evidence. Do not suggest fixes, rewrites, or repair plans, answer an approval question, or infer the reviewee's desired conclusion. Separate observed defects from inferred consequences and state the basis and limits of each inference. Missing evidence is a limitation, not a licence to invent a defect.

Do not read active project state or run `0 proj`. An environment assignment may explicitly include named project state under [environment review](../../env/quality/review.md); that exception does not permit other project-state access.

## Report the evidence

Reference the assignment rather than repeating it. Use this report form; add subject-specific evidence required by the assigned protocol.

```md
# Review report

- Assignment: <path>
- Reviewer: <identity, harness/configuration, and material limitations>

## Coverage

<Surfaces inspected; requirements and lenses assessed; evidence and checks; material omissions, uncertainty, and evidence needed to resolve them.>

## Findings

### F1: Concise defect name

- Location:
- Defect:
- Requirement and evidence:
- Consequence and uncertainty:
```

Subject coverage says what was inspected; quality coverage says which requirements and lenses were assessed. Record both. Inspection of the complete subject does not establish complete quality coverage. Cite discovered authority and evidence where they support the assessment; distinguish them from supplied inputs when the distinction matters.

Use stable finding identifiers and quote only enough to locate the defect. Findings are within scope and lenses unless marked otherwise. For an incidental finding, add `Scope status: incidental out of scope`, `Lens status: incidental outside lens`, or both, according to the boundaries crossed. Incidental observations do not expand reported coverage.

For re-review, record current evidence for every target under Coverage, keyed by the original finding identifier, even when no defect is now established. Report what the evidence shows and what remains unknown, not a `resolved`, `remains`, or `inconclusive` verdict. The reviewee decides resolution.

When no defect is established, write `No findings established.` under Findings. That is not approval. Omit inapplicable optional fields rather than filling the report with empty sections or `Not applicable` entries.

## Evaluate the report

Ignore every reviewer fix suggestion. Evaluate the findings separately and choose any repair independently.

The reviewee reads the report, inspects its cited sources, and checks whether the assigned investigation supplied enough evidence. Evaluate each finding using the [project basis](../../proj/README.md#project-authority): charter, active task, applicable goal, decisions, governing requirements, and evidence.

The reviewee may accept, reject, or leave any finding unresolved, including an in-scope or incidental finding, without reviewer permission. Record the basis. An incidental observation does not automatically become work or a backlog item. Rejection does not erase an observed fact or establish a quality pass.

Acceptance acknowledges a finding; it does not authorize a repair, expand scope, or require immediate work. Reviewer confidence and conclusions supply no project authority.

Preserve the evaluation with the report:

```md
# Review evaluation

- Report:
- Finding dispositions and project basis:
- Review completion: <complete or incomplete; coverage and evidence basis>
- Quality judgement: <pass, fail, or inconclusive; evidence>
- Project-chosen work and remaining uncertainty:
```

A review is complete when the assigned investigation is sufficient, every finding has a disposition, and remaining uncertainty is recorded. Review completion, finding disposition, and quality judgement are distinct. Apply the relevant criteria to all available evidence; a report with no findings cannot establish a pass by itself.

## Repair and re-review

When the project chooses a repair, make it in the current task if that task already authorizes the work. Adjust the task boundary or create another task only when scope, authority, or useful decomposition requires it—not merely because a review found a defect.

Determine the repair independently from the project basis and address the actual source: documentation, implementation, tests, tools, or the governed design. Inspect the repair and every affected boundary, and run applicable checks and trials. [Documentation lint](lint.md) and [documentation test](test.md) govern their evidence; the assigned protocol identifies any other applicable method.

Re-review is the default after repairs. Use the same procedure with the original findings as inputs, covering the complete current content of every affected boundary. Continue with the original reviewer when their investigative context is useful; use a fresh reviewer when the review scope changed or another independent judgement matters. Do not pass authoring conversation or unrelated conclusions. Omit re-review only when the reviewee records a project-grounded reason why other evidence is sufficient for the affected boundary and risk.

Evaluate the new report in the same way as the first. The reviewee decides whether the evidence establishes resolution; no reviewer verdict grants or blocks closure. Track each finding to an evidenced repair, explicit decision, preserved uncertainty, or authorized exclusion. Do not close findings merely to complete a report.
