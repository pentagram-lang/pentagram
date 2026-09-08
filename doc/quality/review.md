# Review

A review gives documentation a fresh reading. The author asks an independent reviewer to read a named set of documents as written and report every problem present in those documents that makes them unclear or incorrect. The [review protocol](review-protocol.md) tells the reviewer how to do this. This guide explains the author's part.

## Prepare the handoff

The handoff to the reviewer is a single chat prompt. Build it using this template:

```text
Read `doc/quality/review-protocol.md` and follow it.
Read the documents below as written. Report every problem present in those
documents that makes them unclear or incorrect. Do not propose any repairs.

Documents to review:
<each document path>

Change ID (optional):
<jj change ID>

Reader and use:
<who the documentation serves and what they need to understand or do>
```

Name every document the reviewer should review and give the reviewer those documents by path. The reviewer may follow links to understand the named documents, but a linked document is out of scope unless you name it.

If the review focuses on a specific change, you may also give a `jj` change ID.

Say who the documentation serves and what those readers need to understand or do. Include the context needed to judge that use. Do not privately explain the documents or steer the reviewer towards one suspected problem. If a document needs a private explanation to make sense, the review should find that problem.

## Evaluate the report

Start the review with a separate subagent that has no inherited authoring conversation or project conclusions. Invoke it with the [handoff prompt](#prepare-the-handoff).

The reviewer returns one report in the review chat. The report describes the text the reviewer read. Treat its findings as evidence, not instructions, and ignore any repair suggestions.

Read each finding against the words it cites and the standards that govern the named documents. Decide whether it establishes a problem present in those documents. Use the project's recorded context and applicable documentation standards to determine what the documents should say. The findings and project context may show that preceding project work is needed before clearly correct text can be written. Do not repair from an unsupported conclusion, turn uncertainty into a finding, or write speculative documentation. Record the needed work through the [project workflow](../../proj/README.md), then write or revise the documents when their text can be established directly.

A finding outside the named documents is out of scope for this review. Use project context to evaluate it and decide whether any repairs are warranted. It does not become part of the quality judgement for the named documents.

Use the report as evidence in the complete quality judgement. A report with no findings means only that the reviewer found no supported problem under the review's conditions; it does not prove that the documentation is clearly correct. Decide what to do with the evidence through the project workflow.

If the project chooses a repair, derive it from project context and documentation standards, not from a reviewer suggestion. Repair the documents as a whole rather than patching only the quoted passage. Do not treat a finding as an invitation to add complexity that makes the documents unclear or incorrect.

After a repair, reuse the same subagent by default, at the author's discretion. Restate the full set of documents in the continuation prompt and say which documents in that set were updated. Do not change the set of documents under review, unless starting a new review. Do not give the reused reviewer the author's repair argument or project decision. Use this continuation prompt:

```text
Re-review the current named documents using `doc/quality/review-protocol.md`.

Documents to review:
<the full set of documents from the original handoff>

Updated documents:
<the named documents updated by the repair>

Read the current documents as written. Check the findings from the previous
review against the current text and report every problem currently present that
makes the documents unclear or incorrect. Do not propose any repairs.
```

If the author does not reuse the same subagent, start a new review with the [handoff prompt](#prepare-the-handoff). Treat it as a new review rather than passing the previous review's context to a new subagent.
