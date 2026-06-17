# MVP-2E v0.12a Runtime Authority Dominance Diagnosis 설계

## 목표

v0.12 actual Isaac calibration이 fail-closed 된 이유를 artifact-only로 고정한다.

v0.12 결과:

- baseline calibration success: `25/30`
- candidate calibration success: `25/30`
- candidate-baseline gap: `0.0`
- failure reason: `baseline_calibration_success_floor_above_v0_12_maximum`
- held-out `36000-36049`: 미개봉

v0.12는 baseline training view를 terminal failure-window material 중심으로 바꿨지만,
runtime에서 baseline과 candidate outcome이 완전히 동일했다. 따라서 다음 가설을 검증한다.

> shared runtime authority / adapter / state-feedback layer가 learned residual 차이를 압축해,
> baseline과 candidate의 policy 차이가 task outcome으로 전달되지 않는다.

## 입력 증거

- `v0_12_baseline_floor_suppression_comparator/calibration_presignal_gate_v0_12.json`
- `v0_12_baseline_floor_suppression_comparator/calibration_external_rollouts/*.json`
- `v0_12_baseline_floor_suppression_comparator/isaac_runtime_fresh_calibration_v0_12/.../*trace.json`
- `baseline_policy_artifact_v0_12.json`
- `candidate_policy_artifact_v0_12.json`

## 진단 규칙

다음 조건을 모두 만족하면 primary root cause를
`RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME`로 분류한다.

1. v0.12 calibration gate가 actual Isaac runtime에서 생성됐다.
2. v0.12 calibration은 held-out을 열지 않고 fail-closed 됐다.
3. baseline success rate가 `V12_BASELINE_FLOOR_SUCCESS_MAXIMUM`을 초과한다.
4. candidate success rate가 `V12_CALIBRATION_SUCCESS_MINIMUM` 이상이다.
5. paired outcome divergence가 0 또는 매우 낮다.
6. `raw_action_before_authority` delta가 `post_adapter_action_vector` delta보다 크다.
7. final post-adapter action의 identical fraction 또는 shared authority active fraction이 높다.

## 산출물

- `v0_12a_runtime_authority_dominance_diagnosis.json`
- `v0_12a_paired_outcome_table.json`
- `v0_12a_action_compression_report.json`

## 다음 slice 추천

진단이 통과하면 다음 downstream slice는
`v0_13_policy_influence_authority_ceiling_slice`다.

v0.13의 방향:

- policy effect가 final action/outcome으로 전달되는지 먼저 gate로 검증한다.
- shared authority는 safety/contract layer로 남기되, task success를 대신 만들어내는 정도를 제한한다.
- candidate/baseline은 같은 authority ceiling, 같은 adapter, 같은 evaluator를 사용한다.
- held-out은 여전히 열지 않는다.

## Claim Boundary

이 진단은 closure authority가 아니다.

금지 claim:

- MVP-2 Closed
- policy uplift proven
- held-out A/B success
- real robot success
- deployable policy
- visual policy performance
