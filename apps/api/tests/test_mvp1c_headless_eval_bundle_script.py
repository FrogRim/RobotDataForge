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
headless_bundle = load_script("run_mvp1c_headless_eval_bundle")
proof = load_script("run_mvp1_proof_audit")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_headless_eval_bundle_exports_uncurated_and_curated_train_hdf5(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    output_dir = tmp_path / "mvp1c_headless_eval"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True

    report = headless_bundle.build_headless_eval_bundle(
        readiness_dir=readiness_dir,
        output_dir=output_dir,
        clean=True,
    )

    assert report["passed"] is True
    assert report["proof_eligible"] is False
    assert report["issues"] == []
    assert Path(report["baseline"]["hdf5_path"]).exists()
    assert Path(report["candidate"]["hdf5_path"]).exists()
    assert report["baseline"]["inspection"]["issues"] == []
    assert report["candidate"]["inspection"]["issues"] == []
    assert report["baseline"]["inspection"]["episode_count"] > report["candidate"]["inspection"]["episode_count"]
    assert set(report["baseline"]["train_episode_ids"]) == {
        "episode_success_a",
        "episode_success_b",
        "episode_duplicate_success_a",
        "episode_tracking_loss_failure",
    }
    assert set(report["candidate"]["train_episode_ids"]) == {
        "episode_success_a",
        "episode_success_b",
    }

    heldout = read_json(output_dir / "heldout_suite_manifest.json")
    assert heldout["held_out"] is True
    assert heldout["validation_episode_ids"] == ["episode_success_c"]
    assert heldout["test_episode_ids"] == ["episode_success_d"]

    template = read_json(output_dir / "policy_eval_input_template.json")
    assert template["evidence_tier"] == "heldout_policy_eval"
    assert template["primary_metric"] == "policy_success_rate"
    assert template["baseline"]["dataset_view"] == "uncurated_success_lifecycle"
    assert template["candidate"]["dataset_view"] == "curated_accepted"
    assert template["baseline"]["rollout_results"] == []
    assert template["candidate"]["rollout_results"] == []


def test_headless_eval_bundle_does_not_mark_mvp1c_or_update_learning_manifest(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    output_dir = tmp_path / "mvp1c_headless_eval"
    trajectory_dir = tmp_path / "real_trajectories"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    before_manifest = read_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json")

    report = headless_bundle.build_headless_eval_bundle(
        readiness_dir=readiness_dir,
        output_dir=output_dir,
        clean=True,
    )
    assert report["passed"] is True

    after_manifest = read_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json")
    assert after_manifest == before_manifest

    audit = proof.build_audit(
        readiness_report_path=readiness_dir / "readiness_report.json",
        curation_manifest_path=readiness_dir / "curation_manifest.json",
        split_manifest_path=readiness_dir / "split_manifest.json",
        dataset_card_path=readiness_dir / "dataset_card.json",
        hdf5_inspection_path=readiness_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
    )

    assert audit["staged_mvp1"]["current_stage"] == "offline_readiness"
    assert audit["staged_mvp1"]["stages"]["MVP-1"]["passed"] is False
    assert audit["policy_uplift_required_for_mvp1"] is False
    assert audit["mvp2_policy_uplift_proof"]["learning_proven"] is False
    missing = {item["name"] for item in audit["missing_required_gates"]}
    assert "raw_xr_trajectory_saved" in missing
    assert "trainer_loader_smoke_passed" in missing
