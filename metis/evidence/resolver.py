"""Resolve evidence records back to authoritative runtime records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvidenceResolution:
    passed: bool
    reason: str = ""


class EvidenceResolver:
    def __init__(self, *, state: Any | None = None, artifact_store: Any | None = None) -> None:
        self.state = state
        self.artifact_store = artifact_store

    def resolve(self, evidence: Any) -> EvidenceResolution:
        source_type = self._field(evidence, "source_type")
        source_ref = self._field(evidence, "source_ref")
        session_id = self._field(evidence, "session_id")
        metadata = self._metadata(evidence)

        if source_type == "artifact":
            return self._resolve_artifact(session_id, source_ref)
        if source_type in {"command", "test", "tool_output"}:
            return self._resolve_tool_backed_evidence(session_id, source_type, source_ref, metadata)
        if source_type == "file":
            return self._resolve_file(source_ref)
        if source_type in {"user_input", "web", "api", "git"}:
            return EvidenceResolution(True, f"{source_type} evidence accepted by source type")
        return EvidenceResolution(False, f"Unsupported or weak evidence source_type: {source_type}")

    def _resolve_artifact(self, session_id: str, source_ref: str) -> EvidenceResolution:
        if self.artifact_store is None:
            return EvidenceResolution(False, "Artifact evidence requires artifact_store")
        artifact = self.artifact_store.get_artifact(source_ref)
        if artifact is None:
            return EvidenceResolution(False, f"Artifact evidence source_ref not found: {source_ref}")
        if artifact.session_id != session_id:
            return EvidenceResolution(False, f"Artifact evidence source_ref belongs to another session: {source_ref}")
        if artifact.status not in {"created", "validated", "final"}:
            return EvidenceResolution(False, f"Artifact status is not accepted: {artifact.status}")
        return EvidenceResolution(True, "Artifact evidence resolved")

    def _resolve_tool_backed_evidence(
        self,
        session_id: str,
        source_type: str,
        source_ref: str,
        metadata: dict[str, Any],
    ) -> EvidenceResolution:
        if self.state is None:
            return EvidenceResolution(False, f"{source_type} evidence requires state store")
        calls = self.state.list_tool_calls(session_id)
        for call in calls:
            if call.get("status") != "ok":
                continue
            result = self._parse_result(call.get("result", ""))
            command_text = self._command_text(result.get("command") or result.get("command_text") or "")
            path = str(result.get("path") or result.get("file") or "")
            if source_type in {"command", "test"} and command_text == source_ref:
                exit_code = result.get("exit_code", metadata.get("exit_code"))
                if exit_code not in (0, "0", None, ""):
                    return EvidenceResolution(False, f"{source_type} evidence command did not succeed: {source_ref}")
                return EvidenceResolution(True, f"{source_type} evidence resolved")
            if source_type == "tool_output" and path == source_ref:
                return EvidenceResolution(True, "Tool output evidence resolved")
        return EvidenceResolution(False, f"{source_type} evidence source_ref not found in successful tool calls: {source_ref}")

    @staticmethod
    def _resolve_file(source_ref: str) -> EvidenceResolution:
        path = Path(source_ref)
        if path.exists():
            return EvidenceResolution(True, "File evidence resolved")
        return EvidenceResolution(False, f"File evidence source_ref not found: {source_ref}")

    @staticmethod
    def _parse_result(result: str) -> dict[str, Any]:
        try:
            data = json.loads(result or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _command_text(command: Any) -> str:
        if isinstance(command, list):
            return " ".join(str(item) for item in command)
        return str(command)

    @staticmethod
    def _field(item: Any, key: str) -> str:
        if isinstance(item, dict):
            return str(item.get(key, ""))
        return str(getattr(item, key, ""))

    @staticmethod
    def _metadata(item: Any) -> dict[str, Any]:
        metadata = item.get("metadata", {}) if isinstance(item, dict) else getattr(item, "metadata", {})
        return metadata if isinstance(metadata, dict) else {}
