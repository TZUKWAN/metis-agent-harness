# Iteration 299: WebSocket Prompt Injection Scanning

## Problem
The WebSocket `/api/v1/chat/stream` endpoint did not call `scan_message()` for prompt injection detection. HTTP chat endpoints (`/api/v1/chat`, `/api/chat`) both had this protection, but WebSocket messages bypassed it entirely.

## Solution

Added `scan_message()` check after validation and rate limiting, before executing the agent turn:
- Unsafe messages receive `{"type": "error", "error": "Potentially unsafe input detected"}` response
- The connection stays open (no disconnect) for subsequent messages
- Injection attempts are logged server-side

## Changes
- `metis/app/web.py`: Added `scan_message()` call in `chat_stream` WebSocket handler

## Result
791 passed, 0 failed
