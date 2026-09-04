import subprocess
from pathlib import Path

BANNED_FILE_NAMES = frozenset(
  {
    'AGENTS.md',
    'AGENTS.override.md',
    'CLAUDE.md',
    'CLAUDE.local.md',
    'GEMINI.md',
  }
)

BANNED_DIRECTORY_NAMES = frozenset(
  {'.agents', '.claude', '.codex', '.gemini'}
)


class RepositoryPolicyError(RuntimeError):
  """The repository contains a prohibited ambient agent surface."""


def _repository_files(repository_root):
  try:
    result = subprocess.run(
      [
        'git',
        'ls-files',
        '--cached',
        '--others',
        '--exclude-standard',
        '-z',
      ],
      cwd=repository_root,
      capture_output=True,
      check=False,
      text=True,
    )
  except OSError as error:
    raise RepositoryPolicyError(
      f'Cannot scan repository with git: {error}'
    ) from error

  if result.returncode != 0:
    detail = result.stderr.strip() or 'unknown git error'
    raise RepositoryPolicyError(
      f'Cannot scan repository with git: {detail}'
    )

  return [Path(path) for path in result.stdout.split('\0') if path]


def _violation(path):
  if path.name in BANNED_FILE_NAMES:
    return f"banned file name '{path.name}'"

  for directory in path.parts:
    if directory in BANNED_DIRECTORY_NAMES:
      return f"banned directory name '{directory}'"

  return None


def check_repository_policy(repository_root):
  """Reject non-ignored ambient agent files and directories."""
  root = Path(repository_root).resolve()
  violations = []
  for path in _repository_files(root):
    reason = _violation(path)
    if reason:
      violations.append((path, reason))

  if not violations:
    return

  details = '\n'.join(
    f'  - {path}: {reason}' for path, reason in violations
  )
  raise RepositoryPolicyError(
    'Repository policy violations found:\n' + details
  )
