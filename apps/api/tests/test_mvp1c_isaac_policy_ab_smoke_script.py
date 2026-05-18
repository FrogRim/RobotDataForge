from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import h5py
import numpy as np


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


isaac_smoke = load_script("run_mvp1c_isaac_policy_ab_smoke")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_hdf5(path: Path, episode_id: str, action_bias: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as h5:
        string_dtype = h5py.string_dtype(encoding="utf-8")
        h5.create_dataset("episodes/episode_ids", data=np.array([episode_id], dtype=object), dtype=string_dtype)
        observations = h5.create_group(f"observations/{episode_id}")
        actions = h5.create_group(f"actions/{episode_id}")
        frames = 6
        observations.create_dataset(
            "end_effector_position",
            data=np.tile(np.array([[0.1, 0.2, 0.3]], dtype=np.float32), (frames, 1)),
        )
        observations.create_dataset(
            "object_position",
            data=np.tile(np.array([[0.4, 0.5, 0.6]], dtype=np.float32), (frames, 1)),
        )
        observations.create_dataset(
            "raw_xr_right_wrist_pose",
            data=np.tile(np.array([[0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]], dtype=np.float32), (frames, 1)),
        )
        observations.create_dataset(
            "aligned_xr_right_wrist_pose",
            data=np.tile(np.array([[0.1, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0]], dtype=np.float32), (frames, 1)),
        )
        action = np.zeros((frames, 7), dtype=np.float32)
        action[:, 0] = action_bias
        action[:, 6] = 1.0
        actions.create_dataset("retargeted_robot_action", data=action)


def make_template(path: Path, baseline_hdf5: Path, candidate_hdf5: Path) -> None:
    write_json(
        path,
        {
            "schema_version": "rdf_mvp1c_policy_eval_input_v0.1.0",
            "evidence_tier": "heldout_policy_eval",
            "primary_metric": "policy_success_rate",
            "task_type": "peg_in_hole",
            "eval_suite": {
                "id": "peg_in_hole_heldout_v1",
                "held_out": True,
                "split": "validation_plus_test",
                "task_type": "peg_in_hole",
                "scenario_ids": ["scenario_a", "scenario_b"],
            },
            "baseline": {
                "name": "uncurated_success_lifecycle_policy",
                "dataset_view": "uncurated_success_lifecycle",
                "dataset_id": "baseline",
                "train_hdf5_path": str(baseline_hdf5),
                "rollout_results": [],
            },
            "candidate": {
                "name": "curated_accepted_policy",
                "dataset_view": "curated_accepted",
                "dataset_id": "candidate",
                "train_hdf5_path": str(candidate_hdf5),
                "rollout_results": [],
            },
        },
    )


def test_linear_policy_training_loads_hdf5_and_predicts(tmp_path: Path) -> None:
    hdf5_path = tmp_path / "train.hdf5"
    make_hdf5(hdf5_path, "episode_a", action_bias=0.25)

    training = isaac_smoke.load_policy_training_data(hdf5_path)
    policy, issues = isaac_smoke.fit_linear_bc_policy("test", training)

    assert issues == []
    assert policy is not None
    assert training.observations.shape == (6, 20)
    assert training.actions.shape == (6, 7)
    prediction = policy.predict(training.observations[:1])
    assert prediction.shape == (1, 7)
    assert np.isfinite(prediction).all()


def test_rollout_csv_to_policy_eval_input_defaults_to_smoke_tier(tmp_path: Path) -> None:
    baseline_hdf5 = tmp_path / "baseline.hdf5"
    candidate_hdf5 = tmp_path / "candidate.hdf5"
    make_hdf5(baseline_hdf5, "episode_baseline", action_bias=0.1)
    make_hdf5(candidate_hdf5, "episode_candidate", action_bias=0.2)
    template_path = tmp_path / "template.json"
    make_template(template_path, baseline_hdf5, candidate_hdf5)

    baseline_rollouts = [
        {"rollout_id": "b0", "scenario_id": "s0", "seed": 0, "success": False, "steps": 3},
        {"rollout_id": "b1", "scenario_id": "s1", "seed": 1, "success": True, "steps": 2},
    ]
    candidate_rollouts = [
        {"rollout_id": "c0", "scenario_id": "s0", "seed": 0, "success": True, "steps": 2},
        {"rollout_id": "c1", "scenario_id": "s1", "seed": 1, "success": True, "steps": 2},
    ]
    baseline_csv = tmp_path / "baseline_rollouts.csv"
    candidate_csv = tmp_path / "candidate_rollouts.csv"
    isaac_smoke.write_rollout_csv(baseline_csv, baseline_rollouts)
    isaac_smoke.write_rollout_csv(candidate_csv, candidate_rollouts)

    output_path = tmp_path / "policy_eval_input.json"
    report = isaac_smoke.build_policy_eval_input_from_rollouts(
        template_path=template_path,
        baseline_csv=baseline_csv,
        candidate_csv=candidate_csv,
        output_path=output_path,
        evidence_tier="isaac_headless_policy_eval_smoke",
        policy_class="linear_bc_numpy_isaac_smoke",
        trainer="rdf_linear_bc_isaac_headless_smoke",
    )

    assert report["evidence_tier"] == "isaac_headless_policy_eval_smoke"
    generated = read_json(output_path)
    assert generated["evidence_tier"] == "isaac_headless_policy_eval_smoke"
    assert generated["baseline"]["rollout_results"][0]["success"] is False
    assert generated["candidate"]["rollout_results"][0]["success"] is True
    assert "limitations" in generated


def test_policy_ab_smoke_skip_isaac_does_not_generate_proof(tmp_path: Path) -> None:
    baseline_hdf5 = tmp_path / "baseline.hdf5"
    candidate_hdf5 = tmp_path / "candidate.hdf5"
    make_hdf5(baseline_hdf5, "episode_baseline", action_bias=0.1)
    make_hdf5(candidate_hdf5, "episode_candidate", action_bias=0.2)
    template_path = tmp_path / "template.json"
    make_template(template_path, baseline_hdf5, candidate_hdf5)

    report = isaac_smoke.run_policy_ab_smoke(
        baseline_hdf5=baseline_hdf5,
        candidate_hdf5=candidate_hdf5,
        template_path=template_path,
        output_dir=tmp_path / "out",
        task="Isaac-Forge-PegInsert-Direct-v0",
        device="cuda:0",
        rollouts_per_policy=2,
        max_steps=3,
        seed_start=100,
        action_scale=1.0,
        headless=True,
        evidence_tier="isaac_headless_policy_eval_smoke",
        skip_isaac=True,
    )

    assert report["passed"] is False
    assert report["proof_eligible"] is False
    assert report["baseline"]["sample_count"] == 6
    assert report["candidate"]["sample_count"] == 6
    assert report["policy_eval_input_path"] is None


def test_policy_eval_input_can_be_marked_headless_heldout(tmp_path: Path) -> None:
    baseline_hdf5 = tmp_path / "baseline.hdf5"
    candidate_hdf5 = tmp_path / "candidate.hdf5"
    make_hdf5(baseline_hdf5, "episode_baseline", action_bias=0.1)
    make_hdf5(candidate_hdf5, "episode_candidate", action_bias=0.2)
    template_path = tmp_path / "template.json"
    make_template(template_path, baseline_hdf5, candidate_hdf5)
    baseline_csv = tmp_path / "baseline_rollouts.csv"
    candidate_csv = tmp_path / "candidate_rollouts.csv"
    isaac_smoke.write_rollout_csv(
        baseline_csv,
        [{"rollout_id": "b0", "scenario_id": "s0", "seed": 0, "success": False, "steps": 3}],
    )
    isaac_smoke.write_rollout_csv(
        candidate_csv,
        [{"rollout_id": "c0", "scenario_id": "s0", "seed": 0, "success": True, "steps": 2}],
    )

    output_path = tmp_path / "policy_eval_input.json"
    report = isaac_smoke.build_policy_eval_input_from_rollouts(
        template_path=template_path,
        baseline_csv=baseline_csv,
        candidate_csv=candidate_csv,
        output_path=output_path,
        evidence_tier="heldout_policy_eval",
        policy_class="linear_bc_numpy_isaac",
        trainer="rdf_linear_bc_isaac_headless",
    )

    generated = read_json(output_path)
    assert report["evidence_tier"] == "heldout_policy_eval"
    assert generated["evidence_tier"] == "heldout_policy_eval"
    assert any("headless Isaac held-out" in item for item in generated["limitations"])
