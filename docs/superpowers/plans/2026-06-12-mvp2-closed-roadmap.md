# MVP-2 Closed Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 이 문서는 MVP-2 Closed까지의 **master roadmap**이다. Phase A는 즉시 실행 가능한
> 구현 단위로 상세화했고, Phase B 이후는 각 phase 진입 시점에 이 문서의 gate 정의를
> 그대로 상속하는 slice spec/plan(기존 ralplan cadence)을 생성해 실행한다.
> 이유: Phase B+의 정확한 코드는 직전 phase의 actual Isaac 결과에 의존하므로,
> 지금 코드를 박제하면 가짜 정밀도(placeholder)가 된다. 대신 **gate/결정 규칙은
> 지금 전부 pre-register**한다 — 그것이 이 프로젝트의 무결성 모델이다.

**Goal:** actual Isaac held-out에서 curated > uncurated policy uplift >= 0.20을 단 1회의 sealed held-out 실행으로 증명하여 MVP-2를 Closed로 만든다.

**Architecture:** 현재 fail-closed 지점(repair probe)부터 held-out까지의 blocker를 의존성 순서로 해소한다. 각 phase는 pre-registered gate를 가지며, 모든 Isaac 증거는 `storage/proof_evidence/` + git-tracked `evidence_manifest.json`으로 보존한다. held-out `21000-21049`는 Phase G 전까지 봉인 유지.

**Tech Stack:** Python 3.11+, NumPy, h5py, pytest, IsaacLab `Isaac-Factory-PegInsert-Direct-v0`, 기존 `run_mvp2c_isaac_training_calibration.py` / `run_mvp2b_isaac_proof_evaluator.py`, env-native `_get_curr_successes` success authority.

---

## 현재 상태 (2026-06-12 실측, Phase E까지 진행 후)

```text
MVP-2: Not Closed
repair probe (v0.6i): green
fixed 40-run gate: passed, 28/40 env-native 10-consecutive success
train dataset / policy artifacts: generated
expressibility sanity: failed, 0/5 candidate policy train-seed success
calibration presignal: not run
held-out 21000-21049: sealed (50 seeds)
증거 보존: storage/proof_evidence/ + evidence_manifest 가동
미완 감사 항목: CI 없음, scenario profile if-chain 35개 (Stage 1 미완)
```

### 역사적 핵심 진단 (Phase A의 근거)

env config: `episode_length_s=10.0`, `decimation=8`, 120Hz → env auto-reset ≈ step 148.
즉 **유효 rollout 예산은 ~147 step**인데 현재 rollout은 150 step을 돌며 reset을 넘는다.

- `16023`의 "hold failure"는 controller 결함이 아니라 **도착이 reset 직전(147)이라
  10-consecutive hold를 쌓을 시간이 물리적으로 없는 것** + post-reset row 오염.
- `16096`의 "tail regression"도 post-reset row가 진단에 섞였을 가능성이 높다.
- 따라서 순서는: (A) reset-boundary 처리로 진단을 깨끗하게 → (B) 그래도 남는
  controller 결함만 envelope 안에서 수리. **horizon 증가는 계속 금지** —
  이번 수정은 horizon을 늘리는 게 아니라 env reset 경계 **안으로 잘라내는** 것이다.

## Blocker 의존성 체인

```text
B0a reset-boundary/tail 처리 (Phase A)
  → B0b controller pacing: seat-by-deadline (Phase B, 필요 시)
    → repair_probe_green_light=true
      → B1 fixed 40-run train-generation gate >=20/40 (Phase C)
        → B2 train dataset: accepted + controlled failure + baseline mix (Phase D)
          → B3 policy training + train-split expressibility sanity (Phase E)
            → B4 calibration: adapter freeze + uplift pre-signal go/no-go (Phase F)
              → B5 held-out 단 1회 50 rollouts/policy (Phase G)
                → B6 closure derivation + buyer artifacts (Phase G/H)
```

---

## Phase 0: 엔지니어링 enabler (proof와 병행, proof-경로 무변경)

### Task 0.1: 최소 CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1:** 워크플로 작성 — push/PR 시 `uv run pytest apps/api/tests -q -m "not isaac"`(또는 Isaac 의존 테스트가 marker 없으면 전체 비-Isaac 테스트), `uvx ruff check scripts apps/api`, `uv run python -m compileall -q scripts apps/api`
- [ ] **Step 2:** Isaac 의존 테스트가 import 단계에서 실패하지 않는지 로컬로 동일 명령 실행해 확인
- [ ] **Step 3:** 커밋 (사용자 승인 후 push)

### Task 0.2: scenario profile 데이터화 (감사 Stage 1, hash-불변 보증부)

**Files:**
- Create: `fixtures/proof/scenario_profiles.json`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py` (`_scenario_seed_ranges`, `_manifest_version_for_profile`, `_excluded_prior_heldout_seed_ranges`)
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: hash-불변 RED 테스트 먼저** — 모든 기존 profile(v0_1…v0_6)에 대해 현재 코드의 `build_mvp2c_scenario_manifest()` `manifest_sha256`를 골든 값으로 고정하는 테스트 작성 (현재 구현에서 값 추출 → 테스트에 상수로 박음)
- [ ] **Step 2:** seed ranges/manifest version/excluded ranges를 JSON으로 이전, if-chain을 로더 1개로 대체
- [ ] **Step 3:** hash-불변 테스트 GREEN 확인 — 골든 hash 전부 동일해야 통과. 하나라도 다르면 **롤백** (proof-frozen 동작 변경 금지)
- [ ] **Step 4:** 전체 회귀 `uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q` + 커밋

수용 기준: 신규 slice 추가가 JSON 1건으로 끝남. 기존 manifest hash 전부 불변.

---

## Phase A: v0.6g — reset-boundary / post-reset tail 처리 (현재 blocker, 즉시)

목적: 진단·판정에서 env reset 오염을 제거해 "controller의 진짜 결함"만 남긴다.
success metric(`max_steps=150`, `stable_steps=10`, env-native authority)은 불변.

### Pre-register (실행 전 hash 고정)

```text
env_reset_boundary_steps: env.max_episode_length에서 runtime에 읽어 artifact에 기록
env_reset_post_step_guard_steps = 2
effective_rollout_budget_steps = min(success_metric.max_steps, env_reset_boundary_steps - env_reset_post_step_guard_steps)
  ← horizon 증가 아님(항상 <=150). rollout은 이 예산을 넘겨 step하지 않는다.
  ← 실제 Isaac A3에서 timeout reset이 env.step() 이후 row에 반영되어 `-1` guard가 한 줄 부족했음을 확인했고,
     `-2` post-step guard로 수정했다.
post_reset_rows_excluded = true
  ← mid-rollout reset-like jump가 그래도 감지되면, jump 이후 row는
    convergence/regression/min-lateral/consecutive 계산에서 제외하고
    jump 발생 사실을 artifact에 기록한다 (배제는 진단 정합용이지 성공 보정용이 아님).
seat_deadline_steps = effective_rollout_budget_steps - stable_steps_required
  ← Phase B pacing의 목표값으로만 사용. 판정 변경 아님.
```

### Task A1: rollout 예산 절단 + reset 경계 메타데이터

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py` (Isaac rollout loop)
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py` (repair probe gate 빌더)
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [x] **Step 1: RED 테스트** — `test_v06g_rollout_budget_never_steps_past_env_reset_boundary`: fake env(`max_episode_length=148`)로 rollout 시 trace 길이 <= 146이고 artifact에 `env_reset_boundary_steps=148`, `effective_rollout_budget_steps=146`, `env_reset_post_step_guard_steps=2`가 기록됨을 단언. `test_v06g_rollout_budget_accounts_for_post_step_timeout_reset`: fake env(`max_episode_length=150`)로 trace 길이 148을 단언. `test_v06g_budget_is_not_horizon_increase`: `effective_rollout_budget_steps <= success_metric.max_steps` 단언.
- [x] **Step 2:** rollout loop에서 `env.max_episode_length`(또는 `env_cfg`에서 계산)를 읽어 step 상한 적용 + reset boundary / effective budget / post-step guard 필드를 trace/gate artifact에 기록
- [x] **Step 3:** GREEN 확인

### Task A2: post-reset tail 제외 규칙

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py` (기존 `v0_6f_reset_boundary_diagnosis` 재사용)
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [x] **Step 1: RED 테스트** — `test_v06g_post_reset_rows_excluded_from_convergence_and_regression`: step 148에 reset-like jump가 있는 합성 trace에서, 제외 적용 시 regression_detected=false / 제외 미적용 시 true가 되는 케이스로 차이를 단언. `test_v06g_exclusion_is_recorded_in_artifact`: `post_reset_rows_excluded=true`와 jump step이 gate artifact에 기록됨을 단언.
- [x] **Step 2:** 기존 jump 감지 helper를 진단 계산 앞단에 연결 (첫 jump 이후 row 절단)
- [x] **Step 3:** GREEN + 전체 회귀

### Task A3: repair probe 재실행 (storage 경로) 및 재판정

- [x] **Step 1:** capture preflight + repair probe 실행 (출력은 storage 기본 경로, evidence manifest 자동 생성):

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --train-generation-probe-only --repair-probe-only \
  --repair-probe-controller-version v0_6f \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

- [x] **Step 2:** 결과 분기 (pre-registered):

```text
16042: pass 유지 기대 (회귀 시 Phase A 변경 자체를 재검토)
16096: post-reset 제외 후 재판정
  → regression 소멸 + last_K_median <= approach band → non-seated converged (green 요건 충족)
  → regression이 진짜로 잔존 → Phase B에 controller 결함으로 이관
16023: budget 절단만으로는 fail 유지 예상 (도착 step147 > seat_deadline≈137)
  → Phase B pacing 대상으로 확정
green이면 Phase C로 직행, 아니면 Phase B로
```

- [x] **Step 3:** worklog/Handoff 기록

### A3 실제 결과 (2026-06-12)

```text
repair_probe_gate_sha256=73a8148344374eeac4bc2abf751b61835fc65947431688bedf1005a7beb35207
green_light_for_40_run_gate=false
hard_stop=true
fixed_40_run_gate_opened=false
heldout_opened=false
reset_like_jump_count=0
post_reset_rows_excluded=false
```

분기 결과:

- `16042`: env-native 10-consecutive pass 유지.
- `16023`: lateral은 안정됐지만 `max_insertion_depth_m=0.022587`로 under-insertion. Phase B pacing 대상.
- `16096`: near band 안까지 수렴하지만 last-K regression이 남아 `non_seated_lateral_converged=false`. Phase B 변경 후 regression guard 재확인 필요.
- Phase C fixed 40-run gate는 아직 열지 않는다.

## Phase B: v0.6h — controller pacing (seat-by-deadline, 필요 시)

목적: `16023`처럼 **올바르게 수렴하지만 너무 늦게 도착**하는 케이스를
`seat_deadline_steps`(≈137) 안에 착좌하도록 전역 pacing을 조정한다.

허용 envelope (기존 동결 유지): global 값만 — ALIGN dwell 단축, DESCEND/INSERT
z-속도 상향(clip 내), approach_lateral_gate_m(0.001) 유지.
금지: per-seed 튜닝, 3-seed grid search, horizon/metric 변경, retry/search/withdraw/force,
held-out 접근.

Exit gate (pre-registered):

```text
repair_probe_green_light = true
  = 16023 env-native pass
    AND >=1 lateral seed env-native pass
    AND 모든 non-seated lateral seed가 converged/no-regression (post-reset 제외 적용 후)
global 변경 후 3-seed 전부 재실행 (regression guard: 기존 pass가 깨지면 invalid)
```

실패 시 escalation: 2회 pacing 시도 후에도 16023이 deadline을 못 맞추면 중단하고
controller 구조(접근 경로) 재진단 slice를 별도 spec으로 — envelope 완화로 풀지 않는다.

### Phase B 실제 결과 (2026-06-12)

```text
v0_6h:
  16023 pass
  16042 pass
  16096 non-seated / not converged

v0_6i:
  repair_probe_gate_sha256=5575361f9f542b02ea3c466baa07036a082fdb9373d9f112a2dee160b90bca4f
  green_light_for_40_run_gate=true
  hard_stop=false
  heldout_opened=false
```

분기 결과:

- `v0_6i` 전역 pacing/xy 설정에서 `16023`과 `16042`가 env-native
  10-consecutive success를 통과했다.
- `16096`은 full seat는 아니지만 last-K median lateral이 near band 안에
  유지되어 non-seated lateral converged로 판정됐다.
- repair probe green이므로 Phase C fixed 40-run gate로 진행 가능하다.

## Phase C: fixed 40-run train-generation gate

진입 조건: repair probe green. 실행 전 pre-register: stratified 40-subset seed id 목록
(config-difficulty cell 배분, 기존 규칙) hash 고정.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --train-generation-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

Pass gate (불변): **>=20/40 env-native 10-consecutive success**, 전 trace
storage/proof_evidence 보존.

실패 분기 (pre-registered): 실패 모드 분포를 post-reset 제외 적용 상태로 집계 →
지배 모드가 pacing이면 Phase B 재진입(전역값만), 새 모드면 진단 slice.
seed 교체/metric 완화/예산 증가 금지.

### Phase C 실제 결과 (2026-06-12)

```text
train_generation_runtime_gate.passed=true
runtime_backend=isaac_runtime
generated_rollout_count=40
generated_success_count=28
required_success_count=20
success_trace_cap=40
heldout_opened=false
```

분기 결과:

- fixed 40-run train-generation gate는 `28/40`으로 통과했다.
- `21000-21049` held-out은 열지 않았다.

## Phase D: train dataset 구축

- accepted: 40-run 통과 trace + (필요 시) 잔여 train_success seed(19000-19159)에서
  추가 생성 — 목표 accepted >= 30 episode.
- controlled failure: `19200-19359`에서 pre-registered taxonomy 분포로 생성.
- candidate view: curation gate 통과 accepted만. baseline view: pre-registered
  3:1 accepted:failure mix (`baseline_noise_mix_ratio=0.25`) — 결과를 보고 변경 금지.
- 산출: 양 HDF5 train view + `NormalizedTrajectoryContractValidator` 통과 contract
  + generator config hash 3종 + train_generation_runtime_gate.passed=true
  (`training_trajectory_source=isaac_runtime_scripted_expert_rollout`).

### Phase D 실제 결과 (2026-06-12)

```text
train_generation_runtime_backend=isaac_runtime
actual_isaac_success_trace_count=28
baseline_uncurated_train.hdf5 generated
candidate_curated_train.hdf5 generated
baseline_policy_artifact.json generated
candidate_policy_artifact.json generated
curation_manifest.json generated
contract_validation.passed=true
```

분기 결과:

- 기존 `train_generation_runtime_gate.json`을 재사용해 full build가 40-run을
  재실행하지 않도록 고정했다.
- pre-heldout gate가 완료되지 않았으므로 full build는 held-out schedule을
  열지 않는다.

## Phase E: policy 학습 + 표현력 sanity (최대 기술 리스크 게이트)

리스크: BC policy가 expert의 **gated 행동**(정렬 전 z=0 → 정렬 후 하강)을 재현하지
못하면 baseline/candidate 모두 0%가 되어 uplift가 정의상 불가능하다.

- 학습: baseline/candidate 동일 trainer/feature/hyperparameter (기존 fairness 불변).
  policy class 선택(`phase_conditioned_numpy_bc` vs 기존 `residual_servo_bc` 계열)과
  phase feature의 출처(depth 유도 vs controller state 기록)는 **학습 시작 전에**
  pre-register — 학습 후 변경 금지.
- **Expressibility sanity (신규 gate, 비-held-out)**: candidate policy를 train_success
  seed 5개(학습에 쓴 seed — 일반화가 아니라 표현력 검증)에서 rollout.
  pre-registered pass: **>=2/5 env-native success**. 미달이면 held-out은커녕
  calibration도 진행하지 않고 policy class/feature 재설계 slice로 회귀.

### Phase E 실제 결과 (2026-06-12)

```text
expressibility_sanity_gate.passed=false
runtime_backend=isaac_runtime
rollout_count=5
success_count=0
required_success_count=2
heldout_opened=false
heldout_21000_21049_accessed=false
reason=candidate policy did not pass train-split expressibility sanity.
expressibility_sanity_gate_sha256=99886c38a7e5012b69a63c628858e52a9c822ff0d1a27a99a8474c83eac76116
```

현재 blocker:

- candidate policy가 학습에 사용한 train-success seed 5개에서도 `0/5`이므로,
  지금 policy/trainer 조합은 expert의 gated behavior를 표현하지 못한다.
- 이 결과는 roadmap의 pre-registered stop rule에 따라 calibration과 held-out
  실행을 차단한다.
- 다음 valid step은 held-out을 열지 않고 candidate policy action output과 expert
  action/adapter target mismatch를 train-split trace에서 진단하거나, 새
  pre-registered policy/trainer slice를 작성하는 것이다.

## Phase F: calibration — adapter freeze + uplift pre-signal

- calibration seeds `20000-20029`에서 기존 selector(frozen score)로 adapter 선택·동결.
- **Uplift pre-signal (신규 go/no-go, pre-registered)**: 동결된 구성으로 baseline vs
  candidate를 calibration 30 seed에서 평가.

```text
go (held-out 개봉 허가):
  candidate_calibration_success > baseline_calibration_success
  AND candidate_calibration_success >= 0.30
no-go:
  held-out 미개봉. Phase D/E로 회귀해 새 slice (dataset 규모/policy class).
  calibration 결과를 보고 mix/threshold/selector를 바꾸는 것은 금지 —
  회귀는 항상 새 pre-registered slice 버전으로만.
```

근거: sealed held-out은 1회용 자원이다. uplift 신호가 calibration에서 전혀 없으면
held-out을 태우는 것은 낭비이고, 이 점검은 held-out을 건드리지 않으므로 무결성 무손상.

## Phase G: held-out A/B — 단 1회

개봉 전 체크리스트 (전부 충족 못 하면 개봉 금지):

```text
[ ] repair_probe_green_light=true (Phase B)
[ ] 40-run gate passed >=20/40 (Phase C)
[ ] train_generation_runtime_gate.passed=true (Phase D)
[ ] expressibility sanity passed (Phase E)
[ ] adapter/policy/hash 전부 동결 + calibration pre-signal go (Phase F)
[ ] 모든 증거 storage/proof_evidence + evidence_manifest 커밋
```

실행 (pre-register): held-out `21000-21049` **50 seed 전부**, 양 policy 각 50 rollouts,
단 1회. (50으로 close-minimum >=20과 stronger public target >=50을 동일 실행에서 충족.)

Closure 판정 (기존 frozen 규칙 그대로):

```text
mvp2_closed = runtime_backend=isaac_runtime AND 양 runtime gate pass
  AND calibration_only_selection_passed AND heldout_leakage_guard_passed
  AND actual_rollouts_per_policy >= 20
  AND validator learning_proven=true AND proof_eligible=true
  AND candidate_success_rate > baseline_success_rate
  AND curated_vs_uncurated_uplift >= 0.20
```

결과 분기:
- **양성** → MVP-2 Closed. Phase H로.
- **음성** → 정직한 non-closing report 보존. 어떤 retry도 **새 pre-registered
  slice + 새 held-out range**로만. `21000-21049` 결과로 어떤 것도 재튜닝 금지.

## Phase H: closure 후속

- `run_mvp1_proof_audit.py --mvp2-learning-proven-report ...`로 proof audit 통합,
  buyer artifacts(dataset card / trust record) 갱신 — non-claims 유지
  (privileged task-state, no real-robot/visual/HMD claims, 좁은 초기조건 분포 limitation 명시).
- 감사 Stage 2 unlock: mvp2b/2c 공통 로직 `services/proof/` 추출, thin CLI화,
  테스트 일반 import 전환 ("동일 입력→동일 artifact hash" 회귀로 검증).
- MVP-1/1+ 분량 main 선머지 후 MVP-2 브랜치 PR (커밋/push는 사용자 승인 필수).
- worklog/Handoff 슬라이스 아카이브 회전, fixture provenance 정정.

---

## Risk register

| # | 리스크 | 완화 |
|---|---|---|
| R1 | BC가 gated 행동을 표현 못 함 (최대) | Phase E expressibility gate가 held-out 전에 차단; residual servo BC 대안 pre-register |
| R2 | uplift < 0.20 | Phase F calibration pre-signal로 sealed held-out 보호; 음성도 valid evidence |
| R3 | pacing 수정이 40-run에서 일반화 실패 | Phase C 실패 분기 pre-registered; seed/metric 불변 |
| R4 | 증거 소실 재발 | storage 기본 경로 + manifest 강제 (Phase A부터 적용 확인) |
| R5 | proof-경로 리팩토링이 hash 체인 파괴 | Stage 1은 hash-불변 골든 테스트 선행, Stage 2는 Phase H로 동결 |

## 금지선 (전 phase 공통)

- held-out `21000-21049`는 Phase G 체크리스트 전 개봉 금지, 결과 본 후 재튜닝 금지
- env-native success authority / `stable_steps=10` / `max_steps=150` 변경 금지
- horizon 증가 금지 (Phase A의 예산 절단은 감소이므로 허용)
- per-seed 튜닝, 3-probe-seed grid search 금지
- deterministic/proxy/fixture 증거로 closure 금지
- git commit/push는 매번 사용자 명시 승인 후에만
