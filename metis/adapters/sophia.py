"""Sophia project adapter."""

from __future__ import annotations

from pathlib import Path

from metis.adapters.base import Adapter
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolSpec


class SophiaAdapter(Adapter):
    name = "sophia"

    def __init__(self, project_root: str | Path = r"D:\LATEXTEST\sophia-agent") -> None:
        self.project_root = Path(project_root).resolve()

    def register_tools(self, registry: ToolRegistry) -> list[ToolSpec]:
        def inspect(args: dict, context: ToolContext) -> dict:
            if not self.project_root.exists():
                raise FileNotFoundError(str(self.project_root))
            files = [path for path in self.project_root.rglob("*.py") if ".git" not in path.parts]
            research_files = [path for path in files if "research" in path.parts]
            return {
                "project": "sophia",
                "root": str(self.project_root),
                "python_files": len(files),
                "research_files": len(research_files),
                "has_task_harness": (self.project_root / "sophia" / "task_harness.py").exists(),
            }

        return [
            ToolSpec(
                "sophia_inspect_project",
                "Inspect Sophia project structure without importing business runtime.",
                {"type": "object", "properties": {}},
                inspect,
                category="adapter",
                side_effect="read",
            )
        ]

    def health_check(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.project_root.exists() and (self.project_root / "sophia" / "task_harness.py").exists(),
            "root": str(self.project_root),
            "has_task_harness": (self.project_root / "sophia" / "task_harness.py").exists(),
            "tool_count": 1,
        }
