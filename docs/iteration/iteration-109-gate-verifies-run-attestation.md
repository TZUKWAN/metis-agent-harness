# Iteration 109 - Gate Verifies Run Attestation

This iteration turns run-level artifact attestation from a generated artifact into a release-gate requirement.

## Problem

Iteration 108 made eval report writers emit `run-attestation.json` and `run-attestation.md`. The JSON listed every run artifact as an in-toto-style subject with a SHA256 digest and byte size.

That was necessary but not sufficient. A generated attestation only helps if the release path verifies it before trusting the run. Without verification, a copied run directory could contain a stale manifest, a tampered report, or a missing task-spec file while still carrying an old attestation.

For Metis, this matters because the harness is meant to help small models improve through regression loops. Those loops depend on historical run bundles being trustworthy.

## Changes

1. Added `verify_run_attestation(run_dir)`.
2. The verifier checks:
   - `run-attestation.json` exists.
   - The attestation is valid JSON.
   - `_type` is `https://in-toto.io/Statement/v1`.
   - `predicateType` is `https://metis.local/attestations/eval-run/v1`.
   - `subject` is a non-empty list.
   - subject entries are objects with names.
   - `run-attestation.json` and `run-attestation.md` are not self-referenced.
   - subject names are unique.
   - each subject file exists.
   - each subject SHA256 matches the current file bytes.
   - each subject size matches the current file bytes.
   - required artifacts are present in the subject list:
     - `manifest.json`
     - `eval-report.json`
     - `task-specs.json`
3. `evaluate_eval_run_gate()` now accepts:
   - `require_run_attestation_evidence=True`
4. The release gate verifies run attestation by default.
5. Gate JSON records:
   - `require_run_attestation_evidence`
6. CLI `metis eval gate --run ...` explicitly enables the requirement.
7. Legacy callers can opt out by calling:

```python
evaluate_eval_run_gate(run_dir, require_run_attestation_evidence=False)
```

The CLI release path does not opt out.

## Failure Modes

The gate can now reject a run for attestation reasons before treating model quality metrics as trustworthy.

Examples:

1. `run-attestation.json missing from run directory`
2. `run-attestation.json is not valid JSON`
3. `run-attestation _type must be https://in-toto.io/Statement/v1`
4. `run-attestation predicateType must be https://metis.local/attestations/eval-run/v1`
5. `run-attestation subject list missing or empty`
6. `run-attestation subject file missing: <name>`
7. `run-attestation digest mismatch for <name>`
8. `run-attestation size mismatch for <name>`
9. `run-attestation required subject missing: manifest.json`
10. `run-attestation required subject missing: eval-report.json`
11. `run-attestation required subject missing: task-specs.json`

## Why This Matters

Metis is an agent harness, not a scenario-specific app. Its core value is forcing weak or cheap models to operate inside strong contracts:

1. task contracts;
2. tool schemas;
3. evidence requirements;
4. provenance hashes;
5. pre-run contracts;
6. failure timelines;
7. regression suites;
8. release gates;
9. artifact attestations.

This change closes the loop between items 8 and 9. The gate no longer trusts that a run directory is intact because a file says it is intact. It recomputes the subject digests and sizes from the files on disk.

That gives downstream systems a cleaner rule:

```text
No valid run attestation, no release-grade eval result.
```

## Validation

- `python -m pytest tests\unit\test_eval_gate.py tests\unit\test_run_attestation.py tests\unit\test_cli_eval.py -q`
- Result: `60 passed`

## Remaining Gaps

1. `eval compare` should consume attestation verification and report baseline/current trust failures separately.
2. `gate.md` should render an attestation summary with subject counts and failed subject names.
3. `run-attestation.json` is unsigned; Sigstore or GitHub artifact attestation remains future work.
4. Targeted eval stub directories and materialized suite directories should also write attestations.
5. Attestation predicates need explicit schema migration rules.
6. OpenTelemetry trace export should include attestation and pre-run anchors as resource/span attributes.
