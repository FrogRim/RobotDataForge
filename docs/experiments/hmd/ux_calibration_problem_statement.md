# UX Calibration Problem Statement

작성일: 2026-05-04

2026-05-19 업데이트:

- Primary HMD recenter는 더 이상 `auto_first_valid_frame` 또는 terminal `P`에 의존하지 않는다.
- 기본 flow는 `RDF_RECENTER_MODE=robot_start_box`다.
- Recenter 기준점은 operator 손 위치가 아니라 simulation 안의 `/World/RDFRecenterStartBox`다.
- Start box center는 기본적으로 `hole_target_approach + per-reset random_offset`이며, random offset은 episode/reset마다 한 번만 샘플링된다.
- Recenter 전에는 setup-only control로 robot을 box 안에 넣을 수 있지만, recording/warmup frame은 recenter 완료 후 시작한다.
- 최신 운영 계약은 `docs/experiments/hmd/hmd_recenter_start_box.md`를 따른다.

## 결론

다음 주요 blocker는 backend pipeline이 아니라 Quest/OpenXR handtracking과 Isaac Lab robot workspace 사이의 조작 UX mismatch다.

현재 pipeline은 trajectory를 저장하고 평가할 수 있다. 그러나 조작자가 느끼는 시점, 손 위치, robot target pose가 자연스럽게 대응하지 않아 task success trajectory를 안정적으로 만들기 어렵다.

## 문제 정의

현재 사용자가 느낀 문제:

```text
실제 내 환경과 Isaac Sim 안의 조작 환경이 너무 다르다.
시점과 조작 좌표가 맞지 않아 조작이 불편하다.
이 UX 불일치가 task success에 큰 영향을 준다.
```

이 문제는 단순 comfort issue가 아니다. Robot Data Forge의 data quality와 collection throughput을 직접 낮춘다.

## 왜 중요한가

Robot Data Forge의 핵심 KPI는 recorded episode 수가 아니라 usable accepted trajectory 수다.

UX mismatch가 있으면 다음 문제가 발생한다.

- operator가 task를 성공시키기 어렵다.
- success trajectory 수가 늘지 않는다.
- evaluator confidence가 낮아진다.
- accepted trajectory rate가 0에 머문다.
- 같은 task를 여러 번 반복해도 학습 가능한 dataset이 쌓이지 않는다.
- operator fatigue가 증가한다.

현재 live smoke 결과도 이 방향을 가리킨다.

```text
task_success_rate: 0.0
accepted_trajectory_rate: 0.0
usable_trajectory_rate: 1.0
```

즉, 데이터는 저장되지만 task success를 만들기 어려운 상태다.

## 현재 구현 상태

현재 calibration:

```text
type: workspace_alignment_v2
trigger:
  - auto_robot_start_box
  - operator_command via P (debug/fallback)
```

현재 저장되는 metadata:

- raw XR right wrist pose
- aligned XR right wrist pose
- translation offset
- rotation_offset_quat
- action filter gain/deadzone/smoothing/axis map
- calibration reason
- calibration events
- raw teleop action
- retargeted robot action
- filtered/applied robot action

현재 부족한 점:

- Isaac OpenXR anchor 자체를 robot workspace에 재배치하지는 않는다.
- visual ghost feedback이 없다.
- operator comfort pose가 시각적으로 표시되지 않는다.
- headset/world origin과 robot workspace 관계가 명시적이지 않다.
- 시각적 feedback이 없어 calibration이 잘 됐는지 즉시 알기 어렵다.

추가 구현된 control-side 보정:

```text
RDF robot-space recenter:
  - RDF_RECENTER_MODE=robot_start_box
  - RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach
  - RDF_RECENTER_BOX_RANDOM_OFFSET sampled once per episode/reset
  - visible /World/RDFRecenterStartBox wireframe
  - setup-only pre-recenter control

RDF action filter:
  - position_gain
  - rotation_gain
  - position_deadzone
  - rotation_deadzone
  - smoothing_alpha
  - signed position axis map
  - signed rotation axis map
```

## 가설

우선 검증할 가설:

1. Translation-only calibration으로는 손과 end-effector 방향 감각을 맞추기 어렵다.
2. XR hand pose와 robot workspace 사이에 rotation alignment가 필요하다.
3. operator 기준 neutral hand pose를 잡고, 그 이후 상대 움직임을 robot action에 mapping해야 한다.
4. current OpenXR anchor와 Isaac camera/viewpoint가 task workspace를 조작하기 좋은 위치가 아니다.
5. action gain이 너무 크거나 작아 fine manipulation이 어렵다.

## 개선 목표

목표:

```text
Quest hand pose movement should feel spatially aligned with the Isaac robot workspace.
```

조작자는 다음을 느껴야 한다.

- 손을 앞으로 움직이면 robot target도 예상 방향으로 움직인다.
- 손을 좌우/상하로 움직일 때 Isaac workspace와 방향이 맞는다.
- 작은 손 움직임으로 cube stack task를 조심스럽게 조작할 수 있다.
- start box recenter 후 조작 시작점이 episode마다 명확하고 반복 가능하다.
- 10분 이상 반복해도 방향 감각 혼란이 적다.

## MVP 범위

이번 UX calibration PR에서 허용:

- calibration metadata 확장
- rotation-aware alignment
- gain / sensitivity parameter
- deadzone / smoothing parameter
- neutral pose capture
- recenter behavior 개선
- debug log 추가
- validation guide 추가

이번 PR에서 금지:

- real robot control
- CloudXR
- full UI replay implementation
- behavior cloning
- tactile hardware
- production authentication
- marketplace / reward logic

## Acceptance Criteria

최소 완료 기준:

```text
1. HMD/AR에서 visible start box를 확인할 수 있다.
2. Robot EEF/fingertip이 start box에 들어간 뒤에만 recenter가 완료된다.
3. Recenter 전 setup-only movement는 recording/warmup frame으로 저장되지 않는다.
4. Recenter 후 hand pose와 robot target movement 방향이 직관적으로 맞는다.
5. calibration metadata에 translation, rotation, gain 정보가 저장된다.
6. calibration event가 trajectory summary에 남는다.
7. operator가 같은 task에서 5분 내 1개 이상의 intentional success-like trajectory를 만들 수 있다.
8. retargeting_jump_max가 비정상적으로 커지지 않는다.
9. 기존 trajectory schema reader가 깨지지 않는다.
```

정량 목표 초안:

```text
20 episode live run:
  replayable_trajectory_rate >= 0.8
  usable_trajectory_rate >= 0.8
  task_success_rate > 0.0
  accepted_trajectory_rate > 0.0
```

## 검증 방법

실행:

```bash
RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

검증:

```bash
curl -sS 'http://localhost:8000/api/admin/kpis?task_id=task_719a38538a64&started_after=2026-05-03T14:48:00Z'
```

추가 확인:

```bash
curl -sS 'http://localhost:8000/api/episodes?task_id=task_719a38538a64&started_after=2026-05-03T14:48:00Z'
```

확인할 값:

- `task_success_rate`
- `accepted_trajectory_rate`
- `retargeting_jump_max`
- `average_data_usability_score`
- `replayable_trajectory_rate`
- `usable_trajectory_rate`

## 이번 PR 반영 내용

작업 제목:

```text
Improve Quest/OpenXR teleop workspace calibration for MVP-0 collection
```

핵심 변경:

- `workspace_alignment_v2` calibration metadata를 저장한다.
- raw action과 filtered/applied action을 함께 저장한다.
- `P` recenter에서 action filter smoothing state를 reset한다.
- environment variable로 gain, deadzone, smoothing, axis map을 조정할 수 있게 한다.
- live validation checklist와 debugging guide를 업데이트한다.
