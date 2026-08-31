# Documentation standards

[Pentagram](../README.md) makes meaning durable through documentation. Code embodies an implementation; documentation states what the system means, what readers can rely on, and how its parts fit together.

Pentagram calls this **documentation primacy**: the documented meaning of a system is the primary authority for its design, implementation, and evaluation.

Code without governing documentation has broken semantic authority. Incorrect, unclear, or unusable documentation breaks that authority too. All code therefore requires correct, high-quality documentation, with each governing claim placed at the smallest scope where it is fully true.

`doc/` defines the shared standards for producing those documents. It is not a warehouse for every subject. Documentation stays beside what it governs; this directory defines the common principles that make those local documents work together.

Each local documentation surface begins with a `README.md`. It provides key orientation and navigation. Authors extend the surface by linking more detailed documents from that entry point as needed.

Pentagram's documentation standards are based on [ergonomics, determinism, and efficiency](../manifesto.md). They must embody each applicable aim in their own design and support that aim across Pentagram.

| Aim             | Embody in documentation standards                                              | Support across Pentagram                                                                                        |
| --------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| **Ergonomics**  | Make the standards natural to read, apply, and edit.                           | Make documented systems easier to discover, learn, use, change, and recover.                                    |
| **Determinism** | Make the standards' scope, authority, and edit impact predictable.             | State system semantics so implementation and tests can realize them and be validated against the documentation. |
| **Efficiency**  | Avoid unnecessary work in understanding, applying, and changing the standards. | Document resource contracts, benefits to preserve, deficiencies to repair, and unknowns to investigate.         |

A design choice can make documentation easier to read but harder to maintain, or easier to edit but harder to understand. Avoid that trade-off where possible. When it remains, prioritize reader comprehension, correct action, and safety over authoring convenience.

Documentation also shapes the repository environment by changing what readers notice, believe, and do. [Environment engineering](../env/README.md) governs how documentation works with code to produce those combined effects. Every document must account for its environmental effects; environment-specific evidence, testing, and review scale with environmental risk and leverage.

## Meaning

[Meaning](meaning/README.md) establishes what documentation says and what readers can rely on. It makes benefits, deficiencies, unknowns, semantics, contracts, and resource behaviour explicit enough to guide understanding, implementation, and evidence.

## Structure

[Structure](structure/README.md) arranges documentation into recursive hierarchies, ordered nodes, and links, and defines formats whose structure carries domain-specific meaning. It keeps authority local, paths usable, structural change predictable, and machine interpretation explicit where needed.

## Style

[Style](style/README.md) carries meaning with minimal cognitive friction and stable interpretation. It defines Pentagram's house voice and keeps terminology coherent across documentation and the systems it describes.

## Quality

[Quality](quality/README.md) evaluates whether documentation embodies and supports the Pentagram aims. It combines criteria, lint, test, and review without mistaking any one kind of evidence for proof.
