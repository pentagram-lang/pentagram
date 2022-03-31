from __future__ import annotations

from io import IOBase
from numpy import integer
from pentagram.machine import MachineBlob
from pentagram.machine import MachineNumber
from pentagram.machine import MachineStream
from pentagram.machine import MachineValue
from typing import Any


def from_python(value: Any) -> MachineValue:
    if isinstance(value, IOBase):
        return MachineStream(value)
    elif isinstance(value, MachineValue):
        return value
    elif isinstance(value, bytearray):
        return MachineBlob(value)
    elif isinstance(value, integer):
        return MachineNumber(value)
    else:
        raise AssertionError(value)


def to_python(value: MachineValue) -> Any:
    simple_values = (
        MachineBlob,
        MachineNumber,
        MachineStream,
    )
    if isinstance(value, simple_values):
        return value.value
    else:
        raise AssertionError(value)
