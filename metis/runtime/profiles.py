"""Model execution profiles."""

from __future__ import annotations

from dataclasses import dataclass

from metis.runtime.budgets import BudgetConfig


@dataclass(frozen=True)
class ModelProfile:
    name: str
    budget: BudgetConfig
    max_tools_per_turn: int = 16
    max_tool_calls_per_turn: int = 16
    one_tool_call_per_turn: bool = False
    strict_output: bool = False
    strict_output_soft: bool = False
    require_done_evidence_refs: bool = False
    parser_repair_retries: int = 1
    max_tool_repair_retries: int = 2
    max_session_tool_calls: int = 200
    concurrent_tool_dispatch: bool = False


PROFILES = {
    "small": ModelProfile(
        name="small",
        budget=BudgetConfig.for_profile("small"),
        max_tools_per_turn=8,
        max_tool_calls_per_turn=8,
        one_tool_call_per_turn=True,
        strict_output=True,
        strict_output_soft=True,
        parser_repair_retries=2,
        max_tool_repair_retries=1,
        max_session_tool_calls=150,
    ),
    "balanced": ModelProfile(
        name="balanced",
        budget=BudgetConfig.for_profile("default"),
        max_tools_per_turn=16,
        max_tool_calls_per_turn=12,
        strict_output=True,
        parser_repair_retries=1,
        max_tool_repair_retries=2,
    ),
    "small_strict": ModelProfile(
        name="small_strict",
        budget=BudgetConfig.for_profile("small"),
        max_tools_per_turn=8,
        max_tool_calls_per_turn=8,
        one_tool_call_per_turn=True,
        strict_output=True,
        require_done_evidence_refs=True,
        parser_repair_retries=2,
        max_tool_repair_retries=1,
    ),
    "deep": ModelProfile(
        name="deep",
        budget=BudgetConfig.for_profile("deep"),
        max_tools_per_turn=64,
        max_tool_calls_per_turn=32,
        strict_output=False,
        parser_repair_retries=1,
        max_tool_repair_retries=4,
        max_session_tool_calls=500,
        concurrent_tool_dispatch=True,
    ),
}


def get_model_profile(name: str | ModelProfile = "small") -> ModelProfile:
    if isinstance(name, ModelProfile):
        return name
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown model profile: {name}") from exc
