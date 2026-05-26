# Iteration 291: Pydantic Response Models

## Problem
API responses were manually constructed dictionaries with no type safety. Inconsistent field names, missing documentation, and no serialization guarantees across endpoints.

## Solution

1. **Response models in `metis/app/schemas.py`**:
   - `ChatResponse`: session_id, response, status, errors
   - `ErrorResponse`: error.code, error.message (matches existing API format)
   - `SessionInfo`: id, title, model, message_count, tool_call_count, evidence_count
   - `SessionListResponse`: sessions list
   - `HealthResponse`: status, name, version, model, uptime_seconds, checks

2. **Type safety**: All models use Pydantic v2 with proper field types and defaults.

3. **Serialization**: `model_dump()` produces consistent dict output matching existing API format.

## Changes
- `metis/app/schemas.py`: Added ChatResponse, ErrorResponse, SessionInfo, SessionListResponse, HealthResponse
- `tests/unit/test_response_models.py`: 8 tests for model construction, defaults, and serialization

## Tests
- `test_chat_response_model`
- `test_chat_response_with_errors`
- `test_error_response_model`
- `test_session_info_model`
- `test_session_list_response_model`
- `test_health_response_model`
- `test_error_response_serialization`
- `test_chat_response_serialization`

## Result
782 passed, 0 failed
