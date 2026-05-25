from pathlib import Path

from metis.runtime.budgets import BudgetConfig
from metis.tools.result_store import PERSISTED_OUTPUT_TAG, ToolResultStore


def test_tool_result_store_inlines_small_output(tmp_path: Path):
    store = ToolResultStore(tmp_path, BudgetConfig(per_tool_chars=10, preview_chars=5))

    result = store.maybe_persist(content="short", tool_name="echo", tool_call_id="c1")

    assert result.persisted is False
    assert result.content == "short"


def test_tool_result_store_persists_large_output(tmp_path: Path):
    store = ToolResultStore(tmp_path, BudgetConfig(per_tool_chars=10, preview_chars=6))

    result = store.maybe_persist(content="0123456789abcdef", tool_name="echo", tool_call_id="c1")

    assert result.persisted is True
    assert result.path is not None
    assert Path(result.path).read_text(encoding="utf-8") == "0123456789abcdef"
    assert PERSISTED_OUTPUT_TAG in result.content
    assert "Preview:" in result.content


def test_tool_result_store_creates_output_dir_lazily(tmp_path: Path):
    store = ToolResultStore(tmp_path, BudgetConfig(per_tool_chars=100, preview_chars=5))

    assert not (tmp_path / ".metis" / "tool-results").exists()
    store.maybe_persist(content="small", tool_name="echo", tool_call_id="c1")
    assert not (tmp_path / ".metis" / "tool-results").exists()
