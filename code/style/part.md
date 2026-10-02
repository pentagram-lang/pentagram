# Partitioning

Within [style](README.md), this guide governs partition design: how to scale code up using recursive, coherent, clearly correct units.

In database engineering, tables are partitioned to optimize the use of compute resources like memory, disk I/O, and locks. In [environment engineering](../../env/README.md), code is intentionally partitioned to optimize **contributor context**—human working memory and agent context windows. For both systems, partitioning restores locality so that operations execute against local capacity rather than requiring global coordination.

Because partition design has high demands for analysis and refactoring, it requires code to follow [functional programming](fn.md) to set a solid foundation: pure transforms of explicit data, leaving effects to a thin shell.

The benefit of good partitioning is that when data structures and the functions that operate on them are colocated within clear boundaries, safety and power compound together. Safety enables change velocity because modifications inside a partition have minimized ability to affect other partitions. Power scales through compounding leverage, assembling useful self-contained units into larger capabilities, without increasing local complexity.

## Principles

Every partition defines a boundary of ownership and exposes an **API**: the explicit contract through which outside code interacts with it. [Subtractive design](../../rm/README.md) guides the design of every partition. It requires removing everything non-essential until the partition contains only the minimum internal scope needed to perform its task, and exposes only the minimum API needed by callers.

A partition owns data and the computation that operates on it. Strong privacy enforces this jurisdiction: code is private by default, including even data. This allows internal partition code to be changed or rewritten freely and safely.

The job of the API is to mediate the boundary, enabling callers to easily use a partition for their own purposes. A good API will let callers specify what computation is required, using explicit input and output data structures, while leaving the partition to govern how to achieve the result.

## Scales

Partitioning is a recursive discipline applied across every level of software structure. The same governing principle—containing the minimum internal scope and exposing the minimum API—operates across four distinct scales:

- **Expressions:** Partition intermediate evaluation and temporary state within a function using local blocks, statements, and assignments ([expression style](expr.md)). This keeps low-level code from causing confusion in surrounding logic, ensuring function bodies remain clean and readable.

- **Data structures and functions:** Partition domain models across separate data structures, and partition computation across discrete functions ([functional programming](fn.md)). Coherent data and function design allows for easy and direct usage.

- **Modules (files):** Partition cooperating data structures and functions into modules (represented on disk as separate files). A module enforces privacy rules to hide internal helpers and representation details, exposing only the exported symbols that form its public API.

- **Packages (directories):** Partition modules into a hierarchy of packages (represented on disk as directories). Packages are nested to build a recursive structure of subpackages, each with their own boundary and clean package-level API.

## Method

Good partitioning is the deliberate result of designing an API from the outside in. Rather than writing internal code and wrapping it in a hasty public interface, use this eight-step recipe to establish the boundary, define the API, and prune internal scope:

1. **Name the capability in one sentence.** State what the partition provides to callers without using implementation nouns or internal mechanics. If describing the capability requires the word "and", consider splitting it into multiple partitions. If two units cannot be described independently, merge them.

2. **Identify owned data and computations.** Determine the data, invariants, and computations that the partition encapsulates, from temporary evaluation state to domain models. A partition boundary that establishes no meaningful ownership does not earn its existence.

3. **Write client code first.** Test the boundary by writing realistic calling code before implementing internal functions. Verify that the call site is clean, direct, and hard to misuse. If calling code requires clumsy orchestration or elaborate setup, redesign the API before writing internals.

4. **Minimize the contract.** Strip away every non-essential component of the API ("when in doubt, leave it out"). Measure API size by conceptual weight rather than symbol count, with the goal of minimizing the ongoing cognitive cost on callers.

5. **Purge reverse dependencies.** Ensure lower-level partitions contain no vocabulary, workflows, or assumptions from higher-level callers. A partition must remain completely freestanding and usable in isolation without awareness of who calls it.

6. **Contain failures.** Translate internal calculation failures and low-level errors into domain-meaningful return values. Do not allow internal implementation mechanics or unexpected error types (or control flow) to leak across the API boundary.

7. **Strip unused internal scope.** Remove all code within the partition not transitively used to satisfy the API. Applying [subtractive design](../../rm/README.md) internally ensures the partition contains only the exact code required for its capability.

8. **Test by variation and change.** Modify an internal data representation or algorithmic detail to confirm that the API holds without breaking callers. Verify that the partition can be fully tested (as an integration test) using only its own public interface and local inputs.

## Heuristics

To supplement the method outline above, these heuristics provide practical rules of thumb for evaluating boundaries and guiding code changes during design and maintenance:

- **One canonical path:** An API must provide exactly one canonical path for each distinct caller intent. Offering multiple overlapping paths to serve the same intent degrades ergonomics and conceals correctness defects. When caller intents diverge, provide separate operations rather than overloading a single interface.

- **Reject central planning:** Prevent functions and data structures from taking on massive scope to coordinate other parts of the system. Coordinating code must not accumulate the domain knowledge of its dependencies; keep units focused on their own discrete transformations.

- **Prevent leaky abstractions:** Pushing internal decisions outward leaks implementation mechanics and internal state across the boundary. When an interface forces callers to inspect internal representations, handle intermediate states, or orchestrate execution sequencing, pull the computation inward to where the data lives.

- **Avoid uninformed usage:** An API must not expect usage that the caller lacks the data to specify correctly. When an interface requires callers to supply inputs, make decisions, or coordinate steps that they lack the data to resolve, callers are forced to guess and correctness defects are inevitable. If a caller cannot legitimately determine how to use an API from its own context, the partition must govern that behaviour internally.

- **Experiment with splitting and merging:** Good partition boundaries rarely appear on the first attempt. Experiment by dividing and combining code along different domain axes until clean boundaries and good partition design emerge. Merge units that share tight invariants; split units whose reasons to change diverge.

- **Refactored code needs redesigned APIs:** Refactoring is not merely moving lines of code between files. When internal implementation changes, re-evaluate what the partition contains and what its API exposes. Preserving an outdated API over restructured internals fossilizes old assumptions.
