from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Marker:
    pass


@dataclass(frozen=True, kw_only=True)
class MarkerAssignment(Marker):
    pass


@dataclass(frozen=True, kw_only=True)
class MarkerBlock(Marker):
    pass


@dataclass(frozen=True, kw_only=True)
class MarkerInlineStart(Marker):
    pass


@dataclass(frozen=True, kw_only=True)
class MarkerInlineEnd(Marker):
    pass


@dataclass(frozen=True, kw_only=True)
class MarkerMethodDefinition(Marker):
    pass
