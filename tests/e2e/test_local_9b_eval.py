import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from metis.evals.runner import EvalResult, EvalSuiteResult
from metis.evals.real_model_suite import (
    generate_real_small_model_eval_run_name,
    real_model_env_configured,
    real_small_model_eval_latest_pointer_path,
    real_small_model_eval_report_dir,
    real_small_model_eval_metadata,
    real_small_model_eval_tasks,
    resolve_real_small_model_eval_run_name,
    run_and_write_real_small_model_eval_suite,
    run_real_small_model_eval_suite,
    write_real_small_model_eval_reports,
)
from metis.runtime.errors import ProviderError


@pytest.mark.network
def test_local_9b_eval_report_exists_or_endpoint_configured():
    report = Path("docs/evals/9b-eval-report.md")
    if not os.getenv("METIS_API_KEY"):
        pytest.skip("METIS_API_KEY not configured; real endpoint eval is skipped, not faked")
    assert report.exists()


def test_real_small_model_eval_suite_declares_strict_default_gates():
    tasks = real_small_model_eval_tasks()
    task_by_id = {task.id: task for task in tasks}

    assert len(tasks) >= 12
    assert set(task_by_id) == {
        "strict-final-no-tools",
        "read-then-summarize",
        "safe-command",
        "write-report-file",
        "read-then-write-summary",
        "forbidden-shell-readme",
        "schema-repair-write-file",
        "command-schema-repair",
        "safe-test-command",
        "verified-test-evidence",
        "verified-write-evidence",
        "verified-read-write-report-evidence",
    }
    repair_task_ids = {"schema-repair-write-file", "command-schema-repair"}
    for task in tasks:
        assert task.max_retry_budget_exhaustions == 0
        assert task.max_pre_dispatch_blocks == 0
        if task.id not in repair_task_ids:
            assert task.max_invalid_tool_calls == 0
            assert task.max_schema_violations == 0
    assert task_by_id["schema-repair-write-file"].min_schema_repair_successes == 1
    assert task_by_id["command-schema-repair"].min_schema_repair_successes == 1
    assert task_by_id["read-then-write-summary"].required_tool_order == ["read_file", "write_file"]
    assert task_by_id["verified-test-evidence"].require_verified_final is True
    assert task_by_id["verified-test-evidence"].required_evidence_sources == ["test"]
    assert task_by_id["verified-write-evidence"].require_verified_final is True
    assert task_by_id["verified-write-evidence"].required_evidence_sources == ["tool_output"]
    assert task_by_id["verified-write-evidence"].required_tool_arguments == [
        {"tool": "write_file", "arguments": {"path": "outputs/verified-write.md"}}
    ]
    verified_report = task_by_id["verified-read-write-report-evidence"]
    assert verified_report.required_tool_order == ["read_file", "write_file"]
    assert verified_report.require_verified_final is True
    assert verified_report.required_evidence_sources == ["tool_output"]
    assert verified_report.required_tool_arguments == [
        {"tool": "read_file", "arguments": {"path": "README.md"}},
        {"tool": "write_file", "arguments": {"path": "outputs/verified-read-write-report.md"}},
    ]


def test_real_small_model_eval_metadata_declares_model_profile_and_task_count():
    metadata = real_small_model_eval_metadata()

    assert metadata["suite"] == "real-small-model"
    assert metadata["profile"] == "small"
    assert metadata["task_count"] == len(real_small_model_eval_tasks())


def test_real_small_model_eval_run_name_supports_timestamp_aliases():
    now = datetime(2026, 5, 25, 1, 2, 3, tzinfo=timezone.utc)

    assert generate_real_small_model_eval_run_name(now=now) == "20260525-010203"
    assert resolve_real_small_model_eval_run_name("auto", now=now) == "20260525-010203"
    assert resolve_real_small_model_eval_run_name("timestamp", now=now) == "20260525-010203"
    assert resolve_real_small_model_eval_run_name("latest", now=now) == "latest"


def test_real_small_model_eval_report_writer_uses_stable_run_directory(tmp_path):
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
                final_verified=True,
                schema_repair_hints_seen=1,
                schema_repair_hint_successes=1,
                schema_repair_hint_failures=0,
                schema_repair_hint_types_seen={"remove_additional_property": 1},
                schema_repair_hint_type_successes={"remove_additional_property": 1},
            )
        ],
        metadata={"suite": "real-small-model", "task_count": 1, "profile": "small"},
    )

    expected_dir = real_small_model_eval_report_dir(output_root=tmp_path, run_name="latest")
    output_dir = write_real_small_model_eval_reports(suite, output_root=tmp_path, run_name="latest")

    assert output_dir == expected_dir
    assert (output_dir / "eval-report.json").exists()
    assert (output_dir / "eval-report.md").exists()
    assert (output_dir / "manifest.json").exists()
    assert '"suite": "real-small-model"' in (output_dir / "eval-report.json").read_text(encoding="utf-8")
    assert "## Metadata" in (output_dir / "eval-report.md").read_text(encoding="utf-8")
    manifest = (output_dir / "manifest.json").read_text(encoding="utf-8")
    assert '"run_name": "latest"' in manifest
    assert '"success_rate": 1.0' in manifest
    manifest_payload = json.loads(manifest)
    assert manifest_payload["summary"]["schema_repair_hint_recovery_rate"] == 1.0
    latest_pointer = json.loads(real_small_model_eval_latest_pointer_path(output_root=tmp_path).read_text(encoding="utf-8"))
    assert latest_pointer["latest_run_name"] == "latest"
    assert latest_pointer["success_rate"] == 1.0
    assert latest_pointer["summary"]["schema_repair_hints_seen"] == 1


def test_real_small_model_eval_report_writer_resolves_auto_run_name_and_latest_pointer(tmp_path, monkeypatch):
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
                final_verified=True,
            )
        ],
        metadata={"suite": "real-small-model", "task_count": 1, "profile": "small"},
    )

    monkeypatch.setattr(
        "metis.evals.real_model_suite.generate_real_small_model_eval_run_name",
        lambda now=None: "20260525-010203",
    )
    output_dir = write_real_small_model_eval_reports(suite, output_root=tmp_path, run_name="auto")

    assert output_dir == real_small_model_eval_report_dir(output_root=tmp_path, run_name="20260525-010203")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_name"] == "20260525-010203"
    assert manifest["requested_run_name"] == "auto"
    assert manifest["summary"]["task_count"] == 1
    latest_pointer = json.loads(real_small_model_eval_latest_pointer_path(output_root=tmp_path).read_text(encoding="utf-8"))
    assert latest_pointer["latest_run_name"] == "20260525-010203"
    assert latest_pointer["latest_run_dir"].endswith("20260525-010203")
    assert latest_pointer["summary"]["task_count"] == 1


@pytest.mark.network
@pytest.mark.asyncio
async def test_real_small_model_eval_suite_runs_when_endpoint_configured(tmp_path):
    if not real_model_env_configured():
        pytest.skip("METIS_BASE_URL, METIS_API_KEY, and METIS_MODEL are required for real endpoint eval")

    (tmp_path / "README.md").write_text("Metis is a reusable agent harness.", encoding="utf-8")
    try:
        suite = await run_real_small_model_eval_suite(workspace=tmp_path)
    except ProviderError as exc:
        if "429 Too Many Requests" in str(exc):
            pytest.skip(f"External provider is rate limited: {exc}")
        raise
    suite.write_reports(tmp_path / "evals")

    assert suite.results
    assert (tmp_path / "evals" / "eval-report.json").exists()
    assert (tmp_path / "evals" / "eval-report.md").exists()


@pytest.mark.network
@pytest.mark.asyncio
async def test_real_small_model_eval_suite_can_write_stable_reports_when_endpoint_configured(tmp_path):
    if not real_model_env_configured():
        pytest.skip("METIS_BASE_URL, METIS_API_KEY, and METIS_MODEL are required for real endpoint eval")

    (tmp_path / "README.md").write_text("Metis is a reusable agent harness.", encoding="utf-8")
    try:
        suite = await run_and_write_real_small_model_eval_suite(
            workspace=tmp_path,
            output_root=tmp_path,
            run_name="latest",
        )
    except ProviderError as exc:
        if "429 Too Many Requests" in str(exc):
            pytest.skip(f"External provider is rate limited: {exc}")
        raise

    assert suite.results
    assert (tmp_path / "docs" / "evals" / "runs" / "latest" / "eval-report.json").exists()
    assert (tmp_path / "docs" / "evals" / "runs" / "latest" / "eval-report.md").exists()
    assert (tmp_path / "docs" / "evals" / "runs" / "latest" / "manifest.json").exists()
