# MVP-2B Isaac Proof Evaluator Design

Date: 2026-06-10

## 목적

MVP-2B의 목적은 ForgeXR / Robot Data Forge가 `learning-proven` policy
uplift를 정직하게 증명할 수 있도록, Isaac Sim / Isaac Lab 기반의 전용
connector insertion evaluator를 만드는 것이다.

MVP-2 Closed는 다음 claim만 허용한다.

```text
pre-registered held-out Isaac scenarios에서,
같은 policy class / trainer / phase input / hyperparameter를 사용했을 때,
curated dataset으로 학습한 candidate policy가 uncurated dataset으로 학습한
baseline policy보다 policy_success_rate가 실용적으로 더 높았다.
```

## 비목표

- real robot success를 주장하지 않는다.
- physical UR readiness를 주장하지 않는다.
- HMD/OpenXR readiness를 주장하지 않는다.
- marketplace, production auth, VLA fine-tuning, World Model training을 만들지
  않는다.
- local proxy, schema fixture, template, smoke-only result를 MVP-2 proof로
  승격하지 않는다.
- scripted controller 자체를 candidate policy로 평가하지 않는다. MVP-2는
  dataset curation이 학습된 policy 결과를 개선했는지를 증명해야 한다.

## 확정 결정

### Proof path

`A3 Hybrid staged path`를 사용한다.

```text
기존 Isaac task
-> runtime smoke / sanity check only

전용 Isaac connector insertion evaluator
-> MVP-2 Closed proof attempt
```

### Evaluator scene

MVP-2 proof용 evaluator는 전용 Isaac 물리 기반 고정 connector insertion scene으로
한다.

- 기존 `Isaac-Forge-PegInsert-Direct-v0`는 smoke / regression sanity로 유지한다.
- MVP-2 Closed claim은 전용 scene 결과에서만 시도한다.
- 전용 scene의 성공 기준, seed split, offset, noise level은 baseline/candidate
  평가 전에 고정한다.

### Success metric

성공 기준은 `기하 + 안정성`이다.

한 rollout은 아래 조건을 모두 만족해야 성공이다.

- `insertion_depth_m >= 0.030`
- `lateral_error_m <= 0.006`
- `orientation_error_deg <= 8.0`
- 위 세 조건이 연속 `10` simulation steps 동안 유지된다.
- `max_steps=150` 안에 조건을 만족한다.

이 값은 MVP-2B initial evaluator 기준이다. 구현 중 Isaac scale이나 scene
geometry가 다르더라도 threshold를 held-out 결과를 본 뒤 변경하지 않는다. 필요한
경우에는 새 `scenario_manifest` version을 만들고 기존 run과 분리한다.

### Scenario split

`scenario_manifest.json`을 먼저 pre-register한다.

Split은 `seed + initial offset + noise level` 기반이다.

Initial MVP-2B manifest:

```text
train_success seeds: 1000-1039
train_failure seeds: 1100-1139
calibration seeds: 2000-2009
held_out seeds: 3000-3019
```

각 scenario는 아래 필드를 가진다.

```json
{
  "scenario_id": "heldout_3000",
  "split": "held_out",
  "seed": 3000,
  "initial_offset_m": [0.002, -0.004, 0.000],
  "orientation_offset_deg": 3.0,
  "noise_level": "medium",
  "max_steps": 150
}
```

`held_out` scenario는 다음에 사용하지 않는다.

- scripted expert parameter tuning
- controlled failure/noise tuning
- curation rule tuning
- policy hyperparameter selection
- evaluator threshold tuning

최종 proof claim은 held-out split에서만 산출한다.

### Training data strategy

학습 데이터는 Isaac evaluator domain에서 직접 raw trajectories를 생성한다.

Primary generation:

```text
scripted expert + controlled noise/failure
```

Operator demo:

```text
secondary visual / UX validation evidence only
not MVP-2 closure gate
```

### Controlled failure taxonomy

Raw train material은 성공 trajectory와 실패/저품질 trajectory를 모두 포함한다.
Failure/noise는 아래 taxonomy로 사전에 고정한다.

- `LATERAL_OFFSET_FAILURE`: lateral offset이 success threshold 밖으로 벗어난다.
- `UNDER_INSERTION_FAILURE`: insertion depth가 부족하다.
- `ORIENTATION_MISALIGNMENT_FAILURE`: orientation error가 threshold를 넘는다.
- `ACTION_JITTER_FAILURE`: action jitter가 stability condition을 깨뜨린다.
- `EARLY_STOP_FAILURE`: 성공 조건 유지 전에 trajectory가 종료된다.

Baseline / candidate 차이는 데이터 curation 여부뿐이다.

- Baseline train view: accepted + rejected/noisy raw trajectories가 섞인
  uncurated dataset.
- Candidate train view: 동일 raw source에서 ForgeXR curation gate를 통과한
  accepted dataset.

### Policy / trainer

Policy / trainer는 NumPy 기반 phase-conditioned BC로 고정한다.

```text
policy_class=phase_conditioned_numpy_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_bc_trainer_v0
```

Fair A/B 원칙:

- baseline과 candidate 모두 phase input을 동일하게 사용한다.
- baseline과 candidate 모두 같은 feature schema를 사용한다.
- baseline과 candidate 모두 같은 trainer code와 hyperparameter를 사용한다.
- baseline과 candidate 모두 같은 held-out scenario set에서 평가한다.
- 유일한 차이는 train dataset view다.

Feature schema:

- phase one-hot: `APPROACH`, `CONTACT`, `INSERT`, `SEAT`
- task geometry: EEF position, connector target position, lateral error,
  insertion depth estimate, orientation error estimate
- robot state: action history summary and current normalized action context

### Closure threshold

MVP-2 Closed initial threshold는 실용적 효과 크기 기준이다.

MVP-2 Closed requires:

- `candidate_success_rate > baseline_success_rate`
- `curated_vs_uncurated_uplift >= 0.20`
- at least `20` held-out rollouts per policy
- existing proof evaluator reports `learning_proven=true`
- existing proof evaluator reports `proof_eligible=true`
- `runtime_backend=isaac_runtime`
- `proof_runtime=dedicated_isaac_connector_insertion_evaluator`
- evidence tier is proof-grade external held-out evaluation, not proxy/smoke

Deterministic, skipped, proxy, smoke, HMD, and visual-only evidence are not
closure evidence. They must never set top-level `mvp2_closed=true` or
`proof_eligible=true`, even when they produce proof-shaped JSON or positive
synthetic uplift.

Bootstrap confidence interval은 report에 남기되, initial MVP-2 Closed blocker로
사용하지 않는다. 성공 후 강화 단계에서 `bootstrap CI lower bound > 0` 기준을
추가한다.

## 시스템 흐름

```text
pre-register scenario_manifest
-> generate Isaac raw trajectories from scripted expert + controlled failures
-> emit normalized trajectory contract
-> replay/action gate
-> data-quality gate
-> curation gate
-> export baseline_uncurated and candidate_curated HDF5
-> train baseline/candidate NumPy phase-conditioned BC with identical setup
-> run held-out Isaac evaluator
-> write rollout videos / CSV / external rollout JSON
-> run_mvp2_learning_proven_policy_eval.py
-> MVP-2 Closed only if existing validator passes threshold
```

## Artifact contract

Default output root:

```text
storage/mvp2b_isaac_proof_evaluator/
```

Required artifacts:

- `scenario_manifest.json`
- `train_raw_trajectories/`
- `curation_manifest.json`
- `baseline_uncurated_train.hdf5`
- `candidate_curated_train.hdf5`
- `baseline_policy_artifact.json`
- `candidate_policy_artifact.json`
- `heldout_rollouts/baseline_rollouts.csv`
- `heldout_rollouts/candidate_rollouts.csv`
- `heldout_rollouts/baseline_external_rollouts.json`
- `heldout_rollouts/candidate_external_rollouts.json`
- `visual_evidence/baseline_representative_rollout.*`
- `visual_evidence/candidate_representative_rollout.*`
- `mvp2_learning_proven_report.json`
- `mvp2b_isaac_proof_evaluator_report.json`

The external rollout JSON must include:

- `source_kind=external_heldout_policy_eval`
- `proof_role=external_trainer_policy_eval`
- `policy_class=phase_conditioned_numpy_bc_policy_v0`
- `trainer=rdf_numpy_phase_conditioned_bc_trainer_v0`
- `heldout_suite.source_kind=external_trainer_eval_suite`
- `heldout_suite.proof_role=external_policy_eval_suite`
- rollout rows with scenario id, seed, success, failure reason, steps, and metric
  summary

## Visual evidence

Visual evidence should come from the actual Isaac evaluator run, not AI-generated
imagery.

Initial visual evidence set:

- one representative baseline failure or partial-success rollout
- one representative candidate success rollout if present
- one side-by-side metric trace plot generated from rollout state logs

Visual evidence is explanatory. It does not override the JSON proof gate.

## Roadmap

### Stage 0: Current UR bridge sanity

Use current MVP-1+ UR source logs only to verify contract continuity and the
phase-conditioned bridge shape. This is not the MVP-2 Closed proof.

### Stage 1: Dedicated evaluator preflight

Create the dedicated Isaac connector insertion scene and verify:

- deterministic reset by scenario seed
- metric extraction
- visual capture path
- JSON/CSV rollout logging

### Stage 2: Isaac domain raw data generation

Generate train raw trajectories using scripted expert and controlled
failure/noise taxonomy. Emit the same normalized contract and pass existing data
trust gates.

### Stage 3: Baseline/candidate training

Train two NumPy phase-conditioned BC policies with identical trainer setup.

### Stage 4: Held-out evaluation

Run at least 20 held-out rollouts per policy from the pre-registered
`held_out` split.

### Stage 5: Proof ingest

Feed external rollout JSON into `run_mvp2_learning_proven_policy_eval.py`. The
existing validator remains the closure authority.

### Stage 6: Reporting

Update buyer-facing and developer-facing reports with:

- scenario manifest summary
- policy/trainer parity
- success metric summary
- accepted/rejected funnel
- baseline/candidate success rates
- visual evidence paths
- limitations and non-claims

## Stop rules

Stop and report if:

- positive uplift requires changing success thresholds after seeing held-out
  results
- validator guards must be weakened
- held-out scenarios leak into training or curation tuning
- Isaac runtime requires HMD/OpenXR as primary path
- physical robot runtime becomes required
- a DB migration or new production dependency becomes necessary
- visual evidence and JSON proof disagree

## Implementation follow-up

After this design is approved, create a new implementation plan that supersedes
the preliminary `docs/superpowers/plans/2026-06-10-mvp2b-proof-grade-evaluator-bridge.md`.
The new plan should focus on the dedicated Isaac evaluator, pre-registered
scenario manifest, Isaac-domain trajectory generation, NumPy phase-conditioned
BC trainer, held-out rollout capture, and proof ingest.
