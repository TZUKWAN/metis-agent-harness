"""Tests for search_code and find_files tools."""

import pytest

from metis.tools.builtin import register_builtin_tools
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext


@pytest.fixture
def registry(tmp_path):
    reg = ToolRegistry()
    register_builtin_tools(reg, workspace=str(tmp_path))
    return reg


@pytest.fixture
def ctx():
    return ToolContext()


class TestSearchCode:
    def test_search_finds_pattern(self, registry, tmp_path, ctx):
        (tmp_path / "app.py").write_text("def hello():\n    print('hello')\n")
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "hello"}, ctx)
        assert result["count"] >= 1
        assert any("app.py" in m.get("file", "") or "app.py" in m for m in result["matches"])

    def test_search_no_match(self, registry, tmp_path, ctx):
        (tmp_path / "empty.py").write_text("# nothing here\n")
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "nonexistent_pattern_xyz"}, ctx)
        assert result["count"] == 0

    def test_search_content_mode(self, registry, tmp_path, ctx):
        (tmp_path / "mod.py").write_text("x = 1\ny = 2\nz = 3\n")
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "y = 2", "output_mode": "content"}, ctx)
        assert result["count"] >= 1
        assert result["matches"][0]["line"] == 2

    def test_search_case_insensitive(self, registry, tmp_path, ctx):
        (tmp_path / "code.py").write_text("CLASS MyClass:\n    pass\n")
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "class", "case_insensitive": True}, ctx)
        assert result["count"] >= 1

    def test_search_invalid_regex(self, registry, tmp_path, ctx):
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "[invalid"}, ctx)
        assert "error" in result

    def test_search_max_results(self, registry, tmp_path, ctx):
        for i in range(20):
            (tmp_path / f"file_{i}.py").write_text(f"marker_{i} = True\n")
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "marker_", "max_results": 5}, ctx)
        assert result["count"] <= 5

    def test_search_skips_hidden_dirs(self, registry, tmp_path, ctx):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.py").write_text("password = '1234'\n")
        (tmp_path / "public.py").write_text("visible = True\n")
        spec = registry.get("search_code")
        result = spec.handler({"pattern": "password"}, ctx)
        assert result["count"] == 0


class TestFindFiles:
    def test_find_py_files(self, registry, tmp_path, ctx):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        spec = registry.get("find_files")
        result = spec.handler({"pattern": "*.py"}, ctx)
        assert result["count"] == 2

    def test_find_recursive(self, registry, tmp_path, ctx):
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("")
        (tmp_path / "root.py").write_text("")
        spec = registry.get("find_files")
        result = spec.handler({"pattern": "**/*.py"}, ctx)
        assert result["count"] == 2

    def test_find_no_match(self, registry, tmp_path, ctx):
        (tmp_path / "a.py").write_text("")
        spec = registry.get("find_files")
        result = spec.handler({"pattern": "*.rs"}, ctx)
        assert result["count"] == 0

    def test_find_returns_file_info(self, registry, tmp_path, ctx):
        (tmp_path / "data.json").write_text('{"key": "value"}')
        spec = registry.get("find_files")
        result = spec.handler({"pattern": "*.json"}, ctx)
        assert result["count"] == 1
        f = result["files"][0]
        assert f["extension"] == ".json"
        assert f["size"] > 0

    def test_find_max_results(self, registry, tmp_path, ctx):
        for i in range(20):
            (tmp_path / f"file_{i}.txt").write_text("")
        spec = registry.get("find_files")
        result = spec.handler({"pattern": "*.txt", "max_results": 5}, ctx)
        assert result["count"] <= 5

    def test_find_skips_hidden_dirs(self, registry, tmp_path, ctx):
        hidden = tmp_path / ".git"
        hidden.mkdir()
        (hidden / "config").write_text("")
        (tmp_path / "visible.txt").write_text("")
        spec = registry.get("find_files")
        result = spec.handler({"pattern": "*"}, ctx)
        paths = [f["path"] for f in result["files"]]
        assert not any(".git" in p for p in paths)
