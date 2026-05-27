"""Generate HTML reports from agent run results."""

from __future__ import annotations

import html
import json
from typing import Any

from metis.runtime.response import AgentRunResult

from .tool_flow import render_tool_flow_mermaid, render_tool_summary_table
from .trace_renderer import render_trace_mermaid, render_trace_timeline


REPORT_CSS = """
:root { --bg: #f8f9fa; --fg: #212529; --accent: #0d6efd; --ok: #28a745; --err: #dc3545; --warn: #fd7e14; }
body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--fg); max-width: 1200px; margin: 0 auto; padding: 20px; }
h1, h2 { border-bottom: 2px solid var(--accent); padding-bottom: 8px; }
.metis-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 16px 0; }
.metis-card { background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; }
.metis-card .label { font-size: 12px; color: #6c757d; text-transform: uppercase; }
.metis-card .value { font-size: 18px; font-weight: bold; }
.metis-card.ok .value { color: var(--ok); }
.metis-card.err .value { color: var(--err); }
.metis-card.warn .value { color: var(--warn); }
.mermaid { background: #fff; border: 1px solid #dee2e6; border-radius: 6px; padding: 12px; overflow-x: auto; }
pre { background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 12px; overflow-x: auto; font-size: 12px; }
.errors { background: #f8d7da; border: 1px solid #f5c2c7; border-radius: 4px; padding: 12px; }
"""


def generate_html_report(result: AgentRunResult, session_id: str = "", title: str = "Agent Run Report") -> str:
    """Generate a complete HTML report from an AgentRunResult."""
    status_class = "ok" if result.status == "final" else "err" if result.errors else "warn"
    usage = result.usage or {}
    tool_count = len(result.tool_results)
    error_count = len(result.errors)

    tool_results_dicts = [
        {
            "name": tr.tool_name,
            "status": tr.status,
            "error": tr.error,
            "metadata": tr.metadata,
        }
        for tr in result.tool_results
    ]

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head>',
        f"<title>{html.escape(title)}</title>",
        f"<style>{REPORT_CSS}</style>",
        '<script type="module">',
        '  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs";',
        '  mermaid.initialize({ startOnLoad: true });',
        "</script>",
        "</head><body>",
        f"<h1>{html.escape(title)}</h1>",
    ]

    # Summary cards
    parts.append('<div class="metis-summary">')
    parts.append(f'  <div class="metis-card {status_class}"><div class="label">Status</div><div class="value">{html.escape(result.status)}</div></div>')
    parts.append(f'  <div class="metis-card"><div class="label">Turns</div><div class="value">{result.turns_used}</div></div>')
    parts.append(f'  <div class="metis-card"><div class="label">Tools</div><div class="value">{tool_count}</div></div>')
    parts.append(f'  <div class="metis-card {'err' if error_count else ''}"><div class="label">Errors</div><div class="value">{error_count}</div></div>')
    parts.append(f'  <div class="metis-card"><div class="label">Tokens</div><div class="value">{usage.get("total_tokens", 0)}</div></div>')
    parts.append("</div>")

    # Final text
    if result.final_text:
        parts.append("<h2>Final Response</h2>")
        parts.append(f"<pre>{html.escape(result.final_text[:2000])}</pre>")

    # Errors
    if result.errors:
        parts.append("<h2>Errors</h2>")
        parts.append('<div class="errors">')
        for err in result.errors:
            parts.append(f"<p>{html.escape(str(err))}</p>")
        parts.append("</div>")

    # Tool flow diagram
    if tool_results_dicts:
        parts.append("<h2>Tool Call Flow</h2>")
        mermaid_flow = render_tool_flow_mermaid(tool_results_dicts)
        parts.append(f'<pre class="mermaid">{mermaid_flow}</pre>')
        parts.append("<h2>Tool Results</h2>")
        parts.append(render_tool_summary_table(tool_results_dicts))

    # Trace timeline
    if result.trace_events:
        parts.append("<h2>Trace Timeline</h2>")
        parts.append(render_trace_timeline(result.trace_events, session_id))
        mermaid_seq = render_trace_mermaid(result.trace_events, session_id)
        if mermaid_seq:
            parts.append("<h2>Sequence Diagram</h2>")
            parts.append(f'<pre class="mermaid">{mermaid_seq}</pre>')

    # Usage details
    if usage:
        parts.append("<h2>Token Usage</h2>")
        parts.append("<pre>")
        parts.append(json.dumps(usage, indent=2, ensure_ascii=False))
        parts.append("</pre>")

    parts.append("</body></html>")
    return "\n".join(parts)


def generate_json_report(result: AgentRunResult, session_id: str = "") -> str:
    """Generate a JSON report from an AgentRunResult."""
    data: dict[str, Any] = {
        "session_id": session_id,
        "status": result.status,
        "turns_used": result.turns_used,
        "tool_count": len(result.tool_results),
        "error_count": len(result.errors),
        "errors": result.errors,
        "usage": result.usage,
        "final_text": result.final_text,
        "trace_events": result.trace_events,
        "tool_results": [
            {
                "name": tr.tool_name,
                "status": tr.status,
                "error": tr.error,
                "metadata": tr.metadata,
            }
            for tr in result.tool_results
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
