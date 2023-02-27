from __future__ import annotations

from pentagram.guest.call import GuestCall
from pentagram.interpret.term import (
    interpret_expression_term,
)
from pentagram.interpret.term import next_term
from pentagram.machine import MachineFrame
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineInstructionPointer
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxMethodDefinition


def interpret_statement(
    frame_stack: MachineFrameStack,
) -> None:
    statement = frame_stack.current.statement
    term_index = frame_stack.current.term_index
    if isinstance(statement, SyntaxExpression):
        if term_index < len(statement.terms):
            interpret_expression_term(
                frame_stack, statement
            )
        else:
            next_statement(frame_stack)
    elif isinstance(statement, SyntaxAssignment):
        if term_index == 0:
            interpret_assignment_enter(
                frame_stack, statement
            )
        else:
            interpret_assignment_exit(
                frame_stack, statement
            )
            next_statement(frame_stack)
    elif isinstance(statement, SyntaxMethodDefinition):
        interpret_method_definition(frame_stack, statement)
        next_statement(frame_stack)
    else:
        raise AssertionError(statement)


def interpret_assignment_enter(
    frame_stack: MachineFrameStack,
    statement: SyntaxAssignment,
) -> None:
    next_term(frame_stack)
    frame_stack.push(
        MachineFrame(
            instruction_pointer=MachineInstructionPointer(
                block=statement.block,
                statement_index=0,
                term_index=0,
            ),
            expression_stack=frame_stack.current.expression_stack,
            environment=frame_stack.current.environment.extend(),
        )
    )


def interpret_assignment_exit(
    frame_stack: MachineFrameStack,
    assignment: SyntaxAssignment,
) -> None:
    expression_stack = frame_stack.current.expression_stack
    environment = frame_stack.current.environment
    for binding in reversed(assignment.bindings):
        assert expression_stack, binding
        environment[binding.name] = expression_stack.pop()


def interpret_method_definition(
    frame_stack: MachineFrameStack,
    method_definition: SyntaxMethodDefinition,
) -> None:
    environment = frame_stack.current.environment
    environment[method_definition.binding.name] = GuestCall(
        definition_environment=environment,
        definition_block=method_definition.block,
    )


def next_statement(frame_stack: MachineFrameStack) -> None:
    frame_stack.current.statement_index += 1
    frame_stack.current.term_index = 0
