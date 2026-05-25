"""Canonical event names emitted by the Metis runtime."""


class EventType:
    """String constants for hook events."""

    AGENT_PRE_RUN = "agent.pre_run"
    AGENT_POST_RUN = "agent.post_run"
    AGENT_ERROR = "agent.error"

    MODEL_PRE_CALL = "model.pre_call"
    MODEL_POST_CALL = "model.post_call"
    MODEL_ERROR = "model.error"

    TOOL_PRE_DISPATCH = "tool.pre_dispatch"
    TOOL_POST_DISPATCH = "tool.post_dispatch"
    TOOL_ERROR = "tool.error"
    TOOL_RESULT_PERSISTED = "tool.result_persisted"
    TOOL_GUARDRAIL_WARN = "tool.guardrail_warn"
    TOOL_GUARDRAIL_BLOCK = "tool.guardrail_block"

    QUALITY_PASSED = "quality.passed"
    QUALITY_FAILED = "quality.failed"

    TRAJECTORY_RECORD = "trajectory.record"
