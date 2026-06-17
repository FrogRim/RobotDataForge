# MVP-2E v0.8h Early-Centered Z Open / Safe Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_8h` so centered seeds can open z before the old deadline while unsafe lateral seeds keep z blocked even after the old deadline, then use a fresh calibration split before opening held-out `27000-27049`.

**Architecture:** Preserve `v0_8g` as historical evidence and add a new `v0_8h` policy slice. Reuse the v0.8g builder/runtime pattern, but replace deadline-precedence force with safe-entry action authority and fresh calibration range `28500-28529`.

**Tech Stack:** Python 3.11, pytest, existing Isaac evaluator backend, existing JSON proof artifact helpers.

---

## Files

Modify:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
scripts/run_mvp2c_isaac_training_calibration.py
apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
docs/developer/worklog.md
docs/developer/debugging_guide.md
tasks/todo.md
Handoff.md
```

Create:

```text
docs/superpowers/specs/2026-06-15-mvp2e-v08h-early-centered-z-open-safe-entry-design.md
docs/superpowers/plans/2026-06-15-mvp2e-v08h-early-centered-z-open-safe-entry.md
```

## Task 1: Evaluator RED Tests

- [ ] Add helper `_v08h_safe_entry_config(script)`.
- [ ] Add helper `_v08h_policy_artifact(script, role="candidate")`.
- [ ] Add test `test_v08h_early_centered_z_opens_before_reference_deadline`.
- [ ] Metric row:

```python
{
    "step": 58,
    "lateral_error_m": 0.004,
    "relative_x_m": 0.004,
    "relative_y_m": 0.0,
    "insertion_depth_m": 0.0,
    "env_native_success": False,
}
```

- [ ] Expected final action:

```text
z=-0.16
reason=early_centered_safe_entry_z
```

- [ ] Add test `test_v08h_unsafe_lateral_blocks_z_after_reference_deadline`.
- [ ] Metric row:

```python
{
    "step": 80,
    "lateral_error_m": 0.007,
    "relative_x_m": 0.007,
    "relative_y_m": -0.001,
    "insertion_depth_m": 0.0,
    "env_native_success": False,
}
```

- [ ] Expected final action:

```text
z=0.0
XY recomputed by capture authority
reason=unsafe_lateral_z_block
```

- [ ] Add test `test_v08h_depth_progress_continuation_keeps_z_open`.
- [ ] Metric row:

```python
{
    "step": 96,
    "lateral_error_m": 0.0058,
    "relative_x_m": 0.0058,
    "relative_y_m": 0.0,
    "insertion_depth_m": 0.010,
    "env_native_success": False,
}
```

- [ ] Expected final action:

```text
z=-0.16
reason=depth_progress_continuation_z
```

- [ ] Add test `test_v08h_env_native_success_stops_forced_z`.
- [ ] Same row with `env_native_success=True` must not force z.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08h" -q
```

- [ ] Expected before implementation: fail because v0.8h symbols do not exist.

## Task 2: Evaluator Implementation

- [ ] Add constants:

```python
V08H_POLICY_SLICE_ID = "v0_8h"
V08H_SLICE_ID = "mvp2e_v08h_early_centered_z_open_safe_entry"
V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08h_early_centered_z_open_safe_entry_config_v0.1.0"
)
V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_AUTHORITY_ID = (
    "early_centered_z_open_safe_entry_authority_v0_8h"
)
```

- [ ] Add `_validated_v08h_early_centered_z_open_safe_entry_config(policy_artifact)`.
- [ ] Add `_apply_v08h_early_centered_z_open_safe_entry(action, metric_row, config)`.
- [ ] Priority order:

```text
env_native_success
depth-progress continuation
early centered safe entry
unsafe lateral z block
before capture prepare start
```

- [ ] Wire `policy_slice=="v0_8h"` in `_apply_selected_action_adapter_with_diagnostics`.
- [ ] Run evaluator v0.8h tests and verify they pass.

## Task 3: Training/Calibration RED Tests

- [ ] Add tests in `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`.
- [ ] Test `test_v08h_requires_failed_v08g_calibration_gate`:
  - call `build_v08h_early_centered_z_open_safe_entry_slice` without v0.8g gate.
  - expect `missing_v0_8g_calibration_presignal_gate`.
- [ ] Test `test_v08h_builds_fresh_manifest_and_peer_fair_artifacts`:
  - create v0.8g failed calibration gate and parent artifacts.
  - build v0.8h slice.
  - assert `policy_slice="v0_8h"`.
  - assert fresh calibration `[28500,28529]`.
  - assert fresh held-out `[27000,27049]`.
  - assert burned calibration includes `[28000,28029]`.
  - assert candidate/baseline v0.8h config hashes match.
- [ ] Test `test_v08h_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac`:
  - fake calibration: baseline 15/30, candidate 29/30.
  - fake held-out: baseline 30/50, candidate 50/50.
  - assert held-out opens only after calibration pass.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08h" -q
```

- [ ] Expected before implementation: fail because v0.8h builder and CLI flag do not exist.

## Task 4: Training/Calibration Implementation

- [ ] Add constants:

```python
V08H_POLICY_SLICE_ID = "v0_8h"
V08H_SLICE_ID = "mvp2e_v08h_early_centered_z_open_safe_entry"
V08H_CHILD_OUTPUT_DIRNAME = "v0_8h_early_centered_z_open_safe_entry"
V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08h_early_centered_z_open_safe_entry_config_v0.1.0"
)
V08H_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v08h_policy_artifact_v0.1.0"
V08H_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v08h_early_centered_z_open_safe_entry_manifest_v0.1.0"
V08H_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v08h_calibration_presignal_gate_v0.1.0"
V08H_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v08h_heldout_closure_gate_v0.1.0"
V08H_EARLY_CENTERED_Z_OPEN_SAFE_ENTRY_AUTHORITY_ID = "early_centered_z_open_safe_entry_authority_v0_8h"
V08H_FRESH_CALIBRATION_RANGE = range(28500, 28530)
V08H_FRESH_HELDOUT_RANGE = range(27000, 27050)
```

- [ ] Add `load_required_v08g_failed_calibration_gate(output_dir)`.
- [ ] Add `derive_v08h_early_centered_z_open_safe_entry_config(output_dir)`.
- [ ] Add `build_v08h_policy_artifact_payload(...)`.
- [ ] Add `build_v08h_fresh_manifest(...)`.
- [ ] Add `build_v08h_early_centered_z_open_safe_entry_slice(output_dir=...)`.
- [ ] Add `_load_v08h_policy_artifacts(output_dir)`.
- [ ] Add `_v08h_runtime_manifest_for_split(...)`.
- [ ] Add `derive_v08h_calibration_presignal_gate(...)`.
- [ ] Add `run_v08h_early_centered_z_open_safe_entry_runtime(...)`.

## Task 5: CLI Wiring

- [ ] Add `v0_8h` to `--policy-slice` choices.
- [ ] Add `--early-centered-z-open-safe-entry-only`.
- [ ] Add a mode gate requiring:

```text
--scenario-profile v0_6
--policy-slice v0_8h
--early-centered-z-open-safe-entry-only
```

- [ ] Evidence manifest must include:

```text
proof_runtime=mvp2e_v08h_early_centered_z_open_safe_entry
policy_slice=v0_8h
calibration_opened=true
heldout_opened=<gate value>
fresh_calibration_28500_28529_accessed=true
fresh_heldout_27000_27049_accessed=<gate value>
mvp2_closed=<gate value>
policy_uplift_proven=<gate value>
```

## Task 6: Verification

- [ ] Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08h" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08g or v08h" -q
```

- [ ] Run broader regression:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08f or v08g or v08h" -q
```

- [ ] Run static checks:

```bash
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

## Task 7: Actual Isaac v0.8h Proof Attempt

- [ ] Run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8h \
  --early-centered-z-open-safe-entry-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

- [ ] If calibration fails, do not open held-out; immediately diagnose the new calibration failure.
- [ ] If calibration passes and held-out runs, read `heldout_closure_gate_v0_8h.json`.
- [ ] If held-out closes MVP-2, update docs and report final closure evidence.
- [ ] If held-out fails, preserve evidence and continue the autonomous loop with a new diagnosis slice.

## Stop Conditions

Stop this slice only if:

```text
v0.8g failed calibration evidence is missing or invalid
fresh held-out 27000-27049 has already been opened by another slice
the repair requires changing env-native 10-consecutive success authority
the implementation would require retry, withdraw, search, force-control, real robot, HMD, or policy uplift overclaim
```
