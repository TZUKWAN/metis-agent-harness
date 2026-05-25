# Iteration 134 - Repair Plan Precondition Metadata

Date: 2026-05-25

## Problem

Iterations 113 and 133 introduced repair-plan precondition phases:

- `phase-0-restore-artifact-trust`
- `phase-0b-repair-suite-hygiene`

Those phases were correctly ordered, but the plan structure did not yet tell downstream automation that they were hard preconditions. A dashboard, CLI executor, or future repair agent could infer the order from phase ids, but inference is brittle. The repair plan should be machine-readable.

For a reusable harness, phase metadata must separate:

1. precondition repair;
2. model behavior repair;
3. verification coverage;
4. owner-area stabilization.

This matters for 9B models because small models should not decide from prose whether a dirty artifact bundle or invalid suite contract blocks behavior repair. The harness should provide that control signal explicitly.

## Implementation

Repair-plan phases now include:

- `phase_type`
- `hard_precondition`
- `blocks`
- `requires_completed_preconditions`

Precondition phases are marked as:

```json
{
  "phase_type": "precondition",
  "hard_precondition": true
}
```

`phase-0-restore-artifact-trust` blocks:

- `comparison_interpretation`
- `model_behavior_repair`
- `targeted_eval_generation`

`phase-0b-repair-suite-hygiene` blocks:

- `model_behavior_repair`
- `targeted_eval_generation`
- `release_decision`

Ordinary phases are typed as:

- `phase-1-stop-release-blockers`: `repair`
- `phase-2-add-targeted-evals`: `verification`
- `phase-3-stabilize-owners`: `stabilization`

`_annotate_repair_phase_dependencies()` walks the phase list and records which hard preconditions must be completed before each phase can run.

Example when both preconditions exist:

```json
[
  {
    "id": "phase-0-restore-artifact-trust",
    "requires_completed_preconditions": []
  },
  {
    "id": "phase-0b-repair-suite-hygiene",
    "requires_completed_preconditions": ["phase-0-restore-artifact-trust"]
  },
  {
    "id": "phase-1-stop-release-blockers",
    "requires_completed_preconditions": [
      "phase-0-restore-artifact-trust",
      "phase-0b-repair-suite-hygiene"
    ]
  }
]
```

The Markdown renderer now prints the same metadata for human review.

## Harness Impact

This change turns repair plans from ordered prose into executable control metadata.

Downstream automation can now:

1. detect hard preconditions without parsing ids;
2. block model behavior repair until artifact trust and suite hygiene are restored;
3. explain why a phase is not executable yet;
4. display precondition chains in dashboards;
5. route small-model repair attempts away from ambiguous or contaminated inputs.

This is a harness-level improvement, not a scenario-specific feature. Any future agent built on Metis benefits from the same precondition discipline.

## Tests

Focused validation:

```powershell
python -m pytest tests\unit\test_eval_compare.py -q
```

Result:

```text
56 passed
```

New assertions verify:

1. artifact trust phase is a hard precondition;
2. suite hygiene phase is a hard precondition;
3. release-blocker and targeted-eval phases declare required completed preconditions;
4. artifact trust precedes suite hygiene in dependency metadata;
5. Markdown renders the hard precondition field.

## Remaining Work

1. Add CLI enforcement that refuses to execute behavior repair before hard preconditions complete.
2. Add dashboard rendering for precondition chains.
3. Add status fields for each phase: `open`, `in_progress`, `blocked`, `complete`, `verified`.
4. Add repair-plan attestation so phase metadata is tamper-evident.
