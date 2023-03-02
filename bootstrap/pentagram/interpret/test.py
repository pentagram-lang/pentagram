from __future__ import annotations

from pentagram.environment import base_environment
from pentagram.interpret.interpret import init_machine
from pentagram.machine import Machine
from pentagram.machine import MachineCall
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock


def make_test_environment(
    bindings: dict[str, MachineValue | MachineCall]
    | None = None
) -> MachineEnvironment:
    return base_environment().extend(bindings)


def init_test_machine(
    block: SyntaxBlock,
    expression_stack: MachineExpressionStack,
    statement_index: int = 0,
    term_index: int = 0,
) -> Machine:
    return init_machine(
        block=block,
        expression_stack=expression_stack,
        environment=make_test_environment(),
        statement_index=statement_index,
        term_index=term_index,
    )
