# Models

A model is a coherent account of the concepts and relationships needed to answer defined questions about a system. It identifies which distinctions change an answer and which variation the system leaves free. A model can expose structure, boundaries, state, or causality so readers can explain behaviour and predict unfamiliar cases.

[Meaning](README.md) uses models to create coherent understanding rather than collections of accurate fragments. [Claims](claims.md) governs the individual propositions a model contains; the models document governs how those propositions work together. A coherent model does not make its propositions true or authoritative. Each proposition still needs appropriate authority and evidence, while individually correct propositions can still form an incoherent model when their relationships are missing or contradictory.

The [Pentagram manifesto](../../manifesto.md) governs model design. Ergonomic models fit the reader's reasoning and remain useful across tasks. Deterministic models keep causes, effects, state, and boundaries explicit enough to support prediction. Efficient models let a small set of concepts explain many cases and expose the costs that matter without forcing readers through incidental implementation detail.

A model can use prose, tables, diagrams, examples, or formal notation. Choose the lightest form that makes the important relationships visible. No representation can replace a missing concept or repair incompatible claims.

## Define concepts and relationships

Begin with the smallest set of concepts that explains the system's important behaviour. Define what each concept is, what it is not, how identity works, and which distinctions change an outcome or decision. Use the exact names established by governing documentation and repository-owned identifiers. Distinguish domain concepts from implementation components, and state the mapping when a model includes both.

State relationships directly: ownership, containment, reference, dependency, cardinality, sequence, or another domain-specific relation. A list of nouns is an inventory, not a model. A relationship earns its place when it helps a reader infer behaviour, locate authority, or predict the consequence of change.

Use the same conceptual spine across orientation, tasks, reference, troubleshooting, implementation documentation, and tests. Different depths can omit detail, but they must not teach incompatible entities or relationships.

## Set system boundaries

Name the system being modelled, the environment around it, and the observers whose questions the model answers. State what lies inside the boundary, what remains external, and who owns the data, decisions, and effects that cross it.

A useful boundary separates contractual distinctions from replaceable mechanism. External documentation models the concepts, guarantees, states, and failures a developer can observe. State which observable differences change an answer and which differences readers cannot rely on. Internal documentation adds the causal depth needed to implement, change, operate, and diagnose those guarantees.

Shared use does not erase ownership. When several systems depend on one concept or contract, identify the interface or system that defines it and show how each participant relates to that owner.

## Make questions answerable

Name the questions the model is responsible for answering. Include the result, decision, change, failure, effect, resource use, or other observation only when the model needs that dimension. Group questions that depend on the same concepts instead of enumerating every scenario separately.

Build answers from a small basis of concepts and relationships. A reader should be able to vary an input, state, or condition and derive the new answer without consulting another isolated rule. Repeated exceptions and one-off answers are evidence that the model lacks a concept, distinction, or reusable relationship.

Use [equations](equations.md) when exact mathematical statements and derivations make those answers clearer. The models document owns the questions, system concepts, and contractual distinctions. The equations document refers to the governing model when declaring mathematical names, domains, mappings, and local notation. It states root equations, can record useful derived equations, and judges whether the equation set can answer the declared questions. If an equation needs an undefined concept, repair the model. If the equations cannot answer a question assigned to them, repair the equation set or the model question instead of hiding the mismatch between documents.

## Prefer functional models where accurate

A functional model describes a system as a mapping from explicit inputs to results. The mapping expresses the system's meaning, not necessarily one implementation function. State the inputs, results, and conditions under which the same inputs determine the same result.

Prefer a functional model to a procedural account when both are accurate. Explicit dependencies support local reasoning, substitution, composition, implementation, and testing without requiring readers to reconstruct an execution history. Failures can be part of the result, and external effects remain explicit at the boundary. The [equations](equations.md) document states functional relationships and their laws exactly when the additional precision is useful.

Do not hide state, time, identity, concurrency, or environmental dependence to make a model appear functional. Include a dependency as an input when that choice accurately describes the boundary; otherwise use a state or causal model. A false functional model destroys the reasoning benefits the form is meant to provide.

## Represent state and change

State is the set of facts about a system at a point in time that the model needs to answer its questions. Represent state only when behaviour depends on those facts. Use the system's actual concepts and names, and identify the observations that distinguish one relevant state from another.

Represent change by relating a starting state, an event or operation, and a resulting state. Include time, ordering, durability, intermediate states, and terminal states only when the relationship depends on them.

Do not force a lifecycle or state machine onto a subject that does not need one, and do not promote incidental implementation flags into conceptual states.

## Trace data flow and causality

Trace representative inputs from their source through the transformations, decisions, and effects that produce an observable result. Keep causes close to their consequences and distinguish a causal dependency from correlation, sequence, or physical proximity.

Make hidden control visible where it changes behaviour: ownership, authority, defaults, precedence, callbacks, retries, caches, clocks, scheduling, and external services. For concurrent or asynchronous systems, state which ordering and lifetime relationships are guaranteed and which remain unconstrained.

A causal model should support counterfactual questions. Readers should be able to ask what changes when an input, state, dependency, or failure differs and derive an answer without memorizing another isolated procedure.

## Record intent and rationale

Explain the problem the model addresses and why its central distinctions or boundaries exist. Connect a design choice to the constraint it answers and the consequence it produces. Preserve rejected alternatives when understanding them prevents the same failed design from returning.

Rationale explains the design; it does not replace current behaviour or grant authority to a proposal. Keep the governing contract clear even when the original reason is historical, disputed, or no longer sufficient.

Record the evidence or condition that could justify revisiting a decision. Do not turn the sequence in which ideas were discovered into the system's explanation.

## Expose assumptions and constraints

An assumption is a premise the model uses without establishing it. A constraint is a condition the system or design must accommodate. Name each consequential assumption or constraint, its source and scope, and what fails or changes if it does not hold.

Do not hide assumptions in defaults, examples, or convenient happy paths. State how an assumption can be checked and when it must be revisited. Distinguish a real external constraint from a current implementation limitation that the design could repair.

Composition depends on aligned premises. When a caller, dependency, runtime, or environment provides a required condition, make that relationship visible rather than letting each side assume the other owns it.

## Explain trade-offs and consequences

A trade-off connects a choice to the benefits it preserves, the costs it accepts, and the conditions under which that balance holds. Name who or what bears each consequence and whether the consequence appears during use, change, operation, or execution.

Evaluate choices against ergonomics, determinism, and efficiency together. Do not assume the aims conflict before trying to improve the design, and do not optimize one local surface by silently moving friction, uncertainty, or resource cost elsewhere.

Avoid universal “best practice” claims where the model establishes only a local decision. Record alternatives, accepted risks, and revisit conditions in enough detail for later contributors to reason from the decision rather than repeat the debate.

## Model failure and recovery

Failure belongs in the main model. Identify invalid and degraded states, the causes that can produce them, the signals that distinguish them, and how effects propagate or remain contained. Include partial completion, timeout, duplication, cancellation, and concurrent change where they alter recovery.

Describe recovery as a transition to a named safe state. State its prerequisites, effects, irreversible steps, evidence of completion, and whether repetition is safe. A command without its expected state and observation leaves the causal loop open.

Troubleshooting should reverse the same causal model that ordinary use follows forward. A growing collection of unrelated warnings and remedies often indicates a missing state, boundary, or causal relationship rather than a need for more caveats.

## Use examples and counterexamples

An example instantiates a declared model. Give the relevant starting state, input or action, resulting state or observation, and the principle the example demonstrates. A reader should be able to vary one condition and predict how the result changes.

Use counterexamples to expose a boundary, invalid interpretation, or tempting model that does not hold. Include failure and recovery cases when a happy-path example would otherwise teach false certainty.

Examples illustrate claims; they do not quietly become the only source of a rule. Make examples executable or mechanically checked when practical, and state the assumptions and limitations that the check does not establish.

## Separate views and abstraction levels

A view answers one class of questions at a named boundary and depth. Public and internal, logical and physical, semantic and operational, or static and runtime views can describe the same system without carrying the same detail.

Give each view its own questions and contractual distinctions. Agreement in one view does not establish agreement in another: two implementations can return the same result while differing in promised effects, failures, timing, or resource use. An implementation or transformation must satisfy every applicable view.

State how concepts correspond across views. External promises must follow from the deeper internal model, while internal mechanisms should be able to change beneath stable external concepts. A shallower view is an abstraction, not an incomplete copy with inconvenient details removed.

Do not blend current, aspirational, proposed, and historical systems into one apparent world. Do not mix abstraction levels inside one explanation when the shift would make an implementation detail look like a guarantee.

## Compose models across boundaries

Models compose when their concepts, identities, assumptions, and contracts align. Show how outputs become inputs, how ownership and authority cross the boundary, and how timing, ordering, consistency, errors, authorization, resources, and versions interact where relevant.

Each local model can be correct while their composition fails. A dependency can promise a thirty-second retry window that exceeds its caller's ten-second deadline; two components can use the same name for different identities; an external atomicity promise can lack an internal invariant that upholds it.

Keep one owner for each shared concept, identity, or contract and link dependent models to that authority. State the local consequence at every boundary where readers must act. Surface mismatched assumptions as design defects instead of adding translation folklore.

## State model limits

Every model omits detail. State which questions the model answers, which variation it intentionally ignores, and where its abstraction stops being reliable. Name uncertainty and unsupported cases instead of extending the model through implication.

For every declared question, readers must be able to find an answer, derive one from the model, or identify the question as unresolved or unsupported. Decide from the contract which variation is intentionally unobservable, not from what the current implementation happens to expose. Another view may make the distinction contractual.

Precision should reduce ambiguity, not create false certainty or apparatus more difficult than the subject. A useful model is the smallest account that supports the decisions, predictions, implementation, and validation required at its boundary.

Inspect the model and the governed design when readers repeatedly encounter surprises, caveat stacks, incompatible explanations, or behaviour that cannot be derived or tested. More prose cannot repair a missing concept, unstable boundary, or contradictory system. When the model changes, reconcile its dependent claims, examples, views, implementation, and evidence.
