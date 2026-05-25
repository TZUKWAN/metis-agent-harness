# Iteration 059 - Eval Suite Schema Validation

## Purpose

Iteration 058 made `run-suite` capable of running, gating, and comparing generic suites. Iteration 059 adds deterministic suite validation before any model call.

This is important for a harness designed around small models and real API calls. A malformed suite should fail locally with a precise report; it should not consume model budget, pollute eval histories, or produce confusing runtime errors.

## Research Basis

Current eval tooling commonly separates validation from execution:

- eval CLIs often expose a `validate` command for suite/config checks;
- CI-oriented eval systems fail fast on bad datasets or suite definitions;
- agent eval practice keeps structural checks deterministic and separate from LLM judge scoring;
- schema validation is especially important when task suites are generated automatically from traces and repair tasks.

Metis follows that pattern by validating suite shape before checking provider configuration or calling the model.

## Implemented

1. New validation module:
   - `metis.evals.suite_validation`

2. New validation API:
   - `validate_eval_suite(path)`
   - `eval_suite_validation_to_markdown(report)`
   - `write_eval_suite_validation(report, output_dir)`

3. New CLI:

```bash
metis eval validate-suite --suite <suite-json-or-dir>
metis eval validate-suite --suite <suite-json-or-dir> --json
metis eval validate-suite --suite <suite-json-or-dir> --output-dir <validation-dir>
```

4. `run-suite` now validates first:
   - validation failure returns `1`;
   - prints the validation markdown;
   - does not check model environment;
   - does not call the model;
   - explicitly states the eval was not run because validation failed.

5. `run_generic_eval_suite()` also validates internally:
   - direct Python callers receive a `ValueError` on invalid suites.
6. Suite JSON readers now accept UTF-8 with BOM through `utf-8-sig`, which prevents Windows-authored JSON files from failing before validation.

## Validation Rules

Top-level rules:

- payload must load as JSON object or JSON list;
- object payload must contain `tasks` as a list;
- `tasks` must not be empty;
- `schema_version`, when present, must be a string;
- `suite` or `name`, when present, must be a string.

Task rules:

- task entry must be an object;
- wrapped materialized tasks must carry object `task_spec`;
- task `id` must be a non-empty string;
- task ids must be unique;
- task `prompt` must be a non-empty string;
- list fields must be lists;
- dict fields must be objects;
- bool fields must be booleans;
- integer threshold fields must be integers or null;
- integer thresholds cannot be negative;
- `max_turns` must be at least 1;
- `required_tool_arguments` entries must be objects;
- `tool` / `tool_name` must be strings when present;
- `arguments` / `args` must be objects when present;
- unknown `EvalTaskSpec` fields are warnings because the loader ignores them.
- UTF-8 files with BOM are accepted.

## Output Contract

Validation JSON includes:

- `path`
- `suite`
- `schema_version`
- `task_count`
- `valid`
- `error_count`
- `warning_count`
- `errors`
- `warnings`

Validation markdown includes:

- summary fields;
- errors section;
- warnings section.

When `--output-dir` is used, files are:

- `suite-validation.json`
- `suite-validation.md`

## Why This Matters For The 9B Goal

The harness must compensate for weak models by removing ambiguity before execution:

- malformed task specs are caught before the model sees a prompt;
- generated repair suites can be audited before they become regression baselines;
- CI can fail with a deterministic schema error instead of a model-dependent failure;
- automatically generated suites become safer to trust.

## Validation

Targeted validation:

```bash
python -m compileall -q metis
python -m pytest tests/unit/test_eval_suite_validation.py tests/unit/test_eval_suite_run.py tests/unit/test_cli_eval.py -q
```

Result:

```text
42 passed
```

## Remaining Gaps

1. Validation rules are hand-coded rather than published as a reusable JSON Schema document.
2. Validation warnings do not yet support severity levels beyond warning/error.
3. Suite validation does not yet inspect actual tool names against a selected tool registry.
4. Suite validation does not yet check quality gate names against a quality gate registry.
5. There is no suite-scoped latest pointer yet.
