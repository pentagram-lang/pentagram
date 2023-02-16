from __future__ import annotations

from pentagram.parse.group import parse_group
from pentagram.parse.line import parse_lines
from pentagram.parse.syntax import parse_syntax
from pentagram.syntax import SyntaxBlock


def parse(source: str) -> SyntaxBlock:
    lines = parse_lines(source)
    group = parse_group(lines)
    return parse_syntax(group)
