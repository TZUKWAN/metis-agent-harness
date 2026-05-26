# Iteration 288: Pydantic Input Validation for Chat Endpoints

## Problem
Chat endpoints used manual dictionary operations with `str(body.get("message", "")).strip()` and ad-hoc empty checks. No type safety, no length limits, inconsistent error codes (400 for validation errors).

## Solution

1. **Pydantic `ChatRequest` model** (`metis/app/schemas.py`):
   - `message`: required, 1-50000 chars, auto-stripped, whitespace-only rejected via `field_validator`
   - `session_id`: optional, max 128 chars
   - Validation errors return 422 Unprocessable Entity

2. **Applied to all 5 agent turn entry points**:
   - `POST /api/v1/chat`
   - `WebSocket /api/v1/chat/stream`
   - `POST /api/v1/chat/sse`
   - Legacy `POST /api/chat`
   - Legacy `POST /api/chat/sse`

3. **Updated existing tests** to expect 422 instead of 400 for empty messages.

## Changes
- `metis/app/schemas.py`: New file with `ChatRequest` Pydantic model
- `metis/app/web.py`: All chat endpoints use `ChatRequest` for validation
- `tests/unit/test_input_validation.py`: 10 tests for model and endpoint validation
- `tests/unit/test_api_versioning.py`: Updated expected status code 400 -> 422

## Tests
- `test_chat_missing_message_returns_422`
- `test_chat_empty_message_returns_422`
- `test_chat_whitespace_only_message_returns_422`
- `test_chat_oversized_message_returns_422`
- `test_chat_sse_missing_message_returns_422`
- `test_legacy_chat_missing_message_returns_422`
- `test_chat_request_model_valid`
- `test_chat_request_model_default_session`
- `test_chat_request_model_rejects_no_message`
- `test_chat_request_model_rejects_oversized`

## Result
772 passed, 0 failed
