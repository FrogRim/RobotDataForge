from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from app.services.mvp5a_file_drop_rehearsal import (
    MIN_CANONICAL_FRAMES,
    PROFILE_IDS,
    build_fixture_canonical_trace,
    build_profile_registry,
    generate_corrupt_drop,
    mutation_specs,
    runtime_capture_preflight,
    validate_profile_drop,
    write_golden_profile_drop,
)


def _golden_dir(tmp_path: Path, profile_id: str) -> Path:
    trace = build_fixture_canonical_trace()
    path = tmp_path / "golden" / profile_id
    write_golden_profile_drop(profile_id, trace, path)
    return path


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_profile_registry_has_exact_required_profiles() -> None:
    registry = build_profile_registry()

    assert registry["required_profile_ids"] == list(PROFILE_IDS)
    assert {profile["profile_id"] for profile in registry["profiles"]} == set(PROFILE_IDS)
    assert all(profile["external_partner_data"] is False for profile in registry["profiles"])
    assert all(profile["live_runtime_support"] is False for profile in registry["profiles"])


def test_fixture_runtime_preflight_is_not_ready() -> None:
    report = runtime_capture_preflight(None)

    assert report["runtime_capture_sufficient"] is False
    assert report["fresh_runtime_capture_required"] is True
    assert report["blocked_reason"] == "runtime_capture_not_supplied"


def test_current_mvp3c_runtime_capture_is_insufficient_for_12_frame_ready() -> None:
    report = runtime_capture_preflight(
        Path("docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package")
    )

    assert report["runtime_capture_supplied"] is True
    assert report["runtime_capture_sufficient"] is False
    assert report["observed_min_source_log_rows_emitted"] < MIN_CANONICAL_FRAMES
    assert "runtime_capture_canonical_trace_missing" in report["issues"]


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_golden_profile_drops_pass_profile_validation(tmp_path: Path, profile_id: str) -> None:
    source_dir = _golden_dir(tmp_path, profile_id)

    report = validate_profile_drop(source_dir, expected_profile_id=profile_id, case_id="golden")

    assert report.passed, report.rejection_reasons
    assert report.frame_count == MIN_CANONICAL_FRAMES
    assert report.export_eligible is True
    assert report.trainer_smoke_eligible is True
    assert report.source_file_hashes
    assert len(report.normalized_rows) == MIN_CANONICAL_FRAMES


@pytest.mark.parametrize("mutation", mutation_specs(), ids=lambda item: f"{item.profile_id}:{item.mutation_id}")
def test_each_mutation_fails_closed_with_expected_reason(tmp_path: Path, mutation) -> None:
    golden = _golden_dir(tmp_path, mutation.profile_id)
    corrupt = tmp_path / "corrupt" / mutation.profile_id / mutation.mutation_id

    generate_corrupt_drop(mutation.profile_id, mutation, golden, corrupt)
    report = validate_profile_drop(corrupt, expected_profile_id=mutation.profile_id, case_id=mutation.mutation_id)

    assert not report.passed
    assert mutation.expected_rejection_reason in report.rejection_reasons
    assert report.export_eligible is False
    assert report.trainer_smoke_eligible is False


def test_mutation_matrix_has_at_least_50_cases_and_category_coverage() -> None:
    specs = mutation_specs()

    assert len(specs) >= 50
    assert {spec.profile_id for spec in specs} == set(PROFILE_IDS)
    assert min(sum(1 for spec in specs if spec.profile_id == profile_id) for profile_id in PROFILE_IDS) >= 12
    assert {
        "schema",
        "timestamp",
        "unit",
        "frame",
        "semantics",
        "provenance",
        "claim",
        "safety",
        "shape",
    }.issubset({spec.category for spec in specs})


def test_unknown_profile_fails_without_auto_detection(tmp_path: Path) -> None:
    source_dir = _golden_dir(tmp_path, "ur_rtde_csv_v0")
    metadata = _json(source_dir / "metadata.json")
    metadata["profile_id"] = "looks_like_ur_but_unregistered"
    _write_json(source_dir / "metadata.json", metadata)

    report = validate_profile_drop(source_dir, expected_profile_id="ur_rtde_csv_v0", case_id="unknown")

    assert not report.passed
    assert "unsupported_profile" in report.rejection_reasons


def test_missing_profile_metadata_fails_closed(tmp_path: Path) -> None:
    source_dir = _golden_dir(tmp_path, "generic_command_state_jsonl_v0")
    metadata = _json(source_dir / "metadata.json")
    metadata.pop("profile_id")
    _write_json(source_dir / "metadata.json", metadata)

    report = validate_profile_drop(source_dir, expected_profile_id="generic_command_state_jsonl_v0", case_id="missing")

    assert not report.passed
    assert "unsupported_profile" in report.rejection_reasons


def test_robot_model_mismatch_fails_profile_resolution(tmp_path: Path) -> None:
    source_dir = _golden_dir(tmp_path, "franka_state_jsonl_v0")
    metadata = _json(source_dir / "metadata.json")
    metadata["robot_model"] = "ur10e"
    _write_json(source_dir / "metadata.json", metadata)

    report = validate_profile_drop(source_dir, expected_profile_id="franka_state_jsonl_v0", case_id="wrong_model")

    assert not report.passed
    assert "unsupported_profile" in report.rejection_reasons


def test_source_hashes_change_when_source_file_changes(tmp_path: Path) -> None:
    source_dir = _golden_dir(tmp_path, "generic_command_state_jsonl_v0")
    clean = validate_profile_drop(source_dir, expected_profile_id="generic_command_state_jsonl_v0", case_id="clean")
    changed_dir = tmp_path / "changed"
    shutil.copytree(source_dir, changed_dir)
    with (changed_dir / "command_state.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    changed = validate_profile_drop(changed_dir, expected_profile_id="generic_command_state_jsonl_v0", case_id="changed")

    assert clean.source_file_hashes["command_state.jsonl"]["sha256"] != changed.source_file_hashes["command_state.jsonl"]["sha256"]
