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


preflight = load_script("run_mvp1c_final_hud_ingest_preflight")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def make_readiness_dir(path: Path) -> None:
    live_export_dir = path.parent / "live_export"
    hdf5_path = live_export_dir / "rdf_mvp1_live_export_smoke.hdf5"
    entry = {
        "trajectory_id": "traj_live",
        "episode_id": "episode_live",
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
    write_json(
        path / "readiness_report.json",
        {
            "passed": True,
            "phase_coverage": ["APPROACH", "ALIGN", "CONTACT", "INSERT", "SEAT", "RELEASE"],
            "readiness_gates": {},
        },
    )
    write_json(
        path / "curation_manifest.json",
        {
            "accepted_count": 2,
            "rejected_count": 1,
            "curation_rules": {"require_replayable": True},
        },
    )
    write_json(path / "split_manifest.json", {"splits": {"train": ["ep_a"], "validation": ["ep_b"], "test": ["ep_c"]}})
    write_json(path / "dataset_card.json", {"task_type": "peg_in_hole", "num_accepted": 2})
    write_json(path / "hdf5_inspection.json", {"episode_count": 2, "issues": [], "warnings": []})
    write_json(
        path / "curated_vs_uncurated_experiment_manifest.json",
        {
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "training_readiness": {
                "loader_smoke_passed": True,
                "trainer_dry_run_passed": True,
                "one_epoch_smoke_passed": False,
                "policy_class": "linear_bc_numpy_smoke",
                "trainer": "rdf_numpy_bc_trainer_smoke",
                "evidence_source": "mvp1a_live_export_bundle",
                "hdf5_path": str(hdf5_path),
                "split_manifest_path": str(live_export_dir / "split_manifest.json"),
                "report_path": str(live_export_dir / "trainer_smoke_report.json"),
                "sample_count": 1,
                "observation_dim": 20,
                "action_dim": 7,
                "live_trajectory_ids": ["traj_live"],
                "live_episode_ids": ["episode_live"],
            },
        },
    )


def make_live_trajectory(path: Path) -> None:
    write_json(
        path / "traj_live.json",
        {
            "id": "traj_live",
            "episode_id": "episode_live",
            "source": {
                "input_device": "quest3_handtracking",
                "runtime": "steamvr_openxr",
                "simulator": "isaac_lab",
                "robot": "franka",
                "task_name": "Isaac-Forge-PegInsert-Direct-v0",
            },
            "frames": [
                {
                    "metadata": {
                        "task_state": {
                            "peg_tip_distance_to_target": 0.01,
                            "axis_alignment_error_rad": 0.1,
                            "insertion_depth": 0.02,
                        }
                    }
                }
            ],
        },
    )


def make_headless_bundle(path: Path, *, bad_template: bool = False) -> None:
    baseline_hdf5 = path / "baseline_uncurated" / "train.hdf5"
    candidate_hdf5 = path / "candidate_curated" / "train.hdf5"
    baseline_hdf5.parent.mkdir(parents=True, exist_ok=True)
    candidate_hdf5.parent.mkdir(parents=True, exist_ok=True)
    baseline_hdf5.write_bytes(b"")
    candidate_hdf5.write_bytes(b"")
    write_json(
        path / "headless_eval_bundle_report.json",
        {
            "passed": True,
            "proof_eligible": False,
            "baseline": {"train_episode_ids": ["ep_a"], "hdf5_path": str(baseline_hdf5)},
            "candidate": {"train_episode_ids": ["ep_b"], "hdf5_path": str(candidate_hdf5)},
        },
    )
    write_json(
        path / "policy_eval_input_template.json",
        {
            "evidence_tier": "isaac_headless_policy_eval_smoke" if bad_template else "heldout_policy_eval",
            "primary_metric": "policy_success_rate",
            "task_type": "peg_in_hole",
            "eval_suite": {"held_out": True, "scenario_ids": ["scenario_a"], "task_type": "peg_in_hole"},
            "baseline": {
                "dataset_view": "uncurated_success_lifecycle",
                "train_hdf5_path": str(baseline_hdf5),
                "rollout_results": [{"success": False}] if bad_template else [],
            },
            "candidate": {
                "dataset_view": "curated_accepted",
                "train_hdf5_path": str(candidate_hdf5),
                "rollout_results": [],
            },
        },
    )


def make_isaac_smoke(path: Path) -> None:
    write_json(
        path / "isaac_policy_ab_smoke_report.json",
        {
            "passed": True,
            "action_scale": 20.0,
            "evidence_tier": "isaac_headless_policy_eval_smoke",
            "proof_eligible": False,
            "baseline": {"success_rate": 0.0},
            "candidate": {"success_rate": 0.0},
            "issues": [],
        },
    )


def test_preflight_reports_ready_for_final_hud_ingest_without_claiming_mvp1c(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "readiness"
    trajectory_dir = tmp_path / "trajectories"
    headless_dir = tmp_path / "headless"
    smoke_dir = tmp_path / "smoke"
    output_dir = tmp_path / "out"
    make_readiness_dir(readiness_dir)
    make_live_trajectory(trajectory_dir)
    make_headless_bundle(headless_dir)
    make_isaac_smoke(smoke_dir)

    report = preflight.run_preflight(
        readiness_dir=readiness_dir,
        headless_eval_dir=headless_dir,
        isaac_smoke_dir=smoke_dir,
        trajectory_dir=trajectory_dir,
        output_dir=output_dir,
        refresh_headless_bundle=False,
        min_rollouts_per_policy=10,
    )

    assert report["ready_for_final_hud_ingest"] is True
    assert report["full_mvp1c_claimed"] is False
    assert report["mvp2_learning_proven_claimed"] is False
    assert report["proof_audit"]["current_stage"] == "MVP-1"
    assert report["proof_audit"]["next_stage"] == "MVP-2"
    assert report["proof_audit"]["missing_required_gates"] == []
    assert (output_dir / "preflight_report.json").exists()
    assert (output_dir / "final_hud_ingest_runbook.md").exists()


def test_preflight_blocks_bad_policy_eval_template(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "readiness"
    trajectory_dir = tmp_path / "trajectories"
    headless_dir = tmp_path / "headless"
    output_dir = tmp_path / "out"
    make_readiness_dir(readiness_dir)
    make_live_trajectory(trajectory_dir)
    make_headless_bundle(headless_dir, bad_template=True)

    report = preflight.run_preflight(
        readiness_dir=readiness_dir,
        headless_eval_dir=headless_dir,
        isaac_smoke_dir=tmp_path / "missing_smoke",
        trajectory_dir=trajectory_dir,
        output_dir=output_dir,
        refresh_headless_bundle=False,
        min_rollouts_per_policy=10,
    )

    assert report["ready_for_final_hud_ingest"] is False
    assert any("template:" in issue for issue in report["issues"])
