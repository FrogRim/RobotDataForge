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


def external_rollout_evidence() -> dict:
    return {
        "source_kind": "external_heldout_policy_eval",
        "proof_grade": True,
        "heldout_suite": {
            "id": "external_ur_heldout_policy_eval_suite",
            "held_out": True,
            "task_type": "connector_insertion",
            "scenario_ids": ["scenario_0"],
            "scenario_set_sha256": "external_scenario_set_sha256",
            "source_kind": "external_trainer_eval_suite",
            "proof_role": "external_policy_eval_suite",
        },
        "baseline_policy_artifact_sha256": "baseline_policy_sha256",
        "candidate_policy_artifact_sha256": "candidate_policy_sha256",
        "baseline_training_artifact_sha256": "baseline_training_sha256",
        "candidate_training_artifact_sha256": "candidate_training_sha256",
        "baseline_external_evaluator_run": {
            "run_id": "baseline_external_eval_run",
            "runner_version": "external_eval_runner_v1",
            "run_log_uri": "file:///external/baseline.jsonl",
            "generated_outside_rdf_local_proxy": True,
        },
        "candidate_external_evaluator_run": {
            "run_id": "candidate_external_eval_run",
            "runner_version": "external_eval_runner_v1",
            "run_log_uri": "file:///external/candidate.jsonl",
            "generated_outside_rdf_local_proxy": True,
        },
    }


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


def audit_with_mvp2_harness(
    output_dir: Path,
    *,
    trajectory_dir: Path,
    harness_report: Path,
    learning_manifest: Path | None = None,
) -> dict:
    return proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=learning_manifest or output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
        mvp2_policy_ab_harness_report_path=harness_report,
    )


def audit_with_mvp2_learning_proven(
    output_dir: Path,
    *,
    trajectory_dir: Path,
    learning_proven_report: Path,
    learning_manifest: Path | None = None,
) -> dict:
    return proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=learning_manifest or output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
        mvp2_learning_proven_report_path=learning_proven_report,
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


def test_proof_audit_summarizes_mvp2_harness_without_learning_proven_claim(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)
    harness_report = tmp_path / "mvp2_policy_ab_harness_report.json"
    write_json(
        harness_report,
        {
            "schema_version": "rdf_mvp2_ur_policy_ab_harness_v0.1.0",
            "passed": True,
            "harness_ready": True,
            "rollout_ingest_contract_ready": True,
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "learning_proven": False,
            "proof_eligible": False,
            "proof_source": {
                "adapter_id": "universal_robots_ur_industrial_arm",
                "source_evidence_type": "file_backed_recorded_log_fixture",
                "validator_backend": "NormalizedTrajectoryContractValidator",
            },
            "claim_boundary": {
                "policy_uplift_claimed": False,
                "learning_results_measured": False,
                "curated_vs_uncurated_uplift": None,
                "learning_proven": False,
                "proof_eligible": False,
            },
            "mvp2a_transition_policy_readiness": {
                "schema_version": "rdf_mvp2a_transition_policy_readiness_v0.1.0",
                "passed": True,
                "mvp2a_policy_ab_ready": True,
                "stronger_policy_trainer_selected": True,
                "next_recommended_gate": "external_heldout_policy_rollout_generation",
                "candidate_curated_train": {
                    "transition_coverage_passed": True,
                    "train_set_overfit_passed": True,
                    "dataset_present_required_phases": ["APPROACH", "CONTACT", "INSERT", "SEAT"],
                    "dataset_missing_required_phases": [],
                    "transition_rich_episode_count": 1,
                },
                "policy_trainer_selection": {
                    "schema_version": "rdf_mvp2a_policy_trainer_selection_v0.1.0",
                    "selected": True,
                    "policy_class": "phase_conditioned_sequence_bc_policy_v0",
                    "trainer": "rdf_phase_conditioned_sequence_bc_trainer_contract_v0",
                },
            },
        },
    )

    report = audit_with_mvp2_harness(
        output_dir,
        trajectory_dir=trajectory_dir,
        harness_report=harness_report,
    )

    harness = report["mvp2_policy_ab_harness"]
    assert harness["available"] is True
    assert harness["harness_ready"] is True
    assert harness["rollout_ingest_contract_ready"] is True
    assert harness["adapter_id"] == "universal_robots_ur_industrial_arm"
    assert harness["source_evidence_type"] == "file_backed_recorded_log_fixture"
    assert harness["learning_results_measured"] is False
    assert harness["learning_proven"] is False
    assert harness["proof_eligible"] is False
    assert harness["mvp2a_policy_ab_ready"] is True
    assert harness["stronger_policy_trainer_selected"] is True
    assert harness["selected_policy_class"] == "phase_conditioned_sequence_bc_policy_v0"
    assert harness["selected_trainer"] == "rdf_phase_conditioned_sequence_bc_trainer_contract_v0"
    assert harness["mvp2a_next_recommended_gate"] == "external_heldout_policy_rollout_generation"
    assert harness["candidate_transition_coverage_passed"] is True
    assert harness["candidate_train_set_overfit_passed"] is True
    stronger_gate = next(
        gate for gate in report["mvp2_policy_uplift_proof"]["gates"] if gate["name"] == "stronger_policy_trainer"
    )
    assert stronger_gate["passed"] is True
    assert stronger_gate["evidence"]["selected_policy_class"] == "phase_conditioned_sequence_bc_policy_v0"
    assert stronger_gate["evidence"]["selected_trainer"] == "rdf_phase_conditioned_sequence_bc_trainer_contract_v0"
    assert report["learning_proven_policy_uplift_achieved"] is False
    assert report["policy_uplift_required_for_mvp1"] is False
    assert report["summary"]["do_not_claim_policy_uplift"] is True


def test_proof_audit_summarizes_mvp2_learning_proven_positive_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)
    mvp2_report = tmp_path / "mvp2_learning_proven_report.json"
    policy_eval_report = tmp_path / "mvp2_policy_eval_report.json"
    write_json(
        policy_eval_report,
        {
            "passed": True,
            "learning_results_measured": True,
            "proof_eligible": True,
            "evidence_tier": "heldout_policy_eval",
            "primary_metric": "policy_success_rate",
            "baseline_success_rate": 0.4,
            "candidate_success_rate": 0.8,
            "curated_vs_uncurated_uplift": 0.4,
            "eval_suite": {
                "id": "external_ur_heldout_policy_eval_suite",
                "held_out": True,
                "task_type": "connector_insertion",
                "scenario_ids": ["scenario_0"],
                "source_kind": "external_trainer_eval_suite",
                "proof_role": "external_policy_eval_suite",
            },
        },
    )
    write_json(
        mvp2_report,
        {
            "schema_version": "rdf_mvp2_learning_proven_policy_eval_v0.1.0",
            "passed": True,
            "learning_results_measured": True,
            "learning_proven": True,
            "proof_eligible": True,
            "evidence_tier": "external_heldout_policy_eval",
            "validator_evidence_tier": "heldout_policy_eval",
            "primary_metric": "policy_success_rate",
            "baseline_success_rate": 0.4,
            "candidate_success_rate": 0.8,
            "curated_vs_uncurated_uplift": 0.4,
            "proof_source": {"adapter_id": "universal_robots_ur_industrial_arm"},
            "artifact_paths": {"policy_eval_report": str(policy_eval_report)},
            "external_rollout_evidence": external_rollout_evidence(),
            "blockers": [],
            "limitations": ["external held-out policy eval proof"],
        },
    )

    report = audit_with_mvp2_learning_proven(
        output_dir,
        trajectory_dir=trajectory_dir,
        learning_proven_report=mvp2_report,
    )

    mvp2 = report["mvp2_learning_proven_policy_eval"]
    assert mvp2["available"] is True
    assert mvp2["validator_report_compatible"] is True
    assert mvp2["learning_results_measured"] is True
    assert mvp2["learning_proven"] is True
    assert mvp2["proof_eligible"] is True
    assert mvp2["evidence_tier"] == "external_heldout_policy_eval"
    assert mvp2["validator_evidence_tier"] == "heldout_policy_eval"
    assert mvp2["curated_vs_uncurated_uplift"] == 0.4
    assert report["learning_proven_policy_uplift_achieved"] is True
    assert report["summary"]["learning_proven"] is True
    assert report["summary"]["policy_uplift_positive"] is True
    assert report["policy_uplift_required_for_mvp1"] is False
    proof_status = report["mvp2_policy_uplift_proof"]
    assert proof_status["learning_proven"] is True
    assert proof_status["summary"]["heldout_policy_ab_recorded"] is True
    assert proof_status["summary"]["evidence_tier"] == "external_heldout_policy_eval"
    heldout_gate = next(
        gate for gate in proof_status["gates"] if gate["name"] == "heldout_policy_ab_recorded"
    )
    uplift_gate = next(
        gate for gate in proof_status["gates"] if gate["name"] == "curated_vs_uncurated_policy_uplift_positive"
    )
    assert heldout_gate["passed"] is True
    assert uplift_gate["passed"] is True


def test_proof_audit_does_not_promote_local_offline_proxy_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)
    mvp2_report = tmp_path / "mvp2_learning_proven_report.json"
    write_json(
        mvp2_report,
        {
            "schema_version": "rdf_mvp2_learning_proven_policy_eval_v0.1.0",
            "passed": True,
            "learning_results_measured": True,
            "learning_proven": True,
            "proof_eligible": True,
            "evidence_tier": "local_offline_policy_eval_proxy",
            "validator_evidence_tier": None,
            "primary_metric": "policy_success_rate",
            "baseline_success_rate": 0.4,
            "candidate_success_rate": 0.8,
            "curated_vs_uncurated_uplift": 0.4,
            "blockers": ["Local offline deterministic proxy cannot close MVP-2."],
            "limitations": ["proxy evidence only"],
        },
    )

    report = audit_with_mvp2_learning_proven(
        output_dir,
        trajectory_dir=trajectory_dir,
        learning_proven_report=mvp2_report,
    )

    mvp2 = report["mvp2_learning_proven_policy_eval"]
    assert mvp2["available"] is True
    assert mvp2["reported_learning_results_measured"] is True
    assert mvp2["learning_results_measured"] is False
    assert mvp2["learning_proven"] is False
    assert mvp2["proof_eligible"] is False
    assert mvp2["negative_or_tie_result_recorded"] is False
    assert mvp2["validator_report_compatible"] is False
    assert report["learning_proven_policy_uplift_achieved"] is False
    assert report["summary"]["policy_uplift_positive"] is False
    assert report["policy_uplift_required_for_mvp1"] is False


def test_proof_audit_summarizes_mvp2_learning_proven_negative_report_without_mvp1_blocker(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)
    mvp2_report = tmp_path / "mvp2_learning_proven_report.json"
    policy_eval_report = tmp_path / "mvp2_policy_eval_report.json"
    write_json(
        policy_eval_report,
        {
            "passed": True,
            "learning_results_measured": True,
            "proof_eligible": False,
            "evidence_tier": "heldout_policy_eval",
            "primary_metric": "policy_success_rate",
            "baseline_success_rate": 0.8,
            "candidate_success_rate": 0.4,
            "curated_vs_uncurated_uplift": -0.4,
            "eval_suite": {
                "id": "external_ur_heldout_policy_eval_suite",
                "held_out": True,
                "task_type": "connector_insertion",
                "scenario_ids": ["scenario_0"],
                "source_kind": "external_trainer_eval_suite",
                "proof_role": "external_policy_eval_suite",
            },
        },
    )
    write_json(
        mvp2_report,
        {
            "schema_version": "rdf_mvp2_learning_proven_policy_eval_v0.1.0",
            "passed": True,
            "learning_results_measured": True,
            "learning_proven": False,
            "proof_eligible": False,
            "evidence_tier": "external_heldout_policy_eval",
            "validator_evidence_tier": "heldout_policy_eval",
            "primary_metric": "policy_success_rate",
            "baseline_success_rate": 0.8,
            "candidate_success_rate": 0.4,
            "curated_vs_uncurated_uplift": -0.4,
            "artifact_paths": {"policy_eval_report": str(policy_eval_report)},
            "external_rollout_evidence": external_rollout_evidence(),
            "blockers": ["Curated held-out policy success rate did not exceed baseline."],
            "limitations": ["negative result is preserved as evidence"],
        },
    )

    report = audit_with_mvp2_learning_proven(
        output_dir,
        trajectory_dir=trajectory_dir,
        learning_proven_report=mvp2_report,
    )

    mvp2 = report["mvp2_learning_proven_policy_eval"]
    assert mvp2["available"] is True
    assert mvp2["learning_results_measured"] is True
    assert mvp2["learning_proven"] is False
    assert mvp2["proof_eligible"] is False
    assert mvp2["negative_or_tie_result_recorded"] is True
    assert mvp2["blockers"] == ["Curated held-out policy success rate did not exceed baseline."]
    assert report["learning_proven_policy_uplift_achieved"] is False
    assert report["summary"]["learning_proven"] is False
    assert report["summary"]["policy_uplift_negative_evidence_recorded"] is True
    assert report["policy_uplift_required_for_mvp1"] is False


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
