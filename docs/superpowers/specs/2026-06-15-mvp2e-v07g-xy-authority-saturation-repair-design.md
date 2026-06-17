# MVP-2E v0.7g XY Authority Saturation Repair Design

작성일: 2026-06-15

## 1. 목적

`v0_7f` artifact-only diagnosis는 `v0_7e` 실제 Isaac Phase E 실패의 현재 1차 원인을
`XY_SATURATION_CENTERING_INSTABILITY`로 분류했다.

`v0_7g`의 목적은 policy/trainer를 다시 크게 바꾸지 않고, 마지막 action mutation 지점 이후에
policy 공통 `xy` authority를 추가해 centering instability를 막는 것이다.

`v0_7g`는 MVP-2 closure slice가 아니다. `v0_7g`는 Phase E expressibility sanity를 다시 열기 전의
runtime action authority repair slice다.

## 2. 현재 증거

입력 증거:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7f_depth_zero_xy_saturation_diagnosis/
    mvp2e_v07f_diagnostic_config.json
    mvp2e_v07f_depth_zero_harness_report.json
    mvp2e_v07f_trace_comparison_table.json
    mvp2e_v07f_gate_manifest.json
```

`v0_7f` 분류:

```text
root_cause_status=classified
primary_root_cause_class=XY_SATURATION_CENTERING_INSTABILITY
secondary_root_cause_candidates=[
  Z_OPEN_LATERAL_REGRESSION,
  Z_OPEN_WITH_NO_VERTICAL_PROGRESS
]
recommended_downstream_slice=v0_7g_xy_authority_saturation_repair
mvp2_closed=false
phase_e_passed=false
calibration_opened=false
heldout_21000_21049_accessed=false
```

핵심 trace 비교:

| seed | policy longest z | policy max depth | policy xy saturation | policy z-open regression | expert longest z | expert max depth | expert xy saturation |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 19003 | 0 | 0.000000 | 1.000 | n/a | 32 | 0.024883 | 0.032 |
| 19012 | 28 | 0.000000 | 0.993 | 0.008326 | 43 | 0.024864 | 0.000 |
| 19129 | 28 | 0.000000 | 0.993 | 0.008503 | 32 | 0.024942 | 0.000 |
| 19030 | 28 | 0.000000 | 0.993 | 0.010115 | 28 | 0.024735 | 0.000 |
| 19119 | 28 | 0.000001 | 0.980 | 0.008700 | 38 | 0.024999 | 0.186 |

결론:

- `z` window만으로는 실패가 설명되지 않는다. 4개 seed에서 28-step z-open이 관측되지만 depth가 0에 머문다.
- `xy` sign agreement는 fail이 아니다. 방향이 완전히 뒤집힌 frame mismatch는 현재 1차 원인이 아니다.
- policy path는 거의 모든 row에서 `xy`가 clip 근처에 포화된다.
- z-open 중 lateral이 0.1-0.9mm 근처에서 8-10mm로 다시 벌어진다.
- 성공 expert는 같은 seed에서 `xy` 포화가 거의 없고 z-open 후 lateral을 0.1-0.3mm 수준으로 유지한다.

## 3. Claim Boundary

`v0_7g`가 해도 되는 claim:

```text
v0_7f에서 분류된 xy saturation / centering instability를 막기 위한 runtime action authority repair를 정의했다.
```

`v0_7g`가 하면 안 되는 claim:

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

`v0_7g`는 calibration과 held-out `21000-21049`를 열지 않는다.

## 4. Repair Principle

현재 action authority 계층은 `z` leak을 막는 데 집중되어 있다.

```text
policy residual/base action
-> v0_7c residual authority
-> selected_action_adapter
-> v0_7d/v0_7e final post-adapter z authority
-> Isaac action
```

`v0_7f` 증거는 `selected_action_adapter` 이후 `xy`가 거의 계속 포화되는 것을 보여준다.
따라서 `v0_7g`는 다음 원칙으로 마지막 `xy` authority를 추가한다.

```text
policy residual/base action
-> v0_7c residual authority
-> selected_action_adapter
-> v0_7d/v0_7e final post-adapter z authority
-> v0_7g final post-adapter xy authority
-> Isaac action
```

핵심 원칙:

- authority는 selected adapter 이후, 실제 Isaac action 직전에 적용한다.
- baseline과 candidate에 동일하게 적용한다.
- config 유무에 따라 꺼지지 않는 필수 authority로 둔다.
- env-native success authority를 바꾸지 않는다.
- z authority, env-native stable-hold authority, held-out firewall을 약화하지 않는다.
- search, retry, withdraw, force-control, live robot control을 추가하지 않는다.
- policy/trainer 재작성 없이 runtime action envelope를 수리한다.

## 5. v0.7g Final XY Authority

새 authority id:

```text
final_post_adapter_xy_authority_gate_v0_7g
```

새 slice id:

```text
mvp2e_v07g_xy_authority_saturation_repair
```

새 schema:

```text
rdf_mvp2e_v07g_xy_authority_config_v0.1.0
```

필수 config fields:

```json
{
  "slice_id": "mvp2e_v07g_xy_authority_saturation_repair",
  "final_post_adapter_xy_authority_id": "final_post_adapter_xy_authority_gate_v0_7g",
  "parent_final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
  "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
  "xy_authority_application_point": "after_selected_action_adapter_and_after_final_z_authority",
  "xy_authority_required": true,
  "baseline_candidate_shared": true,
  "heldout_excluded": true,
  "calibration_opened": false,
  "env_native_success_authority_unchanged": true,
  "stable_hold_authority": "env_native_success_mask",
  "xy_saturation_threshold_abs": 0.049,
  "xy_saturation_ratio_fail_threshold": 0.80,
  "xy_reference_expert_saturation_ratio_max": 0.25,
  "z_open_lateral_regression_fail_threshold_m": 0.003,
  "z_open_end_lateral_fail_threshold_m": 0.006,
  "xy_sign_agreement_min": 0.60,
  "candidate_baseline_attribution_preservation_required": true,
  "post_xy_authority_delta_l2_mean_min": 0.000001,
  "post_xy_authority_delta_nonzero_fraction_min": 0.10,
  "xy_delta_retention_ratio_min": 0.10
}
```

`xy_saturation_ratio_fail_threshold`, `z_open_lateral_regression_fail_threshold_m`,
`z_open_end_lateral_fail_threshold_m`, `xy_sign_agreement_min`은 `v0_7f` diagnosis harness에서 이미 사용한
기준을 이어받는다. `v0_7g`에서 결과를 보고 새로 고른 threshold가 아니다.

## 6. Authority Behavior

`v0_7g` authority는 policy output을 성공 metric으로 직접 바꾸는 것이 아니라, actuator envelope를 안정화한다.

동작 규칙:

1. `xy` sign을 뒤집지 않는다.
2. `xy` action을 `lateral_error_m`과 같은 방향의 state-feedback envelope 안에 둔다.
3. `lateral_error_m`이 z-open gate 주변에 있을 때 clip-saturated xy command가 계속 발생하면 감쇠한다.
4. z-open이 허용된 동안 lateral이 regression하면 `xy` saturation을 더 키우지 않는다.
5. final action vector에 `xy_authority_applied`, `xy_authority_reason`, `pre_xy_authority_action_vector`,
   `post_z_pre_xy_authority_action_vector`, `post_xy_authority_action_vector`를 기록한다.
6. `no_mutation_after_final_post_adapter_authority`는 v0.7g final xy authority 이후 더 이상 action mutation이
   없다는 의미로 재정의한다. v0.7d z authority 이후 v0.7g xy authority가 적용되는 것은 mutation으로 보지
   않는다.

권장 구현 형태:

```text
if phase in ALIGN/DESCEND/INSERT and xy is saturated:
  apply state-aware xy clamp from relative_x/y and lateral_error_m
else:
  preserve selected adapter xy output
```

금지:

```text
per-seed tuning
held-out result based tuning
policy별 다른 clamp
candidate-only repair
success metric 변경
env-native mask 조작
force-reactive control
retry / withdraw / search
```

## 7. Offline Gate Before Isaac

`v0_7g`는 실제 Isaac Phase E를 바로 열지 않는다. 먼저 기존 `v0_7e` trace와 policy artifact를 사용한
offline gate를 통과해야 한다.

필수 offline gate:

```text
G1 config_contract_passed
G2 protected_seed_prescan_passed
G3 final_xy_authority_required_and_hash_stable
G4 after-authority xy_saturation_ratio_mean <= 0.25
G5 z-open historical regression rows receive non-saturated corrective xy action
G6 after-authority action-level xy sign agreement remains >= 0.60
G7 xy_sign_agreement_ratio >= 0.60
G8 z authority unchanged
G9 stable_hold_authority remains env_native_success_mask
G10 candidate_baseline_attribution_not_erased
```

G4의 `0.25`는 성공 expert reference의 대부분이 0-0.032이고 한 seed가 0.186인 사실을 고려한 보수적 상한이다.
이는 `v0_7f`의 "expert reference는 xy saturation dominated가 아니다"라는 진단 기준을 offline repair gate로
재사용한 것이다.

G5와 G6은 existing trace의 state trajectory를 성공으로 재판정하지 않는다. offline replay는 실제 Isaac
dynamics를 다시 계산하지 못하므로, z-open lateral regression이 실제로 사라졌는지는 Phase E runtime trace에서만
판정한다. offline gate는 historical regression row에서 새 final xy action이 포화된 lateral push를 반복하지
않는지만 검증한다.

G10은 다음을 요구한다.

```text
pre_xy_authority_candidate_baseline_xy_delta_l2_mean is reported
pre_xy_authority_candidate_baseline_xy_delta_l2_mean > 1.0e-6
post_xy_authority_candidate_baseline_xy_delta_l2_mean > 1.0e-6
post_xy_authority_candidate_baseline_xy_delta_nonzero_fraction >= 0.10
xy_delta_retention_ratio = post_delta_l2_mean / pre_delta_l2_mean
xy_delta_retention_ratio >= 0.10
shared_xy_authority_did_not_make_policies_identical=true
```

`pre_xy_authority_candidate_baseline_xy_delta_l2_mean <= 1.0e-6`이면
`candidate_baseline_pre_xy_delta_absent`로 fail-closed 한다. 이 경우 denominator가 없으므로
`xy_delta_retention_ratio`를 계산하지 않는다.

이 gate가 필요한 이유는 shared authority가 baseline과 candidate를 완전히 같은 closed-loop servo로 만들어
Phase E는 통과하지만 Phase F/G uplift를 없애는 실패를 막기 위해서다.

## 8. Actual Isaac Phase E 조건

offline gate가 통과하면 같은 train-side expressibility sanity seed에서 실제 Isaac Phase E를 실행한다.

Seed set:

```text
19003
19012
19129
19030
19119
```

Pass 기준:

```text
runtime_backend=isaac_runtime
rollout_count=5
required_success_count=2
env_native_success_mask_consecutive_required=10
success_count >= 2
heldout_21000_21049_accessed=false
calibration_opened=false
mvp2_closed=false
```

Phase E가 통과해도 MVP-2는 닫히지 않는다. Phase E 통과는 calibration/held-out A/B로 넘어가기 위한
expressibility sanity gate일 뿐이다.

## 9. Next Loop After v0.7g

`v0_7g` Phase E 통과 시 다음 valid step:

```text
Phase F calibration freeze and selector evidence, held-out still sealed
```

`v0_7g` Phase E 실패 시 다음 valid step:

```text
artifact-only diagnosis from v0_7g actual Isaac traces
```

실패한 경우에도 success metric을 완화하거나 held-out을 열지 않는다.

## 10. Implementation Touchpoints

예상 변경 지점:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
  - final_post_adapter_xy_authority_gate_v0_7g
  - post-authority diagnostics fields
  - baseline/candidate shared enforcement

scripts/run_mvp2c_isaac_training_calibration.py
  - build_v07g_xy_authority_saturation_repair_slice
  - offline_xy_authority_gate_v0_7g.json
  - v0_7g_xy_authority_manifest.json
  - --policy-slice v0_7g dispatch

apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
  - final xy authority unit tests
  - sign preservation
  - z authority unchanged
  - candidate/baseline shared config

apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
  - v0_7g artifact contract tests
  - protected seed pre-scan
  - offline gate fail/pass semantics
  - claim boundary tests
```

문서 변경:

```text
docs/developer/worklog.md
tasks/todo.md
Handoff.md
```

## 11. Verification Commands

구현 후 최소 검증:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07g or v0_7g or xy_authority or saturation" -q

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07g or v0_7g or xy_authority or saturation" -q

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7g \
  --offline-relabel-only \
  --pretty

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

실제 Isaac Phase E는 offline gate가 통과한 뒤에만 실행한다.

## 12. Stop Conditions

즉시 중단하고 blocker로 기록해야 하는 경우:

- `env_native_success_mask` 또는 10-consecutive success authority를 완화해야 통과하는 경우
- calibration 또는 held-out `21000-21049` 접근이 필요해지는 경우
- baseline과 candidate에 서로 다른 authority를 적용해야 하는 경우
- shared authority가 candidate/baseline action 차이를 완전히 제거하는 경우
- force-control, retry, withdraw, search가 필요해지는 경우
- real robot, HMD/OpenXR, ROS2/DDS runtime이 필요해지는 경우
- DB migration이 필요해지는 경우

## 13. Success Criteria

`v0_7g` implementation slice는 다음이 모두 참일 때 완료된다.

```text
final_post_adapter_xy_authority_gate_v0_7g defined
config hash stable
selected adapter output 이후 xy authority 적용
baseline/candidate shared authority enforced
z authority unchanged
stable_hold_authority=env_native_success_mask preserved
offline xy saturation gate passed
historical_regression_rows_receive_non_saturated_corrective_xy_action passed
candidate/baseline attribution preserved
protected held-out seeds untouched
MVP-2 Closed not claimed
```

MVP-2 Closed 조건은 여전히 다음이다.

```text
fresh held-out A/B
candidate curated success_rate > baseline uncurated success_rate
curated_vs_uncurated_uplift >= 0.20
actual_rollouts_per_policy >= 20
buyer-readable limitations
no policy uplift overclaim
```
