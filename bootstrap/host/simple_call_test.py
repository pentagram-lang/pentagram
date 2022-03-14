from host.simple_call import add
from host.simple_call import cat
from host.simple_call import nil_blob
from host.simple_call import sqrt
from host.simple_call import write
from interpret import interpret
from interpret.test import test_environment
from io import BytesIO
from machine import MachineBlob
from machine import MachineExpressionStack
from machine import MachineNumber
from machine import MachineStream
from numpy import int16
from numpy import int32
from numpy import uint8
from numpy import uint64
from syntax import SyntaxBlock
from syntax import SyntaxExpression
from syntax import SyntaxIdentifier
from test import params


def call_test(binding, args, results):
    term = SyntaxIdentifier(binding.name)
    block = SyntaxBlock([SyntaxExpression([term])])
    expression_stack = MachineExpressionStack(args)
    environment = test_environment()
    interpret(block, expression_stack, environment)
    assert expression_stack == MachineExpressionStack(
        results
    )


def params_add_blob():
    yield uint8(0xF7), b"\xF7"
    yield int16(0xABCD), b"\xCD\xAB"
    yield int32(0x1234_5678), b"\x78\x56\x34\x12"
    yield uint64(1), b"\x01\0\0\0\0\0\0\0"


@params(params_add_blob)
def test_add_blob(number, expected):
    call_test(
        add,
        [MachineBlob(bytearray()), MachineNumber(number)],
        [MachineBlob(bytearray(expected))],
    )


def params_cat_blob():
    yield b"", b"", b""
    yield b"a", b"", b"a"
    yield b"", b"b", b"b"
    yield b"123", b"456", b"123456"


@params(params_cat_blob)
def test_cat_blob(bytes_a, bytes_b, expected):
    call_test(
        cat,
        [
            MachineBlob(bytearray(bytes_a)),
            MachineBlob(bytearray(bytes_b)),
        ],
        [MachineBlob(bytearray(expected))],
    )


def test_nil_blob():
    call_test(nil_blob, [], [MachineBlob(bytearray())])


def test_sqrt():
    call_test(
        sqrt,
        [MachineNumber(int32(4))],
        [MachineNumber(int32(2))],
    )


def test_write():
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
