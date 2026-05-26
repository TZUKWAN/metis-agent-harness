# Iteration 296: Request ID in Structured Logs

## Problem
API request logs did not include the request ID, making it impossible to correlate log entries with specific client requests in a concurrent environment.

## Solution

1. **Request ID in all API logs**: The `auth_and_rate_limit` middleware now extracts/generates `request_id` before calling the next handler, and includes `[req=<id>]` in all log messages.

2. **Consistent ID generation**: If client provides `X-Request-ID` header, it's used. Otherwise, a 16-char hex ID is generated. The same ID appears in the response header and all server-side logs.

3. **Exception logs**: Unhandled exceptions now include the request ID for traceability.

## Changes
- `metis/app/web.py`: Added request_id to API logs and exception logs in auth_and_rate_limit middleware

## Result
791 passed, 0 failed
