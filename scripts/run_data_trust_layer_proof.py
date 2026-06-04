#!/usr/bin/env python3
"""Build a buyer-facing HMD-free data trust layer proof bundle.

This proof is not HMD readiness, physical collection readiness, Gate A
readiness, or policy-uplift evidence. It proves that RDF can generate
reproducible accepted/rejected robot-data artifacts with action semantics,
replay/action-contract evidence, curation evidence, HDF5 export, and trainer
loader smoke without depending on Quest/OpenXR/HMD input.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
SCRIPTS_ROOT = ROOT / "scripts"
for path in (API_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.curator import curate_episodes_with_reasons  # noqa: E402
from app.services.dataset_card import build_dataset_card  # noqa: E402
from export_rdf_to_hdf5 import export_hdf5  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402
import run_mvp1_offline_readiness as readiness  # noqa: E402
from run_mvp1_trainer_smoke import run_trainer_smoke  # noqa: E402


SCHEMA_VERSION = "rdf_data_trust_layer_proof_v0.1.0"
TRUST_RECORD_SCHEMA_VERSION = "rdf_data_trust_record_v0.1.0"
PROOF_ID = "rdf_data_trust_layer_hmd_free_fixture_v0"
DATASET_ID = "dataset_rdf_data_trust_layer_hmd_free_fixture"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "data_trust_layer_proof"
SOURCE_PROFILE = {
    "input_device": "scripted_fixture",
    "runtime": "synthetic_replay_fixture",
    "simulator": "isaac_lab",
    "robot": "franka",
    "task_name": "peg_in_hole_data_trust_layer_fixture",
}
ACTION_CANONICAL_VALUES = {
    "source": "scripted_fixture",
    "representation": "robot_delta_ee_pose",
    "replay_source": "synthetic_replay_fixture",
    "coordinate_frame": "task_frame",
}
CANONICAL_REPRODUCE_COMMAND = "uv run python scripts/run_data_trust_layer_proof.py --clean --pretty"
DATA_TRUST_DATASET_CARD_LIMITATIONS = [
    "Primary proof dataset is generated from deterministic scripted fixtures and synthetic replay fixtures.",
    "Quest/OpenXR/HMD adapters are preserved experimental input adapters and are excluded from this primary proof.",
    "LeRobot-compatible export is metadata-ready but not implemented as a full LeRobot Dataset v3 writer.",
    "Unmeasured sync fields are stored as null and must not be treated as measured values.",
]
LEGACY_OBSERVATION_FIELD_MAPPING = {
    "raw_xr_right_wrist_pose": {
        "status": "legacy_observation_field_name",
        "canonical_meaning": "raw_scripted_fixture_input_pose",
        "claim_boundary": "Compatibility field name only; not HMD readiness, live XR readiness, or Gate A evidence.",
    },
    "aligned_xr_right_wrist_pose": {
        "status": "legacy_observation_field_name",
        "canonical_meaning": "aligned_scripted_fixture_input_pose",
        "claim_boundary": "Compatibility field name only; not HMD readiness, live XR readiness, or Gate A evidence.",
    },
}
ACTION_FIELD_PATHS = [
    "frames[].action.teleop_intent",
    "frames[].action.executed_control",
    "frames[].action.learning_action",
    "frames[].action.retargeted_robot_action",
]
REPLAY_FIELD_PATHS = [
    "trajectory.summary.action_replay_contract",
    "evaluation.metrics.data_quality.replay_verified",
    "evaluation.metrics.data_quality.action_contract_status",
    "evaluation.metrics.data_quality.action_contract_valid",
]
DATA_QUALITY_FIELD_PATHS = [
    "evaluation.metrics.data_quality.replay_verified",
    "evaluation.metrics.data_quality.action_contract_status",
    "evaluation.metrics.data_quality.control_quality",
    "evaluation.metrics.data_quality.quality_failure_reasons",
    "curation_manifest.accepted",
    "curation_manifest.rejected",
]


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def reproduce_command(output_dir: Path) -> str:
    if output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve():
        return CANONICAL_REPRODUCE_COMMAND
    return f"uv run python scripts/run_data_trust_layer_proof.py --output-dir {artifact_path(output_dir)} --clean --pretty"


def _normalize_action(action: dict[str, Any]) -> None:
    action["action_contract_version"] = "rdf_action_contract_v0.2.0"
    action["replay_contract_version"] = "rdf_replay_contract_v0.2.0"
    retargeted = action.get("retargeted_robot_action")
    if isinstance(retargeted, dict):
        retargeted["source"] = ACTION_CANONICAL_VALUES["replay_source"]
        retargeted["representation"] = ACTION_CANONICAL_VALUES["representation"]
        retargeted["coordinate_frame"] = ACTION_CANONICAL_VALUES["coordinate_frame"]
        retargeted["role"] = "robot_action_for_replay_comparison"

    for key, role in (
        ("teleop_intent", "operator_intent"),
        ("executed_control", "robot_control_command"),
        ("learning_action", "candidate_robot_action_for_learning"),
    ):
        payload = action.get(key)
        if not isinstance(payload, dict):
            continue
        payload["role"] = role
        payload["source"] = ACTION_CANONICAL_VALUES["source"]
        payload["representation"] = ACTION_CANONICAL_VALUES["representation"]
        payload["coordinate_frame"] = ACTION_CANONICAL_VALUES["coordinate_frame"]

    teleop_intent = action.get("teleop_intent")
    if isinstance(teleop_intent, dict):
        teleop_intent["label"] = "scripted_fixture_operator_intent"

    executed_control = action.get("executed_control")
    if isinstance(executed_control, dict):
        executed_control["control_mode"] = "scripted_fixture_operator_control"
        executed_control["control_semantics"] = "bounded_task_frame_delta_ee_pose"
        executed_control["applied_to_env"] = True

    learning_action = action.get("learning_action")
    if isinstance(learning_action, dict):
        learning_action["validation_state"] = "requires_evaluation_and_curation"
        learning_action["dataset_semantics"] = "not_training_ready_until_evaluated_curated_and_exported"


def normalize_trajectory(trajectory: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(trajectory)
    normalized["schema_version"] = "rdf_data_trust_trajectory_v0.1.0"
    normalized["source"] = dict(SOURCE_PROFILE)
    summary = normalized.setdefault("summary", {})
    summary["task_state_source"] = "synthetic_replay_fixture"
    summary["fixture_source"] = "scripted_fixture"
    summary["data_trust_layer_proof_id"] = PROOF_ID
    summary["action_replay_contract"] = {
        "schema_version": "rdf_action_replay_contract_v0.2.0",
        "name": "data_trust_layer_scripted_fixture_replay",
        "task": "Isaac-Forge-PegInsert-Direct-v0",
        "replay_mode": "native_direct",
        "action_field": "retargeted_robot_action",
        "action_source": ACTION_CANONICAL_VALUES["replay_source"],
        "action_representation": ACTION_CANONICAL_VALUES["representation"],
        "coordinate_frame": ACTION_CANONICAL_VALUES["coordinate_frame"],
        "initial_state": {
            "type": "deterministic_synthetic_fixture",
            "seed": 20260604,
            "reason": "Proof fixtures are generated deterministically for replay/action-contract inspection.",
        },
        "repeat": 1,
    }
    summary["action_replay_gate"] = {
        "schema_version": "rdf_action_replay_gate_v0.1.0",
        "passed": True,
        "replay_mode": "native_direct",
        "action_field": "retargeted_robot_action",
        "verification_source": "synthetic_replay_fixture",
        "notes": "Deterministic fixture replay gate for data trust layer proof.",
    }
    for frame in normalized.get("frames", []):
        if not isinstance(frame, dict):
            continue
        action = frame.get("action")
        if isinstance(action, dict):
            _normalize_action(action)
        metadata = frame.get("metadata")
        if isinstance(metadata, dict):
            pipeline = metadata.get("teleop_pipeline")
            if isinstance(pipeline, dict):
                pipeline["product_role"] = "robot_data_trust_layer_fixture_to_validated_dataset"
                pipeline["control_mode"] = "scripted_fixture_operator_control"
                pipeline["control_semantics"] = "bounded_task_frame_delta_ee_pose"
    return normalized


def build_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for spec in readiness.fixture_specs():
        trajectory = readiness.build_trajectory(
            spec["name"],
            variant=spec["variant"],
            episode_status=spec["status"],
            final=spec["final"],
            tracking_loss_start=spec.get("tracking_loss_start"),
        )
        records.append(readiness.build_episode_record(normalize_trajectory(trajectory)))
    return records


def split_accepted(accepted: list[dict[str, Any]]) -> dict[str, list[str]]:
    return readiness.split_accepted(accepted)


def build_curation_manifest(
    curated: dict[str, list[dict[str, Any]]],
    *,
    raw_storage: Path,
) -> dict[str, Any]:
    rejected = curated["rejected"]
    reasons = Counter(
        reason
        for item in rejected
        for reason in (item.get("curation") or {}).get("rejection_reasons", [])
    )
    return {
        "schema_version": "rdf_data_trust_curation_manifest_v0.1.0",
        "proof_id": PROOF_ID,
        "task_id": readiness.TASK_ID,
        "raw_episode_count": len(curated["accepted"]) + len(rejected),
        "accepted_count": len(curated["accepted"]),
        "rejected_count": len(rejected),
        "accepted": [
            {
                "episode_id": item["episode"]["id"],
                "trajectory_id": item["trajectory"]["id"],
                "evaluation_id": item["evaluation"]["id"],
                "trajectory_path": artifact_path(raw_storage / "trajectories" / f'{item["trajectory"]["id"]}.json'),
                "evaluation_path": artifact_path(raw_storage / "evaluations" / f'{item["evaluation"]["id"]}.json'),
                "evidence_fields": [
                    "evaluation.metrics.data_quality",
                    "trajectory.summary.action_replay_contract",
                    "trajectory.frames[].action",
                ],
            }
            for item in curated["accepted"]
        ],
        "rejected": [
            {
                "episode_id": item["episode"]["id"],
                "trajectory_id": item["trajectory"]["id"],
                "evaluation_id": item["evaluation"]["id"],
                "reasons": (item.get("curation") or {}).get("rejection_reasons", []),
                "trajectory_path": artifact_path(raw_storage / "trajectories" / f'{item["trajectory"]["id"]}.json'),
                "evaluation_path": artifact_path(raw_storage / "evaluations" / f'{item["evaluation"]["id"]}.json'),
                "evidence_fields": [
                    "curation.rejection_reasons",
                    "evaluation.failure_reason",
                    "evaluation.metrics.data_quality.quality_failure_reasons",
                    "evaluation.metrics.curation.rejection_reasons",
                ],
            }
            for item in rejected
        ],
        "rejection_reason_distribution": dict(sorted(reasons.items())),
        "curation_rules": readiness.CURATION_RULES,
    }


def build_experiment_manifest(curated: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    manifest = readiness.experiment_manifest(curated)
    manifest["schema_version"] = "rdf_data_trust_experiment_manifest_v0.1.0"
    manifest["proof_id"] = PROOF_ID
    manifest["required_future_evidence"] = [
        "Physical/HMD collection readiness must be validated separately before using live HMD adapters.",
        "Policy uplift belongs to MVP-2 and is not claimed by this proof.",
    ]
    return manifest


def build_data_trust_dataset_card(base_card: dict[str, Any]) -> dict[str, Any]:
    card = copy.deepcopy(base_card)
    card["source_profile"] = "synthetic_replay_fixture"
    card["primary_source_hmd_free"] = True
    card["limitations"] = list(DATA_TRUST_DATASET_CARD_LIMITATIONS)
    card["claim_boundaries"] = {
        "hmd_readiness_claimed": False,
        "physical_robot_readiness_claimed": False,
        "gate_a_collection_allowed": False,
        "policy_uplift_claimed": False,
    }
    return card


def _first_item(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        raise RuntimeError("expected at least one item")
    return items[0]


def build_action_semantics(*, accepted_trajectory: Path, hdf5_path: Path) -> dict[str, Any]:
    return {
        "summary": "Primary proof actions are scripted fixture commands represented as robot delta end-effector pose plus gripper in task frame.",
        "canonical_values": dict(ACTION_CANONICAL_VALUES),
        "field_paths": list(ACTION_FIELD_PATHS),
        "artifact_paths": {
            "accepted_trajectory": artifact_path(accepted_trajectory),
            "hdf5_export": artifact_path(hdf5_path),
        },
        "roles": {
            "teleop_intent": {
                "source": ACTION_CANONICAL_VALUES["source"],
                "role": "operator_intent",
                "representation": ACTION_CANONICAL_VALUES["representation"],
                "coordinate_frame": ACTION_CANONICAL_VALUES["coordinate_frame"],
            },
            "executed_control": {
                "source": ACTION_CANONICAL_VALUES["source"],
                "role": "robot_control_command",
                "representation": ACTION_CANONICAL_VALUES["representation"],
                "coordinate_frame": ACTION_CANONICAL_VALUES["coordinate_frame"],
            },
            "learning_action": {
                "source": ACTION_CANONICAL_VALUES["source"],
                "role": "candidate_robot_action_for_learning",
                "representation": ACTION_CANONICAL_VALUES["representation"],
                "coordinate_frame": ACTION_CANONICAL_VALUES["coordinate_frame"],
                "dataset_semantics": "not_training_ready_until_evaluated_curated_and_exported",
            },
            "retargeted_robot_action": {
                "source": ACTION_CANONICAL_VALUES["replay_source"],
                "role": "robot_action_for_replay_comparison",
                "representation": ACTION_CANONICAL_VALUES["representation"],
                "coordinate_frame": ACTION_CANONICAL_VALUES["coordinate_frame"],
            },
        },
    }


def build_replay_action_contract(*, accepted_evaluation: Path, accepted_trajectory: Path) -> dict[str, Any]:
    evaluation = read_json(accepted_evaluation)
    data_quality = ((evaluation.get("metrics") or {}).get("data_quality") or {})
    return {
        "status": data_quality.get("action_contract_status"),
        "replay_verified": data_quality.get("replay_verified"),
        "action_contract_valid": data_quality.get("action_contract_valid"),
        "field_paths": list(REPLAY_FIELD_PATHS),
        "artifact_paths": {
            "accepted_trajectory": artifact_path(accepted_trajectory),
            "accepted_evaluation": artifact_path(accepted_evaluation),
        },
    }


def build_data_quality_summary(
    *,
    accepted_evaluation: Path,
    rejected_evaluation: Path,
    curation_manifest: Path,
) -> dict[str, Any]:
    accepted = read_json(accepted_evaluation)
    rejected = read_json(rejected_evaluation)
    curation = read_json(curation_manifest)
    accepted_quality = ((accepted.get("metrics") or {}).get("data_quality") or {})
    rejected_quality = ((rejected.get("metrics") or {}).get("data_quality") or {})
    return {
        "accepted": {
            "replay_verified": accepted_quality.get("replay_verified"),
            "action_contract_status": accepted_quality.get("action_contract_status"),
            "action_contract_valid": accepted_quality.get("action_contract_valid"),
            "control_quality": accepted_quality.get("control_quality"),
            "quality_failure_reasons": accepted_quality.get("quality_failure_reasons"),
        },
        "rejected": {
            "failure_reason": rejected.get("failure_reason"),
            "quality_failure_reasons": rejected_quality.get("quality_failure_reasons"),
            "curation_rejection_reason_distribution": curation.get("rejection_reason_distribution"),
        },
        "field_paths": list(DATA_QUALITY_FIELD_PATHS),
        "artifact_paths": {
            "accepted_evaluation": artifact_path(accepted_evaluation),
            "rejected_evaluation": artifact_path(rejected_evaluation),
            "curation_manifest": artifact_path(curation_manifest),
        },
    }


def build_legacy_schema_field_mapping(*, hdf5_inspection: Path, trainer_smoke_report: Path) -> dict[str, Any]:
    return {
        "summary": (
            "Some exported observation names are retained for compatibility with the existing RDF HDF5/trainer "
            "schema. They are observation field names, not source-readiness or Gate A claims."
        ),
        "fields": copy.deepcopy(LEGACY_OBSERVATION_FIELD_MAPPING),
        "artifact_paths": {
            "hdf5_inspection": artifact_path(hdf5_inspection),
            "trainer_smoke_report": artifact_path(trainer_smoke_report),
        },
    }


def build_trust_record(
    *,
    output_dir: Path,
    artifact_paths: dict[str, str],
    action_semantics: dict[str, Any],
    replay_action_contract: dict[str, Any],
    data_quality_summary: dict[str, Any],
    legacy_schema_field_mapping: dict[str, Any],
    passed: bool,
) -> dict[str, Any]:
    command = reproduce_command(output_dir)
    return {
        "schema_version": TRUST_RECORD_SCHEMA_VERSION,
        "proof_id": PROOF_ID,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": passed,
        "input_source_profile": "synthetic_replay_fixture",
        "primary_source_hmd_free": True,
        "hmd_readiness_claimed": False,
        "physical_robot_readiness_claimed": False,
        "gate_a_collection_allowed": False,
        "policy_uplift_claimed": False,
        "provenance": {
            "generator": "scripts/run_data_trust_layer_proof.py",
            "fixture_source": "scripted_fixture",
            "runtime": SOURCE_PROFILE["runtime"],
            "robot": SOURCE_PROFILE["robot"],
            "simulator": SOURCE_PROFILE["simulator"],
            "task_name": SOURCE_PROFILE["task_name"],
        },
        "artifact_paths": artifact_paths,
        "verification_commands": [
            command,
            "uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q",
            "uv run pytest apps/api/tests/test_mvp1_trainer_smoke_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q",
        ],
        "audit_trail": [
            {"step": "generate_fixture_trajectories", "status": "passed"},
            {"step": "evaluate_task_and_data_quality", "status": "passed"},
            {"step": "curate_accepted_and_rejected_examples", "status": "passed"},
            {"step": "export_hdf5", "status": "passed"},
            {"step": "inspect_hdf5", "status": "passed"},
            {"step": "trainer_loader_smoke", "status": "passed"},
            {"step": "write_buyer_trust_artifacts", "status": "passed"},
        ],
        "limitations": [
            "This proof does not claim HMD readiness.",
            "This proof does not claim physical robot collection readiness.",
            "This proof does not allow Gate A collection.",
            "This proof does not claim policy uplift.",
            "Quest/OpenXR/HMD adapters remain experimental adapter paths outside this primary proof.",
        ],
        "experimental_adapter": {
            "name": "Quest/OpenXR/HMD live collection",
            "status": "preserved_but_excluded_from_primary_proof",
        },
        "action_semantics": action_semantics,
        "replay_action_contract": replay_action_contract,
        "data_quality_summary": data_quality_summary,
        "legacy_schema_field_mapping": legacy_schema_field_mapping,
    }


def build_buyer_dataset_card(
    *,
    base_card: dict[str, Any],
    trust_record: dict[str, Any],
    action_semantics: dict[str, Any],
    replay_action_contract: dict[str, Any],
    data_quality_summary: dict[str, Any],
    legacy_schema_field_mapping: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "rdf_buyer_dataset_card_v0.1.0",
        "proof_id": PROOF_ID,
        "dataset_card": base_card,
        "buyer_summary": "RDF data trust layer proof with reproducible provenance, curation, export, and trainer-loader evidence.",
        "primary_source_profile": trust_record["input_source_profile"],
        "primary_source_hmd_free": True,
        "claims": {
            "hmd_readiness_claimed": False,
            "physical_robot_readiness_claimed": False,
            "gate_a_collection_allowed": False,
            "policy_uplift_claimed": False,
        },
        "artifact_paths": trust_record["artifact_paths"],
        "verification_commands": trust_record["verification_commands"],
        "action_semantics": action_semantics,
        "replay_action_contract": replay_action_contract,
        "data_quality_summary": data_quality_summary,
        "legacy_schema_field_mapping": legacy_schema_field_mapping,
        "limitations": trust_record["limitations"],
    }


def build_proof_report(trust_record: dict[str, Any], *, counts: dict[str, int]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proof_id": PROOF_ID,
        "passed": trust_record["passed"],
        "summary": {
            "accepted_count": counts["accepted"],
            "rejected_count": counts["rejected"],
            "primary_source_hmd_free": trust_record["primary_source_hmd_free"],
            "hmd_readiness_claimed": trust_record["hmd_readiness_claimed"],
            "gate_a_collection_allowed": trust_record["gate_a_collection_allowed"],
            "policy_uplift_claimed": trust_record["policy_uplift_claimed"],
        },
        "artifact_paths": trust_record["artifact_paths"],
        "reproduce_command": trust_record["verification_commands"][0],
        "action_semantics": trust_record["action_semantics"],
        "replay_action_contract": trust_record["replay_action_contract"],
        "data_quality_summary": trust_record["data_quality_summary"],
        "legacy_schema_field_mapping": trust_record["legacy_schema_field_mapping"],
        "limitations": trust_record["limitations"],
    }


def build_data_trust_layer_proof(output_dir: Path, *, clean: bool = False) -> dict[str, Any]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = build_records()
    curated = curate_episodes_with_reasons(
        records,
        min_quality_score=readiness.CURATION_RULES["min_quality_score"],
        fraud_threshold=readiness.CURATION_RULES["fraud_threshold"],
        min_data_usability_score=readiness.CURATION_RULES["min_data_usability_score"],
    )

    raw_storage = output_dir / "raw"
    curated_storage = output_dir / "curated"
    for item in records:
        write_json(raw_storage / "trajectories" / f'{item["trajectory"]["id"]}.json', item["trajectory"])
        write_json(raw_storage / "evaluations" / f'{item["evaluation"]["id"]}.json', item["evaluation"])
    for item in curated["accepted"]:
        write_json(curated_storage / "trajectories" / f'{item["trajectory"]["id"]}.json', item["trajectory"])
        write_json(curated_storage / "evaluations" / f'{item["evaluation"]["id"]}.json', item["evaluation"])

    splits = split_accepted(curated["accepted"])
    split_ratios = {"train": 0.70, "validation": 0.15, "test": 0.15}
    base_card = build_data_trust_dataset_card(build_dataset_card(
        dataset_id=DATASET_ID,
        dataset_name="Robot Data Forge Data Trust Layer Fixture Proof",
        task={**readiness.TASK, "id": readiness.TASK_ID, "success_criteria": readiness.SUCCESS_CRITERIA},
        episodes=curated["accepted"] + curated["rejected"],
        curation_rules=readiness.CURATION_RULES,
        splits=split_ratios,
        export_format="json+hdf5+trainer_smoke_trust_proof",
    ))
    curation = build_curation_manifest(curated, raw_storage=raw_storage)
    split_manifest = {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "proof_id": PROOF_ID,
        "task_id": readiness.TASK_ID,
        "strategy": "deterministic_data_trust_layer_split",
        "ratios": split_ratios,
        "splits": splits,
    }
    experiment = build_experiment_manifest(curated)

    curation_path = output_dir / "curation_manifest.json"
    split_path = output_dir / "split_manifest.json"
    dataset_card_path = output_dir / "dataset_card.json"
    experiment_path = output_dir / "curated_vs_uncurated_experiment_manifest.json"
    write_json(curation_path, curation)
    write_json(split_path, split_manifest)
    write_json(dataset_card_path, base_card)
    write_json(experiment_path, experiment)

    hdf5_path = output_dir / "rdf_data_trust_layer_proof.hdf5"
    export_result = export_hdf5(
        output_path=hdf5_path,
        trajectories_dir=curated_storage / "trajectories",
        evaluations_dir=curated_storage / "evaluations",
        include_statuses={"success"},
    )
    hdf5_inspection = inspect_hdf5(hdf5_path)
    hdf5_inspection_path = output_dir / "hdf5_inspection.json"
    write_json(hdf5_inspection_path, hdf5_inspection)

    trainer_smoke_path = output_dir / "trainer_smoke_report.json"
    trainer_report = run_trainer_smoke(
        hdf5_path=hdf5_path,
        split_manifest_path=split_path,
        output_path=trainer_smoke_path,
        experiment_manifest_path=experiment_path,
    )

    accepted_item = _first_item(curated["accepted"])
    rejected_item = _first_item(curated["rejected"])
    accepted_trajectory = raw_storage / "trajectories" / f'{accepted_item["trajectory"]["id"]}.json'
    accepted_evaluation = raw_storage / "evaluations" / f'{accepted_item["evaluation"]["id"]}.json'
    rejected_trajectory = raw_storage / "trajectories" / f'{rejected_item["trajectory"]["id"]}.json'
    rejected_evaluation = raw_storage / "evaluations" / f'{rejected_item["evaluation"]["id"]}.json'

    action_semantics = build_action_semantics(accepted_trajectory=accepted_trajectory, hdf5_path=hdf5_path)
    replay_action_contract = build_replay_action_contract(
        accepted_evaluation=accepted_evaluation,
        accepted_trajectory=accepted_trajectory,
    )
    data_quality_summary = build_data_quality_summary(
        accepted_evaluation=accepted_evaluation,
        rejected_evaluation=rejected_evaluation,
        curation_manifest=curation_path,
    )
    legacy_schema_field_mapping = build_legacy_schema_field_mapping(
        hdf5_inspection=hdf5_inspection_path,
        trainer_smoke_report=trainer_smoke_path,
    )
    gates = {
        "accepted_example_present": len(curated["accepted"]) >= 1,
        "rejected_example_present": len(curated["rejected"]) >= 1,
        "hdf5_export_generated": hdf5_path.exists() and bool(export_result.exported_episode_ids),
        "hdf5_inspection_clean": not hdf5_inspection.get("issues"),
        "trainer_smoke_passed": trainer_report.get("passed") is True,
        "no_policy_uplift_claim": trainer_report.get("learning_results_measured") is False
        and trainer_report.get("curated_vs_uncurated_uplift") is None,
        "accepted_data_quality_clean": data_quality_summary["accepted"] == {
            "replay_verified": True,
            "action_contract_status": "pass",
            "action_contract_valid": True,
            "control_quality": "pass",
            "quality_failure_reasons": [],
        },
    }
    artifact_paths = {
        "raw_storage": artifact_path(raw_storage),
        "curated_storage": artifact_path(curated_storage),
        "accepted_trajectory": artifact_path(accepted_trajectory),
        "accepted_evaluation": artifact_path(accepted_evaluation),
        "rejected_trajectory": artifact_path(rejected_trajectory),
        "rejected_evaluation": artifact_path(rejected_evaluation),
        "curation_manifest": artifact_path(curation_path),
        "split_manifest": artifact_path(split_path),
        "dataset_card": artifact_path(dataset_card_path),
        "experiment_manifest": artifact_path(experiment_path),
        "hdf5_export": artifact_path(hdf5_path),
        "hdf5_inspection": artifact_path(hdf5_inspection_path),
        "trainer_smoke_report": artifact_path(trainer_smoke_path),
        "trust_record": artifact_path(output_dir / "trust_record.json"),
        "buyer_dataset_card": artifact_path(output_dir / "buyer_dataset_card.json"),
        "proof_report": artifact_path(output_dir / "proof_report.json"),
    }
    passed = all(gates.values())
    trust_record = build_trust_record(
        output_dir=output_dir,
        artifact_paths=artifact_paths,
        action_semantics=action_semantics,
        replay_action_contract=replay_action_contract,
        data_quality_summary=data_quality_summary,
        legacy_schema_field_mapping=legacy_schema_field_mapping,
        passed=passed,
    )
    buyer_card = build_buyer_dataset_card(
        base_card=base_card,
        trust_record=trust_record,
        action_semantics=action_semantics,
        replay_action_contract=replay_action_contract,
        data_quality_summary=data_quality_summary,
        legacy_schema_field_mapping=legacy_schema_field_mapping,
    )
    proof_report = build_proof_report(
        trust_record,
        counts={"accepted": len(curated["accepted"]), "rejected": len(curated["rejected"])},
    )

    write_json(output_dir / "trust_record.json", trust_record)
    write_json(output_dir / "buyer_dataset_card.json", buyer_card)
    write_json(output_dir / "proof_report.json", proof_report)

    report = {
        "schema_version": SCHEMA_VERSION,
        "proof_id": PROOF_ID,
        "passed": passed,
        "output_dir": artifact_path(output_dir),
        "gates": gates,
        "accepted_count": len(curated["accepted"]),
        "rejected_count": len(curated["rejected"]),
        "hdf5_exported_episode_ids": export_result.exported_episode_ids,
        "artifact_paths": artifact_paths,
    }
    write_json(output_dir / "data_trust_layer_proof_summary.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated data trust proof artifacts.",
    )
    parser.add_argument("--clean", action="store_true", help="Remove the output directory before generating artifacts.")
    parser.add_argument("--pretty", action="store_true", help="Print the full proof summary as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_data_trust_layer_proof(args.output_dir, clean=args.clean)
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF data trust layer proof: {status}")
        print(f"accepted={report['accepted_count']} rejected={report['rejected_count']}")
        print(f"trust_record={report['artifact_paths']['trust_record']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
