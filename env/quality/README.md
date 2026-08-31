# Quality

Within [environment engineering](../README.md), quality judges whether the combined environment produces the effects the author identified through [intent](../intent.md). It evaluates documentation and code together across the applicable `participant`, `situation`, and `encounter-noise` inputs. Locally correct artifacts do not compensate for an environment that produces an important undesirable effect.

Every repository change has environment-quality authorship. The author identifies the affected `total-environment` from the effects and their material environmental causes, not only the changed artifacts. They account for the relevant state, cross-boundary dependencies, and effects created by the change itself and by its interaction with the existing environment. The [documentation quality system](../../doc/quality/README.md) continues to govern documentation quality, and the [coding standards](../../code/README.md) continue to govern implementation and ordinary tests. Environment quality owns the combined environmental effects that neither artifact boundary establishes alone.

Quality evaluates an implemented result. It does not supply a predetermined intent, choose the intervention, or treat a plausible causal hypothesis as proof.

## Judge the complete result

Use the identified intent and the causal hypothesis from [design](../design/README.md) to inspect the complete result. Judge every applicable dimension:

- **Effects:** the environment produces the desirable effects and avoids the important undesirable effects.
- **Encounter coverage:** the result addresses the identified `participant`, `situation`, and `encounter-noise` inputs rather than only an ideal encounter.
- **Causal integrity:** the implemented documentation and code provide the causes on which the hypothesis depends, without conflicting cues or hidden gaps.
- **Execution:** conceptual execution and actual execution agree where their relationship matters, and actual results provide useful feedback and state.
- **Compatibility:** human and agent designs preserve one meaning, authority structure, action model, and state model.
- **Co-benefit:** the complete result creates shared benefits through causes that reinforce both participant classes, while participant-specific gains do not create an important undesirable effect for another participant.
- **Error correction:** the environment remains effective under the applicable information loss, distortion, prior tendencies, mistakes, and bounded internal conflict.

An unsupported dimension makes the judgement inconclusive. An established failure in any applicable dimension makes the result fail even when another effect succeeds.

## Choose adequate evidence

Choose evidence from the consequence of an incorrect judgement, uncertainty about the causal hypothesis and resulting effects, environmental leverage, existing evidence, and the cost of obtaining more. Leverage increases when an environment has broader reach, stronger authority, more repetition, greater automation, or more persistent effects.

Use the smallest combination of evidence that can establish the judgement. Depending on the effect, useful evidence can include direct inspection, source and terminology searches, documentation lint, ordinary implementation tests, documentation tests, representative human use, environment tests, environment review, and observed operation.

Each source supports only what it observes. A lint can establish a source property but not a cognitive effect. An implementation test can establish an actual constraint without proving that a participant understands it. One successful agent response does not establish robust behaviour across contexts, and an agent trial does not establish a human effect.

Formal environment testing or review is not required merely because every change participates in the environment. Use either when the evidence it can add justifies its time and compute. Direct inspection and existing evidence can be sufficient for a low-consequence, well-understood effect with little leverage.

## Test environmental effects

Use an environment test when the question depends on the wider instruction hierarchy, context composition, tool surface, permissions, repository state, system responses, or interaction among documentation and code. State the effect and its `participant`, `situation`, and `encounter-noise` conditions before planning the trial.

For an agent effect, give a fresh subagent a realistic task and the applicable environment without revealing hidden assertions or the desired behaviour. Observe returned answers, citations, tool-produced artifacts, system effects, feedback, and persistent state. Preserve the exposed model, harness, effort, available tools, environmental conditions, and material limitations. Judge observable effects rather than private reasoning or the agent's assessment of itself.

Use additional trials only when variation can materially change the judgement and the added evidence justifies its cost. A trial supports only its observed conditions. Test representative models, harnesses, tasks, and encounter noise when the intent ranges over them.

Human environmental effects require evidence from applicable humans when inspection, established standards, or existing evidence cannot resolve material uncertainty. Use representative tasks and situations, include humans likely to encounter consequential barriers, and observe whether the intended effects occur. Do not substitute agent behaviour for human evidence.

## Review the environment

Use environment review when independent judgement can expose defects in the causal hypothesis, encounter coverage, instruction hierarchy, cross-surface reinforcement, executable constraints, feedback, recovery, compatibility, or resource trade-offs. The review subject is the combined environment needed to judge those relationships, not documentation alone.

Give an independent reviewer a stable subject, the identified effects and environmental-encounter inputs, the consequence-and-uncertainty basis, the required lenses, real exclusions, and a report form. Do not reveal a desired conclusion or preselect likely defects. The reviewer works read-only, identifies evidence for each finding, and records unassessed coverage and uncertainty. The author evaluates every finding against governing authority and evidence, repairs accepted failures at their source, and re-reviews affected boundaries when needed.

[Documentation review](../../doc/quality/review.md) remains responsible for documented meaning, structure, style, and evidence. Environment review crosses the broader documentation-and-code boundary. One assignment can cover both only when it states both subjects and supplies the requirements and evidence needed for each judgement.

## Reconcile the judgement

Record the result as pass, fail, or inconclusive with the effects, environmental-encounter conditions, and evidence it covers. Preserve material uncertainty and the evidence that could resolve it. Do not generalize a result beyond its participants, situations, encounter noise, models, harnesses, or system states.

Repair a failed cause, intervention, or expression through design. If evidence shows that the author's intent is incomplete, conflicting, or unsuitable, return to intent before redesigning or re-evaluating. Reconcile documentation, code, tests, and durable state so the environment and its quality record describe the same system.
