# Iteration 058 - Generic Run Suite Comparison

## Purpose

Iteration 057 made arbitrary eval suites runnable. Iteration 058 adds same-command comparison so `metis eval run-suite` can behave like a release-grade eval command:

```text
run suite -> write reports -> optional gate -> optional baseline/latest comparison -> write comparison and diagnosis artifacts
```

This matters because a reusable harness for small models cannot rely on one-off green runs. It needs regression detection against a stable baseline every time prompts, tools, runtime profiles, or model endpoints change.

## Research Basis

This iteration reviewed current eval/CI practice around regression gates:

- agent eval harness guidance emphasizes comparing candidate runs against baselines;
- CI-oriented eval systems treat regression detection as a release gate;
- agent-specific tooling increasingly compares tool-call behavior, not only final answer text;
- deterministic checks and run artifacts remain the first layer, with judge/rubric scoring as a later extension.

The Metis implementation continues that direction by comparing persisted run directories, including manifests, task specs, failure clusters, environment metadata, and failure artifacts.

## Implemented

`metis eval run-suite` now supports:

```bash
metis eval run-suite --suite <suite-json-or-dir> --compare-baseline <run-dir>
metis eval run-suite --suite <suite-json-or-dir> --compare-latest
metis eval run-suite --suite <suite-json-or-dir> --compare-output-dir <comparison-dir>
metis eval run-suite --suite <suite-json-or-dir> --compare-profile strict
metis eval run-suite --suite <suite-json-or-dir> --compare-profile release
metis eval run-suite --suite <suite-json-or-dir> --compare-profile exploratory
```

Behavior:

1. `--compare-baseline` compares the new run against an explicit baseline run directory.
2. `--compare-latest` reads the previous `docs/evals/runs/latest.json` before the new run is written, then compares against that previous latest run.
3. If `--compare-latest` is requested and no previous pointer exists, the command returns non-zero and prints a clear message.
4. Default comparison output is `<current-run>/comparison`.
5. Comparison uses the existing `compare_eval_runs()` engine.
6. Comparison artifacts are written through `write_eval_run_comparison()`, so diagnosis artifacts are generated too.
7. If comparison detects regression, command exit code becomes non-zero.

## Output Contract

When comparison is enabled, the command writes:

- `comparison.json`
- `comparison.md`
- `diagnosis.json`
- `diagnosis.md`

Those outputs can then feed:

- `metis eval diagnose`
- `metis eval repair-plan`
- `metis eval eval-stubs`
- `metis eval materialize-stubs`
- `metis eval run-suite`

That closes the repeatable repair loop.

## Validation

Targeted validation:

```bash
python -m compileall -q metis
python -m pytest tests/unit/test_cli_eval.py -q
```

Result:

```text
29 passed
```

## Remaining Gaps

1. `run-suite` comparison is command-integrated, but suite-scoped latest pointers are still missing.
2. Comparison is deterministic and artifact-based; open-ended quality rubrics still need a separate judge layer.
3. Suite schema validation should run before any model calls.
4. Baseline comparison currently uses one baseline run; future work should support model/profile matrix comparison.
5. CI output should gain a compact machine-readable summary for external pipelines.
