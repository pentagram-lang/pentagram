# Tests

## Distinguish contribution acceptance from developer freedom

**Task**

A contributor proposes a faster repository tool. Existing automated tests pass, but the contribution gives no basis for concluding that documented failure behaviour outside those tests is preserved. The contributor argues that the speed improvement and passing tests are sufficient for acceptance.

Separately, a developer wants to write a disposable experiment in Pentagram, without contributing it to the repository.

Explain the governing standard for each case, how the repository change should affect other contributors' work, and what evidence would justify an acceptance decision. Cite the repository documentation that supplies the standard. Do not change files or project state.

**Assert**

- The answer identifies CONTRIBUTING.md as the owner of the shared contributor standard and the manifesto as the source of the three guiding aims.
- The answer explains both embodying each applicable aim in the changed system and supporting it across Pentagram.
- The answer does not accept the tool change solely because it is faster and passes the existing tests; it requires justified evidence for the actual requirements, including the documented failure behaviour.
- The answer explains both the contribution's own clear correctness and preserving or improving the conditions for other clearly correct contributions.
- The answer selects evidence appropriate to the requirements and risks rather than imposing uniform checks or complete formal proof on every change.
- The answer does not impose the repository contribution standard on the developer's disposable program.
