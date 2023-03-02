from __future__ import annotations

from numpy import int32
from pentagram.host.simple_call import sqrt
from pentagram.host.value import PI
from pentagram.interpret.term import (
    interpret_expression_term,
)
from pentagram.interpret.test import init_test_machine
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineNumber
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from typing import cast


def test_interpret_number() -> None:
    term = SyntaxNumber(value=int32(100))
    expression = SyntaxExpression(terms=[term])
    machine = init_test_machine(
        SyntaxBlock(statements=[expression]),
        MachineExpressionStack(values=[]),
    )
    interpret_expression_term(machine, expression)
    assert machine == init_test_machine(
        SyntaxBlock(statements=[expression]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(100))]
        ),
        term_index=1,
    )


def test_interpret_identifier_value() -> None:
    term = SyntaxIdentifier(name=PI.name)
    expression = SyntaxExpression(terms=[term])
    expression_stack = MachineExpressionStack(values=[])
    machine = init_test_machine(
        SyntaxBlock(statements=[expression]),
        expression_stack,
    )
    interpret_expression_term(machine, expression)
    assert machine == init_test_machine(
        SyntaxBlock(statements=[expression]),
        MachineExpressionStack(
            values=[cast(MachineValue, PI.value_or_call)]
        ),
        term_index=1,
    )


def test_interpret_identifier_call() -> None:
    term = SyntaxIdentifier(name=sqrt.name)
    expression = SyntaxExpression(terms=[term])
    expression_stack = MachineExpressionStack(
        values=[MachineNumber(value=int32(16))]
    )
    machine = init_test_machine(
        SyntaxBlock(statements=[expression]),
        expression_stack,
    )
    interpret_expression_term(machine, expression)
    assert machine == init_test_machine(
        SyntaxBlock(statements=[expression]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(4))]
        ),
        term_index=1,
    )
