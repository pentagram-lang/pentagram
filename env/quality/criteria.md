# Criteria

Within [quality](README.md), criteria governs one judgement over the affected `total-environment`. The author's [identified intent](../intent.md) supplies the environmental effects to judge. Theory supplies the causal model. The [design method](../design/README.md) supplies the intervention and its hypothesis. The [documentation quality system](../../doc/quality/README.md), [coding standards](../../code/README.md), and local subject documentation supply their artifact and system requirements. Evidence determines whether the complete result satisfies them.

Quality evaluates an implemented result. It does not supply a predetermined intent, choose the intervention, or treat a plausible causal hypothesis as proof.

## Establish the governing basis

Begin with the author's [identified intent](../intent.md). Name the desirable effects, the important undesirable effects, and their applicable `participant`, `situation`, and `encounter-noise` inputs.

Use the [environmental encounter model](../theory.md#environmental-encounter) to identify the affected `total-environment`. The boundary follows the effects and every material documentation or code cause, not only the changed artifacts. Record the relevant system state, cross-boundary dependencies, and material conditions that remain external.

Inspect the causal hypothesis from the [design method](../design/README.md). It must identify the intervention points, the environmental causes introduced or changed, and the path by which those causes should produce or avoid each effect. Treat its assumptions, trade-offs, and unknowns as conditions on the judgement rather than established facts.

Apply the requirements owned by the affected documentation, code, interfaces, and systems. Environment quality judges their combined effects; it does not weaken or replace their local authority.

## Judge the complete result

Judge every applicable dimension across the complete affected environment:

- **Effects:** the environment produces the desirable effects and avoids the important undesirable effects.
- **Encounter coverage:** the result addresses the identified `participant`, `situation`, and `encounter-noise` inputs rather than only an ideal encounter.
- **Causal integrity:** the implemented documentation and code provide the causes on which the hypothesis depends, without conflicting cues or hidden gaps.
- **Execution:** conceptual execution and actual execution agree where their relationship matters, and actual results provide useful feedback and state.
- **Compatibility:** human and agent designs preserve one meaning, authority structure, action model, and state model.
- **Benefit:** the complete result benefits both human and agent participants through causes that reinforce the shared environment, while participant-specific gains do not create an important undesirable effect for another participant.
- **Error correction:** the environment remains effective under the applicable information loss, distortion, prior tendencies, mistakes, and bounded internal conflict.
- **Resources:** participant effort, context, time, compute, storage, and maintenance cost remain justified by the effects they support.

One success cannot compensate for another applicable failure. A clear explanation does not compensate for an unsafe action surface. An executable constraint does not compensate for an environment that consistently leads participants towards the blocked action. A human benefit does not compensate for an important undesirable agent effect, or the reverse.

## Require adequate evidence

Choose evidence from:

- the consequence of an incorrect judgement;
- uncertainty about the causal hypothesis and resulting effects;
- environmental leverage;
- the evidence already available; and
- the cost of obtaining and maintaining more evidence.

Leverage increases with reach, authority, repetition, automation, persistence, and the strength of the consequences the environment can produce. These considerations guide a reasoned decision; they do not create a universal score or quota.

Use the smallest combination of evidence that can establish the judgement. Relevant evidence can include direct inspection, source and terminology searches, documentation lint, implementation tests, documentation tests, representative human use, [environment tests](test.md), [environment review](review.md), and observed operation. Gather it in any useful order.

Each source supports only what it observes. A lint result can establish an exact source property but not a cognitive effect. An implementation test can establish an actual constraint without proving that participants find or understand it. A review can establish a causal or coverage defect without measuring its frequency. One successful agent trial does not establish robust behaviour across contexts, and an agent trial does not establish a human effect.

Formal environment testing or review is not required merely because every change participates in the environment. Direct inspection and existing evidence can be sufficient when consequence, uncertainty, and leverage are limited. Use a formal method when the evidence it can add materially changes confidence in the judgement.

## Reach and reconcile the judgement

The environment passes when adequate evidence establishes the intended effects and every applicable dimension and requirement. It fails when evidence establishes that an important undesirable effect occurs, a required desirable effect does not occur, or another applicable requirement is violated. The result is inconclusive when material evidence is missing, contradictory, or too weak to decide.

Record the judgement with the subject boundary, system state, effects, encounter conditions, and evidence it covers. Preserve material uncertainty and the evidence that could resolve it. Do not generalize beyond the participants, situations, encounter noise, models, harnesses, system states, or other conditions represented by the evidence.

Repair a failed cause, intervention, expression, or implementation through design. If evidence shows that the author's intent is incomplete, conflicting, or unsuitable, return to intent before redesigning or re-evaluating. Reconcile documentation, code, tests, and durable state so the environment and its quality record describe the same system.
