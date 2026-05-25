# Iteration 147 - Signed Attestations

## Problem

Previous iterations made repair and eval artifacts tamper-evident through SHA256 subject digests, but the attestation statement itself still had no operator-controlled signature boundary.

Digest verification catches local artifact drift. It does not prove that the attestation statement was produced under a trusted CI or operator key.

## Change

Metis attestations now support optional HMAC signing.

When `METIS_ATTESTATION_SIGNING_KEY` is set, the following attestation writers add a `signature` block:

- `write_run_attestation()`
- `write_repair_plan_attestation()`
- `write_targeted_eval_stubs_attestation()`
- `write_targeted_eval_suite_attestation()`
- `write_repair_execute_preflight_attestation()`

The signature block uses:

```text
hmac-sha256-v1
```

The signed payload is the canonical attestation JSON excluding the `signature` field itself.

## Verification Behavior

Verification is backward compatible by default:

- unsigned attestations still verify through digest checks;
- signed attestations require `METIS_ATTESTATION_SIGNING_KEY`;
- signed attestations fail if the configured key id does not match;
- signed attestations fail if the HMAC value does not match;
- `METIS_REQUIRE_ATTESTATION_SIGNATURE=1` makes unsigned attestations fail.

`METIS_ATTESTATION_KEY_ID` can provide a stable operator key label. If it is unset, Metis derives a short key id from the signing key hash.

## Why This Matters For Small Models

The repair chain is designed to keep a 9B model downstream of deterministic control-plane checks. Signed attestations let CI distinguish between:

- a locally digest-consistent artifact bundle;
- an artifact bundle approved under the expected operator key.

That reduces the chance that a small model is asked to repair from stale, hand-edited, or unauthenticated orchestration state.

## Verification

Focused validation for this iteration should include:

```powershell
python -m compileall -q metis
python -m pytest tests\unit\test_run_attestation.py tests\unit\test_docs_exist.py tests\unit\test_cli_eval.py tests\unit\test_eval_compare.py -q
```

## Remaining Work

1. Implement actual repair execution behind the verified preflight.
2. Persist repair attempt status back into repair-plan tasks and phases.
