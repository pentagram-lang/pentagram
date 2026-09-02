# Intent

Within [environment engineering](README.md), an author identifies how they intend the environment to work for the subject they are working on.

Within the authority governing the work, the author is responsible for identifying and applying that judgement. This responsibility does not authorize the author to replace operator instructions, project decisions, or the subject's existing contract. The environment can state the intent when it must be recorded, but it does not own another kind of intent. Call the judgement **intent**, not `environment intent`, `environmental intent`, or `local intent`.

The [theory's environment and behaviour model](theory.md#environment-and-behaviour) explains how documentation and code can cause or preserve environmental effects. The author's intent identifies which of those effects the environment should produce or preserve and which important effects it should avoid.

## Identify the intended effects

The author must identify their intent before designing the environment or evaluating its quality. Theory defines an environmental effect as a consequential condition or change that the environment causes or preserves in participant cognition or behaviour, or in a result that actual execution permits or produces. State:

- the desirable environmental effects; and
- the important undesirable environmental effects.

State each effect as the outcome, invariant, or transition that matters. For a system effect, distinguish a result that execution may permit from one it must produce. Every intent must include at least one desirable effect for humans and one for agents because the complete environment must benefit both participant classes. One effect can serve both classes when its conditions genuinely apply to both.

Before stating those effects, bound the subject as the [environmental encounter model](theory.md#environmental-encounter) defines it. Name the affected `total-environment`, its relevant state and cross-boundary dependencies, and any material conditions that remain external. The boundary follows the effects and their environmental causes, not only the artifacts being edited.

The environmental encounter model also explains why an effect depends on what reaches a participant in a situation. For each effect, identify:

- `participant`, ranging over the applicable humans and agents;
- `situation`, containing the participant's task, location, and other conditions that change which parts of the total environment they encounter; and
- `encounter-noise`, ranging over conditions that omit, substitute, or distort environmental information before it becomes available to the participant.

Together with `total-environment` and `environment-channel`, these inputs determine the `observed-environment` from which a participant acts. They describe the conditions under which documentation and code must produce, preserve, or avoid the effect.

When an effect depends on correcting a material frame distortion, identify the distortion and the `participant`, `situation`, or `encounter-noise` condition through which it enters the encounter. State the adequate frame or protected result that the environment must restore or preserve.

## Give design a target

State the intended effects rather than an intervention. For example, “an unsafe change does not reach publication” states an intent; “add a pre-push check” selects a design.

Design uses the effects and their `participant`, `situation`, and `encounter-noise` inputs with theory to form a causal hypothesis: changing an environmental cause should produce or preserve the desirable environmental effects and avoid the important undesirable environmental effects. It then chooses documentation and code interventions that can realize that hypothesis.

## Give quality a basis

[Quality](quality/README.md) evaluates the effects across the identified `participant`, `situation`, and `encounter-noise` conditions. It chooses evidence proportionate to the risk of each effect and the leverage of the affected environmental surfaces; intent does not prescribe a test or metric.

Quality compares the resulting environmental effects with the author's intent. If evidence shows that the intent is incomplete, conflicting, or no longer suitable, the author must reconcile it with the governing authority and identify the revised intent before continuing design or evaluation.

## Record intent when needed

Intent need not become repository text. Record it with the subject when another reader, system, or future decision must rely on it.
