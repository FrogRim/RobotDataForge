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
trainer = load_script("run_mvp1_trainer_smoke")
real_eval = load_script("run_mvp1c_real_policy_eval")
proof = load_script("run_mvp1_proof_audit")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def prepare_mvp1b_fixture(output_dir: Path, trajectory_dir: Path) -> None:
    assert readiness.build_bundle(output_dir, clean=True)["passed"] is True
    trainer_report = trainer.run_trainer_smoke(
        hdf5_path=output_dir / "rdf_mvp1_curated_readiness.hdf5",
        split_manifest_path=output_dir / "split_manifest.json",
        output_path=output_dir / "trainer_smoke_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
    )
    assert trainer_report["passed"] is True

    live_trajectory = read_json(output_dir / "raw" / "trajectories" / "traj_success_a.json")
    live_trajectory["id"] = "traj_live_peg_success"
    live_trajectory["episode_id"] = "episode_live_peg_success"
    live_trajectory["source"]["task_name"] = "peg_in_hole_live_validation"
    live_trajectory["summary"]["task_state_source"] = "isaac_live_validation"
    live_trajectory["summary"]["fixture_source"] = None
    write_json(trajectory_dir / "traj_live_peg_success.json", live_trajectory)

    live_export_dir = output_dir.parent / "mvp1_live_export"
    live_export_dir.mkdir(parents=True, exist_ok=True)
    hdf5_path = live_export_dir / "rdf_mvp1_live_export_smoke.hdf5"
    entry = {
        "trajectory_id": live_trajectory["id"],
        "episode_id": live_trajectory["episode_id"],
        "frame_count": len(live_trajectory["frames"]),
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
    manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    manifest.setdefault("training_readiness", {}).update(
        {
            "loader_smoke_passed": True,
            "trainer_dry_run_passed": True,
            "one_epoch_smoke_passed": True,
            "evidence_source": "mvp1a_live_export_bundle",
            "hdf5_path": str(hdf5_path),
            "split_manifest_path": str(live_export_dir / "split_manifest.json"),
            "report_path": str(live_export_dir / "trainer_smoke_report.json"),
            "sample_count": len(live_trajectory["frames"]),
            "observation_dim": 20,
            "action_dim": 7,
            "live_trajectory_ids": [live_trajectory["id"]],
            "live_episode_ids": [live_trajectory["episode_id"]],
        }
    )
    write_json(output_dir / "curated_vs_uncurated_experiment_manifest.json", manifest)


def policy_eval_payload(*, baseline_successes: list[bool], candidate_successes: list[bool]) -> dict:
    return {
        "schema_version": "rdf_mvp1c_policy_eval_input_v0.1.0",
        "evidence_tier": "heldout_policy_eval",
        "primary_metric": "policy_success_rate",
        "task_type": "peg_in_hole",
        "eval_suite": {
            "id": "peg_insert_heldout_fixture",
            "held_out": True,
            "split": "held_out_pose_clearance",
            "task_type": "peg_in_hole",
        },
        "baseline": {
            "name": "uncurated_success_lifecycle_policy",
            "policy_id": "policy_uncurated_fixture",
            "dataset_view": "uncurated_success_lifecycle",
            "dataset_id": "ds_uncurated_fixture",
            "policy_class": "ACT",
            "trainer": "fixture_real_trainer",
            "rollout_results": [
                {"rollout_id": f"baseline_{index}", "scenario_id": f"scenario_{index}", "success": success}
                for index, success in enumerate(baseline_successes)
            ],
        },
        "candidate": {
            "name": "curated_accepted_policy",
            "policy_id": "policy_curated_fixture",
            "dataset_view": "curated_accepted",
            "dataset_id": "ds_curated_fixture",
            "policy_class": "ACT",
            "trainer": "fixture_real_trainer",
            "rollout_results": [
                {"rollout_id": f"candidate_{index}", "scenario_id": f"scenario_{index}", "success": success}
                for index, success in enumerate(candidate_successes)
            ],
        },
    }


def audit(output_dir: Path, trajectory_dir: Path) -> dict:
    return proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
    )


def test_real_policy_eval_positive_uplift_updates_manifest_and_passes_mvp1c(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    prepare_mvp1b_fixture(output_dir, trajectory_dir)
    input_path = tmp_path / "real_policy_eval_positive.json"
    write_json(
        input_path,
        policy_eval_payload(
            baseline_successes=[True, False, False, True, False],
            candidate_successes=[True, True, True, True, False],
        ),
    )

    report = real_eval.run_real_policy_eval(
        input_path=input_path,
        output_path=output_dir / "policy_uplift_real_eval_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        min_rollouts_per_policy=5,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["proof_eligible"] is True
    assert report["baseline_success_rate"] == 0.4
    assert report["candidate_success_rate"] == 0.8
    assert report["curated_vs_uncurated_uplift"] == 0.4

    manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    assert manifest["learning_results_measured"] is True
    assert manifest["curated_vs_uncurated_uplift"] == 0.4
    assert manifest["policy_uplift_measurement"]["evidence_tier"] == "heldout_policy_eval"
    assert manifest["policy_uplift_measurement"]["primary_metric"] == "policy_success_rate"
    assert "rollout_success_rate" in manifest["policy_uplift_measurement"]["secondary_metrics"]

    audit_report = audit(output_dir, trajectory_dir)
    assert audit_report["status"] == "pass"
    assert audit_report["staged_mvp1"]["current_stage"] == "MVP-1"
    assert audit_report["full_mvp1_proof_achieved"] is True
    assert audit_report["learning_proven_policy_uplift_achieved"] is True


def test_real_policy_eval_negative_uplift_is_recorded_but_not_mvp1c(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    prepare_mvp1b_fixture(output_dir, trajectory_dir)
    input_path = tmp_path / "real_policy_eval_negative.json"
    write_json(
        input_path,
        policy_eval_payload(
            baseline_successes=[True, True, False, True, False],
            candidate_successes=[True, False, False, False, False],
        ),
    )

    report = real_eval.run_real_policy_eval(
        input_path=input_path,
        output_path=output_dir / "policy_uplift_real_eval_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        min_rollouts_per_policy=5,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["proof_eligible"] is False
    assert report["curated_vs_uncurated_uplift"] < 0.0

    audit_report = audit(output_dir, trajectory_dir)
    assert audit_report["status"] == "pass"
    assert audit_report["staged_mvp1"]["current_stage"] == "MVP-1"
    assert audit_report["missing_required_gates"] == []
    assert audit_report["summary"]["learning_ready"] is True
    assert audit_report["summary"]["learning_proven"] is False
    assert audit_report["summary"]["policy_uplift_negative_evidence_recorded"] is True
    integrity_gate = next(item for item in audit_report["gates"] if item["name"] == "policy_claim_integrity_preserved")
    assert integrity_gate["passed"] is True


def test_real_policy_eval_rejects_proxy_or_insufficient_input_without_manifest_update(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    prepare_mvp1b_fixture(output_dir, trajectory_dir)
    input_path = tmp_path / "invalid_policy_eval.json"
    invalid_payload = policy_eval_payload(
        baseline_successes=[True, False],
        candidate_successes=[True, True],
    )
    invalid_payload["evidence_tier"] = "offline_proxy_smoke"
    write_json(input_path, invalid_payload)

    report = real_eval.run_real_policy_eval(
        input_path=input_path,
        output_path=output_dir / "policy_uplift_real_eval_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        min_rollouts_per_policy=5,
        bootstrap_iterations=200,
    )

    assert report["passed"] is False
    assert report["proof_eligible"] is False
    assert "evidence_tier must be heldout_policy_eval or real_heldout_policy_eval" in report["issues"]
    assert "baseline rollout_count must be >= 5" in report["issues"]

    manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    assert "policy_uplift_measurement" not in manifest
    assert manifest["learning_results_measured"] is False
    assert manifest["curated_vs_uncurated_uplift"] is None
