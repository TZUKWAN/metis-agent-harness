"""Render agent trace events into visual formats."""

from __future__ import annotations

import html
from typing import Any


def render_trace_timeline(trace_events: list[dict[str, Any]], session_id: str = "") -> str:
    """Render trace events as an HTML timeline."""
    if not trace_events:
        return "<p>No trace events.</p>"

    lines: list[str] = [
        '<div class="metis-trace-timeline">',
        '  <style>',
        '    .metis-trace-timeline { font-family: monospace; font-size: 13px; }',
        '    .metis-trace-event { border-left: 3px solid #ccc; padding: 4px 8px; margin: 2px 0; }',
        '    .metis-trace-event.ok { border-left-color: #28a745; }',
        '    .metis-trace-event.error { border-left-color: #dc3545; }',
        '    .metis-trace-event.blocked { border-left-color: #fd7e14; }',
        '    .metis-trace-event.started { border-left-color: #6c757d; }',
        '    .metis-trace-event-header { color: #495057; font-weight: bold; }',
        '    .metis-trace-event-attrs { color: #6c757d; font-size: 11px; margin-left: 16px; }',
        '  </style>',
    ]

    for event in trace_events:
        status = event.get("status", "")
        event_type = event.get("event_type", "unknown")
        turn = event.get("turn")
        tool_name = event.get("tool_name", "")
        ev_id = event.get("event_id", "")
        attrs = event.get("attributes", {})

        status_class = status if status in ("ok", "error", "blocked", "started") else ""
        header_parts = [f"#{event.get('index', 0)} {event_type}"]
        if turn is not None:
            header_parts.append(f"turn={turn}")
        if tool_name:
            header_parts.append(f"tool={tool_name}")
        if status:
            header_parts.append(f"status={status}")

        lines.append(f'  <div class="metis-trace-event {status_class}">')
        lines.append(f'    <div class="metis-trace-event-header">{" | ".join(header_parts)}</div>')
        if attrs:
            attr_lines = []
            for key, value in attrs.items():
                if key in ("messages", "result", "content", "stderr", "stdout"):
                    continue  # Skip large fields
                val_str = _format_attr_value(value)
                attr_lines.append(f"{key}={val_str}")
            if attr_lines:
                lines.append(f'    <div class="metis-trace-event-attrs">{" | ".join(attr_lines)}</div>')
        lines.append("  </div>")

    lines.append("</div>")
    return "\n".join(lines)


def render_trace_mermaid(trace_events: list[dict[str, Any]], session_id: str = "") -> str:
    """Render trace events as a Mermaid sequence diagram."""
    if not trace_events:
        return ""

    lines: list[str] = ["sequenceDiagram"]
    participant_order: list[str] = ["User", "Agent", "Model", "Tools"]
    seen: set[str] = set()

    for event in trace_events:
        etype = event.get("event_type", "")
        turn = event.get("turn", 0)
        tool_name = event.get("tool_name", "")
        status = event.get("status", "")

        if etype == "agent.start":
            lines.append(f"    User->>Agent: start session={html.escape(session_id)[:20]}")
        elif etype == "model.request":
            lines.append(f"    Agent->>Model: request (turn {turn})")
        elif etype == "model.response":
            tc = event.get("attributes", {}).get("tool_call_count", 0)
            lines.append(f"    Model-->>Agent: response tools={tc}")
        elif etype == "tool.request" and tool_name:
            if tool_name not in seen:
                seen.add(tool_name)
                participant_order.insert(3, tool_name)
            lines.append(f"    Agent->>{tool_name}: call")
        elif etype == "tool.result" and tool_name:
            if tool_name not in seen:
                seen.add(tool_name)
                participant_order.insert(3, tool_name)
            status_icon = "✓" if status == "ok" else "✗"
            lines.append(f"    {tool_name}-->>Agent: result {status_icon}")
        elif etype == "agent.error":
            err = event.get("attributes", {}).get("error", "error")
            lines.append(f"    Note over Agent,Model: ERROR: {html.escape(str(err))[:40]}")
        elif etype == "finalization.result":
            lines.append(f"    Agent-->>User: done status={status}")

    # Rebuild with explicit participant declarations
    header = ["sequenceDiagram"]
    for p in participant_order:
        header.append(f"    participant {p}")
    return "\n".join(header + lines[1:])


def render_trace_ascii(trace_events: list[dict[str, Any]]) -> str:
    """Render trace events as a compact ASCII timeline."""
    if not trace_events:
        return "(no trace events)"

    lines: list[str] = []
    lines.append("+" + "-" * 78 + "+")
    lines.append("| Trace Timeline                                                              |")
    lines.append("+" + "-" * 78 + "+")

    for event in trace_events:
        status = event.get("status", "")
        etype = event.get("event_type", "")[:30]
        turn = event.get("turn")
        tool = event.get("tool_name", "")[:15]
        idx = event.get("index", 0)

        status_symbol = {"ok": "✓", "error": "✗", "blocked": "⊘", "started": "○"}.get(status, "·")
        turn_str = f"T{turn}" if turn is not None else "  "
        tool_str = f"[{tool}]" if tool else ""

        row = f"| {idx:3d} {status_symbol} {turn_str} {etype:30s} {tool_str:17s} |"
        lines.append(row)

    lines.append("+" + "-" * 78 + "+")
    return "\n".join(lines)


def _format_attr_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    s = str(value)
    if len(s) > 60:
        return s[:57] + "..."
    return s
