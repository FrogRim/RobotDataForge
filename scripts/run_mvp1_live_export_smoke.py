#!/usr/bin/env python3
"""Build a trainer-smoke bundle from real MVP-1A live insertion trajectories.

This is the stronger MVP-1B evidence path: it does not require wearing the HMD
again, but it proves that already-collected Quest/SteamVR/OpenXR/Isaac
insertion trajectories can flow through export and trainer-loader smoke.

It still must not claim curated-vs-uncurated policy uplift.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
for path in (SCRIPT_DIR, API_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.evaluator import add_evaluation_semantics, failure_category_for_reason  # noqa: E402
from export_rdf_to_hdf5 import EXPORTABLE_STATUSES, ExportValidationError, export_hdf5, load_json
from inspect_rdf_hdf5 import inspect_hdf5
from run_mvp1_proof_audit import scan_live_insertion_trajectories
from run_mvp1_trainer_smoke import run_trainer_smoke


SCHEMA_VERSION = "rdf_mvp1_live_export_smoke_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp1_live_export"
DEFAULT_PROOF_LEARNING_MANIFEST = (
    ROOT / "storage" / "mvp1_readiness" / "curated_vs_uncurated_experiment_manifest.json"
)


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def _trajectory_mtime(candidate: dict[str, Any]) -> float:
    try:
        return Path(str(candidate["path"])).stat().st_mtime
    except OSError:
        return 0.0


def select_live_candidates(
    *,
    trajectory_dir: Path,
    trajectory_id: str | None = None,
    limit: int = 1,
) -> list[dict[str, Any]]:
    scan = scan_live_insertion_trajectories(trajectory_dir)
    candidates = list(scan.get("candidates", []))
    if trajectory_id:
        candidates = [item for item in candidates if item.get("trajectory_id") == trajectory_id]
    candidates.sort(key=lambda item: (_trajectory_mtime(item), str(item.get("trajectory_id") or "")), reverse=True)
    return candidates[: max(1, limit)]


def _copy_matching_evaluation(*, trajectory: dict[str, Any], evaluations_dir: Path, output_dir: Path) -> list[str]:
    copied: list[str] = []
    if not evaluations_dir.exists():
        return copied
    trajectory_id = trajectory.get("id")
    episode_id = trajectory.get("episode_id")
    for path in sorted(evaluations_dir.glob("*.json")):
        evaluation = load_json(path)
        if evaluation.get("trajectory_id") == trajectory_id or evaluation.get("episode_id") == episode_id:
            destination = output_dir / path.name
            shutil.copy2(path, destination)
            copied.append(str(destination))
    return copied


def _write_split_manifest(path: Path, episode_ids: list[str]) -> dict[str, Any]:
    # One live trajectory is enough for an MVP-1B smoke. Reusing it across split
    # names is explicitly marked as smoke-only and must not be used for uplift.
    manifest = {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "split_policy": "single_live_episode_reused_for_trainer_smoke_only",
        "warning": "This split is for loader/trainer smoke only, not policy evaluation.",
        "splits": {
            "train": episode_ids,
            "validation": episode_ids,
            "test": episode_ids,
        },
    }
    write_json(path, manifest)
    return manifest


def _write_dataset_card(
    path: Path,
    *,
    trajectories: list[dict[str, Any]],
    hdf5_path: Path,
    trainer_report_path: Path,
) -> dict[str, Any]:
    source = trajectories[0].get("source") if trajectories and isinstance(trajectories[0].get("source"), dict) else {}
    card = {
        "schema_version": "rdf_dataset_card_v0.1.0",
        "dataset_name": "Robot Data Forge MVP-1B Live Export Smoke",
        "created_at": datetime.now(UTC).isoformat(),
        "task_type": "peg_in_hole",
        "robot": source.get("robot", "franka"),
        "source": {
            "input_device": source.get("input_device"),
            "runtime": source.get("runtime"),
            "simulator": source.get("simulator"),
            "task_name": source.get("task_name"),
        },
        "num_live_trajectories": len(trajectories),
        "trajectory_ids": [item.get("id") for item in trajectories],
        "episode_ids": [item.get("episode_id") for item in trajectories],
        "hdf5_path": str(hdf5_path),
        "trainer_smoke_report_path": str(trainer_report_path),
        "limitations": [
            "Smoke-only single-source live export evidence.",
            "Does not measure curated-vs-uncurated policy uplift.",
            "Does not replace MVP-1C held-out policy evaluation.",
        ],
    }
    write_json(path, card)
    return card


def _evaluation_for_trajectory(
    *,
    trajectory: dict[str, Any],
    evaluation_paths: list[str],
) -> dict[str, Any] | None:
    trajectory_id = trajectory.get("id")
    episode_id = trajectory.get("episode_id")
    for path_text in evaluation_paths:
        evaluation = load_json(Path(path_text))
        if evaluation.get("trajectory_id") == trajectory_id or evaluation.get("episode_id") == episode_id:
            return evaluation
    return None


def _evaluation_semantics(
    *,
    trajectory: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    if evaluation is None:
        return {
            "evaluation_semantics_version": "rdf_evaluation_semantics_v0.1.0",
            "failure_category": "METADATA_FAILURE",
            "task_outcome": {
                "operator_success": summary.get("episode_status") == "success",
                "evaluator_task_success": "unknown",
                "task_success_confidence": None,
                "task_failure_reason": None,
            },
            "data_quality": {
                "replay_verified": False,
                "action_contract_valid": False,
                "action_contract_status": "unknown",
                "retargeting_jump": "unknown",
                "native_action_saturation": "unknown",
                "native_action_saturation_ratio": None,
                "sync_quality": "unknown",
                "control_quality": "fail",
                "quality_failure_reasons": [],
            },
            "curation": {
                "raw_saved": True,
                "human_success_pool": summary.get("episode_status") == "success",
                "training_eligible": False,
                "curated_accepted": False,
                "proof_eligible": False,
                "rejection_reasons": ["MISSING_EVALUATION", "REPLAY_NOT_VERIFIED"],
            },
        }

    metrics = evaluation.get("metrics") if isinstance(evaluation.get("metrics"), dict) else {}
    failure_reason = evaluation.get("failure_reason") or evaluation.get("failure_mode")
    failure_category = (
        evaluation.get("failure_category")
        or metrics.get("failure_category")
        or failure_category_for_reason(str(failure_reason) if failure_reason else None)
    )
    return add_evaluation_semantics(
        metrics,
        trajectory,
        success=evaluation.get("success") is True,
        failure_reason=str(failure_reason) if failure_reason else None,
        failure_category=str(failure_category),
        evaluator_confidence=evaluation.get("evaluator_confidence"),
    )


def _curated_dataset_rejection_reasons(
    *,
    trajectory: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> list[str]:
    reasons: list[str] = []
    frames = trajectory.get("frames") if isinstance(trajectory.get("frames"), list) else []
    if not frames:
        reasons.append("EMPTY_TRAJECTORY")
    semantics = _evaluation_semantics(trajectory=trajectory, evaluation=evaluation)
    curation = semantics.get("curation") if isinstance(semantics.get("curation"), dict) else {}
    for reason in curation.get("rejection_reasons") or []:
        if isinstance(reason, str):
            reasons.append(reason)
    if evaluation is None:
        return sorted(set(reasons))
    usability = (
        evaluation.get("metrics", {}).get("data_usability", {})
        if isinstance(evaluation.get("metrics"), dict)
        else {}
    )
    if isinstance(usability, dict):
        for reason in usability.get("rejection_reasons") or []:
            if isinstance(reason, str) and reason not in reasons:
                reasons.append(reason)
    return sorted(set(reasons))


def _write_curation_manifest(
    path: Path,
    *,
    trajectories: list[dict[str, Any]],
    copied_evaluation_paths: list[str],
) -> dict[str, Any]:
    smoke_included = []
    accepted = []
    rejected = []
    rejection_distribution: dict[str, int] = {}
    for trajectory in trajectories:
        summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
        evaluation = _evaluation_for_trajectory(trajectory=trajectory, evaluation_paths=copied_evaluation_paths)
        semantics = _evaluation_semantics(trajectory=trajectory, evaluation=evaluation)
        task_outcome = semantics.get("task_outcome") if isinstance(semantics.get("task_outcome"), dict) else {}
        data_quality = semantics.get("data_quality") if isinstance(semantics.get("data_quality"), dict) else {}
        semantic_curation = semantics.get("curation") if isinstance(semantics.get("curation"), dict) else {}
        semantic_training_eligible = bool(semantic_curation.get("training_eligible"))
        rejection_reasons = _curated_dataset_rejection_reasons(trajectory=trajectory, evaluation=evaluation)
        base_entry = {
            "trajectory_id": trajectory.get("id"),
            "episode_id": trajectory.get("episode_id"),
            "episode_status": summary.get("episode_status"),
            "frame_count": len(trajectory.get("frames") or []),
            "evaluation_id": None if evaluation is None else evaluation.get("id"),
            "evaluation_success": None if evaluation is None else evaluation.get("success"),
            "evaluation_failure_reason": None if evaluation is None else evaluation.get("failure_reason"),
            "evaluation_failure_category": semantics.get("failure_category"),
            "evaluation_score": None if evaluation is None else evaluation.get("score"),
            "data_usability_score": None if evaluation is None else evaluation.get("data_usability_score"),
            "task_outcome": task_outcome,
            "data_quality": data_quality,
            "curation": {
                **semantic_curation,
                "rejection_reasons": rejection_reasons,
                "training_eligible": bool(semantic_training_eligible and not rejection_reasons),
                "curated_accepted": bool(semantic_training_eligible and not rejection_reasons),
                "proof_eligible": bool(
                    semantic_training_eligible
                    and not rejection_reasons
                    and task_outcome.get("evaluator_task_success") is True
                ),
            },
            "smoke_included": True,
            "smoke_inclusion_reason": "LIVE_MVP1A_EXPORT_AND_TRAINER_LOADER_SMOKE_INPUT",
        }
        smoke_included.append(base_entry)
        if rejection_reasons:
            for reason in rejection_reasons:
                rejection_distribution[reason] = rejection_distribution.get(reason, 0) + 1
            rejected.append(
                {
                    **base_entry,
                    "curated_dataset_status": "rejected",
                    "rejection_reasons": rejection_reasons,
                }
            )
        else:
            accepted.append(
                {
                    **base_entry,
                    "curated_dataset_status": "accepted_candidate",
                    "acceptance_reason": "LIVE_EVALUATION_SUCCESS_AND_REPLAY_VERIFIED",
                }
            )
    manifest = {
        "schema_version": "rdf_curation_manifest_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "ruleset_version": "live_export_smoke_v0.1",
        "scope": "trainer_loader_smoke_only",
        "smoke_included_count": len(smoke_included),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "smoke_included": smoke_included,
        "accepted": accepted,
        "rejected": rejected,
        "rejection_reason_distribution": dict(sorted(rejection_distribution.items())),
        "limitations": [
            "Smoke-only curation manifest; smoke_included trajectories may be exported for loader/trainer validation even when rejected for curated dataset use.",
            "Only accepted entries may be treated as curated dataset material.",
            "HMD live trajectories require action_replay_gate.passed=true before accepted promotion.",
        ],
    }
    write_json(path, manifest)
    return manifest


def _write_experiment_manifest(path: Path, *, episode_ids: list[str]) -> dict[str, Any]:
    manifest = {
        "schema_version": "rdf_curated_vs_uncurated_experiment_manifest_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": "mvp1_live_export_smoke",
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "training_readiness": {
            "loader_smoke_passed": False,
            "trainer_dry_run_passed": False,
            "one_epoch_smoke_passed": False,
            "policy_class": None,
            "trainer": None,
            "evidence_source": "mvp1a_live_export_bundle",
        },
        "baseline_a_uncurated_success_lifecycle_episode_ids": [],
        "baseline_b_curated_accepted_episode_ids": episode_ids,
        "required_future_evidence": [
            "Train/evaluate uncurated vs curated policies on held-out insertion suite before reporting uplift.",
        ],
    }
    write_json(path, manifest)
    return manifest


def _merge_training_readiness_into_proof_manifest(
    *,
    proof_learning_manifest_path: Path,
    live_manifest_path: Path,
    trainer_report: dict[str, Any],
    selected_trajectories: list[dict[str, Any]],
) -> None:
    if not proof_learning_manifest_path.exists():
        return
    proof_manifest = read_json(proof_learning_manifest_path)
    live_manifest = read_json(live_manifest_path)
    readiness = live_manifest.get("training_readiness")
    if not isinstance(readiness, dict):
        readiness = {}
    readiness.update(
        {
            "evidence_source": "mvp1a_live_export_bundle",
            "live_trajectory_ids": [item.get("id") for item in selected_trajectories],
            "live_episode_ids": [item.get("episode_id") for item in selected_trajectories],
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
        }
    )
    proof_manifest["training_readiness"] = readiness
    proof_manifest["learning_results_measured"] = False
    proof_manifest["curated_vs_uncurated_uplift"] = None
    proof_manifest["mvp1b_live_export_smoke"] = {
        "schema_version": trainer_report.get("schema_version"),
        "passed": trainer_report.get("passed"),
        "report_path": readiness.get("report_path"),
        "live_export_report_path": str(live_manifest_path.parent / "live_export_smoke_report.json"),
        "hdf5_path": readiness.get("hdf5_path"),
        "split_manifest_path": readiness.get("split_manifest_path"),
        "trajectory_ids": [item.get("id") for item in selected_trajectories],
        "episode_ids": [item.get("episode_id") for item in selected_trajectories],
    }
    write_json(proof_learning_manifest_path, proof_manifest)


def build_live_export_smoke(
    *,
    output_dir: Path,
    trajectory_dir: Path,
    evaluations_dir: Path,
    trajectory_id: str | None = None,
    limit: int = 1,
    clean: bool = False,
    proof_learning_manifest_path: Path | None = DEFAULT_PROOF_LEARNING_MANIFEST,
) -> dict[str, Any]:
    selected = select_live_candidates(trajectory_dir=trajectory_dir, trajectory_id=trajectory_id, limit=limit)
    if not selected:
        raise SystemExit("No real MVP-1A live insertion trajectory candidates found.")

    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    raw_trajectory_dir = output_dir / "raw" / "trajectories"
    raw_evaluation_dir = output_dir / "raw" / "evaluations"
    raw_trajectory_dir.mkdir(parents=True, exist_ok=True)
    raw_evaluation_dir.mkdir(parents=True, exist_ok=True)

    trajectories: list[dict[str, Any]] = []
    copied_trajectory_paths: list[str] = []
    copied_evaluation_paths: list[str] = []
    for candidate in selected:
        source_path = Path(str(candidate["path"]))
        trajectory = load_json(source_path)
        destination = raw_trajectory_dir / source_path.name
        shutil.copy2(source_path, destination)
        copied_trajectory_paths.append(str(destination))
        copied_evaluation_paths.extend(
            _copy_matching_evaluation(
                trajectory=trajectory,
                evaluations_dir=evaluations_dir,
                output_dir=raw_evaluation_dir,
            )
        )
        trajectories.append(trajectory)

    hdf5_path = output_dir / "rdf_mvp1_live_export_smoke.hdf5"
    export_result = export_hdf5(
        output_path=hdf5_path,
        trajectories_dir=raw_trajectory_dir,
        evaluations_dir=raw_evaluation_dir,
        include_statuses=set(EXPORTABLE_STATUSES),
    )

    hdf5_inspection = inspect_hdf5(hdf5_path)
    hdf5_inspection_path = output_dir / "hdf5_inspection.json"
    write_json(hdf5_inspection_path, hdf5_inspection)

    split_manifest_path = output_dir / "split_manifest.json"
    split_manifest = _write_split_manifest(split_manifest_path, export_result.exported_episode_ids)

    trainer_report_path = output_dir / "trainer_smoke_report.json"
    dataset_card = _write_dataset_card(
        output_dir / "dataset_card.json",
        trajectories=trajectories,
        hdf5_path=hdf5_path,
        trainer_report_path=trainer_report_path,
    )
    curation_manifest = _write_curation_manifest(
        output_dir / "curation_manifest.json",
        trajectories=trajectories,
        copied_evaluation_paths=copied_evaluation_paths,
    )
    experiment_manifest_path = output_dir / "curated_vs_uncurated_experiment_manifest.json"
    _write_experiment_manifest(experiment_manifest_path, episode_ids=export_result.exported_episode_ids)

    trainer_report = run_trainer_smoke(
        hdf5_path=hdf5_path,
        split_manifest_path=split_manifest_path,
        output_path=trainer_report_path,
        experiment_manifest_path=experiment_manifest_path,
    )

    if proof_learning_manifest_path is not None:
        _merge_training_readiness_into_proof_manifest(
            proof_learning_manifest_path=proof_learning_manifest_path,
            live_manifest_path=experiment_manifest_path,
            trainer_report=trainer_report,
            selected_trajectories=trajectories,
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": bool(trainer_report.get("passed") and not hdf5_inspection.get("issues")),
        "created_at": datetime.now(UTC).isoformat(),
        "output_dir": str(output_dir),
        "selected_trajectories": selected,
        "copied_trajectory_paths": copied_trajectory_paths,
        "copied_evaluation_paths": copied_evaluation_paths,
        "hdf5_path": str(hdf5_path),
        "hdf5_inspection_path": str(hdf5_inspection_path),
        "split_manifest_path": str(split_manifest_path),
        "dataset_card_path": str(output_dir / "dataset_card.json"),
        "curation_manifest_path": str(output_dir / "curation_manifest.json"),
        "experiment_manifest_path": str(experiment_manifest_path),
        "trainer_smoke_report_path": str(trainer_report_path),
        "proof_learning_manifest_path": str(proof_learning_manifest_path) if proof_learning_manifest_path else None,
        "export": {
            "exported_episode_ids": export_result.exported_episode_ids,
            "skipped_by_status": export_result.skipped_by_status,
            "warnings": export_result.warnings,
        },
        "hdf5": {
            "episode_count": hdf5_inspection.get("episode_count"),
            "issues": hdf5_inspection.get("issues"),
            "warnings": hdf5_inspection.get("warnings"),
        },
        "split_manifest": split_manifest,
        "dataset_card": dataset_card,
        "curation_manifest": curation_manifest,
        "trainer_smoke": {
            "passed": trainer_report.get("passed"),
            "loader_smoke_passed": trainer_report.get("loader_smoke_passed"),
            "trainer_dry_run_passed": trainer_report.get("trainer_dry_run_passed"),
            "one_epoch_smoke_passed": trainer_report.get("one_epoch_smoke_passed"),
            "learning_results_measured": trainer_report.get("learning_results_measured"),
            "curated_vs_uncurated_uplift": trainer_report.get("curated_vs_uncurated_uplift"),
            "sample_count": (trainer_report.get("trainer") or {}).get("sample_count"),
            "observation_dim": (trainer_report.get("trainer") or {}).get("observation_dim"),
            "action_dim": (trainer_report.get("trainer") or {}).get("action_dim"),
        },
    }
    write_json(output_dir / "live_export_smoke_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--trajectory-dir", type=Path, default=ROOT / "storage" / "trajectories")
    parser.add_argument("--evaluations-dir", type=Path, default=ROOT / "storage" / "evaluations")
    parser.add_argument("--trajectory-id", help="Specific live trajectory id to export.")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--proof-learning-manifest",
        type=Path,
        default=DEFAULT_PROOF_LEARNING_MANIFEST,
        help="Existing proof manifest to update with live-export trainer readiness. Use --no-update-proof-manifest to skip.",
    )
    parser.add_argument("--no-update-proof-manifest", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_live_export_smoke(
            output_dir=args.output_dir,
            trajectory_dir=args.trajectory_dir,
            evaluations_dir=args.evaluations_dir,
            trajectory_id=args.trajectory_id,
            limit=args.limit,
            clean=args.clean,
            proof_learning_manifest_path=None if args.no_update_proof_manifest else args.proof_learning_manifest,
        )
    except ExportValidationError as exc:
        raise SystemExit(f"live export smoke failed: {exc}") from exc

    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1B live export smoke: {status}")
        print(f"trajectories={', '.join(str(item.get('trajectory_id')) for item in report['selected_trajectories'])}")
        print(f"hdf5={report['hdf5_path']}")
        print(f"trainer_dry_run_passed={report['trainer_smoke']['trainer_dry_run_passed']}")
        print(f"one_epoch_smoke_passed={report['trainer_smoke']['one_epoch_smoke_passed']}")
        print(f"learning_results_measured={report['trainer_smoke']['learning_results_measured']}")
        print(f"curated_vs_uncurated_uplift={report['trainer_smoke']['curated_vs_uncurated_uplift']}")
        print(f"output={report['output_dir']}/live_export_smoke_report.json")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
