"""HookBus integration for trajectory recording."""

from __future__ import annotations

from metis.events.event_types import EventType
from metis.events.hooks import HookBus
from metis.telemetry.trajectory import TrajectoryRecorder


DEFAULT_TRAJECTORY_EVENTS = [
    EventType.AGENT_PRE_RUN,
    EventType.AGENT_POST_RUN,
    EventType.AGENT_ERROR,
    EventType.MODEL_PRE_CALL,
    EventType.MODEL_POST_CALL,
    EventType.TOOL_PRE_DISPATCH,
    EventType.TOOL_POST_DISPATCH,
    EventType.TOOL_ERROR,
    EventType.TOOL_RESULT_PERSISTED,
    EventType.TOOL_GUARDRAIL_BLOCK,
    EventType.QUALITY_PASSED,
    EventType.QUALITY_FAILED,
    "context.compressed",
    "recovery.retry",
    "swarm.stage_start",
    "swarm.agent_complete",
]


def install_trajectory_hooks(
    hooks: HookBus,
    recorder: TrajectoryRecorder,
    events: list[str] | None = None,
) -> TrajectoryRecorder:
    for event_type in events or DEFAULT_TRAJECTORY_EVENTS:
        hooks.register(event_type, recorder.hook(event_type))
    return recorder
