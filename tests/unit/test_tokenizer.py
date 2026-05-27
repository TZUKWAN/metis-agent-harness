"""Tests for context token estimation."""

from __future__ import annotations

import pytest

from metis.context.tokenizer import (
    CharTokenEstimator,
    CompositeTokenEstimator,
    LanguageAwareTokenEstimator,
)


class TestCharTokenEstimator:
    def test_empty(self):
        est = CharTokenEstimator(chars_per_token=4)
        assert est.estimate("") == 0

    def test_latin(self):
        est = CharTokenEstimator(chars_per_token=4)
        assert est.estimate("abcd") == 1

    def test_cjk(self):
        est = CharTokenEstimator(chars_per_token=4)
        # "这是一个测试" = 6 chars -> 6/4 = 1.5 -> int = 1
        assert est.estimate("这是一个测试") == 1


class TestLanguageAwareTokenEstimator:
    def test_empty(self):
        est = LanguageAwareTokenEstimator()
        assert est.estimate("") == 0

    def test_pure_cjk(self):
        est = LanguageAwareTokenEstimator()
        text = "这是一段纯中文文本用于测试密度"
        tokens = est.estimate(text)
        # CJK density is 1.3 chars/token
        expected = int(len(text) / 1.3)
        assert tokens == expected

    def test_pure_latin(self):
        est = LanguageAwareTokenEstimator()
        text = "This is a pure English text for testing density calculations."
        tokens = est.estimate(text)
        expected = int(len(text) / 3.8)
        assert tokens == expected

    def test_mixed(self):
        est = LanguageAwareTokenEstimator()
        text = "这是中文 mixed with English 混合文本"
        tokens = est.estimate(text)
        # cjk_ratio > 0.25 but <= 0.6, so uses DENSITY_MIXED = 2.0
        expected = int(len(text) / 2.0)
        assert tokens == expected

    def test_code_density(self):
        est = LanguageAwareTokenEstimator()
        text = '{"key": "value", "arr": [1, 2, 3]}'
        tokens = est.estimate(text)
        # code_ratio > 0.05, uses DENSITY_CODE = 3.5
        # punctuation penalty may reduce density further
        expected = int(len(text) / 3.5)
        assert tokens >= int(len(text) / 3.5) * 0.8  # allow for punct penalty

    def test_punctuation_penalty(self):
        est = LanguageAwareTokenEstimator()
        text = "Hello, world! This is a test. With many!!! punctuation??? marks..."
        tokens = est.estimate(text)
        # punct_ratio > 0.15, density reduced by 0.85
        assert tokens > int(len(text) / 3.8)

    def test_default_density_override(self):
        est = LanguageAwareTokenEstimator(default_density=5.0)
        text = "任意文本"
        assert est.estimate(text) == int(len(text) / 5.0)

    def test_count_cjk(self):
        assert LanguageAwareTokenEstimator._count_cjk("中文") == 2
        assert LanguageAwareTokenEstimator._count_cjk("hello") == 0
        assert LanguageAwareTokenEstimator._count_cjk("hello中文") == 2

    def test_count_latin(self):
        assert LanguageAwareTokenEstimator._count_latin("abc") == 3
        assert LanguageAwareTokenEstimator._count_latin("123") == 0
        assert LanguageAwareTokenEstimator._count_latin("abc123") == 3


class TestCompositeTokenEstimator:
    def test_empty_messages(self):
        est = CompositeTokenEstimator()
        assert est.estimate_messages([]) == 0

    def test_simple_message(self):
        est = CompositeTokenEstimator()
        messages = [{"role": "user", "content": "Hello world"}]
        assert est.estimate_messages(messages) > 0

    def test_message_with_reasoning(self):
        est = CompositeTokenEstimator()
        messages = [{"role": "assistant", "content": "Answer", "reasoning_content": "Let me think..."}]
        total = est.estimate_messages(messages)
        assert total > est.text_estimator.estimate("Answer")

    def test_message_with_tool_calls(self):
        est = CompositeTokenEstimator()
        messages = [{
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "1", "function": {"name": "test", "arguments": "{}"}}],
        }]
        total = est.estimate_messages(messages)
        assert total > 0

    def test_tool_schemas(self):
        est = CompositeTokenEstimator()
        schemas = [{"type": "function", "function": {"name": "test"}}]
        assert est.estimate_tool_schemas(schemas) > 0

    def test_estimate_total(self):
        est = CompositeTokenEstimator()
        messages = [{"role": "user", "content": "Hello"}]
        schemas = [{"type": "function", "function": {"name": "test"}}]
        total = est.estimate_total(messages, schemas)
        assert total == est.estimate_messages(messages) + est.estimate_tool_schemas(schemas)

    def test_estimate_total_no_schemas(self):
        est = CompositeTokenEstimator()
        messages = [{"role": "user", "content": "Hello"}]
        assert est.estimate_total(messages) == est.estimate_messages(messages)
