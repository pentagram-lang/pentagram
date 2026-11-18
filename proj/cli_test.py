from __future__ import annotations

import base64
import json
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner

from proj.cli import project_group


@pytest.fixture
def shm_root() -> Iterator[Path]:
  d = Path(tempfile.mkdtemp(prefix='proj-cli-test-', dir='/dev/shm'))
  try:
    yield d
  finally:
    shutil.rmtree(d, ignore_errors=True)


def _invoke(
  runner: CliRunner, root: Path, args: list[str]
) -> tuple[int, str]:
  res = runner.invoke(project_group, ['--root', str(root), *args])
  return res.exit_code, res.output


def test_cli_end_to_end_workflow(shm_root: Path) -> None:
  runner = CliRunner()

  code, out = _invoke(
    runner,
    shm_root,
    [
      'create',
      'alpha',
      '--objective',
      'Build CLI',
      '--scope',
      'Core',
      '--non-goals',
      'GUI',
      '--constraints',
      'Strict',
      '--acceptance',
      'Tests pass',
      '--json',
    ],
  )
  assert code == 0
  assert json.loads(out)['charter_complete'] is True

  code, out = _invoke(
    runner, shm_root, ['update', 'alpha', '--summary', 'Started', '--json']
  )
  assert code == 0 and json.loads(out)['summary'] == 'Started'

  code, out = _invoke(runner, shm_root, ['list', '--json'])
  assert code == 0 and [x['name'] for x in json.loads(out)] == ['alpha']

  code, out = _invoke(
    runner,
    shm_root,
    [
      'stage',
      'create',
      'alpha',
      's1',
      '--outcome',
      'Stage 1 done',
      '--exit-evidence',
      'Ev 1',
      '--json',
    ],
  )
  assert code == 0 and json.loads(out)['name'] == 's1'

  code, out = _invoke(
    runner,
    shm_root,
    [
      'stage',
      'create',
      'alpha',
      's2',
      '--outcome',
      'Stage 2 done',
      '--depends-on',
      's1',
      '--json',
    ],
  )
  assert code == 0 and json.loads(out)['dependencies'] == [1]

  code, out = _invoke(
    runner,
    shm_root,
    [
      'stage',
      'update',
      'alpha',
      's1',
      '--stage-name',
      'stage-one',
      '--json',
    ],
  )
  assert code == 0 and json.loads(out)['name'] == 'stage-one'

  goal_txt = 'Deliver\nalpha!'
  code, out = _invoke(
    runner,
    shm_root,
    [
      'goal',
      'create',
      'alpha',
      '--text',
      goal_txt,
      '--stage',
      'stage-one',
    ],
  )
  assert code == 0 and out.strip() == 'Goal 1: active'

  code, out = _invoke(runner, shm_root, ['goal', 'text', 'alpha'])
  assert code == 0 and out == f'{goal_txt}\n'

  code, out = _invoke(runner, shm_root, ['goal', 'copy', 'alpha'])
  b64 = base64.b64encode(goal_txt.encode('utf-8')).decode('ascii')
  assert code == 0 and out == f'\x1b]52;c;{b64}\x07'

  code, out = _invoke(
    runner,
    shm_root,
    [
      'task',
      'create',
      'alpha',
      '--title',
      'T1',
      '--stage',
      'stage-one',
      '--goal',
      'active',
      '--purpose',
      'P',
      '--scope',
      'S',
      '--exclusions',
      'E',
      '--result',
      'R',
      '--completion-evidence',
      'CE',
      '--tag',
      'core',
      '--json',
    ],
  )
  assert code == 0 and json.loads(out)['tags'] == ['core']

  code, out = _invoke(
    runner, shm_root, ['task', 'ready', 'alpha', '--json']
  )
  assert code == 0 and [t['id'] for t in json.loads(out)] == [1]

  code, out = _invoke(runner, shm_root, ['task', 'activate', 'alpha', '1'])
  assert code == 0 and out.strip() == 'Task 1: active'

  code, out = _invoke(
    runner, shm_root, ['task', 'add-log', 'alpha', '1', 'Progress']
  )
  assert code == 0 and out.strip() == 'Log 2'

  code, out = _invoke(
    runner,
    shm_root,
    ['decision', 'create', 'alpha', '--summary', 'Dec 1', '--task', '1'],
  )
  assert code == 0 and out.strip() == 'Decision 1'

  code, out = _invoke(
    runner,
    shm_root,
    [
      'evidence',
      'create',
      'alpha',
      '--claim',
      'Ev 1',
      '--task',
      '1',
      '--json',
    ],
  )
  assert code == 0 and json.loads(out)['stage_id'] == 1

  code, out = _invoke(runner, shm_root, ['handoff', 'alpha', '--json'])
  hj = json.loads(out)
  assert hj['focus_kind'] == 'task' and hj['focus_id'] == 1
  assert len(hj['task_logs']) == 2

  code, out = _invoke(
    runner,
    shm_root,
    [
      'blocker',
      'create',
      'alpha',
      '--description',
      'Wait',
      '--required',
      'Go',
      '--task',
      '1',
    ],
  )
  assert code == 0 and out.strip() == 'Blocker 1: open'

  code, out = _invoke(
    runner,
    shm_root,
    ['blocker', 'resolve', 'alpha', '1', '--resolution', 'Unblocked'],
  )
  assert code == 0 and out.strip() == 'Blocker 1: resolved'

  code, out = _invoke(
    runner,
    shm_root,
    ['task', 'update', 'alpha', '1', '--no-goal', '--json'],
  )
  assert code == 0 and json.loads(out)['goal_id'] is None

  code, _ = _invoke(runner, shm_root, ['task', 'activate', 'alpha', '1'])
  assert code == 0
  code, _ = _invoke(runner, shm_root, ['task', 'complete', 'alpha', '1'])
  assert code == 0
  code, out = _invoke(
    runner,
    shm_root,
    [
      'stage',
      'achieve',
      'alpha',
      'stage-one',
      '--evidence',
      '1',
      '--json',
    ],
  )
  assert code == 0 and json.loads(out)['status'] == 'achieved'

  code, out = _invoke(
    runner,
    shm_root,
    ['decision', 'list', 'alpha', '--no-task', '--json'],
  )
  assert code == 0 and json.loads(out) == {'items': [], 'has_more': False}

  code, out = _invoke(runner, shm_root, ['archive', 'alpha', '--json'])
  assert code == 0 and Path(json.loads(out)['archive_path']).is_file()


def test_cli_error_cases(shm_root: Path) -> None:
  runner = CliRunner()
  _invoke(runner, shm_root, ['create', 'beta', '--objective', 'Beta'])
  _invoke(
    runner, shm_root, ['stage', 'create', 'beta', 's1', '--outcome', 'O']
  )
  _invoke(
    runner,
    shm_root,
    ['task', 'create', 'beta', '--title', 'T1', '--stage', 's1'],
  )

  for bad_args in (
    ['show', 'missing'],
    ['blocker', 'create', 'beta', '--description', 'D', '--required', 'R'],
    ['task', 'update', 'beta', '1', '--goal', '1', '--no-goal'],
    ['task', 'activate', 'beta', '1'],
  ):
    code, out = _invoke(runner, shm_root, bad_args)
    assert code != 0 and 'Error:' in out
