# 데이터 스키마

공유 JSON schema 파일은 `packages/shared/` 아래에 둔다.

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
        "position_axis_map": "x,y,z",
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

`Isaac-Forge-PegInsert-Direct-v0` 같은 Forge direct insertion task의 native action은 current pose delta가 아니라 fixed asset/hole 기준 normalized target으로 해석된다. 이 semantics는 policy benchmark에는 맞지만 Quest handtracking live teleop 수집 UX에는 맞지 않는다. Live handtracking에서는 `RDF_TELEOP_CONTROL_MODE=auto`가 Forge PegInsert에서 `bounded_direct_ee_target`으로 해석된다. `bounded_direct_ee_target`은 OpenXR retargeter delta를 recentered EEF anchor 기준 desired end-effector target으로 누적하고, robot fingertip이 workspace clamp, max-step/rate-limit, smoothing을 거쳐 그 target을 따라가게 한다. 이 경우 frame metadata의 `control_filter.teleop_control_mode.name`은 `bounded_direct_ee_target`, `control_semantics`는 `bounded_direct_end_effector_target_servo`가 된다. `operator_follow`, `cartesian_delta`, `forge_asset_relative_delta_adapter`는 legacy/debug path로만 사용한다.

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
      "reason": "auto_first_valid_frame",
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

Calibration은 현재 backward-compatible하게 translation offset을 계속 저장한다. 신규 `workspace_alignment_v2`는 raw XR right wrist pose를 현재 robot end-effector pose에 맞추는 translation, orientation alignment용 `rotation_offset_quat`, action filter gain metadata를 추가한다.

Teleoperation control은 live loop에서 optional `rdf_teleop_action_filter`를 통해 조정된다. 이 filter는 position/rotation gain, deadzone, smoothing, signed axis remap을 적용하며, `P` recenter 직후 1 frame movement를 suppress해 operator가 기준점을 다시 잡을 수 있게 한다.

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
  "max_average_input_latency_ms": 120,
  "max_input_latency_ms": 250,
  "max_frame_interval_jitter_ms": 50
}
```

Threshold가 없는 `retargeting_jump`, latency, jitter metric은 기록만 하고 실패 판정에는 사용하지 않는다. `tracking_loss_after_warmup`은 기존 `TRACKING_LOSS > 0.3` 동작을 보존하기 위해 기본 threshold `0.3`을 사용한다.

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
      "native_action_saturation": "fail",
      "native_action_saturation_ratio": 0.18,
      "sync_quality": "pass",
      "control_quality": "fail",
      "quality_failure_reasons": ["RETARGETING_JUMP"]
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
        "RETARGETING_JUMP"
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

`RETARGETING_JUMP`는 task failure가 아니라 `DATA_QUALITY_FAILURE`다. 즉 사용자가 HMD에서 성공했다고 판단한 trajectory는 `operator_success=true`, `human_success_pool=true`로 raw evidence에 남을 수 있다. 다만 replay/action/data-quality gate를 통과하기 전까지 `training_eligible`, `curated_accepted`, `proof_eligible`은 `false`다.

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
