from dataclasses import dataclass
from dataclasses import field
from numpy import integer
from typing import List
from typing import Type


@dataclass
class SyntaxTerm:
    pass


@dataclass
class SyntaxNumber(SyntaxTerm):
    value: integer
    value_type: Type = field(init=False)

    def __post_init__(self):
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
    statements: List["SyntaxStatement"]


@dataclass
class SyntaxStatement:
    terms: List[SyntaxTerm]


@dataclass
class SyntaxExpression(SyntaxStatement):
    pass


@dataclass
class SyntaxBinding(SyntaxStatement):
    bindings: List[SyntaxIdentifier]


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
