from __future__ import annotations

import math
import sys

from numpy import int32
from pentagram.host.convert import from_python
from pentagram.machine import MachineBinding
from typing import Any


def value(name: str, val: Any) -> MachineBinding:
    return MachineBinding(
        name=name, value_or_call=from_python(type(val), val)
    )


COUT = value("cout", sys.stdout.buffer)

PI = value("pi", int32(math.pi))
