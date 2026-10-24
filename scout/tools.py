"""Minimal typed, explicit internal tool registry. No dynamic tool loading."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    read_only: bool
    permission: str
    handler: Callable[[dict[str, Any]], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError("tool name must be non-empty and unique")
        self._tools[tool.name] = tool

    def names_for(self, permissions: set[str]) -> tuple[str, ...]:
        return tuple(sorted(name for name, tool in self._tools.items() if tool.permission in permissions))

    def call(self, name: str, args: dict[str, Any], permissions: set[str]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError("tool is not registered")
        if tool.permission not in permissions:
            raise PermissionError("permission denied")
        if not isinstance(args, dict):
            raise ValueError("tool arguments must be an object")
        result = tool.handler(args)
        if result is None:
            raise ValueError("tool returned an invalid empty result")
        return result
