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
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber
from pentagram.syntax import SyntaxStatement


def init_statement_block(
    statement: SyntaxStatement,
) -> SyntaxBlock:
    return SyntaxBlock([statement])


def test_interpret_expression_enter() -> None:
    statement = SyntaxExpression(
        [SyntaxNumber(value=int32(100))]
    )
    frame_stack = init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([]),
    )
    interpret_statement(frame_stack)
    assert frame_stack == init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([MachineNumber(int32(100))]),
        term_index=1,
    )


def test_interpret_expression_exit() -> None:
    statement = SyntaxExpression(
        [SyntaxNumber(value=int32(100))]
    )
    frame_stack = init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([MachineNumber(int32(100))]),
        term_index=1,
    )
    interpret_statement(frame_stack)
    assert frame_stack == init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([MachineNumber(int32(100))]),
        statement_index=1,
        term_index=0,
    )


def test_interpret_assignment_1_enter() -> None:
    statement = SyntaxAssignment(
        terms=[SyntaxNumber(value=int32(3))],
        bindings=[SyntaxIdentifier(name="x")],
    )
    frame_stack = init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([MachineNumber(int32(4))]),
    )
    interpret_statement(frame_stack)
    assert len(frame_stack) == 2
    assert (
        frame_stack.frames[1].instruction_pointer
        is frame_stack.frames[0].instruction_pointer
    )
    assert (
        frame_stack.frames[1].environment
        is frame_stack.frames[0].environment
    )
    assert (
        frame_stack.current.expression_stack
        == MachineExpressionStack([MachineNumber(int32(3))])
    )


def test_interpret_assignment_1_exit() -> None:
    statement = SyntaxAssignment(
        terms=[SyntaxNumber(value=int32(3))],
        bindings=[SyntaxIdentifier(name="x")],
    )
    frame_stack = init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([MachineNumber(int32(4))]),
    )
    interpret_statement(frame_stack)
    interpret_statement(frame_stack)
    assert frame_stack == init_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([MachineNumber(int32(4))]),
        make_test_environment(
            {"x": MachineNumber(int32(3))}
        ),
        statement_index=1,
    )


def test_interpret_assignment_2_exit() -> None:
    statement = SyntaxAssignment(
        terms=[
            SyntaxNumber(value=int32(300)),
            SyntaxNumber(value=int32(400)),
        ],
        bindings=[
            SyntaxIdentifier(name="abc"),
            SyntaxIdentifier(name="def"),
        ],
    )
    frame_stack = init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([]),
    )
    interpret_statement(frame_stack)
    interpret_statement(frame_stack)
    interpret_statement(frame_stack)
    assert frame_stack == init_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([]),
        make_test_environment(
            {
                "abc": MachineNumber(int32(300)),
                "def": MachineNumber(int32(400)),
            }
        ),
        statement_index=1,
    )


def test_interpret_method_definition_exit() -> None:
    statement = SyntaxMethodDefinition(
        binding=SyntaxIdentifier(name="f"),
        definition=SyntaxExpression(
            [SyntaxIdentifier(name="sqrt")]
        ),
    )
    frame_stack = init_test_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([]),
    )
    interpret_statement(frame_stack)
    environment = frame_stack.current.environment
    assert frame_stack == init_frame_stack(
        init_statement_block(statement),
        MachineExpressionStack([]),
        environment,
        statement_index=1,
    )
    assert environment.base == make_test_environment().base
    assert environment.bindings == {
        "f": GuestCall(
            environment, statement.definition_block
        )
    }
