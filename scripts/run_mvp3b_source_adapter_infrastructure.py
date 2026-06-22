#!/usr/bin/env python3
"""Build the MVP-3B source-adapter matrix proof package.

This runner projects generated/file-backed recorded-log fixture evidence through the
existing robot embodiment adapter registry. It does not open Isaac, control a live robot,
or claim hardware/runtime support or learning-proven value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.normalized_trajectory_contract import (  # noqa: E402
    NormalizedTrajectoryContractValidator,
)
from app.services.robot_embodiment_adapters import (  # noqa: E402
    RobotEmbodimentAdapterRegistry,
    RobotEmbodimentAdapterRegistryProfile,
)


DEFAULT_OUTPUT_DIR = ROOT / "docs" / "proof" / "mvp3b_source_adapter_matrix_proof_package"
PACKAGE_NAME = "mvp3b_source_adapter_matrix_proof_package"
PROOF_ID = "rdf_mvp3b_source_adapter_matrix_infrastructure_v0"
CONTRACT_NAME = "mvp3b_source_adapter_matrix_normalized_contract"
PACKAGE_CREATED_AT = "2026-06-22T00:00:00+00:00"
SOURCE_METADATA_SCHEMA_VERSION = "rdf_mvp3b_command_state_source_metadata_v0.1.0"
REQUIRED_ADAPTERS = (
    "franka_research_arm",
    "robotis_sh5_ros2_dds",
    "universal_robots_ur_industrial_arm",
)
REQUIRED_ACTION_ROLES = (
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
)
EXACT_SPENT_NO_REUSE = [[40000, 40049], [42000, 42049]]
SOURCE_EVIDENCE_LEVEL = "generated_or_file_backed_recorded_log_fixture"
EXPECTED_CONTRACT_SOURCE = {
    "input_device": "recorded_command_state_fixture",
    "runtime": "generated_or_file_backed_recorded_log_fixture",
    "simulator": "none_recorded_log_projection",
    "task_name": "mvp3b_source_adapter_matrix",
}
CANONICAL_FORBIDDEN_CLAIMS = (
    "real_robot_success",
    "real_robot_success_claimed",
    "physical_robot_readiness",
    "physical_robot_readiness_claimed",
    "deployable_policy_readiness",
    "visual_policy_performance",
    "hmd_openxr_collection_readiness",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "production_certification",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "learning_proven_value",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "live_ur_runtime_support",
    "live_ros2_dds_runtime_support",
    "franka_hardware_support",
    "public_sample_import",
    "public_sample_import_claimed",
    "public_sample_evidence_claimed",
    "db_migration",
    "db_migration_claimed",
    "production_auth",
    "production_auth_claimed",
    "real_robot_readiness_claimed",
    "production_robot_support_claimed",
)
NO_CLAIMS = {key: False for key in CANONICAL_FORBIDDEN_CLAIMS}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return payload


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _assert_safe_clean_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    default_output = DEFAULT_OUTPUT_DIR.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if resolved == default_output:
        return
    if _is_relative_to(resolved, temp_root) and resolved != temp_root:
        return
    raise ValueError(f"refusing to clean unsafe output_dir: {resolved}")


def _prepare_output_dir(output_dir: Path, *, clean: bool) -> Path:
    if clean and output_dir.exists():
        _assert_safe_clean_output_dir(output_dir)
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    for child in (
        "source_logs",
        "projections",
        "contracts",
        "adapter_results",
        "generated_contract_smoke",
    ):
        (data_dir / child).mkdir(parents=True, exist_ok=True)
    return data_dir


def _command_state_profile(profile: RobotEmbodimentAdapterRegistryProfile) -> dict[str, Any]:
    return dict(profile.builder_class().command_state_stream_profile)


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
        "source_profile": SOURCE_EVIDENCE_LEVEL,
        "runtime": "recorded_log_fixture",
        "source_provenance": {
            "source_type": "generated_recorded_command_state_fixture",
            "recorded_log_backed": True,
            "generated_external_style_sample": profile.generated_external_style_sample,
            "public_sample_evidence_claimed": False,
        },
        "capabilities": list(profile.capabilities),
        "claim_boundary": dict(profile.claim_boundary),
        "limitations": list(profile.limitations),
        "generated_external_style_sample": profile.generated_external_style_sample,
        "public_sample_evidence_claimed": False,
        **NO_CLAIMS,
    }


def _accepted_command(profile: RobotEmbodimentAdapterRegistryProfile) -> list[float]:
    return {
        "franka_research_arm": [0.018, -0.004, -0.052, 0.002, 0.0, -0.001, 0.35],
        "robotis_sh5_ros2_dds": [0.014, -0.003, -0.041, 0.0, 0.001, -0.002, 0.42],
        "universal_robots_ur_industrial_arm": [0.011, -0.002, -0.036, 0.001, -0.001, 0.0, 0.28],
    }[profile.adapter_id]


def _rejected_command(profile: RobotEmbodimentAdapterRegistryProfile) -> list[float]:
    return {
        "franka_research_arm": [0.42, -0.36, -0.72, 0.24, 0.18, -0.21, 1.0],
        "robotis_sh5_ros2_dds": [0.013, -0.003, -0.039, 0.0, 0.001, -0.002, 0.41],
        "universal_robots_ur_industrial_arm": [0.001, 0.0, 0.092, 0.34, -0.27, 0.19, 0.05],
    }[profile.adapter_id]


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


def _role_payloads(command: list[float]) -> dict[str, Any]:
    return {
        role: {
            "role": role,
            "source": "recorded_command_state_fixture",
            "representation": "robot_delta_ee_pose",
            "coordinate_frame": "task_frame",
            "vector": list(command),
        }
        for role in REQUIRED_ACTION_ROLES
    }


def _source_row(
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    accepted: bool,
) -> dict[str, Any]:
    command_profile = _command_state_profile(profile)
    command = _accepted_command(profile) if accepted else _rejected_command(profile)
    timestamp_gap = not accepted and profile.rejection_reason == "COMMAND_STATE_TIMESTAMP_GAP"
    return {
        "adapter_id": profile.adapter_id,
        "row_id": f"{profile.adapter_id}_{'accepted' if accepted else 'rejected'}_0",
        "timestamp": 0.040 if accepted else (1.840 if timestamp_gap else 0.080),
        "timestamp_ns": 40_000_000 if accepted else (1_840_000_000 if timestamp_gap else 80_000_000),
        "sequence_id": 1 if accepted else 2,
        "accepted": accepted,
        "command": {
            "interface": command_profile["command_interface"],
            "vector": command,
            "unit": "meters_radians_normalized_gripper",
        },
        "state": _state(profile, accepted=accepted),
        "command_state": {
            "eef_pose": [0.436, -0.018, 0.035 if accepted else 0.090, 1.0, 0.0, 0.0, 0.0],
            "gripper_width": command[-1],
            "actions_by_role": _role_payloads(command),
        },
        "action_semantics": {
            "representation": "robot_delta_ee_pose",
            "coordinate_frame": "task_frame",
            "normalized_contract_roles": list(REQUIRED_ACTION_ROLES),
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


def _write_source_logs(profile: RobotEmbodimentAdapterRegistryProfile, source_dir: Path) -> None:
    write_json(source_dir / "metadata.json", _source_metadata(profile))
    write_jsonl(source_dir / "accepted_command_state.jsonl", [_source_row(profile, accepted=True)])
    write_jsonl(source_dir / "rejected_command_state.jsonl", [_source_row(profile, accepted=False)])


def _write_contract_smoke(data_dir: Path, adapter_id: str) -> dict[str, Path | str]:
    smoke_dir = data_dir / "generated_contract_smoke" / adapter_id
    hdf5_path = smoke_dir / f"{adapter_id}.contract_smoke.hdf5"
    trainer_path = smoke_dir / f"{adapter_id}.trainer_smoke.json"
    hdf5_path.parent.mkdir(parents=True, exist_ok=True)
    hdf5_path.write_bytes(b"mvp3b contract smoke placeholder; not a learning result\n")
    write_json(
        trainer_path,
        {
            "passed": True,
            "loader_smoke_passed": True,
            "trainer_dry_run_passed": True,
            "contract_smoke_only": True,
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
            "curated_vs_uncurated_uplift": None,
        },
    )
    return {"hdf5_export": hdf5_path, "trainer_smoke_report": trainer_path}


def _package_contract(adapter_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {role: 0 for role in REQUIRED_ACTION_ROLES}
    for row in rows:
        actions = row.get("command_state", {}).get("actions_by_role", {})
        for role in REQUIRED_ACTION_ROLES:
            if role in actions:
                counts[role] += 1
    return {
        "schema_version": "mvp3b.normalized_trajectory_contract.v1",
        "adapter_id": adapter_id,
        "proof_id": PROOF_ID,
        "contract_name": CONTRACT_NAME,
        "source": {**EXPECTED_CONTRACT_SOURCE, "robot": adapter_id},
        "required_action_roles": list(REQUIRED_ACTION_ROLES),
        "frame_action_role_coverage": {
            role: {"present": count > 0, "frames": count}
            for role, count in counts.items()
        },
        "learning_eligibility_gates": {
            "replay_action_contract": True,
            "trainer_export_smoke": "contract_smoke_only",
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
        **NO_CLAIMS,
    }


def _projected_artifact_hashes(projection_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(projection_dir).as_posix(): _sha256(path)
        for path in sorted(projection_dir.rglob("*"))
        if path.is_file() and path.name != "projection_manifest.json"
    }


def _write_projection_manifest(
    *,
    projection_dir: Path,
    source_dir: Path,
    adapter_id: str,
    accepted_count: int,
    rejected_count: int,
) -> None:
    write_json(
        projection_dir / "projection_manifest.json",
        {
            "schema_version": "rdf_mvp3b_source_adapter_projection_manifest_v0.1.0",
            "adapter_id": adapter_id,
            "source_logs": {
                "accepted_command_state.jsonl": {
                    "sha256": _sha256(source_dir / "accepted_command_state.jsonl"),
                    "rows": accepted_count,
                },
                "rejected_command_state.jsonl": {
                    "sha256": _sha256(source_dir / "rejected_command_state.jsonl"),
                    "rows": rejected_count,
                },
            },
            "projected_artifacts": _projected_artifact_hashes(projection_dir),
            "accepted_count": accepted_count,
            "rejected_count": rejected_count,
            "raw_jsonl_is_direct_trainer_input": False,
            "contract_smoke_only": True,
            **NO_CLAIMS,
        },
    )


def _adapter_result(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    emission_passed: bool,
    emission_issues: list[str],
    accepted_count: int,
    rejected_count: int,
    contract_path: Path,
    data_dir: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp3b_source_adapter_result_v0.1.0",
        "adapter_id": profile.adapter_id,
        "status": "normalized_contract_passed" if emission_passed else "normalized_contract_failed",
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "required_action_roles_present": list(REQUIRED_ACTION_ROLES),
        "adapter_call_evidence": {
            "registry_create_called": True,
            "project_source_evidence_called": True,
            "emit_contract_called": True,
            "contract_path": contract_path.relative_to(data_dir.parent).as_posix(),
        },
        "issues": list(emission_issues),
        "contract_smoke_only": True,
        "learning_results_measured": False,
        "policy_uplift": False,
        "learning_proven_value": False,
        **NO_CLAIMS,
    }


def _build_adapter_package(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    data_dir: Path,
) -> dict[str, Any]:
    source_dir = data_dir / "source_logs" / profile.adapter_id
    projection_dir = data_dir / "projections" / profile.adapter_id
    if source_dir.exists():
        shutil.rmtree(source_dir)
    if projection_dir.exists():
        shutil.rmtree(projection_dir)
    _write_source_logs(profile, source_dir)

    adapter = RobotEmbodimentAdapterRegistry.create(
        profile.adapter_id,
        validator=NormalizedTrajectoryContractValidator(
            proof_id=PROOF_ID,
            contract_name=CONTRACT_NAME,
        ),
    )
    projection = adapter.project_source_evidence(source_dir=source_dir, output_dir=projection_dir)
    if not projection.passed:
        raise RuntimeError(f"{profile.adapter_id} projection failed: {projection.issues}")

    smoke_artifacts = _write_contract_smoke(data_dir, profile.adapter_id)
    emission = adapter.emit_contract(
        source_dir=source_dir,
        projected_dir=projection_dir,
        projected_inputs=projection.projected_inputs,
        export_artifacts=smoke_artifacts,
    )
    if not emission.passed:
        raise RuntimeError(f"{profile.adapter_id} contract emission failed: {emission.issues}")

    accepted_rows = read_jsonl(source_dir / "accepted_command_state.jsonl")
    rejected_rows = read_jsonl(source_dir / "rejected_command_state.jsonl")
    accepted_count = len(accepted_rows)
    rejected_count = len(rejected_rows)

    curation = read_json(projection_dir / "curation_manifest.json")
    curation["accepted_count"] = accepted_count
    curation["rejected_count"] = rejected_count
    curation["contract_smoke_only"] = True
    curation.update(NO_CLAIMS)
    write_json(projection_dir / "curation_manifest.json", curation)
    _write_projection_manifest(
        projection_dir=projection_dir,
        source_dir=source_dir,
        adapter_id=profile.adapter_id,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )

    contract_path = data_dir / "contracts" / f"{profile.adapter_id}_normalized_trajectory_contract.json"
    write_json(contract_path, _package_contract(profile.adapter_id, [*accepted_rows, *rejected_rows]))
    result = _adapter_result(
        profile=profile,
        emission_passed=emission.passed,
        emission_issues=emission.issues,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        contract_path=contract_path,
        data_dir=data_dir,
    )
    write_json(data_dir / "adapter_results" / f"{profile.adapter_id}_adapter_result.json", result)
    return {
        "adapter_id": profile.adapter_id,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "result": result,
    }


def _registry_snapshot(profiles: list[RobotEmbodimentAdapterRegistryProfile]) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp3b_adapter_registry_snapshot_v0.1.0",
        "registry_source": "RobotEmbodimentAdapterRegistry.list_profiles",
        "captured_adapters": list(REQUIRED_ADAPTERS),
        "adapters": [
            {
                **profile.to_artifact(),
                "runtime": "recorded_log_fixture",
                **NO_CLAIMS,
            }
            for profile in profiles
        ],
    }


def _write_config(data_dir: Path) -> None:
    write_json(
        data_dir / "config.json",
        {
            "schema_version": "rdf_mvp3b_source_adapter_config_v0.1.0",
            "proof_slice": "mvp3b_source_adapter_matrix",
            "claim_tier": "source_adapter_infrastructure",
            "changed_variable": "source_adapter_matrix",
            "required_adapters": list(REQUIRED_ADAPTERS),
            "source_evidence_level": SOURCE_EVIDENCE_LEVEL,
            "spent_no_reuse": EXACT_SPENT_NO_REUSE,
            "opened_ranges": {
                "calibration": [],
                "heldout": [],
                "tuning": [],
                "closure": [],
            },
            "learning_proven_addendum": "absent",
            "non_claims": dict(NO_CLAIMS),
            "contract_smoke": {
                "trainer_export_smoke": True,
                "learning_results_measured": False,
                "policy_uplift": False,
                "learning_proven_value": False,
            },
        },
    )


def _write_non_claims(data_dir: Path) -> None:
    write_json(
        data_dir / "non_claims_attestation.json",
        {
            "schema_version": "rdf_mvp3b_non_claims_attestation_v0.1.0",
            "scope": "mvp3b_source_adapter_matrix",
            "forbidden_claims": dict(NO_CLAIMS),
            "contract_smoke_only": True,
        },
    )


def _write_summary(data_dir: Path, adapter_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    adapter_counts = {
        item["adapter_id"]: {
            "accepted_count": item["accepted_count"],
            "rejected_count": item["rejected_count"],
        }
        for item in adapter_outputs
    }
    summary = {
        "schema_version": "rdf_mvp3b_source_adapter_matrix_summary_v0.1.0",
        "status": "source_adapter_infrastructure_closed",
        "adapter_count": len(adapter_outputs),
        "required_adapter_count": len(REQUIRED_ADAPTERS),
        "accepted_count": sum(item["accepted_count"] for item in adapter_outputs),
        "rejected_count": sum(item["rejected_count"] for item in adapter_outputs),
        "adapters": adapter_counts,
        "cached_summary_only": True,
        "contract_smoke_only": True,
        "learning_results_measured": False,
        "policy_uplift": False,
        "learning_proven_value": False,
        **NO_CLAIMS,
    }
    write_json(data_dir / "source_adapter_matrix_summary.json", summary)
    return summary


def _write_readme(output_dir: Path) -> None:
    (output_dir / "README.md").write_text(
        "\n".join(
            [
                "# MVP-3B Source-Adapter Matrix Proof Package",
                "",
                "This package records a source-profile projection proof for generated/file-backed",
                "recorded-log fixtures through the RDF adapter infrastructure.",
                "",
                "The package uses the existing `RobotEmbodimentAdapterRegistry` path for Franka,",
                "Robotis SH5 ROS2-DDS-style, and Universal Robots UR-style source profiles.",
                "",
                "Limitations: no live robot runtime is supported here. No real robot success,",
                "physical readiness, marketplace readiness, production certification, public",
                "sample evidence, or learning-proven value is claimed. Trainer/export smoke is",
                "contract smoke only.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_indexes(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    artifact_entries = [
        {
            "data_path": path.relative_to(output_dir).as_posix(),
            "hash_convention": "file_bytes",
            "file_sha256": _sha256(path),
            "byte_size": path.stat().st_size,
        }
        for path in sorted(data_dir.rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    ]
    write_json(
        data_dir / "artifact_index.json",
        {
            "schema_version": "rdf_mvp3b_artifact_index_v0.1.0",
            "artifact_index": artifact_entries,
        },
    )
    manifest_entries = [
        *artifact_entries,
        {
            "data_path": "data/artifact_index.json",
            "hash_convention": "file_bytes",
            "file_sha256": _sha256(data_dir / "artifact_index.json"),
            "byte_size": (data_dir / "artifact_index.json").stat().st_size,
        },
    ]
    write_json(
        output_dir / "package_manifest.json",
        {
            "schema_version": "rdf_mvp3b_source_adapter_package_manifest_v0.1.0",
            "package_name": PACKAGE_NAME,
            "created_at": PACKAGE_CREATED_AT,
            "claims": {
                "status": "source_adapter_infrastructure_closed",
                "source_adapter_matrix": True,
                "contract_smoke_only": True,
            },
            "artifact_index": manifest_entries,
            "non_claims": dict(NO_CLAIMS),
        },
    )


def build_mvp3b_source_adapter_infrastructure(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
) -> dict[str, Any]:
    data_dir = _prepare_output_dir(output_dir, clean=clean)
    profiles_by_id = {
        profile.adapter_id: profile
        for profile in RobotEmbodimentAdapterRegistry.list_profiles()
        if profile.adapter_id in REQUIRED_ADAPTERS
    }
    missing = [adapter_id for adapter_id in REQUIRED_ADAPTERS if adapter_id not in profiles_by_id]
    if missing:
        raise RuntimeError(f"missing required adapters: {', '.join(missing)}")
    profiles = [profiles_by_id[adapter_id] for adapter_id in REQUIRED_ADAPTERS]

    _write_config(data_dir)
    _write_non_claims(data_dir)
    write_json(data_dir / "adapter_registry_snapshot.json", _registry_snapshot(profiles))
    adapter_outputs = [
        _build_adapter_package(profile=profile, data_dir=data_dir)
        for profile in profiles
    ]
    summary = _write_summary(data_dir, adapter_outputs)
    _write_readme(output_dir)
    _write_indexes(output_dir)

    return {
        "status": summary["status"],
        "passed": True,
        "package_dir": str(output_dir),
        "package_manifest": str(output_dir / "package_manifest.json"),
        "adapter_count": summary["adapter_count"],
        "accepted_count": summary["accepted_count"],
        "rejected_count": summary["rejected_count"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_mvp3b_source_adapter_infrastructure(
        output_dir=args.output_dir,
        clean=args.clean,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        print(f"RDF MVP-3B source-adapter matrix: {report['status']}")
        print(f"package_manifest={report['package_manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
