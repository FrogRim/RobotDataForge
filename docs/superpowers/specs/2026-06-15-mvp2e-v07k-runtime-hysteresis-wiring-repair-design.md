# MVP-2E v0.7k Runtime Hysteresis Wiring Repair 설계

## 목적

`v0_7j` actual Isaac calibration pre-signal은 `baseline=0/30`, `candidate=0/30`으로 fail-closed 됐다.

trace 진단상 `v0_7j`의 final XY authority는 적용됐지만, policy prediction 경로의 stateful hysteresis wiring에서 `v0_7j`가 누락되어 `last_z_motion_allowed`가 runtime에 전달되지 않았다. 결과적으로 `behavior_state_phase=DESCEND` rows에서도 `v07e_hysteresis_z_motion_blocked`가 발생했고, 모든 rollout의 `negative_z_steps=0`, `max_depth=0`이 됐다.

`v0_7k`는 새 success metric이나 trainer가 아니라 runtime wiring repair slice다.

## 변경

- `v0_7j` parent policy artifact를 보존한다.
- `v0_7k` child policy artifact는 `v0_7j` authority config를 그대로 상속한다.
- policy prediction 경로에서 `v0_7j`/`v0_7k`를 stateful hysteresis, residual base-servo, pre-adapter authority 대상에 포함한다.
- final z authority, final XY authority, env-native success authority는 변경하지 않는다.
- `v0_7j` failed calibration artifact는 parent evidence로 보존한다.

## Gate

`v0_7k` offline runtime wiring gate는 다음을 확인한다.

- parent `v0_7j` calibration pre-signal이 actual Isaac에서 실패했고 held-out은 열리지 않았다.
- child baseline/candidate policy artifact가 같은 shared hysteresis config, final z authority config, final XY authority config를 유지한다.
- child policy artifact의 `policy_slice`만 `v0_7k`로 승격되며 success metric과 calibration threshold는 불변이다.

## Calibration

`v0_7k` calibration pre-signal은 기존 calibration split `20000-20029`만 사용한다.

pass 조건은 기존과 동일하다.

- candidate success rate > baseline success rate
- candidate success rate >= 0.30
- held-out `21000-21049` 미접근

## Non-claims

- `v0_7k` calibration pass는 MVP-2 Closed가 아니다.
- MVP-2 Closed는 여전히 held-out A/B에서 curated > uncurated positive uplift가 필요하다.
- real robot, HMD/OpenXR, visual policy, deployable policy claim은 금지한다.
