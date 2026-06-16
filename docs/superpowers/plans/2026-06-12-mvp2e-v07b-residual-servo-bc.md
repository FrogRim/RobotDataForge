# MVP-2E v0.7b Residual Servo BC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` or `superpowers:subagent-driven-development` to
> implement this plan task-by-task. This is a planning artifact only. Do not
> execute implementation until the user explicitly approves a follow-up
> execution lane.

**Goal:** Implement `v0_7b`, a residual servo BC policy slice where baseline and
candidate share the same frozen base geometry servo and learn only residuals.

**Source spec:**
`docs/superpowers/specs/2026-06-12-mvp2e-v07b-residual-servo-bc-design.md`

**Context snapshot:**
`.omx/context/mvp2e-v07b-residual-servo-bc-20260612T084507Z.md`

---

## RALPLAN-DR Summary

### Principles

1. Env-native success mask and stable window remain the only closure authority.
2. Baseline/candidate fairness is stronger than raw performance: same base servo,
   adapter, trainer, feature schema, hyperparameters, and clipping.
3. Residual learning must preserve attribution: dataset view is the only A/B
   difference.
4. Closed-loop recovery data is allowed only as shared train overlay or
   calibration diagnostic, never as held-out-derived tuning.
5. Fail closed before Isaac when offline artifacts cannot prove the contract.

### Decision Drivers

1. `v0_7a_2` passed offline fit but failed actual Isaac Phase E `0/5`; the next
   blocker is policy class / closed-loop transfer.
2. Existing code already has residual servo primitives in the evaluator and
   `v0_5` training slice, so this should extend existing patterns rather than
   introduce a new trainer framework.
3. MVP-2 claim integrity requires preventing base servo, recovery data, or
   calibration selection from becoming hidden candidate-only advantages.

### Viable Options

**Option A: v0.7b residual servo over v0.7a.2 trace-native rows. Chosen.**

Pros:
- Directly addresses the full-action BC expressibility blocker.
- Reuses existing residual constants and `_weak_base_servo_action`.
- Preserves `v0_7a_2` env-native HOLD and trace-native row fixes.
- Lets Phase E test policy class transfer without opening held-out.

Cons:
- Base servo may confound attribution if it is too strong.
- Requires careful metadata and diagnostics to prove the base is shared and
  non-closing.

**Option B: add more full-action BC features or thresholds. Rejected.**

Pros:
- Smaller conceptual change.

Cons:
- `v0_7a_2` already fits offline but fails closed-loop; more offline feature
  fitting does not address the rollout distribution problem.
- Threshold relaxation would violate the authority boundary.

**Option C: policy-specific online recovery data. Rejected for this slice.**

Pros:
- Could improve each policy on its own visited states.

Cons:
- Blends dataset quality with online collection strategy.
- Makes candidate/baseline attribution harder.
- Belongs in a later spec if v0.7b shared overlay is insufficient.

### ADR

**Decision:** Implement `v0_7b` as residual servo BC using `v0_7a_2`
trace-native success/failure rows plus a `v0_7b` shared train closed-loop
recovery overlay induced only by the shared frozen base servo or shared
pre-registered zero-residual policy.

**Drivers:** actual Isaac Phase E failure after offline success, existing residual
servo code surface, and need for strict baseline/candidate fairness.

**Alternatives considered:** full-action BC extension and policy-specific online
recovery data.

**Why chosen:** It changes the minimum policy authority needed for closed-loop
transfer while preserving the MVP-2 A/B attribution contract.

**Consequences:** The implementation must add more guard metadata and tests than
a simple trainer swap. Phase E may still fail; that is valid evidence and must
not trigger threshold weakening.

**Follow-ups:** If `v0_7b` passes Phase E, write a separate calibration freeze
plan before held-out A/B. If it fails, diagnose residual policy class or recovery
row coverage without opening held-out.

---

## Implementation Steps

### Task 1: RED tests for v0.7b contracts

Files:

```text
apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
```

Add tests from `.omx/plans/test-spec-mvp2e-v07b-residual-servo-bc.md` before
implementation.

Expected RED command:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07b or v0_7b or residual_servo" -q
```

### Task 2: Add v0.7b constants and CLI gating

File:

```text
scripts/run_mvp2c_isaac_training_calibration.py
```

Add constants near the current `V07A2_*` block
(`scripts/run_mvp2c_isaac_training_calibration.py:182`):

```python
V07B_POLICY_SLICE_ID = "v0_7b"
V07B_SLICE_ID = "mvp2e_v07b_residual_servo_bc"
V07B_CHILD_OUTPUT_DIRNAME = "v0_7b_residual_servo_bc"
V07B_RESIDUAL_SERVO_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07b_residual_servo_config_v0.1.0"
V07B_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v07b_residual_servo_manifest_v0.1.0"
V07B_OFFLINE_RESIDUAL_FIT_GATE_SCHEMA_VERSION = "rdf_mvp2e_v07b_offline_residual_fit_gate_v0.1.0"
V07B_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v07b_residual_policy_artifact_v0.1.0"
V07B_BASE_SERVO_ID = "frozen_base_geometry_servo_v0_7b"
V07B_RESIDUAL_TARGET_DEFINITION = "actual_trace_action_minus_frozen_base_geometry_servo_action"
```

Update parser and mode guards around
`scripts/run_mvp2c_isaac_training_calibration.py:8266` and
`scripts/run_mvp2c_isaac_training_calibration.py:8305`:

- include `v0_7b` in `--policy-slice` choices.
- add `--recovery-overlay-induction-only`.
- allow `v0_7b` only with `--offline-relabel-only`,
  `--recovery-overlay-induction-only`, or `--expressibility-sanity-only`.
- require `--scenario-profile v0_6`.

Acceptance:

```text
v0_7b normal full run rejects.
v0_7b offline, recovery induction, and expressibility modes route to v0.7b
handlers.
```

### Task 3: Formalize frozen base servo config

Files:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
scripts/run_mvp2c_isaac_training_calibration.py
```

Reuse the existing residual constants and `_weak_base_servo_action`
(`scripts/run_mvp2b_isaac_proof_evaluator.py:52`,
`scripts/run_mvp2b_isaac_proof_evaluator.py:1485`), but wrap v0.7b metadata as
`frozen_base_geometry_servo_v0_7b`.

Implementation details:

- Add helper `build_v07b_residual_servo_config(output_dir, parent_config_sha256)`.
- Include:
  - base servo config
  - base servo config sha256
  - selected adapter source
  - behavior phase rule version `env_native_hold_v0_7a_2`
  - residual target definition
  - held-out exclusion fields
- Validate the config hash before use.

Acceptance:

```text
Config is hash-stable.
Config has no held-out-derived fields.
Config explicitly says closing_gate=false for base-only behavior.
```

### Task 4: Convert v0.7a.2 trace rows into residual rows

File:

```text
scripts/run_mvp2c_isaac_training_calibration.py
```

Build on current v0.7a.2 row prep
(`scripts/run_mvp2c_isaac_training_calibration.py:8030`) and existing v0.5
residual conversion (`scripts/run_mvp2c_isaac_training_calibration.py:5915`).

Add helpers:

```python
trace_row_to_v07b_residual_train_row(...)
residualized_rows_for_v07b(...)
prepare_v07b_candidate_rows(...)
prepare_v07b_baseline_rows(...)
```

Rules:

- candidate source = `prepare_v07a2_candidate_rows`.
- baseline source = `prepare_v07a2_baseline_rows`.
- preserve `behavior_state_phase` from `v0_7a_2`.
- `normalized_action` becomes the residual target.
- store `actual_trace_action` and `base_servo_action`.
- reject protected held-out seeds.

Acceptance:

```text
actual = base + residual within numeric tolerance.
candidate/baseline source reports still point to v0.7a.2 trace-native parent gate.
```

### Task 5: Add shared recovery induction artifact and overlay builder

File:

```text
scripts/run_mvp2c_isaac_training_calibration.py
```

Add a narrow shared train recovery induction path and deterministic overlay
construction:

```python
run_v07b_shared_train_recovery_induction_runtime(...)
build_v07b_train_recovery_overlay(...)
build_v07b_calibration_recovery_manifest(...)
```

The train recovery overlay source is fixed before implementation:

- source artifact =
  `v0_7b_residual_servo_bc/shared_train_recovery_induction_v0_7b.json`.
- source seeds are exactly `19003`, `19012`, `19129`, `19030`, and `19119`.
- `state_induction_policy` must be either `shared_frozen_base_servo` or
  `shared_pre_registered_zero_residual_policy`; default implementation uses
  `shared_frozen_base_servo`.
- `source_policy_slice=none`.
- `policy_specific_source=false`.
- `shared_overlay_for_both_views=true`.
- `proof_authority=false`.
- protected held-out seed range `21000-21049` is forbidden.
- row budget is exactly `max_rows_per_trace=32`, deterministic uniform sampling
  across each trace horizon, for `max_total_rows=160`.
- every sampled recovery state must be relabeled with a frozen expert labeler
  derived from parent `controller_repair_config.json`.
- residual target for recovery rows is
  `expert_recovery_action - base_servo_action`.
- if the shared recovery induction artifact is missing, fail closed with
  `recovery_overlay_source_unavailable`.
- if the labeler inputs, parent config, selected adapter schema, or permitted
  induction-policy metadata are missing or mismatched, fail closed with
  `recovery_overlay_labeler_unavailable`; do not emit empty residuals as a
  silent fallback.
- the exact same recovery rows must be appended to both baseline and candidate.
- Every row must include `proof_role=train_closed_loop_recovery_correction`.
- Recovery rows do not increase `accepted_success_trace_count`.
- Calibration recovery manifest must record zero train inclusion:
  `calibration_recovery_rows_in_train_view=false`.

The prior `v0_7a_2` candidate Phase E traces are diagnostic context only. They
must not be used as train recovery source rows because the source spec requires
shared base-servo or shared zero-residual state induction.

Acceptance:

```text
The shared recovery induction artifact contract exists and is tested.
The overlay contract exists and is tested with fixed source seeds, permitted
state_induction_policy, and fixed row budget.
No v0_7a_2 candidate policy trace is used as recovery overlay source.
No policy-specific online data is collected.
Missing recovery source fails closed with recovery_overlay_source_unavailable.
Missing labeler/config fails closed with recovery_overlay_labeler_unavailable.
No calibration recovery row reaches train HDF5.
```

### Task 6: Write v0.7b HDF5 views and policy artifacts

File:

```text
scripts/run_mvp2c_isaac_training_calibration.py
```

Add:

```python
write_v07b_residual_train_view_hdf5(...)
build_v07b_policy_artifact_payload(...)
derive_v07b_offline_residual_fit_gate(...)
build_v07b_residual_servo_slice(...)
```

Policy artifact requirements:

```text
policy_class=phase_conditioned_residual_servo_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0
trainer_family=phase_conditioned_residual_servo_bc
base_servo_plus_learned_residual=true
base_servo_id=frozen_base_geometry_servo_v0_7b
same_base_servo_as_peer=true
same_feature_schema_as_peer=true
same_trainer_hyperparameters_as_peer=true
same_selected_action_adapter_as_peer=true
```

Use `fit_phase_conditioned_bc_policy` on residualized rows with
`FEATURE_SCHEMA_V07A`, `BEHAVIOR_STATE_PHASES`, and
`FEATURE_SCHEMA_V07A_VERSION`.

Offline residual fit gate requirements:

```text
gate_id=offline_residual_fit_gate_v0_7b
candidate_residual_xy_mae_max <= 0.01
candidate_residual_z_mae_max <= 0.02
candidate_residual_action_rmse_max <= 0.03
candidate_reconstructed_action_xy_mae_max <= 0.01
candidate_reconstructed_action_z_mae_max <= 0.02
candidate_reconstructed_action_rmse_max <= 0.03
candidate_align_reconstructed_negative_z_rate <= 0.10
candidate_descend_reconstructed_negative_z_rate >= 0.80
candidate_descend_reconstructed_z_sign_agreement >= 0.90
candidate_hold_reconstructed_abs_z_mean <= 0.04
```

These thresholds inherit the existing `v0_7a` action-unit offline gate shape and
are pre-registered here. Baseline fit metrics are report-only because the final
A/B authority is held-out rollout uplift, not baseline offline fit quality.

Acceptance:

```text
candidate_curated_train_v0_7b.hdf5 exists.
baseline_uncurated_train_v0_7b.hdf5 exists.
candidate_policy_artifact_v0_7b.json exists.
baseline_policy_artifact_v0_7b.json exists.
offline_residual_fit_gate_v0_7b.json exists.
```

### Task 7: Strengthen runtime residual diagnostics

File:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
```

Current runtime adds base action before adapter for residual trainer artifacts
(`scripts/run_mvp2b_isaac_proof_evaluator.py:1461`). Extend diagnostics:

```text
base_servo_id
base_servo_action
residual_prediction
raw_action_before_adapter
base_servo_config_sha256
residual_target_definition
```

Add fail-closed validation when trainer family is residual but policy artifact
lacks base servo config/hash or residual target definition.

For `v0_7b`, runtime validation is strict:

```text
base_servo_id == frozen_base_geometry_servo_v0_7b
base_servo_config_sha256 == sha256(policy_artifact.base_servo_config)
residual_target_definition == actual_trace_action_minus_frozen_base_geometry_servo_action
```

There must be no silent fallback from missing `v0_7b` metadata to legacy
`WEAK_BASE_SERVO_CONFIG`. Legacy `v0_5` residual artifacts may keep the existing
backward-compatible path, but `v0_7b` artifacts fail closed on any mismatch.

Acceptance:

```text
diagnostics prove adapter was applied after residual reconstruction.
v0_7b missing or mismatched base_servo_id/hash/target_definition fails closed.
v0_5 residual behavior remains backward-compatible.
```

### Task 8: Add v0.7b Phase E guard and runtime path

File:

```text
scripts/run_mvp2c_isaac_training_calibration.py
```

Add:

```python
run_v07b_expressibility_sanity_runtime(...)
```

Pattern after current v0.7a.2 guard
(`scripts/run_mvp2c_isaac_training_calibration.py:3633`):

- expressibility-only still requires existing `scenario_manifest.json` before
  policy-specific gate checks, matching the current dispatch order at
  `scripts/run_mvp2c_isaac_training_calibration.py:8516`.
- missing gate -> `runtime_backend=isaac_runtime_not_started`.
- failed gate -> `runtime_backend=isaac_runtime_not_started`.
- missing candidate policy -> fail closed.
- invalid policy artifact -> fail closed.
- passing offline gate -> run same 5-seed Phase E as v0.7a.2.

Acceptance:

```text
expressibility_sanity_gate_v0_7b.json is written.
missing-gate tests use an output dir with `scenario_manifest.json` present but
without `offline_residual_fit_gate_v0_7b.json`.
heldout_21000_21049_accessed=false always before calibration.
```

### Task 9: Update reports and developer docs

Files:

```text
docs/developer/debugging_guide.md
docs/developer/worklog.md
Handoff.md
```

Record:

- how to run v0.7b offline build.
- how Phase E is gated.
- why v0.7b is not MVP-2 Closed.
- next valid step after Phase E pass/fail.

Do not claim positive held-out uplift.

---

## Verification Steps

Focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07b or v0_7b or residual_servo" -q
```

Regression tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a or v0_7a or v07a1 or v0_7a_1 or v07a2 or v0_7a_2 or v07b or v0_7b or residual_servo" -q
```

Offline artifact build:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7b \
  --recovery-overlay-induction-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7b \
  --offline-relabel-only --pretty
```

Static checks:

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py

git diff --check
```

Actual Isaac Phase E, only after offline gate passes:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7b \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Base servo dominates success and hides curation effect | Require base-only diagnostic as non-closing evidence and keep final closure on baseline-vs-candidate residual policies. |
| Recovery overlay weakens curation contrast | Make overlay shared and explicitly report row counts; candidate must still win despite shared correction rows. |
| Calibration data leaks into training | Add tests that HDF5 metadata excludes calibration recovery proof roles. |
| Residual diagnostics are insufficient | Runtime must log base action, residual prediction, and raw action before adapter. |
| v0.7b still fails Phase E | Fail closed and do not open calibration/held-out; next step is a separate policy-class/recovery coverage diagnosis. |

---

## Available Agent Types

Recommended roles for follow-up execution:

- `executor` — implement code changes in scripts and tests.
- `test-engineer` — harden focused tests and regression selection.
- `verifier` — inspect final artifacts and claim boundaries.
- `critic` — review the implementation against proof integrity constraints.

## Follow-up Staffing Guidance

Default durable path:

```text
$ultragoal implement docs/superpowers/plans/2026-06-12-mvp2e-v07b-residual-servo-bc.md
```

Parallel Team + Ultragoal path, if speed is needed:

```text
$team implement docs/superpowers/plans/2026-06-12-mvp2e-v07b-residual-servo-bc.md
```

Suggested lanes:

```text
executor lane 1: training script v0.7b offline artifacts
executor lane 2: runtime evaluator diagnostics
test-engineer lane: RED/green tests and regression commands
verifier lane: artifact/claim-boundary review after integration
```

Team verification path:

```text
Team must return focused test output, offline artifact build output, compileall,
ruff, git diff --check, and any Isaac Phase E result if run.
Ultragoal checkpoints those outputs as durable evidence.
```

`$ralph` fallback:

Use only if the user explicitly asks for a single-owner persistent verification
loop instead of the default Ultragoal ledger.

## Goal-Mode Follow-up Suggestions

- `$ultragoal` is the recommended next step for implementation.
- `$team` can be combined with `$ultragoal` if parallel lanes are desired.
- `$autoresearch-goal` is not recommended for this slice; the implementation
  target is already specified.
- `$performance-goal` is not applicable; this is not a performance optimization.
