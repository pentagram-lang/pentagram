import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

type JsonValue = (
  str
  | int
  | float
  | bool
  | None
  | Sequence[JsonValue]
  | Mapping[str, JsonValue]
)
type JsonObject = Mapping[str, JsonValue]


def _json_object(value: JsonValue) -> JsonObject | None:
  if not isinstance(value, Mapping):
    return None
  return cast(JsonObject, value)


def _string_list(value: JsonValue) -> list[str] | None:
  if not isinstance(value, list):
    return None
  result: list[str] = []
  for item in value:
    if not isinstance(item, str):
      return None
    result.append(item)
  return result


def _is_under(path: Path, root: Path) -> bool:
  return path == root or root in path.parents


def _read_json_file(
  path: Path, label: str, findings: list[str]
) -> JsonObject | None:
  if not path.exists():
    return None
  if not path.is_file():
    findings.append(f'{label} path is not a file: {path}')
    return None
  try:
    value = json.loads(path.read_text())
  except (OSError, json.JSONDecodeError) as error:
    findings.append(f'Cannot read {label} {path}: {error}')
    return None
  if not isinstance(value, dict):
    findings.append(f'{label} must contain a JSON object: {path}')
    return None
  return value


def _exec_agent(
  project_root: Path, command: Sequence[str], arguments: Sequence[str]
) -> None:
  os.chdir(project_root)
  os.execvpe(command[0], [*command, *arguments], os.environ)
