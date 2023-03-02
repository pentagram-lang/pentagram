from __future__ import annotations

from numpy import int32
from pentagram.interpret.block import interpret_block
from pentagram.interpret.interpret import init_machine
from pentagram.interpret.test import init_test_machine
from pentagram.interpret.test import make_test_environment
from pentagram.machine import Machine
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineInstructionPointer
from pentagram.machine import MachineNumber
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber


def test_interpret_block_enter() -> None:
    block = SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxNumber(value=int32(4))]
            )
        ]
    )
    machine = init_test_machine(
        block, MachineExpressionStack(values=[])
    )
    interpret_block(machine)
    assert machine == init_test_machine(
        block,
        MachineExpressionStack(
            values=[MachineNumber(value=int32(4))]
        ),
        term_index=1,
    )


def test_interpret_block_exit() -> None:
    block = SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxNumber(value=int32(4))]
            )
        ]
    )
    machine = init_test_machine(
        block,
        MachineExpressionStack(values=[]),
        statement_index=1,
    )
    interpret_block(machine)
    assert machine == Machine(
        frames=[],
        expression_stack=MachineExpressionStack(values=[]),
    )


def test_interpret_assignment_1_enter() -> None:
    statement = SyntaxAssignment(
        bindings=[SyntaxIdentifier(name="x")],
        block=SyntaxBlock(
            statements=[
                SyntaxExpression(
                    terms=[SyntaxNumber(value=int32(3))]
                )
            ]
        ),
    )
    machine = init_test_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(
            values=[MachineNumber(value=int32(4))]
        ),
    )
    interpret_block(machine)
    assert len(machine.frames) == 2
    assert machine.frames[
        1
    ].instruction_pointer == MachineInstructionPointer(
        block=statement.block,
        statement_index=0,
        term_index=0,
    )
    assert (
        machine.frames[1].environment.base
        is machine.frames[0].environment
    )
    assert (
        machine.expression_stack
        == MachineExpressionStack(
            values=[MachineNumber(value=int32(4))]
        )
    )
    interpret_block(machine)
    assert len(machine.frames) == 2
    assert machine.frames[
        1
    ].instruction_pointer == MachineInstructionPointer(
        block=statement.block,
        statement_index=0,
        term_index=1,
    )
    interpret_block(machine)
    assert len(machine.frames) == 2
    assert machine.frames[
        1
    ].instruction_pointer == MachineInstructionPointer(
        block=statement.block,
        statement_index=1,
        term_index=0,
    )
    interpret_block(machine)
    assert len(machine.frames) == 1
    assert machine.frames[
        0
    ].instruction_pointer == MachineInstructionPointer(
        block=SyntaxBlock(statements=[statement]),
        statement_index=0,
        term_index=1,
    )
    interpret_block(machine)
    assert machine == init_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(
            values=[
                MachineNumber(value=int32(4)),
            ]
        ),
        make_test_environment(
            {
                "x": MachineNumber(value=int32(3)),
            }
        ),
        statement_index=1,
    )


def test_interpret_assignment_2_exit() -> None:
    statement = SyntaxAssignment(
        bindings=[
            SyntaxIdentifier(name="abc"),
            SyntaxIdentifier(name="def"),
        ],
        block=SyntaxBlock(
            statements=[
                SyntaxExpression(
                    terms=[
                        SyntaxNumber(value=int32(300)),
                        SyntaxNumber(value=int32(400)),
                    ],
                )
            ]
        ),
    )
    machine = init_test_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
    )
    interpret_block(machine)
    interpret_block(machine)
    interpret_block(machine)
    interpret_block(machine)
    interpret_block(machine)
    interpret_block(machine)
    assert machine == init_machine(
        SyntaxBlock(statements=[statement]),
        MachineExpressionStack(values=[]),
        make_test_environment(
            {
                "abc": MachineNumber(value=int32(300)),
                "def": MachineNumber(value=int32(400)),
            }
        ),
        statement_index=1,
    )
