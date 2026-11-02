# Error handling

Within [quality](README.md), error handling governs how code represents, propagates, contains, recovers from, and reports failures during execution. Code is clearly correct only when its failure paths are engineered with the same rigour as its success paths, ensuring that the system exhibits well-defined, predictable, and positive behaviour when operations fail.

Error handling must embody and support the aims defined in the [Pentagram manifesto](../../manifesto.md):

- **Ergonomics:** Make failure contracts visible at every signature and call site, and present errors and recovery outcomes clearly so operators, developers, and contributors can act without guesswork.
- **Determinism:** Distinguish branching domain data from operational errors and invariant crashes, ensuring that failures never corrupt state or jump through hidden control flow.
- **Efficiency:** Isolate and resolve failures at partition boundaries rather than wrapping execution in defensive try-catch pyramids or propagating low-level errors blindly through unrelated layers.

## Data, errors, and crashes

Clear reasoning about failure starts by separating outcomes into three distinct categories: domain data, operational errors, and invariant crashes. Confusing these categories either forces callers to write dead recovery code for bugs or disguises normal branching logic as exceptional failure.

### Domain data

When a caller must inspect an outcome to choose the next conditional control-flow path, that outcome is normal domain data, not an error. Represent expected branching outcomes—such as a missing lookup key, an exhausted iterator, or a validation mismatch that guides interactive branching—explicitly in the return type using optional values or tagged unions.

Never inspect an error to drive conditional domain control flow. If a caller needs to branch on why an operation did not produce a primary value, promote that distinction into the function's return data so the compiler enforces exhaustive handling as ordinary logic.

### Errors

An error represents an operational failure where a function cannot complete its contract—such as an unavailable external resource, a rejected input at a boundary, or a cancelled operation—while program invariants and memory safety remain intact. Because state has not been corrupted, the calling program can safely recover and continue reusing existing memory and resources.

Functions that can fail with an operational error must declare that possibility explicitly in their signature. Every call site must confront the declared error directly, either by propagating it to its own caller or by capturing it as a result value for recovery. Silent error drops and implicit, nonlocal exception jumps are forbidden. Because callers do not branch on specific error variants for domain control flow, error values themselves remain lightweight rather than growing into sprawling, nested type hierarchies.

### Crashes

A crash represents a bug or a violated internal invariant—such as a failed precondition, postcondition, or data-structure assertion (see [internal invariant assertions](test.md#internal-invariant-assertions)). When an internal invariant fails, the program's reasoning foundation is broken: local assumptions no longer hold, state may be corrupted, and no state within the failing unit can be trusted or reused.

Do not route invariant violations through normal error return paths. Instead, terminate the current task or isolation unit immediately so corrupted state cannot propagate or persist. A crash forces recovery to move to a deeper isolation boundary—such as tearing down the task, process, or isolated memory arena and restarting from a known-good state—while still capturing active diagnostic context for telemetry. Conversely, library and production code must never crash on untrusted external inputs or expected operational failures; those must be handled as domain data or declared errors.

## Partitioning and recovery

Containing errors requires clearly correct, well-partitioned code (see [partitioning](../style/part.md)). When partition boundaries and invariants are unclear, contributors cannot determine locally how to resolve a failure and instead let every low-level error propagate across every layer of the stack.

Effective error isolation requires intentional design on both sides of a partition boundary:

- **The inner partition:** A partition must own and recover from every failure that it has the local context and authority to resolve. If an internal step fails in a way that the partition can retry, fall back from, or prevent through earlier input validation, the partition resolves that failure internally. It declares in its public API only the errors that genuinely cannot be resolved within its own boundary.

- **The outer partition:** When calling a fallible API, the outer partition must intentionally decide whether and how to recover from the declared error. Because errors do not drive domain-specific branching, recovery at a partition boundary is generic: the outer partition may abort a bounded unit of work, roll back transient state, retry the operation under a policy, or substitute a safe fallback, or it may decide that its own operation cannot complete and propagate the error upward as part of its own declared contract.

When both the inner and outer sides of every boundary act intentionally, stacking partitions recursively across the program produces a system with predictable, positive failure behaviour. Low-level implementation failures never leak outward, and each boundary absorbs the failures appropriate to its scale.

## Context, telemetry, and presentation

Because error values are not inspected for conditional control flow, diagnostic richness belongs in execution context rather than in complex error-type payloads. As execution moves through scopes and partitions, code attaches structured, typed context—such as scoped marks, operation parameters, and trace spans—to the active lexical scope. When an error or crash occurs, the runtime captures the active context automatically along the failure path.

When an outer partition captures an error (or when a supervision boundary handles a crash) to perform generic recovery, it pairs that recovery with detailed telemetry drawn from the captured context. Attaching structured context to scopes eliminates the need for scattershot defensive logging at every intermediate propagation step while still giving contributors and operators exact visibility into where and why a failure occurred.

When an error or recovery action crosses an external boundary to a human or agent (see [environment engineering](../../env/README.md)), its presentation must be truthful, transparent, and actionable:

- **State what failed in domain terms:** Translate internal failure mechanics into the vocabulary of the boundary's contract, and explain what action or input change can resolve the problem while preserving detailed internal context in telemetry or diagnostic views.

- **Report state and recovery truthfully:** Never leave a participant guessing what changed before the failure occurred. Make recovery atomic where practical, and state plainly whether changes were rolled back cleanly, partially applied, or retried.

- **Avoid silent degradation:** Do not hide operational errors behind silent fallbacks that alter semantics or behind unbounded retry loops that appear as stalls. When a partition recovers by degrading capability or retrying across a noticeable delay, surface that recovery behaviour explicitly.

## Adapting external code

Operating-system interfaces, third-party libraries, and external runtimes rarely separate domain data, operational errors, and invariant crashes. External code frequently overloads error returns or unchecked exceptions to signal routine branching conditions (such as end-of-stream or a missing entry), embeds diagnostics inside external error payloads, or returns error codes when caller preconditions were violated.

Never allow external error types, unchecked exceptions, or external error conventions to leak across internal partitions. Isolate external dependencies behind a thin adapter boundary that immediately transforms their outcomes to match this error model:

- **Promote branching conditions to domain data:** Inspect the external error or status code once inside the adapter to separate expected branching cases from genuine failures, returning those cases as normal optional values or tagged unions. This adapter boundary is the only place where inspecting an error value for conditional control flow is valid, because it repairs an external interface that encoded normal data as an error.

- **Convert operational failures and extract context:** Capture external error payloads or exceptions at the adapter boundary, attach their relevant diagnostic details to the active lexical scope as structured context, and either recover locally or surface a clean declared error.

- **Crash on violated invariants:** When an external interface returns an error code that indicates corrupted internal or external state, terminate the task immediately at the boundary rather than propagating the bug as a recoverable error.
