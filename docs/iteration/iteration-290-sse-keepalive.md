# Iteration 290: SSE Keepalive Comments

## Problem
SSE chat endpoints (`/api/v1/chat/sse` and `/api/chat/sse`) sent `{"status": "thinking"}` progress events every 0.5 seconds during agent turns. This was:
1. Too frequent, wasting bandwidth and client processing
2. Not standard SSE keepalive — frontends had to handle synthetic "thinking" events
3. Could flood event logs on slow connections

## Solution

1. **SSE comment keepalive**: Changed idle timeout from 0.5s to 5s. On timeout, sends standard SSE comment line (`: keepalive\n\n`):
   - SSE spec: lines starting with `:` are ignored by `EventSource` — no client handler needed
   - Keeps connection alive through proxies/Nginx (which typically have 60s timeouts)
   - 5s interval: 12 keepalives/minute vs 120 thinking events/minute previously

2. **Applied to both v1 and legacy SSE endpoints**.

## Changes
- `metis/app/web.py`: Changed SSE idle timeout from 0.5s to 5s, replaced thinking events with SSE comments

## Result
774 passed, 0 failed
