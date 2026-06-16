# MVP-2E v0.12 Baseline Floor Suppression Comparator Spec

## 목적

`v0_11`은 baseline training view에 90% failure material을 넣었지만 actual
Isaac calibration에서 baseline이 `21/30=0.70`으로 남아 calibration floor
`0.65`를 넘었다. `v0_11a`는 이를
`LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE`로 분류했다.

`v0_12`는 candidate policy/trainer/runtime authority를 유지하고, baseline
uncurated comparator만 더 정직하게 낮춘다. 핵심 변경은 failed trajectory 전체를
복제하지 않고, rejected failure trace의 terminal failure window만 uncurated
baseline material로 사용하는 것이다.

## 설계 근거

`v0_11` failure material은 failed trace 전체를 round-robin 복제했다. failed trace
초중반에는 성공 trace와 같은 정렬/하강 행동이 다수 포함될 수 있어, uncurated
baseline이 여전히 shared authority와 결합해 높은 성공 floor를 유지했다.

`v0_12`는 rejected trajectory의 terminal failure transition만 넣어 “큐레이션 없이
실패 tail까지 학습한 baseline”을 만든다. 이는 결과를 보고 metric을 바꾸는 것이
아니라, 이미 열린 calibration에서 발견된 comparator construction bug를 고치는
것이다.

## Seed Split

- calibration: `35000-35029`
- held-out: `36000-36049`
- burned/excluded:
  - prior held-out: `21000-21049`, `24000-24049`, `26000-26049`,
    `27000-27049`, `32000-32049`, `34000-34049`
  - prior calibration: `30000-30029`, `31000-31029`, `33000-33029`

## Comparator Rule

- candidate view: unchanged from `v0_11`
- baseline success rows: same accepted/success rows as parent baseline
- baseline failure rows: only terminal failure-window rows from actual failed
  train-generation traces
- terminal window: last `24` rows from each failed trace
- baseline failure-material ratio target: `0.90`
- allowed ratio: `[0.85, 0.95]`
- no held-out or calibration rows used for training

## Calibration Gate

- actual Isaac runtime only
- 30 rollouts per policy
- `candidate_success_rate >= 0.80`
- `baseline_success_rate <= 0.65`
- `candidate_success_rate > baseline_success_rate`
- `candidate_success_rate - baseline_success_rate >= 0.20`
- attribution preservation: no candidate degradation explosion

## Held-Out Gate

Only if calibration passes:

- fresh held-out `36000-36049`
- 50 rollouts per policy
- `curated_vs_uncurated_uplift >= 0.20`
- generate learning-proven report

## Claim Boundaries

- v0.12 artifact build and calibration are not MVP-2 Closed unless held-out A/B
  passes.
- HMD/OpenXR, real robot, physical readiness, visual policy, deployable policy
  claims remain forbidden.
