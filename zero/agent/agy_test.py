import fnmatch
import json
import posixpath
import subprocess
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import click
import pytest

from zero.agent import agy
from zero.agent.common import JsonObject

HOME = Path('/home/operator')
CONFIG = HOME / '.gemini' / 'config'
PROJECT_ROOT = Path('/work/pentagram')
SYSTEM_FILE = PROJECT_ROOT / 'sys.md'
RUNTIME_DIR = Path('/runtime/pentagram-agy-0')
MODEL = 'gemini-3.8-flash-high'
SYSTEM_CONTENT = '# Pentagram agent system\n'

EXPECTED_ADAPTER = (
  '---\n'
  'name: pentagram\n'
  'description: Pentagram engineering agent governed by the '
  'repository-root system contract.\n'
  'tools:\n'
  '  - ask_question\n'
  '  - define_subagent\n'
  '  - edit_file\n'
  '  - generate_image\n'
  '  - invoke_subagent\n'
  '  - manage_subagents\n'
  '  - manage_task\n'
  '  - read_file\n'
  '  - run_command\n'
  '  - run_workflow\n'
  '  - schedule\n'
  '  - search_web\n'
  '  - send_message\n'
  '  - swarm_manage\n'
  '  - swarm_post_message\n'
  '  - swarm_read_board\n'
  '  - swarm_wait\n'
  '  - write_file\n'
  'commandExecutionPolicy: eager\n'
  '---\n\n'
  '# Pentagram agent system\n'
)


@dataclass(frozen=True)
class CommandCall:
  command: tuple[str, ...]
  cwd: Path
  env: dict[str, str]
  capture_output: bool
  adapter_content: str | None


@dataclass(frozen=True)
class CommandReply:
  returncode: int = 0
  stdout: str = ''
  stderr: str = ''


@dataclass(frozen=True)
class LaunchOutcome:
  exit_code: int | None
  error: str | None
  calls: tuple[CommandCall, ...] = ()
  remaining_runtime_files: tuple[Path, ...] = ()


def _norm(path: Path) -> Path:
  return Path(posixpath.normpath(str(path)))


def _json_text(value: JsonObject) -> str:
  return json.dumps(value)


def _launch_command(
  *arguments: str, model: str = MODEL
) -> tuple[str, ...]:
  return (
    'agy',
    '--new-project',
    '--add-dir',
    str(RUNTIME_DIR),
    '--agent',
    'pentagram',
    '--model',
    model,
    '--dangerously-skip-permissions',
    *arguments,
  )


def _probe_command(model: str = MODEL) -> tuple[str, ...]:
  return (
    'agy',
    '--new-project',
    '--add-dir',
    str(RUNTIME_DIR),
    '--agent',
    'pentagram',
    '--model',
    model,
    '--output-format',
    'stream-json',
    '--print',
    'Reply OK and do not call any tools.',
  )


def _run_launch(
  monkeypatch: pytest.MonkeyPatch,
  *,
  files: Mapping[Path, str] | None = None,
  dirs: Sequence[Path] = (),
  other_paths: Sequence[Path] = (),
  environ: Mapping[str, str] | None = None,
  arguments: Sequence[str] = (),
  model: str = MODEL,
  replies: Sequence[CommandReply] = (CommandReply(0),),
) -> LaunchOutcome:
  virtual_files: dict[Path, str] = {SYSTEM_FILE: SYSTEM_CONTENT}
  if files is not None:
    for path, content in files.items():
      virtual_files[_norm(path)] = content

  virtual_others = {_norm(path) for path in other_paths}
  virtual_dirs = {_norm(HOME), _norm(PROJECT_ROOT)}
  for directory in dirs:
    virtual_dirs.add(_norm(directory))
  for entry in (*virtual_files, *virtual_dirs.copy(), *virtual_others):
    virtual_dirs.update(_norm(parent) for parent in entry.parents)
  virtual_dirs -= set(virtual_files) | virtual_others

  env_map = dict(environ) if environ is not None else {'PATH': '/usr/bin'}
  reply_queue = deque(replies)
  calls: list[CommandCall] = []
  runtime_counter = 0

  def path_kind(path: Path) -> agy.PathKind:
    normalized = _norm(path)
    if normalized in virtual_files:
      return 'file'
    if normalized in virtual_dirs:
      return 'dir'
    if normalized in virtual_others:
      return 'other'
    return 'missing'

  def read_text(path: Path) -> str:
    normalized = _norm(path)
    if normalized not in virtual_files:
      raise FileNotFoundError(normalized)
    return virtual_files[normalized]

  def rglob(root: Path, pattern: str) -> tuple[Path, ...]:
    normalized_root = _norm(root)
    candidates = sorted(
      path
      for path in (*virtual_files, *virtual_dirs)
      if normalized_root in path.parents
      and fnmatch.fnmatchcase(path.name, pattern)
    )
    return tuple(candidates)

  @contextmanager
  def runtime_adapter(agent_content: str) -> Iterator[Path]:
    nonlocal runtime_counter
    runtime_dir = Path(f'/runtime/pentagram-agy-{runtime_counter}')
    runtime_counter += 1
    adapter_file = (
      runtime_dir / '.agents' / 'agents' / 'pentagram' / 'agent.md'
    )
    virtual_files[adapter_file] = agent_content
    virtual_dirs.update(_norm(parent) for parent in adapter_file.parents)
    try:
      yield runtime_dir
    finally:
      virtual_files.pop(adapter_file, None)

  def run_command(
    command: Sequence[str],
    cwd: Path,
    env: Mapping[str, str],
    capture_output: bool,
  ) -> subprocess.CompletedProcess[str]:
    runtime_arg = Path(command[command.index('--add-dir') + 1])
    adapter_file = (
      _norm(runtime_arg) / '.agents' / 'agents' / 'pentagram' / 'agent.md'
    )
    calls.append(
      CommandCall(
        command=tuple(command),
        cwd=_norm(cwd),
        env=dict(env),
        capture_output=capture_output,
        adapter_content=virtual_files.get(adapter_file),
      )
    )
    reply = reply_queue.popleft()
    return subprocess.CompletedProcess(
      list(command), reply.returncode, reply.stdout, reply.stderr
    )

  host = agy._Host(
    home=_norm(HOME),
    environ=env_map,
    resolve=_norm,
    path_kind=path_kind,
    read_text=read_text,
    rglob=rglob,
    runtime_adapter=runtime_adapter,
    run_command=run_command,
  )
  monkeypatch.setattr(agy, '_os_host', lambda: host)

  exit_code: int | None = None
  error: str | None = None
  try:
    agy.launch(PROJECT_ROOT, SYSTEM_FILE, arguments, model)
  except click.exceptions.Exit as exit_exc:
    exit_code = exit_exc.exit_code
  except click.ClickException as click_exc:
    error = str(click_exc)

  remaining_runtime = tuple(
    sorted(
      path for path in virtual_files if str(path).startswith('/runtime/')
    )
  )
  return LaunchOutcome(
    exit_code=exit_code,
    error=error,
    calls=tuple(calls),
    remaining_runtime_files=remaining_runtime,
  )


def test_launch_builds_adapter_ignores_non_ambient_paths_and_exits(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  outcome = _run_launch(
    monkeypatch,
    files={
      CONFIG / 'mcp_config.json': '  \n',
      HOME
      / '.gemini'
      / 'antigravity-cli'
      / 'builtin'
      / 'skills'
      / 'native_swarm'
      / 'SKILL.md': 'builtin\n',
      PROJECT_ROOT
      / '.gemini'
      / 'config'
      / 'skills'
      / 'local'
      / 'SKILL.md': 'local\n',
      PROJECT_ROOT / '.agents' / 'rules' / 'local.md': 'local\n',
    },
    environ={'PATH': '/usr/bin'},
    arguments=('--resume', 'session-1'),
    replies=(CommandReply(returncode=7),),
  )

  assert outcome == LaunchOutcome(
    exit_code=7,
    error=None,
    calls=(
      CommandCall(
        command=_launch_command('--resume', 'session-1'),
        cwd=PROJECT_ROOT,
        env={'PATH': '/usr/bin'},
        capture_output=False,
        adapter_content=EXPECTED_ADAPTER,
      ),
    ),
  )


@pytest.mark.parametrize(
  ('files', 'environ', 'expected_skill'),
  (
    (
      {CONFIG / 'skills' / 'search' / 'SKILL.md': 'skill\n'},
      {'PATH': '/usr/bin'},
      CONFIG / 'skills' / 'search' / 'SKILL.md',
    ),
    (
      {
        CONFIG / 'skills.json': _json_text(
          {'inherits': [{'path': '$SHARED_REG/skills.json'}]}
        ),
        Path('/opt/agy/skills.json'): _json_text(
          {'entries': [{'path': '~/shared/skills'}]}
        ),
        HOME / 'shared' / 'skills' / 'search' / 'SKILL.md': 'skill\n',
      },
      {'PATH': '/usr/bin', 'SHARED_REG': '/opt/agy'},
      HOME / 'shared' / 'skills' / 'search' / 'SKILL.md',
    ),
  ),
  ids=('standard-skill', 'inherited-env-and-home-skill'),
)
def test_preflight_rejects_standard_and_inherited_skills(
  monkeypatch: pytest.MonkeyPatch,
  files: Mapping[Path, str],
  environ: Mapping[str, str],
  expected_skill: Path,
) -> None:
  outcome = _run_launch(monkeypatch, files=files, environ=environ)

  assert outcome == LaunchOutcome(
    exit_code=None,
    error=(
      'AGY filesystem preflight failed:\n'
      f'  - AGY skill {expected_skill} is present; remove it or '
      'deregister its path because AGY has no persistent all-skills '
      'disable setting'
    ),
  )


@pytest.mark.parametrize(
  ('files', 'expected_rule'),
  (
    ({HOME / 'AGENTS.md': 'rule\n'}, HOME / 'AGENTS.md'),
    ({HOME / 'GEMINI.md': 'rule\n'}, HOME / 'GEMINI.md'),
    (
      {HOME / '.gemini' / 'AGENTS.md': 'rule\n'},
      HOME / '.gemini' / 'AGENTS.md',
    ),
    (
      {HOME / '.gemini' / 'GEMINI.md': 'rule\n'},
      HOME / '.gemini' / 'GEMINI.md',
    ),
    (
      {HOME / '.gemini' / 'rules' / 'execution.md': 'rule\n'},
      HOME / '.gemini' / 'rules' / 'execution.md',
    ),
    (
      {HOME / '.agents' / 'rules' / 'execution.md': 'rule\n'},
      HOME / '.agents' / 'rules' / 'execution.md',
    ),
    (
      {CONFIG / 'rules' / 'execution.md': 'rule\n'},
      CONFIG / 'rules' / 'execution.md',
    ),
    (
      {
        CONFIG / 'rules.json': _json_text(
          {'entries': [{'path': 'shared-rules'}]}
        ),
        CONFIG / 'shared-rules' / 'execution.md': 'rule\n',
      },
      CONFIG / 'shared-rules' / 'execution.md',
    ),
  ),
  ids=(
    'home-agents',
    'home-gemini',
    'gemini-agents',
    'gemini-gemini',
    'gemini-rules',
    'agents-rules',
    'config-rules',
    'registered-relative-rules',
  ),
)
def test_preflight_rejects_each_ambient_rule_location(
  monkeypatch: pytest.MonkeyPatch,
  files: Mapping[Path, str],
  expected_rule: Path,
) -> None:
  outcome = _run_launch(monkeypatch, files=files)

  assert outcome == LaunchOutcome(
    exit_code=None,
    error=(
      'AGY filesystem preflight failed:\n'
      f'  - AGY rule file {expected_rule} is present; remove or rename it '
      'because AGY has no persistent setting to disable AGENTS.md/rules '
      'files'
    ),
  )


def test_preflight_applies_inherited_include_and_exclude_filters(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  base_files: dict[Path, str] = {
    CONFIG / 'skills.json': _json_text(
      {
        'inherits': [
          {
            'path': str(CONFIG / 'inherited-skills.json'),
            'include_only': ['team', 'shared'],
          }
        ]
      }
    ),
    CONFIG / 'inherited-skills.json': _json_text(
      {
        'entries': [
          {
            'path': '/shared/skills',
            'include_only': ['search'],
            'exclude': ['private'],
          }
        ]
      }
    ),
    CONFIG / 'rules.json': _json_text(
      {
        'entries': [
          {
            'path': '/shared/rules',
            'include_only': ['policy'],
            'exclude': ['draft'],
          }
        ]
      }
    ),
    Path('/shared/skills/team-private-search/SKILL.md'): 'excluded\n',
    Path('/shared/skills/team-docs/SKILL.md'): 'unmatched\n',
    Path('/shared/skills/solo-search/SKILL.md'): 'missing-group\n',
    Path('/shared/rules/draft-policy.md'): 'excluded\n',
    Path('/shared/rules/notes.md'): 'unmatched\n',
  }

  filtered_outcome = _run_launch(monkeypatch, files=base_files)
  assert filtered_outcome == LaunchOutcome(
    exit_code=0,
    error=None,
    calls=(
      CommandCall(
        command=_launch_command(),
        cwd=PROJECT_ROOT,
        env={'PATH': '/usr/bin'},
        capture_output=False,
        adapter_content=EXPECTED_ADAPTER,
      ),
    ),
  )

  matched_outcome = _run_launch(
    monkeypatch,
    files={
      **base_files,
      Path('/shared/skills/shared-search/SKILL.md'): 'active\n',
      Path('/shared/rules/active-policy.md'): 'active\n',
    },
  )
  assert matched_outcome == LaunchOutcome(
    exit_code=None,
    error=(
      'AGY filesystem preflight failed:\n'
      '  - AGY skill /shared/skills/shared-search/SKILL.md is present; '
      'remove it or deregister its path because AGY has no persistent '
      'all-skills disable setting\n'
      '  - AGY rule file /shared/rules/active-policy.md is present; '
      'remove or rename it because AGY has no persistent setting to '
      'disable AGENTS.md/rules files'
    ),
  )


@pytest.mark.parametrize(
  ('files', 'expected'),
  (
    (
      {
        CONFIG / 'plugins' / 'example' / 'plugin.json': _json_text(
          {'disabled': True}
        )
      },
      LaunchOutcome(
        exit_code=0,
        error=None,
        calls=(
          CommandCall(
            command=_launch_command(),
            cwd=PROJECT_ROOT,
            env={'PATH': '/usr/bin'},
            capture_output=False,
            adapter_content=EXPECTED_ADAPTER,
          ),
        ),
      ),
    ),
    (
      {
        CONFIG / 'plugins' / 'example' / 'plugin.json': _json_text(
          {'disabled': True}
        ),
        CONFIG / 'config.json': _json_text(
          {'plugins': {'example': {'enabled': True}}}
        ),
      },
      LaunchOutcome(
        exit_code=None,
        error=(
          'AGY filesystem preflight failed:\n'
          "  - AGY plugin 'example' is enabled; set "
          f"plugins['example'].enabled = false in {CONFIG / 'config.json'}"
        ),
      ),
    ),
    (
      {
        CONFIG / 'plugins' / 'example' / 'plugin.json': _json_text(
          {'disabled': False}
        ),
        CONFIG / 'config.json': _json_text(
          {'plugins': {'example': {'enabled': False}}}
        ),
      },
      LaunchOutcome(
        exit_code=0,
        error=None,
        calls=(
          CommandCall(
            command=_launch_command(),
            cwd=PROJECT_ROOT,
            env={'PATH': '/usr/bin'},
            capture_output=False,
            adapter_content=EXPECTED_ADAPTER,
          ),
        ),
      ),
    ),
    (
      {
        CONFIG / 'plugins.json': _json_text(
          {'inherits': [{'path': str(CONFIG / 'inherited-plugins.json')}]}
        ),
        CONFIG / 'inherited-plugins.json': _json_text(
          {'entries': [{'path': '/shared/plugins'}]}
        ),
        Path('/shared/plugins/unsafe/plugin.json'): _json_text({}),
      },
      LaunchOutcome(
        exit_code=None,
        error=(
          'AGY filesystem preflight failed:\n'
          "  - AGY plugin 'unsafe' is enabled; set "
          f"plugins['unsafe'].enabled = false in {CONFIG / 'config.json'}"
        ),
      ),
    ),
  ),
  ids=(
    'manifest-disabled',
    'override-enabled-blocks',
    'override-disabled-allows',
    'inherited-plugin-blocks',
  ),
)
def test_preflight_enforces_plugin_manifest_and_override_states(
  monkeypatch: pytest.MonkeyPatch,
  files: Mapping[Path, str],
  expected: LaunchOutcome,
) -> None:
  outcome = _run_launch(monkeypatch, files=files)

  assert outcome == expected


def test_preflight_rejects_configured_mcp_servers_before_launch(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  outcome = _run_launch(
    monkeypatch,
    files={
      CONFIG / 'mcp_config.json': _json_text(
        {
          'mcpServers': {
            'search': {'command': 'search-server'},
            'docs': {'command': 'docs-server'},
          }
        }
      )
    },
  )

  assert outcome == LaunchOutcome(
    exit_code=None,
    error=(
      'AGY filesystem preflight failed:\n'
      f"  - AGY MCP server 'docs' is configured in "
      f'{CONFIG / "mcp_config.json"}; remove it because AGY has no '
      'persistent all-MCP disable setting\n'
      f"  - AGY MCP server 'search' is configured in "
      f'{CONFIG / "mcp_config.json"}; remove it because AGY has no '
      'persistent all-MCP disable setting'
    ),
  )


def test_preflight_reports_cyclic_inheritance_and_invalid_mcp_path(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  outcome = _run_launch(
    monkeypatch,
    files={
      CONFIG / 'skills.json': _json_text(
        {'inherits': [{'path': str(CONFIG / 'cycle.json')}]}
      ),
      CONFIG / 'cycle.json': _json_text(
        {'inherits': [{'path': str(CONFIG / 'skills.json')}]}
      ),
    },
    dirs=(CONFIG / 'mcp_config.json',),
  )

  assert outcome == LaunchOutcome(
    exit_code=None,
    error=(
      'AGY filesystem preflight failed:\n'
      f'  - Cyclic AGY skills config inheritance at '
      f'{CONFIG / "skills.json"}\n'
      f'  - AGY MCP configuration path is not a file: '
      f'{CONFIG / "mcp_config.json"}'
    ),
  )


def test_toolset_preflight_validates_pentagram_adapter_and_launches(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  env = {'PATH': '/usr/bin', agy.AGY_TOOLSET_ENV: '1'}
  probe_stdout = '\n'.join(
    (
      json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
      json.dumps({'event': 'result', 'result': {'status': 'SUCCESS'}}),
    )
  )

  outcome = _run_launch(
    monkeypatch,
    environ=env,
    arguments=('--print', 'hi'),
    replies=(
      CommandReply(returncode=0, stdout=probe_stdout),
      CommandReply(returncode=0),
    ),
  )

  assert outcome == LaunchOutcome(
    exit_code=0,
    error=None,
    calls=(
      CommandCall(
        command=_probe_command(),
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        adapter_content=EXPECTED_ADAPTER,
      ),
      CommandCall(
        command=_launch_command('--print', 'hi'),
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=False,
        adapter_content=EXPECTED_ADAPTER,
      ),
    ),
  )


@pytest.mark.parametrize(
  ('reply', 'expected_error'),
  (
    (
      CommandReply(
        returncode=3,
        stdout='\n'.join(
          (
            json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
            json.dumps(
              {
                'event': 'result',
                'result': {
                  'status': 'ERROR',
                  'error': (
                    'failed to construct executor: unknown component: '
                    'tool "bogus" not found in registry'
                  ),
                },
              }
            ),
          )
        ),
        stderr='error: failed to construct executor\n',
      ),
      (
        'AGY tool preflight failed: failed to construct executor: '
        'unknown component: tool "bogus" not found in registry'
      ),
    ),
    (
      CommandReply(returncode=2, stdout='', stderr='auth expired\n'),
      'AGY tool preflight failed: auth expired',
    ),
    (
      CommandReply(
        returncode=0,
        stdout='\n'.join(
          (
            json.dumps({'event': 'init', 'init': {'agent': 'default'}}),
            json.dumps(
              {'event': 'result', 'result': {'status': 'SUCCESS'}}
            ),
          )
        ),
      ),
      'AGY tool preflight did not initialize the pentagram custom agent',
    ),
    (
      CommandReply(
        returncode=0,
        stdout=json.dumps(
          {'event': 'init', 'init': {'agent': 'pentagram'}}
        ),
      ),
      'AGY tool preflight returned no stream-json result event',
    ),
    (
      CommandReply(
        returncode=0,
        stdout='\n'.join(
          (
            json.dumps({'event': 'init', 'init': {'agent': 'pentagram'}}),
            json.dumps(
              {
                'event': 'result',
                'result': {'status': 'CANCELLED'},
              }
            ),
          )
        ),
      ),
      "AGY tool preflight failed: unexpected result status 'CANCELLED'",
    ),
  ),
  ids=(
    'executor-component-error',
    'stderr-failure',
    'wrong-agent',
    'missing-result-event',
    'non-success-result',
  ),
)
def test_toolset_preflight_stops_before_session_on_invalid_probe(
  monkeypatch: pytest.MonkeyPatch,
  reply: CommandReply,
  expected_error: str,
) -> None:
  env = {'PATH': '/usr/bin', agy.AGY_TOOLSET_ENV: '1'}
  outcome = _run_launch(monkeypatch, environ=env, replies=(reply,))

  assert outcome == LaunchOutcome(
    exit_code=None,
    error=expected_error,
    calls=(
      CommandCall(
        command=_probe_command(),
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        adapter_content=EXPECTED_ADAPTER,
      ),
    ),
  )
