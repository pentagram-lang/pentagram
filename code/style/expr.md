# Expression style

Within [style](README.md), this document describes the expression of code at its smallest useful scale. It governs names, statements, local ordering, and other local decisions.

Code must express its task directly so that a contributor can easily work with it line by line: read it, understand it, debug it, and change it.

Good expression applies the [Pentagram manifesto](../../manifesto.md) aims in low-level code. Ergonomic expression follows machine execution clearly and remains accessible to edits. Deterministic expression makes interpretation follow predictably from explicit terms and context. Efficient expression carries every needed task without unnecessary programming abstraction or machine work.

[Subtractive design](../../rm/README.md) is essential in all code expressions, because it will let the code state exactly what's needed and nothing else.

The rules here are shared defaults, not a demand that every unit of code sound the same.

## Lead to use

Begin with the task the code exists to perform. Let the first useful names and expressions establish what enters the computation, what changes, and what result leaves it. Do not make a reader pass through project setup, incidental machinery, or generic orchestration before they can see the task.

A local sequence should make its next useful step apparent. If the result matters, let the path toward that result remain visible. If a condition controls an task, put the condition where the task can be understood. If an effect crosses a boundary, show that boundary rather than hiding it in a helper whose name says little.

Code should lead to use in the same way that a good document leads to its reader's next need. The reader should not have to begin with the author's history, the order in which the code was discovered, or everything the implementation happens to know.

## Preserve order of tasks

Arrange local code from input through transformation to result and effect. Put each value near the task that gives it meaning. Put a condition before the task it governs, keep related alternatives together where their distinction is made, and make a result visible where the computation establishes it.

When nesting hides that sequence, name the steps. Do not send the reader through distant mutable state, callbacks, or generic dispatch to discover a local task. Source order should explain what the code does now, not record how it was discovered.

## Name what happens

Code's reasoning lives in its names and choices. Name the task that actually occurs. `resolve_module` says more than `process`; `advance_cursor` says more than `handle`; `content_hash` says more than `data`.

Name a value after the concept it carries, not after its storage or temporary role. Name the actor when responsibility matters. Prefer singular, specific names. Preserve established identifiers, syntax, commands, and external terminology when they are exact parts of the interface. Otherwise, remove unexplained abbreviations and general verbs that make the reader guess.

A short name is efficient only when the reader already has the right meaning for it. Do not flatten a precise task into neutral names or layers because a more direct shape feels less conventional.

## Remove development residue

Exploration is not a source feature. Remove temporary prints, trace variables, commented-out alternatives, diagnostic scaffolding, and branches that exist only to inspect a problem when the investigation is over.

A diagnostic that belongs to the running system is not residue. Give it an ordinary name, a deliberate effect boundary, a documented contract where needed, and evidence that covers its behaviour. Do not preserve a temporary mechanism by disguising it as infrastructure.

Project context must not leak into implementation. Do not make a current source file depend on a task, draft, session, conversation, or discovery story that is not part of the code's subject. A contributor who reads the source later must be able to understand its current task without private project records or author memory. And a machine running a clean repo without temporary files must be able to execute correctly.

## Document contracts, not internals

The [`doc/` directory](../../doc/README.md) owns the documentation system, including documentation expressed in or alongside code. Its standards govern that documentation's meaning, structure, style, and quality.

Public documentation in code should describe contracts: behaviour, invariants, constraints, and other facts that a reader may rely on. Public documentation that describes internal details is not acceptable. If an implementation detail affects a contract, document the contract; otherwise, keep the detail private.

Private documentation is always a hazard that risks correctness, and it is only permitted in the exceptional circumstance when it is impossible to create clearly correct code through naming, ordering, modularity, and abstraction.

## Follow lint rules

Lint rules exist because they add value to clarity and correctness. Always follow a lint rule unless the code truly and legitimately requires an exception. If the rule itself is wrong for the codebase, change it globally instead of overriding it locally. Keep a legitimate override narrow and explicit, and state why it is required.

## Keep style local

These expression style rules are shared, but every code unit does not need the same shape. Choose the form, density, or notation that best serves the local code.

Keep that choice local to the code it serves. It must not silently change shared names, semantics, or the meaning of a common code pattern. Do not force unrelated code into the same shape.
