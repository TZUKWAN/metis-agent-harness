# Iteration 300: Broken Import Removal and Final Cleanup

## Problem
Both SSE endpoints (v1 and legacy) used `__import__("metis.app.runtime", fromlist=["build_runtime_hooks"])` to call a function that does not exist in `metis/app/runtime.py`. This caused `AttributeError` at runtime, which was silently caught by the fallback `HookBus()`, meaning SSE progress events from hooks never worked.

## Solution

1. **Removed broken `__import__` calls**: Both `run_turn()` (v1 SSE) and `run_turn_legacy()` (legacy SSE) now create `HookBus()` directly instead of trying to import a non-existent function.

2. **Legacy endpoints**: Kept as full implementations (not redirects) because POST redirects don't forward request bodies. Code duplication is accepted for backward compatibility.

## Changes
- `metis/app/web.py`: Replaced `__import__` + conditional with direct `HookBus()` instantiation in both SSE generators

## Result
791 passed, 0 failed

---

## Summary: Iterations 284-300 (17 iterations)

| Iter | Topic | Key Change |
|------|-------|------------|
| 284 | Lifespan context manager | Replaced deprecated @app.on_event |
| 285 | Global concurrency limiter | asyncio.Semaphore, METIS_MAX_CONCURRENT |
| 286 | Global exception handler | Safe 500 responses, no stack traces |
| 287 | Request body size limit | 413 Payload Too Large, METIS_MAX_BODY_SIZE |
| 288 | Pydantic input validation | ChatRequest model, 422 errors |
| 289 | WebSocket heartbeat | 15s ping during agent turns |
| 290 | SSE keepalive comments | Standard SSE comment lines |
| 291 | Pydantic response models | ChatResponse, ErrorResponse, etc. |
| 292 | Security response headers | nosniff, DENY, no-store, referrer-policy |
| 293 | Graceful shutdown | Wait for active turns during shutdown |
| 294 | Health memory/sessions | RSS memory, session count in /health |
| 295 | CORS + environment | METIS_ENV, production CORS warning |
| 296 | Request ID in logs | [req=id] in all API logs |
| 297 | Token usage in memory | In-memory session token tracking |
| 298 | SSE error handling | task.result() exception handling |
| 299 | WebSocket injection scan | scan_message() for WebSocket messages |
| 300 | Broken import removal | Removed __import__ of non-existent function |

Final test count: **791 passed, 0 failed**
