from __future__ import annotations

import re

from math import ceil
from math import log2
from numpy import integer
from numpy import sctypeDict
from typing import Any
from typing import cast

ignored_digits = re.compile(
    r"[-_]",
    re.VERBOSE,
)


def parse_number(
    base: int, digits: str, suffix: str, sign: str
) -> integer[Any]:
    digits = ignored_digits.sub("", digits)

    if base == 10:
        bits = 32
        signed = True
    else:
        bits = 2 ** (ceil(log2(len(digits))) + 2)
        bits = max(8, min(64, bits))
        signed = False

    if suffix.endswith("b"):
        bits = 8
        signed = False
    elif suffix.endswith("h"):
        bits = 16
    elif suffix.endswith("w"):
        bits = 32
    elif suffix.endswith("d"):
        bits = 64

    if suffix.startswith("i"):
        signed = True
    elif suffix.startswith("u"):
        signed = False

    type_name = f"{'' if signed else 'u'}int{bits}"
    int_value = int(digits, base) * (
        -1 if sign == "-" else 1
    )
    return cast(
        integer[Any], sctypeDict[type_name](int_value)
    )
