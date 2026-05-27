"""Tests for trace renderer."""

from __future__ import annotations

from metis.viz.trace_renderer import render_trace_ascii, render_trace_mermaid, render_trace_timeline


def test_render_trace_timeline_empty():
    result = render_trace_timeline([])
    assert "No trace events" in result


def test_render_trace_timeline_with_events():
    events = [
        {"index": 0, "event_type": "agent.start", "status": "started", "session_id": "s1", "attributes": {"max_turns": 5}},
        {"index": 1, "event_type": "model.request", "status": "started", "turn": 1, "session_id": "s1", "attributes": {"tool_count": 3}},
        {"index": 2, "event_type": "tool.request", "status": "started", "turn": 1, "tool_name": "read_file", "session_id": "s1", "attributes": {}},
        {"index": 3, "event_type": "tool.result", "status": "ok", "turn": 1, "tool_name": "read_file", "session_id": "s1", "attributes": {"failed": False}},
    ]
    result = render_trace_timeline(events, "s1")
    assert "agent.start" in result
    assert "model.request" in result
    assert "read_file" in result
    assert "max_turns=5" in result


def test_render_trace_mermaid_basic():
    events = [
        {"index": 0, "event_type": "agent.start", "status": "started", "session_id": "s1"},
        {"index": 1, "event_type": "model.request", "status": "started", "turn": 1, "session_id": "s1"},
        {"index": 2, "event_type": "model.response", "status": "ok", "turn": 1, "session_id": "s1", "attributes": {"tool_call_count": 2}},
        {"index": 3, "event_type": "tool.request", "status": "started", "turn": 1, "tool_name": "read_file", "session_id": "s1"},
        {"index": 4, "event_type": "tool.result", "status": "ok", "turn": 1, "tool_name": "read_file", "session_id": "s1"},
        {"index": 5, "event_type": "finalization.result", "status": "ok", "session_id": "s1"},
    ]
    result = render_trace_mermaid(events, "s1")
    assert "sequenceDiagram" in result
    assert "User->>Agent" in result
    assert "Agent->>Model" in result
    assert "read_file" in result


def test_render_trace_ascii_basic():
    events = [
        {"index": 0, "event_type": "agent.start", "status": "started"},
        {"index": 1, "event_type": "model.request", "status": "started", "turn": 1},
    ]
    result = render_trace_ascii(events)
    assert "Trace Timeline" in result
    assert "agent.start" in result
    assert "model.request" in result


def test_render_trace_ascii_empty():
    result = render_trace_ascii([])
    assert result == "(no trace events)"
