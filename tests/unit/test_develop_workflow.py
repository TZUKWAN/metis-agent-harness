import json

from metis.develop.workflow import build_development_package, infer_app_name, write_development_package


def test_development_package_requires_approval_and_decomposes_fine_tasks():
    package = build_development_package(
        "Build a legal contract review agent with strict citation requirements.",
        app_name="Lexi Review",
    )

    assert package.app_name == "Lexi Review"
    assert package.plan["approval_required"] is True
    assert package.plan["change_strategy"] == "prompt-first, manifest-driven, architecture-preserving"
    assert package.tasks["task_count"] >= 10
    assert any(task["surface"] == "metis-agent.json draft" for task in package.tasks["tasks"])
    assert any(".claude" in item for item in package.plan["apply_artifacts_after_approval"])
    assert any(".codex" in item for item in package.plan["apply_artifacts_after_approval"])
    assert package.manifest.system_prompt_path == "prompts/lexi-review-system.md"
    assert package.implementation["entrypoint"] == "metis develop"
    assert "metis web --manifest metis-agent.json" in package.implementation["runtime_entrypoints"]


def test_write_development_package_without_approval_writes_only_reports(tmp_path):
    package = build_development_package("Build a finance agent.", app_name="Finance Copilot")

    output_dir = write_development_package(package, tmp_path / "dev", approved=False)

    assert (output_dir / "analysis-report.md").exists()
    assert (output_dir / "adaptation-plan.md").exists()
    assert (output_dir / "task-breakdown.md").exists()
    assert (output_dir / "implementation-contract.md").exists()
    assert (output_dir / "verification-checklist.md").exists()
    assert (output_dir / "task-contract.md").exists()
    assert not (output_dir / "metis-agent.json").exists()
    assert not (output_dir / ".claude" / "commands" / "finance-copilot.md").exists()


def test_write_development_package_with_approval_writes_brand_and_commands(tmp_path):
    package = build_development_package("Build a finance agent.", app_name="Finance Copilot")

    output_dir = write_development_package(package, tmp_path / "dev", approved=True)

    manifest = json.loads((output_dir / "metis-agent.json").read_text(encoding="utf-8"))
    tasks = json.loads((output_dir / "metis-dev-tasks.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "Finance Copilot"
    assert manifest["system_prompt_path"] == "prompts/finance-copilot-system.md"
    assert manifest["developer_prompt_path"] == "prompts/finance-copilot-developer.md"
    assert (output_dir / "prompts" / "finance-copilot-system.md").exists()
    assert (output_dir / "README.md").exists()
    assert (output_dir / "branding.json").exists()
    assert (output_dir / "developer-workflow.md").exists()
    assert (output_dir / "scripts" / "run-cli.ps1").exists()
    assert (output_dir / "scripts" / "run-tui.ps1").exists()
    assert (output_dir / "scripts" / "run-web.ps1").exists()
    assert (output_dir / ".claude" / "commands" / "finance-copilot.md").exists()
    assert (output_dir / ".codex" / "commands" / "finance-copilot.md").exists()
    assert tasks["task_count"] == package.tasks["task_count"]


def test_infer_app_name_from_natural_language_request():
    assert infer_app_name("我要做一个智能体，名字叫 合同审查官，专门审合同") == "合同审查官"
    assert infer_app_name("Build an agent called Grant Builder for nonprofit proposals") == "Grant Builder"
