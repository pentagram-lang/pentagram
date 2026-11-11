import subprocess
from pathlib import Path

import pytest

from zero import commit_message
from zero.test_support import isolate_git_environment


def _git_repository(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
  isolate_git_environment(monkeypatch, root)
  hooks = root / 'hooks'
  hooks.mkdir()
  subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
  return hooks


def _git_commit(root: Path, hooks: Path, message: str) -> None:
  subprocess.run(
    [
      'git',
      '-c',
      f'core.hooksPath={hooks}',
      '-c',
      'commit.gpgsign=false',
      '-c',
      'user.name=Test',
      '-c',
      'user.email=test@example.invalid',
      'commit',
      '--allow-empty',
      '-F',
      '-',
    ],
    cwd=root,
    input=message,
    check=True,
    capture_output=True,
    text=True,
  )


@pytest.mark.parametrize(
  'line',
  [
    'https://example.invalid/' + 'x' * 80,
    '$ python -m pytest --nodeid ' + 'x' * 80,
    '/tmp/' + 'x' * 80,
    '"' + 'x' * 80 + '"',
    'package.Type:' + 'x' * 80,
  ],
  ids=('url', 'command', 'path', 'quoted', 'identifier'),
)
def test_lint_message_accepts_exact_long_literals(line: str) -> None:
  assert commit_message.lint_message(f'Short subject\n\n{line}') == ()


@pytest.mark.parametrize(
  'message',
  ('fix: shorten the subject', 'wip: keep the change in progress'),
  ids=('short-subject', 'work-in-progress'),
)
def test_lint_message_accepts_short_and_work_in_progress_messages(
  message: str,
) -> None:
  assert commit_message.lint_message(message) == ()


def test_lint_message_reports_long_subject_and_body_lines() -> None:
  diagnostics = commit_message.lint_message(
    's' * 73 + '\n\n' + 'prose ' + 'x' * 67
  )

  assert diagnostics == (
    commit_message.Diagnostic(
      1, 73, 'CM001', 'subject is 73 characters; maximum is 72'
    ),
    commit_message.Diagnostic(
      3,
      73,
      'CM002',
      'body line is 73 characters; maximum is 72',
    ),
  )


def test_lint_message_does_not_allow_a_literal_inside_prose() -> None:
  line = 'A sentence containing https://example.invalid/' + 'x' * 50

  assert commit_message.lint_message(f'Short subject\n\n{line}') == (
    commit_message.Diagnostic(
      3,
      len(line),
      'CM002',
      f'body line is {len(line)} characters; maximum is 72',
    ),
  )


def test_lint_message_rejects_a_long_unqualified_token() -> None:
  token = 'x' * 73

  assert commit_message.lint_message(f'Short subject\n\n{token}') == (
    commit_message.Diagnostic(
      3, 73, 'CM002', 'body line is 73 characters; maximum is 72'
    ),
  )


def test_check_commit_message_raises_with_exact_diagnostics(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  diagnostic = commit_message.Diagnostic(
    1, 73, 'CM001', 'subject is 73 characters; maximum is 72'
  )
  monkeypatch.setattr(
    commit_message, '_read_message', lambda _root: 's' * 73
  )

  with pytest.raises(commit_message.CommitMessageLintError) as error:
    commit_message.check_commit_message('.')

  assert error.value.diagnostics == (diagnostic,)
  assert str(error.value) == (
    'Commit message lint violations:\n'
    '  - commit message line 1: CM001: '
    'subject is 73 characters; maximum is 72'
  )


def test_lint_commit_message_reads_only_the_current_commit(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  long_body = 'prose ' + 'x' * 67
  hooks = _git_repository(tmp_path, monkeypatch)
  _git_commit(tmp_path, hooks, f'Older commit\n\n{long_body}\n')
  _git_commit(tmp_path, hooks, 'Current commit\n')

  assert commit_message.lint_commit_message(tmp_path) == ()


@pytest.mark.parametrize(
  ('message', 'expected'),
  [
    (
      's' * 73 + '\n',
      (
        commit_message.Diagnostic(
          1, 73, 'CM001', 'subject is 73 characters; maximum is 72'
        ),
      ),
    ),
    (
      'Current commit\n\n' + 'prose ' + 'x' * 67 + '\n',
      (
        commit_message.Diagnostic(
          3, 73, 'CM002', 'body line is 73 characters; maximum is 72'
        ),
      ),
    ),
  ],
  ids=('long-subject', 'long-body'),
)
def test_lint_commit_message_reports_diagnostics_from_current_commit(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  message: str,
  expected: tuple[commit_message.Diagnostic, ...],
) -> None:
  hooks = _git_repository(tmp_path, monkeypatch)
  _git_commit(tmp_path, hooks, message)

  assert commit_message.lint_commit_message(tmp_path) == expected
