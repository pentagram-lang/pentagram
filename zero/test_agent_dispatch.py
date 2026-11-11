from collections.abc import Mapping, Sequence
from pathlib import Path

import click
import pytest

from zero.agent import common, dispatch


@pytest.mark.parametrize(
  ('content', 'expected', 'expected_findings'),
  [
    (None, None, ()),
    ('{"agent": "codex"}', {'agent': 'codex'}, ()),
    (
      'not json',
      None,
      (
        'Cannot read agent state {path}: '
        'Expecting value: line 1 column 1 (char 0)',
      ),
    ),
    (
      '[]',
      None,
      ('agent state must contain a JSON object: {path}',),
    ),
  ],
  ids=('missing', 'object', 'malformed', 'wrong-shape'),
)
def test_read_json_file_reports_only_invalid_boundaries(
  tmp_path: Path,
  content: str | None,
  expected: dict[str, object] | None,
  expected_findings: tuple[str, ...],
) -> None:
  path = tmp_path / 'agent.json'
  if content is not None:
    path.write_text(content, encoding='utf-8')
  findings = []

  result = common._read_json_file(path, 'agent state', findings)

  assert result == expected
  assert findings == [
    message.format(path=path) for message in expected_findings
  ]


def test_path_boundary_helper_includes_the_root_and_descendants(
  tmp_path: Path,
) -> None:
  root = tmp_path / 'config'

  assert common._is_under(root, root)
  assert common._is_under(root / 'plugins' / 'one', root)
  assert not common._is_under(tmp_path / 'plugins', root)


def test_exec_agent_changes_directory_and_replaces_process(
  monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
  calls: list[
    tuple[str, Path] | tuple[str, str, Sequence[str], Mapping[str, str]]
  ] = []
  monkeypatch.setattr(
    common.os,
    'chdir',
    lambda path: calls.append(('chdir', path)),
  )
  monkeypatch.setattr(
    common.os,
    'execvpe',
    lambda executable, arguments, environment: calls.append(
      ('exec', executable, arguments, environment)
    ),
  )

  common._exec_agent(
    tmp_path, ['codex', '--model', 'gpt-6-astra'], ['--resume']
  )

  assert calls == [
    ('chdir', tmp_path),
    (
      'exec',
      'codex',
      ['codex', '--model', 'gpt-6-astra', '--resume'],
      common.os.environ,
    ),
  ]


def test_dispatch_selects_configured_provider_and_model(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  calls: list[tuple[Path, Path, Sequence[str], str]] = []
  monkeypatch.setattr(
    dispatch.shutil,
    'which',
    lambda executable: f'/bin/{executable}',
  )
  monkeypatch.setitem(
    dispatch._PROVIDERS,
    'codex',
    lambda root, system_file, arguments, model: calls.append(
      (root, system_file, arguments, model)
    ),
  )

  dispatch.launch('codex-astra-yolo', ['--resume', 'session'])

  assert dispatch.__file__ is not None
  root = Path(dispatch.__file__).resolve().parents[2]
  assert calls == [
    (root, root / 'sys.md', ['--resume', 'session'], 'gpt-6-astra')
  ]


def test_dispatch_rejects_a_missing_provider_executable(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setattr(dispatch.shutil, 'which', lambda _executable: None)

  with pytest.raises(click.ClickException) as error:
    dispatch.launch('codex-astra-yolo', [])

  assert str(error.value) == 'Agent executable not found on PATH: codex'
