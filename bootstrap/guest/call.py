from dataclasses import dataclass
from interpret.term import next_term
from machine import MachineCall
from machine import MachineEnvironment
from machine import MachineFrame
from machine import MachineFrameStack
from machine import MachineInstructionPointer
from syntax import SyntaxBlock


@dataclass
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
