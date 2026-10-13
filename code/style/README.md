# Style

Within [coding standards](../README.md), style describes useful patterns that make code easier to read, understand, reason about, and change. Style is not decoration applied after the design. It is the design's visible movement.

Code style governs how machine-oriented instructions read as text; [documentation system](../../doc/README.md) standards governs the meaning, structure, style, and quality of documentation that exists in or alongside code.

[Performance](../performance/README.md) and [quality](../quality/README.md) have their own standards; style cannot make incorrect code correct or make a performance claim true.

## Expression style

Use [expression style](expr.md) for code at its smallest useful scale. It outlines rules that help make actual code execution clear while making the code text easy to work with.

## Functional programming

Use [functional programming](fn.md) to shape code as data transformations that can be composed into larger tasks. By avoiding shared mutable state as much as possible, code can be created, read, and changed with high confidence.

## Partitioning

Use [partitioning](part.md) to divide code into coherent units that maximize local ownership of data and functions. Good partitioning is what enables code to scale in both power and safety.
