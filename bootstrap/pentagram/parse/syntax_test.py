from __future__ import annotations

from collections.abc import Iterable
from numpy import int32
from pentagram.parse.group import Group
from pentagram.parse.line import Line
from pentagram.parse.marker import MarkerAssignment
from pentagram.parse.marker import MarkerMethodDefinition
from pentagram.parse.syntax import parse_syntax
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber
from pentagram.test import params


def params_statements() -> Iterable[
    tuple[Group, SyntaxBlock]
]:
    # Expression
    yield Group(
        [Line(indent=0, terms=[SyntaxIdentifier("abc")])]
    ), SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("abc")])]
    )

    # Comment in group
    yield Group(
        [
            Line(
                indent=0,
                terms=[
                    SyntaxNumber(int32(0)),
                ],
                comment=SyntaxComment(" txt"),
            ),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxNumber(int32(1))],
                    )
                ]
            ),
        ]
    ), SyntaxBlock(
        [
            SyntaxExpression(
                [
                    SyntaxNumber(int32(0)),
                    SyntaxComment(" txt"),
                    SyntaxBlock(
                        [
                            SyntaxExpression(
                                [SyntaxNumber(int32(1))]
                            )
                        ]
                    ),
                ]
            )
        ]
    )

    # Simple assignment
    yield Group(
        [
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier("x"),
                    MarkerAssignment(),
                    SyntaxIdentifier("y"),
                ],
            )
        ]
    ), SyntaxBlock(
        [
            SyntaxAssignment(
                bindings=[SyntaxIdentifier("x")],
                terms=[SyntaxIdentifier("y")],
            )
        ]
    )

    # Nested assignment
    yield Group(
        [
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier("a"),
                    SyntaxIdentifier("b"),
                    MarkerAssignment(),
                    SyntaxIdentifier("c"),
                ],
            ),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier("d"),
                            MarkerAssignment(),
                            SyntaxIdentifier("e"),
                        ],
                    ),
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier("f"),
                            SyntaxIdentifier("g"),
                        ],
                    ),
                ]
            ),
        ]
    ), SyntaxBlock(
        [
            SyntaxAssignment(
                bindings=[
                    SyntaxIdentifier("a"),
                    SyntaxIdentifier("b"),
                ],
                terms=[
                    SyntaxIdentifier("c"),
                    SyntaxBlock(
                        [
                            SyntaxAssignment(
                                bindings=[
                                    SyntaxIdentifier("d")
                                ],
                                terms=[
                                    SyntaxIdentifier("e")
                                ],
                            ),
                            SyntaxExpression(
                                [
                                    SyntaxIdentifier("f"),
                                    SyntaxIdentifier("g"),
                                ]
                            ),
                        ]
                    ),
                ],
            )
        ]
    )

    # Simple method definition
    yield Group(
        [
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier("a1"),
                    MarkerMethodDefinition(),
                    SyntaxIdentifier("b2"),
                ],
            )
        ]
    ), SyntaxBlock(
        [
            SyntaxMethodDefinition(
                binding=SyntaxIdentifier("a1"),
                definition=SyntaxExpression(
                    [SyntaxIdentifier("b2")]
                ),
            )
        ]
    )

    # Block method definition
    yield Group(
        [
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier("add"),
                    MarkerMethodDefinition(),
                ],
            ),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier("x"),
                            SyntaxIdentifier("y"),
                            SyntaxIdentifier("+"),
                        ],
                    )
                ]
            ),
        ]
    ), SyntaxBlock(
        [
            SyntaxMethodDefinition(
                binding=SyntaxIdentifier("add"),
                definition=SyntaxExpression(
                    [
                        SyntaxBlock(
                            [
                                SyntaxExpression(
                                    [
                                        SyntaxIdentifier(
                                            "x"
                                        ),
                                        SyntaxIdentifier(
                                            "y"
                                        ),
                                        SyntaxIdentifier(
                                            "+"
                                        ),
                                    ]
                                )
                            ]
                        )
                    ]
                ),
            )
        ]
    )


@params(params_statements)
def test_statements(
    group: Group, expected_result: SyntaxBlock
) -> None:
    assert parse_syntax(group) == expected_result
