from guest.call import GuestCall
from interpret.term import interpret_term
from machine import MachineExpressionStack
from machine import MachineFrame
from machine import MachineFrameStack
from syntax import SyntaxAssignment
from syntax import SyntaxExpression
from syntax import SyntaxMethodDefinition


def interpret_statement(
    frame_stack: MachineFrameStack
) -> None:
    statement = frame_stack.current.statement
    term_index = frame_stack.current.term_index
    if term_index == 0:
        interpret_statement_enter(frame_stack)
    if term_index < len(statement.terms):
        interpret_term(frame_stack)
    else:
        interpret_statement_exit(frame_stack)
        next_statement(frame_stack)


def interpret_statement_enter(
    frame_stack: MachineFrameStack
) -> None:
    statement = frame_stack.current.statement
    if isinstance(statement, SyntaxExpression):
        pass
    elif isinstance(statement, SyntaxAssignment):
        interpret_assignment_enter(frame_stack)
    elif isinstance(statement, SyntaxMethodDefinition):
        pass
    else:
        assert False, statement


def interpret_statement_exit(
    frame_stack: MachineFrameStack
) -> None:
    statement = frame_stack.current.statement
    if isinstance(statement, SyntaxExpression):
        pass
    elif isinstance(statement, SyntaxAssignment):
        interpret_assignment_exit(frame_stack, statement)
    elif isinstance(statement, SyntaxMethodDefinition):
        interpret_method_definition_exit(
            frame_stack, statement
        )
    else:
        assert False, statement


def interpret_assignment_enter(
    frame_stack: MachineFrameStack,
) -> None:
    old_frame = frame_stack.current
    new_frame = MachineFrame(
        old_frame.instruction_pointer,
        MachineExpressionStack([]),
        old_frame.environment,
    )
    frame_stack.push(new_frame)


def interpret_assignment_exit(
    frame_stack: MachineFrameStack,
    assignment: SyntaxAssignment,
) -> None:
    expression_stack = frame_stack.current.expression_stack
    environment = frame_stack.current.environment
    for binding in reversed(assignment.bindings):
        environment[binding.name] = expression_stack.pop()
    assert len(expression_stack) == 0, expression_stack
    frame_stack.pop()


def interpret_method_definition_exit(
    frame_stack: MachineFrameStack,
    method_definition: SyntaxMethodDefinition,
) -> None:
    environment = frame_stack.current.environment
    environment[method_definition.binding.name] = GuestCall(
        definition_environment=environment,
        definition_block=method_definition.definition_block,
    )


def next_statement(frame_stack: MachineFrameStack) -> None:
    frame_stack.current.statement_index += 1
    frame_stack.current.term_index = 0
