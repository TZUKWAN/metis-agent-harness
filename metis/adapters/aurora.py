"""Aurora project adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metis.adapters.base import Adapter
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolSpec


class AuroraAdapter(Adapter):
    name = "aurora"

    def __init__(self, project_root: str | Path = r"D:\LATEXTEST\aurora-agent") -> None:
        self.project_root = Path(project_root).resolve()

    def register_tools(self, registry: ToolRegistry) -> list[ToolSpec]:
        def inspect(args: dict, context: ToolContext) -> dict:
            if not self.project_root.exists():
                raise FileNotFoundError(str(self.project_root))
            files = [path for path in self.project_root.rglob("*.py") if ".git" not in path.parts]
            tool_files = [path for path in files if "tools" in path.parts]
            return {
                "project": "aurora",
                "root": str(self.project_root),
                "python_files": len(files),
                "tool_files": len(tool_files),
                "has_agent": (self.project_root / "aurora" / "agent.py").exists(),
            }

        return [
            ToolSpec(
                "aurora_inspect_project",
                "Inspect Aurora project structure without importing business runtime.",
                {"type": "object", "properties": {}},
                inspect,
                category="adapter",
                side_effect="read",
            )
        ]

    def health_check(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.project_root.exists() and (self.project_root / "aurora" / "agent.py").exists(),
            "root": str(self.project_root),
            "has_agent": (self.project_root / "aurora" / "agent.py").exists(),
            "tool_count": 1,
        }
