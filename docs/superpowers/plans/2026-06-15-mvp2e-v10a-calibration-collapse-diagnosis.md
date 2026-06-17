# MVP-2E v0.10a Calibration Collapse Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an artifact-only v0.10a diagnosis and a minimal v0.10b runtime lineage repair so the next v0.10 actual Isaac calibration rerun uses the inherited v0.9 authority stack.

**Architecture:** `scripts/run_mvp2c_isaac_training_calibration.py` owns v0.10a artifact loading/classification/CLI. `scripts/run_mvp2b_isaac_proof_evaluator.py` owns runtime policy-slice allowlists, so v0.10b repairs only the evaluator lineage list. Tests prove the diagnosis catches current v0.10 collapse and that `v0_10` now receives v0.9-derived hysteresis/final-z/xy/safe-entry authority.

**Tech Stack:** Python 3.11, pytest, JSON proof artifacts, existing Isaac evaluator action-path helpers.

---

### Task 1: RED tests for v0.10a diagnosis

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add fake v0.10 failed calibration evidence helper**

Add helper near existing v0.10 tests:

```python
def _write_fake_v10_failed_calibration_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v10_parent_evidence(script, output_dir)
    manifest = script.build_v10_fresh_comparator_stress_slice(output_dir=output_dir)
    child_dir = output_dir / script.V10_CHILD_OUTPUT_DIRNAME
    trace_dir = (
        child_dir
        / "isaac_runtime_fresh_calibration_v0_10"
        / "isaac_runtime_heldout_rollout_traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)
    script.write_json(
        child_dir / "calibration_presignal_gate_v0_10.json",
        {
            "schema_version": script.V10_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
            "policy_slice": "v0_10",
            "slice_id": script.V10_SLICE_ID,
            "runtime_backend": "isaac_runtime",
            "passed": False,
            "failure_reason": "candidate_calibration_success_below_v0_10_minimum",
            "baseline_calibration_success_count": 0,
            "baseline_calibration_rollout_count": 30,
            "baseline_calibration_success_rate": 0.0,
            "candidate_calibration_success_count": 1,
            "candidate_calibration_rollout_count": 30,
            "candidate_calibration_success_rate": 1.0 / 30.0,
            "candidate_baseline_success_gap": 1.0 / 30.0,
            "heldout_allowed": False,
            "heldout_opened": False,
            "fresh_calibration_31000_31029_accessed": True,
            "fresh_heldout_32000_32049_accessed": False,
            "mvp2_closed": False,
            "policy_uplift_proven": False,
        },
    )
    candidate_rollouts = []
    baseline_rollouts = []
    for index, seed in enumerate(range(31000, 31030)):
        success = seed == 31012
        for role in ("candidate", "baseline"):
            trace_path = trace_dir / f"{role}_{index:04d}_calibration_{seed}_isaac_trace.json"
            script.write_json(
                trace_path,
                {
                    "schema_version": "rdf_mvp2b_isaac_runtime_trace_v0.1.0",
                    "runtime_backend": "isaac_runtime",
                    "scenario": {"scenario_id": f"calibration_{seed}", "seed": seed},
                    "summary": {
                        "success": success if role == "candidate" else False,
                        "env_native_rollout_success": success if role == "candidate" else False,
                        "env_native_max_consecutive_success_steps": 10 if success and role == "candidate" else 0,
                        "failure_reason": "" if success and role == "candidate" else "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
                        "steps": 2,
                    },
                    "trace": [
                        {
                            "step": 0,
                            "phase": "APPROACH",
                            "behavior_state_phase": "ALIGN",
                            "insertion_depth_m": 0.0,
                            "relative_x_m": 0.004,
                            "relative_y_m": 0.003,
                            "lateral_error_m": 0.005,
                            "orientation_error_deg": 0.08,
                            "env_native_success": False,
                            "controller_action_diagnostics": {
                                "policy_slice": "v0_10",
                                "behavior_state_phase": "ALIGN",
                                "behavior_state_phase_source": "derived_v0_7a_2_runtime_rule",
                                "z_motion_block_reason": "no_v06_controller",
                                "post_adapter_action_vector": [0.05, 0.05, -0.16, 0.0, 0.0, 0.0, 1.0],
                                "no_mutation_after_final_post_adapter_authority": False,
                            },
                        },
                        {
                            "step": 1,
                            "phase": "APPROACH",
                            "behavior_state_phase": "ALIGN",
                            "insertion_depth_m": 0.0,
                            "relative_x_m": 0.004,
                            "relative_y_m": 0.004,
                            "lateral_error_m": 0.006,
                            "orientation_error_deg": 0.08,
                            "env_native_success": False,
                            "controller_action_diagnostics": {
                                "policy_slice": "v0_10",
                                "behavior_state_phase": "ALIGN",
                                "behavior_state_phase_source": "derived_v0_7a_2_runtime_rule",
                                "z_motion_block_reason": "no_v06_controller",
                                "post_adapter_action_vector": [0.05, -0.05, -0.16, 0.0, 0.0, 0.0, 1.0],
                                "no_mutation_after_final_post_adapter_authority": False,
                            },
                        },
                    ],
                },
            )
        candidate_rollouts.append(
            {
                "rollout_id": f"candidate_isaac_{index:04d}",
                "scenario_id": f"calibration_{seed}",
                "success": success,
                "env_native_rollout_success": success,
                "env_native_max_consecutive_success_steps": 10 if success else 0,
                "rollout_log_ref": str(trace_dir / f"candidate_{index:04d}_calibration_{seed}_isaac_trace.json"),
            }
        )
        baseline_rollouts.append(
            {
                "rollout_id": f"baseline_isaac_{index:04d}",
                "scenario_id": f"calibration_{seed}",
                "success": False,
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "rollout_log_ref": str(trace_dir / f"baseline_{index:04d}_calibration_{seed}_isaac_trace.json"),
            }
        )
    rollout_dir = child_dir / "calibration_external_rollouts"
    rollout_dir.mkdir(parents=True, exist_ok=True)
    script.write_json(rollout_dir / "candidate_calibration_rollouts_v0_10.json", candidate_rollouts)
    script.write_json(rollout_dir / "baseline_calibration_rollouts_v0_10.json", baseline_rollouts)
```

- [ ] **Step 2: Add diagnosis test**

```python
def test_v10a_classifies_runtime_policy_slice_authority_lineage_missing(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_failed_calibration_evidence(script, tmp_path)

    report = script.build_v10a_calibration_collapse_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_10a"
    assert report["source_policy_slice"] == "v0_10"
    assert report["runtime_backend"] == "offline_artifact_diagnosis"
    assert report["v0_10_calibration_success"] == {"baseline": 0, "candidate": 1, "total": 30}
    assert report["candidate_weights_unchanged_from_v09"] is True
    assert report["candidate_authority_hashes_unchanged_from_v09"] is True
    assert report["primary_root_cause_class"] == "RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING"
    assert report["recommended_downstream_slice"] == "v0_10b_runtime_policy_slice_authority_lineage_repair"
    assert report["fresh_heldout_32000_32049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False
```

- [ ] **Step 3: Add CLI test**

```python
def test_v10a_cli_runs_artifact_only_calibration_collapse_diagnosis(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v10_failed_calibration_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_10a",
            "--fresh-comparator-calibration-diagnosis-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    report = script.read_json(
        tmp_path
        / script.V10A_CHILD_OUTPUT_DIRNAME
        / "v0_10a_calibration_collapse_diagnosis_report.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert report["primary_root_cause_class"] == "RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING"
    assert evidence_manifest["proof_runtime"] == script.V10A_SLICE_ID
    assert evidence_manifest["recommended_downstream_slice"] == "v0_10b_runtime_policy_slice_authority_lineage_repair"
```

- [ ] **Step 4: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10a" -q
```

Expected: fail because `V10A_*`, `build_v10a_calibration_collapse_diagnosis`, and CLI flag do not exist.

### Task 2: Implement v0.10a artifact-only diagnosis

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants**

```python
V10A_POLICY_SLICE_ID = "v0_10a"
V10A_SLICE_ID = "mvp2e_v10a_calibration_collapse_diagnosis"
V10A_CHILD_OUTPUT_DIRNAME = "v0_10a_calibration_collapse_diagnosis"
V10A_DIAGNOSIS_SCHEMA_VERSION = "rdf_mvp2e_v10a_calibration_collapse_diagnosis_v0.1.0"
V10A_RECOMMENDED_DOWNSTREAM_SLICE = "v0_10b_runtime_policy_slice_authority_lineage_repair"
```

- [ ] **Step 2: Add trace diagnostics summarizer**

Add helpers that read trace JSON files and count:

```text
row_count
no_v06_controller_count
shared_hysteresis_authority_count
final_post_adapter_authority_count
final_post_adapter_xy_authority_count
safe_entry_authority_count
no_mutation_after_final_post_adapter_authority_count
policy_slices_observed
```

Use `trace` rows and `controller_action_diagnostics`.

- [ ] **Step 3: Add diagnosis builder**

Implement `build_v10a_calibration_collapse_diagnosis(output_dir)`.

Required behavior:

- Load v0.10 failed calibration gate.
- Reject if v0.10 calibration passed.
- Reject if held-out `32000-32049` was opened.
- Load v0.10/v0.9 candidate policies.
- Compare candidate weights/bias and authority hash keys.
- Compare v0.10 candidate trace diagnostics against v0.9 candidate trace diagnostics.
- Classify `RUNTIME_POLICY_SLICE_AUTHORITY_LINEAGE_MISSING` when v0.10 inherited configs are present but diagnostics are absent.
- Write `v0_10a_calibration_collapse_diagnosis_report.json`.

- [ ] **Step 4: Add CLI branch**

Add:

```text
--fresh-comparator-calibration-diagnosis-only
--policy-slice v0_10a
```

Branch behavior:

- Reject `--clean`.
- Require `--scenario-profile v0_6 --policy-slice v0_10a`.
- Run builder and write `evidence_manifest.json`.

### Task 3: RED test for v0.10b runtime lineage repair

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add test that v0_10 policy receives inherited authority at runtime**

```python
def test_v10b_runtime_policy_slice_uses_v09_derived_authority_lineage(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    evaluator = load_script("run_mvp2b_isaac_proof_evaluator")
    _write_fake_v10_failed_calibration_evidence(script, tmp_path)

    policy = script.read_json(
        tmp_path / script.V10_CHILD_OUTPUT_DIRNAME / "candidate_policy_artifact_v0_10.json"
    )
    action, diagnostics = evaluator._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "step": 0,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.004,
            "relative_y_m": 0.003,
            "lateral_error_m": 0.005,
            "orientation_error_deg": 0.08,
            "env_native_success": False,
            "env_native_current_consecutive_success_steps": 0,
        },
        previous_action=[0.0] * len(evaluator.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert policy["policy_slice"] == "v0_10"
    assert diagnostics["policy_slice"] == "v0_10"
    assert diagnostics["shared_hysteresis_authority_id"] == "shared_stateful_hysteresis_authority_v0_7e"
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["final_post_adapter_xy_authority_id"] == "final_post_adapter_xy_authority_gate_v0_7o"
    assert diagnostics["no_mutation_after_final_post_adapter_authority"] is True
    assert diagnostics["z_motion_block_reason"] != "no_v06_controller"
    assert action[2] == pytest.approx(0.0)
```

- [ ] **Step 2: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10b_runtime_policy_slice" -q
```

Expected: fail because `v0_10` is not in the evaluator runtime allowlist.

### Task 4: Implement v0.10b minimal runtime lineage repair

**Files:**

- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add `V10_POLICY_SLICE_ID`**

```python
V10_POLICY_SLICE_ID = "v0_10"
```

- [ ] **Step 2: Add v0_10 to the v0.9-derived runtime authority family**

Change:

```python
V08H_DERIVED_POLICY_SLICE_IDS = {V08H_POLICY_SLICE_ID, V08K_POLICY_SLICE_ID, V09_POLICY_SLICE_ID}
```

to:

```python
V08H_DERIVED_POLICY_SLICE_IDS = {
    V08H_POLICY_SLICE_ID,
    V08K_POLICY_SLICE_ID,
    V09_POLICY_SLICE_ID,
    V10_POLICY_SLICE_ID,
}
```

Do not change authority config hashes, policy artifacts, trainer, success metric, or seed ranges.

### Task 5: Verification and next proof attempt

**Files:**

- Modify: `Handoff.md`
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10a or v10b" -q
```

- [ ] **Step 2: Run broader focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09a or v10 or v10a or v10b" -q
```

- [ ] **Step 3: Run static checks**

```bash
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check -- scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py docs/superpowers/specs/2026-06-15-mvp2e-v10a-calibration-collapse-diagnosis-design.md docs/superpowers/plans/2026-06-15-mvp2e-v10a-calibration-collapse-diagnosis.md Handoff.md docs/developer/worklog.md tasks/todo.md
```

- [ ] **Step 4: Run artifact-only diagnosis**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_10a \
  --fresh-comparator-calibration-diagnosis-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

- [ ] **Step 5: Rerun actual v0.10 calibration/held-out gate if tests pass**

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

Expected:

- If calibration passes, the script may open sealed held-out `32000-32049`.
- If calibration still fails, preserve evidence and continue the autonomous diagnosis loop with a new slice.
