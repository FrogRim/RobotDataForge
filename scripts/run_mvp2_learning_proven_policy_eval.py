#!/usr/bin/env python3
"""Close MVP-2 only when curated held-out policy success beats uncurated.

This script wraps the MVP-2 UR policy A/B harness, converts local-offline or
external rollout results into the existing held-out policy validator input, and
preserves the boundary that schema-only rollout fixtures cannot prove uplift.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
API_ROOT = ROOT / "apps" / "api"
for path in (SCRIPT_DIR, API_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_mvp1c_real_policy_eval import run_real_policy_eval  # noqa: E402
from run_mvp1c_rollout_result_adapter import build_policy_eval_input  # noqa: E402
from run_mvp1plus_embodiment_proof import DEFAULT_OUTPUT_DIR as DEFAULT_MVP1PLUS_OUTPUT_DIR  # noqa: E402
from run_mvp2_ur_policy_ab_harness import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as DEFAULT_HARNESS_OUTPUT_DIR,
    build_mvp2_ur_policy_ab_harness,
)


SCHEMA_VERSION = "rdf_mvp2_learning_proven_policy_eval_v0.1.0"
LOCAL_OFFLINE_ROLLOUT_SCHEMA_VERSION = "rdf_mvp2_local_offline_rollout_v0.1.0"
LOCAL_OFFLINE_HELDOUT_SUITE_SCHEMA_VERSION = "rdf_mvp2_local_offline_heldout_suite_v0.1.0"
LOCAL_OFFLINE_PROXY_KIND = "local_offline_policy_eval_proxy"
PHASE_CONDITIONED_LOCAL_PROXY_KIND = "local_phase_conditioned_policy_eval_proxy"
LEGACY_LOCAL_OFFLINE_KIND = "local_offline_heldout_policy_eval"
SCHEMA_ONLY_KIND = "schema_only_rollout_ingest_contract"
EXTERNAL_PROOF_KIND = "external_heldout_policy_eval"
EXTERNAL_TEMPLATE_KIND = "external_heldout_policy_eval_template"
PHASE_CONDITIONED_SUCCESS_LABEL_SOURCE = "phase_conditioned_heldout_task_state_eval"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_learning_proven_policy_eval"
REPORT_NAME = "mvp2_learning_proven_report.json"
POLICY_EVAL_INPUT_NAME = "mvp2_policy_eval_input.json"
POLICY_EVAL_REPORT_NAME = "mvp2_policy_eval_report.json"
LOCAL_OFFLINE_HELDOUT_SUITE_NAME = "mvp2_local_offline_heldout_suite_manifest.json"
EXTERNAL_PROOF_TEMPLATE_SCHEMA_VERSION = "rdf_mvp2_external_policy_eval_template_v0.1.0"
EXTERNAL_PROOF_TEMPLATE_DIR_NAME = "external_policy_eval_template"
EXTERNAL_PROOF_REQUEST_NAME = "external_policy_eval_request.json"
EXTERNAL_BASELINE_TEMPLATE_NAME = "baseline_external_rollouts.template.json"
EXTERNAL_CANDIDATE_TEMPLATE_NAME = "candidate_external_rollouts.template.json"
VALID_OFFLINE_PROFILES = {"positive", "negative", "tie"}


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_safe_clean_target(path: Path) -> bool:
    resolved = path.resolve()
    repo_root = ROOT.resolve()
    storage_root = (repo_root / "storage").resolve()
    tmp_root = Path("/tmp").resolve()
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root,
        repo_root.parent.resolve(),
        storage_root,
        tmp_root,
    }
    if resolved in forbidden:
        return False
    return _is_relative_to(resolved, storage_root) or _is_relative_to(resolved, tmp_root)


def _prepare_output_dir(output_dir: Path, *, clean: bool) -> None:
    if not _is_safe_clean_target(output_dir):
        raise ValueError(f"refusing unsafe MVP-2 learning-proven output path: {output_dir}")
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _load_or_refresh_harness(
    *,
    harness_output_dir: Path,
    mvp1plus_output_dir: Path,
    refresh_harness: bool,
    refresh_mvp1plus: bool,
) -> dict[str, Any]:
    report_path = harness_output_dir / "mvp2_policy_ab_harness_report.json"
    if refresh_harness or not report_path.exists():
        return build_mvp2_ur_policy_ab_harness(
            output_dir=harness_output_dir,
            mvp1plus_output_dir=mvp1plus_output_dir,
            clean=refresh_harness,
            refresh_mvp1plus=refresh_mvp1plus,
        )
    return read_json(report_path)


def _validate_harness_ready(harness_report: dict[str, Any]) -> None:
    if harness_report.get("passed") is not True or harness_report.get("harness_ready") is not True:
        raise ValueError("MVP-2 harness readiness gate failed")
    artifact_paths = harness_report.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        raise ValueError("MVP-2 harness readiness gate failed: artifact_paths missing")
    required_artifacts = (
        "policy_eval_input_template",
        "heldout_suite_manifest",
        "baseline_hdf5",
        "candidate_hdf5",
    )
    missing = [key for key in required_artifacts if not artifact_paths.get(key)]
    if missing:
        raise ValueError(f"MVP-2 harness readiness gate failed: missing artifacts {missing}")
    missing_files = [key for key in required_artifacts if not Path(str(artifact_paths[key])).exists()]
    if missing_files:
        raise ValueError(f"MVP-2 harness readiness gate failed: missing files {missing_files}")
    heldout_suite = harness_report.get("heldout_suite")
    if not isinstance(heldout_suite, dict) or heldout_suite.get("held_out") is not True:
        raise ValueError("MVP-2 harness readiness gate failed: heldout suite missing")
    scenario_ids = heldout_suite.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not scenario_ids:
        raise ValueError("MVP-2 harness readiness gate failed: heldout scenarios missing")


def _stable_unit_interval(text: str) -> float:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def _evaluation_files(view: dict[str, Any]) -> list[Path]:
    evaluations_dir = Path(str(view.get("evaluations_dir", "")))
    if not evaluations_dir.exists():
        return []
    return sorted(evaluations_dir.glob("*.json"))


def _data_quality_metrics(evaluation: dict[str, Any]) -> dict[str, Any]:
    metrics = evaluation.get("metrics")
    if isinstance(metrics, dict) and isinstance(metrics.get("data_quality"), dict):
        return dict(metrics["data_quality"])
    if isinstance(evaluation.get("data_quality"), dict):
        return dict(evaluation["data_quality"])
    if isinstance(evaluation.get("quality"), dict):
        return dict(evaluation["quality"])
    return {}


def _quality_passed(metrics: dict[str, Any]) -> bool:
    quality_fields = (
        "action_contract_valid",
        "replay_verified",
        "retargeting_jump",
        "native_action_saturation",
        "sync_quality",
        "control_quality",
    )
    observed = 0
    passed = 0
    for key in quality_fields:
        if key not in metrics:
            continue
        observed += 1
        value = metrics[key]
        if value is True or value == "pass":
            passed += 1
    if observed == 0:
        status = metrics.get("status") or metrics.get("quality_status")
        return status in {True, "pass", "accepted"}
    return passed == observed


def _quality_signal_rate(view: dict[str, Any]) -> float:
    evaluations = [read_json(path) for path in _evaluation_files(view)]
    if not evaluations:
        raise ValueError("MVP-2 local offline proxy requires evaluation files")
    passed = sum(1 for item in evaluations if _quality_passed(_data_quality_metrics(item)))
    return passed / len(evaluations)


def _profile_rates(
    *,
    harness_report: dict[str, Any],
    offline_profile: str,
) -> tuple[float, float, float, float]:
    if offline_profile not in VALID_OFFLINE_PROFILES:
        raise ValueError(f"offline_profile must be one of {sorted(VALID_OFFLINE_PROFILES)}")
    dataset_views = harness_report.get("dataset_views")
    if not isinstance(dataset_views, dict):
        raise ValueError("MVP-2 harness dataset_views missing")
    baseline_view = dataset_views.get("baseline")
    candidate_view = dataset_views.get("candidate")
    if not isinstance(baseline_view, dict) or not isinstance(candidate_view, dict):
        raise ValueError("MVP-2 harness baseline/candidate dataset views missing")
    baseline_quality_rate = _quality_signal_rate(baseline_view)
    candidate_quality_rate = _quality_signal_rate(candidate_view)
    if offline_profile == "positive":
        return baseline_quality_rate, candidate_quality_rate, baseline_quality_rate, candidate_quality_rate
    if offline_profile == "negative":
        return candidate_quality_rate, baseline_quality_rate, baseline_quality_rate, candidate_quality_rate
    return 0.6, 0.6, baseline_quality_rate, candidate_quality_rate


def _rollout_success(*, policy_quality_rate: float, scenario_id: str, rollout_index: int) -> bool:
    difficulty = 0.15 + 0.7 * _stable_unit_interval(f"{scenario_id}:{rollout_index}")
    return policy_quality_rate >= difficulty


def _build_rollouts(
    *,
    policy_role: str,
    policy_quality_rate: float,
    scenario_ids: list[str],
    rollout_count: int,
) -> list[dict[str, Any]]:
    rollouts: list[dict[str, Any]] = []
    for index in range(rollout_count):
        scenario_id = scenario_ids[index % len(scenario_ids)]
        success = _rollout_success(
            policy_quality_rate=policy_quality_rate,
            scenario_id=scenario_id,
            rollout_index=index,
        )
        rollouts.append(
            {
                "rollout_id": f"{policy_role}_local_offline_{index:04d}",
                "scenario_id": scenario_id,
                "success": success,
                "success_label_source": "deterministic_dataset_quality_signal",
                "policy_quality_signal": policy_quality_rate,
                "not_physical_or_isaac_evidence": True,
            }
        )
    return rollouts


def _write_local_offline_heldout_suite(output_dir: Path, harness_report: dict[str, Any]) -> dict[str, Any]:
    heldout_suite = harness_report["heldout_suite"]
    scenario_ids = [str(item) for item in heldout_suite.get("scenario_ids", [])]
    local_suite = {
        "schema_version": LOCAL_OFFLINE_HELDOUT_SUITE_SCHEMA_VERSION,
        "id": "mvp2_local_offline_ur_policy_eval_suite",
        "held_out": True,
        "task_type": heldout_suite.get("task_type", "connector_insertion"),
        "scenario_ids": scenario_ids,
        "source_kind": "local_offline_derived_from_harness_template",
        "proof_role": "local_offline_policy_eval_suite",
        "not_physical_or_isaac_evidence": True,
        "limitations": [
            "Local-offline rollouts are deterministic evidence derived from recorded-log harness quality signals.",
            "This is not real robot or Isaac rollout evidence.",
        ],
    }
    path = output_dir / LOCAL_OFFLINE_HELDOUT_SUITE_NAME
    write_json(path, local_suite)
    local_suite["path"] = str(path)
    return local_suite


def _write_local_offline_rollouts(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    offline_profile: str,
    min_rollouts_per_policy: int,
) -> dict[str, Any]:
    baseline_rate, candidate_rate, baseline_quality_rate, candidate_quality_rate = _profile_rates(
        harness_report=harness_report,
        offline_profile=offline_profile,
    )
    heldout_suite = _write_local_offline_heldout_suite(output_dir, harness_report)
    scenario_ids = [str(item) for item in heldout_suite["scenario_ids"]]
    rollout_count = max(min_rollouts_per_policy, len(scenario_ids), 10)
    baseline_rollouts = _build_rollouts(
        policy_role="baseline_uncurated",
        policy_quality_rate=baseline_rate,
        scenario_ids=scenario_ids,
        rollout_count=rollout_count,
    )
    candidate_rollouts = _build_rollouts(
        policy_role="candidate_curated",
        policy_quality_rate=candidate_rate,
        scenario_ids=scenario_ids,
        rollout_count=rollout_count,
    )
    baseline_path = output_dir / "baseline_local_offline_rollouts.json"
    candidate_path = output_dir / "candidate_local_offline_rollouts.json"
    baseline_payload = {
        "schema_version": LOCAL_OFFLINE_ROLLOUT_SCHEMA_VERSION,
        "source_kind": LOCAL_OFFLINE_PROXY_KIND,
        "rollout_generation_method": "quality_weighted_local_offline_runner",
        "offline_profile": offline_profile,
        "success_label_source": "deterministic_dataset_quality_signal",
        "heldout_suite_path": heldout_suite["path"],
        "rollout_results": baseline_rollouts,
    }
    candidate_payload = {
        "schema_version": LOCAL_OFFLINE_ROLLOUT_SCHEMA_VERSION,
        "source_kind": LOCAL_OFFLINE_PROXY_KIND,
        "rollout_generation_method": "quality_weighted_local_offline_runner",
        "offline_profile": offline_profile,
        "success_label_source": "deterministic_dataset_quality_signal",
        "heldout_suite_path": heldout_suite["path"],
        "rollout_results": candidate_rollouts,
    }
    write_json(baseline_path, baseline_payload)
    write_json(candidate_path, candidate_payload)
    return {
        "source_kind": LOCAL_OFFLINE_PROXY_KIND,
        "offline_profile": offline_profile,
        "rollout_generation_method": "quality_weighted_local_offline_runner",
        "success_label_source": "deterministic_dataset_quality_signal",
        "baseline_quality_signal_rate": baseline_quality_rate,
        "candidate_quality_signal_rate": candidate_quality_rate,
        "baseline_policy_quality_signal": baseline_rate,
        "candidate_policy_quality_signal": candidate_rate,
        "baseline_results_path": str(baseline_path),
        "candidate_results_path": str(candidate_path),
        "heldout_suite": heldout_suite,
        "rollout_count_per_policy": rollout_count,
    }


def _rollout_payload(path: Path) -> dict[str, Any] | None:
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _rollout_payload_marker(path: Path) -> str | None:
    payload = _rollout_payload(path)
    if payload is None:
        return None
    for key in ("fixture_kind", "source_kind"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _rollout_items(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in ("rollout_results", "rollouts", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _rollout_success_rate_from_payload(payload: dict[str, Any] | None) -> float | None:
    rollouts = _rollout_items(payload)
    if not rollouts:
        return None
    parsed: list[bool] = []
    for rollout in rollouts:
        value = rollout.get("success")
        if isinstance(value, bool):
            parsed.append(value)
    if not parsed:
        return None
    return sum(1 for item in parsed if item) / len(parsed)


def _contains_schema_like_rollout_ids(payload: dict[str, Any] | None) -> bool:
    for rollout in _rollout_items(payload):
        rollout_id = str(rollout.get("rollout_id") or rollout.get("id") or "").lower()
        if "schema_" in rollout_id or rollout_id.startswith("schema"):
            return True
    return False


def _contains_deterministic_success_labels(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("success_label_source") == "deterministic_dataset_quality_signal":
        return True
    return any(
        rollout.get("success_label_source") == "deterministic_dataset_quality_signal"
        for rollout in _rollout_items(payload)
    )


def _contains_phase_conditioned_proxy_labels(payload: dict[str, Any] | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("source_kind") == PHASE_CONDITIONED_LOCAL_PROXY_KIND:
        return True
    if payload.get("success_label_source") == PHASE_CONDITIONED_SUCCESS_LABEL_SOURCE:
        return True
    if isinstance(payload.get("training_material_summary"), dict):
        return True
    return any(
        rollout.get("success_label_source") == PHASE_CONDITIONED_SUCCESS_LABEL_SOURCE
        or any(key in rollout for key in ("policy_score", "scenario_difficulty", "success_margin"))
        for rollout in _rollout_items(payload)
    )


def _same_heldout_suite(baseline_suite: dict[str, Any], candidate_suite: dict[str, Any]) -> bool:
    comparable_keys = ("id", "task_type", "held_out", "scenario_ids", "source_kind", "proof_role")
    return all(baseline_suite.get(key) == candidate_suite.get(key) for key in comparable_keys)


def _external_proof_blockers(
    baseline_payload: dict[str, Any] | None,
    candidate_payload: dict[str, Any] | None,
) -> list[str]:
    blockers: list[str] = []
    for role, payload in (("baseline", baseline_payload), ("candidate", candidate_payload)):
        if not isinstance(payload, dict):
            blockers.append(f"{role} rollout results must be JSON objects with proof-grade provenance.")
            continue
        if payload.get("source_kind") != EXTERNAL_PROOF_KIND:
            blockers.append(f"{role} source_kind must be {EXTERNAL_PROOF_KIND}.")
        if payload.get("proof_role") != "external_trainer_policy_eval":
            blockers.append(f"{role} proof_role must be external_trainer_policy_eval.")
        for key in (
            "policy_artifact_id",
            "policy_artifact_sha256",
            "training_artifact_sha256",
            "trainer",
            "eval_runner",
        ):
            if not isinstance(payload.get(key), str) or not payload.get(key):
                blockers.append(f"{role} {key} is required for proof-grade external evidence.")
        evaluator_run = payload.get("external_evaluator_run")
        if not isinstance(evaluator_run, dict):
            blockers.append(f"{role} external_evaluator_run is required for proof-grade external evidence.")
        else:
            for key in ("run_id", "runner_version", "run_log_uri"):
                if not isinstance(evaluator_run.get(key), str) or not evaluator_run.get(key):
                    blockers.append(f"{role} external_evaluator_run.{key} is required.")
            if evaluator_run.get("generated_outside_rdf_local_proxy") is not True:
                blockers.append(f"{role} external_evaluator_run.generated_outside_rdf_local_proxy must be true.")
        heldout_suite = payload.get("heldout_suite")
        if not isinstance(heldout_suite, dict):
            blockers.append(f"{role} heldout_suite is required for proof-grade external evidence.")
            continue
        if heldout_suite.get("held_out") is not True:
            blockers.append(f"{role} heldout_suite.held_out must be true.")
        if not isinstance(heldout_suite.get("id"), str) or not heldout_suite.get("id"):
            blockers.append(f"{role} heldout_suite.id is required.")
        elif "schema_only" in str(heldout_suite.get("id")).lower():
            blockers.append(f"{role} heldout_suite.id cannot be schema-only.")
        if heldout_suite.get("source_kind") != "external_trainer_eval_suite":
            blockers.append(f"{role} heldout_suite.source_kind must be external_trainer_eval_suite.")
        if heldout_suite.get("proof_role") != "external_policy_eval_suite":
            blockers.append(f"{role} heldout_suite.proof_role must be external_policy_eval_suite.")
        if not isinstance(heldout_suite.get("scenario_set_sha256"), str) or not heldout_suite.get("scenario_set_sha256"):
            blockers.append(f"{role} heldout_suite.scenario_set_sha256 is required.")
        if not isinstance(heldout_suite.get("scenario_ids"), list) or not heldout_suite.get("scenario_ids"):
            blockers.append(f"{role} heldout_suite.scenario_ids must be non-empty.")
        elif any("schema_only" in str(item).lower() for item in heldout_suite.get("scenario_ids", [])):
            blockers.append(f"{role} heldout_suite.scenario_ids cannot be schema-only.")
        rollout_items = _rollout_items(payload)
        if not rollout_items:
            blockers.append(f"{role} rollout_results are required.")
        elif any(not isinstance(item.get("rollout_log_ref"), str) or not item.get("rollout_log_ref") for item in rollout_items):
            blockers.append(f"{role} every rollout_result must include rollout_log_ref.")
    if isinstance(baseline_payload, dict) and isinstance(candidate_payload, dict):
        baseline_suite = baseline_payload.get("heldout_suite")
        candidate_suite = candidate_payload.get("heldout_suite")
        if isinstance(baseline_suite, dict) and isinstance(candidate_suite, dict):
            if not _same_heldout_suite(baseline_suite, candidate_suite):
                blockers.append("baseline and candidate must use the same external held-out suite.")
    return blockers


def _external_rollout_source(
    baseline_results_path: Path,
    candidate_results_path: Path,
) -> dict[str, Any]:
    baseline_payload = _rollout_payload(baseline_results_path)
    candidate_payload = _rollout_payload(candidate_results_path)
    markers = {
        _rollout_payload_marker(baseline_results_path),
        _rollout_payload_marker(candidate_results_path),
    }
    markers.discard(None)
    source = {
        "source_kind": "external_rollout_results",
        "baseline_results_path": str(baseline_results_path),
        "candidate_results_path": str(candidate_results_path),
        "content_markers_checked": True,
        "baseline_marker": _rollout_payload_marker(baseline_results_path),
        "candidate_marker": _rollout_payload_marker(candidate_results_path),
        "baseline_success_rate": _rollout_success_rate_from_payload(baseline_payload),
        "candidate_success_rate": _rollout_success_rate_from_payload(candidate_payload),
        "promotion_blockers": [],
    }

    if SCHEMA_ONLY_KIND in markers:
        source["source_kind"] = SCHEMA_ONLY_KIND
        source["promotion_blockers"] = ["Schema-only rollout ingest fixture cannot close MVP-2."]
        return source

    if _contains_schema_like_rollout_ids(baseline_payload) or _contains_schema_like_rollout_ids(candidate_payload):
        source["source_kind"] = "schema_like_rollout_results"
        source["promotion_blockers"] = ["Schema-like rollout identifiers cannot close MVP-2."]
        return source

    if (
        LOCAL_OFFLINE_PROXY_KIND in markers
        or PHASE_CONDITIONED_LOCAL_PROXY_KIND in markers
        or LEGACY_LOCAL_OFFLINE_KIND in markers
        or _contains_deterministic_success_labels(baseline_payload)
        or _contains_deterministic_success_labels(candidate_payload)
        or _contains_phase_conditioned_proxy_labels(baseline_payload)
        or _contains_phase_conditioned_proxy_labels(candidate_payload)
    ):
        source["source_kind"] = (
            PHASE_CONDITIONED_LOCAL_PROXY_KIND
            if PHASE_CONDITIONED_LOCAL_PROXY_KIND in markers
            or _contains_phase_conditioned_proxy_labels(baseline_payload)
            or _contains_phase_conditioned_proxy_labels(candidate_payload)
            else LOCAL_OFFLINE_PROXY_KIND
        )
        if source["source_kind"] == PHASE_CONDITIONED_LOCAL_PROXY_KIND:
            source["success_label_source"] = PHASE_CONDITIONED_SUCCESS_LABEL_SOURCE
            source["rollout_generation_method"] = "phase_conditioned_local_task_state_evaluator"
            if isinstance(baseline_payload, dict) and isinstance(baseline_payload.get("heldout_suite"), dict):
                source["heldout_suite"] = baseline_payload["heldout_suite"]
        source["promotion_blockers"] = [
            "Phase-conditioned local evaluator proxy cannot close MVP-2."
            if source["source_kind"] == PHASE_CONDITIONED_LOCAL_PROXY_KIND
            else "Local offline deterministic proxy cannot close MVP-2."
        ]
        return source

    proof_blockers = _external_proof_blockers(baseline_payload, candidate_payload)
    if proof_blockers:
        source["promotion_blockers"] = [
            "External rollout results are missing proof-grade provenance: " + "; ".join(proof_blockers)
        ]
        return source

    assert isinstance(baseline_payload, dict)
    assert isinstance(candidate_payload, dict)
    heldout_suite = dict(baseline_payload["heldout_suite"])
    source.update(
        {
            "source_kind": EXTERNAL_PROOF_KIND,
            "proof_grade": True,
            "heldout_suite": heldout_suite,
            "baseline_policy_artifact_id": baseline_payload.get("policy_artifact_id"),
            "candidate_policy_artifact_id": candidate_payload.get("policy_artifact_id"),
            "baseline_policy_artifact_sha256": baseline_payload.get("policy_artifact_sha256"),
            "candidate_policy_artifact_sha256": candidate_payload.get("policy_artifact_sha256"),
            "baseline_training_artifact_sha256": baseline_payload.get("training_artifact_sha256"),
            "candidate_training_artifact_sha256": candidate_payload.get("training_artifact_sha256"),
            "baseline_external_evaluator_run": baseline_payload.get("external_evaluator_run"),
            "candidate_external_evaluator_run": candidate_payload.get("external_evaluator_run"),
            "baseline_trainer": baseline_payload.get("trainer"),
            "candidate_trainer": candidate_payload.get("trainer"),
            "baseline_eval_runner": baseline_payload.get("eval_runner"),
            "candidate_eval_runner": candidate_payload.get("eval_runner"),
            "promotion_blockers": [],
        }
    )
    return source


def _rollout_source(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    offline_profile: str,
    baseline_results_path: Path | None,
    candidate_results_path: Path | None,
    min_rollouts_per_policy: int,
) -> dict[str, Any]:
    if baseline_results_path is None and candidate_results_path is None:
        return _write_local_offline_rollouts(
            output_dir=output_dir,
            harness_report=harness_report,
            offline_profile=offline_profile,
            min_rollouts_per_policy=min_rollouts_per_policy,
        )
    if baseline_results_path is None or candidate_results_path is None:
        raise ValueError("baseline_results_path and candidate_results_path must be provided together")
    return _external_rollout_source(baseline_results_path, candidate_results_path)


def _policy_provenance(policy_report: dict[str, Any]) -> dict[str, Any]:
    baseline = policy_report.get("baseline") if isinstance(policy_report.get("baseline"), dict) else {}
    candidate = policy_report.get("candidate") if isinstance(policy_report.get("candidate"), dict) else {}
    return {
        "baseline": {
            "name": baseline.get("name"),
            "policy_id": baseline.get("policy_id"),
            "dataset_id": baseline.get("dataset_id"),
            "dataset_view": baseline.get("dataset_view"),
            "policy_class": baseline.get("policy_class"),
            "trainer": baseline.get("trainer"),
        },
        "candidate": {
            "name": candidate.get("name"),
            "policy_id": candidate.get("policy_id"),
            "dataset_id": candidate.get("dataset_id"),
            "dataset_view": candidate.get("dataset_view"),
            "policy_class": candidate.get("policy_class"),
            "trainer": candidate.get("trainer"),
        },
    }


def _blockers(policy_report: dict[str, Any], rollout_source: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if rollout_source.get("source_kind") == SCHEMA_ONLY_KIND:
        blockers.append("Schema-only rollout ingest fixture cannot close MVP-2.")
    if policy_report.get("passed") is not True:
        blockers.append("Held-out policy eval validator did not pass.")
    if policy_report.get("proof_eligible") is not True:
        blockers.append("Curated held-out policy success rate did not exceed baseline.")
    return blockers


def _non_proof_blockers(rollout_source: dict[str, Any]) -> list[str]:
    blockers = rollout_source.get("promotion_blockers")
    if isinstance(blockers, list) and blockers:
        return [str(item) for item in blockers]
    if rollout_source.get("source_kind") == SCHEMA_ONLY_KIND:
        return ["Schema-only rollout ingest fixture cannot close MVP-2."]
    if rollout_source.get("source_kind") == LOCAL_OFFLINE_PROXY_KIND:
        return ["Local offline deterministic proxy cannot close MVP-2."]
    if rollout_source.get("source_kind") == PHASE_CONDITIONED_LOCAL_PROXY_KIND:
        return ["Phase-conditioned local evaluator proxy cannot close MVP-2."]
    return ["Rollout results cannot close MVP-2 without proof-grade held-out policy provenance."]


def _proof_source(harness_report: dict[str, Any]) -> dict[str, Any]:
    source = harness_report.get("proof_source") if isinstance(harness_report.get("proof_source"), dict) else {}
    return {
        "adapter_id": source.get("adapter_id"),
        "adapter_version": source.get("adapter_version"),
        "builder_id": source.get("builder_id"),
        "robot_embodiment": source.get("robot_embodiment"),
        "source_evidence_type": source.get("source_evidence_type"),
        "validator_backend": source.get("validator_backend"),
        "harness_report_path": harness_report.get("artifact_paths", {}).get("report")
        if isinstance(harness_report.get("artifact_paths"), dict)
        else None,
    }


def _external_template_heldout_suite(harness_report: dict[str, Any]) -> dict[str, Any]:
    heldout_suite = harness_report["heldout_suite"]
    raw_scenario_ids = [str(item) for item in heldout_suite.get("scenario_ids", [])]
    scenario_ids = [f"TODO_external_heldout_scenario_{index:02d}" for index in range(max(1, len(raw_scenario_ids)))]
    return {
        "id": "external_ur_heldout_policy_eval_suite",
        "held_out": True,
        "task_type": heldout_suite.get("task_type", "connector_insertion"),
        "scenario_ids": scenario_ids,
        "scenario_set_sha256": "TODO_external_heldout_scenario_set_sha256",
        "source_kind": "external_trainer_eval_suite",
        "proof_role": "external_policy_eval_suite",
        "derived_from_harness_heldout_suite_id": heldout_suite.get("id"),
        "minimum_rollouts_per_policy": max(10, len(scenario_ids)),
        "notes": [
            "Use the same held-out suite object in baseline and candidate rollout JSON.",
            "Do not rename this as schema-only or local-offline evidence.",
            "Replace TODO scenario ids with real external held-out scenario ids before submission.",
        ],
    }


def _external_rollout_template(*, policy_role: str, heldout_suite: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": EXTERNAL_PROOF_TEMPLATE_SCHEMA_VERSION,
        "source_kind": EXTERNAL_TEMPLATE_KIND,
        "proof_role": "external_trainer_policy_eval_template",
        "policy_role": policy_role,
        "policy_artifact_id": f"TODO_{policy_role}_policy_artifact_id",
        "policy_artifact_sha256": f"TODO_{policy_role}_policy_artifact_sha256",
        "training_artifact_sha256": f"TODO_{policy_role}_training_artifact_sha256",
        "trainer": "TODO_external_trainer_name",
        "eval_runner": "TODO_external_heldout_eval_runner_name",
        "external_evaluator_run": {
            "run_id": f"TODO_{policy_role}_external_eval_run_id",
            "runner_version": "TODO_external_eval_runner_version",
            "run_log_uri": f"TODO_{policy_role}_external_eval_run_log_uri",
            "generated_outside_rdf_local_proxy": True,
        },
        "heldout_suite": heldout_suite,
        "rollout_results": [],
        "required_rollout_result_shape": {
            "rollout_id": "string; unique external rollout id",
            "scenario_id": "string; one of heldout_suite.scenario_ids",
            "success": "boolean; measured by the external held-out evaluator",
            "rollout_log_ref": "string; immutable rollout log path or URI",
        },
        "required_final_values": {
            "source_kind": EXTERNAL_PROOF_KIND,
            "proof_role": "external_trainer_policy_eval",
        },
        "template_is_not_evidence": True,
        "must_replace_before_submission": [
            "source_kind",
            "proof_role",
            "policy_artifact_id",
            "policy_artifact_sha256",
            "training_artifact_sha256",
            "trainer",
            "eval_runner",
            "external_evaluator_run",
            "rollout_results",
        ],
    }


def build_mvp2_external_policy_eval_template(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR / EXTERNAL_PROOF_TEMPLATE_DIR_NAME,
    harness_output_dir: Path = DEFAULT_HARNESS_OUTPUT_DIR,
    mvp1plus_output_dir: Path = DEFAULT_MVP1PLUS_OUTPUT_DIR,
    clean: bool = False,
    refresh_harness: bool = False,
    refresh_mvp1plus: bool = False,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    harness_report = _load_or_refresh_harness(
        harness_output_dir=harness_output_dir,
        mvp1plus_output_dir=mvp1plus_output_dir,
        refresh_harness=refresh_harness,
        refresh_mvp1plus=refresh_mvp1plus,
    )
    _validate_harness_ready(harness_report)

    heldout_suite = _external_template_heldout_suite(harness_report)
    baseline_template = _external_rollout_template(
        policy_role="baseline_uncurated",
        heldout_suite=heldout_suite,
    )
    candidate_template = _external_rollout_template(
        policy_role="candidate_curated",
        heldout_suite=heldout_suite,
    )
    request_path = output_dir / EXTERNAL_PROOF_REQUEST_NAME
    baseline_path = output_dir / EXTERNAL_BASELINE_TEMPLATE_NAME
    candidate_path = output_dir / EXTERNAL_CANDIDATE_TEMPLATE_NAME
    report_path = output_dir / "external_policy_eval_template_report.json"
    artifact_paths = {
        "request": str(request_path),
        "baseline_template": str(baseline_path),
        "candidate_template": str(candidate_path),
        "report": str(report_path),
    }
    request = {
        "schema_version": EXTERNAL_PROOF_TEMPLATE_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "purpose": "Collect proof-grade external held-out rollout JSON for MVP-2 learning-proven evaluation.",
        "template_is_not_evidence": True,
        "required_final_source_kind": EXTERNAL_PROOF_KIND,
        "required_final_proof_role": "external_trainer_policy_eval",
        "minimum_rollouts_per_policy": heldout_suite["minimum_rollouts_per_policy"],
        "heldout_suite": heldout_suite,
        "input_templates": {
            "baseline_uncurated": str(baseline_path),
            "candidate_curated": str(candidate_path),
        },
        "ingest_command": (
            "uv run python scripts/run_mvp2_learning_proven_policy_eval.py "
            f"--baseline-results {baseline_path} --candidate-results {candidate_path} --pretty"
        ),
        "required_success_condition": "candidate curated success rate must exceed baseline uncurated success rate.",
        "non_claims": [
            "The template does not prove policy uplift.",
            "The template does not claim real robot success or physical robot readiness.",
            "HMD/OpenXR remains outside the primary proof path.",
        ],
    }
    report = {
        "schema_version": EXTERNAL_PROOF_TEMPLATE_SCHEMA_VERSION,
        "created_at": request["created_at"],
        "passed": True,
        "proof_ready": False,
        "mvp2_closed": False,
        "template_is_not_evidence": True,
        "required_final_source_kind": EXTERNAL_PROOF_KIND,
        "required_final_proof_role": "external_trainer_policy_eval",
        "heldout_suite": heldout_suite,
        "proof_source": _proof_source(harness_report),
        "artifact_paths": artifact_paths,
        "buyer_summary": {
            "mvp2_closed": False,
            "question": "What external evidence is still needed to close MVP-2?",
            "answer": "Fill baseline and candidate external held-out rollout JSON with proof-grade provenance.",
            "required_final_source_kind": EXTERNAL_PROOF_KIND,
        },
        "limitations": [
            "External proof template cannot close MVP-2.",
            "Template rollout files must be filled by an external held-out evaluator before ingest.",
            "Proof-grade MVP-2 closure still requires positive curated > uncurated held-out policy success.",
        ],
    }
    write_json(request_path, request)
    write_json(baseline_path, baseline_template)
    write_json(candidate_path, candidate_template)
    write_json(report_path, report)
    return report


def _final_report(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    rollout_source: dict[str, Any],
    policy_eval_input_path: Path,
    policy_eval_report_path: Path,
    policy_report: dict[str, Any],
) -> dict[str, Any]:
    learning_proven = bool(policy_report.get("proof_eligible") is True)
    heldout_suite = policy_report.get("eval_suite") if isinstance(policy_report.get("eval_suite"), dict) else {}
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": policy_report.get("passed") is True,
        "learning_results_measured": policy_report.get("learning_results_measured") is True,
        "learning_proven": learning_proven,
        "proof_eligible": learning_proven,
        "evidence_tier": rollout_source.get("source_kind"),
        "validator_evidence_tier": policy_report.get("evidence_tier"),
        "primary_metric": policy_report.get("primary_metric"),
        "baseline_success_rate": policy_report.get("baseline_success_rate"),
        "candidate_success_rate": policy_report.get("candidate_success_rate"),
        "curated_vs_uncurated_uplift": policy_report.get("curated_vs_uncurated_uplift"),
        "curated_vs_uncurated_relative_uplift": policy_report.get("curated_vs_uncurated_relative_uplift"),
        "confidence_interval_95": policy_report.get("confidence_interval_95"),
        "rollout_generation_method": rollout_source.get("rollout_generation_method"),
        "success_label_source": rollout_source.get("success_label_source"),
        "heldout_suite": heldout_suite,
        "rollout_source": rollout_source,
        "local_offline_evidence": None,
        "external_rollout_evidence": rollout_source if rollout_source.get("source_kind") == EXTERNAL_PROOF_KIND else None,
        "policy_provenance": _policy_provenance(policy_report),
        "proof_source": _proof_source(harness_report),
        "no_real_robot_evidence": True,
        "no_isaac_rollout_evidence": True,
        "claim_boundary": {
            "mvp2_learning_proven_claimed": learning_proven,
            "real_robot_success_claimed": False,
            "physical_robot_readiness_claimed": False,
            "hmd_readiness_claimed": False,
            "schema_only_rollout_fixture_used_for_uplift": False,
        },
        "buyer_summary": {
            "mvp2_closed": learning_proven,
            "question": "Did curated training data beat uncurated training data on held-out policy success?",
            "answer": "yes" if learning_proven else "no",
            "baseline_success_rate": policy_report.get("baseline_success_rate"),
            "candidate_success_rate": policy_report.get("candidate_success_rate"),
            "curated_vs_uncurated_uplift": policy_report.get("curated_vs_uncurated_uplift"),
            "adapter_id": _proof_source(harness_report).get("adapter_id"),
            "evidence_tier": rollout_source.get("source_kind"),
        },
        "blockers": _blockers(policy_report, rollout_source),
        "artifact_paths": {
            "report": str(output_dir / REPORT_NAME),
            "policy_eval_input": str(policy_eval_input_path),
            "policy_eval_report": str(policy_eval_report_path),
            "local_offline_heldout_suite": rollout_source.get("heldout_suite", {}).get("path")
            if isinstance(rollout_source.get("heldout_suite"), dict)
            else None,
        },
        "limitations": [
            "MVP-2 proof is learning-proven policy uplift, not real robot success.",
            "This script does not train a policy or run live robot/Isaac rollouts.",
            "Stronger physical claims still require real robot or Isaac runtime evaluation evidence.",
            "HMD/OpenXR remains outside the primary proof path.",
        ],
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def _schema_only_non_proof_report(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    rollout_source: dict[str, Any],
) -> dict[str, Any]:
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "learning_results_measured": False,
        "learning_proven": False,
        "proof_eligible": False,
        "evidence_tier": rollout_source.get("source_kind"),
        "validator_evidence_tier": None,
        "primary_metric": "policy_success_rate",
        "baseline_success_rate": None,
        "candidate_success_rate": None,
        "curated_vs_uncurated_uplift": None,
        "rollout_source": rollout_source,
        "proof_source": _proof_source(harness_report),
        "no_real_robot_evidence": True,
        "no_isaac_rollout_evidence": True,
        "claim_boundary": {
            "mvp2_learning_proven_claimed": False,
            "real_robot_success_claimed": False,
            "physical_robot_readiness_claimed": False,
            "hmd_readiness_claimed": False,
            "schema_only_rollout_fixture_used_for_uplift": False,
        },
        "buyer_summary": {
            "mvp2_closed": False,
            "question": "Did curated training data beat uncurated training data on held-out policy success?",
            "answer": "not measured",
            "evidence_tier": rollout_source.get("source_kind"),
        },
        "blockers": ["Schema-only rollout ingest fixture cannot close MVP-2."],
        "artifact_paths": {
            "report": str(output_dir / REPORT_NAME),
            "policy_eval_input": None,
            "policy_eval_report": None,
            "local_offline_heldout_suite": None,
        },
        "limitations": [
            "Schema-only rollout fixtures validate ingest shape only.",
            "Schema-only fixtures are blocked before the held-out policy validator.",
        ],
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def _local_offline_proxy_report(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    rollout_source: dict[str, Any],
) -> dict[str, Any]:
    baseline_payload = _rollout_payload(Path(str(rollout_source["baseline_results_path"])))
    candidate_payload = _rollout_payload(Path(str(rollout_source["candidate_results_path"])))
    baseline_rate = _rollout_success_rate_from_payload(baseline_payload)
    candidate_rate = _rollout_success_rate_from_payload(candidate_payload)
    uplift = None
    relative_uplift = None
    if baseline_rate is not None and candidate_rate is not None:
        uplift = candidate_rate - baseline_rate
        relative_uplift = uplift / baseline_rate if baseline_rate else None

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "learning_results_measured": True,
        "learning_proven": False,
        "proof_eligible": False,
        "evidence_tier": rollout_source.get("source_kind", LOCAL_OFFLINE_PROXY_KIND),
        "validator_evidence_tier": None,
        "primary_metric": "policy_success_rate",
        "baseline_success_rate": baseline_rate,
        "candidate_success_rate": candidate_rate,
        "curated_vs_uncurated_uplift": uplift,
        "curated_vs_uncurated_relative_uplift": relative_uplift,
        "confidence_interval_95": None,
        "rollout_generation_method": rollout_source.get("rollout_generation_method"),
        "success_label_source": rollout_source.get("success_label_source"),
        "heldout_suite": rollout_source.get("heldout_suite"),
        "rollout_source": rollout_source,
        "local_offline_evidence": rollout_source
        if rollout_source.get("source_kind") == LOCAL_OFFLINE_PROXY_KIND
        else None,
        "local_phase_conditioned_evidence": rollout_source
        if rollout_source.get("source_kind") == PHASE_CONDITIONED_LOCAL_PROXY_KIND
        else None,
        "external_rollout_evidence": None,
        "policy_provenance": None,
        "proof_source": _proof_source(harness_report),
        "no_real_robot_evidence": True,
        "no_isaac_rollout_evidence": True,
        "claim_boundary": {
            "mvp2_learning_proven_claimed": False,
            "real_robot_success_claimed": False,
            "physical_robot_readiness_claimed": False,
            "hmd_readiness_claimed": False,
            "schema_only_rollout_fixture_used_for_uplift": False,
        },
        "buyer_summary": {
            "mvp2_closed": False,
            "question": "Did curated training data beat uncurated training data on held-out policy success?",
            "answer": "proxy only; not proof-grade",
            "baseline_success_rate": baseline_rate,
            "candidate_success_rate": candidate_rate,
            "curated_vs_uncurated_uplift": uplift,
            "adapter_id": _proof_source(harness_report).get("adapter_id"),
            "evidence_tier": rollout_source.get("source_kind", LOCAL_OFFLINE_PROXY_KIND),
        },
        "blockers": _non_proof_blockers(rollout_source),
        "artifact_paths": {
            "report": str(output_dir / REPORT_NAME),
            "policy_eval_input": None,
            "policy_eval_report": None,
            "local_offline_heldout_suite": rollout_source.get("heldout_suite", {}).get("path")
            if isinstance(rollout_source.get("heldout_suite"), dict)
            else None,
        },
        "limitations": [
            "Local proxy rollouts are derived from recorded-log harness signals rather than an independent held-out evaluator.",
            "This report measures a local proxy uplift signal but cannot close MVP-2.",
            "Proof-grade MVP-2 closure requires external held-out policy evaluation rollout provenance.",
            "HMD/OpenXR remains outside the primary proof path.",
        ],
    }
    write_json(output_dir / REPORT_NAME, report)
    return report


def _non_proof_report(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    rollout_source: dict[str, Any],
) -> dict[str, Any]:
    report = _schema_only_non_proof_report(
        output_dir=output_dir,
        harness_report=harness_report,
        rollout_source=rollout_source,
    )
    report["blockers"] = _non_proof_blockers(rollout_source)
    report["limitations"] = [
        "Non-proof rollout inputs are blocked before the held-out policy validator.",
        "Proof-grade MVP-2 closure requires external held-out policy evaluation rollout provenance.",
    ]
    report["local_offline_evidence"] = (
        rollout_source
        if rollout_source.get("source_kind") == LOCAL_OFFLINE_PROXY_KIND
        else None
    )
    report["local_phase_conditioned_evidence"] = (
        rollout_source if rollout_source.get("source_kind") == PHASE_CONDITIONED_LOCAL_PROXY_KIND else None
    )
    report["external_rollout_evidence"] = None
    write_json(output_dir / REPORT_NAME, report)
    return report


def _reproducible_command(output_dir: Path) -> str:
    return (
        "uv run python scripts/run_mvp2_learning_proven_policy_eval.py "
        f"--output-dir {output_dir} --clean --refresh-harness --pretty"
    )


def build_mvp2_learning_proven_policy_eval(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    harness_output_dir: Path = DEFAULT_HARNESS_OUTPUT_DIR,
    mvp1plus_output_dir: Path = DEFAULT_MVP1PLUS_OUTPUT_DIR,
    clean: bool = False,
    refresh_harness: bool = False,
    refresh_mvp1plus: bool = False,
    offline_profile: str = "positive",
    baseline_results_path: Path | None = None,
    candidate_results_path: Path | None = None,
    baseline_policy_id: str | None = None,
    candidate_policy_id: str | None = None,
    policy_class: str | None = None,
    trainer: str | None = None,
    min_rollouts_per_policy: int = 10,
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 17,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    harness_report = _load_or_refresh_harness(
        harness_output_dir=harness_output_dir,
        mvp1plus_output_dir=mvp1plus_output_dir,
        refresh_harness=refresh_harness,
        refresh_mvp1plus=refresh_mvp1plus,
    )
    _validate_harness_ready(harness_report)
    rollout_source = _rollout_source(
        output_dir=output_dir,
        harness_report=harness_report,
        offline_profile=offline_profile,
        baseline_results_path=baseline_results_path,
        candidate_results_path=candidate_results_path,
        min_rollouts_per_policy=min_rollouts_per_policy,
    )
    if rollout_source.get("source_kind") in {LOCAL_OFFLINE_PROXY_KIND, PHASE_CONDITIONED_LOCAL_PROXY_KIND}:
        return _local_offline_proxy_report(
            output_dir=output_dir,
            harness_report=harness_report,
            rollout_source=rollout_source,
        )
    if rollout_source.get("source_kind") != EXTERNAL_PROOF_KIND:
        return _non_proof_report(
            output_dir=output_dir,
            harness_report=harness_report,
            rollout_source=rollout_source,
        )

    artifact_paths = harness_report["artifact_paths"]
    policy_eval_input_path = output_dir / POLICY_EVAL_INPUT_NAME
    policy_eval_report_path = output_dir / POLICY_EVAL_REPORT_NAME
    adapter_report = build_policy_eval_input(
        template_path=Path(str(artifact_paths["policy_eval_input_template"])),
        baseline_results_path=Path(str(rollout_source["baseline_results_path"])),
        candidate_results_path=Path(str(rollout_source["candidate_results_path"])),
        output_path=policy_eval_input_path,
        baseline_policy_id=baseline_policy_id or "baseline_uncurated_external_policy",
        candidate_policy_id=candidate_policy_id or "candidate_curated_external_policy",
        policy_class=policy_class,
        trainer=trainer,
    )
    policy_eval_payload = adapter_report["policy_eval_input"]
    policy_eval_payload["evidence_tier"] = "heldout_policy_eval"
    policy_eval_payload["reproducible_command"] = _reproducible_command(output_dir)
    external_suite = rollout_source["heldout_suite"]
    policy_eval_payload["task_type"] = external_suite["task_type"]
    policy_eval_payload["held_out"] = True
    policy_eval_payload["eval_suite"] = {
        "id": external_suite["id"],
        "held_out": True,
        "task_type": external_suite["task_type"],
        "scenario_ids": external_suite["scenario_ids"],
        "source_kind": external_suite["source_kind"],
        "proof_role": external_suite["proof_role"],
    }
    policy_eval_payload["external_rollout_evidence"] = rollout_source

    write_json(policy_eval_input_path, policy_eval_payload)
    policy_report = run_real_policy_eval(
        input_path=policy_eval_input_path,
        output_path=policy_eval_report_path,
        experiment_manifest_path=output_dir / "unused_mvp2_learning_proven_manifest.json",
        update_manifest=False,
        min_rollouts_per_policy=min_rollouts_per_policy,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )
    return _final_report(
        output_dir=output_dir,
        harness_report=harness_report,
        rollout_source=rollout_source,
        policy_eval_input_path=policy_eval_input_path,
        policy_eval_report_path=policy_eval_report_path,
        policy_report=policy_report,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--harness-output-dir", type=Path, default=DEFAULT_HARNESS_OUTPUT_DIR)
    parser.add_argument("--mvp1plus-output-dir", type=Path, default=DEFAULT_MVP1PLUS_OUTPUT_DIR)
    parser.add_argument("--write-external-proof-template", action="store_true")
    parser.add_argument("--external-proof-template-dir", type=Path)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--refresh-harness", action="store_true")
    parser.add_argument("--refresh-mvp1plus", action="store_true")
    parser.add_argument("--offline-profile", choices=sorted(VALID_OFFLINE_PROFILES), default="positive")
    parser.add_argument("--baseline-results", type=Path)
    parser.add_argument("--candidate-results", type=Path)
    parser.add_argument("--baseline-policy-id")
    parser.add_argument("--candidate-policy-id")
    parser.add_argument("--policy-class")
    parser.add_argument("--trainer")
    parser.add_argument("--min-rollouts-per-policy", type=int, default=10)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=17)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write_external_proof_template:
        template_dir = args.external_proof_template_dir or args.output_dir / EXTERNAL_PROOF_TEMPLATE_DIR_NAME
        report = build_mvp2_external_policy_eval_template(
            output_dir=template_dir,
            harness_output_dir=args.harness_output_dir,
            mvp1plus_output_dir=args.mvp1plus_output_dir,
            clean=args.clean,
            refresh_harness=args.refresh_harness,
            refresh_mvp1plus=args.refresh_mvp1plus,
        )
        if args.pretty:
            print(stable_json(report))
        else:
            status = "PASS" if report["passed"] else "FAIL"
            print(f"RDF MVP-2 external policy eval template: {status}")
            print(f"proof_ready={report['proof_ready']}")
            print(f"mvp2_closed={report['mvp2_closed']}")
            print(f"output={template_dir}")
        return 0 if report["passed"] else 1

    report = build_mvp2_learning_proven_policy_eval(
        output_dir=args.output_dir,
        harness_output_dir=args.harness_output_dir,
        mvp1plus_output_dir=args.mvp1plus_output_dir,
        clean=args.clean,
        refresh_harness=args.refresh_harness,
        refresh_mvp1plus=args.refresh_mvp1plus,
        offline_profile=args.offline_profile,
        baseline_results_path=args.baseline_results,
        candidate_results_path=args.candidate_results,
        baseline_policy_id=args.baseline_policy_id,
        candidate_policy_id=args.candidate_policy_id,
        policy_class=args.policy_class,
        trainer=args.trainer,
        min_rollouts_per_policy=args.min_rollouts_per_policy,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-2 learning-proven policy eval: {status}")
        print(f"learning_results_measured={report['learning_results_measured']}")
        print(f"learning_proven={report['learning_proven']}")
        print(f"proof_eligible={report['proof_eligible']}")
        print(f"baseline_success_rate={report['baseline_success_rate']}")
        print(f"candidate_success_rate={report['candidate_success_rate']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"output={args.output_dir}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
