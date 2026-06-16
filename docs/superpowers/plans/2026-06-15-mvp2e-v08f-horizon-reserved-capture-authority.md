# MVP-2E v0.8f Horizon-Reserved Capture Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_8f` so a shared horizon-reserved capture authority can recover v0.8d calibration shortfall on a fresh calibration split before opening held-out `27000-27049`.

**Architecture:** Extend the existing v0.8d runtime pattern in `scripts/run_mvp2c_isaac_training_calibration.py` and `scripts/run_mvp2b_isaac_proof_evaluator.py`. Add a new v0.8f config/policy/manifest builder, evaluator-side action authority, fresh calibration/held-out runner, CLI flag, and focused tests.

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
docs/superpowers/specs/2026-06-15-mvp2e-v08f-horizon-reserved-capture-authority-design.md
docs/superpowers/plans/2026-06-15-mvp2e-v08f-horizon-reserved-capture-authority.md
```

## Task 1: Evaluator RED Tests

- [ ] Add evaluator tests in `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`.
- [ ] Test `test_v08f_capture_wait_xy_override_blocks_z_and_recomputes_xy`:
  - build a minimal policy artifact with `policy_slice="v0_8f"`, shared v0.7o XY config, and v0.8f horizon config.
  - metric row: `step=60`, `lateral_error_m=0.006`, `relative_x_m=0.006`, `relative_y_m=-0.002`, `insertion_depth_m=0.0`, `env_native_success=false`.
  - raw action after adapter would have saturated/sign-mismatched XY and negative z.
  - expected final z is `0.0`, XY is `[-0.024,0.008]` clipped by config, reason is `capture_wait_xy_authority`, and rotation/gripper are preserved.
- [ ] Test `test_v08f_seat_region_keeps_z_until_env_native_success`:
  - metric row: `step=120`, `lateral_error_m=0.0002`, `insertion_depth_m=0.0245`, `env_native_success=false`.
  - expected final z is `-0.16` and reason is `forced_horizon_reserved_progress_z`.
  - same row with `env_native_success=true` must not force z progress.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08f" -q
```

- [ ] Expected before implementation: fail because v0.8f symbols do not exist.

## Task 2: Evaluator Implementation

- [ ] Add constants:

```python
V08F_POLICY_SLICE_ID = "v0_8f"
V08F_SLICE_ID = "mvp2e_v08f_horizon_reserved_capture_authority"
V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08f_horizon_reserved_capture_authority_config_v0.1.0"
)
V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_ID = "horizon_reserved_capture_authority_v0_8f"
```

- [ ] Add `_validated_v08f_horizon_reserved_capture_authority_config(policy_artifact)`.
- [ ] Add `_apply_v08f_horizon_reserved_capture_authority(action, metric_row, config)`.
- [ ] Wire `policy_slice=="v0_8f"` in `_apply_selected_action_adapter_with_diagnostics`.
- [ ] v0.8f must reuse v0.7o XY authority validation and must not call v0.8d validator.
- [ ] Run the evaluator v0.8f tests again and verify they pass.

## Task 3: Training/Calibration RED Tests

- [ ] Add tests in `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`.
- [ ] Test `test_v08f_requires_v08e_calibration_shortfall_diagnosis`:
  - call `build_v08f_horizon_reserved_capture_authority_slice` in an empty temp dir.
  - expect `missing_v0_8e_calibration_shortfall_diagnosis`.
- [ ] Test `test_v08f_builds_fresh_manifest_and_peer_fair_artifacts`:
  - create v0.8d parent artifacts and fake v0.8e diagnosis.
  - build v0.8f slice.
  - assert policy artifacts use `policy_slice="v0_8f"`.
  - assert candidate/baseline config hashes match.
  - assert fresh calibration `[27500,27529]`, fresh held-out `[27000,27049]`.
  - assert burned calibration includes `[26500,26529]`.
  - assert held-out `27000-27049` is not accessed.
- [ ] Test `test_v08f_cli_runs_fresh_calibration_before_fresh_heldout_with_fake_isaac`:
  - fake backend must see calibration seeds first and held-out seeds only after calibration pass.
  - fake calibration: baseline 17/30, candidate 28/30.
  - fake held-out: baseline 30/50, candidate 50/50.
  - assert calibration gate passes and closure gate can close in fake runtime.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08f" -q
```

- [ ] Expected before implementation: fail because v0.8f builder and CLI flag do not exist.

## Task 4: Training/Calibration Implementation

- [ ] Add constants:

```python
V08F_POLICY_SLICE_ID = "v0_8f"
V08F_SLICE_ID = "mvp2e_v08f_horizon_reserved_capture_authority"
V08F_CHILD_OUTPUT_DIRNAME = "v0_8f_horizon_reserved_capture_authority"
V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_CONFIG_SCHEMA_VERSION = (
    "rdf_mvp2e_v08f_horizon_reserved_capture_authority_config_v0.1.0"
)
V08F_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v08f_policy_artifact_v0.1.0"
V08F_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v08f_horizon_reserved_capture_authority_manifest_v0.1.0"
V08F_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v08f_calibration_presignal_gate_v0.1.0"
V08F_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v08f_heldout_closure_gate_v0.1.0"
V08F_HORIZON_RESERVED_CAPTURE_AUTHORITY_ID = "horizon_reserved_capture_authority_v0_8f"
V08F_FRESH_CALIBRATION_RANGE = range(27500, 27530)
V08F_FRESH_HELDOUT_RANGE = range(27000, 27050)
```

- [ ] Add `load_required_v08e_calibration_shortfall_diagnosis(output_dir)`.
- [ ] Add `derive_v08f_horizon_reserved_capture_authority_config(output_dir)`.
- [ ] Add `build_v08f_policy_artifact_payload(...)`.
- [ ] Add `build_v08f_fresh_manifest(...)`.
- [ ] Add `build_v08f_horizon_reserved_capture_authority_slice(output_dir=...)`.
- [ ] Add `_load_v08f_policy_artifacts(output_dir)`.
- [ ] Add `_v08f_runtime_manifest_for_split(...)`.
- [ ] Add `derive_v08f_calibration_presignal_gate(...)`.
- [ ] Add `run_v08f_horizon_reserved_capture_authority_runtime(...)`.
- [ ] The runner must stop before held-out if calibration fails.
- [ ] The runner must open `27000-27049` only after calibration passes.

## Task 5: CLI Wiring

- [ ] Add `v0_8f` to `--policy-slice` choices.
- [ ] Add `--horizon-reserved-capture-authority-only`.
- [ ] Add a mode gate requiring:

```text
--scenario-profile v0_6
--policy-slice v0_8f
--horizon-reserved-capture-authority-only
```

- [ ] Evidence manifest must include:

```text
proof_runtime=mvp2e_v08f_horizon_reserved_capture_authority
policy_slice=v0_8f
calibration_opened=true
heldout_opened=<gate value>
fresh_heldout_27000_27049_accessed=<gate value>
mvp2_closed=<gate value>
policy_uplift_proven=<gate value>
```

## Task 6: Verification

- [ ] Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08f" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08e or v08f" -q
```

- [ ] Run broader regression:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08d or v08e or v08f" -q
```

- [ ] Run static checks:

```bash
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

## Task 7: Actual Isaac v0.8f Proof Attempt

- [ ] Run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8f \
  --horizon-reserved-capture-authority-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

- [ ] If calibration fails, do not open held-out; immediately diagnose the new calibration failure.
- [ ] If calibration passes and held-out runs, read `heldout_closure_gate_v0_8f.json`.
- [ ] If held-out closes MVP-2, update docs and report final closure evidence.
- [ ] If held-out fails, preserve evidence and continue the autonomous loop with a new diagnosis slice.

## Stop Conditions

Stop this slice only if:

```text
v0.8e diagnosis is missing or invalid
fresh held-out 27000-27049 has already been opened by another slice
the repair requires changing env-native 10-consecutive success authority
the implementation would require retry, withdraw, search, force-control, real robot, HMD, or policy uplift overclaim
```
