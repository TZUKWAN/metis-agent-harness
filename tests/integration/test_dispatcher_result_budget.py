from pathlib import Path

import pytest

from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.runtime.budgets import BudgetConfig
from metis.runtime.response import ToolCall
from metis.tools.dispatcher import ToolDispatcher
from metis.tools.registry import ToolRegistry
from metis.tools.result_store import PERSISTED_OUTPUT_TAG, ToolResultStore
from metis.tools.spec import ToolSpec


@pytest.mark.asyncio
async def test_dispatcher_persists_large_tool_result(tmp_path: Path):
    registry = ToolRegistry()
    registry.register(ToolSpec("large", "Large", {"type": "object"}, lambda args, ctx: "x" * 30))
    hooks = HookBus()
    events = []
    hooks.register(EventType.TOOL_RESULT_PERSISTED, lambda ctx: events.append(ctx) or ctx)
    dispatcher = ToolDispatcher(
        registry,
        hooks,
        ToolResultStore(tmp_path, BudgetConfig(per_tool_chars=10, preview_chars=5)),
    )

    result = await dispatcher.dispatch(ToolCall(name="large", arguments={}, id="c1"))

    assert result.status == "ok"
    assert result.metadata["persisted"] is True
    assert result.metadata["original_size"] == 30
    assert PERSISTED_OUTPUT_TAG in result.content
    assert events and events[0]["tool"] == "large"
