# MVP-2E v0.7l Calibration Z-Window Failure Diagnosis Design

## 목적

`v0_7k` actual Isaac calibration pre-signal은 `candidate > baseline` 신호는
남겼지만 `candidate_success_rate >= 0.30` close-precondition을 통과하지
못했다.

`v0_7l`의 목적은 새 Isaac 실행 없이 `v0_7k` calibration trace artifact만
분석해 실패 원인을 고정하고, 다음 repair slice를 안전하게 제한하는 것이다.

## 입력 증거

- Parent slice: `v0_7k_runtime_hysteresis_wiring_repair`
- Parent gate:
  `v0_7k_runtime_hysteresis_wiring_repair/calibration_presignal_gate_v0_7k.json`
- Parent trace directory:
  `v0_7k_runtime_hysteresis_wiring_repair/isaac_runtime_calibration_presignal_v0_7k/isaac_runtime_heldout_rollout_traces/`

## 불변 조건

- `heldout_21000_21049`는 접근하지 않는다.
- calibration trace는 이미 열린 `20000-20029`만 사용한다.
- env-native 10-consecutive success authority는 변경하지 않는다.
- success metric, trainer, selected adapter, dataset split을 변경하지 않는다.
- `v0_7l`은 diagnostic-only artifact이며 closure authority가 아니다.

## 분류 규칙

각 trace는 다음 순서로 분류한다.

1. `SUCCESS`
   - env-native success mask의 최장 연속 run이 10 이상이다.
2. `Z_WINDOW_NO_VERTICAL_PROGRESS_WITH_CENTERING`
   - z descent가 20 step 이상 열렸고,
   - `max_insertion_depth_m < 0.001`,
   - z-open 구간의 최대 lateral이 `0.006m` 이하이다.
3. `Z_WINDOW_LATERAL_ESCAPE_NO_DEPTH`
   - z descent가 20 step 이상 열렸고,
   - `max_insertion_depth_m < 0.001`,
   - z-open 구간의 최대 lateral이 `0.006m`를 초과한다.
4. `SEAT_WINDOW_NOT_HELD`
   - `max_insertion_depth_m >= 0.024`,
   - env-native max consecutive success가 10 미만이다.
5. `PARTIAL_INSERTION_NO_STABILITY`
   - `max_insertion_depth_m >= 0.001`,
   - env-native max consecutive success가 10 미만이다.
6. `Z_WINDOW_TOO_SHORT_OR_NEVER_OPENED`
   - z descent 최장 연속 run이 20 step 미만이다.
7. `UNCLASSIFIED_CALIBRATION_FAILURE`

## Root Cause 판정

`candidate` 실패 중 아래 세 class의 합이 절반 이상이면 diagnosis는 confident로
본다.

- `Z_WINDOW_NO_VERTICAL_PROGRESS_WITH_CENTERING`
- `Z_WINDOW_LATERAL_ESCAPE_NO_DEPTH`
- `Z_WINDOW_TOO_SHORT_OR_NEVER_OPENED`

confident diagnosis의 primary root cause:

```text
Z_DESCENT_WINDOW_INSUFFICIENT_AND_CENTERING_ESCAPE
```

권장 downstream slice:

```text
v0_7m_z_window_progress_authority_repair
```

이 수리는 아직 구현하지 않는다. `v0_7l`은 다음 수리 범위를 좁히는
artifact-only diagnosis다.

## 산출물

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7l_calibration_z_window_failure_diagnosis/
    calibration_trace_classification_v0_7l.json
    calibration_failure_diagnosis_v0_7l.json
```

## 성공 기준

- `v0_7k` parent gate가 실제 Isaac calibration failure임을 검증한다.
- baseline/candidate 60개 trace를 모두 분류한다.
- protected held-out 접근이 false임을 증명한다.
- `candidate_failure_class_counts`와 recommended downstream slice를 기록한다.
- `mvp2_closed=false`, `policy_uplift_proven=false`를 명시한다.
