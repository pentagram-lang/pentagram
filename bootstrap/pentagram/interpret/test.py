from __future__ import annotations

from pentagram.environment import base_environment
from pentagram.interpret.interpret import init_frame_stack
from pentagram.machine import MachineCall
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock
from typing import Optional


def test_environment(
    bindings: Optional[
        dict[str, MachineValue | MachineCall]
    ] = None
) -> MachineEnvironment:
    return base_environment().extend(bindings)


def init_test_frame_stack(
    block: SyntaxBlock,
    expression_stack: MachineExpressionStack,
    statement_index: int = 0,
    term_index: int = 0,
) -> MachineFrameStack:
    return init_frame_stack(
        block=block,
        expression_stack=expression_stack,
        environment=test_environment(),
        statement_index=statement_index,
        term_index=term_index,
    )
