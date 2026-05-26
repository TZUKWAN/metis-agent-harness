---
iteration: 149
date: 2026-05-26
phase: P0 Bug Fixes
status: completed
---

# Iteration 149: P0 Bug Fixes

## Changes

### B-1 CompletionClaim enum values changed from Chinese to English
- `metis/evidence/schema.py`: Changed enum values from Chinese ("已生成" etc.) to English ("generated" etc.)
- `metis/quality/gates.py`: Updated COMPLETION_CLAIMS and _claim_has_evidence to use English values
- `metis/evidence/matcher.py`: No code change needed (claim.value now correctly matches English text)
- 8 test files updated to use English text in test data

### B-2 Unified max_turns default value
- `metis/runtime/response.py`: Changed AgentRunRequest.max_turns default from 20 to 12
- All 6 locations now consistently use 12 as the default

### B-3 Aurora/Sophia adapter hardcoded paths removed
- `metis/adapters/aurora.py`: Removed default path D:\LATEXTEST\aurora-agent, now requires explicit project_root
- `metis/adapters/sophia.py`: Removed default path D:\LATEXTEST\sophia-agent, now requires explicit project_root
- 3 test files rewritten to use tmp_path fixture with proper directory structure
- Previously failing 4 tests now pass

### B-4 SYSTEM_ROOT_HINTS false positive fix
- `metis/security/paths.py`: Changed from substring matching to path segment matching
- Renamed SYSTEM_ROOT_HINTS to SYSTEM_ROOT_PARTS for clarity
- Added .git, .config, .npm, .cache to DENY_PARTS
- Added id_rsa, id_ed25519 to DENY_FILES
- Added .pem, .key, .p12, .pfx extension blocking
- Legitimate paths containing "windows" substring no longer incorrectly denied

### B-5 Unified _duplicate_tool_calls deduplication key
- `metis/evals/runner.py`: Both code paths now use (tool_name, args_json) as dedup key
- Previously: state path used args_json, fallback path used content (inconsistent)

## Test Results
- Before: 473 passed, 4 failed, 4 skipped
- After: 477 passed, 0 failed, 4 skipped
- All 4 previously failing tests now pass
