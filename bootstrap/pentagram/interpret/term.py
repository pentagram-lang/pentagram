from __future__ import annotations

from pentagram.machine import Machine
from pentagram.machine import MachineCall
from pentagram.machine import MachineNumber
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.syntax import SyntaxNumber
from typing import Any


def interpret_expression_term(
    machine: Machine,
    statement: SyntaxExpression,
) -> None:
    term = statement.terms[machine.current_frame.term_index]
    if isinstance(term, SyntaxNumber):
        interpret_number_term(machine, term)
    elif isinstance(term, SyntaxIdentifier):
        interpret_identifier_term(machine, term)
    else:
        raise AssertionError(term)


def interpret_number_term(
    machine: Machine,
    number: SyntaxNumber[Any],
) -> None:
    machine.expression_stack.push(
        MachineNumber(value=number.value)
    )
    next_term(machine)


def interpret_identifier_term(
    machine: Machine,
    identifier: SyntaxIdentifier,
) -> None:
    environment = machine.current_frame.environment
    value_or_call = environment[identifier.name]
    if isinstance(value_or_call, MachineValue):
        machine.expression_stack.push(value_or_call)
        next_term(machine)
    elif isinstance(value_or_call, MachineCall):
        value_or_call(machine)
    else:
        raise AssertionError(value_or_call)


def next_term(machine: Machine) -> None:
    machine.current_frame.term_index += 1
