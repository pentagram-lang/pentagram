import os
import subprocess
from pathlib import Path

import pytest

from zero import repo_policy
from zero.test_support import isolate_git_environment


def _git(root: Path, *arguments: str) -> None:
  subprocess.run(
    ['git', *arguments],
    cwd=root,
    check=True,
    capture_output=True,
    text=True,
  )


def test_repository_inventory_preserves_non_utf8_filenames(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  isolate_git_environment(monkeypatch, tmp_path)
  _git(tmp_path, 'init', '-q')
  name = os.fsdecode(b'non-utf8-\xff.txt')
  (tmp_path / name).write_text('content\n', encoding='utf-8')

  assert repo_policy._repository_files(tmp_path) == [Path(name)]


@pytest.mark.parametrize(
  ('path', 'expected'),
  [
    ('AGENTS.md', "banned file name 'AGENTS.md'"),
    ('folder/AGENTS.override.md', "banned file name 'AGENTS.override.md'"),
    ('CLAUDE.md', "banned file name 'CLAUDE.md'"),
    ('CLAUDE.local.md', "banned file name 'CLAUDE.local.md'"),
    ('GEMINI.md', "banned file name 'GEMINI.md'"),
    ('folder/.agents/agent.md', "banned directory name '.agents'"),
    ('folder/.claude/rules.md', "banned directory name '.claude'"),
    ('folder/.codex/skill.md', "banned directory name '.codex'"),
    ('folder/.gemini/config.md', "banned directory name '.gemini'"),
  ],
  ids=(
    'agents',
    'agents-override',
    'claude',
    'claude-local',
    'gemini',
    'agents-directory',
    'claude-directory',
    'codex-directory',
    'gemini-directory',
  ),
)
def test_violation_reports_prohibited_file_and_directory_names(
  path: str, expected: str
) -> None:
  assert repo_policy._violation(Path(path)) == expected


@pytest.mark.parametrize(
  'path',
  [
    'agents/rules/AGENT.md',
    'skills/README.md',
    'rules/GEMINI.txt',
    'docs/SKILL.md',
  ],
  ids=('agent-file', 'skill-directory', 'rules-directory', 'skill-file'),
)
def test_violation_allows_generic_names(path: str) -> None:
  assert repo_policy._violation(Path(path)) is None


def test_policy_uses_git_ignore_rules_and_scans_other_hidden_paths(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  isolate_git_environment(monkeypatch, tmp_path)
  (tmp_path / '.gitignore').write_text(
    'ignored.md\nignored/\n', encoding='utf-8'
  )
  (tmp_path / '.ignore').write_text(
    'ignored-by-ripgrep.md\n', encoding='utf-8'
  )
  (tmp_path / '.rgignore').write_text(
    'ignored-by-rgignore.md\n', encoding='utf-8'
  )
  for name in (
    'ignored.md',
    'ignored-by-ripgrep.md',
    'ignored-by-rgignore.md',
    'agents/rules/SKILL.md',
  ):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('content\n', encoding='utf-8')
  _git(tmp_path, 'init', '-q')

  files = set(repo_policy._repository_files(tmp_path))

  assert files == {
    Path('.gitignore'),
    Path('.ignore'),
    Path('.rgignore'),
    Path('ignored-by-ripgrep.md'),
    Path('ignored-by-rgignore.md'),
    Path('agents/rules/SKILL.md'),
  }
  assert all('.git' not in path.parts for path in files)
  assert repo_policy.check_repository_policy(tmp_path) is None

  banned = tmp_path / 'ignored' / 'AGENTS.md'
  banned.parent.mkdir()
  banned.write_text('content\n', encoding='utf-8')
  _git(tmp_path, 'add', '-f', 'ignored/AGENTS.md')

  with pytest.raises(repo_policy.RepositoryPolicyError) as error:
    repo_policy.check_repository_policy(tmp_path)

  assert str(error.value) == (
    'Repository policy violations found:\n'
    "  - ignored/AGENTS.md: banned file name 'AGENTS.md'"
  )


def test_policy_rejects_a_prohibited_symlink_path_component(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  isolate_git_environment(monkeypatch, tmp_path)
  target = tmp_path / 'target'
  target.mkdir()
  link = tmp_path / 'linked' / '.agents'
  link.parent.mkdir()
  link.symlink_to(target, target_is_directory=True)
  _git(tmp_path, 'init', '-q')

  with pytest.raises(repo_policy.RepositoryPolicyError) as error:
    repo_policy.check_repository_policy(tmp_path)

  assert str(error.value) == (
    'Repository policy violations found:\n'
    "  - linked/.agents: banned directory name '.agents'"
  )
