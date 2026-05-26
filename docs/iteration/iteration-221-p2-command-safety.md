---
iteration: 221
date: 2026-05-26
phase: P2 Safety
status: completed
---

# Iteration 221: Add dangerous command pattern detection

## Changes
- Added DANGEROUS_PATTERNS regex list for destructive commands
- Patterns block: rm -rf /, rm -rf ~, format drive, dd to disk, git force push, git reset --hard, git clean -f, git checkout .
- _check_dangerous_patterns() integrated into run_shell and run_command
- Returns exit_code=-1 with descriptive error when blocked

## Test Results
- 738 passed, 0 failed, 10 skipped
