# Quality

Within [documentation standards](../README.md), documentation quality is a judgement about a complete documentation surface, not about isolated sentences. The surface must accurately describe its subject for its stated scope and status, and its intended readers must be able to find, understand, and use the information. If either part fails, the documentation is not clearly correct.

Quality works with the other documentation pillars. [Meaning](../meaning/README.md) establishes what documents claim and what concepts denote. [Structure](../structure/README.md) arranges content into an interpretable hierarchy with clear paths and boundaries. [Style](../style/README.md) governs how documented meaning is expressed in prose, source, examples, diagrams, and names. Quality evaluates whether the complete documentation surface satisfies all three pillars together, verifying that accurate claims are not obscured by fractured structure or impenetrable expression.

Quality is the mechanism that demonstrates clear correctness. Satisfying an individual pillar in isolation does not guarantee that documentation works; an accurate statement fails when readers cannot locate it, a clean hierarchy fails when its content is inaccurate, and polished prose cannot rescue misleading claims. [Criteria](criteria.md) judges documentation across its complete surface and reading paths, using bounded evidence to establish that documentation faithfully describes its subject and serves its intended reader use.

Quality must embody and support the aims defined in the [Pentagram manifesto](../../manifesto.md). Ergonomic quality provides immediate feedback during authoring and produces actionable inspection findings that pinpoint deficiencies without ambiguity. Deterministic quality makes verification repeatable through explicit lint rules, structured reader trial protocols, and transparent review checklists. Efficient quality bounds verification effort by applying automated mechanical checks before investing contributor time in reader trials and multi-party reviews.

## Criteria

[Criteria](criteria.md) explains what to judge across meaning, structure, style, and the complete surface, and how to report pass, fail, or inconclusive evidence.

## Lint

[Lint](lint.md) defines the mechanical checks for headings, links, indexes, companions, formatting, and final commit messages.

## Test

[Test](test.md) defines independent reader trials, their contracts, and the limits of what a trial can establish.

## Review

[Review](review/README.md) defines independent inspection, findings, evaluation, repair, and re-review for documentation.
