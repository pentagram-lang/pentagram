import subprocess
import tempfile
import unittest
from pathlib import Path

from zero.commit_message import (
  CommitMessageLintError,
  check_commit_message,
  lint_commit_message,
)


class CommitMessageLintTest(unittest.TestCase):
  def setUp(self):
    self.directory = tempfile.TemporaryDirectory()
    self.root = Path(self.directory.name)
    subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
    subprocess.run(
      ['git', 'config', 'user.name', 'Test Contributor'],
      cwd=self.root,
      check=True,
    )
    subprocess.run(
      ['git', 'config', 'user.email', 'test@example.invalid'],
      cwd=self.root,
      check=True,
    )
    self.commit_number = 0

  def tearDown(self):
    self.directory.cleanup()

  def commit(self, message):
    self.commit_number += 1
    (self.root / 'file').write_text(str(self.commit_number))
    message_path = self.root / 'message'
    message_path.write_text(message)
    subprocess.run(['git', 'add', 'file'], cwd=self.root, check=True)
    subprocess.run(
      [
        'git',
        '-c',
        'commit.gpgSign=false',
        'commit',
        '-q',
        '--no-verify',
        '-F',
        str(message_path),
      ],
      cwd=self.root,
      check=True,
    )

  def diagnostics(self, message):
    self.commit(message)
    return lint_commit_message(self.root)

  def test_accepts_message_with_short_subject_and_body(self):
    self.assertEqual(
      (),
      self.diagnostics(
        'feat: add a useful capability\n\nThe body fits.\n'
      ),
    )

  def test_rejects_subject_longer_than_72_characters(self):
    diagnostics = self.diagnostics('x' * 73 + '\n')

    self.assertEqual(
      ('CM001',), tuple(diagnostic.code for diagnostic in diagnostics)
    )
    self.assertEqual(1, diagnostics[0].line)
    self.assertEqual(73, diagnostics[0].length)

  def test_rejects_unwrapped_body_prose(self):
    diagnostics = self.diagnostics(
      'feat: add a capability\n\n' + 'word ' * 15
    )

    self.assertEqual(
      ('CM002',), tuple(diagnostic.code for diagnostic in diagnostics)
    )
    self.assertEqual(3, diagnostics[0].line)

  def test_accepts_explicit_exact_literal_lines(self):
    body = '\n'.join(
      [
        'https://' + 'a' * 80,
        '$ command ' + 'argument ' * 12,
        './' + 'path-' * 20,
        'Type::' + 'Name' * 20,
        '`' + 'quoted literal ' * 10 + '`',
      ]
    )

    self.assertEqual(
      (), self.diagnostics('feat: preserve literals\n\n' + body + '\n')
    )

  def test_rejects_prose_that_contains_a_literal(self):
    body = 'See https://' + 'a' * 80 + ' for the details.'

    diagnostics = self.diagnostics(
      'feat: explain a choice\n\n' + body + '\n'
    )

    self.assertEqual(
      ('CM002',), tuple(diagnostic.code for diagnostic in diagnostics)
    )

  def test_rejects_a_long_unqualified_token(self):
    diagnostics = self.diagnostics(
      'feat: explain a choice\n\n' + 'a' * 80 + '\n'
    )

    self.assertEqual(
      ('CM002',), tuple(diagnostic.code for diagnostic in diagnostics)
    )

  def test_wip_message_is_accepted(self):
    self.assertEqual((), self.diagnostics('WIP\n'))

  def test_checks_only_the_current_commit(self):
    self.commit('feat: old commit\n\n' + 'word ' * 15)
    self.commit('feat: current commit\n\nThe body fits.\n')

    self.assertEqual((), lint_commit_message(self.root))

  def test_diagnostics_are_stable_and_sorted(self):
    message = 'x' * 73 + '\n\n' + 'word ' * 15
    first = self.diagnostics(message)
    second = lint_commit_message(self.root)

    self.assertEqual(first, second)
    self.assertEqual(first, tuple(sorted(first)))
    self.assertEqual(('CM001', 'CM002'), tuple(d.code for d in first))

  def test_check_raises_for_invalid_message(self):
    self.commit('feat: invalid\n\n' + 'word ' * 15)

    with self.assertRaisesRegex(
      CommitMessageLintError,
      r'line 3: CM002: body line is 74 characters; maximum is 72',
    ):
      check_commit_message(self.root)


if __name__ == '__main__':
  unittest.main()
