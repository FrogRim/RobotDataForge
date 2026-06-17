"""Tests for the MVP-2 external proof package verifier (auditability slice).

Spec:  docs/superpowers/specs/2026-06-17-mvp2-auditability-verifier-spec.md
Tasks: docs/superpowers/plans/2026-06-17-mvp2-auditability-verifier-tasks.md

These tests pin the *self-contained, recompute-from-raw* contract:
the verdict (baseline 5/50, candidate 40/50, uplift 0.70, mvp2_closed) must be
independently recomputable from a small git-tracked JSON bundle, with no Isaac
and without trusting the prover.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REAL_TRACES = (
    ROOT
    / "storage/proof_evidence/mvp2c_isaac_training_calibration"
    / "v0_14_comparator_provenance_row_balance"
    / "isaac_runtime_fresh_heldout_v0_14/isaac_runtime_heldout_rollout_traces"
)


def _load_verifier():
    name = "verify_mvp2_package"
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
PACKAGE = ROOT / "docs" / "proof" / "mvp2_learning_proven_evidence_package"
DATA = PACKAGE / "data"
MANIFEST = PACKAGE / "package_manifest.json"

# data/ = 11 files (spec C1a source map).
EXPECTED_FILE_BYTES = (
    "baseline_external_rollouts.json",
    "candidate_external_rollouts.json",
    "heldout_closure_gate_v0_14.json",
    "calibration_presignal_gate_v0_14.json",
    "v0_14_comparator_provenance_row_balance_gate.json",
    "v0_14_comparator_provenance_row_balance_manifest.json",
    "v0_14_row_balance_report.json",
    "v0_14_source_provenance_report.json",
    "mvp2_learning_proven_report.json",
)
EXPECTED_CANONICAL = {
    "baseline_policy_artifact_v0_14.json": "baseline",
    "candidate_policy_artifact_v0_14.json": "candidate",
}


def _stable_json(payload) -> str:
    # Mirror scripts stable_json: ensure_ascii=False, sort_keys=True, indent=2.
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_payload_sha256_excluding(payload: dict, *fields: str) -> str:
    stripped = {k: v for k, v in payload.items() if k not in set(fields)}
    return hashlib.sha256(_stable_json(stripped).encode("utf-8")).hexdigest()


def _manifest_entry_by_data_filename(manifest: dict, filename: str) -> dict | None:
    for entry in manifest.get("artifact_index", []):
        dp = entry.get("data_path") or ""
        if dp.endswith(filename):
            return entry
    return None


class TestBundleIntegrity:
    """C1b contract — RED until T3 copies data/ and amends the manifest."""

    def test_all_eleven_data_files_present(self):
        missing = [
            name
            for name in (*EXPECTED_FILE_BYTES, *EXPECTED_CANONICAL)
            if not (DATA / name).is_file()
        ]
        assert missing == [], f"data/ bundle incomplete, missing: {missing}"
        present = sorted(p.name for p in DATA.glob("*.json"))
        assert len(present) == 11, f"data/ must hold exactly 11 JSON files, got {present}"

    def test_file_bytes_hashes_match_manifest(self):
        manifest = json.loads(MANIFEST.read_text())
        for name in EXPECTED_FILE_BYTES:
            entry = _manifest_entry_by_data_filename(manifest, name)
            assert entry is not None, f"manifest missing data_path entry for {name}"
            actual = _sha256_file(DATA / name)
            assert actual == entry["file_sha256"], f"file-bytes sha256 mismatch for {name}"

    def test_policy_canonical_hashes_bind_to_rollouts(self):
        """Policy artifacts use canonical-payload hash (excl self field), and that
        hash must equal the rollout-declared policy_artifact_sha256 — the binding
        that ties each rollout set to the exact policy that produced it."""
        manifest = json.loads(MANIFEST.read_text())
        for name, role in EXPECTED_CANONICAL.items():
            policy = json.loads((DATA / name).read_text())
            recomputed = _canonical_payload_sha256_excluding(policy, "policy_artifact_sha256")
            # self-consistency
            assert recomputed == policy["policy_artifact_sha256"], f"{name} self-hash mismatch"
            # binding to rollouts
            rollouts = json.loads((DATA / f"{role}_external_rollouts.json").read_text())
            assert recomputed == rollouts["policy_artifact_sha256"], (
                f"{name} not bound to {role} rollouts"
            )
            # manifest records the canonical hash with explicit convention
            entry = _manifest_entry_by_data_filename(manifest, name)
            assert entry is not None, f"manifest missing data_path entry for {name}"
            assert entry.get("hash_convention") == "canonical_payload_excluding_self"
            assert entry.get("canonical_payload_sha256") == recomputed


# Expected hard-check names (spec hard-fail criteria).
HARD_CHECKS = (
    "hash_integrity",
    "rate_recompute",
    "uplift_recompute",
    "uplift_threshold",
    "label_recompute",
    "closure_verdict",
    "seed_disjointness",
    "spent_no_reuse",
    "forbidden_claims",
    "manifest_claim_consistency",
    "audit_ci_seed_pinned",
)
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


def _checks_by_name(report) -> dict:
    return {c.name: c for c in report.checks}


class TestVerifierHardChecks:
    """C2 verifier core — RED until scripts/verify_mvp2_package.py exists."""

    def test_green_case_verifies(self):
        v = _load_verifier()
        report = v.verify_package(MANIFEST)
        assert report.ok is True, f"expected VERIFIED, got failures: {report.failures()}"
        assert report.exit_code == 0

    def test_all_eleven_hard_checks_present_and_pass(self):
        v = _load_verifier()
        report = v.verify_package(MANIFEST)
        by = _checks_by_name(report)
        for name in HARD_CHECKS:
            assert name in by, f"hard-check missing: {name}"
            assert by[name].passed is True, f"hard-check failed: {name} — {by[name].detail}"

    def test_rate_and_uplift_recomputed_from_raw(self):
        v = _load_verifier()
        report = v.verify_package(MANIFEST)
        r = report.recomputed
        assert r["baseline"]["successes"] == 5 and r["baseline"]["rollouts"] == 50
        assert r["candidate"]["successes"] == 40 and r["candidate"]["rollouts"] == 50
        assert abs(r["baseline"]["rate"] - 0.10) < 1e-9
        assert abs(r["candidate"]["rate"] - 0.80) < 1e-9
        assert abs(r["uplift"] - 0.70) < 1e-9

    def test_label_recompute_uses_consecutive_threshold(self):
        """Level B: each rollout success must equal (available AND consec >= 10)."""
        v = _load_verifier()
        report = v.verify_package(MANIFEST)
        by = _checks_by_name(report)
        assert by["label_recompute"].passed is True

    def test_forbidden_claims_all_false(self):
        v = _load_verifier()
        report = v.verify_package(MANIFEST)
        by = _checks_by_name(report)
        assert by["forbidden_claims"].passed is True
        # all 8 keys must have been checked
        for key in FORBIDDEN_CLAIM_KEYS:
            assert key in by["forbidden_claims"].detail or report.checked_forbidden_claims == set(
                FORBIDDEN_CLAIM_KEYS
            )

    def test_advisory_audit_ci_is_seeded_and_separate(self):
        v = _load_verifier()
        report = v.verify_package(MANIFEST)
        ci = report.advisory["package_audit_ci"]
        assert ci["seed"] == 20260617
        assert ci["iterations"] == 2000
        assert 0.0 <= ci["lower"] <= ci["upper"] <= 1.0
        # advisory only — not a hard gate
        assert "package_audit_ci" not in {c.name for c in report.checks}


def _write_trace(path: Path, mask: list[bool]) -> None:
    doc = {"trace": [{"step": i, "env_native_success_mask": bool(m),
                      "env_native_success": bool(m)} for i, m in enumerate(mask)]}
    path.write_text(json.dumps(doc))


class TestLevelC:
    """C3 Level C (--deep): re-derive consecutive run from per-step masks. RED
    until verify_mvp2_package grows the Level C surface."""

    def test_max_consecutive_from_mask(self):
        v = _load_verifier()
        assert v.max_consecutive_from_mask([False, True, True, True, False, True]) == 3
        assert v.max_consecutive_from_mask([False] * 5) == 0
        assert v.max_consecutive_from_mask([True] * 10) == 10

    def test_recompute_trace_consecutive(self):
        v = _load_verifier()
        doc = {"trace": [{"env_native_success_mask": m} for m in [0, 1, 1, 0, 1, 1, 1]]}
        assert v.recompute_trace_consecutive(doc) == 3

    def test_verify_level_c_consistent(self, tmp_path):
        v = _load_verifier()
        _write_trace(tmp_path / "r0_trace.json", [False, True, True, True])  # run 3
        _write_trace(tmp_path / "r1_trace.json", [True] * 10)  # run 10
        rollouts = [
            {"rollout_log_ref": "x/r0_trace.json", "env_native_max_consecutive_success_steps": 3},
            {"rollout_log_ref": "x/r1_trace.json", "env_native_max_consecutive_success_steps": 10},
        ]
        cov = v.verify_level_c(rollouts, tmp_path)
        assert cov["checked"] == 2 and cov["consistent"] == 2
        assert cov["contradictions"] == []

    def test_verify_level_c_contradiction(self, tmp_path):
        v = _load_verifier()
        _write_trace(tmp_path / "bad_trace.json", [True, True])  # run 2
        rollouts = [
            {"rollout_log_ref": "x/bad_trace.json", "env_native_max_consecutive_success_steps": 10},
        ]
        cov = v.verify_level_c(rollouts, tmp_path)
        assert cov["contradictions"], "contradiction must be reported"

    def test_verify_level_c_missing_keeps_coverage_zero(self, tmp_path):
        v = _load_verifier()
        rollouts = [
            {"rollout_log_ref": "x/absent_trace.json", "env_native_max_consecutive_success_steps": 0},
        ]
        cov = v.verify_level_c(rollouts, tmp_path)
        assert cov["checked"] == 0 and cov["missing"] == 1
        assert cov["contradictions"] == []

    def test_verify_level_c_hash_lock_mismatch_is_contradiction(self, tmp_path):
        """A present trace whose bytes do not match the manifest per-trace sha256
        must be a contradiction (Level C hash-lock, not just consecutive match)."""
        v = _load_verifier()
        _write_trace(tmp_path / "r0_trace.json", [True] * 10)  # run 10, consistent label
        rollouts = [
            {"rollout_log_ref": "x/r0_trace.json", "env_native_max_consecutive_success_steps": 10},
        ]
        wrong_hash = {"r0_trace.json": "0" * 64}
        cov = v.verify_level_c(rollouts, tmp_path, expected_hashes=wrong_hash)
        assert cov["contradictions"], "trace-bytes vs manifest hash mismatch must fail"

    def test_verify_level_c_require_hashlock_missing_is_contradiction(self, tmp_path):
        """Under hash-lock, a present trace with no manifest hash is a contradiction."""
        v = _load_verifier()
        _write_trace(tmp_path / "r0_trace.json", [True] * 10)
        rollouts = [
            {"rollout_log_ref": "x/r0_trace.json", "env_native_max_consecutive_success_steps": 10},
        ]
        cov = v.verify_level_c(rollouts, tmp_path, expected_hashes={}, require_hashlock=True)
        assert cov["contradictions"], "missing expected hash under hash-lock must fail"

    def _copy_pkg_with_traces(self, tmp_path):
        import shutil as _sh

        dst = tmp_path / "pkg"
        _sh.copytree(PACKAGE, dst)
        return dst / "package_manifest.json"

    def test_deep_trace_hash_tamper_fails(self, tmp_path):
        if not REAL_TRACES.is_dir():
            pytest.skip("Level C traces are out-of-band; not present in this checkout")
        v = _load_verifier()
        manifest_path = self._copy_pkg_with_traces(tmp_path)
        manifest = json.loads(manifest_path.read_text())
        name = next(iter(manifest["level_c_traces"]["per_trace_sha256"]))
        manifest["level_c_traces"]["per_trace_sha256"][name] = "0" * 64
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest_path, deep=True, traces_dir=REAL_TRACES)
        assert report.ok is False

    def test_deep_empty_hash_map_fails(self, tmp_path):
        if not REAL_TRACES.is_dir():
            pytest.skip("Level C traces are out-of-band; not present in this checkout")
        v = _load_verifier()
        manifest_path = self._copy_pkg_with_traces(tmp_path)
        manifest = json.loads(manifest_path.read_text())
        manifest["level_c_traces"]["per_trace_sha256"] = {}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest_path, deep=True, traces_dir=REAL_TRACES)
        assert report.ok is False, "an emptied trace-hash map must not pass --deep"

    def test_deep_partial_hash_map_fails(self, tmp_path):
        if not REAL_TRACES.is_dir():
            pytest.skip("Level C traces are out-of-band; not present in this checkout")
        v = _load_verifier()
        manifest_path = self._copy_pkg_with_traces(tmp_path)
        manifest = json.loads(manifest_path.read_text())
        name = next(iter(manifest["level_c_traces"]["per_trace_sha256"]))
        del manifest["level_c_traces"]["per_trace_sha256"][name]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest_path, deep=True, traces_dir=REAL_TRACES)
        assert report.ok is False

    def test_deep_count_mismatch_fails(self, tmp_path):
        if not REAL_TRACES.is_dir():
            pytest.skip("Level C traces are out-of-band; not present in this checkout")
        v = _load_verifier()
        manifest_path = self._copy_pkg_with_traces(tmp_path)
        manifest = json.loads(manifest_path.read_text())
        manifest["level_c_traces"]["trace_count_expected"] = 99
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest_path, deep=True, traces_dir=REAL_TRACES)
        assert report.ok is False

    def test_deep_real_traces_or_skip(self):
        if not REAL_TRACES.is_dir():
            pytest.skip("Level C traces are out-of-band; not present in this checkout")
        v = _load_verifier()
        report = v.verify_package(MANIFEST, deep=True, traces_dir=REAL_TRACES)
        by = {c.name: c for c in report.checks}
        assert "level_c_trace_consistency" in by
        assert by["level_c_trace_consistency"].passed is True
        cov = report.advisory["level_c_coverage"]
        assert cov["checked"] == 100 and cov["consistent"] == 100

    def test_deep_missing_traces_still_level_b_verified(self, tmp_path):
        v = _load_verifier()
        report = v.verify_package(MANIFEST, deep=True, traces_dir=tmp_path)
        # No traces present -> Level B verdict unaffected, coverage zero.
        assert report.ok is True
        assert report.advisory["level_c_coverage"]["checked"] == 0


# --------------------------------------------------------------------------- #
# Tamper matrix — the verifier must be able to FAIL (not a rubber stamp).
# --------------------------------------------------------------------------- #
import ast  # noqa: E402
import shutil  # noqa: E402


def _copy_package(tmp_path: Path) -> Path:
    dst = tmp_path / "pkg"
    shutil.copytree(PACKAGE, dst)
    return dst / "package_manifest.json"


def _rehash_file_bytes(manifest_path: Path, filename: str) -> None:
    """Recompute and store the file-bytes sha256 for a data/ file so hash_integrity
    passes — used to isolate a *non-hash* tamper from the hash check."""
    manifest = json.loads(manifest_path.read_text())
    digest = _sha256_file(manifest_path.parent / "data" / filename)
    for entry in manifest["artifact_index"]:
        if (entry.get("data_path") or "").endswith(filename):
            entry["file_sha256"] = digest
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def _checks(report) -> dict:
    return {c.name: c for c in report.checks}


class TestTamperMatrix:
    def test_flip_candidate_success_fails(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        f = manifest.parent / "data" / "candidate_external_rollouts.json"
        doc = json.loads(f.read_text())
        for r in doc["rollout_results"]:
            if r["success"]:
                r["success"] = False
                break
        f.write_text(json.dumps(doc))
        report = v.verify_package(manifest)
        assert report.ok is False

    def test_corrupt_data_byte_fails_hash(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        f = manifest.parent / "data" / "v0_14_row_balance_report.json"
        f.write_bytes(f.read_bytes() + b" ")
        report = v.verify_package(manifest)
        assert _checks(report)["hash_integrity"].passed is False

    def test_consecutive_below_threshold_fails_label(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        f = manifest.parent / "data" / "baseline_external_rollouts.json"
        doc = json.loads(f.read_text())
        for r in doc["rollout_results"]:
            if r["success"]:  # keep success=True but drop consecutive below 10
                r["env_native_max_consecutive_success_steps"] = 9
                break
        f.write_text(json.dumps(doc))
        _rehash_file_bytes(manifest, "baseline_external_rollouts.json")
        report = v.verify_package(manifest)
        assert _checks(report)["label_recompute"].passed is False

    def test_heldout_injected_into_calibration_fails_disjointness(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        f = manifest.parent / "data" / "heldout_closure_gate_v0_14.json"
        gate = json.loads(f.read_text())
        gate["heldout_leakage_guard"]["checked_channels"]["calibration_selector"].append(
            "calibration_40005"
        )
        f.write_text(json.dumps(gate))
        _rehash_file_bytes(manifest, "heldout_closure_gate_v0_14.json")
        report = v.verify_package(manifest)
        assert _checks(report)["seed_disjointness"].passed is False

    def test_non_claim_flipped_true_fails(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        doc = json.loads(manifest.read_text())
        doc["non_claims"]["real_robot_success"] = True
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest)
        assert _checks(report)["forbidden_claims"].passed is False

    def test_uplift_below_threshold_fails(self):
        v = _load_verifier()
        report = v.Report()
        report.recomputed = {"uplift": 0.19}
        v.check_uplift_threshold(report)
        assert _checks(report)["uplift_threshold"].passed is False

    def test_rollout_policy_binding_tamper_fails(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        f = manifest.parent / "data" / "baseline_external_rollouts.json"
        doc = json.loads(f.read_text())
        h = doc["policy_artifact_sha256"]
        doc["policy_artifact_sha256"] = ("0" if h[0] != "0" else "1") + h[1:]
        f.write_text(json.dumps(doc))
        _rehash_file_bytes(manifest, "baseline_external_rollouts.json")
        report = v.verify_package(manifest)
        assert _checks(report)["hash_integrity"].passed is False

    def test_manifest_claim_tamper_fails(self, tmp_path):
        """The human-read manifest claim block must agree with recomputed evidence."""
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        doc = json.loads(manifest.read_text())
        doc["claim"]["heldout_closure"]["candidate_successes"] = 999
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest)
        assert _checks(report)["manifest_claim_consistency"].passed is False

    def test_manifest_claim_mvp2_closed_flip_fails(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        doc = json.loads(manifest.read_text())
        doc["claim"]["mvp2_closed"] = False
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest)
        assert _checks(report)["manifest_claim_consistency"].passed is False

    def test_audit_ci_seed_must_be_pinned(self, tmp_path):
        v = _load_verifier()
        manifest = _copy_package(tmp_path)
        doc = json.loads(manifest.read_text())
        doc["package_audit_ci_seed"] = 123
        manifest.write_text(json.dumps(doc, ensure_ascii=False, indent=2))
        report = v.verify_package(manifest)
        assert _checks(report)["audit_ci_seed_pinned"].passed is False


class TestStdlibOnlyGuard:
    def test_verifier_imports_only_stdlib(self):
        source = (ROOT / "scripts" / "verify_mvp2_package.py").read_text()
        tree = ast.parse(source)
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    modules.add(node.module.split(".")[0])
        modules.discard("__future__")
        non_stdlib = modules - set(sys.stdlib_module_names)
        assert non_stdlib == set(), f"verifier must be stdlib-only, found: {non_stdlib}"
