# Human design

Within [environment design](README.md), human design turns identified effects into an environment that works for the applicable humans. Intent already supplies those effects and their applicable `participant`, `situation`, and `encounter-noise` conditions. The [human schema model](../theory.md#human-schema-activation) explains how environmental cues shape conception and action.

The principles below govern the design together. Each principle changes a design decision; none is a checklist of techniques.

## Design the whole experience

A human experiences a task, not an artifact. Documentation and executable systems succeed or fail as one path even when different subjects own them.

Follow the task from the human's starting condition through to the consequential task result. Design every transition that can break orientation or change meaning. Do not accept a clear page, usable command, or sound implementation when the complete path still prevents the intended effect.

> **Example**
>
> A migration guide is not complete when it explains the transformation command. The experience also includes recognizing whether migration is needed, reviewing the result, resolving a partial failure, and confirming that the system now uses the migrated state.

## Do the hard work to make the system simple

Simplicity means that the human can form an adequate understanding and act without avoidable effort. It does not mean hiding necessary consequences or replacing clear explanation with a sparse interface.

Move complexity into the environment when documentation or code can resolve it reliably. Make the system self-describing, build on relationships humans can already recognize, and reveal detail when it becomes useful. Remove decisions, translation, and memory work that do not belong to the human's task.

> **Example**
>
> A command asks the human to copy several internal identifiers from another tool. A simpler design derives the identifiers, shows the resolved target for confirmation, and retains an explicit override for the exceptional case. The system carries the routine complexity without taking away control.

## Keep humans in control and support recovery

Humans must be able to understand and direct consequential action. When a participant mistake or system failure remains possible, the environment must make it detectable and support recovery instead of treating perfect attention as a prerequisite.

Make the consequence apparent before commitment. Let the human stop, correct, or reverse an action where the governed system permits it. Use constraints when an important undesirable effect should not remain possible, and make feedback explain the state that actually resulted.

> **Example**
>
> Before deleting generated state, a command shows the exact target and whether regeneration is possible. If deletion fails partway through, it identifies what remains and provides the safe recovery action rather than asking the human to reconstruct the state.

## Design for every applicable human

Accessibility is a condition of successful design, not a repair for a nominal design that already excludes people. The environment must remain perceivable, operable, understandable, and robust for the range of humans and access methods covered by the intent.

Begin with the barriers faced by humans who would otherwise be excluded. Preserve the same governed system across different means of access, but do not force uniform presentation or interaction when a different path removes a barrier. Familiarity and consistency should reduce learning work without freezing a design that evidence shows is inadequate.

> **Example**
>
> A diagnostic that distinguishes warning from failure only by colour is not perceivable through every applicable path. Adding an explicit status term preserves the same meaning in visual, spoken, plain-text, and transformed output.

## Produce a human design hypothesis

State the intended effect the intervention serves, the environmental cause it changes, the resulting path through the whole experience, and the effects predicted under the applicable `participant`, `situation`, and `encounter-noise` conditions. When the effect depends on correcting a frame distortion, state the material distortion and how the path corrects it. Mark unsupported beliefs about humans as assumptions.

[Environment quality](../quality/README.md) uses that hypothesis to select proportionate evidence and judge the implemented result. Apply [agent design](agent.md) to the same proposed environment before accepting it; a human benefit cannot excuse an important undesirable environmental effect on agents.
