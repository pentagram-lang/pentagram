from interpret.statement import interpret_statement
from machine import MachineFrameStack


def interpret_block(frame_stack: MachineFrameStack) -> None:
    block = frame_stack.current.block
    statement_index = frame_stack.current.statement_index
    if statement_index < len(block.statements):
        interpret_statement(frame_stack)
    else:
        frame_stack.pop()
