from __future__ import annotations

from pentagram.guest.call import GuestCall
from pentagram.interpret.term import (
    interpret_expression_term,
)
from pentagram.interpret.term import next_term
from pentagram.machine import Machine
from pentagram.machine import MachineFrame
from pentagram.machine import MachineInstructionPointer
from pentagram.syntax import SyntaxAssignment
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxMethodDefinition


def interpret_statement(
    machine: Machine,
) -> None:
    statement = machine.current_frame.statement
    term_index = machine.current_frame.term_index
    if isinstance(statement, SyntaxExpression):
        if term_index < len(statement.terms):
            interpret_expression_term(machine, statement)
        else:
            next_statement(machine)
    elif isinstance(statement, SyntaxAssignment):
        if term_index == 0:
            interpret_assignment_enter(machine, statement)
        else:
            interpret_assignment_exit(machine, statement)
            next_statement(machine)
    elif isinstance(statement, SyntaxMethodDefinition):
        interpret_method_definition(machine, statement)
        next_statement(machine)
    else:
        raise AssertionError(statement)


def interpret_assignment_enter(
    machine: Machine,
    statement: SyntaxAssignment,
) -> None:
    next_term(machine)
    machine.push_frame(
        MachineFrame(
            instruction_pointer=MachineInstructionPointer(
                block=statement.block,
                statement_index=0,
                term_index=0,
            ),
            environment=machine.current_frame.environment.extend(),
        )
    )


def interpret_assignment_exit(
    machine: Machine,
    assignment: SyntaxAssignment,
) -> None:
    environment = machine.current_frame.environment
    for binding in reversed(assignment.bindings):
        assert machine.expression_stack, binding
        environment[
            binding.name
        ] = machine.expression_stack.pop()


def interpret_method_definition(
    machine: Machine,
    method_definition: SyntaxMethodDefinition,
) -> None:
    environment = machine.current_frame.environment
    environment[method_definition.binding.name] = GuestCall(
        definition_environment=environment,
        definition_block=method_definition.block,
    )


def next_statement(machine: Machine) -> None:
    machine.current_frame.statement_index += 1
    machine.current_frame.term_index = 0
