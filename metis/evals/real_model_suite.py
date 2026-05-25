"""Real small-model eval suite definitions and runner helpers."""

from __future__ import annotations

import hashlib
import os
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metis.evidence.ledger import EvidenceLedger
from metis.evals.attestation import write_run_attestation
from metis.evals.provenance import eval_provenance_hash, eval_provenance_payload
from metis.evals.runner import EvalRunner, EvalSuiteResult, EvalTaskSpec, annotate_failure_timelines
from metis.evals.suite_run import generic_eval_tool_inventory_hash
from metis.evals.suite_validation import suite_schema_snapshot_metadata
from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.loop import AgentLoop
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


def real_model_env_configured() -> bool:
    return bool(os.getenv("METIS_BASE_URL") and os.getenv("METIS_API_KEY") and os.getenv("METIS_MODEL"))


def _strict_gate_kwargs() -> dict:
    return {
        "max_invalid_tool_calls": 0,
        "max_schema_violations": 0,
        "max_retry_budget_exhaustions": 0,
        "max_pre_dispatch_blocks": 0,
    }


def real_small_model_eval_tasks() -> list[EvalTaskSpec]:
    return [
        EvalTaskSpec(
            id="strict-final-no-tools",
            prompt=(
                "Return only the strict final JSON for a completed no-tool task. "
                "Summary: Metis can run strict output checks."
            ),
            max_turns=2,
            **_strict_gate_kwargs(),
        ),
        EvalTaskSpec(
            id="read-then-summarize",
            prompt=(
                "Use read_file to read README.md, then return strict final JSON. "
                "The summary must mention Metis."
            ),
            allowed_tools=["read_file"],
            max_turns=4,
            required_tools=["read_file"],
            forbidden_tools=["write_file", "run_shell", "run_command", "run_test"],
            required_tool_arguments=[{"tool": "read_file", "arguments": {"path": "README.md"}}],
            **_strict_gate_kwargs(),
        ),
        EvalTaskSpec(
            id="safe-command",
            prompt=(
                "Use run_command to execute a harmless Python version check, then return strict final JSON. "
                "Do not use run_shell."
            ),
            allowed_tools=["run_command"],
            max_turns=4,
            required_tools=["run_command"],
            forbidden_tools=["run_shell"],
            required_tool_arguments=[
                {"tool": "run_command", "arguments": {"command": {"contains": "python"}}},
            ],
            **_strict_gate_kwargs(),
            max_failure_shape_key_counts={"python pytest": 0},
        ),
        EvalTaskSpec(
            id="write-report-file",
            prompt=(
                "Use write_file to create outputs/real-model-report.md with a short Metis harness summary, "
                "then return strict final JSON. Do not use command tools."
            ),
            allowed_tools=["write_file"],
            max_turns=4,
            required_tools=["write_file"],
            forbidden_tools=["read_file", "run_shell", "run_command", "run_test"],
            required_tool_arguments=[
                {"tool": "write_file", "arguments": {"path": "outputs/real-model-report.md"}},
            ],
            **_strict_gate_kwargs(),
        ),
        EvalTaskSpec(
            id="read-then-write-summary",
            prompt=(
                "Use read_file to read README.md, then use write_file to create outputs/readme-summary.md. "
                "Return strict final JSON after both tool calls succeed."
            ),
            allowed_tools=["read_file", "write_file"],
            max_turns=6,
            required_tools=["read_file", "write_file"],
            forbidden_tools=["run_shell", "run_command", "run_test"],
            required_tool_order=["read_file", "write_file"],
            required_tool_arguments=[
                {"tool": "read_file", "arguments": {"path": "README.md"}},
                {"tool": "write_file", "arguments": {"path": "outputs/readme-summary.md"}},
            ],
            **_strict_gate_kwargs(),
        ),
        EvalTaskSpec(
            id="forbidden-shell-readme",
            prompt=(
                "Summarize README.md using only read_file. Do not use shell, command, test, or write tools. "
                "Return strict final JSON."
            ),
            allowed_tools=["read_file"],
            max_turns=4,
            required_tools=["read_file"],
            forbidden_tools=["run_shell", "run_command", "run_test", "write_file"],
            required_tool_arguments=[{"tool": "read_file", "arguments": {"path": "README.md"}}],
            **_strict_gate_kwargs(),
        ),
        EvalTaskSpec(
            id="schema-repair-write-file",
            prompt=(
                "This is a schema repair test. First call write_file incorrectly with only content and no path. "
                "After the runtime returns schema_validation_failed, retry write_file correctly with "
                "path outputs/schema-repair.md and content. Then return strict final JSON."
            ),
            allowed_tools=["write_file"],
            max_turns=6,
            required_tools=["write_file"],
            forbidden_tools=["read_file", "run_shell", "run_command", "run_test"],
            required_tool_arguments=[
                {"tool": "write_file", "arguments": {"path": "outputs/schema-repair.md"}},
            ],
            min_schema_repair_successes=1,
            max_schema_repair_failures=0,
            allow_recovered_schema_failures=True,
            max_retry_budget_exhaustions=0,
            max_pre_dispatch_blocks=0,
        ),
        EvalTaskSpec(
            id="command-schema-repair",
            prompt=(
                "This is a command schema repair test. First call run_command with command ['python', '--version'] "
                "and timeout set to the string 'fast'. After schema_validation_failed, retry with integer timeout 30. "
                "Do not use run_shell. Return strict final JSON."
            ),
            allowed_tools=["run_command"],
            max_turns=6,
            required_tools=["run_command"],
            forbidden_tools=["run_shell", "read_file", "write_file", "run_test"],
            required_tool_arguments=[
                {"tool": "run_command", "arguments": {"command": {"contains": "python"}, "timeout": 30}},
            ],
            min_schema_repair_successes=1,
            max_schema_repair_failures=0,
            allow_recovered_schema_failures=True,
            max_retry_budget_exhaustions=0,
            max_pre_dispatch_blocks=0,
            max_failure_shape_key_counts={"python pytest": 0},
        ),
        EvalTaskSpec(
            id="safe-test-command",
            prompt=(
                "Use run_test to execute a harmless pytest collection/version style command: "
                "python -m pytest --version. Do not use run_shell. Return strict final JSON."
            ),
            allowed_tools=["run_test"],
            max_turns=5,
            required_tools=["run_test"],
            forbidden_tools=["run_shell", "run_command", "read_file", "write_file"],
            required_tool_arguments=[
                {"tool": "run_test", "arguments": {"command": {"contains": "pytest"}}},
            ],
            **_strict_gate_kwargs(),
            max_failure_shape_key_counts={"python pytest": 0},
        ),
        EvalTaskSpec(
            id="verified-test-evidence",
            prompt=(
                "Use run_test to execute ['python', '-m', 'pytest', '--version']. "
                "The tool response will include evidence_refs. Return strict final JSON with status done and include "
                "the evidence_refs from the tool response. Do not use run_shell."
            ),
            allowed_tools=["run_test"],
            max_turns=5,
            required_tools=["run_test"],
            forbidden_tools=["run_shell", "run_command", "read_file", "write_file"],
            required_tool_arguments=[
                {"tool": "run_test", "arguments": {"command": {"contains": "pytest"}}},
            ],
            required_evidence_sources=["test"],
            require_verified_final=True,
            **_strict_gate_kwargs(),
            max_failure_shape_key_counts={"python pytest": 0},
        ),
        EvalTaskSpec(
            id="verified-write-evidence",
            prompt=(
                "Use write_file to create outputs/verified-write.md with a concise Metis harness note. "
                "The tool response will include evidence_refs. Return strict final JSON with status done and include "
                "the evidence_refs from the write_file tool response. Do not use command tools."
            ),
            allowed_tools=["write_file"],
            max_turns=5,
            required_tools=["write_file"],
            forbidden_tools=["read_file", "run_shell", "run_command", "run_test"],
            required_tool_arguments=[
                {"tool": "write_file", "arguments": {"path": "outputs/verified-write.md"}},
            ],
            required_evidence_sources=["tool_output"],
            require_verified_final=True,
            **_strict_gate_kwargs(),
        ),
        EvalTaskSpec(
            id="verified-read-write-report-evidence",
            prompt=(
                "Use read_file to read README.md, then use write_file to create "
                "outputs/verified-read-write-report.md with a concise Metis harness report. "
                "The write_file tool response will include evidence_refs. Return strict final JSON with status done "
                "and include the evidence_refs from the write_file tool response. Do not use command tools."
            ),
            allowed_tools=["read_file", "write_file"],
            max_turns=7,
            required_tools=["read_file", "write_file"],
            forbidden_tools=["run_shell", "run_command", "run_test"],
            required_tool_order=["read_file", "write_file"],
            required_tool_arguments=[
                {"tool": "read_file", "arguments": {"path": "README.md"}},
                {"tool": "write_file", "arguments": {"path": "outputs/verified-read-write-report.md"}},
            ],
            required_evidence_sources=["tool_output"],
            require_verified_final=True,
            **_strict_gate_kwargs(),
        ),
    ]


def real_small_model_eval_metadata(*, workspace: str | Path = ".") -> dict[str, str | int]:
    return {
        "suite": "real-small-model",
        "suite_definition_type": "code-defined-builtin",
        "schema_version": "code-defined",
        **suite_schema_snapshot_metadata(),
        "task_count": len(real_small_model_eval_tasks()),
        "model": os.getenv("METIS_MODEL", ""),
        "base_url": os.getenv("METIS_BASE_URL", ""),
        "profile": "small",
        "tool_inventory_hash": generic_eval_tool_inventory_hash(workspace=workspace),
    }


def build_real_small_model_eval_runner(*, workspace: str | Path = ".") -> EvalRunner:
    workspace = Path(workspace)
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))
    state = SQLiteStateStore(workspace / ".metis" / "real-model-eval-state.db")
    evidence_ledger = EvidenceLedger(state)
    loop = AgentLoop(
        provider=OpenAICompatibleProvider(),
        registry=registry,
        workspace=str(workspace),
        state=state,
        evidence_ledger=evidence_ledger,
        profile="small",
    )
    return EvalRunner(loop=loop, evidence_ledger=evidence_ledger)


async def run_real_small_model_eval_suite(*, workspace: str | Path = ".") -> EvalSuiteResult:
    runner = build_real_small_model_eval_runner(workspace=workspace)
    return await runner.run_suite(real_small_model_eval_tasks(), metadata=real_small_model_eval_metadata(workspace=workspace))


def generate_real_small_model_eval_run_name(*, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")


def resolve_real_small_model_eval_run_name(run_name: str = "latest", *, now: datetime | None = None) -> str:
    if run_name.lower() in {"auto", "timestamp", "timestamped"}:
        return generate_real_small_model_eval_run_name(now=now)
    return run_name


def real_small_model_eval_runs_root(*, output_root: str | Path = ".") -> Path:
    return Path(output_root) / "docs" / "evals" / "runs"


def real_small_model_eval_report_dir(*, output_root: str | Path = ".", run_name: str = "latest") -> Path:
    return real_small_model_eval_runs_root(output_root=output_root) / run_name


def real_small_model_eval_latest_pointer_path(*, output_root: str | Path = ".") -> Path:
    return real_small_model_eval_runs_root(output_root=output_root) / "latest.json"


def real_small_model_pre_run_contract(
    *,
    workspace: str | Path = ".",
    run_name: str = "latest",
    requested_run_name: str | None = None,
) -> dict[str, Any]:
    tasks = real_small_model_eval_tasks()
    metadata = real_small_model_eval_metadata(workspace=workspace)
    task_specs = {task.id: task for task in tasks}
    contract_suite = EvalSuiteResult(results=[], metadata=metadata, task_specs=task_specs)
    task_spec_hash_summary = contract_suite.task_spec_hash_summary()
    task_contract_hash = contract_suite.task_contract_hash()
    provenance = eval_provenance_payload(
        suite="real-small-model",
        suite_definition_type=str(metadata.get("suite_definition_type", "code-defined-builtin")),
        schema_version=str(metadata.get("schema_version", "code-defined")),
        suite_schema_sha256=str(metadata.get("suite_schema_sha256", "")),
        task_contract_hash=task_contract_hash,
        model=str(metadata.get("model", "")),
        base_url=str(metadata.get("base_url", "")),
        profile=str(metadata.get("profile", "")),
        tool_inventory_hash_value=str(metadata.get("tool_inventory_hash", "")),
    )
    return {
        "artifact_type": "real-small-model-pre-run-contract",
        "suite": "real-small-model",
        "suite_definition_type": metadata.get("suite_definition_type", "code-defined-builtin"),
        "schema_version": metadata.get("schema_version", "code-defined"),
        "run_name": run_name,
        "requested_run_name": requested_run_name or run_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "metadata": metadata,
        "task_count": len(tasks),
        "task_contract_hash": task_contract_hash,
        "task_spec_hash_summary": task_spec_hash_summary,
        "task_specs": [
            {
                "task_id": task.id,
                "task_spec": asdict(task),
                "task_spec_hashes": task_spec_hash_summary[task.id],
            }
            for task in tasks
        ],
        "provenance": provenance,
        "provenance_hash": eval_provenance_hash(provenance),
    }


def pre_run_contract_to_markdown(contract: dict[str, Any]) -> str:
    lines = [
        "# Metis Real Small-Model Pre-run Contract",
        "",
        f"Run: {contract.get('run_name', '')}",
        f"Requested run name: {contract.get('requested_run_name', '')}",
        f"Suite: {contract.get('suite', '')}",
        f"Suite definition type: {contract.get('suite_definition_type', '')}",
        f"Schema version: {contract.get('schema_version', '')}",
        f"Task count: {contract.get('task_count', 0)}",
        f"Task contract hash: {contract.get('task_contract_hash', '')}",
        f"Provenance hash: {contract.get('provenance_hash', '')}",
        "",
        "## Tasks",
        "",
    ]
    task_specs = contract.get("task_specs", [])
    if not task_specs:
        lines.append("- None")
    else:
        lines.extend(
            f"- {task.get('task_id', '')}: {task.get('task_spec_hashes', {}).get('task_spec_hash', '')}"
            for task in task_specs
            if isinstance(task, dict)
        )
    return "\n".join(lines) + "\n"


def write_real_small_model_pre_run_contract(
    *,
    workspace: str | Path = ".",
    output_root: str | Path = ".",
    run_name: str = "latest",
    requested_run_name: str | None = None,
) -> Path:
    output_dir = real_small_model_eval_report_dir(output_root=output_root, run_name=run_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = real_small_model_pre_run_contract(
        workspace=workspace,
        run_name=run_name,
        requested_run_name=requested_run_name,
    )
    (output_dir / "pre-run-contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "pre-run-contract.md").write_text(pre_run_contract_to_markdown(contract), encoding="utf-8")
    return output_dir


def write_real_small_model_eval_reports(
    suite: EvalSuiteResult,
    *,
    output_root: str | Path = ".",
    run_name: str = "latest",
) -> Path:
    requested_run_name = run_name
    run_name = resolve_real_small_model_eval_run_name(run_name)
    output_dir = real_small_model_eval_report_dir(output_root=output_root, run_name=run_name)
    suite.write_reports(output_dir)
    pre_run_evidence = _pre_run_contract_evidence(output_dir)
    manifest = real_small_model_eval_manifest(
        suite,
        run_name=run_name,
        requested_run_name=requested_run_name,
        pre_run_contract_evidence=pre_run_evidence,
    )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    annotate_failure_timelines(output_dir, manifest)
    write_run_attestation(output_dir, manifest=manifest)
    write_real_small_model_eval_latest_pointer(
        suite,
        output_root=output_root,
        run_name=run_name,
        pre_run_contract_evidence=pre_run_evidence,
    )
    return output_dir


def real_small_model_eval_manifest(
    suite: EvalSuiteResult,
    *,
    run_name: str = "latest",
    requested_run_name: str | None = None,
    pre_run_contract_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    passed = sum(1 for result in suite.results if result.success)
    failed = len(suite.results) - passed
    provenance = _real_small_model_eval_provenance(suite)
    pre_run_contract_evidence = pre_run_contract_evidence or {}
    return {
        "suite": "real-small-model",
        "run_name": run_name,
        "requested_run_name": requested_run_name or run_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success_rate": suite.success_rate,
        "task_count": len(suite.results),
        "passed": passed,
        "failed": failed,
        "summary": suite.summary,
        "metadata": suite.metadata,
        "suite_definition_type": suite.metadata.get("suite_definition_type", "code-defined-builtin"),
        "schema_version": suite.metadata.get("schema_version", "code-defined"),
        "suite_schema_id": suite.metadata.get("suite_schema_id", ""),
        "suite_schema_path": suite.metadata.get("suite_schema_path", ""),
        "suite_schema_sha256": suite.metadata.get("suite_schema_sha256", ""),
        "task_contract_hash": suite.task_contract_hash(),
        "task_spec_hash_summary": suite.task_spec_hash_summary(),
        "provenance": provenance,
        "provenance_hash": eval_provenance_hash(provenance),
        "pre_run_contract_path": pre_run_contract_evidence.get("pre_run_contract_path", ""),
        "pre_run_contract_sha256": pre_run_contract_evidence.get("pre_run_contract_sha256", ""),
        "pre_run_provenance_hash": pre_run_contract_evidence.get("pre_run_provenance_hash", ""),
        "failed_tasks": [result.task_id for result in suite.results if not result.success],
    }


def write_real_small_model_eval_latest_pointer(
    suite: EvalSuiteResult,
    *,
    output_root: str | Path = ".",
    run_name: str,
    pre_run_contract_evidence: dict[str, str] | None = None,
) -> Path:
    pointer_path = real_small_model_eval_latest_pointer_path(output_root=output_root)
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    provenance = _real_small_model_eval_provenance(suite)
    pre_run_contract_evidence = pre_run_contract_evidence or _pre_run_contract_evidence(
        real_small_model_eval_report_dir(output_root=output_root, run_name=run_name)
    )
    pointer = {
        "suite": "real-small-model",
        "latest_run_name": run_name,
        "latest_run_dir": str(real_small_model_eval_report_dir(output_root=output_root, run_name=run_name)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "success_rate": suite.success_rate,
        "task_count": len(suite.results),
        "summary": suite.summary,
        "suite_definition_type": suite.metadata.get("suite_definition_type", "code-defined-builtin"),
        "schema_version": suite.metadata.get("schema_version", "code-defined"),
        "suite_schema_id": suite.metadata.get("suite_schema_id", ""),
        "suite_schema_sha256": suite.metadata.get("suite_schema_sha256", ""),
        "task_contract_hash": suite.task_contract_hash(),
        "task_spec_hash_summary": suite.task_spec_hash_summary(),
        "provenance": provenance,
        "provenance_hash": eval_provenance_hash(provenance),
        "pre_run_contract_path": pre_run_contract_evidence.get("pre_run_contract_path", ""),
        "pre_run_contract_sha256": pre_run_contract_evidence.get("pre_run_contract_sha256", ""),
        "pre_run_provenance_hash": pre_run_contract_evidence.get("pre_run_provenance_hash", ""),
    }
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")
    return pointer_path


def _pre_run_contract_evidence(run_dir: Path) -> dict[str, str]:
    contract_path = run_dir / "pre-run-contract.json"
    evidence = {
        "pre_run_contract_path": str(contract_path),
        "pre_run_contract_sha256": "",
        "pre_run_provenance_hash": "",
    }
    if not contract_path.exists():
        return evidence
    raw = contract_path.read_bytes()
    evidence["pre_run_contract_sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        contract = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return evidence
    provenance_hash = contract.get("provenance_hash")
    if isinstance(provenance_hash, str):
        evidence["pre_run_provenance_hash"] = provenance_hash
    return evidence


def _real_small_model_eval_provenance(suite: EvalSuiteResult) -> dict[str, str]:
    return eval_provenance_payload(
        suite="real-small-model",
        suite_definition_type=str(suite.metadata.get("suite_definition_type", "code-defined-builtin")),
        schema_version=str(suite.metadata.get("schema_version", "code-defined")),
        suite_schema_sha256=str(suite.metadata.get("suite_schema_sha256", "")),
        task_contract_hash=suite.task_contract_hash(),
        model=str(suite.metadata.get("model", "")),
        base_url=str(suite.metadata.get("base_url", "")),
        profile=str(suite.metadata.get("profile", "")),
        tool_inventory_hash_value=str(suite.metadata.get("tool_inventory_hash", "")),
    )


async def run_and_write_real_small_model_eval_suite(
    *,
    workspace: str | Path = ".",
    output_root: str | Path = ".",
    run_name: str = "latest",
) -> EvalSuiteResult:
    requested_run_name = run_name
    run_name = resolve_real_small_model_eval_run_name(run_name)
    write_real_small_model_pre_run_contract(
        workspace=workspace,
        output_root=output_root,
        run_name=run_name,
        requested_run_name=requested_run_name,
    )
    suite = await run_real_small_model_eval_suite(workspace=workspace)
    write_real_small_model_eval_reports(suite, output_root=output_root, run_name=run_name)
    return suite
