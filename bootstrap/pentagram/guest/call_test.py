from __future__ import annotations

from numpy import int32
from pentagram.guest.call import GuestCall
from pentagram.interpret import interpret
from pentagram.interpret.test import init_test_frame_stack
from pentagram.interpret.test import make_test_environment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineFrame
from pentagram.machine import MachineInstructionPointer
from pentagram.machine import MachineNumber
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber


def test_call_push_frame() -> None:
    call = GuestCall(
        definition_environment=make_test_environment(),
        definition_block=SyntaxBlock(
            [SyntaxExpression([SyntaxIdentifier(name="g")])]
        ),
    )
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier(name="f")])]
    )
    frame_stack = init_test_frame_stack(
        block,
        MachineExpressionStack([MachineNumber(int32(9))]),
    )
    call(frame_stack)
    assert len(frame_stack) == 2
    assert (
        frame_stack.frames[0]
        == init_test_frame_stack(
            block,
            MachineExpressionStack(
                [MachineNumber(int32(9))]
            ),
            term_index=1,
        ).frames[0]
    )
    assert frame_stack.frames[1] == MachineFrame(
        instruction_pointer=MachineInstructionPointer(
            block=call.definition_block,
            statement_index=0,
            term_index=0,
        ),
        environment=make_test_environment().extend(),
        expression_stack=MachineExpressionStack(
            [MachineNumber(int32(9))]
        ),
    )


def test_call_delegate_to_host_call() -> None:
    call = GuestCall(
        definition_environment=make_test_environment(),
        definition_block=SyntaxBlock(
            [
                SyntaxExpression(
                    [SyntaxIdentifier(name="sqrt")]
                )
            ]
        ),
    )
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier(name="f")])]
    )
    expression_stack = MachineExpressionStack(
        [MachineNumber(int32(16))]
    )
    environment = make_test_environment({"f": call})
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        [MachineNumber(int32(4))]
    )


def test_call_generate_values() -> None:
    call = GuestCall(
        definition_environment=make_test_environment(),
        definition_block=SyntaxBlock(
            [
                SyntaxExpression(
                    [
                        SyntaxNumber(value=int32(2)),
                        SyntaxNumber(value=int32(3)),
                        SyntaxNumber(value=int32(4)),
                    ]
                )
            ]
        ),
    )
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier(name="seq")])]
    )
    expression_stack = MachineExpressionStack(
        [MachineNumber(int32(1))]
    )
    environment = make_test_environment({"seq": call})
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        [
            MachineNumber(int32(1)),
            MachineNumber(int32(2)),
            MachineNumber(int32(3)),
            MachineNumber(int32(4)),
        ]
    )
