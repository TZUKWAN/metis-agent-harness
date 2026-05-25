"""Eval run comparison helpers."""

from __future__ import annotations

import json
import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from metis.evals.attestation import (
    verify_run_attestation,
    write_repair_plan_attestation,
    write_targeted_eval_stubs_attestation,
    write_targeted_eval_suite_attestation,
)
from metis.evals.provenance import eval_provenance_hash
from metis.telemetry.timeline import critical_event_id, load_timeline, timeline_event_ids
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


REGRESSION_METRICS = [
    "parser_failures",
    "tool_failures",
    "quality_failures",
    "false_completion",
    "final_unverified",
    "duplicate_tool_calls",
    "invalid_tool_calls",
    "policy_blocks",
    "evidence_resolution_failures",
    "schema_violations",
    "schema_repair_failures",
    "tool_repair_failures",
    "retry_budget_exhaustions",
    "pre_dispatch_blocks",
    "trajectory_failures",
]

COMPARE_PROFILES = ("strict", "release", "exploratory")
MATERIALIZED_TARGETED_EVAL_SUITE_SCHEMA_VERSION = "1"
MAX_PROMPT_SCHEMA_REPAIR_ARGUMENT_TEMPLATES = 5


def load_eval_run(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    report_path = run_dir / "eval-report.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing eval manifest: {manifest_path}")
    if not report_path.exists():
        raise FileNotFoundError(f"Missing eval JSON report: {report_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    pre_run_contract_path = run_dir / "pre-run-contract.json"
    pre_run_contract = None
    pre_run_contract_sha256 = ""
    if pre_run_contract_path.exists():
        raw = pre_run_contract_path.read_bytes()
        pre_run_contract_sha256 = hashlib.sha256(raw).hexdigest()
        pre_run_contract = json.loads(raw.decode("utf-8"))
    return {
        "run_dir": str(run_dir),
        "manifest": manifest,
        "report": report,
        "pre_run_contract": pre_run_contract,
        "pre_run_contract_path": str(pre_run_contract_path),
        "pre_run_contract_sha256": pre_run_contract_sha256,
    }


def compare_eval_runs(
    *,
    baseline_dir: str | Path,
    current_dir: str | Path,
    profile: str = "release",
) -> dict[str, Any]:
    if profile not in COMPARE_PROFILES:
        raise ValueError(f"Unknown compare profile: {profile}")
    baseline = load_eval_run(baseline_dir)
    current = load_eval_run(current_dir)
    baseline_results = _results_by_task(baseline["report"])
    current_results = _results_by_task(current["report"])
    baseline_clusters = _cluster_summary(Path(baseline["run_dir"]))
    current_clusters = _cluster_summary(Path(current["run_dir"]))
    cluster_diff = _cluster_diff(baseline_clusters, current_clusters)
    task_spec_diff = _task_spec_diff(
        _task_spec_hash_summary(Path(baseline["run_dir"])),
        _task_spec_hash_summary(Path(current["run_dir"])),
        baseline_task_contract_hash=_task_contract_hash(baseline),
        current_task_contract_hash=_task_contract_hash(current),
    )
    environment_diff = _environment_diff(baseline, current)
    provenance_diff = _provenance_diff(baseline, current)
    attestation_diff = _attestation_diff(baseline, current)
    baseline_tasks = set(baseline_results)
    current_tasks = set(current_results)
    shared_tasks = sorted(baseline_tasks & current_tasks)
    quality_gate_diff = _quality_gate_diff(baseline_results, current_results, shared_tasks)
    artifact_path_diagnostics = _quality_gate_artifact_path_diagnostics(quality_gate_diff.get("new_failed_gates", []))
    artifact_path_diagnostic_summary = _artifact_path_diagnostic_summary(artifact_path_diagnostics)
    summary_diff = _summary_diff(_run_eval_summary(baseline), _run_eval_summary(current))
    newly_failed = sorted(
        task_id
        for task_id in shared_tasks
        if baseline_results[task_id].get("success") is True and current_results[task_id].get("success") is not True
    )
    recovered = sorted(
        task_id
        for task_id in shared_tasks
        if baseline_results[task_id].get("success") is not True and current_results[task_id].get("success") is True
    )
    still_failed = sorted(
        task_id
        for task_id in shared_tasks
        if baseline_results[task_id].get("success") is not True and current_results[task_id].get("success") is not True
    )
    metric_deltas = _metric_deltas(baseline_results, current_results, shared_tasks)
    regressed_metrics = [
        delta for delta in metric_deltas if delta["metric"] in REGRESSION_METRICS and delta["delta"] > 0
    ]
    success_rate_delta = float(current["report"].get("success_rate", 0.0)) - float(
        baseline["report"].get("success_rate", 0.0)
    )
    regression_reasons = _regression_reasons(
        profile=profile,
        newly_failed=newly_failed,
        regressed_metrics=regressed_metrics,
        success_rate_delta=success_rate_delta,
        cluster_diff=cluster_diff,
        task_spec_diff=task_spec_diff,
        environment_diff=environment_diff,
        provenance_diff=provenance_diff,
        attestation_diff=attestation_diff,
        quality_gate_diff=quality_gate_diff,
        artifact_path_diagnostic_summary=artifact_path_diagnostic_summary,
        summary_diff=summary_diff,
    )
    regression_reason_links = _regression_reason_links(
        reasons=regression_reasons,
        current_run_dir=Path(current["run_dir"]),
        newly_failed=newly_failed,
        regressed_metrics=regressed_metrics,
        cluster_diff=cluster_diff,
        current_clusters=current_clusters,
        task_spec_diff=task_spec_diff,
        environment_diff=environment_diff,
        provenance_diff=provenance_diff,
        attestation_diff=attestation_diff,
        quality_gate_diff=quality_gate_diff,
        artifact_path_diagnostic_summary=artifact_path_diagnostic_summary,
        summary_diff=summary_diff,
    )
    return {
        "profile": profile,
        "baseline": _run_summary(baseline),
        "current": _run_summary(current),
        "success_rate_delta": success_rate_delta,
        "newly_failed_tasks": newly_failed,
        "recovered_tasks": recovered,
        "still_failed_tasks": still_failed,
        "new_tasks": sorted(current_tasks - baseline_tasks),
        "removed_tasks": sorted(baseline_tasks - current_tasks),
        "metric_deltas": metric_deltas,
        "regressed_metrics": regressed_metrics,
        "cluster_diff": cluster_diff,
        "summary_diff": summary_diff,
        "task_spec_diff": task_spec_diff,
        "environment_diff": environment_diff,
        "provenance_diff": provenance_diff,
        "attestation_diff": attestation_diff,
        "quality_gate_diff": quality_gate_diff,
        "artifact_path_diagnostics": artifact_path_diagnostics,
        "artifact_path_diagnostic_summary": artifact_path_diagnostic_summary,
        "baseline_untrusted": bool(attestation_diff.get("baseline_failures")),
        "current_untrusted": bool(attestation_diff.get("current_failures")),
        "regression_reasons": regression_reasons,
        "regression_reason_links": regression_reason_links,
        "has_regression": bool(regression_reasons),
    }


def eval_run_comparison_to_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# Metis Eval Run Comparison",
        "",
        f"Profile: {comparison.get('profile', 'release')}",
        f"Baseline: {comparison['baseline']['run_name']} ({comparison['baseline']['run_dir']})",
        f"Current: {comparison['current']['run_name']} ({comparison['current']['run_dir']})",
        f"Success rate delta: {comparison['success_rate_delta']:.2%}",
        f"Has regression: {comparison['has_regression']}",
        f"Regression reasons: {_format_list(comparison.get('regression_reasons', []))}",
        "",
        "## Regression Reason Links",
        "",
        *_format_reason_links(comparison.get("regression_reason_links", {})),
        "",
        "## Task Changes",
        "",
        f"- Newly failed: {_format_list(comparison['newly_failed_tasks'])}",
        f"- Recovered: {_format_list(comparison['recovered_tasks'])}",
        f"- Still failed: {_format_list(comparison['still_failed_tasks'])}",
        f"- New tasks: {_format_list(comparison['new_tasks'])}",
        f"- Removed tasks: {_format_list(comparison['removed_tasks'])}",
        "",
        "## Task Spec Drift",
        "",
        f"- Prompt changed: {_format_task_spec_changes(comparison.get('task_spec_diff', {}).get('prompt_changed', []))}",
        f"- Constraints changed: {_format_task_spec_changes(comparison.get('task_spec_diff', {}).get('constraints_changed', []))}",
        f"- Task spec changed: {_format_task_spec_changes(comparison.get('task_spec_diff', {}).get('task_spec_changed', []))}",
        f"- Task contract hash changed: {_format_environment_change(comparison.get('task_spec_diff', {}).get('task_contract_hash_changed'))}",
        f"- Missing baseline specs: {_format_list(comparison.get('task_spec_diff', {}).get('missing_baseline_specs', []))}",
        f"- Missing current specs: {_format_list(comparison.get('task_spec_diff', {}).get('missing_current_specs', []))}",
        "",
        "## Environment Drift",
        "",
        f"- Suite changed: {_format_environment_change(comparison.get('environment_diff', {}).get('suite_changed'))}",
        f"- Model changed: {_format_environment_change(comparison.get('environment_diff', {}).get('model_changed'))}",
        f"- Base URL changed: {_format_environment_change(comparison.get('environment_diff', {}).get('base_url_changed'))}",
        f"- Profile changed: {_format_environment_change(comparison.get('environment_diff', {}).get('profile_changed'))}",
        f"- Task count changed: {_format_environment_change(comparison.get('environment_diff', {}).get('task_count_changed'))}",
        "",
        "## Provenance Drift",
        "",
        f"- Provenance hash changed: {_format_environment_change(comparison.get('provenance_diff', {}).get('provenance_hash_changed'))}",
        f"- Provenance field changes: {_format_provenance_field_changes(comparison.get('provenance_diff', {}).get('field_changes', []))}",
        f"- Pre-run/post-run mismatches: {_format_pre_run_post_run_mismatches(comparison.get('provenance_diff', {}).get('pre_run_post_run_mismatches', []))}",
        "",
        "## Artifact Attestation",
        "",
        f"- Baseline attestation present: {comparison.get('attestation_diff', {}).get('baseline_present', False)}",
        f"- Current attestation present: {comparison.get('attestation_diff', {}).get('current_present', False)}",
        f"- Baseline untrusted: {comparison.get('baseline_untrusted', False)}",
        f"- Current untrusted: {comparison.get('current_untrusted', False)}",
        f"- Failures: {_format_attestation_failures(comparison.get('attestation_diff', {}).get('comparison_attestation_failures', []))}",
        "",
        "## Quality Gate Drift",
        "",
        f"- New failed gates: {_format_quality_gate_changes(comparison.get('quality_gate_diff', {}).get('new_failed_gates', []))}",
        f"- Resolved failed gates: {_format_quality_gate_changes(comparison.get('quality_gate_diff', {}).get('resolved_failed_gates', []))}",
        f"- Artifact path diagnostic summary: {_format_artifact_path_diagnostic_summary(comparison.get('artifact_path_diagnostic_summary', {}))}",
        f"- Artifact path diagnostics: {_format_artifact_path_diagnostics(comparison.get('artifact_path_diagnostics', []))}",
        "",
        "## Summary Drift",
        "",
        f"- Schema repair hint recovery rate: {_format_numeric_change(comparison.get('summary_diff', {}).get('schema_repair_hint_recovery_rate'))}",
        f"- Schema repair hint failures: {_format_numeric_change(comparison.get('summary_diff', {}).get('schema_repair_hint_failures'))}",
        f"- Schema repair hint type failure increases: {_format_count_changes(comparison.get('summary_diff', {}).get('schema_repair_hint_type_failure_increases', []))}",
        "",
        "## Cluster Changes",
        "",
        f"- New clusters: {_format_list(comparison.get('cluster_diff', {}).get('new_clusters', []))}",
        f"- Resolved clusters: {_format_list(comparison.get('cluster_diff', {}).get('resolved_clusters', []))}",
        f"- New critical clusters: {_format_list(comparison.get('cluster_diff', {}).get('new_critical_clusters', []))}",
        f"- Resolved critical clusters: {_format_list(comparison.get('cluster_diff', {}).get('resolved_critical_clusters', []))}",
        f"- Critical severity upgrades: {_format_severity_changes(comparison.get('cluster_diff', {}).get('critical_severity_upgrades', []))}",
        f"- Severity downgrades: {_format_severity_changes(comparison.get('cluster_diff', {}).get('severity_downgrades', []))}",
        f"- Cluster count increases: {_format_count_changes(comparison.get('cluster_diff', {}).get('cluster_count_increases', []))}",
        f"- Critical cluster count increases: {_format_count_changes(comparison.get('cluster_diff', {}).get('critical_cluster_count_increases', []))}",
        f"- Critical affected task increases: {_format_count_changes(comparison.get('cluster_diff', {}).get('critical_cluster_affected_task_increases', []))}",
        "",
        "## Regressed Metrics",
        "",
    ]
    if comparison["regressed_metrics"]:
        lines.extend(
            "- "
            f"{delta['task_id']}.{delta['metric']}: "
            f"{delta['baseline']} -> {delta['current']} ({delta['delta']:+})"
            for delta in comparison["regressed_metrics"]
        )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_eval_run_comparison(comparison: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "comparison.md").write_text(eval_run_comparison_to_markdown(comparison), encoding="utf-8")
    diagnosis = eval_run_comparison_diagnosis(comparison)
    (output_dir / "diagnosis.json").write_text(json.dumps(diagnosis, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "diagnosis.md").write_text(eval_run_diagnosis_to_markdown(diagnosis), encoding="utf-8")
    return output_dir


def load_eval_diagnosis(comparison_dir: str | Path) -> dict[str, Any]:
    diagnosis_path = Path(comparison_dir) / "diagnosis.json"
    if not diagnosis_path.exists():
        raise FileNotFoundError(f"Missing eval diagnosis: {diagnosis_path}")
    return json.loads(diagnosis_path.read_text(encoding="utf-8"))


def build_repair_tasks_from_diagnosis(diagnosis: dict[str, Any]) -> dict[str, Any]:
    backlog_by_cluster = _remediation_backlog_by_cluster(diagnosis)
    tasks = []
    for index, entry in enumerate(diagnosis.get("entries", []), start=1):
        cluster_keys = entry.get("cluster_keys", [])
        backlog_items = [backlog_by_cluster[key] for key in cluster_keys if key in backlog_by_cluster]
        tasks.append(
            {
                "id": f"repair-{index:03d}",
                "reason": entry.get("reason", ""),
                "priority": _repair_priority(entry, backlog_items),
                "owner_area": _repair_owner_area(entry, backlog_items),
                "task_ids": entry.get("task_ids", []),
                "cluster_keys": cluster_keys,
                "artifact_paths": entry.get("artifact_paths", {}),
                "timeline_paths": entry.get("timeline_paths", {}),
                "run_metadata": entry.get("run_metadata", {}),
                "trust_state": entry.get("trust_state", {}),
                "timeline_event_ids": _timeline_event_ids_for_paths(entry.get("timeline_paths", {})),
                "critical_event_ids": _critical_event_ids_for_paths(entry.get("timeline_paths", {})),
                "schema_repair_hint_events": entry.get("schema_repair_hint_events", {}),
                "likely_source_modules": _likely_source_modules(entry, backlog_items),
                "fields": entry.get("fields", []),
                "metrics": entry.get("metrics", []),
                "changes": entry.get("changes", []),
                "quality_gate_changes": entry.get("quality_gate_changes", []),
                "recommended_action": _repair_recommended_action(entry, backlog_items),
                "suggested_eval": _repair_suggested_eval(entry, backlog_items),
                "source_backlog_items": [item.get("id", "") for item in backlog_items],
            }
        )
    return {
        "baseline": diagnosis.get("baseline", {}),
        "current": diagnosis.get("current", {}),
        "profile": diagnosis.get("profile", "release"),
        "task_count": len(tasks),
        "tasks": tasks,
    }


def repair_tasks_to_markdown(repair_tasks: dict[str, Any]) -> str:
    lines = [
        "# Metis Repair Tasks",
        "",
        f"Profile: {repair_tasks.get('profile', 'release')}",
        f"Task count: {repair_tasks.get('task_count', 0)}",
        "",
    ]
    tasks = repair_tasks.get("tasks", [])
    if not tasks:
        lines.append("- None")
        return "\n".join(lines) + "\n"
    for task in tasks:
        lines.extend(
            [
                f"## {task['id']}: {task['reason']}",
                "",
                f"- Priority: {task.get('priority', 'medium')}",
                f"- Owner area: {task.get('owner_area', 'harness-runtime')}",
                f"- Tasks: {_format_list(task.get('task_ids', []))}",
                f"- Clusters: {_format_list(task.get('cluster_keys', []))}",
                f"- Artifacts: {_format_mapping(task.get('artifact_paths', {}))}",
                f"- Timelines: {_format_mapping(task.get('timeline_paths', {}))}",
                f"- Critical events: {_format_mapping(task.get('critical_event_ids', {}))}",
                f"- Likely source modules: {_format_list(task.get('likely_source_modules', []))}",
                f"- Recommended action: {task.get('recommended_action', 'Inspect linked artifacts and add a deterministic regression eval.')}",
                f"- Suggested eval: {task.get('suggested_eval', 'Add a focused regression eval for this repair task.')}",
                "",
            ]
        )
    return "\n".join(lines)


def write_repair_tasks(repair_tasks: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repair-tasks.json").write_text(
        json.dumps(repair_tasks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "repair-tasks.md").write_text(repair_tasks_to_markdown(repair_tasks), encoding="utf-8")
    return output_dir


def diagnose_eval_comparison(comparison_dir: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    diagnosis = load_eval_diagnosis(comparison_dir)
    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)
    write_repair_tasks(repair_tasks, output_dir or comparison_dir)
    return repair_tasks


def load_repair_tasks(path: str | Path) -> dict[str, Any]:
    repair_path = Path(path)
    if repair_path.is_dir():
        repair_path = repair_path / "repair-tasks.json"
    if not repair_path.exists():
        raise FileNotFoundError(f"Missing repair tasks: {repair_path}")
    return json.loads(repair_path.read_text(encoding="utf-8"))


def build_repair_plan(repair_tasks: dict[str, Any]) -> dict[str, Any]:
    tasks = list(repair_tasks.get("tasks", []))
    ordered_tasks = sorted(tasks, key=_repair_task_sort_key)
    owner_areas: dict[str, dict[str, Any]] = {}
    priority_buckets: dict[str, list[str]] = {"critical": [], "high": [], "medium": [], "low": []}
    has_artifact_integrity_tasks = any(_is_artifact_integrity_task(task) for task in ordered_tasks)
    has_artifact_path_hygiene_tasks = any(_is_artifact_path_hygiene_task(task) for task in ordered_tasks)
    phases = []
    if has_artifact_integrity_tasks:
        phases.append(
            {
                "id": "phase-0-restore-artifact-trust",
                "title": "Restore artifact trust",
                "description": "Repair or regenerate untrusted run bundles before interpreting model behavior, metrics, or regression deltas.",
                "phase_type": "precondition",
                "hard_precondition": True,
                "blocks": ["comparison_interpretation", "model_behavior_repair", "targeted_eval_generation"],
                "task_ids": [],
            }
        )
    if has_artifact_path_hygiene_tasks:
        phases.append(
            {
                "id": "phase-0b-repair-suite-hygiene",
                "title": "Repair suite hygiene",
                "description": "Remove non-portable artifact paths and invalid eval contract metadata before repairing model behavior.",
                "phase_type": "precondition",
                "hard_precondition": True,
                "blocks": ["model_behavior_repair", "targeted_eval_generation", "release_decision"],
                "task_ids": [],
            }
        )
    phases.extend(
        [
        {
            "id": "phase-1-stop-release-blockers",
            "title": "Stop release blockers",
            "description": "Fix critical and high-priority regressions before interpreting broader quality movement.",
            "phase_type": "repair",
            "hard_precondition": False,
            "blocks": [],
            "task_ids": [],
        },
        {
            "id": "phase-2-add-targeted-evals",
            "title": "Add targeted eval coverage",
            "description": "Turn every repair into a deterministic regression eval or gate.",
            "phase_type": "verification",
            "hard_precondition": False,
            "blocks": [],
            "task_ids": [],
        },
        {
            "id": "phase-3-stabilize-owners",
            "title": "Stabilize owner areas",
            "description": "Group remaining work by harness owner area so fixes land in coherent infrastructure slices.",
            "phase_type": "stabilization",
            "hard_precondition": False,
            "blocks": [],
            "task_ids": [],
        },
        ]
    )
    release_blocker_phase = next(phase for phase in phases if phase["id"] == "phase-1-stop-release-blockers")
    targeted_eval_phase = next(phase for phase in phases if phase["id"] == "phase-2-add-targeted-evals")
    owner_phase = next(phase for phase in phases if phase["id"] == "phase-3-stabilize-owners")
    artifact_phase = next((phase for phase in phases if phase["id"] == "phase-0-restore-artifact-trust"), None)
    suite_hygiene_phase = next((phase for phase in phases if phase["id"] == "phase-0b-repair-suite-hygiene"), None)
    for task in ordered_tasks:
        task_id = str(task.get("id", ""))
        priority = _normalize_priority(task.get("priority"))
        owner_area = str(task.get("owner_area") or "harness-runtime")
        priority_buckets.setdefault(priority, []).append(task_id)
        owner = owner_areas.setdefault(
            owner_area,
            {
                "owner_area": owner_area,
                "task_count": 0,
                "priorities": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "task_ids": [],
                "cluster_keys": [],
                "recommended_actions": [],
                "suggested_evals": [],
                "critical_event_ids": [],
                "likely_source_modules": [],
            },
        )
        owner["task_count"] += 1
        owner["priorities"][priority] = owner["priorities"].get(priority, 0) + 1
        owner["task_ids"].append(task_id)
        owner["cluster_keys"] = _stable_unique(owner["cluster_keys"] + [str(key) for key in task.get("cluster_keys", [])])
        owner["critical_event_ids"] = _stable_unique(
            owner["critical_event_ids"] + [str(value) for value in (task.get("critical_event_ids") or {}).values()]
        )
        owner["likely_source_modules"] = _stable_unique(
            owner["likely_source_modules"] + [str(value) for value in task.get("likely_source_modules", [])]
        )
        if task.get("recommended_action"):
            owner["recommended_actions"] = _stable_unique(owner["recommended_actions"] + [str(task["recommended_action"])])
        if task.get("suggested_eval"):
            owner["suggested_evals"] = _stable_unique(owner["suggested_evals"] + [str(task["suggested_eval"])])
        if artifact_phase is not None and _is_artifact_integrity_task(task):
            artifact_phase["task_ids"].append(task_id)
        if suite_hygiene_phase is not None and _is_artifact_path_hygiene_task(task):
            suite_hygiene_phase["task_ids"].append(task_id)
        if priority in {"critical", "high"}:
            release_blocker_phase["task_ids"].append(task_id)
        if task.get("suggested_eval"):
            targeted_eval_phase["task_ids"].append(task_id)
        if priority not in {"critical", "high"}:
            owner_phase["task_ids"].append(task_id)
    for phase in phases:
        phase["task_ids"] = _stable_unique(phase["task_ids"])
        phase["task_count"] = len(phase["task_ids"])
    task_statuses = {str(task.get("id", "")): _normalize_repair_status(task.get("status")) for task in ordered_tasks}
    _annotate_repair_phase_dependencies(phases, task_statuses)
    owner_list = sorted(
        owner_areas.values(),
        key=lambda owner: (
            -owner["priorities"].get("critical", 0),
            -owner["priorities"].get("high", 0),
            owner["owner_area"],
        ),
    )
    return {
        "profile": repair_tasks.get("profile", "release"),
        "baseline": repair_tasks.get("baseline", {}),
        "current": repair_tasks.get("current", {}),
        "task_count": len(ordered_tasks),
        "tasks": ordered_tasks,
        "priority_buckets": {priority: ids for priority, ids in priority_buckets.items() if ids},
        "owner_areas": owner_list,
        "phases": phases,
        "phase_status_summary": _repair_phase_status_summary(phases),
        "next_actions": _repair_plan_next_actions(ordered_tasks, owner_list),
    }


def build_eval_stubs_from_repair_tasks(repair_tasks: dict[str, Any]) -> dict[str, Any]:
    stubs = [_eval_stub_for_repair_task(task) for task in repair_tasks.get("tasks", [])]
    return {
        "profile": repair_tasks.get("profile", "release"),
        "baseline": repair_tasks.get("baseline", {}),
        "current": repair_tasks.get("current", {}),
        "stub_count": len(stubs),
        "artifact_path_diagnostic_summary": _artifact_path_diagnostic_summary_from_items(stubs),
        "stubs": stubs,
    }


def eval_stubs_to_markdown(stubs: dict[str, Any]) -> str:
    lines = [
        "# Metis Targeted Eval Stubs",
        "",
        f"Profile: {stubs.get('profile', 'release')}",
        f"Stub count: {stubs.get('stub_count', 0)}",
        f"Artifact path diagnostic summary: {_format_artifact_path_diagnostic_summary(stubs.get('artifact_path_diagnostic_summary', {}))}",
        "",
    ]
    if not stubs.get("stubs"):
        lines.append("- None")
        return "\n".join(lines) + "\n"
    for stub in stubs["stubs"]:
        lines.extend(
            [
                f"## {stub['id']}",
                "",
                f"- Source repair task: {stub.get('source_repair_task_id', '')}",
                f"- Owner area: {stub.get('owner_area', '')}",
                f"- Priority: {stub.get('priority', '')}",
                f"- Reason: {stub.get('reason', '')}",
                f"- Stub type: {stub.get('stub_type', 'model_behavior')}",
                f"- Target runs: {_format_list(stub.get('target_runs', []))}",
                f"- Critical events: {_format_mapping(stub.get('critical_event_ids', {}))}",
                f"- Run metadata: {_format_run_metadata(stub.get('run_metadata', {}))}",
                f"- Trust state: {_format_trust_state(stub.get('trust_state', {}))}",
                f"- Quality gate changes: {_format_quality_gate_changes(stub.get('quality_gate_changes', []))}",
                f"- Missing requirements: {_format_list(stub.get('missing_requirements', []))}",
                f"- Artifact path diagnostics: {_format_artifact_path_diagnostics(stub.get('artifact_path_diagnostics', []))}",
                f"- Schema repair hint types: {_format_list(stub.get('schema_repair_hint_types', []))}",
                f"- Schema repair argument templates: {_format_schema_repair_argument_templates(stub.get('schema_repair_argument_templates', []))}",
                f"- Likely source modules: {_format_list(stub.get('likely_source_modules', []))}",
                f"- Suggested assertion: {stub.get('suggested_assertion', '')}",
                f"- Verification command: {stub.get('verification_command', '')}",
                "",
                "```json",
                json.dumps(stub.get("eval_task_spec", {}), ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def write_eval_stubs(stubs: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "targeted-eval-stubs.json").write_text(json.dumps(stubs, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "targeted-eval-stubs.md").write_text(eval_stubs_to_markdown(stubs), encoding="utf-8")
    write_targeted_eval_stubs_attestation(output_dir, stubs=stubs)
    return output_dir


def load_eval_stubs(path: str | Path) -> dict[str, Any]:
    stubs_path = Path(path)
    if stubs_path.is_dir():
        stubs_path = stubs_path / "targeted-eval-stubs.json"
    if not stubs_path.exists():
        raise FileNotFoundError(f"Missing targeted eval stubs: {stubs_path}")
    return json.loads(stubs_path.read_text(encoding="utf-8"))


def materialize_eval_suite_from_stubs(stubs: dict[str, Any]) -> dict[str, Any]:
    tasks = []
    for stub in stubs.get("stubs", []):
        task_spec = dict(stub.get("eval_task_spec") or {})
        if not task_spec.get("id"):
            task_spec["id"] = stub.get("id", f"targeted-repair-{len(tasks) + 1:03d}")
        tasks.append(
            {
                "task_id": task_spec["id"],
                "source_repair_task_id": stub.get("source_repair_task_id", ""),
                "reason": stub.get("reason", ""),
                "priority": stub.get("priority", ""),
                "owner_area": stub.get("owner_area", ""),
                "cluster_keys": stub.get("cluster_keys", []),
                "critical_event_ids": stub.get("critical_event_ids", {}),
                "run_metadata": stub.get("run_metadata", {}),
                "stub_type": stub.get("stub_type", "model_behavior"),
                "trust_state": stub.get("trust_state", {}),
                "target_runs": stub.get("target_runs", []),
                "quality_gate_changes": stub.get("quality_gate_changes", []),
                "missing_requirements": stub.get("missing_requirements", []),
                "artifact_path_diagnostics": stub.get("artifact_path_diagnostics", []),
                "schema_repair_hint_events": stub.get("schema_repair_hint_events", {}),
                "schema_repair_hint_types": stub.get("schema_repair_hint_types", []),
                "schema_repair_argument_templates": stub.get("schema_repair_argument_templates", []),
                "tool_schemas": stub.get("tool_schemas", {}),
                "likely_source_modules": stub.get("likely_source_modules", []),
                "suggested_assertion": stub.get("suggested_assertion", ""),
                "verification_command": stub.get("verification_command", ""),
                "task_spec": task_spec,
            }
        )
    return {
        "suite": "targeted-repair-regression",
        "schema_version": MATERIALIZED_TARGETED_EVAL_SUITE_SCHEMA_VERSION,
        "profile": stubs.get("profile", "release"),
        "baseline": stubs.get("baseline", {}),
        "current": stubs.get("current", {}),
        "task_count": len(tasks),
        "artifact_path_diagnostic_summary": _artifact_path_diagnostic_summary_from_items(tasks),
        "tasks": tasks,
    }


def eval_suite_to_markdown(suite: dict[str, Any]) -> str:
    lines = [
        "# Metis Materialized Targeted Eval Suite",
        "",
        f"Suite: {suite.get('suite', 'targeted-repair-regression')}",
        f"Schema version: {suite.get('schema_version', 'unversioned')}",
        f"Profile: {suite.get('profile', 'release')}",
        f"Task count: {suite.get('task_count', 0)}",
        f"Artifact path diagnostic summary: {_format_artifact_path_diagnostic_summary(suite.get('artifact_path_diagnostic_summary', {}))}",
        "",
    ]
    if not suite.get("tasks"):
        lines.append("- None")
        return "\n".join(lines) + "\n"
    for task in suite["tasks"]:
        task_spec = task.get("task_spec", {})
        lines.extend(
            [
                f"## {task.get('task_id', '')}",
                "",
                f"- Source repair task: {task.get('source_repair_task_id', '')}",
                f"- Owner area: {task.get('owner_area', '')}",
                f"- Priority: {task.get('priority', '')}",
                f"- Reason: {task.get('reason', '')}",
                f"- Stub type: {task.get('stub_type', 'model_behavior')}",
                f"- Target runs: {_format_list(task.get('target_runs', []))}",
                f"- Critical events: {_format_mapping(task.get('critical_event_ids', {}))}",
                f"- Run metadata: {_format_run_metadata(task.get('run_metadata', {}))}",
                f"- Trust state: {_format_trust_state(task.get('trust_state', {}))}",
                f"- Quality gate changes: {_format_quality_gate_changes(task.get('quality_gate_changes', []))}",
                f"- Missing requirements: {_format_list(task.get('missing_requirements', []))}",
                f"- Artifact path diagnostics: {_format_artifact_path_diagnostics(task.get('artifact_path_diagnostics', []))}",
                f"- Schema repair hint types: {_format_list(task.get('schema_repair_hint_types', []))}",
                f"- Schema repair argument templates: {_format_schema_repair_argument_templates(task.get('schema_repair_argument_templates', []))}",
                f"- Likely source modules: {_format_list(task.get('likely_source_modules', []))}",
                f"- Suggested assertion: {task.get('suggested_assertion', '')}",
                f"- Verification command: {task.get('verification_command', '')}",
                f"- Allowed tools: {_format_list(task_spec.get('allowed_tools', []))}",
                f"- Max turns: {task_spec.get('max_turns', 12)}",
                "",
                "```json",
                json.dumps(task_spec, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def write_materialized_eval_suite(suite: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "targeted-eval-suite.json").write_text(json.dumps(suite, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "targeted-eval-suite.md").write_text(eval_suite_to_markdown(suite), encoding="utf-8")
    write_targeted_eval_suite_attestation(output_dir, suite=suite)
    return output_dir


def materialize_eval_suite(stubs_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    suite = materialize_eval_suite_from_stubs(load_eval_stubs(stubs_path))
    if output_dir:
        write_materialized_eval_suite(suite, output_dir)
    return suite


def repair_plan_to_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Metis Repair Plan",
        "",
        f"Profile: {plan.get('profile', 'release')}",
        f"Task count: {plan.get('task_count', 0)}",
        f"Phase status summary: {_format_mapping(plan.get('phase_status_summary', {}).get('counts', {}))}",
        "",
        "## Priority Buckets",
        "",
    ]
    buckets = plan.get("priority_buckets", {})
    if buckets:
        for priority in ("critical", "high", "medium", "low"):
            if priority in buckets:
                lines.append(f"- {priority}: {_format_list(buckets[priority])}")
    else:
        lines.append("- None")
    lines.extend(["", "## Phases", ""])
    for phase in plan.get("phases", []):
        lines.extend(
            [
                f"### {phase.get('title', phase.get('id', 'phase'))}",
                "",
                f"- ID: {phase.get('id', '')}",
                f"- Phase type: {phase.get('phase_type', 'repair')}",
                f"- Status: {phase.get('status', 'open')}",
                f"- Hard precondition: {str(bool(phase.get('hard_precondition'))).lower()}",
                f"- Requires completed preconditions: {_format_list(phase.get('requires_completed_preconditions', []))}",
                f"- Blocked by: {_format_list(phase.get('blocked_by', []))}",
                f"- Blocks: {_format_list(phase.get('blocks', []))}",
                f"- Task count: {phase.get('task_count', 0)}",
                f"- Tasks: {_format_list(phase.get('task_ids', []))}",
                f"- Description: {phase.get('description', '')}",
                "",
            ]
        )
    lines.extend(["## Owner Areas", ""])
    owners = plan.get("owner_areas", [])
    if not owners:
        lines.append("- None")
    for owner in owners:
        lines.extend(
            [
                f"### {owner.get('owner_area', 'harness-runtime')}",
                "",
                f"- Task count: {owner.get('task_count', 0)}",
                f"- Tasks: {_format_list(owner.get('task_ids', []))}",
                f"- Clusters: {_format_list(owner.get('cluster_keys', []))}",
                f"- Critical events: {_format_list(owner.get('critical_event_ids', []))}",
                f"- Likely source modules: {_format_list(owner.get('likely_source_modules', []))}",
                f"- Priorities: {_format_mapping(owner.get('priorities', {}))}",
                f"- Recommended actions: {_format_list(owner.get('recommended_actions', []))}",
                f"- Suggested evals: {_format_list(owner.get('suggested_evals', []))}",
                "",
            ]
        )
    lines.extend(["## Next Actions", ""])
    next_actions = plan.get("next_actions", [])
    if next_actions:
        lines.extend(f"- {action}" for action in next_actions)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def write_repair_plan(plan: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repair-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "repair-plan.md").write_text(repair_plan_to_markdown(plan), encoding="utf-8")
    write_repair_plan_attestation(output_dir, plan=plan)
    return output_dir


def plan_repairs(repair_tasks_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    repair_tasks = load_repair_tasks(repair_tasks_path)
    plan = build_repair_plan(repair_tasks)
    if output_dir:
        write_repair_plan(plan, output_dir)
    return plan


def eval_run_comparison_diagnosis(comparison: dict[str, Any]) -> dict[str, Any]:
    links = comparison.get("regression_reason_links", {})
    entries = []
    for reason in comparison.get("regression_reasons", []):
        link = links.get(reason, {})
        entries.append(
            {
                "reason": reason,
                "task_ids": link.get("task_ids", []),
                "cluster_keys": link.get("cluster_keys", []),
                "artifact_paths": link.get("artifact_paths", {}),
                "timeline_paths": link.get("timeline_paths", {}),
                "run_metadata": _run_metadata_for_paths(link.get("timeline_paths", {})),
                "schema_repair_hint_events": _schema_repair_hint_events_for_paths(link.get("timeline_paths", {})),
                "fields": link.get("fields", []),
                "metrics": link.get("metrics", []),
                "changes": link.get("changes", []),
                "quality_gate_changes": link.get("quality_gate_changes", []),
                "trust_state": _diagnosis_trust_state(comparison, link),
                "recommended_action": _recommended_action_for_reason(reason),
            }
        )
    return {
        "baseline": comparison.get("baseline", {}),
        "current": comparison.get("current", {}),
        "profile": comparison.get("profile", "release"),
        "has_regression": comparison.get("has_regression", False),
        "baseline_untrusted": bool(comparison.get("baseline_untrusted", False)),
        "current_untrusted": bool(comparison.get("current_untrusted", False)),
        "entry_count": len(entries),
        "entries": entries,
    }


def eval_run_diagnosis_to_markdown(diagnosis: dict[str, Any]) -> str:
    lines = [
        "# Metis Eval Diagnosis",
        "",
        f"Profile: {diagnosis.get('profile', 'release')}",
        f"Has regression: {diagnosis.get('has_regression', False)}",
        f"Baseline untrusted: {diagnosis.get('baseline_untrusted', False)}",
        f"Current untrusted: {diagnosis.get('current_untrusted', False)}",
        f"Entry count: {diagnosis.get('entry_count', 0)}",
        "",
    ]
    entries = diagnosis.get("entries", [])
    if not entries:
        lines.append("- None")
        return "\n".join(lines) + "\n"
    for entry in entries:
        lines.extend(
            [
                f"## {entry['reason']}",
                "",
                f"- Tasks: {_format_list(entry.get('task_ids', []))}",
                f"- Clusters: {_format_list(entry.get('cluster_keys', []))}",
                f"- Fields: {_format_list(entry.get('fields', []))}",
                f"- Artifacts: {_format_mapping(entry.get('artifact_paths', {}))}",
                f"- Timelines: {_format_mapping(entry.get('timeline_paths', {}))}",
                f"- Run metadata: {_format_run_metadata(entry.get('run_metadata', {}))}",
                f"- Trust state: {_format_trust_state(entry.get('trust_state', {}))}",
                f"- Schema repair hint events: {_format_schema_repair_hint_events(entry.get('schema_repair_hint_events', {}))}",
                f"- Quality gate changes: {_format_quality_gate_changes(entry.get('quality_gate_changes', []))}",
                f"- Recommended action: {entry['recommended_action']}",
                "",
            ]
        )
    return "\n".join(lines)


def _diagnosis_trust_state(comparison: dict[str, Any], link: dict[str, Any]) -> dict[str, Any]:
    failures = link.get("failures", [])
    if not failures:
        return {}
    baseline_failures = [failure for failure in failures if isinstance(failure, dict) and failure.get("run") == "baseline"]
    current_failures = [failure for failure in failures if isinstance(failure, dict) and failure.get("run") == "current"]
    return {
        "baseline_untrusted": bool(comparison.get("baseline_untrusted", False)),
        "current_untrusted": bool(comparison.get("current_untrusted", False)),
        "baseline_failures": baseline_failures,
        "current_failures": current_failures,
    }


def _results_by_task(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(result["task_id"]): result for result in report.get("results", [])}


def _metric_deltas(
    baseline_results: dict[str, dict[str, Any]],
    current_results: dict[str, dict[str, Any]],
    shared_tasks: list[str],
) -> list[dict[str, Any]]:
    deltas: list[dict[str, Any]] = []
    for task_id in shared_tasks:
        baseline = baseline_results[task_id]
        current = current_results[task_id]
        for metric in REGRESSION_METRICS:
            baseline_value = _metric_value(baseline.get(metric, 0))
            current_value = _metric_value(current.get(metric, 0))
            if baseline_value != current_value:
                deltas.append(
                    {
                        "task_id": task_id,
                        "metric": metric,
                        "baseline": baseline_value,
                        "current": current_value,
                        "delta": current_value - baseline_value,
                    }
                )
    return deltas


def _quality_gate_diff(
    baseline_results: dict[str, dict[str, Any]],
    current_results: dict[str, dict[str, Any]],
    shared_tasks: list[str],
) -> dict[str, list[dict[str, Any]]]:
    new_failed = []
    resolved_failed = []
    for task_id in shared_tasks:
        baseline_gates = _quality_gate_results_by_name(baseline_results[task_id])
        current_gates = _quality_gate_results_by_name(current_results[task_id])
        gate_names = sorted(set(baseline_gates) | set(current_gates))
        for gate_name in gate_names:
            baseline_gate = baseline_gates.get(gate_name, {})
            current_gate = current_gates.get(gate_name, {})
            baseline_failed = bool(baseline_gate) and baseline_gate.get("passed") is False
            current_failed = bool(current_gate) and current_gate.get("passed") is False
            if current_failed and not baseline_failed:
                new_failed.append(
                    {
                        "task_id": task_id,
                        "gate": gate_name,
                        "baseline_passed": baseline_gate.get("passed") if baseline_gate else None,
                        "current_passed": False,
                        "current_message": current_gate.get("message", ""),
                        "current_metadata": current_gate.get("metadata", {}),
                    }
                )
            if baseline_failed and not current_failed:
                resolved_failed.append(
                    {
                        "task_id": task_id,
                        "gate": gate_name,
                        "baseline_passed": False,
                        "current_passed": current_gate.get("passed") if current_gate else None,
                        "baseline_message": baseline_gate.get("message", ""),
                        "baseline_metadata": baseline_gate.get("metadata", {}),
                    }
                )
    return {
        "new_failed_gates": new_failed,
        "resolved_failed_gates": resolved_failed,
    }


def _quality_gate_results_by_name(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates = {}
    for gate in result.get("quality_gate_results", []) or []:
        if isinstance(gate, dict) and gate.get("name"):
            gates[str(gate["name"])] = gate
    return gates


def _metric_value(value: Any) -> int | float:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return 0


def _run_summary(run: dict[str, Any]) -> dict[str, Any]:
    manifest = run["manifest"]
    report = run["report"]
    metadata = report.get("metadata") or manifest.get("metadata") or {}
    return {
        "run_dir": run["run_dir"],
        "run_name": manifest.get("run_name", Path(run["run_dir"]).name),
        "suite": manifest.get("suite", metadata.get("suite", "")),
        "model": metadata.get("model", ""),
        "base_url": metadata.get("base_url", ""),
        "profile": metadata.get("profile", ""),
        "success_rate": report.get("success_rate", manifest.get("success_rate", 0.0)),
        "task_count": manifest.get("task_count", len(report.get("results", []))),
    }


def _run_eval_summary(run: dict[str, Any]) -> dict[str, Any]:
    report = run["report"]
    manifest = run["manifest"]
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else manifest.get("summary")
    if isinstance(summary, dict):
        return summary
    return {}


def _summary_diff(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_rate = _numeric_summary_value(baseline, "schema_repair_hint_recovery_rate")
    current_rate = _numeric_summary_value(current, "schema_repair_hint_recovery_rate")
    baseline_failures = _numeric_summary_value(baseline, "schema_repair_hint_failures")
    current_failures = _numeric_summary_value(current, "schema_repair_hint_failures")
    baseline_type_failures = _summary_int_map(baseline, "schema_repair_hint_type_failures")
    current_type_failures = _summary_int_map(current, "schema_repair_hint_type_failures")
    shared_types = sorted(set(baseline_type_failures) | set(current_type_failures))
    type_failure_deltas = [
        {
            "key": hint_type,
            "field": "schema_repair_hint_type_failures",
            "baseline": baseline_type_failures.get(hint_type, 0),
            "current": current_type_failures.get(hint_type, 0),
            "delta": current_type_failures.get(hint_type, 0) - baseline_type_failures.get(hint_type, 0),
        }
        for hint_type in shared_types
        if current_type_failures.get(hint_type, 0) != baseline_type_failures.get(hint_type, 0)
    ]
    return {
        "schema_repair_hint_recovery_rate": {
            "field": "schema_repair_hint_recovery_rate",
            "baseline": baseline_rate,
            "current": current_rate,
            "delta": current_rate - baseline_rate,
        },
        "schema_repair_hint_failures": {
            "field": "schema_repair_hint_failures",
            "baseline": baseline_failures,
            "current": current_failures,
            "delta": current_failures - baseline_failures,
        },
        "schema_repair_hint_type_failure_deltas": type_failure_deltas,
        "schema_repair_hint_type_failure_increases": [
            delta for delta in type_failure_deltas if delta["delta"] > 0
        ],
    }


def _numeric_summary_value(summary: dict[str, Any], key: str) -> float:
    value = summary.get(key, 0.0)
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _summary_int_map(summary: dict[str, Any], key: str) -> dict[str, int]:
    value = summary.get(key)
    if not isinstance(value, dict):
        return {}
    return {
        str(item_key): int(item_value)
        for item_key, item_value in value.items()
        if isinstance(item_value, (int, float)) and not isinstance(item_value, bool)
    }


def _environment_diff(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_summary = _run_summary(baseline)
    current_summary = _run_summary(current)
    return {
        "suite_changed": _value_change(baseline_summary, current_summary, "suite"),
        "model_changed": _value_change(baseline_summary, current_summary, "model"),
        "base_url_changed": _value_change(baseline_summary, current_summary, "base_url"),
        "profile_changed": _value_change(baseline_summary, current_summary, "profile"),
        "task_count_changed": _value_change(baseline_summary, current_summary, "task_count"),
    }


def _provenance_diff(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_manifest = baseline["manifest"]
    current_manifest = current["manifest"]
    baseline_hash = baseline_manifest.get("provenance_hash", "")
    current_hash = current_manifest.get("provenance_hash", "")
    hash_changed = None
    if baseline_hash and current_hash and baseline_hash != current_hash:
        hash_changed = {"field": "provenance_hash", "baseline": baseline_hash, "current": current_hash}
    baseline_provenance = baseline_manifest.get("provenance") if isinstance(baseline_manifest.get("provenance"), dict) else {}
    current_provenance = current_manifest.get("provenance") if isinstance(current_manifest.get("provenance"), dict) else {}
    keys = sorted(set(baseline_provenance) | set(current_provenance))
    field_changes = []
    for key in keys:
        if baseline_provenance.get(key) != current_provenance.get(key):
            field_changes.append(
                {"field": key, "baseline": baseline_provenance.get(key), "current": current_provenance.get(key)}
            )
    baseline_mismatches = _pre_run_post_run_mismatches("baseline", baseline)
    current_mismatches = _pre_run_post_run_mismatches("current", current)
    return {
        "baseline_provenance_hash": baseline_hash,
        "current_provenance_hash": current_hash,
        "provenance_hash_changed": hash_changed,
        "field_changes": field_changes,
        "baseline_pre_run_post_run_mismatches": baseline_mismatches,
        "current_pre_run_post_run_mismatches": current_mismatches,
        "pre_run_post_run_mismatches": baseline_mismatches + current_mismatches,
    }


def _attestation_diff(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_present = (Path(baseline["run_dir"]) / "run-attestation.json").exists()
    current_present = (Path(current["run_dir"]) / "run-attestation.json").exists()
    baseline_failures = _labeled_attestation_failures("baseline", baseline, require_if_missing=current_present)
    current_failures = _labeled_attestation_failures("current", current, require_if_missing=baseline_present)
    return {
        "baseline_present": baseline_present,
        "current_present": current_present,
        "baseline_failures": baseline_failures,
        "current_failures": current_failures,
        "comparison_attestation_failures": baseline_failures + current_failures,
    }


def _labeled_attestation_failures(
    run_label: str, run: dict[str, Any], *, require_if_missing: bool
) -> list[dict[str, str]]:
    run_dir = Path(run["run_dir"])
    attestation_path = run_dir / "run-attestation.json"
    if not attestation_path.exists() and not require_if_missing:
        return []
    return [{"run": run_label, "failure": failure} for failure in verify_run_attestation(run_dir)]


def _pre_run_post_run_mismatches(run_label: str, run: dict[str, Any]) -> list[dict[str, Any]]:
    pre_run_contract = run.get("pre_run_contract")
    if not isinstance(pre_run_contract, dict):
        return []
    manifest = run["manifest"]
    mismatches = []
    pre_run_provenance = pre_run_contract.get("provenance")
    pre_run_provenance_hash = pre_run_contract.get("provenance_hash")
    actual_contract_path = str(Path(run["run_dir"]) / "pre-run-contract.json")
    actual_contract_sha256 = str(run.get("pre_run_contract_sha256", ""))
    if manifest.get("pre_run_contract_path") not in ("", None, actual_contract_path):
        mismatches.append(
            {
                "run": run_label,
                "field": "pre_run_contract_path",
                "pre_run": actual_contract_path,
                "manifest": manifest.get("pre_run_contract_path"),
            }
        )
    if manifest.get("pre_run_contract_sha256") not in ("", None, actual_contract_sha256):
        mismatches.append(
            {
                "run": run_label,
                "field": "pre_run_contract_sha256",
                "pre_run": actual_contract_sha256,
                "manifest": manifest.get("pre_run_contract_sha256"),
            }
        )
    if manifest.get("pre_run_provenance_hash") not in ("", None, pre_run_provenance_hash):
        mismatches.append(
            {
                "run": run_label,
                "field": "pre_run_provenance_hash",
                "pre_run": pre_run_provenance_hash,
                "manifest": manifest.get("pre_run_provenance_hash"),
            }
        )
    if isinstance(pre_run_provenance, dict) and pre_run_provenance_hash:
        expected_pre_run_hash = eval_provenance_hash(pre_run_provenance)
        if pre_run_provenance_hash != expected_pre_run_hash:
            mismatches.append(
                {
                    "run": run_label,
                    "field": "pre_run_provenance_hash",
                    "pre_run": pre_run_provenance_hash,
                    "manifest": expected_pre_run_hash,
                    "detail": "pre-run provenance_hash does not match pre-run provenance payload",
                }
            )
    for field in ("provenance_hash", "task_contract_hash", "task_spec_hash_summary"):
        pre_run_value = pre_run_contract.get(field)
        manifest_value = manifest.get(field)
        if pre_run_value != manifest_value:
            mismatches.append(
                {
                    "run": run_label,
                    "field": field,
                    "pre_run": pre_run_value,
                    "manifest": manifest_value,
                }
            )
    return mismatches


def _value_change(baseline: dict[str, Any], current: dict[str, Any], key: str) -> dict[str, Any] | None:
    baseline_value = baseline.get(key)
    current_value = current.get(key)
    if baseline_value != current_value:
        return {"field": key, "baseline": baseline_value, "current": current_value}
    return None


def _cluster_summary(run_dir: Path) -> dict[str, Any]:
    failures_dir = run_dir / "failures"
    clusters_path = failures_dir / "clusters.json"
    backlog_path = failures_dir / "remediation-backlog.json"
    clusters: dict[str, Any] = {"clusters": []}
    backlog: dict[str, Any] = {"items": []}
    if clusters_path.exists():
        clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    if backlog_path.exists():
        backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    cluster_keys = {
        str(cluster.get("cluster_key", ""))
        for cluster in clusters.get("clusters", [])
        if isinstance(cluster, dict) and cluster.get("cluster_key")
    }
    cluster_counts = {
        str(cluster.get("cluster_key", "")): _metric_value(cluster.get("count", 0))
        for cluster in clusters.get("clusters", [])
        if isinstance(cluster, dict) and cluster.get("cluster_key")
    }
    cluster_affected_task_counts = {
        str(cluster.get("cluster_key", "")): len(cluster.get("task_ids", []))
        for cluster in clusters.get("clusters", [])
        if isinstance(cluster, dict) and cluster.get("cluster_key") and isinstance(cluster.get("task_ids", []), list)
    }
    cluster_task_ids = {
        str(cluster.get("cluster_key", "")): [str(task_id) for task_id in cluster.get("task_ids", [])]
        for cluster in clusters.get("clusters", [])
        if isinstance(cluster, dict) and cluster.get("cluster_key") and isinstance(cluster.get("task_ids", []), list)
    }
    critical_cluster_keys = {
        str(item.get("cluster_key", ""))
        for item in backlog.get("items", [])
        if isinstance(item, dict) and item.get("severity") == "critical" and item.get("cluster_key")
    }
    cluster_severities = {
        str(item.get("cluster_key", "")): str(item.get("severity", ""))
        for item in backlog.get("items", [])
        if isinstance(item, dict) and item.get("cluster_key") and item.get("severity")
    }
    return {
        "cluster_keys": cluster_keys,
        "critical_cluster_keys": critical_cluster_keys,
        "cluster_severities": cluster_severities,
        "cluster_counts": cluster_counts,
        "cluster_affected_task_counts": cluster_affected_task_counts,
        "cluster_task_ids": cluster_task_ids,
    }


def _task_spec_hash_summary(run_dir: Path) -> dict[str, dict[str, str]]:
    task_specs_path = run_dir / "task-specs.json"
    if task_specs_path.exists():
        payload = json.loads(task_specs_path.read_text(encoding="utf-8"))
        summary = payload.get("task_spec_hash_summary")
        if isinstance(summary, dict):
            return {str(task_id): dict(hashes) for task_id, hashes in summary.items() if isinstance(hashes, dict)}
        return {
            str(item.get("task_id", "")): dict(item.get("task_spec_hashes") or {})
            for item in payload.get("tasks", [])
            if isinstance(item, dict) and item.get("task_id")
        }
    return _task_spec_hash_summary_from_failures(run_dir)


def _task_contract_hash(run: dict[str, Any]) -> str:
    manifest_hash = run["manifest"].get("task_contract_hash")
    if isinstance(manifest_hash, str) and manifest_hash:
        return manifest_hash
    task_specs_path = Path(run["run_dir"]) / "task-specs.json"
    if task_specs_path.exists():
        payload = json.loads(task_specs_path.read_text(encoding="utf-8"))
        payload_hash = payload.get("task_contract_hash")
        if isinstance(payload_hash, str):
            return payload_hash
    return ""


def _task_spec_hash_summary_from_failures(run_dir: Path) -> dict[str, dict[str, str]]:
    failures_dir = run_dir / "failures"
    index_path = failures_dir / "index.json"
    if not index_path.exists():
        return {}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    summaries: dict[str, dict[str, str]] = {}
    for entry in index.get("artifacts", []):
        path = Path(entry.get("path", ""))
        if not path.is_absolute():
            path = run_dir / path
        if not path.exists():
            continue
        artifact = json.loads(path.read_text(encoding="utf-8"))
        task_id = str(artifact.get("task_id", ""))
        hashes = artifact.get("task_spec_hashes") or {}
        if task_id and hashes:
            summaries[task_id] = dict(hashes)
    return summaries


def _task_spec_diff(
    baseline: dict[str, dict[str, str]],
    current: dict[str, dict[str, str]],
    *,
    baseline_task_contract_hash: str = "",
    current_task_contract_hash: str = "",
) -> dict[str, Any]:
    baseline_tasks = set(baseline)
    current_tasks = set(current)
    shared_tasks = sorted(baseline_tasks & current_tasks)
    task_contract_hash_changed = None
    if (
        baseline_task_contract_hash
        and current_task_contract_hash
        and baseline_task_contract_hash != current_task_contract_hash
    ):
        task_contract_hash_changed = {
            "field": "task_contract_hash",
            "baseline": baseline_task_contract_hash,
            "current": current_task_contract_hash,
        }
    return {
        "baseline_task_specs": len(baseline),
        "current_task_specs": len(current),
        "baseline_task_contract_hash": baseline_task_contract_hash,
        "current_task_contract_hash": current_task_contract_hash,
        "task_contract_hash_changed": task_contract_hash_changed,
        "prompt_changed": _hash_changes(baseline, current, shared_tasks, "prompt_hash"),
        "constraints_changed": _hash_changes(baseline, current, shared_tasks, "constraints_hash"),
        "task_spec_changed": _hash_changes(baseline, current, shared_tasks, "task_spec_hash"),
        "missing_baseline_specs": sorted(current_tasks - baseline_tasks),
        "missing_current_specs": sorted(baseline_tasks - current_tasks),
    }


def _hash_changes(
    baseline: dict[str, dict[str, str]],
    current: dict[str, dict[str, str]],
    shared_tasks: list[str],
    hash_key: str,
) -> list[dict[str, str]]:
    changes = []
    for task_id in shared_tasks:
        baseline_hash = baseline[task_id].get(hash_key, "")
        current_hash = current[task_id].get(hash_key, "")
        if baseline_hash and current_hash and baseline_hash != current_hash:
            changes.append({"task_id": task_id, "baseline": baseline_hash, "current": current_hash})
    return changes


def _cluster_diff(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, list[Any]]:
    baseline_keys = baseline["cluster_keys"]
    current_keys = current["cluster_keys"]
    baseline_critical = baseline["critical_cluster_keys"]
    current_critical = current["critical_cluster_keys"]
    baseline_severities = baseline["cluster_severities"]
    current_severities = current["cluster_severities"]
    shared_keys = baseline_keys & current_keys
    severity_changes = _severity_changes(baseline_severities, current_severities, shared_keys)
    cluster_count_changes = _count_changes(
        baseline["cluster_counts"],
        current["cluster_counts"],
        shared_keys,
        field="count",
    )
    affected_task_count_changes = _count_changes(
        baseline["cluster_affected_task_counts"],
        current["cluster_affected_task_counts"],
        shared_keys,
        field="affected_task_count",
    )
    return {
        "new_clusters": sorted(current_keys - baseline_keys),
        "resolved_clusters": sorted(baseline_keys - current_keys),
        "shared_clusters": sorted(shared_keys),
        "new_critical_clusters": sorted(current_critical - baseline_critical),
        "resolved_critical_clusters": sorted(baseline_critical - current_critical),
        "shared_critical_clusters": sorted(baseline_critical & current_critical),
        "severity_changes": severity_changes,
        "severity_upgrades": [
            change
            for change in severity_changes
            if _severity_rank(change["current_severity"]) > _severity_rank(change["baseline_severity"])
        ],
        "critical_severity_upgrades": [
            change for change in severity_changes if change["current_severity"] == "critical"
        ],
        "severity_downgrades": [
            change
            for change in severity_changes
            if _severity_rank(change["current_severity"]) < _severity_rank(change["baseline_severity"])
        ],
        "cluster_count_changes": cluster_count_changes,
        "cluster_count_increases": [change for change in cluster_count_changes if change["delta"] > 0],
        "cluster_count_decreases": [change for change in cluster_count_changes if change["delta"] < 0],
        "affected_task_count_changes": affected_task_count_changes,
        "affected_task_count_increases": [
            change for change in affected_task_count_changes if change["delta"] > 0
        ],
        "affected_task_count_decreases": [
            change for change in affected_task_count_changes if change["delta"] < 0
        ],
        "critical_cluster_count_increases": [
            change for change in cluster_count_changes if change["delta"] > 0 and change["cluster_key"] in current_critical
        ],
        "critical_cluster_affected_task_increases": [
            change
            for change in affected_task_count_changes
            if change["delta"] > 0 and change["cluster_key"] in current_critical
        ],
    }


def _format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def _regression_reasons(
    *,
    profile: str,
    newly_failed: list[str],
    regressed_metrics: list[dict[str, Any]],
    success_rate_delta: float,
    cluster_diff: dict[str, list[Any]],
    task_spec_diff: dict[str, Any],
    environment_diff: dict[str, Any],
    provenance_diff: dict[str, Any],
    attestation_diff: dict[str, Any],
    quality_gate_diff: dict[str, Any],
    artifact_path_diagnostic_summary: dict[str, Any],
    summary_diff: dict[str, Any],
) -> list[str]:
    if profile == "exploratory":
        return []
    reasons = []
    if success_rate_delta < 0:
        reasons.append("success_rate_decreased")
    if newly_failed:
        reasons.append("newly_failed_tasks")
    if regressed_metrics:
        reasons.append("regressed_metrics")
    if summary_diff.get("schema_repair_hint_recovery_rate", {}).get("delta", 0) < 0:
        reasons.append("schema_repair_hint_recovery_rate_decreased")
    if summary_diff.get("schema_repair_hint_failures", {}).get("delta", 0) > 0:
        reasons.append("schema_repair_hint_failures_increased")
    if summary_diff.get("schema_repair_hint_type_failure_increases"):
        reasons.append("schema_repair_hint_type_failures_increased")
    if quality_gate_diff.get("new_failed_gates"):
        reasons.append("quality_gate_failed")
    if artifact_path_diagnostic_summary.get("total", 0) > 0:
        reasons.append("artifact_path_hygiene_failed")
    if profile == "release":
        if attestation_diff.get("comparison_attestation_failures"):
            reasons.append("attestation_untrusted")
        if provenance_diff.get("pre_run_post_run_mismatches"):
            reasons.append("pre_run_post_run_mismatch")
        if provenance_diff.get("provenance_hash_changed"):
            reasons.append("provenance_hash_changed")
        if cluster_diff["new_critical_clusters"]:
            reasons.append("new_critical_clusters")
        if cluster_diff["critical_severity_upgrades"]:
            reasons.append("critical_severity_upgrades")
        if cluster_diff["critical_cluster_count_increases"]:
            reasons.append("critical_cluster_count_increases")
        if cluster_diff["critical_cluster_affected_task_increases"]:
            reasons.append("critical_cluster_affected_task_increases")
        return reasons
    if profile == "strict":
        if attestation_diff.get("comparison_attestation_failures"):
            reasons.append("attestation_untrusted")
        if provenance_diff.get("pre_run_post_run_mismatches"):
            reasons.append("pre_run_post_run_mismatch")
        if provenance_diff.get("provenance_hash_changed"):
            reasons.append("provenance_hash_changed")
        if any(environment_diff.values()):
            reasons.append("environment_changed")
        if task_spec_diff.get("task_contract_hash_changed"):
            reasons.append("task_contract_hash_changed")
        if task_spec_diff["task_spec_changed"]:
            reasons.append("task_spec_changed")
        if task_spec_diff["missing_baseline_specs"] or task_spec_diff["missing_current_specs"]:
            reasons.append("task_spec_missing")
        if cluster_diff["new_clusters"]:
            reasons.append("new_clusters")
        if cluster_diff["severity_upgrades"]:
            reasons.append("severity_upgrades")
        if cluster_diff["cluster_count_increases"]:
            reasons.append("cluster_count_increases")
        if cluster_diff["affected_task_count_increases"]:
            reasons.append("affected_task_count_increases")
        return reasons
    raise ValueError(f"Unknown compare profile: {profile}")


def _regression_reason_links(
    *,
    reasons: list[str],
    current_run_dir: Path,
    newly_failed: list[str],
    regressed_metrics: list[dict[str, Any]],
    cluster_diff: dict[str, list[Any]],
    current_clusters: dict[str, Any],
    task_spec_diff: dict[str, Any],
    environment_diff: dict[str, Any],
    provenance_diff: dict[str, Any],
    attestation_diff: dict[str, Any],
    quality_gate_diff: dict[str, Any],
    artifact_path_diagnostic_summary: dict[str, Any],
    summary_diff: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    artifact_paths = _failure_artifact_paths(current_run_dir)
    timeline_paths = _failure_timeline_paths(current_run_dir)
    links: dict[str, dict[str, Any]] = {}
    for reason in reasons:
        if reason == "success_rate_decreased":
            task_ids = sorted(artifact_paths)
            links[reason] = _link_payload(task_ids=task_ids, artifact_paths=artifact_paths, timeline_paths=timeline_paths)
        elif reason == "newly_failed_tasks":
            links[reason] = _link_payload(task_ids=newly_failed, artifact_paths=artifact_paths, timeline_paths=timeline_paths)
        elif reason == "regressed_metrics":
            task_ids = sorted({str(delta["task_id"]) for delta in regressed_metrics})
            links[reason] = _link_payload(
                task_ids=task_ids,
                artifact_paths=artifact_paths,
                timeline_paths=timeline_paths,
                metrics=regressed_metrics,
            )
        elif reason == "environment_changed":
            links[reason] = {
                "fields": [
                    change["field"]
                    for change in environment_diff.values()
                    if isinstance(change, dict) and change.get("field")
                ],
                "changes": [change for change in environment_diff.values() if change],
            }
        elif reason == "provenance_hash_changed":
            links[reason] = {
                "provenance_hash_changed": provenance_diff.get("provenance_hash_changed"),
                "field_changes": provenance_diff.get("field_changes", []),
            }
        elif reason == "pre_run_post_run_mismatch":
            links[reason] = {
                "mismatches": provenance_diff.get("pre_run_post_run_mismatches", []),
            }
        elif reason == "attestation_untrusted":
            links[reason] = {
                "failures": attestation_diff.get("comparison_attestation_failures", []),
            }
        elif reason == "schema_repair_hint_recovery_rate_decreased":
            links[reason] = {"change": summary_diff.get("schema_repair_hint_recovery_rate", {})}
        elif reason == "schema_repair_hint_failures_increased":
            links[reason] = {"change": summary_diff.get("schema_repair_hint_failures", {})}
        elif reason == "schema_repair_hint_type_failures_increased":
            links[reason] = {
                "changes": summary_diff.get("schema_repair_hint_type_failure_increases", []),
            }
        elif reason == "quality_gate_failed":
            changes = quality_gate_diff.get("new_failed_gates", [])
            task_ids = sorted({str(change.get("task_id", "")) for change in changes if change.get("task_id")})
            artifact_path_diagnostics = _quality_gate_artifact_path_diagnostics(changes)
            links[reason] = _link_payload(
                task_ids=task_ids,
                artifact_paths=artifact_paths,
                timeline_paths=timeline_paths,
                quality_gate_changes=changes,
                artifact_path_diagnostics=artifact_path_diagnostics,
                artifact_path_diagnostic_summary=artifact_path_diagnostic_summary,
            )
        elif reason == "artifact_path_hygiene_failed":
            changes = quality_gate_diff.get("new_failed_gates", [])
            artifact_path_diagnostics = _quality_gate_artifact_path_diagnostics(changes)
            task_ids = sorted({str(item.get("task_id", "")) for item in artifact_path_diagnostics if item.get("task_id")})
            links[reason] = _link_payload(
                task_ids=task_ids,
                artifact_paths=artifact_paths,
                timeline_paths=timeline_paths,
                artifact_path_diagnostics=artifact_path_diagnostics,
                artifact_path_diagnostic_summary=artifact_path_diagnostic_summary,
            )
        elif reason in {"task_contract_hash_changed", "task_spec_changed", "task_spec_missing"}:
            changes = task_spec_diff.get("task_spec_changed", [])
            task_ids = sorted(
                {str(change["task_id"]) for change in changes}
                | set(task_spec_diff.get("missing_baseline_specs", []))
                | set(task_spec_diff.get("missing_current_specs", []))
            )
            links[reason] = {
                "task_ids": task_ids,
                "artifact_paths": _paths_for_tasks(task_ids, artifact_paths),
                "timeline_paths": _paths_for_tasks(task_ids, timeline_paths),
                "changes": changes,
                "task_contract_hash_changed": task_spec_diff.get("task_contract_hash_changed"),
                "missing_baseline_specs": task_spec_diff.get("missing_baseline_specs", []),
                "missing_current_specs": task_spec_diff.get("missing_current_specs", []),
            }
        else:
            cluster_keys = _reason_cluster_keys(reason, cluster_diff)
            task_ids = _task_ids_for_clusters(cluster_keys, current_clusters)
            links[reason] = {
                "cluster_keys": cluster_keys,
                "task_ids": task_ids,
                "artifact_paths": _paths_for_tasks(task_ids, artifact_paths),
                "timeline_paths": _paths_for_tasks(task_ids, timeline_paths),
            }
    return links


def _reason_cluster_keys(reason: str, cluster_diff: dict[str, list[Any]]) -> list[str]:
    if reason == "new_critical_clusters":
        return list(cluster_diff.get("new_critical_clusters", []))
    if reason == "critical_severity_upgrades":
        return [str(change["cluster_key"]) for change in cluster_diff.get("critical_severity_upgrades", [])]
    if reason == "critical_cluster_count_increases":
        return [str(change["cluster_key"]) for change in cluster_diff.get("critical_cluster_count_increases", [])]
    if reason == "critical_cluster_affected_task_increases":
        return [str(change["cluster_key"]) for change in cluster_diff.get("critical_cluster_affected_task_increases", [])]
    if reason == "new_clusters":
        return list(cluster_diff.get("new_clusters", []))
    if reason == "severity_upgrades":
        return [str(change["cluster_key"]) for change in cluster_diff.get("severity_upgrades", [])]
    if reason == "cluster_count_increases":
        return [str(change["cluster_key"]) for change in cluster_diff.get("cluster_count_increases", [])]
    if reason == "affected_task_count_increases":
        return [str(change["cluster_key"]) for change in cluster_diff.get("affected_task_count_increases", [])]
    return []


def _task_ids_for_clusters(cluster_keys: list[str], clusters: dict[str, Any]) -> list[str]:
    task_ids: set[str] = set()
    cluster_task_ids = clusters.get("cluster_task_ids", {})
    for cluster_key in cluster_keys:
        task_ids.update(str(task_id) for task_id in cluster_task_ids.get(cluster_key, []))
    return sorted(task_ids)


def _link_payload(
    *,
    task_ids: list[str],
    artifact_paths: dict[str, str],
    timeline_paths: dict[str, str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        "task_ids": task_ids,
        "artifact_paths": _paths_for_tasks(task_ids, artifact_paths),
        "timeline_paths": _paths_for_tasks(task_ids, timeline_paths or {}),
    }
    payload.update(extra)
    return payload


def _paths_for_tasks(task_ids: list[str], artifact_paths: dict[str, str]) -> dict[str, str]:
    return {task_id: artifact_paths[task_id] for task_id in task_ids if task_id in artifact_paths}


def _failure_artifact_paths(run_dir: Path) -> dict[str, str]:
    failures_dir = run_dir / "failures"
    index_path = failures_dir / "index.json"
    if not index_path.exists():
        return {}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    paths: dict[str, str] = {}
    for entry in index.get("artifacts", []):
        task_id = str(entry.get("task_id", ""))
        path = Path(entry.get("path", ""))
        if not path.is_absolute():
            path = run_dir / path
        if task_id and path.exists():
            paths[task_id] = str(path)
    return paths


def _failure_timeline_paths(run_dir: Path) -> dict[str, str]:
    failures_dir = run_dir / "failures"
    index_path = failures_dir / "index.json"
    if not index_path.exists():
        return {}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    paths: dict[str, str] = {}
    for entry in index.get("artifacts", []):
        task_id = str(entry.get("task_id", ""))
        path_value = entry.get("timeline_path", "")
        path = Path(path_value)
        if not path.is_absolute():
            path = run_dir / path
        if task_id and path.exists():
            paths[task_id] = str(path)
    return paths


def _severity_changes(
    baseline_severities: dict[str, str],
    current_severities: dict[str, str],
    shared_cluster_keys: set[str],
) -> list[dict[str, str]]:
    changes = []
    for cluster_key in sorted(shared_cluster_keys):
        baseline_severity = baseline_severities.get(cluster_key, "")
        current_severity = current_severities.get(cluster_key, "")
        if baseline_severity and current_severity and baseline_severity != current_severity:
            changes.append(
                {
                    "cluster_key": cluster_key,
                    "baseline_severity": baseline_severity,
                    "current_severity": current_severity,
                }
            )
    return changes


def _severity_rank(severity: str) -> int:
    return {"medium": 1, "high": 2, "critical": 3}.get(severity, 0)


def _count_changes(
    baseline_counts: dict[str, int | float],
    current_counts: dict[str, int | float],
    shared_cluster_keys: set[str],
    *,
    field: str,
) -> list[dict[str, Any]]:
    changes = []
    for cluster_key in sorted(shared_cluster_keys):
        baseline_count = baseline_counts.get(cluster_key, 0)
        current_count = current_counts.get(cluster_key, 0)
        if baseline_count != current_count:
            changes.append(
                {
                    "cluster_key": cluster_key,
                    "field": field,
                    "baseline": baseline_count,
                    "current": current_count,
                    "delta": current_count - baseline_count,
                }
            )
    return changes


def _format_severity_changes(values: list[dict[str, str]]) -> str:
    if not values:
        return "None"
    return ", ".join(
        f"{value['cluster_key']}:{value['baseline_severity']}->{value['current_severity']}"
        for value in values
    )


def _format_count_changes(values: list[dict[str, Any]]) -> str:
    if not values:
        return "None"
    return ", ".join(
        f"{value.get('cluster_key', value.get('key', 'unknown'))}:{value['baseline']}->{value['current']} ({value['delta']:+})"
        for value in values
    )


def _format_quality_gate_changes(values: list[dict[str, Any]]) -> str:
    if not values:
        return "None"
    return ", ".join(
        f"{value.get('task_id', 'unknown')}.{value.get('gate', 'unknown')}"
        for value in values
    )


def _format_artifact_path_diagnostics(values: list[dict[str, Any]]) -> str:
    if not values:
        return "None"
    return ", ".join(
        f"{value.get('task_id', 'unknown')}.{value.get('gate', 'unknown')}:{value.get('source', '')}={value.get('path', '')}({value.get('reason', '')})"
        for value in values
    )


def _format_artifact_path_diagnostic_summary(summary: dict[str, Any]) -> str:
    if not summary or not summary.get("total"):
        return "None"
    return (
        f"total={summary.get('total', 0)}; "
        f"by_reason={_format_int_mapping(summary.get('by_reason', {}))}; "
        f"by_source={_format_int_mapping(summary.get('by_source', {}))}; "
        f"by_gate={_format_int_mapping(summary.get('by_gate', {}))}"
    )


def _format_int_mapping(values: dict[str, Any]) -> str:
    if not values:
        return "None"
    return ", ".join(f"{key}:{values[key]}" for key in sorted(values))


def _format_task_spec_changes(values: list[dict[str, str]]) -> str:
    if not values:
        return "None"
    return ", ".join(value["task_id"] for value in values)


def _format_environment_change(value: dict[str, Any] | None) -> str:
    if not value:
        return "None"
    return f"{value['baseline']} -> {value['current']}"


def _format_numeric_change(value: dict[str, Any] | None) -> str:
    if not value:
        return "None"
    baseline = value.get("baseline", 0)
    current = value.get("current", 0)
    delta = value.get("delta", 0)
    if isinstance(baseline, float) or isinstance(current, float) or isinstance(delta, float):
        return f"{baseline:.4f} -> {current:.4f} ({delta:+.4f})"
    return f"{baseline} -> {current} ({delta:+})"


def _format_reason_links(links: dict[str, dict[str, Any]]) -> list[str]:
    if not links:
        return ["- None"]
    lines: list[str] = []
    for reason, payload in sorted(links.items()):
        parts = []
        if payload.get("task_ids"):
            parts.append(f"tasks={_format_list(payload['task_ids'])}")
        if payload.get("cluster_keys"):
            parts.append(f"clusters={_format_list(payload['cluster_keys'])}")
        if payload.get("fields"):
            parts.append(f"fields={_format_list(payload['fields'])}")
        if reason.startswith("schema_repair_hint_") and isinstance(payload.get("change"), dict):
            parts.append(f"change={_format_change_payload(payload['change'])}")
        if reason.startswith("schema_repair_hint_") and payload.get("changes"):
            parts.append(f"changes={_format_count_changes(payload['changes'])}")
        if reason == "quality_gate_failed" and payload.get("quality_gate_changes"):
            parts.append(f"changes={_format_quality_gate_changes(payload['quality_gate_changes'])}")
        if reason == "quality_gate_failed" and payload.get("artifact_path_diagnostic_summary", {}).get("total"):
            parts.append(
                f"artifact_path_diagnostics={_format_artifact_path_diagnostic_summary(payload['artifact_path_diagnostic_summary'])}"
            )
        if reason == "pre_run_post_run_mismatch" and payload.get("mismatches"):
            parts.append(f"mismatches={_format_pre_run_post_run_mismatches(payload['mismatches'])}")
        if reason == "attestation_untrusted" and payload.get("failures"):
            parts.append(f"failures={_format_attestation_failures(payload['failures'])}")
        artifact_paths = payload.get("artifact_paths") or {}
        if artifact_paths:
            parts.append(f"artifacts={_format_mapping(artifact_paths)}")
        timeline_paths = payload.get("timeline_paths") or {}
        if timeline_paths:
            parts.append(f"timelines={_format_mapping(timeline_paths)}")
        lines.append(f"- {reason}: {'; '.join(parts) if parts else 'recorded'}")
    return lines


def _format_mapping(mapping: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(mapping.items())) if mapping else "None"


def _format_provenance_field_changes(changes: list[dict[str, Any]]) -> str:
    if not changes:
        return "None"
    return ", ".join(str(change.get("field", "")) for change in changes if change.get("field"))


def _format_pre_run_post_run_mismatches(mismatches: list[dict[str, Any]]) -> str:
    if not mismatches:
        return "None"
    return ", ".join(
        f"{mismatch.get('run', 'unknown')}.{mismatch.get('field', 'unknown')}" for mismatch in mismatches
    )


def _format_attestation_failures(failures: list[dict[str, Any]]) -> str:
    if not failures:
        return "None"
    return ", ".join(
        f"{failure.get('run', 'unknown')}.{failure.get('failure', 'unknown')}" for failure in failures
    )


def _format_schema_repair_hint_events(events_by_task: dict[str, Any]) -> str:
    if not events_by_task:
        return "None"
    parts = []
    for task_id, events in sorted(events_by_task.items()):
        if not isinstance(events, list):
            continue
        event_parts = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("event_id", ""))
            hint_types = event.get("hint_types", [])
            if isinstance(hint_types, list) and hint_types:
                event_parts.append(f"{event_id}({','.join(str(value) for value in hint_types)})")
            else:
                event_parts.append(event_id)
        if event_parts:
            parts.append(f"{task_id}={','.join(event_parts)}")
    return "; ".join(parts) if parts else "None"


def _format_run_metadata(metadata_by_task: dict[str, Any]) -> str:
    if not metadata_by_task:
        return "None"
    parts = []
    for task_id, metadata in sorted(metadata_by_task.items()):
        if not isinstance(metadata, dict):
            continue
        anchors = []
        for key in ("pre_run_contract_sha256", "pre_run_provenance_hash", "provenance_hash", "task_contract_hash"):
            if metadata.get(key):
                anchors.append(f"{key}={metadata[key]}")
        parts.append(f"{task_id}({', '.join(anchors)})" if anchors else str(task_id))
    return "; ".join(parts) if parts else "None"


def _format_trust_state(trust_state: dict[str, Any]) -> str:
    if not isinstance(trust_state, dict) or not trust_state:
        return "None"
    parts = [
        f"baseline_untrusted={bool(trust_state.get('baseline_untrusted', False))}",
        f"current_untrusted={bool(trust_state.get('current_untrusted', False))}",
    ]
    baseline_failures = trust_state.get("baseline_failures", [])
    current_failures = trust_state.get("current_failures", [])
    if baseline_failures:
        parts.append(f"baseline_failures={len(baseline_failures)}")
    if current_failures:
        parts.append(f"current_failures={len(current_failures)}")
    return ", ".join(parts)


def _format_schema_repair_argument_templates(templates: list[dict[str, Any]]) -> str:
    if not templates:
        return "None"
    parts = []
    for template in templates:
        hint_type = str(template.get("hint_type", "unknown"))
        schema_path = str(template.get("schema_path", ""))
        parts.append(f"{hint_type}@{schema_path}")
    return ", ".join(parts)


def _format_change_payload(change: dict[str, Any]) -> str:
    field = str(change.get("field", "unknown"))
    return f"{field}:{_format_numeric_change(change)}"


def _recommended_action_for_reason(reason: str) -> str:
    actions = {
        "success_rate_decreased": "Inspect newly failed tasks, compare task specs and environment drift, then add focused regression coverage for the changed behavior.",
        "newly_failed_tasks": "Open the linked failure artifacts and repair the first failing tool, evidence, or finalization boundary.",
        "regressed_metrics": "Inspect the metric deltas and add a targeted eval gate for the metric that increased.",
        "new_critical_clusters": "Prioritize the linked critical clusters and implement the remediation backlog item before release.",
        "critical_severity_upgrades": "Review why the shared cluster became critical and add a regression eval for the severity transition.",
        "critical_cluster_count_increases": "Reduce the expanded critical failure family and verify the cluster count returns to baseline.",
        "critical_cluster_affected_task_increases": "Identify why the critical failure now affects more tasks and add cross-task repair coverage.",
        "environment_changed": "Confirm the model, endpoint, profile, or task count change is intentional before interpreting behavior deltas.",
        "attestation_untrusted": "Treat the comparison as unauditable until both run attestations verify against the current artifact bytes.",
        "pre_run_post_run_mismatch": "Treat the comparison as unauditable until the run pre-run contract and post-run manifest match.",
        "provenance_hash_changed": "Review eval provenance drift before interpreting model or harness behavior changes.",
        "task_contract_hash_changed": "Review suite-level task contract hash drift before attributing behavior changes to the model or harness.",
        "task_spec_changed": "Review task prompt and constraint hash drift before attributing behavior changes to the model or harness.",
        "task_spec_missing": "Regenerate run artifacts with task-specs.json so baseline comparison can be audited.",
        "new_clusters": "Triage newly introduced failure families and decide whether they should become strict gates.",
        "severity_upgrades": "Inspect the linked cluster severity movement and add a focused regression eval.",
        "cluster_count_increases": "Reduce repeated failure frequency or justify the increase as expected exploratory behavior.",
        "affected_task_count_increases": "Investigate why the same failure family spread across more tasks.",
        "schema_repair_hint_recovery_rate_decreased": "Inspect schema repair hint examples and add targeted evals for the hint classes that stopped recovering.",
        "schema_repair_hint_failures_increased": "Review unrecovered schema repair hints and tighten tool schema examples or repair feedback.",
        "schema_repair_hint_type_failures_increased": "Focus on the hint types with increased failures and add type-specific repair fixtures.",
        "quality_gate_failed": "Inspect the newly failing quality gate result, repair the gate input, evidence, or artifact path, then add a focused regression check for that gate.",
        "artifact_path_hygiene_failed": "Remove non-portable artifact paths from quality gate metadata, generated suites, or eval fixtures before release.",
    }
    return actions.get(reason, "Inspect linked artifacts and add a deterministic regression eval for this reason.")


def _remediation_backlog_by_cluster(diagnosis: dict[str, Any]) -> dict[str, dict[str, Any]]:
    current_run_dir = diagnosis.get("current", {}).get("run_dir")
    if not current_run_dir:
        return {}
    backlog_path = Path(current_run_dir) / "failures" / "remediation-backlog.json"
    if not backlog_path.exists():
        return {}
    backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    return {
        str(item.get("cluster_key", "")): item
        for item in backlog.get("items", [])
        if isinstance(item, dict) and item.get("cluster_key")
    }


def _repair_priority(entry: dict[str, Any], backlog_items: list[dict[str, Any]]) -> str:
    if entry.get("reason") == "attestation_untrusted":
        return "critical"
    severities = [str(item.get("severity", "")) for item in backlog_items]
    if "critical" in severities:
        return "critical"
    if "high" in severities:
        return "high"
    reason = str(entry.get("reason", ""))
    if "critical" in reason or reason in {"newly_failed_tasks", "regressed_metrics"}:
        return "high"
    return "medium"


def _repair_owner_area(entry: dict[str, Any], backlog_items: list[dict[str, Any]]) -> str:
    for item in backlog_items:
        owner = item.get("owner_area")
        if owner:
            return str(owner)
    reason = str(entry.get("reason", ""))
    if reason == "attestation_untrusted":
        return "artifact-integrity-and-provenance"
    if reason == "artifact_path_hygiene_failed":
        return "eval-suite-hygiene"
    if reason == "quality_gate_failed":
        return "quality-gates-and-evidence"
    if reason.startswith("task_spec") or reason == "environment_changed":
        return "eval-oracles-and-prompts"
    if "metric" in reason or "failed_tasks" in reason:
        return "harness-runtime"
    return "harness-runtime"


def _repair_recommended_action(entry: dict[str, Any], backlog_items: list[dict[str, Any]]) -> str:
    actions = [str(item.get("recommended_action", "")) for item in backlog_items if item.get("recommended_action")]
    if actions:
        return " ".join(dict.fromkeys(actions))
    return str(entry.get("recommended_action", "Inspect linked artifacts and add a deterministic regression eval."))


def _repair_suggested_eval(entry: dict[str, Any], backlog_items: list[dict[str, Any]]) -> str:
    evals = [str(item.get("suggested_eval", "")) for item in backlog_items if item.get("suggested_eval")]
    if evals:
        return " ".join(dict.fromkeys(evals))
    reason = str(entry.get("reason", ""))
    if reason == "attestation_untrusted":
        return "Regenerate or repair the untrusted run artifact bundle, rerun attestation verification, then repeat comparison."
    if reason == "artifact_path_hygiene_failed":
        return "Add a suite hygiene regression that fails when generated quality gate metadata contains absolute, drive-prefixed, or parent-traversal artifact paths."
    if reason == "quality_gate_failed":
        return "Add a deterministic eval that reproduces the quality gate input and requires the gate to pass."
    if reason == "environment_changed":
        return "Re-run baseline and current with the same model, endpoint, profile, and task count before release gating."
    if reason.startswith("task_spec"):
        return "Add a task-spec stability check and review prompt/constraint hash drift before interpreting regressions."
    return "Add a focused regression eval that reproduces this diagnosis entry and verifies the repair."


def _timeline_event_ids_for_paths(timeline_paths: dict[str, str]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for task_id, path in sorted(timeline_paths.items()):
        try:
            ids = timeline_event_ids(load_timeline(path))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            ids = []
        if ids:
            refs[str(task_id)] = ids
    return refs


def _critical_event_ids_for_paths(timeline_paths: dict[str, str]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for task_id, path in sorted(timeline_paths.items()):
        try:
            event_id = critical_event_id(load_timeline(path))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            event_id = ""
        if event_id:
            refs[str(task_id)] = event_id
    return refs


def _schema_repair_hint_events_for_paths(timeline_paths: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    refs: dict[str, list[dict[str, Any]]] = {}
    for task_id, path in sorted(timeline_paths.items()):
        try:
            timeline = load_timeline(path)
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            continue
        events = _schema_repair_hint_event_summaries(timeline)
        if events:
            refs[str(task_id)] = events
    return refs


def _run_metadata_for_paths(timeline_paths: dict[str, str]) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for task_id, path in sorted(timeline_paths.items()):
        try:
            timeline = load_timeline(path)
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            continue
        run_metadata = timeline.get("run_metadata")
        if isinstance(run_metadata, dict) and run_metadata:
            refs[str(task_id)] = _diagnosis_run_metadata(run_metadata)
    return refs


def _diagnosis_run_metadata(run_metadata: dict[str, Any]) -> dict[str, Any]:
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


def _schema_repair_hint_event_summaries(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = []
    for event in timeline.get("events", []):
        if event.get("event_type") != "schema.repair_hint":
            continue
        attributes = event.get("attributes")
        if not isinstance(attributes, dict):
            continue
        summaries.append(
            {
                "event_id": str(event.get("event_id", "")),
                "parent_event_id": str(attributes.get("parent_event_id", "")),
                "tool_name": str(event.get("tool_name", "")),
                "tool_call_id": str(event.get("tool_call_id", "")),
                "schema_errors": _string_list(attributes.get("schema_errors", [])),
                "hint_types": _string_list(attributes.get("schema_repair_hint_types", [])),
                "hints": _string_list(attributes.get("schema_repair_hints", [])),
                "hint_details": [detail for detail in attributes.get("schema_repair_hint_details", []) if isinstance(detail, dict)],
            }
        )
    return summaries


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _likely_source_modules(entry: dict[str, Any], backlog_items: list[dict[str, Any]]) -> list[str]:
    modules: list[str] = []
    reason = str(entry.get("reason", ""))
    cluster_keys = [str(key) for key in entry.get("cluster_keys", [])]
    metrics = [str(metric.get("metric", "")) for metric in entry.get("metrics", []) if isinstance(metric, dict)]
    owner_areas = [str(item.get("owner_area", "")) for item in backlog_items if item.get("owner_area")]
    quality_gate_names = [
        str(change.get("gate", ""))
        for change in entry.get("quality_gate_changes", [])
        if isinstance(change, dict) and change.get("gate")
    ]
    signal_text = " ".join([reason, *cluster_keys, *metrics, *owner_areas, *quality_gate_names])
    if "attestation" in signal_text or "untrusted" in signal_text or "artifact-integrity" in signal_text:
        modules.extend(
            [
                "metis/evals/attestation.py",
                "metis/evals/compare.py",
                "metis/evals/gate.py",
                "metis/evals/runner.py",
            ]
        )
    if "schema" in signal_text:
        modules.extend(
            [
                "metis/tools/schema_validator.py",
                "metis/tools/dispatcher.py",
                "metis/runtime/loop.py",
            ]
        )
    if "quality_gate" in signal_text or "quality-gate" in signal_text:
        modules.extend(
            [
                "metis/quality/gates.py",
                "metis/quality/runner.py",
                "metis/evals/runner.py",
                "metis/evals/compare.py",
                "metis/evidence/ledger.py",
            ]
        )
    if "policy" in signal_text or "approval" in signal_text or "command" in signal_text:
        modules.extend(
            [
                "metis/tools/policy.py",
                "metis/tools/dispatcher.py",
                "metis/tools/builtin.py",
            ]
        )
    if "retry" in signal_text or "failure_shape" in signal_text or "lineage" in signal_text:
        modules.extend(
            [
                "metis/runtime/loop.py",
                "metis/recovery/retry.py",
                "metis/evals/runner.py",
            ]
        )
    if "evidence" in signal_text or "finalization" in signal_text or "final_unverified" in signal_text:
        modules.extend(
            [
                "metis/runtime/finalization.py",
                "metis/evidence/resolver.py",
                "metis/evidence/ledger.py",
                "metis/runtime/loop.py",
            ]
        )
    if "parser" in signal_text:
        modules.extend(
            [
                "metis/providers/parsers/repair.py",
                "metis/providers/parsers/json_block.py",
                "metis/providers/parsers/hermes_xml.py",
                "metis/runtime/loop.py",
            ]
        )
    if "trajectory" in signal_text or "task_constraint" in signal_text or "failed_tasks" in signal_text:
        modules.extend(
            [
                "metis/evals/runner.py",
                "metis/evals/failures.py",
                "metis/planning/task_contract.py",
            ]
        )
    if reason.startswith("task_spec") or "environment" in reason:
        modules.extend(
            [
                "metis/evals/compare.py",
                "metis/evals/runner.py",
                "metis/evals/real_model_suite.py",
            ]
        )
    if not modules:
        modules.extend(["metis/runtime/loop.py", "metis/evals/runner.py"])
    return _stable_unique(modules)


def _eval_stub_for_repair_task(task: dict[str, Any]) -> dict[str, Any]:
    if _is_artifact_integrity_task(task):
        return _artifact_verification_stub_for_repair_task(task)
    task_id = str(task.get("id", "repair"))
    reason = str(task.get("reason", ""))
    cluster_keys = [str(key) for key in task.get("cluster_keys", [])]
    eval_id = f"targeted-{task_id}"
    hint_events = task.get("schema_repair_hint_events", {})
    hint_types = _schema_repair_hint_types_from_events(hint_events)
    hint_paths = _schema_repair_hint_paths_from_events(hint_events)
    hint_keywords = _schema_repair_hint_keywords_from_events(hint_events)
    custom_tool_schemas = _custom_tool_schemas_from_task(task)
    argument_templates = _schema_repair_argument_templates_from_events(hint_events, custom_tool_schemas=custom_tool_schemas)
    required_tool_arguments = _required_tool_arguments_from_templates(argument_templates)
    quality_gate_changes = _quality_gate_changes_from_task(task)
    quality_gate_names = _quality_gate_names_from_changes(quality_gate_changes)
    expected_artifacts = _quality_gate_expected_artifacts(quality_gate_changes)
    required_evidence_sources = _quality_gate_required_evidence_sources(quality_gate_changes)
    missing_requirements = _quality_gate_missing_requirements(quality_gate_changes)
    requirements = _quality_gate_requirements(quality_gate_changes, missing_requirements=missing_requirements)
    requirement_criteria = _quality_gate_requirement_criteria(quality_gate_changes)
    artifact_path_diagnostics = _quality_gate_artifact_path_diagnostics(quality_gate_changes)
    return {
        "id": eval_id,
        "source_repair_task_id": task_id,
        "reason": reason,
        "priority": _normalize_priority(task.get("priority")),
        "owner_area": str(task.get("owner_area") or "harness-runtime"),
        "cluster_keys": cluster_keys,
        "critical_event_ids": task.get("critical_event_ids", {}),
        "run_metadata": task.get("run_metadata", {}),
        "quality_gate_changes": quality_gate_changes,
        "quality_gate_names": quality_gate_names,
        "missing_requirements": missing_requirements,
        "artifact_path_diagnostics": artifact_path_diagnostics,
        "schema_repair_hint_events": hint_events,
        "schema_repair_hint_types": hint_types,
        "schema_repair_hint_paths": hint_paths,
        "schema_repair_hint_keywords": hint_keywords,
        "tool_schemas": custom_tool_schemas,
        "schema_repair_argument_templates": argument_templates,
        "likely_source_modules": task.get("likely_source_modules", []),
        "suggested_assertion": _suggested_assertion_for_task(task),
        "verification_command": _verification_command_for_modules(task.get("likely_source_modules", [])),
        "eval_task_spec": {
            "id": eval_id,
            "prompt": _eval_stub_prompt(task, argument_templates=argument_templates),
            "allowed_tools": _eval_stub_allowed_tools(task),
            "max_turns": 4,
            **({"quality_gates": quality_gate_names} if quality_gate_names else {}),
            **({"expected_artifacts": expected_artifacts} if expected_artifacts else {}),
            **({"required_evidence_sources": required_evidence_sources} if required_evidence_sources else {}),
            **({"requirements": requirements} if requirements else {}),
            **({"requirement_criteria": requirement_criteria} if requirement_criteria else {}),
            **({"required_tool_arguments": required_tool_arguments} if required_tool_arguments else {}),
            **_eval_stub_constraints(task),
        },
    }


def _artifact_verification_stub_for_repair_task(task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("id", "repair"))
    eval_id = f"artifact-verification-{task_id}"
    trust_state = task.get("trust_state", {}) if isinstance(task.get("trust_state"), dict) else {}
    target_runs = _artifact_verification_target_runs(trust_state)
    return {
        "id": eval_id,
        "stub_type": "artifact_verification",
        "source_repair_task_id": task_id,
        "reason": str(task.get("reason", "")),
        "priority": _normalize_priority(task.get("priority")),
        "owner_area": str(task.get("owner_area") or "artifact-integrity-and-provenance"),
        "cluster_keys": [str(key) for key in task.get("cluster_keys", [])],
        "critical_event_ids": task.get("critical_event_ids", {}),
        "run_metadata": task.get("run_metadata", {}),
        "trust_state": trust_state,
        "target_runs": target_runs,
        "quality_gate_changes": [],
        "quality_gate_names": [],
        "missing_requirements": [],
        "artifact_path_diagnostics": [],
        "schema_repair_hint_events": {},
        "schema_repair_hint_types": [],
        "schema_repair_hint_paths": [],
        "schema_repair_hint_keywords": [],
        "tool_schemas": {},
        "schema_repair_argument_templates": [],
        "likely_source_modules": task.get("likely_source_modules", []),
        "suggested_assertion": _artifact_verification_assertion(trust_state),
        "verification_command": "python -m pytest -q tests\\unit\\test_run_attestation.py tests\\unit\\test_eval_gate.py tests\\unit\\test_eval_compare.py",
        "eval_task_spec": {
            "id": eval_id,
            "fixture_type": "artifact_verification",
            "prompt": _artifact_verification_prompt(task, target_runs=target_runs),
            "allowed_tools": [],
            "max_turns": 1,
            "requires_model_execution": False,
            "quality_gates": ["run_attestation_verifies"],
            "artifact_verification": {
                "target_runs": target_runs,
                "trust_state": trust_state,
                "required_checks": [
                    "run-attestation.json exists",
                    "all attestation subjects exist",
                    "subject sha256 digests match local bytes",
                    "subject sizes match local bytes",
                    "manifest.json, eval-report.json, and task-specs.json are covered",
                ],
            },
        },
    }


def _artifact_verification_target_runs(trust_state: dict[str, Any]) -> list[str]:
    targets = []
    if trust_state.get("baseline_untrusted") or trust_state.get("baseline_failures"):
        targets.append("baseline")
    if trust_state.get("current_untrusted") or trust_state.get("current_failures"):
        targets.append("current")
    return targets or ["baseline", "current"]


def _artifact_verification_assertion(trust_state: dict[str, Any]) -> str:
    targets = _artifact_verification_target_runs(trust_state)
    return (
        "Run attestation verifies for "
        f"{_format_list(targets)} after artifact repair, with no digest, size, missing-file, or required-subject failures."
    )


def _artifact_verification_prompt(task: dict[str, Any], *, target_runs: list[str]) -> str:
    return (
        "Verify artifact integrity for the untrusted Metis eval run bundle. "
        f"Target runs: {_format_list(target_runs)}. "
        "Do not exercise model behavior; this fixture is satisfied only when run attestation verification passes."
    )


def _eval_stub_prompt(task: dict[str, Any], *, argument_templates: list[dict[str, Any]] | None = None) -> str:
    reason = str(task.get("reason", "unknown regression"))
    clusters = _format_list([str(key) for key in task.get("cluster_keys", [])])
    critical_events = _format_mapping(task.get("critical_event_ids", {}))
    hint_context = _eval_stub_hint_context(task)
    argument_context = _eval_stub_argument_template_context(argument_templates or [])
    quality_gate_context = _eval_stub_quality_gate_context(task)
    missing_requirement_context = _eval_stub_missing_requirement_context(task)
    return (
        "Reproduce and verify the Metis harness repair for "
        f"reason={reason}; clusters={clusters}; critical_events={critical_events}. "
        f"{quality_gate_context}"
        f"{missing_requirement_context}"
        f"{hint_context}"
        f"{argument_context}"
        "Use the smallest deterministic task that proves the failure is fixed."
    )


def _eval_stub_allowed_tools(task: dict[str, Any]) -> list[str]:
    hint_tool_names = _schema_repair_tool_names_from_events(task.get("schema_repair_hint_events", {}))
    modules = " ".join(str(module) for module in task.get("likely_source_modules", []))
    clusters = " ".join(str(key) for key in task.get("cluster_keys", []))
    signal = f"{modules} {clusters} {task.get('reason', '')}"
    if "command" in signal or "builtin" in signal:
        return _stable_unique(["run_shell", *hint_tool_names])
    if "evidence" in signal or "finalization" in signal:
        return _stable_unique(["read_file", "write_file", "run_shell", *hint_tool_names])
    return _stable_unique(["read_file", "write_file", *hint_tool_names])


def _eval_stub_constraints(task: dict[str, Any]) -> dict[str, Any]:
    signal = " ".join(
        [
            str(task.get("reason", "")),
            *[str(key) for key in task.get("cluster_keys", [])],
            *[str(module) for module in task.get("likely_source_modules", [])],
        ]
    )
    if "schema" in signal:
        constraints = {
            "max_schema_violations": 0,
            "max_invalid_tool_calls": 0,
            "min_schema_repair_successes": 1,
            "max_schema_repair_failures": 0,
            "allow_recovered_schema_failures": True,
        }
        if _schema_repair_hint_events_flat(task.get("schema_repair_hint_events", {})):
            constraints.update(
                {
                    "min_schema_repair_hint_successes": 1,
                    "max_schema_repair_hint_failures": 0,
                }
            )
        return constraints
    if "retry" in signal or "failure_shape" in signal:
        return {
            "max_retry_budget_exhaustions": 0,
            "max_pre_dispatch_blocks": 0,
            "max_tool_repair_failures": 0,
        }
    if "evidence" in signal or "finalization" in signal:
        return {
            "require_verified_final": True,
            "max_evidence_resolution_failures": 0,
        }
    if "parser" in signal:
        return {
            "max_invalid_tool_calls": 0,
            "max_schema_violations": 0,
        }
    return {
        "max_invalid_tool_calls": 0,
        "max_trajectory_failures": 0,
    }


def _suggested_assertion_for_task(task: dict[str, Any]) -> str:
    signal = " ".join([str(task.get("reason", "")), *[str(key) for key in task.get("cluster_keys", [])]])
    hint_types = _schema_repair_hint_types_from_events(task.get("schema_repair_hint_events", {}))
    quality_gate_names = _quality_gate_names_from_changes(_quality_gate_changes_from_task(task))
    if "quality_gate" in signal and quality_gate_names:
        return (
            "Quality gates "
            f"{_format_list(quality_gate_names)} pass with the same gate inputs, metadata, and artifact expectations "
            "that previously failed."
        )
    if "schema" in signal:
        if hint_types:
            return (
                "Schema repair hint recovery succeeds for hint types "
                f"{_format_list(hint_types)} with no unrecovered hint failures."
            )
        return "Malformed tool arguments are repaired once and the corrected call succeeds without unrecovered schema failures."
    if "retry" in signal or "failure_shape" in signal:
        return "Repeated failure shapes are blocked or recovered within retry budget limits."
    if "evidence" in signal or "finalization" in signal:
        return "Final output is blocked unless it cites resolvable evidence refs."
    if "parser" in signal:
        return "Malformed tool-call text is repaired into a valid tool call or fails with a typed parser repair event."
    return "The focused regression no longer reproduces the linked failure reason."


def _quality_gate_changes_from_task(task: dict[str, Any]) -> list[dict[str, Any]]:
    changes = task.get("quality_gate_changes", [])
    if not isinstance(changes, list):
        return []
    return [change for change in changes if isinstance(change, dict) and change.get("gate")]


def _quality_gate_names_from_changes(changes: list[dict[str, Any]]) -> list[str]:
    return _stable_unique(str(change.get("gate", "")) for change in changes if change.get("gate"))


def _quality_gate_expected_artifacts(changes: list[dict[str, Any]]) -> list[str]:
    artifact_gates = {"artifact_exists", "artifact_non_empty", "no_placeholder"}
    paths: list[str] = []
    for change in changes:
        gate_name = str(change.get("gate", ""))
        metadata = _quality_gate_change_metadata(change)
        if gate_name in artifact_gates:
            paths.extend(_metadata_string_values(metadata, "path", "artifact_path", "expected_artifact"))
            paths.extend(_metadata_string_list_values(metadata, "paths", "artifact_paths", "expected_artifacts"))
        paths.extend(_metadata_string_list_values(metadata, "expected_artifacts"))
    return _stable_unique(path for path in paths if _is_portable_artifact_path(path))


def _quality_gate_required_evidence_sources(changes: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    for change in changes:
        metadata = _quality_gate_change_metadata(change)
        sources.extend(_metadata_string_values(metadata, "source_type", "evidence_source", "required_evidence_source"))
        sources.extend(_metadata_string_list_values(metadata, "source_types", "evidence_sources", "required_evidence_sources"))
    return _stable_unique(sources)


def _quality_gate_missing_requirements(changes: list[dict[str, Any]]) -> list[str]:
    requirements: list[str] = []
    for change in changes:
        metadata = _quality_gate_change_metadata(change)
        requirements.extend(_metadata_string_values(metadata, "missing_requirement"))
        requirements.extend(_metadata_string_list_values(metadata, "missing_requirements"))
    return _stable_unique(requirements)


def _quality_gate_requirements(changes: list[dict[str, Any]], *, missing_requirements: list[str]) -> list[str]:
    requirements: list[str] = []
    for change in changes:
        metadata = _quality_gate_change_metadata(change)
        requirements.extend(_metadata_string_values(metadata, "requirement"))
        requirements.extend(_metadata_string_list_values(metadata, "requirements"))
    requirements.extend(missing_requirements)
    return _stable_unique(requirements)


def _quality_gate_requirement_criteria(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    for change in changes:
        metadata = _quality_gate_change_metadata(change)
        raw_criteria = metadata.get("requirement_criteria", [])
        if isinstance(raw_criteria, list):
            for item in raw_criteria:
                if isinstance(item, dict) and _requirement_criterion_has_verifier(item):
                    portable_criterion = _portable_requirement_criterion(item)
                    if portable_criterion:
                        _append_requirement_criterion(criteria, portable_criterion)
        for artifact_path in _metadata_string_list_values(metadata, "missing_artifact_paths"):
            if not _is_portable_artifact_path(artifact_path):
                continue
            _append_requirement_criterion(
                criteria,
                {
                    "id": f"artifact:{artifact_path}",
                    "required_artifact_path": artifact_path,
                },
            )
        for tool_name in _metadata_string_list_values(metadata, "missing_tools"):
            _append_requirement_criterion(
                criteria,
                {
                    "id": f"tool:{tool_name}",
                    "required_tool": tool_name,
                },
            )
    return criteria


def _quality_gate_artifact_path_diagnostics(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for change in changes:
        metadata = _quality_gate_change_metadata(change)
        task_id = str(change.get("task_id", ""))
        gate = str(change.get("gate", ""))
        for source_key in ("path", "artifact_path", "expected_artifact"):
            _append_artifact_path_diagnostics(
                diagnostics,
                _metadata_string_values(metadata, source_key),
                task_id=task_id,
                gate=gate,
                source=source_key,
            )
        for source_key in ("paths", "artifact_paths", "expected_artifacts", "missing_artifact_paths"):
            _append_artifact_path_diagnostics(
                diagnostics,
                _metadata_string_list_values(metadata, source_key),
                task_id=task_id,
                gate=gate,
                source=source_key,
            )
        raw_criteria = metadata.get("requirement_criteria", [])
        if not isinstance(raw_criteria, list):
            continue
        for index, item in enumerate(raw_criteria):
            if not isinstance(item, dict):
                continue
            criterion_id = str(item.get("id", ""))
            for field_name in ("required_artifact_path", "artifact_path"):
                value = item.get(field_name)
                if isinstance(value, str):
                    _append_artifact_path_diagnostics(
                        diagnostics,
                        [value],
                        task_id=task_id,
                        gate=gate,
                        source=f"requirement_criteria[{index}].{field_name}",
                        criterion_id=criterion_id,
                    )
    return diagnostics


def _append_artifact_path_diagnostics(
    diagnostics: list[dict[str, Any]],
    paths: list[str],
    *,
    task_id: str,
    gate: str,
    source: str,
    criterion_id: str = "",
) -> None:
    for path in paths:
        reason = _artifact_path_policy_failure_reason(path)
        if not reason:
            continue
        diagnostic = {
            "task_id": task_id,
            "gate": gate,
            "source": source,
            "path": path,
            "reason": reason,
        }
        if criterion_id:
            diagnostic["criterion_id"] = criterion_id
        if diagnostic not in diagnostics:
            diagnostics.append(diagnostic)


def _artifact_path_diagnostic_summary_from_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    for item in items:
        raw = item.get("artifact_path_diagnostics", [])
        if isinstance(raw, list):
            diagnostics.extend(entry for entry in raw if isinstance(entry, dict))
    return _artifact_path_diagnostic_summary(diagnostics)


def _artifact_path_diagnostic_summary(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    by_reason: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_gate: dict[str, int] = {}
    by_task: dict[str, int] = {}
    for diagnostic in diagnostics:
        _increment_count(by_reason, str(diagnostic.get("reason", "unknown") or "unknown"))
        _increment_count(by_source, str(diagnostic.get("source", "unknown") or "unknown"))
        _increment_count(by_gate, str(diagnostic.get("gate", "unknown") or "unknown"))
        _increment_count(by_task, str(diagnostic.get("task_id", "unknown") or "unknown"))
    return {
        "total": len(diagnostics),
        "by_reason": dict(sorted(by_reason.items())),
        "by_source": dict(sorted(by_source.items())),
        "by_gate": dict(sorted(by_gate.items())),
        "by_task": dict(sorted(by_task.items())),
    }


def _increment_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _portable_requirement_criterion(item: dict[str, Any]) -> dict[str, Any]:
    criterion = dict(item)
    for field_name in ("required_artifact_path", "artifact_path"):
        value = criterion.get(field_name)
        if isinstance(value, str) and not _is_portable_artifact_path(value):
            criterion.pop(field_name, None)
    return criterion if _requirement_criterion_has_verifier(criterion) else {}


def _is_portable_artifact_path(value: str) -> bool:
    return _artifact_path_policy_failure_reason(value) == ""


def _artifact_path_policy_failure_reason(value: str) -> str:
    normalized = value.replace("\\", "/")
    if not normalized or normalized.startswith("/") or normalized.startswith("~"):
        return "not_relative"
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return "windows_drive_prefix"
    if any(part == ".." for part in normalized.split("/")):
        return "parent_traversal"
    return ""


def _requirement_criterion_has_verifier(item: dict[str, Any]) -> bool:
    return any(
        isinstance(item.get(key), str) and item.get(key)
        for key in (
            "text",
            "requirement",
            "required_source_type",
            "source_type",
            "required_source_ref",
            "source_ref",
            "min_strength",
            "required_artifact_path",
            "artifact_path",
            "required_tool",
            "tool_name",
        )
    )


def _append_requirement_criterion(criteria: list[dict[str, Any]], criterion: dict[str, Any]) -> None:
    key = json.dumps(criterion, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    existing = {
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in criteria
    }
    if key not in existing:
        criteria.append(criterion)


def _quality_gate_change_metadata(change: dict[str, Any]) -> dict[str, Any]:
    metadata = change.get("current_metadata") or change.get("baseline_metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _metadata_string_values(metadata: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value:
            values.append(value)
    return values


def _metadata_string_list_values(metadata: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if isinstance(item, str) and item)
    return values


def _eval_stub_quality_gate_context(task: dict[str, Any]) -> str:
    changes = _quality_gate_changes_from_task(task)
    if not changes:
        return ""
    compact_changes = []
    for change in changes:
        compact_changes.append(
            {
                "task_id": change.get("task_id", ""),
                "gate": change.get("gate", ""),
                "baseline_passed": change.get("baseline_passed"),
                "current_passed": change.get("current_passed"),
                "message": change.get("current_message") or change.get("baseline_message", ""),
                "metadata": change.get("current_metadata") or change.get("baseline_metadata", {}),
            }
        )
    return (
        "Focus on quality gate drift; "
        f"failed_gates={_format_quality_gate_changes(changes)}; "
        "gate_context="
        f"{json.dumps(compact_changes, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}. "
    )


def _eval_stub_missing_requirement_context(task: dict[str, Any]) -> str:
    requirements = _quality_gate_missing_requirements(_quality_gate_changes_from_task(task))
    if not requirements:
        return ""
    return (
        "Cover these previously missing requirements exactly: "
        f"{json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}. "
        "The repair is incomplete unless the final output or recorded evidence makes each requirement verifiable. "
    )


def _eval_stub_hint_context(task: dict[str, Any]) -> str:
    hint_events = task.get("schema_repair_hint_events", {})
    flat_events = _schema_repair_hint_events_flat(hint_events)
    if not flat_events:
        return ""
    hint_types = _format_list(_schema_repair_hint_types_from_events(hint_events))
    hint_paths = _format_list(_schema_repair_hint_paths_from_events(hint_events))
    hint_keywords = _format_list(_schema_repair_hint_keywords_from_events(hint_events))
    return (
        "Focus on schema repair hints "
        f"types={hint_types}; paths={hint_paths}; keywords={hint_keywords}. "
    )


def _eval_stub_argument_template_context(templates: list[dict[str, Any]]) -> str:
    if not templates:
        return ""
    rendered: list[str] = []
    sorted_templates = sorted(templates, key=_prompt_argument_template_sort_key)
    included = sorted_templates[:MAX_PROMPT_SCHEMA_REPAIR_ARGUMENT_TEMPLATES]
    omitted = sorted_templates[MAX_PROMPT_SCHEMA_REPAIR_ARGUMENT_TEMPLATES:]
    for template in included:
        rendered.append(
            json.dumps(
                {
                    "tool": template.get("tool_name", ""),
                    "hint_type": template.get("hint_type", ""),
                    "schema_path": template.get("schema_path", ""),
                    "malformed_arguments": template.get("malformed_arguments", {}),
                    "corrected_arguments": template.get("corrected_arguments", {}),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    overflow = ""
    if omitted:
        overflow_summary = _format_schema_repair_argument_templates(omitted)
        overflow = f" Omitted {len(omitted)} lower-priority templates from prompt: {overflow_summary}."
    return (
        "Use these schema repair argument templates as exact failure-shape targets; "
        f"showing {len(included)} of {len(sorted_templates)} templates; "
        "placeholders are schema-compatible templates, not business data: "
        f"{' | '.join(rendered)}.{overflow} "
    )


def _prompt_argument_template_sort_key(template: dict[str, Any]) -> tuple[int, str, str, str, str]:
    corrected = template.get("corrected_arguments")
    has_corrected_priority = 0 if isinstance(corrected, dict) and bool(corrected) else 1
    return (
        has_corrected_priority,
        str(template.get("tool_name", "")),
        str(template.get("schema_path", "")),
        str(template.get("hint_type", "")),
        str(template.get("schema_keyword", "")),
    )


def _schema_repair_hint_events_flat(events_by_task: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not isinstance(events_by_task, dict):
        return events
    for raw_events in events_by_task.values():
        if not isinstance(raw_events, list):
            continue
        for event in raw_events:
            if isinstance(event, dict):
                events.append(event)
    return events


def _schema_repair_hint_types_from_events(events_by_task: Any) -> list[str]:
    hint_types: list[str] = []
    for event in _schema_repair_hint_events_flat(events_by_task):
        hint_types.extend(_string_list(event.get("hint_types", [])))
        for detail in event.get("hint_details", []):
            if isinstance(detail, dict) and detail.get("hint_type"):
                hint_types.append(str(detail["hint_type"]))
    return _stable_unique(hint_types)


def _schema_repair_hint_paths_from_events(events_by_task: Any) -> list[str]:
    paths: list[str] = []
    for event in _schema_repair_hint_events_flat(events_by_task):
        for detail in event.get("hint_details", []):
            if isinstance(detail, dict) and detail.get("schema_path"):
                paths.append(str(detail["schema_path"]))
    return _stable_unique(paths)


def _schema_repair_hint_keywords_from_events(events_by_task: Any) -> list[str]:
    keywords: list[str] = []
    for event in _schema_repair_hint_events_flat(events_by_task):
        for detail in event.get("hint_details", []):
            if isinstance(detail, dict) and detail.get("schema_keyword"):
                keywords.append(str(detail["schema_keyword"]))
    return _stable_unique(keywords)


def _schema_repair_tool_names_from_events(events_by_task: Any) -> list[str]:
    tool_names = [
        str(event.get("tool_name", ""))
        for event in _schema_repair_hint_events_flat(events_by_task)
        if event.get("tool_name")
    ]
    return _stable_unique(tool_names)


def _custom_tool_schemas_from_task(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_schemas = task.get("tool_schemas", {})
    if not isinstance(raw_schemas, dict):
        return {}
    return {
        str(tool_name): schema
        for tool_name, schema in raw_schemas.items()
        if tool_name and isinstance(schema, dict)
    }


def _schema_repair_argument_templates_from_events(
    events_by_task: Any,
    *,
    custom_tool_schemas: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    custom_tool_schemas = custom_tool_schemas or {}
    for event in _schema_repair_hint_events_flat(events_by_task):
        for detail in event.get("hint_details", []):
            if not isinstance(detail, dict):
                continue
            event_schema = _event_tool_schema(event)
            template = _schema_repair_argument_template_from_detail(
                detail,
                tool_name=str(event.get("tool_name", "")),
                tool_schema=event_schema or custom_tool_schemas.get(str(event.get("tool_name", "")), {}),
            )
            if not template:
                continue
            key = (
                str(template.get("hint_type", "")),
                str(template.get("schema_path", "")),
                str(template.get("schema_keyword", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            templates.append(template)
    return templates


def _event_tool_schema(event: dict[str, Any]) -> dict[str, Any]:
    for key in ("tool_schema", "parameters"):
        schema = event.get(key)
        if isinstance(schema, dict):
            return schema
    return {}


def _schema_repair_argument_template_from_detail(
    detail: dict[str, Any],
    *,
    tool_name: str = "",
    tool_schema: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    hint_type = str(detail.get("hint_type", ""))
    schema_path = str(detail.get("schema_path", ""))
    schema_keyword = str(detail.get("schema_keyword", ""))
    field_name = _schema_path_leaf(schema_path)
    if not hint_type or not field_name:
        return None
    malformed: dict[str, Any] = {}
    corrected: dict[str, Any] = {}
    note = "Template placeholders must be replaced by a concrete eval task before running against a real model."
    field_schema = _tool_argument_schema(tool_name, field_name, tool_schema=tool_schema or {})
    if hint_type == "add_required_property":
        corrected[field_name] = _schema_compatible_placeholder(field_name, field_schema)
    elif hint_type == "remove_additional_property":
        malformed[field_name] = f"<unsupported {field_name}>"
    elif hint_type == "increase_array_items":
        malformed[field_name] = []
        corrected[field_name] = _schema_compatible_array_placeholder(field_name, field_schema)
    elif hint_type == "reduce_array_items":
        malformed[field_name] = [f"<{field_name} item 1>", f"<{field_name} item 2>", "<extra item>"]
        corrected[field_name] = _schema_compatible_array_placeholder(field_name, field_schema)
    elif hint_type == "fix_type":
        malformed[field_name] = "<wrong type>"
        corrected[field_name] = _schema_compatible_placeholder(field_name, field_schema)
    elif hint_type in {"increase_numeric_value", "reduce_numeric_value"}:
        malformed[field_name] = "<out-of-range number>"
        corrected[field_name] = _schema_compatible_placeholder(field_name, field_schema)
    elif hint_type == "fix_string_pattern":
        malformed[field_name] = "<pattern mismatch>"
        corrected[field_name] = _schema_compatible_placeholder(field_name, field_schema)
    elif hint_type == "use_enum_value":
        malformed[field_name] = "<invalid enum>"
        corrected[field_name] = _schema_compatible_placeholder(field_name, field_schema)
    else:
        return None
    return {
        "hint_type": hint_type,
        "schema_path": schema_path,
        "schema_keyword": schema_keyword,
        "tool_name": tool_name,
        "malformed_arguments": malformed,
        "corrected_arguments": corrected,
        "notes": note,
    }


def _schema_path_leaf(schema_path: str) -> str:
    if not schema_path.startswith("$."):
        return ""
    return schema_path.rsplit(".", 1)[-1].strip()


@lru_cache(maxsize=1)
def _builtin_tool_schemas() -> dict[str, dict[str, Any]]:
    registry = ToolRegistry()
    register_builtin_tools(registry)
    return {spec.name: spec.parameters for spec in registry.iter_specs()}


def _tool_argument_schema(tool_name: str, field_name: str, *, tool_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = tool_schema if isinstance(tool_schema, dict) and tool_schema else _builtin_tool_schemas().get(tool_name, {})
    properties = schema.get("properties")
    if isinstance(properties, dict):
        field_schema = properties.get(field_name)
        if isinstance(field_schema, dict):
            return field_schema
    return {}


def _schema_compatible_placeholder(field_name: str, schema: dict[str, Any]) -> Any:
    if isinstance(schema.get("enum"), list) and schema["enum"]:
        return schema["enum"][0]
    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        for option in one_of:
            if isinstance(option, dict) and option.get("type") == "array":
                return _schema_compatible_array_placeholder(field_name, option)
        for option in one_of:
            if isinstance(option, dict):
                return _schema_compatible_placeholder(field_name, option)
    schema_type = schema.get("type")
    if schema_type == "array":
        return _schema_compatible_array_placeholder(field_name, schema)
    if schema_type in {"integer", "number"}:
        minimum = schema.get("minimum", 1)
        if isinstance(minimum, (int, float)) and not isinstance(minimum, bool):
            value = minimum
        else:
            value = 1
        if schema_type == "integer":
            return int(value)
        return float(value)
    if schema_type == "boolean":
        return True
    if field_name == "path":
        return "outputs/metis-placeholder.txt"
    if field_name == "content":
        return "metis-placeholder-content"
    if field_name == "encoding":
        return "utf-8"
    if field_name == "command":
        return "python --version"
    return f"metis-placeholder-{field_name}"


def _schema_compatible_array_placeholder(field_name: str, schema: dict[str, Any]) -> list[Any]:
    item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {"type": "string"}
    return [_schema_compatible_placeholder(f"{field_name}_item", item_schema)]


def _required_tool_arguments_from_templates(templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for template in templates:
        tool_name = str(template.get("tool_name", ""))
        corrected = template.get("corrected_arguments")
        if not tool_name or not isinstance(corrected, dict) or not corrected:
            continue
        arguments = {
            key: _required_argument_expectation(value)
            for key, value in corrected.items()
            if isinstance(key, str) and value not in (None, "", [])
        }
        if not arguments:
            continue
        fingerprint = (tool_name, json.dumps(arguments, ensure_ascii=False, sort_keys=True))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        required.append({"tool": tool_name, "arguments": arguments})
    return required


def _required_argument_expectation(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("<") and value.endswith(">"):
        return {"contains": value.strip("<>")}
    if isinstance(value, str):
        return {"contains": value}
    if isinstance(value, list) and value:
        return {"contains": str(value[0]).strip("<>")}
    return value


def _verification_command_for_modules(modules: list[str]) -> str:
    module_text = " ".join(str(module) for module in modules)
    if "evals/compare.py" in module_text:
        return "python -m pytest -q tests\\unit\\test_eval_compare.py tests\\unit\\test_cli_eval.py"
    if "evals/runner.py" in module_text or "evals/failures.py" in module_text:
        return "python -m pytest -q tests\\unit\\test_eval_runner.py tests\\unit\\test_failure_clusters.py"
    if "runtime/loop.py" in module_text:
        return "python -m pytest -q tests\\integration\\test_agent_loop_fake.py tests\\integration\\test_parser_repair.py tests\\integration\\test_strict_output_block.py"
    if "tools/" in module_text:
        return "python -m pytest -q tests\\unit\\test_tool_schema_validator.py tests\\unit\\test_tool_policy.py tests\\integration\\test_agent_loop_schema_guard.py"
    if "evidence/" in module_text or "finalization.py" in module_text:
        return "python -m pytest -q tests\\unit\\test_finalization_guard.py tests\\unit\\test_evidence_resolver.py tests\\integration\\test_agent_loop_finalization_guard.py"
    return "python -m pytest -q"


def _repair_task_sort_key(task: dict[str, Any]) -> tuple[int, str, str]:
    return (
        {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(_normalize_priority(task.get("priority")), 2),
        str(task.get("owner_area") or "harness-runtime"),
        str(task.get("id") or ""),
    )


def _is_artifact_integrity_task(task: dict[str, Any]) -> bool:
    return (
        task.get("reason") == "attestation_untrusted"
        or task.get("owner_area") == "artifact-integrity-and-provenance"
        or bool(task.get("trust_state"))
    )


def _is_artifact_path_hygiene_task(task: dict[str, Any]) -> bool:
    return task.get("reason") == "artifact_path_hygiene_failed"


def _annotate_repair_phase_dependencies(phases: list[dict[str, Any]], task_statuses: dict[str, str]) -> None:
    prior_preconditions: list[str] = []
    precondition_statuses: dict[str, str] = {}
    for phase in phases:
        phase["requires_completed_preconditions"] = prior_preconditions.copy()
        blocked_by = [
            precondition_id
            for precondition_id in prior_preconditions
            if not _repair_status_is_complete(precondition_statuses.get(precondition_id, "open"))
        ]
        phase["blocked_by"] = blocked_by
        base_status = _repair_phase_base_status(phase, task_statuses)
        phase["status"] = "blocked" if blocked_by and base_status != "not_applicable" else base_status
        if phase.get("hard_precondition"):
            phase_id = str(phase.get("id", ""))
            precondition_statuses[phase_id] = str(phase.get("status", "open"))
            prior_preconditions.append(phase_id)


def _repair_phase_base_status(phase: dict[str, Any], task_statuses: dict[str, str]) -> str:
    task_ids = [str(task_id) for task_id in phase.get("task_ids", []) if str(task_id)]
    if not task_ids:
        return "not_applicable"
    statuses = [_normalize_repair_status(task_statuses.get(task_id)) for task_id in task_ids]
    if all(_repair_status_is_complete(status) for status in statuses):
        return "verified" if all(status == "verified" for status in statuses) else "complete"
    if any(status == "in_progress" for status in statuses):
        return "in_progress"
    if any(status == "blocked" for status in statuses):
        return "blocked"
    return "open"


def _repair_phase_status_summary(phases: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    blocked_phases: list[str] = []
    executable_phases: list[str] = []
    hard_preconditions_open: list[str] = []
    for phase in phases:
        status = str(phase.get("status", "open"))
        phase_id = str(phase.get("id", ""))
        counts[status] = counts.get(status, 0) + 1
        if status == "blocked":
            blocked_phases.append(phase_id)
        if status in {"open", "in_progress"} and not phase.get("blocked_by"):
            executable_phases.append(phase_id)
        if phase.get("hard_precondition") and not _repair_status_is_complete(status):
            hard_preconditions_open.append(phase_id)
    return {
        "counts": counts,
        "blocked_phases": blocked_phases,
        "executable_phases": executable_phases,
        "hard_preconditions_open": hard_preconditions_open,
    }


def _normalize_repair_status(status: Any) -> str:
    value = str(status or "open").lower()
    if value in {"verified", "complete", "completed", "done"}:
        return "verified" if value == "verified" else "complete"
    if value in {"in_progress", "running"}:
        return "in_progress"
    if value in {"blocked", "failed"}:
        return "blocked"
    if value in {"not_applicable", "skipped"}:
        return "not_applicable"
    return "open"


def _repair_status_is_complete(status: Any) -> bool:
    return _normalize_repair_status(status) in {"complete", "verified"}


def _normalize_priority(priority: Any) -> str:
    value = str(priority or "medium").lower()
    if value in {"critical", "high", "medium", "low"}:
        return value
    return "medium"


def _stable_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _repair_plan_next_actions(tasks: list[dict[str, Any]], owner_areas: list[dict[str, Any]]) -> list[str]:
    if not tasks:
        return ["No repair tasks found. Keep the latest eval run as the current baseline and continue scheduled regression checks."]
    critical = [task for task in tasks if _normalize_priority(task.get("priority")) == "critical"]
    high = [task for task in tasks if _normalize_priority(task.get("priority")) == "high"]
    actions = []
    if critical:
        actions.append(
            f"Fix critical repair tasks first: {_format_list([str(task.get('id', '')) for task in critical])}."
        )
    if high:
        actions.append(f"Fix high-priority repair tasks next: {_format_list([str(task.get('id', '')) for task in high])}.")
    if owner_areas:
        owner = owner_areas[0]
        actions.append(
            f"Start with owner area {owner['owner_area']} because it has the highest release-blocking concentration."
        )
    actions.append("Add or update the suggested eval for every repaired task before accepting the fix.")
    actions.append("Rerun eval compare, diagnose, and repair-plan after fixes to verify the queue shrank.")
    return actions
