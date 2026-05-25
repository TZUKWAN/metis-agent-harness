"""In-memory swarm result bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SwarmMessage:
    agent_id: str
    payload: dict[str, Any]


class SwarmBus:
    def __init__(self) -> None:
        self.agents: set[str] = set()
        self.messages: list[SwarmMessage] = []

    def register_agent(self, agent_id: str) -> None:
        self.agents.add(agent_id)

    def publish(self, agent_id: str, payload: dict[str, Any]) -> None:
        if agent_id not in self.agents:
            raise KeyError(f"Unknown swarm agent: {agent_id}")
        self.messages.append(SwarmMessage(agent_id, payload))

    def collect(self, agent_id: str | None = None) -> list[SwarmMessage]:
        if agent_id is None:
            return list(self.messages)
        return [message for message in self.messages if message.agent_id == agent_id]
