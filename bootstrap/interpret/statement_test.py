from guest.call import GuestCall
from interpret.interpret import init_frame_stack
from interpret.statement import interpret_statement
from interpret.test import init_test_frame_stack
from interpret.test import test_environment
from machine import MachineExpressionStack
from machine import MachineNumber
from numpy import int32
from syntax import SyntaxAssignment
from syntax import SyntaxBlock
from syntax import SyntaxExpression
from syntax import SyntaxIdentifier
from syntax import SyntaxMethodDefinition
from syntax import SyntaxNumber
from syntax import SyntaxStatement


def init_statement_block(
    statement: SyntaxStatement
) -> SyntaxBlock:
    return SyntaxBlock([statement])


def test_interpret_expression_enter():
    statement = SyntaxExpression([SyntaxNumber(int32(100))])
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


def test_interpret_expression_exit():
    statement = SyntaxExpression([SyntaxNumber(int32(100))])
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


def test_interpret_assignment_1_enter():
    statement = SyntaxAssignment(
        terms=[SyntaxNumber(int32(3))],
        bindings=[SyntaxIdentifier("x")],
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


def test_interpret_assignment_1_exit():
    statement = SyntaxAssignment(
        terms=[SyntaxNumber(int32(3))],
        bindings=[SyntaxIdentifier("x")],
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
        test_environment({"x": MachineNumber(int32(3))}),
        statement_index=1,
    )


def test_interpret_assignment_2_exit():
    statement = SyntaxAssignment(
        terms=[
            SyntaxNumber(int32(300)),
            SyntaxNumber(int32(400)),
        ],
        bindings=[
            SyntaxIdentifier("abc"),
            SyntaxIdentifier("def"),
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
        test_environment(
            {
                "abc": MachineNumber(int32(300)),
                "def": MachineNumber(int32(400)),
            }
        ),
        statement_index=1,
    )


def test_interpret_method_definition_exit():
    statement = SyntaxMethodDefinition(
        binding=SyntaxIdentifier("f"),
        definition=SyntaxExpression(
            [SyntaxIdentifier("sqrt")]
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
    assert environment.base == test_environment().base
    assert environment.bindings == {
        "f": GuestCall(
            environment, statement.definition_block
        )
    }
