from __future__ import annotations

from pentagram.interpret.block import interpret_block
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineFrame
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineInstructionPointer
from pentagram.syntax import SyntaxBlock


def interpret(
    block: SyntaxBlock,
    expression_stack: MachineExpressionStack,
    environment: MachineEnvironment,
) -> None:
    frame_stack = init_frame_stack(
        block, expression_stack, environment
    )
    while frame_stack:
        interpret_block(frame_stack)


def init_frame_stack(
    block: SyntaxBlock,
    expression_stack: MachineExpressionStack,
    environment: MachineEnvironment,
    statement_index: int = 0,
    term_index: int = 0,
) -> MachineFrameStack:
    return MachineFrameStack(
        frames=[
            MachineFrame(
                instruction_pointer=MachineInstructionPointer(
                    block=block,
                    statement_index=statement_index,
                    term_index=term_index,
                ),
                expression_stack=expression_stack,
                environment=environment,
            )
        ]
    )
