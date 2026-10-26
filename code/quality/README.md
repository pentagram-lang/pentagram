# Quality

Within [coding standards](../README.md), code quality is a judgement about a complete system surface, not about isolated subroutines. The code must faithfully execute its intended behaviour across its stated inputs and conditions, and contributors and developers must be able to understand, reason about, and safely change it. This is what it means for code to be clearly correct.

Quality works with the other code pillars. [Performance](../performance/README.md) establishes extreme speed, structural discipline, work management, and mechanical sympathy with hardware. [Style](../style/README.md) governs how machine-oriented instructions read as text, expressing intent through patterns that make code easy to read, reason about, and change. Quality evaluates whether code satisfies both pillars across its complete execution surface, verifying that speed does not sacrifice intelligibility and that structural elegance does not disguise computational waste.

Quality is the mechanism that demonstrates clear correctness. Neither fast execution nor clean presentation alone guarantees correctness; a performant routine can return incorrect results, and an elegant module can conceal unhandled failure paths or latency cliffs. [Criteria](criteria.md) judges code across its complete execution surface, using tiered evidence to show with high certainty that code meets its functional, operational, and architectural contracts.

Quality must embody and support the aims defined in the [Pentagram manifesto](../../manifesto.md). Ergonomic quality provides immediate feedback in contributor loops and transparent diagnostics when invariants fail. Deterministic quality relies on hermetic, reproducible tests, explicit failure contracts, and noise-free verification gates that yield identical results across identical runs. Efficient quality stages verification into tiered evidence, catching regressions with inexpensive static checks and cost accounting before executing compute-intensive benchmarks and simulations.

## Criteria

[Criteria](criteria.md) explains what to judge across correctness, clarity, and the complete execution surface, and how to report pass, fail, or inconclusive evidence.

## Lint

[Lint](lint.md) defines mechanical checks for formatting, static rules, naming conventions, imports, and automated repository policies.

## Test

[Test](test.md) specifies how to design, run, and maintain tests, combining overlapping verification techniques across lifecycle stages for high confidence in correctness.

## Review

[Review](review/README.md) defines independent inspection, findings, evaluation, repair, and re-review for code.

## Type

[Type](type.md) explains how to use strong types to enforce invariants at compile time and make invalid states unrepresentable.

## Error handling

[Error handling](err.md) explains best practices for handling, reporting, containing, and recovering from errors encountered during code execution.
