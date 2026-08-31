# Design

Within [environment engineering](../README.md), design chooses environmental interventions: deliberate changes to documentation, code, or both that are intended to change an environmental effect. It starts from the effects and encounter conditions identified through [intent](../intent.md). [Intervention theory](../theory.md#intervention-theory) supplies the causal model. Design uses the intended effects and causal model to state why changing particular environmental causes should produce the desirable effects and avoid the important undesirable effects.

Design must account for every part of the `total-environment` that can materially change those effects. This includes readable documentation and code, action surfaces, constraints, system responses, persistent state, and relevant dependencies owned by another subject. An intervention may change one surface, but its causal hypothesis must explain how that change works with the other material causes throughout the environment.

Human design and agent design are different methods for designing that one environment, not separate environments. Use the human method for effects on human participants and the agent method for effects on agent participants. Use both when the intended effects apply to both, and combine the interventions they identify into one design. The human method traces schema activation, conceptual execution, action, and recovery. The agent method traces context conditioning, instruction interpretation, tool use, state recovery, and verification.

Humans and agents may need different expressions or paths. Those differences must preserve the same meaning and governing authority and must expose compatible actions, constraints, feedback, and state. A cue, affordance, constraint, response, or state introduced for one participant class cannot contradict or quietly obstruct the other.

The complete environment must benefit both humans and agents, but every individual cause need not benefit both. Keep participant-specific material at the smallest scope where it changes the effect, without burdening other encounters or creating another governing version. When documentation, interfaces, constraints, feedback, or state express the same relationship, make them confirm or correct one another instead of duplicating authority. A benefit for one participant does not compensate for an important undesirable effect on another.

## Human

[Human design](human.md) shapes schema activation, conceptual execution, action, feedback, and recovery for human participants in their actual situations.

## Agent

[Agent design](agent.md) shapes context conditioning, instruction interpretation, tool use, state recovery, and verification for agent participants in their actual harnesses.
