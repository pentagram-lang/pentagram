# Test

[Quality](README.md) uses test to put documentation into use, regardless of the file type that contains it. An independent subagent receives a realistic reader task. The trial succeeds or fails through returned answers and citations, produced artifacts, and observable effects—not through the subagent's opinion of its own understanding.

Subagent trials directly observe reader understanding and action that [lint](lint.md) and [review](review.md) can only infer. Documentation-test assertions do not cover results that actual system execution permits or produces. Each trial also consumes substantial time and compute and supports only a bounded claim under its recorded conditions. Documentation tests are valuable evidence, but they are not cheap coding unit tests to accumulate or run by default.

## Design test coverage

Test coverage identifies the reader outcomes that need behavioural evidence. Design coverage for the complete documented subject.

Consider what readers must find, understand, decide, or do. For each outcome, consider the consequences if the documentation fails and the uncertainty about whether readers will succeed. Account for evidence from lint, review, prior trials, and observed use, together with the cost of writing, maintaining, and running the test. A documentation failure is key evidence because it identifies an outcome or requirement that was not met.

The right coverage can be several tests, one test, or none. Choose the smallest set that provides enough evidence across the subject. Add a test only when its evidence justifies its cost. Choosing no tests is valid when behavioural trials would not add material evidence; the mere absence of tests does not establish that conclusion.

Reassess coverage when the subject, its intended use, or the evidence changes. Compare the needed coverage with the current companions, then create, change, move, or remove tests to make them agree.

## Plan test runs

Coverage design determines which tests exist. A run plan determines which tests need current evidence.

Plan across the complete test set. Run a trial only when the evidence it can add to the quality decision justifies its time and compute. Judge that value from the consequences and uncertainty of each reader outcome, the evidence already available, and whether the evidence still applies. The plan can run several tests, one test, or no tests.

For each selected test, choose the reader situation, conditions, breadth, number of trials, and evidence needed. Consequence and uncertainty do not create a score or universal quota. A narrow trial can settle a narrow uncertainty; stronger trials are useful only when they can expose a material defect. Do not run another trial after the available evidence is sufficient for the quality decision.

New evidence can change both coverage and the run plan. A documentation failure can reveal missing or weak coverage, invalidate earlier confidence, or show that existing tests need current runs. Reassess coverage first, then plan the runs.

## Store tests beside their subject

Every test companion ends in `.test.md` and stays beside its subject. Replace a Markdown subject's `.md` ending: tests for `guide.md` belong in `guide.test.md`. Append `.test.md` to any other subject's complete filename: tests for `parser.rs` belong in `parser.rs.test.md`.

The companion path must identify exactly one inventoried subject. Removing `.test.md` from the companion gives its base path. The possible subjects are that base path and the base path with `.md` appended; a base path that already ends in `.md` cannot identify itself. A companion fails when neither or both possible subjects exist.

Placement identifies the subject, not its governing authority or test kind. A documentation test follows [documentation criteria](criteria.md) to the applicable documentation requirements wherever that documentation is expressed. An environment test follows [environment criteria](../../env/quality/criteria.md) to the identified intent, design, and affected documentation and code requirements. The companion stores the stable test contract; test results belong in project or review evidence.

Documentation tests and [environment tests](../../env/quality/test.md) for the same subject coexist in this companion and use the same schema. Either test kind can accompany any file. Each test's task and assertions determine which quality criteria its result can support; the subject's file type does not. Do not create a separate environment-test companion or schema.

## Write the test contract

Every test companion uses this form:

```markdown
# Tests

## Find the governing contract

**Task**

Give the reader a realistic question or action, including every condition specific to this task.

**Assert**

- The answer identifies the governing contract.
- The answer cites the correct section.

## Apply the contract

**Task**

Give the reader another realistic question or action.

**Assert**

- State each required observable outcome.
- State any prohibited outcome.
```

The form has three structural rules:

- The H1 is exactly `Tests`.
- Every H2 is a unique test name with a non-empty `Task` followed by a non-empty `Assert` list.
- No other headings are permitted.

These structural rules apply to both documentation and environment tests. The distinct causal boundary, assertion scope, and additional encounter rules belong to [environment tests](../../env/quality/test.md).

The standard rules in [test: run an independent trial](#run-an-independent-trial) apply to every documentation test. Do not repeat them in a task.

Each documentation-test task owns its reader situation and test-specific conditions. State only conditions that can affect the result, such as fixtures, available tools, narrow reading exclusions, or prior knowledge.

Give the reader enough information to begin without supplying the path, model, or conclusion being tested. State assertions as visible outcomes. Do not ask for private reasoning or self-assessment. Include prohibited outcomes when their absence matters.

When the trial must establish that the subject documentation enabled the result, require the returned answer to identify or cite the subject and explain the relevant basis. Answer content alone establishes performance under the trial conditions, not the documentation's contribution.

## Run an independent trial

Run a documentation test from the repository root against the repository as it exists. Start a fresh subagent with no inherited conversation context. Give the subagent the task, but not the test companion or assertions. Tell the subagent not to read `*.test.md` or active project state and not to run `0 proj`.

Let the subagent use the rest of the repository normally. When access to another area could materially reveal the expected result or change the intended reader situation, state the exclusion in the task. Keep exclusions narrow and state the contamination they prevent.

Apply every condition in the task. Establish required fixtures and tools before the trial. Do not expose the companion while communicating the task.

Preserve the returned answer and citations, produced artifacts, and observable effects. Record the test name, task, subagent, harness, exposed model and reasoning configuration, and material limitations. State when the harness does not expose a relevant condition. Do not request or infer private reasoning.

A test contract does not authorize destructive, privileged, credentialed, or external action. Use a safe fixture or obtain the required authority.

## Judge the result

Before judging documentation-test assertions, confirm that the trial used a fresh context, kept the companion and assertions hidden, and followed every task condition. A trial that violates a required condition, or whose compliance cannot be established, is unusable and must be rerun.

Compare all preserved evidence with each assertion. Mark every assertion `satisfied`, `failed`, or `inconclusive`, and cite the observation. The trial passes when every assertion is satisfied, fails when any assertion fails, and is otherwise inconclusive.

The supported claim cannot exceed the assertions. A correct answer found through an unrelated source does not establish that the documentation supplied it. One successful trial establishes one result under its recorded conditions, not every reader or situation.

A failure can belong to the documentation, test contract, trial conditions, tool, or governed system. Repair the source of the failure. Do not add hints merely to force a passing result.

Test observes reader understanding and action attributable to documentation; it never asserts a result of actual system execution. The [lint](lint.md) document checks mechanical source properties, and [review](review.md) judges meaning, expression, and design. Use [environment tests](../../env/quality/test.md) when an agent encounter with the complete environment must establish understanding or action and may also establish a system result.
