from __future__ import annotations

from numpy.typing import NBitBase
from pentagram.machine import MachineCall
from pentagram.machine import MachineFrame
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineInstructionPointer
from pentagram.machine import MachineNumber
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber


def interpret_term(frame_stack: MachineFrameStack) -> None:
    term = frame_stack.current.term
    if isinstance(term, SyntaxNumber):
        interpret_number_term(frame_stack, term)
    elif isinstance(term, SyntaxIdentifier):
        interpret_identifier_term(frame_stack, term)
    elif isinstance(term, SyntaxComment):
        next_term(frame_stack)
    elif isinstance(term, SyntaxBlock):
        interpret_block_term(frame_stack, term)
    else:
        raise AssertionError(term)


def interpret_number_term(
    frame_stack: MachineFrameStack,
    number: SyntaxNumber[NBitBase],
) -> None:
    expression_stack = frame_stack.current.expression_stack
    expression_stack.push(MachineNumber(number.value))
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


def interpret_block_term(
    frame_stack: MachineFrameStack, block: SyntaxBlock
) -> None:
    next_term(frame_stack)
    frame_stack.push(
        MachineFrame(
            MachineInstructionPointer(
                block, statement_index=0, term_index=0
            ),
            frame_stack.current.expression_stack,
            frame_stack.current.environment.extend(),
        )
    )


def next_term(frame_stack: MachineFrameStack) -> None:
    frame_stack.current.term_index += 1
