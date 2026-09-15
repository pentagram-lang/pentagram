# Agent design

Within [environment design](README.md), agent design turns identified effects into an environment that works for the applicable agents. When environmental text reaches model context, [LLM probability conditioning](../theory.md#llm-probability-conditioning) makes it a direct input to model output, while tools and systems determine what generated choices can actually do.

The principles below govern the design together. Each principle changes a design decision; none is a checklist of prompting tricks.

## Specify the result before the process

Design begins with the result the agent must produce, the conditions that make it successful, and the form in which it can be used. A detailed procedure is useful only when following that procedure is part of the required effect.

State the result directly and define the evidence that distinguishes completion from a plausible attempt. Add audience, format, preserved behaviour, and other constraints only when they change that result. Leave the agent freedom to investigate and adjust its approach inside those conditions.

> **Example**
>
> “Repair the parser so it accepts the documented input, preserve all other documented behaviour, add a regression test, and run the focused check” defines a result. A fixed sequence of files to open and edits to make would constrain the approach without improving the contract.

## Treat context as an interface, not a dump

Every contextual cue can change the next generated token. More context is not automatically more understanding: irrelevant material can dilute useful cues, while repeated authority can create competing versions of the task.

Include information because it can change the result. Keep durable authority at its canonical scope, keep task-specific facts with the task, and make the role of each source unmistakable. State a governing instruction once. Use structure whenever the role of adjacent content could otherwise be confused.

> **Example**
>
> The source-control document owns the publication rule; the active task owns the target bookmark. The task links the rule and supplies the target instead of pasting a shortened copy of the rule into every agent encounter.

## Give the agent a clear action boundary

An agent needs to know where autonomous action is expected and where authority must come from elsewhere. Vague caution can produce needless pauses; vague autonomy can produce destructive or external effects that the author never intended.

Define the ordinary in-scope action the agent may complete without interruption. Name the small number of consequential boundaries that require authorization, and state what the agent should do when it reaches one. Where code can enforce an important boundary, make the executable environment agree with the textual authority.

> **Example**
>
> An agent may inspect and edit the requested local files and run non-destructive checks. Publishing the result remains a separate external effect that requires authority for the named target. The boundary permits useful work without implying permission to push it.

## Make tools precise enough to reason about

A tool definition is part of the agent's language for action. If the agent cannot tell when to use a tool, what it will affect, or how to interpret its result, tool use becomes guesswork even when the prose instruction is clear.

Give each exposed action a specific purpose and exact input, effect, result, and failure meaning. Make the natural call express the intended boundary. Return enough information for the agent to decide whether the action succeeded and what remains possible; a silent refusal or ambiguous success result cannot correct the agent's conception.

> **Example**
>
> A publication tool takes an explicit target and reports whether it changed a remote system. When authority is absent, it returns that missing condition without performing the effect. A generic “run command” tool would hide both the boundary and the result.

## Teach the relationship the agent must generalize

Agents can reproduce the surface of an instruction while missing the rule that should govern a new case. A useful design communicates why a condition matters and which variation must preserve it.

Explain rationale when it identifies the invariant or consequence behind a rule. Use clearly separated examples when they establish a real requirement, cover a consequential boundary, or correct an observed failure. Examples should be representative enough that incidental wording does not become the apparent rule.

## Ground claims in observed evidence

An agent should not be able to substitute confidence, intention, or a successful intermediate action for evidence of the required result. The environment must make investigation and verification part of the route to completion.

Require the agent to inspect the relevant subject before making factual claims. Provide checks that observe the actual effect, preserve their output, and make failure actionable. Progress and completion reports must say what the evidence establishes and leave uncertainty visible.

> **Example**
>
> Writing a documentation file establishes only that the file changed. A completion claim follows inspection of the rendered meaning and the applicable documentation check; if either was skipped or failed, the report says so.

## Tune from representative encounters

Prompt, tool, and scaffold effectiveness depends on the task, model, harness, and context history. A workaround inferred from one response can burden every later encounter while fixing nothing general.

Begin with the smallest clear environment that expresses the result and boundaries. Retain an instruction, example, tool exposure, or harness adaptation only when representative evidence shows that it improves the intended effects. Keep condition-specific repairs local and remove them when their evidence no longer holds. Treat model choice, reasoning effort, and concurrency as encounter conditions rather than choices made by agent design.

## Produce an agent design hypothesis

State the required result, the environmental causes the intervention changes, the expected path through context and execution, and the effects predicted under the applicable `participant`, `situation`, and `encounter-noise` conditions. When the effect depends on correcting a frame distortion, state the material distortion and how the path corrects it. Record material model and harness assumptions without generalizing beyond them.

[Environment quality](../quality/README.md) uses that hypothesis to select proportionate evidence and judge the implemented result. Apply [human design](human.md) to the same proposed environment before accepting it; an agent benefit cannot excuse an important undesirable environmental effect on humans.
