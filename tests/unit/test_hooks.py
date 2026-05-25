from metis.events.hooks import HookBus


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
