#!/usr/bin/env python3
"""Audit whether current artifacts prove MVP-1.

MVP-1 is a learning-ready dataset pipeline proof: raw XR/HMD trajectories must
be stored, evaluated, quality-gated, replay/action-gated, curated, exported,
documented, and loadable by a trainer. Downstream policy uplift is intentionally
reported as MVP-2 evidence and must not block MVP-1 completion.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rdf_mvp1_proof_audit_v0.3.0"
REQUIRED_PHASES = {"APPROACH", "ALIGN", "CONTACT", "INSERT", "SEAT", "RELEASE"}
TRANSITION_RICH_PHASES = {"APPROACH", "CONTACT", "INSERT", "SEAT"}
MVP1_TASK_MARKERS = ("peg", "hole", "insert", "connector")
POLICY_UPLIFT_EVIDENCE_TIERS = {"heldout_policy_eval", "real_heldout_policy_eval"}
POLICY_UPLIFT_PRIMARY_METRIC = "policy_success_rate"
SUPPORTING_OFFLINE_GATE_NAMES = (
    "offline_readiness_passed",
    "mvp1_phase_coverage_ready",
    "legacy_curation_manifest_ready",
    "split_manifest_ready",
    "legacy_dataset_card_ready",
    "legacy_hdf5_sanity_ready",
)
MVP1A_GATE_NAMES = (
    "raw_xr_trajectory_saved",
    "task_state_extracted",
    "task_outcome_recorded",
    "data_quality_recorded",
    "operator_success_separated_from_evaluator_task_success",
    "replay_action_gate_recorded",
)
MVP1_DATASET_PIPELINE_GATE_NAMES = (
    *MVP1A_GATE_NAMES,
    "accepted_rejected_curation_manifest_generated",
    "hdf5_export_generated",
    "trainer_loader_smoke_passed",
    "dataset_card_generated",
    "policy_claim_integrity_preserved",
)


@dataclass(frozen=True)
class Gate:
    name: str
    passed: bool
    required_for_full_proof: bool
    evidence: dict[str, Any]
    remediation: str | None = None


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def gate(
    name: str,
    passed: bool,
    *,
    required: bool = True,
    evidence: dict[str, Any] | None = None,
    remediation: str | None = None,
) -> Gate:
    return Gate(
        name=name,
        passed=bool(passed),
        required_for_full_proof=required,
        evidence=evidence or {},
        remediation=None if passed else remediation,
    )


def _task_name_or_type(trajectory: dict[str, Any]) -> str:
    source = trajectory.get("source") if isinstance(trajectory.get("source"), dict) else {}
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    return " ".join(
        str(value or "").lower()
        for value in (
            source.get("task_name"),
            summary.get("task_type"),
            trajectory.get("task_type"),
        )
    )


def _has_task_state(trajectory: dict[str, Any]) -> bool:
    frames = trajectory.get("frames")
    if not isinstance(frames, list):
        return False
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        metadata = frame.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("task_state"), dict):
            state = metadata["task_state"]
            if {
                "peg_tip_distance_to_target",
                "axis_alignment_error_rad",
                "insertion_depth",
            }.issubset(state.keys()):
                return True
    return False


def _phase_coverage(trajectory: dict[str, Any]) -> list[str]:
    phases: set[str] = set()
    frames = trajectory.get("frames")
    if not isinstance(frames, list):
        return []
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        metadata = frame.get("metadata") if isinstance(frame.get("metadata"), dict) else {}
        phase = metadata.get("action_phase")
        if isinstance(phase, str) and phase:
            phases.add(phase.upper())
    return sorted(phases)


def _looks_synthetic(trajectory: dict[str, Any], path: Path) -> bool:
    summary = trajectory.get("summary") if isinstance(trajectory.get("summary"), dict) else {}
    path_text = str(path).lower()
    markers = [
        summary.get("task_state_source"),
        summary.get("fixture_source"),
        summary.get("source"),
    ]
    return "mvp1_readiness" in path_text or any("synthetic" in str(marker).lower() for marker in markers if marker is not None)


def scan_live_insertion_trajectories(trajectory_dir: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    if not trajectory_dir.exists():
        return {
            "trajectory_dir": str(trajectory_dir),
            "candidate_count": 0,
            "candidates": [],
        }

    for path in sorted(trajectory_dir.glob("*.json")):
        trajectory = read_json(path)
        if trajectory is None:
            continue
        frames = trajectory.get("frames") if isinstance(trajectory.get("frames"), list) else []
        task_text = _task_name_or_type(trajectory)
        is_mvp1_task = any(marker in task_text for marker in MVP1_TASK_MARKERS)
        has_task_state = _has_task_state(trajectory)
        source = trajectory.get("source") if isinstance(trajectory.get("source"), dict) else {}
        is_primary_source = (
            source.get("input_device") == "quest3_handtracking"
            and source.get("runtime") == "steamvr_openxr"
            and source.get("simulator") == "isaac_lab"
        )
        synthetic = _looks_synthetic(trajectory, path)
        if is_mvp1_task and has_task_state and is_primary_source and not synthetic and frames:
            candidates.append(
                {
                    "path": str(path),
                    "trajectory_id": trajectory.get("id"),
                    "episode_id": trajectory.get("episode_id"),
                    "frame_count": len(frames),
                    "task": task_text.strip(),
                    "source": source,
                    "has_task_state": has_task_state,
                    "phase_coverage": _phase_coverage(trajectory),
                }
            )

    return {
        "trajectory_dir": str(trajectory_dir),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def _learning_field(learning: dict[str, Any] | None, key: str) -> Any:
    if not isinstance(learning, dict):
        return None
    training = learning.get("training_readiness")
    if isinstance(training, dict) and key in training:
        return training.get(key)
    return learning.get(key)


def _training_readiness_evidence(learning: dict[str, Any] | None, learning_manifest_path: Path) -> dict[str, Any]:
    loader_smoke_passed = _learning_field(learning, "loader_smoke_passed")
    trainer_dry_run_passed = _learning_field(learning, "trainer_dry_run_passed")
    one_epoch_smoke_passed = _learning_field(learning, "one_epoch_smoke_passed")
    return {
        "path": str(learning_manifest_path),
        "loader_smoke_passed": loader_smoke_passed,
        "trainer_dry_run_passed": trainer_dry_run_passed,
        "one_epoch_smoke_passed": one_epoch_smoke_passed,
        "policy_class": _learning_field(learning, "policy_class"),
        "trainer": _learning_field(learning, "trainer"),
        "evidence_source": _learning_field(learning, "evidence_source"),
        "report_path": _learning_field(learning, "report_path"),
        "hdf5_path": _learning_field(learning, "hdf5_path"),
        "split_manifest_path": _learning_field(learning, "split_manifest_path"),
        "sample_count": _learning_field(learning, "sample_count"),
        "observation_dim": _learning_field(learning, "observation_dim"),
        "action_dim": _learning_field(learning, "action_dim"),
        "live_trajectory_ids": _learning_field(learning, "live_trajectory_ids"),
        "live_episode_ids": _learning_field(learning, "live_episode_ids"),
    }


def _trainer_dry_run_ready(learning: dict[str, Any] | None) -> bool:
    loader_smoke_passed = _learning_field(learning, "loader_smoke_passed") is True
    trainer_dry_run_passed = _learning_field(learning, "trainer_dry_run_passed") is True
    one_epoch_smoke_passed = _learning_field(learning, "one_epoch_smoke_passed") is True
    return loader_smoke_passed and (trainer_dry_run_passed or one_epoch_smoke_passed)


def _policy_uplift_measurement(learning: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(learning, dict):
        return {}
    measurement = learning.get("policy_uplift_measurement")
    if isinstance(measurement, dict):
        return measurement
    smoke = learning.get("policy_uplift_smoke")
    if isinstance(smoke, dict):
        return smoke
    return {}


def _policy_uplift_ready(learning: dict[str, Any] | None) -> bool:
    if not isinstance(learning, dict):
        return False
    measurement = _policy_uplift_measurement(learning)
    uplift = learning.get("curated_vs_uncurated_uplift")
    return (
        learning.get("learning_results_measured") is True
        and isinstance(uplift, (int, float))
        and uplift > 0.0
        and measurement.get("proof_eligible") is True
        and measurement.get("evidence_tier") in POLICY_UPLIFT_EVIDENCE_TIERS
        and measurement.get("primary_metric") == POLICY_UPLIFT_PRIMARY_METRIC
    )


def _heldout_policy_measurement_recorded(learning: dict[str, Any] | None) -> bool:
    if not isinstance(learning, dict):
        return False
    measurement = _policy_uplift_measurement(learning)
    uplift = learning.get("curated_vs_uncurated_uplift")
    return (
        learning.get("learning_results_measured") is True
        and isinstance(uplift, (int, float))
        and measurement.get("evidence_tier") in POLICY_UPLIFT_EVIDENCE_TIERS
        and measurement.get("primary_metric") == POLICY_UPLIFT_PRIMARY_METRIC
        and measurement.get("baseline_success_rate") is not None
        and measurement.get("candidate_success_rate") is not None
    )


def _policy_uplift_evidence(learning: dict[str, Any] | None, learning_manifest_path: Path) -> dict[str, Any]:
    measurement = _policy_uplift_measurement(learning)
    return {
        "path": str(learning_manifest_path),
        "learning_results_measured": None if learning is None else learning.get("learning_results_measured"),
        "curated_vs_uncurated_uplift": None if learning is None else learning.get("curated_vs_uncurated_uplift"),
        "measurement_report_path": measurement.get("report_path"),
        "proof_eligible": measurement.get("proof_eligible"),
        "evidence_tier": measurement.get("evidence_tier"),
        "primary_metric": measurement.get("primary_metric"),
        "secondary_metrics": measurement.get("secondary_metrics"),
        "baseline_score": measurement.get("baseline_test_score") or measurement.get("baseline_success_rate"),
        "candidate_score": measurement.get("candidate_test_score") or measurement.get("candidate_success_rate"),
        "proxy_delta": measurement.get("curated_vs_uncurated_proxy_delta"),
    }


def _read_json_from_text_path(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value:
        return None
    return read_json(Path(value))


def _infer_live_export_report_path(learning: dict[str, Any] | None) -> Path | None:
    if not isinstance(learning, dict):
        return None
    smoke = learning.get("mvp1b_live_export_smoke")
    if isinstance(smoke, dict):
        explicit = smoke.get("live_export_report_path")
        if isinstance(explicit, str) and explicit:
            path = Path(explicit)
            if path.exists():
                return path
        hdf5_path = smoke.get("hdf5_path")
        if isinstance(hdf5_path, str) and hdf5_path:
            inferred = Path(hdf5_path).parent / "live_export_smoke_report.json"
            if inferred.exists():
                return inferred
    training = learning.get("training_readiness")
    if isinstance(training, dict):
        hdf5_path = training.get("hdf5_path")
        if isinstance(hdf5_path, str) and hdf5_path:
            inferred = Path(hdf5_path).parent / "live_export_smoke_report.json"
            if inferred.exists():
                return inferred
    return None


def _load_live_export_report(learning: dict[str, Any] | None) -> tuple[dict[str, Any] | None, Path | None]:
    path = _infer_live_export_report_path(learning)
    if path is None:
        return None, None
    return read_json(path), path


def _live_curation_entries(live_export: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(live_export, dict):
        return []
    curation = live_export.get("curation_manifest")
    if not isinstance(curation, dict):
        return []
    entries: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, str]] = set()
    for section_name in ("accepted", "rejected", "smoke_included"):
        section = curation.get(section_name)
        if not isinstance(section, list):
            continue
        for item in section:
            if not isinstance(item, dict):
                continue
            key = (item.get("trajectory_id"), item.get("episode_id"), section_name)
            if key in seen:
                continue
            seen.add(key)
            entries.append(item)
    return entries


def _task_outcome_recorded(entries: list[dict[str, Any]]) -> bool:
    for entry in entries:
        outcome = entry.get("task_outcome")
        if isinstance(outcome, dict) and "operator_success" in outcome and "evaluator_task_success" in outcome:
            return True
    return False


def _data_quality_recorded(entries: list[dict[str, Any]]) -> bool:
    required = {"action_contract_valid", "replay_verified", "control_quality", "quality_failure_reasons"}
    for entry in entries:
        quality = entry.get("data_quality")
        if isinstance(quality, dict) and required.issubset(quality.keys()):
            return True
    return False


def _operator_evaluator_separated(entries: list[dict[str, Any]]) -> bool:
    for entry in entries:
        outcome = entry.get("task_outcome")
        if isinstance(outcome, dict) and "operator_success" in outcome and "evaluator_task_success" in outcome:
            return outcome.get("success_label_source") is not None or outcome.get("operator_success") != outcome.get(
                "evaluator_task_success"
            )
    return False


def _replay_action_gate_recorded(
    *,
    entries: list[dict[str, Any]],
    learning: dict[str, Any] | None,
) -> bool:
    for entry in entries:
        quality = entry.get("data_quality")
        if not isinstance(quality, dict):
            continue
        if "action_contract_valid" in quality and quality.get("replay_verified") in {True, False}:
            return True
    if isinstance(learning, dict):
        replay_gate = learning.get("replay_gate")
        if isinstance(replay_gate, dict) and replay_gate.get("accepted_replay_viability") in {True, False}:
            return True
    return False


def _live_dataset_evidence(
    *,
    live_export: dict[str, Any] | None,
    live_export_path: Path | None,
    learning: dict[str, Any] | None,
) -> dict[str, Any]:
    entries = _live_curation_entries(live_export)
    accepted = []
    rejected = []
    if isinstance(live_export, dict):
        curation = live_export.get("curation_manifest")
        if isinstance(curation, dict):
            accepted = curation.get("accepted") if isinstance(curation.get("accepted"), list) else []
            rejected = curation.get("rejected") if isinstance(curation.get("rejected"), list) else []
    return {
        "path": None if live_export_path is None else str(live_export_path),
        "entry_count": len(entries),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "task_outcome_recorded": _task_outcome_recorded(entries),
        "data_quality_recorded": _data_quality_recorded(entries),
        "operator_success_separated_from_evaluator_task_success": _operator_evaluator_separated(entries),
        "replay_action_gate_recorded": _replay_action_gate_recorded(entries=entries, learning=learning),
        "trajectory_ids": sorted(
            str(item.get("trajectory_id")) for item in entries if item.get("trajectory_id") is not None
        ),
        "episode_ids": sorted(str(item.get("episode_id")) for item in entries if item.get("episode_id") is not None),
    }


def _policy_measurement_report(learning: dict[str, Any] | None) -> dict[str, Any] | None:
    measurement = _policy_uplift_measurement(learning)
    report = _read_json_from_text_path(measurement.get("report_path"))
    return report if isinstance(report, dict) else None


def _transition_rich_live_evidence(live_scan: dict[str, Any]) -> bool:
    for candidate in live_scan.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        phases = set(candidate.get("phase_coverage") or [])
        if TRANSITION_RICH_PHASES.issubset(phases):
            return True
    return False


def _stronger_policy_or_trainer(measurement_report: dict[str, Any] | None) -> bool:
    if not isinstance(measurement_report, dict):
        return False
    policies = []
    for key in ("baseline", "candidate"):
        policy = measurement_report.get(key)
        if isinstance(policy, dict):
            policies.append(policy)
    if not policies:
        return False
    for policy in policies:
        text = " ".join(str(policy.get(key) or "").lower() for key in ("policy_class", "trainer"))
        if "smoke" in text or "linear_bc_numpy_smoke" in text:
            return False
    return True


def build_mvp2_policy_uplift_status(
    *,
    learning: dict[str, Any] | None,
    learning_manifest_path: Path,
    live_scan: dict[str, Any],
) -> dict[str, Any]:
    measurement = _policy_uplift_measurement(learning)
    measurement_report = _policy_measurement_report(learning)
    heldout_recorded = _heldout_policy_measurement_recorded(learning)
    positive_uplift = _policy_uplift_ready(learning)
    negative_evidence = heldout_recorded and not positive_uplift
    result_report_path = measurement.get("report_path")
    result_report_exists = isinstance(result_report_path, str) and Path(result_report_path).exists()
    gates = [
        gate(
            "transition_rich_accepted_dataset",
            _transition_rich_live_evidence(live_scan),
            required=False,
            evidence={
                "required_phases": sorted(TRANSITION_RICH_PHASES),
                "live_candidates": live_scan.get("candidates", []),
            },
            remediation="Collect accepted replay-verified demonstrations that include approach/contact/insert/seat transitions.",
        ),
        gate(
            "stronger_policy_trainer",
            _stronger_policy_or_trainer(measurement_report),
            required=False,
            evidence={
                "report_path": result_report_path,
                "baseline": None if measurement_report is None else measurement_report.get("baseline"),
                "candidate": None if measurement_report is None else measurement_report.get("candidate"),
            },
            remediation="Use a policy/trainer stronger than the current smoke-grade linear BC path before claiming learning-proven.",
        ),
        gate(
            "heldout_policy_ab_recorded",
            heldout_recorded,
            required=False,
            evidence=_policy_uplift_evidence(learning, learning_manifest_path),
            remediation="Run and ingest held-out curated-vs-uncurated policy A/B evaluation.",
        ),
        gate(
            "curated_vs_uncurated_policy_uplift_positive",
            positive_uplift,
            required=False,
            evidence=_policy_uplift_evidence(learning, learning_manifest_path),
            remediation="Curated held-out policy success rate must exceed the uncurated baseline.",
        ),
        gate(
            "positive_or_negative_result_report",
            heldout_recorded and result_report_exists,
            required=False,
            evidence={
                "report_path": result_report_path,
                "exists": result_report_exists,
                "result": "positive" if positive_uplift else "negative" if negative_evidence else "not_measured",
            },
            remediation="Keep a positive or negative policy A/B result report.",
        ),
    ]
    return {
        "scope": "MVP-2 Policy Uplift Proof",
        "learning_proven": positive_uplift,
        "negative_evidence_recorded": negative_evidence,
        "policy_uplift_not_required_for_mvp1": True,
        "gates": [
            {
                "name": item.name,
                "passed": item.passed,
                "required_for_mvp1": False,
                "evidence": item.evidence,
                "remediation": item.remediation,
            }
            for item in gates
        ],
        "summary": {
            "heldout_policy_ab_recorded": heldout_recorded,
            "curated_vs_uncurated_uplift": None if learning is None else learning.get("curated_vs_uncurated_uplift"),
            "proof_eligible": measurement.get("proof_eligible"),
            "evidence_tier": measurement.get("evidence_tier"),
            "primary_metric": measurement.get("primary_metric"),
            "negative_result_report": "preserved" if negative_evidence else "not_applicable",
        },
    }


def build_mvp2_policy_ab_harness_summary(report_path: Path | None) -> dict[str, Any]:
    if report_path is None:
        return {
            "available": False,
            "path": None,
            "harness_ready": False,
            "rollout_ingest_contract_ready": False,
            "learning_results_measured": False,
            "learning_proven": False,
            "proof_eligible": False,
            "adapter_id": None,
            "source_evidence_type": None,
            "policy_uplift_not_claimed": True,
            "limitations": ["MVP-2 policy A/B harness report path was not provided."],
        }

    report = read_json(report_path)
    if report is None:
        return {
            "available": False,
            "path": str(report_path),
            "harness_ready": False,
            "rollout_ingest_contract_ready": False,
            "learning_results_measured": False,
            "learning_proven": False,
            "proof_eligible": False,
            "adapter_id": None,
            "source_evidence_type": None,
            "policy_uplift_not_claimed": True,
            "limitations": ["MVP-2 policy A/B harness report is missing or invalid JSON."],
        }

    proof_source = report.get("proof_source") if isinstance(report.get("proof_source"), dict) else {}
    claim_boundary = report.get("claim_boundary") if isinstance(report.get("claim_boundary"), dict) else {}
    return {
        "available": True,
        "path": str(report_path),
        "schema_version": report.get("schema_version"),
        "harness_ready": report.get("harness_ready") is True,
        "rollout_ingest_contract_ready": report.get("rollout_ingest_contract_ready") is True,
        "learning_results_measured": report.get("learning_results_measured") is True,
        "curated_vs_uncurated_uplift": report.get("curated_vs_uncurated_uplift"),
        "learning_proven": report.get("learning_proven") is True,
        "proof_eligible": report.get("proof_eligible") is True,
        "adapter_id": proof_source.get("adapter_id"),
        "source_evidence_type": proof_source.get("source_evidence_type"),
        "validator_backend": proof_source.get("validator_backend"),
        "policy_uplift_not_claimed": claim_boundary.get("policy_uplift_claimed") is False,
        "limitations": report.get("limitations") if isinstance(report.get("limitations"), list) else [],
    }


def _stage_passed(gate_map: dict[str, Gate], gate_names: tuple[str, ...]) -> bool:
    return all(gate_map.get(name) is not None and gate_map[name].passed for name in gate_names)


def build_staged_status(gates: list[Gate]) -> dict[str, Any]:
    gate_map = {item.name: item for item in gates}
    offline_ready = _stage_passed(gate_map, SUPPORTING_OFFLINE_GATE_NAMES)
    mvp1a = _stage_passed(gate_map, MVP1A_GATE_NAMES)
    mvp1 = _stage_passed(gate_map, MVP1_DATASET_PIPELINE_GATE_NAMES)

    if mvp1:
        current_stage = "MVP-1"
        next_stage = "MVP-2"
    elif mvp1a:
        current_stage = "MVP-1A"
        next_stage = "MVP-1"
    elif offline_ready:
        current_stage = "offline_readiness"
        next_stage = "MVP-1A"
    else:
        current_stage = "pre_readiness"
        next_stage = "offline_readiness"

    stages = {
        "offline_readiness": {
            "passed": offline_ready,
            "gate_names": list(SUPPORTING_OFFLINE_GATE_NAMES),
        },
        "MVP-1A": {
            "passed": mvp1a,
            "goal": "Raw XR/HMD insertion trajectory is saved with task state, task outcome, data quality, replay/action gate, and separated operator/evaluator success.",
            "gate_names": list(MVP1A_GATE_NAMES),
        },
        "MVP-1": {
            "passed": mvp1,
            "goal": "Learning-ready Validated Dataset Pipeline Proof.",
            "gate_names": list(MVP1_DATASET_PIPELINE_GATE_NAMES),
        },
        "MVP-1B": {
            "passed": mvp1,
            "deprecated_alias_for": "MVP-1",
            "goal": "Legacy alias. MVP-1B now maps to learning-ready dataset-pipeline proof, not policy uplift.",
            "gate_names": list(MVP1_DATASET_PIPELINE_GATE_NAMES),
        },
    }
    return {
        "proof_model": "learning_ready_dataset_pipeline",
        "current_stage": current_stage,
        "next_stage": next_stage,
        "legacy_current_stage_alias": "MVP-1B" if current_stage == "MVP-1" else current_stage,
        "stages": stages,
    }


def build_audit(
    *,
    readiness_report_path: Path,
    curation_manifest_path: Path,
    split_manifest_path: Path,
    dataset_card_path: Path,
    hdf5_inspection_path: Path,
    trajectory_dir: Path,
    learning_manifest_path: Path,
    output_path: Path | None = None,
    min_live_trajectories: int = 1,
    mvp2_policy_ab_harness_report_path: Path | None = None,
) -> dict[str, Any]:
    readiness = read_json(readiness_report_path)
    curation = read_json(curation_manifest_path)
    split = read_json(split_manifest_path)
    card = read_json(dataset_card_path)
    hdf5 = read_json(hdf5_inspection_path)
    learning = read_json(learning_manifest_path)
    live_scan = scan_live_insertion_trajectories(trajectory_dir)
    live_export, live_export_path = _load_live_export_report(learning)
    live_dataset = _live_dataset_evidence(live_export=live_export, live_export_path=live_export_path, learning=learning)

    phase_coverage = set(readiness.get("phase_coverage", [])) if readiness else set()
    curation_rules = curation.get("curation_rules", {}) if curation else {}
    learning_measured = bool((learning or {}).get("learning_results_measured"))
    uplift = (learning or {}).get("curated_vs_uncurated_uplift")
    policy_uplift_ready = _policy_uplift_ready(learning)
    heldout_policy_measurement_recorded = _heldout_policy_measurement_recorded(learning)
    trainer_ready = _trainer_dry_run_ready(learning)

    gates = [
        gate(
            "offline_readiness_passed",
            bool(readiness and readiness.get("passed") is True),
            required=False,
            evidence={"path": str(readiness_report_path), "passed": None if readiness is None else readiness.get("passed")},
            remediation="Run scripts/run_mvp1_offline_readiness.py --clean.",
        ),
        gate(
            "mvp1_phase_coverage_ready",
            REQUIRED_PHASES.issubset(phase_coverage),
            required=False,
            evidence={"required_phases": sorted(REQUIRED_PHASES), "observed_phases": sorted(phase_coverage)},
            remediation="Provide APPROACH/ALIGN/CONTACT/INSERT/SEAT/RELEASE phase metadata.",
        ),
        gate(
            "legacy_curation_manifest_ready",
            bool(curation and curation.get("accepted_count", 0) > 0 and curation.get("rejected_count", 0) > 0),
            required=False,
            evidence={
                "path": str(curation_manifest_path),
                "accepted_count": None if curation is None else curation.get("accepted_count"),
                "rejected_count": None if curation is None else curation.get("rejected_count"),
                "curation_rules": curation_rules,
            },
            remediation="Generate accepted/rejected curation manifest with rejection reasons.",
        ),
        gate(
            "split_manifest_ready",
            bool(split and all((split.get("splits") or {}).get(name) for name in ("train", "validation", "test"))),
            required=False,
            evidence={"path": str(split_manifest_path), "splits": None if split is None else split.get("splits")},
            remediation="Generate deterministic train/validation/test split manifest.",
        ),
        gate(
            "legacy_dataset_card_ready",
            bool(card and card.get("num_accepted", 0) > 0 and card.get("task_type") == "peg_in_hole"),
            required=False,
            evidence={
                "path": str(dataset_card_path),
                "task_type": None if card is None else card.get("task_type"),
                "num_accepted": None if card is None else card.get("num_accepted"),
            },
            remediation="Generate dataset card for MVP-1 insertion dataset.",
        ),
        gate(
            "legacy_hdf5_sanity_ready",
            bool(hdf5 and not hdf5.get("issues") and hdf5.get("episode_count", 0) > 0),
            required=False,
            evidence={
                "path": str(hdf5_inspection_path),
                "episode_count": None if hdf5 is None else hdf5.get("episode_count"),
                "issues": None if hdf5 is None else hdf5.get("issues"),
                "warnings": None if hdf5 is None else hdf5.get("warnings"),
            },
            remediation="Run HDF5 export and inspect_rdf_hdf5.py until issues are empty.",
        ),
        gate(
            "policy_claim_integrity_preserved",
            bool(
                learning
                and (
                    policy_uplift_ready
                    or heldout_policy_measurement_recorded
                    or (learning_measured is False and uplift is None)
                )
            ),
            evidence={
                "path": str(learning_manifest_path),
                "learning_results_measured": None if learning is None else learning.get("learning_results_measured"),
                "curated_vs_uncurated_uplift": None if learning is None else learning.get("curated_vs_uncurated_uplift"),
                "policy_uplift_proof_eligible": _policy_uplift_measurement(learning).get("proof_eligible"),
                "policy_uplift_evidence_tier": _policy_uplift_measurement(learning).get("evidence_tier"),
            },
            remediation="Use null uplift until a real policy A/B evaluation has been measured.",
        ),
        gate(
            "raw_xr_trajectory_saved",
            live_scan["candidate_count"] >= min_live_trajectories,
            evidence={**live_scan, "min_live_trajectories": min_live_trajectories},
            remediation="Collect real Quest/SteamVR/Isaac peg-in-hole or connector trajectories with metadata.task_state.",
        ),
        gate(
            "task_state_extracted",
            live_scan["candidate_count"] >= min_live_trajectories
            and any(item.get("has_task_state") is True for item in live_scan.get("candidates", [])),
            evidence={**live_scan, "min_live_trajectories": min_live_trajectories},
            remediation="Extract task_state into trajectory frames before treating XR data as validated dataset material.",
        ),
        gate(
            "task_outcome_recorded",
            live_dataset["task_outcome_recorded"] is True,
            evidence=live_dataset,
            remediation="Run live export/evaluation so task_outcome records operator_success and evaluator_task_success.",
        ),
        gate(
            "data_quality_recorded",
            live_dataset["data_quality_recorded"] is True,
            evidence=live_dataset,
            remediation="Run live evaluation/curation so data_quality records action contract, replay, sync, and control status.",
        ),
        gate(
            "operator_success_separated_from_evaluator_task_success",
            live_dataset["operator_success_separated_from_evaluator_task_success"] is True,
            evidence=live_dataset,
            remediation="Preserve operator_success separately from evaluator_task_success in task_outcome.",
        ),
        gate(
            "replay_action_gate_recorded",
            live_dataset["replay_action_gate_recorded"] is True,
            evidence=live_dataset,
            remediation="Record action contract and replay gate status before curated promotion.",
        ),
        gate(
            "accepted_rejected_curation_manifest_generated",
            bool(curation and curation.get("accepted_count", 0) > 0 and curation.get("rejected_count", 0) > 0),
            evidence={
                "path": str(curation_manifest_path),
                "accepted_count": None if curation is None else curation.get("accepted_count"),
                "rejected_count": None if curation is None else curation.get("rejected_count"),
                "rejection_reason_distribution": None if curation is None else curation.get("rejection_reason_distribution"),
            },
            remediation="Generate accepted/rejected curation manifest with rejection reasons.",
        ),
        gate(
            "hdf5_export_generated",
            bool(hdf5 and not hdf5.get("issues") and hdf5.get("episode_count", 0) > 0),
            evidence={
                "path": str(hdf5_inspection_path),
                "episode_count": None if hdf5 is None else hdf5.get("episode_count"),
                "issues": None if hdf5 is None else hdf5.get("issues"),
                "warnings": None if hdf5 is None else hdf5.get("warnings"),
            },
            remediation="Generate and inspect HDF5 export until issues are empty.",
        ),
        gate(
            "trainer_loader_smoke_passed",
            trainer_ready,
            evidence=_training_readiness_evidence(learning, learning_manifest_path),
            remediation="Run exported dataset through a real trainer loader plus dry-run or one epoch smoke before claiming MVP-1.",
        ),
        gate(
            "dataset_card_generated",
            bool(card and card.get("task_type") == "peg_in_hole" and (card.get("num_accepted", 0) > 0 or card.get("num_live_trajectories", 0) > 0)),
            evidence={
                "path": str(dataset_card_path),
                "task_type": None if card is None else card.get("task_type"),
                "num_accepted": None if card is None else card.get("num_accepted"),
                "num_live_trajectories": None if card is None else card.get("num_live_trajectories"),
            },
            remediation="Generate dataset card for the exported MVP-1 insertion dataset artifact.",
        ),
        gate(
            "no_fake_learning_uplift",
            bool(
                learning
                and (
                    policy_uplift_ready
                    or heldout_policy_measurement_recorded
                    or (learning_measured is False and uplift is None)
                )
            ),
            required=False,
            evidence={
                "path": str(learning_manifest_path),
                "learning_results_measured": None if learning is None else learning.get("learning_results_measured"),
                "curated_vs_uncurated_uplift": None if learning is None else learning.get("curated_vs_uncurated_uplift"),
                "policy_uplift_proof_eligible": _policy_uplift_measurement(learning).get("proof_eligible"),
                "policy_uplift_evidence_tier": _policy_uplift_measurement(learning).get("evidence_tier"),
            },
            remediation="Use null uplift until a real policy A/B evaluation has been measured.",
        ),
        gate(
            "curated_vs_uncurated_policy_uplift_measured",
            policy_uplift_ready,
            required=False,
            evidence=_policy_uplift_evidence(learning, learning_manifest_path),
            remediation="MVP-2 only: train/evaluate uncurated vs curated policies on held-out insertion suite before claiming learning-proven uplift.",
        ),
    ]

    required_gates = [item for item in gates if item.required_for_full_proof]
    passed_required = [item for item in required_gates if item.passed]
    missing_required = [item for item in required_gates if not item.passed]
    status = "pass" if not missing_required else "partial" if passed_required else "fail"
    staged_status = build_staged_status(gates)
    mvp2_status = build_mvp2_policy_uplift_status(
        learning=learning,
        learning_manifest_path=learning_manifest_path,
        live_scan=live_scan,
    )
    mvp2_harness = build_mvp2_policy_ab_harness_summary(mvp2_policy_ab_harness_report_path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "proof_name": "MVP-1 Validated Dataset Pipeline Proof",
        "proof_model": "learning_ready_dataset_pipeline",
        "status": status,
        "full_mvp1_proof_achieved": status == "pass",
        "mvp1_dataset_pipeline_proof_achieved": status == "pass",
        "learning_ready_dataset_artifact": status == "pass",
        "policy_uplift_required_for_mvp1": False,
        "learning_proven_policy_uplift_achieved": mvp2_status["learning_proven"],
        "staged_mvp1": staged_status,
        "mvp2_policy_uplift_proof": mvp2_status,
        "mvp2_policy_ab_harness": mvp2_harness,
        "passed_required_gates": len(passed_required),
        "required_gate_count": len(required_gates),
        "gates": [
            {
                "name": item.name,
                "passed": item.passed,
                "required_for_full_proof": item.required_for_full_proof,
                "evidence": item.evidence,
                "remediation": item.remediation,
            }
            for item in gates
        ],
        "missing_required_gates": [
            {
                "name": item.name,
                "remediation": item.remediation,
            }
            for item in missing_required
        ],
        "summary": {
            "offline_readiness_is_usable_evidence": bool(readiness and readiness.get("passed") is True),
            "live_insertion_evidence_count": live_scan["candidate_count"],
            "trainer_dry_run_passed": trainer_ready,
            "learning_ready": status == "pass",
            "learning_proven": mvp2_status["learning_proven"],
            "heldout_policy_ab_recorded": heldout_policy_measurement_recorded,
            "policy_uplift_positive": policy_uplift_ready,
            "policy_uplift_negative_evidence_recorded": mvp2_status["negative_evidence_recorded"],
            "policy_uplift_not_required_for_mvp1": True,
            "do_not_claim_full_mvp1": bool(missing_required),
            "do_not_claim_policy_uplift": not mvp2_status["learning_proven"],
        },
    }
    if output_path is not None:
        write_json(output_path, report)
    return report


def parse_args() -> argparse.Namespace:
    default_root = ROOT / "storage" / "mvp1_readiness"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-report", type=Path, default=default_root / "readiness_report.json")
    parser.add_argument("--curation-manifest", type=Path, default=default_root / "curation_manifest.json")
    parser.add_argument("--split-manifest", type=Path, default=default_root / "split_manifest.json")
    parser.add_argument("--dataset-card", type=Path, default=default_root / "dataset_card.json")
    parser.add_argument("--hdf5-inspection", type=Path, default=default_root / "hdf5_inspection.json")
    parser.add_argument("--trajectory-dir", type=Path, default=ROOT / "storage" / "trajectories")
    parser.add_argument(
        "--learning-manifest",
        type=Path,
        default=default_root / "curated_vs_uncurated_experiment_manifest.json",
    )
    parser.add_argument(
        "--mvp2-policy-ab-harness-report",
        type=Path,
        default=ROOT / "storage" / "mvp2_policy_ab_harness" / "mvp2_policy_ab_harness_report.json",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "storage" / "mvp1_proof" / "proof_audit.json")
    parser.add_argument("--min-live-trajectories", type=int, default=1)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless MVP-1 learning-ready proof is achieved.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_audit(
        readiness_report_path=args.readiness_report,
        curation_manifest_path=args.curation_manifest,
        split_manifest_path=args.split_manifest,
        dataset_card_path=args.dataset_card,
        hdf5_inspection_path=args.hdf5_inspection,
        trajectory_dir=args.trajectory_dir,
        learning_manifest_path=args.learning_manifest,
        output_path=args.output,
        min_live_trajectories=args.min_live_trajectories,
        mvp2_policy_ab_harness_report_path=args.mvp2_policy_ab_harness_report,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        print(f"RDF MVP-1 proof audit: {report['status'].upper()}")
        print(f"proof_model={report['proof_model']}")
        print(f"stage={report['staged_mvp1']['current_stage']}")
        print(f"next_stage={report['staged_mvp1']['next_stage']}")
        print(f"required_gates={report['passed_required_gates']}/{report['required_gate_count']}")
        print(f"policy_uplift_required_for_mvp1={report['policy_uplift_required_for_mvp1']}")
        print(f"learning_proven_policy_uplift_achieved={report['learning_proven_policy_uplift_achieved']}")
        for item in report["missing_required_gates"]:
            print(f"missing: {item['name']} - {item['remediation']}")
        print(f"output: {args.output}")
    return 1 if args.strict and not report["full_mvp1_proof_achieved"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
