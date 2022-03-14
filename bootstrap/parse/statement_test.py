from numpy import int32
from parse.group import Group
from parse.group import GroupComment
from parse.group import GroupIdentifier
from parse.group import GroupLine
from parse.group import GroupNumber
from parse.statement import parse_statements_block
from syntax import SyntaxAssignment
from syntax import SyntaxBlock
from syntax import SyntaxComment
from syntax import SyntaxExpression
from syntax import SyntaxIdentifier
from syntax import SyntaxMethodDefinition
from syntax import SyntaxNumber
from test import params


def params_statements():
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
def test_statements(group, expected_result):
    assert parse_statements_block(group) == expected_result
