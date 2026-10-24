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
    input_schema: dict[str, type] | None = None
    output_validator: Callable[[Any], bool] | None = None
    timeout_seconds: float = 30.0
    max_retries: int = 0
    audit_required: bool = True


class ToolRegistry:
    def __init__(self, max_calls: int = 20) -> None:
        self._tools: dict[str, Tool] = {}
        self._calls = 0
        self._max_calls = max_calls

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
        if self._calls >= self._max_calls:
            raise RuntimeError("tool-call budget exhausted")
        if tool.input_schema:
            unknown = set(args) - set(tool.input_schema)
            missing = set(tool.input_schema) - set(args)
            if unknown or missing or any(not isinstance(args[key], expected) for key, expected in tool.input_schema.items()):
                raise ValueError("tool arguments do not match the registered schema")
        self._calls += 1
        result = tool.handler(args)
        if result is None or (tool.output_validator and not tool.output_validator(result)):
            raise ValueError("tool returned an invalid output")
        return result

    @property
    def calls_remaining(self) -> int:
        return max(0, self._max_calls - self._calls)
