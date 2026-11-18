from __future__ import annotations

import re
import subprocess
from pathlib import Path

import click

from zero.lib import Diagnostic

MAX_LINE = 72
SUBJECT_RE = re.compile(
  r'^(feat|fix|doc|perf|refactor|style|test|chore|ci|revert)'
  r'(\([^()\r\n]+\))?!?: \S.*$'
)


def read_head_message(repo: Path) -> str:
  try:
    proc = subprocess.run(
      ['git', '-C', str(repo), 'log', '-1', '--format=%B', 'HEAD'],
      capture_output=True,
      text=True,
      encoding='utf-8',
      check=True,
    )
  except (OSError, subprocess.CalledProcessError) as err:
    raise click.ClickException(
      f'failed to read HEAD commit message: {err}'
    ) from err
  return proc.stdout


def is_exempt_literal_line(line: str) -> bool:
  if line.startswith('$ '):
    return True
  if bool(line) and not any(c.isspace() for c in line):
    return True
  if (
    len(line) >= 2
    and line.startswith('`')
    and line.endswith('`')
    and '`' not in line[1:-1]
  ):
    return True
  if len(line) >= 2 and line[0] in ('"', "'") and line[-1] == line[0]:
    quote = line[0]
    i = 1
    end = len(line) - 1
    while i < end:
      ch = line[i]
      if ch == '\\':
        if i + 1 == end:
          return False
        i += 2
      elif ch == quote:
        return False
      else:
        i += 1
    return True
  return False


def check_commit_message(message: str) -> list[Diagnostic]:
  lines = message.splitlines()
  while lines and lines[-1] == '':
    lines.pop()
  if not lines:
    return [Diagnostic('COMMIT_EDITMSG', 'commit message is empty', 1)]

  diags: list[Diagnostic] = []
  subject = lines[0]
  if not SUBJECT_RE.match(subject) or subject.endswith('.'):
    diags.append(
      Diagnostic(
        'COMMIT_EDITMSG',
        'subject must match Conventional Commit format '
        'without trailing "."',
        1,
      )
    )
  if len(subject) > MAX_LINE:
    diags.append(
      Diagnostic(
        'COMMIT_EDITMSG',
        f'subject exceeds {MAX_LINE} characters ({len(subject)})',
        1,
      )
    )
  if len(lines) > 1 and lines[1] != '':
    diags.append(
      Diagnostic(
        'COMMIT_EDITMSG',
        'line 2 after commit subject must be blank',
        2,
      )
    )
  for lineno, line in enumerate(lines[2:], start=3):
    if len(line) > MAX_LINE and not is_exempt_literal_line(line):
      diags.append(
        Diagnostic(
          'COMMIT_EDITMSG',
          f'body line exceeds {MAX_LINE} characters ({len(line)})',
          lineno,
        )
      )
  return diags
