# MVP-2E v0.8k Candidate Training Signal Rebalance Design

## 목적

`v0_8h` actual Isaac calibration은 baseline `23/30`, candidate `25/30`으로
candidate가 더 좋았지만 calibration pre-signal gate의 최소 gap `+0.10`에는
미달했다. `v0_8i`와 `v0_8j` artifact-only diagnosis는 다음을 확인했다.

```text
v0_8i:
  baseline_success_compression=true
  candidate_failures_total=5
  target_failure_reduction_minimum=2

v0_8j:
  candidate_margin_positive_failure_count=0
  candidate_margin_repair_feasible=false
  recommended_downstream_slice=v0_8k_candidate_training_signal_rebalance
```

따라서 `v0_8k`의 목적은 shared controller/action authority를 더 강화하지
않고, candidate curated training view의 learned residual signal을 더 명확하게
만드는 것이다.

MVP-2 Closed를 주장하지 않는다. `v0_8k`는 calibration pre-signal을 다시
통과시키기 위한 candidate data/training-signal slice다.

## 핵심 판단

`v0_8j`에서 candidate failure trace에 attribution-safe residual margin이 없었다.
즉 실패한 calibration seed를 사후로 candidate-only hand-coded controller로
고치는 것은 금지한다. 다음 valid mechanism은 training view에서 candidate가
학습해야 하는 descent / seat 유지 / centered progress 신호를 더 강하게
보이게 만드는 것이다.

이는 trainer 변경이 아니다.

```text
Allowed:
  candidate curated train view deterministic row rebalance
  same NumPy phase-conditioned residual servo BC trainer
  same feature schema
  same selected action adapter
  same shared authority stack
  fresh calibration run

Forbidden:
  candidate-only hand-coded controller
  success metric change
  env-native authority change
  further shared controller strengthening for candidate-only gain
  calibration seed fitting
  held-out seed access before calibration pass
```

## Source Evidence

Required parent artifacts:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8h_early_centered_z_open_safe_entry/
    calibration_presignal_gate_v0_8h.json
    candidate_policy_artifact_v0_8h.json
    baseline_policy_artifact_v0_8h.json

  v0_8i_calibration_uplift_compression_diagnosis/
    v0_8i_calibration_uplift_compression_diagnosis.json

  v0_8j_attribution_preserving_candidate_margin_diagnosis/
    v0_8j_attribution_preserving_candidate_margin_diagnosis.json

  v0_7d_action_authority_post_adapter_z_gate/
    candidate_curated_train_v0_7d.hdf5
    baseline_uncurated_train_v0_7d.hdf5
```

Required parent conditions:

```text
v0_8h.calibration_opened=true
v0_8h.passed=false
v0_8h.failure_reason=candidate_baseline_success_gap_below_minimum
v0_8h.heldout_opened=false
v0_8h.fresh_heldout_27000_27049_accessed=false

v0_8j.candidate_margin_repair_feasible=false
v0_8j.recommended_downstream_slice=v0_8k_candidate_training_signal_rebalance
v0_8j.heldout_opened=false
v0_8j.fresh_heldout_27000_27049_accessed=false
```

## Training View Rebalance

Source rows:

```text
candidate_source = v0_7d candidate_curated_train_v0_7d.hdf5 metadata rows
baseline_source  = v0_7d baseline_uncurated_train_v0_7d.hdf5 metadata rows
```

Baseline view:

```text
baseline_uncurated_train_v0_8k.hdf5 = baseline_source unchanged
```

Candidate view:

```text
candidate_curated_train_v0_8k.hdf5 =
  candidate_source
  + deterministic duplicates from candidate_source only
```

Candidate rebalance classes:

```text
seat_hold_rows:
  behavior_state_phase == "HOLD"
  OR env_native_success_mask == true

centered_descent_rows:
  behavior_state_phase == "DESCEND"
  lateral_error_m <= 0.006
  normalized_action[2] <= -0.08

under_depth_progress_rows:
  behavior_state_phase == "DESCEND"
  insertion_depth_m < 0.024
  lateral_error_m <= 0.006
  normalized_action[2] <= -0.08
```

Duplication rule:

```text
base copy count: 1 for every source row
seat_hold_rows: +3 copies
centered_descent_rows: +1 copy
under_depth_progress_rows: +1 copy
max copies per original row: 5 total
```

Every duplicated row must include metadata:

```text
rebalance_policy_slice="v0_8k"
rebalance_source_row_sha256
rebalance_reason
rebalance_copy_index
rebalance_is_duplicate=true
```

Original rows copied into the `v0_8k` candidate view must include:

```text
rebalance_policy_slice="v0_8k"
rebalance_is_duplicate=false
rebalance_reason="base_source_row"
```

This is deterministic row replication. It is not stochastic sampling, not
runtime augmentation, and not calibration-seed tuning.

## Policy Artifacts

Trainer:

```text
fit_phase_conditioned_bc_policy
trainer_family=phase_conditioned_residual_servo_bc
ridge_lambda=0.001
feature_schema=FEATURE_SCHEMA_V07A
phase_schema=BEHAVIOR_STATE_PHASES
```

Baseline:

```text
Retrain from baseline_uncurated_train_v0_8k.hdf5 unchanged rows.
```

Candidate:

```text
Retrain from candidate_curated_train_v0_8k.hdf5 rebalanced rows.
```

Both artifacts must inherit the `v0_8h` shared runtime authority stack:

```text
selected_action_adapter_id
selected_action_adapter_config_sha256
base_servo_config_sha256
authority_filter_config_sha256
final_post_adapter_authority_config_sha256
final_post_adapter_xy_authority_config_sha256
shared_hysteresis_authority_config_sha256
capture_conditioned_progress_authority_config_sha256
horizon_reserved_capture_authority_config_sha256
deadline_precedence_horizon_authority_config_sha256
early_centered_z_open_safe_entry_config_sha256
```

Allowed baseline/candidate differences:

```text
dataset_view_role
train_sample_count
weights
bias
policy_id
policy_artifact_sha256
training_view_sha256
candidate_training_signal_rebalance fields
```

All other authority, trainer, adapter, feature schema, and success metric fields
must remain equal.

## Offline Gates

`v0_8k` must fail closed unless all gates pass.

### G1 Parent Evidence Gate

Requires valid `v0_8h`, `v0_8i`, and `v0_8j` parent artifacts with held-out
`27000-27049` still unopened.

### G2 Training View Integrity Gate

Requires:

```text
candidate_source_rows > 0
baseline_source_rows > 0
candidate_rebalanced_rows > candidate_source_rows
baseline_rebalanced_rows == baseline_source_rows
candidate_duplicate_rows > 0
candidate_duplicate_rows_by_reason includes seat_hold_rows and centered_descent_rows
all duplicated rows derive from candidate source rows only
no calibration trace rows are used for training
no held-out trace rows are used for training
```

### G3 Peer Fairness Gate

Requires equality of shared trainer/authority/adapter fields and permits only
the explicit dataset-view differences above.

### G4 Candidate Signal Delta Gate

Compare `v0_8k` candidate predictions against parent `v0_8h` candidate
predictions on the source candidate rows.

Requires:

```text
candidate_weight_delta_l2 > 1.0e-6
candidate_prediction_delta_nonzero_fraction >= 0.10
candidate_descent_target_rows_mean_z_delta <= -0.002
baseline_weight_delta_l2 <= 1.0e-9 OR baseline_training_view_unchanged=true
```

This gate proves that the candidate training signal changed while the shared
runtime authority did not change.

## Fresh Calibration / Held-Out Rules

Fresh calibration range:

```text
29000-29029
```

Burned calibration ranges:

```text
26500-26529
27500-27529
28000-28029
28500-28529
```

Held-out:

```text
27000-27049 remains the sealed closure held-out range.
```

Runtime rule:

```text
Run calibration first.
Open held-out 27000-27049 only if calibration pre-signal gate passes.
```

Calibration gate remains:

```text
actual_rollouts_per_policy = 30
candidate_success_rate - baseline_success_rate >= 0.10
candidate_failures_total <= 3
```

Held-out closure remains:

```text
actual_rollouts_per_policy >= 50 per policy
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
env-native 10-consecutive success authority
```

## Non-Claims

`v0_8k` must report:

```text
mvp2_closed=false unless sealed held-out closure passes
policy_uplift_proven=false unless sealed held-out closure passes
real_robot_success=false
physical_robot_readiness=false
hmd_openxr_readiness=false
visual_policy_performance=false
```

## Stop Conditions

Stop and diagnose next if:

```text
parent evidence is missing or inconsistent
training view rebalance uses calibration or held-out trace rows
peer fairness gate fails
candidate signal delta gate fails
fresh calibration still fails
held-out opens before calibration pass
implementation would require changing success metric or env-native authority
implementation would require candidate-only hand-coded runtime controller
```

If calibration fails, preserve `v0_8k` evidence and immediately create the next
diagnostic slice instead of claiming MVP-2 Closed.
