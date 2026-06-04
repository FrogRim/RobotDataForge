# 프론트엔드 계획

이 문서는 #18.13~#18.17 프론트엔드 구현 범위를 추적한다.

주요 목표:

```text
디버깅과 operator review를 위해 backend data flow를 노출한다.
Marketing site를 만들지 않는다.
Mock task를 primary path로 만들지 않는다.
```

구현 대상 page:

```text
/              overview와 현재 phase
/tasks         task list
/tasks/[id]    task detail
/play/[id]     collection session status와 recorder command
/episodes/[id] trajectory replay/debug view
/admin         KPI dashboard
/datasets      dataset export와 download
```

구현 규칙:

```text
Frontend는 `apps/web/lib/api.ts`를 통해 FastAPI backend를 호출한다.
API를 사용할 수 없으면 page는 명시적인 empty/error state를 표시한다.
```

## 구현 상태

구현 완료:

```text
/              phase overview와 navigation
/tasks         API-backed task list
/tasks/[id]    task detail과 task episode list
/play/[id]     collection session status와 operator command
/episodes/[id] episode detail과 trajectory summary
/admin         `/api/admin/kpis`의 #24 KPI group
/datasets      dataset list와 export contract note
```

추가된 shared frontend module:

```text
apps/web/lib/api.ts
apps/web/lib/types.ts
apps/web/lib/trajectory.ts
apps/web/components/common/*
apps/web/components/dashboard/KpiSection.tsx
apps/web/components/replay/TrajectorySummary.tsx
```

검증:

```bash
cd ~/robot-data-forge
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web audit --audit-level=moderate
```

알려진 이슈:

```text
2026-05-28 기준 `npm --prefix apps/web audit --audit-level=moderate`는 0 vulnerabilities다.
`npm audit fix --force`는 Next major downgrade/upgrade 위험이 있으므로 기본 디버깅 흐름에서 사용하지 않는다.
```

## 최종 배포 UX 방향 — 2026-05-28

RDF의 최종 제품은 내부 개발툴만이 아니라, HMD 보유자가 데이터를 넣을 수 있는 `Collector App/Web`을 포함해야 한다.

단, MVP 범위에서는 marketplace, 결제, 보상, production auth, 실제 로봇 제어를 구현하지 않는다. 최종 배포 방향은 아래 순서로 제한한다.

```text
1. Local-first PC Collector Launcher
   - ALVR / SteamVR/OpenXR / Isaac Lab / RDF recorder preflight
   - handtracking quality gate
   - task run / recording / finalize 제어

2. HMD Operator Panel
   - RECENTER OK
   - RECORDING ON
   - tracking stable/unstable
   - task guidance
   - rejected reason의 쉬운 안내

3. Web Dashboard
   - episode 목록
   - quality score
   - accepted/rejected reason
   - curation manifest
   - dataset export 상태

4. Controlled Lab Pilot
   - 제한된 HMD 보유자나 연구실에 배포
   - data quality, operator UX, export artifact 검증

5. Post-MVP Networked Data Factory
   - 여러 collector에서 만든 데이터를 중앙 manifest로 모음
   - 결제/보상/marketplace는 별도 post-MVP 의사결정
```

웹만으로 primary collection을 대체하지 않는다. 현재 primary path는 Quest 3 + ALVR + SteamVR/OpenXR + Isaac Lab + local recorder이므로, 웹은 상태판/검수판이고 실제 runtime 실행은 PC collector가 담당한다.

이 방향은 `docs/MVP_PROGRESS_OVERVIEW.html`의 “최종 제품 그림” 섹션에 반영되어 있다.

## MVP 진행판 하위페이지 — Teleop 입력 신호 리서치 — 2026-05-28

`docs/MVP_PROGRESS_OVERVIEW.html`의 하위 페이지로 `docs/MVP_TELEOP_INPUT_STREAM_RESEARCH.html`을 추가했다.
이 페이지는 최신 `raw-wrist-direct` 실행 로그와 `../developer/papers/2026_teleop_input_stream_accuracy.md`의 리서치 결론을 중학생도 이해할 수 있게 정리한다.

반영 범위:

```text
- 최신 blocker 숫자: tracking_loss_rate, right_hand_tracked_rate, valid-to-valid wrist jump
- Wi-Fi/ALVR 원인 여부: 단독 범인으로 단정하지 않고 추가 계측 필요로 설명
- red flag 조절 방향: 완화가 아니라 validity/outlier/reacquire gate 강화
- 다음 구현 후보: collection preflight, OpenXR provenance, One Euro Filter A/B
```

상위 `docs/MVP_PROGRESS_OVERVIEW.html`에는 하위 페이지 링크를 추가했다. 이 작업은 정적 문서/UX 설명이며, Next.js 앱 route나 FastAPI contract 변경은 아니다.

## MVP 진행판 하위페이지 — HMD 실증 전 입력 게이트 강화 — 2026-05-28

`docs/MVP_PROGRESS_OVERVIEW.html`의 두 번째 하위 페이지로 `docs/MVP_PRE_HMD_STEP1_INPUT_GATES.html`을 추가한다.
이 페이지는 실제 HMD 실증 테스트를 다시 실행하기 전에 끝낸 방어선 구현을 설명한다.

반영 범위:

```text
- evaluator: RAW_WRIST_JUMP data-quality gate
- IsaacLab teleop: first_valid_hand recenter stable right-wrist window
- HMD axis debug script: 15-frame warmup/recenter 기본값
- 검증: RED/GREEN pytest, broad pytest, py_compile, bash -n, HTML parse, patch reverse-check
```

이 페이지도 정적 문서이며 Next.js route를 추가하지 않는다. 실제 운영 dashboard에 반영하는 작업은 별도 frontend step으로 분리한다.

## Frontend lint/build 검증 경로 — 2026-05-28

`apps/web`는 non-interactive 환경에서 `next lint`를 사용하지 않는다. Next.js 15 앱은 명시적 ESLint CLI 구성으로 검증한다.

현재 scripts:

```json
{
  "lint": "eslint .",
  "build": "next build"
}
```

현재 검증 명령:

```bash
cd ~/robot-data-forge
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web audit --audit-level=moderate
```

결정:

- `eslint.config.mjs`는 `next/core-web-vitals`와 `next/typescript`를 사용한다.
- 내부 route navigation은 `next/link`를 사용한다.
- `postcss` transitive advisory는 `overrides.postcss=^8.5.10`로 고정한다.
- `npm audit fix --force`는 major downgrade/upgrade 위험이 있으므로 기본 디버깅 흐름에서 사용하지 않는다.
