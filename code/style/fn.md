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

Remember: functions are computations with direct inputs and outputs. Shared mutable state needs to be avoided because it breaks this contract.

Sharing immutable data is safe, and so is mutating local, unshared data. The hazard is introduced when an external mutation can change the output of a function, or a function's internal mutation changes any externally-owned data.

(Mutations like this are effects, and they are important, like other effects, in limited areas, but they are not suitable for functional code.)

- **Protect functions from external mutation**: Analyze the declared and undeclared inputs of a function, and make sure that function behaviour cannot depend on external changes.

- **Prevent functions from performing external mutation**: Analyze all mutation within a function, and make sure that it only affects locally-owned data.

Use language features where practical for eliminating shared mutable state.

### Building state machines

One useful technique for dealing with shared mutable state is to introduce an explicit state machine that operates as a computation on state data with old state and an event as input, and new state as output.

When written like this, all code is protected from external mutation, leaving state change to specific state transition functions. And the normal data and function design process applies, allowing all of its tools like building examples and testing boundary cases.

## Make effects explicit

There will be a limit to how much of a task can be designed as a computation, because most tasks will also include effects, potentially system interactions, shared mutation, or other operations that can't be fully accomplished as a pure data transformation.

Code should be designed so that the large majority is functions computing data into outputs. This is the most effective way to have the majority of code be clearly correct.

The remaining minority can also be made clearly correct by making sure that effects are only present in boundary code and making sure that they are highly visible and easy to understand.

This setup can be referred to as **functional core, imperative shell**. The functional core is easy to read and test because there are no effects, and the imperative shell is easy to maintain because it is very thin.

### Interpreting effect programs

One useful technique for partly converting effects into computation is to represent effects as data that can be composed. Then the composed effect data is run through one interpreter for a real imperative shell that triggers real effects, and one or more test interpreters that often include some level of simulation or playback.

When the choice of one effect depends on the result of a previous effect, the composed effect data structure will often include a closure for delayed code execution. Technically this is a form of monadic composition, and the result can be run using a **monadic interpreter**.

Whether combining effects needs the full power of a monad or can be something simpler (like list concatenation), ideally all of the pure effect coordination code should be restricted to a glue layer, so that most other functions can continue working with normal, non-effect data.

The benefit of a setup like this is that the glue code and the code that it integrates with can be written and tested as basic data composition, instead of requiring more complex integration tests that would be needed for working with real effects.

## Leave OOP goop behind

Reject popular Object-Oriented Programming (OOP) doctrine as toxic "goop" that will corrode good data and function design. The objection is to OOP itself: when code is organized around objects and inheritance, all data becomes obscured behind ceremonies of indirection and attached behaviour.

Encapsulation, the central virtue of OOP, actually conflates two separate engineering needs: data composition and strong privacy. Data composition groups related facts into larger types, which belongs entirely to functional data design. Strong privacy bounds visibility and protects internal invariants, which belongs entirely to module boundaries.

With functional programming (this guide) handling data composition and [partitioning](part.md) handling strong privacy, what remains of OOP is just goop: rigid class hierarchies that do not compose, state trapped inside opaque instances, and artificial noun-objects invented to manage other objects.

Do not confuse a data API with OOP. Methods associated with a data type—such as constructors, inspectors, or functional transformations—are simply ergonomic syntax for functions operating on that data. They provide readable call chains without adopting OOP's object model or introducing inheritance hierarchies.

Also, language features like traits and dynamic dispatch are not OOP doctrine. Even when the syntax looks object-oriented, they are simply other tools that can be used for designing data and functions.

Stick to the data and functions that match exactly what the task requires, and there will be no need for the mutable object graphs that OOP devolves into.
