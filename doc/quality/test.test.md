# Tests

## Find the documentation-test contract

**Task**

When running a Pentagram documentation test, what repository access should the trial subagent have, what must remain hidden, and what can one passing trial establish? Explain how you know.

**Assert**

- The answer runs the test against the repository as it exists.
- The answer gives the subagent the task but hides the companion and assertions.
- The answer tells the subagent not to read `*.test.md`.
- The answer permits normal access to the rest of the repository unless a narrow exclusion prevents material contamination.
- The answer says one passing trial establishes only one result under its recorded conditions.
- The answer identifies `doc/quality/test.md` as the governing source and cites the relevant sections.

## Reject a contaminated trial

**Task**

A trial subagent returned the expected answer, but it inherited the authoring conversation and read the test companion before answering. Decide whether the result is usable evidence. Explain what a valid rerun requires and how its result should be judged.

**Assert**

- The answer rejects the original result even though its content was correct.
- The answer identifies inherited context as a validity failure.
- The answer identifies access to the test companion and assertions as a validity failure.
- The rerun starts a fresh subagent with no inherited conversation context.
- The rerun uses the repository as it exists.
- The rerun gives the subagent the task but hides the companion and assertions.
- The rerun tells the subagent not to read `*.test.md`.
- The rerun allows normal repository access outside any narrow, consequential exclusion stated in the task.
- The coordinator preserves returned answers and citations, produced artifacts, and observable effects.
- The coordinator records the test name, task, subagent, harness, exposed model and reasoning configuration, trial conditions, and material limitations.
- The coordinator does not request or infer private reasoning.
- The coordinator confirms that every task condition was followed before judging assertions.
- A violation or unverified required condition makes the trial unusable and requires a rerun.
- Each assertion is marked `satisfied`, `failed`, or `inconclusive` from observed evidence.
- The overall result follows from the assertion statuses and remains limited to all recorded conditions.
- The answer cites the test contract and explains how it governs the rerun and judgement.

## Design test coverage

**Task**

A contributor is deciding the documentation-test coverage for two complete subjects. One is a short index whose navigation has strong lint, review, and prior-use evidence with no material uncertainty. The other is a new recovery procedure for an irreversible data migration that has never been tried by an unfamiliar reader. Later, an unfamiliar reader skips a required safety check in the recovery procedure.

Explain how the contributor should design and maintain test coverage for both subjects.

**Assert**

- The answer assesses reader outcomes across each complete subject rather than deciding one test at a time.
- Consequence, uncertainty, and the available evidence govern the coverage for each subject.
- The value of the evidence is weighed against the cost of writing, maintaining, and running the tests.
- Choosing no tests is accepted as a valid design for the index if behavioural trials would add no material evidence.
- The absence of index tests is not itself treated as evidence that zero coverage is correct.
- The recovery procedure receives the smallest test set that adequately addresses its higher consequence and uncertainty.
- The observed reader failure is treated as key evidence and causes the complete recovery coverage to be reassessed without assuming which system caused it.
- The contributor reconciles existing companions with the resulting design instead of treating them as fixed.
- The answer cites the test contract and explains how it governs coverage design.

## Plan test runs

**Task**

A documentation surface has three tests covering navigation, recovery decisions, and recovery actions. Navigation has not changed and has strong current evidence. A repair changes the recovery guidance after an unfamiliar reader skipped a required safety check.

Decide which tests need current runs and how strong those trials should be. Explain the basis for the plan. Keep the run decision separate from deciding which test contracts should exist.

**Assert**

- The answer assesses the complete test set and separates the run plan from coverage design.
- Consequence, uncertainty, affected reader outcomes, the continued relevance of existing evidence, and trial cost govern the run plan.
- The failed reader outcome is treated as key evidence that changes confidence in the recovery outcomes without assuming which system caused it.
- Recovery tests that can expose material defects in the repaired guidance receive current runs.
- The unchanged navigation test is not run merely because it exists when its evidence remains adequate.
- The plan can contain zero, one, or several tests rather than imposing a universal quota.
- Reader situations, conditions, breadth, and trial count are scaled only for the selected tests.
- The plan stops adding trials when the available evidence is sufficient for the quality decision.
- The answer cites the test contract and explains how it governs the run plan.

## Design a documentation test

**Task**

Draft a one-test companion for `doc/quality/criteria.md`. The test should establish whether a reader can decide if documentation with clear prose but a false governing claim meets the quality standard. Name the companion path, provide its complete Markdown contents, and state how the trial should be run.

**Assert**

- The companion path is `doc/quality/criteria.test.md`.
- The Markdown has the exact `Tests` H1, one uniquely named test H2, and no other headings.
- The test uses bold `Task` and `Assert` labels in that order and does not use them as headings.
- The task contains every condition specific to that test.
- The task requires a decision that reveals whether the reader applied criteria; it does not ask the reader to assess their understanding.
- The assertions describe observable answer content, including the conclusion that clear prose cannot compensate for false meaning.
- The trial runs a fresh subagent against the repository with no inherited conversation context.
- The trial tells the subagent not to read `*.test.md` and gives it the task, but not the assertions or companion.
- The trial adds no other reading exclusion unless the exclusion prevents material contamination of the intended reader situation.
- The trial applies every condition stated in the task.
- The draft does not add a mandatory `Authority` field.
- The answer cites the test contract and explains how it governs the companion and trial.

## Choose the test kind

**Task**

A contributor needs evidence for three cases:

1. A parser function returns the documented syntax tree for a fixed input. The evidence does not depend on what a reader understands or does.
2. A reader uses a recovery guide to identify the safe action. The contributor needs to establish that the documentation enabled the reader's understanding and choice, not that a recovery system executed.
3. An agent works with the complete repository documentation and recovery command. The intended environmental effect includes choosing the safe command and the command preserving the recorded state.

For each case, choose a documentation test, environment test, or implementation test. State which assertion classes it permits and where any documentation or environment test companion can live. Explain the governing basis and keep the agent's action distinct from the system's result.

**Assert**

- The parser case uses an implementation test and asserts only the result of actual execution.
- The recovery-guide case uses a documentation test and asserts understanding or action attributable to documentation, never a system result.
- The complete-repository case uses an environment test with an agent encounter and includes an action assertion for choosing or invoking the safe command.
- The complete-repository case can include a result assertion because preserving the recorded state is part of the intended environmental effect.
- The answer distinguishes the agent's choice or invocation from the command's effect on state.
- Documentation and environment tests use the same `Tests`, `Task`, and `Assert` companion schema beside any subject file.
- The subject's file type, the observed output, and the companion path do not determine the test kind.
- The answer identifies the documentation-test, environment-test, and coding-test contracts and explains how they govern the choices.
