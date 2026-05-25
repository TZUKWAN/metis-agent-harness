# Iteration 104 - Compare Pre-Run Contract Anchor

This iteration makes `eval compare` verify the pre-run contract artifact anchor declared by run manifests.

## Problem

Iteration 103 added these fields to manifests and latest pointers:

- `pre_run_contract_path`
- `pre_run_contract_sha256`
- `pre_run_provenance_hash`

Release gate verifies those fields for a single run. The remaining gap was cross-run comparison. `eval compare` could detect pre-run/post-run content drift, but it did not verify that manifest-declared pre-run contract digest matched the actual `pre-run-contract.json` file on disk.

That meant a comparison could still trust a run where:

1. the pre-run contract file exists;
2. task contract and provenance fields match;
3. the manifest's declared contract SHA256 is stale or falsified.

## Changes

1. `load_eval_run()` now computes SHA256 from the actual `<run-dir>/pre-run-contract.json` file bytes.
2. `_pre_run_post_run_mismatches()` now checks:
   - manifest `pre_run_contract_path` against the actual run contract path;
   - manifest `pre_run_contract_sha256` against the actual file digest;
   - manifest `pre_run_provenance_hash` against the contract's `provenance_hash`.
3. Existing release/strict behavior blocks these issues through `pre_run_post_run_mismatch`.
4. Test coverage now proves that a run with matching business fields but a bad manifest `pre_run_contract_sha256` fails comparison.

## Why This Matters

Metis should treat eval runs as portable evidence bundles. When a run is copied between machines or pulled from a repository, compare should verify not just scores and manifests, but also the integrity anchors that prove which pre-run contract was executed.

This mirrors artifact provenance verification practice: the declared subject digest must match the artifact bytes being consumed.

## Validation

- `python -m pytest tests\unit\test_eval_compare.py -q`
- Result: `42 passed`

## References Checked

- SLSA verifying artifacts guidance: provenance subject digest must match the artifact.
- in-toto/SLSA provenance model: subject artifacts are identified by digest.
- OpenTelemetry artifact semantic attributes: artifact hash/digest is structured metadata for provenance and observability.

## Next Gaps

1. Add pre-run contract anchor fields to trace exports and timeline metadata.
2. Include pre-run contract anchor details in diagnosis and repair task reason links.
3. Add `run-attestation.json` with digest entries for manifest, pre-run contract, task specs, reports, and failure artifacts.
4. Split compare trust state into `baseline_untrusted` and `current_untrusted`.
5. Add suite-scoped latest pointers for generic eval suites.
