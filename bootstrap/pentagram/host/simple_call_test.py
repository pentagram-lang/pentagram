from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO
from numpy import int16
from numpy import int32
from numpy import integer
from numpy import uint8
from numpy import uint64
from pentagram.host.simple_call import add
from pentagram.host.simple_call import arr
from pentagram.host.simple_call import cat
from pentagram.host.simple_call import sqrt
from pentagram.host.simple_call import to_be
from pentagram.host.simple_call import to_le
from pentagram.host.simple_call import to_me
from pentagram.host.simple_call import write
from pentagram.interpret import interpret
from pentagram.interpret.test import make_test_environment
from pentagram.machine import MachineArray
from pentagram.machine import MachineBinding
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineNumber
from pentagram.machine import MachineStream
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.test import params
from sys import byteorder
from typing import Any


def call_test(
    binding: MachineBinding,
    args: list[MachineValue],
    results: list[MachineValue],
) -> None:
    term = SyntaxIdentifier(binding.name)
    block = SyntaxBlock([SyntaxExpression([term])])
    expression_stack = MachineExpressionStack(args)
    environment = make_test_environment()
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        results
    )


def test_add() -> None:
    call_test(
        add,
        [
            MachineArray([MachineNumber(uint8(0x01))]),
            MachineNumber(uint8(0x02)),
        ],
        [
            MachineArray(
                [
                    MachineNumber(uint8(0x01)),
                    MachineNumber(uint8(0x02)),
                ]
            ),
        ],
    )


def test_arr() -> None:
    call_test(arr, [MachineValue()], [MachineArray([])])


def params_cat() -> Iterable[tuple[bytes, ...]]:
    yield b"", b"", b""
    yield b"a", b"", b"a"
    yield b"", b"b", b"b"
    yield b"123", b"456", b"123456"


@params(params_cat)
def test_cat(
    bytes_a: bytes, bytes_b: bytes, expected: bytes
) -> None:
    call_test(
        cat,
        [
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in bytes_a
                ]
            ),
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in bytes_b
                ]
            ),
        ],
        [
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in bytes_a + bytes_b
                ]
            )
        ],
    )


def test_sqrt() -> None:
    call_test(
        sqrt,
        [MachineNumber(int32(4))],
        [MachineNumber(int32(2))],
    )


def params_to_endian() -> Iterable[tuple[Any, bytes]]:
    yield uint8(0xF7), b"\xF7"
    yield int16(0xABCD), b"\xCD\xAB"
    yield int32(0x1234_5678), b"\x78\x56\x34\x12"
    yield uint64(1), b"\x01\0\0\0\0\0\0\0"


@params(params_to_endian)
def test_to_endian(
    number: integer[Any], expected_le: list[MachineValue]
) -> None:
    call_test(
        to_be,
        [MachineNumber(number)],
        [
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in reversed(expected_le)
                ]
            )
        ],
    )
    call_test(
        to_le,
        [MachineNumber(number)],
        [
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in expected_le
                ]
            )
        ],
    )
    call_test(
        to_me,
        [MachineNumber(number)],
        [
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in (
                        expected_le
                        if byteorder == "little"
                        else reversed(expected_le)
                    )
                ]
            )
        ],
    )


def test_write() -> None:
    bytes_io = BytesIO()
    call_test(
        write,
        [
            MachineStream(bytes_io),
            MachineArray(
                [
                    MachineNumber(uint8(byte))
                    for byte in b"abcdef"
                ]
            ),
        ],
        [],
    )
    assert bytes_io.getvalue() == b"abcdef"
