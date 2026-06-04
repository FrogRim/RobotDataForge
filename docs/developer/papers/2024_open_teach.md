# OPEN TEACH

## Overview

- problem: RDF는 Meta Quest 3 기반 teleoperation과 data collection pipeline을 안정적으로 운영해야 한다.
- why it matters: OPEN TEACH는 Quest 3, teleoperation server, robot/simulation adapter, data collection module을 분리한 구현체다.

## System Architecture

- components:
  - Quest 3 VR application.
  - server-side `teleop.py`.
  - robot adapters: Allegro, Franka, Kinova, bimanual, simulation.
  - `data_collect.py`.
  - h5/video storage.
- data flow:
  - Quest app에서 human motion을 server로 보낸다.
  - robot-specific adapter가 human motion을 robot action으로 retarget한다.
  - data collection module이 robot state, camera stream, sensor state를 저장한다.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - Quest hand/controller motion.
  - server IP/network configuration.
- processing (mapping -> robot action):
  - robot별 adapter가 human arm/hand motion을 robot command로 변환.
  - sim/real mode를 flag로 분리한다.
- output (dataset):
  - camera stream은 `.avi`.
  - depth/robot information은 `.h5`.

## Dataset Structure

- state:
  - robot states.
  - sensor states.
  - optional depth.
- action:
  - robot command.
  - gripper/hand command.
- observation:
  - camera video stream.
- timestamp:
  - 문서상 명시가 약하므로 RDF는 timestamp를 더 엄격히 유지해야 한다.

## Logging Strategy

- frequency:
  - camera stream과 robot state를 별도 format으로 저장.
- storage format:
  - optimized `.avi` for camera.
  - `.h5` for robot/depth/sensor state.

## Implementation Details

- OpenTeach는 teleop과 data collection을 분리 실행한다.
- `teleop.py robot=franka`와 `data_collect.py robot=franka demo_num=1` 같은 explicit command가 있다.
- simulation은 `sim_env=True`로 분리한다.
- network IP 설정을 사용자가 명시해야 한다.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `app.adapters.isaac_lab_adapter.IsaacLabAdapter`
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `scripts/run_live_rdf_smoke_test.sh`
  - `apps/api/app/services/storage.py`
- what module/function to modify:
  - `IsaacLabAdapter`: command만 반환하지 말고 `capabilities()`를 반환하도록 확장.
  - `rdf_isaac_runtime_recorder.py`: state/action과 camera/video recording boundary를 분리.
  - `storage.py`: future visual stream path를 `videos/` 또는 `observations/`로 분리.

## Minimal Integration Plan

1. `TrajectorySource` metadata에 `adapter_name`, `adapter_mode`, `network_stack` 추가.
2. `scripts/run_live_rdf_smoke_test.sh`에 `--record-state-only`와 `--record-visuals` 모드 분리.
3. visual recording은 live loop 안에서 바로 구현하지 말고 replay-derived camera export로 먼저 구현한다.
4. `storage/trajectories`, `storage/evaluations`, `storage/exports`, `storage/videos` 구조로 확장한다.

## Expected Impact

- RDF가 OpenTeach처럼 robot/sim adapter와 data collection을 명확히 분리한다.
- visual observation 추가 시 JSON trajectory가 과도하게 커지는 문제를 피한다.

## What to Adopt

- teleop module과 data collection module 분리.
- robot/simulation adapter boundary.
- video와 state storage 분리.

## What to Avoid

- conda/Unity app 전체 도입.
- simulation adapter를 primary Isaac Lab path보다 앞세우는 것.

## Reference

- https://github.com/aadhithya14/Open-Teach
- https://github.com/aadhithya14/Open-Teach/blob/main/docs/teleop_data_collect.md
