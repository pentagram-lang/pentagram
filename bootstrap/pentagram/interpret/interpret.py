from __future__ import annotations

from pentagram.interpret.block import interpret_block
from pentagram.machine import Machine
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineFrame
from pentagram.machine import MachineInstructionPointer
from pentagram.syntax import SyntaxBlock


def interpret(
    block: SyntaxBlock,
    expression_stack: MachineExpressionStack,
    environment: MachineEnvironment,
) -> None:
    machine = init_machine(
        block, expression_stack, environment
    )
    while machine.frames:
        interpret_block(machine)


def init_machine(
    block: SyntaxBlock,
    expression_stack: MachineExpressionStack,
    environment: MachineEnvironment,
    statement_index: int = 0,
    term_index: int = 0,
) -> Machine:
    return Machine(
        frames=[
            MachineFrame(
                instruction_pointer=MachineInstructionPointer(
                    block=block,
                    statement_index=statement_index,
                    term_index=term_index,
                ),
                environment=environment,
            )
        ],
        expression_stack=expression_stack,
    )
