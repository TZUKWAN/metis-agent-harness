# Iteration 056 - Executable Targeted Eval Suite

## Purpose

Iteration 055 produced targeted eval stubs from repair tasks. That was useful for human review, but it still left a gap between diagnosis and repeatable regression execution: the harness could suggest a focused eval, but could not yet materialize those suggestions into a loadable suite.

Iteration 056 closes that gap by turning `targeted-eval-stubs.json` into `targeted-eval-suite.json`, and by adding a generic loader that converts JSON task specs back into `EvalTaskSpec` instances.

This follows the harness research direction checked during this iteration: agent regression evaluation needs fixed task inputs, deterministic constraints, comparable runs, and trajectory-level signals rather than only final-output scoring. Recent agent evaluation writing repeatedly emphasizes repeatable scenario suites, tool-call correctness, baseline-vs-candidate comparison, and trace-aware diagnosis.

## Implemented

1. JSON-to-`EvalTaskSpec` loading:
   - `eval_task_spec_from_dict(payload)`
   - `eval_task_specs_from_suite_payload(payload)`
   - `load_eval_task_specs(path)`

2. Supported suite shapes:
   - a raw JSON list of task spec objects;
   - a suite object with `tasks`;
   - materialized task wrappers with `task_spec`;
   - a directory containing `targeted-eval-suite.json`.

3. Stub materialization:
   - `load_eval_stubs(path)`
   - `materialize_eval_suite_from_stubs(stubs)`
   - `eval_suite_to_markdown(suite)`
   - `write_materialized_eval_suite(suite, output_dir)`
   - `materialize_eval_suite(stubs_path, output_dir=None)`

4. CLI:

```bash
metis eval materialize-stubs --stubs <targeted-eval-stubs-json-or-dir>
metis eval materialize-stubs --stubs <targeted-eval-stubs-json-or-dir> --output-dir <suite-dir>
metis eval materialize-stubs --stubs <targeted-eval-stubs-json-or-dir> --json
```

5. Outputs:
   - `targeted-eval-suite.json`
   - `targeted-eval-suite.md`

## Materialized Suite Schema

The materialized suite keeps both execution data and diagnostic provenance.

Top-level fields:

- `suite`: currently `targeted-repair-regression`
- `profile`
- `baseline`
- `current`
- `task_count`
- `tasks`

Each task wrapper includes:

- `task_id`
- `source_repair_task_id`
- `reason`
- `priority`
- `owner_area`
- `cluster_keys`
- `critical_event_ids`
- `likely_source_modules`
- `suggested_assertion`
- `verification_command`
- `task_spec`

`task_spec` is the executable `EvalTaskSpec` payload. It carries prompt, allowed tools, turn budget, required tools, forbidden tools, required tool order, required tool arguments, schema repair constraints, tool repair constraints, retry budget constraints, policy constraints, evidence constraints, and failure-shape constraints.

## Why This Matters

For a reusable Metis harness, repair should become a durable eval, not a one-off note. This iteration creates the deterministic path:

```text
eval run -> comparison -> diagnosis -> repair tasks -> repair plan -> targeted stubs -> materialized eval suite -> loaded EvalTaskSpec list
```

That path is important for 9B-class models because the harness must compensate for weaker native planning reliability with:

- narrow task specs;
- explicit tool constraints;
- explicit retry and repair budgets;
- failure lineage;
- exact source repair provenance;
- repeatable regression gates.

## Validation

Targeted validation:

```bash
python -m compileall -q metis
python -m pytest tests/unit/test_eval_runner.py tests/unit/test_eval_compare.py tests/unit/test_cli_eval.py -q
```

Result:

```text
85 passed
```

## Remaining Gaps

1. The materialized suite can be loaded into `EvalTaskSpec`, but there is not yet a generic CLI command to run any arbitrary suite JSON against a configured provider.
2. Suite metadata does not yet record model/provider/run profile at materialization time because the suite is generated before execution.
3. Stub generation still relies on deterministic rules in `compare.py`; once the rule count grows, source-module and assertion selection should move to dedicated modules.
4. The targeted suite has deterministic harness constraints, but does not yet include optional LLM-as-judge rubrics for open-ended deliverable quality.
5. Materialized suite versioning is implicit; it should gain an explicit schema version before external publication.
