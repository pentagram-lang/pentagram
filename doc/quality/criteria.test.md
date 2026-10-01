# Tests

## Judge archive surfaces

**Task**

You are advising an operator who must archive records. Use the repository's documentation standards to judge whether each documentation surface supports that use clearly and correctly. Read the quality criteria and the meaning, structure, and style standards before answering.

For this task, the archive contract is complete: the command archives only records marked complete, the operator must provide explicit confirmation, the archive target must be available, and the operator must preserve the receipt produced by the command.

The following are the complete fixtures for the task.

**Surface A**

```md
# Archive records

The `archive` command archives every record, regardless of whether it is marked complete. The operator must provide explicit confirmation, the archive target must be available, and the operator must preserve the receipt produced by the command.
```

**Surface B**

```md
# Archive records

After the record has been marked complete, when the archive target is available and the operator has provided explicit confirmation, the operator may archive the record, and, once the command has produced a receipt, the operator must preserve it, while the record must not be archived if any one of the three preconditions is absent.
```

**Surface C**

The operator starts at the `README.md` entry point and follows only the links that it provides. The complete surface contains these two files:

`README.md`

```md
# Record operations

This surface contains guidance for record operations.
```

`archive.md`

```md
# Archive records

Before archiving, confirm that the record is marked complete, the archive target is available, and explicit confirmation has been provided. After the command produces a receipt, preserve it for verification.
```

**Surface D**

The complete surface has a `README.md` with a direct link to `archive.md` under an `Archive records` heading. The linked page uses the same text as Surface C. In a recorded reader trial, an unfamiliar operator was given only this surface and asked, “What must be confirmed before archiving, and what must be preserved afterwards?” The operator answered, “Confirm that the record is complete; preserve the archive target.” No other source was available during the trial.

For each surface, explain whether the documentation supports the operator's use, identify any problem and its governing standard, and state the consequence for the reader. Cite the relevant repository standard and the fixture text. Do not propose rewrites.

**Assert**

- The answer cites `doc/quality/criteria.md` as the quality authority and cites the applicable delegated meaning, structure, or style standard for each judgement without citing personal preference as its basis.
- The answer identifies Surface A's false claim as a meaning and correctness problem even though its prose is easy to follow.
- The answer identifies Surface B's overloaded expression as a style and correctness problem, explains any clarity burden it establishes, and recognizes that its stated archive conditions match the task contract.
- The answer identifies Surface C's missing route from `README.md` to `archive.md` as a structure and correctness problem that also prevents clarity, even though the page's meaning and expression are otherwise usable.
- The answer identifies Surface D's recorded reader failure as evidence of a remaining clarity problem without claiming that it violates meaning, structure, or style or that the reader's failure alone proves its cause.
- The answer keeps correctness and clarity distinct and does not claim that correct meaning, structure, and style guarantee clarity.
- The answer gives an explicit support judgement for all four surfaces and cites the relevant fixture text for each judgement or finding.
- The answer gives a reader consequence for each finding and does not propose a repair or rely on the reader's self-assessment.
