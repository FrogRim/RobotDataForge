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
replay_gate = load_script("apply_mvp1_replay_gate")
headless_bundle = load_script("run_mvp1c_headless_eval_bundle")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def fake_replay_report(path: Path) -> None:
    passed = {
        "episode_success_b",
        "episode_success_d",
        "episode_duplicate_success_a",
    }
    episode_ids = [
        "episode_success_a",
        "episode_success_b",
        "episode_success_c",
        "episode_success_d",
        "episode_duplicate_success_a",
        "episode_tracking_loss_failure",
    ]
    write_json(
        path,
        {
            "schema_version": "rdf_peg_insert_viability_v0.1.0",
            "replay_scope": "raw_success",
            "checks": {
                "accepted_replays": [
                    {
                        "episode_id": episode_id,
                        "trajectory_id": episode_id.replace("episode_", "traj_"),
                        "mode": "native_direct",
                        "action_field": "retargeted_robot_action",
                        "passed": episode_id in passed,
                    }
                    for episode_id in episode_ids
                ]
            },
        },
    )


def fake_single_candidate_replay_report(path: Path) -> None:
    fake_replay_report(path)
    payload = read_json(path)
    rows = payload["checks"]["accepted_replays"]
    for row in rows:
        row["passed"] = row["episode_id"] == "episode_success_a"
    write_json(path, payload)


def test_replay_gate_writes_contract_and_filters_policy_pools(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    report_path = tmp_path / "peg_insert_viability_report.json"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    fixture = read_json(readiness_dir / "raw" / "trajectories" / "traj_success_a.json")
    assert fixture["summary"]["action_replay_contract"]["initial_state"]["seed"] == 202506
    fake_replay_report(report_path)

    gate = replay_gate.apply_replay_gate(readiness_dir=readiness_dir, replay_report_path=report_path)

    assert gate["pool_ready_for_policy_ab"] is True
    assert gate["pool_blockers"] == []
    assert gate["accepted_replay_viability"] is False
    assert gate["baseline_b_replay_verified_curated_accepted_episode_ids"] == [
        "episode_success_b",
        "episode_success_d",
    ]
    assert "episode_success_a" in gate["accepted_replay_failed_episode_ids"]
    assert (readiness_dir / "action_replay_contract.json").exists()
    assert (readiness_dir / "replay_gate_manifest.json").exists()
    assert (readiness_dir / "split_manifest_replay_verified.json").exists()
    assert (readiness_dir / "curated_replay_verified" / "trajectories" / "traj_success_b.json").exists()

    experiment = read_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json")
    assert experiment["replay_gate"]["pool_ready_for_policy_ab"] is True
    assert experiment["baseline_a_replay_verified_success_lifecycle_episode_ids"] == [
        "episode_success_b",
        "episode_success_d",
        "episode_duplicate_success_a",
    ]


def test_replay_gate_requires_replay_verified_heldout_pool(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    report_path = tmp_path / "peg_insert_viability_report.json"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    fake_single_candidate_replay_report(report_path)

    gate = replay_gate.apply_replay_gate(readiness_dir=readiness_dir, replay_report_path=report_path)

    assert gate["pool_ready_for_policy_ab"] is False
    assert gate["baseline_b_replay_verified_curated_accepted_episode_ids"] == ["episode_success_a"]
    assert "replay-verified held-out validation/test set is empty" in gate["pool_blockers"]


def test_headless_bundle_prefers_replay_verified_pool_when_gate_exists(tmp_path: Path) -> None:
    readiness_dir = tmp_path / "mvp1_readiness"
    report_path = tmp_path / "peg_insert_viability_report.json"
    output_dir = tmp_path / "mvp1c_headless_eval"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    fake_replay_report(report_path)
    replay_gate.apply_replay_gate(readiness_dir=readiness_dir, replay_report_path=report_path)

    report = headless_bundle.build_headless_eval_bundle(
        readiness_dir=readiness_dir,
        output_dir=output_dir,
        clean=True,
    )

    assert report["passed"] is True
    assert report["replay_gate_used"] is True
    assert report["baseline"]["source_episode_id_field"] == "baseline_a_replay_verified_success_lifecycle_episode_ids"
    assert report["candidate"]["source_episode_id_field"] == "baseline_b_replay_verified_curated_accepted_episode_ids"
    assert report["candidate"]["train_episode_ids"] == ["episode_success_b"]
    assert Path(report["candidate"]["hdf5_path"]).exists()
