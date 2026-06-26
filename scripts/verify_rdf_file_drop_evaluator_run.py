#!/usr/bin/env python3
"""Verify an RDF file-drop evaluator run package from included evidence.

The verifier intentionally does not import producer service modules. It
recomputes the evaluator verdict from source_drop, normalized_contract, export
receipts, and buyer-facing reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any


PROFILE_REGISTRY: dict[str, dict[str, Any]] = {
    "ur_rtde_csv_v0": {
        "robot_family": "universal_robots",
        "robot_model": "ur10e",
        "dof": 6,
        "joint_names": [
            "shoulder_pan_joint",
            "shoulder_lift_joint",
            "elbow_joint",
            "wrist_1_joint",
            "wrist_2_joint",
            "wrist_3_joint",
        ],
        "source_files": ["metadata.json", "rtde_output.csv"],
        "action_semantics": "target_q_command",
        "state_semantics": "actual_q_state",
    },
    "franka_state_jsonl_v0": {
        "robot_family": "franka",
        "robot_model": "panda",
        "dof": 7,
        "joint_names": [
            "panda_joint1",
            "panda_joint2",
            "panda_joint3",
            "panda_joint4",
            "panda_joint5",
            "panda_joint6",
            "panda_joint7",
        ],
        "source_files": ["metadata.json", "franka_state.jsonl", "franka_command.jsonl"],
        "action_semantics": "q_d_command",
        "state_semantics": "q_actual_state",
    },
    "ros2_channel_bundle_jsonl_v0": {
        "robot_family": "ros2_simulated_manipulator",
        "robot_model": "ur10e_channel_bundle",
        "dof": 6,
        "joint_names": [
            "shoulder_pan_joint",
            "shoulder_lift_joint",
            "elbow_joint",
            "wrist_1_joint",
            "wrist_2_joint",
            "wrist_3_joint",
        ],
        "source_files": [
            "metadata.json",
            "topic_manifest.json",
            "topics/joint_states.jsonl",
            "topics/tf.jsonl",
            "topics/tf_static.jsonl",
            "topics/command.jsonl",
        ],
        "action_semantics": "command_topic_target_joint_state",
        "state_semantics": "joint_states_topic_actual_state",
    },
    "generic_command_state_jsonl_v0": {
        "robot_family": "generic_manipulator",
        "robot_model": "generic_6dof_command_state",
        "dof": 6,
        "joint_names": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"],
        "source_files": ["metadata.json", "command_state.jsonl"],
        "action_semantics": "explicit_command_vector",
        "state_semantics": "explicit_state_vector",
    },
}
SOURCE_METADATA_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_source_metadata_v0.1.0"

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
NON_CLAIMS = {
    "external_partner_data_evaluated": False,
    "real_robot_data_evaluated": False,
    "real_robot_success": False,
    "hardware_readiness": False,
    "live_ur_rtde_support": False,
    "live_franka_support": False,
    "live_ros2_bridge_readiness": False,
    "policy_uplift": False,
    "production_readiness": False,
}
FORBIDDEN_CLAIM_KEYS = set(NON_CLAIMS) | {
    "physical_robot_readiness",
    "deployable_policy_readiness",
    "visual_policy_performance",
    "hmd_openxr_readiness",
    "marketplace_readiness",
    "production_certification",
    "sim_to_real_proven",
    "general_robot_intelligence",
}
CLAIM_FILE_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".html"}
FORBIDDEN_KEY_POSITIVE_VALUE = r"(?:is\s+)?(?:true|yes|ready|validated|evaluated|proven|supported|enabled|closed)\b"
POSITIVE_STRUCTURED_VALUES = {"1", "closed", "enabled", "evaluated", "proven", "ready", "supported", "true", "validated", "yes"}
NEGATION_WORD_RE = re.compile(r"\b(no|not|never|without|does not|do not|is not|are not)\b")
CONTRAST_PIVOT_RE = re.compile(r"\b(but|however|yet|nevertheless|nonetheless|although|though)\b")
POSITIVE_FORBIDDEN_PATTERNS = (
    r"\breal robot ready\b",
    r"\breal robot success\b",
    r"\bphysical robot readiness\b",
    r"\bhardware readiness\b",
    r"\bhardware validated\b",
    r"\bproduction ready\b",
    r"\bproduction readiness\b",
    r"\bproduction certification\b",
    r"\bexternal partner data evaluated\b",
    r"\blive ur support\b",
    r"\blive franka support\b",
    r"\blive ros2 bridge readiness\b",
    r"\bpolicy uplift\b",
    r"\bvisual policy performance\b",
    r"\bmarketplace readiness\b",
    r"\bsim to real proven\b",
    r"\bgeneral robot intelligence\b",
)
MAX_TIMESTAMP_GAP_SECONDS = 0.08
MAX_ACTION_STATE_LAG = 0.05
EXCLUDED_INDEX_FILES = {"package_manifest.json", "verifier_result.json"}


class VerifyError(Exception):
    def __init__(self, check: str, detail: str) -> None:
        self.check = check
        self.detail = detail
        super().__init__(f"{check}: {detail}")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} contains non-object JSONL row")
        rows.append(payload)
    return rows


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def safe_path(root: Path, rel: str) -> Path:
    if rel.startswith("/") or "\\" in rel or any(part in {"", ".."} for part in Path(rel).parts):
        raise VerifyError("unsafe_package_path", rel)
    path = root / rel
    if not is_within(path, root):
        raise VerifyError("unsafe_package_path", rel)
    return path


def source_hashes(source_root: Path) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for path in sorted(source_root.rglob("*")):
        if path.is_symlink():
            raise VerifyError("unsafe_package_path", f"symlink: {path}")
        if path.is_file():
            rel = path.relative_to(source_root).as_posix()
            hashes[rel] = {"sha256": sha256_file(path), "byte_size": path.stat().st_size}
    return hashes


def load_manifest(manifest_or_dir: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = manifest_or_dir / "package_manifest.json" if manifest_or_dir.is_dir() else manifest_or_dir
    if not manifest_path.exists():
        raise VerifyError("manifest_missing", str(manifest_path))
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise VerifyError("manifest_invalid", str(manifest_path))
    return manifest_path.parent, manifest


def verify_artifact_index(run_dir: Path, manifest: dict[str, Any]) -> None:
    index = manifest.get("artifact_index")
    if not isinstance(index, list):
        raise VerifyError("artifact_index_invalid", "artifact_index missing")
    indexed: dict[str, dict[str, Any]] = {}
    for entry in index:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise VerifyError("artifact_index_invalid", "entry invalid")
        rel = entry["path"]
        if rel in indexed:
            raise VerifyError("artifact_index_invalid", f"duplicate path {rel}")
        path = safe_path(run_dir, rel)
        if not path.exists() or not path.is_file():
            raise VerifyError("artifact_hash_mismatch", f"missing indexed file {rel}")
        if entry.get("sha256") != sha256_file(path) or entry.get("byte_size") != path.stat().st_size:
            raise VerifyError("artifact_hash_mismatch", rel)
        indexed[rel] = entry
    actual = {
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.relative_to(run_dir).as_posix() not in EXCLUDED_INDEX_FILES
    }
    if set(indexed) != actual:
        raise VerifyError("artifact_index_completeness_mismatch", f"indexed={len(indexed)} actual={len(actual)}")


def parse_array(value: Any, issues: list[str]) -> list[Any]:
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


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def float_or_nan(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return math.nan
    return numeric if math.isfinite(numeric) else math.nan


def numeric_vector(value: Any, size: int) -> bool:
    return isinstance(value, list) and len(value) == size and all(finite_number(item) for item in value)


def vector_distance(left: Any, right: Any) -> float:
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
        return math.inf
    try:
        return max(abs(float(a) - float(b)) for a, b in zip(left, right, strict=True))
    except (TypeError, ValueError):
        return math.inf


def rigid_transform_plausible(matrix: Any) -> bool:
    if not numeric_vector(matrix, 16):
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


def dedupe(issues: list[str]) -> list[str]:
    return [reason for reason in REJECTION_REASONS if reason in set(issues)]


def validate_metadata(metadata: dict[str, Any], profile_id: str) -> list[str]:
    spec = PROFILE_REGISTRY[profile_id]
    issues: list[str] = []
    required = (
        "schema_version",
        "profile_id",
        "source_kind",
        "generated_by_rdf_sim",
        "external_partner_data",
        "robot_family",
        "robot_model",
        "dof",
        "joint_names",
        "units",
        "action_semantics",
        "state_semantics",
    )
    for key in required:
        if key not in metadata:
            issues.append("schema_missing_required_field")
    if metadata.get("schema_version") != SOURCE_METADATA_SCHEMA_VERSION:
        issues.append("schema_type_mismatch")
    if metadata.get("profile_id") != profile_id:
        issues.append("unsupported_profile")
    if metadata.get("source_kind") != "digital_twin_rehearsal_log":
        issues.append("provenance_boundary_violation")
    if metadata.get("generated_by_rdf_sim") is not True:
        issues.append("provenance_boundary_violation")
    if metadata.get("external_partner_data") is not False or metadata.get("external_data_evaluated") is True:
        issues.append("provenance_boundary_violation")
    if metadata.get("external_partner_data") is True or metadata.get("external_data_evaluated") is True:
        issues.append("claim_boundary_violation")
    if metadata.get("robot_family") != spec["robot_family"] or metadata.get("robot_model") != spec["robot_model"]:
        issues.append("unsupported_profile")
    if metadata.get("dof") != spec["dof"] or metadata.get("joint_names") != spec["joint_names"]:
        issues.append("vector_dimension_mismatch")
    units = metadata.get("units")
    if not isinstance(units, dict) or units.get("joint_position") != "rad":
        issues.append("unit_mismatch")
    if profile_id == "ur_rtde_csv_v0" and isinstance(units, dict):
        if units.get("tcp_position") != "m" or units.get("tcp_rotation") != "rotation_vector_rad":
            issues.append("unit_mismatch")
    if metadata.get("action_semantics") != spec["action_semantics"] or metadata.get("state_semantics") != spec["state_semantics"]:
        issues.append("action_state_semantic_mismatch")
    for key in NON_CLAIMS:
        if metadata.get(key) is True:
            issues.append("claim_boundary_violation")
    return issues


def parse_ur_csv(source_root: Path, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    path = source_root / "rtde_output.csv"
    if not path.exists():
        return [], ["schema_missing_required_artifact"]
    issues: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        rows = list(reader)
    required = {"timestamp", "joint_names", "actual_q", "target_q", "actual_TCP_pose", "target_TCP_pose", "actual_TCP_speed", "robot_mode", "safety_status"}
    if fieldnames != required:
        issues.append("schema_missing_required_field")
    output: list[dict[str, Any]] = []
    for raw in rows:
        if any(raw.get(field) in (None, "") for field in required):
            issues.append("schema_missing_required_field")
        timestamp = float_or_nan(raw.get("timestamp"))
        joint_names = parse_array(raw.get("joint_names"), issues)
        actual_q = parse_array(raw.get("actual_q"), issues)
        target_q = parse_array(raw.get("target_q"), issues)
        actual_tcp = parse_array(raw.get("actual_TCP_pose"), issues)
        target_tcp = parse_array(raw.get("target_TCP_pose"), issues)
        speed = parse_array(raw.get("actual_TCP_speed"), issues)
        if joint_names != spec["joint_names"]:
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
    return output, dedupe(issues)


def parse_franka(source_root: Path, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    state_rows = read_jsonl(source_root / "franka_state.jsonl") if (source_root / "franka_state.jsonl").exists() else []
    command_rows = read_jsonl(source_root / "franka_command.jsonl") if (source_root / "franka_command.jsonl").exists() else []
    if not state_rows or not command_rows:
        issues.append("schema_missing_required_artifact")
    if len(state_rows) != len(command_rows):
        issues.append("timestamp_gap_or_drift")
    rows = [
        {
            "timestamp": float_or_nan(state.get("timestamp")),
            "state_vector": state.get("q"),
            "action_vector": command.get("q_d"),
            "q": state.get("q"),
            "q_d": command.get("q_d"),
            "O_T_EE": state.get("O_T_EE"),
            "O_T_EE_d": command.get("O_T_EE_d"),
            "robot_mode": state.get("robot_mode"),
            "command_timestamp": float_or_nan(command.get("timestamp")),
        }
        for state, command in zip(state_rows, command_rows, strict=False)
    ]
    return rows, dedupe(issues)


def parse_ros2(source_root: Path, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    manifest_path = source_root / "topic_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    if set(manifest.get("topics") or []) != {"/joint_states", "/tf", "/tf_static", "/command"}:
        issues.append("schema_missing_required_artifact")
    joint_rows = read_jsonl(source_root / "topics" / "joint_states.jsonl") if (source_root / "topics" / "joint_states.jsonl").exists() else []
    tf_rows = read_jsonl(source_root / "topics" / "tf.jsonl") if (source_root / "topics" / "tf.jsonl").exists() else []
    tf_static = read_jsonl(source_root / "topics" / "tf_static.jsonl") if (source_root / "topics" / "tf_static.jsonl").exists() else []
    command_rows = read_jsonl(source_root / "topics" / "command.jsonl") if (source_root / "topics" / "command.jsonl").exists() else []
    for rel_path in ("topics/joint_states.jsonl", "topics/tf.jsonl", "topics/tf_static.jsonl", "topics/command.jsonl"):
        if not (source_root / rel_path).exists():
            issues.append("schema_missing_required_artifact")
    if not tf_static:
        issues.append("frame_tree_invalid")
    if len({len(joint_rows), len(tf_rows), len(command_rows)}) != 1:
        issues.append("timestamp_gap_or_drift")
    rows = [
        {
            "timestamp": float_or_nan(joint.get("timestamp")),
            "state_vector": joint.get("position"),
            "action_vector": command.get("target_position"),
            "joint_names": joint.get("name"),
            "frame_id": joint.get("frame_id"),
            "tf_parent": tf.get("parent_frame_id"),
            "tf_child": tf.get("child_frame_id"),
            "tf_timestamp": float_or_nan(tf.get("timestamp")),
            "command_timestamp": float_or_nan(command.get("timestamp")),
            "command_frame_id": command.get("frame_id"),
        }
        for joint, tf, command in zip(joint_rows, tf_rows, command_rows, strict=False)
    ]
    return rows, dedupe(issues)


def parse_generic(source_root: Path, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    path = source_root / "command_state.jsonl"
    if not path.exists():
        return [], ["schema_missing_required_artifact"]
    rows = [
        {
            "timestamp": float_or_nan(row.get("timestamp")),
            "state_vector": row.get("state"),
            "action_vector": row.get("command"),
            "command_timestamp": float_or_nan(row.get("command_timestamp")),
            "state_timestamp": float_or_nan(row.get("state_timestamp")),
            "action_semantics": row.get("action_semantics"),
            "state_semantics": row.get("state_semantics"),
            "reset_boundary": row.get("reset_boundary"),
            "task_success": row.get("task_success"),
        }
        for row in read_jsonl(path)
    ]
    return rows, []


def validate_common(rows: list[dict[str, Any]], spec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if len(rows) < 12:
        issues.append("timestamp_gap_or_drift")
    previous: float | None = None
    for row in rows:
        timestamp = row.get("timestamp")
        if not finite_number(timestamp):
            issues.append("schema_type_mismatch")
        elif previous is not None:
            if float(timestamp) <= previous:
                issues.append("timestamp_not_monotonic")
            if float(timestamp) - previous > MAX_TIMESTAMP_GAP_SECONDS:
                issues.append("timestamp_gap_or_drift")
            previous = float(timestamp)
        else:
            previous = float(timestamp)
        if not numeric_vector(row.get("state_vector"), spec["dof"]):
            issues.append("vector_dimension_mismatch")
        if not numeric_vector(row.get("action_vector"), spec["dof"]):
            issues.append("vector_dimension_mismatch")
    return issues


def validate_semantics(profile_id: str, rows: list[dict[str, Any]], spec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for row in rows:
        if profile_id == "ur_rtde_csv_v0":
            if row.get("robot_mode") != "RUNNING" or row.get("safety_status") != "NORMAL":
                issues.append("safety_or_robot_mode_invalid")
            if not numeric_vector(row.get("actual_TCP_pose"), 6) or not numeric_vector(row.get("target_TCP_pose"), 6):
                issues.append("vector_dimension_mismatch")
            if vector_distance(row.get("actual_q"), row.get("target_q")) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        elif profile_id == "franka_state_jsonl_v0":
            if row.get("robot_mode") != "move":
                issues.append("safety_or_robot_mode_invalid")
            if not numeric_vector(row.get("O_T_EE"), 16) or not numeric_vector(row.get("O_T_EE_d"), 16):
                issues.append("vector_dimension_mismatch")
            elif not rigid_transform_plausible(row["O_T_EE"]):
                issues.append("frame_semantic_drift")
            if abs(float(row.get("command_timestamp", math.nan)) - float(row.get("timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        elif profile_id == "ros2_channel_bundle_jsonl_v0":
            if row.get("joint_names") != spec["joint_names"]:
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
            if row.get("action_semantics") != spec["action_semantics"] or row.get("state_semantics") != spec["state_semantics"]:
                issues.append("action_state_semantic_mismatch")
            if row.get("reset_boundary") is True:
                issues.append("action_state_semantic_mismatch")
            if row.get("task_success") is not None:
                issues.append("claim_boundary_violation")
            if abs(float(row.get("command_timestamp", math.nan)) - float(row.get("state_timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
            if row.get("command_timestamp", 0) > row.get("state_timestamp", 0):
                issues.append("action_state_semantic_mismatch")
    return issues


def validate_source_drop(source_root: Path, expected_profile_id: str) -> dict[str, Any]:
    metadata_path = source_root / "metadata.json"
    initial_issues: list[str] = []
    if not metadata_path.exists():
        metadata = {}
        initial_issues.append("schema_missing_required_artifact")
    else:
        metadata = read_json(metadata_path)
    if not isinstance(metadata, dict):
        return {
            "profile_id": expected_profile_id,
            "observed_profile_id": expected_profile_id,
            "passed": False,
            "rejection_reasons": ["schema_type_mismatch"],
            "frame_count": 0,
            "export_eligible": False,
            "trainer_smoke_eligible": False,
            "rows": [],
        }
    profile_id = str(metadata.get("profile_id") or expected_profile_id)
    if profile_id != expected_profile_id or profile_id not in PROFILE_REGISTRY:
        return {
            "profile_id": expected_profile_id,
            "observed_profile_id": profile_id,
            "passed": False,
            "rejection_reasons": ["unsupported_profile"],
            "frame_count": 0,
            "export_eligible": False,
            "trainer_smoke_eligible": False,
            "rows": [],
        }
    spec = PROFILE_REGISTRY[profile_id]
    issues = [*initial_issues, *validate_metadata(metadata, profile_id)]
    if profile_id == "ur_rtde_csv_v0":
        rows, parse_issues = parse_ur_csv(source_root, spec)
    elif profile_id == "franka_state_jsonl_v0":
        rows, parse_issues = parse_franka(source_root, spec)
    elif profile_id == "ros2_channel_bundle_jsonl_v0":
        rows, parse_issues = parse_ros2(source_root, spec)
    else:
        rows, parse_issues = parse_generic(source_root, spec)
    issues.extend(parse_issues)
    issues.extend(validate_common(rows, spec))
    issues.extend(validate_semantics(profile_id, rows, spec))
    reasons = dedupe(issues)
    return {
        "profile_id": profile_id,
        "observed_profile_id": profile_id,
        "passed": not reasons,
        "rejection_reasons": reasons,
        "frame_count": len(rows),
        "export_eligible": not reasons,
        "trainer_smoke_eligible": not reasons,
        "rows": rows if not reasons else [],
    }


def normalized_contract_for(profile_id: str, computed: dict[str, Any]) -> dict[str, Any]:
    spec = PROFILE_REGISTRY[profile_id]
    rows = computed["rows"] if computed["passed"] else []
    return {
        "schema_version": "rdf_mvp5b_file_drop_normalized_contract_v0.1.0",
        "profile_id": profile_id,
        "passed": computed["passed"],
        "frame_count": computed["frame_count"],
        "state_dim": spec["dof"],
        "action_dim": spec["dof"],
        "action_semantics": spec["action_semantics"],
        "state_semantics": spec["state_semantics"],
        "export_eligible": computed["export_eligible"],
        "trainer_smoke_eligible": computed["trainer_smoke_eligible"],
        "rows": [
            {
                "timestamp": row["timestamp"],
                "state_vector": row["state_vector"],
                "action_vector": row["action_vector"],
            }
            for row in rows
        ],
    }


def expected_evaluation_result(profile_id: str, computed: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp5b_file_drop_evaluation_result_v0.1.0",
        "profile_id": profile_id,
        "observed_profile_id": computed["observed_profile_id"],
        "passed": computed["passed"],
        "frame_count": computed["frame_count"],
        "rejection_reasons": computed["rejection_reasons"],
        "export_eligible": computed["export_eligible"],
        "trainer_smoke_eligible": computed["trainer_smoke_eligible"],
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
        "non_claims": dict(NON_CLAIMS),
    }


def require_rejection_reasons(payload: dict[str, Any], *, check: str, source: str) -> list[str]:
    reasons = payload.get("rejection_reasons")
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        raise VerifyError(check, f"{source} rejection_reasons must be list[str]")
    return reasons


def verify_preflight_result(
    payload: dict[str, Any],
    *,
    profile_id: str,
    computed: dict[str, Any],
    source_hash_map: dict[str, dict[str, Any]],
) -> None:
    if payload.get("profile_id") != profile_id or payload.get("source_file_hashes") != source_hash_map:
        raise VerifyError("source_hash_mismatch", "preflight_result.json")
    expected = {
        "ok": computed["passed"],
        "passed": computed["passed"],
        "command": "preflight",
        "profile_id": profile_id,
        "observed_profile_id": computed["observed_profile_id"],
        "frame_count": computed["frame_count"],
        "export_eligible": computed["export_eligible"],
        "trainer_smoke_eligible": computed["trainer_smoke_eligible"],
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
        "hardware_readiness": False,
        "policy_uplift": False,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise VerifyError("preflight_result_mismatch", f"{key} differs from source recomputation")
    if require_rejection_reasons(payload, check="preflight_result_mismatch", source="preflight_result.json") != computed["rejection_reasons"]:
        raise VerifyError("preflight_result_mismatch", "rejection reasons differ from recomputed truth")


def verify_payloads(run_dir: Path, manifest: dict[str, Any], computed: dict[str, Any], source_hash_map: dict[str, dict[str, Any]]) -> None:
    profile_id = manifest.get("profile_id")
    if profile_id != computed["profile_id"]:
        raise VerifyError("profile_mismatch", f"{profile_id} != {computed['profile_id']}")
    input_receipt = read_json(run_dir / "input_receipt.json")
    if input_receipt.get("profile_id") != profile_id or input_receipt.get("source_file_hashes") != source_hash_map:
        raise VerifyError("source_hash_mismatch", "input_receipt.json")
    preflight_result = read_json(run_dir / "preflight_result.json")
    verify_preflight_result(
        preflight_result,
        profile_id=str(profile_id),
        computed=computed,
        source_hash_map=source_hash_map,
    )
    for rel, payload in (("input_receipt.json", input_receipt), ("preflight_result.json", preflight_result)):
        for key, expected in NON_CLAIMS.items():
            if payload.get(key) is True or (
                isinstance(payload.get("non_claims"), dict) and payload["non_claims"].get(key) is not expected
            ):
                raise VerifyError("non_claim_boundary_mismatch", rel)
    expected_contract = normalized_contract_for(str(profile_id), computed)
    if read_json(run_dir / "normalized" / "normalized_contract.json") != expected_contract:
        raise VerifyError("normalized_contract_mismatch", "normalized contract differs from source recomputation")
    actual_eval = read_json(run_dir / "evaluation_result.json")
    if not isinstance(actual_eval, dict):
        raise VerifyError("evaluation_summary_mismatch", "evaluation_result.json is not an object")
    if (
        actual_eval.get("profile_id") != profile_id
        or actual_eval.get("passed") != computed["passed"]
        or actual_eval.get("frame_count") != computed["frame_count"]
        or actual_eval.get("export_eligible") != computed["export_eligible"]
        or actual_eval.get("trainer_smoke_eligible") != computed["trainer_smoke_eligible"]
    ):
        raise VerifyError("evaluation_summary_mismatch", "evaluation_result.json is not recomputed truth")
    actual_reasons = require_rejection_reasons(actual_eval, check="evaluation_summary_mismatch", source="evaluation_result.json")
    if actual_reasons != computed["rejection_reasons"]:
        raise VerifyError("evaluation_summary_mismatch", "rejection reasons differ from recomputed truth")
    if manifest.get("passed") != computed["passed"] or manifest.get("external_partner_data_evaluated") is not False:
        raise VerifyError("manifest_claim_mismatch", "manifest verdict boundary mismatch")
    buyer_report = read_json(run_dir / "reports" / "buyer_report.json")
    if not isinstance(buyer_report, dict):
        raise VerifyError("buyer_report_mismatch", "buyer_report.json is not an object")
    if (
        buyer_report.get("profile_id") != profile_id
        or buyer_report.get("passed") != computed["passed"]
        or buyer_report.get("frame_count") != computed["frame_count"]
        or buyer_report.get("proof_source_of_truth") != "included_source_drop_and_independent_verifier"
    ):
        raise VerifyError("buyer_report_mismatch", "buyer_report.json differs from recomputed truth")
    buyer_report_reasons = require_rejection_reasons(buyer_report, check="buyer_report_mismatch", source="buyer_report.json")
    if buyer_report_reasons != computed["rejection_reasons"]:
        raise VerifyError("buyer_report_mismatch", "buyer_report.json rejection reasons differ from recomputed truth")
    for key, expected in NON_CLAIMS.items():
        if not isinstance(buyer_report.get("non_claims"), dict) or buyer_report["non_claims"].get(key) is not expected:
            raise VerifyError("buyer_report_mismatch", f"non-claim mismatch: {key}")
    html_path = run_dir / "reports" / "buyer_report.html"
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    expected_status = "Status: <strong>PASS</strong>" if computed["passed"] else "Status: <strong>REJECTED</strong>"
    forbidden_status = "Status: <strong>REJECTED</strong>" if computed["passed"] else "Status: <strong>PASS</strong>"
    required_html_snippets = (
        expected_status,
        f"Profile: <code>{profile_id}</code>",
        f"Frames: {computed['frame_count']}",
        "Evidence source of truth: included source_drop plus independent verifier recomputation.",
        "Boundary: pre-real-log digital-twin rehearsal only.",
    )
    if any(snippet not in html for snippet in required_html_snippets) or forbidden_status in html:
        raise VerifyError("buyer_report_mismatch", "buyer_report.html differs from recomputed truth")


def verify_hdf5(run_dir: Path, computed: dict[str, Any], *, deep_hdf5: bool) -> None:
    export_dir = run_dir / "export"
    hdf5_path = run_dir / "export" / "dataset.hdf5"
    if computed["passed"] and not hdf5_path.exists():
        raise VerifyError("export_missing", "accepted run must include HDF5 export")
    if not computed["export_eligible"] and export_dir.exists():
        raise VerifyError("export_not_allowed_for_rejected_run", "rejected run must not include training export artifacts")
    if hdf5_path.exists() and not deep_hdf5:
        raise VerifyError("deep_hdf5_required", "HDF5 export requires --deep-hdf5")
    if not hdf5_path.exists():
        return
    import h5py  # type: ignore[import-untyped]
    import numpy as np

    rows = computed["rows"]
    expected_states = np.asarray([row["state_vector"] for row in rows], dtype=np.float32)
    expected_actions = np.asarray([row["action_vector"] for row in rows], dtype=np.float32)
    expected_timestamps = np.asarray([row["timestamp"] for row in rows], dtype=np.float64)
    with h5py.File(hdf5_path, "r") as h5:
        states = h5["states"][:]
        actions = h5["actions"][:]
        timestamps = h5["timestamps"][:]
        if h5.attrs.get("profile_id") != computed["profile_id"]:
            raise VerifyError("hdf5_semantic_drift", "profile_id mismatch")
    if not (np.array_equal(states, expected_states) and np.array_equal(actions, expected_actions) and np.array_equal(timestamps, expected_timestamps)):
        raise VerifyError("hdf5_semantic_drift", "dataset arrays differ from recomputed rows")
    inspection = read_json(run_dir / "export" / "hdf5_inspection_report.json")
    trainer = read_json(run_dir / "export" / "trainer_smoke_report.json")
    if inspection.get("hdf5_sha256") != sha256_file(hdf5_path) or trainer.get("passed") is not True:
        raise VerifyError("hdf5_semantic_drift", "export reports mismatch")


def looks_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 128) : start]
    boundary = max(
        prefix.rfind("."),
        prefix.rfind("!"),
        prefix.rfind("?"),
        prefix.rfind("\n"),
        prefix.rfind("<p>"),
        prefix.rfind("</p>"),
        prefix.rfind("<br"),
    )
    if boundary >= 0:
        prefix = prefix[boundary + 1 :]
    negations = list(NEGATION_WORD_RE.finditer(prefix))
    if not negations:
        return False
    trailing_context = prefix[negations[-1].end() :]
    return not bool(CONTRAST_PIVOT_RE.search(trailing_context))


def forbidden_key_forms(key: str) -> set[str]:
    return {key, key.replace("_", " "), key.replace("_", "-")}


def is_positive_structured_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in POSITIVE_STRUCTURED_VALUES
    return False


def scan_structured_claim_value(value: Any, *, source: Path, run_dir: Path) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).strip().lower()
            for forbidden_key in FORBIDDEN_CLAIM_KEYS:
                if key_text in forbidden_key_forms(forbidden_key) and is_positive_structured_value(item):
                    raise VerifyError(
                        "forbidden_claim_leakage",
                        f"{forbidden_key} positive value in {source.relative_to(run_dir)}",
                    )
            scan_structured_claim_value(item, source=source, run_dir=run_dir)
    elif isinstance(value, list):
        for item in value:
            scan_structured_claim_value(item, source=source, run_dir=run_dir)


def scan_structured_claim_file(path: Path, run_dir: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            scan_structured_claim_value(json.loads(path.read_text(encoding="utf-8")), source=path, run_dir=run_dir)
        except json.JSONDecodeError:
            return
    elif suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                scan_structured_claim_value(json.loads(line), source=path, run_dir=run_dir)
            except json.JSONDecodeError:
                continue


def scan_claims(run_dir: Path) -> None:
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in CLAIM_FILE_SUFFIXES:
            continue
        scan_structured_claim_file(path, run_dir)
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for key in sorted(FORBIDDEN_CLAIM_KEYS):
            key_pattern = re.escape(key)
            spaced = re.escape(key.replace("_", " "))
            dashed = re.escape(key.replace("_", "-"))
            if re.search(rf'["\']?{key_pattern}["\']?\s*[:=]\s*(true|yes|1)\b', text):
                raise VerifyError("forbidden_claim_leakage", f"{key}=true in {path.relative_to(run_dir)}")
            for form in (key_pattern, spaced, dashed):
                for match in re.finditer(rf"\b{form}\b\s+{FORBIDDEN_KEY_POSITIVE_VALUE}", text):
                    if not looks_negated(text, match.start()):
                        raise VerifyError("forbidden_claim_leakage", f"{key} positive claim in {path.relative_to(run_dir)}")
            for form in (spaced, dashed):
                for match in re.finditer(rf"\b{form}\b", text):
                    if not looks_negated(text, match.start()):
                        raise VerifyError("forbidden_claim_leakage", f"{key} in {path.relative_to(run_dir)}")
        for pattern in POSITIVE_FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, text):
                if not looks_negated(text, match.start()):
                    raise VerifyError("forbidden_claim_leakage", f"{pattern} in {path.relative_to(run_dir)}")


def verify(manifest_or_dir: Path, *, deep_hdf5: bool) -> dict[str, Any]:
    run_dir, manifest = load_manifest(manifest_or_dir)
    verify_artifact_index(run_dir, manifest)
    scan_claims(run_dir)
    profile_id = manifest.get("profile_id")
    if not isinstance(profile_id, str) or profile_id not in PROFILE_REGISTRY:
        raise VerifyError("unsupported_profile", str(profile_id))
    source_root = run_dir / "source_drop"
    source_hash_map = source_hashes(source_root)
    computed = validate_source_drop(source_root, profile_id)
    verify_payloads(run_dir, manifest, computed, source_hash_map)
    verify_hdf5(run_dir, computed, deep_hdf5=deep_hdf5)
    return {
        "ok": True,
        "verdict": "VERIFIED",
        "profile_id": profile_id,
        "passed": computed["passed"],
        "frame_count": computed["frame_count"],
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
        "checks": [
            "artifact_index",
            "claim_scan",
            "source_hashes",
            "source_semantics",
            "evaluation_recompute",
            "normalized_contract",
            "hdf5_deep" if deep_hdf5 else "hdf5_deep_required_gate",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_or_run_dir")
    parser.add_argument("--deep-hdf5", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = verify(Path(args.manifest_or_run_dir), deep_hdf5=args.deep_hdf5)
        print(stable_json(payload))
        return 0
    except VerifyError as exc:
        print(
            stable_json(
                {
                    "ok": False,
                    "verdict": "FAILED",
                    "failed_checks": [exc.check],
                    "details": exc.detail,
                    "external_partner_data_evaluated": False,
                    "real_robot_data_evaluated": False,
                }
            )
        )
        return 1
    except Exception as exc:  # pragma: no cover - fail-closed guard
        print(
            stable_json(
                {
                    "ok": False,
                    "verdict": "FAILED",
                    "failed_checks": ["internal_error"],
                    "details": str(exc),
                    "external_partner_data_evaluated": False,
                    "real_robot_data_evaluated": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
