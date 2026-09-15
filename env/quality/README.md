# Quality

Environment quality judges whether the complete environment is clearly correct for its intended use. It must produce or preserve every desirable effect, avoid every important undesirable effect, and satisfy every applicable requirement for the participants and situations in scope. Participants in scope must be able to understand what the environment means and use it as intended under the named conditions. The environment must not require them to supply unstated meaning, reconcile contradictions, or perform avoidable work that it could perform itself.

This is a combined judgement. Documentation can be accurate and code can satisfy its contract while their interaction still causes confusion, unsafe action, or a misleading result. [Documentation quality](../../doc/quality/README.md) judges the documentation as written, and the [coding standards](../../code/README.md) govern code and implementation tests. Environment quality judges what the combination causes participants to understand, do, and observe, including results that actual execution permits or produces.

[Criteria](criteria.md) explains the judgement and the evidence boundary. [Test](test.md) puts an implemented environment into a realistic agent encounter when that can add useful evidence. [Review](review.md) independently inspects the causal relationship between documentation, code, participants, actions, and results.

Environment quality follows the [environment theory](../theory.md) and the [manifesto's aims](../../manifesto.md). Name the subject, intent, conditions, and evidence that support each quality judgement. Intent need not be part of the environment surface; [intent](../intent.md) says when to record it, and a review handoff may supply it through an accessible source. Private conversation and author memory cannot supply missing meaning.

## Criteria

[Criteria](criteria.md) explains risk, causal reach, evidence, and pass, fail, or inconclusive judgements.

## Test

[Test](test.md) explains environment-test contracts, agent encounters, and the limits of their assertions.

## Review

[Review](review.md) explains the author's process for arranging and evaluating independent review of documentation and code as one environment.

## Review protocol

[Review protocol](review-protocol.md) tells reviewers how to inspect an environment and report every supported problem that makes it unclear or incorrect.
