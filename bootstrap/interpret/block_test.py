from interpret.block import interpret_block
from interpret.test import init_test_frame_stack
from machine import MachineExpressionStack
from machine import MachineFrameStack
from machine import MachineNumber
from numpy import int32
from syntax import SyntaxBlock
from syntax import SyntaxExpression
from syntax import SyntaxNumber


def test_interpret_block_enter():
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxNumber(int32(4))])]
    )
    frame_stack = init_test_frame_stack(
        block, MachineExpressionStack([])
    )
    interpret_block(frame_stack)
    assert frame_stack == init_test_frame_stack(
        block,
        MachineExpressionStack([MachineNumber(int32(4))]),
        term_index=1,
    )


def test_interpret_block_exit():
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxNumber(int32(4))])]
    )
    frame_stack = init_test_frame_stack(
        block, MachineExpressionStack([]), statement_index=1
    )
    interpret_block(frame_stack)
    assert frame_stack == MachineFrameStack([])
