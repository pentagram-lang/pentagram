from __future__ import annotations

from numpy import int32
from pentagram.guest.call import GuestCall
from pentagram.interpret import interpret
from pentagram.interpret.test import init_test_machine
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
            statements=[
                SyntaxExpression(
                    terms=[SyntaxIdentifier(name="g")]
                )
            ]
        ),
    )
    block = SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="f")]
            )
        ]
    )
    machine = init_test_machine(
        block,
        MachineExpressionStack(
            values=[MachineNumber(value=int32(9))]
        ),
    )
    call(machine)
    assert len(machine.frames) == 2
    assert (
        machine.frames[0]
        == init_test_machine(
            block,
            MachineExpressionStack(values=[]),
            term_index=1,
        ).frames[0]
    )
    assert machine.frames[1] == MachineFrame(
        instruction_pointer=MachineInstructionPointer(
            block=call.definition_block,
            statement_index=0,
            term_index=0,
        ),
        environment=make_test_environment().extend(),
    )
    assert (
        machine.expression_stack
        == MachineExpressionStack(
            values=[MachineNumber(value=int32(9))]
        )
    )


def test_call_delegate_to_host_call() -> None:
    call = GuestCall(
        definition_environment=make_test_environment(),
        definition_block=SyntaxBlock(
            statements=[
                SyntaxExpression(
                    terms=[SyntaxIdentifier(name="sqrt")]
                )
            ]
        ),
    )
    block = SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="f")]
            )
        ]
    )
    expression_stack = MachineExpressionStack(
        values=[MachineNumber(value=int32(16))]
    )
    environment = make_test_environment({"f": call})
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        values=[MachineNumber(value=int32(4))]
    )


def test_call_generate_values() -> None:
    call = GuestCall(
        definition_environment=make_test_environment(),
        definition_block=SyntaxBlock(
            statements=[
                SyntaxExpression(
                    terms=[
                        SyntaxNumber(value=int32(2)),
                        SyntaxNumber(value=int32(3)),
                        SyntaxNumber(value=int32(4)),
                    ]
                )
            ]
        ),
    )
    block = SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="seq")]
            )
        ]
    )
    expression_stack = MachineExpressionStack(
        values=[MachineNumber(value=int32(1))]
    )
    environment = make_test_environment({"seq": call})
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        values=[
            MachineNumber(value=int32(1)),
            MachineNumber(value=int32(2)),
            MachineNumber(value=int32(3)),
            MachineNumber(value=int32(4)),
        ]
    )
