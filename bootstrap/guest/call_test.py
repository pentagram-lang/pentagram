from guest.call import GuestCall
from interpret import interpret
from interpret.test import init_test_frame_stack
from interpret.test import test_environment
from machine import MachineExpressionStack
from machine import MachineFrame
from machine import MachineInstructionPointer
from machine import MachineNumber
from numpy import int32
from syntax import SyntaxBlock
from syntax import SyntaxExpression
from syntax import SyntaxIdentifier
from syntax import SyntaxNumber


def test_call_push_frame():
    call = GuestCall(
        definition_environment=test_environment(),
        definition_block=SyntaxBlock(
            [SyntaxExpression([SyntaxIdentifier("g")])]
        ),
    )
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("f")])]
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
        environment=test_environment().extend(),
        expression_stack=MachineExpressionStack(
            [MachineNumber(int32(9))]
        ),
    )


def test_call_delegate_to_host_call():
    call = GuestCall(
        definition_environment=test_environment(),
        definition_block=SyntaxBlock(
            [SyntaxExpression([SyntaxIdentifier("sqrt")])]
        ),
    )
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("f")])]
    )
    expression_stack = MachineExpressionStack(
        [MachineNumber(int32(16))]
    )
    environment = test_environment({"f": call})
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        [MachineNumber(int32(4))]
    )


def test_call_generate_values():
    call = GuestCall(
        definition_environment=test_environment(),
        definition_block=SyntaxBlock(
            [
                SyntaxExpression(
                    [
                        SyntaxNumber(int32(2)),
                        SyntaxNumber(int32(3)),
                        SyntaxNumber(int32(4)),
                    ]
                )
            ]
        ),
    )
    block = SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("seq")])]
    )
    expression_stack = MachineExpressionStack(
        [MachineNumber(int32(1))]
    )
    environment = test_environment({"seq": call})
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        [
            MachineNumber(int32(1)),
            MachineNumber(int32(2)),
            MachineNumber(int32(3)),
            MachineNumber(int32(4)),
        ]
    )
