# MVP-2E v0.7q Held-out Shortfall Diagnosis 설계

## 목적

v0.7p held-out closure run은 실제 Isaac runtime으로 pre-registered held-out `21000-21049`를 열었지만
MVP-2 close minimum을 통과하지 못했다.

- baseline: `34/50 = 0.68`
- candidate: `41/50 = 0.82`
- uplift: `+0.14`
- close threshold: `candidate_success_rate > baseline_success_rate` 그리고 `uplift >= 0.20`
- 필요한 candidate success count: baseline 34개 기준 최소 44개
- 실제 shortfall: candidate success 3개 부족

v0.7q의 목적은 이 실패를 코드나 metric으로 즉시 고치지 않고, artifact-only 방식으로 원인을 분류해 다음
fresh sealed split 수리 slice의 설계 근거를 고정하는 것이다.

## 핵심 원칙

1. v0.7p held-out `21000-21049`는 이미 열린 proof split이다.
2. v0.7p 결과를 보고 같은 held-out split에 맞춰 threshold, controller, policy, adapter를 조정해 다시 닫지 않는다.
3. v0.7q는 closure authority가 아니다.
4. v0.7q는 post-heldout diagnostic-only artifact이다.
5. 다음 실제 close attempt는 fresh sealed split을 사용해야 한다.

## 입력

- `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7p_heldout_closure/heldout_closure_gate_v0_7p.json`
- `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7p_heldout_closure/isaac_runtime_heldout_rollout_traces/*.json`
- `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7p_heldout_closure/external_rollouts/*.json`

## 출력

새 하위 디렉토리:

`storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7q_heldout_shortfall_diagnosis/`

필수 artifact:

- `heldout_shortfall_diagnosis_v0_7q.json`
- `paired_seed_outcome_table_v0_7q.json`
- `candidate_failure_classification_v0_7q.json`
- `post_heldout_integrity_marker_v0_7q.json`

루트 호환 artifact:

- `heldout_shortfall_diagnosis.json`
- `post_heldout_tuning_marker.json`

## 분류 규칙

### Paired outcome

같은 held-out seed의 baseline/candidate 결과를 다음 네 범주로 분류한다.

- `B1_C1`: baseline 성공, candidate 성공
- `B0_C1`: baseline 실패, candidate 성공
- `B1_C0`: baseline 성공, candidate 실패
- `B0_C0`: baseline 실패, candidate 실패

v0.7p 관측값:

- `B1_C1 = 34`
- `B0_C1 = 7`
- `B1_C0 = 0`
- `B0_C0 = 9`

### Candidate failure class

candidate 실패 seed는 trace summary와 per-step trace에서 다음 순서로 분류한다.

1. `NEAR_SEAT_HOLD_WINDOW_SHORT`
   - `max_depth >= 0.0245`
   - `env_native_max_consecutive_success_steps > 0`
   - 성공 영역에 닿았지만 10-step hold window를 채우지 못한 경우

2. `UNDER_INSERTION_WITH_GOOD_CENTERING`
   - `max_depth < 0.0245`
   - `min_lateral_error_m <= 0.001`
   - center는 맞지만 depth가 부족한 경우

3. `ALIGNMENT_STALL_NO_DESCENT`
   - `max_depth == 0`
   - `longest_z_descent_steps == 0`
   - ALIGN에서 하강이 열리지 않은 경우

4. `OTHER_CANDIDATE_FAILURE`
   - 위 분류에 들어가지 않는 경우

## 진단 판정

`close_shortfall_success_count = required_candidate_success_count - actual_candidate_success_count`

v0.7p에서는 `44 - 41 = 3`.

진단은 다음을 산출한다.

- `dominant_shortfall_class`
- `near_seat_recoverable_count`
- `under_insertion_count`
- `alignment_stall_count`
- `fresh_split_required=true`
- `same_heldout_reuse_allowed_for_closure=false`

다음 slice 추천은 다음 규칙을 따른다.

- `near_seat_recoverable_count >= close_shortfall_success_count`
  - 추천: `v0_8a_fresh_seat_window_authority_slice`
  - 이유: candidate는 baseline보다 7개 더 성공했고 baseline-only regression은 없으며, close shortfall 3개가 near-seat hold 부족으로 설명된다.

- 그 외 `under_insertion_count >= close_shortfall_success_count`
  - 추천: `v0_8a_fresh_z_progress_authority_slice`

- 그 외
  - 추천: `v0_8a_fresh_policy_class_rebase`

## 무결성 가드

- v0.7q는 `mvp2_closed=false`, `policy_uplift_proven=false`를 항상 기록한다.
- `proof_authority=false`를 기록한다.
- `heldout_opened=true`, `heldout_21000_21049_accessed=true`를 기록한다.
- `post_heldout_tuning_marker.json`을 루트에 기록해 이후 같은 proof output에서 tuning/rerun을 감지하게 한다.
- 다음 closure attempt는 fresh sealed split을 요구한다.

## 성공 기준

- v0.7p held-out gate가 존재하고 `heldout_opened=true`임을 확인한다.
- 실제 100개 held-out trace를 읽는다.
- paired outcome count가 gate의 baseline/candidate success count와 일치한다.
- candidate failure 9개가 모두 분류된다.
- close shortfall과 추천 downstream slice가 deterministic하게 산출된다.
- held-out proof 재사용 금지 marker가 기록된다.

## 비목표

- v0.7p metric 변경 금지
- v0.7p held-out rerun 금지
- controller/policy/adapter 수정 금지
- 같은 `21000-21049` split으로 MVP-2 closure 재시도 금지
- real robot/HMD/ROS/runtime scope 확장 금지
