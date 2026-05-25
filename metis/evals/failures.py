"""Failure clustering and deterministic remediation guidance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def cluster_failure_artifacts(failures_dir: str | Path) -> dict[str, Any]:
    failures_dir = Path(failures_dir)
    artifacts = _load_failure_artifacts(failures_dir)
    clusters: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        for key in _cluster_keys(artifact):
            cluster = clusters.setdefault(
                key,
                {
                    "cluster_key": key,
                    "count": 0,
                    "task_ids": [],
                    "signals": [],
                    "remediation": _remediation_for_cluster(key),
                },
            )
            cluster["count"] += 1
            cluster["task_ids"].append(artifact["task_id"])
            cluster["signals"].extend(_artifact_signals(artifact))
    sorted_clusters = sorted(
        clusters.values(),
        key=lambda cluster: (-int(cluster["count"]), str(cluster["cluster_key"])),
    )
    return {
        "failure_count": len(artifacts),
        "cluster_count": len(sorted_clusters),
        "clusters": sorted_clusters,
    }


def failure_clusters_to_markdown(clusters: dict[str, Any]) -> str:
    lines = [
        "# Metis Failure Clusters",
        "",
        f"Failure count: {clusters['failure_count']}",
        f"Cluster count: {clusters['cluster_count']}",
        "",
    ]
    if not clusters["clusters"]:
        lines.append("- None")
        return "\n".join(lines) + "\n"
    for cluster in clusters["clusters"]:
        lines.extend(
            [
                f"## {cluster['cluster_key']}",
                "",
                f"- Count: {cluster['count']}",
                f"- Tasks: {', '.join(cluster['task_ids'])}",
                f"- Remediation: {cluster['remediation']}",
                "- Signals:",
            ]
        )
        unique_signals = sorted(set(str(signal) for signal in cluster["signals"]))
        lines.extend(f"  - {signal}" for signal in unique_signals[:20])
        lines.append("")
    return "\n".join(lines) + "\n"


def write_failure_clusters(failures_dir: str | Path) -> dict[str, Any]:
    failures_dir = Path(failures_dir)
    failures_dir.mkdir(parents=True, exist_ok=True)
    clusters = cluster_failure_artifacts(failures_dir)
    (failures_dir / "clusters.json").write_text(json.dumps(clusters, ensure_ascii=False, indent=2), encoding="utf-8")
    (failures_dir / "clusters.md").write_text(failure_clusters_to_markdown(clusters), encoding="utf-8")
    write_remediation_backlog(clusters, failures_dir)
    return clusters


def build_remediation_backlog(clusters: dict[str, Any]) -> dict[str, Any]:
    items = [_backlog_item(cluster, index + 1) for index, cluster in enumerate(clusters.get("clusters", []))]
    return {
        "failure_count": clusters.get("failure_count", 0),
        "cluster_count": clusters.get("cluster_count", 0),
        "item_count": len(items),
        "items": items,
    }


def remediation_backlog_to_markdown(backlog: dict[str, Any]) -> str:
    lines = [
        "# Metis Remediation Backlog",
        "",
        f"Failure count: {backlog['failure_count']}",
        f"Cluster count: {backlog['cluster_count']}",
        f"Item count: {backlog['item_count']}",
        "",
    ]
    if not backlog["items"]:
        lines.append("- None")
        return "\n".join(lines) + "\n"
    for item in backlog["items"]:
        lines.extend(
            [
                f"## {item['id']}: {item['cluster_key']}",
                "",
                f"- Severity: {item['severity']}",
                f"- Owner area: {item['owner_area']}",
                f"- Affected tasks: {', '.join(item['affected_task_ids'])}",
                f"- Recommended action: {item['recommended_action']}",
                f"- Suggested eval: {item['suggested_eval']}",
                "- Signals:",
            ]
        )
        lines.extend(f"  - {signal}" for signal in item["signals"][:20])
        lines.append("")
    return "\n".join(lines) + "\n"


def write_remediation_backlog(clusters: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    backlog = build_remediation_backlog(clusters)
    (output_dir / "remediation-backlog.json").write_text(
        json.dumps(backlog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "remediation-backlog.md").write_text(remediation_backlog_to_markdown(backlog), encoding="utf-8")
    return backlog


def _load_failure_artifacts(failures_dir: Path) -> list[dict[str, Any]]:
    index_path = failures_dir / "index.json"
    if not index_path.exists():
        return []
    index = json.loads(index_path.read_text(encoding="utf-8"))
    artifacts = []
    for entry in index.get("artifacts", []):
        path = Path(entry.get("path", ""))
        if not path.is_absolute():
            path = failures_dir.parent / path
        if path.exists() and path.name != "index.json":
            artifacts.append(json.loads(path.read_text(encoding="utf-8")))
    return artifacts


def _cluster_keys(artifact: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for failure_type in sorted((artifact.get("tool_failure_types") or {})):
        keys.append(f"tool_failure_type:{failure_type}")
    for shape_key in sorted((artifact.get("failure_shape_keys") or {})):
        keys.append(f"failure_shape:{shape_key}")
    keys.extend(_tool_excerpt_cluster_keys(artifact))
    keys.extend(_task_constraint_cluster_keys(artifact))
    metrics = artifact.get("metrics") or {}
    if _positive(metrics, "trajectory_failures"):
        keys.append("trajectory_failure")
    if _positive(metrics, "schema_violations") or _positive(metrics, "schema_repair_failures"):
        keys.append("schema_failure")
    if _positive(metrics, "retry_budget_exhaustions") or _positive(metrics, "pre_dispatch_blocks"):
        keys.append("retry_budget_failure")
    if _positive(metrics, "evidence_resolution_failures"):
        keys.append("evidence_resolution_failure")
    if metrics.get("final_unverified") is True:
        keys.append("finalization_unverified")
    if not keys:
        keys.append("unknown_failure")
    return keys


def _artifact_signals(artifact: dict[str, Any]) -> list[str]:
    signals = [f"task={artifact.get('task_id', '')}", f"status={artifact.get('status', '')}"]
    for key, value in sorted((artifact.get("task_spec_hashes") or {}).items()):
        signals.append(f"{key}={value}")
    metadata = artifact.get("run_metadata") or {}
    for key in ("suite", "model", "profile"):
        if metadata.get(key):
            signals.append(f"run_{key}={metadata[key]}")
    metrics = artifact.get("metrics") or {}
    for key, value in sorted(metrics.items()):
        if value:
            signals.append(f"{key}={value}")
    for failure_type, count in sorted((artifact.get("tool_failure_types") or {}).items()):
        signals.append(f"tool_failure_type:{failure_type}={count}")
    for shape_key, count in sorted((artifact.get("failure_shape_keys") or {}).items()):
        signals.append(f"failure_shape:{shape_key}={count}")
    for hint_type, count in sorted((artifact.get("schema_repair_hint_types_seen") or {}).items()):
        signals.append(f"schema_repair_hint_type:{hint_type}={count}")
    for hint_type, count in sorted((artifact.get("schema_repair_hint_type_failures") or {}).items()):
        signals.append(f"schema_repair_hint_failure_type:{hint_type}={count}")
    for error in artifact.get("errors") or []:
        signals.append(f"error={error}")
    for excerpt in artifact.get("tool_result_excerpts") or []:
        tool_name = excerpt.get("tool_name", "")
        status = excerpt.get("status", "")
        signals.append(f"tool_excerpt={tool_name}:{status}")
        metadata = excerpt.get("metadata") or {}
        for key in ("failure_type", "policy_decision", "failure_shape_key"):
            if metadata.get(key):
                signals.append(f"tool_excerpt_{key}={metadata[key]}")
        for schema_error in metadata.get("schema_errors") or []:
            signals.append(f"schema_error={schema_error}")
        for hint_type in metadata.get("schema_repair_hint_types") or []:
            signals.append(f"schema_repair_hint_type={hint_type}")
        for detail in metadata.get("schema_repair_hint_details") or []:
            if isinstance(detail, dict):
                hint_type = detail.get("hint_type", "")
                schema_path = detail.get("schema_path", "")
                schema_keyword = detail.get("schema_keyword", "")
                signals.append(f"schema_repair_hint_detail={hint_type}@{schema_path}:{schema_keyword}")
    return signals


def _remediation_for_cluster(cluster_key: str) -> str:
    if cluster_key.startswith("schema_error:"):
        return "Add targeted schema examples and repair feedback for this exact argument validation error."
    if cluster_key.startswith("schema_repair_hint_type:"):
        return "Inspect this schema repair hint class, add targeted examples, and improve hint wording or tool schema constraints."
    if cluster_key.startswith("schema_repair_hint_failure_type:"):
        return "Add a targeted repair fixture for this hint type and assert the corrected retry succeeds."
    if cluster_key.startswith("task_constraint:required_tool_missing"):
        return "Strengthen task planning prompts and required-tool reminders before finalization."
    if cluster_key.startswith("task_constraint:forbidden_tool_used"):
        return "Strengthen tool policy feedback and forbidden-tool checks before dispatch."
    if cluster_key.startswith("task_constraint:tool_order_broken"):
        return "Add step-order planning hints and trajectory gates for required tool sequences."
    if cluster_key.startswith("task_constraint:evidence_source_missing"):
        return "Make evidence source requirements explicit and block finalization until matching evidence exists."
    if cluster_key.startswith("tool_policy_decision:"):
        return "Inspect tool policy configuration and add recovery instructions for denied or approval-required tool calls."
    if cluster_key.startswith("tool_failure_type:schema_validation_failed") or cluster_key == "schema_failure":
        return "Tighten tool schema feedback, add argument examples, and preserve schema repair gates."
    if cluster_key.startswith("tool_failure_type:retry_budget_exhausted") or cluster_key == "retry_budget_failure":
        return "Improve failure lineage blocking, reduce repeated retries, and add task-specific recovery hints."
    if cluster_key.startswith("tool_failure_type:command_failed"):
        return "Add safer command templates, command result interpretation, and recovery-specific tool feedback."
    if cluster_key == "evidence_resolution_failure":
        return "Improve evidence ref propagation and finalization instructions that require existing evidence ids."
    if cluster_key == "finalization_unverified":
        return "Require final answers to cite tool-provided evidence refs and block unsupported completion claims."
    if cluster_key == "trajectory_failure":
        return "Review task oracle gates, required tool order, and prompt constraints for small-model compliance."
    if cluster_key.startswith("failure_shape:"):
        return "Inspect the repeated failure shape and add a targeted guard, repair hint, or eval fixture."
    return "Inspect artifact errors and add a deterministic eval gate or targeted runtime repair."


def _backlog_item(cluster: dict[str, Any], index: int) -> dict[str, Any]:
    cluster_key = str(cluster["cluster_key"])
    return {
        "id": f"remediation-{index:03d}",
        "cluster_key": cluster_key,
        "severity": _severity_for_cluster(cluster),
        "owner_area": _owner_area_for_cluster(cluster_key),
        "affected_task_ids": cluster.get("task_ids", []),
        "recommended_action": cluster.get("remediation", _remediation_for_cluster(cluster_key)),
        "suggested_eval": _suggested_eval_for_cluster(cluster_key),
        "signals": sorted(set(str(signal) for signal in cluster.get("signals", []))),
    }


def _severity_for_cluster(cluster: dict[str, Any]) -> str:
    cluster_key = str(cluster["cluster_key"])
    count = int(cluster.get("count", 0))
    if (
        cluster_key.startswith("schema_error:")
        or cluster_key.startswith("schema_repair_hint_type:")
        or cluster_key.startswith("schema_repair_hint_failure_type:")
    ):
        return "critical"
    if cluster_key.startswith("task_constraint:evidence_source_missing"):
        return "critical"
    if cluster_key.startswith("task_constraint:required_tool_missing"):
        return "high"
    if cluster_key.startswith("task_constraint:forbidden_tool_used"):
        return "high"
    if cluster_key.startswith("task_constraint:tool_order_broken"):
        return "high"
    if cluster_key in {"schema_failure", "retry_budget_failure", "evidence_resolution_failure", "finalization_unverified"}:
        return "critical"
    if cluster_key.startswith("tool_failure_type:retry_budget_exhausted"):
        return "critical"
    if cluster_key.startswith("tool_failure_type:schema_validation_failed"):
        return "critical"
    if count >= 3:
        return "high"
    if cluster_key == "trajectory_failure" or cluster_key.startswith("failure_shape:"):
        return "high"
    return "medium"


def _owner_area_for_cluster(cluster_key: str) -> str:
    if "schema" in cluster_key:
        return "tool-schema-and-repair"
    if cluster_key.startswith("task_constraint:"):
        return "eval-oracles-and-prompts"
    if cluster_key.startswith("tool_policy_decision:"):
        return "tool-command-execution"
    if "retry_budget" in cluster_key or "failure_shape" in cluster_key:
        return "runtime-lineage-and-recovery"
    if "evidence" in cluster_key or "finalization" in cluster_key:
        return "evidence-and-finalization"
    if "command_failed" in cluster_key:
        return "tool-command-execution"
    if "trajectory" in cluster_key:
        return "eval-oracles-and-prompts"
    return "harness-runtime"


def _suggested_eval_for_cluster(cluster_key: str) -> str:
    if "schema" in cluster_key:
        return "Add a schema-repair eval that first reproduces the malformed arguments and then requires one successful corrected retry."
    if cluster_key.startswith("task_constraint:"):
        return "Add a trajectory oracle eval that reproduces the violated task constraint and requires the corrected tool sequence."
    if cluster_key.startswith("tool_policy_decision:"):
        return "Add a tool-policy eval covering denied, blocked, and approval-required calls with explicit recovery behavior."
    if "retry_budget" in cluster_key or "failure_shape" in cluster_key:
        return "Add a lineage regression eval that repeats the failure shape and asserts retry budget exhaustion/pre-dispatch blocking is bounded."
    if "evidence" in cluster_key or "finalization" in cluster_key:
        return "Add a verified-final eval requiring final evidence_refs to match tool-provided evidence ids."
    if "command_failed" in cluster_key:
        return "Add a command-recovery eval requiring the model to interpret nonzero exit output and switch to a safe corrected command."
    if "trajectory" in cluster_key:
        return "Add a trajectory oracle eval covering required tools, forbidden tools, required order, and required tool arguments."
    return "Add a focused regression eval that reproduces this cluster and asserts the corrected runtime behavior."


def _positive(metrics: dict[str, Any], key: str) -> bool:
    value = metrics.get(key, 0)
    return isinstance(value, (int, float)) and value > 0


def _tool_excerpt_cluster_keys(artifact: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for excerpt in artifact.get("tool_result_excerpts") or []:
        metadata = excerpt.get("metadata") or {}
        policy_decision = metadata.get("policy_decision")
        if isinstance(policy_decision, str) and policy_decision:
            keys.append(f"tool_policy_decision:{policy_decision}")
        for schema_error in metadata.get("schema_errors") or []:
            if isinstance(schema_error, str) and schema_error:
                keys.append(f"schema_error:{_normalize_cluster_fragment(schema_error)}")
        for hint_type in metadata.get("schema_repair_hint_types") or []:
            if isinstance(hint_type, str) and hint_type:
                keys.append(f"schema_repair_hint_type:{hint_type}")
        for detail in metadata.get("schema_repair_hint_details") or []:
            if isinstance(detail, dict):
                hint_type = detail.get("hint_type")
                schema_path = detail.get("schema_path")
                if isinstance(hint_type, str) and hint_type and isinstance(schema_path, str) and schema_path:
                    keys.append(f"schema_repair_hint_path:{hint_type}:{_normalize_cluster_fragment(schema_path)}")
    for hint_type, count in (artifact.get("schema_repair_hint_type_failures") or {}).items():
        if isinstance(hint_type, str) and isinstance(count, int) and count > 0:
            keys.append(f"schema_repair_hint_failure_type:{hint_type}")
    return keys


def _task_constraint_cluster_keys(artifact: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    task_spec = artifact.get("task_spec") or {}
    errors = [str(error) for error in artifact.get("errors") or []]
    if task_spec.get("required_tools") and any("Missing required tools" in error for error in errors):
        keys.append("task_constraint:required_tool_missing")
    if task_spec.get("forbidden_tools") and any("Forbidden tools were called" in error for error in errors):
        keys.append("task_constraint:forbidden_tool_used")
    if task_spec.get("required_tool_order") and any("Required tool order not satisfied" in error for error in errors):
        keys.append("task_constraint:tool_order_broken")
    if task_spec.get("required_tool_arguments") and any("Required tool arguments not satisfied" in error for error in errors):
        keys.append("task_constraint:tool_arguments_missing")
    if task_spec.get("required_evidence_sources") and any(
        "Evidence resolution failures exceeded" in error or "required evidence" in error.lower()
        for error in errors
    ):
        keys.append("task_constraint:evidence_source_missing")
    return keys


def _normalize_cluster_fragment(value: str) -> str:
    normalized = "".join(character.lower() if character.isalnum() else "_" for character in value)
    normalized = "_".join(part for part in normalized.split("_") if part)
    return normalized[:120] or "unknown"
