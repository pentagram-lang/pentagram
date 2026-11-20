from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from zero.doc_lint import check_docs
from zero.lib import Diagnostic


@pytest.fixture
def shm_repo() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='zero-doc-test-', dir='/dev/shm'))
  subprocess.run(['git', 'init', '-q', str(d)], check=True)
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def _write(repo: Path, rel: str, text: str) -> None:
  p = repo / rel
  p.parent.mkdir(parents=True, exist_ok=True)
  p.write_text(text, encoding='utf-8')


def test_valid_surface_and_fenced_fixtures(shm_repo: Path) -> None:
  _write(
    shm_repo,
    'README.md',
    '# Root\n\n'
    '## Guide\n\n[Guide](guide.md)\n\n'
    '## Hidden\n\n[Hidden](.hidden/README.md)\n',
  )
  _write(
    shm_repo,
    'guide.md',
    '# Guide\n\n'
    'See [Root](README.md#guide) and [root](README.md#guide).\n'
    'External [web](https://example.com) and [proto](//cdn.test/a).\n'
    'Code [src](mod.rs) and [self](#section-0-a).\n\n'
    '## Section `0` a\n\nText.\n',
  )
  _write(
    shm_repo,
    'guide.test.md',
    '# Tests\n\n'
    '## Use guide\n\n'
    '**Task**\n\n'
    'Read:\n\n'
    '```md\n'
    '# Not an H1\n'
    '### Not an H3\n'
    '```\n\n'
    '**Assert**\n\n'
    '- Cites [guide](guide.md).\n',
  )
  _write(shm_repo, '.hidden/README.md', '# Hidden\n\nLeaf.\n')
  _write(shm_repo, 'mod.rs', 'fn main() {}\n')
  _write(
    shm_repo,
    'only_code/item.test.md',
    '# Tests\n\n## Run\n\n**Task**\n\nDo.\n\n**Assert**\n\n- Pass.\n',
  )
  _write(shm_repo, 'only_code/item.rs', 'fn item() {}\n')
  assert check_docs(shm_repo) == []


def test_companion_naming_and_pairing(shm_repo: Path) -> None:
  _write(
    shm_repo,
    'README.md',
    '# Root\n\n## Dup\n\n[Dup](dup.md)\n',
  )
  _write(shm_repo, 'dup.md', '# Dup\n')
  _write(shm_repo, 'dup.rs', '')
  _write(
    shm_repo,
    'dup.test.md',
    '# Tests\n\n## A\n\n**Task**\n\nDo.\n\n**Assert**\n\n- Ok.\n',
  )
  _write(
    shm_repo,
    'orphan.test.md',
    '# Tests\n\n## A\n\n**Task**\n\nDo.\n\n**Assert**\n\n- Ok.\n',
  )
  _write(shm_repo, 'a.b.test.md', '# Tests\n')
  _write(shm_repo, 'bad_test.md', '# Tests\n')

  assert check_docs(shm_repo) == [
    Diagnostic(
      'a.b.test.md',
      "invalid test companion name 'a.b.test.md'; "
      'expected <stem>.test.md without "." or "test" in stem',
    ),
    Diagnostic(
      'bad_test.md',
      "invalid test companion name 'bad_test.md'; "
      'expected <stem>.test.md without "." or "test" in stem',
    ),
    Diagnostic(
      'dup.test.md',
      "test companion 'dup.test.md' matches multiple siblings: "
      'dup.md, dup.rs',
    ),
    Diagnostic(
      'orphan.test.md',
      "test companion 'orphan.test.md' lacks "
      'non-test sibling orphan.<ext>',
    ),
  ]


def test_companion_structure_failures(shm_repo: Path) -> None:
  _write(shm_repo, 'README.md', '# Root\n\n## A\n\n[A](a.md)\n')
  _write(shm_repo, 'a.md', '# A\n')
  _write(
    shm_repo,
    'a.test.md',
    '# Wrong\n\n'
    'Prose before H2.\n\n'
    '## Dup\n\n'
    'No task.\n\n'
    '**Assert**\n\n'
    '- Ok.\n\n'
    '## Dup\n\n'
    '**Task**\n\n'
    '**Assert**\n\n'
    '- \n\n'
    'Extra paragraph.\n\n'
    '### Bad H3\n',
  )
  assert check_docs(shm_repo) == [
    Diagnostic('a.test.md', 'test companion must start with "# Tests"', 1),
    Diagnostic(
      'a.test.md', 'expected "## <name>" immediately after "# Tests"', 3
    ),
    Diagnostic('a.test.md', "duplicate test heading 'Dup'", 13),
    Diagnostic('a.test.md', 'unexpected H3 heading in test companion', 23),
    Diagnostic('a.test.md', "test 'Dup' must start with **Task**", 5),
    Diagnostic(
      'a.test.md', "test 'Dup' requires Task content before **Assert**", 17
    ),
    Diagnostic(
      'a.test.md',
      "test 'Dup' must have one bullet list after **Assert**",
      17,
    ),
    Diagnostic(
      'a.test.md',
      'duplicate heading identifier #dup (first on line 5)',
      13,
    ),
  ]


def test_headings_links_and_empty_assert_item(shm_repo: Path) -> None:
  _write(
    shm_repo,
    'README.md',
    '# Root\n\n## Target\n\n[Target](target.md)\n',
  )
  _write(
    shm_repo,
    'target.md',
    '# Title\n\n## title\n\n'
    '[q](README.md?a=1)\n\n'
    '[esc](../out.md)\n\n'
    '[abs](/README.md)\n\n'
    '[dir](sub/)\n\n'
    '[case](Readme.md)\n\n'
    '[miss](none.md)\n\n'
    '[nonmd](x.rs#frag)\n\n'
    '[badfrag](README.md#missing)\n\n'
    '[one](README.md#target)\n\n'
    '[two](README.md#target)\n',
  )
  _write(shm_repo, 'sub/README.md', '# Sub\n')
  _write(shm_repo, 'x.rs', '')
  _write(
    shm_repo,
    'target.test.md',
    '# Tests\n\n## Empty item\n\n**Task**\n\nDo.\n\n**Assert**\n\n- \n',
  )

  assert check_docs(shm_repo) == [
    Diagnostic(
      'target.test.md',
      "test 'Empty item' has an empty Assert bullet item",
      11,
    ),
    Diagnostic(
      'target.md',
      'duplicate heading identifier #title (first on line 1)',
      3,
    ),
    Diagnostic(
      'target.md',
      "query string is not allowed in local link 'README.md?a=1'",
      5,
    ),
    Diagnostic('target.md', "link '../out.md' escapes repository root", 7),
    Diagnostic(
      'target.md',
      "link '/README.md' must be relative, not root-anchored",
      9,
    ),
    Diagnostic('target.md', "link 'sub/' targets a directory", 11),
    Diagnostic(
      'target.md',
      "link 'Readme.md' target 'Readme.md' not found in inventory",
      13,
    ),
    Diagnostic(
      'target.md',
      "link 'none.md' target 'none.md' not found in inventory",
      15,
    ),
    Diagnostic(
      'target.md',
      "fragment link 'x.rs#frag' targets non-Markdown file 'x.rs'",
      17,
    ),
    Diagnostic('target.md', 'missing heading #missing in README.md', 19),
    Diagnostic(
      'target.md',
      "inconsistent link text 'two' for 'README.md#target' "
      "(was 'one' on line 21)",
      23,
    ),
    Diagnostic(
      'README.md', 'missing H2 index section linking to sub/README.md'
    ),
  ]


def test_readme_index_and_inventory_filtering(shm_repo: Path) -> None:
  _write(shm_repo, '.gitignore', 'ignored.md\n')
  _write(shm_repo, 'ignored.md', '# Ignored\n')
  _write(
    shm_repo,
    'README.md',
    '# Root\n\n'
    '## Both\n\n[A](a.md) [B](b.md)\n\n'
    '## Empty\n\nNo child link.\n\n'
    '## Again\n\n[A](a.md)\n',
  )
  _write(shm_repo, 'a.md', '# A\n')
  _write(shm_repo, 'b.md', '# B\n')
  _write(shm_repo, 'c.md', '# C\n')
  _write(shm_repo, 'orphan_dir/leaf.md', '# Leaf\n')
  _write(shm_repo, 'deleted.md', '# Deleted\n')
  subprocess.run(
    ['git', '-C', str(shm_repo), 'add', 'deleted.md'], check=True
  )
  (shm_repo / 'deleted.md').unlink()

  outside = shm_repo.parent / 'outside_escape_test.md'
  outside.write_text('# Outside\n', encoding='utf-8')
  try:
    (shm_repo / 'escape.md').symlink_to(outside)
    diags = check_docs(shm_repo)
  finally:
    outside.unlink(missing_ok=True)

  assert diags == [
    Diagnostic(
      'orphan_dir/README.md', "directory 'orphan_dir' is missing README.md"
    ),
    Diagnostic(
      'README.md',
      'index H2 section must link to exactly one direct child (found 2)',
      3,
    ),
    Diagnostic(
      'README.md',
      'index H2 section must link to exactly one direct child (found 0)',
      7,
    ),
    Diagnostic(
      'README.md', 'direct child a.md linked from multiple H2 sections', 11
    ),
    Diagnostic('README.md', 'missing H2 index section linking to c.md'),
  ]


def test_heading_hierarchy_and_index_headings(shm_repo: Path) -> None:
  _write(
    shm_repo,
    'README.md',
    '# Root\n\n'
    '## A\n\n[A](a.md)\n\n### Bad index H3\n\n'
    '## B\n\n[B](b.md)\n\n'
    '## C\n\n[C](c.md)\n\n'
    '## License\n\n[License](LICENSE.md)\n\n'
    '## Sub\n\n[Sub](sub/README.md)\n\n'
    '## Empty index\n\n[Empty index](empty_idx/README.md)\n',
  )
  _write(shm_repo, 'LICENSE.md', 'Plain license text without headings.\n')
  _write(shm_repo, 'sub/README.md', '# Sub\n\n## Leaf\n\n### Allowed H3\n')
  _write(shm_repo, 'empty_idx/README.md', 'Prose without headings.\n')
  _write(shm_repo, 'empty_idx/item.md', '# Item\n')
  _write(shm_repo, 'a.md', '## Starts at H2\n\n### Child\n')
  _write(shm_repo, 'b.md', '# First\n\n# Second\n')
  _write(
    shm_repo,
    'c.md',
    '# Top\n\n### Skip to H3\n\n## Ok\n\n#### Skip to H4\n',
  )

  assert check_docs(shm_repo) == [
    Diagnostic('a.md', 'first heading must be H1, found H2', 1),
    Diagnostic(
      'b.md', 'unexpected H1 heading; only the first heading may be H1', 3
    ),
    Diagnostic('c.md', 'heading level H3 skips from H1', 3),
    Diagnostic('c.md', 'heading level H4 skips from H2', 7),
    Diagnostic('README.md', 'unexpected H3 heading in index README', 7),
    Diagnostic(
      'empty_idx/README.md', 'index README is missing H1 title', 1
    ),
    Diagnostic(
      'empty_idx/README.md',
      'missing H2 index section linking to empty_idx/item.md',
    ),
  ]
