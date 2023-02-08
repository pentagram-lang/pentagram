from __future__ import annotations

from pentagram.parse.group import Group
from pentagram.parse.group import GroupComment
from pentagram.parse.group import GroupIdentifier
from pentagram.parse.group import GroupNumber
from pentagram.parse.group import GroupTerm
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxComment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxMethodDefinition
from pentagram.syntax import SyntaxNumber
from pentagram.syntax import SyntaxStatement
from pentagram.syntax import SyntaxTerm


def parse_statements_block(group: Group) -> SyntaxBlock:
    return SyntaxBlock(
        [
            parse_one_statement(line.terms)
            for line in group.lines
        ]
    )


def parse_one_statement(
    terms: list[GroupTerm],
) -> SyntaxStatement:
    bindings: list[SyntaxIdentifier] = []
    for term in terms:
        if isinstance(term, GroupIdentifier):
            if term.name == "=":
                return SyntaxAssignment(
                    bindings=bindings,
                    terms=parse_terms(
                        terms[len(bindings) + 1 :]
                    ),
                )
            elif term.name == ">>":
                assert len(bindings) == 1
                return SyntaxMethodDefinition(
                    binding=bindings[0],
                    definition=parse_one_statement(
                        terms[2:]
                    ),
                )
            else:
                bindings.append(SyntaxIdentifier(term.name))
        else:
            break
    return SyntaxExpression(parse_terms(terms))


def parse_terms(
    terms: list[GroupTerm],
) -> list[SyntaxTerm]:
    return [parse_one_term(term) for term in terms]


def parse_one_term(term: GroupTerm) -> SyntaxTerm:
    if isinstance(term, GroupNumber):
        return SyntaxNumber(term.value)
    elif isinstance(term, GroupIdentifier):
        return SyntaxIdentifier(term.name)
    elif isinstance(term, GroupComment):
        return SyntaxComment(term.text)
    elif isinstance(term, Group):
        return parse_statements_block(term)
    else:
        raise AssertionError(term)
