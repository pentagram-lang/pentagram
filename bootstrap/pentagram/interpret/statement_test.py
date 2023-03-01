from __future__ import annotations

from numpy import int32
from pentagram.guest.call import GuestCall
from pentagram.interpret.interpret import init_frame_stack
from pentagram.interpret.statement import (
    interpret_statement,
)
from pentagram.interpret.test import init_test_frame_stack
from pentagram.interpret.test import make_test_environment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineNumber
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber


def test_interpret_expression_enter() -> None:
    statement = SyntaxExpression(
        terms=[SyntaxNumber(value=int32(100))]
    )
    frame_stack = init_test_frame_stack(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
    )
    interpret_statement(frame_stack)
    assert frame_stack == init_test_frame_stack(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(100))]
        ),
        term_index=1,
    )


def test_interpret_expression_exit() -> None:
    statement = SyntaxExpression(
        terms=[SyntaxNumber(value=int32(100))]
    )
    frame_stack = init_test_frame_stack(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(100))]
        ),
        term_index=1,
    )
    interpret_statement(frame_stack)
    assert frame_stack == init_test_frame_stack(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(100))]
        ),
        statement_index=1,
        term_index=0,
    )


def test_interpret_method_definition_exit() -> None:
    statement = SyntaxMethodDefinition(
        binding=SyntaxIdentifier(name="f"),
        block=SyntaxBlock(
            statements=[
                SyntaxExpression(
                    terms=[SyntaxIdentifier(name="sqrt")]
                ),
            ]
        ),
    )
    frame_stack = init_test_frame_stack(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
    )
    interpret_statement(frame_stack)
    environment = frame_stack.current.environment
    assert frame_stack == init_frame_stack(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
        environment,
        statement_index=1,
    )
    assert environment.base == make_test_environment().base
    assert environment.bindings == {
        "f": GuestCall(
            definition_environment=environment,
            definition_block=statement.block,
        )
    }
