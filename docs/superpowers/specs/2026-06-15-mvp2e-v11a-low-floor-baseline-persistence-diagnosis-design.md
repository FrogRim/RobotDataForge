# MVP-2E v0.11a Low-Floor Baseline Persistence Diagnosis Spec

## 목적

`v0_11` actual Isaac calibration은 `baseline=21/30`, `candidate=25/30`,
`gap=+0.1333`으로 fail-closed 됐다. `candidate`는 충분히 강하지만
`baseline` low-floor comparator가 목표 floor 이하로 내려가지 않아 held-out을
열 수 없었다.

`v0_11a`는 새 Isaac 실행 없이 `v0_11` calibration artifact만 읽어 다음을
분류하는 artifact-only 진단 slice다.

- low-floor baseline training view가 실제 runtime baseline 성공률을 충분히
  낮췄는가
- candidate가 baseline 실패를 얼마나 회복했는가
- baseline이 candidate보다 나은 degradation seed가 있는가
- 다음 slice가 baseline comparator를 다시 낮춰야 하는지, candidate를 더
  강화해야 하는지

## 입력 증거

- `v0_11_low_floor_comparator_slice/calibration_presignal_gate_v0_11.json`
- `v0_11_low_floor_comparator_slice/calibration_external_rollouts/*.json`
- `v0_11_low_floor_comparator_slice/*policy_artifact_v0_11.json`
- `v0_11_low_floor_comparator_slice/low_floor_comparator_gate_v0_11.json`

## 판정 규칙

진단은 다음 순서로 fail-closed 분류한다.

1. `v0_11` calibration artifact가 없거나 `runtime_backend != isaac_runtime`이면
   `MISSING_OR_NON_ACTUAL_V11_CALIBRATION_EVIDENCE`.
2. `heldout_opened == true`이면 claim-boundary violation으로 실패한다. 이
   slice는 held-out 전용이 아니다.
3. `baseline_success_rate > 0.65`이고 `candidate_success_rate >= 0.80`이면
   `LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE`.
4. `candidate_success_rate < 0.80`이면
   `CANDIDATE_RUNTIME_SUCCESS_BELOW_MINIMUM`.
5. `candidate_baseline_success_gap < 0.20`이면
   `CALIBRATION_GAP_STILL_BELOW_MINIMUM`.

## 산출물

`v0_11a_low_floor_baseline_persistence_diagnosis/` 아래에:

- `v0_11a_low_floor_baseline_persistence_diagnosis.json`
- `v0_11a_paired_outcome_table.json`
- `v0_11a_policy_delta_report.json`

## 다음 slice 권고

주 분류가 `LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE`이면 다음 slice는
`v0_12_baseline_floor_suppression_comparator`다.

이 권고는 policy uplift proof가 아니다. held-out `34000-34049`는 계속 봉인한다.

## Claim Boundaries

- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `proof_authority=false`
- `heldout_opened=false`
- `fresh_heldout_34000_34049_accessed=false`
- real robot, HMD/OpenXR, visual policy, deployable policy claim 금지
