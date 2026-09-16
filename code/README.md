# Coding standards

Code is Pentagram's interface to the machine. It is what implements the executable side of the language itself, and it also implements execution for the contributor environment. This gives code a deep, foundational responsibility.

If code is not correct, there is no forgiveness: the machine will execute incorrect code faithfully, and produce incorrect results. If code is not clear, no contributor will be able to safely change it, and the cost of changes will increase over time without bounds until changes grind to a halt.

All Pentagram code must be clearly correct. This is the only way for code to achieve its developer-facing and contributor-facing goals.

That said, writing clearly correct code depends on a good sense of taste that is expressed in every decision, small and large, through the entire software-development lifecycle.

The `code/` directory defines mechanics of good taste: how code runs fast, expresses intent, uses patterns, and is judged. Specific subsystem design documentation belongs with their respective subsystems; the docs here are about code as a system whose properties emerge through relationships and interactions.

The [manifesto's three aims](../manifesto.md) guide the standards for the code system:

- **Ergonomics:** make helpful software, and write code that is easy to work with.
- **Determinism:** make dependable software, and write code that is immediately accessible to reasoning.
- **Efficiency:** make responsive software, and write the minimum code needed.

These aims improve the code as a system. They do not make unclear or inaccurate code acceptable.

## Performance

[Performance](performance/README.md) describes Pentagram's requirement to be very, very fast for real use cases, and how this is accomplished and established at multiple levels.

## Style

[Style](style/README.md) describes how code expresses intent through useful patterns that make it easy to read, understand, reason about, and change.

## Quality

[Quality](quality/README.md) judges whether code is clearly correct, and describes how tiered evidence is used to show, with the highest practical certainty, that Pentagram has no defects.
