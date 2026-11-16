import os
import stat
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
import pytest

from zero.agent import common


@dataclass(frozen=True, slots=True)
class _FakeNode:
  mode: int
  ino: int
  dev: int = 1
  target: Path | None = None
  children: tuple[tuple[str, Path], ...] = ()
  stat_error: OSError | None = None
  scandir_error: OSError | None = None
  resolve_error: OSError | None = None

  def to_stat_result(self) -> os.stat_result:
    return os.stat_result(
      (self.mode, self.ino, self.dev, 1, 0, 0, 0, 0, 0, 0)
    )


class _FakeDirEntry:
  def __init__(
    self,
    name: str,
    path: Path,
    nodes: Mapping[Path, _FakeNode],
  ) -> None:
    self.name = name
    self.path = str(path)
    self._path = path
    self._nodes = nodes

  def is_symlink(self) -> bool:
    node = self._nodes[self._path]
    return stat.S_ISLNK(node.mode)

  def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
    node = self._nodes[self._path]
    if node.stat_error is not None:
      raise node.stat_error
    if not follow_symlinks or node.target is None:
      return node.to_stat_result()
    target = self._nodes.get(node.target)
    if target is None:
      raise FileNotFoundError(
        2, 'No such file or directory', str(self._path)
      )
    if target.stat_error is not None:
      raise target.stat_error
    return target.to_stat_result()


@contextmanager
def _scandir_context(
  items: list[_FakeDirEntry],
) -> Iterator[Iterator[_FakeDirEntry]]:
  yield iter(items)


def _install_scan_tree(
  mp: pytest.MonkeyPatch,
  nodes: Mapping[Path, _FakeNode],
) -> None:
  def fake_lstat(self: Path) -> os.stat_result:
    node = nodes.get(self)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(self))
    return node.to_stat_result()

  def fake_stat(
    self: Path, *, follow_symlinks: bool = True
  ) -> os.stat_result:
    node = nodes.get(self)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(self))
    if node.stat_error is not None:
      raise node.stat_error
    if follow_symlinks and node.target is not None:
      target = nodes.get(node.target)
      if target is None:
        raise FileNotFoundError(2, 'No such file or directory', str(self))
      if target.stat_error is not None:
        raise target.stat_error
      return target.to_stat_result()
    return node.to_stat_result()

  def fake_resolve(self: Path, strict: bool = False) -> Path:
    del strict
    node = nodes.get(self)
    if node is None:
      return self
    if node.resolve_error is not None:
      raise node.resolve_error
    if node.target is not None:
      return node.target
    return self

  def fake_scandir(
    path: Path | str,
  ) -> AbstractContextManager[Iterator[_FakeDirEntry]]:
    key = Path(path)
    node = nodes.get(key)
    if node is not None and node.target is not None:
      node = nodes.get(node.target)
    if node is None:
      raise FileNotFoundError(2, 'No such file or directory', str(path))
    if node.scandir_error is not None:
      raise node.scandir_error
    entries = [
      _FakeDirEntry(name, child_path, nodes)
      for name, child_path in node.children
    ]
    return _scandir_context(entries)

  mp.setattr(Path, 'lstat', fake_lstat)
  mp.setattr(Path, 'stat', fake_stat)
  mp.setattr(Path, 'resolve', fake_resolve)
  mp.setattr(common.os, 'scandir', fake_scandir)


def test_is_under_matches_root_and_descendants_only() -> None:
  root = Path('/virtual/home/.config')

  assert (
    common.is_under(root, root),
    common.is_under(root / 'plugins' / 'one', root),
    common.is_under(Path('/virtual/home/.config-other'), root),
    common.is_under(Path('/virtual/home/plugins'), root),
  ) == (True, True, False, False)


@pytest.mark.parametrize(
  ('raw', 'expected'),
  [
    ('{"agent": "codex"}', ({'agent': 'codex'}, None)),
    (
      'not json',
      (
        None,
        'Cannot read agent state /virtual/agent.json: '
        'Expecting value: line 1 column 1 (char 0)',
      ),
    ),
    (
      '[]',
      (
        None,
        'agent state must contain a JSON object: /virtual/agent.json',
      ),
    ),
  ],
  ids=('object', 'malformed', 'wrong-shape'),
)
def test_parse_json_object_returns_object_or_error(
  raw: str,
  expected: tuple[dict[str, object] | None, str | None],
) -> None:
  path = Path('/virtual/agent.json')
  assert common.parse_json_object(raw, path, 'agent state') == expected


@pytest.mark.parametrize(
  ('lstat_exc', 'stat_result_or_exc', 'read_result', 'expected'),
  [
    (FileNotFoundError(2, 'missing'), None, None, (None, None)),
    (NotADirectoryError(20, 'not dir'), None, None, (None, None)),
    (
      PermissionError(13, 'lstat denied'),
      None,
      None,
      (None, 'Cannot read agent state {path}: [Errno 13] lstat denied'),
    ),
    (
      None,
      FileNotFoundError(2, 'broken symlink'),
      None,
      (None, 'Cannot read agent state {path}: [Errno 2] broken symlink'),
    ),
    (
      None,
      stat.S_IFDIR | 0o755,
      None,
      (None, 'agent state path is not a file: {path}'),
    ),
    (
      None,
      stat.S_IFREG | 0o644,
      PermissionError(13, 'denied'),
      (None, 'Cannot read agent state {path}: [Errno 13] denied'),
    ),
    (
      None,
      stat.S_IFREG | 0o644,
      UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte'),
      (
        None,
        "Cannot read agent state {path}: 'utf-8' codec can't decode byte "
        '0xff in position 0: invalid start byte',
      ),
    ),
    (
      None,
      stat.S_IFREG | 0o644,
      '{"agent": "claude"}',
      ({'agent': 'claude'}, None),
    ),
  ],
  ids=(
    'missing',
    'not-a-dir-parent',
    'lstat-eperm',
    'broken-symlink',
    'dir-not-file',
    'read-oserror',
    'decode-error',
    'valid-file',
  ),
)
def test_read_json_file_handles_fail_closed_boundaries(
  monkeypatch: pytest.MonkeyPatch,
  lstat_exc: OSError | None,
  stat_result_or_exc: int | OSError | None,
  read_result: str | Exception | None,
  expected: tuple[dict[str, object] | None, str | None],
) -> None:
  target = Path('/virtual/agent.json')

  def fake_lstat(self: Path) -> os.stat_result:
    assert self == target
    if lstat_exc is not None:
      raise lstat_exc
    return os.stat_result(
      (stat.S_IFREG | 0o644, 1, 1, 1, 0, 0, 0, 0, 0, 0)
    )

  def fake_stat(
    self: Path, *, follow_symlinks: bool = True
  ) -> os.stat_result:
    del follow_symlinks
    assert self == target
    if isinstance(stat_result_or_exc, OSError):
      raise stat_result_or_exc
    assert isinstance(stat_result_or_exc, int)
    return os.stat_result((stat_result_or_exc, 1, 1, 1, 0, 0, 0, 0, 0, 0))

  def fake_read_text(self: Path, encoding: str = 'utf-8') -> str:
    assert (self, encoding) == (target, 'utf-8')
    if isinstance(read_result, Exception):
      raise read_result
    assert read_result is not None
    return read_result

  with monkeypatch.context() as mp:
    mp.setattr(Path, 'lstat', fake_lstat)
    mp.setattr(Path, 'stat', fake_stat)
    mp.setattr(Path, 'read_text', fake_read_text)
    obj, error = common.read_json_file(target, 'agent state')

  exp_obj, exp_err = expected
  assert (obj, error) == (
    exp_obj,
    exp_err.format(path=target) if exp_err is not None else None,
  )


def test_check_ambient_file_handles_symlinks_dirs_and_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  real = Path('/virtual/real.md')
  linked = Path('/virtual/linked.md')
  broken = Path('/virtual/broken.md')
  directory = Path('/virtual/dir')
  blocked = Path('/virtual/blocked.md')
  looped = Path('/virtual/looped.md')

  nodes = {
    real: _FakeNode(stat.S_IFREG | 0o644, ino=10),
    linked: _FakeNode(stat.S_IFLNK | 0o777, ino=11, target=real),
    broken: _FakeNode(
      stat.S_IFLNK | 0o777, ino=12, target=Path('/virtual/missing')
    ),
    directory: _FakeNode(stat.S_IFDIR | 0o755, ino=13),
    blocked: _FakeNode(
      stat.S_IFREG | 0o644,
      ino=14,
      stat_error=PermissionError(13, 'denied'),
    ),
    looped: _FakeNode(
      stat.S_IFREG | 0o644,
      ino=15,
      resolve_error=OSError(40, 'Too many levels of symbolic links'),
    ),
  }

  with monkeypatch.context() as mp:
    _install_scan_tree(mp, nodes)
    assert common.check_ambient_file(
      Path('/virtual/absent.md'), label='rules'
    ) == (None, None)
    assert common.check_ambient_file(broken, label='rules') == (None, None)
    assert common.check_ambient_file(directory, label='rules') == (
      None,
      None,
    )
    assert common.check_ambient_file(linked, label='rules') == (real, None)
    assert common.check_ambient_file(blocked, label='rules') == (
      None,
      f'Cannot scan rules {blocked}: [Errno 13] denied',
    )
    assert common.check_ambient_file(looped, label='rules') == (
      None,
      f'Cannot scan rules {looped}: '
      '[Errno 40] Too many levels of symbolic links',
    )


def test_scan_ambient_files_symlinks_cycles_and_errors(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  root = Path('/virtual/skills')
  sub = root / 'sub'
  link_dir = root / 'link_sub'
  cycle = sub / 'cycle'
  blocked_dir = root / 'blocked'
  dir_named_skill = root / 'dir_skill' / 'SKILL.md'
  broken_skill = root / 'broken_skill' / 'SKILL.md'
  unresolvable = root / 'bad_resolve' / 'SKILL.md'
  real_dir = Path('/external/shared')
  real_skill = real_dir / 'SKILL.md'
  sub_skill = sub / 'SKILL.md'
  nested_inside_skill_dir = dir_named_skill / 'SKILL.md'

  nodes = {
    root: _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=1,
      children=(
        ('bad_resolve', root / 'bad_resolve'),
        ('blocked', blocked_dir),
        ('broken_skill', root / 'broken_skill'),
        ('dir_skill', root / 'dir_skill'),
        ('link_sub', link_dir),
        ('sub', sub),
      ),
    ),
    sub: _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=2,
      children=(
        ('SKILL.md', sub_skill),
        ('cycle', cycle),
        ('ignored.md', sub / 'ignored.md'),
      ),
    ),
    sub_skill: _FakeNode(stat.S_IFREG | 0o644, ino=3),
    sub / 'ignored.md': _FakeNode(stat.S_IFREG | 0o644, ino=4),
    cycle: _FakeNode(stat.S_IFLNK | 0o777, ino=5, target=root),
    link_dir: _FakeNode(stat.S_IFLNK | 0o777, ino=6, target=real_dir),
    real_dir: _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=7,
      children=(('SKILL.md', real_dir / 'SKILL.md'),),
    ),
    real_skill: _FakeNode(stat.S_IFREG | 0o644, ino=8),
    blocked_dir: _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=9,
      scandir_error=PermissionError(13, 'denied'),
    ),
    root / 'dir_skill': _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=10,
      children=(('SKILL.md', dir_named_skill),),
    ),
    dir_named_skill: _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=11,
      children=(('SKILL.md', nested_inside_skill_dir),),
    ),
    nested_inside_skill_dir: _FakeNode(stat.S_IFREG | 0o644, ino=12),
    root / 'broken_skill': _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=13,
      children=(('SKILL.md', broken_skill),),
    ),
    broken_skill: _FakeNode(
      stat.S_IFLNK | 0o777,
      ino=14,
      target=Path('/virtual/missing-target'),
    ),
    root / 'bad_resolve': _FakeNode(
      stat.S_IFDIR | 0o755,
      ino=15,
      children=(('SKILL.md', unresolvable),),
    ),
    unresolvable: _FakeNode(
      stat.S_IFREG | 0o644,
      ino=16,
      resolve_error=OSError(5, 'input/output error'),
    ),
  }

  with monkeypatch.context() as mp:
    _install_scan_tree(mp, nodes)
    files, findings = common.scan_ambient_files(
      root, label='skills', match_name='SKILL.md'
    )
    single_files, single_findings = common.scan_ambient_files(
      real_skill,
      label='skills',
      match_name='SKILL.md',
      allow_single_file=True,
    )

  assert (files, findings, single_files, single_findings) == (
    (real_skill, nested_inside_skill_dir, sub_skill),
    (
      f'Cannot scan skills {unresolvable}: [Errno 5] input/output error',
      f'Cannot scan skills {blocked_dir}: [Errno 13] denied',
    ),
    (real_skill,),
    (),
  )


def test_exec_agent_changes_directory_and_replaces_process(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[
    tuple[str, Path] | tuple[str, str, Sequence[str], Mapping[str, str]]
  ] = []
  root = Path('/virtual/repo')
  with monkeypatch.context() as mp:
    mp.setattr(
      common.os, 'chdir', lambda path: calls.append(('chdir', path))
    )
    mp.setattr(
      common.os,
      'execvpe',
      lambda executable, arguments, environment: calls.append(
        ('exec', executable, arguments, environment)
      ),
    )
    common.exec_agent(
      root, ['codex', '--model', 'gpt-6-astra'], ['--resume']
    )

  assert calls == [
    ('chdir', root),
    (
      'exec',
      'codex',
      ['codex', '--model', 'gpt-6-astra', '--resume'],
      common.os.environ,
    ),
  ]


def test_exec_agent_wraps_oserror_in_click_exception(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  root = Path('/virtual/repo')

  with monkeypatch.context() as mp:
    mp.setattr(
      common.os,
      'chdir',
      lambda _path: (_ for _ in ()).throw(PermissionError(13, 'denied')),
    )
    with pytest.raises(click.ClickException) as chdir_error:
      common.exec_agent(root, ['codex'], [])
    assert str(chdir_error.value) == (
      'Failed to launch agent codex: [Errno 13] denied'
    )

  with monkeypatch.context() as mp:
    mp.setattr(common.os, 'chdir', lambda _path: None)
    mp.setattr(
      common.os,
      'execvpe',
      lambda *_a: (_ for _ in ()).throw(FileNotFoundError(2, 'missing')),
    )
    with pytest.raises(click.ClickException) as exec_error:
      common.exec_agent(root, ['codex'], [])
    assert str(exec_error.value) == (
      'Failed to launch agent codex: [Errno 2] missing'
    )
