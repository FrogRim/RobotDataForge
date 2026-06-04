# COLLAB-SIM

## Overview

- problem: RDF의 현재 조작감 문제는 단순 recorder 문제가 아니라 VR pose -> robot command -> simulation feedback latency/control quality 문제다.
- why it matters: COLLAB-SIM은 Isaac Sim + XR + cuRobo 기반 VR teleoperation과 demonstration collection을 구현한 가장 가까운 외부 시스템이다.

## System Architecture

- components:
  - Isaac Sim XR rendering.
  - VR HMD/controllers pose streaming.
  - Franka single/dual arm teleoperation examples.
  - cuRobo MPC/IK controller.
  - recorded demonstrations replay tool.
- data flow:
  - VR HMD/controller pose가 application으로 들어온다.
  - delta teleoperation command로 end-effector target을 만든다.
  - MPC/IK가 robot motion을 생성한다.
  - Isaac Sim physics/rendering이 VR headset으로 feedback된다.
  - demonstrations를 record/replay한다.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - HMD 6-DOF pose.
  - controller 6-DOF pose and button state.
- processing (mapping -> robot action):
  - absolute hand/controller pose를 그대로 쓰기보다 delta end-effector motion으로 변환.
  - MPC/IK로 reachable/smooth robot motion 생성.
- output (dataset):
  - teleop demonstration.
  - replayable states/actions.

## Dataset Structure

- state:
  - robot state.
  - object state.
  - scene reset randomization state.
- action:
  - delta end-effector command.
  - gripper command.
  - optionally MPC target.
- observation:
  - VR rendered scene.
  - current RDF는 visual observation 저장이 약하므로 추후 camera frame 추가 필요.
- timestamp:
  - control tick 기준 step.
  - RDF에는 controller input time과 sim step time을 분리 저장해야 한다.

## Logging Strategy

- frequency:
  - interactive VR target 30-35 FPS 수준을 명시한다.
  - physics/control loop와 recording loop를 분리하는 구조가 필요하다.
- storage format:
  - record/replay 중심.
  - RDF는 JSON first, 이후 HDF5/LeRobot 변환.

## Implementation Details

- COLLAB-SIM은 clarity/simplicity를 우선해 custom workflow callback을 VR controller button mapping에 붙인다.
- environment reset과 demonstration logging을 VR controller에서 수행한다.
- block position randomization 후 새 episode를 시작하는 방식이 MVP-0 100 trajectory collection에 직접 유용하다.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `scripts/run_live_rdf_smoke_test.sh`
- what module/function to modify:
  - `teleop_se3_agent.py`: keyboard/gesture command로 `mark_success`, `mark_failure`, `reset_episode`, `recenter` callback 추가.
  - `rdf_isaac_runtime_recorder.py`: episode boundary를 Isaac window close에만 의존하지 않고 command-driven lifecycle로 전환.
  - `run_live_rdf_smoke_test.sh`: 1 episode smoke test와 multi-episode collection mode 분리.

## Minimal Integration Plan

1. 현재 close-on-finish 저장은 유지한다.
2. `teleop_se3_agent.py`에 `n=success reset`, `r=failure reset`, `c=recenter` key callback 추가.
3. recorder에 `finish_and_restart(reason, success_hint)` 메서드 추가.
4. episode summary에 `operator_marked_success`, `reset_seed`, `scene_randomization` 저장.
5. replay에서 success/failure lifecycle을 확인한다.

## Expected Impact

- 매 episode마다 Isaac을 닫지 않아도 수집이 가능해진다.
- MVP-0 Go criteria의 100 trajectory 수집 시간이 크게 줄어든다.
- 실패 episode와 성공 episode lifecycle이 명확해진다.

## What to Adopt

- delta teleoperation 우선.
- VR/controller callback 기반 episode lifecycle.
- reset randomization metadata.
- record/replay를 core loop로 취급.

## What to Avoid

- cuRobo/MPC 전체 도입은 아직 과하다.
- dual-arm이나 real robot 제어는 AGENTS.md 금지/범위 밖이다.

## Reference

- https://github.com/NVlabs/collab-sim
