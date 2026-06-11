# Implementation Plan: MVP-2D v0.5 Residual Servo BC Proof Slice

Date: 2026-06-11

## Requirements Summary

Implement `v0_5` as a fresh MVP-2D proof slice that can honestly close MVP-2
only if actual Isaac accepted success traces produce a curated candidate policy
that beats an uncurated baseline policy on fresh held-out scenarios.

Primary source:

- `docs/superpowers/specs/2026-06-11-mvp2d-v05-residual-servo-bc-design.md`

Planning artifacts:

- `.omx/context/mvp2d-v05-residual-servo-bc-20260611T062138Z.md`
- `.omx/plans/prd-mvp2d-v05-residual-servo-bc.md`
- `.omx/plans/test-spec-mvp2d-v05-residual-servo-bc.md`

## RALPLAN-DR Summary

### Principles

1. Preserve proof integrity over speed of closure.
2. Hold trainer/hyperparameter/trace-count fairness constant across baseline and
   candidate.
3. Burned held-out ranges remain diagnostic only.
4. Actual Isaac runtime evidence is required for closure.
5. Fail closed before held-out when train-generation quality is insufficient.

### Decision Drivers

1. MVP-2 Closed requires positive held-out uplift, not just oracle success.
2. `v0_3` and `v0_4` tied at `3/20`, so candidate must better use curated data.
3. Held-out one-shot integrity requires all selector/trainer decisions before
   `18000-18019` is evaluated.

### Viable Options

#### Option A: Fair Residual Servo BC

Use a weak geometric base servo plus learned residual with identical trainer and
hyperparameters for baseline/candidate. Dataset view is the only intentional
difference.

Pros:

- Cleanest claim: curation view caused the difference.
- Fits Isaac geometry-heavy task.
- Keeps implementation bounded to current MVP-2C runner/evaluator.

Cons:

- May still fail to produce uplift if residual signal is too weak.
- Requires careful train-view fairness tests.

#### Option B: Stronger Calibration Selector

Keep current trainer but widen calibration adapter selection.

Pros:

- Smaller trainer change.
- May improve both policies' physical feasibility.

Cons:

- `v0_4` already suggests shared adapter improvements do not separate candidate
  from baseline.
- Claim may shift from dataset curation to adapter tuning.

#### Option C: Candidate Near-success Expansion

Add near-success traces to candidate training material.

Pros:

- More training data.
- Higher chance of learning stable correction.

Cons:

- Weakens accepted-only evidence.
- Requires new near-success taxonomy and relabeling boundaries.

Recommendation: Option A.

## Implementation Steps

### 1. Add RED Tests for v0_5 Manifest and Gates

Files:

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Add tests for:

- `v0_5` manifest version and seed ranges.
- burned range exclusion.
- success trace count min `20` and cap `40`.
- held-out not scheduled when train-generation gate fails.
- top-level close remains false without `actual_isaac_success_trace_count >= 20`.
- `--train-generation-probe-only --clean --scenario-profile v0_5` is
  self-contained and writes required setup artifacts before reading them.
- `base_servo_only_diagnostic` exists and is explicitly non-closing.

Relevant code anchors:

- `scripts/run_mvp2c_isaac_training_calibration.py:63`
- `scripts/run_mvp2c_isaac_training_calibration.py:206`
- `scripts/run_mvp2c_isaac_training_calibration.py:248`
- `scripts/run_mvp2c_isaac_training_calibration.py:1810`

### 2. Add v0_5 Scenario Profile and Generator Hash Fields

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Implement:

- `SCENARIO_MANIFEST_VERSION_V05`.
- `_scenario_seed_ranges("v0_5")`.
- `_manifest_version_for_profile("v0_5")`.
- `_excluded_prior_heldout_seed_ranges("v0_5")`.
- CLI choices include `v0_5`.
- generator config hash includes:
  - train-generation seed order
  - success trace minimum/cap
  - residual trainer id
  - weak base servo config hash
  - residual target definition
  - baseline mix and failure taxonomy
  - base-servo-only diagnostic config

Also make the train-generation probe mode self-contained for `v0_5`: when
`--train-generation-probe-only --clean` is used, the runner must create or
refresh `scenario_manifest.json`, `selected_action_adapter.json`, and any
required config hashes before reading them.

### 3. Implement Fair Dataset View Builder

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Implement helpers to derive:

- candidate accepted-only trace set, `20 <= N <= 40`;
- baseline `N` trace view with 60/40 accepted/rejected-noisy mix;
- explicit trace-count equality report;
- exact 60/40 rounding:
  `accepted_count=floor(N*0.60)`,
  `rejected_noisy_count=N-accepted_count`;
- rejected/noisy failure-bucket selection in lexical cycle order:
  `lateral_offset`, `stability_window_loss`, `under_insertion`;
- rejection of candidate near-success/rejected/synthetic/oracle-relabeled rows.

Replace or bypass the current replay-weight-only candidate material path around
`scripts/run_mvp2c_isaac_training_calibration.py:1000` for `v0_5`.

### 4. Add Phase-conditioned Residual Servo BC

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Implement trainer family:

```text
phase_conditioned_residual_servo_bc
```

Required behavior:

- compute weak base servo action from task-state features;
- train residual label as `actual_trace_action - weak_base_servo_action`;
- store policy artifact metadata proving same trainer/hyperparameters/features
  for baseline and candidate;
- store machine-verifiable equality hashes for trainer hyperparameters, feature
  schema, phase input schema, weak base servo config, and selected calibration
  config;
- during inference, output `weak_base_servo_action + learned_residual`, then pass
  through the selected shared runtime adapter.

Keep legacy trainer behavior for earlier profiles unless tests justify a shared
safe extraction.

### 5. Add Shared Calibration Feasibility Selector

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Implement:

- pre-registered residual servo gain/clip candidate list;
- selector score `shared_stability_feasibility_score`;
- selected config shared by baseline/candidate;
- held-out leakage guard against trace paths, rollout JSON, and held-out metrics.

Do not use candidate-baseline uplift as selector objective.

### 6. Wire Held-out Evaluator to Residual Servo Policy Artifacts

Files:

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

Add evaluator support for `phase_conditioned_residual_servo_bc` policy artifacts
without breaking existing linear/ridge BC artifacts.

Relevant anchor:

- `scripts/run_mvp2b_isaac_proof_evaluator.py:982`

### 7. Add Report, Plot, and Fail-closed Evidence

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`
- `docs/developer/debugging_guide.md`
- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

Report:

- `scenario_profile=v0_5`
- `actual_isaac_success_trace_count`
- `actual_isaac_success_trace_cap`
- `trace_count_equal`
- baseline/candidate trace and transition counts
- residual trainer metadata
- selected calibration config hash
- close blockers
- non-claims
- representative plot artifact paths
- `base_servo_only_diagnostic` with success rate or skipped status

Plot:

- use a lightweight existing plotting path if available;
- if plotting dependency is unavailable, emit JSON/CSV trace data and record
  `plot_generation_status=skipped_dependency_unavailable` without setting
  `mvp2_closed=true` from plot status alone.

Base-servo-only diagnostic:

- run on train/calibration diagnostic material only;
- never read held-out success metrics before held-out freeze;
- never set `mvp2_closed=true`;
- explain whether the weak shared base servo is already strong enough to solve
  the task without learned residuals.

Post-held-out guard:

- if `18000-18019` has been evaluated, any rerun/tuning marker for trainer,
  selector, threshold, action scale, or baseline mix must force `v0_5`
  fail-closed and require a fresh `v0_6`.

### 8. Run Verification in the Safe Order

Commands:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2d-v05-skip \
  --clean \
  --scenario-profile v0_5 \
  --skip-isaac \
  --pretty

uv run python -m compileall -q \
  scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py

uvx ruff check \
  scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py

git diff --check
```

Actual Isaac sequence:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2d-v05-train-gate \
  --clean \
  --scenario-profile v0_5 \
  --train-generation-probe-only \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

If accepted success trace count is below `20`, stop and document fail-closed
without running held-out.

Only after train-generation passes:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2d-v05-full-proof \
  --clean \
  --scenario-profile v0_5 \
  --rollouts-per-policy 20 \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --action-scale 1.0 \
  --pretty
```

## Risks and Mitigations

- Risk: `16000-16159` yields fewer than 20 accepted success traces.
  Mitigation: fail closed before held-out; do not burn `18000-18019`.
- Risk: residual servo improves both baseline and candidate equally.
  Mitigation: preserve the result honestly; if tied, `v0_5` fails and `v0_6`
  must be pre-registered.
- Risk: shared weak base servo alone solves the task, weakening the curation
  claim.
  Mitigation: emit non-closing base-servo-only diagnostic and report it
  separately from closure.
- Risk: selector accidentally optimizes candidate uplift.
  Mitigation: use shared feasibility score and tests that reject held-out access.
- Risk: residual trainer becomes a candidate-only advantage.
  Mitigation: artifact equality tests for trainer family, hyperparameters,
  feature schema, phase input, and selected config.
- Risk: report prose says artifacts are equal but hashes disagree.
  Mitigation: make equality machine-verifiable through hashes and fail closure
  on mismatch.
- Risk: plot generation adds dependency churn.
  Mitigation: prefer existing dependencies; otherwise emit trace JSON/CSV and
  record plot gap separately from closure.

## ADR

### Decision

Implement `v0_5` using fair phase-conditioned residual servo BC with a weak
shared geometric base servo and dataset-view-only baseline/candidate difference.

### Drivers

- `v0_3` and `v0_4` tied, so current trainer/adapter path is not separating
  curated candidate from uncurated baseline.
- MVP-2 claim must remain dataset curation value, not candidate-only trainer or
  adapter superiority.
- Actual Isaac train-generation is now viable enough to build accepted success
  traces before held-out.

### Alternatives considered

- Stronger shared calibration selector: rejected as insufficient after `v0_4`
  and likely to shift emphasis to adapter choice.
- Candidate near-success expansion: rejected because it weakens accepted-only
  actual evidence.
- Candidate-only stronger trainer: rejected because it changes the claim.

### Why chosen

Residual servo BC is the smallest trainer change that can make accepted success
traces matter while keeping trainer/hyperparameter fairness intact.

### Consequences

- More tests are needed around policy artifact equality and data-view fairness.
- If residual servo still ties baseline/candidate, MVP-2 remains open.
- `v0_5` held-out can only be used once.

### Follow-ups

- If `v0_5` closes, prepare public-facing evidence separately with 50+ rollouts.
- If `v0_5` fails before held-out, debug train-generation without burning
  `18000-18019`.
- If `v0_5` fails after held-out, create a new pre-registered `v0_6`.

## Available-Agent-Types Roster

- `explore`: codebase symbol/file mapping.
- `architect`: architecture review and boundary risks.
- `critic`: plan/testability/proof-integrity review.
- `executor`: implementation.
- `test-engineer`: focused TDD and verification.
- `verifier`: final evidence audit.
- `writer`: docs, handoff, worklog updates.

## Follow-up Staffing Guidance

Default follow-up: `$ultragoal`.

Suggested lanes:

- `executor` / medium reasoning: implement `v0_5` runner and residual trainer.
- `test-engineer` / medium reasoning: write RED tests for manifest, gates,
  train-view fairness, selector leakage, and closure derivation.
- `verifier` / high reasoning: audit final actual Isaac evidence and ensure
  no burned held-out reuse.
- `writer` / medium reasoning: update worklog, debugging guide, todo, and
  handoff.

For parallel delivery, use `$ultragoal` as durable owner and `$team` for
independent test/implementation/docs lanes.

## Goal-Mode Follow-up Suggestions

- `$ultragoal`: recommended default for durable sequential implementation and
  evidence checkpointing.
- `$team`: useful alongside `$ultragoal` if implementation is split into tests,
  runner, evaluator, and docs lanes.
- `$autoresearch-goal`: not recommended for this step; research decisions are
  already captured in the spec.
- `$performance-goal`: not applicable unless runtime speed becomes the primary
  bottleneck.
- `$ralph`: explicit fallback only if a single-owner persistent fix loop is
  intentionally selected.

## Team Launch Hints

```text
$team implement docs/superpowers/plans/2026-06-11-mvp2d-v05-residual-servo-bc.md
```

Team verification path:

- test lane proves RED/GREEN focused tests;
- runner lane proves deterministic/skip path;
- evaluator lane proves residual policy artifact compatibility;
- docs lane proves worklog/handoff/debugging guide updates;
- leader runs actual Isaac train-generation and held-out only after local gates
  pass.

## Consensus Changelog

- Initial planner draft created from the approved v0_5 spec.
- Architect review approved the plan and required two pre-execution
  improvements: self-contained train-generation probe setup and a non-closing
  base-servo-only diagnostic. Both were added to the PRD, test spec, and
  implementation plan.
- Critic review approved the plan and recommended non-blocking hardening:
  explicit 60/40 rounding, machine-verifiable equality hashes, and a strict
  post-held-out rerun/tuning fail-closed marker. These were added to the PRD,
  test spec, and implementation plan.
