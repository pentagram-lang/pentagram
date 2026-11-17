"""Pure unit tests for proj.core boundary types and constants."""

import pytest

from proj import core


def test_core_constants_and_status_tuples() -> None:
  assert (
    core.PROJECT_SUFFIX,
    core.MAX_PROJECT_NAME_LENGTH,
    core.MAX_GOAL_TEXT_LENGTH,
    core.HANDOFF_LIMIT,
    core.GOAL_STATUSES,
    core.TASK_STATUSES,
    core.BLOCKER_STATUSES,
  ) == (
    '.sqlite3',
    200,
    4000,
    5,
    ('active', 'pending', 'blocked', 'achieved', 'cancelled'),
    ('pending', 'active', 'completed', 'blocked', 'cancelled'),
    ('open', 'resolved', 'withdrawn'),
  )
  assert core.UNSET is core.UNSET
  assert core.UNSET is not core.Unset(object())


@pytest.mark.parametrize(
  ('value', 'expected'),
  [
    ('', False),
    ('   ', False),
    ('\t\n\r', False),
    ('\u00a0\u2003', False),
    (' a ', True),
    ('None', True),
    (b'abc', False),
    (b'\xc2\xa0', False),
    (123, False),
    (None, False),
  ],
  ids=(
    'empty',
    'spaces',
    'ascii-ws',
    'unicode-ws',
    'trimmed',
    'text',
    'bytes-ascii',
    'bytes-ws',
    'int',
    'none',
  ),
)
def test_is_substantive_handles_ascii_and_unicode_whitespace(
  value: object, expected: bool
) -> None:
  assert core.is_substantive(value) is expected


@pytest.mark.parametrize(
  ('raw', 'label'),
  [
    (' valid ', 'Task title'),
    ('日本語', 'Stage name'),
  ],
  ids=('padded-ascii', 'unicode'),
)
def test_substantive_text_parse_preserves_raw_text(
  raw: str, label: str
) -> None:
  assert core.SubstantiveText.parse(raw, label) == core.SubstantiveText(
    raw
  )


@pytest.mark.parametrize(
  ('raw', 'label'),
  [
    ('', 'Project objective'),
    (' \t\n ', 'Stage outcome'),
    ('\u00a0', 'Evidence claim'),
  ],
  ids=('empty', 'whitespace', 'unicode-ws'),
)
def test_substantive_text_parse_rejects_blank_text(
  raw: str, label: str
) -> None:
  with pytest.raises(core.ProjectError) as exc_info:
    core.SubstantiveText.parse(raw, label)
  assert str(exc_info.value) == f'{label} must contain non-whitespace text'


@pytest.mark.parametrize(
  'raw',
  ['a', 'proj-1', 'n' * core.MAX_PROJECT_NAME_LENGTH, 'proj.db'],
  ids=('single-char', 'hyphenated', 'max-length', 'other-suffix'),
)
def test_project_name_parse_accepts_valid_names(raw: str) -> None:
  assert core.ProjectName.parse(raw) == core.ProjectName(raw)


@pytest.mark.parametrize(
  'raw',
  [
    '',
    '.',
    '..',
    'alpha.sqlite3',
    'dir/name',
    'dir\\name',
    'bad\x00name',
    'bad\nname',
    'x' * (core.MAX_PROJECT_NAME_LENGTH + 1),
  ],
  ids=(
    'empty',
    'dot',
    'dotdot',
    'sqlite3-suffix',
    'slash',
    'backslash',
    'nul-byte',
    'non-printable',
    'too-long',
  ),
)
def test_project_name_parse_rejects_invalid_names(raw: str) -> None:
  with pytest.raises(core.ProjectError) as exc_info:
    core.ProjectName.parse(raw)
  assert str(exc_info.value) == (
    'Project names must be printable, non-empty single path components '
    'of at most 200 characters without the .sqlite3 suffix.'
  )


@pytest.mark.parametrize(
  'raw',
  ['g', '  keep leading/trailing  ', 'x' * core.MAX_GOAL_TEXT_LENGTH],
  ids=('single-char', 'preserved-ws', 'exact-max-length'),
)
def test_goal_text_parse_accepts_valid_text(raw: str) -> None:
  assert core.GoalText.parse(raw) == core.GoalText(raw)


@pytest.mark.parametrize(
  ('raw', 'expected_message'),
  [
    ('', 'Goal text must contain at least one non-whitespace character'),
    (
      ' \u2003\n',
      'Goal text must contain at least one non-whitespace character',
    ),
    (
      'x' * (core.MAX_GOAL_TEXT_LENGTH + 1),
      'Goal text is limited to 4,000 characters; received 4,001.',
    ),
  ],
  ids=('empty', 'whitespace', 'over-limit'),
)
def test_goal_text_parse_rejects_blank_or_over_limit_text(
  raw: str, expected_message: str
) -> None:
  with pytest.raises(core.ProjectError) as exc_info:
    core.GoalText.parse(raw)
  assert str(exc_info.value) == expected_message


@pytest.mark.parametrize(
  'raw',
  [1, 42],
  ids=('one', 'forty-two'),
)
def test_positive_int_parse_accepts_positive_integers(raw: int) -> None:
  assert core.PositiveInt.parse(raw, 'Task ID') == core.PositiveInt(raw)


@pytest.mark.parametrize(
  ('raw', 'label'),
  [
    (0, 'Task ID'),
    (-1, 'Stage ID'),
    (True, 'Goal ID'),
    (False, 'Blocker ID'),
  ],
  ids=('zero', 'negative', 'bool-true', 'bool-false'),
)
def test_positive_int_parse_rejects_non_positive_and_bool(
  raw: int, label: str
) -> None:
  with pytest.raises(core.ProjectError) as exc_info:
    core.PositiveInt.parse(raw, label)
  assert str(exc_info.value) == f'{label} must be positive'


def test_charter_input_parse_builds_default_and_full_charters() -> None:
  minimal = core.CharterInput.parse('Ship v1')
  full = core.CharterInput.parse(
    objective='Ship v1',
    scope='Core runtime',
    non_goals='IDE UI',
    constraints='No disk writes',
    acceptance='Suite passes',
  )
  assert (minimal, full) == (
    core.CharterInput(objective=core.SubstantiveText('Ship v1')),
    core.CharterInput(
      objective=core.SubstantiveText('Ship v1'),
      scope='Core runtime',
      non_goals='IDE UI',
      constraints_text='No disk writes',
      acceptance='Suite passes',
    ),
  )


def test_direct_construction_and_reference_and_tag_parsers() -> None:
  assert (
    core.parse_stage_reference('build'),
    core.parse_stage_reference('10'),
    core.parse_stage_reference(4),
    core.parse_stage_reference('stage-1'),
    core.parse_stage_reference('²'),
    core.parse_stage_reference('\u0661'),
    core.parse_goal_reference('active'),
    core.parse_goal_reference('8'),
    core.parse_goal_reference(3),
    core.StageName('stage-1'),
    core.StageName('²'),
    core.StageName('\u0661'),
    core.TaskTag.parse('  cli  '),
    core.dataclass_to_dict(core.TaskTag('core')),
  ) == (
    core.StageName('build'),
    core.PositiveInt(10),
    core.PositiveInt(4),
    core.StageName('stage-1'),
    core.StageName('²'),
    core.StageName('\u0661'),
    'active',
    core.PositiveInt(8),
    core.PositiveInt(3),
    core.StageName('stage-1'),
    core.StageName('²'),
    core.StageName('\u0661'),
    core.TaskTag('cli'),
    {'value': 'core'},
  )

  rejected: list[str] = []
  for bad_call in (
    lambda: core.SubstantiveText('   '),
    lambda: core.ProjectName('../escape'),
    lambda: core.GoalText(''),
    lambda: core.PositiveInt(0),
    lambda: core.PositiveInt(True),
    lambda: core.StageName(''),
    lambda: core.StageName('42'),
    lambda: core.TaskTag.parse('   '),
    lambda: core.TaskTag(' padded '),
    lambda: core.parse_stage_reference(''),
    lambda: core.parse_stage_reference(0),
    lambda: core.parse_stage_reference(True),
    lambda: core.parse_goal_reference('0'),
    lambda: core.parse_goal_reference('other'),
    lambda: core.parse_goal_reference('\u0661'),
    lambda: core.parse_goal_reference(False),
  ):
    with pytest.raises(core.ProjectError) as exc_info:
      bad_call()
    rejected.append(str(exc_info.value))
  assert rejected == [
    'Value must contain non-whitespace text',
    'Project names must be printable, non-empty single path components '
    'of at most 200 characters without the .sqlite3 suffix.',
    'Goal text must contain at least one non-whitespace character',
    'Identifier must be positive',
    'Identifier must be positive',
    "Invalid stage name: ''",
    "Invalid stage name: '42'",
    'Task tags cannot be empty',
    'Task tags cannot contain surrounding whitespace',
    'Stage reference cannot be empty',
    'Stage ID must be positive',
    'Invalid stage reference: True',
    'Goal ID must be positive',
    'Goal references must be positive IDs or active: other',
    'Goal references must be positive IDs or active: \u0661',
    'Goal references must be positive IDs or active: False',
  ]

  with pytest.raises(TypeError) as non_dc:
    core.dataclass_to_dict(core.TaskTag)
  assert (
    str(non_dc.value) == 'dataclass_to_dict requires a dataclass instance'
  )

  with pytest.raises(core.ProjectError) as exc_info:
    core.CharterInput.parse('   ', scope='Ignored')
  assert (
    str(exc_info.value)
    == 'Project objective must contain non-whitespace text'
  )
