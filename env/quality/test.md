# Test

[Quality](README.md) uses test to put an implemented `total-environment` into a realistic agent encounter and observe its effects. Environment-test assertions cover participant understanding or action and, when applicable, a result that actual system execution permits or produces.

Environment tests use the `.test.md` companion and `Tests`, `Task`, and `Assert` form owned by [documentation testing](../../doc/quality/test.md#store-tests-beside-their-subject). They have a different causal boundary and assertion scope. A documentation test attributes understanding or action to documentation. An environment test attributes understanding or action, and any asserted result, to the complete environmental encounter.

Environment testing does not conduct human studies. Existing evidence of human effects can still contribute to the quality judgement governed by [environment criteria](criteria.md).

## Use the shared companion

Store an environment test beside any subject file as [documentation testing](../../doc/quality/test.md#store-tests-beside-their-subject) requires. Documentation and environment tests can coexist as sibling H2 tests in the same companion, including a companion for a code file. The file type does not determine the test kind.

Follow the exact [shared test form](../../doc/quality/test.md#write-the-test-contract). The task and assertions determine whether a test supplies documentation evidence, environment evidence, or both. Do not add a type field or another heading level.

## Design environment-test coverage

Test coverage identifies the intended effects that need evidence from an agent encounter. Intent supplies those effects and their applicable agent `participant`, `situation`, and `encounter-noise` conditions. Design supplies the causal hypothesis.

Environment tests consume authoring and maintenance effort, agent context, compute, and system work. These tests are not cheap executable unit tests to accumulate or run by default.

For each effect, weigh its environmental risk and the affected environmental surface's leverage across all effects, the evidence already available, and what an encounter could establish against the resources required to create, maintain, and run the test. Higher risk can justify stronger evidence for the scoped effect; higher leverage can justify broader coverage of other effects the surface can change. Expand coverage only where an encounter can add material evidence. The right coverage can be several tests, one test, or none; choose the smallest set that provides adequate evidence across the applicable encounter conditions.

Use a documentation test when every assertion concerns reader understanding or action attributable to documentation. Use an implementation test when every assertion concerns results of actual execution and does not depend on participant understanding or action. Use an environment test when an agent encounter with the affected `total-environment` must establish understanding or action. Add a result assertion only when actual execution is part of the intended environmental effect.

Reassess coverage when the intent, design, environment, or evidence changes. Compare the needed coverage with the current companions, then create, change, move, or remove tests to make them agree.

## Plan environment-test runs

Coverage design determines which tests exist. A run plan determines which tests need current evidence.

Run an encounter only when the evidence it can add to the environment-quality judgement justifies its resource use. Use the applicable encounter conditions supplied by intent, and stop when the available evidence is adequate. Running several tests, one test, or no tests can each be appropriate.

New evidence can change both coverage and the run plan. Reassess coverage first, then plan the runs.

## Write the encounter and assertions

In `Task`, give the agent a realistic situation and include every condition that can change the observed environment. State fixtures, available tools, permissions, relevant state, prior interaction, or narrow access exclusions only when the encounter depends on them.

Every assertion must describe an intended environmental effect:

- **Understanding** is evidenced by observable answer content, explanation, or decision.
- **Action** is evidenced by observable output, tool use, artifact, or omission of a prohibited action.
- **Result** is evidenced by an observable consequence that actual system execution permits or produces.

An environment test can use understanding or action as its only assertions. Include a result only when it is part of the intended effect under test. Do not request private reasoning or accept self-assessment as evidence of understanding.

Assertions describe effects, not the environmental causes predicted to produce them. Inspect causes directly and use [review](review.md) to find defects beyond the named effects.

## Run and judge the encounter

Run the test from the repository root against the repository as it exists. Start a fresh agent without inherited authoring conversation. Give the agent `Task`, but hide the companion and `Assert`. Tell the agent not to read `*.test.md` or active project state and not to run `0 proj`, unless project state is an explicit part of the encounter.

Expose the environmental channel named by the task. Preserve the returned answer and citations, tool calls and outputs, artifacts, system results, feedback, and state. Record the agent, harness, exposed model and reasoning configuration, available tools, permissions, environment state, encounter noise, and material limitations.

A test contract does not authorize destructive, external, privileged, credentialed, or irreversible action. Obtain the required authority or use a safe fixture.

Confirm that the encounter followed every task condition before judging it. Mark each assertion `satisfied`, `failed`, or `inconclusive` from the preserved evidence. The test passes when every assertion is satisfied, fails when any assertion fails, and is otherwise inconclusive. Its result is bounded to the assertions and recorded conditions; [environment criteria](criteria.md) applies it with the other available evidence.
