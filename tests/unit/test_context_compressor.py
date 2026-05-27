from metis.context.compressor import SimpleContextCompressor
from metis.context.engine import ContextEngine
from metis.runtime.budgets import BudgetConfig


def test_context_compressor_keeps_system_and_recent_messages():
    messages = [{"role": "system", "content": "[app-system] rules"}]
    messages += [{"role": "user", "content": f"message {i} " + ("x" * 80)} for i in range(12)]
    compressor = SimpleContextCompressor(max_summary_chars=300, keep_recent=3)

    result = compressor.compress(messages, max_chars=500)

    assert result.compressed is True
    assert result.messages[0]["content"] == "[app-system] rules"
    assert result.messages[-1]["content"].startswith("message 11")
    assert any(message.get("metadata", {}).get("metis_context_summary") for message in result.messages)


def test_context_engine_compresses_above_budget():
    # Use a small chars_per_token and large enough messages to exceed the 1000-char floor
    engine = ContextEngine(
        budget=BudgetConfig(model_context_tokens=200, context_threshold=0.5),
        compressor=SimpleContextCompressor(max_summary_chars=120, keep_recent=2),
        chars_per_token=1,
    )
    messages = [{"role": "user", "content": "x" * 300} for _ in range(10)]

    result = engine.build(messages)

    assert result.compressed is True
    assert result.final_chars <= result.original_chars
    assert result.max_chars == 100


class TestSimpleContextCompressor:
    def test_no_compression_when_under_budget(self):
        messages = [{"role": "user", "content": "hello"}]
        comp = SimpleContextCompressor()
        result = comp.compress(messages, max_chars=1000)
        assert result.compressed is False
        assert result.original_chars == result.compressed_chars

    def test_trims_large_tool_results(self):
        comp = SimpleContextCompressor(max_tool_result_chars=50)
        messages = [
            {"role": "user", "content": "query"},
            {"role": "tool", "content": "a" * 200, "name": "test_tool"},
        ]
        result = comp.compress(messages, max_chars=120)  # Phase-1 trim only
        tool_msg = [m for m in result.messages if m.get("role") == "tool"][0]
        assert "trimmed" in tool_msg["content"]
        assert len(tool_msg["content"]) <= 150  # 50 + overhead for summary line

    def test_critical_tool_result_preserved(self):
        comp = SimpleContextCompressor(max_tool_result_chars=50)
        messages = [
            {"role": "user", "content": "query"},
            {"role": "tool", "content": '{"error": "something broke"}', "name": "test_tool"},
        ]
        result = comp.compress(messages, max_chars=500)
        tool_msg = [m for m in result.messages if m.get("role") == "tool"][0]
        # Critical results get 3x limit
        assert "something broke" in tool_msg["content"]

    def test_protected_system_layers_never_truncated(self):
        comp = SimpleContextCompressor(keep_recent=2)
        messages = [
            {"role": "system", "content": "[base-harness] critical harness instructions"},
            {"role": "system", "content": "[task-contract] task contract"},
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
            {"role": "user", "content": "u3"},
            {"role": "user", "content": "u4"},
        ]
        result = comp.compress(messages, max_chars=100)
        contents = [m["content"] for m in result.messages]
        assert "[base-harness] critical harness instructions" in contents
        assert "[task-contract] task contract" in contents

    def test_protected_system_by_metadata(self):
        comp = SimpleContextCompressor(keep_recent=2)
        messages = [
            {"role": "system", "content": "hidden instructions", "metadata": {"layer_type": "behavior-rules"}},
            {"role": "user", "content": "u1"},
            {"role": "user", "content": "u2"},
        ]
        result = comp.compress(messages, max_chars=100)
        assert any(m.get("metadata", {}).get("layer_type") == "behavior-rules" for m in result.messages)

    def test_reasoning_content_counted(self):
        comp = SimpleContextCompressor()
        messages = [{"role": "assistant", "content": "ok", "reasoning_content": "thinking..." * 50}]
        result = comp.compress(messages, max_chars=50)
        assert result.compressed is True

    def test_summary_message_format(self):
        comp = SimpleContextCompressor(max_summary_chars=300, keep_recent=2)
        messages = [{"role": "user", "content": f"msg {i}"} for i in range(10)]
        result = comp.compress(messages, max_chars=40)  # Force compression (orig=50)
        summary_msg = [m for m in result.messages if m.get("metadata", {}).get("metis_context_summary")][0]
        assert "Context Compression" in summary_msg["content"]
        assert summary_msg.get("metadata", {}).get("compressed_items", 0) > 0

    def test_force_fit_keeps_protected_layers(self):
        comp = SimpleContextCompressor(keep_recent=0)
        messages = [
            {"role": "system", "content": "[base-harness] harness"},
            {"role": "user", "content": "x" * 500},
        ]
        result = comp.compress(messages, max_chars=50)
        assert any("[base-harness]" in str(m.get("content", "")) for m in result.messages)

    def test_empty_messages(self):
        comp = SimpleContextCompressor()
        result = comp.compress([], max_chars=1000)
        assert result.compressed is False
        assert result.messages == []

    def test_critical_cache_avoids_reparse(self):
        comp = SimpleContextCompressor()
        msg = {"role": "tool", "content": '{"error": "fail"}'}
        # First call populates cache
        assert comp._is_critical_tool_result(msg) is True
        # Second call uses cache
        assert comp._is_critical_tool_result(msg) is True
        assert id(msg) in comp._critical_cache

    def test_tool_summary_extraction(self):
        comp = SimpleContextCompressor()
        assert comp._tool_summary('{"path": "/tmp/f", "written": true}') == "Wrote /tmp/f"
        assert comp._tool_summary('{"path": "/tmp/f", "content": "data"}') == "Read /tmp/f: data"
        assert comp._tool_summary('{"exit_code": 0}') == "Exit 0"
        assert comp._tool_summary('{"matches": [], "count": 5}') == "Search: 5 matches"
        assert comp._tool_summary('{"files": [], "count": 3}') == "Find: 3 files"
        assert comp._tool_summary('{"error": "oops"}') == "Error: oops"
