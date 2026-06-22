#!/usr/bin/env python3
"""Generic proof package verifier for Robot Data Forge proof slices.

This verifier is intentionally stdlib-only and independent from producer code.
It treats cached verdict files as summaries, not truth. Verdict-critical facts
are recomputed from the package's self-contained data/rollouts/ and data/gates/
JSON bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path


FORBIDDEN_TRUE_CLAIMS = (
    "real_robot_success",
    "physical_robot_readiness",
    "deployable_policy_readiness",
    "visual_policy_performance",
    "hmd_openxr_collection_readiness",
    "universal_robot_support",
    "ur_adapter_support",
    "ros2_dds_adapter_support",
    "franka_hardware_support",
    "marketplace_readiness",
    "production_certification",
)

ROLLOUT_FILES = {
    "calibration": {
        "baseline": "data/rollouts/calibration_baseline_rollouts.json",
        "candidate": "data/rollouts/calibration_candidate_rollouts.json",
    },
    "heldout": {
        "baseline": "data/rollouts/heldout_baseline_rollouts.json",
        "candidate": "data/rollouts/heldout_candidate_rollouts.json",
    },
}

MANDATORY_DATA_PATHS = {
    "data/config.json",
    "data/task_variant_attestation.json",
    "data/seed_discipline_report.json",
    "data/closure_verdict.json",
    "data/learning_result_summary.json",
    "data/non_claims_attestation.json",
    "data/artifact_index.json",
    "data/gates/runtime_gate.json",
    "data/gates/train_generation_runtime_gate.json",
    "data/gates/calibration_selection_report.json",
    "data/gates/train_trace_summary.json",
    "data/gates/post_heldout_guard.json",
    "data/rollouts/calibration_baseline_rollouts.json",
    "data/rollouts/calibration_candidate_rollouts.json",
    "data/rollouts/heldout_baseline_rollouts.json",
    "data/rollouts/heldout_candidate_rollouts.json",
}

MVP3A_EXPECTED_TRAIN_RANGE = [43000, 43049]
MVP3A_EXPECTED_CALIBRATION_RANGE = [41000, 41029]
MVP3A_EXPECTED_HELDOUT_RANGE = [42000, 42049]
MVP2_SPENT_RANGE = [40000, 40049]
MVP3A_PROOF_RUNTIME = "dedicated_isaac_connector_insertion_evaluator"

POLICY_FILES = {
    "baseline": "data/policies/baseline_policy_artifact.json",
    "candidate": "data/policies/candidate_policy_artifact.json",
}

MASK_FILES = {
    "baseline": "data/masks/heldout_baseline_success_masks.json",
    "candidate": "data/masks/heldout_candidate_success_masks.json",
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)
    recomputed: dict = field(default_factory=dict)
    advisory: dict = field(default_factory=dict)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(CheckResult(name=name, passed=passed, detail=detail))

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def failures(self) -> list[str]:
        return [f"{check.name}: {check.detail}" for check in self.checks if not check.passed]


def stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_payload_sha256(payload: dict, *, omit_key: str) -> str:
    canonical = dict(payload)
    canonical.pop(omit_key, None)
    return hashlib.sha256(stable_json(canonical).encode("utf-8")).hexdigest()


def seeds_in_range(span: list[int] | tuple[int, int]) -> set[int]:
    start, end = int(span[0]), int(span[1])
    if start > end:
        raise ValueError(f"invalid seed range: {span}")
    return set(range(start, end + 1))


def trailing_int(label: object) -> int | None:
    match = re.search(r"(\d+)$", str(label))
    return int(match.group(1)) if match else None


def check_hash_integrity(pkg_dir: Path, manifest: dict, report: Report) -> None:
    problems: list[str] = []
    checked = 0
    for entry in manifest.get("artifact_index", []):
        rel = entry.get("data_path")
        if not rel:
            continue
        path = pkg_dir / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
            continue
        if entry.get("hash_convention", "file_bytes") != "file_bytes":
            problems.append(f"unsupported hash convention for {rel}")
            continue
        actual = sha256_file(path)
        if actual != entry.get("file_sha256"):
            problems.append(f"sha256 mismatch {rel}")
        else:
            checked += 1
    detail = f"{checked} manifest data hashes match" if not problems else "; ".join(problems)
    report.add("hash_integrity", not problems, detail)


def check_manifest_data_coverage(pkg_dir: Path, manifest: dict, report: Report) -> None:
    indexed = {
        entry.get("data_path")
        for entry in manifest.get("artifact_index", [])
        if entry.get("data_path")
    }
    actual = {
        path.relative_to(pkg_dir).as_posix()
        for path in (pkg_dir / "data").rglob("*.json")
        if path.is_file()
    }
    missing_required = sorted(MANDATORY_DATA_PATHS - indexed)
    unindexed_actual = sorted(actual - indexed)
    problems = []
    if missing_required:
        problems.append(f"missing required index entries: {missing_required}")
    if unindexed_actual:
        problems.append(f"unindexed data files: {unindexed_actual}")
    report.add(
        "manifest_data_coverage",
        not problems,
        "all package data json files are indexed"
        if not problems
        else "; ".join(problems),
    )


def rollout_records(doc: dict) -> list[dict]:
    rows = doc.get("rollout_results")
    if not isinstance(rows, list):
        raise ValueError("rollout document missing rollout_results list")
    return rows


def rollout_success(row: dict, stable_steps_required: int) -> tuple[bool, list[str]]:
    problems: list[str] = []
    recorded = row.get("success")
    max_consecutive = row.get("env_native_max_consecutive_success_steps")
    if not isinstance(recorded, bool):
        problems.append("success must be bool")
        recorded = False
    if not isinstance(max_consecutive, int) or isinstance(max_consecutive, bool):
        problems.append("env_native_max_consecutive_success_steps must be int")
        max_consecutive = -1
    derived = max_consecutive >= stable_steps_required
    native = row.get("env_native_rollout_success")
    if native is not None and native != derived:
        problems.append("env_native_rollout_success contradicts consecutive threshold")
    if recorded != derived:
        problems.append("success contradicts consecutive threshold")
    return derived, problems


def summarize_rollouts(path: Path, stable_steps_required: int) -> tuple[dict, list[str]]:
    rows = rollout_records(load_json(path))
    successes = 0
    seeds: list[int | None] = []
    problems: list[str] = []
    for index, row in enumerate(rows):
        derived, row_problems = rollout_success(row, stable_steps_required)
        if derived:
            successes += 1
        seed = row.get("seed", trailing_int(row.get("scenario_id")))
        seeds.append(seed)
        for problem in row_problems:
            problems.append(f"{path.name}[{index}]: {problem}")
    total = len(rows)
    return (
        {
            "rollouts": total,
            "successes": successes,
            "rate": successes / total if total else 0.0,
            "seeds": seeds,
        },
        problems,
    )


def recompute_rollout_summaries(
    pkg_dir: Path, stable_steps_required: int, report: Report
) -> dict:
    summaries: dict[str, dict] = {}
    label_problems: list[str] = []
    missing: list[str] = []
    for split, roles in ROLLOUT_FILES.items():
        summaries[split] = {}
        for role, rel in roles.items():
            path = pkg_dir / rel
            if not path.is_file():
                missing.append(rel)
                summaries[split][role] = {
                    "rollouts": 0,
                    "successes": 0,
                    "rate": 0.0,
                    "seeds": [],
                }
                continue
            summary, problems = summarize_rollouts(path, stable_steps_required)
            summaries[split][role] = summary
            label_problems.extend(problems)

    threshold_detail = _rollout_threshold_detail(summaries, pkg_dir)
    rollout_ok = not missing and not threshold_detail
    detail = "rollout counts satisfy thresholds"
    if missing or threshold_detail:
        detail = "; ".join([*missing, *threshold_detail])
    report.add("rollout_recompute", rollout_ok, detail)
    report.add(
        "label_recompute",
        not label_problems,
        "all rollout labels match consecutive threshold"
        if not label_problems
        else "; ".join(label_problems[:8]),
    )
    return summaries


def _rollout_threshold_detail(summaries: dict, pkg_dir: Path) -> list[str]:
    config = load_json(pkg_dir / "data" / "config.json")
    thresholds = config["thresholds"]
    checks = [
        (
            "calibration",
            int(thresholds["min_calibration_rollouts_per_policy"]),
        ),
        ("heldout", int(thresholds["min_heldout_rollouts_per_policy"])),
    ]
    problems: list[str] = []
    for split, minimum in checks:
        for role in ("baseline", "candidate"):
            actual = summaries[split][role]["rollouts"]
            if actual < minimum:
                problems.append(f"{split}/{role} rollouts {actual} < {minimum}")
    return problems


def bootstrap_success_rate_difference_ci(
    *,
    baseline_successes: int,
    baseline_total: int,
    candidate_successes: int,
    candidate_total: int,
    iterations: int,
    seed: int,
) -> dict:
    baseline = [1] * baseline_successes + [0] * (baseline_total - baseline_successes)
    candidate = [1] * candidate_successes + [0] * (candidate_total - candidate_successes)
    rng = random.Random(seed)
    diffs: list[float] = []
    for _ in range(iterations):
        b_rate = sum(rng.choice(baseline) for _ in baseline) / len(baseline)
        c_rate = sum(rng.choice(candidate) for _ in candidate) / len(candidate)
        diffs.append(c_rate - b_rate)
    diffs.sort()
    lower = diffs[int(0.025 * (len(diffs) - 1))]
    upper = diffs[int(0.975 * (len(diffs) - 1))]
    return {
        "method": "bootstrap_success_rate_difference",
        "iterations": iterations,
        "seed": seed,
        "lower": lower,
        "upper": upper,
    }


def add_learning_recompute(report: Report, config: dict, summaries: dict) -> None:
    heldout = summaries["heldout"]
    baseline = heldout["baseline"]
    candidate = heldout["candidate"]
    uplift = candidate["rate"] - baseline["rate"]
    positive = (
        candidate["rate"] > baseline["rate"] and uplift >= config["thresholds"]["uplift_min"]
    )
    learning_result = "positive_uplift" if positive else "non_closing"
    audit_ci = config.get("audit_ci", {})
    ci = bootstrap_success_rate_difference_ci(
        baseline_successes=baseline["successes"],
        baseline_total=baseline["rollouts"],
        candidate_successes=candidate["successes"],
        candidate_total=candidate["rollouts"],
        iterations=int(audit_ci.get("iterations", 1000)),
        seed=int(audit_ci.get("seed", 0)),
    )
    heldout["uplift"] = uplift
    heldout["confidence_interval"] = ci
    report.recomputed["calibration"] = summaries["calibration"]
    report.recomputed["heldout"] = heldout
    report.recomputed["learning_result"] = learning_result
    report.advisory["package_audit_ci"] = ci
    report.add(
        "uplift_recompute",
        -1.0 <= uplift <= 1.0,
        f"baseline={baseline['rate']:.6f} candidate={candidate['rate']:.6f} uplift={uplift:.6f}",
    )


def finalize_package_status(config: dict, report: Report) -> None:
    actual_isaac = config.get("evidence_kind") == "actual_isaac"
    positive = report.recomputed.get("learning_result") == "positive_uplift"
    if not actual_isaac:
        report.recomputed["package_status"] = "synthetic_verifier_fixture"
        report.recomputed["learning_proven_addendum"] = "absent"
        return
    closed = all(check.passed for check in report.checks)
    report.recomputed["package_status"] = (
        "proof_infrastructure_closed" if closed else "proof_infrastructure_failed"
    )
    report.recomputed["learning_proven_addendum"] = (
        "present" if closed and positive else "absent"
    )


def check_non_claims(pkg_dir: Path, report: Report) -> None:
    path = pkg_dir / "data" / "non_claims_attestation.json"
    if not path.is_file():
        report.add("non_claims", False, "missing non_claims_attestation.json")
        return
    payload = load_json(path)
    problems = [key for key in FORBIDDEN_TRUE_CLAIMS if payload.get(key) is not False]
    report.add(
        "non_claims",
        not problems,
        "all forbidden claims are false" if not problems else f"non-false claims: {problems}",
    )


def check_gate_recompute(pkg_dir: Path, config: dict, report: Report) -> dict:
    runtime = config["runtime_expectations"]
    runtime_gate = load_json(pkg_dir / "data" / "gates" / "runtime_gate.json")
    train_gate = load_json(pkg_dir / "data" / "gates" / "train_generation_runtime_gate.json")
    selection = load_json(pkg_dir / "data" / "gates" / "calibration_selection_report.json")
    train_trace = load_json(pkg_dir / "data" / "gates" / "train_trace_summary.json")
    post_guard = load_json(pkg_dir / "data" / "gates" / "post_heldout_guard.json")
    actual_success_trace_count = train_trace.get("actual_success_trace_count")
    gates = {
        "train_runtime_matches": (
            train_gate.get("passed") is True
            and train_gate.get("runtime_backend") == runtime["backend"]
            and train_gate.get("actual_train_generation_evidence") is True
            and train_gate.get("training_trajectory_source") == runtime["training_source"]
        ),
        "heldout_runtime_matches": (
            runtime_gate.get("passed") is True
            and runtime_gate.get("runtime_backend") == runtime["backend"]
            and runtime_gate.get("proof_runtime") == runtime["proof_runtime"]
        ),
        "calibration_selection_matches": (
            selection.get("calibration_only_selection_passed") is True
            and selection.get("heldout_excluded") is True
            and selection.get("selected_adapter_frozen_before_heldout") is True
            and selection.get("same_adapter_used_for_baseline_and_candidate") is True
        ),
        "actual_train_trace_count_matches": (
            isinstance(actual_success_trace_count, int)
            and not isinstance(actual_success_trace_count, bool)
            and actual_success_trace_count >= 1
        ),
        "post_heldout_guard_matches": post_guard.get("passed") is not False,
    }
    report.recomputed["gates"] = gates
    report.add("gate_recompute", all(gates.values()), str(gates))
    return gates


def check_mvp3a_fixed_contract(pkg_dir: Path, config: dict, report: Report) -> None:
    problems: list[str] = []
    task = load_json(pkg_dir / "data" / "task_variant_attestation.json")
    ranges = config.get("seed_ranges", {})
    runtime = config.get("runtime_expectations", {})
    if task.get("source_variable_opened") is not False:
        problems.append("source_variable_opened must be false")
    if ranges.get("train") != MVP3A_EXPECTED_TRAIN_RANGE:
        problems.append(f"train range must be {MVP3A_EXPECTED_TRAIN_RANGE}")
    if ranges.get("calibration") != MVP3A_EXPECTED_CALIBRATION_RANGE:
        problems.append(
            f"calibration range must be {MVP3A_EXPECTED_CALIBRATION_RANGE}"
        )
    if ranges.get("heldout") != MVP3A_EXPECTED_HELDOUT_RANGE:
        problems.append(f"heldout range must be {MVP3A_EXPECTED_HELDOUT_RANGE}")
    if MVP2_SPENT_RANGE not in ranges.get("spent_no_reuse", []):
        problems.append(f"MVP-2 spent range {MVP2_SPENT_RANGE} must be listed")
    if runtime.get("proof_runtime") != MVP3A_PROOF_RUNTIME:
        problems.append(f"proof_runtime must be {MVP3A_PROOF_RUNTIME}")
    report.add(
        "mvp3a_fixed_contract",
        not problems,
        "fixed MVP-3A ranges/source/runtime contract holds"
        if not problems
        else "; ".join(problems),
    )


def _range_from_config(
    ranges: dict, name: str, report: Report
) -> set[int] | None:
    span = ranges.get(name)
    if span is None:
        report.add("seed_contract", False, f"missing seed_ranges.{name}")
        return None
    try:
        return seeds_in_range(span)
    except Exception as exc:
        report.add("seed_contract", False, f"invalid seed_ranges.{name}: {exc}")
        return None


def check_seed_discipline(config: dict, summaries: dict, report: Report) -> None:
    ranges = config["seed_ranges"]
    train = _range_from_config(ranges, "train", report)
    calibration = _range_from_config(ranges, "calibration", report)
    heldout = _range_from_config(ranges, "heldout", report)
    if train is None or calibration is None or heldout is None:
        return
    report.add("seed_contract", True, "seed range contract is present and valid")
    spent = set()
    for span in ranges.get("spent_no_reuse", []):
        spent |= seeds_in_range(span)
    report.add(
        "seed_disjointness",
        not (heldout & train or heldout & calibration),
        "held-out disjoint from train/calibration",
    )
    report.add(
        "spent_no_reuse",
        not (train & spent or calibration & spent or heldout & spent),
        "no configured spent range reused",
    )
    observed = set(summaries["heldout"]["baseline"]["seeds"]) | set(
        summaries["heldout"]["candidate"]["seeds"]
    )
    report.add(
        "heldout_seed_match",
        observed == heldout,
        f"observed_count={len(observed)} expected_count={len(heldout)}",
    )


def max_consecutive(mask: list[bool]) -> int:
    best = cur = 0
    for value in mask:
        cur = cur + 1 if bool(value) else 0
        best = max(best, cur)
    return best


def _rollout_rows(pkg_dir: Path, split: str, role: str) -> list[dict]:
    return rollout_records(load_json(pkg_dir / ROLLOUT_FILES[split][role]))


def _mask_rows(path: Path) -> list[dict]:
    payload = load_json(path)
    rows = payload.get("masks")
    if not isinstance(rows, list):
        raise ValueError(f"{path.name} missing masks list")
    return rows


def _row_key(row: dict) -> tuple[object, object]:
    return (row.get("seed"), row.get("scenario_id"))


def _check_mask_role(
    *,
    pkg_dir: Path,
    role: str,
    path: Path,
    stable_steps_required: int,
    expected_successes: int,
) -> tuple[int, list[str]]:
    rows = _mask_rows(path)
    masks_by_key = {_row_key(row): row for row in rows}
    rollout_rows = _rollout_rows(pkg_dir, "heldout", role)
    rollout_keys = {_row_key(row) for row in rollout_rows}
    mask_keys = set(masks_by_key)
    problems: list[str] = []
    if rollout_keys != mask_keys:
        problems.append(
            f"{role} mask keys do not match heldout rollouts "
            f"(rollouts={len(rollout_keys)} masks={len(mask_keys)})"
        )
    successes = 0
    checked = 0
    for index, rollout in enumerate(rollout_rows):
        key = _row_key(rollout)
        mask_row = masks_by_key.get(key)
        if mask_row is None:
            problems.append(f"{role}[{index}] missing mask for {key}")
            continue
        mask = mask_row.get("env_native_success_mask")
        if not isinstance(mask, list):
            problems.append(f"{role}[{index}] env_native_success_mask must be list")
            continue
        checked += 1
        derived_consecutive = max_consecutive(mask)
        derived_success = derived_consecutive >= stable_steps_required
        if derived_success:
            successes += 1
        if derived_consecutive != rollout.get("env_native_max_consecutive_success_steps"):
            problems.append(
                f"{role}[{index}] mask consecutive {derived_consecutive} != "
                f"rollout consecutive {rollout.get('env_native_max_consecutive_success_steps')}"
            )
        if derived_success != rollout.get("success"):
            problems.append(
                f"{role}[{index}] mask success {derived_success} != "
                f"rollout success {rollout.get('success')}"
            )
    if successes != expected_successes:
        problems.append(
            f"{role} mask successes {successes} != rollout successes {expected_successes}"
        )
    return checked, problems


def check_c_lite_masks(
    pkg_dir: Path,
    stable_steps_required: int,
    summaries: dict,
    report: Report,
    *,
    require: bool = False,
) -> None:
    mask_paths = {role: pkg_dir / rel for role, rel in MASK_FILES.items()}
    if not any(path.exists() for path in mask_paths.values()) and not require:
        return
    problems: list[str] = []
    checked = 0
    for role, path in mask_paths.items():
        if not path.is_file():
            problems.append(f"missing mask file for {role}")
            continue
        try:
            role_checked, role_problems = _check_mask_role(
                pkg_dir=pkg_dir,
                role=role,
                path=path,
                stable_steps_required=stable_steps_required,
                expected_successes=summaries["heldout"][role]["successes"],
            )
        except Exception as exc:
            problems.append(f"{role} mask parse failed: {exc}")
            continue
        checked += role_checked
        problems.extend(role_problems)
    report.recomputed["c_lite"] = {"checked": checked}
    report.add(
        "c_lite_mask_consistency",
        not problems,
        "; ".join(problems) if problems else f"checked={checked}",
    )


def check_actual_isaac_provenance(
    pkg_dir: Path, config: dict, report: Report
) -> None:
    if config.get("evidence_kind") != "actual_isaac":
        return
    problems: list[str] = []
    policy_hashes: dict[str, str] = {}
    for role, rel in POLICY_FILES.items():
        path = pkg_dir / rel
        if not path.is_file():
            problems.append(f"missing policy artifact for {role}")
            continue
        policy = load_json(path)
        recorded_hash = policy.get("policy_artifact_sha256")
        expected_hash = canonical_payload_sha256(
            policy, omit_key="policy_artifact_sha256"
        )
        if recorded_hash != expected_hash:
            problems.append(f"{role} policy canonical hash mismatch")
            continue
        policy_hashes[role] = recorded_hash

    for role, expected_hash in policy_hashes.items():
        for split in ("calibration", "heldout"):
            rows = _rollout_rows(pkg_dir, split, role)
            for index, row in enumerate(rows):
                if row.get("policy_artifact_sha256") != expected_hash:
                    problems.append(
                        f"{split}/{role}[{index}] policy_artifact_sha256 mismatch"
                    )
                    break

    for role, rel in MASK_FILES.items():
        if not (pkg_dir / rel).is_file():
            problems.append(f"missing C-lite mask file for {role}")

    report.add(
        "actual_isaac_provenance",
        not problems,
        "actual_isaac has policy hash binding and mandatory C-lite masks"
        if not problems
        else "; ".join(problems[:8]),
    )


def check_cached_summaries(pkg_dir: Path, manifest: dict, report: Report) -> None:
    closure = load_json(pkg_dir / "data" / "closure_verdict.json")
    summary = load_json(pkg_dir / "data" / "learning_result_summary.json")
    heldout = report.recomputed["heldout"]
    expected = {
        "package_status": report.recomputed["package_status"],
        "learning_result": report.recomputed["learning_result"],
        "learning_proven_addendum": report.recomputed["learning_proven_addendum"],
        "baseline_heldout_successes": heldout["baseline"]["successes"],
        "candidate_heldout_successes": heldout["candidate"]["successes"],
        "heldout_uplift": heldout["uplift"],
    }
    closure_problems = _compare_expected(closure, expected)
    report.add(
        "closure_summary_consistency",
        not closure_problems,
        "cached closure summary matches recompute"
        if not closure_problems
        else "; ".join(closure_problems),
    )
    summary_expected = {
        "learning_result": expected["learning_result"],
        "learning_proven_addendum": expected["learning_proven_addendum"],
        "baseline_heldout_success_rate": heldout["baseline"]["rate"],
        "candidate_heldout_success_rate": heldout["candidate"]["rate"],
        "heldout_uplift": heldout["uplift"],
    }
    summary_problems = _compare_expected(summary, summary_expected)
    claims = manifest.get("claims", {})
    claim_problems = _compare_expected(
        claims,
        {
            "package_status": report.recomputed["package_status"],
            "learning_result": expected["learning_result"],
            "learning_proven_addendum": expected["learning_proven_addendum"],
        },
    )
    problems = [*summary_problems, *claim_problems]
    report.add(
        "learning_result_consistency",
        not problems,
        "learning summary and manifest claims match recompute"
        if not problems
        else "; ".join(problems),
    )
    package_status_problems = _compare_expected(
        {"package_status": closure.get("package_status")},
        {"package_status": report.recomputed["package_status"]},
    ) + _compare_expected(
        {"package_status": claims.get("package_status")},
        {"package_status": report.recomputed["package_status"]},
    )
    report.add(
        "package_status_consistency",
        not package_status_problems,
        "package status matches evidence kind"
        if not package_status_problems
        else "; ".join(package_status_problems),
    )


def check_learning_addendum_artifact(pkg_dir: Path, report: Report) -> None:
    addendum_dir = pkg_dir / "addenda" / "learning_proven"
    report_path = addendum_dir / "learning_proven_report.json"
    manifest_path = addendum_dir / "package_manifest.json"
    expected_present = report.recomputed.get("learning_proven_addendum") == "present"
    if not expected_present:
        report.add(
            "learning_addendum_artifact",
            not report_path.exists(),
            "learning addendum absent as recomputed"
            if not report_path.exists()
            else "learning addendum report exists when recompute says absent",
        )
        return
    if not report_path.is_file() or not manifest_path.is_file():
        report.add(
            "learning_addendum_artifact",
            False,
            "missing learning_proven addendum report or manifest",
        )
        return
    addendum_report = load_json(report_path)
    addendum_manifest = load_json(manifest_path)
    heldout = report.recomputed["heldout"]
    problems = _compare_expected(
        addendum_report,
        {
            "learning_result": report.recomputed["learning_result"],
            "heldout_uplift": heldout["uplift"],
            "baseline_heldout_success_rate": heldout["baseline"]["rate"],
            "candidate_heldout_success_rate": heldout["candidate"]["rate"],
        },
    )
    entries = addendum_manifest.get("artifact_index", [])
    report_entries = [
        entry for entry in entries if entry.get("data_path") == "learning_proven_report.json"
    ]
    if len(report_entries) != 1:
        problems.append("addendum manifest must hash-lock learning_proven_report.json")
    elif report_entries[0].get("file_sha256") != sha256_file(report_path):
        problems.append("addendum manifest sha256 mismatch")
    report.add(
        "learning_addendum_artifact",
        not problems,
        "learning addendum artifact matches recomputed result"
        if not problems
        else "; ".join(problems),
    )


def _compare_expected(actual: dict, expected: dict) -> list[str]:
    problems: list[str] = []
    for key, value in expected.items():
        actual_value = actual.get(key)
        if isinstance(value, float):
            if abs(float(actual_value) - value) > 1e-9:
                problems.append(f"{key} {actual_value!r} != {value!r}")
        elif actual_value != value:
            problems.append(f"{key} {actual_value!r} != {value!r}")
    return problems


def verify_package(manifest_path: Path | str) -> Report:
    manifest_path = Path(manifest_path)
    pkg_dir = manifest_path.parent
    report = Report()
    try:
        manifest = load_json(manifest_path)
        config = load_json(pkg_dir / "data" / "config.json")
        stable_steps_required = int(config["thresholds"]["stable_steps_required"])
        actual_isaac = config.get("evidence_kind") == "actual_isaac"

        check_hash_integrity(pkg_dir, manifest, report)
        check_manifest_data_coverage(pkg_dir, manifest, report)
        check_mvp3a_fixed_contract(pkg_dir, config, report)
        summaries = recompute_rollout_summaries(pkg_dir, stable_steps_required, report)
        add_learning_recompute(report, config, summaries)
        check_gate_recompute(pkg_dir, config, report)
        check_seed_discipline(config, summaries, report)
        check_actual_isaac_provenance(pkg_dir, config, report)
        check_c_lite_masks(
            pkg_dir,
            stable_steps_required,
            summaries,
            report,
            require=actual_isaac,
        )
        check_non_claims(pkg_dir, report)
        finalize_package_status(config, report)
        check_cached_summaries(pkg_dir, manifest, report)
        check_learning_addendum_artifact(pkg_dir, report)
    except Exception as exc:
        report.add("package_parse", False, f"{type(exc).__name__}: {exc}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    report = verify_package(args.manifest)
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"{status} {check.name}: {check.detail}")
    print("VERDICT: VERIFIED" if report.ok else "VERDICT: FAILED")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
