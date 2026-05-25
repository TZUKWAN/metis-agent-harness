"""Release gate checks for Metis eval runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from metis.evals.attestation import verify_run_attestation
from metis.evals.compare import load_eval_run
from metis.evals.provenance import eval_provenance_hash


DEFAULT_GATE_THRESHOLDS = {
    "min_success_rate": 1.0,
    "max_failed_tasks": 0,
    "max_invalid_tool_calls": 0,
    "max_schema_violations": 0,
    "min_schema_repair_hint_recovery_rate": 0.0,
    "max_schema_repair_hint_failures": 0,
    "max_retry_budget_exhaustions": 0,
    "max_pre_dispatch_blocks": 0,
    "max_trajectory_failures": 0,
    "max_failure_clusters": 0,
    "max_critical_remediations": 0,
}


GATE_PROFILES = {
    "dev": {
        **DEFAULT_GATE_THRESHOLDS,
        "min_success_rate": 0.8,
        "max_failed_tasks": 2,
        "max_invalid_tool_calls": 2,
        "max_schema_violations": 3,
        "max_schema_repair_hint_failures": 2,
        "max_retry_budget_exhaustions": 2,
        "max_pre_dispatch_blocks": 2,
        "max_trajectory_failures": 2,
        "max_failure_clusters": 3,
        "max_critical_remediations": 0,
        "require_suite_schema_evidence": False,
        "require_task_contract_evidence": False,
        "require_provenance_evidence": False,
        "require_pre_run_contract_evidence": False,
        "require_run_attestation_evidence": False,
    },
    "candidate": {
        **DEFAULT_GATE_THRESHOLDS,
        "min_success_rate": 0.95,
        "max_failed_tasks": 1,
        "max_invalid_tool_calls": 0,
        "max_schema_violations": 0,
        "max_schema_repair_hint_failures": 1,
        "max_retry_budget_exhaustions": 0,
        "max_pre_dispatch_blocks": 0,
        "max_trajectory_failures": 0,
        "max_failure_clusters": 1,
        "max_critical_remediations": 0,
        "require_suite_schema_evidence": True,
        "require_task_contract_evidence": True,
        "require_provenance_evidence": True,
        "require_pre_run_contract_evidence": True,
        "require_run_attestation_evidence": True,
    },
    "release": {
        **DEFAULT_GATE_THRESHOLDS,
        "require_suite_schema_evidence": True,
        "require_task_contract_evidence": True,
        "require_provenance_evidence": True,
        "require_pre_run_contract_evidence": True,
        "require_run_attestation_evidence": True,
    },
}


def resolve_gate_profile(profile: str) -> dict[str, Any]:
    try:
        return dict(GATE_PROFILES[profile])
    except KeyError as exc:
        raise ValueError(f"Unknown eval gate profile: {profile}") from exc


def evaluate_eval_run_gate(
    run_dir: str | Path,
    *,
    profile: str = "release",
    min_success_rate: float = DEFAULT_GATE_THRESHOLDS["min_success_rate"],
    max_failed_tasks: int = DEFAULT_GATE_THRESHOLDS["max_failed_tasks"],
    max_invalid_tool_calls: int = DEFAULT_GATE_THRESHOLDS["max_invalid_tool_calls"],
    max_schema_violations: int = DEFAULT_GATE_THRESHOLDS["max_schema_violations"],
    min_schema_repair_hint_recovery_rate: float = DEFAULT_GATE_THRESHOLDS["min_schema_repair_hint_recovery_rate"],
    max_schema_repair_hint_failures: int = DEFAULT_GATE_THRESHOLDS["max_schema_repair_hint_failures"],
    max_retry_budget_exhaustions: int = DEFAULT_GATE_THRESHOLDS["max_retry_budget_exhaustions"],
    max_pre_dispatch_blocks: int = DEFAULT_GATE_THRESHOLDS["max_pre_dispatch_blocks"],
    max_trajectory_failures: int = DEFAULT_GATE_THRESHOLDS["max_trajectory_failures"],
    max_failure_clusters: int = DEFAULT_GATE_THRESHOLDS["max_failure_clusters"],
    max_critical_remediations: int = DEFAULT_GATE_THRESHOLDS["max_critical_remediations"],
    require_suite_schema_evidence: bool = True,
    require_task_contract_evidence: bool = True,
    require_provenance_evidence: bool = True,
    require_pre_run_contract_evidence: bool = True,
    require_run_attestation_evidence: bool = True,
) -> dict[str, Any]:
    profile_config = resolve_gate_profile(profile)
    min_success_rate = float(profile_config["min_success_rate"]) if min_success_rate == DEFAULT_GATE_THRESHOLDS["min_success_rate"] else min_success_rate
    max_failed_tasks = int(profile_config["max_failed_tasks"]) if max_failed_tasks == DEFAULT_GATE_THRESHOLDS["max_failed_tasks"] else max_failed_tasks
    max_invalid_tool_calls = int(profile_config["max_invalid_tool_calls"]) if max_invalid_tool_calls == DEFAULT_GATE_THRESHOLDS["max_invalid_tool_calls"] else max_invalid_tool_calls
    max_schema_violations = int(profile_config["max_schema_violations"]) if max_schema_violations == DEFAULT_GATE_THRESHOLDS["max_schema_violations"] else max_schema_violations
    min_schema_repair_hint_recovery_rate = (
        float(profile_config["min_schema_repair_hint_recovery_rate"])
        if min_schema_repair_hint_recovery_rate == DEFAULT_GATE_THRESHOLDS["min_schema_repair_hint_recovery_rate"]
        else min_schema_repair_hint_recovery_rate
    )
    max_schema_repair_hint_failures = (
        int(profile_config["max_schema_repair_hint_failures"])
        if max_schema_repair_hint_failures == DEFAULT_GATE_THRESHOLDS["max_schema_repair_hint_failures"]
        else max_schema_repair_hint_failures
    )
    max_retry_budget_exhaustions = (
        int(profile_config["max_retry_budget_exhaustions"])
        if max_retry_budget_exhaustions == DEFAULT_GATE_THRESHOLDS["max_retry_budget_exhaustions"]
        else max_retry_budget_exhaustions
    )
    max_pre_dispatch_blocks = (
        int(profile_config["max_pre_dispatch_blocks"])
        if max_pre_dispatch_blocks == DEFAULT_GATE_THRESHOLDS["max_pre_dispatch_blocks"]
        else max_pre_dispatch_blocks
    )
    max_trajectory_failures = (
        int(profile_config["max_trajectory_failures"])
        if max_trajectory_failures == DEFAULT_GATE_THRESHOLDS["max_trajectory_failures"]
        else max_trajectory_failures
    )
    max_failure_clusters = int(profile_config["max_failure_clusters"]) if max_failure_clusters == DEFAULT_GATE_THRESHOLDS["max_failure_clusters"] else max_failure_clusters
    max_critical_remediations = (
        int(profile_config["max_critical_remediations"])
        if max_critical_remediations == DEFAULT_GATE_THRESHOLDS["max_critical_remediations"]
        else max_critical_remediations
    )
    require_suite_schema_evidence = bool(profile_config["require_suite_schema_evidence"]) if require_suite_schema_evidence is True else require_suite_schema_evidence
    require_task_contract_evidence = bool(profile_config["require_task_contract_evidence"]) if require_task_contract_evidence is True else require_task_contract_evidence
    require_provenance_evidence = bool(profile_config["require_provenance_evidence"]) if require_provenance_evidence is True else require_provenance_evidence
    require_pre_run_contract_evidence = bool(profile_config["require_pre_run_contract_evidence"]) if require_pre_run_contract_evidence is True else require_pre_run_contract_evidence
    require_run_attestation_evidence = bool(profile_config["require_run_attestation_evidence"]) if require_run_attestation_evidence is True else require_run_attestation_evidence
    run = load_eval_run(run_dir)
    report = run["report"]
    results = report.get("results", [])
    cluster_summary = _load_cluster_summary(Path(run["run_dir"]))
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    failed_tasks = [str(result.get("task_id", "")) for result in results if result.get("success") is not True]
    aggregates = {
        "failed_tasks": len(failed_tasks),
        "invalid_tool_calls": _sum_metric(results, "invalid_tool_calls"),
        "schema_violations": _sum_metric(results, "schema_violations"),
        "schema_repair_hints_seen": _summary_or_sum(summary, results, "schema_repair_hints_seen"),
        "schema_repair_hint_successes": _summary_or_sum(summary, results, "schema_repair_hint_successes"),
        "schema_repair_hint_failures": _summary_or_sum(summary, results, "schema_repair_hint_failures"),
        "schema_repair_hint_recovery_rate": _summary_rate(summary, results),
        "retry_budget_exhaustions": _sum_metric(results, "retry_budget_exhaustions"),
        "pre_dispatch_blocks": _sum_metric(results, "pre_dispatch_blocks"),
        "trajectory_failures": _sum_metric(results, "trajectory_failures"),
        "failure_clusters": int(cluster_summary["cluster_count"]),
        "critical_remediations": int(cluster_summary["critical_remediations"]),
    }
    thresholds = {
        "min_success_rate": min_success_rate,
        "max_failed_tasks": max_failed_tasks,
        "max_invalid_tool_calls": max_invalid_tool_calls,
        "max_schema_violations": max_schema_violations,
        "min_schema_repair_hint_recovery_rate": min_schema_repair_hint_recovery_rate,
        "max_schema_repair_hint_failures": max_schema_repair_hint_failures,
        "max_retry_budget_exhaustions": max_retry_budget_exhaustions,
        "max_pre_dispatch_blocks": max_pre_dispatch_blocks,
        "max_trajectory_failures": max_trajectory_failures,
        "max_failure_clusters": max_failure_clusters,
        "max_critical_remediations": max_critical_remediations,
    }
    success_rate = float(report.get("success_rate", 0.0))
    failures = _gate_failures(
        success_rate=success_rate,
        aggregates=aggregates,
        thresholds=thresholds,
    )
    if require_suite_schema_evidence:
        failures.extend(_suite_schema_evidence_failures(run["manifest"]))
    if require_task_contract_evidence:
        failures.extend(_task_contract_evidence_failures(run["manifest"]))
    if require_provenance_evidence:
        failures.extend(_provenance_evidence_failures(run["manifest"]))
    run_dir = Path(run["run_dir"])
    pre_run_contract = _load_pre_run_contract(run_dir)
    if require_pre_run_contract_evidence:
        failures.extend(_pre_run_contract_evidence_failures(run["manifest"], pre_run_contract, run_dir))
    if require_run_attestation_evidence:
        failures.extend(verify_run_attestation(run_dir))
    return {
        "run": {
            "run_dir": run["run_dir"],
            "run_name": run["manifest"].get("run_name", Path(run["run_dir"]).name),
            "success_rate": success_rate,
            "task_count": len(results),
            "suite_schema_id": run["manifest"].get("suite_schema_id", ""),
            "suite_schema_sha256": run["manifest"].get("suite_schema_sha256", ""),
            "task_contract_hash": run["manifest"].get("task_contract_hash", ""),
            "task_spec_hash_summary": run["manifest"].get("task_spec_hash_summary", {}),
            "provenance": run["manifest"].get("provenance", {}),
            "provenance_hash": run["manifest"].get("provenance_hash", ""),
            "pre_run_contract_path": str(Path(run["run_dir"]) / "pre-run-contract.json"),
            "pre_run_provenance_hash": pre_run_contract.get("provenance_hash", "") if pre_run_contract else "",
        },
        "passed": not failures,
        "profile": profile,
        "thresholds": thresholds,
        "require_suite_schema_evidence": require_suite_schema_evidence,
        "require_task_contract_evidence": require_task_contract_evidence,
        "require_provenance_evidence": require_provenance_evidence,
        "require_pre_run_contract_evidence": require_pre_run_contract_evidence,
        "require_run_attestation_evidence": require_run_attestation_evidence,
        "aggregates": aggregates,
        "cluster_summary": cluster_summary,
        "failed_tasks": failed_tasks,
        "failures": failures,
    }


def eval_gate_to_markdown(gate: dict[str, Any]) -> str:
    lines = [
        "# Metis Eval Gate",
        "",
        f"Run: {gate['run']['run_name']} ({gate['run']['run_dir']})",
        f"Passed: {gate['passed']}",
        f"Profile: {gate.get('profile', 'release')}",
        f"Success rate: {gate['run']['success_rate']:.2%}",
        f"Suite schema id: {gate['run'].get('suite_schema_id', '')}",
        f"Suite schema sha256: {gate['run'].get('suite_schema_sha256', '')}",
        f"Task contract hash: {gate['run'].get('task_contract_hash', '')}",
        f"Task spec hash summary count: {len(gate['run'].get('task_spec_hash_summary', {}) or {})}",
        f"Provenance hash: {gate['run'].get('provenance_hash', '')}",
        f"Pre-run provenance hash: {gate['run'].get('pre_run_provenance_hash', '')}",
        "",
        "## Failures",
        "",
    ]
    if gate["failures"]:
        lines.extend(f"- {failure}" for failure in gate["failures"])
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Aggregates",
            "",
        ]
    )
    lines.extend(f"- {key}: {value}" for key, value in sorted(gate["aggregates"].items()))
    lines.extend(["", "## Thresholds", ""])
    lines.extend(f"- {key}: {value}" for key, value in sorted(gate["thresholds"].items()))
    return "\n".join(lines) + "\n"


def write_eval_gate_report(gate: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "gate.md").write_text(eval_gate_to_markdown(gate), encoding="utf-8")
    return output_dir


def _gate_failures(*, success_rate: float, aggregates: dict[str, Any], thresholds: dict[str, float | int]) -> list[str]:
    failures: list[str] = []
    if success_rate < float(thresholds["min_success_rate"]):
        failures.append(f"success_rate {success_rate:.4f} < {float(thresholds['min_success_rate']):.4f}")
    observed_hint_rate = float(aggregates["schema_repair_hint_recovery_rate"])
    required_hint_rate = float(thresholds["min_schema_repair_hint_recovery_rate"])
    if observed_hint_rate < required_hint_rate:
        failures.append(f"schema_repair_hint_recovery_rate {observed_hint_rate:.4f} < {required_hint_rate:.4f}")
    for aggregate_key, threshold_key in [
        ("failed_tasks", "max_failed_tasks"),
        ("invalid_tool_calls", "max_invalid_tool_calls"),
        ("schema_violations", "max_schema_violations"),
        ("schema_repair_hint_failures", "max_schema_repair_hint_failures"),
        ("retry_budget_exhaustions", "max_retry_budget_exhaustions"),
        ("pre_dispatch_blocks", "max_pre_dispatch_blocks"),
        ("trajectory_failures", "max_trajectory_failures"),
        ("failure_clusters", "max_failure_clusters"),
        ("critical_remediations", "max_critical_remediations"),
    ]:
        observed = int(aggregates[aggregate_key])
        allowed = int(thresholds[threshold_key])
        if observed > allowed:
            failures.append(f"{aggregate_key} {observed} > {allowed}")
    return failures


def _suite_schema_evidence_failures(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not manifest.get("suite_schema_id"):
        failures.append("suite_schema_id missing from manifest")
    if not manifest.get("suite_schema_sha256"):
        failures.append("suite_schema_sha256 missing from manifest")
    return failures


def _task_contract_evidence_failures(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not manifest.get("task_contract_hash"):
        failures.append("task_contract_hash missing from manifest")
    summary = manifest.get("task_spec_hash_summary")
    if not isinstance(summary, dict) or not summary:
        failures.append("task_spec_hash_summary missing from manifest")
    return failures


def _provenance_evidence_failures(manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    provenance = manifest.get("provenance")
    provenance_hash = manifest.get("provenance_hash")
    if not isinstance(provenance, dict) or not provenance:
        failures.append("provenance missing from manifest")
        return failures
    if not provenance_hash:
        failures.append("provenance_hash missing from manifest")
    elif provenance_hash != eval_provenance_hash(provenance):
        failures.append("provenance_hash does not match provenance payload")
    for key in [
        "suite",
        "suite_schema_sha256",
        "task_contract_hash",
        "model",
        "base_url",
        "profile",
        "tool_inventory_hash",
    ]:
        if not provenance.get(key):
            failures.append(f"provenance.{key} missing from manifest")
    return failures


def _load_pre_run_contract(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "pre-run-contract.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _pre_run_contract_evidence_failures(
    manifest: dict[str, Any],
    pre_run_contract: dict[str, Any] | None,
    run_dir: Path,
) -> list[str]:
    if pre_run_contract is None:
        return ["pre-run-contract.json missing from run directory"]
    failures: list[str] = []
    contract_path = run_dir / "pre-run-contract.json"
    contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    pre_run_provenance = pre_run_contract.get("provenance")
    pre_run_provenance_hash = pre_run_contract.get("provenance_hash")
    if not isinstance(pre_run_provenance, dict) or not pre_run_provenance:
        failures.append("pre-run provenance missing from pre-run-contract.json")
    elif pre_run_provenance_hash != eval_provenance_hash(pre_run_provenance):
        failures.append("pre-run provenance_hash does not match pre-run provenance payload")
    if pre_run_provenance_hash != manifest.get("provenance_hash"):
        failures.append("pre-run provenance_hash does not match manifest provenance_hash")
    if pre_run_contract.get("task_contract_hash") != manifest.get("task_contract_hash"):
        failures.append("pre-run task_contract_hash does not match manifest task_contract_hash")
    if pre_run_contract.get("task_spec_hash_summary") != manifest.get("task_spec_hash_summary"):
        failures.append("pre-run task_spec_hash_summary does not match manifest task_spec_hash_summary")
    if manifest.get("pre_run_contract_path") != str(contract_path):
        failures.append("manifest pre_run_contract_path does not match pre-run contract path")
    if manifest.get("pre_run_contract_sha256") != contract_sha256:
        failures.append("manifest pre_run_contract_sha256 does not match pre-run contract file")
    if manifest.get("pre_run_provenance_hash") != pre_run_provenance_hash:
        failures.append("manifest pre_run_provenance_hash does not match pre-run provenance_hash")
    return failures


def _load_cluster_summary(run_dir: Path) -> dict[str, Any]:
    failures_dir = run_dir / "failures"
    clusters_path = failures_dir / "clusters.json"
    backlog_path = failures_dir / "remediation-backlog.json"
    clusters = {"cluster_count": 0, "clusters": []}
    backlog = {"items": []}
    if clusters_path.exists():
        clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    if backlog_path.exists():
        backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    critical_items = [
        item
        for item in backlog.get("items", [])
        if isinstance(item, dict) and item.get("severity") == "critical"
    ]
    return {
        "cluster_count": int(clusters.get("cluster_count", 0)),
        "cluster_keys": [cluster.get("cluster_key", "") for cluster in clusters.get("clusters", [])],
        "critical_remediations": len(critical_items),
        "critical_cluster_keys": [str(item.get("cluster_key", "")) for item in critical_items],
    }


def _sum_metric(results: list[dict[str, Any]], metric: str) -> int:
    total = 0
    for result in results:
        value = result.get(metric, 0)
        if isinstance(value, bool):
            total += int(value)
        elif isinstance(value, (int, float)):
            total += int(value)
    return total


def _summary_or_sum(summary: dict[str, Any], results: list[dict[str, Any]], metric: str) -> int:
    value = summary.get(metric)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return _sum_metric(results, metric)


def _summary_rate(summary: dict[str, Any], results: list[dict[str, Any]]) -> float:
    value = summary.get("schema_repair_hint_recovery_rate")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    seen = _summary_or_sum(summary, results, "schema_repair_hints_seen")
    successes = _summary_or_sum(summary, results, "schema_repair_hint_successes")
    return successes / seen if seen else 0.0
