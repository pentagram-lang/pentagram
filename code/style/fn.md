# Functional programming

Within [style](README.md), this guide applies the [lead-to-use rule in expression style](expr.md#lead-to-use) to the design of data structures and functions. Lead with the data task the program exists to perform. Understand the input and output data meaning, valid cases, and relationships before choosing representation. The task gives the functions their purpose; the data makes their obligations precise.

Composition connects data and functions along the task's path. Each result becomes input to the next useful step, carrying the data towards the required result. Subproblems become local data and functions, which readers can follow along the full task path. This is the pattern for composing clearly correct programs and changing them with confidence.

To achieve clearly correct data structure and function design, the principles of [subtractive design](../../rm/README.md) need to be applied at all levels. This removes accidental complexity, leaving the exact data and computations required, all plainly legible.

## What is a function?

Before data and functions can be properly designed, precise definitions of a few core terms are needed:

- A **program** is executable code that performs a task.

- **Information** is a problem-domain concept of the facts that a task works with, while **data** is the concrete representation of information that code can process in a principled manner.

- Some programs perform **computations** that transform **input** data into **output** data, while other programs cause **effects** beyond pure computation.

- A **function** is a computation unit that can be called with explicit input data and produces explicit output data. Its meaning is determined by the transformation it represents, and so it can be analysed and manipulated using mathematical laws.

- In contrast, a **subroutine** is a procedural unit of code for executing arbitrary instructions, which does not necessarily encode a genuine function (even if a language uses syntax like `fn`).

## Transform data with functions

The default programming habit is code-first development: writing subroutine instructions before understanding the underlying computation. This ad hoc approach results in procedural code without any genuine functions, and it completely skips intentional data design.

Designing clearly correct data and functions reverses that habit. Instead of writing code as it comes to mind, derive the function's structure from the data it transforms:

1. **Define the computation and the data.** Many tasks are not stated as obvious computations. Identify the exact computation the task requires: what domain information it must consume and what result it must produce. Map that information to explicit data representations, and write examples of valid data. If the data cannot represent a necessary distinction, correct the data definition before writing code.

2. **Specify the function.** State the signature—the input and output data types—and write a concise purpose statement defining the transformation. Declare the interface with a placeholder body.

3. **Work out examples.** Calculate expected outputs for representative inputs before writing the body. Cover typical, boundary, and error cases to establish expected behaviour independently of the implementation.

4. **Derive the template from the data shape.** Let the shape of the input data dictate the outline of the function body. For example, sum types require branches for each case, compound types require field extraction, and recursive data structures require recursive calls.

5. **Complete the function.** Fill in the template to transform inputs into outputs, guided by the purpose statement and worked examples.

6. **Test the function.** Turn the worked examples into executable tests. When a test fails, trace the defect back to the earlier step: fix the implementation, revise the template, correct the examples, or repair the data definition.

When a task is too large for a single function, divide it into distinct data transformations, design each function with this recipe, and compose them. When the full problem is complex, design the core computation first and add requirements through iterative refinement.

By subtractive design with this method, the resulting data structures and functions will be defined to match exactly what the task requires, and nothing extra.

## Compose transformations through data and functions

To start composition, take a broad look at the task itself. What is the whole computation? What is all of the data needed for the task?

Use those answers together as the basis for subtractive design, so that the final composition encodes only the structure needed to complete the task, removing any part that does not serve that computation.

Then assemble the data and function composition together along distinct, complementary paths:

- **Compose data structures to build more complex meaning.** Combine values into compound types to represent related facts, or use sum types to represent distinct alternatives. A data structure should never take on extra fields or incidental containers that add no useful meaning to the task.

- **Compose functions to execute more complex computations.** Connect functions into a direct chain that moves the data from its initial inputs to the final result. Do not take unnecessary detours in the dataflow: every function in the chain should advance the computation toward its outcome, without ceremonial wrapper layers or pointless indirection.

Data structures and functions fit together so that every function consumes only the data it needs for its computation, and produces only what the next step expects. A narrow interface is not an attempt at future reuse; it bounds what the function can depend on and keeps each step easy to make clearly correct.

The order of composition and dataflow should build a clear story of the program's execution. When data moves directly through explicit transformations, readers can follow the logic from input to result without having to track ambient state or unravel hidden execution paths.

## Avoid shared mutation hazards

- State may change: model each transition as a function from the current state and input to a new state.
- Constrain how widely values that may change can be referenced; the broader their reach, the more code can observe or depend on their changes. A mutable global is an extreme case.
- Sharing immutable data and mutating an unshared local value are not hazards on their own. Use each language's idiom to keep references to changeable values explicit and their reach bounded.

### Building state machines

- Represent states and allowed transitions explicitly; have each transition return the next state.
- Use examples and tests to check transitions, including boundary cases.

### Integrating with pure glue code

- Where it fits the language, connect transformations and state transitions with pure coordination that passes values explicitly.
- Keep needed mutation within the narrow scope that owns it instead of making a changeable value widely reachable to connect steps.

## Make effects explicit

- Separate pure transformations from effects such as I/O and shared mutation.
- Keep effectful calls and their results visible at the boundary so the functional core remains predictable.

### Interpreting effect programs

- Describe intended effects as a program instead of performing them during core calculations.
- Interpret that program in a thin imperative shell and return its outcomes as values.

## Leave OOP goop behind

- Reject OOP's core principles as hazards, not tools to adopt; the objection is to OOP itself, not just its mutable-state patterns.
- OOP centres classes and object relationships, obscuring data; inheritance does not compose.
- A data API is different: methods owned by a data-oriented type may ergonomically construct, inspect, or transform clear data without adopting OOP's object model.
- Compose algorithms from functions over clear data rather than coordinating behaviour among objects.
