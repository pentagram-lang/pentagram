# Documentation standards

Documentation is part of Pentagram's working system. It tells readers what a subject means, how it behaves, how to use or change it, and what they may rely on. A correct implementation cannot make missing or misleading documentation correct after the fact.

A **subject** is the system, interface, process, or question that a documentation surface describes. A documentation surface is the entry document, every document and section in its reader path, their links and structure, and any companion that supplies part of their contract. A surface stands on its own when a reader can recover its subject, scope, status, and reading path from the surface and the subject it describes. Project records, private conversation, and author memory are not part of that explanation.

The `doc/` directory defines the documentation system: how documentation carries meaning, takes shape, uses language, and is judged. It does not define the meaning of a particular subsystem; the smallest subject that owns a claim does that. Start from the subject's local `README.md` and use these standards to decide how its documentation should work.

Documentation quality belongs to the complete surface, not to a change record or an authoring process. A surface must give its intended readers enough meaning, scope, status, and path to understand and use the subject without reconstructing missing context. These standards judge documentation as documentation, not the change that introduced it.

The [manifesto's three aims](../manifesto.md) guide these standards:

- **Ergonomics:** give readers a short, understandable path.
- **Determinism:** make meaning, status, and links predictable.
- **Efficiency:** carry the needed information without avoidable reading or maintenance work.

The aims improve the documentation system. They do not replace accuracy, understandability, or usability.

## Meaning

[Meaning](meaning/README.md) describes the claims, concepts, relationships, and notation that documentation carries.

## Structure

[Structure](structure/README.md) describes where documentation lives and how readers move through files, sections, links, and companions.

## Style

[Style](style/README.md) describes how documentation expresses its meaning clearly and consistently.

## Quality

[Quality](quality/README.md) judges a complete documentation surface for accuracy, reader use, and the applicable standards. Its evidence comes from mechanical checks, reader trials, and independent review where those methods add useful information.
