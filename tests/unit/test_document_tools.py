"""Unit tests for document generation tools."""

import pytest

from metis.tools.document_tools import register_document_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


@pytest.fixture
def registry(tmp_path):
    reg = ToolRegistry()
    register_document_tools(reg, workspace=str(tmp_path))
    return reg


@pytest.fixture
def context():
    return ToolContext(session_id="test", workspace=".", allowed_tools=None)


def test_flowchart_tool_registered(registry):
    assert "create_flowchart" in registry.list_tools()


def test_spreadsheet_tool_registered(registry):
    assert "create_spreadsheet" in registry.list_tools()


def test_document_tool_registered(registry):
    assert "create_document" in registry.list_tools()


def test_presentation_tool_registered(registry):
    assert "create_presentation" in registry.list_tools()


def test_create_flowchart_basic(registry, context, tmp_path):
    tool = registry.get("create_flowchart")
    result = tool.handler(
        {
            "path": "flow.md",
            "title": "Test Flow",
            "direction": "LR",
            "nodes": [
                {"id": "A", "label": "Start"},
                {"id": "B", "label": "End", "shape": "rounded"},
            ],
            "edges": [{"from": "A", "to": "B", "label": "next"}],
        },
        context,
    )
    assert result["format"] == "mermaid"
    content = (tmp_path / "flow.md").read_text(encoding="utf-8")
    assert "flowchart LR" in content
    assert "A[Start]" in content
    assert "B(End)" in content
    assert "A -->|next| B" in content


def test_create_flowchart_diamond_node(registry, context, tmp_path):
    tool = registry.get("create_flowchart")
    result = tool.handler(
        {
            "path": "decision.md",
            "nodes": [{"id": "D", "label": "Yes?", "shape": "diamond"}],
        },
        context,
    )
    content = (tmp_path / "decision.md").read_text(encoding="utf-8")
    assert "D{Yes?}" in content


def test_create_flowchart_circle_node(registry, context, tmp_path):
    tool = registry.get("create_flowchart")
    result = tool.handler(
        {
            "path": "circle.md",
            "nodes": [{"id": "C", "label": "Start", "shape": "circle"}],
        },
        context,
    )
    content = (tmp_path / "circle.md").read_text(encoding="utf-8")
    assert "C((Start))" in content


def test_create_spreadsheet_basic(registry, context, tmp_path):
    tool = registry.get("create_spreadsheet")
    result = tool.handler(
        {
            "path": "data.xlsx",
            "headers": ["Name", "Score"],
            "rows": [["Alice", 95], ["Bob", 87]],
        },
        context,
    )
    assert result["format"] == "xlsx"
    assert result["rows"] == 2
    assert result["columns"] == 2
    assert (tmp_path / "data.xlsx").exists()


def test_create_document_basic(registry, context, tmp_path):
    tool = registry.get("create_document")
    result = tool.handler(
        {
            "path": "report.docx",
            "title": "Test Report",
            "sections": [
                {"heading": "Introduction", "body": "This is the intro.", "level": 1},
                {"heading": "Details", "body": "More details here.", "level": 2},
            ],
        },
        context,
    )
    assert result["format"] == "docx"
    assert result["sections"] == 2
    assert (tmp_path / "report.docx").exists()


def test_create_document_empty(registry, context, tmp_path):
    tool = registry.get("create_document")
    result = tool.handler({"path": "empty.docx"}, context)
    assert result["format"] == "docx"
    assert (tmp_path / "empty.docx").exists()


def test_create_presentation_basic(registry, context, tmp_path):
    tool = registry.get("create_presentation")
    result = tool.handler(
        {
            "path": "slides.pptx",
            "slides": [
                {"title": "Welcome", "body": "Introduction to Metis"},
                {"title": "Features", "body": "Key capabilities"},
            ],
        },
        context,
    )
    assert result["format"] == "pptx"
    assert result["slides"] == 2
    assert (tmp_path / "slides.pptx").exists()


def test_flowchart_creates_parent_dirs(registry, context, tmp_path):
    tool = registry.get("create_flowchart")
    result = tool.handler({"path": "sub/dir/flow.md", "nodes": [{"id": "A", "label": "X"}]}, context)
    assert (tmp_path / "sub" / "dir" / "flow.md").exists()


def test_spreadsheet_creates_parent_dirs(registry, context, tmp_path):
    tool = registry.get("create_spreadsheet")
    result = tool.handler(
        {"path": "output/data.xlsx", "headers": ["A"], "rows": [[1]]}, context
    )
    assert (tmp_path / "output" / "data.xlsx").exists()
