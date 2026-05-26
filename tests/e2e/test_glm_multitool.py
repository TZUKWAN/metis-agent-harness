"""E2E test: GLM-4.7-Flash multi-tool task with document generation."""

import os

import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest
from metis.state.sqlite_store import SQLiteStateStore
from metis.tools.builtin import register_builtin_tools
from metis.tools.document_tools import register_document_tools
from metis.tools.registry import ToolRegistry
from metis.tools.workspace_tools import register_workspace_tools

BASE_URL = os.getenv("METIS_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
API_KEY = os.getenv("METIS_API_KEY", "")
MODEL = os.getenv("METIS_MODEL", "glm-4.7-flash")

pytestmark = pytest.mark.skipif(not API_KEY, reason="METIS_API_KEY not set")


@pytest.mark.asyncio
async def test_glm_multitool_explore_and_report(tmp_path):
    """GLM should explore workspace, read files, and create a document."""
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "app.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
    (workspace / "src" / "utils.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    (workspace / "README.md").write_text("# My Project\nA demo project.", encoding="utf-8")

    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("glm-multitool")
    registry = ToolRegistry()
    register_builtin_tools(registry, workspace=str(workspace))
    register_workspace_tools(registry, workspace=str(workspace))
    register_document_tools(registry, workspace=str(workspace))

    provider = OpenAICompatibleProvider(base_url=BASE_URL, api_key=API_KEY, model=MODEL)
    loop = AgentLoop(provider=provider, registry=registry, state=state, workspace=str(workspace), profile="small")

    result = await loop.run(
        AgentRunRequest(
            session_id=session_id,
            messages=[{"role": "user", "content": "Explore this project and create a Word document called summary.docx describing the project structure."}],
            max_turns=10,
        )
    )

    assert result.status == "final", f"Expected final, got {result.status}. Errors: {result.errors}"
    assert result.turns_used <= 10


@pytest.mark.asyncio
async def test_glm_flowchart_generation(tmp_path):
    """GLM should create a flowchart from a description."""
    workspace = tmp_path / "project"
    workspace.mkdir()

    state = SQLiteStateStore(tmp_path / "state.db")
    session_id = state.create_session("glm-flowchart")
    registry = ToolRegistry()
    register_document_tools(registry, workspace=str(workspace))

    provider = OpenAICompatibleProvider(base_url=BASE_URL, api_key=API_KEY, model=MODEL)
    loop = AgentLoop(provider=provider, registry=registry, state=state, workspace=str(workspace), profile="small")

    result = await loop.run(
        AgentRunRequest(
            session_id=session_id,
            messages=[{"role": "user", "content": "Create a flowchart called login_flow.md showing a login process: Start -> Enter Credentials -> Validate -> Success (rounded) or Error (diamond) -> End"}],
            max_turns=6,
        )
    )

    assert result.status == "final", f"Expected final, got {result.status}. Errors: {result.errors}"
