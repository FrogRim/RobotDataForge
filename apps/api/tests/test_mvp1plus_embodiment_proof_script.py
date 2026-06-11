from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.normalized_trajectory_contract import NormalizedTrajectoryContractValidator  # noqa: E402
from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402


EXPECTED_ADAPTER_IDS = {
    "franka_research_arm",
    "robotis_sh5_ros2_dds",
    "universal_robots_ur_industrial_arm",
    "universal_robots_ur_external_style",
}
CORE_ADAPTER_IDS = EXPECTED_ADAPTER_IDS - {"universal_robots_ur_external_style"}
EXPECTED_REJECTION_REASONS = {
    "franka_research_arm": "ACTION_SATURATION_OR_CONTROL_QUALITY_FAILURE",
    "robotis_sh5_ros2_dds": "COMMAND_STATE_TIMESTAMP_GAP",
    "universal_robots_ur_industrial_arm": "INDUSTRIAL_ACTION_CONTRACT_MISMATCH",
    "universal_robots_ur_external_style": "INDUSTRIAL_ACTION_CONTRACT_MISMATCH",
}
EXPECTED_PROOF_ID = "rdf_mvp1plus_cross_embodiment_recorded_log_adapter_proof_v0"
EXPECTED_CONTRACT_NAME = "mvp1plus_robot_embodiment_recorded_log_contract"
UR_RECORDED_LOG_FIXTURE = ROOT / "fixtures" / "mvp1plus" / "universal_robots_ur_recorded_log_fixture"


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def lower_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def build_proof(output_dir: Path) -> dict[str, Any]:
    proof = load_script("run_mvp1plus_embodiment_proof")
    report = proof.build_mvp1plus_embodiment_proof(output_dir, clean=True)
    assert report["passed"] is True
    return report


def test_robot_embodiment_adapter_registry_profiles_are_static_and_structured() -> None:
    profiles = {profile.adapter_id: profile for profile in RobotEmbodimentAdapterRegistry.list_profiles()}

    assert set(profiles) == EXPECTED_ADAPTER_IDS
    for adapter_id, profile in profiles.items():
        artifact = profile.to_artifact()
        assert artifact["adapter_id"] == adapter_id
        assert artifact["schema_version"] == "rdf_robot_embodiment_adapter_registry_v0.1.0"
        assert artifact["adapter_version"] == "rdf_robot_embodiment_adapter_v0.1.0"
        assert artifact["builder_class"]
        assert artifact["adapter_class"] == "RobotEmbodimentAdapter"
        assert artifact["capabilities"]
        assert artifact["limitations"]
        assert artifact["claim_boundary"]["real_robot_success_claimed"] is False
        assert artifact["claim_boundary"]["physical_robot_readiness_claimed"] is False
        assert artifact["claim_boundary"]["policy_uplift_claimed"] is False
        assert profile.rejection_reason == EXPECTED_REJECTION_REASONS[adapter_id]

    assert profiles["franka_research_arm"].embodiment_class == "research_arm"
    assert profiles["robotis_sh5_ros2_dds"].embodiment_class == "ros2_dds_manipulator"
    assert profiles["universal_robots_ur_industrial_arm"].embodiment_class == "industrial_arm"
    assert profiles["universal_robots_ur_external_style"].generated_external_style_sample is True


def test_mvp1plus_generates_jsonl_source_evidence_and_projected_inputs(tmp_path: Path) -> None:
    build_proof(tmp_path / "mvp1plus")

    for adapter_id in EXPECTED_ADAPTER_IDS:
        source_dir = tmp_path / "mvp1plus" / "source_logs" / adapter_id
        metadata = read_json(source_dir / "metadata.json")
        accepted_rows = (source_dir / "accepted_command_state.jsonl").read_text(encoding="utf-8").splitlines()
        rejected_rows = (source_dir / "rejected_command_state.jsonl").read_text(encoding="utf-8").splitlines()
        projection = read_json(tmp_path / "mvp1plus" / "projected_inputs" / adapter_id / "projection_manifest.json")
        curation = read_json(tmp_path / "mvp1plus" / "projected_inputs" / adapter_id / "curation_manifest.json")

        assert metadata["adapter_id"] == adapter_id
        assert metadata["source_provenance"]["recorded_log_backed"] is True
        expected_accepted_rows = 4 if adapter_id == "universal_robots_ur_industrial_arm" else 1
        assert len(accepted_rows) == expected_accepted_rows
        assert len(rejected_rows) == 1
        assert projection["projection_semantics"]["raw_jsonl_is_direct_trainer_input"] is False
        assert Path(projection["accepted"]["trajectory"]).exists()
        assert Path(projection["rejected"]["trajectory"]).exists()
        assert curation["accepted_count"] == 1
        assert curation["rejected_count"] == 1
        assert curation["rejection_reason_distribution"] == {EXPECTED_REJECTION_REASONS[adapter_id]: 1}


def test_mvp1plus_uses_repo_local_ur_recorded_log_fixture_by_default(tmp_path: Path) -> None:
    assert (UR_RECORDED_LOG_FIXTURE / "metadata.json").exists()

    build_proof(tmp_path / "mvp1plus")

    output_source_dir = tmp_path / "mvp1plus" / "source_logs" / "universal_robots_ur_industrial_arm"
    metadata = read_json(output_source_dir / "metadata.json")
    accepted_rows = (output_source_dir / "accepted_command_state.jsonl").read_text(encoding="utf-8").splitlines()
    projection = read_json(
        tmp_path
        / "mvp1plus"
        / "projected_inputs"
        / "universal_robots_ur_industrial_arm"
        / "projection_manifest.json"
    )
    accepted_trajectory = read_json(Path(projection["accepted"]["trajectory"]))
    accepted_phases = [
        frame["metadata"]["action_phase"]
        for frame in accepted_trajectory["frames"]
    ]

    assert metadata["source_provenance"]["source_type"] == "file_backed_recorded_log_fixture"
    assert metadata["source_provenance"]["repo_local_recorded_log_fixture"] is True
    assert metadata["source_provenance"]["fixture_path"] == str(UR_RECORDED_LOG_FIXTURE)
    assert metadata["claim_boundary"]["real_robot_success_claimed"] is False
    assert len(accepted_rows) == 4
    assert accepted_phases == ["APPROACH", "CONTACT", "INSERT", "SEAT"]


def test_mvp1plus_ur_recorded_log_dir_overrides_default_fixture(tmp_path: Path) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    profile = RobotEmbodimentAdapterRegistry.get("universal_robots_ur_industrial_arm")
    custom_source = tmp_path / "custom_ur_log"
    proof._write_source_logs(profile, custom_source)
    metadata_path = custom_source / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["source_provenance"]["source_type"] = "external_file_backed_recorded_log"
    metadata["source_provenance"]["repo_local_recorded_log_fixture"] = False
    metadata["source_provenance"]["source_capture_id"] = "custom_ur_recorded_log_001"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    report = proof.build_mvp1plus_embodiment_proof(
        tmp_path / "mvp1plus",
        clean=True,
        ur_recorded_log_dir=custom_source,
    )

    output_metadata = read_json(
        tmp_path / "mvp1plus" / "source_logs" / "universal_robots_ur_industrial_arm" / "metadata.json"
    )
    assert report["passed"] is True
    assert output_metadata["source_provenance"]["source_capture_id"] == "custom_ur_recorded_log_001"
    assert f"--ur-recorded-log-dir {custom_source}" in report["reproduce_command"]


def test_mvp1plus_lineage_hashes_source_and_projected_artifacts(tmp_path: Path) -> None:
    report = build_proof(tmp_path / "mvp1plus")
    ur_proof = next(
        item for item in report["adapter_proofs"] if item["adapter_id"] == "universal_robots_ur_industrial_arm"
    )
    ur_buyer = next(
        item
        for item in report["buyer_summary"]["adapter_summaries"]
        if item["adapter_id"] == "universal_robots_ur_industrial_arm"
    )
    lineage = ur_proof["lineage_evidence"]
    source_metadata_path = tmp_path / "mvp1plus" / "source_logs" / "universal_robots_ur_industrial_arm" / "metadata.json"
    accepted_trajectory_path = Path(ur_proof["projected_inputs"]["accepted_trajectory"])

    assert lineage == ur_buyer["lineage_evidence"]
    assert lineage["source_evidence_type"] == "file_backed_recorded_log_fixture"
    assert lineage["source_files"]["metadata_json"]["sha256"] == sha256_file(source_metadata_path)
    assert lineage["projected_artifacts"]["accepted_trajectory"]["sha256"] == sha256_file(accepted_trajectory_path)
    assert lineage["source_bundle_sha256"]
    assert lineage["projected_bundle_sha256"]


def test_mvp1plus_adapter_emissions_pass_contract_validator_and_preserve_rejections(
    tmp_path: Path,
) -> None:
    build_proof(tmp_path / "mvp1plus")
    validator = NormalizedTrajectoryContractValidator()
    summary = read_json(tmp_path / "mvp1plus" / "mvp1plus_embodiment_proof_summary.json")

    assert summary["adapter_count"] == 4
    assert summary["accepted_count"] == 4
    assert summary["rejected_count"] == 4
    assert summary["rejection_reason_coverage_passed"] is True

    for adapter_id in EXPECTED_ADAPTER_IDS:
        contract = read_json(
            tmp_path / "mvp1plus" / "normalized_contracts" / f"{adapter_id}_normalized_trajectory_contract.json"
        )
        assert validator.validate_learning_eligibility(contract) == []
        assert contract["proof_id"] == EXPECTED_PROOF_ID
        assert contract["contract_name"] == EXPECTED_CONTRACT_NAME
        assert contract["source_profile"]["input_device"] == "recorded_command_state_log"
        assert contract["source_profile"]["simulator"] == "recorded_log_projection"
        assert contract["source_profile"]["adapter_id"] == adapter_id
        evidence = contract["robot_embodiment_adapter_evidence"]
        provenance = evidence["source_provenance"]
        assert evidence["fixture_basis"] == "recorded_log_backed_robot_embodiment_adapter"
        assert provenance["projected_source_profile"] == contract["source_profile"]
        assert provenance["builder_source_profile"]
        assert evidence["adapter_call_evidence"]["registry_lookup_performed"] is True
        assert evidence["adapter_call_evidence"]["builder_called"] is True
        assert evidence["adapter_call_evidence"]["validator_checked"] is True
        assert evidence["adapter_call_evidence"]["uses_preprojected_inputs"] is True
        assert evidence["adapter_call_evidence"]["fixture_clone_prevention"]
        curation = evidence["curation_evidence"]
        assert curation["rejection_reason_distribution"] == {EXPECTED_REJECTION_REASONS[adapter_id]: 1}


def test_mvp1plus_exports_integrated_and_per_embodiment_hdf5_with_trainer_smoke(
    tmp_path: Path,
) -> None:
    report = build_proof(tmp_path / "mvp1plus")
    summary = read_json(tmp_path / "mvp1plus" / "mvp1plus_embodiment_proof_summary.json")

    integrated = summary["integrated_export"]
    assert Path(report["artifact_paths"]["hdf5"]).exists()
    assert integrated["hdf5_export_exists"] is True
    assert integrated["hdf5_inspection_clean"] is True
    assert integrated["trainer_smoke_passed"] is True
    assert len(integrated["episode_ids"]) == 4

    for adapter in summary["adapters"]:
        adapter_id = adapter["adapter_id"]
        inspection = read_json(tmp_path / "mvp1plus" / "hdf5" / f"{adapter_id}.inspection.json")
        trainer = read_json(tmp_path / "mvp1plus" / "hdf5" / f"{adapter_id}.trainer_smoke.json")
        assert inspection["issues"] == []
        assert trainer["loader_smoke_passed"] is True
        assert trainer["trainer_dry_run_passed"] is True
        assert trainer["learning_results_measured"] is False
        assert trainer["curated_vs_uncurated_uplift"] is None


def test_mvp1plus_buyer_summary_is_readable_and_claim_safe(tmp_path: Path) -> None:
    build_proof(tmp_path / "mvp1plus")

    buyer = read_json(tmp_path / "mvp1plus" / "mvp1plus_buyer_summary.json")
    text = lower_text(buyer)

    assert buyer["passed"] is True
    assert set(buyer["buyer_questions"]["which_adapter_emitted_it"]) == EXPECTED_ADAPTER_IDS
    assert buyer["buyer_questions"]["was_replay_or_consistency_checked"] is True
    assert buyer["buyer_questions"]["was_hdf5_export_produced"] is True
    assert buyer["buyer_questions"]["can_a_trainer_load_it"] is True
    assert "generated external-style" in text
    assert "public sample" in text
    assert "policy uplift" in text
    assert "real robot success" in text
    for key in (
        "real_robot_success",
        "physical_robot_readiness",
        "live_runtime_support",
        "hmd_readiness",
        "policy_uplift",
        "universal_robot_support",
        "public_sample_import",
        "marketplace_readiness",
        "db_migration",
        "production_auth",
    ):
        assert buyer["non_claims"][key] is False

    for adapter in buyer["adapter_summaries"]:
        assert adapter["adapter_id"]
        assert adapter["adapter_version"]
        assert adapter["builder_id"]
        assert adapter["action_contract_summary"]
        assert adapter["state_metadata"]
        assert adapter["replay_or_consistency_checked"]
        assert adapter["accepted_funnel"]
        assert adapter["rejected_funnel"]
        assert adapter["hdf5_export"] is True
        assert adapter["trainer_smoke_passed"] is True


def test_mvp1plus_summary_pass_gate_requires_export_trainer_and_rejection_coverage() -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    clean_adapter = {
        "hdf5_export_exists": True,
        "hdf5_inspection_clean": True,
        "trainer_smoke_passed": True,
    }
    clean_integrated = {
        "hdf5_export_exists": True,
        "hdf5_inspection_clean": True,
        "trainer_smoke_passed": True,
    }

    assert proof._summary_passed(
        issues=[],
        integrated_export=clean_integrated,
        adapter_summaries=[clean_adapter],
        rejection_reason_coverage_passed=True,
    )
    assert not proof._summary_passed(
        issues=[],
        integrated_export={**clean_integrated, "hdf5_inspection_clean": False},
        adapter_summaries=[clean_adapter],
        rejection_reason_coverage_passed=True,
    )
    assert not proof._summary_passed(
        issues=[],
        integrated_export=clean_integrated,
        adapter_summaries=[{**clean_adapter, "trainer_smoke_passed": False}],
        rejection_reason_coverage_passed=True,
    )
    assert not proof._summary_passed(
        issues=[],
        integrated_export=clean_integrated,
        adapter_summaries=[clean_adapter],
        rejection_reason_coverage_passed=False,
    )


def test_mvp1plus_missing_or_malformed_source_evidence_reports_structured_issue(
    tmp_path: Path,
) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    profile = RobotEmbodimentAdapterRegistry.get("franka_research_arm")
    adapter = RobotEmbodimentAdapterRegistry.create(profile.adapter_id)

    missing = adapter.project_source_evidence(
        source_dir=tmp_path / "missing_source",
        output_dir=tmp_path / "projected_missing",
    )
    assert missing.passed is False
    assert any("missing source evidence" in issue for issue in missing.issues)

    malformed_dir = tmp_path / "malformed_source"
    malformed_dir.mkdir()
    (malformed_dir / "metadata.json").write_text("{", encoding="utf-8")
    (malformed_dir / "accepted_command_state.jsonl").write_text("{}\n", encoding="utf-8")
    (malformed_dir / "rejected_command_state.jsonl").write_text("{}\n", encoding="utf-8")
    malformed = adapter.project_source_evidence(
        source_dir=malformed_dir,
        output_dir=tmp_path / "projected_malformed",
    )
    assert malformed.passed is False
    assert any("invalid metadata json" in issue for issue in malformed.issues)

    invalid_dir = tmp_path / "invalid_rows"
    proof._write_source_logs(profile, invalid_dir)
    (invalid_dir / "accepted_command_state.jsonl").write_text("{}\n", encoding="utf-8")
    (invalid_dir / "rejected_command_state.jsonl").write_text("{}\n", encoding="utf-8")
    invalid = adapter.project_source_evidence(
        source_dir=invalid_dir,
        output_dir=tmp_path / "projected_invalid",
    )
    assert invalid.passed is False
    assert "accepted jsonl row 1 command.vector missing" in invalid.issues
    assert "rejected jsonl row 1 quality.rejection_reason mismatch" in invalid.issues


def test_mvp1plus_overclaiming_source_metadata_is_rejected(tmp_path: Path) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    profile = RobotEmbodimentAdapterRegistry.get("franka_research_arm")
    adapter = RobotEmbodimentAdapterRegistry.create(profile.adapter_id)
    source_dir = tmp_path / "overclaiming_source"
    proof._write_source_logs(profile, source_dir)
    metadata_path = source_dir / "metadata.json"
    metadata = read_json(metadata_path)
    metadata["claim_boundary"]["policy_uplift_claimed"] = True
    metadata["source_provenance"]["recorded_log_backed"] = False
    metadata["source_provenance"]["live_runtime_support_claimed"] = True
    metadata["public_sample_evidence_claimed"] = True
    metadata["adapter_version"] = "unexpected_version"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    result = adapter.project_source_evidence(
        source_dir=source_dir,
        output_dir=tmp_path / "projected_overclaim",
    )

    assert result.passed is False
    assert "metadata.adapter_version mismatch" in result.issues
    assert "metadata.claim_boundary mismatch" in result.issues
    assert "metadata.claim_boundary.policy_uplift_claimed must be false" in result.issues
    assert "metadata.source_provenance.recorded_log_backed not true" in result.issues
    assert "metadata.source_provenance.live_runtime_support_claimed must be false" in result.issues
    assert "metadata.public_sample_evidence_claimed not false" in result.issues


def test_mvp1plus_emit_contract_rejects_preprojected_adapter_mismatch(
    tmp_path: Path,
) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    profile = RobotEmbodimentAdapterRegistry.get("franka_research_arm")
    adapter = RobotEmbodimentAdapterRegistry.create(profile.adapter_id)
    source_dir = tmp_path / "source"
    projected_dir = tmp_path / "projected"
    proof._write_source_logs(profile, source_dir)
    projection = adapter.project_source_evidence(source_dir=source_dir, output_dir=projected_dir)
    assert projection.passed is True
    projected_inputs = dict(projection.projected_inputs)
    projected_inputs["metadata"] = {**projected_inputs["metadata"], "adapter_id": "wrong_adapter"}

    result = adapter.emit_contract(
        source_dir=source_dir,
        projected_inputs=projected_inputs,
        export_artifacts={
            "hdf5_export": tmp_path / "missing.hdf5",
            "trainer_smoke_report": tmp_path / "missing_trainer.json",
        },
    )

    assert result.passed is False
    assert "projected_inputs.metadata.adapter_id mismatch" in result.issues


def test_mvp1plus_emit_contract_requires_preprojected_inputs(tmp_path: Path) -> None:
    profile = RobotEmbodimentAdapterRegistry.get("franka_research_arm")
    adapter = RobotEmbodimentAdapterRegistry.create(profile.adapter_id)

    result = adapter.emit_contract(
        source_dir=tmp_path / "source",
        projected_dir=tmp_path / "projected",
        export_artifacts={
            "hdf5_export": tmp_path / "missing.hdf5",
            "trainer_smoke_report": tmp_path / "missing_trainer.json",
        },
    )

    assert result.passed is False
    assert "preprojected inputs required for contract emission" in result.issues
    assert result.projected_inputs == {}


def test_mvp1plus_default_registry_adapter_emits_mvp1plus_contract_identity(
    tmp_path: Path,
) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    profile = RobotEmbodimentAdapterRegistry.get("franka_research_arm")
    adapter = RobotEmbodimentAdapterRegistry.create(profile.adapter_id)
    source_dir = tmp_path / "source"
    projected_dir = tmp_path / "projected"
    proof._write_source_logs(profile, source_dir)
    projection = adapter.project_source_evidence(source_dir=source_dir, output_dir=projected_dir)
    assert projection.passed is True
    export = proof._run_export_and_trainer_smoke(
        projected_inputs=projection.projected_inputs,
        hdf5_dir=tmp_path / "hdf5",
        adapter_id=profile.adapter_id,
    )

    result = adapter.emit_contract(
        source_dir=source_dir,
        projected_dir=projected_dir,
        projected_inputs=projection.projected_inputs,
        export_artifacts={
            "hdf5_export": export["hdf5_export"],
            "trainer_smoke_report": export["trainer_smoke_report"],
        },
    )

    assert result.passed is True
    assert result.contract["proof_id"] == EXPECTED_PROOF_ID
    assert result.contract["contract_name"] == EXPECTED_CONTRACT_NAME
    assert result.proof["adapter_call"]["uses_preprojected_inputs"] is True


def test_mvp1plus_emit_contract_rejects_cross_adapter_evaluation_mix(
    tmp_path: Path,
) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    franka_profile = RobotEmbodimentAdapterRegistry.get("franka_research_arm")
    robotis_profile = RobotEmbodimentAdapterRegistry.get("robotis_sh5_ros2_dds")
    franka_adapter = RobotEmbodimentAdapterRegistry.create(franka_profile.adapter_id)
    robotis_adapter = RobotEmbodimentAdapterRegistry.create(robotis_profile.adapter_id)

    franka_source = tmp_path / "source" / franka_profile.adapter_id
    robotis_source = tmp_path / "source" / robotis_profile.adapter_id
    proof._write_source_logs(franka_profile, franka_source)
    proof._write_source_logs(robotis_profile, robotis_source)
    franka_projection = franka_adapter.project_source_evidence(
        source_dir=franka_source,
        output_dir=tmp_path / "projected" / franka_profile.adapter_id,
    )
    robotis_projection = robotis_adapter.project_source_evidence(
        source_dir=robotis_source,
        output_dir=tmp_path / "projected" / robotis_profile.adapter_id,
    )
    assert franka_projection.passed is True
    assert robotis_projection.passed is True
    export = proof._run_export_and_trainer_smoke(
        projected_inputs=franka_projection.projected_inputs,
        hdf5_dir=tmp_path / "hdf5",
        adapter_id=franka_profile.adapter_id,
    )
    mixed_projected_inputs = dict(franka_projection.projected_inputs)
    mixed_projected_inputs["accepted_evaluation"] = robotis_projection.projected_inputs["accepted_evaluation"]

    result = franka_adapter.emit_contract(
        source_dir=franka_source,
        projected_inputs=mixed_projected_inputs,
        export_artifacts={
            "hdf5_export": export["hdf5_export"],
            "trainer_smoke_report": export["trainer_smoke_report"],
        },
    )

    assert result.passed is False
    assert "projected_inputs.accepted_evaluation.trajectory_id mismatch" in result.issues
    assert "projected_inputs.accepted_evaluation.episode_id mismatch" in result.issues


def test_mvp1plus_projection_labels_legacy_xr_exporter_placeholders(tmp_path: Path) -> None:
    build_proof(tmp_path / "mvp1plus")

    projection = read_json(tmp_path / "mvp1plus" / "projected_inputs" / "franka_research_arm" / "projection_manifest.json")
    trajectory = read_json(Path(projection["accepted"]["trajectory"]))
    placeholders = trajectory["frames"][0]["metadata"]["exporter_compatibility_placeholders"]

    assert placeholders == {
        "raw_xr_right_wrist_pose": "zero_pose_exporter_compatibility_only",
        "aligned_xr_right_wrist_pose": "zero_pose_exporter_compatibility_only",
        "hmd_readiness_evidence": False,
    }


def test_mvp1plus_clean_refuses_unsafe_output_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")

    for output_dir in (ROOT, ROOT / "storage", Path(tempfile.gettempdir())):
        with pytest.raises(ValueError, match="refusing to clean unsafe output_dir"):
            proof.build_mvp1plus_embodiment_proof(output_dir, clean=True)
    monkeypatch.setenv("TMPDIR", str(ROOT))
    monkeypatch.setattr(proof.tempfile, "tempdir", None)
    with pytest.raises(ValueError, match="refusing to clean unsafe output_dir"):
        proof.build_mvp1plus_embodiment_proof(ROOT / "apps", clean=True)


def test_mvp1plus_no_clean_run_removes_stale_integrated_export_inputs(tmp_path: Path) -> None:
    proof = load_script("run_mvp1plus_embodiment_proof")
    output_dir = tmp_path / "mvp1plus"
    proof.build_mvp1plus_embodiment_proof(output_dir, clean=True)
    integrated_dir = output_dir / "projected_inputs" / "integrated"
    source_trajectory = next((integrated_dir / "trajectories").glob("*.json"))
    adapter_projected_dir = output_dir / "projected_inputs" / "franka_research_arm"
    adapter_source_trajectory = next((adapter_projected_dir / "trajectories").glob("*.json"))
    stale_trajectory = read_json(source_trajectory)
    stale_trajectory["id"] = "stale_extra_trajectory"
    stale_trajectory["episode_id"] = "stale_extra_episode"
    stale_path = integrated_dir / "trajectories" / "stale_extra_trajectory.json"
    stale_path.write_text(json.dumps(stale_trajectory), encoding="utf-8")
    adapter_stale = read_json(adapter_source_trajectory)
    adapter_stale["id"] = "stale_adapter_trajectory"
    adapter_stale["episode_id"] = "stale_adapter_episode"
    adapter_stale_path = adapter_projected_dir / "trajectories" / "stale_adapter_trajectory.json"
    adapter_stale_path.write_text(json.dumps(adapter_stale), encoding="utf-8")

    report = proof.build_mvp1plus_embodiment_proof(output_dir, clean=False)
    inspection = read_json(output_dir / "hdf5" / "mvp1plus_cross_embodiment.inspection.json")
    adapter_inspection = read_json(output_dir / "hdf5" / "franka_research_arm.inspection.json")

    assert report["passed"] is True
    assert not stale_path.exists()
    assert not adapter_stale_path.exists()
    assert inspection["episode_count"] == 4
    assert adapter_inspection["episode_count"] == 1


def test_existing_mvp1_proof_script_still_passes_after_mvp1plus(tmp_path: Path) -> None:
    build_proof(tmp_path / "mvp1plus")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_data_trust_layer_proof.py"),
            "--output-dir",
            str(tmp_path / "mvp1"),
            "--clean",
            "--pretty",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(result.stdout)
    assert report["passed"] is True
