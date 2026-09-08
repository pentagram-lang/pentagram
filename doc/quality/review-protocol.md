# Review protocol

A review gives a named set of documents a fresh reading. The reviewer reads those documents as written and reports every problem present that makes them unclear or incorrect. The reviewer uses the documentation standards and the handoff's stated reader and use to judge the documents. The reviewer does not supply missing meaning, invent a requirement, propose any repairs, or decide what the project should do with the report.

## Read the handoff and documentation

Read the handoff before the named documents. It names the documents under review, may identify one `jj` change when the review focuses on a specific change, and says who the documentation serves and what those readers need to understand or do.

Read every named document as written. Follow links when needed to understand a named document's purpose, reading path, claims, instructions, and boundaries. A linked document is context, not part of the review, unless the handoff names it. Report a problem in an unnamed linked document as out of scope. Let the words establish what the documentation says; do not fill a gap with a private explanation or an assumption about what the author meant.

When the handoff includes a `jj` change ID, inspect the complete diff for that single change with `jj diff --git --revision CHANGE`, as [source control: working copy](../../source-control.md#working-copy) describes. Use it as evidence alongside the current named documents. The change does not replace reading the current documents as written.

The handoff's reader and use explain how the documentation must work. They do not replace the complete quality judgement with an author's anticipated problem or preferred conclusion.

## Judge clearly correct

Use the [documentation criteria](criteria.md) as the authority for quality. Follow its delegation to [meaning](../meaning/README.md), [structure](../structure/README.md), [style](../style/README.md), and local documentation. Judge these together. Correct meaning cannot rescue a path readers cannot follow, and fluent prose cannot make a false claim correct.

Use the [topology: exercise the reading path](../structure/topology.md#exercise-the-reading-path) to judge how the surface leads readers from one document to the next. Use the [house style: follow the thought](../style/house.md#follow-the-thought) to judge how each paragraph carries its thought. Use the [house style: use a real voice](../style/house.md#use-a-real-voice) to judge whether the document's tone and confidence fit its authority and use. These criteria are called out because a surface can pass isolated factual checks and still fail when readers cannot follow its path or prose. The review still covers the complete documentation criteria.

Do not demand every possible detail. An omission is a problem when the stated use cannot be understood or carried out without it, or when an applicable standard requires it. A strong review is exact about that difference. It reports what is present in the text, what the sources establish, and what remains uncertain; it does not turn uncertainty or a preferred repair into a finding.

The named documents set the review boundary. A supplied change ID adds evidence for a change-focused review; it does not expand the named set. Reader and use establish the conditions for judging those documents; they do not limit the review to an author's anticipated problem. Report every supported problem within the named documents. If the handoff does not supply reader and use clearly enough to judge them, report that limitation instead of silently assuming it. Do not include a problem outside the named set in Findings. You may record it separately as out of scope, with its path and the reason it is excluded.

## Report the evidence

Write one report for the named documents. Identify the documents, reader and use, standards, evidence, optional change ID, and material limitations. Give each supported problem a stable identifier and enough literal text and location for another reader to find it.

Explain the problem from the documentation and its governing standard or evidence. State the reader consequence. Keep an observed problem separate from uncertainty about its cause or repair. A report records evidence for the author and project; it does not approve the document or prescribe its next change.

Use this form:

```md
# Review report

Documents: <the named documents>

Reader and use: <who the documentation serves and what they need to understand or do>

Change ID (if supplied): <jj change ID>

Reviewer: <identity, harness, and material limitations>

## Coverage

<documents, standards, sources, checks, and uncertainty actually examined>

## Findings

### F1: <concise problem name>

Location:

Literal text:

Problem:

Standard and evidence:

Reader consequence and uncertainty:

## Out of scope

<problems noticed outside the named documents and why they are excluded, or `None`>
```

A report with no findings means that no supported problem was found in the named documents under the named standards and conditions. It does not establish a quality pass, and it says nothing about documents outside that set.

## Review again

On a re-review, read the current named documents from the beginning and check every earlier finding against them. Use the original identifier when the same problem is still present and report it in Findings. If it is no longer present, state in Coverage that you checked it and what the current text and evidence establish. Use a new identifier for a distinct current problem. Do not infer that a problem is resolved merely because a passage changed or because no new finding was reported. If a new reviewer conducts the review, treat it as a new review rather than carrying the earlier review's context into it.
