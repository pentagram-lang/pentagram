from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

MAX_LINE_LENGTH = 72

_COMMAND = re.compile(r'^\$ \S(?:.*\S)?$')
_QUOTED = re.compile(r"^(?:`[^`\r\n]+`|'[^'\r\n]+'|\"[^\"\r\n]+\")$")
_URI = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*://\S+$')
_PATH = re.compile(
  r'^(?:~?/|\.{1,2}/)[A-Za-z0-9_./:@%+=~-]+$'
  r'|^[A-Za-z0-9_.][A-Za-z0-9_.:@%+=~-]*/[A-Za-z0-9_./:@%+=~-]+$'
)
_IDENTIFIER = re.compile(
  r'^[A-Za-z_][A-Za-z0-9_]*[./:@%+=~-][A-Za-z0-9_./:@%+=~-]*$'
)


@dataclass(frozen=True, slots=True, order=True)
class Diagnostic:
  line: int
  length: int
  code: str
  message: str

  def __str__(self) -> str:
    return f'commit message line {self.line}: {self.code}: {self.message}'


class CommitMessageLintError(RuntimeError):
  def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
    self.diagnostics = tuple(diagnostics)
    details = '\n'.join(
      f'  - {diagnostic}' for diagnostic in self.diagnostics
    )
    super().__init__('Commit message lint violations:\n' + details)


def read_head_message(repository_root: str | Path) -> str:
  """Read the HEAD commit message body from Git."""
  try:
    root = Path(repository_root).resolve()
    result = subprocess.run(
      ['git', 'show', '-s', '--format=%B', 'HEAD'],
      cwd=root,
      capture_output=True,
      check=False,
    )
  except OSError as error:
    raise RuntimeError(
      f'Cannot read the commit message with git: {error}'
    ) from error

  if result.returncode != 0:
    detail = (
      result.stderr.decode(encoding='utf-8', errors='replace').strip()
      or 'unknown git error'
    )
    raise RuntimeError(
      f'Cannot read the commit message with git: {detail}'
    )

  try:
    return result.stdout.decode(encoding='utf-8')
  except UnicodeDecodeError as error:
    raise RuntimeError(
      f'Cannot read the commit message with git: {error}'
    ) from error


def _is_exact_literal(line: str) -> bool:
  if line != line.strip():
    return False
  if _URI.fullmatch(line) or _COMMAND.fullmatch(line):
    return True
  if _QUOTED.fullmatch(line):
    return True
  return bool(_PATH.fullmatch(line) or _IDENTIFIER.fullmatch(line))


def lint_message(message: str) -> tuple[Diagnostic, ...]:
  """Lint a commit message against line-length and literal rules."""
  lines = message.splitlines()
  diagnostics = []
  if lines and len(lines[0]) > MAX_LINE_LENGTH:
    diagnostics.append(
      Diagnostic(
        1,
        len(lines[0]),
        'CM001',
        (
          f'subject is {len(lines[0])} characters; maximum is '
          f'{MAX_LINE_LENGTH}'
        ),
      )
    )
  for line_number, line in enumerate(lines[1:], 2):
    if len(line) <= MAX_LINE_LENGTH or _is_exact_literal(line):
      continue
    diagnostics.append(
      Diagnostic(
        line_number,
        len(line),
        'CM002',
        f'body line is {len(line)} characters; maximum is '
        f'{MAX_LINE_LENGTH}',
      )
    )
  return tuple(sorted(diagnostics))


def lint_commit_message(
  repository_root: str | Path,
) -> tuple[Diagnostic, ...]:
  """Read and lint the HEAD commit message."""
  message = read_head_message(repository_root)
  return lint_message(message)


def check_commit_message(repository_root: str | Path) -> None:
  """Raise CommitMessageLintError if HEAD commit message has violations."""
  diagnostics = lint_commit_message(repository_root)
  if diagnostics:
    raise CommitMessageLintError(diagnostics)
