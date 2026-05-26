---
iteration: 199
date: 2026-05-26
phase: P5 E2E Validation
status: completed
---

# Iteration 199: E2E test with real GLM-4.7-Flash

## Changes
- Added 2 real E2E tests hitting actual GLM-4.7-Flash API
- test_real_glm_soft_mode: Verifies soft output parsing works with real model responses
- test_real_glm_tool_calling: Verifies native tool calling works (tool_calls or text response)
- Both tests pass with real API calls to https://open.bigmodel.cn/api/paas/v4

## Test Results
- 682 passed, 10 skipped (E2E tests pass with real API)
