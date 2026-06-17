# MVP-2E v0.7f Depth-Zero / XY Saturation Diagnosis Design

작성일: 2026-06-15

## 1. 목적

`v0_7e`는 실제 Isaac Phase E expressibility sanity에서 `runtime_backend=isaac_runtime`까지 도달했지만
`success_count=0/5`로 fail-closed 되었다. 이전 blocker였던 "Isaac runtime 미실행"과
"z window가 너무 짧음"은 일부 해소되었지만, 실제 삽입 깊이는 여전히 거의 0이다.

`v0_7f`의 목적은 새 controller를 바로 만들지 않고, 현재 `v0_7e` 실제 Isaac trace만 사용해
depth-zero 원인을 자동 분류하는 artifact-only harness를 정의하는 것이다.

`v0_7f`는 proof slice가 아니다. `v0_7f`는 다음 repair slice 후보를 만들기 전의 진단 slice다.

## 2. 현재 증거

실제 실행 artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7e_shared_hysteresis_parity_repair/
    expressibility_sanity_gate_v0_7e.json
    expressibility_sanity_manifest_v0_7e.json
    isaac_runtime_expressibility_sanity_v0_7e/
```

실행 결과:

```text
runtime_backend=isaac_runtime
passed=false
success_count=0
rollout_count=5
required_success_count=2
heldout_21000_21049_accessed=false
calibration_opened=false
mvp2_closed=false
policy_uplift_proven=false
```

동일 seed의 성공 expert trace와 `v0_7e` policy trace를 비교하면 다음 차이가 확인된다.

| seed | expert max depth | expert longest z | expert xy saturation | v0.7e max depth | v0.7e longest z | v0.7e xy saturation |
|---|---:|---:|---:|---:|---:|---:|
| 19003 | 0.024883 | 32 | 4/125 | 0.000000 | 0 | 148/148 |
| 19012 | 0.024864 | 43 | 0/124 | 0.000000 | 28 | 147/148 |
| 19129 | 0.024942 | 32 | 0/115 | 0.000000 | 28 | 147/148 |
| 19030 | 0.024735 | 28 | 0/119 | 0.000000 | 28 | 147/148 |
| 19119 | 0.024999 | 38 | 26/140 | 0.000001 | 28 | 145/148 |

핵심 관찰:

- `v0_7e`는 4개 seed에서 28-step z window를 복원했다.
- 그런데 `insertion_depth_m`은 0 또는 0.000001에 머문다.
- `v0_7e`는 거의 모든 row에서 xy action이 clip에 포화된다.
- z-open 구간에서 lateral error가 다시 8-10mm 수준으로 벌어진다.
- 성공 expert는 같은 seed에서 최종 lateral을 약 0.45-0.50mm로 유지하고 depth 0.024m 수준까지 도달한다.

따라서 다음 원인은 단순한 z-window 부족이 아니다. 현재 가장 강한 후보는
xy saturation / centering instability / z-open 중 lateral regression이다.

## 3. Claim Boundary

`v0_7f`가 해도 되는 claim:

```text
v0_7e 실제 Isaac trace에서 depth-zero 실패 원인을 artifact-only harness로 분류했다.
```

`v0_7f`가 하면 안 되는 claim:

```text
MVP-2 Closed
policy uplift proven
curated > uncurated proven
Phase E passed
calibration freeze ready
held-out A/B ready
real robot success
physical robot readiness
visual policy performance
HMD/OpenXR readiness
```

`v0_7f`는 calibration과 held-out `21000-21049`를 열지 않는다.

모든 trace discovery는 payload를 읽기 전에 seed id를 먼저 추출해야 한다.
policy trace와 expert reference trace 모두 seed가 `21000-21049` 범위에 있으면
진단을 중단하고 fail-closed artifact를 기록한다. legacy directory name에
`heldout` 문자열이 포함되어도 protected seed가 아니면 held-out access로 보지 않는다.

## 4. Diagnosis Hypotheses

### H18: Z Window Restoration Diagnostic

질문:

```text
v0_7e가 이전 v0_7d 대비 z window를 실제로 복원했는가?
```

판정:

```text
restored_z_window_count = longest_nonzero_z >= 28 인 trace 수
```

현재 증거상 4/5가 해당한다. 이 harness는 closure gate가 아니라 downstream diagnosis context다.

### H19: XY Saturation Centering Instability

질문:

```text
정책/adapter 출력이 xy clip에 장시간 포화되어 centering을 유지하지 못하는가?
```

측정:

```text
xy_saturation_ratio = count(|action_x| >= 0.049 or |action_y| >= 0.049) / row_count
xy_saturation_during_z_open_ratio
candidate_vs_expert_xy_saturation_ratio_delta
```

초기 판정 기준:

```text
fail_if xy_saturation_ratio >= 0.80
```

근거: `v0_7e`는 145-148/148 row가 포화되고, 성공 expert는 대부분 0-4 row만 포화된다.

### H20: Z-Open Lateral Regression

질문:

```text
z가 열린 뒤 lateral이 capture/near band 밖으로 다시 벌어지는가?
```

측정:

```text
z_open_start_lateral_m
z_open_min_lateral_m
z_open_end_lateral_m
z_open_max_lateral_m
z_open_regression_m = z_open_end_lateral_m - z_open_min_lateral_m
```

판정:

```text
fail_if z_open_regression_m > 0.003
fail_if z_open_end_lateral_m > 0.006
```

근거: `v0_7e`는 z-open 시작 시 0.1-0.9mm까지 가까워졌다가 끝에서 8-10mm로 벌어진다.
이 상태에서 하강하면 peg가 hole 입구에 들어가지 못하고 rim 옆으로 내려간다.

### H21: Premature Z-Open / Approach-Height Readiness

질문:

```text
z-open이 hole 입구에 도달 가능한 approach geometry가 준비되기 전에 열린 것인가?
```

측정:

```text
first_z_open_step
first_depth_positive_step
z_open_steps_before_first_depth
approach_height_or_env_native_z_disp_if_available
```

판정:

```text
diagnostic_only
```

이 harness는 step 번호 자체를 gate로 삼지 않는다. seed별 dynamics가 다르기 때문이다.
대신 `first_depth_positive_step`이 없는 상태에서 z-open이 종료되면 depth-zero failure context로 기록한다.

### H22: XY Action-to-State Response Sign / Frame Check

질문:

```text
xy action 방향이 다음 step의 relative_x/y error를 줄이는가, 아니면 키우는가?
```

측정:

```text
action_x_to_next_relative_x_delta_sign_agreement
action_y_to_next_relative_y_delta_sign_agreement
state_feedback_expected_sign_agreement
```

판정:

```text
fail_if sign_agreement_rate < 0.60
```

이 harness는 action frame / sign mismatch를 배제하거나 분리하기 위한 진단이다.
xy saturation만 보고 gain 문제로 단정하지 않는다.

### H23: Vertical Response / Depth Semantics Check

질문:

```text
z command가 실제로 approach height 또는 insertion depth 진행으로 이어지는가?
```

측정:

```text
z_open_total_steps
z_open_longest_consecutive_steps
first_depth_positive_step
max_insertion_depth_m
env_native_z_disp_or_approach_height_if_available
```

판정:

```text
fail_if z_open_longest_consecutive_steps >= 28 and max_insertion_depth_m <= 0.000001
```

이 harness는 "z sign이 틀렸다"를 바로 결론내리지 않는다. 성공 expert가 같은 env에서 z 하강으로
depth를 만들었기 때문이다. 대신 policy path의 z command가 contact geometry에 도달하지 못했는지,
또는 lateral drift 때문에 depth가 발생하지 않았는지 분류한다.

### H24: Diagnostic Visibility Completeness

질문:

```text
다음 수리 전 trace가 충분한 runtime authority evidence를 노출하는가?
```

필수 필드:

```text
controller_action_diagnostics.behavior_state_phase
controller_action_diagnostics.shared_hysteresis_state_before
controller_action_diagnostics.shared_hysteresis_state_after
controller_action_diagnostics.base_servo_action
controller_action_diagnostics.residual_prediction
controller_action_diagnostics.raw_action_before_authority
controller_action_diagnostics.raw_action_after_authority
controller_action_diagnostics.raw_action_before_adapter
controller_action_diagnostics.pre_controller_action_vector
controller_action_diagnostics.post_adapter_action_vector
controller_action_diagnostics.z_motion_block_reason
controller_action_diagnostics.final_post_adapter_z_motion_allowed
```

판정:

```text
fail_if any required field is missing from any analyzed v0_7e policy trace
```

H24는 per-trace field matrix를 기록해야 한다. Aggregate pass는 모든 analyzed
policy trace가 required fields를 가질 때만 true다. 특정 필드를 optional로
강등하려면 report에 `optional_field_rationale`와 `not_evaluated` 상태를 남겨야 한다.

## 5. Root Cause Classifier

`v0_7f` classifier는 다음 우선순위를 사용한다.

1. `TRACE_DIAGNOSTICS_INCOMPLETE`
   - H24 실패
2. `XY_ACTION_FRAME_OR_SIGN_MISMATCH`
   - H22 실패
   - H22가 `not_evaluated`이면 `TRACE_DIAGNOSTICS_INCOMPLETE`로 분류하거나,
     saturation을 `primary_candidate`로만 기록하고 `recommended_downstream_slice=null`로 둔다.
3. `XY_SATURATION_CENTERING_INSTABILITY`
   - H19 실패
4. `Z_OPEN_LATERAL_REGRESSION`
   - H20 실패
5. `Z_OPEN_WITH_NO_VERTICAL_PROGRESS`
   - H23 실패
6. `PREMATURE_Z_OPEN_CONTEXT`
   - H21이 강한 context를 보이지만 H19-H23이 결정적이지 않을 때
7. `UNCLASSIFIED_DEPTH_ZERO_FAILURE`
   - 위 분류가 모두 불충분할 때

예상 primary class는 `XY_SATURATION_CENTERING_INSTABILITY` 또는
`Z_OPEN_LATERAL_REGRESSION`이다. 이 예상은 closure claim이 아니며, harness 결과가 우선한다.

## 6. Required Artifacts

`v0_7f` 구현은 다음 artifact를 생성해야 한다.

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7f_depth_zero_xy_saturation_diagnosis/
    mvp2e_v07f_diagnostic_config.json
    mvp2e_v07f_depth_zero_harness_report.json
    mvp2e_v07f_trace_comparison_table.json
    mvp2e_v07f_gate_manifest.json
```

상위 report 필수 필드:

```text
policy_slice="v0_7e"
diagnosis_slice="v0_7f"
proof_authority="diagnostic_only_not_closure_authority"
mvp2_closed=false
policy_uplift_proven=false
phase_e_passed=false
calibration_opened=false
heldout_21000_21049_accessed=false
protected_heldout_seed_range="21000-21049"
source_trace_set_sha256
expert_reference_trace_set_sha256
primary_root_cause_class
secondary_root_cause_candidates
recommended_downstream_slice
root_cause_candidate_without_repair_recommendation
```

## 7. Downstream Repair Boundary

`v0_7f`는 수리 코드를 만들지 않는다. `v0_7f`가 할 수 있는 최대 downstream 추천은
다음 중 하나다.

```text
v0_7g_xy_saturation_centering_repair
v0_7g_lateral_regression_guard_repair
v0_7g_action_frame_sign_repair
v0_7g_vertical_response_instrumentation
```

`recommended_downstream_slice`는 report에 기록할 수 있지만, 그 slice를 구현하기 전에는 별도 spec과 plan이 필요하다.

## 8. Verification Plan

구현 전 RED tests:

```text
test_v07f_depth_zero_harness_reads_v07e_actual_isaac_traces
test_v07f_reports_xy_saturation_ratio_against_expert_reference
test_v07f_classifies_lateral_regression_during_z_open
test_v07f_rejects_missing_controller_action_diagnostics
test_v07f_rejects_protected_seed_in_policy_trace_discovery
test_v07f_rejects_protected_seed_in_expert_reference_discovery
test_v07f_h24_requires_per_trace_diagnostic_completeness
test_v07f_h22_not_evaluated_blocks_downstream_repair_recommendation
test_v07f_does_not_open_calibration_or_heldout
test_v07f_marks_proof_authority_diagnostic_only
test_v07f_report_and_manifest_reject_closure_leakage
```

구현 후 검증 명령:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07f or v0_7f or depth_zero or xy_saturation" -q

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7f \
  --depth-zero-diagnosis-only \
  --pretty

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

`--depth-zero-diagnosis-only`는 artifact-only mode다. 이 mode는 Isaac, calibration, held-out A/B, policy training을 시작하지 않는다.

## 9. Self-Review

- Scope: `v0_7f`는 diagnosis artifact만 만든다. 수리와 proof closure를 포함하지 않는다.
- Held-out: `21000-21049`는 접근하지 않는다.
- Calibration: 열지 않는다.
- Success metric: env-native 10-consecutive authority는 변경하지 않는다.
- Historical evidence: `v0_7e` failure artifact는 실패로 보존한다.
- Public claim: MVP-2 Closed나 policy uplift claim을 하지 않는다.
