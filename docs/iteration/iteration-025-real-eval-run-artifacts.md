# Iteration 025 - Real Eval Run Artifacts

## Purpose

This iteration closes one production-readiness gap in the real small-model eval loop: eval results must not only run, they must be written into a stable, inspectable directory structure.

The target user of Metis will repeatedly test 9B-class or flash-class models against the harness. That workflow needs durable run artifacts, not ad hoc temporary outputs. It also needs combined read/write tasks where the model reads context, produces a file, receives tool evidence, and proves final completion by referencing that evidence.

## Changes

### Stable report directory helpers

`metis/evals/real_model_suite.py` now exposes:

- `real_small_model_eval_report_dir(output_root=".", run_name="latest")`
- `write_real_small_model_eval_reports(suite, output_root=".", run_name="latest")`
- `run_and_write_real_small_model_eval_suite(workspace=".", output_root=".", run_name="latest")`

The default report path is:

```text
docs/evals/runs/latest/
```

The helper writes:

- `eval-report.json`
- `eval-report.md`

These files include suite metadata through `EvalSuiteResult.metadata`.

### Verified read/write report eval

The real small-model suite now includes:

```text
verified-read-write-report-evidence
```

This task requires the model to:

1. Call `read_file` against `README.md`.
2. Call `write_file` against `outputs/verified-read-write-report.md`.
3. Use the `evidence_refs` returned by the `write_file` tool response in the strict final JSON.

Trajectory gates:

- required tools: `read_file`, `write_file`
- forbidden tools: `run_shell`, `run_command`, `run_test`
- required order: `read_file -> write_file`
- required evidence source: `tool_output`
- required verified final: `True`
- `max_invalid_tool_calls=0`
- `max_schema_violations=0`
- `max_retry_budget_exhaustions=0`
- `max_pre_dispatch_blocks=0`

## Tests

Executed:

```bash
python -m pytest -q tests\e2e\test_local_9b_eval.py
python -m compileall -q metis
```

Result:

```text
3 passed, 3 skipped
```

The skipped tests require real endpoint environment variables:

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`

They are skipped rather than faked when the environment is not configured.

## Remaining Work

The next production gaps are:

1. Add timestamped run names in addition to `latest`.
2. Add a CLI command that runs the real suite and writes reports without requiring Python imports.
3. Add regression comparison between the current run and a previous run.
4. Add model profile metadata beyond `small`, including retry policy and context strategy.
5. Add a failure-only markdown section so real endpoint failures are easier to inspect quickly.
