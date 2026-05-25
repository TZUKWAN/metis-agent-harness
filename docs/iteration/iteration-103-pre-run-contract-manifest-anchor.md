# Iteration 103 - Pre-Run Contract Manifest Anchor

This iteration makes the pre-run contract a first-class run artifact anchor in manifests, latest pointers, and release gate validation.

## Problem

Metis already writes `pre-run-contract.json` before provider calls and verifies its contents in gate/compare. The remaining problem was discoverability and artifact integrity. A downstream CI job, dashboard, or trace exporter reading only `manifest.json` or `latest.json` could see post-run provenance, but could not directly locate or verify the pre-run contract file.

That left a provenance gap:

1. pre-run contract existed on disk;
2. manifest did not identify the contract file as an artifact subject;
3. external tooling had to guess the file path and recompute hashes manually;
4. gate did not verify that manifest-level pre-run contract evidence matched the actual file.

## Changes

1. Real-small-model manifests and latest pointers now include:
   - `pre_run_contract_path`
   - `pre_run_contract_sha256`
   - `pre_run_provenance_hash`
2. Generic run-suite manifests and latest pointers now include the same fields.
3. `pre_run_contract_sha256` is computed from the actual `pre-run-contract.json` file bytes.
4. When the contract file is missing, the expected path is still recorded and hash fields remain empty, making the missing evidence visible to release gate.
5. `eval gate` now verifies:
   - manifest path matches `<run-dir>/pre-run-contract.json`;
   - manifest SHA256 matches the actual file bytes;
   - manifest pre-run provenance hash matches the contract's `provenance_hash`.

## Why This Matters

The harness goal is to let smaller models perform high-quality work by surrounding them with strong contracts, evidence, gates, and regression loops. For that to work, eval artifacts need stable identity and integrity.

This iteration makes pre-run declarations externally auditable. A consumer can now read one run manifest and immediately know:

1. which pre-run contract file was declared;
2. the digest of that contract file;
3. the provenance hash declared before provider execution;
4. whether release gate verified those claims.

This follows the same basic shape used by artifact provenance systems: identify the subject artifact, bind it to a digest, and make verification automatic.

## Validation

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_eval_suite_run.py -q`
- Result: `34 passed`

## External References Checked

- GitHub artifact attestations bind a subject artifact and digest to a provenance predicate.
- SLSA provenance guidance emphasizes subject digests as a verification anchor.
- OpenTelemetry GenAI semantic conventions emphasize structured trace attributes for model/tool execution context.

## Next Gaps

1. Add the same pre-run contract anchor to trace exports.
2. Make `eval compare` verify manifest-declared pre-run contract SHA256 against the actual file.
3. Include pre-run contract anchors in diagnosis and repair task reason links.
4. Add a run-level attestation file listing manifest, pre-run contract, task specs, and failure artifact digests.
5. Add suite-scoped latest pointers for generic eval suites.
