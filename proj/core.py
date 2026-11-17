import re
from dataclasses import dataclass, fields, is_dataclass
from typing import Final, Literal, NewType

__all__ = [
  'BLOCKER_STATUSES',
  'GOAL_STATUSES',
  'HANDOFF_LIMIT',
  'HANDOFF_TEXT_LIMIT',
  'MAX_GOAL_TEXT_LENGTH',
  'MAX_PROJECT_NAME_LENGTH',
  'PROJECT_SUFFIX',
  'TASK_STATUSES',
  'UNICODE_WHITESPACE',
  'UNSET',
  'BlockerFilterStatus',
  'BlockerStatus',
  'CharterContextStatus',
  'CharterInput',
  'ClaimStatus',
  'FocusKind',
  'GoalReference',
  'GoalStatus',
  'GoalText',
  'PositiveInt',
  'ProjectError',
  'ProjectName',
  'ProjectStatus',
  'RecordContextStatus',
  'StageName',
  'StageReference',
  'StageStatus',
  'SubstantiveText',
  'TaskStatus',
  'TaskTag',
  'TitleStatus',
  'Unset',
  'dataclass_to_dict',
  'is_substantive',
  'parse_goal_reference',
  'parse_stage_reference',
]

PROJECT_SUFFIX: Final[str] = '.sqlite3'
MAX_PROJECT_NAME_LENGTH: Final[int] = 200
MAX_GOAL_TEXT_LENGTH: Final[int] = 4000
HANDOFF_LIMIT: Final[int] = 5
HANDOFF_TEXT_LIMIT: Final[int] = 1000
UNICODE_WHITESPACE: Final[str] = ''.join(
  chr(cp)
  for cp in range(0x110000)
  if not (0xD800 <= cp <= 0xDFFF) and chr(cp).isspace()
)

_PROJECT_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
  r'^[^/\\\x00]+$'
)

type ProjectStatus = Literal['complete', 'active', 'blocked']
type StageStatus = Literal[
  'active', 'pending', 'blocked', 'achieved', 'superseded'
]
type GoalStatus = Literal[
  'active', 'pending', 'blocked', 'achieved', 'cancelled'
]
type TaskStatus = Literal[
  'pending', 'active', 'completed', 'blocked', 'cancelled'
]
type BlockerStatus = Literal['open', 'resolved', 'withdrawn']
type BlockerFilterStatus = Literal['open', 'resolved', 'withdrawn', 'all']
type CharterContextStatus = Literal['current', 'legacy-incomplete']
type RecordContextStatus = Literal['complete', 'legacy-unresolved']
type ClaimStatus = Literal['substantive', 'legacy-blank']
type TitleStatus = Literal['substantive', 'legacy-blank']
type FocusKind = Literal['task', 'goal']

GOAL_STATUSES: Final[tuple[GoalStatus, ...]] = (
  'active',
  'pending',
  'blocked',
  'achieved',
  'cancelled',
)
TASK_STATUSES: Final[tuple[TaskStatus, ...]] = (
  'pending',
  'active',
  'completed',
  'blocked',
  'cancelled',
)
BLOCKER_STATUSES: Final[tuple[BlockerStatus, ...]] = (
  'open',
  'resolved',
  'withdrawn',
)

Unset = NewType('Unset', object)
UNSET: Final[Unset] = Unset(object())


class ProjectError(Exception):
  pass


def is_substantive(value: object) -> bool:
  return isinstance(value, str) and bool(value.strip())


def _is_ascii_digits(value: str) -> bool:
  return bool(value) and value.isascii() and value.isdigit()


def _serialize_value(value: object) -> object:
  if isinstance(value, tuple):
    return [_serialize_value(item) for item in value]
  if is_dataclass(value) and not isinstance(value, type):
    return dataclass_to_dict(value)
  return value


def dataclass_to_dict(record: object) -> dict[str, object]:
  if not is_dataclass(record) or isinstance(record, type):
    raise TypeError('dataclass_to_dict requires a dataclass instance')
  return {
    item.name: _serialize_value(getattr(record, item.name))
    for item in fields(record)
  }


@dataclass(frozen=True, slots=True)
class SubstantiveText:
  value: str

  def __post_init__(self) -> None:
    if not isinstance(self.value, str) or not is_substantive(self.value):
      raise ProjectError('Value must contain non-whitespace text')

  @classmethod
  def parse(cls, raw: str, label: str) -> 'SubstantiveText':
    if not isinstance(raw, str) or not is_substantive(raw):
      raise ProjectError(f'{label} must contain non-whitespace text')
    return cls(raw)


@dataclass(frozen=True, slots=True)
class ProjectName:
  value: str

  def __post_init__(self) -> None:
    if (
      not isinstance(self.value, str)
      or not self.value
      or self.value in ('.', '..')
      or self.value.endswith(PROJECT_SUFFIX)
      or _PROJECT_NAME_PATTERN.fullmatch(self.value) is None
      or not self.value.isprintable()
      or len(self.value) > MAX_PROJECT_NAME_LENGTH
    ):
      raise ProjectError(
        'Project names must be printable, non-empty single path '
        f'components of at most {MAX_PROJECT_NAME_LENGTH} characters '
        'without the .sqlite3 suffix.'
      )

  @classmethod
  def parse(cls, raw: str) -> 'ProjectName':
    return cls(raw)


@dataclass(frozen=True, slots=True)
class GoalText:
  value: str

  def __post_init__(self) -> None:
    if not isinstance(self.value, str) or not is_substantive(self.value):
      raise ProjectError(
        'Goal text must contain at least one non-whitespace character'
      )
    if '\x00' in self.value:
      raise ProjectError('Goal text must not contain NUL characters')
    length = len(self.value)
    if length > MAX_GOAL_TEXT_LENGTH:
      raise ProjectError(
        f'Goal text is limited to {MAX_GOAL_TEXT_LENGTH:,} characters; '
        f'received {length:,}.'
      )

  @classmethod
  def parse(cls, raw: str) -> 'GoalText':
    return cls(raw)


@dataclass(frozen=True, slots=True)
class PositiveInt:
  value: int

  def __post_init__(self) -> None:
    if (
      isinstance(self.value, bool)
      or not isinstance(self.value, int)
      or self.value <= 0
    ):
      raise ProjectError('Identifier must be positive')

  @classmethod
  def parse(cls, raw: int, label: str) -> 'PositiveInt':
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
      raise ProjectError(f'{label} must be positive')
    return cls(raw)


@dataclass(frozen=True, slots=True)
class StageName:
  value: str

  def __post_init__(self) -> None:
    if (
      not isinstance(self.value, str)
      or not self.value
      or _is_ascii_digits(self.value)
    ):
      raise ProjectError(f'Invalid stage name: {self.value!r}')


@dataclass(frozen=True, slots=True)
class TaskTag:
  value: str

  def __post_init__(self) -> None:
    if not isinstance(self.value, str) or not self.value.strip():
      raise ProjectError('Task tags cannot be empty')
    if self.value != self.value.strip():
      raise ProjectError('Task tags cannot contain surrounding whitespace')

  @classmethod
  def parse(cls, raw: str) -> 'TaskTag':
    if not isinstance(raw, str):
      raise ProjectError('Task tags cannot be empty')
    return cls(raw.strip())


type StageReference = PositiveInt | StageName
type GoalReference = PositiveInt | Literal['active']


def parse_stage_reference(raw: int | str) -> StageReference:
  if isinstance(raw, int) and not isinstance(raw, bool):
    return PositiveInt.parse(raw, 'Stage ID')
  if isinstance(raw, str):
    if _is_ascii_digits(raw):
      return PositiveInt.parse(int(raw), 'Stage ID')
    if raw:
      return StageName(raw)
    raise ProjectError('Stage reference cannot be empty')
  raise ProjectError(f'Invalid stage reference: {raw!r}')


def parse_goal_reference(raw: int | str) -> GoalReference:
  if raw == 'active':
    return 'active'
  if isinstance(raw, int) and not isinstance(raw, bool):
    return PositiveInt.parse(raw, 'Goal ID')
  if isinstance(raw, str) and _is_ascii_digits(raw):
    return PositiveInt.parse(int(raw), 'Goal ID')
  raise ProjectError(
    f'Goal references must be positive IDs or active: {raw}'
  )


@dataclass(frozen=True, slots=True)
class CharterInput:
  objective: SubstantiveText
  scope: str = ''
  non_goals: str = ''
  constraints_text: str = ''
  acceptance: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.objective, SubstantiveText):
      raise ProjectError(
        'Project objective must contain non-whitespace text'
      )
    for field_value in (
      self.scope,
      self.non_goals,
      self.constraints_text,
      self.acceptance,
    ):
      if not isinstance(field_value, str):
        raise ProjectError('Charter fields must be text')

  @classmethod
  def parse(
    cls,
    objective: str,
    scope: str = '',
    non_goals: str = '',
    constraints: str = '',
    acceptance: str = '',
  ) -> 'CharterInput':
    return cls(
      objective=SubstantiveText.parse(objective, 'Project objective'),
      scope=scope,
      non_goals=non_goals,
      constraints_text=constraints,
      acceptance=acceptance,
    )
