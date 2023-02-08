from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from numpy import integer
from pentagram.parse.word import WordComment
from pentagram.parse.word import WordIdentifier
from pentagram.parse.word import WordLine
from pentagram.parse.word import WordNumber
from pentagram.parse.word import WordTerm
from typing import Generic
from typing import TypeVar


@dataclass
class GroupTerm:
    pass


TInteger = TypeVar("TInteger", bound=integer)


@dataclass
class GroupNumber(GroupTerm, Generic[TInteger]):
    value: TInteger
    value_type: type[TInteger] = field(init=False)

    def __post_init__(self) -> None:
        self.value_type = type(self.value)
        assert issubclass(
            self.value_type, integer
        ), self.value_type


@dataclass
class GroupIdentifier(GroupTerm):
    name: str


@dataclass
class GroupComment(GroupTerm):
    text: str


@dataclass
class Group(GroupTerm):
    lines: list[GroupLine]


@dataclass
class GroupLine:
    terms: list[GroupTerm]


def parse_group(lines: list[WordLine]) -> Group:
    groups = [Group([])]
    substantial_indent_level = -1

    def group_end(indent_level: int) -> None:
        while indent_level < len(groups) - 1:
            groups[-2].lines[-1].terms.append(groups.pop())

    for line in lines:
        if not line.terms:
            indent_level = substantial_indent_level + 1
        elif len(line.terms) == 1 and isinstance(
            line.terms[0], WordComment
        ):
            indent_level = min(
                substantial_indent_level + 1,
                line.indent // 2,
            )
        else:
            assert line.indent % 2 == 0, line
            indent_level = line.indent // 2
            assert indent_level <= len(groups), line
            substantial_indent_level = indent_level
        if indent_level == len(groups):
            groups.append(Group([]))
        group_end(indent_level)
        groups[-1].lines.append(
            GroupLine(parse_group_terms(line.terms))
        )

    group_end(0)
    return groups[0]


def parse_group_terms(
    terms: list[WordTerm],
) -> list[GroupTerm]:
    return [parse_one_group_term(term) for term in terms]


def parse_one_group_term(term: WordTerm) -> GroupTerm:
    if isinstance(term, WordNumber):
        return GroupNumber(term.value)
    elif isinstance(term, WordIdentifier):
        return GroupIdentifier(term.name)
    elif isinstance(term, WordComment):
        return GroupComment(term.text)
    else:
        raise AssertionError(term)
