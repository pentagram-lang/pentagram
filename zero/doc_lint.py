from __future__ import annotations

import html
import re
import stat
from collections import defaultdict
from collections.abc import (
  Callable,
  Iterable,
  Mapping,
  Sequence,
)
from collections.abc import (
  Set as AbstractSet,
)
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.rules_inline import autolink as _markdown_autolink
from markdown_it.rules_inline import link as _markdown_link
from markdown_it.rules_inline.state_inline import StateInline
from markdown_it.token import Token

from zero.lib import git_ls_files

_URI_SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
_HTML_TAG = re.compile(r'<[^>]*>')


@dataclass(frozen=True, slots=True, order=True)
class Diagnostic:
  path: str
  line: int
  code: str
  message: str

  def __str__(self) -> str:
    return f'{self.path}:{self.line}: {self.code}: {self.message}'


class DocumentationLintError(RuntimeError):
  def __init__(self, diagnostics: Sequence[Diagnostic]) -> None:
    self.diagnostics = tuple(diagnostics)
    details = '\n'.join(
      f'  - {diagnostic}' for diagnostic in self.diagnostics
    )
    super().__init__('Documentation lint violations:\n' + details)


@dataclass(frozen=True, slots=True)
class Heading:
  level: int
  line: int
  text: str
  identifier: str
  is_top_level: bool = True


@dataclass(frozen=True, slots=True)
class ResolvedLink:
  path: str
  fragment: str | None = None
  is_directory: bool = False
  traversal_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InvalidLink:
  reason: Literal['empty', 'query', 'outside']


type LinkTarget = ResolvedLink | InvalidLink


@dataclass(frozen=True, slots=True)
class Link:
  line: int
  text: str
  href: str
  target: LinkTarget | None = None


@dataclass(frozen=True, slots=True)
class CompanionSection:
  line: int
  labels: tuple[str, ...]
  has_task_content: bool
  has_nonempty_assert_list: bool


@dataclass(frozen=True, slots=True)
class Document:
  path: str
  line_count: int
  headings: tuple[Heading, ...]
  links: tuple[Link, ...]
  test_sections: tuple[CompanionSection, ...] = ()


@dataclass
class _LintState:
  inventory: tuple[str, ...]
  inventory_set: frozenset[str]
  directory_set: frozenset[str]
  markdown_paths: tuple[str, ...]
  documents: dict[str, Document]
  heading_index: dict[str, dict[str, tuple[Heading, ...]]]
  diagnostics: list[Diagnostic]


def _inferred_directories(
  inventory: Iterable[str],
  directories: AbstractSet[str],
) -> frozenset[str]:
  inferred: set[str] = {''}
  for item in inventory:
    for parent in PurePosixPath(item).parents:
      if parent != PurePosixPath('.'):
        inferred.add(parent.as_posix())
  for directory in directories:
    normalized = PurePosixPath(directory).as_posix()
    inferred.add('' if normalized == '.' else normalized)
  return frozenset(inferred)


def _build_heading_index(
  documents: Mapping[str, Document],
) -> dict[str, dict[str, tuple[Heading, ...]]]:
  index: dict[str, dict[str, tuple[Heading, ...]]] = {}
  for path, document in documents.items():
    grouped: dict[str, list[Heading]] = defaultdict(list)
    for heading in document.headings:
      grouped[heading.identifier].append(heading)
    index[path] = {
      identifier: tuple(matches) for identifier, matches in grouped.items()
    }
  return index


def _new_lint_state(
  ordered_inventory: tuple[str, ...],
  documents: dict[str, Document],
  diagnostics: list[Diagnostic],
  *,
  directories: AbstractSet[str] = frozenset(),
) -> _LintState:
  return _LintState(
    ordered_inventory,
    frozenset(ordered_inventory),
    _inferred_directories(ordered_inventory, directories),
    tuple(
      path
      for path in ordered_inventory
      if PurePosixPath(path).suffix == '.md'
    ),
    documents,
    _build_heading_index(documents),
    diagnostics,
  )


def _add_diagnostic(
  state: _LintState, path: str, line: int, code: str, message: str
) -> None:
  state.diagnostics.append(Diagnostic(path, line, code, message))


def _git_inventory_resolved(root: Path) -> tuple[Path, ...]:
  raw_paths = git_ls_files(
    root, error_prefix='Cannot scan repository with git'
  )
  kept: list[Path] = []
  try:
    for path in raw_paths:
      full_path = root / path
      try:
        lst = full_path.lstat()
      except (FileNotFoundError, NotADirectoryError):
        continue
      if stat.S_ISREG(lst.st_mode):
        kept.append(path)
        continue
      if not stat.S_ISLNK(lst.st_mode):
        continue
      try:
        st = full_path.stat()
      except (FileNotFoundError, NotADirectoryError):
        continue
      if not stat.S_ISREG(st.st_mode):
        continue
      try:
        resolved = full_path.resolve(strict=True)
      except (FileNotFoundError, NotADirectoryError):
        continue
      if resolved == root or root in resolved.parents:
        kept.append(path)
  except OSError as error:
    raise RuntimeError(
      f'Cannot scan repository with git: {error}'
    ) from error
  return tuple(sorted(kept))


def git_inventory(repository_root: str | Path) -> tuple[Path, ...]:
  """List existing regular files in a Git repository within root."""
  try:
    root = Path(repository_root).resolve()
  except OSError as error:
    raise RuntimeError(
      f'Cannot scan repository with git: {error}'
    ) from error
  return _git_inventory_resolved(root)


def _visible_text(tokens: Sequence[Token] | None) -> str:
  text: list[str] = []
  for token in tokens or ():
    if token.type in {'text', 'code_inline'}:
      text.append(token.content)
    elif token.type in {'softbreak', 'hardbreak'}:
      text.append(' ')
    elif token.type == 'image':
      if token.children is not None:
        text.append(_visible_text(token.children))
      else:
        text.append(token.content)
    elif token.type == 'html_inline':
      text.append(html.unescape(_HTML_TAG.sub('', token.content)))
  return ''.join(text)


def _heading_identifier(text: str) -> str:
  return ''.join(
    '-' if character.isspace() else character
    for character in text.lower()
    if character.isspace()
    or character.isalnum()
    or character in {'-', '_'}
  )


def _token_line(path: str, token: Token) -> int:
  if token.map is None:
    raise RuntimeError(
      f'Markdown parser produced {token.type!r} without a source map '
      f'in {path}'
    )
  return token.map[0] + 1


def _inline_line_offset(path: str, token: Token) -> int:
  offset: object = token.meta.get('inline_line')
  if not isinstance(offset, int):
    raise RuntimeError(
      f'Markdown parser produced a link without a source offset in {path}'
    )
  return offset


def _link_rule_with_source_line(
  rule: Callable[[StateInline, bool], bool],
) -> Callable[[StateInline, bool], bool]:
  def link_rule(state: StateInline, silent: bool) -> bool:
    link_start = state.pos
    token_start = len(state.tokens)
    matched = rule(state, silent)
    if matched and not silent:
      line = state.src.count('\n', 0, link_start)
      for token in state.tokens[token_start:]:
        if token.type == 'link_open':
          token.meta['inline_line'] = line
          break
    return matched

  return link_rule


def _build_parser() -> MarkdownIt:
  parser = MarkdownIt('commonmark', {'html': True})
  parser.inline.ruler.at(
    'link', _link_rule_with_source_line(_markdown_link)
  )
  parser.inline.ruler.at(
    'autolink', _link_rule_with_source_line(_markdown_autolink)
  )
  return parser


_PARSER: Final[MarkdownIt] = _build_parser()


def _is_external_href(href: str) -> bool:
  return bool(_URI_SCHEME.match(href) or href.startswith('//'))


def _strong_label(inline_token: Token, label: str) -> bool:
  children = inline_token.children or []
  return (
    len(children) == 5
    and children[0].type == 'text'
    and children[0].content == ''
    and children[1].type == 'strong_open'
    and children[2].type == 'text'
    and children[2].content == label
    and children[3].type == 'strong_close'
    and children[4].type == 'text'
    and children[4].content == ''
  )


def _has_content(tokens: Sequence[Token]) -> bool:
  for token in tokens:
    if token.type in {'fence', 'code_block'} and token.content.strip():
      return True
    if token.type == 'inline' and _visible_text(token.children).strip():
      return True
  return False


def _has_nonempty_list(tokens: Sequence[Token]) -> bool:
  list_depth = 0
  for token in tokens:
    if token.type in {'bullet_list_open', 'ordered_list_open'}:
      list_depth += 1
      continue
    if token.type in {'bullet_list_close', 'ordered_list_close'}:
      list_depth = max(0, list_depth - 1)
      continue
    if (
      list_depth > 0
      and token.type == 'inline'
      and _visible_text(token.children).strip()
    ):
      return True
  return False


def _extract_companion_sections(
  path: str, tokens: Sequence[Token]
) -> tuple[CompanionSection, ...]:
  heading_indexes = [
    index
    for index, token in enumerate(tokens)
    if token.type == 'heading_open' and token.level == 0
  ]
  sections: list[CompanionSection] = []
  for pos, start in enumerate(heading_indexes):
    if tokens[start].tag != 'h2':
      continue
    end = (
      heading_indexes[pos + 1]
      if pos + 1 < len(heading_indexes)
      else len(tokens)
    )
    heading_line = _token_line(path, tokens[start])
    labels: list[tuple[str, int]] = []
    for token_index in range(start + 3, end):
      token = tokens[token_index]
      if (
        token.type == 'inline'
        and token.children
        and tokens[token_index - 1].type == 'paragraph_open'
        and tokens[token_index - 1].level == 0
      ):
        if _strong_label(token, 'Task'):
          labels.append(('Task', token_index))
        elif _strong_label(token, 'Assert'):
          labels.append(('Assert', token_index))

    label_names = tuple(label for label, _ in labels)
    has_task = False
    has_assert = False
    if label_names == ('Task', 'Assert'):
      task_index = labels[0][1]
      assert_index = labels[1][1]
      has_task = _has_content(tokens[task_index + 2 : assert_index])
      has_assert = _has_nonempty_list(tokens[assert_index + 2 : end])
    sections.append(
      CompanionSection(heading_line, label_names, has_task, has_assert)
    )
  return tuple(sections)


def parse_document(path: str, source: str) -> Document:
  """Parse a Markdown document into frozen structural summaries."""
  tokens = _PARSER.parse(source)
  headings: list[Heading] = []
  links: list[Link] = []
  index = 0
  while index < len(tokens):
    token = tokens[index]
    if token.type == 'heading_open':
      inline = tokens[index + 1]
      text = _visible_text(inline.children)
      headings.append(
        Heading(
          int(token.tag[1:]),
          _token_line(path, token),
          text,
          _heading_identifier(text),
          is_top_level=token.level == 0,
        )
      )
      index += 1
      continue
    if token.type == 'inline':
      children = token.children or []
      child_index = 0
      while child_index < len(children):
        child = children[child_index]
        if child.type != 'link_open':
          child_index += 1
          continue
        depth = 1
        close_index = child_index + 1
        while close_index < len(children) and depth:
          if children[close_index].type == 'link_open':
            depth += 1
          elif children[close_index].type == 'link_close':
            depth -= 1
          close_index += 1
        if depth:
          child_index += 1
          continue
        line = _token_line(path, token) + _inline_line_offset(path, child)
        href = child.attrGet('href') or ''
        target = (
          None if _is_external_href(href) else link_target(path, href)
        )
        links.append(
          Link(
            line,
            _visible_text(children[child_index + 1 : close_index - 1]),
            href,
            target,
          )
        )
        child_index = close_index
        continue
    index += 1

  test_sections = (
    _extract_companion_sections(path, tokens)
    if _is_companion(path)
    else ()
  )
  return Document(
    path=path,
    line_count=len(source.splitlines()),
    headings=tuple(headings),
    links=tuple(links),
    test_sections=test_sections,
  )


def _normalise_target_path(
  source_path: str, raw_path: str
) -> tuple[str | None, bool, tuple[str, ...]]:
  if raw_path.startswith('/'):
    return None, False, ()
  parts = list(PurePosixPath(source_path).parent.parts)
  raw_segments = raw_path.split('/')
  last_nonempty = raw_segments[-1]
  is_directory = raw_path.endswith('/') or last_nonempty in {'.', '..'}
  traversed: list[str] = []

  for segment in raw_segments:
    if segment == '':
      continue
    if segment == '.':
      if parts:
        traversed.append('/'.join(parts))
      continue
    if segment == '..':
      if not parts:
        return None, is_directory, tuple(dict.fromkeys(traversed))
      traversed.append('/'.join(parts))
      parts.pop()
      continue
    if parts:
      traversed.append('/'.join(parts))
    parts.append(segment)

  if raw_path.endswith('/') and parts:
    traversed.append('/'.join(parts))
  return '/'.join(parts), is_directory, tuple(dict.fromkeys(traversed))


def link_target(source_path: str, href: str) -> LinkTarget:
  """Resolve a local Markdown href against its source document path."""
  if href == '':
    return InvalidLink('empty')
  raw_path, separator, raw_fragment = href.partition('#')
  if '?' in raw_path:
    return InvalidLink('query')
  fragment = unquote(raw_fragment) if separator else None
  unquoted_path = unquote(raw_path)
  if unquoted_path == '':
    return ResolvedLink(path=source_path, fragment=fragment)
  normalized, is_directory, traversal_prefixes = _normalise_target_path(
    source_path, unquoted_path
  )
  if normalized is None:
    return InvalidLink('outside')
  return ResolvedLink(
    path=normalized,
    fragment=fragment,
    is_directory=is_directory,
    traversal_prefixes=traversal_prefixes,
  )


def _check_headings(state: _LintState) -> None:
  for path in sorted(state.documents):
    by_identifier = state.heading_index[path]
    for identifier, matches in sorted(by_identifier.items()):
      for heading in matches[1:]:
        _add_diagnostic(
          state,
          path,
          heading.line,
          'MD001',
          (
            f"heading identifier '{identifier}' is duplicated; "
            f'first used at line {matches[0].line}'
          ),
        )


def _check_links(state: _LintState) -> None:
  for path in sorted(state.documents):
    document = state.documents[path]
    valid_links: dict[tuple[str, str | None], list[Link]] = defaultdict(
      list
    )
    for link in document.links:
      target = link.target
      if target is None:
        continue
      if isinstance(target, InvalidLink):
        if target.reason == 'empty':
          message = 'local link destination is empty'
        elif target.reason == 'query':
          message = 'local link destination contains a query string'
        else:
          message = 'local link target is outside the repository'
        _add_diagnostic(state, path, link.line, 'MD002', message)
        continue
      file_prefix = next(
        (
          prefix
          for prefix in target.traversal_prefixes
          if prefix in state.inventory_set
        ),
        None,
      )
      if file_prefix is not None:
        _add_diagnostic(
          state,
          path,
          link.line,
          'MD002',
          (
            'local link path traverses through non-directory file '
            f"'{file_prefix}'"
          ),
        )
        continue
      target_path = target.path
      if target_path in state.directory_set:
        _add_diagnostic(
          state,
          path,
          link.line,
          'MD002',
          'local link target is a directory',
        )
        continue
      if target.is_directory or target_path not in state.inventory_set:
        display_target = (
          f'{target_path}/' if target.is_directory else target_path
        )
        _add_diagnostic(
          state,
          path,
          link.line,
          'MD002',
          f"local link target '{display_target}' is not an inventoried "
          'file',
        )
        continue
      fragment = target.fragment
      if fragment is not None:
        if fragment == '':
          _add_diagnostic(
            state,
            path,
            link.line,
            'MD002',
            f"local link fragment '#' does not identify a heading in "
            f"'{target_path}'",
          )
          continue
        matches = state.heading_index.get(target_path, {}).get(
          fragment, ()
        )
        if not matches:
          _add_diagnostic(
            state,
            path,
            link.line,
            'MD002',
            (
              f"local link fragment '#{fragment}' does not identify "
              f"a heading in '{target_path}'"
            ),
          )
          continue
        if len(matches) > 1:
          _add_diagnostic(
            state,
            path,
            link.line,
            'MD002',
            (
              f"local link fragment '#{fragment}' identifies multiple "
              f"headings in '{target_path}'"
            ),
          )
          continue
      valid_links[(target_path, fragment)].append(link)

    for (target_path, _), links in sorted(
      valid_links.items(), key=lambda item: (item[0][0], item[0][1] or '')
    ):
      first = links[0]
      for link in links[1:]:
        if link.text.casefold() != first.text.casefold():
          _add_diagnostic(
            state,
            path,
            link.line,
            'MD003',
            (
              f"local links to '{target_path}' use different visible text "
              f'from line {first.line}'
            ),
          )


def _is_companion(path: str) -> bool:
  return path.endswith('.test.md')


def _direct_children_by_directory(
  markdown_paths: Sequence[str],
) -> dict[PurePosixPath, tuple[str, ...]]:
  children_by_directory: dict[PurePosixPath, set[str]] = defaultdict(set)
  for path in markdown_paths:
    if _is_companion(path):
      continue
    child = PurePosixPath(path)
    if child.name == 'README.md':
      if child.parent != PurePosixPath('.'):
        children_by_directory[child.parent.parent].add(path)
    else:
      children_by_directory[child.parent].add(path)
  return {
    directory: tuple(sorted(children))
    for directory, children in children_by_directory.items()
  }


def _direct_child_target(
  link: Link,
  inventory_set: frozenset[str],
  child_set: AbstractSet[str],
) -> str | None:
  target = link.target
  if (
    not isinstance(target, ResolvedLink)
    or target.is_directory
    or target.fragment is not None
    or target.path not in child_set
    or any(prefix in inventory_set for prefix in target.traversal_prefixes)
  ):
    return None
  return target.path


def _check_indexes(state: _LintState) -> None:
  children_by_directory = _direct_children_by_directory(
    state.markdown_paths
  )
  noncompanions = tuple(
    path for path in state.markdown_paths if not _is_companion(path)
  )
  for path in noncompanions:
    parent = PurePosixPath(path).parent
    readme_path = (parent / 'README.md').as_posix()
    if readme_path not in state.inventory_set:
      _add_diagnostic(
        state,
        path,
        1,
        'MD004',
        (
          f"directory '{parent.as_posix()}' contains Markdown but has no "
          'README.md'
        ),
      )

  for readme_path in noncompanions:
    if PurePosixPath(readme_path).name != 'README.md':
      continue
    children = children_by_directory.get(
      PurePosixPath(readme_path).parent, ()
    )
    if not children:
      continue
    document = state.documents.get(readme_path)
    if document is None:
      continue

    h1_or_h2 = [h for h in document.headings if h.level <= 2]
    h2s = [h for h in h1_or_h2 if h.level == 2]
    child_set = set(children)
    child_h2_lines: dict[str, set[int]] = defaultdict(set)

    for heading in h2s:
      next_heading_line = document.line_count + 1
      for candidate in h1_or_h2:
        if candidate.line > heading.line:
          next_heading_line = candidate.line
          break
      child_targets = [
        target_path
        for link in document.links
        if heading.line <= link.line < next_heading_line
        for target_path in (
          _direct_child_target(link, state.inventory_set, child_set),
        )
        if target_path is not None
      ]
      for target_path in child_targets:
        child_h2_lines[target_path].add(heading.line)
      if len(child_targets) != 1:
        _add_diagnostic(
          state,
          readme_path,
          heading.line,
          'MD004',
          (
            'H2 section must link to exactly one direct child; '
            f'found {len(child_targets)}'
          ),
        )

    for child in children:
      section_count = len(child_h2_lines.get(child, ()))
      if section_count != 1:
        _add_diagnostic(
          state,
          readme_path,
          1,
          'MD004',
          (
            f"direct child '{child}' must be linked from exactly one H2 "
            f'section; found {section_count}'
          ),
        )


def _check_companions(state: _LintState) -> None:
  for path in state.markdown_paths:
    if not _is_companion(path):
      continue
    line = 1
    base_path = path.removesuffix('.test.md')
    if _is_companion(base_path):
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        'a test companion cannot have a test companion',
      )
      continue
    raw_candidates = [base_path + '.md']
    if not base_path.endswith('.md'):
      raw_candidates.append(base_path)
    if any(
      _is_companion(candidate) and candidate in state.inventory_set
      for candidate in raw_candidates
    ):
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        'a test companion cannot have a test companion',
      )
      continue

    candidates = tuple(
      candidate
      for candidate in raw_candidates
      if not _is_companion(candidate)
    )
    source_paths = tuple(
      candidate
      for candidate in candidates
      if candidate in state.inventory_set
    )
    if not source_paths:
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        'test companion subject is not an inventoried file; expected '
        + ' or '.join(f"'{candidate}'" for candidate in candidates),
      )
      continue
    if len(source_paths) > 1:
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        'test companion subject is ambiguous between '
        + ' and '.join(f"'{source_path}'" for source_path in source_paths),
      )
      continue

    document = state.documents.get(path)
    if document is None:
      continue

    for heading in document.headings:
      if not heading.is_top_level:
        _add_diagnostic(
          state,
          path,
          heading.line,
          'MD005',
          'test companion headings must not be nested inside blockquotes '
          'or lists',
        )

    h1s = [h for h in document.headings if h.is_top_level and h.level == 1]
    h2s = [h for h in document.headings if h.is_top_level and h.level == 2]
    if len(h1s) != 1 or h1s[0].text != 'Tests':
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        "test companion must have exactly one H1 named 'Tests'",
      )
    elif h2s and h2s[0].line < h1s[0].line:
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        "test companion H1 'Tests' must precede all test sections",
      )
    if any(
      h.is_top_level and h.level not in {1, 2} for h in document.headings
    ):
      _add_diagnostic(
        state,
        path,
        line,
        'MD005',
        'test companion may contain only H1 and H2 headings',
      )

    first_heading_by_name: dict[str, Heading] = {}
    duplicate_names: set[str] = set()
    for heading in h2s:
      if not heading.text.strip():
        _add_diagnostic(
          state, path, heading.line, 'MD005', 'test name must not be empty'
        )
        continue
      if heading.text in first_heading_by_name:
        duplicate_names.add(heading.text)
      else:
        first_heading_by_name[heading.text] = heading
    for name in sorted(duplicate_names):
      heading = first_heading_by_name[name]
      _add_diagnostic(
        state,
        path,
        heading.line,
        'MD005',
        f"test name '{name}' is duplicated",
      )

    for section in document.test_sections:
      if section.labels != ('Task', 'Assert'):
        _add_diagnostic(
          state,
          path,
          section.line,
          'MD005',
          "each test must contain one '**Task**' followed by one "
          "'**Assert**'",
        )
        continue
      if not section.has_task_content:
        _add_diagnostic(
          state,
          path,
          section.line,
          'MD005',
          'test Task must not be empty',
        )
      if not section.has_nonempty_assert_list:
        _add_diagnostic(
          state,
          path,
          section.line,
          'MD005',
          'test Assert must contain a non-empty list',
        )


def _parse_sources(
  sources: Mapping[str, str | OSError | UnicodeError],
  markdown_paths: Sequence[str],
) -> tuple[dict[str, Document], list[Diagnostic]]:
  documents: dict[str, Document] = {}
  diagnostics: list[Diagnostic] = []
  for path in markdown_paths:
    entry = sources.get(path)
    if entry is None:
      missing = FileNotFoundError(path)
      diagnostics.append(
        Diagnostic(
          path, 1, 'MD000', f'cannot parse Markdown file: {missing}'
        )
      )
    elif isinstance(entry, (OSError, UnicodeError)):
      diagnostics.append(
        Diagnostic(
          path, 1, 'MD000', f'cannot parse Markdown file: {entry}'
        )
      )
    else:
      documents[path] = parse_document(path, entry)
  return documents, diagnostics


def _lint_parsed(
  ordered_inventory: tuple[str, ...],
  documents: dict[str, Document],
  diagnostics: list[Diagnostic],
  *,
  directories: AbstractSet[str] = frozenset(),
) -> tuple[Diagnostic, ...]:
  state = _new_lint_state(
    ordered_inventory,
    documents,
    diagnostics,
    directories=directories,
  )
  _check_headings(state)
  _check_links(state)
  _check_indexes(state)
  _check_companions(state)
  return tuple(sorted(state.diagnostics))


def lint_sources(
  sources: Mapping[str, str | OSError | UnicodeError],
  *,
  inventory: Iterable[str] | None = None,
  directories: AbstractSet[str] = frozenset(),
) -> tuple[Diagnostic, ...]:
  """Lint Markdown sources and repository inventory entirely in memory."""
  ordered_inventory = tuple(
    sorted(set(sources) if inventory is None else set(inventory))
  )
  markdown_paths = tuple(
    path
    for path in ordered_inventory
    if PurePosixPath(path).suffix == '.md'
  )
  documents, diagnostics = _parse_sources(sources, markdown_paths)
  return _lint_parsed(
    ordered_inventory,
    documents,
    diagnostics,
    directories=directories,
  )


def lint_repository(
  repository_root: str | Path,
) -> tuple[Diagnostic, ...]:
  """Scan and lint all Markdown documentation in a Git repository."""
  try:
    root = Path(repository_root).resolve()
  except OSError as error:
    raise RuntimeError(
      f'Cannot scan repository with git: {error}'
    ) from error
  inventory_paths = _git_inventory_resolved(root)
  ordered_inventory = tuple(
    sorted(path.as_posix() for path in inventory_paths)
  )
  inventory_set = frozenset(ordered_inventory)
  markdown_paths = tuple(
    path
    for path in ordered_inventory
    if PurePosixPath(path).suffix == '.md'
  )
  sources: dict[str, str | OSError | UnicodeError] = {}
  for path in markdown_paths:
    full_path = root / PurePosixPath(path)
    try:
      sources[path] = full_path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as error:
      sources[path] = error
  documents, diagnostics = _parse_sources(sources, markdown_paths)
  try:
    disk_directories = frozenset(
      target.path
      for document in documents.values()
      for link in document.links
      for target in (link.target,)
      if isinstance(target, ResolvedLink)
      and target.path not in inventory_set
      and (root / PurePosixPath(target.path)).is_dir()
    )
  except OSError as error:
    raise RuntimeError(
      f'Cannot inspect documentation link target: {error}'
    ) from error
  return _lint_parsed(
    ordered_inventory,
    documents,
    diagnostics,
    directories=disk_directories,
  )


def check_documentation(repository_root: str | Path) -> None:
  """Raise DocumentationLintError when repository docs have violations."""
  diagnostics = lint_repository(repository_root)
  if diagnostics:
    raise DocumentationLintError(diagnostics)
