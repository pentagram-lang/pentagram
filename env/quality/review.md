# Review

[Quality](README.md) uses independent review to find defects in how documentation and code work together as an environment. The reviewer investigates the assigned causal relationship; the reviewee evaluates the evidence and owns project decisions.

Use the [shared review procedure and record formats](../../doc/quality/review.md): **assign → review → evaluate → repair → re-review**. This document supplies the environmental subject, criteria, and evidence requirements. Documentation-only lenses do not automatically apply to environment review.

Re-review remains the default after repairs. Ordinary repairs stay in the current authorized task. Sharing the procedure does not give a reviewer authority to prescribe repairs, expand scope, or decide closure.

## Bound the environmental review

Start from the identified intent, the affected `total-environment`, its state, and its dependencies. Include every documentation, code, interface, tool, response, and state boundary needed to judge the effects in scope.

Use [environment criteria](criteria.md) as the quality authority. Follow its delegation to intent, theory, design, and the requirements of the affected documentation, code, and systems. Supplied intent names effects to assess, not a desired review conclusion; supplied authority does not restrict contextual investigation.

For each effect, identify credible ways it could diverge from intent and how serious that would be. This **environmental risk** determines evidentiary strength. Trace the effects each affected surface can materially change. This **environmental leverage** determines evidentiary breadth, including relevant effects beyond the immediate change. Stop expanding the boundary when no further material effect can change through the causal path.

Choose investigation depth, evidence, checks, and lenses from that basis, not from a numerical score or a universal checklist. Relevant lenses can include causal integrity, human and agent compatibility, instruction hierarchy, execution agreement, feedback and recovery, permissions, resource cost, and model or harness drift.

Before assigning review, weigh the material evidence it can add against authoring and maintenance effort, reviewer context, compute, and system work. Use the smallest adequate set of reviews; no formal review is required when it cannot add material evidence. This initial selection does not remove the default re-review path for repairs chosen during a review.

## Supply the environmental inputs

Use the shared assignment form with this guide as its protocol. In Subject and scope, identify the environmental boundary. In Review basis, state the risk, leverage, and evidence needed. Supply these inputs directly or through specific accessible references:

- Intended desirable effects and important undesirable effects.
- Applicable human and agent participants, situations, and encounter noise. State explicitly when no encounter noise is in scope.
- The causal hypothesis, material assumptions, and frame distortions it must correct.
- Relevant environmental state, dependencies, and existing evidence.

Keep state created or preserved by documentation and code in the `total-environment`. Reports, including incorrect claims and unwanted advice, are environmental state—not encounter noise. A situation may select or refer to that state; do not duplicate it as an independent input.

Active project state is excluded unless the assignment names it as part of the environment or as evidence. Only that named state may be inspected; `0 proj` may be used only when needed to retrieve it. Do not expose authoring conversation or prior review conclusions to an initial reviewer.

The shared current/change distinction applies: supply a comparison base and complete inspected diff only when the judgement depends on the change. A diff never replaces the complete affected environment.

## Report environmental evidence

Use the shared report without repeating the assignment's intent, inputs, risk, or leverage. Record what was actually assessed and any material limits or deviations from that assignment.

Coverage must identify both the environmental surfaces inspected and the effects, participant conditions, requirements, and lenses assessed. Explain the causal relationships evaluated, the observations and checks used, and any material evidence gaps. Record applicable human expertise, if any, with the reviewer information; do not imply expertise that was not supplied.

Each finding must identify the affected effect and boundary, the observed defect, its governing requirement and causal evidence, and its consequence and uncertainty. Explain the affected surface's causal reach and the seriousness of the consequence where they matter. These belong in the shared finding fields, not in another report schema.

Separate observed defects from predictions. Give the causal basis and limits of a prediction; never present an unobserved human, agent, or execution effect as an observed failure. Review may assess human-effect risks from design principles, theory, and available evidence, but does not conduct human studies. Missing evidence is a gap to record, not permission to invent an effect or assign remedial work.

For re-review, report current evidence against each original finding, not a resolution verdict. The reviewee applies the shared evaluation, ignores any fix suggestions, and decides dispositions and work on the project basis. Apply environment criteria to the final environment-quality judgement. Use [environment tests](test.md) when trials can add material evidence; a completed review or a documentation-quality pass does not establish environment quality.

## Combine documentation and environment review

Use one assignment and one report when the same investigation can adequately cover both subjects. Name both protocols, their subjects, and their criteria; give each boundary the lenses and evidence it needs. In particular, assess poor readability and needless reading work separately for documentation.

Share reviewer metadata and other administration. Within Coverage, distinguish documentation assessment from environment assessment. A finding that crosses both can be recorded once with both requirements and evidence identified. Keep the final documentation and environment quality judgements separate in the reviewee's evaluation. Neither assessment silently establishes the other.
