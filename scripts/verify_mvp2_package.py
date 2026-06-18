#!/usr/bin/env python3
"""Independent verifier for the MVP-2 external proof package (auditability).

Recompute-from-raw, stdlib-only. An external auditor runs:

    python3 scripts/verify_mvp2_package.py \\
        docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json

and independently re-derives the closure verdict (baseline 5/50, candidate 40/50,
uplift 0.70, mvp2_closed) from the small git-tracked JSON bundle — no Isaac, no
trust in the prover. Exit 0 = VERIFIED, non-zero = a hard check failed.

Hash conventions:
  * file_bytes                       -> sha256(file bytes)            (9 artifacts)
  * canonical_payload_excluding_self -> sha256(stable_json minus the  (2 policies)
                                        policy_artifact_sha256 field)

The closure decision is deterministic and does NOT depend on bootstrap CI. The
verifier recomputes a separate, explicitly seeded *package-audit* CI as advisory
evidence only; it does not replace either original CI.

Spec:  docs/superpowers/specs/2026-06-17-mvp2-auditability-verifier-spec.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

FORBIDDEN_CLAIM_KEYS = (
    "real_robot_success",
    "physical_robot_readiness",
    "hmd_openxr_readiness",
    "visual_policy_performance",
    "deployable_real_robot_policy",
    "universal_robot_support",
    "marketplace_readiness",
    "production_certification",
)
LABEL_CONSECUTIVE_THRESHOLD = 10
UPLIFT_THRESHOLD = 0.20
HELDOUT_RANGE = (40000, 40049)
PACKAGE_AUDIT_CI_ITERATIONS = 2000
EXPECTED_AUDIT_CI_SEED = 20260617


# --------------------------------------------------------------------------- #
# Result containers
# --------------------------------------------------------------------------- #
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
    checked_forbidden_claims: set = field(default_factory=set)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(CheckResult(name, passed, detail))

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def failures(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if not c.passed]


# --------------------------------------------------------------------------- #
# Hash helpers (mirror scripts stable_json)
# --------------------------------------------------------------------------- #
def stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_payload_sha256_excluding(payload: dict, *fields: str) -> str:
    stripped = {k: v for k, v in payload.items() if k not in set(fields)}
    return hashlib.sha256(stable_json(stripped).encode("utf-8")).hexdigest()


def _trailing_int(label: str) -> int | None:
    m = re.search(r"(\d+)$", str(label))
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------- #
# Level C: re-derive the consecutive-success run from per-step traces
# --------------------------------------------------------------------------- #
def max_consecutive_from_mask(mask) -> int:
    best = cur = 0
    for value in mask:
        cur = cur + 1 if value else 0
        best = max(best, cur)
    return best


def recompute_trace_consecutive(trace_doc: dict) -> int:
    """Longest run of consecutive env-native success from a trace's per-step mask.

    Prefers env_native_success_mask (the per-step authority field); falls back to
    env_native_success when the mask field is absent.
    """
    steps = trace_doc.get("trace", [])
    mask = []
    for step in steps:
        if "env_native_success_mask" in step:
            mask.append(bool(step["env_native_success_mask"]))
        else:
            mask.append(bool(step.get("env_native_success")))
    return max_consecutive_from_mask(mask)


def verify_level_c(
    rollout_results: list[dict], traces_dir, expected_hashes=None, require_hashlock: bool = False
) -> dict:
    """Match each rollout to its per-step trace and re-derive the consecutive run.

    Missing traces lower coverage but are not contradictions. A present trace is a
    contradiction if (a) hash-lock is required but no manifest hash exists for it,
    (b) its bytes do not match the manifest-recorded per-trace sha256, or (c) the
    re-derived consecutive run disagrees with the recorded value.
    """
    traces_dir = Path(traces_dir)
    expected_hashes = expected_hashes or {}
    checked = consistent = missing = 0
    contradictions: list[dict] = []
    for r in rollout_results:
        name = Path(str(r.get("rollout_log_ref", ""))).name
        tpath = traces_dir / name if name else None
        if not tpath or not tpath.is_file():
            missing += 1
            continue
        checked += 1
        expected_hash = expected_hashes.get(name)
        if expected_hash is None:
            if require_hashlock:
                contradictions.append({"trace": name, "reason": "missing_expected_hash"})
                continue
        else:
            actual_hash = sha256_file(tpath)
            if actual_hash != expected_hash:
                contradictions.append({"trace": name, "reason": "trace_hash_mismatch"})
                continue
        derived = recompute_trace_consecutive(_load_json(tpath))
        recorded = r.get("env_native_max_consecutive_success_steps")
        if derived == recorded:
            consistent += 1
        else:
            contradictions.append(
                {"trace": name, "derived": derived, "recorded": recorded}
            )
    return {
        "expected": len(rollout_results),
        "checked": checked,
        "consistent": consistent,
        "missing": missing,
        "contradictions": contradictions,
    }


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _load_json(path: Path):
    return json.loads(path.read_text())


def _rollout_list(rollouts_doc: dict) -> list[dict]:
    return rollouts_doc["rollout_results"]


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def check_hash_integrity(pkg_dir: Path, manifest: dict, data: dict, report: Report) -> None:
    problems: list[str] = []
    checked = 0
    for entry in manifest.get("artifact_index", []):
        dp = entry.get("data_path")
        if not dp:
            continue  # provenance-only pointer (e.g. root evidence manifest)
        fpath = pkg_dir / dp
        if not fpath.is_file():
            problems.append(f"missing {dp}")
            continue
        conv = entry.get("hash_convention", "file_bytes")
        if conv == "file_bytes":
            actual = sha256_file(fpath)
            if actual != entry.get("file_sha256"):
                problems.append(f"file-bytes mismatch {dp}")
            else:
                checked += 1
        elif conv == "canonical_payload_excluding_self":
            payload = _load_json(fpath)
            actual = canonical_payload_sha256_excluding(payload, "policy_artifact_sha256")
            if actual != entry.get("canonical_payload_sha256"):
                problems.append(f"canonical mismatch {dp}")
            elif actual != payload.get("policy_artifact_sha256"):
                problems.append(f"policy self-hash mismatch {dp}")
            else:
                checked += 1
        else:
            problems.append(f"unknown hash_convention {conv} for {dp}")

    # rollout <-> policy binding: the policy that produced each rollout set.
    for role in ("baseline", "candidate"):
        pol = data[f"{role}_policy"]
        roll = data[f"{role}_rollouts"]
        recomputed = canonical_payload_sha256_excluding(pol, "policy_artifact_sha256")
        if recomputed != roll.get("policy_artifact_sha256"):
            problems.append(f"{role} rollouts not bound to {role} policy")
        else:
            checked += 1

    report.add(
        "hash_integrity",
        not problems,
        f"{checked} hashes/bindings verified" if not problems else "; ".join(problems),
    )


def check_rate_recompute(data: dict, gate: dict, report: Report) -> None:
    rec = {}
    for role in ("baseline", "candidate"):
        rolls = _rollout_list(data[f"{role}_rollouts"])
        successes = sum(1 for r in rolls if r.get("success"))
        total = len(rolls)
        rate = successes / total if total else 0.0
        rec[role] = {"successes": successes, "rollouts": total, "rate": rate}
    rec["uplift"] = rec["candidate"]["rate"] - rec["baseline"]["rate"]
    report.recomputed = rec

    gate_b = gate.get("baseline_success_rate")
    gate_c = gate.get("candidate_success_rate")
    ok = (
        rec["baseline"]["successes"] == 5
        and rec["baseline"]["rollouts"] == 50
        and rec["candidate"]["successes"] == 40
        and rec["candidate"]["rollouts"] == 50
        and abs(rec["baseline"]["rate"] - gate_b) < 1e-9
        and abs(rec["candidate"]["rate"] - gate_c) < 1e-9
    )
    report.add(
        "rate_recompute",
        ok,
        f"baseline {rec['baseline']['successes']}/{rec['baseline']['rollouts']}, "
        f"candidate {rec['candidate']['successes']}/{rec['candidate']['rollouts']} "
        f"(gate {gate_b}/{gate_c})",
    )


def check_uplift_recompute(data: dict, gate: dict, report: Report) -> None:
    uplift = report.recomputed["uplift"]
    gate_uplift = gate.get("curated_vs_uncurated_uplift")
    ok = abs(uplift - gate_uplift) < 1e-9
    report.add("uplift_recompute", ok, f"recomputed {uplift:.4f} vs gate {gate_uplift}")


def check_uplift_threshold(report: Report) -> None:
    uplift = report.recomputed["uplift"]
    ok = uplift >= UPLIFT_THRESHOLD
    report.add("uplift_threshold", ok, f"uplift {uplift:.2f} >= {UPLIFT_THRESHOLD}")


def check_label_recompute(data: dict, report: Report) -> None:
    """Level B: success == (env_native_success_available AND consec >= 10)."""
    bad: list[str] = []
    n = 0
    for role in ("baseline", "candidate"):
        for r in _rollout_list(data[f"{role}_rollouts"]):
            n += 1
            available = bool(r.get("env_native_success_available"))
            consec = r.get("env_native_max_consecutive_success_steps", 0)
            derived = available and consec >= LABEL_CONSECUTIVE_THRESHOLD
            if derived != bool(r.get("success")):
                bad.append(f"{r.get('rollout_id')}")
    report.add(
        "label_recompute",
        not bad,
        f"{n} labels re-derived from consecutive>={LABEL_CONSECUTIVE_THRESHOLD}"
        if not bad
        else f"mismatched labels: {bad[:5]}",
    )


def check_closure_verdict(gate: dict, report: Report) -> None:
    ok = (
        gate.get("mvp2_closed") is True
        and gate.get("policy_uplift_proven") is True
        and gate.get("actual_rollouts_per_policy") == 50
    )
    report.add(
        "closure_verdict",
        ok,
        f"mvp2_closed={gate.get('mvp2_closed')}, "
        f"policy_uplift_proven={gate.get('policy_uplift_proven')}, "
        f"rollouts_per_policy={gate.get('actual_rollouts_per_policy')}",
    )


def check_seed_disjointness(data: dict, gate: dict, report: Report) -> None:
    """Pre-closure: held-out disjoint from every leakage-guard channel."""
    burned: set[int] = set()
    channels = gate.get("heldout_leakage_guard", {}).get("checked_channels", {})
    for labels in channels.values():
        for lab in labels:
            v = _trailing_int(lab)
            if v is not None:
                burned.add(v)
    # fresh calibration presignal range (flagged on the gate).
    if gate.get("fresh_calibration_39000_39029_accessed"):
        burned |= set(range(39000, 39030))

    # Both policies roll out the same 50 held-out seeds, so uniqueness is a
    # per-policy property (50 unique each), not a property of the combined set.
    per_policy_unique = True
    held_all: list[int] = []
    for role in ("baseline", "candidate"):
        ids = [
            _trailing_int(r.get("scenario_id"))
            for r in _rollout_list(data[f"{role}_rollouts"])
        ]
        ids = [v for v in ids if v is not None]
        if len(ids) != len(set(ids)) or len(ids) != 50:
            per_policy_unique = False
        held_all.extend(ids)
    held_set = set(held_all)
    lo, hi = HELDOUT_RANGE
    in_range = all(lo <= v <= hi for v in held_set)
    overlap = held_set & burned
    ok = not overlap and in_range and per_policy_unique and len(held_set) == 50
    report.add(
        "seed_disjointness",
        ok,
        f"held-out n={len(held_set)} range[{min(held_set)}-{max(held_set)}], "
        f"burned n={len(burned)}, overlap={sorted(overlap) or 'none'}, "
        f"per_policy_unique={per_policy_unique}",
    )


def check_spent_no_reuse(manifest: dict, gate: dict, report: Report) -> None:
    spent = manifest.get("spent_heldout_ranges", [])
    target = next((s for s in spent if s.get("range") == "40000-40049"), None)
    ok = (
        target is not None
        and target.get("future_closure_reuse_allowed") is False
        and target.get("same_heldout_reuse_allowed_for_closure") is False
        and gate.get("same_heldout_reuse_allowed_for_closure") is False
    )
    report.add(
        "spent_no_reuse",
        ok,
        "40000-40049 spent/audit-only/no-reuse"
        if ok
        else f"spent record invalid: {target}",
    )


def check_forbidden_claims(manifest: dict, gate: dict, report: Report) -> None:
    """Manifest is the authority for all 8 non-claims (present + False). The
    hash-locked gate carries a subset; whatever it records must not contradict."""
    problems: list[str] = []
    man_nc = manifest.get("non_claims", {})
    for key in FORBIDDEN_CLAIM_KEYS:
        if key not in man_nc:
            problems.append(f"manifest.{key} absent")
        elif man_nc[key] is not False:
            problems.append(f"manifest.{key}={man_nc[key]}")
    # gate non_claims: hash-locked subset must agree (no key flipped true).
    gate_nc = gate.get("non_claims", {})
    for key in FORBIDDEN_CLAIM_KEYS:
        if key in gate_nc and gate_nc[key] is not False:
            problems.append(f"gate.{key}={gate_nc[key]}")
    report.checked_forbidden_claims = set(FORBIDDEN_CLAIM_KEYS)
    gate_covered = sorted(set(FORBIDDEN_CLAIM_KEYS) & set(gate_nc))
    report.add(
        "forbidden_claims",
        not problems,
        f"8 non-claims false in manifest; gate hash-locks {len(gate_covered)}/8"
        if not problems
        else "; ".join(problems),
    )


def check_non_claims_attestation(pkg_dir: Path, gate: dict, report: Report) -> None:
    """All 8 non-claims must be asserted in a hash-locked artifact (not only the
    unprotected manifest), bound to the specific closure gate. The closure gate is
    frozen and records only 6; this attestation makes all 8 hash-locked."""
    att_path = pkg_dir / "data" / "non_claims_attestation.json"
    problems: list[str] = []
    if not att_path.is_file():
        report.add("non_claims_attestation", False, "attestation file missing")
        return
    att = _load_json(att_path)
    nc = att.get("non_claims", {})
    for key in FORBIDDEN_CLAIM_KEYS:
        if nc.get(key) is not False:
            problems.append(f"attestation.{key}={nc.get(key)}")
    gate_sha = sha256_file(pkg_dir / "data" / "heldout_closure_gate_v0_14.json")
    if att.get("binds_to_closure_gate_sha256") != gate_sha:
        problems.append("binds_to_closure_gate_sha256 != closure gate file hash")
    # consistency: gate's recorded subset must agree.
    gate_nc = gate.get("non_claims", {})
    for key in FORBIDDEN_CLAIM_KEYS:
        if key in gate_nc and gate_nc[key] is not False:
            problems.append(f"gate.{key}={gate_nc[key]}")
    report.add(
        "non_claims_attestation",
        not problems,
        "8 non-claims hash-locked and bound to the closure gate"
        if not problems
        else "; ".join(problems),
    )


def check_manifest_claim_consistency(manifest: dict, gate: dict, report: Report) -> None:
    """The human-read manifest claim block must agree with recomputed evidence and
    the gate — an external reviewer reads this block, so it cannot drift."""
    problems: list[str] = []
    claim = manifest.get("claim", {})
    hc = claim.get("heldout_closure", {})
    rec = report.recomputed
    expectations = {
        "baseline_successes": rec["baseline"]["successes"],
        "baseline_rollouts": rec["baseline"]["rollouts"],
        "candidate_successes": rec["candidate"]["successes"],
        "candidate_rollouts": rec["candidate"]["rollouts"],
    }
    for key, want in expectations.items():
        if hc.get(key) != want:
            problems.append(f"claim.{key}={hc.get(key)} != {want}")
    float_expectations = {
        "baseline_success_rate": rec["baseline"]["rate"],
        "candidate_success_rate": rec["candidate"]["rate"],
        "absolute_uplift": rec["uplift"],
    }
    for key, want in float_expectations.items():
        got = hc.get(key)
        if got is None or abs(got - want) >= 1e-9:
            problems.append(f"claim.{key}={got} != {want:.4f}")
    if claim.get("mvp2_closed") is not True:
        problems.append(f"claim.mvp2_closed={claim.get('mvp2_closed')}")
    if claim.get("policy_uplift_proven") is not True:
        problems.append(f"claim.policy_uplift_proven={claim.get('policy_uplift_proven')}")
    if claim.get("mvp2_closed") != gate.get("mvp2_closed"):
        problems.append("claim.mvp2_closed disagrees with gate")
    report.add(
        "manifest_claim_consistency",
        not problems,
        "manifest claim agrees with recomputed evidence and gate"
        if not problems
        else "; ".join(problems),
    )


def check_level_c_hashlock(manifest: dict, rollout_results: list[dict], report: Report) -> None:
    """The manifest's per-trace hash-lock must be complete, or --deep gives a false
    sense of provenance. Empty/partial maps and count drift are hard failures."""
    ltc = manifest.get("level_c_traces", {})
    per = ltc.get("per_trace_sha256", {})
    expected_count = ltc.get("trace_count_expected")
    expected_names = {Path(str(r.get("rollout_log_ref", ""))).name for r in rollout_results}
    problems: list[str] = []
    if not per:
        problems.append("per_trace_sha256 is empty")
    if expected_count != len(expected_names):
        problems.append(f"trace_count_expected={expected_count} != {len(expected_names)} rollouts")
    if len(per) != expected_count:
        problems.append(f"per_trace_sha256 has {len(per)} entries != trace_count_expected")
    missing = expected_names - set(per)
    extra = set(per) - expected_names
    if missing:
        problems.append(f"{len(missing)} rollout traces lack a manifest hash")
    if extra:
        problems.append(f"{len(extra)} manifest hashes have no matching rollout")
    report.add(
        "level_c_hashlock",
        not problems,
        f"hash-lock complete: {len(per)} traces"
        if not problems
        else "; ".join(problems),
    )


def check_audit_ci_seed_pinned(manifest: dict, report: Report) -> None:
    seed = manifest.get("package_audit_ci_seed")
    ok = seed == EXPECTED_AUDIT_CI_SEED
    report.add(
        "audit_ci_seed_pinned",
        ok,
        f"package_audit_ci_seed={seed} (expected {EXPECTED_AUDIT_CI_SEED})",
    )


# --------------------------------------------------------------------------- #
# Advisory: package-audit CI (deterministic, advisory only)
# --------------------------------------------------------------------------- #
def compute_package_audit_ci(data: dict, seed: int) -> dict:
    base = [1 if r.get("success") else 0 for r in _rollout_list(data["baseline_rollouts"])]
    cand = [1 if r.get("success") else 0 for r in _rollout_list(data["candidate_rollouts"])]
    rng = random.Random(seed)
    n_iter = PACKAGE_AUDIT_CI_ITERATIONS
    stats = []
    for _ in range(n_iter):
        b = [base[rng.randrange(len(base))] for _ in range(len(base))]
        c = [cand[rng.randrange(len(cand))] for _ in range(len(cand))]
        stats.append(sum(c) / len(c) - sum(b) / len(b))
    stats.sort()

    def q(p: float) -> float:
        return stats[math.floor(p * (n_iter - 1))]

    return {
        "method": "deterministic_bootstrap_success_rate_difference",
        "seed": seed,
        "iterations": n_iter,
        "lower": q(0.025),
        "upper": q(0.975),
        "quantile_convention": "sorted[floor(p*(n-1))]",
        "advisory_only": True,
        "note": "Separate package-audit CI; not a replacement for either original CI.",
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def verify_package(manifest_path, deep: bool = False, traces_dir=None) -> Report:
    manifest_path = Path(manifest_path)
    pkg_dir = manifest_path.parent
    manifest = _load_json(manifest_path)

    data = {
        "baseline_rollouts": _load_json(pkg_dir / "data" / "baseline_external_rollouts.json"),
        "candidate_rollouts": _load_json(pkg_dir / "data" / "candidate_external_rollouts.json"),
        "baseline_policy": _load_json(pkg_dir / "data" / "baseline_policy_artifact_v0_14.json"),
        "candidate_policy": _load_json(pkg_dir / "data" / "candidate_policy_artifact_v0_14.json"),
    }
    gate = _load_json(pkg_dir / "data" / "heldout_closure_gate_v0_14.json")

    report = Report()
    check_hash_integrity(pkg_dir, manifest, data, report)
    check_rate_recompute(data, gate, report)
    check_uplift_recompute(data, gate, report)
    check_uplift_threshold(report)
    check_label_recompute(data, report)
    check_closure_verdict(gate, report)
    check_seed_disjointness(data, gate, report)
    check_spent_no_reuse(manifest, gate, report)
    check_forbidden_claims(manifest, gate, report)
    check_non_claims_attestation(pkg_dir, gate, report)
    check_manifest_claim_consistency(manifest, gate, report)
    check_audit_ci_seed_pinned(manifest, report)

    seed = int(manifest.get("package_audit_ci_seed", EXPECTED_AUDIT_CI_SEED))
    report.advisory["package_audit_ci"] = compute_package_audit_ci(data, seed)

    if deep:
        rollout_results = _rollout_list(data["baseline_rollouts"]) + _rollout_list(
            data["candidate_rollouts"]
        )
        traces = traces_dir if traces_dir is not None else (pkg_dir / "data" / "traces")
        expected_hashes = manifest.get("level_c_traces", {}).get("per_trace_sha256", {})
        check_level_c_hashlock(manifest, rollout_results, report)
        cov = verify_level_c(
            rollout_results, traces, expected_hashes=expected_hashes, require_hashlock=True
        )
        report.advisory["level_c_coverage"] = cov
        # Only a present-and-contradicting trace fails; missing traces just lower
        # coverage (Level C evidence is out-of-band / optional).
        report.add(
            "level_c_trace_consistency",
            not cov["contradictions"],
            f"{cov['consistent']}/{cov['checked']} present traces consistent, "
            f"{cov['missing']} missing (expected {cov['expected']})"
            if not cov["contradictions"]
            else f"contradictions: {cov['contradictions'][:5]}",
        )

    return report


def _format_report(report: Report) -> str:
    lines = ["MVP-2 package verification", "=" * 60]
    for c in report.checks:
        lines.append(f"  [{'PASS' if c.passed else 'FAIL'}] {c.name}: {c.detail}")
    rec = report.recomputed
    if rec:
        lines.append("-" * 60)
        lines.append(
            f"  recomputed: baseline {rec['baseline']['successes']}/{rec['baseline']['rollouts']}"
            f"={rec['baseline']['rate']:.2f}, candidate "
            f"{rec['candidate']['successes']}/{rec['candidate']['rollouts']}"
            f"={rec['candidate']['rate']:.2f}, uplift {rec['uplift']:.2f}"
        )
    ci = report.advisory.get("package_audit_ci")
    if ci:
        lines.append(
            f"  advisory package-audit CI (seed {ci['seed']}, {ci['iterations']} iters): "
            f"[{ci['lower']:.2f}, {ci['upper']:.2f}] — advisory only, not a hard gate"
        )
    lines.append("=" * 60)
    lines.append("VERDICT: " + ("VERIFIED" if report.ok else "FAILED"))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify the MVP-2 external proof package.")
    parser.add_argument("manifest", help="path to package_manifest.json")
    parser.add_argument("--deep", action="store_true", help="Level C: re-derive from per-step traces")
    parser.add_argument("--traces-dir", default=None, help="directory of Isaac per-step traces")
    args = parser.parse_args(argv)

    report = verify_package(args.manifest, deep=args.deep, traces_dir=args.traces_dir)
    print(_format_report(report))
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
