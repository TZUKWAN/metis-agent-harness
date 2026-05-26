"""Tests for optimized 8B model system prompt."""

from __future__ import annotations

from metis.prompts.assembler import SMALL_MODEL_IDENTITY, PromptAssembler, PromptParts


def test_small_model_identity_contains_tool_guidance():
    assert "read_file" in SMALL_MODEL_IDENTITY
    assert "read_file_range" in SMALL_MODEL_IDENTITY
    assert "search_code" in SMALL_MODEL_IDENTITY
    assert "list_directory" in SMALL_MODEL_IDENTITY


def test_small_model_identity_contains_error_handling():
    assert "error message" in SMALL_MODEL_IDENTITY.lower() or "error" in SMALL_MODEL_IDENTITY.lower()


def test_small_model_identity_has_multi_step_guidance():
    assert "plan" in SMALL_MODEL_IDENTITY.lower()


def test_prompt_assembler_uses_small_identity():
    parts = PromptParts(user_message="test", strict_output_soft=True)
    stack = PromptAssembler().build_stack(parts)
    system = stack.to_system_content()
    assert "Metis Executor" in system
    assert "read_file" in system
