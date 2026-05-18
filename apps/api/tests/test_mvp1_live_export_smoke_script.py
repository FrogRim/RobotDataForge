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
live_export = load_script("run_mvp1_live_export_smoke")
proof = load_script("run_mvp1_proof_audit")
live_replay_gate = load_script("apply_live_replay_gate")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def make_live_fixture(
    readiness_dir: Path,
    trajectory_dir: Path,
    evaluations_dir: Path,
    *,
    episode_status: str = "failure",
    finalize_reason: str = "operator_failure",
    evaluation_success: bool = False,
    failure_reason: str = "TEST_FIXTURE_FAILURE",
) -> dict:
    trajectory = read_json(readiness_dir / "raw" / "trajectories" / "traj_success_a.json")
    trajectory["id"] = "traj_live_export_success"
    trajectory["episode_id"] = "episode_live_export_success"
    trajectory["source"]["task_name"] = "Isaac-Forge-PegInsert-Direct-v0"
    trajectory["summary"]["task_state_source"] = "isaac_live_validation"
    trajectory["summary"]["fixture_source"] = None
    trajectory["summary"]["episode_status"] = episode_status
    trajectory["summary"]["episode_finalize_reason"] = finalize_reason
    write_json(trajectory_dir / "traj_live_export_success.json", trajectory)

    evaluation = read_json(readiness_dir / "raw" / "evaluations" / "eval_success_a.json")
    evaluation["id"] = "eval_live_export_success"
    evaluation["trajectory_id"] = trajectory["id"]
    evaluation["episode_id"] = trajectory["episode_id"]
    evaluation["success"] = evaluation_success
    evaluation["failure_reason"] = failure_reason
    evaluation["failure_category"] = live_export.failure_category_for_reason(failure_reason)
    write_json(evaluations_dir / "eval_live_export_success.json", evaluation)
    return trajectory


def test_mvp1_live_export_smoke_exports_live_candidate_and_updates_proof_manifest(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    evaluations_dir = tmp_path / "real_evaluations"
    output_dir = tmp_path / "mvp1_live_export"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    live_trajectory = make_live_fixture(readiness_dir, trajectory_dir, evaluations_dir)

    report = live_export.build_live_export_smoke(
        output_dir=output_dir,
        trajectory_dir=trajectory_dir,
        evaluations_dir=evaluations_dir,
        trajectory_id=live_trajectory["id"],
        clean=True,
        proof_learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    assert report["passed"] is True
    assert report["selected_trajectories"][0]["trajectory_id"] == live_trajectory["id"]
    assert report["export"]["exported_episode_ids"] == [live_trajectory["episode_id"]]
    assert report["hdf5"]["issues"] == []
    assert report["trainer_smoke"]["loader_smoke_passed"] is True
    assert report["trainer_smoke"]["trainer_dry_run_passed"] is True
    assert report["trainer_smoke"]["one_epoch_smoke_passed"] is True
    assert report["trainer_smoke"]["learning_results_measured"] is False
    assert report["trainer_smoke"]["curated_vs_uncurated_uplift"] is None
    assert report["trainer_smoke"]["sample_count"] == len(live_trajectory["frames"])
    assert report["curation_manifest"]["smoke_included_count"] == 1
    assert report["curation_manifest"]["accepted_count"] == 0
    assert report["curation_manifest"]["rejected_count"] == 1
    assert report["curation_manifest"]["rejected"][0]["curated_dataset_status"] == "rejected"
    assert report["curation_manifest"]["rejected"][0]["evaluation_failure_reason"] == "TEST_FIXTURE_FAILURE"
    assert report["curation_manifest"]["rejected"][0]["evaluation_failure_category"] == "UNKNOWN"
    assert report["curation_manifest"]["rejected"][0]["task_outcome"]["operator_success"] is False
    assert report["curation_manifest"]["rejected"][0]["task_outcome"]["evaluator_task_success"] == "unknown"
    assert report["curation_manifest"]["rejected"][0]["curation"]["raw_saved"] is True
    assert report["curation_manifest"]["rejected"][0]["curation"]["human_success_pool"] is False
    assert report["curation_manifest"]["rejected"][0]["curation"]["training_eligible"] is False
    assert report["curation_manifest"]["rejected"][0]["curation"]["curated_accepted"] is False
    assert report["curation_manifest"]["rejected"][0]["curation"]["proof_eligible"] is False
    assert "REPLAY_NOT_VERIFIED" in report["curation_manifest"]["rejected"][0]["rejection_reasons"]
    assert "EVALUATION_FAILED" in report["curation_manifest"]["rejected"][0]["rejection_reasons"]
    assert "TEST_FIXTURE_FAILURE" in report["curation_manifest"]["rejected"][0]["rejection_reasons"]
    assert (output_dir / "rdf_mvp1_live_export_smoke.hdf5").exists()
    assert (output_dir / "trainer_smoke_report.json").exists()

    proof_manifest = read_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json")
    training = proof_manifest["training_readiness"]
    assert training["evidence_source"] == "mvp1a_live_export_bundle"
    assert training["live_trajectory_ids"] == [live_trajectory["id"]]
    assert training["live_episode_ids"] == [live_trajectory["episode_id"]]
    assert training["hdf5_path"] == str(output_dir / "rdf_mvp1_live_export_smoke.hdf5")
    assert proof_manifest["learning_results_measured"] is False
    assert proof_manifest["curated_vs_uncurated_uplift"] is None


def test_live_export_semantics_keeps_operator_success_but_blocks_training_on_quality_failure(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    evaluations_dir = tmp_path / "real_evaluations"
    output_dir = tmp_path / "mvp1_live_export"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    live_trajectory = make_live_fixture(
        readiness_dir,
        trajectory_dir,
        evaluations_dir,
        episode_status="success",
        finalize_reason="operator_success",
        evaluation_success=False,
        failure_reason="RETARGETING_JUMP",
    )

    report = live_export.build_live_export_smoke(
        output_dir=output_dir,
        trajectory_dir=trajectory_dir,
        evaluations_dir=evaluations_dir,
        trajectory_id=live_trajectory["id"],
        clean=True,
        proof_learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    rejected = report["curation_manifest"]["rejected"][0]
    assert rejected["task_outcome"]["operator_success"] is True
    assert rejected["task_outcome"]["evaluator_task_success"] == "unknown"
    assert rejected["evaluation_failure_category"] == "DATA_QUALITY_FAILURE"
    assert rejected["data_quality"]["retargeting_jump"] == "fail"
    assert rejected["curation"]["raw_saved"] is True
    assert rejected["curation"]["human_success_pool"] is True
    assert rejected["curation"]["training_eligible"] is False
    assert rejected["curation"]["curated_accepted"] is False
    assert rejected["curation"]["proof_eligible"] is False
    assert "RETARGETING_JUMP" in rejected["curation"]["rejection_reasons"]
    assert "REPLAY_NOT_VERIFIED" in rejected["curation"]["rejection_reasons"]


def test_apply_live_replay_gate_promotes_live_export_candidate(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    evaluations_dir = tmp_path / "real_evaluations"
    output_dir = tmp_path / "mvp1_live_export"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    live_trajectory = make_live_fixture(
        readiness_dir,
        trajectory_dir,
        evaluations_dir,
        episode_status="success",
        finalize_reason="auto_success_ready",
        evaluation_success=True,
        failure_reason=None,
    )
    for frame in live_trajectory["frames"]:
        frame.setdefault("action", {})["action_contract_version"] = "rdf_action_contract_v0.2.0"
    write_json(trajectory_dir / "traj_live_export_success.json", live_trajectory)
    report_path = tmp_path / "replay_report.json"
    write_json(
        report_path,
        {
            "checks": {
                "accepted_replays": [
                    {
                        "trajectory_id": live_trajectory["id"],
                        "episode_id": live_trajectory["episode_id"],
                        "mode": "native_direct",
                        "action_field": "retargeted_robot_action",
                        "requested_success_evaluator": "auto",
                        "selected_success_evaluator": "rdf_peg_in_hole",
                        "passed": True,
                        "success_step": 12,
                        "frame_count": len(live_trajectory["frames"]),
                        "missing_action_count": 0,
                    }
                ]
            }
        },
    )

    gate = live_replay_gate.apply_live_replay_gate(
        replay_report_path=report_path,
        trajectory_path=trajectory_dir / "traj_live_export_success.json",
        sqlite_db=None,
    )
    assert gate["passed"] is True
    stored_trajectory = read_json(trajectory_dir / "traj_live_export_success.json")
    assert stored_trajectory["summary"]["action_replay_gate"]["passed"] is True

    report = live_export.build_live_export_smoke(
        output_dir=output_dir,
        trajectory_dir=trajectory_dir,
        evaluations_dir=evaluations_dir,
        trajectory_id=live_trajectory["id"],
        clean=True,
        proof_learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    assert report["curation_manifest"]["accepted_count"] == 1
    assert report["curation_manifest"]["rejected_count"] == 0
    accepted = report["curation_manifest"]["accepted"][0]
    assert accepted["curated_dataset_status"] == "accepted_candidate"
    assert accepted["data_quality"]["replay_verified"] is True
    assert accepted["curation"]["training_eligible"] is True
    assert accepted["curation"]["proof_eligible"] is True


def test_mvp1_proof_audit_shows_live_export_trainer_evidence(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    evaluations_dir = tmp_path / "real_evaluations"
    output_dir = tmp_path / "mvp1_live_export"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    live_trajectory = make_live_fixture(readiness_dir, trajectory_dir, evaluations_dir)

    live_export.build_live_export_smoke(
        output_dir=output_dir,
        trajectory_dir=trajectory_dir,
        evaluations_dir=evaluations_dir,
        trajectory_id=live_trajectory["id"],
        clean=True,
        proof_learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    audit = proof.build_audit(
        readiness_report_path=readiness_dir / "readiness_report.json",
        curation_manifest_path=readiness_dir / "curation_manifest.json",
        split_manifest_path=readiness_dir / "split_manifest.json",
        dataset_card_path=readiness_dir / "dataset_card.json",
        hdf5_inspection_path=readiness_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=readiness_dir / "proof_audit.json",
    )

    assert audit["status"] == "pass"
    assert audit["full_mvp1_proof_achieved"] is True
    assert audit["staged_mvp1"]["current_stage"] == "MVP-1"
    assert audit["staged_mvp1"]["next_stage"] == "MVP-2"
    assert audit["passed_required_gates"] == 11
    trainer_gate = next(item for item in audit["gates"] if item["name"] == "trainer_loader_smoke_passed")
    assert trainer_gate["passed"] is True
    assert trainer_gate["evidence"]["evidence_source"] == "mvp1a_live_export_bundle"
    assert trainer_gate["evidence"]["hdf5_path"] == str(output_dir / "rdf_mvp1_live_export_smoke.hdf5")
    assert trainer_gate["evidence"]["live_trajectory_ids"] == [live_trajectory["id"]]
    assert trainer_gate["evidence"]["sample_count"] == len(live_trajectory["frames"])
    assert audit["missing_required_gates"] == []
    assert audit["summary"]["learning_ready"] is True
    assert audit["summary"]["learning_proven"] is False
