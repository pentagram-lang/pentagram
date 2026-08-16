# Terminology

Within [style](README.md), names are interfaces to concepts. A stable name lets documentation, code, interfaces, diagnostics, logs, tests, tools, and conversation refer to the same concept without mental translation. Naming drift often reveals model drift.

Terminology governs names, not the concepts themselves. [Meaning](../meaning/README.md) owns definitions and distinctions. Terminology keeps the chosen vocabulary clear, stable, and composable across system surfaces.

Terminology applies the aims defined in the [Pentagram manifesto](../../manifesto.md). Ergonomic terminology makes names understandable to readers and straightforward for authors to apply. Deterministic terminology makes meaning, scope, and mappings explicit wherever ambiguity could change understanding or behaviour. Efficient terminology avoids synonym translation, repeated explanation, failed searches, and unnecessary rename work. Across Pentagram, stable terms expose the system model and keep documentation, implementation, tests, diagnostics, and tools aligned.

This guide sets repository-wide defaults. Define specialized vocabulary beside the subject it governs, at the smallest scope where the definition is fully true.

## Keep one name for one concept

Use the same term for the same concept within a scope. Do not rotate through synonyms for variety: technical prose gains rhythm from its sentences, not from renaming its subjects.

If two terms name different concepts, define the distinction and their relationship. If they name the same concept, choose one. When a public name differs from an internal identifier, document the mapping instead of pretending the difference does not exist.

Prefer plain language when it is equally exact. Keep a specialized term when it carries a necessary distinction; explain it for readers who may not know it.

## Define terms where they belong

A useful terminology record identifies the preferred term, scope, governing definition, and distinctions a reader could otherwise miss. Record forbidden or deprecated synonyms and surface mappings when they prevent ambiguity. Add examples and non-examples when they make the concept boundary clearer.

Place the terminology record beside its governing model. A local vocabulary may refine a broad idea, but it must not silently redefine a shared term. Link to the governing definition instead of maintaining a competing glossary entry.

## Map names across surfaces

One concept may have a prose term, a source identifier, a syntactic form, a serialized value, or an established external name. Prefer the same recognizable name where the constraints of each surface allow. When forms must differ, document the mapping at the smallest scope that contains the difference.

A mapping names the preferred term, each surface form, and the reason for the difference. Add translation direction, version, compatibility status, and removal conditions when they matter. A mapped alias does not become a second preferred term.

Do not normalize away a real conceptual distinction. If similar names refer to different concepts, define the boundary and relationship. If the same name refers to different concepts in separate scopes, make the scope visible where confusion could occur.

## Preserve proper nouns

The repository-owned proper nouns are:

- **Pentagram**

External proper nouns keep their established capitalization. Document names are not proper nouns; [house style: use sentence case](house.md#use-sentence-case) governs their capitalization and references.

## Preserve Pentagram's shared terms

The Pentagram manifesto names three connected aims: **ergonomics**, **determinism**, and **efficiency**. Keep those names when referring to the aims. Related words such as clarity, predictability, and performance do not replace them. The manifesto owns their full meaning and aspirational status.

## Use repository roles precisely

Use the role that matters to the claim:

- An **operator** is a human interacting directly with an agent.
- A **contributor** is an internal Pentagram developer.
- A **developer** is the default term for any other developer.
- An **agent** is any LLM AI, including one acting as a developer or contributor.
- A **reader** is any human or agent interpreting repository text.

Do not use **user** or **person** as a fallback role. When the human-agent distinction matters, say **human** or **agent**. Otherwise name the relevant role—such as reader, programmer, maintainer, or reviewer—with a term that applies to both humans and agents.

When a human's pronouns are unstated, use **they/them**. Do not infer pronouns from a name.

## Use Canadian English

Repository prose uses Canadian English by default. Preserve the exact spelling of identifiers, syntax, commands, quoted text, upstream names, and established external terminology.

A local surface may follow another language convention when its audience or governing standard requires one. State the exception where authors will encounter it.

## Keep abbreviations useful

Define an abbreviation on first use when the intended reader may not know it. Leave a familiar abbreviation unexplained when spelling it out would add no understanding, and prefer the full term when an abbreviation would save little.

Do not coin an acronym merely to shorten a phrase. An abbreviation should reduce repeated work without giving the reader another vocabulary to memorize.

## Change terms deliberately

A terminology change is a system change, not a prose substitution. Start from the concept rather than searching for one spelling.

Build an impact inventory before changing dependent uses. Check every applicable category:

- governing definitions, local documentation, examples, diagrams, and navigation;
- language syntax, public interfaces, user interfaces, and commands;
- source-code identifiers, schemas, configuration, protocols, storage, and serialized forms;
- diagnostics, logs, metrics, traces, and other operational output;
- tests, fixtures, snapshots, and generated artifacts;
- compilers, formatters, generators, linters, editors, search indexes, and other tools; and
- migration, release, support, mixed-version, and compatibility material.

The inventory follows conceptual dependencies as well as textual matches. A different spelling can refer to the same concept, and the same spelling can refer to unrelated concepts.

Preserve old-to-new mappings wherever existing readers, callers, stored data, or tools must continue to work. State which forms are accepted and emitted, the mapping's scope and version, and any removal condition. Compatibility does not make both names preferred.

Update the governing definition and any canonical terminology record before dependent uses. Then update every affected surface in the inventory. Do not rely on blind replacement: a terminology change may require model, interface, migration, diagnostic, or test changes beyond the words themselves.

Validate conceptual agreement, not only spelling. Readers must encounter the canonical name and an accurate model; implementation and tests must encode the same boundary; diagnostics and tools must emit or recognize the intended forms; and compatibility cases must exercise preserved mappings. Account for every remaining old term as a current mapping, a preserved historical or quoted use, an external name, or a defect.
