# Tests

## Apply the protocol without overreach

**Task**

Use `doc/quality/review-protocol.md` to answer this task and cite the relevant section. Review a named set of documents. The main document's central claim is accurate but its applicable house-style rule makes a critical condition hard to follow. It links to another document that has a separate style problem, but the handoff does not name that document for review. The handoff names the documents under review, may include one `jj` change ID, and states the reader and use. A different design could also express the claim, but the current design has no other established defect. The task does not supply document paths or literal passages, so do not invent them.

Describe the findings the reviewer should report and the evidence the report should contain. Do not propose any repairs or decide what the project should do with the report.

**Assert**

- The reviewer reads every named document and judges its literal text under the applicable standards.
- The reviewer reports the applicable style deviation as a correctness problem and explains its reader consequence.
- The reviewer may report the linked document's style problem as out of scope, but does not treat it as a finding in the named documents.
- The reviewer does not report an alternative design as a defect without evidence that the current design violates a governing standard or cannot serve its stated use.
- The answer says that the supplied facts do not support an exact document location or quotation, rather than inventing one.
- The answer explains that a report distinguishes observed text, governing standards, evidence, and uncertainty and uses the report form.
- The answer cites `doc/quality/review-protocol.md` as the basis for the reporting guidance.

## Review changed documents

**Task**

Use `doc/quality/review-protocol.md` to answer this task and cite the relevant section. Review a documentation change. The handoff names the documents, gives one `jj` change ID, and states the reader and use. The current documents add a clear explanation but also remove a condition required by the governing standard. Explain what the reviewer records and how the change evidence is used.

Do not recommend a repair or decide what the project should do with the change.

**Assert**

- The answer explains that the reviewer reads the named documents as written and uses the complete diff for the named change to understand what changed.
- The answer explains that the report identifies the removed condition as a supported problem and states the governing standard and reader consequence.
- The answer explains that the report does not treat the new explanation, a likely repair, or the absence of another finding as proof that the change passes.
- The answer explains that the report records the supplied change ID and any evidence limitation.
- The answer cites `doc/quality/review-protocol.md` as the basis for the changed-review guidance.

## Re-review a repaired problem

**Task**

A reused reviewer receives the continuation prompt after a repair. The prompt restates the current named documents and identifies the documents updated by the repair. Use `doc/quality/review-protocol.md` to answer how the reviewer proceeds and cite the relevant section. Review the current documents from the beginning.

Explain how the reviewer proceeds without deciding whether the repair succeeded.

**Assert**

- The answer explains that the reviewer checks every earlier problem against the current documents, reuses its identifier if it is still present, and records in Coverage what the current text and evidence establish if it is no longer present.
- The answer explains that the reviewer reports a new identifier for any distinct current problem.
- The answer explains that the reviewer does not infer resolution from the changed passage, the old report, or the author's repair explanation.
- The answer explains that the report states what the current text and evidence establish and what remains uncertain.
- The answer cites `doc/quality/review-protocol.md` as the basis for the re-review guidance.
