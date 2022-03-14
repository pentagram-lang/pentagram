from parse.group import parse_group
from parse.line import parse_lines
from parse.statement import parse_statements_block
from parse.word import parse_word_lines
from syntax import SyntaxBlock


def parse(source: str) -> SyntaxBlock:
    lines = parse_lines(source)
    word_lines = parse_word_lines(lines)
    group = parse_group(word_lines)
    return parse_statements_block(group)
