#!/usr/bin/env python3
"""Check MVP-2 policy-uplift readiness before fresh HUD data ingest.

This preflight assumes MVP-1 is a learning-ready dataset pipeline proof. It
checks that the curated-vs-uncurated learning-value path is wired up for the
next MVP-2 learning-proven policy A/B, without claiming policy uplift.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_mvp1_proof_audit import build_audit
from run_mvp1c_headless_eval_bundle import build_headless_eval_bundle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READINESS_DIR = ROOT / "storage" / "mvp1_readiness"
DEFAULT_HEADLESS_EVAL_DIR = ROOT / "storage" / "mvp1c_headless_eval"
DEFAULT_ISAAC_SMOKE_DIR = ROOT / "storage" / "mvp1c_isaac_policy_ab_smoke"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp1c_final_hud_ingest_preflight"
SCHEMA_VERSION = "rdf_mvp2_policy_uplift_ingest_preflight_v0.2.0"
EXPECTED_MVP2_GATE = "curated_vs_uncurated_policy_uplift_positive"
VALID_POLICY_EVAL_TIERS = {"heldout_policy_eval", "real_heldout_policy_eval"}


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, stable_json(payload) + "\n")


def _exists(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists()}


def _list_missing_gate_names(audit: dict[str, Any]) -> list[str]:
    return [str(item.get("name")) for item in audit.get("missing_required_gates", []) if isinstance(item, dict)]


def _audit_summary(audit: dict[str, Any]) -> dict[str, Any]:
    staged = audit.get("staged_mvp1") if isinstance(audit.get("staged_mvp1"), dict) else {}
    return {
        "status": audit.get("status"),
        "full_mvp1_proof_achieved": audit.get("full_mvp1_proof_achieved"),
        "current_stage": staged.get("current_stage"),
        "next_stage": staged.get("next_stage"),
        "proof_model": audit.get("proof_model"),
        "policy_uplift_required_for_mvp1": audit.get("policy_uplift_required_for_mvp1"),
        "learning_ready": (audit.get("summary") or {}).get("learning_ready") if isinstance(audit.get("summary"), dict) else None,
        "learning_proven": (audit.get("summary") or {}).get("learning_proven") if isinstance(audit.get("summary"), dict) else None,
        "passed_required_gates": audit.get("passed_required_gates"),
        "required_gate_count": audit.get("required_gate_count"),
        "missing_required_gates": _list_missing_gate_names(audit),
        "mvp2_policy_uplift": audit.get("mvp2_policy_uplift_proof"),
    }


def _check_policy_eval_template(path: Path) -> dict[str, Any]:
    template = read_json(path)
    if template is None:
        return {
            "path": str(path),
            "exists": path.exists(),
            "valid": False,
            "issues": ["policy eval template is missing or invalid JSON"],
        }

    issues: list[str] = []
    baseline = template.get("baseline") if isinstance(template.get("baseline"), dict) else {}
    candidate = template.get("candidate") if isinstance(template.get("candidate"), dict) else {}
    eval_suite = template.get("eval_suite") if isinstance(template.get("eval_suite"), dict) else {}
    if template.get("evidence_tier") not in VALID_POLICY_EVAL_TIERS:
        issues.append("template evidence_tier must be heldout_policy_eval or real_heldout_policy_eval")
    if template.get("primary_metric") != "policy_success_rate":
        issues.append("template primary_metric must be policy_success_rate")
    if eval_suite.get("held_out") is not True:
        issues.append("template eval_suite.held_out must be true")
    for role, policy in (("baseline", baseline), ("candidate", candidate)):
        if not isinstance(policy.get("rollout_results"), list):
            issues.append(f"{role}.rollout_results must be a list")
        if policy.get("rollout_results"):
            issues.append(f"{role}.rollout_results should be empty before fresh HUD eval")
        train_hdf5_path = policy.get("train_hdf5_path")
        if not isinstance(train_hdf5_path, str) or not Path(train_hdf5_path).exists():
            issues.append(f"{role}.train_hdf5_path is missing or does not exist")

    return {
        "path": str(path),
        "exists": True,
        "valid": not issues,
        "evidence_tier": template.get("evidence_tier"),
        "primary_metric": template.get("primary_metric"),
        "held_out": eval_suite.get("held_out"),
        "scenario_count": len(eval_suite.get("scenario_ids", [])) if isinstance(eval_suite.get("scenario_ids"), list) else 0,
        "baseline_train_hdf5_path": baseline.get("train_hdf5_path"),
        "candidate_train_hdf5_path": candidate.get("train_hdf5_path"),
        "baseline_rollout_count": len(baseline.get("rollout_results", [])) if isinstance(baseline.get("rollout_results"), list) else None,
        "candidate_rollout_count": len(candidate.get("rollout_results", [])) if isinstance(candidate.get("rollout_results"), list) else None,
        "issues": issues,
    }


def _check_headless_bundle(headless_eval_dir: Path) -> dict[str, Any]:
    report_path = headless_eval_dir / "headless_eval_bundle_report.json"
    report = read_json(report_path)
    template_check = _check_policy_eval_template(headless_eval_dir / "policy_eval_input_template.json")
    issues: list[str] = []
    if report is None:
        issues.append("headless eval bundle report is missing or invalid")
        report = {}
    elif report.get("passed") is not True:
        issues.append("headless eval bundle report did not pass")
    issues.extend(f"template: {issue}" for issue in template_check["issues"])

    baseline = report.get("baseline") if isinstance(report.get("baseline"), dict) else {}
    candidate = report.get("candidate") if isinstance(report.get("candidate"), dict) else {}
    return {
        "report_path": str(report_path),
        "passed": report.get("passed"),
        "proof_eligible": report.get("proof_eligible"),
        "baseline_train_count": len(baseline.get("train_episode_ids", [])) if isinstance(baseline.get("train_episode_ids"), list) else 0,
        "candidate_train_count": len(candidate.get("train_episode_ids", [])) if isinstance(candidate.get("train_episode_ids"), list) else 0,
        "policy_eval_template": template_check,
        "issues": issues,
    }


def _check_isaac_smoke(isaac_smoke_dir: Path) -> dict[str, Any]:
    report_path = isaac_smoke_dir / "isaac_policy_ab_smoke_report.json"
    report = read_json(report_path)
    if report is None:
        return {
            "available": False,
            "report_path": str(report_path),
            "issues": [],
            "warnings": ["Isaac headless smoke report is optional and currently unavailable."],
        }

    warnings: list[str] = []
    if report.get("evidence_tier") != "isaac_headless_policy_eval_smoke":
        warnings.append("Isaac smoke report evidence_tier is not smoke-only; inspect before using.")
    if report.get("proof_eligible") is not False:
        warnings.append("Isaac smoke report should not be proof eligible by default.")
    return {
        "available": True,
        "report_path": str(report_path),
        "passed": report.get("passed"),
        "action_scale": report.get("action_scale"),
        "baseline_success_rate": (report.get("baseline") or {}).get("success_rate") if isinstance(report.get("baseline"), dict) else None,
        "candidate_success_rate": (report.get("candidate") or {}).get("success_rate") if isinstance(report.get("candidate"), dict) else None,
        "evidence_tier": report.get("evidence_tier"),
        "proof_eligible": report.get("proof_eligible"),
        "issues": report.get("issues", []),
        "warnings": warnings,
    }


def _fresh_hud_requirements(min_rollouts_per_policy: int) -> list[str]:
    return [
        "Collect proof-grade peg-in-hole or connector insertion trajectories from Quest/SteamVR/OpenXR/Isaac with metadata.task_state.",
        "Refresh or replace the uncurated and curated train HDF5 views using the fresh live dataset.",
        "Train baseline on the uncurated success-lifecycle view and candidate on the curated accepted view.",
        "Evaluate both policies headlessly on the same held-out insertion scenario ids.",
        f"Provide at least {min_rollouts_per_policy} rollout results per policy.",
        "Use evidence_tier=heldout_policy_eval for headless Isaac A/B, or real_heldout_policy_eval only when HMD live accepted trajectories are included.",
        "Use primary_metric=policy_success_rate; rollout_success_rate is secondary.",
        "Only a positive curated-minus-uncurated success-rate delta can pass MVP-2 learning-proven proof.",
    ]


def _final_commands(headless_eval_dir: Path, min_rollouts_per_policy: int) -> list[str]:
    return [
        "uv run python scripts/run_mvp0_offline_diagnostics.py",
        "uv run python scripts/run_mvp1_live_export_smoke.py --clean --pretty",
        "uv run python scripts/run_mvp1c_headless_eval_bundle.py --clean --pretty",
        (
            "uv run python scripts/run_mvp1c_rollout_result_adapter.py "
            f"--template {headless_eval_dir / 'policy_eval_input_template.json'} "
            "--baseline-results <baseline_heldout_rollouts.csv-or-json> "
            "--candidate-results <candidate_heldout_rollouts.csv-or-json> "
            f"--output {headless_eval_dir / 'policy_eval_input.json'} "
            "--policy-class <policy_class> --trainer <trainer_name>"
        ),
        (
            "uv run python scripts/run_mvp1c_real_policy_eval.py "
            f"--input {headless_eval_dir / 'policy_eval_input.json'} "
            f"--min-rollouts-per-policy {min_rollouts_per_policy} --pretty"
        ),
        "uv run python scripts/run_mvp1_proof_audit.py --pretty",
    ]


def _runbook(report: dict[str, Any]) -> str:
    commands = "\n".join(f"{index}. `{command}`" for index, command in enumerate(report["final_commands"], start=1))
    requirements = "\n".join(f"- {item}" for item in report["fresh_hud_data_requirements"])
    issues = "\n".join(f"- {item}" for item in report["issues"]) or "- none"
    warnings = "\n".join(f"- {item}" for item in report["warnings"]) or "- none"
    return f"""# MVP-2 Policy Uplift HUD Data Ingest Runbook

Generated: {report["created_at"]}

## Status

- ready_for_final_hud_ingest: `{str(report["ready_for_final_hud_ingest"]).lower()}`
- mvp2_learning_proven_claimed: `{str(report["mvp2_learning_proven_claimed"]).lower()}`
- current_stage: `{report["proof_audit"]["current_stage"]}`
- next_stage: `{report["proof_audit"]["next_stage"]}`
- learning_ready: `{str(report["proof_audit"]["learning_ready"]).lower()}`
- learning_proven: `{str(report["proof_audit"]["learning_proven"]).lower()}`
- missing_required_gates: `{", ".join(report["proof_audit"]["missing_required_gates"]) or "none"}`

## Fresh HUD Data Requirements

{requirements}

## Final Commands After Fresh HUD Data Exists

{commands}

## Issues

{issues}

## Warnings

{warnings}
"""


def run_preflight(
    *,
    readiness_dir: Path,
    headless_eval_dir: Path,
    isaac_smoke_dir: Path,
    trajectory_dir: Path,
    output_dir: Path,
    refresh_headless_bundle: bool,
    min_rollouts_per_policy: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if refresh_headless_bundle:
        build_headless_eval_bundle(
            readiness_dir=readiness_dir,
            output_dir=headless_eval_dir,
            clean=True,
            task_type="peg_in_hole",
        )

    audit = build_audit(
        readiness_report_path=readiness_dir / "readiness_report.json",
        curation_manifest_path=readiness_dir / "curation_manifest.json",
        split_manifest_path=readiness_dir / "split_manifest.json",
        dataset_card_path=readiness_dir / "dataset_card.json",
        hdf5_inspection_path=readiness_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=readiness_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit_snapshot.json",
    )
    audit_summary = _audit_summary(audit)
    headless_bundle = _check_headless_bundle(headless_eval_dir)
    isaac_smoke = _check_isaac_smoke(isaac_smoke_dir)

    required_scripts = {
        "headless_eval_bundle": ROOT / "scripts" / "run_mvp1c_headless_eval_bundle.py",
        "rollout_result_adapter": ROOT / "scripts" / "run_mvp1c_rollout_result_adapter.py",
        "real_policy_eval": ROOT / "scripts" / "run_mvp1c_real_policy_eval.py",
        "proof_audit": ROOT / "scripts" / "run_mvp1_proof_audit.py",
    }
    script_checks = {name: _exists(path) for name, path in required_scripts.items()}

    issues: list[str] = []
    warnings: list[str] = [
        "This preflight must not be used to claim policy uplift; it only prepares the MVP-2 learning-proven A/B ingest.",
    ]
    missing_gates = set(audit_summary["missing_required_gates"])
    if audit_summary["current_stage"] != "MVP-1" or audit_summary["next_stage"] != "MVP-2":
        issues.append("proof audit is not exactly at MVP-1 -> MVP-2")
    if missing_gates:
        issues.append(f"MVP-1 learning-ready gates are still missing: {sorted(missing_gates)}")
    for name, check in script_checks.items():
        if not check["exists"]:
            issues.append(f"required script missing: {name}")
    issues.extend(f"headless_bundle: {issue}" for issue in headless_bundle["issues"])
    if isaac_smoke["available"]:
        warnings.extend(f"isaac_smoke: {warning}" for warning in isaac_smoke["warnings"])
        if isaac_smoke.get("baseline_success_rate") == 0.0 and isaac_smoke.get("candidate_success_rate") == 0.0:
            warnings.append("current Isaac smoke path runs, but both smoke policies still have 0.0 success rate.")
    else:
        warnings.extend(isaac_smoke["warnings"])

    ready = not issues
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "ready_for_mvp2_policy_uplift_ingest" if ready else "blocked",
        "ready_for_final_hud_ingest": ready,
        "ready_for_mvp2_policy_uplift_ingest": ready,
        "full_mvp1c_claimed": False,
        "mvp2_learning_proven_claimed": False,
        "expected_mvp2_gate": EXPECTED_MVP2_GATE,
        "proof_audit": audit_summary,
        "headless_bundle": headless_bundle,
        "script_checks": script_checks,
        "isaac_headless_smoke": isaac_smoke,
        "fresh_hud_data_requirements": _fresh_hud_requirements(min_rollouts_per_policy),
        "final_commands": _final_commands(headless_eval_dir, min_rollouts_per_policy),
        "issues": issues,
        "warnings": warnings,
    }
    write_json(output_dir / "preflight_report.json", report)
    write_text(output_dir / "final_hud_ingest_runbook.md", _runbook(report))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument("--headless-eval-dir", type=Path, default=DEFAULT_HEADLESS_EVAL_DIR)
    parser.add_argument("--isaac-smoke-dir", type=Path, default=DEFAULT_ISAAC_SMOKE_DIR)
    parser.add_argument("--trajectory-dir", type=Path, default=ROOT / "storage" / "trajectories")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--refresh-headless-bundle", action="store_true")
    parser.add_argument("--min-rollouts-per-policy", type=int, default=10)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless ready_for_final_hud_ingest is true.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_preflight(
        readiness_dir=args.readiness_dir,
        headless_eval_dir=args.headless_eval_dir,
        isaac_smoke_dir=args.isaac_smoke_dir,
        trajectory_dir=args.trajectory_dir,
        output_dir=args.output_dir,
        refresh_headless_bundle=args.refresh_headless_bundle,
        min_rollouts_per_policy=args.min_rollouts_per_policy,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        print(f"RDF MVP-2 policy uplift ingest preflight: {report['status'].upper()}")
        print(f"ready_for_final_hud_ingest={report['ready_for_final_hud_ingest']}")
        print(f"current_stage={report['proof_audit']['current_stage']}")
        print(f"next_stage={report['proof_audit']['next_stage']}")
        print(f"missing_required_gates={report['proof_audit']['missing_required_gates']}")
        print(f"report={args.output_dir / 'preflight_report.json'}")
    return 1 if args.strict and not report["ready_for_final_hud_ingest"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
