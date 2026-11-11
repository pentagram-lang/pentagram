import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from zero import doc_lint
from zero.test_support import isolate_git_environment


def _lint_sources(
  root: Path,
  monkeypatch: pytest.MonkeyPatch,
  sources: Mapping[str, str],
) -> tuple[doc_lint.Diagnostic, ...]:
  for name, content in sources.items():
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
  inventory = tuple(Path(name) for name in sources)
  monkeypatch.setattr(doc_lint, '_git_inventory', lambda _root: inventory)
  return doc_lint.lint_repository(root)


def test_parser_extracts_visible_heading_and_link_data() -> None:
  document = doc_lint._parse_document(
    'README.md', '# Guide\n\n[read `the guide`](guide.md#overview)\n'
  )

  assert document.headings == [doc_lint.Heading(1, 1, 'Guide', 'guide')]
  assert document.links == [
    doc_lint.Link(3, 'read the guide', 'guide.md#overview')
  ]


def test_lint_accepts_indexed_links_to_a_unique_heading(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': (
        '# Docs\n\n[Details](guide.md#details)\n\n'
        '## Guide\n\n[Guide](guide.md)\n'
      ),
      'guide.md': '# Guide\n\n## Details\n',
    },
  )

  assert diagnostics == ()


def test_lint_reports_duplicate_heading_query_and_missing_target(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': (
        '# Index\n\n## Guide\n\n[Guide](guide.md?mode=1)\n\n'
        '[Missing](missing.md)\n'
      ),
      'guide.md': '# Guide\n# Guide\n',
    },
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'README.md',
      1,
      'MD004',
      (
        "direct child 'guide.md' must be linked from exactly one H2 "
        'section; found 0'
      ),
    ),
    doc_lint.Diagnostic(
      'README.md',
      3,
      'MD004',
      'H2 section must link to exactly one direct child; found 0',
    ),
    doc_lint.Diagnostic(
      'README.md',
      5,
      'MD002',
      'local link destination contains a query string',
    ),
    doc_lint.Diagnostic(
      'README.md',
      7,
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


@pytest.mark.parametrize(
  ('source', 'line'),
  [
    (
      '# Docs\n\nIntro on the first line.\n[Missing](missing.md)\n',
      4,
    ),
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
def test_lint_reports_multiline_links_at_their_source_line(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  source: str,
  line: int,
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {'README.md': source},
  )

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
  ],
  ids=('wrong-case-path', 'directory-target'),
)
def test_lint_rejects_wrong_case_and_directory_link_targets(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  href: str,
  message: str,
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': (
        '# Docs\n\n## Guide\n\n[Guide](guide/README.md)\n\n'
        f'[Invalid]({href})\n'
      ),
      'guide/README.md': '# Guide\n',
    },
  )

  assert diagnostics == (
    doc_lint.Diagnostic('README.md', 7, 'MD002', message),
  )


def test_lint_diagnostics_do_not_depend_on_inventory_order(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  sources = {
    'README.md': '# Docs\n\n[Missing](missing.md)\n',
    'guide.md': '# Guide\n# Guide\n',
  }
  first = _lint_sources(tmp_path, monkeypatch, sources)
  reversed_inventory = tuple(Path(name) for name in reversed(sources))
  monkeypatch.setattr(
    doc_lint, '_git_inventory', lambda _root: reversed_inventory
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
  assert doc_lint.lint_repository(tmp_path) == expected


def test_lint_reports_ambiguous_missing_and_misnamed_link_targets(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
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
    },
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


def test_lint_accepts_case_variation_for_repeat_links_and_external_markup(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
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
        '**Assert**\n\n- The result is 1.\n'
      ),
    },
  )

  assert diagnostics == ()


def test_lint_requires_directory_indexes_to_link_each_direct_child(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': (
        '# Docs\n\n## Guide\n\n[Guide](guide.md)\n\n'
        '## Nested\n\n[Nested](nested/README.md)\n'
      ),
      'guide.md': '# Guide\n',
      'nested/README.md': '# Nested\n\n## Detail\n',
      'nested/detail.md': '# Detail\n',
      'orphan/guide.md': '# Orphan\n',
    },
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


@pytest.mark.parametrize(
  ('task', 'assertion', 'message'),
  [
    ('', '- The result is 1.\n', 'test Task must not be empty'),
    ('Run build.\n', '', 'test Assert must contain a non-empty list'),
  ],
  ids=('empty-task', 'empty-assertion'),
)
def test_lint_rejects_test_companions_with_empty_task_or_assertion(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
  task: str,
  assertion: str,
  message: str,
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': '# Project\n',
      'project.py': 'def build():\n  return 1\n',
      'project.py.test.md': (
        '# Tests\n\n## Build result\n\n**Task**\n\n'
        f'{task}\n**Assert**\n\n{assertion}'
      ),
    },
  )

  assert diagnostics == (
    doc_lint.Diagnostic('project.py.test.md', 3, 'MD005', message),
  )


def test_lint_rejects_ambiguous_test_companion_subject(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': '# Docs\n\n## Module\n\n[Module](module.py.md)\n',
      'module.py': 'def build():\n  return 1\n',
      'module.py.md': '# Module\n',
      'module.py.test.md': '# Tests\n',
    },
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'module.py.test.md',
      1,
      'MD005',
      'test companion subject is ambiguous between '
      "'module.py.md' and 'module.py'",
    ),
  )


@pytest.mark.parametrize(
  ('source_path', 'href', 'expected'),
  [
    (
      'docs/README.md',
      '../guide.md#details',
      ('guide.md', 'details', False, None),
    ),
    ('README.md', '#local', ('README.md', 'local', False, None)),
    ('README.md', '../../outside.md', (None, None, False, 'outside')),
    ('README.md', 'guide.md?mode=full', (None, None, True, 'query')),
  ],
  ids=('relative-fragment', 'same-file-fragment', 'outside-root', 'query'),
)
def test_link_targets_normalize_paths_without_escape(
  source_path: str,
  href: str,
  expected: tuple[str | None, str | None, bool, str | None],
) -> None:
  assert doc_lint._link_target(source_path, href) == expected


def test_lint_requires_a_valid_test_companion_contract(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': '# Project\n',
      'project.py': 'def build():\n  return 1\n',
      'project.py.test.md': (
        '# Tests\n\n## Build result\n\n**Task**\n\nRun build.\n\n'
        '**Assert**\n\n- The result is 1.\n'
      ),
    },
  )

  assert diagnostics == ()


def test_lint_rejects_test_companion_without_a_task(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  diagnostics = _lint_sources(
    tmp_path,
    monkeypatch,
    {
      'README.md': '# Project\n',
      'project.py': 'def build():\n  return 1\n',
      'project.py.test.md': (
        '# Tests\n\n## Build result\n\n**Task**\n\n**Assert**\n\n'
        '- The result is 1.\n'
      ),
    },
  )

  assert diagnostics == (
    doc_lint.Diagnostic(
      'project.py.test.md',
      3,
      'MD005',
      'test Task must not be empty',
    ),
  )


def test_lint_reports_unreadable_documents_without_aborting_later_checks(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  (tmp_path / 'README.md').write_bytes(b'\xff')
  (tmp_path / 'guide.md').write_text('# Guide\n', encoding='utf-8')
  (tmp_path / 'module.py').write_text(
    'def build(): pass\n', encoding='utf-8'
  )
  (tmp_path / 'module.py.test.md').write_bytes(b'\xff')
  monkeypatch.setattr(
    doc_lint,
    '_git_inventory',
    lambda _root: tuple(
      Path(name)
      for name in (
        'README.md',
        'guide.md',
        'module.py',
        'module.py.test.md',
      )
    ),
  )

  diagnostics = doc_lint.lint_repository(tmp_path)

  assert diagnostics == (
    doc_lint.Diagnostic(
      'README.md',
      1,
      'MD000',
      "cannot parse Markdown file: 'utf-8' codec can't decode byte "
      '0xff in position 0: invalid start byte',
    ),
    doc_lint.Diagnostic(
      'module.py.test.md',
      1,
      'MD000',
      "cannot parse Markdown file: 'utf-8' codec can't decode byte "
      '0xff in position 0: invalid start byte',
    ),
  )


def test_git_inventory_preserves_non_utf8_filenames(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  isolate_git_environment(monkeypatch, tmp_path)
  subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
  name = os.fsdecode(b'non-utf8-\xff.txt')
  (tmp_path / name).write_text('content\n', encoding='utf-8')

  assert doc_lint._git_inventory(tmp_path) == (Path(name),)


def test_git_inventory_excludes_ignored_untracked_files(
  tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  isolate_git_environment(monkeypatch, tmp_path)
  (tmp_path / '.gitignore').write_text('ignored.md\n', encoding='utf-8')
  (tmp_path / 'tracked.md').write_text('# Tracked\n', encoding='utf-8')
  (tmp_path / 'visible.md').write_text('# Visible\n', encoding='utf-8')
  (tmp_path / 'ignored.md').write_text('# Ignored\n', encoding='utf-8')
  subprocess.run(['git', 'init', '-q'], cwd=tmp_path, check=True)
  subprocess.run(
    ['git', 'add', '.gitignore', 'tracked.md'], cwd=tmp_path, check=True
  )

  assert set(doc_lint._git_inventory(tmp_path)) == {
    Path('.gitignore'),
    Path('tracked.md'),
    Path('visible.md'),
  }
