# Coding Standards

This document defines repository-wide coding and testing standards for implementation work. It complements the [documentation standards](../doc/README.md): documentation establishes the meaning and contract, while these standards shape the implementation and its evidence. It does not define Pentagram language semantics or the architecture of a particular subsystem.

Code also shapes the repository environment through readable source and through executable affordances, constraints, feedback, and state. [Environment engineering](../env/README.md) governs those effects in combination with documentation. Every code change must account for its environmental effects; environment-specific evidence, testing, and review scale with environmental risk and leverage.

## Implementation

The Rust boot implementation is functional, data-oriented, readable, and predictable.

- Treat structs and enums as passive data. Put complex logic in standalone functions.
- Reserve one-line methods for fundamental data construction, equality, queries, and views.
- Keep every method and trait implementation to one statement in its body.
- Derive `Default`, `PartialEq`, and `Eq`; do not hand-write those implementations.
- Derive `Default` only when an empty or neutral state is semantically valid.
- Keep `lib.rs`, `mod.rs`, and `main.rs` as manifests containing module declarations and public re-exports only.
- Use singular, fully named module and file names.
- Give functions names that state their specific operation. Avoid vague names such as `process` or `handle` when the context does not make them precise.

Write files from high-level public APIs toward lower-level detail. Keep imports in one block at the top, use specific imports, never use wildcard imports, and use absolute crate-local imports. Test modules may use `use super::*;` as their local scope exception.

Comments are a last resort. Do not add change history, removed-code explanations, region banners, or flow narration. Keep precise public documentation and objective technical constraints when the signature and structure do not already communicate them.

## Tests

Every implementation file containing logic has a same-directory shadow test file, unless the file only defines passive data structures and derived traits. The implementation file ends with:

```rust
#[cfg(test)]
mod module_test;
```

Shadow tests are a narrative of behaviour, not placeholders. Tests contain no comments; use descriptive names and local helpers instead.

Implementation tests assert only results of actual execution. They do not assert participant understanding or action. Use [documentation tests](../doc/quality/test.md) for reader understanding or action attributable to documentation. Use [environment tests](../env/quality/test.md) when an agent encounter with the complete environment must establish understanding or action and may also establish a system result.

Test functions and helpers do not return `Result`. Extract successful results with `expect` or `unwrap`, extract expected failures with `expect_err`, and assert the error's complete content. Do not use `is_ok`, `is_err`, or manual matches merely to probe a result.

Use high-fidelity assertions on complete outcomes. Prefer `pretty_assertions` for equality checks. Do not assert only a length or one field when the complete result can be compared.

Tests provide evidence for documented contracts, invariants, failure behaviour, and boundaries. They do not replace the documentation-level design review described in the [documentation standards](../doc/README.md).
