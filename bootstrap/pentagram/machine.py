from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from io import IOBase
from numpy import integer
from pentagram.syntax import SyntaxBlock
from pentagram.syntax import SyntaxStatement
from pentagram.syntax import SyntaxTerm
from typing import Any
from typing import Generic
from typing import Type
from typing import TypeVar


@dataclass
class MachineValue:
    pass


TItem = TypeVar("TItem", bound=MachineValue)


@dataclass
class MachineArray(MachineValue, Generic[TItem]):
    value: list[TItem]


TInteger = TypeVar("TInteger", bound=integer[Any])


@dataclass
class MachineNumber(MachineValue, Generic[TInteger]):
    value: TInteger
    value_type: Type[TInteger] = field(init=False)

    def __post_init__(self) -> None:
        self.value_type = type(self.value)
        assert issubclass(
            self.value_type, integer
        ), self.value_type


@dataclass
class MachineStream(MachineValue):
    value: IOBase


@dataclass
class MachineExpressionStack:
    values: list[MachineValue]

    def push(self, value: MachineValue) -> None:
        self.values.append(value)

    def push_many(self, values: list[MachineValue]) -> None:
        for value in values:
            self.push(value)

    def pop(self) -> MachineValue:
        return self.values.pop()

    def pop_many(self, count: int) -> list[MachineValue]:
        assert len(self) >= count, (self, count)
        values = []
        for _ in range(count):
            values.append(self.values.pop())
        return values

    def __len__(self) -> int:
        return len(self.values)


class MachineCall(ABC):
    @abstractmethod
    def __call__(
        self, frame_stack: MachineFrameStack
    ) -> None:
        pass


@dataclass
class MachineBinding:
    name: str
    value_or_call: MachineValue | MachineCall


@dataclass
class MachineEnvironment:
    bindings: dict[str, MachineValue | MachineCall]
    base: MachineEnvironment | None

    def extend(
        self,
        bindings: dict[str, MachineValue | MachineCall]
        | None = None,
    ) -> MachineEnvironment:
        return MachineEnvironment(bindings or {}, base=self)

    def __contains__(self, key: str) -> bool:
        if key in self.bindings:
            return True
        elif self.base:
            return key in self.base
        else:
            return False

    def __getitem__(
        self, key: str
    ) -> MachineValue | MachineCall:
        value = self.bindings.get(key)
        if value is None:
            if self.base:
                return self.base[key]
            else:
                raise KeyError(key)
        else:
            return value

    def __setitem__(
        self,
        key: str,
        value: MachineValue | MachineCall,
    ) -> None:
        self.bindings[key] = value

    @staticmethod
    def from_bindings(
        bindings: list[MachineBinding],
    ) -> MachineEnvironment:
        return MachineEnvironment(
            bindings={
                binding.name: binding.value_or_call
                for binding in bindings
            },
            base=None,
        )


@dataclass
class MachineInstructionPointer:
    block: SyntaxBlock
    statement_index: int
    term_index: int


@dataclass
class MachineFrame:
    instruction_pointer: MachineInstructionPointer
    expression_stack: MachineExpressionStack
    environment: MachineEnvironment

    @property
    def block(self) -> SyntaxBlock:
        return self.instruction_pointer.block

    @property
    def statement_index(self) -> int:
        return self.instruction_pointer.statement_index

    @statement_index.setter
    def statement_index(self, value: int) -> None:
        self.instruction_pointer.statement_index = value

    @property
    def statement(self) -> SyntaxStatement:
        return self.block.statements[self.statement_index]

    @property
    def term_index(self) -> int:
        return self.instruction_pointer.term_index

    @term_index.setter
    def term_index(self, value: int) -> None:
        self.instruction_pointer.term_index = value

    @property
    def term(self) -> SyntaxTerm:
        return self.statement.terms[self.term_index]


@dataclass
class MachineFrameStack:
    frames: list[MachineFrame]

    def push(self, frame: MachineFrame) -> None:
        self.frames.append(frame)

    def pop(self) -> MachineFrame:
        return self.frames.pop()

    def __bool__(self) -> bool:
        return bool(self.frames)

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def current(self) -> MachineFrame:
        assert self.frames
        return self.frames[-1]
