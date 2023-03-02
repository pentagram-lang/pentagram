from __future__ import annotations

from pentagram.interpret.statement import (
    interpret_statement,
)
from pentagram.machine import Machine


def interpret_block(machine: Machine) -> None:
    block = machine.current_frame.block
    statement_index = machine.current_frame.statement_index
    if statement_index < len(block.statements):
        interpret_statement(machine)
    else:
        machine.pop_frame()
