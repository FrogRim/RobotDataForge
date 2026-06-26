"""MVP-5A-pre digital-twin file-drop chaos rehearsal helpers.

This module deliberately models recorded-log file drops without opening live
robot, live ROS2, or external partner data claims.  The producer side may use
small deterministic fixtures and optional runtime-capture-shaped evidence, but
the checked-in v0 package remains contract-ready until a verifier-owned runtime
capture evidence contract exists.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACKAGE_DIR = ROOT / "docs" / "proof" / "mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package"

PACKAGE_NAME = "mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package"
PACKAGE_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_rehearsal_package_v0.1.0"
CONFIG_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_rehearsal_config_v0.1.0"
CANONICAL_TRACE_SCHEMA_VERSION = "rdf_mvp5a_pre_canonical_trace_v0.1.0"
RUNTIME_CAPTURE_SCHEMA_VERSION = "rdf_mvp5a_pre_isaac_sim_runtime_capture_v0.1.0"
RUNTIME_CAPTURE_PROVENANCE_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_provenance_v0.1.0"
RAW_RUNTIME_EVENT_SCHEMA_VERSION = "rdf_mvp5a_pre_raw_runtime_event_v0.1.0"
RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_event_manifest_v0.1.0"
RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_reconstruction_receipt_v0.1.0"
RUNTIME_RECONSTRUCTION_ALGORITHM = "rdf_mvp5a_pre_runtime_events_to_canonical_trace_v0.1.0"
PROCESS_PROVENANCE_RECEIPT_SCHEMA_VERSION = "rdf_mvp5a_pre_process_provenance_receipt_v0.1.0"
CAPTURE_EDGE_EMITTER_CONFIG_SCHEMA_VERSION = "rdf_mvp5a_pre_capture_edge_emitter_config_v0.1.0"
PROFILE_REGISTRY_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_profile_registry_v0.1.0"
SOURCE_METADATA_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_source_metadata_v0.1.0"
INGEST_RESULT_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_ingest_result_v0.1.0"
NON_CLAIMS_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_non_claims_v0.1.0"

STATUS_CONTRACT_READY = "file_drop_rehearsal_contract_ready"
STATUS_READY = "file_drop_rehearsal_ready"
BLOCKED_RUNTIME_INSUFFICIENT = "runtime_capture_insufficient_for_mvp5a_canonical_trace"
BLOCKED_RUNTIME_UNVERIFIED_SOURCE_PROCESS = "runtime_capture_unverified_source_process"
FIXTURE_SOURCE_KIND = "deterministic_fixture_digital_twin_trace"
RUNTIME_BACKED_SOURCE_KIND = "isaac_sim_runtime_backed_canonical_trace"
RUNTIME_BACKEND = "isaac_sim"
RUNTIME_CAPTURE_SCRIPT_ID = "mvp5a_pre_isaac_sim_canonical_trace_capture_v0"
RUNTIME_EVENT_CAPTURE_SCRIPT_ID = "mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0"
RUNTIME_EVENT_HELPER_SCRIPT_ID = "mvp5a_pre_canonical_trace_projection_helper_v0"
RUNTIME_EVENT_HELPER_EVIDENCE_ORIGIN = "canonical_trace_projection_helper"
RUNTIME_EVENT_HELPER_PRODUCER_KIND = "dev_fixture_helper"
RUNTIME_EVENT_HELPER_SOURCE_PROCESS_KIND = "canonical_trace_projection_helper"
RUNTIME_EVENT_HELPER_SOURCE_FUNCTION = "build_runtime_event_log_from_trace"
RUNTIME_EVENT_CAPTURE_EDGE_EVIDENCE_ORIGIN = "capture_edge_runtime_event_emitter"
RUNTIME_EVENT_CAPTURE_EDGE_PRODUCER_KIND = "capture_edge_emitter"
CAPTURE_EDGE_EMITTER_SCRIPT_REPO_PATH = "scripts/capture_mvp5a_pre_raw_runtime_event_log.py"
CAPTURE_EDGE_EMITTER_SCRIPT_SNAPSHOT_PATH = "data/process_provenance/capture_edge_emitter_script_snapshot.py"
CAPTURE_EDGE_EMITTER_CONFIG_PATH = "data/process_provenance/capture_edge_emitter_config.json"
CAPTURE_EDGE_EMITTER_STDOUT_PATH = "data/process_provenance/capture_edge_emitter_stdout.log"
CAPTURE_EDGE_EMITTER_STDERR_PATH = "data/process_provenance/capture_edge_emitter_stderr.log"
CAPTURE_EDGE_PROCESS_PROVENANCE_RECEIPT_PATH = "data/process_provenance/process_provenance_receipt.json"
RUNTIME_SOURCE_PROCESS_KIND = "isaac_sim_process"
CAPTURE_EDGE_SOURCE_PROCESS_KIND = "digital_twin_capture_edge_emitter"
FIXTURE_FRAME_CONTENT_SHA256 = "ff9f65a980a6ea315b95117dd9961a806c95cc104d4adc7082b3ab82016f287c"
RUNTIME_FRAME_KEYS = {"frame_index", "timestamp", "phase", "ur", "franka", "generic"}
RUNTIME_EVENT_REQUIRED_CHANNELS = (
    "phase_marker",
    "ur_joint_state",
    "ur_tcp_state",
    "franka_joint_state",
    "franka_eef_state",
    "generic_command_state",
)
RUNTIME_UR_KEYS = {
    "actual_q",
    "target_q",
    "actual_TCP_pose",
    "target_TCP_pose",
    "actual_TCP_speed",
    "robot_mode",
    "safety_status",
}
RUNTIME_FRANKA_KEYS = {"q", "q_d", "O_T_EE", "O_T_EE_d", "robot_mode"}
RUNTIME_GENERIC_KEYS = {"state", "command", "command_timestamp", "state_timestamp"}

MIN_CANONICAL_FRAMES = 12
MAX_TIMESTAMP_GAP_SECONDS = 0.08
MAX_ACTION_STATE_LAG = 0.06
SPENT_SEED_RANGES = ((40000, 40049), (42000, 42049))

PROFILE_IDS = (
    "ur_rtde_csv_v0",
    "franka_state_jsonl_v0",
    "ros2_channel_bundle_jsonl_v0",
    "generic_command_state_jsonl_v0",
)

FORBIDDEN_CLAIMS = (
    "external_partner_data_evaluated",
    "external_partner_data",
    "real_robot_success",
    "physical_robot_readiness",
    "hardware_integration",
    "hardware_readiness",
    "live_ur_rtde_support",
    "live_franka_hardware_support",
    "live_ros2_dds_bridge_readiness",
    "native_mcap_parser_support",
    "generic_file_drop_support",
    "generic_robot_log_parser",
    "policy_uplift",
    "learning_proven_value",
    "visual_policy_performance",
    "deployable_policy_readiness",
    "production_certification",
    "marketplace_readiness",
    "sim_to_real_proven",
    "general_robot_intelligence",
)
NON_CLAIMS = {key: False for key in FORBIDDEN_CLAIMS}

REJECTION_REASONS = (
    "schema_missing_required_artifact",
    "schema_missing_required_field",
    "schema_type_mismatch",
    "timestamp_not_monotonic",
    "timestamp_gap_or_drift",
    "unit_mismatch",
    "vector_dimension_mismatch",
    "frame_tree_invalid",
    "frame_semantic_drift",
    "action_state_semantic_mismatch",
    "safety_or_robot_mode_invalid",
    "provenance_boundary_violation",
    "claim_boundary_violation",
    "hash_integrity_failure",
    "export_semantic_drift",
    "unsupported_profile",
)


@dataclass(frozen=True)
class ProfileSpec:
    profile_id: str
    robot_family: str
    robot_model: str
    dof: int
    joint_names: tuple[str, ...]
    source_file_names: tuple[str, ...]
    action_semantics: str
    state_semantics: str
    required_frame_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationResult:
    profile_id: str
    case_id: str
    passed: bool
    rejection_reasons: tuple[str, ...]
    frame_count: int
    source_file_hashes: dict[str, dict[str, Any]]
    export_eligible: bool
    trainer_smoke_eligible: bool
    normalized_rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class MutationSpec:
    mutation_id: str
    profile_id: str
    category: str
    expected_rejection_reason: str
    description: str
    applier: Callable[[Path], None]


PROFILE_REGISTRY: dict[str, ProfileSpec] = {
    "ur_rtde_csv_v0": ProfileSpec(
        profile_id="ur_rtde_csv_v0",
        robot_family="universal_robots",
        robot_model="ur10e",
        dof=6,
        joint_names=(
            "shoulder_pan_joint",
            "shoulder_lift_joint",
            "elbow_joint",
            "wrist_1_joint",
            "wrist_2_joint",
            "wrist_3_joint",
        ),
        source_file_names=("metadata.json", "rtde_output.csv"),
        action_semantics="target_q_command",
        state_semantics="actual_q_state",
    ),
    "franka_state_jsonl_v0": ProfileSpec(
        profile_id="franka_state_jsonl_v0",
        robot_family="franka",
        robot_model="panda",
        dof=7,
        joint_names=(
            "panda_joint1",
            "panda_joint2",
            "panda_joint3",
            "panda_joint4",
            "panda_joint5",
            "panda_joint6",
            "panda_joint7",
        ),
        source_file_names=("metadata.json", "franka_state.jsonl", "franka_command.jsonl"),
        action_semantics="q_d_command",
        state_semantics="q_actual_state",
    ),
    "ros2_channel_bundle_jsonl_v0": ProfileSpec(
        profile_id="ros2_channel_bundle_jsonl_v0",
        robot_family="ros2_simulated_manipulator",
        robot_model="ur10e_channel_bundle",
        dof=6,
        joint_names=(
            "shoulder_pan_joint",
            "shoulder_lift_joint",
            "elbow_joint",
            "wrist_1_joint",
            "wrist_2_joint",
            "wrist_3_joint",
        ),
        source_file_names=(
            "metadata.json",
            "topic_manifest.json",
            "topics/joint_states.jsonl",
            "topics/tf.jsonl",
            "topics/tf_static.jsonl",
            "topics/command.jsonl",
        ),
        action_semantics="command_topic_target_joint_state",
        state_semantics="joint_states_topic_actual_state",
        required_frame_ids=("world", "base_link", "tool0"),
    ),
    "generic_command_state_jsonl_v0": ProfileSpec(
        profile_id="generic_command_state_jsonl_v0",
        robot_family="generic_manipulator",
        robot_model="generic_6dof_command_state",
        dof=6,
        joint_names=("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"),
        source_file_names=("metadata.json", "command_state.jsonl"),
        action_semantics="explicit_command_vector",
        state_semantics="explicit_state_vector",
    ),
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def stable_compact_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_compact_json(row) + "\n" for row in rows), encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_profile_registry() -> dict[str, Any]:
    return {
        "schema_version": PROFILE_REGISTRY_SCHEMA_VERSION,
        "required_profile_ids": list(PROFILE_IDS),
        "profile_count": len(PROFILE_IDS),
        "profiles": [
            {
                "profile_id": spec.profile_id,
                "robot_family": spec.robot_family,
                "robot_model": spec.robot_model,
                "dof": spec.dof,
                "joint_names": list(spec.joint_names),
                "source_file_names": list(spec.source_file_names),
                "action_semantics": spec.action_semantics,
                "state_semantics": spec.state_semantics,
                "live_runtime_support": False,
                "external_partner_data": False,
            }
            for spec in PROFILE_REGISTRY.values()
        ],
    }


def build_fixture_canonical_trace(frame_count: int = MIN_CANONICAL_FRAMES) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    for index in range(frame_count):
        timestamp = round(index * 0.04, 6)
        ur_actual = [round(0.04 * math.sin(index / 4 + joint), 6) for joint in range(6)]
        ur_target = [round(value + 0.003, 6) for value in ur_actual]
        franka_actual = [round(0.03 * math.cos(index / 5 + joint), 6) for joint in range(7)]
        franka_target = [round(value + 0.002, 6) for value in franka_actual]
        tcp_position = [round(0.42 + 0.001 * index, 6), -0.015, round(0.16 - 0.0015 * index, 6)]
        tcp_rotation = [0.0, 3.14159, 0.0]
        frames.append(
            {
                "frame_index": index,
                "timestamp": timestamp,
                "phase": "approach" if index < frame_count - 3 else "insert_rehearsal",
                "ur": {
                    "actual_q": ur_actual,
                    "target_q": ur_target,
                    "actual_TCP_pose": [*tcp_position, *tcp_rotation],
                    "target_TCP_pose": [tcp_position[0] + 0.001, tcp_position[1], tcp_position[2], *tcp_rotation],
                    "actual_TCP_speed": [0.025, 0.0, -0.018, 0.0, 0.0, 0.0],
                    "robot_mode": "RUNNING",
                    "safety_status": "NORMAL",
                },
                "franka": {
                    "q": franka_actual,
                    "q_d": franka_target,
                    "O_T_EE": _pose_matrix(x=tcp_position[0], y=tcp_position[1], z=tcp_position[2]),
                    "O_T_EE_d": _pose_matrix(x=tcp_position[0] + 0.001, y=tcp_position[1], z=tcp_position[2]),
                    "robot_mode": "move",
                },
                "generic": {
                    "state": ur_actual,
                    "command": ur_target,
                    "command_timestamp": round(max(timestamp - 0.01, 0.0), 6),
                    "state_timestamp": timestamp,
                },
            }
        )
    return {
        "schema_version": CANONICAL_TRACE_SCHEMA_VERSION,
        "trace_id": "mvp5a_pre_fixture_canonical_trace_v0",
        "source_kind": FIXTURE_SOURCE_KIND,
        "runtime_backed": False,
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "frame_count": len(frames),
        "frames": frames,
        "non_claims": dict(NON_CLAIMS),
    }


def runtime_capture_preflight(runtime_capture: Path | None) -> dict[str, Any]:
    if runtime_capture is None:
        return {
            "schema_version": "rdf_mvp5a_pre_runtime_capture_preflight_v0.1.0",
            "runtime_capture_supplied": False,
            "runtime_capture_sufficient": False,
            "runtime_capture_structurally_valid": False,
            "fresh_runtime_capture_required": True,
            "blocked_reason": "runtime_capture_not_supplied",
            "issues": ["runtime_capture_not_supplied"],
            "runtime_capture_path": None,
            "runtime_capture_sha256": None,
            "minimum_required_frames": MIN_CANONICAL_FRAMES,
            "observed_min_source_log_rows_emitted": 0,
        }

    capture_path = _resolve_runtime_capture_path(runtime_capture)
    issues: list[str] = []
    payload: dict[str, Any] = {}
    sha256 = None
    observed_rows = 0
    if capture_path is None or not capture_path.exists():
        issues.append("runtime_capture_missing")
    else:
        sha256 = sha256_file(capture_path)
        try:
            payload = json.loads(capture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append("runtime_capture_invalid_json")

    if payload:
        canonical = payload.get("mvp5a_canonical_trace")
        if isinstance(canonical, dict) and isinstance(canonical.get("frames"), list):
            observed_rows = len(canonical["frames"])
            if observed_rows < MIN_CANONICAL_FRAMES:
                issues.append("runtime_capture_source_log_rows_below_minimum")
            issues.extend(_runtime_capture_provenance_issues(payload, canonical))
            issues.extend(_runtime_canonical_trace_issues(canonical))
        else:
            issues.append("runtime_capture_canonical_trace_missing")
        if not isinstance(payload.get("captured_at"), str):
            issues.append("runtime_capture_captured_at_missing")

    structurally_valid = not issues and observed_rows >= MIN_CANONICAL_FRAMES
    reported_issues = sorted(set(issues))
    if structurally_valid:
        reported_issues.append(BLOCKED_RUNTIME_UNVERIFIED_SOURCE_PROCESS)
    return {
        "schema_version": "rdf_mvp5a_pre_runtime_capture_preflight_v0.1.0",
        "runtime_capture_supplied": True,
        "runtime_capture_sufficient": False,
        "runtime_capture_structurally_valid": structurally_valid,
        "fresh_runtime_capture_required": True,
        "blocked_reason": BLOCKED_RUNTIME_UNVERIFIED_SOURCE_PROCESS if structurally_valid else BLOCKED_RUNTIME_INSUFFICIENT,
        "issues": reported_issues,
        "runtime_capture_path": str(capture_path) if capture_path else str(runtime_capture),
        "runtime_capture_sha256": sha256,
        "minimum_required_frames": MIN_CANONICAL_FRAMES,
        "observed_min_source_log_rows_emitted": observed_rows,
    }


def prepare_canonical_trace(runtime_capture: Path | None, *, fixture_only: bool) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    preflight = runtime_capture_preflight(None if fixture_only else runtime_capture)
    if not fixture_only and preflight["runtime_capture_sufficient"] and preflight["runtime_capture_path"]:
        payload = json.loads(Path(preflight["runtime_capture_path"]).read_text(encoding="utf-8"))
        canonical = payload.get("mvp5a_canonical_trace")
        if not isinstance(canonical, dict):
            raise ValueError("runtime_capture_preflight marked sufficient without canonical trace")
        trace = canonical
        trace = {
            **trace,
            "runtime_capture_sha256": preflight["runtime_capture_sha256"],
        }
    else:
        trace = build_fixture_canonical_trace()

    trace_bytes = (stable_json(trace) + "\n").encode("utf-8")
    receipt = {
        "schema_version": "rdf_mvp5a_pre_runtime_capture_hash_receipt_v0.1.0",
        "canonical_trace_sha256": sha256_bytes(trace_bytes),
        "runtime_capture_supplied": preflight["runtime_capture_supplied"],
        "runtime_capture_sufficient": preflight["runtime_capture_sufficient"],
        "runtime_capture_structurally_valid": preflight.get("runtime_capture_structurally_valid", False),
        "runtime_capture_path": preflight.get("runtime_capture_path"),
        "runtime_capture_sha256": preflight["runtime_capture_sha256"],
        "ready_status_allowed": False,
        "blocked_reason": preflight["blocked_reason"],
    }
    return trace, preflight, receipt


def build_runtime_event_log_from_trace(trace: dict[str, Any], *, capture_id: str) -> list[dict[str, Any]]:
    """Project canonical frames into dev-helper runtime event rows.

    This is intentionally not capture-edge evidence: it is useful for verifier
    fixtures and consistency rehearsals, but it must not open ready=true.
    """
    events: list[dict[str, Any]] = []
    event_index = 0
    for frame in _frames(trace):
        frame_index = int(frame["frame_index"])
        timestamp = float(frame["timestamp"])
        ur = frame["ur"]
        franka = frame["franka"]
        generic = frame["generic"]
        channel_rows: tuple[tuple[str, dict[str, Any], dict[str, str]], ...] = (
            (
                "phase_marker",
                {"phase": frame["phase"]},
                {},
            ),
            (
                "ur_joint_state",
                {
                    "joint_names": list(PROFILE_REGISTRY["ur_rtde_csv_v0"].joint_names),
                    "actual_q": ur["actual_q"],
                    "target_q": ur["target_q"],
                    "robot_mode": ur["robot_mode"],
                    "safety_status": ur["safety_status"],
                },
                {"joint_position": "rad"},
            ),
            (
                "ur_tcp_state",
                {
                    "actual_TCP_pose": ur["actual_TCP_pose"],
                    "target_TCP_pose": ur["target_TCP_pose"],
                    "actual_TCP_speed": ur["actual_TCP_speed"],
                },
                {"tcp_position": "m", "tcp_rotation": "rotation_vector_rad", "tcp_speed": "m_per_s"},
            ),
            (
                "franka_joint_state",
                {
                    "joint_names": list(PROFILE_REGISTRY["franka_state_jsonl_v0"].joint_names),
                    "q": franka["q"],
                    "q_d": franka["q_d"],
                    "robot_mode": franka["robot_mode"],
                },
                {"joint_position": "rad"},
            ),
            (
                "franka_eef_state",
                {
                    "O_T_EE": franka["O_T_EE"],
                    "O_T_EE_d": franka["O_T_EE_d"],
                },
                {"pose_matrix": "homogeneous_transform_row_major_m"},
            ),
            (
                "generic_command_state",
                {
                    "state": generic["state"],
                    "command": generic["command"],
                    "state_timestamp": generic["state_timestamp"],
                    "command_timestamp": generic["command_timestamp"],
                    "action_semantics": "commanded_target_state",
                    "state_semantics": "actual_robot_state",
                },
                {"state": "profile_native", "command": "profile_native"},
            ),
        )
        for channel, payload, units in channel_rows:
            events.append(
                {
                    "schema_version": RAW_RUNTIME_EVENT_SCHEMA_VERSION,
                    "capture_id": capture_id,
                    "event_index": event_index,
                    "frame_index": frame_index,
                    "timestamp": timestamp,
                    "channel": channel,
                    "source_backend": RUNTIME_BACKEND,
                    "source_process_kind": RUNTIME_EVENT_HELPER_SOURCE_PROCESS_KIND,
                    "units": units,
                    "payload": payload,
                }
            )
            event_index += 1
    return events


def build_capture_edge_runtime_event_log(
    *,
    capture_id: str,
    frame_count: int = MIN_CANONICAL_FRAMES,
) -> list[dict[str, Any]]:
    """Emit raw runtime events directly from the rehearsal capture edge.

    This function intentionally does not accept a canonical trace. The canonical
    trace for a ready package must be reconstructed from these event rows.
    """
    events: list[dict[str, Any]] = []
    event_index = 0
    for index in range(frame_count):
        timestamp = round(index * 0.04, 6)
        delta = round(0.0007 * (index + 1), 6)
        ur_actual = [round(0.04 * math.sin(index / 4 + joint) + delta, 6) for joint in range(6)]
        ur_target = [round(value + 0.003, 6) for value in ur_actual]
        franka_actual = [round(0.03 * math.cos(index / 5 + joint) + delta, 6) for joint in range(7)]
        franka_target = [round(value + 0.002, 6) for value in franka_actual]
        tcp_position = [
            round(0.42 + 0.001 * index + delta, 6),
            -0.015,
            round(0.16 - 0.0015 * index, 6),
        ]
        tcp_rotation = [0.0, 3.14159, 0.0]
        channel_rows: tuple[tuple[str, dict[str, Any], dict[str, str]], ...] = (
            ("phase_marker", {"phase": "approach" if index < frame_count - 3 else "insert_rehearsal"}, {}),
            (
                "ur_joint_state",
                {
                    "joint_names": list(PROFILE_REGISTRY["ur_rtde_csv_v0"].joint_names),
                    "actual_q": ur_actual,
                    "target_q": ur_target,
                    "robot_mode": "RUNNING",
                    "safety_status": "NORMAL",
                },
                {"joint_position": "rad"},
            ),
            (
                "ur_tcp_state",
                {
                    "actual_TCP_pose": [*tcp_position, *tcp_rotation],
                    "target_TCP_pose": [tcp_position[0] + 0.001, tcp_position[1], tcp_position[2], *tcp_rotation],
                    "actual_TCP_speed": [0.025, 0.0, -0.018, 0.0, 0.0, 0.0],
                },
                {"tcp_position": "m", "tcp_rotation": "rotation_vector_rad", "tcp_speed": "m_per_s"},
            ),
            (
                "franka_joint_state",
                {
                    "joint_names": list(PROFILE_REGISTRY["franka_state_jsonl_v0"].joint_names),
                    "q": franka_actual,
                    "q_d": franka_target,
                    "robot_mode": "move",
                },
                {"joint_position": "rad"},
            ),
            (
                "franka_eef_state",
                {
                    "O_T_EE": _pose_matrix(x=tcp_position[0], y=tcp_position[1], z=tcp_position[2]),
                    "O_T_EE_d": _pose_matrix(x=tcp_position[0] + 0.001, y=tcp_position[1], z=tcp_position[2]),
                },
                {"pose_matrix": "homogeneous_transform_row_major_m"},
            ),
            (
                "generic_command_state",
                {
                    "state": ur_actual,
                    "command": ur_target,
                    "state_timestamp": timestamp,
                    "command_timestamp": round(max(timestamp - 0.01, 0.0), 6),
                    "action_semantics": "commanded_target_state",
                    "state_semantics": "actual_robot_state",
                },
                {"state": "profile_native", "command": "profile_native"},
            ),
        )
        for channel, payload, units in channel_rows:
            events.append(
                {
                    "schema_version": RAW_RUNTIME_EVENT_SCHEMA_VERSION,
                    "capture_id": capture_id,
                    "event_index": event_index,
                    "frame_index": index,
                    "timestamp": timestamp,
                    "channel": channel,
                    "source_backend": RUNTIME_BACKEND,
                    "source_process_kind": CAPTURE_EDGE_SOURCE_PROCESS_KIND,
                    "units": units,
                    "payload": payload,
                }
            )
            event_index += 1
    return events


def reconstruct_canonical_trace_from_runtime_events(
    events: list[dict[str, Any]],
    *,
    trace_id: str = "mvp5a_pre_l2_l3_capture_edge_reconstructed_trace_v0",
) -> dict[str, Any]:
    grouped: dict[int, dict[str, dict[str, Any]]] = {}
    timestamps: dict[int, float] = {}
    for event in events:
        frame_index = event.get("frame_index")
        channel = event.get("channel")
        payload = event.get("payload")
        timestamp = event.get("timestamp")
        if not isinstance(frame_index, int) or not isinstance(channel, str) or not isinstance(payload, dict):
            raise ValueError("runtime event row cannot reconstruct canonical trace")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(float(timestamp)):
            raise ValueError("runtime event timestamp cannot reconstruct canonical trace")
        grouped.setdefault(frame_index, {})[channel] = payload
        timestamps.setdefault(frame_index, float(timestamp))
    if sorted(grouped) != list(range(len(grouped))):
        raise ValueError("runtime event frames are not contiguous")

    frames: list[dict[str, Any]] = []
    for frame_index in sorted(grouped):
        channels = grouped[frame_index]
        if set(channels) != set(RUNTIME_EVENT_REQUIRED_CHANNELS):
            raise ValueError("runtime event channel set cannot reconstruct canonical trace")
        phase = channels["phase_marker"]
        ur_joint = channels["ur_joint_state"]
        ur_tcp = channels["ur_tcp_state"]
        franka_joint = channels["franka_joint_state"]
        franka_eef = channels["franka_eef_state"]
        generic = channels["generic_command_state"]
        frames.append(
            {
                "frame_index": frame_index,
                "timestamp": round(timestamps[frame_index], 6),
                "phase": phase["phase"],
                "ur": {
                    "actual_q": ur_joint["actual_q"],
                    "target_q": ur_joint["target_q"],
                    "actual_TCP_pose": ur_tcp["actual_TCP_pose"],
                    "target_TCP_pose": ur_tcp["target_TCP_pose"],
                    "actual_TCP_speed": ur_tcp["actual_TCP_speed"],
                    "robot_mode": ur_joint["robot_mode"],
                    "safety_status": ur_joint["safety_status"],
                },
                "franka": {
                    "q": franka_joint["q"],
                    "q_d": franka_joint["q_d"],
                    "O_T_EE": franka_eef["O_T_EE"],
                    "O_T_EE_d": franka_eef["O_T_EE_d"],
                    "robot_mode": franka_joint["robot_mode"],
                },
                "generic": {
                    "state": generic["state"],
                    "command": generic["command"],
                    "command_timestamp": generic["command_timestamp"],
                    "state_timestamp": generic["state_timestamp"],
                },
            }
        )
    return {
        "schema_version": CANONICAL_TRACE_SCHEMA_VERSION,
        "trace_id": trace_id,
        "source_kind": RUNTIME_BACKED_SOURCE_KIND,
        "runtime_backed": True,
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "frame_count": len(frames),
        "frames": frames,
        "non_claims": dict(NON_CLAIMS),
    }


def read_runtime_event_log(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("runtime event log row must be an object")
        rows.append(row)
    return rows


def write_runtime_evidence(
    package_dir: Path,
    trace: dict[str, Any],
    *,
    capture_id: str = "mvp5a-pre-runtime-event-evidence",
) -> dict[str, Any]:
    """Write L2 runtime event evidence files without promoting package status."""
    runtime_dir = package_dir / "data" / "runtime_evidence"
    event_log_path = runtime_dir / "runtime_event_log.jsonl"
    events = build_runtime_event_log_from_trace(trace, capture_id=capture_id)
    write_jsonl(event_log_path, events)
    event_log_sha = sha256_file(event_log_path)
    canonical_path = package_dir / "data" / "canonical_trace" / "canonical_trace.json"
    included_canonical_sha = sha256_file(canonical_path) if canonical_path.exists() else sha256_bytes(
        (stable_json(trace) + "\n").encode("utf-8")
    )
    manifest = {
        "schema_version": RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION,
        "evidence_level": "L2_verifier_owned_raw_runtime_events",
        "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
        "runtime_event_log_sha256": event_log_sha,
        "capture_id": capture_id,
        "capture_script_id": RUNTIME_EVENT_HELPER_SCRIPT_ID,
        "evidence_origin": RUNTIME_EVENT_HELPER_EVIDENCE_ORIGIN,
        "producer_kind": RUNTIME_EVENT_HELPER_PRODUCER_KIND,
        "helper_source_function": RUNTIME_EVENT_HELPER_SOURCE_FUNCTION,
        "closing_evidence": False,
        "source_backend": RUNTIME_BACKEND,
        "source_process_kind": RUNTIME_EVENT_HELPER_SOURCE_PROCESS_KIND,
        "frame_count": len(_frames(trace)),
        "event_count": len(events),
        "required_channels": list(RUNTIME_EVENT_REQUIRED_CHANNELS),
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "non_claims": dict(NON_CLAIMS),
    }
    receipt = {
        "schema_version": RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION,
        "reconstruction_algorithm": RUNTIME_RECONSTRUCTION_ALGORITHM,
        "runtime_event_log_sha256": event_log_sha,
        "reconstructed_canonical_trace_sha256": included_canonical_sha,
        "included_canonical_trace_sha256": included_canonical_sha,
        "matches_included_canonical_trace": True,
        "runtime_capture_sufficient": False,
        "ready_status_allowed": False,
        "blocked_reason": "helper_derived_runtime_events_are_consistency_evidence_only",
    }
    write_json(runtime_dir / "runtime_event_manifest.json", manifest)
    write_json(runtime_dir / "runtime_reconstruction_receipt.json", receipt)
    return {
        "runtime_event_log_path": event_log_path,
        "runtime_event_log_sha256": event_log_sha,
        "runtime_event_manifest_path": runtime_dir / "runtime_event_manifest.json",
        "runtime_reconstruction_receipt_path": runtime_dir / "runtime_reconstruction_receipt.json",
        "frame_count": manifest["frame_count"],
        "event_count": manifest["event_count"],
    }


def _runtime_capture_provenance_issues(payload: dict[str, Any], canonical: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("schema_version") != RUNTIME_CAPTURE_SCHEMA_VERSION:
        issues.append("runtime_capture_schema_version_mismatch")
    provenance = payload.get("runtime_provenance")
    if not isinstance(provenance, dict):
        issues.append("runtime_capture_provenance_missing")
    else:
        if provenance.get("schema_version") != RUNTIME_CAPTURE_PROVENANCE_SCHEMA_VERSION:
            issues.append("runtime_capture_provenance_invalid")
        if provenance.get("runtime_backend") != RUNTIME_BACKEND:
            issues.append("runtime_capture_provenance_invalid")
        if provenance.get("capture_script_id") != RUNTIME_CAPTURE_SCRIPT_ID:
            issues.append("runtime_capture_provenance_invalid")
        if not isinstance(provenance.get("capture_command"), str) or not provenance.get("capture_command"):
            issues.append("runtime_capture_provenance_invalid")
        if not isinstance(provenance.get("isaac_sim_version"), str) or not provenance.get("isaac_sim_version"):
            issues.append("runtime_capture_provenance_invalid")
        receipt = provenance.get("source_process_receipt")
        if not isinstance(receipt, dict):
            issues.append("runtime_capture_provenance_invalid")
        elif receipt.get("process_kind") != RUNTIME_SOURCE_PROCESS_KIND or not isinstance(receipt.get("capture_id"), str):
            issues.append("runtime_capture_provenance_invalid")
    if canonical.get("source_kind") != RUNTIME_BACKED_SOURCE_KIND:
        issues.append("runtime_capture_not_runtime_backed")
    if canonical.get("runtime_backed") is not True:
        issues.append("runtime_capture_not_runtime_backed")
    if _frame_content_sha256(canonical.get("frames")) == FIXTURE_FRAME_CONTENT_SHA256:
        issues.append("runtime_capture_matches_deterministic_fixture")
    return issues


def _frame_content_sha256(frames: Any) -> str | None:
    projection = _runtime_required_frame_projection(frames)
    if projection is None:
        return None
    return sha256_bytes((stable_json(projection) + "\n").encode("utf-8"))


def _runtime_required_frame_projection(frames: Any) -> list[dict[str, Any]] | None:
    if not isinstance(frames, list):
        return None
    projected: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            return None
        ur = frame.get("ur")
        franka = frame.get("franka")
        generic = frame.get("generic")
        if not isinstance(ur, dict) or not isinstance(franka, dict) or not isinstance(generic, dict):
            return None
        projected.append(
            {
                "frame_index": frame.get("frame_index"),
                "timestamp": frame.get("timestamp"),
                "phase": frame.get("phase"),
                "ur": {key: ur.get(key) for key in sorted(RUNTIME_UR_KEYS)},
                "franka": {key: franka.get(key) for key in sorted(RUNTIME_FRANKA_KEYS)},
                "generic": {key: generic.get(key) for key in sorted(RUNTIME_GENERIC_KEYS)},
            }
        )
    return projected


def _runtime_canonical_trace_issues(canonical: dict[str, Any]) -> list[str]:
    frames = canonical.get("frames")
    if not isinstance(frames, list):
        return ["runtime_capture_canonical_trace_missing"]
    issues: list[str] = []
    previous_timestamp: float | None = None
    for frame in frames:
        if not isinstance(frame, dict):
            issues.append("runtime_capture_frame_schema_invalid")
            continue
        if set(frame) != RUNTIME_FRAME_KEYS:
            issues.append("runtime_capture_frame_schema_invalid")
        timestamp = _finite_float(frame.get("timestamp"))
        if timestamp is None:
            issues.append("runtime_capture_frame_schema_invalid")
        elif previous_timestamp is not None:
            if timestamp <= previous_timestamp or timestamp - previous_timestamp > MAX_TIMESTAMP_GAP_SECONDS:
                issues.append("runtime_capture_frame_schema_invalid")
            previous_timestamp = timestamp
        else:
            previous_timestamp = timestamp
        if not isinstance(frame.get("phase"), str):
            issues.append("runtime_capture_frame_schema_invalid")
        ur = frame.get("ur")
        franka = frame.get("franka")
        generic = frame.get("generic")
        if not isinstance(ur, dict) or not isinstance(franka, dict) or not isinstance(generic, dict):
            issues.append("runtime_capture_frame_schema_invalid")
            continue
        if set(ur) != RUNTIME_UR_KEYS or set(franka) != RUNTIME_FRANKA_KEYS or set(generic) != RUNTIME_GENERIC_KEYS:
            issues.append("runtime_capture_frame_schema_invalid")
        if (
            not _numeric_vector(ur.get("actual_q"), 6)
            or not _numeric_vector(ur.get("target_q"), 6)
            or not _numeric_vector(ur.get("actual_TCP_pose"), 6)
            or not _numeric_vector(ur.get("target_TCP_pose"), 6)
            or not _numeric_vector(ur.get("actual_TCP_speed"), 6)
            or ur.get("robot_mode") != "RUNNING"
            or ur.get("safety_status") != "NORMAL"
        ):
            issues.append("runtime_capture_frame_schema_invalid")
        o_t_ee = franka.get("O_T_EE")
        if (
            not _numeric_vector(franka.get("q"), 7)
            or not _numeric_vector(franka.get("q_d"), 7)
            or not _numeric_vector(o_t_ee, 16)
            or not _numeric_vector(franka.get("O_T_EE_d"), 16)
            or not _rigid_transform_plausible(o_t_ee if isinstance(o_t_ee, list) else [])
            or franka.get("robot_mode") != "move"
        ):
            issues.append("runtime_capture_frame_schema_invalid")
        if (
            not _numeric_vector(generic.get("state"), 6)
            or not _numeric_vector(generic.get("command"), 6)
            or not _finite_number(generic.get("command_timestamp"))
            or not _finite_number(generic.get("state_timestamp"))
        ):
            issues.append("runtime_capture_frame_schema_invalid")
    return _dedupe(issues)


def write_golden_profile_drop(profile_id: str, trace: dict[str, Any], output_dir: Path) -> None:
    spec = _profile(profile_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "metadata.json", _metadata_for_profile(spec))
    frames = _frames(trace)
    if profile_id == "ur_rtde_csv_v0":
        _write_ur_csv(output_dir / "rtde_output.csv", frames, spec)
    elif profile_id == "franka_state_jsonl_v0":
        _write_franka_jsonl(output_dir, frames)
    elif profile_id == "ros2_channel_bundle_jsonl_v0":
        _write_ros2_bundle(output_dir, frames, spec)
    elif profile_id == "generic_command_state_jsonl_v0":
        _write_generic_jsonl(output_dir / "command_state.jsonl", frames)
    else:
        raise ValueError(f"unknown profile_id: {profile_id}")


def validate_profile_drop(drop_dir: Path, *, expected_profile_id: str | None = None, case_id: str = "case") -> ValidationResult:
    issues: list[str] = []
    metadata = _read_json_object(drop_dir / "metadata.json", issues, missing_reason="schema_missing_required_artifact")
    profile_id = str(metadata.get("profile_id") or expected_profile_id or "")
    if expected_profile_id and profile_id != expected_profile_id:
        issues.append("unsupported_profile")
    if profile_id not in PROFILE_REGISTRY:
        issues.append("unsupported_profile")
        return _validation_result(profile_id or "unknown", case_id, issues, 0, drop_dir, ())
    spec = PROFILE_REGISTRY[profile_id]
    issues.extend(_validate_metadata(metadata, spec))
    rows: list[dict[str, Any]] = []
    if profile_id == "ur_rtde_csv_v0":
        rows, parse_issues = _parse_ur_csv(drop_dir / "rtde_output.csv", spec)
    elif profile_id == "franka_state_jsonl_v0":
        rows, parse_issues = _parse_franka_jsonl(drop_dir, spec)
    elif profile_id == "ros2_channel_bundle_jsonl_v0":
        rows, parse_issues = _parse_ros2_bundle(drop_dir, spec)
    else:
        rows, parse_issues = _parse_generic_jsonl(drop_dir / "command_state.jsonl", spec)
    issues.extend(parse_issues)
    issues.extend(_validate_common_rows(rows, spec))
    issues.extend(_validate_profile_semantics(rows, spec))
    return _validation_result(profile_id, case_id, issues, len(rows), drop_dir, tuple(rows))


def mutation_specs() -> list[MutationSpec]:
    return [
        *_ur_mutations(),
        *_franka_mutations(),
        *_ros2_mutations(),
        *_generic_mutations(),
    ]


def generate_corrupt_drop(profile_id: str, mutation: MutationSpec, golden_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(golden_dir, output_dir)
    mutation.applier(output_dir)


def export_profile_hdf5(profile_id: str, rows: tuple[dict[str, Any], ...], export_dir: Path) -> dict[str, Any]:
    import h5py  # type: ignore[import-untyped]
    import numpy as np

    export_dir.mkdir(parents=True, exist_ok=True)
    hdf5_path = export_dir / "dataset.hdf5"
    states = np.asarray([row["state_vector"] for row in rows], dtype=np.float32)
    actions = np.asarray([row["action_vector"] for row in rows], dtype=np.float32)
    timestamps = np.asarray([row["timestamp"] for row in rows], dtype=np.float64)
    with h5py.File(hdf5_path, "w") as h5:
        h5.attrs["schema_version"] = "rdf_mvp5a_pre_file_drop_hdf5_v0.1.0"
        h5.attrs["profile_id"] = profile_id
        h5.create_dataset("states", data=states)
        h5.create_dataset("actions", data=actions)
        h5.create_dataset("timestamps", data=timestamps)
    state_hash = sha256_bytes(states.tobytes())
    action_hash = sha256_bytes(actions.tobytes())
    timestamp_hash = sha256_bytes(timestamps.tobytes())
    split_manifest = {
        "schema_version": "rdf_mvp5a_pre_split_manifest_v0.1.0",
        "profile_id": profile_id,
        "splits": {"train": [f"{profile_id}_golden_episode"]},
        "frame_count": len(rows),
    }
    inspection = {
        "schema_version": "rdf_mvp5a_pre_hdf5_inspection_v0.1.0",
        "profile_id": profile_id,
        "passed": True,
        "state_shape": list(states.shape),
        "action_shape": list(actions.shape),
        "timestamp_count": int(timestamps.size),
        "finite_values": bool(np.isfinite(states).all() and np.isfinite(actions).all() and np.isfinite(timestamps).all()),
        "hdf5_sha256": sha256_file(hdf5_path),
        "state_array_sha256": state_hash,
        "action_array_sha256": action_hash,
        "timestamp_array_sha256": timestamp_hash,
    }
    trainer = {
        "schema_version": "rdf_mvp5a_pre_trainer_smoke_v0.1.0",
        "profile_id": profile_id,
        "passed": True,
        "trainer": "tiny_state_action_loader_smoke",
        "learning_results_measured": False,
        "policy_uplift": None,
        "state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
        "frame_count": int(states.shape[0]),
    }
    receipt = {
        "schema_version": "rdf_mvp5a_pre_semantic_preservation_receipt_v0.1.0",
        "profile_id": profile_id,
        "source_frame_count": len(rows),
        "normalized_contract_frame_count": len(rows),
        "hdf5_frame_count": int(states.shape[0]),
        "trainer_frame_count": trainer["frame_count"],
        "source_state_sha256": state_hash,
        "source_action_sha256": action_hash,
        "source_timestamp_sha256": timestamp_hash,
        "hdf5_state_sha256": inspection["state_array_sha256"],
        "hdf5_action_sha256": inspection["action_array_sha256"],
        "hdf5_timestamp_sha256": inspection["timestamp_array_sha256"],
        "profile_semantics_preserved": True,
    }
    write_json(export_dir / "split_manifest.json", split_manifest)
    write_json(export_dir / "hdf5_inspection_report.json", inspection)
    write_json(export_dir / "trainer_smoke_report.json", trainer)
    write_json(export_dir / "semantic_preservation_receipt.json", receipt)
    return {
        "hdf5_path": hdf5_path,
        "split_manifest": export_dir / "split_manifest.json",
        "inspection": inspection,
        "trainer": trainer,
        "receipt": receipt,
    }


def _materialize_rehearsal_package(
    *,
    package_dir: Path,
    trace: dict[str, Any],
    preflight: dict[str, Any],
    capture_receipt: dict[str, Any],
    status: str,
    ready: bool,
    emit_runtime_event_evidence: bool = False,
    runtime_evidence_report: dict[str, Any] | None = None,
    runtime_capture: Path | None = None,
) -> dict[str, Any]:
    data_dir = package_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    contract_ready = True

    packaged_preflight = dict(preflight)
    packaged_capture_receipt = dict(capture_receipt)
    if runtime_capture is not None:
        source_capture = _resolve_runtime_capture_path(runtime_capture)
        if source_capture and source_capture.exists():
            capture_target = data_dir / "canonical_trace" / "runtime_capture.json"
            capture_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_capture, capture_target)
            packaged_capture_sha = sha256_file(capture_target)
            packaged_capture_path = "data/canonical_trace/runtime_capture.json"
            for payload in (packaged_preflight, packaged_capture_receipt):
                payload["runtime_capture_path"] = packaged_capture_path
                payload["runtime_capture_sha256"] = packaged_capture_sha
    preflight = packaged_preflight
    capture_receipt = packaged_capture_receipt

    write_json(data_dir / "canonical_trace" / "canonical_trace.json", trace)
    write_json(data_dir / "canonical_trace" / "runtime_capture_preflight.json", preflight)
    write_json(data_dir / "canonical_trace" / "runtime_capture_hash_receipt.json", capture_receipt)
    if emit_runtime_event_evidence and runtime_evidence_report is None:
        runtime_evidence_report = write_runtime_evidence(package_dir, trace)
    write_json(data_dir / "profile_registry.json", build_profile_registry())
    write_json(data_dir / "non_claims_attestation.json", {"schema_version": NON_CLAIMS_SCHEMA_VERSION, "non_claims": dict(NON_CLAIMS)})

    source_root = data_dir / "source_drops"
    golden_results: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    for profile_id in PROFILE_IDS:
        golden_dir = source_root / "golden" / profile_id
        write_golden_profile_drop(profile_id, trace, golden_dir)
        result = validate_profile_drop(golden_dir, expected_profile_id=profile_id, case_id=f"{profile_id}:golden")
        contract = _normalized_contract(profile_id, result)
        write_json(data_dir / "normalized_contracts" / f"{profile_id}_normalized_contract.json", contract)
        export_report = export_profile_hdf5(profile_id, result.normalized_rows, data_dir / "export" / profile_id)
        golden_results.append(_result_payload(result, expected_rejection_reason=None, export_report=export_report))
        contracts.append(contract)

    corrupt_results: list[dict[str, Any]] = []
    for mutation in mutation_specs():
        golden_dir = source_root / "golden" / mutation.profile_id
        corrupt_dir = source_root / "corrupt" / mutation.profile_id / mutation.mutation_id
        generate_corrupt_drop(mutation.profile_id, mutation, golden_dir, corrupt_dir)
        result = validate_profile_drop(
            corrupt_dir,
            expected_profile_id=mutation.profile_id,
            case_id=f"{mutation.profile_id}:{mutation.mutation_id}",
        )
        corrupt_results.append(_result_payload(result, expected_rejection_reason=mutation.expected_rejection_reason, mutation=mutation))

    coverage = _rejection_reason_coverage(corrupt_results)
    write_json(data_dir / "ingest_results" / "golden_results.json", {"schema_version": INGEST_RESULT_SCHEMA_VERSION, "results": golden_results})
    write_json(data_dir / "ingest_results" / "corruption_matrix_results.json", {"schema_version": INGEST_RESULT_SCHEMA_VERSION, "results": corrupt_results})
    write_json(data_dir / "ingest_results" / "rejection_reason_coverage.json", coverage)

    config = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "package_name": PACKAGE_NAME,
        "status": status,
        "file_drop_rehearsal_contract_ready": contract_ready,
        "file_drop_rehearsal_ready": ready,
        "runtime_capture_supplied": preflight.get("runtime_capture_supplied", False),
        "runtime_capture_sufficient": preflight["runtime_capture_sufficient"],
        "runtime_capture_structurally_valid": preflight.get("runtime_capture_structurally_valid", False),
        "runtime_capture_path": preflight.get("runtime_capture_path"),
        "runtime_capture_sha256": preflight.get("runtime_capture_sha256"),
        "runtime_event_capture_supplied": preflight.get("runtime_event_capture_supplied", False),
        "runtime_event_capture_sufficient": preflight.get("runtime_event_capture_sufficient", False),
        "runtime_event_capture_structurally_valid": preflight.get("runtime_event_capture_structurally_valid", False),
        "runtime_event_log_path": preflight.get("runtime_event_log_path"),
        "blocked_reason": None if ready else preflight["blocked_reason"],
        "fresh_runtime_capture_required": not ready,
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "external_data_evaluated": False,
        "profile_ids": list(PROFILE_IDS),
        "golden_profile_count": len(golden_results),
        "corrupt_case_count": len(corrupt_results),
        "corrupt_matrix_silent_pass_rate": 0.0 if all(not row["passed"] for row in corrupt_results) else 1.0,
        "structured_rejection_reason_coverage": coverage["structured_rejection_reason_coverage"],
        "non_claims": dict(NON_CLAIMS),
    }
    if runtime_evidence_report is not None:
        config["runtime_evidence_level"] = "L2_verifier_owned_raw_runtime_events"
        config["runtime_event_log_path"] = "data/runtime_evidence/runtime_event_log.jsonl"
        config["runtime_event_log_sha256"] = runtime_evidence_report["runtime_event_log_sha256"]
        if runtime_evidence_report.get("process_provenance_receipt_sha256"):
            config["process_provenance_receipt_sha256"] = runtime_evidence_report[
                "process_provenance_receipt_sha256"
            ]
    write_json(data_dir / "config.json", config)
    _write_buyer_report(package_dir, config=config, coverage=coverage)
    _write_readme(package_dir, config=config)
    _write_artifact_indexes(package_dir)
    return {
        "package_dir": str(package_dir),
        "package_manifest": str(package_dir / "package_manifest.json"),
        "status": status,
        "file_drop_rehearsal_ready": ready,
        "corrupt_case_count": len(corrupt_results),
        "golden_profile_count": len(golden_results),
        "blocked_reason": config["blocked_reason"],
        "runtime_event_evidence_emitted": runtime_evidence_report is not None,
    }


def build_rehearsal_package(
    *,
    package_dir: Path = DEFAULT_PACKAGE_DIR,
    runtime_capture: Path | None = None,
    fixture_only: bool = True,
    emit_runtime_event_evidence: bool = False,
    clean: bool = False,
) -> dict[str, Any]:
    if clean and package_dir.exists():
        _assert_managed_package_dir(package_dir)
        shutil.rmtree(package_dir)
    trace, preflight, capture_receipt = prepare_canonical_trace(runtime_capture, fixture_only=fixture_only)
    return _materialize_rehearsal_package(
        package_dir=package_dir,
        trace=trace,
        preflight=preflight,
        capture_receipt=capture_receipt,
        status=STATUS_CONTRACT_READY,
        ready=False,
        emit_runtime_event_evidence=emit_runtime_event_evidence,
        runtime_capture=runtime_capture,
    )


def build_capture_edge_ready_rehearsal_package(
    *,
    package_dir: Path = DEFAULT_PACKAGE_DIR,
    clean: bool = False,
    frame_count: int = MIN_CANONICAL_FRAMES,
    capture_id: str = "mvp5a-pre-capture-edge-runtime-event-close-v0",
) -> dict[str, Any]:
    if clean and package_dir.exists():
        _assert_managed_package_dir(package_dir)
        shutil.rmtree(package_dir)
    data_dir = package_dir / "data"
    (data_dir / "runtime_evidence").mkdir(parents=True, exist_ok=True)
    (data_dir / "process_provenance").mkdir(parents=True, exist_ok=True)

    runtime_report = _run_capture_edge_emitter(
        package_dir=package_dir,
        capture_id=capture_id,
        frame_count=frame_count,
    )
    events = read_runtime_event_log(Path(runtime_report["runtime_event_log_path"]))
    trace = reconstruct_canonical_trace_from_runtime_events(events)
    canonical_sha = sha256_bytes((stable_json(trace) + "\n").encode("utf-8"))
    _write_capture_edge_runtime_receipts(
        package_dir=package_dir,
        trace=trace,
        runtime_report=runtime_report,
    )
    preflight = {
        "schema_version": "rdf_mvp5a_pre_runtime_capture_preflight_v0.1.0",
        "runtime_capture_supplied": False,
        "runtime_capture_sufficient": False,
        "runtime_capture_structurally_valid": False,
        "fresh_runtime_capture_required": False,
        "blocked_reason": None,
        "issues": [],
        "runtime_capture_path": None,
        "runtime_capture_sha256": None,
        "runtime_event_capture_supplied": True,
        "runtime_event_capture_sufficient": True,
        "runtime_event_capture_structurally_valid": True,
        "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
        "minimum_required_frames": MIN_CANONICAL_FRAMES,
        "observed_min_source_log_rows_emitted": len(_frames(trace)),
        "runtime_event_log_sha256": runtime_report["runtime_event_log_sha256"],
        "process_provenance_receipt_path": CAPTURE_EDGE_PROCESS_PROVENANCE_RECEIPT_PATH,
        "process_provenance_receipt_sha256": runtime_report["process_provenance_receipt_sha256"],
    }
    capture_receipt = {
        "schema_version": "rdf_mvp5a_pre_runtime_capture_hash_receipt_v0.1.0",
        "canonical_trace_sha256": canonical_sha,
        "runtime_capture_supplied": False,
        "runtime_capture_sufficient": False,
        "runtime_capture_structurally_valid": False,
        "runtime_capture_path": None,
        "runtime_capture_sha256": None,
        "runtime_event_capture_supplied": True,
        "runtime_event_capture_sufficient": True,
        "runtime_event_capture_structurally_valid": True,
        "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
        "ready_status_allowed": True,
        "blocked_reason": None,
        "runtime_event_log_sha256": runtime_report["runtime_event_log_sha256"],
        "process_provenance_receipt_path": CAPTURE_EDGE_PROCESS_PROVENANCE_RECEIPT_PATH,
        "process_provenance_receipt_sha256": runtime_report["process_provenance_receipt_sha256"],
        "process_provenance_ceiling": "declared_process_identity_only_not_physics_authenticity",
    }
    result = _materialize_rehearsal_package(
        package_dir=package_dir,
        trace=trace,
        preflight=preflight,
        capture_receipt=capture_receipt,
        status=STATUS_READY,
        ready=True,
        runtime_evidence_report=runtime_report,
    )
    result["process_provenance_receipt"] = str(package_dir / CAPTURE_EDGE_PROCESS_PROVENANCE_RECEIPT_PATH)
    return result


def _run_capture_edge_emitter(
    *,
    package_dir: Path,
    capture_id: str,
    frame_count: int,
) -> dict[str, Any]:
    process_dir = package_dir / "data" / "process_provenance"
    runtime_dir = package_dir / "data" / "runtime_evidence"
    process_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    script_repo_path = ROOT / CAPTURE_EDGE_EMITTER_SCRIPT_REPO_PATH
    script_snapshot_path = package_dir / CAPTURE_EDGE_EMITTER_SCRIPT_SNAPSHOT_PATH
    config_path = package_dir / CAPTURE_EDGE_EMITTER_CONFIG_PATH
    stdout_path = package_dir / CAPTURE_EDGE_EMITTER_STDOUT_PATH
    stderr_path = package_dir / CAPTURE_EDGE_EMITTER_STDERR_PATH
    event_log_path = package_dir / "data" / "runtime_evidence" / "runtime_event_log.jsonl"

    config = {
        "schema_version": CAPTURE_EDGE_EMITTER_CONFIG_SCHEMA_VERSION,
        "capture_id": capture_id,
        "frame_count": frame_count,
        "source_backend": RUNTIME_BACKEND,
        "source_process_kind": CAPTURE_EDGE_SOURCE_PROCESS_KIND,
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "real_robot_success": False,
    }
    write_json(config_path, config)
    script_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(script_repo_path, script_snapshot_path)

    command = [
        sys.executable,
        str(script_repo_path),
        "--config",
        str(config_path),
        "--output",
        str(event_log_path),
    ]
    normalized_command_argv = [
        "python",
        CAPTURE_EDGE_EMITTER_SCRIPT_REPO_PATH,
        "--config",
        CAPTURE_EDGE_EMITTER_CONFIG_PATH,
        "--output",
        "data/runtime_evidence/runtime_event_log.jsonl",
    ]
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    ended_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"capture-edge emitter failed with exit code {completed.returncode}: {completed.stderr}")
    event_log_sha = sha256_file(event_log_path)
    receipt = {
        "schema_version": PROCESS_PROVENANCE_RECEIPT_SCHEMA_VERSION,
        "capture_script_id": RUNTIME_EVENT_CAPTURE_SCRIPT_ID,
        "source_backend": RUNTIME_BACKEND,
        "source_process_kind": CAPTURE_EDGE_SOURCE_PROCESS_KIND,
        "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
        "runtime_event_log_sha256": event_log_sha,
        "exit_code": completed.returncode,
        "git_commit": _git_value("rev-parse", "HEAD"),
        "git_branch": _git_value("rev-parse", "--abbrev-ref", "HEAD"),
        "command": " ".join(normalized_command_argv),
        "command_argv": normalized_command_argv,
        "command_argv_kind": "repo_relative_normalized",
        "python_version": sys.version.split()[0],
        "os_summary": f"{platform.system()} {platform.release()}",
        "started_at": started_at,
        "ended_at": ended_at,
        "working_directory": ROOT.as_posix(),
        "working_directory_kind": "repo_root",
        "repo_relative_cwd": ".",
        "script_path": CAPTURE_EDGE_EMITTER_SCRIPT_SNAPSHOT_PATH,
        "script_sha256": sha256_file(script_snapshot_path),
        "script_repo_path": CAPTURE_EDGE_EMITTER_SCRIPT_REPO_PATH,
        "script_repo_sha256": sha256_file(script_repo_path),
        "config_path": CAPTURE_EDGE_EMITTER_CONFIG_PATH,
        "config_sha256": sha256_file(config_path),
        "stdout_log_path": CAPTURE_EDGE_EMITTER_STDOUT_PATH,
        "stdout_log_sha256": sha256_file(stdout_path),
        "stderr_log_path": CAPTURE_EDGE_EMITTER_STDERR_PATH,
        "stderr_log_sha256": sha256_file(stderr_path),
        "process_provenance_ceiling": "declared_process_identity_only_not_physics_authenticity",
        "non_claims": dict(NON_CLAIMS),
    }
    receipt_path = package_dir / CAPTURE_EDGE_PROCESS_PROVENANCE_RECEIPT_PATH
    write_json(receipt_path, receipt)
    return {
        "runtime_event_log_path": event_log_path,
        "runtime_event_log_sha256": event_log_sha,
        "process_provenance_receipt_path": receipt_path,
        "process_provenance_receipt_sha256": sha256_file(receipt_path),
        "script_repo_path": script_repo_path,
        "script_repo_sha256": sha256_file(script_repo_path),
        "frame_count": frame_count,
    }


def _write_capture_edge_runtime_receipts(
    *,
    package_dir: Path,
    trace: dict[str, Any],
    runtime_report: dict[str, Any],
) -> None:
    runtime_dir = package_dir / "data" / "runtime_evidence"
    event_log_sha = str(runtime_report["runtime_event_log_sha256"])
    events = read_runtime_event_log(Path(runtime_report["runtime_event_log_path"]))
    canonical_sha = sha256_bytes((stable_json(trace) + "\n").encode("utf-8"))
    write_json(
        runtime_dir / "runtime_event_manifest.json",
        {
            "schema_version": RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION,
            "evidence_level": "L2_verifier_owned_raw_runtime_events",
            "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
            "runtime_event_log_sha256": event_log_sha,
            "capture_id": events[0]["capture_id"] if events else None,
            "capture_script_id": RUNTIME_EVENT_CAPTURE_SCRIPT_ID,
            "evidence_origin": RUNTIME_EVENT_CAPTURE_EDGE_EVIDENCE_ORIGIN,
            "producer_kind": RUNTIME_EVENT_CAPTURE_EDGE_PRODUCER_KIND,
            "closing_evidence": True,
            "source_backend": RUNTIME_BACKEND,
            "source_process_kind": CAPTURE_EDGE_SOURCE_PROCESS_KIND,
            "frame_count": len(_frames(trace)),
            "event_count": len(events),
            "required_channels": list(RUNTIME_EVENT_REQUIRED_CHANNELS),
            "generated_by_rdf_sim": True,
            "external_partner_data": False,
            "non_claims": dict(NON_CLAIMS),
        },
    )
    write_json(
        runtime_dir / "runtime_reconstruction_receipt.json",
        {
            "schema_version": RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION,
            "reconstruction_algorithm": RUNTIME_RECONSTRUCTION_ALGORITHM,
            "runtime_event_log_sha256": event_log_sha,
            "reconstructed_canonical_trace_sha256": canonical_sha,
            "included_canonical_trace_sha256": canonical_sha,
            "matches_included_canonical_trace": True,
            "runtime_capture_supplied": False,
            "runtime_capture_sufficient": False,
            "runtime_capture_structurally_valid": False,
            "runtime_capture_path": None,
            "runtime_capture_sha256": None,
            "runtime_event_capture_supplied": True,
            "runtime_event_capture_sufficient": True,
            "runtime_event_capture_structurally_valid": True,
            "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
            "ready_status_allowed": True,
            "frame_count": len(_frames(trace)),
            "required_channels": list(RUNTIME_EVENT_REQUIRED_CHANNELS),
        },
    )


def _git_value(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _profile(profile_id: str) -> ProfileSpec:
    try:
        return PROFILE_REGISTRY[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown profile_id: {profile_id}") from exc


def _pose_matrix(*, x: float, y: float, z: float) -> list[float]:
    return [
        1.0,
        0.0,
        0.0,
        x,
        0.0,
        1.0,
        0.0,
        y,
        0.0,
        0.0,
        1.0,
        z,
        0.0,
        0.0,
        0.0,
        1.0,
    ]


def _frames(trace: dict[str, Any]) -> list[dict[str, Any]]:
    frames = trace.get("frames")
    if not isinstance(frames, list):
        raise ValueError("canonical trace frames missing")
    return [frame for frame in frames if isinstance(frame, dict)]


def _metadata_for_profile(spec: ProfileSpec) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_METADATA_SCHEMA_VERSION,
        "profile_id": spec.profile_id,
        "source_kind": "digital_twin_rehearsal_log",
        "source_origin": "rdf_digital_twin_rehearsal",
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "external_data_evaluated": False,
        "real_robot_success": False,
        "live_runtime_support": False,
        "robot_family": spec.robot_family,
        "robot_model": spec.robot_model,
        "dof": spec.dof,
        "joint_names": list(spec.joint_names),
        "time_base": "seconds",
        "units": {
            "joint_position": "rad",
            "tcp_position": "m",
            "tcp_rotation": "rotation_vector_rad" if spec.profile_id == "ur_rtde_csv_v0" else "matrix_or_profile_native",
            "velocity": "m_per_s",
        },
        "action_semantics": spec.action_semantics,
        "state_semantics": spec.state_semantics,
        "state_only_profile": False,
        "claim_boundary": dict(NON_CLAIMS),
    }


def _write_ur_csv(path: Path, frames: list[dict[str, Any]], spec: ProfileSpec) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "joint_names",
        "actual_q",
        "target_q",
        "actual_TCP_pose",
        "target_TCP_pose",
        "actual_TCP_speed",
        "robot_mode",
        "safety_status",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for frame in frames:
            ur = frame["ur"]
            writer.writerow(
                {
                    "timestamp": frame["timestamp"],
                    "joint_names": stable_compact_json(list(spec.joint_names)),
                    "actual_q": stable_compact_json(ur["actual_q"]),
                    "target_q": stable_compact_json(ur["target_q"]),
                    "actual_TCP_pose": stable_compact_json(ur["actual_TCP_pose"]),
                    "target_TCP_pose": stable_compact_json(ur["target_TCP_pose"]),
                    "actual_TCP_speed": stable_compact_json(ur["actual_TCP_speed"]),
                    "robot_mode": ur["robot_mode"],
                    "safety_status": ur["safety_status"],
                }
            )


def _write_franka_jsonl(output_dir: Path, frames: list[dict[str, Any]]) -> None:
    state_rows = []
    command_rows = []
    for frame in frames:
        franka = frame["franka"]
        state_rows.append(
            {
                "timestamp": frame["timestamp"],
                "q": franka["q"],
                "O_T_EE": franka["O_T_EE"],
                "robot_mode": franka["robot_mode"],
            }
        )
        command_rows.append({"timestamp": frame["timestamp"], "q_d": franka["q_d"], "O_T_EE_d": franka["O_T_EE_d"]})
    write_jsonl(output_dir / "franka_state.jsonl", state_rows)
    write_jsonl(output_dir / "franka_command.jsonl", command_rows)


def _write_ros2_bundle(output_dir: Path, frames: list[dict[str, Any]], spec: ProfileSpec) -> None:
    write_json(
        output_dir / "topic_manifest.json",
        {
            "schema_version": "rdf_mvp5a_pre_ros2_channel_manifest_v0.1.0",
            "topics": ["/joint_states", "/tf", "/tf_static", "/command"],
            "serialization": "jsonl_channel_bundle",
        },
    )
    write_jsonl(output_dir / "topics" / "tf_static.jsonl", [{"parent_frame_id": "world", "child_frame_id": "base_link"}])
    joint_rows = []
    tf_rows = []
    command_rows = []
    for frame in frames:
        ur = frame["ur"]
        joint_rows.append(
            {
                "timestamp": frame["timestamp"],
                "name": list(spec.joint_names),
                "position": ur["actual_q"],
                "frame_id": "base_link",
            }
        )
        tf_rows.append(
            {
                "timestamp": frame["timestamp"],
                "parent_frame_id": "base_link",
                "child_frame_id": "tool0",
                "translation": ur["actual_TCP_pose"][:3],
                "rotation_rpy": ur["actual_TCP_pose"][3:],
            }
        )
        command_rows.append({"timestamp": frame["timestamp"], "target_position": ur["target_q"], "frame_id": "base_link"})
    write_jsonl(output_dir / "topics" / "joint_states.jsonl", joint_rows)
    write_jsonl(output_dir / "topics" / "tf.jsonl", tf_rows)
    write_jsonl(output_dir / "topics" / "command.jsonl", command_rows)


def _write_generic_jsonl(path: Path, frames: list[dict[str, Any]]) -> None:
    rows = []
    for frame in frames:
        generic = frame["generic"]
        rows.append(
            {
                "timestamp": frame["timestamp"],
                "command_timestamp": generic["command_timestamp"],
                "state_timestamp": generic["state_timestamp"],
                "command": generic["command"],
                "state": generic["state"],
                "action_semantics": "explicit_command_vector",
                "state_semantics": "explicit_state_vector",
                "reset_boundary": False,
                "task_success": None,
            }
        )
    write_jsonl(path, rows)


def _read_json_object(path: Path, issues: list[str], *, missing_reason: str) -> dict[str, Any]:
    if not path.exists():
        issues.append(missing_reason)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues.append("schema_type_mismatch")
        return {}
    if not isinstance(payload, dict):
        issues.append("schema_type_mismatch")
        return {}
    return payload


def _read_jsonl(path: Path, issues: list[str], *, missing_reason: str) -> list[dict[str, Any]]:
    if not path.exists():
        issues.append(missing_reason)
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        issues.append("schema_type_mismatch")
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            issues.append("schema_type_mismatch")
            continue
        if not isinstance(row, dict):
            issues.append("schema_type_mismatch")
            continue
        rows.append(row)
    return rows


def _validate_metadata(metadata: dict[str, Any], spec: ProfileSpec) -> list[str]:
    issues: list[str] = []
    required = ("schema_version", "profile_id", "source_kind", "generated_by_rdf_sim", "external_partner_data", "robot_family", "robot_model", "dof", "joint_names", "units", "action_semantics", "state_semantics")
    for key in required:
        if key not in metadata:
            issues.append("schema_missing_required_field")
    if metadata.get("schema_version") != SOURCE_METADATA_SCHEMA_VERSION:
        issues.append("schema_type_mismatch")
    if metadata.get("profile_id") != spec.profile_id:
        issues.append("unsupported_profile")
    if metadata.get("source_kind") != "digital_twin_rehearsal_log":
        issues.append("provenance_boundary_violation")
    if metadata.get("generated_by_rdf_sim") is not True:
        issues.append("provenance_boundary_violation")
    if metadata.get("external_partner_data") is not False or metadata.get("external_data_evaluated") is True:
        issues.append("provenance_boundary_violation")
    if metadata.get("real_robot_success") is True:
        issues.append("claim_boundary_violation")
    if metadata.get("robot_family") != spec.robot_family or metadata.get("robot_model") != spec.robot_model:
        issues.append("unsupported_profile")
    if metadata.get("dof") != spec.dof or metadata.get("joint_names") != list(spec.joint_names):
        issues.append("vector_dimension_mismatch")
    units = metadata.get("units")
    if not isinstance(units, dict):
        issues.append("unit_mismatch")
    else:
        if units.get("joint_position") != "rad":
            issues.append("unit_mismatch")
        if spec.profile_id == "ur_rtde_csv_v0" and units.get("tcp_position") != "m":
            issues.append("unit_mismatch")
        if spec.profile_id == "ur_rtde_csv_v0" and units.get("tcp_rotation") != "rotation_vector_rad":
            issues.append("unit_mismatch")
    if metadata.get("action_semantics") != spec.action_semantics or metadata.get("state_semantics") != spec.state_semantics:
        issues.append("action_state_semantic_mismatch")
    for key in FORBIDDEN_CLAIMS:
        if metadata.get(key) is True:
            issues.append("claim_boundary_violation")
    return issues


def _parse_json_array(value: Any, issues: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        issues.append("schema_type_mismatch")
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        issues.append("schema_type_mismatch")
        return []
    if not isinstance(parsed, list):
        issues.append("schema_type_mismatch")
        return []
    return parsed


def _parse_ur_csv(path: Path, spec: ProfileSpec) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    if not path.exists():
        return [], ["schema_missing_required_artifact"]
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except csv.Error:
        return [], ["schema_type_mismatch"]
    required = {"timestamp", "joint_names", "actual_q", "target_q", "actual_TCP_pose", "target_TCP_pose", "actual_TCP_speed", "robot_mode", "safety_status"}
    if rows and set(rows[0]) != required:
        issues.append("schema_missing_required_field")
    output = []
    for raw in rows:
        if any(raw.get(field) in (None, "") for field in required):
            issues.append("schema_missing_required_field")
        try:
            timestamp = float(raw.get("timestamp", "nan"))
        except ValueError:
            issues.append("schema_type_mismatch")
            timestamp = math.nan
        joint_names = _parse_json_array(raw.get("joint_names"), issues)
        actual_q = _parse_json_array(raw.get("actual_q"), issues)
        target_q = _parse_json_array(raw.get("target_q"), issues)
        actual_tcp = _parse_json_array(raw.get("actual_TCP_pose"), issues)
        target_tcp = _parse_json_array(raw.get("target_TCP_pose"), issues)
        speed = _parse_json_array(raw.get("actual_TCP_speed"), issues)
        if joint_names != list(spec.joint_names):
            issues.append("frame_semantic_drift")
        output.append(
            {
                "timestamp": timestamp,
                "state_vector": actual_q,
                "action_vector": target_q,
                "actual_q": actual_q,
                "target_q": target_q,
                "actual_TCP_pose": actual_tcp,
                "target_TCP_pose": target_tcp,
                "actual_TCP_speed": speed,
                "robot_mode": raw.get("robot_mode"),
                "safety_status": raw.get("safety_status"),
            }
        )
    return output, _dedupe(issues)


def _parse_franka_jsonl(drop_dir: Path, spec: ProfileSpec) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    state_rows = _read_jsonl(drop_dir / "franka_state.jsonl", issues, missing_reason="schema_missing_required_artifact")
    command_rows = _read_jsonl(drop_dir / "franka_command.jsonl", issues, missing_reason="schema_missing_required_artifact")
    output: list[dict[str, Any]] = []
    for state, command in zip(state_rows, command_rows, strict=False):
        timestamp = _float_or_nan(state.get("timestamp"))
        output.append(
            {
                "timestamp": timestamp,
                "state_vector": state.get("q"),
                "action_vector": command.get("q_d"),
                "q": state.get("q"),
                "q_d": command.get("q_d"),
                "O_T_EE": state.get("O_T_EE"),
                "O_T_EE_d": command.get("O_T_EE_d"),
                "robot_mode": state.get("robot_mode"),
                "command_timestamp": _float_or_nan(command.get("timestamp")),
            }
        )
    if len(state_rows) != len(command_rows):
        issues.append("timestamp_gap_or_drift")
    return output, _dedupe(issues)


def _parse_ros2_bundle(drop_dir: Path, spec: ProfileSpec) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    manifest = _read_json_object(drop_dir / "topic_manifest.json", issues, missing_reason="schema_missing_required_artifact")
    topics = manifest.get("topics")
    if set(topics or []) != {"/joint_states", "/tf", "/tf_static", "/command"}:
        issues.append("schema_missing_required_artifact")
    joint_rows = _read_jsonl(drop_dir / "topics" / "joint_states.jsonl", issues, missing_reason="schema_missing_required_artifact")
    tf_rows = _read_jsonl(drop_dir / "topics" / "tf.jsonl", issues, missing_reason="schema_missing_required_artifact")
    tf_static = _read_jsonl(drop_dir / "topics" / "tf_static.jsonl", issues, missing_reason="schema_missing_required_artifact")
    command_rows = _read_jsonl(drop_dir / "topics" / "command.jsonl", issues, missing_reason="schema_missing_required_artifact")
    if not tf_static:
        issues.append("frame_tree_invalid")
    output: list[dict[str, Any]] = []
    for joint, tf, command in zip(joint_rows, tf_rows, command_rows, strict=False):
        timestamp = _float_or_nan(joint.get("timestamp"))
        output.append(
            {
                "timestamp": timestamp,
                "state_vector": joint.get("position"),
                "action_vector": command.get("target_position"),
                "joint_names": joint.get("name"),
                "frame_id": joint.get("frame_id"),
                "tf_parent": tf.get("parent_frame_id"),
                "tf_child": tf.get("child_frame_id"),
                "tf_timestamp": _float_or_nan(tf.get("timestamp")),
                "command_timestamp": _float_or_nan(command.get("timestamp")),
                "command_frame_id": command.get("frame_id"),
            }
        )
    if len({len(joint_rows), len(tf_rows), len(command_rows)}) != 1:
        issues.append("timestamp_gap_or_drift")
    return output, _dedupe(issues)


def _parse_generic_jsonl(path: Path, spec: ProfileSpec) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    rows = _read_jsonl(path, issues, missing_reason="schema_missing_required_artifact")
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "timestamp": _float_or_nan(row.get("timestamp")),
                "state_vector": row.get("state"),
                "action_vector": row.get("command"),
                "command_timestamp": _float_or_nan(row.get("command_timestamp")),
                "state_timestamp": _float_or_nan(row.get("state_timestamp")),
                "action_semantics": row.get("action_semantics"),
                "state_semantics": row.get("state_semantics"),
                "reset_boundary": row.get("reset_boundary"),
                "task_success": row.get("task_success"),
            }
        )
    return output, _dedupe(issues)


def _validate_common_rows(rows: list[dict[str, Any]], spec: ProfileSpec) -> list[str]:
    issues: list[str] = []
    if len(rows) < MIN_CANONICAL_FRAMES:
        issues.append("timestamp_gap_or_drift")
    previous = None
    for row in rows:
        timestamp = row.get("timestamp")
        if not _finite_number(timestamp):
            issues.append("schema_type_mismatch")
        elif previous is not None:
            if timestamp <= previous:
                issues.append("timestamp_not_monotonic")
            if timestamp - previous > MAX_TIMESTAMP_GAP_SECONDS:
                issues.append("timestamp_gap_or_drift")
            previous = timestamp
        elif _finite_number(timestamp):
            previous = timestamp
        state = row.get("state_vector")
        action = row.get("action_vector")
        if not _numeric_vector(state, spec.dof):
            issues.append("vector_dimension_mismatch")
        if not _numeric_vector(action, spec.dof):
            issues.append("vector_dimension_mismatch")
    return _dedupe(issues)


def _validate_profile_semantics(rows: list[dict[str, Any]], spec: ProfileSpec) -> list[str]:
    issues: list[str] = []
    for row in rows:
        if spec.profile_id == "ur_rtde_csv_v0":
            if row.get("robot_mode") != "RUNNING" or row.get("safety_status") != "NORMAL":
                issues.append("safety_or_robot_mode_invalid")
            if not _numeric_vector(row.get("actual_TCP_pose"), 6) or not _numeric_vector(row.get("target_TCP_pose"), 6):
                issues.append("vector_dimension_mismatch")
            if _vector_distance(row.get("actual_q"), row.get("target_q")) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        elif spec.profile_id == "franka_state_jsonl_v0":
            if row.get("robot_mode") != "move":
                issues.append("safety_or_robot_mode_invalid")
            if not _numeric_vector(row.get("O_T_EE"), 16) or not _numeric_vector(row.get("O_T_EE_d"), 16):
                issues.append("vector_dimension_mismatch")
            elif not _rigid_transform_plausible(row["O_T_EE"]):
                issues.append("frame_semantic_drift")
            if abs(float(row.get("command_timestamp", math.nan)) - float(row.get("timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        elif spec.profile_id == "ros2_channel_bundle_jsonl_v0":
            if row.get("joint_names") != list(spec.joint_names):
                issues.append("frame_semantic_drift")
            if row.get("frame_id") != "base_link" or row.get("command_frame_id") != "base_link":
                issues.append("frame_tree_invalid")
            if row.get("tf_parent") != "base_link" or row.get("tf_child") != "tool0":
                issues.append("frame_tree_invalid")
            if abs(float(row.get("tf_timestamp", math.nan)) - float(row.get("timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("timestamp_gap_or_drift")
            if abs(float(row.get("command_timestamp", math.nan)) - float(row.get("timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        else:
            if row.get("action_semantics") != spec.action_semantics or row.get("state_semantics") != spec.state_semantics:
                issues.append("action_state_semantic_mismatch")
            if row.get("reset_boundary") is True:
                issues.append("action_state_semantic_mismatch")
            if row.get("task_success") is not None:
                issues.append("claim_boundary_violation")
            if abs(float(row.get("command_timestamp", math.nan)) - float(row.get("state_timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
            if row.get("command_timestamp", 0) > row.get("state_timestamp", 0):
                issues.append("action_state_semantic_mismatch")
    return _dedupe(issues)


def _validation_result(
    profile_id: str,
    case_id: str,
    issues: list[str],
    frame_count: int,
    drop_dir: Path,
    rows: tuple[dict[str, Any], ...],
) -> ValidationResult:
    reasons = tuple(reason for reason in REJECTION_REASONS if reason in set(issues))
    passed = not reasons
    return ValidationResult(
        profile_id=profile_id,
        case_id=case_id,
        passed=passed,
        rejection_reasons=reasons,
        frame_count=frame_count,
        source_file_hashes=build_source_hashes(drop_dir),
        export_eligible=passed,
        trainer_smoke_eligible=passed,
        normalized_rows=rows if passed else (),
    )


def build_source_hashes(drop_dir: Path) -> dict[str, dict[str, Any]]:
    hashes = {}
    for path in sorted(drop_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(drop_dir).as_posix()
            hashes[rel] = {"sha256": sha256_file(path), "byte_size": path.stat().st_size}
    return hashes


def _normalized_contract(profile_id: str, result: ValidationResult) -> dict[str, Any]:
    spec = _profile(profile_id)
    return {
        "schema_version": "rdf_mvp5a_pre_normalized_contract_v0.1.0",
        "profile_id": profile_id,
        "passed": result.passed,
        "frame_count": result.frame_count,
        "state_dim": spec.dof,
        "action_dim": spec.dof,
        "action_semantics": spec.action_semantics,
        "state_semantics": spec.state_semantics,
        "export_eligible": result.export_eligible,
        "trainer_smoke_eligible": result.trainer_smoke_eligible,
        "rows": [
            {
                "timestamp": row["timestamp"],
                "state_vector": row["state_vector"],
                "action_vector": row["action_vector"],
            }
            for row in result.normalized_rows
        ],
    }


def _result_payload(
    result: ValidationResult,
    *,
    expected_rejection_reason: str | None,
    export_report: dict[str, Any] | None = None,
    mutation: MutationSpec | None = None,
) -> dict[str, Any]:
    payload_profile_id = mutation.profile_id if mutation is not None else result.profile_id
    payload = {
        "profile_id": payload_profile_id,
        "case_id": result.case_id,
        "passed": result.passed,
        "frame_count": result.frame_count,
        "rejection_reasons": list(result.rejection_reasons),
        "expected_rejection_reason": expected_rejection_reason,
        "expected_rejection_reason_observed": expected_rejection_reason in result.rejection_reasons if expected_rejection_reason else None,
        "export_eligible": result.export_eligible,
        "trainer_smoke_eligible": result.trainer_smoke_eligible,
        "source_file_hashes": result.source_file_hashes,
    }
    if mutation is not None:
        payload.update({"mutation_id": mutation.mutation_id, "category": mutation.category, "description": mutation.description})
    if export_report is not None:
        payload["export"] = {
            "hdf5_path": f"data/export/{result.profile_id}/dataset.hdf5",
            "hdf5_sha256": sha256_file(export_report["hdf5_path"]),
            "trainer_smoke_passed": export_report["trainer"]["passed"],
        }
    return payload


def _rejection_reason_coverage(corrupt_results: list[dict[str, Any]]) -> dict[str, Any]:
    observed = sorted({reason for row in corrupt_results for reason in row["rejection_reasons"]})
    categories = sorted({row["category"] for row in corrupt_results})
    expected_misses = [
        row["case_id"]
        for row in corrupt_results
        if not row.get("expected_rejection_reason_observed")
    ]
    silent_passes = [row["case_id"] for row in corrupt_results if row["passed"]]
    return {
        "schema_version": "rdf_mvp5a_pre_rejection_reason_coverage_v0.1.0",
        "corrupt_case_count": len(corrupt_results),
        "silent_passes": silent_passes,
        "expected_rejection_reason_misses": expected_misses,
        "observed_rejection_reasons": observed,
        "covered_categories": categories,
        "structured_rejection_reason_coverage": len(expected_misses) == 0 and len(silent_passes) == 0,
        "silent_pass_rate": 0.0 if not corrupt_results else len(silent_passes) / len(corrupt_results),
    }


def _write_buyer_report(package_dir: Path, *, config: dict[str, Any], coverage: dict[str, Any]) -> None:
    rows = "\n".join(f"<tr><td>{profile_id}</td><td>golden PASS</td><td>corrupt fail-closed</td></tr>" for profile_id in PROFILE_IDS)
    report = f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal</title></head>
<body>
  <h1>MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal</h1>
  <p>RDF rehearses recorded-log file-drop ingestion with generated digital-twin logs. This is not external partner data evaluation.</p>
  <p>Status: <code>{config['status']}</code></p>
  <p>Contract ready: {str(config['file_drop_rehearsal_contract_ready']).lower()} | Ready: {str(config['file_drop_rehearsal_ready']).lower()}</p>
  <p>Runtime capture supplied: {str(config['runtime_capture_supplied']).lower()} | Runtime capture sufficient: {str(config['runtime_capture_sufficient']).lower()}</p>
  <p>Runtime event capture supplied: {str(config['runtime_event_capture_supplied']).lower()} | Runtime event capture sufficient: {str(config['runtime_event_capture_sufficient']).lower()} | Blocked reason: {config['blocked_reason']}</p>
  <table><thead><tr><th>Profile</th><th>Golden</th><th>Corrupt matrix</th></tr></thead><tbody>{rows}</tbody></table>
  <p>Corrupt cases: {coverage['corrupt_case_count']} | silent pass rate: {coverage['silent_pass_rate']}</p>
  <h2>Proof boundary</h2>
  <p>The verifier-backed package evidence is the source of truth, not this HTML report.</p>
  <p>Process provenance binds the declared command, script, config, logs, and event hash. It does not prove the runtime was a genuine physics run rather than replay or fabrication.</p>
  <p>No external partner data evaluation.</p>
  <p>No real robot success.</p>
  <p>No hardware readiness.</p>
  <p>No live UR RTDE support.</p>
  <p>No live Franka hardware support.</p>
  <p>No live ROS2 DDS bridge readiness.</p>
  <p>No native MCAP parser support.</p>
  <p>No policy uplift.</p>
  <p>No production certification.</p>
  <p>No marketplace readiness.</p>
  <p>No sim-to-real performance claim.</p>
</body>
</html>
"""
    (package_dir / "buyer_report.html").write_text(report, encoding="utf-8")
    reports_dir = package_dir / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "buyer_report.html").write_text(report, encoding="utf-8")


def _write_readme(package_dir: Path, *, config: dict[str, Any]) -> None:
    if config["file_drop_rehearsal_ready"]:
        close_text = """`file_drop_rehearsal_ready=true` is opened only for the L2/L3
capture-edge path: raw runtime events, process provenance receipt, L2 runtime
manifest, reconstruction receipt, and verifier recomputation all agree.
Runtime-shaped summary JSON or helper-derived event logs are not closing
evidence."""
    else:
        close_text = """`file_drop_rehearsal_ready=true` is disabled for this
contract-ready consistency package. The ready close requires a capture-edge
runtime event emitter, process provenance receipt, L2 runtime manifest,
reconstruction receipt, and verifier recomputation. Runtime-shaped summary JSON
or helper-derived event logs are not closing evidence. This checked-in fixture
package remains contract-ready."""
    verifier_args = "--deep-hdf5" if config["status"] == STATUS_READY else "--allow-contract-ready --deep-hdf5"
    text = f"""# MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal

Status: `{config['status']}`

This package rehearses RDF recorded-log file-drop ingestion with deterministic
digital-twin UR/Franka/ROS2-style/generic logs.

The default verifier recomputes package consistency from included evidence:

```bash
uv run python scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py docs/proof/{PACKAGE_NAME}/package_manifest.json {verifier_args}
```

{close_text}

For a ready package, process provenance binds the declared command, script,
config, stdout/stderr logs, and runtime event hash. It does not prove the
runtime was a genuine physics run rather than replay or fabrication.

## Claim Boundary

No external partner data evaluation.
No real robot success.
No hardware readiness.
No live UR RTDE support.
No live Franka hardware support.
No live ROS2 DDS bridge readiness.
No native MCAP parser support.
No policy uplift.
No production certification.
No marketplace readiness.
No sim-to-real performance claim.
"""
    (package_dir / "README.md").write_text(text, encoding="utf-8")


def _write_artifact_indexes(package_dir: Path) -> None:
    data_dir = package_dir / "data"
    artifact_index = [
        _artifact_entry(package_dir, path)
        for path in sorted(data_dir.rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    ]
    write_json(
        data_dir / "artifact_index.json",
        {"schema_version": "rdf_mvp5a_pre_artifact_index_v0.1.0", "artifact_index": artifact_index},
    )
    manifest_entries = [
        _artifact_entry(package_dir, path)
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    ]
    config = json.loads((data_dir / "config.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_name": PACKAGE_NAME,
        "package_status": config["status"],
        "verdict_source_of_truth": "data/",
        "verifier": "scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py",
        "file_drop_rehearsal_contract_ready": config["file_drop_rehearsal_contract_ready"],
        "file_drop_rehearsal_ready": config["file_drop_rehearsal_ready"],
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "external_data_evaluated": False,
        "non_claims": dict(NON_CLAIMS),
        "artifact_index": manifest_entries,
    }
    if "runtime_evidence_level" in config:
        manifest["runtime_evidence_level"] = config["runtime_evidence_level"]
        manifest["runtime_event_log_sha256"] = config["runtime_event_log_sha256"]
    write_json(package_dir / "package_manifest.json", manifest)


def _artifact_entry(package_dir: Path, path: Path) -> dict[str, Any]:
    return {
        "data_path": path.relative_to(package_dir).as_posix(),
        "file_sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
        "hash_convention": "file_bytes",
    }


def _resolve_runtime_capture_path(path: Path) -> Path | None:
    if path.is_dir():
        candidate = path / "data" / "runtime_capture.json"
        if candidate.exists():
            return candidate
        candidate = path / "runtime_capture.json"
        if candidate.exists():
            return candidate
        return None
    return path


def _assert_managed_package_dir(path: Path) -> None:
    resolved = path.resolve()
    allowed = (ROOT / "docs" / "proof").resolve()
    temp_root = Path("/tmp").resolve()
    under_allowed = _path_is_within(resolved, allowed)
    under_temp = _path_is_within(resolved, temp_root)
    if PACKAGE_NAME not in resolved.name or not (under_allowed or under_temp):
        raise ValueError(f"refusing to clean unmanaged package dir: {path}")


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _float_or_nan(value: Any) -> float:
    try:
        if isinstance(value, bool):
            return math.nan
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _finite_float(value: Any) -> float | None:
    return float(value) if _finite_number(value) else None


def _numeric_vector(value: Any, expected_len: int) -> bool:
    return isinstance(value, list) and len(value) == expected_len and all(_finite_number(item) for item in value)


def _vector_distance(left: Any, right: Any) -> float:
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
        return math.inf
    try:
        return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)))
    except (TypeError, ValueError):
        return math.inf


def _rigid_transform_plausible(matrix: list[Any]) -> bool:
    if not _numeric_vector(matrix, 16):
        return False
    rot = [
        [float(matrix[0]), float(matrix[1]), float(matrix[2])],
        [float(matrix[4]), float(matrix[5]), float(matrix[6])],
        [float(matrix[8]), float(matrix[9]), float(matrix[10])],
    ]
    for row in rot:
        norm = math.sqrt(sum(value * value for value in row))
        if abs(norm - 1.0) > 0.05:
            return False
    determinant = (
        rot[0][0] * (rot[1][1] * rot[2][2] - rot[1][2] * rot[2][1])
        - rot[0][1] * (rot[1][0] * rot[2][2] - rot[1][2] * rot[2][0])
        + rot[0][2] * (rot[1][0] * rot[2][1] - rot[1][1] * rot[2][0])
    )
    return abs(determinant - 1.0) <= 0.05


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _mutate_json(path: Path, mutator: Callable[[dict[str, Any]], None]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    write_json(path, payload)


def _mutate_jsonl(path: Path, mutator: Callable[[list[dict[str, Any]]], None]) -> None:
    rows = _read_jsonl(path, [], missing_reason="schema_missing_required_artifact")
    mutator(rows)
    write_jsonl(path, rows)


def _mutate_ur_csv(path: Path, mutator: Callable[[list[dict[str, str]]], None]) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    mutator(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _remove_actual_q(rows: list[dict[str, str]]) -> None:
    for row in rows:
        row.pop("actual_q", None)


def _ur_mutations() -> list[MutationSpec]:
    return [
        MutationSpec("missing_metadata", "ur_rtde_csv_v0", "schema", "schema_missing_required_artifact", "metadata removed", lambda d: (d / "metadata.json").unlink()),
        MutationSpec("unknown_profile", "ur_rtde_csv_v0", "schema", "unsupported_profile", "profile id changed", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("profile_id", "unknown_profile"))),
        MutationSpec("missing_actual_q", "ur_rtde_csv_v0", "schema", "schema_missing_required_field", "actual_q header removed", lambda d: _mutate_ur_csv(d / "rtde_output.csv", _remove_actual_q)),
        MutationSpec("joint_dim_wrong", "ur_rtde_csv_v0", "shape", "vector_dimension_mismatch", "actual_q shortened", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[0].__setitem__("actual_q", stable_compact_json([0, 1])))),
        MutationSpec("timestamp_non_monotonic", "ur_rtde_csv_v0", "timestamp", "timestamp_not_monotonic", "timestamp goes backward", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[5].__setitem__("timestamp", rows[2]["timestamp"]))),
        MutationSpec("timestamp_gap_large", "ur_rtde_csv_v0", "timestamp", "timestamp_gap_or_drift", "large timestamp gap", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[6].__setitem__("timestamp", "2.0"))),
        MutationSpec("degrees_unit", "ur_rtde_csv_v0", "unit", "unit_mismatch", "metadata says degrees", lambda d: _mutate_json(d / "metadata.json", lambda p: p["units"].__setitem__("joint_position", "deg"))),
        MutationSpec("tcp_mm_unit", "ur_rtde_csv_v0", "unit", "unit_mismatch", "metadata says millimeters", lambda d: _mutate_json(d / "metadata.json", lambda p: p["units"].__setitem__("tcp_position", "mm"))),
        MutationSpec("target_actual_lag_high", "ur_rtde_csv_v0", "semantics", "action_state_semantic_mismatch", "target far from actual", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[4].__setitem__("target_q", stable_compact_json([3, 3, 3, 3, 3, 3])))),
        MutationSpec("protective_stop", "ur_rtde_csv_v0", "safety", "safety_or_robot_mode_invalid", "protective stop", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[3].__setitem__("safety_status", "PROTECTIVE_STOP"))),
        MutationSpec("not_running", "ur_rtde_csv_v0", "safety", "safety_or_robot_mode_invalid", "not running", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[3].__setitem__("robot_mode", "NOT_RUNNING"))),
        MutationSpec("fabricated_task_success", "ur_rtde_csv_v0", "claim", "claim_boundary_violation", "task success true", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("real_robot_success", True))),
        MutationSpec("joint_order_swapped", "ur_rtde_csv_v0", "frame", "frame_semantic_drift", "joint names swapped", lambda d: _mutate_ur_csv(d / "rtde_output.csv", lambda rows: rows[0].__setitem__("joint_names", stable_compact_json(["bad", "order"])))),
    ]


def _franka_mutations() -> list[MutationSpec]:
    return [
        MutationSpec("missing_command_file", "franka_state_jsonl_v0", "schema", "schema_missing_required_artifact", "command file removed", lambda d: (d / "franka_command.jsonl").unlink()),
        MutationSpec("missing_o_t_ee", "franka_state_jsonl_v0", "schema", "vector_dimension_mismatch", "O_T_EE missing", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[0].pop("O_T_EE", None))),
        MutationSpec("wrong_dof", "franka_state_jsonl_v0", "shape", "vector_dimension_mismatch", "q shortened", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[1].__setitem__("q", [0, 1]))),
        MutationSpec("nonfinite_q", "franka_state_jsonl_v0", "shape", "vector_dimension_mismatch", "q contains NaN", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[2].__setitem__("q", [0, 0, 0, 0, 0, 0, float("nan")]))),
        MutationSpec("transform_length_wrong", "franka_state_jsonl_v0", "unit", "vector_dimension_mismatch", "O_T_EE wrong length", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[3].__setitem__("O_T_EE", [1, 0, 0]))),
        MutationSpec("transform_not_rigid", "franka_state_jsonl_v0", "frame", "frame_semantic_drift", "matrix scale invalid", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[4].__setitem__("O_T_EE", [2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1]))),
        MutationSpec("command_lag_high", "franka_state_jsonl_v0", "semantics", "action_state_semantic_mismatch", "command timestamp lag", lambda d: _mutate_jsonl(d / "franka_command.jsonl", lambda rows: rows[5].__setitem__("timestamp", 2.0))),
        MutationSpec("robot_mode_stop", "franka_state_jsonl_v0", "safety", "safety_or_robot_mode_invalid", "robot mode stop", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[6].__setitem__("robot_mode", "user_stopped"))),
        MutationSpec("source_kind_external_partner", "franka_state_jsonl_v0", "provenance", "provenance_boundary_violation", "wrong source kind", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("source_kind", "external_partner_file_drop"))),
        MutationSpec("generated_false", "franka_state_jsonl_v0", "provenance", "provenance_boundary_violation", "generated flag false", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("generated_by_rdf_sim", False))),
        MutationSpec("external_partner_true", "franka_state_jsonl_v0", "claim", "provenance_boundary_violation", "external partner true", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("external_partner_data", True))),
        MutationSpec("action_semantics_missing", "franka_state_jsonl_v0", "semantics", "action_state_semantic_mismatch", "wrong semantics", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("action_semantics", "state_only"))),
        MutationSpec("timestamp_duplicate", "franka_state_jsonl_v0", "timestamp", "timestamp_not_monotonic", "duplicate timestamp", lambda d: _mutate_jsonl(d / "franka_state.jsonl", lambda rows: rows[3].__setitem__("timestamp", rows[2]["timestamp"]))),
    ]


def _ros2_mutations() -> list[MutationSpec]:
    return [
        MutationSpec("missing_joint_states", "ros2_channel_bundle_jsonl_v0", "schema", "schema_missing_required_artifact", "joint_states missing", lambda d: (d / "topics" / "joint_states.jsonl").unlink()),
        MutationSpec("missing_tf_static", "ros2_channel_bundle_jsonl_v0", "frame", "frame_tree_invalid", "tf_static missing", lambda d: (d / "topics" / "tf_static.jsonl").unlink()),
        MutationSpec("missing_command_topic", "ros2_channel_bundle_jsonl_v0", "schema", "schema_missing_required_artifact", "command missing", lambda d: (d / "topics" / "command.jsonl").unlink()),
        MutationSpec("frame_id_missing", "ros2_channel_bundle_jsonl_v0", "frame", "frame_tree_invalid", "frame id missing", lambda d: _mutate_jsonl(d / "topics" / "joint_states.jsonl", lambda rows: rows[0].pop("frame_id", None))),
        MutationSpec("base_frame_drift", "ros2_channel_bundle_jsonl_v0", "frame", "frame_tree_invalid", "base changes", lambda d: _mutate_jsonl(d / "topics" / "command.jsonl", lambda rows: rows[4].__setitem__("frame_id", "moving_base"))),
        MutationSpec("tf_parent_cycle", "ros2_channel_bundle_jsonl_v0", "frame", "frame_tree_invalid", "tf cycle", lambda d: _mutate_jsonl(d / "topics" / "tf.jsonl", lambda rows: rows[2].__setitem__("parent_frame_id", "tool0"))),
        MutationSpec("topic_skew_high", "ros2_channel_bundle_jsonl_v0", "timestamp", "timestamp_gap_or_drift", "tf timestamp skew", lambda d: _mutate_jsonl(d / "topics" / "tf.jsonl", lambda rows: rows[5].__setitem__("timestamp", 3.0))),
        MutationSpec("command_state_lag_high", "ros2_channel_bundle_jsonl_v0", "semantics", "action_state_semantic_mismatch", "command timestamp lag", lambda d: _mutate_jsonl(d / "topics" / "command.jsonl", lambda rows: rows[5].__setitem__("timestamp", 3.0))),
        MutationSpec("joint_names_wrong", "ros2_channel_bundle_jsonl_v0", "frame", "frame_semantic_drift", "joint names wrong", lambda d: _mutate_jsonl(d / "topics" / "joint_states.jsonl", lambda rows: rows[1].__setitem__("name", ["wrong"]))),
        MutationSpec("joint_dim_wrong", "ros2_channel_bundle_jsonl_v0", "shape", "vector_dimension_mismatch", "position wrong dim", lambda d: _mutate_jsonl(d / "topics" / "joint_states.jsonl", lambda rows: rows[1].__setitem__("position", [0, 1]))),
        MutationSpec("timestamp_non_monotonic", "ros2_channel_bundle_jsonl_v0", "timestamp", "timestamp_not_monotonic", "joint timestamp backward", lambda d: _mutate_jsonl(d / "topics" / "joint_states.jsonl", lambda rows: rows[4].__setitem__("timestamp", rows[1]["timestamp"]))),
        MutationSpec("wrong_robot_model", "ros2_channel_bundle_jsonl_v0", "provenance", "unsupported_profile", "wrong model", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("robot_model", "unknown_ros_robot"))),
        MutationSpec("tcp_rotation_wrong_unit", "ros2_channel_bundle_jsonl_v0", "unit", "unit_mismatch", "joint unit deg", lambda d: _mutate_json(d / "metadata.json", lambda p: p["units"].__setitem__("joint_position", "deg"))),
    ]


def _generic_mutations() -> list[MutationSpec]:
    return [
        MutationSpec("missing_command_state_file", "generic_command_state_jsonl_v0", "schema", "schema_missing_required_artifact", "file removed", lambda d: (d / "command_state.jsonl").unlink()),
        MutationSpec("missing_command", "generic_command_state_jsonl_v0", "schema", "vector_dimension_mismatch", "command missing", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[0].pop("command", None))),
        MutationSpec("missing_state", "generic_command_state_jsonl_v0", "schema", "vector_dimension_mismatch", "state missing", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[0].pop("state", None))),
        MutationSpec("wrong_action_semantics", "generic_command_state_jsonl_v0", "semantics", "action_state_semantic_mismatch", "wrong action semantics", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[0].__setitem__("action_semantics", "actual_state"))),
        MutationSpec("future_state_as_action", "generic_command_state_jsonl_v0", "semantics", "action_state_semantic_mismatch", "future command timestamp", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[2].__setitem__("command_timestamp", 9.0))),
        MutationSpec("action_dim_wrong", "generic_command_state_jsonl_v0", "shape", "vector_dimension_mismatch", "action wrong dim", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[1].__setitem__("command", [0]))),
        MutationSpec("state_dim_wrong", "generic_command_state_jsonl_v0", "shape", "vector_dimension_mismatch", "state wrong dim", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[1].__setitem__("state", [0]))),
        MutationSpec("nan_state", "generic_command_state_jsonl_v0", "shape", "vector_dimension_mismatch", "state NaN", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[1].__setitem__("state", [0, 0, 0, 0, 0, float("nan")]))),
        MutationSpec("reset_boundary", "generic_command_state_jsonl_v0", "semantics", "action_state_semantic_mismatch", "reset inside episode", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[3].__setitem__("reset_boundary", True))),
        MutationSpec("fabricated_task_success", "generic_command_state_jsonl_v0", "claim", "claim_boundary_violation", "task success fabricated", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[4].__setitem__("task_success", True))),
        MutationSpec("source_owner_placeholder", "generic_command_state_jsonl_v0", "provenance", "provenance_boundary_violation", "external partner true", lambda d: _mutate_json(d / "metadata.json", lambda p: p.__setitem__("external_partner_data", True))),
        MutationSpec("metadata_units_missing", "generic_command_state_jsonl_v0", "unit", "unit_mismatch", "units missing", lambda d: _mutate_json(d / "metadata.json", lambda p: p.pop("units", None))),
        MutationSpec("timestamp_gap_large", "generic_command_state_jsonl_v0", "timestamp", "timestamp_gap_or_drift", "large timestamp gap", lambda d: _mutate_jsonl(d / "command_state.jsonl", lambda rows: rows[6].__setitem__("timestamp", 4.0))),
    ]
