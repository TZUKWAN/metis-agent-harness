---
iteration: 150
date: 2026-05-26
phase: P1 Security Hardening
status: completed
---

# Iteration 150: P1 Security Hardening

## Changes

### S-1 run_shell security overhaul
- `metis/tools/builtin.py`: Removed `shell=True`, now uses `shell=False` with command parsing
- Added command allowlist (ALLOWED_COMMANDS) with 30+ safe commands
- Added `allowed_commands` parameter to `register_builtin_tools` for extensibility
- Reduced max timeout from 3600 to 600 seconds
- Added content length limit (1MB) for write_file
- Dangerous commands like `rm -rf /` are now blocked before execution
- Metadata updated: `uses_shell: False` (was True)

### S-2 Web API Key authentication + CORS + rate limiting
- `metis/app/web.py`: Added API key authentication via `METIS_WEB_API_KEY` env var
- Added CORS middleware (configurable via `METIS_WEB_CORS_ORIGINS`)
- Added IP-based rate limiting (60 requests/minute default)
- Auth middleware checks X-API-Key header and api_key query parameter
- Returns 401 for invalid key, 429 for rate limit exceeded

### S-3 Prompt injection detection enhancement
- `metis/security/prompt_injection.py`: Expanded from 5 to 11 regex patterns
- Added German (ignoriere/vergiss) and French (ignorez/oubliez) injection patterns
- Added jailbreak/DAN mode detection
- Added role-play injection detection
- Added system prompt exfiltration detection
- Added Unicode normalization attack detection (NFKC comparison)
- Expanded invisible character set from 4 to 16+ characters
- Added format character (Cf category) detection

### S-4 Credential redaction expansion
- `metis/security/redaction.py`: Expanded from 3 to 9 regex patterns
- Added AWS credential detection (AKIA pattern)
- Added GitHub token detection (ghp_, gho_, ghu_, ghs_, ghr_)
- Added Slack token detection (xoxb-, xoxp-, xoxa-, xoxs-)
- Added URL-embedded credential detection (user:pass@host)
- Added database connection string detection (mongodb/postgres/mysql/redis://)
- Added environment variable secret detection (SECRET=, PRIVATE_KEY=, etc.)

### S-5 SQLite hardening
- `metis/state/sqlite_store.py`: Added `PRAGMA foreign_keys=ON`
- Added 9 indexes on frequently queried columns (session_id, plan_id, loop_id)
- Added thread-safe connection support with threading.local
- Connection pooling reverted due to test isolation requirements

## Test Results
- 477 passed, 0 failed, 4 skipped
