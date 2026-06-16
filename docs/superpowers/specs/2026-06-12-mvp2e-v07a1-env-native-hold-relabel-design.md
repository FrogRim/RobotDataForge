# MVP-2E v0.7a.1 Env-Native HOLD Relabel Design

Date: 2026-06-12

## 목적

`v0_7a` behavior_state_phase relabel이 fail-closed된 원인(`HOLD=0`,
`offline_train_fit_gate.passed=false`, `failure_reason=required_phase_missing`)을
수정한다.

수정의 본질은 한 줄이다: HOLD phase의 정의를 geometry proxy 상수
(`insertion_depth_m >= 0.03`)에서 **closure authority인 per-step env-native
success mask**로 교체한다.

```text
v0_7a_1 goal:
  candidate/baseline relabel에서 ALIGN/DESCEND/HOLD 3-phase coverage 확보
  offline_train_fit_gate를 정직하게 평가 가능하게 만듦
  (통과 시) Phase E expressibility sanity 재실행 unblock

v0_7a_1 non-goal:
  phase taxonomy 확장 (CONTACT/STABILIZE 등 추가 금지)
  policy class 변경 (v0_7b residual servo는 pre-registered fallback으로 유지)
  offline fit gate threshold 완화
  success metric / env-native authority / stable_steps=10 변경
  held-out 21000-21049 개봉
  calibration 실행
  새 Isaac train data 생성
```

이 slice는 MVP-2 Closed 선언이 아니다.

## 현재 증거 (root cause 확정)

`v0_7a` artifact (`v0_7a_relabel_config.json`, `offline_train_fit_gate.json`):

```text
assignment_rule_text:
  "ALIGN if lateral_error_m > 0.001;
   DESCEND if lateral_error_m <= 0.001 and insertion_depth_m < 0.03;
   HOLD if lateral_error_m <= 0.001 and insertion_depth_m >= 0.03"
seat_depth_threshold_m = 0.03
seat_depth_threshold_source = SUCCESS_METRIC.insertion_depth_m_min
candidate_phase_row_counts.HOLD = 0
baseline_phase_row_counts.HOLD = 0
failure_reason = required_phase_missing
```

40/40 parent train trace 전수 실측 (2026-06-12):

```text
성공 trace 28개의 env_native_success=true row depth: 0.02401 ~ 0.02500
성공 trace의 max insertion depth: 0.02472 ~ 0.02500
depth >= 0.03 도달한 성공 trace: 0 / 28
per-step env_native_success mask 기록: 40 / 40
```

해석:

- env-native 권위가 인정하는 착좌는 **depth ≈ 0.024~0.025**에서 발생한다.
- `0.03`은 geometry metric의 상수이며 실제 성공 trace가 물리적으로 도달하지 않는다.
- 따라서 `HOLD=0`은 taxonomy 문제도 expressibility 문제도 아닌
  **authority-mismatch 상수 버그**다.

동일 버그 클래스 3회째:

```text
1. RDF geometry pass / env-native fail 방향 불일치 (16096 계열)
2. env-native pass / RDF UNDER_INSERTION 4μm fail (16042, depth 0.024996 vs 0.025)
3. 본 건: geometry seat 상수 0.03 vs env-native 착좌 깊이 ~0.025 → HOLD=0
```

## Authority Invariant (신규 — 이 slice의 핵심 규칙)

이 invariant를 이번 slice부터 영구 규칙으로 고정한다.

```text
착좌/성공 여부를 판정하는 모든 코드는 env-native success mask를 직접 읽는다.
geometry 상수로 착좌를 재유도하지 않는다.
geometry 값(depth/lateral/orientation)은 report-only diagnostic이다.
```

적용 범위: relabel 규칙, runtime phase derivation, offline fit gate,
이후 모든 신규 proof 코드.

## 새 Relabel 규칙 (pre-register + hash, 재라벨 실행 전 고정)

```text
HOLD    := row.env_native_success == true
DESCEND := (not HOLD) AND lateral_error_m <= approach_lateral_gate_m
ALIGN   := (not HOLD) AND lateral_error_m >  approach_lateral_gate_m

approach_lateral_gate_m = 0.001
  (source: parent v0_6i controller_repair_config.approach_lateral_gate_m, 불변)

equality handling:
  lateral_error_m == approach_lateral_gate_m → DESCEND branch

invalid row handling:
  row에 env_native_success 필드 부재 → fail_closed (reason=env_native_mask_missing)
  negative insertion_depth_m → fail_closed (v0_7a 상속)

seat_depth_threshold_m: 제거.
  v0_7a_1 relabel config에 geometry seat 상수 키가 존재하면 안 된다 (테스트로 가드).
```

근거:

- "착좌했는가"의 권위는 env-native로 freeze되어 있으므로, "착좌를 유지하는
  행동"(HOLD)의 라벨도 그 권위의 mask를 직접 읽는 것이 유일하게 정합적이다.
- depth 상수를 `0.024`로 낮추는 대안은 기각한다 — 또 다른 proxy 상수를
  결과를 보고 고르는 것이며, 같은 버그 클래스의 4번째 발생을 심는 길이다.
  mask 직접 사용은 **상수 0개**다.

기대 분포 sanity (gate 아님, report-only):

```text
성공 판정이 env-native 10-consecutive였으므로 성공 trace당 HOLD rows >= 10이
구조적으로 보장된다. candidate HOLD rows >= 280 (28 trace × >=10) 예상.
per-trace HOLD row count를 manifest에 기록한다.
```

## 불변 사항 (fairness / integrity)

```text
feature_schema 불변 (phase one-hot + metric state + previous action)
trainer / hyperparameters 불변
offline_train_fit_gate thresholds 불변:
  candidate_z_mae_max=0.02
  candidate_xy_mae_max=0.01
  candidate_hold_abs_z_mean_max=0.04
baseline/candidate 동일 규칙 적용 (baseline metrics는 report-only 유지,
  phase missing 시 metric key null 보존 — v0_7a 동작 상속)
parent proof-chain hash validation 유지 (selected_action_adapter.json 포함)
env-native success authority / stable_steps=10 / max_steps 불변
held-out 21000-21049 봉인 유지, calibration 미실행
Phase E gate 기준 불변: 5 train seeds, >=2/5 env-native success
--policy-slice v0_7a_1은 --offline-relabel-only 또는
  --expressibility-sanity-only 외 즉시 reject (v0_7a 동작 상속)
```

## Runtime 일관성

`v0_7a`가 도입한 runtime behavior_state_phase derivation을 동일 규칙으로 갱신한다.

```text
rollout 중 env-native success mask는 env에서 step마다 계산되어 이미 기록된다.
prediction 시 phase 계산 = 위 relabel 규칙 그대로 (mask + lateral gate).
train/eval phase 신호의 동일성이 이 수정의 본질이다.
```

## Privileged-Feature 비클레임 보강

phase 입력이 env-native success mask(privileged 평가 신호)를 직접 조건으로
사용하므로 보고서에 명시한다.

```text
policy phase conditioning은 Isaac evaluator-domain privileged 신호
(env-native success mask)를 사용한다. 이는 기존 privileged task-state
비클레임 범위에 포함되며, deployable real-world visual policy 성능을
주장하지 않는다.
```

기존 non-claims 5종(`deployable_real_robot_policy=false` 등)은 그대로 유지한다.

## Artifact Contract

Output root:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_1_behavior_state_phase_relabel/
```

Required artifacts:

```text
v0_7a_1_relabel_config.json        (규칙 텍스트 + approach gate source + sha256)
offline_train_fit_gate.json        (candidate/baseline phase_row_counts에
                                    ALIGN/DESCEND/HOLD 모두 + per-phase MAE)
v0_7a_1_relabel_manifest.json      (parent hash verdict, phase coverage,
                                    per-trace HOLD count, fail-closed 사유)
expressibility_sanity_gate_v0_7a_1.json  (Phase E 재실행 후)
```

evidence_manifest 갱신 포함. 모든 artifact에 `v0_7a_1_relabel_config_sha256` 포함.

## Tests (required focused)

```text
- mask=true row는 depth와 무관하게 HOLD (insertion_depth_m=0.0에서도 HOLD)
- mask=false AND lateral<=gate → DESCEND
- mask=false AND lateral>gate → ALIGN
- lateral==gate equality → DESCEND branch
- env_native_success 필드 부재 row → fail_closed (env_native_mask_missing)
- v0_7a_1 relabel config에 seat_depth_threshold 계열 키 부재 가드
- 합성 success trace(mask 10-consecutive)에서 HOLD>=10
- baseline/candidate가 동일 rule sha256으로 라벨됨
- runtime phase derivation == relabel 규칙 (parity test)
- offline fit gate가 ALIGN/DESCEND/HOLD 3-phase 모두에서 MAE 계산
- --policy-slice v0_7a_1이 허용 모드 외 즉시 reject
- v0_7a(구) config/artifact를 v0_7a_1 입력으로 사용 시 reject
```

## 실행 명령

```bash
# 1) offline relabel + 재학습 + offline fit gate (Isaac 불필요)
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7a_1 \
  --offline-relabel-only --pretty

# 2) offline fit gate 통과 시에만 Phase E 재실행 (Isaac 1세션)
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7a_1 \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

## Stop Conditions

다음 상황에서는 중단하고 보고한다.

```text
- parent rows에 env_native_success 부재 (실측 40/40과 모순 → 데이터 조사)
- mask 규칙 적용 후에도 HOLD=0 (실측 증거와 모순 → 구현 버그 조사,
  규칙 패치로 우회 금지)
- offline fit gate가 z/xy MAE에서 실패
  → 이것이 진짜 expressibility 신호 → v0_7b residual servo 결정으로 이관
  (threshold 완화 금지)
- Phase E 재실행 결과 0~1/5
  → v0_7b residual servo fallback으로 이관
- held-out 개봉이 필요해짐
- success metric / authority / threshold 완화가 필요해짐
```

## Acceptance Criteria

`v0_7a_1` spec은 다음을 만족하면 완료다.

```text
- relabel 규칙이 실행 전에 pre-register되고 sha256가 모든 artifact에 존재
- candidate/baseline 모두 ALIGN/DESCEND/HOLD 3-phase coverage (HOLD>0)
- 성공 trace당 HOLD>=10이 manifest에 기록됨
- offline_train_fit_gate가 정직하게 평가됨 (pass든 fail이든 fail-closed 무결)
- runtime phase derivation parity 테스트 통과
- pass 시 Phase E 재실행 결과가 기록됨 (>=2/5면 Phase F 진입 자격)
- held-out 21000-21049 미개봉, calibration 미실행 유지
- Authority Invariant가 spec/debugging guide에 기록됨
- worklog / Handoff 갱신
```

## Open Boundary

이 spec은 v0.7a.1이 Phase E를 통과한다고 가정하지 않는다. offline fit gate가
MAE에서 정직하게 실패하면 그것이 곧 진짜 expressibility 신호이며, 그때의
올바른 다음 단계는 threshold 완화가 아니라 pre-registered fallback인
`v0_7b residual servo BC`다.
