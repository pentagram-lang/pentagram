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
    # Number
    yield "0x123xiw", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxNumber(value=int32(0x123))]
            )
        ]
    )

    # Identifier
    yield "abc", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="abc")]
            )
        ]
    )

    # Kebab
    yield "a-b-c", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[SyntaxIdentifier(name="a-b-c")]
            )
        ]
    )

    # Multiple terms
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

    # End-line comment
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

    # Comment without whitespace
    yield "abc--de", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[
                    SyntaxIdentifier(name="abc"),
                ],
                comment=SyntaxComment(text="de"),
            )
        ]
    )

    # Only comment
    yield "-- de", SyntaxBlock(
        statements=[
            SyntaxExpression(
                terms=[],
                comment=SyntaxComment(text=" de"),
            )
        ]
    )

    # Assignment
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

    # Multiple lines
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
