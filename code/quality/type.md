# Type

Within [quality](README.md), this document establishes Pentagram's standard for using strong types to achieve continuous, compile-time confidence that code is clearly correct. It covers how strong typing operates as a system, how to design types across functions and partitions, which weak-typing hazards to watch for, how individual typing tools work, and how to manage type-checking performance.

Without strong types, confidence in even the most basic question—whether the code can run at all—rests on two mechanisms that fail to scale as a codebase grows. Manual tracing lets a contributor hold a small region's assumptions in working memory briefly, but that mental model vanishes as soon as the codebase grows or changes occur elsewhere. Sampled runtime execution through [test](test.md) suites shows only that specific inputs succeeded along visited paths during that run; it cannot prove that unvisited branches are wired validly or that future callers satisfy invariants across all inputs.

Strong types replace both limitations with universal compile-time guarantees across every branch before execution begins. At the baseline, static resolution and type checking verify that bindings are in scope, function calls match their declared signatures, and module imports and exports agree across boundaries. Above that baseline, expressive types encode what transformations occur, enforce domain invariants, verify exhaustive case handling, and make invalid states unrepresentable so readers can judge directly whether code meets [criteria](criteria.md) across its complete execution surface.

Strong typing embodies and supports the [Pentagram manifesto](../../manifesto.md): ergonomic types express domain meaning directly in signatures, deterministic types turn invalid states and unhandled cases into predictable compile-time errors, and efficient types eliminate defensive runtime work while preserving compact hardware layouts.

## Contents

- [Strong typing as a system](#strong-typing-as-a-system)
- [Type design and judgement](#type-design-and-judgement)
  - [Leveraging types across functions and dataflow](#leveraging-types-across-functions-and-dataflow)
  - [Partitioning type ownership and boundaries](#partitioning-type-ownership-and-boundaries)
  - [The ceiling and floor of type safety](#the-ceiling-and-floor-of-type-safety)
  - [Designing ergonomic types](#designing-ergonomic-types)
  - [Parsing raw data at boundaries](#parsing-raw-data-at-boundaries)
  - [Eliminating unneeded code through types](#eliminating-unneeded-code-through-types)
- [Weak-typing hazards](#weak-typing-hazards)
- [Strong typing tools](#strong-typing-tools)
  - [Static binding and module resolution](#static-binding-and-module-resolution)
  - [Strict primitives and explicit conversions](#strict-primitives-and-explicit-conversions)
  - [Nominal wrapper types](#nominal-wrapper-types)
  - [Product types](#product-types)
  - [Sum types](#sum-types)
  - [Opaque types](#opaque-types)
  - [Immutability, ownership, and reference types](#immutability-ownership-and-reference-types)
  - [Generics](#generics)
  - [Traits and interfaces](#traits-and-interfaces)
  - [Higher-kinded types](#higher-kinded-types)
  - [Dependent and refinement types](#dependent-and-refinement-types)
- [Type-checking performance](#type-checking-performance)

## Strong typing as a system

Strong typing is not a local annotation exercise; it is a complex system whose real-world effects depend heavily on how types connect data, functions, and modules across the codebase. Using a language with a static type checker does not by itself guarantee clarity or reliability. Poorly bounded types can tangle unrelated modules into brittle, repository-wide blast radii or bury domain intent beneath opaque signature noise. Well-designed types do the opposite: they compound local reasoning, refactoring velocity, and compile-time assurance as the codebase scales.

In weakly typed code, data has no self-contained contract. Its real shape and invariants are defined implicitly by the union of every writer that constructs or mutates it and every reader that consumes it, forcing contributors to hunt across the repository before trusting a local change. A well-structured type system severs that global coupling. Because no producer can construct a type without satisfying its definition and every consumer relies exclusively on that definition, working memory—both human working memory and agent context windows—needs only the local code at hand and the type definitions it touches.

## Type design and judgement

Realizing those system-level benefits requires deliberate design across functions, partition boundaries, safety trade-offs, ergonomics, external inputs, and code subtraction.

### Leveraging types across functions and dataflow

The data-first method in [functional programming](../style/fn.md) derives function structure from the data representations chosen for domain information. Strong typing multiplies that leverage across three complementary practices:

- **Ground types in domain meaning:** Model domain concepts directly through nominal type identities, meaningful field names, and domain-named variants so the domain contract travels with the value rather than living in variable names, comments, or contributor memory. Signatures then state domain transformations directly, consuming functions branch and destructure in domain terms rather than translating to and from bare mechanics, unrelated concepts with identical shapes stay distinct in the type checker, and domain changes guide updates across every affected site.

- **Align representable states with valid domain states:** Choose exact scalar representations, product types of genuinely coexisting facts, and sum types that attach data exclusively to the variants where that data applies. Every invalid combination excluded by the type definition removes an entire class of defects and defensive branches from the program.

- **Encode established properties in output types:** When a function transforms data or establishes a property—such as authenticating a request, normalizing an email address, sorting a sequence, or checking bounds—return a distinct output type that records that guarantee rather than returning the original unverified type. Downstream functions then require that stronger type in their parameters, allowing the compiler to enforce transformation ordering and preconditions statically without repeating checks at each step.

### Partitioning type ownership and boundaries

Across module and package boundaries (see [partitioning](../style/part.md)), strong typing scales reliably only when it is designed as a distributed system of local type contracts rather than one globally shared type graph.

When a detailed type—especially a rich product type or an exhaustive sum type—is exposed and shared directly across many partitions, two problems emerge: it becomes difficult to reason locally about the type's exact role and invariants, and any change to its fields or variants triggers wide-reaching ripple effects across distant modules. Partitioning strong type ownership keeps the type system modular and resilient:

- **Scope rich representation types to their owning partition:** Keep internal sum types, intermediate transformation records, and invariant-bearing representations private to the partition that owns their meaning and exhaustive handling.

- **Pass guarantees across boundaries without leaking internals:** When callers or neighbouring partitions need to hold, compose, or return values owned by a partition, expose narrow boundary types, opaque types, typed handles, or capability tokens. Callers gain full compile-time proof of origin and validity while the owning partition retains freedom to evolve its internal representations without breaking external code. Where partitions decouple from concrete types altogether, use generics and trait or interface contracts to state exact boundary capabilities.

### The ceiling and floor of type safety

A programming language and its type checker set the **ceiling** on static type safety, carrying specific expressive strengths and ergonomic trade-offs. **The code itself sets the floor.** Even in a language with a high static ceiling, the compiler verifies only the constraints expressed in the types the code actually uses. Choosing representations broader or less specific than the domain requires can drop that floor near zero—making invalid states representable, collapsing distinct concepts into interchangeable values, and leaving invariants to unverified convention (see [weak-typing hazards](#weak-typing-hazards) for examples).

Contributors must exercise engineering judgement to raise the type-safety floor so code is as clearly correct as practical through strong types alone. Raising the floor does not justify baroque type-level encodings that obscure domain logic; when pushing a proof further into the type checker makes signatures harder to follow than the invariant warrants, stop at a clear type boundary.

Sufficiently expressive languages also allow contributors to **raise the effective type-safety ceiling** above what the compiler's built-in rules prove directly. When an invariant spans multiple fields, enforces value ranges, or wraps audited low-level or unchecked operations for hardware sympathy (see [performance](../performance/README.md)), seal the raw representation behind module privacy in a small partition and expose only constructors and operations that preserve the invariant. Back that narrow internal boundary with rigorous [test](test.md) coverage—such as property-based, dynamic sanitizer, or formal verification tests—so every caller outside the partition receives a sound compile-time guarantee.

### Designing ergonomic types

Ergonomics is an integral aspect of type safety, not a competing goal. In [environment engineering](../../env/README.md), code and documentation together form the working environment that shapes how contributors understand, write, change, and test a system. When strong types are straightforward to understand, construct, compose, and inspect, the safe path is naturally the easiest path to follow.

When contributors feel tempted to punch holes in strong types for convenience—such as widening private invariant-bearing fields to public, exposing unchecked constructors, weakening domain types back to raw primitives, or adding invalid dummy states to simplify setup or tests (see [unacceptable test practices](test.md#unacceptable-test-practices))—treat that impulse as a signal that the type system as an environment is not working well. If legitimate call sites or tests struggle to assemble valid values or see how types fit together, that friction actively pressures contributors to bypass safety.

Resolving that friction without sacrificing guarantees—especially during advanced type work—requires a strong understanding of language mechanics and careful judgement in applying them so the type system is both safe and easy to use. Apply language features such as focused constructors, composable transformation helpers, inference-friendly signatures, zero-cost views or conversions, and valid test-data builders so invariants remain sound while everyday use stays direct and readable.

Pair those mechanics with clear local documentation (see [documentation standards](../../doc/README.md)) where signatures alone cannot convey the full contract. Documentation is not a substitute for a clean API or a place to repeat obvious types, but concise explanations of domain invariants, intended construction and transformation paths, and semantic laws help contributors use rich or opaque types confidently without reverse-engineering internals.

### Parsing raw data at boundaries

External inputs—such as command-line arguments, files, network payloads, environment variables, and serialized storage—necessarily arrive at the lowest type-safety floor. Rather than inspecting raw inputs with boolean validation helpers and continuing to pass unstructured strings, byte slices, or maps deeper into the program, parse raw inputs at the perimeter directly into narrow domain types ("parse, don't validate").

When raw input fails to satisfy domain constraints at an external boundary, surface that rejection immediately—either as branching domain data when callers take conditional paths on the mismatch, or as a declared operational error when the operation cannot proceed (see [error handling](err.md)). Once data crosses that parsing boundary, interior functions operate exclusively on strongly typed domain values whose invariants are already established.

### Eliminating unneeded code through types

Strong types are one of the sharpest tools for practicing [subtractive design](../../rm/README.md): identifying code that should not exist and making it safe to remove or never write at all.

Treat defensive checks, fallback branches for "impossible" conditions, repeated precondition guards, and error propagation for failures that cannot occur in a given context as design signals that the surrounding types are too loose. By tightening the type definitions so those invalid states and unachievable branches cannot be constructed, the compiler proves that the defensive code, [error handling](err.md) plumbing, and corresponding runtime [test](test.md) cases are unnecessary—letting contributors delete them with complete confidence.

## Weak-typing hazards

Even in a strongly typed language, weak representations can lower the type-safety floor and push unnecessary checks onto callers. For example:

- **Raw primitives:** Representing domain values as raw primitives hides domain rules from the type checker. Unparsed text forces downstream code to assume a valid format or parse it repeatedly, and bare numbers let callers swap distinct identifiers or units without a compile error.

- **Overused stock types:** Stock types express data shape without domain semantics. For example, passing a boolean flag or returning an unlabelled optional forces callers to infer what each case means from context and lets unrelated values be swapped silently. A domain-specific type turns that implicit meaning into a contract the compiler checks across every consumer.

- **Invalid default states:** Giving a domain type an artificial default state makes initialization convenient by polluting its contract. When a placeholder variant or optional wrapper stands in for missing initialization data, every consumer must guard against a value with no valid domain meaning. That shortcut recreates the hazard of implicit null inside a static type system.

- **Combinatorial product types:** Combining many sum types—such as booleans and optionals—inside one flat record multiplies their cases together. Most of the resulting field combinations cannot legitimately occur in the domain, leaving callers with fragile cross-field checks and subtle state bugs. Reshaping the record into an outer sum type represents only the mutually exclusive states that actually exist.

- **Dynamic type erasure:** Representing statically known structure with dynamic values or unchecked casts opts out of compile-time checking. Once a boundary erases static structure—such as storing fixed fields in a string-keyed map—every downstream consumer loses compiler guarantees and preventable mismatches surface only at runtime.

## Strong typing tools

The tools below form a progression from foundational program wiring to advanced compile-time invariants, each with its own target, strengths, and weaknesses.

### Static binding and module resolution

- **Target:** Static resolution checks that referenced names are in scope and that calls and imports match their declared module contracts.

- **Strengths:** The compiler verifies coherent program wiring across every branch before execution begins, including failure paths that rarely run. Cross-codebase renaming and signature changes become deterministic compile checks instead of runtime failures.

- **Weaknesses:** Resolution proves only that names exist and declared types align. Overly broad parameter types still let invalid domain values pass through compatible signatures unchecked.

### Strict primitives and explicit conversions

- **Target:** Strict primitive typing keeps built-in scalar representations distinct—such as numeric widths or text versus raw bytes—and requires explicit conversions between them.

- **Strengths:** Requiring explicit conversions prevents silent numeric truncation and implicit truthiness coercions. Lossy or fallible representation changes remain visible directly in the dataflow.

- **Weaknesses:** Unrelated domain values that share the same scalar type remain interchangeable unless wrapped in distinct nominal types.

### Nominal wrapper types

- **Target:** A nominal wrapper gives a single underlying value a distinct type identity, separating concepts such as account identifiers and order identifiers or milliseconds and seconds.

- **Strengths:** Distinct type identities catch transposed arguments and invalid cross-domain operations at compile time. Compilers typically erase simple wrappers during code generation, making signatures self-documenting with no runtime memory or CPU cost.

- **Weaknesses:** A transparent wrapper enforces type identity alone. Value ranges and other invariants still require privacy protection (see [opaque types](#opaque-types)).

### Product types

- **Target:** A product type groups coexisting domain facts into a single composite record with named fields.

- **Strengths:** Named fields replace fragile positional tuples and ad hoc maps with a fixed structure checked at every construction and access site. Related facts travel together coherently across transformations.

- **Weaknesses:** A record permits every combination of its field types. When fields are valid only in specific modes, a flat record admits invalid combinations unless reshaped with [sum types](#sum-types) or sealed with [opaque types](#opaque-types).

### Sum types

- **Target:** A sum type models mutually exclusive domain cases so each variant carries only the data valid for that case.

- **Strengths:** Attaching data to specific variants eliminates implicit null and impossible cross-state field combinations while expressing domain meaning directly. Exhaustiveness checking proves that consumers handle every case and flags every site that must adapt when variants change.

- **Weaknesses:** Adding a variant requires updating exhaustive matches across the type's visibility scope, making [partitioning type ownership and boundaries](#partitioning-type-ownership-and-boundaries) essential. Careless wildcard branches or catch-all unknown variants also defeat exhaustiveness checking.

### Opaque types

- **Target:** An opaque type hides its internal representation behind module privacy so outside code can construct or transform values only through invariant-preserving functions.

- **Strengths:** Sealing the representation raises the effective type-safety ceiling by guaranteeing multi-field or value-range invariants for every external instance. Verification stays confined to one small module while callers gain compile-time assurance.

- **Weaknesses:** Callers cannot construct literals or match internal fields directly, so the owning module must provide ergonomic constructors and accessors. Any defect inside that module compromises the guarantee for all callers.

### Immutability, ownership, and reference types

- **Target:** Ownership and reference rules track how values may be mutated or aliased and bound how long references and resources remain valid.

- **Strengths:** Static aliasing and lifetime checks prevent dangling references and concurrent data races while keeping mutation local. Must-use or single-use obligations can also ensure that handles and state transitions are never silently dropped.

- **Weaknesses:** Strict aliasing and lifetime rules create friction for cyclic or graph-shaped data. Those structures often require alternative designs such as arena-allocated typed indices or carefully encapsulated interior state.

### Generics

- **Target:** Generics parameterize data structures and functions over caller-chosen types through parametric polymorphism.

- **Strengths:** Type parameters preserve exact caller types across containers and transformations without duplicating code or erasing types dynamically. Parametricity also strengthens correctness: a function that knows nothing concrete about a type parameter cannot inspect or fabricate values of that type, sharply narrowing possible defects.

- **Weaknesses:** Adding type parameters when only one concrete type exists clutters signatures and harms readability, violating [subtractive design](../../rm/README.md).

### Traits and interfaces

- **Target:** Traits and interfaces specify shared capability contracts that independent types can implement without class inheritance hierarchies.

- **Strengths:** Generic functions and module boundaries can state the exact operations they require, decoupling algorithms from concrete representations while keeping dispatch explicit.

- **Weaknesses:** Broad, poorly factored interfaces recreate tight coupling across types. Signatures alone also cannot enforce semantic laws such as associativity or round-trip equivalence, which still require [test](test.md) coverage.

### Higher-kinded types

- **Target:** Higher-kinded types abstract over type constructors—such as collections or fallible contexts—independently of the element types inside them.

- **Strengths:** Abstracting over container shapes unifies recurring structural operations like mapping or sequencing across different wrapper types without losing static type safety.

- **Weaknesses:** Type-constructor abstraction adds substantial conceptual weight and can degrade type inference and compiler diagnostics where concrete functions would read more clearly.

### Dependent and refinement types

- **Target:** Dependent and refinement types constrain types with values or logical predicates checked at compile time, such as collection lengths or numeric bounds.

- **Strengths:** Pushing value-level invariants into the type checker proves properties like bounds safety or non-emptiness statically, removing runtime assertions altogether.

- **Weaknesses:** Value-level proofs complicate type inference and ongoing maintenance. Contributors must judge whether compile-time proofs are clearer and more economical than sealing the invariant in [opaque types](#opaque-types) backed by assertions and [test](test.md) suites.

## Type-checking performance

Type checking is a computational workload governed by [performance](../performance/README.md). Unbounded type complexity can make check times grow superlinearly, stalling vital feedback in the `dev loop` and slowing `pre-merge` gates just like an expensive test suite.

Two mechanisms drive most type-checking slowdowns. Locally, heavy type-level work—such as deeply nested generics or wide trait search spaces—can push the compiler into combinatorial inference. Globally, sharing rich types across many modules couples the type graph so a small change forces wide re-checking.

Manage both costs through the same design, observation, and tuning cycle used for runtime code:

- **Localize the type graph:** Apply [partitioning type ownership and boundaries](#partitioning-type-ownership-and-boundaries) so module interfaces stay narrow and incremental checks remain local.

- **Bound local inference:** Write explicit type annotations at module and function boundaries, and simplify type-level abstractions whose solver cost outweighs their safety benefit.

- **Observe check timings:** Measure compiler and type-checker timings across modules as the codebase grows so scaling cliffs are caught before they degrade contributor velocity.
