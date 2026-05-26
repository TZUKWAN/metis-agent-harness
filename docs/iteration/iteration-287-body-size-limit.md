# Iteration 287: Request Body Size Limit Middleware

## Problem
No request body size limit existed. Malicious or buggy clients could send arbitrarily large payloads, exhausting server memory before reaching any application-level validation.

## Solution

1. **Body size middleware**: Added `body_size_limit` middleware as the first in the chain (before timeout and auth):
   - Checks `Content-Length` header against `MAX_BODY_SIZE`
   - Returns `413 Payload Too Large` with structured error if exceeded
   - Passes through GET requests and requests without Content-Length header

2. **Configurable limit**: `METIS_MAX_BODY_SIZE` environment variable (default 1MB = 1,048,576 bytes)

## Changes
- `metis/app/web.py`: Added `MAX_BODY_SIZE` constant and `body_size_limit` middleware
- `tests/unit/test_body_size_limit.py`: 4 tests for normal, oversized, exact-size, and GET requests

## Tests
- `test_normal_sized_body_accepted`
- `test_oversized_body_rejected`
- `test_exact_max_size_accepted`
- `test_get_request_not_blocked`

## Result
762 passed, 0 failed
