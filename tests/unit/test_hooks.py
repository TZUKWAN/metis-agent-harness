import asyncio

import pytest

from metis.events.hooks import HookBus


# ── Synchronous emit (existing) ──────────────────────────────────


def test_priority_order():
    bus = HookBus()
    seen = []
    bus.register("x", lambda ctx: seen.append("b") or ctx, priority=20)
    bus.register("x", lambda ctx: seen.append("a") or ctx, priority=10)

    bus.emit("x", {})

    assert seen == ["a", "b"]


def test_blocked_stops_chain():
    bus = HookBus()
    seen = []

    def block(ctx):
        seen.append("block")
        ctx["blocked"] = True
        return ctx

    bus.register("x", block, priority=10)
    bus.register("x", lambda ctx: seen.append("late") or ctx, priority=20)

    result = bus.emit("x", {})

    assert result["blocked"] is True
    assert seen == ["block"]


def test_exception_isolated():
    bus = HookBus()

    def bad(ctx):
        raise RuntimeError("boom")

    bus.register("x", bad)
    result = bus.emit("x", {})

    assert result["hook_errors"][0]["error"].endswith("boom")


def test_remove_by_name():
    bus = HookBus()
    bus.register("x", lambda ctx: ctx, name="one")

    assert bus.remove("x", name="one") is True
    assert bus.list_hooks("x") == {"x": []}


# ── Async emit_async ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emit_async_calls_sync_handler():
    bus = HookBus()
    seen = []
    bus.register("x", lambda ctx: seen.append("sync") or ctx)

    result = await bus.emit_async("x", {"data": 1})

    assert seen == ["sync"]
    assert result["data"] == 1


@pytest.mark.asyncio
async def test_emit_async_calls_async_handler():
    bus = HookBus()
    seen = []

    async def handler(ctx):
        seen.append("async")
        return ctx

    bus.register("x", handler)

    result = await bus.emit_async("x", {})

    assert seen == ["async"]


@pytest.mark.asyncio
async def test_emit_async_mixed_sync_and_async():
    bus = HookBus()
    seen = []

    async def async_handler(ctx):
        seen.append("async")
        return ctx

    def sync_handler(ctx):
        seen.append("sync")
        return ctx

    bus.register("x", sync_handler, priority=10)
    bus.register("x", async_handler, priority=20)

    await bus.emit_async("x", {})

    assert seen == ["sync", "async"]


@pytest.mark.asyncio
async def test_emit_async_priority_ordering():
    bus = HookBus()
    seen = []

    async def slow(ctx):
        seen.append("slow")
        return ctx

    def fast(ctx):
        seen.append("fast")
        return ctx

    bus.register("x", slow, priority=20)
    bus.register("x", fast, priority=10)

    await bus.emit_async("x", {})

    assert seen == ["fast", "slow"]


@pytest.mark.asyncio
async def test_emit_async_blocked_chain():
    bus = HookBus()
    seen = []

    async def blocker(ctx):
        seen.append("block")
        ctx["blocked"] = True
        return ctx

    async def late(ctx):
        seen.append("late")
        return ctx

    bus.register("x", blocker, priority=10)
    bus.register("x", late, priority=20)

    result = await bus.emit_async("x", {})

    assert result["blocked"] is True
    assert seen == ["block"]


@pytest.mark.asyncio
async def test_emit_async_exception_isolated():
    bus = HookBus()

    async def bad(ctx):
        raise RuntimeError("async boom")

    async def good(ctx):
        ctx["good"] = True
        return ctx

    bus.register("x", bad, priority=10)
    bus.register("x", good, priority=20)

    result = await bus.emit_async("x", {})

    assert result["hook_errors"][0]["error"].endswith("async boom")
    assert result["good"] is True


@pytest.mark.asyncio
async def test_emit_async_returns_updated_context():
    bus = HookBus()

    async def add_field(ctx):
        ctx["added"] = "yes"
        return ctx

    bus.register("x", add_field)

    result = await bus.emit_async("x", {"original": True})

    assert result["original"] is True
    assert result["added"] == "yes"


@pytest.mark.asyncio
async def test_emit_async_handler_can_be_sync_only():
    bus = HookBus()
    seen = []
    bus.register("x", lambda ctx: seen.append("a") or ctx, priority=10)
    bus.register("x", lambda ctx: seen.append("b") or ctx, priority=20)

    result = await bus.emit_async("x", {})

    assert seen == ["a", "b"]
    assert result["event"] == "x"
