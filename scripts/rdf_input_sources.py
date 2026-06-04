#!/usr/bin/env python3
"""Source-agnostic teleop input sample contracts.

Gate 0 should judge input-source viability before a stream can become robot
action labels. This module keeps the boundary small: adapters normalize legacy
trajectory frame metadata into immutable wrist-pose samples without changing the
stored JSON shape.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Protocol


WRIST_POSE_SAMPLE_SCHEMA_VERSION = "rdf_wrist_pose_sample_v0.1.0"
INPUT_SIGNAL_STATE_SCHEMA_VERSION = "rdf_input_signal_state_v0.1.0"
INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION = "rdf_input_truth_classification_v0.1.0"
QUEST_OPENXR_SOURCE_ID = "quest_openxr_handtracking"
UNSUPPORTED_INPUT_SOURCE_ID = "unsupported_input_source"


@dataclass(frozen=True)
class InputTruthClassification:
    """Frame-local truth classification for input authority decisions."""

    schema_version: str
    truth_state: str
    primary_reason: str
    frame_reason_codes: list[str]
    sample_valid: bool
    tracking_valid: bool
    timestamp_state: str
    confidence_state: str
    position_truth_state: str
    action_hold_required: bool
    resume_block: bool
    recenter_block: bool
    allow_authority: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InputSignalState:
    """Frame-level input viability state separate from task/data curation."""

    schema_version: str
    source_id: str
    source_kind: str
    runtime: str
    device: str
    input_channel: str
    frame_index: int
    timestamp_sec: float
    timestamp_source: str
    input_latency_ms: float | None
    input_latency_source: str
    tracking_confidence: float | None
    tracking_confidence_source: str
    sample_valid: bool
    tracking_valid: bool
    control_safe: bool
    control_safety_flags: list[str]
    action_hold: bool
    hold_reason: str | None
    tracking_epoch_id: int | None
    tracking_epoch_state: str | None
    learning_label_eligible: bool
    learning_label_ineligible_reason: str | None
    quality_flags: list[str]
    input_truth_classification: dict[str, Any]
    input_truth_control_state: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WristPoseSample:
    """Normalized wrist/input sample used by input viability gates."""

    schema_version: str
    source_id: str
    source_kind: str
    runtime: str
    device: str
    input_channel: str
    frame_index: int
    timestamp_sec: float
    timestamp_source: str
    pose: list[float] | None
    position_xyz: list[float] | None
    tracked: bool
    frame_valid: bool
    sample_valid: bool
    input_latency_ms: float | None
    input_latency_source: str
    tracking_confidence: float | None
    tracking_confidence_source: str
    action_hold: bool
    hold_reason: str | None
    tracking_epoch_id: int | None
    tracking_epoch_state: str | None
    anchor_fallback: bool
    quality_flags: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def input_signal_state(self) -> InputSignalState:
        tracking_valid = bool(self.tracked and self.frame_valid)
        control_safety_flags = []
        if not self.sample_valid:
            control_safety_flags.append("invalid_input_sample")
        if self.action_hold:
            control_safety_flags.append("action_hold")

        classification = classify_input_truth(self)
        classification_dict = classification.as_dict()
        input_truth_control_state = merge_input_truth_soft_blocks(
            {
                "action_hold": self.action_hold,
                "hold_reason": self.hold_reason,
                "resume_block": False,
                "recenter_block": False,
                "allow_authority": False,
            },
            classification_dict,
        )
        effective_action_hold = input_truth_control_state.get("action_hold") is True
        effective_hold_reason = self.hold_reason
        if effective_action_hold and effective_hold_reason is None:
            effective_hold_reason = str(
                input_truth_control_state.get("hold_reason")
                or classification.primary_reason
            )

        if effective_action_hold and not self.action_hold:
            control_safety_flags.append("input_truth_action_hold")

        control_safe = bool(self.sample_valid and not effective_action_hold)
        ineligible_reason = None
        if not self.sample_valid:
            ineligible_reason = "invalid_input_sample"
        elif effective_action_hold:
            ineligible_reason = f"hold:{effective_hold_reason or 'action_hold'}"
        elif not control_safe:
            ineligible_reason = "input_not_control_safe"

        return InputSignalState(
            schema_version=INPUT_SIGNAL_STATE_SCHEMA_VERSION,
            source_id=self.source_id,
            source_kind=self.source_kind,
            runtime=self.runtime,
            device=self.device,
            input_channel=self.input_channel,
            frame_index=self.frame_index,
            timestamp_sec=self.timestamp_sec,
            timestamp_source=self.timestamp_source,
            input_latency_ms=self.input_latency_ms,
            input_latency_source=self.input_latency_source,
            tracking_confidence=self.tracking_confidence,
            tracking_confidence_source=self.tracking_confidence_source,
            sample_valid=self.sample_valid,
            tracking_valid=tracking_valid,
            control_safe=control_safe,
            control_safety_flags=control_safety_flags,
            action_hold=effective_action_hold,
            hold_reason=effective_hold_reason,
            tracking_epoch_id=self.tracking_epoch_id,
            tracking_epoch_state=self.tracking_epoch_state,
            learning_label_eligible=control_safe,
            learning_label_ineligible_reason=ineligible_reason,
            quality_flags=list(self.quality_flags),
            input_truth_classification=classification_dict,
            input_truth_control_state=input_truth_control_state,
        )


class InputSourceAdapter(Protocol):
    """Boundary for future XR/HMD/controller/wrist input sources."""

    source_id: str

    def sample_from_frame(
        self, frame: dict[str, Any], *, fallback_index: int = 0
    ) -> WristPoseSample:
        """Normalize one trajectory frame into a common wrist pose sample."""
        ...


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _pose7(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 7:
        return None
    pose: list[float] = []
    for item in value[:7]:
        parsed = _finite_float(item)
        if parsed is None:
            return None
        pose.append(parsed)
    return pose


def _frame_time(frame: dict[str, Any], fallback_index: int) -> float:
    parsed = _finite_float(frame.get("t"))
    return parsed if parsed is not None else float(fallback_index)


def _frame_time_source(frame: dict[str, Any]) -> str:
    return "frame_t" if _finite_float(frame.get("t")) is not None else "fallback_index"


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _quality_reason_code(flag: str) -> str:
    return str(flag).upper()


def _hold_reason_code(reason: str | None) -> str | None:
    if not reason:
        return None
    return str(reason).upper()


def _primary_reason(reason_codes: list[str]) -> str:
    priority = (
        "MISSING_RIGHT_WRIST_POSE",
        "ANCHOR_FALLBACK_POSE",
        "UNTRACKED_RIGHT_HAND",
        "INVALID_XR_FRAME",
        "UNSUPPORTED_INPUT_SOURCE",
        "UNKNOWN_INPUT_SOURCE",
        "RAW_WRIST_JUMP_REJECT",
        "RAW_WRIST_JUMP_WARN",
        "RAW_WRIST_SPIKE_REACQUIRE_PENDING",
        "RAW_WRIST_SPIKE_REACQUIRED",
        "ACTION_HOLD",
        "TIMESTAMP_FALLBACK_INDEX",
        "TRACKING_CONFIDENCE_NOT_AVAILABLE",
    )
    for candidate in priority:
        if candidate in reason_codes:
            return candidate
    return reason_codes[0] if reason_codes else "INPUT_TRUTH_OK"


def classify_input_truth(
    sample: WristPoseSample,
    *,
    previous_valid_position_xyz: list[float] | None = None,
    raw_wrist_jump_warn_m: float = 0.10,
    raw_wrist_jump_reject_m: float = 0.15,
) -> InputTruthClassification:
    """Classify input truth without granting any downstream authority."""

    reason_codes: list[str] = []
    for flag in sample.quality_flags:
        reason_codes.append(_quality_reason_code(flag))

    position_truth_state = "valid"
    if sample.position_xyz is None:
        position_truth_state = "missing"
    if sample.anchor_fallback:
        position_truth_state = "anchor_fallback"
        reason_codes.append("ANCHOR_FALLBACK_POSE")

    timestamp_state = "provided"
    if sample.timestamp_source == "fallback_index":
        timestamp_state = "fallback"
        reason_codes.append("TIMESTAMP_FALLBACK_INDEX")

    confidence_state = "provided"
    if sample.tracking_confidence is None:
        confidence_state = "not_available"
        reason_codes.append("TRACKING_CONFIDENCE_NOT_AVAILABLE")

    hold_code = _hold_reason_code(sample.hold_reason)
    if hold_code is not None:
        reason_codes.append(hold_code)
    elif sample.action_hold:
        reason_codes.append("ACTION_HOLD")

    if (
        sample.sample_valid
        and sample.position_xyz is not None
        and previous_valid_position_xyz is not None
    ):
        jump_m = math.sqrt(
            sum(
                (float(left) - float(right)) ** 2
                for left, right in zip(
                    sample.position_xyz,
                    previous_valid_position_xyz,
                    strict=False,
                )
            )
        )
        if jump_m > raw_wrist_jump_reject_m:
            reason_codes.append("RAW_WRIST_JUMP_REJECT")
        elif jump_m > raw_wrist_jump_warn_m:
            reason_codes.append("RAW_WRIST_JUMP_WARN")

    reason_codes = list(dict.fromkeys(reason_codes))
    tracking_valid = bool(sample.tracked and sample.frame_valid)
    invalid_reasons = {
        "MISSING_RIGHT_WRIST_POSE",
        "ANCHOR_FALLBACK_POSE",
        "UNTRACKED_RIGHT_HAND",
        "INVALID_XR_FRAME",
        "UNSUPPORTED_INPUT_SOURCE",
        "UNKNOWN_INPUT_SOURCE",
    }
    unsafe_reasons = {
        "RAW_WRIST_JUMP_REJECT",
        "RAW_WRIST_JUMP_WARN",
        "RAW_WRIST_SPIKE_REACQUIRE_PENDING",
        "ACTION_HOLD",
    }
    if any(reason in invalid_reasons for reason in reason_codes):
        truth_state = "invalid"
    elif any(reason in unsafe_reasons for reason in reason_codes):
        truth_state = "unsafe"
    else:
        truth_state = "valid"

    primary_reason = _primary_reason(reason_codes)
    action_hold_required = truth_state in {"invalid", "unsafe"}
    resume_block = truth_state in {"invalid", "unsafe"}
    recenter_block = truth_state in {"invalid", "unsafe"}

    return InputTruthClassification(
        schema_version=INPUT_TRUTH_CLASSIFICATION_SCHEMA_VERSION,
        truth_state=truth_state,
        primary_reason=primary_reason,
        frame_reason_codes=reason_codes,
        sample_valid=sample.sample_valid,
        tracking_valid=tracking_valid,
        timestamp_state=timestamp_state,
        confidence_state=confidence_state,
        position_truth_state=position_truth_state,
        action_hold_required=action_hold_required,
        resume_block=resume_block,
        recenter_block=recenter_block,
        allow_authority=truth_state == "valid" and not reason_codes,
    )


def merge_input_truth_soft_blocks(
    control_state: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any]:
    """Merge unsafe input truth only as additional blocks, never grants."""

    blocked = dict(control_state)
    for grant_key in (
        "resume_allowed",
        "recenter_allowed",
        "gate0_pass",
        "gate_a_collection_allowed",
    ):
        blocked.pop(grant_key, None)

    primary_reason = str(classification.get("primary_reason") or "INPUT_TRUTH_BLOCK")
    if classification.get("action_hold_required") is True:
        blocked["action_hold"] = True
        blocked.setdefault("hold_reason", primary_reason)
    if classification.get("resume_block") is True:
        if blocked.get("resume_block") is not True:
            blocked["resume_block_reason"] = primary_reason
        blocked["resume_block"] = True
    if classification.get("recenter_block") is True:
        if blocked.get("recenter_block") is not True:
            blocked["recenter_block_reason"] = primary_reason
        blocked["recenter_block"] = True

    if classification.get("allow_authority") is False:
        blocked["allow_authority"] = False
    else:
        blocked["allow_authority"] = bool(blocked.get("allow_authority", False))
    return blocked


class QuestOpenXrHandtrackingAdapter:
    """Adapter for the existing Quest/OpenXR right-wrist trajectory metadata."""

    source_id = QUEST_OPENXR_SOURCE_ID

    def __init__(
        self,
        *,
        runtime: str = "steamvr_openxr",
        device: str = "quest3",
        input_channel: str = "right_wrist",
    ) -> None:
        self.runtime = runtime
        self.device = device
        self.input_channel = input_channel

    def sample_from_frame(
        self, frame: dict[str, Any], *, fallback_index: int = 0
    ) -> WristPoseSample:
        metadata = frame.get("metadata") or {}
        raw_xr = metadata.get("raw_xr") or {}
        pose = _pose7(raw_xr.get("right_wrist_pose")) or _pose7(
            metadata.get("right_wrist_pose")
        )
        tracked = bool(metadata.get("right_hand_tracked"))
        frame_valid = bool(metadata.get("xr_frame_valid"))
        quality_flags: list[str] = []
        if pose is None:
            quality_flags.append("missing_right_wrist_pose")
        if not tracked:
            quality_flags.append("untracked_right_hand")
        if not frame_valid:
            quality_flags.append("invalid_xr_frame")

        input_latency_ms = _finite_float(metadata.get("input_latency_ms"))
        input_latency_source = (
            "metadata.input_latency_ms"
            if input_latency_ms is not None
            else "not_available"
        )
        tracking_confidence = _finite_float(metadata.get("tracking_confidence"))
        tracking_confidence_source = (
            "metadata.tracking_confidence"
            if tracking_confidence is not None
            else "not_available"
        )
        hold_reason = metadata.get("hold_reason")
        if hold_reason is not None:
            hold_reason = str(hold_reason)
        anchor_fallback = metadata.get("right_wrist_anchor_fallback") is True

        return WristPoseSample(
            schema_version=WRIST_POSE_SAMPLE_SCHEMA_VERSION,
            source_id=self.source_id,
            source_kind="handtracking",
            runtime=self.runtime,
            device=self.device,
            input_channel=self.input_channel,
            frame_index=int(frame.get("step", fallback_index)),
            timestamp_sec=_frame_time(frame, fallback_index),
            timestamp_source=_frame_time_source(frame),
            pose=pose,
            position_xyz=pose[:3] if pose is not None else None,
            tracked=tracked,
            frame_valid=frame_valid,
            sample_valid=bool(pose is not None and tracked and frame_valid),
            input_latency_ms=input_latency_ms,
            input_latency_source=input_latency_source,
            tracking_confidence=tracking_confidence,
            tracking_confidence_source=tracking_confidence_source,
            action_hold=metadata.get("action_hold") is True,
            hold_reason=hold_reason,
            tracking_epoch_id=_optional_int(metadata.get("tracking_epoch_id")),
            tracking_epoch_state=metadata.get("tracking_epoch_state"),
            anchor_fallback=anchor_fallback,
            quality_flags=quality_flags,
        )


class UnsupportedInputSourceAdapter:
    """Fail-closed sentinel for missing or unimplemented input sources."""

    source_id = UNSUPPORTED_INPUT_SOURCE_ID

    def __init__(self, *, reason: str, source: dict[str, Any] | None = None) -> None:
        self.reason = reason
        self.source = source or {}

    def sample_from_frame(
        self, frame: dict[str, Any], *, fallback_index: int = 0
    ) -> WristPoseSample:
        metadata = frame.get("metadata") or {}
        hold_reason = metadata.get("hold_reason")
        if hold_reason is not None:
            hold_reason = str(hold_reason)
        input_latency_ms = _finite_float(metadata.get("input_latency_ms"))

        return WristPoseSample(
            schema_version=WRIST_POSE_SAMPLE_SCHEMA_VERSION,
            source_id=self.source_id,
            source_kind="unsupported",
            runtime=str(self.source.get("runtime") or "unknown"),
            device=str(self.source.get("input_device") or "unknown"),
            input_channel="unknown",
            frame_index=int(frame.get("step", fallback_index)),
            timestamp_sec=_frame_time(frame, fallback_index),
            timestamp_source=_frame_time_source(frame),
            pose=None,
            position_xyz=None,
            tracked=False,
            frame_valid=False,
            sample_valid=False,
            input_latency_ms=input_latency_ms,
            input_latency_source=(
                "metadata.input_latency_ms"
                if input_latency_ms is not None
                else "not_available"
            ),
            tracking_confidence=None,
            tracking_confidence_source="not_available",
            action_hold=metadata.get("action_hold") is True,
            hold_reason=hold_reason,
            tracking_epoch_id=_optional_int(metadata.get("tracking_epoch_id")),
            tracking_epoch_state=metadata.get("tracking_epoch_state"),
            anchor_fallback=False,
            quality_flags=[self.reason],
        )


def quest_openxr_wrist_sample_from_frame(
    frame: dict[str, Any], *, fallback_index: int = 0
) -> WristPoseSample:
    """Compatibility helper for scripts that do not need adapter instances."""

    return QuestOpenXrHandtrackingAdapter().sample_from_frame(
        frame, fallback_index=fallback_index
    )


def adapter_for_trajectory_source(source: dict[str, Any]) -> InputSourceAdapter | None:
    """Select an implemented input adapter from legacy trajectory source metadata."""

    input_device = str(source.get("input_device") or "").lower()
    runtime = str(source.get("runtime") or "").lower()
    if input_device == "quest3_handtracking" and runtime == "steamvr_openxr":
        return QuestOpenXrHandtrackingAdapter(runtime=runtime, device="quest3")
    return None
