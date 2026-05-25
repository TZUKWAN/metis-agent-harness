"""Priority ordered hook bus used by all Metis subsystems."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

HookHandler = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True)
class HookInfo:
    name: str
    priority: int


class HookBus:
    """Small event bus with priority ordering and blocked-chain semantics."""

    def __init__(self) -> None:
        self._hooks: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def register(
        self,
        event: str,
        handler: HookHandler,
        *,
        priority: int = 100,
        name: str | None = None,
    ) -> None:
        entry = {
            "handler": handler,
            "priority": priority,
            "name": name or getattr(handler, "__name__", "anonymous"),
        }
        self._hooks[event].append(entry)
        self._hooks[event].sort(key=lambda item: item["priority"])

    def emit(self, event: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ctx: dict[str, Any] = dict(context or {})
        ctx.setdefault("event", event)

        for entry in list(self._hooks.get(event, [])):
            try:
                result = entry["handler"](ctx)
                if result is not None:
                    ctx = result
            except Exception as exc:  # pragma: no cover - log path still tested by context
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
        handler: HookHandler | None = None,
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
