# Iteration 294: Memory Usage and Session Count in Health Endpoint

## Problem
The `/health` endpoint did not report process memory usage or active session count, making it harder for load balancers and monitoring to detect memory leaks or session overload.

## Solution

1. **Process memory**: Optional `psutil`-based RSS memory check:
   - Reports RSS in MB
   - `< 512MB`: ok
   - `512MB - 1GB`: warning (degraded)
   - `> 1GB`: critical (unhealthy)
   - Gracefully skipped if `psutil` not installed

2. **Session count**: Reports number of active in-memory sessions with status "ok".

## Changes
- `metis/app/web.py`: Added memory and session checks to `health()` endpoint

## Result
787 passed, 0 failed
