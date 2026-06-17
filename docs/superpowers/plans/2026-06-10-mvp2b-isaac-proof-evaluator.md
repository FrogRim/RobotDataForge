# MVP-2B Isaac Proof Evaluator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated Isaac connector insertion proof evaluator that can close MVP-2 only when curated data beats uncurated data on pre-registered held-out policy rollouts.

**Architecture:** Add a new MVP-2B runner that owns scenario manifest generation, Isaac-domain trajectory generation, curation/export, NumPy phase-conditioned BC training, held-out rollout evaluation, proof-grade rollout JSON writing, visual evidence, and final proof ingest through the existing MVP-2 validator. Keep existing Isaac smoke and local proxy scripts as non-proof support tools.

**Tech Stack:** Python 3.11+, NumPy, pytest, existing RDF services, existing HDF5 export helpers, existing MVP-2 proof evaluator, IsaacLab runtime only for the runtime proof attempt, no DB migration, no new production dependency.

---

## Supersedes

This plan supersedes:

```text
docs/superpowers/plans/2026-06-10-mvp2b-proof-grade-evaluator-bridge.md
```

The older plan centered on a bridge over the existing Isaac smoke path. This
plan follows the approved design spec and centers on a dedicated Isaac connector
insertion proof evaluator.

Spec source:

```text
docs/superpowers/specs/2026-06-10-mvp2b-isaac-proof-evaluator-design.md
```

## File Structure

- Create `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Owns MVP-2B scenario manifest, deterministic evaluator math, generated
    trajectory material, phase-conditioned BC training, held-out evaluation,
    proof JSON emission, visual evidence, and top-level report.

- Create `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Focused tests for manifest, leakage guard, metric logic, taxonomy, contract
    validation, train view parity, proof JSON, closure authority, and boundary
    behavior.

- Modify `docs/developer/debugging_guide.md`
  - Add the MVP-2B commands, Isaac preflight notes, and interpretation rules for
    `mvp2_closed`.

- Modify `docs/developer/worklog.md`
  - Record implementation and verification evidence.

- Modify `tasks/todo.md`
  - Track MVP-2B execution steps and final status.

- Modify `Handoff.md`
  - Preserve compact next-session state.

No DB migration is planned.

## RALPLAN-DR Summary

### Principles

- MVP-2 closes only on proof-grade held-out policy uplift.
- Scenario split and success thresholds are fixed before training/evaluation.
- Baseline/candidate fairness is stricter than policy performance.
- Existing proof validator remains closure authority, but final closure also
  requires the dedicated Isaac runtime gate.
- Smoke, proxy, and visual evidence explain the run but cannot override JSON
  proof gates.

### Decision Drivers

1. Existing Isaac smoke uses `linear_bc_numpy_isaac_smoke` and is not the
   selected MVP-2 policy/trainer.
2. Current local phase-conditioned proxy is useful for readiness but is blocked
   from proof promotion.
3. The user chose dedicated Isaac evaluator scope because it gives stronger
   proof and actual visual evidence.

### Viable Options

| Option | Pros | Cons | Decision |
|---|---|---|---|
| Dedicated Isaac connector insertion proof evaluator | Strongest MVP-2 proof boundary, actual visual evidence, clear manifest leak guard | More setup and runtime risk | Chosen |
| Promote existing Isaac smoke runner | Faster, lower code volume | Uses wrong policy class and smoke-only evidence tier | Rejected |
| Continue local proxy hardening | Stable local tests | Cannot close MVP-2 honestly | Rejected |
| Manual external JSON ingestion only | Minimal engineering | Does not create the desired Isaac proof path or visual evidence | Rejected |

### Pre-Mortem

1. Isaac runtime is unavailable or incompatible.
   - Mitigation: keep deterministic non-Isaac tests for manifest, metric,
     curation, trainer, and proof JSON; runtime failure keeps MVP-2 open.
2. Candidate does not beat baseline on held-out scenarios.
   - Mitigation: report honest non-closure with artifacts; do not retune
     thresholds after held-out inspection.
3. Held-out leakage enters training or hyperparameter selection.
   - Mitigation: implement a manifest-based leakage guard and test it before
     any training/eval step.

## ADR: Dedicated Isaac Runtime Gate For MVP-2 Closure

**Decision:** MVP-2B uses a dedicated Isaac connector insertion evaluator and
requires both the existing MVP-2 proof evaluator and the Isaac runtime gate to
pass before setting `mvp2_closed=true`.

**Drivers:**

- MVP-2 is learning-proven value proof, not learning-ready artifact proof.
- Current local proxy and smoke paths are useful but cannot close MVP-2.
- The user wants actual Isaac-derived proof evidence and visual artifacts.

**Alternatives considered:**

- Promote existing Isaac smoke runner: rejected because it is smoke-only and
  uses `linear_bc_numpy_isaac_smoke`.
- Continue phase-conditioned local proxy: rejected because it is circular with
  local task-state scoring.
- Manual external JSON only: rejected because it does not build the dedicated
  evaluator path.

**Consequences:**

- Implementation is heavier than a bridge-only slice.
- Runtime failure is a valid non-closure outcome.
- Deterministic backend remains valuable for tests but is permanently
  non-closing.

**Follow-ups:**

- After MVP-2B closure, strengthen statistical evidence with bootstrap CI lower
  bound > 0.
- Keep real robot validation out of MVP-2B and plan it separately after Isaac
  proof succeeds.

## Task 1: Add Red Tests For Scenario Manifest And Leak Guard

**Files:**
- Create: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Create later: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing manifest tests**

Add these tests:

```python
from pathlib import Path

from conftest import load_script


def test_mvp2b_scenario_manifest_is_pre_registered_and_hashed(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    assert manifest["manifest_version"] == "rdf_mvp2b_scenario_manifest_v0.1.0"
    assert manifest["success_metric"]["insertion_depth_m_min"] == 0.03
    assert manifest["success_metric"]["lateral_error_m_max"] == 0.006
    assert manifest["success_metric"]["orientation_error_deg_max"] == 8.0
    assert manifest["success_metric"]["stable_steps_required"] == 10
    assert manifest["success_metric"]["max_steps"] == 150
    assert manifest["manifest_sha256"]
    assert (tmp_path / "mvp2b" / "scenario_manifest.json").exists()


def test_mvp2b_scenario_manifest_has_disjoint_splits(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }
    assert split_to_seeds["held_out"] == set(range(3000, 3020))
    for left_name, left_seeds in split_to_seeds.items():
        for right_name, right_seeds in split_to_seeds.items():
            if left_name != right_name:
                assert left_seeds.isdisjoint(right_seeds)


def test_mvp2b_leak_guard_rejects_heldout_training_use(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")
    heldout_id = next(row["scenario_id"] for row in manifest["scenarios"] if row["split"] == "held_out")

    leakage_report = script.validate_no_heldout_leakage(
        manifest=manifest,
        training_scenario_ids=["train_success_1000", heldout_id],
        curation_tuning_scenario_ids=[],
        threshold_tuning_scenario_ids=[],
        hyperparameter_scenario_ids=[],
    )

    assert leakage_report["passed"] is False
    assert heldout_id in leakage_report["leaked_scenario_ids"]


def test_mvp2b_threshold_freeze_requires_new_manifest_version(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")
    changed_metric = dict(manifest["success_metric"])
    changed_metric["lateral_error_m_max"] = 0.008

    freeze_report = script.validate_threshold_freeze(
        original_manifest=manifest,
        proposed_success_metric=changed_metric,
        proposed_manifest_version=manifest["manifest_version"],
    )

    assert freeze_report["passed"] is False
    assert freeze_report["requires_new_manifest_version"] is True
```

- [ ] **Step 2: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: fails because `run_mvp2b_isaac_proof_evaluator.py` does not exist.

## Task 2: Implement Scenario Manifest And Leak Guard

**Files:**
- Create: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Test: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add constants and JSON helpers**

Implement these public constants:

```python
SCHEMA_VERSION = "rdf_mvp2b_isaac_proof_evaluator_v0.1.0"
SCENARIO_MANIFEST_VERSION = "rdf_mvp2b_scenario_manifest_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2b_isaac_proof_evaluator"
POLICY_CLASS = "phase_conditioned_numpy_bc_policy_v0"
TRAINER = "rdf_numpy_phase_conditioned_bc_trainer_v0"
PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")
CONTROLLED_FAILURE_REASONS = (
    "LATERAL_OFFSET_FAILURE",
    "UNDER_INSERTION_FAILURE",
    "ORIENTATION_MISALIGNMENT_FAILURE",
    "ACTION_JITTER_FAILURE",
    "EARLY_STOP_FAILURE",
)
```

Implement `stable_json()`, `write_json()`, and `_sha256_payload()` using sorted
JSON serialization.

- [ ] **Step 2: Implement `build_scenario_manifest()`**

The function must create deterministic scenarios for:

```text
train_success: 1000-1039
train_failure: 1100-1139
calibration: 2000-2009
held_out: 3000-3019
```

Each row must include:

```text
scenario_id
split
seed
initial_offset_m
orientation_offset_deg
noise_level
max_steps
```

Write the manifest to `scenario_manifest.json`.

- [ ] **Step 3: Implement `validate_no_heldout_leakage()`**

Inputs:

```python
def validate_no_heldout_leakage(
    *,
    manifest: dict[str, Any],
    training_scenario_ids: list[str],
    curation_tuning_scenario_ids: list[str],
    threshold_tuning_scenario_ids: list[str],
    hyperparameter_scenario_ids: list[str],
) -> dict[str, Any]:
```

Return:

```python
{
    "passed": bool,
    "heldout_scenario_ids": list[str],
    "leaked_scenario_ids": list[str],
    "checked_channels": {
        "training": list[str],
        "curation_tuning": list[str],
        "threshold_tuning": list[str],
        "hyperparameter_selection": list[str],
    },
}
```

- [ ] **Step 4: Implement `validate_threshold_freeze()`**

Inputs:

```python
def validate_threshold_freeze(
    *,
    original_manifest: dict[str, Any],
    proposed_success_metric: dict[str, Any],
    proposed_manifest_version: str,
) -> dict[str, Any]:
```

If success metrics change while the manifest version is unchanged, return:

```python
{
    "passed": False,
    "requires_new_manifest_version": True,
    "changed_fields": list[str],
}
```

- [ ] **Step 5: Run GREEN**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: manifest tests pass.

## Task 3: Add Success Metric Tests And Evaluator Math

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing metric tests**

Add:

```python
def test_mvp2b_success_requires_geometry_and_stability() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    trace = [
        {
            "step": index,
            "insertion_depth_m": 0.031,
            "lateral_error_m": 0.004,
            "orientation_error_deg": 5.0,
        }
        for index in range(12)
    ]

    result = script.evaluate_rollout_trace(trace)

    assert result["success"] is True
    assert result["stable_steps_observed"] >= 10
    assert result["failure_reason"] == ""


def test_mvp2b_success_fails_without_consecutive_stable_steps() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    trace = []
    for index in range(12):
        trace.append(
            {
                "step": index,
                "insertion_depth_m": 0.031,
                "lateral_error_m": 0.004 if index != 9 else 0.009,
                "orientation_error_deg": 5.0,
            }
        )

    result = script.evaluate_rollout_trace(trace)

    assert result["success"] is False
    assert result["failure_reason"] == "STABILITY_WINDOW_NOT_REACHED"
```

- [ ] **Step 2: Implement `evaluate_rollout_trace()`**

The function must count consecutive passing metric rows and return a summary
with:

```text
success
failure_reason
steps
stable_steps_observed
max_insertion_depth_m
min_lateral_error_m
min_orientation_error_deg
```

- [ ] **Step 3: Run metric tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: manifest and metric tests pass.

## Task 4: Generate Scripted Expert And Controlled Failure Trajectories

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing trajectory generation tests**

Add:

```python
def test_mvp2b_controlled_failure_taxonomy_covers_rejection_reasons(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    bundle = script.generate_training_trajectory_bundle(
        manifest=manifest,
        output_dir=tmp_path / "mvp2b",
    )

    rejected_reasons = {
        item["rejection_reason"]
        for item in bundle["curation_manifest"]["items"]
        if item["accepted"] is False
    }
    assert rejected_reasons == set(script.CONTROLLED_FAILURE_REASONS)


def test_mvp2b_generated_trajectory_contracts_pass_validator(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")

    bundle = script.generate_training_trajectory_bundle(
        manifest=manifest,
        output_dir=tmp_path / "mvp2b",
    )

    assert bundle["contract_validation"]["passed"] is True
    assert bundle["accepted_count"] > 0
    assert bundle["rejected_count"] > 0
```

- [ ] **Step 2: Implement deterministic trajectory rows**

For each train scenario, generate a compact list of step records with:

```text
timestamp_s
phase
eef_position_m
target_position_m
lateral_error_m
insertion_depth_m
orientation_error_deg
normalized_action
```

Accepted train scenarios use scripted expert traces. Rejected train scenarios
cycle through the five controlled failure reasons.

- [ ] **Step 3: Emit normalized trajectory contract payloads**

Use the existing `NormalizedTrajectoryContractValidator` from
`app.services.normalized_trajectory_contract`. The generated contract must
include source provenance, input route, robot embodiment, action semantics,
state metadata, replay/consistency evidence, curation evidence, limitations,
and schema version.

- [ ] **Step 4: Write curation manifest**

Write:

```text
train_raw_trajectories/
curation_manifest.json
normalized_trajectory_contracts/
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: taxonomy and contract validation tests pass.

## Task 5: Export Baseline And Candidate HDF5 Train Views

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing export test**

Add:

```python
def test_mvp2b_curation_outputs_baseline_and_candidate_train_views(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    assert Path(report["artifact_paths"]["baseline_uncurated_train_hdf5"]).exists()
    assert Path(report["artifact_paths"]["candidate_curated_train_hdf5"]).exists()
    assert report["training_views"]["baseline"]["includes_rejected_material"] is True
    assert report["training_views"]["candidate"]["includes_rejected_material"] is False
    assert report["training_views"]["candidate"]["accepted_count"] > 0
```

- [ ] **Step 2: Implement train view writer**

Write two HDF5 files under:

```text
baseline_uncurated_train.hdf5
candidate_curated_train.hdf5
```

Use existing HDF5 helper patterns from `scripts/export_rdf_to_hdf5.py` where
that fits the current data shape. If the generated evaluator-domain table is
too direct for the existing exporter, write a small local HDF5 writer inside the
MVP-2B script and keep metadata fields explicit.

- [ ] **Step 3: Inspect train views in the report**

Record for each view:

```text
trajectory_count
transition_count
accepted_count
rejected_count
includes_rejected_material
feature_schema
phase_schema
```

- [ ] **Step 4: Run focused test**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_mvp2b_curation_outputs_baseline_and_candidate_train_views -q
```

Expected: pass.

## Task 6: Train NumPy Phase-Conditioned BC Policies With Fair A/B Parity

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing parity tests**

Add:

```python
def test_mvp2b_phase_conditioned_bc_uses_identical_feature_schema(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    baseline = report["policy_artifacts"]["baseline"]
    candidate = report["policy_artifacts"]["candidate"]
    assert baseline["policy_class"] == "phase_conditioned_numpy_bc_policy_v0"
    assert candidate["policy_class"] == baseline["policy_class"]
    assert candidate["trainer"] == baseline["trainer"]
    assert candidate["feature_schema"] == baseline["feature_schema"]
    assert candidate["phase_schema"] == baseline["phase_schema"]
    assert candidate["hyperparameters"] == baseline["hyperparameters"]
```

- [ ] **Step 2: Implement feature extraction**

Implement:

```python
def featurize_step(step: dict[str, Any], *, previous_action: list[float]) -> tuple[np.ndarray, np.ndarray]:
```

The input feature vector includes phase one-hot, task geometry, and action
history summary. The target is current normalized action.

- [ ] **Step 3: Implement ridge-style BC fitting**

Implement a deterministic NumPy trainer:

```python
def fit_phase_conditioned_bc_policy(
    *,
    policy_id: str,
    train_rows: list[dict[str, Any]],
    hyperparameters: dict[str, Any],
) -> dict[str, Any]:
```

The artifact stores weights, bias, schema, train view id, and metadata. Use the
same hyperparameters for baseline and candidate.

- [ ] **Step 4: Write policy artifact JSON files**

Write:

```text
baseline_policy_artifact.json
candidate_policy_artifact.json
```

- [ ] **Step 5: Run parity tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: policy parity tests pass.

## Task 7: Implement Held-Out Evaluation Backend Boundary And Proof JSON Writer

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing proof JSON tests**

Add:

```python
def test_mvp2b_external_rollout_json_has_required_validator_metadata(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        min_rollouts_per_policy=20,
    )

    baseline = script.read_json(Path(report["artifact_paths"]["baseline_external_rollouts"]))
    candidate = script.read_json(Path(report["artifact_paths"]["candidate_external_rollouts"]))
    assert baseline["source_kind"] == "external_heldout_policy_eval"
    assert candidate["proof_role"] == "external_trainer_policy_eval"
    assert baseline["heldout_suite"]["source_kind"] == "external_trainer_eval_suite"
    assert candidate["heldout_suite"]["proof_role"] == "external_policy_eval_suite"
    assert len(baseline["rollout_results"]) >= 20
    assert len(candidate["rollout_results"]) >= 20
```

- [ ] **Step 2: Implement evaluator backend boundary**

Implement two backend classes in the MVP-2B script:

```python
class DeterministicEvaluatorBackend:
    runtime_backend = "deterministic_test_backend"
    proof_runtime = "test_only_not_isaac"


class IsaacConnectorInsertionEvaluatorBackend:
    runtime_backend = "isaac_runtime"
    proof_runtime = "dedicated_isaac_connector_insertion_evaluator"
```

Both backends return the same structured result:

```text
per_step_traces
rollout_summaries
runtime_metadata
visual_source_paths
heldout_scenario_ids
```

The deterministic backend exists for CI and artifact-shape validation only. It
must never make the top-level MVP-2B report `mvp2_closed=true` or
`proof_eligible=true`.

For every non-Isaac backend, initialize `runtime_gate.passed=false`.

- [ ] **Step 3: Implement deterministic evaluator backend**

Add an execution backend switch:

```text
--skip-isaac
--use-deterministic-eval-backend
```

The deterministic backend exists for CI and test coverage. It must write the
same artifact shape, but its report must mark:

```text
runtime_backend=deterministic_test_backend
proof_runtime=test_only_not_isaac
```

Use `proof_runtime=test_only_not_isaac` in the implementation. It can exercise
the proof JSON writer and existing validator plumbing, but final user-facing
MVP-2 closure must require Isaac runtime.

- [ ] **Step 4: Implement external rollout JSON writer**

Write JSON with:

```text
source_kind=external_heldout_policy_eval
proof_role=external_trainer_policy_eval
policy_class=phase_conditioned_numpy_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_bc_trainer_v0
heldout_suite.source_kind=external_trainer_eval_suite
heldout_suite.proof_role=external_policy_eval_suite
```

- [ ] **Step 5: Run proof JSON tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_mvp2b_external_rollout_json_has_required_validator_metadata -q
```

Expected: pass.

## Task 8: Wire Existing MVP-2 Proof Evaluator And Runtime Gate As Closure Authority

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write failing closure tests**

Add:

```python
def test_mvp2b_deterministic_backend_never_closes_mvp2_even_if_uplift_positive(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        deterministic_profile="candidate_positive",
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    learning_report = script.read_json(Path(report["artifact_paths"]["mvp2_learning_proven_report"]))
    assert learning_report["curated_vs_uncurated_uplift"] >= 0.20
    assert report["runtime_backend"] == "deterministic_test_backend"
    assert report["proof_runtime"] == "test_only_not_isaac"
    assert report["runtime_gate"]["passed"] is False
    assert report["mvp2_closed"] is False
    assert report["proof_eligible"] is False
```

Add a pure runtime-gate derivation test:

```python
def test_mvp2b_isaac_runtime_gate_and_learning_report_close_together() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    closure = script.derive_mvp2b_closure(
        learning_report={
            "learning_proven": True,
            "proof_eligible": True,
            "curated_vs_uncurated_uplift": 0.25,
        },
        runtime_gate={
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
    )

    assert closure["mvp2_closed"] is True
    assert closure["proof_eligible"] is True
```

Add a tied or negative profile test:

```python
def test_mvp2b_non_positive_uplift_keeps_mvp2_open(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        deterministic_profile="tie",
        min_rollouts_per_policy=20,
        bootstrap_iterations=200,
    )

    assert report["mvp2_closed"] is False
    assert report["learning_proven"] is False
```

- [ ] **Step 2: Write threshold-freeze test**

Add:

```python
def test_mvp2b_threshold_freeze_rejects_post_heldout_threshold_change(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    manifest = script.build_scenario_manifest(output_dir=tmp_path / "mvp2b")
    heldout_results_path = tmp_path / "mvp2b" / "heldout_rollouts" / "candidate_rollouts.csv"
    heldout_results_path.parent.mkdir(parents=True)
    heldout_results_path.write_text("scenario_id,success\nheldout_3000,True\n", encoding="utf-8")

    result = script.validate_manifest_threshold_freeze(
        original_manifest=manifest,
        proposed_manifest={
            **manifest,
            "success_metric": {
                **manifest["success_metric"],
                "lateral_error_m_max": 0.010,
            },
        },
        heldout_results_exist=True,
    )

    assert result["passed"] is False
    assert result["requires_new_manifest_version"] is True
```

- [ ] **Step 3: Call `build_mvp2_learning_proven_policy_eval()`**

Pass baseline/candidate rollout JSON into the existing evaluator with:

```text
baseline_policy_id=baseline_uncurated_phase_conditioned_numpy_bc
candidate_policy_id=candidate_curated_phase_conditioned_numpy_bc
policy_class=phase_conditioned_numpy_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_bc_trainer_v0
min_rollouts_per_policy=20
```

- [ ] **Step 4: Mirror closure authority fields**

Top-level report must copy:

```text
learning_report.learning_proven
learning_report.proof_eligible
curated_vs_uncurated_uplift
baseline_success_rate
candidate_success_rate
blockers
```

from the existing evaluator result. Final top-level `learning_proven`,
`proof_eligible`, and `mvp2_closed` must be derived by:

```text
existing_evaluator.learning_proven
AND existing_evaluator.proof_eligible
AND runtime_gate.passed
AND runtime_backend == isaac_runtime
AND proof_runtime == dedicated_isaac_connector_insertion_evaluator
AND curated_vs_uncurated_uplift >= 0.20
```

If the existing evaluator reports `proof_eligible=true` for deterministic
plumbing, the top-level MVP-2B report must still override
`proof_eligible=false` unless the runtime gate is also true.

- [ ] **Step 5: Run closure tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: positive deterministic backend can exercise validator plumbing but
does not close MVP-2; pure runtime-gate derivation shows the exact condition
required for Isaac runtime closure; tie profile does not close.

## Task 9: Preserve Smoke/Proxy/HMD Boundaries

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write boundary tests**

Add:

```python
def test_mvp2b_skip_isaac_never_claims_proof(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    assert report["mvp2_closed"] is False
    assert report["proof_eligible"] is False
    assert report["runtime_backend"] == "skipped"


def test_mvp2b_hmd_openxr_is_not_primary_path(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=True,
        min_rollouts_per_policy=20,
    )

    primary_claims = json.dumps(report["non_claims"]).lower()
    assert "hmd" in primary_claims
    assert "openxr" in primary_claims
    assert report["primary_proof_path"] == "dedicated_isaac_connector_insertion_evaluator"
```

- [ ] **Step 2: Implement boundary fields**

Add report fields:

```text
primary_proof_path
runtime_backend
non_claims
limitations
proof_boundary
```

- [ ] **Step 3: Run boundary tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: boundary tests pass.

## Task 10: Add Visual Evidence From Rollout Logs

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Write visual evidence test**

Add:

```python
def test_mvp2b_visual_evidence_paths_are_written_from_rollout_logs(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        min_rollouts_per_policy=20,
    )

    visual_paths = report["visual_evidence"]
    assert Path(visual_paths["metric_trace_comparison_png"]).exists()
    assert Path(visual_paths["baseline_representative_rollout"]).exists()
    assert Path(visual_paths["candidate_representative_rollout"]).exists()
    assert report["visual_evidence_is_proof_override"] is False
```

Add:

```python
def test_mvp2b_visual_source_trace_provenance_is_required(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    report = script.build_mvp2b_isaac_proof_evaluator(
        output_dir=tmp_path / "mvp2b",
        clean=True,
        skip_isaac=False,
        use_deterministic_eval_backend=True,
        min_rollouts_per_policy=20,
    )

    assert report["visual_evidence_is_proof_override"] is False
    assert report["visual_evidence_source"] in {"rollout_metric_traces", "isaac_runtime_capture"}
    assert report["visual_evidence_source_trace_paths"]
```

- [ ] **Step 2: Implement metric trace image**

Use standard library file writing for representative CSV/JSON traces and use
the existing available plotting stack only if already present in the project
environment. If `matplotlib` is unavailable, write an SVG or HTML metric trace
from rollout log data and keep the report field name explicit for the actual
extension.

- [ ] **Step 3: Run visual test**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_mvp2b_visual_evidence_paths_are_written_from_rollout_logs -q
```

Expected: pass.

## Task 11: Add CLI And Top-Level Report

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Test: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add CLI args**

Supported args:

```text
--output-dir
--clean
--skip-isaac
--use-deterministic-eval-backend
--deterministic-profile
--rollouts-per-policy
--max-steps
--bootstrap-iterations
--bootstrap-seed
--pretty
```

- [ ] **Step 2: Add `main()`**

`main()` calls `build_mvp2b_isaac_proof_evaluator()` and prints:

```text
passed
mvp2_closed
learning_proven
proof_eligible
baseline_success_rate
candidate_success_rate
curated_vs_uncurated_uplift
report_path
```

- [ ] **Step 3: Run script in skipped mode**

```bash
uv run python scripts/run_mvp2b_isaac_proof_evaluator.py --clean --skip-isaac --pretty
```

Expected:

```text
passed=true
mvp2_closed=false
proof_eligible=false
```

## Task 12: Implement And Run Isaac Runtime Proof Backend

**Files:**
- Modify only if required by local Isaac runtime diagnostics:
  `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Do not modify HMD/OpenXR runtime scripts.

- [ ] **Step 1: Run deterministic final check first**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
uv run python scripts/run_mvp2b_isaac_proof_evaluator.py --clean --use-deterministic-eval-backend --pretty
```

Expected: deterministic backend completes and proves the artifact wiring.

- [ ] **Step 2: Implement `IsaacConnectorInsertionEvaluatorBackend.run()`**

The backend must:

1. start IsaacLab headless with the dedicated connector insertion scene,
2. reset each held-out scenario by manifest seed and initial offset,
3. step the baseline or candidate policy,
4. record per-step geometry metrics,
5. evaluate the geometry + stability success metric,
6. write rollout summaries and metric traces,
7. expose runtime metadata with:

```text
runtime_backend=isaac_runtime
proof_runtime=dedicated_isaac_connector_insertion_evaluator
scenario_manifest_sha256
isaac_task_or_scene_id
headless
device
```

Copy `scenario_manifest_sha256` into rollout CSV metadata, external rollout
JSON, visual evidence metadata, and the top-level report so threshold-freeze
and leakage audits can trace every proof-facing artifact back to the same
manifest.

- [ ] **Step 3: Run Isaac runtime command**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_isaac_proof_evaluator.py --clean --rollouts-per-policy 20 --pretty
```

Expected: writes held-out rollout CSV/JSON, visual evidence, and top-level
report. It may still keep `mvp2_closed=false` if candidate does not beat
baseline.

- [ ] **Step 4: Interpret runtime result**

If `mvp2_closed=true`, MVP-2 can be closed for learning-proven Isaac held-out
policy uplift. If `mvp2_closed=false`, preserve artifacts and record the
blocker without changing thresholds.

## Task 13: Documentation And Handoff

**Files:**
- Modify: `docs/developer/debugging_guide.md`
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Update debugging guide**

Add:

```text
MVP-2B Isaac proof evaluator
uv run python scripts/run_mvp2b_isaac_proof_evaluator.py --clean --skip-isaac --pretty
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_isaac_proof_evaluator.py --clean --rollouts-per-policy 20 --pretty
```

State that skipped/deterministic backends do not replace actual Isaac runtime
proof.

- [ ] **Step 2: Update worklog and Handoff**

Record changed files, commands, pass/fail outputs, proof status, and remaining
gap if the runtime attempt does not close MVP-2.

- [ ] **Step 3: Update todo**

Mark MVP-2B tasks according to actual evidence.

## Final Verification

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q
uv run python scripts/run_mvp2b_isaac_proof_evaluator.py --clean --skip-isaac --pretty
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py scripts/run_mvp2_learning_proven_policy_eval.py
git diff --check
```

Runtime proof attempt:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_isaac_proof_evaluator.py --clean --rollouts-per-policy 20 --pretty
```

## Execution Recommendation

Use `$ultragoal` as the default next step. Use `$team` inside the Ultragoal
execution only if the Isaac runtime scene work and proof/reporting work need to
proceed in parallel. Use `$ralph` only as an explicit fallback for single-owner
persistent verification.

## ADR

### Decision

Implement MVP-2B as a dedicated Isaac connector insertion proof evaluator with a
separate deterministic test backend. MVP-2 closure requires both:

```text
existing MVP-2 proof evaluator passes
AND runtime_backend == isaac_runtime
AND proof_runtime == dedicated_isaac_connector_insertion_evaluator
```

### Drivers

- MVP-2 must prove learning value, not only artifact readiness.
- Local proxy and smoke results are useful engineering signals but are not proof
  eligible.
- The user needs actual Isaac-derived rollout traces and visual evidence for a
  credible public/investor-facing explanation.

### Alternatives Considered

- Promote existing Isaac smoke runner: rejected because it uses smoke-only
  evidence and the wrong policy/trainer contract.
- Keep improving local proxy: rejected because it cannot honestly close MVP-2.
- Accept externally supplied rollout JSON only: rejected as the primary plan
  because it does not build the desired dedicated evaluator or visual evidence
  path.

### Consequences

- Implementation scope is larger than a JSON ingestion bridge.
- Isaac runtime compatibility may block MVP-2 closure even if deterministic
  tests pass.
- A non-closing runtime result is still a valid output and must be preserved
  without threshold retuning.

### Follow-Ups

- After first proof-grade runtime result, decide whether to strengthen closure
  with bootstrap CI lower bound > 0.
- If Isaac runtime blocks on environment setup, record the blocker and keep
  deterministic artifacts as non-proof diagnostics.

## Available Agent Types

- `executor`: implement script/tests/docs from this plan.
- `test-engineer`: own red tests, fixture hygiene, and proof-boundary regression
  tests.
- `architect`: review runtime boundary, closure derivation, and proof integrity.
- `critic`: review acceptance criteria before final MVP-2 closure claim.
- `verifier`: run final verification commands and summarize evidence.

## Follow-Up Staffing Guidance

### `$ultragoal` Default

Use `$ultragoal` as the default execution mode. Suggested goal split:

1. Manifest, metric, leak guard, and deterministic backend tests.
2. Trajectory generation, normalized contract validation, curation, HDF5 train
   views, and phase-conditioned BC trainer.
3. Held-out rollout JSON, existing proof evaluator integration, runtime gate,
   visual evidence, CLI, docs, and final verification.
4. Isaac runtime backend proof attempt and closure/non-closure evidence capture.

### `$team` Inside Ultragoal

Use `$team` only if parallelism is useful after the deterministic foundation is
green:

- lane A: Isaac runtime backend and scene stepping diagnostics
- lane B: proof/reporting integration and visual evidence writer
- lane C: test hardening and documentation

Team verification path: each lane returns command output and changed files to
the Ultragoal leader; the leader runs the final verification suite and owns the
ledger checkpoint.

### `$ralph` Fallback

Use `$ralph` only if the user explicitly chooses single-owner persistent
completion pressure instead of durable Ultragoal tracking. The same PRD,
test-spec, and closure rules still apply.

## Goal-Mode Follow-Up Suggestions

- `$ultragoal`: recommended next step for durable sequential implementation and
  checkpointed verification.
- `$team`: optional inside Ultragoal if Isaac runtime and proof/reporting can be
  split safely.
- `$autoresearch-goal`: not recommended for this step because the design
  decision is already fixed and implementation evidence is now needed.
- `$performance-goal`: not applicable unless runtime speed becomes the primary
  blocker after proof correctness is established.
