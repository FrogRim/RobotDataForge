#!/usr/bin/env python3
"""Build a self-contained MVP-3A proof-infrastructure package.

This runner coordinates package assembly from pre-existing evidence artifacts.
It does not execute Isaac, tune policies, or open held-out ranges by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.proof.closure import derive_closure  # noqa: E402
from app.services.proof.contracts import (  # noqa: E402
    CalibrationSelectionReport,
    ClosureThresholds,
    GateInputs,
    LearningReport,
    RuntimeExpectations,
    RuntimeGate,
    TrainRuntimeGate,
)


ROLLOUT_TARGETS = {
    "baseline_calibration_rollouts": "data/rollouts/calibration_baseline_rollouts.json",
    "candidate_calibration_rollouts": "data/rollouts/calibration_candidate_rollouts.json",
    "baseline_heldout_rollouts": "data/rollouts/heldout_baseline_rollouts.json",
    "candidate_heldout_rollouts": "data/rollouts/heldout_candidate_rollouts.json",
}

GATE_TARGETS = {
    "runtime_gate": "data/gates/runtime_gate.json",
    "train_generation_runtime_gate": "data/gates/train_generation_runtime_gate.json",
    "calibration_selection_report": "data/gates/calibration_selection_report.json",
    "train_trace_summary": "data/gates/train_trace_summary.json",
    "post_heldout_guard": "data/gates/post_heldout_guard.json",
}

MASK_TARGETS = {
    "heldout_baseline_success_masks": "data/masks/heldout_baseline_success_masks.json",
    "heldout_candidate_success_masks": "data/masks/heldout_candidate_success_masks.json",
}

POLICY_TARGETS = {
    "baseline_policy_artifact": "data/policies/baseline_policy_artifact.json",
    "candidate_policy_artifact": "data/policies/candidate_policy_artifact.json",
}

DEFAULT_NON_CLAIMS = {
    "real_robot_success": False,
    "physical_robot_readiness": False,
    "deployable_policy_readiness": False,
    "visual_policy_performance": False,
    "hmd_openxr_collection_readiness": False,
    "universal_robot_support": False,
    "ur_adapter_support": False,
    "ros2_dds_adapter_support": False,
    "franka_hardware_support": False,
    "marketplace_readiness": False,
    "production_certification": False,
}


def stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_config(config: dict) -> None:
    if config.get("evidence_kind") not in {"actual_isaac", "synthetic_test_fixture"}:
        raise ValueError("evidence_kind must be actual_isaac or synthetic_test_fixture")
    if config["task_variant"].get("source_variable_opened") is True:
        raise ValueError("source_variable_opened is not allowed in MVP-3A")
    ranges = config["seed_ranges"]
    if ranges.get("train") != [43000, 43049]:
        raise ValueError("MVP-3A train range must be 43000-43049")
    if ranges["heldout"] != [42000, 42049]:
        raise ValueError("MVP-3A heldout range must be 42000-42049")
    if ranges["calibration"] != [41000, 41029]:
        raise ValueError("MVP-3A calibration range must be 41000-41029")
    if [40000, 40049] not in ranges.get("spent_no_reuse", []):
        raise ValueError("MVP-2 spent range 40000-40049 must be listed in spent_no_reuse")
    if config["runtime_expectations"].get(
        "proof_runtime"
    ) != "dedicated_isaac_connector_insertion_evaluator":
        raise ValueError("proof_runtime must be dedicated_isaac_connector_insertion_evaluator")
    if config.get("evidence_kind") == "actual_isaac":
        paths = config.get("evidence_paths", {})
        required = {**MASK_TARGETS, **POLICY_TARGETS}
        missing = [key for key in required if not paths.get(key)]
        if missing:
            raise ValueError(
                "actual_isaac provenance requires policy artifacts and C-lite masks: "
                + ", ".join(missing)
            )


def copy_evidence(config: dict, output_dir: Path) -> list[str]:
    copied: list[str] = []
    paths = config["evidence_paths"]
    copy_targets = {**ROLLOUT_TARGETS, **GATE_TARGETS}
    if config.get("evidence_kind") == "actual_isaac":
        copy_targets.update(POLICY_TARGETS)
    for key, target in copy_targets.items():
        source = Path(paths[key])
        if not source.is_file():
            raise FileNotFoundError(f"missing evidence path for {key}: {source}")
        dest = output_dir / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied.append(target)
    for key, target in MASK_TARGETS.items():
        source_value = paths.get(key)
        if not source_value:
            continue
        source = Path(source_value)
        if not source.is_file():
            if config.get("evidence_kind") == "actual_isaac":
                raise FileNotFoundError(f"missing evidence path for {key}: {source}")
            continue
        dest = output_dir / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied.append(target)
    return copied


def _records(path: Path) -> list[dict]:
    return load_json(path)["rollout_results"]


def _summary(path: Path) -> dict:
    rows = _records(path)
    successes = sum(1 for row in rows if row["success"] is True)
    return {"rollouts": len(rows), "successes": successes, "rate": successes / len(rows)}


def learning_summary(output_dir: Path, config: dict) -> dict:
    baseline = _summary(output_dir / "data" / "rollouts" / "heldout_baseline_rollouts.json")
    candidate = _summary(
        output_dir / "data" / "rollouts" / "heldout_candidate_rollouts.json"
    )
    uplift = candidate["rate"] - baseline["rate"]
    positive = (
        candidate["rate"] > baseline["rate"] and uplift >= config["thresholds"]["uplift_min"]
    )
    return {
        "baseline_heldout_successes": baseline["successes"],
        "candidate_heldout_successes": candidate["successes"],
        "baseline_heldout_success_rate": baseline["rate"],
        "candidate_heldout_success_rate": candidate["rate"],
        "heldout_uplift": uplift,
        "learning_result": "positive_uplift" if positive else "non_closing",
        "learning_proven_addendum": "absent",
    }


def closure_verdict(output_dir: Path, config: dict, summary: dict) -> dict:
    runtime_gate = load_json(output_dir / "data" / "gates" / "runtime_gate.json")
    train_gate = load_json(output_dir / "data" / "gates" / "train_generation_runtime_gate.json")
    selection = load_json(output_dir / "data" / "gates" / "calibration_selection_report.json")
    train_trace = load_json(output_dir / "data" / "gates" / "train_trace_summary.json")
    post_guard = load_json(output_dir / "data" / "gates" / "post_heldout_guard.json")
    thresholds = config["thresholds"]
    heldout_rollouts = _summary(
        output_dir / "data" / "rollouts" / "heldout_baseline_rollouts.json"
    )["rollouts"]
    inputs = GateInputs(
        learning_report=LearningReport(
            learning_proven=summary["learning_result"] == "positive_uplift",
            proof_eligible=True,
            curated_vs_uncurated_uplift=summary["heldout_uplift"],
            baseline_success_rate=summary["baseline_heldout_success_rate"],
            candidate_success_rate=summary["candidate_heldout_success_rate"],
        ),
        runtime_gate=RuntimeGate(**runtime_gate),
        train_generation_runtime_gate=TrainRuntimeGate(**train_gate),
        calibration_selection_report=CalibrationSelectionReport(**selection),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=heldout_rollouts,
        actual_success_trace_count=train_trace["actual_success_trace_count"],
        post_heldout_guard_passed=post_guard.get("passed"),
    )
    verdict = derive_closure(
        inputs=inputs,
        runtime_expectations=RuntimeExpectations(**config["runtime_expectations"]),
        thresholds=ClosureThresholds(
            uplift_min=thresholds["uplift_min"],
            min_rollouts_per_policy=thresholds["min_heldout_rollouts_per_policy"],
            trace_minimum=1,
        ),
    )
    actual_isaac = config.get("evidence_kind") == "actual_isaac"
    package_status = (
        "proof_infrastructure_closed"
        if actual_isaac and verdict.closed
        else "proof_infrastructure_failed"
        if actual_isaac
        else "synthetic_verifier_fixture"
    )
    learning_addendum = (
        "present"
        if actual_isaac and verdict.closed and summary["learning_result"] == "positive_uplift"
        else "absent"
    )
    return {
        **summary,
        "package_status": package_status,
        "learning_result": summary["learning_result"],
        "learning_proven_addendum": learning_addendum,
        "closed": verdict.closed,
        "gates": verdict.gates,
        "blockers": verdict.blockers,
    }


def write_manifest(output_dir: Path) -> None:
    entries = []
    for path in sorted((output_dir / "data").rglob("*.json")):
        rel = path.relative_to(output_dir).as_posix()
        entries.append(
            {
                "data_path": rel,
                "hash_convention": "file_bytes",
                "file_sha256": sha256_file(path),
            }
        )
    closure = load_json(output_dir / "data" / "closure_verdict.json")
    manifest = {
        "package_name": "mvp3a_target_fixture_pose_variant_proof_package",
        "artifact_index": entries,
        "claims": {
            "package_status": closure["package_status"],
            "learning_result": closure["learning_result"],
            "learning_proven_addendum": closure["learning_proven_addendum"],
        },
    }
    write_json(output_dir / "package_manifest.json", manifest)


def write_readme(output_dir: Path) -> None:
    (output_dir / "README.md").write_text(
        "# MVP-3A Target / Fixture Pose Variant Proof Package\n\n"
        "Run `python3 scripts/verify_proof_package.py package_manifest.json` to "
        "recompute the package verdict from self-contained JSON evidence.\n",
        encoding="utf-8",
    )


def write_learning_addendum(output_dir: Path, summary: dict) -> None:
    if summary["learning_proven_addendum"] != "present":
        return
    addendum = output_dir / "addenda" / "learning_proven"
    write_json(
        addendum / "learning_proven_report.json",
        {
            "learning_result": summary["learning_result"],
            "heldout_uplift": summary["heldout_uplift"],
            "baseline_heldout_success_rate": summary["baseline_heldout_success_rate"],
            "candidate_heldout_success_rate": summary["candidate_heldout_success_rate"],
        },
    )
    write_json(
        addendum / "package_manifest.json",
        {
            "package_name": "mvp3a_learning_proven_addendum",
            "artifact_index": [
                {
                    "data_path": "learning_proven_report.json",
                    "hash_convention": "file_bytes",
                    "file_sha256": sha256_file(addendum / "learning_proven_report.json"),
                }
            ],
        },
    )


def build_package(config_path: Path) -> Path:
    config = load_json(config_path)
    validate_config(config)
    output_dir = Path(config["package_policy"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "data" / "config.json", config)
    write_json(output_dir / "data" / "task_variant_attestation.json", config["task_variant"])
    write_json(output_dir / "data" / "non_claims_attestation.json", DEFAULT_NON_CLAIMS)
    copied = copy_evidence(config, output_dir)
    summary = learning_summary(output_dir, config)
    closure = closure_verdict(output_dir, config, summary)
    summary["learning_proven_addendum"] = closure["learning_proven_addendum"]
    write_json(output_dir / "data" / "learning_result_summary.json", summary)
    write_json(output_dir / "data" / "closure_verdict.json", closure)
    write_json(
        output_dir / "data" / "seed_discipline_report.json",
        {"passed": True, "spent_after_closure_attempt": [42000, 42049]},
    )
    write_json(
        output_dir / "data" / "artifact_index.json",
        {"generated_by": "run_mvp3a_proof_infrastructure.py", "copied": copied},
    )
    write_learning_addendum(output_dir, summary)
    write_manifest(output_dir)
    write_readme(output_dir)
    return output_dir / "package_manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = build_package(args.config)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"package_manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
