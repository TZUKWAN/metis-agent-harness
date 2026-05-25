"""Central tool registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from metis.tools.spec import ToolSpec


@dataclass
class ToolFilter:
    names: set[str] | None = None
    categories: set[str] | None = None
    side_effects: set[str] | None = None

    def allows(self, spec: ToolSpec) -> bool:
        if self.names is not None and spec.name not in self.names:
            return False
        if self.categories is not None and spec.category not in self.categories:
            return False
        if self.side_effects is not None and spec.side_effect not in self.side_effects:
            return False
        return True


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec, *, overwrite: bool = False) -> None:
        if spec.name in self._tools and not overwrite:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def require(self, name: str) -> ToolSpec:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: {name}")
        return spec

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def iter_specs(self, tool_filter: ToolFilter | None = None) -> Iterable[ToolSpec]:
        for spec in self._tools.values():
            if tool_filter is None or tool_filter.allows(spec):
                yield spec

    def schemas(self, tool_filter: ToolFilter | None = None, max_tools: int | None = None) -> list[dict]:
        specs = list(self.iter_specs(tool_filter))
        specs.sort(key=lambda item: item.name)
        if max_tools is not None:
            specs = specs[:max_tools]
        return [spec.openai_schema() for spec in specs]
