"""Swarm orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from metis.events.hooks import HookBus
from metis.logging import get_logger
from metis.swarm.bus import SwarmBus
from metis.swarm.decomposer import AgentSpec, SwarmStage, TaskDecomposer

logger = get_logger("swarm")


@dataclass(frozen=True)
class SwarmExecutionRecord:
    task: str
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


class SwarmOrchestrator:
    def __init__(self, *, runner, decomposer: TaskDecomposer | None = None, hooks: HookBus | None = None) -> None:
        self.runner = runner
        self.decomposer = decomposer or TaskDecomposer()
        self.hooks = hooks or HookBus()
        self.bus = SwarmBus()

    async def run(self, task_text: str) -> SwarmExecutionRecord:
        results: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for stage in self.decomposer.decompose(task_text):
            await self.hooks.emit_async("swarm.stage_start", {"stage_id": stage.stage_id})
            if stage.parallel:
                stage_results = await asyncio.gather(
                    *(self._run_agent(agent, task_text) for agent in stage.agents),
                    return_exceptions=True,
                )
                for item in stage_results:
                    if isinstance(item, BaseException):
                        error_payload = {"error": str(item), "error_type": type(item).__name__}
                        errors.append(error_payload)
                        logger.warning("Agent failed in parallel stage: %s", item)
                    else:
                        results.append(item)
            else:
                for agent in stage.agents:
                    try:
                        result = await self._run_agent(agent, task_text)
                        results.append(result)
                    except Exception as exc:
                        error_payload = {"agent_id": agent.agent_id, "error": str(exc), "error_type": type(exc).__name__}
                        errors.append(error_payload)
                        logger.warning("Agent %s failed: %s", agent.agent_id, exc)
        return SwarmExecutionRecord(task_text, results, errors)

    async def _run_agent(self, agent: AgentSpec, task_text: str) -> dict[str, Any]:
        self.bus.register_agent(agent.agent_id)
        result = await self.runner.run_agent(agent=agent, task_text=task_text)
        payload = {"agent_id": agent.agent_id, "role_id": agent.role_id, "result": result}
        self.bus.publish(agent.agent_id, payload)
        await self.hooks.emit_async("swarm.agent_complete", payload)
        return payload
