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
trainer_smoke = load_script("run_mvp1_trainer_smoke")
proof = load_script("run_mvp1_proof_audit")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_mvp1_trainer_smoke_loads_export_and_updates_manifest(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    readiness_report = readiness.build_bundle(output_dir, clean=True)
    assert readiness_report["passed"] is True

    report = trainer_smoke.run_trainer_smoke(
        hdf5_path=output_dir / "rdf_mvp1_curated_readiness.hdf5",
        split_manifest_path=output_dir / "split_manifest.json",
        output_path=output_dir / "trainer_smoke_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    assert report["passed"] is True
    assert report["loader_smoke_passed"] is True
    assert report["trainer_dry_run_passed"] is True
    assert report["one_epoch_smoke_passed"] is True
    assert report["learning_results_measured"] is False
    assert report["curated_vs_uncurated_uplift"] is None
    assert report["issues"] == []
    assert report["trainer"]["sample_count"] > 0
    assert report["trainer"]["observation_dim"] > 0
    assert report["trainer"]["action_dim"] == 7
    assert report["trainer"]["final_loss"] <= report["trainer"]["initial_loss"]

    manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    assert manifest["learning_results_measured"] is False
    assert manifest["curated_vs_uncurated_uplift"] is None
    assert manifest["training_readiness"]["loader_smoke_passed"] is True
    assert manifest["training_readiness"]["trainer_dry_run_passed"] is True
    assert manifest["training_readiness"]["one_epoch_smoke_passed"] is True
    assert manifest["training_readiness"]["policy_class"] == "linear_bc_numpy_smoke"
    assert manifest["training_readiness"]["trainer"] == "rdf_numpy_bc_trainer_smoke"


def test_mvp1_proof_audit_reports_mvp1b_after_live_evidence_and_trainer_smoke(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    readiness_report = readiness.build_bundle(output_dir, clean=True)
    assert readiness_report["passed"] is True

    trainer_smoke.run_trainer_smoke(
        hdf5_path=output_dir / "rdf_mvp1_curated_readiness.hdf5",
        split_manifest_path=output_dir / "split_manifest.json",
        output_path=output_dir / "trainer_smoke_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    live_trajectory = read_json(output_dir / "raw" / "trajectories" / "traj_success_a.json")
    live_trajectory["id"] = "traj_live_peg_success"
    live_trajectory["episode_id"] = "episode_live_peg_success"
    live_trajectory["source"]["task_name"] = "peg_in_hole_live_validation"
    live_trajectory["summary"]["task_state_source"] = "isaac_live_validation"
    live_trajectory["summary"]["fixture_source"] = None
    write_json(trajectory_dir / "traj_live_peg_success.json", live_trajectory)

    audit = proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
    )

    assert audit["status"] == "partial"
    assert audit["full_mvp1_proof_achieved"] is False
    assert audit["passed_required_gates"] == 7
    assert audit["required_gate_count"] == 11
    assert audit["staged_mvp1"]["current_stage"] == "offline_readiness"
    assert audit["staged_mvp1"]["next_stage"] == "MVP-1A"
    assert audit["staged_mvp1"]["stages"]["MVP-1A"]["passed"] is False
    assert audit["staged_mvp1"]["stages"]["MVP-1"]["passed"] is False
    missing = {item["name"] for item in audit["missing_required_gates"]}
    assert missing == {
        "task_outcome_recorded",
        "data_quality_recorded",
        "operator_success_separated_from_evaluator_task_success",
        "replay_action_gate_recorded",
    }
    assert audit["summary"]["trainer_dry_run_passed"] is True
    assert audit["summary"]["learning_ready"] is False
    assert audit["summary"]["learning_proven"] is False
