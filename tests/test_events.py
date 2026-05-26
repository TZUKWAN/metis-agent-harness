"""Tests for metis/events/event_types.py and metis/events/hooks.py."""

from metis.events.event_types import EventType
from metis.events.hooks import HookBus, HookInfo


class TestEventType:
    def test_event_types_are_strings(self):
        assert isinstance(EventType.AGENT_PRE_RUN, str)
        assert isinstance(EventType.TOOL_POST_DISPATCH, str)

    def test_event_type_format(self):
        assert "." in EventType.MODEL_PRE_CALL
        assert EventType.QUALITY_PASSED.startswith("quality.")

    def test_all_events_defined(self):
        events = [attr for attr in dir(EventType) if not attr.startswith("_")]
        assert len(events) >= 10


class TestHookBus:
    def test_register_and_emit(self):
        bus = HookBus()
        received = []
        bus.register("test.event", lambda ctx: received.append(ctx))
        bus.emit("test.event", {"key": "val"})
        assert len(received) == 1

    def test_emit_returns_context(self):
        bus = HookBus()
        result = bus.emit("unknown.event", {"a": 1})
        assert result["a"] == 1

    def test_priority_ordering(self):
        bus = HookBus()
        order = []

        def low(ctx):
            order.append("low")
            return ctx

        def high(ctx):
            order.append("high")
            return ctx

        bus.register("test", low, priority=100)
        bus.register("test", high, priority=1)
        bus.emit("test")
        assert order == ["high", "low"]

    def test_blocked_stops_chain(self):
        bus = HookBus()

        def blocker(ctx):
            return {**ctx, "blocked": True}

        def after(ctx):
            ctx["reached"] = True
            return ctx

        bus.register("test", blocker, priority=1)
        bus.register("test", after, priority=2)
        result = bus.emit("test")
        assert result.get("blocked")
        assert "reached" not in result

    def test_remove_by_name(self):
        bus = HookBus()
        bus.register("test", lambda ctx: ctx, name="handler1")
        bus.register("test", lambda ctx: ctx, name="handler2")
        removed = bus.remove("test", name="handler1")
        assert removed
        info = bus.list_hooks("test")
        assert len(info["test"]) == 1

    def test_list_hooks(self):
        bus = HookBus()
        bus.register("a", lambda ctx: ctx, priority=1, name="h1")
        bus.register("a", lambda ctx: ctx, priority=2, name="h2")
        result = bus.list_hooks("a")
        assert len(result["a"]) == 2

    def test_list_all_hooks(self):
        bus = HookBus()
        bus.register("x", lambda ctx: ctx, name="h1")
        bus.register("y", lambda ctx: ctx, name="h2")
        result = bus.list_hooks()
        assert "x" in result
        assert "y" in result

    def test_clear_specific_event(self):
        bus = HookBus()
        bus.register("a", lambda ctx: ctx)
        bus.register("b", lambda ctx: ctx)
        bus.clear("a")
        assert not bus.list_hooks("a")["a"]
        assert bus.list_hooks("b")["b"]

    def test_clear_all(self):
        bus = HookBus()
        bus.register("a", lambda ctx: ctx)
        bus.register("b", lambda ctx: ctx)
        bus.clear()
        assert not bus.list_hooks()
