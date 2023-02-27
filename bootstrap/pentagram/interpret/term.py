from __future__ import annotations

from pentagram.machine import MachineCall
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineNumber
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from typing import Any


def interpret_expression_term(
    frame_stack: MachineFrameStack,
    statement: SyntaxExpression,
) -> None:
    term = statement.terms[frame_stack.current.term_index]
    if isinstance(term, SyntaxNumber):
        interpret_number_term(frame_stack, term)
    elif isinstance(term, SyntaxIdentifier):
        interpret_identifier_term(frame_stack, term)
    elif isinstance(term, SyntaxComment):
        next_term(frame_stack)
    else:
        raise AssertionError(term)


def interpret_number_term(
    frame_stack: MachineFrameStack,
    number: SyntaxNumber[Any],
) -> None:
    expression_stack = frame_stack.current.expression_stack
    expression_stack.push(MachineNumber(value=number.value))
    next_term(frame_stack)


def interpret_identifier_term(
    frame_stack: MachineFrameStack,
    identifier: SyntaxIdentifier,
) -> None:
    expression_stack = frame_stack.current.expression_stack
    environment = frame_stack.current.environment
    value_or_call = environment[identifier.name]
    if isinstance(value_or_call, MachineValue):
        expression_stack.push(value_or_call)
        next_term(frame_stack)
    elif isinstance(value_or_call, MachineCall):
        value_or_call(frame_stack)
    else:
        raise AssertionError(value_or_call)


def next_term(frame_stack: MachineFrameStack) -> None:
    frame_stack.current.term_index += 1
