import re

from dataclasses import dataclass
from dataclasses import field
from numpy import integer
from numpy.typing import NBitBase
from pentagram.parse.line import Line
from pentagram.parse.line import LineComment
from pentagram.parse.line import LineTerm
from pentagram.parse.line import LineWord
from pentagram.parse.number import parse_number
from typing import Generic
from typing import List
from typing import Type
from typing import TypeVar


@dataclass
class WordTerm:
    pass


TBit = TypeVar("TBit", bound=NBitBase)


@dataclass
class WordNumber(WordTerm, Generic[TBit]):
    value: integer[TBit]
    value_type: Type[integer[TBit]] = field(init=False)

    def __post_init__(self) -> None:
        self.value_type = type(self.value)
        assert issubclass(
            self.value_type, integer
        ), self.value_type


@dataclass
class WordIdentifier(WordTerm):
    name: str


@dataclass
class WordComment(WordTerm):
    text: str


@dataclass
class WordLine:
    indent: int
    terms: List[WordTerm]


def parse_word_lines(lines: list[Line]) -> List[WordLine]:
    return [parse_one_word_line(line) for line in lines]


def parse_one_word_line(line: Line) -> WordLine:
    return WordLine(
        indent=line.indent,
        terms=[
            parse_one_word_term(term) for term in line.terms
        ],
    )


hex_pattern = re.compile(
    r"^"
    r"0x"
    r"(?P<digits> [-0-9A-F]+ )"
    r"(?: x (?P<suffix> .+ ) ) ?"
    r"$",
    re.VERBOSE,
)

decimal_pattern = re.compile(
    r"^"
    r"(?P<digits> [-0-9]+ )"
    r"(?P<suffix> .+ ) ?"
    r"$",
    re.VERBOSE,
)


def parse_one_word_term(term: LineTerm) -> WordTerm:
    if isinstance(term, LineComment):
        return WordComment(text=term.text)
    elif isinstance(term, LineWord):
        hex_match = hex_pattern.match(term.text)
        if hex_match:
            return WordNumber(
                parse_number(
                    base=16,
                    digits=hex_match["digits"],
                    suffix=hex_match["suffix"] or "",
                )
            )
        decimal_match = decimal_pattern.match(term.text)
        if decimal_match:
            return WordNumber(
                parse_number(
                    base=10,
                    digits=decimal_match["digits"],
                    suffix=decimal_match["suffix"] or "",
                )
            )
        return WordIdentifier(term.text)
    else:
        raise NotImplementedError()
