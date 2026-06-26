#!/usr/bin/env python3
"""Verify the MVP-5A-pre digital-twin file-drop chaos rehearsal package.

Default mode is stdlib-only and recomputes verdict-critical evidence from the
included package files.  HDF5 payload inspection is optional via --deep-hdf5.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any, cast


STATUS_CONTRACT_READY = "file_drop_rehearsal_contract_ready"
STATUS_READY = "file_drop_rehearsal_ready"
RUNTIME_CAPTURE_SCHEMA_VERSION = "rdf_mvp5a_pre_isaac_sim_runtime_capture_v0.1.0"
RUNTIME_CAPTURE_PROVENANCE_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_provenance_v0.1.0"
RAW_RUNTIME_EVENT_SCHEMA_VERSION = "rdf_mvp5a_pre_raw_runtime_event_v0.1.0"
RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_event_manifest_v0.1.0"
RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_reconstruction_receipt_v0.1.0"
PROCESS_PROVENANCE_RECEIPT_SCHEMA_VERSION = "rdf_mvp5a_pre_process_provenance_receipt_v0.1.0"
RUNTIME_RECONSTRUCTION_ALGORITHM = "rdf_mvp5a_pre_runtime_events_to_canonical_trace_v0.1.0"
RUNTIME_BACKED_SOURCE_KIND = "isaac_sim_runtime_backed_canonical_trace"
RUNTIME_BACKEND = "isaac_sim"
RUNTIME_CAPTURE_SCRIPT_ID = "mvp5a_pre_isaac_sim_canonical_trace_capture_v0"
RUNTIME_EVENT_CAPTURE_SCRIPT_ID = "mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0"
RUNTIME_EVENT_CAPTURE_EDGE_EVIDENCE_ORIGIN = "capture_edge_runtime_event_emitter"
RUNTIME_EVENT_CAPTURE_EDGE_PRODUCER_KIND = "capture_edge_emitter"
RUNTIME_EVENT_HELPER_EVIDENCE_ORIGIN = "canonical_trace_projection_helper"
RUNTIME_EVENT_HELPER_PRODUCER_KIND = "dev_fixture_helper"
RUNTIME_EVENT_HELPER_SOURCE_FUNCTION = "build_runtime_event_log_from_trace"
RUNTIME_SOURCE_PROCESS_KIND = "isaac_sim_process"
CAPTURE_EDGE_READY_CLOSE_ENABLED = False
CAPTURE_EDGE_READY_CLOSE_DISABLED_ISSUE = (
    "file_drop_rehearsal_ready close is disabled for PR #12 consistency baseline"
)
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
RUNTIME_PHASES = {"approach", "align", "insert", "insert_rehearsal", "settle", "retract"}
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

PROFILE_DOFS = {
    "ur_rtde_csv_v0": 6,
    "franka_state_jsonl_v0": 7,
    "ros2_channel_bundle_jsonl_v0": 6,
    "generic_command_state_jsonl_v0": 6,
}

PROFILE_JOINT_NAMES = {
    "ur_rtde_csv_v0": [
        "shoulder_pan_joint",
        "shoulder_lift_joint",
        "elbow_joint",
        "wrist_1_joint",
        "wrist_2_joint",
        "wrist_3_joint",
    ],
    "franka_state_jsonl_v0": [
        "panda_joint1",
        "panda_joint2",
        "panda_joint3",
        "panda_joint4",
        "panda_joint5",
        "panda_joint6",
        "panda_joint7",
    ],
    "ros2_channel_bundle_jsonl_v0": [
        "shoulder_pan_joint",
        "shoulder_lift_joint",
        "elbow_joint",
        "wrist_1_joint",
        "wrist_2_joint",
        "wrist_3_joint",
    ],
    "generic_command_state_jsonl_v0": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"],
}

PROFILE_ROBOT_METADATA = {
    "ur_rtde_csv_v0": ("universal_robots", "ur10e"),
    "franka_state_jsonl_v0": ("franka", "panda"),
    "ros2_channel_bundle_jsonl_v0": ("ros2_simulated_manipulator", "ur10e_channel_bundle"),
    "generic_command_state_jsonl_v0": ("generic_manipulator", "generic_6dof_command_state"),
}

PROFILE_SOURCE_FILES = {
    "ur_rtde_csv_v0": ["metadata.json", "rtde_output.csv"],
    "franka_state_jsonl_v0": ["metadata.json", "franka_state.jsonl", "franka_command.jsonl"],
    "ros2_channel_bundle_jsonl_v0": [
        "metadata.json",
        "topic_manifest.json",
        "topics/joint_states.jsonl",
        "topics/tf.jsonl",
        "topics/tf_static.jsonl",
        "topics/command.jsonl",
    ],
    "generic_command_state_jsonl_v0": ["metadata.json", "command_state.jsonl"],
}

PROFILE_ACTION_SEMANTICS = {
    "ur_rtde_csv_v0": "target_q_command",
    "franka_state_jsonl_v0": "q_d_command",
    "ros2_channel_bundle_jsonl_v0": "command_topic_target_joint_state",
    "generic_command_state_jsonl_v0": "explicit_command_vector",
}

PROFILE_STATE_SEMANTICS = {
    "ur_rtde_csv_v0": "actual_q_state",
    "franka_state_jsonl_v0": "q_actual_state",
    "ros2_channel_bundle_jsonl_v0": "joint_states_topic_actual_state",
    "generic_command_state_jsonl_v0": "explicit_state_vector",
}

PROFILE_REGISTRY_SCHEMA_VERSION = "rdf_mvp5a_pre_file_drop_profile_registry_v0.1.0"
CANONICAL_TRACE_SCHEMA_VERSION = "rdf_mvp5a_pre_canonical_trace_v0.1.0"

FORBIDDEN_CLAIMS = {
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
}

FORBIDDEN_POSITIVE_PHRASE_ALIASES = {
    "external partner log evaluated",
    "real robot ready",
    "hardware ready",
    "hardware validated",
    "marketplace ready",
    "production ready",
}
FORBIDDEN_POSITIVE_PHRASES = tuple(
    sorted({claim.replace("_", " ") for claim in FORBIDDEN_CLAIMS} | FORBIDDEN_POSITIVE_PHRASE_ALIASES)
)

REJECTION_REASONS = {
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
}


def verify_package(manifest_path: Path, *, allow_contract_ready: bool = False, deep_hdf5: bool = False) -> dict[str, Any]:
    issues: list[str] = []
    package_dir = manifest_path.parent.resolve()
    manifest = _read_json(manifest_path, issues, "package_manifest")

    _verify_manifest_index(package_dir, manifest.get("artifact_index"), issues)
    data_index = _read_json(package_dir / "data" / "artifact_index.json", issues, "data/artifact_index.json")
    _verify_data_index(package_dir, data_index.get("artifact_index"), issues)
    _scan_all_claims(package_dir, issues)
    _scan_spent_seeds(package_dir, issues)

    config = _read_json(package_dir / "data" / "config.json", issues, "data/config.json")
    registry = _read_json(package_dir / "data" / "profile_registry.json", issues, "data/profile_registry.json")
    non_claims = _read_json(package_dir / "data" / "non_claims_attestation.json", issues, "data/non_claims_attestation.json")
    canonical = _read_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", issues, "data/canonical_trace/canonical_trace.json")
    preflight = _read_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", issues, "data/canonical_trace/runtime_capture_preflight.json")
    receipt = _read_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", issues, "data/canonical_trace/runtime_capture_hash_receipt.json")
    golden = _read_json(package_dir / "data" / "ingest_results" / "golden_results.json", issues, "data/ingest_results/golden_results.json")
    corrupt = _read_json(package_dir / "data" / "ingest_results" / "corruption_matrix_results.json", issues, "data/ingest_results/corruption_matrix_results.json")
    coverage = _read_json(package_dir / "data" / "ingest_results" / "rejection_reason_coverage.json", issues, "data/ingest_results/rejection_reason_coverage.json")

    _verify_non_claims(manifest, config, non_claims, issues)
    _verify_status(package_dir, manifest, config, canonical, preflight, receipt, allow_contract_ready, issues)
    _verify_canonical_trace(canonical, receipt, issues)
    _verify_registry(registry, issues)
    _verify_hdf5_deep_requirement(package_dir, deep_hdf5, issues)
    _verify_golden_results(package_dir, golden, canonical, issues, deep_hdf5=deep_hdf5)
    _verify_corrupt_results(package_dir, corrupt, coverage, issues)
    _verify_summary_consistency(config, golden, corrupt, coverage, issues)

    return {
        "ok": not issues,
        "status": config.get("status"),
        "file_drop_rehearsal_ready": config.get("file_drop_rehearsal_ready"),
        "golden_profile_count": len(golden.get("results") or []),
        "corrupt_case_count": len(corrupt.get("results") or []),
        "issues": _dedupe(issues),
    }


def _verify_manifest_index(package_dir: Path, artifact_index: Any, issues: list[str]) -> None:
    if not isinstance(artifact_index, list):
        issues.append("package_manifest artifact_index must be list")
        return
    seen_paths: set[str] = set()
    seen_roles: set[str] = set()
    for entry in artifact_index:
        if not isinstance(entry, dict):
            issues.append("package_manifest artifact entry must be object")
            continue
        data_path_raw = entry.get("data_path")
        data_path = data_path_raw if isinstance(data_path_raw, str) else ""
        if not _safe_data_path(data_path):
            issues.append("artifact_index unsafe data_path")
            continue
        if data_path in seen_paths:
            issues.append(f"{data_path} duplicate artifact path")
        seen_paths.add(data_path)
        role = entry.get("artifact_role")
        if isinstance(role, str):
            if role in seen_roles:
                issues.append(f"{role} duplicate artifact role")
            seen_roles.add(role)
        path = package_dir / data_path
        if not _is_within(path, package_dir):
            issues.append(f"{data_path} symlink escapes package")
            continue
        if not path.is_file():
            issues.append(f"{data_path} missing")
            continue
        _verify_entry_hash(path, entry, data_path, issues)


def _verify_data_index(package_dir: Path, artifact_index: Any, issues: list[str]) -> None:
    if not isinstance(artifact_index, list):
        issues.append("data/artifact_index artifact_index must be list")
        return
    indexed = {entry.get("data_path") for entry in artifact_index if isinstance(entry, dict)}
    expected = {
        path.relative_to(package_dir).as_posix()
        for path in sorted((package_dir / "data").rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    }
    if indexed != expected:
        issues.append("data/artifact_index does not match data files")
    _verify_manifest_index(package_dir, artifact_index, issues)


def _verify_entry_hash(path: Path, entry: dict[str, Any], label: str, issues: list[str]) -> None:
    if entry.get("hash_convention") != "file_bytes":
        issues.append(f"{label} hash_convention mismatch")
    if entry.get("file_sha256") != _sha256_file(path):
        issues.append(f"{label} sha256 mismatch")
    if entry.get("byte_size") != path.stat().st_size:
        issues.append(f"{label} byte_size mismatch")


def _safe_data_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("data/"):
        return False
    pure = PurePosixPath(value)
    return not pure.is_absolute() and ".." not in pure.parts and pure.as_posix() == value


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _verify_non_claims(manifest: dict[str, Any], config: dict[str, Any], non_claims: dict[str, Any], issues: list[str]) -> None:
    payloads = {
        "package_manifest": manifest.get("non_claims"),
        "config": config.get("non_claims"),
        "non_claims_attestation": non_claims.get("non_claims"),
    }
    for label, payload in payloads.items():
        if set(payload or {}) != FORBIDDEN_CLAIMS:
            issues.append(f"{label} non_claim keys mismatch")
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in FORBIDDEN_CLAIMS and value is not False:
                    issues.append(f"{label} forbidden claim {key} must be false")
    _scan_forbidden_true_claims(manifest, "package_manifest", issues)
    _scan_forbidden_true_claims(config, "config", issues)
    _scan_forbidden_true_claims(non_claims, "non_claims_attestation", issues)


def _verify_status(
    package_dir: Path,
    manifest: dict[str, Any],
    config: dict[str, Any],
    canonical: dict[str, Any],
    preflight: dict[str, Any],
    receipt: dict[str, Any],
    allow_contract_ready: bool,
    issues: list[str],
) -> None:
    status = config.get("status")
    if manifest.get("package_status") != status:
        issues.append("package_manifest package_status mismatch")
    if manifest.get("file_drop_rehearsal_ready") != (status == STATUS_READY):
        issues.append("package_manifest file_drop_rehearsal_ready/status mismatch")
    if manifest.get("file_drop_rehearsal_ready") != config.get("file_drop_rehearsal_ready"):
        issues.append("package_manifest file_drop_rehearsal_ready/config mismatch")
    if manifest.get("file_drop_rehearsal_contract_ready") != config.get("file_drop_rehearsal_contract_ready"):
        issues.append("package_manifest file_drop_rehearsal_contract_ready/config mismatch")
    if status not in {STATUS_CONTRACT_READY, STATUS_READY}:
        issues.append(f"unknown status: {status}")
    ready = config.get("file_drop_rehearsal_ready")
    if ready != (status == STATUS_READY):
        issues.append("file_drop_rehearsal_ready/status mismatch")
    if config.get("file_drop_rehearsal_contract_ready") is not True:
        issues.append("file_drop_rehearsal_contract_ready must be true")
    if status == STATUS_CONTRACT_READY and not allow_contract_ready:
        issues.append("contract-ready package requires --allow-contract-ready")
    if status == STATUS_READY:
        if not CAPTURE_EDGE_READY_CLOSE_ENABLED:
            issues.append(CAPTURE_EDGE_READY_CLOSE_DISABLED_ISSUE)
        if preflight.get("runtime_capture_sufficient") is not True:
            issues.append("ready status requires runtime_capture_sufficient=true")
        if receipt.get("ready_status_allowed") is not True:
            issues.append("ready status requires ready_status_allowed=true")
        _verify_ready_runtime_event_evidence(package_dir, canonical, issues)
    if config.get("generated_by_rdf_sim") is not True:
        issues.append("generated_by_rdf_sim must be true")
    if config.get("external_partner_data") is not False or config.get("external_data_evaluated") is not False:
        issues.append("external partner/evaluated claims must be false")


def _verify_ready_runtime_event_evidence(package_dir: Path, canonical: dict[str, Any], issues: list[str]) -> None:
    process_provenance_receipt = _read_json(
        package_dir / "data" / "process_provenance" / "process_provenance_receipt.json",
        issues,
        "data/process_provenance/process_provenance_receipt.json",
        missing_issue="ready status requires data/process_provenance/process_provenance_receipt.json",
    )
    _verify_process_provenance_receipt(package_dir, process_provenance_receipt, issues)
    runtime_manifest = _read_json(
        package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json",
        issues,
        "data/runtime_evidence/runtime_event_manifest.json",
    )
    reconstruction_receipt = _read_json(
        package_dir / "data" / "runtime_evidence" / "runtime_reconstruction_receipt.json",
        issues,
        "data/runtime_evidence/runtime_reconstruction_receipt.json",
    )
    events = _load_runtime_events(package_dir, issues)
    if not events:
        return
    _verify_runtime_event_manifest(package_dir, runtime_manifest, reconstruction_receipt, events, issues)
    issues.extend(_runtime_event_global_issues(events))
    channel_issues: list[str] = []
    for event in events:
        channel_issues.extend(_runtime_channel_payload_issues(event))
    issues.extend(channel_issues)
    if channel_issues:
        return
    reconstructed = _reconstruct_canonical_from_runtime_events(events)
    if reconstructed is None:
        issues.append("runtime events could not reconstruct canonical trace")
        return
    actual_canonical_sha = hashlib.sha256(
        (json.dumps(canonical, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    ).hexdigest()
    if reconstruction_receipt.get("included_canonical_trace_sha256") != actual_canonical_sha:
        issues.append("runtime_reconstruction_receipt included_canonical_trace_sha256 mismatch")
    if reconstruction_receipt.get("reconstructed_canonical_trace_sha256") != actual_canonical_sha:
        issues.append("runtime_reconstruction_receipt reconstructed_canonical_trace_sha256 mismatch")
    if reconstruction_receipt.get("matches_included_canonical_trace") is not True:
        issues.append("runtime_reconstruction_receipt matches_included_canonical_trace must be true")
    if _canonical_runtime_projection(reconstructed) != _canonical_runtime_projection(canonical):
        issues.append("runtime reconstructed canonical trace does not match included canonical trace")


def _verify_process_provenance_receipt(
    package_dir: Path,
    receipt: dict[str, Any],
    issues: list[str],
) -> None:
    event_log_rel = "data/runtime_evidence/runtime_event_log.jsonl"
    event_log_path = package_dir / event_log_rel
    event_log_sha = _sha256_file(event_log_path) if event_log_path.is_file() else None
    if receipt.get("schema_version") != PROCESS_PROVENANCE_RECEIPT_SCHEMA_VERSION:
        issues.append("process_provenance_receipt schema_version mismatch")
    if receipt.get("capture_script_id") != RUNTIME_EVENT_CAPTURE_SCRIPT_ID:
        issues.append("process_provenance_receipt capture_script_id mismatch")
    if receipt.get("source_backend") != RUNTIME_BACKEND:
        issues.append("process_provenance_receipt source_backend mismatch")
    if receipt.get("source_process_kind") != RUNTIME_SOURCE_PROCESS_KIND:
        issues.append("process_provenance_receipt source_process_kind mismatch")
    if receipt.get("runtime_event_log_path") != event_log_rel:
        issues.append("process_provenance_receipt runtime_event_log_path mismatch")
    if receipt.get("runtime_event_log_sha256") != event_log_sha:
        issues.append("process_provenance_receipt runtime_event_log_sha256 mismatch")
    if receipt.get("exit_code") != 0:
        issues.append("process_provenance_receipt exit_code must be 0")
    for key in ("git_commit", "command", "python_version", "os_summary", "started_at", "ended_at"):
        if not isinstance(receipt.get(key), str) or not receipt.get(key):
            issues.append(f"process_provenance_receipt {key} missing")
    for path_key, hash_key in (
        ("script_path", "script_sha256"),
        ("config_path", "config_sha256"),
        ("stdout_log_path", "stdout_log_sha256"),
        ("stderr_log_path", "stderr_log_sha256"),
    ):
        rel_path = receipt.get(path_key)
        expected_hash = receipt.get(hash_key)
        if not isinstance(rel_path, str) or not _safe_data_path(rel_path):
            issues.append(f"process_provenance_receipt {path_key} unsafe")
            continue
        artifact_path = package_dir / rel_path
        if not _is_within(artifact_path, package_dir):
            issues.append(f"process_provenance_receipt {path_key} escapes package")
            continue
        if not artifact_path.is_file():
            issues.append(f"process_provenance_receipt {path_key} missing")
            continue
        if expected_hash != _sha256_file(artifact_path):
            issues.append(f"process_provenance_receipt {hash_key} mismatch")


def _load_runtime_events(package_dir: Path, issues: list[str]) -> list[dict[str, Any]]:
    event_log_path = package_dir / "data" / "runtime_evidence" / "runtime_event_log.jsonl"
    if not event_log_path.is_file():
        issues.append("ready status requires data/runtime_evidence/runtime_event_log.jsonl")
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(event_log_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            issues.append(f"runtime event log invalid jsonl at line {line_number}")
            continue
        if not isinstance(event, dict):
            issues.append(f"runtime event log row must be object at line {line_number}")
            continue
        events.append(event)
    if not events:
        issues.append("runtime event log empty")
    return events


def _verify_runtime_event_manifest(
    package_dir: Path,
    runtime_manifest: dict[str, Any],
    reconstruction_receipt: dict[str, Any],
    events: list[dict[str, Any]],
    issues: list[str],
) -> None:
    event_log_path = package_dir / "data" / "runtime_evidence" / "runtime_event_log.jsonl"
    event_log_sha = _sha256_file(event_log_path)
    frame_indices = {event.get("frame_index") for event in events if isinstance(event.get("frame_index"), int)}
    capture_ids = {event.get("capture_id") for event in events if isinstance(event.get("capture_id"), str)}
    if runtime_manifest.get("schema_version") != RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION:
        issues.append("runtime_event_manifest schema_version mismatch")
    if runtime_manifest.get("evidence_level") != "L2_verifier_owned_raw_runtime_events":
        issues.append("runtime_event_manifest evidence_level mismatch")
    if runtime_manifest.get("runtime_event_log_path") != "data/runtime_evidence/runtime_event_log.jsonl":
        issues.append("runtime_event_manifest runtime_event_log_path mismatch")
    if runtime_manifest.get("runtime_event_log_sha256") != event_log_sha:
        issues.append("runtime_event_manifest runtime_event_log_sha256 mismatch")
    if runtime_manifest.get("capture_script_id") != RUNTIME_EVENT_CAPTURE_SCRIPT_ID:
        issues.append("runtime_event_manifest capture_script_id mismatch")
    helper_signatures = {
        runtime_manifest.get("evidence_origin") == RUNTIME_EVENT_HELPER_EVIDENCE_ORIGIN,
        runtime_manifest.get("producer_kind") == RUNTIME_EVENT_HELPER_PRODUCER_KIND,
        runtime_manifest.get("helper_source_function") == RUNTIME_EVENT_HELPER_SOURCE_FUNCTION,
    }
    capture_edge_ready_origin = (
        runtime_manifest.get("evidence_origin") == RUNTIME_EVENT_CAPTURE_EDGE_EVIDENCE_ORIGIN
        and runtime_manifest.get("producer_kind") == RUNTIME_EVENT_CAPTURE_EDGE_PRODUCER_KIND
        and runtime_manifest.get("closing_evidence") is True
    )
    if any(helper_signatures) or not capture_edge_ready_origin:
        issues.append("helper-derived runtime evidence cannot open ready status")
    if runtime_manifest.get("source_backend") != RUNTIME_BACKEND:
        issues.append("runtime_event_manifest source_backend mismatch")
    if runtime_manifest.get("source_process_kind") != RUNTIME_SOURCE_PROCESS_KIND:
        issues.append("runtime_event_manifest source_process_kind mismatch")
    if len(capture_ids) != 1 or runtime_manifest.get("capture_id") not in capture_ids:
        issues.append("runtime_event_manifest capture_id mismatch")
    if runtime_manifest.get("frame_count") != len(frame_indices):
        issues.append("runtime_event_manifest frame_count mismatch")
    if runtime_manifest.get("event_count") != len(events):
        issues.append("runtime_event_manifest event_count mismatch")
    if runtime_manifest.get("required_channels") != list(RUNTIME_EVENT_REQUIRED_CHANNELS):
        issues.append("runtime_event_manifest required_channels mismatch")
    if runtime_manifest.get("generated_by_rdf_sim") is not True:
        issues.append("runtime_event_manifest generated_by_rdf_sim must be true")
    if runtime_manifest.get("external_partner_data") is not False:
        issues.append("runtime_event_manifest external_partner_data must be false")
    if runtime_manifest.get("non_claims") != {key: False for key in FORBIDDEN_CLAIMS}:
        issues.append("runtime_event_manifest non_claims mismatch")

    if reconstruction_receipt.get("schema_version") != RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION:
        issues.append("runtime_reconstruction_receipt schema_version mismatch")
    if reconstruction_receipt.get("reconstruction_algorithm") != RUNTIME_RECONSTRUCTION_ALGORITHM:
        issues.append("runtime_reconstruction_receipt algorithm mismatch")
    if reconstruction_receipt.get("runtime_event_log_sha256") != event_log_sha:
        issues.append("runtime_reconstruction_receipt runtime_event_log_sha256 mismatch")
    if reconstruction_receipt.get("runtime_capture_sufficient") is not True:
        issues.append("runtime_reconstruction_receipt runtime_capture_sufficient must be true")
    if reconstruction_receipt.get("ready_status_allowed") is not True:
        issues.append("runtime_reconstruction_receipt ready_status_allowed must be true")


def _runtime_event_global_issues(events: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if [event.get("event_index") for event in events] != list(range(len(events))):
        issues.append("runtime event_index not contiguous")
    previous_timestamp: float | None = None
    frames: dict[int, set[str]] = {}
    seen_frame_channels: set[tuple[int, str]] = set()
    capture_ids = {event.get("capture_id") for event in events}
    if len(capture_ids) != 1 or not all(isinstance(capture_id, str) and capture_id for capture_id in capture_ids):
        issues.append("runtime capture_id mismatch")
    for event in events:
        if event.get("schema_version") != RAW_RUNTIME_EVENT_SCHEMA_VERSION:
            issues.append("runtime event schema_version mismatch")
        if event.get("source_backend") != RUNTIME_BACKEND:
            issues.append("runtime event source_backend mismatch")
        if event.get("source_process_kind") != RUNTIME_SOURCE_PROCESS_KIND:
            issues.append("runtime event source_process_kind mismatch")
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not _finite_number(timestamp):
            issues.append("runtime timestamp invalid")
        else:
            current_timestamp = float(timestamp)
            if previous_timestamp is not None and current_timestamp < previous_timestamp:
                issues.append("runtime timestamp not monotonic")
            previous_timestamp = current_timestamp
        frame_index = event.get("frame_index")
        if not isinstance(frame_index, int) or frame_index < 0:
            issues.append("runtime frame_index invalid")
            continue
        channel = event.get("channel")
        if channel not in RUNTIME_EVENT_REQUIRED_CHANNELS:
            issues.append("unknown runtime event channel")
            continue
        key = (frame_index, cast(str, channel))
        if key in seen_frame_channels:
            issues.append("duplicate runtime event for frame/channel")
        seen_frame_channels.add(key)
        frames.setdefault(frame_index, set()).add(cast(str, channel))
        if not isinstance(event.get("units"), dict):
            issues.append("runtime event units missing")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            issues.append("runtime event payload missing")
        elif _contains_non_finite_number(payload):
            issues.append("runtime event contains non-finite number")
    if sorted(frames) != list(range(len(frames))):
        issues.append("runtime frame_index not contiguous")
    for frame_index, channels in frames.items():
        if channels != set(RUNTIME_EVENT_REQUIRED_CHANNELS):
            issues.append(f"runtime frame {frame_index} required channel set mismatch")
    return _dedupe(issues)


def _runtime_channel_payload_issues(event: dict[str, Any]) -> list[str]:
    channel = event.get("channel")
    units = event.get("units")
    payload = event.get("payload")
    if not isinstance(units, dict) or not isinstance(payload, dict):
        return []
    issues: list[str] = []
    if channel == "phase_marker":
        if payload.get("phase") not in RUNTIME_PHASES:
            issues.append("runtime phase unknown")
    elif channel == "ur_joint_state":
        if units.get("joint_position") != "rad":
            issues.append("UR joint_position unit mismatch")
        if payload.get("joint_names") != PROFILE_JOINT_NAMES["ur_rtde_csv_v0"]:
            issues.append("UR joint_names mismatch")
        if not _numeric_vector(payload.get("actual_q"), 6) or not _numeric_vector(payload.get("target_q"), 6):
            issues.append("UR actual_q/target_q dimension mismatch")
        if payload.get("robot_mode") != "RUNNING":
            issues.append("UR robot_mode must be RUNNING")
        if payload.get("safety_status") != "NORMAL":
            issues.append("UR safety_status must be NORMAL")
    elif channel == "ur_tcp_state":
        if units.get("tcp_position") != "m":
            issues.append("UR tcp_position unit mismatch")
        if units.get("tcp_rotation") != "rotation_vector_rad":
            issues.append("UR tcp_rotation unit mismatch")
        if units.get("tcp_speed") != "m_per_s":
            issues.append("UR tcp_speed unit mismatch")
        if (
            not _numeric_vector(payload.get("actual_TCP_pose"), 6)
            or not _numeric_vector(payload.get("target_TCP_pose"), 6)
            or not _numeric_vector(payload.get("actual_TCP_speed"), 6)
        ):
            issues.append("UR TCP vector dimension mismatch")
    elif channel == "franka_joint_state":
        if units.get("joint_position") != "rad":
            issues.append("Franka joint_position unit mismatch")
        if payload.get("joint_names") != PROFILE_JOINT_NAMES["franka_state_jsonl_v0"]:
            issues.append("Franka joint_names mismatch")
        if not _numeric_vector(payload.get("q"), 7) or not _numeric_vector(payload.get("q_d"), 7):
            issues.append("Franka q/q_d dimension mismatch")
        if payload.get("robot_mode") != "move":
            issues.append("Franka robot_mode must be move")
    elif channel == "franka_eef_state":
        if units.get("pose_matrix") != "homogeneous_transform_row_major_m":
            issues.append("Franka EEF pose unit mismatch")
        if not _numeric_vector(payload.get("O_T_EE"), 16) or not _numeric_vector(payload.get("O_T_EE_d"), 16):
            issues.append("Franka EEF matrix length mismatch")
        elif not _rigid_transform(payload["O_T_EE"]):
            issues.append("Franka EEF matrix implausible")
    elif channel == "generic_command_state":
        if (
            payload.get("action_semantics") != "commanded_target_state"
            or payload.get("state_semantics") != "actual_robot_state"
            or "command" not in payload
            or "state" not in payload
        ):
            issues.append("generic command/state semantics missing")
        if not _numeric_vector(payload.get("state"), 6) or not _numeric_vector(payload.get("command"), 6):
            issues.append("generic state/command dimension mismatch")
        if not _finite_number(payload.get("command_timestamp")) or not _finite_number(payload.get("state_timestamp")):
            issues.append("generic command/state timestamp invalid")
        elif abs(float(payload["command_timestamp"]) - float(payload["state_timestamp"])) > MAX_ACTION_STATE_LAG:
            issues.append("generic action-state lag exceeds threshold")
    return issues


def _reconstruct_canonical_from_runtime_events(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    grouped: dict[int, dict[str, dict[str, Any]]] = {}
    for event in events:
        frame_index = event.get("frame_index")
        channel = event.get("channel")
        payload = event.get("payload")
        if not isinstance(frame_index, int) or channel not in RUNTIME_EVENT_REQUIRED_CHANNELS or not isinstance(payload, dict):
            return None
        grouped.setdefault(frame_index, {})[cast(str, channel)] = payload
    if sorted(grouped) != list(range(len(grouped))):
        return None
    frames: list[dict[str, Any]] = []
    for frame_index in sorted(grouped):
        channels = grouped[frame_index]
        if set(channels) != set(RUNTIME_EVENT_REQUIRED_CHANNELS):
            return None
        phase = channels["phase_marker"]
        ur_joint = channels["ur_joint_state"]
        ur_tcp = channels["ur_tcp_state"]
        franka_joint = channels["franka_joint_state"]
        franka_eef = channels["franka_eef_state"]
        generic = channels["generic_command_state"]
        timestamp = events[frame_index * len(RUNTIME_EVENT_REQUIRED_CHANNELS)]["timestamp"]
        frames.append(
            {
                "frame_index": frame_index,
                "timestamp": timestamp,
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
        "trace_id": "mvp5a_pre_l2_runtime_event_reconstructed_trace_v0",
        "source_kind": RUNTIME_BACKED_SOURCE_KIND,
        "runtime_backed": True,
        "generated_by_rdf_sim": True,
        "external_partner_data": False,
        "frame_count": len(frames),
        "frames": frames,
        "non_claims": {key: False for key in FORBIDDEN_CLAIMS},
    }


def _canonical_runtime_projection(canonical: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": canonical.get("schema_version"),
        "source_kind": canonical.get("source_kind"),
        "runtime_backed": canonical.get("runtime_backed"),
        "generated_by_rdf_sim": canonical.get("generated_by_rdf_sim"),
        "external_partner_data": canonical.get("external_partner_data"),
        "frame_count": canonical.get("frame_count"),
        "frames": canonical.get("frames"),
        "non_claims": canonical.get("non_claims"),
    }


def _contains_non_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return not math.isfinite(float(value))
    if isinstance(value, list):
        return any(_contains_non_finite_number(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_non_finite_number(item) for item in value.values())
    return False


def _verify_ready_runtime_capture(
    package_dir: Path,
    canonical: dict[str, Any],
    preflight: dict[str, Any],
    receipt: dict[str, Any],
    issues: list[str],
) -> None:
    runtime_capture_path = package_dir / "data" / "canonical_trace" / "runtime_capture.json"
    if not runtime_capture_path.is_file():
        issues.append("ready status requires data/canonical_trace/runtime_capture.json")
        return
    runtime_capture_sha256 = _sha256_file(runtime_capture_path)
    if preflight.get("runtime_capture_sha256") != runtime_capture_sha256:
        issues.append("ready runtime_capture preflight sha256 mismatch")
    if receipt.get("runtime_capture_sha256") != runtime_capture_sha256:
        issues.append("ready runtime_capture receipt sha256 mismatch")
    if canonical.get("runtime_capture_sha256") != runtime_capture_sha256:
        issues.append("ready canonical runtime_capture sha256 mismatch")

    capture = _read_json(runtime_capture_path, issues, "data/canonical_trace/runtime_capture.json")
    if not isinstance(capture.get("captured_at"), str):
        issues.append("ready runtime_capture captured_at missing")
    capture_trace = capture.get("mvp5a_canonical_trace")
    if not isinstance(capture_trace, dict) or not isinstance(capture_trace.get("frames"), list):
        issues.append("ready runtime_capture canonical trace missing")
        return
    for issue in _runtime_capture_provenance_issues(capture, capture_trace):
        issues.append(f"ready runtime_capture provenance invalid: {issue}")
    if len(capture_trace["frames"]) < MIN_CANONICAL_FRAMES:
        issues.append("ready runtime_capture canonical trace frame count below minimum")
    for issue in _runtime_canonical_trace_issues(capture_trace):
        issues.append(f"ready runtime_capture canonical schema invalid: {issue}")

    expected_canonical = {
        **capture_trace,
        "runtime_capture_sha256": runtime_capture_sha256,
    }
    if canonical != expected_canonical:
        issues.append("ready canonical trace does not match runtime_capture canonical trace")
    if canonical.get("runtime_backed") is not True:
        issues.append("ready canonical trace must be runtime_backed")
    if canonical.get("source_kind") != RUNTIME_BACKED_SOURCE_KIND:
        issues.append("ready canonical trace source_kind mismatch")


def _verify_canonical_trace(canonical: dict[str, Any], receipt: dict[str, Any], issues: list[str]) -> None:
    if canonical.get("schema_version") != CANONICAL_TRACE_SCHEMA_VERSION:
        issues.append("canonical trace schema_version mismatch")
    if canonical.get("generated_by_rdf_sim") is not True:
        issues.append("canonical trace generated_by_rdf_sim must be true")
    frames = canonical.get("frames")
    if not isinstance(frames, list) or len(frames) < MIN_CANONICAL_FRAMES:
        issues.append("canonical trace frame count below minimum")
        return
    for issue in _runtime_canonical_trace_issues(canonical):
        issues.append(f"canonical trace schema invalid: {issue}")
    previous = None
    for frame in frames:
        if not isinstance(frame, dict):
            issues.append("canonical trace frame must be object")
            continue
        timestamp = frame.get("timestamp")
        if not _finite_number(timestamp):
            issues.append("canonical trace timestamp invalid")
        elif previous is not None and timestamp <= previous:
            issues.append("canonical trace timestamp not monotonic")
        previous = timestamp
    actual_hash = hashlib.sha256((json.dumps(canonical, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")).hexdigest()
    if receipt.get("canonical_trace_sha256") != actual_hash:
        issues.append("canonical trace receipt hash mismatch")
    if canonical.get("external_partner_data") is not False:
        issues.append("canonical trace external_partner_data must be false")


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
    return hashlib.sha256(
        (json.dumps(projection, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    ).hexdigest()


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


def _verify_registry(registry: dict[str, Any], issues: list[str]) -> None:
    if registry.get("schema_version") != PROFILE_REGISTRY_SCHEMA_VERSION:
        issues.append("profile registry schema_version mismatch")
    if registry.get("required_profile_ids") != list(PROFILE_IDS):
        issues.append("profile registry required_profile_ids mismatch")
    if registry.get("profile_count") != len(PROFILE_IDS):
        issues.append("profile registry profile_count mismatch")
    profiles = registry.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != len(PROFILE_IDS):
        issues.append("profile registry profile count mismatch")
        return
    profile_ids = [profile.get("profile_id") for profile in profiles if isinstance(profile, dict)]
    if profile_ids != list(PROFILE_IDS):
        issues.append("profile registry profile_id order/exactness mismatch")
    if len(set(profile_ids)) != len(profile_ids):
        issues.append("profile registry duplicate profile_id")
    for profile in profiles:
        if not isinstance(profile, dict):
            issues.append("profile registry profile must be object")
            continue
        profile_id = profile.get("profile_id")
        if profile_id not in PROFILE_IDS:
            issues.append("profile registry unknown profile")
            continue
        if profile.get("dof") != PROFILE_DOFS[profile_id]:
            issues.append(f"{profile_id} dof mismatch")
        if profile.get("joint_names") != PROFILE_JOINT_NAMES[profile_id]:
            issues.append(f"{profile_id} joint_names mismatch")
        if profile.get("external_partner_data") is not False or profile.get("live_runtime_support") is not False:
            issues.append(f"{profile_id} forbidden runtime/partner claim")
        if profile != _expected_profile_registry_entry(profile_id):
            issues.append(f"{profile_id} profile registry contract mismatch")


def _verify_hdf5_deep_requirement(package_dir: Path, deep_hdf5: bool, issues: list[str]) -> None:
    has_hdf5 = any((package_dir / "data" / "export").glob("*/dataset.hdf5"))
    if has_hdf5 and not deep_hdf5:
        issues.append("hdf5 payload verification requires --deep-hdf5")


def _expected_profile_registry_entry(profile_id: str) -> dict[str, Any]:
    family, model = PROFILE_ROBOT_METADATA[profile_id]
    return {
        "profile_id": profile_id,
        "robot_family": family,
        "robot_model": model,
        "dof": PROFILE_DOFS[profile_id],
        "joint_names": PROFILE_JOINT_NAMES[profile_id],
        "source_file_names": PROFILE_SOURCE_FILES[profile_id],
        "action_semantics": PROFILE_ACTION_SEMANTICS[profile_id],
        "state_semantics": PROFILE_STATE_SEMANTICS[profile_id],
        "live_runtime_support": False,
        "external_partner_data": False,
    }


def _verify_golden_results(package_dir: Path, golden: dict[str, Any], canonical: dict[str, Any], issues: list[str], *, deep_hdf5: bool) -> None:
    results = golden.get("results")
    if not isinstance(results, list):
        issues.append("golden results must be list")
        return
    if {row.get("profile_id") for row in results if isinstance(row, dict)} != set(PROFILE_IDS):
        issues.append("golden profile set mismatch")
    for row in results:
        if not isinstance(row, dict):
            issues.append("golden result must be object")
            continue
        profile_id = str(row.get("profile_id") or "")
        source_dir = package_dir / "data" / "source_drops" / "golden" / profile_id
        recomputed = _validate_drop(source_dir, profile_id)
        if not recomputed["passed"]:
            issues.append(f"{profile_id} golden recomputation failed: {','.join(recomputed['rejection_reasons'])}")
        expected_rows = _expected_rows_from_canonical(canonical, profile_id)
        if not expected_rows:
            issues.append(f"{profile_id} canonical projection unavailable")
        elif recomputed.get("source_rows") != expected_rows:
            issues.append(f"{profile_id} golden source rows do not match canonical projection")
        if row.get("passed") is not True:
            issues.append(f"{profile_id} golden cached result not pass")
        if row.get("frame_count") != recomputed["frame_count"]:
            issues.append(f"{profile_id} golden frame_count mismatch")
        if row.get("source_file_hashes") != _source_hashes(source_dir):
            issues.append(f"{profile_id} golden source hash mismatch")
        contract = _read_json(package_dir / "data" / "normalized_contracts" / f"{profile_id}_normalized_contract.json", issues, f"{profile_id} contract")
        _verify_contract(profile_id, contract, recomputed, issues)
        _verify_export_receipts(package_dir, profile_id, recomputed, issues, deep_hdf5=deep_hdf5)


def _verify_corrupt_results(package_dir: Path, corrupt: dict[str, Any], coverage: dict[str, Any], issues: list[str]) -> None:
    results = corrupt.get("results")
    if not isinstance(results, list):
        issues.append("corrupt results must be list")
        return
    if len(results) < 50:
        issues.append("corrupt case count below 50")
    for row in results:
        if not isinstance(row, dict):
            issues.append("corrupt result must be object")
            continue
        profile_id = str(row.get("profile_id") or "")
        mutation_id = str(row.get("mutation_id") or "")
        source_dir = package_dir / "data" / "source_drops" / "corrupt" / profile_id / mutation_id
        recomputed = _validate_drop(source_dir, profile_id)
        expected = row.get("expected_rejection_reason")
        if recomputed["passed"]:
            issues.append(f"{profile_id}:{mutation_id} corrupt case silently passed")
        if expected not in recomputed["rejection_reasons"]:
            issues.append(f"{profile_id}:{mutation_id} expected rejection reason missing")
        if row.get("passed") is not False:
            issues.append(f"{profile_id}:{mutation_id} cached result must be fail")
        if row.get("export_eligible") is not False or row.get("trainer_smoke_eligible") is not False:
            issues.append(f"{profile_id}:{mutation_id} corrupt case export/trainer eligible")
        if row.get("source_file_hashes") != _source_hashes(source_dir):
            issues.append(f"{profile_id}:{mutation_id} corrupt source hash mismatch")
    if coverage.get("structured_rejection_reason_coverage") is not True:
        issues.append("structured_rejection_reason_coverage must be true")
    if coverage.get("silent_pass_rate") != 0.0:
        issues.append("silent_pass_rate must be 0.0")
    if coverage.get("corrupt_case_count") != len(results):
        issues.append("coverage corrupt_case_count mismatch")


def _verify_summary_consistency(config: dict[str, Any], golden: dict[str, Any], corrupt: dict[str, Any], coverage: dict[str, Any], issues: list[str]) -> None:
    golden_raw = golden.get("results")
    corrupt_raw = corrupt.get("results")
    golden_results: list[dict[str, Any]] = [row for row in golden_raw if isinstance(row, dict)] if isinstance(golden_raw, list) else []
    corrupt_results: list[dict[str, Any]] = [row for row in corrupt_raw if isinstance(row, dict)] if isinstance(corrupt_raw, list) else []
    if config.get("golden_profile_count") != len(golden_results):
        issues.append("config golden_profile_count mismatch")
    if config.get("corrupt_case_count") != len(corrupt_results):
        issues.append("config corrupt_case_count mismatch")
    if config.get("structured_rejection_reason_coverage") != coverage.get("structured_rejection_reason_coverage"):
        issues.append("config structured_rejection_reason_coverage mismatch")
    if any(row.get("passed") is not True for row in golden_results):
        issues.append("not all golden cases pass")
    if any(row.get("passed") is not False for row in corrupt_results):
        issues.append("not all corrupt cases fail")


def _validate_drop(source_dir: Path, profile_id: str) -> dict[str, Any]:
    issues: list[str] = []
    metadata = _read_json(source_dir / "metadata.json", issues, f"{profile_id} metadata", missing_issue="schema_missing_required_artifact")
    if profile_id not in PROFILE_IDS:
        issues.append("unsupported_profile")
        return _validation_result(issues, 0)
    issues.extend(_metadata_issues(metadata, profile_id))
    if profile_id == "ur_rtde_csv_v0":
        rows = _parse_ur(source_dir / "rtde_output.csv", issues)
    elif profile_id == "franka_state_jsonl_v0":
        rows = _parse_franka(source_dir, issues)
    elif profile_id == "ros2_channel_bundle_jsonl_v0":
        rows = _parse_ros2(source_dir, issues)
    else:
        rows = _parse_generic(source_dir / "command_state.jsonl", issues)
    issues.extend(_common_row_issues(rows, profile_id))
    issues.extend(_semantic_issues(rows, profile_id))
    return _validation_result(issues, len(rows), rows)


def _metadata_issues(metadata: dict[str, Any], profile_id: str) -> list[str]:
    issues: list[str] = []
    if metadata.get("profile_id") != profile_id:
        issues.append("unsupported_profile")
    if metadata.get("source_kind") != "digital_twin_rehearsal_log":
        issues.append("provenance_boundary_violation")
    if metadata.get("generated_by_rdf_sim") is not True:
        issues.append("provenance_boundary_violation")
    if metadata.get("external_partner_data") is not False or metadata.get("external_data_evaluated") is True:
        issues.append("provenance_boundary_violation")
    if metadata.get("real_robot_success") is True:
        issues.append("claim_boundary_violation")
    if metadata.get("dof") != PROFILE_DOFS[profile_id] or metadata.get("joint_names") != PROFILE_JOINT_NAMES[profile_id]:
        issues.append("vector_dimension_mismatch")
    expected_family, expected_model = PROFILE_ROBOT_METADATA[profile_id]
    if metadata.get("robot_family") != expected_family or metadata.get("robot_model") != expected_model:
        issues.append("unsupported_profile")
    units = metadata.get("units")
    if not isinstance(units, dict) or units.get("joint_position") != "rad":
        issues.append("unit_mismatch")
    if profile_id == "ur_rtde_csv_v0" and isinstance(units, dict):
        if units.get("tcp_position") != "m" or units.get("tcp_rotation") != "rotation_vector_rad":
            issues.append("unit_mismatch")
    expected_action = {
        "ur_rtde_csv_v0": "target_q_command",
        "franka_state_jsonl_v0": "q_d_command",
        "ros2_channel_bundle_jsonl_v0": "command_topic_target_joint_state",
        "generic_command_state_jsonl_v0": "explicit_command_vector",
    }[profile_id]
    if metadata.get("action_semantics") != expected_action:
        issues.append("action_state_semantic_mismatch")
    for key in FORBIDDEN_CLAIMS:
        if metadata.get(key) is True:
            issues.append("claim_boundary_violation")
    return issues


def _parse_ur(path: Path, issues: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        issues.append("schema_missing_required_artifact")
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    required = {"timestamp", "joint_names", "actual_q", "target_q", "actual_TCP_pose", "target_TCP_pose", "actual_TCP_speed", "robot_mode", "safety_status"}
    if rows and set(rows[0]) != required:
        issues.append("schema_missing_required_field")
    parsed = []
    for raw in rows:
        if any(raw.get(field) in (None, "") for field in required):
            issues.append("schema_missing_required_field")
        parsed.append(
            {
                "timestamp": _float(raw.get("timestamp")),
                "state_vector": _json_array(raw.get("actual_q"), issues),
                "action_vector": _json_array(raw.get("target_q"), issues),
                "joint_names": _json_array(raw.get("joint_names"), issues),
                "actual_TCP_pose": _json_array(raw.get("actual_TCP_pose"), issues),
                "target_TCP_pose": _json_array(raw.get("target_TCP_pose"), issues),
                "actual_TCP_speed": _json_array(raw.get("actual_TCP_speed"), issues),
                "robot_mode": raw.get("robot_mode"),
                "safety_status": raw.get("safety_status"),
            }
        )
    return parsed


def _parse_franka(source_dir: Path, issues: list[str]) -> list[dict[str, Any]]:
    states = _read_jsonl(source_dir / "franka_state.jsonl", issues)
    commands = _read_jsonl(source_dir / "franka_command.jsonl", issues)
    if len(states) != len(commands):
        issues.append("timestamp_gap_or_drift")
    rows = []
    for state, command in zip(states, commands, strict=False):
        rows.append(
            {
                "timestamp": _float(state.get("timestamp")),
                "state_vector": state.get("q"),
                "action_vector": command.get("q_d"),
                "O_T_EE": state.get("O_T_EE"),
                "O_T_EE_d": command.get("O_T_EE_d"),
                "robot_mode": state.get("robot_mode"),
                "command_timestamp": _float(command.get("timestamp")),
            }
        )
    return rows


def _parse_ros2(source_dir: Path, issues: list[str]) -> list[dict[str, Any]]:
    manifest = _read_json(source_dir / "topic_manifest.json", issues, "topic_manifest", missing_issue="schema_missing_required_artifact")
    if set(manifest.get("topics") or []) != {"/joint_states", "/tf", "/tf_static", "/command"}:
        issues.append("schema_missing_required_artifact")
    joints = _read_jsonl(source_dir / "topics" / "joint_states.jsonl", issues)
    tfs = _read_jsonl(source_dir / "topics" / "tf.jsonl", issues)
    tf_static = _read_jsonl(source_dir / "topics" / "tf_static.jsonl", issues)
    commands = _read_jsonl(source_dir / "topics" / "command.jsonl", issues)
    if not tf_static:
        issues.append("frame_tree_invalid")
    if len({len(joints), len(tfs), len(commands)}) != 1:
        issues.append("timestamp_gap_or_drift")
    rows = []
    for joint, tf_row, command in zip(joints, tfs, commands, strict=False):
        rows.append(
            {
                "timestamp": _float(joint.get("timestamp")),
                "state_vector": joint.get("position"),
                "action_vector": command.get("target_position"),
                "joint_names": joint.get("name"),
                "frame_id": joint.get("frame_id"),
                "tf_parent": tf_row.get("parent_frame_id"),
                "tf_child": tf_row.get("child_frame_id"),
                "tf_translation": tf_row.get("translation"),
                "tf_rotation_rpy": tf_row.get("rotation_rpy"),
                "tf_timestamp": _float(tf_row.get("timestamp")),
                "command_timestamp": _float(command.get("timestamp")),
                "command_frame_id": command.get("frame_id"),
            }
        )
    return rows


def _parse_generic(path: Path, issues: list[str]) -> list[dict[str, Any]]:
    rows = _read_jsonl(path, issues)
    return [
        {
            "timestamp": _float(row.get("timestamp")),
            "state_vector": row.get("state"),
            "action_vector": row.get("command"),
            "command_timestamp": _float(row.get("command_timestamp")),
            "state_timestamp": _float(row.get("state_timestamp")),
            "action_semantics": row.get("action_semantics"),
            "state_semantics": row.get("state_semantics"),
            "reset_boundary": row.get("reset_boundary"),
            "task_success": row.get("task_success"),
        }
        for row in rows
    ]


def _common_row_issues(rows: list[dict[str, Any]], profile_id: str) -> list[str]:
    issues: list[str] = []
    if len(rows) < MIN_CANONICAL_FRAMES:
        issues.append("timestamp_gap_or_drift")
    previous = None
    dof = PROFILE_DOFS[profile_id]
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
        if not _numeric_vector(row.get("state_vector"), dof):
            issues.append("vector_dimension_mismatch")
        if not _numeric_vector(row.get("action_vector"), dof):
            issues.append("vector_dimension_mismatch")
    return _dedupe(issues)


def _semantic_issues(rows: list[dict[str, Any]], profile_id: str) -> list[str]:
    issues: list[str] = []
    for row in rows:
        if profile_id == "ur_rtde_csv_v0":
            if row.get("joint_names") != PROFILE_JOINT_NAMES[profile_id]:
                issues.append("frame_semantic_drift")
            if not _numeric_vector(row.get("actual_TCP_pose"), 6) or not _numeric_vector(row.get("target_TCP_pose"), 6):
                issues.append("vector_dimension_mismatch")
            if row.get("robot_mode") != "RUNNING" or row.get("safety_status") != "NORMAL":
                issues.append("safety_or_robot_mode_invalid")
            if _distance(row.get("state_vector"), row.get("action_vector")) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        elif profile_id == "franka_state_jsonl_v0":
            if row.get("robot_mode") != "move":
                issues.append("safety_or_robot_mode_invalid")
            if not _numeric_vector(row.get("O_T_EE"), 16) or not _numeric_vector(row.get("O_T_EE_d"), 16):
                issues.append("vector_dimension_mismatch")
            elif not _rigid_transform(row["O_T_EE"]):
                issues.append("frame_semantic_drift")
            if abs(float(row.get("command_timestamp", math.nan)) - float(row.get("timestamp", math.inf))) > MAX_ACTION_STATE_LAG:
                issues.append("action_state_semantic_mismatch")
        elif profile_id == "ros2_channel_bundle_jsonl_v0":
            if row.get("joint_names") != PROFILE_JOINT_NAMES[profile_id]:
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
            if row.get("action_semantics") != "explicit_command_vector" or row.get("state_semantics") != "explicit_state_vector":
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
            or not _rigid_transform(o_t_ee if isinstance(o_t_ee, list) else [])
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


def _expected_rows_from_canonical(canonical: dict[str, Any], profile_id: str) -> list[dict[str, Any]]:
    frames = canonical.get("frames")
    if not isinstance(frames, list):
        return []
    rows: list[dict[str, Any]] = []
    for frame in frames:
        if not isinstance(frame, dict):
            return []
        timestamp = frame.get("timestamp")
        if profile_id == "ur_rtde_csv_v0":
            source = frame.get("ur")
            if not isinstance(source, dict):
                return []
            rows.append(
                {
                    "timestamp": timestamp,
                    "state_vector": source.get("actual_q"),
                    "action_vector": source.get("target_q"),
                    "joint_names": PROFILE_JOINT_NAMES[profile_id],
                    "actual_TCP_pose": source.get("actual_TCP_pose"),
                    "target_TCP_pose": source.get("target_TCP_pose"),
                    "actual_TCP_speed": source.get("actual_TCP_speed"),
                    "robot_mode": source.get("robot_mode"),
                    "safety_status": source.get("safety_status"),
                }
            )
        elif profile_id == "franka_state_jsonl_v0":
            source = frame.get("franka")
            if not isinstance(source, dict):
                return []
            rows.append(
                {
                    "timestamp": timestamp,
                    "state_vector": source.get("q"),
                    "action_vector": source.get("q_d"),
                    "O_T_EE": source.get("O_T_EE"),
                    "O_T_EE_d": source.get("O_T_EE_d"),
                    "robot_mode": source.get("robot_mode"),
                    "command_timestamp": timestamp,
                }
            )
        elif profile_id == "ros2_channel_bundle_jsonl_v0":
            source = frame.get("ur")
            if not isinstance(source, dict):
                return []
            actual_tcp_pose = source.get("actual_TCP_pose")
            rows.append(
                {
                    "timestamp": timestamp,
                    "state_vector": source.get("actual_q"),
                    "action_vector": source.get("target_q"),
                    "joint_names": PROFILE_JOINT_NAMES[profile_id],
                    "frame_id": "base_link",
                    "tf_parent": "base_link",
                    "tf_child": "tool0",
                    "tf_translation": actual_tcp_pose[:3] if isinstance(actual_tcp_pose, list) else None,
                    "tf_rotation_rpy": actual_tcp_pose[3:] if isinstance(actual_tcp_pose, list) else None,
                    "tf_timestamp": timestamp,
                    "command_timestamp": timestamp,
                    "command_frame_id": "base_link",
                }
            )
        elif profile_id == "generic_command_state_jsonl_v0":
            source = frame.get("generic")
            if not isinstance(source, dict):
                return []
            rows.append(
                {
                    "timestamp": timestamp,
                    "state_vector": source.get("state"),
                    "action_vector": source.get("command"),
                    "command_timestamp": source.get("command_timestamp"),
                    "state_timestamp": source.get("state_timestamp"),
                    "action_semantics": "explicit_command_vector",
                    "state_semantics": "explicit_state_vector",
                    "reset_boundary": False,
                    "task_success": None,
                }
            )
        else:
            return []
    return _canonicalize_source_rows(rows)


def _validation_result(issues: list[str], frame_count: int, rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reasons = [reason for reason in REJECTION_REASONS if reason in set(issues)]
    source_rows = _canonicalize_source_rows(rows or []) if not reasons else []
    return {
        "passed": not reasons,
        "rejection_reasons": reasons,
        "frame_count": frame_count,
        "rows": _normalized_rows(rows or []) if not reasons else [],
        "source_rows": source_rows,
    }


def _verify_contract(profile_id: str, contract: dict[str, Any], recomputed: dict[str, Any], issues: list[str]) -> None:
    if contract.get("profile_id") != profile_id:
        issues.append(f"{profile_id} contract profile_id mismatch")
    if contract.get("passed") is not True or contract.get("export_eligible") is not True or contract.get("trainer_smoke_eligible") is not True:
        issues.append(f"{profile_id} contract pass/export/trainer mismatch")
    if contract.get("frame_count") != recomputed["frame_count"]:
        issues.append(f"{profile_id} contract frame_count mismatch")
    if contract.get("state_dim") != PROFILE_DOFS[profile_id] or contract.get("action_dim") != PROFILE_DOFS[profile_id]:
        issues.append(f"{profile_id} contract dims mismatch")
    rows = contract.get("rows")
    if not isinstance(rows, list) or len(rows) != recomputed["frame_count"]:
        issues.append(f"{profile_id} contract rows mismatch")
    else:
        for row in rows:
            if not _numeric_vector(row.get("state_vector"), PROFILE_DOFS[profile_id]) or not _numeric_vector(row.get("action_vector"), PROFILE_DOFS[profile_id]):
                issues.append(f"{profile_id} contract row vector mismatch")
        if _normalized_rows(rows) != recomputed.get("rows"):
            issues.append(f"{profile_id} contract rows do not match recomputed source rows")


def _verify_export_receipts(package_dir: Path, profile_id: str, recomputed: dict[str, Any], issues: list[str], *, deep_hdf5: bool) -> None:
    export_dir = package_dir / "data" / "export" / profile_id
    hdf5_path = export_dir / "dataset.hdf5"
    inspection = _read_json(export_dir / "hdf5_inspection_report.json", issues, f"{profile_id} hdf5 inspection")
    trainer = _read_json(export_dir / "trainer_smoke_report.json", issues, f"{profile_id} trainer smoke")
    receipt = _read_json(export_dir / "semantic_preservation_receipt.json", issues, f"{profile_id} semantic receipt")
    if not hdf5_path.is_file():
        issues.append(f"{profile_id} hdf5 missing")
    elif inspection.get("hdf5_sha256") != _sha256_file(hdf5_path):
        issues.append(f"{profile_id} hdf5 inspection sha256 mismatch")
    if inspection.get("passed") is not True or trainer.get("passed") is not True:
        issues.append(f"{profile_id} inspection/trainer must pass")
    raw_rows = recomputed.get("rows")
    rows: list[dict[str, Any]] = [row for row in raw_rows if isinstance(row, dict)] if isinstance(raw_rows, list) else []
    state_hash = _array_hash([row.get("state_vector") for row in rows])
    action_hash = _array_hash([row.get("action_vector") for row in rows])
    timestamp_hash = _float64_hash([row.get("timestamp") for row in rows])
    if inspection.get("state_array_sha256") != state_hash or inspection.get("action_array_sha256") != action_hash:
        issues.append(f"{profile_id} hdf5 inspection array hash mismatch")
    if inspection.get("timestamp_array_sha256") != timestamp_hash:
        issues.append(f"{profile_id} hdf5 inspection timestamp hash mismatch")
    if receipt.get("source_state_sha256") != state_hash or receipt.get("source_action_sha256") != action_hash:
        issues.append(f"{profile_id} semantic receipt source hash mismatch")
    if receipt.get("hdf5_state_sha256") != state_hash or receipt.get("hdf5_action_sha256") != action_hash:
        issues.append(f"{profile_id} semantic receipt hdf5 hash mismatch")
    if receipt.get("source_timestamp_sha256") != timestamp_hash:
        issues.append(f"{profile_id} semantic receipt source timestamp hash mismatch")
    if receipt.get("hdf5_timestamp_sha256") != timestamp_hash:
        issues.append(f"{profile_id} semantic receipt hdf5 timestamp hash mismatch")
    if receipt.get("profile_semantics_preserved") is not True:
        issues.append(f"{profile_id} semantic receipt not preserved")
    if trainer.get("state_dim") != PROFILE_DOFS[profile_id] or trainer.get("action_dim") != PROFILE_DOFS[profile_id]:
        issues.append(f"{profile_id} trainer dims mismatch")
    if deep_hdf5:
        _verify_deep_hdf5(hdf5_path, profile_id, rows, issues)


def _verify_deep_hdf5(hdf5_path: Path, profile_id: str, rows: list[dict[str, Any]], issues: list[str]) -> None:
    try:
        import h5py  # type: ignore[import-untyped]
        import numpy as np

        with h5py.File(hdf5_path, "r") as h5:
            h5_any = cast(Any, h5)
            states = np.asarray(h5_any["states"][()], dtype=np.float32)
            actions = np.asarray(h5_any["actions"][()], dtype=np.float32)
            timestamps = np.asarray(h5_any["timestamps"][()], dtype=np.float64)
        expected_states = np.asarray([row["state_vector"] for row in rows], dtype=np.float32)
        expected_actions = np.asarray([row["action_vector"] for row in rows], dtype=np.float32)
        expected_timestamps = np.asarray([row["timestamp"] for row in rows], dtype=np.float64)
        if states.shape != expected_states.shape or not bool(np.array_equal(states, expected_states)):
            issues.append(f"{profile_id} deep hdf5 states mismatch")
        if _array_hash(states.tolist()) != _array_hash(expected_states.tolist()):
            issues.append(f"{profile_id} deep hdf5 states hash mismatch")
        if actions.shape != expected_actions.shape or not bool(np.array_equal(actions, expected_actions)):
            issues.append(f"{profile_id} deep hdf5 actions mismatch")
        if _array_hash(actions.tolist()) != _array_hash(expected_actions.tolist()):
            issues.append(f"{profile_id} deep hdf5 actions hash mismatch")
        if timestamps.shape != expected_timestamps.shape or not bool(np.array_equal(timestamps, expected_timestamps)):
            issues.append(f"{profile_id} deep hdf5 timestamps mismatch")
        if _float64_hash(timestamps.tolist()) != _float64_hash(expected_timestamps.tolist()):
            issues.append(f"{profile_id} deep hdf5 timestamps hash mismatch")
    except Exception as exc:  # noqa: BLE001 - verifier reports deep-mode errors as issues.
        issues.append(f"{profile_id} deep hdf5 failed: {type(exc).__name__}: {exc}")


def _array_hash(rows: list[Any]) -> str:
    try:
        import struct

        flattened: list[float] = []
        for row in rows:
            if not isinstance(row, list):
                return ""
            flattened.extend(float(value) for value in row)
        return hashlib.sha256(b"".join(struct.pack("<f", value) for value in flattened)).hexdigest()
    except (TypeError, ValueError):
        return ""


def _float64_hash(values: list[Any]) -> str:
    try:
        import struct

        return hashlib.sha256(b"".join(struct.pack("<d", float(value)) for value in values)).hexdigest()
    except (TypeError, ValueError):
        return ""


def _normalized_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return []
        state = row.get("state_vector")
        action = row.get("action_vector")
        timestamp = _finite_float(row.get("timestamp"))
        if not isinstance(state, list) or not isinstance(action, list) or timestamp is None:
            return []
        try:
            normalized.append(
                {
                    "timestamp": timestamp,
                    "state_vector": [float(value) for value in state],
                    "action_vector": [float(value) for value in action],
                }
            )
        except (TypeError, ValueError):
            return []
    return normalized


def _canonicalize_source_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            return []
        normalized_row = _normalize_source_value(row)
        if not isinstance(normalized_row, dict):
            return []
        normalized.append(normalized_row)
    return normalized


def _normalize_source_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int | float):
        if not math.isfinite(float(value)):
            return value
        return float(value)
    if isinstance(value, list):
        return [_normalize_source_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_source_value(value[key]) for key in sorted(value)}
    return value


def _scan_all_claims(package_dir: Path, issues: list[str]) -> None:
    for path in sorted(package_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".md", ".txt", ".html"}:
            label = path.relative_to(package_dir).as_posix()
            if label.startswith("data/source_drops/corrupt/"):
                continue
            if path.suffix.lower() in {".md", ".txt", ".html"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                _scan_text_for_positive_claims(text, label, issues)
            if path.suffix.lower() == ".json":
                payload = _read_json(path, issues, label)
                _scan_forbidden_true_claims(payload, label, issues)
                _scan_string_values_for_positive_claims(payload, label, issues)
            elif path.suffix.lower() == ".jsonl":
                for row in _read_jsonl(path, issues):
                    _scan_forbidden_true_claims(row, label, issues)
                    _scan_string_values_for_positive_claims(row, label, issues)


def _scan_text_for_positive_claims(text: str, label: str, issues: list[str]) -> None:
    cleaned = html.unescape(re.sub(r"<[^>]*>", " ", text.lower()))
    cleaned = re.sub(r"[_/\\-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    for phrase in FORBIDDEN_POSITIVE_PHRASES:
        for match in re.finditer(re.escape(phrase), cleaned):
            prefix = cleaned[max(0, match.start() - 50) : match.start()]
            if re.search(r"(?:\bno\b|\bnot\b|\bwithout\b|\bfalse\b|\bdoes not\b|\bdo not\b|\bis not\b)(?:\s+\w+){0,3}\s+$", prefix):
                continue
            issues.append(f"{label} forbidden positive claim phrase: {phrase}")


def _scan_forbidden_true_claims(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_CLAIMS and value is True:
                issues.append(f"{label} forbidden claim {key} leaked true")
            _scan_forbidden_true_claims(value, label, issues)
    elif isinstance(payload, list):
        for item in payload:
            _scan_forbidden_true_claims(item, label, issues)


def _scan_string_values_for_positive_claims(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for value in payload.values():
            _scan_string_values_for_positive_claims(value, label, issues)
    elif isinstance(payload, list):
        for item in payload:
            _scan_string_values_for_positive_claims(item, label, issues)
    elif isinstance(payload, str):
        _scan_text_for_positive_claims(payload, label, issues)


def _scan_spent_seeds(package_dir: Path, issues: list[str]) -> None:
    for path in sorted((package_dir / "data").rglob("*.json")):
        payload = _read_json(path, issues, path.relative_to(package_dir).as_posix())
        _scan_seed_payload(payload, path.relative_to(package_dir).as_posix(), issues)
    for path in sorted((package_dir / "data").rglob("*.jsonl")):
        for row in _read_jsonl(path, issues):
            _scan_seed_payload(row, path.relative_to(package_dir).as_posix(), issues)


def _scan_seed_payload(payload: Any, label: str, issues: list[str], key_path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{key_path}.{key}" if key_path else str(key)
            if "seed" in str(key).lower():
                for seed in _iter_ints(value):
                    if any(start <= seed <= end for start, end in SPENT_SEED_RANGES):
                        issues.append(f"{label} seed-like field {next_path} reuses spent seed {seed}")
            _scan_seed_payload(value, label, issues, next_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _scan_seed_payload(item, label, issues, f"{key_path}[{index}]")


def _iter_ints(value: Any) -> list[int]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        out: list[int] = []
        for item in value:
            out.extend(_iter_ints(item))
        return out
    if isinstance(value, dict):
        dict_out: list[int] = []
        for item in value.values():
            dict_out.extend(_iter_ints(item))
        return dict_out
    return []


def _source_hashes(source_dir: Path) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    if not source_dir.exists():
        return hashes
    for path in sorted(source_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(source_dir).as_posix()
            hashes[rel] = {"sha256": _sha256_file(path), "byte_size": path.stat().st_size}
    return hashes


def _read_json(path: Path, issues: list[str], label: str, *, missing_issue: str | None = None) -> dict[str, Any]:
    if not path.exists():
        issues.append(missing_issue or f"{label} missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(f"{label} invalid json: {exc}")
        return {}
    if not isinstance(payload, dict):
        issues.append(f"{label} must be object")
        return {}
    return payload


def _read_jsonl(path: Path, issues: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        issues.append("schema_missing_required_artifact")
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            issues.append("schema_type_mismatch")
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            issues.append("schema_type_mismatch")
    return rows


def _json_array(value: Any, issues: list[str]) -> list[Any]:
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
    return parsed if isinstance(parsed, list) else []


def _float(value: Any) -> float:
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


def _distance(left: Any, right: Any) -> float:
    if not isinstance(left, list) or not isinstance(right, list) or len(left) != len(right):
        return math.inf
    try:
        return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)))
    except (TypeError, ValueError):
        return math.inf


def _rigid_transform(matrix: list[Any]) -> bool:
    if not _numeric_vector(matrix, 16):
        return False
    rows = [
        [float(matrix[0]), float(matrix[1]), float(matrix[2])],
        [float(matrix[4]), float(matrix[5]), float(matrix[6])],
        [float(matrix[8]), float(matrix[9]), float(matrix[10])],
    ]
    for row in rows:
        norm = math.sqrt(sum(value * value for value in row))
        if abs(norm - 1.0) > 0.05:
            return False
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    return abs(determinant - 1.0) <= 0.05


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_manifest", type=Path)
    parser.add_argument("--allow-contract-ready", action="store_true")
    parser.add_argument("--deep-hdf5", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = verify_package(
        args.package_manifest,
        allow_contract_ready=args.allow_contract_ready,
        deep_hdf5=args.deep_hdf5,
    )
    if result["ok"]:
        print("VERDICT: VERIFIED")
        print(f"status={result['status']}")
        print(f"file_drop_rehearsal_ready={str(result['file_drop_rehearsal_ready']).lower()}")
        print(f"golden_profile_count={result['golden_profile_count']}")
        print(f"corrupt_case_count={result['corrupt_case_count']}")
        return 0
    print("VERDICT: FAILED")
    print(f"status={result['status']}")
    print(f"file_drop_rehearsal_ready={str(result['file_drop_rehearsal_ready']).lower()}")
    for issue in result["issues"]:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
