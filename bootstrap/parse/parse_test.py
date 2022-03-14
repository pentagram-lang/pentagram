from numpy import int32
from parse import parse
from syntax import SyntaxAssignment
from syntax import SyntaxBlock
from syntax import SyntaxComment
from syntax import SyntaxExpression
from syntax import SyntaxIdentifier
from syntax import SyntaxNumber
from test import params


def params_parse():
    yield "0x123xiw", SyntaxBlock(
        [SyntaxExpression([SyntaxNumber(int32(0x123))])]
    )
    yield "abc", SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("abc")])]
    )
    yield "a-b-c", SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("a-b-c")])]
    )
    yield "123 abc ", SyntaxBlock(
        [
            SyntaxExpression(
                [
                    SyntaxNumber(int32(123)),
                    SyntaxIdentifier("abc"),
                ]
            )
        ]
    )
    yield "123 abc -- de", SyntaxBlock(
        [
            SyntaxExpression(
                [
                    SyntaxNumber(int32(123)),
                    SyntaxIdentifier("abc"),
                    SyntaxComment(" de"),
                ]
            )
        ]
    )
    yield "abc def  =    10   20", SyntaxBlock(
        [
            SyntaxAssignment(
                terms=[
                    SyntaxNumber(int32(10)),
                    SyntaxNumber(int32(20)),
                ],
                bindings=[
                    SyntaxIdentifier("abc"),
                    SyntaxIdentifier("def"),
                ],
            )
        ]
    )
    yield "123 abc\n456 def", SyntaxBlock(
        [
            SyntaxExpression(
                [
                    SyntaxNumber(int32(123)),
                    SyntaxIdentifier("abc"),
                ]
            ),
            SyntaxExpression(
                [
                    SyntaxNumber(int32(456)),
                    SyntaxIdentifier("def"),
                ]
            ),
        ]
    )


@params(params_parse)
def test_parse(text, expected_result):
    assert parse(text) == expected_result
