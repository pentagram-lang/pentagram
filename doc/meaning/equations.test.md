# Tests

## Build an equation set for a stack

**Task**

Treat the following model as accepted input, not as an implementation description. The model defines finite `stack` values from `empty-stack` and `push(stack, item)`. `stack-size` observes the number of items. `pop-outcome` observes either `no-item` or `popped(item)`, and `stack-after-pop` observes the resulting stack. Popping `empty-stack` returns `no-item` without changing the stack. Popping a stack built by `push` returns its last item and the preceding stack.

Draft the exact equation documentation needed to govern `stack-size`, `pop-outcome`, and `stack-after-pop`. Identify root and derived equations, keep domains and conditions clear, and derive the size of a stack after pushing `first` and then `second` onto `empty-stack`.

**Assert**

- The answer states the model boundary, accepted domains, mappings, conditions, and claim status needed to interpret the equations.
- Root equations cover the size base case and recursive push case.
- Root equations cover both the empty-pop failure and successful-pop outcome and resulting stack.
- The answer labels the two-push result as derived and shows an inspectable derivation to size `2`.
- The answer does not treat equality as evaluation order or mathematical notation as authority or evidence.
- The answer uses descriptive Pentagram-compatible identifiers and readable plain-text equation blocks.
- The answer cites the equations document or visibly applies its definitions, notation, root-basis, and derivation guidance.

## Challenge an inadequate equation set

**Task**

Treat the following model as accepted input, not as an implementation description. The model says `deduplicate(items)` returns the first occurrence of each distinct item in original order. One proposed governing equation is:

```text
item-count(deduplicate(items)) <= item-count(items)
```

The system has a simple implementation and a performance-oriented implementation that uses an index and cache. Judge whether the proposed equation is adequate for the model. Explain what must be repaired, which implementation differences should remain free, and how semantic and resource obligations should be checked.

**Assert**

- The answer finds that the inequality is necessary at most but cannot distinguish every model-forbidden result.
- The answer identifies the missing model observations or relationships needed to express distinctness, first occurrence, membership, and order rather than inventing implementation steps.
- The answer repairs the root basis or governing model instead of adding an unsupported derived equation.
- The answer permits indexing, caching, representation, and algorithm differences when model observations remain satisfied.
- The answer keeps semantic equations separate from resource equations and their measurement conditions.
- The answer allows root or derived equations to provide the clearest implementation and test checks while tracing them to the root basis.
- The answer cites the equations document or visibly uses its adequacy and implementation-conformance guidance.
