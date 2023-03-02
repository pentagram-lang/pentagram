from __future__ import annotations

from numpy import int32
from pentagram.guest.call import GuestCall
from pentagram.interpret.interpret import init_machine
from pentagram.interpret.statement import (
    interpret_statement,
)
from pentagram.interpret.test import init_test_machine
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
    machine = init_test_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
    )
    interpret_statement(machine)
    assert machine == init_test_machine(
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
    machine = init_test_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(100))]
        ),
        term_index=1,
    )
    interpret_statement(machine)
    assert machine == init_test_machine(
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
    machine = init_test_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
    )
    interpret_statement(machine)
    environment = machine.current_frame.environment
    assert machine == init_machine(
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
