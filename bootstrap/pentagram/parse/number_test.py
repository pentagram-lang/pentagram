from __future__ import annotations

from collections.abc import Iterable
from numpy import int8
from numpy import int16
from numpy import int32
from numpy import int64
from numpy import integer
from numpy import uint8
from numpy import uint16
from numpy import uint32
from numpy import uint64
from numpy.typing import NBitBase
from pentagram.parse.number import parse_number
from pentagram.test import params
from typing import Any


def params_parse_number() -> Iterable[
    tuple[int, str, str, Any]
]:
    yield 16, "FF", "i", int8(-1)
    yield 10, "5", "b", uint8(5)
    yield 10, "72", "ih", int16(72)
    yield 16, "123", "", uint16(0x123)
    yield 10, "1029", "w", int32(1029)
    yield 16, "00AB-CDEF", "", uint32(0x00ABCDEF)
    yield 16, "0", "w", uint32(0)
    yield 16, "0", "id", int64(0)
    yield 10, "10-000-000-000", "ud", uint64(10_000_000_000)


@params(params_parse_number)
def test_parse_number(
    base: int,
    digits: str,
    suffix: str,
    expected: integer[NBitBase],
) -> None:
    result = parse_number(base, digits, suffix)
    assert result == expected
    assert type(result) is type(expected)
