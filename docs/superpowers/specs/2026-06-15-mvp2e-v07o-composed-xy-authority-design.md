# MVP-2E v0.7o Composed XY Authority Design

## 목적

`v0_7n` actual Isaac calibration pre-signal은 fail-closed 되었다.

- baseline: 1/30
- candidate: 1/30
- candidate success rate: 0.033333333333
- failure reason: `candidate_calibration_not_above_baseline`
- held-out `21000-21049`: unopened

`v0_7n`은 z-open + low-depth 구간의 sign mismatch를 수리하려 했지만,
실제 trace 비교 결과 parent `v0_7m`보다 calibration 성능이 후퇴했다.

## 새 진단

`v0_7m`은 parent `v0_7j`의 piecewise XY authority를 계속 사용했다.

- `xy_saturation_off_center_state_feedback_clamped`
- `xy_saturation_near_center_clamped_to_state_feedback`
- 일부 `xy_authority_sign_mismatch_not_applied`

반면 `v0_7n`은 strategy를 `z_open_center_maintenance_state_feedback_clip`로
교체하면서 z-open 외 구간의 parent piecewise XY authority가 꺼졌다.

결과:

- candidate 평균 z-open row: `v0_7m=37.86`, `v0_7n=11.5`
- candidate success: `v0_7m=4/30`, `v0_7n=1/30`
- 많은 seed가 z-open 전에 ALIGN에서 gate에 도달하지 못했다.

즉 `v0_7n`의 의도는 "z-open override 추가"였지만 구현 의미는
"parent ALIGN XY authority 교체"가 되었다. 이것은 의도한 repair보다 넓은
행동 변경이다.

## v0.7o Repair

`v0_7o`는 final post-adapter XY authority를 composition으로 정의한다.

1. 기본 경로:
   - parent `v0_7m`/`v0_7j`의 piecewise XY authority를 그대로 유지한다.
   - off-center saturated action은 off-center clip으로 state-feedback한다.
   - near-center saturated action은 near-center clip으로 state-feedback한다.
   - 기존 sign-preservation guard는 유지한다.

2. 좁은 override:
   - z-open 상태
   - low-depth (`insertion_depth_m <= 0.001`)
   - near-center (`lateral_error_m <= 0.006`)
   - env-native success가 아직 아님
   - 이 경우에만 sign-preservation guard보다 center-maintenance state-feedback을
     우선한다.

## 고정값

- `xy_authority_strategy=composed_piecewise_plus_z_open_center_maintenance`
- parent piecewise 값은 `v0_7m` policy artifact에서 상속한다.
- `z_open_centering_depth_max_m=0.001`
- `z_open_centering_lateral_m=0.006`
- `z_open_xy_authority_gain=4.0`
- `z_open_xy_clip_abs=0.05`
- `allow_sign_flip_during_z_open_low_depth=true`

## 변경하지 않는 것

- env-native 10-consecutive success authority
- trainer family / weights / feature schema
- selected action adapter
- final post-adapter z authority
- shared hysteresis z-window config
- calibration seed set
- held-out seed set

## Parent / Boundary

- parent는 failed-closed `v0_7n` calibration pre-signal이다.
- `v0_7n` artifacts는 역사적 실패 증거로 보존한다.
- `v0_7o`는 `v0_7n`을 수정하지 않고 새 slice로 생성한다.
- held-out `21000-21049`는 계속 봉인한다.

## Pass Criteria

Offline gate:

- parent `v0_7n` calibration gate가 failed-closed여야 한다.
- baseline/candidate가 동일 v0.7o XY authority config를 사용해야 한다.
- parent piecewise behavior가 z-open 외 구간에서 유지되어야 한다.
- z-open low-depth override가 z를 변형하지 않고 XY만 조정해야 한다.

Actual calibration pre-signal:

- calibration 30/policy를 실제 Isaac runtime으로 실행한다.
- held-out은 열지 않는다.
- candidate success rate가 baseline보다 높고 `>=0.30`이면 다음 freeze/readiness
  단계로 이동한다.
- 실패하면 artifact-only diagnosis로 다음 valid step을 도출한다.
