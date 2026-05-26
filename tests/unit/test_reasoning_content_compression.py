"""Tests for reasoning_content awareness in context compression."""

from __future__ import annotations

from metis.context.compressor import SimpleContextCompressor
from metis.context.engine import ContextEngine


def test_engine_count_chars_includes_reasoning():
    messages = [
        {"role": "assistant", "content": "ok", "reasoning_content": "Let me think..." * 10},
    ]
    total = ContextEngine._count_chars(messages)
    content_len = len("ok")
    reasoning_len = len("Let me think..." * 10)
    assert total == content_len + reasoning_len


def test_compressor_count_chars_includes_reasoning():
    messages = [
        {"role": "assistant", "content": "x", "reasoning_content": "y" * 100},
    ]
    total = SimpleContextCompressor._count_chars(messages)
    assert total == 1 + 100


def test_score_assistant_with_reasoning_higher_than_text():
    text_only = {"role": "assistant", "content": "ok"}
    with_reasoning = {"role": "assistant", "content": "ok", "reasoning_content": "thinking..."}
    assert SimpleContextCompressor._score_message(text_only, 0, 5) == 50
    assert SimpleContextCompressor._score_message(with_reasoning, 0, 5) == 65


def test_score_assistant_with_tools_higher_than_reasoning():
    with_tools = {"role": "assistant", "content": "", "tool_calls": []}
    with_reasoning = {"role": "assistant", "content": "ok", "reasoning_content": "thinking..."}
    assert SimpleContextCompressor._score_message(with_tools, 0, 5) == 70
    assert SimpleContextCompressor._score_message(with_reasoning, 0, 5) == 65


def test_compression_triggered_by_reasoning_content():
    engine = ContextEngine(chars_per_token=4)
    messages = [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok", "reasoning_content": "A" * 300_000},
    ]
    result = engine.build(messages)
    assert result.compressed is True
    assert result.original_chars > len("SYS") + len("hi") + len("ok")


def test_force_fit_preserves_reasoning_content():
    compressor = SimpleContextCompressor()
    messages = [
        {"role": "system", "content": "S"},
        {"role": "assistant", "content": "A", "reasoning_content": "R" * 200},
        {"role": "tool", "content": "ok", "name": "read"},
    ]
    result = compressor._force_fit(messages, 50)
    assistant_msgs = [m for m in result if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert "R" in assistant_msgs[0].get("reasoning_content", "")
