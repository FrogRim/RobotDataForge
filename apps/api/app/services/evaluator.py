from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.utils.geometry import euclidean, path_length
from app.utils.scoring import clamp01, normalized_path_jitter


FAILURE_TAXONOMY = {
    "TIMEOUT",
    "TARGET_MISSED",
    "UNSTABLE_FINAL_STATE",
    "NO_TRAJECTORY",
    "INVALID_TRAJECTORY",
    "OUT_OF_BOUNDS",
    "PHYSICALLY_IMPLAUSIBLE",
    "TRACKING_LOSS",
    "RETARGETING_JUMP",
    "RAW_WRIST_JUMP",
    "SCENE_STATE_DISCONTINUITY",
    "INPUT_LATENCY",
    "FRAME_JITTER",
    "EXCESSIVE_COLLISION",
    "BAD_CONTACT_SEQUENCE",
    "GRIPPER_FAILURE",
    "OBJECT_DROPPED",
    "ALIGNMENT_ERROR",
    "INSUFFICIENT_INSERTION_DEPTH",
    "SIM_RUNTIME_ERROR",
    "SYNC_FAILURE",
    "MISSING_MODALITY",
    "LOW_DATA_USABILITY",
    "CLOCK_DRIFT",
    "TIMESTAMP_NON_MONOTONIC",
}

EVALUATION_SEMANTICS_VERSION = "rdf_evaluation_semantics_v0.1.0"

FAILURE_CATEGORIES = {
    "TASK_OUTCOME_FAILURE",
    "DATA_QUALITY_FAILURE",
    "REPLAY_FAILURE",
    "ACTION_CONTRACT_FAILURE",
    "METADATA_FAILURE",
    "UNKNOWN",
}

TASK_OUTCOME_FAILURES = {
    "TIMEOUT",
    "TARGET_MISSED",
    "UNSTABLE_FINAL_STATE",
    "OUT_OF_BOUNDS",
    "EXCESSIVE_COLLISION",
    "BAD_CONTACT_SEQUENCE",
    "GRIPPER_FAILURE",
    "OBJECT_DROPPED",
    "ALIGNMENT_ERROR",
    "INSUFFICIENT_INSERTION_DEPTH",
}

DATA_QUALITY_FAILURES = {
    "PHYSICALLY_IMPLAUSIBLE",
    "TRACKING_LOSS",
    "RETARGETING_JUMP",
    "RAW_WRIST_JUMP",
    "SCENE_STATE_DISCONTINUITY",
    "INPUT_LATENCY",
    "FRAME_JITTER",
    "SYNC_FAILURE",
    "LOW_DATA_USABILITY",
    "CLOCK_DRIFT",
    "TIMESTAMP_NON_MONOTONIC",
}

METADATA_FAILURES = {
    "NO_TRAJECTORY",
    "INVALID_TRAJECTORY",
    "MISSING_MODALITY",
}

REPLAY_FAILURES = {
    "REPLAY_NOT_VERIFIED",
    "REPLAY_FAILED",
}

ACTION_CONTRACT_FAILURES = {
    "ACTION_CONTRACT_INVALID",
    "NATIVE_ACTION_SATURATION",
}

REQUIRED_SOURCE_FIELDS = {"input_device", "runtime", "simulator", "robot", "task_name"}
SEAT_SAT_FAIL_THRESHOLD = 0.30
RAW_WRIST_VALID_TO_VALID_JUMP_DEFAULT_THRESHOLD_M = 0.10
SCENE_STATE_DYNAMIC_JUMP_THRESHOLD_M = 0.05
SCENE_STATE_STATIC_TARGET_JUMP_THRESHOLD_M = 0.02
SCENE_STATE_EVENT_LIMIT = 50


@dataclass(frozen=True)
class EvaluationResult:
    success: bool
    score: float
    quality_score: float
    novelty_score: float
    stability_score: float
    efficiency_score: float
    smoothness_score: float
    fraud_risk_score: float
    task_completion_score: float
    interaction_quality_score: float
    contact_sequence_score: float
    physical_plausibility_score: float
    data_usability_score: float | None
    evaluator_confidence: float
    failure_mode: str | None
    failure_reason: str | None
    failure_category: str
    metrics: dict[str, Any]


def _frames(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    frames = trajectory.get("frames") or []
    return frames if isinstance(frames, list) else []


def _positions(frames: list[dict[str, Any]], key: str) -> list[list[float]]:
    points: list[list[float]] = []
    for frame in frames:
        value = frame.get(key)
        if isinstance(value, list) and value:
            points.append([float(v) for v in value])
    return points


def _duration(trajectory: dict[str, Any], frames: list[dict[str, Any]]) -> float:
    summary = trajectory.get("summary") or {}
    if summary.get("duration_sec") is not None:
        return float(summary["duration_sec"])
    if len(frames) >= 2:
        return max(
            0.0, float(frames[-1].get("t", 0.0)) - float(frames[0].get("t", 0.0))
        )
    return 0.0


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _vector_or_none(value: Any, *, min_length: int = 1) -> list[float] | None:
    if not isinstance(value, list) or len(value) < min_length:
        return None
    vector: list[float] = []
    for item in value:
        number = _float_or_none(item)
        if number is None:
            return None
        vector.append(number)
    return vector


def failure_category_for_reason(reason: str | None) -> str:
    if reason is None:
        return "UNKNOWN"
    if reason in TASK_OUTCOME_FAILURES:
        return "TASK_OUTCOME_FAILURE"
    if reason in DATA_QUALITY_FAILURES:
        return "DATA_QUALITY_FAILURE"
    if reason in REPLAY_FAILURES:
        return "REPLAY_FAILURE"
    if reason in ACTION_CONTRACT_FAILURES:
        return "ACTION_CONTRACT_FAILURE"
    if reason in METADATA_FAILURES:
        return "METADATA_FAILURE"
    return "UNKNOWN"


def _status_for_failure(
    reason: str | None, failure_names: set[str], *, evidence_available: bool = True
) -> str:
    if reason in failure_names:
        return "fail"
    return "pass" if evidence_available else "unknown"


def _operator_success(trajectory: dict[str, Any]) -> bool:
    summary = (
        trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    )
    status = str(summary.get("episode_status") or "").lower()
    finalize_reason = str(
        summary.get("episode_finalize_reason") or summary.get("complete_reason") or ""
    ).lower()
    success_label_source = str(summary.get("success_label_source") or "").lower()
    if (
        success_label_source == "task_state_auto"
        or finalize_reason == "auto_success_ready"
    ):
        return False
    return status == "success" or finalize_reason in {"operator_success", "success"}


def _auto_success_ready(trajectory: dict[str, Any]) -> bool:
    summary = (
        trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    )
    finalize_reason = str(
        summary.get("episode_finalize_reason") or summary.get("complete_reason") or ""
    ).lower()
    success_label_source = str(summary.get("success_label_source") or "").lower()
    return bool(
        summary.get("auto_success_ready") is True
        or success_label_source == "task_state_auto"
        or finalize_reason == "auto_success_ready"
    )


def _success_label_source(trajectory: dict[str, Any]) -> str | None:
    summary = (
        trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    )
    source = summary.get("success_label_source")
    return str(source) if isinstance(source, str) and source.strip() else None


def _replay_verified(trajectory: dict[str, Any]) -> bool:
    summary = (
        trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    )
    replay_gate = summary.get("action_replay_gate")
    return isinstance(replay_gate, dict) and replay_gate.get("passed") is True


def _action_contract_status(frames: list[dict[str, Any]]) -> str:
    saw_action = False
    saw_contract = False
    for frame in frames:
        action = frame.get("action")
        if not isinstance(action, dict):
            continue
        saw_action = True
        if action.get("action_contract_version"):
            saw_contract = True
    if saw_contract:
        return "pass"
    return "unknown" if saw_action else "unknown"


def _frame_phase(frame: dict[str, Any]) -> str:
    metadata = frame.get("metadata") or {}
    phase = metadata.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    task_state = metadata.get("task_state") or {}
    phase = task_state.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    phase = frame.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    return "UNKNOWN"


def _native_action_saturation(
    frames: list[dict[str, Any]],
) -> tuple[str, float | None, dict[str, float]]:
    """Return saturation status, aggregate ratio, and per-phase ratios."""
    total = 0
    saturated = 0
    phase_total: dict[str, int] = {}
    phase_saturated: dict[str, int] = {}

    for frame in frames:
        action = frame.get("action")
        if not isinstance(action, dict):
            continue
        candidates: list[Any] = [
            action.get("native_isaac_action"),
            (action.get("executed_control") or {}).get("native_isaac_action")
            if isinstance(action.get("executed_control"), dict)
            else None,
            action.get("applied"),
        ]
        vector = None
        for candidate in candidates:
            vector = _vector_or_none(candidate)
            if vector:
                break
        if not vector:
            continue

        phase = _frame_phase(frame)
        is_saturated = any(abs(value) >= 0.999 for value in vector[:6])
        total += 1
        if is_saturated:
            saturated += 1
        phase_total[phase] = phase_total.get(phase, 0) + 1
        if is_saturated:
            phase_saturated[phase] = phase_saturated.get(phase, 0) + 1

    if total == 0:
        return "unknown", None, {}

    aggregate_ratio = saturated / total
    phase_ratios: dict[str, float] = {
        phase: phase_saturated.get(phase, 0) / count
        for phase, count in phase_total.items()
    }
    seat_ratio = phase_ratios.get("SEAT", 0.0)
    status = "fail" if seat_ratio > SEAT_SAT_FAIL_THRESHOLD else "pass"
    return status, aggregate_ratio, phase_ratios


def _sync_quality_status(metrics: dict[str, Any], reason: str | None) -> str:
    if reason in {
        "SYNC_FAILURE",
        "CLOCK_DRIFT",
        "TIMESTAMP_NON_MONOTONIC",
        "FRAME_JITTER",
    }:
        return "fail"
    sync_metrics = metrics.get("sync_metrics")
    if isinstance(sync_metrics, dict):
        score = _float_or_none(sync_metrics.get("quality_score"))
        if score is None:
            return "unknown"
        return "pass" if score >= 0.7 else "fail"
    return "unknown"


def add_evaluation_semantics(
    metrics: dict[str, Any],
    trajectory: dict[str, Any],
    *,
    success: bool,
    failure_reason: str | None,
    failure_category: str | None = None,
    evaluator_confidence: float | None = None,
    data_usability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach RDF MVP-1 outcome/quality/curation semantics without changing legacy success."""

    frames = _frames(trajectory)
    category = failure_category or failure_category_for_reason(failure_reason)
    if success:
        evaluator_task_success: bool | str = True
        task_success_confidence = evaluator_confidence
        task_failure_reason = None
    elif category == "TASK_OUTCOME_FAILURE":
        evaluator_task_success = False
        task_success_confidence = 0.0
        task_failure_reason = failure_reason
    else:
        evaluator_task_success = "unknown"
        task_success_confidence = None
        task_failure_reason = None

    operator_success = _operator_success(trajectory)
    auto_success_ready = _auto_success_ready(trajectory)
    success_label_source = _success_label_source(trajectory)
    task_success_candidate_pool = bool(operator_success or auto_success_ready)
    replay_verified = _replay_verified(trajectory)
    action_contract_status = _action_contract_status(frames)
    (
        native_action_saturation,
        native_action_saturation_ratio,
        native_action_saturation_phase_ratios,
    ) = _native_action_saturation(frames)
    sync_quality = _sync_quality_status(metrics, failure_reason)
    retargeting_jump = _status_for_failure(
        failure_reason,
        {"RETARGETING_JUMP"},
        evidence_available="retargeting_jump_max" in metrics,
    )
    raw_wrist_valid_to_valid_jump = _status_for_failure(
        failure_reason,
        {"RAW_WRIST_JUMP"},
        evidence_available="raw_wrist_valid_to_valid_jump" in metrics,
    )

    data_quality_reasons: list[str] = []
    if category == "DATA_QUALITY_FAILURE" and failure_reason:
        data_quality_reasons.append(failure_reason)
    if (
        native_action_saturation == "fail"
        and "NATIVE_ACTION_SATURATION" not in data_quality_reasons
    ):
        data_quality_reasons.append("NATIVE_ACTION_SATURATION")
    if sync_quality == "fail" and failure_reason in {
        "SYNC_FAILURE",
        "CLOCK_DRIFT",
        "TIMESTAMP_NON_MONOTONIC",
        "FRAME_JITTER",
    }:
        if failure_reason not in data_quality_reasons:
            data_quality_reasons.append(failure_reason)

    action_contract_valid = action_contract_status == "pass"
    data_quality_passed = (
        not data_quality_reasons
        and retargeting_jump != "fail"
        and raw_wrist_valid_to_valid_jump != "fail"
        and sync_quality != "fail"
    )
    rejection_reasons: list[str] = []
    if not task_success_candidate_pool:
        summary = (
            trajectory.get("summary")
            if isinstance(trajectory.get("summary"), dict)
            else {}
        )
        rejection_reasons.append(
            f"EPISODE_STATUS:{summary.get('episode_status') or 'unknown'}"
        )
    if not replay_verified:
        rejection_reasons.append("REPLAY_NOT_VERIFIED")
    if not success:
        rejection_reasons.append("EVALUATION_FAILED")
        if failure_reason:
            rejection_reasons.append(failure_reason)
    if action_contract_status != "pass":
        rejection_reasons.append("ACTION_CONTRACT_NOT_VERIFIED")
    for reason in data_quality_reasons:
        if reason not in rejection_reasons:
            rejection_reasons.append(reason)
    if data_usability:
        if data_usability.get("usable") is False:
            for reason in data_usability.get("rejection_reasons") or []:
                if isinstance(reason, str) and reason not in rejection_reasons:
                    rejection_reasons.append(reason)

    training_eligible = bool(
        task_success_candidate_pool
        and success
        and replay_verified
        and action_contract_valid
        and data_quality_passed
        and not rejection_reasons
    )
    proof_eligible = bool(training_eligible and evaluator_task_success is True)

    enriched = dict(metrics)
    enriched["evaluation_semantics_version"] = EVALUATION_SEMANTICS_VERSION
    enriched["failure_category"] = category
    enriched["task_outcome"] = {
        "operator_success": operator_success,
        "auto_success_ready": auto_success_ready,
        "success_label_source": success_label_source,
        "evaluator_task_success": evaluator_task_success,
        "task_success_confidence": task_success_confidence,
        "task_failure_reason": task_failure_reason,
    }
    enriched["data_quality"] = {
        "replay_verified": replay_verified,
        "action_contract_valid": action_contract_valid,
        "action_contract_status": action_contract_status,
        "retargeting_jump": retargeting_jump,
        "raw_wrist_valid_to_valid_jump": raw_wrist_valid_to_valid_jump,
        "native_action_saturation": native_action_saturation,
        "native_action_saturation_ratio": native_action_saturation_ratio,
        "native_action_saturation_phase_ratios": native_action_saturation_phase_ratios,
        "native_action_saturation_seat_ratio": native_action_saturation_phase_ratios.get(
            "SEAT", 0.0
        ),
        "sync_quality": sync_quality,
        "control_quality": "fail"
        if data_quality_reasons or action_contract_status == "fail"
        else "unknown"
        if action_contract_status != "pass"
        else "pass",
        "quality_failure_reasons": sorted(set(data_quality_reasons)),
    }
    enriched["curation"] = {
        "raw_saved": True,
        "human_success_pool": operator_success,
        "task_success_candidate_pool": task_success_candidate_pool,
        "training_eligible": training_eligible,
        "curated_accepted": training_eligible,
        "proof_eligible": proof_eligible,
        "rejection_reasons": sorted(set(rejection_reasons)),
    }
    return enriched


def _threshold(
    task_config: dict[str, Any],
    success_criteria: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: float | None = None,
) -> float | None:
    for source in (success_criteria, task_config):
        for key in keys:
            value = _float_or_none(source.get(key))
            if value is not None:
                return value
    return default


def _tracking_loss_rate(frames: list[dict[str, Any]]) -> float:
    if not frames:
        return 1.0
    losses = 0
    for frame in frames:
        metadata = frame.get("metadata") or {}
        if (
            metadata.get("right_hand_tracked") is False
            or metadata.get("xr_frame_valid") is False
        ):
            losses += 1
    return losses / len(frames)


def _post_warmup_frames(
    trajectory: dict[str, Any], frames: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    for index, frame in enumerate(frames):
        metadata = frame.get("metadata") or {}
        if metadata.get("recording_started_after_warmup") is True:
            return frames[index:]

    summary = trajectory.get("summary") or {}
    warmup_dropped_frames = int(
        _float_or_none(summary.get("warmup_dropped_frames")) or 0
    )
    if warmup_dropped_frames > 0:
        # Current recorder drops warm-up frames before saving. If no explicit marker
        # exists, the stored frames are already post-warm-up.
        return frames
    return frames


def _latency_stats(frames: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    latencies: list[float] = []
    for frame in frames:
        metadata = frame.get("metadata") or {}
        latency = _float_or_none(metadata.get("input_latency_ms"))
        if latency is not None:
            latencies.append(latency)
    if not latencies:
        return None, None
    return sum(latencies) / len(latencies), max(latencies)


def _frame_interval_stats(
    frames: list[dict[str, Any]],
) -> tuple[float | None, float | None]:
    times: list[float] = []
    for frame in frames:
        timestamp = _float_or_none(frame.get("t"))
        if timestamp is not None:
            times.append(timestamp)
    if len(times) < 2:
        return None, None

    intervals = [
        times[index] - times[index - 1]
        for index in range(1, len(times))
        if times[index] >= times[index - 1]
    ]
    if not intervals:
        return None, None

    mean_interval = sum(intervals) / len(intervals)
    jitter = max(abs(interval - mean_interval) for interval in intervals)
    return mean_interval * 1000.0, jitter * 1000.0


def _retargeting_vector(frame: dict[str, Any]) -> list[float] | None:
    def command_vector(value: Any) -> list[float] | None:
        vector = _vector_or_none(value)
        if vector:
            return vector
        if not isinstance(value, dict):
            return None
        for key in ("command", "robot_action", "action", "retargeted_robot_action"):
            vector = _vector_or_none(value.get(key))
            if vector:
                return vector
        relative_vector: list[float] = []
        for key in ("delta_position", "delta_rotation"):
            vector = _vector_or_none(value.get(key))
            if vector:
                relative_vector.extend(vector)
        gripper = _float_or_none(value.get("gripper"))
        if gripper is not None:
            relative_vector.append(gripper)
        return relative_vector or None

    action = frame.get("action")
    if isinstance(action, dict):
        for key in ("retargeted_robot_action", "relative", "raw"):
            vector = command_vector(action.get(key))
            if vector:
                return vector
    elif isinstance(action, list):
        vector = command_vector(action)
        if vector:
            return vector

    metadata = frame.get("metadata") or {}
    retargeted = metadata.get("retargeted") or {}
    if isinstance(retargeted, dict):
        for key in ("robot_action", "action", "retargeted_robot_action"):
            vector = command_vector(retargeted.get(key))
            if vector:
                return vector

    for section_name in ("aligned_xr", "raw_xr"):
        section = metadata.get(section_name) or {}
        if isinstance(section, dict):
            pose = _vector_or_none(section.get("right_wrist_pose"), min_length=3)
            if pose:
                return pose[:3]

    pose = _vector_or_none(metadata.get("right_wrist_pose"), min_length=3)
    if pose:
        return pose[:3]
    return None


def _retargeting_jump_stats(frames: list[dict[str, Any]]) -> tuple[float, float]:
    vectors = [
        vector for frame in frames if (vector := _retargeting_vector(frame)) is not None
    ]
    jumps = [
        euclidean(vectors[index - 1], vectors[index])
        for index in range(1, len(vectors))
        if len(vectors[index - 1]) == len(vectors[index])
    ]
    if not jumps:
        return 0.0, 0.0
    return max(jumps), sum(jumps) / len(jumps)


def _raw_wrist_direct_payload(frame: dict[str, Any]) -> dict[str, Any]:
    """Return raw-wrist direct-control diagnostics from known frame locations."""

    action = frame.get("action")
    if isinstance(action, dict) and isinstance(action.get("raw_wrist_direct"), dict):
        return action["raw_wrist_direct"]

    metadata = frame.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("raw_wrist_direct", "raw_wrist_direct_control"):
            value = metadata.get(key)
            if isinstance(value, dict):
                return value
        for section_key in ("teleop_control_mode", "control_filter"):
            section = metadata.get(section_key)
            if not isinstance(section, dict):
                continue
            value = section.get("raw_wrist_direct_control")
            if isinstance(value, dict):
                return value

    return {}


def _raw_wrist_valid_to_valid_jump_stats(
    frames: list[dict[str, Any]], *, threshold_m: float | None
) -> dict[str, Any]:
    """Detect unstable Quest/OpenXR right-wrist jumps in direct-control evidence.

    This is intentionally separate from `RETARGETING_JUMP`: the former checks
    retargeted action continuity, while this gate checks raw right-wrist stream
    continuity before the direct EEF target servo is considered training-safe.
    """

    values: list[float] = []
    events: list[dict[str, Any]] = []
    gate_state_counts: dict[str, int] = {}
    gate_reason_counts: dict[str, int] = {}

    for index, frame in enumerate(frames):
        payload = _raw_wrist_direct_payload(frame)
        if not payload:
            continue
        gate_state = payload.get("gate_state")
        if isinstance(gate_state, str) and gate_state:
            gate_state_counts[gate_state] = gate_state_counts.get(gate_state, 0) + 1
        gate_reason = payload.get("gate_reason")
        if isinstance(gate_reason, str) and gate_reason:
            gate_reason_counts[gate_reason] = gate_reason_counts.get(gate_reason, 0) + 1

        jump_m = None
        for key in ("valid_to_valid_jump_m", "raw_wrist_jump_m"):
            jump_m = _float_or_none(payload.get(key))
            if jump_m is not None:
                break
        if jump_m is None:
            continue
        values.append(jump_m)
        if threshold_m is not None and jump_m > threshold_m:
            events.append(
                {
                    "frame_index": _frame_sequence_id(frame, index),
                    "jump_m": jump_m,
                    "threshold_m": threshold_m,
                    "gate_state": gate_state,
                    "gate_reason": gate_reason,
                    "t": _float_or_none(frame.get("t")),
                }
            )

    max_m = max(values, default=0.0)
    mean_m = sum(values) / len(values) if values else 0.0
    return {
        "fail": bool(events),
        "evidence_available": bool(values),
        "threshold_m": threshold_m,
        "max_m": max_m,
        "mean_m": mean_m,
        "count": len(values),
        "count_over_threshold": len(events),
        "gate_state_counts": gate_state_counts,
        "gate_reason_counts": gate_reason_counts,
        "events": events[:SCENE_STATE_EVENT_LIMIT],
        "event_limit": SCENE_STATE_EVENT_LIMIT,
        "policy": "reject_training_candidate_on_raw_wrist_valid_to_valid_jump",
    }


def _task_state(frame: dict[str, Any]) -> dict[str, Any]:
    metadata = frame.get("metadata") or {}
    value = metadata.get("task_state")
    return value if isinstance(value, dict) else {}


def _latest_task_state(frames: list[dict[str, Any]]) -> dict[str, Any]:
    for frame in reversed(frames):
        state = _task_state(frame)
        if state:
            return state
    return {}


def _frame_sequence_id(frame: dict[str, Any], fallback: int) -> int:
    metadata = frame.get("metadata") or {}
    for source in (frame, metadata):
        for key in ("frame_index", "step", "frame", "index"):
            value = source.get(key)
            if isinstance(value, bool):
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return fallback


def _scene_vector(frame: dict[str, Any], key: str) -> list[float] | None:
    if key in {"end_effector_position", "object_position"}:
        return _vector_or_none(frame.get(key), min_length=3)
    return _vector_or_none(_task_state(frame).get(key), min_length=3)


def _scene_state_discontinuity(frames: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect hidden sim/task reset boundaries inside one recorded trajectory.

    Dynamic robot/object bodies may move quickly during valid teleoperation, so they
    are recorded as diagnostic events only. Static task targets (`hole_position`,
    `hole_target_position`) should not jump within a single insertion episode; a
    jump there marks the trajectory as unsafe for training eligibility.
    """

    tracked_fields = {
        "end_effector_position": (
            "dynamic_body",
            SCENE_STATE_DYNAMIC_JUMP_THRESHOLD_M,
        ),
        "object_position": ("dynamic_body", SCENE_STATE_DYNAMIC_JUMP_THRESHOLD_M),
        "peg_position": ("dynamic_body", SCENE_STATE_DYNAMIC_JUMP_THRESHOLD_M),
        "peg_tip_position": ("dynamic_body", SCENE_STATE_DYNAMIC_JUMP_THRESHOLD_M),
        "hole_position": (
            "static_task_target",
            SCENE_STATE_STATIC_TARGET_JUMP_THRESHOLD_M,
        ),
        "hole_target_position": (
            "static_task_target",
            SCENE_STATE_STATIC_TARGET_JUMP_THRESHOLD_M,
        ),
    }
    events: list[dict[str, Any]] = []
    static_target_frames: set[int] = set()
    dynamic_body_frames: set[int] = set()

    for index in range(1, len(frames)):
        previous = frames[index - 1]
        current = frames[index]
        frame_index = _frame_sequence_id(current, index)
        previous_frame_index = _frame_sequence_id(previous, index - 1)
        for field, (field_kind, threshold) in tracked_fields.items():
            previous_vector = _scene_vector(previous, field)
            current_vector = _scene_vector(current, field)
            if previous_vector is None or current_vector is None:
                continue
            jump_m = euclidean(previous_vector[:3], current_vector[:3])
            if jump_m <= threshold:
                continue
            event = {
                "field": field,
                "field_kind": field_kind,
                "frame_index": frame_index,
                "previous_frame_index": previous_frame_index,
                "jump_m": jump_m,
                "threshold_m": threshold,
                "phase_before": _frame_phase(previous),
                "phase_after": _frame_phase(current),
                "t_before": _float_or_none(previous.get("t")),
                "t_after": _float_or_none(current.get("t")),
            }
            events.append(event)
            if field_kind == "static_task_target":
                static_target_frames.add(frame_index)
            else:
                dynamic_body_frames.add(frame_index)

    return {
        "fail": bool(static_target_frames),
        "event_count": len(events),
        "frames": sorted(static_target_frames),
        "static_task_target_frames": sorted(static_target_frames),
        "dynamic_body_frames": sorted(dynamic_body_frames),
        "events": events[:SCENE_STATE_EVENT_LIMIT],
        "event_limit": SCENE_STATE_EVENT_LIMIT,
        "thresholds_m": {
            "dynamic_body": SCENE_STATE_DYNAMIC_JUMP_THRESHOLD_M,
            "static_task_target": SCENE_STATE_STATIC_TARGET_JUMP_THRESHOLD_M,
        },
        "policy": "reject_training_candidate_on_static_task_target_jump",
    }


def _latest_task_float(
    frames: list[dict[str, Any]], keys: tuple[str, ...]
) -> float | None:
    for frame in reversed(frames):
        state = _task_state(frame)
        for key in keys:
            value = _float_or_none(state.get(key))
            if value is not None:
                return value
    return None


def _insertion_distance_from_state(
    state: dict[str, Any],
) -> tuple[float | None, str, float | None]:
    lateral_distance = _float_or_none(state.get("peg_lateral_distance_to_target"))
    distance_3d = _float_or_none(state.get("peg_tip_distance_3d_to_target"))
    if distance_3d is None:
        distance_3d = _float_or_none(
            state.get(
                "peg_tip_distance_to_target",
                state.get("peg_tip_distance_to_hole_bottom"),
            )
        )
    if lateral_distance is not None:
        return lateral_distance, "lateral_projection", distance_3d
    return distance_3d, "legacy_3d", distance_3d


def _latest_insertion_distance(
    frames: list[dict[str, Any]],
) -> tuple[float | None, str, float | None]:
    for frame in reversed(frames):
        state = _task_state(frame)
        if not state:
            continue
        distance, metric, distance_3d = _insertion_distance_from_state(state)
        if distance is not None:
            return distance, metric, distance_3d
    return None, "unavailable", None


def _latest_task_bool(
    trajectory: dict[str, Any],
    frames: list[dict[str, Any]],
    keys: tuple[str, ...],
) -> bool | None:
    summary = trajectory.get("summary") or {}
    for key in keys:
        value = summary.get(key)
        if isinstance(value, bool):
            return value

    for frame in reversed(frames):
        state = _task_state(frame)
        for key in keys:
            value = state.get(key)
            if isinstance(value, bool):
                return value
    return None


def _is_peg_in_hole_task(
    task_config: dict[str, Any], success_criteria: dict[str, Any]
) -> bool:
    task_type = str(
        task_config.get("task_type") or success_criteria.get("task_type") or ""
    ).lower()
    if "peg" in task_type and ("hole" in task_type or "insert" in task_type):
        return True
    peg_specific_keys = {
        "peg_tip_distance_to_target_max",
        "peg_tip_distance_to_hole_bottom_max",
        "peg_axis_alignment_error_max_rad",
        "axis_alignment_error_max_rad",
        "insertion_depth_min",
    }
    return bool(
        peg_specific_keys.intersection(success_criteria.keys())
        or peg_specific_keys.intersection(task_config.keys())
    )


def _stable_inserted_steps(
    frames: list[dict[str, Any]],
    *,
    distance_max: float,
    alignment_max: float,
    depth_min: float,
) -> int:
    stable_steps = 0
    for frame in reversed(frames):
        state = _task_state(frame)
        distance, _, _ = _insertion_distance_from_state(state)
        alignment = _float_or_none(
            state.get(
                "axis_alignment_error_rad", state.get("peg_axis_alignment_error_rad")
            )
        )
        depth = _float_or_none(state.get("insertion_depth"))
        if distance is None or alignment is None or depth is None:
            break
        if (
            distance <= distance_max
            and alignment <= alignment_max
            and depth >= depth_min
        ):
            stable_steps += 1
            continue
        break
    return stable_steps


def _evaluate_peg_in_hole(
    task_config: dict[str, Any],
    success_criteria: dict[str, Any],
    trajectory: dict[str, Any],
    frames: list[dict[str, Any]],
    object_points: list[list[float]],
    ee_points: list[list[float]],
) -> EvaluationResult | None:
    """Evaluate MVP-1 insertion metrics when frame metadata.task_state is available."""

    if not _is_peg_in_hole_task(
        task_config, success_criteria
    ) or not _latest_task_state(frames):
        return None

    peg_tip_distance, peg_distance_metric, peg_tip_distance_3d = (
        _latest_insertion_distance(frames)
    )
    axis_alignment_error = _latest_task_float(
        frames,
        ("axis_alignment_error_rad", "peg_axis_alignment_error_rad"),
    )
    insertion_depth = _latest_task_float(frames, ("insertion_depth",))
    if (
        peg_tip_distance is None
        or axis_alignment_error is None
        or insertion_depth is None
    ):
        return _failure("INVALID_TRAJECTORY")

    distance_max = (
        _threshold(
            task_config,
            success_criteria,
            ("peg_tip_distance_to_target_max", "peg_tip_distance_to_hole_bottom_max"),
            default=0.015,
        )
        or 0.015
    )
    alignment_max = (
        _threshold(
            task_config,
            success_criteria,
            ("peg_axis_alignment_error_max_rad", "axis_alignment_error_max_rad"),
            default=0.25,
        )
        or 0.25
    )
    depth_min = (
        _threshold(
            task_config,
            success_criteria,
            ("insertion_depth_min",),
            default=0.010,
        )
        or 0.010
    )
    min_stable_steps = int(
        success_criteria.get(
            "min_stable_steps", task_config.get("min_stable_steps", 10)
        )
    )
    max_completion_time_sec = float(
        success_criteria.get(
            "max_completion_time_sec", task_config.get("max_completion_time_sec", 45.0)
        )
    )

    summary = trajectory.get("summary") or {}
    duration_sec = _duration(trajectory, frames)
    total_distance = path_length(ee_points)
    tracking_loss_rate = _tracking_loss_rate(frames)
    post_warmup_frames = _post_warmup_frames(trajectory, frames)
    tracking_loss_after_warmup = _tracking_loss_rate(post_warmup_frames)
    average_input_latency_ms, max_input_latency_ms = _latency_stats(post_warmup_frames)
    frame_interval_mean_ms, frame_interval_jitter_ms = _frame_interval_stats(
        post_warmup_frames
    )
    retargeting_jump_max, retargeting_jump_mean = _retargeting_jump_stats(
        post_warmup_frames
    )
    scene_state_discontinuity = _scene_state_discontinuity(frames)
    collision_count = int(summary.get("collision_count", 0))
    contact_sequence_valid = _latest_task_bool(
        trajectory,
        frames,
        ("contact_sequence_valid",),
    )
    object_drop_detected = bool(
        _latest_task_bool(
            trajectory,
            frames,
            ("object_drop_detected", "object_dropped"),
        )
    )

    stable_steps = _stable_inserted_steps(
        frames,
        distance_max=distance_max,
        alignment_max=alignment_max,
        depth_min=depth_min,
    )

    max_tracking_loss_after_warmup = _threshold(
        task_config,
        success_criteria,
        ("max_tracking_loss_after_warmup", "max_tracking_loss_rate"),
        default=0.3,
    )
    max_retargeting_jump = _threshold(
        task_config,
        success_criteria,
        ("max_retargeting_jump", "max_retargeting_jump_max"),
    )
    max_raw_wrist_valid_to_valid_jump_m = _threshold(
        task_config,
        success_criteria,
        ("max_raw_wrist_valid_to_valid_jump_m", "max_raw_wrist_jump_m"),
        default=RAW_WRIST_VALID_TO_VALID_JUMP_DEFAULT_THRESHOLD_M,
    )
    max_average_input_latency_ms = _threshold(
        task_config,
        success_criteria,
        ("max_average_input_latency_ms", "max_average_latency_ms"),
    )
    max_input_latency_threshold_ms = _threshold(
        task_config,
        success_criteria,
        ("max_input_latency_ms", "max_latency_ms"),
    )
    max_frame_interval_jitter_ms = _threshold(
        task_config,
        success_criteria,
        ("max_frame_interval_jitter_ms", "max_jitter_ms"),
    )
    raw_wrist_valid_to_valid_jump = _raw_wrist_valid_to_valid_jump_stats(
        post_warmup_frames,
        threshold_m=max_raw_wrist_valid_to_valid_jump_m,
    )

    distance_score = clamp01(1 - peg_tip_distance / max(distance_max, 1e-9))
    alignment_score = clamp01(1 - axis_alignment_error / max(alignment_max, 1e-9))
    insertion_depth_score = clamp01(insertion_depth / max(depth_min, 1e-9))
    stability_score = clamp01(stable_steps / max(min_stable_steps, 1))
    efficiency_score = clamp01(1 - duration_sec / max(max_completion_time_sec, 1e-9))
    smoothness_score = clamp01(1 - normalized_path_jitter(ee_points))
    task_completion_score = clamp01(
        0.35 * insertion_depth_score
        + 0.30 * distance_score
        + 0.20 * alignment_score
        + 0.15 * stability_score
    )
    score = clamp01(
        0.45 * task_completion_score
        + 0.20 * efficiency_score
        + 0.20 * smoothness_score
        + 0.15
        * (
            1.0
            if contact_sequence_valid is True
            else 0.5
            if contact_sequence_valid is None
            else 0.0
        )
    )

    failure_reason = None
    if (
        max_tracking_loss_after_warmup is not None
        and tracking_loss_after_warmup > max_tracking_loss_after_warmup
    ):
        failure_reason = "TRACKING_LOSS"
    elif (
        max_average_input_latency_ms is not None
        and average_input_latency_ms is not None
        and average_input_latency_ms > max_average_input_latency_ms
    ):
        failure_reason = "INPUT_LATENCY"
    elif (
        max_input_latency_threshold_ms is not None
        and max_input_latency_ms is not None
        and max_input_latency_ms > max_input_latency_threshold_ms
    ):
        failure_reason = "INPUT_LATENCY"
    elif (
        max_frame_interval_jitter_ms is not None
        and frame_interval_jitter_ms is not None
        and frame_interval_jitter_ms > max_frame_interval_jitter_ms
    ):
        failure_reason = "FRAME_JITTER"
    elif scene_state_discontinuity["fail"]:
        failure_reason = "SCENE_STATE_DISCONTINUITY"
    elif raw_wrist_valid_to_valid_jump["fail"]:
        failure_reason = "RAW_WRIST_JUMP"
    elif (
        max_retargeting_jump is not None and retargeting_jump_max > max_retargeting_jump
    ):
        failure_reason = "RETARGETING_JUMP"
    elif duration_sec > max_completion_time_sec:
        failure_reason = "TIMEOUT"
    elif object_drop_detected:
        failure_reason = "OBJECT_DROPPED"
    elif collision_count > int(success_criteria.get("max_collision_count", 999_999)):
        failure_reason = "EXCESSIVE_COLLISION"
    elif peg_tip_distance > distance_max:
        failure_reason = "TARGET_MISSED"
    elif axis_alignment_error > alignment_max:
        failure_reason = "ALIGNMENT_ERROR"
    elif insertion_depth < depth_min:
        failure_reason = "INSUFFICIENT_INSERTION_DEPTH"
    elif stable_steps < min_stable_steps:
        failure_reason = "UNSTABLE_FINAL_STATE"
    elif contact_sequence_valid is False:
        failure_reason = "BAD_CONTACT_SEQUENCE"

    success = failure_reason is None
    fraud_risk_score = clamp01(
        max(tracking_loss_rate, tracking_loss_after_warmup)
        + (0.2 if total_distance <= 1e-9 else 0.0)
    )
    contact_sequence_score = (
        1.0
        if contact_sequence_valid is True
        else 0.0
        if contact_sequence_valid is False
        else 0.5
    )
    interaction_quality_score = clamp01(
        1.0
        - min(tracking_loss_after_warmup, 1.0) * 0.35
        - min(retargeting_jump_max / max(max_retargeting_jump or 1.0, 1e-9), 1.0) * 0.25
        - min(
            collision_count
            / max(float(success_criteria.get("max_collision_count", 10)), 1.0),
            1.0,
        )
        * 0.25
        - (0.15 if object_drop_detected else 0.0)
    )
    physical_plausibility_score = clamp01(
        1.0
        - min(
            collision_count
            / max(float(success_criteria.get("max_collision_count", 10)), 1.0),
            1.0,
        )
        * 0.35
        - min(retargeting_jump_max / max(max_retargeting_jump or 1.0, 1e-9), 1.0) * 0.35
        - min(tracking_loss_after_warmup, 1.0) * 0.15
        - (0.15 if object_drop_detected else 0.0)
    )
    quality_score = clamp01(score * (1 - 0.5 * fraud_risk_score))
    evaluator_confidence = clamp01(
        quality_score * 0.45
        + task_completion_score * 0.25
        + physical_plausibility_score * 0.15
        + interaction_quality_score * 0.15
    )
    failure_mode = failure_reason or "SUCCESS"
    failure_category = failure_category_for_reason(failure_reason)

    return EvaluationResult(
        success=success,
        score=score,
        quality_score=quality_score,
        novelty_score=0.0,
        stability_score=stability_score,
        efficiency_score=efficiency_score,
        smoothness_score=smoothness_score,
        fraud_risk_score=fraud_risk_score,
        task_completion_score=task_completion_score,
        interaction_quality_score=interaction_quality_score,
        contact_sequence_score=contact_sequence_score,
        physical_plausibility_score=physical_plausibility_score,
        data_usability_score=None,
        evaluator_confidence=evaluator_confidence,
        failure_mode=failure_mode,
        failure_reason=failure_reason,
        failure_category=failure_category,
        metrics=add_evaluation_semantics(
            {
                "task_type": "peg_in_hole",
                "peg_tip_distance_to_target": peg_tip_distance,
                "peg_distance_metric": peg_distance_metric,
                "peg_lateral_distance_to_target": peg_tip_distance
                if peg_distance_metric == "lateral_projection"
                else None,
                "peg_tip_distance_3d_to_target": peg_tip_distance_3d,
                "axis_alignment_error_rad": axis_alignment_error,
                "insertion_depth": insertion_depth,
                "stable_final_steps": stable_steps,
                "completion_time_sec": duration_sec,
                "collision_count": collision_count,
                "contact_sequence_valid": contact_sequence_valid,
                "contact_sequence_source": "task_state_or_summary"
                if contact_sequence_valid is not None
                else "not_available",
                "object_drop_detected": object_drop_detected,
                "tracking_loss_rate": tracking_loss_rate,
                "tracking_loss_after_warmup": tracking_loss_after_warmup,
                "post_warmup_frame_count": len(post_warmup_frames),
                "retargeting_jump_max": retargeting_jump_max,
                "retargeting_jump_mean": retargeting_jump_mean,
                "raw_wrist_valid_to_valid_jump": raw_wrist_valid_to_valid_jump,
                "scene_state_discontinuity": scene_state_discontinuity,
                "average_input_latency_ms": average_input_latency_ms,
                "max_input_latency_ms": max_input_latency_ms,
                "frame_interval_mean_ms": frame_interval_mean_ms,
                "frame_interval_jitter_ms": frame_interval_jitter_ms,
                "distance_score": distance_score,
                "axis_alignment_score": alignment_score,
                "insertion_depth_score": insertion_depth_score,
                "task_completion_score": task_completion_score,
                "interaction_quality_score": interaction_quality_score,
                "contact_sequence_score": contact_sequence_score,
                "physical_plausibility_score": physical_plausibility_score,
                "evaluator_confidence": evaluator_confidence,
                "failure_mode": failure_mode,
            },
            trajectory,
            success=success,
            failure_reason=failure_reason,
            failure_category=failure_category,
            evaluator_confidence=evaluator_confidence,
        ),
    )


def _invalid_source(trajectory: dict[str, Any]) -> bool:
    source = trajectory.get("source") or {}
    return not REQUIRED_SOURCE_FIELDS.issubset(source.keys())


def evaluate_trajectory(
    task_config: dict[str, Any],
    success_criteria: dict[str, Any],
    trajectory: dict[str, Any],
) -> EvaluationResult:
    """Evaluate a trajectory using the spec #9 success rule and score formula."""

    frames = _frames(trajectory)
    if not frames:
        return _failure("NO_TRAJECTORY")
    if trajectory.get("schema_version") is None or _invalid_source(trajectory):
        return _failure("INVALID_TRAJECTORY")

    object_points = _positions(frames, "object_position")
    ee_points = _positions(frames, "end_effector_position")
    if not object_points or not ee_points:
        return _failure("PHYSICALLY_IMPLAUSIBLE")

    peg_result = _evaluate_peg_in_hole(
        task_config,
        success_criteria,
        trajectory,
        frames,
        object_points,
        ee_points,
    )
    if peg_result is not None:
        return peg_result

    summary = trajectory.get("summary") or {}
    target = (
        summary.get("target_position")
        or task_config.get("target_position")
        or task_config.get("goal_position")
    )
    if target is None:
        return _failure("INVALID_TRAJECTORY")
    target_position = [float(v) for v in target]

    distance_to_target_max = float(
        success_criteria.get(
            "distance_to_target_max", task_config.get("success_tolerance", 0.03)
        )
    )
    min_stable_steps = int(success_criteria.get("min_stable_steps", 20))
    max_completion_time_sec = float(
        success_criteria.get("max_completion_time_sec", 30.0)
    )

    final_distance = euclidean(object_points[-1], target_position)
    stable_steps = sum(
        1
        for point in object_points[-min_stable_steps:]
        if euclidean(point, target_position) <= distance_to_target_max
    )
    duration_sec = _duration(trajectory, frames)
    total_distance = path_length(ee_points)
    tracking_loss_rate = _tracking_loss_rate(frames)
    post_warmup_frames = _post_warmup_frames(trajectory, frames)
    tracking_loss_after_warmup = _tracking_loss_rate(post_warmup_frames)
    average_input_latency_ms, max_input_latency_ms = _latency_stats(post_warmup_frames)
    frame_interval_mean_ms, frame_interval_jitter_ms = _frame_interval_stats(
        post_warmup_frames
    )
    retargeting_jump_max, retargeting_jump_mean = _retargeting_jump_stats(
        post_warmup_frames
    )
    collision_count = int((trajectory.get("summary") or {}).get("collision_count", 0))
    bad_contact_sequence = bool(
        (trajectory.get("summary") or {}).get("bad_contact_sequence", False)
    )

    max_tracking_loss_after_warmup = _threshold(
        task_config,
        success_criteria,
        ("max_tracking_loss_after_warmup", "max_tracking_loss_rate"),
        default=0.3,
    )
    max_retargeting_jump = _threshold(
        task_config,
        success_criteria,
        ("max_retargeting_jump", "max_retargeting_jump_max"),
    )
    max_raw_wrist_valid_to_valid_jump_m = _threshold(
        task_config,
        success_criteria,
        ("max_raw_wrist_valid_to_valid_jump_m", "max_raw_wrist_jump_m"),
        default=RAW_WRIST_VALID_TO_VALID_JUMP_DEFAULT_THRESHOLD_M,
    )
    max_average_input_latency_ms = _threshold(
        task_config,
        success_criteria,
        ("max_average_input_latency_ms", "max_average_latency_ms"),
    )
    max_input_latency_threshold_ms = _threshold(
        task_config,
        success_criteria,
        ("max_input_latency_ms", "max_latency_ms"),
    )
    max_frame_interval_jitter_ms = _threshold(
        task_config,
        success_criteria,
        ("max_frame_interval_jitter_ms", "max_jitter_ms"),
    )
    raw_wrist_valid_to_valid_jump = _raw_wrist_valid_to_valid_jump_stats(
        post_warmup_frames,
        threshold_m=max_raw_wrist_valid_to_valid_jump_m,
    )

    distance_score = clamp01(1 - final_distance / max(distance_to_target_max, 1e-9))
    stability_score = clamp01(stable_steps / max(min_stable_steps, 1))
    efficiency_score = clamp01(1 - duration_sec / max(max_completion_time_sec, 1e-9))
    smoothness_score = clamp01(1 - normalized_path_jitter(ee_points))
    score = clamp01(
        0.4 * distance_score
        + 0.2 * stability_score
        + 0.2 * efficiency_score
        + 0.2 * smoothness_score
    )

    failure_reason = None
    if (
        max_tracking_loss_after_warmup is not None
        and tracking_loss_after_warmup > max_tracking_loss_after_warmup
    ):
        failure_reason = "TRACKING_LOSS"
    elif (
        max_average_input_latency_ms is not None
        and average_input_latency_ms is not None
        and average_input_latency_ms > max_average_input_latency_ms
    ):
        failure_reason = "INPUT_LATENCY"
    elif (
        max_input_latency_threshold_ms is not None
        and max_input_latency_ms is not None
        and max_input_latency_ms > max_input_latency_threshold_ms
    ):
        failure_reason = "INPUT_LATENCY"
    elif (
        max_frame_interval_jitter_ms is not None
        and frame_interval_jitter_ms is not None
        and frame_interval_jitter_ms > max_frame_interval_jitter_ms
    ):
        failure_reason = "FRAME_JITTER"
    elif raw_wrist_valid_to_valid_jump["fail"]:
        failure_reason = "RAW_WRIST_JUMP"
    elif (
        max_retargeting_jump is not None and retargeting_jump_max > max_retargeting_jump
    ):
        failure_reason = "RETARGETING_JUMP"
    elif duration_sec > max_completion_time_sec:
        failure_reason = "TIMEOUT"
    elif final_distance > distance_to_target_max:
        failure_reason = "TARGET_MISSED"
    elif stable_steps < min_stable_steps:
        failure_reason = "UNSTABLE_FINAL_STATE"
    elif collision_count > int(success_criteria.get("max_collision_count", 999_999)):
        failure_reason = "EXCESSIVE_COLLISION"
    elif bad_contact_sequence:
        failure_reason = "BAD_CONTACT_SEQUENCE"

    success = failure_reason is None
    fraud_risk_score = clamp01(
        max(tracking_loss_rate, tracking_loss_after_warmup)
        + (0.2 if total_distance <= 1e-9 else 0.0)
    )
    quality_score = clamp01(score * (1 - 0.5 * fraud_risk_score))
    task_completion_score = clamp01(0.7 * distance_score + 0.3 * stability_score)
    interaction_quality_score = clamp01(
        1.0
        - min(tracking_loss_after_warmup, 1.0) * 0.45
        - min(retargeting_jump_max / max(max_retargeting_jump or 1.0, 1e-9), 1.0) * 0.25
        - min(
            (
                collision_count
                / max(float(success_criteria.get("max_collision_count", 10)), 1.0)
            ),
            1.0,
        )
        * 0.3
    )
    contact_sequence_score = 0.0 if bad_contact_sequence else 0.5
    physical_plausibility_score = clamp01(
        1.0
        - min(
            collision_count
            / max(float(success_criteria.get("max_collision_count", 10)), 1.0),
            1.0,
        )
        * 0.4
        - min(retargeting_jump_max / max(max_retargeting_jump or 1.0, 1e-9), 1.0) * 0.4
        - min(tracking_loss_after_warmup, 1.0) * 0.2
    )
    evaluator_confidence = clamp01(
        quality_score * 0.5
        + physical_plausibility_score * 0.25
        + interaction_quality_score * 0.25
    )
    failure_mode = failure_reason or "SUCCESS"
    failure_category = failure_category_for_reason(failure_reason)

    return EvaluationResult(
        success=success,
        score=score,
        quality_score=quality_score,
        novelty_score=0.0,
        stability_score=stability_score,
        efficiency_score=efficiency_score,
        smoothness_score=smoothness_score,
        fraud_risk_score=fraud_risk_score,
        task_completion_score=task_completion_score,
        interaction_quality_score=interaction_quality_score,
        contact_sequence_score=contact_sequence_score,
        physical_plausibility_score=physical_plausibility_score,
        data_usability_score=None,
        evaluator_confidence=evaluator_confidence,
        failure_mode=failure_mode,
        failure_reason=failure_reason,
        failure_category=failure_category,
        metrics=add_evaluation_semantics(
            {
                "final_distance_to_target": final_distance,
                "completion_time_sec": duration_sec,
                "stable_steps": stable_steps,
                "total_distance": total_distance,
                "collision_count": collision_count,
                "tracking_loss_rate": tracking_loss_rate,
                "tracking_loss_after_warmup": tracking_loss_after_warmup,
                "post_warmup_frame_count": len(post_warmup_frames),
                "retargeting_jump_max": retargeting_jump_max,
                "retargeting_jump_mean": retargeting_jump_mean,
                "raw_wrist_valid_to_valid_jump": raw_wrist_valid_to_valid_jump,
                "average_input_latency_ms": average_input_latency_ms,
                "max_input_latency_ms": max_input_latency_ms,
                "frame_interval_mean_ms": frame_interval_mean_ms,
                "frame_interval_jitter_ms": frame_interval_jitter_ms,
                "distance_score": distance_score,
                "task_completion_score": task_completion_score,
                "interaction_quality_score": interaction_quality_score,
                "contact_sequence_score": contact_sequence_score,
                "contact_sequence_source": "summary.bad_contact_sequence"
                if bad_contact_sequence
                else "not_available",
                "physical_plausibility_score": physical_plausibility_score,
                "evaluator_confidence": evaluator_confidence,
                "failure_mode": failure_mode,
            },
            trajectory,
            success=success,
            failure_reason=failure_reason,
            failure_category=failure_category,
            evaluator_confidence=evaluator_confidence,
        ),
    )


def _failure(reason: str) -> EvaluationResult:
    failure_category = failure_category_for_reason(reason)
    metrics = {
        "task_completion_score": 0.0,
        "interaction_quality_score": 0.0,
        "contact_sequence_score": 0.0,
        "physical_plausibility_score": 0.0,
        "evaluator_confidence": 0.0,
        "failure_mode": reason,
    }
    return EvaluationResult(
        success=False,
        score=0.0,
        quality_score=0.0,
        novelty_score=0.0,
        stability_score=0.0,
        efficiency_score=0.0,
        smoothness_score=0.0,
        fraud_risk_score=1.0,
        task_completion_score=0.0,
        interaction_quality_score=0.0,
        contact_sequence_score=0.0,
        physical_plausibility_score=0.0,
        data_usability_score=None,
        evaluator_confidence=0.0,
        failure_mode=reason,
        failure_reason=reason,
        failure_category=failure_category,
        metrics=add_evaluation_semantics(
            metrics,
            {"frames": [], "summary": {}},
            success=False,
            failure_reason=reason,
            failure_category=failure_category,
            evaluator_confidence=0.0,
        ),
    )
