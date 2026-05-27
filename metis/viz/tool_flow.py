"""Render tool call flows as diagrams."""

from __future__ import annotations

import html
from typing import Any


def render_tool_flow_mermaid(tool_results: list[dict[str, Any]]) -> str:
    """Render tool calls as a Mermaid flowchart."""
    if not tool_results:
        return ""

    lines: list[str] = ["flowchart TD"]
    lines.append("    Start([Agent])")

    for i, tr in enumerate(tool_results):
        name = tr.get("name", f"tool_{i}")
        status = tr.get("status", "ok")
        error = tr.get("error", "")
        node_id = f"T{i}"
        safe_name = html.escape(name)

        if status == "ok":
            lines.append(f"    {node_id}[{safe_name}]")
            lines.append(f"    style {node_id} fill:#d4edda,stroke:#28a745")
        elif status == "blocked":
            lines.append(f"    {node_id}[/Blocked: {safe_name}/]")
            lines.append(f"    style {node_id} fill:#fff3cd,stroke:#fd7e14")
        else:
            err_short = html.escape(str(error))[:30] if error else "error"
            lines.append(f"    {node_id}[{safe_name}<br/>✗ {err_short}]")
            lines.append(f"    style {node_id} fill:#f8d7da,stroke:#dc3545")

    # Connections
    prev = "Start"
    for i in range(len(tool_results)):
        node_id = f"T{i}"
        lines.append(f"    {prev} --> {node_id}")
        prev = node_id

    lines.append(f"    {prev} --> End([Done])")
    return "\n".join(lines)


def render_tool_flow_ascii(tool_results: list[dict[str, Any]]) -> str:
    """Render tool calls as an ASCII flow."""
    if not tool_results:
        return "(no tool calls)"

    lines: list[str] = []
    lines.append("Agent")
    lines.append("  |")
    lines.append("  v")

    for tr in tool_results:
        name = tr.get("name", "?")
        status = tr.get("status", "ok")
        error = tr.get("error", "")

        if status == "ok":
            box = f"  [ {name} ]  "
        elif status == "blocked":
            box = f"  [/ {name} /]  "
        else:
            box = f"  [X {name} ]  "

        width = max(len(box), 20)
        lines.append("+" + "-" * width + "+")
        lines.append("|" + box.center(width) + "|")
        if error and status != "ok":
            err_line = f"  {str(error)[:40]}"
            lines.append("|" + err_line.ljust(width) + "|")
        lines.append("+" + "-" * width + "+")
        lines.append("  |")
        lines.append("  v")

    lines.append("Done")
    return "\n".join(lines)


def render_tool_summary_table(tool_results: list[dict[str, Any]]) -> str:
    """Render tool results as an HTML table."""
    if not tool_results:
        return "<p>No tool calls.</p>"

    rows: list[str] = [
        '<table class="metis-tool-table">',
        '  <style>',
        '    .metis-tool-table { border-collapse: collapse; font-family: monospace; font-size: 12px; width: 100%; }',
        '    .metis-tool-table th, .metis-tool-table td { border: 1px solid #dee2e6; padding: 4px 8px; text-align: left; }',
        '    .metis-tool-table th { background: #f8f9fa; }',
        '    .metis-tool-table .ok { color: #28a745; }',
        '    .metis-tool-table .error { color: #dc3545; }',
        '    .metis-tool-table .blocked { color: #fd7e14; }',
        '  </style>',
        '  <thead><tr><th>#</th><th>Tool</th><th>Status</th><th>Error</th><th>Metadata</th></tr></thead>',
        '  <tbody>',
    ]

    for i, tr in enumerate(tool_results):
        name = html.escape(tr.get("name", "?"))
        status = tr.get("status", "ok")
        error = html.escape(str(tr.get("error", "")))
        metadata = tr.get("metadata", {})
        meta_parts = [f"{k}={v}" for k, v in metadata.items() if k not in ("schema_repair_hints", "schema_repair_hint_details")]
        meta_str = html.escape(", ".join(meta_parts))[:100]

        status_class = status if status in ("ok", "error", "blocked") else ""
        rows.append(
            f'    <tr><td>{i+1}</td><td>{name}</td><td class="{status_class}">{status}</td>'
            f'<td>{error}</td><td>{meta_str}</td></tr>'
        )

    rows.append("  </tbody>")
    rows.append("</table>")
    return "\n".join(rows)
