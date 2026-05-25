"""Timeline loading and CLI rendering helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_timeline(path: str | Path) -> dict[str, Any]:
    timeline_path = Path(path)
    if not timeline_path.exists():
        raise FileNotFoundError(f"Missing timeline: {timeline_path}")
    payload = json.loads(timeline_path.read_text(encoding="utf-8"))
    return normalize_timeline(payload)


def normalize_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    events = []
    task_id = str(timeline.get("task_id", ""))
    for index, event in enumerate(timeline.get("events", [])):
        normalized = dict(event)
        normalized["index"] = int(normalized.get("index", index))
        normalized["event_type"] = str(normalized.get("event_type", "unknown"))
        normalized["event_id"] = str(
            normalized.get("event_id") or f"{task_id}:{normalized['index']:03d}:{normalized['event_type']}"
        )
        events.append(normalized)
    normalized_timeline = dict(timeline)
    normalized_timeline["events"] = events
    normalized_timeline["event_count"] = len(events)
    return normalized_timeline


def timeline_to_markdown(timeline: dict[str, Any], *, include_payload: bool = False) -> str:
    timeline = normalize_timeline(timeline)
    lines = [
        "# Metis Trace Timeline",
        "",
        f"Task: {timeline.get('task_id', '')}",
        f"Status: {timeline.get('status', '')}",
        f"Success: {timeline.get('success', False)}",
        f"Event count: {timeline.get('event_count', 0)}",
    ]
    run_metadata = timeline.get("run_metadata")
    if isinstance(run_metadata, dict) and run_metadata:
        lines.extend(
            [
                f"Pre-run contract path: {run_metadata.get('pre_run_contract_path', '')}",
                f"Pre-run contract sha256: {run_metadata.get('pre_run_contract_sha256', '')}",
                f"Pre-run provenance hash: {run_metadata.get('pre_run_provenance_hash', '')}",
            ]
        )
        for label, key in (
            ("Provenance hash", "provenance_hash"),
            ("Task contract hash", "task_contract_hash"),
            ("Suite schema sha256", "suite_schema_sha256"),
        ):
            if run_metadata.get(key):
                lines.append(f"{label}: {run_metadata[key]}")
    lines.extend(["", "| Index | Event ID | Type | Status | Tool | Summary |", "|---:|---|---|---|---|---|"])
    for event in timeline.get("events", []):
        lines.append(
            "| "
            f"{event.get('index', '')} | "
            f"{_escape_table(str(event.get('event_id', '')))} | "
            f"{_escape_table(str(event.get('event_type', '')))} | "
            f"{_escape_table(str(event.get('status', '')))} | "
            f"{_escape_table(str(event.get('tool_name', '')))} | "
            f"{_escape_table(_event_summary(event))} |"
        )
    if include_payload:
        lines.extend(["", "## Event Payloads", ""])
        for event in timeline.get("events", []):
            lines.extend(
                [
                    f"### {event.get('event_id', '')}",
                    "",
                    "```json",
                    json.dumps(event, ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                    "",
                ]
            )
    return "\n".join(lines) + "\n"


def timeline_to_json(timeline: dict[str, Any]) -> str:
    return json.dumps(normalize_timeline(timeline), ensure_ascii=False, indent=2)


def timeline_event_ids(timeline: dict[str, Any]) -> list[str]:
    normalized = normalize_timeline(timeline)
    return [str(event["event_id"]) for event in normalized.get("events", []) if event.get("event_id")]


def select_critical_event(timeline: dict[str, Any]) -> dict[str, Any] | None:
    normalized = normalize_timeline(timeline)
    events = normalized.get("events", [])
    for predicate in (
        _is_failed_finalization_event,
        _is_schema_repair_hint_event,
        _is_failed_tool_event,
        _is_failed_parser_or_repair_event,
        _is_error_event,
    ):
        for event in events:
            if predicate(event):
                return event
    return events[-1] if events else None


def critical_event_id(timeline: dict[str, Any]) -> str:
    event = select_critical_event(timeline)
    return str(event.get("event_id", "")) if event else ""


def _event_summary(event: dict[str, Any]) -> str:
    if event.get("error"):
        return str(event["error"])
    if event.get("error_preview"):
        return str(event["error_preview"])
    if event.get("summary"):
        return str(event["summary"])
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        attributes = event.get("attributes")
        metadata = attributes.get("metadata") if isinstance(attributes, dict) else None
    if isinstance(metadata, dict):
        for key in ("failure_type", "policy_decision", "failure_shape_key", "schema_valid"):
            if key in metadata:
                return f"{key}={metadata[key]}"
    attributes = event.get("attributes")
    if isinstance(attributes, dict):
        hint_types = attributes.get("schema_repair_hint_types")
        if isinstance(hint_types, list) and hint_types:
            return f"schema_repair_hint_types={','.join(str(value) for value in hint_types)}"
        hint_count = attributes.get("hint_count")
        if event.get("event_type") == "schema.repair_hint" and hint_count:
            return f"schema_repair_hints={hint_count}"
        for key in ("gen_ai.operation.name", "finish_reason", "error"):
            if key in attributes:
                return f"{key}={attributes[key]}"
    if event.get("content_preview"):
        return str(event["content_preview"])
    return ""


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")[:500]


def _is_failed_finalization_event(event: dict[str, Any]) -> bool:
    if str(event.get("event_type", "")).startswith("finalization.") and event.get("status") not in {"", "ok", "final"}:
        return True
    attributes = event.get("attributes")
    return (
        event.get("event_type") == "finalization.result"
        and isinstance(attributes, dict)
        and int(attributes.get("error_count", 0) or 0) > 0
    )


def _is_failed_tool_event(event: dict[str, Any]) -> bool:
    if event.get("event_type") != "tool.result":
        return False
    attributes = event.get("attributes")
    if isinstance(attributes, dict) and attributes.get("failed") is True:
        return True
    return event.get("failed") is True or event.get("status") in {"blocked", "error"}


def _is_schema_repair_hint_event(event: dict[str, Any]) -> bool:
    if event.get("event_type") != "schema.repair_hint":
        return False
    attributes = event.get("attributes")
    if not isinstance(attributes, dict):
        return False
    return bool(attributes.get("schema_repair_hints") or attributes.get("schema_repair_hint_details"))


def _is_failed_parser_or_repair_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("event_type", ""))
    return ("parser.repair" in event_type or "repair" in event_type) and event.get("status") == "failed"


def _is_error_event(event: dict[str, Any]) -> bool:
    return event.get("event_type") in {"error", "agent.error"} or event.get("status") == "error"
