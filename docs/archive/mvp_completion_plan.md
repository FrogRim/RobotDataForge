# MVP Completion Plan

이 문서는 Robot Data Forge MVP-0를 완료하고 MVP-1 준비 단계로 넘어가기 위한 최종 실행 계획이다.

Robot Data Forge는 Quest 3 / OpenXR / Isaac Lab 기반 robot teleoperation data generation pipeline이다. 핵심 목적은 실제 로봇 제어가 아니라 imitation learning과 physical AI를 위한 trajectory 수집, 검증, lifecycle tracking, dataset export다.

---

## 1. Current Status

현재 backend/data pipeline은 code-level scaffold 기준으로 다음 항목을 갖춘 상태다.

완료된 항목:

```text
JSON/state-first live trajectory recording
raw XR pose recording
aligned XR pose recording
retargeted action recording
warm-up based recording start
evaluator runtime quality gates
explicit episode lifecycle
success/failure/reset/incomplete status
offline HDF5 export
HDF5 dataset inspection
local SQLite API smoke path
one-shot live smoke script
```

아직 완료로 보지 않는 항목:

```text
real Quest/ALVR/SteamVR/OpenXR live validation with N/F/R/P commands
100+ real Isaac trajectory collection
success-only HDF5 export from real success episodes
operator UX validation for viewpoint/control alignment
human review / evaluator agreement measurement
MVP-1 peg-in-hole or connector insertion task implementation
learning uplift validation
```

중요한 해석:

```text
Unit tests and mock/fake env tests prove code boundaries.
They do not prove MVP-0 Go Criteria.
MVP-0 is complete only after real Quest/OpenXR/Isaac collection data passes validation gates.
```

---

## 2. MVP-0 Definition

MVP-0는 투자자/customer wedge가 아니라 technical pipeline proof다.

목표 flow:

```text
Quest 3 handtracking
  -> ALVR + SteamVR/OpenXR
  -> Isaac Lab teleoperation task
  -> JSON/state-first trajectory recorder
  -> explicit episode lifecycle
  -> ForgeEval
  -> offline HDF5 export
  -> HDF5 sanity inspection
```

MVP-0 기준 task:

```text
Isaac-Stack-Cube-Franka-IK-Rel-v0
```

주의:

```text
This is an engineering smoke test.
Do not present Franka stack cube as the final customer wedge.
```

---

## 3. MVP-0 Completion Criteria

MVP-0는 아래 조건을 모두 만족할 때 완료로 본다.

### 3.1 Live Runtime Criteria

```text
Quest 3 connects through ALVR + SteamVR/OpenXR.
Isaac Lab starts with handtracking teleop.
RDF_RECORD=1 path creates API task/session/episode records.
P command records calibration/recenter metadata.
N command finalizes success episode.
F command finalizes failure episode.
R command finalizes reset episode.
Isaac shutdown without explicit finalization becomes incomplete.
```

### 3.2 Trajectory Data Criteria

각 real trajectory JSON은 다음을 포함해야 한다.

```text
schema_version
source.input_device
source.runtime
source.simulator
source.robot
source.task_name
frames[].metadata.raw_xr
frames[].metadata.aligned_xr
frames[].metadata.retargeted
frames[].action.retargeted_robot_action
summary.episode_status
summary.episode_started_at
summary.episode_finalized_at
summary.warmup_dropped_frames
summary.calibration_events
```

### 3.3 Evaluation Criteria

```text
Evaluation JSON includes trajectory_id and episode_id.
tracking_loss_after_warmup is available.
retargeting_jump_max is available when action data exists.
latency metrics are available when runtime provides input_latency_ms.
jitter metrics are available from timestamps.
failure_reason is interpretable.
```

### 3.4 Export Criteria

```text
At least one real success episode exports to HDF5 with default success-only export.
Failure/reset/incomplete episodes are excluded by default.
Failure/reset/incomplete episodes can be included with explicit flags.
HDF5 inspector reports no blocking issues for success dataset.
```

### 3.5 Minimum Collection Criteria

최소 Go 기준:

```text
100+ real Isaac trajectory attempts
80%+ replayable_trajectory_rate
70%+ valid trajectory rate after warm-up
at least 10 success lifecycle episodes
success-only HDF5 export succeeds
manual review sample exists for evaluator sanity check
```

더 강한 기준:

```text
100+ real trajectory attempts
30+ success lifecycle episodes
tracking_loss_after_warmup < 0.10 median
session_crash_rate < 0.10
HDF5 inspector issues == []
```

---

## 4. Remaining Phases

### Phase A: Real Live Validation

목표:

```text
현재 구현된 runtime pipeline이 실제 Quest/OpenXR/Isaac 환경에서 끝까지 동작하는지 확인한다.
```

작업:

```text
1. ./scripts/run_live_rdf_smoke_test.sh 실행
2. Quest 3 ALVR connection 확인
3. Isaac teleop scene에서 handtracking 확인
4. P/N/F/R command 각각 실행
5. API snapshot과 storage artifact 확인
6. HDF5 export와 inspector 실행
```

완료 산출물:

```text
success/failure/reset/incomplete real episode 각각 1개 이상
storage/trajectories/*.json
storage/evaluations/*.json
storage/exports/*.hdf5
docs/DATA_COLLECTION_LOG.md 기록 1회 이상
```

### Phase B: MVP-0 Collection Run

목표:

```text
MVP-0 Go Criteria를 수치로 판단할 수 있는 최소 dataset을 만든다.
```

작업:

```text
100+ trajectory attempts
session별 tracking/runtime metric 기록
success/failure/reset/incomplete 분포 기록
HDF5 success dataset 생성
debug HDF5 dataset 생성
inspector report 저장
```

완료 산출물:

```text
MVP-0 collection summary
success-only HDF5 dataset
debug HDF5 dataset
known issue list
Go / No-Go 판단
```

### Phase C: Demo Readiness

목표:

```text
투자자/협업자에게 technical pipeline이 닫혔다는 것을 보여줄 수 있는 demo flow를 고정한다.
```

작업:

```text
DEMO_SCRIPT.md 기준 rehearsal
clean success episode 3개 이상 확보
HDF5 inspector 결과 캡처
KPI endpoint 출력 준비
known limitations 정리
```

완료 산출물:

```text
demo-ready commands
demo dataset artifact
demo failure fallback path
```

### Phase D: MVP-1 Preparation

목표:

```text
Peg-in-hole 또는 connector insertion으로 고객/투자 가치 proof를 준비한다.
```

작업:

```text
MVP1_TASK_SPEC.md 확정
success/failure criteria 확정
required observation/action schema 확정
evaluator metric gap 정리
task implementation PR 범위 산정
```

---

## 5. Validation Gates

각 gate를 통과해야 다음 단계로 넘어간다.

| Gate | 통과 조건 | 실패 시 조치 |
|---|---|---|
| API gate | `/api/episodes`, `/api/admin/kpis` 200 | SQLite local API로 재시작 |
| XR gate | ALVR + SteamVR + Quest connected | `--no-start-xr`로 수동 시작 후 재시도 |
| Isaac gate | Isaac task starts and handtracking moves camera/hand input | OpenXR runtime path 확인 |
| Lifecycle gate | P/N/F/R command가 artifact에 반영 | teleop command callback 확인 |
| Trajectory gate | raw/aligned/retargeted fields 존재 | recorder version/path 확인 |
| Evaluation gate | evaluator JSON과 failure_reason 생성 | task/evaluator input 확인 |
| Export gate | success HDF5 export 성공 | success lifecycle episode 먼저 수집 |
| Inspector gate | `issues == []` | missing field 또는 timestamp/action 원인 수정 |

---

## 6. Risks

| Risk | 영향 | 대응 |
|---|---|---|
| ALVR/SteamVR startup race | Isaac Start XR hang 또는 disconnect | one-shot script 사용, 필요 시 `--no-start-xr` |
| handtracking loss | evaluator failure, invalid data 증가 | warm-up frames 증가, Quest 시야 확보 |
| viewpoint/control mismatch | operator UX 저하, trajectory 품질 저하 | P calibration 기록, 이후 control mapping recenter PR |
| calibration is metadata-only | 실제 조작감 개선 제한 | live validation 후 retargeter anchor 보정 별도 PR |
| no real success episode | success-only HDF5 export 불가 | N command로 success lifecycle episode 수집 |
| evaluator false positive | bad data accepted | human review sample로 agreement 측정 |
| LeRobot premature implementation | format drift, rework | HDF5 baseline 이후 별도 PR |

---

## 7. Next PR Sequence

### PR 1: Live Validation Documentation and Run Artifacts

범위:

```text
No application feature changes.
Record live validation results.
Update DATA_COLLECTION_LOG and WORKLOG.
```

목표:

```text
P/N/F/R lifecycle real artifact 확보.
```

### PR 2: Control-Side Recenter If Needed

조건:

```text
Live validation에서 metadata calibration만으로 UX mismatch가 해결되지 않을 때만 진행한다.
```

범위:

```text
teleop control mapping / retargeter anchor correction
```

주의:

```text
This is separate from recorder metadata.
Do not mix with exporter or evaluator work.
```

### PR 3: Human Review and Replay Verification Minimum

범위:

```text
HumanReview workflow
basic trajectory inspection/replay evidence
evaluator agreement measurement
```

### PR 4: MVP-0 Collection Summary and Export Hardening

범위:

```text
real success HDF5 dataset
debug HDF5 dataset
inspector summary
dataset stats if needed
```

### PR 5: MVP-1 Task Setup Spec to Implementation

범위:

```text
peg-in-hole or connector insertion task setup
task-specific evaluator criteria
schema additions only if required
```

---

## 8. Non-Goals

MVP-0/MVP-1 준비 중 아래 항목은 구현하지 않는다.

```text
CloudXR
real robot control
payment
reward payout
marketplace
production auth
full RL pipeline
behavior cloning training runner
full LeRobot Dataset v3 exporter before real data validation
replay page visualization before live data quality is proven
storing image frames directly inside trajectory JSON
rewriting live recorder into HDF5 writer
describing ManiSkill 3 as Isaac-native
treating completed_episodes as data quality
```

---

## 9. Post-MVP Roadmap

MVP-0 이후:

```text
LeRobot Dataset v3 exporter
ACT or Diffusion Policy baseline
camera/video observation export by external references
dataset split and stats generation
trajectory diversity metrics
workspace randomization
Isaac Lab Mimic / MimicGen integration
```

MVP-1 이후:

```text
design partner task import
customer-specific evaluator library
paid pilot package definition
policy uplift report automation
sim-to-real feasibility study
```

---

## 10. Current Best Next Action

다음 액션은 코드 구현이 아니라 real live validation이다.

```bash
cd ~/robot-data-forge
./scripts/run_live_rdf_smoke_test.sh
```

실행 후 반드시 기록한다.

```text
docs/DATA_COLLECTION_LOG.md
docs/WORKLOG.md
```
