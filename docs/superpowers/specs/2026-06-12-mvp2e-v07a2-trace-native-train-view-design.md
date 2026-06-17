# MVP-2E v0.7a.2 Trace-Native Full-Horizon Train View Design

Date: 2026-06-12

## 목적

`v0_7a_1`은 `HOLD` authority를 `env_native_success_mask`로 고정하는 데 성공했지만,
actual proof는 정직하게 fail-closed됐다.

```text
v0_7a_1 result:
  parent_proof_chain_verdict.passed=true
  candidate_trace_enriched_rows=1280
  candidate_authenticated_rows_used=1280
  candidate_phase_row_counts: ALIGN=1280, DESCEND=0, HOLD=0
  offline_train_fit_gate.passed=false
  failure_reason=required_phase_missing
  heldout_21000_21049_accessed=false
```

해석:

```text
env-native HOLD rule이 틀린 것이 아니다.
parent candidate_curated_train.hdf5 view가 runtime trace의 seated/HOLD window를
포함하지 않는 것이 blocker다.
```

`v0_7a_2`의 목적은 HDF5 parent row를 억지로 재해석하지 않고,
`train_generation_runtime_gate.json.generated_trace_paths`의 actual Isaac runtime trace를
직접 train row source로 사용해 full-horizon train view를 만드는 것이다.

이 slice는 MVP-2 Closed 선언이 아니다. 이 slice의 성공은 Phase E expressibility와
이후 calibration/A-B로 가기 위한 training-view blocker 제거를 의미한다.

## 비목표

`v0_7a_2`는 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- calibration `20000-20029`를 실행하지 않는다.
- 새 Isaac train-generation rollout을 만들지 않는다.
- train seed, probe seed, held-out seed를 교체하지 않는다.
- env-native success authority, stable window `N=10`, max horizon을 바꾸지 않는다.
- `HOLD` threshold를 geometry 상수로 완화하지 않는다.
- `v0_7a` 또는 `v0_7a_1` artifact를 소급 수정하지 않는다.
- policy class를 residual servo BC로 바꾸지 않는다.
- deployable real robot policy, visual policy performance, physical robot readiness,
  HMD readiness, universal robot support를 주장하지 않는다.

## 현재 증거

`v0_7a_1` run 결과:

```text
candidate trace hydration: works
candidate authenticated HDF5 rows: 1280
candidate HOLD rows after env-native relabel: 0
expressibility guard: missing_passed_v0_7a_1_offline_train_fit_gate
Isaac runtime started: false
held-out accessed: false
```

trace 직접 확인:

```text
train_generation_runtime_gate.generated_trace_paths count = 40
train_generation_runtime_gate.generated_success_trace_paths count = 28
first runtime trace length = 125
runtime trace row contains:
  step
  env_native_success
  env_native_success_mask
  insertion_depth_m
  relative_x_m
  relative_y_m
  lateral_error_m
  orientation_error_deg
  normalized_action
  controller_action_diagnostics
last row example:
  step=124
  env_native_success_mask=true
  insertion_depth_m≈0.024873
  lateral_error_m≈0.000447
```

따라서 full-horizon runtime trace에는 seated/HOLD row가 존재하지만,
parent `candidate_curated_train.hdf5`에서 matching된 row window는 trace 초반에 머물러
HOLD가 사라진다.

## 핵심 결정

`v0_7a_2`는 HDF5 parent view를 primary row source로 쓰지 않는다.

```text
primary row source:
  train_generation_runtime_gate.json
    generated_trace_paths[]
    generated_success_trace_paths[]

candidate curated view:
  generated_success_trace_paths의 full trace rows
  env_native_success_mask 기반 behavior_state_phase

baseline uncurated view:
  generated_trace_paths 전체의 full trace rows
  즉 success + failure attempts를 고정된 uncurated mix로 사용
  baseline_failure_mix_ratio는 결과를 보지 않고 parent gate에서 산출:
    (generated_rollout_count - generated_success_count) / generated_rollout_count
```

이 구조는 curation effect를 다음처럼 고정한다.

```text
candidate = accepted/success trace rows only
baseline  = uncurated all attempt rows (success + failure)
```

장점:

- candidate와 baseline이 같은 runtime source와 같은 feature/trainer/action adapter를 사용한다.
- baseline에 실패 attempt가 포함되지만, 실패 비율은 parent gate의 고정 evidence에서 온다.
- easy seed cherry-picking이나 threshold relaxation이 없다.
- future A/B를 위한 baseline policy artifact를 동시에 만들 수 있다.

주의:

- baseline failure mix는 "고의로 망가뜨린 데이터"가 아니라 fixed 40-run train-generation의
  uncurated view다.
- `v0_7a_2`는 아직 held-out success uplift를 증명하지 않는다.

## Behavior-State Phase Rule

`v0_7a_1`의 authority invariant를 그대로 상속한다.

```text
HOLD    := row.env_native_success_mask == true
DESCEND := (not HOLD) AND lateral_error_m <= approach_lateral_gate_m
ALIGN   := (not HOLD) AND lateral_error_m > approach_lateral_gate_m

approach_lateral_gate_m = 0.001
behavior_phase_rule_version = env_native_hold_v0_7a_2
```

`env_native_success`와 `env_native_success_mask`가 동시에 존재하면 둘은 같은 boolean이어야 한다.
충돌하면 fail-closed.

`seat_depth_threshold_m`, `SUCCESS_METRIC.insertion_depth_m_min`,
`insertion_depth_m >= constant`는 behavior phase assignment에 사용할 수 없다.

## Runtime Trace Row Contract

각 trace row는 train row로 쓰기 전에 다음 validation을 통과해야 한다.

필수 field:

```text
step
env_native_success_mask 또는 env_native_success
insertion_depth_m
relative_x_m
relative_y_m
lateral_error_m
orientation_error_deg
normalized_action
```

validation:

```text
step은 non-negative int이고 trace 내부에서 strictly increasing
env_native_success_mask는 bool로 해석 가능해야 함
required metric은 finite number
insertion_depth_m은 negative 불가
normalized_action은 ACTION_SCHEMA 길이로 변환 가능해야 함
trace file sha256은 manifest에 기록
trace path는 train_generation_runtime_gate.generated_trace_paths에 포함되어야 함
```

action handling:

```text
runtime trace의 normalized_action을 existing ACTION_SCHEMA 길이로 정규화한다.
6-dim action이면 existing helper와 같은 방식으로 gripper component를 보강한다.
새 action adapter를 만들지 않는다.
```

reset handling:

```text
trace가 env_reset_boundary_steps 또는 reset-like marker를 기록하면
post-reset row는 train view에서 제외하고 manifest count로 남긴다.
이번 slice는 reset recovery policy를 학습하지 않는다.
```

## Training Views

output root:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_2_trace_native_train_view/
```

required train views:

```text
candidate_curated_train_v0_7a_2.hdf5
baseline_uncurated_train_v0_7a_2.hdf5
```

candidate view:

```text
source_paths = train_generation_runtime_gate.generated_success_trace_paths
source_trace_count = generated_success_count
requires source_trace_count >= 20
requires HOLD rows > 0
requires per-success-trace max consecutive env-native mask >= 10
```

baseline view:

```text
source_paths = train_generation_runtime_gate.generated_trace_paths
source_trace_count = generated_rollout_count
contains success + failure attempts
baseline_noise_mix_ratio =
  (generated_rollout_count - generated_success_count) / generated_rollout_count
failure_type_distribution =
  derived from trace summary / reason fields when present,
  otherwise "trace_failed_env_native_window_missing" bucket
```

row metadata:

```text
policy_slice = v0_7a_2
source_trace_path
source_trace_sha256
source_trace_role = candidate_success | baseline_uncurated
trace_step
behavior_state_phase
behavior_phase_rule_version
env_native_success_mask
original_metric_phase
```

## Policy Artifacts

`v0_7a_2` keeps the same policy class as `v0_7a_1`.

```text
policy_class = phase_conditioned_numpy_bc_policy_v0
feature_schema = FEATURE_SCHEMA_V07A
behavior_phase_rule_version = env_native_hold_v0_7a_2
trainer = rdf_numpy_phase_conditioned_bc_trainer_v0
selected_action_adapter = parent selected_action_adapter
```

required artifacts:

```text
v0_7a_2_trace_native_config.json
v0_7a_2_trace_native_manifest.json
candidate_curated_train_v0_7a_2.hdf5
baseline_uncurated_train_v0_7a_2.hdf5
candidate_policy_artifact_v0_7a_2.json
baseline_policy_artifact_v0_7a_2.json
offline_train_fit_gate_v0_7a_2.json
expressibility_sanity_gate_v0_7a_2.json
```

Every artifact includes:

```text
v0_7a_2_trace_native_config_sha256
parent_train_generation_runtime_gate_sha256
heldout_21000_21049_accessed=false
proof_authority=false until held-out A/B
```

## Offline Fit Gate

candidate gate:

```text
candidate_phase_row_counts must include ALIGN, DESCEND, HOLD all > 0
candidate_z_mae_max <= 0.02
candidate_xy_mae_max <= 0.01
candidate_hold_abs_z_mean <= 0.04
candidate_action_rmse_max <= 0.03
candidate_align_predicted_negative_z_rate <= 0.10
candidate_descend_predicted_negative_z_rate >= 0.80
candidate_descend_z_sign_agreement >= 0.90
```

baseline metrics:

```text
baseline_policy_artifact must be written if baseline view has valid rows.
baseline offline metrics are reported with the same schema.
baseline failure does not by itself authorize threshold changes.
future A/B remains blocked if baseline artifact is missing.
```

`offline_train_fit_gate_v0_7a_2.passed=true` means:

```text
candidate policy can enter Phase E expressibility sanity.
It does not mean MVP-2 Closed.
It does not mean calibration or held-out A/B can run automatically.
```

## Phase E Expressibility

Phase E may run only when:

```text
offline_train_fit_gate_v0_7a_2.passed=true
candidate_policy_artifact_v0_7a_2.json exists
behavior_phase_rule_version=env_native_hold_v0_7a_2
heldout_21000_21049_accessed=false
```

Phase E criteria inherit the existing expressibility sanity gate:

```text
train split diagnostic seeds only
5 rollouts
pass if candidate env-native success >= 2/5
no calibration
no held-out
```

If Phase E fails:

```text
record fail-closed evidence
next valid step = v0_7b residual servo BC spec
do not change v0_7a_2 phase thresholds
```

If Phase E passes:

```text
next valid step = calibration presignal gate with baseline/candidate v0_7a_2 policies
held-out still sealed until calibration freeze
```

## Tests

Required focused tests:

```text
trace-native config forbids seat_depth_threshold_m
trace row with env_native_success_mask=true becomes HOLD regardless of depth
trace row with mask=false and lateral<=gate becomes DESCEND
trace row with mask=false and lateral>gate becomes ALIGN
env_native_success / env_native_success_mask conflict fails closed
missing normalized_action fails closed
6-dim normalized_action is converted to ACTION_SCHEMA length consistently
candidate view uses generated_success_trace_paths only
baseline view uses generated_trace_paths exactly
baseline_noise_mix_ratio is derived from parent gate counts, not manual input
candidate view contains HOLD rows from real trace tail
candidate per-success-trace hold windows are counted
runtime prediction uses env_native_hold_v0_7a_2 rule only for v0_7a_2 artifacts
v0_7a and v0_7a_1 compatibility paths remain unchanged
offline gate blocks Phase E when candidate gate fails
expressibility sanity rejects missing passed v0_7a_2 offline gate before Isaac import
held-out 21000-21049 remains unopened in all v0_7a_2 offline commands
```

## 실행 명령

Offline trace-native train view + policy fit:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a_2 \
  --offline-relabel-only \
  --pretty
```

Phase E expressibility sanity only after offline gate passes:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a_2 \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Verification:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a2 or v0_7a_2 or trace_native" -q

uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

## Stop Conditions

Stop and report if:

```text
train_generation_runtime_gate.json is missing or passed=false
generated_success_trace_paths count < 20
trace rows do not contain env_native_success/env_native_success_mask
trace rows do not contain normalized_action
trace action cannot be converted to ACTION_SCHEMA without inventing semantics
candidate trace-native view still has HOLD=0
candidate offline fit gate fails
Phase E candidate expressibility is <2/5
baseline policy cannot be written from generated_trace_paths
implementation requires held-out 21000-21049
implementation requires calibration before Phase E
implementation requires changing env-native success authority
implementation requires changing policy class to residual servo BC
```

Stop result interpretation:

```text
candidate trace-native HOLD=0:
  trace source assumption is wrong; inspect runtime trace format again.

candidate offline fit fails:
  phase-conditioned NumPy BC cannot fit actual trace-native expert rows;
  next step is v0_7b residual servo BC.

Phase E fails:
  offline fit does not transfer to Isaac rollout;
  next step is v0_7b residual servo BC.
```

## Claim Boundary

Allowed claim after successful offline gate:

```text
ForgeXR can construct a trace-native full-horizon train view from actual Isaac
runtime train-generation evidence and train a phase-conditioned BC candidate
policy that fits the expert rows offline.
```

Allowed claim after Phase E pass:

```text
The candidate policy is expressible enough to reproduce basic train-split
Isaac insertion behavior in a small sanity gate.
```

Forbidden claim:

```text
MVP-2 Closed
positive held-out policy uplift
robust public benchmark
real robot success
deployable visual policy
physical robot readiness
HMD/OpenXR readiness
```

MVP-2 Closed still requires:

```text
calibration freeze
fresh held-out A/B
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
actual_rollouts_per_policy >= 20
```
