from __future__ import annotations

from io import IOBase
from numpy import integer
from pentagram.machine import MachineBlob
from pentagram.machine import MachineNumber
from pentagram.machine import MachineStream
from pentagram.machine import MachineValue
from typing import Any
from typing import get_origin


def from_python(
    python_type: type, value: Any
) -> MachineValue:
    origin_python_type = (
        get_origin(python_type) or python_type
    )
    if issubclass(origin_python_type, MachineValue):
        assert isinstance(value, MachineValue)
        return value
    elif issubclass(origin_python_type, IOBase):
        assert isinstance(value, IOBase)
        return MachineStream(value)
    elif issubclass(origin_python_type, bytearray):
        assert isinstance(value, bytearray)
        return MachineBlob(value)
    elif issubclass(origin_python_type, integer):
        assert isinstance(value, integer)
        return MachineNumber(value)
    else:
        raise AssertionError(value)


def to_python(
    python_type: type, value: MachineValue
) -> Any:
    origin_python_type = (
        get_origin(python_type) or python_type
    )
    if issubclass(origin_python_type, MachineValue):
        assert isinstance(value, MachineValue)
        return value
    elif issubclass(origin_python_type, IOBase):
        assert isinstance(value, MachineStream)
        return value.value
    elif issubclass(origin_python_type, bytearray):
        assert isinstance(value, MachineBlob)
        return value.value
    elif issubclass(origin_python_type, integer):
        assert isinstance(value, MachineNumber)
        return value.value
    else:
        raise AssertionError(value)


def from_python_name(name: str) -> str:
    return name.rstrip("_").replace("_", "-")
