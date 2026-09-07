# Pentagram

Pentagram is a language project for clear reasoning. This document states the shared contributor standard and gives the repository a short path to its governing documents, working systems, and operational tools.

Contributors are Pentagram's internal developers, whether human or agent. This standard governs every change to Pentagram's code, documentation, tooling, and processes. It does not impose contribution obligations on developers writing programs in Pentagram.

Use the [manifesto](manifesto.md) to guide almost every contribution decision. Its three connected aims are **ergonomics**, reducing cognitive friction in use and change; **determinism**, making meaning and behaviour follow predictably from explicit conditions; and **efficiency**, avoiding unnecessary manual and automatic work.

Every contribution must **embody and support** each applicable aim: realize it in the system being changed and help realize it across Pentagram.

**Clearly correct is the acceptance standard for every contribution.** Correct means satisfying the actual requirements, including those arising from the manifesto aims. Clearly means the contribution and its evidence make that satisfaction understandable and justified. For documentation and processes, this includes being simple enough to understand quickly and follow correctly.

Contributions must embody and support this standard too: be clearly correct themselves and preserve or improve the conditions for other clearly correct contributions. Understandable contracts, trustworthy components, and useful checks can provide that support.

Use practical evidence appropriate to the requirements and risks. The acceptance standard stays firm; it does not require identical checks or complete formal proof for every change. The manifesto aims remain requirements, not optional polish after correctness.

## Buildkite

The [Buildkite CI](.buildkite/README.md) document describes the merge-gate pipeline and how to inspect its builds.

## License

The [license](LICENSE.md) states the terms for using and changing the repository.

## Code

[Coding standards](code/README.md) guide implementation and implementation tests.

## Documentation standards

[Documentation standards](doc/README.md) define how repository documentation gives meaning a durable, navigable form.

## Environment engineering

[Environment engineering](env/README.md) defines how documentation and code are intentionally designed together as an environment for positive and effective language development.

## Manifesto

The [manifesto](manifesto.md) records Pentagram's aspirational principles and language direction.

## Project

The [project workflow](proj/README.md) defines how contributors plan, execute, check, and reconcile work.

## Setup

The [setup document](setup.md) explains how to install the repository's Nix profile and initialize its Jujutsu workspace.

## Source control

The [source-control document](source-control.md) defines Pentagram's Jujutsu repository model, mutable-change workflow, recovery boundary, and branch-publication process.

## System

The [system document](sys.md) defines the instructions and authority for agents working in the repository.

## Tour

The [language tour](tour/README.md) presents aspirational Pentagram syntax and semantics.

## Command plane

The [command plane](zero/README.md) documents the `0` commands for formatting, validation, tests, agents, and project control.
