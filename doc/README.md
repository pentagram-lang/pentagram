# Documentation standards

Documentation is part of Pentagram's working system. It tells readers what a subject means, how it behaves, how to use or change it, and what they may rely on. A correct implementation cannot make missing or misleading documentation correct after the fact.

A **subject** is the system, interface, process, or question that a documentation surface describes. A documentation surface starts with an entry document and its reading path. It includes every document and section that path presents. It also includes the links and structure that connect them, along with any companion that supplies part of the surface's contract. A surface stands on its own when a reader can recover its subject, scope, status, and reading path from the surface and the subject it describes. Project records, private conversation, and author memory are not part of that explanation.

The `doc/` directory defines the documentation system: how documentation carries meaning, takes shape, uses language, and is judged. It does not define the meaning of a particular subsystem; the smallest subject that owns a claim does that. Start from the subject's local `README.md` and use these standards to decide how its documentation should work.

Documentation quality belongs to the complete surface, not to a change record or an authoring process. A surface must give its intended readers enough meaning, scope, status, and path to understand and use the subject without reconstructing missing context. These standards judge documentation as documentation, not the change that introduced it.

Documentation must be clearly correct. It must accurately describe its subject within its stated scope and status, and its intended readers must be able to find, understand, and use the information. These conditions belong together, but neither guarantees the other. [Quality](quality/README.md) explains how to judge them across the complete surface.

The [manifesto's three aims](../manifesto.md) guide these standards:

- **Ergonomics:** give readers a short, understandable path.
- **Determinism:** make meaning, status, and links predictable.
- **Efficiency:** carry the needed information without avoidable reading or maintenance work.

The aims improve the documentation system. They do not replace accuracy, understandability, or usability, and they do not make unclear or inaccurate documentation acceptable.

## Meaning

[Meaning](meaning/README.md) describes the claims, concepts, relationships, and notation that documentation carries.

## Structure

[Structure](structure/README.md) describes where documentation lives and how readers move through files, sections, links, and companions.

## Style

[Style](style/README.md) describes how documentation expresses its meaning clearly and consistently.

## Quality

[Quality](quality/README.md) judges a complete documentation surface for accuracy, reader use, and the applicable standards. Its evidence comes from mechanical checks, reader trials, and independent review where those methods add useful information.
