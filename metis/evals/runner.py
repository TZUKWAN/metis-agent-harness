"""Agent evaluation runner."""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from metis.artifacts.store import ArtifactStore
from metis.evidence.ledger import EvidenceLedger
from metis.evals.failures import write_failure_clusters
from metis.quality.runner import QualityGateRunner
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, AgentRunResult
from metis.tools.schema_validator import ToolArgumentSchemaValidator


SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS = frozenset({"1"})


@dataclass(frozen=True)
class EvalTaskSpec:
    id: str
    prompt: str
    fixture_type: str = ""
    requires_model_execution: bool = True
    artifact_verification: dict[str, Any] = field(default_factory=dict)
    allowed_tools: list[str] = field(default_factory=list)
    max_turns: int = 12
    expected_artifacts: list[str] = field(default_factory=list)
    required_evidence_sources: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list)
    requirement_criteria: list[dict[str, Any]] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)
    require_verified_final: bool = False
    required_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    required_tool_order: list[str] = field(default_factory=list)
    required_tool_arguments: list[dict[str, Any]] = field(default_factory=list)
    max_duplicate_tool_calls: int | None = None
    max_invalid_tool_calls: int | None = None
    max_policy_blocks: int | None = None
    max_evidence_resolution_failures: int | None = None
    max_schema_violations: int | None = None
    min_schema_repair_successes: int | None = None
    max_schema_repair_failures: int | None = None
    allow_recovered_schema_failures: bool = False
    min_schema_repair_hint_successes: int | None = None
    max_schema_repair_hint_failures: int | None = None
    min_tool_repair_successes: int | None = None
    max_tool_repair_failures: int | None = None
    allow_recovered_tool_failures: bool = False
    max_retry_budget_exhaustions: int | None = None
    max_pre_dispatch_blocks: int | None = None
    required_failure_shape_keys: list[str] = field(default_factory=list)
    forbidden_failure_shape_keys: list[str] = field(default_factory=list)
    max_failure_shape_key_counts: dict[str, int] = field(default_factory=dict)


def eval_task_spec_from_dict(payload: dict[str, Any]) -> EvalTaskSpec:
    """Build an EvalTaskSpec from a JSON object while rejecting incomplete specs."""
    if not isinstance(payload, dict):
        raise TypeError("Eval task spec payload must be a JSON object.")
    allowed_fields = {field_info.name for field_info in fields(EvalTaskSpec)}
    kwargs = {key: value for key, value in payload.items() if key in allowed_fields}
    if not kwargs.get("id"):
        raise ValueError("Eval task spec is missing required field: id")
    if not kwargs.get("prompt"):
        raise ValueError("Eval task spec is missing required field: prompt")
    return EvalTaskSpec(**kwargs)


def eval_task_specs_from_suite_payload(payload: dict[str, Any] | list[dict[str, Any]]) -> list[EvalTaskSpec]:
    if isinstance(payload, list):
        raw_tasks = payload
    elif isinstance(payload, dict):
        raw_tasks = payload.get("tasks", [])
    else:
        raise TypeError("Eval suite payload must be a JSON object or list.")
    if not isinstance(raw_tasks, list):
        raise ValueError("Eval suite payload field 'tasks' must be a list.")
    specs = []
    for item in raw_tasks:
        if isinstance(item, dict) and isinstance(item.get("task_spec"), dict):
            specs.append(eval_task_spec_from_dict(_enriched_task_spec_payload(item["task_spec"], payload if isinstance(payload, dict) else {})))
        else:
            specs.append(eval_task_spec_from_dict(_enriched_task_spec_payload(item, payload if isinstance(payload, dict) else {})))
    return specs


def _enriched_task_spec_payload(task_spec: dict[str, Any], suite_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(task_spec, dict):
        return task_spec
    enriched = dict(task_spec)
    artifact_verification = enriched.get("artifact_verification")
    if not isinstance(artifact_verification, dict):
        return enriched
    target_run_dirs = dict(artifact_verification.get("target_run_dirs") or {})
    for label in artifact_verification.get("target_runs", []):
        if not isinstance(label, str) or label in target_run_dirs:
            continue
        run_summary = suite_payload.get(label)
        if isinstance(run_summary, dict) and run_summary.get("run_dir"):
            target_run_dirs[label] = str(run_summary["run_dir"])
    if target_run_dirs:
        enriched["artifact_verification"] = {**artifact_verification, "target_run_dirs": target_run_dirs}
    return enriched


def normalize_eval_suite_payload(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(payload, list):
        return {"suite": "custom-json-list", "schema_version": "unversioned", "tasks": payload, "task_count": len(payload)}
    if not isinstance(payload, dict):
        raise TypeError("Eval suite payload must be a JSON object or list.")
    schema_version = payload.get("schema_version")
    if schema_version is None:
        return dict(payload)
    if not isinstance(schema_version, str):
        raise ValueError("Eval suite schema_version must be a string.")
    if schema_version not in SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS:
        supported = ", ".join(sorted(SUPPORTED_EVAL_SUITE_SCHEMA_VERSIONS))
        raise ValueError(f"Unsupported eval suite schema_version: {schema_version}. Supported versions: {supported}.")
    return dict(payload)


def load_versioned_eval_suite_payload(path: str | Path) -> dict[str, Any]:
    suite_path = Path(path)
    if suite_path.is_dir():
        suite_path = suite_path / "targeted-eval-suite.json"
    if not suite_path.exists():
        raise FileNotFoundError(f"Missing eval suite: {suite_path}")
    payload = json.loads(suite_path.read_text(encoding="utf-8-sig"))
    return normalize_eval_suite_payload(payload)


def load_eval_task_specs(path: str | Path) -> list[EvalTaskSpec]:
    payload = load_versioned_eval_suite_payload(path)
    return eval_task_specs_from_suite_payload(payload)


@dataclass(frozen=True)
class EvalResult:
    task_id: str
    success: bool
    status: str
    turns_used: int
    tool_calls: int
    latency_seconds: float
    parser_failures: int = 0
    tool_failures: int = 0
    quality_failures: int = 0
    false_completion: bool = False
    final_verified: bool = False
    final_unverified: bool = False
    duplicate_tool_calls: int = 0
    invalid_tool_calls: int = 0
    policy_blocks: int = 0
    evidence_resolution_failures: int = 0
    schema_violations: int = 0
    schema_repair_attempts: int = 0
    schema_repair_successes: int = 0
    schema_repair_failures: int = 0
    schema_repair_hints_seen: int = 0
    schema_repair_hint_successes: int = 0
    schema_repair_hint_failures: int = 0
    schema_repair_hint_types_seen: dict[str, int] = field(default_factory=dict)
    schema_repair_hint_type_successes: dict[str, int] = field(default_factory=dict)
    schema_repair_hint_type_failures: dict[str, int] = field(default_factory=dict)
    tool_repair_attempts: int = 0
    tool_repair_successes: int = 0
    tool_repair_failures: int = 0
    tool_repair_attempts_by_type: dict[str, int] = field(default_factory=dict)
    tool_repair_successes_by_type: dict[str, int] = field(default_factory=dict)
    tool_repair_failures_by_type: dict[str, int] = field(default_factory=dict)
    tool_failure_types: dict[str, int] = field(default_factory=dict)
    retry_budget_exhaustions: int = 0
    pre_dispatch_blocks: int = 0
    failure_shape_keys: dict[str, int] = field(default_factory=dict)
    trajectory_failures: int = 0
    quality_gate_results: list[dict[str, Any]] = field(default_factory=list)
    tool_result_excerpts: list[dict[str, Any]] = field(default_factory=list)
    trace_events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvalSuiteResult:
    results: list[EvalResult]
    metadata: dict[str, Any] = field(default_factory=dict)
    task_specs: dict[str, EvalTaskSpec] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for result in self.results if result.success) / len(self.results)

    @property
    def summary(self) -> dict[str, Any]:
        task_count = len(self.results)
        schema_repair_hints_seen = sum(result.schema_repair_hints_seen for result in self.results)
        schema_repair_hint_successes = sum(result.schema_repair_hint_successes for result in self.results)
        schema_repair_hint_failures = sum(result.schema_repair_hint_failures for result in self.results)
        return {
            "task_count": task_count,
            "passed": sum(1 for result in self.results if result.success),
            "failed": sum(1 for result in self.results if not result.success),
            "schema_repair_hints_seen": schema_repair_hints_seen,
            "schema_repair_hint_successes": schema_repair_hint_successes,
            "schema_repair_hint_failures": schema_repair_hint_failures,
            "schema_repair_hint_recovery_rate": (
                schema_repair_hint_successes / schema_repair_hints_seen if schema_repair_hints_seen else 0.0
            ),
            "schema_repair_hint_types_seen": self._sum_result_maps("schema_repair_hint_types_seen"),
            "schema_repair_hint_type_successes": self._sum_result_maps("schema_repair_hint_type_successes"),
            "schema_repair_hint_type_failures": self._sum_result_maps("schema_repair_hint_type_failures"),
        }

    def to_json(self) -> str:
        return json.dumps(
            {
                "success_rate": self.success_rate,
                "summary": self.summary,
                "metadata": self.metadata,
                "results": [result.__dict__ for result in self.results],
            },
            ensure_ascii=False,
            indent=2,
        )

    def to_markdown(self) -> str:
        lines = [
            "# Metis Eval Report",
            "",
            f"Success rate: {self.success_rate:.2%}",
            "",
        ]
        if self.metadata:
            lines.extend(["## Metadata", ""])
            lines.extend(f"- {key}: {value}" for key, value in sorted(self.metadata.items()))
            lines.append("")
        summary = self.summary
        lines.extend(
            [
                "## Summary",
                "",
                f"- Tasks: {summary['task_count']}",
                f"- Passed: {summary['passed']}",
                f"- Failed: {summary['failed']}",
                f"- Schema repair hints seen: {summary['schema_repair_hints_seen']}",
                f"- Schema repair hint successes: {summary['schema_repair_hint_successes']}",
                f"- Schema repair hint failures: {summary['schema_repair_hint_failures']}",
                f"- Schema repair hint recovery rate: {summary['schema_repair_hint_recovery_rate']:.2%}",
                f"- Schema repair hint types seen: {self._format_mapping(summary['schema_repair_hint_types_seen'])}",
                f"- Schema repair hint type successes: {self._format_mapping(summary['schema_repair_hint_type_successes'])}",
                f"- Schema repair hint type failures: {self._format_mapping(summary['schema_repair_hint_type_failures'])}",
                "",
            ]
        )
        lines.extend(
            [
                "| Task | Success | Status | Turns | Tools | Parser Failures | Tool Failures | Quality Failures | False Completion | Final Verified | Final Unverified | Duplicate Tools | Invalid Tools | Policy Blocks | Evidence Resolution Failures | Schema Violations | Schema Repair Attempts | Schema Repair Successes | Schema Repair Failures | Schema Repair Hints Seen | Schema Repair Hint Successes | Schema Repair Hint Failures | Retry Budget Exhaustions | Pre-dispatch Blocks | Trajectory Failures |",
                "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for result in self.results:
            lines.append(
                "| "
                f"{result.task_id} | {result.success} | {result.status} | {result.turns_used} | "
                f"{result.tool_calls} | {result.parser_failures} | {result.tool_failures} | "
                f"{result.quality_failures} | {result.false_completion} | "
                f"{result.final_verified} | {result.final_unverified} | "
                f"{result.duplicate_tool_calls} | {result.invalid_tool_calls} | "
                f"{result.policy_blocks} | {result.evidence_resolution_failures} | "
                f"{result.schema_violations} | {result.schema_repair_attempts} | "
                f"{result.schema_repair_successes} | {result.schema_repair_failures} | "
                f"{result.schema_repair_hints_seen} | {result.schema_repair_hint_successes} | "
                f"{result.schema_repair_hint_failures} | "
                f"{result.retry_budget_exhaustions} | {result.pre_dispatch_blocks} | "
                f"{result.trajectory_failures} |"
            )
        gate_results = [result for result in self.results if result.quality_gate_results]
        lines.extend(["", "## Quality Gate Results", ""])
        if gate_results:
            for result in gate_results:
                lines.append(f"### {result.task_id}")
                lines.append("")
                for gate in result.quality_gate_results:
                    lines.append(
                        "- "
                        f"{gate.get('name', '')}: "
                        f"passed={gate.get('passed', False)}; "
                        f"message={gate.get('message', '')}"
                    )
                lines.append("")
        else:
            lines.append("- None")
        lines.extend(["", "## Failure Details", ""])
        failed_results = [result for result in self.results if not result.success]
        if not failed_results:
            lines.append("- None")
            return "\n".join(lines) + "\n"
        for result in failed_results:
            lines.extend(
                [
                    f"### {result.task_id}",
                    "",
                    f"- Status: {result.status}",
                    f"- Turns used: {result.turns_used}",
                    f"- Tool calls: {result.tool_calls}",
                    f"- Parser failures: {result.parser_failures}",
                    f"- Tool failures: {result.tool_failures}",
                    f"- Quality failures: {result.quality_failures}",
                    f"- Invalid tool calls: {result.invalid_tool_calls}",
                    f"- Schema violations: {result.schema_violations}",
                    f"- Retry budget exhaustions: {result.retry_budget_exhaustions}",
                    f"- Pre-dispatch blocks: {result.pre_dispatch_blocks}",
                    f"- Trajectory failures: {result.trajectory_failures}",
                    f"- Tool failure types: {self._format_mapping(result.tool_failure_types)}",
                    f"- Failure shape keys: {self._format_mapping(result.failure_shape_keys)}",
                    "- Errors:",
                ]
            )
            if result.errors:
                lines.extend(f"  - {error}" for error in result.errors)
            else:
                lines.append("  - None")
            lines.append("")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_mapping(mapping: dict[str, Any]) -> str:
        if not mapping:
            return "None"
        return ", ".join(f"{key}={value}" for key, value in sorted(mapping.items()))

    def _sum_result_maps(self, field_name: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.results:
            mapping = getattr(result, field_name)
            if not isinstance(mapping, dict):
                continue
            for key, value in mapping.items():
                if isinstance(key, str) and isinstance(value, int) and value:
                    counts[key] = counts.get(key, 0) + value
        return counts

    def write_reports(self, output_dir: str | Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "eval-report.json").write_text(self.to_json(), encoding="utf-8")
        (output_dir / "eval-report.md").write_text(self.to_markdown(), encoding="utf-8")
        self.write_task_specs(output_dir)
        self.write_failure_artifacts(output_dir)

    def write_task_specs(self, output_dir: str | Path) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        tasks = []
        for task_id, hashes in self.task_spec_hash_summary().items():
            task_spec = asdict(self.task_specs[task_id])
            tasks.append(
                {
                    "task_id": task_id,
                    "task_spec": task_spec,
                    "task_spec_hashes": hashes,
                }
            )
        payload = {
            "task_count": len(tasks),
            "task_contract_hash": self.task_contract_hash(),
            "task_spec_hash_summary": self.task_spec_hash_summary(),
            "tasks": tasks,
        }
        path = output_dir / "task-specs.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def task_spec_hash_summary(self) -> dict[str, dict[str, str]]:
        summary = {}
        for task_id in sorted(self.task_specs):
            task_spec = asdict(self.task_specs[task_id])
            summary[task_id] = self._task_spec_hashes(task_spec)
        return summary

    def task_contract_hash(self) -> str:
        return self._sha256_json(
            {
                "task_count": len(self.task_specs),
                "task_spec_hash_summary": self.task_spec_hash_summary(),
            }
        )

    def write_failure_artifacts(self, output_dir: str | Path) -> Path:
        output_dir = Path(output_dir)
        failures_dir = output_dir / "failures"
        failures_dir.mkdir(parents=True, exist_ok=True)
        failed_results = [result for result in self.results if not result.success]
        artifacts = []
        for result in failed_results:
            file_name = f"{self._safe_artifact_name(result.task_id)}.json"
            timeline_name = f"{self._safe_artifact_name(result.task_id)}.timeline.json"
            timeline_md_name = f"{self._safe_artifact_name(result.task_id)}.timeline.md"
            artifact_path = failures_dir / file_name
            timeline_path = failures_dir / timeline_name
            timeline_md_path = failures_dir / timeline_md_name
            payload = self._failure_artifact_payload(result)
            timeline = self._failure_timeline_payload(result)
            payload["timeline_path"] = str(timeline_path)
            artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
            timeline_md_path.write_text(self._failure_timeline_to_markdown(timeline), encoding="utf-8")
            artifacts.append(
                {
                    "task_id": result.task_id,
                    "path": str(artifact_path),
                    "timeline_path": str(timeline_path),
                    "timeline_markdown_path": str(timeline_md_path),
                    "errors": len(result.errors),
                    "has_task_spec": result.task_id in self.task_specs,
                }
            )
        index = {
            "failure_count": len(failed_results),
            "artifacts": artifacts,
        }
        (failures_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        write_failure_clusters(failures_dir)
        return failures_dir

    def _failure_artifact_payload(self, result: EvalResult) -> dict[str, Any]:
        payload = {
            "task_id": result.task_id,
            "success": result.success,
            "status": result.status,
            "turns_used": result.turns_used,
            "tool_calls": result.tool_calls,
            "latency_seconds": result.latency_seconds,
            "metrics": {
                "parser_failures": result.parser_failures,
                "tool_failures": result.tool_failures,
                "quality_failures": result.quality_failures,
                "false_completion": result.false_completion,
                "final_verified": result.final_verified,
                "final_unverified": result.final_unverified,
                "duplicate_tool_calls": result.duplicate_tool_calls,
                "invalid_tool_calls": result.invalid_tool_calls,
                "policy_blocks": result.policy_blocks,
                "evidence_resolution_failures": result.evidence_resolution_failures,
                "schema_violations": result.schema_violations,
                "schema_repair_attempts": result.schema_repair_attempts,
                "schema_repair_successes": result.schema_repair_successes,
                "schema_repair_failures": result.schema_repair_failures,
                "schema_repair_hints_seen": result.schema_repair_hints_seen,
                "schema_repair_hint_successes": result.schema_repair_hint_successes,
                "schema_repair_hint_failures": result.schema_repair_hint_failures,
                "tool_repair_attempts": result.tool_repair_attempts,
                "tool_repair_successes": result.tool_repair_successes,
                "tool_repair_failures": result.tool_repair_failures,
                "retry_budget_exhaustions": result.retry_budget_exhaustions,
                "pre_dispatch_blocks": result.pre_dispatch_blocks,
                "trajectory_failures": result.trajectory_failures,
            },
            "tool_repair_attempts_by_type": result.tool_repair_attempts_by_type,
            "tool_repair_successes_by_type": result.tool_repair_successes_by_type,
            "tool_repair_failures_by_type": result.tool_repair_failures_by_type,
            "schema_repair_hint_types_seen": result.schema_repair_hint_types_seen,
            "schema_repair_hint_type_successes": result.schema_repair_hint_type_successes,
            "schema_repair_hint_type_failures": result.schema_repair_hint_type_failures,
            "tool_failure_types": result.tool_failure_types,
            "failure_shape_keys": result.failure_shape_keys,
            "quality_gate_results": result.quality_gate_results,
            "tool_result_excerpts": result.tool_result_excerpts,
            "run_metadata": self.metadata,
            "errors": result.errors,
        }
        task_spec = self.task_specs.get(result.task_id)
        if task_spec is not None:
            task_spec_payload = asdict(task_spec)
            payload["task_spec"] = task_spec_payload
            payload["task_spec_hashes"] = self._task_spec_hashes(task_spec_payload)
        return payload

    @staticmethod
    def _failure_timeline_payload(result: EvalResult) -> dict[str, Any]:
        events: list[dict[str, Any]]
        if result.trace_events:
            events = [dict(event) for event in result.trace_events]
        else:
            events = [
                {
                    "index": 0,
                    "event_id": f"{result.task_id}:000:task.start",
                    "event_type": "task.start",
                    "task_id": result.task_id,
                    "status": "started",
                    "summary": f"Eval task {result.task_id} started.",
                }
            ]
            for excerpt in result.tool_result_excerpts:
                events.append(
                    {
                        "index": len(events),
                        "event_id": f"{result.task_id}:{len(events):03d}:tool.result",
                        "event_type": "tool.result",
                        "task_id": result.task_id,
                        "tool_index": excerpt.get("index"),
                        "tool_name": excerpt.get("tool_name", ""),
                        "tool_call_id": excerpt.get("tool_call_id", ""),
                        "status": excerpt.get("status", ""),
                        "failed": excerpt.get("failed", False),
                        "metadata": excerpt.get("metadata", {}),
                        "content_preview": excerpt.get("content_preview", ""),
                        "error_preview": excerpt.get("error_preview", ""),
                    }
                )
        for error in result.errors:
            events.append(
                {
                    "index": len(events),
                    "event_id": f"{result.task_id}:{len(events):03d}:error",
                    "event_type": "error",
                    "task_id": result.task_id,
                    "status": "failed",
                    "error": error,
                }
            )
        for gate_result in result.quality_gate_results:
            events.append(
                {
                    "index": len(events),
                    "event_id": f"{result.task_id}:{len(events):03d}:quality.gate",
                    "event_type": "quality.gate",
                    "task_id": result.task_id,
                    "status": "passed" if gate_result.get("passed", False) else "failed",
                    "gate_name": gate_result.get("name", ""),
                    "message": gate_result.get("message", ""),
                    "metadata": gate_result.get("metadata", {}),
                }
            )
        events.append(
            {
                "index": len(events),
                "event_id": f"{result.task_id}:{len(events):03d}:task.end",
                "event_type": "task.end",
                "task_id": result.task_id,
                "status": result.status,
                "success": result.success,
                "turns_used": result.turns_used,
                "tool_calls": result.tool_calls,
                "final_verified": result.final_verified,
                "final_unverified": result.final_unverified,
            }
        )
        return {
            "task_id": result.task_id,
            "success": result.success,
            "status": result.status,
            "event_count": len(events),
            "events": events,
        }

    @staticmethod
    def _failure_timeline_to_markdown(timeline: dict[str, Any]) -> str:
        lines = [
            "# Metis Failure Timeline",
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
        lines.append("")
        for event in timeline.get("events", []):
            lines.extend(
                [
                    f"## {event.get('index', 0)}. {event.get('event_type', '')}",
                    "",
                    f"- Status: {event.get('status', '')}",
                ]
            )
            if event.get("tool_name"):
                lines.append(f"- Tool: {event.get('tool_name')}")
            if event.get("tool_call_id"):
                lines.append(f"- Tool call id: {event.get('tool_call_id')}")
            if event.get("metadata"):
                lines.append(f"- Metadata: {json.dumps(event.get('metadata'), ensure_ascii=False, sort_keys=True)}")
            if event.get("error_preview"):
                lines.append(f"- Error preview: {event.get('error_preview')}")
            if event.get("error"):
                lines.append(f"- Error: {event.get('error')}")
            if event.get("event_type") == "quality.gate":
                lines.append(f"- Gate: {event.get('gate_name', '')}")
                lines.append(f"- Message: {event.get('message', '')}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _safe_artifact_name(value: str) -> str:
        safe = "".join(character if character.isalnum() or character in {"-", "_", "."} else "-" for character in value)
        safe = safe.strip(".-")
        return safe or "task"

    @staticmethod
    def _task_spec_hashes(task_spec: dict[str, Any]) -> dict[str, str]:
        constraints = {key: value for key, value in task_spec.items() if key not in {"id", "prompt"}}
        return {
            "prompt_hash": EvalSuiteResult._sha256(task_spec.get("prompt", "")),
            "constraints_hash": EvalSuiteResult._sha256_json(constraints),
            "task_spec_hash": EvalSuiteResult._sha256_json(task_spec),
        }

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _sha256_json(value: Any) -> str:
        return EvalSuiteResult._sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def annotate_failure_timelines(output_dir: str | Path, run_metadata: dict[str, Any]) -> None:
    output_dir = Path(output_dir)
    index_path = output_dir / "failures" / "index.json"
    if not index_path.exists():
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for entry in index.get("artifacts", []):
        if not isinstance(entry, dict):
            continue
        timeline_path = _resolve_output_path(output_dir, entry.get("timeline_path", ""))
        if not timeline_path or not timeline_path.exists():
            continue
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline["run_metadata"] = _timeline_run_metadata(run_metadata)
        timeline_path.write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path = _resolve_output_path(output_dir, entry.get("timeline_markdown_path", ""))
        if markdown_path and markdown_path.exists():
            markdown_path.write_text(EvalSuiteResult._failure_timeline_to_markdown(timeline), encoding="utf-8")


def _resolve_output_path(output_dir: Path, value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else output_dir / path


def _timeline_run_metadata(run_metadata: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "suite",
        "run_name",
        "requested_run_name",
        "suite_definition_type",
        "schema_version",
        "suite_schema_id",
        "suite_schema_path",
        "suite_schema_sha256",
        "task_contract_hash",
        "provenance_hash",
        "pre_run_contract_path",
        "pre_run_contract_sha256",
        "pre_run_provenance_hash",
    )
    return {key: run_metadata.get(key, "") for key in keys if run_metadata.get(key) not in (None, "")}


class EvalRunner:
    def __init__(
        self,
        *,
        loop: AgentLoop,
        artifact_store: ArtifactStore | None = None,
        evidence_ledger: EvidenceLedger | None = None,
        quality_runner: QualityGateRunner | None = None,
    ) -> None:
        self.loop = loop
        self.artifact_store = artifact_store
        self.evidence_ledger = evidence_ledger
        self.quality_runner = quality_runner or QualityGateRunner()

    async def run_task(self, task: EvalTaskSpec, *, session_id: str | None = None) -> EvalResult:
        session_id = session_id or f"eval-{task.id}"
        started = time.perf_counter()
        if not task.requires_model_execution:
            return self._run_deterministic_fixture(task, started=started)
        run_result = await self.loop.run(
            AgentRunRequest(
                session_id=session_id,
                messages=[{"role": "user", "content": task.prompt}],
                allowed_tools=task.allowed_tools or None,
                max_turns=task.max_turns,
            )
        )
        latency = time.perf_counter() - started
        quality_gate_results = self._quality_gate_results(task, session_id, run_result)
        quality_failures = self._quality_failure_count(task, session_id, quality_gate_results)
        parser_failures = sum(1 for error in run_result.errors if "ParserError" in error)
        recovered_schema_failure_indexes = self._recovered_schema_failure_indexes(run_result)
        recovered_tool_failure_indexes = self._recovered_tool_failure_indexes(run_result)
        tool_failures = sum(
            1
            for index, result in enumerate(run_result.tool_results)
            if result.failed and not (task.allow_recovered_schema_failures and index in recovered_schema_failure_indexes)
            and not (task.allow_recovered_tool_failures and index in recovered_tool_failure_indexes)
        )
        false_completion = any("Completion claim without evidence" in error for error in run_result.errors)
        duplicate_tool_calls = self._duplicate_tool_calls(session_id, run_result)
        invalid_tool_calls = self._invalid_tool_calls(run_result)
        policy_blocks = self._policy_blocks(run_result)
        evidence_resolution_failures = self._evidence_resolution_failures(run_result)
        schema_errors = self._schema_errors(session_id, run_result)
        tool_failure_types = self._tool_failure_types(run_result)
        retry_budget_exhaustions = self._retry_budget_exhaustions(run_result)
        pre_dispatch_blocks = self._pre_dispatch_blocks(run_result)
        failure_shape_keys = self._failure_shape_keys(run_result)
        schema_repair_attempts, schema_repair_successes = self._schema_repair_metrics(run_result)
        schema_repair_failures = max(0, schema_repair_attempts - schema_repair_successes)
        schema_repair_hint_metrics = self._schema_repair_hint_metrics(run_result)
        tool_repair = self._tool_repair_metrics(run_result)
        trajectory_errors = self._trajectory_errors(
            task,
            session_id,
            run_result,
            duplicate_tool_calls=duplicate_tool_calls,
            invalid_tool_calls=invalid_tool_calls,
            policy_blocks=policy_blocks,
            evidence_resolution_failures=evidence_resolution_failures,
            schema_violations=len(schema_errors),
            schema_repair_successes=schema_repair_successes,
            schema_repair_failures=schema_repair_failures,
            schema_repair_hint_successes=schema_repair_hint_metrics["successes"],
            schema_repair_hint_failures=schema_repair_hint_metrics["failures"],
            tool_repair_successes=tool_repair["successes"],
            tool_repair_failures=tool_repair["failures"],
            retry_budget_exhaustions=retry_budget_exhaustions,
            pre_dispatch_blocks=pre_dispatch_blocks,
            failure_shape_keys=failure_shape_keys,
        )
        final_verified = run_result.status == "final" and run_result.final_verified
        final_unverified = run_result.status == "final" and not run_result.final_verified
        success = (
            run_result.status == "final"
            and not parser_failures
            and not tool_failures
            and not quality_failures
            and not false_completion
            and (final_verified or not task.require_verified_final)
            and not trajectory_errors
        )
        return EvalResult(
            task_id=task.id,
            success=success,
            status=run_result.status,
            turns_used=run_result.turns_used,
            tool_calls=len(run_result.tool_results),
            latency_seconds=latency,
            parser_failures=parser_failures,
            tool_failures=tool_failures,
            quality_failures=quality_failures,
            false_completion=false_completion,
            final_verified=final_verified,
            final_unverified=final_unverified,
            duplicate_tool_calls=duplicate_tool_calls,
            invalid_tool_calls=invalid_tool_calls,
            policy_blocks=policy_blocks,
            evidence_resolution_failures=evidence_resolution_failures,
            schema_violations=len(schema_errors),
            schema_repair_attempts=schema_repair_attempts,
            schema_repair_successes=schema_repair_successes,
            schema_repair_failures=schema_repair_failures,
            schema_repair_hints_seen=schema_repair_hint_metrics["seen"],
            schema_repair_hint_successes=schema_repair_hint_metrics["successes"],
            schema_repair_hint_failures=schema_repair_hint_metrics["failures"],
            schema_repair_hint_types_seen=schema_repair_hint_metrics["types_seen"],
            schema_repair_hint_type_successes=schema_repair_hint_metrics["type_successes"],
            schema_repair_hint_type_failures=schema_repair_hint_metrics["type_failures"],
            tool_repair_attempts=tool_repair["attempts"],
            tool_repair_successes=tool_repair["successes"],
            tool_repair_failures=tool_repair["failures"],
            tool_repair_attempts_by_type=tool_repair["attempts_by_type"],
            tool_repair_successes_by_type=tool_repair["successes_by_type"],
            tool_repair_failures_by_type=tool_repair["failures_by_type"],
            tool_failure_types=tool_failure_types,
            retry_budget_exhaustions=retry_budget_exhaustions,
            pre_dispatch_blocks=pre_dispatch_blocks,
            failure_shape_keys=failure_shape_keys,
            trajectory_failures=len(trajectory_errors),
            quality_gate_results=quality_gate_results,
            tool_result_excerpts=self._tool_result_excerpts(run_result),
            trace_events=run_result.trace_events,
            errors=run_result.errors + schema_errors + trajectory_errors,
        )

    def _run_deterministic_fixture(self, task: EvalTaskSpec, *, started: float) -> EvalResult:
        if task.fixture_type == "artifact_verification":
            gate_results = self._artifact_verification_gate_results(task)
            errors = [
                str(result.get("message", ""))
                for result in gate_results
                if not result.get("passed", False) and result.get("message")
            ]
            return EvalResult(
                task_id=task.id,
                success=not errors,
                status="verified" if not errors else "failed",
                turns_used=0,
                tool_calls=0,
                latency_seconds=time.perf_counter() - started,
                quality_failures=len(errors),
                quality_gate_results=gate_results,
                errors=errors,
            )
        return EvalResult(
            task_id=task.id,
            success=False,
            status="unsupported_fixture",
            turns_used=0,
            tool_calls=0,
            latency_seconds=time.perf_counter() - started,
            quality_failures=1,
            errors=[f"Unsupported deterministic fixture type: {task.fixture_type or 'unknown'}"],
        )

    def _artifact_verification_gate_results(self, task: EvalTaskSpec) -> list[dict[str, Any]]:
        artifact_verification = task.artifact_verification if isinstance(task.artifact_verification, dict) else {}
        target_run_dirs = artifact_verification.get("target_run_dirs")
        gate_names = task.quality_gates or ["run_attestation_verifies"]
        result = self.quality_runner.run(gate_names, {"target_run_dirs": target_run_dirs})
        return self._quality_gate_result_payloads(result.results)

    @staticmethod
    def _quality_gate_result_payloads(results: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "name": str(result.name),
                "passed": bool(result.passed),
                "message": str(result.message),
                "metadata": result.metadata if isinstance(result.metadata, dict) else {},
            }
            for result in results
        ]

    async def run_suite(self, tasks: list[EvalTaskSpec], *, metadata: dict[str, Any] | None = None) -> EvalSuiteResult:
        results = [await self.run_task(task) for task in tasks]
        return EvalSuiteResult(results, metadata or {}, {task.id: task for task in tasks})

    def _quality_gate_results(self, task: EvalTaskSpec, session_id: str, run_result: AgentRunResult) -> list[dict[str, Any]]:
        artifacts = self.artifact_store.list_artifacts(session_id) if self.artifact_store else []
        evidence = self.evidence_ledger.list_evidence(session_id) if self.evidence_ledger else []
        if not task.quality_gates:
            return []
        quality = self.quality_runner.run(
            task.quality_gates,
            {
                "artifacts": artifacts,
                "evidence": evidence,
                "requirements": task.requirements,
                "requirement_criteria": task.requirement_criteria,
                "tool_results": run_result.tool_results,
                "final_text": run_result.final_text,
            },
        )
        return self._quality_gate_result_payloads(quality.results)

    def _quality_failure_count(self, task: EvalTaskSpec, session_id: str, quality_gate_results: list[dict[str, Any]]) -> int:
        artifacts = self.artifact_store.list_artifacts(session_id) if self.artifact_store else []
        evidence = self.evidence_ledger.list_evidence(session_id) if self.evidence_ledger else []
        failures = 0
        for path in task.expected_artifacts:
            if not any(str(artifact.path).endswith(path) for artifact in artifacts):
                failures += 1
        for source in task.required_evidence_sources:
            if not any(record.source_type == source for record in evidence):
                failures += 1
        failures += sum(1 for result in quality_gate_results if not result.get("passed", False))
        return failures

    def _duplicate_tool_calls(self, session_id: str, run_result: AgentRunResult) -> int:
        state = getattr(self.loop, "state", None)
        if state is not None:
            calls = state.list_tool_calls(session_id)
            seen: set[tuple[str, str]] = set()
            duplicates = 0
            for call in calls:
                key = (str(call.get("tool_name", "")), json.dumps(call.get("args", {}), sort_keys=True, ensure_ascii=False))
                if key in seen:
                    duplicates += 1
                seen.add(key)
            return duplicates

        seen_results: set[tuple[str, str]] = set()
        duplicates = 0
        for result in run_result.tool_results:
            key = (result.tool_name, result.content)
            if key in seen_results:
                duplicates += 1
            seen_results.add(key)
        return duplicates

    @staticmethod
    def _invalid_tool_calls(run_result: AgentRunResult) -> int:
        invalid_markers = (
            "Unknown tool",
            "not allowed",
            "Tool policy denied",
            "requires approval",
            "Denied dangerous shell command",
            "Tool argument schema validation failed",
        )
        return sum(
            1
            for result in run_result.tool_results
            if result.status in {"blocked", "error"} and any(marker in (result.error or result.content) for marker in invalid_markers)
        )

    @staticmethod
    def _policy_blocks(run_result: AgentRunResult) -> int:
        return sum(1 for result in run_result.tool_results if result.metadata.get("policy_decision") in {"block", "deny", "approval_required"})

    @staticmethod
    def _tool_failure_types(run_result: AgentRunResult) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in run_result.tool_results:
            failure_type = result.metadata.get("failure_type")
            if isinstance(failure_type, str) and failure_type:
                counts[failure_type] = counts.get(failure_type, 0) + 1
        return counts

    @staticmethod
    def _tool_result_excerpts(run_result: AgentRunResult, *, limit: int = 20, preview_chars: int = 500) -> list[dict[str, Any]]:
        excerpts = []
        metadata_keys = [
            "failure_type",
            "recoverable",
            "retry_allowed",
            "retry_budget_exhausted",
            "pre_dispatch_block",
            "schema_valid",
            "schema_errors",
            "failure_shape_key",
            "policy_decision",
            "repair_instruction",
            "schema_repair_hints",
            "schema_repair_hint_types",
            "schema_repair_hint_details",
        ]
        for index, result in enumerate(run_result.tool_results[:limit]):
            excerpts.append(
                {
                    "index": index,
                    "tool_name": result.tool_name,
                    "tool_call_id": result.tool_call_id,
                    "status": result.status,
                    "failed": result.failed,
                    "metadata": {
                        key: result.metadata[key]
                        for key in metadata_keys
                        if key in result.metadata
                    },
                    "content_preview": EvalRunner._preview(result.content, preview_chars),
                    "error_preview": EvalRunner._preview(result.error or "", preview_chars),
                }
            )
        return excerpts

    @staticmethod
    def _preview(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        return value[:limit] + "...[truncated]"

    @staticmethod
    def _retry_budget_exhaustions(run_result: AgentRunResult) -> int:
        return sum(1 for result in run_result.tool_results if result.metadata.get("retry_budget_exhausted") is True)

    @staticmethod
    def _pre_dispatch_blocks(run_result: AgentRunResult) -> int:
        return sum(1 for result in run_result.tool_results if result.metadata.get("pre_dispatch_block") is True)

    @staticmethod
    def _failure_shape_keys(run_result: AgentRunResult) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in run_result.tool_results:
            key = result.metadata.get("failure_shape_key")
            if isinstance(key, str) and key:
                counts[key] = counts.get(key, 0) + 1
        return counts

    @staticmethod
    def _evidence_resolution_failures(run_result: AgentRunResult) -> int:
        markers = ("Unresolved evidence ref", "Missing evidence ref", "Missing evidence refs")
        return sum(1 for error in run_result.errors if any(marker in error for marker in markers))

    def _tool_call_sequence(self, session_id: str, run_result: AgentRunResult) -> list[str]:
        state = getattr(self.loop, "state", None)
        if state is not None:
            return [str(call.get("tool_name", "")) for call in state.list_tool_calls(session_id)]
        return [result.tool_name for result in run_result.tool_results]

    def _trajectory_errors(
        self,
        task: EvalTaskSpec,
        session_id: str,
        run_result: AgentRunResult,
        *,
        duplicate_tool_calls: int,
        invalid_tool_calls: int,
        policy_blocks: int,
        evidence_resolution_failures: int,
        schema_violations: int,
        schema_repair_successes: int,
        schema_repair_failures: int,
        schema_repair_hint_successes: int,
        schema_repair_hint_failures: int,
        tool_repair_successes: int,
        tool_repair_failures: int,
        retry_budget_exhaustions: int,
        pre_dispatch_blocks: int,
        failure_shape_keys: dict[str, int],
    ) -> list[str]:
        sequence = self._tool_call_sequence(session_id, run_result)
        calls = self._tool_call_records(session_id, run_result)
        errors: list[str] = []
        missing_tools = [tool for tool in task.required_tools if tool not in sequence]
        forbidden_tools = [tool for tool in task.forbidden_tools if tool in sequence]
        if missing_tools:
            errors.append(f"Missing required tools: {', '.join(missing_tools)}")
        if forbidden_tools:
            errors.append(f"Forbidden tools were called: {', '.join(forbidden_tools)}")
        if task.required_tool_order and not self._contains_order(sequence, task.required_tool_order):
            errors.append(f"Required tool order not satisfied: {' -> '.join(task.required_tool_order)}")
        for expected in task.required_tool_arguments:
            if not self._has_matching_tool_arguments(calls, expected):
                errors.append(f"Required tool arguments not satisfied: {json.dumps(expected, ensure_ascii=False, sort_keys=True)}")
        if task.max_duplicate_tool_calls is not None and duplicate_tool_calls > task.max_duplicate_tool_calls:
            errors.append(
                f"Duplicate tool calls exceeded: {duplicate_tool_calls} > {task.max_duplicate_tool_calls}"
            )
        if task.max_invalid_tool_calls is not None and invalid_tool_calls > task.max_invalid_tool_calls:
            errors.append(f"Invalid tool calls exceeded: {invalid_tool_calls} > {task.max_invalid_tool_calls}")
        if task.max_policy_blocks is not None and policy_blocks > task.max_policy_blocks:
            errors.append(f"Policy blocks exceeded: {policy_blocks} > {task.max_policy_blocks}")
        if (
            task.max_evidence_resolution_failures is not None
            and evidence_resolution_failures > task.max_evidence_resolution_failures
        ):
            errors.append(
                "Evidence resolution failures exceeded: "
                f"{evidence_resolution_failures} > {task.max_evidence_resolution_failures}"
            )
        if task.max_schema_violations is not None and schema_violations > task.max_schema_violations:
            errors.append(f"Schema violations exceeded: {schema_violations} > {task.max_schema_violations}")
        if (
            task.min_schema_repair_successes is not None
            and schema_repair_successes < task.min_schema_repair_successes
        ):
            errors.append(
                "Schema repair successes below requirement: "
                f"{schema_repair_successes} < {task.min_schema_repair_successes}"
            )
        if task.max_schema_repair_failures is not None and schema_repair_failures > task.max_schema_repair_failures:
            errors.append(
                "Schema repair failures exceeded: "
                f"{schema_repair_failures} > {task.max_schema_repair_failures}"
            )
        if (
            task.min_schema_repair_hint_successes is not None
            and schema_repair_hint_successes < task.min_schema_repair_hint_successes
        ):
            errors.append(
                "Schema repair hint successes below requirement: "
                f"{schema_repair_hint_successes} < {task.min_schema_repair_hint_successes}"
            )
        if (
            task.max_schema_repair_hint_failures is not None
            and schema_repair_hint_failures > task.max_schema_repair_hint_failures
        ):
            errors.append(
                "Schema repair hint failures exceeded: "
                f"{schema_repair_hint_failures} > {task.max_schema_repair_hint_failures}"
            )
        if task.min_tool_repair_successes is not None and tool_repair_successes < task.min_tool_repair_successes:
            errors.append(
                "Tool repair successes below requirement: "
                f"{tool_repair_successes} < {task.min_tool_repair_successes}"
            )
        if task.max_tool_repair_failures is not None and tool_repair_failures > task.max_tool_repair_failures:
            errors.append(
                "Tool repair failures exceeded: "
                f"{tool_repair_failures} > {task.max_tool_repair_failures}"
            )
        if (
            task.max_retry_budget_exhaustions is not None
            and retry_budget_exhaustions > task.max_retry_budget_exhaustions
        ):
            errors.append(
                "Retry budget exhaustions exceeded: "
                f"{retry_budget_exhaustions} > {task.max_retry_budget_exhaustions}"
            )
        if task.max_pre_dispatch_blocks is not None and pre_dispatch_blocks > task.max_pre_dispatch_blocks:
            errors.append(f"Pre-dispatch blocks exceeded: {pre_dispatch_blocks} > {task.max_pre_dispatch_blocks}")
        missing_shape_keys = [key for key in task.required_failure_shape_keys if key not in failure_shape_keys]
        if missing_shape_keys:
            errors.append(f"Missing required failure shape keys: {', '.join(missing_shape_keys)}")
        forbidden_shape_keys = [key for key in task.forbidden_failure_shape_keys if key in failure_shape_keys]
        if forbidden_shape_keys:
            errors.append(f"Forbidden failure shape keys were observed: {', '.join(forbidden_shape_keys)}")
        for key, max_count in task.max_failure_shape_key_counts.items():
            observed = failure_shape_keys.get(key, 0)
            if observed > max_count:
                errors.append(f"Failure shape key count exceeded for {key}: {observed} > {max_count}")
        return errors

    @staticmethod
    def _schema_repair_metrics(run_result: AgentRunResult) -> tuple[int, int]:
        recovered_indexes = EvalRunner._recovered_schema_failure_indexes(run_result)
        attempts = sum(1 for result in run_result.tool_results if result.metadata.get("schema_valid") is False)
        return attempts, len(recovered_indexes)

    @staticmethod
    def _schema_repair_hint_metrics(run_result: AgentRunResult) -> dict[str, Any]:
        recovered_indexes = EvalRunner._recovered_schema_failure_indexes(run_result)
        hinted_indexes: set[int] = set()
        types_seen: dict[str, int] = {}
        type_successes: dict[str, int] = {}
        for index, result in enumerate(run_result.tool_results):
            hint_types = result.metadata.get("schema_repair_hint_types")
            if not isinstance(hint_types, list) or not hint_types:
                if isinstance(result.metadata.get("schema_repair_hints"), list) and result.metadata.get("schema_repair_hints"):
                    hinted_indexes.add(index)
                continue
            hinted_indexes.add(index)
            for hint_type in hint_types:
                if not isinstance(hint_type, str) or not hint_type:
                    continue
                types_seen[hint_type] = types_seen.get(hint_type, 0) + 1
                if index in recovered_indexes:
                    type_successes[hint_type] = type_successes.get(hint_type, 0) + 1
        successes = len(hinted_indexes & recovered_indexes)
        seen = len(hinted_indexes)
        type_failures = {
            hint_type: count - type_successes.get(hint_type, 0)
            for hint_type, count in types_seen.items()
        }
        return {
            "seen": seen,
            "successes": successes,
            "failures": max(0, seen - successes),
            "types_seen": types_seen,
            "type_successes": type_successes,
            "type_failures": type_failures,
        }

    @staticmethod
    def _recovered_schema_failure_indexes(run_result: AgentRunResult) -> set[int]:
        invalid_indexes_by_tool: dict[str, list[int]] = {}
        for index, result in enumerate(run_result.tool_results):
            if result.metadata.get("schema_valid") is False:
                invalid_indexes_by_tool.setdefault(result.tool_name, []).append(index)

        recovered: set[int] = set()
        for tool_name, invalid_indexes in invalid_indexes_by_tool.items():
            valid_indexes = [
                index
                for index, result in enumerate(run_result.tool_results)
                if result.tool_name == tool_name and result.status == "ok" and result.metadata.get("schema_valid") is not False
            ]
            for invalid_index in invalid_indexes:
                if any(valid_index > invalid_index for valid_index in valid_indexes):
                    recovered.add(invalid_index)
        return recovered

    @classmethod
    def _tool_repair_metrics(cls, run_result: AgentRunResult) -> dict[str, Any]:
        recovered_indexes = cls._recovered_tool_failure_indexes(run_result)
        attempts_by_type: dict[str, int] = {}
        successes_by_type: dict[str, int] = {}
        for index, result in enumerate(run_result.tool_results):
            failure_type = result.metadata.get("failure_type")
            if not isinstance(failure_type, str) or not result.metadata.get("recoverable", False):
                continue
            attempts_by_type[failure_type] = attempts_by_type.get(failure_type, 0) + 1
            if index in recovered_indexes:
                successes_by_type[failure_type] = successes_by_type.get(failure_type, 0) + 1
        failures_by_type = {
            failure_type: attempts - successes_by_type.get(failure_type, 0)
            for failure_type, attempts in attempts_by_type.items()
        }
        attempts = sum(attempts_by_type.values())
        successes = sum(successes_by_type.values())
        failures = max(0, attempts - successes)
        return {
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "attempts_by_type": attempts_by_type,
            "successes_by_type": successes_by_type,
            "failures_by_type": failures_by_type,
        }

    @staticmethod
    def _recovered_tool_failure_indexes(run_result: AgentRunResult) -> set[int]:
        failed_indexes_by_tool: dict[str, list[int]] = {}
        for index, result in enumerate(run_result.tool_results):
            if result.metadata.get("failure_type") and result.metadata.get("recoverable", False):
                failed_indexes_by_tool.setdefault(result.tool_name, []).append(index)

        recovered: set[int] = set()
        for tool_name, failed_indexes in failed_indexes_by_tool.items():
            valid_indexes = [
                index
                for index, result in enumerate(run_result.tool_results)
                if result.tool_name == tool_name and result.status == "ok"
            ]
            for failed_index in failed_indexes:
                if any(valid_index > failed_index for valid_index in valid_indexes):
                    recovered.add(failed_index)
        return recovered

    def _schema_errors(self, session_id: str, run_result: AgentRunResult) -> list[str]:
        result_errors = [
            f"Tool schema violation for {result.tool_name}: {'; '.join(result.metadata.get('schema_errors', []))}"
            for result in run_result.tool_results
            if result.metadata.get("schema_valid") is False
        ]
        if result_errors:
            return result_errors

        registry = getattr(self.loop, "registry", None)
        if registry is None:
            return []
        validator = ToolArgumentSchemaValidator()
        errors: list[str] = []
        for call in self._tool_call_records(session_id, run_result):
            spec = registry.get(call["tool_name"])
            if spec is None:
                errors.append(f"Tool schema violation for {call['tool_name']}: unknown tool")
                continue
            result = validator.validate(spec.parameters, call.get("arguments", {}))
            for error in result.errors:
                errors.append(f"Tool schema violation for {call['tool_name']}: {error}")
        return errors

    @staticmethod
    def _contains_order(sequence: list[str], required_order: list[str]) -> bool:
        position = 0
        for tool in sequence:
            if position < len(required_order) and tool == required_order[position]:
                position += 1
        return position == len(required_order)

    def _tool_call_records(self, session_id: str, run_result: AgentRunResult) -> list[dict[str, Any]]:
        state = getattr(self.loop, "state", None)
        if state is not None:
            return [
                {"tool_name": str(call.get("tool_name", "")), "arguments": call.get("args", {})}
                for call in state.list_tool_calls(session_id)
            ]
        return [{"tool_name": result.tool_name, "arguments": {}} for result in run_result.tool_results]

    def _has_matching_tool_arguments(self, calls: list[dict[str, Any]], expected: dict[str, Any]) -> bool:
        tool_name = str(expected.get("tool") or expected.get("tool_name") or "")
        expected_arguments = expected.get("arguments") or expected.get("args") or {}
        for call in calls:
            if tool_name and call.get("tool_name") != tool_name:
                continue
            if self._arguments_match(call.get("arguments", {}), expected_arguments):
                return True
        return False

    @classmethod
    def _arguments_match(cls, actual: Any, expected: Any) -> bool:
        if isinstance(expected, dict) and cls._is_predicate(expected):
            return cls._predicate_match(actual, expected)
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            return all(key in actual and cls._arguments_match(actual[key], value) for key, value in expected.items())
        if isinstance(expected, list):
            if not isinstance(actual, list) or len(actual) != len(expected):
                return False
            return all(cls._arguments_match(actual_item, expected_item) for actual_item, expected_item in zip(actual, expected))
        return actual == expected

    @staticmethod
    def _is_predicate(expected: dict[str, Any]) -> bool:
        return bool({"equals", "contains", "startswith", "endswith", "in"} & set(expected))

    @classmethod
    def _predicate_match(cls, actual: Any, predicate: dict[str, Any]) -> bool:
        actual_text = cls._stringify(actual)
        if "equals" in predicate and actual != predicate["equals"]:
            return False
        if "contains" in predicate and str(predicate["contains"]) not in actual_text:
            return False
        if "startswith" in predicate and not actual_text.startswith(str(predicate["startswith"])):
            return False
        if "endswith" in predicate and not actual_text.endswith(str(predicate["endswith"])):
            return False
        if "in" in predicate:
            options = predicate["in"]
            if not isinstance(options, list) or actual not in options:
                return False
        return True

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)
