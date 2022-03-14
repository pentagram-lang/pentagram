from io import BytesIO
from numpy import int16
from numpy import int32
from numpy import integer
from numpy import uint8
from numpy import uint64
from numpy.typing import NBitBase
from pentagram.host.simple_call import add
from pentagram.host.simple_call import cat
from pentagram.host.simple_call import nil_blob
from pentagram.host.simple_call import sqrt
from pentagram.host.simple_call import write
from pentagram.interpret import interpret
from pentagram.interpret.test import test_environment
from pentagram.machine import MachineBinding
from pentagram.machine import MachineBlob
from pentagram.machine import MachineExpressionStack
from pentagram.machine import MachineNumber
from pentagram.machine import MachineStream
from pentagram.machine import MachineValue
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxExpression
from pentagram.syntax import SyntaxIdentifier
from pentagram.test import params
from typing import Any
from typing import Iterable
from typing import Tuple


def call_test(
    binding: MachineBinding,
    args: list[MachineValue],
    results: list[MachineValue],
) -> None:
    term = SyntaxIdentifier(binding.name)
    block = SyntaxBlock([SyntaxExpression([term])])
    expression_stack = MachineExpressionStack(args)
    environment = test_environment()
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        results
    )


def params_add_blob() -> Iterable[Tuple[Any, bytes]]:
    yield uint8(0xF7), b"\xF7"
    yield int16(0xABCD), b"\xCD\xAB"
    yield int32(0x1234_5678), b"\x78\x56\x34\x12"
    yield uint64(1), b"\x01\0\0\0\0\0\0\0"


@params(params_add_blob)
def test_add_blob(
    number: integer[NBitBase], expected: bytes
) -> None:
    call_test(
        add,
        [MachineBlob(bytearray()), MachineNumber(number)],
        [MachineBlob(bytearray(expected))],
    )


def params_cat_blob() -> Iterable[Tuple[bytes, ...]]:
    yield b"", b"", b""
    yield b"a", b"", b"a"
    yield b"", b"b", b"b"
    yield b"123", b"456", b"123456"


@params(params_cat_blob)
def test_cat_blob(
    bytes_a: bytes, bytes_b: bytes, expected: bytes
) -> None:
    call_test(
        cat,
        [
            MachineBlob(bytearray(bytes_a)),
            MachineBlob(bytearray(bytes_b)),
        ],
        [MachineBlob(bytearray(expected))],
    )


def test_nil_blob() -> None:
    call_test(nil_blob, [], [MachineBlob(bytearray())])


def test_sqrt() -> None:
    call_test(
        sqrt,
        [MachineNumber(int32(4))],
        [MachineNumber(int32(2))],
    )


def test_write() -> None:
    bytes_io = BytesIO()
    call_test(
        write,
        [
            MachineStream(bytes_io),
            MachineBlob(bytearray(b"abcdef")),
        ],
        [],
    )
    assert bytes_io.getvalue() == b"abcdef"
