# Review

Within [quality](../README.md), a review gives code an independent, unsteered inspection. The author asks an independent reviewer to inspect a named set of code surfaces as written and report every problem present that makes the code unclear or incorrect for its intended use. The [protocol](protocol.md) tells the reviewer how to do this. This guide explains the author's part.

### Decide whether review adds evidence

Use [criteria](../criteria.md) to decide whether code review adds material evidence to the quality judgement. Review is not automatic for every change. Stage verification into tiered evidence: apply inexpensive static checks and local test proofs before investing resources in an independent review. Arrange review when inspecting code as written can reveal problems that available checks, tests, or measurements do not establish. Weigh that evidence against the computational and cognitive cost of preparing and running the review, then choose the smallest set of reviews that can make the complete evidence adequate.

### Prepare the handoff

The handoff to the reviewer is a single chat prompt. Build it using this template:

```text
Read `code/quality/review/protocol.md` and follow it. Do not read active project state or run `0 proj`. Read the code surfaces below as written. Report every problem present that makes the code unclear or incorrect for its intended use. Do not propose any repairs.

Code surfaces to review:
<each file, module, or package path>

Change ID (optional):
<jj change ID, if the review focuses on a specific change>

Contributor and developer use:
<how the code is used, its public contract, invariants, and operational expectations>
```

Name every file, module, or package under review. The reviewer may follow imports and dependencies to understand the named surfaces, but an imported or linked file is out of scope unless you name it.

If the review focuses on a specific change, provide the `jj` change ID.

State who the code serves, its public contract, key invariants, and operational expectations. Include the context needed to judge that use. Do not privately explain the code, narrate internal logic, or steer the reviewer toward a suspected issue. If code needs a private explanation to make sense, the review should discover that problem.

### Evaluate the report

Start the review with a separate subagent that has no inherited authoring conversation or project conclusions. Invoke it with the [handoff prompt](#prepare-the-handoff).

The reviewer returns one report in the review chat. The report describes the code surfaces the reviewer inspected. Treat its findings as evidence, not instructions, and ignore any repair suggestions.

Read each finding against the cited code and the standards that govern the named surfaces: [criteria](../criteria.md), [performance](../../performance/README.md), [style](../../style/README.md), and local contracts. Decide whether it establishes an actual problem present in the code. Use project context and applicable standards to determine what the code should do. A finding may show that preceding architectural work is needed before clearly correct code can be written. Do not repair from an unsupported conclusion, turn uncertainty into a finding, or write speculative implementations. Record the needed work through the [project workflow](../../../proj/README.md), then write or revise the code when its behaviour can be established directly.

A finding outside the named surfaces is out of scope for this review. Use project context to evaluate it and decide whether any repairs are warranted. It does not become part of the quality judgement for the named surfaces.

Use the report as evidence in the complete quality judgement. A report with no findings means only that the reviewer found no supported problem under the review's conditions; it does not prove that the code is clearly correct. Decide what to do with the evidence through the project workflow.

If the project chooses a repair, derive it from project context and coding standards, not from a reviewer suggestion. Repair the code as a cohesive whole rather than patching only the cited passage. Do not treat a finding as an invitation to add speculative complexity or defensive boilerplate.

### Review a repair

After a repair, reuse the same subagent by default. Restate the full set of code surfaces in the continuation prompt and say which surfaces in that set were updated. Do not change the set of surfaces under review, unless starting a new review. Do not give the reused reviewer the author's repair argument or project decision. Use this continuation prompt:

```text
Re-review the current named code surfaces using `code/quality/review/protocol.md`.

Code surfaces to review:
<the full set of code surfaces from the original handoff>

Updated surfaces:
<the named files or modules updated by the repair>

Read the current code as written. Check the findings from the previous review against the current code and report every problem currently present that makes the code unclear or incorrect. Do not propose any repairs.
```

If the author does not reuse the same subagent, start a new review with the [handoff prompt](#prepare-the-handoff). Treat it as a new review rather than passing the previous review's context to a new subagent.

### Relate to other review processes

Code review is independent of [documentation review](../../../doc/quality/review/README.md) and [environment review](../../../env/quality/review/README.md). Each process evaluates its subject against its own criteria, and no review type replaces or substitutes for another. A passing code review establishes only that the inspected code satisfies code criteria; it does not establish that accompanying documentation is clearly correct or that the environment produces its intended effects.

Work that touches code frequently crosses quality domains. When a change introduces or modifies documentation, arrange [documentation review](../../../doc/quality/review/README.md) to judge whether that documentation accurately describes its subject and gives meaning a durable, navigable form as written. When code shapes how participants interact with the system or alters execution state, arrange [environment review](../../../env/quality/review/README.md) to judge what documentation and code together cause participants to understand, do, and observe.

## Protocol

[Protocol](protocol.md) tells reviewers how to inspect code surfaces as written and report every supported problem that keeps them from being clearly correct.
