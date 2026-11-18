from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from zero.lib import Diagnostic, git_ls_files

BANNED_BASENAMES = frozenset(
  {
    'AGENTS.md',
    'AGENTS.override.md',
    'CLAUDE.md',
    'CLAUDE.local.md',
    'GEMINI.md',
  }
)
BANNED_DIRS = frozenset({'.agents', '.claude', '.codex', '.gemini'})


def _non_test_sibling(name: str) -> tuple[str, str] | None:
  parts = name.split('.')
  if len(parts) != 2:
    return None
  stem, ext = parts
  if (
    not stem or not ext or 'test' in stem.lower() or 'test' in ext.lower()
  ):
    return None
  return stem, ext


def _test_companion_stem(name: str) -> str | None:
  parts = name.split('.')
  if len(parts) == 2:
    base, ext = parts
    if not base.endswith('_test') or not ext or 'test' in ext.lower():
      return None
    stem = base[:-5]
    return stem if stem and 'test' not in stem.lower() else None
  if len(parts) == 3:
    stem, marker, ext = parts
    if (
      marker != 'test'
      or not stem
      or not ext
      or 'test' in stem.lower()
      or 'test' in ext.lower()
    ):
      return None
    return stem
  return None


def check_repo_paths(paths: Sequence[str]) -> list[Diagnostic]:
  dir_stems: dict[tuple[str, ...], set[str]] = defaultdict(set)
  for rel in paths:
    parts = PurePosixPath(rel).parts
    if not parts:
      continue
    sib = _non_test_sibling(parts[-1])
    if sib is not None:
      dir_stems[parts[:-1]].add(sib[0])

  diags: list[Diagnostic] = []
  for rel in paths:
    parts = PurePosixPath(rel).parts
    if not parts:
      continue
    dirs, name = parts[:-1], parts[-1]
    for d in dirs:
      if d in BANNED_DIRS:
        diags.append(Diagnostic(rel, f'prohibited agent directory {d!r}'))
      elif 'test' in d.lower():
        diags.append(
          Diagnostic(
            rel,
            f'prohibited test directory {d!r}; use tst for test subjects',
          )
        )
    if name in BANNED_BASENAMES:
      diags.append(
        Diagnostic(rel, f'prohibited agent instruction file {name!r}')
      )
    if 'test' in name.lower():
      stem = _test_companion_stem(name)
      if stem is None:
        diags.append(
          Diagnostic(
            rel,
            f'invalid test filename {name!r}; '
            'expected <stem>_test.<ext> or <stem>.test.<ext>',
          )
        )
      elif stem not in dir_stems.get(dirs, set()):
        diags.append(
          Diagnostic(
            rel,
            f'test companion {name!r} lacks non-test sibling {stem}.<ext>',
          )
        )
  return diags


def check_repo_policy(repo: Path) -> list[Diagnostic]:
  paths = [
    rel for rel in git_ls_files(repo) if os.path.lexists(repo / rel)
  ]
  return check_repo_paths(paths)
