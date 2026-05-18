from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import h5py


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
mvp2_sanity = load_script("run_mvp2_learning_sanity")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _force_all_hdf5_phases(hdf5_path: Path, phase: str) -> None:
    with h5py.File(hdf5_path, "r+") as h5:
        episode_ids = [
            value.decode("utf-8") if isinstance(value, bytes) else str(value)
            for value in h5["episodes/episode_ids"][()]
        ]
        for episode_id in episode_ids:
            dataset = h5[f"observations/{episode_id}/metadata_json"]
            for index in range(dataset.shape[0]):
                dataset[index] = json.dumps({"action_phase": phase})


def test_mvp2_learning_sanity_passes_transition_rich_readiness_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    assert readiness.build_bundle(output_dir, clean=True)["passed"] is True

    report = mvp2_sanity.run_learning_sanity(
        hdf5_path=output_dir / "rdf_mvp1_curated_readiness.hdf5",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        output_path=output_dir / "mvp2_learning_sanity_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["curated_vs_uncurated_uplift"] is None
    assert report["next_recommended_gate"] == "stronger_policy_trainer_selection"

    transition = report["mvp2_ladder_gates"]["transition_coverage_audit"]
    assert transition["passed"] is True
    assert transition["transition_rich_episode_count"] == 4
    assert transition["dataset_missing_required_phases"] == []
    assert set(transition["dataset_present_required_phases"]) >= {"APPROACH", "CONTACT", "INSERT", "SEAT"}

    overfit = report["mvp2_ladder_gates"]["train_set_overfit_sanity"]
    assert overfit["passed"] is True
    assert overfit["sample_count"] > 0
    assert overfit["mse_ratio_to_mean_baseline"] <= overfit["max_mse_ratio"]

    manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    sanity = manifest["mvp2_learning_sanity"]
    assert sanity["passed"] is True
    assert sanity["transition_coverage_passed"] is True
    assert sanity["train_set_overfit_passed"] is True
    assert sanity["learning_results_measured"] is False
    assert sanity["curated_vs_uncurated_uplift"] is None


def test_mvp2_learning_sanity_blocks_stable_hold_only_dataset(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    assert readiness.build_bundle(output_dir, clean=True)["passed"] is True
    hdf5_path = output_dir / "rdf_mvp1_curated_readiness.hdf5"
    _force_all_hdf5_phases(hdf5_path, "SEAT")

    report = mvp2_sanity.run_learning_sanity(
        hdf5_path=hdf5_path,
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        output_path=output_dir / "mvp2_learning_sanity_report.json",
        experiment_manifest_path=None,
    )

    assert report["passed"] is False
    assert report["next_recommended_gate"] == "transition_coverage_audit"
    transition = report["mvp2_ladder_gates"]["transition_coverage_audit"]
    assert transition["passed"] is False
    assert transition["transition_rich_episode_count"] == 0
    assert transition["dataset_missing_required_phases"] == ["APPROACH", "CONTACT", "INSERT"]
    assert transition["dataset_phase_counts"] == {"SEAT": 96}
    assert report["mvp2_ladder_gates"]["train_set_overfit_sanity"]["passed"] is True
