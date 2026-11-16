from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from zero.lib import git_ls_files

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


@dataclass(frozen=True, slots=True, order=True)
class PolicyViolation:
  """One repository policy violation at a relative path."""

  path: Path
  reason: str


def repository_files(repository_root: str | Path) -> tuple[Path, ...]:
  """List tracked and non-ignored files in a Git repository."""
  try:
    root = Path(repository_root).resolve()
  except OSError as error:
    raise RepositoryPolicyError(
      f'Cannot scan repository with git: {error}'
    ) from error
  try:
    return git_ls_files(
      root, error_prefix='Cannot scan repository with git'
    )
  except RuntimeError as error:
    raise RepositoryPolicyError(str(error)) from error


def path_violation(path: Path) -> str | None:
  """Return the policy violation reason for a path, or None if allowed."""
  if path.name in BANNED_FILE_NAMES:
    return f"banned file name '{path.name}'"

  for directory in path.parts:
    if directory in BANNED_DIRECTORY_NAMES:
      return f"banned directory name '{directory}'"

  return None


def evaluate_repository_policy(
  paths: Iterable[Path],
) -> tuple[PolicyViolation, ...]:
  """Evaluate repository policy across unique relative paths."""
  violations: list[PolicyViolation] = []
  for path in dict.fromkeys(paths):
    reason = path_violation(path)
    if reason is not None:
      violations.append(PolicyViolation(path, reason))
  return tuple(sorted(violations))


def check_repository_policy(repository_root: str | Path) -> None:
  """Reject non-ignored ambient agent files and directories."""
  violations = evaluate_repository_policy(
    repository_files(repository_root)
  )

  if not violations:
    return

  details = '\n'.join(
    f'  - {violation.path}: {violation.reason}' for violation in violations
  )
  raise RepositoryPolicyError(
    'Repository policy violations found:\n' + details
  )
