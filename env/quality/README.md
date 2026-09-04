# Quality

Within [environment engineering](../README.md), quality judges whether the implemented `total-environment` produces or preserves the desirable environmental effects and avoids the important undesirable environmental effects identified through [intent](../intent.md). It evaluates documentation and code together across the applicable `participant`, `situation`, and `encounter-noise` inputs. Locally correct artifacts do not compensate for an environment that produces an important undesirable environmental effect.

Every repository change has environment-quality authorship. The author identifies the affected environment from the effects and their material causes, not only the changed artifacts. They account for its relevant state, cross-boundary dependencies, and interaction with the existing environment.

The [documentation quality system](../../doc/quality/README.md) continues to govern documentation, and the [coding standards](../../code/README.md) continue to govern implementation and ordinary tests. Environment quality owns the combined environmental effects that neither artifact boundary establishes alone.

Quality begins with the identified intent and the causal hypothesis from [design](../design/README.md). It ends with a judgement over the complete evidence. Criteria governs that judgement. Test and review provide formal environment-specific evidence only when the material evidence they can add justifies their full resource cost: authoring and maintenance effort, participant context, compute, and system work.

Environment quality scales evidence through two distinct properties. **Environmental risk** belongs to an effect in scope: it is the possibility and seriousness of that effect going wrong because the environment fails to produce or preserve a desirable environmental effect or produces an important undesirable environmental effect. Assess it qualitatively from the credible ways the effect can diverge from intent across its applicable inputs and how seriously those divergences matter. Risk governs the strength of evidence needed for that effect.

**Environmental leverage** belongs to an affected environmental surface: it is that surface's causal reach across every environmental effect it can materially change, including effects outside the immediate scope. Trace plausible causal paths from the surface until no further material effect can change through them. Leverage governs the breadth of evidence needed across those effects. Neither property produces a numerical score.

Environment quality does not define a separate lint category. Exact mechanical rules remain with the documentation, code, interface, or system that owns them. Their checks provide bounded evidence about environmental causes and actual execution; they do not establish the complete environmental effects by themselves.

## Criteria

[Criteria](criteria.md) combines the governing intent, design, artifact requirements, and available evidence into a pass, fail, or inconclusive environment-quality judgement.

## Test

[Test](test.md) puts the complete environment into an agent encounter and observes understanding, action, and any applicable system result under recorded conditions.

## Review

[Review](review.md) uses independent judgement to find causal, cross-surface, participant, execution, recovery, and resource defects that direct inspection and trials may miss.
