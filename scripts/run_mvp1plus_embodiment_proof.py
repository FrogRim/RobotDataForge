#!/usr/bin/env python3
"""Build the MVP-1+ cross-embodiment adapter proof bundle.

This proof exercises recorded/log-backed robot embodiment adapters. It is not
live robot control, physical robot readiness, HMD readiness, marketplace
readiness, or policy-uplift evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
SCRIPTS_ROOT = ROOT / "scripts"
for path in (API_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.robot_embodiment_adapters import (  # noqa: E402
    RobotEmbodimentAdapterRegistry,
    RobotEmbodimentAdapterRegistryProfile,
)
from app.services.normalized_trajectory_contract import NormalizedTrajectoryContractValidator  # noqa: E402
from export_rdf_to_hdf5 import export_hdf5  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402
from run_mvp1_trainer_smoke import run_trainer_smoke  # noqa: E402


SCHEMA_VERSION = "rdf_mvp1plus_embodiment_proof_v0.1.0"
SUMMARY_SCHEMA_VERSION = "rdf_mvp1plus_embodiment_summary_v0.1.0"
BUYER_SUMMARY_SCHEMA_VERSION = "rdf_mvp1plus_buyer_summary_v0.1.0"
SOURCE_METADATA_SCHEMA_VERSION = "rdf_mvp1plus_command_state_source_metadata_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp1plus_embodiment_proof"
DEFAULT_UR_RECORDED_LOG_DIR = ROOT / "fixtures" / "mvp1plus" / "universal_robots_ur_recorded_log_fixture"
UR_RECORDED_LOG_ADAPTER_ID = "universal_robots_ur_industrial_arm"
CANONICAL_REPRODUCE_COMMAND = "uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty"
PUBLIC_CLAIM = (
    "ForgeXR can turn generated and file-backed recorded/log-backed command-state evidence "
    "for research, ROS2/DDS-style, and industrial-arm embodiments into "
    "buyer-readable, trainer-loadable trust artifacts through one normalized contract."
)
PROOF_ID = "rdf_mvp1plus_cross_embodiment_recorded_log_adapter_proof_v0"
CONTRACT_NAME = "mvp1plus_robot_embodiment_recorded_log_contract"
NO_CLAIMS = {
    "real_robot_success": False,
    "physical_robot_readiness": False,
    "live_runtime_support": False,
    "hmd_readiness": False,
    "policy_uplift": False,
    "universal_robot_support": False,
    "public_sample_import": False,
    "marketplace_readiness": False,
    "db_migration": False,
    "production_auth": False,
}
SOURCE_LOG_FILES = {
    "metadata_json": "metadata.json",
    "accepted_command_state_jsonl": "accepted_command_state.jsonl",
    "rejected_command_state_jsonl": "rejected_command_state.jsonl",
}
PROJECTED_ARTIFACT_KEYS = (
    "accepted_trajectory",
    "accepted_evaluation",
    "rejected_trajectory",
    "rejected_evaluation",
    "curation_manifest",
    "split_manifest",
    "projection_manifest",
)


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text(text + "\n", encoding="utf-8")


def artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def reproduce_command(output_dir: Path, *, ur_recorded_log_dir: Path | None = None) -> str:
    source_arg = ""
    if ur_recorded_log_dir is not None and ur_recorded_log_dir.resolve() != DEFAULT_UR_RECORDED_LOG_DIR.resolve():
        source_arg = f" --ur-recorded-log-dir {ur_recorded_log_dir}"
    if output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve():
        return f"{CANONICAL_REPRODUCE_COMMAND}{source_arg}"
    return (
        "uv run python scripts/run_mvp1plus_embodiment_proof.py "
        f"--output-dir {artifact_path(output_dir)} --clean --pretty{source_arg}"
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _assert_safe_clean_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    repo_root = ROOT.resolve()
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root,
        repo_root.parent,
    }
    temp_root = Path(tempfile.gettempdir()).resolve()
    canonical_tmp = Path("/tmp").resolve()
    if not (temp_root == canonical_tmp or _is_relative_to(temp_root, canonical_tmp)):
        temp_root = canonical_tmp
    allowed_roots = {
        (repo_root / "storage").resolve(),
        temp_root,
    }
    if (
        resolved in forbidden
        or resolved in allowed_roots
        or not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots)
    ):
        raise ValueError(f"refusing to clean unsafe output_dir: {resolved}")


def _prepare_output_dirs(output_dir: Path, *, clean: bool) -> dict[str, Path]:
    if clean and output_dir.exists():
        _assert_safe_clean_output_dir(output_dir)
        shutil.rmtree(output_dir)
    paths = {
        "source_logs": output_dir / "source_logs",
        "projected_inputs": output_dir / "projected_inputs",
        "curation_manifests": output_dir / "curation_manifests",
        "normalized_contracts": output_dir / "normalized_contracts",
        "hdf5": output_dir / "hdf5",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def _reset_managed_child_dir(path: Path, *, root: Path) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved == root_resolved or not _is_relative_to(resolved, root_resolved):
        raise ValueError(f"refusing to reset unmanaged output dir: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _command_state_profile(profile: RobotEmbodimentAdapterRegistryProfile) -> dict[str, Any]:
    builder = profile.builder_class()
    return dict(builder.command_state_stream_profile)


def _source_metadata(profile: RobotEmbodimentAdapterRegistryProfile) -> dict[str, Any]:
    command_profile = _command_state_profile(profile)
    return {
        "schema_version": SOURCE_METADATA_SCHEMA_VERSION,
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
        "source_provenance": {
            "source_type": "jsonl_plus_metadata_recorded_command_state_log",
            "recorded_log_backed": True,
            "generated_external_style_sample": profile.generated_external_style_sample,
            "public_sample_evidence_claimed": False,
        },
        "capabilities": list(profile.capabilities),
        "claim_boundary": dict(profile.claim_boundary),
        "limitations": list(profile.limitations),
        "generated_external_style_sample": profile.generated_external_style_sample,
        "public_sample_evidence_claimed": False,
    }


def _accepted_command(profile: RobotEmbodimentAdapterRegistryProfile) -> list[float]:
    commands = {
        "franka_research_arm": [0.018, -0.004, -0.052, 0.002, 0.0, -0.001, 0.35],
        "robotis_sh5_ros2_dds": [0.014, -0.003, -0.041, 0.0, 0.001, -0.002, 0.42],
        "universal_robots_ur_industrial_arm": [0.011, -0.002, -0.036, 0.001, -0.001, 0.0, 0.28],
        "universal_robots_ur_external_style": [0.010, -0.002, -0.034, 0.001, -0.001, 0.0, 0.27],
    }
    return commands[profile.adapter_id]


def _rejected_command(profile: RobotEmbodimentAdapterRegistryProfile) -> list[float]:
    commands = {
        "franka_research_arm": [0.42, -0.36, -0.72, 0.24, 0.18, -0.21, 1.0],
        "robotis_sh5_ros2_dds": [0.013, -0.003, -0.039, 0.0, 0.001, -0.002, 0.41],
        "universal_robots_ur_industrial_arm": [0.001, 0.0, 0.092, 0.34, -0.27, 0.19, 0.05],
        "universal_robots_ur_external_style": [0.001, 0.0, 0.090, 0.33, -0.26, 0.18, 0.05],
    }
    return commands[profile.adapter_id]


def _state(profile: RobotEmbodimentAdapterRegistryProfile, *, accepted: bool) -> dict[str, Any]:
    z = 0.035 if accepted else 0.090
    return {
        "interface": _command_state_profile(profile)["state_interface"],
        "end_effector_position": [0.436, -0.018, z],
        "end_effector_quaternion": [1.0, 0.0, 0.0, 0.0],
        "object_position": [0.440, -0.020, 0.0],
        "object_quaternion": [1.0, 0.0, 0.0, 0.0],
        "joint_positions": [0.0, -0.41, 0.18, -1.88, 0.0, 1.57, 0.78],
    }


def _command_state_row(profile: RobotEmbodimentAdapterRegistryProfile, *, accepted: bool) -> dict[str, Any]:
    command_profile = _command_state_profile(profile)
    command = _accepted_command(profile) if accepted else _rejected_command(profile)
    timestamp_gap = not accepted and profile.rejection_reason == "COMMAND_STATE_TIMESTAMP_GAP"
    return {
        "timestamp": 0.040 if accepted else (1.840 if timestamp_gap else 0.080),
        "sequence_id": 1 if accepted else 2,
        "command": {
            "interface": command_profile["command_interface"],
            "vector": command,
            "unit": "meters_radians_normalized_gripper",
        },
        "state": _state(profile, accepted=accepted),
        "action_semantics": {
            "representation": "robot_delta_ee_pose",
            "coordinate_frame": "task_frame",
            "normalized_contract_roles": [
                "teleop_intent",
                "executed_control",
                "learning_action",
                "retargeted_robot_action",
            ],
        },
        "task_phase": "seat" if accepted else "approach_or_contact_failure",
        "quality": {
            "replay_verified": accepted,
            "action_contract_valid": accepted,
            "control_quality": "pass" if accepted else "fail",
            "timestamp_gap_detected": timestamp_gap,
            "rejection_reason": None if accepted else profile.rejection_reason,
        },
    }


def _write_source_logs(profile: RobotEmbodimentAdapterRegistryProfile, source_dir: Path) -> dict[str, Path]:
    metadata_path = source_dir / "metadata.json"
    accepted_path = source_dir / "accepted_command_state.jsonl"
    rejected_path = source_dir / "rejected_command_state.jsonl"
    write_json(metadata_path, _source_metadata(profile))
    write_jsonl(accepted_path, [_command_state_row(profile, accepted=True)])
    write_jsonl(rejected_path, [_command_state_row(profile, accepted=False)])
    return {
        "metadata_json": metadata_path,
        "accepted_command_state_jsonl": accepted_path,
        "rejected_command_state_jsonl": rejected_path,
    }


def _source_override_for_profile(
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    ur_recorded_log_dir: Path | None,
) -> Path | None:
    if profile.adapter_id != UR_RECORDED_LOG_ADAPTER_ID:
        return None
    return ur_recorded_log_dir or DEFAULT_UR_RECORDED_LOG_DIR


def _align_false_claim_boundary_with_profile(
    metadata: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> None:
    claim_boundary = metadata.get("claim_boundary")
    if not isinstance(claim_boundary, dict):
        return
    if any(value is not False for value in claim_boundary.values()):
        return
    if claim_boundary == profile.claim_boundary:
        return

    source_provenance = dict(metadata.get("source_provenance") or {})
    source_provenance["claim_boundary_normalized_to_adapter_profile"] = True
    source_provenance["claim_boundary_source_key_count"] = len(claim_boundary)
    source_provenance["claim_boundary_profile_key_count"] = len(profile.claim_boundary)
    metadata["source_provenance"] = source_provenance
    metadata["claim_boundary"] = dict(profile.claim_boundary)


def _copy_source_logs(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    source_dir: Path,
    target_dir: Path,
) -> dict[str, Path]:
    missing = [filename for filename in SOURCE_LOG_FILES.values() if not (source_dir / filename).exists()]
    if missing:
        raise FileNotFoundError(f"{profile.adapter_id} source log missing: {', '.join(missing)}")
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata = read_json(source_dir / "metadata.json")
    source_provenance = dict(metadata.get("source_provenance") or {})
    if source_dir.resolve() == DEFAULT_UR_RECORDED_LOG_DIR.resolve():
        source_provenance["fixture_path"] = str(DEFAULT_UR_RECORDED_LOG_DIR)
        source_provenance["repo_local_recorded_log_fixture"] = True
    else:
        source_provenance["source_directory"] = str(source_dir)
    metadata["source_provenance"] = source_provenance
    _align_false_claim_boundary_with_profile(metadata, profile)
    write_json(target_dir / "metadata.json", metadata)
    shutil.copy2(source_dir / "accepted_command_state.jsonl", target_dir / "accepted_command_state.jsonl")
    shutil.copy2(source_dir / "rejected_command_state.jsonl", target_dir / "rejected_command_state.jsonl")
    return {key: target_dir / filename for key, filename in SOURCE_LOG_FILES.items()}


def _prepare_source_logs(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    paths: dict[str, Path],
    ur_recorded_log_dir: Path | None,
) -> dict[str, Path]:
    target_dir = paths["source_logs"] / profile.adapter_id
    _reset_managed_child_dir(target_dir, root=paths["source_logs"])
    source_override = _source_override_for_profile(profile, ur_recorded_log_dir=ur_recorded_log_dir)
    if source_override is not None:
        return _copy_source_logs(profile=profile, source_dir=source_override, target_dir=target_dir)
    return _write_source_logs(profile, target_dir)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_lineage(path: Path) -> dict[str, Any]:
    return {
        "path": artifact_path(path),
        "sha256": _sha256_file(path),
        "byte_size": path.stat().st_size,
    }


def _bundle_sha256(records: dict[str, dict[str, Any]]) -> str:
    digest_payload = {
        key: {
            "path": value["path"],
            "sha256": value["sha256"],
            "byte_size": value["byte_size"],
        }
        for key, value in sorted(records.items())
    }
    return hashlib.sha256(stable_json(digest_payload).encode("utf-8")).hexdigest()


def _lineage_evidence(
    *,
    source_logs: dict[str, Path],
    projected_inputs: dict[str, Any],
) -> dict[str, Any]:
    metadata = read_json(source_logs["metadata_json"])
    source_provenance = metadata.get("source_provenance") or {}
    source_files = {key: _file_lineage(path) for key, path in source_logs.items()}
    projected_artifacts = {
        key: _file_lineage(Path(projected_inputs[key]))
        for key in PROJECTED_ARTIFACT_KEYS
        if projected_inputs.get(key)
    }
    return {
        "schema_version": "rdf_mvp1plus_lineage_evidence_v0.1.0",
        "source_evidence_type": source_provenance.get("source_type", "unknown"),
        "source_provenance": source_provenance,
        "source_files": source_files,
        "source_bundle_sha256": _bundle_sha256(source_files),
        "projected_artifacts": projected_artifacts,
        "projected_bundle_sha256": _bundle_sha256(projected_artifacts),
    }


def _run_export_and_trainer_smoke(
    *,
    projected_inputs: dict[str, Any],
    hdf5_dir: Path,
    adapter_id: str,
) -> dict[str, Path | dict[str, Any]]:
    hdf5_path = hdf5_dir / f"{adapter_id}.hdf5"
    inspection_path = hdf5_dir / f"{adapter_id}.inspection.json"
    trainer_smoke_path = hdf5_dir / f"{adapter_id}.trainer_smoke.json"

    export_hdf5(
        output_path=hdf5_path,
        trajectories_dir=Path(projected_inputs["trajectories_dir"]),
        evaluations_dir=Path(projected_inputs["evaluations_dir"]),
        include_statuses={"success"},
    )
    inspection = inspect_hdf5(hdf5_path)
    write_json(inspection_path, inspection)
    trainer = run_trainer_smoke(
        hdf5_path=hdf5_path,
        split_manifest_path=Path(projected_inputs["split_manifest"]),
        output_path=trainer_smoke_path,
        experiment_manifest_path=None,
    )
    return {
        "hdf5_export": hdf5_path,
        "hdf5_inspection": inspection_path,
        "trainer_smoke_report": trainer_smoke_path,
        "inspection": inspection,
        "trainer_smoke": trainer,
    }


def _copy_projected_success_inputs(
    *,
    projected_inputs: dict[str, Any],
    adapter_id: str,
    integrated_dir: Path,
) -> dict[str, Any]:
    trajectories_dir = integrated_dir / "trajectories"
    evaluations_dir = integrated_dir / "evaluations"
    trajectories_dir.mkdir(parents=True, exist_ok=True)
    evaluations_dir.mkdir(parents=True, exist_ok=True)

    trajectory_src = Path(projected_inputs["accepted_trajectory"])
    evaluation_src = Path(projected_inputs["accepted_evaluation"])
    trajectory_dst = trajectories_dir / f"{adapter_id}_{trajectory_src.name}"
    evaluation_dst = evaluations_dir / f"{adapter_id}_{evaluation_src.name}"
    shutil.copy2(trajectory_src, trajectory_dst)
    shutil.copy2(evaluation_src, evaluation_dst)
    trajectory = read_json(trajectory_dst)
    return {
        "trajectory": trajectory_dst,
        "evaluation": evaluation_dst,
        "episode_id": trajectory["episode_id"],
    }


def _write_split_manifest(episode_ids: list[str], path: Path) -> dict[str, Any]:
    manifest = {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "task_id": "task_mvp1plus_cross_embodiment",
        "strategy": "mvp1plus_cross_embodiment_integrated_success_split",
        "splits": {
            "train": list(episode_ids),
            "validation": [],
            "test": [],
        },
    }
    write_json(path, manifest)
    return manifest


def _adapter_summary(result: dict[str, Any]) -> dict[str, Any]:
    proof = result["emission"].proof
    curation = proof.get("curation_evidence") or {}
    contract = result["contract"]
    evidence = contract.get("robot_embodiment_adapter_evidence") or {}
    source_profile = contract.get("source_profile") or {}
    export = result["export"]
    return {
        "adapter_id": result["profile"].adapter_id,
        "adapter_name": result["profile"].adapter_name,
        "robot_family": result["profile"].robot_family,
        "embodiment_class": result["profile"].embodiment_class,
        "evidence_level": result["profile"].evidence_level,
        "generated_external_style_sample": result["profile"].generated_external_style_sample,
        "source_profile": source_profile,
        "adapter_version": result["profile"].adapter_version,
        "builder_id": (contract.get("contract_builder") or {}).get("builder_id"),
        "emitter_id": (contract.get("adapter_contract_emitter") or {}).get("emitter_id"),
        "command_action_semantics": evidence.get("command_action_semantics"),
        "state_metadata": evidence.get("state_metadata"),
        "replay_consistency_evidence": evidence.get("replay_consistency_evidence"),
        "accepted_count": curation.get("accepted_count"),
        "rejected_count": curation.get("rejected_count"),
        "rejection_reason_distribution": curation.get("rejection_reason_distribution"),
        "hdf5_export_exists": Path(export["hdf5_export"]).exists(),
        "hdf5_inspection_clean": (export["inspection"] or {}).get("issues") == [],
        "trainer_smoke_passed": (export["trainer_smoke"] or {}).get("passed") is True,
        "limitations": list(result["profile"].limitations),
        "contract_path": artifact_path(result["contract_path"]),
        "source_logs": {key: artifact_path(path) for key, path in result["source_logs"].items()},
        "lineage_evidence": result["lineage_evidence"],
    }


def _build_integrated_export(
    *,
    adapter_results: list[dict[str, Any]],
    output_dir: Path,
    paths: dict[str, Path],
) -> dict[str, Any]:
    integrated_dir = paths["projected_inputs"] / "integrated"
    _reset_managed_child_dir(integrated_dir, root=paths["projected_inputs"])
    episode_ids: list[str] = []
    copied_inputs: list[dict[str, Any]] = []
    for result in adapter_results:
        copied = _copy_projected_success_inputs(
            projected_inputs=result["projected_inputs"],
            adapter_id=result["profile"].adapter_id,
            integrated_dir=integrated_dir,
        )
        copied_inputs.append(
            {
                "adapter_id": result["profile"].adapter_id,
                "trajectory": artifact_path(copied["trajectory"]),
                "evaluation": artifact_path(copied["evaluation"]),
                "episode_id": copied["episode_id"],
            }
        )
        episode_ids.append(copied["episode_id"])

    split_manifest_path = integrated_dir / "split_manifest.json"
    _write_split_manifest(episode_ids, split_manifest_path)
    hdf5_path = paths["hdf5"] / "mvp1plus_cross_embodiment.hdf5"
    inspection_path = paths["hdf5"] / "mvp1plus_cross_embodiment.inspection.json"
    trainer_smoke_path = paths["hdf5"] / "mvp1plus_cross_embodiment.trainer_smoke.json"
    export_hdf5(
        output_path=hdf5_path,
        trajectories_dir=integrated_dir / "trajectories",
        evaluations_dir=integrated_dir / "evaluations",
        include_statuses={"success"},
    )
    inspection = inspect_hdf5(hdf5_path)
    write_json(inspection_path, inspection)
    trainer = run_trainer_smoke(
        hdf5_path=hdf5_path,
        split_manifest_path=split_manifest_path,
        output_path=trainer_smoke_path,
        experiment_manifest_path=None,
    )
    return {
        "projected_inputs_dir": artifact_path(integrated_dir),
        "copied_inputs": copied_inputs,
        "split_manifest": artifact_path(split_manifest_path),
        "hdf5_export": artifact_path(hdf5_path),
        "hdf5_inspection": artifact_path(inspection_path),
        "trainer_smoke_report": artifact_path(trainer_smoke_path),
        "episode_ids": episode_ids,
        "hdf5_export_exists": hdf5_path.exists(),
        "hdf5_inspection_clean": inspection.get("issues") == [],
        "trainer_smoke_passed": trainer.get("passed") is True,
    }


def _summary_passed(
    *,
    issues: list[str],
    integrated_export: dict[str, Any],
    adapter_summaries: list[dict[str, Any]],
    rejection_reason_coverage_passed: bool,
) -> bool:
    return bool(
        not issues
        and rejection_reason_coverage_passed
        and integrated_export.get("hdf5_export_exists") is True
        and integrated_export.get("hdf5_inspection_clean") is True
        and integrated_export.get("trainer_smoke_passed") is True
        and all(adapter.get("hdf5_export_exists") is True for adapter in adapter_summaries)
        and all(adapter.get("hdf5_inspection_clean") is True for adapter in adapter_summaries)
        and all(adapter.get("trainer_smoke_passed") is True for adapter in adapter_summaries)
    )


def _build_summary(
    *,
    adapter_results: list[dict[str, Any]],
    integrated_export: dict[str, Any],
    output_dir: Path,
    ur_recorded_log_dir: Path | None,
) -> dict[str, Any]:
    summaries = [_adapter_summary(result) for result in adapter_results]
    rejection_reasons = Counter(
        reason
        for summary in summaries
        for reason, count in (summary.get("rejection_reason_distribution") or {}).items()
        for _ in range(int(count))
    )
    issues = [
        issue
        for result in adapter_results
        for issue in result["emission"].issues
    ]
    rejection_reason_coverage_passed = all(
        (summary.get("rejection_reason_distribution") or {}) for summary in summaries
    )
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "proof_id": PROOF_ID,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": _summary_passed(
            issues=issues,
            integrated_export=integrated_export,
            adapter_summaries=summaries,
            rejection_reason_coverage_passed=rejection_reason_coverage_passed,
        ),
        "public_claim": PUBLIC_CLAIM,
        "reproduce_command": reproduce_command(output_dir, ur_recorded_log_dir=ur_recorded_log_dir),
        "adapter_count": len(adapter_results),
        "accepted_count": sum(int(summary.get("accepted_count") or 0) for summary in summaries),
        "rejected_count": sum(int(summary.get("rejected_count") or 0) for summary in summaries),
        "rejection_reason_distribution": dict(sorted(rejection_reasons.items())),
        "rejection_reason_coverage_passed": rejection_reason_coverage_passed,
        "adapters": summaries,
        "integrated_export": integrated_export,
        "mvp_boundary": {
            "mvp1_learning_ready_dataset_pipeline": True,
            "mvp2_learning_proven_policy_uplift": False,
            "not_claimed": dict(NO_CLAIMS),
        },
        "issues": issues,
    }


def _build_buyer_summary(
    *,
    summary: dict[str, Any],
    adapter_results: list[dict[str, Any]],
    output_dir: Path,
    ur_recorded_log_dir: Path | None,
) -> dict[str, Any]:
    adapter_answers = []
    for result in adapter_results:
        profile = result["profile"]
        contract = result["contract"]
        evidence = contract.get("robot_embodiment_adapter_evidence") or {}
        curation = evidence.get("curation_evidence") or {}
        adapter_answers.append(
            {
                "adapter_id": profile.adapter_id,
                "adapter_name": profile.adapter_name,
                "adapter_version": profile.adapter_version,
                "builder_id": (contract.get("contract_builder") or {}).get("builder_id"),
                "robot_embodiment": {
                    "robot_family": profile.robot_family,
                    "embodiment_class": profile.embodiment_class,
                    "evidence_level": profile.evidence_level,
                },
                "where_did_the_data_come_from": (
                    "JSONL + metadata JSON command-state logs projected into RDF-compatible "
                    "trajectory/evaluation artifacts."
                ),
                "input_route": "robot_embodiment_recorded_log_adapter",
                "action_contract_summary": evidence.get("command_action_semantics"),
                "state_metadata": evidence.get("state_metadata"),
                "replay_or_consistency_checked": evidence.get("replay_consistency_evidence"),
                "accepted_funnel": curation.get("accepted"),
                "rejected_funnel": curation.get("rejected"),
                "rejection_reason_distribution": curation.get("rejection_reason_distribution"),
                "hdf5_export": result["export"]["hdf5_export"].exists(),
                "trainer_smoke_passed": (result["export"]["trainer_smoke"] or {}).get("passed") is True,
                "limitations": list(profile.limitations),
                "generated_external_style_sample": profile.generated_external_style_sample,
                "lineage_evidence": result["lineage_evidence"],
            }
        )

    return {
        "schema_version": BUYER_SUMMARY_SCHEMA_VERSION,
        "proof_id": PROOF_ID,
        "created_at": summary["created_at"],
        "passed": summary["passed"],
        "buyer_readable_claim": PUBLIC_CLAIM,
        "plain_language_summary": (
            "This MVP-1+ package shows that different generated and file-backed recorded/log-backed "
            "robot embodiment evidence sources can emit the same normalized trajectory contract, "
            "pass the same data trust gates, export HDF5, and load through the trainer smoke path."
        ),
        "buyer_questions": {
            "where_did_the_data_come_from": (
                "Generated and file-backed recorded/log-backed JSONL command-state evidence with metadata JSON."
            ),
            "which_adapter_emitted_it": [item["adapter_id"] for item in adapter_answers],
            "what_robot_embodiment_is_it_tied_to": [
                item["robot_embodiment"] for item in adapter_answers
            ],
            "what_action_semantics_does_it_satisfy": [
                item["action_contract_summary"] for item in adapter_answers
            ],
            "was_replay_or_consistency_checked": True,
            "why_accepted": "Accepted rows passed replay/action, data-quality, curation, export, and trainer gates.",
            "why_rejected": summary["rejection_reason_distribution"],
            "was_hdf5_export_produced": summary["integrated_export"]["hdf5_export_exists"],
            "can_a_trainer_load_it": summary["integrated_export"]["trainer_smoke_passed"],
            "known_limitations": (
                "Generated and repo-local file-backed recorded/log-backed proof only; no live robot "
                "runtime, real robot success, physical readiness, HMD readiness, public sample import, "
                "marketplace readiness, DB migration, production auth, or policy uplift is claimed."
            ),
        },
        "adapter_summaries": adapter_answers,
        "integrated_export": summary["integrated_export"],
        "rejection_reason_distribution": summary["rejection_reason_distribution"],
        "non_claims": dict(NO_CLAIMS),
        "reproduce_command": reproduce_command(output_dir, ur_recorded_log_dir=ur_recorded_log_dir),
    }


def _build_adapter_result(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    paths: dict[str, Path],
    ur_recorded_log_dir: Path | None,
) -> dict[str, Any]:
    source_dir = paths["source_logs"] / profile.adapter_id
    source_logs = _prepare_source_logs(
        profile=profile,
        paths=paths,
        ur_recorded_log_dir=ur_recorded_log_dir,
    )
    adapter = RobotEmbodimentAdapterRegistry.create(
        profile.adapter_id,
        validator=NormalizedTrajectoryContractValidator(
            proof_id=PROOF_ID,
            contract_name=CONTRACT_NAME,
            artifact_path_formatter=artifact_path,
        ),
    )
    projected_dir = paths["projected_inputs"] / profile.adapter_id
    _reset_managed_child_dir(projected_dir, root=paths["projected_inputs"])
    projection = adapter.project_source_evidence(source_dir=source_dir, output_dir=projected_dir)
    if not projection.passed:
        raise RuntimeError(f"{profile.adapter_id} projection failed: {projection.issues}")

    export = _run_export_and_trainer_smoke(
        projected_inputs=projection.projected_inputs,
        hdf5_dir=paths["hdf5"],
        adapter_id=profile.adapter_id,
    )
    emission = adapter.emit_contract(
        source_dir=source_dir,
        projected_dir=projected_dir,
        projected_inputs=projection.projected_inputs,
        export_artifacts={
            "hdf5_export": export["hdf5_export"],
            "trainer_smoke_report": export["trainer_smoke_report"],
        },
    )
    lineage = _lineage_evidence(source_logs=source_logs, projected_inputs=projection.projected_inputs)
    if emission.contract:
        evidence = emission.contract.get("robot_embodiment_adapter_evidence") or {}
        evidence["lineage_evidence"] = lineage
        emission.contract["robot_embodiment_adapter_evidence"] = evidence
        emission.proof["lineage_evidence"] = lineage
        emission.proof["contract"] = emission.contract
    contract_path = paths["normalized_contracts"] / f"{profile.adapter_id}_normalized_trajectory_contract.json"
    if emission.contract:
        write_json(contract_path, emission.contract)
    curation_path = paths["curation_manifests"] / f"{profile.adapter_id}_curation_manifest.json"
    shutil.copy2(projection.projected_inputs["curation_manifest"], curation_path)
    return {
        "profile": profile,
        "source_logs": source_logs,
        "projection": projection,
        "projected_inputs": projection.projected_inputs,
        "export": export,
        "emission": emission,
        "contract": emission.contract,
        "contract_path": contract_path,
        "curation_manifest": curation_path,
        "lineage_evidence": lineage,
    }


def _build_final_proof(
    *,
    summary: dict[str, Any],
    buyer_summary: dict[str, Any],
    adapter_results: list[dict[str, Any]],
    output_dir: Path,
    ur_recorded_log_dir: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proof_id": PROOF_ID,
        "created_at": summary["created_at"],
        "passed": summary["passed"],
        "public_claim": PUBLIC_CLAIM,
        "adapter_registry": [profile.to_artifact() for profile in RobotEmbodimentAdapterRegistry.list_profiles()],
        "adapter_proofs": [result["emission"].proof for result in adapter_results],
        "summary": summary,
        "buyer_summary": buyer_summary,
        "artifact_paths": {
            "proof": artifact_path(output_dir / "mvp1plus_embodiment_proof.json"),
            "summary": artifact_path(output_dir / "mvp1plus_embodiment_proof_summary.json"),
            "buyer_summary": artifact_path(output_dir / "mvp1plus_buyer_summary.json"),
            "source_logs": artifact_path(output_dir / "source_logs"),
            "projected_inputs": artifact_path(output_dir / "projected_inputs"),
            "normalized_contracts": artifact_path(output_dir / "normalized_contracts"),
            "hdf5": artifact_path(output_dir / "hdf5"),
        },
        "reproduce_command": reproduce_command(output_dir, ur_recorded_log_dir=ur_recorded_log_dir),
        "non_claims": dict(NO_CLAIMS),
        "issues": summary["issues"],
    }


def build_mvp1plus_embodiment_proof(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
    ur_recorded_log_dir: Path | None = None,
) -> dict[str, Any]:
    paths = _prepare_output_dirs(output_dir, clean=clean)
    profiles = RobotEmbodimentAdapterRegistry.list_profiles()
    adapter_results = [
        _build_adapter_result(
            profile=profile,
            paths=paths,
            ur_recorded_log_dir=ur_recorded_log_dir,
        )
        for profile in profiles
    ]
    integrated_export = _build_integrated_export(
        adapter_results=adapter_results,
        output_dir=output_dir,
        paths=paths,
    )
    summary = _build_summary(
        adapter_results=adapter_results,
        integrated_export=integrated_export,
        output_dir=output_dir,
        ur_recorded_log_dir=ur_recorded_log_dir,
    )
    buyer_summary = _build_buyer_summary(
        summary=summary,
        adapter_results=adapter_results,
        output_dir=output_dir,
        ur_recorded_log_dir=ur_recorded_log_dir,
    )
    proof = _build_final_proof(
        summary=summary,
        buyer_summary=buyer_summary,
        adapter_results=adapter_results,
        output_dir=output_dir,
        ur_recorded_log_dir=ur_recorded_log_dir,
    )
    write_json(output_dir / "mvp1plus_embodiment_proof_summary.json", summary)
    write_json(output_dir / "mvp1plus_buyer_summary.json", buyer_summary)
    write_json(output_dir / "mvp1plus_embodiment_proof.json", proof)
    return proof


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--ur-recorded-log-dir",
        type=Path,
        default=None,
        help=(
            "Optional file-backed UR recorded-log source directory. "
            "Defaults to the repo-local claim-safe UR fixture."
        ),
    )
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_mvp1plus_embodiment_proof(
        args.output_dir,
        clean=args.clean,
        ur_recorded_log_dir=args.ur_recorded_log_dir,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1+ robot embodiment adapter proof: {status}")
        print(f"adapter_count={report['summary']['adapter_count']}")
        print(f"accepted_count={report['summary']['accepted_count']}")
        print(f"rejected_count={report['summary']['rejected_count']}")
        print(f"output={args.output_dir}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
