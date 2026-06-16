# MVP-2E v0.7m Z-Window Progress Authority Repair Design

## 목적

`v0_7l` diagnosis는 `v0_7k` calibration 실패의 지배 원인을
`Z_DESCENT_WINDOW_INSUFFICIENT_AND_CENTERING_ESCAPE`로 고정했다.

`v0_7m`은 success metric을 바꾸지 않고, shared runtime hysteresis authority만
수리해 z descent window가 depth progress 전에 28 step으로 끊기는 문제를
줄인다.

## 수리 범위

변경 대상:

- shared hysteresis authority config
- runtime hysteresis state transition

변경하지 않는 것:

- env-native 10-consecutive success authority
- trainer family / weights / feature schema
- selected action adapter
- final post-adapter z authority
- final post-adapter xy authority
- calibration seed set
- held-out seed set

## Repair Rules

1. `z_window_hold_steps=70`
   - `v0_7k` success traces는 대체로 54-70 z step을 사용했다.
   - 기존 28 step은 hole 입구에 닿기 전에 끝나는 사례가 지배적이었다.

2. `z_window_realign_lateral_m=0.006`
   - z-open 중 lateral이 `0.006m`를 초과하면 z push를 멈추고 `ALIGN`으로
     되돌린다.
   - 이 값은 v0.7l 분류의 centering/lateral-escape 경계와 동일하다.
   - hard safety escape와 달리 sticky failure가 아니며, 다시 정렬되면 z window를
     재시작할 수 있다.

3. `hard_safety_escape_lateral_m=0.03` 유지
   - 큰 이탈은 기존 fail-safe처럼 유지한다.

## 무결성

- baseline/candidate는 동일 hysteresis config를 사용한다.
- 수리는 calibration failure diagnosis 이후, held-out 개봉 전에 pre-register된다.
- `v0_7m`은 calibration pre-signal을 다시 통과해야 하며, 이것만으로 MVP-2 Closed가
  아니다.

## 산출물

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7m_z_window_progress_authority_repair/
    v0_7m_hysteresis_authority_config.json
    candidate_policy_artifact_v0_7m.json
    baseline_policy_artifact_v0_7m.json
    z_window_progress_authority_gate_v0_7m.json
    v0_7m_z_window_progress_authority_manifest.json
```

## 다음 분기

- v0.7m calibration pre-signal pass:
  - held-out 전 마지막 calibration/selector freeze 점검으로 진행한다.
- v0.7m calibration pre-signal fail:
  - 새 artifact-only failure diagnosis를 자동 생성하고 다음 repair slice로 분기한다.
