from __future__ import annotations

import pytest

from collections.abc import Iterable
from numpy import int32
from pentagram.parse.group import Group
from pentagram.parse.line import Line
from pentagram.parse.marker import MarkerAssignment
from pentagram.parse.marker import MarkerMethodDefinition
from pentagram.parse.syntax import SyntaxError_
from pentagram.parse.syntax import parse_syntax
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber
from pentagram.test import params


def params_syntax_ok() -> Iterable[
    tuple[Group, SyntaxBlock]
]:
    # Expression
    yield Group(
        items=[
            Line(
                indent=0,
                terms=[SyntaxIdentifier(name="abc")],
            )
        ]
    ), SyntaxBlock(
        statements=[
            SyntaxExpression(
                atoms=[SyntaxIdentifier(name="abc")]
            )
        ]
    )

    # Simple assignment
    yield Group(
        items=[
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier(name="x"),
                    MarkerAssignment(),
                    SyntaxIdentifier(name="y"),
                ],
            )
        ]
    ), SyntaxBlock(
        statements=[
            SyntaxAssignment(
                bindings=[SyntaxIdentifier(name="x")],
                block=SyntaxBlock(
                    statements=[
                        SyntaxExpression(
                            atoms=[
                                SyntaxIdentifier(name="y")
                            ]
                        )
                    ]
                ),
            )
        ]
    )

    # Nested assignment
    yield Group(
        items=[
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier(name="a"),
                    SyntaxIdentifier(name="b"),
                    MarkerAssignment(),
                ],
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier(name="c"),
                        ],
                    ),
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier(name="d"),
                            MarkerAssignment(),
                            SyntaxIdentifier(name="e"),
                        ],
                    ),
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier(name="f"),
                            SyntaxIdentifier(name="g"),
                        ],
                    ),
                ]
            ),
        ]
    ), SyntaxBlock(
        statements=[
            SyntaxAssignment(
                bindings=[
                    SyntaxIdentifier(name="a"),
                    SyntaxIdentifier(name="b"),
                ],
                block=SyntaxBlock(
                    statements=[
                        SyntaxExpression(
                            atoms=SyntaxIdentifier(name="c")
                        ),
                        SyntaxAssignment(
                            bindings=[
                                SyntaxIdentifier(name="d")
                            ],
                            block=SyntaxBlock(
                                statements=SyntaxExpression(
                                    atoms=[
                                        SyntaxIdentifier(
                                            name="e"
                                        )
                                    ],
                                )
                            ),
                        ),
                        SyntaxExpression(
                            atoms=[
                                SyntaxIdentifier(name="f"),
                                SyntaxIdentifier(name="g"),
                            ]
                        ),
                    ],
                ),
            )
        ]
    )

    # Simple method definition
    yield Group(
        items=[
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier(name="a1"),
                    MarkerMethodDefinition(),
                    SyntaxIdentifier(name="b2"),
                ],
            )
        ]
    ), SyntaxBlock(
        statements=[
            SyntaxMethodDefinition(
                binding=SyntaxIdentifier(name="a1"),
                block=SyntaxBlock(
                    statements=[
                        SyntaxExpression(
                            atoms=[
                                SyntaxIdentifier(name="b2")
                            ]
                        ),
                    ]
                ),
            )
        ]
    )

    # Block method definition
    yield Group(
        items=[
            Line(
                indent=0,
                terms=[
                    SyntaxIdentifier(name="add"),
                    MarkerMethodDefinition(),
                ],
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[
                            SyntaxIdentifier(name="x"),
                            SyntaxIdentifier(name="y"),
                            SyntaxIdentifier(name="+"),
                        ],
                    )
                ]
            ),
        ]
    ), SyntaxBlock(
        statements=[
            SyntaxMethodDefinition(
                binding=SyntaxIdentifier(name="add"),
                block=SyntaxBlock(
                    statements=[
                        SyntaxExpression(
                            atoms=[
                                SyntaxIdentifier(name="x"),
                                SyntaxIdentifier(name="y"),
                                SyntaxIdentifier(name="+"),
                            ]
                        )
                    ]
                ),
            )
        ]
    )


@params(params_syntax_ok)
def test_syntax_ok(
    group: Group, expected_result: SyntaxBlock
) -> None:
    assert parse_syntax(group) == expected_result


def params_syntax_error() -> Iterable[tuple[Group, str]]:
    # Initial indent
    yield Group(
        items=[
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[
                            SyntaxNumber(value=int32(1))
                        ],
                    )
                ]
            ),
        ]
    ), "unexpected group"

    # Indent without marker
    yield Group(
        items=[
            Line(
                indent=0,
                terms=[
                    SyntaxNumber(value=int32(0)),
                ],
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[
                            SyntaxNumber(value=int32(1))
                        ],
                    )
                ]
            ),
        ]
    ), "unexpected group"


@params(params_syntax_error)
def test_syntax_error(
    group: Group, expected_error: str
) -> None:
    with pytest.raises(SyntaxError_) as exc_info:
        parse_syntax(group)
    assert str(exc_info.value) == expected_error
