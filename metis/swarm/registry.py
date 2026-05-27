"""Agent registry with filesystem discovery, CRUD, and trash management."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from metis.app.manifest import AgentAppManifest, load_app_manifest, save_app_manifest
from metis.swarm.models import AgentEntry, AgentGroup, AgentStatus, OrchestrationMode, SwarmRegistry


METIS_DIR = Path.home() / ".metis"
SWARM_DIR = METIS_DIR / "swarm"
REGISTRY_PATH = SWARM_DIR / "registry.json"
TRASH_DIR = SWARM_DIR / "trash"

TRASH_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _ensure_dirs() -> None:
    SWARM_DIR.mkdir(parents=True, exist_ok=True)
    TRASH_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> SwarmRegistry:
    _ensure_dirs()
    if REGISTRY_PATH.exists():
        try:
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
            return SwarmRegistry.from_dict(data)
        except Exception:
            pass
    return SwarmRegistry()


def _save_registry(registry: SwarmRegistry) -> None:
    _ensure_dirs()
    registry.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    REGISTRY_PATH.write_text(json.dumps(registry.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _manifest_from_path(path: str | Path) -> AgentAppManifest | None:
    try:
        manifest_path = Path(path) / "metis-agent.json"
        if manifest_path.exists():
            return load_app_manifest(str(manifest_path))
    except Exception:
        pass
    return None


class AgentRegistry:
    """Filesystem-backed agent registry with trash/recycle."""

    def __init__(self) -> None:
        self._registry = _load_registry()
        self._cleanup_trash()

    # ---- Discovery ----

    def scan(self, root: str | Path = ".", *, recursive: bool = True) -> list[AgentEntry]:
        """Scan directory for metis-agent.json files and register new agents."""
        root = Path(root).resolve()
        found: list[AgentEntry] = []
        pattern = "**/metis-agent.json" if recursive else "metis-agent.json"
        for manifest_path in root.glob(pattern):
            agent_dir = manifest_path.parent
            existing = self._find_by_path(str(agent_dir))
            if existing:
                # Update metadata from manifest
                manifest = _manifest_from_path(agent_dir)
                if manifest:
                    existing.name = manifest.name
                    existing.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
                    found.append(existing)
                continue
            manifest = _manifest_from_path(agent_dir)
            if manifest:
                entry = AgentEntry(
                    id=uuid.uuid4().hex[:12],
                    name=manifest.name,
                    path=str(agent_dir),
                    manifest_path=str(manifest_path),
                    description=manifest.description,
                )
                self._registry.agents[entry.id] = entry
                found.append(entry)
        _save_registry(self._registry)
        return found

    def _find_by_path(self, path: str) -> AgentEntry | None:
        for entry in self._registry.agents.values():
            if entry.path == path and entry.status == AgentStatus.ACTIVE:
                return entry
        return None

    # ---- Read ----

    def list_agents(self, status: AgentStatus | None = AgentStatus.ACTIVE) -> list[AgentEntry]:
        if status is None:
            return list(self._registry.agents.values())
        return [a for a in self._registry.agents.values() if a.status == status]

    def get_agent(self, agent_id: str) -> AgentEntry | None:
        return self._registry.agents.get(agent_id)

    def get_manifest(self, agent_id: str) -> AgentAppManifest | None:
        entry = self.get_agent(agent_id)
        if entry:
            return _manifest_from_path(entry.path)
        return None

    # ---- Create ----

    def create_agent(self, name: str, path: str | Path, *, model: str = "", api_key: str = "", base_url: str = "", description: str = "", icon: str = "🤖", capabilities: list[str] | None = None) -> AgentEntry:
        """Create a new agent by writing a metis-agent.json."""
        agent_dir = Path(path).resolve()
        agent_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = agent_dir / "metis-agent.json"

        manifest_data: dict[str, Any] = {
            "name": name,
            "description": description or f"Agent {name}",
            "version": "0.1.0",
            "workspace": ".",
            "model": model or "gpt-4o",
            "profile": "small",
            "icon_text": icon,
        }
        if api_key:
            manifest_data["providers"] = [{
                "name": model or "gpt-4o",
                "model": model or "gpt-4o",
                "provider_type": "openai_compat",
                "priority": 0,
                "api_key": api_key,
            }]
        if base_url:
            manifest_data["base_url"] = base_url

        manifest = AgentAppManifest(**manifest_data)
        save_app_manifest(manifest, str(manifest_path))

        entry = AgentEntry(
            id=uuid.uuid4().hex[:12],
            name=name,
            path=str(agent_dir),
            manifest_path=str(manifest_path),
            description=description,
            icon=icon,
            capabilities=capabilities or [],
        )
        self._registry.agents[entry.id] = entry
        _save_registry(self._registry)
        return entry

    # ---- Update ----

    def update_agent_manifest(self, agent_id: str, **kwargs: Any) -> AgentEntry | None:
        """Update agent manifest fields (name, model, base_url, description, etc.)."""
        entry = self.get_agent(agent_id)
        if not entry:
            return None
        manifest = self.get_manifest(agent_id)
        if not manifest:
            return None

        data = manifest.to_dict()
        for key, value in kwargs.items():
            if key in data and value is not None:
                data[key] = value

        # Handle api_key update in providers
        if "api_key" in kwargs:
            api_key = kwargs["api_key"]
            model = data.get("model", "")
            providers = [p for p in data.get("providers", []) if isinstance(p, dict)]
            providers = [p for p in providers if p.get("model") != model]
            if api_key:
                providers.insert(0, {
                    "name": model,
                    "model": model,
                    "provider_type": "openai_compat",
                    "priority": 0,
                    "api_key": api_key,
                })
            data["providers"] = providers

        # Handle system_prompt: write to file and update path
        if "system_prompt" in kwargs:
            system_prompt = kwargs["system_prompt"]
            if system_prompt:
                prompt_path = Path(entry.path) / "system_prompt.md"
                prompt_path.write_text(system_prompt, encoding="utf-8")
                data["system_prompt_path"] = str(prompt_path)
            elif "system_prompt_path" in data:
                data["system_prompt_path"] = ""

        new_manifest = AgentAppManifest(**data)
        save_app_manifest(new_manifest, entry.manifest_path)

        # Update registry entry
        entry.name = data.get("name", entry.name)
        entry.description = data.get("description", entry.description)
        if "capabilities" in kwargs:
            entry.capabilities = kwargs["capabilities"] or []
        entry.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save_registry(self._registry)
        return entry

    # ---- Delete / Trash ----

    def trash_agent(self, agent_id: str) -> bool:
        """Soft-delete agent to trash. Returns True if successful."""
        entry = self.get_agent(agent_id)
        if not entry or entry.status != AgentStatus.ACTIVE:
            return False

        # Move directory to trash
        src = Path(entry.path)
        trash_name = f"{entry.id}_{int(time.time())}"
        dst = TRASH_DIR / trash_name
        try:
            if src.exists():
                shutil.move(str(src), str(dst))
        except Exception:
            return False

        entry.status = AgentStatus.TRASHED
        entry.trashed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        entry.path = str(dst)
        entry.manifest_path = str(dst / "metis-agent.json")
        _save_registry(self._registry)
        return True

    def restore_agent(self, agent_id: str) -> bool:
        """Restore agent from trash. Can only be restored once."""
        entry = self.get_agent(agent_id)
        if not entry or entry.status != AgentStatus.TRASHED:
            return False
        if entry.restored_once:
            return False

        # Move directory back to original location
        trashed_path = Path(entry.path)
        # Original path was stored without the trash prefix
        original_name = trashed_path.name.split("_", 1)[1] if "_" in trashed_path.name else trashed_path.name
        # We can't know exact original parent; put in a default workspace
        workspace = Path.cwd() / "metis-agents"
        workspace.mkdir(parents=True, exist_ok=True)
        dst = workspace / original_name
        # Avoid collision
        counter = 1
        while dst.exists():
            dst = workspace / f"{original_name}_{counter}"
            counter += 1

        try:
            if trashed_path.exists():
                shutil.move(str(trashed_path), str(dst))
        except Exception:
            return False

        entry.status = AgentStatus.ACTIVE
        entry.trashed_at = None
        entry.restored_once = True
        entry.path = str(dst)
        entry.manifest_path = str(dst / "metis-agent.json")
        _save_registry(self._registry)
        return True

    def permanently_delete(self, agent_id: str) -> bool:
        """Permanently delete agent from trash."""
        entry = self.get_agent(agent_id)
        if not entry or entry.status != AgentStatus.TRASHED:
            return False

        path = Path(entry.path)
        try:
            if path.exists():
                shutil.rmtree(path)
        except Exception:
            pass

        entry.status = AgentStatus.DELETED
        _save_registry(self._registry)
        return True

    def _cleanup_trash(self) -> None:
        """Auto-delete agents that have been in trash for > 7 days."""
        now = time.time()
        to_delete: list[str] = []
        for agent_id, entry in self._registry.agents.items():
            if entry.status == AgentStatus.TRASHED and entry.trashed_at:
                try:
                    trashed_time = time.mktime(time.strptime(entry.trashed_at, "%Y-%m-%dT%H:%M:%S"))
                    if now - trashed_time > TRASH_TTL_SECONDS:
                        to_delete.append(agent_id)
                except Exception:
                    pass
        for agent_id in to_delete:
            self.permanently_delete(agent_id)

    # ---- Groups ----

    def list_groups(self) -> list[AgentGroup]:
        return list(self._registry.groups.values())

    def get_group(self, group_id: str) -> AgentGroup | None:
        return self._registry.groups.get(group_id)

    def create_group(self, name: str, agent_ids: list[str], *, mode: OrchestrationMode = OrchestrationMode.PARALLEL, description: str = "") -> AgentGroup:
        group = AgentGroup(
            id=uuid.uuid4().hex[:12],
            name=name,
            agent_ids=agent_ids,
            mode=mode,
            description=description,
        )
        self._registry.groups[group.id] = group
        _save_registry(self._registry)
        return group

    def update_group(self, group_id: str, **kwargs: Any) -> AgentGroup | None:
        group = self.get_group(group_id)
        if not group:
            return None
        for key, value in kwargs.items():
            if hasattr(group, key) and value is not None:
                setattr(group, key, value)
        _save_registry(self._registry)
        return group

    def delete_group(self, group_id: str) -> bool:
        if group_id in self._registry.groups:
            del self._registry.groups[group_id]
            _save_registry(self._registry)
            return True
        return False

    # ---- Registry raw access ----

    def to_dict(self) -> dict[str, Any]:
        return self._registry.to_dict()
