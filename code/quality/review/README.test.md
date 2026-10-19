# Tests

## Prepare a review

**Task**

Use `code/quality/review/README.md` to answer this task and cite the relevant section. An author wants an independent review of a parser module that processes source code tokens into an abstract syntax tree. Explain what the author puts in the handoff and what the author leaves out.

**Assert**

- The handoff names every code surface under review and provides the reviewer with those file, module, or package paths.
- The handoff may add one `jj` change ID in a separate field after the code surface paths when the review focuses on a specific change.
- The answer says that imported and dependent files are available for context but remain out of scope unless named.
- The reviewer is started as a separate subagent without inherited authoring conversation or project conclusions and receives the handoff, not the author's private explanation.
- The handoff states who the code serves, its public contract, invariants, and operational expectations.
- The handoff tells the reviewer to follow `code/quality/review/protocol.md`.
- The handoff tells the reviewer not to read active project state or run `0 proj`.
- The handoff does not include private explanation or limit the reviewer to one suspected problem.
- The answer uses one prompt containing the handoff and the review request.
- The answer cites `code/quality/review/README.md` as the basis for the handoff guidance.

## Evaluate a report

**Task**

Use `code/quality/review/README.md` to answer this task and cite the relevant section. A reviewer reports that a parser module leaks memory on malformed inputs and panics on an unexpected end-of-file condition, and suggests rewriting the entire parser using a parser-combinator library. The reviewer also notes a style issue in an unnamed imported utility file. Explain how the author evaluates the report.

**Assert**

- The answer checks each finding against the cited code and the standards governing the named code surfaces.
- The answer treats the report as evidence, not as instructions for a repair or a project decision.
- The answer ignores repair suggestions and derives any repair from project context, performance standards, and coding standards.
- The answer does not add speculative complexity or defensive boilerplate.
- The answer repairs the code as a cohesive whole rather than patching only the cited passage.
- The answer uses project context to evaluate the out-of-scope finding and decide whether any repairs are warranted.
- The answer uses project context and coding standards to determine what the code should do, recognizes when preceding architectural work is needed, and does not write speculative implementations.
- The answer does not treat a report with no findings as proof that the code is clearly correct.
- The answer cites `code/quality/review/README.md` as the basis for the evaluation guidance.

## Review a repair

**Task**

Use `code/quality/review/README.md` to answer this task and cite the relevant section. The project repairs a parser module after a review. Explain what the author includes and leaves out when arranging the next review, and how the author evaluates its result.

**Assert**

- The next review examines the current named code surfaces with an independent reviewer.
- Re-review is the default after a repair.
- The author reuses the same subagent by default, at the author's discretion.
- The continuation prompt restates the full named set of code surfaces, identifies the updated surfaces within it, and does not change that set unless starting a new review.
- The reused subagent checks the previous findings against the current code.
- If the author does not reuse the same subagent, the author starts a new review with the original handoff prompt rather than passing the previous review's context to a new subagent.
- The continuation prompt excludes the author's repair argument and project decision.
- The answer cites `code/quality/review/README.md` as the basis for the re-review guidance.

## Relate to other review processes

**Task**

Use `code/quality/review/README.md` to answer this task and cite the relevant section. An author prepares a code change that implements a new compiler flag and adds an explanation in an accompanying reference guide. Explain how code review relates to other review processes and whether additional reviews are warranted.

**Assert**

- The answer explains that code review is independent of documentation review and environment review, and that no review type replaces or substitutes for another.
- The answer explains that a passing code review establishes only that the inspected code satisfies code criteria, and does not establish documentation or environment quality.
- The answer explains that accompanying documentation may warrant an independent documentation review to judge whether that documentation accurately describes its subject and gives meaning a durable, navigable form as written.
- The answer explains that code shaping participant interaction or altering execution state may warrant an independent environment review to judge what documentation and code together cause participants to understand, do, and observe.
- The answer cites `code/quality/review/README.md` as the basis for the multi-process guidance.
