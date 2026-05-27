"""Tests for Swarm Coordinator structured orchestration."""

from __future__ import annotations

import asyncio

import pytest

from metis.swarm.context import SharedContext
from metis.swarm.hub import _extract_json_block, _parse_coordinator_output
from metis.swarm.models import AgentEntry
from metis.swarm.schemas import TaskAssignment


# ---- _extract_json_block ----

def test_extract_json_block_markdown_json() -> None:
    text = 'Some text\n```json\n{"a": 1}\n```\nMore text'
    assert _extract_json_block(text) == '{"a": 1}'


def test_extract_json_block_plain_markdown() -> None:
    text = 'Some text\n```\n{"b": 2}\n```\nMore text'
    assert _extract_json_block(text) == '{"b": 2}'


def test_extract_json_block_raw() -> None:
    text = 'prefix {"c": 3} suffix'
    assert _extract_json_block(text) == '{"c": 3}'


def test_extract_json_block_no_json() -> None:
    assert _extract_json_block("just plain text") is None


def test_extract_json_block_empty() -> None:
    assert _extract_json_block("") is None


# ---- _parse_coordinator_output ----

def test_parse_coordinator_json_output() -> None:
    agents = [
        AgentEntry(id="a1", name="Coder", path="/tmp", manifest_path="/tmp/m.json", capabilities=["code"]),
        AgentEntry(id="a2", name="Writer", path="/tmp", manifest_path="/tmp/m.json", capabilities=["writing"]),
    ]
    text = '''
    {
      "tasks": [
        {"agent_id": "a1", "agent_name": "Coder", "task": "write code", "priority": 5},
        {"agent_id": "a2", "agent_name": "Writer", "task": "write docs", "priority": 3, "capabilities_needed": ["writing"]}
      ],
      "dependencies": {"1": [0]},
      "reasoning": "Code first, then docs"
    }
    '''
    decomp = _parse_coordinator_output(text, agents)
    assert len(decomp.tasks) == 2
    assert decomp.tasks[0].agent_id == "a1"
    assert decomp.tasks[0].task == "write code"
    assert decomp.tasks[1].agent_id == "a2"
    assert decomp.dependencies == {"1": [0]}
    assert "Code first" in decomp.reasoning


def test_parse_coordinator_fallback_legacy() -> None:
    agents = [
        AgentEntry(id="a1", name="Coder", path="/tmp", manifest_path="/tmp/m.json"),
        AgentEntry(id="a2", name="Writer", path="/tmp", manifest_path="/tmp/m.json"),
    ]
    text = "Here is the decomposition:\nCoder: implement auth\nWriter: write README"
    decomp = _parse_coordinator_output(text, agents)
    assert len(decomp.tasks) == 2
    ids = {t.agent_id for t in decomp.tasks}
    assert ids == {"a1", "a2"}
    tasks = {t.task for t in decomp.tasks}
    assert "implement auth" in tasks
    assert "write README" in tasks


def test_parse_coordinator_fallback_no_match() -> None:
    agents = [AgentEntry(id="a1", name="Coder", path="/tmp", manifest_path="/tmp/m.json")]
    text = "No assignments here"
    decomp = _parse_coordinator_output(text, agents)
    assert decomp.tasks == []


# ---- SharedContext ----

@pytest.mark.asyncio
async def test_shared_context_basic() -> None:
    ctx = SharedContext()
    await ctx.set("key1", "value1")
    assert await ctx.get("key1") == "value1"
    assert await ctx.get("missing") is None
    assert await ctx.get("missing", "default") == "default"


@pytest.mark.asyncio
async def test_shared_context_get_all() -> None:
    ctx = SharedContext()
    await ctx.set("a", 1)
    await ctx.set("b", 2)
    all_data = await ctx.get_all()
    assert all_data == {"a": 1, "b": 2}


@pytest.mark.asyncio
async def test_shared_context_clear() -> None:
    ctx = SharedContext()
    await ctx.set("x", 10)
    await ctx.clear()
    assert await ctx.get("x") is None


@pytest.mark.asyncio
async def test_shared_context_concurrent() -> None:
    ctx = SharedContext()

    async def writer(n: int) -> None:
        for i in range(10):
            await ctx.set(f"key_{n}", i)

    await asyncio.gather(writer(0), writer(1), writer(2))
    all_data = await ctx.get_all()
    assert len(all_data) == 3
    assert all(v in range(10) for v in all_data.values())
