from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path

import click
import pytest

from zero.agent.codex import build_codex_command, launch, preflight_codex


@pytest.fixture
def shm_dir() -> Iterator[Path]:
  root = Path(tempfile.mkdtemp(prefix='zero-agent-codex-', dir='/dev/shm'))
  try:
    yield root
  finally:
    shutil.rmtree(root, ignore_errors=True)


def test_codex_clean_launch_and_excluded_paths(shm_dir: Path) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  codex_dir = home / '.codex'
  (codex_dir / 'skills' / 'env_skill').mkdir(parents=True)
  (codex_dir / 'skills' / 'tilde_skill').mkdir(parents=True)
  (codex_dir / 'skills' / 'rel_skill').mkdir(parents=True)
  (codex_dir / 'skills' / 'dir_skill').mkdir(parents=True)
  (codex_dir / 'plugins' / 'p1').mkdir(parents=True)
  (codex_dir / '.tmp' / 'plugins' / 'p2').mkdir(parents=True)
  (codex_dir / 'rules').mkdir(parents=True)
  repo.mkdir(parents=True)

  env_skill = codex_dir / 'skills' / 'env_skill' / 'SKILL.md'
  env_skill.write_text('# env', encoding='utf-8')
  tilde_skill = codex_dir / 'skills' / 'tilde_skill' / 'SKILL.md'
  tilde_skill.write_text('# tilde', encoding='utf-8')
  rel_target = codex_dir / 'skills' / 'rel_skill' / 'SKILL.md'
  rel_target.write_text('# rel', encoding='utf-8')
  (codex_dir / 'skills' / 'dir_skill' / 'SKILL.md').write_text(
    '# dir', encoding='utf-8'
  )
  rel_link = codex_dir / 'skills' / 'rel_link.md'
  rel_link.symlink_to(rel_target)
  (codex_dir / 'skills' / 'rel_link').mkdir()
  (codex_dir / 'skills' / 'rel_link' / 'SKILL.md').symlink_to(rel_target)

  plugin_skill = codex_dir / 'plugins' / 'p1' / 'SKILL.md'
  plugin_skill.write_text('# plugin', encoding='utf-8')
  tmp_plugin_skill = codex_dir / '.tmp' / 'plugins' / 'p2' / 'SKILL.md'
  tmp_plugin_skill.write_text('# tmp plugin', encoding='utf-8')
  (codex_dir / 'skills' / 'via_plugin').mkdir()
  (codex_dir / 'skills' / 'via_plugin' / 'SKILL.md').symlink_to(
    plugin_skill
  )
  (codex_dir / 'skills' / 'via_tmp_plugin').mkdir()
  (codex_dir / 'skills' / 'via_tmp_plugin' / 'SKILL.md').symlink_to(
    tmp_plugin_skill
  )
  (codex_dir / 'rules' / 'exec.rules').write_text(
    'allow', encoding='utf-8'
  )

  (codex_dir / 'config.toml').write_text(
    'profile = ""\n'
    '\n'
    '[features]\n'
    'memories = false\n'
    'plugins = false\n'
    '\n'
    '[mcp_servers.alpha]\n'
    'enabled = false\n'
    '\n'
    '[[skills.config]]\n'
    'path = "$SKILL_ROOT/env_skill/SKILL.md"\n'
    'enabled = false\n'
    '\n'
    '[[skills.config]]\n'
    'path = "~/.codex/skills/tilde_skill/SKILL.md"\n'
    'enabled = false\n'
    '\n'
    '[[skills.config]]\n'
    'path = "skills/rel_skill/SKILL.md"\n'
    'enabled = false\n'
    '\n'
    '[[skills.config]]\n'
    'path = "skills/dir_skill"\n'
    'enabled = false\n',
    encoding='utf-8',
  )

  env = {'SKILL_ROOT': str(codex_dir / 'skills')}
  sys_file = repo / 'sys.md'
  sys_file.write_text('system', encoding='utf-8')

  recorded: list[tuple[Path, list[str], list[str]]] = []

  def fake_exec(
    root: Path, cmd: Sequence[str], args: Sequence[str]
  ) -> None:
    recorded.append((root, list(cmd), list(args)))

  prev_cwd = Path.cwd()
  os.chdir(repo.parent)
  try:
    launch(
      Path(repo.name),
      'gpt-5.4',
      Path(repo.name) / 'sys.md',
      ['--help'],
      home=home,
      environ=env,
      exec_fn=fake_exec,
    )
  finally:
    os.chdir(prev_cwd)

  expected_cmd = build_codex_command(
    'gpt-5.4', sys_file.resolve(), repo.resolve()
  )
  assert expected_cmd == [
    'codex',
    '--model',
    'gpt-5.4',
    '--config',
    f'model_instructions_file={json.dumps(str(sys_file.resolve()))}',
    '--dangerously-bypass-approvals-and-sandbox',
    '--cd',
    str(repo.resolve()),
  ]
  assert recorded == [(repo.resolve(), expected_cmd, ['--help'])]


def test_codex_preflight_rejects_ambient_state_and_configs(
  shm_dir: Path,
) -> None:
  home = shm_dir / 'home'
  repo = shm_dir / 'repo'
  codex_dir = home / '.codex'
  (codex_dir / 'memories').mkdir(parents=True)
  (codex_dir / 'skills' / 's1').mkdir(parents=True)
  (codex_dir / 'skills' / 's2').mkdir(parents=True)
  (repo / '.codex').mkdir(parents=True)

  home_cfg = codex_dir / 'config.toml'
  prof_cfg = codex_dir / 'work.config.toml'
  repo_cfg = repo / '.codex' / 'config.toml'
  mem_file = codex_dir / 'memories' / 'note.md'
  skill_one = codex_dir / 'skills' / 's1' / 'SKILL.md'
  skill_two = codex_dir / 'skills' / 's2' / 'SKILL.md'

  home_cfg.write_text(
    'profile = "work"\n'
    '\n'
    '[mcp_servers.alpha]\n'
    'command = "alpha"\n'
    '\n'
    '[[skills.config]]\n'
    'path = "~/.codex/skills/s1/SKILL.md"\n'
    'enabled = false\n',
    encoding='utf-8',
  )
  prof_cfg.write_text(
    '[features]\nmemories = true\n',
    encoding='utf-8',
  )
  repo_cfg.write_text(
    '[features]\n'
    'plugins = true\n'
    '\n'
    '[[skills.config]]\n'
    'path = "~/.codex/skills/s1/SKILL.md"\n'
    'enabled = true\n',
    encoding='utf-8',
  )
  mem_file.write_text('remember', encoding='utf-8')
  skill_one.write_text('# s1', encoding='utf-8')
  skill_two.write_text('# s2', encoding='utf-8')

  findings = preflight_codex(repo, home=home, environ={})
  assert findings == (
    f"Codex config {home_cfg} sets profile='work'; "
    'clear or remove `profile`',
    f"Codex MCP server 'alpha' in {home_cfg} must set enabled = false",
    f"Codex feature 'memories' must be false or omitted in {prof_cfg}; "
    'run `codex features disable memories`',
    f"Codex feature 'plugins' must be false or omitted in {repo_cfg}; "
    'run `codex features disable plugins`',
    'Codex ambient memory file blocks launch '
    f'(no persistent disable setting): {mem_file}',
    f'Codex skill {skill_one} must be disabled with enabled = false '
    'via /skills',
    f'Codex skill {skill_two} must be disabled with enabled = false '
    'via /skills',
  )

  called = False

  def fake_exec(
    root: Path, cmd: Sequence[str], args: Sequence[str]
  ) -> None:
    nonlocal called
    called = True

  with pytest.raises(click.ClickException) as exc_info:
    launch(
      repo,
      'gpt-5.4',
      repo / 'sys.md',
      (),
      home=home,
      environ={},
      exec_fn=fake_exec,
    )
  assert called is False
  assert exc_info.value.format_message().startswith(
    'Codex filesystem preflight failed:\n'
  )


def test_codex_dedup_repo_equals_home_and_invalid_toml(
  shm_dir: Path,
) -> None:
  home = shm_dir / 'home'
  codex_dir = home / '.codex'
  codex_dir.mkdir(parents=True)
  bad_cfg = codex_dir / 'config.toml'
  bad_cfg.write_text('not = [valid', encoding='utf-8')

  findings = preflight_codex(home, home=home, environ={})
  assert len(findings) == 1
  assert findings[0].startswith(
    f'Invalid TOML in Codex home config ({bad_cfg}):'
  )
