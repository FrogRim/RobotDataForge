# MVP-2E v0.9a Held-out Uplift Shortfall Diagnosis Design

## 목표

`v0_9_fresh_attribution_preserving_uncurated_mix_rebase`는 실제 Isaac held-out
`27000-27049`를 열었고, 50 rollout/policy를 생성했지만 MVP-2 close 기준을
통과하지 못했다.

v0.9a의 목표는 추가 Isaac 실행이나 정책 튜닝이 아니라, 이미 열린 v0.9
held-out 결과를 artifact-only로 진단해 다음 fresh proof slice가 왜 필요한지
증거화하는 것이다.

## 현재 증거

source artifact:

- `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_9_fresh_uncurated_mix_rebase/heldout_closure_gate_v0_9.json`

핵심 값:

- `actual_rollouts_per_policy=50`
- `baseline_success_rate=0.88`
- `candidate_success_rate=0.94`
- `curated_vs_uncurated_uplift=0.06`
- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `fresh_heldout_27000_27049_accessed=true`

중요한 산술:

- 현재 opened held-out에서 baseline이 이미 `0.88`이다.
- 같은 held-out에서 candidate가 완벽하게 `1.00`을 달성해도 최대 uplift는
  `1.00 - 0.88 = 0.12`다.
- MVP-2 close minimum은 `curated_vs_uncurated_uplift >= 0.20`이므로, 이미
  열린 v0.9 held-out은 더 이상 이 기준으로 close할 수 없다.

따라서 v0.9a는 v0.9 held-out을 재사용해 closure를 시도하지 않는다.

## 진단 산출물

새 artifact:

- `v0_9a_heldout_uplift_shortfall_diagnosis/v0_9a_heldout_uplift_shortfall_diagnosis_report.json`

필수 필드:

- `schema_version`
- `policy_slice="v0_9a"`
- `source_policy_slice="v0_9"`
- `source_heldout_closure_gate_path`
- `source_heldout_closure_gate_sha256`
- `actual_rollouts_per_policy`
- `baseline_success_rate`
- `candidate_success_rate`
- `curated_vs_uncurated_uplift`
- `required_minimum_uplift=0.20`
- `max_possible_uplift_on_opened_heldout`
- `opened_heldout_can_no_longer_close_minimum`
- `paired_outcome_counts`
- `baseline_failure_seeds`
- `candidate_failure_seeds`
- `candidate_recovered_baseline_failure_seeds`
- `common_failure_seeds`
- `baseline_ceiling_compression`
- `candidate_non_regression`
- `failure_mix_did_not_create_sufficient_uncurated_heldout_gap`
- `common_failure_trace_summaries`
- `proof_authority=false`
- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `heldout_opened=true`
- `fresh_heldout_27000_27049_accessed=true`
- `same_heldout_reuse_allowed_for_closure=false`
- `recommended_downstream_slice`
- `recommended_next_valid_step`

## 분류 규칙

### paired outcome

각 `scenario_id`에 대해 baseline/candidate success를 pair한다.

- `B1_C1`: baseline success, candidate success
- `B1_C0`: baseline success, candidate fail
- `B0_C1`: baseline fail, candidate success
- `B0_C0`: baseline fail, candidate fail

v0.9 실측 기준 예상 구조:

- `B1_C1=44`
- `B1_C0=0`
- `B0_C1=3`
- `B0_C0=3`

### shortfall root classification

- `baseline_ceiling_compression=true` if `baseline_success_rate >= 0.85`
- `candidate_non_regression=true` if `B1_C0 == 0`
- `failure_mix_did_not_create_sufficient_uncurated_heldout_gap=true` if
  `baseline_success_rate > 1.0 - required_minimum_uplift`
- `opened_heldout_can_no_longer_close_minimum=true` if
  `max_possible_uplift_on_opened_heldout < required_minimum_uplift`

### trace summary

공통 실패 seed와 baseline failure seed는 trace가 존재하면 다음 값을 요약한다.

- `max_insertion_depth_m`
- `min_lateral_error_m`
- `final_insertion_depth_m`
- `final_lateral_error_m`
- `z_nonzero_steps`
- `env_native_max_consecutive_success_steps`
- `failure_mode`

trace가 없으면 진단은 실패하지 않고 `trace_summary_available=false`로 기록한다.

## claim boundary

v0.9a는 closure authority가 아니다.

금지 claim:

- MVP-2 Closed
- policy uplift proven
- v0.9 held-out 재사용으로 close 가능
- real robot success
- deployable visual policy performance

허용 claim:

- v0.9 actual Isaac held-out에서 candidate는 baseline보다 나빠지지 않았다.
- candidate는 baseline 실패 6개 중 3개를 회복했다.
- 하지만 baseline이 0.88로 너무 높아 opened held-out에서는 +0.20 uplift close가 산술적으로 불가능하다.
- 다음 proof는 새로 사전등록된 fresh split과 더 방어 가능한 comparator stress 설계가 필요하다.

## 다음 downstream slice

권장 downstream:

- `v0_10_fresh_comparator_stress_slice`

v0.10은 v0.9 opened held-out 결과를 tuning target으로 쓰면 안 된다. v0.9a는
다음 설계의 정당화만 제공한다. 새 closure proof는 새 pre-registered calibration과
새 sealed held-out에서만 가능하다.
