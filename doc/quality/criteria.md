# Criteria

Within [quality](README.md), documentation quality judges whether a complete documentation surface is clearly correct. The surface must accurately describe its subject within its stated scope and status, and its intended readers must be able to find, understand, and use the information. These are separate conditions: clear prose can state something false, and an accurate statement can still be difficult to use. A surface is not clearly correct when either condition fails.

## Use the pillar standards

Use [meaning](../meaning/README.md) for what the documentation says and what readers may rely on. Use [structure](../structure/README.md) for how documentation is arranged and connected. Use [style](../style/README.md) for how documented meaning is expressed.

The documentation contract comes from these standards and from documentation local to the subject. A local document can state a narrower convention or contract for the surface it owns, but it must state that scope directly. Each pillar's README leads to the detailed standards.

Judge the text against that contract, the subject it describes, and the stated reader use. Project records, private conversation, and author memory do not supply meaning that the documentation does not state.

Violations of [meaning](../meaning/README.md), [structure](../structure/README.md), and [style](../style/README.md) are correctness problems. A document must correctly match the Pentagram documentation contract in what it says, how it is arranged, and how it is expressed. Clarity problems often hide incorrect meaning and are often caused by incorrect structure or style. Correct meaning, structure, and style do not guarantee clarity.

## Judge the complete surface

Judge the complete surface, starting with the entry document and following its reading path. Include every document and section that path presents, along with the links and structure that connect them. Include any companion that supplies part of the surface's contract, even when topology does not make it an ordinary navigation child. A claim can be accurate while the surface still fails because its route is broken or its warning arrives after the action it governs. A surface can be easy to read and still fail when its claims contradict its subject or the documentation contract.

Do not require detail merely because it could be useful. An omission is a problem when the stated reader use cannot be understood or carried out without it, or when the documentation contract requires it. Correct meaning cannot compensate for unusable structure or style. Clear presentation cannot compensate for false meaning.

## Weigh adequate evidence

Evidence must address the condition being judged. A lint result supports only the mechanical rules the linter checks. A test result supports only its assertions under its recorded conditions. A review supports only its recorded subject and quality coverage.

The quality judgement is a pass only when adequate evidence supports both conditions across the complete surface. It is a fail when evidence establishes a violation or establishes a clarity problem that prevents the stated use. It is inconclusive when material evidence is missing, contradictory, or too weak to decide.
