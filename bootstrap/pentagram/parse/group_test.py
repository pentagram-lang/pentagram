from __future__ import annotations

from collections.abc import Iterable
from numpy import int32
from pentagram.parse.group import Group
from pentagram.parse.group import parse_group
from pentagram.parse.line import Line
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from pentagram.test import params


def params_group() -> Iterable[tuple[list[Line], Group]]:
    # No lines
    yield [], Group([])

    # Empty line
    yield [Line(indent=0)], Group([Line(indent=0)])

    # Single identifier
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("abc")])
    ], Group(
        [Line(indent=0, terms=[SyntaxIdentifier("abc")])]
    )

    # Simple indent
    yield [
        Line(indent=0, terms=[SyntaxNumber(int32(1))]),
        Line(indent=0, terms=[SyntaxNumber(int32(2))]),
        Line(indent=2, terms=[SyntaxNumber(int32(3))]),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxNumber(int32(1))]),
            Line(indent=0, terms=[SyntaxNumber(int32(2))]),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxNumber(int32(3))],
                    ),
                ]
            ),
        ]
    )

    # Blank lines of different indents
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("a")]),
        Line(indent=2, terms=[SyntaxIdentifier("b")]),
        Line(indent=2, terms=[SyntaxIdentifier("c")]),
        Line(indent=0),
        Line(indent=2),
        Line(indent=3),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxIdentifier("a")]),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("b")],
                    ),
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("c")],
                    ),
                    Line(indent=0),
                    Line(indent=2),
                    Line(indent=3),
                ]
            ),
        ]
    )

    # Comments in and out of group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("x")]),
        Line(indent=2, terms=[SyntaxIdentifier("y")]),
        Line(indent=2, comment=SyntaxComment("0")),
        Line(indent=4, comment=SyntaxComment("1")),
        Line(indent=0, comment=SyntaxComment("2")),
        Line(indent=0, terms=[SyntaxIdentifier("z")]),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxIdentifier("x")]),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("y")],
                    ),
                    Line(
                        indent=2, comment=SyntaxComment("0")
                    ),
                    Line(
                        indent=4, comment=SyntaxComment("1")
                    ),
                ]
            ),
            Line(indent=0, comment=SyntaxComment("2")),
            Line(indent=0, terms=[SyntaxIdentifier("z")]),
        ]
    )

    # Comment starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("x")]),
        Line(indent=2, comment=SyntaxComment("0")),
        Line(indent=2, terms=[SyntaxIdentifier("y")]),
        Line(indent=0, comment=SyntaxComment("2")),
        Line(indent=0, terms=[SyntaxIdentifier("z")]),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxIdentifier("x")]),
            Line(indent=2, comment=SyntaxComment("0")),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("y")],
                    ),
                ]
            ),
            Line(indent=0, comment=SyntaxComment("2")),
            Line(indent=0, terms=[SyntaxIdentifier("z")]),
        ]
    )

    # Indented comment starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("x")]),
        Line(indent=4, comment=SyntaxComment("0")),
        Line(indent=8, comment=SyntaxComment("1")),
        Line(indent=2, terms=[SyntaxIdentifier("y")]),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxIdentifier("x")]),
            Line(indent=4, comment=SyntaxComment("0")),
            Line(indent=8, comment=SyntaxComment("1")),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("y")],
                    ),
                ]
            ),
        ]
    )

    # Blank line starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("x")]),
        Line(indent=0),
        Line(indent=2, terms=[SyntaxIdentifier("y")]),
        Line(indent=2),
        Line(indent=0),
        Line(indent=0, terms=[SyntaxIdentifier("z")]),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxIdentifier("x")]),
            Line(indent=0),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("y")],
                    ),
                    Line(indent=2),
                    Line(indent=0),
                ]
            ),
            Line(indent=0, terms=[SyntaxIdentifier("z")]),
        ]
    )

    # Large blank line starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier("x")]),
        Line(indent=3),
        Line(indent=9),
        Line(indent=2, terms=[SyntaxIdentifier("y")]),
    ], Group(
        [
            Line(indent=0, terms=[SyntaxIdentifier("x")]),
            Line(indent=3),
            Line(indent=9),
            Group(
                [
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier("y")],
                    ),
                ]
            ),
        ]
    )


@params(params_group)
def test_group(
    lines: list[Line], expected_result: Group
) -> None:
    assert parse_group(lines) == expected_result
