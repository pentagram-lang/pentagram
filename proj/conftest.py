import shutil
import sqlite3
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path

import pytest

from proj import project, storage
from proj.test_support import ProjectWorld

_FIXED_TIME = 1_700_000_000
_CHARTER = (
  'Deliver a reliable project workflow',
  'Project state and commands',
  'Language runtime behaviour',
  'Preserve append-only history',
  'Lifecycle tests and review',
)


@dataclass(frozen=True)
class ProjectTemplates:
  charter: Path
  world: Path
  world_ids: tuple[int, int]


@pytest.fixture(scope='session')
def project_templates(
  tmp_path_factory: pytest.TempPathFactory,
) -> Generator[ProjectTemplates]:
  patcher = pytest.MonkeyPatch()
  try:
    patcher.setattr(storage, 'current_time', lambda: _FIXED_TIME)
    patcher.setattr(project, 'current_time', lambda: _FIXED_TIME)
    connect = storage.connect

    def connect_with_fixed_sql_clock(
      path: str | Path,
    ) -> sqlite3.Connection:
      connection = connect(path)
      connection.create_function(
        'unixepoch', 0, lambda: _FIXED_TIME, deterministic=True
      )
      connection.create_function(
        'strftime',
        2,
        lambda format_value, time_value: (
          str(_FIXED_TIME)
          if format_value == '%s' and time_value == 'now'
          else None
        ),
        deterministic=True,
      )
      return connection

    patcher.setattr(storage, 'connect', connect_with_fixed_sql_clock)
    base = tmp_path_factory.mktemp('project-templates')
    charter_template = base / 'charter.sqlite3'
    world_template = base / 'world.sqlite3'

    def write_template(
      path: Path, include_world: bool
    ) -> tuple[int, int] | None:
      connection = storage.connect(':memory:')
      try:
        storage._initialize_project(connection, 'sample', *_CHARTER)
        if include_world:
          with connection:
            stage_id = connection.execute(
              """
              INSERT INTO stage
                (name, outcome, exit_evidence, position, created_at,
                 updated_at)
              VALUES (?, ?, ?, 0, ?, ?)
              """,
              (
                'Workflow',
                'Represent the lifecycle coherently',
                'A complete validation report',
                _FIXED_TIME,
                _FIXED_TIME,
              ),
            ).lastrowid
            if stage_id is None:
              raise AssertionError('Stage insert returned no row ID')
            task_id = connection.execute(
              """
              INSERT INTO task
                (stage_id, title, purpose, scope, exclusions, result,
                 completion_evidence, created_at, updated_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
              """,
              (
                stage_id,
                'Exercise the lifecycle',
                'Guard state transitions',
                'Task and stage status',
                'CLI presentation',
                'Transitions produce the documented state',
                'Exact returned lifecycle records',
                _FIXED_TIME,
                _FIXED_TIME,
              ),
            ).lastrowid
            if task_id is None:
              raise AssertionError('Task insert returned no row ID')
        path.write_bytes(connection.serialize())
        return (stage_id, task_id) if include_world else None
      finally:
        connection.close()

    write_template(charter_template, False)
    world_ids = write_template(world_template, True)
    if world_ids is None:
      raise AssertionError(
        'World template is missing its stage or task ID'
      )

    yield ProjectTemplates(charter_template, world_template, world_ids)
  finally:
    patcher.undo()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
  return tmp_path


@pytest.fixture
def chartered_project(
  project_root: Path, project_templates: ProjectTemplates
) -> str:
  destination = storage.database_path(project_root, 'sample')
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(project_templates.charter, destination)
  return 'sample'


@pytest.fixture
def project_world(
  project_root: Path, project_templates: ProjectTemplates
) -> ProjectWorld:
  destination = storage.database_path(project_root, 'sample')
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copyfile(project_templates.world, destination)
  stage_id, task_id = project_templates.world_ids
  return ProjectWorld(project_root, 'sample', stage_id, task_id)


@pytest.fixture
def project_clock(
  monkeypatch: pytest.MonkeyPatch, project_world: ProjectWorld
) -> Callable[[int], None]:
  connect = storage.connect

  def set_time(timestamp: int) -> None:
    monkeypatch.setattr(project, 'current_time', lambda: timestamp)
    monkeypatch.setattr(storage, 'current_time', lambda: timestamp)

    def connect_at_time(path: str | Path) -> sqlite3.Connection:
      connection = connect(path)
      connection.create_function(
        'unixepoch', 0, lambda: timestamp, deterministic=True
      )
      connection.create_function(
        'strftime',
        2,
        lambda format_value, time_value: (
          str(timestamp)
          if format_value == '%s' and time_value == 'now'
          else None
        ),
        deterministic=True,
      )
      return connection

    monkeypatch.setattr(storage, 'connect', connect_at_time)

  set_time(_FIXED_TIME)
  return set_time
