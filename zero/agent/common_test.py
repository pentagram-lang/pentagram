from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path

import click
import pytest

from zero.agent.common import (
  check_ambient_file,
  exec_agent,
  expand_env_path,
  is_under,
  json_object,
  parse_json_object,
  raise_preflight,
  read_json_file,
  read_regular_text,
  scan_ambient_files,
  string_list,
)


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  root = Path(
    tempfile.mkdtemp(prefix='zero-agent-common-', dir='/dev/shm')
  )
  try:
    yield root
  finally:
    shutil.rmtree(root, ignore_errors=True)


def test_json_object_and_string_list() -> None:
  assert json_object({'a': 1, 'b': 'two'}) == {'a': 1, 'b': 'two'}
  assert json_object({1: 'a'}) is None
  assert json_object(['a']) is None
  assert json_object(None) is None

  assert string_list(['a', 'b']) == ['a', 'b']
  assert string_list([]) == []
  assert string_list(['a', 1]) is None
  assert string_list(('a',)) is None
  assert string_list('ab') is None


def test_is_under(shm_dir: Path) -> None:
  root = shm_dir / 'root'
  outside = shm_dir / 'outside'
  (root / 'sub').mkdir(parents=True)
  outside.mkdir()
  inside_file = root / 'sub' / 'a.txt'
  inside_file.write_text('ok', encoding='utf-8')
  outside_file = outside / 'b.txt'
  outside_file.write_text('no', encoding='utf-8')
  link_out = root / 'link_out.txt'
  link_out.symlink_to(outside_file)
  link_in = outside / 'link_in.txt'
  link_in.symlink_to(inside_file)

  assert is_under(root, root) is True
  assert is_under(inside_file, root) is True
  assert is_under(root / 'missing.txt', root) is True
  assert is_under(outside_file, root) is False
  assert is_under(link_out, root) is False
  assert is_under(link_in, root) is True


def test_expand_env_path(shm_dir: Path) -> None:
  home = shm_dir / 'home'
  env = {'SUB': 'skills/demo', 'ABS': '/etc/passwd'}

  assert expand_env_path('~', home, env) == home
  assert expand_env_path('~/.codex/config.toml', home, env) == (
    home / '.codex' / 'config.toml'
  )
  assert expand_env_path('~/$SUB/SKILL.md', home, env) == (
    home / 'skills' / 'demo' / 'SKILL.md'
  )
  assert expand_env_path('~/$ABS/x', home, env) == Path(
    f'{home}//etc/passwd/x'
  )
  assert expand_env_path('${SUB}/$UNKNOWN/a', home, env) == Path(
    'skills/demo/$UNKNOWN/a'
  )


def test_read_regular_text_and_json(
  shm_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
  missing = shm_dir / 'missing.json'
  assert read_regular_text(missing, 'cfg') == (None, None)
  assert read_json_file(missing, 'cfg') == (None, None)

  good = shm_dir / 'good.json'
  good.write_text('{"k": "v"}', encoding='utf-8')
  assert read_regular_text(good, 'cfg') == ('{"k": "v"}', None)
  assert read_json_file(good, 'cfg') == ({'k': 'v'}, None)

  link = shm_dir / 'link.json'
  link.symlink_to(good)
  assert read_json_file(link, 'cfg') == ({'k': 'v'}, None)

  dangling = shm_dir / 'dangling.json'
  dangling.symlink_to(shm_dir / 'nope.json')
  text, err = read_regular_text(dangling, 'cfg')
  assert text is None
  assert err is not None and err.startswith(
    f'Could not stat cfg ({dangling}):'
  )

  subdir = shm_dir / 'dir'
  subdir.mkdir()
  assert read_regular_text(subdir, 'cfg') == (
    None,
    f'cfg ({subdir}) is not a regular file',
  )

  fifo = shm_dir / 'pipe'
  os.mkfifo(fifo)
  assert read_regular_text(fifo, 'cfg') == (
    None,
    f'cfg ({fifo}) is not a regular file',
  )

  bad_utf8 = shm_dir / 'bad.bin'
  bad_utf8.write_bytes(b'\xff\xfe')
  raw, utf_err = read_regular_text(bad_utf8, 'cfg')
  assert raw is None
  assert utf_err is not None and utf_err.startswith(
    f'Invalid UTF-8 in cfg ({bad_utf8}):'
  )

  locked = shm_dir / 'locked.txt'
  locked.write_text('secret', encoding='utf-8')
  real_read_text = Path.read_text

  def deny_locked_read(
    self: Path, encoding: str | None = None, errors: str | None = None
  ) -> str:
    if self == locked:
      raise PermissionError(13, 'Permission denied')
    return real_read_text(self, encoding=encoding, errors=errors)

  monkeypatch.setattr(Path, 'read_text', deny_locked_read)
  assert read_regular_text(good, 'cfg') == ('{"k": "v"}', None)
  raw_locked, locked_err = read_regular_text(locked, 'cfg')
  assert raw_locked is None
  assert locked_err is not None and locked_err.startswith(
    f'Could not read cfg ({locked}):'
  )

  arr_text = '[1, 2]'
  assert parse_json_object(arr_text, good, 'cfg') == (
    None,
    f'Expected JSON object in cfg ({good})',
  )
  obj, bad_json_err = parse_json_object('{bad', good, 'cfg')
  assert obj is None
  assert bad_json_err is not None and bad_json_err.startswith(
    f'Invalid JSON in cfg ({good}):'
  )


def test_check_ambient_file(shm_dir: Path) -> None:
  assert check_ambient_file(shm_dir / 'absent.md', label='mem') == (
    None,
    None,
  )

  reg = shm_dir / 'CLAUDE.md'
  reg.write_text('# hi', encoding='utf-8')
  assert check_ambient_file(reg, label='mem') == (reg, None)

  dangling = shm_dir / 'dangling.md'
  dangling.symlink_to(shm_dir / 'target.md')
  assert check_ambient_file(dangling, label='mem') == (None, None)

  subdir = shm_dir / 'dir.md'
  subdir.mkdir()
  assert check_ambient_file(subdir, label='mem') == (
    None,
    f'mem ({subdir}) is not a regular file',
  )

  loop_a = shm_dir / 'loop_a.md'
  loop_b = shm_dir / 'loop_b.md'
  loop_a.symlink_to(loop_b)
  loop_b.symlink_to(loop_a)
  found, err = check_ambient_file(loop_a, label='mem')
  assert found is None
  assert err is not None and err.startswith(
    f'Could not stat mem ({loop_a}):'
  )


def test_scan_ambient_files_cycle_dangling_and_filters(
  shm_dir: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  assert scan_ambient_files(shm_dir / 'missing', label='skills') == (
    (),
    (),
  )

  single = shm_dir / 'single.md'
  single.write_text('x', encoding='utf-8')
  assert scan_ambient_files(single, label='mem') == (
    (),
    (f'mem ({single}) is not a directory',),
  )
  assert scan_ambient_files(
    single, label='mem', suffix='.md', allow_single_file=True
  ) == ((single,), ())

  root = shm_dir / 'skills'
  (root / 'a').mkdir(parents=True)
  (root / 'b').mkdir()
  skill_a = root / 'a' / 'SKILL.md'
  skill_a.write_text('skill', encoding='utf-8')
  note = root / 'b' / 'README.md'
  note.write_text('note', encoding='utf-8')
  (root / 'b' / 'dangling.md').symlink_to(root / 'gone.md')
  (root / 'b' / 'cycle').symlink_to(root)

  shared_dir = shm_dir / 'shared_skill'
  shared_dir.mkdir()
  shared_skill = shared_dir / 'SKILL.md'
  shared_skill.write_text('shared', encoding='utf-8')
  (root / 'alias_one').symlink_to(shared_dir)
  (root / 'alias_two').symlink_to(shared_dir)

  assert scan_ambient_files(
    root, label='skills', match_name='SKILL.md'
  ) == (
    (
      skill_a,
      root / 'alias_one' / 'SKILL.md',
      root / 'alias_two' / 'SKILL.md',
    ),
    (),
  )
  assert scan_ambient_files(root, label='rules', suffix='.md') == (
    (
      skill_a,
      root / 'alias_one' / 'SKILL.md',
      root / 'alias_two' / 'SKILL.md',
      note,
    ),
    (),
  )

  locked_dir = root / 'locked'
  locked_dir.mkdir()
  real_scandir = os.scandir

  def deny_locked_scandir(
    path: str | os.PathLike[str] = '.',
  ) -> AbstractContextManager[Iterator[os.DirEntry[str]]]:
    if path == locked_dir:
      raise PermissionError(13, 'Permission denied')
    return real_scandir(path)

  monkeypatch.setattr(os, 'scandir', deny_locked_scandir)
  files, errors = scan_ambient_files(
    root, label='skills', match_name='SKILL.md'
  )
  assert files == (
    skill_a,
    root / 'alias_one' / 'SKILL.md',
    root / 'alias_two' / 'SKILL.md',
  )
  assert len(errors) == 1
  assert errors[0].startswith(f'Could not scan skills ({locked_dir}):')


def test_raise_preflight_and_exec_agent(shm_dir: Path) -> None:
  raise_preflight('Codex', ())
  with pytest.raises(click.ClickException) as exc_info:
    raise_preflight('Codex', ('first', 'second'))
  assert exc_info.value.format_message() == (
    'Codex filesystem preflight failed:\n  - first\n  - second'
  )

  prev_cwd = Path.cwd()
  try:
    with pytest.raises(click.ClickException) as missing_dir_exc:
      exec_agent(shm_dir / 'no-such-dir', ['codex'], ())
    assert missing_dir_exc.value.format_message().startswith(
      'Failed to launch agent codex: '
    )

    with pytest.raises(click.ClickException) as missing_bin_exc:
      exec_agent(shm_dir, ['nonexistent-agent-binary-xyz'], ('--flag',))
    assert missing_bin_exc.value.format_message().startswith(
      'Failed to launch agent nonexistent-agent-binary-xyz: '
    )
  finally:
    os.chdir(prev_cwd)
