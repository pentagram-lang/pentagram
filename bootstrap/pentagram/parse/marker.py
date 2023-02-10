from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Marker:
    pass


@dataclass
class MarkerAssignment(Marker):
    pass


@dataclass
class MarkerBlock(Marker):
    pass


@dataclass
class MarkerInlineStart(Marker):
    pass


@dataclass
class MarkerInlineEnd(Marker):
    pass


@dataclass
class MarkerMethodDefinition(Marker):
    pass
