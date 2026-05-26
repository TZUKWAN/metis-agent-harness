"""Tests for enhanced context compression with tool result trimming."""

from __future__ import annotations

import json

from metis.context.compressor import SimpleContextCompressor


def test_trim_large_tool_result():
    compressor = SimpleContextCompressor(max_tool_result_chars=100)
    large_content = "x" * 500
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "tool", "content": large_content, "name": "read_file"},
        {"role": "assistant", "content": "done"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert len(result) == 3
    assert result[1]["content"].startswith("xxx")
    assert "trimmed" in result[1]["content"]
    assert len(result[1]["content"]) < 200


def test_trim_preserves_small_tool_results():
    compressor = SimpleContextCompressor(max_tool_result_chars=1000)
    messages = [
        {"role": "tool", "content": "short result", "name": "test"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert result[0]["content"] == "short result"


def test_trim_preserves_non_tool_messages():
    compressor = SimpleContextCompressor(max_tool_result_chars=50)
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user message"},
        {"role": "assistant", "content": "response"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert result[0]["content"] == "system prompt"
    assert result[1]["content"] == "user message"
    assert result[2]["content"] == "response"


def test_tool_summary_search():
    compressor = SimpleContextCompressor()
    import json
    content = json.dumps({"matches": [{"file": "a.py"}], "count": 5})
    assert "5 matches" in compressor._tool_summary(content)


def test_tool_summary_find_files():
    compressor = SimpleContextCompressor()
    import json
    content = json.dumps({"files": [{"path": "a.py"}], "count": 3})
    assert "3 files" in compressor._tool_summary(content)


def test_tool_summary_count_lines():
    compressor = SimpleContextCompressor()
    import json
    content = json.dumps({"total_lines": 100, "non_empty_lines": 80, "blank_lines": 20})
    assert "100 total" in compressor._tool_summary(content)


def test_tool_summary_file_info():
    compressor = SimpleContextCompressor()
    import json
    content = json.dumps({"name": "test.py", "size": 1024, "is_file": True})
    assert "FileInfo" in compressor._tool_summary(content)


def test_tool_summary_result_key():
    compressor = SimpleContextCompressor()
    import json
    content = json.dumps({"result": {"key": "value"}, "evidence_refs": []})
    assert "value" in compressor._tool_summary(content)


def test_compress_with_large_tool_result_auto_trims():
    compressor = SimpleContextCompressor(max_tool_result_chars=50, keep_recent=2)
    large = "A" * 10000
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "go"},
        {"role": "tool", "content": large, "name": "read"},
        {"role": "assistant", "content": "ok"},
    ]
    result = compressor.compress(messages, max_chars=5000)
    assert result.compressed is True
    assert result.compressed_chars < 10000


def test_critical_tool_result_with_error_gets_larger_limit():
    compressor = SimpleContextCompressor(max_tool_result_chars=100)
    # 267 chars: exceeds 100 but fits in 3x limit (300)
    large_error = json.dumps({"error": "x" * 250})
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "tool", "content": large_error, "name": "run_shell"},
        {"role": "assistant", "content": "done"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert len(result) == 3
    error_content = result[1]["content"]
    assert len(error_content) > 200
    assert "trimmed" not in error_content


def test_critical_tool_result_with_status_blocked():
    compressor = SimpleContextCompressor(max_tool_result_chars=100)
    large_blocked = json.dumps({"status": "blocked", "reason": "x" * 500})
    messages = [
        {"role": "tool", "content": large_blocked, "name": "write_file", "status": "blocked"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert len(result[0]["content"]) > 300


def test_critical_tool_result_with_write_confirmation():
    compressor = SimpleContextCompressor(max_tool_result_chars=100)
    large_write = json.dumps({"written": True, "path": "test.py", "detail": "x" * 500})
    messages = [
        {"role": "tool", "content": large_write, "name": "write_file"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert len(result[0]["content"]) > 300


def test_non_critical_tool_result_still_trimmed():
    compressor = SimpleContextCompressor(max_tool_result_chars=100)
    large_ok = json.dumps({"result": "x" * 500})
    messages = [
        {"role": "tool", "content": large_ok, "name": "read_file"},
    ]
    result = compressor._trim_large_tool_results(messages)
    assert "trimmed" in result[0]["content"]


def test_is_critical_tool_result_detects_error():
    assert SimpleContextCompressor._is_critical_tool_result({"content": json.dumps({"error": "fail"}), "role": "tool"})
    assert SimpleContextCompressor._is_critical_tool_result({"content": "something", "status": "failed", "role": "tool"})
    assert not SimpleContextCompressor._is_critical_tool_result({"content": json.dumps({"result": "ok"}), "role": "tool"})


def test_summary_marks_critical_results():
    compressor = SimpleContextCompressor(max_summary_chars=1000, keep_recent=2)
    messages = [
        {"role": "user", "content": "go"},
        {"role": "tool", "content": json.dumps({"error": "something went wrong"}), "name": "run_shell"},
    ]
    summary = compressor._summarize(messages)
    assert "[CRITICAL]" in summary
