# Iteration 295: CORS Configuration and Environment Awareness

## Problem
CORS allowed all origins (`*`) by default with no production warning. No environment distinction — dev, staging, and production ran identically. Health endpoint did not report which environment the server was running in.

## Solution

1. **Environment variable `METIS_ENV`**: Defaults to `development`. Available in health endpoint response as `environment` field.

2. **Production CORS warning**: When `METIS_ENV=production` and CORS is set to `*`, emits a WARNING log to alert operators to configure specific origins.

3. **Origin list cleanup**: Strips whitespace from `METIS_WEB_CORS_ORIGINS` values and filters empty strings.

4. **Health endpoint**: Now includes `environment` field.

## Changes
- `metis/app/web.py`: Added `METIS_ENV` detection, production CORS warning, environment in health response
- `tests/unit/test_cors_config.py`: 4 tests for environment in health, CORS preflight, and production warning

## Tests
- `test_health_includes_environment`
- `test_cors_allows_configured_origin`
- `test_cors_exposes_allowed_headers`
- `test_production_cors_warning_emitted`

## Result
791 passed, 0 failed
