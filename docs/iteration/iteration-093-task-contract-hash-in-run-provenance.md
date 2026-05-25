# Iteration 093: Task Contract Hash in Run Provenance

Date: 2026-05-25

## Objective

Iteration 091 made release gates require suite schema evidence. Iteration 092 made the code-defined `real-small-model` suite record schema evidence honestly.

The remaining gap was task contract provenance. `EvalSuiteResult.write_reports()` already wrote `task-specs.json`, but the top-level `manifest.json` and `latest.json` did not expose a stable hash of the task set. This meant dashboards, release gates, and quick comparisons could see schema provenance but still had to open a secondary file to prove which exact task contracts ran.

This iteration promotes task contract identity to first-class run metadata.

## External References Checked

The external research direction reinforced the same design:

- OpenTelemetry GenAI semantic conventions emphasize trace attributes for model calls, tools, token usage, and GenAI operation visibility: https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
- OpenTelemetry's 2026 GenAI observability guidance frames agent diagnosis as tracing the full chain of model calls and tool invocations: https://opentelemetry.io/blog/2026/genai-observability/
- MLflow dataset tracking emphasizes schema, lineage, and evaluation dataset identity as part of reproducible evaluation: https://mlflow.org/docs/latest/ml/dataset/
- OpenAI Evals provides a model/system evaluation framework and benchmark registry direction: https://github.com/openai/evals
- AgentAssay research highlights trace-first regression testing, behavioral fingerprints, and CI/CD gates for non-deterministic agent workflows: https://arxiv.org/abs/2603.02601

The practical Metis conclusion: every eval artifact must carry enough identity to prove not only the result, but the task contract and schema contract that produced the result.

## Completed Changes

1. `EvalSuiteResult` now exposes:
   - `task_spec_hash_summary()`
   - `task_contract_hash()`

2. `task-specs.json` now includes:
   - `task_contract_hash`
   - `task_spec_hash_summary`
   - per-task `task_spec_hashes`

3. Generic eval run `manifest.json` now includes:
   - `task_contract_hash`
   - `task_spec_hash_summary`

4. Generic eval `latest.json` now includes:
   - `task_contract_hash`
   - `task_spec_hash_summary`

5. Real small-model `manifest.json` now includes:
   - `task_contract_hash`
   - `task_spec_hash_summary`

6. Real small-model `latest.json` now includes:
   - `task_contract_hash`
   - `task_spec_hash_summary`

7. Tests now verify:
   - `task-specs.json` exposes the suite-level task contract hash;
   - generic run manifest/latest pointer preserve task contract identity;
   - real-small-model manifest/latest pointer preserve task contract identity.

## Design Details

The suite-level hash is computed from a stable JSON payload:

```json
{
  "task_count": 12,
  "task_spec_hash_summary": {
    "task-id": {
      "prompt_hash": "...",
      "constraints_hash": "...",
      "task_spec_hash": "..."
    }
  }
}
```

This avoids hashing volatile run results, timestamps, paths, or provider metadata. The hash represents the task contract set only.

## Why This Matters for 9B/Flash Models

Small models need many regression loops. Those loops are only trustworthy if each result can prove:

1. which model/profile ran;
2. which suite schema contract applied;
3. which task contracts ran;
4. which tools and gates were allowed;
5. which traces and failure artifacts were produced.

Without task contract identity in the top-level manifest, two runs can look comparable while silently testing different prompts, required tools, forbidden tools, evidence requirements, or schema repair gates.

This iteration makes task drift harder to miss.

## Verification

- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_compare.py -q`
  - `86 passed`
- `python -m compileall -q metis`
  - passed
- `python -m pytest tests\unit\test_eval_runner.py tests\unit\test_eval_suite_run.py tests\unit\test_eval_compare.py tests\unit\test_eval_gate.py tests\unit\test_cli_eval.py -q`
  - `132 passed`
- `python -m pytest -q`
  - `329 passed, 4 skipped`

## Remaining Gaps

1. `eval compare` should explicitly surface top-level `task_contract_hash` drift from manifests/latest pointers, not only read `task-specs.json`.
2. `eval gate` should optionally require non-empty task contract evidence for release profiles.
3. Task contract hash should include suite-definition metadata when comparing code-defined suites against file-loaded suites.
4. Trace exports should map task contract hash into OTel-compatible resource/span attributes.
5. A generated code-defined suite manifest should be written before real-model execution so model-token spend is tied to a pre-run contract artifact.
