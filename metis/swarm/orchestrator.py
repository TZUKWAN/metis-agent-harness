"""Swarm orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from metis.events.hooks import HookBus
from metis.swarm.bus import SwarmBus
from metis.swarm.decomposer import AgentSpec, SwarmStage, TaskDecomposer


@dataclass(frozen=True)
class SwarmExecutionRecord:
    task: str
    results: list[dict[str, Any]] = field(default_factory=list)


class SwarmOrchestrator:
    def __init__(self, *, runner, decomposer: TaskDecomposer | None = None, hooks: HookBus | None = None) -> None:
        self.runner = runner
        self.decomposer = decomposer or TaskDecomposer()
        self.hooks = hooks or HookBus()
        self.bus = SwarmBus()

    async def run(self, task_text: str) -> SwarmExecutionRecord:
        results: list[dict[str, Any]] = []
        for stage in self.decomposer.decompose(task_text):
            self.hooks.emit("swarm.stage_start", {"stage_id": stage.stage_id})
            if stage.parallel:
                stage_results = await asyncio.gather(*(self._run_agent(agent, task_text) for agent in stage.agents))
            else:
                stage_results = []
                for agent in stage.agents:
                    stage_results.append(await self._run_agent(agent, task_text))
            results.extend(stage_results)
        return SwarmExecutionRecord(task_text, results)

    async def _run_agent(self, agent: AgentSpec, task_text: str) -> dict[str, Any]:
        self.bus.register_agent(agent.agent_id)
        result = await self.runner.run_agent(agent=agent, task_text=task_text)
        payload = {"agent_id": agent.agent_id, "role_id": agent.role_id, "result": result}
        self.bus.publish(agent.agent_id, payload)
        self.hooks.emit("swarm.agent_complete", payload)
        return payload
