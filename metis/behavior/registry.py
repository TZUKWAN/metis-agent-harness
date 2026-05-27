"""Behavior-rules registry — loads, merges, and injects rules into the runtime.

The registry is responsible for:
1. Loading built-in rules
2. Loading custom rules from manifest configuration
3. Injecting prompt rules into the PromptAssembler
4. Registering hook rules on the HookBus
5. Collecting gate rules for finalization
6. Merging contract rules into TaskContractV1
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from metis.behavior.rules import BehaviorRule, BehaviorRulesConfig
from metis.behavior.builtin import build_behavior_rules_config
from metis.events.hooks import HookBus
from metis.prompts.assembler import PromptAssembler, PromptLayer, PromptParts, PromptStack


class BehaviorRulesRegistry:
    """Central registry for all active behavior rules."""

    def __init__(self, config: BehaviorRulesConfig | None = None) -> None:
        self.config = config or build_behavior_rules_config()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def from_manifest(cls, manifest_data: dict[str, Any]) -> "BehaviorRulesRegistry":
        """Create a registry from manifest JSON data."""
        behavior_cfg = manifest_data.get("behavior_rules", {})
        enabled_ids = set(behavior_cfg.get("enabled_ids", []))
        # If no explicit enabled_ids, enable all built-in rules
        if not enabled_ids:
            from metis.behavior.builtin import BUILT_IN_RULES
            enabled_ids = {r.id for r in BUILT_IN_RULES}

        config = build_behavior_rules_config(
            enabled_ids=enabled_ids,
            auto_audit=behavior_cfg.get("auto_audit", True),
            swarm_audit_enabled=behavior_cfg.get("swarm_audit_enabled", True),
        )
        return cls(config)

    @classmethod
    def default(cls) -> "BehaviorRulesRegistry":
        """Registry with all built-in rules enabled."""
        return cls(build_behavior_rules_config())

    # ------------------------------------------------------------------
    # Prompt-layer injection
    # ------------------------------------------------------------------

    def get_prompt_content(self) -> str:
        """Generate the combined prompt text for all active prompt rules.

        Rules are sorted by priority and concatenated with clear separators.
        """
        rules = sorted(self.config.get_prompt_rules(), key=lambda r: r.priority)
        if not rules:
            return ""
        sections: list[str] = []
        for rule in rules:
            if rule.prompt_text:
                sections.append(rule.prompt_text)
        return "\n\n".join(sections)

    def inject_prompt_layer(self, stack: PromptStack) -> PromptStack:
        """Insert the behavior-rules layer into an existing PromptStack.

        The layer is placed immediately after the task-contract layer (if present)
        so it has high precedence but does not override base identity.
        """
        content = self.get_prompt_content()
        if not content:
            return stack

        behavior_layer = PromptLayer(
            layer_type="behavior-rules",
            content=content,
            source="metis.behavior.registry",
            version="v1",
            metadata={"rule_count": len(self.config.get_prompt_rules())},
        )

        # Insert after task-contract layer, or at the beginning if not found
        new_layers: list[PromptLayer] = []
        inserted = False
        for layer in stack.layers:
            new_layers.append(layer)
            if layer.layer_type == "task-contract" and not inserted:
                new_layers.append(behavior_layer)
                inserted = True
        if not inserted:
            # Insert after base-harness (index 1) or at the end
            if new_layers and new_layers[0].layer_type == "base-harness":
                new_layers.insert(1, behavior_layer)
            else:
                new_layers.insert(0, behavior_layer)

        return PromptStack(layers=new_layers)

    def inject_into_assembler(self, assembler: PromptAssembler, parts: PromptParts) -> PromptStack:
        """Build a prompt stack via the assembler and then inject behavior rules."""
        stack = assembler.build_stack(parts)
        return self.inject_prompt_layer(stack)

    # ------------------------------------------------------------------
    # Hook-layer registration
    # ------------------------------------------------------------------

    def register_hooks(self, hooks: HookBus) -> None:
        """Register all active hook rules on the given HookBus."""
        for rule in self.config.get_hook_rules():
            if rule.hook_handler is None:
                continue
            hooks.register(
                event=rule.hook_event,
                handler=rule.hook_handler,
                priority=rule.priority,
                name=f"behavior.{rule.id}",
            )

    # ------------------------------------------------------------------
    # Gate-layer collection
    # ------------------------------------------------------------------

    def get_gate_specs(self) -> list[Any]:
        """Return all active gate spec handlers."""
        return [
            rule.gate_spec
            for rule in self.config.get_gate_rules()
            if rule.gate_spec is not None
        ]

    # ------------------------------------------------------------------
    # Contract-layer collection
    # ------------------------------------------------------------------

    def get_contract_overrides(self) -> dict[str, list[Any]]:
        """Return contract field overrides grouped by field name.

        Each value is a list of contract_values from active contract rules.
        """
        overrides: dict[str, list[Any]] = {}
        for rule in self.config.get_contract_rules():
            if rule.contract_field:
                overrides.setdefault(rule.contract_field, []).append(rule.contract_value)
        return overrides
