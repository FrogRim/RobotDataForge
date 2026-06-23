from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.lerobot_public_slice import (  # noqa: E402
    DEFAULT_SLICE_RULE,
    build_slice_selection_report,
    canonical_row_digest,
    convert_raw_rows_to_rdf,
    normalize_source_row,
    validate_raw_rows,
)
from app.services.lerobot_state_action_contract import LeRobotStateActionContractValidator  # noqa: E402

RUNNER_PATH = ROOT / "scripts/run_lerobot_public_slice_semantic_parity.py"


def _raw_source_row(frame_index: int) -> dict:
    return {
        "episode_index": 0,
        "frame_index": frame_index,
        "timestamp": frame_index * 0.02,
        "observation.state": [float(frame_index + i) for i in range(14)],
        "action": [float(frame_index - i) for i in range(14)],
        "next.done": False,
        "index": frame_index,
        "task_index": 0,
    }


def _raw_rows() -> list[dict]:
    return [
        normalize_source_row(
            _raw_source_row(index),
            repo_id="lerobot/aloha_static_coffee",
            resolved_revision="b144896feb1f37398a862927b22cd3abdf005a6b",
            source_file="data/chunk-000/file-000.parquet",
        )
        for index in range(8)
    ]


def _binding() -> dict:
    return {
        "repo_id": "lerobot/aloha_static_coffee",
        "resolved_revision": "b144896feb1f37398a862927b22cd3abdf005a6b",
        "dataset_card_robot_type": "aloha",
        "source_file": "data/chunk-000/file-000.parquet",
    }


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_lerobot_public_slice_semantic_parity", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_raw_rows_validate_slice_rule_and_digests() -> None:
    rows = _raw_rows()

    report = validate_raw_rows(rows, DEFAULT_SLICE_RULE)

    assert report.ok
    assert report.row_count == 8
    assert report.observation_state_dim == 14
    assert report.action_dim == 14
    assert [row["source_row_sha256"] for row in rows] == [canonical_row_digest(row) for row in rows]


def test_raw_rows_reject_slice_coordinate_drift() -> None:
    rows = _raw_rows()
    rows[-1] = {**rows[-1], "frame_index": 99}

    report = validate_raw_rows(rows, DEFAULT_SLICE_RULE)

    assert not report.ok
    assert any("frame indices" in issue for issue in report.issues)


def test_conversion_is_generic_state_action_without_fabricated_pose_fields() -> None:
    converted, mapping_report, conversion_manifest = convert_raw_rows_to_rdf(_raw_rows(), source_binding=_binding())

    assert mapping_report["fabricated_fields"] == []
    assert mapping_report["canonical_source_rejected_examples_present"] is False
    assert conversion_manifest["deterministic"] is True
    first = converted[0]
    assert first["source_robot_type"] == "aloha"
    assert first["observation_state"] == _raw_rows()[0]["observation.state"]
    assert first["learning_action"] == _raw_rows()[0]["action"]
    forbidden_keys = {"end_effector_position", "object_position", "robot_family_claimed"}
    assert forbidden_keys.isdisjoint(first)


def test_contract_rejects_dimension_drift() -> None:
    converted, _mapping_report, _conversion_manifest = convert_raw_rows_to_rdf(_raw_rows(), source_binding=_binding())
    drifted = copy.deepcopy(converted)
    drifted[3]["learning_action"] = drifted[3]["learning_action"][:-1]

    report = LeRobotStateActionContractValidator().validate_rows(drifted)

    assert not report.ok
    assert any("learning_action dimension drift" in issue for issue in report.issues)


def test_slice_selection_report_discloses_audited_slice_only() -> None:
    rows = _raw_rows()
    report = build_slice_selection_report(
        source_file="data/chunk-000/file-000.parquet",
        raw_rows=rows,
        feature_schema_sha256="a" * 64,
    )

    assert report["full_source_verdict_claimed"] is False
    assert report["audited_slice_verdict_claimed"] is True
    assert report["validation"]["ok"] is True


def test_generated_readme_preserves_aloha_profile_and_offline_boundary(tmp_path: Path) -> None:
    runner = _load_runner()

    runner.write_readme(tmp_path, _binding())

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "not a general LeRobot importer" in readme
    assert "The default verifier is offline" in readme
    assert "14-dimensional state/action contract" in readme
