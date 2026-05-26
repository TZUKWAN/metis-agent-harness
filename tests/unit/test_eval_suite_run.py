import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from metis.evals.runner import EvalResult, EvalSuiteResult, EvalTaskSpec
from metis.evals.real_model_suite import (
    real_small_model_eval_manifest,
    real_small_model_eval_metadata,
    real_small_model_pre_run_contract,
    write_real_small_model_pre_run_contract,
    write_real_small_model_eval_reports,
)
from metis.evals.suite_run import (
    generic_eval_quality_gate_inventory,
    generic_eval_tool_inventory,
    generic_eval_validation_context,
    generic_eval_report_dir,
    generic_eval_pre_run_contract,
    generic_eval_suite_manifest,
    generic_eval_suite_metadata,
    generic_eval_suite_requires_model_execution,
    generate_eval_run_name,
    load_eval_suite_payload,
    resolve_eval_run_name,
    write_generic_eval_pre_run_contract,
    write_generic_eval_suite_reports,
    quality_gate_inventory_to_markdown,
    tool_inventory_to_markdown,
)


def test_load_eval_suite_payload_accepts_directory_and_records_task_count(tmp_path):
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
                            "id": "targeted-repair-001",
                            "prompt": "Recover from schema failure.",
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = load_eval_suite_payload(suite_dir)

    assert payload["suite"] == "targeted-repair-regression"
    assert payload["schema_version"] == "1"
    assert len(payload["tasks"]) == 1


def test_load_eval_suite_payload_rejects_unsupported_schema_version(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        '{"suite": "future-suite", "schema_version": "2", "tasks": [{"id": "future", "prompt": "Run."}]}',
        encoding="utf-8",
    )

    try:
        load_eval_suite_payload(suite_path)
    except ValueError as exc:
        assert "Unsupported eval suite schema_version: 2" in str(exc)
    else:
        raise AssertionError("load_eval_suite_payload should reject unsupported schema versions")


def test_generic_eval_suite_metadata_records_provider_profile_and_suite_path(monkeypatch, tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text('{"suite": "custom-suite", "schema_version": "1", "tasks": []}', encoding="utf-8")
    monkeypatch.setenv("METIS_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    metadata = generic_eval_suite_metadata(
        suite_path=suite_path,
        tasks=[EvalTaskSpec(id="a", prompt="run")],
        profile="small_strict",
    )

    assert metadata["suite"] == "custom-suite"
    assert metadata["schema_version"] == "1"
    assert metadata["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert metadata["suite_schema_sha256"] == hashlib.sha256(
        (Path("docs") / "evals" / "suite-schema-v1.json").read_bytes()
    ).hexdigest()
    assert metadata["task_count"] == 1
    assert metadata["model"] == "glm-4.7-flash"
    assert metadata["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
    assert metadata["profile"] == "small_strict"
    assert metadata["suite_path"] == str(suite_path)
    assert len(metadata["tool_inventory_hash"]) == 64


def test_real_small_model_metadata_records_code_defined_schema_evidence(monkeypatch):
    monkeypatch.setenv("METIS_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    metadata = real_small_model_eval_metadata()

    assert metadata["suite"] == "real-small-model"
    assert metadata["suite_definition_type"] == "code-defined-builtin"
    assert metadata["schema_version"] == "code-defined"
    assert metadata["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert metadata["suite_schema_sha256"] == hashlib.sha256(
        (Path("docs") / "evals" / "suite-schema-v1.json").read_bytes()
    ).hexdigest()
    assert metadata["model"] == "glm-4.7-flash"
    assert metadata["base_url"] == "https://open.bigmodel.cn/api/paas/v4"
    assert len(metadata["tool_inventory_hash"]) == 64


def test_real_small_model_pre_run_contract_records_tasks_and_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("METIS_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    contract = real_small_model_pre_run_contract(
        workspace=tmp_path,
        run_name="20260525-010203",
        requested_run_name="auto",
    )

    assert contract["artifact_type"] == "real-small-model-pre-run-contract"
    assert contract["run_name"] == "20260525-010203"
    assert contract["requested_run_name"] == "auto"
    assert contract["suite_definition_type"] == "code-defined-builtin"
    assert contract["task_count"] == len(contract["task_specs"])
    assert len(contract["task_contract_hash"]) == 64
    assert contract["task_spec_hash_summary"]["strict-final-no-tools"]
    assert contract["provenance"]["task_contract_hash"] == contract["task_contract_hash"]
    assert len(contract["provenance_hash"]) == 64


def test_write_real_small_model_pre_run_contract_writes_json_and_markdown(monkeypatch, tmp_path):
    monkeypatch.setenv("METIS_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    output_dir = write_real_small_model_pre_run_contract(
        workspace=tmp_path,
        output_root=tmp_path,
        run_name="manual",
        requested_run_name="auto",
    )

    payload = json.loads((output_dir / "pre-run-contract.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "pre-run-contract.md").read_text(encoding="utf-8")
    assert payload["run_name"] == "manual"
    assert payload["requested_run_name"] == "auto"
    assert payload["provenance_hash"]
    assert "# Metis Real Small-Model Pre-run Contract" in markdown
    assert "Task contract hash:" in markdown


def test_real_small_model_reports_write_manifest_and_pointer_schema_evidence(tmp_path):
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ],
        metadata={
            "suite": "real-small-model",
            "suite_definition_type": "code-defined-builtin",
            "schema_version": "code-defined",
            "suite_schema_id": "https://metis.local/schemas/evals/suite-schema-v1.json",
            "suite_schema_path": "docs/evals/suite-schema-v1.json",
            "suite_schema_sha256": "abc123",
        },
        task_specs={
            "strict-final-no-tools": EvalTaskSpec(
                id="strict-final-no-tools",
                prompt="Return only the strict final JSON.",
            )
        },
    )

    pre_run_dir = write_real_small_model_pre_run_contract(
        workspace=tmp_path,
        output_root=tmp_path,
        run_name="manual",
        requested_run_name="manual",
    )
    pre_run_contract = json.loads((pre_run_dir / "pre-run-contract.json").read_text(encoding="utf-8"))
    pre_run_contract_sha256 = hashlib.sha256((pre_run_dir / "pre-run-contract.json").read_bytes()).hexdigest()

    output_dir = write_real_small_model_eval_reports(suite, output_root=tmp_path, run_name="manual")

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    pointer = json.loads((tmp_path / "docs" / "evals" / "runs" / "latest.json").read_text(encoding="utf-8"))
    assert manifest["suite_definition_type"] == "code-defined-builtin"
    assert manifest["schema_version"] == "code-defined"
    assert manifest["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert manifest["suite_schema_path"] == "docs/evals/suite-schema-v1.json"
    assert manifest["suite_schema_sha256"] == "abc123"
    assert len(manifest["task_contract_hash"]) == 64
    assert manifest["task_spec_hash_summary"]["strict-final-no-tools"]
    assert manifest["provenance"]["suite"] == "real-small-model"
    assert manifest["provenance"]["task_contract_hash"] == manifest["task_contract_hash"]
    assert len(manifest["provenance_hash"]) == 64
    assert manifest["pre_run_contract_path"] == str(output_dir / "pre-run-contract.json")
    assert manifest["pre_run_contract_sha256"] == pre_run_contract_sha256
    assert manifest["pre_run_provenance_hash"] == pre_run_contract["provenance_hash"]
    assert pointer["suite_definition_type"] == "code-defined-builtin"
    assert pointer["schema_version"] == "code-defined"
    assert pointer["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert pointer["suite_schema_sha256"] == "abc123"
    assert pointer["task_contract_hash"] == manifest["task_contract_hash"]
    assert pointer["task_spec_hash_summary"] == manifest["task_spec_hash_summary"]
    assert pointer["provenance"] == manifest["provenance"]
    assert pointer["provenance_hash"] == manifest["provenance_hash"]
    assert pointer["pre_run_contract_path"] == manifest["pre_run_contract_path"]
    assert pointer["pre_run_contract_sha256"] == manifest["pre_run_contract_sha256"]
    assert pointer["pre_run_provenance_hash"] == manifest["pre_run_provenance_hash"]
    attestation = json.loads((output_dir / "run-attestation.json").read_text(encoding="utf-8"))
    attested = {subject["name"]: subject for subject in attestation["subject"]}
    assert attestation["predicateType"] == "https://metis.local/attestations/eval-run/v1"
    assert attestation["predicate"]["pre_run_contract_sha256"] == pre_run_contract_sha256
    assert "run-attestation.json" not in attested
    assert "manifest.json" in attested
    assert "pre-run-contract.json" in attested
    assert "task-specs.json" in attested
    assert attested["manifest.json"]["digest"]["sha256"] == hashlib.sha256(
        (output_dir / "manifest.json").read_bytes()
    ).hexdigest()
    assert attested["pre-run-contract.json"]["digest"]["sha256"] == pre_run_contract_sha256
    assert (output_dir / "run-attestation.md").exists()


def test_real_small_model_manifest_defaults_to_code_defined_schema_evidence():
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ],
        metadata={},
    )

    manifest = real_small_model_eval_manifest(suite, run_name="manual")

    assert manifest["suite_definition_type"] == "code-defined-builtin"
    assert manifest["schema_version"] == "code-defined"
    assert manifest["suite_schema_id"] == ""
    assert manifest["suite_schema_sha256"] == ""
    assert len(manifest["task_contract_hash"]) == 64
    assert manifest["task_spec_hash_summary"] == {}


def test_real_small_model_failure_timeline_includes_pre_run_contract_anchor(tmp_path):
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=False,
                status="blocked",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
                errors=["Final unverified"],
            )
        ],
        metadata={
            "suite": "real-small-model",
            "suite_definition_type": "code-defined-builtin",
            "schema_version": "code-defined",
            "suite_schema_sha256": "abc123",
        },
        task_specs={
            "strict-final-no-tools": EvalTaskSpec(
                id="strict-final-no-tools",
                prompt="Return only the strict final JSON.",
            )
        },
    )
    pre_run_dir = write_real_small_model_pre_run_contract(
        workspace=tmp_path,
        output_root=tmp_path,
        run_name="manual",
        requested_run_name="manual",
    )
    pre_run_contract = json.loads((pre_run_dir / "pre-run-contract.json").read_text(encoding="utf-8"))
    pre_run_contract_sha256 = hashlib.sha256((pre_run_dir / "pre-run-contract.json").read_bytes()).hexdigest()

    output_dir = write_real_small_model_eval_reports(suite, output_root=tmp_path, run_name="manual")

    timeline = json.loads((output_dir / "failures" / "strict-final-no-tools.timeline.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "failures" / "strict-final-no-tools.timeline.md").read_text(encoding="utf-8")
    assert timeline["run_metadata"]["pre_run_contract_path"] == str(output_dir / "pre-run-contract.json")
    assert timeline["run_metadata"]["pre_run_contract_sha256"] == pre_run_contract_sha256
    assert timeline["run_metadata"]["pre_run_provenance_hash"] == pre_run_contract["provenance_hash"]
    assert "Pre-run contract sha256:" in markdown
    assert pre_run_contract_sha256 in markdown


def test_generic_eval_validation_context_uses_builtin_tools_and_quality_gates(tmp_path):
    context = generic_eval_validation_context(workspace=tmp_path)

    assert {"read_file", "write_file", "run_command", "run_shell", "run_test"} <= context["available_tools"]
    assert {"artifact_exists", "artifact_non_empty", "no_placeholder", "run_attestation_verifies"} <= context[
        "available_quality_gates"
    ]
    assert context["tool_schemas"]["read_file"]["properties"]["path"]["type"] == "string"
    assert context["tool_schemas"]["run_command"]["properties"]["timeout"]["type"] == "integer"


def test_generic_eval_tool_inventory_includes_builtin_tool_metadata(tmp_path):
    inventory = generic_eval_tool_inventory(workspace=tmp_path)
    markdown = tool_inventory_to_markdown(inventory)

    tool_by_name = {tool["name"]: tool for tool in inventory["tools"]}
    assert inventory["workspace"] == str(tmp_path)
    assert inventory["tool_count"] >= 5
    assert tool_by_name["read_file"]["category"] == "files"
    assert tool_by_name["write_file"]["side_effect"] == "write"
    assert tool_by_name["run_shell"]["metadata"]["uses_shell"] is False
    assert "Metis Eval Tool Inventory" in markdown
    assert "read_file" in markdown


def test_generic_eval_quality_gate_inventory_includes_default_gates():
    inventory = generic_eval_quality_gate_inventory()
    markdown = quality_gate_inventory_to_markdown(inventory)

    gate_by_name = {gate["name"]: gate for gate in inventory["quality_gates"]}
    assert inventory["gate_count"] >= 5
    assert gate_by_name["artifact_exists"]["failure_policy"] == "fail"
    assert gate_by_name["run_attestation_verifies"]["description"]
    assert gate_by_name["no_fake_completion"]["description"]
    assert "Metis Eval Quality Gate Inventory" in markdown
    assert "artifact_exists" in markdown


def test_generic_eval_run_name_supports_timestamp_aliases():
    now = datetime(2026, 5, 25, 1, 2, 3, tzinfo=timezone.utc)

    assert generate_eval_run_name(now=now) == "20260525-010203"
    assert resolve_eval_run_name("auto", now=now) == "20260525-010203"
    assert resolve_eval_run_name("timestamped", now=now) == "20260525-010203"
    assert resolve_eval_run_name("manual", now=now) == "manual"


def test_generic_eval_suite_requires_model_execution_detects_deterministic_fixtures(tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "artifact-fixtures",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "artifact-verification-repair-001",
                        "prompt": "Verify artifacts.",
                        "fixture_type": "artifact_verification",
                        "requires_model_execution": False,
                        "artifact_verification": {"target_runs": ["current"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert generic_eval_suite_requires_model_execution(suite_path) is False

    suite_path.write_text(
        json.dumps(
            {
                "suite": "mixed",
                "schema_version": "1",
                "tasks": [
                    {
                        "id": "artifact-verification-repair-001",
                        "prompt": "Verify artifacts.",
                        "fixture_type": "artifact_verification",
                        "requires_model_execution": False,
                    },
                    {"id": "model-task", "prompt": "Run model."},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert generic_eval_suite_requires_model_execution(suite_path) is True


def test_generic_eval_pre_run_contract_records_suite_tasks_and_provenance(monkeypatch, tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "custom-suite",
                "schema_version": "1",
                "tasks": [{"id": "task-a", "prompt": "Run task A."}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("METIS_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    contract = generic_eval_pre_run_contract(
        suite_path=suite_path,
        workspace=tmp_path,
        profile="small_strict",
        run_name="20260525-010203",
        requested_run_name="auto",
    )

    assert contract["artifact_type"] == "generic-eval-pre-run-contract"
    assert contract["suite"] == "custom-suite"
    assert contract["schema_version"] == "1"
    assert contract["run_name"] == "20260525-010203"
    assert contract["requested_run_name"] == "auto"
    assert contract["profile"] == "small_strict"
    assert contract["task_count"] == 1
    assert contract["task_spec_hash_summary"]["task-a"]
    assert contract["provenance"]["task_contract_hash"] == contract["task_contract_hash"]
    assert len(contract["provenance_hash"]) == 64


def test_write_generic_eval_pre_run_contract_writes_json_and_markdown(monkeypatch, tmp_path):
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "custom-suite",
                "schema_version": "1",
                "tasks": [{"id": "task-a", "prompt": "Run task A."}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("METIS_MODEL", "glm-4.7-flash")
    monkeypatch.setenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    output_dir = write_generic_eval_pre_run_contract(
        suite_path=suite_path,
        workspace=tmp_path,
        output_root=tmp_path,
        profile="small",
        run_name="manual",
        requested_run_name="auto",
    )

    payload = json.loads((output_dir / "pre-run-contract.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "pre-run-contract.md").read_text(encoding="utf-8")
    assert payload["suite"] == "custom-suite"
    assert payload["run_name"] == "manual"
    assert payload["requested_run_name"] == "auto"
    assert payload["provenance_hash"]
    assert "# Metis Generic Eval Pre-run Contract" in markdown
    assert "Task contract hash:" in markdown


def test_write_generic_eval_suite_reports_writes_manifest_and_latest_pointer(tmp_path, monkeypatch):
    monkeypatch.setattr("metis.evals.suite_run.generate_eval_run_name", lambda now=None: "20260525-010203")
    suite_path = tmp_path / "targeted-eval-suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "targeted-repair-regression",
                "schema_version": "1",
                "tasks": [{"id": "targeted-repair-001", "prompt": "Recover from schema repair hint failure."}],
            }
        ),
        encoding="utf-8",
    )
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
                schema_repair_hints_seen=1,
                schema_repair_hint_successes=1,
                schema_repair_hint_failures=0,
                schema_repair_hint_types_seen={"remove_additional_property": 1},
                schema_repair_hint_type_successes={"remove_additional_property": 1},
                schema_repair_hint_type_failures={"remove_additional_property": 0},
            )
        ],
        metadata={
            "suite": "targeted-repair-regression",
            "task_count": 1,
            "profile": "small",
            "suite_schema_id": "https://metis.local/schemas/evals/suite-schema-v1.json",
            "suite_schema_path": "docs/evals/suite-schema-v1.json",
            "suite_schema_sha256": "abc123",
        },
        task_specs={
            "targeted-repair-001": EvalTaskSpec(
                id="targeted-repair-001",
                prompt="Recover from schema repair hint failure.",
            )
        },
    )
    pre_run_dir = write_generic_eval_pre_run_contract(
        suite_path=suite_path,
        workspace=tmp_path,
        output_root=tmp_path,
        profile="small",
        run_name="20260525-010203",
        requested_run_name="auto",
    )
    pre_run_contract = json.loads((pre_run_dir / "pre-run-contract.json").read_text(encoding="utf-8"))
    pre_run_contract_sha256 = hashlib.sha256((pre_run_dir / "pre-run-contract.json").read_bytes()).hexdigest()

    output_dir = write_generic_eval_suite_reports(suite, output_root=tmp_path, run_name="auto")

    assert output_dir == generic_eval_report_dir(output_root=tmp_path, run_name="20260525-010203")
    assert (output_dir / "eval-report.json").exists()
    assert (output_dir / "eval-report.md").exists()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    pointer = json.loads((tmp_path / "docs" / "evals" / "runs" / "latest.json").read_text(encoding="utf-8"))
    assert manifest["suite"] == "targeted-repair-regression"
    assert manifest["requested_run_name"] == "auto"
    assert manifest["success_rate"] == 1.0
    assert manifest["summary"]["schema_repair_hint_recovery_rate"] == 1.0
    assert manifest["summary"]["schema_repair_hint_types_seen"] == {"remove_additional_property": 1}
    assert manifest["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert manifest["suite_schema_path"] == "docs/evals/suite-schema-v1.json"
    assert manifest["suite_schema_sha256"] == "abc123"
    assert len(manifest["task_contract_hash"]) == 64
    assert manifest["task_spec_hash_summary"]["targeted-repair-001"]
    assert manifest["provenance"]["suite"] == "targeted-repair-regression"
    assert manifest["provenance"]["task_contract_hash"] == manifest["task_contract_hash"]
    assert len(manifest["provenance_hash"]) == 64
    assert manifest["pre_run_contract_path"] == str(output_dir / "pre-run-contract.json")
    assert manifest["pre_run_contract_sha256"] == pre_run_contract_sha256
    assert manifest["pre_run_provenance_hash"] == pre_run_contract["provenance_hash"]
    assert pointer["latest_run_name"] == "20260525-010203"
    assert pointer["suite"] == "targeted-repair-regression"
    assert pointer["summary"]["schema_repair_hint_successes"] == 1
    assert pointer["suite_schema_id"] == "https://metis.local/schemas/evals/suite-schema-v1.json"
    assert pointer["suite_schema_sha256"] == "abc123"
    assert pointer["task_contract_hash"] == manifest["task_contract_hash"]
    assert pointer["task_spec_hash_summary"] == manifest["task_spec_hash_summary"]
    assert pointer["provenance"] == manifest["provenance"]
    assert pointer["provenance_hash"] == manifest["provenance_hash"]
    assert pointer["pre_run_contract_path"] == manifest["pre_run_contract_path"]
    assert pointer["pre_run_contract_sha256"] == manifest["pre_run_contract_sha256"]
    assert pointer["pre_run_provenance_hash"] == manifest["pre_run_provenance_hash"]
    attestation = json.loads((output_dir / "run-attestation.json").read_text(encoding="utf-8"))
    attested = {subject["name"]: subject for subject in attestation["subject"]}
    assert attestation["predicate"]["suite"] == "targeted-repair-regression"
    assert attestation["predicate"]["pre_run_contract_sha256"] == pre_run_contract_sha256
    assert "manifest.json" in attested
    assert "pre-run-contract.json" in attested
    assert "eval-report.json" in attested
    assert "task-specs.json" in attested
    assert attested["pre-run-contract.json"]["digest"]["sha256"] == pre_run_contract_sha256
    assert "run-attestation.json" not in attested


def test_generic_eval_failure_timeline_includes_pre_run_contract_anchor(tmp_path, monkeypatch):
    monkeypatch.setattr("metis.evals.suite_run.generate_eval_run_name", lambda now=None: "20260525-010203")
    suite_path = tmp_path / "targeted-eval-suite.json"
    suite_path.write_text(
        json.dumps(
            {
                "suite": "targeted-repair-regression",
                "schema_version": "1",
                "tasks": [{"id": "targeted-repair-001", "prompt": "Repair the failing trace."}],
            }
        ),
        encoding="utf-8",
    )
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=False,
                status="blocked",
                turns_used=2,
                tool_calls=1,
                latency_seconds=0.01,
                errors=["Schema violations exceeded"],
            )
        ],
        metadata={
            "suite": "targeted-repair-regression",
            "profile": "small",
            "suite_schema_sha256": "abc123",
        },
        task_specs={
            "targeted-repair-001": EvalTaskSpec(
                id="targeted-repair-001",
                prompt="Repair the failing trace.",
            )
        },
    )
    pre_run_dir = write_generic_eval_pre_run_contract(
        suite_path=suite_path,
        workspace=tmp_path,
        output_root=tmp_path,
        profile="small",
        run_name="20260525-010203",
        requested_run_name="auto",
    )
    pre_run_contract = json.loads((pre_run_dir / "pre-run-contract.json").read_text(encoding="utf-8"))
    pre_run_contract_sha256 = hashlib.sha256((pre_run_dir / "pre-run-contract.json").read_bytes()).hexdigest()

    output_dir = write_generic_eval_suite_reports(suite, output_root=tmp_path, run_name="auto")

    timeline = json.loads((output_dir / "failures" / "targeted-repair-001.timeline.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "failures" / "targeted-repair-001.timeline.md").read_text(encoding="utf-8")
    assert timeline["run_metadata"]["pre_run_contract_path"] == str(output_dir / "pre-run-contract.json")
    assert timeline["run_metadata"]["pre_run_contract_sha256"] == pre_run_contract_sha256
    assert timeline["run_metadata"]["pre_run_provenance_hash"] == pre_run_contract["provenance_hash"]
    assert timeline["run_metadata"]["provenance_hash"]
    assert "Pre-run provenance hash:" in markdown


def test_generic_eval_suite_manifest_records_failed_tasks():
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="ok",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            ),
            EvalResult(
                task_id="bad",
                success=False,
                status="blocked",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            ),
        ],
        metadata={"suite": "custom"},
    )

    manifest = generic_eval_suite_manifest(suite, run_name="manual")

    assert manifest["suite"] == "custom"
    assert manifest["passed"] == 1
    assert manifest["failed"] == 1
    assert manifest["failed_tasks"] == ["bad"]
    assert manifest["summary"]["task_count"] == 2
