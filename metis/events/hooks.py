"""Priority ordered hook bus used by all Metis subsystems."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

HookHandler = Callable[[dict[str, Any]], dict[str, Any] | None]
AsyncHookHandler = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class HookInfo:
    name: str
    priority: int


class HookBus:
    """Small event bus with priority ordering and blocked-chain semantics.

    Supports both synchronous ``emit()`` and asynchronous ``emit_async()``
    dispatch.  Handlers registered via ``register()`` may be sync or async
    callables; both are handled correctly in ``emit_async()``.
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def register(
        self,
        event: str,
        handler: HookHandler | AsyncHookHandler,
        *,
        priority: int = 100,
        name: str | None = None,
    ) -> None:
        entry = {
            "handler": handler,
            "priority": priority,
            "name": name or getattr(handler, "__name__", "anonymous"),
            "is_async": asyncio.iscoroutinefunction(handler),
        }
        self._hooks[event].append(entry)
        self._hooks[event].sort(key=lambda item: item["priority"])

    def emit(self, event: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx: dict[str, Any] = dict(context or {})
        ctx.setdefault("event", event)

        for entry in list(self._hooks.get(event, [])):
            handler = entry["handler"]
            try:
                result = handler(ctx)
                if result is not None:
                    ctx = result
            except Exception as exc:
                errors = ctx.setdefault("hook_errors", [])
                errors.append(
                    {
                        "event": event,
                        "handler": entry["name"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                logger.warning("Hook '%s' failed on '%s': %s", entry["name"], event, exc)

            if ctx.get("blocked"):
                break

        return ctx

    async def emit_async(self, event: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Async dispatch: calls async handlers with ``await``, sync handlers normally."""
        ctx: dict[str, Any] = dict(context or {})
        ctx.setdefault("event", event)

        for entry in list(self._hooks.get(event, [])):
            handler = entry["handler"]
            try:
                if entry["is_async"]:
                    result = await handler(ctx)
                else:
                    result = handler(ctx)
                if result is not None:
                    ctx = result
            except Exception as exc:
                errors = ctx.setdefault("hook_errors", [])
                errors.append(
                    {
                        "event": event,
                        "handler": entry["name"],
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                logger.warning("Hook '%s' failed on '%s': %s", entry["name"], event, exc)

            if ctx.get("blocked"):
                break

        return ctx

    def remove(
        self,
        event: str,
        *,
        handler: HookHandler | AsyncHookHandler | None = None,
        name: str | None = None,
    ) -> bool:
        if event not in self._hooks:
            return False
        original = len(self._hooks[event])
        if handler is not None:
            self._hooks[event] = [h for h in self._hooks[event] if h["handler"] is not handler]
        elif name is not None:
            self._hooks[event] = [h for h in self._hooks[event] if h["name"] != name]
        else:
            return False
        return len(self._hooks[event]) != original

    def list_hooks(self, event: str | None = None) -> dict[str, list[HookInfo]]:
        events = [event] if event else sorted(self._hooks)
        return {
            ev: [HookInfo(name=item["name"], priority=item["priority"]) for item in self._hooks.get(ev, [])]
            for ev in events
        }

    def clear(self, event: str | None = None) -> None:
        if event:
            self._hooks.pop(event, None)
        else:
            self._hooks.clear()
