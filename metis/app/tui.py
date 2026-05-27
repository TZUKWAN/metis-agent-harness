"""Textual-based full-screen TUI for Metis apps."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from metis.app.manifest import AgentAppManifest, save_app_manifest
from metis.app.runtime import build_runtime_status, run_agent_turn
from metis.events.event_types import EventType
from metis.events.hooks import HookBus


class MetisHeader(Static):
    """Top header showing app name, model, and status."""

    status = reactive("Ready")

    def compose(self) -> ComposeResult:
        yield Static(id="header-brand")
        yield Static(id="header-model")
        yield Static(id="header-status")

    def watch_status(self, status: str) -> None:
        status_el = self.query_one("#header-status", Static)
        color = {
            "Ready": "green",
            "Thinking": "yellow",
            "Running": "blue",
            "Error": "red",
        }.get(status, "white")
        status_el.update(Text(status, style=f"bold {color}"))

    def on_mount(self) -> None:
        app = self.app
        if isinstance(app, MetisTUI):
            manifest = app.manifest
            self.query_one("#header-brand", Static).update(
                Text.from_markup(f"[bold]{manifest.name}[/bold] — {manifest.subtitle}")
            )
            self.query_one("#header-model", Static).update(
                Text.from_markup(f"[dim]Model:[/dim] {manifest.model}  [dim]Profile:[/dim] {manifest.profile}")
            )
        self.watch_status(self.status)


class MessageArea(RichLog):
    """Scrollable message history."""

    def __init__(self) -> None:
        super().__init__(highlight=True, markup=True)


class ToolCard(Static):
    """A tool call status card."""

    def __init__(self, name: str, args: dict | None = None) -> None:
        super().__init__()
        self.tool_name = name
        self.tool_args = args or {}
        self.status = "running"
        self.duration_ms = 0

    def compose(self) -> ComposeResult:
        yield Static(id="tool-card-content")

    def on_mount(self) -> None:
        self._update()

    def set_status(self, status: str, duration_ms: int = 0) -> None:
        self.status = status
        self.duration_ms = duration_ms
        self._update()

    def _update(self) -> None:
        icon = {
            "running": "[bold blue]●[/]",
            "ok": "[bold green]✓[/]",
            "error": "[bold red]✗[/]",
            "blocked": "[bold yellow]⊘[/]",
        }.get(self.status, "[dim]○[/]")

        import json
        try:
            args_str = json.dumps(self.tool_args, ensure_ascii=False)
        except Exception:
            args_str = str(self.tool_args)
        if len(args_str) > 200:
            args_str = args_str[:200] + "..."

        title = f"{icon} {self.tool_name}"
        if self.duration_ms > 0:
            title += f" [dim]{self.duration_ms}ms[/dim]"

        border = {
            "running": "blue",
            "ok": "green",
            "error": "red",
            "blocked": "yellow",
        }.get(self.status, "white")

        panel = Panel(
            args_str or "",
            title=title,
            border_style=border,
            padding=(0, 1),
        )
        self.query_one("#tool-card-content", Static).update(panel)


class Composer(Horizontal):
    """Bottom input area with send button."""

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Send a task to the agent...", id="composer-input")
        yield Button("Send", id="composer-send", variant="primary")


class MetisTUI(App):
    """Full-screen Textual TUI for Metis Agent."""

    CSS = """
    Screen { align: center middle; }
    #main { width: 100%; height: 100%; }
    #header { height: 3; background: $surface; color: $text; padding: 0 2; }
    #header-brand { width: 40%; content-align-vertical: middle; }
    #header-model { width: 40%; content-align-vertical: middle; }
    #header-status { width: 20%; content-align-vertical: middle; content-align: right middle; }
    #messages { width: 100%; height: 1fr; border: solid $primary; padding: 1; }
    #composer { height: 3; padding: 0 1; }
    #composer-input { width: 1fr; }
    #composer-send { width: auto; min-width: 8; }
    #footer { height: 1; }
    .tool-card { margin: 0 2 1 4; }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+n", "new_chat", "New Chat"),
        ("ctrl+r", "retry", "Retry"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, manifest: AgentAppManifest, *, max_turns: int = 12) -> None:
        super().__init__()
        self.manifest = manifest
        self.max_turns = max_turns
        self.session_id = "tui"
        self.turn_count = 0
        self._running_task: asyncio.Task | None = None
        self._streaming_buffer = ""
        self._active_tools: dict[str, ToolCard] = {}

    def compose(self) -> ComposeResult:
        yield TUIHeader(id="header")
        with Vertical(id="main"):
            yield MessageArea(id="messages")
            yield Composer(id="composer")
        yield Footer(id="footer")

    def on_mount(self) -> None:
        self.query_one("#messages", MessageArea).write(
            Text.from_markup(f"[dim]Welcome to {self.manifest.name}. Type a message and press Enter.[/dim]")
        )
        self.query_one("#composer-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "composer-input":
            self._send_message()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "composer-send":
            self._send_message()

    def action_new_chat(self) -> None:
        self.session_id = f"tui-{int(time.time())}"
        self.turn_count = 0
        log = self.query_one("#messages", MessageArea)
        log.clear()
        log.write(Text.from_markup("[dim]New session started.[/dim]"))
        self.query_one("#composer-input", Input).focus()

    def action_retry(self) -> None:
        self.query_one("#messages", MessageArea).write(Text.from_markup("[dim]Retry not yet implemented.[/dim]"))

    def action_cancel(self) -> None:
        if self._running_task and not self._running_task.done():
            self._running_task.cancel()
            self.query_one("#header", MetisHeader).status = "Cancelled"

    def _send_message(self) -> None:
        input_widget = self.query_one("#composer-input", Input)
        message = input_widget.value.strip()
        if not message:
            return

        input_widget.value = ""
        self.turn_count += 1
        log = self.query_one("#messages", MessageArea)
        log.write(Text.from_markup(f"[bold blue]>[/] {message}"))
        self.query_one("#header", MetisHeader).status = "Thinking"

        self._running_task = asyncio.create_task(self._run_turn(message, log))

    async def _run_turn(self, message: str, log: MessageArea) -> None:
        hooks = HookBus()
        self._active_tools = {}
        self._streaming_buffer = ""
        streaming_line_id: int | None = None

        _tool_counter = 0

        def on_tool_pre_dispatch(data: dict) -> None:
            nonlocal _tool_counter
            _tool_counter += 1
            name = data.get("tool", "unknown")
            args = data.get("args", {})
            call_id = data.get("tool_call_id", "") or f"{name}-{_tool_counter}"
            self.call_later(self._add_tool_card, call_id, name, args)

        def on_tool_post_dispatch(data: dict) -> None:
            call_id = data.get("tool_call_id", "")
            name = data.get("tool", "unknown")
            status = data.get("status", "ok")
            if call_id and call_id in self._active_tools:
                self.call_later(self._update_tool_card, call_id, status, 0)
            elif name:
                for cid, card in self._active_tools.items():
                    if card.tool_name == name:
                        self.call_later(self._update_tool_card, cid, status, 0)
                        break

        def on_tool_analytics(data: dict) -> None:
            call_id = data.get("tool_call_id", "")
            name = data.get("tool", "")
            duration_ms = data.get("duration_ms", 0)
            if call_id and call_id in self._active_tools:
                self.call_later(self._update_tool_card, call_id, self._active_tools[call_id].status, duration_ms)
            elif name:
                for cid, card in self._active_tools.items():
                    if card.tool_name == name:
                        self.call_later(self._update_tool_card, cid, card.status, duration_ms)
                        break

        def on_stream_chunk(data: dict) -> None:
            content = data.get("content", "")
            if content:
                self._streaming_buffer += content
                self.call_later(self._update_streaming, log)

        hooks.register(EventType.TOOL_PRE_DISPATCH, on_tool_pre_dispatch)
        hooks.register(EventType.TOOL_POST_DISPATCH, on_tool_post_dispatch)
        hooks.register("tool.analytics", on_tool_analytics)
        hooks.register(EventType.MODEL_STREAM_CHUNK, on_stream_chunk)

        try:
            result = await run_agent_turn(
                message, manifest=self.manifest, max_turns=self.max_turns,
                session_id=self.session_id, hooks=hooks,
            )
        except asyncio.CancelledError:
            log.write(Text.from_markup("[dim]Cancelled.[/dim]"))
            self.query_one("#header", MetisHeader).status = "Ready"
            return
        except Exception as exc:
            log.write(Text.from_markup(f"[bold red]Error:[/bold red] {exc}"))
            self.query_one("#header", MetisHeader).status = "Error"
            return

        # Finalize streaming content
        if self._streaming_buffer:
            self._finalize_streaming(log)

        # Show any tool results not yet displayed
        for tr in result.tool_results:
            if tr.tool_call_id not in self._active_tools:
                self._add_tool_card(tr.tool_call_id or tr.tool_name, tr.tool_name, {})
                self._update_tool_card(tr.tool_call_id or tr.tool_name, tr.status or "ok", 0)

        # Show response
        if result.final_text and not self._streaming_buffer:
            log.write(Markdown(result.final_text))
        elif result.errors:
            for err in result.errors:
                log.write(Text.from_markup(f"[yellow]⚠ {err}[/yellow]"))

        # Show usage
        if result.usage:
            total = result.usage.get("total_tokens", 0)
            if total > 0:
                log.write(Text.from_markup(f"[dim]Tokens: {total:,} | Turns: {result.turns_used}[/dim]"))

        self.query_one("#header", MetisHeader).status = "Ready"
        self.query_one("#composer-input", Input).focus()

    def _add_tool_card(self, call_id: str, name: str, args: dict) -> None:
        log = self.query_one("#messages", MessageArea)
        card = ToolCard(name, args)
        card.add_class("tool-card")
        self._active_tools[call_id] = card
        log.write(card)

    def _update_tool_card(self, call_id: str, status: str, duration_ms: int) -> None:
        if call_id in self._active_tools:
            self._active_tools[call_id].set_status(status, duration_ms)

    def _update_streaming(self, log: MessageArea) -> None:
        # Update header to show streaming progress
        header = self.query_one("#header", MetisHeader)
        header.status = f"Streaming ({len(self._streaming_buffer)} chars)"

    def _finalize_streaming(self, log: MessageArea) -> None:
        if self._streaming_buffer:
            log.write(Markdown(self._streaming_buffer))
            self._streaming_buffer = ""

class TUIHeader(Horizontal):
    pass


# Back-compat: keep the original run_tui_sync entry point

def run_tui_sync(manifest: AgentAppManifest, *, max_turns: int = 12) -> int:
    """Run the Textual TUI synchronously."""
    needs_setup = asyncio.run(_check_provider_needs_setup(manifest))
    if needs_setup:
        manifest = _run_setup_wizard(manifest)
        still_needs_setup = asyncio.run(_check_provider_needs_setup(manifest))
        if still_needs_setup:
            from rich.console import Console
            console = Console()
            console.print("[bold red]Warning: Provider still appears unreachable with the new config.[/bold red]")
            console.print("[dim]You can continue anyway, or fix the configuration and restart.[/dim]")
            console.print()
    app = MetisTUI(manifest, max_turns=max_turns)
    app.run()
    return 0


# Preserve original helper functions

async def _check_provider_needs_setup(manifest: AgentAppManifest) -> bool:
    """Check if provider requires configuration."""
    from metis.app.runtime import _build_provider_for_manifest
    try:
        provider = _build_provider_for_manifest(manifest)
        health = await provider.health_check()
        await provider.close()
        return health.get("status") in ("error", "unreachable", "not_initialized")
    except Exception:
        return True


def _extract_api_key_from_manifest(manifest: AgentAppManifest) -> str:
    """Extract api_key from manifest providers list."""
    for p in manifest.providers:
        if isinstance(p, dict) and p.get("api_key"):
            return str(p["api_key"])
    return ""


def _run_setup_wizard(manifest: AgentAppManifest) -> AgentAppManifest:
    """Interactive setup wizard for TUI when provider is not configured."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.rule import Rule
    from typing import Any

    console = Console()
    console.print()
    console.rule("[bold yellow]Welcome to Metis Agent Setup[/bold yellow]", style="yellow")
    console.print("[dim]Your AI provider is not configured yet. Let's set it up.[/dim]")
    console.print()

    current_model = manifest.model or ""
    current_base_url = manifest.base_url or ""
    current_api_key = _extract_api_key_from_manifest(manifest)

    if current_model:
        console.print(f"[dim]Current model:[/dim] {current_model}")
    if current_base_url:
        console.print(f"[dim]Current base URL:[/dim] {current_base_url}")
    if current_api_key:
        console.print(f"[dim]Current API key:[/dim] {'*' * len(current_api_key)}")

    console.print()

    model = Prompt.ask("Model name", default=current_model or "").strip()
    if not model:
        console.print("[bold red]Model is required. Exiting.[/bold red]")
        sys.exit(1)

    base_url = Prompt.ask("Base URL (optional, press Enter to skip)", default=current_base_url or "").strip()
    api_key = Prompt.ask("API Key", default=current_api_key or "", password=True).strip()
    if not api_key:
        console.print("[bold red]API key is required. Exiting.[/bold red]")
        sys.exit(1)

    new_data = manifest.to_dict()
    new_data["model"] = model
    if base_url:
        new_data["base_url"] = base_url

    providers = list(new_data.get("providers", []))
    providers = [p for p in providers if p.get("model") != model]
    provider_cfg: dict[str, Any] = {
        "name": model,
        "model": model,
        "provider_type": "openai_compat",
        "priority": 0,
    }
    if base_url:
        provider_cfg["base_url"] = base_url
    if api_key:
        provider_cfg["api_key"] = api_key
    providers.insert(0, provider_cfg)
    new_data["providers"] = providers

    new_manifest = AgentAppManifest(**new_data)
    save_app_manifest(new_manifest)
    console.print()
    console.print("[bold green]✓ Configuration saved to metis-agent.json[/bold green]")
    console.print()

    return new_manifest


# Also keep the old async run_tui for any direct callers

async def run_tui(manifest: AgentAppManifest, *, max_turns: int = 12) -> int:
    """Back-compat async wrapper around run_tui_sync."""
    return run_tui_sync(manifest, max_turns=max_turns)
