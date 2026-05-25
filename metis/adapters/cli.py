"""Minimal CLI adapter."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from metis.app.manifest import load_app_manifest, write_default_app_manifest
from metis.app.runtime import (
    build_runtime_messages,
    build_runtime_prompt_stack,
    build_runtime_task_contract,
    manifest_allowed_tool_permissions,
)
from metis.app.tui import run_tui_sync
from metis.app.web import create_app
from metis.develop.workflow import build_development_package, infer_app_name, write_development_package
from metis.evals.compare import (
    build_eval_stubs_from_repair_tasks,
    build_repair_plan,
    compare_eval_runs,
    diagnose_eval_comparison,
    eval_stubs_to_markdown,
    eval_run_comparison_to_markdown,
    eval_suite_to_markdown,
    load_repair_tasks,
    materialize_eval_suite,
    plan_repairs,
    repair_plan_to_markdown,
    repair_tasks_to_markdown,
    write_eval_run_comparison,
    write_eval_stubs,
    write_materialized_eval_suite,
    write_repair_plan,
)
from metis.evidence.ledger import EvidenceLedger
from metis.evals.attestation import (
    verify_repair_execute_preflight_attestation,
    verify_repair_plan_attestation,
    verify_targeted_eval_stubs_attestation,
    verify_targeted_eval_suite_attestation,
    write_repair_execute_preflight_attestation,
)
from metis.evals.gate import (
    eval_gate_to_markdown,
    evaluate_eval_run_gate,
    write_eval_gate_report,
)
from metis.evals.real_model_suite import (
    real_model_env_configured,
    real_small_model_eval_latest_pointer_path,
    resolve_real_small_model_eval_run_name,
    run_real_small_model_eval_suite,
    write_real_small_model_pre_run_contract,
    write_real_small_model_eval_reports,
)
from metis.evals.suite_run import (
    generic_eval_env_configured,
    generic_eval_quality_gate_inventory,
    generic_eval_suite_requires_model_execution,
    generic_eval_tool_inventory,
    generic_eval_validation_context,
    quality_gate_inventory_to_markdown,
    resolve_eval_run_name,
    run_generic_eval_suite,
    tool_inventory_to_markdown,
    write_generic_eval_pre_run_contract,
    write_generic_eval_suite_reports,
)
from metis.evals.suite_validation import (
    eval_suite_validation_to_markdown,
    validate_eval_suite,
    write_eval_suite_validation,
)
from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.package_lifecycle import build_package, export_package, install_package, verify_package
from metis.plugins.manager import load_plugin_manifest, validate_plugin_manifest
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.telemetry.timeline import load_timeline, timeline_to_json, timeline_to_markdown
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metis")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="Check runtime configuration")
    run = sub.add_parser("run", help="Run a task through the Metis loop")
    run.add_argument("task")
    run.add_argument("--workspace", default=".")
    run.add_argument("--max-turns", type=int, default=12)
    run.add_argument("--manifest", help="Optional metis-agent.json app manifest")
    run.add_argument("--state-db", help="Optional SQLite state database path")
    run.add_argument("--session-id", default="default", help="Session id used when --state-db is enabled")
    resume = sub.add_parser("resume", help="Resume a persisted Metis session from SQLite state")
    resume.add_argument("--state-db", required=True, help="SQLite state database path")
    resume.add_argument("--session-id", required=True, help="Session id to resume")
    resume.add_argument("--message", required=True, help="New user instruction to append before resuming")
    resume.add_argument("--workspace", default=".")
    resume.add_argument("--max-turns", type=int, default=12)
    resume.add_argument("--manifest", help="Optional metis-agent.json app manifest")
    tui = sub.add_parser("tui", help="Start the reusable Metis terminal UI")
    tui.add_argument("--manifest", help="Optional metis-agent.json app manifest")
    tui.add_argument("--workspace", default=None)
    tui.add_argument("--max-turns", type=int, default=12)
    tui.add_argument("--state-db", help="Optional SQLite state database path")
    web = sub.add_parser("web", help="Start the reusable Metis Web UI")
    web.add_argument("--manifest", help="Optional metis-agent.json app manifest")
    web.add_argument("--workspace", default=None)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8080)
    web.add_argument("--state-db", help="Optional SQLite state database path")
    develop = sub.add_parser("develop", help="Start the Metis developer adaptation workflow")
    develop.add_argument("--request", help="Downstream agent requirement. If omitted, interactive mode asks for it.")
    develop.add_argument("--name", help="Downstream agent display name. If omitted, interactive mode asks for it.")
    develop.add_argument("--output-dir", default="metis-development", help="Directory for reports, plan, and approved artifacts")
    develop.add_argument("--approve", action="store_true", help="Apply approved manifest, prompts, slash commands, and task files")
    develop.add_argument("--json", action="store_true", help="Print package metadata as JSON")
    app_parser = sub.add_parser("app", help="Manage reusable Metis app surfaces")
    app_sub = app_parser.add_subparsers(dest="app_command")
    app_init = app_sub.add_parser("init", help="Create a metis-agent.json app manifest")
    app_init.add_argument("--name", required=True, help="Agent app display name")
    app_init.add_argument("--output", default="metis-agent.json", help="Manifest path to write")
    app_init.add_argument("--workspace", default=".", help="Default workspace for the app")
    app_show = app_sub.add_parser("show", help="Print resolved app manifest")
    app_show.add_argument("--manifest", help="Optional metis-agent.json app manifest")
    app_show.add_argument("--workspace", default=None)
    trace_parser = sub.add_parser("trace", help="Inspect Metis trace artifacts")
    trace_sub = trace_parser.add_subparsers(dest="trace_command")
    trace_show = trace_sub.add_parser("show", help="Render a timeline JSON artifact")
    trace_show.add_argument("--timeline", required=True, help="Timeline JSON path")
    trace_show.add_argument("--json", action="store_true", help="Print normalized JSON instead of markdown")
    trace_show.add_argument("--include-payload", action="store_true", help="Include full event payloads in markdown")
    eval_parser = sub.add_parser("eval", help="Run Metis evaluation suites")
    eval_sub = eval_parser.add_subparsers(dest="eval_suite")
    real_small = eval_sub.add_parser("real-small-model", help="Run the real small-model endpoint eval suite")
    real_small.add_argument("--workspace", default=".")
    real_small.add_argument("--output-root", default=".")
    real_small.add_argument("--run-name", default="auto")
    real_small.add_argument("--gate", action="store_true", help="Run the strict release gate after writing reports")
    real_small.add_argument("--gate-output-dir", help="Directory for gate.json and gate.md")
    real_small.add_argument("--compare-baseline", help="Compare this run against a baseline run directory")
    real_small.add_argument("--compare-latest", action="store_true", help="Compare this run against the previous latest run")
    real_small.add_argument("--compare-output-dir", help="Directory for comparison.json and comparison.md")
    real_small.add_argument(
        "--compare-profile",
        choices=["strict", "release", "exploratory"],
        default="release",
        help="Regression profile for automatic comparison",
    )
    compare = eval_sub.add_parser("compare", help="Compare two eval run directories")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--current", required=True)
    compare.add_argument(
        "--profile",
        choices=["strict", "release", "exploratory"],
        default="release",
        help="Regression profile for deciding the command exit code",
    )
    compare.add_argument("--output-dir")
    compare.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    diagnose = eval_sub.add_parser("diagnose", help="Build repair tasks from a comparison diagnosis")
    diagnose.add_argument("--comparison", required=True, help="Directory containing diagnosis.json")
    diagnose.add_argument("--output-dir", help="Directory for repair-tasks.json and repair-tasks.md")
    diagnose.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    repair_plan = eval_sub.add_parser("repair-plan", help="Build an ordered repair plan from repair tasks")
    repair_plan.add_argument("--repair-tasks", required=True, help="repair-tasks.json file or containing directory")
    repair_plan.add_argument("--output-dir", help="Directory for repair-plan.json and repair-plan.md")
    repair_plan.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    repair_plan.add_argument(
        "--require-executable-phase",
        action="append",
        default=[],
        help="Return non-zero when the named phase is blocked, absent, or not executable",
    )
    verify_repair_plan = eval_sub.add_parser("verify-repair-plan", help="Verify repair-plan attestation artifacts")
    verify_repair_plan.add_argument("--plan-dir", required=True, help="Directory containing repair-plan-attestation.json")
    verify_repair_plan.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    verify_eval_stubs = eval_sub.add_parser("verify-eval-stubs", help="Verify targeted eval stubs attestation artifacts")
    verify_eval_stubs.add_argument("--stubs-dir", required=True, help="Directory containing targeted-eval-stubs-attestation.json")
    verify_eval_stubs.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    verify_targeted_suite = eval_sub.add_parser(
        "verify-targeted-suite",
        help="Verify materialized targeted eval suite attestation artifacts",
    )
    verify_targeted_suite.add_argument(
        "--suite-dir",
        required=True,
        help="Directory containing targeted-eval-suite-attestation.json",
    )
    verify_targeted_suite.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    repair_execute = eval_sub.add_parser("repair-execute", help="Preflight a verified repair execution phase")
    repair_execute.add_argument("--plan-dir", required=True, help="Directory containing repair-plan.json and attestation")
    repair_execute.add_argument("--phase", required=True, help="Repair phase id intended for execution")
    repair_execute.add_argument("--stubs-dir", help="Optional targeted eval stubs directory to verify")
    repair_execute.add_argument("--suite-dir", help="Optional targeted eval suite directory to verify")
    repair_execute.add_argument("--output-dir", help="Directory for repair-execute-preflight.json and .md")
    repair_execute.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    repair_execute.add_argument(
        "--record-attempt-status",
        choices=["in_progress", "blocked", "complete", "verified"],
        help="Persist a repair execution attempt and updated repair-plan snapshot under --output-dir",
    )
    repair_execute.add_argument("--executor-id", default="metis-repair-execute", help="Executor id recorded in attempt artifacts")
    repair_execute.add_argument("--attempt-note", default="", help="Operator or executor note recorded in attempt artifacts")
    repair_execute.add_argument(
        "--execute-safe-commands",
        action="store_true",
        help="Execute no-shell commands declared in the selected repair phase/tasks and write execution evidence",
    )
    repair_execute.add_argument("--workspace", default=".", help="Workspace used for safe repair command execution")
    verify_repair_preflight = eval_sub.add_parser(
        "verify-repair-preflight",
        help="Verify repair-execute preflight attestation artifacts",
    )
    verify_repair_preflight.add_argument(
        "--preflight-dir",
        required=True,
        help="Directory containing repair-execute-preflight-attestation.json",
    )
    verify_repair_preflight.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    eval_stubs = eval_sub.add_parser("eval-stubs", help="Build targeted eval stubs from repair tasks")
    eval_stubs.add_argument("--repair-tasks", required=True, help="repair-tasks.json file or containing directory")
    eval_stubs.add_argument("--output-dir", help="Directory for targeted-eval-stubs.json and targeted-eval-stubs.md")
    eval_stubs.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    materialize_stubs = eval_sub.add_parser("materialize-stubs", help="Convert targeted eval stubs into a loadable eval suite")
    materialize_stubs.add_argument("--stubs", required=True, help="targeted-eval-stubs.json file or containing directory")
    materialize_stubs.add_argument("--output-dir", help="Directory for targeted-eval-suite.json and targeted-eval-suite.md")
    materialize_stubs.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    run_suite = eval_sub.add_parser("run-suite", help="Run any loadable eval suite JSON against the configured model")
    run_suite.add_argument("--suite", required=True, help="Eval suite JSON file or containing directory")
    run_suite.add_argument("--workspace", default=".")
    run_suite.add_argument("--output-root", default=".")
    run_suite.add_argument("--run-name", default="auto")
    run_suite.add_argument(
        "--profile",
        choices=["small", "balanced", "small_strict", "deep"],
        default="small",
        help="Runtime model profile used by the generic suite runner",
    )
    run_suite.add_argument("--gate", action="store_true", help="Run the strict release gate after writing reports")
    run_suite.add_argument("--gate-output-dir", help="Directory for gate.json and gate.md")
    run_suite.add_argument("--compare-baseline", help="Compare this run against a baseline run directory")
    run_suite.add_argument("--compare-latest", action="store_true", help="Compare this run against the previous latest run")
    run_suite.add_argument("--compare-output-dir", help="Directory for comparison.json and comparison.md")
    run_suite.add_argument(
        "--compare-profile",
        choices=["strict", "release", "exploratory"],
        default="release",
        help="Regression profile for automatic comparison",
    )
    validate_suite = eval_sub.add_parser("validate-suite", help="Validate an eval suite JSON without model calls")
    validate_suite.add_argument("--suite", required=True, help="Eval suite JSON file or containing directory")
    validate_suite.add_argument("--workspace", default=".", help="Workspace used to build the active tool registry")
    validate_suite.add_argument("--output-dir", help="Directory for suite-validation.json and suite-validation.md")
    validate_suite.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    list_tools = eval_sub.add_parser("list-tools", help="List tools available to eval suites")
    list_tools.add_argument("--workspace", default=".", help="Workspace used to build the active tool registry")
    list_tools.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    list_quality_gates = eval_sub.add_parser("list-quality-gates", help="List quality gates available to eval suites")
    list_quality_gates.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    gate = eval_sub.add_parser("gate", help="Apply release gate thresholds to one eval run directory")
    gate.add_argument("--run", required=True)
    gate.add_argument("--output-dir")
    gate.add_argument("--json", action="store_true", help="Print JSON instead of markdown")
    gate.add_argument("--profile", choices=["dev", "candidate", "release"], default="release")
    gate.add_argument("--min-success-rate", type=float, default=1.0)
    gate.add_argument("--max-failed-tasks", type=int, default=0)
    gate.add_argument("--max-invalid-tool-calls", type=int, default=0)
    gate.add_argument("--max-schema-violations", type=int, default=0)
    gate.add_argument("--min-schema-repair-hint-recovery-rate", type=float, default=0.0)
    gate.add_argument("--max-schema-repair-hint-failures", type=int, default=0)
    gate.add_argument("--max-retry-budget-exhaustions", type=int, default=0)
    gate.add_argument("--max-pre-dispatch-blocks", type=int, default=0)
    gate.add_argument("--max-trajectory-failures", type=int, default=0)
    gate.add_argument("--max-failure-clusters", type=int, default=0)
    gate.add_argument("--max-critical-remediations", type=int, default=0)
    package_parser = sub.add_parser("package", help="Build and verify portable Metis downstream agent packages")
    package_sub = package_parser.add_subparsers(dest="package_command")
    package_build = package_sub.add_parser("build", help="Build a portable package directory")
    package_build.add_argument("--source", required=True)
    package_build.add_argument("--output", required=True)
    package_build.add_argument("--json", action="store_true")
    package_verify = package_sub.add_parser("verify", help="Verify a portable package directory")
    package_verify.add_argument("--path", required=True)
    package_verify.add_argument("--profile", choices=["dev", "candidate", "release"], default="dev")
    package_verify.add_argument("--json", action="store_true")
    package_install = package_sub.add_parser("install", help="Install a verified package directory")
    package_install.add_argument("--path", required=True)
    package_install.add_argument("--install-dir", required=True)
    package_install.add_argument("--overwrite", action="store_true")
    package_install.add_argument("--json", action="store_true")
    package_export = package_sub.add_parser("export", help="Export a verified package directory to a zip archive")
    package_export.add_argument("--path", required=True)
    package_export.add_argument("--output", required=True)
    package_export.add_argument("--json", action="store_true")
    provider_parser = sub.add_parser("provider", help="Inspect configured model provider capabilities")
    provider_sub = provider_parser.add_subparsers(dest="provider_command")
    provider_capabilities = provider_sub.add_parser("capabilities", help="Print provider capability metadata")
    provider_capabilities.add_argument("--model", help="Provider model name. Defaults to METIS_MODEL.")
    provider_capabilities.add_argument("--base-url", help="Provider base URL. Defaults to METIS_BASE_URL.")
    provider_capabilities.add_argument("--json", action="store_true", help="Print JSON instead of text")
    plugin_parser = sub.add_parser("plugin", help="Inspect Metis plugin manifests")
    plugin_sub = plugin_parser.add_subparsers(dest="plugin_command")
    plugin_inspect = plugin_sub.add_parser("inspect", help="Validate and print a plugin manifest")
    plugin_inspect.add_argument("--path", required=True, help="Plugin directory or manifest.json path")
    plugin_inspect.add_argument("--json", action="store_true", help="Print JSON instead of text")
    checkpoint_parser = sub.add_parser("checkpoint", help="Inspect persisted run checkpoints")
    checkpoint_sub = checkpoint_parser.add_subparsers(dest="checkpoint_command")
    checkpoint_list = checkpoint_sub.add_parser("list", help="List checkpoints for a session")
    checkpoint_list.add_argument("--state-db", required=True, help="SQLite state database path")
    checkpoint_list.add_argument("--session-id", required=True, help="Session id to inspect")
    checkpoint_list.add_argument("--json", action="store_true", help="Print JSON instead of text")
    checkpoint_latest = checkpoint_sub.add_parser("latest", help="Print latest checkpoint for a session")
    checkpoint_latest.add_argument("--state-db", required=True, help="SQLite state database path")
    checkpoint_latest.add_argument("--session-id", required=True, help="Session id to inspect")
    checkpoint_latest.add_argument("--json", action="store_true", help="Print JSON instead of text")
    return parser


def cmd_doctor(args: argparse.Namespace) -> int:
    print("Metis doctor")
    print(f"METIS_BASE_URL={'set' if os.getenv('METIS_BASE_URL') else 'missing'}")
    print(f"METIS_API_KEY={'set' if os.getenv('METIS_API_KEY') else 'missing'}")
    print(f"METIS_MODEL={os.getenv('METIS_MODEL', 'glm-4.7-flash')}")
    return 0


def _provider_capabilities(args: argparse.Namespace) -> int:
    provider = OpenAICompatibleProvider(model=args.model, base_url=args.base_url)
    capabilities = provider.capabilities().to_dict()
    if args.json:
        print(json.dumps(capabilities, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Metis provider capabilities")
        for key in sorted(capabilities):
            value = capabilities[key]
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            print(f"{key}: {value}")
    return 0


def _plugin_inspect(args: argparse.Namespace) -> int:
    manifest = load_plugin_manifest(args.path)
    plugin_dir = Path(args.path)
    if plugin_dir.is_file():
        plugin_dir = plugin_dir.parent
    validation_errors = validate_plugin_manifest(manifest, plugin_dir)
    payload = {"manifest": manifest.to_dict(), "valid": not validation_errors, "validation_errors": list(validation_errors)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Plugin: {manifest.id} ({manifest.name})")
        print(f"Version: {manifest.version}")
        print(f"Valid: {not validation_errors}")
        if validation_errors:
            print("Validation errors:")
            for error in validation_errors:
                print(f"- {error}")
        if manifest.tools:
            print(f"Tools: {', '.join(manifest.tools)}")
        if manifest.required_permissions:
            print(f"Required permissions: {', '.join(manifest.required_permissions)}")
    return 0 if not validation_errors else 1


def _checkpoint_list(args: argparse.Namespace) -> int:
    store = SQLiteStateStore(args.state_db)
    checkpoints = store.list_checkpoints(args.session_id)
    if args.json:
        print(json.dumps({"session_id": args.session_id, "checkpoints": checkpoints}, ensure_ascii=False, indent=2))
    else:
        print(f"Checkpoints for session: {args.session_id}")
        for checkpoint in checkpoints:
            print(
                f"- {checkpoint['id']} phase={checkpoint['phase']} status={checkpoint['status']} "
                f"task_contract_hash={checkpoint['task_contract_hash']} prompt_stack_hash={checkpoint['prompt_stack_hash']}"
            )
    return 0


def _checkpoint_latest(args: argparse.Namespace) -> int:
    store = SQLiteStateStore(args.state_db)
    checkpoint = store.latest_checkpoint(args.session_id)
    if checkpoint is None:
        if args.json:
            print(json.dumps({"session_id": args.session_id, "checkpoint": None}, ensure_ascii=False, indent=2))
        else:
            print(f"No checkpoint found for session: {args.session_id}")
        return 1
    if args.json:
        print(json.dumps({"session_id": args.session_id, "checkpoint": checkpoint}, ensure_ascii=False, indent=2))
    else:
        print(f"Latest checkpoint for session: {args.session_id}")
        print(
            f"{checkpoint['id']} phase={checkpoint['phase']} status={checkpoint['status']} "
            f"task_contract_hash={checkpoint['task_contract_hash']} prompt_stack_hash={checkpoint['prompt_stack_hash']}"
        )
    return 0


async def _run(args: argparse.Namespace) -> int:
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=args.workspace)
    manifest = load_app_manifest(getattr(args, "manifest", None), workspace=args.workspace)
    if args.state_db:
        manifest = replace(manifest, state_db_path=args.state_db)
    state = SQLiteStateStore(args.state_db) if args.state_db else None
    loop = AgentLoop(
        provider=OpenAICompatibleProvider(model=manifest.model, base_url=manifest.base_url or None),
        registry=registry,
        workspace=args.workspace,
        profile=manifest.profile,
        state=state,
        evidence_ledger=EvidenceLedger(state) if state is not None else None,
    )
    result = await loop.run(
        AgentRunRequest(
            messages=build_runtime_messages(args.task, manifest=manifest, workspace=args.workspace),
            max_turns=args.max_turns,
            session_id=args.session_id,
            task_contract_hash=build_runtime_task_contract(args.task, manifest=manifest).contract_hash(),
            prompt_stack_hash=build_runtime_prompt_stack(args.task, manifest=manifest, workspace=args.workspace).stack_hash(),
            allowed_tool_permissions=manifest_allowed_tool_permissions(manifest),
        )
    )
    print(result.final_text)
    return 0 if result.status == "final" else 1


async def _resume(args: argparse.Namespace) -> int:
    store = SQLiteStateStore(args.state_db)
    prior_messages = store.list_messages(args.session_id)
    if not prior_messages:
        print(f"No persisted messages found for session: {args.session_id}", file=sys.stderr)
        return 1
    manifest = load_app_manifest(getattr(args, "manifest", None), workspace=args.workspace)
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=args.workspace)
    loop = AgentLoop(
        provider=OpenAICompatibleProvider(model=manifest.model, base_url=manifest.base_url or None),
        registry=registry,
        workspace=args.workspace,
        profile=manifest.profile,
        state=store,
    )
    store.append_message(args.session_id, "user", args.message, {"source": "resume"})
    task_contract = build_runtime_task_contract(args.message, manifest=manifest)
    prompt_stack = build_runtime_prompt_stack(args.message, manifest=manifest, workspace=args.workspace, task_contract=task_contract)
    result = await loop.run(
        AgentRunRequest(
            messages=prior_messages + [{"role": "user", "content": args.message}],
            max_turns=args.max_turns,
            session_id=args.session_id,
            task_contract_hash=task_contract.contract_hash(),
            prompt_stack_hash=prompt_stack.stack_hash(),
            allowed_tool_permissions=manifest_allowed_tool_permissions(manifest),
            resume_from_checkpoint=True,
        )
    )
    print(result.final_text)
    return 0 if result.status == "final" else 1


def _app_init(args: argparse.Namespace) -> int:
    path = write_default_app_manifest(args.output, name=args.name, workspace=args.workspace)
    print(f"Metis app manifest written to: {path}")
    return 0


def _app_show(args: argparse.Namespace) -> int:
    manifest = load_app_manifest(args.manifest, workspace=args.workspace)
    print(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _tui(args: argparse.Namespace) -> int:
    manifest = load_app_manifest(args.manifest, workspace=args.workspace)
    if args.state_db:
        manifest = replace(manifest, state_db_path=args.state_db)
    return run_tui_sync(manifest, max_turns=args.max_turns)


def _web(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("Metis Web UI requires uvicorn. Install with: pip install 'metis-agent-harness[ui]'", file=sys.stderr)
        return 2
    manifest = load_app_manifest(args.manifest, workspace=args.workspace)
    if args.state_db:
        manifest = replace(manifest, state_db_path=args.state_db)
    app = create_app(manifest)
    print(f"{manifest.name} Web UI")
    print(f"Workspace: {manifest.workspace}")
    print(f"Model: {manifest.model}")
    print(f"URL: http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _develop(args: argparse.Namespace) -> int:
    request = args.request
    app_name = args.name
    if not request:
        if not sys.stdin.isatty():
            print("metis develop requires --request in non-interactive mode.", file=sys.stderr)
            return 2
        request = input("Describe the agent you want to build on Metis: ").strip()
    if not app_name:
        inferred_name = infer_app_name(request)
        if sys.stdin.isatty() and not args.json and not args.approve:
            entered_name = input(f"Agent name [{inferred_name}]: ").strip()
            app_name = entered_name or inferred_name
        else:
            app_name = inferred_name
    package = build_development_package(request, app_name=app_name)
    approved = bool(args.approve)
    if not args.approve and sys.stdin.isatty() and not args.json:
        print(_development_summary(package))
        answer = input("Apply this adaptation now? Type yes to write approved artifacts: ").strip().lower()
        approved = answer in {"y", "yes"}
    output_dir = write_development_package(package, args.output_dir, approved=approved)
    result = {
        "output_dir": str(output_dir),
        "approved": approved,
        "app_name": package.app_name,
        "task_count": package.tasks["task_count"],
        "analysis_report": str(Path(output_dir) / "analysis-report.md"),
        "adaptation_plan": str(Path(output_dir) / "adaptation-plan.md"),
        "task_breakdown": str(Path(output_dir) / "task-breakdown.md"),
        "implementation_contract": str(Path(output_dir) / "implementation-contract.md"),
        "verification_checklist": str(Path(output_dir) / "verification-checklist.md"),
        "task_contract": str(Path(output_dir) / "task-contract.md"),
        "manifest": str(Path(output_dir) / "metis-agent.json") if approved else "",
        "runtime_entrypoints": package.implementation["runtime_entrypoints"],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Developer workflow written to: {output_dir}")
        print(f"Approved artifacts written: {str(approved).lower()}")
        print(f"Task count: {package.tasks['task_count']}")
        print("Runtime entrypoints:")
        for entrypoint in package.implementation["runtime_entrypoints"]:
            print(f"- {entrypoint}")
    return 0


def _development_summary(package) -> str:
    return "\n".join(
        [
            f"Metis developer adaptation: {package.app_name}",
            "",
            "Workflow:",
            "1. Research and fit analysis",
            "2. Adaptation design",
            "3. User approval",
            "4. Prompt/manifest/command implementation",
            "5. Verification",
            "",
            f"Fine-grained tasks: {package.tasks['task_count']}",
            "Default behavior: write reports and plan first; approved artifacts are written only after confirmation.",
            "",
        ]
    )


async def _eval_real_small_model(args: argparse.Namespace) -> int:
    if not real_model_env_configured():
        print("Real small-model eval requires METIS_BASE_URL, METIS_API_KEY, and METIS_MODEL.")
        print("The eval was not run and no model result was faked.")
        return 2
    previous_latest = _read_latest_run_dir(args.output_root) if args.compare_latest else None
    requested_run_name = args.run_name
    run_name = resolve_real_small_model_eval_run_name(args.run_name)
    pre_run_dir = write_real_small_model_pre_run_contract(
        workspace=args.workspace,
        output_root=args.output_root,
        run_name=run_name,
        requested_run_name=requested_run_name,
    )
    print(f"Pre-run contract written to: {pre_run_dir}")
    suite = await run_real_small_model_eval_suite(workspace=args.workspace)
    output_dir = write_real_small_model_eval_reports(suite, output_root=args.output_root, run_name=run_name)
    print(f"Real small-model eval complete: success_rate={suite.success_rate:.2%}")
    print(f"Reports written to: {output_dir}")
    exit_code = 0 if suite.success_rate == 1.0 else 1
    if args.gate:
        gate = evaluate_eval_run_gate(output_dir)
        gate_output_dir = args.gate_output_dir or str(Path(output_dir) / "gate")
        write_eval_gate_report(gate, gate_output_dir)
        print(eval_gate_to_markdown(gate))
        print(f"Gate written to: {gate_output_dir}")
        if not gate["passed"]:
            exit_code = 1
    compare_baseline = args.compare_baseline
    if args.compare_latest:
        if previous_latest is None:
            print("Cannot compare latest: previous docs/evals/runs/latest.json was not available before this run.")
            exit_code = 1
        else:
            compare_baseline = previous_latest
    if compare_baseline:
        comparison = compare_eval_runs(
            baseline_dir=compare_baseline,
            current_dir=output_dir,
            profile=args.compare_profile,
        )
        compare_output_dir = args.compare_output_dir or str(Path(output_dir) / "comparison")
        write_eval_run_comparison(comparison, compare_output_dir)
        print(eval_run_comparison_to_markdown(comparison))
        print(f"Comparison written to: {compare_output_dir}")
        if comparison["has_regression"]:
            exit_code = 1
    return exit_code


def _eval_compare(args: argparse.Namespace) -> int:
    comparison = compare_eval_runs(baseline_dir=args.baseline, current_dir=args.current, profile=args.profile)
    if args.output_dir:
        write_eval_run_comparison(comparison, args.output_dir)
    if args.json:
        print(json.dumps(comparison, ensure_ascii=False, indent=2))
    else:
        print(eval_run_comparison_to_markdown(comparison))
    return 1 if comparison["has_regression"] else 0


def _eval_gate(args: argparse.Namespace) -> int:
    gate = evaluate_eval_run_gate(
        args.run,
        profile=args.profile,
        min_success_rate=args.min_success_rate,
        max_failed_tasks=args.max_failed_tasks,
        max_invalid_tool_calls=args.max_invalid_tool_calls,
        max_schema_violations=args.max_schema_violations,
        min_schema_repair_hint_recovery_rate=args.min_schema_repair_hint_recovery_rate,
        max_schema_repair_hint_failures=args.max_schema_repair_hint_failures,
        max_retry_budget_exhaustions=args.max_retry_budget_exhaustions,
        max_pre_dispatch_blocks=args.max_pre_dispatch_blocks,
        max_trajectory_failures=args.max_trajectory_failures,
        max_failure_clusters=args.max_failure_clusters,
        max_critical_remediations=args.max_critical_remediations,
        require_suite_schema_evidence=True,
        require_task_contract_evidence=True,
        require_provenance_evidence=True,
        require_pre_run_contract_evidence=True,
        require_run_attestation_evidence=True,
    )
    if args.output_dir:
        write_eval_gate_report(gate, args.output_dir)
    if args.json:
        print(json.dumps(gate, ensure_ascii=False, indent=2))
    else:
        print(eval_gate_to_markdown(gate))
    return 0 if gate["passed"] else 1


def _eval_diagnose(args: argparse.Namespace) -> int:
    repair_tasks = diagnose_eval_comparison(args.comparison, args.output_dir)
    if args.json:
        print(json.dumps(repair_tasks, ensure_ascii=False, indent=2))
    else:
        print(repair_tasks_to_markdown(repair_tasks))
    return 0


def _eval_repair_plan(args: argparse.Namespace) -> int:
    plan = plan_repairs(args.repair_tasks)
    if args.output_dir:
        write_repair_plan(plan, args.output_dir)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(repair_plan_to_markdown(plan))
    attestation_errors = _repair_plan_attestation_errors(args)
    if attestation_errors:
        for error in attestation_errors:
            print(error, file=sys.stderr)
        return 1
    phase_errors = _repair_plan_executable_phase_errors(plan, args.require_executable_phase)
    if phase_errors:
        for error in phase_errors:
            print(error, file=sys.stderr)
        return 1
    return 0


def _repair_plan_attestation_errors(args: argparse.Namespace) -> list[str]:
    required_phase_ids = getattr(args, "require_executable_phase", [])
    if not required_phase_ids:
        return []
    if not args.output_dir:
        return ["Repair phase enforcement requires --output-dir so repair-plan attestation can be written and verified."]
    failures = verify_repair_plan_attestation(args.output_dir)
    return [f"Repair plan attestation failed: {failure}" for failure in failures]


def _repair_plan_executable_phase_errors(plan: dict, required_phase_ids: list[str]) -> list[str]:
    if not required_phase_ids:
        return []
    phases = {str(phase.get("id", "")): phase for phase in plan.get("phases", [])}
    executable = set(str(phase_id) for phase_id in plan.get("phase_status_summary", {}).get("executable_phases", []))
    errors: list[str] = []
    for phase_id in required_phase_ids:
        phase = phases.get(str(phase_id))
        if phase is None:
            errors.append(f"Required repair phase is absent: {phase_id}")
            continue
        if str(phase_id) not in executable:
            status = phase.get("status", "open")
            blocked_by = ", ".join(str(value) for value in phase.get("blocked_by", [])) or "none"
            errors.append(f"Required repair phase is not executable: {phase_id} status={status} blocked_by={blocked_by}")
    return errors


def _eval_verify_repair_plan(args: argparse.Namespace) -> int:
    failures = verify_repair_plan_attestation(args.plan_dir)
    return _print_artifact_verification_result(
        artifact_label="repair_plan",
        path_label="plan_dir",
        path=args.plan_dir,
        title="Metis Repair Plan Verification",
        failures=failures,
        as_json=args.json,
    )


def _eval_verify_eval_stubs(args: argparse.Namespace) -> int:
    failures = verify_targeted_eval_stubs_attestation(args.stubs_dir)
    return _print_artifact_verification_result(
        artifact_label="targeted_eval_stubs",
        path_label="stubs_dir",
        path=args.stubs_dir,
        title="Metis Targeted Eval Stubs Verification",
        failures=failures,
        as_json=args.json,
    )


def _eval_verify_targeted_suite(args: argparse.Namespace) -> int:
    failures = verify_targeted_eval_suite_attestation(args.suite_dir)
    return _print_artifact_verification_result(
        artifact_label="targeted_eval_suite",
        path_label="suite_dir",
        path=args.suite_dir,
        title="Metis Targeted Eval Suite Verification",
        failures=failures,
        as_json=args.json,
    )


def _eval_verify_repair_preflight(args: argparse.Namespace) -> int:
    failures = verify_repair_execute_preflight_attestation(args.preflight_dir)
    return _print_artifact_verification_result(
        artifact_label="repair_execute_preflight",
        path_label="preflight_dir",
        path=args.preflight_dir,
        title="Metis Repair Execute Preflight Verification",
        failures=failures,
        as_json=args.json,
    )


def _eval_repair_execute(args: argparse.Namespace) -> int:
    result = _repair_execute_preflight(
        plan_dir=args.plan_dir,
        phase_id=args.phase,
        stubs_dir=args.stubs_dir,
        suite_dir=args.suite_dir,
    )
    if args.output_dir:
        _write_repair_execute_preflight(result, args.output_dir)
    execution_result = None
    if args.execute_safe_commands:
        if not args.output_dir:
            print("Repair safe command execution requires --output-dir.", file=sys.stderr)
            return 1
        execution_result = _execute_repair_safe_commands(
            preflight=result,
            plan_dir=args.plan_dir,
            phase_id=args.phase,
            output_dir=args.output_dir,
            workspace=args.workspace,
        )
        result["execution"] = execution_result
    if args.record_attempt_status or execution_result is not None:
        if not args.output_dir:
            print("Repair execution attempt recording requires --output-dir.", file=sys.stderr)
            return 1
        if execution_result is not None:
            attempt_status = "complete" if execution_result["success"] else "blocked"
        else:
            attempt_status = args.record_attempt_status if result["ready"] else "blocked"
        _write_repair_execution_attempt(
            preflight=result,
            plan_dir=args.plan_dir,
            phase_id=args.phase,
            output_dir=args.output_dir,
            status=attempt_status,
            executor_id=args.executor_id,
            note=args.attempt_note,
        )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_repair_execute_preflight_to_markdown(result))
    if execution_result is not None and not execution_result["success"]:
        return 1
    return 0 if result["ready"] else 1


def _execute_repair_safe_commands(
    *,
    preflight: dict[str, Any],
    plan_dir: str | Path,
    phase_id: str,
    output_dir: str | Path,
    workspace: str | Path,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan, load_failures = _load_repair_plan_for_preflight(Path(plan_dir))
    commands = _repair_phase_safe_commands(plan or {}, phase_id)
    results: list[dict[str, Any]] = []
    failures = list(load_failures)
    if not preflight.get("ready"):
        failures.extend(str(item) for item in preflight.get("failures", []))
    if not commands:
        failures.append(f"no executable safe commands declared for phase: {phase_id}")
    if not failures:
        for index, command in enumerate(commands, start=1):
            safety_errors = _safe_repair_command_errors(command)
            if safety_errors:
                result = {
                    "index": index,
                    "command": command,
                    "display": " ".join(command),
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "; ".join(safety_errors),
                    "blocked": True,
                }
            else:
                result = _run_safe_repair_command(command, workspace=workspace, index=index)
            results.append(result)
            if result["returncode"] != 0:
                failures.append(f"command {index} failed with returncode {result['returncode']}: {result['display']}")
    payload = {
        "operation": "repair_execute_safe_commands",
        "phase": phase_id,
        "workspace": str(Path(workspace)),
        "success": not failures,
        "command_count": len(commands),
        "failure_count": len(failures),
        "failures": failures,
        "commands": results,
    }
    (output_dir / "repair-execution-results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "repair-execution-results.md").write_text(
        _repair_execution_results_to_markdown(payload),
        encoding="utf-8",
    )
    return payload


def _repair_phase_safe_commands(plan: dict[str, Any], phase_id: str) -> list[list[str]]:
    phase = next((item for item in plan.get("phases", []) if str(item.get("id", "")) == phase_id), {})
    task_ids = {str(item) for item in phase.get("task_ids", [])}
    raw_commands: list[Any] = []
    raw_commands.extend(phase.get("execution_commands", []) or [])
    for task in plan.get("tasks", []) or []:
        if str(task.get("id", "")) in task_ids:
            raw_commands.extend(task.get("execution_commands", []) or [])
            raw_commands.extend(task.get("verification_commands", []) or [])
    return [_coerce_safe_command(item) for item in raw_commands if _coerce_safe_command(item)]


def _safe_repair_command_errors(command: list[str]) -> list[str]:
    if not command:
        return ["empty command is not allowed"]
    executable = Path(command[0]).name.lower()
    if executable in {"powershell", "powershell.exe", "pwsh", "pwsh.exe", "cmd", "cmd.exe", "sh", "bash", "zsh"}:
        return [f"shell executable is not allowed for safe repair execution: {command[0]}"]
    lowered = [part.lower() for part in command]
    joined = " ".join(lowered)
    blocked_exact = {"rm", "del", "erase", "rmdir", "rd", "format", "shutdown", "reboot"}
    if executable in blocked_exact:
        return [f"destructive executable is not allowed for safe repair execution: {command[0]}"]
    if executable in {"python", "python.exe", "py", "py.exe"} and any(part in {"-c", "-mrunpy"} for part in lowered[1:]):
        return ["inline Python execution is not allowed for safe repair execution"]
    blocked_phrases = [
        "remove-item",
        "git push",
        "git reset --hard",
        "git clean",
        "npm publish",
        "twine upload",
        "curl -x",
    ]
    for phrase in blocked_phrases:
        if phrase in joined:
            return [f"blocked command phrase for safe repair execution: {phrase}"]
    return []


def _coerce_safe_command(item: Any) -> list[str]:
    command = item.get("command") if isinstance(item, dict) else item
    if isinstance(command, list) and all(isinstance(part, str) and part for part in command):
        return list(command)
    if isinstance(command, str) and command.strip():
        return shlex.split(command)
    return []


def _run_safe_repair_command(command: list[str], *, workspace: str | Path, index: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(workspace),
            shell=False,
            text=True,
            capture_output=True,
            timeout=600,
            check=False,
        )
        return {
            "index": index,
            "command": command,
            "display": " ".join(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "blocked": False,
        }
    except Exception as exc:
        return {
            "index": index,
            "command": command,
            "display": " ".join(command),
            "returncode": 1,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
            "blocked": False,
        }


def _repair_execution_results_to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Metis Repair Execution Results",
        "",
        f"Phase: {payload.get('phase', '')}",
        f"Success: {str(bool(payload.get('success'))).lower()}",
        f"Command count: {payload.get('command_count', 0)}",
        f"Failure count: {payload.get('failure_count', 0)}",
        "",
        "## Commands",
        "",
    ]
    for command in payload.get("commands", []):
        lines.extend(
            [
                f"### Command {command.get('index')}",
                "",
                f"- Command: `{command.get('display', '')}`",
                f"- Return code: {command.get('returncode')}",
                "",
            ]
        )
    if payload.get("failures"):
        lines.extend(["## Failures", ""])
        lines.extend(f"- {failure}" for failure in payload.get("failures", []))
    return "\n".join(lines) + "\n"


def _repair_execute_preflight(
    *,
    plan_dir: str | Path,
    phase_id: str,
    stubs_dir: str | Path | None = None,
    suite_dir: str | Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    plan_dir = Path(plan_dir)
    plan_attestation_failures = verify_repair_plan_attestation(plan_dir)
    checks.append(_preflight_check("repair_plan_attestation", not plan_attestation_failures, plan_attestation_failures))
    plan, plan_failures = _load_repair_plan_for_preflight(plan_dir)
    checks.append(_preflight_check("repair_plan_load", not plan_failures, plan_failures))
    phase_failures = _repair_plan_executable_phase_errors(plan or {}, [phase_id]) if plan is not None else []
    checks.append(_preflight_check("phase_executable", not phase_failures, phase_failures))
    if stubs_dir:
        stubs_failures = verify_targeted_eval_stubs_attestation(stubs_dir)
        checks.append(_preflight_check("targeted_eval_stubs_attestation", not stubs_failures, stubs_failures))
    if suite_dir:
        suite_failures = verify_targeted_eval_suite_attestation(suite_dir)
        checks.append(_preflight_check("targeted_eval_suite_attestation", not suite_failures, suite_failures))
    failures = [failure for check in checks for failure in check["failures"]]
    return {
        "operation": "repair_execute_preflight",
        "ready": not failures,
        "phase": phase_id,
        "plan_dir": str(plan_dir),
        "stubs_dir": str(stubs_dir) if stubs_dir else "",
        "suite_dir": str(suite_dir) if suite_dir else "",
        "checks": checks,
        "failure_count": len(failures),
        "failures": failures,
    }


def _load_repair_plan_for_preflight(plan_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    path = plan_dir / "repair-plan.json"
    if not path.exists():
        return None, ["repair-plan.json missing from repair plan directory"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None, ["repair-plan.json is not valid JSON"]
    if not isinstance(payload, dict):
        return None, ["repair-plan.json root is not an object"]
    return payload, []


def _preflight_check(name: str, passed: bool, failures: list[str]) -> dict[str, Any]:
    return {"name": name, "passed": passed, "failures": failures}


def _repair_execute_preflight_to_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Metis Repair Execute Preflight",
        "",
        f"Ready: {str(bool(result.get('ready'))).lower()}",
        f"Phase: {result.get('phase', '')}",
        f"Plan dir: {result.get('plan_dir', '')}",
        f"Stubs dir: {result.get('stubs_dir', '') or 'none'}",
        f"Suite dir: {result.get('suite_dir', '') or 'none'}",
        f"Failure count: {result.get('failure_count', 0)}",
        "",
        "## Checks",
        "",
    ]
    for check in result.get("checks", []):
        lines.append(f"- {check.get('name', '')}: {'passed' if check.get('passed') else 'failed'}")
        for failure in check.get("failures", []):
            lines.append(f"  - {failure}")
    return "\n".join(lines) + "\n"


def _write_repair_execute_preflight(result: dict[str, Any], output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repair-execute-preflight.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "repair-execute-preflight.md").write_text(
        _repair_execute_preflight_to_markdown(result),
        encoding="utf-8",
    )
    write_repair_execute_preflight_attestation(output_dir, preflight=result)
    return output_dir


def _write_repair_execution_attempt(
    *,
    preflight: dict[str, Any],
    plan_dir: str | Path,
    phase_id: str,
    output_dir: str | Path,
    status: str,
    executor_id: str,
    note: str,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plan, failures = _load_repair_plan_for_preflight(Path(plan_dir))
    attempt = _repair_execution_attempt(
        preflight=preflight,
        phase_id=phase_id,
        status=status,
        executor_id=executor_id,
        note=note,
        load_failures=failures,
    )
    attempt_dir = output_dir / "repair-execute-attempt"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "repair-execute-attempt.json").write_text(
        json.dumps(attempt, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (attempt_dir / "repair-execute-attempt.md").write_text(
        _repair_execution_attempt_to_markdown(attempt),
        encoding="utf-8",
    )
    if plan is not None:
        updated_plan = _repair_plan_with_attempt_status(plan, attempt)
        write_repair_plan(updated_plan, output_dir / "updated-repair-plan")
    return attempt_dir


def _repair_execution_attempt(
    *,
    preflight: dict[str, Any],
    phase_id: str,
    status: str,
    executor_id: str,
    note: str,
    load_failures: list[str],
) -> dict[str, Any]:
    failures = list(preflight.get("failures", [])) + list(load_failures)
    return {
        "operation": "repair_execution_attempt",
        "phase": phase_id,
        "status": status,
        "executor_id": executor_id,
        "note": note,
        "ready": bool(preflight.get("ready")),
        "preflight_failure_count": int(preflight.get("failure_count", 0)),
        "failure_count": len(failures),
        "failures": failures,
        "preflight_checks": preflight.get("checks", []),
        "execution": preflight.get("execution"),
    }


def _repair_execution_attempt_to_markdown(attempt: dict[str, Any]) -> str:
    lines = [
        "# Metis Repair Execution Attempt",
        "",
        f"Phase: {attempt.get('phase', '')}",
        f"Status: {attempt.get('status', '')}",
        f"Executor: {attempt.get('executor_id', '')}",
        f"Ready: {str(bool(attempt.get('ready'))).lower()}",
        f"Failure count: {attempt.get('failure_count', 0)}",
        f"Note: {attempt.get('note', '') or 'none'}",
        "",
        "## Failures",
        "",
    ]
    failures = attempt.get("failures", [])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _repair_plan_with_attempt_status(plan: dict[str, Any], attempt: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(plan, ensure_ascii=False))
    phase_id = str(attempt.get("phase", ""))
    status = str(attempt.get("status", "in_progress"))
    attempt_summary = {
        "phase": phase_id,
        "status": status,
        "executor_id": attempt.get("executor_id", ""),
        "ready": bool(attempt.get("ready")),
        "failure_count": int(attempt.get("failure_count", 0)),
        "failures": attempt.get("failures", []),
        "execution": attempt.get("execution"),
    }
    phase_task_ids: list[str] = []
    for phase in updated.get("phases", []):
        if str(phase.get("id", "")) != phase_id:
            continue
        phase_task_ids = [str(task_id) for task_id in phase.get("task_ids", [])]
        break
    for task in updated.get("tasks", []):
        task_id = str(task.get("id", ""))
        if task_id not in phase_task_ids:
            continue
        task["status"] = status
        task["last_attempt"] = attempt_summary
    rebuilt = build_repair_plan(updated)
    for phase in rebuilt.get("phases", []):
        if str(phase.get("id", "")) == phase_id:
            phase["last_attempt"] = attempt_summary
    for task in rebuilt.get("tasks", []):
        if str(task.get("id", "")) in phase_task_ids:
            task["last_attempt"] = attempt_summary
    rebuilt["execution_attempts"] = list(plan.get("execution_attempts", [])) + [attempt_summary]
    return rebuilt


def _print_artifact_verification_result(
    *,
    artifact_label: str,
    path_label: str,
    path: str,
    title: str,
    failures: list[str],
    as_json: bool,
) -> int:
    result = {
        "artifact": artifact_label,
        path_label: str(path),
        "verified": not failures,
        "failure_count": len(failures),
        "failures": failures,
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_artifact_verification_to_markdown(result, title=title, path_label=path_label))
    return 0 if result["verified"] else 1


def _artifact_verification_to_markdown(result: dict, *, title: str, path_label: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"Artifact: {result.get('artifact', '')}",
        f"{path_label}: {result.get(path_label, '')}",
        f"Verified: {str(bool(result.get('verified'))).lower()}",
        f"Failure count: {result.get('failure_count', 0)}",
        "",
        "## Failures",
        "",
    ]
    failures = result.get("failures", [])
    if failures:
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _eval_stubs(args: argparse.Namespace) -> int:
    stubs = build_eval_stubs_from_repair_tasks(load_repair_tasks(args.repair_tasks))
    if args.output_dir:
        write_eval_stubs(stubs, args.output_dir)
    if args.json:
        print(json.dumps(stubs, ensure_ascii=False, indent=2))
    else:
        print(eval_stubs_to_markdown(stubs))
    return 0


def _eval_materialize_stubs(args: argparse.Namespace) -> int:
    suite = materialize_eval_suite(args.stubs)
    if args.output_dir:
        write_materialized_eval_suite(suite, args.output_dir)
    if args.json:
        print(json.dumps(suite, ensure_ascii=False, indent=2))
    else:
        print(eval_suite_to_markdown(suite))
    return 0


async def _eval_run_suite(args: argparse.Namespace) -> int:
    validation = validate_eval_suite(args.suite, **generic_eval_validation_context(workspace=args.workspace))
    if not validation["valid"]:
        print(eval_suite_validation_to_markdown(validation))
        print("The eval was not run because suite validation failed.")
        return 1
    if args.gate and _validation_has_unversioned_suite(validation):
        print(eval_suite_validation_to_markdown(validation))
        print("The eval was not run because release gate requires a declared supported schema_version.")
        return 1
    targeted_suite_dir = _targeted_suite_attestation_dir(args.suite)
    if targeted_suite_dir is not None:
        attestation_failures = verify_targeted_eval_suite_attestation(targeted_suite_dir)
        if attestation_failures:
            print("The eval was not run because targeted suite attestation failed.")
            for failure in attestation_failures:
                print(f"- {failure}")
            return 1
    requires_model_execution = generic_eval_suite_requires_model_execution(args.suite)
    if requires_model_execution and not generic_eval_env_configured():
        print("Generic eval suite requires METIS_BASE_URL, METIS_API_KEY, and METIS_MODEL.")
        print("The eval was not run and no model result was faked.")
        return 2
    previous_latest = _read_latest_run_dir(args.output_root) if args.compare_latest else None
    requested_run_name = args.run_name
    run_name = resolve_eval_run_name(args.run_name)
    pre_run_dir = write_generic_eval_pre_run_contract(
        suite_path=args.suite,
        workspace=args.workspace,
        output_root=args.output_root,
        profile=args.profile,
        run_name=run_name,
        requested_run_name=requested_run_name,
    )
    print(f"Pre-run contract written to: {pre_run_dir}")
    suite = await run_generic_eval_suite(suite_path=args.suite, workspace=args.workspace, profile=args.profile)
    output_dir = write_generic_eval_suite_reports(suite, output_root=args.output_root, run_name=run_name)
    print(f"Generic eval suite complete: success_rate={suite.success_rate:.2%}")
    print(f"Reports written to: {output_dir}")
    exit_code = 0 if suite.success_rate == 1.0 else 1
    if args.gate:
        gate = evaluate_eval_run_gate(output_dir)
        gate_output_dir = args.gate_output_dir or str(Path(output_dir) / "gate")
        write_eval_gate_report(gate, gate_output_dir)
        print(eval_gate_to_markdown(gate))
        print(f"Gate written to: {gate_output_dir}")
        if not gate["passed"]:
            exit_code = 1
    compare_baseline = args.compare_baseline
    if args.compare_latest:
        if previous_latest is None:
            print("Cannot compare latest: previous docs/evals/runs/latest.json was not available before this run.")
            exit_code = 1
        else:
            compare_baseline = previous_latest
    if compare_baseline:
        comparison = compare_eval_runs(
            baseline_dir=compare_baseline,
            current_dir=output_dir,
            profile=args.compare_profile,
        )
        compare_output_dir = args.compare_output_dir or str(Path(output_dir) / "comparison")
        write_eval_run_comparison(comparison, compare_output_dir)
        print(eval_run_comparison_to_markdown(comparison))
        print(f"Comparison written to: {compare_output_dir}")
        if comparison["has_regression"]:
            exit_code = 1
    return exit_code


def _validation_has_unversioned_suite(validation: dict[str, Any]) -> bool:
    if validation.get("schema_version") == "unversioned":
        return True
    warnings = validation.get("warnings", [])
    if not isinstance(warnings, list):
        return False
    return any(
        isinstance(warning, dict)
        and warning.get("path") == "schema_version"
        and warning.get("code") == "missing"
        for warning in warnings
    )


def _targeted_suite_attestation_dir(suite_path: str | Path) -> Path | None:
    path = Path(suite_path)
    if path.is_dir() and (path / "targeted-eval-suite.json").exists():
        return path
    if path.is_file() and path.name == "targeted-eval-suite.json":
        return path.parent
    return None


def _eval_validate_suite(args: argparse.Namespace) -> int:
    validation = validate_eval_suite(args.suite, **generic_eval_validation_context(workspace=args.workspace))
    if args.output_dir:
        write_eval_suite_validation(validation, args.output_dir)
    if args.json:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
    else:
        print(eval_suite_validation_to_markdown(validation))
    return 0 if validation["valid"] else 1


def _eval_list_tools(args: argparse.Namespace) -> int:
    inventory = generic_eval_tool_inventory(workspace=args.workspace)
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        print(tool_inventory_to_markdown(inventory))
    return 0


def _eval_list_quality_gates(args: argparse.Namespace) -> int:
    inventory = generic_eval_quality_gate_inventory()
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        print(quality_gate_inventory_to_markdown(inventory))
    return 0


def _package_build(args: argparse.Namespace) -> int:
    manifest = build_package(args.source, args.output)
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print(f"Metis package built: {args.output}")
        print(f"File count: {manifest['file_count']}")
    return 0


def _package_verify(args: argparse.Namespace) -> int:
    result = verify_package(args.path, profile=args.profile)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Metis package verification: {args.path}")
        print(f"Profile: {args.profile}")
        print(f"Valid: {str(result['valid']).lower()}")
        if result["failures"]:
            print("Failures:")
            for failure in result["failures"]:
                print(f"- {failure}")
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"- {warning}")
    return 0 if result["valid"] else 1


def _package_install(args: argparse.Namespace) -> int:
    result = install_package(args.path, args.install_dir, overwrite=args.overwrite)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Metis package installed: {result['install_dir']}")
    return 0


def _package_export(args: argparse.Namespace) -> int:
    result = export_package(args.path, args.output)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Metis package exported: {result['archive']}")
        print(f"SHA256: {result['sha256']}")
    return 0


def _trace_show(args: argparse.Namespace) -> int:
    timeline = load_timeline(args.timeline)
    if args.json:
        print(timeline_to_json(timeline))
    else:
        print(timeline_to_markdown(timeline, include_payload=args.include_payload))
    return 0


def _read_latest_run_dir(output_root: str) -> str | None:
    pointer_path = real_small_model_eval_latest_pointer_path(output_root=output_root)
    if not pointer_path.exists():
        return None
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    latest_run_dir = pointer.get("latest_run_dir")
    if not isinstance(latest_run_dir, str) or not latest_run_dir:
        return None
    return latest_run_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "run":
        return asyncio.run(_run(args))
    if args.command == "resume":
        return asyncio.run(_resume(args))
    if args.command == "tui":
        return _tui(args)
    if args.command == "web":
        return _web(args)
    if args.command == "develop":
        return _develop(args)
    if args.command == "app" and args.app_command == "init":
        return _app_init(args)
    if args.command == "app" and args.app_command == "show":
        return _app_show(args)
    if args.command == "trace" and args.trace_command == "show":
        return _trace_show(args)
    if args.command == "eval" and args.eval_suite == "real-small-model":
        return asyncio.run(_eval_real_small_model(args))
    if args.command == "eval" and args.eval_suite == "compare":
        return _eval_compare(args)
    if args.command == "eval" and args.eval_suite == "gate":
        return _eval_gate(args)
    if args.command == "eval" and args.eval_suite == "diagnose":
        return _eval_diagnose(args)
    if args.command == "eval" and args.eval_suite == "repair-plan":
        return _eval_repair_plan(args)
    if args.command == "eval" and args.eval_suite == "verify-repair-plan":
        return _eval_verify_repair_plan(args)
    if args.command == "eval" and args.eval_suite == "verify-eval-stubs":
        return _eval_verify_eval_stubs(args)
    if args.command == "eval" and args.eval_suite == "verify-targeted-suite":
        return _eval_verify_targeted_suite(args)
    if args.command == "eval" and args.eval_suite == "repair-execute":
        return _eval_repair_execute(args)
    if args.command == "eval" and args.eval_suite == "verify-repair-preflight":
        return _eval_verify_repair_preflight(args)
    if args.command == "eval" and args.eval_suite == "eval-stubs":
        return _eval_stubs(args)
    if args.command == "eval" and args.eval_suite == "materialize-stubs":
        return _eval_materialize_stubs(args)
    if args.command == "eval" and args.eval_suite == "run-suite":
        return asyncio.run(_eval_run_suite(args))
    if args.command == "eval" and args.eval_suite == "validate-suite":
        return _eval_validate_suite(args)
    if args.command == "eval" and args.eval_suite == "list-tools":
        return _eval_list_tools(args)
    if args.command == "eval" and args.eval_suite == "list-quality-gates":
        return _eval_list_quality_gates(args)
    if args.command == "package" and args.package_command == "build":
        return _package_build(args)
    if args.command == "package" and args.package_command == "verify":
        return _package_verify(args)
    if args.command == "package" and args.package_command == "install":
        return _package_install(args)
    if args.command == "package" and args.package_command == "export":
        return _package_export(args)
    if args.command == "provider" and args.provider_command == "capabilities":
        return _provider_capabilities(args)
    if args.command == "plugin" and args.plugin_command == "inspect":
        return _plugin_inspect(args)
    if args.command == "checkpoint" and args.checkpoint_command == "list":
        return _checkpoint_list(args)
    if args.command == "checkpoint" and args.checkpoint_command == "latest":
        return _checkpoint_latest(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
