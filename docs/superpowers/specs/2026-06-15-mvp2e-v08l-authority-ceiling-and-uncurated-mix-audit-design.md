# MVP-2E v0.8l Authority Ceiling / Uncurated Mix Audit 설계

## 목표

v0.8k actual Isaac calibration 결과는 lineage fix 이후 baseline 26/30, candidate 27/30으로 복구됐지만, candidate-baseline gap이 +0.033에 그쳐 calibration presignal gate를 통과하지 못했다.

v0.8l의 목표는 held-out을 열기 전에 다음 사실을 artifact-only로 확정하는 것이다.

- baseline이 shared authority 때문에 이미 높은 성공률을 보이는지
- candidate와 baseline residual/action 차이가 실제 rollout에서 압축됐는지
- baseline uncurated training view의 rejected/noisy rows가 실제로 label-conflict를 충분히 만들었는지
- 다음 downstream slice가 단순 candidate reweight가 아니라 fresh pre-registered comparator rebase여야 하는지

## 비목표

- held-out 27000-27049 개봉 금지
- success metric 변경 금지
- calibration gate threshold 완화 금지
- policy uplift claim 금지
- 새 Isaac runtime 실행 금지
- baseline을 사후로 독성 데이터셋처럼 조작 금지

## 입력 증거

- `v0_8k_candidate_training_signal_rebalance/calibration_presignal_gate_v0_8k.json`
- `v0_8k_candidate_training_signal_rebalance/baseline_uncurated_train_v0_8k.hdf5`
- `v0_8k_candidate_training_signal_rebalance/candidate_curated_train_v0_8k.hdf5`
- `v0_8k_candidate_training_signal_rebalance/isaac_runtime_fresh_calibration_v0_8k/isaac_runtime_heldout_rollout_traces/*.json`

## 판정 규칙

v0.8l은 proof authority가 아니다. 다음 조건이 모두 관측되면 `authority_ceiling_detected=true`로 기록한다.

- baseline calibration success rate >= 0.80
- candidate-baseline calibration success gap < 0.10
- held-out 27000-27049 access flag가 false

다음 조건 중 하나 이상이면 `uncurated_comparator_weak=true`로 기록한다.

- baseline rejected/noisy rows가 존재하지만, rejected DESCEND rows 중 강한 negative-z label 비율이 높다.
- candidate/baseline z-open residual mean 차이가 0.005 미만이다.
- candidate가 baseline failure seed 중 2개 이상을 복구하지 못한다.

## 출력

`storage/proof_evidence/mvp2c_isaac_training_calibration/v0_8l_authority_ceiling_uncurated_mix_audit/v0_8l_authority_ceiling_audit_report.json`

필수 필드:

- `schema_version`
- `policy_slice=v0_8l`
- `source_policy_slice=v0_8k`
- `source_v08k_calibration_gate_sha256`
- `baseline_calibration_success_rate`
- `candidate_calibration_success_rate`
- `candidate_baseline_success_gap`
- `authority_ceiling_detected`
- `uncurated_comparator_weak`
- `candidate_baseline_residual_z_mean_delta`
- `baseline_rejected_row_count`
- `baseline_rejected_descend_negative_z_fraction`
- `recommended_downstream_slice`
- `heldout_opened=false`
- `fresh_heldout_27000_27049_accessed=false`
- `mvp2_closed=false`
- `policy_uplift_proven=false`

## 다음 slice 권고

v0.8l이 ceiling/comparator weakness를 확정하면 다음 downstream slice는 `v0_9_fresh_attribution_preserving_uncurated_mix_rebase`가 된다.

그 slice는 fresh calibration/held-out split을 새로 pre-register하고, shared authority가 baseline까지 task를 대부분 해결하지 않도록 learned-action attribution을 보존해야 한다. 동시에 baseline uncurated mix는 사후 독성 조작이 아니라 사전 고정된 controlled failure taxonomy와 ratio를 가져야 한다.
