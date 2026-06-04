# Robot Data Forge 구현 가속 Research Notes

이 폴더는 논문 요약 저장소가 아니다. AGENTS.md 기준의 현재 시스템, 즉 `Quest 3 handtracking -> ALVR + SteamVR/OpenXR -> Isaac Lab teleoperation -> Trajectory Recorder -> ForgeEval -> ForgeCurate -> Dataset Export`를 더 빨리 구현하기 위한 외부 구현체 역설계 노트다.

## Project Classification

Robot Data Forge는 네 가지 성격을 동시에 가진다.

1. VR teleoperation system
2. imitation learning data collection system
3. digital twin control system
4. sim-to-real pipeline

현재 구현 우선순위는 다음 순서다.

```text
1. VR teleoperation 안정화
2. trajectory/data quality metadata 강화
3. replay/evaluation/export 신뢰성 확보
4. LeRobot/HDF5 training-ready export
5. learning uplift validation
6. sim-to-real 확장
```

## Recommended Reading Order

1. [Isaac Lab OpenXR Device](./2026_isaac_lab_openxr_device.md)
2. [Quest2ROS](./2024_quest2ros.md)
3. [LeIsaac LeRobot Recorder](./2026_leisaac_lerobot_recorder.md)
4. [COLLAB-SIM](./2025_collab_sim.md)
5. [LeRobot Dataset v3](./2026_lerobot_dataset_v3.md)
6. [OPEN TEACH](./2024_open_teach.md)
7. [VisionProTeleop](./2024_visionproteleop.md)
8. [UMI](./2024_umi.md)
9. [ALOHA / ACT](./2023_aloha_act.md)
10. [Isaac Lab Mimic](./2024_isaac_lab_mimic.md)
11. [MimicGen](./2023_mimicgen.md)
12. [DROID](./2024_droid.md)
13. [ManiSkill 3 Dataset Tools](./2025_maniskill3.md)
14. [Open-TeleVision](./2024_open_television.md)
15. [BEAVR](./2025_beavr.md)

## Systems

| Rank | System | Group | 1-line summary | Relevance |
|---:|---|---|---|---:|
| 1 | Isaac Lab OpenXR Device | teleoperation | 현재 RDF handtracking path의 직접 구현 기준 | 5 |
| 2 | Quest2ROS | teleoperation | Quest 좌표계와 robot frame alignment 문제를 직접 해결 | 5 |
| 3 | LeIsaac LeRobot Recorder | imitation learning | Isaac Lab teleop 중 LeRobot-format recorder를 붙이는 가장 가까운 구현 | 5 |
| 4 | COLLAB-SIM | teleoperation | Isaac Sim + XR + VR demo collection + replay 구조 | 5 |
| 5 | LeRobot Dataset v3 | imitation learning | training-ready dataset export의 표준 후보 | 5 |
| 6 | OPEN TEACH | teleoperation | Quest 3 teleop server와 data collection module 분리 구조 | 4 |
| 7 | VisionProTeleop | system design | hand/head tracking, coordinate origin, recording metadata 설계가 우수 | 4 |
| 8 | UMI | imitation learning | relative action, latency matching, replay buffer generation | 4 |
| 9 | ALOHA / ACT | imitation learning | HDF5 episode layout과 ACT baseline format | 4 |
| 10 | Isaac Lab Mimic | sim-to-real | Isaac Lab native demo expansion path | 4 |
| 11 | MimicGen | sim-to-real | source demo를 subtask/object-centric synthetic data로 확장 | 3 |
| 12 | DROID | system design | diversity/calibration/session metadata를 dataset 품질로 관리 | 3 |
| 13 | ManiSkill 3 Dataset Tools | system design | raw trajectory + metadata + replay/convert workflow | 3 |
| 14 | Open-TeleVision | teleoperation | active visual feedback, replay verification, ACT training path | 3 |
| 15 | BEAVR | system design | Quest 3 teleop + LeRobot schema + policy evaluation dashboard 방향 | 3 |

## Grouping

### teleoperation

- [Isaac Lab OpenXR Device](./2026_isaac_lab_openxr_device.md)
- [Quest2ROS](./2024_quest2ros.md)
- [COLLAB-SIM](./2025_collab_sim.md)
- [OPEN TEACH](./2024_open_teach.md)
- [Open-TeleVision](./2024_open_television.md)
- [BEAVR](./2025_beavr.md)

### imitation learning

- [LeIsaac LeRobot Recorder](./2026_leisaac_lerobot_recorder.md)
- [LeRobot Dataset v3](./2026_lerobot_dataset_v3.md)
- [UMI](./2024_umi.md)
- [ALOHA / ACT](./2023_aloha_act.md)

### sim-to-real

- [Isaac Lab Mimic](./2024_isaac_lab_mimic.md)
- [MimicGen](./2023_mimicgen.md)
- [DROID](./2024_droid.md)

### system design

- [VisionProTeleop](./2024_visionproteleop.md)
- [ManiSkill 3 Dataset Tools](./2025_maniskill3.md)
- [BEAVR](./2025_beavr.md)
- [DROID](./2024_droid.md)

## Implementation Patterns Extracted

### 1. Recenter / Calibration Is Not Optional

Quest2ROS and VisionProTeleop both make coordinate frame/origin explicit. RDF currently relies on SteamVR/OpenXR/Isaac startup state, which explains the user-reported viewpoint mismatch.

Implement:

```text
teleop_se3_agent.py
  add key callback: c = calibrate/recenter

rdf_isaac_runtime_recorder.py
  store:
    raw_right_wrist_pose
    aligned_right_wrist_pose
    hmd_start_pose
    calibration_transform
    tracking_origin
```

### 2. Store Raw XR Pose and Retargeted Robot Action

Isaac Lab OpenXR separates raw tracking data and retargeted command. RDF should not store only the resulting action.

Implement:

```text
TrajectoryFrame.metadata.raw_xr
TrajectoryFrame.metadata.retargeted
TrajectoryFrame.action.raw
TrajectoryFrame.action.relative
```

### 3. Episode Lifecycle Must Be Command-Driven

COLLAB-SIM and ALOHA use explicit record/replay/reset workflows. RDF currently relies too much on closing Isaac to finish an episode.

Implement:

```text
teleop_se3_agent.py
  n = finish success and reset
  r = finish failure and reset
  c = recenter workspace

RdfIsaacRuntimeRecorder
  finish_and_restart(reason, success_hint)
```

### 4. Training Export Should Be Offline

LeIsaac can write LeRobot directly, but also warns it can add teleop delay. For RDF, avoid heavy encoding inside the live Isaac loop.

Implement:

```text
scripts/export_rdf_to_lerobot.py
scripts/export_rdf_to_act_hdf5.py
```

Keep live recorder JSON/state-first.

### 5. Quality Gates Should Include XR-Specific Metrics

RDF already has `TRACKING_LOSS`. Add metrics from Quest2ROS/BEAVR/UMI-style concerns.

Implement:

```text
tracking_loss_after_warmup
retargeting_jump_max
input_latency_ms_avg
input_latency_ms_max
frame_interval_jitter_ms
calibration_valid
first_gripper_close_position
```

### 6. Dataset Export Should Separate Raw / Accepted / Training

MimicGen and ManiSkill keep failed/generated/replay metadata visible. RDF should not silently discard useful diagnostic data.

Implement:

```text
raw export: all completed episodes
accepted export: ForgeCurate accepted episodes
training export: accepted + converted to LeRobot/HDF5
debug export: failures with failure_reason and runtime metrics
```

### 7. Replay Verification Is a Gate

Open-TeleVision, ALOHA, ManiSkill all include replay/inspection path.

Implement:

```text
apps/web/app/episodes/[episodeId]
  show EE path
  show object path
  show action timeline
  show tracking loss ranges
  show calibration transform

API
  use HumanReview as replay verification first
```

## What Should Be Implemented Next

### Immediate

1. `recenter/calibration` command in `teleop_se3_agent.py`.
2. raw/aligned XR pose metadata in `rdf_isaac_runtime_recorder.py`.
3. `retargeting_jump_max` and `tracking_loss_after_warmup` in `evaluate_trajectory()`.
4. replay page update showing action/EE/object paths and tracking loss ranges.

### Next

5. command-driven episode lifecycle: `success`, `failure`, `reset`, `continue`.
6. offline `export_rdf_to_lerobot.py`.
7. offline `export_rdf_to_act_hdf5.py`.
8. dataset-level stats: action mean/std, state mean/std, episode lengths.

### Later

9. Isaac Lab Mimic source-demo preparation.
10. camera/video observation export.
11. policy baseline runner for ACT or Diffusion Policy.
12. dataset diversity dashboard.

## What Should Be Changed

- Change recorder from “save whatever happens after app launch” to “save after calibration + warm-up + valid tracking”.
- Change episode finish from “close Isaac” to explicit operator lifecycle.
- Change export from one JSON path to three levels: raw/debug/training.
- Change KPI from count-only to quality + synchronization + learning value.

## What Should Be Removed or Avoided

- Do not add CloudXR to MVP. AGENTS.md forbids it.
- Do not add real robot control to MVP.
- Do not store images directly inside trajectory JSON.
- Do not treat `completed_episodes` as data quality.
- Do not export only successes without preserving failure/debug data.
- Do not call ManiSkill 3 Isaac-native. It is a reference for dataset tooling, not the primary simulator.
