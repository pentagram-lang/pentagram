from __future__ import annotations

from dataclasses import dataclass
from pentagram.interpret.term import next_term
from pentagram.machine import Machine
from pentagram.machine import MachineCall
from pentagram.machine import MachineEnvironment
from pentagram.machine import MachineFrame
from pentagram.machine import MachineInstructionPointer
from pentagram.syntax import SyntaxBlock


@dataclass(frozen=True, kw_only=True)
class GuestCall(MachineCall):
    definition_environment: MachineEnvironment
    definition_block: SyntaxBlock

    def __call__(self, machine: Machine) -> None:
        next_term(machine)
        machine.push_frame(
            MachineFrame(
                instruction_pointer=MachineInstructionPointer(
                    block=self.definition_block,
                    statement_index=0,
                    term_index=0,
                ),
                environment=self.definition_environment.extend(),
            )
        )
