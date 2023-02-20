from __future__ import annotations

from io import IOBase
from numpy import integer
from pentagram.machine import MachineArray
from pentagram.machine import MachineNumber
from pentagram.machine import MachineStream
from pentagram.machine import MachineValue
from typing import Any
from typing import cast
from typing import get_origin


def from_python(
    python_type: type, value: Any
) -> MachineValue:
    origin_python_type = (
        get_origin(python_type) or python_type
    )
    if issubclass(origin_python_type, MachineValue):
        assert isinstance(value, origin_python_type)
        return cast(MachineValue, value)
    elif issubclass(origin_python_type, IOBase):
        assert isinstance(value, origin_python_type)
        return MachineStream(value=value)
    elif issubclass(origin_python_type, list):
        assert isinstance(value, origin_python_type)
        return MachineArray(value=value)
    elif issubclass(origin_python_type, integer):
        assert isinstance(value, origin_python_type)
        return MachineNumber(value=value)
    else:
        raise AssertionError(value)


def to_python(
    python_type: type, value: MachineValue
) -> Any:
    origin_python_type = (
        get_origin(python_type) or python_type
    )
    if issubclass(origin_python_type, MachineValue):
        assert isinstance(value, origin_python_type)
        return value
    elif issubclass(origin_python_type, IOBase):
        assert isinstance(value, MachineStream)
        assert isinstance(value.value, origin_python_type)
        return value.value
    elif issubclass(origin_python_type, list):
        assert isinstance(value, MachineArray)
        assert isinstance(value.value, origin_python_type)
        return value.value
    elif issubclass(origin_python_type, integer):
        assert isinstance(value, MachineNumber)
        assert isinstance(value.value, origin_python_type)
        return value.value
    else:
        raise AssertionError(value)


def from_python_name(name: str) -> str:
    return name.rstrip("_").replace("_", "-")
