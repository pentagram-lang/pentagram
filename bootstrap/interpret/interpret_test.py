from interpret import interpret
from interpret.test import test_environment
from machine import MachineExpressionStack
from machine import MachineNumber
from numpy import int32
from syntax import SyntaxBlock
from syntax import SyntaxExpression
from syntax import SyntaxNumber


def test_interpret():
    block = SyntaxBlock(
        [
            SyntaxExpression(
                [
                    SyntaxNumber(int32(1)),
                    SyntaxNumber(int32(2)),
                    SyntaxNumber(int32(3)),
                ]
            )
        ]
    )
    expression_stack = MachineExpressionStack([])
    environment = test_environment()
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        [
            MachineNumber(int32(1)),
            MachineNumber(int32(2)),
            MachineNumber(int32(3)),
        ]
    )
