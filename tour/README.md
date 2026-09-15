# Pentagram Tour — Aspirational Design

> **Status: Aspirational design**
>
> This document describes the intended Pentagram language, not the behaviour currently implemented in this repository. Treat its syntax, semantics, and examples as design requirements under review. Establish current behaviour from tracked implementation, tests, and factual documentation.

## Contents

- [1. Fundamentals](#1-fundamentals)
  - [Hello World](#hello-world)
  - [Comments](#comments)
  - [Variable Assignment](#variable-assignment)
- [2. Primitive Values](#2-primitive-values)
  - [Numbers](#numbers)
  - [Text](#text)
  - [Booleans](#booleans)
- [3. Data Structures](#3-data-structures)
  - [Literal Collections](#literal-collections)
  - [Value Wrappers](#value-wrappers)
  - [Field Access](#field-access)
- [4. Functions and Control Flow](#4-functions-and-control-flow)
  - [Postfix and Prefix Notation](#postfix-and-prefix-notation)
  - [Conditionals](#conditionals)
  - [Loops](#loops)
  - [Function Definition](#function-definition)
  - [Named Arguments](#named-arguments)
  - [Closures](#closures)
- [5. The Type System](#5-the-type-system)
  - [Type Annotations](#type-annotations)
  - [Custom Types](#custom-types)
  - [Specifications (Traits)](#specifications-traits)
  - [Generics](#generics)
  - [Higher-Kinded Types](#higher-kinded-types)
- [6. Error Handling](#6-error-handling)
  - [Error Declaration & Handling](#error-declaration--handling)
  - [Error Context & Marks](#error-context--marks)
  - [Crashes](#crashes)
- [7. Modules & Exports](#7-modules--exports)
  - [Visibility & Exports](#visibility--exports)
  - [Imports](#imports)
  - [Privacy Bypassing](#privacy-bypassing)
- [8. Testing](#8-testing)
  - [Basic Tests](#basic-tests)
  - [Parameterized Tests](#parameterized-tests)
- [9. Advanced Syntax](#9-advanced-syntax)
  - [Custom Block Delimiters](#custom-block-delimiters)

## 1. Fundamentals

Let's start with the absolute basics. Here you'll see how to write a simple program, make notes in your code with comments, and name values using variables.

### Hello World

The simplest program in Pentagram prints a message. Functions, like `say`, are placed after the data they operate on.

```pentagram
'Hello world!' say,
```

### Comments

You can write comments to leave notes for yourself or other programmers. They start and end with `--` and can span multiple lines.

```pentagram
-- This is a comment --
--
This is a comment that
spans multiple lines.
--
--- You can add more hyphens -- to nest comments ---
```

### Variable Assignment

Variables are used to give names to values. In Pentagram, variables are immutable; when you "change" a variable, you are actually creating a new one with the same name that shadows the old one. This makes code more predictable.

```pentagram
-- Create two variables and use them together --
foo = 40,
bar = 2,
baz = foo bar +,

-- Each binding creates a new variable in a nested scope --
x = 1,           -- x is 1 --
x = x 2 +,       -- A new x is created with the value 3 --
x = x 3 *,       -- Another new x is created with the value 9 --

-- The `_=` syntax is sugar for this common rebinding pattern --
x = 1,
x _= 2 +,        -- Equivalent to: x = x 2 +, --

y = sv 1, 2 end-sv,
y _= 3 pushr,    -- Equivalent to: y = y 3 pushr, --

-- Rebinding a record's field creates a new record --
x = y: 1 z,
x.y = 2,         -- Sugar for: x = x 2 z.set-y, --
```

## 2. Primitive Values

Pentagram includes a standard set of primitive value types for representing simple data. All operations, including arithmetic and comparisons, are treated as regular postfix functions.

### Numbers

Numbers support standard arithmetic operations.

```pentagram
foo-1 = 1 2 +,
foo-2 = foo-1 3 -,
foo-3 = foo-2 4 *,
foo-4 = foo-3 5 /,

-- Negation is a special suffix operator --
foo-1 = 1-,
foo-2 = foo-1-,
```

### Text

Text values support concatenation and interpolation. There are no backslash escapes; instead, special characters are handled with square-bracket syntax, and literal quotes can be included by using different outer quotes.

```pentagram
-- Interpolation and concatenation --
foo = 'e',
bar = 'abc' 'd[foo]' cat,

-- Sugar for special characters --
foo = 'a[nl]b[tb]c',

-- Using alternative quotes to include literal quotes --
foo = "a'b'",
bar = `a'"b'`,
```

### Booleans

Booleans support standard logic operators, which will short-circuit. All comparison operators are spelled-out functions for clarity.

```pentagram
-- Logic operators --
foo-1 = true f false g and,
foo-2 = true f false g or,
foo-3 = true not,

-- Comparison operators --
foo-1 = 1 2 eq,      -- Equal --
foo-2 = 3 4 ne,      -- Not equal --
foo-3 = 5 6 gt,      -- Greater than --
foo-4 = 7 8 gte,     -- Greater than or equal to --
foo-5 = 9 10 lt,     -- Less than --
foo-6 = 11 12 lte,   -- Less than or equal to --
```

## 3. Data Structures

Pentagram provides both literal collections for simple data grouping and specialized wrapper types that add semantics like optionality, reference, or mutability.

### Literal Collections

Pentagram has built-in syntax for common, un-typed collections. These resolve to default types if not constrained by the context.

```pentagram
foo = gv 1, 2, 3 end-gv,    -- A group of unordered values --
bar = sv 1, 2, 3 end-sv,    -- A sequence of ordered values --
baz = kv 1 'a', 2 3 end-kv, -- A map of keyed values --
```

### Value Wrappers

These types provide wrappers for values to give them different semantics.

```pentagram
foo = nil,     -- Represents an absent value --
bar = 1 val,   -- Represents an optional value that is present --

baz = 1 ref,   -- An immutable reference to a value --

qux = 1 mut,   -- A mutable box for holding state --

quux = 1 laz,  -- A lazily-computed value --
```

### Field Access

The `.` operator is used to access named fields on records, while the `*` operator is syntactic sugar for accessing the primary wrapped value of a wrapper type.

```pentagram
x = 1 ref,
y = x*,                    -- Reads the value via ref.get-value --
x* = 2,                    -- Rebinds x to a new ref via ref.set-value --

x = 1 laz,
y = x*,                    -- Forces computation via laz.get-value --

-- Optional values must be narrowed before accessing the value --
x = 1 val,
if x.is-val begin
  y = x*                   -- Accesses the value inside the 'val' --
end-if,

-- Mutable boxes are the main exception to the rebinding rule --
x = 1 mut,
y = x*,                    -- Reads the value via mut.get-value --
x 2 write-mut,             -- This performs actual mutation. There is no sugar --
```

## 4. Functions and Control Flow

All programs are built from functions and control-flow structures. This section covers how Pentagram defines and calls functions, how to branch logic with conditionals, and how to loop.

### Postfix and Prefix Notation

Pentagram has two ways to call functions. The default is **postfix**, which is ideal for chaining operations.

```pentagram
-- Postfix style reads like a series of transformations --
result = 5 2 + 3 *,   -- (5 + 2) * 3 --
```

For functions that take blocks of code or have complex arguments, **prefix notation** can be clearer. This is done by wrapping the function's arguments in a `with-<fn-name>...end-<fn-name>` block.

```pentagram
-- Calling the 'map' function with prefix notation --
numbers = sv 1, 2, 3 end-sv,
doubled = with-map
  numbers,
  fn n begin n 2 * end-fn,
end-map,

-- This is equivalent to the postfix version --
doubled = numbers fn n begin n 2 * end-fn map,
```

### Conditionals

Conditional `if` blocks are used to branch execution based on a boolean value.

```pentagram
if condition begin
  'true branch' say
elif other-condition begin
  'elif branch' say
else
  'false branch' say
end-if,

-- Conditionals are also used to narrow tagged union variants --
if pet.is-dog begin
  -- Inside this branch, pet is known to be a dog --
  pet.breed say
end-if,
```

### Loops

Pentagram provides `loop` for infinite loops and `while` for conditional loops.

```pentagram
-- An infinite loop --
loop
  'forever' say
end-loop,

-- A conditional loop --
while condition begin
  'looping' say
end-while,
```

### Function Definition

Use `def fn` to define a named function. Type annotations can be used for parameters and return values.

```pentagram
def f fn
  par x i8,
  par y i8,
  i8
begin
  z = 1 ty i8 end-ty as,
  x y + z +
end-fn,
```

### Named Arguments

Function arguments can be passed by name. This is often used for clarity, especially for functions with many parameters.

```pentagram
-- Passing arguments by name in postfix notation --
foo = name: 'dog' sound: 'bark' animal,

-- Named arguments also work well with prefix notation --
bar = with-animal
  name: 'cat',
  sound: 'meow',
end-animal,
```

### Closures

Anonymous functions, or closures, can be defined inline and capture immutable variables from their outer scope.

```pentagram
-- A closure that captures 'x' --
x = 10,
add-x = fn y begin y x + end-fn,
result = 5 add-x.call,  -- result is 15 --

-- Each closure captures the values in scope when it is created --
base = 5,
f1 = fn x begin x base + end-fn,
base = 10,
f2 = fn x begin x base + end-fn,
-- f1.call will add 5; f2.call will add 10 --
```

## 5. The Type System

Pentagram has a strong, nominal type system designed to ensure correctness while remaining ergonomic. It supports generics, traits (called specifications), and even higher-kinded types.

### Type Annotations

In Pentagram, variables themselves are untyped; they simply hold values. Type annotations are applied to values on the expression stack using `ty` fences.

```pentagram
-- Annotating a value on the stack --
x = 42 ty i8 end-ty as,

-- Type fences can wrap complex expressions --
result = 1 ty i8 end-ty as 2 ty i8 end-ty as +,

-- Variables bind to the typed value --
y = x,
```

### Custom Types

You can define your own data structures using **Records** (for grouping data) and **Tagged Unions** (for variations).

#### Records

Records are product types with named fields.

```pentagram
-- Define a record --
def person rec
  par name txt,
  par age u8,
end-rec,

-- Create an instance --
p = person name: 'Alice' age: 30,

-- Access fields --
p-name = p person.name,
```

#### Tagged Unions

Tagged unions allow you to define a type that can be one of several variants.

```pentagram
-- Define a tag --
def shape tag,

-- Define variants --
def shape.circle rec
  par radius f32,
end-rec,

def shape.square rec
  par side-length f32,
end-rec,
```

### Specifications (Traits)

Specifications (or "specs") define shared behaviour that different types can implement. This is similar to interfaces or traits in other languages.

```pentagram
-- Define a specification --
def serializable spec
  tpar t type,
end-spec,
def serializable.to-bytes fn
  par self t,
  byte-seq
end-fn,

-- Implement the spec for a type --
def developer-serializable impl developer serializable end-impl,
def developer-serializable.to-bytes fn
  par self developer,
  byte-seq
begin
  self.id to-bytes
end-fn,
```

### Generics

Types and functions can be generic, allowing them to work with any type that satisfies certain constraints.

#### Generic Types

```pentagram
-- A generic record --
def box rec
  tpar t type,
  par value t,
end-rec,

-- Explicit and inferred type parameters --
x = 1 ty value: i8 box end-ty as, -- Explicit --
y = 2 ty box end-ty as,           -- Inferred --
z = 3 box,                        -- Fully inferred --

-- A generic tagged union --
def result tag
  tpar ok type,
  tpar err type,
end-tag,

def result.success rec
  par value result.ok,
end-rec,

def result.failure rec
  par error result.err,
end-rec,
```

#### Generic Functions

Functions can declare type parameters (`tpar`) and apply constraints (like requiring a type to implement `ord`).

```pentagram
def max fn
  tpar t type,
  par a t,
  par b t,
  t ord,                -- Constraint: t must implement ord --
  t
begin
  if a b gt begin a else b end-if
end-fn,
```

### Higher-Kinded Types

Pentagram supports higher-kinded types, meaning type parameters can themselves be generic (like a type constructor). This allows for powerful abstractions like `functor`.

```pentagram
-- The functor spec operates on a type constructor 'f' --
def functor spec
  tpar f fn tpar t type, type end-fn,
end-spec,

def functor.map fn
  tpar a type,
  tpar b type,
  par self a functor.f.call,
  par transform fn par x a, b end-fn,
  b functor.f.call
end-fn,

-- Implementing functor for 'box' --
def box-functor impl
  f: fn t begin t box end-fn box functor
end-impl,

def box-functor.map fn
  tpar a type,
  tpar b type,
  par self a box,
  par transform fn par x a, b end-fn,
  b box
begin
  self* transform.call box
end-fn,
```

## 6. Error Handling

Pentagram treats error handling as a core part of the program's logic, not an afterthought. Errors are explicit, typed, and context-aware, ensuring you always know where and why things might go wrong.

### Error Declaration & Handling

Functions that can fail must explicitly declare `err` in their signature. Callers are then required to handle this possibility, either by propagating the error with `?` or capturing it with `try`.

```pentagram
-- Functions declare 'err' if they can fail --
def f fn
  par x bool,
  err,
  bool
begin
  if x begin
    note: 'condition was true' err? -- Propagate an error --
  else
    false
  end-if
end-fn,

-- Handling the error --
-- 1 f,        -- Compile error: must handle the error --
y = 1 f?,      -- Propagate the error to the caller --
z = 1 f.try,   -- Capture the error in a 'result' type --
```

### Error Context & Marks

Unlike exceptions in other languages, Pentagram errors don't carry data themselves. Instead, context is provided by **marks**—values attached to the current scope. When an error occurs, the runtime captures all active marks.

```pentagram
-- Define typed marks for context --
def file-path mark txt end-mark,
def retry-count mark u8 end-mark,

def open-file fn
  par path txt,
  err,
  file
begin
  -- Apply marks to the following block --
  > path file-path,
  > 0 retry-count,
  path open-internal?    -- If this fails, marks are captured --
end-fn,

-- Reading captured marks --
result = 'data.txt' open-file.try,
if result.is-err begin
  -- Retrieve context from the captured error --
  path = result.err get-mark ty file-path opt end-ty as,
end-if,
```

### Crashes

A **crash** is different from an error: it indicates a bug or an unrecoverable state (like a failed assertion) and terminates the current task immediately.

```pentagram
-- Terminate immediately --
if bad-state begin
  crash
end-if,

-- 'must' asserts a condition and crashes if it's false --
x 0 gt must,

-- Crashes also capture marks for diagnostics --
> 'validating input' note,
input valid must,
```

## 7. Modules & Exports

Modules help you organize your code into namespaces and control what is visible to the rest of the program.

### Visibility & Exports

By default, everything defined in a module is private. To make a function or type available to other modules, you must explicitly mark it with `pub`.

```pentagram
def utils mod
  -- This helper is private to the module --
  def helper fn
    par x i8,
    i8
  begin
    x 2 *
  end-fn,

  -- This function is public and can be imported --
  pub def process fn
    par x i8,
    i8
  begin
    x helper
  end-fn
end-mod,
```

### Imports

Use the `use` keyword to bring public items from other modules into your current scope. You can rename imports with `as` to avoid conflicts or shorten names.

```pentagram
-- Import a specific item --
use pkg.utils.process,
result = 5 process,

-- Import with an alias --
use pkg.utils.process as p,
result = 5 p,
```

### Privacy Bypassing

Sometimes, especially when writing tests, you need to access private implementation details. Pentagram allows you to bypass visibility rules explicitly using `non-pub`.

```pentagram
-- Explicitly import a private item --
use pkg.utils.internal-helper non-pub,

-- A common pattern for testing internal logic --
def utils.test mod
  use pkg.utils.internal-helper non-pub,

  test
    result = 5 internal-helper,
    result 10 eq assert
  end-test
end-mod,
```

## 8. Testing

Testing is built directly into the language. You can define tests right alongside your code, making it easy to verify correctness.

### Basic Tests

A `test` block isolates test logic. Inside, you can perform operations and use `assert` to verify results.

```pentagram
test
  x = 1 2 +,
  x 3 eq assert
end-test,
```

### Parameterized Tests

For testing multiple inputs against expected outputs, you can use **rich comments**. These allow you to define a table of test cases that are passed as arguments to the test block.

```pentagram
--
Check addition works correctly

==
1 2 3 test-case,
5 7 12 test-case,
0 0 0 test-case,
==
--
test
  par a i8,
  par b i8,
  par expected i8
begin
  a b + expected eq assert
end-test,
```

## 9. Advanced Syntax

Pentagram includes a few specialized syntax features to help manage complexity in large or deeply nested codebases.

### Custom Block Delimiters

When you have many nested blocks, it can be hard to tell which `end-if` or `end-loop` closes which block. You can add custom markers to delimiters to make the structure explicit.

```pentagram
-- A marked conditional block --
if-'marker' condition begin
  'marked branch' say
end-if-'marker',
```
