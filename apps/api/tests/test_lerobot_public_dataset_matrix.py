from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from app.services.lerobot_public_slice import (
    ALOHA_PUBLIC_SLICE_PROFILE,
    LEROBOT_MATRIX_PROFILE_REGISTRY,
    SO100_PICKPLACE_PUBLIC_SLICE_PROFILE,
    build_matrix_profile_resolver_report,
    build_source_binding_from_profile,
    convert_raw_rows_to_rdf,
    get_lerobot_matrix_profile,
    normalize_source_row,
    validate_raw_rows,
    validate_lerobot_matrix_profiles,
)
from app.services.lerobot_state_action_contract import LeRobotStateActionContractValidator


ROOT = Path(__file__).resolve().parents[3]
MATRIX_PACKAGE = ROOT / "docs" / "proof" / "lerobot_public_dataset_matrix_semantic_parity_proof_package"


def test_matrix_profile_registry_pins_distinct_public_profiles() -> None:
    report = validate_lerobot_matrix_profiles(LEROBOT_MATRIX_PROFILE_REGISTRY)

    assert report["ok"] is True
    assert report["profile_ids"] == [
        "lerobot_aloha_static_coffee",
        "lerobot_svla_so100_pickplace",
    ]
    assert ALOHA_PUBLIC_SLICE_PROFILE.robot_type != SO100_PICKPLACE_PUBLIC_SLICE_PROFILE.robot_type
    assert (
        ALOHA_PUBLIC_SLICE_PROFILE.observation_state_dim,
        ALOHA_PUBLIC_SLICE_PROFILE.action_dim,
    ) != (
        SO100_PICKPLACE_PUBLIC_SLICE_PROFILE.observation_state_dim,
        SO100_PICKPLACE_PUBLIC_SLICE_PROFILE.action_dim,
    )


def test_matrix_profile_registry_rejects_floating_revision() -> None:
    report = validate_lerobot_matrix_profiles(
        (
            ALOHA_PUBLIC_SLICE_PROFILE,
            replace(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE, resolved_revision="main"),
        )
    )

    assert report["ok"] is False
    assert any("resolved_revision" in issue for issue in report["issues"])


def test_matrix_profile_registry_rejects_same_robot_type_or_same_dims() -> None:
    same_robot_type = validate_lerobot_matrix_profiles(
        (
            ALOHA_PUBLIC_SLICE_PROFILE,
            replace(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE, robot_type="aloha"),
        )
    )
    same_dims = validate_lerobot_matrix_profiles(
        (
            ALOHA_PUBLIC_SLICE_PROFILE,
            replace(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE, observation_state_dim=14, action_dim=14),
        )
    )

    assert same_robot_type["ok"] is False
    assert any("robot_type" in issue for issue in same_robot_type["issues"])
    assert same_dims["ok"] is False
    assert any("state/action dims" in issue for issue in same_dims["issues"])


def test_matrix_profile_registry_rejects_missing_or_incompatible_license() -> None:
    report = validate_lerobot_matrix_profiles(
        (
            ALOHA_PUBLIC_SLICE_PROFILE,
            replace(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE, license="unknown"),
        )
    )

    assert report["ok"] is False
    assert any("license" in issue for issue in report["issues"])


def test_unknown_matrix_profile_is_not_accepted() -> None:
    try:
        get_lerobot_matrix_profile("lerobot_unknown_profile")
    except KeyError as exc:
        assert "unknown LeRobot matrix profile" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("unknown profile should fail closed")


def test_matrix_profile_resolver_report_records_selected_and_rejected_candidates() -> None:
    report = build_matrix_profile_resolver_report()

    assert report["ok"] is True
    assert report["selected_profile_id"] == "lerobot_svla_so100_pickplace"
    assert report["selected_profile"]["repo_id"] == "lerobot/svla_so100_pickplace"
    assert report["selected_profile"]["robot_type"] == "so100"
    assert report["selected_profile"]["observation_state_dim"] == 6
    assert report["selected_profile"]["action_dim"] == 6
    rejected = {candidate["repo_id"]: candidate["reason"] for candidate in report["rejected_candidates"]}
    assert "lerobot/xarm_lift_medium" in rejected
    assert "robot_type is unknown" in rejected["lerobot/xarm_lift_medium"]


def _profile_source_row(profile, frame_index: int) -> dict:
    return {
        "episode_index": profile.episode_index,
        "frame_index": frame_index,
        "timestamp": frame_index * 0.02,
        "observation.state": [float(frame_index + i) for i in range(profile.observation_state_dim)],
        "action": [float(frame_index - i) for i in range(profile.action_dim)],
        "next.done": False,
        "index": frame_index,
        "task_index": 0,
    }


def _profile_rows(profile) -> list[dict]:
    return [
        normalize_source_row(
            _profile_source_row(profile, index),
            repo_id=profile.repo_id,
            resolved_revision=profile.resolved_revision,
            source_file=profile.source_file,
        )
        for index in range(profile.frame_count)
    ]


def test_profile_aware_raw_row_validation_accepts_only_own_profile_shape() -> None:
    so100_rows = _profile_rows(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE)

    own_report = validate_raw_rows(
        so100_rows,
        SO100_PICKPLACE_PUBLIC_SLICE_PROFILE.slice_rule,
        expected_profile=SO100_PICKPLACE_PUBLIC_SLICE_PROFILE,
    )
    wrong_profile_report = validate_raw_rows(
        so100_rows,
        ALOHA_PUBLIC_SLICE_PROFILE.slice_rule,
        expected_profile=ALOHA_PUBLIC_SLICE_PROFILE,
    )

    assert own_report.ok
    assert own_report.observation_state_dim == 6
    assert own_report.action_dim == 6
    assert not wrong_profile_report.ok
    assert any("repo_id" in issue or "observation.state dimension" in issue for issue in wrong_profile_report.issues)


def test_profile_aware_conversion_and_contract_preserve_so100_semantics() -> None:
    rows = _profile_rows(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE)
    source_binding = build_source_binding_from_profile(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE)

    converted, mapping_report, conversion_manifest = convert_raw_rows_to_rdf(
        rows,
        source_binding=source_binding,
        profile=SO100_PICKPLACE_PUBLIC_SLICE_PROFILE,
    )
    contract_report = LeRobotStateActionContractValidator().validate_rows(
        converted,
        expected_robot_type=SO100_PICKPLACE_PUBLIC_SLICE_PROFILE.robot_type,
    )

    assert mapping_report["source_robot_type"] == "so100"
    assert mapping_report["observation_state_dim"] == 6
    assert mapping_report["action_dim"] == 6
    assert conversion_manifest["row_count"] == 8
    assert converted[0]["source_robot_type"] == "so100"
    assert converted[0]["observation_state"] == rows[0]["observation.state"]
    assert converted[0]["learning_action"] == rows[0]["action"]
    assert contract_report.ok
    assert contract_report.observation_state_dim == 6
    assert contract_report.action_dim == 6


def test_profile_aware_conversion_rejects_fabricated_fields() -> None:
    rows = _profile_rows(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE)
    rows[0]["end_effector_position"] = [0.0, 0.0, 0.0]

    try:
        convert_raw_rows_to_rdf(
            rows,
            source_binding=build_source_binding_from_profile(SO100_PICKPLACE_PUBLIC_SLICE_PROFILE),
            profile=SO100_PICKPLACE_PUBLIC_SLICE_PROFILE,
        )
    except ValueError as exc:
        assert "forbidden fabricated field" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("fabricated pose fields must fail")


def test_canonical_matrix_package_contains_two_self_contained_profiles() -> None:
    manifest = _read_json(MATRIX_PACKAGE / "package_manifest.json")
    summary = _read_json(MATRIX_PACKAGE / "data" / "matrix_summary.json")

    assert manifest["package_status"] == "external_data_evaluated"
    assert summary["required_profiles"] == [
        "lerobot_aloha_static_coffee",
        "lerobot_svla_so100_pickplace",
    ]
    assert summary["variety_gate"]["passed"] is True
    for profile_id in summary["required_profiles"]:
        profile_root = MATRIX_PACKAGE / "data" / "profiles" / profile_id
        for relative in (
            "source/lerobot_raw_rows.jsonl",
            "source/public_source_binding.json",
            "source/refetch_receipt.json",
            "source/extraction_receipt.json",
            "conversion/rdf_converted_rows.jsonl",
            "contracts/normalized_state_action_contract.json",
            "export/dataset.hdf5",
            "export/trainer_smoke_report.json",
            "reports/buyer_data_evaluation_report.json",
        ):
            assert (profile_root / relative).is_file(), f"{profile_id}/{relative}"


def test_canonical_matrix_package_artifact_index_hashes_match_files() -> None:
    manifest = _read_json(MATRIX_PACKAGE / "package_manifest.json")
    data_index = _read_json(MATRIX_PACKAGE / "data" / "artifact_index.json")

    for container in (manifest, data_index):
        entries = container["artifact_index"]
        assert entries
        for entry in entries:
            path = MATRIX_PACKAGE / entry["data_path"]
            assert path.is_file(), entry["data_path"]
            assert _sha256_file(path) == entry["file_sha256"]
            assert path.stat().st_size == entry["byte_size"]


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
