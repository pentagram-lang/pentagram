from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from zero.lib import Diagnostic
from zero.repo_policy import check_repo_paths, check_repo_policy


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='zero-policy-test-', dir='/dev/shm'))
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def test_valid_repo_paths() -> None:
  paths = [
    'README.md',
    'boot/lex/src/lex.rs',
    'boot/lex/src/lex_test.rs',
    'boot/tst/src/tst.rs',
    'boot/tst/src/tst_test.rs',
    'core/math.penta',
    'core/math.test.penta',
    'doc/README.md',
    'doc/README.test.md',
    'skills/SKILL.md',
  ]
  assert check_repo_paths(paths) == []


def test_banned_names_and_dirs() -> None:
  paths = [
    'AGENTS.md',
    'sub/AGENTS.override.md',
    'CLAUDE.md',
    'nested/CLAUDE.local.md',
    'GEMINI.md',
    '.agents/foo.md',
    'a/.claude/settings.json',
    '.codex/config.toml',
    'x/.gemini/rules.md',
  ]
  assert check_repo_paths(paths) == [
    Diagnostic(
      'AGENTS.md', "prohibited agent instruction file 'AGENTS.md'"
    ),
    Diagnostic(
      'sub/AGENTS.override.md',
      "prohibited agent instruction file 'AGENTS.override.md'",
    ),
    Diagnostic(
      'CLAUDE.md', "prohibited agent instruction file 'CLAUDE.md'"
    ),
    Diagnostic(
      'nested/CLAUDE.local.md',
      "prohibited agent instruction file 'CLAUDE.local.md'",
    ),
    Diagnostic(
      'GEMINI.md', "prohibited agent instruction file 'GEMINI.md'"
    ),
    Diagnostic('.agents/foo.md', "prohibited agent directory '.agents'"),
    Diagnostic(
      'a/.claude/settings.json', "prohibited agent directory '.claude'"
    ),
    Diagnostic(
      '.codex/config.toml', "prohibited agent directory '.codex'"
    ),
    Diagnostic(
      'x/.gemini/rules.md', "prohibited agent directory '.gemini'"
    ),
  ]


def test_test_path_rules() -> None:
  paths = [
    'tests/helper.py',
    'sub/test_dir/a.rs',
    'pkg/foo.py',
    'pkg/test_foo.py',
    'pkg/foo_test_extra.py',
    'pkg/foo.bar.test.md',
    'pkg/test_test.py',
    'pkg/foo.Test.md',
    'pkg/foo_test.test',
    'pkg/orphan_test.py',
    'other/foo_test.py',
  ]
  assert check_repo_paths(paths) == [
    Diagnostic(
      'tests/helper.py',
      "prohibited test directory 'tests'; use tst for test subjects",
    ),
    Diagnostic(
      'sub/test_dir/a.rs',
      "prohibited test directory 'test_dir'; use tst for test subjects",
    ),
    Diagnostic(
      'pkg/test_foo.py',
      "invalid test filename 'test_foo.py'; "
      'expected <stem>_test.<ext> or <stem>.test.<ext>',
    ),
    Diagnostic(
      'pkg/foo_test_extra.py',
      "invalid test filename 'foo_test_extra.py'; "
      'expected <stem>_test.<ext> or <stem>.test.<ext>',
    ),
    Diagnostic(
      'pkg/foo.bar.test.md',
      "invalid test filename 'foo.bar.test.md'; "
      'expected <stem>_test.<ext> or <stem>.test.<ext>',
    ),
    Diagnostic(
      'pkg/test_test.py',
      "invalid test filename 'test_test.py'; "
      'expected <stem>_test.<ext> or <stem>.test.<ext>',
    ),
    Diagnostic(
      'pkg/foo.Test.md',
      "invalid test filename 'foo.Test.md'; "
      'expected <stem>_test.<ext> or <stem>.test.<ext>',
    ),
    Diagnostic(
      'pkg/foo_test.test',
      "invalid test filename 'foo_test.test'; "
      'expected <stem>_test.<ext> or <stem>.test.<ext>',
    ),
    Diagnostic(
      'pkg/orphan_test.py',
      "test companion 'orphan_test.py' lacks "
      'non-test sibling orphan.<ext>',
    ),
    Diagnostic(
      'other/foo_test.py',
      "test companion 'foo_test.py' lacks non-test sibling foo.<ext>",
    ),
  ]


def test_check_repo_policy_skips_deleted_and_catches_broken_symlink(
  shm_dir: Path,
) -> None:
  subprocess.run(['git', 'init', '-q', str(shm_dir)], check=True)
  (shm_dir / 'CLAUDE.md').write_text('deleted', encoding='utf-8')
  (shm_dir / 'ok.py').write_text('', encoding='utf-8')
  subprocess.run(
    ['git', '-C', str(shm_dir), 'add', 'CLAUDE.md', 'ok.py'], check=True
  )
  (shm_dir / 'CLAUDE.md').unlink()
  (shm_dir / 'AGENTS.md').symlink_to('missing-target')

  assert check_repo_policy(shm_dir) == [
    Diagnostic(
      'AGENTS.md', "prohibited agent instruction file 'AGENTS.md'"
    )
  ]
