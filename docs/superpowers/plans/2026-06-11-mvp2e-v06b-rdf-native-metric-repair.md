# MVP-2E v0.6b RDF/native Metric Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the runtime metric semantics that made RDF secondary geometry report success while Isaac Factory native success stayed false.

**Architecture:** Add Factory-native diagnostic helpers and a native-aligned runtime metric row path for actual Isaac PegInsert traces, while preserving legacy deterministic fixture metrics. The repair gate remains env-native authority; RDF geometry stays diagnostic.

**Tech Stack:** Python 3.11, pytest, IsaacLab runtime via lazy imports, existing `scripts/run_mvp2b_isaac_proof_evaluator.py` and `scripts/run_mvp2c_isaac_training_calibration.py`.

---

## File Structure

- Modify `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add pure Factory PegInsert native diagnostic helpers.
  - Add native-aligned runtime metric row builder.
  - Update Isaac runtime backend `_metric_row()` to use native-aligned row when Factory PegInsert config and `factory_utils` base/target pose are available.
  - Keep raw asset pose fields as evidence only; do not calculate `env_native_*` from raw pose deltas.
- Modify `scripts/run_mvp2c_isaac_training_calibration.py`
  - Ensure repair probe gate preserves native diagnostic fields in trace artifacts.
  - Ensure train gate remains blocked unless future repair probe is green.
- Modify `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add RED/GREEN unit tests for native diagnostic math and phase semantics.
- Modify `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add gate regression for RDF-only success.
- Modify docs:
  - `docs/developer/worklog.md`
  - `docs/developer/debugging_guide.md`
  - `tasks/todo.md`
  - `Handoff.md`

## Task 1: Add RED Tests For Native Metric Semantics

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add failing tests**

Add these tests near existing metric/evaluator tests:

```python
def test_factory_peg_insert_native_height_threshold_matches_factory_config():
    diag = script.build_factory_peg_insert_native_success_diagnostics(
        held_base_pos=[0.0, 0.0, 0.045],
        target_held_base_pos=[0.0, 0.0, 0.0],
        fixed_asset_height_m=0.025,
        success_threshold=0.04,
    )

    assert diag["env_native_height_threshold_m"] == 0.001
    assert diag["env_native_z_disp_m"] == 0.045
    assert diag["env_native_is_close_or_below"] is False
    assert diag["env_native_success_mask"] is False


def test_native_aligned_metric_row_does_not_label_high_z_disp_as_seat():
    row = script.factory_peg_insert_native_aligned_metric_row_from_pose_values(
        step=0,
        held_pos=[0.0, 0.0, 0.045],
        fixed_pos=[0.0, 0.0, 0.0],
        held_base_pos=[0.0, 0.0, 0.045],
        target_held_base_pos=[0.0, 0.0, 0.0],
        held_base_quat=[1.0, 0.0, 0.0, 0.0],
        target_held_base_quat=[1.0, 0.0, 0.0, 0.0],
        held_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_asset_height_m=0.025,
        success_threshold=0.04,
    )

    assert row["legacy_positive_z_disp_m"] == 0.045
    assert row["approach_height_m"] == 0.045
    assert row["native_seating_progress_m"] == 0.0
    assert row["runtime_depth_feature_m"] == 0.0
    assert row["insertion_depth_m"] == 0.0
    assert row["phase"] != "SEAT"


def test_native_aligned_metric_row_labels_near_native_target_as_seat_candidate():
    row = script.factory_peg_insert_native_aligned_metric_row_from_pose_values(
        step=0,
        held_pos=[0.0002, 0.0002, 0.0005],
        fixed_pos=[0.0, 0.0, 0.0],
        held_base_pos=[0.0002, 0.0002, 0.0005],
        target_held_base_pos=[0.0, 0.0, 0.0],
        held_base_quat=[1.0, 0.0, 0.0, 0.0],
        target_held_base_quat=[1.0, 0.0, 0.0, 0.0],
        held_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_quat=[1.0, 0.0, 0.0, 0.0],
        fixed_asset_height_m=0.025,
        success_threshold=0.04,
    )

    assert row["env_native_xy_dist_m"] < 0.0025
    assert row["env_native_z_disp_m"] < 0.001
    assert row["env_native_success_mask"] is True
    assert row["phase"] == "SEAT"
```

- [ ] **Step 2: Run targeted RED test**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "factory_peg_insert_native or native_aligned_metric" -q
```

Expected: FAIL because the new helper functions do not exist.

## Task 2: Implement Pure Native Diagnostic Helpers

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add pure helper functions**

Add after `rdf_compatible_metric_row_from_pose_values()`:

```python
def build_factory_peg_insert_native_success_diagnostics(
    *,
    held_base_pos: list[float] | np.ndarray,
    target_held_base_pos: list[float] | np.ndarray,
    fixed_asset_height_m: float,
    success_threshold: float,
    xy_threshold_m: float = 0.0025,
) -> dict[str, Any]:
    held = np.asarray(held_base_pos, dtype=np.float64)
    fixed = np.asarray(target_held_base_pos, dtype=np.float64)
    delta = held - fixed
    xy_dist = float(np.linalg.norm(delta[:2]))
    z_disp = float(delta[2])
    height_threshold = float(fixed_asset_height_m) * float(success_threshold)
    is_centered = xy_dist < float(xy_threshold_m)
    is_close_or_below = z_disp < height_threshold
    return {
        "env_native_xy_dist_m": round(xy_dist, 6),
        "env_native_z_disp_m": round(z_disp, 6),
        "env_native_height_threshold_m": round(height_threshold, 6),
        "env_native_xy_threshold_m": round(float(xy_threshold_m), 6),
        "env_native_is_centered": bool(is_centered),
        "env_native_is_close_or_below": bool(is_close_or_below),
        "env_native_success_mask": bool(is_centered and is_close_or_below),
        "env_native_diagnostics_source": "factory_utils_base_target",
        "factory_fixed_asset_height_m": round(float(fixed_asset_height_m), 6),
        "factory_success_threshold": round(float(success_threshold), 6),
    }
```

- [ ] **Step 2: Add phase helper**

```python
def _phase_from_native_seating_progress(
    *,
    approach_height_m: float,
    native_seating_progress_m: float,
    fixed_asset_height_m: float,
    env_native_success_mask: bool,
) -> str:
    if env_native_success_mask:
        return "SEAT"
    if float(approach_height_m) > 0.010:
        return "APPROACH"
    progress_ratio = float(native_seating_progress_m) / max(float(fixed_asset_height_m), 1.0e-9)
    if progress_ratio < 0.25:
        return "CONTACT"
    if progress_ratio < 0.90:
        return "INSERT"
    return "SEAT"
```

- [ ] **Step 3: Add native-aligned row builder**

```python
def factory_peg_insert_native_aligned_metric_row_from_pose_values(
    *,
    step: int,
    held_pos: list[float] | np.ndarray,
    fixed_pos: list[float] | np.ndarray,
    held_base_pos: list[float] | np.ndarray,
    target_held_base_pos: list[float] | np.ndarray,
    held_base_quat: list[float] | np.ndarray,
    target_held_base_quat: list[float] | np.ndarray,
    held_quat: list[float] | np.ndarray,
    fixed_quat: list[float] | np.ndarray,
    fixed_asset_height_m: float,
    success_threshold: float,
) -> dict[str, Any]:
    legacy = rdf_compatible_metric_row_from_pose_values(
        step=step,
        held_pos=held_pos,
        fixed_pos=fixed_pos,
        held_quat=held_quat,
        fixed_quat=fixed_quat,
    )
    diag = build_factory_peg_insert_native_success_diagnostics(
        held_base_pos=held_base_pos,
        target_held_base_pos=target_held_base_pos,
        fixed_asset_height_m=fixed_asset_height_m,
        success_threshold=success_threshold,
    )
    z_disp = float(diag["env_native_z_disp_m"])
    approach_height = max(0.0, z_disp)
    native_progress = max(0.0, float(fixed_asset_height_m) - max(z_disp, 0.0))
    phase = _phase_from_native_seating_progress(
        approach_height_m=approach_height,
        native_seating_progress_m=native_progress,
        fixed_asset_height_m=float(fixed_asset_height_m),
        env_native_success_mask=bool(diag["env_native_success_mask"]),
    )
    return {
        **legacy,
        "phase": phase,
        "legacy_positive_z_disp_m": legacy["insertion_depth_m"],
        "rdf_z_disp_legacy_m": legacy["insertion_depth_m"],
        "insertion_depth_m": round(native_progress, 6),
        "runtime_depth_feature_m": round(native_progress, 6),
        "approach_height_m": round(approach_height, 6),
        "native_seating_progress_m": round(native_progress, 6),
        "native_seating_margin_m": round(float(diag["env_native_height_threshold_m"]) - z_disp, 6),
        "rdf_metric_semantics": "factory_native_aligned_v0_6b",
        **diag,
        "held_base_pose_w": {
            "position_m": [round(float(value), 6) for value in np.asarray(held_base_pos, dtype=np.float64).tolist()],
            "quaternion_wxyz": [round(float(value), 6) for value in np.asarray(held_base_quat, dtype=np.float64).tolist()],
        },
        "target_held_base_pose_w": {
            "position_m": [round(float(value), 6) for value in np.asarray(target_held_base_pos, dtype=np.float64).tolist()],
            "quaternion_wxyz": [round(float(value), 6) for value in np.asarray(target_held_base_quat, dtype=np.float64).tolist()],
        },
        "held_asset_pose_w": {
            "position_m": [round(float(value), 6) for value in np.asarray(held_pos, dtype=np.float64).tolist()],
            "quaternion_wxyz": [round(float(value), 6) for value in np.asarray(held_quat, dtype=np.float64).tolist()],
        },
        "fixed_asset_pose_w": {
            "position_m": [round(float(value), 6) for value in np.asarray(fixed_pos, dtype=np.float64).tolist()],
            "quaternion_wxyz": [round(float(value), 6) for value in np.asarray(fixed_quat, dtype=np.float64).tolist()],
        },
        "rdf_relative_pose_inputs": {
            "held_pos_w": [round(float(value), 6) for value in np.asarray(held_pos, dtype=np.float64).tolist()],
            "fixed_pos_w": [round(float(value), 6) for value in np.asarray(fixed_pos, dtype=np.float64).tolist()],
        },
    }
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "factory_peg_insert_native or native_aligned_metric" -q
```

Expected: PASS.

## Task 3: Use Factory Base/Target Native-aligned Rows In Actual Runtime

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add Factory base/target pose extraction**

Inside runtime-only code, import Factory utilities lazily and compute the same
poses used by `_get_curr_successes`:

```python
def _factory_peg_insert_base_target_pose_from_env(unwrapped: Any) -> dict[str, np.ndarray] | None:
    cfg_task = getattr(unwrapped, "cfg_task", None)
    if str(getattr(cfg_task, "name", "")) != "peg_insert":
        return None
    try:
        import isaaclab_tasks.direct.factory.factory_utils as factory_utils
    except Exception:
        return None
    held_base_pos, held_base_quat = factory_utils.get_held_base_pose(
        getattr(unwrapped, "held_pos"),
        getattr(unwrapped, "held_quat"),
        cfg_task.name,
        cfg_task.fixed_asset_cfg,
        unwrapped.num_envs,
        unwrapped.device,
    )
    target_pos, target_quat = factory_utils.get_target_held_base_pose(
        getattr(unwrapped, "fixed_pos"),
        getattr(unwrapped, "fixed_quat"),
        cfg_task.name,
        cfg_task.fixed_asset_cfg,
        unwrapped.num_envs,
        unwrapped.device,
    )
    return {
        "held_base_pos": IsaacConnectorInsertionEvaluatorBackend._tensor_row(held_base_pos),
        "held_base_quat": IsaacConnectorInsertionEvaluatorBackend._tensor_row(held_base_quat),
        "target_held_base_pos": IsaacConnectorInsertionEvaluatorBackend._tensor_row(target_pos),
        "target_held_base_quat": IsaacConnectorInsertionEvaluatorBackend._tensor_row(target_quat),
    }
```

- [ ] **Step 2: Update `_metric_row()`**

Inside `IsaacConnectorInsertionEvaluatorBackend._metric_row()`, after reading
`held`, `fixed`, `held_quat`, and `fixed_quat`, branch on Factory PegInsert.
If Factory utilities are not available, return a legacy row with a diagnostic
blocker rather than approximate `env_native_*` fields:

```python
cfg_task = getattr(unwrapped, "cfg_task", None)
task_name = str(getattr(cfg_task, "name", ""))
fixed_asset_cfg = getattr(cfg_task, "fixed_asset_cfg", None)
fixed_asset_height_m = getattr(fixed_asset_cfg, "height", None)
success_threshold = getattr(cfg_task, "success_threshold", None)
if task_name == "peg_insert" and fixed_asset_height_m is not None and success_threshold is not None:
    native_pose = _factory_peg_insert_base_target_pose_from_env(unwrapped)
    if native_pose is None:
        row = rdf_compatible_metric_row_from_pose_values(
            step=step,
            held_pos=held,
            fixed_pos=fixed,
            held_quat=held_quat,
            fixed_quat=fixed_quat,
        )
        row["native_metric_blocker"] = "factory_utils_base_target_unavailable"
        row["env_native_diagnostics_source"] = "unavailable"
        return row
    return factory_peg_insert_native_aligned_metric_row_from_pose_values(
        step=step,
        held_pos=held,
        fixed_pos=fixed,
        held_base_pos=native_pose["held_base_pos"],
        target_held_base_pos=native_pose["target_held_base_pos"],
        held_base_quat=native_pose["held_base_quat"],
        target_held_base_quat=native_pose["target_held_base_quat"],
        held_quat=held_quat,
        fixed_quat=fixed_quat,
        fixed_asset_height_m=float(fixed_asset_height_m),
        success_threshold=float(success_threshold),
    )
return rdf_compatible_metric_row_from_pose_values(
    step=step,
    held_pos=held,
    fixed_pos=fixed,
    held_quat=held_quat,
    fixed_quat=fixed_quat,
)
```

- [ ] **Step 3: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: PASS.

## Task 4: Add v0.6b Trace Semantic Validator

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add failing validator tests**

Add tests:

```python
def test_v06b_trace_semantic_validator_requires_factory_base_target_source():
    verdict = script.validate_v06b_native_metric_trace_rows([
        {
            "env_native_success": True,
            "env_native_success_mask": True,
            "env_native_diagnostics_source": "raw_asset_delta_approximation",
            "legacy_positive_z_disp_m": 0.045,
            "runtime_depth_feature_m": 0.0,
        }
    ])

    assert verdict["valid"] is False
    assert "env_native_diagnostics_source" in verdict["reasons"]


def test_v06b_trace_semantic_validator_rejects_legacy_depth_feature_use():
    verdict = script.validate_v06b_native_metric_trace_rows([
        {
            "env_native_success": False,
            "env_native_success_mask": False,
            "env_native_diagnostics_source": "factory_utils_base_target",
            "legacy_positive_z_disp_m": 0.045,
            "runtime_depth_feature_m": 0.045,
            "insertion_depth_m": 0.045,
            "held_asset_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
            "fixed_asset_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
            "held_base_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
            "target_held_base_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
        }
    ])

    assert verdict["valid"] is False
    assert "runtime_depth_feature_m" in verdict["reasons"]


def test_v06b_trace_semantic_validator_requires_read_env_native_success_field():
    verdict = script.validate_v06b_native_metric_trace_rows([
        {
            "env_native_success_mask": False,
            "env_native_diagnostics_source": "factory_utils_base_target",
            "env_native_xy_dist_m": 0.0002,
            "env_native_z_disp_m": 0.045,
            "env_native_height_threshold_m": 0.001,
            "legacy_positive_z_disp_m": 0.045,
            "runtime_depth_feature_m": 0.0,
            "held_asset_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
            "fixed_asset_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
            "held_base_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
            "target_held_base_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
        }
    ])

    assert verdict["valid"] is False
    assert "missing_required_native_metric_fields" in verdict["reasons"]


def test_v06b_trace_semantic_validator_rejects_native_mask_mismatch():
    verdict = script.validate_v06b_native_metric_trace_rows([
        {
            "env_native_success": True,
            "env_native_success_mask": False,
            "env_native_diagnostics_source": "factory_utils_base_target",
            "env_native_xy_dist_m": 0.0002,
            "env_native_z_disp_m": 0.045,
            "env_native_height_threshold_m": 0.001,
            "legacy_positive_z_disp_m": 0.045,
            "runtime_depth_feature_m": 0.0,
            "held_asset_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
            "fixed_asset_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
            "held_base_pose_w": {"position_m": [0, 0, 0.045], "quaternion_wxyz": [1, 0, 0, 0]},
            "target_held_base_pose_w": {"position_m": [0, 0, 0], "quaternion_wxyz": [1, 0, 0, 0]},
        }
    ])

    assert verdict["valid"] is False
    assert "env_native_success_mask_mismatch" in verdict["reasons"]
```

- [ ] **Step 2: Implement validator**

Add:

```python
def validate_v06b_native_metric_trace_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    required = {
        "env_native_diagnostics_source",
        "env_native_success",
        "env_native_success_mask",
        "env_native_xy_dist_m",
        "env_native_z_disp_m",
        "env_native_height_threshold_m",
        "held_asset_pose_w",
        "fixed_asset_pose_w",
        "held_base_pose_w",
        "target_held_base_pose_w",
        "legacy_positive_z_disp_m",
        "runtime_depth_feature_m",
    }
    for row in rows:
        missing = sorted(required - set(row))
        if missing:
            reasons.append("missing_required_native_metric_fields")
        if row.get("env_native_diagnostics_source") != "factory_utils_base_target":
            reasons.append("env_native_diagnostics_source")
        if not isinstance(row.get("env_native_success"), bool):
            reasons.append("env_native_success")
        elif bool(row.get("env_native_success")) != bool(row.get("env_native_success_mask")):
            reasons.append("env_native_success_mask_mismatch")
        legacy = row.get("legacy_positive_z_disp_m")
        runtime_depth = row.get("runtime_depth_feature_m")
        if legacy is not None and runtime_depth is not None and abs(float(legacy) - float(runtime_depth)) < 1.0e-9 and float(legacy) > 0.001:
            reasons.append("runtime_depth_feature_m")
    return {"valid": not reasons, "reasons": sorted(set(reasons))}
```

- [ ] **Step 3: Connect validator to repair gate derivation**

In `derive_v06_repair_probe_gate_from_probe_result()`, validate every trace row.
If invalid, force:

```python
gate["green_light_for_40_run_gate"] = False
gate["hard_stop"] = True
gate["v0_6b_native_metric_trace_validation"] = verdict
gate["v0_6a_post_repair_probe_gate"] = {
    "green_light_for_40_run_gate": False,
    "proof_authority": False,
    "reason": "v0_6b_native_metric_trace_validation_failed",
}
```

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v06b_trace_semantic_validator or repair_probe_gate" -q
```

Expected: PASS.

## Task 5: Keep Repair Gate Env-native Only

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Inspect: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add gate regression test**

```python
def test_v06_repair_probe_gate_rejects_rdf_only_success():
    gate = script.evaluate_v06_repair_probe_gate({
        16023: {"env_native_rollout_success": False, "lateral_divergence_stopped": True},
        16042: {"env_native_rollout_success": False, "lateral_divergence_stopped": True},
        16096: {"env_native_rollout_success": False, "lateral_divergence_stopped": True},
    })

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["hard_stop"] is True
```

- [ ] **Step 2: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "repair_probe_gate" -q
```

Expected: PASS.

## Task 6: Runtime Repair Probe Verification

**Files:**
- Runtime artifacts under `/tmp/rdf-mvp2e-v06b-native-metric-repair`

- [ ] **Step 1: Run capture-radius preflight only**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06b-native-metric-repair \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected:

```text
preflight_branch in {A, B}
repair_probe_allowed=true
train_generation_gate_allowed=false
```

- [ ] **Step 2: Run repair probe only**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06b-native-metric-repair \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected if still blocked:

```text
green_light_for_40_run_gate=false
hard_stop=true
trace rows include env_native_xy_dist_m, env_native_z_disp_m,
env_native_height_threshold_m, env_native_is_centered,
env_native_is_close_or_below
```

Expected if unblocked:

```text
green_light_for_40_run_gate=true
```

Do not run fixed 40-run gate in this plan unless the user explicitly starts the
next ultragoal after reviewing this repair-probe evidence.

## Task 7: Documentation

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Record the root cause**

Record:

```text
RDF runtime insertion_depth_m previously represented positive z displacement
above the Factory target. Factory native success requires z_disp < 0.001m.
```

- [ ] **Step 2: Record the next gate**

Record:

```text
fixed 40-run gate remains forbidden unless a future repair_probe_gate has
green_light_for_40_run_gate=true and semantic validation passes.
```

## Verification Commands

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

## Stop Conditions

Stop and report if:

- changing env-native success authority becomes necessary;
- held-out would need to be opened;
- fixed 40-run gate would need to run without repair green light;
- old deterministic proof artifacts would require incompatible schema changes;
- Isaac runtime cannot expose native diagnostic inputs.

## Execution Recommendation

Use `$ultragoal` for sequential implementation after consensus approval. Use
`$team` only if splitting test/helper/runtime/doc lanes becomes necessary.
