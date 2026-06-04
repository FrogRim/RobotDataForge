# Next Issues

작성일: 2026-05-04

이 문서는 Notion 또는 GitHub issue로 옮기기 위한 작업 후보 목록이다.

## 현재 상태 요약

```text
MVP-0 implementation: 완료
MVP-0 live smoke validation: 완료
MVP-0 quantitative Go Criteria: 미완료
Next blocker: Teleop UX / calibration mismatch
```

현재 backend/data pipeline은 동작한다. 다음 작업은 더 많은 기능 추가가 아니라 success trajectory를 만들 수 있는 조작 환경을 확보하는 것이다.

---

## Issue 1. MVP-0 Smoke Validation Completed

Type:

```text
Documentation / Milestone
```

Summary:

```text
Quest/OpenXR/Isaac Lab 기반 Robot Data Forge MVP-0 live smoke validation을 완료 상태로 고정한다.
```

Evidence:

- `P/N/F/R` lifecycle command 동작
- trajectory/evaluation/usability 생성
- dataset export/card 생성
- task reuse 확인
- scoped KPI filter 확인

Acceptance Criteria:

- `docs/MVP0_SMOKE_VALIDATION_REPORT.md` 존재
- `docs/DATA_COLLECTION_LOG.md`에 live run 기록 존재
- MVP-0 smoke complete와 quantitative Go Criteria 미완료가 명확히 구분됨

Status:

```text
Done
```

---

## Issue 2. Improve Quest/OpenXR Teleop Workspace Calibration

Type:

```text
MVP-0 blocker / UX / Data quality
```

Summary:

```text
Quest handtracking workspace와 Isaac robot workspace의 시점/좌표계 mismatch를 줄인다.
```

Why:

- 현재 task_success_rate와 accepted_trajectory_rate가 0이다.
- 사용자가 실제 조작에서 큰 불편함을 보고했다.
- success trajectory가 나오지 않으면 MVP-0 quantitative validation과 MVP-1로 넘어갈 수 없다.

Scope:

- recenter behavior 개선
- neutral pose capture
- rotation-aware alignment metadata
- translation/gain/smoothing parameter
- calibration event logging
- UX validation checklist

Out of Scope:

- real robot control
- CloudXR
- replay UI
- behavior cloning

Acceptance Criteria:

- `P` recenter 후 조작 방향이 직관적으로 맞는다.
- calibration metadata에 translation, rotation/gain이 남는다.
- 20 episode smoke run에서 `task_success_rate > 0.0` 또는 최소 intentional success-like trajectory가 나온다.
- 기존 API tests 통과.

Suggested PR:

```text
PR: Improve Quest/OpenXR teleop workspace calibration for MVP-0 collection
```

Priority:

```text
P0
```

---

## Issue 3. Add Sync Error Measurement

Type:

```text
Data quality / ForgeSync
```

Summary:

```text
XR input timestamp, Isaac simulation timestamp, recorder timestamp 사이의 sync_error_ms를 frame metadata에 기록한다.
```

Why:

- 현재 scoped KPI에서 `sync_error_ms_mean=null`, `sync_error_ms_p95=null`이다.
- timestamp alignment는 robot learning dataset 신뢰성의 핵심이다.

Scope:

- recorder timestamp source 정의
- frame metadata에 `timestamp_source`, `recorder_timestamp`, `sim_timestamp`, optional `xr_timestamp` 기록
- 가능한 경우 `sync_error_ms` 계산
- unavailable이면 warning 유지

Acceptance Criteria:

- `sync_error_ms_mean`이 measured value로 표시된다.
- 측정 불가능한 경우 명확히 unavailable로 남는다.
- 기존 trajectory schema reader가 깨지지 않는다.

Priority:

```text
P1
```

---

## Issue 4. Add Action Phase Metadata

Type:

```text
Evaluation / Segmentation / QA
```

Summary:

```text
Trajectory frame에 action_phase metadata를 추가해 APPROACH/ALIGN/CONTACT 등 segment가 UNKNOWN으로만 남지 않게 한다.
```

Why:

- 현재 `ActionSegment` structure는 있으나 live data에서는 `UNKNOWN` 위주다.
- 실패 원인을 phase 단위로 분석하려면 phase metadata가 필요하다.

Scope:

- recorder 또는 evaluator heuristic에서 `action_phase` 후보 생성
- 최소 초기 phase:
  - APPROACH
  - ALIGN
  - CONTACT
  - STABILIZE
  - UNKNOWN
- segment confidence 기록

Acceptance Criteria:

- live trajectory에서 UNKNOWN이 아닌 segment가 생성된다.
- segment source와 confidence가 저장된다.
- failure analysis에서 phase별 reason을 연결할 수 있다.

Priority:

```text
P1
```

---

## Issue 5. Collect 20 MVP-0 Trajectories After UX Calibration

Type:

```text
Validation / Data collection
```

Summary:

```text
UX calibration 개선 후 20 episode collection run을 수행한다.
```

Why:

- 현재는 기능 smoke만 완료했다.
- quantitative MVP-0 Go Criteria로 가기 전 작은 batch validation이 필요하다.

Scope:

- same task_id under one collection task
- success/failure/reset/incomplete lifecycle 기록
- scoped KPI 저장
- dataset export
- HDF5 export/inspect

Acceptance Criteria:

```text
recorded_episodes >= 20
replayable_trajectory_rate >= 0.8
usable_trajectory_rate >= 0.8
task_success_rate > 0.0
accepted_trajectory_rate > 0.0
```

Priority:

```text
P1
```

---

## Issue 6. Run 100 Trajectory MVP-0 Quantitative Validation

Type:

```text
Milestone / Validation
```

Summary:

```text
MVP-0 quantitative Go Criteria 충족 여부를 100 trajectory 이상으로 검증한다.
```

Acceptance Criteria:

```text
recorded_episodes >= 100
replayable_trajectory_rate >= 0.8
valid_trajectory_rate >= 0.7
JSON export success
HDF5 export success
dataset card generated
accepted trajectory dataset non-empty
```

Priority:

```text
P2
```

---

## Issue 7. Prepare MVP-1 Task Selection

Type:

```text
MVP-1 planning
```

Summary:

```text
Peg-in-hole 또는 connector insertion 중 MVP-1 기준 task를 선택한다.
```

Dependencies:

- Issue 2 UX calibration
- Issue 5 20 trajectory collection
- Issue 6 MVP-0 quantitative validation

Acceptance Criteria:

- task success/failure criteria 문서화
- required observations/actions 정의
- evaluator metric 정의
- dataset schema implication 정의

Priority:

```text
P2
```

---

## Post-MVP Backlog

MVP 범위 밖:

- LeRobot Dataset v3 full writer
- replay UI visualization
- behavior cloning training
- CloudXR
- real robot control
- paid pilot billing
- marketplace
- production authentication

이 항목들은 MVP-0 quantitative validation 이후 별도 roadmap으로 이동한다.
