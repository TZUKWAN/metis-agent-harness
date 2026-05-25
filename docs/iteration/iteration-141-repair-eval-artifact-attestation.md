# Iteration 141 - Repair Eval Artifact Attestation

Date: 2026-05-25

## Problem

Repair plans are now attested and independently verifiable. The next gap was the artifacts generated after the plan:

- targeted eval stubs;
- materialized targeted eval suites.

These artifacts are consumed by later repair and regression loops. If they can be edited after generation without detection, a future repair loop can run against a stale or tampered regression contract.

For a small-model harness, this is dangerous because a 9B model should not be asked to repair against an unaudited generated eval contract.

## Implementation

Added repair eval artifact attestation helpers in `metis.evals.attestation`:

- `build_repair_eval_artifact_attestation()`
- `write_targeted_eval_stubs_attestation()`
- `write_targeted_eval_suite_attestation()`
- `verify_targeted_eval_stubs_attestation()`
- `verify_targeted_eval_suite_attestation()`
- `repair_eval_artifact_attestation_to_markdown()`

The new predicate type is:

```text
https://metis.local/attestations/repair-eval-artifacts/v1
```

`write_eval_stubs()` now writes:

- `targeted-eval-stubs.json`
- `targeted-eval-stubs.md`
- `targeted-eval-stubs-attestation.json`
- `targeted-eval-stubs-attestation.md`

`write_materialized_eval_suite()` now writes:

- `targeted-eval-suite.json`
- `targeted-eval-suite.md`
- `targeted-eval-suite-attestation.json`
- `targeted-eval-suite-attestation.md`

The attestation predicate records:

- builder id;
- output directory;
- artifact type;
- profile;
- task or stub count;
- suite schema version when available;
- generated timestamp;
- artifact count.

Verification checks:

1. attestation JSON exists;
2. statement type is correct;
3. predicate type is the repair eval artifact predicate;
4. artifact type matches expected wrapper;
5. subject list is present;
6. self-subjects are rejected;
7. subject files exist;
8. SHA256 digests match current bytes;
9. sizes match;
10. required JSON and Markdown subjects are present.

## Harness Impact

The repair trust chain now extends beyond repair planning:

```text
comparison
-> diagnosis
-> repair tasks
-> attested repair plan
-> attested targeted eval stubs
-> attested materialized targeted eval suite
```

This matters because generated eval contracts are executable infrastructure. They decide what future repairs must prove. Making them tamper-evident keeps model repair downstream of deterministic artifact verification.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py tests\unit\test_run_attestation.py -q
```

Result:

```text
62 passed
```

New coverage verifies:

1. targeted eval stubs write attestation JSON and Markdown;
2. targeted eval suite writes attestation JSON and Markdown;
3. attestation subjects include only the generated JSON and Markdown artifacts;
4. verification passes immediately after writing;
5. verification detects digest drift for tampered stubs Markdown;
6. verification detects digest drift for tampered suite JSON.

## Remaining Work

1. Add CLI verification commands for targeted eval stubs and materialized suites.
2. Add CI recipe steps for repair eval artifact verification.
3. Add signed attestation support.
4. Add attestation verification before running materialized targeted eval suites.
