# Subtractive design

Within [Pentagram](../README.md), subtractive design keeps the repository limited to what the current system requires. It applies to both code and documentation.

The French writer and aviator Antoine de Saint-Exupéry offered this formulation in his 1939 memoir _Wind, Sand and Stars_:

> “Perfection is achieved, not when there is nothing more to add, but when there is nothing left to take away.”

## Design through subtraction

Subtractive design is the primary tool for every repository change.

Saint-Exupéry's engineers worked through generations of calculation and drawing, refining form until joints and wings disappeared into a unified whole and the machine could disappear behind its function.

Use the same discipline for new designs and repairs to old ones. Every change to code or documentation is a demand to re-evaluate what is truly essential.

Determine what must be maintained, added, and reshaped; then use subtraction to remove everything else. Repeat the process as needed. The goal is not emptiness. The goal is a tool whose parts work together so naturally that the final system works in flawless harmony without any traces of accidental complexity.

## Remove what no longer serves

Remove code and documentation that are unused or outdated. When a requirement changes, remove what served the old requirement unless it still serves a current one. Do not leave old support competing with the present system.

## Verify removals

When a removal is broad or difficult to verify by inspection, use uncommitted Python scripts in `.tmp/` to search the repository for remaining references or other residue. Treat their output as provisional evidence for the removal; the scripts themselves are not repository code.

## Do not build for a future need

Do not add or preserve code or documentation solely for a future need. Keep future work in the project system or other appropriate provisional storage until the need is current and its shape is understood.

A possible future is not a present contract. Let a real requirement justify each addition when it arrives.

## Apply subtraction at every scale

The same discipline applies at every scale, from a line of code to a whole subsystem. Remove what obscures the current purpose without removing what that purpose requires.
