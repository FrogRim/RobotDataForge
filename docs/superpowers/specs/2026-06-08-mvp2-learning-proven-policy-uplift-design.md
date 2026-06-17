# MVP-2 Learning-Proven Policy Uplift Design

Date: 2026-06-08

## 목적

MVP-2의 목적은 MVP-1/MVP-1+ data trust layer가 만든 curated dataset artifact가
downstream learning performance를 실제로 개선하는지 증명하는 것이다.

이번 설계에서 `MVP-2 Closed`는 다음 조건이 모두 참일 때만 인정한다.

```text
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift > 0
proof_eligible = true
learning_proven = true
```

동률 또는 negative 결과는 중요한 evidence로 보존하지만 `MVP-2 Closed`가 아니다.
그 경우 report는 `learning_proven=false`와 blocker summary를 남기고, 다음 data
iteration으로 이어진다.

## 현재 기준점

이미 완료된 slice:

```text
MVP-1 Closed
-> adapter-emitted normalized trajectory contract
-> buyer-facing data trust artifacts

MVP-1+ Closed
-> Franka / ROBOTIS SH5 ROS2-DDS / Universal Robots UR adapter proof
-> UR file-backed recorded-log lineage

MVP-2 Rebase first slice Closed
-> UR policy A/B harness readiness
-> baseline_uncurated / candidate_curated HDF5 exports
-> held-out suite manifest
-> schema-only rollout ingest contract
```

남은 gap:

```text
real measured rollout results
-> positive curated-vs-uncurated policy success uplift
-> learning-proven result report
```

## 선택한 접근: Approach C

Approach C는 local offline policy A/B runner와 external rollout ingest path를
동시에 보존한다.

```text
MVP-1+ UR file-backed lineage proof
-> baseline_uncurated dataset view
-> candidate_curated dataset view
-> local offline policy trainer/evaluator
-> held-out rollout result logs
-> rollout result adapter
-> real policy eval validator
-> mvp2_learning_proven_report.json
-> proof audit / buyer-facing summary
```

Local offline A/B가 positive uplift를 내면 `MVP-2 local proof Closed`로 인정한다.
External evaluator 또는 Isaac/physical rollout은 같은 ingest contract를 통해 더 강한
evidence tier로 확장한다.

## 범위

이번 MVP-2 Closed slice에 포함한다.

- `mvp2_*` primary entrypoint 추가.
- UR file-backed MVP-1+ artifact를 source lineage로 사용.
- baseline uncurated dataset view와 candidate curated dataset view를 같은 harness에서
  재사용.
- local offline policy trainer/evaluator 구현 또는 기존 deterministic proxy를
  MVP-2용으로 엄격하게 재정의.
- held-out suite에서 baseline/candidate rollout result를 생성.
- `run_mvp1c_rollout_result_adapter.py`와 `run_mvp1c_real_policy_eval.py`의 검증
  semantics를 재사용하되, 새 public artifact는 `mvp2_*` 이름으로 기록.
- positive uplift일 때만 `learning_proven=true`와 `proof_eligible=true`를 기록.
- negative 또는 동률일 때는 `learning_proven=false`와 bottleneck summary를 기록.
- buyer-facing report에 positive uplift 여부, evidence tier, limitations,
  reproducible command를 추가.

이번 slice에 포함하지 않는다.

- live UR/RTDE runtime.
- physical UR readiness.
- real robot success.
- HMD/OpenXR readiness 또는 Gate A collection.
- VLA fine-tuning.
- World Model training.
- marketplace, payment, worker UX.
- DB migration 또는 production auth.

## Success Criteria

MVP-2 Closed 조건:

- `scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty`
  실행이 exit 0.
- `storage/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json` 생성.
- report가 다음을 기록.
  - `learning_results_measured=true`
  - `learning_proven=true`
  - `proof_eligible=true`
  - `baseline_success_rate < candidate_success_rate`
  - `curated_vs_uncurated_uplift > 0`
  - `evidence_tier=local_offline_heldout_policy_eval`
  - UR file-backed lineage source와 harness report path
  - baseline/candidate train HDF5 path
  - held-out suite id와 rollout counts
  - limitations와 non-claims
- `mvp2_policy_eval_input.json`이 proof-grade held-out policy eval input으로
  검증된다.
- proof audit 또는 buyer-facing summary가 MVP-2 positive uplift를 읽을 수 있다.
- negative run은 report를 생성하지만 exit 0으로 `Closed`를 주장하지 않는다.

## Data Flow

```text
storage/mvp1plus_embodiment_proof/
  -> universal_robots_ur_industrial_arm normalized contract + lineage

storage/mvp2_policy_ab_harness/
  -> baseline_uncurated/baseline_uncurated_train.hdf5
  -> candidate_curated/candidate_curated_train.hdf5
  -> mvp2_heldout_suite_manifest.json
  -> mvp2_policy_eval_input_template.json

local offline policy A/B runner
  -> baseline_rollouts.json
  -> candidate_rollouts.json

rollout result adapter
  -> mvp2_policy_eval_input.json

real policy eval validator
  -> policy_uplift_real_eval_report.json

MVP-2 wrapper
  -> mvp2_learning_proven_report.json
```

## Components

### `run_mvp2_learning_proven_policy_eval.py`

Primary MVP-2 Closed entrypoint.

Responsibilities:

- Refresh or load `mvp2_policy_ab_harness_report.json`.
- Verify UR file-backed lineage and harness readiness.
- Train/evaluate local offline baseline and candidate policies.
- Write rollout result logs.
- Convert rollout logs into proof eval input.
- Run real policy eval validation.
- Build final `mvp2_learning_proven_report.json`.
- Return non-zero when required inputs are invalid.
- Return zero only when the evaluation ran and the result artifact was written.
  The report itself determines whether `learning_proven=true`.

### Local Offline Policy A/B Runner

The local runner must compare the same held-out scenarios with two policies.

- Baseline policy trains from `baseline_uncurated` view.
- Candidate policy trains from `candidate_curated` view.
- Both policies use the same held-out suite.
- Primary metric is `policy_success_rate`.
- Output is rollout logs, not a direct claim.

The first implementation may use a simple deterministic learner if it is
documented as `local_offline_heldout_policy_eval` and does not claim real robot
or Isaac success.

### Policy Eval Validator

Reuse the existing positive-uplift rule:

```text
passed = input schema and rollout minimums are valid
proof_eligible = passed and curated_vs_uncurated_uplift > 0
```

The wrapper must not weaken this validator.

### Buyer-Facing Summary

The summary must answer:

- What data source produced the training artifacts?
- Which robot embodiment and input lineage are used?
- What are baseline and candidate dataset views?
- What held-out suite was used?
- What were baseline and candidate success rates?
- Was the uplift positive?
- Is this local offline evidence, external evaluator evidence, Isaac evidence,
  or physical robot evidence?
- What claims are not made?

## Error Handling

Stop and report without claiming Closed if:

- MVP-1+ UR file-backed lineage is missing or hash validation fails.
- Harness readiness is false.
- Baseline or candidate HDF5 export is missing or empty.
- Held-out suite has no scenarios.
- Rollout result logs are missing, malformed, or below minimum rollout count.
- Candidate success rate is less than or equal to baseline success rate.
- Validator rules would need to be weakened to pass.

Negative uplift is not a crash. It is a measured non-close result.

## Tests

Add focused tests for:

- Positive local offline A/B result sets `learning_proven=true`.
- Negative local offline A/B result writes a report but keeps
  `learning_proven=false`.
- Equal success rates do not close MVP-2.
- Schema-only rollout fixture cannot be promoted to policy evidence.
- Missing or tampered UR lineage blocks the wrapper.
- Harness readiness false blocks the wrapper.
- Buyer-facing summary includes evidence tier, source lineage, rates, uplift,
  limitations, and reproducible command.
- Existing MVP-1 and MVP-1+ tests remain passing.

Minimum verification:

```text
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts apps/api/app apps/api/tests
git diff --check
```

## Claim Boundaries

If positive uplift passes, the allowed claim is:

```text
ForgeXR produced a local offline held-out policy A/B result where the curated
UR file-backed dataset view outperformed the uncurated baseline under the same
MVP-2 evaluation contract.
```

The following claims remain disallowed:

- Physical UR success.
- Real robot success.
- Live UR/RTDE support.
- HMD/OpenXR readiness.
- General policy transfer across robots.
- Marketplace readiness.
- VLA or World Model training success.

## Stop Condition

If the local offline policy A/B cannot produce positive curated > uncurated
uplift without weakening validators or fabricating evidence, the implementation
must stop with:

- measured baseline/candidate rates
- failure reason
- likely bottleneck
- recommended next data/trainer iteration

In that case MVP-2 remains open.
