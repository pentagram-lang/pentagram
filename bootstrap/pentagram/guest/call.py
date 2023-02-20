from __future__ import annotations

from dataclasses import dataclass
from pentagram.interpret.term import next_term
from pentagram.machine import MachineCall
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineFrame
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineInstructionPointer
from pentagram.syntax import SyntaxBlock


@dataclass(frozen=True, kw_only=True)
class GuestCall(MachineCall):
    definition_environment: MachineEnvironment
    definition_block: SyntaxBlock

    def __call__(
        self, frame_stack: MachineFrameStack
    ) -> None:
        next_term(frame_stack)
        frame_stack.push(
            MachineFrame(
                MachineInstructionPointer(
                    self.definition_block,
                    statement_index=0,
                    term_index=0,
                ),
                frame_stack.current.expression_stack,
                self.definition_environment.extend(),
            )
        )
