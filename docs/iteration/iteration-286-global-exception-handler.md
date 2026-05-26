# Iteration 286: Global Exception Handler

## Problem
Only `HTTPException` had a structured error handler. Unhandled exceptions (code bugs, provider failures, validation errors) propagated through the middleware chain and could leak internal stack traces to clients—a security risk in production.

Additionally, Starlette's `BaseHTTPMiddleware` wraps exceptions in `ExceptionGroup` before they reach `@app.exception_handler(Exception)`, making the decorator-based approach unreliable.

## Solution

1. **Middleware-level catch-all**: Moved exception handling into the outermost `auth_and_rate_limit` middleware via `try/except Exception` around `call_next(request)`:
   - Catches all unhandled exceptions regardless of middleware wrapping
   - Returns standardized `{"error": {"code": 500, "message": "Internal server error"}}` to client
   - No stack traces, no internal details leaked

2. **Server-side logging**: Uses `logger.exception()` to record full traceback for debugging while keeping client response safe.

3. **Preserved HTTPException handler**: `@app.exception_handler(HTTPException)` still handles expected HTTP errors with structured responses.

## Changes
- `metis/app/web.py`: Added try/except in `auth_and_rate_limit` middleware, removed `@app.exception_handler(Exception)`
- `tests/unit/test_global_exception_handler.py`: 3 tests for HTTP exception structure, safe response, and server-side logging

## Tests
- `test_http_exception_returns_structured_error`
- `test_unhandled_exception_returns_safe_response`
- `test_unhandled_exception_logged`

## Result
758 passed, 0 failed
