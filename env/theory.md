# Theory

Within [environment engineering](README.md), theory explains why documentation and code influence human and agent cognition and behaviour. That influence exists whether or not the environment was designed deliberately. Environment engineering makes it intentional.

Documentation and code express meanings and systems as text. Those systems can shape cognition through conceptual execution and produce consequences through actual execution. The combined environment can therefore produce effects that the local quality of either documentation or code does not predict.

> **Conceptual and actual execution**
>
> Execution belongs to a system as a whole, not to each artifact that expresses it. An artifact need not be independently runnable to have actual effects: a linter applies a lint rule, a type checker enforces a type declaration, and an API implementation realizes an API definition.
>
> **Conceptual execution** occurs when a human or agent reasons through a system: following its relationships, anticipating its constraints, simulating an action, or predicting an outcome. This execution directly shapes reasoning and behaviour without producing the system's actual effects.
>
> **Actual execution** occurs when a human or agent follows a procedure, a machine runs code, or those acts combine to carry the system into effect. Its results—including outputs, diagnostics, permitted or prevented effects, and changed state—become environmental information that can confirm, correct, or otherwise change conception.
>
> Linters, static type systems, formal proofs, APIs, automated and manual tests, CLIs, and other interfaces can participate in both modes. A conceptual model executes only conceptually: parallel systems can express, enforce, test, or instantiate its relationships, but those systems perform the actual execution.

## Environment and behaviour

An environment supplies causes; cognition, behaviour, and system effects are among their consequences. The relationship is conditional rather than uniform. The same text can produce different interpretations for participants with different prior knowledge, and the same system can expose different actions in different situations.

For this theory, a **participant** is an applicable human or agent. A **behaviour** is an action or output produced by a participant. An **environmental effect** is a consequential change in cognition, behaviour, or the result that a system permits or produces.

Environmental systems can affect behaviour through both modes of execution. Their expressions and interfaces supply cues, relationships, affordances, and defaults for conceptual execution. Their actual execution realizes constraints and consequences and produces feedback and persistent state. A participant can still attempt a behaviour that the system prevents. The resulting observation can then change the participant's conception of the system.

The environment does not determine every behaviour by itself. Human prior experience, model parameters and decoding policies, and conditions outside the environmental boundary also matter. The theory instead identifies causal mechanisms through which environmental conditions can change what becomes likely, familiar, detectable, or possible.

## Environmental encounter

The **total environment** is the complete environment created by documentation and code for one subject in one state. It includes readable text and the action surfaces, constraints, responses, and persistent state expressed by its systems. A participant acts from an **observed environment**: the part of those environmental conditions available in the applicable situation.

For the equation in this section, `participant` ranges over applicable humans and agents. `situation` contains the task, location, project state, and other conditions that change what the participant encounters. `encounter-noise` ranges over conditions that omit, substitute, or distort environmental information before it becomes available to the participant. `environment-channel` includes selection, ordering, transformation, and exposure by documentation and systems. For every applicable `participant`, `situation`, and `encounter-noise`, this root equation defines the observation:

```text
observed-environment(participant, situation, encounter-noise)
= environment-channel(
    total-environment,
    participant,
    situation,
    encounter-noise
  )
```

The observed environment can contain the complete environment when the channel exposes it without noise. Otherwise, it is a projection rather than necessarily a literal subset. Retrieval can select text, a summary can transform it, a diagnostic can derive new information, and a tool can expose an action without exposing its implementation.

## LLM probability conditioning

For an autoregressive LLM, observed environmental text affects behaviour when it is serialized into the model context. The model assigns each possible next token a conditional probability from its parameters, that context, and the response prefix already generated. Each generated token extends the prefix and conditions the next choice. Environment engineering can therefore change a direct input to the probabilities from which a response is generated.

For the equations in this section, `model` is fixed. `context` is the serialized token sequence available before generation. `empty-response` is the empty token sequence, and `append-token(response, token)` adds `token` to the end of `response`; together they build every finite `response`. `token` ranges over tokens supported by the model. `next-token-probability(model, context, response, token)` is the probability assigned to `token` after `context` and the existing `response` prefix. A completed response includes a terminal token when the model uses one. These root equations define its model-assigned probability:

```text
model-response-probability(model, context, empty-response) = 1

model-response-probability(
  model,
  context,
  append-token(response, token)
)
= model-response-probability(model, context, response)
  * next-token-probability(model, context, response, token)
```

The recurrence matters to environment theory because contextual influence composes across the response. Environmental cues need not describe a complex target response directly. Compatible cues can instead condition successive choices towards concepts, relationships, and actions that support the response as a whole.

## Human schema activation

Environment engineering models human environmental effects through schema activation. A **schema** is a learned structure that organizes concepts, relationships, expectations, and action patterns. In this model, environmental cues activate applicable schemas and make them more influential in current interpretation, recall, inference, and action selection.

Examples can establish prototypes. Terminology can supply categories and causal roles. Structure can imply hierarchy and authority. Interfaces and affordances can represent available actions. Defaults can represent a normal path, while feedback can frame an outcome as success, failure, or irrelevance. Several compatible cues can activate overlapping schemas and establish an understanding that no one cue expresses completely.

Conceptual execution occurs when the activated schemas let a human follow the system's relationships or anticipate its operation. Actual results can then activate different schemas, revise expectations, or expose a mismatch between the system conceived and the system encountered.

The model also treats learned affective and action dispositions as activatable alongside conceptual schemas. Their joint activation shapes immediate expectations, preparation, and behaviour, while experience forms and revises the underlying structures over time.

## Durable frame reconstruction

A **frame** is a coherent, situation-relevant configuration of concepts, relationships, expectations, and possible actions. It is an environment-engineering abstraction across the distinct LLM and human mechanisms above. Only the parts of a frame that can change the effects the author intends or the important undesired effects they seek to avoid are consequential. An adequate reconstruction preserves those parts; it may vary elsewhere.

Pentagram work depends on a frame that combines concepts, standards, behaviours, and expertise. Reproducing that combination in every prompt or explaining it completely before a human contributes is infeasible. The repository environment makes the frame durable instead.

Each participant works from a temporary, situation-specific reconstruction. An agent's reconstruction is conditioned through active context; a human's is activated through environmental cues. Neither reconstruction is the durable authority. Current documentation, code, and project state preserve the material from which an adequate frame can be reconstructed.

Compatible cues make reconstruction easier and more reliable. One surface can state a concept, another instantiate it, another constrain incompatible action, and another expose divergence. Their overlap can establish a frame too complex to express as one prompt or introductory explanation. The cues need compatible meaning, not identical wording or duplicated authority.

## Error correction

Within environment engineering, an **error** is any distortion that makes a participant's reconstructed frame inadequate for the situation. Errors can arise from prior tendencies, incomplete information, incorrect interpretation, minor conflicts within the environment, or outside influence. Each can change which relationships the participant perceives and relies on.

Errors can remove, distort, or give undue weight to parts of the frame. A small gap or conflict need not remain local: it can let a competing prior supply a relationship, change how other cues are interpreted, and redirect conceptual execution and behaviour. Documentation and code can therefore remain individually sound while the combined environment establishes a frame that leads away from the effects the author intended.

Good error correction is a robustness property of that combined environment. Despite such errors, the environment still produces the intended effects and avoids important undesired effects. It can do so by helping the participant recover an adequate frame, by preventing or containing an undesired effect during actual execution, or by combining both forms of correction. The results of actual execution can also supply environmental information that corrects conception.

Text and actual system behaviour can express the same relationships in different ways, so one can correct a distorted understanding of the other. Canonical authority prevents these complementary expressions from becoming several governing versions of the same meaning.

Internal consistency strengthens this property. A well-engineered environment minimizes self-conflicts to the greatest practical extent. When conflicts remain, explicit conflict-resolution rules identify which meaning governs and how the participant or system should proceed. These rules keep a minor conflict from making recovery ambiguous.

## Intervention theory

The environmental effects described above occur whether or not anyone designed them deliberately. Text conditions LLM probabilities and activates human schemas. Systems support conceptual execution, produce actual effects, and help the combined environment remain robust against error. Changing the environment can alter one or more of these causal conditions.

An **environmental intervention** is a deliberate change to documentation or code made to change an environmental effect. The intervention need not express the entire intended frame as a direct instruction. It can instead change what a participant encounters, how they reconstruct or conceptually execute a system, what actual execution permits or produces, or how well the combined environment corrects error.

The author's intent identifies the effects the intervention should cause and the important undesired effects it should avoid. Intervention theory turns that intent into a causal hypothesis: changing an environmental cause should change the relevant cognition, behaviour, or actual effect. [Design](design/README.md) uses the hypothesis to choose an intervention, and [quality](quality/README.md) compares the resulting effects with the author's intent. The intervention points therefore follow from the preceding mechanisms, not from a generic preference for more documentation or automation.

| Intervention point          | Theoretical basis                                                                                                                                                               |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Environmental text          | When encountered, content, terminology, examples, models, and readable code can alter LLM context, activate human schemas, and make systems available for conceptual execution. |
| Environmental channel       | Location, structure, retrieval, ordering, and tool exposure alter the environment available in a situation.                                                                     |
| Action surface              | Interfaces, affordances, and defaults change which actions appear available or normal.                                                                                          |
| Actual execution            | Execution by humans, agents, or machines realizes constraints, checks, transformations, and other consequences.                                                                 |
| System response and state   | Diagnostics and output change conception; persistent state preserves conditions needed for later reasoning and action.                                                          |
| Cross-surface reinforcement | Compatible expressions provide several cues and make frame reconstruction robust against error.                                                                                 |

An intervention can act through several points at once. Source code can supply textual cues, define an action surface, enforce a constraint, and produce feedback. Changing a system's expression can alter conceptual execution even when its actual operation remains constant. Changing actual execution can alter conception through the resulting observations. The points identify distinct causal reasons for expecting effects; they do not require separate artifacts.

A plausible mechanism supports a prediction; it does not establish that the intervention works. Evidence must address the predicted direction, coverage, and robustness against error.
