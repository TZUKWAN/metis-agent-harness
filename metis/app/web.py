"""FastAPI Web UI for reusable Metis agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from metis.app.manifest import AgentAppManifest, load_app_manifest
from metis.app.runtime import build_runtime_status, run_agent_turn, state_store_for_manifest
from metis.evidence.ledger import EvidenceLedger
from metis.runtime.response import AgentRunResult


WEB_DIR = Path(__file__).parent / "web_assets"


def create_app(manifest: AgentAppManifest | None = None) -> FastAPI:
    manifest = manifest or load_app_manifest()
    app = FastAPI(title=manifest.name, version=manifest.version)
    app.state.manifest = manifest
    app.state.sessions = {}
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8"))

    @app.get("/api/config")
    async def config() -> dict[str, Any]:
        return manifest.to_dict()

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return build_runtime_status(manifest)

    @app.get("/api/sessions")
    async def sessions() -> dict[str, Any]:
        items = [
            {
                "id": session_id,
                "title": data.get("title", "Untitled"),
                "model": data.get("model", manifest.model),
                "message_count": len(data.get("messages", [])),
                "tool_call_count": len(data.get("tool_calls", [])),
                "evidence_count": len(data.get("evidence", [])),
            }
            for session_id, data in app.state.sessions.items()
        ]
        seen = {item["id"] for item in items}
        state = state_store_for_manifest(manifest)
        if state is not None:
            for row in state.list_sessions():
                session_id = str(row["id"])
                if session_id in seen:
                    continue
                messages = state.list_messages(session_id)
                tool_calls = state.list_tool_calls(session_id)
                evidence = EvidenceLedger(state).list_evidence(session_id)
                items.append(
                    {
                        "id": session_id,
                        "title": _session_title(messages),
                        "model": manifest.model,
                        "message_count": len(messages),
                        "tool_call_count": len(tool_calls),
                        "evidence_count": len(evidence),
                    }
                )
        return {"sessions": items}

    @app.get("/api/sessions/{session_id}")
    async def session_detail(session_id: str) -> dict[str, Any]:
        session = app.state.sessions.get(session_id)
        if session is None:
            state = state_store_for_manifest(manifest)
            if state is not None:
                messages = state.list_messages(session_id)
                if messages:
                    evidence = EvidenceLedger(state).list_evidence(session_id)
                    return {
                        "id": session_id,
                        "title": _session_title(messages),
                        "model": manifest.model,
                        "messages": messages,
                        "tool_calls": state.list_tool_calls(session_id),
                        "evidence": [
                            {
                                "id": item.id,
                                "claim": item.claim,
                                "source_type": item.source_type,
                                "source_ref": item.source_ref,
                                "strength": item.strength,
                                "metadata": item.metadata,
                            }
                            for item in evidence
                        ],
                        "trace_events": [],
                    }
            raise HTTPException(status_code=404, detail="session not found")
        return {
            "id": session_id,
            "title": session.get("title", "Untitled"),
            "model": session.get("model", manifest.model),
            "messages": session.get("messages", []),
            "tool_calls": session.get("tool_calls", []),
            "evidence": session.get("evidence", []),
            "trace_events": session.get("trace_events", []),
        }

    @app.post("/api/chat")
    async def chat(request: Request) -> dict[str, Any]:
        body = await request.json()
        message = str(body.get("message", "")).strip()
        session_id = str(body.get("session_id", "")).strip() or uuid4().hex
        if not message:
            raise HTTPException(status_code=400, detail="message is required")
        result = await run_agent_turn(message, manifest=manifest, session_id=session_id)
        _record_session(app, session_id, message, result, manifest.model)
        return {
            "session_id": session_id,
            "response": result.final_text,
            "status": result.status,
            "errors": result.errors,
        }

    @app.websocket("/api/chat/stream")
    async def chat_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                message = str(data.get("message", "")).strip()
                session_id = str(data.get("session_id", "")).strip() or uuid4().hex
                if not message:
                    await websocket.send_json({"type": "error", "error": "message is required"})
                    continue
                await websocket.send_json({"type": "tool_call", "name": "metis.agent_loop"})
                result = await run_agent_turn(message, manifest=manifest, session_id=session_id)
                _record_session(app, session_id, message, result, manifest.model)
                if result.errors:
                    await websocket.send_json({"type": "tool_result", "name": "metis.agent_loop", "result": "; ".join(result.errors)})
                await websocket.send_json(
                    {
                        "type": "done",
                        "session_id": session_id,
                        "content": result.final_text,
                        "status": result.status,
                    }
                )
        except WebSocketDisconnect:
            return

    return app


def _record_session(app: FastAPI, session_id: str, user_message: str, result: AgentRunResult, model: str) -> None:
    session = app.state.sessions.setdefault(
        session_id,
        {"title": user_message[:50], "model": model, "messages": [], "tool_calls": [], "evidence": [], "trace_events": []},
    )
    session["messages"].append({"role": "user", "content": user_message})
    session["messages"].append({"role": "assistant", "content": result.final_text, "status": result.status, "errors": result.errors})
    session["tool_calls"].extend(_tool_results_to_session(result))
    session["evidence"].extend(_evidence_refs_from_tool_results(result))
    session["trace_events"].extend(result.trace_events)


def _tool_results_to_session(result: AgentRunResult) -> list[dict[str, Any]]:
    return [
        {
            "name": item.tool_name,
            "status": item.status,
            "error": item.error,
            "content": item.content,
            "metadata": item.metadata,
        }
        for item in result.tool_results
    ]


def _evidence_refs_from_tool_results(result: AgentRunResult) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in result.tool_results:
        refs = item.metadata.get("evidence_refs", [])
        if not isinstance(refs, list):
            continue
        for ref in refs:
            evidence.append({"id": str(ref), "source": item.tool_name, "status": item.status})
    return evidence


def _session_title(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "user" and str(message.get("content", "")).strip():
            return str(message["content"])[:50]
    return "Untitled"
