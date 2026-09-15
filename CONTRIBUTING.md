# Contributing

Thanks for reading about how to contribute to Pentagram!

To get oriented with the language implementation, you can visit the [README](README.md) and follow the links there to any topic you need to know.

This guide here will help you understand:

1. [how to use the manifesto](#using-the-manifesto) when designing and building your contribution; and
2. [what your contribution needs to be accepted](#acceptance-criteria).

## Using the manifesto

Use the [manifesto](manifesto.md) to guide almost every decision about your contribution. It has three connected aims:

- **Ergonomics:** reduce friction in reading, using, and changing the system.
- **Determinism:** make meaning and behaviour predictable from explicit conditions.
- **Efficiency:** avoid unnecessary manual and automatic work.

These aims describe the kind of programming language Pentagram is trying to build. Ergonomics makes reasoning easier, determinism makes it dependable, and efficiency makes it useful in practice. They belong together: a contribution should not improve one by sacrificing another.

The goal is for every change to embody and support each aim, to the extent applicable and practical:

- **Embody.** Put the aim into practice in the system you are changing.
- **Support.** Help realize the aim across Pentagram.

## Acceptance criteria

**Every contribution must be clearly correct: it must do what it is supposed to do, and be easy to understand.**

Your contribution must meet all its requirements, not just produce the expected output. The work itself must be easy to understand. A proof of correctness cannot make up for unclear work; clear presentation cannot make up for unmet obligations.

The subject matter and your resources set the practical limits. Within those limits, a contribution will not be accepted while anything remains unclear or incorrect.

There is no substitute for clearly correct. Probably correct or barely correct is not enough. Nor is work that readers can understand only after a struggle.

### Why it matters

Incorrect work adds defects or hazards to the repository, directly affecting Pentagram developers.

Unclear work risks future defects and hazards, because difficulty in understanding makes all later changes more likely to be unclear or incorrect.

By keeping every incremental change clear and correct, Pentagram itself incrementally becomes a better programming language.

Accepted work becomes part of the repository's future. A contribution must preserve or improve the conditions for later contributions to be clearly correct. Other contributors learn from accepted work and its examples; a defect in accepted work is not permission to repeat it in yours.

### Examples

These examples show qualities that contributions might have. They are not a checklist or a preferred design. Clarity and correctness are separate. Each label says which qualities the example demonstrates; an omitted quality is not assessed.

#### Documentation

- **Clear:** A concise introduction makes the subject and next path apparent.
- **Unclear:** A procedure contains the needed facts, but its conditions and consequences are scattered.
- **Correct:** A reference accurately states the current contract and its limits.
- **Incorrect:** A document describes planned behaviour as current behaviour.
- **Clear but incorrect:** A document plainly states the wrong contract.
- **Correct but unclear:** A document accurately describes behaviour, but readers must reconstruct how its parts relate.

#### Code

- **Clear:** A small operation's purpose and data flow are apparent from its local structure.
- **Unclear:** An operation's meaning depends on hidden state.
- **Correct:** An implementation behaves as its contract describes across the cases that contract covers.
- **Incorrect:** An implementation works in familiar cases but violates a required case or changes unrelated behaviour.
- **Clear but incorrect:** Readable code produces the wrong result.
- **Correct but unclear:** Code satisfies its contract, but its behaviour is difficult to reconstruct.

Match the repair to the problem. More explanation, more checks, or a different design are not enough by themselves. Different designs can both be clearly correct; a preference for another design does not by itself show a problem with yours.

### Quality guidance

What qualifies as clearly correct is not based just on intuition.

Pentagram has specific quality guides that apply depending on what's included in a contribution:

- [Documentation quality](doc/quality/README.md) judges whether documentation gives meaning a durable, navigable form.
- [Code quality](code/quality/README.md) judges whether code is performant and maintainable, with practical assurance that it has no defects.
- [Environment quality](env/quality/README.md) judges whether documentation and code work together to shape understanding, action, and system results.

Other local documentation that intersects with the contribution also informs what is clearly correct.
