# Claims

Within [meaning](README.md), a claim is one proposition that documentation asks a reader to understand or rely on. The claims document defines how to make that proposition inspectable; it does not catalogue every subject documentation can discuss.

[Models](models.md) governs the concepts and relationships that make claims form a coherent system. [Equations](equations.md) gives selected claims an exact mathematical form and distinguishes root equations from derived equations. Local documentation decides which claims its subject requires.

Clear claims embody Pentagram's aims. They are easy to understand and change, their interpretation follows from explicit conditions, and one well-formed claim can support reading, implementation, tests, and later decisions without repeated reconstruction.

## Write one assessable proposition

State the subject, what is asserted about that subject, and any condition that changes the assertion. Split a sentence when its parts have different scope, status, authority, or evidence. A reviewer should be able to ask what would confirm or contradict the claim.

Give a consequential claim the details needed to assess it. A behaviour claim identifies the observer, conditions, and result. A requirement identifies the responsible actor and obligation. An invariant identifies the domain in which it holds. A resource claim identifies the operation, input scale, resource, conditions, and kind of bound. A contract is a bounded set of such claims.

Use labels, identifiers, or metadata only when consequence, reuse, or traceability repays their maintenance cost.

## State kind, status, and scope

Make clear whether a claim is a definition, fact, requirement, recommendation, aspiration, proposal, rationale, or example. An example presents one instance; it does not establish the whole rule.

For a descriptive claim, distinguish established fact, inference, conflict, and unknown. For a requirement, distinguish proposed and accepted authority, and track implementation conformance separately. Present current behaviour, current requirements, and current aspirations or proposals with distinct force.

State the smallest complete scope in which the claim applies. Name relevant versions, environments, actors, inputs, modes, times, and preconditions when they affect the conclusion. Silence does not establish permission, prohibition, compatibility, or a default.

Keep each claim about the subject the document governs. Do not present the current project, conversation, draft, or session as part of another subject. Project records may describe current project state because the project is their subject.

## Give each governing claim one authority

Pentagram documentation is the primary semantic authority for the systems it governs. Give each governing claim one owning document at the smallest scope where the claim is fully true. A shared claim belongs to the system or interface that defines it, not to whichever consumer describes it first.

Every governing claim must be current for its declared scope. If active claims compete within that scope, the governed design is incoherent. Repair the design until the claims can be made jointly true or one claim governs; do not preserve the conflict as parallel documentation authorities.

Use repository history for former claims and change history. Do not carry either in current claim text.

Delegate authority with a direct link and words that name the relationship. Dependent documentation can repeat the local consequence needed for correct use, but it must not create another apparent definition. Formal tone, repetition, code, and tests do not silently acquire semantic authority.

Prefer one governing basis to repeated independent claims. When a proposition follows from that basis, identify it as derived and preserve a direct path to its premises rather than restating the proposition as another authority. The derived proposition draws its authority from those premises. A change to the basis requires reconciliation of every dependent conclusion.

A derived proposition inherits every limiting condition and scope from its premises and cannot have stronger authority than the premises support. A proposed or unestablished premise remains visible as a condition on the conclusion; derivation cannot turn that premise into unconditional accepted authority. The derived proposition can have a different claim kind. For example, definitions can support a derived fact or law. State claim kind separately from authority.

## Relate evidence without confusing it for authority

Evidence supports or challenges a factual claim, shows whether implementation conforms, or tests whether a requirement produces its intended result. Evidence does not decide which claim governs.

A derivation shows that a conclusion follows from stated premises. It does not establish that the premises are true, authoritative, or appropriate for the system. Keep logical dependence and supporting evidence distinct so a valid derivation cannot conceal a defective premise.

Use the most direct evidence available and state the conditions needed to interpret it. Distinguish established results from inference, and expose contradictory or inconclusive evidence instead of smoothing disagreement into confident prose.

## State system condition directly

A benefit names a property to preserve, the conditions that produce it, and the consequence that matters. A deficiency names a current gap, its scope and consequence, and the needed repair when known. A conflict names claims or evidence that cannot all be accepted. An unknown states the open question, why the answer matters, and what could resolve it.

Do not turn benefits into praise, deficiencies into blame, or unknowns into guesses. Distinguish an unknown from an assumption, estimate, intentionally unspecified behaviour, and missing support.
