from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_verify_proof_package import (
    _mask_doc,
    _policy_artifact,
    _rollouts,
    _stable_json,
    _write_json,
)


ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts" / "run_mvp3a_proof_infrastructure.py"
VERIFIER = ROOT / "scripts" / "verify_proof_package.py"


def _write_evidence(
    tmp_path: Path,
    *,
    positive: bool = True,
    include_actual_provenance: bool = False,
) -> dict:
    evidence = tmp_path / "evidence"
    heldout_candidate_successes = 40 if positive else 5
    baseline_policy = _policy_artifact("baseline")
    candidate_policy = _policy_artifact("candidate")
    baseline_policy_hash = (
        baseline_policy["policy_artifact_sha256"] if include_actual_provenance else None
    )
    candidate_policy_hash = (
        candidate_policy["policy_artifact_sha256"] if include_actual_provenance else None
    )
    paths = {
        "baseline_calibration_rollouts": evidence / "baseline_calibration_rollouts.json",
        "candidate_calibration_rollouts": evidence / "candidate_calibration_rollouts.json",
        "baseline_heldout_rollouts": evidence / "baseline_heldout_rollouts.json",
        "candidate_heldout_rollouts": evidence / "candidate_heldout_rollouts.json",
        "runtime_gate": evidence / "runtime_gate.json",
        "train_generation_runtime_gate": evidence / "train_generation_runtime_gate.json",
        "calibration_selection_report": evidence / "calibration_selection_report.json",
        "train_trace_summary": evidence / "train_trace_summary.json",
        "post_heldout_guard": evidence / "post_heldout_guard.json",
    }
    if include_actual_provenance:
        paths.update(
            {
                "baseline_policy_artifact": evidence / "baseline_policy_artifact.json",
                "candidate_policy_artifact": evidence / "candidate_policy_artifact.json",
                "heldout_baseline_success_masks": evidence
                / "heldout_baseline_success_masks.json",
                "heldout_candidate_success_masks": evidence
                / "heldout_candidate_success_masks.json",
            }
        )
        _write_json(paths["baseline_policy_artifact"], baseline_policy)
        _write_json(paths["candidate_policy_artifact"], candidate_policy)
        _write_json(paths["heldout_baseline_success_masks"], _mask_doc(range(42000, 42050), 5))
        _write_json(
            paths["heldout_candidate_success_masks"],
            _mask_doc(range(42000, 42050), heldout_candidate_successes),
        )
    _write_json(
        paths["baseline_calibration_rollouts"],
        _rollouts(range(41000, 41030), 5, policy_hash=baseline_policy_hash),
    )
    _write_json(
        paths["candidate_calibration_rollouts"],
        _rollouts(range(41000, 41030), 26, policy_hash=candidate_policy_hash),
    )
    _write_json(
        paths["baseline_heldout_rollouts"],
        _rollouts(range(42000, 42050), 5, policy_hash=baseline_policy_hash),
    )
    _write_json(
        paths["candidate_heldout_rollouts"],
        _rollouts(
            range(42000, 42050),
            heldout_candidate_successes,
            policy_hash=candidate_policy_hash,
        ),
    )
    _write_json(
        paths["runtime_gate"],
        {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
    )
    _write_json(
        paths["train_generation_runtime_gate"],
        {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime",
        },
    )
    _write_json(
        paths["calibration_selection_report"],
        {
            "calibration_only_selection_passed": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
    )
    _write_json(paths["train_trace_summary"], {"actual_success_trace_count": 1})
    _write_json(paths["post_heldout_guard"], {"passed": True})
    return {key: str(path) for key, path in paths.items()}


def _write_config(
    tmp_path: Path,
    evidence_paths: dict,
    output_dir: Path,
    *,
    evidence_kind: str = "synthetic_test_fixture",
    source_opened: bool = False,
) -> Path:
    config = {
        "proof_slice": "mvp3a_target_fixture_pose_variant",
        "evidence_kind": evidence_kind,
        "claim_tier": "proof_infrastructure",
        "task_variant": {
            "family": "connector_insertion",
            "variant": "target_fixture_pose_variant",
            "changed_variable": "task_variant",
            "source_variable_opened": source_opened,
        },
        "runtime_expectations": {
            "backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
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
            "stable_steps_required": 10,
        },
        "audit_ci": {
            "method": "bootstrap_success_rate_difference",
            "iterations": 200,
            "seed": 20260620,
        },
        "evidence_paths": evidence_paths,
        "package_policy": {
            "output_dir": str(output_dir),
            "freeze_mvp2_assets": True,
            "copy_rollout_json_into_package": True,
            "copy_c_lite_masks_into_package_when_present": True,
        },
    }
    path = tmp_path / "config.json"
    path.write_text(_stable_json(config) + "\n", encoding="utf-8")
    return path


def _run_runner(config: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--config", str(config)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_runner_writes_self_contained_positive_package(tmp_path: Path):
    output = tmp_path / "package"
    config = _write_config(tmp_path, _write_evidence(tmp_path, positive=True), output)

    result = _run_runner(config)

    assert result.returncode == 0, result.stderr
    assert (output / "data" / "rollouts" / "heldout_candidate_rollouts.json").is_file()
    assert (output / "data" / "gates" / "runtime_gate.json").is_file()
    closure = json.loads((output / "data" / "closure_verdict.json").read_text())
    assert closure["package_status"] == "synthetic_verifier_fixture"
    verify = subprocess.run(
        [sys.executable, str(VERIFIER), str(output / "package_manifest.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_runner_nonclosing_package_has_no_learning_addendum(tmp_path: Path):
    output = tmp_path / "package"
    config = _write_config(tmp_path, _write_evidence(tmp_path, positive=False), output)

    result = _run_runner(config)

    assert result.returncode == 0, result.stderr
    assert not (output / "addenda" / "learning_proven").exists()
    summary = json.loads((output / "data" / "learning_result_summary.json").read_text())
    assert summary["learning_result"] == "non_closing"


def test_runner_rejects_source_variable_opened(tmp_path: Path):
    output = tmp_path / "package"
    config = _write_config(
        tmp_path,
        _write_evidence(tmp_path),
        output,
        source_opened=True,
    )

    result = _run_runner(config)

    assert result.returncode == 1
    assert "source_variable_opened" in result.stderr


def test_runner_rejects_missing_train_seed_range(tmp_path: Path):
    output = tmp_path / "package"
    config = _write_config(tmp_path, _write_evidence(tmp_path), output)
    payload = json.loads(config.read_text())
    payload["seed_ranges"].pop("train")
    config.write_text(_stable_json(payload) + "\n", encoding="utf-8")

    result = _run_runner(config)

    assert result.returncode == 1
    assert "train range" in result.stderr


def test_runner_rejects_actual_isaac_without_provenance(tmp_path: Path):
    output = tmp_path / "package"
    config = _write_config(
        tmp_path,
        _write_evidence(tmp_path, positive=True),
        output,
        evidence_kind="actual_isaac",
    )

    result = _run_runner(config)

    assert result.returncode == 1
    assert "actual_isaac provenance" in result.stderr


def test_runner_writes_actual_isaac_package_with_provenance(tmp_path: Path):
    output = tmp_path / "package"
    config = _write_config(
        tmp_path,
        _write_evidence(
            tmp_path,
            positive=True,
            include_actual_provenance=True,
        ),
        output,
        evidence_kind="actual_isaac",
    )

    result = _run_runner(config)

    assert result.returncode == 0, result.stderr
    closure = json.loads((output / "data" / "closure_verdict.json").read_text())
    assert closure["package_status"] == "proof_infrastructure_closed"
    assert (output / "addenda" / "learning_proven" / "learning_proven_report.json").is_file()
    verify = subprocess.run(
        [sys.executable, str(VERIFIER), str(output / "package_manifest.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_runner_marks_actual_isaac_gate_failure_as_failed_package(tmp_path: Path):
    output = tmp_path / "package"
    evidence_paths = _write_evidence(
        tmp_path,
        positive=True,
        include_actual_provenance=True,
    )
    train_trace = Path(evidence_paths["train_trace_summary"])
    payload = json.loads(train_trace.read_text())
    payload["actual_success_trace_count"] = 0
    train_trace.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    config = _write_config(
        tmp_path,
        evidence_paths,
        output,
        evidence_kind="actual_isaac",
    )

    result = _run_runner(config)

    assert result.returncode == 0, result.stderr
    closure = json.loads((output / "data" / "closure_verdict.json").read_text())
    assert closure["closed"] is False
    assert closure["package_status"] == "proof_infrastructure_failed"
    assert closure["learning_proven_addendum"] == "absent"
    assert not (output / "addenda" / "learning_proven").exists()
