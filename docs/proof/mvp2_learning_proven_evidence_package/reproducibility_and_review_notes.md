# Reproducibility And Review Notes

이 문서는 외부 기술 검토자가 v0.14 MVP-2 package를 재현하거나 리뷰할 때 따라야
하는 최소 절차를 정리한다.

## Reproduction Command

원래 closure artifact는 Isaac runtime path에서 아래 형태로 생성됐다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_14 \
  --comparator-provenance-row-balance-runtime \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

현재 root manifest가 `40000-40049`를 spent로 기록하므로 같은 output directory에
동일 closure를 다시 실행하면 runtime guard가 fail closed해야 한다. 재현 목적의
새 실행은 새 output directory와 새 held-out range를 사용해야 한다.

## Fresh-Clone Reproduction Record (2026-06-18)

clone-only 재현을 실제로 수행했다. 별도 디렉토리에 `git clone`한 뒤(working tree
잔여물 없이 커밋된 내용만), 프로젝트 의존성 없이 bare `python3`로 verifier를 돌렸다.

```text
clone branch HEAD                         : 1ba43c0
clone 내 storage/ tracked 파일            : 3 (proof_evidence README + mvp2b/mvp2c 작은 manifest)
clone 내 v0_14 closure 디렉토리 tracked   : 0  ← 실제 closure 증거/trace는 gitignored
clone 내 Level C per-step trace           : 0  (--deep coverage 0/100 missing)
verifier Level B 결과                     : VERIFIED (11 hard-check, exit 0)
```

즉 판정은 **오직 git-tracked `data/` 번들**에서 재계산됐고, fresh clone에는 v0_14
storage artifact도 per-step trace도 존재하지 않는다. 이는 self-attestation 갭이
닫혔음을 end-to-end로 보인다. 단, **별도 물리 머신** 재현은 아직 open gap이다
(`package_manifest.json`의 `review_gaps`와 `clone_only_reproduction` 참조).

## Independent Recompute Verification (1차 경로, Isaac 불필요)

외부 감사자가 우리를 신뢰하지 않고 closure 판정을 독립 재계산하는 가장 강한 경로다.
판정-임계 artifact는 `data/`에 git-tracked 사본으로 포함되므로 clone 한 번이면 된다.

```bash
# Level B (기본, 오프라인, stdlib-only)
python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json

# Level C (out-of-band per-step trace가 로컬에 있을 때)
python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json \
  --deep --traces-dir <isaac_runtime_heldout_rollout_traces dir>
```

verifier는 12개 hard-check를 raw rollout 기록에서 재계산한다: hash 무결성(file-bytes
10개 + policy canonical 2개 + rollout↔policy binding), rate(baseline 5/50, candidate
40/50), uplift(0.70), threshold(>=0.20), label(success==consecutive>=10),
closure(`mvp2_closed`/`policy_uplift_proven`/50), seed disjointness(held-out
40000-40049가 leakage-guard 전 channel과 disjoint), spent/no-reuse, forbidden-claims
8종, non-claims-attestation(8종 전부 hash-locked·gate-bound 증서), manifest-claim-
consistency(사람이 읽는 manifest claim 블록이 recomputed/gate와 일치),
audit-ci-seed-pinned(`package_audit_ci_seed==20260617`). `--deep`는 추가로
per-trace sha256 hash-lock + per-step mask consecutive 재유도를 검증한다.
`VERDICT: VERIFIED` + exit 0이면 독립 검증 통과다. 어떤 artifact·manifest claim·trace
hash를 변조하면 해당 hard-check가 fail한다(이 동작은
`apps/api/tests/test_verify_mvp2_package.py`의 tamper matrix로 회귀 보호된다).

## Level C Trace Tarball (out-of-band, hash-locked + reproducible)

100개 per-step Isaac trace는 git에 담기엔 크므로 out-of-band 단일 tarball로 묶고
manifest에 sha256만 hash-lock한다(`level_c_traces.trace_tarball_sha256`). 그 해시가
의미를 가지려면 tarball이 byte-재현 가능해야 하므로 결정적 빌더를 쓴다(정렬된 이름,
정규화된 tar 메타데이터, gzip mtime=0).

```bash
# trace를 가진 사람은 동일 tarball + 동일 sha256를 재생성할 수 있다
python3 scripts/build_mvp2_trace_tarball.py \
  <isaac_runtime_heldout_rollout_traces dir> <out.tar.gz>
# → sha256가 manifest.level_c_traces.trace_tarball_sha256와 일치해야 함

# 받은 tarball 무결성 확인은 표준 도구로 충분
sha256sum <out.tar.gz>   # == manifest.level_c_traces.trace_tarball_sha256
```

tarball을 풀면 `--deep` 검증 입력이 된다(per-trace sha256 hash-lock + per-step mask
consecutive 재유도). tarball hosting 위치는 별도 결정 사항이며, 무결성 anchor(sha256)와
재생성 recipe는 manifest에 고정돼 있다.

## Local Verification Commands

패키지 작성 시 사용한 self-review 명령이다.

```bash
rg -n "5 / 30|26 / 30|5 / 50|40 / 50|\\+0\\.70|\\[0\\.56, 0\\.82\\]|40000-40049|Isaac held-out evaluator domain|real robot|HMD/OpenXR|visual policy|deployable" \
  docs/proof/mvp2_learning_proven_evidence_package
```

```bash
rg -n "TB[D]|TO[D]O|real robot success[=]true|hmd_openxr_readiness[=]true|visual_policy_performance[=]true|deployable_real_robot_policy[=]true|future_tuning_allowed[=]true|future_closure_reuse_allowed[=]true" \
  docs/proof/mvp2_learning_proven_evidence_package docs/developer/worklog.md Handoff.md
```

```bash
python -m json.tool \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json \
  >/tmp/rdf_mvp2_package_manifest.validated.json
```

```bash
git diff --check
```

## Review Checklist

리뷰어는 아래 순서로 확인하는 것이 좋다.

1. `evidence_manifest.json`에서 `mvp2_closed=true`,
   `policy_uplift_proven=true`, `same_heldout_reuse_allowed_for_closure=false`,
   `spent_heldout_ranges`를 확인한다.
2. `heldout_closure_gate_v0_14.json`에서 baseline `5 / 50`, candidate
   `40 / 50`, uplift `+0.70`, CI `[0.56, 0.82]`를 확인한다.
3. `calibration_presignal_gate_v0_14.json`에서 held-out을 열기 전 calibration
   pre-signal baseline `5 / 30`, candidate `26 / 30`을 확인한다.
4. `v0_14_comparator_provenance_row_balance_gate.json`에서 held-out access가
   false인 상태로 comparator fairness gate가 통과했는지 확인한다.
5. `v0_14_row_balance_report.json`에서 failure material ratio `0.5`,
   duplicate failure rows disallowed, failure-to-success row ratio `1.0`을
   확인한다.
6. `mvp2_learning_proven_report.json`에서 `evidence_tier`,
   `proof_eligible`, policy provenance, non-claim boundary를 확인한다.

## Codex-Assisted Process

이번 package freeze는 Codex를 사용해 진행했다.

- Codex가 로컬 JSON artifact를 읽고 수치와 SHA-256을 추출했다.
- Codex가 external reviewer용 문서 구조를 작성했다.
- Codex가 `40000-40049` spent held-out rule과 non-claim boundary를 문서 전반에
  반복 고정했다.
- Codex가 `rg`, `python -m json.tool`, `git diff --check` 검증을 실행했다.

Codex 사용은 문서화와 검증 보조에 한정된다. Proof claim은 artifact와 test
evidence가 뒷받침해야 하며, Codex 텍스트 자체는 authority가 아니다.

## Known Review Gaps

- 별도 machine에서 third-party full reproduction은 아직 수행하지 않았다.
- 이 package 작성 단계에서 live Isaac rerun은 수행하지 않았다.
- legal/commercial due diligence는 수행하지 않았다.
- real robot, HMD/OpenXR, visual policy, deployable policy claim은 scope 밖이다.
