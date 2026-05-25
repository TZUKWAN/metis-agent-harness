from metis.planning.models import Goal, Step
from metis.planning.task_contract import TaskContractV1, build_intake_task_contract, build_task_contract


def test_small_task_contract_is_step_scoped():
    goal = Goal(id="g", session_id="s", objective="Build Metis")
    step = Step(
        id="st",
        plan_id="p",
        order_index=1,
        title="Create hooks",
        action="Implement HookBus",
        expected_output="hooks.py",
        verification_method="pytest tests/unit/test_hooks.py",
        done_condition="hook tests pass",
        allowed_tools=["write_file", "run_shell"],
    )

    contract = build_task_contract(goal, step, model_profile="small")

    assert "Execute exactly one step" in contract
    assert "Build Metis" in contract
    assert "Create hooks" in contract
    assert "write_file, run_shell" in contract
    assert "Do not invent" in contract


def test_task_contract_v1_has_stable_hash_and_prompt():
    contract = TaskContractV1(
        objective="Build a report",
        deliverables=["report.md"],
        acceptance_criteria=["report exists"],
        evidence_requirements=["file evidence"],
    )

    assert contract.contract_hash() == TaskContractV1(
        objective="Build a report",
        deliverables=["report.md"],
        acceptance_criteria=["report exists"],
        evidence_requirements=["file evidence"],
    ).contract_hash()
    prompt = contract.to_prompt()
    assert "Metis task contract v1" in prompt
    assert "Build a report" in prompt
    assert "report exists" in prompt
    assert contract.contract_hash() in prompt


def test_build_intake_task_contract_sets_truthfulness_defaults():
    contract = build_intake_task_contract("Fix the project", allowed_tools=["run_shell"])

    assert contract.objective == "Fix the project"
    assert contract.allowed_tools == ["run_shell"]
    assert any("completion" in item for item in contract.acceptance_criteria)
    assert any("exact command" in item for item in contract.evidence_requirements)
