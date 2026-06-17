# MVP-2E v0.7c Residual Action Authority Gate Design

Date: 2026-06-12

## 목적

`v0_7b`는 missing recovery source와 offline residual artifact 문제를 해결했다.

```text
shared_train_recovery_induction_v0_7b:
  passed=true
  runtime_backend=isaac_runtime
  trace_path_count=5

offline_residual_fit_gate_v0_7b:
  passed=true
  candidate_gate_passed=true
  phase_e_candidate_expressibility_unblocked=true

actual Isaac Phase E:
  passed=false
  success_count=0
  rollout_count=5
  required_success_count=2
  heldout_21000_21049_accessed=false
```

Phase E trace 진단:

```text
19003: ALIGN=148, depth_max=0.0, residual_z=-0.0907..-0.0014, post_adapter_z=-0.16..-0.0762
19012: ALIGN=148, depth_max=0.0, residual_z=-0.0895..0.0003, post_adapter_z=-0.16..-0.0223
19129: ALIGN=145 DESCEND=3, depth_max=0.0, residual_z=0.0015..0.0941, post_adapter_z=0.0157..0.16
19030: ALIGN=145 DESCEND=3, depth_max=0.0, residual_z=-0.1617..0.0002, post_adapter_z=-0.16..-0.0269
19119: ALIGN=147 DESCEND=1, depth_max=0.0, residual_z=0.0089..0.0945, post_adapter_z=0.16..0.16
```

진단:

```text
base_servo_action.z is small and gated.
learned residual.z bypasses that gate.
selected action adapter then saturates z in ALIGN.
```

`v0_7c`의 목적은 `v0_7b`를 사후 패치하지 않고, 새 policy slice에서
post-residual action authority를 pre-register하는 것이다.

## 비목표

`v0_7c`는 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- calibration을 실행하지 않는다.
- env-native success authority, `stable_steps=10`, `max_steps=150`을 바꾸지 않는다.
- Phase E threshold `>=2/5`를 완화하지 않는다.
- `v0_7b` artifact를 성공처럼 소급 변경하지 않는다.
- candidate 전용 controller, candidate 전용 adapter, candidate 전용 residual clip을 만들지 않는다.
- full-action BC로 되돌아가지 않는다.
- retry / withdraw / search / force-control policy를 구현하지 않는다.
- real robot policy, visual policy performance, physical readiness, universal robot support를 주장하지 않는다.

## 검토한 선택지

### Option A: Offline residual target gate만 강화

offline metric에 `ALIGN` z residual MAE와 z sign violation을 추가한다.

장점:

- 구현 범위가 작다.
- Isaac 실행 전에 잘못된 policy artifact를 더 많이 차단한다.

단점:

- runtime covariate shift에서 residual이 다시 큰 z를 낼 수 있다.
- `v0_7b`의 실제 원인인 "post-residual action authority 부재"를 막지 못한다.

결론: 보조 gate로는 필요하지만 primary fix로는 부족하다.

### Option B: Post-residual action authority gate

runtime prediction 순서를 다음처럼 바꾼다.

```text
base_action = frozen_base_geometry_servo(state)
residual_prediction = residual_policy(feature(state))
raw_action_before_authority = base_action + residual_prediction
raw_action_after_authority = action_authority_filter(
  behavior_state_phase,
  base_action,
  residual_prediction,
  raw_action_before_authority
)
post_adapter_action = selected_action_adapter(raw_action_after_authority)
```

장점:

- `v0_7b` 실패 원인을 직접 막는다.
- base servo와 residual policy의 책임 경계를 명확히 만든다.
- baseline/candidate가 같은 authority gate를 공유하므로 A/B fairness가 유지된다.

단점:

- base servo가 policy action을 더 강하게 제한하므로, final held-out uplift claim은
  "same action-authority scaffold 위에서의 curated-vs-uncurated residual policy 비교"로
  더 좁게 표현해야 한다.

결론: 채택한다.

### Option C: 더 강한 residual model class로 이동

linear NumPy residual BC를 버리고 MLP, sequence policy, recovery-aware policy class로 이동한다.

장점:

- 표현력이 올라간다.

단점:

- 현재 실패 원인은 표현력 이전에 action authority 부재다.
- policy class를 크게 바꾸면 curation effect와 architecture effect가 섞인다.
- calibration/held-out 봉인 상태에서는 아직 정당화가 약하다.

결론: `v0_7c`에서 하지 않는다. `v0_7c`가 fail-closed된 뒤 별도 spec으로만 검토한다.

## 핵심 결정

`v0_7c`는 `v0_7b`의 residual target과 dataset view를 계승하되,
runtime action authority layer를 추가한다.

```text
policy_slice = v0_7c
slice_id = mvp2e_v07c_residual_action_authority_gate
base_servo_id = frozen_base_geometry_servo_v0_7b
residual_target_definition = actual_trace_action_minus_frozen_base_geometry_servo_action
authority_filter_id = frozen_residual_action_authority_gate_v0_7c
```

`base_servo_id`는 `v0_7b`와 동일하게 유지한다. 새로 freeze되는 것은
base servo가 아니라 residual 이후 action authority contract다.

## Action Authority Contract

### Runtime 순서

반드시 아래 순서를 따른다.

```text
1. runtime state에서 behavior_state_phase 계산
2. residual_policy(feature) 예측
3. frozen_base_geometry_servo(state) 계산
4. raw_action_before_authority = base_action + residual_prediction
5. raw_action_after_authority = v0_7c_action_authority_filter(...)
6. selected_action_adapter(raw_action_after_authority)
7. diagnostics 기록
```

adapter를 먼저 적용하거나, adapter 이후에 authority filter를 적용하면 fail-closed한다.

### Behavior phase별 authority

`v0_7c`는 `v0_7a_2` behavior-state rule을 계승한다.

```text
HOLD    := env_native_success_mask is true
DESCEND := not HOLD AND lateral_error_m <= 0.001
ALIGN   := not HOLD AND lateral_error_m > 0.001
```

`ALIGN`:

```text
raw_action_after_authority[:2] = raw_action_before_authority[:2]
raw_action_after_authority[2] = base_action[2]
raw_action_after_authority[3:] = raw_action_before_authority[3:]
align_residual_z_suppressed = true
```

의미:

- lateral/yaw correction은 residual이 보정할 수 있다.
- z motion authority는 base servo가 갖는다.
- learned residual은 ALIGN에서 down/up z push를 만들 수 없다.

`DESCEND`:

```text
raw_action_after_authority = raw_action_before_authority
align_residual_z_suppressed = false
```

`HOLD`:

```text
raw_action_after_authority = raw_action_before_authority
align_residual_z_suppressed = false
```

`DESCEND/HOLD` z residual까지 막으면 successful insertion과 seated hold를 표현하지
못할 수 있으므로 `v0_7c`에서는 막지 않는다. 만약 `v0_7c` Phase E가 descent/hold z
문제로 fail-closed되면, 그 변경은 `v0_7d`에서 별도 pre-register한다.

### 필수 diagnostics

runtime trace row는 다음을 기록한다.

```text
base_servo_action
residual_prediction
raw_action_before_authority
raw_action_after_authority
post_adapter_action_vector
authority_filter_id
authority_filter_config_sha256
behavior_state_phase
align_residual_z_suppressed
residual_z_before_authority
residual_z_after_authority
z_authority_source
```

`ALIGN`에서 기대되는 값:

```text
z_authority_source = base_servo
raw_action_after_authority[2] == base_servo_action[2]
residual_z_after_authority == 0.0
align_residual_z_suppressed == true
```

`DESCEND/HOLD`에서 기대되는 값:

```text
z_authority_source = base_plus_residual
raw_action_after_authority[2] == raw_action_before_authority[2]
align_residual_z_suppressed == false
```

## Config / Hash Contract

새 artifact:

```text
v0_7c_action_authority_config.json
```

필수 필드:

```text
schema_version = rdf_mvp2e_v07c_action_authority_config_v0.1.0
policy_slice = v0_7c
slice_id = mvp2e_v07c_residual_action_authority_gate
authority_filter_id = frozen_residual_action_authority_gate_v0_7c
base_servo_id = frozen_base_geometry_servo_v0_7b
base_servo_config_sha256
residual_target_definition = actual_trace_action_minus_frozen_base_geometry_servo_action
behavior_phase_rule_version = env_native_hold_v0_7a_2
selected_action_adapter_id
align_z_authority = base_servo_z_only
descend_z_authority = base_plus_residual
hold_z_authority = base_plus_residual
heldout_21000_21049_accessed = false
candidate_specific = false
baseline_specific = false
authority_filter_config_sha256
```

hash는 `authority_filter_config_sha256` 자신을 제외한 canonical JSON payload로 계산한다.

## Dataset / Recovery Source

`v0_7c`는 `v0_7b`의 train-side shared recovery induction source를 재사용할 수 있다.
이 source는 shared frozen base servo로 생성됐고, policy-specific source가 아니며,
held-out을 열지 않았기 때문이다.

재사용 가능한 source 조건:

```text
shared_train_recovery_induction_v0_7b.passed == true
source_policy_slice == none
policy_specific_source == false
proof_authority == false
heldout_21000_21049_accessed == false
trace_path_count == 5
```

조건 중 하나라도 깨지면 `v0_7c` offline build는 fail-closed한다.

`v0_7c`는 train rows의 residual target definition을 바꾸지 않는다.

```text
residual_target = actual_trace_action - base_servo_action
```

새로운 authority filter는 training target을 바꾸는 것이 아니라 runtime action
authority를 제한한다.

## Offline Gate

`v0_7c`는 `v0_7b` offline residual fit gate를 계승하고, action-authority gate를 추가한다.

필수 gate:

```text
offline_residual_fit_gate_v0_7c.passed == true
offline_action_authority_gate_v0_7c.passed == true
```

`offline_action_authority_gate_v0_7c` 필수 metric:

```text
candidate_align_row_count > 0
baseline_align_row_count > 0
candidate_align_z_suppression_rate == 1.0
baseline_align_z_suppression_rate == 1.0
candidate_align_raw_z_equals_base_z_rate >= 0.999
baseline_align_raw_z_equals_base_z_rate >= 0.999
candidate_align_residual_z_after_authority_abs_max <= 1e-9
baseline_align_residual_z_after_authority_abs_max <= 1e-9
candidate_authority_filter_config_sha256 == baseline_authority_filter_config_sha256
candidate_selected_action_adapter_id == baseline_selected_action_adapter_id
heldout_21000_21049_accessed == false
```

이 gate는 Phase E를 쉽게 만들기 위한 threshold 완화가 아니다. `v0_7b`에서 누락된
action authority invariant를 Isaac 실행 전에 검증하는 fail-closed gate다.

## Phase E Expressibility Gate

Phase E는 `v0_7b`와 같은 train-split sanity role을 유지한다.

```text
input policy = candidate v0_7c residual policy artifact
seeds = fixed Phase E train seeds inherited from v0_7b
rollouts = 5
pass = env-native 10-consecutive success >= 2/5
closure_authority = false
heldout_21000_21049_accessed = false
```

Phase E 통과는 MVP-2 Closed가 아니다. Phase E 통과 후에만 별도
calibration freeze plan으로 이동한다.

Phase E 실패 시:

```text
v0_7c failed_closed = true
calibration_opened = false
heldout_opened = false
next_valid_step = diagnose from v0_7c traces
```

## Artifact Layout

새 output dir:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7c_residual_action_authority_gate/
```

필수 artifact:

```text
v0_7c_action_authority_config.json
v0_7c_residual_action_authority_manifest.json
candidate_curated_train_v0_7c.hdf5
baseline_uncurated_train_v0_7c.hdf5
candidate_policy_artifact_v0_7c.json
baseline_policy_artifact_v0_7c.json
offline_residual_fit_gate_v0_7c.json
offline_action_authority_gate_v0_7c.json
expressibility_sanity_gate_v0_7c.json
```

각 policy artifact는 다음을 포함해야 한다.

```text
policy_slice = v0_7c
policy_class = phase_conditioned_residual_servo_bc_policy_v0
trainer = rdf_numpy_phase_conditioned_residual_servo_bc_trainer_v0
base_servo_plus_learned_residual = true
base_servo_id = frozen_base_geometry_servo_v0_7b
base_servo_config_sha256
residual_target_definition
authority_filter_id = frozen_residual_action_authority_gate_v0_7c
authority_filter_config_sha256
selected_action_adapter_id
heldout_21000_21049_accessed = false
```

## Tests

필수 test coverage:

- `v0_7c` authority config가 hash-stable이고 held-out access를 기록하지 않는다.
- `ALIGN` row에서 residual z가 suppression되어 `raw_action_after_authority[2] == base_action[2]`가 된다.
- `DESCEND/HOLD` row에서는 residual z가 suppression되지 않는다.
- policy artifact가 authority config/hash를 누락하면 runtime이 fail-closed한다.
- runtime diagnostics가 `raw_action_before_authority`, `raw_action_after_authority`,
  `post_adapter_action_vector`를 모두 기록한다.
- offline action-authority gate가 `ALIGN` z violation을 잡고 Phase E를 막는다.
- baseline/candidate가 서로 다른 authority config 또는 adapter를 쓰면 fail-closed한다.
- `v0_7c` full run은 금지되고, offline-only / expressibility-only mode만 허용된다.
- expressibility-only는 offline residual fit gate와 offline action authority gate가 둘 다 통과하기 전에는
  Isaac을 시작하지 않는다.
- held-out `21000-21049` access flag가 하나라도 true이면 fail-closed한다.

## Claim Boundary

`v0_7c` 통과 후 주장 가능한 것:

```text
ForgeXR/RDF has a pre-registered residual action authority policy slice that
prevents learned residuals from bypassing the base servo ALIGN z gate, and can
test candidate train-split expressibility without opening held-out scenarios.
```

`v0_7c`만으로 주장 금지:

```text
MVP-2 Closed
positive policy uplift
held-out A/B success
real robot success
deployable real-world visual policy
physical robot readiness
HMD readiness
universal robot support
```

MVP-2 Closed는 여전히 다음을 요구한다.

```text
Phase E pass
calibration freeze
sealed held-out A/B on 21000-21049
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
```

## 실행 순서

1. `v0_7c` authority config helper와 tests를 추가한다.
2. runtime evaluator에 post-residual authority filter를 추가한다.
3. offline build에 `v0_7c` child slice를 추가한다.
4. offline residual fit gate와 offline action authority gate를 생성한다.
5. offline gates가 통과한 뒤에만 actual Isaac Phase E를 실행한다.
6. Phase E 통과 시 별도 calibration freeze plan으로 이동한다.
7. Phase E 실패 시 calibration/held-out을 열지 않고 trace diagnostic만 문서화한다.

## Self-review

- Placeholder scan: incomplete marker와 unresolved threshold 없음.
- Scope check: `v0_7c`는 residual action authority gate만 다룬다.
- Ambiguity check: authority filter order, phase별 z authority, offline gates,
  Phase E stop condition, held-out boundary를 명시했다.
- Claim boundary: MVP-2 Closed, held-out uplift, real robot/HMD readiness claim 금지를 명시했다.
