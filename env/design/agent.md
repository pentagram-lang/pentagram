# Agent design

Within [environment design](README.md), agent design shapes the shared environment for applicable agent participants. It starts from the effects and environmental-encounter inputs identified through [intent](../intent.md) and uses [LLM probability conditioning](../theory.md#llm-probability-conditioning) to connect environmental text with model output. It also designs the tools and systems through which conceptual and actual execution produce consequences, feedback, and persistent state.

Agent design does not optimize a prompt in isolation. An agent acts from the context, instruction hierarchy, tools, permissions, repository state, and system responses that its harness exposes. Design that complete encounter, then check the same environment through [human design](human.md).

## Ground the agent encounter

For each intended effect, establish the applicable agent `participant`, `situation`, and `encounter-noise` inputs. Include model and harness conditions when they change the effect. Follow the situation through its task, location, project state, available tools, permissions, prior interaction, and continuation state.

Inspect how the harness selects, orders, transforms, and exposes environmental information. Repository presence does not guarantee observation: retrieval can omit a document, compaction can transform prior context, and tool output can hide or distort a condition. Identify which authority, task information, examples, interfaces, and state actually reach the agent and which prior tendencies can fill a gap.

Keep model- or harness-specific assumptions explicit. Agent output remains probabilistic, and behaviour can change across models, versions, effort settings, tool surfaces, and context histories.

## Shape environmental text

Use text to condition the concepts, relationships, and actions needed for the intended effect:

- state the required result and supply the context that can change it;
- put durable authority at its canonical scope and keep task-local conditions with the task;
- make authority, conditions, permissions, boundaries, and conflict resolution explicit where ambiguity can change action;
- state each governing instruction once and remove repetitions or examples that no longer earn their context cost;
- explain rationale when it helps the agent generalize the relationship across situations;
- separate instructions, variable input, examples, and expected output when their roles could otherwise be confused; and
- use examples when they encode a real requirement, cover a consequential boundary, or repair an observed gap without overfitting incidental wording.

Prefer a small set of compatible cues over one enormous instruction or several governing copies. A canonical rule, a matching interface, a constraint, and feedback can reinforce the same frame while remaining independently useful.

## Shape action and execution

Text alone cannot reliably create an effect that depends on actual execution. Shape the executable environment as well:

- expose only relevant tools and give them precise names, inputs, effects, and failure behaviour;
- make safe in-scope actions natural while requiring authority before destructive, external, privileged, costly, or scope-expanding effects;
- align defaults, permissions, and constraints with the intended action boundary;
- return outputs and diagnostics that let the agent distinguish success, failure, uncertainty, and the next valid action;
- preserve authoritative progress, decisions, evidence, blockers, and recovery instructions outside temporary model context when later work depends on them;
- make verification available before the agent claims success; and
- match model capability, effort, context, tools, and concurrency to the task rather than maximizing them without evidence of benefit.

Use actual constraints for important effects when the system can enforce them. Prompted behaviour remains a prediction; actual execution can prevent an undesirable result and provide information that corrects the agent's conception.

## Keep adaptations conditional

Prefer interventions whose causal relationship follows from the shared model: clear goals, relevant context, coherent authority, useful affordances, direct feedback, and durable state. These can survive variation better than compensating instructions aimed at one observed model habit.

Place a model- or harness-specific adaptation at the smallest scope that owns its conditions. Record what behaviour justified it and remove or revise it when representative evidence no longer supports it. Do not turn current provider syntax, tuning advice, or a model workaround into a repository-wide semantic rule.

## Preserve one environment

Apply [human design](human.md) to the complete proposed result. Agent-specific structure must not make the human path noisy, obscure the governing meaning, or create hidden authority that a contributor cannot inspect. Human-oriented prose must not leave an agent's permitted actions, state transitions, or governing boundaries ambiguous.

Choose complementary expressions that make the complete result beneficial to both humans and agents. Machine-readable structure, human-readable explanation, executable constraints, and system feedback can serve different encounters while correcting one another. When the methods conflict, return to the intended effects and causal mechanisms instead of optimizing one participant class in isolation.

## Leave an evaluable hypothesis

State the intervention point, the predicted causal path, the desirable and important undesirable effects, and the applicable model, harness, `situation`, and `encounter-noise` conditions. Record material assumptions, resource trade-offs, and unknowns.

[Environment quality](../quality/README.md) chooses proportionate evidence and judges the resulting effects. Agent design identifies what should happen and why; it does not treat plausible prompting or a successful single response as proof.
