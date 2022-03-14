from interpret.block import interpret_block
from machine import MachineEnvironment
from machine import MachineExpressionStack
from machine import MachineFrame
from machine import MachineFrameStack
from machine import MachineInstructionPointer
from syntax import SyntaxBlock


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
        [
            MachineFrame(
                MachineInstructionPointer(
                    block, statement_index, term_index
                ),
                expression_stack,
                environment,
            )
        ]
    )
