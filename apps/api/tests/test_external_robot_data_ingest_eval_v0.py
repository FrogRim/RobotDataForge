from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.external_robot_data_ingest import (  # noqa: E402
    SOURCE_METADATA_SCHEMA_VERSION,
    STAGING_DERIVATION_ALGORITHM,
    build_adapter_staging_source,
    validate_external_source_dir,
    verify_adapter_staging_source,
)
from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402


def _load_script(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_package_hashes(package_dir: Path) -> None:
    data_dir = package_dir / "data"
    artifact_entries = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_index.json":
            artifact_entries.append(
                {
                    "data_path": path.relative_to(package_dir).as_posix(),
                    "file_sha256": _sha256(path),
                    "byte_size": path.stat().st_size,
                    "hash_convention": "file_bytes",
                }
            )
    _write_json(
        data_dir / "artifact_index.json",
        {
            "schema_version": "rdf_external_robot_data_ingest_eval_artifact_index_v0.1.0",
            "artifact_index": artifact_entries,
        },
    )
    manifest = json.loads((package_dir / "package_manifest.json").read_text(encoding="utf-8"))
    manifest_entries = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file():
            manifest_entries.append(
                {
                    "data_path": path.relative_to(package_dir).as_posix(),
                    "file_sha256": _sha256(path),
                    "byte_size": path.stat().st_size,
                    "hash_convention": "file_bytes",
                }
            )
    manifest["artifact_index"] = manifest_entries
    _write_json(package_dir / "package_manifest.json", manifest)


def _promote_package_copy_to_external_data_evaluated(package_dir: Path) -> None:
    manifest_path = package_dir / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["package_status"] = "external_data_evaluated"
    manifest["external_source_included"] = True
    _write_json(manifest_path, manifest)

    config_path = package_dir / "data/config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["status"] = "external_data_evaluated"
    config["package_status"] = "external_data_evaluated"
    config["external_source_included"] = True
    _write_json(config_path, config)

    buyer_path = package_dir / "data/reports/buyer_data_evaluation_report.json"
    buyer = json.loads(buyer_path.read_text(encoding="utf-8"))
    buyer["claim"] = "external_data_evaluated"
    buyer["external_data_evaluated"] = True
    _write_json(buyer_path, buyer)

    source_availability_path = package_dir / "data/source/source_availability_report.json"
    source_availability = json.loads(source_availability_path.read_text(encoding="utf-8"))
    source_availability["external_source_included"] = True
    source_availability["external_data_evaluated"] = True
    _write_json(source_availability_path, source_availability)


def _run_external_ingest_verifier(package_manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_external_robot_data_ingest_package.py"),
            str(package_manifest),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def _metadata(**overrides) -> dict:
    payload = {
        "schema_version": SOURCE_METADATA_SCHEMA_VERSION,
        "source_id": "external_ur_log_20260623_temp",
        "source_origin": "external_supplied_recorded_log",
        "source_acquisition": "file_drop",
        "source_owner": "Review Partner Lab",
        "source_license": "private_review",
        "source_redistribution_allowed": True,
        "provenance_trust_tier": "attested_file_drop",
        "public_source_url": None,
        "upstream_dataset_revision": None,
        "upstream_published_sha256": None,
        "recorded_log_backed": True,
        "generated_by_rdf": False,
        "repo_fixture": False,
        "robot_family_claimed": "universal_robots_ur",
        "embodiment_class_claimed": "industrial_arm",
        "command_stream": {
            "interface": "industrial_arm_command_fixture",
            "unit": "meters_radians_normalized_gripper",
        },
        "state_stream": {"interface": "industrial_arm_state_stream_fixture"},
        "coordinate_frames_declared": {
            "command_frame": "task_frame",
            "state_frame": "robot_base_frame",
        },
    }
    payload.update(overrides)
    return payload


def _row(sequence_id: int, timestamp: float, *, accepted: bool = True) -> dict:
    return {
        "sequence_id": sequence_id,
        "timestamp": timestamp,
        "task_phase": "insert" if accepted else "approach_or_contact_failure",
        "command": {
            "interface": "industrial_arm_command_fixture",
            "unit": "meters_radians_normalized_gripper",
            "vector": [0.011, -0.002, -0.036, 0.001, -0.001, 0.0, 0.28],
        },
        "state": {
            "interface": "industrial_arm_state_stream_fixture",
            "joint_positions": [0.0, -0.42, 0.19, -1.89, 0.0, 1.58, 0.77],
            "end_effector_position": [0.432, -0.016, 0.09],
            "end_effector_quaternion": [1.0, 0.0, 0.0, 0.0],
            "object_position": [0.44, -0.01, 0.06],
            "object_quaternion": [1.0, 0.0, 0.0, 0.0],
        },
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
        "quality": {
            "action_contract_valid": accepted,
            "replay_verified": accepted,
            "control_quality": "pass" if accepted else "fail",
            "rejection_reason": None if accepted else "INDUSTRIAL_ACTION_CONTRACT_MISMATCH",
        },
    }


def _write_source(
    source_dir: Path,
    *,
    metadata: dict | None = None,
    accepted_rows: list[dict] | None = None,
    rejected_rows: list[dict] | None = None,
) -> Path:
    accepted = accepted_rows if accepted_rows is not None else [_row(i, i * 0.04) for i in range(1, 5)]
    rejected = rejected_rows if rejected_rows is not None else [_row(5, 0.20, accepted=False)]
    _write_json(source_dir / "metadata.json", metadata if metadata is not None else _metadata())
    _write_jsonl(source_dir / "accepted_command_state.jsonl", accepted)
    _write_jsonl(source_dir / "rejected_command_state.jsonl", rejected)
    (source_dir / "PROVENANCE.md").write_text("Attested external review drop.\n", encoding="utf-8")
    (source_dir / "LICENSE.txt").write_text("private_review\n", encoding="utf-8")
    return source_dir


def test_valid_temp_external_source_without_adapter_only_metadata_passes(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path / "external_drop")

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert report.ok, report.issues
    assert report.package_status == "external_data_evaluated"
    assert report.accepted_count == 4
    assert report.rejected_count == 1
    assert "metadata.json" in report.source_file_hashes
    assert "accepted_command_state.jsonl" in report.source_file_hashes
    assert "rejected_command_state.jsonl" in report.source_file_hashes
    assert "adapter_version" not in report.metadata
    assert "source_provenance" not in report.metadata


def test_external_data_evaluated_rejects_repo_fixture_path() -> None:
    source_dir = ROOT / "fixtures" / "mvp1plus" / "universal_robots_ur_recorded_log_fixture"

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert any("forbidden source path" in issue for issue in report.issues)


def test_external_data_evaluated_rejects_generated_or_fixture_metadata(tmp_path: Path) -> None:
    source_dir = _write_source(
        tmp_path / "external_drop",
        metadata=_metadata(generated_by_rdf=True, repo_fixture=True),
    )

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert "metadata.generated_by_rdf must be false" in report.issues
    assert "metadata.repo_fixture must be false" in report.issues


def test_attested_file_drop_rejects_placeholder_owner_and_license(tmp_path: Path) -> None:
    source_dir = _write_source(
        tmp_path / "external_drop",
        metadata=_metadata(
            source_owner="person_or_org_or_public_dataset",
            source_license="public_license_name",
        ),
    )

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert "metadata.source_owner placeholder" in report.issues
    assert "metadata.source_license placeholder" in report.issues


def test_refetchable_public_source_requires_url_revision_and_hash(tmp_path: Path) -> None:
    source_dir = _write_source(
        tmp_path / "external_drop",
        metadata=_metadata(
            source_origin="public_dataset_recorded_log",
            provenance_trust_tier="refetchable_public_source",
            source_license="Apache-2.0",
            public_source_url=None,
            upstream_dataset_revision=None,
            upstream_published_sha256=None,
        ),
    )

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert "metadata.public_source_url required for refetchable_public_source" in report.issues
    assert "metadata.upstream_dataset_revision required for refetchable_public_source" in report.issues
    assert "metadata.upstream_published_sha256 required for refetchable_public_source" in report.issues


def test_row_contract_rejects_missing_required_fields(tmp_path: Path) -> None:
    bad_row = _row(1, 0.04)
    del bad_row["action_semantics"]["normalized_contract_roles"]
    source_dir = _write_source(
        tmp_path / "external_drop",
        accepted_rows=[bad_row, *[_row(i, i * 0.04) for i in range(2, 5)]],
    )

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert any("accepted row 1 action_semantics.normalized_contract_roles missing" in issue for issue in report.issues)


def test_committed_evaluated_row_count_contract_requires_four_accepted_and_one_rejected(tmp_path: Path) -> None:
    source_dir = _write_source(
        tmp_path / "external_drop",
        accepted_rows=[_row(1, 0.04), _row(2, 0.08), _row(3, 0.12)],
        rejected_rows=[_row(4, 0.16, accepted=False), _row(5, 0.20, accepted=False)],
    )

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert "accepted_rows < 4" in report.issues
    assert "rejected_rows must equal 1 for v0 committed/evaluated evidence" in report.issues


def test_rejected_rows_require_failure_predicate_or_reason(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path / "external_drop", rejected_rows=[_row(5, 0.20, accepted=True)])

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert "rejected row 1 must include a failure predicate or rejection reason" in report.issues


def test_timestamp_monotonicity_and_numeric_vectors_are_enforced(tmp_path: Path) -> None:
    bad_row = _row(2, 0.01)
    bad_row["command"]["vector"] = ["bad"]
    source_dir = _write_source(
        tmp_path / "external_drop",
        accepted_rows=[_row(1, 0.04), bad_row, _row(3, 0.12), _row(4, 0.16)],
    )

    report = validate_external_source_dir(source_dir, package_status="external_data_evaluated")

    assert not report.ok
    assert "accepted rows timestamps must be monotonic" in report.issues
    assert "accepted row 2 command.vector must be numeric vector" in report.issues


def test_builds_deterministic_adapter_staging_source_without_mutating_raw_metadata(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path / "external_drop")
    raw_before = (source_dir / "metadata.json").read_text(encoding="utf-8")
    staging_dir = tmp_path / "staging"

    report = build_adapter_staging_source(source_dir, staging_dir)

    assert report.ok, report.issues
    assert (source_dir / "metadata.json").read_text(encoding="utf-8") == raw_before
    staging_metadata = json.loads((staging_dir / "metadata.json").read_text(encoding="utf-8"))
    derivation = json.loads((staging_dir / "staging_derivation_report.json").read_text(encoding="utf-8"))
    assert staging_metadata["adapter_id"] == "universal_robots_ur_industrial_arm"
    assert staging_metadata["adapter_version"]
    assert staging_metadata["source_provenance"]["external_source_id"] == "external_ur_log_20260623_temp"
    assert derivation["derivation_algorithm"] == STAGING_DERIVATION_ALGORITHM
    assert derivation["selected_adapter_id"] == "universal_robots_ur_industrial_arm"
    assert derivation["raw_metadata_sha256"] == report.raw_metadata_sha256
    assert (source_dir / "accepted_command_state.jsonl").read_bytes() == (
        staging_dir / "accepted_command_state.jsonl"
    ).read_bytes()
    assert (source_dir / "rejected_command_state.jsonl").read_bytes() == (
        staging_dir / "rejected_command_state.jsonl"
    ).read_bytes()

    projection = RobotEmbodimentAdapterRegistry.create(
        "universal_robots_ur_industrial_arm"
    ).project_source_evidence(source_dir=staging_dir, output_dir=tmp_path / "projection")
    assert projection.passed is True, projection.issues


def test_verifies_staging_derivation_and_detects_raw_metadata_tamper(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path / "external_drop")
    staging_dir = tmp_path / "staging"
    build_adapter_staging_source(source_dir, staging_dir)

    raw_metadata = json.loads((source_dir / "metadata.json").read_text(encoding="utf-8"))
    raw_metadata["source_owner"] = "Different Owner"
    _write_json(source_dir / "metadata.json", raw_metadata)

    report = verify_adapter_staging_source(source_dir, staging_dir)

    assert not report.ok
    assert "raw_metadata_sha256 mismatch" in report.issues
    assert "derived staging metadata mismatch" in report.issues


def test_verifies_staging_derivation_and_detects_staging_metadata_tamper(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path / "external_drop")
    staging_dir = tmp_path / "staging"
    build_adapter_staging_source(source_dir, staging_dir)

    staging_metadata = json.loads((staging_dir / "metadata.json").read_text(encoding="utf-8"))
    staging_metadata["adapter_version"] = "tampered"
    _write_json(staging_dir / "metadata.json", staging_metadata)

    report = verify_adapter_staging_source(source_dir, staging_dir)

    assert not report.ok
    assert "derived_metadata_sha256 mismatch" in report.issues
    assert "derived staging metadata mismatch" in report.issues


def test_verifies_staging_derivation_and_detects_staging_row_tamper(tmp_path: Path) -> None:
    source_dir = _write_source(tmp_path / "external_drop")
    staging_dir = tmp_path / "staging"
    build_adapter_staging_source(source_dir, staging_dir)

    rows = [
        json.loads(line)
        for line in (staging_dir / "accepted_command_state.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows[0]["command"]["vector"][0] = 99.0
    _write_jsonl(staging_dir / "accepted_command_state.jsonl", rows)

    report = verify_adapter_staging_source(source_dir, staging_dir)

    assert not report.ok
    assert "staging_accepted_sha256 differs from source accepted sha256" in report.issues
    assert "staging_accepted_sha256 mismatch" in report.issues


def test_runner_projects_external_jsonl_source_through_adapter_staging(tmp_path: Path) -> None:
    runner = _load_script("run_external_robot_data_ingest_eval_v0", "scripts/run_external_robot_data_ingest_eval_v0.py")
    source_dir = _write_source(tmp_path / "external_drop")
    output_dir = tmp_path / "output"

    report = runner.run_external_ingest_eval(
        external_source_dir=source_dir,
        output_dir=output_dir,
        clean=True,
        package_status="external_data_evaluated",
    )

    assert report["package_status"] == "external_data_evaluated"
    assert report["status"] == "external_data_evaluated"
    assert report["gates"]["source_validation_passed"] is True
    assert report["gates"]["staging_derivation_verified"] is True
    assert report["gates"]["adapter_projection_passed"] is True
    assert report["gates"]["normalized_contract_emitted"] is True
    assert report["gates"]["hdf5_exported"] is True
    assert report["gates"]["hdf5_inspection_clean"] is True
    assert report["gates"]["trainer_smoke_passed"] is True
    assert report["counts"] == {"accepted_rows": 4, "rejected_rows": 1}
    assert report["selected_adapter_id"] == "universal_robots_ur_industrial_arm"
    assert "metadata.json" in report["source_file_hashes"]
    assert Path(report["artifact_paths"]["staging_derivation_report"]).exists()
    assert Path(report["artifact_paths"]["projection_manifest"]).exists()
    assert Path(report["artifact_paths"]["accepted_trajectory"]).exists()
    assert Path(report["artifact_paths"]["rejected_trajectory"]).exists()
    assert Path(report["artifact_paths"]["normalized_contract"]).exists()
    assert Path(report["artifact_paths"]["hdf5_export"]).exists()
    assert Path(report["artifact_paths"]["hdf5_inspection"]).exists()
    assert Path(report["artifact_paths"]["trainer_smoke_report"]).exists()
    contract = json.loads(Path(report["artifact_paths"]["normalized_contract"]).read_text(encoding="utf-8"))
    evidence = contract["robot_embodiment_adapter_evidence"]
    assert evidence["source_provenance"]["source_evidence_level"] == "generated_recorded_log"
    assert evidence["export_trainer_evidence"]["trainer_smoke_passed"] is True
    assert report["non_claims"]["real_robot_success"] is False
    assert report["non_claims"]["live_ur_rtde_support"] is False


def test_runner_degrades_to_contract_ready_when_source_missing(tmp_path: Path) -> None:
    runner = _load_script("run_external_robot_data_ingest_eval_v0", "scripts/run_external_robot_data_ingest_eval_v0.py")

    report = runner.run_external_ingest_eval(
        external_source_dir=tmp_path / "missing_external_drop",
        output_dir=tmp_path / "output",
        clean=True,
        package_status="external_ingest_contract_ready",
    )

    assert report["package_status"] == "external_ingest_contract_ready"
    assert report["status"] == "external_ingest_contract_ready"
    assert report["gates"]["source_validation_passed"] is False
    assert report["gates"]["adapter_projection_passed"] is False
    assert report["gates"]["trainer_smoke_passed"] is False
    assert report["counts"] == {"accepted_rows": 0, "rejected_rows": 0}
    assert report["artifact_paths"]["staging_derivation_report"] is None
    assert report["artifact_paths"]["normalized_contract"] is None
    assert report["artifact_paths"]["trainer_smoke_report"] is None
    assert report["stop_reason"] == "no eligible external source rows available"


def test_builds_contract_ready_proof_package_without_canonical_external_rows(tmp_path: Path) -> None:
    runner = _load_script("run_external_robot_data_ingest_eval_v0", "scripts/run_external_robot_data_ingest_eval_v0.py")
    package_dir = tmp_path / "proof_package"

    manifest = runner.build_external_ingest_proof_package(
        package_dir=package_dir,
        external_source_dir=tmp_path / "missing_external_drop",
        clean=True,
        package_status="external_ingest_contract_ready",
    )

    assert manifest["package_status"] == "external_ingest_contract_ready"
    assert manifest["external_source_included"] is False
    assert not (package_dir / "data/source/accepted_command_state.jsonl").exists()
    assert not (package_dir / "data/source/rejected_command_state.jsonl").exists()
    assert (package_dir / "README.md").exists()
    assert (package_dir / "package_manifest.json").exists()
    assert (package_dir / "data/config.json").exists()
    assert (package_dir / "data/source/source_availability_report.json").exists()
    assert (package_dir / "data/reports/buyer_data_evaluation_report.json").exists()
    assert (package_dir / "data/non_claims_attestation.json").exists()
    assert (package_dir / "data/artifact_index.json").exists()

    config = json.loads((package_dir / "data/config.json").read_text(encoding="utf-8"))
    assert config["external_source_included"] is False
    assert config["status"] == "external_ingest_contract_ready"
    assert config["allowed_future_status"] == "external_data_evaluated"
    buyer = json.loads((package_dir / "data/reports/buyer_data_evaluation_report.json").read_text(encoding="utf-8"))
    assert buyer["claim"] == "external_ingest_contract_ready"
    assert buyer["external_data_evaluated"] is False
    assert "does not cryptographically prove physical external origin" in buyer["provenance_trust_boundary"]
    non_claims = json.loads((package_dir / "data/non_claims_attestation.json").read_text(encoding="utf-8"))
    assert non_claims["non_claims"]["real_robot_success"] is False
    assert non_claims["non_claims"]["policy_uplift_or_learning_proven"] is False
    artifact_index = json.loads((package_dir / "data/artifact_index.json").read_text(encoding="utf-8"))
    indexed_paths = {entry["data_path"] for entry in artifact_index["artifact_index"]}
    assert "data/config.json" in indexed_paths
    assert "data/reports/buyer_data_evaluation_report.json" in indexed_paths
    assert all("storage/" not in entry["data_path"] for entry in manifest["artifact_index"])


def test_external_ingest_verifier_accepts_canonical_contract_ready_package() -> None:
    result = _run_external_ingest_verifier(
        ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json"
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: VERIFIED" in result.stdout
    assert "status=external_ingest_contract_ready" in result.stdout
    assert "external_source_included=false" in result.stdout


def test_external_ingest_verifier_rejects_hash_tamper(tmp_path: Path) -> None:
    package_copy = tmp_path / "package"
    shutil.copytree(ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package", package_copy)
    config = json.loads((package_copy / "data/config.json").read_text(encoding="utf-8"))
    config["external_source_included"] = True
    _write_json(package_copy / "data/config.json", config)

    result = _run_external_ingest_verifier(package_copy / "package_manifest.json")

    assert result.returncode != 0
    assert "data/config.json sha256 mismatch" in result.stdout


def test_external_ingest_verifier_is_stdlib_only() -> None:
    script = (ROOT / "scripts/verify_external_robot_data_ingest_package.py").read_text(encoding="utf-8")
    forbidden_imports = ("app.", "numpy", "h5py", "pandas", "torch")

    assert not any(forbidden in script for forbidden in forbidden_imports)


def test_external_ingest_verifier_rejects_source_rows_in_contract_ready_even_if_hashes_refreshed(tmp_path: Path) -> None:
    package_copy = tmp_path / "package"
    shutil.copytree(ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package", package_copy)
    _write_json(package_copy / "data/source/metadata.json", _metadata())
    _write_jsonl(package_copy / "data/source/accepted_command_state.jsonl", [_row(i, i * 0.04) for i in range(1, 5)])
    _write_jsonl(package_copy / "data/source/rejected_command_state.jsonl", [_row(5, 0.20, accepted=False)])
    _refresh_package_hashes(package_copy)

    result = _run_external_ingest_verifier(package_copy / "package_manifest.json")

    assert result.returncode != 0
    assert "contract-ready package must not include data/source/accepted_command_state.jsonl" in result.stdout
    assert "contract-ready package must not include data/source/rejected_command_state.jsonl" in result.stdout


def test_external_ingest_verifier_rejects_nonclaim_true_even_if_hashes_refreshed(tmp_path: Path) -> None:
    package_copy = tmp_path / "package"
    shutil.copytree(ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package", package_copy)
    non_claims_path = package_copy / "data/non_claims_attestation.json"
    non_claims = json.loads(non_claims_path.read_text(encoding="utf-8"))
    non_claims["non_claims"]["real_robot_success"] = True
    _write_json(non_claims_path, non_claims)
    _refresh_package_hashes(package_copy)

    result = _run_external_ingest_verifier(package_copy / "package_manifest.json")

    assert result.returncode != 0
    assert "non_claims_attestation forbidden claim real_robot_success must be false" in result.stdout


def test_external_ingest_verifier_rejects_spent_seed_even_if_hashes_refreshed(tmp_path: Path) -> None:
    package_copy = tmp_path / "package"
    shutil.copytree(ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package", package_copy)
    config_path = package_copy / "data/config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["example_seed"] = 42000
    _write_json(config_path, config)
    _refresh_package_hashes(package_copy)

    result = _run_external_ingest_verifier(package_copy / "package_manifest.json")

    assert result.returncode != 0
    assert "reuses spent seed 42000" in result.stdout


def test_external_ingest_verifier_rejects_readme_forbidden_claim_leakage(tmp_path: Path) -> None:
    package_copy = tmp_path / "package"
    shutil.copytree(ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package", package_copy)
    readme_path = package_copy / "README.md"
    readme_path.write_text(readme_path.read_text(encoding="utf-8") + "\nreal_robot_success: true\n", encoding="utf-8")

    result = _run_external_ingest_verifier(package_copy / "package_manifest.json")

    assert result.returncode != 0
    assert "README forbidden claim real_robot_success leaked true" in result.stdout


def test_external_ingest_verifier_rejects_evaluated_status_until_semantic_parity_exists(tmp_path: Path) -> None:
    package_copy = tmp_path / "package"
    shutil.copytree(ROOT / "docs/proof/external_robot_data_ingest_eval_v0_proof_package", package_copy)
    _write_json(package_copy / "data/source/metadata.json", _metadata())
    _write_jsonl(package_copy / "data/source/accepted_command_state.jsonl", [_row(i, i * 0.04) for i in range(1, 5)])
    _write_jsonl(package_copy / "data/source/rejected_command_state.jsonl", [_row(5, 0.20, accepted=False)])
    _promote_package_copy_to_external_data_evaluated(package_copy)
    _refresh_package_hashes(package_copy)

    result = _run_external_ingest_verifier(package_copy / "package_manifest.json")

    assert result.returncode != 0
    assert "external_data_evaluated verifier requires semantic parity artifacts before enablement" in result.stdout
