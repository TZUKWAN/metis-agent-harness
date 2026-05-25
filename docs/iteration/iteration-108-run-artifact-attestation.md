# Iteration 108 - Run Artifact Attestation

This iteration adds run-level artifact attestations for eval runs.

## Problem

Metis now records provenance across manifests, pre-run contracts, timelines, diagnosis, repair tasks, targeted eval stubs, and materialized suites. The missing piece was a single artifact inventory for a run directory.

Without that inventory, external tooling must discover files and compute digests itself before trusting a copied or uploaded run bundle.

## Changes

1. Added `metis/evals/attestation.py`.
2. Added `build_run_attestation(run_dir, manifest=None)`.
3. Added `write_run_attestation(run_dir, manifest=None)`.
4. Added `run_attestation_to_markdown(attestation)`.
5. Real-small-model report writing now emits:
   - `run-attestation.json`
   - `run-attestation.md`
6. Generic run-suite report writing emits the same files.
7. Public exports were added through `metis.evals`.

## Attestation Shape

The JSON uses an in-toto/SLSA-like statement shape:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "predicateType": "https://metis.local/attestations/eval-run/v1",
  "subject": [
    {
      "name": "manifest.json",
      "digest": {"sha256": "..."},
      "size_bytes": 1234
    }
  ],
  "predicate": {
    "builder": {"id": "metis-agent-harness"},
    "run_dir": "...",
    "suite": "...",
    "run_name": "...",
    "task_contract_hash": "...",
    "provenance_hash": "...",
    "pre_run_contract_path": "...",
    "pre_run_contract_sha256": "...",
    "pre_run_provenance_hash": "...",
    "artifact_count": 12
  }
}
```

`run-attestation.json` and `run-attestation.md` are excluded from the subject list to avoid recursive self-reference.

## Why This Matters

The harness goal is not only to make small models pass tests. It is to make their work auditable. A run bundle is useful only if it can be copied, compared, uploaded, and verified later.

Run attestation provides the first stable artifact graph for:

1. manifest;
2. pre-run contract;
3. task specs;
4. eval reports;
5. failure artifacts;
6. timelines;
7. cluster and remediation artifacts.

## Validation

- `python -m pytest tests\unit\test_run_attestation.py tests\unit\test_eval_suite_run.py -q`
- Result: `20 passed`

## References Checked

- GitHub artifact attestations bind a named artifact and digest to a predicate using in-toto format.
- SLSA provenance uses `subject` entries with artifact names and SHA256 digests.
- GitHub CLI attestation verification recomputes local artifact digests and compares them with attestation subjects.

## Next Gaps

1. Release gate should verify `run-attestation.json` subject digests.
2. Compare should report missing attestation or attestation digest drift.
3. Targeted eval stub/materialized suite output directories should also write attestations.
4. Add optional signing or external Sigstore/GitHub attestation integration.
5. Add OpenTelemetry-compatible trace export with run artifact anchors.
