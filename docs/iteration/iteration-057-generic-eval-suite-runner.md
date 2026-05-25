# Iteration 057 - Generic Eval Suite Runner

## Purpose

Iteration 056 made `targeted-eval-suite.json` loadable. Iteration 057 makes it runnable.

The harness now supports a generic suite execution path that is not tied to the built-in `real-small-model` suite. This is required for Metis to become a domain-neutral agent infrastructure layer: scenario teams should be able to generate or author a suite JSON, run it against any configured OpenAI-compatible provider, and receive the same reports, manifests, failure artifacts, timelines, clusters, and gates as the built-in eval.

## Research Basis

This iteration followed current public eval practice:

- OpenAI Evals uses external task data plus runner logic and records aggregate results.
- Braintrust emphasizes systematic experiments, agent traces, and trace-level scoring.
- LangSmith positions agent evaluation around full trajectories, tool calls, and multi-turn workflows.

For Metis, the same principle means `targeted-eval-suite.json` must not remain a static artifact. It must be executable through the same runtime path that produces comparable eval runs.

## Implemented

1. New generic suite runner module:
   - `metis.evals.suite_run`

2. Suite loading and metadata:
   - `load_eval_suite_payload(path)`
   - `generic_eval_suite_metadata(...)`
   - `generic_eval_env_configured()`

3. Generic runner construction:
   - `build_generic_eval_runner(workspace=".", profile="small")`
   - registers built-in tools;
   - uses `OpenAICompatibleProvider`;
   - creates a SQLite state store under `.metis/generic-eval-suite-state.db`;
   - wires `EvidenceLedger`;
   - supports `small`, `balanced`, `small_strict`, and `deep` runtime profiles.

4. Suite execution:
   - `run_generic_eval_suite(suite_path=..., workspace=..., profile=...)`
   - loads tasks through `load_eval_task_specs()`;
   - runs via `EvalRunner.run_suite()`;
   - records suite name, suite path, schema version, task count, model, base URL, and profile in metadata.

5. Generic report writing:
   - `write_generic_eval_suite_reports(...)`
   - `generic_eval_suite_manifest(...)`
   - `write_generic_eval_latest_pointer(...)`

6. New CLI:

```bash
metis eval run-suite --suite <suite-json-or-dir>
metis eval run-suite --suite <suite-json-or-dir> --workspace <workspace> --output-root <output-root>
metis eval run-suite --suite <suite-json-or-dir> --run-name auto --profile small
metis eval run-suite --suite <suite-json-or-dir> --gate
```

The command refuses to run without:

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`

It explicitly states that no model result was faked.

## Output Contract

The generic runner writes the same run artifacts expected by comparison and gate tooling:

- `eval-report.json`
- `eval-report.md`
- `task-specs.json`
- `failures/index.json`
- `failures/clusters.json`
- `failures/clusters.md`
- `failures/remediation-backlog.json`
- `failures/remediation-backlog.md`
- `manifest.json`
- `docs/evals/runs/latest.json`

The manifest includes:

- suite name
- run name
- requested run name
- generated timestamp
- success rate
- task count
- passed count
- failed count
- metadata
- failed task ids

## Why This Matters For The 9B Goal

The long-term objective is to make small models behave like much larger coding agents by surrounding them with structure:

- explicit task specs;
- strict tool permissions;
- required tool order;
- required tool arguments;
- schema repair metrics;
- tool repair metrics;
- retry-budget constraints;
- evidence and finalization constraints;
- trace-aware failure artifacts;
- release gates;
- regression comparison.

`metis eval run-suite` turns those controls into a repeatable execution unit. That is a core harness capability, not a scenario-specific feature.

## Validation

Targeted validation:

```bash
python -m compileall -q metis
python -m pytest tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py tests/unit/test_eval_runner.py -q
```

Result:

```text
64 passed
```

## Remaining Gaps

1. `targeted-eval-suite.json` still has no explicit schema validator; malformed fields are caught only during task loading.
2. `run-suite` can run and gate, but cannot yet compare against a baseline in the same invocation.
3. `latest.json` is shared by generic and real-small-model suites; this is useful for common compare tooling but should gain suite-scoped pointers too.
4. There is no JSONL/YAML import path for third-party benchmark formats yet.
5. There is no rubric/judge extension for open-ended deliverable quality yet.
