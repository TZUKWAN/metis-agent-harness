"""Role-filtered tool registry."""

from __future__ import annotations

from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FilteredToolRegistry:
    def __init__(self, base: ToolRegistry, allowed_tools: list[str]) -> None:
        self.base = base
        self.allowed = set(allowed_tools)

    def get(self, name: str) -> ToolSpec | None:
        if name not in self.allowed:
            return None
        return self.base.get(name)

    def require(self, name: str) -> ToolSpec:
        spec = self.get(name)
        if spec is None:
            raise PermissionError(f"Tool not allowed for role: {name}")
        return spec

    def list_tools(self) -> list[str]:
        return sorted(name for name in self.base.list_tools() if name in self.allowed)

    def schemas(self, *args, **kwargs) -> list[dict]:
        return [self.base.require(name).openai_schema() for name in self.list_tools()]
