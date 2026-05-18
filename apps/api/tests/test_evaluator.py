from __future__ import annotations

from app.services.evaluator import evaluate_trajectory


TASK_CONFIG = {"target_position": [0.75, 0.5], "success_tolerance": 0.03}
SUCCESS_CRITERIA = {
    "distance_to_target_max": 0.03,
    "min_stable_steps": 2,
    "max_completion_time_sec": 30,
}


def make_frame(
    t: float,
    step: int,
    object_position: list[float],
    metadata: dict | None = None,
    action: dict | None = None,
) -> dict:
    return {
        "t": t,
        "step": step,
        "end_effector_position": object_position,
        "object_position": object_position,
        "metadata": metadata or {"right_hand_tracked": True, "xr_frame_valid": True},
        **({"action": action} if action is not None else {}),
    }


def make_trajectory(
    object_position: list[float] | None = None,
    frames: list[dict] | None = None,
) -> dict:
    object_position = object_position or [0.75, 0.5]
    return {
        "schema_version": "0.1.0",
        "source": {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "simulator": "isaac_lab",
            "robot": "franka",
            "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
        },
        "frames": frames or [
            make_frame(0.0, 0, [0.1, 0.5]),
            make_frame(5.0, 1, object_position),
            make_frame(6.0, 2, object_position),
        ],
        "summary": {"duration_sec": 6.0, "collision_count": 0},
    }


def test_evaluator_success() -> None:
    result = evaluate_trajectory(TASK_CONFIG, SUCCESS_CRITERIA, make_trajectory())
    assert result.success is True
    assert result.failure_reason is None
    assert result.score > 0.0


def test_evaluator_target_missed() -> None:
    result = evaluate_trajectory(TASK_CONFIG, SUCCESS_CRITERIA, make_trajectory([0.2, 0.5]))
    assert result.success is False
    assert result.failure_reason == "TARGET_MISSED"
    assert result.failure_category == "TASK_OUTCOME_FAILURE"
    assert result.metrics["failure_category"] == "TASK_OUTCOME_FAILURE"
    assert result.metrics["task_outcome"]["evaluator_task_success"] is False
    assert result.metrics["task_outcome"]["task_failure_reason"] == "TARGET_MISSED"


def test_evaluator_tracks_loss_after_warmup_gate() -> None:
    frames = [
        make_frame(
            0.0,
            0,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True, "recording_started_after_warmup": True},
        ),
        make_frame(0.1, 1, [0.75, 0.5], {"right_hand_tracked": False, "xr_frame_valid": True}),
        make_frame(0.2, 2, [0.75, 0.5], {"right_hand_tracked": False, "xr_frame_valid": False}),
    ]
    criteria = {**SUCCESS_CRITERIA, "max_tracking_loss_after_warmup": 0.5}
    result = evaluate_trajectory(TASK_CONFIG, criteria, make_trajectory(frames=frames))
    assert result.success is False
    assert result.failure_reason == "TRACKING_LOSS"
    assert result.metrics["tracking_loss_after_warmup"] == 2 / 3


def test_evaluator_retargeting_jump_gate() -> None:
    frames = [
        make_frame(
            0.0,
            0,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True},
            {"retargeted_robot_action": {"command": [0.0, 0.0, 0.0, 1.0]}},
        ),
        make_frame(
            0.1,
            1,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True},
            {"retargeted_robot_action": {"command": [0.05, 0.0, 0.0, 1.0]}},
        ),
        make_frame(
            0.2,
            2,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True},
            {"retargeted_robot_action": {"command": [1.0, 0.0, 0.0, 1.0]}},
        ),
    ]
    criteria = {**SUCCESS_CRITERIA, "max_retargeting_jump": 0.5}
    result = evaluate_trajectory(TASK_CONFIG, criteria, make_trajectory(frames=frames))
    assert result.success is False
    assert result.failure_reason == "RETARGETING_JUMP"
    assert result.failure_category == "DATA_QUALITY_FAILURE"
    assert result.metrics["failure_category"] == "DATA_QUALITY_FAILURE"
    assert result.metrics["task_outcome"]["evaluator_task_success"] == "unknown"
    assert result.metrics["task_outcome"]["task_failure_reason"] is None
    assert result.metrics["data_quality"]["retargeting_jump"] == "fail"
    assert "RETARGETING_JUMP" in result.metrics["data_quality"]["quality_failure_reasons"]
    assert result.metrics["curation"]["raw_saved"] is True
    assert result.metrics["curation"]["training_eligible"] is False
    assert result.metrics["curation"]["curated_accepted"] is False
    assert result.metrics["curation"]["proof_eligible"] is False
    assert result.metrics["retargeting_jump_max"] > 0.5


def test_evaluator_latency_gate() -> None:
    frames = [
        make_frame(0.0, 0, [0.75, 0.5], {"right_hand_tracked": True, "xr_frame_valid": True, "input_latency_ms": 120}),
        make_frame(0.1, 1, [0.75, 0.5], {"right_hand_tracked": True, "xr_frame_valid": True, "input_latency_ms": 140}),
        make_frame(0.2, 2, [0.75, 0.5], {"right_hand_tracked": True, "xr_frame_valid": True, "input_latency_ms": 160}),
    ]
    criteria = {**SUCCESS_CRITERIA, "max_average_input_latency_ms": 100}
    result = evaluate_trajectory(TASK_CONFIG, criteria, make_trajectory(frames=frames))
    assert result.success is False
    assert result.failure_reason == "INPUT_LATENCY"
    assert result.metrics["average_input_latency_ms"] == 140


def test_evaluator_jitter_gate() -> None:
    frames = [
        make_frame(0.0, 0, [0.75, 0.5]),
        make_frame(0.02, 1, [0.75, 0.5]),
        make_frame(0.5, 2, [0.75, 0.5]),
    ]
    criteria = {**SUCCESS_CRITERIA, "max_frame_interval_jitter_ms": 50}
    result = evaluate_trajectory(TASK_CONFIG, criteria, make_trajectory(frames=frames))
    assert result.success is False
    assert result.failure_reason == "FRAME_JITTER"
    assert result.metrics["frame_interval_jitter_ms"] > 50


def test_evaluator_quality_thresholds_are_backward_compatible() -> None:
    result = evaluate_trajectory(TASK_CONFIG, SUCCESS_CRITERIA, make_trajectory())
    assert result.success is True
    assert result.metrics["retargeting_jump_max"] == 0.0
    assert result.metrics["average_input_latency_ms"] is None
    assert result.metrics["frame_interval_jitter_ms"] is not None


def peg_frame(
    t: float,
    step: int,
    *,
    distance: float,
    alignment: float,
    depth: float,
    lateral_distance: float | None = None,
    distance_3d: float | None = None,
    contact_sequence_valid: bool = True,
    object_drop_detected: bool = False,
) -> dict:
    return make_frame(
        t,
        step,
        [0.75, 0.5],
        {
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "task_state": {
                "peg_tip_distance_to_target": distance,
                "peg_lateral_distance_to_target": lateral_distance,
                "peg_tip_distance_3d_to_target": distance_3d,
                "axis_alignment_error_rad": alignment,
                "insertion_depth": depth,
                "contact_sequence_valid": contact_sequence_valid,
                "object_drop_detected": object_drop_detected,
            },
        },
        {"retargeted_robot_action": {"command": [0.01 * step, 0.0, 0.0, 1.0]}},
    )


def peg_trajectory(frames: list[dict]) -> dict:
    trajectory = make_trajectory(frames=frames)
    trajectory["source"]["task_name"] = "peg_in_hole"
    trajectory["summary"] = {"duration_sec": frames[-1]["t"], "collision_count": 0}
    return trajectory


PEG_CONFIG = {"task_type": "peg_in_hole"}
PEG_CRITERIA = {
    "peg_tip_distance_to_target_max": 0.015,
    "peg_axis_alignment_error_max_rad": 0.25,
    "insertion_depth_min": 0.025,
    "min_stable_steps": 2,
    "max_completion_time_sec": 45,
    "max_retargeting_jump": 0.25,
}


def test_peg_in_hole_task_state_success() -> None:
    frames = [
        peg_frame(0.0, 0, distance=0.05, alignment=0.4, depth=0.0),
        peg_frame(1.0, 1, distance=0.01, alignment=0.1, depth=0.03),
        peg_frame(2.0, 2, distance=0.008, alignment=0.08, depth=0.032),
    ]

    result = evaluate_trajectory(PEG_CONFIG, PEG_CRITERIA, peg_trajectory(frames))

    assert result.success is True
    assert result.failure_reason is None
    assert result.failure_mode == "SUCCESS"
    assert result.metrics["task_type"] == "peg_in_hole"
    assert result.metrics["insertion_depth"] == 0.032
    assert result.metrics["stable_final_steps"] == 2
    assert result.task_completion_score > 0.0
    assert result.contact_sequence_score == 1.0


def test_peg_in_hole_prefers_lateral_distance_for_insertion_success() -> None:
    frames = [
        peg_frame(0.0, 0, distance=0.05, alignment=0.4, depth=0.0),
        peg_frame(1.0, 1, distance=0.030, lateral_distance=0.004, alignment=0.1, depth=0.03),
        peg_frame(2.0, 2, distance=0.028, lateral_distance=0.003, alignment=0.08, depth=0.032),
    ]

    result = evaluate_trajectory(PEG_CONFIG, PEG_CRITERIA, peg_trajectory(frames))

    assert result.success is True
    assert result.failure_reason is None
    assert result.metrics["peg_distance_metric"] == "lateral_projection"
    assert result.metrics["peg_lateral_distance_to_target"] == 0.003
    assert result.metrics["peg_tip_distance_3d_to_target"] == 0.028
    assert result.metrics["stable_final_steps"] == 2


def test_task_state_auto_success_is_not_human_success_pool() -> None:
    frames = [
        peg_frame(0.0, 0, distance=0.05, alignment=0.4, depth=0.0),
        peg_frame(1.0, 1, distance=0.01, alignment=0.1, depth=0.03),
        peg_frame(2.0, 2, distance=0.008, alignment=0.08, depth=0.032),
    ]
    trajectory = peg_trajectory(frames)
    trajectory["summary"].update(
        {
            "episode_status": "success",
            "episode_finalize_reason": "auto_success_ready",
            "success_label_source": "task_state_auto",
            "auto_success_ready": True,
            "operator_success": False,
        }
    )

    result = evaluate_trajectory(PEG_CONFIG, PEG_CRITERIA, trajectory)

    assert result.success is True
    assert result.metrics["task_outcome"]["operator_success"] is False
    assert result.metrics["task_outcome"]["auto_success_ready"] is True
    assert result.metrics["task_outcome"]["success_label_source"] == "task_state_auto"
    assert result.metrics["curation"]["human_success_pool"] is False
    assert result.metrics["curation"]["task_success_candidate_pool"] is True
    assert result.metrics["curation"]["training_eligible"] is False


def test_peg_in_hole_alignment_failure() -> None:
    frames = [
        peg_frame(0.0, 0, distance=0.01, alignment=0.5, depth=0.03),
        peg_frame(1.0, 1, distance=0.01, alignment=0.5, depth=0.03),
    ]

    result = evaluate_trajectory(PEG_CONFIG, PEG_CRITERIA, peg_trajectory(frames))

    assert result.success is False
    assert result.failure_reason == "ALIGNMENT_ERROR"
    assert result.failure_mode == "ALIGNMENT_ERROR"
    assert result.metrics["axis_alignment_error_rad"] == 0.5


def test_peg_in_hole_insertion_depth_failure() -> None:
    frames = [
        peg_frame(0.0, 0, distance=0.01, alignment=0.1, depth=0.01),
        peg_frame(1.0, 1, distance=0.01, alignment=0.1, depth=0.01),
    ]

    result = evaluate_trajectory(PEG_CONFIG, PEG_CRITERIA, peg_trajectory(frames))

    assert result.success is False
    assert result.failure_reason == "INSUFFICIENT_INSERTION_DEPTH"
    assert result.metrics["insertion_depth"] == 0.01


if __name__ == "__main__":
    test_evaluator_success()
    test_evaluator_target_missed()
