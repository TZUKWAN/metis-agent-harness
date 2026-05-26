# Iteration 284: Replace Deprecated @app.on_event with Lifespan Context Manager

## Problem
FastAPI's `@app.on_event("startup")` is deprecated and emits DeprecationWarning. The modern approach uses `@asynccontextmanager lifespan`, which provides cleaner startup/shutdown lifecycle management and better testability.

## Solution

1. **Lifespan context manager**: Replaced `@app.on_event("startup")` with `@asynccontextmanager async def lifespan(app: FastAPI)`:
   - Startup: creates `_periodic_cleanup` background task
   - Yield: application runs
   - Shutdown: cancels cleanup task gracefully

2. **FastAPI integration**: Passed `lifespan=lifespan` to `FastAPI(...)` constructor

3. **Code cleanup**: Removed unused `import json as _json` in `standard_error_handler` and redundant local `build_runtime_status` import in `tools_list`

## Changes
- `metis/app/web.py`: Replaced deprecated startup event with lifespan context manager

## Tests
- `tests/unit/test_web_timeout.py`: Verifies web server initialization

## Result
751 passed, 0 failed. No DeprecationWarnings from FastAPI lifecycle management.
