from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from numpy import integer
from typing import Generic
from typing import Type
from typing import TypeVar


@dataclass
class SyntaxTerm:
    pass


TInteger = TypeVar("TInteger", bound=integer)


@dataclass
class SyntaxNumber(SyntaxTerm, Generic[TInteger]):
    value: TInteger
    value_type: Type[TInteger] = field(init=False)

    def __post_init__(self) -> None:
        self.value_type = type(self.value)
        assert issubclass(
            self.value_type, integer
        ), self.value_type


@dataclass
class SyntaxIdentifier(SyntaxTerm):
    name: str


@dataclass
class SyntaxComment(SyntaxTerm):
    text: str


@dataclass
class SyntaxBlock(SyntaxTerm):
    statements: list[SyntaxStatement]


@dataclass
class SyntaxStatement:
    terms: list[SyntaxTerm]


@dataclass
class SyntaxExpression(SyntaxStatement):
    pass


@dataclass
class SyntaxBinding(SyntaxStatement):
    bindings: list[SyntaxIdentifier]


@dataclass
class SyntaxAssignment(SyntaxBinding):
    pass


@dataclass
class SyntaxModification(SyntaxBinding):
    pass


@dataclass
class SyntaxMethodDefinition(SyntaxStatement):
    binding: SyntaxIdentifier
    definition_block: SyntaxBlock

    def __init__(
        self,
        binding: SyntaxIdentifier,
        definition: SyntaxStatement,
    ):
        super().__init__(terms=[])
        self.binding = binding
        self.definition_block = SyntaxBlock([definition])
