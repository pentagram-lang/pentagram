# Test

[Quality](README.md) uses test to put an implemented environment into realistic agent encounters and observe its effects. An environment test can exercise documentation, code, interfaces, tools, permissions, state, and system responses together. The result comes from observations that support or contradict effects in cognition, behaviour, or system results—not from an agent's opinion that the environment worked.

Environment tests supply bounded evidence under recorded conditions. They consume author effort, agent context, compute, and maintenance work, and a trial can itself expose agents or systems to consequences. Design only the coverage and trials whose evidence justifies those costs.

Environment testing does not conduct human studies. It can exercise system effects relevant to humans, but it cannot establish human cognitive or behavioural effects without applicable evidence produced elsewhere.

## Design effect coverage

Design test coverage for the effects within the identified intent that an agent trial can observe. For each such desirable and important undesirable effect, consider:

- the applicable agent `participant`, `situation`, and `encounter-noise` inputs;
- the consequence if the environment produces the wrong effect;
- uncertainty about the causal hypothesis and implemented result;
- environmental leverage and variation;
- evidence already available from inspection, checks, ordinary tests, prior trials, review, and operation; and
- the cost and risk of preparing, running, and maintaining a trial.

The right coverage can be several tests, one test, or none. Choose the smallest set that can add material evidence to the judgement governed by [criteria](criteria.md). Choosing no environment tests is valid when other evidence is adequate; the absence of tests does not itself establish that decision.

Reassess coverage when the intent, environment boundary, intervention, participants, system state, models, harnesses, observed effects, or existing evidence changes. A failed or surprising encounter is key evidence. It can reveal a missing effect, an invalid causal hypothesis, inadequate coverage, or a test whose conditions no longer represent the environment.

## Plan current trials

Coverage determines which effects may need test contracts. A run plan determines which trials need current evidence.

Plan across the complete coverage rather than running every available test. Select a trial when its evidence can materially change the current judgement. Scale its agent conditions, situations, encounter noise, repetitions, and environmental variation to the consequence and uncertainty it can resolve. Stop adding trials when the available evidence is adequate.

Do not vary conditions merely to accumulate runs. Vary a model, harness, task, access method, project state, failure, interruption, or information loss when the identified effect ranges over that condition or evidence shows that it can change the outcome.

## Define the test contract

Before a trial, record:

- the subject and affected `total-environment`;
- the relevant environment state and cross-boundary dependencies;
- the desirable or important undesirable effect being tested;
- the applicable `participant`, `situation`, and `encounter-noise` inputs;
- the causal hypothesis and intervention points under test;
- the environmental channel the trial will expose;
- the realistic task or encounter;
- observable assertions, including prohibited effects where their absence matters;
- fixtures, safety limits, permissions, and other trial conditions; and
- the evidence the trial can and cannot establish.

State assertions as observable responses, behaviours, system results, feedback, or persistent state. When cognition matters, identify a response or action that provides evidence for it and preserve the limits of that inference. Do not request private reasoning or accept participant self-assessment as proof.

A test contract does not authorize destructive, external, privileged, credentialed, or irreversible action. Obtain the required authority or use a safe representative fixture.

Keep the contract and resulting evidence with the subject when another contributor, system, or future decision must rely on them. The record can use project evidence during active work; preserve durable claims in the subject's documentation or tests when they must remain part of the governed system.

## Run an agent trial

Use an agent trial when an intended effect applies to an agent and depends on the wider context, instruction hierarchy, retrieval, tools, permissions, repository state, system responses, or interaction among surfaces.

Start a fresh agent without inherited authoring conversation or hidden evaluator context. Give the agent the realistic task and expose exactly the environmental channel named by the contract. Do not give it the test assertions, expected observations, or extra hints added only to make the trial pass. Permit or exclude repository areas, tools, project state, and prior interaction according to the situation being tested rather than a universal test sandbox.

Preserve the returned answer and citations, tool calls and outputs, produced artifacts, system effects, feedback, and persistent state. Record the agent, harness, exposed model and reasoning configuration, available tools, permissions, environment state, task, encounter noise, and material limitations. State when the harness does not expose a relevant condition.

One agent trial establishes only one result under its recorded conditions. Test representative variation only when the intent ranges over it and the added evidence justifies its cost. A fresh agent cannot establish effects that depend on a continuing context; reproduce or supply that context as part of the recorded environment instead.

## Judge and preserve the result

Before judging assertions, confirm that the trial used the recorded environment and agent encounter conditions, kept hidden evaluator information out of the encounter, respected every safety and authority condition, and produced usable observations. A material condition that was violated or cannot be established makes the affected evidence unusable or inconclusive.

Mark every assertion `satisfied`, `failed`, or `inconclusive` and cite the observation. The trial passes when every assertion is satisfied, fails when any assertion fails, and is otherwise inconclusive. The supported claim cannot exceed the assertions and recorded conditions.

A failed trial does not identify its own cause. The defect can belong to intent, design, documentation, code, the environmental channel, the test contract, trial execution, or an external condition. Investigate and repair the source. Do not add cues that exist only in the trial or weaken an assertion merely to obtain a pass.

Preserve the contract, observations, assertion judgements, overall result, environmental conditions, and limitations as [criteria](criteria.md) evidence. Reconcile the environment and rerun only the affected coverage when a repair invalidates earlier evidence.

[Documentation testing](../../doc/quality/test.md) remains the method for a named documentation outcome. Use environment testing when the effect depends on the combined instruction hierarchy, repository composition, action surface, execution, feedback, state, or interaction among systems.
