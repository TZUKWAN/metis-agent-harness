# Iteration 039 - Compare Profiles

Date: 2026-05-25

## Objective

Make eval run comparison support multiple blocking policies instead of a single hard-coded regression rule.

The harness needs different behavior in different phases:

- exploratory research needs complete diffs without blocking;
- release gates need critical reliability protection;
- strict harness hardening needs every cluster degradation to fail fast.

## Implemented

1. `compare_eval_runs()` now accepts:
   - `profile="release"`
   - `profile="strict"`
   - `profile="exploratory"`

2. Comparison output now includes:
   - `profile`
   - `regression_reasons`

3. `release` profile behavior:
   - blocks success rate decrease
   - blocks newly failed tasks
   - blocks regressed scalar metrics
   - blocks new critical clusters
   - blocks critical severity upgrades
   - blocks critical cluster count increases
   - blocks critical affected task increases

4. `strict` profile behavior:
   - blocks all release-profile regressions
   - blocks any new cluster
   - blocks any severity upgrade
   - blocks any cluster count increase
   - blocks any affected task count increase

5. `exploratory` profile behavior:
   - records all task, metric, and cluster diffs
   - leaves `has_regression=False`
   - returns CLI exit code `0` unless another command-level failure happens

6. CLI additions:
   - `metis eval compare --profile strict|release|exploratory`
   - `metis eval real-small-model --compare-profile strict|release|exploratory`

## Design Rationale

Hard-coded regression behavior is too blunt for a reusable harness.

For CI, the default should remain protective: release should fail when critical reliability, evidence, repair, or finalization families regress. For development, strict mode is useful because any newly discovered failure family may deserve immediate attention. For research, exploratory mode lets the team run comparisons on unstable suites without turning every known issue into a failed automation step.

This keeps the comparison artifact identical across modes while only changing the blocking decision.

## External Calibration

Recent agent evaluation guidance consistently emphasizes fixed baselines, CI gates, and failure-mode tracking:

- Agent Patterns describes eval harnesses as fixed scenario sets with scoring, baseline comparison, reports, and CI gates.
- Braintrust's agent evaluation guidance emphasizes metrics across multi-step workflows and regression gates.
- Corbell's failure-driven eval automation emphasizes clustering production failures into meaningful patterns and turning them into eval coverage.

This iteration maps those patterns into Metis by making baseline comparison policy explicit and configurable.

## Validation

Targeted tests:

```bash
python -m pytest -q tests\unit\test_eval_compare.py
python -m pytest -q tests\unit\test_cli_eval.py
```

Result:

```text
11 passed
13 passed
```

Compile check:

```bash
python -m compileall -q metis
```

Result: passed.

## Next Work

1. Enrich failure artifacts with task spec metadata:
   - prompt
   - required tools
   - forbidden tools
   - required evidence sources
   - quality gates

2. Add compact tool-result excerpts for failed tasks.

3. Persist provider/model/run environment metadata into failure artifacts and comparison summaries.

4. Add trace timeline export so every comparison regression can link to the failing turn, tool call, and finalization check.
