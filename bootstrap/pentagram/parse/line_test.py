from __future__ import annotations

from collections.abc import Iterable
from numpy import int32
from numpy import int64
from numpy import uint8
from numpy import uint16
from numpy import uint32
from numpy import uint64
from pentagram.parse.line import Line
from pentagram.parse.line import parse_atom
from pentagram.parse.line import parse_lines
from pentagram.parse.marker import MarkerAssignment
from pentagram.parse.marker import MarkerMethodDefinition
from pentagram.syntax import SyntaxAtom
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from pentagram.test import params


def params_lines() -> Iterable[tuple[str, list[Line]]]:
    # Identifiers
    yield ("a\n" "b\n"), [
        Line(indent=0, terms=[SyntaxIdentifier(name="a")]),
        Line(indent=0, terms=[SyntaxIdentifier(name="b")]),
    ]

    # Numbers and indent
    yield "a0 1b c-2\n" "  def ghi\n", [
        Line(
            indent=0,
            terms=[
                SyntaxIdentifier(name="a0"),
                SyntaxNumber(value=uint8(1)),
                SyntaxIdentifier(name="c-2"),
            ],
        ),
        Line(
            indent=2,
            terms=[
                SyntaxIdentifier(name="def"),
                SyntaxIdentifier(name="ghi"),
            ],
        ),
    ]

    # Just indent
    yield "\n" "    \n", [
        Line(indent=0),
        Line(indent=4),
    ]

    # Comments
    yield "   -- desc\n" "0x1-2--xyz\n", [
        Line(
            indent=3,
            terms=[],
            comment=SyntaxComment(text=" desc"),
        ),
        Line(
            indent=0,
            terms=[SyntaxNumber(value=uint8(0x12))],
            comment=SyntaxComment(text="xyz"),
        ),
    ]

    # Assignment
    yield "x = y", [
        Line(
            indent=0,
            terms=[
                SyntaxIdentifier(name="x"),
                MarkerAssignment(),
                SyntaxIdentifier(name="y"),
            ],
        ),
    ]

    # Method definition
    yield "f >> x", [
        Line(
            indent=0,
            terms=[
                SyntaxIdentifier(name="f"),
                MarkerMethodDefinition(),
                SyntaxIdentifier(name="x"),
            ],
        ),
    ]


@params(params_lines)
def test_lines(
    lines: str, expected_result: list[Line]
) -> None:
    assert parse_lines(lines) == expected_result


def params_atom() -> Iterable[tuple[str, SyntaxAtom]]:
    yield "abc", SyntaxIdentifier(name="abc")
    yield "0", SyntaxNumber(value=int32(0))
    yield "123-", SyntaxNumber(value=int32(-123))
    yield "456d", SyntaxNumber(value=int64(456))
    yield "0xFF", SyntaxNumber(value=uint8(255))
    yield "0xF01D-AB1E", SyntaxNumber(
        value=uint32(0xF01D_AB1E)
    )
    yield "0xA-B_C-D", SyntaxNumber(value=uint16(0xABCD))
    yield "0x0xh", SyntaxNumber(value=uint16(0))
    yield "0xDDxd", SyntaxNumber(value=uint64(0xDD))


@params(params_atom)
def test_atom(
    source: str, expected_result: SyntaxAtom
) -> None:
    assert parse_atom(source) == expected_result
