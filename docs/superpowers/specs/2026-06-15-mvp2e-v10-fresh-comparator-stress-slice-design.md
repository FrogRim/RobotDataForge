# MVP-2E v0.10 Fresh Comparator Stress Slice Design

## 목표

`v0_9` actual Isaac held-out은 candidate가 baseline보다 낫다는 방향성은 보였지만,
baseline이 `0.88`로 너무 높아 `>=0.20` uplift close가 산술적으로 불가능했다.

v0.10의 목표는 새 calibration/held-out split을 사전등록하고, baseline uncurated
comparator를 더 강한 controlled raw/rejected-material stress view로 재구성해
MVP-2 close 조건을 다시 시도하는 것이다.

## v0.9에서 얻은 제약

source diagnosis:

- `v0_9a_heldout_uplift_shortfall_diagnosis_report.json`

핵심 제약:

- `27000-27049`는 opened/burned held-out이므로 다시 closure에 쓰지 않는다.
- v0.9 baseline success `0.88`에서는 candidate가 완벽해도 최대 uplift `0.12`다.
- v0.10은 v0.9 opened held-out outcome을 tuning target으로 사용하지 않는다.
- v0.10은 comparator definition, fresh split, gate를 실행 전에 고정한다.

## 새 split

사전등록 seed range:

- fresh calibration: `31000-31029`
- fresh held-out: `32000-32049`

burned/excluded ranges:

- `21000-21049`
- `24000-24049`
- `26000-26049`
- `27000-27049`
- `30000-30029`

held-out `32000-32049`는 calibration gate가 통과하기 전까지 열지 않는다.

## comparator stress 정의

v0.10 baseline은 `controlled_uncurated_stress` view다.

구성:

- candidate: v0.9 candidate curated rows를 그대로 사용한다.
- baseline: accepted/success rows + actual train-generation failed trace rows를 섞는다.
- baseline target failure-material row ratio: `0.70`
- failure material source: existing actual Isaac train-generation failed traces only.
- selection: deterministic round-robin, result-blind.
- per-seed tuning 금지.
- held-out outcome을 보고 ratio를 조정하는 것 금지.

왜 `0.70`인가:

- v0.9의 `0.40` failure-material row ratio는 baseline held-out success `0.88`을
  만들었고, opened held-out에서 close가 불가능했다.
- MVP-2 close requires `candidate_success_rate - baseline_success_rate >= 0.20`.
- v0.9 candidate가 `0.94`였으므로, baseline comparator가 적어도 `<=0.74`
  근처까지 내려와야 close 여지가 생긴다.
- `0.70`은 raw/rejected-material stress proof용 사전등록 값이며, 일반 uncurated
  데이터 분포에 대한 public benchmark claim이 아니다.

## fairness invariants

baseline/candidate는 다음을 동일하게 유지한다.

- `selected_action_adapter_id`
- `policy_class`
- `trainer`
- `trainer_family`
- `feature_schema`
- `phase_schema`
- `action_schema`
- shared runtime authority layers
- calibration selector behavior
- held-out success authority

차이는 dataset view content뿐이다.

## calibration gate

fresh calibration `31000-31029`에서 다음을 만족해야 held-out을 연다.

- `actual_rollouts_per_policy == 30`
- `candidate_calibration_success_rate >= 0.80`
- `candidate_calibration_success_rate > baseline_calibration_success_rate`
- `candidate_baseline_success_gap >= 0.20`
- `heldout_opened=false`
- `fresh_heldout_32000_32049_accessed=false`

통과하지 못하면 v0.10은 fail-closed하고, held-out은 열지 않는다.

## held-out closure gate

fresh held-out `32000-32049`에서 다음을 만족해야 MVP-2 Closed다.

- actual Isaac runtime
- 50 rollout/policy
- held-out leakage guard pass
- candidate success rate > baseline success rate
- curated_vs_uncurated_uplift >= 0.20
- MVP-2 learning validator proof eligible
- stronger public evidence target은 별도 field로 구분한다.

## claim boundary

v0.10이 pass하더라도 claim은 다음으로 제한한다.

허용:

- ForgeXR/RDF는 controlled uncurated-stress comparator에서 curated data가
  더 나은 held-out policy outcome을 만든다는 Isaac evaluator-domain proof를 보였다.

금지:

- real robot success
- deployable visual policy performance
- universal robot support
- HMD/OpenXR readiness
- 일반 uncurated robot data 전체에 대한 benchmark claim

## 산출물

새 child directory:

- `v0_10_fresh_comparator_stress_slice`

주요 artifacts:

- `v0_10_comparator_stress_config.json`
- `comparator_stress_gate_v0_10.json`
- `candidate_curated_train_v0_10.hdf5`
- `baseline_uncurated_stress_train_v0_10.hdf5`
- `candidate_policy_artifact_v0_10.json`
- `baseline_policy_artifact_v0_10.json`
- `v0_10_fresh_manifest.json`
- `calibration_presignal_gate_v0_10.json`
- `heldout_closure_gate_v0_10.json` only if calibration passes

## 다음 실패 루프

- calibration 실패: artifact-only `v0_10a_calibration_shortfall_diagnosis`
- held-out uplift 실패: artifact-only `v0_10b_heldout_shortfall_diagnosis`
- held-out close 성공: MVP-2 Closed package freeze
