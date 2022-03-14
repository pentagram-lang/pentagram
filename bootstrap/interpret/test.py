from environment import base_environment
from interpret.interpret import init_frame_stack
from machine import MachineCall
from machine import MachineEnvironment
from machine import MachineExpressionStack
from machine import MachineFrameStack
from machine import MachineValue
from syntax import SyntaxBlock
from typing import Dict
from typing import Optional
from typing import Union


def test_environment(
    bindings: Optional[
        Dict[str, Union[MachineValue, MachineCall]]
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
