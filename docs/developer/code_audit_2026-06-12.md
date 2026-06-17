# Robot Data Forge 코드베이스 감사 보고서

Date: 2026-06-12
Scope: 전체 repo (scripts, apps/api, tests, docs, 증거 artifact, git 상태)
Method: 실측 기반 (wc/grep/git/artifact 검사). 추측 발견 없음 — 모든 항목에 측정 근거를 병기.

## 종합 평가

- 강점: proof-integrity **프로세스**는 우수하다. pre-registered manifest, fail-closed gate,
  env-native success authority, held-out 봉인, anti-p-hacking 가드, 119 passed 테스트,
  ruff/compileall 클린.
- 약점: proof **물증 보존**과 **코드 구조**가 프로세스 수준을 따라가지 못한다.
  실제로 2026-06-12 재부팅으로 모든 actual-Isaac 증거가 이미 소실됐다.
- 한 문장: "증명 규율은 1급, 증거 보관과 코드 형상은 부채 누적 상태."

---

## 발견 사항

### P0 — 즉시 (증거/자산 보존)

#### A-1. 모든 actual-Isaac proof 증거가 /tmp에 있다가 소실됨 (이미 발생)

측정:

```text
ls -d /tmp/rdf-*           → 0개 (2026-06-11까지 30+개 존재)
uptime -s                  → 2026-06-12 09:36:34 (재부팅)
find storage -iname "*v0_6*" -o -iname "*mvp2e*"  → 없음
```

소실된 것:

- v0.5 train-gate 40개 trace (5/40 근거, lateral 실패 분포 원본)
- v0.6a chamfer/capture preflight artifact
- v0.6b–e repair probe trace (16023/16042/16096 env-native 판정 원본)
- 모든 viability JSON (`rdf-mvp2c-factory-viability` 등)

영향:

- `Handoff.md` / `docs/developer/worklog.md`의 증거 경로가 전부 dangling pointer.
- 의사결정 요약(수치)은 문서에 인용돼 남았으나 **원본 trace 재검은 Isaac 재실행 없이는 불가**.
- v0.6e에서 측정한 numeric `capture_radius_m`가 repo 문서에 수치로 기록돼 있지 않다면
  v0.6g 전에 capture probe **재실행 필요**.

조치 (Stage 0):

1. 모든 proof runner의 기본 `--output-dir`을 `/tmp/...` → `storage/proof_evidence/<slice>/`로 변경.
2. slice별 `evidence_manifest.json` (파일 목록 + sha256 + 생성 커맨드)을 **git 추적** —
   대형 trace는 storage(gitignored)에 두되 manifest로 무결성/존재를 증명.
3. 과거 /tmp 증거는 "lost on 2026-06-12 reboot; decisions stand on recorded summaries"로
   worklog에 정직하게 기록. 소급 재구성/재연출 금지.
4. 40-run gate와 held-out A/B는 **반드시** 이 보존 체계 위에서만 실행.

#### A-2. Handoff.md가 gitignored — 인계 상태 문서가 버전 관리 밖

측정: `git check-ignore Handoff.md` → ignored (`.gitignore:35`), `storage/`도 ignored.

영향: 디스크 장애/오삭제 = 프로젝트 상태 기억 상실. A-1과 결합하면 단일 머신이
proof 체인 전체의 단일 장애점.

조치: Handoff.md를 추적 전환하거나, 최소한 슬라이스 종료마다
`docs/developer/handoff_snapshots/`로 스냅샷 커밋.

#### A-3. CI 부재

측정: `.github/workflows/` 없음.

영향: 119개 테스트가 로컬 수동 실행에만 의존. 회귀가 커밋 시점에 잡히지 않음.

조치: pytest(비-Isaac) + ruff + compileall만 도는 최소 GitHub Actions 1개.
Isaac 의존 테스트는 marker로 skip.

### P1 — 구조 (proof 일정과 동기화해 처리; 아래 "리팩토링 동결 원칙" 참조)

#### B-1. `run_mvp2c_isaac_training_calibration.py` 5,266줄 monolith

측정: 5,266줄 (2026-06-11 세션 시작 시 2,257줄 → 하루 만에 2.3배).
scenario manifest(34개 `scenario_profile ==` 분기), controller, capture probe,
gate 5종, HDF5 view, policy 학습, validator bridge, CLI가 한 파일.

영향: v0.6f/g처럼 slice가 늘 때마다 같은 파일이 비대화. 리뷰/회귀 범위가 전 파일.

#### B-2. mvp2b ↔ mvp2c 결합 + 중복

측정: `scripts/`는 패키지가 아님(`__init__.py` 없음). mvp2c가 `sys.path.insert` 후
`from run_mvp2b_isaac_proof_evaluator import ...` (line 37–46).
동일 이름 top-level 함수 **27개**가 양쪽에 중복 정의
(`_scenario_row`, `_heldout_suite`, `_contract_for_trajectory` 등).

영향: 어느 정의가 실행되는지 추적 비용. 한쪽만 고치는 partial-fix 버그 표면.
실제로 이번 세션의 `_phase_from_depth`/phase vocabulary 혼선도 이 이중 정의 구조와 동근.

#### B-3. 테스트 24/33개 파일이 importlib 경로 로딩

측정: `spec_from_file_location` 사용 파일 24개.

영향: 모듈 캐시 분리로 동일 모듈 다중 로드, coverage 추적 불가, IDE 점프/리네임 불가.

#### B-4. scenario profile sprawl (코드 하드코딩)

측정: v0_1…v0_6 seed range가 if-chain으로 하드코딩, `scenario_profile ==` 34회.

영향: 새 slice = 코드 수정 = proof-frozen 파일에 diff. 데이터(JSON registry)로
분리하면 slice 추가가 코드 무변경이 됨.

#### B-5. `apps/api/app/services/evaluator.py` 1,579줄

services 레이어에도 같은 비대화 패턴 진행 중.

#### B-6. 거대 단일 브랜치

측정: `codex/mvp2-learning-proven-uplift`가 main 대비 15 커밋, 미머지.
MVP-2B~2E 전체가 한 브랜치에 누적.

영향: 리뷰 단위 비대, main이 5주 전 상태. MVP-1/1+ Closed 성과도 main에 없음.

### P2 — 위생

#### C-1. 컨텍스트 문서 비대

측정: `worklog.md` 12,928줄, `Handoff.md` 3,829줄, `tasks/todo.md` 1,766줄.
"압축 인계 문서"가 스스로 컨텍스트 한도를 초과. 슬라이스 종료마다 아카이브 회전 필요.

#### C-2. 합성 fixture의 provenance 라벨 모호

측정: `storage/mvp1_readiness/raw/trajectories/traj_success_a.json` —
`source.input_device=quest3_handtracking`, `source.runtime=steamvr_openxr`인데
실체는 `control_mode=offline_fixture_operator_follow` 합성 fixture.
buyer-trust 제품에서 source 라벨과 실체의 불일치는 신뢰 리스크.
조치: `source.input_device=offline_fixture` 계열로 정정하거나
`source.fixture=true` 최상위 필드 추가.

#### C-3. 테스트 파일 비대

측정: `test_teleop_diagnostics_scripts.py` 2,765줄, `test_mvp2c_...py` 2,503줄.

#### C-4. legacy 표면 미분리

`mvp1c_*`, HMD/teleop 스크립트는 정책상 보존 대상이나, `scripts/legacy/` 또는
명시적 "compatibility surface" 디렉토리로 분리해 현행 proof 경로와 시각적으로 구분 권장.

---

## 리팩토링 동결 원칙 (가장 중요한 CTO 판단)

**40-run train-generation gate와 held-out A/B 실행 전에는 proof-경로 코드
(run_mvp2b/2c, controller, manifest 생성)를 구조 변경하지 않는다.**

이유:

1. pre-registered hash 체인(scenario manifest, controller config, selector config)이
   코드 동작에 결합돼 있어 리팩토링이 hash/동작 동등성을 깨면 pre-registration이 무효가 된다.
2. held-out 직전의 대규모 diff는 "결과를 보고 코드를 바꿨다"는 의심 표면을 만든다.
3. 따라서 구조 개선(Stage 2)은 slice 경계에서, 가능하면 MVP-2 Close 후에 수행한다.
   Stage 0(증거 보존)과 Stage 1(데이터 분리)은 동작 무변경이므로 예외.

---

## 단계별 개선 계획

### Stage 0 — 지금 즉시, v0.6f/g와 병행 (반나절) : 증거 보존

- [ ] proof runner 기본 output-dir을 `storage/proof_evidence/<slice>/`로 변경
- [ ] `evidence_manifest.json` (sha256 + 재현 커맨드) 생성 로직 추가, git 추적
- [ ] /tmp 증거 소실 사실을 worklog에 기록 (소급 재구성 금지)
- [ ] v0.6e numeric capture_radius가 repo 문서에 없으면 capture probe 재실행으로 재확보
- [ ] Handoff 스냅샷 정책 (A-2)
- [ ] 최소 CI 1본 (A-3) — pytest(비-Isaac) + ruff + compileall

수용 기준: 다음 Isaac 실행부터 모든 증거가 재부팅 생존 + manifest 검증 가능.

### Stage 1 — v0.6g spec과 같은 slice 경계 (1일) : profile 데이터화

- [ ] `scenario_profiles.json`으로 v0_1…v0_6f seed range/metric/excluded 이전
- [ ] if-chain 제거, 로더 함수 1개로 대체
- [ ] 회귀 보증: 기존 profile별 `manifest_sha256`가 변경 전후 동일함을 테스트로 고정

수용 기준: 신규 slice 추가가 JSON 1건 추가로 끝남. 기존 hash 전부 불변.

### Stage 2 — 40-run gate 통과 후 ~ held-out 전 금지, 권장은 MVP-2 Close 후 (2–3일) : proof runner 분해

- [ ] 공유 로직을 `apps/api/app/services/proof/` 패키지로 추출:
      trace 평가, action adapter, HDF5 train view, BC policy, gate 파생, rollout JSON
- [ ] `run_mvp2b/2c`는 thin CLI(인자 파싱 + 조립)로 축소, 27개 중복 함수 단일화
- [ ] 테스트 importlib 로딩 → 일반 import 전환 (B-3)
- [ ] 동등성 보증: "동일 입력 → 동일 artifact sha256" 회귀 테스트로 추출 검증

수용 기준: mvp2b/2c 각 500줄 이하 CLI, 중복 함수 0, coverage 측정 가능.

### Stage 3 — MVP-2 Close 후 (지속) : 위생

- [ ] worklog/Handoff 슬라이스별 아카이브 회전 (C-1)
- [ ] fixture provenance 정정 (C-2)
- [ ] legacy 표면 분리 (C-4)
- [ ] `evaluator.py` 책임 분해 (B-5)
- [ ] main 머지 전략: MVP-1/1+ Closed 분량을 먼저 PR로 분리 머지 (B-6)
- [ ] 테스트 파일 분할 (C-3)

---

## 하지 말 것

- held-out 21000-21049 봉인 해제 전 proof-경로 구조 변경
- 증거 소실을 이유로 metric/threshold/green rule 재논의 (소실은 보존 실패지 판정 무효가 아님)
- 소실된 trace의 소급 재구성·재연출 (재실행은 새 증거로만 기록)
- 리팩토링과 proof 실행을 같은 diff에 섞기
