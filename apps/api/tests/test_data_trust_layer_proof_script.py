from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_proof(output_dir: Path) -> dict:
    proof = load_script("run_data_trust_layer_proof")
    report = proof.build_data_trust_layer_proof(output_dir, clean=True)
    assert report["passed"] is True
    return report


def assert_paths_exist(paths: dict[str, str]) -> None:
    for key, value in paths.items():
        assert value, key
        assert Path(value).exists(), key


def lower_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).lower()


def test_trust_record_contains_reproducibility_fields(tmp_path: Path) -> None:
    build_proof(tmp_path / "proof")

    trust = read_json(tmp_path / "proof" / "trust_record.json")
    for key in (
        "schema_version",
        "provenance",
        "audit_trail",
        "verification_commands",
        "limitations",
        "artifact_paths",
        "action_semantics",
        "replay_action_contract",
        "data_quality_summary",
        "legacy_schema_field_mapping",
    ):
        assert key in trust

    for key in ("action_semantics", "replay_action_contract", "data_quality_summary", "legacy_schema_field_mapping"):
        assert trust[key]["artifact_paths"]
        assert trust[key].get("field_paths") or trust[key].get("fields")


def test_trust_record_makes_no_disallowed_claims(tmp_path: Path) -> None:
    build_proof(tmp_path / "proof")

    trust = read_json(tmp_path / "proof" / "trust_record.json")

    assert trust["hmd_readiness_claimed"] is False
    assert trust["physical_robot_readiness_claimed"] is False
    assert trust["gate_a_collection_allowed"] is False
    assert trust["policy_uplift_claimed"] is False
    assert trust["primary_source_hmd_free"] is True


def test_primary_source_metadata_is_hmd_free(tmp_path: Path) -> None:
    report = build_proof(tmp_path / "proof")
    trust = read_json(tmp_path / "proof" / "trust_record.json")
    trajectory = read_json(Path(report["artifact_paths"]["accepted_trajectory"]))

    assert trust["input_source_profile"] == "synthetic_replay_fixture"
    assert trajectory["source"]["input_device"] == "scripted_fixture"
    assert trajectory["source"]["runtime"] == "synthetic_replay_fixture"
    primary_source_text = lower_text(
        {
            "input_source_profile": trust["input_source_profile"],
            "provenance": trust["provenance"],
            "trajectory_source": trajectory["source"],
        }
    )
    for forbidden in ("quest", "quest3", "hmd", "headset", "openxr", "steamvr", "alvr"):
        assert forbidden not in primary_source_text


def test_data_trust_proof_has_accepted_and_rejected_examples(tmp_path: Path) -> None:
    build_proof(tmp_path / "proof")

    curation = read_json(tmp_path / "proof" / "curation_manifest.json")

    assert curation["accepted_count"] >= 1
    assert curation["rejected_count"] >= 1
    assert curation["accepted"]
    assert curation["rejected"]
    for item in curation["rejected"]:
        assert item["reasons"]
        assert item["evidence_fields"]
        assert any("evaluation" in field or "curation" in field for field in item["evidence_fields"])


def test_action_semantics_are_directly_asserted(tmp_path: Path) -> None:
    report = build_proof(tmp_path / "proof")
    trust = read_json(tmp_path / "proof" / "trust_record.json")
    buyer = read_json(tmp_path / "proof" / "buyer_dataset_card.json")
    proof_report = read_json(tmp_path / "proof" / "proof_report.json")
    trajectory = read_json(Path(report["artifact_paths"]["accepted_trajectory"]))

    frame_action = trajectory["frames"][0]["action"]
    for key in ("teleop_intent", "executed_control", "learning_action", "retargeted_robot_action"):
        assert frame_action[key]
    for key in ("teleop_intent", "executed_control", "learning_action"):
        role = frame_action[key]
        assert role.get("command"), key
        assert role.get("role"), key
        assert role.get("representation") == "robot_delta_ee_pose"
        assert role.get("source") == "scripted_fixture"
        assert role.get("coordinate_frame") == "task_frame"

    assert "not_training_ready_until_evaluated_curated_and_exported" in frame_action["learning_action"][
        "dataset_semantics"
    ]

    for surface in (trust["action_semantics"], buyer["action_semantics"], proof_report["action_semantics"]):
        text = lower_text(surface)
        for allowed in ("scripted_fixture", "synthetic_replay_fixture", "robot_delta_ee_pose", "task_frame"):
            assert allowed in text
        assert "hmd_free_" not in text
        for forbidden in ("quest", "quest3", "hmd", "headset", "openxr", "steamvr", "alvr"):
            assert forbidden not in text


def test_replay_action_contract_and_data_quality_status_are_directly_asserted(tmp_path: Path) -> None:
    report = build_proof(tmp_path / "proof")

    accepted_eval = read_json(Path(report["artifact_paths"]["accepted_evaluation"]))
    rejected_eval = read_json(Path(report["artifact_paths"]["rejected_evaluation"]))
    curation = read_json(tmp_path / "proof" / "curation_manifest.json")

    data_quality = accepted_eval["metrics"]["data_quality"]
    assert data_quality["replay_verified"] is True
    assert data_quality["action_contract_status"] == "pass"
    assert data_quality["action_contract_valid"] is True
    assert data_quality["control_quality"] == "pass"
    assert data_quality["quality_failure_reasons"] == []

    rejected_entry = curation["rejected"][0]
    assert rejected_entry["reasons"]
    assert rejected_entry["evaluation_id"] == rejected_eval["id"]
    assert any("evaluation" in field or "curation" in field for field in rejected_entry["evidence_fields"])


def test_data_trust_proof_exports_and_trainer_smoke_passes(tmp_path: Path) -> None:
    report = build_proof(tmp_path / "proof")

    assert Path(report["artifact_paths"]["hdf5_export"]).exists()
    trust = read_json(tmp_path / "proof" / "trust_record.json")
    inspection = read_json(Path(report["artifact_paths"]["hdf5_inspection"]))
    trainer = read_json(Path(report["artifact_paths"]["trainer_smoke_report"]))

    assert inspection["issues"] == []
    assert trainer["loader_smoke_passed"] is True
    assert trainer["trainer_dry_run_passed"] is True
    assert trainer["one_epoch_smoke_passed"] is True
    assert trainer["learning_results_measured"] is False
    assert trainer["curated_vs_uncurated_uplift"] is None
    assert trust["legacy_schema_field_mapping"]["fields"]["raw_xr_right_wrist_pose"][
        "status"
    ] == "legacy_observation_field_name"
    assert "not HMD readiness" in trust["legacy_schema_field_mapping"]["fields"]["raw_xr_right_wrist_pose"][
        "claim_boundary"
    ]


def test_buyer_report_is_evidence_backed(tmp_path: Path) -> None:
    build_proof(tmp_path / "proof")

    trust = read_json(tmp_path / "proof" / "trust_record.json")
    buyer = read_json(tmp_path / "proof" / "buyer_dataset_card.json")
    dataset_card = read_json(tmp_path / "proof" / "dataset_card.json")
    proof_report = read_json(tmp_path / "proof" / "proof_report.json")
    proof = load_script("run_data_trust_layer_proof")

    assert_paths_exist(trust["artifact_paths"])
    assert proof.reproduce_command(proof.DEFAULT_OUTPUT_DIR) == "uv run python scripts/run_data_trust_layer_proof.py --clean --pretty"
    assert "uv run python scripts/run_data_trust_layer_proof.py" in proof_report["reproduce_command"]
    limitations = " ".join(proof_report["limitations"]).lower()
    assert "does not claim hmd readiness" in limitations
    assert "does not claim policy uplift" in limitations
    dataset_limitations = lower_text(dataset_card["limitations"])
    buyer_dataset_text = lower_text(buyer["dataset_card"])
    assert "isaac/quest synthetic teleoperation" not in dataset_limitations
    assert "isaac/quest synthetic teleoperation" not in buyer_dataset_text
    assert "teleoperation unless documented otherwise" not in buyer_dataset_text
    assert "scripted fixtures" in dataset_limitations
    assert "synthetic replay fixtures" in dataset_limitations
    assert buyer["action_semantics"] == trust["action_semantics"]
    assert buyer["replay_action_contract"] == trust["replay_action_contract"]
    assert buyer["data_quality_summary"] == trust["data_quality_summary"]
    assert buyer["legacy_schema_field_mapping"] == trust["legacy_schema_field_mapping"]


def test_repo_governance_docs_are_not_hmd_primary() -> None:
    docs = {
        "README.md": ROOT / "README.md",
        "AGENTS.md": ROOT / "AGENTS.md",
        "docs/developer/project_instructions.md": ROOT
        / "docs"
        / "developer"
        / "project_instructions.md",
    }
    handoff_path = ROOT / "Handoff.md"
    if handoff_path.exists():
        docs["Handoff.md"] = handoff_path

    for name, path in docs.items():
        text = path.read_text(encoding="utf-8").lower()
        assert "data trust layer" in text or "데이터 trust layer" in text, name
        assert "experimental input adapter" in text or "experimental adapter" in text, name
        assert "quest 3 + steamvr/openxr + isaac lab 기반 수집이다" not in text, name
        assert "primary path is quest" not in text, name
        assert "quest 3 handtracking\n  -> alvr + steamvr/openxr" not in text, name

    project_instructions = docs["docs/developer/project_instructions.md"].read_text(encoding="utf-8")
    assert "Quest 3 handtracking 입력이 Isaac Lab task에 전달된다." not in project_instructions
    assert "MVP-1의 목적은 XR/HMD teleoperation raw trajectory" not in project_instructions
    assert "| ForgeXR | Quest 3 handtracking, SteamVR/OpenXR 입력 수집 |" not in project_instructions

    if "Handoff.md" in docs:
        handoff = docs["Handoff.md"].read_text(encoding="utf-8")
        reset_idx = handoff.find("2026-06-04")
        hmd_idx = handoff.find("2026-06-03 - HMD Gate 0")
        assert reset_idx != -1
        assert hmd_idx == -1 or reset_idx < hmd_idx
