import json

import pytest

from metis.evidence.ledger import EvidenceLedger
from metis.evals.attestation import write_run_attestation
from metis.evals.runner import (
    EvalResult,
    EvalRunner,
    EvalSuiteResult,
    EvalTaskSpec,
    eval_task_spec_from_dict,
    eval_task_specs_from_suite_payload,
    load_eval_task_specs,
    load_versioned_eval_suite_payload,
)
from metis.providers.fake import FakeProvider
from metis.runtime.loop import AgentLoop
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


def test_eval_task_spec_from_dict_ignores_unknown_fields():
    task = eval_task_spec_from_dict(
        {
            "id": "targeted-repair-001",
            "prompt": "Recover from schema failure.",
            "allowed_tools": ["write_file"],
            "max_turns": 4,
            "min_schema_repair_successes": 1,
            "unknown_future_field": "kept-out",
        }
    )

    assert task.id == "targeted-repair-001"
    assert task.prompt == "Recover from schema failure."
    assert task.allowed_tools == ["write_file"]
    assert task.max_turns == 4
    assert task.min_schema_repair_successes == 1
    assert not hasattr(task, "unknown_future_field")


def test_eval_task_specs_from_suite_payload_accepts_materialized_task_spec_wrappers():
    specs = eval_task_specs_from_suite_payload(
        {
            "suite": "targeted-repair-regression",
            "tasks": [
                {
                    "task_id": "targeted-repair-001",
                    "task_spec": {
                        "id": "targeted-repair-001",
                        "prompt": "Fix schema repair.",
                        "max_schema_repair_failures": 0,
                    },
                }
            ],
        }
    )

    assert len(specs) == 1
    assert specs[0].id == "targeted-repair-001"
    assert specs[0].max_schema_repair_failures == 0


def test_eval_task_specs_from_suite_payload_enriches_artifact_verification_target_dirs():
    specs = eval_task_specs_from_suite_payload(
        {
            "suite": "targeted-repair-regression",
            "schema_version": "1",
            "baseline": {"run_dir": "runs/baseline"},
            "current": {"run_dir": "runs/current"},
            "tasks": [
                {
                    "task_spec": {
                        "id": "artifact-verification-repair-001",
                        "prompt": "Verify artifacts.",
                        "fixture_type": "artifact_verification",
                        "requires_model_execution": False,
                        "artifact_verification": {"target_runs": ["current"]},
                    }
                }
            ],
        }
    )

    assert specs[0].requires_model_execution is False
    assert specs[0].fixture_type == "artifact_verification"
    assert specs[0].artifact_verification["target_run_dirs"] == {"current": "runs/current"}


def test_load_eval_task_specs_reads_targeted_suite_directory(tmp_path):
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "targeted-eval-suite.json").write_text(
        json.dumps(
            {
                "suite": "targeted-repair-regression",
                "schema_version": "1",
                "tasks": [
                    {
                        "task_spec": {
                            "id": "targeted-repair-002",
                            "prompt": "Recover from retry budget exhaustion.",
                            "max_retry_budget_exhaustions": 0,
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    specs = load_eval_task_specs(suite_dir)

    assert [spec.id for spec in specs] == ["targeted-repair-002"]
    assert specs[0].max_retry_budget_exhaustions == 0


def test_load_versioned_eval_suite_payload_rejects_unsupported_schema_version(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "future-suite",
                "schema_version": "2",
                "tasks": [{"id": "future", "prompt": "Run."}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported eval suite schema_version: 2"):
        load_versioned_eval_suite_payload(suite_path)


@pytest.mark.asyncio
async def test_eval_runner_records_successful_task_metrics():
    final = json.dumps(
        {"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    loop = AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(EvalTaskSpec(id="smoke", prompt="finish", max_turns=1))

    assert result.success is True
    assert result.status == "final"
    assert result.final_verified is False
    assert result.final_unverified is True
    assert result.turns_used == 1
    assert result.tool_calls == 0
    assert result.duplicate_tool_calls == 0
    assert result.invalid_tool_calls == 0


@pytest.mark.asyncio
async def test_eval_runner_executes_artifact_verification_fixture_without_provider(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {"suite": "unit", "run_name": "run", "task_count": 0}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "eval-report.json").write_text(
        json.dumps({"success_rate": 1.0, "summary": {}, "metadata": {}, "results": []}),
        encoding="utf-8",
    )
    (run_dir / "task-specs.json").write_text(
        json.dumps({"task_count": 0, "task_contract_hash": "", "task_spec_hash_summary": {}, "tasks": []}),
        encoding="utf-8",
    )
    write_run_attestation(run_dir, manifest=manifest)
    provider = FakeProvider([{"content": "should not be consumed"}])
    runner = EvalRunner(loop=AgentLoop(provider=provider, registry=ToolRegistry(), profile="small"))

    result = await runner.run_task(
        EvalTaskSpec(
            id="artifact-verification",
            prompt="Verify artifacts.",
            fixture_type="artifact_verification",
            requires_model_execution=False,
            artifact_verification={"target_run_dirs": {"current": str(run_dir)}},
            quality_gates=["run_attestation_verifies"],
        )
    )

    assert result.success is True
    assert result.status == "verified"
    assert result.turns_used == 0
    assert result.tool_calls == 0
    assert result.quality_failures == 0
    assert result.quality_gate_results == [
        {
            "name": "run_attestation_verifies",
            "passed": True,
            "message": "Run attestation verifies for all target run directories",
            "metadata": {"target_run_dirs": {"current": str(run_dir)}},
        }
    ]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_eval_runner_artifact_verification_fixture_fails_on_tampered_run(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {"suite": "unit", "run_name": "run", "task_count": 0}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "eval-report.json").write_text(
        json.dumps({"success_rate": 1.0, "summary": {}, "metadata": {}, "results": []}),
        encoding="utf-8",
    )
    (run_dir / "task-specs.json").write_text(
        json.dumps({"task_count": 0, "task_contract_hash": "", "task_spec_hash_summary": {}, "tasks": []}),
        encoding="utf-8",
    )
    write_run_attestation(run_dir, manifest=manifest)
    (run_dir / "eval-report.json").write_text(
        json.dumps({"success_rate": 0.0, "summary": {}, "metadata": {}, "results": [], "tampered": True}),
        encoding="utf-8",
    )
    provider = FakeProvider([{"content": "should not be consumed"}])
    runner = EvalRunner(loop=AgentLoop(provider=provider, registry=ToolRegistry(), profile="small"))

    result = await runner.run_task(
        EvalTaskSpec(
            id="artifact-verification",
            prompt="Verify artifacts.",
            fixture_type="artifact_verification",
            requires_model_execution=False,
            artifact_verification={"target_run_dirs": {"current": str(run_dir)}},
        )
    )

    assert result.success is False
    assert result.status == "failed"
    assert result.quality_failures >= 1
    assert result.quality_gate_results[0]["name"] == "run_attestation_verifies"
    assert result.quality_gate_results[0]["passed"] is False
    assert "current: run-attestation digest mismatch for eval-report.json" in result.quality_gate_results[0]["message"]
    assert "current: run-attestation digest mismatch for eval-report.json" in result.errors[0]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_eval_runner_can_require_verified_final(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("eval-verified")
    state.record_tool_call(
        session_id,
        "run_test",
        {"command": ["python", "-m", "pytest", "-q"]},
        result='{"command":["python","-m","pytest","-q"],"exit_code":0,"stdout":"1 passed"}',
        status="ok",
        call_id="t1",
    )
    ledger = EvidenceLedger(state)
    ledger.record_claim(
        session_id=session_id,
        claim="Test command executed",
        source_type="test",
        source_ref="python -m pytest -q",
        metadata={"exit_code": 0, "status": "ok"},
        evidence_id="e1",
    )
    final = json.dumps(
        {
            "status": "done",
            "summary": "All tests passed.",
            "evidence_refs": ["e1"],
            "artifact_refs": [],
            "next_action": "",
        }
    )
    loop = AgentLoop(
        provider=FakeProvider([{"content": final}]),
        registry=ToolRegistry(),
        profile="small_strict",
        state=state,
        evidence_ledger=ledger,
    )
    runner = EvalRunner(loop=loop, evidence_ledger=ledger)

    result = await runner.run_task(
        EvalTaskSpec(id="verified", prompt="finish", max_turns=1, require_verified_final=True),
        session_id=session_id,
    )

    assert result.success is True
    assert result.final_verified is True
    assert result.final_unverified is False


@pytest.mark.asyncio
async def test_eval_runner_fails_unverified_final_when_required():
    final = json.dumps(
        {"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    loop = AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(EvalTaskSpec(id="unverified", prompt="finish", max_turns=1, require_verified_final=True))

    assert result.success is False
    assert result.final_verified is False
    assert result.final_unverified is True


@pytest.mark.asyncio
async def test_eval_suite_writes_reports(tmp_path):
    final = json.dumps(
        {"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    runner = EvalRunner(loop=AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small"))

    suite = await runner.run_suite([EvalTaskSpec(id="smoke", prompt="finish", max_turns=1)])
    suite.write_reports(tmp_path)

    report_md = (tmp_path / "eval-report.md").read_text(encoding="utf-8")
    assert "Success rate" in report_md
    assert "## Summary" in report_md
    assert "## Quality Gate Results" in report_md
    assert "Retry Budget Exhaustions" in report_md
    assert "Pre-dispatch Blocks" in report_md
    assert "## Failure Details" in report_md
    assert "- None" in report_md
    failures_index = json.loads((tmp_path / "failures" / "index.json").read_text(encoding="utf-8"))
    assert failures_index == {"failure_count": 0, "artifacts": []}
    failure_clusters = json.loads((tmp_path / "failures" / "clusters.json").read_text(encoding="utf-8"))
    assert failure_clusters == {"failure_count": 0, "cluster_count": 0, "clusters": []}
    remediation_backlog = json.loads((tmp_path / "failures" / "remediation-backlog.json").read_text(encoding="utf-8"))
    assert remediation_backlog == {"failure_count": 0, "cluster_count": 0, "item_count": 0, "items": []}
    report_json = json.loads((tmp_path / "eval-report.json").read_text(encoding="utf-8"))
    assert report_json["success_rate"] == 1.0
    assert report_json["results"][0]["quality_gate_results"] == []
    assert report_json["summary"]["schema_repair_hint_recovery_rate"] == 0.0
    task_specs = json.loads((tmp_path / "task-specs.json").read_text(encoding="utf-8"))
    assert task_specs["task_count"] == 1
    assert len(task_specs["task_contract_hash"]) == 64
    assert task_specs["task_spec_hash_summary"]["smoke"] == task_specs["tasks"][0]["task_spec_hashes"]
    assert task_specs["tasks"][0]["task_id"] == "smoke"
    assert set(task_specs["tasks"][0]["task_spec_hashes"]) == {"prompt_hash", "constraints_hash", "task_spec_hash"}


def test_eval_suite_markdown_includes_failure_only_details():
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="passing",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            ),
            EvalResult(
                task_id="failing",
                success=False,
                status="blocked",
                turns_used=3,
                tool_calls=2,
                latency_seconds=0.02,
                invalid_tool_calls=1,
                schema_violations=2,
                retry_budget_exhaustions=1,
                pre_dispatch_blocks=1,
                trajectory_failures=1,
                tool_failure_types={"schema_validation_failed": 1},
                failure_shape_keys={"write_file schema_validation_failed": 1},
                errors=["Schema violations exceeded: 2 > 0"],
            ),
        ],
        metadata={"suite": "unit"},
    )

    markdown = suite.to_markdown()

    assert "## Failure Details" in markdown
    assert "### failing" in markdown
    assert "### passing" not in markdown
    assert "- Status: blocked" in markdown
    assert "- Tool failure types: schema_validation_failed=1" in markdown
    assert "- Failure shape keys: write_file schema_validation_failed=1" in markdown
    assert "  - Schema violations exceeded: 2 > 0" in markdown


def test_eval_suite_summary_aggregates_schema_repair_hint_metrics():
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="hint-ok",
                success=True,
                status="final",
                turns_used=3,
                tool_calls=2,
                latency_seconds=0.01,
                schema_repair_hints_seen=1,
                schema_repair_hint_successes=1,
                schema_repair_hint_failures=0,
                schema_repair_hint_types_seen={"remove_additional_property": 1},
                schema_repair_hint_type_successes={"remove_additional_property": 1},
                schema_repair_hint_type_failures={"remove_additional_property": 0},
            ),
            EvalResult(
                task_id="hint-bad",
                success=False,
                status="final",
                turns_used=2,
                tool_calls=1,
                latency_seconds=0.01,
                schema_repair_hints_seen=1,
                schema_repair_hint_successes=0,
                schema_repair_hint_failures=1,
                schema_repair_hint_types_seen={"add_required_property": 1},
                schema_repair_hint_type_successes={},
                schema_repair_hint_type_failures={"add_required_property": 1},
            ),
        ]
    )

    summary = suite.summary
    markdown = suite.to_markdown()
    payload = json.loads(suite.to_json())

    assert summary["schema_repair_hints_seen"] == 2
    assert summary["schema_repair_hint_successes"] == 1
    assert summary["schema_repair_hint_failures"] == 1
    assert summary["schema_repair_hint_recovery_rate"] == 0.5
    assert summary["schema_repair_hint_types_seen"] == {
        "add_required_property": 1,
        "remove_additional_property": 1,
    }
    assert summary["schema_repair_hint_type_successes"] == {"remove_additional_property": 1}
    assert summary["schema_repair_hint_type_failures"] == {"add_required_property": 1}
    assert "Schema repair hint recovery rate: 50.00%" in markdown
    assert "Schema repair hint type failures: add_required_property=1" in markdown
    assert payload["summary"]["schema_repair_hint_recovery_rate"] == 0.5


def test_eval_suite_writes_failure_artifacts(tmp_path):
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="pass",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            ),
            EvalResult(
                task_id="bad/task id",
                success=False,
                status="blocked",
                turns_used=3,
                tool_calls=2,
                latency_seconds=0.02,
                invalid_tool_calls=1,
                schema_violations=2,
                retry_budget_exhaustions=1,
                pre_dispatch_blocks=1,
                trajectory_failures=1,
                tool_failure_types={"schema_validation_failed": 1},
                failure_shape_keys={"write_file schema_validation_failed": 1},
                errors=["Schema violations exceeded: 2 > 0"],
            ),
        ]
    )

    suite.write_reports(tmp_path)

    failures_dir = tmp_path / "failures"
    index = json.loads((failures_dir / "index.json").read_text(encoding="utf-8"))
    artifact = json.loads((failures_dir / "bad-task-id.json").read_text(encoding="utf-8"))
    timeline = json.loads((failures_dir / "bad-task-id.timeline.json").read_text(encoding="utf-8"))
    timeline_md = (failures_dir / "bad-task-id.timeline.md").read_text(encoding="utf-8")
    clusters = json.loads((failures_dir / "clusters.json").read_text(encoding="utf-8"))
    assert index["failure_count"] == 1
    assert index["artifacts"][0]["task_id"] == "bad/task id"
    assert index["artifacts"][0]["errors"] == 1
    assert index["artifacts"][0]["timeline_path"].endswith("bad-task-id.timeline.json")
    assert index["artifacts"][0]["timeline_markdown_path"].endswith("bad-task-id.timeline.md")
    assert artifact["task_id"] == "bad/task id"
    assert artifact["timeline_path"].endswith("bad-task-id.timeline.json")
    assert artifact["metrics"]["schema_violations"] == 2
    assert artifact["metrics"]["retry_budget_exhaustions"] == 1
    assert artifact["tool_failure_types"] == {"schema_validation_failed": 1}
    assert artifact["failure_shape_keys"] == {"write_file schema_validation_failed": 1}
    assert artifact["errors"] == ["Schema violations exceeded: 2 > 0"]
    assert timeline["task_id"] == "bad/task id"
    assert timeline["events"][0]["event_type"] == "task.start"
    assert timeline["events"][0]["event_id"] == "bad/task id:000:task.start"
    assert timeline["events"][-1]["event_type"] == "task.end"
    assert timeline["events"][-1]["event_id"].endswith(":task.end")
    assert "Metis Failure Timeline" in timeline_md
    assert any(cluster["cluster_key"] == "schema_failure" for cluster in clusters["clusters"])
    assert (failures_dir / "clusters.md").exists()
    backlog = json.loads((failures_dir / "remediation-backlog.json").read_text(encoding="utf-8"))
    assert any(item["cluster_key"] == "schema_failure" for item in backlog["items"])
    assert (failures_dir / "remediation-backlog.md").exists()


@pytest.mark.asyncio
async def test_eval_suite_failure_artifacts_include_task_spec_metadata(tmp_path):
    final = json.dumps(
        {"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    runner = EvalRunner(loop=AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small"))
    task = EvalTaskSpec(
        id="spec-failure",
        prompt="Read README.md, then write a verified summary.",
        allowed_tools=["read_file", "write_file"],
        max_turns=2,
        expected_artifacts=["outputs/summary.md"],
        required_evidence_sources=["tool_output"],
        quality_gates=["markdown_report"],
        require_verified_final=True,
        required_tools=["read_file", "write_file"],
        forbidden_tools=["run_shell"],
        required_tool_order=["read_file", "write_file"],
        required_tool_arguments=[{"tool": "read_file", "arguments": {"path": "README.md"}}],
        max_invalid_tool_calls=0,
        max_schema_violations=0,
        max_retry_budget_exhaustions=0,
        max_pre_dispatch_blocks=0,
    )

    suite = await runner.run_suite([task])
    suite = EvalSuiteResult(suite.results, {"suite": "unit", "model": "fake-9b", "profile": "small"}, suite.task_specs)
    suite.write_reports(tmp_path)

    index = json.loads((tmp_path / "failures" / "index.json").read_text(encoding="utf-8"))
    artifact = json.loads((tmp_path / "failures" / "spec-failure.json").read_text(encoding="utf-8"))
    timeline = json.loads((tmp_path / "failures" / "spec-failure.timeline.json").read_text(encoding="utf-8"))
    timeline_md = (tmp_path / "failures" / "spec-failure.timeline.md").read_text(encoding="utf-8")
    report = json.loads((tmp_path / "eval-report.json").read_text(encoding="utf-8"))
    report_md = (tmp_path / "eval-report.md").read_text(encoding="utf-8")
    task_spec = artifact["task_spec"]
    assert index["artifacts"][0]["has_task_spec"] is True
    assert report["results"][0]["quality_gate_results"] == [
        {
            "name": "markdown_report",
            "passed": False,
            "message": "Unknown quality gate: markdown_report",
            "metadata": {},
        }
    ]
    assert "markdown_report: passed=False; message=Unknown quality gate: markdown_report" in report_md
    assert artifact["quality_gate_results"] == report["results"][0]["quality_gate_results"]
    gate_events = [event for event in timeline["events"] if event["event_type"] == "quality.gate"]
    assert gate_events == [
        {
            "index": gate_events[0]["index"],
            "event_id": gate_events[0]["event_id"],
            "event_type": "quality.gate",
            "task_id": "spec-failure",
            "status": "failed",
            "gate_name": "markdown_report",
            "message": "Unknown quality gate: markdown_report",
            "metadata": {},
        }
    ]
    assert "quality.gate" in timeline_md
    assert "Unknown quality gate: markdown_report" in timeline_md
    assert task_spec["id"] == "spec-failure"
    assert task_spec["prompt"] == "Read README.md, then write a verified summary."
    assert task_spec["allowed_tools"] == ["read_file", "write_file"]
    assert task_spec["required_tools"] == ["read_file", "write_file"]
    assert task_spec["forbidden_tools"] == ["run_shell"]
    assert task_spec["required_evidence_sources"] == ["tool_output"]
    assert task_spec["quality_gates"] == ["markdown_report"]
    assert task_spec["required_tool_arguments"] == [{"tool": "read_file", "arguments": {"path": "README.md"}}]
    assert task_spec["max_invalid_tool_calls"] == 0
    assert task_spec["max_schema_violations"] == 0
    assert set(artifact["task_spec_hashes"]) == {"prompt_hash", "constraints_hash", "task_spec_hash"}
    assert len(artifact["task_spec_hashes"]["task_spec_hash"]) == 64
    assert artifact["run_metadata"] == {"suite": "unit", "model": "fake-9b", "profile": "small"}


@pytest.mark.asyncio
async def test_eval_runner_passes_task_requirements_to_quality_gates(tmp_path):
    final = json.dumps(
        {"status": "done", "summary": "covered item", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    runner = EvalRunner(loop=AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small"))

    result = await runner.run_task(
        EvalTaskSpec(
            id="requirements-gate",
            prompt="Cover the acceptance criteria.",
            max_turns=1,
            requirements=["covered item", "missing item"],
            requirement_criteria=[
                {
                    "id": "REQ-missing",
                    "text": "missing item",
                    "required_source_type": "tool_output",
                    "min_strength": "strong",
                }
            ],
            quality_gates=["requirements_covered"],
        )
    )

    assert result.quality_gate_results == [
        {
            "name": "requirements_covered",
            "passed": False,
            "message": "Missing requirement evidence: missing item",
            "metadata": {
                "requirements": ["covered item", "missing item"],
                "requirement_criteria": [
                    {"id": "", "text": "covered item", "original_text": "covered item", "index": 0},
                    {"id": "", "text": "missing item", "original_text": "missing item", "index": 1},
                    {
                        "id": "REQ-missing",
                        "text": "missing item",
                        "original_text": "missing item",
                        "index": 0,
                        "required_source_type": "tool_output",
                        "required_source_ref": "",
                        "min_strength": "strong",
                        "required_artifact_path": "",
                        "required_tool": "",
                    },
                ],
                "missing_requirements": ["missing item"],
                "missing_requirement_ids": ["REQ-missing"],
                "missing_artifact_paths": [],
                "missing_tools": [],
                "evidence_count": 0,
                "artifact_count": 0,
            },
        }
    ]
    assert result.quality_failures == 1


@pytest.mark.asyncio
async def test_eval_suite_failure_artifacts_include_tool_result_excerpts(tmp_path):
    responses = [
        {"tool_calls": [{"name": "write_file", "arguments": {"content": "missing path"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            lambda args, ctx: {"ok": True},
        )
    )
    runner = EvalRunner(loop=AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced"))

    suite = await runner.run_suite(
        [EvalTaskSpec(id="tool-excerpt", prompt="write", max_turns=2, max_schema_violations=0)]
    )
    suite.write_reports(tmp_path)

    artifact = json.loads((tmp_path / "failures" / "tool-excerpt.json").read_text(encoding="utf-8"))
    timeline = json.loads((tmp_path / "failures" / "tool-excerpt.timeline.json").read_text(encoding="utf-8"))
    excerpt = artifact["tool_result_excerpts"][0]
    assert excerpt["tool_name"] == "write_file"
    assert excerpt["tool_call_id"] == "c1"
    assert excerpt["status"] == "blocked"
    assert excerpt["failed"] is True
    assert excerpt["metadata"]["failure_type"] == "schema_validation_failed"
    assert excerpt["metadata"]["schema_valid"] is False
    assert "$.path: missing required property" in excerpt["metadata"]["schema_errors"]
    assert "Tool argument schema validation failed" in excerpt["error_preview"]
    tool_events = [event for event in timeline["events"] if event["event_type"] == "tool.result"]
    assert tool_events[0]["tool_name"] == "write_file"
    assert tool_events[0]["tool_call_id"] == "c1"
    assert tool_events[0]["attributes"]["metadata"]["failure_type"] == "schema_validation_failed"
    event_types = [event["event_type"] for event in timeline["events"]]
    assert "model.request" in event_types
    assert "model.response" in event_types
    assert "tool.request" in event_types
    assert "finalization.result" in event_types


@pytest.mark.asyncio
async def test_eval_suite_writes_metadata_to_reports(tmp_path):
    final = json.dumps(
        {"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    runner = EvalRunner(loop=AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small"))

    suite = await runner.run_suite(
        [EvalTaskSpec(id="smoke", prompt="finish", max_turns=1)],
        metadata={"model": "glm-4.7-flash", "profile": "small"},
    )
    suite.write_reports(tmp_path)

    report_json = json.loads((tmp_path / "eval-report.json").read_text(encoding="utf-8"))
    report_md = (tmp_path / "eval-report.md").read_text(encoding="utf-8")
    assert report_json["metadata"]["model"] == "glm-4.7-flash"
    assert "- model: glm-4.7-flash" in report_md
    assert "- profile: small" in report_md


@pytest.mark.asyncio
async def test_eval_runner_counts_duplicate_tool_calls(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"echo": args["value"]}))
    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c1"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c2"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(EvalTaskSpec(id="duplicate", prompt="run", max_turns=3), session_id="dup")

    assert result.status == "final"
    assert result.tool_calls == 2
    assert result.duplicate_tool_calls == 1


@pytest.mark.asyncio
async def test_eval_runner_enforces_duplicate_tool_call_threshold(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    registry = ToolRegistry()
    registry.register(ToolSpec("echo", "Echo", {"type": "object"}, lambda args, ctx: {"echo": args["value"]}))
    responses = [
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c1"}]},
        {"tool_calls": [{"name": "echo", "arguments": {"value": "same"}, "id": "c2"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(id="duplicate-threshold", prompt="run", max_turns=3, max_duplicate_tool_calls=0),
        session_id="dup-threshold",
    )

    assert result.success is False
    assert result.trajectory_failures == 1
    assert any("Duplicate tool calls exceeded" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_counts_invalid_tool_calls():
    responses = [
        {"tool_calls": [{"name": "write_file", "arguments": {"path": "x.txt", "content": "x"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(ToolSpec("write_file", "Write", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(EvalTaskSpec(id="invalid", prompt="run", allowed_tools=["read_file"], max_turns=3))

    assert result.invalid_tool_calls == 1
    assert result.tool_failure_types == {"tool_not_allowed": 1}


@pytest.mark.asyncio
async def test_eval_runner_enforces_required_and_forbidden_tools():
    responses = [
        {"tool_calls": [{"name": "read_file", "arguments": {}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(ToolSpec("read_file", "Read", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="tool-oracle",
            prompt="run",
            max_turns=2,
            required_tools=["run_test"],
            forbidden_tools=["read_file"],
        )
    )

    assert result.success is False
    assert result.trajectory_failures == 2
    assert any("Missing required tools" in error for error in result.errors)
    assert any("Forbidden tools were called" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_enforces_required_tool_order():
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {}, "id": "c1"}]},
        {"tool_calls": [{"name": "write_file", "arguments": {}, "id": "c2"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(ToolSpec("run_test", "Test", {"type": "object"}, lambda args, ctx: {"ok": True}))
    registry.register(ToolSpec("write_file", "Write", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="tool-order",
            prompt="run",
            max_turns=3,
            required_tool_order=["write_file", "run_test"],
        )
    )

    assert result.success is False
    assert result.trajectory_failures == 1
    assert any("Required tool order not satisfied" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_allows_matching_required_tool_arguments(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"command": ["python", "-m", "pytest", "-q"]}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(ToolSpec("run_test", "Test", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="tool-args-pass",
            prompt="run",
            max_turns=2,
            required_tool_arguments=[
                {"tool": "run_test", "arguments": {"command": {"contains": "pytest"}}},
            ],
        ),
        session_id="tool-args-pass",
    )

    assert result.success is True
    assert result.trajectory_failures == 0


@pytest.mark.asyncio
async def test_eval_runner_enforces_required_tool_arguments(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"command": ["python", "-m", "unittest"]}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(ToolSpec("run_test", "Test", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="tool-args-fail",
            prompt="run",
            max_turns=2,
            required_tool_arguments=[
                {"tool": "run_test", "arguments": {"command": {"contains": "pytest"}}},
            ],
        ),
        session_id="tool-args-fail",
    )

    assert result.success is False
    assert result.trajectory_failures == 1
    assert any("Required tool arguments not satisfied" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_supports_exact_required_tool_arguments(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "write_file", "arguments": {"path": "report.md", "content": "ok"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(ToolSpec("write_file", "Write", {"type": "object"}, lambda args, ctx: {"ok": True}))
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="tool-args-exact",
            prompt="run",
            max_turns=2,
            required_tool_arguments=[
                {"tool": "write_file", "arguments": {"path": "report.md"}},
            ],
        ),
        session_id="tool-args-exact",
    )

    assert result.success is True


@pytest.mark.asyncio
async def test_eval_runner_counts_tool_schema_violations(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "write_file", "arguments": {"content": "missing path"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            lambda args, ctx: {"ok": True},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(EvalTaskSpec(id="schema-count", prompt="run", max_turns=2), session_id="schema-count")

    assert result.schema_violations == 1
    assert any("Tool schema violation for write_file" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_enforces_tool_schema_violation_threshold(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"timeout": "thirty"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "run_test",
            "Test",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer"},
                },
            },
            lambda args, ctx: {"ok": True},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(id="schema-threshold", prompt="run", max_turns=2, max_schema_violations=0),
        session_id="schema-threshold",
    )

    assert result.success is False
    assert result.schema_violations == 1
    assert any("Schema violations exceeded" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_counts_recovered_schema_repair(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "write_file", "arguments": {"content": "missing path"}, "id": "c1"}]},
        {"tool_calls": [{"name": "write_file", "arguments": {"path": "report.md", "content": "ok"}, "id": "c2"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            lambda args, ctx: {"ok": True},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="schema-repair",
            prompt="run",
            max_turns=3,
            min_schema_repair_successes=1,
            max_schema_repair_failures=0,
            allow_recovered_schema_failures=True,
        ),
        session_id="schema-repair",
    )

    assert result.schema_repair_attempts == 1
    assert result.schema_repair_successes == 1
    assert result.schema_repair_failures == 0
    assert result.schema_repair_hints_seen == 1
    assert result.schema_repair_hint_successes == 1
    assert result.schema_repair_hint_failures == 0
    assert result.schema_repair_hint_types_seen == {"add_required_property": 1}
    assert result.schema_repair_hint_type_successes == {"add_required_property": 1}
    assert result.schema_repair_hint_type_failures == {"add_required_property": 0}
    assert result.tool_failures == 0


@pytest.mark.asyncio
async def test_eval_runner_gates_schema_repair_hint_metrics(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "README.md", "url": "x"}, "id": "c1"}]},
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "README.md"}, "id": "c2"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "read_file",
            "Read",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            lambda args, ctx: {"ok": True},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="schema-hint-repair",
            prompt="run",
            max_turns=3,
            min_schema_repair_hint_successes=1,
            max_schema_repair_hint_failures=0,
            allow_recovered_schema_failures=True,
        ),
        session_id="schema-hint-repair",
    )

    assert result.success is True
    assert result.schema_repair_hints_seen == 1
    assert result.schema_repair_hint_successes == 1
    assert result.schema_repair_hint_failures == 0
    assert result.schema_repair_hint_types_seen == {"remove_additional_property": 1}
    assert result.schema_repair_hint_type_successes == {"remove_additional_property": 1}
    assert result.schema_repair_hint_type_failures == {"remove_additional_property": 0}
    assert result.tool_result_excerpts[0]["metadata"]["schema_repair_hints"] == ["Remove the unsupported argument at $.url."]
    assert result.tool_result_excerpts[0]["metadata"]["schema_repair_hint_types"] == ["remove_additional_property"]
    assert result.tool_result_excerpts[0]["metadata"]["schema_repair_hint_details"][0]["schema_keyword"] == "additionalProperties"


@pytest.mark.asyncio
async def test_eval_runner_fails_unrecovered_schema_repair_hint_requirement(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "read_file", "arguments": {"path": "README.md", "url": "x"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "read_file",
            "Read",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            lambda args, ctx: {"ok": True},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="schema-hint-repair-fail",
            prompt="run",
            max_turns=2,
            min_schema_repair_hint_successes=1,
            max_schema_repair_hint_failures=0,
            allow_recovered_schema_failures=True,
        ),
        session_id="schema-hint-repair-fail",
    )

    assert result.success is False
    assert result.schema_repair_hints_seen == 1
    assert result.schema_repair_hint_successes == 0
    assert result.schema_repair_hint_failures == 1
    assert result.schema_repair_hint_types_seen == {"remove_additional_property": 1}
    assert result.schema_repair_hint_type_successes == {}
    assert result.schema_repair_hint_type_failures == {"remove_additional_property": 1}
    assert any("Schema repair hint successes below requirement" in error for error in result.errors)
    assert any("Schema repair hint failures exceeded" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_fails_unrecovered_schema_repair_requirement(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "write_file", "arguments": {"content": "missing path"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "write_file",
            "Write",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            lambda args, ctx: {"ok": True},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="schema-repair-fail",
            prompt="run",
            max_turns=2,
            min_schema_repair_successes=1,
            max_schema_repair_failures=0,
            allow_recovered_schema_failures=True,
        ),
        session_id="schema-repair-fail",
    )

    assert result.schema_repair_attempts == 1
    assert result.schema_repair_successes == 0
    assert result.schema_repair_failures == 1
    assert any("Schema repair successes below requirement" in error for error in result.errors)
    assert any("Schema repair failures exceeded" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_counts_recovered_generic_tool_repair(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "bad"}, "id": "c1"}]},
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "good"}, "id": "c2"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()

    def handler(args, ctx):
        return {"exit_code": 0 if args["command"] == "good" else 1, "stderr": "bad command"}

    registry.register(
        ToolSpec(
            "run_test",
            "Test",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            handler,
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="generic-tool-repair",
            prompt="run",
            max_turns=3,
            min_tool_repair_successes=1,
            max_tool_repair_failures=0,
            allow_recovered_tool_failures=True,
        ),
        session_id="generic-tool-repair",
    )

    assert result.tool_repair_attempts == 1
    assert result.tool_repair_successes == 1
    assert result.tool_repair_failures == 0
    assert result.tool_repair_attempts_by_type == {"command_failed": 1}
    assert result.tool_repair_successes_by_type == {"command_failed": 1}
    assert result.tool_failures == 0


@pytest.mark.asyncio
async def test_eval_runner_fails_unrecovered_generic_tool_repair(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "bad"}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "run_test",
            "Test",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            lambda args, ctx: {"exit_code": 1, "stderr": "bad command"},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="generic-tool-repair-fail",
            prompt="run",
            max_turns=2,
            min_tool_repair_successes=1,
            max_tool_repair_failures=0,
            allow_recovered_tool_failures=True,
        ),
        session_id="generic-tool-repair-fail",
    )

    assert result.tool_repair_attempts == 1
    assert result.tool_repair_successes == 0
    assert result.tool_repair_failures == 1
    assert result.tool_repair_failures_by_type == {"command_failed": 1}
    assert any("Tool repair successes below requirement" in error for error in result.errors)
    assert any("Tool repair failures exceeded" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_counts_retry_budget_and_lineage_blocks(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/a.py"}, "id": "c1"}]},
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/b.py"}, "id": "c2"}]},
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/c.py"}, "id": "c3"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "run_test",
            "Test",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            lambda args, ctx: {"exit_code": 1, "stderr": "failed"},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(id="lineage-metrics", prompt="run", max_turns=4),
        session_id="lineage-metrics",
    )

    assert result.retry_budget_exhaustions == 2
    assert result.pre_dispatch_blocks == 1
    assert result.tool_failure_types["command_failed"] == 2
    assert result.tool_failure_types["retry_budget_exhausted"] == 1
    assert result.failure_shape_keys["python pytest"] == 3


@pytest.mark.asyncio
async def test_eval_runner_enforces_lineage_metric_thresholds(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    responses = [
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/a.py"}, "id": "c1"}]},
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/b.py"}, "id": "c2"}]},
        {"tool_calls": [{"name": "run_test", "arguments": {"command": "python -m pytest tests/c.py"}, "id": "c3"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            "run_test",
            "Test",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            lambda args, ctx: {"exit_code": 1, "stderr": "failed"},
        )
    )
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="small", state=state)
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="lineage-thresholds",
            prompt="run",
            max_turns=4,
            max_retry_budget_exhaustions=1,
            max_pre_dispatch_blocks=0,
            forbidden_failure_shape_keys=["python pytest"],
            max_failure_shape_key_counts={"python pytest": 2},
        ),
        session_id="lineage-thresholds",
    )

    assert result.success is False
    assert result.trajectory_failures == 4
    assert any("Retry budget exhaustions exceeded" in error for error in result.errors)
    assert any("Pre-dispatch blocks exceeded" in error for error in result.errors)
    assert any("Forbidden failure shape keys were observed" in error for error in result.errors)
    assert any("Failure shape key count exceeded for python pytest" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_enforces_required_failure_shape_keys():
    final = json.dumps(
        {"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""}
    )
    loop = AgentLoop(provider=FakeProvider([{"content": final}]), registry=ToolRegistry(), profile="small")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(
            id="missing-shape",
            prompt="finish",
            max_turns=1,
            required_failure_shape_keys=["python pytest"],
        )
    )

    assert result.success is False
    assert result.trajectory_failures == 1
    assert any("Missing required failure shape keys" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_counts_policy_blocks(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    responses = [
        {"tool_calls": [{"name": "run_shell", "arguments": {"command": "rm -rf ."}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(EvalTaskSpec(id="policy", prompt="run", allowed_tools=["run_shell"], max_turns=3))

    assert result.policy_blocks == 1
    assert result.invalid_tool_calls == 1


@pytest.mark.asyncio
async def test_eval_runner_enforces_policy_block_threshold(tmp_path):
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(tmp_path))
    responses = [
        {"tool_calls": [{"name": "run_shell", "arguments": {"command": "rm -rf ."}, "id": "c1"}]},
        {"content": json.dumps({"status": "done", "summary": "ok", "evidence_refs": [], "artifact_refs": [], "next_action": ""})},
    ]
    loop = AgentLoop(provider=FakeProvider(responses), registry=registry, profile="balanced")
    runner = EvalRunner(loop=loop)

    result = await runner.run_task(
        EvalTaskSpec(id="policy-threshold", prompt="run", allowed_tools=["run_shell"], max_turns=3, max_policy_blocks=0)
    )

    assert result.success is False
    assert any("Policy blocks exceeded" in error for error in result.errors)


@pytest.mark.asyncio
async def test_eval_runner_counts_evidence_resolution_failures(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("eval-evidence-fail")
    ledger = EvidenceLedger(state)
    ledger.record_claim(
        session_id=session_id,
        claim="Test command executed",
        source_type="test",
        source_ref="python -m pytest -q",
        metadata={"exit_code": 0, "status": "ok"},
        evidence_id="e1",
    )
    final = json.dumps(
        {
            "status": "done",
            "summary": "All tests passed.",
            "evidence_refs": ["e1"],
            "artifact_refs": [],
            "next_action": "",
        }
    )
    loop = AgentLoop(
        provider=FakeProvider([{"content": final}]),
        registry=ToolRegistry(),
        profile="small_strict",
        state=state,
        evidence_ledger=ledger,
    )
    runner = EvalRunner(loop=loop, evidence_ledger=ledger)

    result = await runner.run_task(EvalTaskSpec(id="evidence-fail", prompt="finish", max_turns=1), session_id=session_id)

    assert result.status == "blocked"
    assert result.evidence_resolution_failures == 1


@pytest.mark.asyncio
async def test_eval_runner_enforces_evidence_resolution_failure_threshold(tmp_path):
    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("eval-evidence-threshold")
    ledger = EvidenceLedger(state)
    ledger.record_claim(
        session_id=session_id,
        claim="Test command executed",
        source_type="test",
        source_ref="python -m pytest -q",
        metadata={"exit_code": 0, "status": "ok"},
        evidence_id="e1",
    )
    final = json.dumps(
        {
            "status": "done",
            "summary": "All tests passed.",
            "evidence_refs": ["e1"],
            "artifact_refs": [],
            "next_action": "",
        }
    )
    loop = AgentLoop(
        provider=FakeProvider([{"content": final}]),
        registry=ToolRegistry(),
        profile="small_strict",
        state=state,
        evidence_ledger=ledger,
    )
    runner = EvalRunner(loop=loop, evidence_ledger=ledger)

    result = await runner.run_task(
        EvalTaskSpec(
            id="evidence-threshold",
            prompt="finish",
            max_turns=1,
            max_evidence_resolution_failures=0,
        ),
        session_id=session_id,
    )

    assert result.success is False
    assert any("Evidence resolution failures exceeded" in error for error in result.errors)
