"""Tests for tool flow renderer."""

from __future__ import annotations

from metis.viz.tool_flow import render_tool_flow_ascii, render_tool_flow_mermaid, render_tool_summary_table


def test_render_tool_flow_mermaid_empty():
    result = render_tool_flow_mermaid([])
    assert result == ""


def test_render_tool_flow_mermaid_ok_tools():
    tools = [
        {"name": "read_file", "status": "ok"},
        {"name": "write_file", "status": "ok"},
    ]
    result = render_tool_flow_mermaid(tools)
    assert "flowchart TD" in result
    assert "read_file" in result
    assert "write_file" in result
    assert "fill:#d4edda" in result


def test_render_tool_flow_mermaid_error_tool():
    tools = [
        {"name": "read_file", "status": "ok"},
        {"name": "bad_cmd", "status": "error", "error": "command failed"},
    ]
    result = render_tool_flow_mermaid(tools)
    assert "bad_cmd" in result
    assert "fill:#f8d7da" in result


def test_render_tool_flow_mermaid_blocked_tool():
    tools = [
        {"name": "dangerous", "status": "blocked"},
    ]
    result = render_tool_flow_mermaid(tools)
    assert "dangerous" in result
    assert "fill:#fff3cd" in result


def test_render_tool_flow_ascii_basic():
    tools = [
        {"name": "read_file", "status": "ok"},
        {"name": "write_file", "status": "ok"},
    ]
    result = render_tool_flow_ascii(tools)
    assert "read_file" in result
    assert "write_file" in result


def test_render_tool_flow_ascii_empty():
    result = render_tool_flow_ascii([])
    assert result == "(no tool calls)"


def test_render_tool_summary_table():
    tools = [
        {"name": "read_file", "status": "ok", "error": None, "metadata": {"size": 100}},
        {"name": "bad_cmd", "status": "error", "error": "failed", "metadata": {}},
    ]
    result = render_tool_summary_table(tools)
    assert "read_file" in result
    assert "bad_cmd" in result
    assert "failed" in result
    assert "<table" in result
