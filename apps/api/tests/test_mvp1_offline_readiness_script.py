from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "run_mvp1_offline_readiness.py"
SPEC = importlib.util.spec_from_file_location("run_mvp1_offline_readiness", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
readiness = importlib.util.module_from_spec(SPEC)
sys.modules["run_mvp1_offline_readiness"] = readiness
SPEC.loader.exec_module(readiness)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mvp1_offline_readiness_bundle_generates_required_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"

    report = readiness.build_bundle(output_dir, clean=True)

    assert report["passed"] is True
    assert report["raw_episode_count"] == 8
    assert report["accepted_count"] == 4
    assert report["rejected_count"] == 4
    assert set(readiness.PHASE_SEQUENCE).issubset(set(report["phase_coverage"]))
    assert report["evaluator_failure_reason_distribution"] == {
        "ALIGNMENT_ERROR": 1,
        "INSUFFICIENT_INSERTION_DEPTH": 1,
        "TRACKING_LOSS": 1,
    }
    assert report["hdf5_inspection_issue_count"] == 0

    for artifact_path in report["artifact_paths"].values():
        assert Path(artifact_path).exists()

    curation = read_json(output_dir / "curation_manifest.json")
    assert curation["accepted_count"] == 4
    assert curation["rejected_count"] == 4
    assert "DUPLICATE_TRAJECTORY" in curation["rejection_reason_distribution"]
    assert "EVALUATION_FAILED" in curation["rejection_reason_distribution"]

    split_manifest = read_json(output_dir / "split_manifest.json")
    assert split_manifest["splits"]["train"]
    assert split_manifest["splits"]["validation"]
    assert split_manifest["splits"]["test"]

    dataset_card = read_json(output_dir / "dataset_card.json")
    assert dataset_card["num_accepted"] == 4
    assert dataset_card["num_rejected"] == 4
    assert dataset_card["task_type"] == "peg_in_hole"
    assert dataset_card["robot"] == "franka"


def test_mvp1_readiness_manifest_does_not_invent_learning_uplift(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"

    report = readiness.build_bundle(output_dir, clean=True)
    experiment = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")

    assert report["learning_results_measured"] is False
    assert report["readiness_gates"]["no_fake_learning_uplift"] is True
    assert experiment["learning_results_measured"] is False
    assert experiment["curated_vs_uncurated_uplift"] is None
    assert experiment["baseline_a_uncurated_success_lifecycle_episode_ids"]
    assert experiment["baseline_b_curated_accepted_episode_ids"]
    assert "Run real policy A/B evaluation before reporting any learning uplift." in report["next_actions"]


def test_mvp1_readiness_trajectories_preserve_mvp1_data_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"

    readiness.build_bundle(output_dir, clean=True)
    trajectory_path = output_dir / "raw" / "trajectories" / "traj_success_a.json"
    trajectory = read_json(trajectory_path)
    first_frame = trajectory["frames"][0]

    assert trajectory["source"] == readiness.SOURCE
    assert first_frame["metadata"]["task_state"]["peg_tip_distance_to_target"] is not None
    assert first_frame["metadata"]["action_phase"] == "APPROACH"
    assert first_frame["metadata"]["raw_xr"]["right_wrist_pose"]
    assert first_frame["metadata"]["aligned_xr"]["right_wrist_pose"]
    assert first_frame["action"]["retargeted_robot_action"]["command"]
    assert first_frame["action"]["teleop_intent"]["role"] == "operator_intent"
    assert first_frame["action"]["executed_control"]["role"] == "robot_control_command"
    assert first_frame["action"]["learning_action"]["validation_state"] == "requires_evaluation_and_curation"
    assert first_frame["metadata"]["teleop_pipeline"]["product_role"] == "xr_teleop_trajectory_to_validated_learning_dataset"
    assert trajectory["summary"]["sync_metrics"]["quality_score"] >= 0.7
    assert trajectory["summary"]["data_usability"]["usable"] is True
    assert trajectory["summary"]["action_segments"][0]["phase"] == "APPROACH"
