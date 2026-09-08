# Tests

## Distinguish contribution acceptance from developer freedom

**Task**

A contributor proposes a faster repository tool. Existing automated tests pass, but the contribution gives no basis for concluding that documented failure behaviour outside those tests is preserved. The contributor argues that the speed improvement and passing tests are sufficient for acceptance.

Separately, a developer wants to write a disposable experiment in Pentagram, without contributing it to the repository.

Explain the governing standard for each case, how the repository change should affect other contributors' work, and what evidence would justify an acceptance decision. Cite the repository documentation that supplies the standard. Do not change files or project state.

**Assert**

- The answer identifies CONTRIBUTING.md as the owner of the shared contributor standard and the manifesto as the source of the three guiding aims.
- The answer explains both embodying each aim in the changed system and supporting it across Pentagram, to the extent applicable and practical.
- The answer does not accept the tool change solely because it is faster and passes the existing tests; it requires justified evidence for the actual requirements, including the documented failure behaviour.
- The answer explains both the contribution's own clear correctness and preserving or improving the conditions for other clearly correct contributions.
- The answer does not impose the repository contribution standard on the developer's disposable program.

## Distinguish correctness from clarity

**Task**

Consider two hypothetical contributions. One is easy to read and returns the expected values, but violates an explicit memory bound. The other satisfies its requirements, but its evidence consists only of passing happy-path tests and leaves readers unable to establish why a removed error check is safe.

Explain what “clearly” and “correct” mean for these cases and what could change the acceptance judgement. Cite the governing documentation. Do not change files or project state.

**Assert**

- The answer identifies CONTRIBUTING.md as the governing source and distinguishes satisfaction of actual requirements from understandable, justified evidence of that satisfaction.
- The answer identifies the first contribution as incorrect despite its expected return values and readability, because the memory bound is an actual requirement.
- The answer preserves the premise that the second contribution is correct but distinguishes that fact from whether its correctness is clear; the supplied evidence does not justify acceptance.
- The answer connects an improved judgement to meeting the missing requirement or establishing the missing justification, without treating one example's technique as mandatory for every contribution.
