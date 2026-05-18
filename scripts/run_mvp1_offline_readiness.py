#!/usr/bin/env python3
"""Build a CLI-only MVP-1 peg-in-hole readiness bundle.

This script intentionally uses synthetic/offline trajectories. It validates
the backend data contracts for MVP-1 without claiming live HMD evidence or
measured policy uplift.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
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
from app.services.evaluator import add_evaluation_semantics, evaluate_trajectory  # noqa: E402
from app.services.segmentation import segment_actions  # noqa: E402
from app.services.sync import compute_sync_metrics  # noqa: E402
from app.services.usability import compute_data_usability  # noqa: E402
from export_rdf_to_hdf5 import export_hdf5  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402


SCHEMA_VERSION = "rdf_mvp1_offline_readiness_v0.1.0"
TASK_ID = "task_mvp1_peg_in_hole_offline"
DATASET_ID = "dataset_mvp1_peg_in_hole_offline_readiness"
PHASE_SEQUENCE = ("APPROACH", "ALIGN", "CONTACT", "INSERT", "SEAT", "RELEASE")
SUCCESS_CRITERIA = {
    "task_type": "peg_in_hole",
    "peg_tip_distance_to_target_max": 0.015,
    "peg_axis_alignment_error_max_rad": 0.25,
    "insertion_depth_min": 0.025,
    "min_stable_steps": 4,
    "max_completion_time_sec": 45.0,
    "max_tracking_loss_after_warmup": 0.25,
    "max_retargeting_jump": 1.50,
    "max_average_input_latency_ms": 80.0,
    "max_frame_interval_jitter_ms": 25.0,
    "max_collision_count": 1,
}
TASK = {
    "id": TASK_ID,
    "task_type": "peg_in_hole",
    "description": "Offline MVP-1 peg-in-hole readiness fixture for evaluator, curator, export, and split contracts.",
    "environment_config": {
        "task_type": "peg_in_hole",
        "robot": "franka",
        "simulator": "isaac_lab",
        "fixture_source": "synthetic_offline_readiness",
    },
    "success_criteria": SUCCESS_CRITERIA,
}
REPLAY_CONTRACT = {
    "schema_version": "rdf_action_replay_contract_v0.1.0",
    "name": "mvp1_offline_fixture_recorded_action_replay",
    "task": "Isaac-Forge-PegInsert-Direct-v0",
    "replay_mode": "native_direct",
    "action_field": "retargeted_robot_action",
    "initial_state": {
        "type": "isaac_reset_seed",
        "seed": 202506,
        "reason": "Synthetic readiness fixtures are open-loop and only replay-valid from their deterministic fixture initial state.",
    },
    "repeat": 1,
}
SOURCE = {
    "input_device": "quest3_handtracking",
    "runtime": "steamvr_openxr",
    "simulator": "isaac_lab",
    "robot": "franka",
    "task_name": "peg_in_hole_mvp1_offline_readiness",
}
CURATION_RULES = {
    "min_quality_score": 0.65,
    "fraud_threshold": 0.30,
    "min_data_usability_score": 0.70,
    "require_success_status": True,
    "require_evaluator_success": True,
    "require_replayable": True,
    "duplicate_threshold": 0.03,
}


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def phase_state(phase: str, phase_step: int, *, final: dict[str, Any]) -> dict[str, Any]:
    baseline = {
        "APPROACH": (0.080, 0.45, 0.000),
        "ALIGN": (0.034, 0.18, 0.000),
        "CONTACT": (0.018, 0.12, 0.006),
        "INSERT": (0.010, 0.08, 0.020),
        "SEAT": (final["distance"], final["alignment"], final["depth"]),
        "RELEASE": (final["distance"], final["alignment"], final["depth"]),
    }
    distance, alignment, depth = baseline[phase]
    if phase == "INSERT":
        depth += phase_step * 0.002
    return {
        "peg_tip_distance_to_target": distance,
        "axis_alignment_error_rad": alignment,
        "insertion_depth": depth,
        "contact_sequence_valid": bool(final.get("contact_sequence_valid", True)),
        "object_drop_detected": bool(final.get("object_drop_detected", False)),
    }


def path_offset(variant: int, step: int, total_steps: int) -> list[float]:
    progress = step / max(total_steps - 1, 1)
    patterns = (
        (0.000, 0.000, 0.000),
        (0.020 * progress, 0.025 * (1.0 - abs(0.5 - progress) * 2), 0.002),
        (-0.018 * progress, -0.020 * (1.0 - abs(0.5 - progress) * 2), -0.001),
        (0.012 * (1.0 - progress), 0.035 * ((step % 3) - 1) / 2.0, 0.003 * progress),
    )
    return list(patterns[variant % len(patterns)])


def build_frame(
    *,
    step: int,
    total_steps: int,
    phase: str,
    phase_step: int,
    variant: int,
    final: dict[str, Any],
    tracking_loss: bool = False,
) -> dict[str, Any]:
    t = step * 0.05
    offset = path_offset(variant, step, total_steps)
    state = phase_state(phase, phase_step, final=final)
    object_position = [
        0.45 + step * 0.004 + offset[0],
        0.08 + offset[1],
        0.04 + min(state["insertion_depth"], 0.035) + offset[2],
    ]
    ee_position = [
        object_position[0] + 0.035,
        object_position[1] - 0.010,
        object_position[2] + 0.045,
    ]
    action_command = [
        0.006 + 0.0005 * variant,
        offset[1] * 0.05,
        min(state["insertion_depth"], 0.04) * 0.20,
        0.0,
        0.0,
        max(0.0, 0.06 - state["axis_alignment_error_rad"] * 0.05),
        1.0 if phase in {"CONTACT", "INSERT", "SEAT"} else 0.0,
    ]
    raw_action = [value * 1.15 for value in action_command]
    hand_tracked = not tracking_loss
    return {
        "t": t,
        "step": step,
        "end_effector_position": ee_position,
        "end_effector_quaternion": [1.0, 0.0, 0.0, 0.0],
        "object_position": object_position,
        "object_quaternion": [1.0, 0.0, 0.0, 0.0],
        "action": {
            "raw": raw_action,
            "applied": action_command,
            "teleop_intent": {
                "command": raw_action,
                "role": "operator_intent",
                "representation": "openxr_retargeted_delta_ee_pose_plus_gripper",
                "source": "offline_mvp1_readiness_fixture",
                "coordinate_frame": "openxr_retargeter_output",
            },
            "executed_control": {
                "command": action_command,
                "role": "robot_control_command",
                "representation": "delta_ee_pose_plus_gripper",
                "source": "offline_fixture_controller",
                "control_mode": "offline_fixture_operator_follow",
                "control_semantics": "operator_workspace_target_following",
                "applied_to_env": True,
            },
            "learning_action": {
                "command": action_command,
                "role": "candidate_robot_action_for_learning",
                "representation": "delta_ee_pose_plus_gripper",
                "source": "executed_control",
                "validation_state": "requires_evaluation_and_curation",
                "dataset_semantics": "not_learning_ready_until_curated",
            },
            "retargeted_robot_action": {
                "command": action_command,
                "action_type": "delta_ee_pose_plus_gripper",
            },
        },
        "contacts": [{"body_a": "peg", "body_b": "hole_chamfer"}] if phase in {"CONTACT", "INSERT", "SEAT"} else [],
        "metadata": {
            "action_phase": phase,
            "right_hand_tracked": hand_tracked,
            "xr_frame_valid": hand_tracked,
            "input_latency_ms": 24.0 if hand_tracked else 65.0,
            "sim_fps": 20.0,
            "sync_error_ms": 4.0,
            "timestamp_source": "recorder_monotonic",
            "teleop_pipeline": {
                "schema_version": "rdf_xr_teleop_dataset_pipeline_v0.1.0",
                "product_role": "xr_teleop_trajectory_to_validated_learning_dataset",
                "teleop_intent_field": "action.teleop_intent",
                "executed_control_field": "action.executed_control",
                "learning_action_field": "action.learning_action",
                "learning_action_status": "candidate_requires_evaluation_and_curation",
                "control_mode": "offline_fixture_operator_follow",
                "control_semantics": "operator_workspace_target_following",
            },
            "raw_xr": {
                "right_wrist_pose": [
                    0.10 + step * 0.003,
                    0.20 + offset[1],
                    0.30 + state["insertion_depth"],
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            },
            "aligned_xr": {
                "right_wrist_pose": [
                    ee_position[0],
                    ee_position[1],
                    ee_position[2],
                    1.0,
                    0.0,
                    0.0,
                    0.0,
                ],
            },
            "retargeted": {
                "raw_robot_action": raw_action,
                "robot_action": action_command,
            },
            "task_state": state,
        },
    }


def build_trajectory(
    name: str,
    *,
    variant: int,
    episode_status: str,
    final: dict[str, Any],
    replayable: bool = True,
    tracking_loss_start: int | None = None,
) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    step = 0
    frames_per_phase = 4
    total_steps = frames_per_phase * len(PHASE_SEQUENCE)
    for phase in PHASE_SEQUENCE:
        for phase_step in range(frames_per_phase):
            frames.append(
                build_frame(
                    step=step,
                    total_steps=total_steps,
                    phase=phase,
                    phase_step=phase_step,
                    variant=variant,
                    final=final,
                    tracking_loss=tracking_loss_start is not None and step >= tracking_loss_start,
                )
            )
            step += 1

    episode_id = f"episode_{name}"
    trajectory_id = f"traj_{name}"
    return {
        "id": trajectory_id,
        "episode_id": episode_id,
        "task_id": TASK_ID,
        "schema_version": "0.1.0",
        "source": SOURCE,
        "frames": frames,
        "summary": {
            "duration_sec": frames[-1]["t"] - frames[0]["t"],
            "episode_status": episode_status,
            "episode_started_at": "2026-05-07T00:00:00+00:00",
            "episode_finalized_at": "2026-05-07T00:00:02+00:00",
            "episode_finalize_reason": f"offline_{episode_status}",
            "episode_failure_reason": None if episode_status == "success" else "OFFLINE_FIXTURE_FAILURE",
            "episode_failure_note": "Synthetic/offline MVP-1 readiness fixture.",
            "reset_count": 0,
            "collision_count": int(final.get("collision_count", 0)),
            "replayable": replayable,
            "task_type": "peg_in_hole",
            "task_state_source": "synthetic_offline_readiness",
            "action_replay_contract": REPLAY_CONTRACT,
        },
    }


def fixture_specs() -> list[dict[str, Any]]:
    success_final = {"distance": 0.006, "alignment": 0.05, "depth": 0.033, "contact_sequence_valid": True}
    return [
        {"name": "success_a", "variant": 0, "status": "success", "final": success_final},
        {"name": "success_b", "variant": 1, "status": "success", "final": success_final},
        {"name": "success_c", "variant": 2, "status": "success", "final": success_final},
        {"name": "success_d", "variant": 3, "status": "success", "final": success_final},
        {"name": "duplicate_success_a", "variant": 0, "status": "success", "final": success_final},
        {
            "name": "alignment_failure",
            "variant": 1,
            "status": "failure",
            "final": {"distance": 0.006, "alignment": 0.42, "depth": 0.033, "contact_sequence_valid": True},
        },
        {
            "name": "depth_failure",
            "variant": 2,
            "status": "failure",
            "final": {"distance": 0.006, "alignment": 0.05, "depth": 0.010, "contact_sequence_valid": True},
        },
        {
            "name": "tracking_loss_failure",
            "variant": 3,
            "status": "success",
            "final": success_final,
            "tracking_loss_start": 12,
        },
    ]


def evaluation_payload(trajectory: dict[str, Any]) -> dict[str, Any]:
    result = evaluate_trajectory(
        {**TASK["environment_config"], "task_type": TASK["task_type"]},
        SUCCESS_CRITERIA,
        trajectory,
    )
    payload = asdict(result)
    suffix = trajectory["id"].removeprefix("traj_")
    payload.update(
        {
            "id": f"eval_{suffix}",
            "trajectory_id": trajectory["id"],
            "episode_id": trajectory["episode_id"],
            "task_id": TASK_ID,
            "schema_version": "evaluation_v0.2.0",
        }
    )
    return payload


def build_episode_record(trajectory: dict[str, Any]) -> dict[str, Any]:
    evaluation = evaluation_payload(trajectory)
    sync_metrics = compute_sync_metrics(trajectory)
    replayable = bool((trajectory.get("summary") or {}).get("replayable", True))
    episode_status = str((trajectory.get("summary") or {}).get("episode_status") or "unknown")
    data_usability = compute_data_usability(
        trajectory,
        evaluation,
        sync_metrics,
        replayable=replayable,
        episode_status=episode_status,
    )
    evaluation["data_usability_score"] = data_usability["score"]
    evaluation["metrics"] = add_evaluation_semantics(
        {
            **(evaluation.get("metrics") if isinstance(evaluation.get("metrics"), dict) else {}),
            "sync_metrics": sync_metrics,
            "data_usability": data_usability,
        },
        trajectory,
        success=evaluation.get("success") is True,
        failure_reason=evaluation.get("failure_reason"),
        failure_category=evaluation.get("failure_category"),
        evaluator_confidence=evaluation.get("evaluator_confidence"),
        data_usability=data_usability,
    )
    segments = segment_actions(trajectory)
    summary = trajectory.setdefault("summary", {})
    summary["sync_metrics"] = sync_metrics
    summary["data_usability"] = data_usability
    summary["action_segments"] = segments
    return {
        "episode": {
            "id": trajectory["episode_id"],
            "task_id": TASK_ID,
            "status": episode_status,
            "trajectory_id": trajectory["id"],
            "evaluation_id": evaluation["id"],
            "replayable": replayable,
            "usable": data_usability["usable"],
            "data_usability_score": data_usability["score"],
        },
        "trajectory": trajectory,
        "evaluation": evaluation,
        "sync_metrics": sync_metrics,
        "data_usability": data_usability,
        "action_segments": segments,
    }


def split_accepted(accepted: list[dict[str, Any]]) -> dict[str, list[str]]:
    ids = [item["episode"]["id"] for item in accepted]
    if len(ids) >= 4:
        return {"train": ids[:2], "validation": ids[2:3], "test": ids[3:4]}
    if len(ids) == 3:
        return {"train": ids[:1], "validation": ids[1:2], "test": ids[2:3]}
    if len(ids) == 2:
        return {"train": ids[:1], "validation": [], "test": ids[1:2]}
    return {"train": ids, "validation": [], "test": []}


def curation_manifest(curated: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rejected = curated["rejected"]
    reasons = Counter(
        reason
        for item in rejected
        for reason in (item.get("curation") or {}).get("rejection_reasons", [])
    )
    return {
        "schema_version": "rdf_curation_manifest_v0.1.0",
        "task_id": TASK_ID,
        "raw_episode_count": len(curated["accepted"]) + len(rejected),
        "accepted_count": len(curated["accepted"]),
        "rejected_count": len(rejected),
        "accepted_episode_ids": [item["episode"]["id"] for item in curated["accepted"]],
        "rejected": [
            {
                "episode_id": item["episode"]["id"],
                "trajectory_id": item["trajectory"]["id"],
                "reasons": (item.get("curation") or {}).get("rejection_reasons", []),
            }
            for item in rejected
        ],
        "rejection_reason_distribution": dict(sorted(reasons.items())),
        "curation_rules": CURATION_RULES,
    }


def experiment_manifest(curated: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    raw_success_ids = [
        item["episode"]["id"]
        for item in curated["accepted"] + curated["rejected"]
        if item["episode"]["status"] == "success"
    ]
    accepted_ids = [item["episode"]["id"] for item in curated["accepted"]]
    return {
        "schema_version": "rdf_curated_vs_uncurated_experiment_manifest_v0.1.0",
        "task_id": TASK_ID,
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "training_readiness": {
            "loader_smoke_passed": False,
            "trainer_dry_run_passed": False,
            "one_epoch_smoke_passed": False,
            "policy_class": None,
            "trainer": None,
        },
        "baseline_a_uncurated_success_lifecycle_episode_ids": raw_success_ids,
        "baseline_b_curated_accepted_episode_ids": accepted_ids,
        "required_future_evidence": [
            "Run exported dataset through a real trainer loader plus dry-run or one epoch smoke.",
            "Train the same policy class on uncurated lifecycle-success data and curated accepted data.",
            "Evaluate both on held-out pose/clearance/connector variants.",
            "Report success-rate delta with confidence interval; do not fill uplift before measurement.",
        ],
    }


def build_bundle(output_dir: Path, *, clean: bool = False) -> dict[str, Any]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = [
        build_episode_record(
            build_trajectory(
                spec["name"],
                variant=spec["variant"],
                episode_status=spec["status"],
                final=spec["final"],
                tracking_loss_start=spec.get("tracking_loss_start"),
            )
        )
        for spec in fixture_specs()
    ]
    curated = curate_episodes_with_reasons(
        records,
        min_quality_score=CURATION_RULES["min_quality_score"],
        fraud_threshold=CURATION_RULES["fraud_threshold"],
        min_data_usability_score=CURATION_RULES["min_data_usability_score"],
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
    card = build_dataset_card(
        dataset_id=DATASET_ID,
        dataset_name="Robot Data Forge MVP-1 Peg-In-Hole Offline Readiness",
        task={**TASK, "success_criteria": SUCCESS_CRITERIA},
        episodes=curated["accepted"] + curated["rejected"],
        curation_rules=CURATION_RULES,
        splits=split_ratios,
        export_format="json+hdf5_readiness",
    )
    manifest = curation_manifest(curated)
    split_manifest = {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "task_id": TASK_ID,
        "strategy": "deterministic_readiness_split",
        "ratios": split_ratios,
        "splits": splits,
        "held_out_definition": "MVP-1 live validation must replace this fixture with held-out pose/clearance/connector variants.",
    }
    learning_manifest = experiment_manifest(curated)

    write_json(output_dir / "curation_manifest.json", manifest)
    write_json(output_dir / "split_manifest.json", split_manifest)
    write_json(output_dir / "dataset_card.json", card)
    write_json(output_dir / "curated_vs_uncurated_experiment_manifest.json", learning_manifest)

    hdf5_path = output_dir / "rdf_mvp1_curated_readiness.hdf5"
    export_result = export_hdf5(
        output_path=hdf5_path,
        trajectories_dir=curated_storage / "trajectories",
        evaluations_dir=curated_storage / "evaluations",
        include_statuses={"success"},
    )
    hdf5_inspection = inspect_hdf5(hdf5_path)
    write_json(output_dir / "hdf5_inspection.json", hdf5_inspection)

    phase_coverage = sorted(
        {
            segment["phase"]
            for item in records
            for segment in item["action_segments"]
        }
    )
    required_phases = set(PHASE_SEQUENCE)
    evaluator_failure_reasons = Counter(
        item["evaluation"]["failure_reason"]
        for item in records
        if item["evaluation"].get("failure_reason")
    )
    readiness_gates = {
        "accepted_episode_minimum_met": len(curated["accepted"]) >= 4,
        "rejected_episode_examples_present": len(curated["rejected"]) >= 3,
        "required_phase_coverage_met": required_phases.issubset(set(phase_coverage)),
        "dataset_card_generated": True,
        "split_manifest_generated": True,
        "curated_vs_uncurated_manifest_ready": learning_manifest["learning_results_measured"] is False,
        "hdf5_export_generated": hdf5_path.exists(),
        "hdf5_inspection_clean": not hdf5_inspection.get("issues"),
        "no_fake_learning_uplift": learning_manifest["curated_vs_uncurated_uplift"] is None,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": all(readiness_gates.values()),
        "task": TASK,
        "output_dir": str(output_dir),
        "artifact_paths": {
            "raw_storage": str(raw_storage),
            "curated_storage": str(curated_storage),
            "curation_manifest": str(output_dir / "curation_manifest.json"),
            "split_manifest": str(output_dir / "split_manifest.json"),
            "dataset_card": str(output_dir / "dataset_card.json"),
            "experiment_manifest": str(output_dir / "curated_vs_uncurated_experiment_manifest.json"),
            "hdf5_export": str(hdf5_path),
            "hdf5_inspection": str(output_dir / "hdf5_inspection.json"),
        },
        "readiness_gates": readiness_gates,
        "raw_episode_count": len(records),
        "accepted_count": len(curated["accepted"]),
        "rejected_count": len(curated["rejected"]),
        "phase_coverage": phase_coverage,
        "evaluator_failure_reason_distribution": dict(sorted(evaluator_failure_reasons.items())),
        "curation_rejection_reason_distribution": manifest["rejection_reason_distribution"],
        "hdf5_exported_episode_ids": export_result.exported_episode_ids,
        "hdf5_inspection_issue_count": len(hdf5_inspection.get("issues", [])),
        "learning_results_measured": False,
        "next_actions": [
            "Replace synthetic readiness fixtures with real Quest/Isaac peg-in-hole trajectories.",
            "Run scripts/run_mvp1_trainer_smoke.py to prove exported HDF5 loader/trainer readiness.",
            "Collect curated and uncurated splits from the same task definition.",
            "Run real policy A/B evaluation before reporting any learning uplift.",
        ],
    }
    write_json(output_dir / "readiness_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "storage" / "mvp1_readiness",
        help="Directory for generated readiness artifacts.",
    )
    parser.add_argument("--clean", action="store_true", help="Remove the output directory before generating artifacts.")
    parser.add_argument("--pretty", action="store_true", help="Print the full readiness report as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_bundle(args.output_dir, clean=args.clean)
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1 offline readiness: {status}")
        print(
            "episodes: "
            f"raw={report['raw_episode_count']} "
            f"accepted={report['accepted_count']} "
            f"rejected={report['rejected_count']}"
        )
        print(f"phases: {', '.join(report['phase_coverage'])}")
        print(f"hdf5: {report['artifact_paths']['hdf5_export']}")
        print("learning_results_measured: false")
        for action in report["next_actions"]:
            print(f"next: {action}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
