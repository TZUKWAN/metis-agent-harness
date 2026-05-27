"""Tests for report generator."""

from __future__ import annotations

from metis.runtime.response import AgentRunResult, ToolResult
from metis.viz.report import generate_html_report, generate_json_report


def test_generate_html_report_basic():
    result = AgentRunResult(
        status="final",
        final_text="Hello world",
        turns_used=2,
        tool_results=[
            ToolResult(tool_name="read_file", content="data", status="ok"),
        ],
        trace_events=[
            {"index": 0, "event_type": "agent.start", "status": "started"},
        ],
        usage={"total_tokens": 42},
    )
    html = generate_html_report(result, session_id="s1", title="Test Report")
    assert "<!DOCTYPE html>" in html
    assert "Test Report" in html
    assert "Hello world" in html
    assert "read_file" in html
    assert "42" in html
    assert "agent.start" in html
    assert "sequenceDiagram" in html  # Mermaid seq diagram
    assert "flowchart TD" in html  # Mermaid flowchart


def test_generate_html_report_with_errors():
    result = AgentRunResult(
        status="blocked",
        final_text="",
        turns_used=1,
        errors=["Something went wrong"],
    )
    html = generate_html_report(result)
    assert "Something went wrong" in html
    assert "blocked" in html


def test_generate_html_report_empty():
    result = AgentRunResult(status="final")
    html = generate_html_report(result)
    assert "<!DOCTYPE html>" in html
    assert "0" in html  # tool count


def test_generate_json_report():
    result = AgentRunResult(
        status="final",
        turns_used=1,
        tool_results=[
            ToolResult(tool_name="read_file", content="data", status="ok"),
        ],
        usage={"total_tokens": 10},
    )
    json_str = generate_json_report(result, session_id="s1")
    assert '"status": "final"' in json_str
    assert '"session_id": "s1"' in json_str
    assert '"tool_count": 1' in json_str
