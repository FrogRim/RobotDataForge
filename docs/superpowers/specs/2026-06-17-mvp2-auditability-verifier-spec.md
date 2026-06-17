# Spec: MVP-2 Auditability — Self-Verifying Closure Bundle + Independent Verifier

Date: 2026-06-17
Status: APPROVED (human review 2026-06-17) — Phase 2 PLAN in progress
Branch: `codex/mvp2-learning-proven-uplift`

## Objective

MVP-2는 이미 Closed다 (held-out 40000–40049, 50 rollouts/policy, uplift 0.70).
그러나 증명물은 **신뢰 가능한 자산**이 아직 아니다. 핵심 결함은 *self-attestation*이다:

- `docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json`은 git에 있고
  10개 artifact의 `file_sha256`를 나열한다.
- 그러나 그 10개 파일은 전부 `storage/proof_evidence/**` = **gitignored**. 외부 감사자가
  repo를 clone하면 해시를 대조할 **파일이 없다**. 결국 "FrogRim 머신의 파일이 진짜고
  조작 안 됐다"를 **믿어야** 한다 — 이 제품(robot data **trust** layer)이 없애려는 바로 그 신뢰.

**이 작업의 목표:** 외부 감사자가 우리를 신뢰하지 않고, Isaac 없이, 단 한 번의 `git clone`만으로
closure 판정을 **독립 재계산**할 수 있게 만든다.

성공의 모습:
```
git clone <repo>
python3 scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json
→ 30초, Isaac 0, 신뢰 0
→ baseline 5/50 = 0.10, candidate 40/50 = 0.80, uplift 0.70 (>= 0.20), mvp2_closed=true
→ VERDICT: VERIFIED (exit 0)
```

비목표 (scope 밖, 명시적 제외):
- held-out 40000–40049 재개봉 / Isaac 재실행 / 재튜닝 — 일절 없음. 순수 패키징 + 검증 도구.
- 과거 슬라이스(v0.6~v0.13) 소급 패키징 — v0.14 closure 단 하나만 대상.
- n=1 robustness 보강(추가 held-out band, 복수 run) — 별도 작업. 단, verifier는 n=1과 CI를
  **정직하게 disclose**한다 (숨기지 않음 = auditability 요건).
- 통계적 재검정 / 새 CI를 closure gate로 승격 — 금지.

## 검증 모델 (Recompute, 3-depth)

각 rollout 레코드에 이미 들어있는 필드와 trace의 per-step mask를 활용한 3개 깊이:

| 레벨 | 재계산 | 신뢰하는 것 | 데이터 | 기본/옵션 |
|------|--------|------------|--------|-----------|
| A (rate) | rate·uplift·disjointness·hash | 각 rollout의 `success` bool | small JSON bundle | 포함 |
| **B (label)** | 추가로 `success == (env_native_max_consecutive_success_steps >= 10)` 재유도 | 기록된 consecutive count | same bundle (추가 0) | **기본** |
| C (mask) | 추가로 148-step `env_native_success_mask`에서 consecutive count 자체를 재유도 | 아무것도 (env가 쓴 per-step mask까지 내려감) | +large traces (100 files) | `--deep` |

데이터 번들은 **small git-tracked JSON bundle, expected < 1MB** (data/ = 11개 JSON; formatting 변동으로
정확 byte 크기는 약속하지 않는다). `env_native_max_consecutive_success_steps`가 이미 이 번들 안에
있으므로 **Level B는 무거운 trace 없이 공짜로 가능**하다. Level C trace(100 files, 수십~수백 MB)만
out-of-band로 둔다.

## Confidence Interval 처리 (정직한 disclosure)

두 개의 서로 다른 CI가 존재하며 **섞으면 안 된다**:

```
closure gate  (heldout_closure_gate_v0_14.json):
  confidence_interval_report = { method: bootstrap_success_rate_difference,
                                 iterations: 2000, lower: 0.56, upper: 0.82 }
  → RNG seed 미기록 → bit-reproducible 아님

learning report (mvp2_learning_proven_report.json):
  confidence_interval_95 = { method: deterministic_bootstrap,
                             iterations: 2000, seed: 23, lower: 0.56, upper: 0.84 }
  → seed=23 기록 → 재현 가능, 그러나 closure gate CI와 별개의 값
```

Spec 규칙 (문구 고정):

> Closure decision is deterministic and does not depend on bootstrap CI.
>
> The original closure gate CI [0.56, 0.82] is retained as historical reported
> evidence, but it is not bit-reproducible because the RNG seed was not recorded.
>
> The verifier recomputes a separate package-audit CI with an explicit fixed seed.
> That recomputed CI is audit evidence, not a retroactive replacement for the
> original closure gate CI.

따라서 CI는 **hard closure gate가 아니라 disclosed probabilistic audit field**다. verifier는
package-audit CI를 명시적 고정 seed(`package_audit_ci_seed`, manifest에 기록)로 재계산해 자기
값으로 보고하고, 원본 두 CI를 별개로 표기하되 어느 것도 재작성하지 않는다.

package-audit CI 알고리즘 (재현성을 위해 seed만이 아니라 알고리즘까지 고정):

```text
rng = random.Random(20260617)              # package_audit_ci_seed
iterations = 2000
# baseline successes 와 candidate successes 를 각각 with-replacement 재표본
for _ in range(iterations):
    b = [rng.random() < baseline_rate  for _ in range(baseline_rollouts)]   # 또는 관측 라벨 재표본
    c = [rng.random() < candidate_rate for _ in range(candidate_rollouts)]
    statistic = mean(c) - mean(b)          # candidate_success_rate - baseline_success_rate
quantile convention = sorted(samples)[floor(p * (n - 1))]   # p ∈ {0.025, 0.975}
reported package-audit CI is advisory only (NOT a hard gate, NOT a replacement for either original CI)
```

구현 주의: "관측 라벨을 with-replacement 재표본"이 통계적으로 정확하다(베르누이 모수 가정 회피).
verifier는 각 policy의 관측 success/failure 라벨 리스트(rollout_results에서 추출)를 직접 재표본한다.
위 의사코드의 `rng.random() < rate`는 동등한 대안 표기일 뿐이며, **실제 구현은 관측 라벨 재표본으로
고정**한다. 어느 쪽이든 seed/iterations/quantile convention이 명시되어 결정적이다.

## Hard-Fail 판정 기준 (전부 결정적 — RNG 없음)

verifier가 비-zero로 종료해야 하는 조건 (하나라도 깨지면 FAIL):

```
1. hash match        : data/ 각 파일 sha256 == package_manifest.artifact_index[].file_sha256
2. rate              : baseline sum(success)=5 → 5/50=0.10 ; candidate=40 → 40/50=0.80
3. uplift            : candidate_rate - baseline_rate == 0.70
4. threshold         : uplift >= 0.20
5. label (Level B)   : ∀ rollout, success == (env_native_success_available
                       AND env_native_max_consecutive_success_steps >= 10)
6. closure verdict   : mvp2_closed == true ; policy_uplift_proven == true
                       ; actual_rollouts_per_policy == 50
7. seed disjointness : held-out 40000-40049 is disjoint from train / calibration 39000-39029 /
                       pre-existing burned ranges BEFORE closure (∩ = ∅)
                       ; 모든 rollout scenario_id ∈ [40000,40049] 이고 unique
8. spent/no-reuse    : AFTER closure, 40000-40049가 spent/audit-only/no-reuse로 기록됨 —
                       spent_heldout_ranges에 40000-40049 spent
                       ; future_closure_reuse_allowed=false
                       ; same_heldout_reuse_allowed_for_closure=false
                       (주의: post-closure spent를 pre-closure disjointness 위반으로 오판하지 말 것)
9. forbidden claims  : non_claims의 8종 전부 false —
                       real_robot_success, physical_robot_readiness, hmd_openxr_readiness,
                       visual_policy_performance, deployable_real_robot_policy,
                       universal_robot_support, marketplace_readiness, production_certification
10. manifest claim   : manifest.claim.heldout_closure(successes/rollouts/rates/absolute_uplift)가
                       recomputed와 일치 ; claim.mvp2_closed==gate.mvp2_closed==true ;
                       claim.policy_uplift_proven==true (사람이 읽는 claim 블록의 drift 차단)
11. audit ci seed    : manifest.package_audit_ci_seed == 20260617 (고정 seed 강제)
--deep 추가 hard-check (trace 있을 때):
   level_c_hashlock          : per_trace_sha256 비어있지 않음 ; len==trace_count_expected==100 ;
                               rollout trace 이름 set == manifest hash 이름 set (map 제거/부분/drift 차단)
   level_c_trace_consistency : present trace마다 sha256(bytes)==manifest.per_trace_sha256[name]
                               (hash-lock; 항목 부재도 contradiction) AND mask→consecutive 재유도==record
```

advisory (NOT hard-fail, 보고만):
```
A. package-audit CI : 고정 seed로 재계산, [lower,upper] 보고, 원본 두 CI와 별개로 표기
C. Level C coverage : --deep 시 로컬 trace n/100에서 mask→consecutive 재유도 일치 여부
```

## Tech Stack

- Python 3.11+, **stdlib only** (verifier): `json`, `hashlib`, `random`, `argparse`, `pathlib`,
  `math`, `re`, `dataclasses`, `sys` 등 표준 라이브러리만. numpy/scipy/h5py 등 서드파티 금지 —
  감사자가 bare `python3`로 실행 가능해야 함. import-guard 테스트가 `sys.stdlib_module_names`로 강제.
- 테스트: pytest (`apps/api/tests/`).
- CI: GitHub Actions.

## Commands

```bash
# 검증 (Level B, 기본 — 오프라인, ~30초)
python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json

# 검증 (Level C deep — 로컬 trace 있을 때)
python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json \
  --deep --traces-dir storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/isaac_runtime_fresh_heldout_v0_14/isaac_runtime_heldout_rollout_traces

# 테스트
uv run pytest apps/api/tests/test_verify_mvp2_package.py -q

# 린트
uvx ruff check scripts/verify_mvp2_package.py
```

## Project Structure

```
docs/proof/mvp2_learning_proven_evidence_package/
  README.md                              # (수정) verify 사용법 추가
  claims_and_limitations.md              # (수정) two-CI nuance + n=1 disclosure
  evidence_index.md                      # (수정) data/ 경로 반영
  reproducibility_and_review_notes.md    # (수정) clone→verify 절차
  v0_14_comparator_provenance_row_balance_appendix.md
  package_manifest.json                  # (수정) data/ 경로화 + disjointness ranges
                                         #        + package_audit_ci_seed + trace hashes
  data/                                  # (신규) 판정-임계 번들 git 추적 (small JSON, <1MB) — data/ = 11 files
    # file-bytes sha256 (9개, 기존 manifest file_sha256 불변):
    baseline_external_rollouts.json
    candidate_external_rollouts.json
    heldout_closure_gate_v0_14.json
    calibration_presignal_gate_v0_14.json
    v0_14_comparator_provenance_row_balance_gate.json
    v0_14_comparator_provenance_row_balance_manifest.json   # comparator_manifest (추가)
    v0_14_row_balance_report.json
    v0_14_source_provenance_report.json
    mvp2_learning_proven_report.json
    # canonical-payload sha256 excl self (2개, 신규 manifest entry):
    baseline_policy_artifact_v0_14.json
    candidate_policy_artifact_v0_14.json
scripts/verify_mvp2_package.py           # (신규) stdlib-only verifier
apps/api/tests/test_verify_mvp2_package.py  # (신규) green + tamper 테스트
.github/workflows/ci.yml                 # (신규/확장) verifier Level B 실행
```

원본은 `storage/proof_evidence/**`에 그대로 둔다(provenance 소스). `data/`는 그 동결 복사본이며,
복사본↔원본 동일성은 sha256로 보증한다(같은 해시 = 위치 무관).

## Code Style

verifier는 한 함수 = 한 체크. 각 체크는 `(name, passed: bool, detail: str)` 형태 결과를 반환.

```python
def check_rate_recompute(rollouts: list[dict], claimed: dict) -> CheckResult:
    """baseline/candidate 성공률을 raw rollout에서 재계산해 claim과 대조."""
    successes = sum(1 for r in rollouts if r["success"])
    total = len(rollouts)
    rate = successes / total
    ok = (successes == claimed["successes"]) and abs(rate - claimed["rate"]) < 1e-9
    return CheckResult("rate_recompute", ok,
                       f"recomputed {successes}/{total}={rate:.2f} vs claimed "
                       f"{claimed['successes']}/{claimed['rollouts']}={claimed['rate']:.2f}")
```

규칙: f-string, 명시적 비교, `1e-9` 허용오차는 float rate 비교에만(정수 카운트는 정확 비교).
어떤 체크도 예외를 삼키지 않는다 — 파싱 실패는 그 자체로 FAIL.

## Testing Strategy

framework: pytest. 위치: `apps/api/tests/test_verify_mvp2_package.py`.

```
green case:
  - 실제 data/ 번들 → exit 0, 모든 hard 체크 PASS, uplift 0.70 재계산
tamper cases (각각 verifier가 FAIL해야 함 — rubber stamp 아님 증명):
  - candidate rollout 1개 success true→false 변조 → rate/label FAIL
  - data/ 파일 1개 1바이트 변조 → hash FAIL
  - rollout 1개 max_consecutive 10→9 (success=true 유지) → label FAIL
  - held-out seed 40005를 calibration range에 주입 → disjointness FAIL
  - non_claims.real_robot_success false→true → forbidden-claims FAIL
  - uplift 0.70→0.19 시나리오 → threshold FAIL
Level C:
  - 합성 trace mask 10-consecutive → max_consecutive 재유도 == 10
  - mask가 record의 consecutive와 모순 → --deep FAIL
guard:
  - verifier가 stdlib 외 import 0개 (ast 파싱으로 단언)
```

coverage 기대: verifier의 모든 hard 체크 함수가 green 1 + tamper 1 이상으로 커버.

## Boundaries

- **Always:**
  - hard 체크는 정수/유리수로 정확 비교(rate float만 1e-9 허용오차).
  - verifier stdlib-only 유지.
  - non-claims 8종 보존.
  - 커밋 전 `pytest` + `ruff` 통과.
  - 두 CI를 항상 별개로 표기.
- **Ask first:**
  - `git commit` / `push` (CLAUDE.md GitHub 통제 — 명시 승인 필수).
  - `package_manifest.json`의 기존 해시/경로 수정.
  - `data/`로 artifact 복사(= proof 증거를 git에 추가).
  - `.github/workflows/ci.yml` 신규/변경.
- **Never:**
  - held-out 40000–40049 재개봉 / Isaac 재실행 / 재튜닝.
  - closure gate CI seed를 소급 기록하거나 두 CI를 합치기.
  - 112MB trace를 git에 커밋.
  - verifier 체크를 재계산 없이 pass 처리.
  - hard-fail 기준을 verifier를 통과시키려고 완화.

## Success Criteria

```
[ ] clean 머신 git clone + python3 scripts/verify_mvp2_package.py <manifest> (Isaac 없음)
    → exit 0, baseline 5/50, candidate 40/50, uplift 0.70, mvp2_closed=true 재계산 출력
[ ] 6종 tamper 케이스 각각 verifier exit 비-zero
[ ] CI가 매 push에서 verifier Level B 실행 ; data/ 파일 변조 시 CI fail
[ ] --deep가 로컬 trace에서 mask→consecutive 재유도, 100/100 일치 보고
[ ] 문서가 두 CI를 별개로 명시 + closure 판정이 CI 비의존임을 명시 + n=1 disclose
[ ] hard-fail 11기준 전부 코드로 강제 + 테스트로 커버 (+ --deep trace hash-lock)
[ ] verifier stdlib-only (import guard 테스트 통과)
```

## Resolved Decisions (human review 2026-06-17)

1. **package-audit CI seed = `20260617`**, 알고리즘까지 위 "Confidence Interval 처리"에 고정.
   manifest `package_audit_ci_seed`에 기록.
2. **Level C trace 회수 = tarball + manifest hash-lock**, 호스팅 미결정(이 슬라이스 충분).
   manifest에 아래 필드 필수:
   ```text
   trace_count_expected = 100
   per_trace_sha256[]                                    # 100개 파일별 sha256
   trace_tarball_sha256                                  # 단일 tarball 해시
   trace_tarball_status = out_of_band_not_required_for_level_b
   deep_verification_mode = optional
   ```
3. **CI = 신규 `.github/workflows/ci.yml`** (P0 A-3 해소)에 verifier Level B job +
   비-Isaac pytest + ruff 합류 (로드맵 Phase 0 Task 0.1과 통합). 전체 pytest ~24초로 부담 낮음.
   `uv` setup 단계를 명확히 기술.

## Manifest 수정 사항 (Phase 2에서 상세화)

`package_manifest.json`에 추가/변경:
- `artifact_index[].path`를 `data/` 상대 경로로 (또는 `data_path` 필드 병기).
- `seed_ranges` 블록: `train`, `calibration=39000-39029`, `heldout=40000-40049`,
  `pre_closure_burned[]` (disjointness 입력), `post_closure_spent[]`.
- `package_audit_ci_seed = 20260617`.
- Level C 필드 5종(위 Resolved Decisions #2).
- 기존 `artifact_index[].file_sha256`는 **불변** — 복사본이 동일 해시를 가져야 하므로
  복사 후 재계산이 아니라 기존 해시와 일치 검증 (불일치 시 복사 오류로 FAIL).
