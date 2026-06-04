from __future__ import annotations

import pytest

from app.services.evaluator import (
    _native_action_saturation,
    add_evaluation_semantics,
    evaluate_trajectory,
)


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
        "frames": frames
        or [
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
    result = evaluate_trajectory(
        TASK_CONFIG, SUCCESS_CRITERIA, make_trajectory([0.2, 0.5])
    )
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
            {
                "right_hand_tracked": True,
                "xr_frame_valid": True,
                "recording_started_after_warmup": True,
            },
        ),
        make_frame(
            0.1, 1, [0.75, 0.5], {"right_hand_tracked": False, "xr_frame_valid": True}
        ),
        make_frame(
            0.2, 2, [0.75, 0.5], {"right_hand_tracked": False, "xr_frame_valid": False}
        ),
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
    assert (
        "RETARGETING_JUMP" in result.metrics["data_quality"]["quality_failure_reasons"]
    )
    assert result.metrics["curation"]["raw_saved"] is True
    assert result.metrics["curation"]["training_eligible"] is False
    assert result.metrics["curation"]["curated_accepted"] is False
    assert result.metrics["curation"]["proof_eligible"] is False
    assert result.metrics["retargeting_jump_max"] > 0.5


def test_evaluator_raw_wrist_valid_to_valid_jump_gate() -> None:
    frames = [
        make_frame(
            0.0,
            0,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True},
            {
                "raw_wrist_direct": {
                    "gate_state": "accepted",
                    "valid_to_valid_jump_m": 0.01,
                }
            },
        ),
        make_frame(
            0.1,
            1,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True},
            {"raw_wrist_direct": {"gate_state": "warn", "valid_to_valid_jump_m": 0.12}},
        ),
        make_frame(
            0.2,
            2,
            [0.75, 0.5],
            {"right_hand_tracked": True, "xr_frame_valid": True},
            {
                "raw_wrist_direct": {
                    "gate_state": "accepted",
                    "valid_to_valid_jump_m": 0.02,
                }
            },
        ),
    ]
    criteria = {**SUCCESS_CRITERIA, "max_raw_wrist_valid_to_valid_jump_m": 0.10}

    result = evaluate_trajectory(TASK_CONFIG, criteria, make_trajectory(frames=frames))

    assert result.success is False
    assert result.failure_reason == "RAW_WRIST_JUMP"
    assert result.failure_category == "DATA_QUALITY_FAILURE"
    assert result.metrics["raw_wrist_valid_to_valid_jump"]["fail"] is True
    assert result.metrics["raw_wrist_valid_to_valid_jump"]["max_m"] == 0.12
    assert result.metrics["raw_wrist_valid_to_valid_jump"]["count_over_threshold"] == 1
    assert "RAW_WRIST_JUMP" in result.metrics["data_quality"]["quality_failure_reasons"]
    assert "RAW_WRIST_JUMP" in result.metrics["curation"]["rejection_reasons"]
    assert result.metrics["curation"]["training_eligible"] is False


def test_evaluator_latency_gate() -> None:
    frames = [
        make_frame(
            0.0,
            0,
            [0.75, 0.5],
            {
                "right_hand_tracked": True,
                "xr_frame_valid": True,
                "input_latency_ms": 120,
            },
        ),
        make_frame(
            0.1,
            1,
            [0.75, 0.5],
            {
                "right_hand_tracked": True,
                "xr_frame_valid": True,
                "input_latency_ms": 140,
            },
        ),
        make_frame(
            0.2,
            2,
            [0.75, 0.5],
            {
                "right_hand_tracked": True,
                "xr_frame_valid": True,
                "input_latency_ms": 160,
            },
        ),
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
        peg_frame(
            1.0, 1, distance=0.030, lateral_distance=0.004, alignment=0.1, depth=0.03
        ),
        peg_frame(
            2.0, 2, distance=0.028, lateral_distance=0.003, alignment=0.08, depth=0.032
        ),
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


def _scene_state_frame(
    t: float,
    step: int,
    *,
    eef: list[float],
    peg: list[float],
    hole: list[float],
    hole_target: list[float],
    distance: float = 0.006,
) -> dict:
    return make_frame(
        t,
        step,
        peg,
        {
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "task_state": {
                "peg_position": peg,
                "peg_tip_position": peg,
                "hole_position": hole,
                "hole_target_position": hole_target,
                "peg_tip_distance_to_target": distance,
                "peg_lateral_distance_to_target": min(distance, 0.004),
                "peg_tip_distance_3d_to_target": distance,
                "axis_alignment_error_rad": 0.05,
                "insertion_depth": 0.03,
                "contact_sequence_valid": True,
                "object_drop_detected": False,
            },
        },
        {"retargeted_robot_action": {"command": [0.01 * step, 0.0, 0.0, 1.0]}},
    ) | {"end_effector_position": eef}


def test_peg_in_hole_scene_state_discontinuity_blocks_training() -> None:
    frames = [
        _scene_state_frame(
            0.0,
            0,
            eef=[0.51, -0.10, 0.18],
            peg=[0.50, -0.12, 0.15],
            hole=[0.55, 0.03, 0.00],
            hole_target=[0.55, 0.03, 0.025],
            distance=0.03,
        ),
        _scene_state_frame(
            0.1,
            1,
            eef=[0.64, -0.04, 0.12],
            peg=[0.64, -0.04, 0.09],
            hole=[0.63, -0.03, 0.06],
            hole_target=[0.63, -0.03, 0.085],
        ),
        _scene_state_frame(
            0.2,
            2,
            eef=[0.64, -0.04, 0.12],
            peg=[0.64, -0.04, 0.09],
            hole=[0.63, -0.03, 0.06],
            hole_target=[0.63, -0.03, 0.085],
        ),
    ]
    trajectory = peg_trajectory(frames)
    trajectory["summary"].update(
        {
            "episode_status": "success",
            "episode_finalize_reason": "operator_success",
            "replay_verified": True,
        }
    )

    result = evaluate_trajectory(PEG_CONFIG, PEG_CRITERIA, trajectory)

    assert result.success is False
    assert result.failure_reason == "SCENE_STATE_DISCONTINUITY"
    assert result.failure_category == "DATA_QUALITY_FAILURE"
    assert result.metrics["scene_state_discontinuity"]["fail"] is True
    assert result.metrics["scene_state_discontinuity"]["frames"] == [1]
    assert (
        "SCENE_STATE_DISCONTINUITY"
        in result.metrics["data_quality"]["quality_failure_reasons"]
    )
    assert result.metrics["curation"]["training_eligible"] is False
    assert (
        "SCENE_STATE_DISCONTINUITY" in result.metrics["curation"]["rejection_reasons"]
    )


# ---------------------------------------------------------------------------
# _native_action_saturation — phase-conditional unit tests
# ---------------------------------------------------------------------------


def _sat_frame(phase: str, *, saturated: bool) -> dict:
    value = 1.0 if saturated else 0.0
    return {
        "metadata": {"action_phase": phase},
        "action": {"native_isaac_action": [value, 0.0, 0.0, 0.0, 0.0, 0.0]},
    }


def test_native_action_saturation_insert_heavy_passes() -> None:
    frames = (
        [_sat_frame("INSERT", saturated=True)] * 18
        + [_sat_frame("INSERT", saturated=False)] * 82
        + [_sat_frame("SEAT", saturated=False)] * 18
        + [_sat_frame("CONTACT", saturated=False)] * 2
    )

    status, ratio, phase_ratios = _native_action_saturation(frames)

    assert status == "pass"
    assert ratio == pytest.approx(0.15)
    assert phase_ratios["INSERT"] == pytest.approx(0.18)
    assert phase_ratios.get("SEAT", 0.0) == pytest.approx(0.0)


def test_native_action_saturation_seat_above_threshold_fails() -> None:
    frames = [_sat_frame("SEAT", saturated=True)] * 40 + [
        _sat_frame("SEAT", saturated=False)
    ] * 60

    status, _, phase_ratios = _native_action_saturation(frames)

    assert status == "fail"
    assert phase_ratios["SEAT"] == pytest.approx(0.40)


def test_native_action_saturation_seat_below_threshold_passes() -> None:
    frames = [_sat_frame("SEAT", saturated=True)] * 25 + [
        _sat_frame("SEAT", saturated=False)
    ] * 75

    status, _, phase_ratios = _native_action_saturation(frames)

    assert status == "pass"
    assert phase_ratios["SEAT"] == pytest.approx(0.25)


def test_native_action_saturation_gripper_excluded_from_sat() -> None:
    frame = {
        "metadata": {"action_phase": "SEAT"},
        "action": {"native_isaac_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]},
    }

    status, ratio, phase_ratios = _native_action_saturation([frame])

    assert status == "pass"
    assert ratio == pytest.approx(0.0)
    assert phase_ratios.get("SEAT", 0.0) == pytest.approx(0.0)


def test_native_action_saturation_no_action_returns_unknown() -> None:
    frames = [{"metadata": {"action_phase": "INSERT"}, "action": {}}]

    status, ratio, phase_ratios = _native_action_saturation(frames)

    assert status == "unknown"
    assert ratio is None
    assert phase_ratios == {}


# ---------------------------------------------------------------------------
# add_evaluation_semantics — phase-conditional integration tests
# ---------------------------------------------------------------------------


def _make_sat_trajectory(
    insert_sat_ratio: float, seat_sat_ratio: float
) -> tuple[dict, list[dict]]:
    insert_sat = int(100 * insert_sat_ratio)
    insert_clear = 100 - insert_sat
    seat_sat = int(100 * seat_sat_ratio)
    seat_clear = 100 - seat_sat
    frames = (
        [_sat_frame("INSERT", saturated=True)] * insert_sat
        + [_sat_frame("INSERT", saturated=False)] * insert_clear
        + [_sat_frame("SEAT", saturated=True)] * seat_sat
        + [_sat_frame("SEAT", saturated=False)] * seat_clear
    )
    trajectory = {"frames": frames, "summary": {}}
    return trajectory, frames


def test_add_evaluation_semantics_stores_phase_ratios() -> None:
    trajectory, _ = _make_sat_trajectory(insert_sat_ratio=0.20, seat_sat_ratio=0.0)

    metrics = add_evaluation_semantics(
        {}, trajectory, success=True, failure_reason=None
    )

    dq = metrics["data_quality"]
    assert "native_action_saturation_phase_ratios" in dq
    assert "native_action_saturation_seat_ratio" in dq
    assert dq["native_action_saturation_phase_ratios"]["INSERT"] == pytest.approx(0.20)
    assert dq["native_action_saturation_seat_ratio"] == pytest.approx(0.0)


def test_add_evaluation_semantics_insert_saturation_does_not_block() -> None:
    trajectory, _ = _make_sat_trajectory(insert_sat_ratio=0.20, seat_sat_ratio=0.0)

    metrics = add_evaluation_semantics(
        {}, trajectory, success=True, failure_reason=None
    )

    dq = metrics["data_quality"]
    assert dq["native_action_saturation"] == "pass"
    assert "NATIVE_ACTION_SATURATION" not in dq["quality_failure_reasons"]


def test_add_evaluation_semantics_seat_saturation_above_threshold_blocks() -> None:
    trajectory, _ = _make_sat_trajectory(insert_sat_ratio=0.0, seat_sat_ratio=0.40)

    metrics = add_evaluation_semantics(
        {}, trajectory, success=True, failure_reason=None
    )

    dq = metrics["data_quality"]
    assert dq["native_action_saturation"] == "fail"
    assert "NATIVE_ACTION_SATURATION" in dq["quality_failure_reasons"]


if __name__ == "__main__":
    test_evaluator_success()
    test_evaluator_target_missed()
