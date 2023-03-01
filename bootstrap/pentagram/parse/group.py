from __future__ import annotations

from dataclasses import dataclass
from pentagram.parse.line import Line


@dataclass(frozen=True, kw_only=False)
class Group:
    items: list[Line | Group]


def parse_group(lines: list[Line]) -> Group:
    groups = [Group([])]
    substantial_indent_level = 0

    def group_end(indent_level: int) -> None:
        while indent_level < len(groups) - 1:
            groups[-2].items.append(groups.pop())

    for line in lines:
        if not line:
            indent_level = substantial_indent_level
        else:
            assert line.indent % 2 == 0, line
            indent_level = line.indent // 2
            assert indent_level <= len(groups), line
            substantial_indent_level = indent_level
        if indent_level == len(groups):
            groups.append(Group([]))
        group_end(indent_level)
        groups[-1].items.append(line)

    group_end(0)
    return groups[0]
