# MVP-2E v0.7j Off-Center XY Authority Repair 설계

## 목적

`v0_7i` diagnosis는 `v0_7h` calibration failure의 primary root cause를 `OFF_CENTER_XY_AUTHORITY_GAP_AND_LATE_ALIGNMENT`로 분류했다.

`v0_7j`는 `v0_7g` policy artifact를 parent로 삼아, final post-adapter XY authority를 near-center 전용에서 off-center 포함 piecewise state-feedback authority로 확장한다.

## 핵심 변경

기존 `v0_7g`:

- saturated XY action을 `lateral_error_m <= 0.006`일 때만 state-feedback으로 clamp한다.
- off-center 구간에서는 `±0.05` saturated XY action이 그대로 남는다.

`v0_7j`:

- off-center 구간에서도 saturated XY action을 state-feedback action으로 치환한다.
- off-center에서는 travel authority를 보존하기 위해 `off_center_clip_abs=0.05`를 사용한다.
- near-center에서는 overshoot 억제를 위해 `near_center_clip_abs=0.02`를 유지한다.
- z authority, env-native success authority, calibration/held-out split은 변경하지 않는다.

## Integrity guard

- candidate/baseline에 동일한 shared authority config를 적용한다.
- success metric, calibration minimum `0.30`, held-out close threshold는 변경하지 않는다.
- protected held-out `21000-21049`는 계속 봉인한다.
- `v0_7j`는 calibration pre-signal이 통과해도 MVP-2 Closed가 아니다.

## Verification sequence

1. Offline authority gate:
   - off-center saturated action이 state-feedback으로 치환되는지 확인
   - z action 보존
   - sign-preservation guard 기록
   - candidate/baseline action delta가 완전히 사라지지 않는지 확인

2. Actual Isaac calibration pre-signal:
   - calibration seeds `20000-20029`
   - baseline/candidate 각 30 rollouts
   - candidate success rate > baseline success rate
   - candidate success rate >= 0.30
   - held-out not opened

3. Pass 시 next valid step:
   - `v0_7k_heldout_ab` actual held-out A/B

4. Fail 시 next valid step:
   - `v0_7k_calibration_failure_diagnosis`

## Non-claims

- real robot success 아님
- visual policy performance 아님
- deployable robot policy 아님
- MVP-2 Closed 아님
