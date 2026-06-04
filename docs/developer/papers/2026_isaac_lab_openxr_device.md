# Isaac Lab OpenXR Device

## Overview

- problem: Robot Data Forge(RDF)는 Quest 3 handtracking을 Isaac Lab의 `teleop_se3_agent.py`로 받아 Franka task를 조작하고 trajectory를 저장해야 한다.
- why it matters: AGENTS.md의 primary path가 `Quest 3 handtracking -> ALVR + SteamVR/OpenXR -> Isaac Lab teleoperation task -> Trajectory Recorder`이므로, Isaac Lab의 OpenXR device/retargeter 구조가 현재 구현의 가장 직접적인 기준이다.

## System Architecture

- components:
  - `OpenXRDevice`: OpenXR hand/head tracking source.
  - `RetargeterBase`: raw XR data를 robot command로 변환하는 경계.
  - `Se3AbsRetargeter`, `Se3RelRetargeter`: hand pose를 end-effector command로 변환.
  - `GripperRetargeter`: pinch/gripper mapping.
- data flow:
  - OpenXR runtime이 hand/head joint pose를 제공한다.
  - `OpenXRDevice.advance()`가 raw tracking data를 읽는다.
  - retargeter가 robot action을 생성한다.
  - Isaac Lab env step이 action을 적용한다.
  - RDF recorder가 env state/action/runtime metadata를 frame으로 저장한다.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - hand joint pose: wrist, palm, thumb/index/middle/ring/little joints.
  - head pose: HMD pose.
  - gesture: pinch 기반 gripper command.
- processing (mapping -> robot action):
  - `Se3RelRetargeter` 또는 현재 task config의 handtracking retargeter가 hand motion을 robot target pose로 변환한다.
  - gripper는 pinch strength를 action의 마지막 값으로 반영한다.
- output (dataset):
  - RDF 현재 frame: `end_effector_position`, `object_position`, `action.raw`, `metadata.right_wrist_pose`, `metadata.pinch_strength`.
  - 추가해야 할 frame: `head_pose`, `retargeting_mode`, `retargeting_gain`, `xr_anchor_pose`, `tracking_target`.

## Dataset Structure

- state:
  - robot: end-effector pose, gripper state, joint state 가능하면 추가.
  - object: task object pose, target pose.
  - XR: right/left wrist, head pose, tracking validity.
- action:
  - raw Isaac action.
  - retargeted end-effector target.
  - gripper command.
- observation:
  - MVP-0는 state 중심.
  - MVP-1/learning export에서는 camera observation 또는 replay-derived visual observation 추가 필요.
- timestamp:
  - `t`, `step`은 이미 있다.
  - `xr_timestamp`, `sim_timestamp`, `recorded_at_monotonic` 추가 필요.

## Logging Strategy

- frequency:
  - Isaac env step마다 저장한다.
  - XR runtime이 72Hz이고 simulation이 60Hz일 수 있으므로 frame마다 `sim_fps`, `xr_frame_valid`, `frame_drop`을 남긴다.
- storage format:
  - 현재 JSON trajectory 유지.
  - training-ready export에서는 LeRobot/HDF5 변환기를 별도로 둔다.

## Implementation Details

- Isaac Lab docs는 OpenXR device가 raw tracking dictionary 또는 retargeted command를 제공하는 구조라고 설명한다.
- `DeviceBase.add_callback()` 경계가 있으므로 START/STOP/RESET/recenter 같은 operator command를 device callback에 붙일 수 있다.
- `Se3AbsRetargeter`는 절대 위치 기반이라 viewpoint/anchor mismatch에 취약할 수 있다.
- `Se3RelRetargeter`는 현재 RDF 문제인 “시점과 workspace가 안 맞는 느낌”을 줄이는 후보가 된다.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `apps/api/app/schemas/common.py`
  - `apps/api/app/services/evaluator.py`
- what module/function to modify:
  - `teleop_se3_agent.py`: `--rdf_recenter_on_start`, `--rdf_precision_mode`, `--rdf_retargeting_mode` 옵션 추가.
  - `rdf_isaac_runtime_recorder.py`: `_xr_metadata()`에 head pose, retargeter mode, anchor/recenter metadata 저장.
  - `TrajectoryFrame`: metadata는 dict라 migration 없이 확장 가능.
  - `evaluate_trajectory()`: `retargeting_jump`, `xr_frame_valid_after_warmup` quality gate 추가.

## Minimal Integration Plan

1. `rdf_isaac_runtime_recorder.py`의 `_xr_metadata()`에서 `teleop_interface` 내부 cache에서 head pose를 읽는 함수 추가.
2. first valid frame에서 `hmd_start_pose`, `right_wrist_start_pose`를 session summary에 저장.
3. `teleop_se3_agent.py`에 keyboard callback으로 `RDF_RECENTER`를 연결한다.
4. recenter 시점의 HMD/right wrist pose를 `retargeting_offset`으로 저장한다.
5. evaluator에 `retargeting_jump_max`와 `tracking_loss_after_warmup` metrics를 추가한다.

## Expected Impact

- 현재 사용자가 느낀 시점 불일치가 “측정 가능한 metadata”가 된다.
- absolute retargeting의 anchor drift를 replay/evaluation에서 확인할 수 있다.
- MVP-0 trajectory acceptance rate가 올라간다.

## What to Adopt

- Isaac Lab의 OpenXR retargeter 경계를 그대로 따른다.
- raw OpenXR pose와 retargeted action을 둘 다 저장한다.
- START/STOP/RESET/recenter를 callback command로 모델링한다.

## What to Avoid

- CloudXR를 현재 MVP에 도입하지 않는다. AGENTS.md에서 CloudXR는 금지 범위다.
- OpenXR raw pose만 저장하고 어떤 retargeter/gain을 썼는지 누락하지 않는다.

## Reference

- https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.devices.html
- https://isaac-sim.github.io/IsaacLab/main/source/how-to/cloudxr_teleoperation.html
