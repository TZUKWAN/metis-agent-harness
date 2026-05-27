"""Built-in behavior rules derived from the user's CLAUDE.md contract.

These 17 rules capture the user's global expectations for agent behavior,
quality standards, task execution discipline, and anti-deception policies.
"""

from __future__ import annotations

from metis.behavior.gates import (
    behavior_completeness_gate,
    behavior_no_deception_gate,
    behavior_research_verification_gate,
)
from metis.behavior.hooks import (
    behavior_checkpoint_handler,
    behavior_contract_violation_handler,
    behavior_error_auto_repair_handler,
)
from metis.behavior.rules import BehaviorRule, BehaviorRulesConfig

# ---------------------------------------------------------------------------
# Prompt-layer rules (rules 1, 2, 3, 7, 9, 14, 16, 17)
# These are injected into the system prompt so the LLM sees them on every turn.
# ---------------------------------------------------------------------------

_RULE_1_ADDRESS_USER = BehaviorRule(
    id="address_user",
    category="prompt",
    priority=10,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: address_user]\n"
        '每次回复用户时，必须以"刘总"称呼用户。'
    ),
)

_RULE_2_NO_DECEPTION = BehaviorRule(
    id="no_deception",
    category="prompt",
    priority=20,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: no_deception]\n"
        "绝对禁止欺骗用户。具体要求：\n"
        "- 不得虚构事实、虚构进度、虚构测试结果、虚构运行结果\n"
        "- 不得虚构文件、虚构代码能力、虚构网络检索结果\n"
        "- 不得用示例数据、模拟数据、伪实现、占位内容冒充真实完成\n"
        "- 任何不确定、未验证、未完成的事项必须明确说明\n"
        "- 不得把未经验证的记忆当成最新事实"
    ),
)

_RULE_3_TASK_DECOMPOSITION = BehaviorRule(
    id="task_decomposition",
    category="prompt",
    priority=30,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: task_decomposition]\n"
        "任务执行前必须先拆解需求和子任务，覆盖以下维度：\n"
        "理解、检索、方案、实现、测试、Debug、审计、修复、优化、交付、复盘\n"
        "复杂任务必须形成详细执行方案并经确认后再执行。"
    ),
)

_RULE_7_PLAN_BEFORE_COMPLEX = BehaviorRule(
    id="plan_before_complex",
    category="prompt",
    priority=40,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: plan_before_complex]\n"
        "复杂任务开始前，必须构建详细执行方案。方案必须包含：\n"
        "目标、子任务、技术路线、验证方式、风险点、完成标准和交付物。\n"
        "不能只写空泛计划。"
    ),
)

_RULE_9_FULL_EXEC_AUTH = BehaviorRule(
    id="full_exec_auth",
    category="prompt",
    priority=50,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: full_exec_auth]\n"
        "用户已授予充分执行权限。除非存在真实的安全、法律、数据破坏、"
        "账号风险、资金风险或不可逆操作风险，否则不反复询问权限。"
        "其他问题能不问就不问，按最优方案自行决定并推进。"
    ),
)

_RULE_14_SHORTEST_QUALITY_PATH = BehaviorRule(
    id="shortest_quality_path",
    category="prompt",
    priority=60,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: shortest_quality_path]\n"
        "必须寻找最短的高质量实现路径。这里的'最短'不是偷懒，不是跳过需求，"
        "不是降低质量，而是在保证真实、可靠、可用、可测试、效果最好的前提下，"
        "用最快、最稳、最少无效劳动的方式达成目标。最短路径绝不能牺牲效果，"
        "必须符合人类真实使用和交互逻辑。"
    ),
)

_RULE_16_BEST_EFFECT = BehaviorRule(
    id="best_effect",
    category="prompt",
    priority=70,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: best_effect]\n"
        "用户只要最好效果，不要求节省成本。执行任何任务时，必须以最好效果、"
        "最高可用性、最高可靠性、最高可信度为目标，不以节省token、节省调用、"
        "节省时间、节省工具成本、节省检索成本为优先。为了达到最好效果，可以不惜"
        "投入更多检索、推理、实现、测试、审计、重构、验证、修复、复盘和多轮迭代成本；"
        "可以多源交叉验证、多方案比较、多工具协同、多智能体协作。"
    ),
)

_RULE_17_GOAL_MODE = BehaviorRule(
    id="goal_mode",
    category="prompt",
    priority=80,
    enabled=True,
    prompt_text=(
        "[Behavior Rule: goal_mode]\n"
        "当进入goal模式后，不要向用户提问是否继续。目标是基于用户设定的goal，"
        "通过不断的迭代，交付高质量可用可信可靠的成果，在完成这个目标前，"
        "不要退出，无需询问用户是否继续，只要达到最终目标，完美交付。"
    ),
)

# ---------------------------------------------------------------------------
# Hook-layer rules (rules 5, 8, 13)
# These register handlers on the HookBus for runtime automation.
# ---------------------------------------------------------------------------

_RULE_5_CHECKPOINTS = BehaviorRule(
    id="high_density_checkpoints",
    category="hook",
    priority=100,
    enabled=True,
    hook_event="behavior.checkpoint",
    hook_handler=behavior_checkpoint_handler,
)

_RULE_8_AUTO_REPAIR = BehaviorRule(
    id="auto_repair_on_error",
    category="hook",
    priority=90,
    enabled=True,
    hook_event="agent.error",
    hook_handler=behavior_error_auto_repair_handler,
)

_RULE_13_NO_AGENT_DECEPTION = BehaviorRule(
    id="no_agent_deception",
    category="hook",
    priority=95,
    enabled=True,
    hook_event="behavior.contract_violation",
    hook_handler=behavior_contract_violation_handler,
)

# ---------------------------------------------------------------------------
# Gate-layer rules (rules 4, 10, 11, 12, 15)
# These are evaluated during finalization as quality gates.
# ---------------------------------------------------------------------------

_RULE_10_COMPLETENESS = BehaviorRule(
    id="completeness_gate",
    category="gate",
    priority=100,
    enabled=True,
    gate_spec=behavior_completeness_gate(),
)

_RULE_12_NO_FAKE_COMPLETION = BehaviorRule(
    id="no_fake_completion_gate",
    category="gate",
    priority=110,
    enabled=True,
    gate_spec=behavior_no_deception_gate(),
)

_RULE_11_RESEARCH_VERIFY = BehaviorRule(
    id="research_verification_gate",
    category="gate",
    priority=90,
    enabled=True,
    gate_spec=behavior_research_verification_gate(),
)

# ---------------------------------------------------------------------------
# Contract-layer rules (rule 6)
# These merge constraints into TaskContractV1.
# ---------------------------------------------------------------------------

_RULE_6_ACTIVE_RESEARCH = BehaviorRule(
    id="active_research",
    category="contract",
    priority=50,
    enabled=True,
    contract_field="evidence_requirements",
    contract_value=(
        "If the task requires external knowledge, research must be performed using "
        "available tools (web_search, web_fetch, literature_search) before implementation. "
        "Research evidence must be recorded in the evidence ledger."
    ),
)

# ---------------------------------------------------------------------------
# Aggregated built-in rule set
# ---------------------------------------------------------------------------

BUILT_IN_RULES: list[BehaviorRule] = [
    # Prompt layer
    _RULE_1_ADDRESS_USER,
    _RULE_2_NO_DECEPTION,
    _RULE_3_TASK_DECOMPOSITION,
    _RULE_7_PLAN_BEFORE_COMPLEX,
    _RULE_9_FULL_EXEC_AUTH,
    _RULE_14_SHORTEST_QUALITY_PATH,
    _RULE_16_BEST_EFFECT,
    _RULE_17_GOAL_MODE,
    # Hook layer
    _RULE_5_CHECKPOINTS,
    _RULE_8_AUTO_REPAIR,
    _RULE_13_NO_AGENT_DECEPTION,
    # Gate layer
    _RULE_10_COMPLETENESS,
    _RULE_12_NO_FAKE_COMPLETION,
    _RULE_11_RESEARCH_VERIFY,
    # Contract layer
    _RULE_6_ACTIVE_RESEARCH,
]


def build_behavior_rules_config(
    *,
    enabled_ids: set[str] | None = None,
    auto_audit: bool = True,
    swarm_audit_enabled: bool = True,
) -> BehaviorRulesConfig:
    """Build a BehaviorRulesConfig from the built-in rule set.

    Args:
        enabled_ids: If provided, only rules whose id is in this set are enabled.
                     If None, all built-in rules are enabled by default.
        auto_audit: Whether to run automatic audit gates after each run.
        swarm_audit_enabled: Whether to inject an auditor agent in swarm mode.
    """
    rules = []
    for rule in BUILT_IN_RULES:
        if enabled_ids is not None:
            rule = BehaviorRule(
                id=rule.id,
                category=rule.category,
                priority=rule.priority,
                enabled=rule.id in enabled_ids,
                prompt_text=rule.prompt_text,
                hook_event=rule.hook_event,
                hook_handler=rule.hook_handler,
                gate_spec=rule.gate_spec,
                contract_field=rule.contract_field,
                contract_value=rule.contract_value,
            )
        rules.append(rule)
    return BehaviorRulesConfig(
        rules=rules,
        auto_audit=auto_audit,
        swarm_audit_enabled=swarm_audit_enabled,
    )
