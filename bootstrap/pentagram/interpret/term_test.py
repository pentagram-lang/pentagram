from __future__ import annotations

from numpy import int32
from pentagram.host.simple_call import sqrt
from pentagram.host.value import PI
from pentagram.interpret.term import interpret_term
from pentagram.interpret.test import init_test_frame_stack
from pentagram.interpret.test import make_test_environment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineFrame
from pentagram.machine import MachineInstructionPointer
from pentagram.machine import MachineNumber
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from pentagram.syntax import SyntaxTerm
from typing import cast


def init_term_block(term: SyntaxTerm) -> SyntaxBlock:
    return SyntaxBlock(
        statements=[SyntaxExpression(terms=[term])]
    )


def test_interpret_number() -> None:
    term = SyntaxNumber(value=int32(100))
    frame_stack = init_test_frame_stack(
        init_term_block(term),
        MachineExpressionStack(values=[]),
    )
    interpret_term(frame_stack)
    assert frame_stack == init_test_frame_stack(
        init_term_block(term),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(100))]
        ),
        term_index=1,
    )


def test_interpret_identifier_value() -> None:
    term = SyntaxIdentifier(name=PI.name)
    expression_stack = MachineExpressionStack(values=[])
    frame_stack = init_test_frame_stack(
        init_term_block(term), expression_stack
    )
    interpret_term(frame_stack)
    assert frame_stack == init_test_frame_stack(
        init_term_block(term),
        MachineExpressionStack(
            values=[cast(MachineValue, PI.value_or_call)]
        ),
        term_index=1,
    )


def test_interpret_identifier_call() -> None:
    term = SyntaxIdentifier(name=sqrt.name)
    expression_stack = MachineExpressionStack(
        values=[MachineNumber(value=int32(16))]
    )
    frame_stack = init_test_frame_stack(
        init_term_block(term), expression_stack
    )
    interpret_term(frame_stack)
    assert frame_stack == init_test_frame_stack(
        init_term_block(term),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(4))]
        ),
        term_index=1,
    )


def test_interpret_comment() -> None:
    term = SyntaxComment(text="something")
    expression_stack = MachineExpressionStack(
        values=[MachineNumber(value=int32(10))]
    )
    frame_stack = init_test_frame_stack(
        init_term_block(term), expression_stack
    )
    interpret_term(frame_stack)
    assert frame_stack == init_test_frame_stack(
        init_term_block(term),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(10))]
        ),
        term_index=1,
    )


def test_interpret_block() -> None:
    term = init_term_block(SyntaxNumber(value=int32(2)))
    expression_stack = MachineExpressionStack(
        values=[MachineNumber(value=int32(10))]
    )
    frame_stack = init_test_frame_stack(
        init_term_block(term), expression_stack
    )
    interpret_term(frame_stack)
    assert len(frame_stack) == 2
    assert (
        frame_stack.frames[0]
        == init_test_frame_stack(
            init_term_block(term),
            MachineExpressionStack(
                values=[MachineNumber(value=int32(10))]
            ),
            term_index=1,
        ).frames[0]
    )
    assert frame_stack.frames[1] == MachineFrame(
        instruction_pointer=MachineInstructionPointer(
            block=term, statement_index=0, term_index=0
        ),
        environment=make_test_environment().extend(),
        expression_stack=MachineExpressionStack(
            values=[MachineNumber(value=int32(10))]
        ),
    )
