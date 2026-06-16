# MVP-2E v0.7b Residual Servo BC Design

Date: 2026-06-12

## 목적

`v0_7a_2`는 trace-native full-horizon train view와 env-native `HOLD`
authority를 올바르게 만들었다. 그러나 actual Isaac train-split Phase E는
정직하게 fail-closed됐다.

```text
v0_7a_2 offline gate:
  passed=true
  candidate_phase_row_counts={ALIGN:1973, DESCEND:1422, HOLD:284}
  baseline_phase_row_counts={ALIGN:3321, DESCEND:1826, HOLD:308}
  candidate_xy_mae_max=0.001105
  candidate_z_mae_max=0.013433
  heldout_21000_21049_accessed=false

v0_7a_2 actual Isaac Phase E:
  runtime_backend=isaac_runtime
  passed=false
  success_count=0
  rollout_count=5
  required_success_count=2
  reason=candidate policy did not pass train-split expressibility sanity
  heldout_21000_21049_accessed=false
```

해석:

```text
train-view / HOLD row / offline fit 문제는 해결됐다.
남은 blocker는 full-action BC가 closed-loop rollout에서 expert state machine을
안정적으로 재현하지 못하는 policy-class 문제다.
```

`v0_7b`의 목적은 full-action BC를 버리고, 같은 frozen base geometry servo 위에서
baseline과 candidate가 각각 residual만 학습하게 만드는 것이다.

```text
policy_action =
  selected_action_adapter(
    frozen_base_geometry_servo(state) + residual_policy(state)
  )
```

`v0_7b`는 MVP-2 Closed 선언이 아니다. 이 slice의 성공은 Phase E
expressibility sanity를 다시 열고, 이후 calibration freeze와 held-out A/B로
갈 수 있음을 의미한다.

## 비목표

`v0_7b`는 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- held-out result를 보고 base servo, residual clip, trainer threshold를 조정하지 않는다.
- success metric, env-native authority, stable window `N=10`, max horizon을 바꾸지 않는다.
- `HOLD` 또는 success 판정을 geometry proxy threshold로 되돌리지 않는다.
- baseline/candidate에 다른 base servo, 다른 adapter, 다른 trainer, 다른 feature schema를 주지 않는다.
- scripted expert 또는 base servo 자체를 evaluated policy로 주장하지 않는다.
- calibration recovery rows를 final training set에 섞지 않는다.
- retry / withdraw / search / force-control policy를 구현하지 않는다.
- deterministic/proxy/synthetic backend를 MVP-2 closure evidence로 승격하지 않는다.
- deployable real robot policy, visual policy performance, physical robot readiness,
  HMD readiness, universal robot support를 주장하지 않는다.

## 핵심 결정

### 1. Full-action BC 폐기

`v0_7a_2`는 offline row reconstruction을 통과했지만 actual Isaac Phase E에서
`0/5`였다. 따라서 다음 valid step은 threshold 완화가 아니라 policy action
authority를 바꾸는 것이다.

기존 full-action BC:

```text
policy(state) -> full normalized_action
```

`v0_7b` residual servo BC:

```text
base_action = frozen_base_geometry_servo(state)
residual_target = actual_trace_action - base_action
policy_action = base_action + residual_policy(state)
```

이 변경은 "더 강한 candidate 전용 controller"가 아니다. baseline과 candidate가
동일한 base servo와 동일한 residual trainer를 공유하고, 차이는 dataset view만
남는다.

### 2. Frozen base geometry servo

모든 `v0_7b` policy는 같은 base geometry servo를 사용한다.

필수 속성:

```text
base_servo_id = frozen_base_geometry_servo_v0_7b
base_servo_config_sha256 = required
base_servo_source = v0_6 geometry controller family / existing weak servo prior
heldout_tuned = false
candidate_specific = false
baseline_specific = false
closing_gate = false
```

base servo는 direction prior와 stability scaffold를 제공한다. 단, base servo가
혼자 task success를 만들어 MVP-2 claim을 대신하면 안 된다. 그래서 `v0_7b`는
`base_only_diagnostic`을 필수 artifact로 남긴다.

```text
base_only_diagnostic:
  closing_gate=false
  can_close_mvp2=false
  heldout_excluded=true
  reports confound risk only
```

base-only diagnostic이 강하게 성공하더라도 MVP-2는 닫히지 않는다. 최종
authority는 여전히 동일 base servo 위의 baseline residual policy와 candidate
residual policy 간 held-out A/B다.

### 3. Dataset view만 다르게 유지

baseline과 candidate가 공유해야 하는 것:

```text
frozen_base_geometry_servo
base_servo_config_sha256
residual_target_definition
feature_schema
behavior_phase_rule_version
trainer implementation
trainer hyperparameters
selected_action_adapter_id
selected_action_adapter_config
action_schema
action clipping
offline residual fit thresholds
Phase E train seeds
calibration selector rule
held-out scenarios
```

달라질 수 있는 유일한 것:

```text
candidate = curated / accepted trace-native residual rows + shared train recovery overlay
baseline  = uncurated all-attempt trace-native residual rows + shared train recovery overlay
```

shared recovery overlay를 둘 다 받기 때문에 curation contrast가 약해질 수 있다.
그럼에도 candidate가 이기면 claim은 더 방어 가능하다. candidate가 이기지 못하면
그 결과도 valid non-closing evidence로 남긴다.

## Residual Target Contract

각 train row는 기존 `normalized_action`을 직접 target으로 쓰지 않는다.

```text
actual_trace_action = ACTION_SCHEMA 길이로 정규화된 runtime action
base_action = frozen_base_geometry_servo(metric_row)
residual_target = actual_trace_action - base_action
```

row-level required metadata:

```text
actual_trace_action
base_servo_action
residual_target
residual_target_definition=actual_trace_action_minus_frozen_base_geometry_servo_action
base_servo_config_sha256
behavior_phase_rule_version=env_native_hold_v0_7a_2
source_trace_sha256
proof_role
```

허용하지 않는 target:

```text
held_out_action - base_action
post-held-out retuned expert action - base_action
candidate-only oracle relabel
direct synthetic correction label without source/proof_role
```

runtime prediction은 반드시 아래 순서를 따른다.

```text
1. feature(state) 계산
2. residual_policy(feature) 예측
3. frozen_base_geometry_servo(state) 계산
4. raw_action_before_adapter = base_action + residual_prediction
5. selected_action_adapter + clipping 적용
6. diagnostics에 base_action/residual_prediction/raw_action_before_adapter 기록
```

adapter가 residual 이전에 적용되거나, baseline/candidate가 서로 다른 adapter를 쓰면
fail-closed한다.

## Train / Calibration Closed-loop Recovery Data

`v0_7b`는 closed-loop recovery data를 사용한다. 단, 이 data는 accepted success
trajectory를 늘리는 증거가 아니라, off-nominal state에서 residual policy가 무엇을
해야 하는지 알려주는 correction evidence다.

### Train-side recovery rows

train-side recovery rows는 final residual training view에 포함할 수 있다.

원칙:

```text
split = train only
seed source = existing v0_6/v0_7 train split, protected held-out 제외
state induction policy = shared frozen base servo or shared pre-registered zero-residual policy
labeling policy = frozen scripted expert / controller label
target = expert_action - base_servo_action
same row budget for baseline and candidate
same recovery rows appended to both views
proof_role=train_closed_loop_recovery_correction
accepted_success_trace_count에 포함 금지
```

이 설계는 DAgger식 closed-loop correction의 안전한 절반만 가져온다. policy-specific
online data를 baseline/candidate별로 다르게 수집하지 않는다. 그렇게 하면 curation
uplift가 online collection strategy 차이와 섞이기 때문이다.

금지:

```text
candidate policy로 방문한 state만 candidate에 추가
baseline policy로 방문한 state만 baseline에 추가
held-out state recovery label 생성
retry/withdraw/search sequence를 accepted trajectory로 승격
```

### Calibration recovery rows

calibration closed-loop recovery data는 final training set에 섞지 않는다.

사용 가능:

```text
shared residual clip / regularization / adapter config selector
base-only confound diagnostic
candidate/baseline feasibility diagnostic
selector_score_pre_registered=true
selected_config_used_for_both_policies=true
```

사용 불가:

```text
final residual policy fitting rows
candidate-only hyperparameter choice
held-out threshold tuning
MVP-2 closure evidence
```

calibration recovery rows를 학습에 섞고 싶다면 `v0_7b`가 아니라 별도 spec에서
calibration role을 다시 정의해야 한다.

## Behavior Phase / Feature Schema

`v0_7b`는 `v0_7a_2` behavior phase rule을 상속한다.

```text
HOLD    := env_native_success_mask == true
DESCEND := not HOLD AND lateral_error_m <= 0.001
ALIGN   := not HOLD AND lateral_error_m > 0.001

behavior_phase_rule_version = env_native_hold_v0_7a_2
```

착좌/성공 authority는 env-native mask다. geometry values
(`insertion_depth_m`, `lateral_error_m`, `orientation_error_deg`)는 feature와
diagnostic으로 남지만 success authority가 아니다.

Feature schema는 baseline/candidate가 동일해야 한다. `phase` 또는
`behavior_state_phase`를 한쪽에만 추가하거나 제거하면 fail-closed한다.

## Offline Gates

`v0_7b`는 Isaac Phase E 전에 offline residual fit gate를 통과해야 한다.

필수 checks:

```text
candidate/baseline residual row count > 0
candidate/baseline ALIGN/DESCEND/HOLD rows present
base_servo_config_sha256 identical
selected_action_adapter_config_sha256 identical
trainer_hyperparameters_sha256 identical
residual_target_definition identical
heldout_21000_21049_accessed=false
protected held-out seed range absent from trace payloads and filenames
```

권장 residual fit metrics:

```text
candidate_residual_xy_mae_max
candidate_residual_z_mae_max
candidate_reconstructed_action_xy_mae_max
candidate_reconstructed_action_z_mae_max
candidate_hold_abs_z_mean
baseline metrics report-only
```

threshold는 implementation plan에서 current `v0_7a_2` action MAE gate와 residual
scale을 대조해 pre-register한다. threshold 완화로 Phase E를 열 수 없다.

## Phase E Expressibility Gate

Phase E는 train-split sanity다. MVP-2 closure가 아니다.

```text
input policy = candidate residual policy artifact
runtime_backend = isaac_runtime
rollout_count = 5
required_success_count = 2
success authority = env-native 10-consecutive success
heldout_21000_21049_accessed=false
```

통과하면 calibration selector/freeze 단계로 간다. 실패하면 `v0_7b`는
fail-closed되고, 다음 valid step은 더 강한 residual policy class 또는 additional
train-side recovery row 설계다. success metric 완화는 금지한다.

## Calibration / Held-out Flow

`v0_7b`의 downstream flow:

```text
1. offline residual fit gate
2. candidate Phase E expressibility sanity (5 train seeds, >=2/5)
3. calibration recovery selector / shared config freeze
4. baseline and candidate final artifacts frozen
5. held-out A/B on sealed 21000-21049
```

held-out A/B는 다음 조건을 만족해야 MVP-2 Closed 후보가 된다.

```text
actual_rollouts_per_policy >= 20
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
learning_validator.proof_eligible=true
evidence_tier=external_heldout_policy_eval
mvp2_closed=true
```

`v0_7b` spec 작성 또는 Phase E 통과만으로는 MVP-2 Closed가 아니다.

## Artifact Contract

Output root:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7b_residual_servo_bc/
```

Required artifacts:

```text
v0_7b_residual_servo_config.json
v0_7b_residual_servo_manifest.json
train_closed_loop_recovery_manifest_v0_7b.json
calibration_recovery_manifest_v0_7b.json
base_servo_only_diagnostic_v0_7b.json
candidate_curated_train_v0_7b.hdf5
baseline_uncurated_train_v0_7b.hdf5
candidate_policy_artifact_v0_7b.json
baseline_policy_artifact_v0_7b.json
offline_residual_fit_gate_v0_7b.json
expressibility_sanity_gate_v0_7b.json
```

Policy artifact required fields:

```text
policy_class=phase_conditioned_residual_servo_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0
trainer_family=phase_conditioned_residual_servo_bc
base_servo_plus_learned_residual=true
base_servo_id
base_servo_config
base_servo_config_sha256
residual_target_definition
behavior_phase_rule_version
feature_schema
selected_action_adapter_id
selected_action_adapter_config_sha256
same_feature_schema_as_peer=true
same_trainer_hyperparameters_as_peer=true
same_base_servo_as_peer=true
```

Top-level reports must state that `v0_7b` uses privileged Isaac task-state
features and does not claim deployable visual policy or real robot readiness.

## Tests

Focused tests must cover:

```text
- v0_7b config requires base_servo_config_sha256 and residual_target_definition.
- residual target = actual_trace_action - base_servo_action.
- reconstructed action = base_servo_action + residual_prediction before adapter.
- selected action adapter is applied after residual reconstruction.
- baseline/candidate policy artifacts share base_servo_config_sha256.
- baseline/candidate policy artifacts share trainer hyperparameters and feature schema.
- candidate/baseline differ only by dataset view metadata.
- train closed-loop recovery rows are shared overlay rows for both views.
- calibration recovery rows are not included in final train HDF5.
- recovery rows cannot reference protected held-out seeds 21000-21049.
- base_only_diagnostic has closing_gate=false and can_close_mvp2=false.
- Phase E rejects missing or failed offline_residual_fit_gate_v0_7b.
- runtime prediction logs base_action, residual_prediction, raw_action_before_adapter.
- v0_7a_2 behavior remains unchanged.
```

## Expected Commands

Implementation plan should turn these into exact runnable commands.

```bash
# offline residual views + policies + residual fit gate (Isaac 불필요)
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7b \
  --offline-relabel-only --pretty

# offline gate 통과 후에만 Phase E (Isaac 1세션)
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7b \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

## Stop Conditions

다음 상황에서는 fail-closed하고 보고한다.

```text
- base_servo_config_sha256가 baseline/candidate 사이에서 다름
- residual_target_definition이 artifact 사이에서 다름
- baseline/candidate adapter 또는 clipping이 다름
- calibration recovery rows가 final train HDF5에 섞임
- train recovery rows가 held-out seed range를 참조함
- base servo가 held-out 결과를 보고 조정됨
- Phase E를 offline residual fit gate 없이 실행해야 함
- Phase E가 0~1/5로 실패함
- success metric / env-native authority / stable window 완화가 필요해짐
- held-out 21000-21049 접근이 필요해짐
```

## Acceptance Criteria

`v0_7b` implementation은 다음을 만족해야 완료다.

```text
- v0_7b residual servo config가 hash-stable artifact로 생성된다.
- baseline/candidate train views는 residual target을 저장한다.
- baseline/candidate policy artifacts는 동일 base servo, 동일 adapter,
  동일 trainer, 동일 feature schema를 증명한다.
- train-side closed-loop recovery rows는 shared overlay로 기록된다.
- calibration recovery rows는 selector/freeze 전용으로 기록되고 train rows에 섞이지 않는다.
- base-only diagnostic은 report-only / non-closing으로 남는다.
- offline residual fit gate가 통과해야 Phase E를 실행할 수 있다.
- Phase E가 actual Isaac에서 >=2/5 env-native success를 달성해야 calibration으로 진행한다.
- held-out 21000-21049는 계속 봉인된다.
```

## Claim Boundary

`v0_7b` 통과 후 주장 가능한 것:

```text
same frozen base geometry servo 위에서 curated residual policy와 uncurated
residual policy를 공정하게 비교할 수 있는 policy class와 train/calibration
precondition을 만들었다.
```

`v0_7b`만으로 주장 금지:

```text
MVP-2 Closed
positive held-out policy uplift
real robot success
deployable visual policy
HMD/OpenXR readiness
physical robot readiness
universal robot support
public robust benchmark
```

## Spec Self-review

- Placeholder scan: 미결정 표식 없음.
- Scope check: `v0_7b` residual servo BC와 train/calibration recovery data 경계만 다룬다.
- Ambiguity check: residual target, action authority order, baseline/candidate fairness,
  recovery row split, calibration non-training role, held-out boundary를 명시했다.
- Proof integrity check: held-out 봉인, env-native authority, stable window, same-base-servo
  fairness guard를 유지한다.
