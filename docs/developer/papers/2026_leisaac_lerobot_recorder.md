# LeIsaac LeRobot Recorder

## Overview

- problem: RDF는 현재 JSON trajectory export만 구현되어 있다. MVP-1 learning value proof에는 training-ready dataset format이 필요하다.
- why it matters: LeIsaac은 Isaac Lab teleoperation 중 LeRobot format recorder를 직접 붙이는 구현체다. RDF의 `Trajectory Recorder -> Validated Dataset Export`와 매우 가깝다.

## System Architecture

- components:
  - Isaac Lab teleoperation script.
  - `--record` HDF5 recorder.
  - `--use_lerobot_recorder` LeRobot recorder.
  - success/failure에 따른 flush/clear episode handling.
- data flow:
  - teleop device가 action 생성.
  - Isaac Lab env step이 observation/action 생성.
  - recorder manager가 매 step frame을 LeRobot frame으로 변환.
  - episode 종료 시 success면 `flush()`, failure면 `clear()`.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - LeIsaac 예시는 SO101 leader/keyboard/gamepad 중심이지만 구조는 Isaac Lab teleop device 공통이다.
  - RDF의 Quest handtracking도 같은 `teleop_se3_agent.py` loop에서 처리된다.
- processing (mapping -> robot action):
  - `build_lerobot_frame` 단계에서 Isaac observation/action을 training schema로 변환한다.
  - 첫 5 frame을 skip해 초기 instability를 줄인다.
- output (dataset):
  - LeRobot frame buffer.
  - 성공 episode만 저장하는 dataset.
  - HDF5 또는 LeRobot Dataset v3.

## Dataset Structure

- state:
  - joint positions.
  - optional camera observations.
  - task-specific object state.
- action:
  - robot action tensor.
  - action frequency는 `--lerobot_dataset_fps`.
- observation:
  - camera images를 enable하면 visual policy training 가능.
- timestamp:
  - dataset FPS 기반 index.
  - RDF에서는 `t`, `step`, `sim_timestamp`, `xr_timestamp`를 같이 유지해야 한다.

## Logging Strategy

- frequency:
  - fixed dataset FPS, 예: 30 FPS.
  - teleop control loop와 recording FPS를 분리할 수 있다.
- storage format:
  - HDF5 기본.
  - LeRobot recorder는 바로 LeRobot format으로 저장.

## Implementation Details

- LeIsaac recorder는 기본 recorder manager를 `LeRobotRecorderManager`로 대체한다.
- 매 env step 후 observation/action을 수집하고 `build_lerobot_frame`으로 변환한다.
- episode success면 buffer를 저장하고, failure면 clear한다.
- 초기 5 frame을 skip한다. RDF가 방금 추가한 `RDF_WARMUP_VALID_FRAMES`와 같은 문제의식이다.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `apps/api/app/services/exporter.py`
  - `apps/api/app/routers/datasets.py`
  - `packages/shared/trajectory_schema.json`
- what module/function to modify:
  - `exporter.py`: `export_format == "lerobot"`를 post-MVP가 아니라 MVP-1 gate로 준비.
  - 새 파일 `scripts/export_rdf_to_lerobot.py`: accepted RDF JSON trajectories를 LeRobot Dataset v3 layout으로 변환.
  - `TrajectoryPayload.summary`: `dataset_fps`, `recording_fps`, `warmup_dropped_frames` 확정 필드 추가.

## Minimal Integration Plan

1. 현재 JSON export는 유지한다.
2. `scripts/export_rdf_to_lerobot.py`를 추가한다.
3. RDF frame을 `observation.state`, `action`, `timestamp`, `episode_index`, `frame_index`로 flatten한다.
4. 실패 episode는 기본 제외하고, `--include-failures` 옵션으로 negative dataset 생성만 허용한다.
5. `/api/datasets/export`는 우선 `json`만 유지하되, CLI converter를 `docs/ROADMAP.md`에 MVP-1 prerequisite로 올린다.

## Expected Impact

- RDF가 “저장 도구”에서 “학습 가능한 dataset exporter”로 넘어간다.
- MVP-1의 `curated dataset uplift` 실험을 LeRobot/ACT/Diffusion Policy 도구로 바로 연결할 수 있다.

## What to Adopt

- success episode만 flush하는 기본 정책.
- 초기 frame skip/warm-up.
- fixed dataset FPS.
- direct LeRobot export path.

## What to Avoid

- live teleop loop 안에서 heavy encoding을 수행해 조작 latency를 늘리는 것.
- 실패 episode를 조용히 버려 error analysis가 불가능해지는 것. 실패는 저장하되 training export에서 제외한다.

## Reference

- https://lightwheelai.github.io/leisaac/docs/features/lerobot_recorder/
- https://lightwheelai.github.io/leisaac/docs/getting_started/teleoperation/
- https://github.com/LightwheelAI/leisaac
