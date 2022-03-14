from collections import deque
from dataclasses import dataclass
from typing import Deque
from typing import List
from typing import Optional


@dataclass
class LineTerm:
    pass


@dataclass
class LineWord(LineTerm):
    text: str


@dataclass
class LineComment(LineTerm):
    text: str


@dataclass
class Line:
    indent: int
    terms: List[LineTerm]


def parse_lines(source: str) -> List[Line]:
    source_progress = deque(source)

    def loop():
        while source_progress:
            yield parse_one_line(source_progress)

    return list(loop())


def parse_one_line(source_progress: Deque[str]) -> Line:
    indent = parse_one_line_indent(source_progress)
    terms = parse_one_line_words(source_progress)
    comment = parse_one_line_comment(source_progress)
    if comment:
        terms.append(comment)
    if source_progress:
        source_0 = source_progress[0]
        assert source_0 == "\n", source_progress
        source_progress.popleft()
    return Line(indent, terms)


def parse_one_line_indent(
    source_progress: Deque[str]
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
    source_progress: Deque[str]
) -> List[LineTerm]:
    terms = []
    token_progress = list()

    def token_end():
        nonlocal token_progress
        if token_progress:
            terms.append(LineWord("".join(token_progress)))
            token_progress = list()

    while source_progress:
        source_0 = source_progress[0]
        if source_0 == " ":
            token_end()
        elif source_0 == "\n":
            break
        elif source_0 == ":":
            token_end()
            terms.append(LineWord(":"))
        elif source_0 == "-" and len(source_progress) > 1:
            source_1 = source_progress[1]
            if source_1 == "-":
                break
            else:
                token_progress.append(source_0)
        else:
            token_progress.append(source_0)
        source_progress.popleft()

    token_end()
    return terms


def parse_one_line_comment(
    source_progress: Deque[str]
) -> Optional[LineComment]:
    comment = None

    if len(source_progress) > 1:
        source_0 = source_progress[0]
        source_1 = source_progress[1]

        if source_0 == "-" and source_1 == "-":
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
            comment = LineComment("".join(comment_progress))
    return comment
