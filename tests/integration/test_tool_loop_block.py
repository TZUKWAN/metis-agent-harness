import pytest

from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.guardrails import ToolCallGuardrailController
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_dispatcher_blocks_repeated_failed_tool_call():
    registry = ToolRegistry()

    def fail(args, ctx):
        raise RuntimeError("boom")

    registry.register(ToolSpec("fail", "Fail", {"type": "object"}, fail))
    dispatcher = ToolDispatcher(registry, guardrails=ToolCallGuardrailController(max_exact_failures=1))
    call = ToolCall(name="fail", arguments={"x": 1}, id="c1")

    first = await dispatcher.dispatch(call)
    second = await dispatcher.dispatch(call)

    assert first.status == "error"
    assert second.status == "blocked"
    assert "Repeated failed call" in second.error
