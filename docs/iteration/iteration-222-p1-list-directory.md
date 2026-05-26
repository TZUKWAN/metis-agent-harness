---
iteration: 222
date: 2026-05-26
phase: P1 Core Features
status: completed
---

# Iteration 222: Add list_directory tool

## Changes
- New list_directory tool: lists directory contents with name, type, size, extension
- Directories listed first, alphabetical sorting
- show_hidden option, max_entries limit (default 200, max 1000)
- Security: workspace path validation + is_read_denied check

## Test Results
- 744 passed, 0 failed, 10 skipped
