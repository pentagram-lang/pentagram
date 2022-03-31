from __future__ import annotations

from collections.abc import Iterable
from numpy import int32
from pentagram.parse import parse
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from pentagram.test import params


def params_parse() -> Iterable[tuple[str, SyntaxBlock]]:
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
def test_parse(
    text: str, expected_result: SyntaxBlock
) -> None:
    assert parse(text) == expected_result
