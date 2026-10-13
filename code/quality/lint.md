# Lint

Within [quality](README.md), lint enforces mechanical formatting, static compiler rules, code hygiene, and repository invariants that can be decided reliably from files without execution. The checks remain separate so each result identifies what it observed. `0 check fmt` validates formatting across all languages. `0 check lint` runs static linters. `0 check repo-policy` enforces repository hygiene. The complete `0 check` cycle composes these checks with test suites and commit validation.

Passing lint establishes that code satisfies mechanical rules and baseline compiler invariants. It does not establish that code satisfies its runtime contracts, handles unexpected inputs, or is easy to reason about and safely change. [Criteria](criteria.md) governs the complete quality judgement; lint provides the initial, least expensive tier of evidence.

Because check commands read the working tree through automated Git interoperability, run `jj status` before executing checks so Jujutsu exports the current working copy.

## Command plane integration

The [command plane](../../zero/README.md) provides automated commands to format code, apply mechanical fixes, and validate rules:

- `0 fix` formats all source files and applies automated linter fixes across Rust and Python. Use `0 fix fmt` to run only formatters, or `0 fix lint` to run only linter fixes.
- `0 check fmt` validates formatting across Rust, Python, Nix, and Markdown without modifying files.
- `0 check lint` runs static analysis and compiler lints without modifying files.
- `0 check --skip-commit` runs the complete verification suite—including formatting, linting, repository policy, documentation lint, and all test suites—without validating commit messages or history.
- `0 check` runs the complete verification suite, including commit-message and history validation.

Contributors use `0 fix` for routine authoring and `0 check --skip-commit` before sharing work.

## Rust

The Rust boot implementation is functional, data-oriented, readable, and predictable. Structs and enums are transparent, passive data records. Complex logic lives in standalone, composable functions rather than deeply nested method hierarchies. Methods are reserved for fundamental construction, queries, and views.

Code is designed to be self-documenting through precise types and explicit error contracts. Functions declare their intent in their signatures, and logic is kept to straightforward data transformations. Comments are a last resort rather than routine narration.

[`Cargo.toml`](../../Cargo.toml) configures compiler lints and Clippy to enforce this discipline automatically. Warnings are denied (`-D warnings`), and the `pedantic`, `cargo`, and `style` lint suites are enabled wholesale. The rules actively shape the codebase across four areas:

- **Numeric and conversion safety:** Unchecked integer and float casts are rejected. Conversions must be explicit, lossless, and bounded, preventing silent overflow and truncation.

- **Mechanical sympathy:** Enum variants must not vary wildly in size, avoiding memory and cache bloat. Gratuitous heap allocations, redundant clones, and passing small values by pointer are eliminated.

- **Explicit failure contracts:** Fallible functions must return typed `Result`s. Concealed panics, unhandled unwraps, and process termination are forbidden in library code.

- **Subtractive cleanliness:** Dead code, unused variables, unnecessary mutability, and stale dependencies immediately fail the build.

A small number of lints are explicitly allowed. Doc-comment requirements are temporarily disabled until comment standards are properly established. Module-name repetition is allowed to support clear, singular type naming, and `must_use_candidate` is allowed to avoid redundant attribute annotations.

[`rustfmt.toml`](../../rustfmt.toml) enforces a 75-character line length, two-space indentation, and unified import grouping. Every implementation file containing logic requires an adjacent shadow test file ending in `_test.rs`.

Import practices combine mechanical enforcement with authoring convention. While `rustfmt` and Clippy mechanically enforce single-block layout, item-level granularity, and ban inline absolute paths in function bodies, other practices remain conventions evaluated during review. These include using absolute crate-local paths (`use crate::...`) instead of relative navigation paths, importing specific items rather than intermediate modules, and reserving `use super::*;` strictly for shadow test modules as their local scope exception.

## Python

The command plane (`zero/`) and project subsystem (`proj/`) are written in Python and governed by [`ruff.toml`](../../ruff.toml).

Formatting is enforced by `ruff format`:

- Line length is capped at 75 characters.
- Indentation uses 2 spaces.
- String literals default to single quotes (`quote-style = "single"`).
- Line endings use standard Unix line feeds (`lf`).

Linting is enforced by `ruff check`:

- **Errors (`E`):** Enforces standard pycodestyle error rules.
- **Flakes (`F`):** Detects undefined names, unused imports, duplicate arguments, and syntax errors.
- **Isort (`I`):** Enforces deterministic import grouping and alphabetical ordering.

Run `0 fix lint` to apply automated fixes for import ordering and safe rule corrections.

## Nix

Repository packages, developer environments, and toolchain dependencies are defined in `flake.nix` and `nix/*.nix`.

Formatting is enforced by `nixfmt` across all Nix expressions. Nix formatting runs automatically as part of `0 check fmt` and `0 fix fmt`. Expressions must use consistent two-space indentation and standard list formatting, ensuring deterministic evaluation and reproducible environment builds.

## Repository policy

Repository policy rules are enforced by `zero/repo_policy.py` during `0 check` and `0 check --skip-commit`.

The policy scanner inspects repository files using the Git inventory (tracked files and untracked files not ignored by Git). It prevents unauthorized agent configurations, private memory, or ambient harness instructions from being committed:

- **Banned file names:** `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `CLAUDE.local.md`, and `GEMINI.md`.
- **Banned directory names:** `.agents`, `.claude`, `.codex`, and `.gemini`.

Ambient instruction files or agent-specific scratch directories must not exist in the working tree. Contributors must keep agent configuration in approved repository locations or operator-level configuration.
