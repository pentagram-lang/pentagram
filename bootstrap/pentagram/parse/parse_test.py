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
        statements=[
            SyntaxExpression(
                terms=[SyntaxNumber(value=int32(0x123))]
            )
        ]
    )
    yield "abc", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="abc")]
            )
        ]
    )
    yield "a-b-c", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="a-b-c")]
            )
        ]
    )
    yield "123 abc ", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[
                    SyntaxNumber(value=int32(123)),
                    SyntaxIdentifier(name="abc"),
                ]
            )
        ]
    )
    yield "123 abc -- de", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[
                    SyntaxNumber(value=int32(123)),
                    SyntaxIdentifier(name="abc"),
                ],
                comment=SyntaxComment(text=" de"),
            )
        ]
    )
    yield "abc def  =    10   20", SyntaxBlock(
        statements=[
            SyntaxAssignment(
                bindings=[
                    SyntaxIdentifier(name="abc"),
                    SyntaxIdentifier(name="def"),
                ],
                block=SyntaxBlock(
                    statements=[
                        SyntaxExpression(
                            terms=[
                                SyntaxNumber(
                                    value=int32(10)
                                ),
                                SyntaxNumber(
                                    value=int32(20)
                                ),
                            ],
                        )
                    ]
                ),
            )
        ]
    )
    yield "123 abc\n456 def", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[
                    SyntaxNumber(value=int32(123)),
                    SyntaxIdentifier(name="abc"),
                ]
            ),
            SyntaxExpression(
                terms=[
                    SyntaxNumber(value=int32(456)),
                    SyntaxIdentifier(name="def"),
                ]
            ),
        ]
    )


@params(params_parse)
def test_parse(
    text: str, expected_result: SyntaxBlock
) -> None:
    assert parse(text) == expected_result
