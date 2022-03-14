from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from io import IOBase
from numpy import integer
from syntax import SyntaxBlock
from syntax import SyntaxStatement
from syntax import SyntaxTerm
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from typing import Union


@dataclass
class MachineValue:
    pass


@dataclass
class MachineBlob(MachineValue):
    value: bytearray


@dataclass
class MachineNumber(MachineValue):
    value: integer
    value_type: Type = field(init=False)

    def __post_init__(self):
        self.value_type = type(self.value)
        assert issubclass(
            self.value_type, integer
        ), self.value_type


@dataclass
class MachineStream(MachineValue):
    value: IOBase


@dataclass
class MachineExpressionStack:
    values: List[MachineValue]

    def push(self, value: MachineValue) -> None:
        self.values.append(value)

    def push_many(self, values: List[MachineValue]) -> None:
        for value in values:
            self.push(value)

    def pop(self) -> MachineValue:
        return self.values.pop()

    def pop_many(self, count: int) -> MachineValue:
        assert len(self) >= count, (self, count)
        values = []
        for _ in range(count):
            values.append(self.values.pop())
        return values

    def __len__(self) -> int:
        return len(self.values)


@dataclass
class MachineCall(ABC):
    @abstractmethod
    def __call__(
        self, frame_stack: "MachineFrameStack"
    ) -> None:
        pass


@dataclass
class MachineBinding:
    name: str
    value_or_call: Union[MachineValue, MachineCall]

    @property
    def value(self):
        assert isinstance(self.value_or_call, MachineValue)
        return self.value_or_call

    @property
    def call(self):
        assert isinstance(self.value_or_call, MachineCall)
        return self.value_or_call


@dataclass
class MachineEnvironment:
    bindings: Dict[str, Union[MachineValue, MachineCall]]
    base: Optional["MachineEnvironment"]

    def extend(
        self,
        bindings: Optional[
            Dict[str, Union[MachineValue, MachineCall]]
        ] = None,
    ) -> "MachineEnvironment":
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
    ) -> Union[MachineValue, MachineCall]:
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
        value: Union[MachineValue, MachineCall],
    ) -> None:
        self.bindings[key] = value

    @staticmethod
    def from_bindings(
        bindings: List[MachineBinding]
    ) -> "MachineEnvironment":
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
    def statement_index(self, value) -> int:
        self.instruction_pointer.statement_index = value

    @property
    def statement(self) -> SyntaxStatement:
        return self.block.statements[self.statement_index]

    @property
    def term_index(self) -> int:
        return self.instruction_pointer.term_index

    @term_index.setter
    def term_index(self, value) -> int:
        self.instruction_pointer.term_index = value

    @property
    def term(self) -> SyntaxTerm:
        return self.statement.terms[self.term_index]


@dataclass
class MachineFrameStack:
    frames: List[MachineFrame]

    def push(self, frame: MachineFrame) -> None:
        self.frames.append(frame)

    def pop(self) -> None:
        return self.frames.pop()

    def __bool__(self) -> bool:
        return bool(self.frames)

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def current(self) -> MachineFrame:
        assert self.frames
        return self.frames[-1]
