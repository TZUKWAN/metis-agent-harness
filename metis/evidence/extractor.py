"""Extract typed evidence from tool results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExtractedEvidence:
    claim: str
    source_type: str
    source_ref: str
    metadata: dict[str, Any]


class ToolEvidenceExtractor:
    def extract(self, tool_result: Any) -> list[ExtractedEvidence]:
        name = self._name(tool_result)
        content = self._content(tool_result)
        status = self._status(tool_result)
        parsed = self._parse_json(content)
        evidence: list[ExtractedEvidence] = []

        if name in {"run_shell", "run_command", "run_test"}:
            command = self._command_text(parsed.get("command") or parsed.get("command_text") or parsed.get("cmd") or "")
            stdout = str(parsed.get("stdout") or content)
            exit_code = parsed.get("exit_code")
            claim = f"Command executed: {command or 'run_shell'}"
            if "pytest" in command.lower() or "pytest" in stdout.lower():
                claim = f"Test command executed: {command or 'pytest'}"
            evidence.append(
                ExtractedEvidence(
                    claim=claim,
                    source_type="test" if name == "run_test" or "pytest" in command.lower() else "command",
                    source_ref=command or name,
                    metadata={
                        "tool": name,
                        "status": status,
                        "exit_code": exit_code,
                        "stdout": stdout[:1000],
                        "passed": parsed.get("passed"),
                    },
                )
            )
        elif name in {"write_file", "edit_file", "apply_patch"}:
            path = str(parsed.get("path") or parsed.get("file") or "")
            evidence.append(
                ExtractedEvidence(
                    claim=f"File modified: {path or name}",
                    source_type="tool_output",
                    source_ref=path or name,
                    metadata={"tool": name, "status": status},
                )
            )
        return evidence

    @staticmethod
    def _name(tool_result: Any) -> str:
        if isinstance(tool_result, dict):
            return str(tool_result.get("tool_name") or tool_result.get("name") or "")
        return str(getattr(tool_result, "tool_name", getattr(tool_result, "name", "")))

    @staticmethod
    def _content(tool_result: Any) -> str:
        if isinstance(tool_result, dict):
            return str(tool_result.get("content", ""))
        return str(getattr(tool_result, "content", ""))

    @staticmethod
    def _status(tool_result: Any) -> str:
        if isinstance(tool_result, dict):
            return str(tool_result.get("status", ""))
        return str(getattr(tool_result, "status", ""))

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _command_text(command: Any) -> str:
        if isinstance(command, list):
            return " ".join(str(item) for item in command)
        return str(command)
