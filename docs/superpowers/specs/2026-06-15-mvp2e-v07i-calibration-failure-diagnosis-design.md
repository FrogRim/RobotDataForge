# MVP-2E v0.7i Calibration Failure Diagnosis 설계

## 목적

`v0_7h` actual Isaac calibration pre-signal은 `baseline=2/30`, `candidate=5/30`으로 candidate가 baseline보다 높았지만, `candidate_calibration_success_rate=0.166666666667`이라 pre-registered minimum `0.30`을 넘지 못했다.

`v0_7i`의 목적은 새 정책이나 새 trainer를 만들지 않고, `v0_7h` calibration trace를 artifact-only로 분석해 다음 repair slice의 단일 root cause를 고정하는 것이다.

## 입력 증거

- `v0_7h_calibration_presignal/calibration_presignal_gate_v0_7h.json`
- `v0_7h_calibration_presignal/isaac_runtime_calibration_presignal_v0_7h/isaac_runtime_heldout_rollout_traces/*.json`

주의: 디렉터리명에 `heldout`이 포함돼도, `v0_7h` runtime manifest는 `source_split=calibration`, `semantic_eval_split=calibration`이다. Protected held-out seed `21000-21049`는 접근 금지다.

## 진단 가설

`v0_7g`의 XY authority는 near-center 구간에서만 saturation을 clamp한다. Calibration trace에서는 초기 lateral이 약 `17-20mm`인 seed가 많고, 이 off-center 구간에서 `normalized_action[:2]`가 여전히 `±0.05`로 포화된다.

따라서 candidate는 일부 seed에서 late alignment 후 성공하지만, 다수 seed는:

- off-center 구간에서 saturated XY action을 오래 사용한다.
- z gate가 닫혀 있어 depth가 끝까지 0에 머문다.
- 혹은 step 140 근처에야 env-native mask에 닿아 10-step hold window를 채우지 못한다.

## 산출물

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7i_calibration_failure_diagnosis/
    calibration_failure_diagnosis_v0_7i.json
    calibration_trace_classification_v0_7i.json
```

## 분류 기준

각 rollout trace에 대해 다음을 계산한다.

- `initial_lateral_error_m`
- `min_lateral_error_m`
- `final_lateral_error_m`
- `max_insertion_depth_m`
- `first_z_motion_step`
- `first_depth_positive_step`
- `first_env_native_success_step`
- `env_native_max_consecutive_success_steps`
- `max_consecutive_z_motion_steps`
- `off_center_xy_saturation_count`
- `near_center_xy_authority_applied_count`

분류 label:

- `SUCCESS`
- `OFF_CENTER_XY_AUTHORITY_GAP_DEPTH_ZERO`
- `UNDER_INSERTION_LATE_SEAT_WINDOW`
- `PARTIAL_INSERTION_NO_STABILITY`
- `LATERAL_DRIFT_OR_RIM_EJECT`
- `UNCLASSIFIED_CALIBRATION_FAILURE`

## Gate

`v0_7i` diagnosis는 closure gate가 아니다.

`diagnosis_confident=true` 조건:

- `v0_7h` gate가 존재한다.
- `v0_7h.passed=false`
- `v0_7h.failure_reason=candidate_calibration_success_below_minimum`
- `runtime_backend=isaac_runtime`
- `heldout_21000_21049_accessed=false`
- candidate failures 중 `OFF_CENTER_XY_AUTHORITY_GAP_DEPTH_ZERO` 또는 `UNDER_INSERTION_LATE_SEAT_WINDOW`가 지배적이다.
- trace diagnostics에서 `v0_7g` final XY authority가 near-center 조건 때문에 off-center saturation을 차단하지 못한 증거가 있다.

## 다음 slice

`diagnosis_confident=true`이면 다음 valid step은 `v0_7j_off_center_xy_authority_repair`다.

수리 방향은:

- candidate/baseline 공통 shared infrastructure로 적용한다.
- success metric, calibration threshold, held-out split은 변경하지 않는다.
- off-center 구간에서도 sign-preserving XY authority를 적용하되, policy attribution이 완전히 사라지지 않는지 offline delta retention을 다시 측정한다.

## 금지

- held-out `21000-21049` 접근 금지
- calibration 결과를 MVP-2 Closed로 주장 금지
- success metric 또는 `0.30` calibration minimum 완화 금지
- policy uplift claim 금지
- real robot/HMD readiness claim 금지
