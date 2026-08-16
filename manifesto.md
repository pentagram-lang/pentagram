# The Pentagram Manifesto — Aspirational Design

> **Status: Aspirational design**
>
> This document records Pentagram's intended principles and direction. It is not a description of the behaviour currently implemented in this repository. Treat its claims as design requirements under review and use tracked code, tests, and factual documentation to establish current behaviour.

## Background

### Modern perks

Programmers have never had more at their fingertips. Code is high level and has safety built in as a core feature. Toolchains are deep, runtimes are stable, ecosystems are vast. LLMs can summon code, patterns, and insights in ways that feel like science fiction finally arriving.

### Obtuse inevitability

And yet, stumbling blocks remain. Languages that are awkward to read and write, but whose champions call this “just how it must be.” Abstractions that add complexity, explained away as sophistication. Every keystroke of friction defended as inevitable -- laws of physics rather than a design failure.

### Persistent confusion

The foundation is twisted webs of shared, mutable state, enshrined as though object-orientation were some ideal. A religion so strong that it has become heresay to point out how this practice erodes clarity, eliminates reason, and leaves both humans and machines struggling in the dark.

### Cycle tax

Even the pursuit of speed is muddled. Real gains require endless tuning and ritual, while the base performance of programs wastes compute by default. Cycles are lost not to the substance of the work but to alternative priorities.

## Aspirations

### Reset

Language and culture are inseparable: the constructs of a language shape how programmers think, and the norms of the culture reinforce the language in turn. This feedback loop hardens over decades, making its flaws appear natural, even inevitable. Only a new language can break that loop. Only a recalibrated core can enable new goals, new practices, and a culture that embraces clarity, kindness, and power all at once.

### Ergonomics

Comfort and productivity in reading and writing code are not luxuries, but multipliers. A language should minimize friction: syntax should aid comprehension, not obscure it. Structures should support thought, not bend it. Ergonomics here means more than aesthetics -- it means designing with respect for human cognition and making programming feel natural, humane, and clear.

### Determinism

Confidence in correctness is what transforms code from a liability into an asset. By eliminating shared, mutable state from the foundation, a language can make programs predictable and reasoning straightforward. Determinism is not a constraint but a liberation: it frees programmers from the fog of hidden interactions and enables higher-level reasoning about algorithms, data structures, and systems — drawing computation closer to its mathematical roots. Both humans and machines can reason with confidence, guided by clarity that can only come from the composition of simple values.

### Efficiency

As for performance, saving CPU cycles should not require endless incantations or ritual optimization. A well-designed language ensures that programs run fast by default. This is not some abstract concern: baseline performance has real environmental impacts and directly affects the utility of programs written in the language.

## Design

### Typography

In Pentagram, everything begins at the keyboard. Symbols are chosen to type cleanly on most layouts without gymnastics. Common operations are given the shortest names, a kind of linguistic Huffman coding. Whitespace is fluid in editing (cleaned up in auto-formatting), with unambiguous fences defining overall program structure.

### Flow

Code flows in the order of thought. Postfix form is the default, so values read as they transform, with prefix mode available when multi-line expression trees are more clear. Records have sugar for scoped field-access functions, and functions are never bound to records. Type annotations use the same grammar as expressions, so code and its types share a single form of reasoning.

### Trust

Values are immutable. Full stop. Code reads as mutation, but this is actually lexical replacement. Actual side effects require function calls. Errors are always explicitly propagated or captured call sites. Exports are an easy opt-in, and escape hatches exist.

### Power

Types are nominal and strict, null is never implicit, and generics with higher-order traits enable advanced expressivity. Tagged unions are narrowed through plain conditionals rather than a separate pattern-matching sub-language.

### Runtime

Pure values are copy-on-write with compiler proofs to skip the copy, making safety fast. Concurrency is structured and green-threaded, with asynchronous operations allowed in any functions. Modern async IO (e.g. io_uring) is the only IO.

### Meta

All forms of regularity and predictability help humans learn and refactor, and help machines model and assist. The clarity that benefits people is the same clarity that strengthens automated tooling.

## Appendix: On Reasoning

Is it unreasonable to attempt ergonomics, determinism, and efficiency all together in one language? Only if you've forgotten what programming actually is. At its core, coding is reasoning—thinking clearly about what should happen and expressing that thought in executable form. Everything else—the syntax, the tooling, the frameworks—exists to serve that essential act of reasoning. When a language makes reasoning difficult, it's failing at its fundamental purpose. And right now, many languages actively fight reasoning: they obscure meaning with baroque notation, they favour inscrutable processes over mathematics, and they waste resources running programs no human or computer truly understands. The three values aren't ambitious luxuries—they're basic requirements that flow directly from taking reasoning seriously.

### Reasoning Ergonomics

Reasoning happens in minds—human minds, for now, though increasingly in collaboration with machine intelligence. If the notation fights comprehension, if common patterns require contortions, if the syntax adds cognitive load instead of reducing it, you're actively hindering the core activity. Ergonomics isn't about making programming "feel nice"—it's about removing obstacles between thought and expression. When code is hard to read, reasoning becomes hard to verify. When syntax is awkward to write, exploratory thinking gets abandoned before it reaches clarity. And here's what matters: the clarity that helps humans also strengthens automated tooling. LLMs, compilers, and analyzers all benefit from the same structural predictability and explicit semantics that make code comprehensible to people. A language designed for reasoning serves both intelligences, creating conditions where understanding compounds rather than fragments.

## Reaonsing Determinism

You cannot reason about systems where causes and effects are obscured. Shared mutable state creates action-at-a-distance that defeats local understanding—you read one piece of code, but its behaviour depends on distant mutations you can't see. Understanding becomes archaeology: tracing through layers of indirection, trying to reconstruct what might have changed and when. This isn't reasoning, it's detective work in a crime scene that's still active. Determinism means that understanding one piece gives you knowledge that stays true. When values are isolated and data flow is explicit, both human and machine intelligence can actually trace what happens. The compiler can prove optimizations safe. The programmer can refactor with confidence. The LLM can verify correctness. All three rely on the same foundation: that reading the code tells you what it does, completely and reliably.

## Reasoning Efficiency

Here's what we're actually running: programs no one fully understands, wrapped in layers of defensive code that exist only because reasoning was impossible. Redundant validation because state might have changed. Excessive logging because we can't trace what happened. Try-catch pyramids because errors could come from anywhere. Locks and synchronization overhead because mutation might happen concurrently. We're not just running slow code—we're executing confusion, burning cycles on runtime insurance policies that only exist because the language made reasoning impossible. When you can reason about code, this waste disappears. Errors are caught early, not propagated through layers. Defensive checks become provably unnecessary. The compiler can leverage determinism for aggressive optimization. And the code that does run—the actual work—runs fast, because clarity enables intelligent optimization. Faster programs aren't just environmentally responsible, they're more useful: responsive, accessible, scalable. Performance isn't something you sacrifice for correctness or bolt on later through ritual optimization. It's what emerges naturally when you can reason about what your code actually does.

## Reasoning Psychology

Unreasonable code creates constant cognitive dissonance. You're trying to hold a mental model of a system where anything can mutate anything, where side effects hide everywhere, where reading the code isn't enough because you need to trace through ten layers of indirection to understand what actually happens. It's exhausting. And the exhaustion becomes invisible—after years, it stops registering as pain and just becomes the baseline. The constant weight of defensive thinking, the resignation when opening certain codebases, the way you steel yourself before debugging. This isn't just technical friction. It's grinding against untruth: code that lies about what it does, systems that hide their complexity, abstractions that claim to simplify but actually obscure. There's research across cognitive psychology, narrative coherence, and contemplative traditions pointing to the same insight: untruth requires maintenance, creates stress, demands constant compartmentalization. Truth allows relaxation, coherence, ease. Clarity isn't merely pleasant -- it's psychologically liberating.

## Reasoning Reset

You can't rewrite culture. Can't fork society and fix the merge conflicts. Most harmful systems—institutional, cultural, historical—resist reconstruction. You can fight them, resist them, work against them, but you can't sit down and redesign them from first principles. But a programming language? That you can rebuild. It's small enough, bounded enough, technical enough to have technical solutions. And just maybe, those solutions can bring some truth and reason to a small corner of the world.
