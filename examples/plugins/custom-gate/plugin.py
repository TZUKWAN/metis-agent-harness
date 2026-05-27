"""Custom quality gate plugin for Metis."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from metis.plugins.api import PluginContext
from metis.quality.gates import GateResult, GateSpec


def _no_hardcoded_paths_gate(context: dict[str, Any]) -> GateResult:
    artifacts = context.get("artifacts") or []
    hardcoded: list[str] = []

    for artifact in artifacts:
        path = str(getattr(artifact, "path", artifact.get("path", "")) if hasattr(artifact, "path") else artifact.get("path", ""))
        try:
            content = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue

        # Match common absolute path patterns: /home/..., C:\..., /usr/..., etc.
        if re.search(r"(?:/[a-zA-Z0-9_]+){2,}|(?:[A-Z]:\\[^\s\"']+)", content):
            hardcoded.append(path)

    if hardcoded:
        return GateResult(
            "no_hardcoded_paths",
            False,
            f"Artifacts contain hardcoded absolute paths: {', '.join(hardcoded)}",
            {"hardcoded_artifacts": hardcoded},
        )
    return GateResult(
        "no_hardcoded_paths",
        True,
        "No hardcoded absolute paths found",
        {},
    )


def register(context: PluginContext) -> None:
    context.register_quality_gate(
        GateSpec(
            name="no_hardcoded_paths",
            description="Artifacts must not contain hardcoded absolute paths",
            handler=_no_hardcoded_paths_gate,
            failure_policy="fail",
        )
    )
