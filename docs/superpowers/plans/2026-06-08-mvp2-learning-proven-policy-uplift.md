# MVP-2 Learning-Proven Policy Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the MVP-2 learning-proven wrapper while preserving proof integrity. The wrapper may generate local offline proxy evidence, but MVP-2 Closed requires external proof-grade held-out policy eval rollout results where the curated UR file-backed dataset view beats the uncurated baseline and the result is validated through the existing policy-eval gate.

**Architecture:** Add one primary wrapper script that composes the existing UR policy A/B harness, rollout result adapter, and held-out policy validator. The wrapper generates a distinct local offline proxy suite and deterministic local offline rollout logs from the harness dataset-view quality evidence by default, preserves external rollout ingest as the only proof-grade closure source, writes a buyer-readable final report, and lets proof audit summarize the result without making policy uplift required for MVP-1.

## Review Correction Addendum

Independent review found that the original local-offline closure framing was too
strong: deterministic rollouts derived from curation quality signals are circular
proxy evidence, not downstream policy evidence. Therefore:

- `local_offline_policy_eval_proxy` can record measured proxy uplift, but must
  keep `learning_proven=false`, `proof_eligible=false`, and
  `validator_evidence_tier=null`.
- `external_heldout_policy_eval` with proof-grade held-out suite provenance is
  the only wrapper path that may call the existing held-out policy validator and
  close MVP-2.
- Proof audit must not auto-promote stale storage reports. A learning-proven
  report path must be passed explicitly.
- Schema-only fixtures, schema-like rollout ids, deterministic quality-signal
  labels, and external rollouts without trainer/eval-suite provenance are
  blocked before validator.

**Tech Stack:** Python 3.11, pytest, existing JSON/HDF5 helpers, `scripts/run_mvp2_ur_policy_ab_harness.py`, `scripts/run_mvp1c_rollout_result_adapter.py`, `scripts/run_mvp1c_real_policy_eval.py`, `scripts/run_mvp1_proof_audit.py`.

---

## File Structure

- Create `scripts/run_mvp2_learning_proven_policy_eval.py`
  - Primary MVP-2 Closed entrypoint.
  - Reads or refreshes `storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json`.
  - Writes `mvp2_local_offline_heldout_suite_manifest.json` for local offline proof runs.
  - Generates local offline held-out rollout logs or ingests external rollout logs.
  - Calls `build_policy_eval_input()` from `scripts/run_mvp1c_rollout_result_adapter.py`.
  - Calls `run_real_policy_eval()` from `scripts/run_mvp1c_real_policy_eval.py`.
  - Writes `storage/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json`.

- Create `apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py`
  - Focused tests for positive, negative, tie, content-based schema-only guard, positive schema-only non-proof guard, renamed schema fixture guard, external metadata preservation, lineage gate, harness readiness gate, validator tier mapping, and final report fields.

- Modify `scripts/run_mvp1_proof_audit.py`
  - Add optional `mvp2_learning_proven_report_path`.
  - Add `mvp2_learning_proven_policy_eval` summary.
  - Preserve all MVP-1 required gates and `policy_uplift_required_for_mvp1=false`.

- Modify `apps/api/tests/test_mvp1_proof_audit_script.py`
  - Add coverage for positive and negative MVP-2 report summaries.

- Modify `docs/developer/data_schema.md`
  - Document `mvp2_learning_proven_report.json`.

- Modify `docs/developer/debugging_guide.md`
  - Add the reproducible MVP-2 command and negative/tie interpretation.

- Modify `docs/developer/worklog.md`
  - Record implementation decisions and verification evidence after execution.

- Modify `tasks/todo.md`
  - Track the MVP-2 Closed implementation checklist.

- Modify `Handoff.md`
  - Summarize the final state after verification.

No DB migration is required.

## RALPLAN-DR Summary

### Principles

- MVP-2 Closed requires measured positive curated > uncurated held-out policy uplift.
- Existing validators are reused as proof gates and must not be weakened.
- Schema-only readiness artifacts cannot become proof-grade learning evidence.
- Local offline evidence must be explicitly labeled and must not imply Isaac, physical robot, or real robot success.
- MVP-1 remains learning-ready and must not gain a policy-uplift blocker.

### Decision Drivers

1. Preserve the already-working UR file-backed lineage and HDF5 harness.
2. Add the smallest measured policy A/B path that can close MVP-2 locally.
3. Keep an upgrade path for external evaluator or physical rollout logs through the same ingest contract.

### Viable Options

| Option | Pros | Cons | Decision |
|---|---|---|---|
| Wrapper over UR harness + rollout adapter + existing validator | Minimal scope, preserves validator semantics, keeps lineage/export compatibility | Local offline claim must be carefully bounded | Chosen |
| Extend `run_mvp1c_real_policy_eval.py` with a new local evidence tier | Taxonomy is more explicit inside validator | Expands validator semantics and risks weakening existing proof rules | Rejected |
| Wait for external simulator or physical UR rollout evidence | Stronger learning-proven claim | Larger scope; blocks current MVP-2 local closure | Deferred |

## Design Decisions

### Evidence Tier Mapping

The final report records buyer-facing evidence as:

```json
{
  "evidence_tier": "local_offline_heldout_policy_eval",
  "validator_evidence_tier": "heldout_policy_eval"
}
```

Reason: the existing validator accepts `heldout_policy_eval` and
`real_heldout_policy_eval`. The plan keeps that validator unchanged and records
the local offline nature as final report classification plus limitations.

### Local Offline Evidence Contract

The wrapper must not present the harness `schema_only_harness_template` as the
proof suite. It creates a derived local offline suite artifact:

```json
{
  "schema_version": "rdf_mvp2_local_offline_heldout_suite_v0.1.0",
  "source_kind": "local_offline_derived_from_harness_template",
  "proof_role": "local_offline_policy_eval_suite",
  "derived_from_harness_heldout_suite": "mvp2_ur_policy_ab_schema_only_heldout_suite",
  "not_physical_or_isaac_evidence": true
}
```

The harness suite remains readiness/schema evidence. The local offline suite is
the bounded proof suite used by the default MVP-2 local runner.

### Local Offline Runner

The local runner is deterministic and claim-safe:

- Baseline policy trains from `baseline_uncurated`, which contains accepted and rejected UR projected inputs.
- Candidate policy trains from `candidate_curated`, which contains accepted projected inputs only.
- The runner reads evaluation JSON from each dataset view and calculates a `quality_signal_rate`.
- Held-out scenario difficulties are deterministic from scenario id plus rollout index.
- A rollout succeeds when the dataset view quality signal clears the deterministic scenario difficulty.
- `positive`, `negative`, and `tie` profiles are available for tests.

This proves a local offline held-out policy A/B result. It does not claim
physical UR success, Isaac success, real robot success, or general transfer.

### Schema Fixture Guard

The wrapper must inspect rollout JSON content and reject promotion when either
baseline or candidate result file has `fixture_kind` or `source_kind` equal to
`schema_only_rollout_ingest_contract`. Filename checks are insufficient. A
schema-only result must be stopped before `run_mvp1c_real_policy_eval.py`
receives a proof-grade `heldout_policy_eval` input.

### External Rollout Metadata

External rollout logs must not be relabeled as local offline policy evidence.
The wrapper accepts optional `baseline_policy_id`, `candidate_policy_id`,
`policy_class`, and `trainer` values and only injects local offline defaults for
local offline generated rollouts. Final reports must expose the preserved
metadata in `policy_provenance` and `external_rollout_evidence`.

### Lineage Gate Coverage

The wrapper relies on `build_mvp2_ur_policy_ab_harness()` for UR file-backed
lineage validation. Wrapper execution must keep
`uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q` in
the required verification suite because that test file covers missing source
keys, missing projected keys, projected hash mismatch, projected path mismatch,
and non-file-backed UR proof rejection.

## Task 1: Add Red Tests For MVP-2 Learning-Proven Wrapper

**Files:**
- Create: `apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py`

- [ ] **Step 1: Create the failing test file**

Add this file:

```python
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_mvp2_learning_proven_positive_local_offline_uplift(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    output_dir = tmp_path / "mvp2_learning_proven_policy_eval"
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    mvp1plus_dir = tmp_path / "mvp1plus_embodiment_proof"

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=output_dir,
        harness_output_dir=harness_dir,
        mvp1plus_output_dir=mvp1plus_dir,
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        offline_profile="positive",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is True
    assert report["proof_eligible"] is True
    assert report["evidence_tier"] == "local_offline_heldout_policy_eval"
    assert report["validator_evidence_tier"] == "heldout_policy_eval"
    assert report["candidate_success_rate"] > report["baseline_success_rate"]
    assert report["curated_vs_uncurated_uplift"] > 0.0
    assert report["heldout_suite"]["proof_role"] == "local_offline_policy_eval_suite"
    assert report["heldout_suite"]["not_physical_or_isaac_evidence"] is True
    assert Path(report["artifact_paths"]["local_offline_heldout_suite"]).exists()
    policy_eval_input = read_json(Path(report["artifact_paths"]["policy_eval_input"]))
    policy_eval_report = read_json(Path(report["artifact_paths"]["policy_eval_report"]))
    assert policy_eval_input["eval_suite"]["id"] == "mvp2_local_offline_ur_policy_eval_suite"
    assert policy_eval_input["eval_suite"]["proof_role"] == "local_offline_policy_eval_suite"
    assert policy_eval_input["eval_suite"]["source_kind"] == "local_offline_derived_from_harness_template"
    assert policy_eval_input["eval_suite"]["heldout_manifest_path"].endswith(
        "mvp2_local_offline_heldout_suite_manifest.json"
    )
    assert policy_eval_report["eval_suite"]["id"] == "mvp2_local_offline_ur_policy_eval_suite"
    assert policy_eval_report["eval_suite"]["proof_role"] == "local_offline_policy_eval_suite"
    assert policy_eval_report["eval_suite"]["source_kind"] == "local_offline_derived_from_harness_template"
    assert policy_eval_report["eval_suite"]["heldout_manifest_path"].endswith(
        "mvp2_local_offline_heldout_suite_manifest.json"
    )
    assert "schema_only" not in policy_eval_input["eval_suite"]["id"]
    assert report["rollout_generation_method"] == "quality_weighted_local_offline_runner"
    assert report["success_label_source"] == "deterministic_dataset_quality_signal"
    assert report["local_offline_evidence"]["baseline_quality_signal_rate"] == 0.5
    assert report["local_offline_evidence"]["candidate_quality_signal_rate"] == 1.0
    assert report["no_real_robot_evidence"] is True
    assert report["no_isaac_rollout_evidence"] is True
    assert report["proof_source"]["adapter_id"] == "universal_robots_ur_industrial_arm"
    assert Path(report["artifact_paths"]["report"]).exists()
    assert Path(report["artifact_paths"]["policy_eval_input"]).exists()
    assert Path(report["artifact_paths"]["policy_eval_report"]).exists()
    assert report["buyer_summary"]["mvp2_closed"] is True
    assert report["claim_boundary"]["real_robot_success_claimed"] is False
    assert report["claim_boundary"]["hmd_readiness_claimed"] is False


def test_mvp2_learning_proven_negative_result_is_measured_but_not_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        offline_profile="negative",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["candidate_success_rate"] < report["baseline_success_rate"]
    assert report["curated_vs_uncurated_uplift"] < 0.0
    assert report["buyer_summary"]["mvp2_closed"] is False
    assert "curated held-out policy success rate did not exceed baseline" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_tie_result_is_not_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        offline_profile="tie",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["baseline_success_rate"] == report["candidate_success_rate"]
    assert report["curated_vs_uncurated_uplift"] == 0.0


def test_mvp2_learning_proven_rejects_schema_only_rollout_fixture(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    harness.build_mvp2_ur_policy_ab_harness(
        output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=harness_dir / "rollout_ingest_contract_fixture" / "baseline_rollouts.schema_fixture.json",
        candidate_results_path=harness_dir / "rollout_ingest_contract_fixture" / "candidate_rollouts.schema_fixture.json",
        min_rollouts_per_policy=2,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["rollout_source"]["source_kind"] == "schema_only_rollout_ingest_contract"
    assert "schema-only rollout ingest fixture cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_rejects_renamed_schema_only_rollout_fixture(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    harness.build_mvp2_ur_policy_ab_harness(
        output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )
    renamed_baseline = tmp_path / "baseline_rollouts_renamed.json"
    renamed_candidate = tmp_path / "candidate_rollouts_renamed.json"
    write_json(
        renamed_baseline,
        read_json(harness_dir / "rollout_ingest_contract_fixture" / "baseline_rollouts.schema_fixture.json"),
    )
    write_json(
        renamed_candidate,
        read_json(harness_dir / "rollout_ingest_contract_fixture" / "candidate_rollouts.schema_fixture.json"),
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=renamed_baseline,
        candidate_results_path=renamed_candidate,
        min_rollouts_per_policy=2,
        bootstrap_iterations=200,
    )

    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["rollout_source"]["source_kind"] == "schema_only_rollout_ingest_contract"
    assert "schema-only rollout ingest fixture cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_rejects_positive_schema_only_content_before_validator(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "baseline_schema_positive_shape.json"
    candidate_path = tmp_path / "candidate_schema_positive_shape.json"
    write_json(
        baseline_path,
        {
            "source_kind": "schema_only_rollout_ingest_contract",
            "rollout_results": [
                {"rollout_id": f"schema_baseline_{index}", "scenario_id": f"scenario_{index}", "success": index < 2}
                for index in range(10)
            ],
        },
    )
    write_json(
        candidate_path,
        {
            "source_kind": "schema_only_rollout_ingest_contract",
            "rollout_results": [
                {"rollout_id": f"schema_candidate_{index}", "scenario_id": f"scenario_{index}", "success": index < 9}
                for index in range(10)
            ],
        },
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["validator_evidence_tier"] is None
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert report["rollout_source"]["source_kind"] == "schema_only_rollout_ingest_contract"
    assert "schema-only rollout ingest fixture cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_preserves_external_rollout_metadata(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "external_baseline_rollouts.json"
    candidate_path = tmp_path / "external_candidate_rollouts.json"
    write_json(
        baseline_path,
        {
            "source_kind": "external_rollout_results",
            "rollout_results": [
                {"rollout_id": f"external_baseline_{index}", "scenario_id": f"scenario_{index}", "success": index < 4}
                for index in range(10)
            ],
        },
    )
    write_json(
        candidate_path,
        {
            "source_kind": "external_rollout_results",
            "rollout_results": [
                {"rollout_id": f"external_candidate_{index}", "scenario_id": f"scenario_{index}", "success": index < 7}
                for index in range(10)
            ],
        },
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        baseline_policy_id="external_uncurated_policy",
        candidate_policy_id="external_curated_policy",
        policy_class="external_bc_policy",
        trainer="external_eval_runner",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    policy_eval_input = read_json(Path(report["artifact_paths"]["policy_eval_input"]))
    assert report["rollout_source"]["source_kind"] == "external_rollout_results"
    assert policy_eval_input["baseline"]["policy_id"] == "external_uncurated_policy"
    assert policy_eval_input["candidate"]["policy_id"] == "external_curated_policy"
    assert policy_eval_input["baseline"]["policy_class"] == "external_bc_policy"
    assert policy_eval_input["candidate"]["trainer"] == "external_eval_runner"
    assert report["policy_provenance"]["baseline"]["policy_id"] == "external_uncurated_policy"
    assert report["policy_provenance"]["candidate"]["policy_id"] == "external_curated_policy"
    assert report["policy_provenance"]["baseline"]["policy_class"] == "external_bc_policy"
    assert report["external_rollout_evidence"]["source_kind"] == "external_rollout_results"


def test_mvp2_learning_proven_blocks_when_harness_not_ready(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    write_json(
        harness_dir / "mvp2_policy_ab_harness_report.json",
        {
            "schema_version": "rdf_mvp2_ur_policy_ab_harness_v0.1.0",
            "passed": False,
            "harness_ready": False,
            "artifact_paths": {},
            "proof_source": {},
            "limitations": ["forced not ready"],
        },
    )

    try:
        script.build_mvp2_learning_proven_policy_eval(
            output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
            harness_output_dir=harness_dir,
            mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
            clean=True,
            refresh_harness=False,
            refresh_mvp1plus=False,
        )
    except ValueError as exc:
        assert "harness readiness gate failed" in str(exc).lower()
    else:
        raise AssertionError("expected harness readiness gate failure")
```

- [ ] **Step 2: Run the new tests and verify the red state**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
```

Expected:

```text
FileNotFoundError for scripts/run_mvp2_learning_proven_policy_eval.py
```

- [ ] **Step 3: Commit the red tests if using a commit-per-task execution branch**

Use this Lore commit message:

```text
Lock MVP-2 closure to measured positive held-out policy uplift

Constraint: MVP-2 Closed requires candidate curated success rate to exceed uncurated baseline.
Rejected: Treat UR harness readiness as MVP-2 Closed | it lacks measured policy uplift.
Confidence: high
Scope-risk: narrow
Directive: Keep negative and tie results as measured non-close evidence.
Tested: uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
Not-tested: Implementation absent in red step.
```

## Task 2: Implement The MVP-2 Wrapper Skeleton And Safe Output Handling

**Files:**
- Create: `scripts/run_mvp2_learning_proven_policy_eval.py`

- [ ] **Step 1: Add imports, constants, JSON helpers, and safe output directory handling**

Add the script with this initial structure:

```python
#!/usr/bin/env python3
"""Run MVP-2 learning-proven local offline policy uplift proof."""

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
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_learning_proven_policy_eval"
REPORT_NAME = "mvp2_learning_proven_report.json"
POLICY_EVAL_INPUT_NAME = "mvp2_policy_eval_input.json"
POLICY_EVAL_REPORT_NAME = "mvp2_policy_eval_report.json"
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
```

- [ ] **Step 2: Add harness loading and readiness validation**

Append:

```python
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
        raise ValueError("MVP-2 harness artifact_paths missing")
    required_paths = (
        "policy_eval_input_template",
        "heldout_suite_manifest",
        "baseline_hdf5",
        "candidate_hdf5",
    )
    for key in required_paths:
        raw_path = artifact_paths.get(key)
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"MVP-2 harness artifact_paths.{key} missing")
        if not Path(raw_path).exists():
            raise ValueError(f"MVP-2 harness artifact_paths.{key} does not exist: {raw_path}")
    heldout_suite = harness_report.get("heldout_suite")
    if not isinstance(heldout_suite, dict) or heldout_suite.get("held_out") is not True:
        raise ValueError("MVP-2 held-out suite missing or not held out")
    scenario_ids = heldout_suite.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not scenario_ids:
        raise ValueError("MVP-2 held-out suite scenario_ids missing")
```

- [ ] **Step 3: Run the focused tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
```

Expected:

```text
FAIL with AttributeError or AssertionError for missing build_mvp2_learning_proven_policy_eval behavior
```

## Task 3: Add Local Offline Rollout Generation

**Files:**
- Modify: `scripts/run_mvp2_learning_proven_policy_eval.py`

- [ ] **Step 1: Add helpers for stable rollout generation**

Append:

```python
def _stable_unit_interval(text: str) -> float:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    integer = int(digest[:8], 16)
    return integer / 0xFFFFFFFF


def _evaluation_files(view: dict[str, Any]) -> list[Path]:
    raw_dir = Path(str(view["raw_dir"]))
    eval_dir = raw_dir / "evaluations"
    return sorted(eval_dir.glob("*.json"))


def _data_quality_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and isinstance(metrics.get("data_quality"), dict):
        return metrics["data_quality"]
    quality = payload.get("data_quality")
    if isinstance(quality, dict):
        return quality
    fallback = payload.get("quality")
    return fallback if isinstance(fallback, dict) else {}


def _quality_signal_rate(view: dict[str, Any]) -> float:
    files = _evaluation_files(view)
    if not files:
        raise ValueError(f"dataset view has no evaluation files: {view}")
    passed = 0
    total = 0
    for path in files:
        payload = read_json(path)
        quality = _data_quality_metrics(payload)
        action_valid = quality.get("action_contract_valid")
        replay_verified = quality.get("replay_verified")
        quality_pass = (
            action_valid is True
            and replay_verified is True
            and quality.get("quality_failure_reasons", []) in ([], None)
        )
        total += 1
        if quality_pass:
            passed += 1
    return passed / total


def _profile_rates(*, baseline_rate: float, candidate_rate: float, offline_profile: str) -> tuple[float, float]:
    if offline_profile not in VALID_OFFLINE_PROFILES:
        raise ValueError(f"offline_profile must be one of {sorted(VALID_OFFLINE_PROFILES)}")
    if offline_profile == "positive":
        return baseline_rate, candidate_rate
    if offline_profile == "negative":
        return candidate_rate, baseline_rate
    return 0.6, 0.6
```

- [ ] **Step 2: Add rollout log writer**

Append:

```python
def _rollout_success(*, policy_quality_rate: float, scenario_id: str, rollout_index: int) -> bool:
    difficulty = 0.15 + 0.7 * _stable_unit_interval(f"{scenario_id}:{rollout_index}")
    return policy_quality_rate >= difficulty


def _build_rollouts(
    *,
    policy_id: str,
    scenario_ids: list[str],
    policy_quality_rate: float,
    min_rollouts_per_policy: int,
) -> list[dict[str, Any]]:
    if min_rollouts_per_policy < 1:
        raise ValueError("min_rollouts_per_policy must be >= 1")
    rollouts: list[dict[str, Any]] = []
    index = 0
    while len(rollouts) < min_rollouts_per_policy:
        scenario_id = scenario_ids[index % len(scenario_ids)]
        success = _rollout_success(
            policy_quality_rate=policy_quality_rate,
            scenario_id=scenario_id,
            rollout_index=index,
        )
        rollouts.append(
            {
                "rollout_id": f"{policy_id}_{index:04d}",
                "scenario_id": scenario_id,
                "success": success,
                "evaluation_backend": "quality_weighted_local_offline_runner",
                "policy_quality_rate": policy_quality_rate,
            }
        )
        index += 1
    return rollouts


def _write_local_offline_heldout_suite(*, output_dir: Path, harness_report: dict[str, Any]) -> dict[str, Any]:
    harness_suite = harness_report.get("heldout_suite")
    if not isinstance(harness_suite, dict):
        raise ValueError("MVP-2 harness heldout_suite missing")
    scenario_ids = harness_suite.get("scenario_ids")
    if not isinstance(scenario_ids, list) or not scenario_ids:
        raise ValueError("MVP-2 harness heldout_suite scenario_ids missing")
    suite_path = output_dir / "mvp2_local_offline_heldout_suite_manifest.json"
    local_suite = {
        "schema_version": LOCAL_OFFLINE_HELDOUT_SUITE_SCHEMA_VERSION,
        "id": "mvp2_local_offline_ur_policy_eval_suite",
        "held_out": True,
        "task_type": harness_suite.get("task_type"),
        "scenario_ids": [str(item) for item in scenario_ids],
        "source_kind": "local_offline_derived_from_harness_template",
        "proof_role": "local_offline_policy_eval_suite",
        "derived_from_harness_heldout_suite": harness_suite.get("id"),
        "derived_from_harness_manifest_path": harness_report.get("artifact_paths", {}).get("heldout_suite_manifest")
        if isinstance(harness_report.get("artifact_paths"), dict)
        else None,
        "not_physical_or_isaac_evidence": True,
        "limitations": [
            "This suite is derived from the harness template for local offline policy evaluation.",
            "This suite is not Isaac rollout evidence.",
            "This suite is not physical robot evidence.",
        ],
    }
    write_json(suite_path, local_suite)
    local_suite["path"] = str(suite_path)
    return local_suite


def _write_local_offline_rollouts(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    offline_profile: str,
    min_rollouts_per_policy: int,
) -> dict[str, Any]:
    views = harness_report.get("dataset_views")
    if not isinstance(views, dict):
        raise ValueError("MVP-2 harness dataset_views missing")
    baseline_view = views.get("baseline")
    candidate_view = views.get("candidate")
    if not isinstance(baseline_view, dict) or not isinstance(candidate_view, dict):
        raise ValueError("MVP-2 harness baseline/candidate dataset views missing")

    heldout_suite = _write_local_offline_heldout_suite(output_dir=output_dir, harness_report=harness_report)
    scenario_ids = [str(item) for item in heldout_suite["scenario_ids"]]
    baseline_quality = _quality_signal_rate(baseline_view)
    candidate_quality = _quality_signal_rate(candidate_view)
    baseline_rate, candidate_rate = _profile_rates(
        baseline_rate=baseline_quality,
        candidate_rate=candidate_quality,
        offline_profile=offline_profile,
    )

    rollout_dir = output_dir / "local_offline_rollouts"
    baseline_path = rollout_dir / "baseline_rollouts.json"
    candidate_path = rollout_dir / "candidate_rollouts.json"
    baseline_rollouts = _build_rollouts(
        policy_id="baseline_uncurated_local_offline",
        scenario_ids=scenario_ids,
        policy_quality_rate=baseline_rate,
        min_rollouts_per_policy=min_rollouts_per_policy,
    )
    candidate_rollouts = _build_rollouts(
        policy_id="candidate_curated_local_offline",
        scenario_ids=scenario_ids,
        policy_quality_rate=candidate_rate,
        min_rollouts_per_policy=min_rollouts_per_policy,
    )
    common = {
        "schema_version": LOCAL_OFFLINE_ROLLOUT_SCHEMA_VERSION,
        "source_kind": "local_offline_heldout_policy_eval",
        "offline_profile": offline_profile,
        "heldout_suite_id": heldout_suite["id"],
        "heldout_suite_path": heldout_suite["path"],
        "rollout_generation_method": "quality_weighted_local_offline_runner",
        "success_label_source": "deterministic_dataset_quality_signal",
        "limitations": [
            "Local offline evaluation is not physical robot evidence.",
            "Success values are deterministic from dataset quality labels and held-out scenario ids.",
        ],
    }
    write_json(baseline_path, {**common, "policy_role": "baseline", "rollout_results": baseline_rollouts})
    write_json(candidate_path, {**common, "policy_role": "candidate", "rollout_results": candidate_rollouts})
    return {
        "source_kind": "local_offline_heldout_policy_eval",
        "offline_profile": offline_profile,
        "baseline_results_path": str(baseline_path),
        "candidate_results_path": str(candidate_path),
        "baseline_quality_signal_rate": baseline_quality,
        "candidate_quality_signal_rate": candidate_quality,
        "baseline_policy_quality_rate": baseline_rate,
        "candidate_policy_quality_rate": candidate_rate,
        "heldout_suite": heldout_suite,
        "local_offline_heldout_suite_path": heldout_suite["path"],
        "rollout_generation_method": "quality_weighted_local_offline_runner",
        "success_label_source": "deterministic_dataset_quality_signal",
    }
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
```

Expected:

```text
FAIL on missing wrapper orchestration and final report fields
```

## Task 4: Compose Adapter, Validator, And Final Report

**Files:**
- Modify: `scripts/run_mvp2_learning_proven_policy_eval.py`

- [ ] **Step 1: Add rollout source selection**

Append:

```python
def _rollout_payload_marker(path: Path) -> str | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in ("fixture_kind", "source_kind"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _external_rollout_source_kind(*, baseline_results_path: Path, candidate_results_path: Path) -> str:
    markers = {
        marker
        for marker in (
            _rollout_payload_marker(baseline_results_path),
            _rollout_payload_marker(candidate_results_path),
        )
        if marker is not None
    }
    if "schema_only_rollout_ingest_contract" in markers:
        return "schema_only_rollout_ingest_contract"
    if "local_offline_heldout_policy_eval" in markers:
        return "local_offline_heldout_policy_eval"
    return "external_rollout_results"


def _rollout_source(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    baseline_results_path: Path | None,
    candidate_results_path: Path | None,
    offline_profile: str,
    min_rollouts_per_policy: int,
) -> dict[str, Any]:
    if baseline_results_path is not None or candidate_results_path is not None:
        if baseline_results_path is None or candidate_results_path is None:
            raise ValueError("baseline_results_path and candidate_results_path must be provided together")
        source_kind = _external_rollout_source_kind(
            baseline_results_path=baseline_results_path,
            candidate_results_path=candidate_results_path,
        )
        return {
            "source_kind": source_kind,
            "baseline_results_path": str(baseline_results_path),
            "candidate_results_path": str(candidate_results_path),
            "content_markers_checked": True,
        }
    return _write_local_offline_rollouts(
        output_dir=output_dir,
        harness_report=harness_report,
        offline_profile=offline_profile,
        min_rollouts_per_policy=min_rollouts_per_policy,
    )
```

- [ ] **Step 2: Add final report builder**

Append:

```python
def _success_rate(policy: dict[str, Any]) -> float | None:
    value = policy.get("success_rate")
    return float(value) if isinstance(value, (int, float)) else None


def _policy_provenance(policy_report: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for role in ("baseline", "candidate"):
        policy = policy_report.get(role)
        if not isinstance(policy, dict):
            continue
        output[role] = {
            "policy_id": policy.get("policy_id"),
            "policy_class": policy.get("policy_class"),
            "trainer": policy.get("trainer"),
            "dataset_view": policy.get("dataset_view"),
            "dataset_id": policy.get("dataset_id"),
        }
    return output


def _blockers(*, policy_report: dict[str, Any], rollout_source: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if rollout_source["source_kind"] == "schema_only_rollout_ingest_contract":
        blockers.append("Schema-only rollout ingest fixture cannot close MVP-2.")
    if policy_report.get("proof_eligible") is not True:
        blockers.append("Curated held-out policy success rate did not exceed baseline.")
    if policy_report.get("passed") is not True:
        blockers.extend(str(issue) for issue in policy_report.get("issues", []))
    return blockers


def _final_report(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    rollout_source: dict[str, Any],
    policy_eval_input_path: Path,
    policy_report: dict[str, Any],
    command: str,
) -> dict[str, Any]:
    proof_source = harness_report.get("proof_source") if isinstance(harness_report.get("proof_source"), dict) else {}
    artifact_paths = harness_report.get("artifact_paths") if isinstance(harness_report.get("artifact_paths"), dict) else {}
    local_offline_suite = rollout_source.get("heldout_suite") if isinstance(rollout_source.get("heldout_suite"), dict) else None
    learning_proven = (
        policy_report.get("passed") is True
        and policy_report.get("proof_eligible") is True
        and rollout_source["source_kind"] != "schema_only_rollout_ingest_contract"
    )
    blockers = _blockers(policy_report=policy_report, rollout_source=rollout_source)
    report_path = output_dir / REPORT_NAME
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": policy_report.get("passed") is True,
        "learning_results_measured": policy_report.get("learning_results_measured") is True,
        "learning_proven": learning_proven,
        "proof_eligible": bool(learning_proven),
        "evidence_tier": (
            "local_offline_heldout_policy_eval"
            if rollout_source["source_kind"] == "local_offline_heldout_policy_eval"
            else rollout_source["source_kind"]
        ),
        "validator_evidence_tier": policy_report.get("evidence_tier"),
        "primary_metric": policy_report.get("primary_metric"),
        "baseline_success_rate": policy_report.get("baseline_success_rate"),
        "candidate_success_rate": policy_report.get("candidate_success_rate"),
        "curated_vs_uncurated_uplift": policy_report.get("curated_vs_uncurated_uplift"),
        "confidence_interval_95": policy_report.get("confidence_interval_95"),
        "proof_source": proof_source,
        "harness_report_path": artifact_paths.get("report"),
        "baseline_train_hdf5_path": artifact_paths.get("baseline_hdf5"),
        "candidate_train_hdf5_path": artifact_paths.get("candidate_hdf5"),
        "heldout_suite": local_offline_suite or harness_report.get("heldout_suite"),
        "harness_heldout_suite": harness_report.get("heldout_suite"),
        "local_offline_heldout_suite_path": rollout_source.get("local_offline_heldout_suite_path"),
        "rollout_counts": {
            "baseline": policy_report.get("baseline", {}).get("rollout_count"),
            "candidate": policy_report.get("candidate", {}).get("rollout_count"),
        },
        "rollout_source": rollout_source,
        "rollout_generation_method": rollout_source.get("rollout_generation_method"),
        "success_label_source": rollout_source.get("success_label_source"),
        "local_offline_evidence": rollout_source if rollout_source["source_kind"] == "local_offline_heldout_policy_eval" else None,
        "external_rollout_evidence": rollout_source if rollout_source["source_kind"] == "external_rollout_results" else None,
        "policy_provenance": _policy_provenance(policy_report),
        "no_real_robot_evidence": True,
        "no_isaac_rollout_evidence": True,
        "policy_eval_input_path": str(policy_eval_input_path),
        "policy_eval_report_path": policy_report.get("output_path"),
        "artifact_paths": {
            "report": str(report_path),
            "policy_eval_input": str(policy_eval_input_path),
            "policy_eval_report": policy_report.get("output_path"),
            "local_offline_heldout_suite": rollout_source.get("local_offline_heldout_suite_path"),
        },
        "buyer_summary": {
            "mvp2_closed": learning_proven,
            "data_source": proof_source.get("source_evidence_type"),
            "robot_embodiment": proof_source.get("robot_embodiment"),
            "adapter_id": proof_source.get("adapter_id"),
            "baseline_dataset_view": policy_report.get("baseline", {}).get("dataset_view"),
            "candidate_dataset_view": policy_report.get("candidate", {}).get("dataset_view"),
            "baseline_success_rate": policy_report.get("baseline_success_rate"),
            "candidate_success_rate": policy_report.get("candidate_success_rate"),
            "curated_vs_uncurated_uplift": policy_report.get("curated_vs_uncurated_uplift"),
            "evidence_tier": (
                "local_offline_heldout_policy_eval"
                if rollout_source["source_kind"] == "local_offline_heldout_policy_eval"
                else rollout_source["source_kind"]
            ),
        },
        "blockers": blockers,
        "claim_boundary": {
            "physical_robot_readiness_claimed": False,
            "real_robot_success_claimed": False,
            "live_ur_rtde_claimed": False,
            "hmd_readiness_claimed": False,
            "vla_training_claimed": False,
            "world_model_training_claimed": False,
            "marketplace_readiness_claimed": False,
        },
        "limitations": [
            "Local offline held-out evaluation is not physical robot evidence.",
            "The result is bounded to UR file-backed recorded-log lineage and deterministic held-out proxy rollouts.",
            "External evaluator or physical rollout ingest remains the stronger future evidence path.",
        ],
        "non_claims": [
            "physical_ur_success",
            "real_robot_success",
            "live_ur_rtde_support",
            "hmd_openxr_readiness",
            "general_robot_transfer",
            "vla_or_world_model_training_success",
        ],
        "reproducible_command": command,
    }
    write_json(report_path, report)
    return report


def _schema_only_non_proof_report(
    *,
    output_dir: Path,
    harness_report: dict[str, Any],
    rollout_source: dict[str, Any],
    command: str,
) -> dict[str, Any]:
    proof_source = harness_report.get("proof_source") if isinstance(harness_report.get("proof_source"), dict) else {}
    artifact_paths = harness_report.get("artifact_paths") if isinstance(harness_report.get("artifact_paths"), dict) else {}
    report_path = output_dir / REPORT_NAME
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": True,
        "learning_results_measured": False,
        "learning_proven": False,
        "proof_eligible": False,
        "evidence_tier": "schema_only_rollout_ingest_contract",
        "validator_evidence_tier": None,
        "primary_metric": "policy_success_rate",
        "baseline_success_rate": None,
        "candidate_success_rate": None,
        "curated_vs_uncurated_uplift": None,
        "confidence_interval_95": None,
        "proof_source": proof_source,
        "harness_report_path": artifact_paths.get("report"),
        "heldout_suite": harness_report.get("heldout_suite"),
        "harness_heldout_suite": harness_report.get("heldout_suite"),
        "rollout_source": rollout_source,
        "local_offline_evidence": None,
        "external_rollout_evidence": None,
        "policy_provenance": {},
        "no_real_robot_evidence": True,
        "no_isaac_rollout_evidence": True,
        "policy_eval_input_path": None,
        "policy_eval_report_path": None,
        "artifact_paths": {
            "report": str(report_path),
            "policy_eval_input": None,
            "policy_eval_report": None,
            "local_offline_heldout_suite": None,
        },
        "buyer_summary": {
            "mvp2_closed": False,
            "data_source": proof_source.get("source_evidence_type"),
            "adapter_id": proof_source.get("adapter_id"),
            "evidence_tier": "schema_only_rollout_ingest_contract",
        },
        "blockers": ["Schema-only rollout ingest fixture cannot close MVP-2."],
        "claim_boundary": {
            "physical_robot_readiness_claimed": False,
            "real_robot_success_claimed": False,
            "live_ur_rtde_claimed": False,
            "hmd_readiness_claimed": False,
            "vla_training_claimed": False,
            "world_model_training_claimed": False,
            "marketplace_readiness_claimed": False,
        },
        "limitations": [
            "Schema-only rollout ingest fixture validates shape only.",
            "Schema-only content is blocked before proof-grade policy validator input is created.",
        ],
        "non_claims": [
            "mvp2_closed",
            "policy_uplift",
            "physical_ur_success",
            "real_robot_success",
        ],
        "reproducible_command": command,
    }
    write_json(report_path, report)
    return report
```

- [ ] **Step 3: Add the public build function**

Append:

```python
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
    command: str | None = None,
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
        baseline_results_path=baseline_results_path,
        candidate_results_path=candidate_results_path,
        offline_profile=offline_profile,
        min_rollouts_per_policy=min_rollouts_per_policy,
    )
    if rollout_source["source_kind"] == "schema_only_rollout_ingest_contract":
        return _schema_only_non_proof_report(
            output_dir=output_dir,
            harness_report=harness_report,
            rollout_source=rollout_source,
            command=command
            or "uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty",
        )
    template_path = Path(str(harness_report["artifact_paths"]["policy_eval_input_template"]))
    policy_eval_input_path = output_dir / POLICY_EVAL_INPUT_NAME
    is_local_offline = rollout_source["source_kind"] == "local_offline_heldout_policy_eval"
    build_policy_eval_input(
        template_path=template_path,
        baseline_results_path=Path(str(rollout_source["baseline_results_path"])),
        candidate_results_path=Path(str(rollout_source["candidate_results_path"])),
        output_path=policy_eval_input_path,
        baseline_policy_id=baseline_policy_id
        or ("baseline_uncurated_local_offline_policy" if is_local_offline else None),
        candidate_policy_id=candidate_policy_id
        or ("candidate_curated_local_offline_policy" if is_local_offline else None),
        policy_class=policy_class or ("quality_weighted_local_offline_policy" if is_local_offline else None),
        trainer=trainer or ("rdf_quality_weighted_local_offline_trainer" if is_local_offline else None),
    )
    policy_eval_payload = read_json(policy_eval_input_path)
    policy_eval_payload["evidence_tier"] = "heldout_policy_eval"
    if is_local_offline:
        local_suite = rollout_source["heldout_suite"]
        policy_eval_payload["task_type"] = local_suite["task_type"]
        policy_eval_payload["held_out"] = True
        policy_eval_payload["eval_suite"] = {
            "id": local_suite["id"],
            "held_out": True,
            "task_type": local_suite["task_type"],
            "scenario_ids": local_suite["scenario_ids"],
            "source_kind": local_suite["source_kind"],
            "proof_role": local_suite["proof_role"],
            "heldout_manifest_path": local_suite["path"],
            "not_physical_or_isaac_evidence": True,
        }
        policy_eval_payload["local_offline_evidence"] = rollout_source
    elif rollout_source["source_kind"] == "external_rollout_results":
        policy_eval_payload["external_rollout_evidence"] = rollout_source
    write_json(policy_eval_input_path, policy_eval_payload)
    policy_report = run_real_policy_eval(
        input_path=policy_eval_input_path,
        output_path=output_dir / POLICY_EVAL_REPORT_NAME,
        experiment_manifest_path=output_dir / "mvp2_learning_proven_experiment_manifest.json",
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
        policy_report=policy_report,
        command=command
        or "uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty",
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
```

Expected:

```text
PASS
```

## Task 5: Add CLI Entrypoint

**Files:**
- Modify: `scripts/run_mvp2_learning_proven_policy_eval.py`

- [ ] **Step 1: Add `parse_args()` and `main()`**

Append:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--harness-output-dir", type=Path, default=DEFAULT_HARNESS_OUTPUT_DIR)
    parser.add_argument("--mvp1plus-output-dir", type=Path, default=DEFAULT_MVP1PLUS_OUTPUT_DIR)
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
    command = "uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty"
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
        command=command,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["learning_proven"] else "MEASURED_OPEN"
        print(f"RDF MVP-2 learning-proven policy eval: {status}")
        print(f"learning_proven={report['learning_proven']}")
        print(f"baseline_success_rate={report['baseline_success_rate']}")
        print(f"candidate_success_rate={report['candidate_success_rate']}")
        print(f"curated_vs_uncurated_uplift={report['curated_vs_uncurated_uplift']}")
        print(f"output={report['artifact_paths']['report']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the CLI**

Run:

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py --output-dir /tmp/rdf_mvp2_learning_proven --harness-output-dir /tmp/rdf_mvp2_harness --mvp1plus-output-dir /tmp/rdf_mvp1plus --clean --refresh-harness --refresh-mvp1plus --pretty
```

Expected:

```text
"learning_proven": true
"proof_eligible": true
```

- [ ] **Step 3: Run focused tests again**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
```

Expected:

```text
8 passed
```

## Task 6: Integrate MVP-2 Final Report Into Proof Audit

**Files:**
- Modify: `scripts/run_mvp1_proof_audit.py`
- Modify: `apps/api/tests/test_mvp1_proof_audit_script.py`

- [ ] **Step 1: Add proof audit tests first**

Append these tests to `apps/api/tests/test_mvp1_proof_audit_script.py`:

```python
def test_proof_audit_summarizes_mvp2_learning_proven_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)
    mvp2_report = tmp_path / "mvp2_learning_proven_report.json"
    write_json(
        mvp2_report,
        {
            "schema_version": "rdf_mvp2_learning_proven_policy_eval_v0.1.0",
            "passed": True,
            "learning_results_measured": True,
            "learning_proven": True,
            "proof_eligible": True,
            "evidence_tier": "local_offline_heldout_policy_eval",
            "validator_evidence_tier": "heldout_policy_eval",
            "baseline_success_rate": 0.4,
            "candidate_success_rate": 0.8,
            "curated_vs_uncurated_uplift": 0.4,
            "proof_source": {"adapter_id": "universal_robots_ur_industrial_arm"},
            "limitations": ["local offline evidence"],
        },
    )

    report = proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
        mvp2_learning_proven_report_path=mvp2_report,
    )

    summary = report["mvp2_learning_proven_policy_eval"]
    assert summary["available"] is True
    assert summary["learning_proven"] is True
    assert summary["proof_eligible"] is True
    assert summary["evidence_tier"] == "local_offline_heldout_policy_eval"
    assert summary["curated_vs_uncurated_uplift"] == 0.4
    assert report["learning_proven_policy_uplift_achieved"] is True
    assert report["summary"]["learning_proven"] is True
    assert report["policy_uplift_required_for_mvp1"] is False


def test_proof_audit_summarizes_mvp2_negative_report_without_mvp1_block(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "real_trajectories"
    build_readiness(output_dir)
    mvp2_report = tmp_path / "mvp2_learning_proven_report.json"
    write_json(
        mvp2_report,
        {
            "schema_version": "rdf_mvp2_learning_proven_policy_eval_v0.1.0",
            "passed": True,
            "learning_results_measured": True,
            "learning_proven": False,
            "proof_eligible": False,
            "evidence_tier": "local_offline_heldout_policy_eval",
            "baseline_success_rate": 0.8,
            "candidate_success_rate": 0.4,
            "curated_vs_uncurated_uplift": -0.4,
            "blockers": ["Curated held-out policy success rate did not exceed baseline."],
        },
    )

    report = proof.build_audit(
        readiness_report_path=output_dir / "readiness_report.json",
        curation_manifest_path=output_dir / "curation_manifest.json",
        split_manifest_path=output_dir / "split_manifest.json",
        dataset_card_path=output_dir / "dataset_card.json",
        hdf5_inspection_path=output_dir / "hdf5_inspection.json",
        trajectory_dir=trajectory_dir,
        learning_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
        output_path=output_dir / "proof_audit.json",
        mvp2_learning_proven_report_path=mvp2_report,
    )

    summary = report["mvp2_learning_proven_policy_eval"]
    assert summary["available"] is True
    assert summary["learning_proven"] is False
    assert summary["negative_or_tie_result_recorded"] is True
    assert report["learning_proven_policy_uplift_achieved"] is False
    assert report["policy_uplift_required_for_mvp1"] is False
```

- [ ] **Step 2: Run proof audit tests and verify red state**

Run:

```bash
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py -q
```

Expected:

```text
TypeError: build_audit() got an unexpected keyword argument 'mvp2_learning_proven_report_path'
```

- [ ] **Step 3: Add audit summary helper**

Add this helper to `scripts/run_mvp1_proof_audit.py` near the existing MVP-2 harness summary helper:

```python
def build_mvp2_learning_proven_summary(report_path: Path | None) -> dict[str, Any]:
    if report_path is None:
        return {
            "available": False,
            "path": None,
            "learning_results_measured": False,
            "learning_proven": False,
            "proof_eligible": False,
            "evidence_tier": None,
            "curated_vs_uncurated_uplift": None,
            "negative_or_tie_result_recorded": False,
            "limitations": ["MVP-2 learning-proven report path was not provided."],
        }
    report = read_json(report_path)
    if report is None:
        return {
            "available": False,
            "path": str(report_path),
            "learning_results_measured": False,
            "learning_proven": False,
            "proof_eligible": False,
            "evidence_tier": None,
            "curated_vs_uncurated_uplift": None,
            "negative_or_tie_result_recorded": False,
            "limitations": ["MVP-2 learning-proven report is missing or invalid JSON."],
        }
    uplift = report.get("curated_vs_uncurated_uplift")
    negative_or_tie = (
        report.get("learning_results_measured") is True
        and report.get("learning_proven") is not True
        and isinstance(uplift, (int, float))
        and uplift <= 0.0
    )
    return {
        "available": True,
        "path": str(report_path),
        "schema_version": report.get("schema_version"),
        "learning_results_measured": report.get("learning_results_measured") is True,
        "learning_proven": report.get("learning_proven") is True,
        "proof_eligible": report.get("proof_eligible") is True,
        "evidence_tier": report.get("evidence_tier"),
        "validator_evidence_tier": report.get("validator_evidence_tier"),
        "baseline_success_rate": report.get("baseline_success_rate"),
        "candidate_success_rate": report.get("candidate_success_rate"),
        "curated_vs_uncurated_uplift": uplift,
        "negative_or_tie_result_recorded": negative_or_tie,
        "adapter_id": (report.get("proof_source") or {}).get("adapter_id")
        if isinstance(report.get("proof_source"), dict)
        else None,
        "limitations": report.get("limitations") if isinstance(report.get("limitations"), list) else [],
        "blockers": report.get("blockers") if isinstance(report.get("blockers"), list) else [],
    }
```

- [ ] **Step 4: Wire the helper into `build_audit()` and CLI**

Change `build_audit()` signature:

```python
def build_audit(
    *,
    readiness_report_path: Path,
    curation_manifest_path: Path,
    split_manifest_path: Path,
    dataset_card_path: Path,
    hdf5_inspection_path: Path,
    trajectory_dir: Path,
    learning_manifest_path: Path,
    output_path: Path | None = None,
    min_live_trajectories: int = 1,
    mvp2_policy_ab_harness_report_path: Path | None = None,
    mvp2_learning_proven_report_path: Path | None = None,
) -> dict[str, Any]:
```

Then build and include:

```python
mvp2_learning_proven = build_mvp2_learning_proven_summary(mvp2_learning_proven_report_path)
combined_learning_proven = mvp2_status["learning_proven"] or mvp2_learning_proven["learning_proven"]
```

Inside the final report dictionary add:

```python
"mvp2_learning_proven_policy_eval": mvp2_learning_proven,
"learning_proven_policy_uplift_achieved": combined_learning_proven,
```

If the existing report dictionary already contains
`"learning_proven_policy_uplift_achieved": mvp2_status["learning_proven"]`,
replace that value with `combined_learning_proven`. Also set
`summary["learning_proven"]` to `combined_learning_proven` and
`summary["do_not_claim_policy_uplift"]` to `not combined_learning_proven`.

Add CLI argument:

```python
parser.add_argument(
    "--mvp2-learning-proven-report",
    type=Path,
    default=ROOT / "storage" / "mvp2_learning_proven_policy_eval" / "mvp2_learning_proven_report.json",
)
```

Pass it into `build_audit()`:

```python
mvp2_learning_proven_report_path=args.mvp2_learning_proven_report,
```

- [ ] **Step 5: Run proof audit tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py -q
```

Expected:

```text
PASS
```

## Task 7: Update Documentation And Handoff

**Files:**
- Modify: `docs/developer/data_schema.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Document the final report schema**

Add a section to `docs/developer/data_schema.md`:

````markdown
## MVP-2 Learning-Proven Report

`storage/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json`는
curated UR file-backed dataset view와 uncurated baseline의 held-out policy A/B
결과를 기록한다.

필수 필드:

- `schema_version`
- `learning_results_measured`
- `learning_proven`
- `proof_eligible`
- `evidence_tier`
- `validator_evidence_tier`
- `baseline_success_rate`
- `candidate_success_rate`
- `curated_vs_uncurated_uplift`
- `proof_source`
- `harness_report_path`
- `baseline_train_hdf5_path`
- `candidate_train_hdf5_path`
- `heldout_suite`
- `harness_heldout_suite`
- `local_offline_heldout_suite_path`
- `rollout_counts`
- `rollout_generation_method`
- `success_label_source`
- `local_offline_evidence`
- `external_rollout_evidence`
- `policy_provenance`
- `no_real_robot_evidence`
- `no_isaac_rollout_evidence`
- `buyer_summary`
- `limitations`
- `non_claims`
- `reproducible_command`

`evidence_tier=local_offline_heldout_policy_eval`은 local offline held-out A/B
증거를 뜻한다. 기존 validator 입력에는 `validator_evidence_tier=heldout_policy_eval`
을 사용해 기존 proof rule을 약화하지 않는다.

`source_kind=schema_only_rollout_ingest_contract`인 rollout JSON은 validator에
`heldout_policy_eval`로 전달하지 않는다. 이 경우 report는 남지만
`validator_evidence_tier=null`, `learning_results_measured=false`,
`learning_proven=false`이다.
````

- [ ] **Step 2: Document the command and failure interpretation**

Add to `docs/developer/debugging_guide.md`:

````markdown
## MVP-2 Learning-Proven Policy Eval

기본 실행:

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty
```

성공 조건:

- `learning_results_measured=true`
- `learning_proven=true`
- `proof_eligible=true`
- `candidate_success_rate > baseline_success_rate`
- `curated_vs_uncurated_uplift > 0`

negative 또는 tie 결과는 script failure가 아니다. 이 경우 report는 남지만
`learning_proven=false`이며 MVP-2는 Closed가 아니다.
````

- [ ] **Step 3: Update worklog, todo, and handoff after verification**

Add a concise entry with:

- What changed.
- Why the validator tier mapping is preserved.
- Which files changed.
- Verification commands and results.
- Remaining MVP-2 gap if the final run is not positive.

## Task 8: Run Required Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run focused MVP-2 wrapper tests**

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 2: Run existing MVP-2 harness tests**

```bash
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 3: Run MVP-1+ embodiment proof tests**

```bash
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 4: Run proof audit and policy validator tests**

```bash
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 5: Run MVP-1 data trust proof tests**

```bash
uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
```

Expected:

```text
PASS
```

- [ ] **Step 6: Run the MVP-2 final proof command**

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty
```

Expected:

```text
"learning_proven": true
"proof_eligible": true
"candidate_success_rate": greater than "baseline_success_rate"
```

- [ ] **Step 7: Run regression proof commands**

```bash
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
```

Expected:

```text
PASS
```

- [ ] **Step 8: Run static checks**

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts apps/api/app apps/api/tests
git diff --check
```

Expected:

```text
PASS
```

## Completion Criteria

- `scripts/run_mvp2_learning_proven_policy_eval.py` exists.
- At least one local offline held-out policy A/B run produces positive curated > uncurated uplift.
- Final report records `learning_proven=true`.
- Final report records `proof_eligible=true`.
- Final report records `evidence_tier=local_offline_heldout_policy_eval`.
- Validator report records `evidence_tier=heldout_policy_eval`.
- Final report distinguishes `heldout_suite` from `harness_heldout_suite` for local offline proof runs.
- Schema-only rollout fixtures are rejected by JSON content markers even when renamed.
- Schema-only rollout fixtures are blocked before a proof-grade validator report is written.
- External rollout metadata is preserved when external rollout result files are supplied.
- Final report exposes `policy_provenance` for validated non-schema rollout results.
- Negative and tie runs are measured non-close reports.
- Schema-only harness fixture cannot close MVP-2.
- MVP-1 proof audit remains learning-ready and does not require policy uplift.
- HMD/OpenXR remains outside the primary proof path.
- No physical robot readiness or real robot success claim is introduced.

## ADR

**Decision:** Build MVP-2 Closed as a wrapper over the existing UR harness, rollout adapter, and policy eval validator.

**Drivers:**

- MVP-2 Closed requires measured positive curated-vs-uncurated policy uplift.
- Existing UR harness already proves lineage, HDF5 export, held-out suite, and rollout ingest shape.
- Existing policy validator already enforces positive uplift.
- The implementation must not weaken validators or introduce real robot runtime.

**Alternatives considered:**

- Use only the existing UR harness report. Rejected because it intentionally records no learning results.
- Modify `run_mvp1c_real_policy_eval.py` to accept a new local evidence tier. Rejected because it expands validator semantics when a wrapper-level classification is enough.
- Build a live UR/RTDE evaluator. Rejected because physical runtime is outside this slice.
- Make policy uplift a new MVP-1 audit blocker. Rejected because MVP-1 remains learning-ready by definition.

**Consequences:**

- The first MVP-2 closure claim is local offline and bounded.
- External evaluator and physical rollout evidence can later reuse the same adapter and validator path.
- Buyer-facing report must state limitations clearly.

**Follow-ups:**

- Add external evaluator result ingestion when a design partner or sim evaluator produces rollout logs.
- Add stronger statistical evidence once rollout counts and scenario variety increase.
- Move to physical UR validation only after readiness and safety gates are explicitly scoped.

## Available Agent Types And Staffing Guidance

- `executor`: implement script, tests, and docs.
- `test-engineer`: review negative/tie/schema-only tests and validator boundaries.
- `architect`: review wrapper composition and claim boundaries.
- `critic`: verify plan consistency, acceptance criteria, and stop conditions.
- `verifier`: run final command suite and summarize evidence.

Recommended execution:

- Use `$ultragoal` as the durable owner for implementation checkpoints.
- Use `$team` only if splitting into parallel lanes: wrapper/tests, audit/docs, verification.
- Use `$ralph` only as an explicit fallback for a single-owner verification loop.

Suggested reasoning:

- Implementation lane: medium.
- Test/verification lane: high.
- Architecture/claim-boundary review: high.

Suggested `$team` launch shape:

```text
team objective: implement MVP-2 learning-proven policy uplift wrapper from docs/superpowers/plans/2026-06-08-mvp2-learning-proven-policy-uplift.md
lanes:
  1. wrapper + focused tests
  2. proof audit + docs
  3. verification + claim-boundary review
```

## Goal-Mode Follow-Up Suggestions

- `$ultragoal`: default next step. Use it to execute this plan as durable checkpoints.
- `$team`: use with `$ultragoal` if parallel implementation would materially speed delivery.
- `$autoresearch-goal`: not recommended for this slice because the implementation target is already specified.
- `$performance-goal`: not applicable because this is not a performance optimization.
- `$ralph`: available only if the user explicitly wants persistent single-owner execution instead of durable goal tracking.
