from __future__ import annotations

import posixpath
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from markdown_it import MarkdownIt
from markdown_it.token import Token

from zero.lib import Diagnostic, git_ls_files

EXTERNAL_LINK_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*:')


@dataclass(frozen=True, slots=True)
class _ParsedDoc:
  rel: str
  blocks: list[list[Token]]
  headings: list[tuple[str, str, str, int]]
  slugs: frozenset[str]
  links: list[tuple[str, str, int]]


def _inventoried_files(repo: Path) -> list[str]:
  root = repo.resolve()
  kept: list[str] = []
  for rel in git_ls_files(repo):
    p = repo / rel
    if not p.exists():
      continue
    resolved = p.resolve()
    if resolved.is_file() and resolved.is_relative_to(root):
      kept.append(rel)
  return kept


def _is_test_md_candidate(name: str) -> bool:
  return name.endswith('.md') and 'test' in name.lower()


def _md_companion_stem(name: str) -> str | None:
  parts = name.split('.')
  if len(parts) != 3 or parts[1] != 'test' or parts[2] != 'md':
    return None
  stem = parts[0]
  return stem if stem and 'test' not in stem.lower() else None


def _non_test_sibling(name: str) -> str | None:
  parts = name.split('.')
  if len(parts) != 2:
    return None
  stem, ext = parts
  if (
    not stem or not ext or 'test' in stem.lower() or 'test' in ext.lower()
  ):
    return None
  return stem


def _top_level_blocks(tokens: Sequence[Token]) -> list[list[Token]]:
  blocks: list[list[Token]] = []
  current: list[Token] = []
  depth = 0
  for tok in tokens:
    current.append(tok)
    depth += tok.nesting
    if depth == 0:
      blocks.append(current)
      current = []
  return blocks


def _block_line(block: Sequence[Token]) -> int:
  return block[0].map[0] + 1 if block[0].map is not None else 1


def _inline_text(token: Token) -> str:
  if not token.children:
    return token.content
  parts: list[str] = []
  for child in token.children:
    if child.type in ('text', 'code_inline'):
      parts.append(child.content)
    elif child.type in ('softbreak', 'hardbreak'):
      parts.append(' ')
  return ''.join(parts)


def _heading_slug(text: str) -> str:
  out: list[str] = []
  for ch in text.lower():
    if ch.isspace():
      out.append('-')
    elif ch.isalnum() or ch in ('-', '_'):
      out.append(ch)
  return ''.join(out)


def _extract_inline_links(token: Token) -> list[tuple[str, str]]:
  links: list[tuple[str, str]] = []
  children = token.children or []
  i = 0
  while i < len(children):
    if children[i].type == 'link_open':
      href_val = children[i].attrGet('href')
      href = href_val if isinstance(href_val, str) else ''
      parts: list[str] = []
      depth = 1
      i += 1
      while i < len(children) and depth > 0:
        c = children[i]
        if c.type == 'link_open':
          depth += 1
        elif c.type == 'link_close':
          depth -= 1
        elif c.type in ('text', 'code_inline'):
          parts.append(c.content)
        elif c.type in ('softbreak', 'hardbreak'):
          parts.append(' ')
        i += 1
      links.append((href, ''.join(parts)))
    else:
      i += 1
  return links


def _parse_doc(md: MarkdownIt, repo: Path, rel: str) -> _ParsedDoc:
  text = (repo / rel).read_text(encoding='utf-8')
  tokens = md.parse(text)
  blocks = _top_level_blocks(tokens)
  headings: list[tuple[str, str, str, int]] = []
  links: list[tuple[str, str, int]] = []
  for idx, tok in enumerate(tokens):
    if tok.type == 'heading_open':
      line = tok.map[0] + 1 if tok.map is not None else 1
      title = _inline_text(tokens[idx + 1])
      headings.append((tok.tag, title, _heading_slug(title), line))
    elif tok.type == 'inline':
      line = tok.map[0] + 1 if tok.map is not None else 1
      for href, label in _extract_inline_links(tok):
        links.append((href, label, line))
  return _ParsedDoc(
    rel=rel,
    blocks=blocks,
    headings=headings,
    slugs=frozenset(h[2] for h in headings),
    links=links,
  )


def _is_label_paragraph(block: Sequence[Token], label: str) -> bool:
  if len(block) != 3 or block[0].type != 'paragraph_open':
    return False
  children = [
    c
    for c in (block[1].children or [])
    if not (c.type == 'text' and c.content == '')
  ]
  return (
    len(children) == 3
    and children[0].type == 'strong_open'
    and children[1].type == 'text'
    and children[1].content == label
    and children[2].type == 'strong_close'
  )


def _has_empty_list_item(block: Sequence[Token]) -> bool:
  depth = 0
  has_content = False
  item_count = 0
  for tok in block[1:-1]:
    if tok.type == 'list_item_open' and depth == 0:
      item_count += 1
      has_content = False
    elif tok.type == 'list_item_close' and depth == 1:
      if not has_content:
        return True
    elif tok.type in ('inline', 'fence', 'code_block', 'html_block'):
      if tok.content.strip():
        has_content = True
    depth += tok.nesting
  return item_count == 0


def _check_companion_structure(
  doc: _ParsedDoc, diags: list[Diagnostic]
) -> None:
  blocks = doc.blocks
  if not blocks:
    diags.append(
      Diagnostic(doc.rel, 'test companion must start with "# Tests"', 1)
    )
    return
  first = blocks[0]
  if (
    first[0].type != 'heading_open'
    or first[0].tag != 'h1'
    or _inline_text(first[1]) != 'Tests'
  ):
    diags.append(
      Diagnostic(
        doc.rel,
        'test companion must start with "# Tests"',
        _block_line(first),
      )
    )
  if len(blocks) < 2:
    diags.append(
      Diagnostic(
        doc.rel,
        'test companion must have at least one "## <name>" section',
        1,
      )
    )
    return
  if blocks[1][0].type != 'heading_open' or blocks[1][0].tag != 'h2':
    diags.append(
      Diagnostic(
        doc.rel,
        'expected "## <name>" immediately after "# Tests"',
        _block_line(blocks[1]),
      )
    )

  sections: list[tuple[str, int, list[list[Token]]]] = []
  seen_titles: set[str] = set()
  for block in blocks[1:]:
    if block[0].type == 'heading_open':
      line = _block_line(block)
      if block[0].tag != 'h2':
        diags.append(
          Diagnostic(
            doc.rel,
            f'unexpected {block[0].tag.upper()} heading in test companion',
            line,
          )
        )
        continue
      title = _inline_text(block[1])
      if not title.strip():
        diags.append(
          Diagnostic(doc.rel, 'empty H2 heading in test companion', line)
        )
      elif title in seen_titles:
        diags.append(
          Diagnostic(doc.rel, f'duplicate test heading {title!r}', line)
        )
      seen_titles.add(title)
      sections.append((title, line, []))
    elif sections:
      sections[-1][2].append(block)

  for title, line, sec in sections:
    has_task = bool(sec) and _is_label_paragraph(sec[0], 'Task')
    if not has_task:
      diags.append(
        Diagnostic(
          doc.rel, f'test {title!r} must start with **Task**', line
        )
      )
    start = 1 if has_task else 0
    assert_idx = next(
      (
        i
        for i in range(start, len(sec))
        if _is_label_paragraph(sec[i], 'Assert')
      ),
      None,
    )
    if assert_idx is None:
      diags.append(
        Diagnostic(doc.rel, f'test {title!r} is missing **Assert**', line)
      )
      continue
    if assert_idx == start:
      diags.append(
        Diagnostic(
          doc.rel,
          f'test {title!r} requires Task content before **Assert**',
          _block_line(sec[assert_idx]),
        )
      )
    after = sec[assert_idx + 1 :]
    if len(after) != 1 or after[0][0].type != 'bullet_list_open':
      diags.append(
        Diagnostic(
          doc.rel,
          f'test {title!r} must have one bullet list after **Assert**',
          _block_line(sec[assert_idx]),
        )
      )
    elif _has_empty_list_item(after[0]):
      diags.append(
        Diagnostic(
          doc.rel,
          f'test {title!r} has an empty Assert bullet item',
          _block_line(after[0]),
        )
      )


def _resolve_local_href(
  rel_from: str,
  href: str,
  file_set: set[str],
  dir_set: set[str],
) -> tuple[str, str] | str:
  if '?' in href:
    return f'query string is not allowed in local link {href!r}'
  path_part, sep, fragment = href.partition('#')
  if path_part == '':
    if sep == '#':
      return rel_from, fragment
    return 'empty local link target'
  if path_part.startswith('/'):
    return f'link {href!r} must be relative, not root-anchored'
  base_dir = posixpath.dirname(rel_from)
  joined = posixpath.normpath(posixpath.join(base_dir, path_part))
  if joined == '..' or joined.startswith('../'):
    return f'link {href!r} escapes repository root'
  if path_part.endswith('/') or joined == '.' or joined in dir_set:
    return f'link {href!r} targets a directory'
  if joined not in file_set:
    return f'link {href!r} target {joined!r} not found in inventory'
  return joined, (fragment if sep == '#' else '')


def _is_external(href: str) -> bool:
  return href.startswith('//') or bool(EXTERNAL_LINK_RE.match(href))


def _check_headings_and_links(
  doc: _ParsedDoc,
  docs: dict[str, _ParsedDoc],
  file_set: set[str],
  dir_set: set[str],
  diags: list[Diagnostic],
) -> None:
  seen_slugs: dict[str, int] = {}
  for _tag, _title, slug, line in doc.headings:
    if slug in seen_slugs:
      diags.append(
        Diagnostic(
          doc.rel,
          f'duplicate heading identifier #{slug} '
          f'(first on line {seen_slugs[slug]})',
          line,
        )
      )
    else:
      seen_slugs[slug] = line

  seen_labels: dict[tuple[str, str], tuple[str, str, int]] = {}
  for href, label, line in doc.links:
    if _is_external(href):
      continue
    resolved = _resolve_local_href(doc.rel, href, file_set, dir_set)
    if isinstance(resolved, str):
      diags.append(Diagnostic(doc.rel, resolved, line))
      continue
    target, fragment = resolved
    if '#' in href:
      if not target.endswith('.md'):
        diags.append(
          Diagnostic(
            doc.rel,
            f'fragment link {href!r} targets non-Markdown file {target!r}',
            line,
          )
        )
        continue
      target_doc = docs[target]
      if not fragment or fragment not in target_doc.slugs:
        diags.append(
          Diagnostic(
            doc.rel,
            f'missing heading #{fragment} in {target}',
            line,
          )
        )
        continue
    key = (target, fragment)
    norm_label = ' '.join(label.split()).casefold()
    if key in seen_labels and seen_labels[key][0] != norm_label:
      _, prev_label, prev_line = seen_labels[key]
      diags.append(
        Diagnostic(
          doc.rel,
          f'inconsistent link text {label!r} for {href!r} '
          f'(was {prev_label!r} on line {prev_line})',
          line,
        )
      )
    elif key not in seen_labels:
      seen_labels[key] = (norm_label, label, line)


def _check_readme_index(
  doc: _ParsedDoc,
  direct_children: set[str],
  file_set: set[str],
  dir_set: set[str],
  diags: list[Diagnostic],
) -> None:
  if not direct_children:
    return
  sections: list[tuple[int, list[list[Token]]]] = []
  for block in doc.blocks:
    if block[0].type == 'heading_open' and block[0].tag == 'h2':
      sections.append((_block_line(block), []))
    elif sections:
      sections[-1][1].append(block)

  child_sections: dict[str, list[int]] = defaultdict(list)
  for h2_line, sec_blocks in sections:
    linked: set[str] = set()
    for block in sec_blocks:
      for tok in block:
        if tok.type != 'inline':
          continue
        for href, _label in _extract_inline_links(tok):
          if _is_external(href):
            continue
          resolved = _resolve_local_href(doc.rel, href, file_set, dir_set)
          if (
            isinstance(resolved, tuple) and resolved[0] in direct_children
          ):
            linked.add(resolved[0])
    if len(linked) != 1:
      diags.append(
        Diagnostic(
          doc.rel,
          f'index H2 section must link to exactly one direct child '
          f'(found {len(linked)})',
          h2_line,
        )
      )
    for child in linked:
      child_sections[child].append(h2_line)

  for child in sorted(direct_children):
    lines = child_sections.get(child, [])
    if not lines:
      diags.append(
        Diagnostic(
          doc.rel,
          f'missing H2 index section linking to {child}',
        )
      )
    elif len(lines) > 1:
      diags.append(
        Diagnostic(
          doc.rel,
          f'direct child {child} linked from multiple H2 sections',
          lines[1],
        )
      )


def check_docs(repo: Path) -> list[Diagnostic]:
  files = _inventoried_files(repo)
  file_set = set(files)
  dir_set: set[str] = set()
  siblings_by_dir: dict[str, dict[str, list[str]]] = defaultdict(
    lambda: defaultdict(list)
  )
  non_companion_mds: set[str] = set()
  md_companions: list[str] = []

  for rel in files:
    parts = PurePosixPath(rel).parts
    for i in range(1, len(parts)):
      dir_set.add('/'.join(parts[:i]))
    parent = posixpath.dirname(rel)
    name = parts[-1]
    stem = _non_test_sibling(name)
    if stem is not None:
      siblings_by_dir[parent][stem].append(rel)
    if _is_test_md_candidate(name):
      md_companions.append(rel)
    elif rel.endswith('.md'):
      non_companion_mds.add(rel)

  md = MarkdownIt()
  docs = {
    rel: _parse_doc(md, repo, rel) for rel in files if rel.endswith('.md')
  }
  diags: list[Diagnostic] = []

  for rel in md_companions:
    parts = PurePosixPath(rel).parts
    stem = _md_companion_stem(parts[-1])
    if stem is None:
      diags.append(
        Diagnostic(
          rel,
          f'invalid test companion name {parts[-1]!r}; '
          'expected <stem>.test.md without "." or "test" in stem',
        )
      )
      continue
    matches = siblings_by_dir[posixpath.dirname(rel)].get(stem, [])
    if len(matches) == 0:
      diags.append(
        Diagnostic(
          rel,
          f'test companion {parts[-1]!r} lacks '
          f'non-test sibling {stem}.<ext>',
        )
      )
    elif len(matches) > 1:
      diags.append(
        Diagnostic(
          rel,
          f'test companion {parts[-1]!r} matches multiple siblings: '
          f'{", ".join(matches)}',
        )
      )
    _check_companion_structure(docs[rel], diags)

  for rel in sorted(docs):
    _check_headings_and_links(docs[rel], docs, file_set, dir_set, diags)

  dirs_with_md = {posixpath.dirname(rel) for rel in non_companion_mds}
  for d in sorted(dirs_with_md):
    readme = 'README.md' if d == '' else f'{d}/README.md'
    if readme not in non_companion_mds:
      diags.append(
        Diagnostic(readme, f'directory {d or "."!r} is missing README.md')
      )

  for rel in sorted(non_companion_mds):
    if PurePosixPath(rel).name != 'README.md':
      continue
    d = posixpath.dirname(rel)
    children = {
      f
      for f in non_companion_mds
      if f != rel and posixpath.dirname(f) == d
    }
    for f in non_companion_mds:
      if PurePosixPath(f).name != 'README.md' or f == rel:
        continue
      parent_of_child_dir = posixpath.dirname(posixpath.dirname(f))
      if d == '' and '/' in f and f.count('/') == 1:
        children.add(f)
      elif d != '' and parent_of_child_dir == d:
        children.add(f)
    _check_readme_index(docs[rel], children, file_set, dir_set, diags)

  return diags
