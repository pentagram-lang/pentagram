# Quality

Within [environment engineering](../README.md), quality judges whether the implemented `total-environment` produces the effects the author identified through [intent](../intent.md). It evaluates documentation and code together across the applicable `participant`, `situation`, and `encounter-noise` inputs. Locally correct artifacts do not compensate for an environment that produces an important undesirable effect.

Every repository change has environment-quality authorship. The author identifies the affected environment from the effects and their material causes, not only the changed artifacts. They account for its relevant state, cross-boundary dependencies, and interaction with the existing environment.

The [documentation quality system](../../doc/quality/README.md) continues to govern documentation, and the [coding standards](../../code/README.md) continue to govern implementation and ordinary tests. Environment quality owns the combined environmental effects that neither artifact boundary establishes alone.

Quality begins with the identified intent and the causal hypothesis from [design](../design/README.md). It ends with a judgement over the complete evidence. Criteria governs that judgement. Test and review provide formal environment-specific evidence when their value justifies their cost.

Environment quality does not define a separate lint category. Exact mechanical rules remain with the documentation, code, interface, or system that owns them. Their checks provide bounded evidence about environmental causes and actual execution; they do not establish the complete environmental effects by themselves.

## Criteria

[Criteria](criteria.md) combines the governing intent, design, artifact requirements, and available evidence into a pass, fail, or inconclusive environment-quality judgement.

## Test

[Test](test.md) puts the environment into realistic human or agent encounters and judges observable effects under recorded conditions.

## Review

[Review](review.md) uses independent judgement to find causal, cross-surface, participant, execution, recovery, and resource defects that direct inspection and trials may miss.
