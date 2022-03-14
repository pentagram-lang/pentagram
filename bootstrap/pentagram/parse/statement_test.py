from numpy import int32
from pentagram.parse.group import Group
from pentagram.parse.group import GroupComment
from pentagram.parse.group import GroupIdentifier
from pentagram.parse.group import GroupLine
from pentagram.parse.group import GroupNumber
from pentagram.parse.statement import parse_statements_block
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber
from pentagram.test import params
from typing import Iterable
from typing import Tuple


def params_statements() -> Iterable[
    Tuple[Group, SyntaxBlock]
]:
    # Expression
    yield Group(
        [GroupLine([GroupIdentifier("abc")])]
    ), SyntaxBlock(
        [SyntaxExpression([SyntaxIdentifier("abc")])]
    )

    # Comment in group
    yield Group(
        [
            GroupLine(
                [
                    GroupNumber(int32(0)),
                    GroupComment(" txt"),
                    Group(
                        [GroupLine([GroupNumber(int32(1))])]
                    ),
                ]
            )
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
            GroupLine(
                [
                    GroupIdentifier("x"),
                    GroupIdentifier("="),
                    GroupIdentifier("y"),
                ]
            )
        ]
    ), SyntaxBlock(
        [
            SyntaxAssignment(
                terms=[SyntaxIdentifier("y")],
                bindings=[SyntaxIdentifier("x")],
            )
        ]
    )

    # Nested assignment
    yield Group(
        [
            GroupLine(
                [
                    GroupIdentifier("a"),
                    GroupIdentifier("b"),
                    GroupIdentifier("="),
                    GroupIdentifier("c"),
                    Group(
                        [
                            GroupLine(
                                [
                                    GroupIdentifier("d"),
                                    GroupIdentifier("="),
                                    GroupIdentifier("e"),
                                ]
                            ),
                            GroupLine(
                                [
                                    GroupIdentifier("f"),
                                    GroupIdentifier("g"),
                                ]
                            ),
                        ]
                    ),
                ]
            )
        ]
    ), SyntaxBlock(
        [
            SyntaxAssignment(
                terms=[
                    SyntaxIdentifier("c"),
                    SyntaxBlock(
                        [
                            SyntaxAssignment(
                                terms=[
                                    SyntaxIdentifier("e")
                                ],
                                bindings=[
                                    SyntaxIdentifier("d")
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
                bindings=[
                    SyntaxIdentifier("a"),
                    SyntaxIdentifier("b"),
                ],
            )
        ]
    )

    # Simple method definition
    yield Group(
        [
            GroupLine(
                [
                    GroupIdentifier("a1"),
                    GroupIdentifier("/="),
                    GroupIdentifier("b2"),
                ]
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
            GroupLine(
                [
                    GroupIdentifier("add"),
                    GroupIdentifier("/="),
                    Group(
                        [
                            GroupLine(
                                [
                                    GroupIdentifier("x"),
                                    GroupIdentifier("y"),
                                    GroupIdentifier("+"),
                                ]
                            )
                        ]
                    ),
                ]
            )
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
    assert parse_statements_block(group) == expected_result
