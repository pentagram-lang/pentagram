# Equations

Within [meaning](README.md), an equation is an exact mathematical statement relating expressions under declared conditions. It may assert an equality, an inequality, or another named relation. Pentagram documentation uses equation as the generic term for all three forms. An equation does not prescribe an implementation or execute from left to right.

[Claims](claims.md) governs the status, scope, authority, and evidence of every equation. [Models](models.md) owns the questions, system concepts, and contractual distinctions that equations express. The equations document refers to the governing model when declaring mathematical names, domains, mappings, and local notation. It gives selected claims an exact form and builds answers from a small governing basis.

Equations have two roles in an equation set. A root equation is stated independently. A derived equation follows from root equations, earlier derived equations, and stated mathematics. A derivation is the reasoning that produces a derived equation or another answer. A model question can be answered by a stated equation or by a reader performing a derivation.

The equations document applies the aims of the [Pentagram manifesto](../../manifesto.md) to precise expression. Small, familiar notation reduces reading and editing friction. Explicit variables and conditions make conclusions predictable. Reusable relationships reduce repeated explanation and give implementation and tests a shared contract without imposing unnecessary formal machinery.

## Use equations where precision matters

Use an equation when readers need to calculate a result, derive an unfamiliar case, compare implementations, check preservation, or verify a bound. Prefer prose when mathematical notation would merely restate a claim that is already unambiguous.

An equation needs the same context as any other consequential claim. Name the system and boundary, define its terms, state its conditions and scope, and distinguish a requirement from a fact, proposal, or example. Mathematical form does not create authority or evidence.

Use the smallest equation set that can answer the required questions directly or through derivation. Do not formalize incidental implementation detail, duplicate a consequence as another independent rule, or add notation merely to make a document appear rigorous.

## Use mathematical notation

Equation blocks use a small plain-text mathematical notation. They are not Pentagram source code.

Write mathematical function application as a name followed by a parenthesized, comma-separated argument list. Parenthesized application distinguishes the notation from Pentagram's postfix function calls. Use `=`, `!=`, `<`, `<=`, `>`, and `>=` for their ordinary mathematical relations. Use `+`, `-`, `*`, and `/` for ordinary arithmetic. Write logical relationships with the words `and`, `or`, `not`, and `iff` when words are easier to read and type than specialized symbols.

**Running example.** The examples below use a small item model. Every `items` value is a finite sequence generated from `empty-items` by `add-item`; `add-item` puts an accepted `item` at the end of a sequence; and `item-count` returns the number of items in a sequence. These names and assumptions belong only to the running example. Governing documentation must use the documented system's actual terms and boundaries.

Use lowercase Pentagram identifiers and join multiple words with hyphens. Preserve an exact repository-owned identifier when a mathematical name refers to that identifier. Do not introduce subscripts, primes, Greek letters, or single-letter abbreviations when a descriptive Pentagram identifier remains practical.

Keep the Markdown source readable without rendering. Use fenced `text` blocks, break an equation after a complete mathematical expression, and indent continuations by two spaces. Do not align distant operators with manual spacing or duplicate one equation in plain-text and rendered forms.

Introduce additional notation only when repeated use repays its learning, typing, searching, and editing cost. Define the notation immediately before its first use and keep its meaning stable within the documentation surface.

## Define every name and domain

Introduce each mathematical function, variable, value, and collection before using it. Use or link to the governing model's concept definitions instead of replacing them with generic mathematical vocabulary or creating competing definitions.

State the mathematical domain over which each variable ranges by reference to the governing model. Define local notation and mappings between mathematical names and system concepts, together with every restriction needed to interpret the equation. The equation uses those definitions; it does not establish the model's concepts by itself.

The running example's model therefore defines how `items` values are formed, what `item` can denote, and what `item-count` observes before using those names in an equation.

Distinguish mathematical names from repository identifiers when they differ. State the mapping once at the smallest scope that contains both, then use each name consistently for its own role.

## Keep conditions with the equation

State quantifiers and preconditions immediately before the equation. Prefer direct prose to compressed notation.

In the running example, suppose `remove-last` accepts every supported sequence and `items-after-remove-last` observes the resulting sequence. Its item-count relationship applies only when the starting sequence is non-empty, so keep that condition immediately before the equation:

> For every non-empty `items`:

```text
item-count(items-after-remove-last(items)) = item-count(items) - 1
```

The condition applies only to this equation. Separating the condition would make the equation appear to cover `empty-items`.

Name exceptional and unsupported inputs instead of allowing a reader to infer that an equation is universal. When failure is part of the contract, include the result that represents the failure or give the failure behaviour its own adjacent claim.

A family of equations may share a condition only when the shared scope is unmistakable. Repeat a condition when separating it would make an equation unsafe or misleading to reuse.

## Use equality only for equality

The relation `left = right` claims that both expressions have the same mathematical value. Equality is symmetric; the written order does not specify data flow, evaluation order, rewriting direction, or implementation sequence.

Use a named function or relation when the contract is directional. Use an inequality for a bound, and state whether the bound is required, expected, estimated, or measured. The surrounding claim must define the operation, measurement boundary, units, supported inputs, and other applicable conditions.

For a resource view of the running example, suppose `storage-use` reports bytes under a defined representation and measurement boundary, `base-storage` is a fixed byte allowance, and `storage-per-item` is the byte allowance for each item. A required linear storage bound can then be written:

```text
storage-use(items)
<= base-storage + item-count(items) * storage-per-item
```

These resource names and conditions extend only the running example. The inequality is a requirement only when its surrounding claim gives it that status.

Do not use equality when the contract permits approximation, refinement, several valid results, or only matching observations. Name the actual relation and define it before use. Familiar symbols do not repair a relation that the model has left unclear.

## Build from root equations

Root equations provide the independent basis of an equation set. [Claims](claims.md) determines whether a root equation is a definition, requirement, fact, proposal, example, or another kind of claim. Use root equations for base cases, primitive operations, composition or transition rules, resource bounds, and other claims that need an independent basis.

The running example uses two root equations to define `item-count` over its entire domain:

```text
item-count(empty-items) = 0

item-count(add-item(items, item)) = item-count(items) + 1
```

The first root equation covers the base form. The second explains a compound through its immediate part.

The running model can also describe the failure and state change of `remove-last`. Extend the operation above with `remove-last-outcome`, which observes either the failure `no-item` or the success `removed(item)`. These root equations define both the outcome and resulting sequence for every input:

```text
remove-last-outcome(empty-items) = no-item
items-after-remove-last(empty-items) = empty-items

remove-last-outcome(add-item(items, item)) = removed(item)
items-after-remove-last(add-item(items, item)) = items
```

The first pair covers failure without a state change. The second pair covers success and the resulting state. An equation about item count alone would establish neither the outcome nor the state transition.

Keep the set of root equations small enough to understand and sufficient to answer the declared questions. When one equation follows from the others, derive it instead of creating another apparent authority. Do not pursue a formally minimal basis when an additional root equation makes the system materially clearer or safer.

Prefer root equations that explain a compound through its immediate parts. Local equations let readers handle values of unfamiliar size and let implementations and tests reuse the same statement. When state, time, effects, failure, or external observations affect an answer, name those dependencies rather than hiding them behind a function that appears independent of context.

## Derive answers and laws

For every model question the equation set claims to settle, determine whether readers can find the answer in a stated equation or must derive it from the equation set. Make either route practical and verify every needed derivation. Each step in a derivation follows from a root equation, an earlier derived equation, or stated mathematics.

A useful equation set commonly permits indefinitely many derivations and derived equations. Do not try to document them all. Document a key derived equation and its derivation when the result answers an important question, prevents difficult reasoning from being repeated, exposes an obligation clearly, or provides a useful implementation or test check. Leave routine or one-time derivations unstated when readers can reconstruct them without needless difficulty.

Let `first` and `second` be any two values accepted by `add-item` in the running example. The root equations determine the count of the resulting sequence:

```text
item-count(add-item(add-item(empty-items, first), second))
= item-count(add-item(empty-items, first)) + 1
= item-count(empty-items) + 2
= 2
```

Show the reason for each non-obvious step and keep every condition used by the derivation visible. Name an intermediate result when several later derivations reuse it. Omit steps only when doing so cannot hide a condition or make the conclusion difficult to check.

A derived equation draws its authority from the root equations and earlier derived equations on which it depends rather than establishing an independent source. Keep the derivation with the conclusion or link directly to the equations and derivation that establish it. When a required answer cannot be derived, determine whether a root equation is missing, the model lacks a necessary concept, or the supposed requirement is false.

An equation can constrain an operation without defining it. Before treating an equation set as a definition, check that its root equations distinguish every result the model forbids.

For example, extend the running model with a `sort` operation that accepts and returns supported sequences. This equation says only that sorting preserves item count:

```text
item-count(sort(items)) = item-count(items)
```

Within this example, a `sort` implementation could return `items` unchanged, reversed, or rotated and still preserve the item count. This item-count equation therefore does not define the permitted result of `sort`. It is a derived equation only if other root equations in the example define which results `sort` permits and entail item-count preservation.

Derive commutativity, associativity, identity, idempotence, preservation, and other claimed laws from the governing model and root equations instead of inferring a law from a familiar operation name.

## Judge adequacy against the model

An equation set is adequate for its declared questions when it permits every outcome the governing model allows, rejects every outcome the model forbids, and leaves intentionally unobservable implementation choices unconstrained.

Judge adequacy using the root equations, documented derived equations, and further answers that can be derived from them. Root equations provide the independent basis, but a derived equation may be the clearest and most efficient way to answer a question, distinguish cases, expose a forbidden result, or check an implementation. A documented derivation must keep the derived equation's basis inspectable.

An equation set need not formalize every claim in a model. For each question the equation set claims to settle, apply this rubric:

| Test               | Review question                                                                                          |
| ------------------ | -------------------------------------------------------------------------------------------------------- |
| **Coverage**       | Can the equation set answer every assigned question directly or by derivation?                           |
| **Cases**          | Do applicable root or derived equations expose every case that can change an answer?                     |
| **Discrimination** | Does every model-forbidden answer conflict with an applicable root or derived equation?                  |
| **Freedom**        | Can implementations differ wherever the model intentionally leaves freedom?                              |
| **Consistency**    | Can the root equations be satisfied together, and are documented derived equations consistent with them? |
| **Derivation**     | Do documented derived equations and other answers follow without missing conditions or circularity?      |
| **Conformance**    | Can each implementation be checked with the equations that expose its obligations most clearly?          |
| **Traceability**   | Can each documented derivation, implementation check, and item of evidence be traced to root equations?  |

Challenge adequacy with counterexamples and deliberately wrong implementations. Use whichever applicable root or derived equation exposes a failure most clearly. If a model-forbidden answer satisfies every applicable equation, confirm that the model states the missing distinction, then repair the root equations. Adding a derived equation that does not follow from the roots does not repair their basis. If the model cannot state why the answer is wrong, repair the model first. If a valid performance-oriented implementation fails only because its machinery differs, the equation set constrains a distinction the model intended to leave free.

Adequacy is relative to an explicit boundary. It does not require equations about every physical fact or every question another model could ask.

## Apply equations to every implementation

Every implementation conforms by satisfying the applicable governing equations over their declared domains. An implementation designed for performance has the same semantic obligations as every other implementation. Representation, algorithm, data layout, caching, and execution order may differ only where the governing model leaves them free.

Write governing equations against the model's observations. Map each implementation operation to those observations when names or interfaces differ. Include implementation identity only when an equation varies by implementation, as resource use or another implementation-specific view may.

When equations cover several contractual views, give each view its own equations. Agreement in returned values does not establish agreement in effects, failures, order, timing, or resources. A resource equation does not replace the semantic equations, and semantic conformance does not establish a performance claim.

Suppose the running example has a performance-oriented implementation operation named `indexed-item-count`. Its semantic obligation applies to every supported sequence:

```text
indexed-item-count(items) = item-count(items)
```

The implementation may use an index, cache, different representation, or another algorithm without changing that obligation. If `indexed-item-count-work` reports defined work units under a fixed measurement boundary and `maximum-count-work` is a required upper bound, state the performance obligation separately:

```text
indexed-item-count-work(items) <= maximum-count-work
```

The first equation establishes agreement with the model. The second equation states an independent performance requirement. Neither equation implies the other.

Do not describe a performance-oriented implementation as a transformation unless the documented system actually transforms one program, plan, value, or representation into another. When a transformation is part of the system, state the exact observations it must preserve. Implementation choice and transformation correctness are separate obligations.

Tests can instantiate root and derived equations with selected or generated inputs. Deliberately wrong implementations test discrimination; structurally independent and performance-oriented implementations test freedom and conformance. A proof can establish an equation over its declared domain, and an executable reference can provide comparison evidence. None of these decides whether the equations state the right contract.

[Quality](../quality/README.md) governs how review, tests, proofs, and other evidence evaluate documentation and implementation. Keep mathematical names, variables, conditions, and equations recognizable across those surfaces so agreement remains inspectable without requiring identical syntax.

## Keep equations current

A governing equation states the current definition, fact, or obligation for its declared scope. When that equation changes, update it and reconcile dependent prose, examples, implementation, and evidence. Repository history preserves the former equation.

When a root equation changes, revisit every derived equation, derivation, and implementation obligation that depends on it. Do not preserve a former consequence as an independent equation merely because another document or test still expects it.

Equations that govern the same question and scope must be jointly satisfiable. If they are not, repair the documented model or system until the current root equations can be satisfied together.

Inspect both the equation and the governed design when the equation requires extensive exceptions, cannot be translated into a clear implementation obligation, or repeatedly produces surprising conclusions. More notation cannot repair a missing concept, unstable boundary, or contradictory contract.
