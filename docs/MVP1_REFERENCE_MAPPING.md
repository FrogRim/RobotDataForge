# MVP-1 Reference Mapping

이 문서는 사용자 제공 MVP-1 참고 보고서를 현재 Robot Data Forge 구현 계획으로 번역한 압축 매핑이다. 외부 시스템 자체를 복제하지 않고, MVP-1에서 구현 가능한 데이터 인프라 요구사항만 반영한다.

## 2026-05-18 Reframe

MVP-1은 `learning-ready` Validated Dataset Pipeline Proof다. Quest/SteamVR/OpenXR/Isaac raw trajectory가 저장되고, task state/outcome, data quality, operator/evaluator separation, replay/action gate, curation manifest, HDF5 export, trainer loader smoke, dataset card까지 연결되면 MVP-1은 통과한다.

Curated dataset이 uncurated baseline보다 downstream policy success rate를 올린다는 `learning-proven` 주장은 MVP-2 Policy Uplift Proof로 이동했다. 이 문서의 이전 `MVP-1C` 표현은 legacy policy-uplift section으로 해석한다.

## Core Thesis

MVP-1의 목표는 Quest/Isaac recording 자체가 아니라 `peg-in-hole` 또는 `connector insertion`에서 raw XR/HMD trajectory를 검증, 큐레이션, export, trainer-load 가능한 learning-ready dataset artifact로 승격하는 증거를 남기는 것이다.

## Staged MVP-1 Structure

MVP-1은 한 번에 끝나는 단일 gate가 아니라 세 단계로 나눈다. 이 구분은 앞으로 Go/No-Go 판단과 문서, proof audit, 다음 작업 우선순위에 반영한다.

| 단계 | 목적 | 완료 증거 | 아직 주장하면 안 되는 것 |
|---|---|---|---|
| MVP-1A: Real Insertion Data Path | 실제 Quest/SteamVR/OpenXR/Isaac insertion task에서 학습 가능한 trajectory가 기록되는지 증명 | real peg-in-hole 또는 connector trajectory, `metadata.task_state`, phase/eval/curation/export 통과 | policy 성능 향상, customer/investor proof 완료 |
| MVP-1B: Training Readiness | export artifact가 실제 policy trainer에 연결되는지 증명 | exported dataset loader 통과, ACT/BC 등 1 epoch 또는 dry-run training smoke, schema/normalization/split 재현성 | curated가 uncurated보다 낫다는 성능 claim |
| MVP-2: Learning Value Proof | curated dataset의 downstream learning value를 증명 | transition-rich accepted dataset, stronger trainer, held-out suite에서 curated vs uncurated uplift 측정, confidence interval, positive/negative result report | 측정되지 않은 uplift, 일반화되지 않은 customer claim |

판단 규칙:

- MVP-1A가 없으면 MVP-1B/1C 증거는 synthetic/offline proof에 머문다.
- MVP-1B가 없으면 export는 training-ready가 아니라 schema-ready에 가깝다.
- MVP-2가 없으면 learning-proven policy uplift를 주장하지 않는다.
- 현재 `run_mvp1_proof_audit.py`의 `pass` 상태는 MVP-1 learning-ready proof가 닫혔다는 뜻이며, policy uplift를 주장한다는 뜻이 아니다.

필수 산출물:

```text
accepted dataset package
dataset card
replay/QA evidence
MVP-2 curated > uncurated uplift report 또는 negative result report
```

## P0 Mapping

| 참고 항목 | 현재 상태 | 다음 구현 |
|---|---|---|
| insertion phase taxonomy | `ActionSegment` 존재, `SEAT` 지원 추가 | recorder/evaluator가 `action_phase`를 생성 |
| Quest teleop quality instrumentation | raw/applied action, calibration analyzer, preflight 구현 | live calibration preset 축적 |
| curator + rejection reasons | ForgeCurate와 usability rejection reason 구현 | human review agreement 연결 |
| curated vs uncurated A/B | 아직 없음 | dataset split/export와 training report spec 작성 |
| OXE-style schema/export + dataset card | dataset card placeholder와 source metadata 존재 | split manifest와 stronger dataset card 추가 |

## Offline Readiness Bundle

HMD 없이 CLI에서 MVP-1 data contract를 확인하는 bundle을 제공한다.

```bash
uv run python scripts/run_mvp1_offline_readiness.py --clean
```

현재 bundle이 확인하는 것:

- `peg_in_hole` `metadata.task_state` 기반 evaluator success/failure
- `APPROACH -> ALIGN -> CONTACT -> INSERT -> SEAT -> RELEASE` phase coverage
- data usability score와 rejection reason 생성
- ForgeCurate accepted/rejected manifest
- train/validation/test split manifest
- dataset card 생성
- curated accepted trajectory의 HDF5 export와 inspector sanity check
- curated vs uncurated A/B 실험 manifest

중요한 제한:

- 이 bundle은 synthetic/offline fixture다.
- 실제 Quest/Isaac live run 증거가 아니다.
- `curated_vs_uncurated_uplift`는 측정하지 않으며 `null`로 유지한다.
- 실제 learning uplift는 MVP-2 policy A/B 평가 이후에만 채울 수 있다.

## Proof Audit

MVP-1 proof는 readiness artifact만으로 완료되지 않는다. 현재 증거 상태를 gate별로 판정하는 audit CLI를 둔다.

```bash
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

현재 MVP-1 learning-ready proof에 필요한 gate:

- raw XR trajectory saved
- task_state extracted
- task_outcome recorded
- data_quality recorded
- operator_success separated from evaluator_task_success
- replay/action gate recorded
- accepted/rejected curation manifest generated
- HDF5 export generated
- trainer loader smoke passed
- dataset card generated
- policy claim integrity preserved

현재 expected status:

```text
pass
```

이유:

- CLI readiness, live trajectory evidence, curation/export, trainer loader smoke가 연결됐다.
- proof audit는 MVP-1을 learning-ready dataset pipeline proof로 평가한다.
- Isaac held-out policy A/B 결과는 baseline/candidate success rate가 모두 `0.0`이므로 MVP-2 negative evidence로 보존한다.
- Policy uplift는 MVP-1 required gate가 아니다.

staged 해석:

- 현재 상태는 MVP-1 learning-ready 완료다.
- 다음 제품 proof는 MVP-2이며, curated vs uncurated held-out policy uplift가 positive로 측정되어야 한다.
- MVP-1 완료는 주장할 수 있지만, learning-proven policy uplift는 아직 주장하지 않는다.

MVP-1 trainer smoke:

```bash
uv run python scripts/run_mvp1_trainer_smoke.py --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

이 smoke는 HDF5 export, split manifest, observation/action arrays, deterministic BC-style dry-run을 검증한다. 다만 `learning_results_measured=false`와 `curated_vs_uncurated_uplift=null`을 유지하므로, policy 성능 향상 claim은 여전히 금지된다.

MVP-1 stronger live-export smoke:

```bash
uv run python scripts/run_mvp1_live_export_smoke.py --clean --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

이 경로는 이미 수집된 live trajectory를 `storage/mvp1_live_export/`로 묶고, 해당 live-derived HDF5가 trainer smoke를 통과하는지 확인한다. HMD 재착용은 필요 없다. proof audit의 `trainer_loader_smoke_passed` evidence는 live-export evidence path, live trajectory id, live HDF5 path를 포함한다.

제한:

- single live trajectory split은 smoke-only다.
- policy uplift와 generalization은 MVP-2에서만 주장한다.
- live candidate가 `failure` lifecycle이어도 export/trainer smoke에는 사용할 수 있다. 여기서 증명하는 것은 success가 아니라 data path/training readiness다.

## Phase Taxonomy

MVP-1 insertion task에서 우선 지원하는 phase:

```text
APPROACH
ALIGN
CONTACT
INSERT
SEAT
RELEASE
```

기존 generic phase도 유지한다.

```text
STABILIZE
RECOVER
UNKNOWN
```

해석:

- `SEAT`: peg/connector가 final depth에 들어가 seating되는 구간.
- `STABILIZE`: seating 이후 흔들림이 줄어드는 broad stabilization 구간.
- `UNKNOWN`: explicit phase signal이 아직 없다는 뜻이며 실패가 아니다.

## Experiment Direction

권장 MVP-1 실험:

```text
Task: peg-in-hole first, connector insertion second
Data: accepted 30-50 minimum, 60-100 preferred
Split: train/val/test 70/15/15 plus held-out pose/clearance variant
Baseline A: BC on uncurated success-only
Baseline B: BC on curated accepted-only
Metric: success rate uplift on held-out suite
```

주의:

- learning KPI는 실제 training/evaluation 전까지 placeholder로만 둔다.
- synthetic augmentation, tactile, verifier-guided retry는 post-MVP 또는 P2다.
- Stack cube MVP-0 결과를 insertion customer proof로 과장하지 않는다.

## MVP-1C Measurement Gate

MVP-1C는 smoke test가 아니라 실제 learning value proof다. 따라서 proof audit는 다음 조건을 모두 요구한다.

```text
learning_results_measured=true
curated_vs_uncurated_uplift > 0
policy_uplift_measurement.proof_eligible=true
policy_uplift_measurement.evidence_tier in [heldout_policy_eval, real_heldout_policy_eval]
policy_uplift_measurement.primary_metric=policy_success_rate
policy_uplift_measurement.secondary_metrics.rollout_success_rate present
```

Offline proxy smoke는 다음 명령으로 실행한다.

```bash
uv run python scripts/run_mvp1c_policy_uplift_smoke.py --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

현재 offline proxy smoke 결과는 다음과 같다.

```text
baseline=uncurated_success_lifecycle
candidate=curated_accepted
primary_metric=action_prediction_score
evidence_tier=offline_proxy_smoke
proof_eligible=false
uncurated_score=0.9670253734580941
curated_score=0.9327330477860399
proxy_delta=-0.0342923256720542
```

판단:

- 현재 proxy에서는 curated가 uncurated보다 낮다.
- 이 수치는 full MVP-1C proof가 아니며, proof audit도 이를 통과시키지 않는다.
- 다음 단계는 실제 collected insertion dataset을 충분히 모으고, held-out rollout suite에서 policy success rate를 비교하는 것이다.

Real held-out rollout 결과가 생기면 다음 CLI로 manifest에 반영한다.

```bash
uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1_readiness/policy_eval_input.json \
  --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

이 CLI는 success-rate uplift를 계산하고 `confidence_interval_95`를 남긴다. 단, 다음 조건이 아니면 full MVP-1C proof로 인정하지 않는다.

- real held-out policy eval evidence
- insertion task type
- held-out suite 명시
- uncurated baseline vs curated candidate 명시
- policy당 최소 rollout 수 충족
- curated success rate가 uncurated success rate보다 높음

negative real eval은 실패가 아니라 중요한 측정 결과다. 이 경우 fake uplift gate는 통과하지만 MVP-1C gate는 계속 실패한다.

MVP-1C headless A/B 평가를 준비하는 bundle은 다음 명령으로 생성한다.

```bash
uv run python scripts/run_mvp1c_headless_eval_bundle.py --clean --pretty
```

이 bundle은 uncurated train HDF5와 curated train HDF5를 분리하고, held-out suite manifest와 real policy eval input template을 만든다.

```text
baseline_uncurated/mvp1c_uncurated_success_lifecycle_train.hdf5
candidate_curated/mvp1c_curated_accepted_train.hdf5
heldout_suite_manifest.json
policy_eval_input_template.json
```

이 단계는 training/eval 준비물이며, learning result가 아니다. full MVP-1C는 template의 `rollout_results`가 실제 headless policy rollout 결과로 채워지고 `run_mvp1c_real_policy_eval.py`를 통과했을 때만 주장한다.

Trainer/evaluator가 CSV 또는 JSON rollout log를 만든 뒤에는 adapter로 template을 채운다.

```bash
uv run python scripts/run_mvp1c_rollout_result_adapter.py \
  --template storage/mvp1c_headless_eval/policy_eval_input_template.json \
  --baseline-results path/to/baseline_rollouts.csv \
  --candidate-results path/to/candidate_rollouts.json \
  --output storage/mvp1c_headless_eval/policy_eval_input.json \
  --policy-class ACT \
  --trainer your_headless_trainer
```

지원 입력:

- CSV: `rollout_id,scenario_id,success`
- JSON list: `[{"rollout_id": "...", "scenario_id": "...", "success": true}]`
- JSON object: `{"rollout_results": [...]}`
- aggregate JSON: `{"rollout_count": 20, "success_count": 12}`

이 adapter는 manifest를 갱신하지 않는다. 다음 명령이 valid real held-out input으로 판정해야 MVP-2 policy-uplift proof에 반영된다.

```bash
uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1c_headless_eval/policy_eval_input.json \
  --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

Historical verification:

- rollout adapter focused/headless/real-eval tests: `8 passed`
- full API tests: `85 passed`
- compileall: passed
- old proof audit framing: `current_stage=MVP-1B`, `next_stage=MVP-1C`, gates `9/10`

따라서 headless bridge는 준비됐지만, positive held-out policy rollout 결과가 없으면 MVP-2 learning-proven은 아직 주장하지 않는다.

Isaac 자체에서 HUD/HMD 없이 rollout smoke를 돌리는 경로도 추가했다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/run_mvp1c_isaac_policy_ab_smoke.py \
  --rollouts-per-policy 2 \
  --max-steps 80 \
  --pretty
```

이 runner는 baseline/candidate HDF5에서 lightweight BC policy를 fit하고 `Isaac-Forge-PegInsert-Direct-v0`에서 같은 seed set으로 rollout한다. 산출물은 `storage/mvp1c_isaac_policy_ab_smoke/`에 저장된다.

현재 smoke 결과:

- baseline success rate: `0.0`
- candidate success rate: `0.0`
- evidence tier: `isaac_headless_policy_eval_smoke`
- proof eligible: `false`
- old proof audit framing: `current_stage=MVP-1B`, `next_stage=MVP-1C`, gates `9/10`

판단:

- HUD/HMD 없이 실제 Isaac rollout execution은 가능하다.
- 현재 tiny readiness fixture와 lightweight BC policy는 success를 만들지 못했다.
- 이 결과는 제품적으로 유용한 negative smoke지만 MVP-2 learning-proven proof는 아니다.
- 다음 proof-grade 반복은 real insertion accepted/uncurated train set을 늘리고, held-out pose/clearance scenarios에서 최소 policy당 10회, 권장 50회 이상 rollout해야 한다.

MVP-2 policy-uplift ingest 직전 상태는 다음 preflight로 확인한다.

```bash
uv run python scripts/run_mvp1c_final_hud_ingest_preflight.py \
  --refresh-headless-bundle \
  --pretty
```

현재 결과:

- `ready_for_mvp2_policy_uplift_ingest=true`
- `mvp2_learning_proven_claimed=false`
- `current_stage=MVP-1`
- `next_stage=MVP-2`
- missing MVP-1 gates: `[]`

이 상태의 의미:

- MVP-2를 위해 transition-rich accepted data와 real held-out policy A/B rollout이 남았다.
- headless bundle, template, adapter, real eval ingest, proof audit path는 준비됐다.
- MVP-2 learning-proven은 아직 완료가 아니며, positive policy success-rate uplift가 측정되어야 한다.
