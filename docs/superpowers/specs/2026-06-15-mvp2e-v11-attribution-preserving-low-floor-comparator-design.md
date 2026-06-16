# MVP-2E v0.11 Attribution-Preserving Low-Floor Comparator 설계

## 목표

v0.10b 수리 후 actual Isaac calibration은 candidate가 baseline을 악화시키지 않고
baseline failure 2개를 회복했지만, baseline이 `23/30`까지 성공해
`candidate_baseline_success_gap=0.0667`에 머물렀다.

v0.11의 목표는 새 fresh split에서 baseline comparator floor를 실행 전에 낮추고,
그 floor가 실제 calibration에서 충분히 낮은지 audit한 뒤에만 held-out을 여는 것이다.

## source diagnosis

입력 진단:

- `v0_10c_calibration_gap_compression_diagnosis_report.json`

필수 source 조건:

- `primary_root_cause_class=CALIBRATION_GAP_COMPRESSED_BY_BASELINE_SUCCESS_FLOOR`
- `candidate_non_regression=true`
- `candidate_degraded_baseline_success_seeds=[]`
- `candidate_recoveries_observed=2`
- `candidate_recoveries_required_for_minimum_gap=6`
- `heldout_opened=false`
- `fresh_heldout_32000_32049_accessed=false`

## 새 split

사전등록 seed range:

- fresh calibration: `33000-33029`
- fresh held-out: `34000-34049`

excluded ranges:

- opened held-out: `21000-21049`, `24000-24049`, `26000-26049`, `27000-27049`
- opened calibration: `30000-30029`, `31000-31029`
- sealed v0.10 held-out: `32000-32049`

held-out `34000-34049`는 v0.11 calibration gate가 통과하기 전까지 열지 않는다.

## low-floor comparator 정의

v0.11 baseline은 `low_floor_uncurated_stress` view다.

구성:

- candidate: v0.10/v0.9 candidate curated rows를 그대로 사용한다.
- baseline: accepted/success rows + actual train-generation failed trace rows를 섞는다.
- baseline target failure-material row ratio: `0.90`
- allowed actual ratio: `[0.85, 0.95]`
- failure material source: existing actual Isaac train-generation failed traces only.
- selection: deterministic round-robin, result-blind.
- calibration/held-out rollout outcome을 보고 ratio를 조정하지 않는다.
- per-seed tuning 금지.

왜 `0.90`인가:

- v0.10의 `0.70` failure-material row ratio에서도 baseline이 `23/30` 성공했다.
- v0.11은 "일반 uncurated 데이터 분포"가 아니라 comparator floor를 낮추는 stress
  comparator다.
- `0.90`은 v0.10c root cause인 shared authority floor를 calibration에서 드러내기
  위한 사전등록 값이며, public benchmark 분포 claim이 아니다.

## fairness / attribution invariants

baseline/candidate는 다음을 동일하게 유지한다.

- `selected_action_adapter_id`
- `policy_class`
- `trainer`
- `trainer_family`
- `feature_schema`
- `phase_schema`
- `action_schema`
- shared runtime authority layers
- env-native 10-consecutive success authority

차이는 dataset view content뿐이다.

Attribution preservation:

- calibration에서 `B1_C0 == 0`이어야 한다.
- candidate uplift는 baseline failure recovery에서 나와야 한다.
- candidate success가 shared authority만으로 올라간 것인지 확인하기 위해
  baseline success floor ceiling을 별도 audit한다.

## calibration gate

fresh calibration `33000-33029`에서 다음을 모두 만족해야 held-out을 연다.

- actual Isaac runtime
- `actual_rollouts_per_policy == 30`
- `candidate_calibration_success_rate >= 0.80`
- `candidate_calibration_success_rate > baseline_calibration_success_rate`
- `candidate_baseline_success_gap >= 0.20`
- `baseline_calibration_success_rate <= 0.65`
- `attribution_preservation_gate_passed=true`
- `heldout_opened=false`
- `fresh_heldout_34000_34049_accessed=false`

통과하지 못하면 v0.11은 fail-closed하고, held-out은 열지 않는다.

## held-out closure gate

fresh held-out `34000-34049`에서 다음을 만족해야 MVP-2 Closed다.

- actual Isaac runtime
- 50 rollout/policy
- candidate success rate > baseline success rate
- curated_vs_uncurated_uplift >= `0.20`
- no held-out leakage
- MVP-2 learning-proven report generated

## claim boundary

허용:

- Isaac evaluator-domain에서 pre-registered low-floor uncurated comparator 대비
  curated dataset policy가 더 나은 held-out outcome을 만들었는지 검증한다.

금지:

- real robot success
- deployable real-world visual policy performance
- HMD/OpenXR readiness
- 일반 uncurated robot data 전체에 대한 public benchmark claim
- policy uplift proof before held-out pass

## 산출물

child directory:

- `v0_11_low_floor_comparator_slice`

주요 artifacts:

- `v0_11_low_floor_comparator_config.json`
- `low_floor_comparator_gate_v0_11.json`
- `candidate_curated_train_v0_11.hdf5`
- `baseline_uncurated_low_floor_train_v0_11.hdf5`
- `candidate_policy_artifact_v0_11.json`
- `baseline_policy_artifact_v0_11.json`
- `v0_11_fresh_manifest.json`
- `calibration_presignal_gate_v0_11.json`
- `heldout_closure_gate_v0_11.json` only if calibration passes

## 다음 실패 루프

- calibration floor가 여전히 높음: artifact-only `v0_11a_low_floor_failure_diagnosis`
- calibration은 통과했지만 held-out uplift 미달: artifact-only
  `v0_11b_heldout_shortfall_diagnosis`
- held-out close 성공: MVP-2 Closed package freeze
