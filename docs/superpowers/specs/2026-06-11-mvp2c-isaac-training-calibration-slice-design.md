# MVP-2C Isaac Training / Calibration Slice Design

Date: 2026-06-11

## 목적

MVP-2C의 목적은 MVP-2B actual Isaac runtime proof attempt가 실패한 뒤, 같은
held-out 결과를 보고 threshold나 action scale을 사후 조정하지 않고, 새로
pre-register된 training / calibration / held-out slice로 MVP-2 Closed를 다시
시도할 수 있는 정직한 proof path를 만드는 것이다.

MVP-2C는 아래 claim만 허용한다.

```text
새 scenario_manifest version에서,
held-out과 분리된 train/calibration split만 사용해
Isaac-runtime scripted expert train data와 action adapter를 고정한 뒤,
fresh held-out Isaac scenarios에서 curated dataset candidate policy가
uncurated baseline policy보다 practical effect size 이상으로 더 잘 수행했다.
```

## 배경

MVP-2B에서 실제 Isaac runtime path는 구현되고 검증됐다.

```text
runtime_backend=isaac_runtime
proof_runtime=dedicated_isaac_connector_insertion_evaluator
runtime_gate.passed=true
actual_rollouts_per_policy=20
```

하지만 actual held-out result는 non-closing이었다.

```text
baseline_success_rate=0.0
candidate_success_rate=0.0
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
```

Trace diagnosis:

```text
baseline:
  20 rollouts, 0 success
  all UNDER_INSERTION_FAILURE

candidate:
  20 rollouts, 0 success
  LATERAL_OFFSET_FAILURE=10
  ORIENTATION_MISALIGNMENT_FAILURE=7
  STABILITY_WINDOW_NOT_REACHED=3
  max_depth can reach 0.034m, but no stable 10-step seating window is achieved
```

이 결과는 중요한 engineering signal이다.

- Isaac runtime evaluator는 실제로 동작한다.
- 현재 policy / action adapter는 stable seating을 만들지 못한다.
- candidate가 depth를 만들 수는 있지만 lateral/orientation/stability를 동시에
  유지하지 못한다.
- 기존 held-out 결과를 본 뒤 threshold, success metric, action scale,
  hyperparameter를 바꿔 같은 manifest에서 close하면 proof integrity가 깨진다.

## 비목표

MVP-2C는 다음을 하지 않는다.

- 기존 MVP-2B held-out seeds `3000-3019`를 calibration, tuning, closure proof에
  재사용하지 않는다.
- success threshold를 낮추지 않는다.
- stable step requirement를 낮추지 않는다.
- held-out 결과를 본 뒤 baseline uncurated view의 failure/noise 비율을 바꾸지
  않는다.
- deterministic backend, local proxy, schema fixture, template, smoke-only result를
  MVP-2 closure evidence로 승격하지 않는다.
- scripted expert controller 자체를 candidate policy로 평가하지 않는다.
- VLA fine-tuning, World Model training, RL, marketplace, worker UX, HMD Gate A,
  real robot control을 구현하지 않는다.
- HMD/OpenXR readiness, physical robot readiness, real robot success를 주장하지
  않는다.

## Proof Integrity 원칙

### 새 manifest version

MVP-2C는 새 manifest version을 사용한다.

```text
manifest_version=rdf_mvp2c_scenario_manifest_v0.1.0
```

MVP-2B held-out seeds는 historical non-closing evidence로만 남긴다. MVP-2C의
train, calibration, held-out split에는 사용하지 않는다.

### Pre-registered split

MVP-2C initial split:

```text
train_success seeds: 4000-4079
train_failure seeds: 4100-4179
calibration seeds: 5000-5019
held_out seeds: 6000-6019
```

Split axis:

```text
seed + initial_offset_m + orientation_offset_deg + noise_profile
```

`held_out` split은 다음에 사용하지 않는다.

- scripted expert parameter tuning
- controlled failure/noise tuning
- curation rule tuning
- policy hyperparameter selection
- action adapter selection
- evaluator threshold tuning

### Fixed success metric

MVP-2C는 MVP-2B의 geometry + stability success metric을 유지한다.

```text
insertion_depth_m >= 0.030
lateral_error_m <= 0.006
orientation_error_deg <= 8.0
stable_steps_required = 10
max_steps = 150
```

이 값은 MVP-2C manifest에 기록하고 hash에 포함한다.

## 설계 요약

MVP-2C는 MVP-2B runner를 무작정 튜닝하지 않고, 다음 네 경계를 명확히 추가한다.

1. `Mvp2cScenarioManifest`
   - 새 train/calibration/held-out split을 pre-register한다.
   - 이전 MVP-2B held-out seeds와 겹치면 실패한다.

2. `IsaacRuntimeScriptedExpertDataGenerator`
   - Isaac runtime에서 train split trajectory를 직접 생성한다.
   - expert는 dataset generation용이며 held-out policy로 평가하지 않는다.
   - accepted와 controlled failure raw trajectories를 모두 저장한다.
   - scripted expert와 controlled failure generator config는 hash-stable artifact로
     저장한다.

3. `ActionAdapterCandidateRegistry`
   - normalized policy action을 Isaac env action으로 변환하는 후보들을 사전에
     선언한다.
   - 후보 목록과 parameter는 calibration 전에 hash로 고정한다.

4. `CalibrationOnlyActionAdapterSelector`
   - calibration split에서만 adapter를 선택한다.
   - held-out rollout JSON이나 held-out trace path를 읽으면 실패한다.
   - 선택된 adapter artifact는 held-out evaluation 전에 freeze한다.

## Data Flow

```text
build MVP-2C scenario_manifest
-> generate train split Isaac runtime scripted expert trajectories
-> emit normalized trajectory contracts
-> run replay/action/data-quality/curation gates
-> export baseline_uncurated HDF5 and candidate_curated HDF5
-> train baseline/candidate NumPy phase-conditioned BC with identical setup
-> run calibration split across predeclared action adapters
-> freeze selected action_adapter_artifact
-> run fresh held-out Isaac evaluator with selected adapter
-> write baseline/candidate external rollout JSON
-> run existing MVP-2 learning-proven validator
-> set MVP-2 Closed only if runtime + validator + uplift gates pass
```

## Scripted Expert Training Data

### 역할

Scripted expert는 train material generator다. It is not the evaluated policy.

Scripted expert는 Isaac runtime state에서 아래 값을 읽는다.

- `held_pos`
- `fixed_pos`
- `held_quat`
- phase estimate
- previous action

각 step은 normalized trajectory contract와 HDF5 train view에 들어갈 수 있도록
아래 metadata를 기록한다.

- `phase`
- `insertion_depth_m`
- `relative_x_m`
- `relative_y_m`
- `lateral_error_m`
- `orientation_error_deg`
- `normalized_action`
- `action_adapter_id`
- `runtime_backend=isaac_runtime`
- `proof_runtime=dedicated_isaac_connector_insertion_evaluator`

### Generator config hash

Train data generation config는 training, calibration, held-out evaluation 전에
hash-stable artifact로 고정한다.

Required fields:

- `scripted_expert_config_sha256`
- `controlled_failure_config_sha256`
- `train_generation_config_sha256`

이 값들은 top-level report, curation manifest, train view metadata,
normalized trajectory contract source provenance에 포함한다.

Implementation must fail if:

- `scripted_expert_config_sha256` changes after train data generation starts
- `controlled_failure_config_sha256` changes after train data generation starts
- `train_generation_config_sha256` changes after calibration starts
- any generation config changes after held-out evaluation starts

### Accepted trajectory

Accepted train trajectory는 geometry + stability success metric을 만족해야 한다.
단, train split에서의 success는 MVP-2 Closed evidence가 아니다. 이것은 학습용
curated material evidence다.

### Controlled failure trajectory

Failure taxonomy는 MVP-2B와 호환되게 유지한다.

- `LATERAL_OFFSET_FAILURE`
- `UNDER_INSERTION_FAILURE`
- `ORIENTATION_MISALIGNMENT_FAILURE`
- `ACTION_JITTER_FAILURE`
- `EARLY_STOP_FAILURE`

Baseline train view는 accepted + rejected/noisy material을 포함한다.

Candidate train view는 curation gate를 통과한 accepted material만 포함한다.

## Baseline Uncurated Mix Pre-registration

Baseline uncurated는 “고의로 망가진 dataset”처럼 보여서는 안 된다. Baseline은
curation 전 raw material을 대표하되, failure/noisy material이 과도하게 많아지는
것을 막기 위해 mix ratio를 사전에 고정한다.

MVP-2C initial baseline mix:

```json
{
  "baseline_noise_mix_ratio": 0.25,
  "accepted_failure_ratio": {
    "accepted": 3,
    "failure_or_noisy": 1
  },
  "failure_type_distribution": {
    "LATERAL_OFFSET_FAILURE": 0.20,
    "UNDER_INSERTION_FAILURE": 0.20,
    "ORIENTATION_MISALIGNMENT_FAILURE": 0.20,
    "ACTION_JITTER_FAILURE": 0.20,
    "EARLY_STOP_FAILURE": 0.20
  }
}
```

Required baseline mix artifact fields:

- `baseline_noise_mix_ratio`
- `accepted_failure_ratio`
- `failure_type_distribution`
- `noise_profile_config_sha256`

Rules:

- Baseline train view samples from accepted and failure/noisy raw material using
  the fixed pre-registered mix above.
- Candidate train view uses only accepted material that passed curation.
- The mix ratio must be fixed before training, calibration, and held-out
  evaluation.
- The mix ratio must not be changed after seeing calibration or held-out
  performance.
- `failure_type_distribution` must sum to `1.0`.
- `noise_profile_config_sha256` must be included in the top-level report and
  train view metadata.
- If baseline material cannot satisfy the fixed mix, the run must fail rather
  than silently resampling a different baseline.

## Action Adapter 후보

MVP-2C initial candidate registry는 세 후보로 고정한다.

### `isaac_delta_pose_direct_v0`

```text
normalized_action[0:6] -> Isaac action[0:6]
gripper ignored or mapped only if env supports it
clip to [-1, 1]
```

장점:

- MVP-2B와 가장 가까운 baseline adapter다.
- 회귀 비교가 쉽다.

위험:

- z / orientation semantics mismatch가 그대로 남을 수 있다.

### `isaac_signed_xy_downward_servo_v0`

```text
dx = xy_gain * normalized_action_dx
dy = xy_gain * normalized_action_dy
dz = z_gain * normalized_action_dz
rotation = orientation_gain * normalized_action_rotation
clip to [-1, 1]
```

장점:

- MVP-2B trace에서 드러난 signed lateral correction과 under-insertion 문제를
  직접 다룬다.
- phase-conditioned BC feature schema와 잘 맞는다.

위험:

- calibration split에서 gain이 과하게 선택되면 action saturation이 커질 수 있다.

### `isaac_stability_damped_servo_v0`

```text
adapter_action = damping * previous_env_action + (1 - damping) * current_policy_action
seat phase에서 dz와 rotation을 낮추고 xy correction을 유지
clip to [-1, 1]
```

장점:

- candidate가 max depth에 도달한 뒤 stable window를 놓친 문제를 겨냥한다.
- action jitter를 줄일 수 있다.

위험:

- 과도한 damping은 insertion progress를 늦춰 under-insertion을 만들 수 있다.

## Calibration Selection

Calibration은 held-out이 아니다. MVP-2C는 calibration split에서 adapter를 선택할 수
있지만, 이 선택 규칙은 held-out 전에 고정해야 한다.

Selection score:

```text
selector_score =
  1.00 * (candidate_calibration_success_rate - baseline_calibration_success_rate)
  + 0.25 * candidate_stability_margin
  - 0.10 * candidate_action_saturation_rate
```

Tie-break order:

1. higher candidate calibration success rate
2. higher candidate stability margin
3. lower candidate action saturation rate
4. deterministic lexical order of `adapter_id`

Required calibration report fields:

- `scenario_manifest_sha256`
- `action_adapter_registry_sha256`
- `selector_score_config_sha256`
- `selector_score_pre_registered=true`
- `calibration_scenario_ids`
- `heldout_scenario_ids_excluded=true`
- `heldout_excluded=true`
- `same_adapter_used_for_baseline_and_candidate=true`
- `selected_adapter_frozen_before_heldout=true`
- `selected_adapter_id`
- `selected_adapter_sha256`
- per-adapter baseline/candidate calibration success rates
- per-adapter action saturation rate
- leakage guard result

The selector must fail if any held-out scenario id, held-out trace path, or
held-out rollout JSON is used.

The selector must not read:

- held-out rollout JSON
- held-out trace paths
- held-out scenario ids except for exclusion checks
- held-out success metrics

If selector score uses candidate-baseline calibration uplift, the scoring
formula and weights must be pre-registered in `selector_score_config_sha256`
before calibration begins. The same selected adapter must be used for both
baseline and candidate during held-out evaluation.

## Policy / Trainer

Policy class remains:

```text
phase_conditioned_numpy_bc_policy_v0
```

Trainer remains:

```text
rdf_numpy_phase_conditioned_bc_trainer_v0
```

Fairness invariants:

- baseline and candidate use identical feature schema
- baseline and candidate use identical phase input
- baseline and candidate use identical trainer code
- baseline and candidate use identical hyperparameters
- baseline and candidate use identical selected action adapter
- baseline and candidate run on identical held-out scenario ids
- only train dataset view differs

Feature schema must include signed geometry:

- phase one-hot: `APPROACH`, `CONTACT`, `INSERT`, `SEAT`
- `insertion_depth_m`
- `relative_x_m`
- `relative_y_m`
- `lateral_error_m`
- `orientation_error_deg`
- previous action summary

## Privileged Task-State Feature Non-Claim

MVP-2C policy input uses Isaac evaluator-domain task-state / geometry features:

- `insertion_depth_m`
- `relative_x_m`
- `relative_y_m`
- `lateral_error_m`
- `orientation_error_deg`
- `phase`

Therefore the report must explicitly state:

```text
This is an Isaac evaluator-domain learning proof using privileged task-state
features. It does not claim deployable real-world visual policy performance.
```

Required non-claims:

- `deployable_real_robot_policy=false`
- `visual_policy_performance=false`
- `real_robot_success=false`
- `physical_robot_readiness=false`
- `universal_robot_support=false`

## Artifact Contract

Default output root:

```text
storage/mvp2c_isaac_training_calibration/
```

Required artifacts:

```text
scenario_manifest.json
action_adapter_candidates.json
action_adapter_registry_hash.json
baseline_noise_mix_config.json
generator_config_hashes.json
calibration_selection_report.json
selected_action_adapter.json
train_raw_trajectories/
normalized_trajectory_contracts/
curation_manifest.json
baseline_uncurated_train.hdf5
candidate_curated_train.hdf5
baseline_policy_artifact.json
candidate_policy_artifact.json
calibration_rollout_traces/
heldout_rollout_traces/
external_rollouts/baseline_external_rollouts.json
external_rollouts/candidate_external_rollouts.json
mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
mvp2c_isaac_training_calibration_report.json
visual_evidence/metric_trace_comparison.png
```

Top-level report required fields:

- `schema_version`
- `manifest_version`
- `scenario_manifest_sha256`
- `scripted_expert_config_sha256`
- `controlled_failure_config_sha256`
- `train_generation_config_sha256`
- `baseline_noise_mix_ratio`
- `accepted_failure_ratio`
- `failure_type_distribution`
- `noise_profile_config_sha256`
- `runtime_backend`
- `proof_runtime`
- `runtime_gate`
- `selector_score_config_sha256`
- `selected_action_adapter_id`
- `selected_action_adapter_sha256`
- `selector_score_pre_registered`
- `same_adapter_used_for_baseline_and_candidate`
- `heldout_excluded`
- `selected_adapter_frozen_before_heldout`
- `calibration_only_selection_passed`
- `heldout_leakage_guard_passed`
- `actual_rollouts_per_policy`
- `baseline_success_rate`
- `candidate_success_rate`
- `curated_vs_uncurated_uplift`
- `mvp2c_close_minimum_passed`
- `stronger_public_evidence_target_passed`
- `confidence_interval_report`
- `mvp2_closed`
- `proof_eligible`
- `blockers`
- `non_claims`
- `limitations`
- `reproducible_command`

## MVP-2 Closure Rule

MVP-2C can set `mvp2_closed=true` only when all conditions are true.

```text
runtime_backend == isaac_runtime
proof_runtime == dedicated_isaac_connector_insertion_evaluator
runtime_gate.passed == true
calibration_only_selection_passed == true
heldout_leakage_guard_passed == true
actual_rollouts_per_policy >= 20
existing_mvp2_validator.learning_proven == true
existing_mvp2_validator.proof_eligible == true
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
```

The top-level report must expose this as:

```text
mvp2c_close_minimum_passed=true|false
```

MVP-2C must keep `mvp2_closed=false` when:

- Isaac runtime is skipped
- deterministic backend is used
- local proxy is used
- calibration split is missing
- selected adapter is not frozen before held-out
- held-out leakage is detected
- rollout count is below 20 per policy
- candidate success rate is not greater than baseline
- uplift is below 0.20

## Stronger Public Evidence Target

MVP-2C engineering closure minimum is not the same as robust public benchmark
evidence. A 20-rollout result may close the engineering proof, but it must be
labeled as minimum evidence.

Close minimum:

- `actual_rollouts_per_policy >= 20`
- `candidate_success_rate > baseline_success_rate`
- `curated_vs_uncurated_uplift >= 0.20`

Stronger public / investor-facing evidence target:

- `actual_rollouts_per_policy >= 50` per policy preferred
- binomial confidence interval or bootstrap confidence interval reported
- report distinguishes `mvp2c_close_minimum_passed` from
  `stronger_public_evidence_target_passed`

Rules:

- `mvp2_closed=true` may be set when close minimum passes.
- `stronger_public_evidence_target_passed=false` must not block engineering
  closure.
- Buyer/investor-facing summaries must say “minimum engineering proof” when
  rollout count is below 50 per policy.
- Public benchmark language is allowed only when
  `stronger_public_evidence_target_passed=true`.

## Tests

Required focused tests:

- scenario manifest uses `rdf_mvp2c_scenario_manifest_v0.1.0`
- MVP-2B held-out seeds `3000-3019` do not appear in MVP-2C split
- train/calibration/held-out scenario ids are disjoint
- held-out leakage guard rejects held-out scenario ids in training,
  calibration, adapter selection, threshold tuning, or hyperparameter selection
- action adapter registry is predeclared and hash-stable
- baseline uncurated view uses pre-registered `baseline_noise_mix_ratio`,
  `accepted_failure_ratio`, `failure_type_distribution`, and
  `noise_profile_config_sha256`
- scripted expert, controlled failure, and train generation config hashes are
  written and included in top-level proof artifacts
- generation config mutation after calibration or held-out start fails
- selected adapter artifact is written before held-out evaluation
- selector score config is pre-registered and hash-stable
- selector report includes anti-p-hacking fields:
  `selector_score_pre_registered=true`,
  `same_adapter_used_for_baseline_and_candidate=true`, `heldout_excluded=true`,
  and `selected_adapter_frozen_before_heldout=true`
- calibration selector fails if it reads held-out trace or rollout JSON
- baseline/candidate policies share feature schema, trainer, hyperparameters,
  selected adapter, and held-out suite
- generated train trajectories pass `NormalizedTrajectoryContractValidator`
- baseline train HDF5 includes rejected material
- candidate train HDF5 excludes rejected material
- deterministic/skipped backend remains non-closing
- actual Isaac runtime report remains non-closing unless existing validator and
  runtime gate both pass
- report distinguishes `mvp2c_close_minimum_passed` from
  `stronger_public_evidence_target_passed`
- report includes privileged task-state feature non-claim fields
- top-level report preserves HMD/OpenXR non-claims

Required verification commands after implementation:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q

uv run pytest \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py \
  apps/api/tests/test_mvp1_proof_audit_script.py \
  -q

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --clean \
  --skip-isaac \
  --pretty

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --clean \
  --use-deterministic-eval-backend \
  --pretty

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --pretty

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

## Stop Conditions

Stop and report if any condition occurs.

- Isaac runtime cannot run locally.
- Implementing the slice requires live ROS2/DDS, real robot control, HMD
  collection, marketplace, or production auth.
- Existing normalized trajectory validator must be weakened.
- Existing MVP-2 learning-proven validator must be weakened.
- Success thresholds must be lowered to get a pass.
- Baseline noise/failure mix must be changed after training, calibration, or
  held-out evaluation starts.
- Train generation config hashes change after calibration or held-out
  evaluation starts.
- Held-out scenarios are needed for calibration or adapter selection.
- Calibration selector needs held-out success metrics or held-out trace content.
- Candidate does not beat baseline on fresh held-out scenarios.
- Action adapter selection cannot be separated from held-out evidence.
- The run produces visual evidence but no proof-grade rollout JSON.

## Definition of Done

MVP-2C implementation is complete when:

- The new MVP-2C manifest is pre-registered and hash-stable.
- Isaac-runtime scripted expert train data is generated for train split.
- Accepted and controlled-failure trajectories are stored and curated.
- Baseline noise/failure mix is pre-registered and hash-stable.
- Scripted expert, controlled failure, train generation, and noise profile
  configs are hash-stable and included in proof artifacts.
- Baseline uncurated and candidate curated HDF5 train views are exported.
- Baseline/candidate policies are trained with identical fair A/B setup.
- Action adapter candidates are predeclared and hash-stable.
- Calibration-only adapter selection is complete and held-out leakage-free.
- Calibration anti-p-hacking fields are present and true.
- Fresh held-out Isaac rollouts are generated through the selected adapter.
- Existing MVP-2 validator ingests the external rollout JSON.
- Top-level report either honestly closes MVP-2 or records non-closing blockers.
- Top-level report distinguishes minimum engineering closure from stronger
  public evidence target.
- Top-level report states privileged task-state feature non-claims.
- Docs and handoff are updated with commands, artifacts, and interpretation.

## Recommended Implementation Plan Shape

Use `$ralplan` and `$ultragoal` before implementation.

Recommended task sequence:

1. Add RED tests for MVP-2C manifest, seed separation, and leakage guard.
2. Add baseline noise mix and generator config hash tests.
3. Add action adapter registry and hash-stability tests.
4. Add calibration-only selector tests that reject held-out access.
5. Implement MVP-2C manifest and adapter registry.
6. Implement Isaac-runtime scripted expert train data generation.
7. Reuse or factor MVP-2B HDF5, policy, rollout JSON, and visual evidence
   helpers where this reduces duplication without weakening boundaries.
8. Implement calibration adapter selection and selected adapter freeze artifact.
9. Implement close-minimum vs stronger-public-evidence reporting.
10. Implement privileged task-state non-claims.
11. Implement fresh held-out evaluation through the selected adapter.
12. Run deterministic non-closing checks.
13. Run actual Isaac runtime proof attempt.
14. Update worklog, debugging guide, todo, and handoff.

## Open Boundary

This spec does not assume that MVP-2C will close MVP-2. It creates the next
proof-valid attempt. If the fresh held-out result is still non-positive, the
correct outcome is another non-closing proof report, not threshold relaxation.
