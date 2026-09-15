from __future__ import annotations

import html
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from markdown_it import MarkdownIt

_URI_SCHEME = re.compile(r'^[A-Za-z][A-Za-z0-9+.-]*:')
_HTML_TAG = re.compile(r'<[^>]*>')


@dataclass(frozen=True, order=True)
class Diagnostic:
  path: str
  line: int
  code: str
  message: str

  def __str__(self):
    return f'{self.path}:{self.line}: {self.code}: {self.message}'


class DocumentationLintError(RuntimeError):
  def __init__(self, diagnostics):
    self.diagnostics = tuple(diagnostics)
    details = '\n'.join(
      f'  - {diagnostic}' for diagnostic in self.diagnostics
    )
    super().__init__('Documentation lint violations:\n' + details)


@dataclass
class Heading:
  level: int
  line: int
  text: str
  identifier: str


@dataclass
class Link:
  line: int
  text: str
  href: str
  target_path: str | None = None
  target_fragment: str | None = None
  has_query: bool = False


@dataclass
class Document:
  path: str
  source: str
  tokens: list
  headings: list[Heading]
  links: list[Link]


class _LintState:
  def __init__(self, root, inventory):
    self.root = root
    self.inventory = tuple(sorted(inventory))
    self.inventory_set = {path.as_posix() for path in self.inventory}
    self.markdown_paths = tuple(
      path.as_posix() for path in self.inventory if path.suffix == '.md'
    )
    self.documents = {}
    self.diagnostics = []

  def add(self, path, line, code, message):
    self.diagnostics.append(Diagnostic(path, line, code, message))


def _git_inventory(repository_root):
  try:
    result = subprocess.run(
      [
        'git',
        'ls-files',
        '--cached',
        '--others',
        '--exclude-standard',
        '-z',
      ],
      cwd=repository_root,
      capture_output=True,
      check=False,
      text=True,
    )
  except OSError as error:
    raise RuntimeError(
      f'Cannot scan repository with git: {error}'
    ) from error

  if result.returncode != 0:
    detail = result.stderr.strip() or 'unknown git error'
    raise RuntimeError(f'Cannot scan repository with git: {detail}')

  return tuple(
    Path(path)
    for path in result.stdout.split('\0')
    if path and (repository_root / Path(path)).exists()
  )


def _visible_text(tokens):
  text = []
  for token in tokens or []:
    if token.type in {'text', 'code_inline'}:
      text.append(token.content)
    elif token.type in {'softbreak', 'hardbreak'}:
      text.append(' ')
    elif token.type == 'image':
      text.append(token.attrGet('alt') or '')
    elif token.type == 'html_inline':
      text.append(html.unescape(_HTML_TAG.sub('', token.content)))
  return ''.join(text)


def _heading_identifier(text):
  return ''.join(
    '-' if character.isspace() else character
    for character in text.lower()
    if character.isspace()
    or character.isalnum()
    or character in {'-', '_'}
  )


def _parse_document(path, source):
  parser = MarkdownIt('commonmark', {'html': True})
  tokens = parser.parse(source)
  headings = []
  links = []
  index = 0
  while index < len(tokens):
    token = tokens[index]
    if token.type == 'heading_open':
      inline = tokens[index + 1]
      text = _visible_text(inline.children)
      headings.append(
        Heading(
          int(token.tag[1:]),
          token.map[0] + 1,
          text,
          _heading_identifier(text),
        )
      )
      index += 3
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
        links.append(
          Link(
            token.map[0] + 1,
            _visible_text(children[child_index + 1 : close_index - 1]),
            child.attrGet('href') or '',
          )
        )
        child_index = close_index
        continue
    index += 1
  return Document(path, source, tokens, headings, links)


def _normalise_target_path(source_path, raw_path):
  if not raw_path:
    return source_path
  if raw_path.startswith('/'):
    return None
  source = PurePosixPath(source_path)
  parts = list(source.parent.parts)
  for part in PurePosixPath(raw_path).parts:
    if part in {'', '.'}:
      continue
    if part == '..':
      if not parts:
        return None
      parts.pop()
      continue
    parts.append(part)
  return '/'.join(parts)


def _link_target(source_path, href):
  raw_path, separator, raw_fragment = href.partition('#')
  if '?' in raw_path:
    return None, None, True, 'query'
  path = _normalise_target_path(source_path, unquote(raw_path))
  if path is None:
    return None, None, False, 'outside'
  fragment = unquote(raw_fragment) if separator and raw_fragment else None
  return path, fragment, False, None


def _check_headings(state):
  for path in sorted(state.documents):
    headings = state.documents[path].headings
    by_identifier = defaultdict(list)
    for heading in headings:
      by_identifier[heading.identifier].append(heading)
    for identifier, matches in sorted(by_identifier.items()):
      for heading in matches[1:]:
        state.add(
          path,
          heading.line,
          'MD001',
          (
            f"heading identifier '{identifier}' is duplicated; "
            f'first used at line {matches[0].line}'
          ),
        )


def _check_links(state):
  for path in sorted(state.documents):
    document = state.documents[path]
    headings = defaultdict(list)
    for heading in document.headings:
      headings[heading.identifier].append(heading)
    valid_links = defaultdict(list)
    for link in document.links:
      href = link.href
      if _URI_SCHEME.match(href) or href.startswith('//'):
        continue
      target_path, fragment, has_query, error = _link_target(path, href)
      link.target_path = target_path
      link.target_fragment = fragment
      link.has_query = has_query
      if error == 'query':
        state.add(
          path,
          link.line,
          'MD002',
          'local link destination contains a query string',
        )
        continue
      if error == 'outside':
        state.add(
          path,
          link.line,
          'MD002',
          'local link target is outside the repository',
        )
        continue
      target_fs_path = state.root / PurePosixPath(target_path)
      if target_fs_path.is_dir():
        state.add(
          path, link.line, 'MD002', 'local link target is a directory'
        )
        continue
      if target_path not in state.inventory_set:
        state.add(
          path,
          link.line,
          'MD002',
          f"local link target '{target_path}' is not an inventoried file",
        )
        continue
      if fragment is not None:
        matching_headings = (
          headings if target_path == path else defaultdict(list)
        )
        if target_path != path and target_path in state.documents:
          matching_headings = defaultdict(list)
          for heading in state.documents[target_path].headings:
            matching_headings[heading.identifier].append(heading)
        matches = matching_headings.get(fragment, [])
        if not matches:
          state.add(
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
          state.add(
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
    for target, links in sorted(valid_links.items()):
      first = links[0]
      for link in links[1:]:
        if link.text != first.text:
          state.add(
            path,
            link.line,
            'MD003',
            (
              f"local links to '{target[0]}' use different visible text "
              f'from line {first.line}'
            ),
          )


def _is_companion(path):
  return path.endswith('.test.md')


def _companion_subject_candidates(path):
  base_path = path.removesuffix('.test.md')
  candidates = [base_path + '.md']
  if not base_path.endswith('.md'):
    candidates.append(base_path)
  return tuple(candidates)


def _direct_children(state, readme_path):
  readme = PurePosixPath(readme_path)
  parent = readme.parent
  children = {
    path
    for path in state.markdown_paths
    if not _is_companion(path)
    and PurePosixPath(path).parent == parent
    and path != readme_path
  }
  children.update(
    path
    for path in state.markdown_paths
    if path.endswith('/README.md')
    and not _is_companion(path)
    and PurePosixPath(path).parent.parent == parent
  )
  return tuple(sorted(children))


def _check_indexes(state):
  noncompanions = tuple(
    path for path in state.markdown_paths if not _is_companion(path)
  )
  for path in noncompanions:
    parent = PurePosixPath(path).parent
    readme_path = (parent / 'README.md').as_posix()
    if readme_path not in state.inventory_set:
      state.add(
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
    children = _direct_children(state, readme_path)
    if not children:
      continue
    document = state.documents[readme_path]
    sections = []
    h2s = [heading for heading in document.headings if heading.level == 2]
    for index, heading in enumerate(h2s):
      next_heading_line = len(document.source.splitlines()) + 1
      for candidate in document.headings:
        if candidate.line > heading.line and candidate.level <= 2:
          next_heading_line = min(next_heading_line, candidate.line)
      sections.append(
        (
          heading,
          [
            link
            for link in document.links
            if heading.line <= link.line < next_heading_line
          ],
        )
      )
    child_set = set(children)
    child_links_by_section = {}
    for heading, links in sections:
      child_links = [
        link
        for link in links
        if link.target_path in child_set
        and not link.has_query
        and link.target_fragment is None
      ]
      child_links_by_section[heading.line] = child_links
      if len(child_links) != 1:
        state.add(
          readme_path,
          heading.line,
          'MD004',
          (
            'H2 section must link to exactly one direct child; '
            f'found {len(child_links)}'
          ),
        )
    child_sections = defaultdict(list)
    for heading, links in sections:
      for link in child_links_by_section[heading.line]:
        child_sections[link.target_path].append((heading, link))
    for child in children:
      matches = child_sections.get(child, [])
      if len(matches) != 1:
        state.add(
          readme_path,
          1,
          'MD004',
          (
            f"direct child '{child}' must be linked from exactly one H2 "
            f'section; found {len(matches)}'
          ),
        )


def _strong_label(inline_token, label):
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


def _test_sections(document):
  tokens = document.tokens
  h2_indexes = [
    index
    for index, token in enumerate(tokens)
    if token.type == 'heading_open' and token.tag == 'h2'
  ]
  sections = []
  for index, start in enumerate(h2_indexes):
    end = (
      h2_indexes[index + 1] if index + 1 < len(h2_indexes) else len(tokens)
    )
    sections.append((start, end))
  return sections


def _check_companions(state):
  for path in state.markdown_paths:
    if not _is_companion(path):
      continue
    candidates = _companion_subject_candidates(path)
    source_paths = tuple(
      candidate
      for candidate in candidates
      if candidate in state.inventory_set
    )
    line = 1
    if any(_is_companion(source_path) for source_path in source_paths):
      state.add(
        path,
        line,
        'MD005',
        'a test companion cannot have a test companion',
      )
      continue
    if not source_paths:
      state.add(
        path,
        line,
        'MD005',
        'test companion subject is not an inventoried file; expected '
        + ' or '.join(f"'{candidate}'" for candidate in candidates),
      )
      continue
    if len(source_paths) > 1:
      state.add(
        path,
        line,
        'MD005',
        'test companion subject is ambiguous between '
        + ' and '.join(f"'{source_path}'" for source_path in source_paths),
      )
      continue
    document = state.documents[path]
    tokens = document.tokens
    h1s = [heading for heading in document.headings if heading.level == 1]
    if len(h1s) != 1 or h1s[0].text != 'Tests':
      state.add(
        path,
        line,
        'MD005',
        "test companion must have exactly one H1 named 'Tests'",
      )
    if any(heading.level not in {1, 2} for heading in document.headings):
      state.add(
        path,
        line,
        'MD005',
        'test companion may contain only H1 and H2 headings',
      )
    h2s = [heading for heading in document.headings if heading.level == 2]
    names = [heading.text for heading in h2s]
    for name in sorted({name for name in names if names.count(name) > 1}):
      heading = next(heading for heading in h2s if heading.text == name)
      state.add(
        path, heading.line, 'MD005', f"test name '{name}' is duplicated"
      )
    sections = _test_sections(document)
    for start, end in sections:
      heading_line = tokens[start].map[0] + 1
      labels = []
      for token_index in range(start + 2, end):
        token = tokens[token_index]
        if token.type == 'inline' and token.children:
          if _strong_label(token, 'Task'):
            labels.append(('Task', token_index))
          elif _strong_label(token, 'Assert'):
            labels.append(('Assert', token_index))
      if [label for label, _ in labels] != ['Task', 'Assert']:
        state.add(
          path,
          heading_line,
          'MD005',
          "each test must contain one '**Task**' followed by one "
          "'**Assert**'",
        )
        continue
      task_index = labels[0][1]
      assert_index = labels[1][1]
      task_content = tokens[task_index + 1 : assert_index]
      if not _has_content(task_content):
        state.add(
          path, heading_line, 'MD005', 'test Task must not be empty'
        )
      assert_content = tokens[assert_index + 1 : end]
      if not _has_nonempty_list(assert_content):
        state.add(
          path,
          heading_line,
          'MD005',
          'test Assert must contain a non-empty list',
        )


def _has_content(tokens):
  for token in tokens:
    if token.type in {'fence', 'code_block'} and token.content.strip():
      return True
    if token.type == 'inline' and _visible_text(token.children).strip():
      return True
  return False


def _has_nonempty_list(tokens):
  in_list = False
  for token in tokens:
    if token.type in {'bullet_list_open', 'ordered_list_open'}:
      in_list = True
      continue
    if (
      in_list
      and token.type == 'inline'
      and _visible_text(token.children).strip()
    ):
      return True
    if in_list and token.type in {
      'bullet_list_close',
      'ordered_list_close',
    }:
      in_list = False
  return False


def lint_repository(repository_root):
  root = Path(repository_root).resolve()
  inventory = _git_inventory(root)
  state = _LintState(root, inventory)
  for path in state.markdown_paths:
    full_path = root / PurePosixPath(path)
    try:
      source = full_path.read_text(encoding='utf-8')
      state.documents[path] = _parse_document(path, source)
    except (OSError, UnicodeError) as error:
      state.add(path, 1, 'MD000', f'cannot parse Markdown file: {error}')
  _check_headings(state)
  _check_links(state)
  _check_indexes(state)
  _check_companions(state)
  return tuple(sorted(state.diagnostics))


def check_documentation(repository_root):
  diagnostics = lint_repository(repository_root)
  if diagnostics:
    raise DocumentationLintError(diagnostics)
