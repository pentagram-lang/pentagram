from io import IOBase
from machine import MachineBlob
from machine import MachineNumber
from machine import MachineStream
from machine import MachineValue
from numpy import integer
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
        assert False, value


def to_python(value: MachineValue) -> Any:
    simple_values = (
        MachineBlob,
        MachineNumber,
        MachineStream,
    )
    if isinstance(value, simple_values):
        return value.value
    else:
        assert False, value
