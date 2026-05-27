# Metis Behavior Rules Engine

The Behavior Rules Engine internalizes user behavioral contracts (such as the
17 global rules from `CLAUDE.md`) into active Metis runtime capabilities.

## Overview

Instead of relying solely on a static configuration file, the Behavior Rules
Engine injects rules into four runtime layers:

| Layer | Mechanism | Rules Applied |
|-------|-----------|---------------|
| **Prompt** | Injected as a `PromptLayer` into the system prompt stack | Rules 1, 2, 3, 7, 9, 14, 16, 17 |
| **Hook** | Registered on `HookBus` for runtime automation | Rules 5, 8, 13 |
| **Gate** | Evaluated during `AgentLoop` finalization | Rules 10, 11, 12, 15 |
| **Contract** | Merged into `TaskContractV1` constraints | Rule 6 |
| **Swarm** | Injected into coordinator decomposition prompt | Rule 4 |

## Configuration

Enable or disable behavior rules via `metis-agent.json`:

```json
{
  "behavior_rules_enabled": true,
  "behavior_rules_path": "",
  "auto_audit_enabled": true,
  "swarm_audit_enabled": true,
  "behavior_rules": {
    "enabled_ids": ["address_user", "no_deception", "task_decomposition"],
    "auto_audit": true,
    "swarm_audit_enabled": true
  }
}
```

Or via environment variables:

```bash
export METIS_BEHAVIOR_RULES_ENABLED=true
export METIS_AUTO_AUDIT_ENABLED=true
export METIS_SWARM_AUDIT_ENABLED=true
```

If `enabled_ids` is omitted, all built-in rules are enabled by default.

## Built-in Rules

### Prompt-layer Rules

These rules are concatenated and injected as a `behavior-rules` prompt layer
immediately after the `task-contract` layer.

- **`address_user`** — Always address the user as "刘总"
- **`no_deception`** — Never fabricate facts, progress, tests, files, or research
- **`task_decomposition`** — Decompose tasks into 11 phases: understanding, research, design, implementation, testing, debug, audit, fix, optimization, delivery, review
- **`plan_before_complex`** — Build a detailed execution plan before complex tasks
- **`full_exec_auth`** — Do not ask for permission unless there is a real safety/legal risk
- **`shortest_quality_path`** — Find the shortest high-quality implementation path without cutting corners
- **`best_effect`** — Prioritize best effect, highest availability, reliability, and credibility over cost
- **`goal_mode`** — In goal mode, do not ask the user whether to continue; iterate until the goal is achieved

### Hook-layer Rules

- **`high_density_checkpoints`** — Emits `behavior.checkpoint` events at turn start/complete for observability
- **`auto_repair_on_error`** — Classifies errors and flags auto-repair eligibility
- **`no_agent_deception`** — Records contract-violation events when deception is detected

### Gate-layer Rules

- **`behavior_completeness`** — Warns if tests are mentioned but not executed, or artifacts are claimed but missing
- **`behavior_no_deception`** — Fails if placeholder text (TODO, FIXME, simulated data) or completion claims without evidence are detected
- **`behavior_research_verification`** — Warns if external references are made without research tool evidence

### Contract-layer Rules

- **`active_research`** — Merges into `TaskContractV1.evidence_requirements` requiring research tools when external knowledge is needed

## Programmatic API

### Loading Rules

```python
from metis.behavior import BehaviorRulesRegistry

# Default: all built-in rules enabled
registry = BehaviorRulesRegistry.default()

# From manifest
registry = BehaviorRulesRegistry.from_manifest({
    "behavior_rules": {"enabled_ids": ["no_deception", "completeness_gate"]}
})
```

### Injecting Prompt Rules

```python
from metis.prompts.assembler import PromptAssembler, PromptParts

assembler = PromptAssembler()
parts = PromptParts(user_message="Hello")
stack = registry.inject_into_assembler(assembler, parts)
```

### Registering Hooks

```python
from metis.events.hooks import HookBus

hooks = HookBus()
registry.register_hooks(hooks)
```

### Accessing Gate Specs

```python
for gate_spec in registry.get_gate_specs():
    result = gate_spec.handler(context)
    if not result.passed:
        print(f"Gate {result.name} failed: {result.message}")
```

## Swarm Audit

When `swarm_audit_enabled` is true and a group runs in `COORDINATOR` mode,
the decomposition prompt automatically includes behavior-audit constraints:

- Every sub-task must include testing and verification
- No completion claims without concrete evidence
- Research sub-tasks when external knowledge is needed
- Full 11-phase decomposition coverage
- Autonomous execution without permission loops

## Extending with Custom Rules

You can define custom behavior rules by creating `BehaviorRule` instances and
passing them to `BehaviorRulesConfig`:

```python
from metis.behavior import BehaviorRule, BehaviorRulesConfig, BehaviorRulesRegistry

my_rule = BehaviorRule(
    id="custom_greeting",
    category="prompt",
    priority=10,
    enabled=True,
    prompt_text="[Behavior Rule: custom_greeting]\nAlways greet formally.",
)

config = BehaviorRulesConfig(rules=[my_rule])
registry = BehaviorRulesRegistry(config)
```

## Architecture

```
metis/behavior/
  __init__.py      — Public API exports
  rules.py         — BehaviorRule, BehaviorRulesConfig data models
  builtin.py       — 17 built-in rule definitions
  registry.py      — BehaviorRulesRegistry (load, inject, register)
  gates.py         — GateSpec factories for post-hoc auditing
  hooks.py         — HookBus handlers for runtime automation
```

## Testing

Run behavior-rules tests:

```bash
python -m pytest tests/unit/test_behavior_rules.py
python -m pytest tests/unit/test_behavior_gates.py
python -m pytest tests/unit/test_behavior_hooks.py
python -m pytest tests/unit/test_behavior_prompt.py
```
