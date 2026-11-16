"""Tests for zero.doc_lint."""

import os
import stat
import subprocess
from pathlib import Path

import pytest

from zero import doc_lint


def test_parse_document_extracts_structure_and_heading_links() -> None:
  document = doc_lint.parse_document(
    'docs/README.md',
    '# Guide ![`icon`](badge.png)\n\n'
    '## [Child `doc`](child.md#overview)\n\n'
    '[External](https://example.invalid/guide)\n',
  )

  assert document == doc_lint.Document(
    path='docs/README.md',
    line_count=5,
    headings=(
      doc_lint.Heading(1, 1, 'Guide icon', 'guide-icon'),
      doc_lint.Heading(2, 3, 'Child doc', 'child-doc'),
    ),
    links=(
      doc_lint.Link(
        3,
        'Child doc',
        'child.md#overview',
        doc_lint.ResolvedLink(
          path='docs/child.md',
          fragment='overview',
          traversal_prefixes=('docs',),
        ),
      ),
      doc_lint.Link(
        5,
        'External',
        'https://example.invalid/guide',
        None,
      ),
    ),
    test_sections=(),
  )

  companion = doc_lint.parse_document(
    'module.py.test.md',
    '# Tests\n\n> ## Quoted\n\n## Build\n\n**Task**\n\nRun.\n\n'
    '**Assert**\n\n- Ok\n',
  )
  assert companion.headings == (
    doc_lint.Heading(1, 1, 'Tests', 'tests', is_top_level=True),
    doc_lint.Heading(2, 3, 'Quoted', 'quoted', is_top_level=False),
    doc_lint.Heading(2, 5, 'Build', 'build', is_top_level=True),
  )
  assert companion.test_sections == (
    doc_lint.CompanionSection(
      line=5,
      labels=('Task', 'Assert'),
      has_task_content=True,
      has_nonempty_assert_list=True,
    ),
  )


@pytest.mark.parametrize(
  ('source_path', 'href', 'expected'),
  [
    (
      'docs/README.md',
      '../guide.md#details',
      doc_lint.ResolvedLink(
        path='guide.md',
        fragment='details',
        traversal_prefixes=('docs',),
      ),
    ),
    (
      'README.md',
      '#local',
      doc_lint.ResolvedLink(path='README.md', fragment='local'),
    ),
    (
      'README.md',
      '#',
      doc_lint.ResolvedLink(path='README.md', fragment=''),
    ),
    (
      'README.md',
      'guide.md#',
      doc_lint.ResolvedLink(path='guide.md', fragment=''),
    ),
    ('README.md', '', doc_lint.InvalidLink('empty')),
    ('README.md', '../../outside.md', doc_lint.InvalidLink('outside')),
    ('README.md', '/abs.md', doc_lint.InvalidLink('outside')),
    ('README.md', 'guide.md?mode=full', doc_lint.InvalidLink('query')),
    (
      'README.md',
      'guide.md/',
      doc_lint.ResolvedLink(
        path='guide.md',
        is_directory=True,
        traversal_prefixes=('guide.md',),
      ),
    ),
    (
      'README.md',
      'missing/',
      doc_lint.ResolvedLink(
        path='missing',
        is_directory=True,
        traversal_prefixes=('missing',),
      ),
    ),
    (
      'README.md',
      'guide.md/../README.md',
      doc_lint.ResolvedLink(
        path='README.md', traversal_prefixes=('guide.md',)
      ),
    ),
    (
      'README.md',
      '.',
      doc_lint.ResolvedLink(path='', is_directory=True),
    ),
    (
      'docs/README.md',
      'guide%20page.md#sec%20one',
      doc_lint.ResolvedLink(
        path='docs/guide page.md',
        fragment='sec one',
        traversal_prefixes=('docs',),
      ),
    ),
  ],
  ids=(
    'relative-fragment',
    'same-file-fragment',
    'empty-self-fragment',
    'empty-file-fragment',
    'empty-href',
    'outside-root',
    'leading-slash',
    'query',
    'trailing-slash-file',
    'trailing-slash-missing',
    'traverse-through-file',
    'root-dot',
    'percent-decoded',
  ),
)
def test_link_target_normalizes_paths_and_edge_cases(
  source_path: str,
  href: str,
  expected: doc_lint.LinkTarget,
) -> None:
  assert doc_lint.link_target(source_path, href) == expected


def test_lint_sources_accepts_heading_links_and_image_alt_text() -> None:
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': (
        '# Docs\n\n## [Guide ![badge](icon.png)](guide.md)\n\n'
        '[Details](guide.md#details-pic)\n'
      ),
      'guide.md': '# Guide\n\n## Details ![pic](icon.png)\n',
      'icon.png': '',
    }
  )

  assert diagnostics == ()


def test_lint_sources_reports_link_and_heading_edge_cases() -> None:
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': (
        '# \n\n'
        '[Empty]()\n'
        '[Hash](#)\n'
        '[GuideHash](guide.md#)\n'
        '[SlashFile](guide.md/)\n'
        '[MissingDir](missing/)\n'
        '[Traverse](guide.md/../README.md)\n'
        '[DotFile](guide.md/.)\n'
        '[Root](.)\n'
        '[RootSlash](./)\n'
        '[MissingHeadingLink](#missing)\n'
        '## [Guide](guide.md)\n'
      ),
      'guide.md': '# Guide\n# Guide\n',
      'sub/README.md': '# Sub\n\n[Up](..)\n',
    }
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'README.md',
      1,
      'MD004',
      "direct child 'sub/README.md' must be linked from exactly one H2 "
      'section; found 0',
    ),
    doc_lint.Diagnostic(
      'README.md', 3, 'MD002', 'local link destination is empty'
    ),
    doc_lint.Diagnostic(
      'README.md',
      4,
      'MD002',
      "local link fragment '#' does not identify a heading in 'README.md'",
    ),
    doc_lint.Diagnostic(
      'README.md',
      5,
      'MD002',
      "local link fragment '#' does not identify a heading in 'guide.md'",
    ),
    doc_lint.Diagnostic(
      'README.md',
      6,
      'MD002',
      "local link path traverses through non-directory file 'guide.md'",
    ),
    doc_lint.Diagnostic(
      'README.md',
      7,
      'MD002',
      "local link target 'missing/' is not an inventoried file",
    ),
    doc_lint.Diagnostic(
      'README.md',
      8,
      'MD002',
      "local link path traverses through non-directory file 'guide.md'",
    ),
    doc_lint.Diagnostic(
      'README.md',
      9,
      'MD002',
      "local link path traverses through non-directory file 'guide.md'",
    ),
    doc_lint.Diagnostic(
      'README.md', 10, 'MD002', 'local link target is a directory'
    ),
    doc_lint.Diagnostic(
      'README.md', 11, 'MD002', 'local link target is a directory'
    ),
    doc_lint.Diagnostic(
      'README.md',
      12,
      'MD002',
      "local link fragment '#missing' does not identify a heading in "
      "'README.md'",
    ),
    doc_lint.Diagnostic(
      'guide.md',
      2,
      'MD001',
      "heading identifier 'guide' is duplicated; first used at line 1",
    ),
    doc_lint.Diagnostic(
      'sub/README.md', 3, 'MD002', 'local link target is a directory'
    ),
  )


def test_lint_sources_counts_distinct_h2_sections_per_child() -> None:
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': (
        '# Docs\n\n## Guide\n\n[Guide](guide.md)\n[Guide](guide.md)\n'
      ),
      'guide.md': '# Guide\n',
    }
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'README.md',
      3,
      'MD004',
      'H2 section must link to exactly one direct child; found 2',
    ),
  )


@pytest.mark.parametrize(
  ('source', 'line'),
  [
    ('# Docs\n\nIntro on the first line.\n[Missing](missing.md)\n', 4),
    (
      '# Docs\n\nIntro on the first line.\n'
      '`code\nspan` [Missing](missing.md)\n',
      5,
    ),
    (
      '<span title="`a b`"></span> `a\nb` [Missing](missing.md)\n',
      2,
    ),
    (
      '[before](https://example.invalid/url`foo`) `\nfoo\n` '
      '[Missing](missing.md)\n',
      3,
    ),
  ],
  ids=(
    'soft-break',
    'multiline-code-span',
    'code-span-after-html',
    'code-span-after-link-destination',
  ),
)
def test_lint_sources_reports_multiline_links_at_source_line(
  source: str, line: int
) -> None:
  diagnostics = doc_lint.lint_sources({'README.md': source})

  assert diagnostics == (
    doc_lint.Diagnostic(
      'README.md',
      line,
      'MD002',
      "local link target 'missing.md' is not an inventoried file",
    ),
  )


@pytest.mark.parametrize(
  ('href', 'message'),
  [
    (
      'Guide.md',
      "local link target 'Guide.md' is not an inventoried file",
    ),
    ('guide/', 'local link target is a directory'),
    ('empty-dir/', 'local link target is a directory'),
  ],
  ids=('wrong-case-path', 'inferred-directory', 'explicit-directory'),
)
def test_lint_sources_rejects_wrong_case_and_directory_targets(
  href: str, message: str
) -> None:
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': (
        '# Docs\n\n## Guide\n\n[Guide](guide/README.md)\n\n'
        f'[Invalid]({href})\n'
      ),
      'guide/README.md': '# Guide\n',
    },
    directories={'empty-dir'},
  )

  assert diagnostics == (
    doc_lint.Diagnostic('README.md', 7, 'MD002', message),
  )


def test_lint_sources_does_not_depend_on_inventory_order() -> None:
  sources = {
    'README.md': '# Docs\n\n[Missing](missing.md)\n',
    'guide.md': '# Guide\n# Guide\n',
  }
  first = doc_lint.lint_sources(sources)
  reversed_run = doc_lint.lint_sources(
    sources, inventory=reversed(tuple(sources))
  )

  expected = (
    doc_lint.Diagnostic(
      'README.md',
      1,
      'MD004',
      "direct child 'guide.md' must be linked from exactly one H2 "
      'section; found 0',
    ),
    doc_lint.Diagnostic(
      'README.md',
      3,
      'MD002',
      "local link target 'missing.md' is not an inventoried file",
    ),
    doc_lint.Diagnostic(
      'guide.md',
      2,
      'MD001',
      "heading identifier 'guide' is duplicated; first used at line 1",
    ),
  )

  assert first == expected
  assert reversed_run == expected


def test_lint_sources_reports_ambiguous_missing_and_misnamed_targets() -> (
  None
):
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': '# Docs\n\n## Guide\n\n[Guide](guide.md)\n',
      'guide.md': '# Guide\n\n## Details\n\n## Details\n',
      'module.py': 'def build():\n  return 1\n',
      'module.py.test.md': (
        '# Tests\n\n'
        '[One](guide.md#details)\n\n'
        '[Guide](guide.md#missing)\n\n'
        '[Guide](guide.md#guide)\n\n'
        '[Different](guide.md#guide)\n\n'
        '## Build result\n\n**Task**\n\nRun build.\n\n'
        '**Assert**\n\n- The result is 1.\n'
      ),
    }
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'guide.md',
      5,
      'MD001',
      "heading identifier 'details' is duplicated; first used at line 3",
    ),
    doc_lint.Diagnostic(
      'module.py.test.md',
      3,
      'MD002',
      "local link fragment '#details' identifies multiple headings in "
      "'guide.md'",
    ),
    doc_lint.Diagnostic(
      'module.py.test.md',
      5,
      'MD002',
      "local link fragment '#missing' does not identify a heading in "
      "'guide.md'",
    ),
    doc_lint.Diagnostic(
      'module.py.test.md',
      9,
      'MD003',
      "local links to 'guide.md' use different visible text from line 7",
    ),
  )


def test_lint_sources_accepts_case_variation_and_external_markup() -> None:
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': (
        '# Docs\n\n## Guide\n\n[Guide](guide.md)\n\n'
        '[External](https://example.invalid/guide)\n'
        '`[Code](missing.md)`\n'
        '<a href="missing.md">HTML</a>\n'
      ),
      'guide.md': '# Guide\n',
      'module.py': 'def build():\n  return 1\n',
      'module.py.test.md': (
        '# Tests\n\n[Build](guide.md)\n[build](guide.md)\n\n'
        '## Build result\n\n**Task**\n\nRun build.\n\n'
        '**Assert**\n\n- \n  - \n- Outer\n'
      ),
    }
  )

  assert diagnostics == ()


def test_lint_sources_requires_directory_indexes_to_link_children() -> (
  None
):
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': (
        '# Docs\n\n## Guide\n\n[Guide](guide.md)\n\n'
        '## Nested\n\n[Nested](nested/README.md)\n'
      ),
      'guide.md': '# Guide\n',
      'nested/README.md': '# Nested\n\n## Detail\n',
      'nested/detail.md': '# Detail\n',
      'orphan/guide.md': '# Orphan\n',
    }
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'nested/README.md',
      1,
      'MD004',
      "direct child 'nested/detail.md' must be linked from exactly one "
      'H2 section; found 0',
    ),
    doc_lint.Diagnostic(
      'nested/README.md',
      3,
      'MD004',
      'H2 section must link to exactly one direct child; found 0',
    ),
    doc_lint.Diagnostic(
      'orphan/guide.md',
      1,
      'MD004',
      "directory 'orphan' contains Markdown but has no README.md",
    ),
  )


def test_lint_sources_validates_all_companion_rules() -> None:
  subject_and_nesting = doc_lint.lint_sources(
    {
      'README.md': '# Docs\n\n## Mod\n\n[Mod](mod.py.md)\n',
      'mod.py': 'def build(): pass\n',
      'mod.py.md': '# Mod\n',
      'mod.py.test.md': '# Tests\n',
      'parser.rs': 'fn main() {}\n',
      'parser.rs.test.md': '# Tests\n',
      'parser.rs.test.md.test.md': '# Tests\n',
      'guide': 'ok\n',
      'guide.test.md': '# Tests\n',
      'guide.test.md.test.md': '# Tests\n',
      'guide.test.test.md': '# Tests\n',
      'other.test.test.md': '# Tests\n',
    }
  )
  assert subject_and_nesting == (
    doc_lint.Diagnostic(
      'guide.test.md.test.md',
      1,
      'MD005',
      'a test companion cannot have a test companion',
    ),
    doc_lint.Diagnostic(
      'guide.test.test.md',
      1,
      'MD005',
      'a test companion cannot have a test companion',
    ),
    doc_lint.Diagnostic(
      'mod.py.test.md',
      1,
      'MD005',
      "test companion subject is ambiguous between 'mod.py.md' and "
      "'mod.py'",
    ),
    doc_lint.Diagnostic(
      'other.test.test.md',
      1,
      'MD005',
      'test companion subject is not an inventoried file; expected '
      "'other.test'",
    ),
    doc_lint.Diagnostic(
      'parser.rs.test.md.test.md',
      1,
      'MD005',
      'a test companion cannot have a test companion',
    ),
  )

  wrong_h1_dup_h2_empty_task_and_nested_headings = doc_lint.lint_sources(
    {
      'README.md': '# Docs\n',
      'a.py': 'pass\n',
      'a.py.test.md': (
        '> # Tests\n\n'
        '> ## Quoted H2\n\n'
        '## Case\n\n'
        '**Task**\n\n'
        '**Assert**\n\n'
        '- Ok.\n\n'
        '## Case\n\n'
        '**Task**\n\nRun.\n\n'
        '**Assert**\n\n- Ok.\n'
      ),
      'b.py': 'pass\n',
      'b.py.test.md': (
        '## Before H1\n\n'
        '**Task**\n\nRun.\n\n'
        '**Assert**\n\n'
        '### Sub heading\n\n'
        '- Nested list item\n\n'
        '# Tests\n\n'
        '##   \n\n'
        '> **Task**\n'
        '> **Assert**\n\n'
        '- **Task**\n'
        '- **Assert**\n\n'
        '## Nested empty sublist\n\n'
        '**Task**\n\nRun.\n\n'
        '**Assert**\n\n'
        '- \n  - \n'
        '- ![image only alt](img.png)\n'
      ),
    }
  )
  assert wrong_h1_dup_h2_empty_task_and_nested_headings == (
    doc_lint.Diagnostic(
      'a.py.test.md',
      1,
      'MD005',
      'test companion headings must not be nested inside blockquotes '
      'or lists',
    ),
    doc_lint.Diagnostic(
      'a.py.test.md',
      1,
      'MD005',
      "test companion must have exactly one H1 named 'Tests'",
    ),
    doc_lint.Diagnostic(
      'a.py.test.md',
      3,
      'MD005',
      'test companion headings must not be nested inside blockquotes '
      'or lists',
    ),
    doc_lint.Diagnostic(
      'a.py.test.md', 5, 'MD005', 'test Task must not be empty'
    ),
    doc_lint.Diagnostic(
      'a.py.test.md', 5, 'MD005', "test name 'Case' is duplicated"
    ),
    doc_lint.Diagnostic(
      'a.py.test.md',
      13,
      'MD001',
      "heading identifier 'case' is duplicated; first used at line 5",
    ),
    doc_lint.Diagnostic(
      'b.py.test.md',
      1,
      'MD005',
      'test Assert must contain a non-empty list',
    ),
    doc_lint.Diagnostic(
      'b.py.test.md',
      1,
      'MD005',
      "test companion H1 'Tests' must precede all test sections",
    ),
    doc_lint.Diagnostic(
      'b.py.test.md',
      1,
      'MD005',
      'test companion may contain only H1 and H2 headings',
    ),
    doc_lint.Diagnostic(
      'b.py.test.md',
      15,
      'MD005',
      "each test must contain one '**Task**' followed by one '**Assert**'",
    ),
    doc_lint.Diagnostic(
      'b.py.test.md', 15, 'MD005', 'test name must not be empty'
    ),
  )


def test_lint_sources_reports_unreadable_entries_without_aborting() -> (
  None
):
  decode_error = UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid')
  diagnostics = doc_lint.lint_sources(
    {
      'README.md': decode_error,
      'guide.md': '# Guide\n# Guide\n',
      'module.py': 'def build(): pass\n',
      'module.py.test.md': OSError('permission denied'),
    }
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'README.md',
      1,
      'MD000',
      f'cannot parse Markdown file: {decode_error}',
    ),
    doc_lint.Diagnostic(
      'guide.md',
      2,
      'MD001',
      "heading identifier 'guide' is duplicated; first used at line 1",
    ),
    doc_lint.Diagnostic(
      'module.py.test.md',
      1,
      'MD000',
      'cannot parse Markdown file: permission denied',
    ),
  )


def test_git_inventory_skips_extra_stat_on_regular_files_and_wraps_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def fail_resolve(self: Path, strict: bool = False) -> Path:
    del strict
    raise OSError('bad root')

  monkeypatch.setattr(Path, 'resolve', fail_resolve)
  with pytest.raises(RuntimeError) as inv_err:
    doc_lint.git_inventory(Path('.'))
  assert str(inv_err.value) == 'Cannot scan repository with git: bad root'
  with pytest.raises(RuntimeError) as lint_err:
    doc_lint.lint_repository('.')
  assert str(lint_err.value) == 'Cannot scan repository with git: bad root'
  monkeypatch.undo()

  def ok_run(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'], 0, stdout=b'README.md\0', stderr=b''
    )

  monkeypatch.setattr(subprocess, 'run', ok_run)
  monkeypatch.setattr(
    Path,
    'lstat',
    lambda _self: os.stat_result(
      (stat.S_IFREG | 0o644, 1, 1, 1, 0, 0, 0, 0, 0, 0)
    ),
  )
  monkeypatch.setattr(
    Path,
    'stat',
    lambda self: (_ for _ in ()).throw(
      AssertionError(f'unexpected stat({self})')
    ),
  )
  assert doc_lint.git_inventory(Path('/virtual/repo')) == (
    Path('README.md'),
  )

  def fail_lstat(self: Path) -> os.stat_result:
    raise PermissionError('stat failed')

  monkeypatch.setattr(Path, 'lstat', fail_lstat)
  with pytest.raises(RuntimeError) as stat_err:
    doc_lint.git_inventory(Path('.'))
  assert str(stat_err.value) == (
    'Cannot scan repository with git: stat failed'
  )

  def nonzero_run(
    *args: object, **kwargs: object
  ) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
      ['git'], 1, stdout=b'', stderr=b'  git error  '
    )

  monkeypatch.setattr(subprocess, 'run', nonzero_run)
  with pytest.raises(RuntimeError) as nonzero_err:
    doc_lint.git_inventory(Path('.'))
  assert str(nonzero_err.value) == (
    'Cannot scan repository with git: git error'
  )


def test_lint_repository_and_check_documentation_virtualized(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  root = Path('/virtual/repo')
  files: dict[str, str | Exception] = {
    'README.md': '# Docs\n\n[Missing](missing.md)\n[Dir](linkdir)\n',
    'broken.md': UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'bad byte'),
  }
  dirs = {'linkdir'}

  monkeypatch.setattr(Path, 'resolve', lambda self, strict=False: root)
  monkeypatch.setattr(
    doc_lint,
    '_git_inventory_resolved',
    lambda _root: tuple(Path(name) for name in files),
  )

  def fake_read_text(self: Path, encoding: str = 'utf-8') -> str:
    assert encoding == 'utf-8'
    rel = self.relative_to(root).as_posix()
    entry = files[rel]
    if isinstance(entry, Exception):
      raise entry
    return entry

  def fake_is_dir(self: Path) -> bool:
    return self.relative_to(root).as_posix() in dirs

  monkeypatch.setattr(Path, 'read_text', fake_read_text)
  monkeypatch.setattr(Path, 'is_dir', fake_is_dir)

  with pytest.raises(doc_lint.DocumentationLintError) as exc_info:
    doc_lint.check_documentation(root)

  expected_diagnostics = (
    doc_lint.Diagnostic(
      'README.md',
      1,
      'MD004',
      "direct child 'broken.md' must be linked from exactly one H2 "
      'section; found 0',
    ),
    doc_lint.Diagnostic(
      'README.md',
      3,
      'MD002',
      "local link target 'missing.md' is not an inventoried file",
    ),
    doc_lint.Diagnostic(
      'README.md', 4, 'MD002', 'local link target is a directory'
    ),
    doc_lint.Diagnostic(
      'broken.md',
      1,
      'MD000',
      "cannot parse Markdown file: 'utf-8' codec can't decode byte "
      '0xff in position 0: bad byte',
    ),
  )
  assert exc_info.value.diagnostics == expected_diagnostics
  assert (
    str(expected_diagnostics[1])
    == "README.md:3: MD002: local link target 'missing.md' is not an "
    'inventoried file'
  )
  assert str(exc_info.value) == (
    'Documentation lint violations:\n'
    + '\n'.join(f'  - {d}' for d in expected_diagnostics)
  )

  files = {'README.md': '# Docs\n'}
  doc_lint.check_documentation(root)

  files = {'README.md': '# Docs\n\n[Sub](linkdir/)\n'}

  def fail_is_dir(self: Path) -> bool:
    raise OSError('dir probe failed')

  monkeypatch.setattr(Path, 'is_dir', fail_is_dir)
  with pytest.raises(RuntimeError) as dir_err:
    doc_lint.lint_repository(root)
  assert str(dir_err.value) == (
    'Cannot inspect documentation link target: dir probe failed'
  )


def test_git_inventory_cli_filters_ignored_symlinks_and_outside_targets(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  def git(repo: Path, *args: str) -> None:
    subprocess.run(
      [
        'git',
        '-C',
        str(repo),
        '-c',
        'user.name=Test',
        '-c',
        'user.email=test@example.invalid',
        '-c',
        'commit.gpgsign=false',
        *args,
      ],
      check=True,
      capture_output=True,
      text=True,
    )

  repo = tmp_path / 'repo'
  repo.mkdir()
  outside = tmp_path / 'outside.md'
  outside.write_text('# Outside\n', encoding='utf-8')
  target_dir = repo / 'subdir'
  target_dir.mkdir()
  (target_dir / 'inside.md').write_text('# Inside\n', encoding='utf-8')

  with monkeypatch.context() as env:
    for key in list(os.environ):
      if key.startswith('GIT_'):
        env.delenv(key, raising=False)
    env.setenv('HOME', str(tmp_path))
    env.setenv('XDG_CONFIG_HOME', str(tmp_path))
    env.setenv('GIT_CONFIG_GLOBAL', '/dev/null')
    env.setenv('GIT_CONFIG_NOSYSTEM', '1')

    git(repo, 'init', '-q')
    non_utf8 = os.fsdecode(b'non-utf8-\xff.txt')
    (repo / '.gitignore').write_text('ignored.md\n', encoding='utf-8')
    (repo / 'tracked.md').write_text('# Tracked\n', encoding='utf-8')
    (repo / 'deleted.md').write_text('# Deleted\n', encoding='utf-8')
    (repo / 'visible.md').write_text('# Visible\n', encoding='utf-8')
    (repo / 'ignored.md').write_text('# Ignored\n', encoding='utf-8')
    (repo / non_utf8).write_text('bytes\n', encoding='utf-8')
    (repo / 'dirlink').symlink_to(target_dir)
    (repo / 'outlink.md').symlink_to(outside)
    git(repo, 'add', '.gitignore', 'tracked.md', 'deleted.md')
    (repo / 'deleted.md').unlink()

    assert doc_lint.git_inventory(repo) == (
      Path('.gitignore'),
      Path(non_utf8),
      Path('subdir/inside.md'),
      Path('tracked.md'),
      Path('visible.md'),
    )
