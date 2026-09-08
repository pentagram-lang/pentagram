# Environment engineering

Environment engineering studies and designs what documentation and code together cause humans and agents to understand, do, and observe. In this directory, an **environment** means the information available to a participant, the actions the system makes available, the results its execution permits or produces, and the feedback and state that follow.

Documentation and code can each be sound while their combination still gives a reader the wrong idea, makes an unsafe action seem normal, or reports an outcome misleadingly. Environment engineering follows those interactions across the smallest boundary that can change the effect being considered. It does not replace the subject's documentation or code contract.

Use this method when the interaction between documentation and code matters. The [quality guide](quality/README.md) judges the combined result; the [documentation standards](../doc/README.md) and [coding standards](../code/README.md) still judge their own surfaces.

The [manifesto's aims](../manifesto.md) guide environment design:

- **Ergonomics:** make understanding and action easier.
- **Determinism:** make the path to a result explicit and predictable.
- **Efficiency:** avoid moving unnecessary work to participants or systems.

## Theory

[Theory](theory.md) defines the environment model, participants, encounters, effects, execution, and causal boundaries used by the other documents.

## Intent

[Intent](intent.md) records the desirable effects to produce or preserve and the important undesirable effects to avoid.

## Design

[Design](design/README.md) turns intent into changes to documentation, code, or both and states why those changes should work.

## Quality

[quality guide](quality/README.md) judges the complete environment against its intent and selects evidence in proportion to risk and causal reach.
