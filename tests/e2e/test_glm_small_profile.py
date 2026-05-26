"""E2E test: GLM-4.7-Flash with small profile (strict_output_soft=True)."""

import os

import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry

BASE_URL = os.getenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
API_KEY = os.getenv("METIS_API_KEY", "")
MODEL = os.getenv("METIS_MODEL", "glm-4.7-flash")

pytestmark = pytest.mark.skipif(not API_KEY, reason="METIS_API_KEY not set")


@pytest.mark.asyncio
async def test_glm_small_profile_read_file(tmp_path):
    """GLM-4.7-Flash should complete a read_file task with small profile."""
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "hello.txt").write_text("Hello from Metis!", encoding="utf-8")

    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("glm-small-e2e")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))

    provider = OpenAICompatibleProvider(base_url=BASE_URL, api_key=API_KEY, model=MODEL)
    loop = AgentLoop(provider=provider, registry=registry, state=state, workspace=str(workspace), profile="small")

    result = await loop.run(
        AgentRunRequest(
            session_id=session_id,
            messages=[{"role": "user", "content": "Read the file hello.txt and tell me what's in it."}],
            allowed_tools=["read_file"],
            max_turns=6,
        )
    )

    assert result.status == "final", f"Expected final, got {result.status}. Errors: {result.errors}"
    assert result.turns_used <= 6
    assert "hello.txt" in result.final_text.lower() or len(result.tool_results) > 0


@pytest.mark.asyncio
async def test_glm_small_profile_write_file(tmp_path):
    """GLM-4.7-Flash should complete a write_file task with small profile."""
    workspace = tmp_path / "project"
    workspace.mkdir()

    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("glm-small-write")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))

    provider = OpenAICompatibleProvider(base_url=BASE_URL, api_key=API_KEY, model=MODEL)
    loop = AgentLoop(provider=provider, registry=registry, state=state, workspace=str(workspace), profile="small")

    result = await loop.run(
        AgentRunRequest(
            session_id=session_id,
            messages=[{"role": "user", "content": "Create a file called output.txt with the content 'Test output from Metis'."}],
            allowed_tools=["write_file"],
            max_turns=6,
        )
    )

    assert result.status == "final", f"Expected final, got {result.status}. Errors: {result.errors}"
    assert (workspace / "output.txt").exists(), "output.txt was not created"
    content = (workspace / "output.txt").read_text(encoding="utf-8")
    assert "Metis" in content, f"File content doesn't contain 'Metis': {content}"
