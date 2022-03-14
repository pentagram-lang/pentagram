from numpy import int32
from pentagram.interpret import interpret
from pentagram.interpret.test import test_environment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineNumber
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxNumber


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
