# Tests

## Prepare a review

**Task**

Use `doc/quality/review.md` to answer this task and cite the relevant section. An author wants an independent review of a recovery guide that helps readers recover from a failed operation. Explain what the author puts in the handoff and what the author leaves out.

**Assert**

- The handoff names every document under review and gives the reviewer those documents.
- The handoff may add one `jj` change ID in a separate field after the document paths when the review focuses on a specific change.
- The answer says that linked documents are available for context but remain out of scope unless named.
- The reviewer is started as a separate subagent without inherited authoring conversation or project conclusions and receives the handoff, not the author's private explanation.
- The handoff states the readers and what they need to understand or do.
- The handoff tells the reviewer to follow `doc/quality/review-protocol.md`.
- The handoff does not include private explanation or limit the reviewer to one suspected problem.
- The answer uses one prompt containing the handoff and the review request.
- The answer cites `doc/quality/review.md` as the basis for the handoff guidance.

## Evaluate a report

**Task**

Use `doc/quality/review.md` to answer this task and cite the relevant section. A reviewer reports that a recovery guide contains a false condition and an unclear instruction, but gives no evidence for a proposed repair. The reviewer also notes a problem in an unnamed linked document. Explain how the author evaluates the report.

**Assert**

- The answer checks each finding against the cited text and the standards governing the named documents.
- The answer treats the report as evidence, not as instructions for a repair or a project decision.
- The answer ignores repair suggestions and derives any repair from project context and documentation standards.
- The answer does not add complexity that makes the documents unclear or incorrect.
- The answer uses project context to evaluate the out-of-scope finding and decide whether any repairs are warranted.
- The answer uses project context and documentation standards to determine what the documents should say, recognizes when preceding project work is needed, and does not write speculative documentation.
- The answer does not treat a report with no findings as proof that the documentation is clearly correct.
- The answer cites `doc/quality/review.md` as the basis for the evaluation guidance.

## Review a repair

**Task**

Use `doc/quality/review.md` to answer this task and cite the relevant section. The project repairs a recovery guide after a review. Explain what the author includes and leaves out when arranging the next review, and how the author evaluates its result.

**Assert**

- The next review examines the current named documents with an independent reviewer.
- Re-review is the default after a repair.
- The author reuses the same subagent by default, at the author's discretion.
- The continuation prompt restates the full named set, identifies the updated documents within it, and does not change that set unless starting a new review.
- The reused subagent checks the previous findings against the current text.
- If the author does not reuse the same subagent, the author starts a new review with the original handoff prompt rather than passing the previous review's context to a new subagent.
- The handoff excludes the author's repair argument and project decision.
- The answer cites `doc/quality/review.md` as the basis for the re-review guidance.
