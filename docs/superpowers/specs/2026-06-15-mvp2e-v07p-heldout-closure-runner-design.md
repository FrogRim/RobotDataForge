# MVP-2E v0.7p Held-out Closure Runner 설계

## 목적

v0.7o는 `calibration_presignal_gate_v0_7o`에서 실제 Isaac calibration pre-signal을 통과했다.
하지만 기존 full `run_mvp2c_isaac_training_calibration.py` 경로는 `--policy-slice v0_7o`를
full held-out 실행에 연결하지 않는다. v0.7p는 v0.7o policy artifact를 그대로 사용해
pre-registered held-out `21000-21049`를 여는 전용 closure runner다.

## 성공 기준

- 부모 artifact는 `v0_7o_composed_xy_authority`여야 한다.
- `calibration_presignal_gate_v0_7o.passed=true` 및 `heldout_allowed=true` 전에는 held-out을 열지 않는다.
- held-out 실행 전까지 `heldout_21000_21049_accessed=false`를 검증한다.
- 실제 `IsaacConnectorInsertionEvaluatorBackend`로 baseline/candidate를 같은 held-out suite에서 실행한다.
- baseline/candidate는 같은 adapter, trainer, feature schema, hyperparameter family를 사용한다.
- close 최소 기준은 기존 MVP-2C 기준을 유지한다.
  - actual rollouts per policy >= 20
  - candidate success rate > baseline success rate
  - curated_vs_uncurated_uplift >= 0.20
  - train-generation runtime gate 통과
  - held-out leakage guard 통과
  - calibration-only selector guard 통과

## 금지

- v0.7o policy artifact를 재학습하지 않는다.
- held-out 결과를 본 뒤 adapter, trainer, threshold, success metric을 바꾸지 않는다.
- deterministic/local proxy rollout을 closure 증거로 승격하지 않는다.
- `21000-21049` held-out은 v0.7o calibration gate 통과 이후에만 접근한다.

## 산출물

- `v0_7p_heldout_closure/heldout_closure_gate_v0_7p.json`
- `v0_7p_heldout_closure/baseline_external_rollouts.json`
- `v0_7p_heldout_closure/candidate_external_rollouts.json`
- `v0_7p_heldout_closure/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json`
- root `evidence_manifest.json` 업데이트

## fail-closed 동작

- v0.7o calibration gate가 없거나 실패하면 held-out 미실행.
- v0.7o artifacts가 peer-fairness를 깨면 held-out 미실행.
- Isaac runtime이 실패하면 `mvp2_closed=false`와 runtime error artifact를 기록한다.
- held-out uplift가 기준 미달이면 `mvp2_closed=false`로 기록하고 다음 diagnosis slice로 넘어간다.
