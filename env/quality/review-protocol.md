# Review protocol

An environment review gives a named environmental surface a fresh reading. The reviewer reads its documentation and code together and reports every problem present that makes the environment unclear or incorrect for its intended use. The reviewer uses the environment criteria and the handoff's stated intent, conditions, causal model, evidence, and participant use to identify supported problems. The reviewer does not supply missing meaning, invent a requirement, propose any repairs, or decide what the project should do with the report.

## Read the handoff and environment

Read the handoff before the named environmental surface. It names the documents, code, interfaces, state, and other surfaces under review, may identify one `jj` change when the review focuses on a specific change, and states the intent, conditions, causal model, evidence, and participant use that govern the review.

Inspect every named document, code path, interface, state boundary, and other surface as it currently exists. Follow links and dependencies when they are needed to understand a named surface. A linked or dependent surface is context, not part of the review, unless the handoff names it. Do not use private authoring conversation or earlier review conclusions as environmental evidence, and do not let the handoff steer the review towards one suspected problem or preferred conclusion. Inspect active project state only when the handoff names it as part of the environment or evidence.

If the handoff does not supply these inputs clearly enough to judge the environment, report that limitation instead of silently assuming them.

Use the [theory: environmental encounter model](../theory.md#environmental-encounter) to distinguish state created or preserved by documentation or code in the `total-environment` from external conditions supplied by `participant`, `situation`, or `encounter-noise`.

When the handoff includes a `jj` change ID, inspect the complete diff for that single change with `jj --ignore-working-copy diff --git --revision CHANGE`, as [source control: working copy](../../source-control.md#working-copy) describes. The `--ignore-working-copy` option prevents this read-only inspection from snapshotting current edits. Use the diff with the current named environment; it does not replace that inspection or expand the named boundary.

## Judge the environment

Use [criteria](criteria.md) as the authority for environment quality. Use the supplied intent for the desirable and important undesirable effects and their conditions. Use the design hypothesis for the proposed causal path. Apply the requirements owned by the affected documentation, code, interfaces, and systems. Environment review supplies evidence about the combined result; it does not replace those local authorities or issue the pass, fail, or inconclusive quality judgement.

Follow the path from each participant's situation through the information, actions, constraints, feedback, and state the environment exposes. Inspect what the documentation and code together cause participants to understand and do, and what actual execution permits or produces. Report a problem when the named environment establishes a contradiction, an unsafe or misleading action or result, or another condition that prevents the intended use or violates an applicable requirement.

Keep observed conditions separate from predicted consequences. A contradiction or unsafe implementation can be a present problem without an observed participant encounter. A claim that a human, agent, or execution result was affected needs evidence for that effect; if the evidence is missing, record the limitation or prediction without presenting it as an observed failure. Do not demand details that the stated use, intent, or applicable standards do not require, and do not treat an alternative design as a defect without evidence against the current environment.

## Report the evidence

Write one report for the named environmental surface. Identify the surface, intent and conditions, optional change ID, reviewer, sources, coverage, findings, and material limitations. Give each supported problem a stable identifier and enough literal text, observed condition, location, boundary, and causal path for another reader to find it and understand its environmental consequence.

Use this form:

```md
# Environment review report

Environmental surface: <the named documents, code, interfaces, and state>

Intent and conditions: <the supplied intent and applicable conditions>

Change ID (if supplied): <jj change ID>

Reviewer: <identity, harness, and material limitations>

## Coverage

<surfaces, effects, participant conditions, causal paths, standards, sources, checks, and uncertainty actually examined>

## Findings

### F1: <concise problem name>

Affected effect and causal path:

Location and boundary:

Literal or observed condition:

Problem:

Intent, requirement, and evidence:

Participant or system consequence and uncertainty:

## Out of scope

<problems noticed outside the named surface and why they are excluded, or `None`>
```

Explain the problem from the inspected environment and its governing intent, requirement, or evidence. State how the documentation and code together establish the affected consequence. Keep an observed problem separate from uncertainty about its cause or consequence. Do not include repair suggestions or a project decision. Missing evidence belongs in Coverage or in the finding's uncertainty, not in an invented observation.

A report with no findings means that no supported problem was found in the named environment under the stated conditions and coverage. It does not establish a quality pass, and it says nothing about surfaces outside the named boundary.

## Review again

On a re-review, read the current named environmental surface from the beginning and check every earlier finding against it. Use the original identifier when the same problem is still present and report it in Findings. If it is no longer present, state in Coverage what the current environment and evidence establish. Use a new identifier for a distinct current problem. Do not infer that a problem is resolved merely because a surface changed or because no new finding was reported. If a new reviewer conducts the review, treat it as a new review rather than carrying the earlier review's context into it.
