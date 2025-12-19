# Pentagram Context for Agents

## Mandatory Readings

**CRITICAL**: At the start of every session, you **MUST** read `.tmp/manifesto.md` to understand the foundational philosophy and core principles of Pentagram. This document outlines the rationale behind its design and its aspirations.

## Introduction

Pentagram is built on the belief that a programming language should be a tool for clear reasoning. It rejects the "inevitable" friction of modern development—baroque syntax, shared mutable state, and inefficient defaults—in favor of three core aspirations:

- **Ergonomics**: We prioritize human cognition. Reading and writing code should be a low-friction activity where the syntax aids comprehension rather than obscuring it.
- **Determinism**: By eliminating shared mutable state at the foundation, we make programs predictable. This allows both humans and machines to reason about code with absolute confidence.
- **Efficiency**: High performance is a baseline requirement, not a post-process optimization. Pentagram programs are designed to run fast by default, reducing both environmental impact and developer frustration.

## Key Language Features

Pentagram's design flows directly from its core aspirations, resulting in a unique set of features that prioritize flow and safety:

- **Postfix Flow**: The language defaults to postfix notation (e.g., `1 2 +`), allowing values to be read in the order they transform. Prefix mode remains available for complex expression trees where it provides better clarity.
- **Immutable Core**: Every value in Pentagram is immutable. What appears as mutation is actually lexical replacement within a scope, ensuring that data flow is always explicit and traceable.
- **Strict Type System**: Our nominal and strict type system supports generics, traits (specifications), and higher-kinded types, providing powerful abstractions without sacrificing clarity.
- **Explicit Error Handling**: We avoid exceptions. Errors are treated as first-class values that must be explicitly propagated or captured using the `?` operator and context-aware "marks."
- **Structured Concurrency**: Concurrency is built-in, green-threaded, and purely asynchronous. All IO operations utilize modern async interfaces (like `io_uring`) to ensure maximum efficiency.

## Critical Reference

**ALWAYS consult `.tmp/tour.md` for detailed syntax, semantics, and feature implementation.**
That file contains the definitive guide on:

- Variable assignment and scoping
- Primitive values (Numbers, Text, Booleans)
- Data structures (Collections, Wrappers)
- Control flow (Loops, Conditionals)
- Type definitions (Records, Unions, Specs)
- Module system and testing

Refer to `.tmp/tour.md` whenever you need to write or analyze Pentagram code.

## Task Runner (`pt`)

The `pt` command is the central nervous system of the Pentagram development workflow. It is a Nix-installed task runner that ensures every developer and agent interacts with the codebase in a consistent, reproducible manner.

### Developer Workflows

The `pt` runner organizes common tasks into high-level workflows that prioritize speed and correctness:

- **The Fix Loop (`pt fix` / `pt f`)**: This is the primary tool for maintaining code health. It automatically formats Rust and Python code, applies automated fixes for common lints, and runs Clippy to catch deeper issues. For large changes, you can use `pt f l <package>` to focus these operations on a specific local area.
- **The Check Cycle (`pt check` / `pt c`)**: This command represents our "Definition of Done." It runs the full suite of formatters, linters, and tests. It also validates the project's commit history. No task is considered complete until `pt check` passes in its entirety.
- **Execution (`pt run` / `pt r`)**: Use this to execute Pentagram scripts or start the `boot_shell`. It handles the environment setup required to run the Pentagram runtime.

### Testing and Validation Rigor

We treat warnings as errors. The `pt` runner will fail if any lints are triggered, ensuring that technical debt does not accumulate. Testing is equally rigorous and split into two domains:

- **Bootstrap Testing (`pt check btest` / `pt c bt`)**: These are the Rust-based unit and integration tests for the language's "boot" implementation. You can scope these to specific packages (e.g., `pt c bt boot_eval`) or test names (e.g., `pt c bt boot_eval arithmetic`).
- **Language Testing (`pt check test` / `pt c t`)**: These are the end-to-end tests written in Pentagram itself (located in `core/`). They verify the high-level behavior of the language.
- **Observability**: Use the `-n` flag (e.g., `pt c bt -n`) with bootstrap tests to disable output capture, which is essential when debugging tests that produce stdout logs.

### Completion Standard

The standard for any contribution is absolute: **ALL** work must result in a passing `pt check` before it can be integrated. This ensures the main branch remains stable and the history remains valid.

## Commit Standards

Pentagram treats its history as a high-fidelity narrative. The goal is to produce a single, well-crafted commit that represents a complete pull request (PR).

### The Single-Commit Workflow

We operate on a "one commit per PR" model. A commit is not a snapshot of a moment in time, but a living document of a specific contribution.

1.  **Session Orientation (Crucial)**: Every session must begin by determining its relationship to the project's PR history.
    - **The Goal**: Identify if you are continuing an existing PR or starting a new one. In our model, a single commit _is_ a single PR.
    - **The Audit**: Analyze the git state to find your bearings. Look for WIP commit messages, check the working tree for uncommitted changes, and examine the commit history to see if you are part of a chain of unmerged PRs.
    - **The Decision**: Explicitly decide which commit is the focus of the current session. If you are starting fresh, you will create a WIP commit. If you are continuing, you will amend the existing one. Never assume the "task" matches the session boundaries.
2.  **The Placeholder**: If starting a new PR, begin with a simple WIP message (e.g., `feat` or `fix`).
3.  **The Living Commit**: All subsequent work—fixes, refactors, or formatting—must be folded into the identified commit using `git commit --amend`. We never create "fixup" or "lint" commits within a single PR's scope.
4.  **Fact-Gathering**: When the implementation is stable, the transition out of WIP begins with a rigorous audit.
    - **The Audit**: Run `git show --stat` to identify every file touched by the PR.
    - **Logical Grouping**: Organize these files into logical clusters (e.g., Infrastructure, Parser, Tooling).
    - **Exhaustive Analysis**: Employ subagents (via `codebase_investigator`) to perform a deep, factual dive into every changed file. Run these subagents in parallel to ensure efficiency while maintaining depth.
    - **Diff Provisioning**: Since subagents may lack direct shell access, the parent agent must provide the relevant diff content. Pre-divide the full `git show` output into logical, separate files within a project-local temporary directory (e.g., `.tmp/diffs/`) for the subagents to analyze.
    - **No Line Left Behind**: The subagent's mandate is to extract objective data about every single change. No line of the diff can remain unexamined. This is a "facts only" research phase; do not summarize until this phase is complete.
5.  **Narrative Synthesis**: After research, synthesize these facts into a definitive commit message. This message is the final product.

### The Narrative (Primary Focus)

The commit message is a technical essay on the change. It must go beyond "what" and explain the "why," the "how," and the "impact."

- **The Intent**: Why was this change necessary? What problem does it solve or what aspiration does it fulfill?
- **The Architecture**: How does this change fit into the existing system? What were the trade-offs made during implementation?
- **The Findings**: What did we discover during the research phase? Highlight non-obvious consequences of the diff.
- **The Impact**: What is the state of the system now? How should future developers (or agents) reason about this new code?

### Safety and Control

- **User Confirmation**: Never execute `git add`, `git commit`, or `git commit --amend` without explicit user confirmation or request. You are responsible for proposing these actions, but the user maintains final authority over the git state.

### Syntax (Secondary Focus)

While the narrative is paramount, it must be wrapped in strict **Conventional Commit** syntax to support automated tooling.

- **The Summary Line**: The first line is the "headline" of the PR. It must be a clear, concise Conventional Commit message. This line is used directly in the project's changelog, so it must be meaningful at a glance.
- **The Body**: The extensive narrative (The Intent, Architecture, Findings, Impact) must be placed in the body of the commit message, separated from the summary line by a blank line.
- **Format**: `<type>[optional scope]: <description>`
- **Types**: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`.
- **Linear History**: No merge commits. The history remains a single, clean line of narrative-driven entries.
- **Validation**: Every commit is validated via `pt check` (which runs `cog check`).
