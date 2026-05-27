"""Tests for the Behavior Rules Engine data models and registry."""

from __future__ import annotations

import pytest

from metis.behavior.builtin import BUILT_IN_RULES, build_behavior_rules_config
from metis.behavior.rules import BehaviorRule, BehaviorRulesConfig
from metis.behavior.registry import BehaviorRulesRegistry
from metis.prompts.assembler import PromptAssembler, PromptParts


class TestBehaviorRule:
    def test_rule_creation(self) -> None:
        rule = BehaviorRule(
            id="test_rule",
            category="prompt",
            priority=50,
            enabled=True,
            prompt_text="Test prompt",
        )
        assert rule.id == "test_rule"
        assert rule.category == "prompt"
        assert rule.priority == 50
        assert rule.enabled is True
        assert rule.prompt_text == "Test prompt"

    def test_rule_to_dict(self) -> None:
        rule = BehaviorRule(id="r1", category="hook", priority=10, enabled=False)
        d = rule.to_dict()
        assert d["id"] == "r1"
        assert d["category"] == "hook"
        assert d["enabled"] is False


class TestBehaviorRulesConfig:
    def test_empty_config(self) -> None:
        cfg = BehaviorRulesConfig()
        assert cfg.get_prompt_rules() == []
        assert cfg.get_hook_rules() == []
        assert cfg.get_gate_rules() == []
        assert cfg.get_contract_rules() == []

    def test_filtering_by_category(self) -> None:
        rules = [
            BehaviorRule(id="p1", category="prompt", priority=1, enabled=True),
            BehaviorRule(id="p2", category="prompt", priority=2, enabled=False),
            BehaviorRule(id="h1", category="hook", priority=3, enabled=True),
            BehaviorRule(id="g1", category="gate", priority=4, enabled=True),
        ]
        cfg = BehaviorRulesConfig(rules=rules)
        assert len(cfg.get_prompt_rules()) == 1  # only enabled
        assert len(cfg.get_hook_rules()) == 1
        assert len(cfg.get_gate_rules()) == 1


class TestBuiltInRules:
    def test_all_rules_have_unique_ids(self) -> None:
        ids = [r.id for r in BUILT_IN_RULES]
        assert len(ids) == len(set(ids))

    def test_prompt_rules_have_text(self) -> None:
        for rule in BUILT_IN_RULES:
            if rule.category == "prompt":
                assert rule.prompt_text, f"Prompt rule {rule.id} has empty text"

    def test_hook_rules_have_handler(self) -> None:
        for rule in BUILT_IN_RULES:
            if rule.category == "hook":
                assert rule.hook_handler is not None, f"Hook rule {rule.id} has no handler"
                assert rule.hook_event, f"Hook rule {rule.id} has no event"

    def test_gate_rules_have_spec(self) -> None:
        for rule in BUILT_IN_RULES:
            if rule.category == "gate":
                assert rule.gate_spec is not None, f"Gate rule {rule.id} has no spec"

    def test_build_config_defaults(self) -> None:
        cfg = build_behavior_rules_config()
        assert len(cfg.rules) == len(BUILT_IN_RULES)
        assert cfg.auto_audit is True
        assert cfg.swarm_audit_enabled is True

    def test_build_config_with_enabled_ids(self) -> None:
        cfg = build_behavior_rules_config(enabled_ids={"address_user", "no_deception"})
        enabled = [r for r in cfg.rules if r.enabled]
        assert len(enabled) == 2
        assert {r.id for r in enabled} == {"address_user", "no_deception"}


class TestBehaviorRulesRegistry:
    def test_default_registry(self) -> None:
        reg = BehaviorRulesRegistry.default()
        assert len(reg.config.rules) == len(BUILT_IN_RULES)

    def test_from_manifest_empty(self) -> None:
        reg = BehaviorRulesRegistry.from_manifest({})
        assert len(reg.config.rules) == len(BUILT_IN_RULES)

    def test_from_manifest_with_behavior_rules(self) -> None:
        reg = BehaviorRulesRegistry.from_manifest({
            "behavior_rules": {"enabled_ids": ["address_user"], "auto_audit": False}
        })
        enabled = [r for r in reg.config.rules if r.enabled]
        assert len(enabled) == 1
        assert enabled[0].id == "address_user"
        assert reg.config.auto_audit is False

    def test_get_prompt_content(self) -> None:
        reg = BehaviorRulesRegistry.default()
        content = reg.get_prompt_content()
        assert "刘总" in content
        assert "no_deception" in content
        assert "task_decomposition" in content

    def test_inject_prompt_layer(self) -> None:
        reg = BehaviorRulesRegistry.default()
        assembler = PromptAssembler()
        stack = assembler.build_stack(PromptParts(user_message="test"))
        original_types = [l.layer_type for l in stack.layers]
        assert "behavior-rules" not in original_types

        new_stack = reg.inject_prompt_layer(stack)
        new_types = [l.layer_type for l in new_stack.layers]
        assert "behavior-rules" in new_types

    def test_inject_into_assembler(self) -> None:
        reg = BehaviorRulesRegistry.default()
        assembler = PromptAssembler()
        stack = reg.inject_into_assembler(assembler, PromptParts(user_message="test"))
        types = [l.layer_type for l in stack.layers]
        assert "behavior-rules" in types
        behavior_layer = [l for l in stack.layers if l.layer_type == "behavior-rules"][0]
        assert "刘总" in behavior_layer.content

    def test_get_prompt_content_empty_when_disabled(self) -> None:
        cfg = build_behavior_rules_config(enabled_ids=set())
        reg = BehaviorRulesRegistry(cfg)
        assert reg.get_prompt_content() == ""
