"""FastAPI Web UI for reusable Metis agents."""

from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from metis.app.manifest import AgentAppManifest, load_app_manifest
from metis.app.metrics import MetricsStore
from metis.app.runtime import build_runtime_status, run_agent_turn, state_store_for_manifest
from metis.app.schemas import ChatRequest
from metis.evidence.ledger import EvidenceLedger
from metis.logging import get_logger
from metis.runtime.response import AgentRunResult
from metis.security.injection import scan_message

logger = get_logger("web")


WEB_DIR = Path(__file__).parent / "web_assets"

_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_SESSION_STORE: dict[str, list[float]] = {}
RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_SESSION_MAX = 10
RATE_LIMIT_SESSION_WINDOW = 60

SESSION_TTL_SECONDS = 3600
MAX_IN_MEMORY_SESSIONS = 5000
MAX_RATE_LIMIT_ENTRIES = 10000
MAX_BODY_SIZE = int(os.getenv("METIS_MAX_BODY_SIZE", 1_048_576))  # 1MB default


def _cleanup_stale_sessions(sessions: dict[str, dict[str, Any]]) -> int:
    now = time.time()
    stale_keys = [
        sid for sid, data in sessions.items()
        if now - data.get("last_activity", 0) > SESSION_TTL_SECONDS
    ]
    for key in stale_keys:
        sessions.pop(key, None)
    # Evict oldest if still over limit
    if len(sessions) > MAX_IN_MEMORY_SESSIONS:
        sorted_by_activity = sorted(sessions.items(), key=lambda x: x[1].get("last_activity", 0))
        to_evict = sorted_by_activity[: len(sessions) - MAX_IN_MEMORY_SESSIONS]
        for sid, _ in to_evict:
            sessions.pop(sid, None)
        stale_keys.extend([sid for sid, _ in to_evict])
    return len(set(stale_keys))


def _prune_rate_limit_store() -> int:
    now = time.time()
    removed = 0
    for key in list(_RATE_LIMIT_STORE.keys()):
        timestamps = [t for t in _RATE_LIMIT_STORE[key] if now - t < RATE_LIMIT_WINDOW]
        if timestamps:
            _RATE_LIMIT_STORE[key] = timestamps
        else:
            _RATE_LIMIT_STORE.pop(key, None)
            removed += 1
    if len(_RATE_LIMIT_STORE) > MAX_RATE_LIMIT_ENTRIES:
        sorted_keys = sorted(_RATE_LIMIT_STORE.keys(), key=lambda k: min(_RATE_LIMIT_STORE[k]))
        for key in sorted_keys[: len(_RATE_LIMIT_STORE) - MAX_RATE_LIMIT_ENTRIES]:
            _RATE_LIMIT_STORE.pop(key, None)
            removed += 1
    return removed


def _prune_session_rate_limit_store() -> int:
    now = time.time()
    removed = 0
    for key in list(_RATE_LIMIT_SESSION_STORE.keys()):
        timestamps = [t for t in _RATE_LIMIT_SESSION_STORE[key] if now - t < RATE_LIMIT_SESSION_WINDOW]
        if timestamps:
            _RATE_LIMIT_SESSION_STORE[key] = timestamps
        else:
            _RATE_LIMIT_SESSION_STORE.pop(key, None)
            removed += 1
    if len(_RATE_LIMIT_SESSION_STORE) > MAX_RATE_LIMIT_ENTRIES:
        sorted_keys = sorted(_RATE_LIMIT_SESSION_STORE.keys(), key=lambda k: min(_RATE_LIMIT_SESSION_STORE[k]))
        for key in sorted_keys[: len(_RATE_LIMIT_SESSION_STORE) - MAX_RATE_LIMIT_ENTRIES]:
            _RATE_LIMIT_SESSION_STORE.pop(key, None)
            removed += 1
    return removed


def _check_rate_limit(client_ip: str) -> None:
    _prune_rate_limit_store()
    now = time.time()
    timestamps = _RATE_LIMIT_STORE.get(client_ip, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    timestamps.append(now)
    _RATE_LIMIT_STORE[client_ip] = timestamps
    if len(timestamps) > RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _check_session_rate_limit(session_id: str) -> None:
    _prune_session_rate_limit_store()
    now = time.time()
    timestamps = _RATE_LIMIT_SESSION_STORE.get(session_id, [])
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_SESSION_WINDOW]
    timestamps.append(now)
    _RATE_LIMIT_SESSION_STORE[session_id] = timestamps
    if len(timestamps) > RATE_LIMIT_SESSION_MAX:
        raise HTTPException(status_code=429, detail="Session rate limit exceeded")


async def _periodic_cleanup(app: FastAPI) -> None:
    """Background task to evict stale sessions and rate limit entries."""
    while True:
        await asyncio.sleep(300)
        try:
            cleaned_sessions = _cleanup_stale_sessions(app.state.sessions)
            cleaned_rate = _prune_rate_limit_store()
            cleaned_session_rate = _prune_session_rate_limit_store()
            total = cleaned_sessions + cleaned_rate + cleaned_session_rate
            if total > 0:
                logger.info("Background cleanup: %d sessions, %d rate, %d session_rate", cleaned_sessions, cleaned_rate, cleaned_session_rate)
        except Exception as exc:
            logger.warning("Background cleanup error: %s", exc)


def _check_api_key(request: Request) -> None:
    api_key = os.getenv("METIS_WEB_API_KEY", "")
    if not api_key:
        return
    provided = request.headers.get("X-API-Key", "") or request.query_params.get("api_key", "")
    if provided != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def create_app(manifest: AgentAppManifest | None = None) -> FastAPI:
    manifest = manifest or load_app_manifest()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup_task = asyncio.create_task(_periodic_cleanup(app))
        app.state.shutting_down = False
        logger.info("Metis web server starting: %s v%s", manifest.name, manifest.version)
        yield
        app.state.shutting_down = True
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        shutdown_timeout = int(os.getenv("METIS_SHUTDOWN_TIMEOUT", "30"))
        limiter = app.state.concurrency_limiter
        while limiter._value < app.state.max_concurrent and shutdown_timeout > 0:
            logger.info("Waiting for %d active requests to complete", app.state.max_concurrent - limiter._value)
            await asyncio.sleep(1)
            shutdown_timeout -= 1
        logger.info("Metis web server shutting down")

    app = FastAPI(title=manifest.name, version=manifest.version, lifespan=lifespan)
    app.state.manifest = manifest
    app.state.sessions = {}
    app.state.metrics = MetricsStore()
    max_concurrent = int(os.getenv("METIS_MAX_CONCURRENT", max((os.cpu_count() or 2) * 2, 4)))
    app.state.max_concurrent = max_concurrent
    app.state.concurrency_limiter = asyncio.Semaphore(max_concurrent)

    allowed_origins = [o.strip() for o in os.getenv("METIS_WEB_CORS_ORIGINS", "*").split(",") if o.strip()]
    env_name = os.getenv("METIS_ENV", "development").lower()
    if env_name == "production" and "*" in allowed_origins:
        logger.warning("CORS allows all origins (*) in production mode. Set METIS_WEB_CORS_ORIGINS explicitly.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def body_size_limit(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=413,
                content={"error": {"code": 413, "message": f"Payload too large (max {MAX_BODY_SIZE} bytes)"}},
            )
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.middleware("http")
    async def request_timeout(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/chat") or path.startswith("/api/chat") or path.startswith("/api/v1/chat/"):
            timeout_seconds = 600
        else:
            timeout_seconds = 30
        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning("Request timeout: %s %s after %ds", request.method, path, timeout_seconds)
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=504,
                content={"error": {"code": 504, "message": f"Gateway timeout after {timeout_seconds}s"}},
            )

    @app.middleware("http")
    async def auth_and_rate_limit(request: Request, call_next):
        _check_api_key(request)
        client_ip = request.client.host if request.client else "unknown"
        _check_rate_limit(client_ip)
        start = time.monotonic()
        request_id = request.headers.get("X-Request-ID", uuid4().hex[:16])
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled exception in %s %s [req=%s]", request.method, request.url.path, request_id)
            from starlette.responses import JSONResponse
            response = JSONResponse(
                status_code=500,
                content={"error": {"code": 500, "message": "Internal server error"}},
            )
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        if request.url.path.startswith("/api/"):
            logger.info("%s %s %d %s [req=%s]", request.method, request.url.path, response.status_code, f"{duration_ms}ms", request_id)
            app.state.metrics.record(request.url.path, request.method, response.status_code, duration_ms)
        return response

    @app.exception_handler(HTTPException)
    async def standard_error_handler(request: Request, exc: HTTPException):
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.status_code, "message": exc.detail}},
        )

    v1 = APIRouter()

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse((WEB_DIR / "templates" / "index.html").read_text(encoding="utf-8"))

    @v1.get("/config")
    async def config() -> dict[str, Any]:
        return manifest.to_dict()

    _start_time = time.time()

    @v1.get("/health")
    async def health() -> dict[str, Any]:
        checks: dict[str, Any] = {}
        overall = "healthy"

        # Provider connectivity
        try:
            from metis.app.runtime import build_runtime_status
            runtime = build_runtime_status(manifest)
            provider_status = runtime.get("provider_status", {})
            checks["provider"] = provider_status.get("status", "unknown")
            if checks["provider"] not in ("ok", "unknown"):
                overall = "degraded"
        except Exception as exc:
            checks["provider"] = f"error: {exc}"
            overall = "degraded"

        # State store connectivity
        try:
            state = state_store_for_manifest(manifest)
            if state is not None:
                checks["state_store"] = "ok"
            else:
                checks["state_store"] = "not_configured"
        except Exception as exc:
            checks["state_store"] = f"error: {exc}"
            overall = "degraded"

        # Disk space
        try:
            import shutil
            usage = shutil.disk_usage(".")
            free_gb = usage.free / (1024 ** 3)
            checks["disk"] = {"free_gb": round(free_gb, 2), "status": "ok" if free_gb > 1.0 else "critical"}
            if free_gb <= 1.0:
                overall = "unhealthy"
        except Exception as exc:
            checks["disk"] = f"error: {exc}"

        # Memory usage
        try:
            import psutil
            proc = psutil.Process()
            mem_info = proc.memory_info()
            rss_mb = round(mem_info.rss / (1024 * 1024), 1)
            mem_status = "ok" if rss_mb < 512 else ("warning" if rss_mb < 1024 else "critical")
            checks["memory"] = {"rss_mb": rss_mb, "status": mem_status}
            if mem_status == "critical":
                overall = "unhealthy"
            elif mem_status == "warning" and overall == "healthy":
                overall = "degraded"
        except ImportError:
            pass
        except Exception as exc:
            checks["memory"] = f"error: {exc}"

        # Sessions
        checks["sessions"] = {"count": len(app.state.sessions), "status": "ok"}

        return {
            "status": overall,
            "name": manifest.name,
            "version": manifest.version,
            "model": manifest.model,
            "environment": env_name,
            "uptime_seconds": round(time.time() - _start_time, 1),
            "checks": checks,
        }

    @v1.get("/status")
    async def status() -> dict[str, Any]:
        runtime = build_runtime_status(manifest)
        active = app.state.max_concurrent - getattr(app.state.concurrency_limiter, "_value", app.state.max_concurrent)
        runtime["concurrency"] = {
            "max": app.state.max_concurrent,
            "active": active,
            "available": app.state.max_concurrent - active,
        }
        return runtime

    @v1.get("/tools")
    async def tools_list() -> dict[str, Any]:
        try:
            from metis.tools.builtin import register_builtin_tools
            from metis.tools.document_tools import register_document_tools
            from metis.tools.workspace_tools import register_workspace_tools
            from metis.tools.web_tools import register_web_tools
            from metis.tools.registry import ToolRegistry
            registry = ToolRegistry()
            register_builtin_tools(registry, workspace=".")
            register_document_tools(registry, workspace=".")
            register_workspace_tools(registry, workspace=".")
            register_web_tools(registry)
            tools = []
            for name in registry.list_tools():
                spec = registry.get(name)
                if spec:
                    tools.append({
                        "name": spec.name,
                        "description": spec.description,
                        "category": spec.category,
                        "side_effect": spec.side_effect,
                    })
            return {"tools": tools}
        except Exception as exc:
            logger.warning("Failed to list tools: %s", exc)
            return {"tools": []}

    @v1.get("/sessions")
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

    @v1.get("/sessions/{session_id}")
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

    @v1.delete("/sessions/{session_id}")
    async def session_delete(session_id: str) -> dict[str, Any]:
        removed = app.state.sessions.pop(session_id, None)
        return {"deleted": session_id, "existed": removed is not None}

    @v1.get("/sessions/{session_id}/usage")
    async def session_usage(session_id: str) -> dict[str, Any]:
        session = app.state.sessions.get(session_id)
        if session is not None:
            return session.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "api_calls": 0})
        state = state_store_for_manifest(manifest)
        if state is not None:
            return state.get_token_usage(session_id)
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "api_calls": 0}

    @v1.get("/metrics")
    async def metrics() -> dict[str, Any]:
        return app.state.metrics.summary()

    @v1.get("/metrics/prometheus")
    async def metrics_prometheus() -> StreamingResponse:
        body = app.state.metrics.prometheus_format()
        return StreamingResponse(iter([body]), media_type="text/plain")

    @v1.post("/chat")
    async def chat(request: Request) -> dict[str, Any]:
        raw = await request.json()
        try:
            req = ChatRequest(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        message = req.message.strip()
        session_id = req.session_id.strip() or uuid4().hex
        request_id = request.headers.get("X-Request-ID", "")
        _check_session_rate_limit(session_id)
        scan = scan_message(message)
        if not scan.safe:
            logger.warning("Prompt injection detected: %s", scan.matched_patterns)
            raise HTTPException(status_code=400, detail="Potentially unsafe input detected")
        async with app.state.concurrency_limiter:
            result = await run_agent_turn(message, manifest=manifest, session_id=session_id, request_id=request_id)
        _record_session(app, session_id, message, result, manifest.model)
        return {
            "session_id": session_id,
            "response": result.final_text,
            "status": result.status,
            "errors": result.errors,
        }

    @v1.websocket("/chat/stream")
    async def chat_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                try:
                    req = ChatRequest(**data)
                except Exception:
                    await websocket.send_json({"type": "error", "error": "Invalid request: message required (1-50000 chars)"})
                    continue
                message = req.message.strip()
                session_id = req.session_id.strip() or uuid4().hex
                request_id = str(data.get("request_id", "")).strip()
                _check_session_rate_limit(session_id)
                scan = scan_message(message)
                if not scan.safe:
                    logger.warning("Prompt injection detected via WebSocket: %s", scan.matched_patterns)
                    await websocket.send_json({"type": "error", "error": "Potentially unsafe input detected"})
                    continue
                await websocket.send_json({"type": "tool_call", "name": "metis.agent_loop"})

                heartbeat_stop = asyncio.Event()

                async def heartbeat():
                    while not heartbeat_stop.is_set():
                        await asyncio.sleep(15)
                        if not heartbeat_stop.is_set():
                            try:
                                await websocket.send_json({"type": "ping"})
                            except Exception:
                                break

                hb_task = asyncio.create_task(heartbeat())
                try:
                    async with app.state.concurrency_limiter:
                        result = await run_agent_turn(message, manifest=manifest, session_id=session_id, request_id=request_id)
                finally:
                    heartbeat_stop.set()
                    hb_task.cancel()
                    try:
                        await hb_task
                    except asyncio.CancelledError:
                        pass

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

    @v1.post("/chat/sse")
    async def chat_sse(request: Request) -> StreamingResponse:
        raw = await request.json()
        try:
            req = ChatRequest(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        message = req.message.strip()
        session_id = req.session_id.strip() or uuid4().hex
        request_id = request.headers.get("X-Request-ID", "")
        _check_session_rate_limit(session_id)

        progress_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        def on_tool_analytics(data: dict[str, Any]) -> None:
            try:
                progress_queue.put_nowait({"type": "tool_call", "name": data.get("tool", ""), "status": data.get("status", ""), "duration_ms": data.get("duration_ms", 0)})
            except Exception:
                pass

        def on_turn_complete(data: dict[str, Any]) -> None:
            try:
                progress_queue.put_nowait({"type": "turn", "turn": data.get("turn", 0), "duration_ms": data.get("turn_duration_ms", 0)})
            except Exception:
                pass

        async def event_stream():
            yield _sse_event("start", {"session_id": session_id})

            async def run_turn():
                from metis.events.hooks import HookBus
                hooks = HookBus()
                hooks.register("tool.analytics", on_tool_analytics)
                hooks.register("turn.complete", on_turn_complete)
                async with app.state.concurrency_limiter:
                    result = await run_agent_turn(message, manifest=manifest, session_id=session_id, request_id=request_id)
                _record_session(app, session_id, message, result, manifest.model)
                return result

            task = asyncio.create_task(run_turn())
            while not task.done():
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=5)
                    if event is None:
                        break
                    yield _sse_event(event.pop("type", "progress"), event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

            try:
                result = task.result()
            except Exception as exc:
                logger.error("Agent turn failed in SSE: %s", exc)
                yield _sse_event("error", {"error": "Agent turn failed", "session_id": session_id})
                return
            for tool_result in result.tool_results:
                yield _sse_event("tool_result", {"name": tool_result.tool_name, "status": tool_result.status})
            if result.errors:
                yield _sse_event("errors", {"errors": result.errors})
            yield _sse_event("done", {
                "session_id": session_id,
                "content": result.final_text,
                "status": result.status,
                "turns_used": result.turns_used,
            })

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    app.include_router(v1, prefix="/api/v1")

    @app.get("/api/config")
    async def config_legacy() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/config")

    @app.get("/api/health")
    async def health_legacy() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/health")

    @app.get("/api/status")
    async def status_legacy() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/status")

    @app.get("/api/tools")
    async def tools_legacy() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/tools")

    @app.get("/api/sessions")
    async def sessions_legacy() -> RedirectResponse:
        return RedirectResponse(url="/api/v1/sessions")

    @app.get("/api/sessions/{session_id}")
    async def session_detail_legacy(session_id: str) -> RedirectResponse:
        return RedirectResponse(url=f"/api/v1/sessions/{session_id}")

    @app.delete("/api/sessions/{session_id}")
    async def session_delete_legacy(session_id: str) -> RedirectResponse:
        return RedirectResponse(url=f"/api/v1/sessions/{session_id}")

    @app.get("/api/sessions/{session_id}/usage")
    async def session_usage_legacy(session_id: str) -> RedirectResponse:
        return RedirectResponse(url=f"/api/v1/sessions/{session_id}/usage")

    @app.post("/api/chat")
    async def chat_legacy(request: Request) -> dict[str, Any]:
        raw = await request.json()
        try:
            req = ChatRequest(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        message = req.message.strip()
        session_id = req.session_id.strip() or uuid4().hex
        request_id = request.headers.get("X-Request-ID", "")
        _check_session_rate_limit(session_id)
        scan = scan_message(message)
        if not scan.safe:
            logger.warning("Prompt injection detected: %s", scan.matched_patterns)
            raise HTTPException(status_code=400, detail="Potentially unsafe input detected")
        async with app.state.concurrency_limiter:
            result = await run_agent_turn(message, manifest=manifest, session_id=session_id, request_id=request_id)
        _record_session(app, session_id, message, result, manifest.model)
        return {
            "session_id": session_id,
            "response": result.final_text,
            "status": result.status,
            "errors": result.errors,
        }

    @app.post("/api/chat/sse")
    async def chat_sse_legacy(request: Request) -> StreamingResponse:
        raw = await request.json()
        try:
            req = ChatRequest(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        message = req.message.strip()
        session_id = req.session_id.strip() or uuid4().hex
        request_id = request.headers.get("X-Request-ID", "")
        _check_session_rate_limit(session_id)
        progress_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        def on_tool_analytics_legacy(data: dict[str, Any]) -> None:
            try:
                progress_queue.put_nowait({"type": "tool_call", "name": data.get("tool", ""), "status": data.get("status", ""), "duration_ms": data.get("duration_ms", 0)})
            except Exception:
                pass

        def on_turn_complete_legacy(data: dict[str, Any]) -> None:
            try:
                progress_queue.put_nowait({"type": "turn", "turn": data.get("turn", 0), "duration_ms": data.get("turn_duration_ms", 0)})
            except Exception:
                pass

        async def event_stream_legacy():
            yield _sse_event("start", {"session_id": session_id})

            async def run_turn_legacy():
                from metis.events.hooks import HookBus
                hooks = HookBus()
                hooks.register("tool.analytics", on_tool_analytics_legacy)
                hooks.register("turn.complete", on_turn_complete_legacy)
                async with app.state.concurrency_limiter:
                    result = await run_agent_turn(message, manifest=manifest, session_id=session_id, request_id=request_id)
                _record_session(app, session_id, message, result, manifest.model)
                return result

            task = asyncio.create_task(run_turn_legacy())
            while not task.done():
                try:
                    event = await asyncio.wait_for(progress_queue.get(), timeout=5)
                    if event is None:
                        break
                    yield _sse_event(event.pop("type", "progress"), event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"

            try:
                result = task.result()
            except Exception as exc:
                logger.error("Agent turn failed in SSE (legacy): %s", exc)
                yield _sse_event("error", {"error": "Agent turn failed", "session_id": session_id})
                return
            for tool_result in result.tool_results:
                yield _sse_event("tool_result", {"name": tool_result.tool_name, "status": tool_result.status})
            if result.errors:
                yield _sse_event("errors", {"errors": result.errors})
            yield _sse_event("done", {
                "session_id": session_id,
                "content": result.final_text,
                "status": result.status,
                "turns_used": result.turns_used,
            })

        return StreamingResponse(event_stream_legacy(), media_type="text/event-stream")

    return app


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _record_session(app: FastAPI, session_id: str, user_message: str, result: AgentRunResult, model: str) -> None:
    session = app.state.sessions.setdefault(
        session_id,
        {"title": user_message[:50], "model": model, "messages": [], "tool_calls": [], "evidence": [], "trace_events": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "api_calls": 0}},
    )
    session["last_activity"] = time.time()
    session["messages"].append({"role": "user", "content": user_message})
    session["messages"].append({"role": "assistant", "content": result.final_text, "status": result.status, "errors": result.errors})
    session["tool_calls"].extend(_tool_results_to_session(result))
    session["evidence"].extend(_evidence_refs_from_tool_results(result))
    session["trace_events"].extend(result.trace_events)
    usage = result.usage
    if usage:
        session_usage_data = session["usage"]
        session_usage_data["prompt_tokens"] = session_usage_data.get("prompt_tokens", 0) + usage.get("prompt_tokens", 0)
        session_usage_data["completion_tokens"] = session_usage_data.get("completion_tokens", 0) + usage.get("completion_tokens", 0)
        session_usage_data["total_tokens"] = session_usage_data.get("total_tokens", 0) + usage.get("total_tokens", 0)
        session_usage_data["api_calls"] = session_usage_data.get("api_calls", 0) + 1
    if len(app.state.sessions) > 100:
        cleaned = _cleanup_stale_sessions(app.state.sessions)
        if cleaned:
            logger.info("Cleaned up %d stale sessions", cleaned)


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
