# Provider Capability Registry Status

Date: 2026-05-25

## Completed

- Added `ProviderCapabilities` in `metis/providers/base.py`.
- Added OpenAI-compatible provider capability reporting:
  - provider type
  - model
  - native tool-calling support
  - JSON schema support flag
  - streaming implementation status
  - thinking support
  - configured context/output token limits
  - retryable provider status codes
- Added deterministic fake-provider capability reporting for tests.
- Added CLI inspection command:

```powershell
metis provider capabilities --model glm-4.7-flash --json
```

- Updated architecture/module/README documentation.

## Verification

- `python -m compileall -q metis`: passed.
- `python -m pytest tests\unit\test_openai_compat_provider.py tests\unit\test_fake_provider.py tests\unit\test_cli_eval.py -q`: `69 passed`.

Full-suite verification after the current remediation batch: `python -m pytest -q` passed with `461 passed, 4 skipped`.
