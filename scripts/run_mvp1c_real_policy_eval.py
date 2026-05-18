#!/usr/bin/env python3
"""Ingest MVP-1C held-out policy evaluation results.

This script does not train or simulate a policy by itself. It validates a
curated-vs-uncurated held-out rollout result file, computes success-rate uplift,
writes a measurement report, and updates the experiment manifest only when the
input is proof-grade held-out policy evaluation evidence.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import random
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READINESS_DIR = ROOT / "storage" / "mvp1_readiness"
SCHEMA_VERSION = "rdf_mvp1c_heldout_policy_eval_v0.2.0"
VALID_EVIDENCE_TIERS = {"heldout_policy_eval", "real_heldout_policy_eval"}
VALID_PRIMARY_METRICS = {"policy_success_rate"}
VALID_TASK_TYPES = {"peg_in_hole", "connector_insertion"}


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


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "success", "succeeded", "pass", "passed", "1"}:
            return True
        if lowered in {"false", "failure", "failed", "fail", "0"}:
            return False
    return None


def _policy_label(policy: dict[str, Any], fallback: str) -> str:
    for key in ("name", "policy_id", "dataset_view", "dataset_id"):
        value = policy.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def _extract_rollout_successes(policy: dict[str, Any]) -> tuple[list[int], list[str], list[str]]:
    successes: list[int] = []
    rollout_ids: list[str] = []
    issues: list[str] = []

    rollouts = policy.get("rollouts")
    if rollouts is None:
        rollouts = policy.get("rollout_results")
    if rollouts is None:
        rollouts = policy.get("results")

    if isinstance(rollouts, list):
        for index, rollout in enumerate(rollouts):
            if not isinstance(rollout, dict):
                issues.append(f"rollout[{index}] is not an object")
                continue
            success_value = None
            for key in ("success", "terminal_success", "policy_success", "rollout_success"):
                if key in rollout:
                    success_value = rollout.get(key)
                    break
            success = _as_bool(success_value)
            if success is None:
                issues.append(f"rollout[{index}] has no boolean success field")
                continue
            successes.append(1 if success else 0)
            rollout_id = rollout.get("rollout_id") or rollout.get("id") or rollout.get("scenario_id")
            rollout_ids.append(str(rollout_id) if rollout_id is not None else f"rollout_{index}")
        return successes, rollout_ids, issues

    rollout_count = policy.get("rollout_count", policy.get("num_rollouts"))
    success_count = policy.get("success_count", policy.get("successes"))
    if isinstance(rollout_count, int) and isinstance(success_count, int):
        if rollout_count < 0 or success_count < 0 or success_count > rollout_count:
            issues.append("aggregate success_count/rollout_count is invalid")
        else:
            successes = [1] * success_count + [0] * (rollout_count - success_count)
            rollout_ids = [f"aggregate_{index}" for index in range(rollout_count)]
        return successes, rollout_ids, issues

    issues.append("policy result must provide rollout_results[] or aggregate success_count/rollout_count")
    return successes, rollout_ids, issues


def _policy_summary(policy: dict[str, Any], role: str, successes: list[int], rollout_ids: list[str]) -> dict[str, Any]:
    rollout_count = len(successes)
    success_count = sum(successes)
    success_rate = float(success_count / rollout_count) if rollout_count else None
    return {
        "role": role,
        "name": _policy_label(policy, role),
        "policy_id": policy.get("policy_id"),
        "dataset_id": policy.get("dataset_id"),
        "dataset_view": policy.get("dataset_view"),
        "trainer": policy.get("trainer"),
        "policy_class": policy.get("policy_class"),
        "rollout_count": rollout_count,
        "success_count": success_count,
        "success_rate": success_rate,
        "rollout_ids": rollout_ids,
    }


def _contains_token(policy: dict[str, Any], token: str) -> bool:
    haystack = " ".join(
        str(policy.get(key, ""))
        for key in ("name", "policy_id", "dataset_id", "dataset_view", "description")
    ).lower()
    return token in haystack


def _bootstrap_delta_ci(
    baseline_successes: list[int],
    candidate_successes: list[int],
    *,
    seed: int,
    iterations: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    deltas: list[float] = []
    baseline_count = len(baseline_successes)
    candidate_count = len(candidate_successes)
    for _ in range(iterations):
        baseline_rate = sum(rng.choice(baseline_successes) for _ in range(baseline_count)) / baseline_count
        candidate_rate = sum(rng.choice(candidate_successes) for _ in range(candidate_count)) / candidate_count
        deltas.append(candidate_rate - baseline_rate)
    deltas.sort()
    lower_index = max(0, int(0.025 * (len(deltas) - 1)))
    upper_index = min(len(deltas) - 1, int(0.975 * (len(deltas) - 1)))
    return {
        "method": "deterministic_bootstrap",
        "seed": seed,
        "iterations": iterations,
        "lower": deltas[lower_index],
        "upper": deltas[upper_index],
    }


def _metric_delta(
    *,
    baseline_score: float | None,
    candidate_score: float | None,
) -> float | None:
    if baseline_score is None or candidate_score is None:
        return None
    return float(candidate_score - baseline_score)


def _secondary_metrics(
    payload: dict[str, Any],
    *,
    baseline_score: float | None,
    candidate_score: float | None,
) -> dict[str, Any]:
    metrics = payload.get("secondary_metrics")
    normalized = dict(metrics) if isinstance(metrics, dict) else {}
    normalized.setdefault(
        "rollout_success_rate",
        {
            "role": "secondary_metric",
            "baseline": baseline_score,
            "candidate": candidate_score,
            "delta": _metric_delta(baseline_score=baseline_score, candidate_score=candidate_score),
            "source": "same held-out policy rollout outcomes as policy_success_rate",
        },
    )
    return normalized


def validate_and_measure(
    payload: dict[str, Any],
    *,
    input_path: Path,
    output_path: Path,
    min_rollouts_per_policy: int,
    bootstrap_iterations: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    evidence_tier = payload.get("evidence_tier")
    primary_metric = payload.get("primary_metric")
    eval_suite = payload.get("eval_suite") if isinstance(payload.get("eval_suite"), dict) else {}
    task_type = payload.get("task_type") or eval_suite.get("task_type")
    held_out = payload.get("held_out")
    if held_out is None:
        held_out = eval_suite.get("held_out")

    if evidence_tier not in VALID_EVIDENCE_TIERS:
        issues.append("evidence_tier must be heldout_policy_eval or real_heldout_policy_eval")
    if primary_metric not in VALID_PRIMARY_METRICS:
        issues.append("primary_metric must be policy_success_rate")
    if task_type not in VALID_TASK_TYPES:
        issues.append("task_type must be peg_in_hole or connector_insertion")
    if held_out is not True:
        issues.append("eval_suite.held_out or held_out must be true")

    baseline_policy = payload.get("baseline")
    candidate_policy = payload.get("candidate")
    if not isinstance(baseline_policy, dict):
        issues.append("baseline policy result must be an object")
        baseline_policy = {}
    if not isinstance(candidate_policy, dict):
        issues.append("candidate policy result must be an object")
        candidate_policy = {}

    baseline_successes, baseline_rollout_ids, baseline_issues = _extract_rollout_successes(baseline_policy)
    candidate_successes, candidate_rollout_ids, candidate_issues = _extract_rollout_successes(candidate_policy)
    issues.extend(f"baseline: {issue}" for issue in baseline_issues)
    issues.extend(f"candidate: {issue}" for issue in candidate_issues)

    if len(baseline_successes) < min_rollouts_per_policy:
        issues.append(f"baseline rollout_count must be >= {min_rollouts_per_policy}")
    if len(candidate_successes) < min_rollouts_per_policy:
        issues.append(f"candidate rollout_count must be >= {min_rollouts_per_policy}")
    if baseline_rollout_ids and candidate_rollout_ids and set(baseline_rollout_ids) & set(candidate_rollout_ids):
        warnings.append("baseline and candidate reuse rollout/scenario ids; confirm paired evaluation was intended")
    if not _contains_token(baseline_policy, "uncurated"):
        issues.append("baseline dataset_view/name must identify an uncurated dataset")
    if not _contains_token(candidate_policy, "curated"):
        issues.append("candidate dataset_view/name must identify a curated dataset")

    baseline = _policy_summary(baseline_policy, "baseline", baseline_successes, baseline_rollout_ids)
    candidate = _policy_summary(candidate_policy, "candidate", candidate_successes, candidate_rollout_ids)
    baseline_score = baseline["success_rate"]
    candidate_score = candidate["success_rate"]
    uplift = None
    relative_uplift = None
    ci_95 = None
    if baseline_score is not None and candidate_score is not None:
        uplift = _metric_delta(baseline_score=baseline_score, candidate_score=candidate_score)
        relative_uplift = float(uplift / baseline_score) if baseline_score else None
    if baseline_successes and candidate_successes:
        ci_95 = _bootstrap_delta_ci(
            baseline_successes,
            candidate_successes,
            seed=bootstrap_seed,
            iterations=bootstrap_iterations,
        )
        if uplift is not None and uplift > 0.0 and ci_95["lower"] <= 0.0:
            warnings.append("uplift is positive but the 95% bootstrap CI crosses zero")

    passed = not issues
    proof_eligible = bool(passed and uplift is not None and uplift > 0.0)
    if passed and not proof_eligible:
        warnings.append("real policy evaluation was measured, but curated did not beat uncurated")

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "input_path": str(input_path),
        "output_path": str(output_path),
        "passed": passed,
        "proof_eligible": proof_eligible,
        "evidence_tier": evidence_tier,
        "primary_metric": primary_metric,
        "secondary_metrics": _secondary_metrics(
            payload,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
        ),
        "metric_direction": "higher_is_better",
        "task_type": task_type,
        "eval_suite": eval_suite,
        "held_out": held_out,
        "baseline": baseline,
        "candidate": candidate,
        "baseline_success_rate": baseline_score,
        "candidate_success_rate": candidate_score,
        "curated_vs_uncurated_uplift": uplift,
        "curated_vs_uncurated_relative_uplift": relative_uplift,
        "confidence_interval_95": ci_95,
        "learning_results_measured": passed,
        "min_rollouts_per_policy": min_rollouts_per_policy,
        "issues": issues,
        "warnings": warnings,
    }


def update_experiment_manifest(manifest_path: Path, report: dict[str, Any]) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    measurement = {
        "schema_version": SCHEMA_VERSION,
        "report_path": report["output_path"],
        "proof_eligible": report["proof_eligible"],
        "evidence_tier": report["evidence_tier"],
        "primary_metric": report["primary_metric"],
        "secondary_metrics": report["secondary_metrics"],
        "baseline_success_rate": report["baseline_success_rate"],
        "candidate_success_rate": report["candidate_success_rate"],
        "baseline_rollout_count": report["baseline"]["rollout_count"],
        "candidate_rollout_count": report["candidate"]["rollout_count"],
        "curated_vs_uncurated_uplift": report["curated_vs_uncurated_uplift"],
        "curated_vs_uncurated_relative_uplift": report["curated_vs_uncurated_relative_uplift"],
        "confidence_interval_95": report["confidence_interval_95"],
        "eval_suite": report["eval_suite"],
        "task_type": report["task_type"],
        "warnings": report["warnings"],
    }
    manifest["policy_uplift_measurement"] = measurement
    manifest["learning_results_measured"] = report["learning_results_measured"]
    manifest["curated_vs_uncurated_uplift"] = report["curated_vs_uncurated_uplift"]
    write_json(manifest_path, manifest)
    return manifest


def run_real_policy_eval(
    *,
    input_path: Path,
    output_path: Path,
    experiment_manifest_path: Path,
    update_manifest: bool = True,
    min_rollouts_per_policy: int = 10,
    bootstrap_iterations: int = 2000,
    bootstrap_seed: int = 17,
) -> dict[str, Any]:
    payload = read_json(input_path)
    report = validate_and_measure(
        payload,
        input_path=input_path,
        output_path=output_path,
        min_rollouts_per_policy=min_rollouts_per_policy,
        bootstrap_iterations=bootstrap_iterations,
        bootstrap_seed=bootstrap_seed,
    )
    write_json(output_path, report)
    if update_manifest and report["passed"]:
        update_experiment_manifest(experiment_manifest_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Held-out policy evaluation JSON.")
    parser.add_argument(
        "--experiment-manifest",
        type=Path,
        default=DEFAULT_READINESS_DIR / "curated_vs_uncurated_experiment_manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_READINESS_DIR / "policy_uplift_real_eval_report.json",
    )
    parser.add_argument("--min-rollouts-per-policy", type=int, default=10)
    parser.add_argument("--bootstrap-iterations", type=int, default=2000)
    parser.add_argument("--bootstrap-seed", type=int, default=17)
    parser.add_argument("--no-update-manifest", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_real_policy_eval(
        input_path=args.input,
        output_path=args.output,
        experiment_manifest_path=args.experiment_manifest,
        update_manifest=not args.no_update_manifest,
        min_rollouts_per_policy=args.min_rollouts_per_policy,
        bootstrap_iterations=args.bootstrap_iterations,
        bootstrap_seed=args.bootstrap_seed,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1C real policy eval ingest: {status}")
        print(f"proof_eligible={report['proof_eligible']}")
        print(f"baseline_success_rate={report['baseline_success_rate']}")
        print(f"candidate_success_rate={report['candidate_success_rate']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"learning_results_measured={report['learning_results_measured']}")
        print(f"output={args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
