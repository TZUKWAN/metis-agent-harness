"""Metis Swarm Hub — Web UI for multi-agent management and orchestration."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from metis.app.manifest import AgentAppManifest
from metis.app.runtime import run_agent_turn
from metis.events.hooks import HookBus
from metis.events.event_types import EventType
from metis.logging import get_logger
from metis.swarm.models import AgentStatus, OrchestrationMode
from metis.swarm.registry import AgentRegistry

logger = get_logger("swarm.hub")

HUB_DIR = Path(__file__).parent.parent / "app" / "web_assets_swarm"


def _extract_json_block(text: str) -> str | None:
    """Extract JSON object from text, handling markdown code blocks."""
    text = text.strip()
    # Try markdown code block
    if "```json" in text:
        start = text.find("```json") + len("```json")
        end = text.find("```", start)
        if end != -1:
            return text[start:end].strip()
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end != -1:
            return text[start:end].strip()
    # Try raw JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1].strip()
    return None


def _parse_coordinator_output(
    text: str,
    agents: list[Any],
) -> "TaskDecomposition":
    """Parse coordinator output into TaskDecomposition.

    Tries JSON first, falls back to legacy prefix matching.
    """
    from metis.swarm.schemas import TaskAssignment, TaskDecomposition

    task_decomp: TaskDecomposition | None = None

    json_str = _extract_json_block(text)
    if json_str:
        try:
            parsed = json.loads(json_str)
            task_decomp = TaskDecomposition(**parsed)
        except Exception:
            task_decomp = None

    if task_decomp is None:
        assignments: dict[str, str] = {}
        for line in text.splitlines():
            for a in agents:
                if line.strip().upper().startswith(f"{a.name.upper()}:"):
                    assignments[a.id] = line.split(":", 1)[1].strip()
                    break
        legacy_tasks: list[TaskAssignment] = []
        for a in agents:
            if a.id in assignments:
                legacy_tasks.append(TaskAssignment(
                    agent_id=a.id,
                    agent_name=a.name,
                    task=assignments[a.id],
                ))
        task_decomp = TaskDecomposition(tasks=legacy_tasks)

    return task_decomp


def create_hub_app() -> FastAPI:
    app = FastAPI(title="Metis Swarm Hub", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registry = AgentRegistry()
    app.state.registry = registry
    app.state.sessions: dict[str, dict[str, Any]] = {}

    # ---- Static / HTML ----
    app.mount("/static", StaticFiles(directory=HUB_DIR / "static"), name="swarm-static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((HUB_DIR / "templates" / "index.html").read_text(encoding="utf-8"))

    v1 = APIRouter()

    # ---- Agents ----

    @v1.get("/agents")
    async def list_agents(status: str | None = "active") -> dict[str, Any]:
        agent_status = AgentStatus(status) if status else None
        agents = registry.list_agents(status=agent_status)
        return {"agents": [a.to_dict() for a in agents]}

    @v1.get("/agents/{agent_id}")
    async def get_agent(agent_id: str) -> dict[str, Any]:
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="agent not found")
        manifest = registry.get_manifest(agent_id)
        manifest_dict = manifest.to_dict() if manifest else {}
        system_prompt = ""
        if manifest and manifest.system_prompt_path:
            try:
                prompt_file = Path(manifest.system_prompt_path)
                if prompt_file.exists():
                    system_prompt = prompt_file.read_text(encoding="utf-8")
            except Exception:
                pass
        return {
            "agent": agent.to_dict(),
            "manifest": manifest_dict,
            "system_prompt": system_prompt,
        }

    @v1.post("/agents/scan")
    async def scan_agents(request: Request) -> dict[str, Any]:
        raw = await request.json()
        root = raw.get("root", ".")
        found = registry.scan(root, recursive=True)
        return {"found": len(found), "agents": [a.to_dict() for a in found]}

    @v1.post("/agents")
    async def create_agent(request: Request) -> dict[str, Any]:
        raw = await request.json()
        name = str(raw.get("name", "")).strip()
        if not name:
            raise HTTPException(status_code=422, detail="name is required")
        path = raw.get("path", f"./metis-agents/{name.lower().replace(' ', '-')}")
        entry = registry.create_agent(
            name=name,
            path=path,
            model=str(raw.get("model", "")),
            api_key=str(raw.get("api_key", "")),
            base_url=str(raw.get("base_url", "")),
            description=str(raw.get("description", "")),
            icon=str(raw.get("icon", "🤖")),
            capabilities=raw.get("capabilities") or [],
        )
        return {"agent": entry.to_dict()}

    @v1.patch("/agents/{agent_id}")
    async def update_agent(agent_id: str, request: Request) -> dict[str, Any]:
        raw = await request.json()
        allowed = {"name", "model", "base_url", "api_key", "description", "profile", "icon_text", "system_prompt", "capabilities"}
        kwargs = {k: v for k, v in raw.items() if k in allowed}
        entry = registry.update_agent_manifest(agent_id, **kwargs)
        if not entry:
            raise HTTPException(status_code=404, detail="agent not found")
        return {"agent": entry.to_dict()}

    @v1.post("/agents/{agent_id}/trash")
    async def trash_agent(agent_id: str) -> dict[str, Any]:
        ok = registry.trash_agent(agent_id)
        if not ok:
            raise HTTPException(status_code=400, detail="cannot trash agent")
        return {"trashed": True}

    @v1.post("/agents/{agent_id}/restore")
    async def restore_agent(agent_id: str) -> dict[str, Any]:
        ok = registry.restore_agent(agent_id)
        if not ok:
            raise HTTPException(status_code=400, detail="cannot restore agent (already restored once or not in trash)")
        return {"restored": True}

    @v1.delete("/agents/{agent_id}/permanent")
    async def delete_permanently(agent_id: str) -> dict[str, Any]:
        ok = registry.permanently_delete(agent_id)
        if not ok:
            raise HTTPException(status_code=400, detail="cannot delete agent")
        return {"deleted": True}

    # ---- Groups ----

    @v1.get("/groups")
    async def list_groups() -> dict[str, Any]:
        groups = registry.list_groups()
        return {"groups": [g.to_dict() for g in groups]}

    @v1.post("/groups")
    async def create_group(request: Request) -> dict[str, Any]:
        raw = await request.json()
        name = str(raw.get("name", "")).strip()
        if not name:
            raise HTTPException(status_code=422, detail="name is required")
        agent_ids = raw.get("agent_ids", [])
        mode_str = raw.get("mode", "parallel")
        group = registry.create_group(
            name=name,
            agent_ids=agent_ids,
            mode=OrchestrationMode(mode_str),
            description=str(raw.get("description", "")),
        )
        return {"group": group.to_dict()}

    @v1.delete("/groups/{group_id}")
    async def delete_group(group_id: str) -> dict[str, Any]:
        ok = registry.delete_group(group_id)
        if not ok:
            raise HTTPException(status_code=404, detail="group not found")
        return {"deleted": True}

    # ---- Chat with single agent ----

    @v1.post("/agents/{agent_id}/chat")
    async def agent_chat(agent_id: str, request: Request) -> dict[str, Any]:
        raw = await request.json()
        message = str(raw.get("message", "")).strip()
        if not message:
            raise HTTPException(status_code=422, detail="message is required")

        manifest = registry.get_manifest(agent_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="agent manifest not found")

        try:
            result = await run_agent_turn(message, manifest=manifest, session_id=raw.get("session_id", uuid4().hex))
            return {
                "response": result.final_text,
                "status": result.status,
                "errors": result.errors,
                "usage": result.usage,
                "turns_used": result.turns_used,
            }
        except Exception as exc:
            logger.error("Agent chat failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    # ---- Group orchestration ----

    @v1.post("/groups/{group_id}/chat")
    async def group_chat(group_id: str, request: Request) -> dict[str, Any]:
        raw = await request.json()
        message = str(raw.get("message", "")).strip()
        if not message:
            raise HTTPException(status_code=422, detail="message is required")

        group = registry.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="group not found")

        agents = [registry.get_agent(aid) for aid in group.agent_ids]
        agents = [a for a in agents if a and a.status == AgentStatus.ACTIVE]
        if not agents:
            raise HTTPException(status_code=400, detail="group has no active agents")

        results: list[dict[str, Any]] = []

        if group.mode == OrchestrationMode.PARALLEL:
            # Run all agents in parallel, collect results
            async def run_one(agent_id: str, manifest: AgentAppManifest) -> dict[str, Any]:
                try:
                    result = await run_agent_turn(message, manifest=manifest, session_id=uuid4().hex)
                    return {
                        "agent_id": agent_id,
                        "agent_name": registry.get_agent(agent_id).name if registry.get_agent(agent_id) else agent_id,
                        "response": result.final_text,
                        "status": result.status,
                        "errors": result.errors,
                    }
                except Exception as exc:
                    return {"agent_id": agent_id, "error": str(exc)}

            tasks = [run_one(a.id, registry.get_manifest(a.id)) for a in agents]
            results = await asyncio.gather(*tasks)

        elif group.mode == OrchestrationMode.SERIAL:
            # Relay: pass output from one agent to the next
            current_message = message
            for agent in agents:
                manifest = registry.get_manifest(agent.id)
                if not manifest:
                    continue
                try:
                    result = await run_agent_turn(current_message, manifest=manifest, session_id=uuid4().hex)
                    results.append({
                        "agent_id": agent.id,
                        "agent_name": agent.name,
                        "response": result.final_text,
                        "status": result.status,
                        "errors": result.errors,
                    })
                    current_message = result.final_text or current_message
                except Exception as exc:
                    results.append({"agent_id": agent.id, "error": str(exc)})
                    break

        elif group.mode == OrchestrationMode.COORDINATOR:
            # Coordinator splits task, workers execute, coordinator synthesizes
            # Phase 1: first agent acts as coordinator to decompose task into JSON
            coordinator = agents[0]
            coord_manifest = registry.get_manifest(coordinator.id)
            if not coord_manifest:
                raise HTTPException(status_code=500, detail="coordinator manifest not found")

            worker_info = "\n".join(
                f"- {a.name} (id: {a.id}, capabilities: {a.capabilities})"
                for a in agents[1:]
            )

            behavior_audit_text = ""
            if coord_manifest.swarm_audit_enabled:
                behavior_audit_text = (
                    "\n\nBehavior Audit Rules (must be enforced across all sub-tasks):\n"
                    "- Each sub-task must include testing and verification as part of its scope\n"
                    "- No agent may claim completion without concrete evidence (files, tool outputs, command results)\n"
                    "- If external knowledge is needed, a research sub-task must be included\n"
                    "- Task decomposition must cover: understanding, research, design, implementation, testing, debug, audit, fix, optimization, delivery, review\n"
                    "- Do not ask the user for permission to continue; execute autonomously within safe boundaries"
                )

            decomposition_prompt = (
                f"You are the coordinator for a team of agents. The user's request is:\n\n{message}\n\n"
                f"Your team members are:\n{worker_info}\n\n"
                f"Please decompose this task into clear sub-tasks. "
                f"Respond ONLY with a JSON object matching this schema:\n\n"
                f"{{\n"
                f'  "tasks": [\n'
                f'    {{"agent_id": "<agent-id>", "agent_name": "<name>", "task": "<description>", "priority": <0-10>, "capabilities_needed": ["<capability>"]}},\n'
                f'    ...\n'
                f'  ],\n'
                f'  "dependencies": {{"<task_index>": [<prerequisite_task_indices>]}},\n'
                f'  "reasoning": "<why you decomposed this way>"\n'
                f"}}\n\n"
                f"Rules:\n"
                f"- tasks array indices are 0-based\n"
                f"- dependencies maps task index -> list of prerequisite task indices\n"
                f"- tasks with no dependencies can run in parallel\n"
                f"- agent_id must match one of the worker agent ids listed above\n"
                f"- If you are unsure which agent to assign, set agent_id to the best match"
                f"{behavior_audit_text}"
            )

            try:
                coord_result = await run_agent_turn(decomposition_prompt, manifest=coord_manifest, session_id=uuid4().hex)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"coordinator failed: {exc}")

            # Parse decomposition: try JSON first, fallback to legacy prefix matching
            from metis.swarm.context import SharedContext

            task_decomp = _parse_coordinator_output(coord_result.final_text or "", agents[1:])

            # Shared context for worker results
            shared_ctx = SharedContext()

            # Execute workers using topological sort (parallel within layers)
            worker_results: list[dict[str, Any]] = []
            if task_decomp.tasks:
                try:
                    exec_order = task_decomp.topological_sort()
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=f"invalid task dependencies: {exc}")

                # Group by dependency depth (layers)
                # Build in-degree map to determine layers
                n = len(task_decomp.tasks)
                in_degree: dict[int, int] = {i: 0 for i in range(n)}
                for task_idx_str, deps in task_decomp.dependencies.items():
                    task_idx = int(task_idx_str)
                    for dep in deps:
                        dep_idx = int(dep) if isinstance(dep, str) else dep
                        in_degree[task_idx] = in_degree.get(task_idx, 0) + 1

                # Determine layers: BFS level assignment
                layer: dict[int, int] = {}
                queue = [i for i in range(n) if in_degree[i] == 0]
                for i in queue:
                    layer[i] = 0
                adj: dict[int, list[int]] = {i: [] for i in range(n)}
                for task_idx_str, deps in task_decomp.dependencies.items():
                    task_idx = int(task_idx_str)
                    for dep in deps:
                        dep_idx = int(dep) if isinstance(dep, str) else dep
                        adj[dep_idx].append(task_idx)
                front = 0
                while front < len(queue):
                    node = queue[front]
                    front += 1
                    for neighbor in adj[node]:
                        new_deg = in_degree[neighbor] - 1
                        in_degree[neighbor] = new_deg
                        if new_deg == 0:
                            layer[neighbor] = layer[node] + 1
                            queue.append(neighbor)

                # Group task indices by layer
                layers: dict[int, list[int]] = {}
                for idx in exec_order:
                    l = layer.get(idx, 0)
                    layers.setdefault(l, []).append(idx)

                # Execute layer by layer
                for l in sorted(layers.keys()):
                    layer_indices = layers[l]
                    async def run_one_task(task_idx: int) -> dict[str, Any]:
                        task_assign = task_decomp.tasks[task_idx]
                        agent_id = task_assign.agent_id or ""
                        manifest = registry.get_manifest(agent_id)
                        agent = registry.get_agent(agent_id)
                        if not manifest or not agent:
                            return {
                                "agent_id": agent_id,
                                "error": f"agent not found or manifest missing",
                                "task": task_assign.task,
                            }
                        try:
                            result = await run_agent_turn(task_assign.task, manifest=manifest, session_id=uuid4().hex)
                            # Write to shared context
                            await shared_ctx.set(agent_id, {
                                "response": result.final_text,
                                "status": result.status,
                                "task": task_assign.task,
                            })
                            return {
                                "agent_id": agent_id,
                                "agent_name": agent.name,
                                "task": task_assign.task,
                                "response": result.final_text,
                                "status": result.status,
                            }
                        except Exception as exc:
                            return {"agent_id": agent_id, "error": str(exc), "task": task_assign.task}

                    layer_results = await asyncio.gather(*(run_one_task(idx) for idx in layer_indices))
                    worker_results.extend(layer_results)

            # Phase 2: coordinator synthesizes final result with shared context
            ctx_data = await shared_ctx.get_all()
            synthesis_input = (
                f"Original request: {message}\n\n"
                f"Worker results:\n"
                + "\n\n".join(
                    f"[{r.get('agent_name', r['agent_id'])}]: {r.get('response', r.get('error', ''))}"
                    for r in worker_results
                )
                + f"\n\nShared context:\n{json.dumps(ctx_data, ensure_ascii=False, indent=2)}"
                + "\n\nPlease synthesize these results into a single cohesive final response."
            )
            try:
                final_result = await run_agent_turn(synthesis_input, manifest=coord_manifest, session_id=uuid4().hex)
            except Exception as exc:
                final_result = None

            results = {
                "decomposition": task_decomp.model_dump() if task_decomp else {"tasks": []},
                "worker_results": worker_results,
                "final_response": final_result.final_text if final_result else None,
            }

        return {
            "group_id": group_id,
            "mode": group.mode.value,
            "message": message,
            "results": results,
        }

    # ---- WebSocket for single-agent streaming ----

    @v1.websocket("/agents/{agent_id}/stream")
    async def agent_stream(websocket: WebSocket, agent_id: str) -> None:
        await websocket.accept()
        manifest = registry.get_manifest(agent_id)
        if not manifest:
            await websocket.send_json({"type": "error", "error": "agent not found"})
            return

        try:
            while True:
                data = await websocket.receive_json()
                message = str(data.get("message", "")).strip()
                if not message:
                    continue

                session_id = str(data.get("session_id", "")).strip() or uuid4().hex

                hooks = HookBus()

                def _put(event: dict[str, Any]) -> None:
                    try:
                        asyncio.get_running_loop().call_soon_threadsafe(
                            lambda: asyncio.create_task(websocket.send_json(event))
                        )
                    except Exception:
                        pass

                hooks.register(EventType.AGENT_PRE_RUN, lambda d: None)
                hooks.register(EventType.MODEL_PRE_CALL, lambda d: None)
                hooks.register(EventType.MODEL_STREAM_CHUNK, lambda d: websocket.send_json({
                    "type": "token", "content": d.get("content", ""), "turn": d.get("turn", 0)
                }))
                hooks.register(EventType.TOOL_PRE_DISPATCH, lambda d: websocket.send_json({
                    "type": "tool_start", "name": d.get("tool", ""), "arguments": d.get("args", {})
                }))
                hooks.register(EventType.TOOL_POST_DISPATCH, lambda d: websocket.send_json({
                    "type": "tool_end", "name": d.get("tool", ""), "status": d.get("status", "ok")
                }))
                hooks.register("turn.complete", lambda d: websocket.send_json({
                    "type": "turn", "turn": d.get("turn", 0)
                }))

                result = await run_agent_turn(message, manifest=manifest, session_id=session_id, hooks=hooks)
                await websocket.send_json({
                    "type": "done",
                    "content": result.final_text,
                    "status": result.status,
                    "errors": result.errors,
                })
        except WebSocketDisconnect:
            return
        except Exception as exc:
            logger.debug("WebSocket error: %s", exc)

    app.include_router(v1, prefix="/api/v1")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "healthy", "agents": len(registry.list_agents()), "groups": len(registry.list_groups())}

    return app
