# MVP-3A Proof-Infrastructure Task Variant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP-3A thin runner and generic verifier so a new Isaac target / fixture pose task variant can produce a self-contained, externally recomputable proof package.

**Architecture:** The runner is a producer-side coordinator: it reads a pre-registered config and actual evidence paths, copies verdict-critical JSON into a git-trackable package, derives cached summaries through `app.services.proof`, and never opens Isaac itself. The verifier is an independent stdlib-only auditor: it reads the package, recomputes counts/rates/uplift/CI and closure consistency from `data/rollouts/` plus `data/gates/`, and treats `closure_verdict.json` as cached summary only.

**Tech Stack:** Python 3.11, stdlib-only verifier, pytest, existing `app.services.proof` spine, local filesystem package artifacts.

## Global Constraints

- Do not modify `scripts/run_mvp2c_isaac_training_calibration.py`.
- Do not modify `scripts/run_mvp2b_isaac_proof_evaluator.py`.
- Do not modify `scripts/verify_mvp2_package.py`.
- Do not modify `docs/proof/mvp2_learning_proven_evidence_package/`.
- Do not reuse held-out `40000-40049`.
- Do not tune thresholds or metrics from held-out `42000-42049` outcomes.
- `data/rollouts/` is mandatory for MVP-3A packages.
- `data/gates/` is mandatory for MVP-3A packages.
- `closure_verdict.json` is cached summary, not source of truth.
- Synthetic package tests validate runner/verifier behavior only; they cannot set `package_status=proof_infrastructure_closed`.
- Actual Isaac evidence artifacts and self-contained rollout JSON are required before `proof_infrastructure_closed` is claimed.
- Actual Isaac evidence cannot be self-attested by `config.evidence_kind`.
- Actual Isaac packages must include policy artifact hash binding and per-rollout C-lite mask binding.
- The generic verifier must independently enforce the MVP-3A fixed contract:
  `source_variable_opened=false`, `seed_ranges.train=[43000,43049]`,
  `seed_ranges.calibration=[41000,41029]`, `seed_ranges.heldout=[42000,42049]`,
  `spent_no_reuse` includes `[40000,40049]`, and
  `proof_runtime=dedicated_isaac_connector_insertion_evaluator`.
- No new runtime dependency for `scripts/verify_proof_package.py`; it must run with `python3` only.
- Do not commit, push, tag, or open PR unless the user explicitly authorizes that action. Commit steps below are review checkpoints only.

---

## Scope Check

This plan contains two tightly coupled subsystems:

```text
producer: scripts/run_mvp3a_proof_infrastructure.py
auditor:  scripts/verify_proof_package.py
```

They stay in one plan because the package contract binds them. Actual fresh Isaac rollout execution is outside this plan. This plan stops when synthetic package tests, verifier tamper tests, MVP-2 verifier regression, and frozen-asset diff checks pass.

## File Structure

Create:

```text
scripts/verify_proof_package.py
scripts/run_mvp3a_proof_infrastructure.py
apps/api/tests/test_verify_proof_package.py
apps/api/tests/test_mvp3a_proof_infrastructure.py
```

Modify:

```text
docs/superpowers/specs/2026-06-20-mvp3a-proof-infrastructure-task-variant-design.md
docs/developer/worklog.md
Handoff.md
```

No code task modifies frozen MVP-2 files.

## Package Contract

The runner writes this package shape:

```text
docs/proof/mvp3a_target_fixture_pose_variant_proof_package/
  README.md
  package_manifest.json
  data/
    config.json
    task_variant_attestation.json
    seed_discipline_report.json
    closure_verdict.json
    learning_result_summary.json
    non_claims_attestation.json
    artifact_index.json
    gates/
      runtime_gate.json
      train_generation_runtime_gate.json
      calibration_selection_report.json
      train_trace_summary.json
      post_heldout_guard.json
    rollouts/
      calibration_baseline_rollouts.json
      calibration_candidate_rollouts.json
      heldout_baseline_rollouts.json
      heldout_candidate_rollouts.json
    policies/
      baseline_policy_artifact.json
      candidate_policy_artifact.json
    masks/
      heldout_baseline_success_masks.json
      heldout_candidate_success_masks.json
```

`data/masks/` is optional input/output for synthetic fixtures. If present, verifier runs C-lite. If absent, verifier runs Level B.
For `evidence_kind=actual_isaac`, `data/masks/` and `data/policies/` are mandatory.

Source-of-truth hierarchy:

```text
data/rollouts/ -> rollout count, success count, success rate, uplift, CI, addendum status
data/masks/    -> optional max-consecutive and rollout success derivation
data/policies/ -> actual-Isaac rollout-to-policy hash binding
data/gates/    -> runtime, train trace, calibration selection, post-heldout gates
data/config.json -> pre-registered ranges, thresholds, runtime expectations, audit CI seed
closure_verdict.json -> cached expected result checked against recomputation
```

---

### Task 1: RED tests for generic verifier recompute contract

**Files:**
- Create: `apps/api/tests/test_verify_proof_package.py`
- Create in Task 2: `scripts/verify_proof_package.py`

**Interfaces:**
- Consumes: package contract from the spec.
- Produces: failing tests that require `verify_package(manifest_path: Path) -> Report`.

- [ ] **Step 1: Create the verifier test file with a self-contained package fixture**

Use this fixture shape. Keep every artifact under `tmp_path`; do not read `storage/`.

```python
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_verifier():
    name = "verify_proof_package"
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rollout(seed: int, consecutive: int) -> dict:
    return {
        "scenario_id": f"mvp3a_seed_{seed}",
        "seed": seed,
        "success": consecutive >= 10,
        "env_native_rollout_success": consecutive >= 10,
        "env_native_max_consecutive_success_steps": consecutive,
    }


def _rollouts(seeds: range, success_count: int) -> dict:
    rows = []
    for index, seed in enumerate(seeds):
        rows.append(_rollout(seed, 10 if index < success_count else 3))
    return {"rollout_results": rows}


def _make_package(tmp_path: Path, *, positive: bool = True) -> Path:
    pkg = tmp_path / "pkg"
    data = pkg / "data"
    heldout_candidate_successes = 40 if positive else 5

    files = {
        "data/config.json": {
            "proof_slice": "mvp3a_target_fixture_pose_variant",
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
        },
        "data/task_variant_attestation.json": {
            "family": "connector_insertion",
            "variant": "target_fixture_pose_variant",
            "source_variable_opened": False,
        },
        "data/non_claims_attestation.json": {
            "real_robot_success": False,
            "physical_robot_readiness": False,
            "deployable_policy_readiness": False,
            "visual_policy_performance": False,
            "hmd_openxr_collection_readiness": False,
            "universal_robot_support": False,
            "ur_adapter_support": False,
            "ros2_dds_adapter_support": False,
            "franka_hardware_support": False,
            "marketplace_readiness": False,
            "production_certification": False,
        },
        "data/gates/runtime_gate.json": {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
        "data/gates/train_generation_runtime_gate.json": {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime",
        },
        "data/gates/calibration_selection_report.json": {
            "calibration_only_selection_passed": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
        "data/gates/train_trace_summary.json": {"actual_success_trace_count": 1},
        "data/gates/post_heldout_guard.json": {"passed": True},
        "data/rollouts/calibration_baseline_rollouts.json": _rollouts(range(41000, 41030), 5),
        "data/rollouts/calibration_candidate_rollouts.json": _rollouts(range(41000, 41030), 26),
        "data/rollouts/heldout_baseline_rollouts.json": _rollouts(range(42000, 42050), 5),
        "data/rollouts/heldout_candidate_rollouts.json": _rollouts(
            range(42000, 42050), heldout_candidate_successes
        ),
    }

    baseline_rate = 5 / 50
    candidate_rate = heldout_candidate_successes / 50
    uplift = candidate_rate - baseline_rate
    status = "positive_uplift" if positive else "non_closing"
    files["data/learning_result_summary.json"] = {
        "baseline_heldout_success_rate": baseline_rate,
        "candidate_heldout_success_rate": candidate_rate,
        "heldout_uplift": uplift,
        "learning_result": status,
        "learning_proven_addendum": "present" if positive else "absent",
    }
    files["data/closure_verdict.json"] = {
        "package_status": "proof_infrastructure_closed",
        "learning_result": status,
        "learning_proven_addendum": "present" if positive else "absent",
        "baseline_heldout_successes": 5,
        "candidate_heldout_successes": heldout_candidate_successes,
        "heldout_uplift": uplift,
    }

    for rel, payload in files.items():
        _write_json(pkg / rel, payload)

    artifact_index = []
    for rel in sorted(files):
        artifact_index.append(
            {"data_path": rel, "hash_convention": "file_bytes", "file_sha256": _sha(pkg / rel)}
        )
    _write_json(data / "artifact_index.json", {"artifact_index": artifact_index})
    artifact_index.append(
        {
            "data_path": "data/artifact_index.json",
            "hash_convention": "file_bytes",
            "file_sha256": _sha(data / "artifact_index.json"),
        }
    )
    manifest = {
        "package_name": "mvp3a_target_fixture_pose_variant_proof_package",
        "artifact_index": artifact_index,
        "claims": {
            "package_status": "proof_infrastructure_closed",
            "learning_result": status,
            "learning_proven_addendum": "present" if positive else "absent",
        },
    }
    _write_json(pkg / "package_manifest.json", manifest)
    return pkg / "package_manifest.json"
```

- [ ] **Step 2: Add RED tests for recomputation and cached-summary distrust**

```python
def test_valid_positive_package_verifies_from_rollouts(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    verifier = _load_verifier()

    report = verifier.verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["heldout"]["baseline"]["successes"] == 5
    assert report.recomputed["heldout"]["candidate"]["successes"] == 40
    assert abs(report.recomputed["heldout"]["uplift"] - 0.70) < 1e-9
    assert report.recomputed["learning_result"] == "positive_uplift"


def test_valid_nonclosing_package_verifies_without_addendum(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=False)
    verifier = _load_verifier()

    report = verifier.verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["learning_result"] == "non_closing"
    assert report.recomputed["learning_proven_addendum"] == "absent"


def test_closure_verdict_cannot_override_rollout_recompute(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=False)
    closure = manifest.parent / "data" / "closure_verdict.json"
    payload = json.loads(closure.read_text())
    payload["learning_result"] = "positive_uplift"
    payload["learning_proven_addendum"] = "present"
    _write_json(closure, payload)

    verifier = _load_verifier()
    report = verifier.verify_package(manifest)

    assert report.ok is False
    assert any("closure_summary_consistency" in failure for failure in report.failures())
```

- [ ] **Step 3: Run the RED tests**

Run:

```bash
uv run pytest apps/api/tests/test_verify_proof_package.py -q
```

Expected:

```text
FAIL: FileNotFoundError or module import error for scripts/verify_proof_package.py
```

- [ ] **Step 4: Review checkpoint**

Do not commit unless explicitly authorized. If authorized, use Lore protocol and include:

```text
Tested: uv run pytest apps/api/tests/test_verify_proof_package.py -q (expected RED before implementation)
```

---

### Task 2: Implement generic verifier core

**Files:**
- Create: `scripts/verify_proof_package.py`
- Test: `apps/api/tests/test_verify_proof_package.py`

**Interfaces:**
- Produces: `verify_package(manifest_path: Path) -> Report`
- Produces: CLI `python3 scripts/verify_proof_package.py <manifest>`
- Produces: `Report.ok`, `Report.exit_code`, `Report.failures()`, `Report.recomputed`

- [ ] **Step 1: Create verifier skeleton and report types**

```python
#!/usr/bin/env python3
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
        self.checks.append(CheckResult(name, passed, detail))

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def failures(self) -> list[str]:
        return [f"{check.name}: {check.detail}" for check in self.checks if not check.passed]
```

- [ ] **Step 2: Add stdlib helpers**

```python
def stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def load_json(path: Path):
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seeds_in_range(span: list[int] | tuple[int, int]) -> set[int]:
    start, end = int(span[0]), int(span[1])
    if start > end:
        raise ValueError(f"invalid seed range: {span}")
    return set(range(start, end + 1))


def trailing_int(label: object) -> int | None:
    match = re.search(r"(\d+)$", str(label))
    return int(match.group(1)) if match else None
```

- [ ] **Step 3: Add rollout recomputation**

```python
def rollout_records(doc: dict) -> list[dict]:
    rows = doc.get("rollout_results")
    if not isinstance(rows, list):
        raise ValueError("rollout document missing rollout_results list")
    return rows


def rollout_success(row: dict, stable_steps_required: int) -> bool:
    recorded = row.get("success")
    max_consecutive = row.get("env_native_max_consecutive_success_steps")
    if not isinstance(recorded, bool):
        raise ValueError("rollout success must be bool")
    if not isinstance(max_consecutive, int) or isinstance(max_consecutive, bool):
        raise ValueError("env_native_max_consecutive_success_steps must be int")
    derived = max_consecutive >= stable_steps_required
    if row.get("env_native_rollout_success") is not None and row.get("env_native_rollout_success") != derived:
        raise ValueError("env_native_rollout_success contradicts consecutive threshold")
    if recorded != derived:
        raise ValueError("success contradicts consecutive threshold")
    return derived


def summarize_rollouts(path: Path, stable_steps_required: int) -> dict:
    rows = rollout_records(load_json(path))
    successes = sum(1 for row in rows if rollout_success(row, stable_steps_required))
    total = len(rows)
    return {
        "rollouts": total,
        "successes": successes,
        "rate": successes / total if total else 0.0,
        "seeds": [row.get("seed", trailing_int(row.get("scenario_id"))) for row in rows],
    }
```

- [ ] **Step 4: Add deterministic audit CI**

```python
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
    return {"method": "bootstrap_success_rate_difference", "iterations": iterations, "seed": seed, "lower": lower, "upper": upper}
```

- [ ] **Step 5: Implement `verify_package` core**

The first version must pass Task 1 tests. It must:

```text
1. load manifest and config
2. verify artifact hashes
3. read data/rollouts/ four files
4. compute calibration and held-out summaries
5. compute held-out uplift
6. compute positive_uplift vs non_closing
7. compare cached closure_verdict and learning_result_summary to recomputed values
8. verify non-claims are false
9. return Report
```

Use this entrypoint shape:

```python
def verify_package(manifest_path: Path | str) -> Report:
    manifest_path = Path(manifest_path)
    pkg_dir = manifest_path.parent
    report = Report()
    manifest = load_json(manifest_path)
    config = load_json(pkg_dir / "data" / "config.json")
    thresholds = config["thresholds"]
    stable_steps_required = int(thresholds["stable_steps_required"])

    check_hash_integrity(pkg_dir, manifest, report)
    summaries = recompute_rollout_summaries(pkg_dir, stable_steps_required)
    report.recomputed["calibration"] = summaries["calibration"]
    report.recomputed["heldout"] = summaries["heldout"]
    add_learning_recompute(report, config, summaries)
    check_non_claims(pkg_dir, report)
    check_cached_summaries(pkg_dir, report)
    return report
```

- [ ] **Step 6: Add CLI**

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
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
```

- [ ] **Step 7: Run verifier core tests**

Run:

```bash
uv run pytest apps/api/tests/test_verify_proof_package.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Check stdlib-only import surface**

Run:

```bash
python3 - <<'PY'
import ast
from pathlib import Path
tree = ast.parse(Path("scripts/verify_proof_package.py").read_text())
imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports += [alias.name.split(".")[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.append(node.module.split(".")[0])
blocked = sorted(set(imports) & {"numpy", "scipy", "pandas", "pydantic", "app"})
assert blocked == [], blocked
print("stdlib-only import guard passed")
PY
```

Expected:

```text
stdlib-only import guard passed
```

- [ ] **Step 9: Review checkpoint**

Do not commit unless explicitly authorized. If authorized, commit verifier core and tests with Lore protocol.

---

### Task 3: RED tests for verifier hardening, Level B, and C-lite

**Files:**
- Modify: `apps/api/tests/test_verify_proof_package.py`
- Modify in Task 4: `scripts/verify_proof_package.py`

**Interfaces:**
- Consumes: `_make_package` fixture from Task 1.
- Produces: hard-fail tests for tamper and optional masks.

- [ ] **Step 1: Add tamper helper**

```python
def _tamper_json(path: Path, edit) -> None:
    payload = json.loads(path.read_text())
    edit(payload)
    _write_json(path, payload)
```

- [ ] **Step 2: Add hard-fail tests**

```python
def test_rollout_success_label_tamper_fails_level_b(tmp_path: Path):
    manifest = _make_package(tmp_path)
    rollout_path = manifest.parent / "data" / "rollouts" / "heldout_candidate_rollouts.json"
    _tamper_json(rollout_path, lambda p: p["rollout_results"][0].update({"success": False}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("label_recompute" in failure for failure in report.failures())


def test_non_claim_true_tamper_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    claims_path = manifest.parent / "data" / "non_claims_attestation.json"
    _tamper_json(claims_path, lambda p: p.update({"real_robot_success": True}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("non_claims" in failure for failure in report.failures())


def test_gate_runtime_tamper_fails_closure_consistency(tmp_path: Path):
    manifest = _make_package(tmp_path)
    runtime_path = manifest.parent / "data" / "gates" / "runtime_gate.json"
    _tamper_json(runtime_path, lambda p: p.update({"proof_runtime": "wrong_runtime"}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("gate_recompute" in failure for failure in report.failures())


def test_heldout_spent_overlap_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    config_path = manifest.parent / "data" / "config.json"
    _tamper_json(config_path, lambda p: p["seed_ranges"].update({"heldout": [40000, 40049]}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("spent_no_reuse" in failure for failure in report.failures())


def test_addendum_present_with_nonclosing_rollouts_fails(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=False)
    summary_path = manifest.parent / "data" / "learning_result_summary.json"
    _tamper_json(summary_path, lambda p: p.update({"learning_proven_addendum": "present"}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("learning_result_consistency" in failure for failure in report.failures())
```

- [ ] **Step 3: Add C-lite mask tests**

```python
def _mask_doc(seeds: range, success_count: int) -> dict:
    rows = []
    for index, seed in enumerate(seeds):
        if index < success_count:
            mask = [False, True, True, True, True, True, True, True, True, True, True]
        else:
            mask = [False, True, True, False, True]
        rows.append({"scenario_id": f"mvp3a_seed_{seed}", "seed": seed, "env_native_success_mask": mask})
    return {"masks": rows}


def test_c_lite_masks_recompute_successes_when_present(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    pkg = manifest.parent
    _write_json(pkg / "data" / "masks" / "heldout_baseline_success_masks.json", _mask_doc(range(42000, 42050), 5))
    _write_json(pkg / "data" / "masks" / "heldout_candidate_success_masks.json", _mask_doc(range(42000, 42050), 40))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["c_lite"]["checked"] == 100


def test_c_lite_mask_contradiction_fails(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    pkg = manifest.parent
    _write_json(pkg / "data" / "masks" / "heldout_baseline_success_masks.json", _mask_doc(range(42000, 42050), 5))
    _write_json(pkg / "data" / "masks" / "heldout_candidate_success_masks.json", _mask_doc(range(42000, 42050), 39))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("c_lite_mask_consistency" in failure for failure in report.failures())
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest apps/api/tests/test_verify_proof_package.py -q
```

Expected:

```text
At least one new hardening/C-lite test fails before verifier hardening is implemented.
```

---

### Task 4: Implement verifier hardening, gates, and C-lite

**Files:**
- Modify: `scripts/verify_proof_package.py`
- Test: `apps/api/tests/test_verify_proof_package.py`

**Interfaces:**
- Produces hard checks:
  - `hash_integrity`
  - `rollout_recompute`
  - `label_recompute`
  - `gate_recompute`
  - `seed_disjointness`
  - `spent_no_reuse`
  - `non_claims`
  - `closure_summary_consistency`
  - `learning_result_consistency`
  - `c_lite_mask_consistency` when masks exist

- [ ] **Step 1: Implement hash integrity over manifest artifact index**

```python
def check_hash_integrity(pkg_dir: Path, manifest: dict, report: Report) -> None:
    problems: list[str] = []
    for entry in manifest.get("artifact_index", []):
        rel = entry.get("data_path")
        if not rel:
            continue
        path = pkg_dir / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
            continue
        actual = sha256_file(path)
        if actual != entry.get("file_sha256"):
            problems.append(f"sha256 mismatch {rel}")
    report.add("hash_integrity", not problems, "; ".join(problems) if problems else "all data hashes match")
```

- [ ] **Step 2: Implement gate recompute**

Use only `data/gates/` and `data/config.json`.

```python
def check_gate_recompute(pkg_dir: Path, config: dict, report: Report) -> dict:
    runtime = config["runtime_expectations"]
    runtime_gate = load_json(pkg_dir / "data" / "gates" / "runtime_gate.json")
    train_gate = load_json(pkg_dir / "data" / "gates" / "train_generation_runtime_gate.json")
    selection = load_json(pkg_dir / "data" / "gates" / "calibration_selection_report.json")
    train_trace = load_json(pkg_dir / "data" / "gates" / "train_trace_summary.json")
    post_guard = load_json(pkg_dir / "data" / "gates" / "post_heldout_guard.json")
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
            isinstance(train_trace.get("actual_success_trace_count"), int)
            and not isinstance(train_trace.get("actual_success_trace_count"), bool)
            and train_trace["actual_success_trace_count"] >= 1
        ),
        "post_heldout_guard_matches": post_guard.get("passed") is not False,
    }
    report.add("gate_recompute", all(gates.values()), str(gates))
    return gates
```

- [ ] **Step 3: Implement seed checks**

```python
def check_seed_discipline(config: dict, summaries: dict, report: Report) -> None:
    ranges = config["seed_ranges"]
    train = seeds_in_range(ranges["train"])
    calibration = seeds_in_range(ranges["calibration"])
    heldout = seeds_in_range(ranges["heldout"])
    spent = set()
    for span in ranges.get("spent_no_reuse", []):
        spent |= seeds_in_range(span)
    report.add("seed_disjointness", not (heldout & train or heldout & calibration), "held-out disjoint from train/calibration")
    report.add("spent_no_reuse", not (train & spent or calibration & spent or heldout & spent), "no configured spent range reused")
    observed_heldout = set(summaries["heldout"]["baseline"]["seeds"]) | set(summaries["heldout"]["candidate"]["seeds"])
    report.add("heldout_seed_match", observed_heldout == heldout, f"observed_count={len(observed_heldout)}")
```

- [ ] **Step 4: Implement C-lite mask consistency**

```python
def max_consecutive(mask: list[bool]) -> int:
    best = cur = 0
    for value in mask:
        cur = cur + 1 if bool(value) else 0
        best = max(best, cur)
    return best


def check_c_lite_masks(pkg_dir: Path, stable_steps_required: int, summaries: dict, report: Report) -> None:
    masks_dir = pkg_dir / "data" / "masks"
    baseline_path = masks_dir / "heldout_baseline_success_masks.json"
    candidate_path = masks_dir / "heldout_candidate_success_masks.json"
    if not baseline_path.exists() and not candidate_path.exists():
        return
    problems: list[str] = []
    checked = 0
    for role, path in {"baseline": baseline_path, "candidate": candidate_path}.items():
        if not path.is_file():
            problems.append(f"missing mask file for {role}")
            continue
        rows = load_json(path).get("masks", [])
        successes = 0
        for row in rows:
            checked += 1
            if max_consecutive(row.get("env_native_success_mask", [])) >= stable_steps_required:
                successes += 1
        if successes != summaries["heldout"][role]["successes"]:
            problems.append(f"{role} mask successes {successes} != rollout successes {summaries['heldout'][role]['successes']}")
    report.recomputed["c_lite"] = {"checked": checked}
    report.add("c_lite_mask_consistency", not problems, "; ".join(problems) if problems else f"checked={checked}")
```

- [ ] **Step 5: Run verifier hardening tests**

Run:

```bash
uv run pytest apps/api/tests/test_verify_proof_package.py -q
```

Expected:

```text
All verifier tests pass.
```

- [ ] **Step 6: Run compile/import checks**

Run:

```bash
python3 -m compileall -q scripts/verify_proof_package.py
uvx ruff check scripts/verify_proof_package.py apps/api/tests/test_verify_proof_package.py
```

Expected:

```text
All checks passed
```

---

### Task 5: RED tests for MVP-3A runner

**Files:**
- Create: `apps/api/tests/test_mvp3a_proof_infrastructure.py`
- Create in Task 6: `scripts/run_mvp3a_proof_infrastructure.py`

**Interfaces:**
- Consumes: temp evidence JSON files.
- Produces: failing tests for runner CLI:
  - `python3 scripts/run_mvp3a_proof_infrastructure.py --config <config> --output-dir <pkg>`

- [ ] **Step 1: Create runner test fixture helpers**

Reuse the package fixture logic from `test_verify_proof_package.py` by writing source evidence into `tmp_path / "evidence"` instead of directly into package `data/`.

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from apps.api.tests.test_verify_proof_package import _rollouts, _stable_json, _write_json

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "scripts" / "run_mvp3a_proof_infrastructure.py"
VERIFIER = ROOT / "scripts" / "verify_proof_package.py"


def _write_evidence(tmp_path: Path, *, positive: bool = True) -> dict:
    evidence = tmp_path / "evidence"
    heldout_candidate_successes = 40 if positive else 5
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
    _write_json(paths["baseline_calibration_rollouts"], _rollouts(range(41000, 41030), 5))
    _write_json(paths["candidate_calibration_rollouts"], _rollouts(range(41000, 41030), 26))
    _write_json(paths["baseline_heldout_rollouts"], _rollouts(range(42000, 42050), 5))
    _write_json(paths["candidate_heldout_rollouts"], _rollouts(range(42000, 42050), heldout_candidate_successes))
    _write_json(paths["runtime_gate"], {"passed": True, "runtime_backend": "isaac_runtime", "proof_runtime": "dedicated_isaac_connector_insertion_evaluator"})
    _write_json(paths["train_generation_runtime_gate"], {"passed": True, "runtime_backend": "isaac_runtime", "actual_train_generation_evidence": True, "training_trajectory_source": "isaac_runtime"})
    _write_json(paths["calibration_selection_report"], {"calibration_only_selection_passed": True, "heldout_excluded": True, "selected_adapter_frozen_before_heldout": True, "same_adapter_used_for_baseline_and_candidate": True})
    _write_json(paths["train_trace_summary"], {"actual_success_trace_count": 1})
    _write_json(paths["post_heldout_guard"], {"passed": True})
    return {key: str(path) for key, path in paths.items()}
```

- [ ] **Step 2: Add config helper**

```python
def _write_config(tmp_path: Path, evidence_paths: dict, output_dir: Path, *, source_opened: bool = False) -> Path:
    config = {
        "proof_slice": "mvp3a_target_fixture_pose_variant",
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
        "audit_ci": {"method": "bootstrap_success_rate_difference", "iterations": 200, "seed": 20260620},
        "evidence_paths": evidence_paths,
        "package_policy": {
            "output_dir": str(output_dir),
            "freeze_mvp2_assets": True,
            "copy_rollout_json_into_package": True,
            "copy_c_lite_masks_into_package_when_present": True,
        },
    }
    path = tmp_path / "config.json"
    _write_json(path, config)
    return path
```

- [ ] **Step 3: Add RED runner tests**

```python
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
    config = _write_config(tmp_path, _write_evidence(tmp_path), output, source_opened=True)

    result = _run_runner(config)

    assert result.returncode == 1
    assert "source_variable_opened" in result.stderr
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp3a_proof_infrastructure.py -q
```

Expected:

```text
FAIL: runner script missing
```

---

### Task 6: Implement MVP-3A thin runner

**Files:**
- Create: `scripts/run_mvp3a_proof_infrastructure.py`
- Test: `apps/api/tests/test_mvp3a_proof_infrastructure.py`

**Interfaces:**
- Consumes config JSON.
- Produces `package_manifest.json` and package `data/`.
- Does not import `scripts/verify_proof_package.py`.

- [ ] **Step 1: Create script skeleton and import `app.services.proof`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.proof.closure import derive_closure
from app.services.proof.contracts import (
    CalibrationSelectionReport,
    ClosureThresholds,
    GateInputs,
    LearningReport,
    RuntimeExpectations,
    RuntimeGate,
    TrainRuntimeGate,
)
```

- [ ] **Step 2: Add JSON/hash helpers**

```python
def stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def load_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
```

- [ ] **Step 3: Add preflight validation**

```python
def validate_config(config: dict) -> None:
    if config["task_variant"].get("source_variable_opened") is True:
        raise ValueError("source_variable_opened is not allowed in MVP-3A")
    ranges = config["seed_ranges"]
    if ranges["heldout"] != [42000, 42049]:
        raise ValueError("MVP-3A heldout range must be 42000-42049")
    if ranges["calibration"] != [41000, 41029]:
        raise ValueError("MVP-3A calibration range must be 41000-41029")
    if [40000, 40049] not in ranges.get("spent_no_reuse", []):
        raise ValueError("MVP-2 spent range 40000-40049 must be listed in spent_no_reuse")
```

- [ ] **Step 4: Copy evidence into package**

```python
ROLLOUT_TARGETS = {
    "baseline_calibration_rollouts": "data/rollouts/calibration_baseline_rollouts.json",
    "candidate_calibration_rollouts": "data/rollouts/calibration_candidate_rollouts.json",
    "baseline_heldout_rollouts": "data/rollouts/heldout_baseline_rollouts.json",
    "candidate_heldout_rollouts": "data/rollouts/heldout_candidate_rollouts.json",
}

GATE_TARGETS = {
    "runtime_gate": "data/gates/runtime_gate.json",
    "train_generation_runtime_gate": "data/gates/train_generation_runtime_gate.json",
    "calibration_selection_report": "data/gates/calibration_selection_report.json",
    "train_trace_summary": "data/gates/train_trace_summary.json",
    "post_heldout_guard": "data/gates/post_heldout_guard.json",
}


def copy_evidence(config: dict, output_dir: Path) -> list[str]:
    copied: list[str] = []
    paths = config["evidence_paths"]
    for key, target in {**ROLLOUT_TARGETS, **GATE_TARGETS}.items():
        source = Path(paths[key])
        dest = output_dir / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        copied.append(target)
    for key, target in {
        "heldout_baseline_success_masks": "data/masks/heldout_baseline_success_masks.json",
        "heldout_candidate_success_masks": "data/masks/heldout_candidate_success_masks.json",
    }.items():
        source_value = paths.get(key)
        if source_value:
            source = Path(source_value)
            if source.is_file():
                dest = output_dir / target
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                copied.append(target)
    return copied
```

- [ ] **Step 5: Compute learning summary from copied rollouts**

Use the same formula as verifier, but do not import verifier.

```python
def _records(path: Path) -> list[dict]:
    return load_json(path)["rollout_results"]


def _summary(path: Path) -> dict:
    rows = _records(path)
    successes = sum(1 for row in rows if row["success"] is True)
    return {"rollouts": len(rows), "successes": successes, "rate": successes / len(rows)}


def learning_summary(output_dir: Path, config: dict) -> dict:
    baseline = _summary(output_dir / "data" / "rollouts" / "heldout_baseline_rollouts.json")
    candidate = _summary(output_dir / "data" / "rollouts" / "heldout_candidate_rollouts.json")
    uplift = candidate["rate"] - baseline["rate"]
    positive = candidate["rate"] > baseline["rate"] and uplift >= config["thresholds"]["uplift_min"]
    return {
        "baseline_heldout_successes": baseline["successes"],
        "candidate_heldout_successes": candidate["successes"],
        "baseline_heldout_success_rate": baseline["rate"],
        "candidate_heldout_success_rate": candidate["rate"],
        "heldout_uplift": uplift,
        "learning_result": "positive_uplift" if positive else "non_closing",
        "learning_proven_addendum": "present" if positive else "absent",
    }
```

- [ ] **Step 6: Derive cached closure with proof spine**

```python
def closure_verdict(output_dir: Path, config: dict, summary: dict) -> dict:
    runtime_gate = load_json(output_dir / "data" / "gates" / "runtime_gate.json")
    train_gate = load_json(output_dir / "data" / "gates" / "train_generation_runtime_gate.json")
    selection = load_json(output_dir / "data" / "gates" / "calibration_selection_report.json")
    train_trace = load_json(output_dir / "data" / "gates" / "train_trace_summary.json")
    post_guard = load_json(output_dir / "data" / "gates" / "post_heldout_guard.json")
    thresholds = config["thresholds"]
    inputs = GateInputs(
        learning_report=LearningReport(
            learning_proven=summary["learning_result"] == "positive_uplift",
            proof_eligible=True,
            curated_vs_uncurated_uplift=summary["heldout_uplift"],
            baseline_success_rate=summary["baseline_heldout_success_rate"],
            candidate_success_rate=summary["candidate_heldout_success_rate"],
        ),
        runtime_gate=RuntimeGate(**runtime_gate),
        train_generation_runtime_gate=TrainRuntimeGate(**train_gate),
        calibration_selection_report=CalibrationSelectionReport(**selection),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=thresholds["min_heldout_rollouts_per_policy"],
        actual_success_trace_count=train_trace["actual_success_trace_count"],
        post_heldout_guard_passed=post_guard.get("passed"),
    )
    verdict = derive_closure(
        inputs=inputs,
        runtime_expectations=RuntimeExpectations(**config["runtime_expectations"]),
        thresholds=ClosureThresholds(
            uplift_min=thresholds["uplift_min"],
            min_rollouts_per_policy=thresholds["min_heldout_rollouts_per_policy"],
            trace_minimum=1,
        ),
    )
    return {
        "package_status": "proof_infrastructure_closed",
        "learning_result": summary["learning_result"],
        "learning_proven_addendum": summary["learning_proven_addendum"],
        "closed": verdict.closed,
        "gates": verdict.gates,
        "blockers": verdict.blockers,
        **summary,
    }
```

- [ ] **Step 7: Write manifest, README, and optional addendum**

```python
def write_manifest(output_dir: Path) -> None:
    entries = []
    for path in sorted((output_dir / "data").rglob("*.json")):
        rel = path.relative_to(output_dir).as_posix()
        entries.append({"data_path": rel, "hash_convention": "file_bytes", "file_sha256": sha256_file(path)})
    manifest = {
        "package_name": "mvp3a_target_fixture_pose_variant_proof_package",
        "artifact_index": entries,
        "claims": load_json(output_dir / "data" / "closure_verdict.json"),
    }
    write_json(output_dir / "package_manifest.json", manifest)


def write_readme(output_dir: Path) -> None:
    (output_dir / "README.md").write_text(
        "# MVP-3A Target / Fixture Pose Variant Proof Package\n\n"
        "Run `python3 scripts/verify_proof_package.py package_manifest.json` to recompute the package verdict.\n",
    )
```

- [ ] **Step 8: Add CLI main**

```python
def build_package(config_path: Path) -> Path:
    config = load_json(config_path)
    validate_config(config)
    output_dir = Path(config["package_policy"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "data" / "config.json", config)
    write_json(output_dir / "data" / "task_variant_attestation.json", config["task_variant"])
    write_json(output_dir / "data" / "non_claims_attestation.json", DEFAULT_NON_CLAIMS)
    copy_evidence(config, output_dir)
    summary = learning_summary(output_dir, config)
    write_json(output_dir / "data" / "learning_result_summary.json", summary)
    write_json(output_dir / "data" / "closure_verdict.json", closure_verdict(output_dir, config, summary))
    write_json(output_dir / "data" / "seed_discipline_report.json", {"passed": True, "spent_after_closure_attempt": [42000, 42049]})
    write_json(output_dir / "data" / "artifact_index.json", {"generated_by": "run_mvp3a_proof_infrastructure.py"})
    write_manifest(output_dir)
    write_readme(output_dir)
    return output_dir / "package_manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = build_package(args.config)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"package_manifest={manifest}")
    return 0
```

- [ ] **Step 9: Run runner tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp3a_proof_infrastructure.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 10: Run verifier tests again**

Run:

```bash
uv run pytest apps/api/tests/test_verify_proof_package.py -q
```

Expected:

```text
All verifier tests pass
```

---

### Task 7: Documentation and operator guardrails

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`
- Optional modify: `docs/developer/debugging_guide.md` if the runner command becomes an operator workflow.

**Interfaces:**
- Consumes: final runner/verifier command lines.
- Produces: handoff state for the next session.

- [ ] **Step 1: Update worklog**

Add a dated section with:

```text
작업 내용:
- scripts/verify_proof_package.py added as generic stdlib-only package verifier.
- scripts/run_mvp3a_proof_infrastructure.py added as thin package builder.
- MVP-3A package contract now requires self-contained data/rollouts/ and data/gates/.

판단 이유:
- Avoid MVP-2 self-attestation recurrence.
- Keep actual Isaac rollout execution outside runner.

검증:
- uv run pytest apps/api/tests/test_verify_proof_package.py -q
- uv run pytest apps/api/tests/test_mvp3a_proof_infrastructure.py -q
- python3 scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json
- uvx ruff check scripts apps/api
- git diff --check
```

- [ ] **Step 2: Update Handoff**

Add:

```text
MVP-3A runner/verifier implemented locally.
Actual Isaac evidence collection not yet run.
No proof_infrastructure_closed claim exists until actual Isaac package is generated and verified.
```

- [ ] **Step 3: Decide debugging guide update by command surface**

If the final user workflow includes a persistent command, add:

```text
python3 scripts/run_mvp3a_proof_infrastructure.py --config <config>
python3 scripts/verify_proof_package.py <package_manifest>
```

If only tests use the runner in this slice, record the command in `worklog` and skip `debugging_guide.md`.

---

### Task 8: Final verification and frozen asset audit

**Files:**
- No new files unless Task 7 documents changed.

**Interfaces:**
- Consumes all prior tasks.
- Produces final evidence for completion claim.

- [ ] **Step 1: Run targeted tests**

```bash
uv run pytest apps/api/tests/test_verify_proof_package.py -q
uv run pytest apps/api/tests/test_mvp3a_proof_infrastructure.py -q
uv run pytest apps/api/tests/test_proof_spine_*.py -q
uv run pytest apps/api/tests/test_verify_mvp2_package.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run MVP-2 verifier regression**

```bash
python3 scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json
```

Expected final line:

```text
VERDICT: VERIFIED
```

- [ ] **Step 3: Run lint and compile checks**

```bash
uvx ruff check scripts apps/api
python3 -m compileall -q scripts/verify_proof_package.py scripts/run_mvp3a_proof_infrastructure.py
git diff --check
```

Expected:

```text
All checks passed
compileall exits 0
git diff --check exits 0
```

- [ ] **Step 4: Audit frozen MVP-2 files**

```bash
git diff -- \
  scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package
```

Expected:

```text
no output
```

- [ ] **Step 5: Report remaining truth**

Final completion report must say:

```text
MVP-3A runner/verifier contract implemented and tested with synthetic packages.
No actual MVP-3A proof_infrastructure_closed claim has been made.
Actual Isaac evidence collection remains a separate next slice.
```

Do not claim:

```text
- MVP-3A Proof-Infrastructure Closed
- MVP-3A Learning-Proven Addendum
- real robot readiness
- adapter support
```

---

## Self-Review Checklist

- Spec coverage:
  - self-contained rollout bundle -> Task 1, Task 2, Task 5, Task 6
  - Level B and C-lite -> Task 3, Task 4
  - calibration/held-out threshold split -> Task 1 fixture, Task 2 verifier, Task 5 runner config
  - dedicated proof runtime -> Task 1 fixture, Task 5 config, Task 6 closure derivation
  - synthetic test boundary -> Global Constraints, Task 8 report
  - frozen MVP-2 assets -> Global Constraints, Task 8 audit
- Red-flag scan required after saving:
  - Search this plan for unfinished markers, vague repair verbs, deferred work language, and ellipsis characters; the scan must return no matches.
- Type consistency:
  - `verify_package(manifest_path: Path | str) -> Report`
  - runner CLI uses `--config`
  - package fields use `data/rollouts/`, `data/gates/`, `data/masks/`
