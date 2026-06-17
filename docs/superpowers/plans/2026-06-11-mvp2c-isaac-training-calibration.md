# MVP-2C Isaac Training / Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP-2C runner that creates a fresh pre-registered Isaac training / calibration / held-out proof attempt, then closes MVP-2 only when actual Isaac held-out rollouts prove curated > uncurated uplift.

**Architecture:** Add `scripts/run_mvp2c_isaac_training_calibration.py` as a new proof runner beside the MVP-2B runner. Reuse MVP-2B patterns for stable JSON, HDF5 train views, phase-conditioned NumPy BC, external rollout JSON, visual evidence, and existing MVP-2 validator ingest, while adding new MVP-2C boundaries for baseline mix pre-registration, generator config hashes, calibration-only adapter selection, selected adapter freeze, close-minimum reporting, stronger public evidence reporting, and privileged-feature non-claims.

Actual MVP-2C closure requires two runtime gates:

- `train_generation_runtime_gate.passed=true` with
  `train_generation_runtime_backend=isaac_runtime`
- held-out `runtime_gate.passed=true` with `runtime_backend=isaac_runtime`

Deterministic train generation and deterministic held-out evaluation remain
test/plumbing paths only and cannot close MVP-2C.

**Tech Stack:** Python 3.11+, NumPy, h5py, pytest, existing RDF services, existing `NormalizedTrajectoryContractValidator`, existing MVP-2 learning-proven validator wrapper, IsaacLab runtime only for actual proof attempts, no DB migration, no new production dependency.

---

## Source Artifacts

- Spec:
  `docs/superpowers/specs/2026-06-11-mvp2c-isaac-training-calibration-slice-design.md`
- Context snapshot:
  `.omx/context/mvp2c-isaac-training-calibration-20260610T175054Z.md`
- PRD:
  `.omx/plans/prd-mvp2c-isaac-training-calibration.md`
- Test spec:
  `.omx/plans/test-spec-mvp2c-isaac-training-calibration.md`

## File Structure

- Create `scripts/run_mvp2c_isaac_training_calibration.py`
  - Owns MVP-2C manifest, fixed split, baseline mix config, generator config
    hashes, action adapter registry, calibration selector, selected adapter
    freeze, Isaac/deterministic evaluation dispatch, HDF5 train views, policy
    artifacts, external rollout JSON, learning validator ingest, visual evidence,
    and top-level report.

- Create `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Focused RED/GREEN coverage for manifest, leakage guard, baseline mix,
    generator hash immutability, adapter registry, calibration-only selector,
    contract validation, train views, policy fairness, closure authority, public
    evidence target, and non-claims.

- Modify `docs/developer/debugging_guide.md`
  - Add MVP-2C commands, actual Isaac runtime interpretation, non-closing
    outcomes, and public-evidence language.

- Modify `docs/developer/worklog.md`
  - Record implementation decisions, changed files, verification commands, and
    actual run result.

- Modify `tasks/todo.md`
  - Track MVP-2C implementation progress and closure status.

- Modify `Handoff.md`
  - Preserve compact next-session state and current MVP-2 closure truth.

No DB migration is planned.

## RALPLAN-DR Summary

### Principles

- MVP-2C closure authority stays with actual Isaac held-out rollout evidence plus
  the existing MVP-2 learning-proven validator.
- Held-out evidence must be excluded from training, calibration, adapter
  selection, threshold tuning, and hyperparameter selection.
- Baseline uncurated must be a pre-registered raw-material view, not a
  post-result poisoned baseline.
- Baseline and candidate differ only by train dataset view; policy/trainer,
  feature schema, hyperparameters, selected adapter, and held-out suite are
  shared.
- Public claims must be weaker than engineering closure unless the stronger
  rollout and confidence-interval target passes.

### Decision Drivers

1. MVP-2B actual Isaac runtime gate passed but produced zero uplift, so the next
   attempt must use a fresh pre-registered split rather than tuning against the
   seen held-out result.
2. The hardened MVP-2C spec adds proof-integrity guards that must be implemented
   before any fresh held-out run.
3. MVP-2C needs real visual/runtime evidence, but visual artifacts and
   deterministic paths must never override proof-grade JSON and validator gates.
4. Actual closure requires both Isaac-runtime train generation and Isaac-runtime
   held-out evaluation; held-out-only Isaac evidence is not enough.

### Viable Options

| Option | Pros | Cons | Decision |
|---|---|---|---|
| New MVP-2C runner beside MVP-2B | Clean proof boundary, preserves MVP-2B history, easier non-regression testing | Some helper duplication remains | Chosen |
| Refactor MVP-2B into shared library first | Less duplication long-term | Larger blast radius before proof is stable | Rejected for this slice |
| Patch MVP-2B in place into MVP-2C | Less file creation | Blurs historical non-closing run and fresh proof attempt | Rejected |
| Use external rollout template only | Minimal code | Does not create the requested Isaac training/calibration proof path | Rejected |

### Pre-Mortem

1. Calibration selector accidentally reads held-out content.
   - Mitigation: make selector input a typed/calibrated summary object, reject
     held-out paths and held-out success metrics, and test the rejection.
2. Baseline uplift looks manufactured because failure ratio changes after
   results.
   - Mitigation: write `baseline_noise_mix_config.json`, include its hash in train
     metadata and top-level report, and fail when fixed mix cannot be satisfied.
3. Actual Isaac runtime still produces non-positive uplift.
   - Mitigation: record a non-closing report with trace artifacts and blockers;
     do not relax thresholds or mark MVP-2 Closed.
4. Train material silently comes from a deterministic fixture while held-out
   rollouts come from Isaac.
   - Mitigation: add `train_generation_runtime_gate` and make deterministic train
     generation non-closing.

### Expanded Test Plan

- Unit: manifest, hash, leakage guard, baseline mix, selector score, adapter
  registry, closure derivation, confidence/public target derivation.
- Integration: full `--skip-isaac` and deterministic backend runner outputs,
  HDF5 train view shape, policy artifact fairness, external rollout JSON ingest.
- E2E: actual Isaac runtime command through
  `/home/kangrim/IsaacLab/_isaac_sim/python.sh`.
- Observability: top-level report includes artifact paths, blocker list,
  selected adapter, hashes, train generation runtime gate, held-out runtime gate,
  validator bridge provenance, validator evidence, non-claims, and reproducible
  command.

## ADR: Fresh MVP-2C Runner With Calibration-Only Adapter Selection

**Decision:** Implement MVP-2C as a new runner that reuses MVP-2B-compatible
helpers where safe, but owns new proof-integrity artifacts and closure fields.

**Drivers:**

- MVP-2B is a valid historical non-closing proof attempt and should remain
  inspectable.
- MVP-2C needs new manifest seeds, baseline mix pre-registration, generator
  hashes, and calibration-only adapter selection.
- The existing MVP-2 validator remains the downstream learning-proven gate.

**Alternatives considered:**

- Shared library refactor first: rejected because it increases blast radius
  before MVP-2C proof behavior is stable.
- Mutate MVP-2B runner: rejected because it blends historical and fresh proof
  attempts.
- External JSON only: rejected because it does not build the requested actual
  Isaac training/calibration route.

**Why chosen:**

The new runner gives the cleanest proof boundary and fastest TDD path while
preserving existing MVP-2B tests and artifacts as regression guards.

**Consequences:**

- There will be some temporary duplication with MVP-2B.
- A later cleanup can extract stable helper modules after MVP-2C closes or
  records a useful non-closing attempt.
- Execution can stop honestly if actual Isaac runtime or fresh held-out uplift
  fails.
- A held-out Isaac run cannot close MVP-2C if train generation was deterministic
  or otherwise lacks `train_generation_runtime_gate.passed=true`.

**Follow-ups:**

- After MVP-2C, consider extracting common proof-runner helpers into
  `apps/api/app/services/` only if both MVP-2B and MVP-2C need further evolution.
- If engineering close passes with 20 rollouts, run the stronger public evidence
  target with at least 50 rollouts per policy before public benchmark language.

## Task 1: Add RED Tests For Manifest And Leakage Boundary

**Files:**
- Create: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Create later: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Write failing manifest tests**

Add this test skeleton:

```python
from pathlib import Path
from typing import Any

import pytest


def load_script(name: str) -> Any:
    import importlib.util

    script_path = Path(__file__).resolve().parents[3] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mvp2c_scenario_manifest_is_pre_registered_and_hashed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")

    assert manifest["manifest_version"] == "rdf_mvp2c_scenario_manifest_v0.1.0"
    assert manifest["success_metric"]["insertion_depth_m_min"] == 0.03
    assert manifest["success_metric"]["lateral_error_m_max"] == 0.006
    assert manifest["success_metric"]["orientation_error_deg_max"] == 8.0
    assert manifest["success_metric"]["stable_steps_required"] == 10
    assert manifest["success_metric"]["max_steps"] == 150
    assert manifest["manifest_sha256"]
    assert (tmp_path / "mvp2c" / "scenario_manifest.json").exists()


def test_mvp2c_scenario_manifest_uses_fresh_disjoint_seed_ranges(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }

    assert split_to_seeds["train_success"] == set(range(4000, 4080))
    assert split_to_seeds["train_failure"] == set(range(4100, 4180))
    assert split_to_seeds["calibration"] == set(range(5000, 5020))
    assert split_to_seeds["held_out"] == set(range(6000, 6020))
    assert set(range(3000, 3020)).isdisjoint(set().union(*split_to_seeds.values()))
```

- [ ] **Step 2: Write failing leakage guard test**

Add:

```python
def test_mvp2c_leak_guard_rejects_heldout_in_selection_channels(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    heldout_id = next(row["scenario_id"] for row in manifest["scenarios"] if row["split"] == "held_out")

    report = script.validate_mvp2c_no_heldout_leakage(
        manifest=manifest,
        training_scenario_ids=[],
        curation_tuning_scenario_ids=[],
        threshold_tuning_scenario_ids=[],
        hyperparameter_scenario_ids=[],
        adapter_selection_scenario_ids=[heldout_id],
        calibration_trace_paths=[str(tmp_path / "heldout_rollout_traces" / "trace.json")],
        heldout_rollout_json_paths=[str(tmp_path / "external_rollouts" / "candidate_external_rollouts.json")],
        heldout_success_metrics={"candidate_success_rate": 1.0},
    )

    assert report["passed"] is False
    assert heldout_id in report["leaked_scenario_ids"]
    assert "adapter_selection" in report["blocked_channels"]
    assert "heldout_rollout_json_paths" in report["blocked_channels"]
    assert "heldout_success_metrics" in report["blocked_channels"]
```

- [ ] **Step 3: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected: import fails because `scripts/run_mvp2c_isaac_training_calibration.py`
does not exist.

## Task 2: Add RED Tests For Baseline Mix And Hash Immutability

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add baseline mix test**

```python
def test_mvp2c_baseline_noise_mix_is_pre_registered_and_hash_stable(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2c")

    assert config["baseline_noise_mix_ratio"] == 0.25
    assert config["accepted_failure_ratio"] == {"accepted": 3, "failure_or_noisy": 1}
    assert sum(config["failure_type_distribution"].values()) == pytest.approx(1.0)
    assert config["noise_profile_config_sha256"]

    again = script.build_baseline_noise_mix_config(output_dir=tmp_path / "mvp2c_again")
    assert config["noise_profile_config_sha256"] == again["noise_profile_config_sha256"]
```

- [ ] **Step 2: Add generator hash test**

```python
def test_mvp2c_generation_config_hashes_are_written_and_guarded(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2c")

    assert hashes["scripted_expert_config_sha256"]
    assert hashes["controlled_failure_config_sha256"]
    assert hashes["train_generation_config_sha256"]

    changed = dict(hashes)
    changed["train_generation_config_sha256"] = "0" * 64
    guard = script.validate_generation_config_immutability(
        original_hashes=hashes,
        current_hashes=changed,
        train_generation_started=True,
        calibration_started=True,
        heldout_started=False,
    )

    assert guard["passed"] is False
    assert "train_generation_config_sha256" in guard["changed_fields"]


def test_mvp2c_scripted_generator_hash_change_after_train_start_fails(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    hashes = script.build_generator_config_hashes(output_dir=tmp_path / "mvp2c")
    changed = dict(hashes)
    changed["scripted_expert_config_sha256"] = "1" * 64

    guard = script.validate_generation_config_immutability(
        original_hashes=hashes,
        current_hashes=changed,
        train_generation_started=True,
        calibration_started=False,
        heldout_started=False,
    )

    assert guard["passed"] is False
    assert "scripted_expert_config_sha256" in guard["changed_fields"]
```

- [ ] **Step 3: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected: fails on missing MVP-2C functions.

## Task 3: Add RED Tests For Adapter Registry And Calibration Selector

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add registry hash test**

```python
def test_mvp2c_action_adapter_registry_is_predeclared_and_hashed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    registry = script.build_action_adapter_registry(output_dir=tmp_path / "mvp2c")

    adapter_ids = {item["adapter_id"] for item in registry["adapters"]}
    assert adapter_ids == {
        "isaac_delta_pose_direct_v0",
        "isaac_signed_xy_downward_servo_v0",
        "isaac_stability_damped_servo_v0",
    }
    assert registry["action_adapter_registry_sha256"]
```

- [ ] **Step 2: Add selector score and anti-p-hacking test**

```python
def test_mvp2c_calibration_selector_is_calibration_only_and_freezes_adapter(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    registry = script.build_action_adapter_registry(output_dir=tmp_path / "mvp2c")

    calibration_summaries = [
        {
            "adapter_id": "isaac_delta_pose_direct_v0",
            "baseline_success_rate": 0.10,
            "candidate_success_rate": 0.20,
            "candidate_stability_margin": 0.10,
            "candidate_action_saturation_rate": 0.02,
        },
        {
            "adapter_id": "isaac_signed_xy_downward_servo_v0",
            "baseline_success_rate": 0.10,
            "candidate_success_rate": 0.45,
            "candidate_stability_margin": 0.20,
            "candidate_action_saturation_rate": 0.04,
        },
    ]

    report = script.select_action_adapter_from_calibration(
        manifest=manifest,
        registry=registry,
        calibration_summaries=calibration_summaries,
        output_dir=tmp_path / "mvp2c",
    )

    assert report["selected_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert report["selector_score_pre_registered"] is True
    assert report["same_adapter_used_for_baseline_and_candidate"] is True
    assert report["heldout_excluded"] is True
    assert report["selected_adapter_frozen_before_heldout"] is True
    assert Path(report["artifact_paths"]["selected_action_adapter"]).exists()
```

- [ ] **Step 3: Add selector held-out content rejection test**

```python
def test_mvp2c_calibration_selector_rejects_heldout_rollout_content(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    manifest = script.build_mvp2c_scenario_manifest(output_dir=tmp_path / "mvp2c")
    registry = script.build_action_adapter_registry(output_dir=tmp_path / "mvp2c")

    with pytest.raises(ValueError, match="held-out"):
        script.select_action_adapter_from_calibration(
            manifest=manifest,
            registry=registry,
            calibration_summaries=[],
            output_dir=tmp_path / "mvp2c",
            heldout_rollout_json_paths=[str(tmp_path / "heldout.json")],
        )
```

## Task 4: Implement MVP-2C Manifest, Hash Artifacts, And Guards

**Files:**
- Create: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants and stable JSON utilities**

Implement with the same stable JSON behavior used by
`scripts/run_mvp2b_isaac_proof_evaluator.py`.

Required constants:

```python
SCHEMA_VERSION = "rdf_mvp2c_isaac_training_calibration_v0.1.0"
SCENARIO_MANIFEST_VERSION = "rdf_mvp2c_scenario_manifest_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2c_isaac_training_calibration"
MVP2B_HELDOUT_SEEDS = set(range(3000, 3020))
SUCCESS_METRIC = {
    "insertion_depth_m_min": 0.030,
    "lateral_error_m_max": 0.006,
    "orientation_error_deg_max": 8.0,
    "stable_steps_required": 10,
    "max_steps": 150,
}
```

- [ ] **Step 2: Implement `build_mvp2c_scenario_manifest()`**

Implementation requirements:

- use seeds exactly from the spec,
- write `scenario_manifest.json`,
- compute `manifest_sha256` from stable JSON excluding no fields,
- raise `ValueError` if any seed overlaps `MVP2B_HELDOUT_SEEDS`.

- [ ] **Step 3: Implement baseline mix and generator hash builders**

Create:

```python
def build_baseline_noise_mix_config(*, output_dir: Path) -> dict[str, Any]:
    return baseline_mix_config


def build_generator_config_hashes(*, output_dir: Path) -> dict[str, Any]:
    return generator_config_hashes


def validate_generation_config_immutability(
    *,
    original_hashes: dict[str, Any],
    current_hashes: dict[str, Any],
    train_generation_started: bool,
    calibration_started: bool,
    heldout_started: bool,
) -> dict[str, Any]:
    return immutability_report
```

Write:

```text
baseline_noise_mix_config.json
generator_config_hashes.json
```

- [ ] **Step 4: Implement leakage guard**

Create `validate_mvp2c_no_heldout_leakage()` with channels for training,
curation tuning, threshold tuning, hyperparameter selection, adapter selection,
calibration trace paths, held-out rollout JSON paths, and held-out success
metrics.

- [ ] **Step 5: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected: manifest/hash/guard tests pass; later tests still fail until
subsequent tasks are implemented.

## Task 5: Implement Action Adapter Registry And Calibration Selector

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Implement adapter registry**

Create `build_action_adapter_registry()` that writes:

```text
action_adapter_candidates.json
action_adapter_registry_hash.json
```

The registry must include all three adapter ids and parameter dictionaries.

- [ ] **Step 2: Implement selector score config hash**

Write a stable selector score config with:

```text
selector_score =
  1.00 * uplift
  + 0.25 * candidate_stability_margin
  - 0.10 * candidate_action_saturation_rate
```

Persist `selector_score_config_sha256`.

- [ ] **Step 3: Implement `select_action_adapter_from_calibration()`**

Selector rules:

- reject any held-out JSON path, trace path, or success metric input,
- compute score only from calibration summaries,
- apply deterministic tie-break order,
- write `calibration_selection_report.json`,
- write `selected_action_adapter.json`,
- include all anti-p-hacking fields as `true`.

- [ ] **Step 4: Run selector tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected: adapter registry and selector tests pass.

## Task 6: Generate Runtime-Gated Training Material, Contracts, And Train Views

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Implement `IsaacRuntimeScriptedExpertDataGenerator` boundary**

Create a generator boundary with two implementations:

```text
IsaacRuntimeScriptedExpertDataGenerator
DeterministicScriptedExpertFixtureGenerator
```

Actual closure must use:

```text
train_generation_runtime_backend=isaac_runtime
train_generation_runtime_gate.passed=true
```

The deterministic fixture generator is allowed only for RED/GREEN tests,
`--skip-isaac`, and `--use-deterministic-eval-backend` non-closing plumbing
runs.

- [ ] **Step 2: Add train generation runtime gate tests**

Add a test that creates a report with positive held-out uplift but
`train_generation_runtime_backend=deterministic_test_backend`; assert
`mvp2_closed=false` and the blocker names `train_generation_runtime_gate`.

- [ ] **Step 3: Ensure accepted contracts include generator hash provenance**

Every accepted normalized trajectory contract must include:

```text
source_provenance.scenario_manifest_sha256
source_provenance.scripted_expert_config_sha256
source_provenance.controlled_failure_config_sha256
source_provenance.train_generation_config_sha256
source_provenance.train_generation_runtime_backend
```

- [ ] **Step 4: Implement fixed baseline mix selection**

Baseline view must include accepted plus failure/noisy rows according to
`baseline_noise_mix_ratio=0.25`. If the generated material cannot satisfy the
fixed mix, raise `ValueError`.

- [ ] **Step 5: Implement HDF5 train views**

Write:

```text
baseline_uncurated_train.hdf5
candidate_curated_train.hdf5
```

Include train view metadata with manifest hash, generator hashes, baseline mix
hash, train generation runtime backend, feature schema, and action schema.
Do not write selected adapter metadata into HDF5 because adapter selection occurs
after policy training. Selected adapter metadata belongs in
`selected_action_adapter.json`, `policy_eval_binding.json`, held-out rollout
JSON, and top-level report.

- [ ] **Step 6: Add and run tests**

Add assertions for contract validation, baseline rejected material, candidate
accepted-only material, and HDF5 metadata.

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

## Task 7: Train Shared Phase-Conditioned Policies, Run Calibration, And Bind Adapter

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Reuse MVP-2B phase-conditioned NumPy BC structure**

Keep policy identifiers MVP-2C-specific:

```text
baseline_uncurated_mvp2c_phase_conditioned_numpy_bc
candidate_curated_mvp2c_phase_conditioned_numpy_bc
```

Both must use:

```text
policy_class=phase_conditioned_numpy_bc_policy_v0
trainer=rdf_numpy_phase_conditioned_bc_trainer_v0
```

- [ ] **Step 2: Bind selected adapter into policy evaluation artifacts**

After calibration selection, write `policy_eval_binding.json` and update the
top-level policy artifact metadata so both baseline and candidate reference the
same `selected_action_adapter_id` and `selected_action_adapter_sha256`. Do not
mutate the HDF5 train views.

- [ ] **Step 3: Implement calibration evaluator path**

For deterministic tests, calibration summaries may be generated from the same
trace evaluation mechanics as MVP-2B. For actual Isaac execution, calibration
must run against calibration split only.

- [ ] **Step 4: Add fairness tests**

Assert baseline/candidate share feature schema, phase schema, action schema,
trainer, hyperparameters, selected adapter, and held-out suite.

## Task 8: Implement Held-Out Evaluation, External Rollout JSON, And Closure

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Reuse MVP-2B backend dispatch shape**

Support:

```text
--skip-isaac
--use-deterministic-eval-backend
actual Isaac runtime default
```

Deterministic and skipped paths must always remain non-closing.

- [ ] **Step 2: Apply selected adapter to both baseline and candidate held-out runs**

The same selected adapter must convert normalized policy actions for both
policies during held-out evaluation.

- [ ] **Step 3: Write MVP-2C learning-validator bridge**

Write an MVP-2C-specific bridge under:

```text
mvp2_learning_harness_bridge/
```

The bridge must include:

```text
mvp2_policy_ab_harness_report.json
mvp2_policy_eval_input_template.json
mvp2_heldout_suite_manifest.json
learning_validator_bridge_sha256
```

The bridge report must point only to MVP-2C artifacts:

```text
baseline_uncurated_train.hdf5
candidate_curated_train.hdf5
baseline_policy_artifact.json
candidate_policy_artifact.json
selected_action_adapter.json
policy_eval_binding.json
```

Add a test that fails if any bridge artifact path contains an MVP-2B output dir
or UR harness output dir.

- [ ] **Step 4: Write proof-grade rollout JSON**

Write:

```text
external_rollouts/baseline_external_rollouts.json
external_rollouts/candidate_external_rollouts.json
```

Required provenance:

```text
source_kind=external_heldout_policy_eval
proof_role=external_trainer_policy_eval
external_evaluator_run.generated_outside_rdf_local_proxy=true
heldout_suite.source_kind=external_trainer_eval_suite
heldout_suite.proof_role=external_policy_eval_suite
selected_action_adapter_id=<selected adapter>
selected_action_adapter_sha256=<selected adapter hash>
```

- [ ] **Step 5: Run existing MVP-2 validator wrapper**

Call `build_mvp2_learning_proven_policy_eval()` with MVP-2C held-out rollout
paths, MVP-2C bridge dir as `harness_output_dir`, and policy metadata.

- [ ] **Step 6: Implement MVP-2C closure derivation**

Create `derive_mvp2c_closure()` that requires:

```text
runtime_backend == isaac_runtime
proof_runtime == dedicated_isaac_connector_insertion_evaluator
train_generation_runtime_backend == isaac_runtime
train_generation_runtime_gate.passed == true
runtime_gate.passed == true
calibration_only_selection_passed == true
heldout_leakage_guard_passed == true
actual_rollouts_per_policy >= 20
learning_report.learning_proven == true
learning_report.proof_eligible == true
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
```

## Task 9: Implement Report Fields, Public Evidence Target, And Non-Claims

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Write top-level report**

Write:

```text
mvp2c_isaac_training_calibration_report.json
```

Include all required spec fields: schema, manifest, hashes, baseline mix,
selector, train generation runtime gate, held-out runtime gate,
`learning_validator_bridge_sha256`, bridge provenance, rollout metrics, closure
flags, blockers, non-claims, limitations, and reproducible command.

- [ ] **Step 2: Derive public evidence target**

Implement:

```python
def derive_stronger_public_evidence_target(
    *,
    actual_rollouts_per_policy: int,
    confidence_interval_report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "stronger_public_evidence_target_passed": (
            actual_rollouts_per_policy >= 50
            and isinstance(confidence_interval_report, dict)
            and bool(confidence_interval_report)
        ),
        "minimum_rollouts_per_policy_for_public_target": 50,
        "confidence_interval_reported": isinstance(confidence_interval_report, dict)
        and bool(confidence_interval_report),
    }
```

Return true only when rollouts per policy are at least `50` and a binomial or
bootstrap confidence interval is present.

- [ ] **Step 3: Add privileged-feature non-claim fields**

Top-level `non_claims` object must include:

```json
{
  "deployable_real_robot_policy": false,
  "visual_policy_performance": false,
  "real_robot_success": false,
  "physical_robot_readiness": false,
  "universal_robot_support": false
}
```

- [ ] **Step 4: Add reporting tests**

Assert `mvp2c_close_minimum_passed` and
`stronger_public_evidence_target_passed` are separate fields.

## Task 10: Add CLI, Docs, And Verification

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Add CLI arguments**

Support:

```text
--output-dir
--clean
--skip-isaac
--use-deterministic-eval-backend
--rollouts-per-policy
--max-steps
--isaac-task
--device
--action-scale
--bootstrap-iterations
--bootstrap-seed
--pretty
```

- [ ] **Step 2: Run focused verification**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

- [ ] **Step 3: Run relevant regression suite**

```bash
uv run pytest \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py \
  apps/api/tests/test_mvp1_proof_audit_script.py \
  -q
```

- [ ] **Step 4: Run non-closing script checks**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py --clean --skip-isaac --pretty
uv run python scripts/run_mvp2c_isaac_training_calibration.py --clean --use-deterministic-eval-backend --pretty
```

Expected: both commands pass but keep `mvp2_closed=false`.

- [ ] **Step 5: Run actual Isaac proof attempt**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --pretty
```

Expected if proof succeeds: `runtime_backend=isaac_runtime`,
`train_generation_runtime_backend=isaac_runtime`,
`mvp2c_close_minimum_passed=true`, `mvp2_closed=true`.

Expected if proof fails: `runtime_backend=isaac_runtime`,
`mvp2_closed=false`, with concrete blockers and trace artifacts.

- [ ] **Step 6: Run static checks**

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

- [ ] **Step 7: Update documentation**

Document commands, paths, and interpretation in:

```text
docs/developer/debugging_guide.md
docs/developer/worklog.md
tasks/todo.md
Handoff.md
```

## Risks And Mitigations

- Risk: MVP-2C positive uplift still does not appear.
  - Mitigation: report non-closure honestly and preserve artifacts; do not tune
    thresholds or claim closure.
- Risk: Implementation grows into a broad refactor of MVP-2B.
  - Mitigation: keep MVP-2C in one new runner first; defer helper extraction
    until after proof behavior is known.
- Risk: Calibration selector creates hidden p-hacking channel.
  - Mitigation: selector accepts calibration summaries only and rejects held-out
    paths, JSON, scenario ids beyond exclusion checks, and success metrics.
- Risk: Public post/investor language overclaims a 20-rollout result.
  - Mitigation: keep `stronger_public_evidence_target_passed` separate and false
    unless at least 50 rollouts per policy plus confidence interval are present.

## Stop Conditions

Stop implementation and report if:

- Isaac runtime cannot run locally.
- Existing validators must be weakened.
- Success thresholds must be lowered.
- Baseline noise/failure mix must be changed after train, calibration, or
  held-out starts.
- `scripted_expert_config_sha256` or `controlled_failure_config_sha256` changes
  after train generation starts.
- `train_generation_config_sha256` changes after calibration or held-out starts.
- Selector needs held-out traces, rollout JSON, or success metrics.
- Train generation was deterministic or lacks
  `train_generation_runtime_gate.passed=true` during a claimed actual closure
  attempt.
- Physical robot runtime, live ROS2/DDS, HMD collection, marketplace, or
  production auth becomes required.

## Available-Agent-Types Roster

- `executor`: implementation and refactoring lane.
- `test-engineer`: TDD coverage and regression design lane.
- `architect`: boundary review for proof integrity and closure semantics.
- `critic`: consensus and quality gate review.
- `verifier`: final evidence collection and claim validation.
- `writer`: documentation, handoff, and buyer/public wording lane.

## Follow-Up Staffing Guidance

Default: use `$ultragoal` for durable sequential execution.

Recommended lanes if using `$team` with `$ultragoal`:

- Lane 1, `test-engineer`, medium reasoning:
  create RED tests in `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`.
- Lane 2, `executor`, high reasoning:
  implement `scripts/run_mvp2c_isaac_training_calibration.py`.
- Lane 3, `verifier`, high reasoning:
  run focused/regression/script/Isaac verification and summarize closure truth.
- Lane 4, `writer`, medium reasoning:
  update debugging guide, worklog, todo, and handoff after implementation.

## Launch Hints

Preferred durable execution:

```text
$ultragoal implement docs/superpowers/plans/2026-06-11-mvp2c-isaac-training-calibration.md
```

Parallel execution option:

```text
$team implement docs/superpowers/plans/2026-06-11-mvp2c-isaac-training-calibration.md
```

Team + Ultragoal option:

```text
$ultragoal run MVP-2C plan and use $team for test, implementation, verification, and docs lanes
```

Ralph fallback:

```text
$ralph implement docs/superpowers/plans/2026-06-11-mvp2c-isaac-training-calibration.md
```

Use Ralph only if a single-owner persistent verification loop is explicitly
selected. Ultragoal remains the default durable goal-mode follow-up.

## Team Verification Path

Before Team shutdown, the team must prove:

- focused MVP-2C tests pass,
- MVP-2B and MVP-2 learning-proven regression tests pass,
- `--skip-isaac` and deterministic MVP-2C runs are non-closing,
- actual Isaac runtime attempt was run or the runtime blocker is recorded,
- report fields match the hardened spec,
- docs and handoff are updated.

## Goal-Mode Follow-Up Suggestions

- `$ultragoal`: recommended default for this implementation plan.
- `$team`: useful if splitting RED tests, runner implementation, verification,
  and docs into parallel lanes.
- `$autoresearch-goal`: not recommended as the next step because the research
  question has been converted into a concrete implementation plan.
- `$performance-goal`: not applicable unless the next task becomes runtime speed
  or throughput optimization.
- `$ralph`: fallback only for explicit single-owner persistence.

## Changelog

- Initial plan created from hardened MVP-2C spec.
