# MVP-2E v0.8j Attribution-Preserving Candidate Margin Diagnosis 설계

## 목적

`v0.8h` actual Isaac calibration은 candidate 25/30, baseline 23/30으로
candidate가 앞섰지만, calibration gate가 요구하는 `candidate-baseline >= 0.10`
조건에는 미달했다. `v0.8i`는 이 실패를 `baseline_success_compression=true`,
`candidate_failures_total=5`, `candidate_failures_to_recover_for_calibration_gate=2`로
분류했다.

`v0.8j`의 목적은 곧바로 controller를 강화하는 것이 아니다. shared safety/action
authority를 더 강화하면 baseline도 같이 올라가 uplift가 더 압축될 수 있다. 따라서
`v0.8j`는 기존 `v0.8h` trace만 사용해 candidate가 baseline과 다른 learned residual
margin을 실제로 갖고 있는지 판정한다.

## 범위

포함한다.

- `v0.8h` failed calibration gate와 60개 calibration trace를 읽는다.
- `v0.8i` diagnosis를 부모 증거로 요구한다.
- paired outcome을 `B1_C1`, `B0_C1`, `B1_C0`, `B0_C0`로 유지한다.
- role별 residual z intent, z-open timing, depth timing, lateral-at-z-open을 계산한다.
- candidate-only win(`B0_C1`)에서 관측된 residual margin signature를 기준 evidence로 기록한다.
- both-fail(`B0_C0`) candidate failure 중 같은 signature가 존재하는지 판정한다.
- attribution-preserving repair가 가능한지 fail-closed로 결정한다.

제외한다.

- Isaac runtime 실행
- held-out `27000-27049` 접근
- success metric 변경
- shared authority 추가 강화
- candidate-only hand-coded controller 추가
- retry, withdraw, search, force-control
- real robot/HMD/visual policy claim

## 핵심 판정

`v0.8j`는 세 가지를 분리한다.

1. `candidate_only_margin_signature`
   - `B0_C1` seed에서 candidate가 baseline보다 더 강한 learned residual descent intent를 보였는지.
   - 기본 evidence: z-open 구간의 candidate residual z median이 baseline보다 더 음수이고, candidate z-open lateral median이 더 작다.

2. `candidate_failure_recoverability`
   - `B0_C0` candidate failure 중 candidate-only margin signature와 같은 residual pattern이 존재하는지.
   - 존재하면 다음 slice에서 symmetric residual-intent rule을 설계할 수 있다.
   - 존재하지 않으면 candidate-only hand-coded repair는 attribution을 약화하므로 금지한다.

3. `next_slice_recommendation`
   - recoverable failure 수가 `v0.8i.target_failure_reduction_minimum` 이상이면
     `v0_8k_residual_intent_margin_repair`를 추천한다.
   - 부족하면 `v0_8k_candidate_training_signal_rebalance`를 추천한다.

## Attribution Guard

repair 가능 판정은 다음 조건을 모두 만족해야 한다.

- rule은 baseline/candidate에 동일하게 적용 가능해야 한다.
- rule activation 차이는 policy artifact의 learned residual output에서만 나와야 한다.
- same shared safety authority를 유지해야 한다.
- baseline artifact나 baseline trace를 억지로 낮추는 변경은 금지한다.
- candidate-only 상수, seed별 조건, calibration seed별 예외는 금지한다.

## 산출물

`storage/proof_evidence/mvp2c_isaac_training_calibration/` 아래에 다음을 생성한다.

```text
v0_8j_attribution_preserving_candidate_margin_diagnosis/
  v0_8j_attribution_preserving_candidate_margin_diagnosis.json
  residual_margin_table_v0_8j.json
  candidate_failure_recoverability_v0_8j.json
  evidence_manifest.json
```

top-level 호환 산출물도 남긴다.

```text
attribution_preserving_candidate_margin_diagnosis_v0_8j.json
```

## Close Boundary

`v0.8j`는 proof authority가 아니다.

- `mvp2_closed=false`
- `policy_uplift_proven=false`
- `heldout_opened=false`
- `fresh_heldout_27000_27049_accessed=false`

이 slice가 통과해도 MVP-2는 닫히지 않는다. 이 slice는 다음 runtime slice가
candidate attribution을 보존할 수 있는지 판정하는 진단 gate다.

## 성공 조건

`v0.8j` 자체 성공 조건:

- `v0.8h` failed calibration evidence를 읽는다.
- `v0.8i` diagnosis를 읽고 hash로 연결한다.
- 60개 `v0.8h` calibration trace를 모두 분류한다.
- paired outcome count가 `v0.8i`와 일치한다.
- candidate failure 5개가 모두 recoverability 판정된다.
- unclassified evidence가 0개다.
- held-out `27000-27049` 접근이 false로 유지된다.

MVP-2 closure 조건은 아니다.
