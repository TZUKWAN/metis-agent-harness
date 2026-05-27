import pytest

from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.policy import CommandClassifier, ToolPolicyEngine
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolSpec


def test_command_classifier_blocks_destructive_shell_command():
    decision = CommandClassifier().classify("rm -rf .")

    assert decision.blocked is True
    assert decision.risk_level == "destructive"


def test_command_classifier_requires_approval_for_external_publish():
    decision = CommandClassifier().classify("git push origin main")

    assert decision.approval_required is True
    assert decision.risk_level == "external_publish"


@pytest.mark.asyncio
async def test_dispatcher_blocks_dangerous_run_shell_before_handler():
    called = False

    def handler(args, ctx):
        nonlocal called
        called = True
        return {"exit_code": 0}

    registry = ToolRegistry()
    registry.register(ToolSpec("run_shell", "Run", {"type": "object"}, handler, side_effect="write"))
    dispatcher = ToolDispatcher(registry, policy_engine=ToolPolicyEngine())

    result = await dispatcher.dispatch(ToolCall(name="run_shell", arguments={"command": "rm -rf ."}, id="c1"), ToolContext())

    assert called is False
    assert result.status == "blocked"
    assert result.metadata["risk_level"] == "destructive"
    assert result.metadata["failure_type"] == "unsafe_command"
    assert result.metadata["recoverable"] is False
    assert result.metadata["retry_allowed"] is False


@pytest.mark.asyncio
async def test_dispatcher_marks_allowed_policy_metadata():
    registry = ToolRegistry()
    registry.register(ToolSpec("read_file", "Read", {"type": "object"}, lambda args, ctx: {"ok": True}))
    dispatcher = ToolDispatcher(registry, policy_engine=ToolPolicyEngine())

    result = await dispatcher.dispatch(ToolCall(name="read_file", arguments={}, id="c1"), ToolContext())

    assert result.status == "ok"
    assert result.metadata["policy_decision"] == "allow"
    assert result.metadata["risk_level"] == "safe_read"


@pytest.mark.asyncio
async def test_dispatcher_marks_approval_required_repair_metadata():
    called = False

    def handler(args, ctx):
        nonlocal called
        called = True
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(ToolSpec("run_shell", "Run", {"type": "object"}, handler, side_effect="write"))
    dispatcher = ToolDispatcher(registry, policy_engine=ToolPolicyEngine())

    result = await dispatcher.dispatch(
        ToolCall(name="run_shell", arguments={"command": "git push origin main"}, id="c1"),
        ToolContext(),
    )

    assert called is False
    assert result.status == "blocked"
    assert result.metadata["failure_type"] == "approval_required"
    assert result.metadata["recoverable"] is False
    assert "Do not bypass approval" in result.metadata["repair_instruction"]
