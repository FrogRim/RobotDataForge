# MVP-2E v0.10 Fresh Comparator Stress Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0_10_fresh_comparator_stress_slice`, a fresh actual-Isaac proof attempt with stronger pre-registered uncurated stress comparator and new sealed held-out `32000-32049`.

**Architecture:** Extend `scripts/run_mvp2c_isaac_training_calibration.py` with one child slice that requires v0.9a diagnosis, builds v0.10 train views/policy artifacts, runs fresh calibration `31000-31029`, and opens held-out `32000-32049` only when calibration passes.

**Tech Stack:** Python 3.11, NumPy ridge regression via existing residual policy trainer, HDF5 via existing train-view writer, pytest, Isaac runtime for calibration/held-out.

---

### Task 1: RED tests for v0.10 artifact builder

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add fake v0.10 parent helper**

Use existing fake v0.9/v0.9a helpers:

```python
def _write_fake_v10_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v09_parent_evidence(script, output_dir)
    script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=output_dir)
    _write_fake_v09a_failed_heldout_evidence(script, output_dir)
    script.build_v09a_heldout_uplift_shortfall_diagnosis(output_dir=output_dir)
```

- [ ] **Step 2: Add missing parent test**

```python
def test_v10_requires_v09a_shortfall_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_9a_heldout_uplift_shortfall_diagnosis"):
        script.build_v10_fresh_comparator_stress_slice(output_dir=tmp_path)
```

- [ ] **Step 3: Add comparator stress build test**

```python
def test_v10_builds_fresh_comparator_stress_views(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_parent_evidence(script, tmp_path)

    manifest = script.build_v10_fresh_comparator_stress_slice(output_dir=tmp_path)

    gate = manifest["comparator_stress_gate"]
    assert manifest["policy_slice"] == "v0_10"
    assert manifest["fresh_calibration_seed_range"] == [31000, 31029]
    assert manifest["fresh_heldout_seed_range"] == [32000, 32049]
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_32000_32049_accessed"] is False
    assert gate["passed"] is True
    assert gate["baseline_failure_material_ratio_target"] == pytest.approx(0.70)
    assert 0.65 <= gate["baseline_actual_failure_material_ratio"] <= 0.75
    assert gate["candidate_rows_unchanged_from_v09"] is True
    assert gate["peer_fairness_mismatch_keys"] == []
```

- [ ] **Step 4: Add CLI build test**

```python
def test_v10_cli_builds_artifact_only_comparator_stress(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile", "v0_6",
            "--policy-slice", "v0_10",
            "--fresh-comparator-stress-only",
            "--output-dir", str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path / script.V10_CHILD_OUTPUT_DIRNAME / "v0_10_comparator_stress_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V10_SLICE_ID
    assert evidence_manifest["fresh_heldout_32000_32049_accessed"] is False
```

- [ ] **Step 5: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10" -q
```

Expected: fail because `V10_*`, builder, and CLI flag do not exist.

### Task 2: Implement v0.10 artifact builder

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants**

```python
V10_POLICY_SLICE_ID = "v0_10"
V10_SLICE_ID = "mvp2e_v10_fresh_comparator_stress_slice"
V10_CHILD_OUTPUT_DIRNAME = "v0_10_fresh_comparator_stress_slice"
V10_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v10_policy_artifact_v0.1.0"
V10_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v10_fresh_comparator_stress_manifest_v0.1.0"
V10_COMPARATOR_STRESS_GATE_SCHEMA_VERSION = "rdf_mvp2e_v10_comparator_stress_gate_v0.1.0"
V10_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v10_calibration_presignal_gate_v0.1.0"
V10_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v10_heldout_closure_gate_v0.1.0"
V10_FRESH_CALIBRATION_RANGE = range(31000, 31030)
V10_FRESH_HELDOUT_RANGE = range(32000, 32050)
V10_BASELINE_FAILURE_MATERIAL_RATIO = 0.70
V10_CALIBRATION_SUCCESS_MINIMUM = 0.80
V10_CALIBRATION_UPLIFT_MINIMUM = 0.20
```

- [ ] **Step 2: Add parent loader**

Implement `load_required_v09a_heldout_uplift_shortfall_diagnosis(output_dir)`.
It must require:

```text
policy_slice == "v0_9a"
source_policy_slice == "v0_9"
opened_heldout_can_no_longer_close_minimum == true
recommended_downstream_slice == "v0_10_fresh_comparator_stress_slice"
mvp2_closed == false
policy_uplift_proven == false
```

- [ ] **Step 3: Build v0.10 rows**

Reuse v0.9 candidate rows and failed train-generation rows. Build:

```text
candidate_rows_v10 = candidate_rows_v09 unchanged
baseline_rows_v10 = accepted/success rows + deterministic duplicated failure rows
target failure row ratio = 0.70
allowed actual ratio = [0.65, 0.75]
```

- [ ] **Step 4: Train policies and write artifacts**

Use existing `fit_phase_conditioned_bc_policy` and `write_v07c_residual_train_view_hdf5`.
Copy shared v0.9 policy authority fields into v0.10 policy artifacts.

- [ ] **Step 5: Write manifest/gate**

Write:

```text
v0_10_comparator_stress_config.json
comparator_stress_gate_v0_10.json
v0_10_comparator_stress_manifest.json
candidate_curated_train_v0_10.hdf5
baseline_uncurated_stress_train_v0_10.hdf5
candidate_policy_artifact_v0_10.json
baseline_policy_artifact_v0_10.json
```

### Task 3: Implement v0.10 fresh runtime path

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add `build_v10_fresh_manifest(output_dir, stress_manifest)`.
- [ ] Add `_v10_runtime_manifest_for_split(fresh_manifest, split)`.
- [ ] Add `derive_v10_calibration_presignal_gate(...)` with:

```text
candidate_calibration_success_rate >= 0.80
candidate_baseline_success_gap >= 0.20
heldout_allowed=true only if both pass
```

- [ ] Add `run_v10_fresh_comparator_stress_runtime(...)`.
- [ ] Calibration uses `31000-31029`; held-out uses `32000-32049`.
- [ ] If calibration fails, return calibration gate and do not open held-out.
- [ ] If calibration passes, run actual held-out 50/policy and write `heldout_closure_gate_v0_10.json`.

### Task 4: CLI wiring

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add `--policy-slice v0_10`.
- [ ] Add `--fresh-comparator-stress-only`.
- [ ] Add `--fresh-comparator-stress-runtime`.
- [ ] Add `_command_from_args` support.
- [ ] Add main branches and evidence manifest metadata.
- [ ] Reject `--clean` for both v0.10 modes.
- [ ] Runtime branch rejects fake backend flags.

### Task 5: Verification

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09a or v10" -q
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

Then run artifact-only build:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_10 \
  --fresh-comparator-stress-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

If artifact build passes, run actual Isaac runtime:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_10 \
  --fresh-comparator-stress-runtime \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

### Task 6: Next loop

- If v0.10 closes MVP-2, freeze final proof package.
- If calibration fails, immediately write `v0_10a_calibration_shortfall_diagnosis`.
- If held-out opens but uplift fails, immediately write `v0_10b_heldout_shortfall_diagnosis`.
