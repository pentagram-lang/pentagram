#!/usr/bin/env python
from __future__ import annotations

import sys

from pentagram.environment import base_environment
from pentagram.guest.call import GuestCall
from pentagram.interpret import interpret
from pentagram.loop import loop
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineValue
from pentagram.parse import parse


def main() -> None:
    if len(sys.argv) == 2:
        arg = sys.argv[1]
        if arg == "--parse":
            parse_loop()
        else:
            main_run(arg)
    else:
        main_loop()


def main_run(
    source_filename: str,
    environment: MachineEnvironment | None = None,
) -> None:
    with open(source_filename, "r") as source_file:
        source_text = source_file.read()
    root_block = parse(source_text)
    root_expression_stack = MachineExpressionStack(
        values=[]
    )
    if not environment:
        environment = base_environment()
    interpret(
        root_block, root_expression_stack, environment
    )
    assert not root_expression_stack, root_expression_stack
    assert "main" in environment, environment.bindings
    main_call = environment["main"]
    assert isinstance(main_call, GuestCall), main_call
    main_expression_stack = MachineExpressionStack(
        values=[]
    )
    interpret(
        main_call.definition_block,
        main_expression_stack,
        main_call.definition_environment,
    )
    if main_expression_stack.values:
        print(main_expression_stack.values)


def main_loop() -> None:
    environment = base_environment().extend()

    def statement_loop(
        statement_text: str,
    ) -> list[MachineValue]:
        block = parse(statement_text)
        expression_stack = MachineExpressionStack(values=[])
        interpret(block, expression_stack, environment)
        return expression_stack.values

    loop(statement_loop)


def parse_loop() -> None:
    loop(parse)


if __name__ == "__main__":
    main()
