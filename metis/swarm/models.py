"""Data models for Metis Swarm."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    ACTIVE = "active"
    TRASHED = "trashed"
    DELETED = "deleted"


class OrchestrationMode(str, Enum):
    PARALLEL = "parallel"       # 并行讨论：所有 agent 同时处理，结果汇总
    SERIAL = "serial"           # 串行接力：A -> B -> C，前一个输出给后一个
    COORDINATOR = "coordinator" # 分工协作：coordinator 拆解任务，分发给 workers


@dataclass
class AgentEntry:
    id: str
    name: str
    path: str                     # metis-agent.json 所在目录绝对路径
    manifest_path: str
    status: AgentStatus = AgentStatus.ACTIVE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    trashed_at: str | None = None
    restored_once: bool = False   # 是否已恢复过一次
    description: str = ""
    icon: str = "🤖"
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "manifest_path": self.manifest_path,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "trashed_at": self.trashed_at,
            "restored_once": self.restored_once,
            "description": self.description,
            "icon": self.icon,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentEntry:
        return cls(
            id=data["id"],
            name=data["name"],
            path=data["path"],
            manifest_path=data["manifest_path"],
            status=AgentStatus(data.get("status", "active")),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            trashed_at=data.get("trashed_at"),
            restored_once=data.get("restored_once", False),
            description=data.get("description", ""),
            icon=data.get("icon", "🤖"),
            capabilities=data.get("capabilities", []),
        )


@dataclass
class AgentGroup:
    id: str
    name: str
    agent_ids: list[str] = field(default_factory=list)
    mode: OrchestrationMode = OrchestrationMode.PARALLEL
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "agent_ids": self.agent_ids,
            "mode": self.mode.value,
            "description": self.description,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentGroup:
        return cls(
            id=data["id"],
            name=data["name"],
            agent_ids=data.get("agent_ids", []),
            mode=OrchestrationMode(data.get("mode", "parallel")),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
        )


@dataclass
class SwarmRegistry:
    agents: dict[str, AgentEntry] = field(default_factory=dict)
    groups: dict[str, AgentGroup] = field(default_factory=dict)
    version: str = "1.0.0"
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "groups": {k: v.to_dict() for k, v in self.groups.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmRegistry:
        return cls(
            agents={k: AgentEntry.from_dict(v) for k, v in data.get("agents", {}).items()},
            groups={k: AgentGroup.from_dict(v) for k, v in data.get("groups", {}).items()},
            version=data.get("version", "1.0.0"),
            updated_at=data.get("updated_at", ""),
        )
