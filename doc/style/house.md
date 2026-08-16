# House style

Within [style](README.md), writing is part of the interface. If a reader must untangle the prose before they can reason about the system, the documentation has moved complexity instead of removing it.

House style applies Pentagram's aims to expression. Ergonomic writing follows the reader's thought and remains workable in source. Deterministic writing makes interpretation follow predictably from explicit words and context. Efficient writing carries every needed distinction without unnecessary reading, translation, formatting, or editing work.

Pentagram writing is direct, alive, and exact. It can carry a real voice and still be technical. The [Pentagram manifesto](../../manifesto.md) is an authoritative example: it makes strong claims in clear language, uses contrast and rhythm to make ideas memorable, and states plainly that its aspirations are not current behaviour.

House style governs expression. [Meaning](../meaning/README.md) establishes what the document says, [structure](../structure/README.md) gives it a home, and [quality](../quality/README.md) asks whether it works. The rules here are shared defaults, not a demand that every document sound the same.

## Lead to use

Begin with the reader's next need. Make the understanding, decision, or action the document supports easy to see and easy to reach.

An entry point says what the subject is and where to continue. A decision document states the decision. A procedure states its outcome and prerequisites. A recovery guide exposes immediate danger. A reference gets to exact facts without forcing the reader through a story.

Do not lead with the author's history, the implementation chronology, or everything known about the subject. Lead with use.

## Follow the thought

Information should arrive in the order needed to reason about it.

- Put conditions before the actions they govern.
- Put warnings immediately before risky or irreversible steps.
- State a decision before its rationale when the reader must act on it.
- Establish a model before details that depend on it.
- Keep causes near effects, rules near exceptions, and actions near expected results.

Give each paragraph one movement of thought. Open with the fact or relationship that makes the rest intelligible.

Chronology is useful when chronology is the subject: a state transition, incident timeline, or migration sequence. Elsewhere, it usually records discovery instead of explaining the system.

## Use a real voice

Write like an author who understands the subject and respects the reader. Be confident where authority and evidence support confidence. Name uncertainty where they do not.

The house voice is not one fixed tone. A specification is exact and restrained. A recovery procedure is calm and firm. An explanation can be warm and conversational. A manifesto can be forceful, rhythmic, and metaphorical. They belong to the same house because each makes its thought clear.

Do not confuse neutrality with rigour. Strong language can sharpen a real distinction. It must not hide conditions, manufacture authority, or replace an argument. Avoid marketing language, condescension, and claims about what a reader should find easy or obvious.

## Build clean sentences

Name the actor when responsibility or behaviour depends on it. Prefer concrete verbs to abstract noun phrases. Write “the scheduler retries the job,” not “job retry behaviour occurs.” Use passive voice when the actor is genuinely irrelevant or unknown, not when it would conceal ownership.

Keep conditions, modifiers, and exceptions close to what they govern.

Use pronouns and demonstratives such as “it,” “this,” “that,” “these,” and “those” only when their referent is immediate and unmistakable. In long sentences or paragraphs, repeat the specific noun instead.

## Use sentence case

Use sentence case for every repository-owned heading and text interface. Capitalize the first word and proper nouns. Preserve exact capitalization when required by an identifier, command, syntax, quotation, or established external term. [Terminology](terminology.md) records repository-owned proper nouns. Do not use title case to signal hierarchy, importance, or interface identity.

A text interface is wording presented to readers as part of a repository-owned tool or structured surface. Labels, prompts, help text, status and error messages, diagnostics, and report fields are text interfaces. Apply sentence case to complete sentences and fragments alike.

Title case quietly increases the number of apparent names in a system. In documentation, every title-cased heading or document name can look like another special identity that readers must remember and rank. In text interfaces, title-cased labels and fields make every element compete for attention. Sentence case keeps capitalization meaningful: proper names and exact forms remain visible, while structure, wording, position, and deliberate emphasis show hierarchy and importance.

Document names are not proper nouns. Their headings and references follow sentence case. For example, write `# House style` as the heading and “the house style” in ordinary prose rather than preserving the heading's initial capital.

A link already marks a linked document reference. An unlinked reference to a document needs no marker when its wording or context clearly identifies the reference as a document; bold remains available for rhetorical effect. When an unlinked reference could be read as ordinary prose, identify it with a textual marker such as “document,” bold styling, or both: for example, “the claims document,” “the **claims**,” or “the **claims document**.”

## Keep source workable

A document must work as rendered text for its readers and as editable source for its authors. Design both surfaces before accepting a trade-off. If the trade-off remains, protect reader comprehension, correct action, and safety.

Keep source order close to reading order. Prefer ordinary Markdown to raw HTML, manual spacing, and layout tricks. Let formatters own mechanical layout instead of creating hand-aligned source that breaks under editing.

Make common edits local and predictable. A useful edit should produce a focused, intelligible diff rather than unrelated reflow or repeated maintenance elsewhere. Use authoring conventions and automation when they reduce total work without weakening the rendered result.

## Be exact, then stop

Use specific nouns, concrete verbs, and explicit boundaries. Name relevant versions, units, quantities, states, permissions, timing, and failure conditions. Distinguish capability from permission, possibility from guarantee, and current behaviour from intended behaviour.

Concision is the smallest complete expression, not the fewest words. Concision is not density. Prefer several clear sentences to one sentence that makes the reader unpack several relationships. Cut repetition, filler, and indirect phrasing. Keep every detail that changes meaning, safety, compatibility, recovery, or the reader's decision.

Words such as “simply,” “obviously,” “just,” and “easy” describe the author's experience, not the system. Replace reassurance with the real prerequisites, steps, constraints, or evidence.

## Make claims legible

A sentence should reveal what kind of [claim](../meaning/claims.md) it makes. Facts state what is true for a named scope. Requirements name the responsible actor and condition. Recommendations leave room for a justified exception. Rationale explains why. Examples illustrate without quietly becoming the whole contract.

Do not present a proposal or aspiration as current fact. Formal tone, bold type, and capital letters do not create authority. If a document adopts specialized normative keywords, it must define or link to their exact force and use them consistently.

Resource claims must be inspectable. Name the operation, input scale, resource, relevant bound or unit, and applicable conditions. Distinguish a contract from a target, design expectation, measurement, estimate, and unknown. A measurement names the workload and the runtime, hardware, cache state, and other conditions needed to interpret the result. Do not substitute “fast,” “small,” or “efficient” for a specific claim.

Phrase semantic and resource claims so their actors, inputs, conditions, outputs, effects, failures, and bounds map cleanly to implementation and tests. Explicit claim expression makes translation and validation inspectable; style does not establish the governing semantics or provide the evidence used for validation.

## Make system status legible

A benefit names the property to preserve, the conditions that produce it, and the consequence that matters. A deficiency names the current gap, its scope, and its consequence; name the needed repair when known. An unknown states what is not established instead of turning uncertainty into praise, criticism, or a guessed fact.

Distinguish missing facts, assumptions, estimates, unresolved decisions, conflicting evidence, and intentionally unspecified behaviour. Never blend disagreement into plausible prose.

When uncertainty matters, name what could resolve the uncertainty and how an incorrect understanding would affect the system or decision. Do not hedge facts that are established for their stated scope. Honesty means expressing both confidence and doubt at their proper strength.

## Show the system

Technical writing is more than prose. Use the form that makes the relevant relationship easiest to see: prose for causes, lists for parallel items, tables for regular dimensions, diagrams for flows or boundaries, examples for concrete behaviour, and formal notation when its precision earns the cost of learning it. A list or table should expose structure rather than hide the relationships among its entries.

Keep examples small enough to expose the idea and real enough to reveal names, states, defaults, and consequences. State assumptions and placeholders. Show the expected result. Add invalid, boundary, or recovery cases when they change understanding.

A diagram should name its question and level of abstraction. Essential information must remain searchable, reviewable, and available without relying on visual styling or a screenshot alone.

## Write useful links

Link text should tell readers where the link leads. For a whole document, use a recognizable form of the document title with capitalization that fits the sentence. For a section in another document, name both the document and the section unless the immediate context has already named the document. A section heading alone is sufficient for a link within the current document.

Descriptive link text is permitted for rhetorical effect when the description still identifies the target honestly. Avoid generic link text such as “here,” “this page,” or “learn more.”

Within one document, use the same link text for each resolved target, including its fragment. Links to different fragments are different targets.

The surrounding sentence should explain the relationship between the current text and the target: navigation, definition, authority, prerequisite, rationale, or evidence. A link must not make readers guess why the target matters, and it must not replace a condition, warning, or consequence needed locally.

## Keep style local

House style is a common voice, not a voice flattened into uniformity. A local documentation surface can choose the tone, density, or notation that best serves its subject and reader.

Keep a local convention at the smallest scope where it helps. It cannot silently change shared terminology, claim authority, or notation. Prefer a clear local exception over weakening a useful global rule, and remove the exception when its reason disappears.
