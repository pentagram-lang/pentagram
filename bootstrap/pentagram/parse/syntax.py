from __future__ import annotations

from collections import deque
from pentagram.parse.group import Group
from pentagram.parse.line import Line
from pentagram.parse.marker import Marker
from pentagram.parse.marker import MarkerAssignment
from pentagram.parse.marker import MarkerMethodDefinition
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxAtom
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber
from pentagram.syntax import SyntaxStatement
from pentagram.syntax import SyntaxTerm
from typing import Iterable


class SyntaxError_(Exception):
    pass


def parse_syntax(group: Group) -> SyntaxBlock:
    def loop() -> Iterable[SyntaxStatement]:
        items_progress = deque(group.items)
        while items_progress:
            item = items_progress.popleft()
            if isinstance(item, Group):
                raise SyntaxError_(
                    "Unexpected nested group"
                )
            assert isinstance(item, Line), item
            yield parse_one_statement(
                items_progress, item, deque(item.terms)
            )

    return SyntaxBlock(statements=list(loop()))


def parse_one_statement(
    items_progress: deque[Line | Group],
    line: Line,
    terms_progress: deque[SyntaxAtom | Marker],
) -> SyntaxStatement:
    terms: list[SyntaxAtom] = []
    while terms_progress:
        term = terms_progress.popleft()
        if isinstance(term, MarkerAssignment):
            bindings = get_bindings(terms)
            if not bindings:
                raise SyntaxError_(
                    "Missing assignment binding"
                )
            block, comment = parse_next_block(
                items_progress, line, terms_progress
            )
            return SyntaxAssignment(
                bindings=bindings,
                block=block,
                comment=comment,
            )
        elif isinstance(term, MarkerMethodDefinition):
            bindings = get_bindings(terms)
            if not bindings:
                raise SyntaxError_("Missing method binding")
            elif len(bindings) > 1:
                raise SyntaxError_(
                    "Multiple method bindings"
                )
            block, comment = parse_next_block(
                items_progress, line, terms_progress
            )
            return SyntaxMethodDefinition(
                binding=bindings[0],
                block=block,
                comment=comment,
            )
        else:
            assert isinstance(term, SyntaxAtom), term
            terms.append(term)
    return SyntaxExpression(terms=terms)


def get_bindings(
    terms: list[SyntaxTerm],
) -> list[SyntaxIdentifier]:
    for term in terms:
        if isinstance(term, SyntaxNumber):
            raise SyntaxError_(
                "Unexpected number in binding"
            )
        else:
            assert isinstance(term, SyntaxIdentifier), term
    return terms


def parse_next_block(
    items_progress: deque[Line | Group],
    line: Line,
    terms_progress: deque[SyntaxAtom | Marker],
) -> tuple[SyntaxStatement, SyntaxComment | None]:
    if terms_progress:
        block = SyntaxBlock(
            statements=[
                parse_one_statement(
                    items_progress, line, terms_progress
                )
            ]
        )
        comment = None
    elif not items_progress or not isinstance(
        items_progress[0], Group
    ):
        raise SyntaxError_("Missing expected block")
    else:
        block = parse_syntax(items_progress.popleft())
        comment = line.comment
    return block, comment
