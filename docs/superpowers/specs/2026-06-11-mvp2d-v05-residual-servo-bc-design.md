# MVP-2D v0.5 Residual Servo BC Proof Slice Design

Date: 2026-06-11

## 목적

MVP-2D `v0_5`의 목적은 oracle repair 이후에도 남아 있는 MVP-2 Closed blocker,
즉 actual Isaac held-out에서 curated candidate가 uncurated baseline을 이기지 못한
문제를 fresh proof slice로 다시 검증하는 것이다.

`v0_5`에서 허용되는 claim은 하나다.

```text
같은 trainer, 같은 hyperparameter, 같은 trajectory count 조건에서,
accepted actual Isaac success traces로 구성된 curated candidate view가
accepted + rejected/noisy raw material로 구성된 uncurated baseline view보다
fresh held-out Isaac scenarios에서 practical effect size 이상으로 더 잘 수행했다.
```

이 spec은 proof integrity를 우선한다. `v0_5`는 closed를 쉽게 만들기 위한
held-out tuning slice가 아니라, fresh held-out을 보기 전에 dataset view, trainer,
calibration selector, seed split, stop rule을 모두 고정하는 proof slice다.

## 배경

MVP-2D oracle repair는 성공했다.

```text
/tmp/rdf-mvp2d-factory-oracle-repair.json
scripted_oracle_passed=true
policy_loop_viability=true
selected_success_evaluator=rdf_peg_in_hole
effective_steps=145
horizon_limited=true
success_step=4
```

이 결과는 이전 root cause가 stale target과 horizon reset이었다는 진단을 지지한다.
실제 Isaac train-generation도 success traces를 만들 수 있게 됐다.

그러나 `v0_3`, `v0_4` held-out proof attempts는 non-closing이었다.

```text
v0_3:
  train_generation_success=3
  actual_rollouts_per_policy=20
  baseline_success_rate=0.15
  candidate_success_rate=0.15
  curated_vs_uncurated_uplift=0.0
  mvp2_closed=false

v0_4:
  train_generation_success=5
  actual_rollouts_per_policy=20
  baseline_success_rate=0.15
  candidate_success_rate=0.15
  curated_vs_uncurated_uplift=0.0
  mvp2_closed=false
```

해석:

- oracle repair는 더 이상 active blocker가 아니다.
- actual Isaac train-generation gate는 통과 가능한 상태가 됐다.
- 현재 candidate trainer / adapter path는 continuous diagnostic을 조금 개선할 수는
  있지만 held-out success count를 baseline보다 높이지 못한다.
- 따라서 `v0_5`의 핵심 변화는 candidate policy/trainer path가 curated accepted
  traces를 실제로 활용할 수 있게 만드는 것이다.

## 비목표

`v0_5`는 다음을 하지 않는다.

- `v0_3` 또는 `v0_4` held-out 결과를 보고 threshold, action scale, baseline mix,
  selector score, hyperparameter를 사후 조정하지 않는다.
- burned held-out seed ranges를 proof closure에 재사용하지 않는다.
- baseline을 고의로 망가진 dataset으로 만들지 않는다.
- candidate-only stronger trainer를 허용하지 않는다.
- candidate-only adapter selection을 허용하지 않는다.
- near-success traces, oracle relabeling, synthetic correction labels를 candidate
  accepted evidence로 승격하지 않는다.
- scripted expert controller 자체를 evaluated policy로 쓰지 않는다.
- deterministic backend, proxy result, schema fixture, smoke-only result를
  MVP-2 closure evidence로 승격하지 않는다.
- VLA fine-tuning, World Model training, RL, real robot control, HMD Gate A,
  marketplace, worker UX를 구현하지 않는다.
- real robot success, deployable visual policy, physical robot readiness,
  universal robot support를 주장하지 않는다.

## Proof Integrity 원칙

### Fresh manifest

`v0_5`는 새 manifest version을 사용한다.

```text
manifest_version=rdf_mvp2d_scenario_manifest_v0.5.0
scenario_profile=v0_5
```

Burned ranges:

```text
3000-3019
6000-6019
9000-9019
12000-12019
15000-15019
```

Burned ranges는 historical diagnostic evidence로만 유지한다. `v0_5`의
training, calibration, held-out split에는 포함하지 않는다.

### Pre-registered split

`v0_5` split:

```text
train_success seeds: 16000-16159
train_failure seeds: 16200-16359
calibration seeds: 17000-17029
held_out seeds: 18000-18019
```

`held_out` split은 다음에 사용하지 않는다.

- train-generation controller tuning
- controlled failure/noise tuning
- curation rule tuning
- trainer family selection
- trainer hyperparameter selection
- residual servo gain/clip selection
- evaluator threshold tuning
- action adapter selection outside the pre-registered selector

### One-shot held-out rule

`v0_5` held-out A/B는 한 번만 실행한다. 실패하면 `v0_5`는 fail-closed된다.
같은 held-out range로 trainer, selector, metric, baseline mix, action scale을 다시
조정하지 않는다.

## Train-generation Gate

`v0_5`는 held-out을 실행하기 전에 actual Isaac train-generation gate를 먼저 닫아야
한다.

Train-generation rules:

- `train_success=16000-16159`를 pre-registered order로 실행한다.
- accepted actual Isaac success traces를 최소 20개 확보해야 한다.
- accepted success traces는 최대 40개까지만 candidate train view에 사용한다.
- 40개가 확보되면 train-generation은 stop할 수 있다.
- 160개 seed를 모두 실행했는데 success trace가 20개 미만이면 즉시 fail-closed한다.
- 이 경우 held-out A/B는 실행하지 않는다.

Top-level required evidence:

```text
actual_isaac_success_trace_count >= 20
actual_isaac_success_trace_cap <= 40
training_trajectory_source=isaac_runtime_scripted_expert_rollout
train_generation_runtime_gate.passed=true
```

## Dataset Views

### Candidate curated view

Candidate는 accepted actual Isaac success traces만 사용한다.

포함 가능:

- RDF `peg_in_hole` metric을 통과한 actual Isaac success trace
- train-generation gate가 accepted로 기록한 trace
- pre-registered success trace cap 안에 들어온 trace

포함 불가:

- near-success trace
- rejected/noisy trace
- oracle relabeled trace
- synthetic correction row
- held-out trace
- calibration trace

### Baseline uncurated view

Baseline은 candidate와 같은 trace count를 사용한다. Candidate가 accepted success
trace `N`개를 사용하면 baseline도 `N`개 trajectory를 학습한다.

Baseline mix는 pre-register한다.

```text
accepted_ratio=0.60
rejected_noisy_ratio=0.40
```

Baseline rejected/noisy failure taxonomy:

```text
lateral_offset
under_insertion
stability_window_loss
```

Baseline은 same raw train pool에서 구성한다. 즉 baseline은 다른 source에서 가져온
약한 fixture가 아니라, 같은 `v0_5` train-generation / controlled failure material의
uncurated view다.

### Data-size fairness

Baseline과 candidate는 trajectory count를 동일하게 맞춘다. Transition count는
trace length 차이에 따라 달라질 수 있지만, report는 다음 값을 명시해야 한다.

- `baseline_trace_count`
- `candidate_trace_count`
- `baseline_transition_count`
- `candidate_transition_count`
- `trace_count_equal=true`

## Trainer Design

`v0_5` trainer family는 `phase-conditioned residual servo BC`다.

공정성 규칙:

- baseline과 candidate는 같은 trainer implementation을 사용한다.
- baseline과 candidate는 같은 hyperparameter를 사용한다.
- baseline과 candidate는 같은 feature schema를 사용한다.
- baseline과 candidate는 같은 phase input을 사용한다.
- 차이는 dataset view뿐이다.

### Weak geometric base servo

모든 policy는 동일한 weak geometric base servo를 공유한다. Base servo는 방향성을
제공하지만 task success를 대신 만들 정도로 강하면 안 된다.

Base servo 역할:

- phase별 목표 방향 제공
- lateral / depth correction의 약한 prior 제공
- learned residual이 stability와 insertion correction을 담당할 수 있게 scaffold 제공

Base servo config는 calibration 전에 pre-register하고 hash에 포함한다.

### Residual target

Residual label은 actual accepted trace action에서 온다.

```text
residual_target = actual_trace_action - weak_base_servo_action
```

허용하지 않는 target:

- `oracle_live_target_action - weak_base_servo_action`
- 직접 생성한 task-state correction label
- held-out result를 보고 만든 relabel

이 경계는 `v0_5` claim을 oracle imitation이 아니라 curated data learning proof로
유지하기 위한 것이다.

## Calibration Selector

Calibration은 pre-registered residual servo gain/clip 후보 중 하나를 고르는 데만
사용한다.

Selector constraints:

- selector 후보 목록은 calibration 전에 hash-stable artifact로 고정한다.
- selector score는 `shared_stability_feasibility_score`다.
- selector는 candidate uplift를 직접 최적화하지 않는다.
- selected config는 baseline/candidate 모두 동일하게 사용한다.
- selected config는 held-out 전에 freeze한다.
- selector는 held-out rollout JSON, held-out trace paths, held-out success metrics를
  읽으면 실패한다.

`shared_stability_feasibility_score`는 아래 성격을 가져야 한다.

```text
둘 다 실행 가능한 공통 servo config를 고른다.
candidate에 유리한 adapter를 고르는 것이 아니다.
```

Report required fields:

- `selector_score_pre_registered=true`
- `same_adapter_used_for_baseline_and_candidate=true`
- `heldout_excluded=true`
- `selected_adapter_frozen_before_heldout=true`
- `selector_score_name=shared_stability_feasibility_score`

## Held-out Evaluation

Held-out split:

```text
held_out seeds: 18000-18019
rollouts_per_policy=20
```

Held-out uses:

- actual Isaac runtime
- RDF-compatible metric
- selected shared residual servo config
- baseline policy artifact
- candidate policy artifact

Held-out does not use:

- deterministic backend
- imported template result
- synthetic evaluator result
- held-out-driven retuning

## Close Gates

`v0_5` can close MVP-2 only when all gates pass.

Required gates:

```text
train_generation_runtime_gate.passed=true
actual_isaac_success_trace_count >= 20
actual_rollouts_per_policy >= 20
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
learning_validator.proof_eligible=true
learning_validator.evidence_tier=external_heldout_policy_eval
mvp2_closed=true
```

Engineering close minimum:

```text
actual_rollouts_per_policy >= 20
curated_vs_uncurated_uplift >= 0.20
```

Public evidence target remains separate:

```text
actual_rollouts_per_policy >= 50 per policy preferred
confidence interval reported
stronger_public_evidence_target_passed=true
```

A 20-rollout result can close the engineering proof but must not be described as
a robust public benchmark.

## Visual Evidence

`v0_5` creates lightweight visual evidence only.

Required plot artifacts:

- representative success rollout trace plot
- representative baseline failure rollout trace plot
- representative candidate failure or success rollout trace plot

Plot contents:

- lateral error over time
- insertion depth over time
- stability window indicator
- phase indicator
- success/failure reason

Isaac viewport screenshot/video is out of scope for this slice. It can be
generated later from successful artifacts for public-facing material.

## Reports and Artifacts

The runner must emit or update:

- `scenario_manifest.json`
- `generator_config_hashes.json`
- `baseline_noise_mix_config.json`
- `selected_action_adapter.json`
- `baseline_policy_artifact.json`
- `candidate_policy_artifact.json`
- `baseline_train_view.hdf5`
- `candidate_train_view.hdf5`
- baseline/candidate external held-out rollout JSON
- `mvp2_learning_proven_report.json`
- `mvp2c_isaac_training_calibration_report.json`
- representative trace plot files

Top-level report must include:

- `scenario_profile=v0_5`
- burned seed ranges
- train-generation success trace count
- success trace cap
- baseline/candidate trace counts
- baseline mix ratio
- failure taxonomy
- residual trainer metadata
- weak base servo config hash
- selected calibration config hash
- close gate status
- public evidence target status
- non-claims

## Non-claims

The report must preserve the existing MVP-2 non-claims.

```text
deployable_real_robot_policy=false
visual_policy_performance=false
real_robot_success=false
physical_robot_readiness=false
universal_robot_support=false
hmd_readiness=false
```

`v0_5` is an Isaac evaluator-domain learning proof using privileged task-state
features. It does not claim deployable real-world visual policy performance.

## Failure Handling

Fail-closed conditions:

- fewer than 20 accepted actual Isaac success traces from `train_success`
- held-out leakage detected
- baseline/candidate trainer or hyperparameter differs
- baseline/candidate trace count differs
- candidate includes near-success or relabeled synthetic evidence
- selector reads held-out artifacts
- deterministic/proxy backend is used for closure
- candidate success rate is not greater than baseline
- uplift is below `0.20`

If any fail-closed condition occurs, the runner must write a report explaining
the blocker and must not set `mvp2_closed=true`.

## Acceptance Criteria

`v0_5` implementation is complete when:

- `scenario_profile=v0_5` exists and burned ranges are excluded.
- Train-generation runs actual Isaac in pre-registered order.
- Accepted actual Isaac success trace count is gated at minimum 20 and maximum
  40.
- Baseline and candidate train views have equal trajectory count.
- Baseline uses accepted 60% / rejected-noisy 40% with the fixed three-failure
  taxonomy.
- Candidate uses accepted actual Isaac success traces only.
- Baseline and candidate use identical phase-conditioned residual servo BC
  trainer and hyperparameters.
- Calibration selector uses shared stability feasibility score only.
- Held-out A/B runs once on `18000-18019`.
- MVP-2 closes only if all close gates pass.
- If the proof does not close, the report remains fail-closed and preserves the
  burned held-out boundary.

## Spec Self-review

- Placeholder scan: no unresolved placeholder remains.
- Scope check: this spec covers one implementation slice, `v0_5`, and does not
  include marketplace, VLA, real robot, HMD readiness, or public benchmark work.
- Ambiguity check: seed ranges, trace caps, baseline mix, trainer fairness,
  residual target, calibration selector, held-out rule, and close gates are
  explicit.
- Proof integrity check: held-out is one-shot, burned ranges are excluded, and
  tuning after held-out is prohibited.
