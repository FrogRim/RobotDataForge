# MVP-2E v0.7f Depth-Zero / XY Saturation Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_7f`, an artifact-only diagnosis harness that classifies
why `v0_7e` actual Isaac Phase E still has `depth≈0` despite restored z windows
on four of five train-side sanity seeds.

**Architecture:** `v0_7f` is not a new policy/trainer/control slice. It reads
existing `v0_7e` actual Isaac policy traces and same-seed successful expert
reference traces, computes H18-H24 diagnostics, writes a hash-stable report, and
optionally recommends a future `v0_7g_*` repair slice. It must not run Isaac,
train policies, open calibration, open held-out `21000-21049`, or mutate
historical `v0_7e` evidence.

**Tech Stack:** Python 3.11, NumPy, pytest, existing MVP-2B/MVP-2C proof
scripts.

---

## Source Artifacts

- Spec:
  `docs/superpowers/specs/2026-06-15-mvp2e-v07f-depth-zero-xy-saturation-diagnosis-design.md`
- Context:
  `.omx/context/mvp2e-v07f-depth-zero-xy-saturation-diagnosis-20260615T055459Z.md`
- PRD:
  `.omx/plans/prd-mvp2e-v07f-depth-zero-xy-saturation-diagnosis.md`
- Test spec:
  `.omx/plans/test-spec-mvp2e-v07f-depth-zero-xy-saturation-diagnosis.md`
- Source failure evidence:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7e_shared_hysteresis_parity_repair/`
- Expert reference evidence:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/isaac_runtime_train_generation_probe/`

## RALPLAN-DR Summary

### Principles

1. Diagnosis before repair: no `v0_7g` code until `v0_7f` classifies the current
   depth-zero failure.
2. Artifact-only boundary: `v0_7f` must not invoke Isaac, training, calibration,
   or held-out A/B.
3. Historical failure integrity: `v0_7e` remains failed Phase E evidence.
4. Authority separation: env-native success authority is unchanged; `v0_7f`
   diagnostics cannot override closure status.
5. Reviewer readability: the report must make xy saturation, lateral regression,
   and evidence gaps obvious without manual trace parsing.
6. Seed firewall first: protected held-out seed ids are rejected before payload
   reads, even when traces live in legacy `heldout_rollout_traces` directories.

### Decision Drivers

1. `v0_7e` actual Isaac Phase E reached runtime but failed `0/5`.
2. Four traces recovered `longest_nonzero_z=28`, yet insertion depth stayed
   zero or near-zero.
3. `v0_7e` policy traces show 145-148/148 xy saturation rows while successful
   expert traces on the same seeds usually show 0-4 saturation rows.

### Viable Options

**Option A: go straight to `v0_7g` xy/gain repair. Rejected.**

The current evidence strongly suggests xy saturation and z-open lateral
regression, but sign/frame mismatch and vertical response gaps must be
separated before another repair loop.

**Option B: rerun `v0_7e` Phase E. Rejected.**

The latest actual Isaac run already failed `0/5` with trace evidence. Rerunning
without a new diagnosis or repair is not informative.

**Option C: implement `v0_7f` artifact-only diagnosis harness. Chosen.**

This is the smallest step that preserves proof integrity, produces reusable
evidence, and determines whether the next valid repair is xy saturation,
lateral regression guard, action-frame/sign repair, or vertical instrumentation.

## ADR

**Decision:** Add `v0_7f_depth_zero_xy_saturation_diagnosis` as an artifact-only
diagnosis mode in `scripts/run_mvp2c_isaac_training_calibration.py`.

**Drivers:** `v0_7e` Phase E `0/5`, restored z windows without insertion depth,
near-total xy saturation, and held-out/calibration sealing requirements.

**Alternatives considered:** rerun `v0_7e`, implement `v0_7g` directly, or change
trainer/policy class.

**Why chosen:** It avoids another blind repair, uses existing traces, and keeps
the MVP-2 claim boundary clean.

**Consequences:** `v0_7f` may classify the root cause and recommend a future
repair slice, but MVP-2 remains open and Phase E remains failed until a later
slice passes actual Isaac.

**Follow-ups:** If `v0_7f` classifies `XY_SATURATION_CENTERING_INSTABILITY` or
`Z_OPEN_LATERAL_REGRESSION`, write a separate `v0_7g` repair spec. If it finds
missing diagnostics or sign/frame ambiguity, add instrumentation before repair.

---

## File Structure

### Modify

- `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add `v0_7f` constants, config builder, trace loaders, H18-H24 harness
    records, classifier, artifact writer, and CLI guard.

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add RED/GREEN tests for config hash, trace summaries, harness records,
    classifier, CLI mode, and proof-boundary fields.

- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

### Do Not Modify

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - `v0_7f` reads existing evaluator trace output; it should not change runtime
    policy behavior.

### Generated During Execution

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7f_depth_zero_xy_saturation_diagnosis/
    mvp2e_v07f_diagnostic_config.json
    mvp2e_v07f_depth_zero_harness_report.json
    mvp2e_v07f_trace_comparison_table.json
    mvp2e_v07f_gate_manifest.json
```

---

## Implementation Steps

### Task 1: RED tests for v0.7f config and trace summaries

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Add fixture helpers that write minimal `v0_7e` policy trace rows with
  nested `controller_action_diagnostics`.
- [ ] Add fixture helpers that write same-seed expert reference trace rows.
- [ ] Add `test_v07f_diagnostic_config_is_hash_stable_and_seals_heldout`.
- [ ] Add `test_v07f_extracts_trace_summary_z_windows_depth_and_xy_saturation`.
- [ ] Add `test_v07f_extracts_z_open_lateral_regression`.
- [ ] Add `test_v07f_computes_action_to_state_sign_agreement_when_fields_exist`.
- [ ] Add `test_v07f_marks_sign_agreement_not_evaluated_when_fields_missing`.
- [ ] Add `test_v07f_rejects_missing_controller_action_diagnostics`.

### Task 2: Implement config and trace-summary helpers

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add constants:
  - `V07F_POLICY_SLICE_ID = "v0_7f"`
  - `V07F_DIAGNOSIS_SLICE_ID = "mvp2e_v07f_depth_zero_xy_saturation_diagnosis"`
  - `V07F_OUTPUT_DIRNAME = "v0_7f_depth_zero_xy_saturation_diagnosis"`
  - schema versions for config, report, comparison table, and manifest.
- [ ] Add `build_v07f_diagnostic_config(output_dir: Path)`.
- [ ] Add `validate_v07f_diagnostic_config(config)`.
- [ ] Add trace discovery helpers for:
  - `v0_7e_shared_hysteresis_parity_repair/isaac_runtime_expressibility_sanity_v0_7e/...`;
  - `isaac_runtime_train_generation_probe/isaac_runtime_heldout_rollout_traces/...`.
- [ ] Add protected seed pre-scan for both source trace sets before reading
  payloads. If any seed is in `21000-21049`, write fail-closed diagnostic
  metadata and do not classify a repair.
- [ ] Add deterministic seed extraction from trace filenames and payload fields.
- [ ] Add hash helpers for source trace set and expert reference trace set.
- [ ] Add `_summarize_v07f_trace(rows)` that computes:
  - `row_count`;
  - `longest_nonzero_z`;
  - `z_open_spans`;
  - `max_insertion_depth_m`;
  - `first_depth_positive_step`;
  - `xy_saturation_count`;
  - `xy_saturation_ratio`;
  - `xy_saturation_during_z_open_ratio`;
  - `z_open_start_lateral_m`;
  - `z_open_min_lateral_m`;
  - `z_open_end_lateral_m`;
  - `z_open_max_lateral_m`;
  - `z_open_regression_m`;
  - diagnostics completeness flags.
- [ ] Add sign-agreement helper that returns `not_evaluated` if required
  `relative_x_m` / `relative_y_m` fields are missing.
- [ ] Add per-trace diagnostic completeness matrix for H24. Aggregate H24 pass
  requires every analyzed policy trace to contain required diagnostics unless a
  field is explicitly optional with a recorded rationale.

### Task 3: RED tests for H18-H24 harness records and classifier

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Add `test_v07f_depth_zero_harness_reads_v07e_actual_isaac_traces`.
- [ ] Add `test_v07f_reports_xy_saturation_ratio_against_expert_reference`.
- [ ] Add `test_v07f_classifies_lateral_regression_during_z_open`.
- [ ] Add `test_v07f_classifier_prioritizes_missing_diagnostics_before_root_cause`.
- [ ] Add `test_v07f_rejects_protected_seed_in_policy_trace_discovery`.
- [ ] Add `test_v07f_rejects_protected_seed_in_expert_reference_discovery`.
- [ ] Add `test_v07f_h24_requires_per_trace_diagnostic_completeness`.
- [ ] Add `test_v07f_h22_not_evaluated_blocks_downstream_repair_recommendation`.
- [ ] Add `test_v07f_does_not_open_calibration_or_heldout`.
- [ ] Add `test_v07f_marks_proof_authority_diagnostic_only`.
- [ ] Add `test_v07f_gate_manifest_records_required_artifacts_and_hashes`.
- [ ] Add `test_v07f_report_and_manifest_reject_closure_leakage`.

### Task 4: Implement H18-H24 and report writer

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add harness record builders:
  - `H18_Z_WINDOW_RESTORATION_DIAGNOSTIC`
  - `H19_XY_SATURATION_CENTERING_INSTABILITY`
  - `H20_Z_OPEN_LATERAL_REGRESSION`
  - `H21_PREMATURE_Z_OPEN_CONTEXT`
  - `H22_XY_ACTION_FRAME_OR_SIGN_CHECK`
  - `H23_VERTICAL_RESPONSE_DEPTH_SEMANTICS`
  - `H24_DIAGNOSTIC_VISIBILITY_COMPLETENESS`
- [ ] Add `_classify_v07f_depth_zero_harnesses(harnesses)`.
- [ ] Classification priority:
  1. `TRACE_DIAGNOSTICS_INCOMPLETE`
  2. `XY_ACTION_FRAME_OR_SIGN_MISMATCH`
  3. `XY_SATURATION_CENTERING_INSTABILITY`
  4. `Z_OPEN_LATERAL_REGRESSION`
  5. `Z_OPEN_WITH_NO_VERTICAL_PROGRESS`
  6. `PREMATURE_Z_OPEN_CONTEXT`
  7. `UNCLASSIFIED_DEPTH_ZERO_FAILURE`
- [ ] Define `H22 not_evaluated` semantics:
  - if sign/frame evidence is missing because trace fields are absent, classify
    as `TRACE_DIAGNOSTICS_INCOMPLETE` or record saturation as
    `primary_candidate` only;
  - in that case `recommended_downstream_slice` must be `null`.
- [ ] Add `build_v07f_trace_comparison_table(output_dir)`.
- [ ] Add `build_v07f_depth_zero_harness_report(output_dir, config=None)`.
- [ ] Add `write_v07f_depth_zero_diagnosis_artifacts(output_dir)`.
- [ ] Ensure report includes:
  - `proof_authority="diagnostic_only_not_closure_authority"`;
  - `mvp2_closed=false`;
  - `policy_uplift_proven=false`;
  - `phase_e_passed=false`;
  - `calibration_opened=false`;
  - `heldout_21000_21049_accessed=false`;
  - source and expert trace set hashes.
- [ ] Ensure closure leakage is impossible in generated report/manifest:
  `mvp2_closed`, `policy_uplift_proven`, `phase_e_passed`,
  `calibration_opened`, and `heldout_21000_21049_accessed` must all be false.

### Task 5: CLI guard and artifact-only execution path

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add `--depth-zero-diagnosis-only` CLI flag.
- [ ] Add `v0_7f` to `--policy-slice` choices only for diagnosis mode.
- [ ] Reject `--depth-zero-diagnosis-only --clean` to avoid deleting source
  evidence before reading it.
- [ ] Reject `--policy-slice v0_7f` unless `--depth-zero-diagnosis-only` is set.
- [ ] Ensure diagnosis mode returns after writing artifacts and never calls
  evaluator backend, Isaac, training, calibration, or held-out flows.
- [ ] Add evidence manifest entries for the four `v0_7f` artifacts.
- [ ] Preserve the distinction between protected seed access and legacy path
  labels containing `heldout`.

### Task 6: Documentation and verification

**Files:**

- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] Record implementation result and generated artifact paths.
- [ ] Record root-cause classification and downstream recommendation.
- [ ] Keep claim boundary explicit: MVP-2 not Closed, Phase E not passed,
  calibration unopened, held-out sealed.
- [ ] Run focused v0.7f tests.
- [ ] Run relevant v0.7e/v0.7f/harness regression tests.
- [ ] Run compileall, ruff, and `git diff --check`.

---

## Verification Commands

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07f or v0_7f or depth_zero or xy_saturation" -q

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7f \
  --depth-zero-diagnosis-only \
  --pretty

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07e or v0_7e or v07f or v0_7f or harness" -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

## Stop Conditions

Stop and report if:

- required `v0_7e` actual Isaac trace evidence is missing;
- expert reference traces for the same seeds are unavailable and no defensible
  comparison can be made;
- implementation would require running Isaac or training;
- implementation would require calibration or held-out access;
- classifier cannot distinguish evidence gaps from root cause classes;
- success metric or Phase E closure authority would need to change.

## Available Agent Types

- `executor`: implement tests and artifact-only harness.
- `test-engineer`: strengthen focused pytest coverage and fail-closed cases.
- `verifier`: check claim boundaries, generated artifacts, and no held-out
  access.
- `architect`: review artifact boundary and classifier semantics.
- `critic`: review plan completeness and proof-integrity risks.

## Goal-Mode Follow-up Suggestions

- `$ultragoal` is the default follow-up for implementing this sequential plan.
- `$team` is optional if implementation is split into disjoint lanes:
  tests, script implementation, and verification/docs.
- `$ralph` is a fallback only if a single-owner persistence loop is explicitly
  preferred.
