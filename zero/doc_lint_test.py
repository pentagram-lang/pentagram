import subprocess
import tempfile
import unittest
from pathlib import Path

from zero.doc_lint import check_documentation, lint_repository


class DocumentationLintTest(unittest.TestCase):
  def setUp(self):
    self.directory = tempfile.TemporaryDirectory()
    self.root = Path(self.directory.name)
    subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)

  def tearDown(self):
    self.directory.cleanup()

  def write(self, relative_path, content):
    path = self.root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

  def diagnostics(self):
    return lint_repository(self.root)

  def codes(self):
    return [diagnostic.code for diagnostic in self.diagnostics()]

  def write_root_index(self, children):
    content = '# Root\n\n'
    for title, path in children:
      content += f'## {title}\n\n[{title}]({path})\n\n'
    self.write('README.md', content)

  def test_rejects_duplicate_generated_heading_identifiers(self):
    self.write('README.md', '# Root\n\n## A-B\n\n## A B\n')

    diagnostics = self.diagnostics()

    self.assertEqual(['MD001'], self.codes())
    self.assertEqual('README.md', diagnostics[0].path)
    self.assertEqual(5, diagnostics[0].line)
    self.assertIn("heading identifier 'a-b'", diagnostics[0].message)

  def test_resolves_local_links_and_excludes_external_markup(self):
    self.write_root_index([('Guide', 'guide.md')])
    self.write(
      'guide.md',
      """# Guide

## Details

[details](#details)
[missing](missing.md)
[wrong case](GUIDE.md)
[query](guide.md?view=full)
[outside](../../outside.md)
[directory](assets)
[missing heading](guide.md#missing)
[external](https://example.com/guide.md)

```markdown
[code](missing.md)
```

<a href="missing.md">html</a>
""",
    )
    (self.root / 'assets').mkdir()

    diagnostics = self.diagnostics()

    self.assertEqual(6, self.codes().count('MD002'))
    self.assertNotIn('MD003', self.codes())
    self.assertTrue(
      all(diagnostic.path == 'guide.md' for diagnostic in diagnostics)
    )

  def test_requires_consistent_text_for_one_link_target(self):
    self.write_root_index([('Guide', 'guide.md'), ('Target', 'target.md')])
    self.write(
      'guide.md',
      """# Guide

[first](target.md)
[second](./target.md)
""",
    )
    self.write('target.md', '# Target\n')

    diagnostics = self.diagnostics()

    self.assertEqual(['MD003'], self.codes())
    self.assertEqual(3, diagnostics[0].line)
    self.assertIn("local links to 'target.md'", diagnostics[0].message)

  def test_requires_index_sections_for_direct_children(self):
    self.write('README.md', '# Root\n')
    self.write('guide.md', '# Guide\n')

    diagnostics = self.diagnostics()

    self.assertEqual(['MD004'], self.codes())
    self.assertIn("direct child 'guide.md'", diagnostics[0].message)

  def test_requires_a_readme_for_every_markdown_directory(self):
    self.write('README.md', '# Root\n')
    self.write('nested/guide.md', '# Guide\n')

    diagnostics = self.diagnostics()

    self.assertEqual(['MD004'], self.codes())
    self.assertIn("directory 'nested'", diagnostics[0].message)

  def test_accepts_an_index_with_file_and_directory_children(self):
    self.write_root_index(
      [('Guide', 'guide.md'), ('Details', 'details/README.md')]
    )
    self.write('guide.md', '# Guide\n')
    self.write(
      'details/README.md',
      '# Details\n\n## Notes\n\n[Notes](notes.md)\n',
    )
    self.write('details/notes.md', '# Notes\n')

    self.assertEqual((), self.diagnostics())

  def test_requires_test_companion_subject_and_structure(self):
    self.write_root_index([('Guide', 'guide.md')])
    self.write('orphan.test.md', '# Tests\n')
    self.write('guide.md', '# Guide\n')
    self.write(
      'guide.test.md',
      '# Tests\n\n## Guide\n\n**Task**\n\nRead it.\n\n'
      '**Assert**\n\n- It works.\n',
    )
    self.write('guide.test.test.md', '# Tests\n')

    diagnostics = self.diagnostics()

    self.assertEqual(['MD005', 'MD005'], self.codes())
    messages = [diagnostic.message for diagnostic in diagnostics]
    self.assertTrue(
      any('not an inventoried file' in message for message in messages)
    )
    self.assertTrue(
      any(
        'cannot have a test companion' in message for message in messages
      )
    )

  def test_rejects_empty_tasks_and_assertion_lists(self):
    self.write_root_index([('Guide', 'guide.md')])
    self.write('guide.md', '# Guide\n')
    self.write(
      'guide.test.md',
      """# Tests

## Empty

**Task**

**Assert**

-
""",
    )

    diagnostics = self.diagnostics()

    self.assertEqual(['MD005', 'MD005'], self.codes())
    messages = [diagnostic.message for diagnostic in diagnostics]
    self.assertTrue(
      any('Task must not be empty' in message for message in messages)
    )
    self.assertTrue(
      any(
        'Assert must contain a non-empty list' in message
        for message in messages
      )
    )

  def test_uses_only_current_git_inventory(self):
    self.write('README.md', '# Root\n')
    self.write('.gitignore', 'ignored.md\n')
    self.write('ignored.md', '# A\n\n# A\n')
    self.write('tracked.md', '# A\n')
    subprocess.run(['git', 'add', 'tracked.md'], cwd=self.root, check=True)
    (self.root / 'tracked.md').unlink()

    check_documentation(self.root)

  def test_returns_stable_sorted_diagnostics(self):
    self.write(
      'README.md',
      '# Root\n\n## A-B\n\n## A B\n\n[missing](missing.md)\n',
    )

    first = self.diagnostics()
    second = self.diagnostics()

    self.assertEqual(first, second)
    self.assertEqual(first, tuple(sorted(first)))


if __name__ == '__main__':
  unittest.main()
