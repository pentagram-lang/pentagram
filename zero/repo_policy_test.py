import subprocess
import tempfile
import unittest
from pathlib import Path

from zero.repo_policy import (
  BANNED_DIRECTORY_NAMES,
  BANNED_FILE_NAMES,
  RepositoryPolicyError,
  check_repository_policy,
)


class RepositoryPolicyTest(unittest.TestCase):
  def setUp(self):
    self.directory = tempfile.TemporaryDirectory()
    self.root = Path(self.directory.name)
    subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)

  def tearDown(self):
    self.directory.cleanup()

  def write(self, relative_path, content='content'):
    path = self.root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

  def assertRejected(self):
    with self.assertRaises(RepositoryPolicyError):
      check_repository_policy(self.root)

  def test_rejects_each_banned_file_name(self):
    for file_name in BANNED_FILE_NAMES:
      with self.subTest(file_name=file_name):
        self.write(file_name)
        self.assertRejected()
        (self.root / file_name).unlink()

  def test_rejects_each_banned_directory_name(self):
    for directory_name in BANNED_DIRECTORY_NAMES:
      with self.subTest(directory_name=directory_name):
        self.write(
          Path('nested')
          / directory_name
          / 'skills'
          / 'example'
          / 'SKILL.md'
        )
        self.assertRejected()
        for path in sorted(
          (self.root / 'nested').rglob('*'),
          reverse=True,
        ):
          if path.is_file():
            path.unlink()
          elif path.is_dir():
            path.rmdir()

  def test_allows_generic_agent_and_skill_names(self):
    self.write('agents/SKILL.md')
    self.write('skills/agent/rules.md')
    self.write('docs/sys.md')
    self.write('TEAM_GUIDE.md')
    self.write('CONTEXT.md')

    check_repository_policy(self.root)

  def test_ignores_gitignored_policy_paths(self):
    self.write('.gitignore', 'ignored/\n')
    self.write('ignored/AGENTS.md')
    self.write('ignored/.claude/skills/example/SKILL.md')
    self.write('visible/README.md')

    check_repository_policy(self.root)

  def test_rejects_tracked_path_even_when_gitignore_matches(self):
    self.write('.gitignore', 'AGENTS.md\n')
    self.write('AGENTS.md')
    subprocess.run(
      ['git', 'add', '-f', 'AGENTS.md'],
      cwd=self.root,
      check=True,
    )

    self.assertRejected()

  def test_does_not_treat_ripgrep_ignore_files_as_git_ignores(self):
    for ignore_name in ('.ignore', '.rgignore'):
      with self.subTest(ignore_name=ignore_name):
        self.write(ignore_name, 'AGENTS.md\n')
        self.write('AGENTS.md')
        self.assertRejected()
        (self.root / 'AGENTS.md').unlink()
        (self.root / ignore_name).unlink()

  def test_rejects_banned_symlink_path_component(self):
    target = self.root.parent / f'{self.root.name}-agent-state'
    target.mkdir()
    self.addCleanup(target.rmdir)
    (self.root / '.agents').symlink_to(target, target_is_directory=True)

    self.assertRejected()

  def test_excludes_the_git_tree_but_scans_other_hidden_paths(self):
    self.write('.git/AGENTS.md')
    self.write('.visible/GEMINI.md')

    with self.assertRaisesRegex(RepositoryPolicyError, 'GEMINI.md'):
      check_repository_policy(self.root)
