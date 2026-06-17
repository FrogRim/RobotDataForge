# MVP-2E v0.7a Behavior-State Phase Relabel Design

Date: 2026-06-12

## 목적

`v0_7a`의 목적은 MVP-2 Phase E expressibility blocker를 해결하기 위한
offline-only policy slice를 사전 등록하는 것이다.

현재 상태:

```text
repair probe: v0.6i green
fixed 40-run train-generation gate: passed, 28/40 actual Isaac success
train dataset / policy artifacts: generated
expressibility sanity: failed, 0/5
calibration: not run
held-out 21000-21049: sealed
```

진단은 다음 한 문장으로 고정한다.

```text
expert는 lateral-gated behavior-state controller인데,
policy는 depth-derived phase feature로 학습되어 한 phase 안에 z=0 정렬 행동과
z=-0.16 하강 행동이 섞였고, linear BC가 "항상 하강"으로 붕괴했다.
```

`v0_7a`는 새 Isaac train-generation을 하지 않는다. 기존 `v0_6` actual Isaac
train-generation evidence를 보존한 채, row-level phase label과 policy feature schema를
offline으로 다시 정의해 baseline/candidate 정책을 재학습한다.

## 비목표

`v0_7a`는 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- calibration `20000-20029`를 실행하지 않는다.
- 새 actual Isaac expert train-generation rollout을 만들지 않는다.
- train-generation seed를 교체하지 않는다.
- baseline mix, curation threshold, env-native success authority, `stable_steps=10`,
  `max_steps=150`을 바꾸지 않는다.
- expressibility 실패 후 threshold를 완화하지 않는다.
- candidate-only feature, candidate-only trainer, candidate-only action adapter를
  허용하지 않는다.
- `v0_7b` residual servo BC fallback을 동시에 구현하지 않는다.
- deterministic/proxy/fixture evidence로 MVP-2 Closed를 주장하지 않는다.
- deployable visual policy, real robot success, physical readiness, HMD readiness를
  주장하지 않는다.

## Parent Evidence

`v0_7a`는 아래 artifact를 parent evidence로 삼는다.

```text
slice_id=v0_7a
parent_scenario_profile=v0_6
parent_repair_probe_gate_sha256=5575361f9f542b02ea3c466baa07036a082fdb9373d9f112a2dee160b90bca4f
parent_train_generation_runtime_gate:
  passed=true
  generated_rollout_count=40
  generated_success_count=28
  required_success_count=20
parent_failed_expressibility_sanity_gate_sha256=99886c38a7e5012b69a63c628858e52a9c822ff0d1a27a99a8474c83eac76116
parent_baseline_uncurated_train_hdf5_file_sha256=053de6ffa333acaa7c34df3b5c4fbff57a730ae1e8fee1cc318b81dd80cf5730
parent_candidate_curated_train_hdf5_file_sha256=62d4bef4f691a2e6b782b07510991e8af7570ba5d9b85f48fbb04134720e1829
parent_baseline_policy_artifact_file_sha256=474d2758ae1d458ad9b58124e92abb3b7ebad022530a63cf7915a1e625161c99
parent_candidate_policy_artifact_file_sha256=8af2e82b44e901ccc7115a92bdad967c45c940430cc10062fc6f964f7e3d134c
parent_baseline_policy_artifact_payload_sha256=3259fb039e0c8a36b02a9f691fd45fe542e3dabda043dc5c9eae7d13c28cc93e
parent_candidate_policy_artifact_payload_sha256=e915d9da4090c3cfb1218d6799b6ae1ad5d61528faf9c699acab9450116e10f5
parent_curation_manifest_file_sha256=76d8169d330e11a2d76d13030cada8d811f9088139e0bae150523bb6d58a7df1
```

구현은 위 file hash와 payload hash가 실제 artifact와 일치하지 않으면 training 전
중단한다. `*_file_sha256`은 파일 bytes의 SHA-256이고, `*_payload_sha256`은 JSON
payload 내부의 `policy_artifact_sha256` 값이다. 두 hash namespace를 혼합하지 않는다.

## 원인 진단

현재 policy feature path는 phase one-hot과 continuous task-state feature를 함께 쓴다.
핵심 code anchor:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
  featurize_step(...)
  fit_phase_conditioned_bc_policy(...)
  _phase_from_depth(...)
  rdf_compatible_metric_row_from_pose_values(...)

scripts/run_mvp2c_isaac_training_calibration.py
  _write_train_view_hdf5(...)
  _write_policy_artifacts(...)
  run_v06_expressibility_sanity_runtime(...)
```

현재 depth-derived phase는 다음 의미다.

```text
APPROACH: depth < 0.006
CONTACT : depth < 0.016
INSERT  : depth < insertion_depth_m_min
SEAT    : depth >= insertion_depth_m_min
```

이 phase는 expert controller의 z-gate와 무관하다. 따라서 같은 `APPROACH` 안에
다음 두 행동이 섞인다.

```text
ALIGN behavior: lateral gate가 닫힘 -> z action ~= 0
DESCEND behavior: lateral gate가 열림 -> z action ~= -0.16
```

`v0_7a`의 핵심 변경은 phase를 task progress label이 아니라 behavior-state
conditioning label로 바꾸는 것이다.

## v0.7a Behavior-State Phase Contract

`v0_7a`는 기존 `phase` field를 덮어쓰지 않는다. 기존 depth-derived phase는 audit용으로
보존하고, 새 derived field를 추가한다.

```text
original_depth_phase = row["phase"]
behavior_state_phase = one of ALIGN | DESCEND | HOLD
phase_label_source = frozen_v0_7a_behavior_state_rule
```

### Constants

```text
behavior_phase_schema = ["ALIGN", "DESCEND", "HOLD"]
approach_lateral_gate_m = 0.001
approach_lateral_gate_source = parent_v0_6i_controller_repair_config.approach_lateral_gate_m
seat_depth_threshold_m = 0.03
seat_depth_threshold_source = SUCCESS_METRIC.insertion_depth_m_min
orientation_gate_rad = 0.25
orientation_gate_source = parent_v0_6i_controller_repair_config.align_orientation_gate_rad
```

`orientation_gate_rad`는 report와 future extension을 위해 기록하지만, `v0_7a`
behavior-state phase assignment에는 사용하지 않는다. 이유는 현재 failure mode가
z-gate/lateral gate mismatch이고, orientation은 train-generation trace에서 지배 blocker로
관측되지 않았기 때문이다. 이 값을 phase assignment에 추가하려면 새 slice가 필요하다.

### Assignment Rule

각 row는 정확히 하나의 `behavior_state_phase`를 가져야 한다.

```text
if lateral_error_m > approach_lateral_gate_m:
    behavior_state_phase = "ALIGN"
elif lateral_error_m <= approach_lateral_gate_m and insertion_depth_m < seat_depth_threshold_m:
    behavior_state_phase = "DESCEND"
elif lateral_error_m <= approach_lateral_gate_m and insertion_depth_m >= seat_depth_threshold_m:
    behavior_state_phase = "HOLD"
else:
    stop: relabel_config_invalid
```

Equality handling:

```text
lateral_error_m == approach_lateral_gate_m -> DESCEND or HOLD branch
insertion_depth_m == seat_depth_threshold_m -> HOLD branch
```

Invalid row handling:

```text
missing lateral_error_m -> stop
missing insertion_depth_m -> stop
NaN or infinite lateral_error_m -> stop
NaN or infinite insertion_depth_m -> stop
negative insertion_depth_m -> clamp only if parent row already clamps it; otherwise stop
```

Reset-tail handling:

- Rows already accepted into `train_generation_runtime_gate.generated_success_trace_paths`
  are treated as post-reset-clean evidence.
- If any trace contains `reset_like_jump_count > 0` or post-reset exclusion metadata with
  excluded rows, only the pre-reset-clean rows may be relabeled.
- The relabel manifest must record `post_reset_rows_used=false` for excluded rows.

## Dataset Relabel Rules

`v0_7a` applies the same relabel transform to both dataset views.

```text
baseline_uncurated_view -> relabel with v0_7a rule
candidate_curated_view  -> relabel with v0_7a rule
```

Fairness invariants:

```text
same_behavior_phase_rule=true
same_feature_schema=true
same_trainer=true
same_hyperparameters=true
same_action_schema=true
same_action_adapter=true
same_max_steps=true
same_success_authority=true
only_dataset_view_differs=true
```

The previous depth-derived `phase` remains in `metadata_json` and report artifacts for audit.
The model feature vector uses `behavior_state_phase`, not the old `phase`.

## Feature Schema v0.7a

`v0_7a` replaces the four old phase one-hot fields with three behavior-state fields.

```text
feature_schema_v0_7a = [
  "behavior_phase_ALIGN",
  "behavior_phase_DESCEND",
  "behavior_phase_HOLD",
  "insertion_depth_m",
  "relative_x_m",
  "relative_y_m",
  "lateral_error_m",
  "orientation_error_deg",
  "previous_action_dx",
  "previous_action_dy",
  "previous_action_dz",
  "previous_action_rx",
  "previous_action_ry",
  "previous_action_rz",
  "previous_action_gripper"
]
```

Feature schema change requires new artifact schema versions:

```text
train_view_schema_version=rdf_mvp2e_v07a_behavior_phase_train_view_hdf5_v0.1.0
policy_artifact_schema_version=rdf_mvp2e_v07a_behavior_phase_policy_artifact_v0.1.0
relabel_manifest_schema_version=rdf_mvp2e_v07a_behavior_phase_relabel_manifest_v0.1.0
offline_train_fit_gate_schema_version=rdf_mvp2e_v07a_offline_train_fit_gate_v0.1.0
```

## Pre-Registration Artifact

Before relabeling, implementation must write:

```text
v0_7a_relabel_config.json
```

Required fields:

```text
schema_version
slice_id
scenario_profile
parent_artifact_hashes
behavior_phase_schema
approach_lateral_gate_m
approach_lateral_gate_source
seat_depth_threshold_m
seat_depth_threshold_source
assignment_rule_text
equality_handling
invalid_row_handling
reset_tail_handling
feature_schema_v0_7a
trainer
policy_class
ridge_lambda
baseline_noise_mix_ratio
offline_fit_metric_definitions
offline_fit_thresholds
offline_fit_aggregation_rule
heldout_21000_21049_accessed=false
proof_authority=false
relabel_config_sha256
```

Once `relabel_config_sha256` is written, these fields are immutable for `v0_7a`.

## Offline Train Fit Gate

`offline_train_fit_gate` runs after relabeling and policy training, before any Isaac
expressibility run.

Purpose:

```text
Do not spend Isaac runtime on a policy that cannot reconstruct its own training rows.
```

The blocking gate is candidate-only, because candidate curated policy is the one that
must express accepted expert behavior before calibration or held-out. Baseline metrics
are still reported but are not blocking, because baseline intentionally contains
rejected/noisy material.

### Candidate Required Phase Coverage

Candidate accepted rows must include all three behavior phases.

```text
candidate_phase_row_count.ALIGN > 0
candidate_phase_row_count.DESCEND > 0
candidate_phase_row_count.HOLD > 0
```

If `DESCEND` or `HOLD` is absent, stop before HDF5 export with:

```text
failure_reason=required_phase_missing
```

Failure traces in the baseline may have zero `HOLD` rows. That is expected and not a
hard stop as long as the combined baseline view and candidate view are both transformed
by the same relabel rule.

### Candidate Reconstruction Thresholds

Offline reconstruction is evaluated on training rows after fitting.

```text
candidate_xy_mae_max <= 0.01
candidate_z_mae_max <= 0.02
candidate_action_rmse_max <= 0.03
candidate_align_predicted_negative_z_rate <= 0.10
candidate_descend_predicted_negative_z_rate >= 0.80
candidate_descend_z_sign_agreement >= 0.90
candidate_hold_abs_z_mean <= 0.04
```

Aggregation and definitions:

```text
candidate_xy_mae_max =
  max over behavior phases present in candidate required phase set of
  mean over rows in that phase of
  (abs(predicted_action_dx - expert_action_dx) + abs(predicted_action_dy - expert_action_dy)) / 2

candidate_z_mae_max =
  max over behavior phases present in candidate required phase set of
  mean over rows in that phase of abs(predicted_action_dz - expert_action_dz)

candidate_action_rmse_max =
  max over behavior phases present in candidate required phase set of
  sqrt(mean over rows in that phase and all action dimensions of
       (predicted_action_dim - expert_action_dim)^2)

candidate_align_predicted_negative_z_rate =
  count(ALIGN rows where predicted_action_dz <= -0.08) / count(ALIGN rows)

candidate_descend_predicted_negative_z_rate =
  count(DESCEND rows where predicted_action_dz <= -0.08) / count(DESCEND rows)

candidate_descend_z_sign_agreement =
  count(DESCEND rows where sign_bucket(predicted_action_dz) == sign_bucket(expert_action_dz))
  / count(DESCEND rows)

candidate_hold_abs_z_mean =
  mean over HOLD rows of abs(predicted_action_dz)

sign_bucket(z): negative if z <= -0.08, zero if -0.08 < z < 0.02, positive if z >= 0.02
```

Denominator rules:

```text
Candidate ALIGN, DESCEND, HOLD denominator must each be > 0.
If any candidate required phase denominator is 0, do not compute the metric:
  passed=false
  failure_reason=required_phase_missing

Baseline metrics use the same aggregation where denominators exist.
If a baseline phase denominator is 0, record metric=null with
  baseline_metric_status.<phase>=phase_absent_report_only
This does not block v0.7a because baseline includes rejected/noisy material.
```

These thresholds, denominators, sign buckets, and aggregation rules are fixed before
v0.7a implementation. They must be serialized into `v0_7a_relabel_config.json` and
covered by `relabel_config_sha256` before policy training starts. If they fail, do not
tune the numbers or aggregation inside `v0_7a`.

### Gate Output

Write:

```text
offline_train_fit_gate.json
```

Required fields:

```text
schema_version
passed
candidate_gate_passed
baseline_report_only
candidate_phase_row_counts
baseline_phase_row_counts
candidate_xy_mae_max
candidate_z_mae_max
candidate_action_rmse_max
candidate_align_predicted_negative_z_rate
candidate_descend_predicted_negative_z_rate
candidate_descend_z_sign_agreement
candidate_hold_abs_z_mean
baseline_same_metrics_report_only
relabel_config_sha256
baseline_policy_artifact_sha256
candidate_policy_artifact_sha256
heldout_21000_21049_accessed=false
proof_authority=false
offline_train_fit_gate_sha256
```

## Expressibility Sanity Gate

Only if `offline_train_fit_gate.passed=true`, run the existing train-split expressibility
sanity check.

Unchanged gate:

```text
rollout_count=5
required_success_count=2
runtime_backend=isaac_runtime
success_authority=env_native_10_consecutive
heldout_21000_21049_accessed=false
proof_authority=false
```

The selected 5 seeds remain the first five success seeds from the existing
`train_generation_runtime_gate.generated_success_trace_paths`. Do not choose easier
seeds after seeing v0.7a offline metrics.

Pass:

```text
expressibility_sanity_gate.passed=true
success_count >= 2
```

Fail:

```text
expressibility_sanity_gate.passed=false
archive v0_7a as non-closing
do not run calibration
do not open held-out
```

## Calibration / Held-Out Boundary

`v0_7a` does not change Phase F/G rules.

Calibration can run only if:

```text
repair_probe_green_light=true
train_generation_runtime_gate.passed=true
offline_train_fit_gate.passed=true
expressibility_sanity_gate.passed=true
```

Held-out `21000-21049` can open only if:

```text
candidate_calibration_success > baseline_calibration_success
candidate_calibration_success >= 0.30
all policy/config/artifact hashes frozen
```

MVP-2 Closed still requires:

```text
runtime_backend=isaac_runtime
actual_rollouts_per_policy >= 20
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
learning_validator.learning_proven=true
learning_validator.proof_eligible=true
```

## v0.7b Fallback Boundary

`v0_7b` is pre-declared only as a fallback path.

Fallback trigger:

```text
v0_7a archived as failed
AND (
  offline_train_fit_gate.passed=false
  OR expressibility_sanity_gate.passed=false
)
```

Fallback candidate:

```text
policy_class=phase_conditioned_residual_servo_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0
trainer_family=phase_conditioned_residual_servo_bc
```

Guard:

- `v0_7b` requires a new spec and new pre-registration hash.
- Do not tune `v0_7b` constants using held-out `21000-21049`.
- Do not implement `v0_7b` in the same PR/slice as `v0_7a`.

## Failure Taxonomy

`v0_7a` introduces these failure reasons:

```text
parent_artifact_hash_mismatch
relabel_config_invalid
input_trace_missing
input_trace_hash_mismatch
row_missing_required_metric
required_phase_missing
offline_train_fit_failed
expressibility_failed
calibration_presignal_failed
heldout_negative
```

## Stop Rules

Stop before relabeling if:

- any parent artifact hash is missing or mismatched
- train_generation_runtime_gate is not `passed=true`
- failed expressibility parent hash is not recorded

Stop before HDF5 export if:

- any row cannot be assigned exactly one `ALIGN|DESCEND|HOLD`
- `behavior_state_phase` would overwrite the original depth-derived `phase`
- candidate accepted data has zero `DESCEND` or zero `HOLD` rows

Stop before Isaac expressibility if:

- `offline_train_fit_gate.passed != true`
- baseline and candidate do not share feature schema, trainer, hyperparameters,
  action adapter, and relabel config hash

Stop before calibration if:

- expressibility sanity is below `2/5`

Stop before held-out if:

- calibration pre-signal does not satisfy `candidate > baseline AND candidate >= 0.30`

Stop permanently for held-out `21000-21049` after Phase G if:

- candidate success rate is not greater than baseline success rate
- uplift is below `0.20`

No retuning against `21000-21049` is allowed.

## Buyer-Facing Limitation

`v0_7a` must keep this non-claim in proof and buyer-facing reports:

```text
This is an Isaac evaluator-domain learning proof using privileged task-state and
behavior-state phase features derived from frozen controller geometry gates.
It does not claim deployable real-world visual policy performance, real robot
success, physical robot readiness, HMD readiness, or universal robot support.
```

## Implementation Plan Handoff

The next document should be an implementation plan, not another design debate.

Required plan tasks:

1. Add relabel config builder and hash validation.
2. Add deterministic row relabeler preserving original `phase`.
3. Add v0.7a feature schema and HDF5 writer path.
4. Add v0.7a policy artifact metadata and trainer reuse.
5. Add offline train fit gate.
6. Wire expressibility sanity to require offline gate first.
7. Update reports, worklog, debugging guide, and handoff.
8. Verify with targeted tests, non-Isaac full tests, JSON validation, and no held-out access.
