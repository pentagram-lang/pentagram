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
    yield [], Group(items=[])

    # Empty line
    yield [Line(indent=0)], Group(items=[Line(indent=0)])

    # Single identifier
    yield [
        Line(indent=0, terms=[SyntaxIdentifier(name="abc")])
    ], Group(
        items=[
            Line(
                indent=0,
                terms=[SyntaxIdentifier(name="abc")],
            )
        ]
    )

    # Simple indent
    yield [
        Line(
            indent=0, terms=[SyntaxNumber(value=int32(1))]
        ),
        Line(
            indent=0, terms=[SyntaxNumber(value=int32(2))]
        ),
        Line(
            indent=2, terms=[SyntaxNumber(value=int32(3))]
        ),
    ], Group(
        items=[
            Line(
                indent=0,
                terms=[SyntaxNumber(value=int32(1))],
            ),
            Line(
                indent=0,
                terms=[SyntaxNumber(value=int32(2))],
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[
                            SyntaxNumber(value=int32(3))
                        ],
                    ),
                ]
            ),
        ]
    )

    # Blank lines of different indents
    yield [
        Line(indent=0, terms=[SyntaxIdentifier(name="a")]),
        Line(indent=2, terms=[SyntaxIdentifier(name="b")]),
        Line(indent=2, terms=[SyntaxIdentifier(name="c")]),
        Line(indent=0),
        Line(indent=2),
        Line(indent=3),
    ], Group(
        items=[
            Line(
                indent=0, terms=[SyntaxIdentifier(name="a")]
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier(name="b")],
                    ),
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier(name="c")],
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
        Line(indent=0, terms=[SyntaxIdentifier(name="x")]),
        Line(indent=2, terms=[SyntaxIdentifier(name="y")]),
        Line(indent=2, comment=SyntaxComment(text="0")),
        Line(indent=4, comment=SyntaxComment(text="1")),
        Line(indent=0, comment=SyntaxComment(text="2")),
        Line(indent=0, terms=[SyntaxIdentifier(name="z")]),
    ], Group(
        items=[
            Line(
                indent=0, terms=[SyntaxIdentifier(name="x")]
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier(name="y")],
                    ),
                    Line(
                        indent=2,
                        comment=SyntaxComment(text="0"),
                    ),
                    Group(
                        items=[
                            Line(
                                indent=4,
                                comment=SyntaxComment(
                                    text="1"
                                ),
                            ),
                        ]
                    ),
                ]
            ),
            Line(indent=0, comment=SyntaxComment(text="2")),
            Line(
                indent=0, terms=[SyntaxIdentifier(name="z")]
            ),
        ]
    )

    # Comment starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier(name="x")]),
        Line(indent=2, comment=SyntaxComment(text="0")),
        Line(indent=2, terms=[SyntaxIdentifier(name="y")]),
        Line(indent=0, comment=SyntaxComment(text="2")),
        Line(indent=0, terms=[SyntaxIdentifier(name="z")]),
    ], Group(
        items=[
            Line(
                indent=0, terms=[SyntaxIdentifier(name="x")]
            ),
            Group(
                items=[
                    Line(
                        indent=2,
                        comment=SyntaxComment(text="0"),
                    ),
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier(name="y")],
                    ),
                ]
            ),
            Line(indent=0, comment=SyntaxComment(text="2")),
            Line(
                indent=0, terms=[SyntaxIdentifier(name="z")]
            ),
        ]
    )

    # Blank line starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier(name="x")]),
        Line(indent=0),
        Line(indent=2, terms=[SyntaxIdentifier(name="y")]),
        Line(indent=2),
        Line(indent=0),
        Line(indent=0, terms=[SyntaxIdentifier(name="z")]),
    ], Group(
        items=[
            Line(
                indent=0, terms=[SyntaxIdentifier(name="x")]
            ),
            Line(indent=0),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier(name="y")],
                    ),
                    Line(indent=2),
                    Line(indent=0),
                ]
            ),
            Line(
                indent=0, terms=[SyntaxIdentifier(name="z")]
            ),
        ]
    )

    # Large blank line starting a group
    yield [
        Line(indent=0, terms=[SyntaxIdentifier(name="x")]),
        Line(indent=3),
        Line(indent=9),
        Line(indent=2, terms=[SyntaxIdentifier(name="y")]),
    ], Group(
        items=[
            Line(
                indent=0, terms=[SyntaxIdentifier(name="x")]
            ),
            Line(indent=3),
            Line(indent=9),
            Group(
                items=[
                    Line(
                        indent=2,
                        terms=[SyntaxIdentifier(name="y")],
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
