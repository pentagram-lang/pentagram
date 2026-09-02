# Tests

## Identify intent before design

**Task**

You are about to design documentation and code for a new repository command. Explain who is responsible for identifying the relevant intent and how governing authority bounds that responsibility. Define an environmental effect and state what must be identified before choosing changes, including how humans and agents affect those requirements. Explain how to bound the `total-environment` and where environment state and external encounter conditions belong. State what `env/` does and does not supply as intent. Cite the governing repository documentation.

**Assert**

- The answer says the author identifies desirable and important undesirable environmental effects for the subject before design or quality evaluation.
- The answer says the author identifies and applies intent within governing authority and cannot replace operator instructions, project decisions, or the subject's existing contract.
- The answer calls the author's judgement `intent`, not `environment intent`, `environmental intent`, or `local intent`.
- The answer says an effect can be an outcome, an invariant, or a transition and distinguishes a system result that execution permits from one it produces.
- The answer includes at least one desirable effect for humans and one for agents because the complete environment must benefit both participant classes.
- The answer distinguishes intended effects from interventions and does not treat `env/` as a source of predetermined intents.
- The answer follows causal reach to bound the `total-environment` and keeps state created or preserved by documentation and code in that environment.
- The answer uses `participant`, `situation`, and `encounter-noise` to state the applicable encounter conditions, keeps material external conditions outside the `total-environment`, and does not duplicate environment state through `situation`.
- The answer cites `env/intent.md` and the applicable definitions in `env/theory.md`.

## Scale environment-quality evidence

**Task**

A proposed change affects shared repository guidance used across many subjects. Explain how environment quality decides the strength and breadth of evidence to gather, where its investigation stops, and how it decides whether environment tests or review are worth performing. Cite the governing repository documentation.

**Assert**

- The answer assigns environmental risk to each effect in scope and explains that it governs evidentiary strength.
- The answer assesses risk from the credible material ways the effect can diverge from intent and how seriously those divergences matter.
- The answer assigns environmental leverage to each affected environmental surface across all effects and explains that it governs evidentiary breadth.
- The answer follows plausible causal paths from an affected surface and stops expanding the boundary when no further material effect can change through them.
- The answer weighs the evidence an environment test or review can add against its resource cost without describing the test run itself as risky.
- The answer cites the governing definitions and methods in `env/quality/`.

## Choose the test system

**Task**

A change contains documentation and an executable command implemented in `command.rs`. A `.test.md` companion must accompany `command.rs` rather than a Markdown subject. You need evidence that readers understand and act from the documentation, that actual command execution produces its required outcome, and that an agent encounter with the complete environment produces an intended action and applicable system outcome. Explain which Pentagram test system covers each need, what each can assert, and where the durable test contracts belong. Cite the governing repository documentation.

**Assert**

- The answer says documentation tests assert reader understanding or action attributable to documentation and never assert a result of actual system execution.
- The answer says implementation tests assert only results of actual execution and do not assert participant understanding or action.
- The answer places implementation tests in the same-directory shadow test file required by `code/README.md`, not in a `.test.md` companion.
- The answer says environment tests assert understanding or action from an encounter with the complete environment and may also assert an applicable system result.
- The answer distinguishes participant action from a system result by the proposition asserted, even when one execution trace supplies evidence for both.
- The answer explains that documentation and environment tests share the `.test.md` companion schema, can accompany any file type, and are distinguished by their task, assertions, and causal boundary rather than by the subject's file type. It maps a companion for `command.rs` to `command.rs.test.md`.
- The answer cites `doc/quality/test.md`, `code/README.md`, and `env/quality/test.md`.
