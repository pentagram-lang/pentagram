from __future__ import annotations

from numpy import int32
from pentagram.interpret.block import interpret_block
from pentagram.interpret.test import init_test_frame_stack
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineNumber
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxNumber


def test_interpret_block_enter() -> None:
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxNumber(value=int32(4))])]
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


def test_interpret_block_exit() -> None:
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxNumber(value=int32(4))])]
    )
    frame_stack = init_test_frame_stack(
        block, MachineExpressionStack([]), statement_index=1
    )
    interpret_block(frame_stack)
    assert frame_stack == MachineFrameStack([])
