import unittest
from unittest.mock import DEFAULT, patch

from click.testing import CliRunner

from zero.__main__ import cli


class CommandPlaneTest(unittest.TestCase):
  def test_doc_check_runs_independent_timed_step(self):
    with patch('zero.__main__.doc_lint.check_documentation') as check:
      result = CliRunner().invoke(cli, ['check', 'doc'])

    self.assertEqual(0, result.exit_code)
    check.assert_called_once()
    self.assertIn('[PASS] doc-lint (', result.output)

  def test_commit_check_runs_independent_timed_step(self):
    with patch(
      'zero.__main__.commit_message.check_commit_message'
    ) as check:
      result = CliRunner().invoke(cli, ['check', 'commit'])

    self.assertEqual(0, result.exit_code)
    check.assert_called_once()
    self.assertIn('[PASS] commit-message (', result.output)

  def test_skip_commit_bypasses_line_and_history_checks(self):
    with patch.multiple(
      'zero.__main__',
      do_check_fmt=DEFAULT,
      do_check_lint=DEFAULT,
      do_check_repo_policy=DEFAULT,
      do_check_doc_lint=DEFAULT,
      do_ztest=DEFAULT,
      do_ptest=DEFAULT,
      do_btest=DEFAULT,
      do_test=DEFAULT,
      do_check_commit_message=DEFAULT,
      do_check_history=DEFAULT,
    ) as checks:
      result = CliRunner().invoke(cli, ['check', '--skip-commit'])

    self.assertEqual(0, result.exit_code)
    checks['do_check_commit_message'].assert_not_called()
    checks['do_check_history'].assert_not_called()


if __name__ == '__main__':
  unittest.main()
