# MVP-2E v0.7e Shared Hysteresis Parity Repair Design

Date: 2026-06-15

Status: pre-implementation design

## 목적

`v0_7d`는 final post-adapter z authority와 env-native stable-hold
authority를 offline gate까지 통과시켰지만, 실제 Isaac Phase E
expressibility sanity는 `0/5`로 fail-closed됐다.

artifact-only autoresearch 결과는 실패 원인을 다음처럼 지지한다.

```text
z_window_hypothesis_verdict=supported
root_cause=runtime phase/action-authority parity failure
```

같은 train-side scenario에서 expert는 `v0_6_active_state_controller`를
사용해 긴 z-descent window를 유지했고, policy runtime은 stateful controller
없이 순간 lateral gate에 의해 z window가 짧게 끊겼다.

```text
seed 19003: expert z streak=32, policy z streak=0
seed 19012: expert z streak=43, policy z streak=4
seed 19030: expert z streak=28, policy z streak=4
seed 19119: expert z streak=38, policy z streak=2
seed 19129: expert z streak=32, policy z streak=3
```

expert는 `depth>0`에 도달하지만 policy는 모든 sampled trace에서
`max_insertion_depth_m=0.0`으로 남았다. 따라서 `v0_7e`의 목적은 policy
runtime에 shared stateful hysteresis controller parity를 복원하고, 그 복원이
baseline/candidate 차이를 지우지 않는지 offline으로 확인한 뒤에만 Phase E를
다시 여는 것이다.

## 비목표

`v0_7e`는 다음을 하지 않는다.

- calibration을 실행하지 않는다.
- held-out `21000-21049`를 열지 않는다.
- policy uplift, MVP-2 Closed, curated > uncurated held-out improvement를 claim하지 않는다.
- env-native success authority, `stable_steps=10`, Phase E threshold `>=2/5`를 바꾸지 않는다.
- selected action adapter를 재선택하거나 candidate에 유리하게 튜닝하지 않는다.
- trainer family, feature schema, baseline/candidate fairness contract를 바꾸지 않는다.
- policy를 새로 큰 모델로 교체하지 않는다.
- retry, withdraw, search, force-control runtime을 도입하지 않는다.
- real robot success, physical readiness, HMD/OpenXR readiness, visual policy performance를 claim하지 않는다.

## 근거 Artifact

설계 근거는 아래 artifact에 고정한다.

```text
.omx/specs/autoresearch-mvp2e-v07e-hysteresis-parity/result.json
.omx/specs/autoresearch-mvp2e-v07e-hysteresis-parity/completion.json
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7d_action_authority_post_adapter_z_gate/
```

boundary evidence:

```text
analysis_generated_from_existing_json_only=true
isaac_rerun_performed=false
policy_training_performed=false
calibration_opened=false
heldout_21000_21049_accessed=false
mvp2_closed=false
policy_uplift_proven=false
```

## 핵심 판단

`v0_7d` 실패는 z sign 문제나 env 물리 실패가 아니다. 성공 expert trace가 같은
env/task에서 z 하강을 유지해 `depth>0`에 도달했기 때문이다.

핵심 차이는 controller parity다.

```text
expert_controller_versions=["v0_6_active_state_controller"]
expert_stateful_controller_present=true
policy_controller_versions=[]
policy_stateful_controller_present=false
policy_dominant_z_motion_block_reason=final_post_adapter_align_z_blocked
policy_dominant_z_motion_block_reason_fraction=0.982432
```

policy trace에서는 lateral이 `0.001m` gate 안으로 잠깐 들어간 뒤 xy saturation
때문에 바로 gate 밖으로 나가고, final post-adapter authority가 z를 다시
막는다. 그 결과 z-descent window가 2-4 step 수준으로 쪼개져 hole entrance에
도달하지 못한다.

offline counterfactual은 물리 성공을 증명하지 않는다. 다만 recorded policy
state에 stateful hysteresis를 적용하면 `19012`, `19030`, `19119`, `19129`에서
expert-scale `28` step z-open window가 만들어질 수 있음을 보여준다. `19003`은
기존 trace에서 lateral gate entry 자체가 없어 counterfactual도 `0`으로 남는다.

## Authority Invariant

`v0_7e`는 `v0_7d`의 final action authority invariant를 유지한다.

```text
No selected adapter, scale, clip, normalization, or controller may mutate
the action after final post-adapter authority.
```

추가 invariant:

```text
Z-motion permission must be stateful and rollout-local, not an instantaneous
single-row lateral-threshold decision.
```

구체적으로:

- stateful hysteresis controller는 baseline과 candidate에 동일하게 적용한다.
- controller state는 rollout 시작마다 reset한다.
- controller state는 관측된 task-state와 이전 controller state에서 결정적으로 계산한다.
- shared hysteresis는 policy-specific advantage가 아니라 train/eval parity repair다.
- final post-adapter authority는 shared hysteresis가 허용하지 않는 z motion을 계속 차단한다.
- env-native success mask와 stable-hold authority는 geometry threshold로 대체하지 않는다.

## v0.7e Runtime Action Path

`v0_7e` runtime은 다음 순서를 따른다.

```text
1. task_state / metric_row 읽기
2. shared_stateful_hysteresis_controller.update(metric_row, previous_state)
3. behavior_state_phase 계산
4. residual_policy(feature) 예측
5. frozen_base_geometry_servo(state) 계산
6. raw_action = base_action + residual_prediction
7. pre_adapter_authority(raw_action, hysteresis_state)
8. selected_action_adapter(pre_adapter_action)
9. final_post_adapter_authority(post_adapter_action, hysteresis_state, env_native_mask)
10. env.step(final_action)
11. diagnostics 기록
```

`shared_stateful_hysteresis_controller`는 final authority 이전에 z permission을
계산하지만, 최종 enforcement는 반드시 step 9에서 수행한다.

## Shared Hysteresis Controller

`v0_7e`는 새로운 search controller를 만들지 않는다. 목표는 expert generation에서
이미 쓰인 `v0_6_active_state_controller` 계열의 stateful z-window semantics를
policy runtime에 동일하게 복원하는 것이다.

기본 state:

```text
ALIGN
DESCEND
INSERT
HOLD
```

entry rule:

```text
ALIGN -> DESCEND:
  lateral_error_m <= approach_lateral_gate_m
  AND orientation_error within existing frozen authority tolerance
```

hold rule:

```text
Once DESCEND opens, keep z_motion_allowed=true through the frozen
stateful controller window unless a hard safety escape condition fires.
```

diagnostic lower bound:

```text
min_descend_window_reference_steps=28
source=minimum successful expert z-descent streak in shared train-side evidence
```

`28`은 success threshold가 아니다. 이는 policy path가 expert-scale z window를
전혀 만들지 못하는지 확인하는 offline diagnostic lower bound다. 실제 runtime
controller config는 가능한 한 기존 `v0_6_active_state_controller` config와
lineage를 공유해야 한다.

hard safety escape는 Phase E를 쉽게 만들기 위한 튜닝 knob가 아니다. lateral이
gross escape 수준으로 커져 z 하강을 유지하면 명백히 off-center descent가 되는
경우를 fail-closed로 막는 장치다. `0.001m` 근처 chatter는 hard safety escape가
아니며, 그 chatter를 제거하는 것이 이 slice의 목적이다.

## XY Saturation 처리

autoresearch 결과는 z-open row에서 xy saturation rate가 `1.0`으로 관측된 trace가
있음을 보여준다.

`v0_7e`에서는 xy gain, selected adapter scale, base servo gain을 먼저 바꾸지
않는다. 이 slice의 변수는 stateful hysteresis parity 복원 하나로 제한한다.

필수 diagnostic:

```text
xy_saturation_rate_during_z_open
lateral_gate_exit_step
lateral_at_open_end_m
lateral_next_step_m
z_motion_block_reason_after_gate_exit
```

Phase E가 계속 실패하되 z window가 복원되어 있다면 다음 root cause는 xy
saturation 또는 contact/insert dynamics로 재분류한다. 그 경우 별도 `v0_7f`
slice를 설계한다.

## Offline Gates

Isaac Phase E를 다시 열기 전에 `v0_7e`는 아래 offline gate를 모두 통과해야 한다.

### 1. Hysteresis Parity Gate

artifact:

```text
offline_hysteresis_parity_gate_v0_7e.json
```

필수 조건:

```text
heldout_21000_21049_accessed=false
calibration_opened=false
isaac_rerun_performed=false
policy_training_performed=false
same_hysteresis_config_for_baseline_and_candidate=true
same_final_post_adapter_authority_for_baseline_and_candidate=true
same_selected_action_adapter_for_baseline_and_candidate=true
```

v0.7d trace counterfactual 기준:

```text
scenario_count=5
counterfactual_z_window_ge_28_count >= 3
seed_19030_counterfactual_z_window_ge_28=true
```

현재 autoresearch evidence는 `4/5`가 이 조건을 만족한다. 이 gate는 기존 trace
기반 offline sanity이며 실제 success claim이 아니다.

### 2. Attribution Preservation Gate

artifact:

```text
attribution_preservation_gate_v0_7e.json
```

shared hysteresis가 baseline/candidate 양쪽에 동일 적용되면 Phase E는 풀리지만
후속 A/B에서 차이가 사라질 수 있다. 따라서 Phase E 전에 최소한 policy artifact
차이가 runtime action 차이로 남아 있는지 확인한다.

필수 조건:

```text
candidate_baseline_artifacts_differ=true
shared_infrastructure_equalities_all_true=true
candidate_baseline_action_delta_l2_mean > 1e-6
candidate_baseline_action_delta_nonzero_fraction >= 0.10
```

측정 대상은 train-side offline rows와 v0.7d/v0.7e policy artifacts다. held-out,
calibration, Isaac rerun 결과를 읽으면 fail-closed한다.

이 gate가 실패하면 Phase E를 열지 않는다. shared hysteresis가 policy 차이를
지워버렸다면 Phase E 통과 가능성과 무관하게 MVP-2 A/B signal이 약해진 것이다.

### 3. Final Authority Regression Gate

artifact:

```text
final_action_authority_regression_gate_v0_7e.json
```

필수 조건:

```text
ALIGN rows without z permission:
  final_post_adapter_action_vector[2] == 0.0

DESCEND/INSERT rows with z permission:
  z action may pass

HOLD rows:
  stable_hold_authority == "env_native_success_mask"
```

`v0_7e`는 `v0_7d`에서 고친 post-adapter z leak와 stable-hold authority를
되돌리면 안 된다.

## Phase E 재실행 조건

아래가 모두 참일 때만 실제 Isaac Phase E를 다시 실행한다.

```text
offline_hysteresis_parity_gate_v0_7e.passed=true
attribution_preservation_gate_v0_7e.passed=true
final_action_authority_regression_gate_v0_7e.passed=true
heldout_21000_21049_accessed=false
calibration_opened=false
```

Phase E 기준은 그대로 유지한다.

```text
rollout_count=5
required_success_count=2
success_authority=env_native_10_consecutive
seed_scope=train-side expressibility sanity only
```

Phase E가 통과해도 MVP-2 Closed가 아니다. Phase E 통과는 calibration을 열 수
있는 선행 조건일 뿐이다.

## Failure Handling

offline gate 실패:

```text
Do not run Isaac.
Classify the failed gate and write a new repair note.
```

Phase E 실패, z window 미복원:

```text
Classify as hysteresis parity implementation failure.
Do not proceed to calibration.
```

Phase E 실패, z window 복원됨:

```text
Classify next root cause as xy saturation, contact/insert dynamics,
or policy residual quality. Open a new harness report before any next repair.
```

Phase E 통과, attribution gate 약함:

```text
Do not proceed to held-out.
Design a separate data-effect guard before calibration.
```

## Artifact Contract

`v0_7e`는 아래 artifact를 생성해야 한다.

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7e_shared_hysteresis_parity_repair/
  v0_7e_hysteresis_authority_config.json
  candidate_policy_artifact_v0_7e.json
  baseline_policy_artifact_v0_7e.json
  offline_hysteresis_parity_gate_v0_7e.json
  attribution_preservation_gate_v0_7e.json
  final_action_authority_regression_gate_v0_7e.json
  v0_7e_shared_hysteresis_parity_manifest.json
```

Phase E를 실제 실행한 뒤에만 추가 artifact를 생성한다.

```text
  expressibility_sanity_gate_v0_7e.json
  isaac_runtime_expressibility_sanity_v0_7e/
```

## Buyer / Public Claim Boundary

`v0_7e` 설계와 offline gate 통과만으로 허용되는 claim:

```text
The v0.7d Phase E failure was traced to a runtime parity gap:
the policy path lacked the stateful z-window controller used by the
successful expert generation path.
```

Phase E 통과 후에만 허용되는 claim:

```text
The candidate policy passed the train-split Isaac expressibility sanity gate
after restoring shared stateful hysteresis parity.
```

계속 금지되는 claim:

```text
MVP-2 Closed
policy uplift proven
curated > uncurated held-out improvement proven
real robot success
physical readiness
HMD/OpenXR readiness
visual policy performance
deployable policy
universal robot support
```

## 다음 실행 단위

다음 단계는 이 spec 기준의 implementation plan이다.

우선순위:

1. `v0_7e` shared hysteresis config and lineage artifact를 RED test로 고정한다.
2. offline hysteresis parity counterfactual gate를 구현한다.
3. attribution preservation gate를 구현한다.
4. final action authority regression gate를 구현한다.
5. policy runtime path에 shared stateful hysteresis controller를 baseline/candidate 공통으로 배선한다.
6. focused pytest, compile, lint, `git diff --check`를 통과시킨다.
7. offline gates가 모두 통과한 뒤에만 Phase E 재실행을 별도 단계로 수행한다.
