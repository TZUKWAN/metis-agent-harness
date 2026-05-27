"""Metis Behavior Rules Engine — internalizes user behavioral contracts into runtime."""

from __future__ import annotations

from metis.behavior.builtin import BUILT_IN_RULES, build_behavior_rules_config
from metis.behavior.rules import BehaviorRule, BehaviorRulesConfig
from metis.behavior.registry import BehaviorRulesRegistry

__all__ = [
    "BehaviorRule",
    "BehaviorRulesConfig",
    "BehaviorRulesRegistry",
    "BUILT_IN_RULES",
    "build_behavior_rules_config",
]
