import pytest

from metis.context.engine import ContextEngine
from metis.providers.fake import FakeProvider
from metis.runtime.budgets import BudgetConfig
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_loop_sends_compressed_context_to_provider():
    provider = FakeProvider(
        [{"content": '{"status":"done","summary":"done","evidence_refs":[],"artifact_refs":[],"next_action":""}'}]
    )
    engine = ContextEngine(budget=BudgetConfig(model_context_tokens=100, context_threshold=0.5), chars_per_token=1)
    loop = AgentLoop(provider=provider, registry=ToolRegistry(), context_engine=engine)
    messages = [{"role": "user", "content": "x" * 40} for _ in range(10)]

    result = await loop.run(AgentRunRequest(messages=messages, max_turns=1))

    assert result.status == "final"
    sent_messages = provider.calls[0]["messages"]
    assert len(sent_messages) < len(messages)
    assert any(message.get("metadata", {}).get("metis_context_summary") for message in sent_messages)
