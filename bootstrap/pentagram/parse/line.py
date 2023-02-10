from __future__ import annotations

import re

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from pentagram.parse.marker import Marker
from pentagram.parse.marker import MarkerAssignment
from pentagram.parse.marker import MarkerBlock
from pentagram.parse.marker import MarkerMethodDefinition
from pentagram.parse.marker import MarkerStartBlock
from pentagram.parse.number import parse_number
from pentagram.syntax import SyntaxAtom
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber


@dataclass
class Line:
    indent: int
    terms: list[SyntaxAtom | Marker] = field(
        default_factory=list
    )
    comment: SyntaxComment | None = field(default=None)


def parse_lines(source: str) -> list[Line]:
    source_progress = deque(source)

    def loop() -> Iterable[Line]:
        while source_progress:
            yield parse_one_line(source_progress)

    return list(loop())


def parse_one_line(source_progress: deque[str]) -> Line:
    indent = parse_one_line_indent(source_progress)
    terms, comment = parse_one_line_words(source_progress)
    if source_progress:
        source_0 = source_progress[0]
        assert source_0 == "\n", source_progress
        source_progress.popleft()
    return Line(indent, terms, comment)


def parse_one_line_indent(
    source_progress: deque[str],
) -> int:
    indent = 0
    while source_progress:
        source_0 = source_progress[0]
        if source_0 == " ":
            indent += 1
            source_progress.popleft()
        else:
            break
    return indent


def parse_one_line_words(
    source_progress: deque[str],
) -> tuple[list[SyntaxAtom | Marker], SyntaxComment | None]:
    terms: list[SyntaxAtom | Marker] = []
    comment: SyntaxComment | None = []
    token_progress: list[str] = list()

    def token_end() -> None:
        nonlocal token_progress
        if token_progress:
            terms.append(
                parse_atom("".join(token_progress))
            )
            token_progress = list()

    while source_progress:
        source_0 = source_progress[0]
        source_1 = (
            source_progress[1]
            if len(source_progress) > 1
            else None
        )
        if source_0 == " ":
            token_end()
        elif source_0 == "\n":
            break
        elif source_0 == "=":
            token_end()
            terms.append(MarkerAssignment())
        elif source_0 == ":":
            token_end()
            terms.append(MarkerBlock())
        elif (source_0, source_1) == (">", ">"):
            token_end()
            terms.append(MarkerMethodDefinition())
        elif (source_0, source_1) == ("-", "-"):
            comment = parse_one_line_comment(
                source_progress
            )
            break
        else:
            token_progress.append(source_0)
        source_progress.popleft()

    token_end()
    return terms, comment


def parse_one_line_comment(
    source_progress: deque[str],
) -> SyntaxComment:
    source_progress.popleft()
    source_progress.popleft()
    comment_progress = list()
    while source_progress:
        source_0 = source_progress[0]
        if source_0 == "\n":
            break
        else:
            comment_progress.append(source_0)
            source_progress.popleft()
    return SyntaxComment("".join(comment_progress))


hex_start = re.compile(
    r"^0x",
    re.VERBOSE,
)

hex_pattern = re.compile(
    r"^"
    r"0x"
    r"(?P<digits> [0-9A-F]+ (?: [-_] [0-9A-F]+ )* )"
    r"(?: x (?P<suffix> [^-+] + ) ) ?"
    r"(?: (?P<sign> [-+] ) ) ?"
    r"$",
    re.VERBOSE,
)

decimal_start = re.compile(
    r"^[0-9]",
    re.VERBOSE,
)

decimal_pattern = re.compile(
    r"^"
    r"(?P<digits> [0-9]+ (?: [-_] [0-9]+ )* )"
    r"(?P<suffix> [^-+] + ) ?"
    r"(?P<sign> [-+] ) ?"
    r"$",
    re.VERBOSE,
)


def parse_atom(source: str) -> SyntaxAtom:
    if hex_start.match(source):
        hex_match = hex_pattern.match(source)
        assert hex_match is not None
        return SyntaxNumber(
            parse_number(
                base=16,
                digits=hex_match["digits"],
                suffix=hex_match["suffix"] or "",
                sign=hex_match["sign"] or "",
            )
        )
    if decimal_start.match(source):
        decimal_match = decimal_pattern.match(source)
        assert decimal_match is not None
        return SyntaxNumber(
            parse_number(
                base=10,
                digits=decimal_match["digits"],
                suffix=decimal_match["suffix"] or "",
                sign=hex_match["sign"] or "",
            )
        )
    return SyntaxIdentifier(source)
