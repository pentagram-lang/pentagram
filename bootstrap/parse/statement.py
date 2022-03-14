from parse.group import Group
from parse.group import GroupComment
from parse.group import GroupIdentifier
from parse.group import GroupNumber
from parse.group import GroupTerm
from syntax import SyntaxAssignment
from syntax import SyntaxBlock
from syntax import SyntaxComment
from syntax import SyntaxExpression
from syntax import SyntaxIdentifier
from syntax import SyntaxMethodDefinition
from syntax import SyntaxNumber
from syntax import SyntaxStatement
from syntax import SyntaxTerm
from typing import List


def parse_statements_block(group: Group) -> SyntaxBlock:
    return SyntaxBlock(
        [
            parse_one_statement(line.terms)
            for line in group.lines
        ]
    )


def parse_one_statement(
    terms: List[GroupTerm],
) -> SyntaxStatement:
    bindings: List[SyntaxIdentifier] = []
    for term in terms:
        if isinstance(term, GroupIdentifier):
            if term.name == "=":
                return SyntaxAssignment(
                    terms=parse_terms(
                        terms[len(bindings) + 1 :]
                    ),
                    bindings=bindings,
                )
            elif term.name == "/=":
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
    terms: List[GroupTerm],
) -> List[SyntaxTerm]:
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
        assert False, term
