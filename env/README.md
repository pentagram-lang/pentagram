# Environment engineering

[Pentagram](../README.md) intentionally engineers documentation and code together as an environment for positive and effective language development.

Documentation states what Pentagram means and shapes how readers understand it. Code is both environmental text and the expression of executable systems. Those systems enforce constraints, expose affordances, return feedback, and preserve state. Environment engineering deliberately designs how documentation and code produce these effects together.

High-quality documentation and code do not guarantee a good environment. Together, they can still produce important undesirable environmental effects or fail to support desirable environmental effects, allowing prior human experience, model training, or other conditions to determine the result. Within the authority governing each subject they work on, authors identify how they intend the environment to work—which desirable environmental effects the environment should produce or preserve and which important undesirable environmental effects it should avoid—and apply environment engineering to shape documentation and code towards that intent.

`env/` contains shared environment-engineering guidance. It does not supply predetermined intents or contain project-specific designs and evidence. Documentation and code remain with their subjects. When another reader, system, or future decision must rely on an author's identified intent, the author records it with the subject.

Environment engineering does not define or conduct human studies. Authors may use applicable findings produced elsewhere when identifying intent, choosing an intervention, or judging environmental quality.

Pentagram's environment engineering is based on [ergonomics, determinism, and efficiency](../manifesto.md). It must embody each applicable aim in its own design and support that aim across Pentagram.

| Aim             | Embody in environment engineering                                                                 | Support across Pentagram                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Ergonomics**  | Reduce friction when authors identify intent, design environments, and evaluate their quality.    | Make practices for positive and effective language development natural for humans and agents.                 |
| **Determinism** | Make the relationships among intent, environmental causes, and observed effects explicit.         | Keep documentation and code consistent so meaning, constraints, feedback, and recovery reinforce one another. |
| **Efficiency**  | Avoid repeated framing, competing copies, and evidence whose cost exceeds the decision it serves. | Preserve and present useful context while avoiding unnecessary human effort, agent context, and system work.  |

The [documentation standards](../doc/README.md) govern documentation meaning, structure, style, and documentation quality. The [coding standards](../code/README.md) govern code and implementation tests. Environment engineering governs how documentation and code work together as an environment. Every repository change participates in that environment and must account for its environmental effects; formal environment testing and review remain proportional to environmental risk and leverage.

## Theory

[Theory](theory.md) presents Pentagram's adopted model of how text and systems can condition LLM probabilities, activate human schemas, support durable frame reconstruction, and correct frame distortion. Its mechanisms support causal hypotheses; evidence determines their effects in a particular encounter.

## Intent

[Intent](intent.md) guides authors in identifying how they intend the environment to work for the subject, including the desirable environmental effects and important undesirable environmental effects. The identified intent directs design and gives quality a basis for evaluation. The guide does not prescribe those effects or require every intent to be recorded in repository text.

## Design

[Design](design/README.md) turns identified effects and environmental-encounter inputs into documentation and code interventions. Its human and agent methods use their distinct cognitive mechanisms to shape one compatible environment that benefits both.

## Quality

[Quality](quality/README.md) defines environment-quality authorship and the proportional evidence, testing, and review used to judge environmental effects.
