# MVP-2 Auditability Verifier — Phase 3 TASKS

Spec: `docs/superpowers/specs/2026-06-17-mvp2-auditability-verifier-spec.md` (APPROVED)
Date: 2026-06-17
Branch: `codex/mvp2-learning-proven-uplift`

> TDD 규율: C2/C3는 **테스트 선행**. 각 구현 태스크 앞에 RED 테스트 태스크가 온다.
> 커밋/푸시는 CLAUDE.md GitHub 통제에 따라 **명시 승인 시에만**. 각 태스크는 로컬 검증까지.

## C1a 실측 source map (확정)

복사본 무결성 리스크는 **해소됨**: 기존 manifest 8개 파일은 byte-exact 복사 시 `file_sha256` 일치(OK).

`data/` 최종 = **11개 파일**:

| # | data/ 파일 | storage 원본 | 해시 규약 | 상태 |
|---|-----------|-------------|----------|------|
| 1 | baseline_external_rollouts.json | …/external_rollouts/ | file-bytes | 기존 manifest OK |
| 2 | candidate_external_rollouts.json | …/external_rollouts/ | file-bytes | 기존 manifest OK |
| 3 | heldout_closure_gate_v0_14.json | …/ | file-bytes | 기존 manifest OK |
| 4 | calibration_presignal_gate_v0_14.json | …/ | file-bytes | 기존 manifest OK |
| 5 | v0_14_comparator_provenance_row_balance_gate.json | …/ | file-bytes | 기존 manifest OK |
| 6 | v0_14_row_balance_report.json | …/ | file-bytes | 기존 manifest OK |
| 7 | v0_14_source_provenance_report.json | …/ | file-bytes | 기존 manifest OK |
| 8 | mvp2_learning_proven_report.json | …/mvp2_learning_proven_policy_eval/ | file-bytes | 기존 manifest OK |
| 9 | v0_14_comparator_provenance_row_balance_manifest.json | …/ | file-bytes | manifest엔 있으나 data/ 목록에 누락됐던 것 → 추가 |
| 10 | baseline_policy_artifact_v0_14.json | …/ | **canonical-payload (excl self)** | **신규** (manifest에 없음) |
| 11 | candidate_policy_artifact_v0_14.json | …/ | **canonical-payload (excl self)** | **신규** (manifest에 없음) |

제외 결정:
- `root_evidence_manifest` (evidence_manifest.json, 686KB, cross-slice 글로벌) → **data/ 미포함**.
  사유: spent/closure 사실은 `package_manifest.json`(이미 git) + `heldout_closure_gate`(data/ #3)에
  이미 존재. 686KB 글로벌 파일은 verdict 번들에 noise. manifest엔 provenance 포인터로만 유지.

두 해시 규약 (실측 확정):
```text
file-bytes:        sha256(open(path,'rb').read())                       # 9개 (#1–9)
canonical-payload: sha256(stable_json({k:v for k,v in d.items()         # 정책 2개 (#10–11)
                          if k != "policy_artifact_sha256"}))
  stable_json = json.dumps(d, ensure_ascii=False, sort_keys=True, indent=2)
```
cross-check (실측 MATCH): `policy.policy_artifact_sha256 == rollout.policy_artifact_sha256`
→ rollout이 바로 그 정책에서 나왔음을 묶는다.

번들 총량 실측: ~284KB (< 1MB).

---

## Task 1 — C1a: source map + manifest 수정안 확정 (문서)

- [ ] **Acceptance:** 위 11-file source map + 2 해시 규약 + root_manifest 제외 결정이
      spec/tasks에 박힘. manifest 수정 항목 목록 완성(경로 data/ 화, 정책 2개 신규 entry,
      `seed_ranges`, `package_audit_ci_seed=20260617`, Level C 5필드).
      **spec 갱신 포함:** spec의 Project Structure data/ 목록이 10개로 보이면 11개로 교정
      (comparator_manifest 추가, 정책 2개 명시). 최종 기준 = **data/ = 11 files**.
- [ ] **Verify:** 본 문서의 source map 표가 실측치와 일치(이미 측정 완료);
      `grep -c "data/ = 11\|11 files" spec` 으로 spec/tasks 일치 확인.
- [ ] **Files:** 이 tasks 문서, `docs/superpowers/specs/2026-06-17-mvp2-auditability-verifier-spec.md` (코드 없음).

## Task 2 — C1b: bundle 무결성 RED 테스트

- [ ] **Acceptance:** `test_verify_mvp2_package.py`에 bundle-integrity 테스트가 RED로 존재 —
      (a) data/ 11개 파일 존재, (b) #1–9 file-bytes sha256 == manifest `file_sha256`,
      (c) #10–11 canonical-payload 해시 == policy 자기선언 == rollout 선언.
      현재 data/ 부재이므로 실패해야 정상.
- [ ] **Verify:** `uv run pytest apps/api/tests/test_verify_mvp2_package.py -k integrity -q` → FAIL(수집·실행되며 data 부재로 red).
- [ ] **Files:** `apps/api/tests/test_verify_mvp2_package.py`.

## Task 3 — C1b: byte-exact copy + manifest 보강 → GREEN

- [ ] **Acceptance:** storage 원본 11개를 `docs/proof/mvp2_learning_proven_evidence_package/data/`로
      복사. `package_manifest.json` 보강: artifact_index 경로 data/ 화, 정책 2개 신규 entry
      (`hash_convention=canonical_payload_excluding_self`), `seed_ranges` 블록
      (train/calibration=39000-39029/heldout=40000-40049/pre_closure_burned[]/post_closure_spent[]),
      `package_audit_ci_seed=20260617`, Level C 5필드
      (`trace_count_expected=100`, `per_trace_sha256[]`, `trace_tarball_sha256`,
      `trace_tarball_status=out_of_band_not_required_for_level_b`, `deep_verification_mode=optional`).
      **기존 file-bytes 9개 sha256 불변(#1–9, comparator_manifest 포함) + 정책 2개(#10–11)는
      canonical-payload hash 신규 추가.** `trace_tarball_sha256`는 hosting 미결정이므로
      placeholder 금지 — `null` + `trace_tarball_status=out_of_band_not_required_for_level_b`.
- [ ] **Verify:** Task 2 테스트 GREEN. `python -m json.tool package_manifest.json`.
- [ ] **Files:** `data/*` (11), `package_manifest.json`. (코드 0)

## Task 4 — C2: verifier hard-check RED 테스트 (9 + advisory)

- [ ] **Acceptance:** `verify_mvp2_package` 모듈을 import해 실제 bundle에 돌리는 테스트가 RED —
      green-case(exit 0, uplift 0.70 재계산) + 11 hard-check 각 단언 + advisory CI 보고 단언.
      (hardening 후 추가: manifest_claim_consistency, audit_ci_seed_pinned,
       --deep level_c_trace_consistency hash-lock)
      모듈 미존재로 실패해야 정상. forbidden claims는 **8종** 명시:
      `real_robot_success, physical_robot_readiness, hmd_openxr_readiness, visual_policy_performance,
      deployable_real_robot_policy, universal_robot_support, marketplace_readiness, production_certification`.
- [ ] **Verify:** `pytest -k "verifier_green or hard_check" -q` → FAIL (ImportError/미구현).
- [ ] **Files:** `apps/api/tests/test_verify_mvp2_package.py`.

## Task 5 — C2: verifier 코어 구현 (Level A/B) → GREEN

- [ ] **Acceptance:** `scripts/verify_mvp2_package.py` (stdlib-only) 구현. 11 hard-check:
      1 hash(두 규약 + rollout↔policy binding), 2 rate(5/50,40/50), 3 uplift(0.70),
      4 threshold(≥0.20), 5 label B(`success==(avail AND consec≥10)`), 6 closure(mvp2_closed,
      policy_uplift_proven, rollouts==50), 7 disjointness(pre-closure ∩=∅, scenario_id∈[40000,40049] unique),
      8 spent/no-reuse(post-closure), 9 forbidden 8종 false. + advisory package-audit CI
      (seed 20260617, 관측 라벨 with-replacement 재표본, quantile `sorted[floor(p*(n-1))]`).
      구조화 리포트 + 최종 VERDICT + exit code.
- [ ] **Verify:** Task 4 테스트 GREEN. 실제 실행 exit 0. `uvx ruff check scripts/verify_mvp2_package.py`.
- [ ] **Files:** `scripts/verify_mvp2_package.py`.

## Task 6 — C3: Level C RED 테스트

- [ ] **Acceptance:** 합성 trace fixture로 RED — mask 10-consecutive → max_consecutive 재유도==10;
      mask가 record와 모순 → `--deep` FAIL; trace 부재 → Level B는 통과하고 coverage=0/100 보고.
- [ ] **Verify:** `pytest -k level_c -q` → FAIL.
- [ ] **Files:** `apps/api/tests/test_verify_mvp2_package.py` (+ 합성 fixture, 인라인 생성).

## Task 7 — C3: Level C `--deep` 구현 → GREEN

- [ ] **Acceptance:** `--deep --traces-dir` 시 각 로컬 trace의 `env_native_success_mask`에서
      최장 consecutive run 재유도, rollout record의 `env_native_max_consecutive_success_steps`와 대조,
      coverage(n/100) 보고. trace 부재 시 Level B 결과 불변.
- [ ] **Verify:** Task 6 GREEN. 실제 trace dir로 `--deep` 100/100 일치(로컬에 trace 있을 때).
- [ ] **Files:** `scripts/verify_mvp2_package.py`.

## Task 8 — C4: tamper matrix + import guard 완성

- [ ] **Acceptance:** 7 tamper 케이스 각각 exit≠0 — (1) candidate success true→false,
      (2) data 파일 1바이트 변조, (3) max_consecutive 10→9 (success 유지),
      (4) held-out 40005를 calibration range 주입, (5) non_claims.real_robot_success→true,
      (6) uplift 0.19 시나리오, (7) **rollout의 policy_artifact_sha256 한 글자 변경 →
      rollout↔policy binding FAIL**. + import-guard: verifier가 stdlib 외 import 0개(ast 단언).
      tamper fixture는 원본 불변(임시 복사본에 변조).
- [ ] **Verify:** `pytest apps/api/tests/test_verify_mvp2_package.py -q` 전체 GREEN(6 tamper가 fail을 단언).
- [ ] **Files:** `apps/api/tests/test_verify_mvp2_package.py`.

## Task 9 — C5: 패키지 문서 갱신 (C2 인터페이스 확정 후 병렬 가능)

- [ ] **Acceptance:** README에 `git clone → python3 scripts/verify_mvp2_package.py <manifest>` 절차.
      claims_and_limitations에 two-CI nuance(0.56/0.82 seedless vs 0.56/0.84 seed=23, 섞지 않음,
      audit CI는 retroactive replace 아님) + n=1 disclosure. evidence_index/repro를 data/ 경로로 갱신.
- [ ] **Verify:** `rg`로 forbidden true-claim 0; 두 CI 별개 표기 확인; 링크 경로 유효.
- [ ] **Files:** (4개)
      `docs/proof/mvp2_learning_proven_evidence_package/README.md`,
      `docs/proof/mvp2_learning_proven_evidence_package/claims_and_limitations.md`,
      `docs/proof/mvp2_learning_proven_evidence_package/evidence_index.md`,
      `docs/proof/mvp2_learning_proven_evidence_package/reproducibility_and_review_notes.md`.

## Task 10 — C6: CI 워크플로

- [ ] **Acceptance:** 신규 `.github/workflows/ci.yml` — uv setup → `python3 scripts/verify_mvp2_package.py`
      (Level B) → `uv run pytest -q` → `uvx ruff check scripts apps/api`. push/PR 트리거.
      주의: `-m "not isaac"`는 marker 미정의 시 흔들리므로 **현재는 `uv run pytest -q`로 명확화**.
      Isaac-heavy 테스트가 실제 존재하면 먼저 pytest config에 `isaac` marker를 정의한 뒤
      `-m "not isaac"`로 전환(별도 선행 단계).
- [ ] **Verify:** 로컬에서 동일 3 명령 green; data/ 파일 1바이트 변조 시 verifier step fail 모의 확인.
- [ ] **Files:** `.github/workflows/ci.yml`.

---

## 의존 그래프

```text
T1(C1a doc) → T2(C1b RED) → T3(C1b GREEN: bundle+manifest)
                                  → T4(C2 RED) → T5(C2 impl)
                                       → T6(C3 RED) → T7(C3 impl)
                                       → T8(C4 tamper+guard)
                                       → T9(C5 docs)            [T5 후 병렬]
                                            → T10(C6 CI)        [T5/T8 안정 후]
```

## 전역 수용 (Phase 4 IMPLEMENT 완료 기준)

- [ ] clean clone + `python3 scripts/verify_mvp2_package.py <manifest>` (Isaac 0) → exit 0, uplift 0.70 재계산
- [ ] 7 tamper 전부 exit≠0 (policy binding 포함)
- [ ] CI가 매 push verifier Level B 실행; data/ 변조 시 fail
- [ ] `--deep` 100/100 일치 (로컬 trace 시)
- [ ] 문서 two-CI 별개 + n=1 disclose; verifier stdlib-only(guard 통과)
