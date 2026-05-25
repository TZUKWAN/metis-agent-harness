"""Metis developer adaptation workflow."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metis.app.manifest import AgentAppManifest
from metis.planning.task_contract import TaskContractV1, build_intake_task_contract
from metis.swarm.decomposer import decompose_development_plan


@dataclass(frozen=True)
class DevelopmentPackage:
    requirement: str
    app_name: str
    slug: str
    analysis: dict[str, Any]
    plan: dict[str, Any]
    tasks: dict[str, Any]
    manifest: AgentAppManifest
    implementation: dict[str, Any]
    verification: dict[str, Any]
    task_contract: TaskContractV1


def build_development_package(requirement: str, *, app_name: str) -> DevelopmentPackage:
    requirement = requirement.strip()
    app_name = app_name.strip()
    if not requirement:
        raise ValueError("developer requirement is required")
    if not app_name:
        raise ValueError("app name is required")
    slug = _slugify(app_name)
    analysis = _analysis(requirement, app_name)
    plan = _plan(requirement, app_name, slug)
    tasks = {"task_count": 0, "tasks": []}
    tasks["tasks"] = decompose_development_plan(plan)
    tasks["task_count"] = len(tasks["tasks"])
    implementation = _implementation_contract(requirement, app_name, slug)
    verification = _verification_contract(app_name, slug)
    task_contract = build_intake_task_contract(
        requirement,
        source=f"metis.develop:{slug}",
    )
    manifest = AgentAppManifest(
        name=app_name,
        subtitle="Metis-powered Agent",
        description=f"{app_name} adapted from Metis Agent Harness",
        workspace=".",
        model="glm-4.7-flash",
        profile="small",
        icon_text=app_name[:1].upper(),
        system_prompt_path=f"prompts/{slug}-system.md",
        developer_prompt_path=f"prompts/{slug}-developer.md",
    )
    return DevelopmentPackage(
        requirement,
        app_name,
        slug,
        analysis,
        plan,
        tasks,
        manifest,
        implementation,
        verification,
        task_contract,
    )


def infer_app_name(requirement: str) -> str:
    """Infer a downstream agent name from a natural-language developer request."""

    requirement = requirement.strip()
    patterns = [
        r"(?:called|named|name is|名字叫|命名为|叫做)\s+([A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff _-]{1,40})",
        r"(?:agent|智能体)\s+([A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff _-]{1,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, requirement, flags=re.I)
        if match:
            candidate = re.split(r"[,.，。;；\n]", match.group(1).strip())[0]
            candidate = re.split(r"\s+(?:for|to|that|which)\s+", candidate, flags=re.I)[0]
            candidate = re.split(r"(?:专门|用于|面向|可以)", candidate)[0]
            return candidate.strip(" -_") or "Metis Agent"
    return "Metis Agent"


def write_development_package(
    package: DevelopmentPackage,
    output_dir: str | Path,
    *,
    approved: bool = False,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_and_md(output_dir, "analysis-report", package.analysis, _analysis_markdown(package))
    _write_json_and_md(output_dir, "adaptation-plan", package.plan, _plan_markdown(package))
    _write_json_and_md(output_dir, "task-breakdown", package.tasks, _tasks_markdown(package))
    _write_json_and_md(output_dir, "implementation-contract", package.implementation, _implementation_markdown(package))
    _write_json_and_md(output_dir, "verification-checklist", package.verification, _verification_markdown(package))
    _write_json_and_md(
        output_dir,
        "task-contract",
        package.task_contract.to_dict(),
        _task_contract_markdown(package),
    )
    if approved:
        _write_approved_artifacts(package, output_dir)
    return output_dir


def _analysis(requirement: str, app_name: str) -> dict[str, Any]:
    return {
        "artifact_type": "metis_developer_analysis",
        "app_name": app_name,
        "requirement": requirement,
        "principles": [
            "Preserve the Metis harness architecture unless a requirement cannot be met through configuration, prompts, tools, or adapters.",
            "Prefer prompt, manifest, slash-command, and tool registration changes before runtime-core changes.",
            "Treat brand identity as a first-class deliverable across CLI, TUI, Web UI, backend config, Claude Code commands, and Codex commands.",
            "Require research and analysis before implementation; do not skip directly to code changes.",
            "Require user approval before applying adaptation changes.",
            "Decompose approved implementation into small tasks suitable for weaker models.",
        ],
        "metis_extension_points": [
            {
                "surface": "metis-agent.json",
                "purpose": "Single source of truth for downstream agent name, subtitle, description, workspace, model, profile, icon, and prompt paths.",
                "core_change_required": False,
            },
            {
                "surface": "prompts",
                "purpose": "Scenario behavior, evidence rules, delivery standards, and developer workflow instructions.",
                "core_change_required": False,
            },
            {
                "surface": "CLI/TUI/Web app shells",
                "purpose": "Reusable runtime interfaces that read the manifest and therefore inherit downstream branding and prompts.",
                "core_change_required": False,
            },
            {
                "surface": "slash commands",
                "purpose": "Claude Code and Codex entry commands that keep the same approved analysis-plan-task-verify workflow.",
                "core_change_required": False,
            },
            {
                "surface": "task orchestration",
                "purpose": "Fine-grained implementation tasks suitable for small models and audit checkpoints.",
                "core_change_required": False,
            },
        ],
        "research_queries": [
            f"{app_name} target domain best practices",
            f"{app_name} user workflow requirements",
            "agent harness prompt adaptation patterns",
            "small model task decomposition best practices",
        ],
        "expected_surfaces": [
            "metis-agent.json",
            f"prompts/{_slugify(app_name)}-system.md",
            f"prompts/{_slugify(app_name)}-developer.md",
            "web ui branding",
            "cli/tui labels",
            "backend manifest/config",
            ".claude/commands",
            ".codex/commands",
            "metis-dev-tasks.json",
        ],
        "approval_gate": {
            "default": "Reports and plans are written first.",
            "apply_condition": "Approved artifacts are written only after --approve or an interactive yes response.",
        },
        "fit_assessment": {
            "architecture_change_expected": False,
            "reason": "The requirement should be satisfied through manifest, prompts, slash commands, and task orchestration unless later analysis proves a missing harness capability.",
        },
    }


def _plan(requirement: str, app_name: str, slug: str) -> dict[str, Any]:
    return {
        "artifact_type": "metis_adaptation_plan",
        "app_name": app_name,
        "slug": slug,
        "requirement": requirement,
        "approval_required": True,
        "change_strategy": "prompt-first, manifest-driven, architecture-preserving",
        "phases": [
            {
                "id": "phase-1-research-and-fit-analysis",
                "goal": "Research the target domain and map user needs to existing Metis extension points.",
                "allowed_changes": ["analysis-report.md", "external-research-notes.md"],
            },
            {
                "id": "phase-2-adaptation-design",
                "goal": "Design prompt, branding, tool, command, and eval adaptations without changing core runtime architecture.",
                "allowed_changes": ["adaptation-plan.md", "metis-agent.json draft", "prompt contract draft", "slash command contract draft"],
            },
            {
                "id": "phase-3-user-approval",
                "goal": "Wait for the user to approve or revise the plan.",
                "allowed_changes": ["approval record"],
            },
            {
                "id": "phase-4-implementation",
                "goal": "Apply approved manifest, prompt, command, and task-orchestration changes.",
                "allowed_changes": [
                    "manifest",
                    "system prompt",
                    "developer prompt",
                    "Claude Code slash command",
                    "Codex slash command",
                    "developer tasks",
                    "run instructions",
                ],
            },
            {
                "id": "phase-5-verification",
                "goal": "Run focused tests, compile checks, and UI/config smoke checks.",
                "allowed_changes": ["verification checklist", "test reports", "fixes for discovered defects"],
            },
        ],
        "apply_artifacts_after_approval": [
            "metis-agent.json",
            f"prompts/{slug}-system.md",
            f"prompts/{slug}-developer.md",
            f".claude/commands/{slug}.md",
            f".codex/commands/{slug}.md",
            "metis-dev-tasks.json",
            "README.md",
            "branding.json",
            "developer-workflow.md",
            "verification-checklist.md",
            "scripts/run-cli.ps1",
            "scripts/run-tui.ps1",
            "scripts/run-web.ps1",
        ],
    }


def _implementation_contract(requirement: str, app_name: str, slug: str) -> dict[str, Any]:
    return {
        "artifact_type": "metis_development_implementation_contract",
        "app_name": app_name,
        "slug": slug,
        "requirement": requirement,
        "entrypoint": "metis develop",
        "runtime_entrypoints": [
            "metis run --manifest metis-agent.json \"<task>\"",
            "metis tui --manifest metis-agent.json",
            "metis web --manifest metis-agent.json",
        ],
        "customization_policy": {
            "default": "prompt-first, manifest-driven, architecture-preserving",
            "allowed_without_core_change": [
                "brand name",
                "subtitle",
                "description",
                "system prompt",
                "developer prompt",
                "slash command text",
                "task breakdown contract",
                "verification checklist",
            ],
            "requires_explicit_justification": [
                "runtime loop changes",
                "tool dispatcher changes",
                "provider protocol changes",
                "security policy changes",
            ],
        },
        "quality_bar": [
            "The generated package must be runnable with the reusable Metis CLI, TUI, and Web UI.",
            "The manifest must bind the downstream brand and prompt paths.",
            "Prompts must preserve evidence-backed delivery, approval gates, small-task decomposition, and truthful reporting.",
            "Claude Code and Codex commands must use the same workflow as metis develop.",
            "Every implementation task must include a verification instruction.",
        ],
    }


def _verification_contract(app_name: str, slug: str) -> dict[str, Any]:
    return {
        "artifact_type": "metis_development_verification_checklist",
        "app_name": app_name,
        "slug": slug,
        "checks": [
            "analysis-report.md exists and states the developer requirement.",
            "adaptation-plan.md exists and requires approval before implementation.",
            "task-breakdown.md exists and contains fine-grained tasks with verification steps.",
            "metis-agent.json exists after approval and contains name, prompt paths, model, profile, workspace, and icon_text.",
            f"prompts/{slug}-system.md exists and contains the downstream app name and evidence rules.",
            f"prompts/{slug}-developer.md exists and contains the architecture-preserving customization workflow.",
            f".claude/commands/{slug}.md exists and references analysis, approval, task decomposition, implementation, and verification.",
            f".codex/commands/{slug}.md exists and references analysis, approval, task decomposition, implementation, and verification.",
            "README.md explains how to run CLI, TUI, and Web UI with the generated manifest.",
            "scripts/run-cli.ps1, scripts/run-tui.ps1, and scripts/run-web.ps1 exist for developer convenience.",
        ],
        "recommended_commands": [
            "python -m compileall -q metis",
            "python -m pytest tests/unit/test_develop_workflow.py tests/unit/test_cli_eval.py tests/unit/test_app_manifest.py tests/unit/test_app_web.py -q",
            "python -m pytest -q",
        ],
    }


def _write_approved_artifacts(package: DevelopmentPackage, output_dir: Path) -> None:
    (output_dir / "metis-agent.json").write_text(
        json.dumps(package.manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    prompts_dir = output_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / f"{package.slug}-system.md").write_text(_system_prompt(package), encoding="utf-8")
    (prompts_dir / f"{package.slug}-developer.md").write_text(_developer_prompt(package), encoding="utf-8")
    (output_dir / "metis-dev-tasks.json").write_text(
        json.dumps(package.tasks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "branding.json").write_text(
        json.dumps(_branding(package), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(package), encoding="utf-8")
    (output_dir / "developer-workflow.md").write_text(_developer_workflow(package), encoding="utf-8")
    scripts_dir = output_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "run-cli.ps1").write_text(_run_script(package, "cli"), encoding="utf-8")
    (scripts_dir / "run-tui.ps1").write_text(_run_script(package, "tui"), encoding="utf-8")
    (scripts_dir / "run-web.ps1").write_text(_run_script(package, "web"), encoding="utf-8")
    for root in (".claude", ".codex"):
        command_dir = output_dir / root / "commands"
        command_dir.mkdir(parents=True, exist_ok=True)
        (command_dir / f"{package.slug}.md").write_text(_slash_command(package, root), encoding="utf-8")


def _system_prompt(package: DevelopmentPackage) -> str:
    return (
        f"# {package.app_name} System Prompt\n\n"
        f"You are {package.app_name}, a scenario-specific agent running on Metis Agent Harness.\n"
        "Your job is to satisfy the downstream user requirement while preserving Metis reliability rules.\n\n"
        "Mandatory operating rules:\n"
        "- Keep claims evidence-backed and distinguish verified facts from assumptions.\n"
        "- Prefer small, reviewable steps and explicit checkpoints for weaker models.\n"
        "- Use tools only when they are needed and report tool failures truthfully.\n"
        "- Do not claim files, tests, uploads, API calls, or research are complete unless they are actually complete.\n"
        "- Preserve approval gates for architecture-affecting changes.\n"
        "- Deliver artifacts that are usable through Metis CLI, TUI, and Web UI surfaces.\n\n"
        f"User requirement:\n{package.requirement}\n"
    )


def _developer_prompt(package: DevelopmentPackage) -> str:
    return (
        f"# {package.app_name} Developer Prompt\n\n"
        "Adapt behavior through prompts, manifests, tools, slash commands, eval contracts, and task orchestration before changing core harness architecture.\n\n"
        "Required development workflow:\n"
        "1. Understand the developer request and identify the target user, domain, artifacts, risks, and acceptance criteria.\n"
        "2. Inspect the existing Metis extension points before proposing changes.\n"
        "3. Research domain requirements when external knowledge is needed; record what was actually verified.\n"
        "4. Produce an analysis report and an adaptation plan.\n"
        "5. Wait for approval before implementation unless the developer has explicitly passed an approval flag.\n"
        "6. Decompose approved work into small tasks that a weaker model can complete reliably.\n"
        "7. Implement the approved manifest, prompt, command, UI-branding, backend-config, and verification artifacts.\n"
        "8. Run focused tests, then broader tests, then write a truthful completion report with residual risks.\n"
    )


def _slash_command(package: DevelopmentPackage, root: str) -> str:
    command_name = "Claude Code" if root == ".claude" else "Codex"
    return (
        f"# /{package.slug}\n\n"
        f"Use {package.app_name} through Metis Agent Harness in {command_name}.\n\n"
        "Required workflow:\n"
        "1. Analyze the user's request against the existing Metis architecture and this downstream agent's requirement.\n"
        "2. Prefer prompt, manifest, command, tool-registration, and eval-contract changes over core architecture changes.\n"
        "3. Produce analysis and adaptation plan before implementation.\n"
        "4. Wait for user approval unless approval was explicitly provided.\n"
        "5. Decompose approved work into fine-grained tasks and execute each task with verification.\n"
        "6. Finish with tested evidence, residual risks, and exact changed files.\n"
    )


def _branding(package: DevelopmentPackage) -> dict[str, Any]:
    return {
        "name": package.app_name,
        "slug": package.slug,
        "subtitle": package.manifest.subtitle,
        "description": package.manifest.description,
        "icon_text": package.manifest.icon_text,
        "surfaces": ["cli", "tui", "web", "claude-code", "codex"],
    }


def _readme(package: DevelopmentPackage) -> str:
    return (
        f"# {package.app_name}\n\n"
        "This downstream agent package was generated by `metis develop`.\n\n"
        "## Requirement\n\n"
        f"{package.requirement}\n\n"
        "## Run\n\n"
        "```powershell\n"
        "metis run --manifest metis-agent.json \"Describe your task here\"\n"
        "metis tui --manifest metis-agent.json\n"
        "metis web --manifest metis-agent.json\n"
        "```\n\n"
        "## Generated Surfaces\n\n"
        "- `metis-agent.json`: shared brand, runtime defaults, and prompt paths.\n"
        f"- `prompts/{package.slug}-system.md`: runtime system behavior.\n"
        f"- `prompts/{package.slug}-developer.md`: developer customization workflow.\n"
        f"- `.claude/commands/{package.slug}.md`: Claude Code command.\n"
        f"- `.codex/commands/{package.slug}.md`: Codex command.\n"
        "- `metis-dev-tasks.json`: fine-grained task plan for future adaptation work.\n"
    )


def _developer_workflow(package: DevelopmentPackage) -> str:
    return (
        f"# {package.app_name} Developer Workflow\n\n"
        "Use this package as a Metis-based downstream agent, not as a forked runtime architecture.\n\n"
        "1. Capture the developer's natural-language requirement.\n"
        "2. Inspect `metis-agent.json`, prompts, slash commands, and task files.\n"
        "3. Prefer prompt and configuration changes before core runtime changes.\n"
        "4. Write analysis and plan artifacts before implementation.\n"
        "5. Get approval.\n"
        "6. Execute small tasks from `metis-dev-tasks.json`.\n"
        "7. Verify generated files, run relevant tests, and report only what is actually proven.\n"
    )


def _run_script(package: DevelopmentPackage, mode: str) -> str:
    if mode == "cli":
        return (
            "param([string]$Task = \"Describe your task here\")\n"
            "metis run --manifest metis-agent.json $Task\n"
        )
    if mode == "tui":
        return "metis tui --manifest metis-agent.json\n"
    return "metis web --manifest metis-agent.json\n"


def _write_json_and_md(output_dir: Path, stem: str, payload: dict[str, Any], markdown: str) -> None:
    (output_dir / f"{stem}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / f"{stem}.md").write_text(markdown, encoding="utf-8")


def _analysis_markdown(package: DevelopmentPackage) -> str:
    lines = [f"# {package.app_name} Developer Analysis", "", f"Requirement: {package.requirement}", ""]
    lines.append("## Principles")
    lines.extend(f"- {item}" for item in package.analysis["principles"])
    lines.extend(["", "## Metis Extension Points"])
    for item in package.analysis["metis_extension_points"]:
        lines.extend(
            [
                f"- Surface: {item['surface']}",
                f"  Purpose: {item['purpose']}",
                f"  Core change required: {str(item['core_change_required']).lower()}",
            ]
        )
    lines.extend(["", "## Research Queries"])
    lines.extend(f"- {item}" for item in package.analysis["research_queries"])
    lines.extend(["", "## Expected Surfaces"])
    lines.extend(f"- {item}" for item in package.analysis["expected_surfaces"])
    return "\n".join(lines) + "\n"


def _plan_markdown(package: DevelopmentPackage) -> str:
    lines = [
        f"# {package.app_name} Adaptation Plan",
        "",
        f"Strategy: {package.plan['change_strategy']}",
        f"Approval required: {str(package.plan['approval_required']).lower()}",
        "",
        "## Phases",
    ]
    for phase in package.plan["phases"]:
        lines.extend(["", f"### {phase['id']}", phase["goal"], "", "Allowed changes:"])
        lines.extend(f"- {item}" for item in phase["allowed_changes"])
    lines.extend(["", "## Apply After Approval"])
    lines.extend(f"- {item}" for item in package.plan["apply_artifacts_after_approval"])
    return "\n".join(lines) + "\n"


def _implementation_markdown(package: DevelopmentPackage) -> str:
    lines = [
        f"# {package.app_name} Implementation Contract",
        "",
        f"Entrypoint: `{package.implementation['entrypoint']}`",
        "",
        "## Runtime Entrypoints",
    ]
    lines.extend(f"- `{item}`" for item in package.implementation["runtime_entrypoints"])
    lines.extend(["", "## Quality Bar"])
    lines.extend(f"- {item}" for item in package.implementation["quality_bar"])
    lines.extend(["", "## Customization Policy"])
    lines.append(f"Default: {package.implementation['customization_policy']['default']}")
    lines.extend(["", "Allowed without core change:"])
    lines.extend(f"- {item}" for item in package.implementation["customization_policy"]["allowed_without_core_change"])
    lines.extend(["", "Requires explicit justification:"])
    lines.extend(f"- {item}" for item in package.implementation["customization_policy"]["requires_explicit_justification"])
    return "\n".join(lines) + "\n"


def _verification_markdown(package: DevelopmentPackage) -> str:
    lines = [f"# {package.app_name} Verification Checklist", "", "## Checks"]
    lines.extend(f"- [ ] {item}" for item in package.verification["checks"])
    lines.extend(["", "## Recommended Commands"])
    lines.extend(f"- `{item}`" for item in package.verification["recommended_commands"])
    return "\n".join(lines) + "\n"


def _task_contract_markdown(package: DevelopmentPackage) -> str:
    return f"# {package.app_name} Task Contract\n\n```text\n{package.task_contract.to_prompt()}\n```\n"


def _tasks_markdown(package: DevelopmentPackage) -> str:
    lines = [f"# {package.app_name} Development Tasks", "", f"Task count: {package.tasks['task_count']}", ""]
    for task in package.tasks["tasks"]:
        lines.extend(
            [
                f"## {task['id']}: {task['title']}",
                "",
                f"- Phase: {task['phase_id']}",
                f"- Surface: {task['surface']}",
                f"- Verification: {task['verification']}",
                "",
                task["instruction"],
                "",
            ]
        )
    return "\n".join(lines)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "metis-agent"
