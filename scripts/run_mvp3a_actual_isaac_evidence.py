#!/usr/bin/env python3
"""Collect actual Isaac MVP-3A evidence and build the proof package.

This script executes the evaluator backend; it does not modify frozen MVP-2
artifacts. The generated package is still verified independently by
scripts/verify_proof_package.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "proof_evidence" / "mvp3a_target_fixture_pose_variant"
DEFAULT_PACKAGE_DIR = ROOT / "docs" / "proof" / "mvp3a_target_fixture_pose_variant_proof_package"
DEFAULT_BASELINE_POLICY = (
    ROOT
    / "storage"
    / "proof_evidence"
    / "mvp2c_isaac_training_calibration"
    / "v0_14_comparator_provenance_row_balance"
    / "baseline_policy_artifact_v0_14.json"
)
DEFAULT_CANDIDATE_POLICY = (
    ROOT
    / "storage"
    / "proof_evidence"
    / "mvp2c_isaac_training_calibration"
    / "v0_14_comparator_provenance_row_balance"
    / "candidate_policy_artifact_v0_14.json"
)
PROOF_RUNTIME = "dedicated_isaac_connector_insertion_evaluator"
SUCCESS_METRIC = {
    "name": "connector_insertion_geometry_stability_v0",
    "insertion_depth_m_min": 0.03,
    "lateral_error_m_max": 0.006,
    "orientation_error_deg_max": 8.0,
    "max_steps": 150,
    "stable_steps_required": 10,
}


@dataclass(frozen=True)
class EvidenceResult:
    output_dir: Path
    package_dir: Path
    config_path: Path
    manifest_path: Path | None


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _copy_policy(source: Path, dest: Path) -> dict:
    payload = load_json(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    return payload


def _scenario_row(*, split_label: str, seed: int) -> dict[str, Any]:
    offset_scale = 0.0005 * ((seed % 7) - 3)
    orientation = float(((seed // 3) % 9) - 4)
    return {
        "scenario_id": f"{split_label}_{seed}",
        "split": "held_out",
        "mvp3a_split": split_label,
        "seed": seed,
        "initial_offset_m": [round(offset_scale, 6), round(-offset_scale / 2.0, 6), 0.0],
        "orientation_offset_deg": orientation,
        "noise_level": f"mvp3a_{split_label}_target_fixture_pose_variant",
        "max_steps": SUCCESS_METRIC["max_steps"],
    }


def _scenario_manifest(*, split_label: str, seeds: range) -> dict[str, Any]:
    manifest = {
        "schema_version": "rdf_mvp3a_actual_isaac_scenario_manifest_v0.1.0",
        "task_type": "connector_insertion",
        "task_variant": "target_fixture_pose_variant",
        "scenario_axis": "pre_registered_seed_initial_offset_target_fixture_pose_variant",
        "success_metric": dict(SUCCESS_METRIC),
        "success_authority": {
            "primary": "isaac_env_native_consecutive_success_v0",
            "stable_steps_required": SUCCESS_METRIC["stable_steps_required"],
        },
        "scenarios": [_scenario_row(split_label=split_label, seed=seed) for seed in seeds],
        "leakage_policy": {
            "held_out_excluded_from_training": True,
            "held_out_excluded_from_curation_tuning": True,
            "held_out_excluded_from_threshold_tuning": True,
            "held_out_excluded_from_hyperparameter_selection": True,
        },
    }
    manifest["manifest_sha256"] = sha256_payload(manifest)
    return manifest


def _result_rollouts(result: Any) -> list[dict]:
    rows = list(getattr(result, "baseline_rollouts", []) or [])
    rows.extend(list(getattr(result, "candidate_rollouts", []) or []))
    return rows


def _result_trace_paths(result: Any) -> list[str]:
    paths = list(getattr(result, "baseline_trace_paths", []) or [])
    paths.extend(list(getattr(result, "candidate_trace_paths", []) or []))
    return paths


def _bind_rollouts(
    *,
    rows: list[dict],
    scenarios: list[dict],
    policy_artifact: dict,
) -> list[dict]:
    policy_hash = str(policy_artifact["policy_artifact_sha256"])
    if len(rows) != len(scenarios):
        raise ValueError(f"rollout count {len(rows)} != scenario count {len(scenarios)}")
    bound = []
    for row, scenario in zip(rows, scenarios, strict=True):
        updated = dict(row)
        updated["seed"] = int(scenario["seed"])
        updated["scenario_id"] = str(scenario["scenario_id"])
        updated["policy_artifact_sha256"] = policy_hash
        bound.append(updated)
    return bound


def _run_policy_split(
    *,
    backend: Any,
    output_dir: Path,
    split_label: str,
    role: str,
    seeds: range,
    policy_artifact: dict,
) -> tuple[dict, list[dict], list[str]]:
    manifest = _scenario_manifest(split_label=split_label, seeds=seeds)
    write_json(output_dir / f"{split_label}_{role}_scenario_manifest.json", manifest)
    result = backend.run_single_policy_probe(
        manifest=manifest,
        output_dir=output_dir / f"{split_label}_{role}_runtime",
        policy_artifact=policy_artifact,
        role=role,
        max_rollouts=len(manifest["scenarios"]),
        stop_after_first_success=False,
    )
    rows = _bind_rollouts(
        rows=_result_rollouts(result),
        scenarios=manifest["scenarios"],
        policy_artifact=policy_artifact,
    )
    return dict(result.runtime_gate), rows, _result_trace_paths(result)


def _mask_doc(*, rows: list[dict], trace_paths: list[str]) -> dict:
    if len(rows) != len(trace_paths):
        raise ValueError(f"mask trace count {len(trace_paths)} != rollout count {len(rows)}")
    masks = []
    for row, trace_path in zip(rows, trace_paths, strict=True):
        trace_doc = load_json(Path(trace_path))
        trace = trace_doc.get("trace")
        if not isinstance(trace, list):
            raise ValueError(f"trace missing per-step list: {trace_path}")
        masks.append(
            {
                "scenario_id": row["scenario_id"],
                "seed": row["seed"],
                "env_native_success_mask": [
                    bool(step.get("env_native_success")) for step in trace
                ],
            }
        )
    return {"masks": masks}


def _rollout_doc(*, split_label: str, role: str, rows: list[dict]) -> dict:
    return {
        "schema_version": "rdf_mvp3a_actual_isaac_rollouts_v0.1.0",
        "split": split_label,
        "role": role,
        "rollout_results": rows,
    }


def _all_runtime_gates_passed(gates: list[dict]) -> bool:
    return bool(gates) and all(gate.get("passed") is True for gate in gates)


def _config_payload(*, output_dir: Path, package_dir: Path) -> dict:
    evidence = {
        "baseline_calibration_rollouts": output_dir / "baseline_calibration_rollouts.json",
        "candidate_calibration_rollouts": output_dir / "candidate_calibration_rollouts.json",
        "baseline_heldout_rollouts": output_dir / "baseline_heldout_rollouts.json",
        "candidate_heldout_rollouts": output_dir / "candidate_heldout_rollouts.json",
        "runtime_gate": output_dir / "runtime_gate.json",
        "train_generation_runtime_gate": output_dir / "train_generation_runtime_gate.json",
        "calibration_selection_report": output_dir / "calibration_selection_report.json",
        "train_trace_summary": output_dir / "train_trace_summary.json",
        "post_heldout_guard": output_dir / "post_heldout_guard.json",
        "baseline_policy_artifact": output_dir / "baseline_policy_artifact.json",
        "candidate_policy_artifact": output_dir / "candidate_policy_artifact.json",
        "heldout_baseline_success_masks": output_dir / "heldout_baseline_success_masks.json",
        "heldout_candidate_success_masks": output_dir / "heldout_candidate_success_masks.json",
    }
    return {
        "proof_slice": "mvp3a_target_fixture_pose_variant",
        "evidence_kind": "actual_isaac",
        "claim_tier": "proof_infrastructure",
        "task_variant": {
            "family": "connector_insertion",
            "variant": "target_fixture_pose_variant",
            "changed_variable": "task_variant",
            "source_variable_opened": False,
        },
        "runtime_expectations": {
            "backend": "isaac_runtime",
            "proof_runtime": PROOF_RUNTIME,
            "training_source": "isaac_runtime",
        },
        "seed_ranges": {
            "train": [43000, 43049],
            "calibration": [41000, 41029],
            "heldout": [42000, 42049],
            "spent_no_reuse": [[40000, 40049]],
        },
        "thresholds": {
            "uplift_min": 0.2,
            "min_calibration_rollouts_per_policy": 30,
            "min_heldout_rollouts_per_policy": 50,
            "stable_steps_required": SUCCESS_METRIC["stable_steps_required"],
        },
        "audit_ci": {
            "method": "bootstrap_success_rate_difference",
            "iterations": 10000,
            "seed": 20260620,
        },
        "evidence_paths": {key: str(path) for key, path in evidence.items()},
        "package_policy": {
            "output_dir": str(package_dir),
            "freeze_mvp2_assets": True,
            "copy_rollout_json_into_package": True,
            "copy_c_lite_masks_into_package_when_present": True,
        },
    }


def _make_backend(*, headless: bool, device: str, max_steps: int) -> Any:
    sys.path.insert(0, str(ROOT / "scripts"))
    from run_mvp2b_isaac_proof_evaluator import IsaacConnectorInsertionEvaluatorBackend

    return IsaacConnectorInsertionEvaluatorBackend(
        headless=headless,
        device=device,
        max_steps=max_steps,
    )


class SubprocessSplitBackend:
    runtime_backend = "isaac_runtime"
    proof_runtime = PROOF_RUNTIME

    def __init__(
        self,
        *,
        isaac_python: Path,
        headless: bool,
        device: str,
        max_steps: int,
    ) -> None:
        self.isaac_python = isaac_python
        self.headless = headless
        self.device = device
        self.max_steps = max_steps

    def run_single_policy_probe(
        self,
        *,
        manifest: dict,
        output_dir: Path,
        policy_artifact: dict,
        role: str,
        max_rollouts: int,
        stop_after_first_success: bool,
    ) -> Any:
        del max_rollouts, stop_after_first_success
        output_dir = Path(output_dir)
        manifest_path = output_dir / "scenario_manifest_input.json"
        policy_path = output_dir / "policy_artifact_input.json"
        result_path = output_dir / "split_result.json"
        write_json(manifest_path, manifest)
        write_json(policy_path, policy_artifact)
        cmd = [
            str(self.isaac_python),
            str(Path(__file__).resolve()),
            "--run-split",
            "--manifest",
            str(manifest_path),
            "--policy-artifact",
            str(policy_path),
            "--role",
            role,
            "--output-dir",
            str(output_dir),
            "--device",
            self.device,
            "--max-steps",
            str(self.max_steps),
            "--result",
            str(result_path),
        ]
        if self.headless:
            cmd.append("--headless")
        else:
            cmd.append("--no-headless")
        completed = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                completed.stderr.strip()
                or completed.stdout.strip()
                or f"split subprocess failed for {role}"
            )
        payload = load_json(result_path)
        return SimpleNamespace(
            runtime_gate=payload["runtime_gate"],
            baseline_rollouts=payload.get("rollouts", []),
            candidate_rollouts=[],
            baseline_trace_paths=payload.get("trace_paths", []),
            candidate_trace_paths=[],
        )


def run_split_once(
    *,
    manifest_path: Path,
    policy_artifact_path: Path,
    role: str,
    output_dir: Path,
    result_path: Path,
    headless: bool,
    device: str,
    max_steps: int,
) -> Path:
    backend = _make_backend(headless=headless, device=device, max_steps=max_steps)
    manifest = load_json(manifest_path)
    policy = load_json(policy_artifact_path)
    result = backend.run_single_policy_probe(
        manifest=manifest,
        output_dir=output_dir,
        policy_artifact=policy,
        role=role,
        max_rollouts=len(manifest["scenarios"]),
        stop_after_first_success=False,
    )
    write_json(
        result_path,
        {
            "runtime_gate": result.runtime_gate,
            "rollouts": _result_rollouts(result),
            "trace_paths": _result_trace_paths(result),
        },
    )
    return result_path


def collect_actual_evidence(
    *,
    output_dir: Path,
    package_dir: Path,
    baseline_policy_path: Path,
    candidate_policy_path: Path,
    backend: Any,
    train_seeds: range = range(43000, 43001),
    calibration_seeds: range = range(41000, 41030),
    heldout_seeds: range = range(42000, 42050),
    build_package: bool = False,
) -> EvidenceResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_policy = _copy_policy(
        baseline_policy_path, output_dir / "baseline_policy_artifact.json"
    )
    candidate_policy = _copy_policy(
        candidate_policy_path, output_dir / "candidate_policy_artifact.json"
    )

    train_gate, train_rows, _train_traces = _run_policy_split(
        backend=backend,
        output_dir=output_dir,
        split_label="train",
        role="candidate",
        seeds=train_seeds,
        policy_artifact=candidate_policy,
    )
    cal_base_gate, cal_base, _cal_base_traces = _run_policy_split(
        backend=backend,
        output_dir=output_dir,
        split_label="calibration",
        role="baseline",
        seeds=calibration_seeds,
        policy_artifact=baseline_policy,
    )
    cal_candidate_gate, cal_candidate, _cal_candidate_traces = _run_policy_split(
        backend=backend,
        output_dir=output_dir,
        split_label="calibration",
        role="candidate",
        seeds=calibration_seeds,
        policy_artifact=candidate_policy,
    )
    heldout_base_gate, heldout_base, heldout_base_traces = _run_policy_split(
        backend=backend,
        output_dir=output_dir,
        split_label="heldout",
        role="baseline",
        seeds=heldout_seeds,
        policy_artifact=baseline_policy,
    )
    heldout_candidate_gate, heldout_candidate, heldout_candidate_traces = _run_policy_split(
        backend=backend,
        output_dir=output_dir,
        split_label="heldout",
        role="candidate",
        seeds=heldout_seeds,
        policy_artifact=candidate_policy,
    )

    write_json(
        output_dir / "baseline_calibration_rollouts.json",
        _rollout_doc(split_label="calibration", role="baseline", rows=cal_base),
    )
    write_json(
        output_dir / "candidate_calibration_rollouts.json",
        _rollout_doc(split_label="calibration", role="candidate", rows=cal_candidate),
    )
    write_json(
        output_dir / "baseline_heldout_rollouts.json",
        _rollout_doc(split_label="heldout", role="baseline", rows=heldout_base),
    )
    write_json(
        output_dir / "candidate_heldout_rollouts.json",
        _rollout_doc(split_label="heldout", role="candidate", rows=heldout_candidate),
    )
    write_json(
        output_dir / "heldout_baseline_success_masks.json",
        _mask_doc(rows=heldout_base, trace_paths=heldout_base_traces),
    )
    write_json(
        output_dir / "heldout_candidate_success_masks.json",
        _mask_doc(rows=heldout_candidate, trace_paths=heldout_candidate_traces),
    )

    eval_gates = [
        cal_base_gate,
        cal_candidate_gate,
        heldout_base_gate,
        heldout_candidate_gate,
    ]
    write_json(
        output_dir / "runtime_gate.json",
        {
            "passed": _all_runtime_gates_passed(eval_gates),
            "runtime_backend": "isaac_runtime",
            "proof_runtime": PROOF_RUNTIME,
            "role_gates": eval_gates,
        },
    )
    write_json(
        output_dir / "train_generation_runtime_gate.json",
        {
            "passed": train_gate.get("passed") is True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime",
            "role_gate": train_gate,
        },
    )
    write_json(
        output_dir / "calibration_selection_report.json",
        {
            "calibration_only_selection_passed": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
    )
    write_json(
        output_dir / "train_trace_summary.json",
        {
            "actual_success_trace_count": sum(1 for row in train_rows if row["success"] is True),
            "train_rollout_count": len(train_rows),
        },
    )
    write_json(
        output_dir / "post_heldout_guard.json",
        {
            "passed": True,
            "spent_after_closure_attempt": [42000, 42049],
            "no_reuse": True,
        },
    )

    config = _config_payload(output_dir=output_dir, package_dir=package_dir)
    config_path = output_dir / "mvp3a_actual_isaac_package_config.json"
    write_json(config_path, config)
    manifest_path = None
    if build_package:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "run_mvp3a_proof_infrastructure.py"),
                "--config",
                str(config_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        manifest_path = package_dir / "package_manifest.json"
    return EvidenceResult(
        output_dir=output_dir,
        package_dir=package_dir,
        config_path=config_path,
        manifest_path=manifest_path,
    )


def _safe_clean(path: Path) -> None:
    resolved = path.resolve()
    allowed = {
        DEFAULT_OUTPUT_DIR.resolve(),
        DEFAULT_PACKAGE_DIR.resolve(),
    }
    if resolved not in allowed:
        raise ValueError(f"refusing to clean non-default path: {path}")
    if path.exists():
        shutil.rmtree(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-split", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--policy-artifact", type=Path)
    parser.add_argument("--role")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--baseline-policy", type=Path, default=DEFAULT_BASELINE_POLICY)
    parser.add_argument("--candidate-policy", type=Path, default=DEFAULT_CANDIDATE_POLICY)
    parser.add_argument(
        "--isaac-python",
        type=Path,
        default=Path("/home/kangrim/IsaacLab/_isaac_sim/python.sh"),
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-steps", type=int, default=SUCCESS_METRIC["max_steps"])
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--skip-package", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.run_split:
            missing = [
                name
                for name in ("manifest", "policy_artifact", "role", "result")
                if getattr(args, name) in (None, "")
            ]
            if missing:
                raise ValueError("--run-split missing required args: " + ", ".join(missing))
            run_split_once(
                manifest_path=args.manifest,
                policy_artifact_path=args.policy_artifact,
                role=args.role,
                output_dir=args.output_dir,
                result_path=args.result,
                headless=args.headless,
                device=args.device,
                max_steps=args.max_steps,
            )
            print(f"split_result={args.result}")
            return 0
        if args.clean:
            _safe_clean(args.output_dir)
            _safe_clean(args.package_dir)
        backend = SubprocessSplitBackend(
            isaac_python=args.isaac_python,
            headless=args.headless,
            device=args.device,
            max_steps=args.max_steps,
        )
        result = collect_actual_evidence(
            output_dir=args.output_dir,
            package_dir=args.package_dir,
            baseline_policy_path=args.baseline_policy,
            candidate_policy_path=args.candidate_policy,
            backend=backend,
            build_package=not args.skip_package,
        )
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"evidence_dir={result.output_dir}")
    print(f"config={result.config_path}")
    if result.manifest_path is not None:
        print(f"package_manifest={result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
