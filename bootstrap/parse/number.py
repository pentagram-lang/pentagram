from math import ceil
from math import log2
from numpy import integer
from numpy import sctypeDict


def parse_number(
    base: int, digits: str, suffix: str
) -> integer:
    digits = digits.replace("-", "")

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
    int_value = int(digits, base)
    return sctypeDict[type_name](int_value)
