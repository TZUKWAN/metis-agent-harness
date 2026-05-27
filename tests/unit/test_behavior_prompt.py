"""Tests verifying behavior-rules prompt injection into the runtime."""

from __future__ import annotations

from metis.app.manifest import AgentAppManifest
from metis.app.runtime import build_runtime_prompt_stack
from metis.behavior.registry import BehaviorRulesRegistry
from metis.prompts.assembler import PromptAssembler, PromptParts


class TestBehaviorPromptInjection:
    def test_behavior_rules_in_prompt_stack(self) -> None:
        manifest = AgentAppManifest(
            name="Test App",
            behavior_rules_enabled=True,
        )
        stack = build_runtime_prompt_stack("Hello", manifest=manifest)
        types = [l.layer_type for l in stack.layers]
        assert "behavior-rules" in types

    def test_behavior_rules_disabled_no_layer(self) -> None:
        manifest = AgentAppManifest(
            name="Test App",
            behavior_rules_enabled=False,
        )
        stack = build_runtime_prompt_stack("Hello", manifest=manifest)
        types = [l.layer_type for l in stack.layers]
        assert "behavior-rules" not in types

    def test_prompt_contains_liu_zong(self) -> None:
        manifest = AgentAppManifest(
            name="Test App",
            behavior_rules_enabled=True,
        )
        stack = build_runtime_prompt_stack("Hello", manifest=manifest)
        behavior_layer = [l for l in stack.layers if l.layer_type == "behavior-rules"][0]
        assert "刘总" in behavior_layer.content

    def test_prompt_contains_no_deception(self) -> None:
        manifest = AgentAppManifest(
            name="Test App",
            behavior_rules_enabled=True,
        )
        stack = build_runtime_prompt_stack("Hello", manifest=manifest)
        behavior_layer = [l for l in stack.layers if l.layer_type == "behavior-rules"][0]
        assert "no_deception" in behavior_layer.content or "欺骗" in behavior_layer.content

    def test_prompt_contains_task_decomposition(self) -> None:
        manifest = AgentAppManifest(
            name="Test App",
            behavior_rules_enabled=True,
        )
        stack = build_runtime_prompt_stack("Hello", manifest=manifest)
        behavior_layer = [l for l in stack.layers if l.layer_type == "behavior-rules"][0]
        assert "task_decomposition" in behavior_layer.content or "拆解" in behavior_layer.content

    def test_prompt_contains_goal_mode(self) -> None:
        manifest = AgentAppManifest(
            name="Test App",
            behavior_rules_enabled=True,
        )
        stack = build_runtime_prompt_stack("Hello", manifest=manifest)
        behavior_layer = [l for l in stack.layers if l.layer_type == "behavior-rules"][0]
        assert "goal_mode" in behavior_layer.content or "goal模式" in behavior_layer.content
