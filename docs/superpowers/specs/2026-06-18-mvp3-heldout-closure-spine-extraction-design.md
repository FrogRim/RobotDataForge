# Spec: Held-Out / Closure Integrity Spine Extraction (MVP-3 enabler)

Date: 2026-06-18
Status: APPROVED (brainstorm 2026-06-18) — writing-plans next
Branch: `codex/mvp3-heldout-closure-spine`

## Objective

MVP-3는 **source/task expansion** 단계다: fresh held-out robustness를 유지하면서 새
task + 새 data source/adapter를 붙여 proof package를 **반복 생성**한다. 그 반복의
불변 축(task/source-agnostic spine) 중 **fork하기 가장 위험한 한 조각** —
held-out/closure 무결성 — 을 archive를 건드리지 않고 clean 모듈로 forward 추출한다.

`run_mvp2c_isaac_training_calibration.py`(36,540줄, 638 함수)는 v0.6~v0.14 proof
history를 품은 **append-only archive**다. `mvp2-v0.14-*` tag가 그 위에 "어느 커밋 =
어느 proof" 추적성을 박았다. 이 archive는 **동결**한다 — 전면 분해/historical slice
모듈화/대규모 rewrite는 하지 않는다. 대신 MVP-3가 반복 사용할 무결성 spine의
계약만 깨끗하게 빼낸다.

성공의 모습:
```
새 (task, source)로 proof package를 만들 때, 개발자는 run_mvp2c를 fork하지 않고
services/proof/ 스파인을 import해 seed 규율·leakage guard·closure 판정을 재사용한다.
golden 테스트는 v0.14 archive가 실제로 저장한 closure verdict 필드와 일치함을
검증하고, 8-gate boolean은 새 spine에서 재구성해 모두 true임을 확인한다. 단,
`heldout_closure_gate_v0_14.json`에는 per-gate boolean이 저장되어 있지 않으므로
per-gate artifact identity를 주장하지 않는다.
```

비목표 (명시적 제외):
- `run_mvp2c_isaac_training_calibration.py` 수정/분해/모듈 import 주입 — 일절 없음.
- v0.6~v0.13 slice 로직 추출·모듈화 — archive에 남긴다.
- 검증된 proof artifact(가치·해시·claim boundary) 의미 변경 — 금지.
- MVP-3 task/source adapter 실제 구현 — 이번 slice는 **spine만**.
- train view / BC policy / rollout 생성 / evidence manifest 배관 추출 — 후속 sub-project.
- `verify_mvp2_package.py`와 코드 공유 — 금지(아래 독립성 원칙).

## 추출 대상의 실측 계약 (archive에서)

`derive_mvp2c_closure`의 8-gate AND (run_mvp2c line 30910):
```text
1 train_runtime_matches            ← "isaac_runtime" / training source 문자열 하드코딩
2 heldout_runtime_matches          ← ISAAC_PROOF_RUNTIME 하드코딩
3 calibration_selection_matches    ← calibration_only_selection_passed
4 heldout_leakage_matches          ← heldout_leakage_guard.passed
5 actual_train_trace_count_matches ← count >= trace_minimum
6 post_heldout_guard_matches       ← post_heldout_guard passed (또는 None)
7 learning_matches                 ← uplift >= 0.20 AND candidate > baseline
                                      AND uplift == candidate - baseline
8 rollout_count_matches            ← >= MIN_PROOF_ROLLOUTS_PER_POLICY
close_minimum = all 8 AND
```
**핵심**: gate 1·2만 Isaac 상수에 묶여 있다. 나머지(leakage 집합 로직, count/uplift/
rollout 임계, AND 구조)는 이미 agnostic. 따라서 추출은 **Isaac 상수를 파라미터로
들어올리는 것**이지 로직 재설계가 아니다. 임계값(0.20, MIN_PROOF_ROLLOUTS_PER_POLICY,
trace minimum)은 v0.14 값을 default로 둔 파라미터로 노출한다.

## Tech Stack

- Python 3.11+. 새 모듈은 `apps/api/app/services/proof/` 패키지(일반 import →
  importlib 부채 회피). 순수 로직(seed 집합 + AND gate)이라 numpy/h5py 불필요.
- 타입: **Pydantic 모델** (services/schemas 지배 스타일 — BaseModel 9 files vs
  dataclass 5; `normalized_trajectory_contract.py`·`proof_evidence.py` 등 기존
  proof 인프라와 일관). Proof-affecting boolean, numeric, threshold, and seed
  range fields are strict/fail-closed so truthy strings, numeric booleans, and
  coerced seed endpoints cannot become proof evidence.
- 테스트: pytest (`apps/api/tests/`).

## Project Structure

```
apps/api/app/services/proof/
  __init__.py
  contracts.py        # SeedRangeConfig, RuntimeExpectations, ClosureThresholds,
                      #   GateInputs, ClosureVerdict, LeakageReport 등 입력/출력 타입
  seed_discipline.py  # recorded seed-range validation + configured spent/no-reuse rejection
  leakage_guard.py    # held-out ∩ (train ∪ calibration ∪ pre-closure burned) = ∅
                      #   (leakage-guard channel에서 burned set 파생, scenario_id 검사)
  closure.py          # derive_closure(): 8-gate AND, Isaac 상수는
                      #   RuntimeExpectations 파라미터로 주입.
                      #   missing success-trace count는 MVP-3 reuse를 위해 fail-closed.
apps/api/tests/
  test_proof_spine_closure.py       # gate 단위 + golden(v0.14 일치) + 파라미터화
  test_proof_spine_leakage.py       # disjointness 위반/통과 + channel 파생
  test_proof_spine_seed_discipline.py
```

## Code Style

순수 함수, 한 함수 = 한 책임. Isaac 상수는 파라미터로 주입(하드코딩 금지).

```python
def derive_closure(
    gate_inputs: GateInputs,
    runtime: RuntimeExpectations,      # expected backend/proof_runtime/training_source
    thresholds: ClosureThresholds,     # uplift_min=0.20, min_rollouts, trace_min (v0.14 defaults)
) -> ClosureVerdict:
    """8-gate AND. Returns reconstructed per-gate booleans, closed verdict, and blockers.
    Artifact-level closure fields are golden-pinned to v0.14 archive output; per-gate
    booleans are reconstructed because the archive artifact does not store them."""
    train_runtime_matches = (
        gate_inputs.train_runtime_gate_passed
        and gate_inputs.train_runtime_backend == runtime.backend
        and gate_inputs.training_trajectory_source == runtime.training_source
    )
    ...
    closed = all([train_runtime_matches, heldout_runtime_matches, ...])
    return ClosureVerdict(closed=closed, gates={...}, blockers=[...])
```

## Testing Strategy

framework: pytest. 위치 `apps/api/tests/`.

```text
golden (안전망 — 가장 중요):
  - v0.14 기록 입력(data/ + storage artifact)에서 derive_closure →
    mvp2_closed, mvp2c_close_minimum_passed, proof_eligible, learning_proven,
    blockers가 archive output과 artifact-level로 일치
  - 새 spine이 8-gate boolean을 재구성해 모두 true임을 확인하되,
    heldout_closure_gate_v0_14.json과 per-gate identity를 주장하지 않음
  - leakage_guard(v0.14 입력) → passed, burned/held-out disjoint 가 기록과 일치
unit:
  - 각 gate가 단독으로 false면 closed=false (8개 음성 케이스)
  - uplift 0.19 → learning_matches false; rollouts 19 → rollout_count_matches false
  - uplift와 candidate-baseline rate difference 불일치 → learning_matches false
  - truthy string/int boolean evidence, bool/string seed endpoints, invalid
    thresholds reject at contract boundary
  - leakage: held-out seed를 burned에 주입 → disjointness 위반
  - leakage: empty held-out set → fail-closed
  - seed_discipline: 범위 겹침/spent 재사용 시 reject
parameterization:
  - RuntimeExpectations를 non-Isaac 값으로 줘도 동일 AND 로직 동작
    (task/source-agnostic 입증)
independence:
  - 스파인은 verify_mvp2_package를 import하지 않는다 (ast 가드 또는 grep 테스트)
```

## Boundaries

- **Always:**
  - archive(`run_mvp2c`) 무수정. 새 모듈은 독립.
  - golden 동치(archive가 저장한 closure verdict 필드와 일치) 유지 —
    깨지면 추출 로직 오류로 간주.
  - Isaac 상수는 파라미터, 임계는 v0.14 default 파라미터.
  - 커밋 전 pytest + ruff.
- **Ask first:**
  - `git commit` / `push` / PR (CLAUDE.md GitHub 통제).
  - Pydantic vs dataclass 최종 선택이 기존 services 패턴과 충돌하면 확인.
- **Never:**
  - `run_mvp2c`/`run_mvp2b` 수정하거나 새 모듈을 거기서 import.
  - proof artifact 의미/해시/claim boundary 변경.
  - 스파인과 `verify_mvp2_package` 코드 공유 (독립성 파괴).
  - v0.6~v0.13 slice 로직을 이번에 추출.

## Success Criteria

```text
[ ] apps/api/app/services/proof/ 스파인 모듈 (seed/leakage/closure) 존재, 일반 import
[ ] derive_closure가 v0.14 기록 입력에서 archive output의
    mvp2_closed, mvp2c_close_minimum_passed, proof_eligible, learning_proven,
    blockers와 일치하고, 재구성한 8-gate가 모두 true (golden 통과)
[ ] leakage_guard가 v0.14 입력에서 기록된 disjointness 결과 재현
[ ] leakage_guard가 empty held-out set을 evidence missing으로 보고 fail-closed 처리
[ ] proof-affecting booleans, numeric evidence, thresholds, seed ranges가 strict
    validation으로 coercion을 거부
[ ] learning_matches가 reported uplift와 candidate-baseline rate difference의
    내부 일관성을 검증
[ ] Isaac 상수 0개 하드코딩 — RuntimeExpectations로 주입; non-Isaac 값으로도 동작
[ ] 스파인이 verify_mvp2_package를 import하지 않음 (독립성 가드 통과)
[ ] run_mvp2c/run_mvp2b 무수정 (git diff에 archive 변경 0)
[ ] 단위 + golden + 파라미터화 테스트 통과, ruff clean
```

## 독립성 원칙 (재강조)

스파인(producer)과 `verify_mvp2_package`(독립 auditor)는 **같은 계약을 공유하되 코드는
공유하지 않는다.** verifier의 존재 이유가 "독립적 제2 증인"이므로 코드 공유는 그 가치를
파괴한다. golden 테스트가 "두 구현 모두 v0.14 archive와 일치"를 증명함으로써 둘의 합의를
보인다. 미래에 둘이 어긋나면 그것이 곧 회귀 신호다.

## Resolved Scope Decisions

1. **seed_discipline 범위** — 이번 추출은 recorded seed range validation과
   configured spent/no-reuse rejection까지만 한다. 새 seed range 자동 할당기는
   MVP-3가 실제 pre-registration automation을 요구할 때 후속 slice로 다룬다.
2. **contract 타입** — Pydantic을 사용한다. 기존 services 패턴과 맞춘다.
