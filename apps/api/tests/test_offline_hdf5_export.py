from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import h5py
import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "export_rdf_to_hdf5.py"
SPEC = importlib.util.spec_from_file_location("export_rdf_to_hdf5", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
exporter = importlib.util.module_from_spec(SPEC)
sys.modules["export_rdf_to_hdf5"] = exporter
SPEC.loader.exec_module(exporter)

INSPECT_SCRIPT_PATH = ROOT / "scripts" / "inspect_rdf_hdf5.py"
INSPECT_SPEC = importlib.util.spec_from_file_location("inspect_rdf_hdf5", INSPECT_SCRIPT_PATH)
assert INSPECT_SPEC is not None and INSPECT_SPEC.loader is not None
inspector = importlib.util.module_from_spec(INSPECT_SPEC)
sys.modules["inspect_rdf_hdf5"] = inspector
INSPECT_SPEC.loader.exec_module(inspector)


def frame(step: int) -> dict[str, Any]:
    return {
        "t": float(step) * 0.1,
        "step": step,
        "end_effector_position": [0.5 + step * 0.01, 0.1, 0.2],
        "end_effector_quaternion": [1.0, 0.0, 0.0, 0.0],
        "object_position": [0.4 + step * 0.01, 0.0, 0.0609],
        "object_quaternion": [1.0, 0.0, 0.0, 0.0],
        "action": {
            "raw": [0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            "retargeted_robot_action": {
                "command": [0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                "action_type": "delta_ee_pose_plus_gripper",
            },
        },
        "contacts": [],
        "metadata": {
            "right_hand_tracked": True,
            "xr_frame_valid": True,
            "raw_xr": {
                "right_wrist_pose": [0.1 + step * 0.01, 0.2, 0.3, 1.0, 0.0, 0.0, 0.0],
            },
            "aligned_xr": {
                "right_wrist_pose": [0.5 + step * 0.01, 0.1, 0.2, 1.0, 0.0, 0.0, 0.0],
            },
            "retargeted": {
                "robot_action": [0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
            },
            "cube_states": {
                "cube_1": {"position": [0.4, 0.0, 0.02]},
            },
        },
    }


def trajectory_payload(
    name: str,
    *,
    status: str | None = "success",
    frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "duration_sec": 0.2,
        "collision_count": 0,
        "target_position": [0.41, 0.0, 0.0609],
    }
    if status is not None:
        summary.update(
            {
                "episode_status": status,
                "episode_started_at": "2026-05-01T00:00:00+00:00",
                "episode_finalized_at": "2026-05-01T00:00:01+00:00",
                "episode_finalize_reason": f"operator_{status}",
                "episode_failure_reason": "OPERATOR_MARKED_FAILURE" if status == "failure" else None,
                "episode_failure_note": "operator marked failure" if status == "failure" else None,
                "reset_count": 1 if status == "reset" else 0,
            }
        )
    return {
        "id": f"traj_{name}",
        "episode_id": f"episode_{name}",
        "task_id": "task_001",
        "schema_version": "0.1.0",
        "source": {
            "input_device": "quest3_handtracking",
            "runtime": "steamvr_openxr",
            "simulator": "isaac_lab",
            "robot": "franka",
            "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0",
        },
        "frames": frames if frames is not None else [frame(0), frame(1)],
        "summary": summary,
    }


def evaluation_payload(
    name: str,
    *,
    success: bool = True,
    linked: bool = True,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": f"eval_{name}",
        "success": success,
        "score": 0.9 if success else 0.1,
        "quality_score": 0.8 if success else 0.2,
        "novelty_score": 0.0,
        "stability_score": 1.0 if success else 0.0,
        "efficiency_score": 0.7,
        "smoothness_score": 0.9,
        "fraud_risk_score": 0.0,
        "failure_reason": None if success else "TARGET_MISSED",
        "metrics": metrics if metrics is not None else {
            "tracking_loss_after_warmup": 0.0,
            "retargeting_jump_max": 0.01,
        },
    }
    if linked:
        payload["episode_id"] = f"episode_{name}"
        payload["trajectory_id"] = f"traj_{name}"
        payload["task_id"] = "task_001"
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_record(
    storage_root: Path,
    name: str,
    *,
    status: str | None = "success",
    evaluation_success: bool = True,
    evaluation_linked: bool = True,
    frames: list[dict[str, Any]] | None = None,
    evaluation_metrics: dict[str, Any] | None = None,
) -> None:
    write_json(storage_root / "trajectories" / f"traj_{name}.json", trajectory_payload(name, status=status, frames=frames))
    write_json(
        storage_root / "evaluations" / f"eval_{name}.json",
        evaluation_payload(name, success=evaluation_success, linked=evaluation_linked, metrics=evaluation_metrics),
    )


def read_json_dataset(dataset: h5py.Dataset) -> dict[str, Any]:
    value = dataset[()]
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def read_strings(dataset: h5py.Dataset) -> list[str]:
    return [value.decode("utf-8") if isinstance(value, bytes) else str(value) for value in dataset[()]]


def export(storage_root: Path, output: Path, include_statuses: set[str] | None = None):
    return exporter.export_hdf5(
        output_path=output,
        trajectories_dir=storage_root / "trajectories",
        evaluations_dir=storage_root / "evaluations",
        include_statuses=include_statuses,
    )


def test_export_valid_success_episode_preserves_training_fields(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    output = tmp_path / "dataset.hdf5"
    write_record(storage_root, "success")

    result = export(storage_root, output)

    assert result.exported_episode_ids == ["episode_success"]
    with h5py.File(output, "r") as h5:
        assert set(h5.keys()) == {"episodes", "observations", "states", "actions", "timestamps", "metadata", "evaluation"}
        assert read_strings(h5["episodes"]["episode_ids"]) == ["episode_success"]
        assert h5["observations"]["episode_success"]["raw_xr_right_wrist_pose"].shape == (2, 7)
        assert h5["observations"]["episode_success"]["aligned_xr_right_wrist_pose"].shape == (2, 7)
        assert h5["actions"]["episode_success"]["teleop_intent"].shape == (2, 7)
        assert h5["actions"]["episode_success"]["executed_control"].shape == (2, 7)
        assert h5["actions"]["episode_success"]["learning_action"].shape == (2, 7)
        assert h5["actions"]["episode_success"]["retargeted_robot_action"].shape == (2, 7)
        assert h5["actions"]["episode_success"]["learning_action"].attrs["source_field"].startswith(
            "frame.action.learning_action"
        )
        assert h5["states"]["episode_success"]["robot_end_effector_position"].shape == (2, 3)
        assert h5["timestamps"]["episode_success"]["t"].shape == (2,)
        source = read_json_dataset(h5["metadata"]["episode_success"]["source_json"])
        assert source["task_name"] == "Isaac-Stack-Cube-Franka-IK-Rel-v0"


def test_default_export_excludes_failure_reset_and_incomplete(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "success", status="success", evaluation_success=True)
    write_record(storage_root, "failure", status="failure", evaluation_success=False)
    write_record(storage_root, "reset", status="reset", evaluation_success=False)
    write_record(storage_root, "incomplete", status="incomplete", evaluation_success=False, frames=[])

    result = export(storage_root, tmp_path / "dataset.hdf5")

    assert result.exported_episode_ids == ["episode_success"]
    assert result.skipped_by_status == {"failure": 1, "incomplete": 1, "reset": 1}


def test_include_flags_allow_failure_reset_and_incomplete(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "success", status="success", evaluation_success=True)
    write_record(storage_root, "failure", status="failure", evaluation_success=False)
    write_record(storage_root, "reset", status="reset", evaluation_success=False)
    write_record(storage_root, "incomplete", status="incomplete", evaluation_success=False, frames=[])

    result = export(
        storage_root,
        tmp_path / "dataset_all.hdf5",
        include_statuses={"success", "failure", "reset", "incomplete"},
    )

    assert set(result.exported_episode_ids) == {
        "episode_success",
        "episode_failure",
        "episode_reset",
        "episode_incomplete",
    }
    with h5py.File(tmp_path / "dataset_all.hdf5", "r") as h5:
        lifecycle = read_json_dataset(h5["metadata"]["episode_incomplete"]["lifecycle_json"])
        assert lifecycle["episode_status"] == "incomplete"
        assert h5["timestamps"]["episode_incomplete"]["t"].shape == (0,)


def test_missing_source_field_fails_with_clear_error(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    payload = trajectory_payload("bad", status="success")
    del payload["source"]["task_name"]
    write_json(storage_root / "trajectories" / "traj_bad.json", payload)

    with pytest.raises(exporter.ExportValidationError, match="task_name"):
        export(storage_root, tmp_path / "dataset.hdf5")


def test_export_structure_is_deterministic(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "b", status="success")
    write_record(storage_root, "a", status="success")

    first = export(storage_root, tmp_path / "first.hdf5")
    second = export(storage_root, tmp_path / "second.hdf5")

    assert first.exported_episode_ids == second.exported_episode_ids == ["episode_a", "episode_b"]
    with h5py.File(tmp_path / "first.hdf5", "r") as h5_first, h5py.File(tmp_path / "second.hdf5", "r") as h5_second:
        assert read_strings(h5_first["episodes"]["episode_ids"]) == read_strings(h5_second["episodes"]["episode_ids"])
        assert read_json_dataset(h5_first["metadata"]["dataset_json"]) == read_json_dataset(h5_second["metadata"]["dataset_json"])
        assert (
            h5_first["actions"]["episode_a"]["retargeted_robot_action"][:].tolist()
            == h5_second["actions"]["episode_a"]["retargeted_robot_action"][:].tolist()
        )


def test_legacy_recording_without_episode_status_can_be_inferred_from_evaluation(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "legacy", status=None, evaluation_success=True)

    result = export(storage_root, tmp_path / "legacy.hdf5")

    assert result.exported_episode_ids == ["episode_legacy"]
    with h5py.File(tmp_path / "legacy.hdf5", "r") as h5:
        lifecycle = read_json_dataset(h5["metadata"]["episode_legacy"]["lifecycle_json"])
        assert lifecycle["episode_status"] == "success"
        assert lifecycle["episode_status_inferred"] is True
        assert lifecycle["episode_status_source"] == "evaluation.success"


def test_unlinked_single_legacy_evaluation_is_preserved_when_unambiguous(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "legacy", status=None, evaluation_success=True, evaluation_linked=False)

    result = export(storage_root, tmp_path / "legacy_unlinked.hdf5")

    assert result.exported_episode_ids == ["episode_legacy"]
    assert result.warnings
    with h5py.File(tmp_path / "legacy_unlinked.hdf5", "r") as h5:
        assert bool(h5["episodes"]["episode_legacy"].attrs["evaluation_link_inferred"]) is True
        metrics = read_json_dataset(h5["evaluation"]["episode_legacy"]["metrics_json"])
        assert metrics["retargeting_jump_max"] == 0.01


def test_evaluator_metrics_are_preserved(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "success", status="success", evaluation_success=True)

    export(storage_root, tmp_path / "dataset.hdf5")

    with h5py.File(tmp_path / "dataset.hdf5", "r") as h5:
        evaluation = read_json_dataset(h5["evaluation"]["episode_success"]["evaluation_json"])
        metrics = read_json_dataset(h5["evaluation"]["episode_success"]["metrics_json"])
        assert evaluation["success"] is True
        assert metrics["tracking_loss_after_warmup"] == 0.0
        assert metrics["retargeting_jump_max"] == 0.01


def test_exporter_pairs_evaluation_by_explicit_trajectory_id(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(
        storage_root,
        "explicit",
        status="success",
        evaluation_success=True,
        evaluation_metrics={"tracking_loss_after_warmup": 0.0, "retargeting_jump_max": 0.123},
    )
    write_record(
        storage_root,
        "unlinked",
        status="success",
        evaluation_success=True,
        evaluation_linked=False,
        evaluation_metrics={"tracking_loss_after_warmup": 0.5, "retargeting_jump_max": 9.0},
    )

    result = export(storage_root, tmp_path / "explicit.hdf5")

    assert any("no trajectory_id/episode_id" in warning for warning in result.warnings)
    with h5py.File(tmp_path / "explicit.hdf5", "r") as h5:
        assert h5["episodes"]["episode_explicit"].attrs["evaluation_pairing_source"] == "trajectory_id"
        metrics = read_json_dataset(h5["evaluation"]["episode_explicit"]["metrics_json"])
        assert metrics["retargeting_jump_max"] == 0.123


def test_exporter_warns_but_keeps_episode_when_evaluation_metrics_are_missing(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "no_metrics", status="success", evaluation_success=True, evaluation_metrics={})

    result = export(storage_root, tmp_path / "no_metrics.hdf5")

    assert result.exported_episode_ids == ["episode_no_metrics"]
    assert any("no metrics" in warning for warning in result.warnings)
    with h5py.File(tmp_path / "no_metrics.hdf5", "r") as h5:
        assert h5["evaluation"]["episode_no_metrics"].attrs["evaluation_available"]
        assert read_json_dataset(h5["evaluation"]["episode_no_metrics"]["metrics_json"]) == {}


def test_hdf5_sanity_checker_reports_minimal_export(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "success", status="success", evaluation_success=True)
    export(storage_root, tmp_path / "dataset.hdf5")

    report = inspector.inspect_hdf5(tmp_path / "dataset.hdf5")

    assert report["episode_count"] == 1
    assert report["episode_statuses"] == {"success": 1}
    episode = report["episodes"]["episode_success"]
    assert "retargeted_robot_action" in episode["action_fields"]
    assert episode["action_dimensions"]["retargeted_robot_action"] == 7
    assert episode["timestamp_count"] == 2
    assert episode["timestamp_monotonic"] is True
    assert episode["evaluation_metrics_available"] is True
    assert episode["lifecycle_metadata_available"] is True
    assert episode["retargeting_action_jump_max"] == 0.0
    assert not report["issues"]


def test_hdf5_sanity_checker_reports_missing_optional_metrics_without_crashing(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    write_record(storage_root, "no_metrics", status="success", evaluation_success=True, evaluation_metrics={})
    export(storage_root, tmp_path / "no_metrics.hdf5")

    report = inspector.inspect_hdf5(tmp_path / "no_metrics.hdf5")

    assert report["episode_count"] == 1
    assert not report["issues"]
    assert report["episodes"]["episode_no_metrics"]["evaluation_metrics_available"] is False
    assert any("evaluation metrics empty" in warning for warning in report["warnings"])
