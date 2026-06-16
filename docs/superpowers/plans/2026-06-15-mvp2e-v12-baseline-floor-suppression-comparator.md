# MVP-2E v0.12 Baseline Floor Suppression Comparator Plan

## 목표

`v0_11a`의 `LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE`를 받아,
failure-tail-window baseline comparator를 만들고 fresh calibration/held-out
proof path를 실행한다.

## 구현 순서

1. RED tests
   - v0.12가 v0.11a diagnosis를 요구함
   - terminal failure-window rows만 baseline failure material로 사용함
   - candidate rows/policy authority는 v0.11에서 유지됨
   - fresh manifest가 `35000-35029`, `36000-36049`를 사용하고 prior split을 재사용하지 않음
   - CLI artifact-only/runtime guard

2. Code
   - v0.12 constants
   - terminal failure-window row selector
   - v0.12 policy artifact/manifest/gate builder
   - v0.12 fresh calibration/held-out runtime runner
   - evidence manifest wiring
   - evaluator policy-slice lineage allowlist에 `v0_12` 추가

3. Verification
   - focused pytest `-k "v12"`
   - `compileall`
   - `ruff check`
   - artifact-only command
   - actual Isaac runtime command

4. Loop
   - calibration fail: preserve evidence, write v0.12a diagnosis
   - held-out fail: preserve evidence, write v0.12b shortfall diagnosis
   - held-out pass: freeze MVP-2 Closed proof package

## 성공 기준

- v0.12 artifact gate passes and held-out stays sealed before calibration.
- actual calibration passes before held-out opens.
- MVP-2 Closed only if fresh held-out A/B reports positive uplift >= 0.20.
