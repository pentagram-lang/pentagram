from __future__ import annotations

import pentagram.host.simple_call
import pentagram.host.value

from itertools import chain
from pentagram.machine import MachineBinding
from pentagram.machine import MachineEnvironment
from typing import Any


def base_environment() -> MachineEnvironment:
    return MachineEnvironment.from_bindings(
        extract_all_bindings(
            pentagram.host.simple_call, pentagram.host.value
        )
    )


def extract_all_bindings(
    *modules: Any,
) -> list[MachineBinding]:
    return list(
        chain.from_iterable(map(extract_bindings, modules))
    )


def extract_bindings(module: Any) -> list[MachineBinding]:
    return [
        export
        for export in module.__dict__.values()
        if isinstance(export, MachineBinding)
    ]
