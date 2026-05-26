---
iteration: 201
date: 2026-05-26
phase: P2 Performance
status: completed
---

# Iteration 201: Fix HTTP client leak - persistent connection pool

## Changes
- Provider now uses a persistent httpx.AsyncClient instead of creating one per request
- Added connection pool limits: max_connections=10, max_keepalive_connections=5
- Added close() method, async context manager support (__aenter__/__aexit__)
- Client is lazily created and reused across calls
- Verified with real GLM-4.7-Flash API calls

## Impact
- Eliminates TCP connection leak (previously 1 new connection per provider call)
- Eliminates TLS handshake overhead per call
- Added 4 lifecycle tests

## Test Results
- 686 passed, 0 failed, 10 skipped
