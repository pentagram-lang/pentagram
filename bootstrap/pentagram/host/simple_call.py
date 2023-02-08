from __future__ import annotations

import math

from dataclasses import dataclass
from dataclasses import field
from inspect import Signature
from inspect import signature
from io import IOBase
from numpy import int32
from numpy import integer
from numpy import uint8
from pentagram.host.convert import from_python
from pentagram.host.convert import from_python_name
from pentagram.host.convert import to_python
from pentagram.interpret.term import next_term
from pentagram.machine import MachineBinding
from pentagram.machine import MachineCall
from pentagram.machine import MachineFrameStack
from pentagram.machine import MachineNumber
from pentagram.machine import MachineValue
from sys import byteorder
from typing import Any
from typing import Callable
from typing import get_args


@dataclass
class SimpleHostCall(MachineCall):
    func: Callable[..., Any]
    signature: Signature = field(init=False)

    def __post_init__(self) -> None:
        self.signature = signature(self.func, eval_str=True)

    def __call__(
        self, frame_stack: MachineFrameStack
    ) -> None:
        frame = frame_stack.current
        expression_stack = frame.expression_stack
        try:
            converted_args = []
            for parameter in reversed(
                self.signature.parameters.values()
            ):
                arg = expression_stack.pop()
                converted_args.append(
                    to_python(parameter.annotation, arg)
                )
            results = self.func(*reversed(converted_args))
            if self.signature.return_annotation is None:
                result_types: tuple[Any, ...] = ()
            elif issubclass(
                self.signature.return_annotation, tuple
            ):
                result_types = get_args(
                    self.signature.return_annotation
                )
            else:
                result_types = (
                    self.signature.return_annotation,
                )
                results = (results,)
            converted_results = []
            for i, result_type in enumerate(result_types):
                converted_results.append(
                    from_python(result_type, results[i])
                )
        except Exception as e:
            raise Exception(f"Error calling {self}") from e
        expression_stack.push_many(converted_results)
        next_term(frame_stack)


def simple_call(func: Callable[..., Any]) -> MachineBinding:
    return MachineBinding(
        from_python_name(func.__name__),
        SimpleHostCall(func),
    )


@simple_call
def add(
    array: list[MachineValue], value: MachineValue
) -> list[MachineValue]:
    return array + [value]


@simple_call
def arr(init: Any) -> list[MachineValue]:
    return list()


@simple_call
def cat(
    initial_array: list[MachineValue],
    concatenation_array: list[MachineValue],
) -> list[MachineValue]:
    return initial_array + concatenation_array


@simple_call
def sqrt(x: int32) -> int32:
    return int32(math.sqrt(x))


@simple_call
def to_be(value: integer[Any]) -> list[MachineValue]:
    value = (
        value.byteswap() if byteorder == "little" else value
    )
    return [
        MachineNumber(uint8(byte))
        for byte in value.tobytes()
    ]


@simple_call
def to_le(value: integer[Any]) -> list[MachineValue]:
    value = (
        value if byteorder == "little" else value.byteswap()
    )
    return [
        MachineNumber(uint8(byte))
        for byte in value.tobytes()
    ]


@simple_call
def to_me(value: integer[Any]) -> list[MachineValue]:
    return [
        MachineNumber(uint8(byte))
        for byte in value.tobytes()
    ]


@simple_call
def write(
    stream: IOBase, array: list[MachineNumber[uint8]]
) -> None:
    stream.write(bytes([item.value for item in array]))
