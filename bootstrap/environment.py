import host.simple_call
import host.value

from itertools import chain
from machine import MachineBinding
from machine import MachineEnvironment
from typing import Any
from typing import List


def base_environment() -> MachineEnvironment:
    return MachineEnvironment.from_bindings(
        extract_all_bindings(host.simple_call, host.value)
    )


def extract_all_bindings(
    *modules: Any
) -> List[MachineBinding]:
    return list(
        chain.from_iterable(map(extract_bindings, modules))
    )


def extract_bindings(module: Any) -> List[MachineBinding]:
    return [
        export
        for export in module.__dict__.values()
        if isinstance(export, MachineBinding)
    ]
