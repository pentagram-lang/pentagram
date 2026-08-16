# Environment engineering

[Pentagram](../README.md) intentionally engineers documentation and code together as an environment for positive and effective language development.

Documentation states what Pentagram means and shapes how readers understand it. Code is both environmental text and the expression of executable systems. Those systems enforce constraints, expose affordances, return feedback, and preserve state. Environment engineering deliberately designs how documentation and code produce these effects together.

High quality documentation and code do not guarantee a good environment. Together, they can still guide humans or agents towards undesired behaviour. They can also leave important behaviour unguided, allowing prior human experience or model training to determine it. Environment engineering addresses both failures by requiring an intent, and deliberately designing documentation and code to realize it.

`env/` contains shared environment-engineering guidance, not project-specific designs or evidence. Documentation and code remain with their subjects. Environmental intent becomes repository text only when another reader, system, or future decision must rely on it, and then belongs with the subject it governs.

Pentagram's environment engineering is based on [ergonomics, determinism, and efficiency](../manifesto.md). It must embody each applicable aim in its own design and support that aim across Pentagram.

| Aim             | Embody in environment engineering                                                                 | Support across Pentagram                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Ergonomics**  | Make environmental intent, design, and quality natural to understand, use, and change.            | Make practices for positive and effective language development natural for humans and agents.                 |
| **Determinism** | Make the relationships among intent, environmental causes, and observed effects explicit.         | Keep documentation and code consistent so meaning, constraints, feedback, and recovery reinforce one another. |
| **Efficiency**  | Avoid repeated framing, competing copies, and evidence whose cost exceeds the decision it serves. | Preserve and present useful context while avoiding unnecessary human effort, agent context, and system work.  |

The [documentation standards](../doc/README.md) govern documentation meaning, structure, style, and documentation quality. The [coding standards](../code/README.md) govern code and implementation tests. Environment engineering governs how documentation and code work together as an environment. Every repository change participates in that environment and must account for its environmental effects; formal environment testing and review remain proportional to behavioural risk and leverage.

## Theory

[Theory](theory.md) explains how text and systems shape LLM probabilities and human schemas, how compatible cues establish durable frames, and how the combined environment remains robust against error.

## Intent

[Intent](intent.md) gives authors the minimal guidance needed to determine environmental intent before design or quality evaluation without prescribing intent values or requiring every intent to become repository text.

## Design

[Design](design/README.md) explains how to engineer documentation and code together as a powerful environment for humans and agents.

## Quality

[Quality](quality/README.md) defines environment-quality authorship and the proportional testing and review used to establish environmental effects.
