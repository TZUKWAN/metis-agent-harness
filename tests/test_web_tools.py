"""Tests for web_fetch tool."""

from metis.tools.web_tools import register_web_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


def test_web_fetch_registered():
    registry = ToolRegistry()
    register_web_tools(registry)
    assert registry.get("web_fetch") is not None


def test_web_fetch_blocks_non_http():
    registry = ToolRegistry()
    register_web_tools(registry)
    spec = registry.get("web_fetch")
    result = spec.handler({"url": "ftp://example.com/file"}, ToolContext())
    assert "error" in result
    assert "HTTP" in result["error"]


def test_web_fetch_blocks_localhost():
    registry = ToolRegistry()
    register_web_tools(registry)
    spec = registry.get("web_fetch")
    for host in ["http://localhost/secret", "http://127.0.0.1/admin", "http://169.254.169.254/metadata"]:
        result = spec.handler({"url": host}, ToolContext())
        assert "error" in result


def test_web_fetch_real_url():
    registry = ToolRegistry()
    register_web_tools(registry)
    spec = registry.get("web_fetch")
    result = spec.handler({"url": "https://httpbin.org/get", "timeout": 10}, ToolContext())
    assert "content" in result or "error" in result
