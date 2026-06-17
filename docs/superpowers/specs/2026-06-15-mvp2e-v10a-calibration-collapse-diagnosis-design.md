# MVP-2E v0.10a Calibration Collapse Diagnosis Design

## 목적

`v0_10_fresh_comparator_stress_slice`는 artifact-only comparator stress gate를 통과했지만 실제 Isaac calibration에서 fail-closed 됐다.

핵심 실패 증거:

- `policy_slice=v0_10`
- 실제 Isaac runtime 사용
- calibration `31000-31029` opened
- held-out `32000-32049` unopened
- baseline `0/30`
- candidate `1/30`
- failure reason: `candidate_calibration_success_below_v0_10_minimum`

`v0_10a`의 목적은 추가 Isaac 실행 없이 이미 생성된 v0.10 calibration traces와 v0.9 working traces를 비교해, 실패가 정책 데이터 효과인지 runtime authority lineage collapse인지 분류하는 것이다.

## Product / Claim Boundary

이 진단은 proof authority가 아니다.

- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `proof_authority=false`
- `runtime_backend=offline_artifact_diagnosis`
- held-out `32000-32049`를 열지 않는다.

## Required Evidence

`v0_10a`는 아래 artifact가 없으면 fail-closed 한다.

- `v0_10_fresh_comparator_stress_slice/calibration_presignal_gate_v0_10.json`
- `v0_10_fresh_comparator_stress_slice/candidate_policy_artifact_v0_10.json`
- `v0_10_fresh_comparator_stress_slice/baseline_policy_artifact_v0_10.json`
- `v0_10_fresh_comparator_stress_slice/calibration_external_rollouts/candidate_calibration_rollouts_v0_10.json`
- `v0_10_fresh_comparator_stress_slice/calibration_external_rollouts/baseline_calibration_rollouts_v0_10.json`
- `v0_10_fresh_comparator_stress_slice/isaac_runtime_fresh_calibration_v0_10/isaac_runtime_heldout_rollout_traces/*.json`
- `v0_9_fresh_uncurated_mix_rebase/candidate_policy_artifact_v0_9.json`
- `v0_9_fresh_uncurated_mix_rebase/calibration_external_rollouts/candidate_calibration_rollouts_v0_9.json`
- `v0_9_fresh_uncurated_mix_rebase/isaac_runtime_fresh_calibration_v0_9/isaac_runtime_heldout_rollout_traces/*.json`

## Diagnosis Invariants

`v0_10a`는 다음을 검증한다.

1. v0.10 candidate policy weights/bias are unchanged from v0.9 candidate.
2. v0.10 candidate policy carries the same authority config hashes as v0.9 candidate.
3. v0.10 actual trace diagnostics do not apply the inherited authority stack.
4. v0.9 actual trace diagnostics do apply the inherited authority stack.
5. v0.10 held-out `32000-32049` remains unopened.

## Authority Lineage Collapse Definition

Primary root cause is `RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING` when all are true:

- v0.10 candidate weights equal v0.9 candidate weights.
- v0.10 candidate authority hashes equal v0.9 candidate authority hashes.
- v0.10 candidate traces contain `policy_slice=v0_10`.
- v0.10 candidate traces show `z_motion_block_reason=no_v06_controller` for most rows.
- v0.10 candidate traces show no `shared_hysteresis_authority_id`.
- v0.10 candidate traces show no `final_post_adapter_authority_id`.
- v0.10 candidate traces show no `final_post_adapter_xy_authority_id`.
- v0.9 candidate traces show those authority diagnostics present.

## Outputs

Write:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_10a_calibration_collapse_diagnosis/
    v0_10a_calibration_collapse_diagnosis_report.json
```

Report fields:

- `schema_version`
- `policy_slice=v0_10a`
- `source_policy_slice=v0_10`
- `runtime_backend=offline_artifact_diagnosis`
- `proof_authority=false`
- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `heldout_opened=false`
- `fresh_heldout_32000_32049_accessed=false`
- `v0_10_calibration_success`
- `v0_9_candidate_calibration_success`
- `candidate_weights_unchanged_from_v09`
- `candidate_authority_hashes_unchanged_from_v09`
- `v0_10_authority_diagnostics`
- `v0_9_authority_diagnostics`
- `primary_root_cause_class`
- `recommended_downstream_slice`
- `v0_10a_calibration_collapse_diagnosis_sha256`

## Recommended Downstream Slice

If `RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING` is classified, recommend:

```text
v0_10b_runtime_policy_slice_authority_lineage_repair
```

This repair must not change trainer, policy weights, comparator mix, success metric, calibration seeds, or held-out seeds. It may only make the evaluator runtime treat `v0_10` as a v0.9-derived policy slice with the already-declared authority stack.

## Verification

Minimum verification:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10a or v10b" -q
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

Then run artifact-only diagnosis:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_10a \
  --fresh-comparator-calibration-diagnosis-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```
