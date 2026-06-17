# MVP-2E v0.7n Z-Open XY Center-Maintenance Authority Design

## 목적

`v0_7m` calibration pre-signal은 실제 Isaac runtime에서 실패했다.

- baseline: 3/30
- candidate: 4/30
- candidate success rate: 0.133333333333
- failure reason: `candidate_calibration_success_below_minimum`
- held-out `21000-21049`: unopened

trace 진단 결과, `z_window_hold_steps=70`은 적용되었지만 실패 다수는
z-open 중 `xy_authority_sign_mismatch_not_applied`로 lateral이 5-6mm까지
밀리고, depth가 0에 머문다.

## Root Cause

`v0_7j` final XY authority는 saturated action에서 state-feedback 후보가
기존 action sign을 뒤집으면 `xy_authority_sign_mismatch_not_applied`로 빠진다.

이 규칙은 일반 구간에서는 보수적일 수 있지만, z-open + low-depth 구간에서는
오히려 rim 밖으로 미는 action을 방치한다.

## v0.7n Repair

`v0_7n`은 final post-adapter XY authority만 좁게 확장한다.

허용되는 변경:

- z-open 상태
- insertion depth < `0.001m`
- env-native success가 아직 아님
- `xy_sign_mismatch` 또는 saturated XY가 관측됨

위 조건에서는 기존 sign-preservation guard보다 state-feedback centering을 우선한다.

고정값:

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

## 무결성

- baseline/candidate 모두 같은 v0.7n XY authority config를 사용한다.
- parent는 failed-closed `v0_7m` calibration pre-signal이다.
- held-out은 계속 봉인한다.
- v0.7n calibration pre-signal 통과만으로 MVP-2 Closed가 아니다.

## 다음 분기

- v0.7n calibration pre-signal pass:
  - held-out 전 selector/freeze readiness 점검으로 이동한다.
- v0.7n calibration pre-signal fail:
  - 새 artifact-only diagnosis를 생성하고 다음 repair slice로 이동한다.
