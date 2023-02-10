from __future__ import annotations

from pentagram.parse.group import parse_group
from pentagram.parse.line import parse_lines
from pentagram.parse.syntax import parse_syntax
from pentagram.parse.word_line import parse_word_lines
from pentagram.syntax import SyntaxBlock


def parse(source: str) -> SyntaxBlock:
    lines = parse_lines(source)
    word_lines = parse_word_lines(lines)
    group = parse_group(word_lines)
    return parse_syntax(group)
