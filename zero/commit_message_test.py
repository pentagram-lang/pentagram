"""Tests for zero.commit_message."""

import os
import subprocess
from pathlib import Path

import pytest

from zero import commit_message


def test_lint_message_accepts_empty_and_72_char_lines() -> None:
  assert commit_message.lint_message('') == ()
  subject = 'a' * 72
  body = 'b' * 72
  assert commit_message.lint_message(f'{subject}\n\n{body}\n') == ()


def test_lint_message_reports_long_subject_and_body_lines() -> None:
  subject = 's' * 73
  body = 'b' * 75
  diagnostics = commit_message.lint_message(f'{subject}\n\n{body}\n')
  assert diagnostics == (
    commit_message.Diagnostic(
      1,
      73,
      'CM001',
      'subject is 73 characters; maximum is 72',
    ),
    commit_message.Diagnostic(
      3,
      75,
      'CM002',
      'body line is 75 characters; maximum is 72',
    ),
  )
  assert str(diagnostics[0]) == (
    'commit message line 1: CM001: subject is 73 characters; maximum is 72'
  )


@pytest.mark.parametrize(
  'literal',
  [
    'https://example.invalid/' + ('x' * 60),
    '$ cargo test --package boot_shell -- --nocapture ' + ('y' * 30),
    '`' + ('c' * 73) + '`',
    "'" + ('q' * 73) + "'",
    '"' + ('d' * 73) + '"',
    './zero/subdir/' + ('module_' * 10) + 'file.py',
    '../parent/' + ('module_' * 10) + 'file.py',
    '/absolute/path/' + ('module_' * 10) + 'file.py',
    '~/home/path/' + ('module_' * 10) + 'file.py',
    '.buildkite/pipelines/' + ('step_' * 12) + 'pipeline.yml',
    '0/command/subcommand/' + ('segment_' * 8) + 'target',
    'Module.nested_identifier_' + ('segment_' * 8) + 'symbol',
  ],
)
def test_lint_message_exempts_exact_body_literals(literal: str) -> None:
  message = f'Short subject\n\n{literal}\n'
  assert commit_message.lint_message(message) == ()


@pytest.mark.parametrize(
  'line',
  [
    ' https://example.invalid/' + ('x' * 60),
    'https://example.invalid/' + ('x' * 60) + ' trailing words',
    'See ' + './zero/' + ('segment_' * 9) + 'file.py',
    '.buildkite/step ' + ('x' * 65),
    '`' + ('c' * 73) + '` with suffix',
    's' * 73,
  ],
)
def test_lint_message_rejects_non_exact_long_body_lines(line: str) -> None:
  diagnostics = commit_message.lint_message(f'Short subject\n\n{line}\n')
  assert diagnostics == (
    commit_message.Diagnostic(
      3,
      len(line),
      'CM002',
      f'body line is {len(line)} characters; maximum is 72',
    ),
  )


def test_read_head_message_wraps_resolve_os_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def fail_resolve(self: Path) -> Path:
    raise OSError('bad cwd')

  monkeypatch.setattr(Path, 'resolve', fail_resolve)

  with pytest.raises(RuntimeError) as error:
    commit_message.read_head_message('.')
  assert str(error.value) == (
    'Cannot read the commit message with git: bad cwd'
  )


def test_read_head_message_wraps_subprocess_and_decode_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def fail_run(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    raise FileNotFoundError('git missing')

  monkeypatch.setattr(subprocess, 'run', fail_run)
  with pytest.raises(RuntimeError) as missing_err:
    commit_message.read_head_message('.')
  assert str(missing_err.value) == (
    'Cannot read the commit message with git: git missing'
  )

  def nonzero_with_stderr(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'],
      128,
      stdout=b'',
      stderr=b'  fatal: bad revision \xff  \n',
    )

  monkeypatch.setattr(subprocess, 'run', nonzero_with_stderr)
  with pytest.raises(RuntimeError) as stderr_err:
    commit_message.read_head_message('.')
  assert str(stderr_err.value) == (
    'Cannot read the commit message with git: fatal: bad revision \ufffd'
  )

  def nonzero_without_stderr(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'], 1, stdout=b'', stderr=b'   \n'
    )

  monkeypatch.setattr(subprocess, 'run', nonzero_without_stderr)
  with pytest.raises(RuntimeError) as empty_err:
    commit_message.read_head_message('.')
  assert str(empty_err.value) == (
    'Cannot read the commit message with git: unknown git error'
  )

  def invalid_utf8_stdout(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'], 0, stdout=b'\xffinvalid', stderr=b''
    )

  monkeypatch.setattr(subprocess, 'run', invalid_utf8_stdout)
  with pytest.raises(RuntimeError) as utf8_err:
    commit_message.read_head_message('.')
  assert str(utf8_err.value) == (
    "Cannot read the commit message with git: 'utf-8' codec can't "
    'decode byte 0xff in position 0: invalid start byte'
  )


def test_check_commit_message_virtualized(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  stdout = b'Valid subject\n\nCaf\xc3\xa9 body\n'

  def fake_run(
    cmd: list[str], **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    assert cmd == ['git', 'show', '-s', '--format=%B', 'HEAD']
    assert kwargs.get('text') is None
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=b'')

  monkeypatch.setattr(subprocess, 'run', fake_run)
  commit_message.check_commit_message('.')

  stdout = ('x' * 73 + '\n\n' + ('y' * 74)).encode('utf-8')
  with pytest.raises(commit_message.CommitMessageLintError) as exc_info:
    commit_message.check_commit_message('.')

  expected_diagnostics = (
    commit_message.Diagnostic(
      1, 73, 'CM001', 'subject is 73 characters; maximum is 72'
    ),
    commit_message.Diagnostic(
      3, 74, 'CM002', 'body line is 74 characters; maximum is 72'
    ),
  )
  assert exc_info.value.diagnostics == expected_diagnostics
  assert str(exc_info.value) == (
    'Commit message lint violations:\n'
    '  - commit message line 1: CM001: subject is 73 characters; '
    'maximum is 72\n'
    '  - commit message line 3: CM002: body line is 74 characters; '
    'maximum is 72'
  )


def test_git_cli_reads_head_utf8_under_c_locale(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def git(*args: str) -> None:
    subprocess.run(
      [
        'git',
        '-C',
        str(tmp_path),
        '-c',
        'user.name=Test',
        '-c',
        'user.email=test@example.invalid',
        '-c',
        'commit.gpgsign=false',
        *args,
      ],
      check=True,
      capture_output=True,
      text=True,
    )

  with monkeypatch.context() as env:
    for key in list(os.environ):
      if key.startswith('GIT_'):
        env.delenv(key, raising=False)
    env.setenv('HOME', str(tmp_path))
    env.setenv('XDG_CONFIG_HOME', str(tmp_path))
    env.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
    env.setenv('GIT_CONFIG_NOSYSTEM', '1')
    env.setenv('LC_ALL', 'C')

    git('init', '-q')
    git('commit', '--allow-empty', '-m', 'x' * 73)
    with pytest.raises(commit_message.CommitMessageLintError) as exc_info:
      commit_message.check_commit_message(tmp_path)
    assert exc_info.value.diagnostics == (
      commit_message.Diagnostic(
        1, 73, 'CM001', 'subject is 73 characters; maximum is 72'
      ),
    )

    git('commit', '--allow-empty', '-m', 'Café HEAD subject')
    assert (
      commit_message.read_head_message(tmp_path).strip()
      == 'Café HEAD subject'
    )
    commit_message.check_commit_message(tmp_path)
