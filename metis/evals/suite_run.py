"""Generic eval suite loading, execution, and report writing."""

from __future__ import annotations

import json
import os
import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from metis.evidence.ledger import EvidenceLedger
from metis.evals.attestation import write_run_attestation
from metis.quality.runner import QualityGateRunner
from metis.evals.provenance import eval_provenance_hash, eval_provenance_payload, tool_inventory_hash
from metis.evals.runner import (
    EvalRunner,
    EvalSuiteResult,
    EvalTaskSpec,
    annotate_failure_timelines,
    load_eval_task_specs,
    load_versioned_eval_suite_payload,
)
from metis.evals.suite_validation import suite_schema_snapshot_metadata, validate_eval_suite
from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.profiles import PROFILES
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


def generic_eval_env_configured() -> bool:
    return bool(os.getenv("METIS_BASE_URL") and os.getenv("METIS_API_KEY") and os.getenv("METIS_MODEL"))


def generic_eval_suite_requires_model_execution(suite_path: str | Path) -> bool:
    return any(task.requires_model_execution for task in load_eval_task_specs(suite_path))


def generic_eval_validation_context(*, workspace: str | Path = ".") -> dict[str, Any]:
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))
    quality_runner = QualityGateRunner()
    return {
        "available_tools": set(registry.list_tools()),
        "available_quality_gates": set(quality_runner.gates),
        "tool_schemas": {spec.name: spec.parameters for spec in registry.iter_specs()},
    }


def generic_eval_tool_inventory(*, workspace: str | Path = ".") -> dict[str, Any]:
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))
    tools = []
    for spec in sorted(registry.iter_specs(), key=lambda item: item.name):
        tools.append(
            {
                "name": spec.name,
                "description": spec.description,
                "category": spec.category,
                "side_effect": spec.side_effect,
                "permission_level": spec.permission_level,
                "requires_permission": spec.requires_permission,
                "retry_policy": spec.retry_policy,
                "verification": spec.verification,
                "metadata": spec.metadata,
                "parameters": spec.parameters,
            }
        )
    return {
        "workspace": str(workspace),
        "tool_count": len(tools),
        "tools": tools,
    }


def generic_eval_tool_inventory_hash(*, workspace: str | Path = ".") -> str:
    return tool_inventory_hash(generic_eval_tool_inventory(workspace=workspace))


def generic_eval_quality_gate_inventory() -> dict[str, Any]:
    quality_runner = QualityGateRunner()
    gates = []
    for spec in sorted(quality_runner.gates.values(), key=lambda item: item.name):
        gates.append(
            {
                "name": spec.name,
                "description": spec.description,
                "failure_policy": spec.failure_policy,
                "metadata": spec.metadata,
            }
        )
    return {
        "gate_count": len(gates),
        "quality_gates": gates,
    }


def tool_inventory_to_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Metis Eval Tool Inventory",
        "",
        f"Workspace: {inventory.get('workspace', '')}",
        f"Tool count: {inventory.get('tool_count', 0)}",
        "",
    ]
    if not inventory.get("tools"):
        lines.append("- None")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| Tool | Category | Side Effect | Permission | Requires Permission | Description |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for tool in inventory["tools"]:
        lines.append(
            "| "
            f"{tool.get('name', '')} | "
            f"{tool.get('category', '')} | "
            f"{tool.get('side_effect', '')} | "
            f"{tool.get('permission_level', '')} | "
            f"{tool.get('requires_permission', False)} | "
            f"{_markdown_cell(tool.get('description', ''))} |"
        )
    return "\n".join(lines) + "\n"


def quality_gate_inventory_to_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Metis Eval Quality Gate Inventory",
        "",
        f"Gate count: {inventory.get('gate_count', 0)}",
        "",
    ]
    if not inventory.get("quality_gates"):
        lines.append("- None")
        return "\n".join(lines) + "\n"
    lines.extend(["| Gate | Failure Policy | Description |", "|---|---|---|"])
    for gate in inventory["quality_gates"]:
        lines.append(
            "| "
            f"{gate.get('name', '')} | "
            f"{gate.get('failure_policy', '')} | "
            f"{_markdown_cell(gate.get('description', ''))} |"
        )
    return "\n".join(lines) + "\n"


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def load_eval_suite_payload(path: str | Path) -> dict[str, Any]:
    return load_versioned_eval_suite_payload(path)


def eval_suite_name(path: str | Path, payload: dict[str, Any] | None = None) -> str:
    payload = payload or load_eval_suite_payload(path)
    name = payload.get("suite") or payload.get("name")
    if isinstance(name, str) and name:
        return name
    return _resolve_suite_path(path).stem


def generic_eval_suite_metadata(
    *,
    suite_path: str | Path,
    tasks: list[EvalTaskSpec],
    profile: str = "small",
    payload: dict[str, Any] | None = None,
    workspace: str | Path = ".",
) -> dict[str, Any]:
    payload = payload or load_eval_suite_payload(suite_path)
    return {
        "suite": eval_suite_name(suite_path, payload),
        "suite_path": str(_resolve_suite_path(suite_path)),
        "schema_version": payload.get("schema_version", "unversioned"),
        **suite_schema_snapshot_metadata(),
        "task_count": len(tasks),
        "model": os.getenv("METIS_MODEL", ""),
        "base_url": os.getenv("METIS_BASE_URL", ""),
        "profile": profile,
        "tool_inventory_hash": generic_eval_tool_inventory_hash(workspace=workspace),
    }


def build_generic_eval_runner(*, workspace: str | Path = ".", profile: str = "small") -> EvalRunner:
    if profile not in PROFILES:
        raise ValueError(f"Unknown model profile: {profile}")
    workspace = Path(workspace)
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))
    state = SQLiteStateStore(workspace / ".metis" / "generic-eval-suite-state.db")
    evidence_ledger = EvidenceLedger(state)
    loop = AgentLoop(
        provider=OpenAICompatibleProvider(),
        registry=registry,
        workspace=str(workspace),
        state=state,
        evidence_ledger=evidence_ledger,
        profile=profile,
    )
    return EvalRunner(loop=loop, evidence_ledger=evidence_ledger)


async def run_generic_eval_suite(
    *,
    suite_path: str | Path,
    workspace: str | Path = ".",
    profile: str = "small",
) -> EvalSuiteResult:
    validation = validate_eval_suite(suite_path, **generic_eval_validation_context(workspace=workspace))
    if not validation["valid"]:
        first_error = validation["errors"][0]["message"] if validation["errors"] else "invalid suite"
        raise ValueError(f"Invalid eval suite: {first_error}")
    payload = load_eval_suite_payload(suite_path)
    tasks = load_eval_task_specs(suite_path)
    runner = build_generic_eval_runner(workspace=workspace, profile=profile)
    return await runner.run_suite(
        tasks,
        metadata=generic_eval_suite_metadata(
            suite_path=suite_path,
            tasks=tasks,
            profile=profile,
            payload=payload,
            workspace=workspace,
        ),
    )


def generate_eval_run_name(*, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")


def resolve_eval_run_name(run_name: str = "auto", *, now: datetime | None = None) -> str:
    if run_name.lower() in {"auto", "timestamp", "timestamped"}:
        return generate_eval_run_name(now=now)
    return run_name


def generic_eval_runs_root(*, output_root: str | Path = ".") -> Path:
    return Path(output_root) / "docs" / "evals" / "runs"


def generic_eval_report_dir(*, output_root: str | Path = ".", run_name: str = "auto") -> Path:
    return generic_eval_runs_root(output_root=output_root) / resolve_eval_run_name(run_name)


def generic_eval_pre_run_contract(
    *,
    suite_path: str | Path,
    workspace: str | Path = ".",
    profile: str = "small",
    run_name: str = "auto",
    requested_run_name: str | None = None,
) -> dict[str, Any]:
    payload = load_eval_suite_payload(suite_path)
    tasks = load_eval_task_specs(suite_path)
    metadata = generic_eval_suite_metadata(
        suite_path=suite_path,
        tasks=tasks,
        profile=profile,
        payload=payload,
        workspace=workspace,
    )
    task_specs = {task.id: task for task in tasks}
    contract_suite = EvalSuiteResult(results=[], metadata=metadata, task_specs=task_specs)
    suite_name = str(metadata.get("suite") or "custom-eval-suite")
    provenance = _eval_run_provenance(contract_suite, suite_name=suite_name)
    task_spec_hash_summary = contract_suite.task_spec_hash_summary()
    return {
        "artifact_type": "generic-eval-pre-run-contract",
        "suite": suite_name,
        "suite_path": str(_resolve_suite_path(suite_path)),
        "schema_version": metadata.get("schema_version", "unversioned"),
        "run_name": run_name,
        "requested_run_name": requested_run_name or run_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace": str(workspace),
        "profile": profile,
        "metadata": metadata,
        "task_count": len(tasks),
        "task_contract_hash": contract_suite.task_contract_hash(),
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
        "# Metis Generic Eval Pre-run Contract",
        "",
        f"Run: {contract.get('run_name', '')}",
        f"Requested run name: {contract.get('requested_run_name', '')}",
        f"Suite: {contract.get('suite', '')}",
        f"Suite path: {contract.get('suite_path', '')}",
        f"Schema version: {contract.get('schema_version', '')}",
        f"Profile: {contract.get('profile', '')}",
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


def write_generic_eval_pre_run_contract(
    *,
    suite_path: str | Path,
    workspace: str | Path = ".",
    output_root: str | Path = ".",
    profile: str = "small",
    run_name: str = "auto",
    requested_run_name: str | None = None,
) -> Path:
    output_dir = generic_eval_runs_root(output_root=output_root) / run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    contract = generic_eval_pre_run_contract(
        suite_path=suite_path,
        workspace=workspace,
        profile=profile,
        run_name=run_name,
        requested_run_name=requested_run_name,
    )
    (output_dir / "pre-run-contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "pre-run-contract.md").write_text(pre_run_contract_to_markdown(contract), encoding="utf-8")
    return output_dir


def write_generic_eval_suite_reports(
    suite: EvalSuiteResult,
    *,
    output_root: str | Path = ".",
    run_name: str = "auto",
) -> Path:
    requested_run_name = run_name
    run_name = resolve_eval_run_name(run_name)
    output_dir = generic_eval_runs_root(output_root=output_root) / run_name
    suite.write_reports(output_dir)
    pre_run_evidence = _pre_run_contract_evidence(output_dir)
    manifest = generic_eval_suite_manifest(
        suite,
        run_name=run_name,
        requested_run_name=requested_run_name,
        pre_run_contract_evidence=pre_run_evidence,
    )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    annotate_failure_timelines(output_dir, manifest)
    write_run_attestation(output_dir, manifest=manifest)
    write_generic_eval_latest_pointer(
        suite,
        output_root=output_root,
        run_name=run_name,
        pre_run_contract_evidence=pre_run_evidence,
    )
    return output_dir


def generic_eval_suite_manifest(
    suite: EvalSuiteResult,
    *,
    run_name: str,
    requested_run_name: str | None = None,
    pre_run_contract_evidence: dict[str, str] | None = None,
) -> dict[str, Any]:
    passed = sum(1 for result in suite.results if result.success)
    failed = len(suite.results) - passed
    suite_name = str(suite.metadata.get("suite") or "custom-eval-suite")
    provenance = _eval_run_provenance(suite, suite_name=suite_name)
    pre_run_contract_evidence = pre_run_contract_evidence or {}
    return {
        "suite": suite_name,
        "run_name": run_name,
        "requested_run_name": requested_run_name or run_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "success_rate": suite.success_rate,
        "task_count": len(suite.results),
        "passed": passed,
        "failed": failed,
        "summary": suite.summary,
        "metadata": suite.metadata,
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


def write_generic_eval_latest_pointer(
    suite: EvalSuiteResult,
    *,
    output_root: str | Path = ".",
    run_name: str,
    pre_run_contract_evidence: dict[str, str] | None = None,
) -> Path:
    pointer_path = generic_eval_runs_root(output_root=output_root) / "latest.json"
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    provenance = _eval_run_provenance(suite, suite_name=str(suite.metadata.get("suite", "custom-eval-suite")))
    pre_run_contract_evidence = pre_run_contract_evidence or _pre_run_contract_evidence(
        generic_eval_runs_root(output_root=output_root) / run_name
    )
    pointer = {
        "suite": suite.metadata.get("suite", "custom-eval-suite"),
        "latest_run_name": run_name,
        "latest_run_dir": str(generic_eval_runs_root(output_root=output_root) / run_name),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "success_rate": suite.success_rate,
        "task_count": len(suite.results),
        "summary": suite.summary,
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


def _eval_run_provenance(suite: EvalSuiteResult, *, suite_name: str) -> dict[str, str]:
    return eval_provenance_payload(
        suite=suite_name,
        suite_definition_type=str(suite.metadata.get("suite_definition_type", "")),
        schema_version=str(suite.metadata.get("schema_version", "")),
        suite_schema_sha256=str(suite.metadata.get("suite_schema_sha256", "")),
        task_contract_hash=suite.task_contract_hash(),
        model=str(suite.metadata.get("model", "")),
        base_url=str(suite.metadata.get("base_url", "")),
        profile=str(suite.metadata.get("profile", "")),
        tool_inventory_hash_value=str(suite.metadata.get("tool_inventory_hash", "")),
    )


async def run_and_write_generic_eval_suite(
    *,
    suite_path: str | Path,
    workspace: str | Path = ".",
    output_root: str | Path = ".",
    run_name: str = "auto",
    profile: str = "small",
) -> tuple[EvalSuiteResult, Path]:
    requested_run_name = run_name
    run_name = resolve_eval_run_name(run_name)
    write_generic_eval_pre_run_contract(
        suite_path=suite_path,
        workspace=workspace,
        output_root=output_root,
        profile=profile,
        run_name=run_name,
        requested_run_name=requested_run_name,
    )
    suite = await run_generic_eval_suite(suite_path=suite_path, workspace=workspace, profile=profile)
    output_dir = write_generic_eval_suite_reports(suite, output_root=output_root, run_name=run_name)
    return suite, output_dir


def _resolve_suite_path(path: str | Path) -> Path:
    suite_path = Path(path)
    if suite_path.is_dir():
        suite_path = suite_path / "targeted-eval-suite.json"
    if not suite_path.exists():
        raise FileNotFoundError(f"Missing eval suite: {suite_path}")
    return suite_path
