# Quest2ROS

## Overview

- problem: RDF 사용자는 Quest/Isaac AR 화면이 따라오더라도 실제 조작 시점과 robot workspace가 맞지 않아 불편함을 느꼈다.
- why it matters: Quest2ROS는 Quest 좌표계가 startup HMD pose에 임의로 잡히는 문제를 reference frame alignment 기능으로 해결한다. RDF의 현재 UX 문제와 직접 대응된다.

## System Architecture

- components:
  - Quest 2/3 standalone app.
  - Wi-Fi TCP endpoint.
  - ROS topics for pose/twist/buttons.
  - reference frame alignment UI.
  - haptic feedback subscriber.
- data flow:
  - Quest headset tracks controllers.
  - app streams controller pose, twist, inputs to TCP endpoint.
  - ROS bridge publishes topics.
  - robot control node subscribes and maps telemetry to robot command.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - left/right controller pose.
  - linear/angular velocity.
  - button state.
- processing (mapping -> robot action):
  - controller pose is transformed into a user-defined reference frame.
  - robot node consumes aligned Cartesian pose/twist.
- output (dataset):
  - PoseStamped/Twist/control inputs can be logged as trajectory source.
  - RDF should store both raw XR pose and aligned pose.

## Dataset Structure

- state:
  - robot state from Isaac.
  - aligned hand/controller pose.
  - raw hand/controller pose.
- action:
  - retargeted robot command.
  - optional velocity/twist command.
- observation:
  - current RDF state observation.
- timestamp:
  - Quest2ROS reports around 72 Hz topic frequency and latency measurement.
  - RDF should record `xr_sample_time`, `sim_step_time`, `api_receive_time`.

## Logging Strategy

- frequency:
  - about 72 Hz for Quest topic publishing.
  - RDF should record actual observed sample interval and jitter, not only nominal FPS.
- storage format:
  - RDF JSON trajectory with frame metadata.
  - calibration event in session metadata.

## Implementation Details

- Quest2ROS lets the operator align either controller to the desired robot/world reference frame, then press buttons for several seconds to set a new coordinate system.
- After alignment, all pose/twist data is expressed in that reference frame.
- The paper emphasizes no visual occlusion between headset and controller for stable tracking.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
  - `docs/DEBUGGING_GUIDE.md`
- what module/function to modify:
  - `rdf_isaac_runtime_recorder.py`: add `raw_right_wrist_pose`, `aligned_right_wrist_pose`, `calibration_transform`.
  - `teleop_se3_agent.py`: add recenter/calibrate command.
  - `evaluate_trajectory()`: add failure reason or metric for `RETARGETING_JUMP` if aligned pose jumps.

## Minimal Integration Plan

1. Add `--rdf_enable_calibration_metadata` flag default true.
2. On first valid handtracking frame, store `raw_origin_pose`.
3. Add key command `c` to set `calibration_transform` from current hand/HMD pose to task workspace center.
4. Store `calibration_transform` in trajectory summary and session runtime metrics.
5. Display calibration status in terminal logs and docs.

## Expected Impact

- 현재 사용자가 느낀 “시점이 너무 맞지 않다” 문제를 가장 작은 변화로 줄인다.
- replay에서 raw pose와 aligned pose를 비교해 calibration 실패를 분석할 수 있다.

## What to Adopt

- user-triggered reference frame alignment.
- raw pose and transformed pose both logged.
- tracking occlusion warning as quality gate.

## What to Avoid

- Quest2ROS/ROS stack 전체 도입.
- controller-only assumption. RDF primary input is Quest handtracking.

## Reference

- https://quest2ros.github.io/files/Quest2ROS.pdf
- https://quest2ros.github.io/q2r-web/
