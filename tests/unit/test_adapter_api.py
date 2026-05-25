from metis.adapters.base import Adapter
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


class FakeAdapter(Adapter):
    name = "fake"

    def register_tools(self, registry):
        return [ToolSpec("fake_tool", "Fake", {"type": "object"}, lambda args, ctx: {"ok": True})]


def test_adapter_api_registers_tool():
    registry = ToolRegistry()
    registration = FakeAdapter().register(registry)

    assert registration.tools == ["fake_tool"]
    assert registry.list_tools() == ["fake_tool"]
