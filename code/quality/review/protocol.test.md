# Tests

## Apply the protocol without overreach

**Task**

Use `code/quality/review/protocol.md` to answer this task and cite the relevant section. Review a named set of code surfaces. The primary function computes the expected result on typical inputs, but an unchecked boundary condition causes an unhandled panic on empty slices. The function imports an external utility that has a performance inefficiency, but the handoff does not name that utility for review. The handoff names the code surfaces under review, may include one `jj` change ID, and states the contributor and developer use. A different architectural pattern could also express the logic, but the current design has no other established defect. The task does not supply file paths or literal code, so do not invent them.

Describe the findings the reviewer should report and the evidence the report should contain. Do not propose any repairs or decide what the project should do with the report.

**Assert**

- The reviewer inspects every named code surface and judges its literal code under the applicable quality standards.
- The answer treats the complete execution surface, mechanical sympathy, scale regimes, and structural clarity as part of the complete criteria, not as a restricted review checklist.
- The reviewer reports the unhandled boundary panic as a correctness defect and explains its execution consequence.
- The reviewer may report the imported utility's performance issue as out of scope, but does not treat it as a finding in the named code surfaces.
- The reviewer does not report an alternative design as a defect without evidence that the current design violates a governing standard or cannot serve its stated use.
- The answer says that the supplied facts do not support an exact code location or literal quotation, rather than inventing one.
- The answer explains that a report distinguishes observed code, governing standards, evidence, and uncertainty and uses the report form.
- The answer cites `code/quality/review/protocol.md` as the basis for the reporting guidance.

## Review changed code

**Task**

Use `code/quality/review/protocol.md` to answer this task and cite the relevant section. Review a code change. The handoff names the code surfaces, gives one `jj` change ID, and states the contributor and developer use. The current code adds a faster path for common inputs but removes an invariant check required by the public contract. Explain what the reviewer records and how the change evidence is used.

Do not recommend a repair or decide what the project should do with the change.

**Assert**

- The answer explains that the reviewer inspects the named code surfaces as written and uses the complete diff for the named change to understand what changed.
- The answer explains that the report identifies the removed invariant check as a supported defect and states the governing standard and execution consequence.
- The answer explains that the report does not treat the faster execution path, a likely repair, or the absence of another finding as proof that the change passes.
- The answer explains that the report records the supplied change ID and any evidence limitation.
- The answer cites `code/quality/review/protocol.md` as the basis for the changed-code review guidance.

## Re-review a repaired problem

**Task**

A reused reviewer receives the continuation prompt after a repair. The prompt restates the current named code surfaces and identifies the surfaces updated by the repair. Use `code/quality/review/protocol.md` to answer how the reviewer proceeds and cite the relevant section. Review the current code surfaces from the beginning.

Explain how the reviewer proceeds without deciding whether the repair succeeded.

**Assert**

- The answer explains that the reviewer checks every earlier problem against the current code, reuses its identifier if it is still present, and records in Coverage what the current code and evidence establish if it is no longer present.
- The answer explains that the reviewer reports a new identifier for any distinct current problem.
- The answer explains that the reviewer does not infer resolution from the changed passage, the old report, or the author's repair explanation.
- The answer explains that the report states what the current code and evidence establish and what remains uncertain.
- The answer cites `code/quality/review/protocol.md` as the basis for the re-review guidance.
