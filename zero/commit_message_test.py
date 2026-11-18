from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import click
import pytest

from zero.commit_message import (
  check_commit_message,
  is_exempt_literal_line,
  read_head_message,
)
from zero.lib import Diagnostic


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='zero-cm-test-', dir='/dev/shm'))
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def test_valid_commit_messages() -> None:
  types = (
    'feat',
    'fix',
    'doc',
    'perf',
    'refactor',
    'style',
    'test',
    'chore',
    'ci',
    'revert',
  )
  for kind in types:
    assert check_commit_message(f'{kind}: add thing') == []
    assert check_commit_message(f'{kind}(zero)!: add thing') == []

  valid = (
    'feat(zero): implement commit message check\n'
    '\n'
    'Short wrapped prose line.\n'
    '$ nix shell .#default -c pytest -W error zero proj --verbose --flag\n'
    'https://example.com/very/long/url/that/exceeds/seventy-two/characters/here\n'
    'http://example.com/' + 'x/' * 30 + 'here\n'
    'zero/very/long/token/' + 'path/' * 12 + 'end\n'
    '`' + 'backtick literal ' * 5 + 'end`\n'
    '"' + 'double \\"quoted\\" ' * 5 + 'end"\n'
    "'" + "single \\'quoted\\' " * 5 + "end'\n"
    '\n\n'
  )
  assert check_commit_message(valid) == []
  assert check_commit_message('feat: ' + 'x' * 66) == []


def test_invalid_commit_messages() -> None:
  assert check_commit_message('') == [
    Diagnostic('COMMIT_EDITMSG', 'commit message is empty', 1)
  ]
  assert check_commit_message('\n\n') == [
    Diagnostic('COMMIT_EDITMSG', 'commit message is empty', 1)
  ]

  bad_subject = 'build: wrong type and ends with period.'
  assert check_commit_message(bad_subject) == [
    Diagnostic(
      'COMMIT_EDITMSG',
      'subject must match Conventional Commit format without trailing "."',
      1,
    )
  ]
  assert check_commit_message('feat(a(b)): nested scope') == [
    Diagnostic(
      'COMMIT_EDITMSG',
      'subject must match Conventional Commit format without trailing "."',
      1,
    )
  ]
  assert check_commit_message('feat:x') == [
    Diagnostic(
      'COMMIT_EDITMSG',
      'subject must match Conventional Commit format without trailing "."',
      1,
    )
  ]

  long_sub = 'feat: ' + 'a' * 67
  assert check_commit_message(long_sub) == [
    Diagnostic('COMMIT_EDITMSG', 'subject exceeds 72 characters (73)', 1)
  ]

  msg = (
    'feat: valid subject\n'
    'missing blank line\n'
    + 'x ' * 40
    + '\n'
    + 'See https://example.com/'
    + 'x/' * 26
    + 'here\n'
    + '`bad ` inner backtick '
    + 'x' * 60
    + '`\n'
    + '"bad " inner quote '
    + 'x' * 60
    + '"\n'
    + '"escaped closing quote '
    + 'x' * 60
    + '\\"\n'
  )
  assert check_commit_message(msg) == [
    Diagnostic(
      'COMMIT_EDITMSG', 'line 2 after commit subject must be blank', 2
    ),
    Diagnostic(
      'COMMIT_EDITMSG', 'body line exceeds 72 characters (80)', 3
    ),
    Diagnostic(
      'COMMIT_EDITMSG', 'body line exceeds 72 characters (80)', 4
    ),
    Diagnostic(
      'COMMIT_EDITMSG', 'body line exceeds 72 characters (83)', 5
    ),
    Diagnostic(
      'COMMIT_EDITMSG', 'body line exceeds 72 characters (80)', 6
    ),
    Diagnostic(
      'COMMIT_EDITMSG', 'body line exceeds 72 characters (85)', 7
    ),
  ]


def test_is_exempt_literal_line_boundaries() -> None:
  assert is_exempt_literal_line('``') is True
  assert is_exempt_literal_line('""') is True
  assert is_exempt_literal_line("''") is True
  assert is_exempt_literal_line('"ok \\\\"') is True
  assert is_exempt_literal_line('"bad \\"') is False
  assert is_exempt_literal_line('$foo bar') is False


def test_read_head_message(shm_dir: Path) -> None:
  subprocess.run(['git', 'init', '-q', str(shm_dir)], check=True)
  with pytest.raises(
    click.ClickException, match='failed to read HEAD commit message'
  ):
    read_head_message(shm_dir)
  subprocess.run(
    ['git', '-C', str(shm_dir), 'config', 'user.name', 'Test'],
    check=True,
  )
  subprocess.run(
    [
      'git',
      '-C',
      str(shm_dir),
      'config',
      'user.email',
      'test@example.com',
    ],
    check=True,
  )
  subprocess.run(
    [
      'git',
      '-C',
      str(shm_dir),
      'commit',
      '--allow-empty',
      '-q',
      '-m',
      'feat: initial commit',
      '-m',
      'Body prose.',
    ],
    check=True,
  )
  msg = read_head_message(shm_dir)
  assert msg == 'feat: initial commit\n\nBody prose.\n\n'
  assert check_commit_message(msg) == []
