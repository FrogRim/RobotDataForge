# MVP-2 Rebase UR Policy A/B Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first MVP-2 Rebase slice: a UR file-backed recorded-log policy A/B harness that prepares MVP-2-named dataset/eval artifacts and validates schema-only rollout ingest without claiming policy uplift.

**Architecture:** Add a new `mvp2_*` primary script that reuses the MVP-1+ UR adapter-emitted contract lineage, prepares uncurated/candidate dataset views, exports HDF5, writes a held-out suite and policy eval template, and validates a schema-only rollout ingest fixture. Keep legacy `mvp1c_*` scripts as compatibility surfaces, and add a small proof-audit summary that reads the new harness report without changing MVP-1 pass semantics.

**Tech Stack:** Python 3.11, pytest, existing RDF JSON/HDF5 export helpers, existing MVP-1+ robot embodiment adapter services, existing proof audit script.

---

## File Structure

- Create `scripts/run_mvp2_ur_policy_ab_harness.py`
  - Primary MVP-2 Rebase harness entrypoint.
  - Calls or reads `scripts/run_mvp1plus_embodiment_proof.py` artifacts.
  - Produces `storage/mvp2_policy_ab_harness/` artifacts.
  - Writes `mvp2_policy_ab_harness_report.json`.

- Create `apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py`
  - Focused TDD tests for the new harness script.
  - Verifies claim boundaries, UR lineage, artifact names, schema-only ingest, and proof audit summary.

- Modify `scripts/run_mvp1_proof_audit.py`
  - Add optional `--mvp2-policy-ab-harness-report`.
  - Add `mvp2_policy_ab_harness` summary to the audit report.
  - Do not change MVP-1 required gates.

- Modify `apps/api/tests/test_mvp1_proof_audit_script.py`
  - Add focused coverage proving the new MVP-2 harness summary does not promote MVP-1 or learning-proven status.

- Modify `docs/developer/worklog.md`
  - Record implementation decisions and verification evidence.

- Modify `tasks/todo.md`
  - Add execution checklist updates.

- Modify `Handoff.md`
  - Summarize completed implementation slice after verification.

No DB migration is required.

---

## Task 1: Add Red Tests For MVP-2 UR Harness

**Files:**
- Create: `apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py`
- Read-only reference: `apps/api/tests/test_mvp1plus_embodiment_proof_script.py`
- Read-only reference: `apps/api/tests/test_mvp1c_rollout_result_adapter_script.py`

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
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


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


def test_mvp2_ur_harness_preserves_adapter_emitted_contract_lineage(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    assert report["passed"] is True
    assert report["proof_source"]["adapter_id"] == "universal_robots_ur_industrial_arm"
    assert report["proof_source"]["source_evidence_type"] == "file_backed_recorded_log_fixture"
    assert report["proof_source"]["contract_path"].endswith(
        "universal_robots_ur_industrial_arm_normalized_trajectory_contract.json"
    )
    assert report["proof_source"]["validator_backend"] == "NormalizedTrajectoryContractValidator"
    assert report["claim_boundary"]["policy_uplift_claimed"] is False
    assert report["claim_boundary"]["learning_results_measured"] is False
    assert report["claim_boundary"]["curated_vs_uncurated_uplift"] is None
    assert report["claim_boundary"]["learning_proven"] is False
    assert report["claim_boundary"]["proof_eligible"] is False


def test_mvp2_ur_harness_creates_mvp2_named_dataset_and_eval_artifacts(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    output_dir = tmp_path / "mvp2_policy_ab_harness"

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=output_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    artifact_paths = report["artifact_paths"]
    expected_files = [
        output_dir / "mvp2_policy_ab_harness_report.json",
        output_dir / "mvp2_policy_eval_input_template.json",
        output_dir / "mvp2_heldout_suite_manifest.json",
        output_dir / "baseline_uncurated" / "baseline_uncurated_train.hdf5",
        output_dir / "candidate_curated" / "candidate_curated_train.hdf5",
        output_dir / "rollout_ingest_contract_fixture" / "baseline_rollouts.schema_fixture.json",
        output_dir / "rollout_ingest_contract_fixture" / "candidate_rollouts.schema_fixture.json",
        output_dir / "rollout_ingest_contract_fixture" / "ingest_contract_report.json",
    ]
    for path in expected_files:
        assert path.exists(), str(path)

    assert "mvp1c" not in json.dumps(artifact_paths, sort_keys=True).lower()
    assert read_json(output_dir / "mvp2_heldout_suite_manifest.json")["held_out"] is True
    template = read_json(output_dir / "mvp2_policy_eval_input_template.json")
    assert template["schema_version"] == "rdf_mvp2_policy_eval_input_v0.1.0"
    assert template["baseline"]["dataset_view"] == "baseline_uncurated_recorded_log_harness"
    assert template["candidate"]["dataset_view"] == "candidate_curated_accepted"
    assert template["baseline"]["rollout_results"] == []
    assert template["candidate"]["rollout_results"] == []


def test_mvp2_schema_only_rollout_ingest_is_not_policy_evidence(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    ingest = report["rollout_ingest_contract"]
    assert ingest["passed"] is True
    assert ingest["fixture_kind"] == "schema_only_rollout_ingest_contract"
    assert ingest["proof_eligible"] is False
    assert ingest["learning_results_measured"] is False
    assert ingest["curated_vs_uncurated_uplift"] is None
    assert ingest["baseline_rollout_count"] == 2
    assert ingest["candidate_rollout_count"] == 2
    assert "schema fixture" in " ".join(ingest["limitations"]).lower()


def test_mvp2_harness_cli_writes_report_and_preserves_claim_boundary(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    output_dir = tmp_path / "mvp2_policy_ab_harness"

    exit_code = harness.main(
        [
            "--output-dir",
            str(output_dir),
            "--mvp1plus-output-dir",
            str(tmp_path / "mvp1plus_embodiment_proof"),
            "--refresh-mvp1plus",
            "--clean",
            "--pretty",
        ]
    )

    assert exit_code == 0
    report = read_json(output_dir / "mvp2_policy_ab_harness_report.json")
    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False
```

- [ ] **Step 2: Run the new tests and verify they fail because the script is missing**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
```

Expected:

```text
FileNotFoundError: .../scripts/run_mvp2_ur_policy_ab_harness.py
```

- [ ] **Step 3: Commit the red tests if working in an execution branch**

```bash
git add apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py
git commit -m "Add MVP-2 UR harness contract tests" -m "Constraint: MVP-2 first slice must not claim policy uplift
Rejected: Start from legacy HUD ingest tests | they do not prove adapter-emitted UR lineage
Confidence: high
Scope-risk: narrow
Directive: Keep these tests focused on harness readiness and no-uplift boundaries
Tested: uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
Not-tested: Implementation is intentionally absent in the red step"
```

---

## Task 2: Implement The MVP-2 UR Harness Script

**Files:**
- Create: `scripts/run_mvp2_ur_policy_ab_harness.py`
- Read-only reference: `scripts/run_mvp1plus_embodiment_proof.py`
- Read-only reference: `scripts/export_rdf_to_hdf5.py`
- Read-only reference: `scripts/inspect_rdf_hdf5.py`
- Read-only reference: `scripts/run_mvp1c_rollout_result_adapter.py`

- [ ] **Step 1: Add the new script with constants and IO helpers**

Create `scripts/run_mvp2_ur_policy_ab_harness.py` with this top section:

```python
#!/usr/bin/env python3
"""Build the MVP-2 UR policy A/B harness without claiming policy uplift."""

from __future__ import annotations

import argparse
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

from app.services.normalized_trajectory_contract import NormalizedTrajectoryContractValidator  # noqa: E402
from export_rdf_to_hdf5 import export_hdf5  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402
from run_mvp1c_rollout_result_adapter import build_policy_eval_input  # noqa: E402
from run_mvp1plus_embodiment_proof import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as DEFAULT_MVP1PLUS_OUTPUT_DIR,
    build_mvp1plus_embodiment_proof,
)


SCHEMA_VERSION = "rdf_mvp2_ur_policy_ab_harness_v0.1.0"
POLICY_EVAL_INPUT_SCHEMA_VERSION = "rdf_mvp2_policy_eval_input_v0.1.0"
HELDOUT_SUITE_SCHEMA_VERSION = "rdf_mvp2_heldout_suite_manifest_v0.1.0"
INGEST_CONTRACT_SCHEMA_VERSION = "rdf_mvp2_rollout_ingest_contract_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_policy_ab_harness"
UR_ADAPTER_ID = "universal_robots_ur_industrial_arm"


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
```

- [ ] **Step 2: Add safe output preparation**

Add:

```python
def _is_safe_clean_target(path: Path) -> bool:
    resolved = path.resolve()
    forbidden = {
        ROOT.resolve(),
        ROOT.parent.resolve(),
        Path.home().resolve(),
        Path("/").resolve(),
        (ROOT / "storage").resolve(),
        Path("/tmp").resolve(),
    }
    if resolved in forbidden:
        return False
    return resolved.is_relative_to(ROOT.resolve()) or resolved.is_relative_to(Path("/tmp").resolve())


def _prepare_output_dir(output_dir: Path, *, clean: bool) -> None:
    if clean and output_dir.exists():
        if not _is_safe_clean_target(output_dir):
            raise ValueError(f"refusing to clean unsafe MVP-2 harness output path: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: Add MVP-1+ proof loading and UR adapter extraction**

Add:

```python
def _load_or_refresh_mvp1plus(
    *,
    mvp1plus_output_dir: Path,
    refresh_mvp1plus: bool,
) -> dict[str, Any]:
    proof_path = mvp1plus_output_dir / "mvp1plus_embodiment_proof.json"
    if refresh_mvp1plus or not proof_path.exists():
        return build_mvp1plus_embodiment_proof(mvp1plus_output_dir, clean=refresh_mvp1plus)
    return read_json(proof_path)


def _ur_adapter_proof(mvp1plus_proof: dict[str, Any]) -> dict[str, Any]:
    for proof in mvp1plus_proof.get("adapter_proofs", []):
        if isinstance(proof, dict) and proof.get("adapter_id") == UR_ADAPTER_ID:
            return proof
    raise ValueError(f"MVP-1+ proof does not contain {UR_ADAPTER_ID}")


def _validate_ur_contract(contract_path: Path) -> None:
    contract = read_json(contract_path)
    issues = NormalizedTrajectoryContractValidator().validate_learning_eligibility(contract)
    if issues:
        raise ValueError(f"UR normalized contract failed learning eligibility: {issues}")
```

- [ ] **Step 4: Add dataset view creation**

Add:

```python
def _copy_json(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_view(
    *,
    output_root: Path,
    view_name: str,
    trajectory_paths: list[Path],
    evaluation_paths: list[Path],
) -> dict[str, Any]:
    raw_dir = output_root / view_name / "raw"
    trajectories_dir = raw_dir / "trajectories"
    evaluations_dir = raw_dir / "evaluations"
    for path in trajectory_paths:
        _copy_json(path, trajectories_dir / path.name)
    for path in evaluation_paths:
        _copy_json(path, evaluations_dir / path.name)
    return {
        "view_name": view_name,
        "raw_dir": str(raw_dir),
        "trajectories_dir": str(trajectories_dir),
        "evaluations_dir": str(evaluations_dir),
        "trajectory_count": len(trajectory_paths),
        "evaluation_count": len(evaluation_paths),
    }


def _dataset_views(output_dir: Path, ur_proof: dict[str, Any]) -> dict[str, Any]:
    projected = ur_proof["projected_inputs"]
    accepted_trajectory = Path(projected["accepted_trajectory"])
    accepted_evaluation = Path(projected["accepted_evaluation"])
    rejected_trajectory = Path(projected["rejected_trajectory"])
    rejected_evaluation = Path(projected["rejected_evaluation"])
    baseline = _copy_view(
        output_root=output_dir,
        view_name="baseline_uncurated",
        trajectory_paths=[accepted_trajectory, rejected_trajectory],
        evaluation_paths=[accepted_evaluation, rejected_evaluation],
    )
    candidate = _copy_view(
        output_root=output_dir,
        view_name="candidate_curated",
        trajectory_paths=[accepted_trajectory],
        evaluation_paths=[accepted_evaluation],
    )
    return {"baseline": baseline, "candidate": candidate}
```

- [ ] **Step 5: Add HDF5 export and inspection**

Add:

```python
def _export_view(view: dict[str, Any], output_path: Path, *, include_statuses: set[str]) -> dict[str, Any]:
    result = export_hdf5(
        output_path=output_path,
        trajectories_dir=Path(view["trajectories_dir"]),
        evaluations_dir=Path(view["evaluations_dir"]),
        include_statuses=include_statuses,
    )
    inspection = inspect_hdf5(output_path)
    inspection_path = output_path.with_suffix(".inspection.json")
    write_json(inspection_path, inspection)
    return {
        "hdf5_path": str(output_path),
        "inspection_path": str(inspection_path),
        "episode_ids": result.exported_episode_ids,
        "skipped_by_status": result.skipped_by_status,
        "inspection_clean": inspection.get("issues", []) == [],
        "include_statuses": sorted(include_statuses),
    }
```

- [ ] **Step 6: Add held-out suite and policy eval template writers**

Add:

```python
def _episode_ids_from_export(export: dict[str, Any]) -> list[str]:
    ids = export.get("episode_ids")
    return [str(item) for item in ids] if isinstance(ids, list) else []


def _write_heldout_suite(output_dir: Path, candidate_export: dict[str, Any]) -> dict[str, Any]:
    episode_ids = _episode_ids_from_export(candidate_export)
    manifest = {
        "schema_version": HELDOUT_SUITE_SCHEMA_VERSION,
        "id": "mvp2_ur_policy_ab_schema_only_heldout_suite",
        "held_out": True,
        "task_type": "connector_insertion",
        "scenario_ids": [f"schema_only_scenario_for_{episode_id}" for episode_id in episode_ids],
        "source": "schema_only_harness_template",
        "limitations": [
            "Held-out suite is a harness template, not a proof-grade policy evaluation suite.",
            "Real MVP-2 learning-proven proof requires external held-out rollout results.",
        ],
    }
    write_json(output_dir / "mvp2_heldout_suite_manifest.json", manifest)
    return manifest


def _write_policy_eval_template(
    *,
    output_dir: Path,
    heldout_suite: dict[str, Any],
    baseline_export: dict[str, Any],
    candidate_export: dict[str, Any],
) -> dict[str, Any]:
    template = {
        "schema_version": POLICY_EVAL_INPUT_SCHEMA_VERSION,
        "evidence_tier": "schema_only_rollout_ingest_contract",
        "primary_metric": "policy_success_rate",
        "task_type": heldout_suite["task_type"],
        "eval_suite": {
            "id": heldout_suite["id"],
            "held_out": True,
            "task_type": heldout_suite["task_type"],
            "scenario_ids": heldout_suite["scenario_ids"],
            "heldout_manifest_path": str(output_dir / "mvp2_heldout_suite_manifest.json"),
        },
        "baseline": {
            "name": "baseline_uncurated_recorded_log_harness_policy",
            "dataset_view": "baseline_uncurated_recorded_log_harness",
            "dataset_id": "mvp2_ur_baseline_uncurated_recorded_log_harness",
            "train_hdf5_path": baseline_export["hdf5_path"],
            "train_episode_ids": baseline_export["episode_ids"],
            "policy_class": "schema_only_external_policy",
            "trainer": "schema_only_external_trainer_contract",
            "rollout_results": [],
        },
        "candidate": {
            "name": "candidate_curated_accepted_policy",
            "dataset_view": "candidate_curated_accepted",
            "dataset_id": "mvp2_ur_candidate_curated_accepted",
            "train_hdf5_path": candidate_export["hdf5_path"],
            "train_episode_ids": candidate_export["episode_ids"],
            "policy_class": "schema_only_external_policy",
            "trainer": "schema_only_external_trainer_contract",
            "rollout_results": [],
        },
        "claim_boundary": {
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "proof_eligible": False,
        },
    }
    write_json(output_dir / "mvp2_policy_eval_input_template.json", template)
    return template
```

- [ ] **Step 7: Add schema-only rollout fixture and ingest contract**

Add:

```python
def _write_schema_rollout_fixtures(output_dir: Path, heldout_suite: dict[str, Any]) -> dict[str, Path]:
    fixture_dir = output_dir / "rollout_ingest_contract_fixture"
    scenario_ids = heldout_suite["scenario_ids"] or ["schema_only_scenario"]
    baseline = {
        "fixture_kind": "schema_only_rollout_ingest_contract",
        "rollout_results": [
            {"rollout_id": "baseline_schema_0001", "scenario_id": scenario_ids[0], "success": True},
            {"rollout_id": "baseline_schema_0002", "scenario_id": scenario_ids[0], "success": False},
        ],
    }
    candidate = {
        "fixture_kind": "schema_only_rollout_ingest_contract",
        "rollout_results": [
            {"rollout_id": "candidate_schema_0001", "scenario_id": scenario_ids[0], "success": True},
            {"rollout_id": "candidate_schema_0002", "scenario_id": scenario_ids[0], "success": True},
        ],
    }
    baseline_path = fixture_dir / "baseline_rollouts.schema_fixture.json"
    candidate_path = fixture_dir / "candidate_rollouts.schema_fixture.json"
    write_json(baseline_path, baseline)
    write_json(candidate_path, candidate)
    return {"baseline": baseline_path, "candidate": candidate_path}


def _run_schema_ingest_contract(output_dir: Path, fixture_paths: dict[str, Path]) -> dict[str, Any]:
    report = build_policy_eval_input(
        template_path=output_dir / "mvp2_policy_eval_input_template.json",
        baseline_results_path=fixture_paths["baseline"],
        candidate_results_path=fixture_paths["candidate"],
        output_path=output_dir / "rollout_ingest_contract_fixture" / "mvp2_policy_eval_input.schema_fixture.json",
        baseline_policy_id="schema_only_baseline_policy",
        candidate_policy_id="schema_only_candidate_policy",
        policy_class="schema_only_external_policy",
        trainer="schema_only_external_trainer_contract",
    )
    metadata = report["adapter_metadata"]
    contract = {
        "schema_version": INGEST_CONTRACT_SCHEMA_VERSION,
        "passed": report["passed"],
        "fixture_kind": "schema_only_rollout_ingest_contract",
        "proof_eligible": False,
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "baseline_rollout_count": metadata["baseline_rollout_count"],
        "candidate_rollout_count": metadata["candidate_rollout_count"],
        "policy_eval_input_path": report["output_path"],
        "limitations": [
            "Schema fixture validates rollout ingest shape only.",
            "Schema fixture is not held-out policy evaluation evidence.",
            "Schema fixture must not update the learning manifest.",
        ],
    }
    write_json(output_dir / "rollout_ingest_contract_fixture" / "ingest_contract_report.json", contract)
    return contract
```

- [ ] **Step 8: Add report builder and CLI**

Add:

```python
def _proof_source(ur_proof: dict[str, Any]) -> dict[str, Any]:
    lineage = ur_proof.get("lineage_evidence") if isinstance(ur_proof.get("lineage_evidence"), dict) else {}
    return {
        "adapter_id": UR_ADAPTER_ID,
        "adapter_version": ur_proof.get("adapter_version"),
        "builder_id": ur_proof.get("builder_id"),
        "robot_embodiment": ur_proof.get("robot_embodiment"),
        "source_evidence_type": lineage.get("source_evidence_type"),
        "contract_path": ur_proof.get("normalized_contract_path"),
        "validator_backend": "NormalizedTrajectoryContractValidator",
        "lineage_evidence": lineage,
    }


def build_mvp2_ur_policy_ab_harness(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    mvp1plus_output_dir: Path = DEFAULT_MVP1PLUS_OUTPUT_DIR,
    clean: bool = False,
    refresh_mvp1plus: bool = False,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    mvp1plus = _load_or_refresh_mvp1plus(
        mvp1plus_output_dir=mvp1plus_output_dir,
        refresh_mvp1plus=refresh_mvp1plus,
    )
    ur_proof = _ur_adapter_proof(mvp1plus)
    contract_path = Path(ur_proof["normalized_contract_path"])
    _validate_ur_contract(contract_path)

    views = _dataset_views(output_dir, ur_proof)
    baseline_export = _export_view(
        views["baseline"],
        output_dir / "baseline_uncurated" / "baseline_uncurated_train.hdf5",
        include_statuses={"success", "failure"},
    )
    candidate_export = _export_view(
        views["candidate"],
        output_dir / "candidate_curated" / "candidate_curated_train.hdf5",
        include_statuses={"success"},
    )
    heldout_suite = _write_heldout_suite(output_dir, candidate_export)
    template = _write_policy_eval_template(
        output_dir=output_dir,
        heldout_suite=heldout_suite,
        baseline_export=baseline_export,
        candidate_export=candidate_export,
    )
    fixtures = _write_schema_rollout_fixtures(output_dir, heldout_suite)
    ingest_contract = _run_schema_ingest_contract(output_dir, fixtures)

    claim_boundary = {
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "learning_proven": False,
        "proof_eligible": False,
        "policy_uplift_claimed": False,
        "real_robot_success_claimed": False,
        "physical_robot_readiness_claimed": False,
        "hmd_readiness_claimed": False,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": True,
        "harness_ready": True,
        "rollout_ingest_contract_ready": ingest_contract["passed"],
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "learning_proven": False,
        "proof_eligible": False,
        "proof_source": _proof_source(ur_proof),
        "dataset_views": views,
        "exports": {"baseline": baseline_export, "candidate": candidate_export},
        "heldout_suite": heldout_suite,
        "policy_eval_input_template": template,
        "rollout_ingest_contract": ingest_contract,
        "claim_boundary": claim_boundary,
        "artifact_paths": {
            "report": str(output_dir / "mvp2_policy_ab_harness_report.json"),
            "policy_eval_input_template": str(output_dir / "mvp2_policy_eval_input_template.json"),
            "heldout_suite_manifest": str(output_dir / "mvp2_heldout_suite_manifest.json"),
            "baseline_hdf5": baseline_export["hdf5_path"],
            "candidate_hdf5": candidate_export["hdf5_path"],
            "ingest_contract_report": str(output_dir / "rollout_ingest_contract_fixture" / "ingest_contract_report.json"),
        },
        "limitations": [
            "This is a policy A/B harness readiness artifact, not policy uplift evidence.",
            "The rollout ingest fixture is schema-only.",
            "The UR source is file-backed recorded-log fixture evidence, not physical UR readiness.",
        ],
    }
    write_json(output_dir / "mvp2_policy_ab_harness_report.json", report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mvp1plus-output-dir", type=Path, default=DEFAULT_MVP1PLUS_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--refresh-mvp1plus", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_mvp2_ur_policy_ab_harness(
        output_dir=args.output_dir,
        mvp1plus_output_dir=args.mvp1plus_output_dir,
        clean=args.clean,
        refresh_mvp1plus=args.refresh_mvp1plus,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        print("RDF MVP-2 UR policy A/B harness: PASS")
        print(f"harness_ready={report['harness_ready']}")
        print(f"rollout_ingest_contract_ready={report['rollout_ingest_contract_ready']}")
        print(f"learning_results_measured={report['learning_results_measured']}")
        print(f"learning_proven={report['learning_proven']}")
        print(f"output={args.output_dir}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 9: Run the new tests and fix mechanical issues**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
```

Expected after implementation:

```text
4 passed
```

- [ ] **Step 10: Commit the new script**

```bash
git add scripts/run_mvp2_ur_policy_ab_harness.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py
git commit -m "Build MVP-2 UR policy A/B harness boundary" -m "Constraint: Harness readiness must not become learning-proven policy evidence
Rejected: Rename legacy mvp1c scripts | compatibility would be riskier than adding a new primary mvp2 surface
Confidence: medium
Scope-risk: moderate
Directive: Treat schema-only rollout fixtures as ingest-contract evidence only
Tested: uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
Not-tested: Real trainer rollout, live UR runtime, policy uplift"
```

---

## Task 3: Add Proof Audit MVP-2 Harness Summary

**Files:**
- Modify: `scripts/run_mvp1_proof_audit.py`
- Modify: `apps/api/tests/test_mvp1_proof_audit_script.py`

- [ ] **Step 1: Add a failing proof-audit test**

Append to `apps/api/tests/test_mvp1_proof_audit_script.py`:

```python
def test_proof_audit_summarizes_mvp2_harness_without_learning_proven_claim(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    trajectory_dir = tmp_path / "trajectories"
    prepare_mvp1b_fixture(output_dir, trajectory_dir)
    harness_report = tmp_path / "mvp2_policy_ab_harness_report.json"
    write_json(
        harness_report,
        {
            "schema_version": "rdf_mvp2_ur_policy_ab_harness_v0.1.0",
            "passed": True,
            "harness_ready": True,
            "rollout_ingest_contract_ready": True,
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "learning_proven": False,
            "proof_eligible": False,
            "artifact_paths": {
                "report": str(harness_report),
            },
            "proof_source": {
                "adapter_id": "universal_robots_ur_industrial_arm",
            },
        },
    )

    report = audit(
        output_dir,
        trajectory_dir,
        mvp2_policy_ab_harness_report_path=harness_report,
    )

    harness = report["mvp2_policy_ab_harness"]
    assert harness["harness_ready"] is True
    assert harness["rollout_ingest_contract_ready"] is True
    assert harness["learning_results_measured"] is False
    assert harness["curated_vs_uncurated_uplift"] is None
    assert harness["learning_proven"] is False
    assert harness["proof_eligible"] is False
    assert report["summary"]["learning_ready"] is True
    assert report["summary"]["learning_proven"] is False
    assert report["policy_uplift_required_for_mvp1"] is False
```

If the local `audit()` helper in this test file does not accept `mvp2_policy_ab_harness_report_path`, update that helper to pass the new keyword through to `build_audit()`.

- [ ] **Step 2: Run the focused proof-audit test and verify it fails**

Run:

```bash
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py::test_proof_audit_summarizes_mvp2_harness_without_learning_proven_claim -q
```

Expected:

```text
TypeError: build_audit() got an unexpected keyword argument 'mvp2_policy_ab_harness_report_path'
```

- [ ] **Step 3: Add proof-audit helper**

In `scripts/run_mvp1_proof_audit.py`, add this helper near the MVP-2 policy status helpers:

```python
def build_mvp2_policy_ab_harness_summary(report_path: Path | None) -> dict[str, Any]:
    if report_path is None:
        return {
            "present": False,
            "harness_ready": False,
            "rollout_ingest_contract_ready": False,
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "learning_proven": False,
            "proof_eligible": False,
            "primary_report_path": None,
            "adapter_id": None,
        }
    report = read_json(report_path)
    if report is None:
        return {
            "present": False,
            "harness_ready": False,
            "rollout_ingest_contract_ready": False,
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "learning_proven": False,
            "proof_eligible": False,
            "primary_report_path": str(report_path),
            "adapter_id": None,
            "issues": ["MVP-2 policy A/B harness report is missing or invalid JSON"],
        }
    source = report.get("proof_source") if isinstance(report.get("proof_source"), dict) else {}
    return {
        "present": True,
        "harness_ready": report.get("harness_ready") is True,
        "rollout_ingest_contract_ready": report.get("rollout_ingest_contract_ready") is True,
        "learning_results_measured": report.get("learning_results_measured") is True,
        "curated_vs_uncurated_uplift": report.get("curated_vs_uncurated_uplift"),
        "learning_proven": report.get("learning_proven") is True,
        "proof_eligible": report.get("proof_eligible") is True,
        "primary_report_path": str(report_path),
        "adapter_id": source.get("adapter_id"),
    }
```

- [ ] **Step 4: Extend `build_audit()` signature and report**

Add the keyword:

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
) -> dict[str, Any]:
```

Inside `build_audit()`, after `mvp2_status = build_mvp2_policy_uplift_status(...)`, add:

```python
mvp2_harness = build_mvp2_policy_ab_harness_summary(mvp2_policy_ab_harness_report_path)
```

In the final report dict, add:

```python
"mvp2_policy_ab_harness": mvp2_harness,
```

Do not change `status`, `required_gate_count`, or `policy_uplift_required_for_mvp1`.

- [ ] **Step 5: Add CLI argument**

In `parse_args()`, add:

```python
parser.add_argument(
    "--mvp2-policy-ab-harness-report",
    type=Path,
    default=ROOT / "storage" / "mvp2_policy_ab_harness" / "mvp2_policy_ab_harness_report.json",
)
```

In `main()`, pass:

```python
mvp2_policy_ab_harness_report_path=args.mvp2_policy_ab_harness_report,
```

- [ ] **Step 6: Run focused proof-audit tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py -q
```

Expected:

```text
all tests in test_mvp1_proof_audit_script.py pass
```

- [ ] **Step 7: Commit proof-audit summary work**

```bash
git add scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp1_proof_audit_script.py
git commit -m "Expose MVP-2 harness readiness in proof audit" -m "Constraint: MVP-1 audit must not make policy uplift required
Rejected: Fold harness readiness into MVP-1 required gates | it would blur learning-ready and learning-proven boundaries
Confidence: high
Scope-risk: narrow
Directive: Keep mvp2_policy_ab_harness informational until real held-out results are ingested
Tested: uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py -q
Not-tested: Real MVP-2 rollout"
```

---

## Task 4: Run End-To-End Harness Verification

**Files:**
- Execute: `scripts/run_mvp2_ur_policy_ab_harness.py`
- Execute: `scripts/run_mvp1_proof_audit.py`

- [ ] **Step 1: Run the new harness command**

Run:

```bash
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
```

Expected key fields in printed JSON:

```text
"passed": true
"harness_ready": true
"rollout_ingest_contract_ready": true
"learning_results_measured": false
"curated_vs_uncurated_uplift": null
"learning_proven": false
"proof_eligible": false
```

- [ ] **Step 2: Check artifact paths**

Run:

```bash
test -f storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json
test -f storage/mvp2_policy_ab_harness/mvp2_policy_eval_input_template.json
test -f storage/mvp2_policy_ab_harness/mvp2_heldout_suite_manifest.json
test -f storage/mvp2_policy_ab_harness/baseline_uncurated/baseline_uncurated_train.hdf5
test -f storage/mvp2_policy_ab_harness/candidate_curated/candidate_curated_train.hdf5
test -f storage/mvp2_policy_ab_harness/rollout_ingest_contract_fixture/ingest_contract_report.json
```

Expected:

```text
exit code 0
```

- [ ] **Step 3: Run proof audit with the harness report**

Run:

```bash
uv run python scripts/run_mvp1_proof_audit.py \
  --mvp2-policy-ab-harness-report storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json \
  --pretty
```

Expected:

```text
"status": "pass"
"policy_uplift_required_for_mvp1": false
"mvp2_policy_ab_harness": {
  "harness_ready": true,
  "rollout_ingest_contract_ready": true,
  "learning_results_measured": false,
  "learning_proven": false,
  "proof_eligible": false
}
```

- [ ] **Step 4: Verify no accidental HMD primary language in MVP-2 harness artifacts**

Run:

```bash
rg -n "fresh HUD|Quest/OpenXR/HMD.*primary|HMD live trajectory|Gate A collection readiness" storage/mvp2_policy_ab_harness scripts/run_mvp2_ur_policy_ab_harness.py
```

Expected:

```text
no matches
```

---

## Task 5: Regression, Lint, Docs

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Run focused and compatibility tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
uv run pytest apps/api/tests/test_mvp1c_headless_eval_bundle_script.py apps/api/tests/test_mvp1c_rollout_result_adapter_script.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run proof scripts**

Run:

```bash
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
```

Expected:

```text
all commands exit 0
```

- [ ] **Step 3: Run static checks**

Run:

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py
git diff --check
```

Expected:

```text
compileall exits 0
ruff exits 0
git diff --check exits 0
```

- [ ] **Step 4: Update docs**

Append a worklog section with:

```markdown
## 2026-06-08 - MVP-2 UR policy A/B harness implementation

### 작업 내용

- `scripts/run_mvp2_ur_policy_ab_harness.py`를 추가해 UR file-backed recorded-log lineage에서 MVP-2 policy A/B harness artifact를 생성했다.
- schema-only rollout ingest fixture를 검증하되 policy uplift evidence로 해석하지 않도록 `proof_eligible=false`를 유지했다.
- `run_mvp1_proof_audit.py`에 MVP-2 harness readiness summary를 추가했다.

### 판단 이유

- MVP-2는 새 adapter-emitted contract lineage에서 시작해야 하며, legacy HMD/HUD ingest path를 primary로 사용하면 안 된다.
- 이번 slice는 learning-proven proof가 아니라 policy A/B harness readiness proof다.

### 변경 파일

- `scripts/run_mvp2_ur_policy_ab_harness.py`
- `scripts/run_mvp1_proof_audit.py`
- `apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py`
- `apps/api/tests/test_mvp1_proof_audit_script.py`
- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

### 실행한 검증 명령과 결과

- `uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q`: pass count와 실패 없는 종료 상태를 기록한다.
- `uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q`: pass count와 실패 없는 종료 상태를 기록한다.
- `uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q`: pass count와 실패 없는 종료 상태를 기록한다.
- `uv run pytest apps/api/tests/test_mvp1c_headless_eval_bundle_script.py apps/api/tests/test_mvp1c_rollout_result_adapter_script.py -q`: pass count와 실패 없는 종료 상태를 기록한다.
- `uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty`: `passed=true`, output directory, 주요 artifact path를 기록한다.
- `uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty`: `passed=true`, adapter count, accepted/rejected count를 기록한다.
- `uv run python scripts/run_data_trust_layer_proof.py --clean --pretty`: `passed=true`를 기록한다.
- `uv run python -m compileall -q scripts apps/api/app apps/api/tests`: 종료 코드 0을 기록한다.
- `uvx ruff check scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py`: `All checks passed!`를 기록한다.
- `git diff --check`: 출력 없음과 종료 코드 0을 기록한다.

### 남은 gap 또는 다음 작업

- 실제 policy uplift는 측정하지 않았다.
- 실제 held-out rollout 결과와 trainer/policy class 선택은 다음 MVP-2 slice다.
- live UR/RTDE runtime, physical robot readiness, HMD readiness는 주장하지 않는다.
```

Update `tasks/todo.md` by marking the MVP-2 harness implementation checklist complete and update `Handoff.md` with the new command and output directory.

- [ ] **Step 5: Commit docs and final implementation state**

```bash
git add scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py docs/developer/worklog.md tasks/todo.md Handoff.md
git commit -m "Prove MVP-2 harness readiness from UR contract lineage" -m "Constraint: MVP-2 Rebase first slice is harness-ready only, not learning-proven
Rejected: Claim uplift from schema-only rollout fixtures | fixtures validate ingest shape only
Confidence: high
Scope-risk: moderate
Directive: Require real held-out rollout input before setting learning_results_measured=true
Tested: uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q; uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q; uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q; uv run pytest apps/api/tests/test_mvp1c_headless_eval_bundle_script.py apps/api/tests/test_mvp1c_rollout_result_adapter_script.py -q; uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty; uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty; uv run python scripts/run_data_trust_layer_proof.py --clean --pretty; uv run python -m compileall -q scripts apps/api/app apps/api/tests; uvx ruff check scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py; git diff --check
Not-tested: Real policy training, real held-out rollout, live UR runtime"
```

---

## Self-Review

Spec coverage:

- UR file-backed recorded log as first source: Task 2 extracts `universal_robots_ur_industrial_arm`.
- `mvp2_*` primary surfaces: Task 2 creates `run_mvp2_ur_policy_ab_harness.py` and `mvp2_*` artifacts.
- Legacy `mvp1c_*` compatibility: Task 2 reuses stable functions without deleting old scripts; Task 5 runs compatibility tests.
- Schema-only ingest fixture: Task 2 writes schema fixture and sets `proof_eligible=false`; Task 1 tests it.
- Proof audit summary: Task 3 adds informational summary without changing MVP-1 gates.
- No policy uplift claim: Tasks 1-5 enforce false/null claim boundary.
- HMD isolation: Task 4 searches for accidental HMD primary wording in new artifacts.

Placeholder scan:

- The plan intentionally uses concrete file paths, function names, constants, and expected command outputs.
- No plan step requires unspecified implementation behavior.

Type consistency:

- `build_mvp2_ur_policy_ab_harness()` returns the same keys tested in Task 1.
- `build_mvp2_policy_ab_harness_summary()` returns the same keys added to proof audit in Task 3.
- CLI `main(argv: list[str] | None = None)` supports direct test invocation and normal script execution.
