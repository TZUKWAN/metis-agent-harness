"""Stage-aware tool routing."""

from __future__ import annotations

from dataclasses import dataclass

from metis.runtime.profiles import ModelProfile, get_model_profile
from metis.tools.registry import ToolFilter, ToolRegistry
from metis.tools.spec import ToolSpec


STAGE_CATEGORIES = {
    "explore": {"filesystem", "files", "search", "shell", "general", "test"},
    "plan": {"planning", "filesystem", "files", "general", "test"},
    "execute": {"filesystem", "files", "shell", "artifact", "general", "test"},
    "verify": {"shell", "quality", "artifact", "general", "test"},
    "finalize": {"artifact", "quality", "general", "test"},
}


@dataclass(frozen=True)
class ToolRouteRequest:
    stage: str = "execute"
    allowed_tools: list[str] | None = None
    profile: str | ModelProfile = "small"


class ToolRouter:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def route(self, request: ToolRouteRequest) -> list[ToolSpec]:
        profile = get_model_profile(request.profile)
        categories = STAGE_CATEGORIES.get(request.stage)
        names = set(request.allowed_tools) if request.allowed_tools else None
        specs = list(self.registry.iter_specs(ToolFilter(names=names, categories=categories)))
        if not specs and names is not None:
            specs = list(self.registry.iter_specs(ToolFilter(names=names)))
        specs.sort(key=lambda spec: (spec.side_effect != "read", spec.name))
        return specs[: profile.max_tools_per_turn]

    def schemas(self, request: ToolRouteRequest) -> list[dict]:
        return [spec.openai_schema() for spec in self.route(request)]
