# 데이터 스키마

공유 JSON schema 파일은 `packages/shared/` 아래에 둔다.

## External Robot Data Ingest v0 Source Drop

`External Robot Data Ingest / Evaluation v0`의 입력 source는 repo fixture가 아니라
외부에서 전달된 offline JSONL command/state drop이어야 한다. 현재 canonical package는
실제 external source가 없어 `external_ingest_contract_ready`만 claim하며,
`external_data_evaluated`를 claim하지 않는다.

필수 파일:

```text
metadata.json
accepted_command_state.jsonl
rejected_command_state.jsonl
PROVENANCE.md
LICENSE.txt
```

`metadata.json`의 v0 필수 source evidence:

```json
{
  "schema_version": "rdf_external_command_state_source_metadata_v0.1.0",
  "source_id": "external_ur_log_20260623_temp",
  "source_origin": "external_supplied_recorded_log",
  "source_acquisition": "file_drop",
  "source_owner": "Review Partner Lab",
  "source_license": "private_review",
  "source_redistribution_allowed": true,
  "provenance_trust_tier": "attested_file_drop",
  "recorded_log_backed": true,
  "generated_by_rdf": false,
  "repo_fixture": false,
  "robot_family_claimed": "universal_robots_ur",
  "embodiment_class_claimed": "industrial_arm",
  "command_stream": {
    "interface": "industrial_arm_command_fixture",
    "unit": "meters_radians_normalized_gripper"
  },
  "state_stream": {
    "interface": "industrial_arm_state_stream_fixture"
  },
  "coordinate_frames_declared": {
    "command_frame": "task_frame",
    "state_frame": "robot_base_frame"
  }
}
```

각 JSONL row는 최소한 아래 field를 포함해야 한다.

```json
{
  "sequence_id": 1,
  "timestamp": 0.04,
  "task_phase": "insert",
  "command": {
    "interface": "industrial_arm_command_fixture",
    "unit": "meters_radians_normalized_gripper",
    "vector": [0.011, -0.002, -0.036, 0.001, -0.001, 0.0, 0.28]
  },
  "state": {
    "interface": "industrial_arm_state_stream_fixture",
    "joint_positions": [0.0, -0.42, 0.19, -1.89, 0.0, 1.58, 0.77],
    "end_effector_position": [0.432, -0.016, 0.09],
    "end_effector_quaternion": [1.0, 0.0, 0.0, 0.0],
    "object_position": [0.44, -0.01, 0.06],
    "object_quaternion": [1.0, 0.0, 0.0, 0.0]
  },
  "action_semantics": {
    "representation": "robot_delta_ee_pose",
    "coordinate_frame": "task_frame",
    "normalized_contract_roles": [
      "teleop_intent",
      "executed_control",
      "learning_action",
      "retargeted_robot_action"
    ]
  },
  "quality": {
    "action_contract_valid": true,
    "replay_verified": true,
    "control_quality": "pass",
    "rejection_reason": null
  }
}
```

v0 committed/evaluated evidence는 `accepted_rows >= 4`, `rejected_rows == 1`을
요구한다. `rejected_command_state.jsonl`의 row는 failure predicate 또는
buyer-readable `rejection_reason`을 포함해야 한다.

Raw `metadata.json`은 adapter-only field를 요구하지 않는다. RDF는 이를
`data/staging/metadata.json`으로 결정적으로 파생하고,
`staging_derivation_report.json`에 raw/staging/source row hash를 묶는다.
Offline verifier는 이 데이터 일관성을 재계산하지만, metadata에 적힌 외부 origin이
실제 물리 로그인지 암호학적으로 증명하지는 못한다.

## Episode Lifecycle

Episode lifecycle은 evaluator success와 분리한다. 즉, 사람이 episode를 `failure`로 finalize하더라도 evaluator가 trajectory를 task success로 판정할 수 있고, 반대로 사람이 `success`로 finalize했더라도 quality gate에서 evaluator failure가 날 수 있다.

신규 lifecycle status:

```text
running
success
failure
reset
incomplete
```

Legacy status:

```text
recording
completed
invalid
```

Legacy row는 읽을 수 있게 유지하지만 신규 episode start는 `running`을 사용한다.

Episode DB metadata:

```json
{
  "status": "failure",
  "started_at": "2026-05-01T00:00:00Z",
  "ended_at": "2026-05-01T00:00:12Z",
  "finalize_reason": "operator_failure",
  "failure_reason": "OPERATOR_MARKED_FAILURE",
  "failure_note": "Operator stopped because hand mapping felt wrong.",
  "reset_count": 1,
  "accepted": false,
  "replayable": true
}
```

Trajectory summary에는 같은 lifecycle metadata를 optional field로 저장한다.

```json
{
  "summary": {
    "episode_status": "reset",
    "episode_started_at": "2026-05-01T00:00:00Z",
    "episode_finalized_at": "2026-05-01T00:00:12Z",
    "episode_finalize_reason": "operator_reset",
    "episode_failure_reason": null,
    "episode_failure_note": null,
    "reset_count": 2
  }
}
```

`incomplete`는 Isaac shutdown, runtime error, 또는 operator finalize 없이 종료된 episode를 표시한다. `reset`은 task success/failure가 아니라 operator가 environment를 다시 시작한 episode임을 표시한다.

## Trajectory Frame 확장 필드

기존 reader를 깨지 않기 위해 새 XR/calibration 정보는 기존 `TrajectoryFrame.action`과 `TrajectoryFrame.metadata` 내부의 optional nested field로만 추가한다.

필수 기존 구조:

```json
{
  "t": 0.0,
  "step": 0,
  "end_effector_position": [0.5, 0.1, 0.2],
  "object_position": [0.4, 0.0, 0.0609],
  "action": {},
  "metadata": {}
}
```

추가되는 action field:

```json
{
  "action": {
    "raw": [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0],
    "applied": [0.045, 0.0, -0.045, 0.0, 0.0, 0.07, 1.0],
    "teleoperation_active": true,
    "pinch_or_gripper": 1.0,
    "relative": {
      "delta_position": [0.045, 0.0, -0.045],
      "delta_rotation": [0.0, 0.0, 0.07],
      "gripper": 1.0
    },
    "teleop_intent": {
      "command": [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0],
      "role": "operator_intent",
      "representation": "openxr_retargeted_delta_ee_pose_plus_gripper",
      "source": "teleop_interface.advance",
      "coordinate_frame": "openxr_retargeter_output"
    },
    "executed_control": {
      "command": [0.045, 0.0, -0.045, 0.0, 0.0, 0.07, 1.0],
      "role": "robot_control_command",
      "representation": "delta_ee_pose_plus_gripper",
      "source": "rdf_live_teleop_controller",
      "control_mode": "bounded_direct_ee_target",
      "control_semantics": "bounded_direct_end_effector_target_servo",
      "applied_to_env": true
    },
    "learning_action": {
      "command": [0.045, 0.0, -0.045, 0.0, 0.0, 0.07, 1.0],
      "role": "candidate_robot_action_for_learning",
      "representation": "delta_ee_pose_plus_gripper",
      "source": "executed_control",
      "validation_state": "requires_evaluation_and_curation",
      "dataset_semantics": "not_learning_ready_until_curated"
    },
    "retargeted_robot_action": {
      "command": [0.045, 0.0, -0.045, 0.0, 0.0, 0.07, 1.0],
      "action_type": "delta_ee_pose_plus_gripper",
      "source": "teleop_interface.advance",
      "applied_to_env": true
    },
    "control_filter": {
      "name": "rdf_teleop_action_filter",
      "applied": true,
      "config": {
        "position_gain": 0.45,
        "rotation_gain": 0.35,
        "position_axis_map": "x,z,y",
        "rotation_axis_map": "x,y,z"
      }
    }
  }
}
```

`action.raw`는 Isaac OpenXR retargeter가 만든 원본 command다. `action.applied`와 `action.retargeted_robot_action.command`는 기존 호환 필드다. 새 contract에서는 역할을 더 명확히 나눈다.

- `action.teleop_intent`: operator/XR retargeter가 낸 조작 의도. 학습용으로 검증됐다는 뜻이 아니다.
- `action.executed_control`: Isaac robot controller에 실제 적용한 command.
- `action.learning_action`: export/training 후보 action. evaluator와 curator를 통과하기 전까지 learning-ready라고 주장하지 않는다.

`Isaac-Forge-PegInsert-Direct-v0` 같은 Forge direct insertion task의 native action은 current pose delta가 아니라 fixed asset/hole 기준 normalized target으로 해석된다. 이 semantics는 policy benchmark에는 맞지만 Quest handtracking live teleop 수집 UX에는 맞지 않는다. Live handtracking에서는 `RDF_TELEOP_CONTROL_MODE=auto`가 Forge PegInsert에서 `bounded_direct_ee_target`으로 해석된다. `bounded_direct_ee_target`은 OpenXR retargeter delta를 recentered EEF anchor 기준 absolute desired end-effector target으로 재구성하고, robot fingertip이 workspace clamp, max-step/rate-limit, smoothing을 거쳐 그 target을 따라가게 한다. Quest/OpenXR는 Y-up이고 Isaac robot workspace는 Z-up이므로 live default `position_axis_map`은 `x,z,y`다. 이 경우 frame metadata의 `control_filter.teleop_control_mode.name`은 `bounded_direct_ee_target`, `control_semantics`는 `bounded_direct_end_effector_target_servo`가 된다. `operator_follow`, `cartesian_delta`, `forge_asset_relative_delta_adapter`는 legacy/debug path로만 사용한다.

추가되는 metadata field:

```json
{
  "metadata": {
    "teleop_pipeline": {
      "schema_version": "rdf_xr_teleop_dataset_pipeline_v0.1.0",
      "product_role": "xr_teleop_trajectory_to_validated_learning_dataset",
      "teleop_intent_field": "action.teleop_intent",
      "executed_control_field": "action.executed_control",
      "learning_action_field": "action.learning_action",
      "learning_action_status": "candidate_requires_evaluation_and_curation"
    },
    "raw_xr": {
      "tracking_origin": "steamvr_openxr_virtual_world",
      "right_wrist_pose": [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0],
      "left_wrist_pose": [],
      "head_pose": [],
      "right_hand_joints": {
        "wrist": [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]
      }
    },
    "aligned_xr": {
      "tracking_origin": "rdf_calibrated_workspace",
      "right_wrist_pose": [0.5, 0.1, 0.2, 1.0, 0.0, 0.0, 0.0],
      "calibration_id": "calib_001",
      "calibration_valid": true,
      "calibration_reason": "operator_command",
      "translation_offset": [0.4, -0.1, -0.1],
      "rotation_offset_quat": [1.0, 0.0, 0.0, 0.0],
      "position_gain": 0.45,
      "control_filter": {
        "name": "rdf_teleop_action_filter"
      }
    },
    "retargeted": {
      "robot_action": [0.045, 0.0, -0.045, 0.0, 0.0, 0.07, 1.0],
      "raw_robot_action": [0.1, 0.0, -0.1, 0.0, 0.0, 0.2, 1.0],
      "action_type": "delta_ee_pose_plus_gripper",
      "applied_to_env": true,
      "source": "teleop_interface.advance",
      "control_filter": {
        "name": "rdf_teleop_action_filter"
      }
    },
    "calibration": {
      "calibration_id": "calib_001",
      "status": "calibrated",
      "type": "workspace_alignment_v2"
    }
  }
}
```

`raw_wrist_direct_ee_target` mode에서는 `action.raw_wrist_direct`와
`metadata.control_filter.teleop_control_mode.raw_wrist_direct_control`에 raw-wrist direct control evidence가
저장된다. Valid-to-valid raw wrist spike가 `raw_wrist_jump_reject_m`를 넘으면 controller는 즉시 새 pose로
rebase하지 않고 robot action을 held 처리한 뒤 `raw_wrist_reacquire_valid_frames`만큼 안정적인 후보 frame을
기다린다. 단일 frame spike가 원래 wrist neighborhood로 돌아오면 기존 origin을 유지하고 다음 valid frame을
accepted로 기록한다.

```json
{
  "action": {
    "executed_control": {
      "control_mode": "raw_wrist_direct_ee_target"
    },
    "raw_wrist_direct": {
      "input_source": "raw_right_wrist_pose",
      "gate_state": "held",
      "gate_reason": "raw_wrist_spike_reacquire_pending",
      "raw_wrist_pose": [0.3, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
      "raw_wrist_origin_pose": [0.0, 0.0, 0.0],
      "wrist_offset_raw": [0.0, 0.0, 0.0],
      "wrist_offset_robot": [0.0, 0.0, 0.0],
      "valid_to_valid_jump_m": 0.28,
      "raw_wrist_jump_warn_m": 0.1,
      "raw_wrist_jump_reject_m": 0.15,
      "raw_wrist_reacquire_valid_count": 1,
      "raw_wrist_reacquire_required_frames": 3,
      "raw_wrist_reacquire_stable_m": 0.03,
      "retargeted_action_for_comparison": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]
    }
  }
}
```

추가되는 runtime boundary metadata:

```json
{
  "metadata": {
    "sim_step_boundary": {
      "schema_version": "rdf_sim_step_boundary_v0.1.0",
      "source": "isaac_env_step_return",
      "env_step_return_available": true,
      "terminated": {
        "available": true,
        "any": true,
        "all": true,
        "true_count": 1,
        "count": 1
      },
      "truncated": {
        "available": true,
        "any": false,
        "all": false,
        "true_count": 0,
        "count": 1
      },
      "done": {
        "available": true,
        "any": true,
        "all": true,
        "true_count": 1,
        "count": 1
      },
      "reset_boundary": true,
      "reset_boundary_reason": "terminated",
      "info_keys": ["final_observation"]
    }
  }
}
```

`sim_step_boundary`는 IsaacLab `env.step()` 반환값의 `terminated` / `truncated` / legacy `done` / `info` key를 저장한 boundary evidence다. Recorder는 reset boundary frame을 raw trajectory 안에 보존하고, summary에는 `sim_reset_boundary_frame_count`, `sim_reset_boundary_frames`를 남긴다. 이 metadata는 trajectory를 자동 split하지 않는다. H15 같은 scene-state discontinuity가 발생했을 때 hidden env reset인지 recorder boundary 누락인지 판정하기 위한 증거다.

## Camera Conditioning Metadata

ForgeXR dataset은 `action-contract-valid`, `replay-verified`뿐 아니라 `camera-conditioning-ready` 여부를 별도 gate로 기록한다. 이유는 operator/HMD 시점, Isaac camera, robot base, EEF, task object frame이 달라지면 같은 hand motion이라도 화면에서 보이는 방향과 downstream visual policy가 받아들이는 조건이 달라지기 때문이다.

원칙:

- Raw XR/HMD pose와 raw robot/action label은 보존한다.
- Camera/view 기반 보정은 raw action을 덮어쓰지 않고 derived metadata/action view로 추가한다.
- Camera geometry가 부족한 trajectory도 raw evidence로 저장한다. 다만 `camera_conditioning_ready=false`이면 camera-conditioned 학습/증명 material로 승격하지 않는다.
- 최소 frame chain은 `world -> robot_base -> end_effector -> task/object -> camera/operator_view`를 복원할 수 있어야 한다.

추가되는 optional metadata field:

```json
{
  "metadata": {
    "camera_conditioning": {
      "schema_version": "rdf_camera_conditioning_v0.1.0",
      "status": "raw_geometry_recorded",
      "camera_conditioning_ready": false,
      "camera_id": "hmd_xr_camera",
      "operator_view_frame": "hmd_xr_camera",
      "frames": {
        "world": "isaac_world",
        "robot_base": "franka_base",
        "end_effector": "franka_fingertip_midpoint",
        "task": "peg_in_hole_hole_target",
        "camera": "hmd_xr_camera"
      },
      "camera_pose": {
        "T_world_camera": [],
        "source": "openxr_hmd_pose",
        "timestamp_source": "frame_metadata"
      },
      "transforms": {
        "T_world_robot_base": [],
        "T_world_end_effector": [],
        "T_world_task_target": [],
        "T_camera_end_effector": [],
        "T_camera_task_target": []
      },
      "intrinsics": {
        "model": "xr_runtime_projection",
        "fx": null,
        "fy": null,
        "cx": null,
        "cy": null,
        "width": null,
        "height": null,
        "source": "unknown"
      },
      "visibility": {
        "end_effector_visible": null,
        "task_target_visible": null,
        "held_object_visible": null,
        "occlusion_status": "unknown"
      },
      "derived_action_frames": {
        "robot_world_action": "action.executed_control",
        "robot_base_action": null,
        "eef_relative_action": null,
        "camera_relative_action": null,
        "operator_view_relative_action": null
      },
      "readiness": {
        "intrinsics_present": false,
        "extrinsics_present": false,
        "time_aligned": false,
        "task_objects_visible": false,
        "projection_smoke_passed": false,
        "failure_reasons": ["CAMERA_EXTRINSICS_MISSING"]
      }
    }
  }
}
```

Camera conditioning failure reasons:

```text
CAMERA_INTRINSICS_MISSING
CAMERA_EXTRINSICS_MISSING
CAMERA_TIME_UNSYNCED
TASK_OBJECT_OUT_OF_VIEW
LOW_VISIBILITY
PROJECTION_SMOKE_FAILED
DERIVED_CAMERA_ACTION_UNAVAILABLE
CAMERA_CONDITIONING_NOT_READY
```

Derived action labels are semantic views over the same episode, not replacements:

- `robot_world_action`: Isaac/world frame control view.
- `robot_base_action`: robot base frame control view.
- `eef_relative_action`: end-effector local frame action view.
- `camera_relative_action`: camera optical/view frame action view.
- `operator_view_relative_action`: HMD/operator view frame action view used for camera-conditioned learning.

## Trajectory Summary 확장 필드

Recorder는 episode summary에 calibration history를 저장한다.

```json
{
  "summary": {
    "auto_calibrate_on_first_valid": true,
    "calibration": {
      "calibration_id": "calib_001",
      "type": "workspace_alignment_v2",
      "translation_only_compatible": true,
      "reason": "auto_robot_start_box",
      "tracking_origin": "steamvr_openxr_virtual_world",
      "aligned_origin": "rdf_robot_workspace",
      "raw_origin_pose": [0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0],
      "aligned_origin_pose": [0.5, 0.1, 0.2, 1.0, 0.0, 0.0, 0.0],
      "translation_offset": [0.4, -0.1, -0.1],
      "rotation_offset_quat": [1.0, 0.0, 0.0, 0.0],
      "position_gain": 0.45,
      "control_filter": {
        "name": "rdf_teleop_action_filter"
      }
    },
    "calibration_events": [],
    "control_filter": {
      "name": "rdf_teleop_action_filter",
      "applied": true
    }
  }
}
```

Calibration은 현재 backward-compatible하게 translation offset을 계속 저장한다. 신규 `workspace_alignment_v2`는 raw XR right wrist pose를 recenter 완료 시점의 robot end-effector pose에 맞추는 translation, orientation alignment용 `rotation_offset_quat`, action filter gain metadata를 추가한다.

Episode summary는 frame-level camera metadata를 요약해 readiness를 빠르게 판정할 수 있어야 한다.

```json
{
  "summary": {
    "camera_conditioning": {
      "schema_version": "rdf_camera_conditioning_v0.1.0",
      "camera_conditioning_ready": false,
      "status": "not_ready",
      "camera_ids": ["hmd_xr_camera"],
      "operator_view_frame": "hmd_xr_camera",
      "frames_recorded": ["world", "robot_base", "end_effector", "task", "camera"],
      "derived_action_frames": ["robot_world_action"],
      "readiness_failure_reasons": [
        "CAMERA_INTRINSICS_MISSING",
        "PROJECTION_SMOKE_FAILED"
      ]
    }
  }
}
```

HMD live collection의 primary recenter는 `robot_start_box` mode다. 이 mode에서는 operator의 첫 stable hand pose를 곧바로 기준점으로 쓰지 않는다. Episode/reset마다 robot-space start box를 만들고, valid right-hand tracking과 robot EEF/fingertip inside-box 조건이 `RDF_AUTO_RECENTER_VALID_FRAMES` 동안 유지된 뒤에 calibration event를 만든다.

Runtime recenter contract:

```text
RDF_RECENTER_MODE=robot_start_box
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08
RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01
RDF_RECENTER_BOX_HALF_EXTENTS=0.04,0.04,0.04
RDF_RECENTER_BOX_VISUAL=0
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1
RDF_RECENTER_SETUP_CONTROL=1
```

`RDF_RECENTER_BOX_RANDOM_OFFSET`은 reset마다 한 번만 샘플링되고 episode 동안 고정된다. Recenter 전 setup-only control은 robot을 start box 안으로 넣기 위한 동작이며, trajectory recording/warmup frame으로 저장하지 않는다. 세부 UX와 로그 계약은 [`docs/experiments/hmd/hmd_recenter_start_box.md`](../experiments/hmd/hmd_recenter_start_box.md)를 따른다.

Teleoperation control은 live loop에서 optional `rdf_teleop_action_filter`를 통해 조정된다. 이 filter는 position/rotation gain, deadzone, smoothing, signed axis remap을 적용한다. Terminal `P` recenter는 fallback/debug command이며 primary HMD collection flow가 아니다.

## Evaluation Runtime Quality Metrics

`Evaluation.metrics`는 JSON object이므로 DB migration 없이 runtime quality metric을 추가한다. 기존 reader를 깨지 않도록 모든 새 field는 optional로 취급한다.

Stored evaluation JSON은 DB row와 별도로 offline export에서 trajectory와 metric을 안정적으로 pair할 수 있도록 다음 metadata를 포함한다.

```json
{
  "id": "eval_001",
  "trajectory_id": "traj_001",
  "episode_id": "episode_001",
  "task_id": "task_001",
  "evaluated_at": "2026-05-01T00:00:00Z",
  "success": true,
  "failure_reason": null,
  "metrics": {}
}
```

`trajectory_id`, `episode_id`, `task_id`, `evaluated_at`은 신규 저장분에 포함된다. 기존 evaluation JSON에는 이 field가 없을 수 있으므로 reader/exporter는 optional로 처리한다.

추가되는 metric:

```json
{
  "tracking_loss_after_warmup": 0.03,
  "post_warmup_frame_count": 300,
  "retargeting_jump_max": 0.08,
  "retargeting_jump_mean": 0.02,
  "raw_wrist_valid_to_valid_jump": {
    "fail": false,
    "evidence_available": true,
    "threshold_m": 0.1,
    "max_m": 0.04,
    "mean_m": 0.01,
    "count_over_threshold": 0,
    "policy": "reject_training_candidate_on_raw_wrist_valid_to_valid_jump"
  },
  "average_input_latency_ms": 35.0,
  "max_input_latency_ms": 80.0,
  "frame_interval_mean_ms": 16.7,
  "frame_interval_jitter_ms": 4.2
}
```

Quality gate threshold는 `Task.success_criteria` 또는 `Task.environment_config`에 아래 key로 둘 수 있다.

```json
{
  "max_tracking_loss_after_warmup": 0.3,
  "max_retargeting_jump": 0.25,
  "max_raw_wrist_valid_to_valid_jump_m": 0.1,
  "max_average_input_latency_ms": 120,
  "max_input_latency_ms": 250,
  "max_frame_interval_jitter_ms": 50
}
```

Threshold가 없는 `retargeting_jump`, latency, jitter metric은 기록만 하고 실패 판정에는 사용하지 않는다. `tracking_loss_after_warmup`은 기존 `TRACKING_LOSS > 0.3` 동작을 보존하기 위해 기본 threshold `0.3`을 사용한다. `raw_wrist_valid_to_valid_jump`는 raw-wrist direct control evidence가 있는 경우 기본 threshold `0.10m`를 사용해 `RAW_WRIST_JUMP` data-quality failure로 training eligibility를 차단한다.

## Offline HDF5 Export Schema

Live recorder의 source of truth는 계속 JSON trajectory다. HDF5는 recording 완료 후 실행하는 offline training export format이다.

Top-level group:

```text
/episodes
/observations
/states
/actions
/timestamps
/metadata
/evaluation
```

각 episode는 동일한 `episode_id` subgroup으로 저장한다.

```text
/observations/<episode_id>/raw_xr_right_wrist_pose
/observations/<episode_id>/aligned_xr_right_wrist_pose
/actions/<episode_id>/retargeted_robot_action
/states/<episode_id>/robot_end_effector_position
/timestamps/<episode_id>/t
/metadata/<episode_id>/lifecycle_json
/evaluation/<episode_id>/metrics_json
```

Lifecycle filtering:

```text
default:
  success only

optional:
  --include-failure
  --include-reset
  --include-incomplete
```

Exporter는 `summary.episode_status`를 우선 사용한다. 오래된 recording처럼 lifecycle metadata가 없으면 `summary.complete_reason` 또는 `evaluation.success`로 legacy inference를 수행하고, 그 사실을 `lifecycle_json.episode_status_inferred`에 남긴다.

Evaluation pairing 순서:

```text
1. evaluation.trajectory_id == trajectory.id
2. evaluation.episode_id == trajectory.episode_id
3. trajectory/evaluation이 각각 1개뿐인 legacy unlinked fallback
```

Pairing 결과는 HDF5에 `evaluation_pairing_source`로 남긴다. Evaluation metrics는 optional이다. Metrics가 없어도 export 자체는 실패하지 않고 warning만 남긴다.

상세 mapping은 `docs/EXPORT_FORMAT.md`를 기준으로 한다.

## Quality Infrastructure Schema

이번 단계부터 live recorder format은 유지하되, episode finalize 이후 다음 파생 품질 모델을 저장한다. 기존 trajectory JSON reader는 새 field를 optional로 처리해야 한다.

### SyncMetrics

`SyncMetrics`는 XR input, Isaac simulation, recorder timestamp 정렬 품질을 episode/trajectory 단위로 남긴다.

```json
{
  "id": "sync_001",
  "episode_id": "episode_001",
  "trajectory_id": "traj_001",
  "collection_session_id": "session_001",
  "schema_version": "0.1.0",
  "quality_score": 0.86,
  "metrics_json": {
    "schema_version": "sync_metrics_v0.1.0",
    "frame_count": 300,
    "timestamp_count": 300,
    "timestamp_source": "isaac_sim",
    "timestamp_monotonic": true,
    "frame_interval_mean_ms": 16.7,
    "frame_interval_jitter_ms": 4.2,
    "frame_drop_rate": 0.01,
    "hand_tracking_loss_rate": 0.02,
    "hand_tracking_loss_after_warmup": 0.01,
    "average_input_latency_ms": 35.0,
    "max_input_latency_ms": 80.0,
    "sync_error_ms_mean": 3.0,
    "sync_error_ms_p95": 6.0,
    "sync_error_source": "frame_metadata",
    "quality_score": 0.86,
    "warnings": []
  }
}
```

`sync_error_ms`가 frame metadata에 없으면 `sync_error_ms_mean`과 `sync_error_ms_p95`는 `null`이고 `warnings`에 `sync_error_ms_unavailable`이 들어간다. 측정되지 않은 값을 측정값처럼 보정하지 않는다.

### DataUsabilityScore

`DataUsabilityScore`는 success 여부와 별개로 학습에 쓸 수 있는 trajectory인지 판단하기 위한 score다.

```json
{
  "id": "usable_001",
  "episode_id": "episode_001",
  "trajectory_id": "traj_001",
  "evaluation_id": "eval_001",
  "schema_version": "0.1.0",
  "score": 0.82,
  "usable": true,
  "rejection_reasons_json": [],
  "components_json": {
    "replayable_score": 1.0,
    "sync_quality_score": 0.86,
    "required_modality_score": 1.0,
    "evaluator_confidence_score": 0.8,
    "physical_plausibility_score": 0.9
  }
}
```

기본 hard rejection:

```text
NOT_REPLAYABLE
MISSING_MODALITY:frames
MISSING_MODALITY:end_effector_position
MISSING_MODALITY:object_position
LOW_DATA_USABILITY_SCORE
```

`raw_xr_pose`, `aligned_xr_pose` 누락은 현재 backward compatibility 때문에 score 하락과 reason 기록으로 처리하되, legacy recording 전체를 무조건 실패시키지는 않는다.

### ActionSegment

Action phase는 frame metadata에 `action_phase` 또는 `phase`가 있을 때 그대로 segment로 묶는다. 아직 phase 정보가 없으면 하나의 `UNKNOWN` segment를 생성한다.

```json
{
  "id": "seg_001",
  "episode_id": "episode_001",
  "trajectory_id": "traj_001",
  "phase": "APPROACH",
  "start_frame": 0,
  "end_frame": 42,
  "confidence": 1.0,
  "source": "frame_metadata",
  "metadata_json": {}
}
```

지원 phase:

```text
APPROACH
ALIGN
CONTACT
INSERT
SEAT
STABILIZE
RELEASE
RECOVER
UNKNOWN
```

MVP-1 insertion task에서는 `SEAT`를 final seating / fully inserted stabilization 전후 구간에 사용한다. 기존 `STABILIZE`는 broader stabilization phase로 유지한다.

### Manipulation-aware Evaluation Fields

`Evaluation` row와 stored evaluation JSON은 기존 success/failure/quality field를 유지하면서 다음 field를 optional-compatible하게 포함한다.

```json
{
  "task_completion_score": 0.9,
  "interaction_quality_score": 0.8,
  "contact_sequence_score": 0.5,
  "physical_plausibility_score": 0.9,
  "data_usability_score": 0.82,
  "evaluator_confidence": 0.84,
  "failure_mode": "SUCCESS"
}
```

`contact_sequence_score=0.5`는 현재 contact sequence signal이 없다는 conservative placeholder다. 실제 contact sequence를 측정한 값처럼 해석하면 안 된다.

### MVP-1 Evaluation Semantics

MVP-1부터 `evaluation.success` 하나로 task outcome, data quality, replay validity, curation eligibility를 모두 해석하지 않는다. Backward compatibility를 위해 top-level `evaluation.success`는 기존 validated evaluator success로 유지하고, 세부 의미는 `metrics` 아래에 분리해 저장한다.

```json
{
  "failure_reason": "RETARGETING_JUMP",
  "failure_category": "DATA_QUALITY_FAILURE",
  "metrics": {
    "evaluation_semantics_version": "rdf_evaluation_semantics_v0.1.0",
    "failure_category": "DATA_QUALITY_FAILURE",
    "task_outcome": {
      "operator_success": true,
      "auto_success_ready": false,
      "success_label_source": "operator",
      "evaluator_task_success": "unknown",
      "task_success_confidence": null,
      "task_failure_reason": null
    },
    "data_quality": {
      "replay_verified": false,
      "action_contract_valid": true,
      "action_contract_status": "pass",
      "retargeting_jump": "fail",
      "raw_wrist_valid_to_valid_jump": "fail",
      "native_action_saturation": "fail",
      "native_action_saturation_ratio": 0.18,
      "scene_state_discontinuity": {
        "fail": true,
        "frames": [172],
        "static_task_target_frames": [172],
        "dynamic_body_frames": [172],
        "policy": "reject_training_candidate_on_static_task_target_jump"
      },
      "sync_quality": "pass",
      "control_quality": "fail",
      "quality_failure_reasons": ["SCENE_STATE_DISCONTINUITY"]
    },
    "curation": {
      "raw_saved": true,
      "human_success_pool": true,
      "task_success_candidate_pool": true,
      "training_eligible": false,
      "curated_accepted": false,
      "proof_eligible": false,
      "rejection_reasons": [
        "REPLAY_NOT_VERIFIED",
        "EVALUATION_FAILED",
        "SCENE_STATE_DISCONTINUITY"
      ]
    }
  }
}
```

`metrics.task_outcome.evaluator_task_success`는 boolean이 아니라 tri-state다.

```text
true     evaluator가 task success를 확인했다.
false    evaluator가 task outcome failure를 확인했다.
unknown  data/control/replay/metadata 문제가 먼저 걸렸거나 object state만으로 task success를 안정적으로 판정할 수 없다.
```

`failure_category` taxonomy:

```text
TASK_OUTCOME_FAILURE
DATA_QUALITY_FAILURE
REPLAY_FAILURE
ACTION_CONTRACT_FAILURE
METADATA_FAILURE
UNKNOWN
```

`RETARGETING_JUMP`, `RAW_WRIST_JUMP`, `SCENE_STATE_DISCONTINUITY`는 task failure가 아니라 `DATA_QUALITY_FAILURE`다. 즉 사용자가 HMD에서 성공했다고 판단한 trajectory는 `operator_success=true`, `human_success_pool=true`로 raw evidence에 남을 수 있다. 다만 replay/action/data-quality gate를 통과하기 전까지 `training_eligible`, `curated_accepted`, `proof_eligible`은 `false`다.

`metrics.raw_wrist_valid_to_valid_jump`는 `action.raw_wrist_direct.valid_to_valid_jump_m` 또는 호환 `raw_wrist_jump_m` evidence를 집계한다. `threshold_m` 초과 event가 하나라도 있으면 `failure_reason=RAW_WRIST_JUMP`가 될 수 있으며, `quality_failure_reasons`와 `curation.rejection_reasons`에 같은 이유를 남긴다.

`metrics.scene_state_discontinuity`는 peg-in-hole evaluator가 frame 간 scene-state jump를 감지했을 때 기록한다. EEF/object/peg 같은 dynamic body jump는 evidence로 보존하지만 그 자체만으로 hard reject하지 않는다. `hole_position` 또는 `hole_target_position` 같은 static task target이 한 recorded trajectory 안에서 2cm 이상 이동하면 hidden env reset, task-state teleport, recorder boundary 누락 가능성이 높으므로 `SCENE_STATE_DISCONTINUITY`로 training eligibility를 차단한다.

Camera conditioning도 task success와 분리한다. Peg insertion이 성공하고 replay/action gate를 통과하더라도 camera intrinsics/extrinsics, HMD pose time alignment, task-object visibility, projection smoke가 부족하면 `camera_conditioning_ready=false`로 남긴다. 이 경우 raw trajectory와 robot-frame learning action은 보존하지만, camera-conditioned visual policy 또는 view-conditioned dataset claim에는 사용하지 않는다.

HMD task guidance가 `SUCCESS_READY` 조건을 안정적으로 만족해 자동 finalize하는 경우 summary에는 아래 lifecycle metadata가 추가될 수 있다.

```json
{
  "summary": {
    "episode_status": "success",
    "episode_finalize_reason": "auto_success_ready",
    "success_label_source": "task_state_auto",
    "operator_success": false,
    "auto_success_ready": true,
    "success_ready_hold_sec": 1.533,
    "task_guidance_status": {
      "status": "AUTO_FINALIZE_READY",
      "phase": "SEAT",
      "success_ready": true,
      "hold_complete": true,
      "distance_ok": true,
      "alignment_ok": true,
      "depth_ok": true
    }
  }
}
```

이 경우 `metrics.task_outcome.operator_success=false`, `metrics.task_outcome.auto_success_ready=true`, `metrics.curation.human_success_pool=false`, `metrics.curation.task_success_candidate_pool=true`가 된다. 즉 자동 success는 human label이 아니라 task-state 기반 success candidate다. 학습/증명 승격은 여전히 evaluator success, replay verification, action contract, data-quality gate를 통과해야 한다.

### MVP-1 Peg-in-Hole Task State

MVP-1 peg-in-hole / insertion task는 base trajectory schema를 바꾸지 않고 frame metadata에 optional task-specific state를 추가한다.

```json
{
  "frames": [
    {
      "metadata": {
        "task_state": {
          "peg_tip_distance_to_target": 0.008,
          "axis_alignment_error_rad": 0.08,
          "insertion_depth": 0.032,
          "contact_sequence_valid": true,
          "object_drop_detected": false
        }
      }
    }
  ]
}
```

지원 field:

```text
peg_tip_distance_to_target
peg_tip_distance_to_hole_bottom
axis_alignment_error_rad
peg_axis_alignment_error_rad
insertion_depth
contact_sequence_valid
object_drop_detected
object_dropped
```

Task가 `peg_in_hole` 계열이고 위 task_state가 있으면 evaluator는 generic target distance 평가 대신 insertion-specific metric을 사용한다.

추가 evaluator metric:

```text
peg_tip_distance_to_target
axis_alignment_error_rad
insertion_depth
stable_final_steps
contact_sequence_valid
object_drop_detected
axis_alignment_score
insertion_depth_score
```

추가 failure reason:

```text
ALIGNMENT_ERROR
INSUFFICIENT_INSERTION_DEPTH
```

주의:

- 이 변경은 live recorder schema redesign이 아니다.
- `metadata.task_state`가 없으면 기존 generic evaluator 경로를 그대로 사용한다.
- Isaac stack smoke task에서 명시적으로 `RDF_PEG_ASSET_NAME` / `RDF_HOLE_ASSET_NAME`을 주지 않으면 recorder는 기존 cube 기반 state를 유지한다.
- Isaac `Factory` / `Forge` Direct peg insertion task에서는 recorder가 기본적으로 `held_asset`을 peg, `fixed_asset`을 hole로 해석한다.
- `RDF_PEG_TIP_LOCAL_OFFSET`, `RDF_HOLE_TARGET_LOCAL_OFFSET`, `RDF_INSERTION_AXIS_WORLD`는 실제 Isaac asset origin이 success 기준과 어긋날 때 live calibration 값으로 조정한다.

## HMD Run Log Summary Artifact

`run_hmd_axis_debug.sh`는 physical HMD validation run의 terminal output을 자동 저장하고, `summarize_hmd_run_log.py`가 로그와 최신 RDF artifact를 합쳐 summary JSON을 만든다.

파일 위치:

```text
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log.summary.json
```

Schema version:

```text
rdf_hmd_run_log_summary_v0.1.0
```

핵심 field:

```json
{
  "schema_version": "rdf_hmd_run_log_summary_v0.1.0",
  "files": {
    "log": "storage/logs/hmd_axis_debug/hmd_axis_debug_...log",
    "trajectory": "storage/trajectories/traj_....json",
    "evaluation": "storage/evaluations/eval_....json",
    "analysis": "storage/hmd_motion_mapping/latest_mapping_report.json"
  },
  "log_counts": {
    "AUTO_RECENTER_UNSTABLE_RIGHT_WRIST": 0,
    "raw_wrist_spike_reacquire_pending": 0,
    "TRACKING_LOSS": 0,
    "RAW_WRIST_JUMP": 0
  },
  "evaluation": {
    "failure_reason": "RAW_WRIST_JUMP",
    "failure_category": "DATA_QUALITY_FAILURE",
    "tracking_loss_rate": 0.0,
    "raw_wrist_jump_max_m": 0.933923
  },
  "analysis": {
    "right_hand_tracked_rate": 1.0,
    "xr_frame_valid_rate": 1.0,
    "H13_status": "WARN"
  },
  "classification": "input_quality_failure",
  "decision": {
    "gate_a_collection_allowed": false,
    "axis_gain_tuning_allowed": false,
    "reasons": ["RAW_WRIST_JUMP_INPUT_QUALITY_FAILURE", "H13_NOT_PASS"]
  }
}
```

이 artifact는 training dataset export가 아니다. 운영자가 복붙 없이 다음 분기 결정을 내리기 위한 local diagnostic summary다.

## Gate 0 XR Input Viability Metadata

Gate 0은 task success와 독립적으로 Quest/OpenXR handtracking input stream 품질을 기록한다. 이 metadata는 raw trajectory를 폐기하지 않고, training eligibility 이전에 input quality를 분리해 판정하기 위한 evidence다.

### Source-Agnostic Wrist Pose Sample Contract

Gate 0 Phase 1은 persisted trajectory JSON을 DB migration 없이 유지하면서, legacy Quest/OpenXR frame metadata를 공통 wrist/input sample로 normalize하는 adapter boundary를 추가한다.

현재 contract 구현:

```text
scripts/rdf_input_sources.py
```

공통 sample schema:

```json
{
  "schema_version": "rdf_wrist_pose_sample_v0.1.0",
  "source_id": "quest_openxr_handtracking",
  "source_kind": "handtracking",
  "runtime": "steamvr_openxr",
  "device": "quest3",
  "input_channel": "right_wrist",
  "frame_index": 7,
  "timestamp_sec": 1.25,
  "pose": [0.12, -0.34, 0.56, 1.0, 0.0, 0.0, 0.0],
  "position_xyz": [0.12, -0.34, 0.56],
  "tracked": true,
  "frame_valid": true,
  "sample_valid": true,
  "input_latency_ms": 37.5,
  "action_hold": true,
  "hold_reason": "tracking_resume_warmup",
  "tracking_epoch_id": 2,
  "tracking_epoch_state": "valid",
  "quality_flags": []
}
```

Legacy compatibility rule:

- 기존 저장 경로 `metadata.raw_xr.right_wrist_pose`, `metadata.right_wrist_pose`, `metadata.right_hand_tracked`, `metadata.xr_frame_valid`, `metadata.action_hold`, `metadata.hold_reason`, `metadata.tracking_epoch_id`는 제거하지 않는다.
- Gate 0 Phase 1의 adapter는 위 legacy fields를 읽어 `WristPoseSample`로 normalize한다.
- invalid frame은 interpolation하지 않는다. `pose=null`, `sample_valid=false`, `quality_flags`로 이유를 남긴다.
- 구현되지 않은 source는 Gate 0에서 `UNSUPPORTED_INPUT_SOURCE`로 fail한다. Source metadata 자체가 없으면 `UNKNOWN_INPUT_SOURCE`로 fail한다. MediaPipe/controller/future-XR metadata가 legacy wrist pose와 비슷하게 생겼더라도 Quest/OpenXR adapter가 대신 pass시키면 안 된다.
- 향후 recorder가 `metadata.input_sample`을 저장하더라도 additive field여야 하며, HDF5 export와 proof audit이 의존하는 legacy wrist fields는 유지한다.

Frame-level metadata 추가 field:

```json
{
  "metadata": {
    "action_hold": true,
    "hold_reason": "invalid_right_hand",
    "tracking_epoch_id": 1,
    "tracking_epoch_state": "invalid",
    "tracking_gate_reason": "invalid_right_hand",
    "gate0_test_type": "tracking_reacquire",
    "gate_a_collection_blocked": true
  },
  "action": {
    "action_hold": true,
    "hold_reason": "invalid_right_hand"
  }
}
```

Field 의미:

| field | 의미 |
|---|---|
| `action_hold` | 현재 frame에서 robot action이 tracking/recenter/reacquire gate 때문에 hold되었는지 |
| `hold_reason` | `invalid_right_hand`, `tracking_resume_warmup`, `raw_wrist_spike_reacquire_pending`, `teleoperation_inactive` 등 hold 이유 |
| `tracking_epoch_id` | tracking loss/reacquire로 나뉘는 valid tracking segment id |
| `tracking_epoch_state` | 현재 frame의 tracking 상태. `valid` 또는 `invalid` |
| `tracking_gate_reason` | action hold가 tracking gate에서 온 경우의 reason |
| `gate0_test_type` | `static`, `slow_motion`, `recenter`, `tracking_reacquire` |
| `gate_a_collection_blocked` | Gate 0 diagnostic run에서 Gate A collection이 막혀 있음을 표시 |

Trajectory summary 추가 field:

```json
{
  "summary": {
    "gate0_test_type": "static",
    "gate_a_collection_blocked": true,
    "action_hold_frame_count": 12,
    "action_hold_frames": [5, 6, 7],
    "hold_reason_counts": {
      "invalid_right_hand": 4,
      "tracking_resume_warmup": 8
    },
    "tracking_epoch_ids": [0, 1],
    "tracking_epoch_count": 2
  }
}
```

Gate 0 report artifact:

```text
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log.gate0.json
```

Schema version:

```text
rdf_gate0_xr_input_viability_report_v0.1.0
```

핵심 JSON shape:

```json
{
  "schema_version": "rdf_gate0_xr_input_viability_report_v0.1.0",
  "test_type": "static",
  "gate0_pass": false,
  "gate_a_collection_allowed": false,
  "failure_reasons": ["RAW_WRIST_JUMP", "TRACKING_LOSS"],
  "metrics": {
    "right_hand_tracked_rate": 0.8,
    "xr_frame_valid_rate": 0.8,
    "raw_wrist_jump_count": 1,
    "tracking_loss_count": 1,
    "tracking_loss_duration_ms": 50.0,
    "auto_recenter_unstable_count": 2,
    "wrist_position_delta_p95": 0.35,
    "wrist_position_delta_max": 0.39,
    "frame_drop_rate": 0.25,
    "input_latency_ms": {
      "mean": 58.0,
      "p95": 112.0,
      "max": 120.0,
      "count": 5
    }
  },
  "H13": {
    "id": "H13",
    "status": "FAIL",
    "count_over_threshold": 1,
    "max_m": 0.39
  }
}
```

이 artifact는 dataset export가 아니다. Gate A collection 재개 전, XR input stream viability를 증명하기 위한 local diagnostic report다.

Gate 0 batch aggregate artifact:

```text
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_gate0-all.log.gate0_all.json
```

Schema version:

```text
rdf_gate0_all_report_v0.1.0
```

핵심 JSON shape:

```json
{
  "schema_version": "rdf_gate0_all_report_v0.1.0",
  "gate0_all_pass": false,
  "gate_a_collection_allowed": false,
  "stage_order": [
    "gate0-static",
    "gate0-slow-motion",
    "gate0-recenter",
    "gate0-reacquire"
  ],
  "failure_reasons": ["RAW_WRIST_JUMP"],
  "stages": [
    {
      "mode": "gate0-static",
      "report_path": "storage/logs/hmd_axis_debug/<run>.log.gate0.json",
      "exists": true,
      "gate0_pass": false,
      "gate_a_collection_allowed": false,
      "failure_reasons": ["RAW_WRIST_JUMP"],
      "input_source": {
        "source_id": "quest_openxr_handtracking",
        "adapter": "QuestOpenXrHandtrackingAdapter",
        "adapter_status": "matched_source",
        "sample_schema_version": "rdf_wrist_pose_sample_v0.1.0"
      },
      "H13": {
        "id": "H13",
        "status": "FAIL"
      },
      "metrics": {
        "right_hand_tracked_rate": 1.0,
        "xr_frame_valid_rate": 1.0,
        "raw_wrist_jump_count": 1
      }
    }
  ],
  "input_sources": [
    {
      "source_id": "quest_openxr_handtracking",
      "adapter": "QuestOpenXrHandtrackingAdapter",
      "adapter_status": "matched_source",
      "sample_schema_version": "rdf_wrist_pose_sample_v0.1.0"
    }
  ]
}
```

`gate0-all` aggregate는 네 개 개별 `.gate0.json` report를 합산한 operator convenience artifact다. `gate0_all_pass=false`이면 `gate_a_collection_allowed=false`이며, Gate A collection은 재개하지 않는다. `scripts/run_collection_loop.sh`는 aggregate schema, 네 개 stage 순서/개수, stage별 pass/allow/failure reason, matched input source, 단일 source id, report freshness를 다시 검증한 뒤에만 명시적 Gate A collection을 시작한다.

## MVP-1+ Robot Embodiment Adapter Proof Artifacts

MVP-1+는 MVP-2 policy uplift 이전에 여러 robot embodiment source가 같은
data trust layer contract를 emit할 수 있는지 확인하는 단계다. 이 단계는
real robot runtime, live ROS2/DDS runtime, HMD readiness, marketplace,
production auth, DB migration을 주장하지 않는다.

실행 명령:

```bash
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
```

기본 출력 위치:

```text
storage/mvp1plus_embodiment_proof/
```

최상위 artifact:

```text
storage/mvp1plus_embodiment_proof/mvp1plus_embodiment_proof.json
storage/mvp1plus_embodiment_proof/mvp1plus_embodiment_proof_summary.json
storage/mvp1plus_embodiment_proof/mvp1plus_buyer_summary.json
```

핵심 schema version:

```text
rdf_mvp1plus_embodiment_proof_v0.1.0
rdf_mvp1plus_embodiment_summary_v0.1.0
rdf_mvp1plus_buyer_summary_v0.1.0
rdf_mvp1plus_command_state_source_metadata_v0.1.0
rdf_mvp1plus_embodiment_projection_v0.1.0
rdf_mvp1plus_lineage_evidence_v0.1.0
rdf_normalized_trajectory_contract_v0.1.0
```

Adapter source evidence는 adapter별로 `JSONL + metadata JSON` 형태를 사용한다.

```text
source_logs/<adapter_id>/metadata.json
source_logs/<adapter_id>/accepted_command_state.jsonl
source_logs/<adapter_id>/rejected_command_state.jsonl
```

현재 represented adapter:

| adapter_id | 역할 | claim boundary |
|---|---|---|
| `franka_research_arm` | baseline / research-arm adapter | generated recorded-log proof only |
| `robotis_sh5_ros2_dds` | ROS2 / DDS command-state bridge adapter | no live ROS2/DDS runtime claim |
| `universal_robots_ur_industrial_arm` | industrial-arm adapter | repo-local file-backed recorded-log fixture by default; no UR/RTDE runtime claim |
| `universal_robots_ur_external_style` | generated external-style UR sample | no public sample import claim |

`metadata.json` 핵심 shape:

```json
{
  "schema_version": "rdf_mvp1plus_command_state_source_metadata_v0.1.0",
  "adapter_id": "franka_research_arm",
  "adapter_version": "rdf_robot_embodiment_adapter_v0.1.0",
  "robot_family": "franka",
  "embodiment_class": "research_arm",
  "command_state_interface": "joint_and_ee_delta_command_fixture",
  "command_state_transport": "fixture_command_state",
  "state_interface": "fixture_joint_and_ee_state",
  "coordinate_frames": {
    "command_frame": "task_frame",
    "state_frame": "robot_base_frame",
    "normalization_frame": "rdf_normalized_task_frame"
  },
  "source_provenance": {
    "source_type": "jsonl_plus_metadata_recorded_command_state_log",
    "recorded_log_backed": true,
    "public_sample_evidence_claimed": false
  },
  "claim_boundary": {
    "real_robot_success_claimed": false,
    "physical_robot_readiness_claimed": false,
    "live_runtime_support_claimed": false,
    "hmd_readiness_claimed": false,
    "policy_uplift_claimed": false,
    "universal_robot_support_claimed": false
  }
}
```

`accepted_command_state.jsonl`과 `rejected_command_state.jsonl`의 row는 다음
필드를 요구한다.

```json
{
  "timestamp": 0.04,
  "sequence_id": 1,
  "command": {
    "interface": "joint_and_ee_delta_command_fixture",
    "vector": [0.018, -0.004, -0.052, 0.002, 0.0, -0.001, 0.35],
    "unit": "meters_radians_normalized_gripper"
  },
  "state": {
    "interface": "fixture_joint_and_ee_state",
    "end_effector_position": [0.436, -0.018, 0.035],
    "end_effector_quaternion": [1.0, 0.0, 0.0, 0.0],
    "object_position": [0.44, -0.02, 0.0],
    "object_quaternion": [1.0, 0.0, 0.0, 0.0],
    "joint_positions": [0.0, -0.41, 0.18, -1.88, 0.0, 1.57, 0.78]
  },
  "action_semantics": {
    "representation": "robot_delta_ee_pose",
    "coordinate_frame": "task_frame",
    "normalized_contract_roles": [
      "teleop_intent",
      "executed_control",
      "learning_action",
      "retargeted_robot_action"
    ]
  },
  "quality": {
    "replay_verified": true,
    "action_contract_valid": true,
    "control_quality": "pass",
    "timestamp_gap_detected": false,
    "rejection_reason": null
  }
}
```

Projection output은 기존 HDF5 exporter/trainer 호환을 위해 RDF trajectory /
evaluation / curation manifest로 변환된다. `raw_xr_right_wrist_pose`와
`aligned_xr_right_wrist_pose`는 exporter compatibility placeholder이며,
HMD evidence가 아니다.

```json
{
  "exporter_compatibility_placeholders": {
    "raw_xr_right_wrist_pose": "zero_pose_exporter_compatibility_only",
    "aligned_xr_right_wrist_pose": "zero_pose_exporter_compatibility_only",
    "hmd_readiness_evidence": false
  }
}
```

Adapter-emitted normalized contract는 adapter별로 생성된다.

```text
normalized_contracts/<adapter_id>_normalized_trajectory_contract.json
```

Contract의 `source_profile`은 projected recorded-log provenance를 유지한다.
Builder가 가진 static source profile은 `robot_embodiment_adapter_evidence`
아래 `source_provenance.builder_source_profile`에만 남긴다. 이를 통해
builder static fixture가 recorded-log source provenance를 덮어쓰지 않는다.

UR industrial adapter의 기본 source는 다음 repo-local fixture다.

```text
fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/
```

이 fixture는 `source_provenance.source_type=file_backed_recorded_log_fixture`를
사용하고, output source copy에는 `fixture_path`와
`repo_local_recorded_log_fixture=true`를 기록한다. 이는 file-backed ingestion
path를 증명하기 위한 claim-safe fixture이며, physical UR run, live UR/RTDE
runtime, public sample import, real robot success evidence가 아니다.

Custom UR source를 검증할 때는 동일한 `metadata.json`,
`accepted_command_state.jsonl`, `rejected_command_state.jsonl` shape를 가진
directory를 `--ur-recorded-log-dir`로 지정한다.

```bash
uv run python scripts/run_mvp1plus_embodiment_proof.py \
  --output-dir /tmp/rdf_mvp1plus_custom_ur \
  --ur-recorded-log-dir /path/to/ur_recorded_log_dir \
  --clean --pretty
```

`lineage_evidence`는 proof, normalized contract evidence, adapter summary,
buyer summary에 같은 payload로 들어간다.

```json
{
  "schema_version": "rdf_mvp1plus_lineage_evidence_v0.1.0",
  "source_evidence_type": "file_backed_recorded_log_fixture",
  "source_files": {
    "metadata_json": {
      "path": "storage/mvp1plus_embodiment_proof/source_logs/universal_robots_ur_industrial_arm/metadata.json",
      "sha256": "<sha256>",
      "byte_size": 1024
    }
  },
  "source_bundle_sha256": "<sha256>",
  "projected_artifacts": {
    "accepted_trajectory": {
      "path": "storage/mvp1plus_embodiment_proof/projected_inputs/universal_robots_ur_industrial_arm/trajectories/<id>.json",
      "sha256": "<sha256>",
      "byte_size": 2048
    }
  },
  "projected_bundle_sha256": "<sha256>"
}
```

`source_bundle_sha256`는 source evidence files의 path/sha256/byte_size를
stable JSON으로 정렬해 다시 hash한 값이다. `projected_bundle_sha256`도 같은
방식으로 projected trajectory/evaluation/curation/split/projection artifacts를
묶는다. 이 값들은 buyer가 "어떤 source가 어떤 trainer-loadable artifact로
project됐는가"를 재현 가능하게 추적하기 위한 lineage evidence다.

Buyer summary는 다음 non-claim을 모두 `false`로 기록한다.

```json
{
  "real_robot_success": false,
  "physical_robot_readiness": false,
  "live_runtime_support": false,
  "hmd_readiness": false,
  "policy_uplift": false,
  "universal_robot_support": false,
  "public_sample_import": false,
  "marketplace_readiness": false,
  "db_migration": false,
  "production_auth": false
}
```

## MVP-2 UR Policy A/B Harness Artifact

MVP-2 Rebase의 첫 artifact는 UR file-backed recorded-log lineage에서 시작하는
policy A/B harness readiness proof다. 이는 learning-proven proof가 아니라,
curated/uncurated dataset view, HDF5 export, held-out suite manifest,
policy eval input template, schema-only rollout ingest contract가 같은 lineage로
연결되는지 확인하는 artifact다.

기본 실행 위치:

```text
storage/mvp2_policy_ab_harness/
```

Primary report:

```text
storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json
```

주요 schema version:

```json
{
  "mvp2_policy_ab_harness_report": "rdf_mvp2_ur_policy_ab_harness_v0.1.0",
  "mvp2_policy_eval_input_template": "rdf_mvp2_policy_eval_input_v0.1.0",
  "mvp2_heldout_suite_manifest": "rdf_mvp2_heldout_suite_manifest_v0.1.0",
  "rollout_ingest_contract": "rdf_mvp2_rollout_ingest_contract_v0.1.0"
}
```

Report의 proof source는 MVP-1+ UR adapter-emitted contract lineage를 가리킨다.

```json
{
  "proof_source": {
    "adapter_id": "universal_robots_ur_industrial_arm",
    "source_evidence_type": "file_backed_recorded_log_fixture",
    "validator_backend": "NormalizedTrajectoryContractValidator",
    "contract_path": "storage/mvp1plus_embodiment_proof/normalized_contracts/universal_robots_ur_industrial_arm_normalized_trajectory_contract.json"
  }
}
```

Dataset view는 두 개다.

```json
{
  "baseline": {
    "dataset_view": "baseline_uncurated_recorded_log_harness",
    "include_statuses": ["failure", "success"]
  },
  "candidate": {
    "dataset_view": "candidate_curated_accepted",
    "include_statuses": ["success"]
  }
}
```

Schema-only rollout ingest fixture는 외부 trainer/evaluator 결과 shape 검증용이다.
`baseline_success_rate`와 `candidate_success_rate`가 계산될 수 있지만, 이 값은
fixture ingest sanity 값일 뿐 policy uplift evidence가 아니다. 현재 schema-only
fixture는 baseline/candidate success rate를 의도적으로 같은 값으로 두며,
`schema_fixture_metrics.non_comparative=true`와
`must_not_be_used_for_policy_uplift=true`를 기록한다.

MVP-2 harness는 UR proof source가
`source_evidence_type=file_backed_recorded_log_fixture`이고
`source_bundle_sha256`, `projected_bundle_sha256`, source file hash,
projected artifact hash가 존재할 때만 `lineage_gate.passed=true`가 된다. 기존
MVP-1+ output을 재사용하더라도 이 gate를 통과하지 못하면 harness는 실패해야
한다. 이 gate는 expected source/artifact key set, `projected_inputs` path와
lineage path 일치, per-file SHA-256, byte size, bundle SHA-256을 재계산해
확인한다.

`passed`와 `harness_ready`는 상수 true가 아니라 다음 gate에서 파생된다.

```json
{
  "lineage_gate_passed": true,
  "ur_contract_validation_passed": true,
  "baseline_export_nonempty": true,
  "candidate_export_nonempty": true,
  "baseline_hdf5_inspection_clean": true,
  "candidate_hdf5_inspection_clean": true,
  "rollout_ingest_contract_ready": true,
  "schema_fixture_non_comparative": true,
  "schema_fixture_not_policy_uplift": true
}
```

MVP-2 Rebase first slice는 다음 boundary를 항상 유지한다.

```json
{
  "learning_results_measured": false,
  "curated_vs_uncurated_uplift": null,
  "learning_proven": false,
  "proof_eligible": false,
  "policy_uplift_claimed": false,
  "physical_robot_readiness_claimed": false,
  "hmd_readiness_claimed": false
}
```

`run_mvp1_proof_audit.py`는 `mvp2_policy_ab_harness` summary를 읽을 수 있지만,
이 summary는 MVP-1 gate를 통과시키거나 `learning_proven_policy_uplift_achieved`
를 `true`로 만들지 않는다.

## MVP-2 Learning-Proven Policy Eval Artifact

MVP-2 learning-proven artifact는 UR policy A/B harness 위에서 curated dataset
view가 uncurated dataset view보다 held-out policy success rate에서 실제로
높은지 측정한 report다. 단, default local offline runner는 deterministic
quality-signal proxy이므로 MVP-2 Closed evidence가 아니다. MVP-2 Closed는
external proof-grade held-out policy eval rollout provenance가 있을 때만 가능하다.
기본 위치는 다음과 같다.

```text
storage/mvp2_learning_proven_policy_eval/
```

Primary report:

```text
storage/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
```

주요 schema version:

```json
{
  "mvp2_learning_proven_report": "rdf_mvp2_learning_proven_policy_eval_v0.1.0",
  "local_offline_rollout": "rdf_mvp2_local_offline_rollout_v0.1.0",
  "local_offline_heldout_suite": "rdf_mvp2_local_offline_heldout_suite_v0.1.0",
  "external_policy_eval_template": "rdf_mvp2_external_policy_eval_template_v0.1.0",
  "policy_eval_report": "rdf_mvp1c_heldout_policy_eval_v0.2.0"
}
```

MVP-2 Closed 조건은 다음 값이 동시에 true/positive일 때만 충족된다.

```json
{
  "learning_results_measured": true,
  "learning_proven": true,
  "proof_eligible": true,
  "evidence_tier": "external_heldout_policy_eval",
  "validator_evidence_tier": "heldout_policy_eval",
  "curated_vs_uncurated_uplift": "> 0"
}
```

또한 `candidate_success_rate`는 반드시 `baseline_success_rate`보다 커야 한다.
Negative 또는 tie 결과는 `learning_results_measured=true`인 evidence로 보존되지만
`learning_proven=false`, `proof_eligible=false`로 남아 MVP-2를 close하지 않는다.

Local offline path는 harness의 schema-only held-out suite를 그대로 쓰지 않는다.
Wrapper는 local offline suite와 rollout JSON을 만들지만, 이 경로는
`evidence_tier=local_offline_policy_eval_proxy`, `validator_evidence_tier=null`,
`learning_proven=false`, `proof_eligible=false`로 남아야 한다. 즉 default local
offline output은 local readiness/proxy evidence이며 validator proof input/report를
생성하지 않는다.

```json
{
  "id": "mvp2_local_offline_ur_policy_eval_suite",
  "held_out": true,
  "task_type": "connector_insertion",
  "source_kind": "local_offline_derived_from_harness_template",
  "proof_role": "local_offline_policy_eval_suite",
  "heldout_manifest_path": "storage/mvp2_learning_proven_policy_eval/mvp2_local_offline_heldout_suite_manifest.json",
  "not_physical_or_isaac_evidence": true
}
```

Schema-only rollout ingest fixture와 local deterministic proxy는 MVP-2 proof로
승격할 수 없다. 다음 marker 중 하나가 rollout input에 있거나 `schema_*`
rollout id / `deterministic_dataset_quality_signal` label source가 감지되면 wrapper는
`run_real_policy_eval.py`를 호출하지 않고 non-proof report를 쓴다.

```json
{
  "fixture_kind": "schema_only_rollout_ingest_contract",
  "source_kind": "schema_only_rollout_ingest_contract"
}
```

외부 evaluator가 채워야 할 proof package template은 다음 위치에 생성된다.

```text
storage/mvp2_learning_proven_policy_eval/external_policy_eval_template/
```

주요 template artifact:

```text
external_policy_eval_request.json
baseline_external_rollouts.template.json
candidate_external_rollouts.template.json
external_policy_eval_template_report.json
```

이 template은 `proof_ready=false`, `mvp2_closed=false`,
`template_is_not_evidence=true`를 기록한다. 즉, 외부 evaluator가 실제
baseline/candidate held-out rollout 결과를 채워 넣기 전까지는 MVP-2 evidence가
아니다.

```json
{
  "source_kind": "external_heldout_policy_eval_template",
  "proof_role": "external_trainer_policy_eval_template",
  "template_is_not_evidence": true,
  "required_final_values": {
    "source_kind": "external_heldout_policy_eval",
    "proof_role": "external_trainer_policy_eval"
  },
  "heldout_suite": {
    "scenario_ids": ["TODO_external_heldout_scenario_00"]
  },
  "rollout_results": []
}
```

채워진 external rollout JSON만 `source_kind=external_heldout_policy_eval`,
`proof_role=external_trainer_policy_eval`, external `heldout_suite`, trainer,
eval runner, policy artifact provenance, non-empty `rollout_results`를 포함해야
한다. 채우지 않은 template 파일을 그대로 ingest하면 wrapper는 validator 호출 전
non-proof report로 차단한다.

External `heldout_suite.id`와 `heldout_suite.scenario_ids`는 schema-only fixture
값이면 안 된다. `schema_only`가 포함된 suite id 또는 scenario id는 proof-grade
provenance가 아니므로 wrapper가 validator 호출 전에 차단한다.

`mvp2_learning_proven_report.json`의 주요 buyer-facing field는 다음과 같다.

```json
{
  "evidence_tier": "external_heldout_policy_eval",
  "validator_evidence_tier": "heldout_policy_eval",
  "primary_metric": "policy_success_rate",
  "baseline_success_rate": 0.7,
  "candidate_success_rate": 1.0,
  "curated_vs_uncurated_uplift": 0.3,
  "proof_source": {
    "adapter_id": "universal_robots_ur_industrial_arm",
    "source_evidence_type": "file_backed_recorded_log_fixture",
    "validator_backend": "NormalizedTrajectoryContractValidator"
  },
  "claim_boundary": {
    "real_robot_success_claimed": false,
    "physical_robot_readiness_claimed": false,
    "hmd_readiness_claimed": false
  }
}
```

`run_mvp1_proof_audit.py`는 새 report를
`mvp2_learning_proven_policy_eval` summary로 읽는다. 이 report path는 명시적으로
전달해야 하며, `evidence_tier=external_heldout_policy_eval`와
`validator_evidence_tier=heldout_policy_eval`가 아닌 report는 positive uplift로
승격하지 않는다. `policy_uplift_required_for_mvp1=false`는 계속 유지된다.

### MVP-2A transition / policy readiness report

현재 UR policy A/B harness는 MVP-2 Closed를 주장하지 않고, 그 전에 필요한
`MVP-2A` readiness를 별도 artifact로 남긴다.

```text
storage/mvp2_policy_ab_harness/mvp2a_transition_policy_readiness_report.json
storage/mvp2_policy_ab_harness/mvp2a_policy_trainer_selection_report.json
storage/mvp2_policy_ab_harness/candidate_curated/curation_manifest.json
storage/mvp2_policy_ab_harness/candidate_curated/split_manifest.json
storage/mvp2_policy_ab_harness/candidate_curated/mvp2_learning_sanity_report.json
```

주요 schema:

```json
{
  "schema_version": "rdf_mvp2a_transition_policy_readiness_v0.1.0",
  "passed": true,
  "mvp2a_policy_ab_ready": true,
  "learning_results_measured": false,
  "curated_vs_uncurated_uplift": null,
  "learning_proven": false,
  "stronger_policy_trainer_selected": true,
  "next_recommended_gate": "external_heldout_policy_rollout_generation",
  "policy_trainer_selection": {
    "schema_version": "rdf_mvp2a_policy_trainer_selection_v0.1.0",
    "selected": true,
    "policy_class": "phase_conditioned_sequence_bc_policy_v0",
    "trainer": "rdf_phase_conditioned_sequence_bc_trainer_contract_v0"
  },
  "candidate_curated_train": {
    "transition_coverage_passed": true,
    "train_set_overfit_passed": true,
    "dataset_present_required_phases": ["APPROACH", "CONTACT", "INSERT", "SEAT"],
    "dataset_missing_required_phases": [],
    "transition_rich_episode_count": 1,
    "sample_count": 4
  }
}
```

`run_mvp2_learning_sanity.py`는 frame metadata의 `action_phase` / `phase`,
`task_state.action_phase`, 그리고 command-state fixture의
`command_state_row.task_phase`를 transition phase source로 읽는다.

`run_mvp1_proof_audit.py`의 `mvp2_policy_ab_harness` summary는
`mvp2a_policy_ab_ready`, `mvp2a_next_recommended_gate`,
`candidate_transition_coverage_passed`, `candidate_train_set_overfit_passed`,
`stronger_policy_trainer_selected`, `selected_policy_class`, `selected_trainer`를
함께 노출한다. 이 값들은 MVP-2 Closed evidence가 아니라, 다음 proof-grade
held-out policy A/B를 실행해도 되는지 판단하는 pre-A/B readiness evidence다.
현재 UR recorded-log fixture는 `APPROACH`, `CONTACT`, `INSERT`, `SEAT`를 모두
포함하도록 projection된다. `mvp2a_policy_ab_ready=true`는 transition-rich train
material과 trainer/policy contract 선택이 준비됐다는 뜻이며, policy training이나
positive uplift를 증명하지 않는다. MVP-2 Closed는 여전히 external held-out rollout
JSON에서 positive curated > uncurated uplift가 확인되어야 한다.

### MVP-2 phase-conditioned local eval proxy artifact

`MVP-2A` readiness 이후 `scripts/run_mvp2_phase_conditioned_external_eval.py`는
phase-conditioned local evaluator proxy를 생성한다. 이 evaluator는
`baseline_uncurated`와 `candidate_curated` HDF5 train material을 읽고 같은
local held-out proxy suite에 대해 rollout JSON을 만든다. 이 artifact는 positive
proxy delta를 보존하지만, 독립 external held-out policy rollout evidence가 아니므로
MVP-2 Closed proof로 승격하지 않는다.

주요 artifact:

```text
storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_phase_conditioned_local_eval_proxy_report.json
storage/mvp2_phase_conditioned_local_eval_proxy/phase_conditioned_proxy_rollouts/baseline_uncurated_proxy_rollouts.json
storage/mvp2_phase_conditioned_local_eval_proxy/phase_conditioned_proxy_rollouts/candidate_curated_proxy_rollouts.json
storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
```

최상위 report schema:

```json
{
  "schema_version": "rdf_mvp2_phase_conditioned_local_eval_proxy_v0.1.0",
  "passed": true,
  "mvp2_closed": false,
  "proxy_results_measured": true,
  "proxy_uplift_positive": true,
  "learning_results_measured": true,
  "learning_proven": false,
  "proof_eligible": false,
  "evidence_tier": "local_phase_conditioned_policy_eval_proxy",
  "validator_evidence_tier": null,
  "primary_metric": "policy_success_rate",
  "baseline_success_rate": 0.4,
  "candidate_success_rate": 0.9,
  "curated_vs_uncurated_uplift": 0.5,
  "selected_policy_class": "phase_conditioned_sequence_bc_policy_v0",
  "selected_trainer": "rdf_phase_conditioned_sequence_bc_trainer_contract_v0",
  "eval_runner": "rdf_phase_conditioned_task_state_heldout_eval_v0",
  "claim_boundary": {
    "mvp2_learning_proven_claimed": false,
    "real_robot_success_claimed": false,
    "physical_robot_readiness_claimed": false,
    "hmd_readiness_claimed": false,
    "isaac_runtime_success_claimed": false
  }
}
```

생성된 rollout JSON은 반드시 proxy provenance를 포함한다. `source_kind`가
`local_phase_conditioned_policy_eval_proxy`인 파일은 positive delta가 있어도
`run_mvp2_learning_proven_policy_eval.py`에서 proof-grade external evidence로
승격되지 않는다.

```json
{
  "source_kind": "local_phase_conditioned_policy_eval_proxy",
  "proof_role": "local_phase_conditioned_policy_eval_proxy",
  "policy_artifact_id": "rdf_mvp2_candidate_curated_phase_policy_...",
  "policy_class": "phase_conditioned_sequence_bc_policy_v0",
  "trainer": "rdf_phase_conditioned_sequence_bc_trainer_contract_v0",
  "eval_runner": "rdf_phase_conditioned_task_state_heldout_eval_v0",
  "proxy_only": true,
  "not_external_proof_grade_evidence": true,
  "heldout_suite": {
    "id": "local_ur_phase_conditioned_heldout_policy_eval_proxy_suite",
    "held_out": true,
    "task_type": "connector_insertion",
    "source_kind": "local_phase_conditioned_eval_suite",
    "proof_role": "local_phase_conditioned_policy_eval_proxy_suite"
  },
  "rollout_results": []
}
```

이 artifact가 닫는 것은 MVP-2A 이후의 local proxy readiness gap이다. MVP-2
Closed는 여전히 독립 external held-out evaluator가 생성한
`source_kind=external_heldout_policy_eval`, `proof_role=external_trainer_policy_eval`
rollout JSON과 positive curated > uncurated policy success가 필요하다. 다음 claim은
false로 유지한다.

- real robot success
- physical UR readiness
- Isaac runtime success
- HMD/OpenXR readiness
- marketplace 또는 production readiness

## MVP-2C Isaac Training / Calibration Artifact Schema

`scripts/run_mvp2c_isaac_training_calibration.py`는 MVP-2B와 분리된 fresh proof
attempt artifact를 생성한다.

주요 artifact:

```text
scenario_manifest.json
action_adapter_candidates.json
action_adapter_registry_hash.json
baseline_noise_mix_config.json
generator_config_hashes.json
calibration_selection_report.json
selected_action_adapter.json
policy_eval_binding.json
train_raw_trajectories/
normalized_trajectory_contracts/
curation_manifest.json
baseline_uncurated_train.hdf5
candidate_curated_train.hdf5
baseline_policy_artifact.json
candidate_policy_artifact.json
external_rollouts/baseline_external_rollouts.json
external_rollouts/candidate_external_rollouts.json
mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
mvp2c_isaac_training_calibration_report.json
visual_evidence/metric_trace_comparison.png
```

최상위 report 필수 경계:

```json
{
  "schema_version": "rdf_mvp2c_isaac_training_calibration_v0.1.0",
  "mvp2_closed": false,
  "mvp2c_close_minimum_passed": false,
  "stronger_public_evidence_target_passed": false,
  "runtime_backend": "isaac_runtime",
  "train_generation_runtime_backend": "deterministic_test_backend",
  "train_generation_runtime_gate": {
    "actual_train_generation_evidence": false,
    "training_trajectory_source": "deterministic_domain_generator"
  },
  "actual_rollouts_per_policy": 20,
  "baseline_noise_mix_ratio": 0.25,
  "accepted_failure_ratio": {
    "accepted": 3,
    "failure_or_noisy": 1
  },
  "scripted_expert_config_sha256": "...",
  "controlled_failure_config_sha256": "...",
  "train_generation_config_sha256": "...",
  "selected_action_adapter": {
    "selector_score_config_sha256": "...",
    "selected_adapter_sha256": "...",
    "selected_adapter_config": {
      "adapter_mode": "per_axis_signed_xy_downward_servo",
      "xy_source": "state_feedback",
      "xy_state_feedback_gain": 4.0,
      "xy_action_clip": 0.035,
      "z_action_scale": 24.0,
      "z_action_clip": 0.12,
      "rotation_action_scale": 1.0,
      "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0]
    },
    "selected_adapter_config_sha256": "...",
    "selector_score_pre_registered": true,
    "same_adapter_used_for_baseline_and_candidate": true,
    "heldout_excluded": true,
    "selected_adapter_frozen_before_heldout": true
  },
  "calibration_only_selection_passed": true,
  "heldout_leakage_guard_passed": true,
  "non_claims": {
    "deployable_real_robot_policy": false,
    "visual_policy_performance": false,
    "real_robot_success": false,
    "physical_robot_readiness": false,
    "universal_robot_support": false
  }
}
```

MVP-2C close minimum은 다음이 모두 참일 때만 true가 된다.

```text
train_generation_runtime_gate.passed=true
train_generation_runtime_backend=isaac_runtime
train_generation_runtime_gate.actual_train_generation_evidence=true
train_generation_runtime_gate.training_trajectory_source=isaac_runtime_scripted_expert_rollout
runtime_gate.passed=true
runtime_backend=isaac_runtime
proof_runtime=dedicated_isaac_connector_insertion_evaluator
calibration_only_selection_passed=true
heldout_leakage_guard_passed=true
actual_rollouts_per_policy >= 20
existing_mvp2_validator.learning_proven=true
existing_mvp2_validator.proof_eligible=true
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
```

`stronger_public_evidence_target_passed`는 close minimum과 별도다. 공개
benchmark 또는 investor-facing claim에는 policy당 50개 이상 rollout과 confidence
interval evidence가 필요하다.

## LeRobot Public ALOHA Audited Slice Semantic Parity Schema

`docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/`는
public LeRobot source의 deterministic audited slice를 RDF trust layer에 태운
첫 `external_data_evaluated` package다. 이 schema는 기존 UR-style
command/state log와 다르며, EEF/object pose field를 만들지 않는다.

Source binding artifact:

```text
data/source/public_source_binding.json
data/source/upstream_file_hashes.json
data/source/refetch_receipt.json
data/source/extraction_receipt.json
data/source/slice_selection_report.json
data/source/lerobot_raw_rows.jsonl
data/source/lerobot_feature_schema.json
```

Converted RDF row schema:

```json
{
  "schema_version": "rdf_public_lerobot_state_action_row_v0.1.0",
  "source_kind": "public_lerobot_dataset_slice",
  "source_robot_type": "aloha",
  "observation_state": [0.0],
  "learning_action": [0.0],
  "action_semantics": {
    "representation": "lerobot_action_vector",
    "coordinate_frame": "source_dataset_native_frame",
    "normalized_contract_roles": ["source_action", "learning_action"]
  }
}
```

현재 canonical package의 측정값:

```text
repo_id=lerobot/aloha_static_coffee
resolved_revision=b144896feb1f37398a862927b22cd3abdf005a6b
slice_rule=first_episode_first_n_frames
episode_index=0
frame_start=0
frame_count=8
observation_state_dim=14
action_dim=14
full_source_verdict_claimed=false
audited_slice_verdict_claimed=true
```

이 package가 허용하는 claim은 `public LeRobot ALOHA audited slice`의
source binding, semantic conversion, generic state/action contract, HDF5 export,
trainer smoke, verifier recomputation이다. Full LeRobot parser support, full
dataset evaluation, real robot readiness, visual policy performance, policy uplift,
deployable policy, marketplace, production, sim-to-real claim은 모두 false다.

## LeRobot Public Dataset Matrix Semantic Parity Schema

`docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/`는
frozen verified ALOHA audited slice와 새로 생성한 SO-100 audited slice를
같은 matrix verifier / generic state-action contract discipline으로 재검증한
matrix package다.

허용 claim:

```text
external_public_lerobot_dataset_matrix_semantic_parity
```

정확한 의미:

```text
두 개의 명시적 profile(Aloha bimanual + SO-100 single-arm)이 각각 public
source binding, deterministic audited slice, raw-row digest, semantic conversion,
generic state/action contract, HDF5 export, trainer smoke, verifier recomputation을
통과했다.
```

Profile registry:

```text
lerobot_aloha_static_coffee
  repo_id=lerobot/aloha_static_coffee
  resolved_revision=b144896feb1f37398a862927b22cd3abdf005a6b
  robot_type=aloha
  observation_state_dim=14
  action_dim=14

lerobot_svla_so100_pickplace
  repo_id=lerobot/svla_so100_pickplace
  resolved_revision=3d6d687a25cdf1565cdf24550814f72d999a861d
  robot_type=so100
  observation_state_dim=6
  action_dim=6
```

Matrix package layout:

```text
data/config.json
data/matrix_summary.json
data/profile_resolver_report.json
data/non_claims_attestation.json
data/artifact_index.json
data/profiles/<profile_id>/
  source/
  conversion/
  contracts/
  export/
  reports/
```

각 profile의 `source/lerobot_raw_rows.jsonl`이 semantic parity source of truth다.
`matrix_summary.json`, `buyer_data_evaluation_report.json`,
`package_manifest.json`은 cached/index artifact이며 verifier source of truth가 아니다.

금지 claim:

```text
generic LeRobot parser support
full LeRobot dataset evaluation
real robot success
physical robot readiness
live hardware / RTDE / ROS2-DDS / Franka bridge readiness
visual policy performance
policy uplift / learning-proven value
deployable policy readiness
marketplace readiness
production certification
sim-to-real proof
general robot intelligence
```

## MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal Package Schema

`docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/`는
실제 partner file-drop 전의 digital-twin/generated recorded-log chaos
rehearsal package다. source of truth는 `data/` 아래 포함 evidence이며,
`package_manifest.json`, `data/config.json`, `buyer_report.html`은 verifier가
재계산해야 하는 index/summary/report artifact다.

Package status:

```text
file_drop_rehearsal_contract_ready
file_drop_rehearsal_ready
```

현재 fixture-only package는 다음 상태다.

```text
status=file_drop_rehearsal_contract_ready
file_drop_rehearsal_ready=false
blocked_reason=runtime_capture_not_supplied
```

`file_drop_rehearsal_ready=true`는 v0 package에서 의도적으로 열리지 않는다.
`runtime_capture.json`이 supplied되고 `MIN_CANONICAL_FRAMES=12` 이상이며 각 frame이
UR commanded/actual joints, UR TCP pose/speed, Franka commanded/actual state,
Franka EEF transform, generic command/state, phase, robot mode, safety status를
모두 포함하더라도, 그 JSON은 self-attested payload일 수 있다. 따라서
verifier-owned raw runtime evidence contract가 별도 구현되기 전까지는
`runtime_capture_structurally_valid=true`까지만 기록하고
`runtime_capture_sufficient=false`,
`blocked_reason=runtime_capture_unverified_source_process`로 contract-ready에
머문다. builder가 deterministic fixture를 runtime-backed로 덮어써 승격하면
안 된다. Known deterministic fixture frame content digest와 동일한 trace는
`source_kind`와 `runtime_backed`를 relabel해도 ready evidence가 아니며
contract-ready에 머문다. timestamp-only capture, row-count-only capture,
provenance 없는 capture도 contract-ready에 머문다.

필수 profile:

```text
ur_rtde_csv_v0
franka_state_jsonl_v0
ros2_channel_bundle_jsonl_v0
generic_command_state_jsonl_v0
```

Package layout:

```text
data/config.json
data/profile_registry.json
data/non_claims_attestation.json
data/artifact_index.json
data/canonical_trace/
  canonical_trace.json
  runtime_capture.json   # runtime capture가 supplied된 경우에만 존재
  runtime_capture_preflight.json
  runtime_capture_hash_receipt.json
data/source_drops/
  golden/<profile_id>/
  corrupt/<profile_id>/<mutation_id>/
data/normalized_contracts/
data/export/<profile_id>/
  dataset.hdf5
  split_manifest.json
  hdf5_inspection_report.json
  trainer_smoke_report.json
  semantic_preservation_receipt.json
data/ingest_results/
  golden_results.json
  corruption_matrix_results.json
  rejection_reason_coverage.json
data/reports/buyer_report.html
```

검증 원칙:

```text
golden source drops는 profile parser/semantic gate로 재계산한다.
golden source drops는 `canonical_trace.json`에서 profile별 deterministic
projection으로 재유도한 normalized rows와 일치해야 한다.
profile_registry는 verifier-owned exact contract이며 schema_version,
profile_count, robot family/model, source_file_names, action/state semantics까지
일치해야 한다.
corrupt source drops는 expected rejection reason으로 fail-closed되어야 한다.
HDF5 export는 source drop에서 재계산한 rows 기준으로 state/action/timestamp
hash와 deep payload check를 묶는다. HDF5가 포함된 MVP-5A-pre package는
`--deep-hdf5` 없이 final `VERDICT: VERIFIED`를 내면 안 되며, default mode는
`hdf5 payload verification requires --deep-hdf5`로 fail-closed되어야 한다.
buyer report와 README는 positive forbidden claim scan 대상이다.
artifact path는 data/ 상대 경로만 허용하고 symlink escape를 금지한다.
`file_drop_rehearsal_ready=true`는 현재 verifier에서 항상 fail-closed다. 향후
ready path를 열려면 included `runtime_capture.json`의 `mvp5a_canonical_trace`
뿐 아니라 verifier-owned raw runtime evidence를 함께 정의하고, package
`canonical_trace.json`이 그 raw evidence에서 재계산되어야 한다.
```

금지 claim:

```text
external_partner_data_evaluated
external_partner_data
real_robot_success
physical_robot_readiness
hardware_integration
hardware_readiness
live_ur_rtde_support
live_franka_hardware_support
live_ros2_dds_bridge_readiness
native_mcap_parser_support
generic_file_drop_support
generic_robot_log_parser
policy_uplift
learning_proven_value
visual_policy_performance
deployable_policy_readiness
production_certification
marketplace_readiness
sim_to_real_proven
general_robot_intelligence
```
