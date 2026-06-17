# MVP-2E v0.14 Comparator Provenance / Row-Balance Design

Date: 2026-06-15

Status: pre-implementation design

## 목적

`v0_13`은 actual Isaac fresh calibration을 실행했지만 fail-closed됐다.

```text
baseline_calibration_success_count = 25 / 30
candidate_calibration_success_count = 23 / 30
candidate_baseline_success_gap = -0.066666666666
failure_reason = baseline_calibration_success_floor_above_v0_13_maximum
fresh_heldout_38000_38049_accessed = false
heldout_opened = false
```

paired seed 결과는 다음과 같다.

```text
baseline pass, candidate pass = 22
baseline pass, candidate fail = 3   # 37003, 37010, 37026
baseline fail, candidate pass = 1   # 37022
baseline fail, candidate fail = 4   # 37006, 37016, 37018, 37020
```

`v0_13`은 policy influence preservation 자체는 통과했다. 그러나 baseline
comparator가 낮은 floor로 작동하지 않았다. `v0_14`의 목적은 evaluator나
success metric을 바꾸는 것이 아니라, baseline uncurated training view의
source/provenance와 row-balance를 고쳐 curation contrast가 실제로 의미 있게
보존되는 comparator를 만드는 것이다.

## v0.13 증거

### 1. candidate-only failure는 insertion 실패가 아니라 ALIGN gate 미통과

candidate가 baseline에게 진 seed `37003`, `37010`, `37026`은 모두 다음 패턴을
보였다.

```text
behavior_state_phase = ALIGN for all 148 steps
insertion_depth_m max = 0.0
post_adapter z descent count = 0
failure_reason = ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED
```

candidate는 lateral을 gate 근처까지 줄였지만 `approach_lateral_gate_m=0.001`을
넘지 못했다.

```text
37003 candidate min_lateral_error_m = 0.001027
37010 candidate min_lateral_error_m = 0.001027
37026 candidate min_lateral_error_m = 0.001826
```

같은 seed에서 baseline은 gate를 통과해 57~63 step 연속 z descent를 만들고
env-native 10-consecutive success를 달성했다.

### 2. baseline failure material은 실제로 noisy poison이 아니라 near-gate ALIGN tutor

`baseline_uncurated_terminal_low_floor_train_v0_12.hdf5` metadata:

```text
total rows = 71850
candidate_success rows = 7185
train_generation_failed_attempt rows = 64665
baseline_actual_failure_material_ratio = 0.90
```

failure-labeled rows는 실제 trace summary 기준으로 failure다.

```text
env_native_rollout_success = false
failure_reason = ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED
```

하지만 이 rows는 전부 terminal-window `ALIGN` rows이며, lateral 분포가 매우
near-gate다.

```text
train_generation_failed_attempt phase = ALIGN only
lateral_error_m median = 0.000460
lateral_error_m q90    = 0.001149
lateral_error_m max    = 0.001240
```

즉 rejected material은 task-failure evidence로는 맞지만, BC training data로는
sub-mm gate 주변 correction을 대량 제공하는 near-miss tutor로 작동한다.

### 3. row-count imbalance가 baseline을 강화했다

failure material은 12개 near-miss failed traces에서 왔고, trace당 약 5,376~5,400
rows로 증폭되어 baseline의 90%를 차지했다.

```text
candidate_success distinct traces = 28, rows/trace ~= 223-279
train_generation_failed_attempt distinct traces = 12, rows/trace ~= 5376-5400
```

따라서 `v0_13` baseline은 "accepted + rejected/noisy uncurated"라는 의미보다
"near-gate ALIGN terminal rows를 압도적으로 많이 본 policy"가 됐다.

## Root Cause

```text
V13_CALIBRATION_FAILURE_ROOT_CAUSE =
  BASELINE_COMPARATOR_NEAR_MISS_TERMINAL_ALIGN_OVERSAMPLING
```

실패 원인은 controller authority나 held-out leakage가 아니다. 핵심은
`v0_12` baseline construction이 terminal failure window를 90% ratio로 반복
복제하면서, rejected near-miss rows가 baseline에게 precision ALIGN skill을
가르친 것이다.

이 상태에서 positive uplift가 안 나온 것은 정직한 결과다. curation 효과가 없는
것이 아니라, comparator가 curation contrast를 측정하기에 부적합했다.

## v0.14 목표

`v0_14`는 다음을 만든다.

```text
provenance_checked_row_balanced_uncurated_comparator
```

요구사항:

1. failure material source는 filename label이 아니라 trace summary authority로
   판정한다.
2. `source_trace_role=train_generation_failed_attempt` rows는 반드시
   `env_native_rollout_success=false` source trace에서 와야 한다.
3. near-miss terminal failure rows가 baseline을 지배하지 못하도록 row cap과
   phase/source balance를 pre-register한다.
4. candidate/baseline은 같은 trainer, feature schema, base servo, adapter,
   authority config를 계속 공유한다.
5. fresh calibration/held-out range를 새로 봉인한다.
6. held-out은 calibration gate 통과 전까지 열지 않는다.

## Comparator Construction

### Candidate

candidate는 `v0_12` candidate curated rows를 그대로 복사한다.

```text
candidate_view_role = candidate_curated
candidate_rows_unchanged_from_v0_12 = true
```

candidate를 수정하면 curation effect와 comparator repair가 섞이므로 금지한다.

### Baseline

baseline은 accepted rows와 rejected near-miss rows를 모두 포함하되, rejected
rows가 precision tutor로 과대표집되지 않게 제한한다.

Pre-registered mix:

```text
baseline_failure_material_ratio_target = 0.50
accepted_failure_ratio = 0.50
```

Rationale:

- accepted와 rejected를 같은 row mass로 비교해 uncurated contamination은 남긴다.
- `v0_12`의 0.90 ratio처럼 near-miss terminal rows가 trainer를 지배하지 못하게 한다.
- 0.50은 calibration result를 보고 고른 값이 아니라, binary accepted/rejected
  comparator의 symmetric baseline이다.

Row-balance constraints:

```text
max_rows_per_failure_source_trace = 300
max_failure_align_rows_per_source_trace = 300
max_failure_to_success_row_ratio = 1.10
failure_material_selection = row_balanced_near_miss_terminal_failure_rows
duplicate_failure_rows_allowed = false
```

`300`은 accepted success trace의 observed per-trace upper envelope
(`~223-279 rows/trace`)를 round-up한 cap이다. 이 값은 success count를 보고 고른
것이 아니라 source trace row-count imbalance를 막기 위한 structural cap이다.

Failure row selection:

```text
1. group failure rows by source trace summary hash/path
2. sort each trace by step
3. take terminal rows up to max_rows_per_failure_source_trace
4. do not cycle-copy rows to hit ratio
5. if failure rows exceed target count, deterministic round-robin by source trace
6. if failure rows are below target count, use available rows and record shortfall
```

즉 ratio target은 target이지 duplication 허가가 아니다.

## Provenance Gate

`v0_14` artifact-only gate는 다음을 검증한다.

```text
all rows:
  source_trace_summary_success is present
  source_trace_summary_failure_reason is present for rejected rows
  source_trace_sha256 or source_trace_path is present
  calibration/heldout seed ranges not used

failure rows:
  accepted == false
  source_trace_role == train_generation_failed_attempt
  source_trace_summary_success == false
  source_trace_summary_env_native_rollout_success == false
  source_trace_summary_failure_reason != ""
  source_path_label is report-only, not authority

success rows:
  accepted == true
  source_trace_summary_success == true
```

filename에 `train_success`가 들어 있어도 summary가 false면 failure로 판정한다.
반대로 filename이 failure처럼 보여도 summary가 true면 failure material로 쓸 수
없다.

## Row-Balance Gate

`v0_14`는 다음 gate를 통과해야 actual calibration을 열 수 있다.

```text
baseline_actual_failure_material_ratio in [0.45, 0.55]
failure_source_trace_count >= 10
max_rows_per_failure_source_trace <= 300
duplicate_failure_rows_allowed == false
candidate_rows_unchanged_from_v0_12 == true
peer_fairness_mismatch_keys == []
calibration_or_heldout_rows_used_for_training == false
fresh_heldout_40000_40049_accessed == false
```

gate가 실패하면 fail-closed하고 Isaac runtime을 열지 않는다.

## Fresh Splits

`v0_14`는 새 calibration/held-out range를 사용한다.

```text
fresh_calibration = 39000-39029
fresh_heldout     = 40000-40049
```

Burned/excluded:

```text
all prior calibration ranges
all prior held-out ranges
v0_13 calibration 37000-37029
v0_13 sealed heldout 38000-38049
train-generation source ranges 19000-19359
```

`40000-40049`는 calibration gate 통과 전 접근 금지다.

## Calibration Gate

close-minimum으로 가기 전 calibration presignal은 기존 기준을 유지한다.

```text
rollouts_per_policy = 30
runtime_backend = isaac_runtime
candidate_success_rate >= 0.80
candidate_success_rate > baseline_success_rate
candidate_baseline_success_gap >= 0.20
baseline_success_rate <= 0.65
policy_influence_preservation_passed == true
heldout_allowed == true only if all above pass
```

`v0_14` calibration이 실패하면 held-out을 열지 않고 새 diagnosis artifact를 만든다.

## Held-out Closure

calibration gate가 통과한 경우에만 `40000-40049` held-out을 연다.

MVP-2 Closed 조건:

```text
actual_rollouts_per_policy >= 20
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
runtime_backend = isaac_runtime
heldout_leakage_guard.passed == true
mvp2_closed = true only in heldout closure gate
```

stronger public target은 별도 필드로 유지한다.

```text
actual_rollouts_per_policy >= 50 preferred
confidence interval reported
stronger_public_evidence_target_passed separately reported
```

## 비목표

`v0_14`는 다음을 하지 않는다.

- success metric, env-native authority, `stable_steps=10`을 바꾸지 않는다.
- candidate-only controller, candidate-only adapter, candidate-only feature를 만들지 않는다.
- baseline을 결과를 보고 임의로 poison하지 않는다.
- held-out `40000-40049`를 calibration 전에 열지 않는다.
- `v0_13` 결과를 소급 성공으로 바꾸지 않는다.
- synthetic/proxy backend를 closure evidence로 승격하지 않는다.
- real robot success, deployable visual policy, HMD/OpenXR readiness를 주장하지 않는다.

## 성공 산출물

Artifact-only:

```text
v0_14_comparator_provenance_row_balance_config.json
v0_14_comparator_provenance_row_balance_gate.json
candidate_policy_artifact_v0_14.json
baseline_policy_artifact_v0_14.json
candidate_curated_train_v0_14.hdf5
baseline_uncurated_row_balanced_train_v0_14.hdf5
v0_14_fresh_manifest.json
```

Runtime:

```text
calibration_runtime_manifest_v0_14.json
calibration_presignal_gate_v0_14.json
calibration_external_rollouts/*_v0_14.json
heldout_runtime_manifest_v0_14.json        # only after calibration pass
heldout_closure_gate_v0_14.json            # only after heldout run
```

## Claim Boundary

`v0_14` artifact-only gate 통과는 comparator repair evidence일 뿐 MVP-2 Closed가
아니다.

허용 claim:

```text
v0_14 fixed a comparator validity bug where near-miss rejected terminal
rows dominated the uncurated baseline view.
```

금지 claim:

```text
MVP-2 Closed
curated policy uplift proven
real robot success
physical robot readiness
visual policy performance
HMD/OpenXR readiness
```
