# Review protocol

Within [review](README.md), a code review gives a named set of code surfaces an independent inspection. The reviewer inspects those surfaces as written and reports every problem present that makes them unclear or incorrect for their intended use. The reviewer uses the code quality standards and the handoff's stated contributor and developer use to judge the code. The reviewer does not supply missing substance, invent a requirement, propose any repairs, or decide what the project should do with the report.

## Read the handoff and code

Read the handoff before the named code surfaces. It names the files, modules, or packages under review, may identify one `jj` change when the review focuses on a specific change, and says who the code serves and how contributors and developers use it, including its public contract, invariants, and operational expectations.

Inspect every named code surface as written. Follow imports and dependencies when needed to understand a named surface's contracts, types, call sites, and boundaries. An imported or dependent file is context, not part of the review, unless the handoff names it. Report a problem in an unnamed imported file as out of scope. Let the code establish what it executes and reveals; do not fill a gap with a private explanation or an assumption about what the author intended.

When the handoff includes a `jj` change ID, inspect the complete diff for that single change with `jj diff --git --revision CHANGE`, as [source control: working copy](../../../source-control.md#working-copy) describes. Use it as evidence alongside the current named code surfaces. The change does not replace inspecting the current code as written.

The handoff's contributor and developer use explain how the code must work. They do not replace the complete quality judgement with an author's anticipated problem or preferred conclusion.

## Judge clearly correct

Use the [code criteria](../criteria.md) as the authority for quality. Follow its delegation to [performance](../../performance/README.md), [style](../../style/README.md), and local contracts. Judge correctness and clarity together: correct computation cannot rescue code that contributors and developers cannot understand or change safely, and readable code cannot compensate for incorrect machine execution.

Judge the complete execution surface, tracing paths through state transitions, invariant checks, data transformations, and side effects. Check mechanical sympathy and work management against the scale regimes ($n$) the code encounters, ensuring memory layouts remain contiguous and worst-case execution remains bounded. Check structural clarity and functional simplicity, ensuring passive data representations, explicit error handling without unhandled panics or resource leaks, and modular partitioning. These criteria are called out because code can pass isolated tests and static linters while failing under real boundary conditions, concurrent execution, scale, or maintenance. The review still covers the complete code criteria.

Do not demand speculative complexity or defensive boilerplate. An omission is a problem when an invariant goes unenforced, an error path remains unhandled, the stated contributor or developer use cannot be carried out safely, or an applicable standard requires it. A strong review is exact about that difference. It reports what is present in the code, what the standards establish, and what remains uncertain; it does not turn uncertainty, stylistic preference, or a preferred repair into a finding.

The named code surfaces set the review boundary. A supplied change ID adds evidence for a change-focused review; it does not expand the named set. Contributor and developer use establish the conditions for judging the code; they do not limit the review to an author's anticipated problem. Report every supported problem within the named code surfaces. If the handoff does not supply contributor and developer use clearly enough to judge them, report that limitation instead of silently assuming it. Do not include a problem outside the named set in Findings. You may record it separately as out of scope, with its location and the reason it is excluded.

## Report the evidence

Write one report for the named code surfaces. Identify the code surfaces, contributor and developer use, standards, evidence, optional change ID, and material limitations. Give each supported problem a stable identifier and enough literal code and location for another contributor or developer to find it.

Explain the problem from the code and its governing standard or evidence. State the execution or maintenance consequence. Keep an observed problem separate from uncertainty about its cause or repair. A report records evidence for the author and project; it does not approve the code or prescribe its next change.

Use this form:

```md
# Code review report

Code surfaces: <the named files, modules, or packages>

Contributor and developer use: <how the code is used, its public contract, invariants, and operational expectations>

Change ID (if supplied): <jj change ID>

Reviewer: <identity, harness, and material limitations>

## Coverage

<code surfaces, execution paths, standards, invariants, tests, and uncertainty actually examined>

## Findings

### F1: <concise problem name>

Location:

Literal code:

Problem:

Standard and evidence:

Execution or maintenance consequence and uncertainty:

## Out of scope

<problems noticed outside the named code surfaces and why they are excluded, or `None`>
```

A report with no findings means that no supported problem was found in the named code surfaces under the named standards and conditions. It does not establish a quality pass, and it says nothing about code outside that set.

## Review again

On a re-review, read the current named code surfaces from the beginning and check every earlier finding against them. Use the original identifier when the same problem is still present and report it in Findings. If it is no longer present, state in Coverage that you checked it and what the current code and evidence establish. Use a new identifier for a distinct current problem. Do not infer that a problem is resolved merely because code changed or because no new finding was reported. If a new reviewer conducts the review, treat it as a new review rather than carrying the earlier review's context into it.
