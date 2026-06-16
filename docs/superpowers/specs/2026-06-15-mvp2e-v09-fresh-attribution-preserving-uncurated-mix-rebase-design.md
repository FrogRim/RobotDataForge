# MVP-2E v0.9 Fresh Attribution-Preserving Uncurated Mix Rebase 설계

## 목적

`v0_8k` lineage fix 이후 actual Isaac calibration은 다음 결과로 fail-closed됐다.

```text
baseline=26/30=0.8667
candidate=27/30=0.9000
gap=+0.0333 < +0.10
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
```

`v0_8l` audit는 두 가지를 artifact-only로 확정했다.

```text
authority_ceiling_detected=true
uncurated_comparator_weak=true
baseline_rejected_row_count=1936
baseline_rejected_descend_negative_z_fraction=0.940594059406
candidate_recovered_baseline_failure_count=1
recommended_downstream_slice=v0_9_fresh_attribution_preserving_uncurated_mix_rebase
```

따라서 `v0_9`의 목적은 shared controller/action authority를 더 강화하지 않고,
baseline uncurated comparator를 fresh proof slice용으로 다시 사전 등록하는 것이다.

MVP-2 Closed를 주장하지 않는다. `v0_9`는 fresh calibration이 통과할 때만 sealed
held-out `27000-27049`를 열 수 있다.

## 비목표

- success metric 변경 금지
- env-native 10-consecutive authority 변경 금지
- candidate-only hand-coded controller 금지
- shared action authority 추가 강화 금지
- held-out `27000-27049` 선개봉 금지
- baseline을 결과 보고 사후 독성 데이터셋처럼 조작 금지
- real robot / HMD / visual policy claim 금지

## Parent Evidence

Required:

```text
v0_8k_candidate_training_signal_rebalance/
  calibration_presignal_gate_v0_8k.json
  candidate_curated_train_v0_8k.hdf5
  baseline_uncurated_train_v0_8k.hdf5
  candidate_policy_artifact_v0_8k.json
  baseline_policy_artifact_v0_8k.json

v0_8l_authority_ceiling_uncurated_mix_audit/
  v0_8l_authority_ceiling_audit_report.json

train_generation_runtime_gate.json
isaac_runtime_train_generation_probe/isaac_runtime_heldout_rollout_traces/*.json
```

Required parent conditions:

```text
v0_8l.authority_ceiling_detected=true
v0_8l.uncurated_comparator_weak=true
v0_8l.recommended_downstream_slice=v0_9_fresh_attribution_preserving_uncurated_mix_rebase
v0_8l.heldout_opened=false
v0_8l.fresh_heldout_27000_27049_accessed=false
```

## Dataset Rebase

Candidate:

```text
candidate_curated_train_v0_9.hdf5 = v0_8k candidate_curated_train_v0_8k.hdf5 rows unchanged
```

Baseline:

```text
baseline_uncurated_train_v0_9.hdf5 =
  accepted success rows from v0_8k candidate view
  + actual failed train-generation trace rows from the 40 pre-registered train probe attempts
  + deterministic duplicated failure rows until the pre-registered noise mix ratio is met
```

Pre-registered baseline mix fields:

```text
baseline_noise_mix_ratio=0.40
accepted_failure_ratio=0.40
failure_type_distribution={
  "env_native_stability_window_not_reached": 1.0
}
noise_profile_config_sha256=<hash>
scripted_expert_config_sha256=<hash of source train_generation_runtime_gate>
controlled_failure_config_sha256=<hash of failed train-generation trace path list + taxonomy>
train_generation_config_sha256=<hash of train_generation_runtime_gate>
```

Rationale:

```text
0.40은 train-generation attempt 기준 실패 12/40=0.30보다 높지만, 실패 trace가
실제로 baseline 학습 신호에 희석됐다는 v0_8l audit 결과를 반영한 fresh slice
pre-registration 값이다. 이 값은 fresh v0_9 calibration/held-out 결과를 보기 전에
고정하며, held-out 결과를 본 뒤 변경하지 않는다.
```

Every baseline failure row must include:

```text
uncurated_mix_policy_slice="v0_9"
uncurated_mix_is_failure_material=true
uncurated_mix_source_trace_sha256
uncurated_mix_source_trace_path
uncurated_mix_failure_type="env_native_stability_window_not_reached"
uncurated_mix_copy_index
uncurated_mix_ratio_target=0.40
```

This is not a marketplace feature, not real robot evidence, and not a claim
that the baseline is universally representative. It is a fresh, explicit,
pre-registered uncurated comparator for this Isaac evaluator-domain proof.

## Policy Artifacts

Baseline and candidate both use:

```text
trainer=fit_phase_conditioned_bc_policy
trainer_family=phase_conditioned_residual_servo_bc
feature_schema=FEATURE_SCHEMA_V07A
phase_schema=BEHAVIOR_STATE_PHASES
selected_action_adapter_id inherited from v0_8k
shared authority stack inherited from v0_8k / v0_8h lineage
```

Allowed differences:

```text
dataset_view_role
train_sample_count
weights
bias
training_view_sha256
policy_id
policy_artifact_sha256
uncurated_mix fields for baseline
```

Forbidden differences:

```text
selected_action_adapter_id
trainer
trainer_family
feature_schema
phase_schema
action_schema
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

## Offline Gates

`v0_9` must fail closed unless:

```text
parent v0_8l audit is valid and recommends v0_9
train_generation_runtime_gate passed with actual_train_generation_evidence=true
candidate rows are copied unchanged from v0_8k candidate view
baseline mix config includes all required pre-registration fields and hashes
baseline failure rows come only from train-generation traces, not calibration/held-out traces
baseline actual failure material ratio >= 0.35 and <= 0.45
candidate and baseline peer fairness holds for trainer/adapter/authority fields
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
```

## Fresh Calibration / Held-Out

Fresh calibration range:

```text
30000-30029
```

Burned calibration ranges:

```text
26500-26529
27500-27529
28000-28029
28500-28529
29000-29029
```

Held-out:

```text
27000-27049 remains sealed until v0_9 calibration passes.
```

Calibration gate remains:

```text
actual_rollouts_per_policy=30
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

`v0_9` must report:

```text
mvp2_closed=false unless sealed held-out closure passes
policy_uplift_proven=false unless sealed held-out closure passes
deployable_real_robot_policy=false
visual_policy_performance=false
real_robot_success=false
physical_robot_readiness=false
hmd_openxr_readiness=false
```

## Stop / Next Loop

If `v0_9` calibration fails:

```text
preserve calibration evidence
do not open held-out
write artifact-only diagnosis
continue to the next valid slice automatically
```

If `v0_9` calibration passes:

```text
open held-out 27000-27049 once
run 50/50 actual Isaac A/B
close MVP-2 only if held-out closure gate passes
```
