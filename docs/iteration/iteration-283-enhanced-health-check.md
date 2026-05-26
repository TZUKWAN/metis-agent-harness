# Iteration 283: Enhanced Health Check Endpoint

## Problem
The `/health` endpoint only returned static metadata. Production load balancers and monitoring systems need real subsystem health checks to make routing decisions.

## Solution
Enhanced `/health` to perform active subsystem checks:

1. **Provider connectivity**: Checks provider endpoint status via `build_runtime_status()`
2. **State store**: Verifies database/state store connectivity
3. **Disk space**: Checks free disk space, flags critical if < 1GB
4. **Overall status**: `healthy` / `degraded` / `unhealthy` based on worst failing check

Status logic:
- Disk critical → `unhealthy`
- Provider error / state store error → `degraded`
- Provider unknown / not configured → `healthy` (expected in some deployments)
- All ok → `healthy`

## Changes
- `metis/app/web.py`: Rewrote `health()` endpoint with active checks

## Tests
- `tests/unit/test_web_timeout.py`: Verifies health endpoint returns 200

## Result
751 passed, 0 failed
