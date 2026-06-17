# MVP-2E Harness-Gated Closure Design

Date: 2026-06-12

Status: pre-implementation design

## 목적

MVP-2E는 더 이상 `v0_7d`, `v0_7e` 같은 policy slice를 직접 반복하지 않는다.

현재 상태는 다음과 같다.

```text
MVP-2: Not Closed
v0_6i repair probe: green
fixed 40-run train-generation gate: passed, 28/40 env-native success
train dataset / policy artifacts: generated
v0_7c offline gates: passed
v0_7c actual Isaac Phase E: failed, 0/5
calibration: not opened
held-out 21000-21049: sealed
```

`v0_7c`의 실제 실패는 코드 실패가 아니라 proof gate의 정상 동작이다.
`v0_7c`는 learned residual z bypass를 막았지만, `ALIGN`에서
`base_servo_action[2] = -0.001`이 selected action adapter를 거쳐
`post_adapter_z = -0.032`가 되면서 stable centering 전에 하강이 발생했다.

따라서 다음 slice를 바로 만들지 않고, 먼저 MVP-2E closure를 막는 원인을
harness 체인으로 분리한다.

```text
harness-gated diagnosis
-> root-cause class 확정
-> downstream slice spec 생성
-> offline gate
-> actual Isaac Phase E final sanity
-> calibration
-> sealed held-out A/B
```

`v0_7d`는 이 spec 안에서 직접 구현 대상이 아니다. `v0_7d`는
closure-critical harness를 통과하거나, harness report가 특정 root cause class를
확정한 뒤 생성되는 downstream repair slice다.

## 비목표

이 spec은 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- calibration을 실행하지 않는다.
- env-native success authority, `stable_steps=10`, `max_steps=150`을 바꾸지 않는다.
- Phase E threshold `>=2/5`를 완화하지 않는다.
- `v0_7c` artifact를 성공 evidence로 소급 변경하지 않는다.
- policy uplift를 claim하지 않는다.
- real robot success, physical robot readiness, HMD/OpenXR readiness, visual policy performance를 claim하지 않는다.
- VLA fine-tuning, world model training, force-control runtime, live robot runtime을 구현하지 않는다.

## 연구 근거와 적용 범위

이 spec의 harness는 최신 imitation learning / robot policy evaluation 연구를
그대로 구현하려는 것이 아니다. MVP-2E의 현재 blocker에 필요한 failure class를
정의하기 위한 engineering gate로만 사용한다.

참고한 외부 근거:

- Robot Data Curation with Mutual Information Estimators, 2025:
  demonstration quality는 state diversity와 action predictability를 함께 봐야 하며,
  filtering이 RoboMimic과 실제 robot setup에서 성능을 개선할 수 있음을 보인다.
  https://arxiv.org/abs/2502.08623
- Is Your Imitation Learning Policy Better than Mine? Policy Comparison with
  Near-Optimal Stopping, 2025:
  imitation policy comparison은 10~50회 수준의 작은 rollout budget에서 통계적으로
  취약하므로, 비교 protocol과 evidence strength를 분리해야 한다.
  https://arxiv.org/abs/2503.10966
- Reactive Diffusion Policy, RSS 2025:
  contact-rich manipulation은 slow/fast phase와 tactile/contact 반응성이 중요하다는
  점을 보인다. RDF MVP-2E는 force/tactile policy를 구현하지 않지만, contact/phase
  authority harness를 둔다.
  https://arxiv.org/abs/2503.02881
- Difference-Aware Retrieval Policies for Imitation Learning, 2026:
  standard BC는 rollout 중 OOD state와 compounding error에 취약하며, local
  neighborhood support가 중요한 진단 축임을 보인다.
  https://arxiv.org/abs/2606.09758
- A Careful Examination of Large Behavior Models for Multitask Dexterous
  Manipulation, 2025 / Science Robotics 2026:
  robot policy evidence는 blind/randomized trials, controlled evaluation,
  statistical confidence, normalization sensitivity를 명시해야 한다.
  https://arxiv.org/abs/2507.05331
- AutoEval, 2025:
  policy evaluation은 evaluator와 success classifier 신뢰성이 병목이므로, evaluator
  authority와 trace authenticity를 분리해 기록해야 한다.
  https://arxiv.org/abs/2503.24278
- DAgger, 2011:
  behavior cloning은 policy가 유도한 state distribution에서 covariate shift와
  compounding error가 발생할 수 있다.
  https://arxiv.org/abs/1011.0686

적용 원칙:

```text
research evidence -> harness category
not
research evidence -> new algorithm adoption
```

즉, MVP-2E는 diffusion policy, retrieval policy, force policy, DAgger를 새로
도입하지 않는다. 다만 이 연구들이 반복적으로 지적하는 실패 축을 harness로
명시한다.

## Closure Authority Layer

MVP-2E의 authority hierarchy는 다음과 같다.

```text
Level 0: scenario / evaluator immutability
Level 1: trace authenticity and action semantics
Level 2: expert / base / adapter mechanics
Level 3: policy offline fit and closed-loop support
Level 4: actual Isaac Phase E
Level 5: calibration freeze
Level 6: sealed held-out A/B
Level 7: buyer-facing learning-proven report
```

중요한 규칙:

- env-native 10-consecutive success는 closure authority다.
- RDF/geometric proxy metric은 secondary diagnostic이다.
- secondary diagnostic은 env-native success를 veto할 수 없다.
- offline gate는 actual Isaac success를 대체할 수 없다.
- Phase E는 디버거가 아니라 final sanity gate다.
- calibration과 held-out은 Phase E 통과 전까지 절대 접근하지 않는다.

## Harness Set

### H0. Scenario / Evaluator Immutability Harness

목적: proof target 자체가 흔들리지 않았는지 검증한다.

검증 항목:

- `scenario_profile = v0_6`
- env-native success authority 고정
- `stable_steps_required = 10`
- `success_metric.max_steps = 150`
- held-out `21000-21049` unopened
- seed ranges, exclusion ranges, selector config, evaluator config hash 기록

Fail condition:

- held-out 접근 흔적이 있으면 즉시 fail-closed.
- evaluator threshold나 max step 변경이 있으면 새 MVP-2E slice 금지.

### H1. Action Authority Contract Harness

목적: policy action의 책임 경계를 확인한다.

검증 항목:

```text
base_servo_action
residual_prediction
raw_action_before_authority
raw_action_after_authority
selected_action_adapter
post_adapter_action_vector
```

`ALIGN`에서 필수 invariant:

```text
residual_z_after_authority == 0.0
post_adapter_action_vector[2] == 0.0
```

`v0_7c`는 첫 invariant만 통과했고 두 번째 invariant에서 실패했다. 따라서
이 harness는 `v0_7d` 생성 전 반드시 close-critical이다.

### H2. Adapter Final-Action Harness

목적: adapter가 authority filter 이후에 action 의미를 다시 깨뜨리지 않는지 확인한다.

검증 항목:

- raw z가 0이면 post-adapter z도 0이어야 한다.
- adapter scaling이 phase gate를 우회하면 fail.
- adapter id, adapter config sha256, action scaling, clipping rule을 artifact에 기록한다.

Fail condition:

- `ALIGN` row에서 `abs(post_adapter_action_vector[2]) > 1e-9`.
- adapter가 post-authority action을 다시 하강 action으로 변환.

### H3. Base Servo Closed-Loop Harness

목적: policy residual이 없을 때 base servo / adapter 조합 자체가 gate를 위반하는지 확인한다.

검증 항목:

- base-only action으로 `ALIGN`에서 post-adapter z가 0인지.
- lateral centering이 stable gate에 들어가기 전 하강하지 않는지.
- `DESCEND` 전환 시점의 lateral / orientation / depth가 gate 조건과 일치하는지.

이 harness는 base servo가 task를 완전히 성공해야 한다는 뜻이 아니다. base servo가
정렬 전 하강을 만들면 residual policy가 그 위에서 학습돼도 실패 원인이 섞이므로
막는 것이다.

### H4. Scripted Expert Viability Harness

목적: downstream policy가 모방할 source expert가 실제 Isaac에서 여전히 유효한지 확인한다.

검증 항목:

- fixed 40-run train-generation gate가 `>=20/40` env-native success를 유지.
- actual trace count, success trace count, generator config hash 기록.
- 실패 trace도 failure taxonomy와 함께 보존.

Fail condition:

- scripted expert가 fresh train gate에서 `>=20/40`을 못 넘으면 policy slice 생성 금지.

### H5. Phase / Mode Transition Harness

목적: phase label이 실제 controller 행동 상태와 일치하는지 확인한다.

검증 항목:

- `ALIGN`: z descent 금지, xy/yaw correction active.
- `DESCEND`: centering gate 통과 후 z descent 허용.
- `HOLD`: env-native seated mask를 유지.
- phase가 depth-only proxy로 오염되지 않는지.

Fail condition:

- 같은 phase 안에서 expert action이 bimodal하게 섞이며 linear/residual BC가 gate를
  표현할 수 없는 상태.

### H6. Train Data Consistency Harness

목적: train row, feature row, action target, runtime evaluator가 같은 schema를 쓰는지 확인한다.

검증 항목:

- policy feature schema와 evaluator runtime state schema 일치.
- baseline/candidate가 같은 feature, trainer, adapter, normalization을 사용.
- candidate와 baseline의 차이는 curated vs uncurated data view뿐.
- synthetic / fixture / actual Isaac trace provenance가 구분됨.

Fail condition:

- train에서는 controller-state phase를 쓰고 eval에서는 depth-derived phase를 쓰는 불일치.
- baseline/candidate 중 한쪽에만 다른 adapter나 feature가 적용.

### H7. Action Divergence Harness

목적: closed-loop 실패 전에 policy action이 expert/base action에서 어디서 갈라지는지 측정한다.

검증 항목:

- phase별 expert action 대비 policy action MAE.
- sign mismatch rate.
- z premature descent count.
- xy/yaw correction direction agreement.
- post-adapter action 기준 error.

Pass 의미:

- action divergence가 작다는 것은 success를 증명하지 않는다.
- 다만 Phase E를 실행할 최소 표현력 조건을 만족한다.

### H8. Transition Diversity / Coverage Harness

목적: candidate train view가 성공 episode만 포함해도 transition coverage가 충분한지 확인한다.

검증 항목:

- phase별 row count: `ALIGN`, `DESCEND`, `INSERT`, `HOLD`.
- transition count: `ALIGN->DESCEND`, `DESCEND->HOLD`.
- accepted success trace가 특정 easy band에만 몰리지 않는지.
- controlled failure trace가 baseline uncurated view에 pre-registered mix로 들어가는지.

이 harness는 close-critical은 아니지만, public/investor-facing claim 전 credibility booster다.

### H9. Train-Support / OOD State Harness

목적: policy rollout state가 train data support 밖으로 나가는 순간을 Phase E 전에 찾는다.

검증 항목:

- rollout state의 kNN distance to train states.
- high-distance state에서 action divergence 증가 여부.
- rollout이 train support 밖으로 나간 뒤 compounding error가 발생하는지.

연구 근거: standard BC는 OOD rollout state와 compounding error에 취약하며, 2026 DARP는
local neighborhood support를 imitation policy robustness의 핵심 축으로 다룬다.

Fail condition:

- train-split rollout에서도 early state가 train support 밖으로 벗어나고, 그 구간에서
  post-adapter action이 gate를 위반.

### H10. Covariate-Shift Perturbation Harness

목적: Phase E 5-seed를 바로 태우기 전에 작은 perturbation에서 policy가 복구 가능한지 확인한다.

검증 항목:

- train-side seed에서만 small lateral / orientation perturbation.
- held-out seed 미사용.
- perturbation 후 centering gate 회복 여부.
- action saturation / premature z 발생 여부.

이 harness는 DAgger류의 covariate shift 문제를 새 interactive learning으로 풀자는 뜻이
아니다. MVP-2E에서는 perturbation 진단만 수행한다.

### H11. Saturation / Actuator-Budget Harness

목적: policy가 action clip에 붙어서 상태를 제어하지 못하는지 확인한다.

검증 항목:

- phase별 action saturation rate.
- xy/yaw/z channel별 saturation rate.
- saturation row에서 lateral / orientation error가 감소하는지.
- adapter scaling 후 clip이 발생하는지.

Fail condition:

- `ALIGN` 대부분에서 xy가 clip에 붙고 lateral이 줄지 않음.
- z clip이 phase authority를 우회.

### H12. Contact / Phase Authority Harness

목적: contact-rich insertion에서 z push가 올바른 phase에만 발생하는지 확인한다.

검증 항목:

- `ALIGN`에서는 z push 금지.
- `DESCEND/INSERT`에서는 lateral gate 통과 후 bounded push만 허용.
- contact/seat 진단은 env-native mask를 primary로 하고 RDF geometry는 secondary로 기록.
- force/tactile sensor가 없으므로 force policy claim은 금지.

Fail condition:

- centering 전 z push로 rim-eject가 반복.
- RDF secondary metric으로 env-native failure를 성공 처리.

### H13. Execution Quality Harness

목적: success count만 보지 않고 성공의 질을 기록한다.

검증 항목:

- first success step.
- max consecutive env-native window.
- seated at horizon 여부.
- final lateral / orientation / depth.
- reset boundary 접근 여부.
- row-level trace completeness.

Pass 의미:

- MVP-2 close minimum은 success rate uplift지만, buyer-facing report에는 execution quality를
  함께 남겨야 한다.

### H14. Source / Trace Authenticity Harness

목적: actual Isaac evidence와 synthetic/fixture evidence가 섞이지 않게 한다.

검증 항목:

- `runtime_backend=isaac_runtime` 여부.
- trace file sha256.
- generator config sha256.
- fixture / synthetic / parser-test artifact는 proof evidence에서 제외.

Fail condition:

- synthetic fixture를 actual Isaac rollout처럼 사용.
- proof report가 generated parser test artifact를 policy evidence로 claim.

### H15. Normalization / Action Schema Harness

목적: train, adapter, evaluator, HDF5 export가 같은 action semantics를 쓰는지 확인한다.

검증 항목:

- action channel order.
- pre-adapter vs post-adapter action 구분.
- normalization mean/std 또는 scaling config hash.
- baseline/candidate normalization 동일성.
- HDF5 export와 trainer loader가 같은 schema를 읽는지.

Fail condition:

- offline train action은 raw frame인데 runtime adapter는 scaled action으로 비교.
- baseline/candidate normalization이 서로 다름.

### H16. Statistical Evidence Harness

목적: engineering close minimum과 public evidence strength를 분리한다.

검증 항목:

```text
engineering_close_minimum:
  actual_rollouts_per_policy >= 20
  candidate_success_rate > baseline_success_rate
  curated_vs_uncurated_uplift >= 0.20

stronger_public_evidence_target:
  actual_rollouts_per_policy >= 50
  confidence interval or bootstrap interval reported
  blind/randomized trial order recorded where practical
```

MVP-2 Closed는 engineering close minimum으로 판단한다. 다만 buyer/public-facing report는
`stronger_public_evidence_target_passed`를 별도 boolean으로 표기한다.

### H17. Actual Isaac Phase E Final Sanity Harness

목적: harness 통과 후 생성된 downstream slice가 실제 train-split closed-loop에서 최소
표현력을 갖는지 확인한다.

Pass gate:

```text
runtime_backend = isaac_runtime
policy_slice = downstream slice generated after harness report
rollout_count = 5
required_success_count = 2
candidate_success_count >= 2
heldout_21000_21049_accessed = false
```

Fail condition:

- `0/5` 또는 `1/5`이면 calibration 금지.
- 실패 시 Phase E trace를 H1-H15 harness로 재분류하고, 새 downstream slice를 별도
  pre-registered spec으로만 생성.

## Harness Tiering

Close-critical for next downstream slice:

```text
H0, H1, H2, H3, H4, H5, H6, H7, H9, H11, H12, H14, H15, H17
```

Credibility booster before public/investor-facing claim:

```text
H8, H10, H13, H16 stronger_public_evidence_target
```

Engineering close minimum:

```text
H16 engineering_close_minimum
```

Deferred / post-MVP-2:

```text
force/tactile policy
visual policy performance
real robot validation
live HMD/OpenXR collection
marketplace / production runtime
```

## v0.7d Generation Rule

`v0_7d`는 이 spec의 직접 산출물이 아니다.

`v0_7d` spec 생성을 허용하는 조건:

```text
harness_report.generated = true
harness_report.heldout_21000_21049_accessed = false
H0 passed
root_cause_class is one of the pre-registered classes below
```

Pre-registered root cause classes:

```text
ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK
BASE_SERVO_PREMATURE_DESCENT
PHASE_LABEL_RUNTIME_MISMATCH
TRAIN_RUNTIME_SCHEMA_MISMATCH
ACTION_DIVERGENCE_UNDER_COVARIATE_SHIFT
TRAIN_SUPPORT_OOD_ROLLOUT
SATURATION_DOMINATED_CONTROL
NORMALIZATION_OR_ADAPTER_SCHEMA_MISMATCH
EXPERT_SOURCE_INVALID
EVALUATOR_OR_SCENARIO_MUTATION
```

Mapping:

| Root cause class | Allowed downstream slice |
|---|---|
| `ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK` | `v0_7d` action authority repair: `ALIGN` post-adapter z must be zero |
| `BASE_SERVO_PREMATURE_DESCENT` | base servo gate repair before policy slice; no held-out |
| `PHASE_LABEL_RUNTIME_MISMATCH` | phase/state relabel slice; no policy class change unless separately justified |
| `TRAIN_RUNTIME_SCHEMA_MISMATCH` | schema/normalization repair slice |
| `ACTION_DIVERGENCE_UNDER_COVARIATE_SHIFT` | train-side recovery/support slice; no held-out |
| `TRAIN_SUPPORT_OOD_ROLLOUT` | support/coverage slice; no held-out |
| `SATURATION_DOMINATED_CONTROL` | action adapter / actuator budget repair slice |
| `NORMALIZATION_OR_ADAPTER_SCHEMA_MISMATCH` | normalization contract repair slice |
| `EXPERT_SOURCE_INVALID` | return to scripted expert / train-generation gate |
| `EVALUATOR_OR_SCENARIO_MUTATION` | stop; proof authority invalidated |

현재 `v0_7c` 진단 기준으로 가장 유력한 downstream slice는 다음이다.

```text
v0_7d_action_authority_post_adapter_z_gate
```

하지만 이 이름과 구현은 harness report가 `ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK` 또는
`BASE_SERVO_PREMATURE_DESCENT`를 확정한 뒤에만 생성한다.

## Artifact Contract

새 evidence 경로:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/harness_gated_closure/
```

필수 artifact:

```text
mvp2e_harness_config.json
mvp2e_harness_report.json
mvp2e_harness_gate_manifest.json
harness_trace_index.json
harness_research_rationale.json
```

`mvp2e_harness_report.json` 필수 필드:

```json
{
  "schema_version": "rdf_mvp2e_harness_report_v0.1.0",
  "scenario_profile": "v0_6",
  "policy_slice_under_test": "v0_7c",
  "downstream_slice_created": false,
  "downstream_slice_id": null,
  "heldout_21000_21049_accessed": false,
  "calibration_accessed": false,
  "harnesses": {},
  "close_critical_passed": false,
  "root_cause_class": "ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK",
  "recommended_downstream_slice": "v0_7d_action_authority_post_adapter_z_gate",
  "mvp2_closed": false,
  "non_claims": {
    "real_robot_success": false,
    "physical_robot_readiness": false,
    "visual_policy_performance": false,
    "hmd_openxr_readiness": false
  }
}
```

## Stop Rules

Stop and report if:

- held-out `21000-21049` was accessed before Phase G.
- evaluator success authority changed.
- scenario profile hash changed without explicit new profile.
- synthetic/fixture evidence is used as actual Isaac proof.
- baseline/candidate use different trainer, adapter, feature schema, or normalization.
- root cause class is not in the pre-registered list.
- a proposed repair requires live robot control, HMD/OpenXR collection, force-control runtime,
  VLA fine-tuning, or policy architecture expansion beyond the pre-registered slice.

## Claim Boundary

Allowed after this harness spec is implemented:

```text
ForgeXR/RDF now has a harness-gated MVP-2E closure path that prevents repeated
policy slice iteration without root-cause evidence.
```

Not allowed:

```text
MVP-2 is closed.
policy uplift is proven.
curated data improves policy success on held-out.
the policy works on real robots.
the system is HMD/OpenXR ready.
the evidence proves visual policy performance.
```

## Next Step

After user approval of this spec:

1. Write an implementation plan for the harness report builder and close-critical gates.
2. Implement harnesses in red/green order, starting with H0-H3 and H15 because they directly
   explain the `v0_7c` failure.
3. Generate `mvp2e_harness_report.json` against `v0_7c`.
4. Only if the report classifies the root cause, create the downstream `v0_7d` spec.
