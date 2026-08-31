# Human design

Within [environment design](README.md), human design shapes the shared environment for applicable human participants. It starts from the effects and environmental-encounter inputs identified through [intent](../intent.md) and uses the [human schema model](../theory.md#human-schema-activation) to connect an intervention to cognition, behaviour, and actual results.

Human design does not optimize an artifact for an abstract average reader. It designs documentation and code for humans performing particular tasks under the applicable conditions, then checks the same environment through [agent design](agent.md).

## Ground the human encounter

For each intended effect, establish the applicable human `participant`, `situation`, and `encounter-noise` inputs. Account for the participant's relevant prior knowledge, learned schemas, abilities, and means of access. Follow the situation through its task, location, project state, surrounding work, interruptions, and consequences.

Treat unsupported beliefs about humans as assumptions, not observations. Inspect existing work and evidence when they can establish what humans encounter, attempt, misunderstand, or recover from. When consequence or uncertainty warrants direct human evidence, include the range of applicable humans rather than only the most familiar or least constrained participant.

Do not mistake an existing process for the desired effect. A familiar process can carry needless work or prevent some humans from succeeding. Preserve it only when the intent or evidence requires its effects.

## Trace cognition and action

Start from the `observed-environment` available in the situation. Trace the proposed path through:

1. the cues and relationships the human encounters;
2. the schemas and expectations those cues can activate;
3. the frame needed to conceptually execute the system;
4. the action the environment makes apparent or possible;
5. the consequences produced through actual execution; and
6. the feedback and persistent state available for correction or continuation.

Identify where the path depends on memory, divided attention, unfamiliar terminology, hidden state, an unstated relationship, or knowledge that the applicable participant may not have. Identify where `encounter-noise` can remove or distort a necessary cue. A plausible path must include recovery from consequential gaps rather than assume a complete first encounter.

Trace the whole task across documentation and code. A clear instruction paired with an opaque command, an apparent affordance rejected without useful feedback, or a safe system hidden behind a misleading interface remains a failed environment.

## Choose an intervention

Choose the smallest combination of environmental causes with a plausible path to the intended effects. Depending on the intent, human design can:

- make purpose, authority, relationships, available actions, current state, and consequences perceptible;
- use stable terminology, familiar relationships, examples, and progressive depth to support an adequate frame without unnecessary reading;
- arrange cues so the normal path of thought and action appears before exceptional detail;
- make affordances and defaults support the desirable action while constraints prevent or contain important undesirable effects;
- give timely, specific feedback that explains what happened and provides a route to correction;
- preserve orientation and useful state across interruption, failure, and return;
- make consequential actions controllable and reversible where the governed system permits it; and
- support applicable access and adaptation needs without changing the canonical meaning.

Use a technique because its causal role fits the intended effect, not because it is a generic design preference. Several compatible causes can reinforce one relationship and correct partial encounter noise. Repeated governing prose instead creates competing authority and weakens that correction.

## Preserve one environment

Apply [agent design](agent.md) to the complete proposed result. Preserve shared semantics even when humans and agents need different expressions or paths to them.

Choose causes that make the complete result co-beneficial. Explicit relationships, concise canonical guidance, deterministic interfaces, visible state, precise diagnostics, and recoverable operations can help both participant classes through different cognitive mechanisms. Keep participant-specific material at the smallest scope where it changes the effect. It must not burden other encounters, hide authority, or create a second version of the system.

When the methods conflict, return to the identified effects and causal mechanisms. Do not silently trade an important undesirable effect on agents for a human benefit, or the reverse.

## Leave an evaluable hypothesis

State the intervention point, the predicted causal path, the desirable and important undesirable effects, and the applicable environmental-encounter inputs. Record material assumptions, trade-offs, and unknowns.

[Environment quality](../quality/README.md) chooses proportionate evidence and judges the resulting effects. Human design identifies what should happen and why; it does not declare that the intervention worked.
