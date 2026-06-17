# MVP-2E v0.13 Policy Influence Authority Ceiling Slice 설계

## 목적

v0.12 actual Isaac calibration은 baseline과 candidate가 모두 `25/30 = 0.8333`으로 성공해 fail-closed 됐다. v0.12a artifact-only 진단은 baseline/candidate의 learned residual 차이가 runtime adapter/authority 이후 크게 압축되는 것을 확인했다.

v0.13의 목적은 shared runtime authority가 policy 차이를 지우지 못하도록 ceiling을 걸고, 같은 evaluator/task에서 curated candidate와 uncurated baseline의 차이가 calibration과 held-out에 실제로 남는지 검증하는 것이다.

## 증거 기반 출발점

v0.12a 진단 결과:

- `primary_root_cause_class=RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME`
- paired calibration outcome: `B1_C1=25`, `B1_C0=0`, `B0_C1=0`, `B0_C0=5`
- raw action mean delta: `0.038582484729`
- post-adapter action mean delta: `0.008654557081`
- post-adapter identical fraction: `0.573462125064`
- shared XY authority active fraction: `0.68835790544`
- final post-adapter z block active fraction: `0.672343670564`
- fresh held-out `36000-36049` was not opened.

이 증거는 “candidate가 못 배웠다”가 아니라 “shared authority가 candidate/baseline action 차이를 압축했다”는 쪽을 지지한다.

## Scope

v0.13은 MVP-2 closure를 다시 시도하는 fresh runtime slice다.

포함:

- v0.12 정책/학습 view를 parent로 한 v0.13 policy artifact 생성
- shared `policy_influence_authority_ceiling_config` 추가
- selected action adapter의 state-feedback influence를 global ceiling으로 제한
- v0.13 runtime path에서 v0.8h style forced z progress injection을 사용하지 않음
- final z authority와 shared hysteresis는 유지
- fresh calibration `37000-37029`
- fresh held-out `38000-38049`
- calibration 통과 시에만 held-out open
- same policy class / trainer / adapter / authority ceiling for baseline and candidate

제외:

- held-out 결과를 본 뒤 threshold 변경
- candidate-only authority
- live robot / HMD / ROS runtime
- policy architecture rewrite
- VLA / RL / world model training
- success metric 변경
- v0.12 결과에 v0.13 기준 소급 적용

## v0.13 Authority Definition

### 기존 문제

v0.12는 다음 경로에서 learned residual 차이가 압축됐다.

1. selected action adapter의 `policy_plus_state_feedback`
2. final post-adapter XY authority
3. v0.8h derived safe-entry / progress authority

결과적으로 baseline/candidate raw action은 달라도 final action과 rollout outcome이 같아졌다.

### v0.13 원칙

Shared authority는 “policy를 대신해 성공시키는 controller”가 아니라 “unsafe action을 막는 guardrail”이어야 한다.

따라서 v0.13에서는:

- z authority는 unsafe ALIGN descent를 block한다.
- z progress를 policy 없이 강제로 inject하지 않는다.
- XY authority는 task-state servo로 final action을 대체하지 않는다.
- selected adapter의 state-feedback term은 낮은 global ceiling을 갖는다.
- post-adapter action은 candidate/baseline raw-policy delta를 일정 비율 이상 보존해야 한다.

## Pre-registered Config

`policy_influence_authority_ceiling_config`:

```json
{
  "policy_slice": "v0_13",
  "authority_id": "policy_influence_authority_ceiling_v0_13",
  "source_policy_slice": "v0_12",
  "state_feedback_gain_ceiling": 0.5,
  "xy_action_clip": 0.05,
  "z_action_clip": 0.16,
  "z_progress_injection_enabled": false,
  "final_xy_state_feedback_replacement_enabled": false,
  "min_post_adapter_delta_retention_ratio": 0.35,
  "max_post_adapter_identical_fraction": 0.50,
  "same_config_for_baseline_and_candidate": true,
  "heldout_excluded": true
}
```

`state_feedback_gain_ceiling=0.5`은 기존 `WEAK_BASE_SERVO_CONFIG.xy_gain`과 같은 scale로 고정한다. v0.12의 `xy_state_feedback_gain=3.0`, final XY authority gain `4.0` 대비 shared task-state correction을 줄이는 값이다.

## Fresh Split

- calibration: `37000-37029`
- held-out: `38000-38049`

Forbidden reuse:

- previous held-out ranges: `21000-21049`, `24000-24049`, `26000-26049`, `27000-27049`, `32000-32049`, `34000-34049`, `36000-36049`
- previous calibration ranges: `30000-30029`, `31000-31029`, `33000-33029`, `35000-35029`

## Offline Gate

Before Isaac runtime, v0.13 must pass an artifact-only policy influence gate using v0.12 calibration traces.

Required:

- `raw_action_before_authority_mean_delta > post_adapter_action_mean_delta`
- simulated v0.13 post-adapter retention ratio `>= 0.35`
- simulated v0.13 post-adapter identical fraction `<= 0.50`
- same authority ceiling config hash for baseline and candidate
- held-out remains unopened

This gate is diagnostic and pre-runtime only. It is not closure authority.

## Calibration Gate

Fresh calibration `37000-37029` must satisfy:

- actual Isaac runtime only
- `baseline_success_rate <= 0.65`
- `candidate_success_rate >= 0.80`
- `candidate_success_rate > baseline_success_rate`
- `candidate_baseline_success_gap >= 0.20`
- attribution/policy influence preservation passes
- held-out remains unopened

If this fails, the slice fails closed and writes a diagnosis recommendation. It must not open held-out.

## Held-out Closure Gate

Fresh held-out `38000-38049` opens only if calibration passes.

MVP-2 Closed requires:

- actual rollouts per policy `>= 20`
- candidate success rate > baseline success rate
- curated vs uncurated uplift `>= 0.20`
- learning report passes
- no held-out leakage
- buyer/non-claim boundaries preserved

## Claim Boundary

Until held-out closure passes:

- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `proof_authority=false` for artifact-only gates
- no real robot / HMD / visual policy / deployable policy claim

Even if v0.13 closes MVP-2, the claim remains Isaac evaluator-domain privileged-state learning proof.
