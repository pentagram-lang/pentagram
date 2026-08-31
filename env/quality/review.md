# Review

[Quality](README.md) uses review to find environment defects that require independent judgement. A reviewer investigates how the combined documentation-and-code environment realizes its causal hypothesis, covers encounters, executes, remains compatible, benefits both humans and agents, corrects errors, and uses resources. The author evaluates each finding against governing authority and evidence.

A report supplies evidence. It does not give the reviewer authority over the intended effects or the governed systems, and it does not decide the final judgement governed by [criteria](criteria.md).

## Choose current or change review

Use current review when the implemented result can answer the review. The origin of a defect is irrelevant.

Use change review when the reviewer must compare a specific base with the resulting environment. The assigned diff alone is not the subject: the reviewer examines it in the context of the complete affected environment.

Choose one kind. If the result alone can establish the effects and relationships under review, use current review. If the decision depends on what the change introduced, removed, or preserved, use change review.

## Scale and bound the review

Start from the identified effects, the affected `total-environment`, and its relevant state. Record the material consequence of a missed defect, uncertainty about the causal hypothesis and effects, and environmental leverage. Use that basis to choose the subject boundary, investigation depth, supporting evidence, checks, lenses, and re-review conditions. It does not produce a numerical score.

Name the exact environment, effect, change, relationship, or claim the reviewer is responsible for. Include every documentation, code, interface, tool, response, and state boundary needed to judge that subject. State real exclusions, but do not suggest likely defects or a desired conclusion.

Select lenses that can resolve the material uncertainty. Useful lenses include:

- intended and important undesirable effects;
- `participant`, `situation`, and `encounter-noise` coverage;
- environmental-channel selection, ordering, transformation, and exposure;
- causal integrity and hidden assumptions;
- agreement between conceptual and actual execution;
- instruction hierarchy, authority, and cross-surface conflict;
- human and agent compatibility and asymmetric failure;
- whether the complete result benefits both participant classes;
- feedback, persistent state, interruption, recovery, and error correction;
- permissions, constraints, external effects, and safety boundaries;
- effort, context, time, compute, storage, and maintenance cost; and
- model, harness, dependency, and version drift.

Do not ask a reviewer to review everything. Subject coverage records which assigned environmental boundaries were inspected. Quality coverage records which effects, conditions, requirements, and lenses were assessed. Record both and identify every material area left unassessed.

## Keep the subject stable

Review the repository and systems as they exist. The reviewer works read-only, and the author avoids changing the reviewed boundary until the report returns.

If reviewed material or state changes before evaluation, identify which coverage and findings the change affects and rerun that work against the current environment. Prepare a new packet when the assignment itself changes.

For a change review, write the complete assigned diff under `.tmp/` with `jj diff --git` and explicit base and result revisions. Inspect it before giving its path and the resulting repository context to the reviewer. Regenerate the diff and rerun affected review work after a material revision.

## Prepare one review packet

The packet is the complete assignment. Include:

- the review phase and kind;
- the subject, scope, and real exclusions;
- the affected `total-environment`, relevant state, and dependencies;
- the desirable and important undesirable effects;
- the applicable `participant`, `situation`, and `encounter-noise` inputs;
- the causal hypothesis and material assumptions under review;
- the comparison base and diff path for a change review;
- the stable-subject rule and response to a changed boundary;
- the consequence, uncertainty, leverage, and required assurance;
- the required lenses;
- [criteria](criteria.md) as the quality authority;
- additional governing authority and evidence supplied as inputs;
- safety, authority, access, and resource constraints;
- the reviewer instruction; and
- the report form.

The criteria delegate to identified intent, theory, design, documentation, coding, and local subject requirements. The reviewer follows that delegation and independently establishes the applicable authority and evidence from durable repository sources. Supplied intent identifies the effects to judge; it must not be phrased as a desired review conclusion.

Prepare the complete packet before starting. Do not substitute inherited conversation context for the packet. A re-review packet also includes the original text and evidence for every target finding.

## Prompt the reviewer

Include this instruction in the packet and replace every placeholder:

```text
Find environment problems in the assigned scope.

Review phase: <initial or re-review>
Review kind: <current or change>
Subject: <environment, effect, change, relationship, or claim>
Environment boundary and state: <total-environment, state, and dependencies>
Intended effects: <desirable and important undesirable effects>
Encounter inputs: <participant, situation, and encounter-noise conditions>
Causal hypothesis: <intervention points, causal path, and material assumptions>
Scope: <exact responsibility and real exclusions>
Comparison: <base and diff path for change review, or not applicable>
Subject stability: <read-only reviewer, unchanged boundary, and response to change>
Consequence, uncertainty, and leverage: <basis for the review>
Required assurance: <scope, investigation, evidence, checks, and re-review>
Lenses: <assigned environment lenses>
Quality authority: env/quality/criteria.md
Additional authority and evidence: <supplied inputs, or none>
Re-review targets: <original findings and evidence, or not applicable>
Constraints: <safety, authority, access, and resource constraints, or none>

Work read-only. Do not read active project state unless the assignment includes
it as environmental state or named evidence. Do not run `0 proj` otherwise.

Inspect the complete assigned environment in repository and system context.
Apply env/quality/criteria.md and follow its delegation to the identified intent,
theory, design, documentation, coding, and local subject requirements. Follow
relevant authority, implementation, tests, diagnostics, tools, callers,
consumers, responses, and state as far as needed.

Find every material problem you can establish within the assigned scope and
lenses. Do not actively seek problems outside them. Mark incidental findings
without expanding the search. Do not answer a review question, infer a desired
conclusion, or treat preference as a defect.

Return the supplied report form. Give causal evidence for every finding. Record
subject coverage, quality coverage, and material gaps in evidence or certainty.
```

## Run the review independently

Start an initial review with an independent reviewer who has no inherited authoring conversation or prior conclusions. Give them the complete packet and access to the environment needed for investigation. Do not expose active project state unless it is part of the assigned environment or supplies named evidence.

The reviewer works read-only, inspects the complete assigned subject in context, and follows relevant authority, implementation, tests, diagnostics, tools, callers, and consumers as far as the assignment requires. They find supported problems rather than answer a review question, approve the environment, or infer the author's preferred conclusion.

Record the reviewer, harness, exposed model and reasoning configuration, applicable human expertise, and material limitations. Review can identify human-effect defects from the governing design principles, theory, and available evidence, but it does not conduct human studies or establish an unobserved human effect.

## Require a structured report

Use this report form:

```md
# Environment review report

## Coverage

- Review phase and kind:
- Subject, environment boundary, and state:
- Intended and important undesirable effects:
- Participant, situation, and encounter-noise coverage:
- Comparison base and diff:
- Lenses and required assurance:
- Assurance provided:
- Quality authority:
- Additional authority and evidence supplied:
- Authority and evidence established during review:
- Documentation, code, systems, and states inspected:
- Subject coverage:
- Quality coverage:
- Checks run:
- Context, evidence, and conditions not assessed:

## Findings

### F1: Concise defect name

- Location or boundary:
- Scope status: in scope | incidental out of scope
- Lens status: within lens | incidental outside lens
- Intended or important undesirable effect:
- Defect:
- Requirement or authority:
- Causal evidence:
- Observed or predicted environmental effect:
- Consequence:
- Repair boundary:
- Uncertainty:

## Re-review status

- Target finding: resolved | remains | inconclusive — evidence

## Remaining uncertainty

- Uncertainty and evidence needed to resolve it
```

Give one numbered subsection to each finding. Mark incidental findings without expanding review coverage. When no defect is established, write `No findings established.` under Findings. That result is not approval. An initial review uses `Not applicable.` for Re-review status.

## Evaluate, repair, and re-review

The author checks that the report supplied the required assurance, inspects every cited source, and evaluates each finding against its authority and evidence. Record each finding as accepted, rejected, or unresolved with reasons. Separate review completion from the final environment-quality judgement.

Preserve this evaluation with the report:

```md
# Environment review evaluation

- Report:
- Assurance: sufficient | insufficient — evidence
- Review status: complete | incomplete — reason
- Environment-quality judgement: pass | fail | inconclusive — evidence
- Finding dispositions:
- Remaining uncertainty and required follow-up:
```

Repair accepted findings at their source. Change intent when the intended effects are defective, design when the hypothesis or intervention is defective, documentation or code when their expression or execution is defective, and tests or tools when the evidence mechanism is defective.

Directly inspect each repair and every affected boundary. Run applicable checks and [environment tests](test.md). Choose current or change re-review by the same distinction as the initial review. Continue with the original reviewer when their investigative context helps test the repair; use a fresh reviewer when the boundary changed or another independent judgement matters.

Give the reviewer one complete re-review packet containing the original text and evidence for every target. Re-review the complete current content and state of every affected boundary. Track each finding to a supported resolution, explicit decision, preserved uncertainty, or authorized exclusion; do not close it merely to complete the report.

## Combine documentation and environment review

[Documentation review](../../doc/quality/review.md) remains responsible for documented meaning, structure, style, and documentation evidence. Environment review is responsible for the broader causal relationship among documentation, code, participants, channels, execution, feedback, and state.

One assignment can cover both only when it names both subjects, supplies both criteria as quality authorities, gives each boundary adequate lenses and evidence, and reports their coverage and judgements separately. A documentation review does not silently establish environment quality, and an environment review does not silently establish documentation quality.
