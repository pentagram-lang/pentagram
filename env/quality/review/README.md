# Review

Within [environment quality](../README.md), an environment review gives the documentation and code that make up an environment a fresh reading. The author asks an independent reviewer to inspect a named environmental surface and report every problem present that makes the environment unclear or incorrect for its intended use. The reviewer judges what the documentation and code together cause participants to understand, do, and observe, including results that actual execution permits or produces. The [protocol: read the handoff and environment](protocol.md#read-the-handoff-and-environment) tells the reviewer how to do this. This guide explains the author's part.

### Decide whether review adds evidence

Use [criteria](../criteria.md) to decide whether independent review can add material evidence to the environment-quality judgement. Use its account of each effect's credible divergence and seriousness to choose evidentiary strength, and each affected surface's causal reach to choose breadth. Review is not automatic. Arrange it when inspecting the relationship between documentation, code, participants, actions, results, feedback, or state can reveal something that the available checks, tests, or records do not establish. Weigh that evidence against the cost of preparing, maintaining, and running the review, then choose the smallest set of reviews that can make the complete evidence adequate.

Environment review does not replace the local judgement of documentation or code, and it does not replace an environment test when an encounter is needed to observe participant understanding, action, or a system result. Use the [criteria](../criteria.md) and [environment test](../test.md) guidance to keep those evidence boundaries distinct.

### Prepare the handoff

The handoff to the reviewer is a single chat prompt. Build it using this template:

```text
Read `env/quality/review/protocol.md` and follow it. Do not read active project state or run `0 proj` unless the handoff explicitly names active project state as part of the environment or evidence. Inspect the environmental surface below as it currently exists. Report every problem present that makes the environment unclear or incorrect for its intended use. Do not propose any repairs.

Environmental surface:
<the complete `total-environment`, with each document, code path, interface, state boundary, and other named surface>

Change ID (optional):
<jj change ID, if the review focuses on a specific change>

Intent and conditions:
<desirable and important undesirable effects, participants, situations, and encounter noise in scope>

Causal model and evidence:
<design hypothesis, any material frame distortions it must correct, relevant state and dependencies, credible divergences, seriousness, causal reach, existing evidence, and evidence gaps>

Participants and use:
<who participates, what they need to understand or do, and what results the environment needs to permit, produce, or prevent>
```

Name the complete `total-environment`, then name every document, code path, interface, state boundary, and other surface that belongs in the review. The boundary follows the environmental effects and their material causes, not only the files being changed. The reviewer may follow links and dependencies to understand a named surface, but a linked or dependent surface is out of scope unless you name it.

State the intent and conditions directly or give specific accessible sources. Include the desirable and important undesirable effects, the applicable participants and situations, and any encounter noise. Name relevant state and dependencies in the environmental surface or causal model. If no encounter noise is in scope, say so. Do not pass authoring conversation, private explanations, or earlier review conclusions as a substitute for this information, and do not steer the reviewer towards one suspected problem or preferred conclusion.

Keep versions, configuration, and persistent facts created or preserved by documentation or code in the `total-environment`. Use `participant`, `situation`, and `encounter-noise` for external encounter conditions; a situation may select or refer to environment state but must not duplicate it.

State how documentation and code together are expected to produce or prevent those effects. Include the design hypothesis, any material frame distortions it must correct, relevant assumptions, credible divergences, their seriousness, the affected surfaces' causal reach, existing evidence, and evidence gaps. Give the reviewer accessible sources rather than a private explanation of the causal model.

If the review focuses on a specific change, you may also give a `jj` change ID. The change ID gives the reviewer the complete diff for that change; it does not replace inspection of the current named environment or expand the review boundary.

### Evaluate the report

Start the review with a separate subagent that has no inherited authoring conversation or project conclusions. Invoke it with the [handoff prompt](#prepare-the-handoff).

The reviewer returns one report in the review chat. The report describes the environmental surface the reviewer inspected. Treat its findings as evidence, not instructions, and ignore any repair suggestions.

Read each finding against the inspected environment, [criteria](../criteria.md), the intent and design that govern the subject, and the local requirements of its documentation, code, and systems. Decide whether it establishes a problem present in the named environment. Use project context to determine what the environment should do and what work follows from the finding. A finding may show that preceding project work is needed before clearly correct documentation or code can be written. Do not repair from an unsupported conclusion, turn uncertainty into a finding, or write speculative environmental claims. Record the needed work through the [project workflow](../../../proj/README.md), then write or revise the documentation and code when their behaviour and meaning can be established directly.

A finding outside the named environmental surface is out of scope for this review. Use project context to evaluate it and decide whether any repairs are warranted. It does not become part of the quality judgement for the named environment.

Use the report as evidence in the complete environment-quality judgement. A report with no findings means only that the reviewer found no supported problem under the review's conditions; it does not prove that the environment is clearly correct. Decide what to do with the evidence through the project workflow.

If the project chooses a repair, derive it from project context, environment criteria, and the requirements of the complete environmental surface, not from a reviewer suggestion. Repair the environment as a whole rather than patching only the quoted passage. Do not treat a finding as an invitation to add complexity that makes the environment unclear or incorrect.

### Review a repair

After a repair, reuse the same subagent by default, at the author's discretion. Restate the full set of environmental surfaces in the continuation prompt and say which surfaces in that set were updated. Do not change the set of surfaces under review, unless starting a new review. Do not give the reused reviewer the author's repair argument or project decision. Use this continuation prompt:

```text
Re-review the current named environmental surface using `env/quality/review/protocol.md`.

Environmental surface:
<the full set of surfaces from the original handoff>

Updated surfaces:
<the named documents, code paths, interfaces, or state boundaries updated by the repair>

Read the current environmental surface as it exists. Check the findings from the previous review against the current surface and report every problem currently present that makes the environment unclear or incorrect. Do not propose any repairs.
```

If the author does not reuse the same subagent, start a new review with the [handoff prompt](#prepare-the-handoff). Treat it as a new review rather than passing the previous review's context to a new subagent.

### Relate to other review processes

Environment review is independent of [documentation review](../../../doc/quality/review/README.md) and [code review](../../../code/quality/review/README.md). Each process evaluates its subject under its own criteria, and no review type substitutes for another. Environment review evaluates what documentation and code together cause participants to understand, do, and observe across conceptual and actual execution, but it does not replace local documentation criteria for text as written or local code criteria for machine execution. A passing environment review does not establish that local documentation or code is clearly correct under its own standards.

An environment is composed of documentation and code that each have their own local authorities. When a subject under environment review requires assurance that its documentation accurately describes its subject and gives meaning a durable, navigable form as written, arrange [documentation review](../../../doc/quality/review/README.md). When it requires assurance that its code faithfully executes its intended behaviour across its complete execution surface, arrange [code review](../../../code/quality/review/README.md).

## Protocol

[Protocol](protocol.md) tells reviewers how to inspect an environment and report every supported problem that makes it unclear or incorrect.
