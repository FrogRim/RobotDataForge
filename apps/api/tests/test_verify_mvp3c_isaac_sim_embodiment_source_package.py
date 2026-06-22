"""Contract tests for the MVP-3C Isaac Sim embodiment source verifier.

These tests intentionally define the independent auditor before producer code exists.
Synthetic fixtures are allowed to exercise verifier mechanics, but they must never
mint the original `isaac_sim_embodiment_source_closed` status.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "scripts" / "verify_mvp3c_isaac_sim_embodiment_source_package.py"
DEFAULT_PACKAGE = (
    ROOT / "docs" / "proof" / "mvp3c_isaac_sim_embodiment_source_proof_package"
)

REQUIRED_EMBODIMENTS = (
    "franka_panda_isaac_sim",
    "universal_robots_ur10e_isaac_sim",
)
REQUIRED_ACTION_ROLES = (
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
)
EXACT_SPENT_NO_REUSE = [[40000, 40049], [42000, 42049]]
CANONICAL_FORBIDDEN_CLAIMS = (
    "real_robot_success",
    "real_robot_success_claimed",
    "physical_robot_readiness",
    "physical_robot_readiness_claimed",
    "deployable_policy_readiness",
    "deployable_policy_readiness_claimed",
    "visual_policy_performance",
    "visual_policy_performance_claimed",
    "hmd_openxr_collection_readiness",
    "hmd_openxr_collection_readiness_claimed",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "production_certification",
    "production_certification_claimed",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "learning_proven_value",
    "learning_proven_value_claimed",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "live_ur_runtime_support",
    "live_ur_runtime_support_claimed",
    "live_ur_hardware_support",
    "live_ur_hardware_support_claimed",
    "live_franka_hardware_support",
    "live_franka_hardware_support_claimed",
    "live_ros2_dds_runtime_support",
    "live_ros2_dds_runtime_support_claimed",
    "franka_hardware_support",
    "franka_hardware_support_claimed",
    "ur_hardware_support",
    "ur_hardware_support_claimed",
    "ros2_bridge_support",
    "ros2_bridge_support_claimed",
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


def _load_verifier():
    name = "verify_mvp3c_isaac_sim_embodiment_source_package"
    spec = importlib.util.spec_from_file_location(name, VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_stable_json(row) + "\n" for row in rows), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl_payloads(path: Path) -> list[dict]:
    rows = []
    decoder = json.JSONDecoder()
    body = path.read_text(encoding="utf-8")
    index = 0
    while index < len(body):
        while index < len(body) and body[index].isspace():
            index += 1
        if index >= len(body):
            break
        payload, index = decoder.raw_decode(body, index)
        assert isinstance(payload, dict)
        rows.append(payload)
    return rows


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_id(embodiment_id: str) -> str:
    return f"{embodiment_id}_runtime_capture_20260622T010000Z"


def _source_rows(embodiment_id: str, *, accepted: bool) -> list[dict]:
    role_values = {role: [0.1, 0.2, 0.3, 0.4] for role in REQUIRED_ACTION_ROLES}
    return [
        {
            "embodiment_id": embodiment_id,
            "runtime_capture_id": _capture_id(embodiment_id),
            "row_id": f"{embodiment_id}_{'accepted' if accepted else 'rejected'}_0",
            "timestamp_ns": 1_000_000 if accepted else 2_000_000,
            "runtime": "isaac_sim",
            "simulator": "isaac_sim",
            "source_kind": "isaac_sim_runtime_backed_command_state_log",
            "accepted": accepted,
            "command_state": {
                "joint_positions": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
                "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "eef_pose": [0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 1.0],
                "actions_by_role": role_values,
            },
        }
    ]


def _contract(
    embodiment_id: str,
    *,
    roles: tuple[str, ...] = REQUIRED_ACTION_ROLES,
) -> dict:
    frame_count = 2
    return {
        "schema_version": "mvp3c.normalized_trajectory_contract.v1",
        "embodiment_id": embodiment_id,
        "source": {
            "input_device": "isaac_sim_command_state_log",
            "runtime": "isaac_sim",
            "simulator": "isaac_sim",
            "robot": embodiment_id,
            "task_name": "mvp3c_isaac_sim_embodiment_source",
        },
        "required_action_roles": list(roles),
        "frame_action_role_coverage": {
            role: {"present": True, "frames": frame_count} for role in roles
        },
        "learning_eligibility_gates": {
            "replay_action_contract": True,
            "trainer_export_smoke": "contract_smoke_only",
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
    }


def _make_package(
    tmp_path: Path,
    *,
    embodiments: tuple[str, ...] = REQUIRED_EMBODIMENTS,
    synthetic: bool = True,
) -> Path:
    pkg = tmp_path / "mvp3c_pkg"
    data = pkg / "data"
    forbidden_false = {key: False for key in CANONICAL_FORBIDDEN_CLAIMS}
    embodiment_counts = {}

    _write_json(
        data / "config.json",
        {
            "schema_version": "rdf_mvp3c_isaac_sim_embodiment_source_config_v0.1.0",
            "proof_slice": "mvp3c_isaac_sim_embodiment_source",
            "claim_tier": "isaac_sim_embodiment_source",
            "changed_variable": "isaac_sim_embodiment_source_pair",
            "required_embodiments": list(REQUIRED_EMBODIMENTS),
            "evidence_kind": "synthetic_verifier_fixture"
            if synthetic
            else "isaac_sim_runtime_backed_source_log",
            "requested_status": "synthetic_verifier_fixture"
            if synthetic
            else "isaac_sim_embodiment_source_closed",
            "synthetic_verifier_fixture": synthetic,
            "runtime_evidence_captured": not synthetic,
            "closure_assertion": not synthetic,
            "source_evidence_level": "synthetic_verifier_fixture"
            if synthetic
            else "isaac_sim_runtime_backed_command_state_log",
            "runtime_expectations": {
                "runtime": "isaac_sim",
                "simulator": "isaac_sim",
                "platform": "linux",
            },
            "spent_no_reuse": EXACT_SPENT_NO_REUSE,
            "opened_ranges": {
                "calibration": [],
                "heldout": [],
                "tuning": [],
                "closure": [],
            },
            "learning_proven_addendum": "absent",
            "non_claims": forbidden_false,
        },
    )
    _write_json(
        data / "non_claims_attestation.json",
        {
            "scope": "mvp3c_isaac_sim_embodiment_source",
            "forbidden_claims": forbidden_false,
        },
    )

    for embodiment_id in embodiments:
        accepted_rows = _source_rows(embodiment_id, accepted=True)
        rejected_rows = _source_rows(embodiment_id, accepted=False)
        source_dir = data / "source_logs" / embodiment_id
        accepted_path = source_dir / "accepted_command_state.jsonl"
        rejected_path = source_dir / "rejected_command_state.jsonl"
        runtime_metadata_path = (
            data / "runtime_metadata" / f"{embodiment_id}_runtime_metadata.json"
        )
        preflight_path = data / "preflight" / f"{embodiment_id}_preflight.json"

        _write_json(
            runtime_metadata_path,
            {
                "schema_version": "rdf_mvp3c_runtime_metadata_v0.1.0",
                "embodiment_id": embodiment_id,
                "runtime_capture_id": _capture_id(embodiment_id),
                "runtime": "isaac_sim",
                "simulator": "isaac_sim",
                "platform": "linux",
                "source_kind": "isaac_sim_runtime_backed_command_state_log",
                "capture_origin": "synthetic_verifier_fixture"
                if synthetic
                else "isaac_sim_process",
                "real_robot_success": False,
                "physical_robot_readiness": False,
                "live_runtime_support": False,
            },
        )
        _write_json(
            preflight_path,
            {
                "schema_version": "rdf_mvp3c_preflight_v0.1.0",
                "embodiment_id": embodiment_id,
                "runtime_capture_id": _capture_id(embodiment_id),
                "asset_loaded": True,
                "articulation_detected": True,
                "joint_state_readable": True,
                "action_command_writable": True,
                "source_log_rows_emitted": 2,
                "runtime_metadata_recorded": True,
            },
        )
        _write_json(
            source_dir / "metadata.json",
            {
                "embodiment_id": embodiment_id,
                "runtime_capture_id": _capture_id(embodiment_id),
                "runtime": "isaac_sim",
                "simulator": "isaac_sim",
                "source_kind": "isaac_sim_runtime_backed_command_state_log",
                "real_robot_success": False,
                "live_runtime_support": False,
                "hmd_openxr_collection_readiness": False,
            },
        )
        _write_jsonl(accepted_path, accepted_rows)
        _write_jsonl(rejected_path, rejected_rows)

        projection_dir = data / "projections" / embodiment_id
        _write_json(
            projection_dir / "trajectories" / "accepted.json",
            {"embodiment_id": embodiment_id, "frames": accepted_rows},
        )
        _write_json(
            projection_dir / "trajectories" / "rejected.json",
            {"embodiment_id": embodiment_id, "frames": rejected_rows},
        )
        _write_json(
            projection_dir / "evaluations" / "accepted.json",
            {"embodiment_id": embodiment_id, "accepted": True, "count": 1},
        )
        _write_json(
            projection_dir / "evaluations" / "rejected.json",
            {"embodiment_id": embodiment_id, "accepted": False, "count": 1},
        )
        _write_json(
            projection_dir / "curation_manifest.json",
            {
                "embodiment_id": embodiment_id,
                "accepted_count": 1,
                "rejected_count": 1,
                "accepted_reasons": ["contract_roles_present"],
                "rejected_reasons": ["negative_control_row"],
            },
        )
        _write_json(
            projection_dir / "projection_manifest.json",
            {
                "embodiment_id": embodiment_id,
                "runtime_capture_id": _capture_id(embodiment_id),
                "runtime_metadata": {
                    "data_path": runtime_metadata_path.relative_to(pkg).as_posix(),
                    "sha256": _sha(runtime_metadata_path),
                },
                "source_logs": {
                    "accepted_command_state.jsonl": {
                        "sha256": _sha(accepted_path),
                        "rows": 1,
                    },
                    "rejected_command_state.jsonl": {
                        "sha256": _sha(rejected_path),
                        "rows": 1,
                    },
                },
                "projected_artifacts": {
                    "trajectories/accepted.json": _sha(
                        projection_dir / "trajectories" / "accepted.json"
                    ),
                    "trajectories/rejected.json": _sha(
                        projection_dir / "trajectories" / "rejected.json"
                    ),
                    "evaluations/accepted.json": _sha(
                        projection_dir / "evaluations" / "accepted.json"
                    ),
                    "evaluations/rejected.json": _sha(
                        projection_dir / "evaluations" / "rejected.json"
                    ),
                    "curation_manifest.json": _sha(projection_dir / "curation_manifest.json"),
                },
                "accepted_count": 1,
                "rejected_count": 1,
            },
        )
        _write_json(
            data / "contracts" / f"{embodiment_id}_normalized_trajectory_contract.json",
            _contract(embodiment_id),
        )
        _write_json(
            data / "adapter_results" / f"{embodiment_id}_adapter_result.json",
            {
                "embodiment_id": embodiment_id,
                "status": "normalized_contract_passed",
                "accepted_count": 1,
                "rejected_count": 1,
                "required_action_roles_present": list(REQUIRED_ACTION_ROLES),
                "learning_results_measured": False,
                "policy_uplift": False,
                "learning_proven_value": False,
            },
        )
        embodiment_counts[embodiment_id] = {
            "accepted_count": 1,
            "rejected_count": 1,
            "runtime_capture_id": _capture_id(embodiment_id),
        }

    _write_json(
        data / "isaac_sim_runtime_summary.json",
        {
            "status": "synthetic_verifier_fixture"
            if synthetic
            else "isaac_sim_embodiment_source_closed",
            "runtime": "isaac_sim",
            "simulator": "isaac_sim",
            "platform": "linux",
            "embodiment_count": len(embodiments),
            "synthetic_verifier_fixture": synthetic,
        },
    )
    _write_json(
        data / "embodiment_source_summary.json",
        {
            "status": "synthetic_verifier_fixture"
            if synthetic
            else "isaac_sim_embodiment_source_closed",
            "required_embodiment_count": len(REQUIRED_EMBODIMENTS),
            "embodiment_count": len(embodiments),
            "accepted_count": sum(c["accepted_count"] for c in embodiment_counts.values()),
            "rejected_count": sum(c["rejected_count"] for c in embodiment_counts.values()),
            "embodiments": embodiment_counts,
            "cached_summary_only": True,
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
    )
    (pkg / "README.md").write_text(
        "MVP-3C exercises Isaac Sim embodiment-source verifier mechanics. "
        "It does not claim real robot success, physical robot readiness, live "
        "hardware support, live ROS2-DDS support, policy uplift, marketplace "
        "readiness, production certification, or universal robot support.\n",
        encoding="utf-8",
    )

    artifact_entries = []
    for path in sorted(data.rglob("*")):
        if path.is_file() and path.name != "artifact_index.json":
            artifact_entries.append(
                {
                    "data_path": path.relative_to(pkg).as_posix(),
                    "hash_convention": "file_bytes",
                    "file_sha256": _sha(path),
                }
            )
    _write_json(data / "artifact_index.json", {"artifact_index": artifact_entries})
    artifact_entries.append(
        {
            "data_path": "data/artifact_index.json",
            "hash_convention": "file_bytes",
            "file_sha256": _sha(data / "artifact_index.json"),
        }
    )
    _write_json(
        pkg / "package_manifest.json",
        {
            "package_name": "mvp3c_isaac_sim_embodiment_source_proof_package",
            "claims": {
                "status": "synthetic_verifier_fixture"
                if synthetic
                else "isaac_sim_embodiment_source_closed"
            },
            "artifact_index": artifact_entries,
        },
    )
    return pkg / "package_manifest.json"


def _replace_index_hash(
    entry: dict,
    *,
    package_root: Path,
    rel_path: str,
    file_sha256: str,
) -> bool:
    if entry.get("data_path") != rel_path:
        return False
    entry["file_sha256"] = file_sha256
    if "byte_size" in entry:
        entry["byte_size"] = (package_root / rel_path).stat().st_size
    return True


def _refresh_indexed_hashes(manifest: Path, *changed_rel_paths: str) -> None:
    pkg = manifest.parent
    artifact_index_path = pkg / "data" / "artifact_index.json"
    artifact_index = _read_json(artifact_index_path)
    for rel_path in changed_rel_paths:
        assert any(
            _replace_index_hash(
                entry,
                package_root=pkg,
                rel_path=rel_path,
                file_sha256=_sha(pkg / rel_path),
            )
            for entry in artifact_index["artifact_index"]
        )
    _write_json(artifact_index_path, artifact_index)

    package_manifest = _read_json(manifest)
    for rel_path in set(changed_rel_paths) | {"data/artifact_index.json"}:
        assert any(
            _replace_index_hash(
                entry,
                package_root=pkg,
                rel_path=rel_path,
                file_sha256=_sha(pkg / rel_path),
            )
            for entry in package_manifest["artifact_index"]
        )
    _write_json(manifest, package_manifest)


def _refresh_projection_manifest_hashes(
    manifest: Path,
    *,
    embodiment_id: str,
    source_logs: tuple[str, ...] = (),
    projected_artifacts: tuple[str, ...] = (),
) -> None:
    pkg = manifest.parent
    rel = f"data/projections/{embodiment_id}/projection_manifest.json"
    path = pkg / rel
    payload = _read_json(path)
    for filename in source_logs:
        source_path = pkg / "data" / "source_logs" / embodiment_id / filename
        payload["source_logs"][filename]["sha256"] = _sha(source_path)
        payload["source_logs"][filename]["rows"] = len(_read_jsonl_payloads(source_path))
    for artifact in projected_artifacts:
        artifact_path = pkg / "data" / "projections" / embodiment_id / artifact
        payload["projected_artifacts"][artifact] = _sha(artifact_path)
    _write_json(path, payload)
    _refresh_indexed_hashes(manifest, rel)


def _remove_indexed_file_and_refresh(manifest: Path, rel_path: str) -> None:
    pkg = manifest.parent
    path = pkg / rel_path
    path.unlink()

    artifact_index_path = pkg / "data" / "artifact_index.json"
    artifact_index = _read_json(artifact_index_path)
    artifact_index["artifact_index"] = [
        entry
        for entry in artifact_index["artifact_index"]
        if entry.get("data_path") != rel_path
    ]
    _write_json(artifact_index_path, artifact_index)

    package_manifest = _read_json(manifest)
    package_manifest["artifact_index"] = [
        entry
        for entry in package_manifest["artifact_index"]
        if entry.get("data_path") != rel_path
    ]
    for entry in package_manifest["artifact_index"]:
        if entry.get("data_path") == "data/artifact_index.json":
            entry["file_sha256"] = _sha(artifact_index_path)
            if "byte_size" in entry:
                entry["byte_size"] = artifact_index_path.stat().st_size
    _write_json(manifest, package_manifest)


def _copy_default_package(tmp_path: Path) -> Path:
    package_copy = tmp_path / "real_mvp3c_package"
    shutil.copytree(DEFAULT_PACKAGE, package_copy)
    return package_copy / "package_manifest.json"


def _tamper_json(path: Path, edit) -> None:
    payload = _read_json(path)
    edit(payload)
    _write_json(path, payload)


def _tamper_jsonl(path: Path, edit) -> None:
    rows = _read_jsonl_payloads(path)
    edit(rows)
    _write_jsonl(path, rows)


def _tamper_indexed_json(manifest: Path, rel_path: str, edit) -> None:
    _tamper_json(manifest.parent / rel_path, edit)
    _refresh_indexed_hashes(manifest, rel_path)


def _tamper_indexed_jsonl(manifest: Path, rel_path: str, edit) -> None:
    _tamper_jsonl(manifest.parent / rel_path, edit)
    _refresh_indexed_hashes(manifest, rel_path)


def _checks(report) -> dict:
    return {check.name: check for check in report.checks}


def _assert_failed_check(report, expected_check: str) -> None:
    checks = _checks(report)
    assert report.ok is False
    assert checks["hash_integrity"].passed is True
    assert checks[expected_check].passed is False


def test_synthetic_fixture_verifies_as_synthetic_not_closed(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path)
    report = _load_verifier().verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.exit_code == 0
    assert report.recomputed["status"] == "synthetic_verifier_fixture"
    assert report.recomputed["status"] != "isaac_sim_embodiment_source_closed"
    assert report.recomputed["embodiments"] == list(REQUIRED_EMBODIMENTS)


def test_hash_refreshed_synthetic_package_cannot_assert_original_closure(
    tmp_path: Path,
) -> None:
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        "data/config.json",
        lambda payload: payload.update(
            {
                "requested_status": "isaac_sim_embodiment_source_closed",
                "evidence_kind": "isaac_sim_runtime_backed_source_log",
                "source_evidence_level": "isaac_sim_runtime_backed_command_state_log",
            }
        ),
    )
    _tamper_json(
        manifest,
        lambda payload: payload["claims"].update(
            {"status": "isaac_sim_embodiment_source_closed"}
        ),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "synthetic_non_closure")


def test_hash_refreshed_synthetic_promotion_requires_hash_bound_runtime_capture_source(
    tmp_path: Path,
) -> None:
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        "data/config.json",
        lambda payload: payload.update(
            {
                "requested_status": "isaac_sim_embodiment_source_closed",
                "evidence_kind": "isaac_sim_runtime_backed_source_log",
                "synthetic_verifier_fixture": False,
                "runtime_evidence_captured": True,
                "closure_assertion": True,
                "source_evidence_level": "isaac_sim_runtime_backed_command_state_log",
            }
        ),
    )
    _tamper_json(
        manifest,
        lambda payload: payload["claims"].update(
            {"status": "isaac_sim_embodiment_source_closed"}
        ),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "runtime_capture_source")


def test_missing_required_embodiment_fails(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path, embodiments=REQUIRED_EMBODIMENTS[:-1])
    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "embodiment_set_exactness")


def test_source_log_byte_tamper_fails_hash_integrity(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path)
    source_log = (
        manifest.parent
        / "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl"
    )
    source_log.write_text(source_log.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["hash_integrity"].passed is False


def test_unindexed_data_file_fails(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path)
    _write_json(manifest.parent / "data" / "unindexed_runtime_claim.json", {"bad": True})

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["data_coverage"].passed is False


def test_runtime_metadata_must_be_isaac_sim(tmp_path: Path) -> None:
    embodiment_id = REQUIRED_EMBODIMENTS[0]
    rel = f"data/runtime_metadata/{embodiment_id}_runtime_metadata.json"
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(manifest, rel, lambda payload: payload.update({"runtime": "mock_sim"}))

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "runtime_metadata")


def test_preflight_required_fields_are_verifier_owned(tmp_path: Path) -> None:
    cases = (
        ("asset_loaded", False),
        ("articulation_detected", False),
        ("joint_state_readable", False),
        ("action_command_writable", False),
        ("runtime_metadata_recorded", False),
        ("source_log_rows_emitted", 1),
    )
    for field, value in cases:
        manifest = _make_package(tmp_path / field)
        rel = "data/preflight/franka_panda_isaac_sim_preflight.json"
        _tamper_indexed_json(manifest, rel, lambda payload, field=field, value=value: payload.update({field: value}))

        report = _load_verifier().verify_package(manifest)

        _assert_failed_check(report, "preflight_required_fields")


def test_runtime_capture_id_must_bind_rows_to_hash_bound_runtime_metadata(
    tmp_path: Path,
) -> None:
    manifest = _make_package(tmp_path)
    _tamper_indexed_jsonl(
        manifest,
        "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl",
        lambda rows: rows[0].update({"runtime_capture_id": "missing_capture_id"}),
    )
    _refresh_indexed_hashes(
        manifest,
        "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "runtime_capture_binding")


def test_runtime_capture_binding_rejects_row_runtime_or_embodiment_drift(
    tmp_path: Path,
) -> None:
    cases = (
        ("embodiment_id", "universal_robots_ur10e_isaac_sim"),
        ("runtime", "quest3_handtracking"),
        ("simulator", "steamvr_openxr"),
    )
    for field, value in cases:
        manifest = _make_package(tmp_path / field)
        _tamper_indexed_jsonl(
            manifest,
            "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl",
            lambda rows, field=field, value=value: rows[0].update({field: value}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_failed_check(report, "runtime_capture_binding")


def test_source_projection_hash_binding_rejects_refreshed_source_semantic_tamper(
    tmp_path: Path,
) -> None:
    manifest = _make_package(tmp_path)
    source_rel = "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl"
    _tamper_indexed_jsonl(
        manifest,
        source_rel,
        lambda rows: rows[0]["command_state"].update({"joint_positions": [9, 9, 9]}),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "source_projection_hash_binding")


def test_hash_refreshed_source_row_semantic_tamper_fails_source_log_completeness(
    tmp_path: Path,
) -> None:
    manifest = _copy_default_package(tmp_path)
    embodiment_id = "franka_panda_isaac_sim"
    source_rel = f"data/source_logs/{embodiment_id}/accepted_command_state.jsonl"
    trajectory_rel = f"data/projections/{embodiment_id}/trajectories/accepted.json"
    runtime_capture_rel = "data/runtime_capture.json"

    def corrupt_row(row: dict) -> None:
        row["command_state"]["joint_positions"] = ["not-a-number"]
        row["command_state"]["actions_by_role"]["learning_action"] = ["not-a-number"]

    _tamper_jsonl(manifest.parent / source_rel, lambda rows: corrupt_row(rows[0]))
    corrupted_rows = _read_jsonl_payloads(manifest.parent / source_rel)
    _tamper_json(
        manifest.parent / trajectory_rel,
        lambda payload: payload.update({"frames": corrupted_rows}),
    )
    _tamper_json(
        manifest.parent / runtime_capture_rel,
        lambda payload: corrupt_row(
            payload["embodiments"][embodiment_id]["source_rows"]["accepted"][0]
        ),
    )
    _refresh_projection_manifest_hashes(
        manifest,
        embodiment_id=embodiment_id,
        source_logs=("accepted_command_state.jsonl",),
        projected_artifacts=("trajectories/accepted.json",),
    )
    _refresh_indexed_hashes(manifest, source_rel, trajectory_rel, runtime_capture_rel)

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "source_log_completeness")


def test_hash_refreshed_projection_frame_drift_fails_source_projection_binding(
    tmp_path: Path,
) -> None:
    manifest = _copy_default_package(tmp_path)
    embodiment_id = "franka_panda_isaac_sim"
    trajectory_rel = f"data/projections/{embodiment_id}/trajectories/accepted.json"

    def drift_projection(payload: dict) -> None:
        payload["frames"][0]["command_state"]["joint_positions"] = [9.0, 9.0, 9.0]

    _tamper_json(manifest.parent / trajectory_rel, drift_projection)
    _refresh_projection_manifest_hashes(
        manifest,
        embodiment_id=embodiment_id,
        projected_artifacts=("trajectories/accepted.json",),
    )
    _refresh_indexed_hashes(manifest, trajectory_rel)

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "source_projection_hash_binding")


def test_summary_cache_override_fails(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        "data/embodiment_source_summary.json",
        lambda payload: payload.update({"accepted_count": 999}),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "summary_cache_consistency")


def test_contract_source_and_action_roles_are_checked(tmp_path: Path) -> None:
    cases = (
        (
            "source_runtime",
            lambda payload: payload["source"].update({"runtime": "generated_fixture"}),
            "contract_source_fields",
        ),
        (
            "missing_role",
            lambda payload: payload["required_action_roles"].remove("learning_action"),
            "contract_action_roles",
        ),
    )
    for name, edit, expected_check in cases:
        manifest = _make_package(tmp_path / name)
        rel = "data/contracts/franka_panda_isaac_sim_normalized_trajectory_contract.json"
        _tamper_indexed_json(manifest, rel, edit)

        report = _load_verifier().verify_package(manifest)

        _assert_failed_check(report, expected_check)


def test_forbidden_json_claims_fail_recursively(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        "data/runtime_metadata/franka_panda_isaac_sim_runtime_metadata.json",
        lambda payload: payload.update({"live_ur_hardware_support_claimed": True}),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_failed_check(report, "forbidden_claims")


def test_readme_positive_forbidden_claim_text_fails(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path)
    readme = manifest.parent / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "This package proves real robot success and production certification.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["forbidden_claims"].passed is False


def test_spent_ranges_are_exact_and_opened_ranges_are_empty(tmp_path: Path) -> None:
    cases = (
        (
            "spent",
            lambda payload: payload.update({"spent_no_reuse": [[40000, 40049]]}),
            "spent_no_reuse_exact",
        ),
        (
            "opened_heldout",
            lambda payload: payload["opened_ranges"].update({"heldout": [42050, 42099]}),
            "opened_ranges_empty",
        ),
    )
    for name, edit, expected_check in cases:
        manifest = _make_package(tmp_path / name)
        _tamper_indexed_json(manifest, "data/config.json", edit)

        report = _load_verifier().verify_package(manifest)

        _assert_failed_check(report, expected_check)


def test_xr_and_static_recorder_leakage_fails(tmp_path: Path) -> None:
    leak_cases = (
        (
            "quest_input_device",
            "data/contracts/franka_panda_isaac_sim_normalized_trajectory_contract.json",
            lambda payload: payload["source"].update({"input_device": "quest3_handtracking"}),
        ),
        (
            "steamvr_source_metadata",
            "data/source_logs/universal_robots_ur10e_isaac_sim/metadata.json",
            lambda payload: payload.update({"runtime": "steamvr_openxr"}),
        ),
        (
            "franka_static_for_ur",
            "data/source_logs/universal_robots_ur10e_isaac_sim/metadata.json",
            lambda payload: payload.update({"embodiment_id": "franka_panda_isaac_sim"}),
        ),
    )
    for name, rel, edit in leak_cases:
        manifest = _make_package(tmp_path / name)
        _tamper_indexed_json(manifest, rel, edit)

        report = _load_verifier().verify_package(manifest)

        assert report.ok is False


def test_verifier_import_guard_is_stdlib_only() -> None:
    tree = ast.parse(VERIFIER.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])

    allowed = set(sys.stdlib_module_names) | {"__future__"}
    forbidden = imported_roots - allowed
    assert forbidden == set()


def test_report_survives_tmp_package_copy(tmp_path: Path) -> None:
    manifest = _make_package(tmp_path / "source")
    package_copy = tmp_path / "copy"
    shutil.copytree(manifest.parent, package_copy)

    report = _load_verifier().verify_package(package_copy / "package_manifest.json")

    assert report.ok is True, report.failures()
    assert report.recomputed["status"] == "synthetic_verifier_fixture"


def test_real_runtime_backed_package_verifies_as_mvp3c_closed() -> None:
    manifest = DEFAULT_PACKAGE / "package_manifest.json"
    report = _load_verifier().verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["status"] == "isaac_sim_embodiment_source_closed"
    assert report.recomputed["accepted_count"] == 2
    assert report.recomputed["rejected_count"] == 2


def test_real_package_hash_refreshed_tamper_matrix_fails(tmp_path: Path) -> None:
    cases = (
        (
            "runtime_capture_source_drift",
            "runtime_capture_source",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/runtime_capture.json",
                lambda payload: payload["embodiments"]["franka_panda_isaac_sim"][
                    "runtime_metadata"
                ].update({"capture_origin": "synthetic_verifier_fixture"}),
            ),
        ),
        (
            "preflight_boolean",
            "preflight_required_fields",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/preflight/franka_panda_isaac_sim_preflight.json",
                lambda payload: payload.update({"asset_loaded": False}),
            ),
        ),
        (
            "runtime_capture_id_drift",
            "runtime_capture_binding",
            lambda manifest: _tamper_indexed_jsonl(
                manifest,
                "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl",
                lambda rows: rows[0].update({"runtime_capture_id": "drifted_capture"}),
            ),
        ),
        (
            "source_row_embodiment_drift",
            "runtime_capture_binding",
            lambda manifest: _tamper_indexed_jsonl(
                manifest,
                "data/source_logs/franka_panda_isaac_sim/accepted_command_state.jsonl",
                lambda rows: rows[0].update(
                    {"embodiment_id": "universal_robots_ur10e_isaac_sim"}
                ),
            ),
        ),
        (
            "runtime_metadata_removal",
            "embodiment_set_exactness",
            lambda manifest: _remove_indexed_file_and_refresh(
                manifest,
                "data/runtime_metadata/franka_panda_isaac_sim_runtime_metadata.json",
            ),
        ),
        (
            "source_row_runtime_metadata_mismatch",
            "runtime_metadata",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/runtime_metadata/franka_panda_isaac_sim_runtime_metadata.json",
                lambda payload: payload.update({"runtime_capture_id": "drifted_capture"}),
            ),
        ),
        (
            "forbidden_claim",
            "forbidden_claims",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/runtime_metadata/franka_panda_isaac_sim_runtime_metadata.json",
                lambda payload: payload.update({"live_ur_hardware_support_claimed": True}),
            ),
        ),
        (
            "opened_range",
            "opened_ranges_empty",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/config.json",
                lambda payload: payload["opened_ranges"].update({"closure": [43000, 43049]}),
            ),
        ),
        (
            "spent_range",
            "spent_no_reuse_exact",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/config.json",
                lambda payload: payload.update({"spent_no_reuse": [[40000, 40049]]}),
            ),
        ),
        (
            "count_drift",
            "summary_cache_consistency",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/embodiment_source_summary.json",
                lambda payload: payload.update({"accepted_count": 999}),
            ),
        ),
        (
            "projection_binding",
            "source_projection_hash_binding",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/projections/franka_panda_isaac_sim/projection_manifest.json",
                lambda payload: payload["source_logs"]["accepted_command_state.jsonl"].update(
                    {"sha256": "0" * 64}
                ),
            ),
        ),
        (
            "role_removal",
            "contract_action_roles",
            lambda manifest: _tamper_indexed_json(
                manifest,
                "data/contracts/franka_panda_isaac_sim_normalized_trajectory_contract.json",
                lambda payload: payload["required_action_roles"].remove("learning_action"),
            ),
        ),
    )
    for name, expected_check, tamper in cases:
        manifest = _copy_default_package(tmp_path / name)
        tamper(manifest)

        report = _load_verifier().verify_package(manifest)

        _assert_failed_check(report, expected_check)
