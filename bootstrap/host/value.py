import math
import sys

from host.convert import from_python
from machine import MachineBinding
from numpy import int32
from typing import Any


def value(name: str, val: Any) -> MachineBinding:
    return MachineBinding(name, from_python(val))


COUT = value("cout", sys.stdout.buffer)

PI = value("pi", int32(math.pi))
