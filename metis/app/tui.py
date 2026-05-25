"""Simple built-in terminal UI for Metis apps."""

from __future__ import annotations

import asyncio

from metis.app.manifest import AgentAppManifest
from metis.app.runtime import build_runtime_status, run_agent_turn


async def run_tui(manifest: AgentAppManifest, *, max_turns: int = 12) -> int:
    print(f"{manifest.name} - {manifest.subtitle}")
    print(f"Workspace: {manifest.workspace}")
    print(f"Model: {manifest.model}")
    status = build_runtime_status(manifest)
    permissions = status["allowed_tool_permissions"] or "manifest default"
    print(f"Tool permissions: {permissions}")
    print("Type /exit to quit.")
    print()
    while True:
        try:
            message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not message:
            continue
        if message.lower() in {"/exit", "/quit"}:
            return 0
        result = await run_agent_turn(message, manifest=manifest, max_turns=max_turns)
        if result.final_text:
            print(result.final_text)
        else:
            print(f"[{result.status}] " + "; ".join(result.errors))
        print()


def run_tui_sync(manifest: AgentAppManifest, *, max_turns: int = 12) -> int:
    return asyncio.run(run_tui(manifest, max_turns=max_turns))
