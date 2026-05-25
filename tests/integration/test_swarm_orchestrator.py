from dataclasses import dataclass

import pytest

from metis.swarm.decomposer import AgentSpec, SwarmStage
from metis.swarm.orchestrator import SwarmOrchestrator


class TwoStageDecomposer:
    def decompose(self, task_text: str):
        return [
            SwarmStage("explore", False, [AgentSpec("explorer-1", "explorer", "explore")]),
            SwarmStage("verify", False, [AgentSpec("verifier-1", "verifier", "verify")]),
        ]


class DummyRunner:
    async def run_agent(self, *, agent, task_text: str):
        return {"summary": f"{agent.role_id}:{task_text}"}


@pytest.mark.asyncio
async def test_swarm_orchestrator_runs_explorer_and_verifier():
    orchestrator = SwarmOrchestrator(runner=DummyRunner(), decomposer=TwoStageDecomposer())

    record = await orchestrator.run("inspect project")

    assert [item["role_id"] for item in record.results] == ["explorer", "verifier"]
    assert len(orchestrator.bus.collect()) == 2
