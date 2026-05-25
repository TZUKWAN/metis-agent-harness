# 9B Endpoint Evaluation Report

Status: real smoke test passed when `METIS_API_KEY`, `METIS_BASE_URL`, and `METIS_MODEL` were configured.

## Quality gate drift comparison

Eval comparison now consumes per-task `quality_gate_results`.

This closes a release-risk gap for small models: a run can keep the same success rate while a delivery quality gate starts failing. `eval compare` now emits `quality_gate_diff`, flags `quality_gate_failed` in release and strict profiles when a gate newly fails, and links that reason to task ids, artifacts, timelines, and structured `quality_gate_changes`.

Diagnosis and repair tasks also preserve the gate changes. The generated owner area is `quality-gates-and-evidence`, and the suggested eval asks for a deterministic reproduction of the gate input with the gate required to pass.

Targeted eval stubs now carry that same gate drift forward. A `quality_gate_failed` repair task preserves `quality_gate_changes`, extracts `quality_gate_names`, writes the gate names into `eval_task_spec.quality_gates`, and injects compact gate metadata into the prompt. Materialized targeted suites keep the same wrapper metadata, so CI and later repair loops can understand the gate-level regression without reopening the original diagnosis file.

Gate metadata is now also compiled into hard eval constraints when possible. Artifact gate metadata such as `path` or `expected_artifacts` becomes `eval_task_spec.expected_artifacts`; evidence metadata such as `required_evidence_sources` becomes `eval_task_spec.required_evidence_sources`. This reduces the amount of implicit contract reasoning expected from a 9B model.

Default quality gates now emit structured metadata at the source. Artifact gates report checked, missing, empty, or placeholder artifact paths; requirement coverage reports missing requirements and evidence/artifact counts. This makes the compare-to-repair path machine-readable instead of depending on natural-language gate messages.

Requirement coverage gaps now become first-class targeted eval context. When `requirements_covered` reports `missing_requirements`, generated stubs and materialized suites preserve those missing requirements and the prompt explicitly requires the repair to make each one verifiable through final output or recorded evidence.

`EvalTaskSpec` now also has a `requirements` field. Generic eval suites can declare acceptance criteria structurally, and `EvalRunner` passes those criteria into quality gates. This makes `requirements_covered` a runtime verifier over task contracts rather than a prompt-only convention.

Requirement contracts can now be structured through `requirement_criteria`. Criteria can include stable ids, required evidence source types, source refs, and minimum evidence strength. `requirements_covered` reports missing requirement ids, which gives repair loops and dashboards a stable key instead of relying only on requirement text.

Requirement criteria can now also require a concrete artifact path and a successful tool result. `requirements_covered` accepts `required_artifact_path` or `artifact_path`, normalizes Windows and POSIX separators before matching produced artifact records, and accepts `required_tool` or `tool_name` only when the matching tool result is successful. Failed criteria report `missing_artifact_paths` and `missing_tools` in gate metadata, giving repair tasks a direct distinction between "the answer said it did the work" and "the harness observed the file/tool evidence."

Those artifact/tool criteria are now validated before suite execution and propagated through targeted repair generation. A `requirement_criteria` entry may be text-only, evidence-only, artifact-only, tool-only, or a combination, but it must contain at least one verifier field. `validate_eval_suite()` rejects empty criteria, non-string criterion fields, and unknown `required_tool` references when a tool inventory is available. When `requirements_covered` emits `missing_artifact_paths` or `missing_tools`, targeted eval stubs synthesize concrete criteria such as `{"required_artifact_path": "outputs/report.md"}` or `{"required_tool": "write_file"}` so the next regression task verifies the observed execution trace directly.

Artifact path contracts are now checked for portability during suite validation. `expected_artifacts`, `required_artifact_path`, and `artifact_path` must be relative artifact paths; absolute paths, Windows drive-prefixed paths, and parent traversal are rejected before model execution. This keeps generated and handwritten suites reusable across machines instead of binding a regression contract to one developer's local workspace.

Targeted eval generation now applies the same artifact path policy before writing executable repair contracts. Quality gate metadata can still preserve the original observed path for diagnosis, but only portable relative artifact paths are compiled into `eval_task_spec.expected_artifacts` or synthesized `requirement_criteria`. This prevents a failed run recorded on one machine from generating a repair suite that immediately fails validation on another machine.

Filtered artifact paths are now reported as explicit diagnostics on targeted eval stubs and materialized suite tasks. `artifact_path_diagnostics` records the task id, gate, source metadata field, original path, rejection reason, and criterion id when available. The Markdown reports surface the same diagnostics so a repair reviewer can see why a path was kept for diagnosis but excluded from the executable contract.

Generated targeted eval stubs and materialized suites now also include `artifact_path_diagnostic_summary`. The summary aggregates filtered paths by reason, source metadata field, gate, and task id. This gives dashboards a compact metric surface while preserving per-path diagnostics for audit.

Eval run comparison now exposes the same artifact path diagnostic surface before targeted stubs are generated. `compare_eval_runs()` derives `artifact_path_diagnostics` and `artifact_path_diagnostic_summary` from newly failed quality gate metadata, renders the summary in comparison Markdown, and attaches the summary to the `quality_gate_failed` regression reason link. This lets release tooling detect artifact-contract hygiene issues at compare time, not only after repair-suite materialization.

Artifact path hygiene is now a first-class release/strict regression reason. When comparison finds non-portable artifact path diagnostics, `compare_eval_runs()` emits `artifact_path_hygiene_failed`, links the diagnostic details and summary, and routes repair tasks to `eval-suite-hygiene`. This turns absolute paths, Windows drive-prefixed paths, and parent traversal in gate metadata into hard release blockers instead of advisory warnings.

Repair plans now give artifact path hygiene its own pre-behavior phase. When `artifact_path_hygiene_failed` appears in repair tasks, `build_repair_plan()` inserts `phase-0b-repair-suite-hygiene` before release blockers. If artifact trust repair also exists, trust remains first and suite hygiene follows. This keeps contract cleanup ahead of model behavior repair, which is critical for small models that need the harness to separate invalid eval metadata from genuine reasoning or tool-use regressions.

Repair-plan phases now carry machine-readable execution metadata. Precondition phases declare `phase_type: precondition`, `hard_precondition: true`, the downstream work they block, and `requires_completed_preconditions`. Ordinary phases are typed as repair, verification, or stabilization. The Markdown plan renders these fields too, so both humans and future repair executors can see that artifact trust and suite hygiene must complete before behavior repair.

Repair plans now also compute phase status. Every phase includes `status` and `blocked_by`, and the plan includes `phase_status_summary` with counts, blocked phases, executable phases, and open hard preconditions. An unresolved artifact-trust or suite-hygiene precondition now deterministically blocks downstream behavior repair phases; marking the precondition task complete or verified unblocks the later phases. This moves more orchestration judgment out of the model and into the harness control plane.

The repair-plan CLI now exposes that control plane as an enforcement hook. `metis eval repair-plan --require-executable-phase <phase-id>` returns non-zero when the requested phase is absent, blocked, or not executable. This lets CI and future repair executors fail before invoking a model on an unsafe phase, while still printing or writing the plan that explains the block.

Repair-plan outputs are now attested. `write_repair_plan()` writes `repair-plan-attestation.json` and `repair-plan-attestation.md` alongside the JSON and Markdown plan. The attestation uses predicate type `https://metis.local/attestations/repair-plan/v1`, records SHA256 digests for `repair-plan.json` and `repair-plan.md`, and can detect digest drift if either artifact is edited after generation. This makes repair orchestration metadata tamper-evident before CI or future executors trust it.

Phase enforcement now requires a verified repair-plan artifact. When `metis eval repair-plan --require-executable-phase <phase-id>` is used, `--output-dir` is required so the plan can be written and `verify_repair_plan_attestation()` can run before phase status is trusted. If the attestation fails, the command returns non-zero before checking executability. This prevents CI or repair automation from acting on unaudited plan metadata.

Repair-plan attestation can now be verified as a standalone CI step. `metis eval verify-repair-plan --plan-dir <directory>` verifies `repair-plan-attestation.json` against the current repair-plan artifacts and returns non-zero on failure. `--json` emits `plan_dir`, `verified`, `failure_count`, and `failures` for machine consumers.

The complete CI workflow is documented in `docs/evals/repair-plan-ci-recipe.md`. The recipe orders compare, diagnose, repair-plan generation, repair-plan attestation verification, and executable phase enforcement so a 9B model is never invoked on a blocked phase or from an unattested repair plan.

Targeted repair eval artifacts are now attested too. `write_eval_stubs()` writes `targeted-eval-stubs-attestation.json` / `.md`, and `write_materialized_eval_suite()` writes `targeted-eval-suite-attestation.json` / `.md`. Both use predicate type `https://metis.local/attestations/repair-eval-artifacts/v1` and verify SHA256 digests for the generated JSON and Markdown artifacts. This extends the repair trust chain from the repair plan into the generated regression contracts.

Repair eval artifact verification is now exposed through CLI commands. `metis eval verify-eval-stubs --stubs-dir <directory>` verifies targeted eval stub artifacts, and `metis eval verify-targeted-suite --suite-dir <directory>` verifies materialized targeted suite artifacts. Both commands support `--json` and return non-zero on attestation failure, so CI can block before generated repair contracts are consumed.

`metis eval run-suite` now verifies materialized targeted suite attestation before execution when `--suite` points at a `targeted-eval-suite.json` file or a directory containing one. If `targeted-eval-suite-attestation.json` is missing or fails digest verification, the suite is not run. Generic eval suites that are not materialized targeted repair suites are unaffected.

The repair flow now has a single pre-execution gate. `metis eval repair-execute --plan-dir <plan> --phase <phase-id> --stubs-dir <stubs> --suite-dir <suite>` verifies repair-plan attestation, loads `repair-plan.json`, checks that the requested phase is executable, and optionally verifies targeted eval stubs and suite attestations. It does not edit files or invoke a model; it exists to give future repair executors one deterministic readiness check.

`repair-execute` can now persist its readiness result. Passing `--output-dir <directory>` writes `repair-execute-preflight.json` and `repair-execute-preflight.md`, preserving per-check pass/fail status and failure details as CI artifacts.

Preflight artifacts are now attested and independently verifiable. `repair-execute --output-dir <directory>` also writes `repair-execute-preflight-attestation.json` and `.md`; `metis eval verify-repair-preflight --preflight-dir <directory>` verifies that the preflight decision artifacts still match their recorded digests. This prevents a stale or edited readiness decision from becoming the approval source for repair execution.

Attestations now support optional HMAC signing. When `METIS_ATTESTATION_SIGNING_KEY` is set, Metis signs run, repair-plan, targeted eval stub, targeted suite, and repair-execute-preflight attestation JSON with `hmac-sha256-v1`. Verification rejects signed attestations if the configured key is absent or different, and hardened CI can set `METIS_REQUIRE_ATTESTATION_SIGNATURE=1` to reject unsigned attestations. This gives the 9B-oriented repair chain both local digest verification and an operator-controlled production trust boundary.

`repair-execute` can now persist execution attempts without pretending that generic code repair has happened. `--record-attempt-status <status>` writes `repair-execute-attempt.json/.md` and an `updated-repair-plan` snapshot whose phase tasks carry the recorded status and `last_attempt` summary. The updated plan is regenerated through the normal repair-plan builder and attested again, so downstream executors can resume from a machine-readable phase state instead of relying on stdout.

## Suite contract validation update

Metis now validates `required_tool_arguments` against the actual registered tool schemas before a generic eval suite is allowed to run.

This matters for 9B/flash model evaluation because suite design errors must not be confused with model failures. The validator now catches unknown tool argument fields, literal type mismatches, text predicates applied to numeric/boolean-only parameters, and invalid `in` predicate candidate values before any provider call is made.

The generic validation context now includes:

- `available_tools`
- `available_quality_gates`
- `tool_schemas`

This keeps eval suite validation tied to the current tool registry rather than to hand-maintained assumptions.

## Schema repair hint metrics

Metis now records whether schema failures included actionable repair hints and whether the later trajectory recovered after those hints.

New per-task metrics:

- `schema_repair_hints_seen`
- `schema_repair_hint_successes`
- `schema_repair_hint_failures`

New eval gates:

- `min_schema_repair_hint_successes`
- `max_schema_repair_hint_failures`

These metrics are intended to separate generic schema repair from hint-driven schema repair. This is important for 9B/flash models because the harness should be measured not only by how often it blocks invalid tool calls, but also by how often its feedback helps the model recover.

Schema repair hints are now also typed for clustering and regression tracking:

- `schema_repair_hint_types`
- `schema_repair_hint_details`
- `schema_repair_hint_types_seen`
- `schema_repair_hint_type_successes`
- `schema_repair_hint_type_failures`

The detail form keeps `hint_type`, `schema_path`, `schema_keyword`, original `schema_error`, and model-facing `hint_text` together so reports can remain stable even when human-readable wording changes.

Eval reports now include a suite-level `summary` object and a Markdown `## Summary` section. The summary includes schema repair hint recovery rate and per-type seen/success/failure counts, making it possible to compare hint-driven recovery across models, profiles, and eval runs.

Release gates can now enforce schema repair hint recovery:

- `min_schema_repair_hint_recovery_rate`
- `max_schema_repair_hint_failures`

CLI flags:

- `metis eval gate --min-schema-repair-hint-recovery-rate <rate>`
- `metis eval gate --max-schema-repair-hint-failures <count>`

Run manifests and latest pointers now include the same suite-level `summary`, so external dashboards and CI can read hint recovery health from `manifest.json` or `latest.json` without opening the full eval report.

Eval comparison now reads that summary and emits `summary_diff`. Release and strict comparison profiles flag regressions when schema repair hint recovery rate decreases, total hint failures increase, or a specific hint type starts failing more often. The Markdown comparison report includes a `## Summary Drift` section for this run-level movement.

## Current real-model eval suite

Metis now defines a reusable real small-model eval suite in `metis/evals/real_model_suite.py`.

The suite is intentionally real-provider only. It does not fake model results. When the following variables are absent, network tests are skipped:

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`

Current tasks:

1. `strict-final-no-tools`
   - Checks strict final JSON behavior without tools.
   - Gates:
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

2. `read-then-summarize`
   - Requires `read_file` against `README.md`.
   - Forbids write and command tools.
   - Gates:
     - required tool: `read_file`
     - required argument: `path=README.md`
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

3. `safe-command`
   - Requires `run_command`.
   - Forbids `run_shell`.
   - Gates:
     - required tool: `run_command`
     - required argument contains `python`
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

4. `write-report-file`
   - Requires `write_file`.
   - Requires `path=outputs/real-model-report.md`.
   - Forbids read and command tools.
   - Gates:
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

5. `read-then-write-summary`
   - Requires `read_file` before `write_file`.
   - Requires `path=README.md` and `path=outputs/readme-summary.md`.
   - Forbids command tools.
   - Gates:
     - required tool order: `read_file -> write_file`
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

6. `forbidden-shell-readme`
   - Requires README summarization with `read_file` only.
   - Forbids shell, command, test, and write tools.
   - Gates:
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

7. `schema-repair-write-file`
   - Intentionally asks the model to make one malformed `write_file` call, then recover.
   - Requires corrected `path=outputs/schema-repair.md`.
   - Gates:
     - `min_schema_repair_successes=1`
     - `max_schema_repair_failures=0`
     - `allow_recovered_schema_failures=True`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

8. `command-schema-repair`
   - Intentionally asks for malformed `run_command` timeout, then requires correction.
   - Forbids `run_shell`.
   - Gates:
     - `min_schema_repair_successes=1`
     - `max_schema_repair_failures=0`
     - `allow_recovered_schema_failures=True`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

9. `safe-test-command`
   - Requires `run_test` with a pytest command.
   - Forbids `run_shell`.
   - Gates:
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`
     - `max_failure_shape_key_counts={"python pytest": 0}`

10. `verified-test-evidence`
   - Requires `run_test`.
   - Requires the final JSON to include evidence refs returned by the tool result.
   - Requires verified final status through `require_verified_final=True`.
   - Gates:
     - required evidence source: `test`
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

11. `verified-write-evidence`
   - Requires `write_file`.
   - Requires `path=outputs/verified-write.md`.
   - Requires the final JSON to include evidence refs returned by `write_file`.
   - Requires verified final status through `require_verified_final=True`.
   - Gates:
     - required evidence source: `tool_output`
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

12. `verified-read-write-report-evidence`
   - Requires `read_file` before `write_file`.
   - Requires `path=README.md`.
   - Requires `path=outputs/verified-read-write-report.md`.
   - Requires the final JSON to include evidence refs returned by the `write_file` tool response.
   - Requires verified final status through `require_verified_final=True`.
   - Gates:
     - required evidence source: `tool_output`
     - required tool order: `read_file -> write_file`
     - `max_invalid_tool_calls=0`
     - `max_schema_violations=0`
     - `max_retry_budget_exhaustions=0`
     - `max_pre_dispatch_blocks=0`

## Report metadata

Real small-model eval reports now include:

- suite name
- task count
- model
- base URL
- runtime profile

## Stable run artifacts

Real small-model eval runs now have stable report helpers:

- `real_small_model_eval_report_dir(output_root=".", run_name="latest")`
- `write_real_small_model_eval_reports(suite, output_root=".", run_name="latest")`
- `run_and_write_real_small_model_eval_suite(workspace=".", output_root=".", run_name="latest")`

The default report directory is:

```text
docs/evals/runs/latest/
```

Each run directory contains:

- `eval-report.json`
- `eval-report.md`
- `manifest.json`
- `task-specs.json`
- `failures/index.json`
- `failures/<task-id>.json` for each failed task
- `failures/clusters.json`
- `failures/clusters.md`
- `failures/remediation-backlog.json`
- `failures/remediation-backlog.md`

This keeps real endpoint outputs reproducible and auditable without faking model results.

`task-specs.json` contains every eval task contract and stable task hashes, even for passing tasks. This lets comparison detect eval fixture drift independently from model or harness regressions.

## CLI entrypoint

The real small-model eval suite can now be launched through the installed `metis` console script:

```bash
metis eval real-small-model --workspace . --output-root . --run-name auto
```

Behavior:

- If `METIS_BASE_URL`, `METIS_API_KEY`, or `METIS_MODEL` is missing, the command returns `2`.
- Missing endpoint configuration never produces a fake eval pass.
- If the suite runs and every task passes, the command returns `0`.
- If the suite runs but at least one task fails, the command returns `1`.
- The CLI defaults to `--run-name auto`.
- `auto`, `timestamp`, and `timestamped` resolve to UTC timestamp run names such as `20260525-010203`.

Automatic post-run checks:

```bash
metis eval real-small-model --gate
```

Runs the strict release gate after writing the current eval report. By default, gate artifacts are written to:

```text
docs/evals/runs/<run-name>/gate/
```

```bash
metis eval real-small-model --compare-baseline docs/evals/runs/<baseline>
```

Compares the current run against an explicit baseline. By default, comparison artifacts are written to:

```text
docs/evals/runs/<run-name>/comparison/
```

```bash
metis eval real-small-model --compare-latest
```

Reads the previous `docs/evals/runs/latest.json` before the current run is written, then compares the current run against that previous latest run. If no previous latest pointer exists, the command returns `1` and states that comparison could not be performed.

The checks can be combined:

```bash
metis eval real-small-model --gate --compare-latest
```

The final exit code is `1` if the eval itself fails, the gate fails, or comparison detects a regression.

The CLI writes the same stable artifacts under:

```text
docs/evals/runs/<run-name>/
```

It also writes a latest-run pointer:

```text
docs/evals/runs/latest.json
```

The pointer records:

- latest run name
- latest run directory
- updated timestamp
- success rate
- task count

The run manifest includes:

- suite
- run name
- requested run name
- generated timestamp
- success rate
- task count
- passed count
- failed count
- suite metadata
- failed task ids

## Run comparison

Eval runs can now be compared through:

```bash
metis eval compare --baseline docs/evals/runs/<baseline> --current docs/evals/runs/<current>
```

Comparison profiles:

```bash
metis eval compare \
  --baseline docs/evals/runs/<baseline> \
  --current docs/evals/runs/<current> \
  --profile release
```

Available profiles:

- `release`: default. Blocks task/metric regressions and critical cluster regressions.
- `strict`: blocks task/metric regressions, task spec drift, and any cluster degradation, including noncritical new clusters or count increases.
- `exploratory`: records all diffs but does not return a regression exit code.

Optional outputs:

```bash
metis eval compare \
  --baseline docs/evals/runs/<baseline> \
  --current docs/evals/runs/<current> \
  --output-dir docs/evals/comparisons/<name> \
  --json
```

The comparison reads both run directories:

- `manifest.json`
- `eval-report.json`
- `task-specs.json`
- `failures/clusters.json`
- `failures/remediation-backlog.json`

It reports:

- success rate delta
- regression reasons
- regression reason links
- newly failed tasks
- recovered tasks
- still failed tasks
- new tasks
- removed tasks
- regressed metrics
- task spec drift
- environment drift
- new failure clusters
- resolved failure clusters
- new critical failure clusters
- resolved critical failure clusters
- critical severity upgrades
- severity downgrades
- cluster count increases/decreases
- affected task count increases/decreases
- critical cluster count increases
- critical affected task increases

Regression metrics currently tracked:

- parser failures
- tool failures
- quality failures
- false completion
- final unverified
- duplicate tool calls
- invalid tool calls
- policy blocks
- evidence resolution failures
- schema violations
- schema repair failures
- tool repair failures
- retry budget exhaustions
- pre-dispatch blocks
- trajectory failures

Exit codes:

- `0`: no regression detected.
- `1`: success rate decreased, a previously passing task failed, a tracked negative metric increased, or a new critical failure cluster appeared.

Cluster comparison behavior:

- `new_clusters` and `resolved_clusters` are computed from deterministic cluster keys in `failures/clusters.json`.
- `new_critical_clusters` and `resolved_critical_clusters` are computed from critical backlog entries in `failures/remediation-backlog.json`.
- `critical_severity_upgrades` records shared clusters whose current severity became `critical`.
- `severity_downgrades` records shared clusters whose current severity decreased.
- Older run directories without cluster/backlog files are tolerated and treated as having no cluster findings.
- Noncritical new clusters are reported for triage but do not alone mark the run as a regression.
- New critical clusters always mark the run as a regression because they represent newly introduced schema, retry-budget, evidence, or finalization failure families.
- Critical severity upgrades also mark the run as a regression, even when the cluster key already existed in the baseline.
- Critical cluster count increases mark the run as a regression, because an existing critical failure family has expanded.
- Critical affected task increases mark the run as a regression, because the same critical failure family now damages more eval tasks.
- Noncritical count increases are reported for triage but do not alone mark the run as a regression.

Task spec drift behavior:

- `prompt_changed` records tasks whose prompt hash changed.
- `constraints_changed` records tasks whose non-prompt constraints changed.
- `task_spec_changed` records tasks whose complete task spec changed.
- `missing_baseline_specs` and `missing_current_specs` record task spec availability mismatches.
- `release` reports task spec drift but does not block on it.
- `strict` blocks on task spec drift or missing task spec data.
- `exploratory` records drift without blocking.

Environment drift behavior:

- `suite_changed` records suite name changes.
- `model_changed` records model changes.
- `base_url_changed` records endpoint/base URL changes.
- `profile_changed` records runtime profile changes.
- `task_count_changed` records suite task-count changes.
- `release` reports environment drift but does not block on it.
- `strict` blocks on environment drift.
- `exploratory` records drift without blocking.

Regression reason links:

- `newly_failed_tasks` links to affected task ids and current failure artifacts.
- `regressed_metrics` links to affected task ids, metric deltas, and current failure artifacts when present.
- cluster-related reasons link to cluster keys, affected task ids, and failure artifacts.
- `task_spec_changed` and `task_spec_missing` link to task ids and task-spec drift records.
- `environment_changed` links to changed environment fields and old/new values.

This makes `comparison.json` suitable for automated triage and for generating follow-up repair tickets or diagnosis reports.

When `--output-dir` is provided, comparison writes:

- `comparison.json`
- `comparison.md`
- `diagnosis.json`
- `diagnosis.md`

Diagnosis entries include:

- reason
- task ids
- cluster keys
- artifact paths
- changed fields
- metric deltas
- hash/environment changes
- recommended action

Comparison diagnosis can be turned into repair task stubs:

```bash
metis eval diagnose --comparison docs/evals/runs/<run-name>/comparison
```

The command reads `diagnosis.json`, links cluster reasons to the current run's `failures/remediation-backlog.json` when available, and writes:

- `repair-tasks.json`
- `repair-tasks.md`

Repair task stubs include:

- id
- reason
- priority
- owner area
- affected task ids
- cluster keys
- artifact paths
- timeline paths
- recommended action
- suggested eval
- source remediation backlog items

Repair task stubs can be turned into an ordered repair plan:

```bash
metis eval repair-plan --repair-tasks docs/evals/runs/<run-name>/comparison
```

The command accepts either a `repair-tasks.json` file or a directory containing it. It writes `repair-plan.json` and `repair-plan.md` when `--output-dir` is provided.

Repair plans include:

- priority buckets
- owner-area groups
- execution phases
- next actions
- carried-through task, cluster, recommended action, and suggested eval references

Failed eval runs also export compact per-task timelines:

- `<task>.timeline.json`
- `<task>.timeline.md`

These timelines currently include task start, tool result, error, and task end events. Comparison reason links, diagnosis entries, and repair tasks carry timeline paths when available.

Timelines can be inspected from the CLI:

```bash
metis trace show --timeline docs/evals/runs/<run-name>/failures/<task>.timeline.json
```

Useful variants:

```bash
metis trace show --timeline docs/evals/runs/<run-name>/failures/<task>.timeline.json --json
metis trace show --timeline docs/evals/runs/<run-name>/failures/<task>.timeline.json --include-payload
```

Every timeline event has a stable `event_id`, which is intended to become the anchor for future repair tasks and span-level failure localization.

Runtime results now carry native `trace_events`. Failed eval timelines prefer these runtime events when available. Current runtime event types include:

- `agent.start`
- `model.request`
- `model.response`
- `parser.repair.request`
- `parser.repair.result`
- `tool.request`
- `tool.result`
- `schema.repair_hint`
- `finalization.check`
- `finalization.result`
- `finalization.repair.request`
- `finalization.repair.result`
- `agent.error`

`schema.repair_hint` events are emitted after schema-invalid tool results when actionable hints are available. They carry the parent `tool.result` event id, schema errors, hint text, hint types, typed hint details, tool name, and tool call id. This gives repair tasks and dashboards a stable event-level anchor for analyzing whether a 9B/flash model recovered after receiving a specific schema hint.

Repair tasks now anchor to timeline events when timeline files are available:

- `timeline_event_ids`
- `critical_event_ids`

Critical event selection is deterministic. It currently prioritizes failed finalization events, schema repair hint events, failed tool results, failed parser/finalization repair events, and explicit error events. This means schema repair tasks can point directly to the emitted hint event while still preserving the full timeline for parent tool-result lookup.

Comparison diagnosis now extracts schema repair hint event summaries from linked timelines. Each diagnosis entry can carry `schema_repair_hint_events` grouped by task id, including event id, parent event id, tool name, tool call id, schema errors, hint types, hint text, and typed hint details. Repair tasks preserve the same payload so targeted eval generation can use it without reopening the timeline.

Targeted eval stubs now consume those hint events. Schema repair stubs carry hint types, schema paths, schema keywords, the original hint event payload, and hint-aware gates:

- `min_schema_repair_hint_successes=1`
- `max_schema_repair_hint_failures=0`

Materialized targeted suites preserve this hint metadata so later real-model suites can be generated from concrete hint failure families.

Targeted eval stubs also derive `schema_repair_argument_templates` from typed hint details. These templates contain placeholder malformed and corrected argument objects for common hint types such as missing required properties, unsupported additional properties, and empty arrays. The placeholders are explicit templates, not real model data, and are intended to be replaced or schema-filled before running a real provider eval.

When a template includes `tool_name` and non-empty corrected arguments, targeted eval stubs now generate `required_tool_arguments`. Placeholder values are expressed as conservative `contains` predicates so suite validation can verify the argument names against the tool schema without pretending the placeholder is real business data.

Those placeholders are now schema-compatible for builtin tools. The stub generator reads builtin tool schemas through `ToolRegistry` and `register_builtin_tools()`, resolves fields from `tool_name` plus the schema path leaf, and emits concrete placeholder values such as `outputs/metis-placeholder.txt` for `write_file.path` or a non-empty placeholder array for `run_command.command`. This keeps the generated tasks honest: they remain templates, but their corrected arguments can pass schema-aware suite validation.

Targeted eval prompts now include the same schema repair argument templates. Each prompt-visible template carries the tool name, hint type, schema path, malformed arguments, and corrected arguments. This makes hint-derived evals more usable for 9B/flash models because the model sees the concrete failure shape it must recover from, while the suite still enforces the corrected call through `required_tool_arguments`.

Materialized targeted eval suites now write a top-level `schema_version` of `1`, and the generated Markdown displays the same version. This gives generated repair-regression suites an explicit compatibility marker before more fields, gates, migrations, and runner behaviors are added.

Suite validation now checks supported schema versions, not only the type of the `schema_version` field. Version `1` is currently supported; missing versions remain a warning for legacy compatibility, while unknown declared versions are rejected before the suite runs.

The eval suite schema is now documented in `docs/evals/suite-schema.md`. The document defines version 1 top-level fields, wrapped repair-regression task entries, direct `EvalTaskSpec` entries, required tool argument expectations, schema repair metadata, compatibility rules, migration rules, and release gate expectations.

The runner load path is now version-aware. `load_eval_task_specs()` and generic suite loading both pass through a shared payload normalizer that accepts supported version `1`, keeps legacy unversioned suites compatible, and rejects unknown declared schema versions before task specs are built.

A machine-readable suite schema snapshot now exists at `docs/evals/suite-schema-v1.json`. It captures the version 1 top-level suite object, wrapped repair-regression task entry, direct `EvalTaskSpec` entry, task spec field shapes, required tool argument entries, and Metis metadata such as supported schema versions and predicate keys.

Prompt-visible schema repair argument templates are now sorted and capped. Targeted eval prompts show the highest-priority five templates, report how many templates are shown out of the total, and summarize omitted lower-priority templates as `hint_type@schema_path`. This keeps schema repair context useful for 9B/flash models without letting diagnostic JSON dominate the prompt.

Schema repair placeholder generation now supports custom tool schemas carried by repair tasks or individual hint events. Resolution prefers event-level `tool_schema` or `parameters`, then task-level `tool_schemas[tool_name]`, then builtin tool schemas. This lets targeted eval stubs generate corrected arguments for business-specific tools instead of only Metis builtin tools.

Materialized targeted suites now preserve `tool_schemas` on each wrapped task entry, and suite schema v1 documentation plus the machine-readable JSON snapshot declare that field. Custom business tool schemas therefore survive the repair task -> eval stub -> materialized suite path.

Suite validation now consumes those suite-local `tool_schemas`. If no explicit tool inventory is supplied, schema keys are treated as available tools, and `required_tool_arguments` are checked against the merged schema view. Explicit caller-provided schemas still override suite-local schemas.

Validation reports now include suite schema snapshot metadata: schema id, local snapshot path, and SHA256 for `docs/evals/suite-schema-v1.json`. This makes validation output auditable against the exact machine-readable schema artifact used by the current harness version.

`metis eval run-suite --gate` now refuses unversioned suites. Missing `schema_version` remains a validation warning for legacy compatibility, but release-gated suite runs require a declared supported suite schema version before any provider call is made.

Generic eval run metadata, `manifest.json`, and `latest.json` now record suite schema snapshot metadata. The run artifacts include schema id, local schema path where applicable, and SHA256 for the machine-readable suite schema snapshot.

Independent release gating now requires that manifest evidence by default. `metis eval gate --run <run-dir>` fails if `manifest.json` does not contain `suite_schema_id` and `suite_schema_sha256`, and the gate report renders both values for audit. This prevents old or manually assembled run directories from passing release gating without proving which suite schema contract governed the run.

The built-in `real-small-model` suite is code-defined rather than loaded from a suite JSON file. Its metadata, manifest, and latest pointer now declare `suite_definition_type: code-defined-builtin` and `schema_version: code-defined`, while still recording the current suite schema snapshot id, path, and SHA256. This keeps the real 9B/flash eval path compatible with strict release gating without pretending that the suite came from a file-loaded versioned JSON suite.

Eval run manifests and latest pointers now also expose task contract identity. `task-specs.json`, `manifest.json`, and `latest.json` include `task_contract_hash` plus a per-task `task_spec_hash_summary`. This lets release tooling quickly prove that two runs used the same task contract set before comparing model behavior.

`eval compare` now consumes top-level task contract hashes. Comparison output reports `task_contract_hash_changed`, and the strict profile treats that drift as a regression reason. This prevents model or harness behavior changes from being interpreted before the eval contract itself is verified.

`eval gate` now requires task contract evidence by default. A release-gated run must include `task_contract_hash` and a non-empty `task_spec_hash_summary` in `manifest.json`, in addition to suite schema evidence. The gate report renders the task contract hash and task spec summary count.

Eval run artifacts now include combined provenance. Generic and real-small-model manifests/latest pointers include `provenance` and `provenance_hash`, combining suite identity, schema hash, task contract hash, model endpoint/profile, and tool inventory hash into one auditable run fingerprint.

`eval gate` now validates provenance evidence by default. A release-gated run must include a non-empty provenance payload, a matching `provenance_hash`, and required provenance fields for suite, schema, task contract, model endpoint/profile, and tool inventory.

`eval compare` now reports provenance hash drift. Release and strict comparison profiles treat `provenance_hash_changed` as a regression reason, and the Markdown report includes a `## Provenance Drift` section with changed provenance fields.

`metis eval real-small-model` now writes a pre-run contract before calling the provider. The run directory receives `pre-run-contract.json` and `pre-run-contract.md` containing the code-defined task specs, task hashes, task contract hash, provenance payload, and provenance hash. The CLI resolves `run_name` once so pre-run contract and post-run reports land in the same directory.

`metis eval run-suite` now has the same pre-run contract behavior for loadable generic suites. Before provider calls, the run directory receives `pre-run-contract.json` and `pre-run-contract.md` with suite path, schema version, profile, executable task specs, task hashes, task contract hash, provenance payload, and provenance hash.

`eval gate` now verifies pre-run contract consistency. A release-gated run must include `pre-run-contract.json`, and its provenance hash, task contract hash, and task spec hash summary must match the post-run `manifest.json`.

`eval compare` now reports pre-run/post-run contract mismatches. Release and strict comparison profiles treat `pre_run_post_run_mismatch` as a regression reason when a run has `pre-run-contract.json` but its provenance hash, task contract hash, or task spec hash summary differs from `manifest.json`.

Run manifests and latest pointers now anchor the pre-run contract artifact directly. Both real-small-model and generic run-suite paths write `pre_run_contract_path`, `pre_run_contract_sha256`, and `pre_run_provenance_hash`. `eval gate` verifies those fields against the actual `pre-run-contract.json` file before release.

`eval compare` now verifies the same pre-run contract artifact anchor. If a manifest declares a stale or incorrect `pre_run_contract_path`, `pre_run_contract_sha256`, or `pre_run_provenance_hash`, release and strict comparison profiles report `pre_run_post_run_mismatch`.

Failed timelines now include run-level provenance anchors. Real-small-model and generic run-suite report writers annotate each failed task timeline with `run_metadata`, including the pre-run contract path, pre-run contract SHA256, pre-run provenance hash, post-run provenance hash, task contract hash, and suite schema hash. `metis trace show` renders these anchors in Markdown.

Diagnosis entries and repair tasks now inherit timeline run metadata. When comparison diagnosis reads failed-task timelines, it copies `run_metadata` into `diagnosis.json` and downstream `repair-tasks.json`, so automated repair work can see the pre-run contract anchor without reopening trace files.

Targeted eval stubs and materialized targeted suites now preserve repair task `run_metadata`. Generated regression samples retain the original failure run's pre-run contract/provenance anchor through the full diagnosis -> repair task -> eval stub -> materialized suite chain.

Eval report writers now emit run-level artifact attestations. Each real-small-model and generic run-suite run writes `run-attestation.json` and `run-attestation.md`, listing run artifacts as in-toto-style subjects with SHA256 digests and sizes. The attestation predicate records suite, run name, task contract hash, provenance hash, and pre-run contract anchors.

`eval gate` now verifies run-level artifact attestation evidence by default. A release-gated run must include `run-attestation.json`; each subject file must exist; each subject SHA256 and size must match the current bytes on disk; `manifest.json`, `eval-report.json`, and `task-specs.json` must be covered. This turns the run directory into a locally verifiable artifact bundle before comparison, dashboard upload, or downstream repair generation.

`eval compare` now evaluates run attestation trust before interpreting release/strict regressions. If one side has `run-attestation.json` and the other side is missing it, or if either attestation no longer matches the local artifact bytes, compare records `attestation_diff` and release/strict profiles emit `attestation_untrusted`. Legacy comparisons where both sides lack attestation remain compatible, but mixed or tampered bundles are treated as unauditable.

Comparison output now also includes top-level `baseline_untrusted` and `current_untrusted` booleans. CI, dashboards, and repair agents can use those fields directly instead of parsing attestation failure text.

Comparison diagnosis and repair tasks now preserve attestation trust state. `attestation_untrusted` entries carry `trust_state` with baseline/current untrusted booleans and side-specific failures, and repair tasks route this reason to `artifact-integrity-and-provenance` with critical priority. This keeps artifact repair separate from model-behavior repair.

Repair plans now add a `phase-0-restore-artifact-trust` precondition phase whenever artifact integrity tasks are present. This phase asks the repair loop to restore trusted run bundles before interpreting model behavior, metrics, or regression deltas.

Targeted eval stubs now distinguish artifact verification from model-behavior regression. `attestation_untrusted` repair tasks produce `stub_type=artifact_verification` with `requires_model_execution=false`, empty `allowed_tools`, preserved `trust_state`, side-specific `target_runs`, and a `run_attestation_verifies` quality gate. Materialized suites preserve that fixture metadata so a deterministic verifier can handle it without spending provider calls.

Generic eval execution now honors `requires_model_execution=false`. `EvalRunner` bypasses provider calls for `fixture_type=artifact_verification` and verifies `run-attestation.json` against target run directories. `metis eval run-suite` only requires provider environment variables when at least one suite task needs model execution, so all-artifact verification suites can run offline without fake model results.

Deterministic fixture results now persist quality gate result metadata. `EvalResult` includes `quality_gate_results`, and eval reports render a `## Quality Gate Results` section. Artifact verification fixtures record the `run_attestation_verifies` gate name, pass/fail state, message, and target run metadata so dashboards and repair agents do not have to parse error text.

Model-behavior evals now persist the same quality gate result metadata. Gate results are included in `eval-report.json`, rendered in `eval-report.md`, copied into failed-task artifacts, and emitted as `quality.gate` events in failure timelines. This makes quality gates traceable evidence rather than only aggregate failure counts.

Repair tasks also include `likely_source_modules`. This is a deterministic source-localization hint derived from reason, cluster keys, metrics, and remediation owner area. Repair plans aggregate those module hints by owner area together with critical event ids.

Repair tasks can also generate targeted eval stubs:

```bash
metis eval eval-stubs --repair-tasks docs/evals/runs/<run-name>/comparison
```

Useful variants:

```bash
metis eval eval-stubs --repair-tasks docs/evals/runs/<run-name>/comparison --output-dir docs/evals/runs/<run-name>/comparison/eval-stubs
metis eval eval-stubs --repair-tasks docs/evals/runs/<run-name>/comparison --json
```

The command writes:

- `targeted-eval-stubs.json`
- `targeted-eval-stubs.md`

Each stub carries source repair task id, critical event ids, likely source modules, suggested assertion, verification command, and an eval task spec skeleton.

Automatic comparison through the real small-model suite also accepts the profile:

```bash
metis eval real-small-model --compare-latest --compare-profile release
```

This keeps CI/release usage strict enough to protect trust while still allowing exploratory analysis runs that collect evidence without blocking.

## Release gate

Eval runs can now be checked with a strict release gate:

```bash
metis eval gate --run docs/evals/runs/<run-name>
```

Optional output:

```bash
metis eval gate \
  --run docs/evals/runs/<run-name> \
  --output-dir docs/evals/gates/<name> \
  --json
```

Default thresholds:

- `--min-success-rate 1.0`
- `--max-failed-tasks 0`
- `--max-invalid-tool-calls 0`
- `--max-schema-violations 0`
- `--max-retry-budget-exhaustions 0`
- `--max-pre-dispatch-blocks 0`
- `--max-trajectory-failures 0`
- `--max-failure-clusters 0`
- `--max-critical-remediations 0`

Gate outputs:

- `gate.json`
- `gate.md`

Exit codes:

- `0`: gate passed.
- `1`: gate failed.

Cluster-aware gate behavior:

- `failure_clusters` is read from `failures/clusters.json`.
- `critical_remediations` is read from `failures/remediation-backlog.json`.
- Older run directories without cluster files are tolerated and treated as zero cluster findings.
- New real eval runs produce these files automatically through `EvalSuiteResult.write_reports()`.

This means a run can be blocked not only by failed tasks or schema violations, but also by critical failure families discovered from structured artifacts.

## Failure-only report section

`eval-report.md` now appends:

```text
## Failure Details
```

When all tasks pass, this section contains:

```text
- None
```

When tasks fail, each failing task gets a dedicated section with:

- status
- turns used
- tool calls
- parser failures
- tool failures
- quality failures
- invalid tool calls
- schema violations
- retry budget exhaustions
- pre-dispatch blocks
- trajectory failures
- tool failure types
- failure shape keys
- errors

This keeps the full metric table intact while making failed real endpoint runs faster to debug.

## Failure artifacts

`EvalSuiteResult.write_reports()` now writes structured failure artifacts under:

```text
failures/
```

The failure index is always written:

```text
failures/index.json
```

When all tasks pass:

```json
{
  "failure_count": 0,
  "artifacts": []
}
```

When tasks fail, each failing task gets one JSON artifact:

```text
failures/<safe-task-id>.json
```

Each failure artifact includes:

- task id
- status
- turns used
- tool calls
- latency
- task spec metadata when the failure came from an `EvalRunner.run_suite()` task
- core metrics
- tool repair metrics by type
- tool failure types
- failure shape keys
- compact tool result excerpts
- errors

Task spec metadata includes:

- prompt
- allowed tools
- max turns
- expected artifacts
- required evidence sources
- quality gates
- verified-final requirement
- required tools
- forbidden tools
- required tool order
- required tool arguments
- schema, policy, evidence, retry, pre-dispatch, and failure-shape thresholds

Failure artifacts also include stable task-spec hashes when task metadata is available:

- `prompt_hash`
- `constraints_hash`
- `task_spec_hash`

These hashes make baseline comparisons auditable. If a task changed between two runs, a regression can be separated from a real model/harness behavior change.

Failure artifacts include `run_metadata` copied from the eval suite metadata, such as suite, model, base URL, and runtime profile when available.

These JSON files are intended for automated diagnosis, regression clustering, and later small-model behavior repair datasets.

Tool result excerpts include up to the first 20 tool results in compact form:

- index
- tool name
- tool call id
- status
- failed flag
- selected failure metadata
- content preview
- error preview

Selected metadata includes failure type, recoverability, retry flags, pre-dispatch blocking, schema validity, schema errors, failure shape key, policy decision, and repair instruction when present.

Failure clustering now consumes task spec and tool excerpt signals:

- exact schema validation errors become `schema_error:*` clusters
- missing required tools become task-constraint clusters
- forbidden tool use becomes task-constraint clusters
- broken required tool order becomes task-constraint clusters
- missing required tool arguments become task-constraint clusters
- tool policy decisions become policy-decision clusters

## Failure clustering

Failure artifacts are now clustered automatically after report writing.

Outputs:

- `failures/clusters.json`
- `failures/clusters.md`

Current deterministic cluster dimensions:

- tool failure type
- failure shape key
- trajectory failure
- schema failure
- retry budget failure
- evidence resolution failure
- unverified finalization
- unknown failure fallback

Each cluster includes:

- cluster key
- count
- task ids
- signals
- deterministic remediation guidance

Example remediation categories:

- schema failures: tighten tool schema feedback and add argument examples
- retry budget failures: improve failure lineage blocking and task-specific recovery hints
- command failures: add safer command templates and recovery-specific tool feedback
- evidence failures: improve evidence ref propagation and finalization instructions
- trajectory failures: review oracle gates, required tool order, and prompt constraints

## Remediation backlog

Failure clusters now generate a deterministic remediation backlog:

```text
failures/remediation-backlog.json
failures/remediation-backlog.md
```

Each backlog item includes:

- id
- cluster key
- severity
- owner area
- affected task ids
- recommended action
- suggested eval
- signals

Current severity rules:

- critical:
  - schema failures
  - retry budget failures
  - evidence resolution failures
  - unverified finalization
- high:
  - trajectory failures
  - repeated failure shapes
  - clusters with count >= 3
- medium:
  - other deterministic failure clusters

Current owner areas:

- `tool-schema-and-repair`
- `runtime-lineage-and-recovery`
- `evidence-and-finalization`
- `tool-command-execution`
- `eval-oracles-and-prompts`
- `harness-runtime`

Recorded command:

```bash
python -m pytest -q -m network
```

Latest local run in this work session: `1 passed, 58 deselected`.

Latest suite definition check in this work session:

```bash
python -m pytest -q tests\e2e\test_local_9b_eval.py
```

Result after failure clustering, failure artifacts, failure-only report, release gate, eval run comparison, timestamped run names, latest pointer, CLI, manifest, stable run artifacts, and verified read/write evidence expansion: `30 passed` for eval failure/report focused tests.

No API key is stored in this repository.

## Targeted eval suite materialization

Repair tasks can now move beyond human-readable stubs into loadable eval suites.

Workflow:

```bash
metis eval eval-stubs --repair-tasks docs/evals/runs/<run-name>/comparison --output-dir docs/evals/runs/<run-name>/comparison/eval-stubs
metis eval materialize-stubs --stubs docs/evals/runs/<run-name>/comparison/eval-stubs --output-dir docs/evals/runs/<run-name>/comparison/targeted-suite
```

Generated files:

- `targeted-eval-stubs.json`
- `targeted-eval-stubs.md`
- `targeted-eval-suite.json`
- `targeted-eval-suite.md`

The materialized suite preserves repair provenance:

- source repair task id
- reason
- priority
- owner area
- cluster keys
- critical event ids
- likely source modules
- suggested assertion
- verification command

It also carries the executable `EvalTaskSpec` payload under `task_spec`, so code can load the suite using `load_eval_task_specs(path)`.

This turns a failed run into a reusable regression asset:

```text
failure artifact -> timeline -> diagnosis -> repair task -> eval stub -> targeted eval suite -> EvalTaskSpec
```

The next missing piece is a generic CLI runner for arbitrary suite JSON, so `targeted-eval-suite.json` can be run directly against any configured model/provider pair.

## Generic suite runner

Arbitrary loadable eval suites can now be executed against the configured OpenAI-compatible provider:

```bash
metis eval run-suite --suite docs/evals/runs/<run-name>/comparison/targeted-suite --workspace . --output-root . --run-name auto --profile small
```

Optional gate:

```bash
metis eval run-suite --suite docs/evals/runs/<run-name>/comparison/targeted-suite --gate
```

The command requires a real endpoint:

- `METIS_BASE_URL`
- `METIS_API_KEY`
- `METIS_MODEL`

If those variables are missing, the command exits without running and explicitly states that no model result was faked.

The generic runner writes the same artifact shape as the built-in real-small-model suite:

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

This closes the current repair-to-regression execution loop:

```text
comparison -> diagnosis -> repair tasks -> eval stubs -> materialized suite -> run-suite -> report/gate/failures
```

Same-command baseline comparison is now supported:

```bash
metis eval run-suite --suite <suite> --compare-baseline <run-dir>
metis eval run-suite --suite <suite> --compare-latest
metis eval run-suite --suite <suite> --compare-profile strict
```

`--compare-latest` reads the previous `docs/evals/runs/latest.json` before the current run writes a new latest pointer. This preserves the correct baseline for automatic regression checks.

Default comparison output:

```text
<current-run>/comparison
```

Comparison output files:

- `comparison.json`
- `comparison.md`
- `diagnosis.json`
- `diagnosis.md`

If comparison detects a regression, the command exits non-zero.

Suite schema validation is now available before model calls:

```bash
metis eval validate-suite --suite <suite-json-or-dir>
metis eval validate-suite --suite <suite-json-or-dir> --json
metis eval validate-suite --suite <suite-json-or-dir> --output-dir <validation-dir>
```

`run-suite` now validates first. If validation fails:

- no endpoint environment check is performed;
- no model call is made;
- the validation markdown is printed;
- the command exits non-zero.

Validation output files:

- `suite-validation.json`
- `suite-validation.md`

Core validation checks:

- non-empty task list
- string `schema_version` when present
- unique non-empty task ids
- non-empty prompts
- list/dict/bool/integer field types
- non-negative integer thresholds
- `max_turns >= 1`
- valid `required_tool_arguments` object shape
- warnings for unknown `EvalTaskSpec` fields that would be ignored by the loader
- UTF-8 JSON files with BOM are accepted, which helps Windows-authored suite files validate normally

Registry-aware validation is now enabled for generic suite execution.

`validate-suite` accepts a workspace:

```bash
metis eval validate-suite --suite <suite-json-or-dir> --workspace <workspace>
```

The workspace is used to build the active built-in tool registry. The validator now checks tool references in:

- `allowed_tools`
- `required_tools`
- `forbidden_tools`
- `required_tool_order`
- `required_tool_arguments[*].tool`
- `required_tool_arguments[*].tool_name`

It also checks `quality_gates` against the default quality gate registry.

`run-suite` uses the same registry-aware validation before endpoint checks and model calls.

Inventory visibility is now available:

```bash
metis eval list-tools --workspace <workspace>
metis eval list-tools --workspace <workspace> --json
metis eval list-quality-gates
metis eval list-quality-gates --json
```

Tool inventory includes:

- name
- description
- category
- side effect
- permission requirement
- retry policy
- verification label
- metadata
- full parameter schema

Quality gate inventory includes:

- name
- description
- failure policy
- metadata

The next missing eval-chain gap is predicate-vs-tool-schema validation: `required_tool_arguments` should be checked against the referenced tool's JSON schema before model calls.
