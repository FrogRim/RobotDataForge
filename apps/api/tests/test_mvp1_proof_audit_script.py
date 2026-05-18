from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


readiness = load_script("run_mvp1_offline_readiness")
proof = load_script("run_mvp1_proof_audit")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_readiness(output_dir: Path) -> None:
    report = readiness.build_bundle(output_dir, clean=True)
    assert report["passed"] is True


def audit(output_dir: Path, *, trajectory_dir: Path, learning_manifest: Path | None = None) -> dict:
    return proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=learning_manifest or output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
    )


def add_live_export_evidence(manifest: dict, live_export_dir: Path, trajectory: dict) -> dict:
    live_export_dir.mkdir(parents=True, exist_ok=True)
    hdf5_path = live_export_dir / "rdf_mvp1_live_export_smoke.hdf5"
    entry = {
        "trajectory_id": trajectory["id"],
        "episode_id": trajectory["episode_id"],
        "frame_count": len(trajectory["frames"]),
        "task_outcome": {
            "operator_success": False,
            "auto_success_ready": True,
            "success_label_source": "task_state_auto",
            "evaluator_task_success": True,
            "task_success_confidence": 0.9,
            "task_failure_reason": None,
        },
        "data_quality": {
            "action_contract_valid": True,
            "action_contract_status": "pass",
            "replay_verified": True,
            "retargeting_jump": "pass",
            "native_action_saturation": "pass",
            "sync_quality": "pass",
            "control_quality": "pass",
            "quality_failure_reasons": [],
        },
    }
    write_json(
        live_export_dir / "live_export_smoke_report.json",
        {
            "passed": True,
            "hdf5_path": str(hdf5_path),
            "curation_manifest": {
                "accepted_count": 1,
                "rejected_count": 0,
                "accepted": [entry],
                "rejected": [],
                "smoke_included": [entry],
            },
        },
    )
    training = manifest.setdefault("training_readiness", {})
    training.update(
        {
            "loader_smoke_passed": True,
            "trainer_dry_run_passed": True,
            "one_epoch_smoke_passed": True,
            "policy_class": training.get("policy_class") or "linear_bc_numpy_smoke",
            "trainer": training.get("trainer") or "rdf_numpy_bc_trainer_smoke",
            "evidence_source": "mvp1a_live_export_bundle",
            "hdf5_path": str(hdf5_path),
            "split_manifest_path": str(live_export_dir / "split_manifest.json"),
            "report_path": str(live_export_dir / "trainer_smoke_report.json"),
            "sample_count": len(trajectory["frames"]),
            "observation_dim": 20,
            "action_dim": 7,
            "live_trajectory_ids": [trajectory["id"]],
            "live_episode_ids": [trajectory["episode_id"]],
        }
    )
    return manifest


def test_mvp1_proof_audit_reports_partial_until_live_and_learning_evidence_exist(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)

    report = audit(output_dir, trajectory_dir=trajectory_dir)

    assert report["status"] == "partial"
    assert report["full_mvp1_proof_achieved"] is False
    assert report["passed_required_gates"] == 4
    assert report["required_gate_count"] == 11
    assert report["staged_mvp1"]["current_stage"] == "offline_readiness"
    assert report["staged_mvp1"]["next_stage"] == "MVP-1A"
    assert report["staged_mvp1"]["stages"]["MVP-1A"]["passed"] is False
    assert report["staged_mvp1"]["stages"]["MVP-1"]["passed"] is False
    missing = {item["name"] for item in report["missing_required_gates"]}
    assert missing == {
        "raw_xr_trajectory_saved",
        "task_state_extracted",
        "task_outcome_recorded",
        "data_quality_recorded",
        "operator_success_separated_from_evaluator_task_success",
        "replay_action_gate_recorded",
        "trainer_loader_smoke_passed",
    }
    assert report["summary"]["do_not_claim_full_mvp1"] is True
    assert report["policy_uplift_required_for_mvp1"] is False
    assert (output_dir / "proof_audit.json").exists()


def test_mvp1_proof_audit_passes_when_real_trajectory_and_measured_uplift_are_supplied(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)

    live_trajectory = read_json(output_dir / "raw" / "trajectories" / "traj_success_a.json")
    live_trajectory["id"] = "traj_live_peg_success"
    live_trajectory["episode_id"] = "episode_live_peg_success"
    live_trajectory["source"]["task_name"] = "peg_in_hole_live_validation"
    live_trajectory["summary"]["task_state_source"] = "isaac_live_validation"
    live_trajectory["summary"]["fixture_source"] = None
    write_json(trajectory_dir / "traj_live_peg_success.json", live_trajectory)

    measured_manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    measured_manifest["learning_results_measured"] = True
    measured_manifest["curated_vs_uncurated_uplift"] = 0.18
    measured_manifest["policy_uplift_measurement"] = {
        "report_path": str(tmp_path / "real_policy_report.json"),
        "proof_eligible": True,
        "evidence_tier": "heldout_policy_eval",
        "primary_metric": "policy_success_rate",
        "baseline_success_rate": 0.42,
        "candidate_success_rate": 0.60,
        "secondary_metrics": {
            "rollout_success_rate": {"baseline": 0.42, "candidate": 0.60, "delta": 0.18}
        },
    }
    measured_manifest["training_readiness"] = {
        "loader_smoke_passed": True,
        "trainer_dry_run_passed": True,
        "policy_class": "ACT",
        "trainer": "test_fixture_trainer",
    }
    measured_manifest = add_live_export_evidence(measured_manifest, tmp_path / "mvp1_live_export", live_trajectory)
    measured_path = tmp_path / "measured_learning_manifest.json"
    write_json(measured_path, measured_manifest)

    report = audit(output_dir, trajectory_dir=trajectory_dir, learning_manifest=measured_path)

    assert report["status"] == "pass"
    assert report["full_mvp1_proof_achieved"] is True
    assert report["mvp1_dataset_pipeline_proof_achieved"] is True
    assert report["learning_ready_dataset_artifact"] is True
    assert report["policy_uplift_required_for_mvp1"] is False
    assert report["learning_proven_policy_uplift_achieved"] is True
    assert report["required_gate_count"] == 11
    assert report["missing_required_gates"] == []
    assert report["staged_mvp1"]["current_stage"] == "MVP-1"
    assert report["staged_mvp1"]["next_stage"] == "MVP-2"
    assert report["staged_mvp1"]["stages"]["MVP-1A"]["passed"] is True
    assert report["staged_mvp1"]["stages"]["MVP-1"]["passed"] is True
    assert report["summary"]["live_insertion_evidence_count"] == 1
    assert report["summary"]["trainer_dry_run_passed"] is True
    assert report["summary"]["learning_ready"] is True
    assert report["summary"]["learning_proven"] is True


def test_mvp1_proof_audit_rejects_offline_proxy_uplift_as_full_mvp1c(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)

    live_trajectory = read_json(output_dir / "raw" / "trajectories" / "traj_success_a.json")
    live_trajectory["id"] = "traj_live_peg_success"
    live_trajectory["episode_id"] = "episode_live_peg_success"
    live_trajectory["source"]["task_name"] = "peg_in_hole_live_validation"
    live_trajectory["summary"]["task_state_source"] = "isaac_live_validation"
    live_trajectory["summary"]["fixture_source"] = None
    write_json(trajectory_dir / "traj_live_peg_success.json", live_trajectory)

    proxy_manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    proxy_manifest["learning_results_measured"] = True
    proxy_manifest["curated_vs_uncurated_uplift"] = 0.18
    proxy_manifest["policy_uplift_measurement"] = {
        "report_path": str(tmp_path / "offline_proxy_report.json"),
        "proof_eligible": False,
        "evidence_tier": "offline_proxy_smoke",
        "primary_metric": "action_prediction_score",
        "baseline_test_score": 0.80,
        "candidate_test_score": 0.98,
    }
    proxy_manifest["training_readiness"] = {
        "loader_smoke_passed": True,
        "trainer_dry_run_passed": True,
        "policy_class": "linear_bc_numpy_smoke",
        "trainer": "test_fixture_trainer",
    }
    proxy_path = tmp_path / "proxy_learning_manifest.json"
    write_json(proxy_path, proxy_manifest)

    report = audit(output_dir, trajectory_dir=trajectory_dir, learning_manifest=proxy_path)

    assert report["status"] == "partial"
    assert report["full_mvp1_proof_achieved"] is False
    assert report["staged_mvp1"]["current_stage"] == "offline_readiness"
    assert report["staged_mvp1"]["next_stage"] == "MVP-1A"
    missing = {item["name"] for item in report["missing_required_gates"]}
    assert "policy_claim_integrity_preserved" in missing
    integrity_gate = next(item for item in report["gates"] if item["name"] == "policy_claim_integrity_preserved")
    assert integrity_gate["passed"] is False
    uplift_gate = next(item for item in report["gates"] if item["name"] == "curated_vs_uncurated_policy_uplift_measured")
    assert uplift_gate["evidence"]["evidence_tier"] == "offline_proxy_smoke"
    assert uplift_gate["evidence"]["proof_eligible"] is False
    assert uplift_gate["required_for_full_proof"] is False


def test_mvp1_proof_audit_reports_mvp1a_when_only_real_insertion_evidence_exists(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)

    live_trajectory = read_json(output_dir / "raw" / "trajectories" / "traj_success_a.json")
    live_trajectory["id"] = "traj_live_peg_success"
    live_trajectory["episode_id"] = "episode_live_peg_success"
    live_trajectory["source"]["task_name"] = "peg_in_hole_live_validation"
    live_trajectory["summary"]["task_state_source"] = "isaac_live_validation"
    live_trajectory["summary"]["fixture_source"] = None
    write_json(trajectory_dir / "traj_live_peg_success.json", live_trajectory)

    report = audit(output_dir, trajectory_dir=trajectory_dir)

    assert report["status"] == "partial"
    assert report["staged_mvp1"]["current_stage"] == "offline_readiness"
    assert report["staged_mvp1"]["next_stage"] == "MVP-1A"
    assert report["staged_mvp1"]["stages"]["MVP-1A"]["passed"] is False
    assert report["staged_mvp1"]["stages"]["MVP-1"]["passed"] is False
    missing = {item["name"] for item in report["missing_required_gates"]}
    assert missing == {
        "task_outcome_recorded",
        "data_quality_recorded",
        "operator_success_separated_from_evaluator_task_success",
        "replay_action_gate_recorded",
        "trainer_loader_smoke_passed",
    }


def test_mvp1_proof_audit_rejects_synthetic_readiness_trajectory_as_live_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "mvp1_readiness" / "raw" / "trajectories"
    build_readiness(output_dir)

    report = audit(output_dir, trajectory_dir=trajectory_dir)

    live_gate = next(item for item in report["gates"] if item["name"] == "raw_xr_trajectory_saved")
    assert live_gate["passed"] is False
    assert live_gate["evidence"]["candidate_count"] == 0
