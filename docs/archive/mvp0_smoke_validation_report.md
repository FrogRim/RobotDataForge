# MVP-0 Smoke Validation Report

작성일: 2026-05-04

## 결론

Robot Data Forge의 MVP-0 implementation과 live smoke validation은 완료로 판단한다.

정확한 상태는 다음과 같다.

```text
MVP-0 implementation: 완료
MVP-0 live smoke validation: 완료
MVP-0 quantitative Go Criteria: 미완료
MVP-1 진입 준비: 부분 완료
```

이번 결과는 “Quest/OpenXR/Isaac Lab 기반 기술 파이프라인이 실제로 닫혔다”는 증명이다. 다만 100개 이상 trajectory 수집, replayable 80%+, accepted trajectory dataset 생성 같은 정량 Go Criteria는 아직 완료하지 않았다.

## 검증된 Primary Path

검증된 primary path:

```text
Quest 3 handtracking
  -> ALVR + SteamVR/OpenXR
  -> Isaac Lab teleoperation
  -> Trajectory Recorder
  -> ForgeEval
  -> DataUsability
  -> ForgeCurate
  -> Dataset Export / Dataset Card
```

웹 mock task는 이번 검증의 primary path가 아니다. 이번 검증은 실제 Isaac Lab OpenXR handtracking run에서 수행되었다.

## 실행 환경

확인된 환경:

```text
OS: Ubuntu 24.04.4
GPU: NVIDIA GeForce RTX 4060 Ti
NVIDIA driver: 570.211.01
Isaac Sim: 5.1 / Kit 107.3.3
Isaac Lab: 2.3.2
Task: Isaac-Stack-Cube-Franka-IK-Rel-v0
Input: Quest 3 handtracking
Runtime: SteamVR OpenXR
Streaming: ALVR
```

실행 명령:

```bash
RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

Scoped KPI 확인 명령:

```bash
curl -sS 'http://localhost:8000/api/admin/kpis?task_id=task_719a38538a64&started_after=2026-05-03T14:48:00Z'
```

## Live Smoke KPI

2026-05-03 23:48 이후 scoped run 기준:

```json
{
  "recorded_episodes": 4,
  "completed_episodes": 3,
  "invalid_episode_rate": 0.0,
  "average_episode_duration": 16.78,
  "frames_per_episode": 119.67,
  "replayable_trajectory_rate": 0.75,
  "hand_tracking_loss_rate": 0.0,
  "frame_drop_rate": 0.0,
  "task_success_rate": 0.0,
  "accepted_trajectory_rate": 0.0,
  "average_data_usability_score": 0.891,
  "usable_trajectory_rate": 1.0,
  "sync_error_ms_mean": null,
  "sync_error_ms_p95": null
}
```

## 완료된 검증 항목

완료:

- Isaac Lab OpenXR task launch
- Quest/OpenXR handtracking recorder start
- terminal hotkey lifecycle command
  - `P`: recenter/calibration
  - `N`: success finalize
  - `F`: failure finalize
  - `R`: reset finalize
- `Trajectory` 생성
- `Evaluation` 생성
- `SyncMetrics` 생성
- `DataUsabilityScore` 생성
- `ActionSegment` 생성
- `Dataset` export manifest 생성
- `DatasetCard` 생성
- task reuse 확인
- scoped KPI filter 확인

## 중요한 로그 근거

Task reuse 확인:

```text
[RDF] Using collection task task_719a38538a64
[RDF] Reusing collection task task_719a38538a64
[RDF] Reusing collection task task_719a38538a64
```

Lifecycle command 확인:

```text
[RDF] Terminal hotkeys active: P=recenter, N=success, F=failure, R=reset
[RDF] Calibration/recenter requested
[RDF] Episode finalize requested: status=success reason=operator_success
[RDF] Submitted episode ... status=success ...
```

## 완료로 보지 않는 항목

아직 완료하지 않은 Go Criteria:

- 100개 이상 real trajectory 수집
- 80%+ replayable trajectory rate 유지
- 70%+ valid trajectory rate 유지
- 실제 accepted success trajectory dataset 생성
- replay/QA 화면 기반 검토
- HDF5 batch export를 real collection set에서 검증
- evaluator agreement human review set 확보

## 현재 한계

현재 가장 큰 한계:

```text
Teleoperation UX / calibration mismatch 때문에 실제 task success trajectory가 나오지 않는다.
```

현재 수치상 증거:

```text
task_success_rate: 0.0
accepted_trajectory_rate: 0.0
```

단, 이번 run은 기능 smoke 목적이었기 때문에 이 값 자체를 No-Go로 보지 않는다. 다음 단계는 조작 UX를 개선한 뒤 success trajectory collection을 반복해야 한다.

## 남은 품질 Gap

남은 gap:

- `sync_error_ms`가 아직 측정되지 않는다.
- `ActionSegment.phase`는 대부분 `UNKNOWN`이다.
- 실조작 UX가 실제 사용 환경과 맞지 않아 task success에 영향을 준다.
- stale rows와 patch 전 rows는 DB에 남아 있으므로 scoped query를 사용해야 한다.

## 다음 우선순위

다음 작업 우선순위:

1. Teleop UX / workspace calibration 개선
2. `sync_error_ms` 측정 추가
3. action phase metadata 기록
4. 20개 live trajectory collection run
5. 100개 trajectory MVP-0 quantitative validation

## Notion 요약문

Notion에는 다음 요약을 상단에 붙인다.

```text
Robot Data Forge MVP-0 implementation and live smoke validation are complete.
The primary Quest/OpenXR/Isaac Lab data pipeline now records trajectories,
evaluates them, computes usability metrics, and exports dataset artifacts.

The remaining blocker is not backend functionality but teleoperation UX:
the Quest/OpenXR handtracking workspace does not yet feel aligned with the
Isaac robot workspace, preventing reliable task success trajectories.
```
