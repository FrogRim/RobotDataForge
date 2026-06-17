# MVP-2E v0.7d Action Authority Post-Adapter Z Gate Design

Date: 2026-06-12

Status: pre-implementation design

## 목적

`v0_7c`는 residual z를 `ALIGN`에서 suppress했지만 실제 Isaac Phase E는
`0/5`로 fail-closed됐다. harness-gated closure report는 원인을 다음처럼
분류했다.

```text
primary_root_cause_class=ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK
secondary_root_cause_candidates=[
  BASE_SERVO_PREMATURE_DESCENT,
  PHASE_LABEL_RUNTIME_MISMATCH
]
recommended_downstream_slice=v0_7d_action_authority_post_adapter_z_gate
```

핵심 증거:

```text
residual_z_after_authority = 0.0
base_servo_z = -0.001
selected action adapter z_action_scale = 32.0
post_adapter_z = -0.032
ALIGN post_adapter_z_violation_count = 727 / 727
```

즉 현재 authority filter는 adapter 이전 action에는 적용되지만, selected action
adapter가 마지막 mutation으로 z 하강을 다시 만든다. `v0_7d`의 목적은 마지막
action mutation 이후에 config-independent final action authority를 적용하여
이 leak를 차단하는 것이다.

Claude review에서 추가로 확인한 네 번째 authority mismatch도 같은 slice에
포함한다.

```text
selected_adapter_config.stable_hold_depth_m = 0.03
selected_adapter_config.stable_hold_lateral_m = 0.006
observed env-native seating depth ~= 0.024-0.025
```

`stable_hold` readiness가 geometry threshold를 closure authority처럼 쓰면
env-native mask가 참이어도 hold action으로 전환되지 못할 수 있다. 따라서
`v0_7d`는 post-adapter z authority와 stable-hold env-native authority를 같은
authority-layer repair로 묶는다.

## 비목표

`v0_7d`는 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- calibration을 실행하지 않는다.
- env-native success authority, `stable_steps=10`, `max_steps=150`을 바꾸지 않는다.
- Phase E threshold `>=2/5`를 완화하지 않는다.
- `v0_7c` evidence를 성공 evidence로 소급 변경하지 않는다.
- selected action adapter config를 candidate에 유리하게 재선택하거나 튜닝하지 않는다.
- policy class, trainer, feature schema, baseline/candidate fairness contract를 바꾸지 않는다.
- retry / withdraw / search / force-control runtime을 구현하지 않는다.
- real robot success, physical readiness, HMD/OpenXR readiness, visual policy performance를 claim하지 않는다.

## Authority Invariant

`v0_7d`의 핵심 invariant는 다음이다.

```text
All safety-critical z-motion and stable-hold authority must be evaluated
after the final action mutation point and must use the env-native authority
where seating/hold success is being judged.
```

구체적으로:

- adapter 이전 `raw_action_after_authority`만으로는 충분하지 않다.
- selected action adapter 이후 `post_adapter_action_vector`가 최종 검증 대상이다.
- `ALIGN`에서 z motion이 허용되지 않으면 final `post_adapter_action_vector[2]`는
  반드시 `0.0`이어야 한다.
- 이 final z gate는 adapter instrumentation config 유무와 무관하게 작동해야 한다.
- `adapter_not_instrumented`, `no_v06_controller` 같은 상태는 진단 reason일 수는
  있어도 gate bypass 조건이 될 수 없다.
- `stable_hold` readiness는 env-native success mask / consecutive-window authority를
  사용해야 하며, `stable_hold_depth_m`, `stable_hold_lateral_m` 같은 geometry
  상수는 report-only diagnostic으로 강등하거나 제거한다.

## Runtime 순서

`v0_7d` runtime action path는 다음 순서를 따른다.

```text
1. behavior_state_phase 계산
2. residual_policy(feature) 예측
3. frozen_base_geometry_servo(state) 계산
4. raw_action_before_authority = base_action + residual_prediction
5. pre_adapter_authority(raw_action_before_authority)
6. selected_action_adapter(pre_adapter_action)
7. final_post_adapter_authority(post_adapter_action, behavior_state_phase, env_native_mask)
8. env.step(final_action)
9. diagnostics 기록
```

`final_post_adapter_authority`는 마지막 mutation 이후에 위치한다. 이후에는 어떤
adapter, scale, clip, normalization도 action을 다시 바꿀 수 없다.

## Final Post-Adapter Z Authority

`ALIGN`:

```text
if z_motion_allowed is not true:
  final_action[2] = 0.0
  z_motion_block_reason = concrete_reason
```

필수 조건:

- `final_action[2]`는 adapter scale 적용 후에도 `0.0`이어야 한다.
- `z_motion_block_reason`은 `adapter_not_instrumented`로 남으면 안 된다.
- `phase_controller`가 없거나 adapter config가 오래된 경우에도 final z gate는 꺼지면 안 된다.
- gate 적용은 baseline/candidate 모두 동일해야 한다.

`DESCEND` / `INSERT`:

- pre-registered behavior-state rule이 z motion을 허용하는 경우에만 z action을 통과시킨다.
- env-native success metric이나 threshold는 바꾸지 않는다.

`HOLD`:

- env-native success mask가 true이고 consecutive-window를 누적할 수 있도록 hold action을 허용한다.
- hold readiness는 geometry threshold가 아니라 env-native mask authority를 따른다.

## Stable-Hold Authority Repair

현재 H12는 다음 artifact를 failure로 분류한다.

```text
selected_action_adapter.json:
  stable_hold_depth_m=0.03
  stable_hold_lateral_m=0.006
  stable_hold_orientation_deg=8.0
  stable_hold_uses_env_native_mask=null
```

`v0_7d`에서 stable-hold readiness는 다음 중 하나여야 한다.

```text
stable_hold_authority = "env_native_success_mask"
stable_hold_uses_env_native_mask = true
```

geometry threshold는 다음처럼만 사용할 수 있다.

- buyer-facing secondary diagnostic
- report-only trace evidence
- failure explanation 보조 필드

geometry threshold가 hold action 진입을 veto하면 fail-closed한다.

## Train / Eval Parity

`v0_7d`는 expert generation, offline gate, policy rollout 모두 같은 authority
contract를 사용해야 한다.

필수 parity evidence:

- `final_post_adapter_authority_id`
- `final_post_adapter_authority_config_sha256`
- `stable_hold_authority`
- `stable_hold_authority_config_sha256`
- baseline/candidate 동일 여부
- train/eval 동일 여부

## Offline Gates

Isaac Phase E를 열기 전에 다음 offline gate가 통과해야 한다.

```text
offline_final_action_authority_gate_v0_7d:
  all ALIGN rows:
    residual_z_after_authority == 0.0
    final_post_adapter_action_vector[2] == 0.0
    z_motion_block_reason != "adapter_not_instrumented"
  H12:
    stable_hold_authority == "env_native_success_mask"
  candidate/baseline:
    same selected adapter
    same authority config sha256
    same stable-hold authority sha256
```

이 gate가 실패하면 Isaac Phase E를 실행하지 않는다.

## Phase E 재실행 조건

offline gate가 통과하면 기존 Phase E threshold를 유지하고 실제 Isaac sanity를
재실행한다.

```text
rollout_count=5
required_success_count=2
success_authority=env_native_10_consecutive
heldout_21000_21049_accessed=false
calibration_opened=false
```

Phase E가 통과해야 calibration으로 넘어갈 수 있다. Phase E가 실패하면
`v0_7d`를 성공 evidence로 사용하지 않고, 새 harness report를 생성한다.

## Buyer / Public Claim Boundary

`v0_7d`가 성공해도 아직 MVP-2 Closed가 아니다.

허용되는 claim:

```text
The action-authority repair allowed the MVP-2E candidate policy to pass the
train-split Isaac expressibility sanity gate.
```

금지되는 claim:

```text
MVP-2 Closed
policy uplift proven
curated > uncurated held-out improvement proven
real robot success
physical readiness
HMD/OpenXR readiness
visual policy performance
deployable policy
```

## 다음 실행 단위

다음 단계는 이 spec 기준의 implementation plan이다.

우선순위:

1. `final_post_adapter_authority` unit tests를 RED로 작성한다.
2. stable-hold env-native authority tests를 RED로 작성한다.
3. evaluator runtime path에 final post-adapter gate를 배선한다.
4. `selected_action_adapter` stable-hold geometry thresholds를 authority에서 제거하거나 report-only로 강등한다.
5. offline `v0_7d` gate를 생성한다.
6. focused tests와 compile/lint를 통과시킨다.
7. offline gate 통과 후에만 Phase E를 별도 실행한다.
