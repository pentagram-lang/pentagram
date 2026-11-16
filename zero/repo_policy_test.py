"""Tests for zero.repo_policy."""

import os
import subprocess
from pathlib import Path

import pytest

from zero import repo_policy


@pytest.mark.parametrize('name', sorted(repo_policy.BANNED_FILE_NAMES))
def test_path_violation_rejects_banned_file_names(name: str) -> None:
  assert (
    repo_policy.path_violation(Path(name)) == f"banned file name '{name}'"
  )
  assert (
    repo_policy.path_violation(Path('nested/dir') / name)
    == f"banned file name '{name}'"
  )


@pytest.mark.parametrize(
  'directory',
  sorted(repo_policy.BANNED_DIRECTORY_NAMES),
)
def test_path_violation_rejects_banned_directories(directory: str) -> None:
  assert (
    repo_policy.path_violation(Path(directory) / 'settings.json')
    == f"banned directory name '{directory}'"
  )
  assert (
    repo_policy.path_violation(Path('pkg') / directory / 'note.md')
    == f"banned directory name '{directory}'"
  )
  assert (
    repo_policy.path_violation(Path('linked') / directory)
    == f"banned directory name '{directory}'"
  )


def test_path_violation_allows_permitted_paths() -> None:
  assert repo_policy.path_violation(Path('README.md')) is None
  assert repo_policy.path_violation(Path('docs/AGENTS.txt')) is None
  assert repo_policy.path_violation(Path('.claude-notes/todo.md')) is None


def test_evaluate_repository_policy_deduplicates_and_sorts() -> None:
  paths = [
    Path('README.md'),
    Path('z/CLAUDE.md'),
    Path('z/CLAUDE.md'),
    Path('.gemini/settings.json'),
    Path('a/AGENTS.md'),
    Path('a/AGENTS.md'),
  ]
  assert repo_policy.evaluate_repository_policy(paths) == (
    repo_policy.PolicyViolation(
      Path('.gemini/settings.json'),
      "banned directory name '.gemini'",
    ),
    repo_policy.PolicyViolation(
      Path('a/AGENTS.md'),
      "banned file name 'AGENTS.md'",
    ),
    repo_policy.PolicyViolation(
      Path('z/CLAUDE.md'),
      "banned file name 'CLAUDE.md'",
    ),
  )
  assert repo_policy.evaluate_repository_policy([Path('README.md')]) == ()


def test_repository_files_wraps_resolve_os_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def fail_resolve(self: Path) -> Path:
    raise OSError('unresolvable root')

  monkeypatch.setattr(Path, 'resolve', fail_resolve)

  with pytest.raises(repo_policy.RepositoryPolicyError) as error:
    repo_policy.repository_files('.')
  assert str(error.value) == (
    'Cannot scan repository with git: unresolvable root'
  )


def test_repository_files_wraps_subprocess_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def fail_run(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    raise FileNotFoundError('git missing')

  monkeypatch.setattr(subprocess, 'run', fail_run)
  with pytest.raises(repo_policy.RepositoryPolicyError) as missing_err:
    repo_policy.repository_files('.')
  assert str(missing_err.value) == (
    'Cannot scan repository with git: git missing'
  )

  def nonzero_with_stderr(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'],
      128,
      stdout=b'',
      stderr=b'  fatal: not a git repository  \n',
    )

  monkeypatch.setattr(subprocess, 'run', nonzero_with_stderr)
  with pytest.raises(repo_policy.RepositoryPolicyError) as stderr_err:
    repo_policy.repository_files('.')
  assert str(stderr_err.value) == (
    'Cannot scan repository with git: fatal: not a git repository'
  )

  def nonzero_without_stderr(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'], 1, stdout=b'', stderr=b' \n'
    )

  monkeypatch.setattr(subprocess, 'run', nonzero_without_stderr)
  with pytest.raises(repo_policy.RepositoryPolicyError) as empty_err:
    repo_policy.repository_files('.')
  assert str(empty_err.value) == (
    'Cannot scan repository with git: unknown git error'
  )


def test_check_repository_policy_virtualized(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  stdout = b'README.md\0zero/cli.py\0'
  expected_root = str(Path('.').resolve())

  def fake_run(
    cmd: list[str], **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    assert cmd == [
      'git',
      '-C',
      expected_root,
      'ls-files',
      '--cached',
      '--others',
      '--exclude-standard',
      '-z',
    ]
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr=b'')

  monkeypatch.setattr(subprocess, 'run', fake_run)
  repo_policy.check_repository_policy('.')

  stdout = (
    b'README.md\0.codex/config.toml\0.codex/config.toml\0docs/GEMINI.md\0'
  )
  with pytest.raises(repo_policy.RepositoryPolicyError) as exc_info:
    repo_policy.check_repository_policy('.')

  assert str(exc_info.value) == (
    'Repository policy violations found:\n'
    "  - .codex/config.toml: banned directory name '.codex'\n"
    "  - docs/GEMINI.md: banned file name 'GEMINI.md'"
  )


def test_git_cli_gitignore_ignore_files_forced_tracked_and_symlinks(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def git(*args: str) -> None:
    subprocess.run(
      ['git', '-C', str(tmp_path), *args],
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

    git('init', '-q')

    (tmp_path / '.gitignore').write_text(
      '.claude/\nignored-dir/\nCLAUDE.local.md\n',
      encoding='utf-8',
    )
    (tmp_path / '.ignore').write_text('AGENTS.md\n', encoding='utf-8')
    (tmp_path / '.rgignore').write_text('GEMINI.md\n', encoding='utf-8')
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'settings.json').write_text(
      '{}', encoding='utf-8'
    )
    (tmp_path / 'ignored-dir').mkdir()
    (tmp_path / 'ignored-dir' / 'CLAUDE.md').write_text(
      'x', encoding='utf-8'
    )
    (tmp_path / 'CLAUDE.local.md').write_text('local', encoding='utf-8')
    (tmp_path / 'README.md').write_text('# Repo\n', encoding='utf-8')
    repo_policy.check_repository_policy(tmp_path)

    (tmp_path / 'AGENTS.md').write_text('not gitignored', encoding='utf-8')
    (tmp_path / 'GEMINI.md').write_text('not gitignored', encoding='utf-8')
    (tmp_path / 'CLAUDE.md').symlink_to(tmp_path / 'README.md')
    (tmp_path / 'linked').mkdir()
    (tmp_path / 'linked' / '.agents').symlink_to(tmp_path / 'README.md')
    git('add', '-f', 'CLAUDE.local.md')

    with pytest.raises(repo_policy.RepositoryPolicyError) as exc_info:
      repo_policy.check_repository_policy(tmp_path)

    assert str(exc_info.value) == (
      'Repository policy violations found:\n'
      "  - AGENTS.md: banned file name 'AGENTS.md'\n"
      "  - CLAUDE.local.md: banned file name 'CLAUDE.local.md'\n"
      "  - CLAUDE.md: banned file name 'CLAUDE.md'\n"
      "  - GEMINI.md: banned file name 'GEMINI.md'\n"
      "  - linked/.agents: banned directory name '.agents'"
    )
