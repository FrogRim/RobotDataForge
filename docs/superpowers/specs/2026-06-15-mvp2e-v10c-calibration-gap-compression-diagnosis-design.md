# MVP-2E v0.10c Calibration Gap Compression Diagnosis 설계

## 목표

v0.10b runtime authority lineage repair 이후 실제 Isaac v0.10 calibration이
baseline 23/30, candidate 25/30으로 회복됐지만, `candidate_baseline_success_gap=0.0667`이라
MVP-2 close minimum인 `+0.20`을 통과하지 못했다.

v0.10c는 새 policy를 학습하거나 held-out을 열지 않는다. 이미 열린 calibration artifact만 읽어
왜 curated candidate와 uncurated baseline의 gap이 압축됐는지 buyer/audit 가능한 진단으로 고정한다.

## 입력

- `v0_10_fresh_comparator_stress_slice/calibration_presignal_gate_v0_10.json`
- `v0_10_fresh_comparator_stress_slice/calibration_external_rollouts/{baseline,candidate}_calibration_rollouts_v0_10.json`
- 각 rollout의 Isaac trace JSON
- `candidate_policy_artifact_v0_10.json`
- `baseline_policy_artifact_v0_10.json`

## 불변 조건

- `runtime_backend=isaac_runtime`인 실제 calibration artifact만 허용한다.
- `heldout_opened=false`
- `fresh_heldout_32000_32049_accessed=false`
- v0.10 held-out은 v0.10c에서 절대 열지 않는다.
- success metric, calibration threshold, held-out threshold를 바꾸지 않는다.
- policy uplift를 claim하지 않는다.

## 진단 산출물

출력 파일:

`storage/proof_evidence/mvp2c_isaac_training_calibration/v0_10c_calibration_gap_compression_diagnosis/v0_10c_calibration_gap_compression_diagnosis_report.json`

필수 필드:

- `policy_slice="v0_10c"`
- `source_policy_slice="v0_10"`
- `runtime_backend="offline_artifact_diagnosis"`
- `baseline_calibration_success_count`
- `candidate_calibration_success_count`
- `candidate_baseline_success_gap`
- `required_candidate_baseline_success_gap=0.20`
- `paired_outcome_counts`
- `candidate_degraded_baseline_success_seeds`
- `candidate_recovered_baseline_failure_seeds`
- `common_failure_seeds`
- `baseline_ceiling_compression`
- `candidate_non_regression`
- `shared_authority_success_floor_detected`
- `primary_root_cause_class`
- `recommended_downstream_slice`
- `heldout_opened=false`
- `fresh_heldout_32000_32049_accessed=false`
- `mvp2_closed=false`
- `policy_uplift_proven=false`

## 분류 규칙

`CALIBRATION_GAP_COMPRESSED_BY_BASELINE_SUCCESS_FLOOR` 조건:

- calibration gate가 fail이고,
- failure reason이 `candidate_baseline_success_gap_below_v0_10_minimum`이며,
- candidate success rate는 `0.80` 이상이고,
- baseline success rate가 `0.70` 이상이고,
- `B1_C0 == 0`이며,
- `B0_C1 < 6`이다.

해석:

- candidate는 baseline 성공 케이스를 망치지 않는다.
- candidate가 일부 baseline 실패를 복구하지만, baseline이 shared runtime authority / base servo floor로 너무 많이 성공한다.
- 이 상태에서 held-out을 열면 +0.20 uplift를 기대하기 어렵다.

## 다음 slice 권고

진단이 위 root cause로 확정되면 downstream은 새 fresh seed range를 쓰는
`v0_11_attribution_preserving_low_floor_comparator_slice`로 권고한다.

v0.11 방향:

- 기존 held-out `32000-32049`는 v0.10용으로 봉인 유지 또는 burned 처리한다.
- 새 calibration/held-out range를 pre-register한다.
- success metric은 env-native 10-consecutive 그대로 둔다.
- shared safety authority는 유지하되, baseline/candidate 차이를 죽이는 comparator floor를 별도 harness로 측정한다.
- baseline을 사후 독성화하지 않는다. baseline view mix와 comparator config는 v0.11 실행 전 hash-stable로 고정한다.

## Non-claims

- MVP-2 Closed 아님.
- policy uplift proven 아님.
- real robot success 아님.
- deployable visual policy 아님.
- HMD/OpenXR readiness 아님.
