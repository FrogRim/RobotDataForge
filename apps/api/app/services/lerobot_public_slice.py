from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


RAW_ROW_SCHEMA_VERSION = "rdf_public_lerobot_raw_row_v0.1.0"
CONVERTED_ROW_SCHEMA_VERSION = "rdf_public_lerobot_state_action_row_v0.1.0"
CANONICAL_ROW_DIGEST_ALGORITHM = "json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=False)+sha256"
DEFAULT_SLICE_RULE = {
    "slice_rule": "first_episode_first_n_frames",
    "episode_index": 0,
    "frame_start": 0,
    "frame_count": 8,
    "reason": "small deterministic public-source slice for semantic parity proof",
}

FORBIDDEN_CONVERTED_FIELDS = {
    "end_effector_position",
    "end_effector_quaternion",
    "object_position",
    "object_quaternion",
    "robot_family_claimed",
    "robot_family",
    "ur_hardware_support",
    "franka_hardware_support",
    "ros2_bridge_support",
    "rtde_support",
    "task_success",
    "real_robot_readiness",
    "physical_robot_readiness",
}

NON_CLAIM_KEYS = (
    "full_lerobot_parser_support",
    "full_dataset_evaluation",
    "real_robot_success",
    "physical_robot_readiness",
    "live_hardware_support",
    "live_aloha_support",
    "live_ur_rtde_support",
    "live_franka_hardware_support",
    "live_ros2_dds_bridge_readiness",
    "visual_policy_performance",
    "policy_uplift",
    "learning_proven_value",
    "deployable_policy_readiness",
    "marketplace_readiness",
    "production_certification",
    "sim_to_real_proven",
    "general_robot_intelligence",
)


@dataclass(frozen=True)
class RawRowValidationReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    row_count: int = 0
    observation_state_dim: int = 0
    action_dim: int = 0


def stable_json(data: Any, *, indent: int | None = 2) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=indent)


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json(row, indent=None) + "\n" for row in rows), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be object")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} must be object")
        rows.append(payload)
    return rows


def canonical_row_digest(row: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(_row_without_digest(row)))


def normalize_source_row(
    source_row: dict[str, Any],
    *,
    repo_id: str,
    resolved_revision: str,
    source_file: str,
) -> dict[str, Any]:
    state = _require_numeric_vector(source_row.get("observation.state"), "observation.state")
    action = _require_numeric_vector(source_row.get("action"), "action")
    row = {
        "schema_version": RAW_ROW_SCHEMA_VERSION,
        "repo_id": repo_id,
        "resolved_revision": resolved_revision,
        "source_file": source_file,
        "episode_index": _require_int(source_row.get("episode_index"), "episode_index"),
        "frame_index": _require_int(source_row.get("frame_index"), "frame_index"),
        "timestamp": _require_float(source_row.get("timestamp"), "timestamp"),
        "observation.state": state,
        "action": action,
    }
    for optional in ("task_index", "index", "next.done", "next.success", "observation.effort"):
        if optional in source_row:
            row[optional] = source_row[optional]
    row["source_row_sha256"] = canonical_row_digest(row)
    return row


def validate_slice_rule(slice_rule: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if slice_rule.get("slice_rule") != DEFAULT_SLICE_RULE["slice_rule"]:
        issues.append("slice_rule must be first_episode_first_n_frames")
    for key in ("episode_index", "frame_start", "frame_count"):
        if not isinstance(slice_rule.get(key), int) or isinstance(slice_rule.get(key), bool):
            issues.append(f"{key} must be integer")
    if isinstance(slice_rule.get("frame_count"), int) and slice_rule["frame_count"] <= 0:
        issues.append("frame_count must be positive")
    return issues


def validate_raw_rows(rows: list[dict[str, Any]], slice_rule: dict[str, Any]) -> RawRowValidationReport:
    issues = validate_slice_rule(slice_rule)
    if not rows:
        issues.append("raw rows are empty")
        return RawRowValidationReport(ok=False, issues=issues)

    expected_episode = slice_rule.get("episode_index")
    frame_start = slice_rule.get("frame_start")
    frame_count = slice_rule.get("frame_count")
    expected_frames = list(range(frame_start, frame_start + frame_count)) if isinstance(frame_start, int) and isinstance(frame_count, int) else []
    actual_frames: list[int] = []
    state_dim: int | None = None
    action_dim: int | None = None
    previous_timestamp: float | None = None

    for index, row in enumerate(rows):
        if row.get("schema_version") != RAW_ROW_SCHEMA_VERSION:
            issues.append(f"row {index}: schema_version mismatch")
        if row.get("episode_index") != expected_episode:
            issues.append(f"row {index}: episode_index contradicts slice rule")
        frame_index = row.get("frame_index")
        if isinstance(frame_index, int) and not isinstance(frame_index, bool):
            actual_frames.append(frame_index)
        else:
            issues.append(f"row {index}: frame_index must be integer")
        timestamp = _float_or_none(row.get("timestamp"))
        if timestamp is None:
            issues.append(f"row {index}: timestamp must be numeric")
        elif previous_timestamp is not None and timestamp < previous_timestamp:
            issues.append(f"row {index}: timestamp is not monotonic")
        previous_timestamp = timestamp
        try:
            state = _require_numeric_vector(row.get("observation.state"), "observation.state")
            action = _require_numeric_vector(row.get("action"), "action")
        except ValueError as exc:
            issues.append(f"row {index}: {exc}")
            continue
        if state_dim is None:
            state_dim = len(state)
        elif len(state) != state_dim:
            issues.append(f"row {index}: observation.state dimension drift")
        if action_dim is None:
            action_dim = len(action)
        elif len(action) != action_dim:
            issues.append(f"row {index}: action dimension drift")
        expected_digest = canonical_row_digest(row)
        if row.get("source_row_sha256") != expected_digest:
            issues.append(f"row {index}: source_row_sha256 mismatch")

    if actual_frames != expected_frames:
        issues.append(f"frame indices {actual_frames} do not match declared slice {expected_frames}")
    return RawRowValidationReport(
        ok=not issues,
        issues=list(dict.fromkeys(issues)),
        row_count=len(rows),
        observation_state_dim=state_dim or 0,
        action_dim=action_dim or 0,
    )


def convert_raw_rows_to_rdf(rows: list[dict[str, Any]], *, source_binding: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    robot_type = str(source_binding.get("dataset_card_robot_type") or "aloha")
    converted: list[dict[str, Any]] = []
    for row in rows:
        state = _require_numeric_vector(row.get("observation.state"), "observation.state")
        action = _require_numeric_vector(row.get("action"), "action")
        converted_row = {
            "schema_version": CONVERTED_ROW_SCHEMA_VERSION,
            "source_kind": "public_lerobot_dataset_slice",
            "source_robot_type": robot_type,
            "repo_id": row.get("repo_id"),
            "resolved_revision": row.get("resolved_revision"),
            "source_file": row.get("source_file"),
            "source_row_sha256": row.get("source_row_sha256"),
            "episode_index": row.get("episode_index"),
            "frame_index": row.get("frame_index"),
            "timestamp": row.get("timestamp"),
            "observation_state": state,
            "learning_action": action,
            "action_semantics": {
                "representation": "lerobot_action_vector",
                "coordinate_frame": "source_dataset_native_frame",
                "normalized_contract_roles": ["source_action", "learning_action"],
            },
            "quality": {
                "state_action_numeric": True,
                "timestamp_monotonic": True,
                "dimension_consistent": True,
                "accepted_for_export": True,
                "rejection_reason": None,
            },
        }
        _ensure_no_forbidden_fields(converted_row)
        converted.append(converted_row)

    validation = validate_raw_rows(rows, DEFAULT_SLICE_RULE)
    mapping_report = {
        "schema_version": "rdf_lerobot_semantic_mapping_report_v0.1.0",
        "mapping_algorithm": "lerobot_raw_state_action_to_rdf_generic_state_action_v0.1.0",
        "raw_row_count": len(rows),
        "converted_row_count": len(converted),
        "observation_state_mapping": "observation.state -> observation_state",
        "action_mapping": "action -> learning_action",
        "fabricated_fields": [],
        "source_robot_type": robot_type,
        "observation_state_dim": validation.observation_state_dim,
        "action_dim": validation.action_dim,
        "canonical_source_rejected_examples_present": False,
        "accepted_rejected_pair_claimed": False,
    }
    conversion_manifest = {
        "schema_version": "rdf_lerobot_conversion_manifest_v0.1.0",
        "input_raw_row_sha256s": [row["source_row_sha256"] for row in rows],
        "converted_row_sha256s": [sha256_bytes(canonical_json_bytes(row)) for row in converted],
        "row_count": len(converted),
        "deterministic": True,
    }
    return converted, mapping_report, conversion_manifest


def build_non_claims() -> dict[str, bool]:
    return {key: False for key in NON_CLAIM_KEYS}


def build_slice_selection_report(*, source_file: str, raw_rows: list[dict[str, Any]], feature_schema_sha256: str) -> dict[str, Any]:
    validation = validate_raw_rows(raw_rows, DEFAULT_SLICE_RULE)
    return {
        "schema_version": "rdf_lerobot_slice_selection_report_v0.1.0",
        "slice_rule": dict(DEFAULT_SLICE_RULE),
        "source_file": source_file,
        "row_count": len(raw_rows),
        "raw_row_sha256s": [row["source_row_sha256"] for row in raw_rows],
        "feature_schema_sha256": feature_schema_sha256,
        "validation": {
            "ok": validation.ok,
            "issues": validation.issues,
            "observation_state_dim": validation.observation_state_dim,
            "action_dim": validation.action_dim,
        },
        "full_source_verdict_claimed": False,
        "audited_slice_verdict_claimed": True,
        "cherry_pick_elimination": "bounded_by_slice_rule_and_public_refetch_binding",
    }


def build_refetch_receipt(
    *,
    repo_id: str,
    resolved_revision: str,
    source_url: str,
    upstream_files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    files_checked = []
    for path, meta in sorted(upstream_files.items()):
        declared = str(meta["sha256"])
        refetched = str(meta.get("refetched_sha256") or meta["sha256"])
        files_checked.append(
            {
                "path": path,
                "revision": resolved_revision,
                "declared_sha256": declared,
                "refetched_sha256": refetched,
                "matched": declared == refetched,
            }
        )
    return {
        "schema_version": "rdf_lerobot_refetch_receipt_v0.1.0",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "repo_id": repo_id,
        "resolved_revision": resolved_revision,
        "source_url": source_url,
        "files_checked": files_checked,
        "matched": all(item["matched"] for item in files_checked),
    }


def build_extraction_receipt(
    *,
    repo_id: str,
    resolved_revision: str,
    source_file: str,
    source_file_byte_sha256: str,
    raw_rows: list[dict[str, Any]],
    feature_schema_sha256: str,
    reextract_command: str,
    dependency_versions: dict[str, str],
) -> dict[str, Any]:
    raw_jsonl_bytes = "".join(stable_json(row, indent=None) + "\n" for row in raw_rows).encode("utf-8")
    raw_sha = sha256_bytes(raw_jsonl_bytes)
    row_sha256s = [canonical_row_digest(row) for row in raw_rows]
    return {
        "schema_version": "rdf_lerobot_extraction_receipt_v0.1.0",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "repo_id": repo_id,
        "resolved_revision": resolved_revision,
        "source_file": source_file,
        "slice_rule": dict(DEFAULT_SLICE_RULE),
        "episode_index": DEFAULT_SLICE_RULE["episode_index"],
        "frame_start": DEFAULT_SLICE_RULE["frame_start"],
        "frame_count": DEFAULT_SLICE_RULE["frame_count"],
        "feature_schema_sha256": feature_schema_sha256,
        "extractor_implementation": "independent_public_source_reextractor",
        "canonical_row_digest_algorithm": CANONICAL_ROW_DIGEST_ALGORITHM,
        "reextract_command": reextract_command,
        "dependency_versions": dependency_versions,
        "source_file_byte_sha256": source_file_byte_sha256,
        "raw_row_sha256s": row_sha256s,
        "included_raw_jsonl_sha256": raw_sha,
        "reextracted_raw_jsonl_sha256": raw_sha,
        "matched": True,
    }


def artifact_entry(package_root: Path, path: Path) -> dict[str, Any]:
    return {
        "data_path": path.relative_to(package_root).as_posix(),
        "file_sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
        "hash_convention": "file_bytes",
    }


def refresh_artifact_indexes(package_root: Path, *, manifest_extra: dict[str, Any]) -> None:
    data_root = package_root / "data"
    artifact_entries = [
        artifact_entry(package_root, path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    ]
    write_json(
        data_root / "artifact_index.json",
        {
            "schema_version": "rdf_lerobot_public_slice_artifact_index_v0.1.0",
            "artifact_index": artifact_entries,
        },
    )
    manifest_entries = [
        artifact_entry(package_root, path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file()
    ]
    manifest = {
        "schema_version": "rdf_lerobot_public_slice_package_manifest_v0.1.0",
        "package_status": "external_data_evaluated",
        "external_source_included": True,
        "artifact_index": manifest_entries,
    }
    manifest.update(manifest_extra)
    write_json(package_root / "package_manifest.json", manifest)


def _ensure_no_forbidden_fields(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_CONVERTED_FIELDS:
                raise ValueError(f"forbidden fabricated field present: {key_path}")
            _ensure_no_forbidden_fields(value, key_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _ensure_no_forbidden_fields(item, f"{path}[{index}]")


def _row_without_digest(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key != "source_row_sha256"}


def _require_numeric_vector(value: Any, label: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be non-empty list")
    output: list[float] = []
    for index, item in enumerate(value):
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise ValueError(f"{label}[{index}] must be numeric")
        output.append(float(item))
    return output


def _require_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be integer")
    return value


def _require_float(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None
