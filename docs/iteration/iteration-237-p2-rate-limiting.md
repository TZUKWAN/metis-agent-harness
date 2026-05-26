---
iteration: 237
date: 2026-05-26
phase: P2 Safety
status: completed
---

# Iteration 237: Add session-level rate limiting to web API

## Changes
- Added per-session rate limiting to chat endpoints (POST /api/chat, WebSocket, SSE)
- Session rate limit: 10 requests per 60 seconds per session_id
- IP rate limit remains: 60 requests per 60 seconds per IP
- Prevents runaway 8B model clients from flooding the API

## Test Results
- 791 passed, 0 failed, 10 skipped
