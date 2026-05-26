# Iteration 292: Security Response Headers Middleware

## Problem
API responses lacked standard security headers, exposing the application to:
- MIME type sniffing attacks (browser interpreting JSON as HTML)
- Clickjacking (embedding API in iframe)
- Sensitive API responses being cached by proxies/CDNs
- Referrer leakage

## Solution

1. **`security_headers` middleware**: Added as first middleware in the chain, injects headers into every response:
   - `X-Content-Type-Options: nosniff` — prevents MIME sniffing
   - `X-Frame-Options: DENY` — prevents iframe embedding
   - `Referrer-Policy: strict-origin-when-cross-origin` — limits referrer info
   - `Cache-Control: no-store` — applied only to `/api/*` paths to prevent caching of dynamic responses

2. **Non-API paths**: Static files and the index page do not get `Cache-Control: no-store`, allowing normal browser caching.

## Changes
- `metis/app/web.py`: Added `security_headers` middleware
- `tests/unit/test_security_headers.py`: 5 tests for header presence and scope

## Tests
- `test_nosniff_header_present`
- `test_frame_options_header_present`
- `test_referrer_policy_header_present`
- `test_api_endpoints_have_no_store_cache`
- `test_non_api_endpoints_no_cache_header`

## Result
787 passed, 0 failed
