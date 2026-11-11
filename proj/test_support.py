from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from proj import storage


@dataclass(frozen=True)
class ProjectWorld:
  root: Path
  name: str
  stage_id: int
  task_id: int


def rewrite_project_database(
  path: Path,
  trigger_names: Sequence[str],
  statement: str,
  parameters: Sequence[object] = (),
  ignore_check_constraints: bool = False,
) -> None:
  connection = storage.connect(':memory:')
  try:
    connection.deserialize(path.read_bytes())
    trigger_sql = {
      row['name']: row['sql']
      for row in connection.execute(
        'SELECT name, sql FROM sqlite_master '
        'WHERE type = ? AND name IN ('
        + ', '.join('?' for _ in trigger_names)
        + ')',
        ('trigger', *trigger_names),
      )
    }
    if set(trigger_sql) != set(trigger_names):
      raise AssertionError(
        f'Expected existing triggers {trigger_names}; '
        f'found {tuple(sorted(trigger_sql))}'
      )
    for trigger_name in trigger_names:
      connection.execute(f'DROP TRIGGER "{trigger_name}"')
    connection.commit()
    if ignore_check_constraints:
      connection.execute('PRAGMA ignore_check_constraints = ON')
    connection.execute(statement, parameters)
    connection.commit()
    for trigger_name in trigger_names:
      connection.execute(trigger_sql[trigger_name])
    connection.commit()
    path.write_bytes(connection.serialize())
  finally:
    connection.close()
