import json
import hashlib

from metis.evals.attestation import write_run_attestation
from metis.evals.provenance import eval_provenance_hash
from metis.evals.gate import eval_gate_to_markdown, evaluate_eval_run_gate, resolve_gate_profile, write_eval_gate_report


def write_run(
    run_dir,
    *,
    success_rate,
    results,
    summary=None,
    schema_evidence=True,
    task_contract_evidence=True,
    provenance_evidence=True,
    provenance_override=None,
    provenance_hash_override=None,
    pre_run_contract=True,
    pre_run_override=None,
):
    manifest = {
        "suite": "real-small-model",
        "run_name": run_dir.name,
        "success_rate": success_rate,
        "task_count": len(results),
    }
    if schema_evidence:
        manifest.update(
            {
                "suite_schema_id": "https://metis.local/schemas/evals/suite-schema-v1.json",
                "suite_schema_sha256": "abc123",
            }
        )
    if task_contract_evidence:
        manifest.update(
            {
                "task_contract_hash": "contract123",
                "task_spec_hash_summary": {
                    str(result.get("task_id", "task")): {
                        "prompt_hash": "prompt123",
                        "constraints_hash": "constraints123",
                        "task_spec_hash": "spec123",
                    }
                    for result in results
                },
            }
        )
    if provenance_evidence:
        provenance = provenance_override or {
            "suite": "real-small-model",
            "suite_definition_type": "code-defined-builtin",
            "schema_version": "code-defined",
            "suite_schema_sha256": manifest.get("suite_schema_sha256", "abc123"),
            "task_contract_hash": manifest.get("task_contract_hash", "contract123"),
            "model": "glm-4.7-flash",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "profile": "small",
            "tool_inventory_hash": "toolhash123",
        }
        manifest["provenance"] = provenance
        manifest["provenance_hash"] = (
            provenance_hash_override if provenance_hash_override is not None else eval_provenance_hash(provenance)
        )
    run_dir.mkdir(parents=True)
    if pre_run_contract:
        pre_run = pre_run_override or {
            "artifact_type": "test-pre-run-contract",
            "suite": manifest.get("suite", ""),
            "run_name": manifest.get("run_name", ""),
            "task_contract_hash": manifest.get("task_contract_hash", ""),
            "task_spec_hash_summary": manifest.get("task_spec_hash_summary", {}),
            "provenance": manifest.get("provenance", {}),
            "provenance_hash": manifest.get("provenance_hash", ""),
        }
        pre_run_path = run_dir / "pre-run-contract.json"
        pre_run_path.write_text(json.dumps(pre_run), encoding="utf-8")
        manifest["pre_run_contract_path"] = str(pre_run_path)
        manifest["pre_run_contract_sha256"] = hashlib.sha256(pre_run_path.read_bytes()).hexdigest()
        manifest["pre_run_provenance_hash"] = pre_run.get("provenance_hash", "")
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "eval-report.json").write_text(
        json.dumps({"success_rate": success_rate, "summary": summary or {}, "metadata": {}, "results": results}),
        encoding="utf-8",
    )
    task_spec_hash_summary = manifest.get("task_spec_hash_summary", {})
    (run_dir / "task-specs.json").write_text(
        json.dumps(
            {
                "task_count": len(results),
                "task_contract_hash": manifest.get("task_contract_hash", ""),
                "task_spec_hash_summary": task_spec_hash_summary,
                "tasks": [
                    {
                        "task_id": str(result.get("task_id", "task")),
                        "task_spec": {"id": str(result.get("task_id", "task"))},
                        "task_spec_hashes": task_spec_hash_summary.get(str(result.get("task_id", "task")), {}),
                    }
                    for result in results
                ],
            }
        ),
        encoding="utf-8",
    )
    write_run_attestation(run_dir, manifest=manifest)


def write_failure_cluster_files(run_dir, *, clusters, backlog_items):
    failures_dir = run_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    (failures_dir / "clusters.json").write_text(
        json.dumps({"failure_count": len(backlog_items), "cluster_count": len(clusters), "clusters": clusters}),
        encoding="utf-8",
    )
    (failures_dir / "remediation-backlog.json").write_text(
        json.dumps(
            {
                "failure_count": len(backlog_items),
                "cluster_count": len(clusters),
                "item_count": len(backlog_items),
                "items": backlog_items,
            }
        ),
        encoding="utf-8",
    )


def test_eval_gate_fails_on_default_strict_thresholds(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=0.5,
        results=[
            {
                "task_id": "a",
                "success": False,
                "invalid_tool_calls": 1,
                "schema_violations": 2,
                "retry_budget_exhaustions": 1,
                "pre_dispatch_blocks": 1,
                "trajectory_failures": 1,
            },
            {"task_id": "b", "success": True},
        ],
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert gate["failed_tasks"] == ["a"]
    assert gate["aggregates"]["failed_tasks"] == 1
    assert gate["aggregates"]["invalid_tool_calls"] == 1
    assert gate["aggregates"]["schema_violations"] == 2
    assert "success_rate 0.5000 < 1.0000" in gate["failures"]
    assert "schema_violations 2 > 0" in gate["failures"]
    assert gate["aggregates"]["failure_clusters"] == 0
    assert gate["aggregates"]["critical_remediations"] == 0
    assert gate["run"]["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert gate["run"]["task_contract_hash"] == "contract123"
    assert gate["run"]["provenance_hash"]
    assert gate["run"]["pre_run_provenance_hash"]


def test_eval_gate_profiles_define_release_strictness():
    dev = resolve_gate_profile("dev")
    release = resolve_gate_profile("release")

    assert dev["min_success_rate"] < release["min_success_rate"]
    assert dev["require_provenance_evidence"] is False
    assert release["require_provenance_evidence"] is True


def test_eval_gate_dev_profile_allows_legacy_partial_run(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=0.8,
        results=[{"task_id": "a", "success": False}, {"task_id": "b", "success": True}],
        schema_evidence=False,
        task_contract_evidence=False,
        provenance_evidence=False,
        pre_run_contract=False,
    )
    (run_dir / "run-attestation.json").unlink()

    gate = evaluate_eval_run_gate(run_dir, profile="dev")

    assert gate["passed"] is True
    assert gate["profile"] == "dev"
    assert gate["require_provenance_evidence"] is False


def test_eval_gate_passes_when_thresholds_allow_observed_metrics(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=0.5,
        results=[
            {"task_id": "a", "success": False, "invalid_tool_calls": 1, "schema_violations": 2},
            {"task_id": "b", "success": True},
        ],
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        min_success_rate=0.5,
        max_failed_tasks=1,
        max_invalid_tool_calls=1,
        max_schema_violations=2,
    )
    markdown = eval_gate_to_markdown(gate)

    assert gate["passed"] is True
    assert gate["failures"] == []
    assert "Passed: True" in markdown
    assert "Suite schema sha256: abc123" in markdown
    assert "Task contract hash: contract123" in markdown
    assert "Provenance hash:" in markdown
    assert "Pre-run provenance hash:" in markdown
    assert "- None" in markdown


def test_eval_gate_fails_when_suite_schema_evidence_is_missing(tmp_path):
    run_dir = tmp_path / "run"
    write_run(run_dir, success_rate=1.0, results=[{"task_id": "a", "success": True}], schema_evidence=False)

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "suite_schema_id missing from manifest" in gate["failures"]
    assert "suite_schema_sha256 missing from manifest" in gate["failures"]


def test_eval_gate_can_disable_suite_schema_evidence_requirement_for_legacy_runs(tmp_path):
    run_dir = tmp_path / "run"
    write_run(run_dir, success_rate=1.0, results=[{"task_id": "a", "success": True}], schema_evidence=False)

    gate = evaluate_eval_run_gate(run_dir, require_suite_schema_evidence=False)

    assert gate["passed"] is True


def test_eval_gate_fails_when_task_contract_evidence_is_missing(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        task_contract_evidence=False,
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "task_contract_hash missing from manifest" in gate["failures"]
    assert "task_spec_hash_summary missing from manifest" in gate["failures"]


def test_eval_gate_can_disable_task_contract_evidence_requirement_for_legacy_runs(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        task_contract_evidence=False,
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        require_task_contract_evidence=False,
        require_pre_run_contract_evidence=False,
    )

    assert gate["passed"] is True


def test_eval_gate_fails_when_provenance_evidence_is_missing(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        provenance_evidence=False,
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "provenance missing from manifest" in gate["failures"]


def test_eval_gate_fails_when_provenance_hash_mismatches_payload(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        provenance_hash_override="bad-hash",
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "provenance_hash does not match provenance payload" in gate["failures"]


def test_eval_gate_fails_when_provenance_payload_is_incomplete(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        provenance_override={
            "suite": "real-small-model",
            "suite_schema_sha256": "abc123",
            "task_contract_hash": "contract123",
        },
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "provenance.model missing from manifest" in gate["failures"]
    assert "provenance.tool_inventory_hash missing from manifest" in gate["failures"]


def test_eval_gate_can_disable_provenance_evidence_requirement_for_legacy_runs(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        provenance_evidence=False,
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        require_provenance_evidence=False,
        require_pre_run_contract_evidence=False,
    )

    assert gate["passed"] is True


def test_eval_gate_fails_when_pre_run_contract_is_missing(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        pre_run_contract=False,
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "pre-run-contract.json missing from run directory" in gate["failures"]


def test_eval_gate_fails_when_pre_run_contract_mismatches_manifest(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        pre_run_override={
            "artifact_type": "test-pre-run-contract",
            "task_contract_hash": "other-contract",
            "task_spec_hash_summary": {},
            "provenance": {
                "suite": "real-small-model",
                "suite_schema_sha256": "abc123",
                "task_contract_hash": "other-contract",
                "model": "glm-4.7-flash",
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "profile": "small",
                "tool_inventory_hash": "toolhash123",
            },
            "provenance_hash": "other-hash",
        },
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "pre-run provenance_hash does not match pre-run provenance payload" in gate["failures"]
    assert "pre-run provenance_hash does not match manifest provenance_hash" in gate["failures"]
    assert "pre-run task_contract_hash does not match manifest task_contract_hash" in gate["failures"]
    assert "pre-run task_spec_hash_summary does not match manifest task_spec_hash_summary" in gate["failures"]


def test_eval_gate_can_disable_pre_run_contract_requirement_for_legacy_runs(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[{"task_id": "a", "success": True}],
        pre_run_contract=False,
    )

    gate = evaluate_eval_run_gate(run_dir, require_pre_run_contract_evidence=False)

    assert gate["passed"] is True


def test_eval_gate_fails_when_run_attestation_is_missing(tmp_path):
    run_dir = tmp_path / "run"
    write_run(run_dir, success_rate=1.0, results=[{"task_id": "a", "success": True}])
    (run_dir / "run-attestation.json").unlink()

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "run-attestation.json missing from run directory" in gate["failures"]


def test_eval_gate_fails_when_run_attestation_digest_mismatches_file(tmp_path):
    run_dir = tmp_path / "run"
    write_run(run_dir, success_rate=1.0, results=[{"task_id": "a", "success": True}])
    (run_dir / "eval-report.json").write_text(
        json.dumps(
            {
                "success_rate": 1.0,
                "summary": {},
                "metadata": {},
                "results": [{"task_id": "a", "success": True}],
                "tampered": True,
            }
        ),
        encoding="utf-8",
    )

    gate = evaluate_eval_run_gate(run_dir)

    assert gate["passed"] is False
    assert "run-attestation digest mismatch for eval-report.json" in gate["failures"]


def test_eval_gate_can_disable_run_attestation_requirement_for_legacy_runs(tmp_path):
    run_dir = tmp_path / "run"
    write_run(run_dir, success_rate=1.0, results=[{"task_id": "a", "success": True}])
    (run_dir / "run-attestation.json").unlink()

    gate = evaluate_eval_run_gate(run_dir, require_run_attestation_evidence=False)

    assert gate["passed"] is True


def test_eval_gate_fails_on_schema_repair_hint_summary_thresholds(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[],
        summary={
            "schema_repair_hints_seen": 4,
            "schema_repair_hint_successes": 3,
            "schema_repair_hint_failures": 1,
            "schema_repair_hint_recovery_rate": 0.75,
        },
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        min_schema_repair_hint_recovery_rate=0.9,
        max_schema_repair_hint_failures=0,
    )

    assert gate["passed"] is False
    assert gate["aggregates"]["schema_repair_hints_seen"] == 4
    assert gate["aggregates"]["schema_repair_hint_successes"] == 3
    assert gate["aggregates"]["schema_repair_hint_failures"] == 1
    assert gate["aggregates"]["schema_repair_hint_recovery_rate"] == 0.75
    assert "schema_repair_hint_recovery_rate 0.7500 < 0.9000" in gate["failures"]
    assert "schema_repair_hint_failures 1 > 0" in gate["failures"]


def test_eval_gate_can_fallback_to_result_level_schema_repair_hint_metrics(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=1.0,
        results=[
            {"task_id": "a", "success": True, "schema_repair_hints_seen": 1, "schema_repair_hint_successes": 1},
            {
                "task_id": "b",
                "success": True,
                "schema_repair_hints_seen": 1,
                "schema_repair_hint_successes": 0,
                "schema_repair_hint_failures": 1,
            },
        ],
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        min_schema_repair_hint_recovery_rate=0.5,
        max_schema_repair_hint_failures=1,
    )

    assert gate["passed"] is True
    assert gate["aggregates"]["schema_repair_hint_recovery_rate"] == 0.5
    assert gate["aggregates"]["schema_repair_hint_failures"] == 1


def test_eval_gate_fails_on_critical_failure_clusters_even_when_task_thresholds_are_relaxed(tmp_path):
    run_dir = tmp_path / "run"
    write_run(
        run_dir,
        success_rate=0.5,
        results=[{"task_id": "a", "success": False, "schema_violations": 0}],
    )
    write_failure_cluster_files(
        run_dir,
        clusters=[{"cluster_key": "schema_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "schema_failure", "severity": "critical"}],
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        min_success_rate=0.5,
        max_failed_tasks=1,
        max_failure_clusters=0,
        max_critical_remediations=0,
    )

    assert gate["passed"] is False
    assert gate["aggregates"]["failure_clusters"] == 1
    assert gate["aggregates"]["critical_remediations"] == 1
    assert gate["cluster_summary"]["critical_cluster_keys"] == ["schema_failure"]
    assert "failure_clusters 1 > 0" in gate["failures"]
    assert "critical_remediations 1 > 0" in gate["failures"]


def test_eval_gate_passes_cluster_thresholds_when_explicitly_allowed(tmp_path):
    run_dir = tmp_path / "run"
    write_run(run_dir, success_rate=0.5, results=[{"task_id": "a", "success": False}])
    write_failure_cluster_files(
        run_dir,
        clusters=[{"cluster_key": "trajectory_failure", "count": 1, "task_ids": ["a"]}],
        backlog_items=[{"cluster_key": "trajectory_failure", "severity": "high"}],
    )

    gate = evaluate_eval_run_gate(
        run_dir,
        min_success_rate=0.5,
        max_failed_tasks=1,
        max_failure_clusters=1,
        max_critical_remediations=0,
    )

    assert gate["passed"] is True
    assert gate["cluster_summary"]["cluster_keys"] == ["trajectory_failure"]


def test_write_eval_gate_report_outputs_json_and_markdown(tmp_path):
    gate = {
        "run": {"run_name": "run", "run_dir": "run", "success_rate": 1.0},
        "passed": True,
        "thresholds": {},
        "aggregates": {},
        "failed_tasks": [],
        "failures": [],
    }

    output_dir = write_eval_gate_report(gate, tmp_path / "gate")

    assert (output_dir / "gate.json").exists()
    assert (output_dir / "gate.md").exists()
