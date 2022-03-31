from __future__ import annotations

from collections.abc import Iterable
from pentagram.parse.line import Line
from pentagram.parse.line import LineComment
from pentagram.parse.line import LineWord
from pentagram.parse.line import parse_lines
from pentagram.test import params


def params_lines() -> Iterable[tuple[str, list[Line]]]:
    yield "a\n" "b\n", [
        Line(indent=0, terms=[LineWord("a")]),
        Line(indent=0, terms=[LineWord("b")]),
    ]
    yield "a0 1b c-2\n" "  def ghi\n", [
        Line(
            indent=0,
            terms=[
                LineWord("a0"),
                LineWord("1b"),
                LineWord("c-2"),
            ],
        ),
        Line(
            indent=2,
            terms=[LineWord("def"), LineWord("ghi")],
        ),
    ]
    yield "\n" "    \n", [
        Line(indent=0, terms=[]),
        Line(indent=4, terms=[]),
    ]
    yield "   -- desc\n" "0x1-2--xyz\n", [
        Line(indent=3, terms=[LineComment(" desc")]),
        Line(
            indent=0,
            terms=[LineWord("0x1-2"), LineComment("xyz")],
        ),
    ]


@params(params_lines)
def test_lines(
    lines: str, expected_result: list[Line]
) -> None:
    assert parse_lines(lines) == expected_result
