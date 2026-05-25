import json
import hashlib

from metis.evals.attestation import (
    verify_repair_plan_attestation,
    verify_targeted_eval_stubs_attestation,
    verify_targeted_eval_suite_attestation,
    write_run_attestation,
)
from metis.evals.compare import (
    build_eval_stubs_from_repair_tasks,
    build_repair_tasks_from_diagnosis,
    build_repair_plan,
    compare_eval_runs,
    diagnose_eval_comparison,
    eval_run_comparison_diagnosis,
    eval_run_diagnosis_to_markdown,
    eval_run_comparison_to_markdown,
    eval_stubs_to_markdown,
    eval_suite_to_markdown,
    load_eval_stubs,
    materialize_eval_suite,
    materialize_eval_suite_from_stubs,
    plan_repairs,
    repair_plan_to_markdown,
    write_eval_run_comparison,
    write_eval_stubs,
    write_materialized_eval_suite,
    write_repair_plan,
)
from metis.evals.suite_validation import validate_eval_suite


def write_run(
    run_dir,
    *,
    run_name,
    success_rate,
    results,
    metadata=None,
    summary=None,
    task_contract_hash=None,
    provenance=None,
    provenance_hash=None,
    task_spec_hash_summary=None,
    pre_run_contract=None,
    pre_run_anchor=True,
    pre_run_anchor_override=None,
):
    metadata = metadata or {}
    summary = summary or {}
    run_dir.mkdir(parents=True)
    manifest = {
        "suite": metadata.get("suite", "real-small-model"),
        "run_name": run_name,
        "success_rate": success_rate,
        "task_count": len(results),
        "summary": summary,
        "metadata": metadata,
    }
    if task_contract_hash is not None:
        manifest["task_contract_hash"] = task_contract_hash
    if provenance is not None:
        manifest["provenance"] = provenance
    if provenance_hash is not None:
        manifest["provenance_hash"] = provenance_hash
    if task_spec_hash_summary is not None:
        manifest["task_spec_hash_summary"] = task_spec_hash_summary
    if pre_run_contract is not None:
        pre_run_path = run_dir / "pre-run-contract.json"
        pre_run_path.write_text(json.dumps(pre_run_contract), encoding="utf-8")
        if pre_run_anchor:
            anchor = pre_run_anchor_override or {
                "pre_run_contract_path": str(pre_run_path),
                "pre_run_contract_sha256": hashlib.sha256(pre_run_path.read_bytes()).hexdigest(),
                "pre_run_provenance_hash": pre_run_contract.get("provenance_hash", ""),
            }
            manifest.update(anchor)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "eval-report.json").write_text(
        json.dumps({"success_rate": success_rate, "summary": summary, "metadata": metadata, "results": results}),
        encoding="utf-8",
    )


def write_clusters(run_dir, *, clusters=None, backlog_items=None):
    clusters = clusters or []
    backlog_items = backlog_items or []
    failures_dir = run_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    (failures_dir / "clusters.json").write_text(
        json.dumps(
            {
                "failure_count": sum(int(cluster.get("count", 0)) for cluster in clusters),
                "cluster_count": len(clusters),
                "clusters": clusters,
            }
        ),
        encoding="utf-8",
    )
    (failures_dir / "remediation-backlog.json").write_text(
        json.dumps(
            {
                "failure_count": sum(int(cluster.get("count", 0)) for cluster in clusters),
                "cluster_count": len(clusters),
                "item_count": len(backlog_items),
                "items": backlog_items,
            }
        ),
        encoding="utf-8",
    )
    (failures_dir / "a.timeline.json").write_text(
        json.dumps(
            {
                "task_id": "a",
                "events": [
                    {"event_id": "a:000:model.response", "event_type": "model.response", "status": "ok"},
                    {
                        "event_id": "a:001:tool.result",
                        "event_type": "tool.result",
                        "status": "blocked",
                        "attributes": {"failed": True, "metadata": {"failure_type": "schema_validation_failed"}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def write_task_specs(run_dir, task_hashes):
    (run_dir / "task-specs.json").write_text(
        json.dumps(
            {
                "task_count": len(task_hashes),
                "tasks": [
                    {
                        "task_id": task_id,
                        "task_spec": {"id": task_id},
                        "task_spec_hashes": hashes,
                    }
                    for task_id, hashes in task_hashes.items()
                ],
            }
        ),
        encoding="utf-8",
    )


def write_run_attestation_for_compare(run_dir):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if not (run_dir / "task-specs.json").exists():
        write_task_specs(run_dir, {})
    write_run_attestation(run_dir, manifest=manifest)


def write_failure_index(run_dir, failures):
    failures_dir = run_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for task_id, payload in failures.items():
        path = failures_dir / f"{task_id}.json"
        timeline_path = failures_dir / f"{task_id}.timeline.json"
        path.write_text(json.dumps({"task_id": task_id, **payload}), encoding="utf-8")
        timeline_path.write_text(
            json.dumps({"task_id": task_id, "events": [{"event_type": "task.end"}]}),
            encoding="utf-8",
        )
        artifacts.append(
            {
                "task_id": task_id,
                "path": str(path),
                "timeline_path": str(timeline_path),
                "errors": len(payload.get("errors", [])),
            }
        )
    (failures_dir / "index.json").write_text(
        json.dumps({"failure_count": len(artifacts), "artifacts": artifacts}),
        encoding="utf-8",
    )


def test_compare_eval_runs_detects_new_failures_and_metric_regressions(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=[
            {"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0},
            {"task_id": "b", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0},
        ],
    )
    write_run(
        current,
        run_name="current",
        success_rate=0.5,
        results=[
            {"task_id": "a", "success": False, "schema_violations": 1, "retry_budget_exhaustions": 0},
            {"task_id": "b", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 1},
            {"task_id": "c", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0},
        ],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)

    assert comparison["has_regression"] is True
    assert comparison["success_rate_delta"] == -0.5
    assert comparison["newly_failed_tasks"] == ["a"]
    assert comparison["new_tasks"] == ["c"]
    assert {"task_id": "a", "metric": "schema_violations", "baseline": 0, "current": 1, "delta": 1} in comparison[
        "regressed_metrics"
    ]
    assert {
        "task_id": "b",
        "metric": "retry_budget_exhaustions",
        "baseline": 0,
        "current": 1,
        "delta": 1,
    } in comparison["regressed_metrics"]


def test_compare_eval_runs_detects_cluster_diffs_and_new_critical_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(
        baseline,
        clusters=[{"cluster_key": "retry_budget_failure", "count": 1, "task_ids": ["old"]}],
        backlog_items=[{"cluster_key": "retry_budget_failure", "severity": "critical"}],
    )
    write_clusters(
        current,
        clusters=[
            {"cluster_key": "schema_failure", "count": 1, "task_ids": ["a"]},
            {"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]},
        ],
        backlog_items=[
            {"cluster_key": "schema_failure", "severity": "critical"},
            {"cluster_key": "trajectory_failure", "severity": "high"},
        ],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert comparison["cluster_diff"]["new_clusters"] == ["schema_failure", "trajectory_failure"]
    assert comparison["cluster_diff"]["resolved_clusters"] == ["retry_budget_failure"]
    assert comparison["cluster_diff"]["new_critical_clusters"] == ["schema_failure"]
    assert comparison["cluster_diff"]["resolved_critical_clusters"] == ["retry_budget_failure"]
    assert "## Cluster Changes" in markdown
    assert "New critical clusters: schema_failure" in markdown


def test_compare_eval_runs_records_noncritical_new_cluster_without_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(baseline)
    write_clusters(
        current,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)

    assert comparison["has_regression"] is False
    assert comparison["cluster_diff"]["new_clusters"] == ["trajectory_failure"]
    assert comparison["cluster_diff"]["new_critical_clusters"] == []


def test_compare_eval_runs_reports_task_spec_hash_drift_without_release_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_task_specs(
        baseline,
        {"a": {"prompt_hash": "p1", "constraints_hash": "c1", "task_spec_hash": "s1"}},
    )
    write_task_specs(
        current,
        {"a": {"prompt_hash": "p2", "constraints_hash": "c1", "task_spec_hash": "s2"}},
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is False
    assert comparison["task_spec_diff"]["prompt_changed"] == [
        {"task_id": "a", "baseline": "p1", "current": "p2"}
    ]
    assert comparison["task_spec_diff"]["task_spec_changed"] == [
        {"task_id": "a", "baseline": "s1", "current": "s2"}
    ]
    assert "## Task Spec Drift" in markdown
    assert "Prompt changed: a" in markdown


def test_compare_eval_runs_reports_manifest_task_contract_hash_drift(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results, task_contract_hash="contract-a")
    write_run(current, run_name="current", success_rate=1.0, results=results, task_contract_hash="contract-b")

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is False
    assert comparison["task_spec_diff"]["task_contract_hash_changed"] == {
        "field": "task_contract_hash",
        "baseline": "contract-a",
        "current": "contract-b",
    }
    assert "Task contract hash changed: contract-a -> contract-b" in markdown


def test_compare_eval_runs_release_profile_blocks_provenance_hash_drift(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    baseline_provenance = {
        "suite": "real-small-model",
        "suite_schema_sha256": "schema-a",
        "task_contract_hash": "contract-a",
        "model": "glm-4.7-flash",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "profile": "small",
        "tool_inventory_hash": "tools-a",
    }
    current_provenance = dict(baseline_provenance)
    current_provenance["tool_inventory_hash"] = "tools-b"
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        provenance=baseline_provenance,
        provenance_hash="prov-a",
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        provenance=current_provenance,
        provenance_hash="prov-b",
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert "provenance_hash_changed" in comparison["regression_reasons"]
    assert comparison["provenance_diff"]["provenance_hash_changed"] == {
        "field": "provenance_hash",
        "baseline": "prov-a",
        "current": "prov-b",
    }
    assert comparison["provenance_diff"]["field_changes"] == [
        {"field": "tool_inventory_hash", "baseline": "tools-a", "current": "tools-b"}
    ]
    assert "## Provenance Drift" in markdown
    assert "Provenance hash changed: prov-a -> prov-b" in markdown
    assert "Provenance field changes: tool_inventory_hash" in markdown


def test_compare_eval_runs_release_profile_blocks_pre_run_post_run_mismatch(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        task_contract_hash="contract-a",
        provenance_hash="prov-a",
        task_spec_hash_summary={"a": {"task_spec_hash": "spec-a"}},
        pre_run_contract={
            "artifact_type": "test-pre-run-contract",
            "provenance_hash": "prov-a",
            "task_contract_hash": "contract-a",
            "task_spec_hash_summary": {"a": {"task_spec_hash": "spec-a"}},
        },
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        task_contract_hash="contract-b",
        provenance_hash="prov-b",
        task_spec_hash_summary={"a": {"task_spec_hash": "spec-b"}},
        pre_run_contract={
            "artifact_type": "test-pre-run-contract",
            "provenance_hash": "prov-before-provider",
            "task_contract_hash": "contract-before-provider",
            "task_spec_hash_summary": {"a": {"task_spec_hash": "spec-before-provider"}},
        },
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert "pre_run_post_run_mismatch" in comparison["regression_reasons"]
    assert comparison["provenance_diff"]["current_pre_run_post_run_mismatches"] == [
        {
            "run": "current",
            "field": "provenance_hash",
            "pre_run": "prov-before-provider",
            "manifest": "prov-b",
        },
        {
            "run": "current",
            "field": "task_contract_hash",
            "pre_run": "contract-before-provider",
            "manifest": "contract-b",
        },
        {
            "run": "current",
            "field": "task_spec_hash_summary",
            "pre_run": {"a": {"task_spec_hash": "spec-before-provider"}},
            "manifest": {"a": {"task_spec_hash": "spec-b"}},
        },
    ]
    assert comparison["regression_reason_links"]["pre_run_post_run_mismatch"]["mismatches"] == comparison[
        "provenance_diff"
    ]["pre_run_post_run_mismatches"]
    assert "Pre-run/post-run mismatches: current.provenance_hash" in markdown
    assert "pre_run_post_run_mismatch: mismatches=current.provenance_hash" in markdown


def test_compare_eval_runs_release_profile_blocks_pre_run_contract_anchor_mismatch(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        task_contract_hash="contract-a",
        provenance_hash="prov-a",
        task_spec_hash_summary={"a": {"task_spec_hash": "spec-a"}},
        pre_run_contract={
            "artifact_type": "test-pre-run-contract",
            "provenance_hash": "prov-a",
            "task_contract_hash": "contract-a",
            "task_spec_hash_summary": {"a": {"task_spec_hash": "spec-a"}},
        },
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        task_contract_hash="contract-a",
        provenance_hash="prov-a",
        task_spec_hash_summary={"a": {"task_spec_hash": "spec-a"}},
        pre_run_contract={
            "artifact_type": "test-pre-run-contract",
            "provenance_hash": "prov-a",
            "task_contract_hash": "contract-a",
            "task_spec_hash_summary": {"a": {"task_spec_hash": "spec-a"}},
        },
        pre_run_anchor_override={
            "pre_run_contract_path": str(current / "pre-run-contract.json"),
            "pre_run_contract_sha256": "bad-sha",
            "pre_run_provenance_hash": "prov-a",
        },
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert "pre_run_post_run_mismatch" in comparison["regression_reasons"]
    assert comparison["provenance_diff"]["current_pre_run_post_run_mismatches"] == [
        {
            "run": "current",
            "field": "pre_run_contract_sha256",
            "pre_run": hashlib.sha256((current / "pre-run-contract.json").read_bytes()).hexdigest(),
            "manifest": "bad-sha",
        }
    ]
    assert "Pre-run/post-run mismatches: current.pre_run_contract_sha256" in markdown


def test_compare_eval_runs_release_profile_blocks_attestation_digest_mismatch(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_task_specs(baseline, {"a": {"task_spec_hash": "spec-a"}})
    write_run_attestation_for_compare(baseline)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_task_specs(current, {"a": {"task_spec_hash": "spec-a"}})
    write_run_attestation_for_compare(current)
    (current / "eval-report.json").write_text(
        json.dumps(
            {
                "success_rate": 1.0,
                "summary": {},
                "metadata": {},
                "results": results,
                "tampered": True,
            }
        ),
        encoding="utf-8",
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert "attestation_untrusted" in comparison["regression_reasons"]
    assert comparison["baseline_untrusted"] is False
    assert comparison["current_untrusted"] is True
    assert {"run": "current", "failure": "run-attestation digest mismatch for eval-report.json"} in comparison[
        "attestation_diff"
    ]["current_failures"]
    assert {"run": "current", "failure": "run-attestation size mismatch for eval-report.json"} in comparison[
        "attestation_diff"
    ]["current_failures"]
    assert comparison["regression_reason_links"]["attestation_untrusted"] == {
        "failures": comparison["attestation_diff"]["comparison_attestation_failures"]
    }
    assert "Artifact Attestation" in markdown
    assert "attestation_untrusted: failures=current.run-attestation digest mismatch for eval-report.json" in markdown


def test_compare_eval_runs_release_profile_blocks_one_sided_missing_attestation(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_task_specs(baseline, {"a": {"task_spec_hash": "spec-a"}})
    write_run_attestation_for_compare(baseline)
    write_run(current, run_name="current", success_rate=1.0, results=results)

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)

    assert comparison["has_regression"] is True
    assert "attestation_untrusted" in comparison["regression_reasons"]
    assert comparison["attestation_diff"]["baseline_present"] is True
    assert comparison["attestation_diff"]["current_present"] is False
    assert comparison["baseline_untrusted"] is False
    assert comparison["current_untrusted"] is True
    assert comparison["attestation_diff"]["current_failures"] == [
        {"run": "current", "failure": "run-attestation.json missing from run directory"}
    ]


def test_compare_eval_runs_strict_profile_blocks_manifest_task_contract_hash_drift(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results, task_contract_hash="contract-a")
    write_run(current, run_name="current", success_rate=1.0, results=results, task_contract_hash="contract-b")

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current, profile="strict")

    assert comparison["has_regression"] is True
    assert "task_contract_hash_changed" in comparison["regression_reasons"]
    assert comparison["regression_reason_links"]["task_contract_hash_changed"]["task_contract_hash_changed"] == {
        "field": "task_contract_hash",
        "baseline": "contract-a",
        "current": "contract-b",
    }


def test_compare_eval_runs_strict_profile_blocks_task_spec_drift(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_task_specs(
        baseline,
        {"a": {"prompt_hash": "p1", "constraints_hash": "c1", "task_spec_hash": "s1"}},
    )
    write_task_specs(
        current,
        {"a": {"prompt_hash": "p1", "constraints_hash": "c2", "task_spec_hash": "s2"}},
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current, profile="strict")

    assert comparison["has_regression"] is True
    assert "task_spec_changed" in comparison["regression_reasons"]


def test_compare_eval_runs_reports_environment_drift_without_release_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        metadata={"suite": "real-small-model", "model": "glm-a", "base_url": "https://a", "profile": "small"},
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        metadata={"suite": "real-small-model", "model": "glm-b", "base_url": "https://b", "profile": "small_strict"},
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is False
    assert comparison["environment_diff"]["model_changed"] == {
        "field": "model",
        "baseline": "glm-a",
        "current": "glm-b",
    }
    assert comparison["environment_diff"]["base_url_changed"]["current"] == "https://b"
    assert comparison["environment_diff"]["profile_changed"]["current"] == "small_strict"
    assert "## Environment Drift" in markdown
    assert "Model changed: glm-a -> glm-b" in markdown


def test_compare_eval_runs_strict_profile_blocks_environment_drift(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        metadata={"model": "glm-a", "profile": "small"},
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        metadata={"model": "glm-b", "profile": "small"},
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current, profile="strict")

    assert comparison["has_regression"] is True
    assert "environment_changed" in comparison["regression_reasons"]


def test_compare_eval_runs_links_task_regression_reasons_to_artifacts(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=[{"task_id": "a", "success": True, "schema_violations": 0}],
    )
    write_run(
        current,
        run_name="current",
        success_rate=0.0,
        results=[{"task_id": "a", "success": False, "schema_violations": 1}],
    )
    write_failure_index(current, {"a": {"errors": ["Schema violations exceeded"], "metrics": {"schema_violations": 1}}})

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["regression_reason_links"]["newly_failed_tasks"]["task_ids"] == ["a"]
    assert "a" in comparison["regression_reason_links"]["newly_failed_tasks"]["artifact_paths"]
    assert "a" in comparison["regression_reason_links"]["newly_failed_tasks"]["timeline_paths"]
    assert comparison["regression_reason_links"]["regressed_metrics"]["metrics"] == [
        {"task_id": "a", "metric": "schema_violations", "baseline": 0, "current": 1, "delta": 1}
    ]
    assert "## Regression Reason Links" in markdown
    assert "newly_failed_tasks: tasks=a" in markdown
    assert "timelines=" in markdown


def test_compare_eval_runs_detects_quality_gate_result_drift(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    baseline_results = [
        {
            "task_id": "a",
            "success": True,
            "schema_violations": 0,
            "quality_gate_results": [
                {"name": "markdown_report", "passed": True, "message": "ok", "metadata": {"path": "report.md"}}
            ],
        }
    ]
    current_results = [
        {
            "task_id": "a",
            "success": True,
            "schema_violations": 0,
            "quality_gate_results": [
                {
                    "name": "markdown_report",
                    "passed": False,
                    "message": "Missing required heading",
                    "metadata": {"path": "report.md"},
                }
            ],
        }
    ]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=baseline_results)
    write_run(current, run_name="current", success_rate=1.0, results=current_results)
    write_failure_index(current, {"a": {"errors": ["quality gate failed"], "metrics": {}}})

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)
    diagnosis = eval_run_comparison_diagnosis(comparison)
    diagnosis_markdown = eval_run_diagnosis_to_markdown(diagnosis)
    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)

    assert comparison["has_regression"] is True
    assert "quality_gate_failed" in comparison["regression_reasons"]
    assert comparison["quality_gate_diff"]["new_failed_gates"] == [
        {
            "task_id": "a",
            "gate": "markdown_report",
            "baseline_passed": True,
            "current_passed": False,
            "current_message": "Missing required heading",
            "current_metadata": {"path": "report.md"},
        }
    ]
    link = comparison["regression_reason_links"]["quality_gate_failed"]
    assert link["task_ids"] == ["a"]
    assert link["quality_gate_changes"] == comparison["quality_gate_diff"]["new_failed_gates"]
    assert "a" in link["artifact_paths"]
    assert "a" in link["timeline_paths"]
    assert "## Quality Gate Drift" in markdown
    assert "a.markdown_report" in markdown
    assert "quality_gate_failed: tasks=a; changes=a.markdown_report" in markdown
    assert diagnosis["entries"][0]["quality_gate_changes"] == comparison["quality_gate_diff"]["new_failed_gates"]
    assert "Quality gate changes: a.markdown_report" in diagnosis_markdown
    task = repair_tasks["tasks"][0]
    assert task["owner_area"] == "quality-gates-and-evidence"
    assert task["quality_gate_changes"] == comparison["quality_gate_diff"]["new_failed_gates"]
    assert "metis/quality/runner.py" in task["likely_source_modules"]
    assert "requires the gate to pass" in task["suggested_eval"]


def test_compare_eval_runs_surfaces_artifact_path_diagnostic_summary(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    baseline_results = [
        {
            "task_id": "a",
            "success": True,
            "quality_gate_results": [
                {"name": "artifact_exists", "passed": True, "message": "ok", "metadata": {"path": "outputs/report.md"}}
            ],
        }
    ]
    current_results = [
        {
            "task_id": "a",
            "success": True,
            "quality_gate_results": [
                {
                    "name": "artifact_exists",
                    "passed": False,
                    "message": "Missing artifacts.",
                    "metadata": {
                        "expected_artifacts": ["outputs/report.md", "C:\\tmp\\report.md"],
                        "missing_artifact_paths": ["../escape.md"],
                    },
                }
            ],
        }
    ]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=baseline_results)
    write_run(current, run_name="current", success_rate=1.0, results=current_results)
    write_failure_index(current, {"a": {"errors": ["quality gate failed"], "metrics": {}}})

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    expected_summary = {
        "total": 2,
        "by_reason": {"parent_traversal": 1, "windows_drive_prefix": 1},
        "by_source": {"expected_artifacts": 1, "missing_artifact_paths": 1},
        "by_gate": {"artifact_exists": 2},
        "by_task": {"a": 2},
    }
    assert comparison["artifact_path_diagnostic_summary"] == expected_summary
    assert "artifact_path_hygiene_failed" in comparison["regression_reasons"]
    assert comparison["regression_reason_links"]["quality_gate_failed"]["artifact_path_diagnostic_summary"] == expected_summary
    assert comparison["regression_reason_links"]["artifact_path_hygiene_failed"]["artifact_path_diagnostic_summary"] == expected_summary
    assert "Artifact path diagnostic summary:" in markdown
    assert "total=2" in markdown
    assert "artifact_path_hygiene_failed: tasks=a" in markdown
    assert "artifact_path_diagnostics=total=2" in markdown
    assert "artifact_path_diagnostics=total=2" in markdown

    repair_tasks = build_repair_tasks_from_diagnosis(eval_run_comparison_diagnosis(comparison))
    hygiene_task = next(task for task in repair_tasks["tasks"] if task["reason"] == "artifact_path_hygiene_failed")
    assert hygiene_task["priority"] == "medium"
    assert hygiene_task["owner_area"] == "eval-suite-hygiene"
    assert "non-portable artifact paths" in hygiene_task["recommended_action"]
    assert "suite hygiene regression" in hygiene_task["suggested_eval"]


def test_compare_eval_runs_links_cluster_regression_reasons_to_artifacts(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(baseline)
    write_clusters(
        current,
        clusters=[{"cluster_key": "schema_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "schema_failure", "severity": "critical"}],
    )
    write_failure_index(current, {"a": {"errors": ["schema"], "metrics": {"schema_violations": 1}}})

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)

    link = comparison["regression_reason_links"]["new_critical_clusters"]
    assert link["cluster_keys"] == ["schema_failure"]
    assert link["task_ids"] == ["a"]
    assert "a" in link["artifact_paths"]
    assert "a" in link["timeline_paths"]


def test_compare_eval_runs_links_strict_drift_reasons(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        metadata={"model": "a"},
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        metadata={"model": "b"},
    )
    write_task_specs(baseline, {"a": {"prompt_hash": "p1", "constraints_hash": "c1", "task_spec_hash": "s1"}})
    write_task_specs(current, {"a": {"prompt_hash": "p2", "constraints_hash": "c1", "task_spec_hash": "s2"}})

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current, profile="strict")

    assert comparison["regression_reason_links"]["environment_changed"]["fields"] == ["model"]
    assert comparison["regression_reason_links"]["task_spec_changed"]["task_ids"] == ["a"]
    assert comparison["regression_reason_links"]["task_spec_changed"]["changes"] == [
        {"task_id": "a", "baseline": "s1", "current": "s2"}
    ]


def test_compare_eval_runs_strict_profile_blocks_noncritical_new_cluster(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(baseline)
    write_clusters(
        current,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current, profile="strict")

    assert comparison["profile"] == "strict"
    assert comparison["has_regression"] is True
    assert comparison["regression_reasons"] == ["new_clusters"]


def test_compare_eval_runs_exploratory_profile_records_without_blocking(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=[{"task_id": "a", "success": True, "schema_violations": 0}],
    )
    write_run(
        current,
        run_name="current",
        success_rate=0.0,
        results=[{"task_id": "a", "success": False, "schema_violations": 1}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current, profile="exploratory")
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["profile"] == "exploratory"
    assert comparison["newly_failed_tasks"] == ["a"]
    assert comparison["regressed_metrics"] == [
        {"task_id": "a", "metric": "schema_violations", "baseline": 0, "current": 1, "delta": 1}
    ]
    assert comparison["has_regression"] is False
    assert comparison["regression_reasons"] == []
    assert "Profile: exploratory" in markdown


def test_compare_eval_runs_detects_critical_severity_upgrade_as_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(
        baseline,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )
    write_clusters(
        current,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "critical"}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert comparison["cluster_diff"]["new_clusters"] == []
    assert comparison["cluster_diff"]["new_critical_clusters"] == ["trajectory_failure"]
    assert comparison["cluster_diff"]["critical_severity_upgrades"] == [
        {
            "cluster_key": "trajectory_failure",
            "baseline_severity": "high",
            "current_severity": "critical",
        }
    ]
    assert "Critical severity upgrades: trajectory_failure:high->critical" in markdown


def test_compare_eval_runs_records_severity_downgrade_without_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(
        baseline,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "critical"}],
    )
    write_clusters(
        current,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)

    assert comparison["has_regression"] is False
    assert comparison["cluster_diff"]["resolved_critical_clusters"] == ["trajectory_failure"]
    assert comparison["cluster_diff"]["severity_downgrades"] == [
        {
            "cluster_key": "trajectory_failure",
            "baseline_severity": "critical",
            "current_severity": "high",
        }
    ]


def test_compare_eval_runs_detects_critical_cluster_count_growth_as_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(
        baseline,
        clusters=[{"cluster_key": "schema_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "schema_failure", "severity": "critical"}],
    )
    write_clusters(
        current,
        clusters=[{"cluster_key": "schema_failure", "count": 3, "task_ids": ["a", "b"]}],
        backlog_items=[{"cluster_key": "schema_failure", "severity": "critical"}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert comparison["cluster_diff"]["critical_cluster_count_increases"] == [
        {"cluster_key": "schema_failure", "field": "count", "baseline": 1, "current": 3, "delta": 2}
    ]
    assert comparison["cluster_diff"]["critical_cluster_affected_task_increases"] == [
        {
            "cluster_key": "schema_failure",
            "field": "affected_task_count",
            "baseline": 1,
            "current": 2,
            "delta": 1,
        }
    ]
    assert "Critical cluster count increases: schema_failure:1->3 (+2)" in markdown


def test_compare_eval_runs_records_noncritical_cluster_count_growth_without_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0, "retry_budget_exhaustions": 0}]
    write_run(baseline, run_name="baseline", success_rate=1.0, results=results)
    write_run(current, run_name="current", success_rate=1.0, results=results)
    write_clusters(
        baseline,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )
    write_clusters(
        current,
        clusters=[{"cluster_key": "trajectory_failure", "count": 2, "task_ids": ["a", "b"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)

    assert comparison["has_regression"] is False
    assert comparison["cluster_diff"]["cluster_count_increases"] == [
        {"cluster_key": "trajectory_failure", "field": "count", "baseline": 1, "current": 2, "delta": 1}
    ]
    assert comparison["cluster_diff"]["critical_cluster_count_increases"] == []


def test_compare_eval_runs_detects_recovery_without_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    write_run(
        baseline,
        run_name="baseline",
        success_rate=0.0,
        results=[{"task_id": "a", "success": False, "schema_violations": 1}],
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=[{"task_id": "a", "success": True, "schema_violations": 0}],
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is False
    assert comparison["recovered_tasks"] == ["a"]
    assert "Recovered: a" in markdown
    assert "Has regression: False" in markdown


def test_compare_eval_runs_detects_schema_repair_hint_summary_regression(tmp_path):
    baseline = tmp_path / "baseline"
    current = tmp_path / "current"
    results = [{"task_id": "a", "success": True, "schema_violations": 0}]
    write_run(
        baseline,
        run_name="baseline",
        success_rate=1.0,
        results=results,
        summary={
            "schema_repair_hint_recovery_rate": 1.0,
            "schema_repair_hint_failures": 0,
            "schema_repair_hint_type_failures": {"add_required_property": 0},
        },
    )
    write_run(
        current,
        run_name="current",
        success_rate=1.0,
        results=results,
        summary={
            "schema_repair_hint_recovery_rate": 0.5,
            "schema_repair_hint_failures": 2,
            "schema_repair_hint_type_failures": {"add_required_property": 2},
        },
    )

    comparison = compare_eval_runs(baseline_dir=baseline, current_dir=current)
    markdown = eval_run_comparison_to_markdown(comparison)

    assert comparison["has_regression"] is True
    assert "schema_repair_hint_recovery_rate_decreased" in comparison["regression_reasons"]
    assert "schema_repair_hint_failures_increased" in comparison["regression_reasons"]
    assert "schema_repair_hint_type_failures_increased" in comparison["regression_reasons"]
    assert comparison["summary_diff"]["schema_repair_hint_recovery_rate"] == {
        "field": "schema_repair_hint_recovery_rate",
        "baseline": 1.0,
        "current": 0.5,
        "delta": -0.5,
    }
    assert comparison["summary_diff"]["schema_repair_hint_type_failure_increases"] == [
        {
            "key": "add_required_property",
            "field": "schema_repair_hint_type_failures",
            "baseline": 0,
            "current": 2,
            "delta": 2,
        }
    ]
    assert comparison["regression_reason_links"]["schema_repair_hint_recovery_rate_decreased"]["change"]["delta"] == -0.5
    assert "## Summary Drift" in markdown
    assert "Schema repair hint recovery rate: 1.0000 -> 0.5000 (-0.5000)" in markdown
    assert "Schema repair hint type failure increases: add_required_property:0->2 (+2)" in markdown
    assert (
        "schema_repair_hint_recovery_rate_decreased: "
        "change=schema_repair_hint_recovery_rate:1.0000 -> 0.5000 (-0.5000)"
    ) in markdown
    assert "schema_repair_hint_type_failures_increased: changes=add_required_property:0->2 (+2)" in markdown


def test_write_eval_run_comparison_outputs_json_and_markdown(tmp_path):
    comparison = {
        "baseline": {"run_name": "base", "run_dir": "base"},
        "current": {"run_name": "current", "run_dir": "current"},
        "success_rate_delta": 0.0,
        "has_regression": False,
        "newly_failed_tasks": [],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
        "regression_reasons": [],
        "regression_reason_links": {},
    }

    output_dir = write_eval_run_comparison(comparison, tmp_path / "comparison")

    assert (output_dir / "comparison.json").exists()
    assert (output_dir / "comparison.md").exists()
    assert (output_dir / "diagnosis.json").exists()
    assert (output_dir / "diagnosis.md").exists()


def test_eval_run_comparison_diagnosis_summarizes_reason_links():
    comparison = {
        "profile": "release",
        "has_regression": True,
        "baseline": {"run_name": "base"},
        "current": {"run_name": "current"},
        "regression_reasons": ["newly_failed_tasks"],
        "regression_reason_links": {
            "newly_failed_tasks": {
                "task_ids": ["a"],
                "artifact_paths": {"a": "failures/a.json"},
            }
        },
    }

    diagnosis = eval_run_comparison_diagnosis(comparison)

    assert diagnosis["entry_count"] == 1
    assert diagnosis["entries"][0]["reason"] == "newly_failed_tasks"
    assert diagnosis["entries"][0]["task_ids"] == ["a"]
    assert diagnosis["entries"][0]["artifact_paths"] == {"a": "failures/a.json"}
    assert diagnosis["entries"][0]["timeline_paths"] == {}
    assert "Open the linked failure artifacts" in diagnosis["entries"][0]["recommended_action"]


def test_eval_run_comparison_diagnosis_preserves_attestation_trust_state():
    comparison = {
        "profile": "release",
        "has_regression": True,
        "baseline": {"run_name": "base"},
        "current": {"run_name": "current"},
        "baseline_untrusted": False,
        "current_untrusted": True,
        "regression_reasons": ["attestation_untrusted"],
        "regression_reason_links": {
            "attestation_untrusted": {
                "failures": [
                    {"run": "current", "failure": "run-attestation digest mismatch for eval-report.json"}
                ]
            }
        },
    }

    diagnosis = eval_run_comparison_diagnosis(comparison)
    markdown = eval_run_diagnosis_to_markdown(diagnosis)
    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)

    assert diagnosis["baseline_untrusted"] is False
    assert diagnosis["current_untrusted"] is True
    assert diagnosis["entries"][0]["trust_state"] == {
        "baseline_untrusted": False,
        "current_untrusted": True,
        "baseline_failures": [],
        "current_failures": [
            {"run": "current", "failure": "run-attestation digest mismatch for eval-report.json"}
        ],
    }
    assert "Current untrusted: True" in markdown
    assert "Trust state: baseline_untrusted=False, current_untrusted=True, current_failures=1" in markdown
    task = repair_tasks["tasks"][0]
    assert task["priority"] == "critical"
    assert task["owner_area"] == "artifact-integrity-and-provenance"
    assert task["trust_state"] == diagnosis["entries"][0]["trust_state"]
    assert "metis/evals/attestation.py" in task["likely_source_modules"]
    assert "Regenerate or repair the untrusted run artifact bundle" in task["suggested_eval"]


def test_eval_run_comparison_diagnosis_summarizes_schema_repair_hint_events(tmp_path):
    timeline_path = tmp_path / "a.timeline.json"
    timeline_path.write_text(
        json.dumps(
            {
                "task_id": "a",
                "events": [
                    {
                        "event_id": "a:001:tool.result",
                        "event_type": "tool.result",
                        "status": "blocked",
                        "tool_name": "write_file",
                        "tool_call_id": "c1",
                        "attributes": {"failed": True, "metadata": {"failure_type": "schema_validation_failed"}},
                    },
                    {
                        "event_id": "a:002:schema.repair_hint",
                        "event_type": "schema.repair_hint",
                        "status": "emitted",
                        "tool_name": "write_file",
                        "tool_call_id": "c1",
                        "attributes": {
                            "parent_event_id": "a:001:tool.result",
                            "schema_errors": ["$.path: missing required property"],
                            "schema_repair_hints": ["Add the required argument $.path."],
                            "schema_repair_hint_types": ["add_required_property"],
                            "schema_repair_hint_details": [
                                {
                                    "hint_type": "add_required_property",
                                    "schema_path": "$.path",
                                    "schema_keyword": "required",
                                }
                            ],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    comparison = {
        "profile": "release",
        "has_regression": True,
        "baseline": {"run_name": "base"},
        "current": {"run_name": "current"},
        "regression_reasons": ["schema_repair_hint_type_failures_increased"],
        "regression_reason_links": {
            "schema_repair_hint_type_failures_increased": {
                "task_ids": ["a"],
                "timeline_paths": {"a": str(timeline_path)},
            }
        },
    }

    diagnosis = eval_run_comparison_diagnosis(comparison)
    markdown = eval_run_diagnosis_to_markdown(diagnosis)
    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)

    hint_event = diagnosis["entries"][0]["schema_repair_hint_events"]["a"][0]
    assert hint_event["event_id"] == "a:002:schema.repair_hint"
    assert hint_event["parent_event_id"] == "a:001:tool.result"
    assert hint_event["hint_types"] == ["add_required_property"]
    assert hint_event["hints"] == ["Add the required argument $.path."]
    assert hint_event["hint_details"][0]["schema_path"] == "$.path"
    assert "Schema repair hint events: a=a:002:schema.repair_hint(add_required_property)" in markdown
    assert repair_tasks["tasks"][0]["schema_repair_hint_events"] == diagnosis["entries"][0]["schema_repair_hint_events"]


def test_eval_run_comparison_diagnosis_carries_timeline_run_metadata(tmp_path):
    timeline_path = tmp_path / "a.timeline.json"
    run_metadata = {
        "suite": "real-small-model",
        "run_name": "current",
        "pre_run_contract_path": "docs/evals/runs/current/pre-run-contract.json",
        "pre_run_contract_sha256": "contract-sha",
        "pre_run_provenance_hash": "pre-prov",
        "provenance_hash": "post-prov",
        "task_contract_hash": "task-contract",
        "suite_schema_sha256": "schema-sha",
    }
    timeline_path.write_text(
        json.dumps(
            {
                "task_id": "a",
                "run_metadata": run_metadata,
                "events": [{"event_id": "a:000:task.start", "event_type": "task.start"}],
            }
        ),
        encoding="utf-8",
    )
    comparison = {
        "profile": "release",
        "has_regression": True,
        "baseline": {"run_name": "base"},
        "current": {"run_name": "current"},
        "regression_reasons": ["newly_failed_tasks"],
        "regression_reason_links": {
            "newly_failed_tasks": {
                "task_ids": ["a"],
                "timeline_paths": {"a": str(timeline_path)},
            }
        },
    }

    diagnosis = eval_run_comparison_diagnosis(comparison)
    markdown = eval_run_diagnosis_to_markdown(diagnosis)
    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)

    assert diagnosis["entries"][0]["run_metadata"] == {"a": run_metadata}
    assert repair_tasks["tasks"][0]["run_metadata"] == {"a": run_metadata}
    assert "pre_run_contract_sha256=contract-sha" in markdown
    assert "pre_run_provenance_hash=pre-prov" in markdown


def test_build_repair_tasks_from_diagnosis_links_backlog_items(tmp_path):
    current = tmp_path / "current"
    failures_dir = current / "failures"
    failures_dir.mkdir(parents=True)
    (failures_dir / "remediation-backlog.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "remediation-001",
                        "cluster_key": "schema_failure",
                        "severity": "critical",
                        "owner_area": "tool-schema-and-repair",
                        "recommended_action": "Tighten schema feedback.",
                        "suggested_eval": "Add schema repair eval.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (failures_dir / "a.timeline.json").write_text(
        json.dumps(
            {
                "task_id": "a",
                "events": [
                    {"event_id": "a:000:model.response", "event_type": "model.response", "status": "ok"},
                    {
                        "event_id": "a:001:tool.result",
                        "event_type": "tool.result",
                        "status": "blocked",
                        "attributes": {"failed": True, "metadata": {"failure_type": "schema_validation_failed"}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    diagnosis = {
        "profile": "release",
        "current": {"run_dir": str(current)},
        "entries": [
            {
                "reason": "new_critical_clusters",
                "task_ids": ["a"],
                "cluster_keys": ["schema_failure"],
                "artifact_paths": {"a": str(failures_dir / "a.json")},
                "timeline_paths": {"a": str(failures_dir / "a.timeline.json")},
                "recommended_action": "fallback",
            }
        ],
    }

    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)

    assert repair_tasks["task_count"] == 1
    task = repair_tasks["tasks"][0]
    assert task["priority"] == "critical"
    assert task["owner_area"] == "tool-schema-and-repair"
    assert task["timeline_paths"] == {"a": str(failures_dir / "a.timeline.json")}
    assert task["timeline_event_ids"] == {"a": ["a:000:model.response", "a:001:tool.result"]}
    assert task["critical_event_ids"] == {"a": "a:001:tool.result"}
    assert "metis/tools/schema_validator.py" in task["likely_source_modules"]
    assert "metis/tools/dispatcher.py" in task["likely_source_modules"]
    assert task["source_backlog_items"] == ["remediation-001"]
    assert task["recommended_action"] == "Tighten schema feedback."
    assert task["suggested_eval"] == "Add schema repair eval."


def test_build_repair_tasks_prefers_schema_repair_hint_critical_event(tmp_path):
    current = tmp_path / "current"
    failures_dir = current / "failures"
    failures_dir.mkdir(parents=True)
    (failures_dir / "a.timeline.json").write_text(
        json.dumps(
            {
                "task_id": "a",
                "events": [
                    {
                        "event_id": "a:001:tool.result",
                        "event_type": "tool.result",
                        "status": "blocked",
                        "attributes": {"failed": True, "metadata": {"failure_type": "schema_validation_failed"}},
                    },
                    {
                        "event_id": "a:002:schema.repair_hint",
                        "event_type": "schema.repair_hint",
                        "status": "emitted",
                        "attributes": {
                            "parent_event_id": "a:001:tool.result",
                            "schema_repair_hints": ["Add the required argument $.path."],
                            "schema_repair_hint_details": [{"hint_type": "add_required_property"}],
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    diagnosis = {
        "profile": "release",
        "current": {"run_dir": str(current)},
        "entries": [
            {
                "reason": "schema_repair_hint_type_failures_increased",
                "task_ids": ["a"],
                "cluster_keys": ["schema_repair_hint_failure_type:add_required_property"],
                "timeline_paths": {"a": str(failures_dir / "a.timeline.json")},
            }
        ],
    }

    repair_tasks = build_repair_tasks_from_diagnosis(diagnosis)

    task = repair_tasks["tasks"][0]
    assert task["timeline_event_ids"] == {"a": ["a:001:tool.result", "a:002:schema.repair_hint"]}
    assert task["critical_event_ids"] == {"a": "a:002:schema.repair_hint"}


def test_diagnose_eval_comparison_writes_repair_task_outputs(tmp_path):
    comparison_dir = tmp_path / "comparison"
    comparison_dir.mkdir()
    (comparison_dir / "diagnosis.json").write_text(
        json.dumps(
            {
                "profile": "release",
                "current": {"run_dir": str(tmp_path / "current")},
                "entries": [
                    {
                        "reason": "newly_failed_tasks",
                        "task_ids": ["a"],
                        "artifact_paths": {"a": "failures/a.json"},
                        "recommended_action": "Open artifacts.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    repair_tasks = diagnose_eval_comparison(comparison_dir)

    assert repair_tasks["task_count"] == 1
    assert (comparison_dir / "repair-tasks.json").exists()
    assert (comparison_dir / "repair-tasks.md").exists()


def test_build_repair_plan_groups_tasks_by_priority_and_owner():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-002",
                "reason": "regressed_metrics",
                "priority": "high",
                "owner_area": "harness-runtime",
                "cluster_keys": ["trajectory_failure"],
                "recommended_action": "Fix trajectory loop.",
                "suggested_eval": "Add trajectory eval.",
            },
            {
                "id": "repair-001",
                "reason": "new_critical_clusters",
                "priority": "critical",
                "owner_area": "tool-schema-and-repair",
                "cluster_keys": ["schema_failure"],
                "critical_event_ids": {"schema-task": "schema-task:001:tool.result"},
                "likely_source_modules": ["metis/tools/schema_validator.py", "metis/tools/dispatcher.py"],
                "recommended_action": "Fix schema repair.",
                "suggested_eval": "Add schema eval.",
            },
        ],
    }

    plan = build_repair_plan(repair_tasks)
    markdown = repair_plan_to_markdown(plan)

    assert plan["task_count"] == 2
    assert [task["id"] for task in plan["tasks"]] == ["repair-001", "repair-002"]
    assert plan["priority_buckets"]["critical"] == ["repair-001"]
    assert plan["priority_buckets"]["high"] == ["repair-002"]
    assert plan["owner_areas"][0]["owner_area"] == "tool-schema-and-repair"
    assert plan["owner_areas"][0]["critical_event_ids"] == ["schema-task:001:tool.result"]
    assert "metis/tools/schema_validator.py" in plan["owner_areas"][0]["likely_source_modules"]
    assert plan["phases"][0]["task_ids"] == ["repair-001", "repair-002"]
    assert "Metis Repair Plan" in markdown
    assert "tool-schema-and-repair" in markdown
    assert "schema-task:001:tool.result" in markdown
    assert "metis/tools/schema_validator.py" in markdown


def test_build_repair_plan_puts_artifact_integrity_before_behavior_repairs():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-002",
                "reason": "newly_failed_tasks",
                "priority": "high",
                "owner_area": "harness-runtime",
                "suggested_eval": "Add behavior eval.",
            },
            {
                "id": "repair-001",
                "reason": "attestation_untrusted",
                "priority": "critical",
                "owner_area": "artifact-integrity-and-provenance",
                "trust_state": {
                    "baseline_untrusted": False,
                    "current_untrusted": True,
                    "baseline_failures": [],
                    "current_failures": [
                        {"run": "current", "failure": "run-attestation digest mismatch for eval-report.json"}
                    ],
                },
                "likely_source_modules": ["metis/evals/attestation.py", "metis/evals/compare.py"],
                "suggested_eval": "Regenerate or repair the untrusted run artifact bundle.",
            },
        ],
    }

    plan = build_repair_plan(repair_tasks)
    markdown = repair_plan_to_markdown(plan)

    assert plan["phases"][0]["id"] == "phase-0-restore-artifact-trust"
    assert plan["phases"][0]["task_ids"] == ["repair-001"]
    assert plan["phases"][0]["phase_type"] == "precondition"
    assert plan["phases"][0]["hard_precondition"] is True
    assert plan["phases"][0]["requires_completed_preconditions"] == []
    assert "model_behavior_repair" in plan["phases"][0]["blocks"]
    assert plan["phases"][1]["id"] == "phase-1-stop-release-blockers"
    assert plan["phases"][1]["task_ids"] == ["repair-001", "repair-002"]
    assert plan["phases"][1]["requires_completed_preconditions"] == ["phase-0-restore-artifact-trust"]
    assert plan["owner_areas"][0]["owner_area"] == "artifact-integrity-and-provenance"
    assert "Restore artifact trust" in markdown
    assert "Repair or regenerate untrusted run bundles" in markdown
    assert "Hard precondition: true" in markdown


def test_build_repair_plan_puts_suite_hygiene_before_behavior_repairs():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-002",
                "reason": "newly_failed_tasks",
                "priority": "high",
                "owner_area": "harness-runtime",
                "suggested_eval": "Add behavior eval.",
            },
            {
                "id": "repair-001",
                "reason": "artifact_path_hygiene_failed",
                "priority": "medium",
                "owner_area": "eval-suite-hygiene",
                "recommended_action": "Remove non-portable artifact paths before release.",
                "suggested_eval": "Add suite hygiene regression.",
            },
        ],
    }

    plan = build_repair_plan(repair_tasks)
    markdown = repair_plan_to_markdown(plan)

    phase_ids = [phase["id"] for phase in plan["phases"]]
    assert phase_ids.index("phase-0b-repair-suite-hygiene") < phase_ids.index("phase-1-stop-release-blockers")

    hygiene_phase = next(phase for phase in plan["phases"] if phase["id"] == "phase-0b-repair-suite-hygiene")
    release_phase = next(phase for phase in plan["phases"] if phase["id"] == "phase-1-stop-release-blockers")
    targeted_eval_phase = next(phase for phase in plan["phases"] if phase["id"] == "phase-2-add-targeted-evals")
    owner_phase = next(phase for phase in plan["phases"] if phase["id"] == "phase-3-stabilize-owners")

    assert hygiene_phase["task_ids"] == ["repair-001"]
    assert hygiene_phase["phase_type"] == "precondition"
    assert hygiene_phase["hard_precondition"] is True
    assert hygiene_phase["requires_completed_preconditions"] == []
    assert hygiene_phase["status"] == "open"
    assert hygiene_phase["blocked_by"] == []
    assert "release_decision" in hygiene_phase["blocks"]
    assert release_phase["requires_completed_preconditions"] == ["phase-0b-repair-suite-hygiene"]
    assert release_phase["status"] == "blocked"
    assert release_phase["blocked_by"] == ["phase-0b-repair-suite-hygiene"]
    assert release_phase["task_ids"] == ["repair-002"]
    assert targeted_eval_phase["task_ids"] == ["repair-002", "repair-001"]
    assert targeted_eval_phase["requires_completed_preconditions"] == ["phase-0b-repair-suite-hygiene"]
    assert targeted_eval_phase["status"] == "blocked"
    assert owner_phase["task_ids"] == ["repair-001"]
    assert plan["phase_status_summary"]["counts"]["open"] == 1
    assert plan["phase_status_summary"]["counts"]["blocked"] == 3
    assert plan["phase_status_summary"]["blocked_phases"] == [
        "phase-1-stop-release-blockers",
        "phase-2-add-targeted-evals",
        "phase-3-stabilize-owners",
    ]
    assert plan["phase_status_summary"]["executable_phases"] == ["phase-0b-repair-suite-hygiene"]
    assert plan["phase_status_summary"]["hard_preconditions_open"] == ["phase-0b-repair-suite-hygiene"]
    assert plan["owner_areas"][1]["owner_area"] == "eval-suite-hygiene"
    assert "Repair suite hygiene" in markdown
    assert "Remove non-portable artifact paths" in markdown
    assert "Status: blocked" in markdown
    assert "Blocked by: phase-0b-repair-suite-hygiene" in markdown


def test_build_repair_plan_puts_artifact_trust_before_suite_hygiene():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-002",
                "reason": "artifact_path_hygiene_failed",
                "priority": "medium",
                "owner_area": "eval-suite-hygiene",
            },
            {
                "id": "repair-001",
                "reason": "attestation_untrusted",
                "priority": "critical",
                "owner_area": "artifact-integrity-and-provenance",
                "trust_state": {"current_untrusted": True},
            },
        ],
    }

    plan = build_repair_plan(repair_tasks)

    assert [phase["id"] for phase in plan["phases"][:2]] == [
        "phase-0-restore-artifact-trust",
        "phase-0b-repair-suite-hygiene",
    ]
    assert plan["phases"][0]["task_ids"] == ["repair-001"]
    assert plan["phases"][1]["task_ids"] == ["repair-002"]
    assert plan["phases"][0]["requires_completed_preconditions"] == []
    assert plan["phases"][1]["requires_completed_preconditions"] == ["phase-0-restore-artifact-trust"]
    assert plan["phases"][2]["requires_completed_preconditions"] == [
        "phase-0-restore-artifact-trust",
        "phase-0b-repair-suite-hygiene",
    ]


def test_build_repair_plan_unblocks_phases_after_preconditions_complete():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-001",
                "reason": "artifact_path_hygiene_failed",
                "priority": "medium",
                "owner_area": "eval-suite-hygiene",
                "status": "verified",
            },
            {
                "id": "repair-002",
                "reason": "newly_failed_tasks",
                "priority": "high",
                "owner_area": "harness-runtime",
            },
        ],
    }

    plan = build_repair_plan(repair_tasks)

    hygiene_phase = next(phase for phase in plan["phases"] if phase["id"] == "phase-0b-repair-suite-hygiene")
    release_phase = next(phase for phase in plan["phases"] if phase["id"] == "phase-1-stop-release-blockers")

    assert hygiene_phase["status"] == "verified"
    assert release_phase["status"] == "open"
    assert release_phase["blocked_by"] == []
    assert plan["phase_status_summary"]["hard_preconditions_open"] == []
    assert "phase-1-stop-release-blockers" in plan["phase_status_summary"]["executable_phases"]


def test_plan_repairs_loads_tasks_and_writes_plan(tmp_path):
    repair_dir = tmp_path / "repair"
    output_dir = tmp_path / "plan"
    repair_dir.mkdir()
    (repair_dir / "repair-tasks.json").write_text(
        json.dumps(
            {
                "profile": "release",
                "tasks": [
                    {
                        "id": "repair-001",
                        "reason": "newly_failed_tasks",
                        "priority": "high",
                        "owner_area": "harness-runtime",
                        "suggested_eval": "Add focused eval.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_repairs(repair_dir, output_dir=output_dir)

    assert plan["task_count"] == 1
    assert (output_dir / "repair-plan.json").exists()
    assert (output_dir / "repair-plan.md").exists()
    assert (output_dir / "repair-plan-attestation.json").exists()
    assert (output_dir / "repair-plan-attestation.md").exists()
    assert verify_repair_plan_attestation(output_dir) == []


def test_write_repair_plan_outputs_json_and_markdown(tmp_path):
    plan = {"profile": "release", "task_count": 0, "tasks": [], "priority_buckets": {}, "owner_areas": [], "phases": []}

    output_dir = write_repair_plan(plan, tmp_path / "plan")

    assert (output_dir / "repair-plan.json").exists()
    assert (output_dir / "repair-plan.md").exists()
    attestation = json.loads((output_dir / "repair-plan-attestation.json").read_text(encoding="utf-8"))
    subjects = {subject["name"]: subject for subject in attestation["subject"]}
    assert attestation["predicateType"] == "https://metis.local/attestations/repair-plan/v1"
    assert attestation["predicate"]["profile"] == "release"
    assert set(subjects) == {"repair-plan.json", "repair-plan.md"}
    assert "repair-plan-attestation.json" not in subjects
    assert verify_repair_plan_attestation(output_dir) == []


def test_verify_repair_plan_attestation_detects_digest_drift(tmp_path):
    plan = {"profile": "release", "task_count": 0, "tasks": [], "priority_buckets": {}, "owner_areas": [], "phases": []}
    output_dir = write_repair_plan(plan, tmp_path / "plan")

    (output_dir / "repair-plan.md").write_text("tampered", encoding="utf-8")

    assert "repair-plan-attestation digest mismatch for repair-plan.md" in verify_repair_plan_attestation(output_dir)


def test_build_eval_stubs_from_repair_tasks_creates_targeted_schema_eval():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-001",
                "reason": "new_critical_clusters",
                "priority": "critical",
                "owner_area": "tool-schema-and-repair",
                "cluster_keys": ["schema_failure"],
                "critical_event_ids": {"a": "a:001:tool.result"},
                "run_metadata": {
                    "a": {
                        "pre_run_contract_sha256": "contract-sha",
                        "pre_run_provenance_hash": "pre-prov",
                        "provenance_hash": "post-prov",
                        "task_contract_hash": "task-contract",
                    }
                },
                "likely_source_modules": ["metis/tools/schema_validator.py", "metis/tools/dispatcher.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    markdown = eval_stubs_to_markdown(stubs)

    assert stubs["stub_count"] == 1
    stub = stubs["stubs"][0]
    assert stub["id"] == "targeted-repair-001"
    assert stub["source_repair_task_id"] == "repair-001"
    assert stub["critical_event_ids"] == {"a": "a:001:tool.result"}
    assert stub["run_metadata"] == repair_tasks["tasks"][0]["run_metadata"]
    assert stub["eval_task_spec"]["min_schema_repair_successes"] == 1
    assert stub["eval_task_spec"]["allow_recovered_schema_failures"] is True
    assert "tests\\unit\\test_tool_schema_validator.py" in stub["verification_command"]
    assert "targeted-repair-001" in markdown
    assert "a:001:tool.result" in markdown
    assert "pre_run_contract_sha256=contract-sha" in markdown


def test_build_eval_stubs_from_attestation_untrusted_creates_artifact_fixture():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-001",
                "reason": "attestation_untrusted",
                "priority": "critical",
                "owner_area": "artifact-integrity-and-provenance",
                "trust_state": {
                    "baseline_untrusted": False,
                    "current_untrusted": True,
                    "baseline_failures": [],
                    "current_failures": [
                        {"run": "current", "failure": "run-attestation digest mismatch for eval-report.json"}
                    ],
                },
                "likely_source_modules": ["metis/evals/attestation.py", "metis/evals/compare.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    markdown = eval_stubs_to_markdown(stubs)
    suite = materialize_eval_suite_from_stubs(stubs)

    stub = stubs["stubs"][0]
    assert stub["id"] == "artifact-verification-repair-001"
    assert stub["stub_type"] == "artifact_verification"
    assert stub["target_runs"] == ["current"]
    assert stub["trust_state"] == repair_tasks["tasks"][0]["trust_state"]
    assert stub["eval_task_spec"]["fixture_type"] == "artifact_verification"
    assert stub["eval_task_spec"]["requires_model_execution"] is False
    assert stub["eval_task_spec"]["allowed_tools"] == []
    assert stub["eval_task_spec"]["max_turns"] == 1
    assert stub["eval_task_spec"]["quality_gates"] == ["run_attestation_verifies"]
    assert "run attestation verification passes" in stub["eval_task_spec"]["prompt"]
    assert "tests\\unit\\test_run_attestation.py" in stub["verification_command"]
    assert "Stub type: artifact_verification" in markdown
    assert "Target runs: current" in markdown
    task = suite["tasks"][0]
    assert task["stub_type"] == "artifact_verification"
    assert task["target_runs"] == ["current"]
    assert task["trust_state"] == repair_tasks["tasks"][0]["trust_state"]
    assert task["task_spec"]["requires_model_execution"] is False


def test_build_eval_stubs_from_quality_gate_failure_preserves_gate_context():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-001",
                "reason": "quality_gate_failed",
                "priority": "high",
                "owner_area": "quality-gates-and-evidence",
                "quality_gate_changes": [
                    {
                        "task_id": "a",
                        "gate": "artifact_exists",
                        "baseline_passed": True,
                        "current_passed": False,
                        "current_message": "Missing artifacts: outputs/report.md",
                        "current_metadata": {
                            "path": "outputs/report.md",
                            "required_evidence_sources": ["tool_output"],
                        },
                    }
                ],
                "likely_source_modules": ["metis/quality/runner.py", "metis/evidence/ledger.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    markdown = eval_stubs_to_markdown(stubs)
    suite = materialize_eval_suite_from_stubs(stubs)
    suite_markdown = eval_suite_to_markdown(suite)

    stub = stubs["stubs"][0]
    task_spec = stub["eval_task_spec"]
    assert stub["quality_gate_changes"] == repair_tasks["tasks"][0]["quality_gate_changes"]
    assert stub["quality_gate_names"] == ["artifact_exists"]
    assert task_spec["quality_gates"] == ["artifact_exists"]
    assert task_spec["expected_artifacts"] == ["outputs/report.md"]
    assert task_spec["required_evidence_sources"] == ["tool_output"]
    assert "failed_gates=a.artifact_exists" in task_spec["prompt"]
    assert "outputs/report.md" in task_spec["prompt"]
    assert "Quality gates artifact_exists pass" in stub["suggested_assertion"]
    assert "Quality gate changes: a.artifact_exists" in markdown
    task = suite["tasks"][0]
    assert task["quality_gate_changes"] == repair_tasks["tasks"][0]["quality_gate_changes"]
    assert task["task_spec"]["quality_gates"] == ["artifact_exists"]
    assert task["task_spec"]["expected_artifacts"] == ["outputs/report.md"]
    assert task["task_spec"]["required_evidence_sources"] == ["tool_output"]
    assert "Quality gate changes: a.artifact_exists" in suite_markdown


def test_build_eval_stubs_filters_non_portable_artifact_paths_from_gate_metadata():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-path-policy",
                "reason": "quality_gate_failed",
                "priority": "high",
                "owner_area": "quality-gates-and-evidence",
                "quality_gate_changes": [
                    {
                        "task_id": "artifact",
                        "gate": "artifact_exists",
                        "baseline_passed": True,
                        "current_passed": False,
                        "current_message": "Missing artifacts.",
                        "current_metadata": {
                            "expected_artifacts": [
                                "outputs/report.md",
                                "../escape.md",
                                "C:\\tmp\\report.md",
                            ],
                            "requirement_criteria": [
                                {"id": "REQ-bad-path", "required_artifact_path": "/tmp/report.md"},
                                {"id": "REQ-tool", "required_tool": "write_file"},
                            ],
                            "missing_artifact_paths": ["/tmp/report.md", "outputs/summary.md"],
                        },
                    }
                ],
                "likely_source_modules": ["metis/evals/compare.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    markdown = eval_stubs_to_markdown(stubs)
    suite = materialize_eval_suite_from_stubs(stubs)
    suite_markdown = eval_suite_to_markdown(suite)
    task_spec = stubs["stubs"][0]["eval_task_spec"]

    assert task_spec["expected_artifacts"] == ["outputs/report.md"]
    assert task_spec["requirement_criteria"] == [
        {"id": "REQ-tool", "required_tool": "write_file"},
        {"id": "artifact:outputs/summary.md", "required_artifact_path": "outputs/summary.md"},
    ]
    diagnostics = stubs["stubs"][0]["artifact_path_diagnostics"]
    expected_summary = {
        "total": 4,
        "by_reason": {"not_relative": 2, "parent_traversal": 1, "windows_drive_prefix": 1},
        "by_source": {
            "expected_artifacts": 2,
            "missing_artifact_paths": 1,
            "requirement_criteria[0].required_artifact_path": 1,
        },
        "by_gate": {"artifact_exists": 4},
        "by_task": {"artifact": 4},
    }
    assert diagnostics == [
        {
            "task_id": "artifact",
            "gate": "artifact_exists",
            "source": "expected_artifacts",
            "path": "../escape.md",
            "reason": "parent_traversal",
        },
        {
            "task_id": "artifact",
            "gate": "artifact_exists",
            "source": "expected_artifacts",
            "path": "C:\\tmp\\report.md",
            "reason": "windows_drive_prefix",
        },
        {
            "task_id": "artifact",
            "gate": "artifact_exists",
            "source": "missing_artifact_paths",
            "path": "/tmp/report.md",
            "reason": "not_relative",
        },
        {
            "task_id": "artifact",
            "gate": "artifact_exists",
            "source": "requirement_criteria[0].required_artifact_path",
            "path": "/tmp/report.md",
            "reason": "not_relative",
            "criterion_id": "REQ-bad-path",
        },
    ]
    assert stubs["artifact_path_diagnostic_summary"] == expected_summary
    assert "Artifact path diagnostic summary:" in markdown
    assert "total=4" in markdown
    assert "Artifact path diagnostics:" in markdown
    assert "windows_drive_prefix" in markdown
    assert suite["tasks"][0]["task_spec"]["expected_artifacts"] == ["outputs/report.md"]
    assert suite["tasks"][0]["task_spec"]["requirement_criteria"] == task_spec["requirement_criteria"]
    assert suite["tasks"][0]["artifact_path_diagnostics"] == diagnostics
    assert suite["artifact_path_diagnostic_summary"] == expected_summary
    assert "Artifact path diagnostic summary:" in suite_markdown
    assert "Artifact path diagnostics:" in suite_markdown


def test_build_eval_stubs_from_requirements_gate_failure_surfaces_missing_requirements():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-req",
                "reason": "quality_gate_failed",
                "priority": "high",
                "owner_area": "quality-gates-and-evidence",
                "quality_gate_changes": [
                    {
                        "task_id": "coverage",
                        "gate": "requirements_covered",
                        "baseline_passed": True,
                        "current_passed": False,
                        "current_message": "Missing requirement evidence: citations, risk register",
                        "current_metadata": {
                            "requirements": ["citations", "risk register", "summary"],
                            "missing_requirements": ["citations", "risk register"],
                            "requirement_criteria": [
                                {
                                    "id": "REQ-citations",
                                    "text": "citations",
                                    "required_source_type": "artifact",
                                    "min_strength": "medium",
                                }
                            ],
                            "evidence_count": 1,
                            "artifact_count": 1,
                        },
                    }
                ],
                "likely_source_modules": ["metis/quality/runner.py", "metis/evidence/ledger.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    markdown = eval_stubs_to_markdown(stubs)
    suite = materialize_eval_suite_from_stubs(stubs)
    suite_markdown = eval_suite_to_markdown(suite)

    stub = stubs["stubs"][0]
    task_spec = stub["eval_task_spec"]
    assert stub["quality_gate_names"] == ["requirements_covered"]
    assert stub["missing_requirements"] == ["citations", "risk register"]
    assert task_spec["quality_gates"] == ["requirements_covered"]
    assert task_spec["requirements"] == ["citations", "risk register", "summary"]
    assert task_spec["requirement_criteria"] == [
        {
            "id": "REQ-citations",
            "text": "citations",
            "required_source_type": "artifact",
            "min_strength": "medium",
        }
    ]
    assert "Cover these previously missing requirements exactly" in task_spec["prompt"]
    assert '"citations"' in task_spec["prompt"]
    assert '"risk register"' in task_spec["prompt"]
    assert "Missing requirements: citations, risk register" in markdown
    assert suite["tasks"][0]["missing_requirements"] == ["citations", "risk register"]
    assert suite["tasks"][0]["task_spec"]["requirements"] == ["citations", "risk register", "summary"]
    assert suite["tasks"][0]["task_spec"]["requirement_criteria"] == task_spec["requirement_criteria"]
    assert "Missing requirements: citations, risk register" in suite_markdown


def test_build_eval_stubs_from_requirements_gate_failure_surfaces_missing_artifact_and_tool_criteria():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-req-artifact-tool",
                "reason": "quality_gate_failed",
                "priority": "high",
                "owner_area": "quality-gates-and-evidence",
                "quality_gate_changes": [
                    {
                        "task_id": "coverage",
                        "gate": "requirements_covered",
                        "baseline_passed": True,
                        "current_passed": False,
                        "current_message": "Missing artifact and tool evidence.",
                        "current_metadata": {
                            "missing_artifact_paths": ["outputs/report.md"],
                            "missing_tools": ["write_file"],
                        },
                    }
                ],
                "likely_source_modules": ["metis/quality/gates.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    suite = materialize_eval_suite_from_stubs(stubs)

    task_spec = stubs["stubs"][0]["eval_task_spec"]
    assert task_spec["requirement_criteria"] == [
        {"id": "artifact:outputs/report.md", "required_artifact_path": "outputs/report.md"},
        {"id": "tool:write_file", "required_tool": "write_file"},
    ]
    assert suite["tasks"][0]["task_spec"]["requirement_criteria"] == task_spec["requirement_criteria"]


def test_build_eval_stubs_from_schema_repair_hint_events_creates_hint_aware_eval():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-001",
                "reason": "schema_repair_hint_type_failures_increased",
                "priority": "critical",
                "owner_area": "tool-schema-and-repair",
                "cluster_keys": ["schema_repair_hint_failure_type:add_required_property"],
                "critical_event_ids": {"a": "a:002:schema.repair_hint"},
                "schema_repair_hint_events": {
                    "a": [
                        {
                            "event_id": "a:002:schema.repair_hint",
                            "parent_event_id": "a:001:tool.result",
                            "tool_name": "write_file",
                            "tool_call_id": "c1",
                            "schema_errors": ["$.path: missing required property"],
                            "hint_types": ["add_required_property"],
                            "hints": ["Add the required argument $.path."],
                            "hint_details": [
                                {
                                    "hint_type": "add_required_property",
                                    "schema_path": "$.path",
                                    "schema_keyword": "required",
                                },
                                {
                                    "hint_type": "remove_additional_property",
                                    "schema_path": "$.url",
                                    "schema_keyword": "additionalProperties",
                                },
                            ],
                        },
                        {
                            "event_id": "b:002:schema.repair_hint",
                            "parent_event_id": "b:001:tool.result",
                            "tool_name": "run_command",
                            "tool_call_id": "c2",
                            "schema_errors": ["$.command: array length 0 is less than minItems 1"],
                            "hint_types": ["increase_array_items"],
                            "hints": ["Provide enough array items for $.command; do not pass an empty array."],
                            "hint_details": [
                                {
                                    "hint_type": "increase_array_items",
                                    "schema_path": "$.command",
                                    "schema_keyword": "minItems",
                                }
                            ],
                        }
                    ]
                },
                "likely_source_modules": ["metis/tools/schema_validator.py", "metis/runtime/loop.py"],
            }
        ],
    }

    stubs = build_eval_stubs_from_repair_tasks(repair_tasks)
    markdown = eval_stubs_to_markdown(stubs)
    suite = materialize_eval_suite_from_stubs(stubs)

    stub = stubs["stubs"][0]
    task_spec = stub["eval_task_spec"]
    assert stub["schema_repair_hint_types"] == [
        "add_required_property",
        "remove_additional_property",
        "increase_array_items",
    ]
    assert stub["schema_repair_hint_paths"] == ["$.path", "$.url", "$.command"]
    assert stub["schema_repair_hint_keywords"] == ["required", "additionalProperties", "minItems"]
    assert stub["schema_repair_hint_events"] == repair_tasks["tasks"][0]["schema_repair_hint_events"]
    assert stub["schema_repair_argument_templates"] == [
        {
            "hint_type": "add_required_property",
            "schema_path": "$.path",
            "schema_keyword": "required",
            "tool_name": "write_file",
            "malformed_arguments": {},
            "corrected_arguments": {"path": "outputs/metis-placeholder.txt"},
            "notes": "Template placeholders must be replaced by a concrete eval task before running against a real model.",
        },
        {
            "hint_type": "remove_additional_property",
            "schema_path": "$.url",
            "schema_keyword": "additionalProperties",
            "tool_name": "write_file",
            "malformed_arguments": {"url": "<unsupported url>"},
            "corrected_arguments": {},
            "notes": "Template placeholders must be replaced by a concrete eval task before running against a real model.",
        },
        {
            "hint_type": "increase_array_items",
            "schema_path": "$.command",
            "schema_keyword": "minItems",
            "tool_name": "run_command",
            "malformed_arguments": {"command": []},
            "corrected_arguments": {"command": ["metis-placeholder-command_item"]},
            "notes": "Template placeholders must be replaced by a concrete eval task before running against a real model.",
        },
    ]
    assert "types=add_required_property, remove_additional_property, increase_array_items" in task_spec["prompt"]
    assert "paths=$.path, $.url, $.command" in task_spec["prompt"]
    assert "schema repair argument templates as exact failure-shape targets" in task_spec["prompt"]
    assert "showing 3 of 3 templates" in task_spec["prompt"]
    assert '"corrected_arguments":{"path":"outputs/metis-placeholder.txt"}' in task_spec["prompt"]
    assert '"malformed_arguments":{"url":"<unsupported url>"}' in task_spec["prompt"]
    assert '"corrected_arguments":{"command":["metis-placeholder-command_item"]}' in task_spec["prompt"]
    assert task_spec["min_schema_repair_hint_successes"] == 1
    assert task_spec["max_schema_repair_hint_failures"] == 0
    assert "run_command" in task_spec["allowed_tools"]
    assert task_spec["required_tool_arguments"] == [
        {"tool": "write_file", "arguments": {"path": {"contains": "outputs/metis-placeholder.txt"}}},
        {"tool": "run_command", "arguments": {"command": {"contains": "metis-placeholder-command_item"}}},
    ]
    assert (
        "Schema repair hint recovery succeeds for hint types "
        "add_required_property, remove_additional_property, increase_array_items"
    ) in stub["suggested_assertion"]
    assert "Schema repair hint types: add_required_property, remove_additional_property, increase_array_items" in markdown
    assert "Schema repair argument templates: add_required_property@$.path, remove_additional_property@$.url, increase_array_items@$.command" in markdown
    assert suite["tasks"][0]["schema_repair_hint_events"] == repair_tasks["tasks"][0]["schema_repair_hint_events"]
    assert suite["tasks"][0]["schema_repair_hint_types"] == [
        "add_required_property",
        "remove_additional_property",
        "increase_array_items",
    ]
    assert suite["tasks"][0]["schema_repair_argument_templates"] == stub["schema_repair_argument_templates"]
    assert suite["tasks"][0]["task_spec"]["required_tool_arguments"] == task_spec["required_tool_arguments"]


def test_schema_repair_argument_templates_in_prompt_are_sorted_and_capped():
    hint_details = [
        {"hint_type": "remove_additional_property", "schema_path": "$.extra", "schema_keyword": "additionalProperties"},
        {"hint_type": "add_required_property", "schema_path": "$.path", "schema_keyword": "required"},
        {"hint_type": "fix_type", "schema_path": "$.content", "schema_keyword": "type"},
        {"hint_type": "fix_string_pattern", "schema_path": "$.encoding", "schema_keyword": "pattern"},
        {"hint_type": "use_enum_value", "schema_path": "$.mode", "schema_keyword": "enum"},
        {"hint_type": "increase_numeric_value", "schema_path": "$.timeout", "schema_keyword": "minimum"},
        {"hint_type": "reduce_array_items", "schema_path": "$.command", "schema_keyword": "maxItems"},
    ]
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-templates",
                "reason": "schema_repair_hint_type_failures_increased",
                "cluster_keys": ["schema_repair_hint_failure_type:mixed"],
                "schema_repair_hint_events": {
                    "a": [
                        {
                            "event_id": "a:002:schema.repair_hint",
                            "tool_name": "write_file",
                            "hint_details": hint_details,
                        }
                    ]
                },
                "likely_source_modules": ["metis/tools/schema_validator.py"],
            }
        ],
    }

    task_spec = build_eval_stubs_from_repair_tasks(repair_tasks)["stubs"][0]["eval_task_spec"]
    prompt = task_spec["prompt"]

    assert "showing 5 of 7 templates" in prompt
    assert "Omitted 2 lower-priority templates from prompt" in prompt
    assert '"schema_path":"$.content"' in prompt
    assert '"schema_path":"$.path"' in prompt
    assert '"schema_path":"$.extra"' not in prompt
    assert "remove_additional_property@$.extra" in prompt
    assert prompt.index('"schema_path":"$.content"') < prompt.index('"schema_path":"$.path"')


def test_schema_repair_argument_templates_use_custom_tool_schemas():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-custom-tool",
                "reason": "schema_repair_hint_type_failures_increased",
                "cluster_keys": ["schema_repair_hint_failure_type:add_required_property"],
                "tool_schemas": {
                    "crm_update": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "integer", "minimum": 1000},
                            "status": {"type": "string", "enum": ["qualified", "nurture"]},
                        },
                        "required": ["customer_id", "status"],
                    }
                },
                "schema_repair_hint_events": {
                    "a": [
                        {
                            "event_id": "a:002:schema.repair_hint",
                            "tool_name": "crm_update",
                            "hint_details": [
                                {
                                    "hint_type": "add_required_property",
                                    "schema_path": "$.customer_id",
                                    "schema_keyword": "required",
                                },
                                {
                                    "hint_type": "use_enum_value",
                                    "schema_path": "$.status",
                                    "schema_keyword": "enum",
                                },
                            ],
                        }
                    ]
                },
                "likely_source_modules": ["metis/tools/schema_validator.py"],
            }
        ],
    }

    stub = build_eval_stubs_from_repair_tasks(repair_tasks)["stubs"][0]

    assert stub["tool_schemas"] == repair_tasks["tasks"][0]["tool_schemas"]
    assert stub["schema_repair_argument_templates"][0]["corrected_arguments"] == {"customer_id": 1000}
    assert stub["schema_repair_argument_templates"][1]["corrected_arguments"] == {"status": "qualified"}
    assert stub["eval_task_spec"]["required_tool_arguments"] == [
        {"tool": "crm_update", "arguments": {"customer_id": 1000}},
        {"tool": "crm_update", "arguments": {"status": {"contains": "qualified"}}},
    ]
    assert "crm_update" in stub["eval_task_spec"]["allowed_tools"]
    suite = materialize_eval_suite_from_stubs({"profile": "release", "stubs": [stub]})
    assert suite["tasks"][0]["tool_schemas"] == repair_tasks["tasks"][0]["tool_schemas"]


def test_schema_repair_argument_templates_prefer_event_tool_schema_over_task_schema():
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-event-schema",
                "reason": "schema_repair_hint_type_failures_increased",
                "cluster_keys": ["schema_repair_hint_failure_type:add_required_property"],
                "tool_schemas": {
                    "crm_update": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "integer", "minimum": 1000}},
                    }
                },
                "schema_repair_hint_events": {
                    "a": [
                        {
                            "event_id": "a:002:schema.repair_hint",
                            "tool_name": "crm_update",
                            "tool_schema": {
                                "type": "object",
                                "properties": {"customer_id": {"type": "integer", "minimum": 2000}},
                            },
                            "hint_details": [
                                {
                                    "hint_type": "add_required_property",
                                    "schema_path": "$.customer_id",
                                    "schema_keyword": "required",
                                }
                            ],
                        }
                    ]
                },
                "likely_source_modules": ["metis/tools/schema_validator.py"],
            }
        ],
    }

    templates = build_eval_stubs_from_repair_tasks(repair_tasks)["stubs"][0]["schema_repair_argument_templates"]

    assert templates[0]["corrected_arguments"] == {"customer_id": 2000}


def test_materialized_hint_aware_suite_required_arguments_validate_against_schema(tmp_path):
    repair_tasks = {
        "profile": "release",
        "tasks": [
            {
                "id": "repair-001",
                "reason": "schema_repair_hint_type_failures_increased",
                "priority": "critical",
                "owner_area": "tool-schema-and-repair",
                "cluster_keys": ["schema_repair_hint_failure_type:add_required_property"],
                "schema_repair_hint_events": {
                    "a": [
                        {
                            "event_id": "a:002:schema.repair_hint",
                            "tool_name": "write_file",
                            "hint_types": ["add_required_property"],
                            "hint_details": [
                                {
                                    "hint_type": "add_required_property",
                                    "schema_path": "$.path",
                                    "schema_keyword": "required",
                                }
                            ],
                        }
                    ]
                },
                "likely_source_modules": ["metis/tools/schema_validator.py"],
            }
        ],
    }
    suite = materialize_eval_suite_from_stubs(build_eval_stubs_from_repair_tasks(repair_tasks))
    suite_dir = write_materialized_eval_suite(suite, tmp_path / "suite")

    report = validate_eval_suite(
        suite_dir,
        tool_schemas={
            "write_file": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            "read_file": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    )

    assert report["valid"] is True
    assert suite["tasks"][0]["task_spec"]["required_tool_arguments"] == [
        {"tool": "write_file", "arguments": {"path": {"contains": "outputs/metis-placeholder.txt"}}}
    ]


def test_write_eval_stubs_outputs_json_and_markdown(tmp_path):
    stubs = {"profile": "release", "stub_count": 0, "stubs": []}

    output_dir = write_eval_stubs(stubs, tmp_path / "stubs")

    assert (output_dir / "targeted-eval-stubs.json").exists()
    assert (output_dir / "targeted-eval-stubs.md").exists()
    assert (output_dir / "targeted-eval-stubs-attestation.json").exists()
    assert (output_dir / "targeted-eval-stubs-attestation.md").exists()
    attestation = json.loads((output_dir / "targeted-eval-stubs-attestation.json").read_text(encoding="utf-8"))
    subjects = {subject["name"]: subject for subject in attestation["subject"]}
    assert attestation["predicateType"] == "https://metis.local/attestations/repair-eval-artifacts/v1"
    assert attestation["predicate"]["artifact_type"] == "targeted-eval-stubs"
    assert set(subjects) == {"targeted-eval-stubs.json", "targeted-eval-stubs.md"}
    assert verify_targeted_eval_stubs_attestation(output_dir) == []


def test_verify_targeted_eval_stubs_attestation_detects_digest_drift(tmp_path):
    output_dir = write_eval_stubs({"profile": "release", "stub_count": 0, "stubs": []}, tmp_path / "stubs")

    (output_dir / "targeted-eval-stubs.md").write_text("tampered", encoding="utf-8")

    assert (
        "targeted-eval-stubs-attestation.json digest mismatch for targeted-eval-stubs.md"
        in verify_targeted_eval_stubs_attestation(output_dir)
    )


def test_materialize_eval_suite_from_stubs_preserves_repair_metadata():
    stubs = {
        "profile": "release",
        "stubs": [
            {
                "id": "targeted-repair-001",
                "source_repair_task_id": "repair-001",
                "reason": "new_critical_clusters",
                "priority": "critical",
                "owner_area": "tool-schema-and-repair",
                "cluster_keys": ["schema_failure"],
                "critical_event_ids": {"a": "a:001:tool.result"},
                "run_metadata": {
                    "a": {
                        "pre_run_contract_sha256": "contract-sha",
                        "pre_run_provenance_hash": "pre-prov",
                        "provenance_hash": "post-prov",
                        "task_contract_hash": "task-contract",
                    }
                },
                "tool_schemas": {
                    "crm_update": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "integer", "minimum": 1000}},
                    }
                },
                "likely_source_modules": ["metis/tools/schema_validator.py"],
                "suggested_assertion": "Schema repair must recover.",
                "verification_command": "python -m pytest tests/unit/test_tool_schema_validator.py -q",
                "eval_task_spec": {
                    "id": "targeted-repair-001",
                    "prompt": "Recover from schema failure.",
                    "allowed_tools": ["write_file"],
                    "min_schema_repair_successes": 1,
                    "allow_recovered_schema_failures": True,
                },
            }
        ],
    }

    suite = materialize_eval_suite_from_stubs(stubs)
    markdown = eval_suite_to_markdown(suite)

    assert suite["suite"] == "targeted-repair-regression"
    assert suite["schema_version"] == "1"
    assert suite["task_count"] == 1
    assert suite["artifact_path_diagnostic_summary"] == {
        "total": 0,
        "by_reason": {},
        "by_source": {},
        "by_gate": {},
        "by_task": {},
    }
    task = suite["tasks"][0]
    assert task["task_id"] == "targeted-repair-001"
    assert task["source_repair_task_id"] == "repair-001"
    assert task["critical_event_ids"] == {"a": "a:001:tool.result"}
    assert task["run_metadata"] == stubs["stubs"][0]["run_metadata"]
    assert task["tool_schemas"] == stubs["stubs"][0]["tool_schemas"]
    assert task["task_spec"]["min_schema_repair_successes"] == 1
    assert "Metis Materialized Targeted Eval Suite" in markdown
    assert "Schema version: 1" in markdown
    assert "Schema repair must recover." in markdown
    assert "pre_run_contract_sha256=contract-sha" in markdown


def test_materialize_eval_suite_loads_stubs_and_writes_suite(tmp_path):
    stubs_dir = tmp_path / "stubs"
    output_dir = tmp_path / "suite"
    write_eval_stubs(
        {
            "profile": "release",
            "stub_count": 1,
            "stubs": [
                {
                    "id": "targeted-repair-001",
                    "eval_task_spec": {
                        "id": "targeted-repair-001",
                        "prompt": "Recover from tool failure.",
                        "max_tool_repair_failures": 0,
                    },
                }
            ],
        },
        stubs_dir,
    )

    assert load_eval_stubs(stubs_dir)["stub_count"] == 1
    suite = materialize_eval_suite(stubs_dir, output_dir=output_dir)

    assert suite["task_count"] == 1
    assert suite["schema_version"] == "1"
    assert (output_dir / "targeted-eval-suite.json").exists()
    assert (output_dir / "targeted-eval-suite.md").exists()
    assert (output_dir / "targeted-eval-suite-attestation.json").exists()
    assert (output_dir / "targeted-eval-suite-attestation.md").exists()
    assert verify_targeted_eval_suite_attestation(output_dir) == []
    written = json.loads((output_dir / "targeted-eval-suite.json").read_text(encoding="utf-8"))
    assert written["schema_version"] == "1"
    assert written["tasks"][0]["task_spec"]["max_tool_repair_failures"] == 0


def test_write_materialized_eval_suite_outputs_json_and_markdown(tmp_path):
    suite = {"suite": "targeted-repair-regression", "profile": "release", "task_count": 0, "tasks": []}

    output_dir = write_materialized_eval_suite(suite, tmp_path / "suite")

    assert (output_dir / "targeted-eval-suite.json").exists()
    assert (output_dir / "targeted-eval-suite.md").exists()
    attestation = json.loads((output_dir / "targeted-eval-suite-attestation.json").read_text(encoding="utf-8"))
    subjects = {subject["name"]: subject for subject in attestation["subject"]}
    assert attestation["predicateType"] == "https://metis.local/attestations/repair-eval-artifacts/v1"
    assert attestation["predicate"]["artifact_type"] == "targeted-eval-suite"
    assert set(subjects) == {"targeted-eval-suite.json", "targeted-eval-suite.md"}
    assert verify_targeted_eval_suite_attestation(output_dir) == []


def test_verify_targeted_eval_suite_attestation_detects_digest_drift(tmp_path):
    suite = {"suite": "targeted-repair-regression", "profile": "release", "task_count": 0, "tasks": []}
    output_dir = write_materialized_eval_suite(suite, tmp_path / "suite")

    (output_dir / "targeted-eval-suite.json").write_text("tampered", encoding="utf-8")

    assert (
        "targeted-eval-suite-attestation.json digest mismatch for targeted-eval-suite.json"
        in verify_targeted_eval_suite_attestation(output_dir)
    )
