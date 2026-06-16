# MVP-2E v0.7h Calibration Pre-Signal Design

## 목적

`v0_7g`는 actual Isaac Phase E expressibility sanity를 통과했다.
하지만 MVP-2 Closed는 아직 아니다. 다음 gate는 roadmap Phase F다.

`v0_7h`의 목적은 held-out `21000-21049`를 열기 전에 calibration split
`20000-20029`에서 baseline/candidate `v0_7g` policy artifact를 같은
runtime/action authority로 평가해 sealed held-out을 열 가치가 있는지 확인하는 것이다.

## 현재 증거

- `v0_7g` offline xy authority gate passed.
- actual Isaac `v0_7g` Phase E expressibility sanity passed:
  - `runtime_backend=isaac_runtime`
  - `success_count=2`
  - `required_success_count=2`
  - `rollout_count=5`
  - `heldout_21000_21049_accessed=false`
- MVP-2 remains open because calibration pre-signal and held-out A/B are not run.

## 설계 결정

### 선택한 접근

`v0_7h`는 새 policy/trainer를 만들지 않는다.

대신 `v0_7g`에서 생성된 아래 artifact를 그대로 사용한다.

- `candidate_policy_artifact_v0_7g.json`
- `baseline_policy_artifact_v0_7g.json`
- `offline_xy_authority_gate_v0_7g.json`
- `expressibility_sanity_gate_v0_7g.json`

`v0_7h`는 calibration scenarios `20000-20029`만 actual Isaac으로 실행한다.
기존 evaluator backend는 `held_out` split만 rollout 대상으로 읽기 때문에,
runtime용 calibration manifest는 calibration rows를 `held_out`으로 복사하되 다음
필드를 명시한다.

- `semantic_eval_split=calibration`
- `source_split=calibration`
- `protected_heldout_21000_21049_accessed=false`
- `heldout_opened=false`

이 split rewrite는 backend API 재사용을 위한 wrapper이며, product claim 상
held-out 개봉이 아니다.

### 거부한 접근

- `v0_7g` Phase E 통과만으로 held-out을 바로 실행: roadmap Phase F 위반.
- `21000-21049` 일부를 calibration처럼 사용: held-out seal 위반.
- calibration 결과를 보고 success metric, xy authority, trainer, dataset mix를 변경:
  p-hacking risk. 실패 시 새 pre-registered slice로 회귀한다.
- deterministic/proxy calibration으로 held-out go 판단: MVP-2 proof path에 부족.

## Gate 정의

`v0_7h_calibration_presignal_gate.passed=true` 조건:

```text
runtime_backend == "isaac_runtime"
AND proof_runtime == "dedicated_isaac_connector_insertion_evaluator"
AND calibration_rollouts_per_policy >= 30
AND candidate_calibration_success_rate > baseline_calibration_success_rate
AND candidate_calibration_success_rate >= 0.30
AND heldout_21000_21049_accessed == false
AND calibration_opened == true
AND mvp2_closed == false
AND policy_uplift_proven == false
```

실패 시:

```text
heldout_allowed=false
heldout_21000_21049_accessed=false
mvp2_closed=false
recommended_downstream_slice="v0_7i_calibration_failure_diagnosis"
```

## Artifact

생성 경로:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7h_calibration_presignal/
    calibration_runtime_manifest_v0_7h.json
    calibration_presignal_gate_v0_7h.json
    calibration_rollout_summary_v0_7h.json
    calibration_external_rollouts/
      baseline_calibration_rollouts_v0_7h.json
      candidate_calibration_rollouts_v0_7h.json
```

호환을 위해 top-level에도 다음 파일을 쓴다.

```text
calibration_presignal_gate.json
```

top-level file은 `v0_7h` gate를 가리키는 compatibility pointer이며,
held-out opening authority가 아니다. held-out 개봉은 별도 Phase G slice에서만
수행한다.

## Boundary

- `v0_7h`는 calibration을 연다.
- `v0_7h`는 held-out을 열지 않는다.
- `v0_7h`는 MVP-2 closure authority가 아니다.
- `v0_7h`는 policy uplift를 claim하지 않는다.
- `v0_7h`는 real robot, HMD/OpenXR, visual policy, deployable policy readiness를
  claim하지 않는다.

## 다음 분기

Pass:

- 다음 valid step은 `v0_7i` held-out A/B execution plan이다.
- held-out `21000-21049` 50 seeds를 양 policy 각 50 rollout으로 단 1회 실행한다.

Fail:

- held-out은 계속 봉인한다.
- 다음 valid step은 `v0_7i_calibration_failure_diagnosis`다.
- calibration trace에서 candidate/baseline success gap, action authority, xy/z
  trace, phase transition, env-native stable window를 artifact-only로 분류한다.
