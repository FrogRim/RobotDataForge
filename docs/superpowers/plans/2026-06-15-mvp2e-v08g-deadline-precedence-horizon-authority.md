# MVP-2E v0.8g Deadline-Precedence Horizon Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_8g` so horizon-reserved z progress takes precedence over capture-wait after the deadline, using a fresh calibration split before opening held-out `27000-27049`.

**Architecture:** Preserve `v0_8f` as historical evidence and add a new `v0_8g` policy slice. Reuse the v0.8f builder/runtime pattern, but add a deadline-precedence action authority in the evaluator and fresh calibration range `28000-28029`.

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
docs/superpowers/specs/2026-06-15-mvp2e-v08g-deadline-precedence-horizon-authority-design.md
docs/superpowers/plans/2026-06-15-mvp2e-v08g-deadline-precedence-horizon-authority.md
```

## Task 1: Evaluator RED Tests

- [ ] Add evaluator test `test_v08g_deadline_precedence_overrides_capture_wait`.
- [ ] Use a minimal `policy_slice="v0_8g"` policy artifact with v0.8g config.
- [ ] Metric row:

```python
{
    "step": 80,
    "lateral_error_m": 0.006,
    "relative_x_m": 0.006,
    "relative_y_m": -0.002,
    "insertion_depth_m": 0.0,
    "env_native_success": False,
}
```

- [ ] Input action can have positive/zero z.
- [ ] Expected final action:

```text
z=-0.16
XY recomputed by capture authority
reason=forced_horizon_reserved_progress_z_deadline_precedence
```

- [ ] Add test `test_v08g_env_native_success_stops_forced_z`.
- [ ] Same metric row with `env_native_success=True` must not force z progress.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08g" -q
```

- [ ] Expected before implementation: fail because v0.8g symbols do not exist.

## Task 2: Evaluator Implementation

- [ ] Add constants:

```python
V08G_POLICY_SLICE_ID = "v0_8g"
V08G_SLICE_ID = "mvp2e_v08g_deadline_precedence_horizon_authority"
V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08g_deadline_precedence_horizon_authority_config_v0.1.0"
)
V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_ID = (
    "deadline_precedence_horizon_authority_v0_8g"
)
```

- [ ] Add `_validated_v08g_deadline_precedence_horizon_authority_config(policy_artifact)`.
- [ ] Add `_apply_v08g_deadline_precedence_horizon_authority(action, metric_row, config)`.
- [ ] Priority order:

```text
env_native_success
deadline forced z
capture wait
before deadline
```

- [ ] Wire `policy_slice=="v0_8g"` in `_apply_selected_action_adapter_with_diagnostics`.
- [ ] Run evaluator v0.8g tests and verify they pass.

## Task 3: Training/Calibration RED Tests

- [ ] Add tests in `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`.
- [ ] Test `test_v08g_requires_failed_v08f_calibration_gate`:
  - call `build_v08g_deadline_precedence_horizon_authority_slice` without v0.8f gate.
  - expect `missing_v0_8f_calibration_presignal_gate`.
- [ ] Test `test_v08g_builds_fresh_manifest_and_peer_fair_artifacts`:
  - create v0.8f failed calibration gate and parent artifacts.
  - build v0.8g slice.
  - assert `policy_slice="v0_8g"`.
  - assert fresh calibration `[28000,28029]`.
  - assert fresh held-out `[27000,27049]`.
  - assert burned calibration includes `[27500,27529]`.
  - assert candidate/baseline v0.8g config hashes match.
- [ ] Test `test_v08g_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac`:
  - fake calibration: baseline 15/30, candidate 29/30.
  - fake held-out: baseline 30/50, candidate 50/50.
  - assert held-out opens only after calibration pass.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08g" -q
```

- [ ] Expected before implementation: fail because v0.8g builder and CLI flag do not exist.

## Task 4: Training/Calibration Implementation

- [ ] Add constants:

```python
V08G_POLICY_SLICE_ID = "v0_8g"
V08G_SLICE_ID = "mvp2e_v08g_deadline_precedence_horizon_authority"
V08G_CHILD_OUTPUT_DIRNAME = "v0_8g_deadline_precedence_horizon_authority"
V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08g_deadline_precedence_horizon_authority_config_v0.1.0"
)
V08G_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v08g_policy_artifact_v0.1.0"
V08G_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v08g_deadline_precedence_horizon_authority_manifest_v0.1.0"
V08G_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v08g_calibration_presignal_gate_v0.1.0"
V08G_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v08g_heldout_closure_gate_v0.1.0"
V08G_DEADLINE_PRECEDENCE_HORIZON_AUTHORITY_ID = "deadline_precedence_horizon_authority_v0_8g"
V08G_FRESH_CALIBRATION_RANGE = range(28000, 28030)
V08G_FRESH_HELDOUT_RANGE = range(27000, 27050)
```

- [ ] Add `load_required_v08f_failed_calibration_gate(output_dir)`.
- [ ] Add `derive_v08g_deadline_precedence_horizon_authority_config(output_dir)`.
- [ ] Add `build_v08g_policy_artifact_payload(...)`.
- [ ] Add `build_v08g_fresh_manifest(...)`.
- [ ] Add `build_v08g_deadline_precedence_horizon_authority_slice(output_dir=...)`.
- [ ] Add `_load_v08g_policy_artifacts(output_dir)`.
- [ ] Add `_v08g_runtime_manifest_for_split(...)`.
- [ ] Add `derive_v08g_calibration_presignal_gate(...)`.
- [ ] Add `run_v08g_deadline_precedence_horizon_authority_runtime(...)`.

## Task 5: CLI Wiring

- [ ] Add `v0_8g` to `--policy-slice` choices.
- [ ] Add `--deadline-precedence-horizon-authority-only`.
- [ ] Add a mode gate requiring:

```text
--scenario-profile v0_6
--policy-slice v0_8g
--deadline-precedence-horizon-authority-only
```

- [ ] Evidence manifest must include:

```text
proof_runtime=mvp2e_v08g_deadline_precedence_horizon_authority
policy_slice=v0_8g
calibration_opened=true
heldout_opened=<gate value>
fresh_calibration_28000_28029_accessed=true
fresh_heldout_27000_27049_accessed=<gate value>
mvp2_closed=<gate value>
policy_uplift_proven=<gate value>
```

## Task 6: Verification

- [ ] Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08g" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08f or v08g" -q
```

- [ ] Run broader regression:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08d or v08e or v08f or v08g" -q
```

- [ ] Run static checks:

```bash
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

## Task 7: Actual Isaac v0.8g Proof Attempt

- [ ] Run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8g \
  --deadline-precedence-horizon-authority-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

- [ ] If calibration fails, do not open held-out; immediately diagnose the new calibration failure.
- [ ] If calibration passes and held-out runs, read `heldout_closure_gate_v0_8g.json`.
- [ ] If held-out closes MVP-2, update docs and report final closure evidence.
- [ ] If held-out fails, preserve evidence and continue the autonomous loop with a new diagnosis slice.

## Stop Conditions

Stop this slice only if:

```text
v0.8f failed calibration evidence is missing or invalid
fresh held-out 27000-27049 has already been opened by another slice
the repair requires changing env-native 10-consecutive success authority
the implementation would require retry, withdraw, search, force-control, real robot, HMD, or policy uplift overclaim
```
