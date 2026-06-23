from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry


SOURCE_METADATA_SCHEMA_VERSION = "rdf_external_command_state_source_metadata_v0.1.0"

PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY = "external_ingest_contract_ready"
PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED = "external_data_evaluated"
ALLOWED_PACKAGE_STATUSES = {
    PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY,
    PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED,
}

ALLOWED_SOURCE_ORIGINS = {
    "external_supplied_recorded_log",
    "public_dataset_recorded_log",
}
ALLOWED_PROVENANCE_TRUST_TIERS = {
    "attested_file_drop",
    "refetchable_public_source",
}

DEFAULT_EXTERNAL_ADAPTER_ID = "universal_robots_ur_industrial_arm"
STAGING_DERIVATION_ALGORITHM = "rdf_external_ingest_adapter_staging_v0.1.0"

REQUIRED_RAW_METADATA_FIELDS = (
    "schema_version",
    "source_id",
    "source_origin",
    "source_acquisition",
    "source_owner",
    "source_license",
    "source_redistribution_allowed",
    "provenance_trust_tier",
    "recorded_log_backed",
    "generated_by_rdf",
    "repo_fixture",
    "robot_family_claimed",
    "embodiment_class_claimed",
    "command_stream",
    "state_stream",
    "coordinate_frames_declared",
)

REQUIRED_ROW_PATHS = (
    "sequence_id",
    "timestamp",
    "task_phase",
    "command.interface",
    "command.unit",
    "command.vector",
    "state.interface",
    "state.joint_positions",
    "state.end_effector_position",
    "state.end_effector_quaternion",
    "state.object_position",
    "state.object_quaternion",
    "action_semantics.representation",
    "action_semantics.coordinate_frame",
    "action_semantics.normalized_contract_roles",
    "quality.action_contract_valid",
    "quality.replay_verified",
    "quality.control_quality",
    "quality.rejection_reason",
)

PLACEHOLDER_STRINGS = {
    "",
    "none",
    "n/a",
    "na",
    "null",
    "unknown",
    "todo",
    "tbd",
    "person_or_org_or_public_dataset",
    "public_license_name",
    "private_review|public_license_name|not_redistributable",
}

REPO_ROOT = Path(__file__).resolve().parents[4]
FORBIDDEN_EXTERNAL_DATA_ROOTS = (
    REPO_ROOT / "docs" / "proof",
    REPO_ROOT / "storage",
    REPO_ROOT / "fixtures",
    REPO_ROOT / ".omx",
    REPO_ROOT / ".superpowers",
)


@dataclass(frozen=True)
class ExternalSourceValidationReport:
    package_status: str
    source_dir: str
    ok: bool
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    accepted_rows: list[dict[str, Any]] = field(default_factory=list)
    rejected_rows: list[dict[str, Any]] = field(default_factory=list)
    source_file_hashes: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def accepted_count(self) -> int:
        return len(self.accepted_rows)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_rows)


@dataclass(frozen=True)
class AdapterStagingSourceReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    source_dir: str = ""
    staging_dir: str = ""
    selected_adapter_id: str = ""
    derivation_algorithm: str = STAGING_DERIVATION_ALGORITHM
    raw_metadata_sha256: str = ""
    source_accepted_sha256: str = ""
    source_rejected_sha256: str = ""
    derived_metadata_sha256: str = ""
    staging_accepted_sha256: str = ""
    staging_rejected_sha256: str = ""


def validate_external_source_dir(
    source_dir: Path | str,
    *,
    package_status: str,
) -> ExternalSourceValidationReport:
    """Validate an external command/state JSONL drop without mutating evidence."""

    source_path = Path(source_dir)
    issues: list[str] = []
    metadata: dict[str, Any] = {}
    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    if package_status not in ALLOWED_PACKAGE_STATUSES:
        issues.append(f"unknown package_status: {package_status}")
    if package_status == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED:
        issues.extend(_validate_source_path_for_external_data(source_path))

    metadata_path = source_path / "metadata.json"
    accepted_path = source_path / "accepted_command_state.jsonl"
    rejected_path = source_path / "rejected_command_state.jsonl"

    for required_path in (metadata_path, accepted_path, rejected_path):
        if not required_path.exists():
            issues.append(f"missing source file: {required_path.name}")

    if metadata_path.exists():
        metadata, metadata_issues = _read_json_object(metadata_path, label="metadata")
        issues.extend(metadata_issues)
        if metadata:
            issues.extend(_validate_raw_metadata(metadata, source_path, package_status=package_status))

    if accepted_path.exists():
        accepted_rows, accepted_issues = _read_jsonl_objects(accepted_path, label="accepted rows")
        issues.extend(accepted_issues)
    if rejected_path.exists():
        rejected_rows, rejected_issues = _read_jsonl_objects(rejected_path, label="rejected rows")
        issues.extend(rejected_issues)

    if metadata:
        issues.extend(_validate_rows(accepted_rows, metadata, label="accepted", accepted=True))
        issues.extend(_validate_rows(rejected_rows, metadata, label="rejected", accepted=False))

    if package_status == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED:
        if len(accepted_rows) < 4:
            issues.append("accepted_rows < 4")
        if len(rejected_rows) != 1:
            issues.append("rejected_rows must equal 1 for v0 committed/evaluated evidence")

    source_file_hashes = build_source_file_hash_manifest(source_path)
    return ExternalSourceValidationReport(
        package_status=package_status,
        source_dir=str(source_path),
        ok=not issues,
        issues=_dedupe(issues),
        metadata=metadata,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        source_file_hashes=source_file_hashes,
    )


def build_source_file_hash_manifest(source_dir: Path | str) -> dict[str, dict[str, Any]]:
    source_path = Path(source_dir)
    manifest: dict[str, dict[str, Any]] = {}
    for name in (
        "LICENSE.txt",
        "PROVENANCE.md",
        "accepted_command_state.jsonl",
        "metadata.json",
        "rejected_command_state.jsonl",
    ):
        path = source_path / name
        if path.exists() and path.is_file():
            manifest[name] = {
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
    return dict(sorted(manifest.items()))


def build_adapter_staging_source(
    source_dir: Path | str,
    staging_dir: Path | str,
    *,
    adapter_id: str | None = None,
) -> AdapterStagingSourceReport:
    source_path = Path(source_dir)
    staging_path = Path(staging_dir)
    validation = validate_external_source_dir(
        source_path,
        package_status=PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED,
    )
    issues = list(validation.issues)
    selected_adapter_id = adapter_id or _select_adapter_id(validation.metadata)
    if issues:
        return AdapterStagingSourceReport(
            ok=False,
            issues=issues,
            source_dir=str(source_path),
            staging_dir=str(staging_path),
            selected_adapter_id=selected_adapter_id,
        )

    staging_path.mkdir(parents=True, exist_ok=True)
    staging_metadata = derive_adapter_staging_metadata(validation.metadata, selected_adapter_id=selected_adapter_id)
    _write_json(staging_path / "metadata.json", staging_metadata)
    shutil.copyfile(source_path / "accepted_command_state.jsonl", staging_path / "accepted_command_state.jsonl")
    shutil.copyfile(source_path / "rejected_command_state.jsonl", staging_path / "rejected_command_state.jsonl")

    raw_metadata_sha256 = _sha256_file(source_path / "metadata.json")
    source_accepted_sha256 = _sha256_file(source_path / "accepted_command_state.jsonl")
    source_rejected_sha256 = _sha256_file(source_path / "rejected_command_state.jsonl")
    derived_metadata_sha256 = _sha256_file(staging_path / "metadata.json")
    staging_accepted_sha256 = _sha256_file(staging_path / "accepted_command_state.jsonl")
    staging_rejected_sha256 = _sha256_file(staging_path / "rejected_command_state.jsonl")
    derivation_report = {
        "schema_version": "rdf_external_ingest_staging_derivation_report_v0.1.0",
        "derivation_algorithm": STAGING_DERIVATION_ALGORITHM,
        "raw_metadata_sha256": raw_metadata_sha256,
        "source_accepted_sha256": source_accepted_sha256,
        "source_rejected_sha256": source_rejected_sha256,
        "selected_adapter_id": selected_adapter_id,
        "selected_adapter_profile_version": staging_metadata["adapter_version"],
        "derived_metadata_sha256": derived_metadata_sha256,
        "staging_accepted_sha256": staging_accepted_sha256,
        "staging_rejected_sha256": staging_rejected_sha256,
        "field_mapping": _staging_field_mapping(),
        "adapter_profile_constants": _adapter_profile_constants(selected_adapter_id),
    }
    _write_json(staging_path / "staging_derivation_report.json", derivation_report)
    return AdapterStagingSourceReport(
        ok=True,
        source_dir=str(source_path),
        staging_dir=str(staging_path),
        selected_adapter_id=selected_adapter_id,
        raw_metadata_sha256=raw_metadata_sha256,
        source_accepted_sha256=source_accepted_sha256,
        source_rejected_sha256=source_rejected_sha256,
        derived_metadata_sha256=derived_metadata_sha256,
        staging_accepted_sha256=staging_accepted_sha256,
        staging_rejected_sha256=staging_rejected_sha256,
    )


def verify_adapter_staging_source(
    source_dir: Path | str,
    staging_dir: Path | str,
) -> AdapterStagingSourceReport:
    source_path = Path(source_dir)
    staging_path = Path(staging_dir)
    issues: list[str] = []

    report_path = staging_path / "staging_derivation_report.json"
    derivation_report, report_issues = _read_json_object(report_path, label="staging_derivation_report")
    issues.extend(report_issues)
    raw_metadata, raw_issues = _read_json_object(source_path / "metadata.json", label="raw metadata")
    issues.extend(raw_issues)
    staging_metadata, staging_issues = _read_json_object(staging_path / "metadata.json", label="staging metadata")
    issues.extend(staging_issues)
    selected_adapter_id = str(derivation_report.get("selected_adapter_id") or DEFAULT_EXTERNAL_ADAPTER_ID)

    actual_raw_metadata_sha256 = _sha256_if_exists(source_path / "metadata.json")
    actual_source_accepted_sha256 = _sha256_if_exists(source_path / "accepted_command_state.jsonl")
    actual_source_rejected_sha256 = _sha256_if_exists(source_path / "rejected_command_state.jsonl")
    actual_derived_metadata_sha256 = _sha256_if_exists(staging_path / "metadata.json")
    actual_staging_accepted_sha256 = _sha256_if_exists(staging_path / "accepted_command_state.jsonl")
    actual_staging_rejected_sha256 = _sha256_if_exists(staging_path / "rejected_command_state.jsonl")

    _check_report_hash(issues, derivation_report, "raw_metadata_sha256", actual_raw_metadata_sha256)
    _check_report_hash(issues, derivation_report, "source_accepted_sha256", actual_source_accepted_sha256)
    _check_report_hash(issues, derivation_report, "source_rejected_sha256", actual_source_rejected_sha256)
    _check_report_hash(issues, derivation_report, "derived_metadata_sha256", actual_derived_metadata_sha256)
    _check_report_hash(issues, derivation_report, "staging_accepted_sha256", actual_staging_accepted_sha256)
    _check_report_hash(issues, derivation_report, "staging_rejected_sha256", actual_staging_rejected_sha256)

    if actual_staging_accepted_sha256 != actual_source_accepted_sha256:
        issues.append("staging_accepted_sha256 differs from source accepted sha256")
    if actual_staging_rejected_sha256 != actual_source_rejected_sha256:
        issues.append("staging_rejected_sha256 differs from source rejected sha256")

    if raw_metadata and staging_metadata:
        expected_metadata = derive_adapter_staging_metadata(raw_metadata, selected_adapter_id=selected_adapter_id)
        expected_metadata_sha256 = _sha256_bytes((_stable_json(expected_metadata) + "\n").encode("utf-8"))
        if actual_derived_metadata_sha256 != expected_metadata_sha256:
            issues.append("derived staging metadata mismatch")

    return AdapterStagingSourceReport(
        ok=not issues,
        issues=_dedupe(issues),
        source_dir=str(source_path),
        staging_dir=str(staging_path),
        selected_adapter_id=selected_adapter_id,
        raw_metadata_sha256=actual_raw_metadata_sha256,
        source_accepted_sha256=actual_source_accepted_sha256,
        source_rejected_sha256=actual_source_rejected_sha256,
        derived_metadata_sha256=actual_derived_metadata_sha256,
        staging_accepted_sha256=actual_staging_accepted_sha256,
        staging_rejected_sha256=actual_staging_rejected_sha256,
    )


def derive_adapter_staging_metadata(
    raw_metadata: dict[str, Any],
    *,
    selected_adapter_id: str | None = None,
) -> dict[str, Any]:
    adapter_id = selected_adapter_id or _select_adapter_id(raw_metadata)
    profile = RobotEmbodimentAdapterRegistry.get(adapter_id)
    command_profile = profile.builder_class().command_state_stream_profile
    return {
        "schema_version": "rdf_external_ingest_adapter_staging_metadata_v0.1.0",
        "adapter_id": profile.adapter_id,
        "adapter_name": profile.adapter_name,
        "adapter_version": profile.adapter_version,
        "robot_family": profile.robot_family,
        "embodiment_class": profile.embodiment_class,
        "command_state_interface": command_profile["command_interface"],
        "command_state_transport": command_profile["transport"],
        "state_interface": command_profile["state_interface"],
        "coordinate_frames": {
            "command_frame": "task_frame",
            "state_frame": "robot_base_frame",
            "normalization_frame": "rdf_normalized_task_frame",
        },
        "evidence_level": profile.evidence_level,
        "source_profile": "external_jsonl_command_state_drop",
        "runtime": "external_recorded_log_file_drop",
        "source_provenance": {
            "source_type": "external_jsonl_command_state_drop",
            "external_source_id": raw_metadata.get("source_id"),
            "source_origin": raw_metadata.get("source_origin"),
            "source_acquisition": raw_metadata.get("source_acquisition"),
            "source_owner": raw_metadata.get("source_owner"),
            "source_license": raw_metadata.get("source_license"),
            "provenance_trust_tier": raw_metadata.get("provenance_trust_tier"),
            "recorded_log_backed": raw_metadata.get("recorded_log_backed") is True,
            "generated_external_style_sample": profile.generated_external_style_sample,
            "public_sample_evidence_claimed": False,
        },
        "capabilities": list(profile.capabilities),
        "claim_boundary": dict(profile.claim_boundary),
        "limitations": [
            *profile.limitations,
            "Adapter-compatible staging metadata derived from immutable raw external metadata.",
            "Offline verifier checks data-evaluation consistency, not physical origin.",
        ],
        "generated_external_style_sample": profile.generated_external_style_sample,
        "public_sample_evidence_claimed": False,
    }


def _select_adapter_id(raw_metadata: dict[str, Any]) -> str:
    robot_family = raw_metadata.get("robot_family_claimed")
    embodiment_class = raw_metadata.get("embodiment_class_claimed")
    for profile in RobotEmbodimentAdapterRegistry.list_profiles():
        if profile.robot_family == robot_family and profile.embodiment_class == embodiment_class:
            return profile.adapter_id
    return DEFAULT_EXTERNAL_ADAPTER_ID


def _staging_field_mapping() -> dict[str, str]:
    return {
        "raw.source_id": "staging.source_provenance.external_source_id",
        "raw.source_origin": "staging.source_provenance.source_origin",
        "raw.source_acquisition": "staging.source_provenance.source_acquisition",
        "raw.source_owner": "staging.source_provenance.source_owner",
        "raw.source_license": "staging.source_provenance.source_license",
        "raw.provenance_trust_tier": "staging.source_provenance.provenance_trust_tier",
        "raw.recorded_log_backed": "staging.source_provenance.recorded_log_backed",
        "adapter_profile.adapter_id": "staging.adapter_id",
        "adapter_profile.adapter_version": "staging.adapter_version",
        "adapter_profile.command_state_stream_profile": "staging.command_state_interface/state_interface",
    }


def _adapter_profile_constants(adapter_id: str) -> dict[str, Any]:
    profile = RobotEmbodimentAdapterRegistry.get(adapter_id)
    command_profile = profile.builder_class().command_state_stream_profile
    return {
        "adapter_id": profile.adapter_id,
        "adapter_name": profile.adapter_name,
        "adapter_version": profile.adapter_version,
        "robot_family": profile.robot_family,
        "embodiment_class": profile.embodiment_class,
        "command_state_interface": command_profile["command_interface"],
        "command_state_transport": command_profile["transport"],
        "state_interface": command_profile["state_interface"],
        "evidence_level": profile.evidence_level,
        "generated_external_style_sample": profile.generated_external_style_sample,
    }


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n", encoding="utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_if_exists(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return _sha256_file(path)


def _check_report_hash(
    issues: list[str],
    derivation_report: dict[str, Any],
    key: str,
    actual_sha256: str,
) -> None:
    expected_sha256 = derivation_report.get(key)
    if expected_sha256 != actual_sha256:
        issues.append(f"{key} mismatch")


def _validate_source_path_for_external_data(source_dir: Path) -> list[str]:
    resolved = source_dir.resolve()
    issues: list[str] = []
    for root in FORBIDDEN_EXTERNAL_DATA_ROOTS:
        if _is_relative_to(resolved, root.resolve()):
            issues.append(f"forbidden source path for external_data_evaluated: {resolved}")
            break
    return issues


def _validate_raw_metadata(
    metadata: dict[str, Any],
    source_dir: Path,
    *,
    package_status: str,
) -> list[str]:
    issues: list[str] = []
    for key in REQUIRED_RAW_METADATA_FIELDS:
        if key not in metadata:
            issues.append(f"metadata.{key} missing")

    if metadata.get("schema_version") != SOURCE_METADATA_SCHEMA_VERSION:
        issues.append("metadata.schema_version mismatch")
    if metadata.get("source_origin") not in ALLOWED_SOURCE_ORIGINS:
        issues.append("metadata.source_origin unsupported")
    if metadata.get("provenance_trust_tier") not in ALLOWED_PROVENANCE_TRUST_TIERS:
        issues.append("metadata.provenance_trust_tier unsupported")
    if metadata.get("recorded_log_backed") is not True:
        issues.append("metadata.recorded_log_backed must be true")
    if metadata.get("generated_by_rdf") is not False:
        issues.append("metadata.generated_by_rdf must be false")
    if metadata.get("repo_fixture") is not False:
        issues.append("metadata.repo_fixture must be false")
    if package_status == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED and metadata.get("source_redistribution_allowed") is not True:
        issues.append("metadata.source_redistribution_allowed must be true for external_data_evaluated")

    if _is_placeholder(metadata.get("source_owner")):
        issues.append("metadata.source_owner placeholder")
    if _is_placeholder(metadata.get("source_license")):
        issues.append("metadata.source_license placeholder")

    command_stream = metadata.get("command_stream")
    if not isinstance(command_stream, dict):
        issues.append("metadata.command_stream must be object")
    else:
        if _is_placeholder(command_stream.get("interface")):
            issues.append("metadata.command_stream.interface missing")
        if _is_placeholder(command_stream.get("unit")):
            issues.append("metadata.command_stream.unit missing")

    state_stream = metadata.get("state_stream")
    if not isinstance(state_stream, dict):
        issues.append("metadata.state_stream must be object")
    elif _is_placeholder(state_stream.get("interface")):
        issues.append("metadata.state_stream.interface missing")

    coordinate_frames = metadata.get("coordinate_frames_declared")
    if not isinstance(coordinate_frames, dict):
        issues.append("metadata.coordinate_frames_declared must be object")
    elif _is_placeholder(coordinate_frames.get("command_frame")) or _is_placeholder(coordinate_frames.get("state_frame")):
        issues.append("metadata.coordinate_frames_declared command_frame/state_frame missing")

    if metadata.get("provenance_trust_tier") == "refetchable_public_source":
        issues.extend(_validate_refetchable_public_source(metadata, source_dir))
    return issues


def _validate_refetchable_public_source(metadata: dict[str, Any], source_dir: Path) -> list[str]:
    issues: list[str] = []
    if _is_placeholder(metadata.get("public_source_url")):
        issues.append("metadata.public_source_url required for refetchable_public_source")
    if _is_placeholder(metadata.get("upstream_dataset_revision")):
        issues.append("metadata.upstream_dataset_revision required for refetchable_public_source")
    upstream_hash = metadata.get("upstream_published_sha256")
    if _is_placeholder(upstream_hash):
        issues.append("metadata.upstream_published_sha256 required for refetchable_public_source")
    elif not _is_sha256_hex(upstream_hash):
        issues.append("metadata.upstream_published_sha256 must be sha256 hex")
    if metadata.get("source_origin") != "public_dataset_recorded_log":
        issues.append("metadata.source_origin must be public_dataset_recorded_log for refetchable_public_source")
    if not (source_dir / "LICENSE.txt").exists():
        issues.append("LICENSE.txt required for refetchable_public_source")
    return issues


def _validate_rows(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    label: str,
    accepted: bool,
) -> list[str]:
    issues: list[str] = []
    previous_timestamp: float | int | None = None
    for index, row in enumerate(rows, start=1):
        row_label = f"{label} row {index}"
        issues.extend(_validate_required_row_paths(row, row_label))
        timestamp = _get_path(row, "timestamp")
        if _is_number(timestamp):
            if previous_timestamp is not None and timestamp < previous_timestamp:
                issues.append(f"{label} rows timestamps must be monotonic")
            previous_timestamp = timestamp
        elif "timestamp" in row:
            issues.append(f"{row_label} timestamp must be numeric")
        issues.extend(_validate_row_shapes(row, metadata, row_label))
        issues.extend(_validate_row_quality(row, row_label, accepted=accepted))
    return _dedupe(issues)


def _validate_required_row_paths(row: dict[str, Any], row_label: str) -> list[str]:
    issues: list[str] = []
    for path in REQUIRED_ROW_PATHS:
        if not _has_path(row, path):
            issues.append(f"{row_label} {path} missing")
    return issues


def _validate_row_shapes(row: dict[str, Any], metadata: dict[str, Any], row_label: str) -> list[str]:
    issues: list[str] = []
    command_stream = metadata.get("command_stream") if isinstance(metadata.get("command_stream"), dict) else {}
    state_stream = metadata.get("state_stream") if isinstance(metadata.get("state_stream"), dict) else {}
    coordinate_frames = (
        metadata.get("coordinate_frames_declared")
        if isinstance(metadata.get("coordinate_frames_declared"), dict)
        else {}
    )

    if _get_path(row, "command.interface") != command_stream.get("interface"):
        issues.append(f"{row_label} command.interface mismatch")
    if _get_path(row, "command.unit") != command_stream.get("unit"):
        issues.append(f"{row_label} command.unit mismatch")
    if _get_path(row, "state.interface") != state_stream.get("interface"):
        issues.append(f"{row_label} state.interface mismatch")
    if _get_path(row, "action_semantics.coordinate_frame") != coordinate_frames.get("command_frame"):
        issues.append(f"{row_label} action_semantics.coordinate_frame mismatch")

    if not _numeric_vector(_get_path(row, "command.vector"), min_len=1):
        issues.append(f"{row_label} command.vector must be numeric vector")
    if not _numeric_vector(_get_path(row, "state.joint_positions"), min_len=1):
        issues.append(f"{row_label} state.joint_positions must be numeric vector")
    if not _numeric_vector(_get_path(row, "state.end_effector_position"), min_len=3, max_len=3):
        issues.append(f"{row_label} state.end_effector_position must be numeric vector length 3")
    if not _numeric_vector(_get_path(row, "state.end_effector_quaternion"), min_len=4, max_len=4):
        issues.append(f"{row_label} state.end_effector_quaternion must be numeric vector length 4")
    if not _numeric_vector(_get_path(row, "state.object_position"), min_len=3, max_len=3):
        issues.append(f"{row_label} state.object_position must be numeric vector length 3")
    if not _numeric_vector(_get_path(row, "state.object_quaternion"), min_len=4, max_len=4):
        issues.append(f"{row_label} state.object_quaternion must be numeric vector length 4")

    roles = _get_path(row, "action_semantics.normalized_contract_roles")
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        issues.append(f"{row_label} action_semantics.normalized_contract_roles must be string list")
    elif "learning_action" not in roles:
        issues.append(f"{row_label} action_semantics.normalized_contract_roles missing learning_action")
    return issues


def _validate_row_quality(row: dict[str, Any], row_label: str, *, accepted: bool) -> list[str]:
    issues: list[str] = []
    action_contract_valid = _get_path(row, "quality.action_contract_valid")
    replay_verified = _get_path(row, "quality.replay_verified")
    control_quality = _get_path(row, "quality.control_quality")
    rejection_reason = _get_path(row, "quality.rejection_reason")
    if accepted:
        if action_contract_valid is not True:
            issues.append(f"{row_label} quality.action_contract_valid must be true")
        if replay_verified is not True:
            issues.append(f"{row_label} quality.replay_verified must be true")
        if control_quality != "pass":
            issues.append(f"{row_label} quality.control_quality must be pass")
        if rejection_reason is not None:
            issues.append(f"{row_label} quality.rejection_reason must be null")
        return issues

    has_failure_predicate = (
        action_contract_valid is False
        or replay_verified is False
        or control_quality == "fail"
        or (isinstance(rejection_reason, str) and bool(rejection_reason.strip()))
    )
    if not has_failure_predicate:
        issues.append(f"{row_label} must include a failure predicate or rejection reason")
    return issues


def _read_json_object(path: Path, *, label: str) -> tuple[dict[str, Any], list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"{label} invalid json: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"{label} must be object"]
    return payload, []


def _read_jsonl_objects(path: Path, *, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"{label} unreadable: {exc}"]
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{label} line {index} invalid json: {exc}")
            continue
        if not isinstance(row, dict):
            issues.append(f"{label} line {index} must be object")
            continue
        rows.append(row)
    return rows, issues


def _get_path(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _has_path(payload: dict[str, Any], dotted_path: str) -> bool:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _numeric_vector(value: Any, *, min_len: int, max_len: int | None = None) -> bool:
    if not isinstance(value, list) or len(value) < min_len:
        return False
    if max_len is not None and len(value) != max_len:
        return False
    return all(_is_number(item) for item in value)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    return value.strip().lower() in PLACEHOLDER_STRINGS


def _is_sha256_hex(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(char in "0123456789abcdefABCDEF" for char in value)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _dedupe(issues: list[str]) -> list[str]:
    return list(dict.fromkeys(issues))
