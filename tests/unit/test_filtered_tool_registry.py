import pytest

from metis.swarm.filtered_registry import FilteredToolRegistry
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolSpec


def test_filtered_tool_registry_blocks_unallowed_tool():
    base = ToolRegistry()
    base.register(ToolSpec("read_file", "Read", {"type": "object"}, lambda args, ctx: args))
    base.register(ToolSpec("write_file", "Write", {"type": "object"}, lambda args, ctx: args))
    filtered = FilteredToolRegistry(base, ["read_file"])

    assert filtered.list_tools() == ["read_file"]
    assert filtered.get("write_file") is None
    with pytest.raises(PermissionError):
        filtered.require("write_file")
