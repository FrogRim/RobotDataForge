#!/usr/bin/env python3
"""Convert headless rollout logs into MVP-1C policy eval input JSON.

This adapter bridges an external trainer/evaluator and
scripts/run_mvp1c_real_policy_eval.py. It does not run rollouts, does not update
the experiment manifest, and does not claim MVP-1C proof by itself.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = ROOT / "storage" / "mvp1c_headless_eval"
SCHEMA_VERSION = "rdf_mvp1c_rollout_result_adapter_v0.1.0"


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
        if lowered in {"true", "success", "succeeded", "pass", "passed", "1", "yes"}:
            return True
        if lowered in {"false", "failure", "failed", "fail", "0", "no"}:
            return False
    return None


def _success_from_mapping(row: dict[str, Any], *, index: int) -> bool:
    for key in ("success", "terminal_success", "policy_success", "rollout_success", "succeeded"):
        if key in row:
            success = _as_bool(row[key])
            if success is not None:
                return success
    raise ValueError(f"rollout[{index}] has no parseable success field")


def _rollout_from_mapping(row: dict[str, Any], *, index: int, default_prefix: str) -> dict[str, Any]:
    success = _success_from_mapping(row, index=index)
    rollout_id = row.get("rollout_id") or row.get("id") or f"{default_prefix}_{index:04d}"
    scenario_id = row.get("scenario_id") or row.get("scenario") or row.get("eval_case") or row.get("case_id")
    output: dict[str, Any] = {
        "rollout_id": str(rollout_id),
        "success": success,
    }
    if scenario_id is not None and str(scenario_id):
        output["scenario_id"] = str(scenario_id)
    optional_keys = (
        "episode_id",
        "seed",
        "failure_reason",
        "time_to_completion",
        "steps",
        "phase_failure",
        "collision_count",
    )
    for key in optional_keys:
        value = row.get(key)
        if value not in (None, ""):
            output[key] = value
    return output


def _rollouts_from_aggregate(data: dict[str, Any], *, default_prefix: str) -> list[dict[str, Any]]:
    rollout_count = data.get("rollout_count", data.get("num_rollouts"))
    success_count = data.get("success_count", data.get("successes"))
    if not isinstance(rollout_count, int) or not isinstance(success_count, int):
        return []
    if rollout_count < 0 or success_count < 0 or success_count > rollout_count:
        raise ValueError("aggregate success_count/rollout_count is invalid")
    return [
        {
            "rollout_id": f"{default_prefix}_{index:04d}",
            "success": index < success_count,
        }
        for index in range(rollout_count)
    ]


def load_rollout_results(path: Path, *, default_prefix: str) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError(f"{path}: CSV header is missing")
            return [
                _rollout_from_mapping(dict(row), index=index, default_prefix=default_prefix)
                for index, row in enumerate(reader)
            ]

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [
            _rollout_from_mapping(row, index=index, default_prefix=default_prefix)
            for index, row in enumerate(data)
            if isinstance(row, dict)
        ]
    if not isinstance(data, dict):
        raise ValueError(f"{path}: rollout result JSON must be an object or list")

    for key in ("rollout_results", "rollouts", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [
                _rollout_from_mapping(row, index=index, default_prefix=default_prefix)
                for index, row in enumerate(value)
                if isinstance(row, dict)
            ]

    aggregate = _rollouts_from_aggregate(data, default_prefix=default_prefix)
    if aggregate:
        return aggregate
    raise ValueError(f"{path}: no rollout_results/rollouts/results or aggregate counts found")


def _success_rate(rollouts: list[dict[str, Any]]) -> float | None:
    if not rollouts:
        return None
    return sum(1 for row in rollouts if row.get("success") is True) / len(rollouts)


def build_policy_eval_input(
    *,
    template_path: Path,
    baseline_results_path: Path,
    candidate_results_path: Path,
    output_path: Path,
    baseline_policy_id: str | None = None,
    candidate_policy_id: str | None = None,
    policy_class: str | None = None,
    trainer: str | None = None,
) -> dict[str, Any]:
    template = read_json(template_path)
    baseline_rollouts = load_rollout_results(baseline_results_path, default_prefix="baseline")
    candidate_rollouts = load_rollout_results(candidate_results_path, default_prefix="candidate")

    baseline = template.get("baseline")
    candidate = template.get("candidate")
    if not isinstance(baseline, dict):
        raise ValueError("template baseline must be an object")
    if not isinstance(candidate, dict):
        raise ValueError("template candidate must be an object")

    baseline["rollout_results"] = baseline_rollouts
    candidate["rollout_results"] = candidate_rollouts
    if baseline_policy_id:
        baseline["policy_id"] = baseline_policy_id
    if candidate_policy_id:
        candidate["policy_id"] = candidate_policy_id
    if policy_class:
        baseline["policy_class"] = policy_class
        candidate["policy_class"] = policy_class
    if trainer:
        baseline["trainer"] = trainer
        candidate["trainer"] = trainer

    adapter_metadata = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "template_path": str(template_path),
        "baseline_results_path": str(baseline_results_path),
        "candidate_results_path": str(candidate_results_path),
        "baseline_rollout_count": len(baseline_rollouts),
        "candidate_rollout_count": len(candidate_rollouts),
        "baseline_success_rate": _success_rate(baseline_rollouts),
        "candidate_success_rate": _success_rate(candidate_rollouts),
        "does_not_update_manifest": True,
    }
    template["rollout_result_adapter"] = adapter_metadata
    write_json(output_path, template)
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": True,
        "output_path": str(output_path),
        "policy_eval_input": template,
        "adapter_metadata": adapter_metadata,
        "warnings": [
            "This adapter only converts rollout logs; run run_mvp1c_real_policy_eval.py to validate proof eligibility.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DEFAULT_BUNDLE_DIR / "policy_eval_input_template.json")
    parser.add_argument("--baseline-results", type=Path, required=True)
    parser.add_argument("--candidate-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_BUNDLE_DIR / "policy_eval_input.json")
    parser.add_argument("--baseline-policy-id")
    parser.add_argument("--candidate-policy-id")
    parser.add_argument("--policy-class")
    parser.add_argument("--trainer")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_policy_eval_input(
        template_path=args.template,
        baseline_results_path=args.baseline_results,
        candidate_results_path=args.candidate_results,
        output_path=args.output,
        baseline_policy_id=args.baseline_policy_id,
        candidate_policy_id=args.candidate_policy_id,
        policy_class=args.policy_class,
        trainer=args.trainer,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        metadata = report["adapter_metadata"]
        print("RDF MVP-1C rollout result adapter: PASS")
        print(f"baseline_rollouts={metadata['baseline_rollout_count']}")
        print(f"candidate_rollouts={metadata['candidate_rollout_count']}")
        print(f"baseline_success_rate={metadata['baseline_success_rate']}")
        print(f"candidate_success_rate={metadata['candidate_success_rate']}")
        print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
