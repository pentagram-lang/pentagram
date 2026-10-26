# Test

Within [quality](README.md), this document establishes Pentagram's testing standard for showing, with the highest practical certainty, that the codebase has no defects. It covers how tests are designed, combined across lifecycle stages, managed as a performance workload, and kept free of flakes.

Just as no single benchmark can prove the real-world resource consumption of a program, no single test—and for any sufficiently complex software, no finite suite of tests—can provide a complete proof of correctness. Every verification method has blind spots, maintenance weight, and execution costs. Even formal verification checks an abstracted model or specification that can drift from the machine instructions that actually run. For that reason, this guide refers to every verification mechanism—from unit assertions to automated theorem checks—as a **test**. While the word "proof" emphasizes an idealized guarantee, "test" foregrounds the active process, the concrete costs, and the real fallibilities that contributors must manage.

Before reaching for runtime tests, consider whether a claim belongs in the type system. Depending on the invariant, [type](type.md) design can make invalid states unrepresentable at compile time, providing a universal guarantee across all possible inputs that no sample of runtime tests can match. For everything that types and [lint](lint.md) cannot settle alone, high confidence comes from combining distinct testing techniques whose strengths overlap to cover each other's weaknesses, and placing each test into the lifecycle stage where its value justifies its cost.

Tests exist to make the implementation's correctness clear: a contributor reading a test—and seeing how different tests fit together—should be able to clearly understand what the implementation does and why it is correct. For tests to serve that purpose, the tests themselves must also be clearly correct, doing their job accurately while remaining easy to read, reason about, and maintain.

## Contents

- [Test design and judgement](#test-design-and-judgement)
  - [Objective test properties](#objective-test-properties)
  - [Test code and assertions](#test-code-and-assertions)
  - [Engineering judgement](#engineering-judgement)
- [Unacceptable test practices](#unacceptable-test-practices)
- [Test performance and codebase scaling](#test-performance-and-codebase-scaling)
- [Flake detection, enforcement, and infrastructure isolation](#flake-detection-enforcement-and-infrastructure-isolation)
  - [Test result database](#test-result-database)
  - [Post-merge detection and pre-merge enforcement](#post-merge-detection-and-pre-merge-enforcement)
  - [Flake handling in the dev loop and pre-merge](#flake-handling-in-the-dev-loop-and-pre-merge)
  - [Flake resolution](#flake-resolution)
  - [Infrastructure failure escape hatches](#infrastructure-failure-escape-hatches)
- [Testing lifecycle and combinable axes](#testing-lifecycle-and-combinable-axes)
- [Isolation scope techniques](#isolation-scope-techniques)
  - [Unit testing](#unit-testing)
  - [Integration testing](#integration-testing)
  - [System testing](#system-testing)
- [Input and expectation techniques](#input-and-expectation-techniques)
  - [Input partitioning](#input-partitioning)
  - [Snapshot testing](#snapshot-testing)
  - [Property-based testing](#property-based-testing)
  - [Exhaustive small-scope testing](#exhaustive-small-scope-testing)
  - [Metamorphic testing](#metamorphic-testing)
  - [Model-based stateful testing](#model-based-stateful-testing)
  - [Differential testing](#differential-testing)
  - [Fuzz testing](#fuzz-testing)
- [Substrate, in-band, formal, and meta techniques](#substrate-in-band-formal-and-meta-techniques)
  - [Deterministic simulation testing](#deterministic-simulation-testing)
  - [Internal invariant assertions](#internal-invariant-assertions)
  - [Dynamic sanitizer testing](#dynamic-sanitizer-testing)
  - [Formal verification testing](#formal-verification-testing)
  - [Mutation testing](#mutation-testing)
- [Manual testing](#manual-testing)

## Test design and judgement

Writing tests is a code design task just as consequential as designing the implementation itself. Sound test design requires objective execution properties, clear test code and assertions, and disciplined engineering judgement about what belongs in the suite.

### Objective test properties

Every test must satisfy four objective properties:

- **Falsifiable:** A test must reliably fail when the contract or invariant it guards is broken. Tests that check tautologies, mirror implementation internals without asserting external meaning, or pass when the underlying feature fails provide false confidence while consuming maintenance and compute budgets.

- **Hermetic:** A test must completely own its execution environment and state. It must not depend on ambient environment variables, shared filesystem paths, external network services, global mutable state, or the execution order of other tests.

- **Deterministic:** Given the exact same source revision and a healthy execution environment (with unhealthy environments isolated through [infrastructure failure escape hatches](#infrastructure-failure-escape-hatches)), a test must produce the identical outcome on every run. It must not depend on unseeded randomness, wall-clock timing races, or uncontrolled thread scheduling. Tests that intentionally use pseudorandom generation—such as property-based, model-based, or simulation tests—must derive their default seed from the source revision so that re-runs on the same revision remain strictly deterministic while new revisions automatically explore new cases.

- **Reproducible:** When a test fails—including during seeded property generation, fuzzing, or simulation—it must report the exact seed, input artifact, or schedule trace needed to replay that identical failure immediately in the local `dev loop` (even after the working copy or source revision changes).

### Test code and assertions

How a test is written determines how effectively it catches and explains defects:

- **Assert whole, exact composite values in straight-line code:** Rather than asserting isolated fields or loose predicates (such as checking only that a status succeeded or that an ID is non-zero), assert equality against the complete expected composite value. Use language features that provide structural equality on composed data structures (such as derived equality traits or value-equality records) so nested structures can be compared in a single assertion, and make generated values such as unique IDs, counters, and timestamps deterministic in tests so they can be included verbatim in the expected value. When constructing large composite expectations, it can help to write the test initially with dummy expected data, run a characterization pass to observe the exact full output, and—after verifying that the output is genuinely correct—use it as the expected value or snapshot. Because a deterministic test has only one valid expectation, assertion code must be straight-line—free of nested conditionals, branching, or error recovery—so that any deviation across any field immediately fails the test.

- **Provide self-contained failure feedback:** When a test fails, its initial failure output should make the defect clear—or provide enough information to construct a minimal reproduction directly from that output—without requiring a contributor to add temporary instrumentation or re-run under a debugger just to see what went wrong. Whole-value equality diffs and clear input reporting support this directly.

- **Factor test code as functional transformations:** Test code is first-class repository code and must follow [functional programming](../style/fn.md). Factor repetitive setup, execution, and comparison mechanics into clean, composable functions over explicit test data so that each individual test expresses only the essential inputs, transformation, and expected output that make that test meaningful. Make sure that factoring cooperates with the test infrastructure rather than degrading failure attribution: when extracting assertion helpers or structuring case-based tests, use the language's caller-tracking or parameterized-test mechanisms (or return values to assert at the top level) so that independent failures are reported clearly and point directly to the specific failing test case rather than an internal helper line.

- **Let test code and data stand without narrative comments:** Tests must not rely on inline comments for subjective narration of setup steps or assertions. The machine executes only the code and data, not the comments; when tests are properly factored with clear names and explicit data, their meaning is immediately legible without commentary.

### Engineering judgement

Satisfying these design rules makes an individual test sound and usable, but does not by itself make the test worth keeping in the repository. Every test carries a concrete authoring, maintenance, and runtime execution cost, and that runtime cost is multiplied by how often the test runs. Contributors must exercise strict engineering judgement across three decisions:

1. **What to test:** Target the actual fault lines of the system—core invariants, boundary conditions, state transitions, and regressions codified from discovered defects. Apply [subtractive design](../../rm/README.md) to avoid testing claims whose invariants are already enforced by [type](type.md) design or broader checks.

2. **How to test:** Select the testing technique and isolation boundary that establish the claim with the least complexity and lowest runtime overhead.

3. **When the test runs:** Assign the test to the lifecycle stage whose execution frequency matches the test's cost and signal—including whether the test needs to run more than once at all:

   - **Run-once tests (`.tmp/`):** When a test is needed to establish a one-time claim—such as verifying a migration, proving an algorithmic equivalence during a refactor, or confirming a broad removal—but does not need to be re-run on future changes, write it as an uncommitted run-once test in `.tmp/`. Run-once tests provide immediate verification evidence with zero ongoing maintenance or CI execution cost.

   - **Committed tests (permanent-for-now):** Committing a test into the repository means accepting its recurring execution and maintenance cost across future changes. Treat committed tests as **permanent-for-now**, not sacred: as the codebase evolves, invariants shift into the type system, or better tests supersede older ones, it is always valid to re-evaluate committed tests and change or remove them.

The total value and total cost of the repository's test suite are the sum of these individual judgements. Poor judgement compounds rapidly: it produces an expensive test suite that checks very little of value while running so slowly and breaking so brittlely that contributors cannot make changes with meaningful velocity.

## Unacceptable test practices

The following practices are forbidden in committed tests because they corrupt production design, hide concurrency or timing defects, or degrade suite performance:

- **Source-code text audits:** Committed tests must not scan implementation source files for tokens, strings, or regular-expression patterns as a substitute for testing behaviour (though uncommitted run-once scripts in `.tmp/`, as described in [verify removals in subtractive design](../../rm/README.md#verify-removals), remain useful for verifying broad removals during refactoring).

- **Testing dead code used only by tests:** Implementation code that has no production callers must not be kept alive solely because a test exercises it. Apply [subtractive design](../../rm/README.md) and delete both the dead implementation code and its tests.

- **Weakening strong types for testing:** Never loosen type invariants, widen field visibility, make required fields optional, or replace [type](type.md)-safe representations with raw primitives just to make test construction easier.

- **Compromising API design for tests:** Do not distort module boundaries, export private internals, or pollute production function signatures with test-only parameters to accommodate a test. If a boundary is genuinely awkward to test, repair the data and function design using [functional programming](../style/fn.md) and [partitioning](../style/part.md) so the real interface is clean for all callers.

- **Forced test serialization:** Never serialize test execution (such as with serial-execution attributes, global mutexes, or single-threaded runner flags) to work around shared state or threading bugs. Fix the underlying isolation or concurrency defect so tests run safely in parallel.

- **Global mutable test observation state:** Do not record or inspect test observations through global mutable state or non-thread-safe statics. Pass explicit, locally owned state or thread-safe isolated handles into the unit under test.

- **Debug prints:** Do not leave debug print statements or noisy standard-output dumps in committed tests; keep test output clean so failure diagnostics stand out immediately.

- **Real operating-system sleeps:** Never use wall-clock OS sleeps to wait for asynchronous work or background threads. Sleeps waste time on every run and cause timing flakes under load; use explicit synchronization primitives, deterministic channels, or simulated clocks instead.

- **In-test retries:** Never wrap test assertions or operations in retry loops to mask intermittent failures.

- **Ignored tests:** Do not commit disabled or ignored tests, which rot silently without providing verification. When codifying a known, unfixed defect is genuinely valuable to test, use an explicit expected-failure (`xfail`) test that continues to compile and execute on every run and fails the suite the moment the outcome unexpectedly changes.

## Test performance and codebase scaling

Because the test suite executes continuously across every contributor iteration and CI pipeline, managing test cost is a performance problem. Every principle in [performance](../performance/README.md)—the evolutionary spiral of design, observe, and tune, along with the disciplines of eliminating, reducing, bounding, localizing, moving, specializing, scheduling, overlapping, and parallelizing work—applies directly to the test suite itself.

In fact, test performance operates at a severe structural disadvantage compared to the performance of the main software:

- **Main software executes finite task paths.** Regular execution traverses only the specific code paths required for a single task and input. Even in a large codebase, this can be designed to run a small fraction of the system and complete quickly.

- **Tests must traverse the entire codebase.** To maintain coverage, the test suite must exercise every subsystem, every feature, every invariant, and every error path across the whole repository. There is no way to skip coverage across the codebase without leaving defects unguarded.

As a software project grows toward its peak codebase size—which software design and [subtractive design](../../rm/README.md) must keep bounded rather than growing without limit, even as active development continues—the total work required of the test suite scales with the entire codebase. Consequently, test costs must be acceptable both while the project is ramping up and once it reaches peak size. Scaling up with zero or negative headroom on test performance is fatal: a suite that barely meets latency budgets when the codebase is small will grind development to a halt long before the project reaches maturity.

To defend that headroom, test performance must be productionized immediately rather than deferred:

- **In the `dev loop`:** Because running tests forms the core of the `dev loop`, local runs of targeted subject-matter tests must not break contributor flow, targeting completion within **100 ms**. Individual local test invocations must measure and surface execution durations so contributors immediately see when a test they write or modify is slow.

- **In CI (`pre-merge` and `post-merge`):** Automated pipelines must record per-test start and end timestamps alongside per-run system resource-utilization time series (CPU core saturation, memory footprint, and I/O throughput over time).

Tracking start and end timestamps identifies slow tests and reveals the exact set of tests active at any instant during a run. Correlating those active test intervals against the run's resource-utilization timeline is critical for right-sizing and allocating CI hardware, diagnosing scheduling stragglers, and fixing parallelism bugs where concurrent tests contend for machine resources.

## Flake detection, enforcement, and infrastructure isolation

Even with strict standards for hermetic and deterministic design, flawed tests will occasionally pass `pre-merge` checks and merge to `main`. Allowing flaky tests to linger on `main` destroys determinism: contributors habituate to re-running failed builds, real regressions are dismissed as noise, and engineering velocity collapses.

At the same time, flake enforcement must not confound true test non-determinism with changing source code on development branches or with underlying infrastructure outages. Development branches undergo constant history rewrites (rebases, squashes, splits, and amends), branch forks and joins, and legitimate work-in-progress failures, whereas `main` has a linear, immutable history. The system therefore records all `pre-merge` and `post-merge` runs for heuristic analysis, while using only `post-merge` runs on `main` to establish proven flakes.

### Test result database

All `pre-merge` and `post-merge` test runs record their observations in a bounded, append-only database keyed by source revision and the fully-qualified name of each test, alongside each test's start and end timestamps and the run's resource-utilization time series. Two signals are derived from this history:

- **Definitive flaky test set (`post-merge` only):** From the append-only history of non-`inconclusive` `post-merge` runs on `main` (see [infrastructure failure escape hatches](#infrastructure-failure-escape-hatches)), any test still present in the repository whose recorded outcomes both pass and fail on the same `main` source revision belongs to the computed flaky test set. Bounded truncation of older database records is suspended whenever this set is non-empty, ensuring that flake evidence cannot age out before the flake is resolved.

- **Per-test error rates (`pre-merge` and `post-merge`):** Across all `pre-merge` and `post-merge` runs, the database computes per-test failure rates to provide a broader heuristic picture of test health. A high error rate surfaces unproven flakiness (such as seed-dependent or environment-sensitive failures that did not flip on a single `main` revision) as well as high susceptibility to churn (brittle tests that repeatedly break during normal branch development and warrant redesign or removal).

### Post-merge detection and pre-merge enforcement

Automated flake detection and enforcement anchor on `main` and gate future merges:

- **Automatic retry-to-detect and re-runs in `post-merge`:** In addition to heavier `post-merge`-only checks, `post-merge` always runs all `pre-merge` tests on `main` for linear-history and flake verification. `post-merge` runs use the source revision as the default pseudorandom seed, ensuring that tests with intentional randomness execute the exact same cases on every run of that revision while still varying across new commits. When a test fails during a `post-merge` run, the runner retries that test automatically on the exact same source revision and seed. This retry is never used to turn a red build green; its sole purpose is to detect whether the test outcome flips. In addition, `post-merge` tests on `main` can be re-run manually or on a schedule, appending further observations for that revision to the database.

- **Timeout flakes:** Per-test time limits exist both to catch wedges and to enforce test performance goals. Every test must maintain substantial headroom below its time limit so that normal execution variance never triggers a timeout. If a test flips between passing and exceeding its per-test time limit on the same `main` revision, that is a legitimate test flake.

- **Hard `pre-merge` stop:** While the definitive flaky test set is non-empty, no `pre-merge` check will pass if any test in that set exists in the branch under test (or, if blocking all unrelated changes proves too onerous at scale, rules may scope the `pre-merge` block to changes related to the fully-qualified names of the flaky tests). Unblocking `pre-merge` requires [flake resolution](#flake-resolution).

### Flake handling in the dev loop and pre-merge

While working on a branch, contributors run targeted subject-matter tests manually in the `dev loop` and run the full suite automatically in `pre-merge`. Neither stage retries failing tests automatically—both because unmerged branches undergo constant history rewrites, forks, and joins, and because automatic retries on a branch would mask newly introduced flakes right when they should be caught.

When a test fails in the `dev loop` or `pre-merge` and then passes on a manual re-run without a relevant code change, never brush the failure off just because the re-run turned green:

- **If the branch introduced the flake:** Apply [flake resolution](#flake-resolution) directly on the branch before merging.

- **If the flake appears unrelated to the branch (or its origin is unclear):** Validate and escalate it outside the branch by re-running that specific test repeatedly in `post-merge` on `main`. If the test flips on `main`, it enters the definitive flaky test set automatically—making the flake visible to all contributors and blocking `pre-merge` so contributors can coordinate on [flake resolution](#flake-resolution) rather than silently absorbing random failures across separate branches. If the test holds steady on `main`, treat the non-determinism as introduced or exposed by the branch and resolve it before merging.

### Flake resolution

Whether a flake is caught in the `dev loop`, spotted during `pre-merge`, or proven in `post-merge` on `main`, resolving it involves four independent considerations:

- **Evaluate whether the test is worth keeping:** A flaky test may not be worth maintaining at all, or may not be worth keeping in its current form. Apply [engineering judgement](#engineering-judgement) and [subtractive design](../../rm/README.md): if the test's value does not justify its cost, or if a simpler, higher-signal check can replace it, delete or simplify the test.

- **Investigate suspected implementation non-determinism:** Independently of whether the test is kept, simplified, or deleted, sufficient suspicion of implementation non-determinism—such as a concurrency race, unseeded randomness, or ordering bug in production code—triggers a root-cause investigation and fix within the practical limits of the subject matter and available resources (as established in [acceptance criteria in the contribution guide](../../CONTRIBUTING.md#acceptance-criteria)).

- **Fix poorly written test code:** A flake can also stem from poorly written test code, such as violated hermeticity, timing assumptions, or shared mutable state. When the test is kept, fix the defect in the test. Even when the individual test is deleted or simplified, investigate and fix the defect if suspicion points to shared test helpers, fixtures, or harness code that other tests rely on.

- **Rename any kept test after a flake fix:** Because the test result database is append-only and has no mechanism to mark a test name as "un-flaked," any previously recorded flaky test that is kept—**even when the fix is purely in the implementation code or shared test helpers and the test body itself is unchanged**—must be **renamed** so it enters the suite under a clean identity.

### Infrastructure failure escape hatches

Most infrastructure failures—such as a runner losing network connectivity during setup or crashing entirely—render an entire test run obviously incomplete. However, localized or transient infrastructure failures can break specific tests during a run and recover for a retry, making healthy tests appear to flake on that source revision.

To prevent infrastructure faults from poisoning the computed flaky set without ever allowing a broken run to pass as green, the system provides two run-level escape hatches that classify an entire test run as `inconclusive` (matching the outcome model for [weighing adequate evidence in criteria](criteria.md#weigh-adequate-evidence)):

- **Audited post-hoc run override:** An operator or contributor can append an audited override record that reclassifies a completed test run as `inconclusive` when investigation confirms an underlying infrastructure failure. Because the flaky tests set is computed only over non-`inconclusive` runs, excluding the overridden run removes a test from the computed flaky set unless other valid runs independently establish that the test flaked.

- **Programmatic run cancellation:** When a test interacts with a legitimate external or host test dependency—such as a test object store service, kernel subsystem, or hardware device—and detects that the dependency itself is unavailable or unhealthy, the test can programmatically cancel the entire test run and record the run as `inconclusive`. This prevents an infrastructure outage from being recorded as an owned test failure or flake while refusing to silently skip the test.

## Testing lifecycle and combinable axes

Just as [modes of measurement in performance](../performance/README.md#modes-of-measurement) span four canonical lifecycle stages, tests are distributed across the same four stages according to their execution cost and feedback role:

- **`dev loop`:** Local runs of targeted subject-matter tests while editing code. Unlike heavy performance profiling where contributors expect to spend extra time, tests form the core of the `dev loop` and must not break cognitive flow, targeting completion within **100 ms**.

- **`pre-merge`:** Fast, noise-free, deterministic verification gates that block regressions and banned flaky tests before changes land on `main`.

- **`post-merge`:** Asynchronous verification pipelines on `main` that always run all `pre-merge` tests (for linear-history verification and flake detection) alongside compute-intensive exploration, deep simulations, and sanitizers.

- **`field`:** Production diagnostics, in-band invariant assertions on opted-in or canary builds, and failure reproduction harnesses fed by real-world workloads.

Within these stages, testing techniques are not mutually exclusive silos. They sit on three orthogonal axes that contributors can combine:

1. **Isolation scope:** How much of the system runs together (`unit`, `integration`, `system`).

2. **Input and expectation design:** How test cases are chosen and how expected outputs are verified (`input partitioning`, `snapshot`, `property-based`, `exhaustive small-scope`, `metamorphic`, `model-based`, `differential`, `fuzz`).

3. **Execution substrate, in-band checks, formal, and meta verification:** How the underlying runtime or machine model is controlled, instrumented, or analyzed (`deterministic simulation`, `internal invariant assertions`, `dynamic sanitizer`, `formal verification`, `mutation`).

For example, a contributor might combine an `integration` scope with `property-based` input generation and `internal invariant assertions`, or combine a `system` scope with `snapshot` expectations. Each technique below defines its target, strengths, weaknesses, and ideal lifecycle stages.

## Isolation scope techniques

### Unit testing

- **Target:** It verifies an individual function or internal unit in isolation. When code follows [functional programming](../style/fn.md), pure data transformations are already isolated from effects; any remaining external dependencies are replaced with mocks or test doubles so that only the unit under test can cause a failure.

- **Strengths:** Unit tests execute at in-memory speed, require minimal setup, and provide immediate, unambiguous attribution when an assertion fails. They make boundary cases and local data transformations straightforward to exercise.

- **Weaknesses:** Because collaborators are mocked or absent, unit tests cannot verify that separate units or modules agree on their shared contracts, and tests coupled too tightly to private helper structure can create maintenance friction during refactoring.

- **Ideal stages:** Unit tests are the foundation of the `dev loop` and `pre-merge` gates.

### Integration testing

- **Target:** It exercises a single module strictly through its external public API, or composes two or more modules together to verify their combined behaviour, while continuing to mock external system boundaries.

- **Strengths:** Integration tests catch interface mismatches, broken assumptions across boundaries, and composition bugs that isolated unit tests miss. Because they interact with modules as an external caller does, writing an integration test serves as an immediate local test of public API design, revealing whether interfaces compose ergonomically or force awkward plumbing on callers.

- **Weaknesses:** They carry higher setup and runtime cost than unit tests, and a failure requires narrowing down which step in the composed chain broke the contract.

- **Ideal stages:** Integration tests belong in the `dev loop` and `pre-merge` gates.

### System testing

- **Target:** It drives the complete system from full external inputs to full external outputs with no code-level mocks (using only system-level mocks when necessary).

- **Strengths:** System tests verify exact external expectations end-to-end. Because they couple exclusively to the public external surface, they survive all forms of internal refactoring without requiring test rewrites.

- **Weaknesses:** Full-pipeline execution is significantly more expensive in CPU, memory, and I/O than in-memory tests, and failures provide coarse attribution that must be traced back through the pipeline.

- **Ideal stages:** Focused system tests run in the `dev loop` and `pre-merge`, large or resource-heavy end-to-end corpora run in `post-merge`, and—because only external interfaces are used—system tests also fit `field` verification against deployed builds.

## Input and expectation techniques

### Input partitioning

- **Target:** It divides an input domain into equivalence classes where behaviour should be uniform, testing representative interior values, exact boundary values between classes (`0`, `1`, `-1`, empty, single-element, capacity limits), and covering combinations of parameters (chosen directly, generated as combinatorial covering arrays, or used to stratify generators).

- **Strengths:** Partitioning maximizes defect detection per test case with minimal runtime cost, directly targeting the off-by-one, boundary, and parameter-interaction errors where logic most frequently fails.

- **Weaknesses:** It relies on the partition model matching the implementation's actual control flow; if an unexpected branch or hidden state interaction splits an assumed equivalence class so that behaviour inside the class is not uniform, testing only representative values from each partition can miss it.

- **Ideal stages:** This technique belongs in the `dev loop` and `pre-merge` gates as the primary discipline for structuring test cases.

### Snapshot testing

- **Target:** It compares complete, complex structured outputs—such as abstract syntax trees, intermediate representations, formatted source code, or compiler diagnostics—against recorded reference snapshots.

- **Strengths:** Snapshot tests capture rich structural output in full detail without requiring hundreds of brittle, hand-written field assertions, making unexpected changes across complex outputs immediately visible in diffs.

- **Weaknesses:** Snapshots can be large and reading their diffs can be difficult—a problem multiplied when many snapshots change at the same time.

- **Ideal stages:** Snapshot tests are well suited for the `dev loop` and `pre-merge` gates.

### Property-based testing

- **Target:** It asserts universal invariants—such as round-trip invertibility, idempotence, algebraic laws, or structural preservation—across structured inputs generated randomly from a seeded distribution.

- **Strengths:** Property-based tests explore input combinations that contributors rarely think to write by hand, uncovering edge cases across wide input spaces while keeping test code concise.

- **Weaknesses:** Writing effective generators that produce valid, well-distributed domain inputs requires nontrivial design effort, and randomized exploration can consume substantial compute time with diminishing value as iteration counts grow.

- **Ideal stages:** Bounded, fast seed runs fit the `dev loop` and `pre-merge`, while high-iteration exploration runs belong in `post-merge`.

### Exhaustive small-scope testing

- **Target:** It deterministically enumerates and tests every possible valid input up to a small structural size bound—such as all expression trees up to depth three, all small control-flow graphs, or all bit-width boundary combinations.

- **Strengths:** Because most defects that do not depend on scale already manifest on small inputs, exhaustive small-scope testing provides complete certainty within that bound, requires no randomness, and never flakes.

- **Weaknesses:** Combinatorial explosion limits enumeration to very small bounds, leaving scale-dependent bugs and deep structural interactions unexamined.

- **Ideal stages:** Small, fast bounds run in the `dev loop` and `pre-merge`, while larger enumeration bounds run in `post-merge`.

### Metamorphic testing

- **Target:** It verifies systems where computing the exact expected output for an arbitrary complex input is impractical, by applying a known domain transformation to an input (such as renaming local variables, permuting independent declarations, or inserting dead code) and asserting the known mathematical relationship between the original and transformed outputs.

- **Strengths:** Metamorphic testing enables automated verification of complex pipelines like compiler optimizations and type inference across vast corpora of programs without needing precalculated expected outputs for each input.

- **Weaknesses:** It checks only the relative consistency required by the chosen transformation relation; a defect that affects both the original and transformed inputs identically will go undetected.

- **Ideal stages:** Lightweight metamorphic checks fit `pre-merge`, while large-scale metamorphic campaigns across generated corpora belong in `post-merge`.

### Model-based stateful testing

- **Target:** It generates coherent sequences of operations against a stateful system and compares the real implementation's state transitions and return values after every step against a simplified, trusted reference state machine.

- **Strengths:** Stateful sequences uncover deep bugs caused by temporal ordering, resource lifecycle transitions, cache invalidation, and interleaved mutation that single-call input-output tests cannot reach.

- **Weaknesses:** Authors must build and maintain a second, simplified model of the stateful contract, and long action sequences can be expensive to execute and debug.

- **Ideal stages:** Short, deterministic action sequences fit the `dev loop` and `pre-merge`, while deep randomized sequence exploration belongs in `post-merge`.

### Differential testing

- **Target:** It feeds identical inputs into two or more implementations of the same contract—such as a bootstrap compiler and a self-hosted compiler, an unoptimized reference implementation and an optimized fast path, or a previous version and a candidate change—and asserts that their observable outputs agree.

- **Strengths:** Differential testing uses one implementation to check another across arbitrarily complex inputs without manual expectation writing, catching subtle semantic divergences immediately.

- **Weaknesses:** Maintaining multiple implementations carries architectural cost, and implementations can occasionally share the same misunderstanding of the specification.

- **Ideal stages:** Targeted differential checks run in the `dev loop` and `pre-merge`, while massive differential campaigns over generated or real-world corpora run in `post-merge`.

### Fuzz testing

- **Target:** It feeds mutated or generated inputs into a target entry point—using instrumented coverage guidance to observe which branches and state transitions each input reaches, and retaining inputs that discover new execution paths for further mutation—to uncover panics, crashes, memory safety violations, infinite loops, and pathological resource spikes. Raw byte fuzzing targets boundary decoders, lexers, and parsers, while domain-guided (structure-aware or grammar-guided) fuzzing mutates valid syntax trees or typed programs to penetrate deep compiler and runtime phases.

- **Strengths:** Coverage-guided mutation and domain-aware generators steer exploration directly toward unvisited branches rather than sampling blindly, relentlessly discovering dark corners of the state space that contributors overlook and producing concrete, reproducible counterexample inputs whenever a crash or assertion failure is found.

- **Weaknesses:** Fuzzing is an open-ended search that consumes substantial CPU time to reach deep paths, and without strong internal assertions or differential comparisons across implementations it primarily detects crashes and hangs rather than silent semantic miscomputations.

- **Ideal stages:** Continuous fuzzing campaigns belong in `post-merge` and on-demand in the `dev loop`.

## Substrate, in-band, formal, and meta techniques

### Deterministic simulation testing

- **Target:** It replaces the nondeterministic operating environment beneath the code—clocks, timers, asynchronous I/O completions, network packet delivery, disk faults, and thread or atomic interleavings—with a deterministic, seed-controlled simulator or stateless model checker.

- **Strengths:** Simulation and schedule exploration systematically expose invalid dependencies on system timing, message ordering, partial I/O failure, and thread interleaving that normal mocks never model and that otherwise manifest only as rare, irreproducible production flakes.

- **Weaknesses:** Building and maintaining a faithful simulated substrate or instrumenting atomic schedules requires disciplined architectural boundaries, and exhaustive schedule exploration grows exponentially with concurrent operations.

- **Ideal stages:** Fixed-seed regressions and small schedule explorations run in the `dev loop` and `pre-merge`, while broad multi-seed simulation and fault-injection sweeps run in `post-merge`.

### Internal invariant assertions

- **Target:** It embeds executable precondition, postcondition, and data-structure invariant checks directly inside implementation code so that any violation immediately aborts execution with a diagnostic failure.

- **Strengths:** Internal assertions act as a universal force multiplier across every other technique: when enabled, every unit test, system test, fuzz campaign, simulation, and canary run automatically verifies internal state consistency at intermediate steps rather than checking only final outputs.

- **Weaknesses:** Expensive invariant checks (such as validating full tree balance or graph acyclicity on every mutation) can degrade runtime performance and alter asymptotic complexity if left enabled unconditionally on hot production paths.

- **Ideal stages:** Cheap invariants run across all stages (`dev loop`, `pre-merge`, `post-merge`, and `field`), while expensive structural invariants are enabled in `dev loop`, `pre-merge`, and `post-merge` test builds.

### Dynamic sanitizer testing

- **Target:** It executes existing test suites under compiler-instrumented runtimes or abstract machine interpreters (such as AddressSanitizer, ThreadSanitizer, UndefinedBehaviorSanitizer, and Miri) to check memory safety, pointer provenance, aliasing rules, uninitialized reads, arithmetic overflow, and data races at the instruction level.

- **Strengths:** Sanitizers and machine-model interpreters detect undefined behaviour and subtle memory or concurrency bugs the exact moment they occur, even when the corrupted operation happens to produce the expected high-level test output on a given machine.

- **Weaknesses:** Instrumented execution and abstract machine interpretation introduce severe memory overhead and runtime slowdowns ranging from two-fold to well over a hundred-fold.

- **Ideal stages:** Sanitizer and machine-model runs belong in `post-merge` pipelines and targeted `dev loop` checks when authoring low-level or `unsafe` code.

### Formal verification testing

- **Target:** It uses SMT solvers, symbolic execution engines, bounded model checkers, or theorem provers to mechanically test whether core algorithms, type-system rules, or memory invariants hold across all symbolic paths or mathematical states within a specification.

- **Strengths:** Formal verification tests examine every path within their verification boundary simultaneously, uncovering subtle corner cases in critical algorithms, reference-counting protocols, or compiler invariants that random sampling can miss.

- **Weaknesses:** Solver runtimes can explode unpredictably on complex arithmetic or unbounded loops, and whenever a formal model is written separately from the implementation rather than mechanically extracted from source code, translation drift can allow the formal test to pass while the actual code contains a bug.

- **Ideal stages:** Fast bounded symbolic checks can run in `pre-merge`, while heavy solver and model-checking tests belong in `post-merge` and specialized `dev loop` verification.

### Mutation testing

- **Target:** It tests the quality of the test suite itself by systematically injecting small syntactic faults (mutants)—such as flipping relational operators, removing statements, or altering return values—into the implementation source code and verifying that at least one test fails for each mutant.

- **Strengths:** Mutation testing directly measures test falsifiability rather than mere line execution coverage, exposing dead code and weak tests that execute code paths without actually asserting their results.

- **Weaknesses:** Compiling and running the test suite across hundreds or thousands of generated code mutants is extremely compute-intensive, and equivalent mutants (syntactic changes that do not alter program semantics) require manual inspection to interpret.

- **Ideal stages:** Mutation testing belongs exclusively in `post-merge` analysis pipelines and targeted on-demand audits in the `dev loop`.

## Manual testing

When automated tests are unsuitable—such as for physical hardware or host boundaries, visual rendering judgement, or operational workflows that cannot be hermetically automated at reasonable cost—use manual tests specified in a `.test.md` companion file.

Manual code tests share the companion placement and contract format defined in [documentation test](../../doc/quality/test.md):

- **Companion placement:** Store the companion beside its code subject by appending `.test.md` to the complete filename (for example, `runner.rs.test.md` beside `runner.rs`), as specified in [store tests beside their subject in documentation test](../../doc/quality/test.md#store-tests-beside-their-subject). Manual code tests, documentation tests, and [environment tests](../../env/quality/test.md) can coexist as sibling `##` sections in the same companion file.

- **Contract form:** Follow the exact `# Tests` heading, `## <Test name>` sections, `**Task**` instructions, and `**Assert**` list defined in [write the test contract in documentation test](../../doc/quality/test.md#write-the-test-contract). State the concrete execution setup, inputs, and steps in `Task`, and state falsifiable, observable system outcomes in `Assert`.

- **Coverage and run planning:** Manual and subagent-driven companion trials consume substantial time, compute, and attention. Add a manual test only when automated tests cannot practically establish the claim, and plan runs selectively when changes to the subject or its operational risk require fresh evidence.

- **Independent execution and judgement:** Run the manual test in a fresh subagent context (or via a human when physical or host interaction requires it) against the current repository state. When using a subagent, give it the `Task` while hiding the `.test.md` companion and `Assert` list, and instruct it not to read `*.test.md` or active project state (`0 proj`). Preserve the command outputs, artifacts, and observed system effects, then judge each assertion as `satisfied`, `failed`, or `inconclusive` from the recorded evidence. A test contract never authorizes destructive, privileged, credentialed, or external side effects without explicit authority or a safe fixture.
