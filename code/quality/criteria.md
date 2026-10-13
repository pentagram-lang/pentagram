# Criteria

Within [quality](README.md), code quality judges whether code is clearly correct across its complete execution surface. The code must faithfully execute its intended behaviour across all valid and invalid conditions, and contributors and developers must be able to understand, reason about, and safely change it.

Correctness and clarity are distinct and non-compensatory. For correctness, code must satisfy its functional, operational, and safety contracts, enforcing invariants and handling errors explicitly without unhandled panics, resource leaks, or state corruption. For clarity, code must reveal its intent and data flow directly, allowing contributors and developers to predict its behaviour and modify it safely. Readable code that produces the wrong result is broken, and working code that cannot be understood creates maintenance debt that eventually halts progress. Code is not clearly correct when either condition fails.

## Use the pillar standards

Use [performance](../performance/README.md) for managing computational work, matching scale regimes, and engineering mechanical sympathy with hardware. Use [style](../style/README.md) for expressing intent through clear patterns, modular partitioning, data orientation, and explicit error contracts.

The code contract comes from these standards, from repository architecture, and from documentation and interface specifications local to the subject. A local document, module, or package can establish a narrower convention or stricter contract for the surface it owns, but it must declare that scope directly. Each pillar's README leads to its detailed standards.

Judge the code against that contract, the machine execution it produces, and the needs of contributors and developers. Project records, private conversation, and author memory do not supply substance that the code and its documentation omit. The code must stand on its own text and explicit interfaces.

Violations of [performance](../performance/README.md) and [style](../style/README.md) are correctness problems. Code must match the Pentagram contract in what it computes, how it consumes machine resources, and how its structure expresses intent. An inefficient algorithm or opaque abstraction is a system defect, not a cosmetic flaw. Conforming to performance and style standards is necessary, but does not alone guarantee clear correctness.

## Judge the complete execution surface

Judge the complete execution surface, starting with public entry points and following the execution path through every state transition, invariant check, transformation, and side effect. Include data representations, resource lifecycles, and explicit error handling paths. An isolated routine can run successfully on expected inputs while the complete surface still fails because it panics on boundary conditions, leaks resources, lacks backpressure, or leaves state corrupted after an error.

Dead code and speculative abstractions are impediments to understanding and must not be retained. Conversely, an omission is a defect when an invariant goes unenforced, an error path remains unhandled, a stated contributor or developer use cannot be carried out safely, or the contract requires it. Fast execution cannot compensate for impenetrable structure. Clean presentation cannot compensate for incorrect computation.

## Weigh adequate evidence

Evidence must address the condition being judged. A lint result supports only the mechanical and static rules the linter checks. A test result supports only its assertions under its recorded inputs and execution conditions. An independent review supports only its recorded subject and quality coverage. Performance observation supports only measured workloads on recorded hardware baselines.

Evidence adequacy is proportional to operational risk and leverage. Stage verification into tiered evidence: apply inexpensive static checks and local proofs before investing resources in broader test suites, independent review, or performance measurement. Each tier addresses distinct failure modes, and no single tier can establish complete correctness alone.

The quality judgement is a pass only when adequate evidence supports both correctness and clarity across the complete execution surface. It is a fail when evidence establishes a contract violation, an unmet invariant, an unhandled failure mode, or a clarity problem that prevents safe reasoning or change. It is inconclusive when material evidence is missing, contradictory, or too weak to decide.
