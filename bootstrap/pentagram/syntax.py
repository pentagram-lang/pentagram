from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from numpy import integer
from typing import Any
from typing import Generic
from typing import Type
from typing import TypeVar


@dataclass(frozen=True, kw_only=True)
class SyntaxTerm:
    pass


@dataclass(frozen=True, kw_only=True)
class SyntaxAtom:
    pass


TInteger = TypeVar("TInteger", bound=integer[Any])


@dataclass(frozen=True, kw_only=True)
class SyntaxNumber(SyntaxAtom, Generic[TInteger]):
    value: TInteger
    value_type: Type[TInteger] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value_type", type(self.value)
        )
        assert issubclass(
            self.value_type, integer
        ), self.value_type


@dataclass(frozen=True, kw_only=True)
class SyntaxIdentifier(SyntaxAtom):
    name: str


@dataclass(frozen=True, kw_only=True)
class SyntaxComment:
    text: str


@dataclass(frozen=True, kw_only=True)
class SyntaxBlock:
    statements: list[SyntaxStatement]


@dataclass(frozen=True, kw_only=True)
class SyntaxStatement:
    comment: SyntaxComment | None = field(default=None)


@dataclass(frozen=True, kw_only=True)
class SyntaxExpression(SyntaxStatement):
    terms: list[SyntaxTerm]


@dataclass(frozen=True, kw_only=True)
class SyntaxAssignment(SyntaxStatement):
    bindings: list[SyntaxIdentifier]
    block: SyntaxBlock


@dataclass(frozen=True, kw_only=True)
class SyntaxModification(SyntaxStatement):
    bindings: list[SyntaxIdentifier]
    block: SyntaxBlock


@dataclass(frozen=True, kw_only=True)
class SyntaxMethodDefinition(SyntaxStatement):
    binding: SyntaxIdentifier
    block: SyntaxBlock
