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

from metis.app.hitl_api import router as hitl_router, set_hitl_store
from metis.app.manifest import AgentAppManifest, load_app_manifest, save_app_manifest
from metis.app.metrics import MetricsStore
from metis.app.runtime import build_runtime_status, run_agent_turn, state_store_for_manifest
from metis.app.schemas import ChatRequest
from metis.evidence.ledger import EvidenceLedger
from metis.hitl.store import ApprovalStore
from metis.logging import get_logger
from metis.runtime.response import AgentRunResult
from metis.security.injection import scan_message
from metis.tools.registry import ToolRegistry
from metis.tools.builtin import register_builtin_tools

logger = get_logger("web")


WEB_DIR = Path(__file__).parent / "web_assets"

_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_SESSION_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK = asyncio.Lock()
_RATE_LIMIT_SESSION_LOCK = asyncio.Lock()
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


async def _check_rate_limit(client_ip: str) -> None:
    async with _RATE_LIMIT_LOCK:
        _prune_rate_limit_store()
        now = time.time()
        timestamps = _RATE_LIMIT_STORE.get(client_ip, [])
        timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        timestamps.append(now)
        _RATE_LIMIT_STORE[client_ip] = timestamps
        if len(timestamps) > RATE_LIMIT_MAX:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")


async def _check_session_rate_limit(session_id: str) -> None:
    async with _RATE_LIMIT_SESSION_LOCK:
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

    async def _watch_manifest(app: FastAPI) -> None:
        """Background task to watch metis-agent.json for changes and hot-reload."""
        manifest_path = Path(os.getenv("METIS_APP_MANIFEST", "metis-agent.json"))
        if not manifest_path.exists():
            return
        last_mtime = manifest_path.stat().st_mtime
        while not getattr(app.state, "shutting_down", False):
            await asyncio.sleep(5)
            try:
                if not manifest_path.exists():
                    continue
                current_mtime = manifest_path.stat().st_mtime
                if current_mtime != last_mtime:
                    last_mtime = current_mtime
                    logger.info("Manifest file changed, hot-reloading...")
                    try:
                        new_manifest = load_app_manifest(manifest_path)
                        app.state.manifest = new_manifest
                        if hasattr(app.state, "provider") and hasattr(app.state.provider, "close"):
                            try:
                                await app.state.provider.close()
                            except Exception as exc:
                                logger.warning("Error closing old provider during hot-reload: %s", exc)
                        app.state.provider = _build_provider_for_manifest(new_manifest)
                        logger.info("Manifest hot-reload complete: model=%s profile=%s", new_manifest.model, new_manifest.profile)
                    except Exception as exc:
                        logger.warning("Manifest hot-reload failed: %s", exc)
            except Exception as exc:
                logger.debug("Manifest watch error: %s", exc)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from metis.app.runtime import _build_provider_for_manifest

        app.state.provider = _build_provider_for_manifest(manifest)
        # Initialize shared HITL store for web-mode approvals
        app.state.hitl_store = ApprovalStore()
        set_hitl_store(app.state.hitl_store)
        cleanup_task = asyncio.create_task(_periodic_cleanup(app))
        manifest_watch_task = asyncio.create_task(_watch_manifest(app))
        app.state.shutting_down = False
        logger.info("Metis web server starting: %s v%s", manifest.name, manifest.version)
        yield
        app.state.shutting_down = True
        cleanup_task.cancel()
        manifest_watch_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        try:
            await manifest_watch_task
        except asyncio.CancelledError:
            pass
        shutdown_timeout = int(os.getenv("METIS_SHUTDOWN_TIMEOUT", "30"))
        limiter = app.state.concurrency_limiter
        while limiter._value < app.state.max_concurrent and shutdown_timeout > 0:
            logger.info("Waiting for %d active requests to complete", app.state.max_concurrent - limiter._value)
            await asyncio.sleep(1)
            shutdown_timeout -= 1
        if hasattr(app.state.provider, "close"):
            try:
                await app.state.provider.close()
            except Exception as exc:
                logger.warning("Provider close error during shutdown: %s", exc)
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
        await _check_rate_limit(client_ip)
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
        current = getattr(app.state, "manifest", manifest)
        cfg = current.to_dict()
        # Determine if setup is needed by checking provider health
        try:
            provider = app.state.provider
            ph = await provider.health_check()
            cfg["needs_setup"] = ph.get("status") in ("error", "unreachable", "not_initialized")
        except Exception:
            cfg["needs_setup"] = True
        return cfg

    @v1.post("/setup")
    async def setup(request: Request) -> dict[str, Any]:
        raw = await request.json()
        current = getattr(app.state, "manifest", manifest)
        model = str(raw.get("model", current.model)).strip()
        base_url = str(raw.get("base_url", current.base_url or "")).strip()
        api_key = str(raw.get("api_key", "")).strip()
        preserve_key = raw.get("preserve_key", False)
        profile = str(raw.get("profile", current.profile)).strip()
        hitl_enabled = raw.get("hitl_enabled")

        if not model:
            raise HTTPException(status_code=422, detail="model is required")

        # Build new manifest with provider config
        new_data = current.to_dict()
        new_data["model"] = model
        if base_url:
            new_data["base_url"] = base_url
        if profile:
            new_data["profile"] = profile
        if hitl_enabled is not None:
            new_data["hitl_enabled"] = bool(hitl_enabled)

        # Extract existing api_key for this model if preserving
        old_api_key = ""
        for p in new_data.get("providers", []):
            if isinstance(p, dict) and p.get("api_key"):
                old_api_key = str(p["api_key"])
                break

        # Store api_key in providers list for persistence
        providers = list(new_data.get("providers", []))
        # Remove existing provider entries for this model to avoid duplicates
        providers = [p for p in providers if p.get("model") != model]
        provider_cfg: dict[str, Any] = {
            "name": model,
            "model": model,
            "provider_type": "openai_compat",
            "priority": 0,
        }
        if base_url:
            provider_cfg["base_url"] = base_url
        if api_key:
            provider_cfg["api_key"] = api_key
        elif preserve_key and old_api_key:
            provider_cfg["api_key"] = old_api_key
        providers.insert(0, provider_cfg)
        new_data["providers"] = providers

        new_manifest = AgentAppManifest(**new_data)
        save_app_manifest(new_manifest)

        # Hot-reload: update app.state.manifest and rebuild provider
        app.state.manifest = new_manifest
        try:
            if hasattr(app.state, "provider") and hasattr(app.state.provider, "close"):
                await app.state.provider.close()
        except Exception as exc:
            logger.warning("Error closing old provider during setup: %s", exc)
        try:
            from metis.app.runtime import _build_provider_for_manifest
            app.state.provider = _build_provider_for_manifest(new_manifest)
        except Exception as exc:
            logger.error("Failed to rebuild provider after setup: %s", exc)
            raise HTTPException(status_code=500, detail=f"Failed to initialize provider: {exc}")

        return {"ok": True, "model": model, "profile": new_manifest.profile, "needs_setup": False}

    _start_time = time.time()

    @v1.get("/health")
    async def health() -> dict[str, Any]:
        checks: dict[str, Any] = {}
        overall = "healthy"

        # Provider connectivity
        try:
            provider = app.state.provider
            provider_health = await provider.health_check()
            checks["provider"] = provider_health.get("status", "unknown")
            # Only mark degraded if provider returns a non-ok status that isn't a simple connection error
            # (connection errors are expected in isolated test/dev environments)
            if checks["provider"] == "error":
                checks["provider"] = "unreachable"
            elif checks["provider"] not in ("ok", "unknown", "unreachable"):
                overall = "degraded"
        except AttributeError:
            checks["provider"] = "not_initialized"
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
        from metis.app.runtime import manifest_allowed_tool_permissions, _state_db_path, build_runtime_status

        if hasattr(app.state, "provider"):
            provider = app.state.provider
            caps = provider.capabilities().to_dict()
            registry = ToolRegistry()
            register_builtin_tools(registry, workspace=manifest.workspace)
            result: dict[str, Any] = {
                "manifest": manifest.to_dict(),
                "workspace": manifest.workspace,
                "profile": manifest.profile,
                "provider_capabilities": caps,
                "allowed_tool_permissions": manifest_allowed_tool_permissions(manifest),
                "tools": registry.list_tools(),
                "state_db_path": str(_state_db_path(manifest, workspace=manifest.workspace)) if manifest.state_db_path else "",
            }
            router_stats = getattr(provider, "get_stats", None)
            if router_stats is not None:
                result["routing_stats"] = router_stats()
        else:
            # Fallback for tests or contexts without lifespan
            result = build_runtime_status(manifest)

        active = app.state.max_concurrent - getattr(app.state.concurrency_limiter, "_value", app.state.max_concurrent)
        result["concurrency"] = {
            "max": app.state.max_concurrent,
            "active": active,
            "available": app.state.max_concurrent - active,
        }
        return result

    @v1.get("/tools")
    async def tools_list() -> dict[str, Any]:
        try:
            from metis.app.runtime import build_agent_loop_with_mcp
            loop = await build_agent_loop_with_mcp(manifest)
            tools = []
            for name in loop.registry.list_tools():
                spec = loop.registry.get(name)
                if spec:
                    tools.append({
                        "name": spec.name,
                        "description": spec.description,
                        "category": spec.category,
                        "side_effect": spec.side_effect,
                    })
            # Clean up provider and MCP clients to avoid resource leaks
            if hasattr(loop.provider, "close"):
                try:
                    await loop.provider.close()
                except Exception:
                    pass
            if hasattr(loop, "_mcp_clients"):
                for client in loop._mcp_clients:
                    try:
                        await client.close()
                    except Exception:
                        pass
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
        state = state_store_for_manifest(manifest)
        if state is not None:
            try:
                state.delete_session(session_id)
            except Exception as exc:
                logger.warning("Failed to delete session from state store: %s", exc)
        return {"deleted": session_id, "existed": removed is not None or state is not None}

    @v1.get("/sessions/{session_id}/trace")
    async def session_trace(session_id: str) -> HTMLResponse:
        session = app.state.sessions.get(session_id)
        if session is None:
            state = state_store_for_manifest(manifest)
            if state is not None:
                messages = state.list_messages(session_id)
                if messages:
                    trace_events = []
                    return HTMLResponse(render_trace_timeline(trace_events, session_id))
            raise HTTPException(status_code=404, detail="session not found")
        from metis.viz.trace_renderer import render_trace_timeline
        trace_events = session.get("trace_events", [])
        html_content = render_trace_timeline(trace_events, session_id)
        return HTMLResponse(html_content)

    @v1.get("/sessions/{session_id}/report")
    async def session_report(session_id: str) -> HTMLResponse:
        session = app.state.sessions.get(session_id)
        if session is None:
            state = state_store_for_manifest(manifest)
            if state is not None:
                messages = state.list_messages(session_id)
                if messages:
                    tool_calls = state.list_tool_calls(session_id)
                    from metis.runtime.response import AgentRunResult, ToolResult
                    from metis.viz.report import generate_html_report
                    tool_results = [
                        ToolResult(
                            tool_name=tc.get("tool_name", ""),
                            content=tc.get("result", ""),
                            status=tc.get("status", "ok"),
                            tool_call_id=tc.get("call_id", ""),
                            error=tc.get("error"),
                            metadata=tc.get("metadata", {}),
                        )
                        for tc in tool_calls
                    ]
                    errors: list[str] = []
                    for m in messages:
                        if m.get("role") == "assistant" and m.get("errors"):
                            errors.extend(m.get("errors", []))
                    result = AgentRunResult(
                        status=messages[-1].get("status", "unknown") if messages else "unknown",
                        final_text=messages[-1].get("content", "") if messages else "",
                        turns_used=len([m for m in messages if m.get("role") == "assistant"]),
                        tool_results=tool_results,
                        trace_events=[],
                        errors=errors,
                        usage=state.get_token_usage(session_id),
                    )
                    html_content = generate_html_report(result, session_id, title=f"Session {session_id[:8]}")
                    return HTMLResponse(html_content)
            raise HTTPException(status_code=404, detail="session not found")
        from metis.runtime.response import AgentRunResult, ToolResult
        from metis.viz.report import generate_html_report
        tool_results = [
            ToolResult(
                tool_name=tc.get("name", ""),
                content=tc.get("content", ""),
                status=tc.get("status", "ok"),
                tool_call_id=tc.get("tool_call_id", ""),
                error=tc.get("error"),
                metadata=tc.get("metadata", {}),
            )
            for tc in session.get("tool_calls", [])
        ]
        errors = []
        for m in session.get("messages", []):
            if m.get("role") == "assistant" and m.get("errors"):
                errors.extend(m.get("errors", []))
        result = AgentRunResult(
            status=session.get("messages", [{}])[-1].get("status", "unknown") if session.get("messages") else "unknown",
            final_text=session.get("messages", [{}])[-1].get("content", "") if session.get("messages") else "",
            turns_used=len([m for m in session.get("messages", []) if m.get("role") == "assistant"]),
            tool_results=tool_results,
            trace_events=session.get("trace_events", []),
            errors=errors,
            usage=session.get("usage", {}),
        )
        html_content = generate_html_report(result, session_id, title=f"Session {session_id[:8]}")
        return HTMLResponse(html_content)

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

    async def _handle_chat(raw: dict[str, Any], request_id: str = "") -> dict[str, Any]:
        try:
            req = ChatRequest(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        message = req.message.strip()
        session_id = req.session_id.strip() or uuid4().hex
        await _check_session_rate_limit(session_id)
        scan = scan_message(message)
        if not scan.safe:
            logger.warning("Prompt injection detected: %s", scan.matched_patterns)
            raise HTTPException(status_code=400, detail="Potentially unsafe input detected")
        async with app.state.concurrency_limiter:
            result = await run_agent_turn(
                message, manifest=manifest, session_id=session_id, request_id=request_id,
                hitl_store=getattr(app.state, "hitl_store", None),
            )
        _record_session(app, session_id, message, result, manifest.model)
        return {
            "session_id": session_id,
            "response": result.final_text,
            "status": result.status,
            "errors": result.errors,
        }

    @v1.post("/chat")
    async def chat(request: Request) -> dict[str, Any]:
        raw = await request.json()
        request_id = request.headers.get("X-Request-ID", "")
        return await _handle_chat(raw, request_id=request_id)

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
                await _check_session_rate_limit(session_id)
                scan = scan_message(message)
                if not scan.safe:
                    logger.warning("Prompt injection detected via WebSocket: %s", scan.matched_patterns)
                    await websocket.send_json({"type": "error", "error": "Potentially unsafe input detected"})
                    continue

                progress_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
                from metis.events.hooks import HookBus
                from metis.events.event_types import EventType
                ws_hooks = HookBus()

                def _put_event(event: dict[str, Any]) -> None:
                    try:
                        progress_queue.put_nowait(event)
                    except Exception:
                        pass

                ws_hooks.register(EventType.AGENT_PRE_RUN, lambda d: _put_event({"type": "status", "status": "started", "session_id": d.get("session_id", session_id)}))
                ws_hooks.register(EventType.MODEL_PRE_CALL, lambda d: _put_event({"type": "status", "status": "thinking", "turn": d.get("turn", 0)}))
                ws_hooks.register(EventType.MODEL_STREAM_CHUNK, lambda d: _put_event({"type": "token", "content": d.get("content", ""), "turn": d.get("turn", 0)}))
                ws_hooks.register(EventType.TOOL_PRE_DISPATCH, lambda d: _put_event({"type": "tool_start", "name": d.get("tool", ""), "arguments": d.get("args", {})}))
                ws_hooks.register(EventType.TOOL_POST_DISPATCH, lambda d: _put_event({"type": "tool_end", "name": d.get("tool", ""), "status": d.get("status", "ok")}))
                ws_hooks.register("tool.analytics", lambda d: _put_event({"type": "tool_call", "name": d.get("tool", ""), "status": d.get("status", ""), "duration_ms": d.get("duration_ms", 0)}))
                ws_hooks.register("turn.complete", lambda d: _put_event({"type": "turn", "turn": d.get("turn", 0), "duration_ms": d.get("turn_duration_ms", 0), "tool_call_count": d.get("tool_call_count", 0)}))
                ws_hooks.register(EventType.AGENT_POST_RUN, lambda d: _put_event({"type": "status", "status": "completed", "session_id": d.get("session_id", session_id)}))

                heartbeat_stop = asyncio.Event()

                async def heartbeat():
                    while not heartbeat_stop.is_set():
                        await asyncio.sleep(15)
                        if not heartbeat_stop.is_set():
                            try:
                                await websocket.send_json({"type": "ping"})
                            except Exception:
                                break

                async def event_pump():
                    """Read events from queue and send to websocket."""
                    while not heartbeat_stop.is_set():
                        try:
                            event = await asyncio.wait_for(progress_queue.get(), timeout=5)
                            if event is None:
                                break
                            try:
                                await websocket.send_json(event)
                            except Exception:
                                break
                        except asyncio.TimeoutError:
                            continue
                        except Exception:
                            break

                hb_task = asyncio.create_task(heartbeat())
                pump_task = asyncio.create_task(event_pump())
                try:
                    async with app.state.concurrency_limiter:
                        result = await run_agent_turn(
                            message, manifest=manifest, session_id=session_id, request_id=request_id,
                            hooks=ws_hooks, hitl_store=getattr(app.state, "hitl_store", None),
                        )
                finally:
                    heartbeat_stop.set()
                    try:
                        progress_queue.put_nowait(None)
                    except Exception:
                        pass
                    hb_task.cancel()
                    pump_task.cancel()
                    try:
                        await hb_task
                    except asyncio.CancelledError:
                        pass
                    try:
                        await pump_task
                    except asyncio.CancelledError:
                        pass

                _record_session(app, session_id, message, result, manifest.model)
                if result.errors:
                    await websocket.send_json({"type": "error", "errors": result.errors})
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
        except Exception as exc:
            logger.debug("WebSocket error: %s", exc)
            return

    async def _handle_chat_sse(raw: dict[str, Any], request_id: str = "") -> StreamingResponse:
        try:
            req = ChatRequest(**raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        message = req.message.strip()
        session_id = req.session_id.strip() or uuid4().hex
        await _check_session_rate_limit(session_id)

        progress_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        from metis.events.hooks import HookBus
        from metis.events.event_types import EventType
        sse_hooks = HookBus()

        def _put_event(event: dict[str, Any]) -> None:
            try:
                progress_queue.put_nowait(event)
            except Exception:
                pass

        def on_agent_pre_run(data: dict[str, Any]) -> None:
            _put_event({"type": "status", "status": "started", "session_id": data.get("session_id", session_id)})

        def on_model_pre_call(data: dict[str, Any]) -> None:
            _put_event({"type": "status", "status": "thinking", "turn": data.get("turn", 0)})

        def on_model_stream_chunk(data: dict[str, Any]) -> None:
            _put_event({"type": "token", "content": data.get("content", ""), "turn": data.get("turn", 0)})

        def on_tool_pre_dispatch(data: dict[str, Any]) -> None:
            _put_event({"type": "tool_start", "name": data.get("tool", ""), "arguments": data.get("args", {})})

        def on_tool_post_dispatch(data: dict[str, Any]) -> None:
            _put_event({"type": "tool_end", "name": data.get("tool", ""), "status": data.get("status", "ok")})

        def on_tool_analytics(data: dict[str, Any]) -> None:
            _put_event({"type": "tool_call", "name": data.get("tool", ""), "status": data.get("status", ""), "duration_ms": data.get("duration_ms", 0)})

        def on_turn_complete(data: dict[str, Any]) -> None:
            turn = data.get("turn", 0)
            tool_call_count = data.get("tool_call_count", 0)
            _put_event({"type": "turn", "turn": turn, "duration_ms": data.get("turn_duration_ms", 0), "tool_call_count": tool_call_count})
            if tool_call_count == 0:
                _put_event({"type": "status", "status": "responding", "turn": turn})

        def on_agent_post_run(data: dict[str, Any]) -> None:
            _put_event({"type": "status", "status": "completed", "session_id": data.get("session_id", session_id)})

        sse_hooks.register(EventType.AGENT_PRE_RUN, on_agent_pre_run)
        sse_hooks.register(EventType.MODEL_PRE_CALL, on_model_pre_call)
        sse_hooks.register(EventType.MODEL_STREAM_CHUNK, on_model_stream_chunk)
        sse_hooks.register(EventType.TOOL_PRE_DISPATCH, on_tool_pre_dispatch)
        sse_hooks.register(EventType.TOOL_POST_DISPATCH, on_tool_post_dispatch)
        sse_hooks.register("tool.analytics", on_tool_analytics)
        sse_hooks.register("turn.complete", on_turn_complete)
        sse_hooks.register(EventType.AGENT_POST_RUN, on_agent_post_run)

        async def event_stream():
            yield _sse_event("start", {"session_id": session_id})

            async def run_turn():
                async with app.state.concurrency_limiter:
                    result = await run_agent_turn(
                        message, manifest=manifest, session_id=session_id, request_id=request_id,
                        hooks=sse_hooks, hitl_store=getattr(app.state, "hitl_store", None),
                    )
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

            # Drain any remaining events that arrived just before/after task completion
            while True:
                try:
                    event = progress_queue.get_nowait()
                    if event is None:
                        break
                    yield _sse_event(event.pop("type", "progress"), event)
                except asyncio.QueueEmpty:
                    break

            try:
                result = task.result()
            except Exception as exc:
                logger.error("Agent turn failed in SSE: %s", exc)
                yield _sse_event("error", {"error": "Agent turn failed", "session_id": session_id})
                return
            for tool_result in result.tool_results:
                yield _sse_event("tool_result", {"name": tool_result.tool_name, "status": tool_result.status, "content_preview": str(tool_result.content)[:500] if tool_result.content else ""})
            if result.errors:
                yield _sse_event("errors", {"errors": result.errors})
            yield _sse_event("done", {
                "session_id": session_id,
                "content": result.final_text,
                "status": result.status,
                "turns_used": result.turns_used,
            })

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @v1.post("/chat/sse")
    async def chat_sse(request: Request) -> StreamingResponse:
        raw = await request.json()
        request_id = request.headers.get("X-Request-ID", "")
        return await _handle_chat_sse(raw, request_id=request_id)

    app.include_router(v1, prefix="/api/v1")
    app.include_router(hitl_router, prefix="/api/v1")

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
        request_id = request.headers.get("X-Request-ID", "")
        return await _handle_chat(raw, request_id=request_id)

    @app.post("/api/chat/sse")
    async def chat_sse_legacy(request: Request) -> StreamingResponse:
        raw = await request.json()
        request_id = request.headers.get("X-Request-ID", "")
        return await _handle_chat_sse(raw, request_id=request_id)

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
